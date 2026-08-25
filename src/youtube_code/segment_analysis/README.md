# Segment-Klassifikation

Eigenständige Pipeline für die LLM-Kodierung von Transkriptsegmenten.
Läuft **parallel** zur Politics-Screening-Pipeline; geteilt wird nur die
Registry-Datei. An `submit_batch_jobs.py` und `download_results.py` wird
nichts geändert.

## Ablage

```
youtube_code/llm_analysis/segments/
    __init__.py            (leer anlegen)
    segment_prompts.py     Prompttext + responseSchema + Prüfregeln
    submit_segments.py     JSONL bauen, hochladen, Job starten
    download_segments.py   Ergebnisse holen, prüfen, speichern
```

## Ablauf

1. **`submit_segments.py`** mit `DRY_RUN = True` starten.
   Erzeugt JSONL und Manifest, schickt nichts ab. Die Konsole zeigt die
   Feldreihenfolge des Schemas — dort müssen die Belegfelder vor den
   Score-Feldern stehen.
2. Erste Zeilen des JSONL ansehen.
3. `DRY_RUN = False`, erneut starten, bestätigen. Der Run landet in der
   Registry, JSONL und Manifest werden auf die `run_id` umbenannt.
4. **`download_segments.py`** starten, sobald der Job durch ist.
   Holt alle offenen Segment-Runs, prüft und speichert.

## Konfiguration

Beide Skripte haben oben einen `CONFIG`-Block, sonst keine Argumente.

### submit_segments.py

| Parameter | Bedeutung |
|---|---|
| `SEGMENT_FILE` | Ausgabe von `segment_transcripts.py` |
| `PROMPT_KEY` | Schlüssel aus `SEGMENT_PROMPTS` |
| `REPLICATES` | Durchläufe pro Segment. 1 = Produktiv, >1 = Reliabilität |
| `CONTEXT_WORDS` | Wörter aus dem Vorsegment, nur bei `use_context = True` |
| `TEMPERATURE` | Bei `REPLICATES > 1` zwingend > 0 |
| `MAX_SEGMENTS` | Nur für Pilotläufe, sonst `None` |
| `DRY_RUN` | Immer erst `True` |
| `*_COLUMN` | Spaltennamen in `SEGMENT_FILE` |

Fehlt eine `segment_id`-Spalte, wird sie als
`{video_id}__s{segment_index:04d}` gebaut. Existiert sie, wird sie
unverändert übernommen.

### download_segments.py

| Parameter | Bedeutung |
|---|---|
| `RUN_IDS` | Leer = alle offenen Segment-Runs |
| `RESULTS_DIR` | Zielordner der Ergebnis-CSVs |
| `SEGMENT_FILE_FOR_CHECK` | `None` = Datei aus `submit_segments.py` |
| `OVERWRITE` | Bestehende Ergebnisdatei überschreiben |

## Ausgabe

Eine CSV pro Run, Long-Format: **eine Zeile je (Segment × Replikat)**.

Identität: `run_id`, `custom_id`, `segment_id`, `video_id`,
`segment_index`, `replicate`, `n_chars`, `text_sha1`, `prompt_sha1`.

Dazu alle Modellfelder. Listenfelder (`rus_belege`, `instrumente`, …)
stehen als JSON-String in der Zelle:

```python
import json
df["rus_belege"] = df["rus_belege"].map(lambda v: json.loads(v) if v else [])
```

### Prüfspalten

| Spalte | Bedeutung |
|---|---|
| `ok_schema` | Antwort geparst, alle Felder da, Enums gültig |
| `ok_status` | `status` stimmt mit `erwaehnt` und `len(belege)` überein |
| `ok_score` | `score` genau dann gesetzt, wenn `status == "kodiert"`, und im Wertebereich |
| `beleg_quote` | Anteil der Belegstellen, die wörtlich im Segment stehen |
| `beleg_fehlend` | Die nicht gefundenen Belege, gekürzt |
| `parse_error` | Leer, `api_error: …`, `parse_error: …` oder `keine Antwort` |

Diese vier messen, ob das Modell **die Prozedur eingehalten** hat. Sie
sagen nichts darüber, ob das Urteil inhaltlich richtig ist — das kommt
aus dem Handcoding. Die Trennung ist für den Methodenteil nützlich:
Prozedurtreue und Validität sind getrennt berichtbar.

Requests ohne Antwort erscheinen als Zeile mit `parse_error =
"keine Antwort"` und werden nicht stillschweigend weggelassen. Für die
Analyse also auf `ok_schema & ok_status & ok_score` filtern und die
Ausfallquote separat berichten.

## Was gegenüber der bestehenden Pipeline anders ist

| | bestehend | hier |
|---|---|---|
| Identität | `custom_id = video_id` | `{segment_id}__r{n}` |
| `responseSchema` | nur im Grouped-Pfad | immer |
| Manifest | nur im Grouped-Pfad | immer |
| JSONL nach Upload | gelöscht | bleibt liegen |
| Modellfelder | überschreiben ID-Spalten | strikt getrennt |
| Fehlende Antworten | fallen raus | eigene Zeile |

**Replikate** laufen innerhalb *eines* Runs. Die Registry bleibt dadurch
unverändert; der Replikat-Index steht in `custom_id` und Manifest. Der
Uniqueness-Check der Registry greift damit weiterhin gegen echte
Doppel-Submits.

## Neuen Prompt hinzufügen

Zwei Bundle-Formen in `segment_prompts.py`:

**`kind = "flat_status"`** (POSITION_V1): Felder liegen flach im JSON.
`status` wird aus `erwaehnt`/`belege` abgeleitet, `score` genau dann
gesetzt, wenn `status == "kodiert"`.

```python
"NEUER_PROMPT": {
    "kind": "flat_status",
    "text": ...,
    "schema": ...,
    "target_variable": "...",
    "status_rules": [...],      # (erwaehnt, belege, status, score)
    "score_ranges": {...},
    "evidence_fields": [...],
    "enum_fields": {...},
},
```

**`kind = "nested_dimension"`** (POPULISMUS_P, IDEOLOGIE_I): Jede
Dimension ist ein eigenes JSON-Objekt `{"beleg": ..., "wert": ...}`.
Zwei Nullkonventionen:

- `null_convention = "zero"` — ohne Beleg ist `wert = 0` (nie `null`).
  Passt zu Skalen, die bei 0 „nicht vorhanden" bedeuten (Populismus).
- `null_convention = "null"` — ohne Beleg ist `wert = null`. Passt zu
  Skalen mit echter Mittelkategorie (Ideologie: 0 ist eine gültige
  Position, „nicht erkennbar" muss `null` sein).

```python
"NEUER_PROMPT": {
    "kind": "nested_dimension",
    "text": ...,                     # ohne Ausgabeformat-JSON-Beispiel
    "schema": ...,                   # jede Dimension: OBJECT mit
                                      # propertyOrdering ["beleg","wert"]
    "target_variable": "...",
    "segment_label": "SEGMENT",      # Ueberschrift vor dem Text
    "use_context": False,            # True = Kontextblock aus Vorsegment
    "dimensions": [...],             # Namen der Dimensionsfelder
    "wert_range": (low, high),
    "gate_field": None,              # optional: bool-Feld, das bei
                                      # gate_open_value=False ALLE
                                      # Dimensionen auf (null, null) zwingt
    "gate_open_value": True,
    "null_convention": "zero" | "null",
    "trailing_fields": {"feld": "bool"},  # muessen am ENDE von
                                           # propertyOrdering stehen
},
```

`get_bundle()` prüft bei beiden Arten, dass Belege vor Werten generiert
werden. Bei `nested_dimension` zusätzlich: `gate_field` steht an erster
Stelle, `trailing_fields` an letzter — versucht jemand versehentlich,
z. B. `ukraine_bezug` in die Mitte zu schieben, bricht das Skript beim
Laden ab statt beim Kodieren still den Priming-Schutz zu verlieren.

Der Prompttext darf keinen `{segment_text}`-Platzhalter enthalten. Der
Segmenttext wird angehängt, nicht per `.format()` eingesetzt — sonst
würden die geschweiften Klammern im JSON-Beispiel den Prompt zerlegen.

### Kontextblock (`use_context = True`)

Für Prompts, die den vorangehenden Textfluss brauchen (Populismus P):
`submit_segments.py` hängt automatisch die letzten `CONTEXT_WORDS`
Wörter des vorherigen Segments **desselben Videos** an, sortiert nach
`segment_index`. Das erste Segment eines Videos bekommt keinen Kontext.
Der Kontext wird im Prompt ausdrücklich als „nicht zu bewerten" markiert
und fließt nicht in die Belegprüfung ein.

## Verfügbare Prompts

| Prompt | kind | Eingabe | Ziel |
|---|---|---|---|
| `POSITION_V1` | flat_status | Segment | Position Russland / Westpolitik |
| `POPULISMUS_P` | nested_dimension | Segment + Kontext | vier Populismus-Subdimensionen |
| `IDEOLOGIE_I` | nested_dimension | ganzes Transkript | Links-Rechts-Positionierung |

### IDEOLOGIE_I: ganze Transkripte statt Segmente

Im Original für ganze, unsegmentierte Transkripte konzipiert (Baseline-
Videos vor Kriegsbeginn). Läuft über dieselbe Pipeline wie die
Segmentprompts — ein Video wird dabei als **ein Segment** behandelt.

```python
# submit_segments.py
SEGMENT_FILE    = <Baseline-Datei mit video_id + Transkriptspalte>
TEXT_COLUMN     = "transcript"      # oder wie die Spalte bei dir heisst
PROMPT_KEY      = "IDEOLOGIE_I"
DATASET_VERSION = "baseline_v1"
```

`SEGMENT_ID_COLUMN` und `SEGMENT_INDEX_COLUMN` können in der Baseline-
Datei fehlen: Ist keine `segment_index`-Spalte vorhanden, nimmt
`load_segments` automatisch `0` an und baut `segment_id` als
`{video_id}__s0000` — ein Segment pro Video, ohne dass die Zeilen
umbenannt werden müssen. `use_context = False` ist im Bundle bereits
gesetzt, es wird also kein Kontextblock angehängt.

**Die Auswahl der Baseline-Periode (vor Kriegsbeginn) liegt vollständig
bei dir** — `SEGMENT_FILE` muss bereits auf die richtigen Videos
gefiltert sein, die Pipeline prüft das nicht.

Zwei Dinge bleiben außerhalb der Pipeline und gehören ins
Analyse-Skript:

- **Aggregation Video → Kanal** über den Median der Baseline-Videos,
  mit Ausschluss der Videos, bei denen `positionen_gegen_kanal = true`
  ist (referierte statt vertretene Positionen — die Werte sind dort
  laut Prompt-Design unzuverlässig).
- **Ankertext-Validierung vor jeder Berichterstattung**: denselben
  Prompt auf Wahlprogramm-Auszüge mit bekannter Verortung anwenden und
  prüfen, ob die erwartete Rangfolge reproduziert wird (z. B. auf
  `wirtschaft`: Linke < Grüne ≈ SPD < CDU < FDP). Reproduziert das
  Modell diese Ordnung nicht, ist die Variable nicht berichtsfähig —
  unabhängig davon, wie plausibel einzelne Kanalwerte aussehen.

## Validierung gegen Handkodierung

Drei Schritte. Zusätzliche Dateien: `prepare_validation.py`,
`compare_coding.py`, `reliability.py`.

### 1. `prepare_validation.py`

Liest die Excel-Handkodierung, prüft sie **mit denselben Regeln wie
später die Modellausgabe** (Enums, Statusableitung, Score-Gating) und
schreibt zwei Dateien:

- `handkodierung_geprueft.csv` — normalisiert
- `segmente_validierung.csv` — die kodierten Segmente inkl. Text

Das Skript bricht ab, wenn die Handkodierung inkonsistent ist — etwa
ein `rus_score` bei `rus_status = "deskriptiv"`. Das ist beabsichtigt:
Sonst misst die Übereinstimmung Kodierfehler statt Instrumentengüte.

CONFIG: `HAND_FILE`, `HAND_ID_COLUMN`, `KEY_FILE` (nur bei
Blindkodierung mit Schlüsseldatei), `MULTI_SEPARATOR` für `emo_ziel`.

### 2. `submit_segments.py` / `download_segments.py`

```python
SEGMENT_FILE    = <Pfad aus Schritt 1>/segmente_validierung.csv
DATASET_VERSION = "validierung_v1"
```

`DATASET_VERSION` unbedingt ändern, sonst blockiert der
Uniqueness-Check der Registry den späteren Produktivlauf.

### 3. `compare_coding.py`

CONFIG: `MODEL_FILE` (`None` = neueste CSV in `MODEL_DIR`),
`REPLICATE_MODE` (`"first"` oder `"modal"`).

Ausgabe: `uebereinstimmung_report.txt`,
`uebereinstimmung_kennzahlen.csv`, `uebereinstimmung_zeilen.csv`.

### Was der Bericht trennt

**Stufe 1 — Status** (nominal, alle Segmente): Krippendorffs Alpha,
Cohens Kappa, Konfusionsmatrix. Zusätzlich dichotom „kodiert ja/nein",
weil das die neue und riskante Unterscheidung des Instruments ist.

**Stufe 2 — Scores** (ordinal, nur wo *beide* Seiten „kodiert"
gesagt haben): ordinales Alpha, quadratisch gewichtetes Kappa,
exakte Übereinstimmung, Anteil mit Abweichung ≤ 1, mittlerer Versatz
mit Konfidenzintervall, Konfusionsmatrix.

Das `n` fällt hier deutlich unter die Gesamtzahl. Bei 50 Segmenten
bleiben je nach Verteilung oft nur 15–25 Fälle pro Score. Unter 10
weist der Bericht die Kennzahlen aus, markiert sie aber als nicht
belastbar.

**Versatz vs. Rauschen.** Für ein Within-Design ist ein systematischer
Versatz (Modell durchgehend negativer als Hand) weit harmloser als
unsystematisches Rauschen — er hebt sich in `C−B` weitgehend auf,
solange er nicht mit dem Medientyp variiert. Das Konfidenzintervall
zeigt, ob überhaupt ein systematischer Anteil nachweisbar ist.

**Dimensionalitätscheck.** Am Ende steht `r(rus_score, west_score)`
getrennt für Hand und Modell. Liegt die Korrelation beim Modell
deutlich höher, zieht die autoregressive Generierung die zweite Skala
an die erste heran — dann sind getrennte API-Calls pro Dimension
erforderlich.

### Reliabilitätsmaße

`reliability.py` implementiert Krippendorffs Alpha (nominal, ordinal,
intervall) und Cohens Kappa (ungewichtet, linear, quadratisch) ohne
externe Pakete. Alpha ist gegen das kanonische Beispiel aus
Krippendorff (2011) geprüft: nominal 0.691, ordinal 0.807, intervall
0.811.

Alpha gibt `None` zurück, wenn es undefiniert ist — etwa wenn eine
Seite keine Varianz zeigt. Das ist nicht dasselbe wie 0 und darf im
Bericht nicht als schlechte Reliabilität gelesen werden.

## Bekannte Eigenheiten

- `rus_score` und `west_score` kommen als Float aus pandas, sobald eine
  Zeile `null` enthält. Für Auswertungen ggf. `.astype("Int64")`.
- Die Belegprüfung normalisiert auf Kleinschreibung und entfernt
  Satzzeichen. Erfindet das Modell Zeichensetzung, ist der Beleg
  trotzdem auffindbar; ändert es Wortlaut oder Wortstellung, nicht.
- `thinking_budget = 0` ist gesetzt. Für Extract-then-judge ist das
  vertretbar, weil die Zwischenschritte im Output stehen. Falls du das
  ändern willst, ist es ein eigener Run mit eigener `run_id`.

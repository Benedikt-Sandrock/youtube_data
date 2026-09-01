# Schritt 5 — Klassifikation von Transkripten

Eigenständige Pipeline für die LLM-Kodierung von Transkriptsegmenten
(`COMPLETE_PROCESS.md` Schritt 5). Läuft parallel zur Politics-Screening-
Pipeline; geteilt wird nur die Registry-Datei `data/store/llm_runs.sqlite`
(`youtube_code.store.llm_run_store`).

Benötigter Input ist eine Liste von Video-IDs. Alle Jobs werden automatisch
über `llm_run_store.add_run()`/`get_run()`/`update_run()` in `llm_runs.sqlite`
registriert.

## Ablauf (0–3)

```
youtube_code/step5_segment_analysis/
    segment_prompts_simple.py     0: Prompttext + responseSchema + Prüfregeln
    process_scraped_segments.py   1: Transkripte -> Segmente/Ausschnitte
    submit_segments.py            2: JSONL bauen, hochladen, Job starten
    download_segments_simple.py   3: Ergebnisse holen, prüfen, speichern
```

0. **`segment_prompts_simple.py`**: Prompts liegen im Dict `SEGMENT_PROMPTS`,
   Zugriff über `get_bundle(prompt_key)`. `get_bundle()` validiert beim Laden
   Feldreihenfolge, Gate-/Trailing-Feld-Position und (bei
   `nested_dimension`-Prompts) `beleg`-vor-`wert`-Ordnung — ein defektes
   Bundle bricht das Skript ab, statt beim Kodieren still falsche Ergebnisse
   zu produzieren.
1. **`process_scraped_segments.py`**: holt für die angeforderten Video-IDs
   die Transkripte aus `transcript_store.get_transcripts()`, zerlegt sie in
   Segmente (oder ein Ausschnitt pro Video, siehe `IDEOLOGIE_I`-Sonderfall
   unten) und schreibt `video_id, segment_index, text, n_woerter`.
2. **`submit_segments.py`** mit `DRY_RUN = True` starten. Erzeugt JSONL und
   Manifest, schickt nichts ab. Die Konsole zeigt die Feldreihenfolge des
   Schemas. Erste Zeilen des JSONL ansehen, dann `DRY_RUN = False`, erneut
   starten, bestätigen. Der Run landet in der Registry, JSONL und Manifest
   werden auf die `run_id` umbenannt.
3. **`download_segments_simple.py`** starten, sobald der Job durch ist. Holt
   alle offenen Segment-Runs (`status == "submitted"` und `notes` beginnt mit
   `"segments"`), prüft und speichert nach
   `outputs/llm_results/segment_analysis_active__{run_id}/{run_id}_{PROMPT_KEY}.csv`.

## `build_segments()`: programmatische Verkettung mit Schritt 4

`process_scraped_segments.py` bietet neben dem CLI-Pfad
(`build_segments_file()`, liest `VIDEO_ID_SOURCE` als CSV) die importierbare
Funktion

```python
def build_segments(video_ids: Iterable[str], *, out_file: Path = OUT_FILE) -> pd.DataFrame:
```

die dieselbe Kernlogik direkt auf einer Video-ID-Liste ausführt und das
geschriebene DataFrame zurückgibt — ohne Umweg über eine manuell
zwischengespeicherte CSV. Damit lässt sich Schritt 4 direkt verketten:

```python
from youtube_code.step4_transcript_download.select_targets import select_baseline_targets
from youtube_code.step5_segment_analysis.process_scraped_segments import build_segments

targets = select_baseline_targets()
segments = build_segments(targets["video_id"])
```

`build_segments_file()` (der `if __name__ == "__main__":`-Pfad) ruft intern
`build_segments(load_video_id_filter())` auf — der bisherige manuelle
Workflow über `VIDEO_ID_SOURCE` bleibt unverändert lauffähig. Alle
Konfigurationskonstanten (`TARGET_WORDS`, `MAX_SEGMENTS_PER_VIDEO`, `MODUS`,
`NUR_STATUS_OK`, …) bleiben Modul-Level-Defaults.

## Konfiguration

### submit_segments.py

| Parameter | Bedeutung |
|---|---|
| `SEGMENT_FILE` | Ausgabe von `process_scraped_segments.py` (bzw. `build_segments()`) |
| `PROMPT_KEY` | Schlüssel aus `SEGMENT_PROMPTS` |
| `REPLICATES` | Durchläufe pro Segment. 1 = Produktiv, >1 = Reliabilität (erfordert `TEMPERATURE > 0`) |
| `CONTEXT_WORDS` | Wörter aus dem Vorsegment, nur bei `use_context = True` |
| `MAX_SEGMENTS` | Nur für Pilotläufe, sonst `None` |
| `DRY_RUN` | Immer erst `True` |
| `ALLOW_EXISTING_RUN` | Schutz gegen versehentliche Doppel-Submits |
| `*_COLUMN` | Spaltennamen in `SEGMENT_FILE` |

Fehlt eine `segment_id`-Spalte, wird sie aus `VIDEO_ID_COLUMN` +
`SEGMENT_INDEX_COLUMN` gebaut (`{video_id}__s{segment_index:04d}`). Fehlt
auch `SEGMENT_INDEX_COLUMN`, wird `0` angenommen — ein Segment pro Video.

### download_segments_simple.py

| Parameter | Bedeutung |
|---|---|
| `RUN_IDS` | Leer = alle offenen Segment-Runs (`status="submitted"`, `notes` beginnt mit `"segments"`) |
| `RESULTS_ROOT` | `outputs/llm_results/` |
| `SEGMENT_FILE_FOR_CHECK` | `None` = Datei aus `submit_segments.SEGMENT_FILE` |
| `OVERWRITE` | Bestehende Ergebnisdatei überschreiben |

## Ausgabe

Eine CSV pro Run, Long-Format: **eine Zeile je (Segment × Replikat)**.

Identität: `run_id`, `custom_id`, `segment_id`, `video_id`,
`segment_index`, `replicate`. Dazu alle Modellfelder (Array-/Objektfelder
stehen als JSON-String in der Zelle) sowie vier Prüfspalten:

| Spalte | Bedeutung |
|---|---|
| `ok_schema` | Antwort geparst, alle Felder da, Enums gültig |
| `ok_status` | `status`/Gate-Konsistenz eingehalten (z. B. `score` genau dann gesetzt, wenn `status == "bewertend"`) |
| `ok_score` | `score` im erlaubten Wertebereich (oder korrekt `null`, wenn Gate/Status das verlangt) |
| `beleg_quote` | Anteil der Belegstellen aus `evidence_fields`/`beleg`, die wörtlich im Segment stehen (`None`, wenn keine Belegfelder definiert sind) |

Diese Spalten messen, ob das Modell **die Prozedur eingehalten** hat, nicht,
ob das Urteil inhaltlich richtig ist. Requests ohne Antwort erscheinen als
Zeile mit `parse_error = "keine Antwort"` und werden nicht stillschweigend
weggelassen. Für die Analyse also auf `ok_schema & ok_status & ok_score`
filtern und die Ausfallquote separat berichten.

## Neuen Prompt hinzufügen (`segment_prompts_simple.py`)

Zwei Bundle-Formen, unterschieden über `"kind"`:

**`kind = "flat_status"`** (aktuell alle drei bestehenden Prompts:
`POSITION_V1`, `POPULISMUS_P`, `IDEOLOGIE_I`): Felder liegen flach im JSON.
`conditional_score_rules` beschreibt Tripel `(status_field, expected_value,
score_field)` — der Score-Wert muss genau dann gesetzt sein, wenn
`status_field == expected_value`. `evidence_fields` listet Listenfelder mit
Belegzitaten (aktuell bei allen drei Prompts leer — keiner verlangt aktuell
separate Belegfelder). Optional `gate_field`/`gate_open_value`: ist das Gate
geschlossen, müssen alle Score-/Belegfelder `null`/leer sein.

```python
"NEUER_PROMPT": {
    "kind": "flat_status",
    "text": ...,
    "schema": ...,
    "target_variable": "...",
    "conditional_score_rules": [...],   # (status_field, expected_value, score_field)
    "score_ranges": {...},
    "evidence_fields": [...],
    "enum_fields": {...},
    "gate_field": None,          # optional
    "gate_open_value": True,
    "trailing_fields": {"feld": "bool"},  # muessen am ENDE von propertyOrdering stehen
},
```

**`kind = "nested_dimension"`** (im Code unterstützt, aktuell von keinem
Prompt genutzt): Jede Dimension ist ein eigenes JSON-Objekt `{"beleg": ...,
"wert": ...}`. Zwei Nullkonventionen: `null_convention = "zero"` (ohne Beleg
ist `wert = 0`, passt zu Skalen, die bei 0 „nicht vorhanden" bedeuten) oder
`"null"` (ohne Beleg ist `wert = null`, passt zu Skalen mit echter
Mittelkategorie).

```python
"NEUER_PROMPT": {
    "kind": "nested_dimension",
    "text": ...,
    "schema": ...,                   # jede Dimension: OBJECT mit
                                      # propertyOrdering ["beleg", "wert"]
    "target_variable": "...",
    "dimensions": [...],
    "wert_range": (low, high),
    "gate_field": None,
    "gate_open_value": True,
    "null_convention": "zero" | "null",
    "trailing_fields": {"feld": "bool"},
},
```

`get_bundle()` prüft bei beiden Arten, dass Belege/Scores in der richtigen
Reihenfolge stehen; bei `nested_dimension` zusätzlich, dass `gate_field` an
erster und `trailing_fields` an letzter Stelle in `propertyOrdering` stehen
(Priming-Schutz). Der Prompttext darf keinen `{segment_text}`-Platzhalter
enthalten — der Segmenttext wird angehängt, nicht per `.format()` eingesetzt.

### Kontextblock (`use_context = True`)

Für Prompts, die den vorangehenden Textfluss brauchen (`POPULISMUS_P`):
`submit_segments.py` hängt automatisch die letzten `CONTEXT_WORDS` Wörter
des vorherigen Segments **desselben Videos** an, sortiert nach
`segment_index`. Das erste Segment eines Videos bekommt keinen Kontext.

## Verfügbare Prompts

| Prompt | kind | Eingabe | Ziel |
|---|---|---|---|
| `POSITION_V1` | flat_status | Segment | Position Russland / westliche Ukraine-Politik |
| `POPULISMUS_P` | flat_status + Kontext | Segment | vier Populismus-Subdimensionen + Ukraine-Bezug |
| `IDEOLOGIE_I` | flat_status | ganzes Transkript | Wirtschaft-/Gesellschaft-Positionierung |

### IDEOLOGIE_I: ganze Transkripte statt Segmente

Für `IDEOLOGIE_I` wird `process_scraped_segments.py`s `MODUS =
"ganze_transkripte"` verwendet — ein Video wird dabei als **ein Segment**
behandelt (Transkripte oberhalb `EXCERPT_WORD_BUDGET` Wörtern werden nicht
am Anfang gekappt, sondern in `EXCERPT_N_CHUNKS` gleichmäßig verteilte,
auf Satzenden gerundete Ausschnitte aufgeteilt). Läuft über dieselbe
Submit-/Download-Pipeline wie die Segmentprompts.

## Was gegenüber der Politics-Screening-Pipeline anders ist

| | Politics-Screening | hier |
|---|---|---|
| Identität | `custom_id = video_id` | `{segment_id}__r{n}` |
| `responseSchema` | nur im Grouped-Pfad | immer |
| Manifest | nur im Grouped-Pfad | immer |
| Fehlende Antworten | fallen raus | eigene Zeile (`parse_error = "keine Antwort"`) |

**Replikate** laufen innerhalb *eines* Runs. Die Registry bleibt dadurch
unverändert; der Replikat-Index steht in `custom_id` und Manifest. Der
Uniqueness-Check der Registry greift damit weiterhin gegen echte
Doppel-Submits.

## Validierung gegen Handkodierung

**Nicht implementiert / offener Punkt.** Ein früherer Stand dieser README
beschrieb ein dreistufiges Validierungs-Tooling (`prepare_validation.py`,
`compare_coding.py`, `reliability.py` samt Krippendorffs Alpha und Cohens
Kappa) — diese Dateien existieren im aktuellen Repo nicht. Bevor Ergebnisse
dieser Pipeline berichtet werden, braucht es einen Abgleich gegen
Handkodierung; wie das umgesetzt wird, ist noch offen.

## Unangetastete Diagnose-/Brücken-/Auswertungsskripte

Im Ordner liegen daneben (Einordnung nicht Teil dieser Schritt-5-Aufräumung):

- `prepare_channel_scores.py` — Brücke Segment- zu Kanal-Aggregation,
  Vorstufe zu Schritt 6. Erwartet aktuell manuell umbenannte Eingabedateien
  (`run_0011_POSITION_V1.csv` etc.), nicht direkt den automatischen Output
  von `download_segments_simple.py`.
- `check_baseline_coverage.py`, `finde_download_kandidaten.py`,
  `video_sample_uebersicht.py` — Diagnose-/Ad-hoc-Skripte, die laut
  `CLAUDE.md` eigentlich nach `scripts/adhoc/` gehörten.
- `deskriptiv_aggregation.py`, `deskriptiv_plots.py`, `geglaettete_kurve.py`,
  `fe_signifikanz_test.py` — Schritt-6-Auswertungsskripte
  (`COMPLETE_PROCESS.md`), landen mittelfristig in einem eigenen Ordner.

## Bekannte Eigenheiten

- Score-Spalten kommen als Float aus pandas, sobald eine Zeile `null`
  enthält. Für Auswertungen ggf. `.astype("Int64")`.
- Die Belegprüfung (`beleg_quote`) normalisiert auf Kleinschreibung und
  entfernt Satzzeichen. Erfindet das Modell Zeichensetzung, ist der Beleg
  trotzdem auffindbar; ändert es Wortlaut oder Wortstellung, nicht.
- `THINKING_BUDGET = 0` ist gesetzt. Für Extract-then-judge ist das
  vertretbar, weil die Zwischenschritte im Output stehen.

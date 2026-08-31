# Neue Kanäle zum longitudinalen Screening hinzufügen

Diese Anleitung beschreibt den Prozess, um zusätzliche Kanäle in das bestehende
longitudinale Politik-Screening (`data/raw/screening_state.sqlite`, über
`src/youtube_code/store/screening_state_store.py` — seit Phase 4d der
Restrukturierung die alleinige Quelle der Wahrheit, nicht mehr die frühere
`data/samples/russia/longitudinal_screening_state.csv`) einzuspeisen — egal ob
es sich um Kanäle handelt, die komplett neu sind, oder um Kanäle, die schon
Zeilen im State haben (z.B. nur für Kriegsperioden), denen aber noch das
Vorkriegs-Baseline-Fenster fehlt. Der Ablauf ist in beiden Fällen identisch;
das Skript in Schritt 3 erkennt automatisch, welcher Fall vorliegt.

**Grundprinzip:** Der State wird durch Anhängen (append) erweitert, nie durch
Neuaufbau. `prepare_longitudinal_screening.py` ("einmal"-Skript laut
`README_PIPELINE.md`) baute den State ursprünglich komplett neu auf einer
festen Rohdatendatei (`videos_wo_shorts_description.jsonl`) auf und ist für
nachträgliche Ergänzungen NICHT gedacht — dafür würden bestehende Labels/
`screening_round`-Zuweisungen riskiert; seit der SQLite-Migration ist das
Skript ohnehin nicht mehr sinnvoll ausführbar (schreibt gegen die alte CSV,
nicht gegen die DB). Für neue Kanäle immer den Append-Weg unten nehmen.

## Voraussetzungen

- `.venv/Scripts/python.exe` (nicht `python3` — ist auf diesem Windows-Rechner nicht
  im PATH).
- Vor jedem Aufruf eines Skripts, das `youtube_code`-Module importiert:
  `PYTHONPATH=src` voranstellen (sonst `ModuleNotFoundError`).
- Vor jedem Aufruf: `PYTHONIOENCODING=utf-8` setzen (sonst crasht das Skript beim
  `print()` von Emoji-/Sonderzeichen-Kanalnamen in der cp1252-Windows-Konsole — der
  Crash passiert erst beim Drucken, bereits geschriebene Dateien bleiben unberührt,
  aber sicherheitshalber trotzdem immer mitgeben).
- Lange Skripte (API-Sammlung, State-Verarbeitung) laufen oft länger als 2 Minuten —
  im Hintergrund laufen lassen und auf Abschluss warten statt mit `sleep` zu pollen.

## Schritt 1 — Kanal-IDs sammeln

Eine CSV mit einer Spalte `channel_id` (eine Zeile pro Zielkanal) anlegen, z.B.
`outputs/segment_analysis/meine_neuen_kanaele.csv`. Die YouTube-Channel-ID (beginnt mit
`UC...`), nicht der Handle/Anzeigename.

## Schritt 2 — Video-IDs sammeln (`src/youtube_code/collection/channel_all_videos.py`)

Am Kopf des Skripts konfigurieren:

- `MODE = "TARGETED_SEARCH"` für normale Kanäle (grob bis ~7.000–15.000 Videos
  insgesamt). Kanalliste in `TARGETED_CHANNEL_INPUT` auf die CSV aus Schritt 1 zeigen
  lassen. Nutzt `playlistItems.list` über die komplette Uploads-Playlist.
- `MODE = "TARGETED_SEARCH_YTDLP"` für sehr große Kanäle (>~15.000–20.000 Videos
  insgesamt) — `playlistItems.list` bricht bei ca. 20.000 Items ab
  (YouTube-API-Limitation), `search().list` deckt bei solchen Kanälen oft nur einen
  winzigen, nicht-repräsentativen Ausschnitt ab. Kanalliste in
  `TARGETED_SEARCH_YTDLP_CHANNEL_INPUT` eintragen. Nutzt yt-dlp zur ID-Enumeration,
  danach `videos().list` in 50er-Batches für die echten `publishedAt`-Werte. Kann pro
  Kanal mehrere Minuten dauern.
- `TARGETED_PUBLISHED_AFTER` / `TARGETED_PUBLISHED_BEFORE`: das gewünschte
  Zeitfenster. **Wichtig:** Videos mit `period < INTERVAL_START` (aktuell `-12`, siehe
  `screening_config.py`) werden in Schritt 5 ohnehin verworfen — `period` ist der
  Monatsabstand zum Referenzdatum `2022-02-24` (Kriegsbeginn). Es lohnt sich also
  i.d.R. nicht, deutlich vor `2021-02-24` zu sammeln. Nach oben hin gibt es keine
  Kappung — bis zum aktuellen Datum sammeln, wenn der volle Zeitraum gewünscht ist.

Schreibt neue Video-IDs (`video_id`, `channel_id`, `published_at`, `title`) nach
`data/raw/sample_50k_channels_russia_ukraine.json` und in die zentrale Registry
(`data/raw/video_registry.sqlite`).

**Vorsicht bei den Eingabedateien:** `TARGETED_CHANNEL_INPUT` /
`TARGETED_SEARCH_YTDLP_CHANNEL_INPUT` zeigen oft noch auf Dateien von einem früheren
Lauf. Inhalt vorher prüfen und bei Bedarf überschreiben, nicht blind anhängen.

## Schritt 3 — Beschreibungen holen (`src/youtube_code/collection/metadata_collection.py`)

Am Kopf konfigurieren:

- `channel_metadata = False` (für diesen Zweck nicht nötig).
- `video_metadata = True`, `DETAILED = True`.
- `VIDEOS_INPUT_PATH` auf die in Schritt 2 gesammelten Video-IDs zeigen lassen (akzeptiert
  eine JSON-Liste von Dicts mit `video_id` oder eine CSV mit `video_id`-Spalte).

Schreibt (hängt an) `data/raw/video_metadata_detailed_total.jsonl` — inzwischen >2GB,
wächst mit jedem Lauf weiter. Diese Datei ist historisch **nicht** für alle Kanäle
vollständig; nach dem Lauf verifizieren, dass für jeden Zielkanal tatsächlich Zeilen
mit plausiblen Beschreibungen und `published_at` im gewünschten Fenster vorhanden sind,
bevor man zu Schritt 4 übergeht.

**Bekannter Stolperstein (in dieser Session aufgetreten):** `append_channels_to_state.py`
(Schritt 4) lädt diese JSONL komplett per `pandas.read_json(..., lines=True)` — bei der
vollen ~2GB-Datei führt das zu einem `MemoryError`, selbst wenn nur wenige tausend
Zeilen tatsächlich gebraucht werden. Abhilfe: die Datei vorher zeilenweise (streaming,
`json.loads` pro Zeile, kein Pandas) auf die Ziel-`channel_id`s aus Schritt 1 filtern
und nur diese kleinere JSONL an `--videos` übergeben. Beispiel:

```python
import json, csv

target_ids = set()
with open("outputs/segment_analysis/meine_neuen_kanaele.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        target_ids.add(row["channel_id"])

with open("data/raw/video_metadata_detailed_total.jsonl", encoding="utf-8") as fin, \
     open("data/raw/video_metadata_detailed_gefiltert.jsonl", "w", encoding="utf-8") as fout:
    for line in fin:
        obj = json.loads(line)
        if obj.get("channel_id") in target_ids:
            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
```

## Schritt 4 — State erweitern (`src/youtube_code/politics_screening/longitudinal/append_channels_to_state.py`)

**Vorher immer ein Backup anlegen** — die State-DB hat keine Git-Historie:

```bash
cp data/raw/screening_state.sqlite \
   data/raw/screening_state.sqlite.bak_<kurze_beschreibung>
```

Dann:

```bash
PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
  src/youtube_code/politics_screening/longitudinal/append_channels_to_state.py \
  --channels outputs/segment_analysis/meine_neuen_kanaele.csv \
  --videos data/raw/video_metadata_detailed_gefiltert.jsonl \
  --dry-run
```

Erst die Ausgabe prüfen (Anzahl neuer Kandidatenzeilen, Verteilung über
`interval_index`, wie viele Kanäle als "komplett neu" vs. "nur Baseline ergänzt"
erkannt wurden). Passt das Bild, denselben Befehl **ohne** `--dry-run` erneut ausführen,
um wirklich zu schreiben.

Das Skript repliziert exakt die Interval-/Rank-Logik von `prepare_longitudinal_screening.py`,
aber additiv: Kanäle, die schon im State stehen, bekommen nur die fehlenden
`period < 0`-Zeilen (Baseline), komplett neue Kanäle den vollen Zeitraum ab
`period >= INTERVAL_START`. Bereits im State vorhandene `video_id`s werden automatisch
übersprungen (keine Duplikate).

## Schritt 5 — Screening-Runde erzeugen (`src/youtube_code/politics_screening/longitudinal/create_longitudinal_screening.py`)

Modul-Konstante `DRY_RUN` am Kopf der Datei zuerst auf `True` setzen und laufen lassen:

```bash
PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
  src/youtube_code/politics_screening/longitudinal/create_longitudinal_screening.py
```

Das Skript plant adaptiv **über den gesamten State** (nicht nur die neuen Kanäle) die
nächste Runde: pro Kanal/Interval wird geprüft, ob `TARGET_WITH_BUFFER_PER_INTERVAL`
(aktuell 12) schon erreicht ist, ob Ergebnisse noch ausstehen, oder ob der
Kandidatenpool erschöpft ist — nur unzureichende Zellen bekommen neue Kandidaten. Die
gedruckte Planübersicht (Anzahl Kandidaten, Requests, Verteilung, Beispielzeilen)
prüfen. Passt sie, `DRY_RUN = False` setzen und erneut laufen lassen — schreibt dann:

- `data/samples/russia/batches_longitudinal/screening_rounds/screening_round_NNN_title_candidates.csv`
- `data/samples/russia/batches_longitudinal/screening_round_summaries/screening_round_NNN_selection_summary.csv`
- aktualisiert `screening_round` in der State-Datei für die ausgewählten Zeilen.

## Schritt 6 — Titel-Klassifikation abschicken (`src/youtube_code/llm_analysis/run_longitudinal_screening_batch.py`)

Am Kopf konfigurieren:

- `ROUND_NUMBER` = die in Schritt 5 erzeugte Rundennummer.
- `MODE = "title"`.
- `DRY_RUN = True` zuerst.

```bash
PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
  src/youtube_code/llm_analysis/run_longitudinal_screening_batch.py
```

Das Skript validiert vorab streng (Kandidaten-IDs müssen exakt mit den noch
unbearbeiteten State-Zeilen dieser Runde übereinstimmen, keine leeren Titel, keine
Dubletten) und zeigt eine Preflight-Übersicht (Video-/Request-Anzahl, Verteilung,
Beispielzeilen). Am Ende fragt es interaktiv `Create dry-run files? [Y/n]` — das
schreibt nur lokale Vorschau-Dateien (JSONL, Manifest), noch **keine** echte
Einreichung. Erst wenn diese Vorschau plausibel aussieht, `DRY_RUN = False` setzen und
das Skript erneut laufen lassen — das reicht den Batch-Job wirklich bei Vertex AI ein
(Gemini 2.5 Flash, Prompt 32) und trägt ihn in die Registry
(`data/raw/llm_runs.sqlite`, Quelle `screening_active`, siehe
`src/youtube_code/store/llm_run_store.py`) ein.

`ALLOW_EXISTING_RUN = True` nur für einen bewussten Retry setzen — Standard `False`
verhindert versehentliche Doppel-Einreichungen für dieselbe Runde/Stufe.

## Schritt 7 — Ergebnisse abholen (`src/youtube_code/llm_analysis/download_results.py`)

Prüft den Job-Status in der Registry und lädt fertige Ergebnisse herunter (als CSV nach
`outputs/llm_results/screening_active__<run_id>/`).

## Schritt 8 — Ergebnisse in den State zurückführen (`src/youtube_code/politics_screening/update_screening_state.py`)

Am Kopf konfigurieren: `MODE = "title"`, `ROUND_NUMBER` und `RUN_ID` (aus der Registry)
setzen. Erst `DRY_RUN = True` laufen lassen und die Merge-Vorschau prüfen, dann
`DRY_RUN = False` für den echten Merge. Direkte Labels (0/1) werden zu
`politics_final` kopiert; `-1`-Fälle (titelseitig unklar) werden automatisch in eine
Description-Kandidaten-CSV geschrieben
(`data/samples/russia/batches_longitudinal/description_rounds/screening_round_NNN_description_candidates.csv`)
für die nächste Stufe.

## Schritt 9 — Beschreibungs-Validierung für die `-1`-Fälle

Für Videos, die anhand des Titels allein nicht eindeutig waren, denselben
Runden-Zyklus wie Schritt 6–8 noch einmal durchlaufen, diesmal mit `MODE = "description"`
(sowohl in `run_longitudinal_screening_batch.py` als auch in `update_screening_state.py`,
gleiche `ROUND_NUMBER`). Nutzt Prompt 33 und liest Titel+Beschreibung. Nach diesem Merge
bleibt ein zweites `-1` bewusst als `politics_final = -1` stehen (spätere
manuelle/Transkript-Prüfung).

## Schritt 10 — Wiederholen

`create_longitudinal_screening.py` (Schritt 5) erneut laufen lassen — prüft
automatisch pro Kanal/Interval, ob das Ziel erreicht ist, und plant nur für noch
unzureichende Zellen die nächste Runde. Wiederholen, bis für die neuen Kanäle entweder
das Ziel erreicht ist oder ihr Kandidatenpool erschöpft ist (Status
`candidate_pool_exhausted` in der Runden-Zusammenfassung).

## Kurzreferenz (Skript → Zweck)

| Skript | Zweck | Ausführung |
| --- | --- | --- |
| `collection/channel_all_videos.py` | Video-IDs für Zeitfenster sammeln | pro neue Kanalgruppe |
| `collection/metadata_collection.py` | Beschreibungen holen | pro neue Kanalgruppe |
| `politics_screening/longitudinal/append_channels_to_state.py` | Neue Kandidatenzeilen in den State einspeisen | pro neue Kanalgruppe |
| `politics_screening/longitudinal/create_longitudinal_screening.py` | Nächste Screening-Runde planen (State-weit) | wiederholt |
| `llm_analysis/run_longitudinal_screening_batch.py` | Batch-Job einreichen (Prompt 32 title / Prompt 33 description) | pro Runde × 2 Stufen |
| `llm_analysis/download_results.py` | Ergebnisse abholen | pro Runde × 2 Stufen |
| `politics_screening/update_screening_state.py` | Ergebnisse in State mergen | pro Runde × 2 Stufen |

## Wichtige Konstanten (`src/youtube_code/politics_screening/screening_config.py`)

- `INTERVAL_START = -12`, `INTERVAL_SIZE = 3`: Perioden werden ab 12 Monaten vor
  Kriegsbeginn in 3-Monats-Intervallen gruppiert.
- `TARGET_POLITICAL_PER_INTERVAL = 10`, `TARGET_WITH_BUFFER_PER_INTERVAL = 12`: Ziel
  pro Kanal/Interval — 10 politische Videos, 12 als Puffer für z.B. fehlende
  Transkripte.
- Zentrale State-Ablage seit Phase 4d: `data/raw/screening_state.sqlite`
  (`src/youtube_code/store/screening_state_store.py`), nicht git-getrackt. Die
  frühere `STATE_FILE`-Konstante (`screening_config.py`,
  `longitudinal_screening_state.csv`) ist nur noch historisch, wird von den
  Schreiber-Skripten nicht mehr verwendet. **Vor jedem schreibenden Schritt
  (4) sichern.**

## Optional: Master-Kanalliste

Für die kanalbezogene Klassifikation (Tier, Medientyp usw., unabhängig vom
Screening-State) pflegt der Nutzer zusätzlich `data/external/media_type_russia_merged.xlsx`
manuell (Spalte `notiz` markiert manuelle Ergänzungen). Das ist für den technischen
Screening-Ablauf oben nicht erforderlich, aber für die spätere Auswertung/Konsistenz
empfehlenswert, neue Kanäle dort ebenfalls einzutragen.

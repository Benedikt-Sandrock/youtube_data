# Handoff: Baseline-Datenerhebung für 27 Kanäle

Kontext-Briefing für eine neue Claude-Code-Session in diesem Repo
(`C:\Users\bened\PycharmProjects\youtube_data`). Ziel dieser Session: **eigenständig**
Videos + Metadaten für 27 Kanäle im Vorkriegsfenster sammeln, sie ins Screening
einspeisen, die Titel-Klassifikation starten und bis zum Abschluss überwachen.

## Auftrag

Für 27 Kanäle (Liste unten) fehlen im longitudinalen Screening-State komplett die
Kandidatenzeilen für das Baseline-Fenster **2021-02-24 bis 2022-02-23** (12 Monate vor
Kriegsbeginn). Die Kanäle selbst sind bereits als politisch relevant identifiziert
(hohe Kriegsvideo-Zahlen im Rohpool). Aufgabe: Rohdaten für dieses Fenster besorgen,
in den State einspeisen, Titel-Screening-Runde(n) fahren, bis pro Kanal/Intervall
genug politische Videos gefunden sind (oder der Kandidatenpool erschöpft ist).

Arbeite das **selbstständig** durch (Sammlung → Metadaten → State-Erweiterung →
Screening-Runde(n) → Klassifikation → Monitoring), ohne bei jedem Einzelschritt
nachzufragen. Melde dich bei Meilensteinen (State erweitert, Runde abgeschlossen,
Baseline-Ziel erreicht) und bei Blockern (API-Quota, Fehlern) - nicht bei jedem
einzelnen Kanal/Video-Fortschritt.

## Zielkanäle (bereits als CSV gespeichert)

`outputs/segment_analysis/kanaele_baseline_collection_todo.csv` (channel_id,
channel_title, tier, n_baseline_zeilen=0, video_count). 27 Zeilen, in zwei Gruppen
nach Sammelmethode:

**Sehr groß (>60.000 Videos gesamt) → `TARGETED_SEARCH_YTDLP`-Modus nötig:**
euronews (deutsch), WELT Nachrichtensender, OE24.TV — playlistItems.list bricht bei
~20.000 Items ab, hier hilft nur die yt-dlp-Enumeration (siehe
`channel_all_videos.py`-Docstring, MODE="TARGETED_SEARCH_YTDLP").

**Normal (<7.000 Videos gesamt) → `TARGETED_SEARCH`-Modus reicht:**
die übrigen 24 Kanäle (Finanzdenker, Kontrafunk, BOSS DELUXE, DACH Medien, Enrico
Rudolph, Entertainment-Shorts, Dirk Muchow, DER GLÜCKSRITTER, ANDI in Deutschland,
Politik mit Kopf, Iris Aschenbrenner, Flavio von Witzleben, Krissy Rieger, Cassandra
Sommer, Deutschlands Wahnsinn, Apollo News, RTL Doku, Demokratisch Denken,
warum.kritisch, MENTALE FITNESS, mym by Simo, InfoBox, Alexander Raue Klartext,
Wieder Zensiert - Alles Ausser Mainstream Boschimo). Exakte Video-Counts in der CSV.

## Schritt-für-Schritt-Plan

### 1. Video-IDs sammeln (`src/youtube_code/collection/channel_all_videos.py`)

- Zeitfenster ist bereits korrekt vorkonfiguriert:
  `TARGETED_PUBLISHED_AFTER = "2021-02-24T00:00:00Z"`,
  `TARGETED_PUBLISHED_BEFORE = "2022-02-23T23:59:59Z"`.
- Für die 24 normalen Kanäle: `MODE = "TARGETED_SEARCH"`, Kanalliste in
  `TARGETED_CHANNEL_INPUT` (`outputs/segment_analysis/baseline_still_missing_channels.csv`)
  **überschreiben** mit den 24 Ziel-IDs (Datei existiert bereits von einem früheren,
  anderen Lauf - Inhalt vorher prüfen/ersetzen, nicht blind anhängen).
- Für die 3 riesigen Kanäle: `MODE = "TARGETED_SEARCH_YTDLP"`, Kanalliste in
  `TARGETED_SEARCH_YTDLP_CHANNEL_INPUT`
  (`outputs/segment_analysis/baseline_unreliable_large_channels.csv`, ebenfalls
  vorher prüfen/ersetzen - dort stehen aktuell noch andere Kanäle von einem früheren
  Lauf, u.a. Habibiflo und tagesschau). yt-dlp-Enumeration für 60.000-135.000 Videos
  pro Kanal kann mehrere Minuten dauern.
- Schreibt nach `data/raw/sample_50k_channels_russia_ukraine.json` und in die zentrale
  Registry (`data/raw/video_registry.sqlite`).

### 2. Beschreibungen holen (`src/youtube_code/collection/metadata_collection.py`)

- `video_metadata = True`, `DETAILED = True` setzen.
- `VIDEOS_INPUT_PATH` auf die gerade gesammelten neuen Video-IDs zeigen lassen (Skript
  akzeptiert JSON-Liste von Dicts mit `video_id` oder CSV mit `video_id`-Spalte -
  ggf. aus dem Ergebnis von Schritt 1 filtern).
- Schreibt nach `data/raw/video_metadata_detailed_total.jsonl` (2GB, wird
  fortgeschrieben - prüfen, ob das Skript anhängt oder eine gezielte Teilmenge
  zurückgibt; ggf. wie in dieser Session selbst filtern/extrahieren).
- **WICHTIG (aus dieser Session gelernt):** Diese Datei ist historisch NICHT
  vollständig für alle Kanäle - für genau diese 27 Kanäle fehlten die
  Baseline-Beschreibungen komplett, weshalb dieser Schritt überhaupt nötig ist. Nach
  dem Lauf verifizieren, dass für jeden Zielkanal tatsächlich Zeilen mit
  `published_at` im Fenster 2021-02-24 bis 2022-02-23 vorhanden sind, bevor man zu
  Schritt 3 übergeht.

### 3. State erweitern (neues, wiederverwendbares Skript)

`src/youtube_code/politics_screening/longitudinal/append_channels_to_state.py`
(diese Session geschrieben, im Repo committed) - repliziert exakt die
Interval-/Rank-Logik von `prepare_longitudinal_screening.py`, aber als Append statt
Neuaufbau.

```
# VORHER IMMER Backup anlegen (State hat keine Git-Historie, ~1.2GB):
cp data/samples/russia/longitudinal_screening_state.csv \
   data/samples/russia/longitudinal_screening_state.csv.bak_<beschreibung>

PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
  src/youtube_code/politics_screening/longitudinal/append_channels_to_state.py \
  --channels outputs/segment_analysis/kanaele_baseline_collection_todo.csv \
  --videos <JSONL aus Schritt 2> \
  --dry-run   # erst pruefen, dann ohne --dry-run wirklich schreiben
```

Das Skript erkennt automatisch, welche Kanäle schon Zeilen im State haben (nur
Baseline period<0 wird ergänzt) vs. komplett neue Kanäle (voller Zeitraum).

### 4. Screening-Runde erzeugen und Titel-Klassifikation starten

Pipeline und Reihenfolge stehen in
`src/youtube_code/politics_screening/README_PIPELINE.md` und
`src/youtube_code/llm_analysis/How to -  Title Classification.txt` - **beide vor dem
ersten Lauf lesen**, dort stehen die aktuellen Konventionen (Registry-Format,
DRY_RUN-Empfehlung etc.) genauer als hier zusammengefasst werden kann. Kurzfassung:

1. `create_longitudinal_screening.py` - liest State, plant nächste Runde (adaptiv,
   pro Kanal/Intervall bis `TARGET_WITH_BUFFER_PER_INTERVAL=12`), schreibt
   Kandidaten-CSV + markiert `screening_round` im State. **Erst mit `DRY_RUN=True`
   den Plan prüfen**, dann `DRY_RUN=False` für den echten Lauf.
2. `llm_analysis/run_longitudinal_screening_batch.py` - `ROUND_NUMBER` auf die neue
   Runde setzen (State war zuletzt bei Runde 8 in `MODE="description"` - für die
   neuen Kanäle ist es eine neue Runde in `MODE="title"`), `DRY_RUN=True` zuerst
   prüfen, dann submitten. Läuft async auf Vertex AI (Gemini 2.5 Flash) über die
   Registry (`llm_analysis/registry/runs_registry.csv`).
3. Ergebnisse abholen: `llm_analysis/download_results.py` (Job-Status prüfen/Resultate
   laden).
4. `politics_screening/update_screening_state.py` - merged die Titel-Labels zurück in
   den State (`politics_final` bei direkten 0/1-Labels, `-1` geht in die
   Description-Validierungsrunde).
5. Für `-1`-Fälle: `create_description_validation_sample.py` +
   `run_longitudinal_screening_batch.py` mit `MODE="description"` (Prompt 33) analog
   wiederholen.
6. Nach jeder Runde `create_longitudinal_screening.py` erneut laufen lassen - prüft
   automatisch pro Kanal/Intervall, ob `TARGET_WITH_BUFFER_PER_INTERVAL` erreicht ist,
   und plant die nächste Runde nur für noch unzureichende Zellen.

Wiederholen, bis für die 27 Kanäle im Baseline-Fenster entweder das Ziel erreicht ist
oder der Kandidatenpool erschöpft ist (Status `candidate_pool_exhausted` in der
Runden-Zusammenfassung).

## Wichtige technische Hinweise (diese Session gelernt)

- `python3` ist auf diesem Windows-Rechner nicht im PATH - immer
  `.venv/Scripts/python.exe` verwenden.
- Für Skripte, die `youtube_code`-Module importieren (nicht nur pandas/Pfade direkt),
  `PYTHONPATH=src` voranstellen, sonst `ModuleNotFoundError: No module named
  'youtube_code'`.
- `PYTHONIOENCODING=utf-8` vor Python-Aufrufen setzen - sonst crasht das Skript beim
  Drucken von Emoji-Kanalnamen (cp1252-Konsole). Der Crash passiert erst beim
  `print()`, nicht beim Schreiben - bereits geschriebene Dateien/State-Änderungen
  bleiben davon unberührt, aber sicherheitshalber immer mit dem Encoding-Fix starten.
- Lange Skripte (State-Verarbeitung, API-Sammlung) im Hintergrund laufen lassen
  (`run_in_background`) und mit `TaskOutput(block=true)` auf Abschluss warten - nicht
  mit `sleep`-Schleifen pollen.
- **State-Datei (`data/samples/russia/longitudinal_screening_state.csv`, ~1.2GB) hat
  keine Git-Historie (nicht getrackt) - vor JEDER Änderung ein `.bak_<name>`-Backup
  anlegen.** Diese Session hat das bereits einmal getan
  (`longitudinal_screening_state.csv.bak_pre_37channels`), bevor 10 von 37 Kanälen
  erfolgreich Baseline-Zeilen bekamen (siehe unten).
- Nur `data/transcripts/all_transcripts_segments.csv` zählt projektweit als "hat schon
  ein Transkript" - relevant erst wieder für den Transkript-Scraping-Schritt nach dem
  Screening, nicht für diese Aufgabe direkt.
- Bei Hintergrund-Tasks nicht bei jedem Zwischenstand eine Nachricht schicken - nur
  bei Abschluss oder echten Meilensteinen/Blockern melden.

## Bereits erledigt (nicht wiederholen)

- 10 von ursprünglich 37 "Kanäle ohne Baseline" haben bereits Baseline-Kandidatenzeilen
  im State (Einsatzfahrten und so, Schweinfurter Nachrichten, gewaltig nachhaltig,
  HÄMATOM, Northern Finance, RedeFabrik, BildungsTV, exxpressTV, Serdar Somuncu,
  Bosetti will reden!) - deren Rohdaten lagen zufällig schon in
  `video_metadata_detailed_total.jsonl` vor.
- Diese 27 verbliebenen Kanäle sind der Rest, für den echte Neusammlung nötig ist.
- Master-Kanalliste (`data/external/media_type_russia_merged.xlsx`) wurde diese
  Session bereits um AUF1, PI-NEWS, Epoch Times Deutschland, Y-Kollektiv ergänzt
  (Spalte `notiz` markiert manuelle Ergänzungen) - nicht erneut hinzufügen.

# Handoff: Baseline-Datenerhebung 27 Kanäle — Fortsetzung ab Schritt 3

Diese Datei ist der Wiedereinstiegspunkt für eine neue Session, die den Auftrag aus
`outputs/segment_analysis/HANDOFF_baseline_collection_27_channels.md` (Original-Handoff,
Schritte 1–6) fortsetzt. **Schritte 1 und 2 sind für alle 27 Kanäle abgeschlossen und
verifiziert** (Details unten). Auftrag jetzt: **mit Schritt 3 (State erweitern)
weitermachen**, dann Schritte 4–6 wie im Original-Handoff beschrieben.

## Wichtig: Zwischenzeitliche Projekt-Restrukturierung

Der Nutzer führt parallel eine **weitreichende Restrukturierung des Projekts** durch,
Plan liegt in `.claude/restructuring/RESTRUCTURING_PLAN.md`, Fortschritt in
`.claude/restructuring/RESTRUCTURING_PROGRESS.md`. Diese Session begann, **bevor** diese
Restrukturierung durchgeführt wurde — je nachdem, wie weit sie beim Wiedereinstieg
fortgeschritten ist, können sich Pfade, Dateiformate (v.a. State: CSV → möglicherweise
`data/store/screening_state.sqlite`, siehe Phase 3c/4 des Plans) und Skript-Interfaces
geändert haben.

**Vor dem Weitermachen zwingend:**
1. `.claude/restructuring/RESTRUCTURING_PROGRESS.md` lesen — welche Phasen sind erledigt?
2. Prüfen, ob die unten genannten Pfade noch existieren. Falls nicht: per Dateiname
   suchen (die Inhalte/Daten sollten migriert, nicht verloren sein) und dieses Dokument
   gedanklich auf die neue Struktur übersetzen.
3. Falls die Restrukturierung bereits Phase 3c (Screening-State → SQLite) und/oder
   Phase 4 (Code-Reorganisation) erreicht hat: `append_channels_to_state.py` (siehe
   Schritt 3 unten) existiert in seiner jetzigen Form evtl. nicht mehr — dann das
   äquivalente Store-Modul (`youtube_code.store.screening_store` o.ä., siehe
   Zielstruktur im Plan) für den Upsert der Baseline-Kandidatenzeilen nutzen statt des
   CSV-Append-Skripts.
4. Falls sich `src/youtube_code/config/paths.py` geändert hat (Phase 5 des Plans
   erwähnt das explizit): Pfad-Konstanten (`RAW`, `OUTPUTS`, `CHANNEL_LISTS`) neu prüfen,
   bevor man sich auf die untenstehenden Pfade verlässt.

## Was in dieser Session bereits erledigt wurde (nicht wiederholen)

### Schritt 1 — Video-IDs sammeln: abgeschlossen für alle 27 Kanäle

- **24 "normale" Kanäle** (`TARGETED_SEARCH`-Modus): **0 Baseline-Videos gefunden — und
  das ist verifiziert korrekt, kein Bug.** Für jeden der 24 Kanäle wurde die komplette
  Uploads-Playlist bis zu ihrem natürlichen Ende (oder bis vor das Fenster
  2021-02-24 bis 2022-02-23) durchpaginiert, ohne einen Pagination-Cap zu erreichen
  (Diagnose-Skript-Ergebnis, 0 von 24 "unresolved"). Ursache: Die öffentlich abrufbare
  Upload-Historie der meisten dieser Kanäle reicht gar nicht bis 2021/2022 zurück
  (vermutlich Content-Bereinigung/Rebrand irgendwann in den letzten Jahren — heutiges
  Datum in dieser Session war 2026-08-28, über 4,5 Jahre nach dem Baseline-Fenster), der
  Rest hat eine echte Aktivitätslücke genau in diesem Zeitraum. Vollständiger
  Diagnose-Report: `outputs/segment_analysis/baseline_reach_check_24channels.json`.
  → **Kandidatenpool für alle 24 Kanäle gilt als erschöpft.**
- **3 sehr große Kanäle** (`TARGETED_SEARCH_YTDLP`-Modus, euronews/WELT/OE24.TV):
  **28.412 Baseline-Videos gefunden** (euronews 8.645, WELT 7.552, OE24.TV 12.215).
  Gespeichert in `data/raw/sample_50k_channels_russia_ukraine.json` und
  `data/raw/video_registry.sqlite`.
- `outputs/segment_analysis/kanaele_baseline_collection_todo.csv` ist bereits mit den
  finalen `n_baseline_zeilen`-Werten aktualisiert (0 für die 24, echte Counts für die 3
  großen).
- Liste der 28.412 Video-IDs (nur die 3 großen Kanäle, Baseline-Fenster):
  `outputs/segment_analysis/baseline_3_large_channels_video_ids.csv`.

### Schritt 2 — Beschreibungen holen: abgeschlossen und verifiziert (nur für die 3 großen Kanäle nötig, da die 24 anderen 0 Videos haben)

- `metadata_collection.py` mit `video_metadata=True`, `DETAILED=True`,
  `VIDEOS_INPUT_PATH` = die obige 28.412-Video-ID-CSV gelaufen (Registrier
  `channel_metadata` wurde für diesen Lauf auf `False` gesetzt, da für diesen Auftrag
  nicht gebraucht — bei Bedarf für andere Zwecke wieder auf `True` setzen).
  Geschrieben nach `data/raw/video_metadata_detailed_total.jsonl`.
- **Verifiziert:** Alle 28.412 Ziel-Video-IDs sind in der jsonl vorhanden, mit
  plausiblen Beschreibungen (Stichprobe: 400–500 Zeichen) und korrekten
  `published_at`-Werten im Fenster. 0 fehlend.

### Aktueller Zustand einiger Skript-Configs (ggf. zurücksetzen/neu prüfen)

- `src/youtube_code/collection/channel_all_videos.py`: `MODE` steht aktuell auf
  `"TARGETED_SEARCH_YTDLP"` (letzter Lauf dieser Session). `TARGETED_CHANNEL_INPUT`
  zeigt auf `baseline_still_missing_channels.csv` (24 normale Kanäle, überschrieben),
  `TARGETED_SEARCH_YTDLP_CHANNEL_INPUT` auf `baseline_unreliable_large_channels.csv`
  (3 große Kanäle, überschrieben). Für Schritt 3 nicht mehr benötigt.
- `src/youtube_code/collection/metadata_collection.py`: `channel_metadata=False`,
  `video_metadata=True`, `DETAILED=True`, `VIDEOS_INPUT_PATH` zeigt auf die
  28.412-Video-ID-CSV. Für Schritt 3 nicht mehr benötigt — falls dieses Skript für
  andere Zwecke wiederverwendet wird, Konfiguration prüfen/zurücksetzen.

## Nebenbefund (auf Nutzerfrage recherchiert, keine Aktion nötig)

Kanal **tagesschau** (`UC5NOEUbkLheQcaaRldYW5GA`, nicht Teil der 27er-Liste) hat bereits
192 Baseline-Kandidatenzeilen im State (`period=-1`), davon 15 bereits gescreent
(13 politisch relevant, 2 nicht), 177 noch offen für eine künftige Screening-Runde.

## Nächster Schritt: Schritt 3 — State erweitern

Wie im Original-Handoff beschrieben (Abschnitt "3. State erweitern"):

```
# VORHER IMMER Backup anlegen (State hat keine Git-Historie, ~1.2GB — sofern die
# Restrukturierung diese Datei nicht schon durch data/store/screening_state.sqlite
# ersetzt hat, siehe Hinweis oben):
cp data/samples/russia/longitudinal_screening_state.csv \
   data/samples/russia/longitudinal_screening_state.csv.bak_pre_27channels_step3

PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
  src/youtube_code/politics_screening/longitudinal/append_channels_to_state.py \
  --channels outputs/segment_analysis/kanaele_baseline_collection_todo.csv \
  --videos data/raw/video_metadata_detailed_total.jsonl \
  --dry-run   # erst pruefen, dann ohne --dry-run wirklich schreiben
```

Da 24 der 27 Kanäle 0 Baseline-Videos haben, wird das Skript für diese vermutlich keine
(oder nur die bereits vorher vorhandenen) Zeilen anlegen — das ist erwartet, kein Fehler.
Für die 3 großen Kanäle sollten ~28.412 neue Baseline-Kandidatenzeilen entstehen (nach
Anwendung der Rank-/Interval-Logik des Skripts, die finale Zahl der tatsächlich
übernommenen Kandidaten kann kleiner sein als 28.412, falls das Skript pro
Kanal/Intervall auf `TARGET_WITH_BUFFER_PER_INTERVAL` begrenzt — normales Verhalten,
siehe Skript-Logik).

Danach weiter mit Schritt 4–6 aus dem Original-Handoff (Screening-Runde erzeugen,
Titel-Klassifikation starten, Ergebnisse zurückführen, iterieren bis Ziel erreicht oder
Pool erschöpft). Alle dortigen technischen Hinweise (venv-Python, `PYTHONPATH=src`,
`PYTHONIOENCODING=utf-8`, Hintergrund-Läufe mit `TaskOutput(block=true)`, nur bei
Meilensteinen/Blockern melden) gelten unverändert.

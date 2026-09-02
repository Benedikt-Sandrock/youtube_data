## Regeln für jede Session:
**README.md**:Um die Dateistruktur zu verstehen, lies die im ROOT abgelegt `README.md`.

**COMPLETE_PROCESS.md**: Um den Ablauf des Projekts zu verstehen, lies `COMPLETE_PROCESS.md`

**Transkript-Verfügbarkeit**: Beim Abgleich, für welche Videos schon ein Transkript vorliegt, zählt NUR der `transcript_store` (`data/store/transcripts.sqlite`, Modul `src/youtube_code/store/transcript_store.py`) — maßgeblich sind dessen Funktionen `attempted_video_ids()`/`has_transcript()`/`get_transcripts()`. Alle CSV-basierten Transkript-Dateien (u. a. das ehemalige `data/transcripts/all_transcripts_segments.csv`) sind veraltete Formate aus der Zeit vor der Store-Migration (Phase 3) und zählen nicht.

**Keine Ad-hoc-Skripte/Daten außerhalb von `scripts/adhoc/`**: Einmalige, projektspezifische Auswertungs- oder Migrationsskripte sowie ihre Zwischendateien gehören nach `scripts/adhoc/`, nicht lose in `src/youtube_code/` oder ins Repo-Root. Das hält die zentrale Codebasis (`src/youtube_code/`) auf dauerhaft gepflegten, wiederverwendbaren Code beschränkt.

**Offen — Zählungsverzerrung durch Mindestlängen-Filter (`MIN_VIDEO_DURATION_SECONDS`, 181s)**: `select_baseline_targets()` (`src/youtube_code/step4_transcript_download/select_targets.py`) prüft weiterhin gegen die rohen `politics_final==1`-Zählungen aus `screening_state.sqlite`, bevor der Duration-Filter am Ende die Video-IDs aussortiert. Da `screening_state` laut `scripts/adhoc/check_min_duration_violations.py` noch 265.523 Altzeilen unter 181s (bzw. mit unbekannter Dauer) enthält — teils schon mit `politics_final`-Label —, kann ein Kanal fälschlich als "Baseline-Ziel erreicht" gelten, obwohl ein Teil der dafür gezählten Videos zu kurz war und nach dem Filter gar nicht mehr im Sample landet. Der Nutzer muss noch prüfen/entscheiden, ob und wie `screening_state` bzw. die Zielzählung bereinigt werden soll, bevor auf Basis der Baseline-Qualifikation weitergearbeitet wird.

Ich habe die Funktion get_states in screening_state_store.py um eine politics_final Option erweitert. Überprüfe beim nächsten Start, ob die Funktion so noch funktioniert. Wenn ja, lösche diesen Eintrag aus der CLAUDE.md Datei.


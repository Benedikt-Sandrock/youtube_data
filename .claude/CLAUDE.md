## Regeln für jede Session:
**README.md**:Um die Dateistruktur zu verstehen, lies die im ROOT abgelegt `README.md`.

**Transkript-Verfügbarkeit**: Beim Abgleich, für welche Videos schon ein Transkript vorliegt, zählt NUR der `transcript_store` (`data/store/transcripts.sqlite`, Modul `src/youtube_code/store/transcript_store.py`) — maßgeblich sind dessen Funktionen `attempted_video_ids()`/`has_transcript()`/`get_transcripts()`. Alle CSV-basierten Transkript-Dateien (u. a. das ehemalige `data/transcripts/all_transcripts_segments.csv`) sind veraltete Formate aus der Zeit vor der Store-Migration (Phase 3) und zählen nicht.

**Keine Ad-hoc-Skripte/Daten außerhalb von `scripts/adhoc/`**: Einmalige, projektspezifische Auswertungs- oder Migrationsskripte sowie ihre Zwischendateien gehören nach `scripts/adhoc/`, nicht lose in `src/youtube_code/` oder ins Repo-Root. Das hält die zentrale Codebasis (`src/youtube_code/`) auf dauerhaft gepflegten, wiederverwendbaren Code beschränkt.


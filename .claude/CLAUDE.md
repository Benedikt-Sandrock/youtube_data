## Regeln für jede Session:

**HAUPTZIEL HEUTE (3.9.26)**: Erste Beantwortung aller Forschungsfragen

**README.md**:Um die Dateistruktur zu verstehen, lies die im ROOT abgelegt `README.md`.

**COMPLETE_PROCESS.md**: Um den Ablauf des Projekts zu verstehen, lies `COMPLETE_PROCESS.md`

**Forschungsfragen**:
Ich möchte mit dem Projekt folgende Fragen untersuchen:
1. Hat der Populismus auf YouTube nach dem Beginn des Ukraine-Kriegs zugenommen? Gibt es Unterschiede nach politischer Ideologie oder Medientyp? Bei welchen Dimensionen des Populismus hat sich etwas verändert?
2. Wie hat sich der Erfolg der Kanäle entwickelt? Werden bestimmte Medientypen erfolgreicher? Sind populistische Kanäle seit Kriegsbeginn erfolgreicher geworden? Gibt es Untersschiede zwischen rechten und linken Kanälen?
3. Werden Kanäle, die populistischer werden, auch erfolgreicher?
4. Bei erfolgreicher werdenen Kanälen: Betrifft das nur Kriegsvideos oder auch andere Videos?
Anmerkung: Wo immer möglich, Vergleich vor vs. nach Kriegsbeginn durchführen, um den Kriegsbeginn als exogene Variation zu nutzen.
Behalte diese Fragen immer im Hinterkopf. Weise mich darauf hin, falls ich nicht zielorientiert arbeite.

**Transkript-Verfügbarkeit**: Beim Abgleich, für welche Videos schon ein Transkript vorliegt, zählt NUR der `transcript_store` (`data/store/transcripts.sqlite`, Modul `src/youtube_code/store/transcript_store.py`) — maßgeblich sind dessen Funktionen `attempted_video_ids()`/`has_transcript()`/`get_transcripts()`. Alle CSV-basierten Transkript-Dateien (u. a. das ehemalige `data/transcripts/all_transcripts_segments.csv`) sind veraltete Formate aus der Zeit vor der Store-Migration (Phase 3) und zählen nicht.

**Keine Ad-hoc-Skripte/Daten außerhalb von `scripts/adhoc/`**: Einmalige, projektspezifische Auswertungs- oder Migrationsskripte sowie ihre Zwischendateien gehören nach `scripts/adhoc/`, nicht lose in `src/youtube_code/` oder ins Repo-Root. Das hält die zentrale Codebasis (`src/youtube_code/`) auf dauerhaft gepflegten, wiederverwendbaren Code beschränkt.

**Testläufe**: Führe Testläufe von Skripten, die voraussichtlich etwas länger dauern und viel Arbeitsspeicher blockieren, nicht ohne meine Genehmigung durch. Frage vorher immer nach.

**Anpssung von READMEs und Docstring**: Wenn du Skripte oder Strukturen anpasst, passe immer auch die jeweiligen Docstrings und READMEs an, die auf die geänderten Dinge Bezug nehmen.


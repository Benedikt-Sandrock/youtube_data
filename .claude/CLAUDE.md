## Regeln für jede Session:

**README.md**:Um die Dateistruktur zu verstehen, lies die im ROOT abgelegt `README.md`.

**COMPLETE_PROCESS.md**: Um den Ablauf des Projekts zu verstehen, lies `COMPLETE_PROCESS.md`

**Lies "Aufgaben.md" in .claude**: Da stehen die Hauptaufgaben, die ich heute erledigen möchte. Weise mich ab und zu darauf hin, falls ich zu viele andere Dinge mache und nicht zielgerichtet arbeite.

**Realismus**: Gib keine zu optimistischen Antworten. Wenn ich bspw. frage, ob sich die detailliertere Untersuchung von ersten Befunden/grafischen Trends lohnt, gib eine ehrlich Einschätzung ab, ob wirklich etwas dahinterstecken könnte, oder ob es sich eher um Spezifikationssuche handelt.

**Session Context**: Wenn ich Anfragen stelle, die sich effizienter in einer neuen Session mit leerem Context bearbeiten lassen, weise mich darauf hin, eine neue Session zu starten.

**Regressionsoutput**: Wenn du Skripte für detaillierte Regressionen schreibst (mehrere Läufe mit verschiedenen Spezifikationen), sorge immer dafür, dass der Output übersichtlich in eine menschenlesbare Markdown Datei geschreiben wird. Das Verzeichnis dafür soll immer ein Ordner namens "regression_results" im ursprünglichen Ergebnispfad (z.B. OUTPUTS / "segment_analysis") sein.

**Forschungsfragen**:
Ich möchte mit dem Projekt folgende Fragen untersuchen:
1. Hat der Populismus auf YouTube nach dem Beginn des Ukraine-Kriegs zugenommen? Gibt es Unterschiede nach politischer Ideologie oder Medientyp? Bei welchen Dimensionen des Populismus hat sich etwas verändert?
2. Wie hat sich der Erfolg der Kanäle entwickelt? Werden bestimmte Medientypen erfolgreicher? Sind populistische Kanäle seit Kriegsbeginn erfolgreicher geworden? Gibt es Untersschiede zwischen rechten und linken Kanälen?
3. Werden Kanäle, die populistischer werden, auch erfolgreicher?
4. Bei erfolgreicher werdenen Kanälen: Betrifft das nur Kriegsvideos oder auch andere Videos?
Anmerkung: Wo immer möglich, Vergleich vor vs. nach Kriegsbeginn durchführen, um den Kriegsbeginn als exogene Variation zu nutzen.
Behalte diese Fragen immer im Hinterkopf. Weise mich darauf hin, falls ich nicht zielorientiert arbeite.

**Transkript-Verfügbarkeit**: Beim Abgleich, für welche Videos schon ein Transkript vorliegt, zählt NUR der `transcript_store` (`data/store/transcripts.sqlite`, Modul `src/youtube_code/store/transcript_store.py`) — maßgeblich sind dessen Funktionen `attempted_video_ids()`/`has_transcript()`/`get_transcripts()`. Alle CSV-basierten Transkript-Dateien (u. a. das ehemalige `data/transcripts/all_transcripts_segments.csv`) sind veraltete Formate aus der Zeit vor der Store-Migration (Phase 3) und zählen nicht.

**Zentraler Analysedatensatz**: `outputs/stata_rohdaten/videos_roh.dta` + `kanaele_roh.dta` (erzeugt von `src/youtube_code/step6_auswertung/export_stata_rohdaten.py`, Variablen in `docs/codebuch_rohdatensatz.md`) ist der zentrale Ausgangspunkt für alle neuen Analysen und Grafiken (Stata und Python). Neue Analyseskripte lesen von dort, nicht aus den Stores oder den älteren CSVs in `outputs/segment_analysis/`. Wenn ich Daten hinzufüge oder ändere (neue LLM-Runs, neue Kanäle/Videos, neue Klassifikationen, Topics, Formate, Kanalmerkmale), wird der Export entsprechend erweitert (Codebuch, Konsistenzprüfungen, Docstring mitpflegen) und neu erzeugt — weise mich darauf hin, wenn ein Neu-Export fällig ist. Für LLM-basierte Variablen (`pop_*`, `pos_*`) immer `min_dauer == 1` filtern. Der Export dauert ca. 40 min — vor dem Start fragen.

**Keine Ad-hoc-Skripte/Daten außerhalb von `scripts/adhoc/`**: Einmalige, projektspezifische Auswertungs- oder Migrationsskripte sowie ihre Zwischendateien gehören nach `scripts/adhoc/`, nicht lose in `src/youtube_code/` oder ins Repo-Root. Das hält die zentrale Codebasis (`src/youtube_code/`) auf dauerhaft gepflegten, wiederverwendbaren Code beschränkt. **Ausnahme:** Skripte für die Arbeitspakete aus `.claude/plans/masterarbeit_strategie.md` kommen nach `scripts/masterarbeit/apN_<thema>.py`, ihre Ergebnisse nach `outputs/masterarbeit/apN_<thema>/` (siehe die READMEs dort).

**Parameter über Konfigurationsblock statt argparse**: Neue Skripte bekommen ihre Eingaben (Kanäle, Zeiträume, Schwellen, Pfade, Seeds usw.) über einen klar markierten Konfigurationsblock mit Konstanten oben im Skript (direkt nach den Imports), nicht über `argparse`/Kommandozeilenargumente. Jede Konstante bekommt einen kurzen Kommentar zu erlaubten Werten; ungültige Werte werden in `main()` geprüft und mit verständlicher Meldung abgebrochen.

**Testläufe**: Führe Testläufe von Skripten, die voraussichtlich etwas länger dauern und viel Arbeitsspeicher blockieren, nicht ohne meine Genehmigung durch. Frage vorher immer nach.

**Anpssung von READMEs und Docstring**: Wenn du Skripte oder Strukturen anpasst, passe immer auch die jeweiligen Docstrings und READMEs an, die auf die geänderten Dinge Bezug nehmen.


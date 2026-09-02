# COMPLETE PROJECT PROCESS

Diese Datei beschreibt den gesamten Prozess, von der Auswahl des Samples über die Auswahl und Klassifikation relevanter Videos bis zur Auswertung der Ergebnisse.

## Wichtig:
In Zukunft soll so viel wie möglich automatisch konfiguriert werden. Bsp.: In der Auswertung soll angegeben werden können, welche Dimension für welches Sample analysiert werden soll (z.B. Populismus für Russland-Sample). Die Skripte suchen sich dann die entsprechdnen Kanäle und LLM-Outputs zusammen (inklusive Baselines für die Kanäle) und erstellen angepasste Analysen.

## 1. SAMPLE
### Scripts: `youtube_code/step1_sample`
### Zentrale Speicherung: `data/store/video_registry.sqlite`
Das Sample entsteht über Stichwortsuchen via YouTube-API nach vorher definierten Begriffen in vorher definierten Zeiträumen. Welche Videos mit welchen Suchen gefunden wurden, wird in einer registry festgehalten.
Für die Kanäle, die diese Videos hochgeladen haben, wird zunächst eine Sprachklassifikation vorgenommen, um deutschsprachige Kanäle herauszufiltern. Für diese werden Daten für ALLE Videos seit dem 24.02.2021 (1 Jahr vor Kriegsbeginn) über die API abgefragt. Zudem werden Metadaten für die Kanäle abgefragt.
Über das zentrale Skript `youtube_code/step1_sample/build_channel_provenance.py` wird die Sample-Zugehörigkeit definiert: es liest Such-Provenienz, Sprachklassifikation und Kanal-Metadaten direkt aus `video_registry.sqlite` und lässt sich über `QUERY_FILTER`/`SEARCH_PERIOD_FILTER` auf einen Ausschnitt der Suchhistorie einschränken — z.B. alle Kanäle, die im Suchzeitraum 24.02.2021 - 23.02.2022 über die Suche nach "CDU" oder "SPD" gefunden wurden. `ANALYSIS_ID` bestimmt den Output-Unterordner (`data/samples/<ANALYSIS_ID>/`), sodass verschiedene Sample-Definitionen sich nie überschreiben. Siehe `youtube_code/step1_sample/README.md` für die vollständige Skript-Übersicht.

## 2. Vor- und Nachkriegskanäle
### README: `youtube_code/step2_baseline_channels/README.md` für eine detaillierte Beschreibung sowie den Schritt-für-Schritt-Ablauf.
### Scripts: `youtube_code/step2_baseline_channels` (inkl. `longitudinal/`) sowie die geteilte Batch-Infrastruktur in `youtube_code/llm_analysis`
### Zentrale Speicherung: `data/store/screening_state.sqlite`
Kanäle, die bereits vor dem Krieg existiert haben (Grüdungsdatum in den Kanalmetadatan in `video_registry.sqlite`), erhalten die letzten 12 Monate vor Kriegsbeginn als Baseline-Fenster.
Kanäle, die erst nach Kriegsbeginn gegründet wurden, erhalten ein flexibles Baseline-Fenster von bis zu 12 Monaten nach ihrer Gründung (`youtube_code/step2_baseline_channels/longitudinal/assign_postwar_baseline.py`).
Für das jeweilige Baseline-Fenster werden Videos benötigt, die politischen Inhalt enthalten, damit sie für eine Klassifikation verwendet werden können. Als Vorauswahl werden Videotitel und -beschreibungen über ein LLM klassifiziert. Sobald ein Kanal eine gewisse Anzahl politisch klassifizierter Videos hat, gilt seine Baseline als vollständig.

## 3. Identifikation von Kriegsvideos
### Scripts: `youtube_code/step3_war_videos`
### Zentrale Speicherung: Tabelle `video_topic_relevance` in `video_registry.sqlite`
Für alle Kanäle, die in die Analyse eingehen sollen, werden Videos gesucht, die sich mit dem Ukraine-Krieg beschäftigen. Dazu wird eine Stichwortsuche in Titel und Beschreibung nach einer vorgegebenen Liste verwendet (`youtube_code/step3_war_videos/topic_keywords.py`, übernommen aus den bereits validierten Mustern in `new_analysis/feasibility.py`). In der zentralen Videospeicherung gibt die generische Tabelle `video_topic_relevance` (Spalte `topic`) an, ob ein Video (vermutlich) Bezug zu einem Thema hat oder nicht — Standard-Topic ist `russia_ukraine_war`, weitere Themen (z.B. Nahost) lassen sich ohne Schema-Änderung ergänzen. `youtube_code/step3_war_videos/classify_topic_relevance.py` führt die Klassifikation aus.
Diese Videos bilden einen wichtigen Teil der Analyse, da hier die direkten Auswirkungen der Kommunikation im Krieg gemessen werden können.

## 4. Download von Transkripten
### Scripts: `youtube_code/step4_transcript_download`
### Zentrale Speicherung: `data/store/transcripts.sqlite`
Für relevante Videos (z.B. Baseline-Videos, Kriegsvideos) sollen Video-Transkripte heruntergeladen werden. Dies geschieht über eine zentrale Funktion (`download_transcripts()`), die eine Liste von Video IDs als Input erhält. `youtube_code/step4_transcript_download/select_targets.py` extrahiert aus den gespeicherten Videodaten die passende Liste an Video IDs für eine von drei Konfigurationen; `run_transcript_selection.py` verbindet beides.
Drei Konfigurationen sind am wichtigsten:
1. `select_baseline_targets()`: Für alle Kanäle die Baseline überprüfen und alle Video IDs extrahieren, die zu den Baseline-Videos der Kanäle gehören.
2. `select_cell_fill_targets()`: Kanal-Monats-Zellen identifizieren und Kriegs-/ und (bestenfalls) als politisch klassifizierte Nichts-Kriegsvideos identifizieren, damit jede Zelle mit einer variabel festlegbaren Zahl an Videos besetzt ist.
3. `select_war_period_targets()`: Alle Kriegsvideos in einem bestimmten Zeitraum identifizieren (z.B. kurz vor und nach einem wichtigen Event).

## 5. Klassifikation von Transkripten
### Scripts: `youtube_code/step5_segment_analysis`
### Zentrale Speicherung: `outputs` und `data/store/llm_runs.sqlite`
Der Klassifizierungsprozess läuft in mehreren Schritten. Benötigter Input ist eine Liste von Video IDs. Alle Jobs werden automatisch in `llm_runs.sqlite` in die Registry eingetragen.
0. Prompts werden festgelegt in `segment_prompts_simple.py`
1. `process_scraped_segments.py`: Für alle IDs werden Transkripte abgerufen. Diese werden zu Segmenten zusammengefügt, die an Vertex AI geschickt werden können.
2. `submit_segments.py`: Segmente werden zusammen mit einem Prompt an Vertex AI geschickt.
3. `download_segments_simple.py`: Fertige Jobs werden heruntergeladen
Im Ordner sind weitere Diagnoseskripte enthalten, deren Funktion überprüft werden muss.

## 6. Auswertung von Transkripten
### Scripts: `youtube_code/step6_auswertung`
### Zentrale Speicherung: `outputs`
Über `prepare_channel_scores.py` (Segment- → Video- → Kanal×Periode-Aggregation), `deskriptiv_aggregation`, `deskriptiv_plots`, `geglaettete_kurve` und `fe_signifikanz_test` werden Auswertungen vorgenommen (siehe `youtube_code/step6_auswertung/README.md` für den Ablauf und die aktuell noch offene manuelle Kuratierungsstufe zwischen LLM-Rohergebnis und `prepare_channel_scores.py`-Input). 
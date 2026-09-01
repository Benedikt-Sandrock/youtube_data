# Sample — Kurzreferenz

Skripte für COMPLETE_PROCESS.md Schritt 1 ("SAMPLE"): Stichwortsuche nach
Kanälen/Videos, Sprachklassifikation, Video-/Kanal-Metadaten-Abruf, und das
zentrale Skript, über das die Sample-Zugehörigkeit definiert wird. Alle vier
Collection-Skripte (`video_identification.py`, `channel_all_videos.py`,
`metadata_collection.py`) schreiben live in `data/store/video_registry.sqlite`
(Modul `src/youtube_code/store/video_registry.py`) — das ist seit der
Restrukturierung die alleinige, laufend aktuelle Quelle für Such-Provenienz,
Sprach-Klassifikation und Kanal-Metadaten; die dabei zusätzlich geschriebenen
JSON/JSONL-Dateien sind nur noch Nebenprodukte einzelner Skript-Läufe, keine
maßgebliche Quelle mehr.

| Skript | Zweck | Ausführung |
| --- | --- | --- |
| `video_identification.py` | Stichwortsuche nach Videos/Kanälen für konfigurierte Suchbegriffe/Zeiträume (`settings_variables.py`); schreibt `search_runs`/`video_search_hits` | pro Suchlauf |
| `channel_all_videos.py` | Für neu entdeckte Kanäle: Sprachklassifikation + alle Videos seit dem Analyse-Start abrufen; schreibt `language_classification` sowie Video-Kernfelder | pro neue Kanalgruppe |
| `metadata_collection.py` | Detaillierte Video- und/oder Kanal-Metadaten für eine ID-Liste abrufen; schreibt `video_details` bzw. `channels` | bei Bedarf |
| `settings_variables.py` | Gemeinsame Konfiguration (Suchzeitraum, Suchbegriffe, Zielverzeichnis) für `video_identification.py`/`channel_all_videos.py` — kein eigenständiges Skript, wird per bare sibling import eingebunden | — |
| `build_channel_provenance.py` | **Zentrales Sample-Definitions-Skript**: kombiniert Such-Provenienz, Sprachklassifikation, Kanal-Metadaten sowie Video-Registry-Lookups aus `video_registry.sqlite` zu einer Kanal-Provenienztabelle mit Eligibility-Flags. `QUERY_FILTER`/`SEARCH_PERIOD_FILTER` legen fest, welcher Ausschnitt der Suchhistorie "das Sample" für einen Lauf ist (z. B. alle über "CDU"/"SPD" im Zeitraum 24.02.2021–23.02.2022 gefundenen Kanäle); `ANALYSIS_ID` bestimmt den Output-Unterordner (`data/samples/<ANALYSIS_ID>/`), sodass verschiedene Läufe sich nie überschreiben | einmal je Sample-Definition |

## Hinweise

- `video_identification.py` und `channel_all_videos.py` sind zum direkten
  Ausführen gedacht (`python video_identification.py`), nicht zum Importieren
  — sie binden `settings_variables.py` per bare sibling import ein (verlässt
  sich darauf, dass Python beim direkten Start das Skriptverzeichnis auf
  `sys.path[0]` legt).
- `build_channel_provenance.py` liest ausschließlich aus dem Store — keine
  JSON-Zwischendateien, keine erneute Migration nötig. Vor einem echten Lauf
  erst mit `DRY_RUN = True` die gedruckte Übersicht prüfen.
- Für Schritt 2 (Vor-/Nachkriegskanäle, Baseline-Fenster) siehe
  `src/youtube_code/step2_baseline_channels/`.

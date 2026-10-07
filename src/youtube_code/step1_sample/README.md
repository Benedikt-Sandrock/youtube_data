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
| `metadata_collection.py` | Detaillierte Video- und/oder Kanal-Metadaten für eine ID-Liste abrufen; schreibt `video_details` bzw. `channels`. Standardmäßig ein einmaliger Snapshot (bereits bekannte video_ids werden übersprungen, `view_count`/`like_count`/`comment_count` bleiben unverändert); mit `REFRESH_MODE = True` werden diese drei Spalten für die übergebene ID-Liste bewusst mit dem neu abgerufenen Wert überschrieben (siehe Docstring dort und `video_registry.refresh_video_stats()`). Mit `CHECK_CHANNELS_MODE = True` (seit 2026-09-10) statt einer fertigen Video-ID-Liste eine Kanalliste übergeben: `get_missing_metadata_for_channels()` prüft dann selbst, welche der in der Registry bereits bekannten Videos dieser Kanäle Metadaten fehlen (`view_count` bei `DETAILED = False`, `video_details`/`topic_categories` bei `DETAILED = True`) und fragt nur die fehlenden gezielt nach — keine Video-Discovery, für Kanäle ganz ohne bekanntes Video siehe `channel_all_videos.py` (`TARGETED_SEARCH`) | bei Bedarf |
| `channel_video_formats.py` | Für eine Kanalliste (`CHANNEL_INPUT`, CSV/JSON mit `channel_id`) das Format jedes Videos im Fenster `PUBLISHED_AFTER`–`PUBLISHED_BEFORE` bestimmen: Short / normales Video / Livestream. Die Data API hat kein `isShort`-Feld, deshalb über die kanaleigenen Format-Playlists `UUSH<rest>` / `UULF<rest>` / `UULV<rest>` (aus `UC<rest>`); die drei Format-Playlists sind gefilterte Ansichten der auf die neuesten ~20.000 Uploads gekappten Upload-Liste und teilen sich diese Grenze (tagesschau: alle drei enden im Juli 2022). Meldet die Upload-Playlist `UU<rest>` ≥ `UPLOADS_CAP_THRESHOLD` Einträge, ergänzt yt-dlp jede Format-Playlist, die den Fensteranfang nicht erreicht, über die Tabs `/shorts`, `/videos`, `/streams`. Schreibt die Tabelle `video_format` und trägt bisher unbekannte Videos mit detaillierten Metadaten in `videos`/`video_details` nach. **Alles-oder-nichts pro Kanal**: ein Kanal wird erst nach vollständigem Abruf in einer Transaktion geschrieben; bei Quota-Abbruch wird er verworfen und im Folgelauf komplett neu abgefragt (Statusdatei `<liste>_formats_status.csv` neben der Kanalliste). Report: `outputs/video_formats/<liste>_formats_report.md` (inkl. HEAD-Validierung gegen `/shorts/<id>` und Dauer-Plausibilität). Erst mit `DRY_RUN = True` testen; danach `step3_topic_relevance` für die neuen Videos laufen lassen | pro Kanalliste |
| `settings_variables.py` | Gemeinsame Konfiguration (Suchzeitraum, Suchbegriffe, Zielverzeichnis) für `video_identification.py`/`channel_all_videos.py` — kein eigenständiges Skript, wird per bare sibling import eingebunden | — |
| `build_channel_provenance.py` | **Zentrales Sample-Definitions-Skript**: kombiniert Such-Provenienz, Sprachklassifikation, Kanal-Metadaten sowie Video-Registry-Lookups aus `video_registry.sqlite` zu einer Kanal-Provenienztabelle mit Eligibility-Flags. `QUERY_FILTER`/`SEARCH_PERIOD_FILTER` legen fest, welcher Ausschnitt der Suchhistorie "das Sample" für einen Lauf ist (z. B. alle über "CDU"/"SPD" im Zeitraum 24.02.2021–23.02.2022 gefundenen Kanäle); `ANALYSIS_ID` bestimmt den Output-Unterordner (`data/samples/<ANALYSIS_ID>/`), sodass verschiedene Läufe sich nie überschreiben | einmal je Sample-Definition |

## Hinweise

- `video_identification.py` und `channel_all_videos.py` sind zum direkten
  Ausführen gedacht (`python video_identification.py`), nicht zum Importieren
  — sie binden `settings_variables.py` per bare sibling import ein (verlässt
  sich darauf, dass Python beim direkten Start das Skriptverzeichnis auf
  `sys.path[0]` legt).
- `channel_all_videos.py` im Modus `TARGETED_SEARCH_YTDLP` zählt den
  `/videos`-Tab auf — der enthält **keine Shorts und keine Livestreams**.
  Bei Kanälen, die (auch) darüber nachgescrapt wurden, fehlen diese daher in
  der Registry; `channel_video_formats.py` trägt sie nach. Der yt-dlp-Helfer
  selbst liegt in `youtube_code/utils/ytdlp.py` (`list_channel_video_ids_ytdlp(channel_id, tab=...)`).
- yt-dlp bricht die Tab-Aufzählung bei wiederholtem „Incomplete data“ von
  YouTube standardmäßig **still** ab und liefert eine Teilliste (06.10.2026,
  tagesschau `/videos`: 6.510 statt 29.973 IDs). `ytdlp.py` setzt deshalb
  10 Wiederholungen mit Wartezeit und `raise_incomplete_data`: Der Abbruch
  wird zur Exception, beide Skripte tragen den Kanal als `fehler` in ihre
  Statusdatei ein, und ein Folgelauf fragt ihn neu ab. yt-dlp-Warnungen werden
  jetzt ausgegeben (`[yt-dlp] ...`). Kanäle, die vor dieser Änderung per
  yt-dlp als `komplett` vermerkt wurden, können unbemerkt unvollständig sein.
- Die yt-dlp-Aufzählung läuft lazy (`iter_channel_video_id_batches`, 50er-Blöcke,
  neueste zuerst). Beide Skripte hören auf zu blättern, sobald
  `YTDLP_EARLY_STOP_BATCHES` Blöcke komplett vor dem Fensteranfang liegen —
  ältere Tab-Seiten werden dann gar nicht mehr abgerufen (tagesschau `/videos`:
  ~18.000 statt ~30.000 IDs). Die Ausgabe `yt-dlp ...: N IDs gelesen ... ->
  Fensteranfang erreicht, Stopp` bzw. `Tab-Ende erreicht` zeigt, welcher Fall
  eintrat.
- `build_channel_provenance.py` liest ausschließlich aus dem Store — keine
  JSON-Zwischendateien, keine erneute Migration nötig. Vor einem echten Lauf
  erst mit `DRY_RUN = True` die gedruckte Übersicht prüfen.
- Für Schritt 2 (Vor-/Nachkriegskanäle, Baseline-Fenster) siehe
  `src/youtube_code/step2_baseline_channels/`.

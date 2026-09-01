# youtube_data

Sammlung, Screening und LLM-gestützte Kodierung von YouTube-Kanal- und
Video-Daten (Politik-Screening, Segment-Klassifikation). Dieses README gibt
einen Kurzüberblick über die Ordnerstruktur nach der mehrphasigen
Restrukturierung (`.claude/restructuring/RESTRUCTURING_PROGRESS.md`
dokumentiert den vollständigen Verlauf). Für Session-Regeln siehe
`.claude/CLAUDE.md`.

## Zentrale Datenhaltung: `data/store/`

Die vier SQLite-Stores sind die alleinige Quelle der Wahrheit für
Video-Metadaten, Transkripte, Screening-Status und LLM-Runs. Zugriff läuft
ausschließlich über die passenden Module in `src/youtube_code/store/` (nie
über `DB_PATH` oder rohes SQL direkt):

| Store | Modul | Inhalt |
| --- | --- | --- |
| `data/store/video_registry.sqlite` | `video_registry.py` | zentrale Video-/Kanal-Metadaten-Registry, inkl. Kanal-Metadaten (`channels`), Sprachklassifikation (`language_classification`), Such-Provenienz (`search_runs`/`video_search_hits`) sowie Keyword-basierter Themen-Relevanz (`video_topic_relevance`, z.B. Ukraine-Krieg-Bezug, siehe `step3_war_videos/`) — alle laufen live mit den Collection-/Klassifikationsskripten mit, keine separate Migration nötig |
| `data/store/transcripts.sqlite` | `transcript_store.py` | heruntergeladene Transkripte |
| `data/store/screening_state.sqlite` | `screening_state_store.py` | longitudinaler Politik-Screening-Status |
| `data/store/llm_runs.sqlite` | `llm_run_store.py` | Registry aller eingereichten LLM-Batch-Jobs |

Die Dateien sind groß (bis >1 GB) und daher **nicht** in Git getrackt
(`.gitignore`); sie existieren nur lokal bzw. in den externen Backups (siehe
unten). Jedes Modul exponiert Funktionen wie `total_count()`,
`get_transcripts()`, `attempted_video_ids()` — Verifikation nach jeder
Store-Änderung:

```bash
PYTHONPATH=src python -c "from youtube_code.store import video_registry, transcript_store, screening_state_store, llm_run_store; print(video_registry.total_count(), transcript_store.total_count(), screening_state_store.total_count(), llm_run_store.total_count())"
```

## Zulieferdateien — nicht die Wahrheit

Die folgenden `data/`-Unterordner enthalten kuratierte oder rohe
Zulieferdateien (Kanallisten, Stichproben, Exploration, externe Excel-Dateien)
für einzelne Skripte/Analysen. Sie sind **nicht** die maßgebliche Datenquelle
— das sind ausschließlich die Stores oben:

- `data/raw/` — unverarbeitete API-Dumps und Zwischendateien einzelner Läufe.
- `data/channel_lists/` — Kanal-Identifikationslisten.
- `data/samples/` — Stichproben für Screening-Runden und Klassifikation.
- `data/external/` — extern gepflegte Dateien (z. B. manuelle Kanal-Klassifikation).
- `data/exploration/` — Ad-hoc-Explorationsdaten.
- `data/transcripts/` — historisch die CSV-basierte Transkriptablage vor der
  Store-Migration (Phase 3b); mittlerweile leer, ersetzt durch
  `data/store/transcripts.sqlite`.

## Outputs

- `outputs/llm_results/<source>__<run_id>/` — heruntergeladene, bezahlte
  LLM-Ergebnisse pro Run. **Nicht regenerierbar** (echtes Geld für die
  API-Calls) — nie leichtfertig löschen.
- `outputs/llm/` — Zwischen-/Arbeitsdateien laufender LLM-Batch-Jobs
  (JSONL, Manifeste) vor dem Download nach `llm_results/`.
- `outputs/segment_analysis/`, `outputs/title_classification/`,
  `outputs/validation/`, `outputs/sample_feasibility/`, `outputs/pilot/` —
  Analyse-/Validierungsausgaben einzelner Pipelines, überwiegend
  regenerierbar aus den Stores.

## Code

- `src/youtube_code/store/` — zentrale Zugriffsschicht auf die vier Stores
  (Muster für neue Zugriffsfunktionen: `video_registry.py`).
- `src/youtube_code/config/paths.py` — alle Projektpfade als Konstanten;
  neue Skripte importieren Pfade ausschließlich von hier, statt sie
  hart zu kodieren.
- `src/youtube_code/step1_sample/` — COMPLETE_PROCESS.md Schritt 1: Kanal-/
  Video-Sammlung über die YouTube-API sowie `build_channel_provenance.py`,
  das zentrale Skript, über das die Sample-Zugehörigkeit definiert wird
  (siehe `README.md` dort).
- `src/youtube_code/step2_baseline_channels/` — COMPLETE_PROCESS.md Schritt 2:
  longitudinales Politik-Screening zur Bestimmung der Vor-/Nachkriegs-
  Baseline-Fenster je Kanal (siehe `README.md` dort für den detaillierten
  Ablauf; nutzt die geteilte Batch-Infrastruktur in
  `src/youtube_code/llm_analysis/`).
- `src/youtube_code/politics_screening/` — **existiert nicht mehr**: alle
  aktuellen Skripte sind nach `step2_baseline_channels/` verschoben; die
  restlichen, nicht in der Kurzreferenz-Pipeline geführten Skripte (Ad-hoc-/
  Diagnose-Skripte) liegen jetzt unter
  `src/youtube_code/archive/politics_screening_legacy/`.
- `src/youtube_code/step3_war_videos/` — COMPLETE_PROCESS.md Schritt 3:
  Keyword-basierte Themen-Relevanz-Klassifikation (`classify_topic_relevance.py`,
  Keyword-Quelle `topic_keywords.py`, Boilerplate-Filter `boilerplate.py`),
  schreibt in die Tabelle `video_topic_relevance` in `video_registry.sqlite`
  (siehe `README.md` dort für Details).
- `src/youtube_code/step4_transcript_download/` — COMPLETE_PROCESS.md
  Schritt 4: Zielauswahl für den Transkript-Download (`select_targets.py`,
  drei Konfigurationen: Baseline/Zell-Auffüllung/Kriegszeitraum) und der
  eigentliche Download (`download_transcripts.py`), verbunden über
  `run_transcript_selection.py` (siehe `README.md` dort für Details).
- `src/youtube_code/step5_segment_analysis/` — COMPLETE_PROCESS.md Schritt 5:
  Transkriptsegment-Kodierung per LLM (`segment_prompts_simple.py`,
  `process_scraped_segments.py`, `submit_segments.py`,
  `download_segments_simple.py`; siehe `README.md` dort für Prompts,
  Prüfspalten und offene Punkte).
- `src/youtube_code/llm_analysis/` — gemeinsame Infrastruktur für
  LLM-Batch-Jobs (Einreichung, Download, Registry-Anbindung).
- `src/youtube_code/archive/` — abgelöster/toter Code, nicht mehr gepflegt,
  aber aus Referenzgründen nicht gelöscht.
- `scripts/adhoc/` — einmalige, projektspezifische Skripte (u. a. die
  Migrationsskripte der Store-Umstellung, Phase 3). Neue Ad-hoc-Skripte
  gehören ebenfalls hierher, nicht lose in `src/youtube_code/` (siehe
  `.claude/CLAUDE.md`).
- `scripts/archive/` — abgelöste Root-level-Skripte.

## Backups

- `_backups/` (git-ignoriert) — lokaler Mirror-Clone `git_mirror_2026-08-28.git`
  von vor dem Git-History-Rewrite (Phase 2). Spiegelt nur den damaligen
  Git-Stand, **nicht** die aktuelle `data/store/`-Struktur (die Stores waren
  zu dem Zeitpunkt noch nicht git-ignoriert bzw. lagen noch unter `data/raw/`).
- Für `data/store/*.sqlite` selbst existiert **kein Git-Backup** (bewusst
  ausgeschlossen, siehe oben) — Sicherung liegt in der Verantwortung des
  Nutzers, z. B. per `sqlite3 <db> ".backup <ziel>"` oder Datei-Sync auf ein
  externes Medium.

## Weiterführende Dokumentation

- `.claude/CLAUDE.md` — verbindliche Session-Regeln (u. a. Transkript-Prüfung,
  Ad-hoc-Skript-Ablage).
- `.claude/restructuring/RESTRUCTURING_PROGRESS.md` — Verlauf und
  Abschluss-Zusammenfassung der Repo-Restrukturierung.
- `src/youtube_code/step1_sample/README.md` — Kurzreferenz für Schritt 1
  (Sample-Sammlung und -Definition).
- `src/youtube_code/step2_baseline_channels/README.md` — Politik-Screening-
  Pipeline im Detail: wie das Vorkriegs-/Postwar-Baseline-Fenster pro Kanal
  festgelegt wird, der Schritt-für-Schritt-Ablauf zum Hinzufügen neuer Kanäle
  und wie man die Video-IDs qualifizierender Kanäle abruft.
- `src/youtube_code/step3_war_videos/README.md` — Keyword-Quelle,
  Boilerplate-Filter und Tabellen-Schema der Themen-Relevanz-Klassifikation.
- `src/youtube_code/step4_transcript_download/README.md` — die drei
  Zielauswahl-Konfigurationen und `download_transcripts()`.
- `src/youtube_code/step5_segment_analysis/README.md` — Segment-Klassifikations-Pipeline.

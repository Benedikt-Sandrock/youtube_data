# Restrukturierungsplan: YouTube-Datenprojekt

## Context

Das Projekt ist über mehrere Analysephasen gewachsen (Kanal-/Video-Sammlung → Politik-Screening → LLM-basierte Segment-Klassifikation), wobei sich für ähnliche Aufgaben immer wieder neue, parallele Datei-Kopien und teils parallele Skript-Pipelines angesammelt haben, statt bestehende zu erweitern. Das Ergebnis ist ein 42,5-GB-Repository mit drei konkreten, vom Nutzer benannten Problemen:

1. **Unübersichtlichkeit** – viele Ordner mit Ergebnissen/Daten/Code, die stark vermischt sind (Ad-hoc-Skripte direkt in Daten-/Output-Ordnern, zwei gleichnamige `llm_analysis`-Verzeichnisse, `scripts/` überlappt funktional mit `src/youtube_code/`).
2. **Datenduplikate** – dieselben oder sehr ähnliche Datensätze liegen mehrfach vor, oft als JSON/JSONL/CSV-Vollkopien statt als eine zentrale Quelle mit Filter-Zugriff (z. B. 6 überlappende "sample_50k_channels"-Dateien, 19 GB fast identische State-Backup-Snapshots, 4 konkurrierende Transkript-Dateien).
3. **Performance bei großen Dateien** – mehrere Kern-Dateien sind mehrere GB groß (CSV mit eingebetteten Zeilenumbrüchen, JSONL ohne Index), was Einlesen/Ändern spürbar verlangsamt.

Eine umfassende Codebase-Exploration (3 parallele Recherchen zu Gesamtstruktur/Größen, Code-Architektur und Datendateien) hat die konkreten Ursachen identifiziert; dieser Plan adressiert sie in einer Reihenfolge, die jederzeit unterbrochen und in einer späteren Session fortgesetzt werden kann. Der Nutzer hat vier Leitplanken explizit festgelegt:

- Backup-Snapshots: **aggressiv aufräumen** (nur 1–2 letzte State-Snapshots behalten).
- Git-History: **bereinigen** (z. B. `git-filter-repo`), inkl. Sicherheitscheck vor dem Rewrite.
- Datenformat: **vollständige Migration** der Kern-Daten in SQLite/Parquet einplanen.
- Ausführung: **nur Plan liefern** – der Nutzer setzt ihn selbst um, mit Unterstützung in späteren Sessions; repetitive Schritte können an Claude übergeben werden.

Das bestehende Pattern in `src/youtube_code/utils/video_registry.py` (SQLite-Registry mit `upsert_videos`/COALESCE-Merge/`export_jsonl`-Snapshot) ist bereits genau das Zielmuster für "zentrale Sammeldatei + Konfiguration statt Datei-Kopien" und wird erweitert statt neu erfunden. Ebenso ist `src/youtube_code/config/paths.py` das bestehende zentrale Config-Modul (`ROOT`, `DATA`, `OUTPUTS`, Unterordner-Konstanten), das um Store-Pfade ergänzt wird; aktuell enthält es bereits Drift (`REPORTS`, `GRAPHS` referenzieren nicht existierende Ordner).

## Zielstruktur

```
data/
  raw_archive/        # unveränderte API-Rohdumps (read-only nach Schreiben)
  store/              # ZENTRALE Sammeldateien — Single Source of Truth
    videos.sqlite         # Erweiterung von video_registry.sqlite (+ Detail-Tabelle, + Sample-Zugehörigkeit als Spalten/Tabelle statt Kopie-Dateien)
    transcripts.parquet   # oder SQLite-Tabelle; Ersatz für all_transcripts_segments.csv + Varianten
    screening_state.sqlite  # Ersatz für longitudinal_screening_state.csv + Vollkopie-Backups
    llm_runs.sqlite        # konsolidierte Run-Registry (Ersatz für 3 CSV-Varianten + verstreute Kopien)
  channel_lists/, external/, exploration/   # bleiben, kuratiert

outputs/
  llm_results/<run_id>/   # NICHT regenerierbare, bezahlte Batch-Ergebnisse, referenziert aus llm_runs.sqlite
  reports/                 # regenerierbare Analyse-Exporte, jederzeit lösch-/neu erzeugbar
  _cache/                  # regenerierbare Snapshots (z.B. all_videos.jsonl-Export), .gitignore't

src/youtube_code/
  config/    # paths.py, settings.py — erweitert um Store-Pfade
  store/     # NEU: video_store.py, transcript_store.py, screening_store.py, run_registry.py (Muster von video_registry.py)
  collection/, scraping/, politics_screening/, llm_analysis/, segment_analysis/, new_analysis/, archive/
  # new_analysis/out_screening, out_segments: keine Daten mehr im Source-Tree

scripts/
  adhoc/     # alle Ad-hoc/"sample.py"-artigen Skripte, sprechend benannt, nie in data/outputs/src
```

**Verhinderungsregel:** Kein Skript schreibt künftig direkt in `data/`/`outputs/`, ohne über eine Funktion aus `youtube_code.store` zu gehen; Ad-hoc-Analysen landen ausschließlich in `scripts/adhoc/`.

## Phasenplan

Jede Phase ist einzeln in einer späteren Session ausführbar (klarer Ein-/Ausgangszustand). Reihenfolge nach Abhängigkeit und Risiko:

| Phase | Abhängig von | Nutzen | Risiko |
|---|---|---|---|
| 0a Vorbereitung (platzneutral) | — | Absicherung | gering |
| 1 Datenbereinigung | 0a | sehr hoch (~25+ GB, macht 0b/Phase 2 erst möglich) | gering–mittel |
| 0b Physische Sicherung | 1 (Platz muss erst frei sein) | Absicherung für Phase 2 | gering |
| 2 Git-History-Rewrite | 0b | hoch (Repo-Größe) | mittel–hoch, irreversibel ohne Backup |
| 3 Format-Migration (a–d, einzeln je Datentyp) | 1 | hoch (Kernziel 2+3) | mittel |
| 4 Code-Reorganisation | 3 | mittel–hoch (Kernziel 1) | mittel |
| 5 Konfiguration/Doku | 3+4 | hoch für Nachhaltigkeit | gering |

### Phase 0 — Sicherheitsnetz (angepasst wegen Platzmangel)

**Ausgangslage:** Auf dem Gerät sind aktuell nur ~5,1 GB frei (237 GB Gesamtgröße, 232 GB belegt), keine externe Festplatte verfügbar. Ein vollständiges lokales Backup (data/ + outputs/ ≈ 42,5 GB, .git ≈ 12 GB) VOR jeder Aktion ist damit nicht machbar. Da die meisten großen Duplikat-Kandidaten aus Phase 1 **nicht in Git getrackt sind** (reine Working-Tree-Dateien), hat ihr Löschen keinen Einfluss auf die Git-History — die Reihenfolge wird daher umgestellt: erst die platzneutrale Verifikation, dann die risikolosen Löschungen (Phase 1), erst danach die eigentliche physische Sicherung, sobald genug Platz frei ist.

**0a. Platzneutrale Vorbereitung (kein zusätzlicher Speicher nötig):**
1. Committer-Check: `git log --format='%ae' | sort -u` dokumentieren (Erwartung: nur bekannte Adressen) — wichtig, da Phase 2 die History für jeden Klon bricht.
2. Für jede in Phase 1 zur Löschung vorgesehene Datei: Checksum (PowerShell `Get-FileHash`) und/oder Zeilenzahl bilden und gegen die jeweils **behaltene** Datei vergleichen (nicht extern gesichert, da die behaltene Datei selbst die Absicherung ist — per Nutzerentscheidung reicht Verifikation ohne zusätzliche Kopie bei nachweislichen 1:1-Duplikaten).
3. Aktuellen freien Speicherplatz dokumentieren (Referenzwert für die Prüfung nach Phase 1).

**Verifikation 0a:** Committer-Liste dokumentiert; Checksum-/Zeilen-Vergleich für jede Löschkandidat-Datei zeigt eindeutige Redundanz zur behaltenen Datei.

**0b. Physische Sicherung (nach Phase 1, sobald Platz frei ist):**
1. Nach Abschluss von Phase 1 (~25 GB freigeworden) lokalen `git clone --mirror` bzw. `git bundle create` der `.git` (~12 GB) anlegen — passt jetzt in den freigewordenen Platz. Im Mirror zusätzlich `git lfs fetch --all`, sonst fehlen LFS-Objekte.
2. Diesen lokalen Mirror/Bundle in den bestehenden GCP-Bucket hochladen (`GCP_BUCKET_NAME`/`GCP_PROJECT_ID` aus `config/settings.py` — derselbe Bucket wie für die Gemini-Batch-Jobs, ~1 USD/Monat für 40+ GB), danach lokal löschen, um den Platz wieder freizugeben.
3. Die kleinen, nicht regenerierbaren bezahlten LLM-Ergebnisse (`outputs/segment_analysis/` ~93 MB, `outputs/llm/` ~213 MB, zusammen ~300 MB) ebenfalls in den GCP-Bucket hochladen — unabhängig vom Platzproblem, da sie klein genug sind.

**Verifikation 0b:** Hochgeladener Mirror lässt sich aus dem Bucket herunterladen und öffnen; Objekt-Anzahl/Größe im Bucket ≈ lokale Quelle; lokaler Mirror/Bundle danach gelöscht, Speicherplatz wieder frei.

### Phase 1 — Datenbereinigung eindeutiger Duplikate (~25+ GB)

**Läuft vor der physischen Sicherung (0b)** — abgesichert durch die Verifikation aus 0a, nicht durch eine zusätzliche externe Kopie, da es sich um nachweisliche 1:1-Duplikate handelt und die behaltene Datei selbst die Absicherung ist. Ziel dieser Phase ist unter anderem, genug Speicherplatz für 0b/Phase 2 freizumachen.

Reihenfolge nach Risiko, aufsteigend:

- **State-Backups**: `data/samples/russia/batches_longitudinal/state_backups/*` (15–16 × ~1,25 GB ≈ 19 GB) — nur letzte 1–2 behalten, Rest löschen. Ebenso `longitudinal_screening_state.csv.bak_pre_37channels` und `.csv.before_postwar_assignment.csv` (je 1,25 GB), falls nicht als einzige Quelle für einen sonst nicht rekonstruierbaren Zwischenstand nötig. Vor Löschung: Zeilenzahl jeder Backup-Datei gegen die aktuelle State-Datei vergleichen (aktuelle muss Obermenge/Fortführung sein) + Checksum-Abgleich gegen Phase-0-Liste.
- **Tote Transkript-Formate** (per `.claude/CLAUDE.md`-Regel: nur `all_transcripts_segments.csv` ist Source of Truth): `all_transcripts_backup.csv` (2,65 GB, nach Stichproben-Diff-Bestätigung löschen), `all_transcripts.csv` (405 MB), `all_transcripts_2.csv` (38,7 MB), `single_transcripts.csv` (764 KB).
- **"sample_50k_channels"-Familie**: je Datei per `grep -r "<dateiname>" src/ scripts/` den Referenzstatus klären, dann `data/raw/videos_total.json` (417 MB, toter Pfad `../JSON Files/...`), `data/raw/sample_russia_ukraine.json` (306 MB, unreferenziert, fehlerhaft in LFS getrackt), die unreferenzierte `.jsonl`-Variante (191 MB) löschen; `video_registry.sqlite` und `sample_50k_channels_russia_ukraine.json` behalten (werden in Phase 3 migriert).
- **`outputs/sample_feasibility/videos_clean.jsonl`** (1,26 GB) ist ein reserialisiertes 1:1-Duplikat von `data/samples/russia/sample_50k_channels_russia_ukraine_wo_shorts.jsonl`: Smoke-Test, dass `new_analysis/feasibility.py` es korrekt neu erzeugt, dann als Cache behandeln/löschen.
- **Verstreute Ad-hoc-Skripte** in Daten-/Output-Ordnern (`data/raw/sample.py`, `outputs/segment_analysis/sample.py`, `src/youtube_code/new_analysis/out_screening/sample.py`, `src/youtube_code/segment_analysis/sample.py`, `src/youtube_code/segment_analysis/temp.csv` u. a., insgesamt 21 Fundstellen): sichten, nach `scripts/adhoc/` verschieben oder löschen.

**Verifikation:** `du -sh data/ outputs/` vor/nach (erwarteter Rückgang ≥ 25 GB); Kern-Skripte laufen mit `DRY_RUN=True` weiterhin fehlerfrei.

### Phase 2 — Git-History bereinigen

1. `git-filter-repo` installieren; großen-Blobs-Analyse (`git-filter-repo --analyze` oder `git rev-list --objects --all` + `cat-file --batch-check`) für auch inzwischen umbenannte/gelöschte Pfade.
2. `.gitattributes` reparieren (Tippfehler `diff=lfd`→`diff=lfs`, doppelte Zeile für `all_transcripts.csv` entfernen) und Grundsatzentscheidung: großes Rohdaten künftig ganz aus Git heraushalten (empfohlen) statt LFS weiter zu pflegen.
3. Mit `git-filter-repo --path ... --invert-paths` bzw. `--strip-blobs-bigger-than` historische große Blobs entfernen (inkl. Vorgängerversionen der in Phase 1 gelöschten Dateien).
4. `git lfs prune` (+ Remote-seitige LFS-Bereinigung, providerabhängig).
5. Force-Push auf allen Branches/Tags — **nur nach expliziter Bestätigung**, da destruktiv für alle Klone.
6. `.gitignore` erweitern: `data/store/*.sqlite`, `data/store/*.parquet`, ggf. `outputs/llm_results/` dauerhaft ausschließen.

**Verifikation:** `du -sh .git` vor/nach (Ziel: deutlich < 1 GB); `git fsck` fehlerfrei; frischer Klon lässt sich normal auschecken, `git log --all -- src/` zeigt weiterhin sinnvolle Code-Historie; Test-Clone mit `pip install -e .` + Kern-Skript-Lauf.

### Phase 3 — Datenformat-Migration je Datentyp

Jeder Teilschritt einzeln ausführbar, mit Vorher/Nachher-Verifikation (Zeilenzahl, eindeutige IDs, Stichproben-Hash) vor jeder Löschung der Alt-Datei:

- **3a Video-Metadaten → `data/store/videos.sqlite`**: Erweiterung der bestehenden `videos`-Tabelle aus `video_registry.py` um `video_metadata_detailed` (description/tags/counts) und Sample-Zugehörigkeit (`video_sample_membership(video_id, sample_name)` oder Bool-Spalten wie `is_shorts`). Import-Reihenfolge: `video_metadata_total.jsonl`, `video_metadata_detailed_total.jsonl`, `sample_50k_channels_russia_ukraine_wo_shorts.jsonl`, `sample_50k_channels_russia_ukraine.json`, Dedupe auf `video_id` per COALESCE (bestehendes Muster).
- **3b Transkripte → `data/store/transcripts.parquet`** (oder SQLite mit Index auf `video_id`): ausschließlich aus `all_transcripts_segments.csv`. Vor Umsetzung kurz entscheiden: SQLite (konsistent mit übrigem Store, einfache `WHERE video_id IN (...)`) vs. Parquet (schneller für spaltenweise Batch-Analysen).
- **3c Screening-State → `data/store/screening_state.sqlite`**: `longitudinal_screening_state.csv` importieren; künftige Runs schreiben per Upsert statt CSV-Vollkopie — das behebt strukturell die Ursache der 19-GB-Backup-Flut. Optional: schlanke `screening_state_history`-Tabelle (nur geänderte Felder + Zeitstempel/`run_id`) als Diff-Backup statt Vollkopien.
- **3d LLM-Run-Ergebnisse → `data/store/llm_runs.sqlite` + `outputs/llm_results/<run_id>/`**: die drei Registry-Varianten (`runs_registry.csv`, `_legacy`, `_old`, plus die abweichende Top-Level-Kopie unter `llm_analysis/registry/`) zu einer Tabelle zusammenführen (`run_id, pipeline, status, input_path, output_path, created_at`). Physische Ergebnisse je Run konsolidieren; da bezahlte, nicht günstig reproduzierbare Daten: **konservativ vorgehen**, im Zweifel behalten statt löschen, Einzelfälle mit Nutzer absprechen statt automatisch zu bereinigen.

**Verifikation je Teilschritt:** kleines Validierungsskript (`scripts/adhoc/verify_migration_<typ>.py`), das Zeilenzahlen/Checksums Alt- vs. Neu vergleicht und explizit OK/MISMATCH meldet; alte Dateien erst nach OK für alle vier Typen als Löschkandidat markieren.

### Phase 4 — Code-Reorganisation und Pipeline-Konsolidierung

1. `src/youtube_code/store/` anlegen (`video_store.py`, `transcript_store.py`, `screening_store.py`, `run_registry.py`) nach dem Muster von `video_registry.py`; dieses wird Wrapper oder wird ersetzt.
2. `utils/io.py` schrittweise auf Store-Aufrufe umstellen statt eigener JSON/JSONL-Boilerplate.
3. `politics_screening/legacy/` vs. `longitudinal/`: Nutzungsstand per `git log` klären, dann archivieren oder Koexistenz explizit dokumentieren.
4. Die zwei divergierenden Registry-Pfade (`politics_screening/screening_config.py` vs. `segment_analysis/segment_analysis_config.py`) auf denselben, aus Phase 3d konsolidierten Pfad umstellen; Top-Level `llm_analysis/`-Ordner danach löschen.
5. `run_politics_screening_batch.py`/`run_longitudinal_screening_batch.py` (675/673 Zeilen, nur Default-Konstanten unterschiedlich) zu einer parametrisierten Funktion zusammenführen.
6. Import-Konsistenz herstellen: einheitlich `from youtube_code.X import Y`, keine `from src.youtube_code...` oder nackten sibling-Importe (`from settings_variables import ...`).
7. Verbleibende Ad-hoc-Skripte nach `scripts/adhoc/` verschieben; `scripts/` vs. `src/youtube_code`-Überlappungen (z. B. `scripts/old/channel_activity_over_time.py` vs. `archive/outcome_analysis/activity_over_time_updated.py`) je Paar auflösen.
8. Kaputte Pfade reparieren oder als deprecated markieren: `collection/video_sampling.py`, `collection/comment_download.py` (`../JSON Files/...`).
9. Optional, größerer Schritt: `# CONFIG`-Blöcke schrittweise durch argparse/YAML ersetzen, beginnend beim meistgenutzten Batch-Runner.

**Verifikation:** `python -c "import youtube_code"` + Subpackage-Importe aus sauberem `.venv`; End-to-End-Dry-Run je geänderter Pipeline; `grep -r "runs_registry_old\|runs_registry_legacy\|JSON Files" src/` liefert keine Treffer mehr.

### Phase 5 — Konfiguration und Dokumentation (Abschluss)

1. `config/paths.py` bereinigen: `STORE`-Pfade ergänzen, `REPORTS`/`GRAPHS`-Drift auflösen (Ordner anlegen oder Konstanten entfernen); optionales `paths_check.py` warnt bei fehlenden referenzierten Ordnern.
2. Root-`README.md`: Kurzüberblick über Ordnerstruktur, Verweis auf `.claude/CLAUDE.md` und die bestehenden Sub-READMEs.
3. `.claude/CLAUDE.md` aktualisieren: Transkript-Regel auf `data/store/transcripts.*` ändern, neue Regel "keine Ad-hoc-Skripte/Daten außerhalb von `scripts/adhoc/`" ergänzen.
4. `.gitignore` final durchgehen (Store-Dateien, `_cache/` konsequent ausgeschlossen); externe Backup-Strategie für `data/store/` dokumentieren (z. B. `sqlite3 .backup`/rsync statt Git).
5. Kurze Migrations-Zusammenfassung dokumentieren (was wurde wann gelöscht/migriert, wo liegt das Vor-Migration-Backup aus Phase 0).

**Verifikation:** Eine neue Session kann allein anhand README + CLAUDE.md + `config/paths.py` die Datenlage verstehen, ohne den Verlauf dieser Restrukturierung zu kennen.

## Kritische Dateien (Referenz für spätere Umsetzung)

- `src/youtube_code/utils/video_registry.py` — Zielmuster für alle Store-Module.
- `src/youtube_code/utils/io.py` — wird schrittweise auf Store-Aufrufe umgestellt.
- `src/youtube_code/config/paths.py` — zentrale Pfad-Konfiguration, wird um Store-Pfade erweitert.
- `.gitattributes` — kaputtes LFS-Setup, in Phase 2 zu reparieren.
- `src/youtube_code/llm_analysis/registry/run_registry.py` — Basis für konsolidierte `run_registry.py` in Phase 3d/4.
- `src/youtube_code/politics_screening/screening_config.py`, `src/youtube_code/segment_analysis/segment_analysis_config.py` — divergierende Registry-Pfade, in Phase 4 zu vereinheitlichen.

## Session-Wiedereinstieg zwischen den Phasen

Empfehlung: **eine Session pro Phase**, bei Phase 3 (Format-Migration) sogar **eine Session pro Teilschritt (3a–3d)**, da jeder unabhängig verifizierbar ist und Migrationsfehler bei GB-großen Dateien sonst schwer auseinanderzuhalten sind. Phase 2 (Git-History-Rewrite) sollte immer isoliert laufen, ohne parallele Aufräum-/Code-Arbeit in derselben Session.

- **Fortschritts-Tracking:** Eine kleine Datei `RESTRUCTURING_PROGRESS.md` im Repo führen (Status je Phase/Teilschritt, Datum, Besonderheiten). Sie ist die Quelle, die zu Sessionbeginn genannt wird — zusammen mit dieser Plan-Datei ergibt das den vollständigen Kontext, ohne dass der Stand aus dem Gedächtnis rekonstruiert werden muss. Fortschritt wird über den tatsächlichen Repo-/Git-Zustand verifiziert (`du -sh`, `git status`, Existenz der Store-Dateien), nicht nur behauptet.
- **Plan Mode je Session:** aktivieren, wenn am Anfang noch eine Entscheidung für den anstehenden Teilschritt aussteht (insbesondere Phase 2, Phase 3-Design, Phase 4-Merges); bei rein mechanischer Ausführung eines bereits im Detail abgesegneten Schritts reicht normaler Modus mit expliziter Bestätigung vor der eigentlichen destruktiven Aktion (Löschen, Force-Push).
- **Sessionstart:** Plan-Datei-Pfad nennen, aktuelle Phase/Teilschritt benennen, Stand laut `RESTRUCTURING_PROGRESS.md` mitgeben, und erwähnen, falls seit der letzten Session außerhalb dieses Plans etwas am Repo verändert wurde (sonst wird vor dem Weitermachen der Zustand verifiziert statt blind auf altem Stand aufgesetzt).

## Verifikationsstrategie insgesamt

- Vor jeder Löschung: Checksum/Zeilenzahl-Vergleich gegen Phase-0-Referenzliste.
- Nach jeder Migration: dediziertes Verify-Skript mit OK/MISMATCH-Ausgabe, nie "sieht plausibel aus" als Kriterium.
- Nach jeder Code-Änderung: sauberer `.venv`-Import-Test + Dry-Run der betroffenen Pipeline.
- Nach Phase 2: Test-Clone in separatem Verzeichnis, `pip install -e .`, Kern-Skript ausführen.

# Phase 5 — Konfiguration und Dokumentation (Plan)

## Context

Phase 4 (Code-Reorganisation) ist laut `RESTRUCTURING_PROGRESS.md` vollständig abgeschlossen (4a–4e). Phase 5 ist laut `RESTRUCTURING_PLAN.md` der Abschlussschritt: Konfiguration bereinigen und Dokumentation nachziehen, damit eine neue Session die Datenlage allein anhand README + CLAUDE.md + `config/paths.py` versteht, ohne den Restrukturierungsverlauf zu kennen.

**Wichtige Änderung seit dem letzten Progress-Eintrag:** Zu Beginn dieser Session hat der Nutzer die 4 SQLite-Stores manuell von `data/raw/` nach `data/store/` verschoben (entspricht der ursprünglichen Zielstruktur des Plans). Das macht zwei Dinge, die ohnehin in Phase 5 fällig waren, jetzt akut:

1. Die 4 Store-Module (`src/youtube_code/store/{video_registry,transcript_store,screening_state_store,llm_run_store}.py`) definieren aktuell `DB_PATH = RAW / "<name>.sqlite"` — zeigt seit der manuellen Verschiebung ins Leere. **Der gesamte in Phase 4 migrierte Store-Zugriffscode ist dadurch aktuell funktionsunfähig**, nicht nur unschön.
2. `data/store/screening_state.sqlite` (1,7 GB) steht **aktuell im Git-Index als "A" (staged)**, `.gitignore` hat keinen Eintrag für `data/store/*.sqlite`. Ein versehentlicher `git commit` würde die 13-GB-Problematik reproduzieren, die Phase 2 mit dem History-Rewrite gerade behoben hat.

Phase 5 beginnt daher mit diesen zwei Sofortmaßnahmen, bevor der ursprünglich geplante Doku-/Config-Teil folgt.

## Schritt 1 — Store-Pfade reparieren (zuerst, dringend)

- `src/youtube_code/config/paths.py`: neue Konstante `STORE = DATA / "store"` ergänzen.
- In den 4 Store-Modulen `DB_PATH = RAW / "<name>.sqlite"` → `DB_PATH = STORE / "<name>.sqlite"` (Import von `RAW` durch `STORE` ersetzen). Kein Call-Site außerhalb der 4 Module betroffen, da alle Consumer ausschließlich über Funktionen gehen (`get_state()`, `upsert_transcripts()` usw.), nie über `DB_PATH` direkt.
- `REPORTS`/`GRAPHS`-Drift zugleich auflösen: beide Konstanten sind laut `grep -rn "REPORTS\|GRAPHS" src/ scripts/` komplett unreferenziert → entfernen.
- `ACTIVITY`-Konstante wird nur noch von den bereits archivierten `archive/outcome_analysis/activity_over_time_updated.py` und `scripts/archive/channel_activity_over_time.py` referenziert — in der Ausführungssession kurz beim Nutzer nachfragen, ob diese Archiv-Skripte noch laufen sollen (Konstante behalten) oder nicht (Konstante ebenfalls entfernen), statt das anzunehmen.
- Optional (aus dem Ursprungsplan): kleines `paths_check.py`, das beim Import prüft, ob alle referenzierten Ordner existieren, und warnt statt zu crashen.

## Schritt 2 — Git-Absicherung (direkt danach, vor jedem Commit)

- `.gitignore` ergänzen: `/data/store/*.sqlite` sowie `*.sqlite-wal` / `*.sqlite-shm` (alle 4 Module laufen im WAL-Modus, Sidecar-Dateien können jederzeit entstehen).
- Die aktuell gestagte `data/store/screening_state.sqlite` per `git restore --staged data/store/screening_state.sqlite` wieder aus dem Index nehmen — **nicht committen**.
- Verifikation: `git status` darf danach keine der 4 `.sqlite`-Dateien mehr als `A`/`??` zeigen.

## Schritt 3 — `.claude/CLAUDE.md` aktualisieren

- Transkript-Verfügbarkeitsregel von `data/transcripts/all_transcripts_segments.csv` (in 4c gelöscht) auf den `transcript_store`/`data/store/transcripts.sqlite` ändern (z. B. `attempted_video_ids()`/`get_transcripts()` als maßgebliche Prüfung nennen).
- Neue Regel ergänzen: keine Ad-hoc-Skripte/Daten außerhalb von `scripts/adhoc/` — das ist die im Ursprungsplan als "Verhinderungsregel" formulierte Leitplanke, bisher aber nirgends als tatsächliche CLAUDE.md-Regel verankert.

## Schritt 4 — Root-`README.md` erstellen (existiert aktuell gar nicht)

Kurzüberblick über die Ordnerstruktur, u. a.:
- `data/store/` — die 4 SQLite-Stores, Single Source of Truth.
- `data/raw/`, `channel_lists/`, `samples/`, `external/`, `exploration/` — kuratierte/rohe Zulieferdateien, nicht die Wahrheit.
- `outputs/llm_results/<source>__<run_id>/` — bezahlte, nicht regenerierbare LLM-Ergebnisse.
- `outputs/reports/`, `_cache/` — regenerierbar, jederzeit löschbar.
- `scripts/adhoc/` — Einmal-/Ad-hoc-Skripte.
- `src/youtube_code/store/` — zentrale Zugriffsschicht (Muster: `video_registry.py`).

Verweis auf `.claude/CLAUDE.md` sowie die bestehenden Sub-READMEs (`README_ADD_NEW_CHANNELS.md`, `README_PIPELINE.md`, `segment_analysis/README.md`).

## Schritt 5 — Sub-READMEs korrigieren

- **`src/youtube_code/politics_screening/README_PIPELINE.md`**: Die Skript-Tabelle nennt 4 Namen, die es so nicht mehr gibt — `create_longitudinal_screening_round.py`, `update_longitudinal_state.py`, `select_longitudinal_transcripts.py`, `analyze_longitudinal_coverage.py` (vermutlich Altlast einer früheren Umbenennung, unabhängig von der Store-Migration; `create_longitudinal_screening.py` und `update_screening_state.py` sind die bekannten aktuellen Namen, die anderen zwei in der Ausführungssession per Verzeichnis-Scan/`git log --follow` klären).
- **`README_ADD_NEW_CHANNELS.md`**: laut Progress bereits in 4e aktualisiert — nur stichprobenartig gegenprüfen.
- **`segment_analysis/README.md`**: referenziert nur Handkodierungs-CSVs (Inter-Rater-Workflow), keine Store-relevanten Pfade gefunden — vermutlich unverändert lassen, kurz gegenprüfen.

## Schritt 6 — Offene Altlasten-Rückfragen ("alt heißt nicht automatisch tot")

Diese in der Ausführungssession **nicht unilateral** archivieren/löschen, sondern einzeln beim Nutzer rückfragen (Standing-Regel, siehe `project-restructuring-decisions`-Memory):
- `src/youtube_code/scraping/transcript_scraping.py` — Vorgänger-Scraper, vermutlich tot (in 4c gefunden, nicht angefasst).
- `src/youtube_code/politics_screening/longitudinal/prepare_longitudinal_screening.py` — Bootstrap-Skript, seit der Store-Migration nicht mehr sinnvoll ausführbar, wird aber noch in `README_PIPELINE.md` referenziert (siehe Schritt 5).
- `data/external/media_type_russia_merged.xlsx.bak` (31 KB) — keine Code-Referenz, unklarer Zweck.

## Schritt 7 — Migrations-Zusammenfassung / Abschluss

- Kurzen zusammenfassenden Abschnitt an `RESTRUCTURING_PROGRESS.md` anhängen: was wurde insgesamt gelöscht/migriert, wo liegt das Vor-Migrations-Backup (Phase 0b, `_backups/git_mirror_2026-08-28.git` — mit Hinweis, dass dieser Mirror nur den Git-History-Stand vor Phase 2 spiegelt, nicht die aktuelle `data/store/`-Struktur).
- Externe Backup-Strategie für `data/store/` dokumentieren (liegt jetzt außerhalb von Git, da per `.gitignore` ausgeschlossen) — z. B. `sqlite3 .backup`/rsync, da sonst kein Sicherungsmechanismus mehr für die jetzt zentralen Store-Dateien existiert.

## Verifikation

- `python -c "from youtube_code.store import video_registry, transcript_store, screening_state_store, llm_run_store"` fehlerfrei; `total_count()` je Store liefert die aus Phase 3 bekannten Referenzwerte (2.307.005 / 72.443 / 1.012.206 / 83) — bestätigt, dass die Pfad-Reparatur die bestehenden Daten wiederfindet statt leere DBs anzulegen.
- `git status` zeigt keine `.sqlite`-Datei mehr als `A`/`??`.
- `grep -rn "REPORTS\|GRAPHS\|ACTIVITY\b" src/ scripts/` liefert nur noch die bewusst belassenen Referenzen (falls `ACTIVITY` laut Nutzerentscheidung bleibt).
- Eine neue Session versteht die Datenlage allein anhand `README.md` + `.claude/CLAUDE.md` + `config/paths.py` (ursprüngliches Verifikationsziel des Gesamtplans).

## Hinweis zur Ausführung

Passend zur Standing-Entscheidung des Nutzers ("nur Pläne liefern, Ausführung erfolgt selbst oder auf expliziten Auftrag in einer späteren Session") liefert diese Session nur den Plan. Schritt 1+2 (Store-Pfad-Fix + Git-Absicherung) sollten in der nächsten Sitzung als Allererstes erledigt werden, unabhängig vom Rest der Phase — solange die Pfade falsch zeigen, ist jeder store-basierte Codepfad im Repo faktisch defekt, und die 1,7-GB-Datei bleibt bis dahin ein Commit-Risiko.

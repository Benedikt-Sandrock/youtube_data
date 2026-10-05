# Plan: Phase 4 — Code-Reorganisation und Pipeline-Konsolidierung

## Status (Stand 2026-08-31)

**Teilschritt 4a ist abgeschlossen** — ausgeführt auf expliziten
Ausführungsauftrag (Abweichung von der sonst geltenden "nur Pläne
liefern"-Regel für diese eine Sitzung). Vollständige Details, Verifikation
und die zwei bewusst offen gelassenen Punkte stehen im Abschnitt "Phase 4a"
von `.claude/restructuring/RESTRUCTURING_PROGRESS.md` — dort nachlesen statt
hier zu duplizieren. Kurzfassung: ~5,8 GB Backups/tote Sample-Datei gelöscht,
`legacy/`, `collection/{video_sampling,comment_download}.py` und alle 12
Dateien aus `scripts/old/` per `git mv` nach `archive/` verschoben, 5×
`from src.youtube_code...` auf `from youtube_code...` vereinheitlicht, die
verbleibenden nackten Sibling-Importe (`settings_variables`,
`success_data_utils`, `deskriptiv_aggregation`/`fe_signifikanz_test`) bewusst
**nicht** auf relative Importe umgestellt (siehe "Neue Erkenntnisse" unten),
sondern im Docstring als Muster dokumentiert.

**Alle 4a-Änderungen liegen aktuell nur im Working Tree, noch nicht
committet** (Repo ist auf `main`; committet wird nur auf expliziten
Nutzerwunsch). Eine neue Session, die mit 4b beginnt, sollte das prüfen
(`git status`) und ggf. zuerst klären, ob/wie committet werden soll, bevor
weitere Dateien angefasst werden — sonst vermischen sich 4a- und
4b-Änderungen in einem Diff.

**Teilschritt 4b, Schritt 1 ist abgeschlossen** (2026-08-31, auf explizitem
Ausführungsauftrag bei knappem Session-Budget — Nutzer hat sich nach
Rückfrage für "nur Schritt 1" entschieden). Details und Verifikation stehen
in `RESTRUCTURING_PROGRESS.md` Abschnitt "Phase 4b, Schritt 1". Kurzfassung:
die 4 reinen Leser-Call-Sites (Punkt 1 unten) sind auf `llm_run_store`
umgestellt; `llm_run_store.get_runs()` wurde dabei **nicht** um `prompt_id`/
`dataset_version` als SQL-Filter erweitert, stattdessen wird an den
Call-Sites zusätzlich per Pandas nachgefiltert — bei Bedarf in Schritt 2–6
gegenprüfen, ob eine echte Store-Erweiterung sich mehr lohnt. **Änderungen
liegen nur im Working Tree, noch nicht committet.**

**Teilschritt 4b, Schritt 2–6 ist abgeschlossen** (2026-08-31, auf explizitem
Ausführungsauftrag direkt im Anschluss an Schritt 1). Details und
Verifikation stehen in `RESTRUCTURING_PROGRESS.md` Abschnitt "Phase 4b,
Schritt 2–6". Kurzfassung: alle verbleibenden Call-Sites (zentrale
Schreiber, `retry_run.py`/`update_screening_state.py`-Registry-Teil,
`segment_analysis_active`-Quelle, beide Configs) sind auf `llm_run_store`
umgestellt; dafür wurden `llm_run_store.add_run()`/`update_run()`/
`next_run_id()` als neue Store-Funktionen ergänzt (fetch-merge-upsert-
Semantik in `update_run()`, siehe Progress-Notiz); `download_segments.py`/
`download_segments_simple.py` wurden bewusst **nicht** zusammengelegt
(unterschiedliche Prompt-Module mit kollidierenden `prompt_key`-Schemata,
siehe Progress-Notiz); alle toten Registry-Dateien (`merge_and_evaluate.py`,
`src/youtube_code/llm_analysis/registry/`, Repo-Root-`llm_analysis/`) sind
archiviert bzw. gelöscht, nachdem sie 1:1 gegen `llm_runs.sqlite`
abgeglichen wurden. **Änderungen liegen weiterhin nur im Working Tree,
noch nicht committet** (zusammen mit Schritt 1 im selben Diff).

**Teilschritt 4c ist abgeschlossen** (2026-08-31, auf explizitem
Ausführungsauftrag — "führe Abschnitt 4c durch"). Details, Live-Smoke-Test
und Verifikation stehen in `RESTRUCTURING_PROGRESS.md` Abschnitt "Phase
4c". Kurzfassung: Kern-Scraper (`transcript_scraping_segments.py`) und alle
5 Downstream-Leser sind auf `transcript_store` umgestellt, der
CSV-Backup-Block ist ersatzlos gestrichen, `single_transcript_downloader.py`
ist archiviert. **Ein Punkt aus Schritt 4 bleibt offen**: Die
Löschung der beiden Alt-Dateien `data/transcripts/all_transcripts_segments.csv`
(2,8 GB) und `all_transcripts_backup.csv` (2,7 GB) wurde von der
automatischen Berechtigungs-Klassifizierung blockiert; der Nutzer hat sich
auf Rückfrage entschieden, sie selbst zu löschen, statt Claude einen
erneuten Versuch zu erlauben — eine neue Session sollte per `ls
data/transcripts/` prüfen, ob das bereits erfolgt ist. Zusätzlich wurde
`src/youtube_code/scraping/transcript_scraping.py` als vermutlich toter,
aber nicht im 4c-Plantext genannter Vorgänger-Scraper entdeckt und bewusst
nicht angefasst (siehe Progress-Notiz, Kandidat für Phase 5). **Änderungen
liegen weiterhin nur im Working Tree, noch nicht committet.**

**Teilschritt 4d, Schritte 1–5 sind abgeschlossen** (2026-08-31, auf
explizitem Ausführungsauftrag — "führe Abschnitt 4d aus"). Details,
Rückfrage-Ergebnis zu Schritt 4 und Verifikation stehen in
`RESTRUCTURING_PROGRESS.md` Abschnitt "Phase 4d". Kurzfassung: alle 4
Schreiber (`append_channels_to_state.py`, `create_longitudinal_screening.py`,
`assign_postwar_baseline.py`, `update_screening_state.py`) und der
`get_baseline_ids.py`-Leser sind auf `screening_state_store` umgestellt;
zusätzlich wurden die read-seitigen Call-Sites in beiden Batch-Runnern und
`retry_run.py` mitmigriert, damit sie nach der Schreiber-Umstellung nicht auf
einer veraltenden CSV weiterlaufen. **Schritt 6 (Batch-Runner-Merge) ist inzwischen ebenfalls abgeschlossen**
(2026-08-31, separate Sitzung, auf explizitem Ausführungsauftrag "führe
Schritt 6 durch") — Details in `RESTRUCTURING_PROGRESS.md` Abschnitt
"Phase 4d", Nachtrag zu Schritt 6. Kurzfassung: gemeinsame Logik nach
`src/youtube_code/llm_analysis/screening_batch_submission.py` extrahiert
(`submit_screening_batch()`, parametrisiert über `round_number`,
`period_column`, `period_noun`); `run_politics_screening_batch.py`/
`run_longitudinal_screening_batch.py` sind jetzt ~54-Zeilen-Wrapper mit nur
noch dem USER-CONFIG-Block. Ein neuer,
nicht im Plantext gelisteter Bootstrap-Kandidat
(`prepare_longitudinal_screening.py`) wurde bewusst nicht angefasst, analog
zum 4c-Fund `transcript_scraping.py` (Kandidat für Phase 5). **Änderungen
liegen nur im Working Tree, noch nicht committet** (4a–4c sind laut
Commit-Log bereits committet — der Plan-Text hier war insofern stale).

**Teilschritt 4d ist damit vollständig abgeschlossen (Schritte 1–6).**

**Teilschritt 4e ist ebenfalls abgeschlossen** (2026-08-31, auf explizitem
Ausführungsauftrag — "führe Abschnitt 4e aus"). Details und Verifikation
stehen in `RESTRUCTURING_PROGRESS.md` Abschnitt "Phase 4e". Kurzfassung: die
4 Store-Module sind per `git mv` von `utils/` nach `store/` verschoben, alle
Call-Sites (39 Import-Treffer in 29 Dateien) entsprechend umgestellt und
verifiziert; die physische LLM-Ergebnis-Konsolidierung ist durchgeführt (83
Dateien aus den verstreuten Ordnern nach `outputs/llm_results/<source>__
<run_id>/` verschoben, `results_path` in `llm_runs.sqlite` aktualisiert,
zusätzlich — über den Plantext hinaus, aber notwendig, damit die
Konsolidierung nicht beim nächsten Lauf wieder auseinanderfällt — die drei
Download-Skripte auf den neuen Ablageort als künftigen Schreibort
umgestellt); `README_ADD_NEW_CHANNELS.md` ist über die im Plantext genannte
Registry-Referenz hinaus auch bei mehreren weiteren, beim Gegenprüfen
gefundenen veralteten State-CSV-Pfaden aktualisiert. **Änderungen liegen nur
im Working Tree, noch nicht committet.**

**Phase 4 ist damit vollständig abgeschlossen (4a–4e).**

### Neue Erkenntnisse aus 4a (relevant für alle weiteren Teilschritte)

- **`python -c "import youtube_code"` schlägt in diesem Environment ohne
  weiteres Zutun fehl** (`ModuleNotFoundError`) — auch aus der `.venv`
  heraus. Die editable-Install-Konfiguration (`.venv/Lib/site-packages/
  __editable___youtube_data_0_1_0_finder.py`) mappt `src`, `data`, `scripts`,
  `outputs` als Top-Level-Namespaces, aber **nicht** `youtube_code` selbst als
  Top-Level-Package. Jeder `python -c "import youtube_code"`-Verifikationsschritt
  (auch die für 4b–4e im Plan vorgeschlagenen) muss deshalb mit
  `PYTHONPATH=src` (bzw. `sys.path.insert(0, "src")` im Skript) laufen, sonst
  schlägt die Verifikation fälschlich fehl, obwohl der Code korrekt ist.
  Vermutlich funktionieren die vielen `from youtube_code...`-Imports im
  Alltag über eine PyCharm-"Sources Root"-Markierung von `src/`, die sys.path
  nur innerhalb der IDE, nicht in einer bloßen Shell ergänzt — für
  Kommandozeilen-Verifikation in künftigen Sitzungen immer `PYTHONPATH=src`
  explizit setzen.
- **`wc -l` ist für Zeilen-/Datensatzzählungen auf den Screening-State-CSVs
  unbrauchbar**: `longitudinal_screening_state.csv` hat mehrzeilige gequotete
  Felder, wodurch `wc -l` ~18 Mio. "Zeilen" meldet statt der tatsächlichen
  1.012.206 Datensätze. Für Zeilenvergleiche immer einen CSV-fähigen Reader
  (`pandas.read_csv`) oder die jeweilige Store-Funktion (`total_count()`,
  `round_counts()`) verwenden — relevant für alle noch folgenden
  Verifikationsschritte in 4b–4e, die auf CSV-vs-Store-Vergleichen beruhen.
- Ein als "wahrscheinlich tot" eingestufter Ordner (`scripts/old/`, 12
  Dateien) wurde nicht automatisch entschieden, sondern per Rückfrage an den
  Nutzer geklärt (Ergebnis: alles archiviert) — falls in 4b–4e ähnlich
  unklare "alt vs. tot"-Fälle auftauchen (z. B. bei den in 4b Punkt 6
  erwähnten `registry/runs_registry_legacy.csv`/`_old.csv`), lohnt sich eine
  kurze Rückfrage statt einer stillschweigenden Annahme.

---

## Context

Die Restrukturierung (`.claude/restructuring/RESTRUCTURING_PLAN.md`) hat in Phase 3a–3d vier neue SQLite-Stores geschaffen (`video_registry.py`, `transcript_store.py`, `screening_state_store.py`, `llm_run_store.py`, alle unter `src/youtube_code/utils/`) und deren Inhalte per Migrationsskript aus den alten CSV/JSON(L)-Quellen befüllt und verifiziert. Die alten Quelldateien wurden dabei bewusst **nicht** gelöscht und die lesenden/schreibenden Skripte **nicht** umgestellt — das war laut Plan explizit für Phase 4 vorgesehen. Ergebnis: die Stores existieren als Snapshot, aber die eigentlichen Pipelines (Transkript-Scraper, Screening-State-Schreiber, LLM-Run-Registry) laufen weiterhin gegen die alten CSVs weiter, sodass die Stores bei jedem neuen Lauf sofort wieder veralten und die ursprünglichen Probleme (19 GB Backup-Fluten, Vollkopie-Rewrites, zwei kollidierende Registry-CSVs) strukturell bestehen bleiben.

Drei parallele Recherche-Agenten haben den aktuellen Code-Stand für alle 9 im Masterplan genannten Phase-4-Punkte plus die in den Phase-3-Progress-Notizen aufgelaufenen Folgepunkte präzise erfasst (Datei:Zeile-genau). Zwei Punkte erwiesen sich dabei als echte Nutzerentscheidungen (nicht aus dem Code ableitbar) und wurden geklärt:

- **Sample-Membership-Ableitung** ("russia_base" o.ä.): Die bereits migrierten `search_runs`/`video_search_hits`-Daten enthalten nur deutsche Partei-Suchbegriffe; die Russland/Ukraine-Kanal-Identifikation liegt unmigriert im Archiv mit anderem Schema. → **Nutzerentscheidung: komplett aus Phase 4 heraus, als eigenständiges Thema für eine spätere, separate Session** (analog zur 27-Kanäle-Fachaufgabe).
- **Physische LLM-Ergebnis-Konsolidierung**: → **Nutzerentscheidung: `outputs/llm/longitudinal/` UND `outputs/segment_analysis/` werden in Phase 4 konsolidiert; `outputs/llm/gemini/nahost_descriptive_figures/` (164 MB, thematisch fremd) wird ignoriert und nur als offener Punkt dokumentiert.**

Weil der verbleibende Scope sehr groß ist (10+ Call-Sites für die Run-Registry, 4 Screening-State-Schreiber + 5 Leser, 1 Kern-Scraper + 5 Transkript-Leser, diverse Aufräumpunkte), wird Phase 4 — analog zu Phase 3a–3d — in fünf einzeln ausführbare, session-große Teilschritte gegliedert, geordnet nach Abhängigkeit und Risiko: **4a (mechanisches Aufräumen, keine Abhängigkeiten) → 4b (LLM-Run-Registry) → 4c (Transkripte) → 4d (Screening-State, hängt an 4b) → 4e (Store-Modulverschiebung + physische Ergebnis-Konsolidierung, hängt an 4b–4d)**. Wie bei Phase 3 gilt die Standing-Entscheidung des Nutzers: **nur Pläne liefern, Ausführung erfolgt durch den Nutzer selbst** (ggf. mit Claude-Unterstützung in späteren Sessions, sofern dort explizit ein Ausführungsauftrag erteilt wird — wie bereits bei 3c/3d geschehen).

Jeder Teilschritt folgt dem in Phase 3 etablierten Muster: Store-/Code-Änderung → Smoke-Test/Dry-Run → Verifikation → Alt-Pfad erst danach entfernen.

---

## Teilschritt 4a — Mechanisches Aufräumen (keine Abhängigkeiten, niedrigstes Risiko) ✅ ERLEDIGT (2026-08-31)

**Siehe "Status"-Abschnitt oben und `RESTRUCTURING_PROGRESS.md` Abschnitt "Phase 4a" für die vollständige Durchführung und Verifikation.** Der folgende Originaltext bleibt als Referenz stehen, wurde aber bereits umgesetzt.

Empfohlen als erste Sitzung, da unabhängig von allen anderen Teilschritten und schnell hohen Nutzen bringt (~3,9 GB, tote Importe, Namenskollisionen).

1. **Backup-Cleanup (~3,9 GB)**: `data/samples/russia/batches_longitudinal/state_backups/politics_screening_state_before_run_0024.csv` (1,31 GB), `..._before_run_0025.csv` (1,31 GB), `data/samples/russia/longitudinal_screening_state.csv.bak_pre_27channels_step3` (1,29 GB) löschen — die in Phase 3c genannte Rückhaltebedingung ("erst wenn Runden 9/10 gemergt sind") ist laut Progress-Notiz inzwischen erfüllt. Vorher kurz per `screening_state_store.total_count()`/`round_counts()` gegen die aktuelle State-Datei bestätigen, dass keine der drei Backup-Dateien die einzige Quelle für einen sonst verlorenen Zwischenstand ist (analog Phase-1-Vorgehen).
2. **`legacy/` archivieren**: `src/youtube_code/politics_screening/legacy/` (3 Dateien, seit 26 Tagen unverändert, keine aktiven Importe gefunden) per `git mv` nach `src/youtube_code/archive/politics_screening_legacy/` verschieben (Historie erhalten), nicht löschen.
3. **Kaputte, tote Skripte deprecaten**: `src/youtube_code/collection/video_sampling.py` und `comment_download.py` (kaputte `../JSON Files/...`-Pfade, keine aktiven Importe) — nach `archive/` verschieben statt reparieren, da niemand sie aufruft.
4. **`sample_50k_channels_russia_ukraine.jsonl`** (ohne `_wo_shorts`, 1,87 GB, `data/samples/russia/`) löschen — nur auskommentierte Referenzen (`screening_config.py:12` u.a.), keine aktive Nutzung.
5. **Import-Konsistenz reparieren**: die 5 `from src.youtube_code...`-Stellen (`collection/video_search.py:7-9`, `scripts/adhoc/merge_ideology_group_labels.py:2`, `scripts/training_data.py:9`) auf `from youtube_code...` umstellen; die nackten Sibling-Importe (`from settings_variables import ...` in `channel_all_videos.py:59`/`video_identification.py:49`/`video_search.py:6`, `from success_data_utils import ...` in 3 `archive/success_analysis/*.py`-Dateien, `from deskriptiv_aggregation import ...`/`from fe_signifikanz_test import ...` in `segment_analysis/*.py`) auf Paket-relative Importe umstellen bzw. bei Modulen, die nur als Skript mit `cwd`-Annahme laufen, das als bewusstes Muster im Docstring vermerken statt stillschweigend zu lassen.
6. **`scripts/` vs. `src/youtube_code/` Namenskollision auflösen**: `scripts/video_sampling.py` (625 Zeilen, sauberer Code, aktiv) vs. `src/youtube_code/collection/video_sampling.py` (jetzt archiviert, Schritt 3) — nach Schritt 3 ist die Kollision bereits aufgelöst, hier nur gegenprüfen. `scripts/old/` als Ganzes sichten (`channel_activity_over_time.py`, `evaluate_title_classification.py`, `run_title_*_batch.py`, `outcome_analysis/`, `transcript_analysis/`) — sind laut Recherche fast alle durch `src/youtube_code/`-Pendants abgelöst; falls bestätigt, nach `scripts/archive/` oder direkt löschen (mit Nutzer je Datei kurz gegenprüfen, da "alt" nicht automatisch "tot" heißt).
7. **Kleinere offene Fragen dokumentieren statt automatisch entscheiden**: `data/external/media_type_russia_merged.xlsx.bak` (klein, unklarer Zweck, keine Code-Referenz) und die JSONL-Doppelspurigkeit in `src/youtube_code/utils/io.py:get_video_metadata()` (schreibt sowohl JSONL als auch `video_registry.upsert_videos()`) — beides als offene Punkte in `RESTRUCTURING_PROGRESS.md` festhalten statt in 4a blind zu entscheiden.

**Kritische Dateien:** siehe Pfade oben, keine neuen Store-Funktionen nötig.

**Verifikation:** `du -sh data/` vor/nach (Rückgang ≈ 3,9 GB + 1,87 GB ≈ 5,8 GB); `grep -r "from src.youtube_code\|from settings_variables\|from success_data_utils\|from deskriptiv_aggregation\|from fe_signifikanz_test" src/ scripts/` liefert keine Treffer mehr (oder nur dokumentierte Ausnahmen); `python -c "import youtube_code"` weiterhin fehlerfrei; `git mv`-Historie per `git log --follow` auf die neuen Pfade nachvollziehbar.

---

## Teilschritt 4b — LLM-Run-Registry: Call-Sites auf `llm_run_store` umstellen

**Design-Entscheidung (empfohlen, nicht mehr offen):** Direktumbau statt Kompatibilitäts-Wrapper um die alte `RunRegistry`-Klasse — passt zum Ziel "vollständige Migration", vermeidet eine dauerhafte Doppelschicht, und die neue `get_run(source, run_id)`-Signatur (bewusster API-Bruch, da `run_id` jetzt nicht mehr global eindeutig ist) macht einen transparenten Wrapper ohnehin unsauber.

**Reihenfolge innerhalb 4b** (nach Blast-Radius, kleinste/isolierteste zuerst):
1. Reine Leser-Call-Sites zuerst: `run_longitudinal_screening_batch.py`, `run_politics_screening_batch.py`, `run_transcript_classification_batch.py` (je nur `get_runs(...)` als Preflight-Duplikat-Check) und `evaluate_politics_screening.py` (`get_run`) — auf `llm_run_store.get_runs(source="screening_active", ...)` / `get_run(source="screening_active", run_id=...)` umstellen.
2. Zentrale Schreiber: `submit_batch_jobs.py` (`add_run` in `run_all_prompts()`, von den drei obigen Skripten importiert — hoher Blast-Radius, zuerst isoliert testen) und `download_results.py` (5× `update_run` mit unterschiedlichen Status-Werten in `process_run()`) auf `upsert_runs(source="screening_active", records=[...])` umstellen.
3. `retry_run.py` (verkettete `get_run`/`update_run`-Aufrufe über ein importiertes Registry-Objekt) und `update_screening_state.py` (nur der Registry-Teil, Zeile 311–312 — der State-Teil gehört zu 4d) umstellen.
4. Parallele `segment_analysis_active`-Quelle: `submit_segments.py`, `download_segments.py`, `download_segments_simple.py` (fast identischer Code wie `download_segments.py` — bei dieser Gelegenheit prüfen, ob sich beide zusammenlegen lassen) analog auf `source="segment_analysis_active"` umstellen.
5. `segment_analysis_config.py` und `screening_config.py`: `REGISTRY_PATH`-Konstante durch einen Verweis auf den konsolidierten Store ersetzen (beide Configs zeigen dann auf dieselbe `llm_runs.sqlite`, unterschieden nur noch per `source`-Parameter).
6. Aufräumen: `llm_analysis/merge_and_evaluate.py` (kaputter Import, tote `gemini_old`-Quelle) nach `archive/` verschieben; Top-Level-`llm_analysis/`-Ordner (Repo-Root, nur noch `registry/runs_registry.csv`) löschen; `src/youtube_code/llm_analysis/registry/` (alte `run_registry.py`-Klasse + `runs_registry.csv`/`_legacy.csv`/`_old.csv`) nach `archive/` verschieben, sobald keine Call-Site mehr importiert.

**Kritische Dateien:** `src/youtube_code/utils/llm_run_store.py` (Zielmuster bereits vorhanden), alle 10 oben genannten Call-Sites, `src/youtube_code/politics_screening/screening_config.py`, `src/youtube_code/segment_analysis/segment_analysis_config.py`.

**Verifikation:** kleines `scripts/adhoc/verify_llm_run_callsites.py` (Dry-Run-Modus je Skript, prüft nur ob Registry-Zugriffe fehlerfrei laufen, ohne echte Batch-Jobs abzuschicken); danach `llm_run_store.total_count()`/`source_counts()` vor/nach jedem realen Lauf eines Skripts unverändert bzw. plausibel wachsend; `grep -r "RunRegistry\|runs_registry.csv" src/ scripts/` liefert nach Abschluss keine aktiven Treffer mehr (nur noch in `archive/`).

---

## Teilschritt 4c — Transkripte: Scraper + Leser auf `transcript_store` umstellen

**Höchstes Einzelrisiko der ganzen Phase 4**, da der Scraper mit echten (kostenpflichtigen) API-Calls läuft — vor jeder Änderung sicherstellen, dass kein Lauf aktiv ist (Prozessliste, wie in 3b/3c/3d bereits geübt), und nach der Umstellung erst mit einer kleinen Video-ID-Menge testen, bevor ein voller Lauf gestartet wird.

1. `src/youtube_code/scraping/transcript_scraping_segments.py`: Resume-Filter (aktuell `pd.read_csv(OUTPUT_FILE, usecols=["video_id","status"])`, Zeilen 97–114) durch `transcript_store.attempted_video_ids()`/`get_transcripts()` ersetzen; Batch-Flush (Zeile 252) und finalen Flush (Zeile 273–275) durch `upsert_transcripts()` ersetzen; den kompletten Backup-Block (Zeilen 265–269, erzeugt `all_transcripts_backup.csv` neu) **ersatzlos streichen** — das ist die strukturelle Ursache der in Phase 1 bereinigten 2,9 GB Backup-Datei.
2. `single_transcript_downloader.py` (schreibt in die bereits gelöschte, tote `single_transcripts.csv`) nach `archive/` verschieben statt zu migrieren — kein aktiver Nutzen erkennbar.
3. Die 5 Downstream-Leser umstellen (Muster: `pd.read_csv(TRANSCRIPTS / "all_transcripts_segments.csv", usecols=[...])` → passender `transcript_store`-Aufruf):
   - `src/youtube_code/segment_analysis/process_scraped_segments.py` (Zeilen 65, 310–343, gechunktes Lesen mit Status-Filter) → `get_transcripts()` mit Filterung.
   - `src/youtube_code/new_analysis/segment_transcripts.py` (Zeilen 51, 238–271, Streaming-Generator `iter_transcripts()`) → äquivalent auf Store umstellen, Generator-Schnittstelle nach außen beibehalten.
   - `src/youtube_code/scraping/get_baseline_ids.py` (Zeile 29, nur `video_id`-Spalte) → `attempted_video_ids()`.
   - `scripts/adhoc/segment_analysis_result_checks.py` (Zeile 74) → `attempted_video_ids()`.
   - `scripts/adhoc/sample_feasibility_helpers.py` (Zeilen 66–67, 111–112, zwei Call-Sites in einer Datei) → `attempted_video_ids()`.
4. `data/transcripts/all_transcripts_segments.csv` (2,9 GB) und die zugehörige (durch Schritt 1 nicht mehr neu erzeugte) `all_transcripts_backup.csv` erst löschen, nachdem alle 6 Call-Sites umgestellt und verifiziert sind.

**Kritische Dateien:** `src/youtube_code/utils/transcript_store.py` (Zielmuster bereits vorhanden), die 6 oben genannten Dateien.

**Verifikation:** Smoke-Test des Scrapers mit einer kleinen Test-ID-Liste (`DRY_RUN`-ähnlich, wenige Videos) vor produktivem Einsatz; `transcript_store.total_count()`/`status_counts()` vor/nach unverändert bzw. plausibel wachsend; jeder umgestellte Leser liefert für eine Stichprobe dieselben `video_id`s/Segmente wie vorher (Vergleich CSV-Snapshot vs. Store, analog Phase-3b-Verify-Skript); `all_transcripts_backup.csv` entsteht nach einem Testlauf **nicht** mehr neu.

---

## Teilschritt 4d — Screening-State: 4 Schreiber + Leser auf `screening_state_store` umstellen

**Abhängig von 4b**, da `update_screening_state.py` sowohl State- als auch Registry-Zugriffe in derselben Datei hat und die Registry-Seite dort sauber vormigriert sein sollte, bevor der State-Teil angefasst wird. Nur angehen, wenn gerade kein Screening-Batch aktiv läuft (Prozess-Check wie in 3c).

1. `append_channels_to_state.py` (Zeilen 61, 134–135, reines Anhängen neuer Kanäle, kein Backup vorhanden) → `upsert_state_rows()` mit nur den neuen Zeilen statt `pd.concat` + Vollkopie-`to_csv`.
2. `create_longitudinal_screening.py` (Zeilen 469, 521–530, setzt nur `screening_round` für ausgewählte Zeilen, aktuell atomarer Vollkopie-Rewrite über `atomic_write_csv`) → `upsert_state_rows()` nur für die betroffenen Zeilen/Spalten; die Konsistenz-Validierung aus `load_screening_state()` als eigene Funktion erhalten (ggf. auf DB-Export anwenden, analog Phase-3c-Verify-Muster).
3. `assign_postwar_baseline.py` (Zeilen 158, 190–194, EINZIGES der vier Skripte mit automatischem Vollkopie-Backup `*.before_postwar_assignment.csv`) → `upsert_state_rows()` für die 4 betroffenen Spalten; den Backup-Block ersatzlos streichen (SQLite braucht kein CSV-Vollkopie-Muster).
4. `update_screening_state.py` (komplexestes der vier: Label-Schutzregeln "nur NULL→Wert", `validate_state_consistency()`, Backup nach `STATE_BACKUP_DIR`, plus der in 4b bereits migrierte Registry-Zugriff) — hier **vorab mit dem Nutzer klären, welche Spalten je Call-Site künftig übergeben werden und wie die Label-Schutzregel auf die neue Upsert-Semantik abgebildet wird** (laut Phase-3c-Plan bewusst nicht vorweggenommen, da Business-Logik). Backup-Block (Zeile 744–745, erzeugt die ~2,6 GB `state_backups/`-Vollkopien) ersatzlos streichen.
5. `get_baseline_ids.py` (hartkodierter State-Pfad als String, Zeile 4–9) auf `screening_state_store.get_state()` umstellen (gleicher Zug wie der Transkript-Teil desselben Skripts in 4c — beide in einer Sitzung sinnvoll, da dieselbe Datei betroffen ist).
6. **Batch-Runner-Merge**: `run_politics_screening_batch.py`/`run_longitudinal_screening_batch.py` (675/673 Zeilen) zu einer parametrisierten Funktion zusammenführen — die Recherche fand über die bekannte `ROUND_NUMBER`-Konstante hinaus eine echte Spaltennamen-Divergenz (`"time_period"` vs. `"interval_label"`, 6 Stellen), die als zusätzlicher Parameter (z. B. `PERIOD_COLUMN`) mitgeführt werden muss, nicht nur als Konstante am Skriptkopf.

**Kritische Dateien:** `src/youtube_code/utils/screening_state_store.py` (Zielmuster bereits vorhanden), die 5 oben genannten Dateien, die 2 Batch-Runner.

**Verifikation:** `screening_state_store.total_count()`/`round_counts()`/`label_counts()` vor/nach jedem umgestellten Schreiber unverändert bzw. plausibel; `validate_state_consistency()` (bestehende Funktion) läuft nach jedem Testlauf weiterhin fehlerfrei über den DB-Export; kein Backup-Block erzeugt nach einem Testlauf mehr eine neue Vollkopie; gemergter Batch-Runner läuft für beide bisherigen Modi (`politics`/`longitudinal`) mit identischem Ergebnis wie vorher (Vergleichslauf mit `DRY_RUN=True`).

---

## Teilschritt 4e — Store-Modulverschiebung + physische LLM-Ergebnis-Konsolidierung

**Zuletzt**, da hier die inzwischen stabilisierten Call-Sites aus 4b–4d nur noch umbenannt/verschoben werden (mechanisch, wenig Merge-Konfliktpotential mehr).

1. `src/youtube_code/store/` anlegen; `video_registry.py`, `transcript_store.py`, `screening_state_store.py`, `llm_run_store.py` von `utils/` dorthin verschieben (`git mv`, Historie erhalten); alle Importe in den in 4b–4d bereits umgestellten Call-Sites entsprechend anpassen (`from youtube_code.utils.video_registry import ...` → `from youtube_code.store.video_registry import ...`).
2. Physische LLM-Ergebnis-Konsolidierung (Nutzerentscheidung, siehe Context): nach dem in `.claude/plans/phase_3d.md` Abschnitt 6 skizzierten Muster `outputs/llm_results/<source>__<run_id>/`:
   - `outputs/llm/longitudinal/` (schon nach Run gruppiert, 32+24 Dateien inkl. `_copy`/`_retry`/`_combined`-Varianten) verschieben und in `llm_runs.sqlite` (`results_path`-Spalte) verlinken — einfacherer Teil.
   - `outputs/segment_analysis/` (flache Struktur, ~19 Run-CSVs gemischt mit ~45 abgeleiteten Analyse-Dateien ohne `run_id`) aufräumen: zuerst Run-Ergebnisse (an `segment_analysis_active`-Runs in `llm_runs.sqlite` zuordenbar) von abgeleiteten Analysen (`channel_classification_*.csv`, `baseline_*.csv`, `uebersicht_*.csv`, `populism_runs_combined.csv` u. a., landen z. B. in `outputs/reports/`) trennen.
   - `outputs/llm/gemini/nahost_descriptive_figures/` (164 MB) **explizit ignorieren** und als offenen Punkt in `RESTRUCTURING_PROGRESS.md` festhalten (Nutzerentscheidung).
3. `README_ADD_NEW_CHANNELS.md` gegenprüfen — referenziert u. a. `runs_registry.csv` (Zeile 175); Pfad-Referenzen entsprechend den in 4b–4e vorgenommenen Umbenennungen aktualisieren.

**Kritische Dateien:** die 4 Store-Module, `.claude/plans/phase_3d.md` (Konsolidierungsvorschlag), `src/youtube_code/politics_screening/README_ADD_NEW_CHANNELS.md`.

**Verifikation:** `python -c "import youtube_code"` + gezielte Subpackage-Importe aus sauberem `.venv`; `grep -r "utils.video_registry\|utils.transcript_store\|utils.screening_state_store\|utils.llm_run_store" src/ scripts/` liefert keine Treffer mehr; Dateizahl-Check `outputs/llm_results/` vs. vorher verschobene Quellordner; End-to-End-Dry-Run mindestens einer Pipeline je Store-Typ.

---

## Gesamt-Verifikation nach Abschluss aller 5 Teilschritte

- `grep -r "runs_registry_old\|runs_registry_legacy\|JSON Files" src/` liefert keine Treffer mehr (aus dem Masterplan übernommenes Kriterium).
- `python -c "import youtube_code"` + Subpackage-Importe aus sauberem `.venv` fehlerfrei.
- Keine der drei Kern-Pipelines (Scraper, Screening-Batch, LLM-Run-Submit/Download) erzeugt mehr automatisch eine CSV-Vollkopie/Backup.
- `RESTRUCTURING_PROGRESS.md` um einen Phase-4-Abschnitt ergänzt (Status je Teilschritt 4a–4e, offene Punkte: Sample-Membership-Ableitung als separate Session, `nahost_descriptive_figures/`-Konsolidierung, `data/external/media_type_russia_merged.xlsx.bak`).
- Bereit für Phase 5 (Konfiguration/Doku): `config/paths.py`-Bereinigung, README, `.claude/CLAUDE.md`-Regel-Update auf die neuen Stores.

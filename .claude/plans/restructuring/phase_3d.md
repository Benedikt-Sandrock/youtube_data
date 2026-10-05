# Phase 3d — LLM-Run-Registry → `data/raw/llm_runs.sqlite`

## Context

Teil der laufenden Repo-Restrukturierung (`.claude/restructuring/RESTRUCTURING_PLAN.md`,
Fortschritt in `RESTRUCTURING_PROGRESS.md`). Phase 3a (Video-Metadaten), 3b
(Transkripte) und 3c (Screening-State) sind abgeschlossen; Phase 3d ist der
letzte Format-Migrations-Teilschritt und überträgt denselben Ansatz auf die
Registry der LLM-Batch-Runs (`RunRegistry` aus
`src/youtube_code/llm_analysis/registry/run_registry.py`). Jede Zeile
repräsentiert einen an Gemini geschickten Batch-Job (Prompt, Modell, Datensatz,
Zielvariable) plus Ergebnis-Pfad — die Kern-Buchführung für alle bezahlten,
nicht günstig reproduzierbaren LLM-Klassifikationsläufe des Projekts.

Wie in Phase 3a–3c liefert diese Session **nur den Plan** — Umsetzung erfolgt
in einer späteren Session (Nutzer-Standing-Entscheidung, siehe
`project-restructuring-decisions`-Memory).

## Wichtiger Befund: die Recherche korrigiert die Plan-Annahme

Der ursprüngliche Plan-Text nannte "die drei Registry-Varianten
(`runs_registry.csv`, `_legacy`, `_old`, plus die abweichende Top-Level-Kopie
unter `llm_analysis/registry/`)" und ging von einer einzigen Ziel-Tabelle mit
`run_id` als natürlichem Schlüssel aus. Die Recherche in dieser Session zeigt:
**die "Top-Level-Kopie" ist keine Kopie**, sondern eine zweite, unabhängig
aktive Registry mit kollidierendem `run_id`-Namensraum. Eine reine
`run_id`-Migration würde also Zeilen aus verschiedenen Quellen stillschweigend
überschreiben.

Vier CSV-Dateien, alle mit identischem Schema (`RunRegistry.REGISTRY_COLUMNS`,
16 Spalten), aber vier getrennte `run_id`-Zähler, die alle bei `run_0001`
beginnen:

| Datei | Zeilen | Aktiv? | `REGISTRY_PATH` in Code | Pipeline |
|---|---|---|---|---|
| `src/youtube_code/llm_analysis/registry/runs_registry.csv` | 25 | **ja** | `screening_config.PROJECT_ROOT` = `src/youtube_code/` → `.../llm_analysis/registry/runs_registry.csv` | Longitudinal-Politik-Screening (Titel/Beschreibung), Ergebnisse in `outputs/llm/longitudinal/` |
| `llm_analysis/registry/runs_registry.csv` (Repo-Root, **kein** `src/`) | 19 | **ja** | `segment_analysis_config.ROOT` = Repo-Root → `.../llm_analysis/registry/runs_registry.csv` | Segment-Klassifikation (IDEOLOGIE/POPULISMUS/POSITION), Ergebnisse in `outputs/segment_analysis/` |
| `runs_registry_legacy.csv` | 25 | nein | nirgends im Code referenziert | Frühere Screening-Runden 001–008 vor einem Laufwerkswechsel (`E:\PyhcarmProjects\...`-Pfade, andere `job_id`s/Timestamps als die aktuelle Registry — keine 1:1-Duplikate, sondern neu eingereichte Läufe) |
| `runs_registry_old.csv` | 14 | nein | nur `merge_and_evaluate.py` (relativer Pfad `"registry/runs_registry_old.csv"`, defekter Import `from registry.run_registry import ...`, Skript nirgends sonst importiert — tot) | Frühe `populism_score`-Läufe (Juni/Juli), Ergebnisse in `outputs/llm/gemini/results/` |

Der scheinbare Namens-Zufall (beide Pfade enden auf
`llm_analysis/registry/runs_registry.csv`) kommt daher, dass
`screening_config.py` und `segment_analysis_config.py` **unterschiedliche
Basis-Konstanten** (`PROJECT_ROOT` = `src/youtube_code/` vs. `ROOT` = Repo-Root)
mit demselben relativen Suffix kombinieren — kein Copy-Paste-Duplikat, sondern
zwei unabhängig gewachsene Konfigurationen, die zufällig denselben Ordnernamen
gewählt haben.

**Stichprobe der `results_path`-Existenz** bestätigt die Aktiv/Tot-Einstufung:
`outputs/segment_analysis/run_0001_IDEOLOGIE_I.csv` und
`outputs/llm/longitudinal/title_classification/run_0002.csv` existieren
physisch; `outputs/llm/title_classification/run_0001.csv` (legacy) und
`outputs/llm/gemini/results/run_0001.csv` (old, Ordner existiert nicht mehr
im Repo) fehlen beide. Für `_legacy`/`_old` gibt es also ohnehin nichts mehr
physisch zu konsolidieren — nur die Metadaten-Zeilen selbst sind erhaltenswert
(Audit-Trail), nicht mehr verknüpfte Dateien.

**Nicht Teil dieser Migration** (zur Klarstellung, da namensähnlich):
`data/channel_lists/all_identification/runs_registry.json` ist eine völlig
andere Registry (Such-Query-Provenienz für die Kanal-Identifikation) und wurde
bereits in Phase 3a als `search_runs`/`video_search_hits` migriert.

## Recherche-Befunde (verifiziert)

- **Schema** (`RunRegistry.REGISTRY_COLUMNS`, identisch in allen vier CSVs):
  `run_id, job_id, status, prompt_id, prompt_number, prompt_version, model,
  thinking_budget, dataset_id, dataset_version, target_variable,
  validation_basis, created_at, updated_at, results_path, notes`.
- **Zeilenzahlen:** aktuelle Screening-Registry 25, aktuelle Segment-Registry
  19, `_legacy` 25, `_old` 14 → **83 Zeilen insgesamt** zu importieren.
- **12 Call-Sites** verwenden `RunRegistry` aktiv (submit/download je Pipeline,
  `evaluate_politics_screening.py`, `update_screening_state.py`,
  `merge_and_evaluate.py` [tot]); alle über `RunRegistry(REGISTRY_PATH)` mit
  `add_run`/`update_run`/`get_runs`/`get_run` — kein direktes CSV-Parsing
  außerhalb der Klasse gefunden.
- **Keine `run_id`-Kollisionen innerhalb** einer einzelnen Quelldatei (die
  `_next_run_id()`-Logik in `RunRegistry` verhindert das strukturell), aber
  **Kollisionen zwischen den vier Quellen** (z. B. `run_0001` existiert in
  allen vier Dateien mit völlig unterschiedlichem Inhalt) — das ist der
  zentrale Designpunkt für diese Phase.
- Zielmuster `video_registry.py`/`transcript_store.py`/`screening_state_store.py`
  (Phase 3a–3c): `sqlite3.connect(DB_PATH, timeout=30)` + WAL-Mode,
  Migrations-/Verify-Skript-Stil mit `.bak_pre_migration`.
- Speicherort-Präzedenzfall: `data/raw/` (wie `video_registry.sqlite`,
  `transcripts.sqlite`, `screening_state.sqlite`), nicht `data/store/`
  (kommt gebündelt erst in Phase 5).

## Design-Entscheidungen für diese Session

- **Synthetischer Primärschlüssel statt `run_id`:** `id INTEGER PRIMARY KEY
  AUTOINCREMENT`, zusätzlich `UNIQUE(source, run_id)`. Der ursprüngliche
  Plan-Text ("Tabelle mit `run_id, pipeline, status, ...`") ging von einem
  einzigen `run_id`-Namensraum aus — das trifft laut obigem Befund nicht zu.
  Ein `source`-Feld macht die tatsächliche Herkunft explizit (nicht nur
  "Pipeline", da `_legacy`/`_old` funktional zur selben Pipeline gehören wie
  eine der aktiven Registries, aber eigene Dateien mit eigenem Zähler sind):
  `'screening_active'`, `'segment_analysis_active'`, `'screening_legacy'`,
  `'gemini_old'`. Der ursprüngliche `run_id`-Wert bleibt als eigene Spalte
  erhalten (nicht global eindeutig, aber innerhalb `source` eindeutig — wichtig
  für Nachvollziehbarkeit, da alle Ergebnisdateien/Docstrings/Handoffs bisher
  nach `run_id` allein benennen).
- **Volles Spaltenschema statt der verkürzten Version aus dem Top-Level-Plan**
  (`run_id, pipeline, status, input_path, output_path, created_at`): analog zu
  3a–3c wird das bestehende, bereits funktionierende Schema
  (`REGISTRY_COLUMNS`) 1:1 übernommen statt reduziert — kein Informationsverlust,
  keine Neuerfindung.
- **Kein Merge/Dedup der 83 Zeilen:** anders als bei Video-Metadaten (3a, echte
  inhaltliche Dopplung derselben Entität) sind hier alle Zeilen historisch
  unterschiedliche Runs (auch `_legacy`/`_old`, siehe Tabelle oben) — reiner
  Import aller vier Quellen, kein COALESCE-Merge nötig. Upsert-Semantik dient
  hier nur der Idempotenz bei erneutem Skriptlauf, nicht der Quellen-Fusion.
  Bei einem zweiten Lauf muss der Vergleichsschlüssel `(source, run_id)` sein,
  nicht `run_id` allein.
- **Physische Ergebnis-Konsolidierung nach `outputs/llm_results/<run_id>/`**
  (im Top-Level-Plan-Text vorgesehen) wird in dieser Phase **nicht**
  durchgeführt. Begründung: (1) der Nutzer hat für diesen Teilschritt explizit
  "konservativ vorgehen, im Zweifel behalten statt löschen, Einzelfälle mit
  Nutzer absprechen" vorgegeben; (2) ein Ordnername nach `<run_id>` allein wäre
  wegen der Namensraum-Kollision mehrdeutig (welches `run_0001`?); (3) mehrere
  aktive Downstream-Skripte referenzieren die bestehenden `results_path`-Werte
  direkt (`merge_and_evaluate.py` zwar tot, aber `evaluate_politics_screening.py`
  aktiv) — ein Verschieben ist ein Call-Site-Umbau wie die in 3a–3c bereits
  aufgeschobenen Themen und gehört damit konsistent zu **Phase 4**. Diese Phase
  liefert nur die SQLite-Registry als Nachschlagewerk; siehe Abschnitt 6 für
  einen konkreten Vorschlag zur späteren Umsetzung.
- **`data/raw/llm_runs.sqlite`**, Modul
  `src/youtube_code/utils/llm_run_store.py` (analog `transcript_store.py`/
  `screening_state_store.py`). Wandert wie die anderen Stores in Phase 4 nach
  `store/`.
- **Alle vier Quell-CSVs bleiben unangetastet liegen**, keine Löschung in
  dieser Phase.

## 1. Schema

```sql
CREATE TABLE IF NOT EXISTS llm_runs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    source            TEXT NOT NULL,   -- 'screening_active' | 'segment_analysis_active'
                                        -- | 'screening_legacy' | 'gemini_old'
    run_id            TEXT NOT NULL,   -- Original-Wert aus der Quell-CSV, NICHT global eindeutig
    job_id            TEXT,
    status            TEXT,
    prompt_id         TEXT,
    prompt_number     TEXT,
    prompt_version    TEXT,
    model             TEXT,
    thinking_budget   INTEGER,
    dataset_id        TEXT,
    dataset_version   TEXT,
    target_variable   TEXT,
    validation_basis  TEXT,
    created_at        TEXT,
    updated_at        TEXT,
    results_path      TEXT,
    notes             TEXT,
    UNIQUE(source, run_id)
);

CREATE INDEX IF NOT EXISTS idx_llm_runs_dataset ON llm_runs(dataset_id);
CREATE INDEX IF NOT EXISTS idx_llm_runs_target  ON llm_runs(target_variable);
```

Begründung Indizes: `dataset_id` und `target_variable` sind die Felder, über
die `evaluate_politics_screening.py` und `RunRegistry.get_runs(**filters)`
heute am häufigsten filtern.

## 2. `src/youtube_code/utils/llm_run_store.py` (neu)

Modul-Docstring erklärt Zweck, vorläufigen Speicherort (→ Phase 4 nach
`store/`), und die vier `source`-Werte inkl. kurzer Erklärung, welche Datei/
Pipeline jeweils dahintersteht (siehe Tabelle oben, damit das nicht nur im
Migrationsskript-Kommentar steht).

- `_connect() -> sqlite3.Connection` — WAL-Mode, Schema anlegen, wie in
  `video_registry.py`/`transcript_store.py`/`screening_state_store.py`.
- `upsert_runs(source: str, records: list[dict]) -> int` — Upsert über
  `(source, run_id)` als Konfliktschlüssel, alle übrigen Spalten werden bei
  Konflikt überschrieben (ganze-Zeile-gewinnt-Muster wie `transcript_store`,
  passend zu einer reinen Registry ohne konkurrierende Teil-Updates
  verschiedener Quellen für dieselbe Zeile). Gibt Anzahl geänderter Zeilen
  zurück.
- `get_runs(source=None, dataset_id=None, target_variable=None, status=None) ->
  pd.DataFrame` — gefilterte Abfrage, Ersatz für
  `RunRegistry.get_runs(**filters)`; ohne Filter komplette Tabelle.
- `get_run(source: str, run_id: str) -> pd.Series` — Ersatz für
  `RunRegistry.get_run(run_id)`, jetzt mit Pflicht-`source`, da `run_id`
  allein nicht mehr eindeutig ist (bewusster API-Bruch, siehe Hinweis unten).
- `total_count() -> int`.
- `source_counts() -> pd.DataFrame` — `GROUP BY source`, Sanity-Helfer, sollte
  nach Migration `{screening_active: 25, segment_analysis_active: 19,
  screening_legacy: 25, gemini_old: 14}` ergeben.
- `export_csv(source, output_path) -> int` — Snapshot-Export einer einzelnen
  Quelle in der ursprünglichen `REGISTRY_COLUMNS`-Spaltenreihenfolge (ohne
  `id`/`source`), hält bestehende Konsumenten während der Übergangszeit
  kompatibel.

**Wichtiger Hinweis für Phase 4** (hier nur dokumentiert, nicht entschieden):
Die 12 aktiven Call-Sites rufen heute `RunRegistry(REGISTRY_PATH)` mit einer
Pfad-Konstante auf, die implizit die Pipeline festlegt — sie müssten in
Phase 4 auf `upsert_runs(source="screening_active", ...)` bzw.
`source="segment_analysis_active"` umgestellt werden. Ob dafür ein
`RunRegistry`-kompatibler Wrapper (gleiche Methodennamen, `source` fest in der
Instanz verankert) oder ein direkter Umbau auf die neuen Funktionsnamen
sinnvoller ist, wird dort entschieden — analog zur in Phase 3c offen
gelassenen Frage der Call-Site-Anpassung.

## 3. Migrationsskript `scripts/adhoc/migrate_llm_runs_to_store.py` (neu)

Einmaliges Skript, löscht keine Quelldateien, idempotent (Upsert über
`(source, run_id)`).

1. **Sicherheits-Checkpoint:** Prozessliste auf laufende
   `submit_batch_jobs.py`/`download_results.py`/
   `run_longitudinal_screening_batch.py`/`run_politics_screening_batch.py`/
   `submit_segments.py`/`download_segments*.py`-Instanzen prüfen (alle
   Skripte, die aktiv in eine der beiden lebenden Registries schreiben),
   analog zum Checkpoint in Phase 3b/3c.
2. Backup der Ziel-DB falls bereits vorhanden (`*.bak_pre_migration`, idempotent).
3. Vier Quellen laden, je mit fest zugeordnetem `source`-Tag:
   ```python
   SOURCES = [
       ("screening_active",        SRC / "llm_analysis/registry/runs_registry.csv"),
       ("segment_analysis_active", ROOT / "llm_analysis/registry/runs_registry.csv"),
       ("screening_legacy",        SRC / "llm_analysis/registry/runs_registry_legacy.csv"),
       ("gemini_old",              SRC / "llm_analysis/registry/runs_registry_old.csv"),
   ]
   ```
4. Je Quelle: `pd.read_csv(path, dtype=str)`, NaN → `None`, `upsert_runs(source, records)`.
5. Preflight/Nachlauf-Referenzwerte ausgeben und gegen die oben dokumentierten
   Zeilenzahlen prüfen (25 / 19 / 25 / 14 = 83 gesamt) — bei Abweichung
   abbrechen statt automatisch weiterzumachen.
6. `source_counts()` und `total_count()` am Ende ausgeben.

## 4. Verifikationsskript `scripts/adhoc/verify_llm_runs_migration.py` (neu)

Da die Gesamtmenge klein ist (83 Zeilen), **vollständiger Vergleich statt
Stichprobe** — stärker als das Sampling-Verfahren aus 3a–3c und hier ohne
Performance-Nachteil möglich:

- Für jede der vier Quell-CSVs: jede Zeile laden, per `(source, run_id)` in der
  DB nachschlagen, alle 16 Facheinheiten-Spalten Feld für Feld vergleichen
  (Read-only-Connection, `file:{db_path}?mode=ro`).
- Zeilenzahl-Check je Quelle (CSV vs. `source_counts()`) und gesamt (83).
- Stichprobe der `results_path`-Existenz (die bereits in der Recherche
  geprüften vier Beispielpfade + ggf. weitere) nur informativ geloggt (kein
  OK/MISMATCH-Kriterium, da erwartetermaßen zwei der vier Quellen tote Pfade
  haben — das ist kein Migrationsfehler).
- OK/MISMATCH-Ausgabe je Quelle und gesamt.

## 5. Reihenfolge & Sicherheits-Checkpoints

**Vor der Migration:** Sicherheits-Checkpoint (Punkt 1 oben) technisch prüfen.

**Nach der Migration:** `verify_llm_runs_migration.py` → OK für alle vier
Quellen; `RESTRUCTURING_PROGRESS.md` um einen Phase-3d-Abschnitt ergänzen
(Status, Datum, Kennzahlen, offene Folgepunkte für Phase 4).

## 6. Separater Vorschlag: physische Ergebnis-Konsolidierung (kein Teil dieser Migration)

Für eine spätere, separat freizugebende Aufräumrunde (frühestens Phase 4, da
sie Call-Sites berührt): Ergebnisdateien der beiden **aktiven** Registries
nach `outputs/llm_results/<source>__<run_id>/` verschieben (z. B.
`outputs/llm_results/screening_active__run_0002/`), referenziert über die
`results_path`-Spalte in `llm_runs.sqlite` statt über verstreute
Ordnerstrukturen. Für `screening_legacy`/`gemini_old` gibt es nichts zu
verschieben (Dateien bereits nicht mehr vorhanden, siehe Recherche-Befund) —
dort bleibt nur die DB-Zeile als historischer Audit-Eintrag. Explizit **nicht**
Teil dieser Phase, nur als konkretisierter Vorschlag festgehalten, damit er in
Phase 4 nicht neu erarbeitet werden muss.

## 7. Explizit NICHT Teil von Phase 3d

- Umstellung der 12 aktiven Call-Sites auf `llm_run_store.upsert_runs()`/
  `get_runs()`/`get_run()` statt `RunRegistry` → **Phase 4** (inkl. Entscheidung
  Wrapper vs. Direktumbau, siehe Hinweis in Abschnitt 2).
- Löschen einer der vier Quell-CSVs, auch der toten `_legacy`/`_old`-Dateien →
  frühestens nach Phase-4-Umstellung, dann eigene Freigabe.
- Physische Ergebnis-Konsolidierung nach `outputs/llm_results/<run_id>/` →
  siehe Abschnitt 6, separat freizugebender Folgeschritt.
- Bereinigung der Top-Level-`llm_analysis/`-Verzeichnisstruktur (Ordner
  existiert nach Herausnahme der CSV weiterhin leer, falls die Datei später
  gelöscht wird) → Phase 4/5.
- `.claude/CLAUDE.md`-Regel-Update → **Phase 5**, analog zur bereits offenen
  Transkript-Regel aus Phase 3b/3c.
- Modul-Verschiebung nach `store/llm_run_store.py` → **Phase 4**.

## Kritische Dateien

- `src/youtube_code/utils/llm_run_store.py` — neu anzulegen.
- `scripts/adhoc/migrate_llm_runs_to_store.py` — neu anzulegen.
- `scripts/adhoc/verify_llm_runs_migration.py` — neu anzulegen.
- `src/youtube_code/utils/transcript_store.py` /
  `screening_state_store.py` — Referenzmuster für Modul-/Migrations-/
  Verify-Stil (Phase 3b/3c).
- `src/youtube_code/llm_analysis/registry/run_registry.py` — Quelle des
  `REGISTRY_COLUMNS`-Schemas, bleibt in dieser Phase unangetastet (12
  Call-Sites hängen noch daran, Umstellung ist Phase 4).
- `src/youtube_code/politics_screening/screening_config.py` (`REGISTRY_PATH`,
  Zeile 49) und `src/youtube_code/segment_analysis/segment_analysis_config.py`
  (`REGISTRY_PATH`, Zeile 10) — die beiden divergierenden aktiven Pfade,
  bleiben in dieser Phase unangetastet (Phase 4 stellt Call-Sites um).
- `src/youtube_code/llm_analysis/registry/runs_registry.csv` (25 Zeilen),
  `llm_analysis/registry/runs_registry.csv` (Repo-Root, 19 Zeilen),
  `runs_registry_legacy.csv` (25 Zeilen), `runs_registry_old.csv` (14 Zeilen)
  — die vier Quellen, alle unangetastet lassen.

## Verifikation

1. `PYTHONPATH=src python scripts/adhoc/migrate_llm_runs_to_store.py` läuft
   fehlerfrei durch, Preflight-/Nachlauf-Zahlen plausibel (25/19/25/14 = 83
   erwartet).
2. `PYTHONPATH=src python scripts/adhoc/verify_llm_runs_migration.py` meldet
   OK für alle vier Quellen (vollständiger Feld-Vergleich, keine Stichprobe).
3. `python -c "from youtube_code.utils.llm_run_store import total_count;
   print(total_count())"` liefert 83.
4. `source_counts()` liefert exakt `{screening_active: 25,
   segment_analysis_active: 19, screening_legacy: 25, gemini_old: 14}`.
5. Zweiter Lauf von `migrate_llm_runs_to_store.py` (Idempotenz-Test):
   `total_count()` bleibt unverändert bei 83, keine Fehler.
6. `RESTRUCTURING_PROGRESS.md` um einen Phase-3d-Abschnitt (Status, Datum,
   Kennzahlen, offene Folgepunkte für Phase 4, Konsolidierungs-Vorschlag aus
   Abschnitt 6) ergänzt.

Damit ist nach Abschluss dieser Session **Phase 3 (Format-Migration)
vollständig geplant** — alle vier Teilschritte (3a Video-Metadaten, 3b
Transkripte, 3c Screening-State, 3d LLM-Runs) haben entweder einen
umgesetzten oder einen freigabefähigen Plan-Stand. Nächster Schritt danach:
Phase 4 (Code-Reorganisation), die die in 3a–3d aufgeschobenen Call-Site-
Umstellungen bündelt.

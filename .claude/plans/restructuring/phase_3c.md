# Phase 3c — Screening-State → `data/raw/screening_state.sqlite`

## Context

Teil der laufenden Repo-Restrukturierung (`.claude/restructuring/RESTRUCTURING_PLAN.md`,
Fortschritt in `RESTRUCTURING_PROGRESS.md`). Phase 3a (Video-Metadaten) und 3b
(Transkripte) sind abgeschlossen; Phase 3c überträgt denselben Ansatz auf den
Screening-State. Quelle ist `data/samples/russia/longitudinal_screening_state.csv`
(1,3 GB, 1.012.206 Zeilen, 19 Spalten) — die zentrale Tabelle des Longitudinal-
Screening-Workflows (ein Video = eine Kandidatenzeile mit Runden-Zuordnung und
Politik-Labels).

**Konkretes strukturelles Problem, das diese Phase adressiert:** Jeder der vier
Schreib-Orte (`append_channels_to_state.py`, `create_longitudinal_screening.py`,
`assign_postwar_baseline.py`, `update_screening_state.py`) lädt den kompletten
State als pandas-DataFrame, ändert eine Teilmenge der Zeilen/Spalten im Speicher
und schreibt die **komplette** Datei per `to_csv` neu — drei der vier Orte legen
davor zusätzlich per `shutil.copy2`/`to_csv` eine **komplette Vollkopie** als
Backup an (`state_backups/politics_screening_state_before_<run_id>.csv`,
`*.before_postwar_assignment.csv`). Das war die Ursache der in Phase 1 bereits
einmalig bereinigten ~19-GB-Backup-Flut, und erzeugt bei jedem weiteren
Screening-Lauf erneut 1,3 GB pro Vollkopie. Zwei solcher Vollkopien liegen
aktuell schon wieder in `state_backups/` (`before_run_0024.csv`,
`before_run_0025.csv`, zusammen ~2,6 GB), plus ein weiterer Vollkopie-Backup
`longitudinal_screening_state.csv.bak_pre_27channels_step3` (1,29 GB) aus der
zwischenzeitlichen Fachaufgabe.

Wie in Phase 3a/3b liefert diese Session **nur den Plan** — Umsetzung erfolgt in
einer späteren Session (Nutzer-Standing-Entscheidung für die gesamte
Restrukturierung, siehe `project-restructuring-decisions`-Memory). Der Nutzer hat
bestätigt, dass aktuell kein Screening-Batch läuft — die Migration selbst ist
damit sicher durchführbar, sobald sie freigegeben wird.

## Recherche-Befunde (verifiziert)

- **Schema der CSV** (`pd.read_csv(..., nrows=5)`): `video_id, channel_id,
  channel_title, published_at, title, description, period, interval_index,
  interval_label, rank_within_period, candidate_rank,
  target_political_per_interval, target_with_buffer_per_interval,
  politics_title, politics_title_desc, politics_final, screening_round,
  selected_for_transcript, is_transcript_reserve`.
- **Zeilenzahl/Eindeutigkeit** (voller Spalten-Scan über 8 Kernspalten):
  1.012.206 Zeilen, **0 doppelte `video_id`**, 0 fehlende `video_id` — anders als
  bei Transkripten (Phase 3b) ist `video_id` hier bereits strukturell eindeutig,
  weil `normalize_video_ids()` in `update_screening_state.py` das bei jedem Laden
  erzwingt (wirft bei Duplikaten). Migration ist damit ein einfacher Einmal-Import
  aus **einer** Quelle, kein Mehrquellen-Merge wie in Phase 3a.
- **Nullable-Spalten:** `politics_title`/`politics_final` je 699.134 NULL (313.072
  gescreente Zeilen), `politics_title_desc` 954.143 NULL (nur bei
  `politics_title == -1` befüllt), `screening_round` bis 10 (aktueller Stand),
  `selected_for_transcript`/`is_transcript_reserve` **aktuell 100 % NULL** (Feature
  aus `longitudinal_config.py` `RESERVE_TRANSCRIPTS_PER_PERIOD` aber noch nicht in
  Betrieb) — Spalten werden trotzdem mitmigriert, rein informativ NULL.
- **Vier aktive Schreib-Orte**, alle im Muster "State komplett laden → Teilmenge
  in-memory ändern → komplett neu schreiben" (kein Skript macht heute schon ein
  gezieltes Zeilen-Update):
  - `longitudinal/append_channels_to_state.py` — hängt komplette neue Zeilen an
    (INSERT-artig), kein automatisches Backup (Docstring verlangt manuelles
    Backup vom Nutzer).
  - `longitudinal/create_longitudinal_screening.py` (`update_state_with_round`) —
    setzt `screening_round` für die in dieser Runde ausgewählten Zeilen.
  - `longitudinal/assign_postwar_baseline.py` — setzt `interval_index`,
    `interval_label`, `target_political_per_interval`,
    `target_with_buffer_per_interval` für bestimmte Zeilen; schreibt vorher ein
    Vollkopie-Backup.
  - `update_screening_state.py` (Haupt-Merge-Skript) — setzt `politics_title` /
    `politics_title_desc` / `politics_final` für die Zeilen einer Runde;
    `validate_state_consistency()` erzwingt danach klare Invarianten (u. a.:
    Labels werden nie überschrieben, nur von NULL auf einen Wert gesetzt);
    schreibt vorher ein Vollkopie-Backup.
- Alle anderen Referenzen auf `STATE_FILE`/die State-CSV im Repo sind entweder
  auskommentiert oder tot (`diagnose.py`, `find_missing_screened_channels.py`,
  `merge_description_classification_runs.py`) — keine weiteren aktiven Leser
  außerhalb der vier oben genannten Skripte.
- Zielmuster `video_registry.py`/`transcript_store.py` (Phase 3a/3b):
  `sqlite3.connect(DB_PATH, timeout=30)` + WAL-Mode + `busy_timeout`, eigene
  Connection je Aufruf, COALESCE-Upsert-Pattern, `_chunks()`-Helper für
  `IN (...)`-Queries, Migrations-/Verify-Skript-Stil mit `.bak_pre_migration`
  und Stichproben-Feld-Vergleich.
- Speicherort-Präzedenzfall: Phase 3a/3b legen die Stores unter `data/raw/`
  ab (nicht `data/store/`, der Zielordner aus dem ursprünglichen Plan-Text kommt
  gebündelt erst in Phase 5) — Phase 3c folgt demselben Muster.

## Design-Entscheidungen für diese Session

- **Eine flache Tabelle**, kein Aufsplitten wie bei `videos`/`video_details` in
  Phase 3a: Es gibt nur eine Quelle (die CSV selbst, kein Mehrquellen-Merge), und
  alle 19 Spalten gehören zu einem einzigen, zusammenhängenden
  Screening-Datensatz pro Video — eine zweite Tabelle würde hier keinen
  Kosten-Vorteil bringen, nur Join-Aufwand.
- **Schreib-Primitive: generischer `upsert_state_rows()`** nach demselben
  COALESCE-Muster wie `video_registry.upsert_videos` (nicht das
  "ganze-Zeile-gewinnt"-Muster aus `transcript_store`, das dort wegen konkurrierender
  Scrape-*Versuche* nötig war). Das Storage-Modul setzt nur die Mechanik um
  (Spalte wird überschrieben, wenn ein neuer Wert übergeben wird, sonst bleibt der
  alte erhalten); **welche Spalten ein Call-Site übergibt und ob z. B. Labels vor
  Überschreiben geschützt werden müssen, bleibt Business-Logik der aufrufenden
  Skripte** — das ist heute genauso (`validate_state_consistency`,
  `expected_title_rows`-Maske) und wird erst in Phase 4 auf die neuen Call-Sites
  übertragen, nicht in dieser Phase entschieden. Das hält das Storage-Modul
  konsistent mit dem bereits etablierten Muster und vermeidet, eine Vier-Wege-
  Entscheidung über inkompatible Update-Semantiken vorwegzunehmen, die eigentlich
  erst beim tatsächlichen Umbau der vier Call-Sites in Phase 4 getroffen werden muss.
- **Kein `screening_state_history`-Diff-Table** in dieser Phase (im
  ursprünglichen Plan-Text als "optional" markiert). Scope bleibt wie bei 3a/3b:
  Migration + Verifikation + Storage-Modul, kein neues Feature. Bleibt offener
  Folgepunkt für Phase 4, falls dort ein Audit-Trail gewünscht wird.
- **`data/raw/screening_state.sqlite`**, Modul
  `src/youtube_code/utils/screening_state_store.py` (analog `transcript_store.py`,
  eigene Datei statt Erweiterung von `video_registry.py` — andere Datendomäne).
  Wandert wie die anderen Stores in Phase 4 nach `store/`.
- **CSV bleibt unangetastet liegen**, keine Löschung von State-Backups in dieser
  Phase (siehe eigener Abschnitt unten für die separate Aufräum-Empfehlung).

## 1. Schema

```sql
CREATE TABLE IF NOT EXISTS screening_state (
    video_id                         TEXT PRIMARY KEY,
    channel_id                       TEXT NOT NULL,
    channel_title                    TEXT,
    published_at                     TEXT,
    title                            TEXT,
    description                      TEXT,
    period                           INTEGER,
    interval_index                   INTEGER,
    interval_label                   TEXT,
    rank_within_period               INTEGER,
    candidate_rank                   INTEGER,
    target_political_per_interval    INTEGER,
    target_with_buffer_per_interval  INTEGER,
    politics_title                   INTEGER,  -- -1/0/1/NULL
    politics_title_desc              INTEGER,  -- -1/0/1/NULL
    politics_final                   INTEGER,  -- -1/0/1/NULL
    screening_round                  INTEGER,
    selected_for_transcript          INTEGER,  -- 0/1/NULL, aktuell immer NULL
    is_transcript_reserve            INTEGER   -- 0/1/NULL, aktuell immer NULL
);

CREATE INDEX IF NOT EXISTS idx_screening_state_channel ON screening_state(channel_id);
CREATE INDEX IF NOT EXISTS idx_screening_state_round   ON screening_state(screening_round);
```

Begründung Indizes: `channel_id` und `screening_round` sind die zwei
Filter-/Gruppierungs-Spalten, über die alle vier Schreib-Skripte und
`load_screening_state` heute per Maske selektieren (`round_mask`,
kanalweise Fenster-Iteration in `assign_postwar_baseline.py`).

## 2. `src/youtube_code/utils/screening_state_store.py` (neu)

Modul-Docstring erklärt Zweck, vorläufigen Speicherort (→ Phase 4 nach `store/`),
und dass Label-Schutzregeln bewusst Caller-Verantwortung bleiben (siehe oben).

- `_connect() -> sqlite3.Connection` — WAL-Mode, Schema anlegen, wie in
  `video_registry.py`/`transcript_store.py`.
- `_chunks(iterable, size=500)` — wie in `video_registry.py`.
- `_to_nullable_int(value)` — robuste Konvertierung für die 9 nullable
  Integer-Spalten (NaN/None/float → int/None).
- `upsert_state_rows(records: list[dict]) -> int` — COALESCE-Upsert über alle
  19 Spalten (`video_id` Pflichtfeld je Record), gibt Anzahl tatsächlich
  geänderter Zeilen zurück (`con.total_changes`-Differenz, analog Phase 3a/3b).
- `get_state(video_ids=None, channel_ids=None, screening_round=None) ->
  pd.DataFrame` — gechunkte Filter-Query (Batch 500 bei `IN (...)`), ohne Filter
  liefert sie die komplette Tabelle (Ersatz für `pd.read_csv(STATE_FILE)`).
- `total_count() -> int`.
- `round_counts() -> pd.DataFrame` — `GROUP BY screening_round`, Sanity-Helfer.
- `label_counts() -> pd.DataFrame` — `GROUP BY politics_final`, Sanity-Helfer.
- `export_csv(output_path) -> int` — Snapshot-Export mit identischer
  Spaltenreihenfolge wie die Quell-CSV (hält bestehende Excel-/Ad-hoc-Konsumenten
  während der Übergangszeit bis Phase 4 kompatibel).

## 3. Migrationsskript `scripts/adhoc/migrate_screening_state_to_store.py` (neu)

Einmaliges Skript, löscht keine Quelldateien, idempotent (Upsert-basiert).

1. **Sicherheits-Checkpoint:** Prozessliste auf laufende
   `create_longitudinal_screening.py`/`update_screening_state.py`/
   `append_channels_to_state.py`/`assign_postwar_baseline.py`-Instanzen prüfen,
   vor dem eigentlichen Lauf abbrechen falls ein Treffer (Nutzer hat für den
   aktuellen Moment bereits "kein Screening läuft" bestätigt, Skript prüft es
   trotzdem technisch nach, analog zum expliziten Checkpoint in Phase 3b).
2. Backup der Ziel-DB falls bereits vorhanden (`*.bak_pre_migration`, idempotent).
3. CSV mit `pd.read_csv(..., dtype={"video_id": "string", "channel_id": "string"},
   low_memory=False)` einmalig vollständig laden (bei 8 Spalten dauerte das
   ~20 s; mit allen 19 Spalten inkl. `description`-Freitext entsprechend länger,
   aber unproblematisch als Einmal-Migration).
4. Preflight: `video_id`-Eindeutigkeit erneut prüfen (Referenzwert 1.012.206,
   0 Duplikate) — bei Abweichung abbrechen, nicht automatisch weitermachen.
5. NaN → `None`-Konvertierung (`df.astype(object).where(pd.notnull(df), None)`,
   wie in Phase 3b) für alle nullable Spalten.
6. `upsert_state_rows()` in Chunks von 5.000 Zeilen aufrufen, Fortschritts-Log
   alle ~100.000 Zeilen.
7. `total_count()` vor/nach vergleichen, `round_counts()`/`label_counts()`
   ausgeben.

## 4. Verifikationsskript `scripts/adhoc/verify_screening_state_migration.py` (neu)

- Zeilenzahl-Check: CSV (`video_id`-Spalte, voller Scan) vs.
  `SELECT COUNT(*) FROM screening_state` — OK/MISMATCH.
- Reservoir-Sampling (`SAMPLE_SIZE=300`) über `video_id`, plus gezielte
  Stichproben aus jeder `politics_final`-Ausprägung (-1/0/1/NULL) und aus
  `screening_round=10` (aktuellster Stand) — Feld-für-Feld-Vergleich aller 19
  Spalten gegen eine Read-only-Connection (`file:{db_path}?mode=ro`).
- **Konsistenz-Check statt Neuerfindung:** `updated_screening_state.load_state()`
  bzw. dessen `validate_state_consistency()`-Funktion auf eine aus der DB
  exportierte DataFrame (`get_state()`) anwenden — bestätigt, dass die
  migrierten Daten dieselben Invarianten erfüllen wie die Quell-CSV, ohne die
  Validierungslogik zu duplizieren.
- Abschließende `round_counts()`/`label_counts()`-Gegenprobe gegen
  `value_counts()` der Quell-CSV.

## 5. Reihenfolge & Sicherheits-Checkpoints

**Vor der Migration:** Sicherheits-Checkpoint (Punkt 1 oben) technisch prüfen,
nicht nur auf die Nutzeraussage vertrauen; keine neuen Dependencies nötig.

**Nach der Migration:** `verify_screening_state_migration.py` → OK für
Zeilenzahl, Stichprobe und Konsistenz-Check; `RESTRUCTURING_PROGRESS.md` um
Phase-3c-Abschnitt ergänzen (Status, Datum, Kennzahlen). CSV bleibt liegen.

## 6. Separates Aufräum-Angebot (kein Teil der Migration selbst)

Der Vollkopie-Backup `longitudinal_screening_state.csv.bak_pre_27channels_step3`
(1,29 GB) wurde in Phase 3a als "Rückfallebene bis Screening-Runde 009 verarbeitet
ist" markiert — Runde 009 (Titel) und Runde 010 (Titel + Beschreibung) sind laut
`RESTRUCTURING_PROGRESS.md` inzwischen gemergt. Die ursprüngliche Rückhalte-
Begründung ist damit erfüllt; die Datei ist ein Aufräumkandidat nach demselben
Muster wie die in Phase 1 bereits gelöschten `state_backups/`-Snapshots (Zeilenzahl-
Vergleich gegen aktuellen State vor Löschung). Das ist inhaltlich Phase-1-artiges
Aufräumen, kein Format-Migrations-Thema — wird hier nur als Vorschlag notiert,
nicht automatisch mit erledigt; separate Freigabe empfohlen.

## 7. Explizit NICHT Teil von Phase 3c

- Umstellung der vier Schreib-Orte (`append_channels_to_state.py`,
  `create_longitudinal_screening.py`, `assign_postwar_baseline.py`,
  `update_screening_state.py`) auf `upsert_state_rows()` statt CSV-Vollkopie →
  **Phase 4**. Erst dort wird auch entschieden, welche Spalten je Call-Site
  übergeben werden und wie das Backup-Vollkopie-Verhalten entfernt/ersetzt wird.
- Löschen der CSV → erst nach Phase-4-Umstellung aller Konsumenten.
- Löschen der `state_backups/`-Vollkopien (`before_run_0024.csv`,
  `before_run_0025.csv`) und von `.bak_pre_27channels_step3` → optionaler,
  separat freizugebender Schritt (siehe Abschnitt 6).
- `screening_state_history`-Diff-Table (optional laut ursprünglichem Plan-Text).
- Sample-Membership-Ableitung aus `video_search_hits` (offener Folgepunkt aus
  Phase 3a, unabhängig von 3c).
- `.claude/CLAUDE.md`-Regel-Update (Source-of-Truth-Hinweis auf die neuen Stores)
  → **Phase 5**, analog zur bereits offenen Transkript-Regel.
- Modul-Verschiebung nach `store/screening_store.py` → **Phase 4**.

## Kritische Dateien

- `src/youtube_code/utils/screening_state_store.py` — neu anzulegen.
- `scripts/adhoc/migrate_screening_state_to_store.py` — neu anzulegen.
- `scripts/adhoc/verify_screening_state_migration.py` — neu anzulegen.
- `src/youtube_code/utils/video_registry.py` — Referenzmuster für
  COALESCE-Upsert (Phase 3a).
- `src/youtube_code/utils/transcript_store.py` — Referenzmuster für
  Modul-/Migrations-/Verify-Stil (Phase 3b).
- `src/youtube_code/politics_screening/update_screening_state.py` — liefert
  `validate_state_consistency()` für den Verify-Konsistenz-Check; bleibt sonst
  unangetastet.
- `src/youtube_code/politics_screening/screening_config.py` — `STATE_FILE`,
  bleibt in dieser Phase unangetastet (Phase 4 stellt Call-Sites um).
- `data/samples/russia/longitudinal_screening_state.csv` — Quelle, 1,3 GB,
  unangetastet lassen.

## Verifikation

1. `PYTHONPATH=src python scripts/adhoc/migrate_screening_state_to_store.py`
   läuft fehlerfrei durch, Preflight-Zahlen plausibel (1.012.206 Zeilen erwartet).
2. `PYTHONPATH=src python scripts/adhoc/verify_screening_state_migration.py`
   meldet OK für Zeilenzahl, Stichprobe und Konsistenz-Check.
3. `python -c "from youtube_code.utils.screening_state_store import total_count;
   print(total_count())"` liefert 1.012.206.
4. Zweiter Lauf von `migrate_screening_state_to_store.py` (Idempotenz-Test):
   `total_count()` bleibt unverändert, keine Fehler.
5. `RESTRUCTURING_PROGRESS.md` um einen Phase-3c-Abschnitt (Status, Datum,
   Kennzahlen, offene Folgepunkte für Phase 4, Aufräum-Angebot aus Abschnitt 6)
   ergänzt.
</content>

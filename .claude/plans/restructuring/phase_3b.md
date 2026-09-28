# Phase 3b — Transkripte → `data/raw/transcripts.sqlite`

## Context

Teil der laufenden Repo-Restrukturierung (`.claude/restructuring/RESTRUCTURING_PLAN.md`,
Fortschritt in `RESTRUCTURING_PROGRESS.md`). Phase 3a hat Video-Metadaten bereits
erfolgreich nach `video_registry.sqlite` migriert; Phase 3b überträgt denselben
Ansatz auf die Transkript-Rohdaten. Quelle ist laut `.claude/CLAUDE.md`-Projektregel
ausschließlich `data/transcripts/all_transcripts_segments.csv` (2,72 GB) — die einzige
Source of Truth für Transkript-Verfügbarkeit. Ziel: eine zentrale, indizierte,
duplikatfreie SQLite-Ablage statt einer wachsenden CSV mit bekannten strukturellen
Problemen (eingebettete Zeilenumbrüche, reine Append-Schreibweise ohne Dedupe, ein
teures Voll-Neuschreib-Backup alle 500 API-Requests).

Wie in Phase 3a liefert diese Session **nur den Plan** — Umsetzung erfolgt in einer
späteren Session (Nutzer-Standing-Entscheidung für die gesamte Restrukturierung).

### In dieser Session bereits entschiedene Eckpunkte
- **Format:** SQLite (nicht Parquet) — Zugriffsmuster ist Key-Lookup
  (`WHERE video_id IN (...)`), konsistent mit den übrigen Stores.
- **Speicherort:** `data/raw/transcripts.sqlite` (nicht `data/store/`) — Nutzerentscheidung,
  konsistent mit dem Phase-3a-Präzedenzfall (`video_registry.sqlite` liegt ebenfalls in
  `data/raw/`). Der `data/store/`-Zielordner samt `paths.py`-Bereinigung kommt gebündelt
  erst in Phase 5.
- **Neues Modul:** `src/youtube_code/utils/transcript_store.py` (eigene Datei, nicht in
  `video_registry.py` eingebaut — andere Datendomäne). Wandert in Phase 4 nach `store/`.
- **Scope-Grenze:** Nur Migration + Verifikation. Scraper-Schreibverhalten und
  Downstream-Leseskripte bleiben unangetastet (Phase 4). Die CSV wird **nicht gelöscht**.

## Recherche-Befunde (verifiziert)

- Header: `video_id,transcript_segments,language_code,is_generated,status`.
  `transcript_segments` ist JSON-Array-Text (`{"start","duration","text"}`-Objekte),
  kann leer/None sein. `status` ∈ `"OK"` / `"Kein Transkript"` / `f"Fehler: {e}"` (Freitext).
- **Eingebettete Zeilenumbrüche real und quantifiziert:** 91.036 physische Zeilen,
  aber nur **72.443 echte Records** — Differenz durch mehrzeilige Exception-Texte im
  `status`-Feld (`transcript_scraping_segments.py:233-239`). Datei ist aber korrekt
  RFC4180-gequotet; `pandas.read_csv` liest sie schon jetzt in bestehenden Skripten
  korrekt — kein naives Zeilen-Splitting verwenden.
- **Kein Upsert im aktuellen Scraper:** `save_to_csv()` (transcript_scraping_segments.py)
  schreibt nur per Append (`mode="a"`), Dedupe nur über einen In-Memory-Resume-Filter
  beim Scraper-Start. `video_id` ist daher in der CSV **nicht eindeutig** — Migration
  muss selbst deduplizieren.
- Bekannter Testfall für den Newline-Sonderfall: `video_id=QsVgwJ40-zo`.
- Zielmuster `src/youtube_code/utils/video_registry.py`: `sqlite3.connect(DB_PATH, timeout=30)`
  + `PRAGMA journal_mode=WAL` + `PRAGMA busy_timeout=30000`, `CREATE TABLE IF NOT EXISTS`
  bei jedem Connect, je Aufruf eigene Connection (`try/finally` fürs Schließen),
  COALESCE-Upsert-Pattern, `_chunks()`-Helper (Batch 500) für `IN (...)`-Queries.
  Import: `from youtube_code.config import RAW` (per `config/__init__.py` re-exportiert
  aus `paths.py`) — gleiches Muster für `TRANSCRIPTS`.
- Migrations-/Verify-Stil aus Phase 3a (`scripts/adhoc/migrate_video_metadata_to_registry.py`,
  `scripts/adhoc/verify_video_metadata_migration.py`): Vorab-Backup mit `.bak_pre_*`-Suffix
  (idempotent, nicht überschreiben), batchweises Lesen mit Fortschritts-Logging,
  Read-only-Connection (`file:{db_path}?mode=ro`) fürs Verify-Skript, Stichproben-Vergleich
  Feld-für-Feld.

## 1. Schema

Neue Datei `data/raw/transcripts.sqlite`, Tabelle `transcripts`:

```sql
CREATE TABLE IF NOT EXISTS transcripts (
    video_id            TEXT PRIMARY KEY,
    transcript_segments TEXT,     -- JSON-Text; NULL wenn kein Transkript/Fehler
    language_code       TEXT,
    is_generated         INTEGER, -- 0/1/NULL
    status               TEXT,    -- "OK" | "Kein Transkript" | "Fehler: <Freitext, ggf. mehrzeilig>"
    n_segments           INTEGER  -- abgeleitet: len(json.loads(transcript_segments)); billig beim Upsert mitberechnet,
                                   -- macht Coverage-Queries günstig ohne JSON-Parsing bei jeder Abfrage
)
```

Kein zusätzlicher Index nötig (PK deckt `video_id`-Lookups ab; ~72k Zeilen macht
`GROUP BY status` als Full-Scan unproblematisch). Keine zweite Detail-Tabelle wie bei
Videos — ein Transkript-Record ist atomar, keine teuren/billigen Feldgruppen.

## 2. Dedupe-Regel

Anders als `video_registry.upsert_videos` (Feld-für-Feld-COALESCE über **komplementäre**
Quellen) gilt hier **Ganze-Zeile-gewinnt**: ein Duplikat ist ein wiederholter Scrape-
*Versuch* desselben Videos, kein Teil-Feld einer anderen Quelle — Felder aus zwei
verschiedenen Versuchen zu mischen wäre inkonsistent.

Priorität: `"OK"` (Rang 0) > `"Kein Transkript"` (Rang 1) > alles andere / `"Fehler: ..."`
(Rang 2). Begründung: `"Kein Transkript"` ist ein definitives API-Ergebnis
(`NoTranscriptFound`), `"Fehler: ..."` fast immer transient (Rate-Limit, Timeout) und
trifft keine Aussage über echte Verfügbarkeit — ein späterer Fehler-Eintrag darf ein
früheres `"OK"` nicht überschreiben. Bei gleichem Rang gewinnt der zuletzt geschriebene
Datensatz (Last-Wins).

Die Regel steckt direkt in der `ON CONFLICT`-Klausel von `upsert_transcripts()` (nicht im
Migrationsskript) — dadurch gilt sie automatisch auch für künftige Phase-4-Direktschreib-
vorgänge des Scrapers, und die Migration kann die CSV chunk-weise in beliebiger
Reihenfolge durchlaufen:

```sql
INSERT INTO transcripts
    (video_id, transcript_segments, language_code, is_generated, status, n_segments)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(video_id) DO UPDATE SET
    transcript_segments = excluded.transcript_segments,
    language_code       = excluded.language_code,
    is_generated         = excluded.is_generated,
    status               = excluded.status,
    n_segments           = excluded.n_segments
WHERE (CASE WHEN excluded.status = 'OK' THEN 0
            WHEN excluded.status = 'Kein Transkript' THEN 1
            ELSE 2 END)
      <= (CASE WHEN transcripts.status = 'OK' THEN 0
               WHEN transcripts.status = 'Kein Transkript' THEN 1
               ELSE 2 END)
```

(`<=` statt `<`: bei gleichem Rang wird trotzdem überschrieben → Last-Wins innerhalb
derselben Prioritätsstufe.)

## 3. `src/youtube_code/utils/transcript_store.py` (neu)

Modul-Docstring erklärt Zweck, Dedupe-Regel, vorläufigen Speicherort (→ Phase 4 nach
`store/`). Funktionen (Signaturen, analog zu `video_registry.py`):

- `_to_bool_int(value)` — robuste `is_generated`-Konvertierung (bool/str/NaN/None → 0/1/None).
- `_n_segments(transcript_segments_json)` — Segmentanzahl aus JSON-Text, `None` bei leer/kaputt.
- `_connect() -> sqlite3.Connection` — WAL-Mode, Schema anlegen, wie in `video_registry.py`.
- `upsert_transcripts(records: list[dict]) -> int` — Kernfunktion, wendet die Priorität-
  Upsert-Regel an; `records`-dicts brauchen `video_id`, `transcript_segments` darf JSON-Text
  oder bereits dekodierte Liste sein (wird serialisiert). Gibt Anzahl **tatsächlich
  angewendeter** Schreibvorgänge zurück (`con.total_changes` vor/nach), nicht Anzahl
  versuchter Zeilen — relevant fürs Migrations-Logging ("wie viele wegen Priorität übersprungen").
- `get_transcripts(video_ids) -> dict[video_id, dict]` — gechunkte `IN (...)`-Query
  (Batch 500, wie `video_registry._chunks`), `transcript_segments` wird zurückgegeben.
- `get_transcript(video_id) -> dict | None` — Einzel-Wrapper um `get_transcripts`.
- `attempted_video_ids() -> set` — alle `video_id`s mit irgendeinem Scrape-Versuch (jeder
  Status). Ersetzt in Phase 4 das aktuelle `pd.read_csv(usecols=["video_id"])`-Muster in
  `get_baseline_ids.py` und den Resume-Filter im Scraper.
- `has_transcript(video_ids) -> set` — Teilmenge mit `status='OK'` und vorhandenem Transkript.
- `total_count() -> int`.
- `status_counts() -> pd.DataFrame` — Sanity-Check-Helfer (`GROUP BY status`).
- `export_jsonl(output_path, include_segments=True) -> int` — Snapshot-Export, standardmäßig
  MIT `transcript_segments` (das ist hier der Nutzinhalt, anders als der schlanke Default
  bei `video_registry.export_jsonl`).

## 4. Migrationsskript `scripts/adhoc/migrate_transcripts_to_store.py` (neu)

Einmaliges Skript, löscht keine Quelldateien, idempotent (Upsert-basiert statt
destruktivem Neuaufbau — mehrfaches Ausführen überschreibt nie einen besseren
vorhandenen Datensatz).

- `preflight_duplicate_report() -> (n_rows, n_unique)`: liest **nur** die `video_id`-Spalte
  chunk-weise (billig), zählt Vorkommen, druckt Zeilen-/Duplikat-Übersicht. **Sicherheits-
  Checkpoint:** Ergebnis (~72.443 erwartete Records) vor dem eigentlichen Lauf mit den
  Recherche-Referenzwerten abgleichen; bei starker Abweichung abbrechen.
- `migrate()`: liest die volle CSV mit `pd.read_csv(..., chunksize=500)` (konsistent mit
  dem `CSV_CHUNKSIZE=500`-Muster in `segment_transcripts.py`), wandelt NaN robust zu
  `None` (`chunk.astype(object).where(pd.notnull(chunk), None)` — sonst bindet `sqlite3`
  NaN als `REAL NaN` statt `NULL`), ruft `upsert_transcripts()` je Chunk auf,
  Fortschritts-Log alle ~10.000 Zeilen.
- `main()`: Backup der Ziel-DB falls bereits vorhanden (`*.bak_pre_migration`, idempotent,
  nicht überschreiben) → Preflight → `total_count()` vorher → Migration → `total_count()`
  nachher, Abgleich gegen `n_unique` aus dem Preflight (WARNUNG bei Abweichung) →
  `status_counts()`-Ausgabe.

## 5. Verifikationsskript `scripts/adhoc/verify_transcripts_migration.py` (neu)

- Reservoir-Sampling (`SAMPLE_SIZE=200`) über die `video_id`-Spalte, **plus erzwungener
  Sonderfall `QsVgwJ40-zo`** (bekannter embedded-newline-Fall).
- Für die Ziel-`video_id`s: **ein voller CSV-Chunk-Durchlauf**, der alle Vorkommen dieser
  IDs einsammelt (Duplikate können irgendwo in der Datei liegen) — `expected_winner()`
  simuliert dieselbe Prioritäts-/Last-Wins-Regel wie die SQL-`ON CONFLICT`-Klausel in
  Python, über alle gesammelten Vorkommen je ID.
- Vergleich Feld für Feld (`transcript_segments` JSON-normalisiert, `language_code`,
  `status`, `is_generated`, `n_segments`) gegen eine **Read-only-Connection**
  (`file:{db_path}?mode=ro`) auf `transcripts.sqlite`.
- Expliziter Zusatz-Check für `QsVgwJ40-zo`: genau 1 CSV-Vorkommen, Status enthält `\n`,
  DB-Status ist Zeichen-für-Zeichen identisch zur CSV-Zelle (Beweis, dass der Newline
  korrekt migriert wurde, nicht abgeschnitten).
- Abschließender Zeilenzahl-Check: eindeutige `video_id`s (voller CSV-Scan, nur `video_id`-
  Spalte) vs. `SELECT COUNT(*) FROM transcripts` — OK/MISMATCH.

## 6. Reihenfolge & Sicherheits-Checkpoints

**Vor der Migration:** Preflight-Ausgabe gegen Referenzwerte prüfen; sicherstellen, dass
kein `transcript_scraping_segments.py`-Lauf parallel auf dieselbe CSV schreibt; keine
neuen Dependencies nötig (pandas bereits genutzt, `sqlite3` Stdlib).

**Nach der Migration:** `verify_transcripts_migration.py` → OK für Stichprobe, Zeilenzahl
und `QsVgwJ40-zo`-Sonderfall; `status_counts()`-Summe gegen `total_count()` plausibilisieren;
2–3 Records manuell stichprobenartig gegenlesen; `RESTRUCTURING_PROGRESS.md` mit Status,
Datum und Kennzahlen (Gesamtrecords, Duplikat-Anzahl, finale `total_count()`) ergänzen.
CSV bleibt liegen.

## 7. Explizit NICHT Teil von Phase 3b

- Scraper-Umstellung (`transcript_scraping_segments.py` auf `upsert_transcripts()`/
  `attempted_video_ids()` statt CSV-Append) → **Phase 4**.
- Downstream-Leseskripte umstellen (`process_scraped_segments.py`,
  `new_analysis/segment_transcripts.py`, `scraping/get_baseline_ids.py`,
  `scripts/adhoc/segment_analysis_result_checks.py`,
  `scripts/adhoc/sample_feasibility_helpers.py`) → **Phase 4**.
- Löschen der CSV → erst nach Phase-4-Umstellung aller Konsumenten.
- `.claude/CLAUDE.md`-Regel-Update (Transkript-Source-of-Truth → `data/store/transcripts.*`) → **Phase 5**.
- Modul-Verschiebung nach `store/transcript_store.py` → **Phase 4**.

## Kritische Dateien

- `src/youtube_code/utils/transcript_store.py` — neu anzulegen.
- `scripts/adhoc/migrate_transcripts_to_store.py` — neu anzulegen.
- `scripts/adhoc/verify_transcripts_migration.py` — neu anzulegen.
- `src/youtube_code/utils/video_registry.py` — Referenzmuster (Phase 3a).
- `data/transcripts/all_transcripts_segments.csv` — Quelle, 2,72 GB, unangetastet lassen.
- `src/youtube_code/config/paths.py` — liefert `RAW`/`TRANSCRIPTS` (re-exportiert über
  `config/__init__.py`, bestätigt: `from youtube_code.config import RAW` funktioniert
  bereits für `video_registry.py`).

## Verifikation

1. `PYTHONPATH=src python scripts/adhoc/migrate_transcripts_to_store.py` läuft fehlerfrei
   durch, Preflight-Zahlen plausibel (~72.443 Records erwartet).
2. `PYTHONPATH=src python scripts/adhoc/verify_transcripts_migration.py` meldet OK für
   Stichprobe, Zeilenzahl-Check und den `QsVgwJ40-zo`-Sonderfall.
3. `python -c "from youtube_code.utils.transcript_store import total_count; print(total_count())"`
   liefert eine plausible Zahl (~72k, abzüglich echter Duplikate).
4. Zweiter Lauf von `migrate_transcripts_to_store.py` (Idempotenz-Test): `total_count()`
   bleibt unverändert, keine Fehler.
5. `RESTRUCTURING_PROGRESS.md` um einen Phase-3b-Abschnitt (Status, Datum, Kennzahlen,
   offene Folgepunkte für Phase 4) ergänzt.
</content>

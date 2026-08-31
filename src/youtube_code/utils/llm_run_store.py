"""
Zentrale SQLite-Ablage fuer die LLM-Batch-Run-Registry (Prompt/Modell/
Datensatz/Zielvariable je an Gemini geschickten Batch-Job, siehe
youtube_code.llm_analysis.registry.run_registry.RunRegistry). Ersetzt vier
parallele CSV-Registries als Nachschlagewerk - Migration siehe
scripts/adhoc/migrate_llm_runs_to_store.py, Design-Hintergrund in
.claude/plans/phase_3d.md.

Vorlaeufiger Speicherort data/raw/llm_runs.sqlite (Phase 3d der
Restrukturierung) - wandert zusammen mit dem Modul in Phase 4 nach
data/store/ bzw. src/youtube_code/store/llm_run_store.py.

Kein globaler run_id-Namensraum: die vier Quell-CSVs haben je einen eigenen
run_id-Zaehler, der jeweils bei run_0001 beginnt und zwischen den Quellen
kollidiert (z.B. run_0001 existiert in allen vier Dateien mit voellig
unterschiedlichem Inhalt). Der Primaerschluessel ist daher ein synthetischer
`id INTEGER PRIMARY KEY AUTOINCREMENT`, eindeutig ist nur die Kombination
`(source, run_id)`. Die vier `source`-Werte und was dahintersteht:

    screening_active         - src/youtube_code/llm_analysis/registry/runs_registry.csv
                                (SRC-Pfad), Longitudinal-Politik-Screening
                                (Titel/Beschreibung), Ergebnisse in
                                outputs/llm/longitudinal/. Aktiv beschrieben
                                ueber politics_screening/screening_config.py:REGISTRY_PATH.
    segment_analysis_active  - llm_analysis/registry/runs_registry.csv
                                (Repo-Root-Pfad, KEIN src/), Segment-
                                Klassifikation (IDEOLOGIE/POPULISMUS/POSITION),
                                Ergebnisse in outputs/segment_analysis/. Aktiv
                                beschrieben ueber
                                segment_analysis/segment_analysis_config.py:REGISTRY_PATH.
    screening_legacy          - runs_registry_legacy.csv, fruehere
                                Screening-Runden 001-008 vor einem
                                Laufwerkswechsel. Nirgends im Code mehr
                                referenziert, referenzierte Ergebnisdateien
                                existieren physisch nicht mehr - nur die
                                Metadaten-Zeilen selbst sind Audit-Trail.
    gemini_old                 - runs_registry_old.csv, fruehe
                                populism_score-Laeufe. Nur im toten
                                merge_and_evaluate.py referenziert,
                                referenzierte Ergebnisdateien existieren
                                physisch nicht mehr.

Da alle vier Quellen historisch unterschiedliche Runs sind (kein inhaltliches
Duplikat wie bei video_registry), gibt es kein Feld-fuer-Feld-COALESCE ueber
Quellen hinweg - upsert_runs() dient nur der Idempotenz bei erneutem
Skriptlauf derselben Quelle ("ganze Zeile gewinnt" bei Konflikt auf
(source, run_id), analog transcript_store).

Nutzung:
    from youtube_code.utils.llm_run_store import (
        upsert_runs, get_runs, get_run, add_run, update_run,
    )
    upsert_runs("screening_active", records)  # Liste von dicts, REGISTRY_COLUMNS-Felder
    get_runs(dataset_id="main_transcripts", target_variable="ideology_score")
    get_run("screening_active", "run_0017")
    add_run("screening_active", prompt_id="PROMPT_32", ...)      # -> neue run_id
    update_run("screening_active", "run_0017", status="downloaded")

add_run()/update_run() sind duenne Komfortfunktionen ueber upsert_runs(),
die die bisherige RunRegistry.add_run()/update_run()-Aufrufform an den
Call-Sites nachbilden (Phase 4b der Restrukturierung, .claude/plans/
phase_4.md) - direkte upsert_runs()-Aufrufe bleiben fuer Bulk-Schreiben
(z.B. Migration) weiterhin der Normalfall.
"""
import sqlite3

from youtube_code.config import RAW

DB_PATH = RAW / "llm_runs.sqlite"

# Identisch zu RunRegistry.REGISTRY_COLUMNS
# (src/youtube_code/llm_analysis/registry/run_registry.py), ohne id/source.
REGISTRY_COLUMNS = [
    "run_id", "job_id", "status",
    "prompt_id", "prompt_number", "prompt_version",
    "model", "thinking_budget",
    "dataset_id", "dataset_version",
    "target_variable", "validation_basis",
    "created_at", "updated_at",
    "results_path", "notes",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_runs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    source            TEXT NOT NULL,
    run_id            TEXT NOT NULL,
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
)
"""

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_llm_runs_dataset ON llm_runs(dataset_id)",
    "CREATE INDEX IF NOT EXISTS idx_llm_runs_target  ON llm_runs(target_variable)",
]

_UPSERT_COLUMNS = ["source", "run_id"] + REGISTRY_COLUMNS[1:]  # run_id nur einmal

_UPDATE_CLAUSE = ",\n".join(
    f"    {col} = excluded.{col}" for col in REGISTRY_COLUMNS[1:]
)

_UPSERT_SQL = f"""
INSERT INTO llm_runs ({', '.join(_UPSERT_COLUMNS)})
VALUES ({', '.join('?' * len(_UPSERT_COLUMNS))})
ON CONFLICT(source, run_id) DO UPDATE SET
{_UPDATE_CLAUSE}
"""


def _to_nullable_int(value):
    """Wandelt thinking_budget robust in int/None (NaN/None/float/String)."""
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN
        return None
    if isinstance(value, str):
        s = value.strip()
        if s == "" or s.lower() == "nan":
            return None
        try:
            return int(float(s))
        except (TypeError, ValueError):
            return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.execute(_SCHEMA)
    for stmt in _INDEXES:
        con.execute(stmt)
    return con


def upsert_runs(source: str, records) -> int:
    """
    Schreibt eine Liste von Run-Dicts (REGISTRY_COLUMNS-Felder, mind.
    "run_id") fuer eine gegebene `source` in die zentrale Ablage. Konflikt-
    schluessel ist (source, run_id) - bei Konflikt gewinnt die ganze
    uebergebene Zeile (kein Merge zwischen Quellen, siehe Modul-Docstring).
    Gibt die Anzahl tatsaechlich angewendeter Schreibvorgaenge zurueck
    (con.total_changes-Differenz).
    """
    rows = []
    for r in records:
        run_id = r.get("run_id")
        if not run_id:
            continue
        row = [source, str(run_id).strip()]
        for col in REGISTRY_COLUMNS[1:]:
            value = r.get(col)
            if col == "thinking_budget":
                value = _to_nullable_int(value)
            row.append(value)
        rows.append(tuple(row))
    if not rows:
        return 0

    con = _connect()
    try:
        before = con.total_changes
        con.executemany(_UPSERT_SQL, rows)
        con.commit()
        after = con.total_changes
    finally:
        con.close()
    return after - before


def get_runs(source=None, dataset_id=None, target_variable=None, status=None):
    """
    Gibt ein DataFrame aller llm_runs-Spalten zurueck, gefiltert ueber jeden
    uebergebenen Parameter (UND-Verknuepfung). Ohne Filter komplette Tabelle.
    Ersatz fuer RunRegistry.get_runs(**filters).
    """
    import pandas as pd

    where = []
    params = []
    if source is not None:
        where.append("source = ?")
        params.append(source)
    if dataset_id is not None:
        where.append("dataset_id = ?")
        params.append(dataset_id)
    if target_variable is not None:
        where.append("target_variable = ?")
        params.append(target_variable)
    if status is not None:
        where.append("status = ?")
        params.append(status)

    query = "SELECT * FROM llm_runs"
    if where:
        query += " WHERE " + " AND ".join(where)

    con = _connect()
    try:
        return pd.read_sql_query(query, con, params=params)
    finally:
        con.close()


def next_run_id(source: str) -> str:
    """
    Naechste freie run_id fuer eine gegebene `source`, im Format "run_NNNN".
    Ersatz fuer RunRegistry._next_run_id() (src/youtube_code/llm_analysis/
    registry/run_registry.py), aber jetzt je `source` statt global gezaehlt
    - jede der vier Quellen hatte historisch ihren eigenen Zaehler, siehe
    Modul-Docstring.
    """
    import pandas as pd

    con = _connect()
    try:
        existing = pd.read_sql_query(
            "SELECT run_id FROM llm_runs WHERE source = ?", con, params=[source],
        )
    finally:
        con.close()
    if existing.empty:
        return "run_0001"
    numbers = existing["run_id"].str.extract(r"run_(\d+)")[0].dropna().astype(int)
    next_num = (numbers.max() + 1) if not numbers.empty else 1
    return f"run_{next_num:04d}"


def add_run(source: str, **fields) -> str:
    """
    Legt einen neuen Run fuer `source` an (naechste freie run_id per
    next_run_id(), created_at/updated_at automatisch gesetzt) und gibt die
    run_id zurueck. Ersatz fuer RunRegistry.add_run(...) - `fields` sind
    beliebige REGISTRY_COLUMNS-Felder (z.B. prompt_id, model, dataset_id,
    status; status faellt auf "submitted" zurueck, wenn nicht angegeben).
    """
    from datetime import datetime

    run_id = next_run_id(source)
    now = datetime.now().isoformat(timespec="seconds")
    record = {
        "run_id": run_id,
        "status": "submitted",
        "created_at": now,
        "updated_at": now,
        "results_path": "",
        "notes": "",
        **fields,
    }
    upsert_runs(source, [record])
    return run_id


def update_run(source: str, run_id: str, **fields) -> None:
    """
    Aktualisiert einzelne Felder eines bestehenden Runs. upsert_runs()
    ersetzt bei einem Konflikt die ganze Zeile (siehe dort), deshalb wird
    hier erst die bestehende Zeile geholt und die uebergebenen Felder
    darueber gemergt (fetch-merge-upsert), damit nicht uebergebene Felder
    nicht auf NULL fallen. Ersatz fuer RunRegistry.update_run(run_id,
    **kwargs). Wirft ValueError, wenn (source, run_id) nicht existiert
    (via get_run()).
    """
    from datetime import datetime

    existing = get_run(source, run_id)
    record = {col: existing.get(col) for col in REGISTRY_COLUMNS}
    record.update(fields)
    record["updated_at"] = datetime.now().isoformat(timespec="seconds")
    upsert_runs(source, [record])


def get_run(source: str, run_id: str):
    """
    Ersatz fuer RunRegistry.get_run(run_id), jetzt mit Pflicht-`source`, da
    run_id allein nicht mehr global eindeutig ist (bewusster API-Bruch
    gegenueber RunRegistry, siehe Modul-Docstring). Wirft ValueError, wenn
    (source, run_id) nicht existiert.
    """
    import pandas as pd

    con = _connect()
    try:
        df = pd.read_sql_query(
            "SELECT * FROM llm_runs WHERE source = ? AND run_id = ?",
            con, params=[source, str(run_id).strip()],
        )
    finally:
        con.close()
    if df.empty:
        raise ValueError(f"(source={source!r}, run_id={run_id!r}) nicht in llm_runs gefunden.")
    return df.iloc[0]


def total_count() -> int:
    con = _connect()
    try:
        return con.execute("SELECT COUNT(*) FROM llm_runs").fetchone()[0]
    finally:
        con.close()


def source_counts():
    """Sanity-Check-Helfer: DataFrame mit einer Zeile je source und n."""
    import pandas as pd

    con = _connect()
    try:
        return pd.read_sql_query(
            "SELECT source, COUNT(*) AS n FROM llm_runs GROUP BY source ORDER BY source",
            con,
        )
    finally:
        con.close()


def export_csv(source: str, output_path) -> int:
    """
    Schreibt einen Snapshot einer einzelnen `source` als CSV nach
    output_path, in der urspruenglichen REGISTRY_COLUMNS-Spaltenreihenfolge
    (ohne id/source) - haelt bestehende RunRegistry-Konsumenten waehrend der
    Uebergangszeit bis Phase 4 kompatibel. Gibt die Anzahl geschriebener
    Zeilen zurueck.
    """
    df = get_runs(source=source)[REGISTRY_COLUMNS]
    df.to_csv(output_path, index=False)
    return len(df)

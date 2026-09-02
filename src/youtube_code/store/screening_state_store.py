"""
Zentrale SQLite-Ablage fuer den Longitudinal-Screening-State (video_id,
channel_id, Zeitfenster-/Rang-Metadaten, politics_title/politics_title_desc/
politics_final, screening_round, selected_for_transcript,
is_transcript_reserve). Ersetzt data/samples/russia/longitudinal_screening_state.csv
(1,3 GB, 1.012.206 Zeilen) als Source of Truth fuer den Screening-Workflow -
Migration siehe scripts/adhoc/migrate_screening_state_to_store.py.

Vorlaeufiger Speicherort data/raw/screening_state.sqlite (Phase 3c der
Restrukturierung, siehe .claude/plans/phase_3c.md) - wandert zusammen mit dem
Modul in Phase 4 nach data/store/ bzw.
src/youtube_code/store/screening_store.py.

Anders als bei transcript_store.upsert_transcripts ("ganze Zeile gewinnt", weil
ein Duplikat dort ein wiederholter Scrape-*Versuch* ist) gilt hier wie bei
video_registry.upsert_videos ein Feld-fuer-Feld-COALESCE: eine Spalte wird nur
ueberschrieben, wenn der aufrufende Call-Site einen nicht-NULL-Wert uebergibt,
sonst bleibt der vorhandene Wert erhalten. Das ist reine Mechanik - OB und
WELCHE Spalten ein Call-Site ueberhaupt uebergeben darf (z. B. die Regel "ein
einmal gesetztes Politik-Label wird nie ueberschrieben" aus
update_screening_state.validate_state_consistency) bleibt bewusst
Business-Logik der aufrufenden Skripte und wird erst in Phase 4 auf die
neuen Call-Sites uebertragen, nicht hier im Storage-Modul entschieden.

Nutzung in einem Screening-Skript:
    from youtube_code.store.screening_state_store import upsert_state_rows, get_state
    upsert_state_rows(new_or_changed_rows)  # Liste von dicts mit mind. "video_id", "channel_id"
    get_state(screening_round=10)           # DataFrame fuer eine Teilmenge
"""
import sqlite3

from youtube_code.config import STORE

DB_PATH = STORE / "screening_state.sqlite"

# Reihenfolge identisch zur Quell-CSV (siehe export_csv).
COLUMNS = [
    "video_id",
    "channel_id",
    "channel_title",
    "published_at",
    "title",
    "description",
    "period",
    "interval_index",
    "interval_label",
    "rank_within_period",
    "candidate_rank",
    "target_political_per_interval",
    "target_with_buffer_per_interval",
    "politics_title",
    "politics_title_desc",
    "politics_final",
    "screening_round",
    "selected_for_transcript",
    "is_transcript_reserve",
]

# Die neun nullable Integer-Spalten (Rest ist TEXT bzw. video_id/channel_id
# als Pflichtfeld).
_NULLABLE_INT_COLUMNS = {
    "period",
    "interval_index",
    "rank_within_period",
    "candidate_rank",
    "target_political_per_interval",
    "target_with_buffer_per_interval",
    "politics_title",
    "politics_title_desc",
    "politics_final",
    "screening_round",
    "selected_for_transcript",
    "is_transcript_reserve",
}

_SCHEMA = """
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
    politics_title                   INTEGER,
    politics_title_desc              INTEGER,
    politics_final                   INTEGER,
    screening_round                  INTEGER,
    selected_for_transcript          INTEGER,
    is_transcript_reserve            INTEGER
)
"""

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_screening_state_channel ON screening_state(channel_id)",
    "CREATE INDEX IF NOT EXISTS idx_screening_state_round   ON screening_state(screening_round)",
]

_UPDATE_CLAUSE = ",\n".join(
    f"    {col} = COALESCE(excluded.{col}, screening_state.{col})"
    for col in COLUMNS
    if col != "video_id"
)

_UPSERT_SQL = f"""
INSERT INTO screening_state ({', '.join(COLUMNS)})
VALUES ({', '.join('?' * len(COLUMNS))})
ON CONFLICT(video_id) DO UPDATE SET
{_UPDATE_CLAUSE}
"""


def _to_nullable_int(value):
    """Wandelt eine der neun nullable Integer-Spalten robust in int/None (NaN/None/float/String)."""
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


def upsert_state_rows(records) -> int:
    """
    Schreibt eine Liste von Screening-State-Dicts (mind. "video_id",
    idealerweise auch "channel_id") gemaess dem Feld-fuer-Feld-COALESCE-Muster
    (siehe Modul-Docstring) in die zentrale Ablage. Gibt die Anzahl
    tatsaechlich angewendeter Schreibvorgaenge zurueck (con.total_changes-
    Differenz), nicht die Anzahl versuchter Zeilen.
    """
    rows = []
    for r in records:
        vid = r.get("video_id")
        if not vid:
            continue
        row = [str(vid).strip()]
        for col in COLUMNS[1:]:
            value = r.get(col)
            if col in _NULLABLE_INT_COLUMNS:
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


def get_state(video_ids=None, channel_ids=None, politics_final=None, screening_round=None):
    """
    Gibt ein DataFrame mit den screening_state-Spalten zurueck, gefiltert
    ueber jeden uebergebenen Parameter (UND-Verknuepfung).
    """
    import pandas as pd

    con = _connect()
    try:
        # 1. Ohne jeglichen Filter: Komplette Tabelle laden
        if video_ids is None and channel_ids is None and politics_final is None and screening_round is None:
            return pd.read_sql_query(
                f"SELECT {', '.join(COLUMNS)} FROM screening_state", con
            )

        video_ids = [str(v).strip() for v in video_ids] if video_ids is not None else None
        channel_ids = [str(c).strip() for c in channel_ids] if channel_ids is not None else None

        # Hilfsfunktion zum Erstellen der Standard-Bedingungen (politics_final & screening_round)
        def build_extra_conditions():
            extra_where = []
            extra_params = []
            if politics_final is not None:
                extra_where.append("politics_final = ?")
                extra_params.append(politics_final)
            if screening_round is not None:
                extra_where.append("screening_round = ?")
                extra_params.append(screening_round)
            return extra_where, extra_params

        frames = []

        # Fall A: Chunks über video_ids
        if video_ids is not None:
            id_chunks = list(_chunks(video_ids)) if video_ids else [[]]
            for chunk in id_chunks:
                if not chunk:
                    continue
                where = [f"video_id IN ({','.join('?' * len(chunk))})"]
                params = list(chunk)

                if channel_ids is not None:
                    where.append(f"channel_id IN ({','.join('?' * len(channel_ids))})")
                    params.extend(channel_ids)

                extra_where, extra_params = build_extra_conditions()
                where.extend(extra_where)
                params.extend(extra_params)

                frames.append(pd.read_sql_query(
                    f"SELECT {', '.join(COLUMNS)} FROM screening_state WHERE {' AND '.join(where)}",
                    con, params=params,
                ))

        # Fall B: Chunks über channel_ids (falls keine video_ids angegeben)
        elif channel_ids is not None:
            for chunk in _chunks(channel_ids):
                if not chunk:
                    continue
                where = [f"channel_id IN ({','.join('?' * len(chunk))})"]
                params = list(chunk)

                extra_where, extra_params = build_extra_conditions()
                where.extend(extra_where)
                params.extend(extra_params)

                frames.append(pd.read_sql_query(
                    f"SELECT {', '.join(COLUMNS)} FROM screening_state WHERE {' AND '.join(where)}",
                    con, params=params,
                ))

        # Fall C: Nur skalar gefilterte Parameter (politics_final und/oder screening_round)
        else:
            where, params = build_extra_conditions()
            if where:
                frames.append(pd.read_sql_query(
                    f"SELECT {', '.join(COLUMNS)} FROM screening_state WHERE {' AND '.join(where)}",
                    con, params=params,
                ))

        if not frames:
            return pd.DataFrame(columns=COLUMNS)
        return pd.concat(frames, ignore_index=True)

    finally:
        con.close()

def total_count() -> int:
    con = _connect()
    try:
        return con.execute("SELECT COUNT(*) FROM screening_state").fetchone()[0]
    finally:
        con.close()


def round_counts():
    """Sanity-Check-Helfer: DataFrame mit einer Zeile je screening_round und n."""
    import pandas as pd

    con = _connect()
    try:
        return pd.read_sql_query(
            "SELECT screening_round, COUNT(*) AS n FROM screening_state "
            "GROUP BY screening_round ORDER BY screening_round",
            con,
        )
    finally:
        con.close()


def label_counts():
    """Sanity-Check-Helfer: DataFrame mit einer Zeile je politics_final und n."""
    import pandas as pd

    con = _connect()
    try:
        return pd.read_sql_query(
            "SELECT politics_final, COUNT(*) AS n FROM screening_state "
            "GROUP BY politics_final ORDER BY politics_final",
            con,
        )
    finally:
        con.close()


def export_csv(output_path) -> int:
    """
    Schreibt einen vollstaendigen Snapshot der Ablage als CSV nach
    output_path, mit identischer Spaltenreihenfolge wie die Quell-CSV (haelt
    bestehende Excel-/Ad-hoc-Konsumenten waehrend der Uebergangszeit bis
    Phase 4 kompatibel). Gibt die Anzahl geschriebener Zeilen zurueck.
    """
    df = get_state()
    df.to_csv(output_path, index=False)
    return len(df)


def _chunks(items, size=500):
    items = list(items)
    for i in range(0, len(items), size):
        yield items[i:i + size]

"""
Zentrale SQLite-Ablage fuer per YouTube-Data-API abgefragte Video-Kommentare
(COMPLETE_PROCESS.md Schritt 7). Eigener Store analog zu transcript_store.py
statt einer neuen Tabelle in video_registry.sqlite: Kommentare sind - wie
Transkripte - ein eigenstaendiger Daten-Collection-Concern mit eigener
Fetch-/Quota-Logik und potenziell sehr vielen Zeilen Rohtext je Video, keine
schlanken Metadaten-Spalten wie videos/channels.

Zwei Tabellen, weil Kommentare (anders als ein Transkript) 1:n pro Video
sind - ein einzelnes Statusfeld pro Video reicht nicht:
- comment_fetch_status: ein Datensatz pro video_id, Fetch-Versuch/-Tiefe
  (Resume-Logik, Muster: transcript_store.attempted_video_ids()).
- comments: die eigentlichen Kommentar-Datensaetze (comment_id als
  Primary Key, dedupefaehig ueber mehrere Fetches hinweg).

Reply-Tiefe (include_replies): ein Video kann zunaechst nur mit
Top-Level-Kommentaren erfasst werden (guenstiger, weniger Quota) und
spaeter gezielt um Antworten ergaenzt werden, ohne die schon gespeicherten
Top-Level-Kommentare zu verlieren. comment_fetch_status.include_replies
haelt fest, bis zu welcher Tiefe ein Video bereits abgefragt wurde;
attempted_video_ids(include_replies=...) beruecksichtigt das (ein
Replies-Fetch deckt eine Top-Level-Anfrage mit ab, nicht umgekehrt) und der
Upsert von comment_fetch_status lehnt ein Downgrade (Replies -> nur
Top-Level) ab, siehe _UPSERT_STATUS_SQL.

Snapshot-Charakter: anders als ein Transkript ist die Kommentarmenge eines
Videos nicht statisch - nach dem Fetch koennen neue Kommentare dazukommen.
V1 behandelt jeden Fetch als einmaligen Snapshot (kein automatisches
Re-Fetch bereits versuchter Videos), analog zur bewusst akzeptierten
Snapshot-Logik von videos.view_count/like_count/comment_count in
video_registry.py. Ein Re-Fetch-/Staleness-Mechanismus ist bewusst nicht
Teil dieser ersten Version.

Nutzung in einem Fetch-Skript (siehe step7_comments/download_comments.py):
    from youtube_code.store.comment_store import upsert_comments, upsert_comment_status, attempted_video_ids
    attempted = attempted_video_ids(include_replies=False)
    upsert_comments(new_comment_rows)          # Liste von dicts mit mind. "comment_id", "video_id"
    upsert_comment_status(new_status_rows)     # Liste von dicts mit mind. "video_id", "status", "include_replies"
"""
import sqlite3
from datetime import datetime, timezone

from youtube_code.config import STORE

DB_PATH = STORE / "comments.sqlite"

_STATUS_SCHEMA = """
CREATE TABLE IF NOT EXISTS comment_fetch_status (
    video_id        TEXT PRIMARY KEY,
    status          TEXT,
    include_replies INTEGER,
    n_top_level     INTEGER,
    n_replies       INTEGER,
    fetched_at      TEXT
)
"""

_COMMENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS comments (
    comment_id        TEXT PRIMARY KEY,
    video_id          TEXT,
    parent_id         TEXT,
    type              TEXT,
    author            TEXT,
    author_channel_id TEXT,
    text              TEXT,
    published_at      TEXT,
    updated_at        TEXT,
    like_count        INTEGER
)
"""

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_comments_video_id ON comments(video_id)",
]

# Ueberschreibt einen bestehenden Status nur, wenn der neue Fetch mindestens
# so tief war wie der alte (excluded.include_replies >= alte
# include_replies) - ein spaeterer "jetzt auch Replies"-Lauf aktualisiert so
# gezielt Videos, die bisher nur mit Top-Level-Kommentaren erfasst waren,
# waehrend ein versehentlicher Top-Level-Rerun eines bereits mit Replies
# erfassten Videos dessen Status/Counts unangetastet laesst (WHERE-Klausel
# verhindert das Downgrade).
_UPSERT_STATUS_SQL = """
INSERT INTO comment_fetch_status
    (video_id, status, include_replies, n_top_level, n_replies, fetched_at)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(video_id) DO UPDATE SET
    status          = excluded.status,
    include_replies = excluded.include_replies,
    n_top_level     = excluded.n_top_level,
    n_replies       = excluded.n_replies,
    fetched_at      = excluded.fetched_at
WHERE excluded.include_replies >= comment_fetch_status.include_replies
"""

# "Ganze Zeile gewinnt" wie bei transcript_store.upsert_transcripts - ein
# Duplikat hier ist ein wiederholter Fetch-Versuch desselben Kommentars
# (z.B. bearbeiteter Text/aktualisierter like_count), kein Teil-Feld einer
# komplementaeren Quelle.
_UPSERT_COMMENTS_SQL = """
INSERT INTO comments
    (comment_id, video_id, parent_id, type, author, author_channel_id, text, published_at, updated_at, like_count)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(comment_id) DO UPDATE SET
    video_id          = excluded.video_id,
    parent_id         = excluded.parent_id,
    type              = excluded.type,
    author            = excluded.author,
    author_channel_id = excluded.author_channel_id,
    text              = excluded.text,
    published_at      = excluded.published_at,
    updated_at        = excluded.updated_at,
    like_count        = excluded.like_count
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.execute(_STATUS_SCHEMA)
    con.execute(_COMMENTS_SCHEMA)
    for stmt in _INDEXES:
        con.execute(stmt)
    return con


def _to_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def upsert_comment_status(records) -> int:
    """
    Schreibt eine Liste von Status-Dicts (mind. "video_id", "status";
    idealerweise auch "include_replies", "n_top_level", "n_replies") gemaess
    der Downgrade-Schutz-Regel (siehe Modul-Docstring/_UPSERT_STATUS_SQL) in
    comment_fetch_status. "fetched_at" wird, falls nicht mitgegeben, auf den
    aktuellen UTC-Zeitpunkt gesetzt. Gibt die Anzahl tatsaechlich
    angewendeter Schreibvorgaenge zurueck (con.total_changes-Differenz).
    """
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    for r in records:
        vid = r.get("video_id")
        if not vid:
            continue
        rows.append((
            str(vid).strip(),
            r.get("status"),
            int(bool(r.get("include_replies", 0))),
            _to_int(r.get("n_top_level")),
            _to_int(r.get("n_replies")),
            r.get("fetched_at") or now,
        ))
    if not rows:
        return 0

    con = _connect()
    try:
        before = con.total_changes
        con.executemany(_UPSERT_STATUS_SQL, rows)
        con.commit()
        after = con.total_changes
    finally:
        con.close()
    return after - before


def upsert_comments(records) -> int:
    """
    Schreibt eine Liste von Kommentar-Dicts (mind. "comment_id", "video_id")
    per Last-Wins-Upsert (siehe _UPSERT_COMMENTS_SQL) in die comments-Tabelle.
    Gibt die Anzahl tatsaechlich angewendeter Schreibvorgaenge zurueck.
    """
    rows = []
    for r in records:
        cid = r.get("comment_id")
        vid = r.get("video_id")
        if not cid or not vid:
            continue
        rows.append((
            str(cid).strip(),
            str(vid).strip(),
            r.get("parent_id"),
            r.get("type"),
            r.get("author"),
            r.get("author_channel_id"),
            r.get("text"),
            r.get("published_at"),
            r.get("updated_at"),
            _to_int(r.get("like_count")),
        ))
    if not rows:
        return 0

    con = _connect()
    try:
        before = con.total_changes
        con.executemany(_UPSERT_COMMENTS_SQL, rows)
        con.commit()
        after = con.total_changes
    finally:
        con.close()
    return after - before


def attempted_video_ids(include_replies: bool = False) -> set:
    """
    Gibt alle video_ids zurueck, fuer die bereits ein Fetch-Versuch vorliegt,
    der die angefragte Tiefe abdeckt: include_replies=False liefert jedes
    versuchte Video (unabhaengig von dessen include_replies-Wert),
    include_replies=True nur Videos, die tatsaechlich mit Replies erfasst
    wurden. Jeder Status zaehlt (nicht nur "OK") - Muster:
    transcript_store.attempted_video_ids().
    """
    con = _connect()
    try:
        if include_replies:
            rows = con.execute(
                "SELECT video_id FROM comment_fetch_status WHERE include_replies = 1"
            )
        else:
            rows = con.execute("SELECT video_id FROM comment_fetch_status")
        return {row[0] for row in rows}
    finally:
        con.close()


def get_comment_status(video_ids) -> dict:
    """
    Gibt ein Mapping video_id -> dict(status, include_replies, n_top_level,
    n_replies, fetched_at) fuer die uebergebenen video_ids zurueck (nur fuer
    video_ids mit vorhandenem Fetch-Versuch).
    """
    video_ids = [str(v).strip() for v in video_ids if v]
    if not video_ids:
        return {}

    fields = ["video_id", "status", "include_replies", "n_top_level", "n_replies", "fetched_at"]
    con = _connect()
    result = {}
    try:
        for chunk in _chunks(video_ids):
            placeholders = ",".join("?" * len(chunk))
            rows = con.execute(
                f"SELECT {', '.join(fields)} FROM comment_fetch_status WHERE video_id IN ({placeholders})",
                chunk,
            ).fetchall()
            for row in rows:
                d = dict(zip(fields, row))
                result[d.pop("video_id")] = d
    finally:
        con.close()
    return result


def get_comments(video_ids) -> dict:
    """
    Gibt ein Mapping video_id -> Liste von Kommentar-Dicts (comment_id,
    parent_id, type, author, author_channel_id, text, published_at,
    updated_at, like_count) fuer die uebergebenen video_ids zurueck. Videos
    ohne gespeicherte Kommentare fehlen im Ergebnis (nicht mit leerer Liste
    vertreten).
    """
    video_ids = [str(v).strip() for v in video_ids if v]
    if not video_ids:
        return {}

    fields = ["comment_id", "video_id", "parent_id", "type", "author",
              "author_channel_id", "text", "published_at", "updated_at", "like_count"]
    con = _connect()
    result = {}
    try:
        for chunk in _chunks(video_ids):
            placeholders = ",".join("?" * len(chunk))
            rows = con.execute(
                f"SELECT {', '.join(fields)} FROM comments WHERE video_id IN ({placeholders})",
                chunk,
            ).fetchall()
            for row in rows:
                d = dict(zip(fields, row))
                result.setdefault(d.pop("video_id"), []).append(d)
    finally:
        con.close()
    return result


def total_count() -> int:
    con = _connect()
    try:
        return con.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    finally:
        con.close()


def status_counts():
    """Sanity-Check-Helfer: DataFrame mit einer Zeile je status und n."""
    import pandas as pd

    con = _connect()
    try:
        return pd.read_sql_query(
            "SELECT status, include_replies, COUNT(*) AS n FROM comment_fetch_status "
            "GROUP BY status, include_replies ORDER BY n DESC",
            con,
        )
    finally:
        con.close()


def export_jsonl(output_path) -> int:
    """Schreibt einen vollstaendigen Snapshot der comments-Tabelle als JSONL nach output_path."""
    import json

    fields = ["comment_id", "video_id", "parent_id", "type", "author",
              "author_channel_id", "text", "published_at", "updated_at", "like_count"]
    con = _connect()
    n = 0
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            for row in con.execute(
                f"SELECT {', '.join(fields)} FROM comments ORDER BY video_id, comment_id"
            ):
                f.write(json.dumps(dict(zip(fields, row)), ensure_ascii=False) + "\n")
                n += 1
    finally:
        con.close()
    return n


def _chunks(items, size=500):
    items = list(items)
    for i in range(0, len(items), size):
        yield items[i:i + size]

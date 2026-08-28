"""
Zentrale SQLite-Registry fuer alle je ueber die YouTube-API abgefragten
Video-Metadaten (video_id, channel_id, published_at, title).

Jedes Fetch-Skript soll seine frisch abgerufenen Videos hierueber
upserten (upsert_videos), damit jederzeit klar ist, fuer welche Kanaele
und Zeitraeume schon Daten vorliegen - ohne dass irgendein Skript eine
wachsende JSONL bei jedem Aufruf komplett neu laden/schreiben muesste.

`outputs/all_videos.jsonl` ist kein Live-Speicher mehr, sondern ein bei
Bedarf per export_jsonl() erzeugter Snapshot dieser DB. Die "Registry"
im engeren Sinn (aeltestes/neuestes Video je Kanal) ist keine separat
gepflegte Buchfuehrung, sondern eine einfache Abfrage (coverage_report).

Nutzung in einem Fetch-Skript:
    from youtube_code.utils.video_registry import upsert_videos
    upsert_videos(new_videos)   # Liste von dicts mit mind. "video_id"
"""
import json
import sqlite3

from youtube_code.config import RAW

DB_PATH = RAW / "video_registry.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,
    channel_id TEXT,
    published_at TEXT,
    title TEXT
)
"""

_UPSERT_SQL = """
INSERT INTO videos (video_id, channel_id, published_at, title)
VALUES (?, ?, ?, ?)
ON CONFLICT(video_id) DO UPDATE SET
    channel_id = COALESCE(videos.channel_id, excluded.channel_id),
    published_at = COALESCE(videos.published_at, excluded.published_at),
    title = COALESCE(videos.title, excluded.title)
"""


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.execute(_SCHEMA)
    return con


def upsert_videos(records) -> int:
    """
    Schreibt eine Liste von Video-Dicts (mind. "video_id", idealerweise
    auch "channel_id"/"published_at"/"title") in die zentrale Registry.
    Platzhalter-Eintraege ("no_video_found_...", siehe channel_all_videos.py)
    werden uebersprungen. Vorhandene Felder werden nie mit leeren Werten
    ueberschrieben (COALESCE), spaetere, luecken­haftere Quellen koennen
    also nichts kaputtmachen. Gibt die Anzahl geschriebener Zeilen zurueck.
    """
    rows = []
    for r in records:
        vid = r.get("video_id")
        if not vid or "no_video_found" in str(vid):
            continue
        rows.append((
            str(vid).strip(),
            r.get("channel_id"),
            r.get("published_at"),
            r.get("title"),
        ))
    if not rows:
        return 0

    con = _connect()
    try:
        con.executemany(_UPSERT_SQL, rows)
        con.commit()
    finally:
        con.close()
    return len(rows)


def export_jsonl(output_path, include_title: bool = False) -> int:
    """
    Schreibt einen vollstaendigen Snapshot der Registry als JSONL nach
    output_path. Standardmaessig nur video_id/channel_id/published_at
    (bewusst schlank gehalten, siehe fruehere Absprache) - include_title=True
    haengt zusaetzlich den Titel an.
    """
    fields = ["video_id", "channel_id", "published_at"]
    if include_title:
        fields.append("title")

    con = _connect()
    n = 0
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            for row in con.execute(
                f"SELECT {', '.join(fields)} FROM videos ORDER BY video_id"
            ):
                f.write(json.dumps(dict(zip(fields, row)), ensure_ascii=False) + "\n")
                n += 1
    finally:
        con.close()
    return n


def coverage_report():
    """
    Gibt ein DataFrame mit einer Zeile je channel_id zurueck:
    aeltestes_video, neuestes_video, n_videos. Das ist die
    "Registry mit aeltestem/neuestem Video pro Kanal" - immer live aus
    den tatsaechlichen Daten berechnet, keine separate Buchfuehrung.
    """
    import pandas as pd

    con = _connect()
    try:
        return pd.read_sql_query(
            """
            SELECT channel_id,
                   MIN(published_at) AS aeltestes_video,
                   MAX(published_at) AS neuestes_video,
                   COUNT(*) AS n_videos
            FROM videos
            WHERE channel_id IS NOT NULL
            GROUP BY channel_id
            """,
            con,
        )
    finally:
        con.close()


def total_count() -> int:
    con = _connect()
    try:
        return con.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    finally:
        con.close()


def _chunks(items, size=500):
    items = list(items)
    for i in range(0, len(items), size):
        yield items[i:i + size]


def get_channel_map(video_ids) -> dict:
    """
    Gibt ein Mapping video_id -> channel_id fuer die uebergebenen video_ids
    zurueck (nur fuer video_ids, die in der Registry mit gesetzter
    channel_id vorhanden sind; unbekannte video_ids fehlen im Ergebnis).
    """
    video_ids = [str(v) for v in video_ids]
    if not video_ids:
        return {}

    con = _connect()
    result = {}
    try:
        for chunk in _chunks(video_ids):
            placeholders = ",".join("?" * len(chunk))
            rows = con.execute(
                f"SELECT video_id, channel_id FROM videos "
                f"WHERE video_id IN ({placeholders}) AND channel_id IS NOT NULL",
                chunk,
            ).fetchall()
            result.update(rows)
    finally:
        con.close()
    return result


def get_videos_for_channels(channel_ids) -> dict:
    """
    Gibt ein Mapping channel_id -> Menge aller in der Registry bekannten
    video_ids dieses Kanals zurueck - ueber die GESAMTE Registry, nicht nur
    ueber einen aktuellen Input. So laesst sich pro Kanal die vollstaendige
    Historie bereits abgefragter Videos ermitteln.
    """
    channel_ids = [str(c) for c in channel_ids if c]
    if not channel_ids:
        return {}

    con = _connect()
    result = {}
    try:
        for chunk in _chunks(channel_ids):
            placeholders = ",".join("?" * len(chunk))
            rows = con.execute(
                f"SELECT video_id, channel_id FROM videos WHERE channel_id IN ({placeholders})",
                chunk,
            ).fetchall()
            for vid, cid in rows:
                result.setdefault(cid, set()).add(vid)
    finally:
        con.close()
    return result

"""
Zentrale SQLite-Registry fuer alle je ueber die YouTube-API abgefragten
Video-Metadaten (video_id, channel_id, published_at, title, ... siehe
_NEW_VIDEO_COLUMNS fuer die seit Phase 3a der Restrukturierung ergaenzten
Felder), die zugehoerigen Detail-Metadaten (Beschreibung/Tags/... in
video_details) sowie die Such-Provenienz aus der Kanal-Identifikations-
Recherche (search_runs, video_search_hits: mit welchem Suchbegriff und in
welchem Recherche-Lauf ein Video gefunden wurde).

Jedes Fetch-Skript soll seine frisch abgerufenen Videos hierueber
upserten (upsert_videos), damit jederzeit klar ist, fuer welche Kanaele
und Zeitraeume schon Daten vorliegen - ohne dass irgendein Skript eine
wachsende JSONL bei jedem Aufruf komplett neu laden/schreiben muesste.

`outputs/all_videos.jsonl` ist kein Live-Speicher mehr, sondern ein bei
Bedarf per export_jsonl() erzeugter Snapshot dieser DB. Die "Registry"
im engeren Sinn (aeltestes/neuestes Video je Kanal) ist keine separat
gepflegte Buchfuehrung, sondern eine einfache Abfrage (coverage_report).

Nutzung in einem Fetch-Skript:
    from youtube_code.store.video_registry import upsert_videos
    upsert_videos(new_videos)   # Liste von dicts mit mind. "video_id"
"""
import json
import sqlite3

from youtube_code.config import STORE

DB_PATH = STORE / "video_registry.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,
    channel_id TEXT,
    published_at TEXT,
    title TEXT,
    channel_title TEXT,
    duration TEXT,
    view_count INTEGER,
    like_count INTEGER,
    comment_count INTEGER
)
"""

# Seit Phase 3a hinzugekommene Spalten - fuer eine schon vor der Erweiterung
# angelegte DB per ALTER TABLE nachgezogen (siehe _ensure_video_columns).
_NEW_VIDEO_COLUMNS = {
    "channel_title": "TEXT",
    "duration": "TEXT",
    "view_count": "INTEGER",
    "like_count": "INTEGER",
    "comment_count": "INTEGER",
}

_DETAILS_SCHEMA = """
CREATE TABLE IF NOT EXISTS video_details (
    video_id TEXT PRIMARY KEY,
    description TEXT,
    tags TEXT,
    category_id TEXT,
    default_language TEXT,
    default_audio_language TEXT,
    live_broadcast_content TEXT,
    privacy_status TEXT,
    upload_status TEXT,
    license TEXT,
    topic_relevant_topic_ids TEXT,
    topic_categories TEXT,
    location_description TEXT
)
"""

_SEARCH_RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_runs (
    run_id TEXT PRIMARY KEY,
    query TEXT,
    search_start TEXT,
    search_end TEXT,
    month_interval INTEGER,
    executed_at TEXT
)
"""

_SEARCH_HITS_SCHEMA = """
CREATE TABLE IF NOT EXISTS video_search_hits (
    video_id TEXT,
    run_id TEXT,
    query TEXT,
    PRIMARY KEY (video_id, run_id, query)
)
"""

_LANGUAGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS language_classification (
    channel_id TEXT PRIMARY KEY,
    is_german INTEGER,
    german_ratio REAL,
    country TEXT    
)
"""

_UPSERT_SQL = """
INSERT INTO videos (
    video_id, channel_id, published_at, title,
    channel_title, duration, view_count, like_count, comment_count
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(video_id) DO UPDATE SET
    channel_id = COALESCE(videos.channel_id, excluded.channel_id),
    published_at = COALESCE(videos.published_at, excluded.published_at),
    title = COALESCE(videos.title, excluded.title),
    channel_title = COALESCE(videos.channel_title, excluded.channel_title),
    duration = COALESCE(videos.duration, excluded.duration),
    view_count = COALESCE(videos.view_count, excluded.view_count),
    like_count = COALESCE(videos.like_count, excluded.like_count),
    comment_count = COALESCE(videos.comment_count, excluded.comment_count)
"""

_DETAILS_UPSERT_SQL = """
INSERT INTO video_details (
    video_id, description, tags, category_id, default_language,
    default_audio_language, live_broadcast_content, privacy_status,
    upload_status, license, topic_relevant_topic_ids, topic_categories,
    location_description
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(video_id) DO UPDATE SET
    description = COALESCE(video_details.description, excluded.description),
    tags = COALESCE(video_details.tags, excluded.tags),
    category_id = COALESCE(video_details.category_id, excluded.category_id),
    default_language = COALESCE(video_details.default_language, excluded.default_language),
    default_audio_language = COALESCE(video_details.default_audio_language, excluded.default_audio_language),
    live_broadcast_content = COALESCE(video_details.live_broadcast_content, excluded.live_broadcast_content),
    privacy_status = COALESCE(video_details.privacy_status, excluded.privacy_status),
    upload_status = COALESCE(video_details.upload_status, excluded.upload_status),
    license = COALESCE(video_details.license, excluded.license),
    topic_relevant_topic_ids = COALESCE(video_details.topic_relevant_topic_ids, excluded.topic_relevant_topic_ids),
    topic_categories = COALESCE(video_details.topic_categories, excluded.topic_categories),
    location_description = COALESCE(video_details.location_description, excluded.location_description)
"""


_UPSERT_CLASSIFICATION_SQL = """
INSERT INTO language_classification (
    channel_id, is_german, german_ratio, country
)
VALUES (?,?,?,?)
ON CONFLICT(channel_id) DO UPDATE SET
    is_german = COALESCE(excluded.is_german, language_classification.is_german),
    german_ratio = COALESCE(excluded.german_ratio, language_classification.german_ratio),
    country = COALESCE(excluded.country, language_classification.country)
"""


def _ensure_video_columns(con) -> None:
    """
    Faengt den Fall ab, dass DB_PATH schon vor Phase 3a existierte: die
    obige _SCHEMA (CREATE TABLE IF NOT EXISTS) legt die neuen Spalten nur
    bei einer frisch erzeugten Tabelle an. Bei einer bestehenden Tabelle
    werden fehlende Spalten hier per ALTER TABLE nachgezogen.
    """
    existing = {row[1] for row in con.execute("PRAGMA table_info(videos)")}
    for col, col_type in _NEW_VIDEO_COLUMNS.items():
        if col not in existing:
            con.execute(f"ALTER TABLE videos ADD COLUMN {col} {col_type}")


def _to_int(value):
    """Wandelt Zaehl-Felder (oft als String aus der API) robust in int/None."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_json(value):
    """Kodiert Listen-/Dict-Felder (tags, topic_*) als JSON-Text, None bleibt None."""
    return json.dumps(value, ensure_ascii=False) if value is not None else None


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.execute(_SCHEMA)
    con.execute(_DETAILS_SCHEMA)
    con.execute(_SEARCH_RUNS_SCHEMA)
    con.execute(_SEARCH_HITS_SCHEMA)
    con.execute(_LANGUAGE_SCHEMA)
    _ensure_video_columns(con)
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
            r.get("channel_title"),
            r.get("duration"),
            _to_int(r.get("view_count")),
            _to_int(r.get("like_count")),
            _to_int(r.get("comment_count")),
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


def upsert_video_details(records) -> int:
    """
    Schreibt die "teuren", selten geaenderten Detail-Felder aus dem
    detaillierten Metadaten-Fetch (description/tags/category_id/...) in
    video_details. Gleiches COALESCE-Verhalten wie upsert_videos: nie
    Vorhandenes mit leeren Werten ueberschreiben. Listen-/Dict-Felder
    (tags, topic_relevant_topic_ids, topic_categories) werden als JSON-Text
    gespeichert.
    """
    rows = []
    for r in records:
        vid = r.get("video_id")
        if not vid or "no_video_found" in str(vid):
            continue
        rows.append((
            str(vid).strip(),
            r.get("description"),
            _to_json(r.get("tags")),
            r.get("category_id"),
            r.get("default_language"),
            r.get("default_audio_language"),
            r.get("live_broadcast_content"),
            r.get("privacy_status"),
            r.get("upload_status"),
            r.get("license"),
            _to_json(r.get("topic_relevant_topic_ids")),
            _to_json(r.get("topic_categories")),
            r.get("location_description"),
        ))
    if not rows:
        return 0

    con = _connect()
    try:
        con.executemany(_DETAILS_UPSERT_SQL, rows)
        con.commit()
    finally:
        con.close()
    return len(rows)


def upsert_search_runs(records) -> int:
    """
    Schreibt die Recherche-Laeufe aus runs_registry.json (je run_id: Such-
    begriff + Zeitfenster) in search_runs. Reine Fakten-Tabelle (run_id ist
    bereits eindeutig durch den Zeitstempel), daher INSERT OR IGNORE statt
    COALESCE-Merge - ein bestehender Lauf wird nie nachtraeglich geaendert.
    """
    rows = []
    for r in records:
        run_id = r.get("run_id")
        if not run_id:
            continue
        rows.append((
            str(run_id),
            r.get("query"),
            r.get("search_start"),
            r.get("search_end"),
            r.get("month_interval"),
            r.get("executed_at"),
        ))
    if not rows:
        return 0

    con = _connect()
    try:
        con.executemany(
            "INSERT OR IGNORE INTO search_runs "
            "(run_id, query, search_start, search_end, month_interval, executed_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        con.commit()
    finally:
        con.close()
    return len(rows)


def upsert_search_hits(records) -> int:
    """
    Schreibt die Such-Provenienz aus identification_vids.json (je Video: mit
    welchem Suchbegriff es in welchem Recherche-Lauf gefunden wurde) in
    video_search_hits. Ein Video kann mehrfach vorkommen, einmal je
    (run_id, query)-Treffer. Reine Fakten-Tabelle, INSERT OR IGNORE.
    """
    rows = []
    for r in records:
        vid, run_id, query = r.get("video_id"), r.get("run_id"), r.get("query")
        if not vid or not run_id or not query:
            continue
        rows.append((str(vid).strip(), str(run_id), str(query)))
    if not rows:
        return 0

    con = _connect()
    try:
        con.executemany(
            "INSERT OR IGNORE INTO video_search_hits (video_id, run_id, query) VALUES (?, ?, ?)",
            rows,
        )
        con.commit()
    finally:
        con.close()
    return len(rows)


def upsert_language_classification(records) -> int:
    """
    Schreibt die Sprach-Klassifikation der Kanäle in language_classification.
    COALESCE-Verhalten wie bei upsert_videos.
    """
    rows = []
    for r in records:
        cid = r.get("channel_id")
        if not cid:
            continue
        rows.append((
            str(cid).strip(),
            r.get("is_german"),
            r.get("german_ratio"),
            r.get("country")
        ))
    if not rows:
        return 0

    con = _connect()
    try:
        con.executemany(_UPSERT_CLASSIFICATION_SQL, rows)
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


def language_classification_count() -> int:
    con = _connect()
    try:
        return con.execute("SELECT COUNT(*) FROM language_classification").fetchone()[0]
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

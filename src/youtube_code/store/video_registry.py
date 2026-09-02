"""
Zentrale SQLite-Registry fuer alle je ueber die YouTube-API abgefragten
Video-Metadaten (video_id, channel_id, published_at, title, ... siehe
_NEW_VIDEO_COLUMNS fuer die seit Phase 3a der Restrukturierung ergaenzten
Felder), die zugehoerigen Detail-Metadaten (Beschreibung/Tags/... in
video_details), die Such-Provenienz aus der Kanal-Identifikations-Recherche
(search_runs, video_search_hits: mit welchem Suchbegriff und in welchem
Recherche-Lauf ein Video gefunden wurde), die Sprach-Klassifikation je Kanal
(language_classification) sowie die Kanal-Metadaten (channels: Abonnenten,
Gruendungsdatum etc., siehe get_channel_metadata() in youtube_code.utils.io).
Zusaetzlich die Keyword-basierte Themen-Relevanz je Video (video_topic_relevance,
z.B. Ukraine-Krieg-Bezug, siehe youtube_code.step3_war_videos) - nicht zu
verwechseln mit der YouTube-API-eigenen Spalte video_details.topic_relevant_topic_ids.
Alle vier laufen seit der Anbindung der Collection-Skripte (video_identification.py,
channel_all_videos.py, get_channel_metadata()/get_video_metadata() in
youtube_code.utils.io) live mit, statt nur per Einmal-Migration befuellt zu
werden - siehe get_search_provenance() fuer das zentrale Abfrage-Muster
("alle Kanaele, gefunden ueber Suchbegriff X im Zeitraum Y").

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
import re
import sqlite3

from youtube_code.config import MIN_VIDEO_DURATION_SECONDS, STORE

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

_CHANNELS_SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
    channel_id TEXT PRIMARY KEY,
    title TEXT,
    subscribers INTEGER,
    views INTEGER,
    video_count INTEGER,
    hidden_subscriber_count INTEGER,
    handle TEXT,
    published_at TEXT,
    country TEXT,
    default_language TEXT,
    description TEXT,
    profile_keywords TEXT,
    privacy_status TEXT,
    uploads_playlist_id TEXT,
    thumbnail_url TEXT,
    banner_url TEXT
)
"""

_TOPIC_RELEVANCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS video_topic_relevance (
    video_id            TEXT NOT NULL,
    topic               TEXT NOT NULL,
    is_relevant         INTEGER,
    matched_keywords    TEXT,
    title_only          INTEGER,
    keyword_set_version TEXT,
    classified_at       TEXT,
    PRIMARY KEY (video_id, topic)
)
"""

# channel_id hat (anders als video_id) keinen PRIMARY KEY und damit ohne
# diesen Index keinerlei Index - jede channel_id-gefilterte Abfrage
# (v.a. get_videos_with_text(), Grundlage von classify_topic_relevance.py)
# braucht sonst einen vollen Tabellenscan ueber alle videos-Zeilen. Bei
# mehreren hunderttausend bis Millionen Zeilen ist das der dominante
# Laufzeitfaktor - deutlich teurer als die Python-seitige Klassifikation.
_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_videos_channel_id ON videos(channel_id)",
]

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

_CHANNELS_UPSERT_SQL = """
INSERT INTO channels (
    channel_id, title, subscribers, views, video_count, hidden_subscriber_count,
    handle, published_at, country, default_language, description, profile_keywords,
    privacy_status, uploads_playlist_id, thumbnail_url, banner_url
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(channel_id) DO UPDATE SET
    title = COALESCE(channels.title, excluded.title),
    subscribers = COALESCE(channels.subscribers, excluded.subscribers),
    views = COALESCE(channels.views, excluded.views),
    video_count = COALESCE(channels.video_count, excluded.video_count),
    hidden_subscriber_count = COALESCE(channels.hidden_subscriber_count, excluded.hidden_subscriber_count),
    handle = COALESCE(channels.handle, excluded.handle),
    published_at = COALESCE(channels.published_at, excluded.published_at),
    country = COALESCE(channels.country, excluded.country),
    default_language = COALESCE(channels.default_language, excluded.default_language),
    description = COALESCE(channels.description, excluded.description),
    profile_keywords = COALESCE(channels.profile_keywords, excluded.profile_keywords),
    privacy_status = COALESCE(channels.privacy_status, excluded.privacy_status),
    uploads_playlist_id = COALESCE(channels.uploads_playlist_id, excluded.uploads_playlist_id),
    thumbnail_url = COALESCE(channels.thumbnail_url, excluded.thumbnail_url),
    banner_url = COALESCE(channels.banner_url, excluded.banner_url)
"""

# Bewusst die umgekehrte COALESCE-Richtung wie bei _CHANNELS_UPSERT_SQL/_UPSERT_SQL
# (dort gewinnt der alte Wert fuer immer): ein Re-Klassifizierungslauf mit neuer
# keyword_set_version soll bestehende Zeilen ueberschreiben koennen, aehnlich
# _UPSERT_CLASSIFICATION_SQL.
_TOPIC_RELEVANCE_UPSERT_SQL = """
INSERT INTO video_topic_relevance (
    video_id, topic, is_relevant, matched_keywords, title_only,
    keyword_set_version, classified_at
)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(video_id, topic) DO UPDATE SET
    is_relevant = COALESCE(excluded.is_relevant, video_topic_relevance.is_relevant),
    matched_keywords = COALESCE(excluded.matched_keywords, video_topic_relevance.matched_keywords),
    title_only = COALESCE(excluded.title_only, video_topic_relevance.title_only),
    keyword_set_version = COALESCE(excluded.keyword_set_version, video_topic_relevance.keyword_set_version),
    classified_at = COALESCE(excluded.classified_at, video_topic_relevance.classified_at)
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
    con.execute(_CHANNELS_SCHEMA)
    con.execute(_TOPIC_RELEVANCE_SCHEMA)
    _ensure_video_columns(con)
    for stmt in _INDEXES:
        con.execute(stmt)
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

    Liest "queries" (Liste, ein Lauf kann mehrere Suchbegriffe abdecken -
    siehe register_run() in video_identification.py), nicht das
    gleichnamige Singular-Feld "query", das runs_registry.json nie
    schreibt. Die Liste wird als JSON-Text in die query-Spalte kodiert.
    """
    rows = []
    for r in records:
        run_id = r.get("run_id")
        if not run_id:
            continue
        rows.append((
            str(run_id),
            _to_json(r.get("queries")),
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


def upsert_channels(records) -> int:
    """
    Schreibt Kanal-Metadaten (Abonnenten, Gruendungsdatum etc., siehe
    get_channel_metadata() in youtube_code.utils.io) in die channels-
    Tabelle. Gleiches COALESCE-Verhalten wie upsert_videos: ein bereits
    gespeicherter Wert wird nie mit einem leeren/None-Wert ueberschrieben.
    """
    rows = []
    for r in records:
        cid = r.get("channel_id")
        if not cid:
            continue
        rows.append((
            str(cid).strip(),
            r.get("title"),
            _to_int(r.get("subscribers")),
            _to_int(r.get("views")),
            _to_int(r.get("video_count")),
            r.get("hidden_subscriber_count"),
            r.get("handle"),
            r.get("published_at"),
            r.get("country"),
            r.get("default_language"),
            r.get("description"),
            r.get("profile_keywords"),
            r.get("privacy_status"),
            r.get("uploads_playlist_id"),
            r.get("thumbnail_url"),
            r.get("banner_url"),
        ))
    if not rows:
        return 0

    con = _connect()
    try:
        con.executemany(_CHANNELS_UPSERT_SQL, rows)
        con.commit()
    finally:
        con.close()
    return len(rows)


def upsert_topic_relevance(records) -> int:
    """
    Schreibt die Keyword-basierte Themen-Klassifikation (z.B. Ukraine-Krieg-
    Bezug, siehe youtube_code.step3_war_videos) in video_topic_relevance.
    Nicht zu verwechseln mit video_details.topic_relevant_topic_ids (das ist
    die YouTube-API-eigene Freebase-Topic-Kategorisierung - inhaltlich
    voellig unabhaengig, nur Namensaehnlichkeit).

    Anders als upsert_channels/upsert_videos gewinnt hier der NEUE Wert
    (COALESCE(excluded.col, table.col), siehe _TOPIC_RELEVANCE_UPSERT_SQL):
    ein Re-Klassifizierungslauf mit neuer keyword_set_version soll
    bestehende Zeilen ueberschreiben koennen, statt sie fuer immer
    einzufrieren.
    """
    rows = []
    for r in records:
        vid = r.get("video_id")
        topic = r.get("topic")
        if not vid or not topic:
            continue
        rows.append((
            str(vid).strip(),
            str(topic).strip(),
            r.get("is_relevant"),
            _to_json(r.get("matched_keywords")),
            r.get("title_only"),
            r.get("keyword_set_version"),
            r.get("classified_at"),
        ))
    if not rows:
        return 0

    con = _connect()
    try:
        con.executemany(_TOPIC_RELEVANCE_UPSERT_SQL, rows)
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


def channels_count() -> int:
    con = _connect()
    try:
        return con.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
    finally:
        con.close()


def topic_relevance_count(topic=None) -> int:
    """Anzahl Zeilen in video_topic_relevance, optional auf ein topic gefiltert."""
    con = _connect()
    try:
        if topic is None:
            return con.execute("SELECT COUNT(*) FROM video_topic_relevance").fetchone()[0]
        return con.execute(
            "SELECT COUNT(*) FROM video_topic_relevance WHERE topic = ?", (str(topic),)
        ).fetchone()[0]
    finally:
        con.close()


def _chunks(items, size=500):
    items = list(items)
    for i in range(0, len(items), size):
        yield items[i:i + size]


def known_video_ids() -> set:
    """
    Gibt alle video_ids zurueck, die bereits in der Registry vorliegen
    (Muster: transcript_store.attempted_video_ids()). Grundlage fuer den
    Resume-Filter in get_video_metadata() - nur noch nicht abgefragte IDs
    werden ueber die API nachgeladen.
    """
    con = _connect()
    try:
        return {row[0] for row in con.execute("SELECT video_id FROM videos")}
    finally:
        con.close()


def known_video_detail_ids() -> set:
    """
    Gibt alle video_ids zurueck, fuer die bereits Detail-Metadaten
    (description/tags/category_id/...) in video_details vorliegen. Anders
    als known_video_ids() (Tabelle videos, immer per API-Fetch befuellt)
    ist das die Grundlage fuer den Resume-Filter im detailed-Zweig von
    get_video_metadata(): ein Video kann bereits Basis-Metadaten haben,
    ohne dass je die detaillierten Felder abgefragt wurden.
    """
    con = _connect()
    try:
        return {row[0] for row in con.execute("SELECT video_id FROM video_details")}
    finally:
        con.close()


def known_channel_ids_with_videos() -> set:
    """
    Gibt alle channel_ids zurueck, fuer die mindestens ein Video in der
    videos-Tabelle vorliegt (anders als known_channel_ids(): das ist die
    channels-Tabelle mit Kanal-Metadaten - ein Kanal kann Metadaten ohne
    Videos haben oder umgekehrt). Grundlage fuer den "bereits bekannt"-Filter
    in channel_all_videos.py (NEW_CHANNELS-Modus), seit dieser nicht mehr aus
    einer JSON-Datei, sondern direkt aus der Registry liest.

    Einschraenkung: Kanaele, fuer die in einem frueheren Lauf 0 Videos im
    Zeitfenster gefunden wurden, tauchen hier nicht auf (es gibt keine Zeile
    fuer "kein Video gefunden") und gelten daher bei jedem erneuten Lauf
    wieder als neu.
    """
    con = _connect()
    try:
        return {
            row[0] for row in con.execute(
                "SELECT DISTINCT channel_id FROM videos WHERE channel_id IS NOT NULL"
            )
        }
    finally:
        con.close()


def newest_video_per_channel() -> dict:
    """
    Gibt ein Mapping channel_id -> juengstes bekanntes published_at zurueck,
    ueber die gesamte Registry (nicht auf eine Eingabe-Kanalliste
    beschraenkt). Grundlage fuer den Delta-Filter im UPDATE-Modus von
    channel_all_videos.py (frueher aus einer JSON-Datei berechnet).
    """
    con = _connect()
    try:
        rows = con.execute(
            "SELECT channel_id, MAX(published_at) FROM videos "
            "WHERE channel_id IS NOT NULL AND published_at IS NOT NULL "
            "GROUP BY channel_id"
        ).fetchall()
        return dict(rows)
    finally:
        con.close()


def known_channel_ids() -> set:
    """
    Gibt alle channel_ids zurueck, fuer die bereits Kanal-Metadaten in
    channels vorliegen (Muster: known_video_ids()/transcript_store.
    attempted_video_ids()). Grundlage fuer den Resume-Filter in
    get_channel_metadata().
    """
    con = _connect()
    try:
        return {row[0] for row in con.execute("SELECT channel_id FROM channels")}
    finally:
        con.close()


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


def get_channels(channel_ids=None):
    """
    Gibt die channels-Tabelle als DataFrame zurueck - vollstaendig, oder auf
    channel_ids gefiltert, wenn uebergeben.
    """
    import pandas as pd

    con = _connect()
    try:
        if channel_ids is None:
            return pd.read_sql_query("SELECT * FROM channels", con)

        channel_ids = [str(c) for c in channel_ids if c]
        if not channel_ids:
            return pd.read_sql_query("SELECT * FROM channels WHERE 0", con)

        frames = []
        for chunk in _chunks(channel_ids):
            placeholders = ",".join("?" * len(chunk))
            frames.append(pd.read_sql_query(
                f"SELECT * FROM channels WHERE channel_id IN ({placeholders})",
                con,
                params=chunk,
            ))
        return pd.concat(frames, ignore_index=True) if frames else pd.read_sql_query(
            "SELECT * FROM channels WHERE 0", con
        )
    finally:
        con.close()


def get_language_classification(channel_ids=None):
    """
    Gibt die language_classification-Tabelle als DataFrame zurueck -
    vollstaendig, oder auf channel_ids gefiltert, wenn uebergeben.
    """
    import pandas as pd

    con = _connect()
    try:
        if channel_ids is None:
            return pd.read_sql_query("SELECT * FROM language_classification", con)

        channel_ids = [str(c) for c in channel_ids if c]
        if not channel_ids:
            return pd.read_sql_query("SELECT * FROM language_classification WHERE 0", con)

        frames = []
        for chunk in _chunks(channel_ids):
            placeholders = ",".join("?" * len(chunk))
            frames.append(pd.read_sql_query(
                f"SELECT * FROM language_classification WHERE channel_id IN ({placeholders})",
                con,
                params=chunk,
            ))
        return pd.concat(frames, ignore_index=True) if frames else pd.read_sql_query(
            "SELECT * FROM language_classification WHERE 0", con
        )
    finally:
        con.close()


def get_video_rows(video_ids):
    """
    Gibt video_id/channel_id/published_at fuer die uebergebenen video_ids
    zurueck (Verallgemeinerung von get_channel_map: alle drei Spalten statt
    nur des channel_id-Mappings, und ohne den channel_id-IS-NOT-NULL-Filter).
    """
    import pandas as pd

    video_ids = [str(v) for v in video_ids if v]
    if not video_ids:
        return pd.DataFrame(columns=["video_id", "channel_id", "published_at"])

    con = _connect()
    try:
        frames = []
        for chunk in _chunks(video_ids):
            placeholders = ",".join("?" * len(chunk))
            frames.append(pd.read_sql_query(
                f"SELECT video_id, channel_id, published_at FROM videos "
                f"WHERE video_id IN ({placeholders})",
                con,
                params=chunk,
            ))
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
            columns=["video_id", "channel_id", "published_at"]
        )
    finally:
        con.close()


def first_observed_dates(channel_ids):
    """
    Gibt eine pd.Series (Index: channel_id, Werte: MIN(published_at)) fuer
    die uebergebenen channel_ids zurueck - das frueheste in der Registry
    beobachtete Video je Kanal, beschraenkt auf die uebergebenen IDs.
    """
    import pandas as pd

    channel_ids = [str(c) for c in channel_ids if c]
    if not channel_ids:
        return pd.Series(dtype="object", name="first_observed_video_date")

    con = _connect()
    try:
        frames = []
        for chunk in _chunks(channel_ids):
            placeholders = ",".join("?" * len(chunk))
            frames.append(pd.read_sql_query(
                f"SELECT channel_id, MIN(published_at) AS first_observed_video_date "
                f"FROM videos WHERE channel_id IN ({placeholders}) "
                f"AND published_at IS NOT NULL GROUP BY channel_id",
                con,
                params=chunk,
            ))
        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
            columns=["channel_id", "first_observed_video_date"]
        )
        return combined.set_index("channel_id")["first_observed_video_date"]
    finally:
        con.close()


def get_search_provenance(queries=None, search_period=None):
    """
    Zentraler Baustein fuer die Sample-Definition: eine Zeile je
    (video_id, channel_id, run_id, query)-Fund aus der Stichwortsuche.

    queries:
        Liste von Suchbegriffen - nur Treffer mit einem dieser Begriffe
        werden zurueckgegeben. None = alle Suchbegriffe.
    search_period:
        (start, end) als 'YYYY-MM-DD' - nur Laeufe, deren komplettes
        Suchfenster (search_runs.search_start/search_end) innerhalb dieses
        Zeitraums liegt (gleiche "fully contained"-Semantik wie
        video_identification.select_run_ids). None = alle Laeufe.

    channel_id kommt per LEFT JOIN aus videos (kann NULL sein, falls fuer
    das Video noch keine videos-Zeile existiert).
    """
    import pandas as pd

    sql = (
        "SELECT h.video_id AS video_id, v.channel_id AS channel_id, "
        "h.run_id AS run_id, h.query AS query "
        "FROM video_search_hits h "
        "JOIN search_runs r ON h.run_id = r.run_id "
        "LEFT JOIN videos v ON h.video_id = v.video_id "
        "WHERE 1=1"
    )
    params: list = []

    if queries is not None:
        queries = [str(q) for q in queries]
        if not queries:
            return pd.DataFrame(columns=["video_id", "channel_id", "run_id", "query"])
        placeholders = ",".join("?" * len(queries))
        sql += f" AND h.query IN ({placeholders})"
        params.extend(queries)

    if search_period is not None:
        period_start, period_end = search_period
        sql += " AND r.search_start >= ? AND r.search_end <= ?"
        params.extend([str(period_start), str(period_end)])

    con = _connect()
    try:
        return pd.read_sql_query(sql, con, params=params)
    finally:
        con.close()


def get_topic_relevance(topic, video_ids=None):
    """
    Gibt die video_topic_relevance-Zeilen fuer ein topic zurueck - vollstaendig,
    oder auf video_ids gefiltert, wenn uebergeben. Siehe upsert_topic_relevance()
    fuer die Abgrenzung zu video_details.topic_relevant_topic_ids.
    """
    import pandas as pd

    con = _connect()
    try:
        if video_ids is None:
            return pd.read_sql_query(
                "SELECT * FROM video_topic_relevance WHERE topic = ?",
                con, params=[str(topic)],
            )

        video_ids = [str(v) for v in video_ids if v]
        if not video_ids:
            return pd.read_sql_query("SELECT * FROM video_topic_relevance WHERE 0", con)

        frames = []
        for chunk in _chunks(video_ids):
            placeholders = ",".join("?" * len(chunk))
            frames.append(pd.read_sql_query(
                f"SELECT * FROM video_topic_relevance "
                f"WHERE topic = ? AND video_id IN ({placeholders})",
                con,
                params=[str(topic), *chunk],
            ))
        return pd.concat(frames, ignore_index=True) if frames else pd.read_sql_query(
            "SELECT * FROM video_topic_relevance WHERE 0", con
        )
    finally:
        con.close()


def topic_relevant_video_ids(topic) -> set:
    """
    Gibt alle video_ids zurueck, die fuer topic als is_relevant=1 klassifiziert
    wurden (Muster: transcript_store.attempted_video_ids()).
    """
    con = _connect()
    try:
        return {
            row[0] for row in con.execute(
                "SELECT video_id FROM video_topic_relevance WHERE topic = ? AND is_relevant = 1",
                (str(topic),),
            )
        }
    finally:
        con.close()


_DURATION_RE = re.compile(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", re.IGNORECASE)


def duration_to_seconds(duration):
    """
    Parst eine ISO-8601-Dauer, wie sie die YouTube-API in videos.duration
    liefert (z.B. "PT3M21S"), zu Sekunden. Gibt None fuer leere/unparsebare
    Werte zurueck (z.B. Videos, fuer die contentDetails noch nie abgefragt
    wurde). Gleiches Regex-Muster wie der archivierte duration_seconds() in
    archive/new_analysis/attention_diagnostics.py.
    """
    if not duration:
        return None
    match = _DURATION_RE.fullmatch(str(duration).strip())
    if not match:
        return None
    days, hours, minutes, seconds = (int(x) if x else 0 for x in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def duration_lookup(video_ids) -> dict:
    """
    Gibt video_id -> duration_seconds (None bei unbekannter/unparsebarer
    Dauer) fuer die uebergebenen video_ids zurueck. Grundlage fuer
    Mindestlaengen-Pruefungen an Stellen, die ihre Kandidaten nicht ueber
    get_videos_with_text() beziehen, sondern direkt aus screening_state_store
    oder video_topic_relevance (siehe step4_transcript_download/select_targets.py,
    download_transcripts()) - dort koennen historisch gewachsene Zeilen liegen,
    die vor Einfuehrung des Mindestlaengen-Filters entstanden sind.
    """
    import pandas as pd

    video_ids = sorted({str(v) for v in video_ids if v})
    if not video_ids:
        return {}

    con = _connect()
    try:
        frames = []
        for chunk in _chunks(video_ids):
            placeholders = ",".join("?" * len(chunk))
            frames.append(pd.read_sql_query(
                f"SELECT video_id, duration FROM videos WHERE video_id IN ({placeholders})",
                con,
                params=chunk,
            ))
        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["video_id", "duration"])
    finally:
        con.close()

    return {row.video_id: duration_to_seconds(row.duration) for row in df.itertuples()}


def get_videos_with_text(channel_ids=None, video_ids=None, min_duration_seconds=MIN_VIDEO_DURATION_SECONDS):
    """
    Gibt video_id/channel_id/channel_title/published_at/title/description
    zurueck (videos LEFT JOIN video_details), optional auf channel_ids oder
    video_ids gefiltert. Grundlage fuer die Keyword-Klassifikation in
    youtube_code.step3_war_videos sowie fuer append_channels_to_state.py
    (Schritt 2), das damit die frueher separat exportierte JSONL ersetzt.

    Filtert dabei zentral alle Videos heraus, deren Dauer unter
    min_duration_seconds liegt (Default: MIN_VIDEO_DURATION_SECONDS aus
    youtube_code.config, aktuell 181s) - inklusive Videos mit noch
    unbekannter Dauer (kein contentDetails-Fetch bisher), da fuer sie die
    Mindestlaenge nicht verifiziert werden kann. min_duration_seconds=None
    deaktiviert den Filter komplett (z.B. fuer Diagnose-Zwecke).
    """
    import pandas as pd

    cols = "v.video_id, v.channel_id, v.channel_title, v.published_at, v.title, v.duration, d.description"
    base_sql = (
        f"SELECT {cols} FROM videos v "
        f"LEFT JOIN video_details d ON v.video_id = d.video_id"
    )
    out_cols = ["video_id", "channel_id", "channel_title", "published_at", "title", "description"]

    def _finalize(df):
        if min_duration_seconds is not None and not df.empty:
            seconds = df["duration"].map(duration_to_seconds)
            keep = [s is not None and s >= min_duration_seconds for s in seconds]
            df = df.loc[keep]
        return df.drop(columns="duration").reset_index(drop=True)

    if channel_ids is None and video_ids is None:
        con = _connect()
        try:
            return _finalize(pd.read_sql_query(base_sql, con))
        finally:
            con.close()

    filter_col, filter_ids = ("v.channel_id", channel_ids) if channel_ids is not None else ("v.video_id", video_ids)
    filter_ids = [str(x) for x in filter_ids if x]
    if not filter_ids:
        return pd.DataFrame(columns=out_cols)

    con = _connect()
    try:
        frames = []
        for chunk in _chunks(filter_ids):
            placeholders = ",".join("?" * len(chunk))
            frames.append(pd.read_sql_query(
                f"{base_sql} WHERE {filter_col} IN ({placeholders})",
                con,
                params=chunk,
            ))
        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=out_cols + ["duration"])
        return _finalize(combined)
    finally:
        con.close()

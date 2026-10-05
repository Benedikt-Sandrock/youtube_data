"""
Zentrale SQLite-Ablage fuer alle je per YouTube-Transcript-API abgefragten
Transkripte (video_id, transcript_segments als JSON-Text, language_code,
is_generated, status). Ersetzt die bisherige Source of Truth
data/transcripts/all_transcripts_segments.csv (siehe .claude/CLAUDE.md) durch
eine indizierte, duplikatfreie Ablage - Migration siehe
scripts/adhoc/migrate_transcripts_to_store.py.

Vorlaeufiger Speicherort data/raw/transcripts.sqlite (Phase 3b der
Restrukturierung) - wandert zusammen mit dem Modul in Phase 4 nach
data/store/ bzw. src/youtube_code/store/transcript_store.py.

Dedupe-/Upsert-Regel (siehe upsert_transcripts): anders als bei
video_registry.upsert_videos (Feld-fuer-Feld-COALESCE ueber komplementaere
Quellen) gilt hier "ganze Zeile gewinnt", weil ein Duplikat hier ein
wiederholter Scrape-*Versuch* desselben Videos ist, kein Teil-Feld einer
anderen Quelle. Prioritaet: "OK" (Rang 0) > "Kein Transkript" (Rang 1) >
alles andere / "Fehler: ..." (Rang 2), bei gleichem Rang Last-Wins. Die
Regel steckt direkt in der ON CONFLICT-Klausel, gilt also automatisch auch
fuer kuenftige Scraper-Direktschreibvorgaenge (Phase 4), nicht nur fuer die
einmalige Migration.

Nutzung in einem Scraping-/Analyse-Skript:
    from youtube_code.store.transcript_store import upsert_transcripts, get_transcripts
    upsert_transcripts(new_records)  # Liste von dicts mit mind. "video_id", "status"
    get_transcripts(video_ids)       # dict[video_id, dict] fuer einen Batch
"""
import json
import sqlite3

from youtube_code.config import STORE

DB_PATH = STORE / "transcripts.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS transcripts (
    video_id TEXT PRIMARY KEY,
    transcript_segments TEXT,
    language_code TEXT,
    is_generated INTEGER,
    status TEXT,
    n_segments INTEGER
)
"""

_UPSERT_SQL = """
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
"""


def _to_bool_int(value):
    """
    Wandelt is_generated robust in 0/1/None: echte bools direkt, Strings
    ("True"/"False"/"true"/"false", auch mit Leerraum) case-insensitiv,
    NaN/None/leerer String -> None statt versehentlich 0.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, float) and value != value:  # NaN
        return None
    s = str(value).strip().lower()
    if s in ("", "none", "nan"):
        return None
    if s == "true":
        return 1
    if s == "false":
        return 0
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def _n_segments(transcript_segments):
    """
    Ermittelt die Segmentanzahl aus transcript_segments (JSON-Text oder
    bereits dekodierte Liste). None bei leer/None/kaputtem JSON - bewusst
    kein Fehlerabbruch, da das Feld in der Quelle unzuverlaessig sein kann.
    """
    if transcript_segments is None:
        return None
    value = transcript_segments
    if isinstance(value, str):
        s = value.strip()
        if s == "" or s.lower() == "nan":
            return None
        try:
            value = json.loads(s)
        except (TypeError, ValueError):
            return None
    if isinstance(value, list):
        return len(value)
    return None


def _to_segments_text(transcript_segments):
    """Serialisiert transcript_segments zu JSON-Text falls noch nicht Text; None bleibt None."""
    if transcript_segments is None:
        return None
    if isinstance(transcript_segments, str):
        s = transcript_segments.strip()
        return None if s == "" or s.lower() == "nan" else transcript_segments
    return json.dumps(transcript_segments, ensure_ascii=False)


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.execute(_SCHEMA)
    return con


def upsert_transcripts(records) -> int:
    """
    Schreibt eine Liste von Transkript-Dicts (mind. "video_id", idealerweise
    auch "status") gemaess der Prioritaets-/Last-Wins-Regel (siehe Modul-
    Docstring) in die zentrale Ablage. transcript_segments darf JSON-Text
    oder bereits dekodierte Liste sein. Gibt die Anzahl tatsaechlich
    angewendeter Schreibvorgaenge zurueck (con.total_changes-Differenz),
    nicht die Anzahl versuchter Zeilen - Zeilen, die wegen der Prioritaets-
    regel uebersprungen wurden, zaehlen also nicht mit.
    """
    rows = []
    for r in records:
        vid = r.get("video_id")
        if not vid:
            continue
        segments_text = _to_segments_text(r.get("transcript_segments"))
        rows.append((
            str(vid).strip(),
            segments_text,
            r.get("language_code"),
            _to_bool_int(r.get("is_generated")),
            r.get("status"),
            _n_segments(segments_text),
        ))
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


def get_transcripts(video_ids) -> dict:
    """
    Gibt ein Mapping video_id -> dict(transcript_segments, language_code,
    is_generated, status, n_segments) fuer die uebergebenen video_ids
    zurueck (nur fuer video_ids mit vorhandenem Scrape-Versuch; unbekannte
    video_ids fehlen im Ergebnis). Gechunkte IN(...)-Query, Batch 500.
    Fehlt fuer einen Teil der abgefragten video_ids ein Scrape-Versuch, wird
    das per Print gemeldet (Anzahl der fehlenden IDs).
    """
    video_ids = [str(v).strip() for v in video_ids if v]
    if not video_ids:
        return {}

    fields = ["video_id", "transcript_segments", "language_code", "is_generated", "status", "n_segments"]
    con = _connect()
    result = {}
    try:
        for chunk in _chunks(video_ids):
            placeholders = ",".join("?" * len(chunk))
            rows = con.execute(
                f"SELECT {', '.join(fields)} FROM transcripts WHERE video_id IN ({placeholders})",
                chunk,
            ).fetchall()
            for row in rows:
                d = dict(zip(fields, row))
                result[d.pop("video_id")] = d
    finally:
        con.close()

    n_missing = len(set(video_ids) - result.keys())
    if n_missing:
        print(f"get_transcripts: fuer {n_missing} von {len(set(video_ids))} abgefragten video_ids liegt kein Scrape-Versuch vor.")

    return result


def get_transcript(video_id) -> dict | None:
    """Einzel-Wrapper um get_transcripts fuer genau eine video_id."""
    return get_transcripts([video_id]).get(str(video_id).strip())


def attempted_video_ids() -> set:
    """
    Gibt alle video_ids zurueck, fuer die irgendein Scrape-Versuch vorliegt
    (jeder Status, nicht nur "OK"). Ersetzt in Phase 4 das aktuelle
    pd.read_csv(usecols=["video_id"])-Muster in get_baseline_ids.py und den
    Resume-Filter im Scraper.
    """
    con = _connect()
    try:
        return {row[0] for row in con.execute("SELECT video_id FROM transcripts")}
    finally:
        con.close()


def has_transcript(video_ids) -> set:
    """
    Gibt die Teilmenge der uebergebenen video_ids zurueck, fuer die
    status='OK' UND ein tatsaechliches Transkript vorliegt (n_segments > 0
    bzw. gesetzt).
    """
    video_ids = [str(v).strip() for v in video_ids if v]
    if not video_ids:
        return set()

    con = _connect()
    result = set()
    try:
        for chunk in _chunks(video_ids):
            placeholders = ",".join("?" * len(chunk))
            rows = con.execute(
                f"SELECT video_id FROM transcripts "
                f"WHERE video_id IN ({placeholders}) AND status = 'OK' "
                f"AND transcript_segments IS NOT NULL AND n_segments > 0",
                chunk,
            ).fetchall()
            result.update(r[0] for r in rows)
    finally:
        con.close()
    return result


def total_count() -> int:
    con = _connect()
    try:
        return con.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
    finally:
        con.close()


def status_counts():
    """Sanity-Check-Helfer: DataFrame mit einer Zeile je status und n."""
    import pandas as pd

    con = _connect()
    try:
        return pd.read_sql_query(
            "SELECT status, COUNT(*) AS n FROM transcripts GROUP BY status ORDER BY n DESC",
            con,
        )
    finally:
        con.close()


def export_jsonl(output_path, include_segments: bool = True) -> int:
    """
    Schreibt einen vollstaendigen Snapshot der Ablage als JSONL nach
    output_path. Anders als video_registry.export_jsonl standardmaessig
    MIT transcript_segments (das ist hier der eigentliche Nutzinhalt) -
    include_segments=False fuer einen schlanken Snapshot ohne Segmenttext.
    """
    fields = ["video_id", "language_code", "is_generated", "status", "n_segments"]
    if include_segments:
        fields.insert(1, "transcript_segments")

    con = _connect()
    n = 0
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            for row in con.execute(
                f"SELECT {', '.join(fields)} FROM transcripts ORDER BY video_id"
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

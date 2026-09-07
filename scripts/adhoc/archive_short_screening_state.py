"""
Archiviert alle screening_state-Zeilen mit BESTAETIGTER Dauer < MIN_VIDEO_DURATION_SECONDS
(alle politics_final-Label inkl. NULL) in eine neue Tabelle
screening_state_archive_short_duration innerhalb derselben screening_state.sqlite-Datei
und entfernt sie danach aus der aktiven screening_state-Tabelle.

Zeilen mit noch UNBEKANNTER Dauer bleiben bewusst unangetastet - fuer sie liess sich
bisher nicht verifizieren, ob sie zu kurz sind (siehe backfill_duration_political_videos.py
fuer den Nachlade-Ansatz; bei politics_final==1 stellten sich nach dem Nachladen ca. 77%
der zuvor "unbekannten" Videos als tatsaechlich lang genug heraus - pauschales Aussortieren
haette diese also faelschlich verworfen).

Hintergrund/Motivation:
1. select_targets.select_baseline_targets() zaehlte politics_final==1-Videos bisher roh
   (vor dem Duration-Filter) fuer die Baseline-Zielerreichung - siehe Fix dort.
2. create_longitudinal_screening.plan_screening_round() zieht den Kandidatenpool fuer
   neue Screening-Runden aus politics_final IS NULL-Zeilen, ebenfalls ohne Dauer-Pruefung -
   zu kurze NULL-Zeilen dort haetten kuenftiges LLM-Klassifikationsbudget verschwendet
   (siehe Fix dort, gleiche Datei-Aenderung wie hier beschrieben).
Mit beiden Code-Fixen ist die Korrektheit bereits sichergestellt, unabhaengig davon, ob
dieses Skript laeuft. Es dient nur der Aufraeumung/Verkleinerung der aktiven Tabelle.

Keine Klassifikation geht verloren: alle Original-Spalten + duration_seconds + archived_at
werden 1:1 in die Archiv-Tabelle uebernommen, BEVOR die Zeilen aus screening_state
geloescht werden (eine Transaktion, atomar). --dry-run zeigt nur die betroffenen Zeilen
an, ohne zu schreiben.

Seit .claude/plans/screening_state_update.md enthaelt screening_state_store.COLUMNS
NICHT mehr channel_title/published_at/title/description (siehe dortiger Moduldocstring).
Die Archiv-Tabelle behaelt diese vier Spalten bewusst bei (dauerhafter Snapshot fuer
Videos, die aus der weiteren Verarbeitung ausscheiden) - ARCHIVE_STATE_COLUMNS unten
listet daher explizit COLUMNS + die vier Textspalten, und find_confirmed_too_short()
laedt den State per get_state_with_text() (video_id-Join gegen video_registry), damit
die Textspalten fuer den Insert ueberhaupt verfuegbar sind.

Nutzung:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        scripts/adhoc/archive_short_screening_state.py [--dry-run]
"""
import argparse
import sqlite3
from datetime import datetime, timezone

from youtube_code.config import MIN_VIDEO_DURATION_SECONDS
from youtube_code.store import screening_state_store, video_registry

ARCHIVE_TABLE = "screening_state_archive_short_duration"

_ARCHIVE_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {ARCHIVE_TABLE} (
    video_id                         TEXT PRIMARY KEY,
    channel_id                       TEXT,
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
    is_transcript_reserve            INTEGER,
    duration_seconds                 REAL,
    archived_at                      TEXT,
    archive_reason                   TEXT
)
"""

# Reihenfolge identisch zu _ARCHIVE_SCHEMA oben: screening_state_store.COLUMNS
# hat die vier Textspalten seit dem Schema-Refactor nicht mehr, die
# Archiv-Tabelle behaelt sie aber bewusst bei (siehe Moduldocstring) - daher
# hier explizit wieder eingefuegt statt COLUMNS direkt zu verwenden.
ARCHIVE_STATE_COLUMNS = [
    "video_id", "channel_id", "channel_title", "published_at", "title", "description",
    "period", "interval_index", "interval_label", "rank_within_period", "candidate_rank",
    "target_political_per_interval", "target_with_buffer_per_interval",
    "politics_title", "politics_title_desc", "politics_final",
    "screening_round", "selected_for_transcript", "is_transcript_reserve",
]

_INSERT_SQL = f"""
INSERT OR IGNORE INTO {ARCHIVE_TABLE}
    ({', '.join(ARCHIVE_STATE_COLUMNS)}, duration_seconds, archived_at, archive_reason)
VALUES ({', '.join('?' * (len(ARCHIVE_STATE_COLUMNS) + 3))})
"""


def _chunks(items, size=500):
    items = list(items)
    for i in range(0, len(items), size):
        yield items[i:i + size]


def find_confirmed_too_short() -> "pd.DataFrame":
    import pandas as pd

    state = screening_state_store.get_state_with_text()
    lookup = video_registry.duration_lookup(state["video_id"].tolist())
    state = state.copy()
    state["duration_seconds"] = state["video_id"].map(lookup)
    too_short = state["duration_seconds"].notna() & (state["duration_seconds"] < MIN_VIDEO_DURATION_SECONDS)
    return state.loc[too_short].reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Nur zaehlen/anzeigen, nichts schreiben/loeschen.")
    args = parser.parse_args()

    to_archive = find_confirmed_too_short()
    print(f"screening_state-Zeilen mit bestaetigter Dauer < {MIN_VIDEO_DURATION_SECONDS}s: {len(to_archive):,}")
    if not to_archive.empty:
        print(to_archive["politics_final"].value_counts(dropna=False).sort_index().rename("n").to_string())

    if args.dry_run or to_archive.empty:
        print("DRY RUN oder keine Zeilen - es wurde nichts archiviert/geloescht.")
        return

    archived_at = datetime.now(timezone.utc).isoformat()
    rows = [
        tuple(row[c] for c in ARCHIVE_STATE_COLUMNS)
        + (row["duration_seconds"], archived_at, f"duration<{MIN_VIDEO_DURATION_SECONDS}s")
        for _, row in to_archive.iterrows()
    ]
    video_ids = to_archive["video_id"].tolist()

    con = sqlite3.connect(screening_state_store.DB_PATH, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    try:
        con.execute(_ARCHIVE_SCHEMA)
        con.executemany(_INSERT_SQL, rows)
        deleted = 0
        for chunk in _chunks(video_ids):
            placeholders = ",".join("?" * len(chunk))
            cur = con.execute(f"DELETE FROM screening_state WHERE video_id IN ({placeholders})", chunk)
            deleted += cur.rowcount
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

    print(f"\nArchiviert nach {ARCHIVE_TABLE}: {len(rows):,} Zeilen")
    print(f"Aus screening_state geloescht: {deleted:,} Zeilen")
    print(f"screening_state.sqlite verbleibende Gesamtzeilen: {screening_state_store.total_count():,}")


if __name__ == "__main__":
    main()

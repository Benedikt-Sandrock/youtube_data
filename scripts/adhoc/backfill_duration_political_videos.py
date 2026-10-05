"""
Laedt fuer die als politics_final==1 gelabelten screening_state-Zeilen mit noch
unbekannter Dauer (video_registry.videos.duration IS NULL) die contentDetails
per YouTube Data API nach und schreibt nur die duration-Spalte zurueck.

Hintergrund: Diese Zeilen stammen aus der Zeit vor Einfuehrung des zentralen
Mindestlaengen-Filters (config.MIN_VIDEO_DURATION_SECONDS, durchgesetzt seit
video_registry.get_videos_with_text()) und wurden nie mit contentDetails
abgefragt - sie zaehlen deshalb aktuell als "nicht bestaetigt lang genug" und
werden von select_targets._filter_min_duration() verworfen, obwohl ein
Teil davon tatsaechlich lang genug sein duerfte. Reines Nachladen fehlender
Metadaten, keine Aenderung an Klassifikationen (politics_final etc. bleiben
unangetastet - siehe screening_state_store, das hier gar nicht beschrieben wird).

video_registry.upsert_videos() ueberschreibt nie einen bereits vorhandenen
(nicht-NULL) Wert (COALESCE(videos.duration, excluded.duration) - siehe
video_registry._UPSERT_SQL), d.h. dieses Skript kann bestehende Dauern nicht
kaputt machen, selbst bei mehrfachem Lauf.

Kosten: 1 Quota-Einheit pro 50 Video-IDs (videos().list). Bei ca. 30.000
betroffenen IDs also ca. 600 Calls / 600 Quota-Einheiten (Standard-Tagesquota:
10.000 Einheiten).

Nutzung:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        scripts/adhoc/backfill_duration_political_videos.py [--dry-run] [--limit N]
"""
import argparse
import time

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from youtube_code.config import API_KEY
from youtube_code.store import screening_state_store, video_registry

BATCH_SIZE = 50


def _chunks(items, size=BATCH_SIZE):
    items = list(items)
    for i in range(0, len(items), size):
        yield items[i:i + size]


def find_unknown_duration_political_ids() -> list:
    """video_ids mit politics_final==1, deren duration in video_registry.videos noch NULL/unbekannt ist."""
    state = screening_state_store.get_state(politics_final=1)
    video_ids = state["video_id"].tolist()
    lookup = video_registry.duration_lookup(video_ids)
    return [v for v in video_ids if lookup.get(v) is None]


def fetch_durations(video_ids: list, youtube) -> tuple[list, list]:
    """Fragt contentDetails in 50er-Batches ab. Gibt (records, not_found_ids) zurueck."""
    records = []
    not_found = []
    for batch in _chunks(video_ids):
        for attempt in range(3):
            try:
                resp = youtube.videos().list(part="contentDetails", id=",".join(batch)).execute()
                break
            except HttpError as e:
                if attempt == 2:
                    raise
                print(f"  API-Fehler ({e}), erneuter Versuch in 5s...")
                time.sleep(5)

        found_ids = set()
        for item in resp.get("items", []):
            vid = item["id"]
            found_ids.add(vid)
            duration = item.get("contentDetails", {}).get("duration")
            if duration:
                records.append({"video_id": vid, "duration": duration})
        not_found.extend(v for v in batch if v not in found_ids)
    return records, not_found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Nur zaehlen/anzeigen, keine API-Calls, kein Schreiben.")
    parser.add_argument("--limit", type=int, default=None, help="Nur die ersten N IDs verarbeiten (Test).")
    args = parser.parse_args()

    ids = find_unknown_duration_political_ids()
    print(f"politics_final==1-Videos mit unbekannter Dauer: {len(ids):,}")
    if args.limit:
        ids = ids[:args.limit]
        print(f"--limit gesetzt, verarbeite nur {len(ids):,} IDs.")

    n_calls = -(-len(ids) // BATCH_SIZE)
    print(f"Benoetigte API-Calls (a 50 IDs): {n_calls:,} (~{n_calls:,} Quota-Einheiten)")

    if args.dry_run or not ids:
        print("DRY RUN oder keine IDs - es wurde nichts abgefragt/geschrieben.")
        return

    youtube = build("youtube", "v3", developerKey=API_KEY)
    records, not_found = fetch_durations(ids, youtube)

    written = video_registry.upsert_videos(records) if records else 0
    print(f"\nDauer erfolgreich nachgeladen und geschrieben: {len(records):,}")
    print(f"Nicht gefunden (geloescht/privat/API liefert kein contentDetails): {len(not_found):,}")
    print(f"upsert_videos() gemeldete Zeilen: {written:,}")
    print(
        "\nHinweis: not_found-IDs bleiben mit unbekannter Dauer und werden von "
        "select_targets._filter_min_duration() weiterhin als 'nicht bestaetigt lang genug' verworfen."
    )


if __name__ == "__main__":
    main()

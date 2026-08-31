"""
Einmaliges Migrationsskript fuer Phase 3a der Restrukturierung
(siehe .claude/restructuring/RESTRUCTURING_PLAN.md, Abschnitt "Phase 3").

Importiert die bisher verstreuten Video-Metadaten-Dateien in
data/raw/video_registry.sqlite (Tabellen videos, video_details) sowie die
Such-Provenienz-Registry aus data/channel_lists/all_identification/ in die
neuen Tabellen search_runs/video_search_hits. Reiner Daten-Import per
COALESCE-Upsert (video_registry.py) - ueberschreibt nie Vorhandenes,
loescht keine Quelldateien. Kein Bestandteil einer laufenden Pipeline,
danach nicht mehr regelmaessig auszufuehren.

Ausfuehrung (aus dem Repo-Root, src muss auf dem PYTHONPATH liegen):
    PYTHONPATH=src python scripts/adhoc/migrate_video_metadata_to_registry.py
"""
import json
import shutil

from youtube_code.config import CHANNEL_LISTS, RAW, SAMPLES
from youtube_code.utils.video_registry import (
    DB_PATH,
    total_count,
    upsert_search_hits,
    upsert_search_runs,
    upsert_video_details,
    upsert_videos,
)

BATCH_SIZE = 5000
PROGRESS_EVERY = 200_000

# (Pfad, hat Detail-Felder wie description/tags/category_id/...)
JSONL_SOURCES = [
    (RAW / "video_metadata_total.jsonl", False),
    (RAW / "video_metadata_detailed_total.jsonl", True),
    (RAW / "neue_kanaele_video_metadata_detailed.jsonl", True),
    (SAMPLES / "russia" / "sample_50k_channels_russia_ukraine_wo_shorts.jsonl", True),
]

JSON_ARRAY_SOURCE = RAW / "sample_50k_channels_russia_ukraine.json"

IDENTIFICATION_DIR = CHANNEL_LISTS / "all_identification"


def iter_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def chunked(iterable, size):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def migrate_jsonl_source(path, has_details: bool) -> None:
    print(f"\n== {path} ==")
    if not path.exists():
        print("  UEBERSPRUNGEN (Datei nicht gefunden)")
        return

    read, written_core, written_details = 0, 0, 0
    for batch in chunked(iter_jsonl(path), BATCH_SIZE):
        read += len(batch)
        written_core += upsert_videos(batch)
        if has_details:
            written_details += upsert_video_details(batch)
        if read % PROGRESS_EVERY < BATCH_SIZE:
            print(f"  ... {read} Zeilen gelesen")

    print(f"  gelesen: {read}, videos upserted: {written_core}", end="")
    if has_details:
        print(f", video_details upserted: {written_details}")
    else:
        print()


def migrate_json_array_source(path) -> None:
    print(f"\n== {path} ==")
    if not path.exists():
        print("  UEBERSPRUNGEN (Datei nicht gefunden)")
        return

    with open(path, encoding="utf-8") as f:
        records = json.load(f)
    print(f"  gelesen: {len(records)} Zeilen")

    written = 0
    for batch in chunked(records, BATCH_SIZE):
        written += upsert_videos(batch)
    print(f"  videos upserted: {written}")


def migrate_search_provenance() -> None:
    runs_path = IDENTIFICATION_DIR / "runs_registry.json"
    hits_path = IDENTIFICATION_DIR / "identification_vids.json"

    print(f"\n== {runs_path} ==")
    if runs_path.exists():
        with open(runs_path, encoding="utf-8") as f:
            runs = json.load(f)
        records = [{"run_id": run_id, **meta} for run_id, meta in runs.items()]
        written = upsert_search_runs(records)
        print(f"  gelesen: {len(records)} Runs, search_runs upserted: {written}")
    else:
        print("  UEBERSPRUNGEN (Datei nicht gefunden)")

    print(f"\n== {hits_path} ==")
    if hits_path.exists():
        with open(hits_path, encoding="utf-8") as f:
            videos = json.load(f)
        hits = [
            {"video_id": v["video_id"], "run_id": hit["run_id"], "query": hit["query"]}
            for v in videos
            for hit in v.get("found_by", [])
        ]
        written = 0
        for batch in chunked(hits, BATCH_SIZE):
            written += upsert_search_hits(batch)
        print(f"  gelesen: {len(videos)} Videos / {len(hits)} Treffer, "
              f"video_search_hits upserted: {written}")
    else:
        print("  UEBERSPRUNGEN (Datei nicht gefunden)")


def main() -> None:
    backup_path = DB_PATH.with_name(DB_PATH.name + ".bak_pre_phase3a")
    if backup_path.exists():
        print(f"Backup existiert bereits, wird nicht ueberschrieben: {backup_path}")
    else:
        print(f"Sichere {DB_PATH} nach {backup_path} ...")
        shutil.copy2(DB_PATH, backup_path)

    count_before = total_count()
    print(f"videos-Zeilen vor der Migration: {count_before}")

    for path, has_details in JSONL_SOURCES:
        migrate_jsonl_source(path, has_details)

    migrate_json_array_source(JSON_ARRAY_SOURCE)
    migrate_search_provenance()

    count_after = total_count()
    print(f"\nvideos-Zeilen nach der Migration: {count_after} (+{count_after - count_before})")


if __name__ == "__main__":
    main()

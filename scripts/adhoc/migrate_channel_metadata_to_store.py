"""
Einmaliges Migrationsskript fuer den Uebertrag der Kanal-Metadaten
(Abonnenten, Gruendungsdatum, Beschreibung etc.) aus
data/archive/raw/channel_metadata_total.json in die Tabelle channels von
data/store/video_registry.sqlite (siehe video_registry.upsert_channels).
Reiner Daten-Import per COALESCE-Upsert - ueberschreibt nie Vorhandenes,
loescht keine Quelldateien. Kein Bestandteil einer laufenden Pipeline, danach
nicht mehr regelmaessig auszufuehren: neue Kanal-Metadaten-Abfragen landen
bereits live in derselben Tabelle (get_channel_metadata() in
youtube_code.utils.io ruft video_registry.upsert_channels() direkt auf).

Ausfuehrung (aus dem Repo-Root, src muss auf dem PYTHONPATH liegen):
    PYTHONPATH=src python scripts/adhoc/migrate_channel_metadata_to_store.py
"""
import json
import shutil

from youtube_code.config import DATA
from youtube_code.store.video_registry import (
    DB_PATH,
    channels_count,
    upsert_channels,
)

SOURCE_FILE = DATA / "archive" / "raw" / "channel_metadata_total.json"
BATCH_SIZE = 5000


def chunked(iterable, size):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def main() -> None:
    backup_path = DB_PATH.with_name(DB_PATH.name + ".bak_pre_channel_metadata")
    if backup_path.exists():
        print(f"Backup existiert bereits, wird nicht ueberschrieben: {backup_path}")
    elif DB_PATH.exists():
        print(f"Sichere {DB_PATH} nach {backup_path} ...")
        shutil.copy2(DB_PATH, backup_path)

    print(f"\n== {SOURCE_FILE} ==")
    if not SOURCE_FILE.exists():
        print("  UEBERSPRUNGEN (Datei nicht gefunden)")
        return

    with open(SOURCE_FILE, encoding="utf-8") as f:
        records = json.load(f)
    print(f"  gelesen: {len(records)} Kanaele")

    count_before = channels_count()

    written = 0
    for batch in chunked(records, BATCH_SIZE):
        written += upsert_channels(batch)

    count_after = channels_count()
    print(f"  channels upserted: {written}")
    print(
        f"\nchannels-Zeilen vor/nach der Migration: "
        f"{count_before} -> {count_after} (+{count_after - count_before})"
    )


if __name__ == "__main__":
    main()

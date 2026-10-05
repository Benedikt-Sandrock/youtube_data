"""
Einmaliges Migrationsskript fuer den Uebertrag der Sprach-Klassifikation
(is_german/german_ratio/country je Kanal) aus
data/raw/classified_channels_total.json in die Tabelle
language_classification von data/store/video_registry.sqlite (siehe
video_registry.upsert_language_classification). Reiner Daten-Import per
COALESCE-Upsert - ueberschreibt nie Vorhandenes, loescht keine Quelldateien.
Kein Bestandteil einer laufenden Pipeline, danach nicht mehr regelmaessig
auszufuehren.

Ausfuehrung (aus dem Repo-Root, src muss auf dem PYTHONPATH liegen):
    PYTHONPATH=src python scripts/adhoc/migrate_language_classification_to_store.py
"""
import json
import shutil

from youtube_code.config import RAW
from youtube_code.store.video_registry import (
    DB_PATH,
    language_classification_count,
    upsert_language_classification,
)

SOURCE_FILE = RAW / "classified_channels_total.json"
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
    backup_path = DB_PATH.with_name(DB_PATH.name + ".bak_pre_language_classification")
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

    count_before = language_classification_count()

    written = 0
    for batch in chunked(records, BATCH_SIZE):
        written += upsert_language_classification(batch)

    count_after = language_classification_count()
    print(f"  language_classification upserted: {written}")
    print(
        f"\nlanguage_classification-Zeilen vor/nach der Migration: "
        f"{count_before} -> {count_after} (+{count_after - count_before})"
    )


if __name__ == "__main__":
    main()

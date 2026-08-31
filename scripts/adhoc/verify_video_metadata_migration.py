"""
Verifikationsskript zu migrate_video_metadata_to_registry.py (Phase 3a der
Restrukturierung). Prueft NICHT nur "Datei -> DB", sondern simuliert fuer eine
Stichprobe von video_ids den vollen COALESCE-Merge (Reihenfolge: Backup-DB
vor der Migration -> die 5 Quelldateien in Importreihenfolge) und vergleicht
das erwartete Ergebnis Feld fuer Feld mit dem tatsaechlichen Wert in der
migrierten DB. Das faengt auch den Fall ab, dass eine frueher importierte
Quelle den Wert schon gesetzt hat und eine spaetere Quelle ihn (korrekt)
nicht mehr ueberschreiben durfte.

Voraussetzung: video_registry.sqlite.bak_pre_phase3a existiert noch (wird von
migrate_video_metadata_to_registry.py vor der Migration angelegt).

Ausfuehrung:
    PYTHONPATH=src python scripts/adhoc/verify_video_metadata_migration.py
"""
import json
import random
import sqlite3

from youtube_code.config import CHANNEL_LISTS, RAW, SAMPLES
from youtube_code.store.video_registry import DB_PATH

SAMPLE_PER_SOURCE = 40

CORE_FIELDS = [
    "channel_id", "published_at", "title",
    "channel_title", "duration", "view_count", "like_count", "comment_count",
]
DETAIL_FIELDS = [
    "description", "tags", "category_id", "default_language",
    "default_audio_language", "live_broadcast_content", "privacy_status",
    "upload_status", "license", "topic_relevant_topic_ids",
    "topic_categories", "location_description",
]
ALL_FIELDS = CORE_FIELDS + DETAIL_FIELDS
INT_FIELDS = {"view_count", "like_count", "comment_count"}
JSON_FIELDS = {"tags", "topic_relevant_topic_ids", "topic_categories"}

# Welche Felder liefert welche Quelle ueberhaupt (fehlende Felder werden bei
# der Merge-Simulation uebersprungen, nicht als "None gefunden" gewertet).
SOURCES = [
    ("backup", None, ["channel_id", "published_at", "title"]),
    ("video_metadata_total", RAW / "video_metadata_total.jsonl", CORE_FIELDS),
    ("video_metadata_detailed_total", RAW / "video_metadata_detailed_total.jsonl", ALL_FIELDS),
    ("neue_kanaele_detailed", RAW / "neue_kanaele_video_metadata_detailed.jsonl", ALL_FIELDS),
    ("sample_wo_shorts", SAMPLES / "russia" / "sample_50k_channels_russia_ukraine_wo_shorts.jsonl", ALL_FIELDS),
    ("sample_50k_json", RAW / "sample_50k_channels_russia_ukraine.json", CORE_FIELDS),
]
JSONL_SOURCE_NAMES = {"video_metadata_total", "video_metadata_detailed_total",
                       "neue_kanaele_detailed", "sample_wo_shorts"}


def iter_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def reservoir_sample_ids(path, k, rng):
    sample = []
    n = 0
    for record in iter_jsonl(path):
        vid = record.get("video_id")
        if not vid:
            continue
        n += 1
        if len(sample) < k:
            sample.append(vid)
        else:
            j = rng.randint(0, n - 1)
            if j < k:
                sample[j] = vid
    return sample


def to_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def fetch_db_rows(db_path, video_ids, has_new_schema: bool):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    result = {}
    try:
        placeholders = ",".join("?" * len(video_ids))
        if has_new_schema:
            select_cols = ["v.video_id", "v.channel_id", "v.published_at", "v.title",
                           "v.channel_title", "v.duration", "v.view_count", "v.like_count",
                           "v.comment_count"] + [f"d.{c}" for c in DETAIL_FIELDS]
            out_cols = ["video_id"] + CORE_FIELDS + DETAIL_FIELDS
            query = (
                f"SELECT {', '.join(select_cols)} FROM videos v "
                f"LEFT JOIN video_details d ON v.video_id = d.video_id "
                f"WHERE v.video_id IN ({placeholders})"
            )
        else:
            out_cols = ["video_id", "channel_id", "published_at", "title"]
            query = f"SELECT video_id, channel_id, published_at, title FROM videos WHERE video_id IN ({placeholders})"

        for row in con.execute(query, list(video_ids)):
            row_dict = dict(zip(out_cols, row))
            for f in JSON_FIELDS:
                if row_dict.get(f) is not None:
                    row_dict[f] = json.loads(row_dict[f])
            result[row_dict["video_id"]] = row_dict
    finally:
        con.close()
    return result


def main():
    rng = random.Random(42)
    backup_path = DB_PATH.with_name(DB_PATH.name + ".bak_pre_phase3a")
    if not backup_path.exists():
        print(f"ABBRUCH: {backup_path} nicht gefunden - kann Merge-Erwartung nicht simulieren.")
        return

    # 1) Stichprobe an video_ids je Quelle ziehen
    target_ids = set()
    per_source_sample_ids = {}
    for name, path, _fields in SOURCES:
        if path is None:
            continue
        if not path.exists():
            print(f"WARNUNG: {path} nicht gefunden, wird bei der Stichprobe uebersprungen.")
            continue
        if name in JSONL_SOURCE_NAMES:
            ids = reservoir_sample_ids(path, SAMPLE_PER_SOURCE, rng)
        else:
            with open(path, encoding="utf-8") as f:
                records = json.load(f)
            ids = [r["video_id"] for r in rng.sample(records, min(SAMPLE_PER_SOURCE, len(records)))]
        per_source_sample_ids[name] = ids
        target_ids.update(ids)
    print(f"Ziel-Stichprobe: {len(target_ids)} eindeutige video_ids ueber alle Quellen.")

    # 2) Fuer jede Quelle die Records der Ziel-ids einsammeln (ein Streaming-Durchlauf je Datei)
    records_by_source = {"backup": {}}
    for name, path, _fields in SOURCES:
        if name == "backup" or path is None or not path.exists():
            continue
        found = {}
        if name in JSONL_SOURCE_NAMES:
            for record in iter_jsonl(path):
                vid = record.get("video_id")
                if vid in target_ids:
                    found[vid] = record
        else:
            with open(path, encoding="utf-8") as f:
                for record in json.load(f):
                    vid = record.get("video_id")
                    if vid in target_ids:
                        found[vid] = record
        records_by_source[name] = found

    # 3) Backup-DB (alter Schema-Stand) und aktuelle DB (neuer Stand) fuer die Ziel-ids laden
    backup_rows = fetch_db_rows(backup_path, target_ids, has_new_schema=False)
    current_rows = fetch_db_rows(DB_PATH, target_ids, has_new_schema=True)
    records_by_source["backup"] = {vid: row for vid, row in backup_rows.items()}

    # 4) Merge je Ziel-id simulieren und mit der aktuellen DB vergleichen
    mismatches = []
    checked = 0
    for vid in sorted(target_ids):
        actual = current_rows.get(vid)
        if actual is None:
            mismatches.append((vid, "-", "kein Eintrag in videos", None))
            continue
        for field in ALL_FIELDS:
            expected = None
            for name, _path, fields in SOURCES:
                if field not in fields:
                    continue
                record = records_by_source.get(name, {}).get(vid)
                if record is None:
                    continue
                raw = record.get(field)
                if raw is not None:
                    expected = raw
                    break
            actual_value = actual.get(field)
            if field in INT_FIELDS:
                ok = to_int(expected) == actual_value
            else:
                ok = expected == actual_value
            checked += 1
            if not ok:
                mismatches.append((vid, field, expected, actual_value))

    print(f"\n{checked} Feld-Vergleiche ueber {len(target_ids)} video_ids.")
    if mismatches:
        print(f"MISMATCH: {len(mismatches)} Abweichungen:")
        for vid, field, expected, actual_value in mismatches[:30]:
            print(f"  video_id={vid} field={field} erwartet={expected!r} tatsaechlich={actual_value!r}")
        if len(mismatches) > 30:
            print(f"  ... und {len(mismatches) - 30} weitere")
    else:
        print("OK: keine Abweichungen in der Stichprobe.")

    # 5) Zeilenzahlen der reinen Fakten-Tabellen pruefen
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        n_runs = con.execute("SELECT COUNT(*) FROM search_runs").fetchone()[0]
        n_hits = con.execute("SELECT COUNT(*) FROM video_search_hits").fetchone()[0]
    finally:
        con.close()

    runs_path = CHANNEL_LISTS / "all_identification" / "runs_registry.json"
    hits_path = CHANNEL_LISTS / "all_identification" / "identification_vids.json"
    with open(runs_path, encoding="utf-8") as f:
        expected_runs = len(json.load(f))
    with open(hits_path, encoding="utf-8") as f:
        expected_hits = sum(len(v.get("found_by", [])) for v in json.load(f))

    print(f"\nsearch_runs: {n_runs} (erwartet {expected_runs}) -> {'OK' if n_runs == expected_runs else 'MISMATCH'}")
    print(f"video_search_hits: {n_hits} (erwartet {expected_hits}) -> {'OK' if n_hits == expected_hits else 'MISMATCH'}")


if __name__ == "__main__":
    main()

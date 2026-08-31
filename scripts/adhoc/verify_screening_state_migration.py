"""
Verifikationsskript zu migrate_screening_state_to_store.py (Phase 3c der
Restrukturierung, siehe .claude/plans/phase_3c.md).

Prueft:
1. Zeilenzahl: CSV (voller video_id-Scan) vs. COUNT(*) in screening_state.
2. Stichprobe (Reservoir-Sampling ueber video_id, plus gezielte Stichproben
   je politics_final-Ausprägung -1/0/1/NULL und aus screening_round=10) -
   Feld-fuer-Feld-Vergleich aller 19 Spalten gegen eine Read-only-Connection.
3. Konsistenz-Check: update_screening_state.validate_state_consistency() auf
   eine aus der DB exportierte DataFrame anwenden (bestaetigt dieselben
   Invarianten wie die Quell-CSV, ohne die Validierungslogik zu duplizieren).
4. round_counts()/label_counts() gegen value_counts() der Quell-CSV.

Ausfuehrung:
    PYTHONPATH=src python scripts/adhoc/verify_screening_state_migration.py
"""
import random
import sqlite3

import pandas as pd

from youtube_code.politics_screening.screening_config import STATE_FILE
from youtube_code.politics_screening.update_screening_state import (
    validate_state_consistency,
)
from youtube_code.utils.screening_state_store import COLUMNS, DB_PATH, get_state

SOURCE_CSV = STATE_FILE
CSV_CHUNKSIZE = 5_000
SAMPLE_SIZE = 300
TARGET_ROUND = 10


def reservoir_sample_ids(path, k, rng) -> list:
    """Reservoir-Sampling ueber die video_id-Spalte, chunk-weise gelesen."""
    sample = []
    n = 0
    for chunk in pd.read_csv(path, usecols=["video_id"], chunksize=CSV_CHUNKSIZE):
        for vid in chunk["video_id"].dropna().astype(str):
            n += 1
            if len(sample) < k:
                sample.append(vid)
            else:
                j = rng.randint(0, n - 1)
                if j < k:
                    sample[j] = vid
    return sample


def targeted_sample_ids(path, rng, per_bucket=25) -> set:
    """
    Zieht zusaetzlich gezielte Stichproben aus jeder politics_final-
    Ausprägung (-1/0/1/NULL) sowie aus screening_round=TARGET_ROUND, damit die
    Stichprobe nicht rein zufaellig ueber die (in Summe seltenen) gescreenten
    Zeilen hinweggeht.
    """
    buckets: dict = {-1: [], 0: [], 1: [], "NULL": [], "round": []}
    for chunk in pd.read_csv(
        path,
        usecols=["video_id", "politics_final", "screening_round"],
        chunksize=CSV_CHUNKSIZE,
    ):
        for _, row in chunk.iterrows():
            vid = row["video_id"]
            if pd.isna(vid):
                continue
            vid = str(vid)
            label = row["politics_final"]
            key = "NULL" if pd.isna(label) else int(label)
            if key in buckets and len(buckets[key]) < per_bucket:
                buckets[key].append(vid)
            if row.get("screening_round") == TARGET_ROUND and len(buckets["round"]) < per_bucket:
                buckets["round"].append(vid)

    result = set()
    for key, ids in buckets.items():
        result.update(ids)
        print(f"  Bucket {key}: {len(ids)} Stichproben-ids gefunden.")
    return result


def collect_csv_rows(path, target_ids) -> dict:
    """Voller CSV-Chunk-Durchlauf: sammelt die Quell-Zeile je Ziel-video_id (strukturell eindeutig, siehe Migrationsskript)."""
    rows = {}
    for chunk in pd.read_csv(
        path,
        dtype={"video_id": "string", "channel_id": "string"},
        low_memory=False,
        chunksize=CSV_CHUNKSIZE,
    ):
        chunk = chunk.astype(object).where(pd.notnull(chunk), None)
        for record in chunk.to_dict(orient="records"):
            vid = str(record.get("video_id"))
            if vid in target_ids:
                rows[vid] = record
    return rows


def fetch_db_rows(video_ids) -> dict:
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    result = {}
    try:
        placeholders = ",".join("?" * len(video_ids))
        query = f"SELECT {', '.join(COLUMNS)} FROM screening_state WHERE video_id IN ({placeholders})"
        for row in con.execute(query, list(video_ids)):
            d = dict(zip(COLUMNS, row))
            result[d.pop("video_id")] = d
    finally:
        con.close()
    return result


def values_equal(expected, actual) -> bool:
    """Wertsemantischer Vergleich: NaN/None gleichgesetzt, Zahlen ueber float genaehert (int vs. float aus SQLite)."""
    if (expected is None or (isinstance(expected, float) and expected != expected)) and \
       (actual is None or (isinstance(actual, float) and actual != actual)):
        return True
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return float(expected) == float(actual)
    return str(expected) == str(actual)


def main() -> None:
    rng = random.Random(42)

    print(f"== Stichprobe ziehen (Reservoir-Sampling, n={SAMPLE_SIZE}) aus {SOURCE_CSV} ==")
    sample_ids = set(reservoir_sample_ids(SOURCE_CSV, SAMPLE_SIZE, rng))

    print("\n== Gezielte Stichproben je politics_final-Bucket und screening_round=10 ==")
    sample_ids |= targeted_sample_ids(SOURCE_CSV, rng)
    print(f"  {len(sample_ids)} Ziel-video_ids insgesamt.")

    print("\n== Voller CSV-Durchlauf: Quell-Zeilen der Ziel-ids einsammeln ==")
    csv_rows = collect_csv_rows(SOURCE_CSV, sample_ids)
    missing_from_csv = sample_ids - set(csv_rows)
    if missing_from_csv:
        print(f"  WARNUNG: {len(missing_from_csv)} Ziel-ids kamen in der CSV nicht vor: {list(missing_from_csv)[:5]}...")
        sample_ids -= missing_from_csv

    print("\n== Feld-fuer-Feld-Vergleich gegen die migrierte DB ==")
    db_rows = fetch_db_rows(sample_ids)
    mismatches = []
    checked = 0
    for vid in sorted(sample_ids):
        expected = csv_rows[vid]
        actual = db_rows.get(vid)
        if actual is None:
            mismatches.append((vid, "-", "kein Eintrag in screening_state", None))
            continue
        for col in COLUMNS:
            if col == "video_id":
                continue
            checked += 1
            if not values_equal(expected.get(col), actual.get(col)):
                mismatches.append((vid, col, expected.get(col), actual.get(col)))

    print(f"  {checked} Feld-Vergleiche ueber {len(sample_ids)} video_ids.")
    if mismatches:
        print(f"  MISMATCH: {len(mismatches)} Abweichungen:")
        for vid, field, expected_v, actual_v in mismatches[:30]:
            print(f"    video_id={vid} field={field} erwartet={expected_v!r} tatsaechlich={actual_v!r}")
        if len(mismatches) > 30:
            print(f"    ... und {len(mismatches) - 30} weitere")
    else:
        print("  OK: keine Abweichungen in der Stichprobe.")

    print("\n== Konsistenz-Check: validate_state_consistency() auf DB-Export ==")
    db_state = get_state()
    db_state["politics_title"] = db_state["politics_title"].astype("Int8")
    db_state["politics_title_desc"] = db_state["politics_title_desc"].astype("Int8")
    db_state["politics_final"] = db_state["politics_final"].astype("Int8")
    try:
        validate_state_consistency(db_state)
        print("  OK: DB-Export erfuellt dieselben Invarianten wie die Quell-CSV.")
    except ValueError as exc:
        print(f"  MISMATCH: {exc}")

    print("\n== Zeilenzahl-Check (voller CSV-Scan, nur video_id-Spalte) ==")
    unique_ids = set()
    for chunk in pd.read_csv(SOURCE_CSV, usecols=["video_id"], chunksize=CSV_CHUNKSIZE):
        unique_ids.update(chunk["video_id"].dropna().astype(str))
    n_unique = len(unique_ids)
    n_db = len(db_state)
    print(f"  eindeutige video_ids in CSV: {n_unique}")
    print(f"  COUNT(*) in screening_state.sqlite: {n_db}")
    print("  OK" if n_unique == n_db else "  MISMATCH")

    print("\n== round_counts() / label_counts() gegen CSV value_counts() ==")
    csv_full = pd.read_csv(
        SOURCE_CSV,
        usecols=["screening_round", "politics_final"],
        low_memory=False,
    )
    print("-- screening_round (CSV) --")
    print(csv_full["screening_round"].value_counts(dropna=False).sort_index().to_string())
    print("-- screening_round (DB) --")
    print(db_state["screening_round"].value_counts(dropna=False).sort_index().to_string())
    print("-- politics_final (CSV) --")
    print(csv_full["politics_final"].value_counts(dropna=False).sort_index().to_string())
    print("-- politics_final (DB) --")
    print(db_state["politics_final"].value_counts(dropna=False).sort_index().to_string())


if __name__ == "__main__":
    main()

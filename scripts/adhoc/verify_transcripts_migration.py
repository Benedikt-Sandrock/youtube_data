"""
Verifikationsskript zu migrate_transcripts_to_store.py (Phase 3b der
Restrukturierung, siehe .claude/plans/phase_3b.md).

Zieht eine Stichprobe von video_ids (Reservoir-Sampling ueber die volle
CSV) plus den bekannten embedded-newline-Sonderfall QsVgwJ40-zo, sammelt
in einem vollen CSV-Chunk-Durchlauf ALLE Vorkommen dieser IDs (Duplikate
koennen irgendwo in der Datei liegen) und simuliert dieselbe Prioritaets-/
Last-Wins-Regel wie die ON CONFLICT-Klausel in transcript_store.py in
Python (expected_winner()). Vergleicht das Ergebnis Feld fuer Feld gegen
eine Read-only-Connection auf transcripts.sqlite. Prueft zusaetzlich den
QsVgwJ40-zo-Sonderfall explizit (Newline-Erhalt) und einen abschliessenden
Zeilenzahl-Check (eindeutige CSV-video_ids vs. COUNT(*) in der DB).

Ausfuehrung:
    PYTHONPATH=src python scripts/adhoc/verify_transcripts_migration.py
"""
import json
import random
import sqlite3

import pandas as pd

from youtube_code.config import TRANSCRIPTS
from youtube_code.utils.transcript_store import DB_PATH, _n_segments, _to_bool_int

SOURCE_CSV = TRANSCRIPTS / "all_transcripts_segments.csv"
CSV_CHUNKSIZE = 500
SAMPLE_SIZE = 200
FORCED_SPECIAL_CASE = "QsVgwJ40-zo"

FIELDS = ["transcript_segments", "language_code", "is_generated", "status", "n_segments"]


def _status_rank(status) -> int:
    if status == "OK":
        return 0
    if status == "Kein Transkript":
        return 1
    return 2


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


def collect_occurrences(path, target_ids) -> dict:
    """
    Voller CSV-Chunk-Durchlauf: sammelt fuer jede Ziel-video_id ALLE
    Vorkommen in Datei-Reihenfolge (fuer die Last-Wins-Simulation muss die
    Reihenfolge erhalten bleiben).
    """
    occurrences = {vid: [] for vid in target_ids}
    n_rows = 0
    for chunk in pd.read_csv(path, chunksize=CSV_CHUNKSIZE):
        chunk = chunk.astype(object).where(pd.notnull(chunk), None)
        for record in chunk.to_dict(orient="records"):
            n_rows += 1
            vid = str(record.get("video_id"))
            if vid in occurrences:
                occurrences[vid].append(record)
    return occurrences, n_rows


def expected_winner(records: list) -> dict | None:
    """
    Simuliert die ON-CONFLICT-Prioritaets-/Last-Wins-Regel aus
    transcript_store.upsert_transcripts ueber alle CSV-Vorkommen einer
    video_id: niedrigster Status-Rang gewinnt, bei Gleichstand der zuletzt
    in Datei-Reihenfolge aufgetretene Datensatz.
    """
    winner = None
    winner_rank = None
    for record in records:
        rank = _status_rank(record.get("status"))
        if winner is None or rank <= winner_rank:
            winner = record
            winner_rank = rank
    return winner


def normalize_segments(value):
    """JSON-normalisiert transcript_segments fuer einen wertsemantischen Vergleich."""
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        if s == "" or s.lower() == "nan":
            return None
        try:
            return json.loads(s)
        except (TypeError, ValueError):
            return value
    return value


def fetch_db_rows(video_ids) -> dict:
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    result = {}
    try:
        placeholders = ",".join("?" * len(video_ids))
        query = (
            f"SELECT video_id, transcript_segments, language_code, is_generated, status, n_segments "
            f"FROM transcripts WHERE video_id IN ({placeholders})"
        )
        for row in con.execute(query, list(video_ids)):
            d = dict(zip(["video_id", *FIELDS], row))
            result[d.pop("video_id")] = d
    finally:
        con.close()
    return result


def check_special_case(occurrences: dict) -> None:
    print(f"\n== Sonderfall {FORCED_SPECIAL_CASE} (embedded newline) ==")
    records = occurrences.get(FORCED_SPECIAL_CASE, [])
    if len(records) != 1:
        print(f"  WARNUNG: {len(records)} CSV-Vorkommen gefunden, 1 erwartet (Fall evtl. nicht mehr eindeutig).")
        if not records:
            return
    csv_status = records[-1].get("status")
    if "\n" not in str(csv_status):
        print("  WARNUNG: CSV-status enthaelt keinen Newline mehr (Sonderfall evtl. veraltet).")

    db_row = fetch_db_rows([FORCED_SPECIAL_CASE]).get(FORCED_SPECIAL_CASE)
    if db_row is None:
        print("  MISMATCH: keine Zeile in der DB gefunden.")
        return
    if db_row["status"] == csv_status:
        print("  OK: DB-status ist zeichen-fuer-zeichen identisch zur CSV-Zelle (inkl. Newline).")
    else:
        print(f"  MISMATCH: CSV-status={csv_status!r} vs. DB-status={db_row['status']!r}")


def main() -> None:
    rng = random.Random(42)

    print(f"== Stichprobe ziehen (Reservoir-Sampling, n={SAMPLE_SIZE}) aus {SOURCE_CSV} ==")
    sample_ids = set(reservoir_sample_ids(SOURCE_CSV, SAMPLE_SIZE, rng))
    sample_ids.add(FORCED_SPECIAL_CASE)
    print(f"  {len(sample_ids)} Ziel-video_ids (inkl. erzwungenem Sonderfall).")

    print("\n== Voller CSV-Durchlauf: alle Vorkommen der Ziel-ids einsammeln ==")
    occurrences, n_rows = collect_occurrences(SOURCE_CSV, sample_ids)
    n_unique_total = None  # wird unten im Zeilenzahl-Check separat ermittelt
    missing_from_csv = [vid for vid, recs in occurrences.items() if not recs]
    if missing_from_csv:
        print(f"  WARNUNG: {len(missing_from_csv)} Ziel-ids kamen in der CSV nicht vor (Stichprobenartefakt): {missing_from_csv[:5]}...")
        sample_ids -= set(missing_from_csv)

    print("\n== Feld-fuer-Feld-Vergleich gegen die migrierte DB ==")
    db_rows = fetch_db_rows(sample_ids)
    mismatches = []
    checked = 0
    for vid in sorted(sample_ids):
        expected = expected_winner(occurrences[vid])
        actual = db_rows.get(vid)
        if actual is None:
            mismatches.append((vid, "-", "kein Eintrag in transcripts", None))
            continue

        exp_segments_text = expected.get("transcript_segments")
        exp_status = expected.get("status")
        exp_lang = expected.get("language_code")
        exp_is_gen = _to_bool_int(expected.get("is_generated"))
        exp_n_segments = _n_segments(exp_segments_text)

        checks = [
            ("transcript_segments", normalize_segments(exp_segments_text), normalize_segments(actual["transcript_segments"])),
            ("language_code", exp_lang, actual["language_code"]),
            ("status", exp_status, actual["status"]),
            ("is_generated", exp_is_gen, actual["is_generated"]),
            ("n_segments", exp_n_segments, actual["n_segments"]),
        ]
        for field, exp_val, act_val in checks:
            checked += 1
            if exp_val != act_val:
                mismatches.append((vid, field, exp_val, act_val))

    print(f"  {checked} Feld-Vergleiche ueber {len(sample_ids)} video_ids.")
    if mismatches:
        print(f"  MISMATCH: {len(mismatches)} Abweichungen:")
        for vid, field, expected, actual_value in mismatches[:30]:
            print(f"    video_id={vid} field={field} erwartet={expected!r} tatsaechlich={actual_value!r}")
        if len(mismatches) > 30:
            print(f"    ... und {len(mismatches) - 30} weitere")
    else:
        print("  OK: keine Abweichungen in der Stichprobe.")

    check_special_case(occurrences)

    print("\n== Zeilenzahl-Check (voller CSV-Scan, nur video_id-Spalte) ==")
    unique_ids = set()
    for chunk in pd.read_csv(SOURCE_CSV, usecols=["video_id"], chunksize=CSV_CHUNKSIZE):
        unique_ids.update(chunk["video_id"].dropna().astype(str))
    n_unique = len(unique_ids)

    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        n_db = con.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
    finally:
        con.close()

    print(f"  eindeutige video_ids in CSV: {n_unique}")
    print(f"  COUNT(*) in transcripts.sqlite: {n_db}")
    print("  OK" if n_unique == n_db else "  MISMATCH")


if __name__ == "__main__":
    main()

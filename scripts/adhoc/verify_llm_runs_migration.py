"""
Verifikationsskript zu migrate_llm_runs_to_store.py (Phase 3d der
Restrukturierung, siehe .claude/plans/phase_3d.md).

Da die Gesamtmenge klein ist (83 Zeilen), voller Vergleich statt Stichprobe:
1. Fuer jede der vier Quell-CSVs: jede Zeile per (source, run_id) in der DB
   nachschlagen, alle 16 Facheinheiten-Spalten Feld fuer Feld vergleichen
   (Read-only-Connection).
2. Zeilenzahl-Check je Quelle und gesamt (83).
3. Stichprobe der results_path-Existenz (nur informativ geloggt, kein
   OK/MISMATCH-Kriterium - zwei der vier Quellen haben erwartetermassen tote
   Pfade).

Ausfuehrung:
    PYTHONPATH=src python scripts/adhoc/verify_llm_runs_migration.py
"""
import sqlite3

import pandas as pd

from youtube_code.config import ROOT, SRC
from youtube_code.utils.llm_run_store import DB_PATH, REGISTRY_COLUMNS

SOURCES = [
    ("screening_active",        SRC / "llm_analysis" / "registry" / "runs_registry.csv"),
    ("segment_analysis_active", ROOT / "llm_analysis" / "registry" / "runs_registry.csv"),
    ("screening_legacy",        SRC / "llm_analysis" / "registry" / "runs_registry_legacy.csv"),
    ("gemini_old",              SRC / "llm_analysis" / "registry" / "runs_registry_old.csv"),
]

EXPECTED_COUNTS = {
    "screening_active": 25,
    "segment_analysis_active": 19,
    "screening_legacy": 25,
    "gemini_old": 14,
}
EXPECTED_TOTAL = 83

# Aus der Plan-Recherche bekannte results_path-Stichproben (nur informativ).
SAMPLE_RESULT_PATHS = {
    "outputs/segment_analysis/run_0001_IDEOLOGIE_I.csv": True,
    "outputs/llm/longitudinal/title_classification/run_0002.csv": True,
    "outputs/llm/title_classification/run_0001.csv": False,
    "outputs/llm/gemini/results/run_0001.csv": False,
}


def values_equal(expected, actual) -> bool:
    """Wertsemantischer Vergleich: NaN/None gleichgesetzt, Zahlen ueber float genaehert."""
    if (expected is None or (isinstance(expected, float) and expected != expected)) and \
       (actual is None or (isinstance(actual, float) and actual != actual)):
        return True
    if isinstance(expected, str) and expected.strip() == "" and \
       (actual is None or (isinstance(actual, str) and actual.strip() == "")):
        return True
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return float(expected) == float(actual)
    return str(expected) == str(actual)


def fetch_db_row(con, source, run_id):
    query = f"SELECT {', '.join(REGISTRY_COLUMNS)} FROM llm_runs WHERE source = ? AND run_id = ?"
    row = con.execute(query, [source, run_id]).fetchone()
    if row is None:
        return None
    return dict(zip(REGISTRY_COLUMNS, row))


def main() -> None:
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)

    total_checked_rows = 0
    total_field_comparisons = 0
    total_mismatches = 0
    grand_total_csv_rows = 0

    try:
        for source, path in SOURCES:
            print(f"\n== Quelle: {source} ({path}) ==")
            df = pd.read_csv(path, dtype=str)
            df = df.astype(object).where(pd.notnull(df), None)
            n_csv = len(df)
            grand_total_csv_rows += n_csv
            expected = EXPECTED_COUNTS[source]
            print(f"  CSV-Zeilen: {n_csv} (erwartet {expected}) [{'OK' if n_csv == expected else 'MISMATCH'}]")

            n_db = con.execute("SELECT COUNT(*) FROM llm_runs WHERE source = ?", [source]).fetchone()[0]
            print(f"  DB-Zeilen (source={source}): {n_db} [{'OK' if n_db == n_csv else 'MISMATCH'}]")

            mismatches = []
            for record in df.to_dict(orient="records"):
                run_id = record["run_id"]
                total_checked_rows += 1
                db_row = fetch_db_row(con, source, run_id)
                if db_row is None:
                    mismatches.append((run_id, "-", "kein Eintrag in llm_runs", None))
                    continue
                for col in REGISTRY_COLUMNS:
                    if col == "run_id":
                        continue
                    total_field_comparisons += 1
                    if not values_equal(record.get(col), db_row.get(col)):
                        mismatches.append((run_id, col, record.get(col), db_row.get(col)))

            if mismatches:
                total_mismatches += len(mismatches)
                print(f"  MISMATCH: {len(mismatches)} Abweichungen:")
                for run_id, field, expected_v, actual_v in mismatches[:20]:
                    print(f"    run_id={run_id} field={field} erwartet={expected_v!r} tatsaechlich={actual_v!r}")
                if len(mismatches) > 20:
                    print(f"    ... und {len(mismatches) - 20} weitere")
            else:
                print(f"  OK: alle {n_csv} Zeilen vollstaendig uebereinstimmend.")

        print(f"\n== Gesamt ==")
        print(f"  CSV-Zeilen gesamt: {grand_total_csv_rows} (erwartet {EXPECTED_TOTAL})")
        n_db_total = con.execute("SELECT COUNT(*) FROM llm_runs").fetchone()[0]
        print(f"  DB-Zeilen gesamt: {n_db_total}")
        print(f"  Feld-Vergleiche: {total_field_comparisons} ueber {total_checked_rows} Zeilen")
        if total_mismatches == 0 and grand_total_csv_rows == EXPECTED_TOTAL == n_db_total:
            print("  OK: vollstaendige Uebereinstimmung, keine Abweichungen.")
        else:
            print(f"  MISMATCH: {total_mismatches} Feld-Abweichungen und/oder Zeilenzahl-Abweichung.")

        print("\n== results_path-Existenz (informativ, kein OK/MISMATCH-Kriterium) ==")
        for rel_path, expected_exists in SAMPLE_RESULT_PATHS.items():
            actual_exists = (ROOT / rel_path).exists()
            note = "wie erwartet" if actual_exists == expected_exists else "abweichend von Recherche-Stand"
            print(f"  {rel_path}: exists={actual_exists} ({note})")
    finally:
        con.close()


if __name__ == "__main__":
    main()

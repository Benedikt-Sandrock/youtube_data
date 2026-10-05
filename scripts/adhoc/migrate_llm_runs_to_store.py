"""
Einmaliges Migrationsskript fuer Phase 3d der Restrukturierung
(siehe .claude/restructuring/RESTRUCTURING_PROGRESS.md und
.claude/plans/phase_3d.md).

Importiert die vier parallelen LLM-Run-Registry-CSVs (identisches Schema,
aber vier getrennte run_id-Zaehler, die alle bei run_0001 beginnen) nach
data/raw/llm_runs.sqlite (Tabelle llm_runs, siehe
youtube_code.store.llm_run_store). Upsert-basiert ueber (source, run_id),
daher idempotent bei mehrfacher Ausfuehrung. Loescht keine der vier
Quell-CSVs.

Vor dem Lauf sicherstellen, dass keiner der Schreib-Orte parallel in eine der
beiden aktiven Registries schreibt (submit_batch_jobs.py, download_results.py,
run_longitudinal_screening_batch.py, run_politics_screening_batch.py,
submit_segments.py, download_segments*.py) - wird unten technisch per
Prozessliste geprueft, analog zum Checkpoint in Phase 3b/3c.

Ausfuehrung (aus dem Repo-Root, src muss auf dem PYTHONPATH liegen):
    PYTHONPATH=src python scripts/adhoc/migrate_llm_runs_to_store.py
"""
import shutil
import subprocess

import pandas as pd

from youtube_code.config import ROOT, SRC
from youtube_code.store.llm_run_store import (
    DB_PATH,
    REGISTRY_COLUMNS,
    source_counts,
    total_count,
    upsert_runs,
)

SOURCES = [
    ("screening_active",        SRC / "llm_analysis" / "registry" / "runs_registry.csv"),
    ("segment_analysis_active", ROOT / "llm_analysis" / "registry" / "runs_registry.csv"),
    ("screening_legacy",        SRC / "llm_analysis" / "registry" / "runs_registry_legacy.csv"),
    ("gemini_old",              SRC / "llm_analysis" / "registry" / "runs_registry_old.csv"),
]

# Referenzwerte aus dem Plan (voller Scan zum Planungszeitpunkt).
EXPECTED_COUNTS = {
    "screening_active": 25,
    "segment_analysis_active": 19,
    "screening_legacy": 25,
    "gemini_old": 14,
}
EXPECTED_TOTAL = 83

# Prozessnamen der Schreib-Orte, die in eine der beiden aktiven Registries
# schreiben koennten (Sicherheits-Checkpoint).
WRITER_SCRIPT_NAMES = [
    "submit_batch_jobs.py",
    "download_results.py",
    "run_longitudinal_screening_batch.py",
    "run_politics_screening_batch.py",
    "submit_segments.py",
    "download_segments.py",
]


def check_no_writer_running() -> None:
    """
    Technischer Sicherheits-Checkpoint: bricht ab, falls einer der
    Schreib-Orte aktuell als Prozess laeuft (Windows: Get-CimInstance ueber
    powershell, da tasklist selbst keine Kommandozeile anzeigt).
    """
    print("== Sicherheits-Checkpoint: laufende LLM-Run-Schreib-Prozesse pruefen ==")
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" "
                "| Select-Object -ExpandProperty CommandLine",
            ],
            capture_output=True, text=True, timeout=30,
        )
        command_lines = result.stdout or ""
    except Exception as exc:
        print(f"  WARNUNG: Prozessliste konnte nicht geprueft werden ({exc}). "
              "Fahre fort, da der Nutzer bereits bestaetigt hat, dass kein "
              "Batch-Job-Lauf aktiv ist.")
        return

    hits = [name for name in WRITER_SCRIPT_NAMES if name in command_lines]
    if hits:
        raise SystemExit(
            f"ABBRUCH: Laufender Prozess gefunden, der auf {hits} referenziert. "
            "Bitte zuerst beenden, bevor migriert wird."
        )
    print("  OK: kein aktiver Schreib-Prozess gefunden.")


def preflight() -> dict:
    """Liest jede Quell-CSV, prueft Zeilenzahl gegen den Referenzwert aus dem Plan."""
    print("\n== Preflight: Zeilenzahlen je Quelle ==")
    counts = {}
    for source, path in SOURCES:
        if not path.exists():
            raise SystemExit(f"ABBRUCH: Quelldatei fehlt: {path}")
        df = pd.read_csv(path, dtype=str)
        n = len(df)
        counts[source] = n
        expected = EXPECTED_COUNTS[source]
        status = "OK" if n == expected else "ABWEICHUNG"
        print(f"  {source}: {n} Zeilen (erwartet {expected}) [{status}]")

    total = sum(counts.values())
    print(f"  Summe: {total} (erwartet {EXPECTED_TOTAL})")
    if counts != EXPECTED_COUNTS:
        raise SystemExit(
            f"ABBRUCH: Zeilenzahlen weichen vom Plan-Referenzwert ab: {counts} "
            f"!= {EXPECTED_COUNTS}. Bitte manuell pruefen, bevor migriert wird."
        )
    return counts


def migrate() -> None:
    print("\n== Migration ==")
    for source, path in SOURCES:
        df = pd.read_csv(path, dtype=str)
        df = df[REGISTRY_COLUMNS]
        df = df.astype(object).where(pd.notnull(df), None)
        records = df.to_dict(orient="records")
        n_written = upsert_runs(source, records)
        print(f"  {source}: {len(records)} Zeilen gelesen, {n_written} upserted (angewendet)")


def main() -> None:
    check_no_writer_running()

    backup_path = DB_PATH.with_name(DB_PATH.name + ".bak_pre_migration")
    if DB_PATH.exists():
        if backup_path.exists():
            print(f"Backup existiert bereits, wird nicht ueberschrieben: {backup_path}")
        else:
            print(f"Sichere {DB_PATH} nach {backup_path} ...")
            shutil.copy2(DB_PATH, backup_path)
    else:
        print(f"{DB_PATH} existiert noch nicht, kein Backup noetig.")

    expected_counts = preflight()

    count_before = total_count()
    print(f"\nllm_runs-Zeilen vor der Migration: {count_before}")

    migrate()

    count_after = total_count()
    print(f"\nllm_runs-Zeilen nach der Migration: {count_after}")
    expected_total = sum(expected_counts.values())
    if count_after != expected_total:
        print(f"WARNUNG: {count_after} Zeilen in der DB weicht ab von {expected_total} erwarteten Zeilen.")
    else:
        print(f"OK: stimmt mit den erwarteten {expected_total} Zeilen ueberein.")

    print("\n== source_counts() ==")
    print(source_counts().to_string(index=False))
    print(f"\ntotal_count() = {total_count()}")


if __name__ == "__main__":
    main()

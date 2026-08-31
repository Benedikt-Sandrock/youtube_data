"""
Verifiziert Phase 4b (LLM-Run-Registry: Call-Sites auf llm_run_store
umgestellt, siehe .claude/plans/phase_4.md) ohne echte Batch-Jobs
abzuschicken oder die produktive data/raw/llm_runs.sqlite zu veraendern.

Zwei Teile:
  1. Import-Check: alle in 4b umgestellten Module importieren fehlerfrei
     (faengt kaputte Importe/Signaturen ab, die ein reiner grep uebersieht).
  2. Funktions-Check: add_run()/update_run()/next_run_id() gegen eine
     TEMPORAERE KOPIE von llm_runs.sqlite - insbesondere die fetch-merge-
     upsert-Semantik von update_run() (nicht uebergebene Felder duerfen
     nicht auf NULL fallen).

Ausfuehren mit dem venv-Interpreter, PYTHONPATH=src:
    PYTHONPATH=src .venv/Scripts/python.exe scripts/adhoc/verify_llm_run_callsites.py
"""

from __future__ import annotations

import importlib
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

CALLSITE_MODULES = [
    "youtube_code.utils.llm_run_store",
    "youtube_code.politics_screening.screening_config",
    "youtube_code.segment_analysis.segment_analysis_config",
    "youtube_code.llm_analysis.submit_batch_jobs",
    "youtube_code.llm_analysis.download_results",
    "youtube_code.politics_screening.retry_run",
    "youtube_code.politics_screening.update_screening_state",
    "youtube_code.segment_analysis.submit_segments",
    "youtube_code.segment_analysis.download_segments",
    "youtube_code.segment_analysis.download_segments_simple",
    "youtube_code.llm_analysis.run_longitudinal_screening_batch",
    "youtube_code.llm_analysis.run_politics_screening_batch",
    "youtube_code.llm_analysis.run_transcript_classification_batch",
    "youtube_code.llm_analysis.evaluate_politics_screening",
]


def check_imports() -> bool:
    print("=== 1/2 Import-Check ===")
    ok = True
    for module_name in CALLSITE_MODULES:
        try:
            importlib.import_module(module_name)
            print(f"  OK   {module_name}")
        except Exception as error:
            ok = False
            print(f"  FAIL {module_name} -> {type(error).__name__}: {error}")
    return ok


def check_store_functions() -> bool:
    print("\n=== 2/2 Funktions-Check (llm_run_store, temporaere DB-Kopie) ===")
    import youtube_code.utils.llm_run_store as store

    real_db_path = store.DB_PATH
    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_db_path = Path(tmp_dir) / "llm_runs_verify.sqlite"
        shutil.copy(real_db_path, temp_db_path)
        store.DB_PATH = temp_db_path
        try:
            before = store.get_run("screening_active", "run_0001")

            store.update_run("screening_active", "run_0001", status="VERIFY_TEST")
            after = store.get_run("screening_active", "run_0001")
            assert after["status"] == "VERIFY_TEST", "update_run hat status nicht gesetzt"
            assert after["results_path"] == before["results_path"], (
                "update_run hat ein nicht uebergebenes Feld (results_path) "
                "veraendert - fetch-merge-upsert ist kaputt"
            )
            assert after["model"] == before["model"], (
                "update_run hat ein nicht uebergebenes Feld (model) "
                "veraendert - fetch-merge-upsert ist kaputt"
            )
            print("  OK   update_run() aendert nur die uebergebenen Felder")

            run_id_1 = store.add_run("verify_test_source", prompt_id="P1", model="m1")
            run_id_2 = store.add_run("verify_test_source", prompt_id="P2", model="m2")
            assert run_id_1 == "run_0001" and run_id_2 == "run_0002", (
                f"next_run_id zaehlt nicht korrekt je source: {run_id_1}, {run_id_2}"
            )
            print(f"  OK   add_run()/next_run_id() vergeben {run_id_1}, {run_id_2} fuer eine neue source")

            unaffected = store.get_runs(source="screening_active")
            assert len(unaffected) == 25, (
                f"screening_active hat {len(unaffected)} statt 25 Zeilen - "
                "add_run() fuer eine andere source hat abgefaerbt"
            )
            print("  OK   andere sources bleiben unveraendert (kein Cross-Source-Leak)")
        finally:
            store.DB_PATH = real_db_path
    return True


def main() -> None:
    imports_ok = check_imports()
    functions_ok = check_store_functions() if imports_ok else False

    print("\n=== Ergebnis ===")
    if imports_ok and functions_ok:
        print("Alle Checks bestanden.")
    else:
        print("Mindestens ein Check ist fehlgeschlagen - siehe oben.")
        sys.exit(1)


if __name__ == "__main__":
    main()

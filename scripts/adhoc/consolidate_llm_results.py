"""
Phase 4e, Schritt 2 der Restrukturierung (.claude/plans/phase_4.md):
physische LLM-Ergebnis-Konsolidierung. Verschiebt die Ergebnisdateien der
beiden aktiven llm_run_store-Quellen (screening_active,
segment_analysis_active) von ihren verstreuten Ordnern
(outputs/llm/longitudinal/{title,description}_classification/,
outputs/segment_analysis/) nach outputs/llm_results/<source>__<run_id>/
(Muster aus .claude/plans/phase_3d.md Abschnitt 6) und aktualisiert die
results_path-Spalte in llm_runs.sqlite entsprechend.

Zuordnung: jede Datei im Quellordner wird ueber ihr "run_NNNN"-Praefix einem
Run zugeordnet (auch Nebendateien wie *_group_validation.csv, *_copy.csv,
*_retry.csv, *_combined.csv, *_corrected.csv landen im selben Zielordner wie
die in results_path referenzierte Hauptdatei). Dateien ohne run_NNNN-Praefix
(abgeleitete Analysen in outputs/segment_analysis/, HANDOFF-Dokus etc.)
bleiben unangetastet liegen.

outputs/llm/gemini/nahost_descriptive_figures/ wird bewusst NICHT angefasst
(Nutzerentscheidung, siehe Plan-Context) - genau wie screening_legacy/
gemini_old (referenzierte Dateien existieren laut Phase-3d-Recherche
physisch nicht mehr, dort bleibt nur die DB-Zeile als Audit-Trail).

Nutzung:
    PYTHONPATH=src .venv/Scripts/python.exe scripts/adhoc/consolidate_llm_results.py --dry-run
    PYTHONPATH=src .venv/Scripts/python.exe scripts/adhoc/consolidate_llm_results.py
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from youtube_code.config import ROOT, OUTPUTS  # noqa: E402
from youtube_code.store import llm_run_store  # noqa: E402

RUN_ID_RE = re.compile(r"^(run_\d{4})(?:[_.].*)?$")

SOURCE_DIRS = {
    "screening_active": [
        OUTPUTS / "llm" / "longitudinal" / "title_classification",
        OUTPUTS / "llm" / "longitudinal" / "description_classification",
    ],
    "segment_analysis_active": [
        OUTPUTS / "segment_analysis",
    ],
}

DEST_ROOT = OUTPUTS / "llm_results"


def plan_moves():
    """
    Liefert eine Liste von (source, run_id, src_path, dest_path)-Tupeln fuer
    alle Dateien, die anhand ihres run_NNNN-Praefix einem Run zugeordnet
    werden koennen. Dateien ohne dieses Praefix werden uebersprungen.
    """
    moves = []
    for source, dirs in SOURCE_DIRS.items():
        for d in dirs:
            if not d.exists():
                continue
            for f in sorted(d.iterdir()):
                if not f.is_file():
                    continue
                m = RUN_ID_RE.match(f.name)
                if not m:
                    continue
                run_id = m.group(1)
                dest_dir = DEST_ROOT / f"{source}__{run_id}"
                moves.append((source, run_id, f, dest_dir / f.name))
    return moves


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    moves = plan_moves()
    print(f"{len(moves)} Dateien zugeordnet fuer Verschiebung.\n")

    by_source = {}
    for source, run_id, src, dest in moves:
        by_source.setdefault(source, set()).add(run_id)
    for source, run_ids in by_source.items():
        print(f"  {source}: {len(run_ids)} Runs betroffen")

    if args.dry_run:
        print("\n--dry-run: keine Dateien werden verschoben, keine DB-Aenderung.")
        for source, run_id, src, dest in moves:
            print(f"  [{source}] {src.relative_to(ROOT)} -> {dest.relative_to(ROOT)}")
        return

    # 1. Dateien verschieben
    moved = 0
    for source, run_id, src, dest in moves:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        moved += 1
    print(f"\n{moved} Dateien verschoben.")

    # 2. results_path in der DB auf den neuen Pfad umbiegen. Berechnet den
    #    Zielpfad unabhaengig vom in-memory move_map neu (robust gegen einen
    #    Teil-Abbruch nach Schritt 1: leitet aus dem alten Dateinamen +
    #    run_NNNN-Praefix + Zielmuster ab, statt sich auf die Reihenfolge in
    #    dieser main()-Ausfuehrung zu verlassen).
    updated = 0
    for source in SOURCE_DIRS:
        runs = llm_run_store.get_runs(source=source)
        for _, row in runs.iterrows():
            old_path = row.get("results_path")
            if not isinstance(old_path, str) or not old_path.strip():
                continue
            old_path_obj = Path(old_path)
            m = RUN_ID_RE.match(old_path_obj.name)
            if not m:
                continue
            run_id = m.group(1)
            new_path = DEST_ROOT / f"{source}__{run_id}" / old_path_obj.name
            if str(new_path) != old_path and new_path.exists():
                llm_run_store.update_run(source, row["run_id"], results_path=str(new_path))
                updated += 1
    print(f"{updated} results_path-Werte in llm_runs.sqlite aktualisiert.")

    # 3. leere Quellordner entfernen
    for dirs in SOURCE_DIRS.values():
        for d in dirs:
            if d.exists() and not any(d.iterdir()):
                d.rmdir()
                print(f"Leerer Ordner entfernt: {d.relative_to(ROOT)}")
    longitudinal = ROOT / "outputs" / "llm" / "longitudinal"
    if longitudinal.exists() and not any(longitudinal.iterdir()):
        longitudinal.rmdir()
        print(f"Leerer Ordner entfernt: {longitudinal.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

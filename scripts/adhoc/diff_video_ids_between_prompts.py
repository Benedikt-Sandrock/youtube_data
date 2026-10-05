"""
Vergleicht zwei Segment-Analyse-Prompts anhand der Video-IDs, fuer die sie
gelaufen sind, und schreibt die Mengendifferenz in beide Richtungen als
CSVs (Spalte "video_id", max. MAX_ROWS_PER_FILE Zeilen je Datei).

Aufrufstruktur ueber die Datenbanken/Dateien des Projekts:

1. llm_runs.sqlite (Modul store.llm_run_store, Tabelle llm_runs)
   ist die Registry aller eingereichten Batch-Jobs. Sie enthaelt selbst
   KEINE Video-IDs, nur Metadaten je Run: welcher `prompt_id` mit welchem
   `dataset_id`/`dataset_version` lief, und unter `results_path` den Pfad
   zur zugehoerigen Ergebnis-CSV. get_runs(source=..., ...) liefert diese
   Registry gefiltert als DataFrame.
2. Fuer jeden Run mit passendem `prompt_id` wird die CSV unter
   `results_path` gelesen (siehe segment_analysis/README.md: eine Zeile
   je Segment x Replikat, Spalte `video_id` ist Teil der Identitaet jeder
   Zeile). Die `video_id`-Spalte aller passenden Runs wird zu einem Set
   vereinigt -> "alle Video-IDs, fuer die Prompt X gelaufen ist".
3. Kein Zugriff auf video_registry/transcript_store noetig, da nur
   Video-IDs aus den LLM-Ergebnissen selbst verglichen werden, nicht
   gegen Metadaten oder Transkript-Verfuegbarkeit.
4. Die Mengendifferenz (nur bei Prompt A, nicht bei Prompt B / und
   umgekehrt) wird in Bloecken von MAX_ROWS_PER_FILE Zeilen als CSVs
   nach OUTPUT_DIR geschrieben.
"""
import math

import pandas as pd

from youtube_code.config import EXPLORATION
from youtube_code.store import llm_run_store

# --- CONFIG ---------------------------------------------------------------

SOURCE = "segment_analysis_active"

PROMPT_A = "POSITION_V1"
PROMPT_B = "POPULISMUS_P"

# Nur Runs mit diesem Status beruecksichtigen (None = alle Status).
STATUS_FILTER = "downloaded"

OUTPUT_DIR = EXPLORATION
MAX_ROWS_PER_FILE = 5000

# --- Implementierung --------------------------------------------------------


def video_ids_for_prompt(prompt_id: str) -> set[str]:
    """
    Vereinigt die video_id-Spalte aller heruntergeladenen Ergebnis-CSVs
    der Runs mit gegebenem prompt_id (source=SOURCE) zu einem Set.
    """
    runs = llm_run_store.get_runs(source=SOURCE)
    runs = runs[runs["prompt_id"] == prompt_id]

    if STATUS_FILTER is not None:
        runs = runs[runs["status"] == STATUS_FILTER]

    ids: set[str] = set()
    for _, run in runs.iterrows():
        results_path = run["results_path"]
        if not results_path:
            print(f"  [uebersprungen] {run['run_id']}: kein results_path gesetzt")
            continue
        df = pd.read_csv(results_path, usecols=["video_id"])
        ids.update(df["video_id"].dropna().unique().tolist())
        print(f"  {run['run_id']} ({results_path}): {df['video_id'].nunique()} Video-IDs")

    print(f"Prompt {prompt_id}: {len(runs)} Runs, {len(ids)} eindeutige Video-IDs insgesamt")
    return ids


def write_chunked_csv(video_ids: set[str], out_stem: str) -> None:
    """
    Schreibt video_ids als eine oder mehrere CSVs (Spalte "video_id") mit
    je maximal MAX_ROWS_PER_FILE Zeilen: <out_stem>.csv bei einer Datei,
    sonst <out_stem>_part1.csv, <out_stem>_part2.csv, ...
    """
    ids_sorted = sorted(video_ids)
    if not ids_sorted:
        print(f"  {out_stem}: keine Video-IDs, keine Datei geschrieben")
        return

    n_parts = math.ceil(len(ids_sorted) / MAX_ROWS_PER_FILE)
    for i in range(n_parts):
        chunk = ids_sorted[i * MAX_ROWS_PER_FILE : (i + 1) * MAX_ROWS_PER_FILE]
        suffix = f"_part{i + 1}" if n_parts > 1 else ""
        out_path = OUTPUT_DIR / f"{out_stem}{suffix}.csv"
        pd.DataFrame({"video_id": chunk}).to_csv(out_path, index=False)
        print(f"  geschrieben: {out_path} ({len(chunk)} Zeilen)")


def main() -> None:
    print(f"Video-IDs fuer Prompt A ({PROMPT_A}):")
    ids_a = video_ids_for_prompt(PROMPT_A)
    print(f"Video-IDs fuer Prompt B ({PROMPT_B}):")
    ids_b = video_ids_for_prompt(PROMPT_B)

    only_a = ids_a - ids_b
    only_b = ids_b - ids_a
    print(f"Nur bei {PROMPT_A}, nicht bei {PROMPT_B}: {len(only_a)}")
    print(f"Nur bei {PROMPT_B}, nicht bei {PROMPT_A}: {len(only_b)}")

    write_chunked_csv(only_a, f"video_ids_only_{PROMPT_A}_not_{PROMPT_B}")
    write_chunked_csv(only_b, f"video_ids_only_{PROMPT_B}_not_{PROMPT_A}")


if __name__ == "__main__":
    main()

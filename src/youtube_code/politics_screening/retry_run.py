"""
retry_run.py

Automatisiert den kompletten Retry-Flow für einen Run, der beim Download mit
status="validation_failed" hängen geblieben ist (z. B. wegen einer einzelnen
kaputten Gruppe wie dem item_10/item_010-Fall).

Was das Skript für dich erledigt:
  1. Liest den Original-Run aus der Registry (Modus wird automatisch aus
     target_variable abgeleitet: politics_title -> Title-Runde,
     politics_title_desc -> Description-Runde).
  2. Lädt die zugehörige {run_id}_retry.csv.
  3. Reichert sie bei Bedarf mit fehlenden Spalten aus dem aktuellen
     Screening-State an (Description-Modus braucht "description" und
     "politics_title", die im Manifest/Retry-File nie gespeichert werden).
  4. Submitted sie als eigenen kleinen Run über run_all_prompts().
  5. Pollt (falls WAIT_FOR_COMPLETION=True) bis der Vertex-AI-Job fertig ist.
  6. Lädt das Ergebnis über die bestehende process_run()-Logik aus
     download_results.py herunter und validiert es.
  7. Kombiniert Original- und Retry-Ergebnisse zu einer Datei und biegt den
     URSPRÜNGLICHEN run_id in der Registry auf diese kombinierte Datei um
     (status="downloaded") - damit update_screening_state.py danach ganz
     normal mit der ursprünglichen RUN_ID weiterarbeiten kann.

WICHTIG - bitte vor dem ersten scharfen Einsatz gegenchecken:
  - Die exakten Methodennamen von RunRegistry (get_run/get_runs/update_run)
    habe ich aus der Verwendung in deinen Skripten abgeleitet, nicht aus der
    Klassendefinition selbst (die lag mir nicht vor).
  - Falls get_run() bei unbekannter run_id nicht None sondern eine Exception
    wirft, greift der try/except unten trotzdem.
"""

from pathlib import Path
import time

import pandas as pd

from youtube_code.llm_analysis.submit_batch_jobs import (
    registry,
    client,
    run_all_prompts,
    MODEL_ALIASES,
)
from youtube_code.llm_analysis.download_results import process_run
from youtube_code.llm_analysis.prompts import prompts_title_classification
from youtube_code.politics_screening.screening_config import (
    BATCH_INPUT_DIR,
    DESCRIPTIONS_PER_REQUEST,
    GROUPING_SEED,
    MANIFEST_DIR,
    MAX_DESCRIPTION_CHARS,
    STATE_FILE,
    TITLES_PER_REQUEST,
)

REVERSE_MODEL_ALIASES = {value: key for key, value in MODEL_ALIASES.items()}

MODE_SETTINGS = {
    "politics_title": {
        "prompt_key": "PROMPT_32",
        "input_mode": "title",
        "items_per_request": TITLES_PER_REQUEST,
        "max_description_chars": None,
        "needs_enrichment": False,
    },
    "politics_title_desc": {
        "prompt_key": "PROMPT_33",
        "input_mode": "title_description",
        "items_per_request": DESCRIPTIONS_PER_REQUEST,
        "max_description_chars": MAX_DESCRIPTION_CHARS,
        "needs_enrichment": True,
    },
}


def get_job_state(job_id: str) -> str:
    status_job = client.batches.get(name=job_id)
    return (
        status_job.state.name
        if hasattr(status_job.state, "name")
        else str(status_job.state)
    )


def enrich_retry_file(retry_path: Path) -> None:
    """Join description + politics_title back in from the current state.

    Needed because the manifest (and therefore the retry file derived from
    it) never stores these columns, but input_mode="title_description"
    requires both.
    """
    state = pd.read_csv(
        STATE_FILE, dtype={"video_id": "string"}, low_memory=False
    )
    retry_df = pd.read_csv(
        retry_path, dtype={"video_id": "string"}, low_memory=False
    )

    # Idempotent machen: falls die Datei (z.B. aus einem früheren manuellen
    # Versuch) schon angereichert wurde, erst verwerfen und frisch aus dem
    # aktuellen State ziehen, statt an überlappenden Spalten zu scheitern.
    retry_df = retry_df.drop(
        columns=["description", "politics_title"], errors="ignore"
    )

    lookup = state.set_index("video_id")[["description", "politics_title"]]
    retry_df = retry_df.join(lookup, on="video_id")

    missing = retry_df["description"].isna().sum()
    if missing:
        raise ValueError(
            f"{missing} video_ids aus der Retry-Datei wurden nicht im "
            f"State gefunden ({STATE_FILE}). Breche ab, bevor etwas "
            "kaputtgeht."
        )

    retry_df.to_csv(retry_path, index=False, encoding="utf-8-sig")
    print(f"  Retry-Datei angereichert: {retry_path}")


def submit_retry(source_run_id: str) -> str:
    """Submits the retry CSV for source_run_id as a new run. Returns the new run_id."""
    run = registry.get_run(source_run_id)
    if run is None:
        raise ValueError(f"Run {source_run_id} nicht in der Registry gefunden.")
    if run["status"] != "validation_failed":
        raise ValueError(
            f"Run {source_run_id} hat status={run['status']!r}, "
            "erwartet wird 'validation_failed'. Dieses Skript ist nur für "
            "den Fall gedacht, dass ein Teil einer Gruppe abgelehnt wurde."
        )

    target_variable = run["target_variable"]
    if target_variable not in MODE_SETTINGS:
        raise ValueError(
            f"Unbekannte target_variable {target_variable!r}, kenne nur "
            f"{sorted(MODE_SETTINGS)}."
        )
    settings = MODE_SETTINGS[target_variable]

    results_path = Path(run["results_path"])
    retry_path = results_path.with_name(f"{results_path.stem}_retry.csv")
    if not retry_path.exists():
        raise FileNotFoundError(
            f"Erwartete Retry-Datei nicht gefunden: {retry_path}"
        )

    if settings["needs_enrichment"]:
        enrich_retry_file(retry_path)

    model_name = REVERSE_MODEL_ALIASES.get(run["model"])
    if model_name is None:
        raise ValueError(
            f"Konnte Model-Alias für {run['model']!r} nicht zurückauflösen."
        )

    print(f"\nSubmitting retry for {source_run_id} ({target_variable})...")
    result = run_all_prompts(
        csv_path=retry_path,
        prompt_keys=[settings["prompt_key"]],
        prompts={
            settings["prompt_key"]: prompts_title_classification[
                settings["prompt_key"]
            ]
        },
        dataset_id=f"{run['dataset_id']}_retry_of_{source_run_id}",
        dataset_version=run.get("dataset_version", "v1"),
        target_variable=target_variable,
        input_mode=settings["input_mode"],
        validation_basis=run.get("validation_basis", "screening_state"),
        model_name=model_name,
        thinking_budget=run.get("thinking_budget"),
        prompt_version=run.get("prompt_version", "v1"),
        items_per_request=settings["items_per_request"],
        grouping_seed=GROUPING_SEED,
        batch_input_dir=BATCH_INPUT_DIR,
        manifest_dir=MANIFEST_DIR,
        max_description_chars=(
            settings["max_description_chars"]
            if settings["max_description_chars"] is not None
            else 5_000
        ),
        # Default in submit_batch_jobs.py is "politics_title_model", aber
        # der Screening-State (und damit auch die angereicherte Retry-Datei)
        # nennt die Spalte "politics_title".
        previous_title_label_column="politics_title",
        dry_run=False,
    )

    retry_run_id = result[settings["prompt_key"]]["run_id"]
    if retry_run_id is None:
        raise RuntimeError(
            f"Submission ist fehlgeschlagen: {result[settings['prompt_key']]}"
        )
    print(f"Retry-Run submitted: {retry_run_id}")
    return retry_run_id


def wait_for_job(run_id: str, poll_interval_seconds: int = 300) -> None:
    run = registry.get_run(run_id)
    job_id = run["job_id"]
    while True:
        state = get_job_state(job_id)
        print(f"  [{run_id}] Status: {state}")
        if state == "JOB_STATE_SUCCEEDED":
            return
        if state in {"JOB_STATE_FAILED", "JOB_STATE_CANCELLED"}:
            raise RuntimeError(f"Retry-Job {run_id} ist fehlgeschlagen ({state}).")
        time.sleep(poll_interval_seconds)


def finalize_retry(source_run_id: str, retry_run_id: str) -> None:
    """Downloads the retry run and merges it back into source_run_id."""
    outcome = process_run(retry_run_id)
    if outcome != "downloaded":
        raise RuntimeError(
            f"Retry-Run {retry_run_id} endete mit status={outcome!r} statt "
            "'downloaded' - bitte manuell prüfen (evtl. wieder eine "
            "kaputte Gruppe, dann müsste man erneut retryen)."
        )

    original_run = registry.get_run(source_run_id)
    retry_run = registry.get_run(retry_run_id)

    original_results = pd.read_csv(
        original_run["results_path"], dtype={"video_id": "string"}, low_memory=False
    )
    retry_results = pd.read_csv(
        retry_run["results_path"], dtype={"video_id": "string"}, low_memory=False
    )
    combined = pd.concat([original_results, retry_results], ignore_index=True)

    duplicates = combined["video_id"].duplicated().sum()
    if duplicates:
        raise ValueError(
            f"{duplicates} doppelte video_ids nach dem Kombinieren - "
            "breche ab, bevor der Merge etwas verfälscht."
        )

    combined_path = Path(original_run["results_path"]).with_name(
        f"{source_run_id}_combined.csv"
    )
    combined.to_csv(combined_path, index=False, encoding="utf-8-sig")
    print(f"Kombinierte Ergebnisdatei gespeichert: {combined_path}")

    registry.update_run(
        source_run_id, status="downloaded", results_path=str(combined_path)
    )
    registry.update_run(retry_run_id, status=f"merged_into_{source_run_id}")
    print(
        f"Registry aktualisiert: {source_run_id} ist jetzt status='downloaded' "
        f"mit {len(combined):,} Zeilen. Kann jetzt normal mit "
        "update_screening_state.py gemergt werden."
    )


def retry_run(
    source_run_id: str,
    wait_for_completion: bool = True,
    poll_interval_seconds: int = 300,
) -> None:
    retry_run_id = submit_retry(source_run_id)

    if not wait_for_completion:
        print(
            f"\nWAIT_FOR_COMPLETION=False - Job {retry_run_id} läuft im "
            "Hintergrund weiter. Sobald er fertig ist, ruf auf:\n"
            f"  finalize_retry({source_run_id!r}, {retry_run_id!r})"
        )
        return

    print(f"\nWarte auf Fertigstellung von {retry_run_id} "
          f"(Poll-Intervall: {poll_interval_seconds}s)...")
    wait_for_job(retry_run_id, poll_interval_seconds=poll_interval_seconds)

    print(f"\nJob fertig, lade Ergebnisse herunter und merge...")
    finalize_retry(source_run_id, retry_run_id)


# ============================================================
# CONFIG - vor jedem Lauf anpassen
# ============================================================

# if __name__ == "__main__":
#     SOURCE_RUN_ID = "run_0006"        # der validation_failed-Run
#     WAIT_FOR_COMPLETION = True        # False = nur submitten, später finalize_retry() separat aufrufen
#     POLL_INTERVAL_SECONDS = 60       # alle 5 Minuten checken
#
#     retry_run(
#         source_run_id=SOURCE_RUN_ID,
#         wait_for_completion=WAIT_FOR_COMPLETION,
#         poll_interval_seconds=POLL_INTERVAL_SECONDS,
#     )

if __name__ == "__main__":
    finalize_retry(source_run_id="run_0006", retry_run_id="run_0007")
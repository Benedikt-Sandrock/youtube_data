"""
Submit one production title-screening round to Vertex AI.

This is intentionally separate from ``run_title_training_batch.py``:

- training/validation runs read a manually labelled sample;
- production runs read a file created by ``create_screening_round.py``.

Before creating a batch, this script verifies that the round file contains
exactly the videos reserved for that round in ``politics_screening_state.csv``
and that none of them already has a title label.
"""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from youtube_code.llm_analysis.prompts import (
    prompts_title_classification,
)
from youtube_code.llm_analysis.registry.run_registry import RunRegistry
from youtube_code.llm_analysis.submit_batch_jobs import (
    run_all_prompts,
)
from youtube_code.politics_screening.screening_config import (
    BATCH_INPUT_DIR,
    GROUPING_SEED,
    MANIFEST_DIR,
    REGISTRY_PATH,
    SCREENING_ROUND_DIR,
    STATE_FILE,
    TITLES_PER_REQUEST,
)


# ============================================================
# CONFIG
# ============================================================

ROUND_NUMBER = 1

PROMPT_KEY = "PROMPT_33"
PROMPT_VERSION = "v1"
MODEL_NAME = "gemini_25_flash"

# Keep this True until JSONL, manifest, counts, and sample titles have been
# checked. Then change only this setting to False for the real submission.
DRY_RUN = False

# False prevents accidental duplicate production jobs for the same dataset,
# prompt, and target variable. Set True only for a deliberate replacement or
# retry after inspecting the existing Registry runs.
ALLOW_EXISTING_RUN = False


TARGET_VARIABLE = "politics_title_desc"
INPUT_MODE = "title_desc"
VALIDATION_BASIS = "screening_state"


# ============================================================
# ROUND PATH AND VALIDATION
# ============================================================

def get_round_file(round_number: int) -> Path:
    if round_number < 1:
        raise ValueError("ROUND_NUMBER must be at least 1.")
    return (
        SCREENING_ROUND_DIR
        / f"screening_round_{round_number:03d}_title_candidates.csv"
    )


def normalize_ids(
    data: pd.DataFrame,
    source_name: str,
) -> pd.DataFrame:
    if "video_id" not in data.columns:
        raise ValueError(f"{source_name} has no video_id column.")

    normalized = data.copy()
    normalized["video_id"] = (
        normalized["video_id"].astype("string").str.strip()
    )

    invalid = (
        normalized["video_id"].isna()
        | normalized["video_id"].eq("")
    )
    if invalid.any():
        raise ValueError(
            f"{source_name} contains {int(invalid.sum()):,} invalid "
            "video IDs."
        )

    duplicated = normalized["video_id"].duplicated(keep=False)
    if duplicated.any():
        duplicate_ids = sorted(
            normalized.loc[duplicated, "video_id"].unique().tolist()
        )
        raise ValueError(
            f"{source_name} contains duplicate video IDs: "
            f"{duplicate_ids[:10]}"
        )

    return normalized


def load_and_validate_round(
    round_number: int,
) -> tuple[pd.DataFrame, object]:
    round_file = get_round_file(round_number)
    if not round_file.exists():
        raise FileNotFoundError(
            f"Screening round file not found: {round_file}"
        )
    if not STATE_FILE.exists():
        raise FileNotFoundError(
            f"Screening state not found: {STATE_FILE}"
        )

    round_data = normalize_ids(
        pd.read_csv(
            round_file,
            dtype={
                "video_id": "string",
                "channel_id": "string",
                "title": "string",
                "time_period": "string",
            },
            low_memory=False,
        ),
        "screening round file",
    )

    required_round_columns = {
        "video_id",
        "channel_id",
        "time_period",
        "title",
        "screening_round",
    }
    missing = required_round_columns - set(round_data.columns)
    if missing:
        raise ValueError(
            "Screening round file is missing columns: "
            f"{sorted(missing)}"
        )

    raw_round_numbers = round_data["screening_round"]
    numeric_round_numbers = pd.to_numeric(
        raw_round_numbers,
        errors="coerce",
    )
    invalid_round_numbers = (
        raw_round_numbers.notna()
        & numeric_round_numbers.isna()
    )
    if invalid_round_numbers.any() or numeric_round_numbers.isna().any():
        raise ValueError(
            "Round file contains missing or invalid screening_round values."
        )
    round_data["screening_round"] = numeric_round_numbers.astype(
        "Int16"
    )
    wrong_round = ~round_data["screening_round"].eq(round_number)
    if wrong_round.any():
        values = sorted(
            round_data.loc[
                wrong_round,
                "screening_round",
            ]
            .dropna()
            .unique()
            .tolist()
        )
        raise ValueError(
            f"Round file contains rows outside round {round_number}: "
            f"{values}"
        )

    round_data["title"] = (
        round_data["title"].astype("string").str.strip()
    )
    missing_titles = (
        round_data["title"].isna()
        | round_data["title"].eq("")
    )
    if missing_titles.any():
        raise ValueError(
            f"Round file contains {int(missing_titles.sum()):,} empty "
            "titles."
        )

    state = normalize_ids(
        pd.read_csv(
            STATE_FILE,
            dtype={"video_id": "string"},
            low_memory=False,
        ),
        "screening state",
    )
    required_state_columns = {
        "video_id",
        "screening_round",
        "politics_title",
    }
    missing = required_state_columns - set(state.columns)
    if missing:
        raise ValueError(
            f"Screening state is missing columns: {sorted(missing)}"
        )

    state["screening_round"] = pd.to_numeric(
        state["screening_round"],
        errors="coerce",
    ).astype("Int16")
    raw_title_labels = state["politics_title"]
    numeric_title_labels = pd.to_numeric(
        raw_title_labels,
        errors="coerce",
    )
    invalid_title_labels = (
        raw_title_labels.notna()
        & numeric_title_labels.isna()
    )
    if invalid_title_labels.any():
        values = sorted(
            raw_title_labels.loc[invalid_title_labels]
            .astype(str)
            .unique()
            .tolist()
        )
        raise ValueError(
            "Screening state contains invalid politics_title values: "
            f"{values[:10]}"
        )
    invalid_numeric_labels = (
        numeric_title_labels.notna()
        & ~numeric_title_labels.isin([-1, 0, 1])
    )
    if invalid_numeric_labels.any():
        values = sorted(
            numeric_title_labels.loc[
                invalid_numeric_labels
            ].unique().tolist()
        )
        raise ValueError(
            "Screening state contains politics_title labels outside "
            f"-1/0/1: {values}"
        )
    state["politics_title"] = numeric_title_labels.astype("Int8")

    state_round = state.loc[
        state["screening_round"].eq(round_number)
    ].copy()
    if state_round.empty:
        raise ValueError(
            f"No State rows are assigned to screening round {round_number}."
        )

    round_ids = set(round_data["video_id"])
    state_ids = set(state_round["video_id"])
    missing_in_round_file = sorted(state_ids - round_ids)
    unexpected_in_round_file = sorted(round_ids - state_ids)
    if missing_in_round_file or unexpected_in_round_file:
        raise ValueError(
            "Round file IDs do not exactly match the IDs reserved in the "
            f"State for round {round_number}. "
            f"Missing in round file: {len(missing_in_round_file):,} "
            f"{missing_in_round_file[:10]}; "
            f"unexpected in round file: {len(unexpected_in_round_file):,} "
            f"{unexpected_in_round_file[:10]}."
        )

    already_labelled = state_round["politics_title"].notna()
    if already_labelled.any():
        labelled_ids = (
            state_round.loc[already_labelled, "video_id"]
            .head(10)
            .tolist()
        )
        raise ValueError(
            f"{int(already_labelled.sum()):,} videos in round "
            f"{round_number} already have politics_title labels: "
            f"{labelled_ids}. Do not submit the same round again."
        )

    return round_data, round_file


def require_no_existing_run(
    registry_path,
    dataset_id: str,
    prompt_key: str,
    target_variable: str,
) -> None:
    if ALLOW_EXISTING_RUN:
        return

    registry = RunRegistry(registry_path)
    existing = registry.get_runs(
        dataset_id=dataset_id,
        prompt_id=prompt_key,
        target_variable=target_variable,
    )

    if existing.empty:
        return

    columns = [
        column
        for column in [
            "run_id",
            "status",
            "job_id",
            "created_at",
        ]
        if column in existing.columns
    ]
    raise ValueError(
        "A Registry run already exists for this production round. "
        "This may be an accidental duplicate submission:\n"
        f"{existing[columns].to_string(index=False)}\n"
        "Set ALLOW_EXISTING_RUN=True only for a deliberate retry."
    )


def print_preflight(
    round_data: pd.DataFrame,
    round_file,
    dataset_id: str,
) -> None:
    expected_requests = math.ceil(
        len(round_data) / TITLES_PER_REQUEST
    )

    print("\n" + "=" * 68)
    print(f"PRODUCTION TITLE SCREENING: ROUND {ROUND_NUMBER:03d}")
    print("=" * 68)
    print(f"Round file             : {round_file}")
    print(f"Dataset ID             : {dataset_id}")
    print(f"Videos                 : {len(round_data):,}")
    print(
        f"Channels               : "
        f"{round_data['channel_id'].nunique():,}"
    )
    print(f"Titles per request     : {TITLES_PER_REQUEST}")
    print(f"Expected requests      : {expected_requests:,}")
    print(f"Prompt                  : {PROMPT_KEY}")
    print(f"Model                   : {MODEL_NAME}")
    print(f"Dry run                 : {DRY_RUN}")

    print("\nVideos by period:")
    print(
        round_data["time_period"]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print("\nFirst round rows:")
    preview_columns = [
        "video_id",
        "channel_id",
        "time_period",
        "title",
    ]
    print(
        round_data[preview_columns]
        .head(10)
        .to_string(index=False)
    )
    print("=" * 68)


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    if PROMPT_KEY not in prompts_title_classification:
        raise KeyError(
            f"{PROMPT_KEY} is missing from "
            "prompts_title_classification."
        )

    round_data, round_file = load_and_validate_round(
        round_number=ROUND_NUMBER,
    )
    dataset_id = (
        f"politics_screening_round_{ROUND_NUMBER:03d}_title"
    )

    require_no_existing_run(
        registry_path=REGISTRY_PATH,
        dataset_id=dataset_id,
        prompt_key=PROMPT_KEY,
        target_variable=TARGET_VARIABLE,
    )
    print_preflight(
        round_data=round_data,
        round_file=round_file,
        dataset_id=dataset_id,
    )

    selected_prompts = {
        PROMPT_KEY: prompts_title_classification[PROMPT_KEY]
    }

    run_all_prompts(
        csv_path=round_file,
        prompt_keys=[PROMPT_KEY],
        prompts=selected_prompts,
        dataset_id=dataset_id,
        dataset_version="v1",
        target_variable=TARGET_VARIABLE,
        input_mode=INPUT_MODE,
        validation_basis=VALIDATION_BASIS,
        model_name=MODEL_NAME,
        thinking_budget=0,
        prompt_version=PROMPT_VERSION,
        items_per_request=TITLES_PER_REQUEST,
        grouping_seed=GROUPING_SEED,
        batch_input_dir=BATCH_INPUT_DIR,
        manifest_dir=MANIFEST_DIR,
        dry_run=DRY_RUN,
    )


if __name__ == "__main__":
    main()

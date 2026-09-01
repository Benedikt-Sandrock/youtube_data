"""
Submit transcript-classification jobs to Vertex AI.

This runner is separate from run_politics_screening_batch.py:

- politics screening decides which videos are relevant;
- transcript classification measures substantive variables such as populism
  or ideology for the selected videos.

Each transcript is sent as one independent model request.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from youtube_code.config import SAMPLES
from youtube_code.llm_analysis.prompts import prompts_populism_all
from youtube_code.llm_analysis.submit_batch_jobs import (
    run_all_prompts,
)
from youtube_code.step2_baseline_channels.screening_config import (
    BATCH_INPUT_DIR,
    GROUPING_SEED,
    MANIFEST_DIR,
)
from youtube_code.store.llm_run_store import get_runs


# ============================================================
# USER CONFIG
# ============================================================

# Replace this path with the file produced by your transcript download step.
# Required columns: video_id and transcript.
TRANSCRIPT_FILE = (
    SAMPLES
    / "russia"
    / "transcripts_for_classification.csv"
)

# Select the prompt collection imported above and one or more prompt keys.
PROMPT_COLLECTION = prompts_populism_all
PROMPT_KEYS = ["PROMPT_28"]

TARGET_VARIABLE = "populism_score"
VALIDATION_BASIS = "all_statements"

DATASET_VERSION = "v1"
PROMPT_VERSION = "v1"
MODEL_NAME = "gemini_25_flash"
THINKING_BUDGET = 0

# First inspect the generated JSONL. Change only this setting to False for
# the real submission.
DRY_RUN = True

# Prevent accidental duplicate submissions for the same dataset, prompt,
# target variable, and dataset version.
ALLOW_EXISTING_RUN = False


# ============================================================
# FIXED TRANSCRIPT SETTINGS
# ============================================================

INPUT_MODE = "transcript"
ITEMS_PER_REQUEST = 1
TRANSCRIPT_BATCH_INPUT_DIR = BATCH_INPUT_DIR / "transcripts"


# ============================================================
# VALIDATION
# ============================================================

def normalize_prompt_keys(
    prompt_keys: list[str] | str,
) -> list[str]:
    if isinstance(prompt_keys, str):
        normalized = [prompt_keys]
    else:
        normalized = list(prompt_keys)

    normalized = [
        str(prompt_key).strip()
        for prompt_key in normalized
        if str(prompt_key).strip()
    ]
    if not normalized:
        raise ValueError("At least one PROMPT_KEY must be specified.")
    if len(normalized) != len(set(normalized)):
        raise ValueError("PROMPT_KEYS contains duplicates.")

    missing = [
        prompt_key
        for prompt_key in normalized
        if prompt_key not in PROMPT_COLLECTION
    ]
    if missing:
        raise KeyError(
            f"Prompts missing from the selected collection: {missing}"
        )

    return normalized


def load_and_validate_transcripts(
    transcript_file: Path,
) -> pd.DataFrame:
    if not transcript_file.exists():
        raise FileNotFoundError(
            f"Transcript file not found: {transcript_file}"
        )

    data = pd.read_csv(
        transcript_file,
        dtype={"video_id": "string"},
        low_memory=False,
    )
    required_columns = {"video_id", "transcript"}
    missing = required_columns - set(data.columns)
    if missing:
        raise ValueError(
            f"Transcript file is missing columns: {sorted(missing)}"
        )
    if data.empty:
        raise ValueError("Transcript file contains no rows.")

    data["video_id"] = data["video_id"].astype("string").str.strip()
    invalid_ids = data["video_id"].isna() | data["video_id"].eq("")
    if invalid_ids.any():
        raise ValueError(
            f"Transcript file contains {int(invalid_ids.sum()):,} "
            "missing or empty video IDs."
        )

    duplicated = data["video_id"].duplicated(keep=False)
    if duplicated.any():
        duplicate_ids = sorted(
            data.loc[duplicated, "video_id"].unique().tolist()
        )
        raise ValueError(
            "Every video_id must occur exactly once. Duplicate IDs: "
            f"{duplicate_ids[:10]}"
        )

    cleaned_transcripts = (
        data["transcript"].astype("string").fillna("").str.strip()
    )
    empty_transcripts = cleaned_transcripts.eq("")
    if empty_transcripts.any():
        empty_ids = (
            data.loc[empty_transcripts, "video_id"].head(10).tolist()
        )
        raise ValueError(
            f"Transcript file contains {int(empty_transcripts.sum()):,} "
            f"empty transcripts: {empty_ids}"
        )

    return data


def require_no_existing_runs(
    dataset_id: str,
    prompt_keys: list[str],
) -> None:
    if ALLOW_EXISTING_RUN:
        return

    conflicts = []

    for prompt_key in prompt_keys:
        existing = get_runs(
            source="screening_active",
            dataset_id=dataset_id,
            target_variable=TARGET_VARIABLE,
        )
        if not existing.empty:
            existing = existing[
                (existing["dataset_version"] == DATASET_VERSION)
                & (existing["prompt_id"] == prompt_key)
            ]
        if not existing.empty:
            conflicts.append(existing)

    if not conflicts:
        return

    existing_runs = pd.concat(conflicts, ignore_index=True)
    columns = [
        column
        for column in [
            "run_id",
            "prompt_id",
            "status",
            "job_id",
            "created_at",
        ]
        if column in existing_runs.columns
    ]
    raise ValueError(
        "At least one matching Registry run already exists. This may be "
        "an accidental duplicate submission:\n"
        f"{existing_runs[columns].to_string(index=False)}\n"
        "Set ALLOW_EXISTING_RUN=True only for a deliberate retry."
    )


def print_preflight(
    data: pd.DataFrame,
    prompt_keys: list[str],
    dataset_id: str,
) -> None:
    transcript_lengths = (
        data["transcript"]
        .astype("string")
        .fillna("")
        .str.len()
    )

    print("\n" + "=" * 72)
    print("PRODUCTION TRANSCRIPT CLASSIFICATION")
    print("=" * 72)
    print(f"Input file              : {TRANSCRIPT_FILE}")
    print(f"Dataset ID              : {dataset_id}")
    print(f"Dataset version         : {DATASET_VERSION}")
    print(f"Videos / requests       : {len(data):,}")
    print(f"Prompts                 : {prompt_keys}")
    print(f"Target variable         : {TARGET_VARIABLE}")
    print(f"Validation basis        : {VALIDATION_BASIS}")
    print(f"Model                   : {MODEL_NAME}")
    print(f"Thinking budget         : {THINKING_BUDGET}")
    print(f"Dry run                 : {DRY_RUN}")
    print(
        f"Transcript length chars : "
        f"median={transcript_lengths.median():,.0f}, "
        f"mean={transcript_lengths.mean():,.0f}, "
        f"max={transcript_lengths.max():,}"
    )
    print("\nFirst input rows:")
    print(
        data[["video_id", "transcript"]]
        .assign(
            transcript=lambda frame: (
                frame["transcript"]
                .astype("string")
                .str.replace(r"\s+", " ", regex=True)
                .str.slice(0, 160)
            )
        )
        .head(5)
        .to_string(index=False)
    )
    print("=" * 72)


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    if not TARGET_VARIABLE.strip():
        raise ValueError("TARGET_VARIABLE must not be empty.")
    if TARGET_VARIABLE in {
        "politics_title",
        "politics_title_desc",
    }:
        raise ValueError(
            "Use run_politics_screening_batch.py for title and "
            "description screening."
        )

    prompt_keys = normalize_prompt_keys(PROMPT_KEYS)
    data = load_and_validate_transcripts(TRANSCRIPT_FILE)
    dataset_id = TRANSCRIPT_FILE.stem

    require_no_existing_runs(
        dataset_id=dataset_id,
        prompt_keys=prompt_keys,
    )
    print_preflight(
        data=data,
        prompt_keys=prompt_keys,
        dataset_id=dataset_id,
    )

    selected_prompts = {
        prompt_key: PROMPT_COLLECTION[prompt_key]
        for prompt_key in prompt_keys
    }

    run_all_prompts(
        csv_path=TRANSCRIPT_FILE,
        prompt_keys=prompt_keys,
        prompts=selected_prompts,
        dataset_id=dataset_id,
        dataset_version=DATASET_VERSION,
        target_variable=TARGET_VARIABLE,
        input_mode=INPUT_MODE,
        validation_basis=VALIDATION_BASIS,
        model_name=MODEL_NAME,
        thinking_budget=THINKING_BUDGET,
        prompt_version=PROMPT_VERSION,
        items_per_request=ITEMS_PER_REQUEST,
        grouping_seed=GROUPING_SEED,
        batch_input_dir=TRANSCRIPT_BATCH_INPUT_DIR,
        manifest_dir=MANIFEST_DIR,
        dry_run=DRY_RUN,
    )


if __name__ == "__main__":
    main()

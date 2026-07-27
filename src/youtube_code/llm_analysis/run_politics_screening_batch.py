"""
Submit one production politics-screening batch to Vertex AI.

Set ``MODE`` to:

- ``"title"``: submit the title candidates from create_screening_round.py
  to Prompt 32.
- ``"description"``: submit the title-uncertain cases produced by
  update_screening_state.py to Prompt 33.

All mode-specific settings are derived from ``MODE``. Before submission, the
candidate IDs and their current labels are checked against
politics_screening_state.csv.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
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
    DESCRIPTIONS_PER_REQUEST,
    GROUPING_SEED,
    MANIFEST_DIR,
    MAX_DESCRIPTION_CHARS,
    REGISTRY_PATH,
    SCREENING_ROUND_DIR,
    STATE_FILE,
    TITLES_PER_REQUEST,
)


# ============================================================
# USER CONFIG
# ============================================================

ROUND_NUMBER = 1

# "title" or "description"
MODE = "description"

# Keep True until the generated JSONL, manifest, counts, and sample inputs
# have been inspected. Then change only this setting to False.
DRY_RUN = False

# False prevents duplicate production runs for the same round and stage.
# Set True only for a deliberate retry after inspecting the existing run.
ALLOW_EXISTING_RUN = False


# ============================================================
# FIXED PRODUCTION CONFIG
# ============================================================

PROMPT_VERSION = "v1"
MODEL_NAME = "gemini_25_flash"
DATASET_VERSION = "v1"
VALIDATION_BASIS = "screening_state"
THINKING_BUDGET = 0


@dataclass(frozen=True)
class ModeSettings:
    prompt_key: str
    target_variable: str
    input_mode: str
    dataset_suffix: str
    items_per_request: int
    candidate_directory: Path
    candidate_filename_suffix: str
    required_candidate_columns: frozenset[str]
    previous_title_label_column: str | None = None
    max_description_chars: int | None = None


def get_mode_settings(mode: str) -> ModeSettings:
    normalized_mode = mode.strip().lower()

    settings = {
        "title": ModeSettings(
            prompt_key="PROMPT_32",
            target_variable="politics_title",
            input_mode="title",
            dataset_suffix="title",
            items_per_request=TITLES_PER_REQUEST,
            candidate_directory=SCREENING_ROUND_DIR,
            candidate_filename_suffix="title_candidates",
            required_candidate_columns=frozenset(
                {
                    "video_id",
                    "channel_id",
                    "time_period",
                    "title",
                    "screening_round",
                }
            ),
        ),
        "description": ModeSettings(
            prompt_key="PROMPT_33",
            target_variable="politics_title_desc",
            input_mode="title_description",
            dataset_suffix="description",
            items_per_request=DESCRIPTIONS_PER_REQUEST,
            candidate_directory=(
                SCREENING_ROUND_DIR.parent / "description_rounds"
            ),
            candidate_filename_suffix="description_candidates",
            required_candidate_columns=frozenset(
                {
                    "video_id",
                    "channel_id",
                    "time_period",
                    "title",
                    "description",
                    "politics_title",
                    "screening_round",
                }
            ),
            previous_title_label_column="politics_title",
            max_description_chars=MAX_DESCRIPTION_CHARS,
        ),
    }

    if normalized_mode not in settings:
        raise ValueError(
            f"Unknown MODE {mode!r}. Use 'title' or 'description'."
        )

    return settings[normalized_mode]


# ============================================================
# PATHS AND DATA VALIDATION
# ============================================================

def get_candidate_file(
    round_number: int,
    settings: ModeSettings,
) -> Path:
    if round_number < 1:
        raise ValueError("ROUND_NUMBER must be at least 1.")

    return (
        settings.candidate_directory
        / (
            f"screening_round_{round_number:03d}_"
            f"{settings.candidate_filename_suffix}.csv"
        )
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


def parse_label_column(
    data: pd.DataFrame,
    column: str,
    source_name: str,
) -> pd.Series:
    raw = data[column]
    numeric = pd.to_numeric(raw, errors="coerce")

    invalid_text = raw.notna() & numeric.isna()
    if invalid_text.any():
        values = sorted(
            raw.loc[invalid_text].astype(str).unique().tolist()
        )
        raise ValueError(
            f"{source_name} contains non-numeric {column} values: "
            f"{values[:10]}"
        )

    outside_domain = numeric.notna() & ~numeric.isin([-1, 0, 1])
    if outside_domain.any():
        values = sorted(
            numeric.loc[outside_domain].unique().tolist()
        )
        raise ValueError(
            f"{source_name} contains {column} values outside -1/0/1: "
            f"{values}"
        )

    return numeric.astype("Int8")


def load_candidate_file(
    path: Path,
    settings: ModeSettings,
) -> pd.DataFrame:
    if not path.exists():
        if settings.input_mode == "title":
            preparation = "Run create_screening_round.py first."
        else:
            preparation = (
                "First merge the title results with "
                "update_screening_state.py in title mode."
            )
        raise FileNotFoundError(
            f"Candidate file not found: {path}\n{preparation}"
        )

    candidates = normalize_ids(
        pd.read_csv(
            path,
            dtype={
                "video_id": "string",
                "channel_id": "string",
                "title": "string",
                "description": "string",
                "time_period": "string",
            },
            low_memory=False,
        ),
        "candidate file",
    )

    missing = (
        settings.required_candidate_columns - set(candidates.columns)
    )
    if missing:
        raise ValueError(
            f"Candidate file is missing columns: {sorted(missing)}"
        )
    if candidates.empty:
        raise ValueError("Candidate file contains no videos.")

    candidate_rounds = pd.to_numeric(
        candidates["screening_round"],
        errors="coerce",
    )
    if candidate_rounds.isna().any():
        raise ValueError(
            "Candidate file contains missing or invalid "
            "screening_round values."
        )
    candidates["screening_round"] = candidate_rounds.astype("Int16")

    wrong_round = ~candidates["screening_round"].eq(ROUND_NUMBER)
    if wrong_round.any():
        values = sorted(
            candidates.loc[wrong_round, "screening_round"]
            .unique()
            .tolist()
        )
        raise ValueError(
            f"Candidate file contains rows outside round "
            f"{ROUND_NUMBER}: {values}"
        )

    candidates["title"] = (
        candidates["title"].astype("string").str.strip()
    )
    missing_titles = (
        candidates["title"].isna()
        | candidates["title"].eq("")
    )
    if missing_titles.any():
        raise ValueError(
            f"Candidate file contains "
            f"{int(missing_titles.sum()):,} empty titles."
        )

    if settings.input_mode == "title_description":
        candidates["politics_title"] = parse_label_column(
            candidates,
            "politics_title",
            "candidate file",
        )
        not_uncertain = ~candidates["politics_title"].eq(-1)
        if not_uncertain.any():
            rows = (
                candidates.loc[
                    not_uncertain,
                    ["video_id", "politics_title"],
                ]
                .head(10)
                .to_dict("records")
            )
            raise ValueError(
                "Every description candidate must have "
                f"politics_title == -1. Invalid rows: {rows}"
            )

    return candidates


def load_state() -> pd.DataFrame:
    if not STATE_FILE.exists():
        raise FileNotFoundError(
            f"Screening state not found: {STATE_FILE}"
        )

    state = normalize_ids(
        pd.read_csv(
            STATE_FILE,
            dtype={"video_id": "string"},
            low_memory=False,
        ),
        "screening state",
    )

    required_columns = {
        "video_id",
        "screening_round",
        "politics_title",
        "politics_title_desc",
        "politics_final",
    }
    missing = required_columns - set(state.columns)
    if missing:
        raise ValueError(
            f"Screening state is missing columns: {sorted(missing)}"
        )

    raw_rounds = state["screening_round"]
    numeric_rounds = pd.to_numeric(raw_rounds, errors="coerce")
    invalid_rounds = raw_rounds.notna() & numeric_rounds.isna()
    if invalid_rounds.any():
        values = sorted(
            raw_rounds.loc[invalid_rounds]
            .astype(str)
            .unique()
            .tolist()
        )
        raise ValueError(
            "Screening state contains invalid screening_round values: "
            f"{values[:10]}"
        )
    state["screening_round"] = numeric_rounds.astype("Int16")

    for column in [
        "politics_title",
        "politics_title_desc",
        "politics_final",
    ]:
        state[column] = parse_label_column(
            state,
            column,
            "screening state",
        )

    return state


def get_expected_state_rows(
    state: pd.DataFrame,
    settings: ModeSettings,
) -> pd.DataFrame:
    round_mask = state["screening_round"].eq(ROUND_NUMBER)

    if settings.input_mode == "title":
        expected_mask = (
            round_mask
            & state["politics_title"].isna()
            & state["politics_title_desc"].isna()
            & state["politics_final"].isna()
        )
    else:
        expected_mask = (
            round_mask
            & state["politics_title"].eq(-1)
            & state["politics_title_desc"].isna()
            & state["politics_final"].isna()
        )

    expected = state.loc[expected_mask].copy()
    if expected.empty:
        raise ValueError(
            f"No unresolved {settings.dataset_suffix} cases exist in "
            f"State for round {ROUND_NUMBER}. The round may already have "
            "been processed."
        )

    return expected


def require_exact_id_match(
    candidates: pd.DataFrame,
    expected: pd.DataFrame,
    settings: ModeSettings,
) -> None:
    candidate_ids = set(candidates["video_id"])
    expected_ids = set(expected["video_id"])

    missing_candidates = sorted(expected_ids - candidate_ids)
    unexpected_candidates = sorted(candidate_ids - expected_ids)
    if missing_candidates or unexpected_candidates:
        raise ValueError(
            f"{settings.dataset_suffix.capitalize()} candidate IDs do not "
            f"exactly match the unresolved State rows for round "
            f"{ROUND_NUMBER}. "
            f"Missing in candidate file: {len(missing_candidates):,} "
            f"{missing_candidates[:10]}; "
            f"unexpected in candidate file: "
            f"{len(unexpected_candidates):,} "
            f"{unexpected_candidates[:10]}."
        )


def load_and_validate_inputs(
    settings: ModeSettings,
) -> tuple[pd.DataFrame, Path, int]:
    candidate_file = get_candidate_file(
        ROUND_NUMBER,
        settings,
    )
    candidates = load_candidate_file(candidate_file, settings)
    state = load_state()
    expected = get_expected_state_rows(state, settings)
    require_exact_id_match(candidates, expected, settings)

    empty_description_count = 0
    if settings.input_mode == "title_description":
        cleaned_descriptions = (
            candidates["description"]
            .astype("string")
            .fillna("")
            .str.strip()
        )
        empty_description_count = int(
            cleaned_descriptions.eq("").sum()
        )

    return candidates, candidate_file, empty_description_count


# ============================================================
# REGISTRY AND PREFLIGHT
# ============================================================

def require_no_existing_run(
    dataset_id: str,
    settings: ModeSettings,
) -> None:
    if ALLOW_EXISTING_RUN:
        return

    registry = RunRegistry(REGISTRY_PATH)
    existing = registry.get_runs(
        dataset_id=dataset_id,
        prompt_id=settings.prompt_key,
        target_variable=settings.target_variable,
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
        "A Registry run already exists for this production stage. "
        "This may be an accidental duplicate submission:\n"
        f"{existing[columns].to_string(index=False)}\n"
        "Set ALLOW_EXISTING_RUN=True only for a deliberate retry."
    )


def print_preflight(
    candidates: pd.DataFrame,
    candidate_file: Path,
    dataset_id: str,
    settings: ModeSettings,
    empty_description_count: int,
) -> None:
    expected_requests = math.ceil(
        len(candidates) / settings.items_per_request
    )

    print("\n" + "=" * 72)
    print(
        f"PRODUCTION POLITICS SCREENING: "
        f"{MODE.upper()} / ROUND {ROUND_NUMBER:03d}"
    )
    print("=" * 72)
    print(f"Candidate file          : {candidate_file}")
    print(f"Dataset ID              : {dataset_id}")
    print(f"Videos                  : {len(candidates):,}")
    print(
        f"Channels                : "
        f"{candidates['channel_id'].nunique():,}"
    )
    print(
        f"Items per request       : "
        f"{settings.items_per_request}"
    )
    print(f"Expected requests       : {expected_requests:,}")
    print(f"Prompt                  : {settings.prompt_key}")
    print(f"Input mode              : {settings.input_mode}")
    print(f"Target variable         : {settings.target_variable}")
    print(f"Model                   : {MODEL_NAME}")
    print(f"Dry run                 : {DRY_RUN}")

    if settings.input_mode == "title_description":
        print(
            f"Empty descriptions      : "
            f"{empty_description_count:,}"
        )
        print(
            f"Description character cap: "
            f"{settings.max_description_chars:,}"
        )
        print(
            f"Previous title column   : "
            f"{settings.previous_title_label_column}"
        )

    print("\nVideos by period:")
    print(
        candidates["time_period"]
        .value_counts()
        .sort_index()
        .to_string()
    )

    preview_columns = [
        "video_id",
        "channel_id",
        "time_period",
        "title",
    ]
    if settings.input_mode == "title_description":
        preview_columns.append("politics_title")

    print("\nFirst candidate rows:")
    print(
        candidates[preview_columns]
        .head(10)
        .to_string(index=False)
    )

    if empty_description_count:
        print(
            "\nWARNING: Videos with empty descriptions will still be sent "
            "with their title. Inspect these rows in the dry run."
        )
    print("=" * 72)


# ============================================================
# SUBMISSION
# ============================================================

def build_submission_kwargs(
    candidate_file: Path,
    dataset_id: str,
    settings: ModeSettings,
) -> dict:
    kwargs = {
        "csv_path": candidate_file,
        "prompt_keys": [settings.prompt_key],
        "prompts": {
            settings.prompt_key: prompts_title_classification[
                settings.prompt_key
            ]
        },
        "dataset_id": dataset_id,
        "dataset_version": DATASET_VERSION,
        "target_variable": settings.target_variable,
        "input_mode": settings.input_mode,
        "validation_basis": VALIDATION_BASIS,
        "model_name": MODEL_NAME,
        "thinking_budget": THINKING_BUDGET,
        "prompt_version": PROMPT_VERSION,
        "items_per_request": settings.items_per_request,
        "grouping_seed": GROUPING_SEED,
        "batch_input_dir": BATCH_INPUT_DIR,
        "manifest_dir": MANIFEST_DIR,
        "dry_run": DRY_RUN,
    }

    if settings.input_mode == "title_description":
        kwargs.update(
            {
                "max_description_chars": (
                    settings.max_description_chars
                ),
                "previous_title_label_column": (
                    settings.previous_title_label_column
                ),
            }
        )

    return kwargs


def main() -> None:
    settings = get_mode_settings(MODE)

    if settings.prompt_key not in prompts_title_classification:
        raise KeyError(
            f"{settings.prompt_key} is missing from "
            "prompts_title_classification."
        )

    candidates, candidate_file, empty_description_count = (
        load_and_validate_inputs(settings)
    )
    dataset_id = (
        f"politics_screening_round_{ROUND_NUMBER:03d}_"
        f"{settings.dataset_suffix}"
    )

    require_no_existing_run(
        dataset_id=dataset_id,
        settings=settings,
    )
    print_preflight(
        candidates=candidates,
        candidate_file=candidate_file,
        dataset_id=dataset_id,
        settings=settings,
        empty_description_count=empty_description_count,
    )

    run_all_prompts(
        **build_submission_kwargs(
            candidate_file=candidate_file,
            dataset_id=dataset_id,
            settings=settings,
        )
    )


if __name__ == "__main__":
    main()

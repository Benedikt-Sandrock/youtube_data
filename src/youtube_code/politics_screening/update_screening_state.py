"""
Merge validated Prompt-32 or Prompt-33 results into the screening state.

Modes
-----
title:
    Merge ``politics_title`` for one screening round. Direct labels 0/1 are
    copied to ``politics_final``. Label -1 remains unresolved and is written
    to a separate description-candidate CSV for Prompt 33.

description:
    Merge ``politics_title_desc`` for the title-deferred videos of one round
    and copy it to ``politics_final``. A second -1 is deliberately retained as
    ``politics_final = -1`` for later manual/transcript handling.

The script only accepts fully downloaded and validated Registry runs. Before
any write, it demands an exact ID match between the expected pending State
rows and the result file. Existing labels are never overwritten.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from youtube_code.llm_analysis.registry.run_registry import RunRegistry
from youtube_code.politics_screening.screening_config import (
    REGISTRY_PATH,
    SCREENING_ROUND_DIR,
    STATE_FILE,
)


# ============================================================
# CONFIG
# ============================================================

# "title" or "description"
MODE = "title"

# Screening round whose pending results are being merged.
ROUND_NUMBER = 1

# Registry run containing the completely validated result file.
RUN_ID = "run_0001"

# First inspect the complete merge plan with True. Set to False only after
# counts, labels, paths, and sample rows are plausible.
DRY_RUN = True

# Additional safeguard for a real write.
CONFIRM_BEFORE_WRITE = True


BATCH_DIR = SCREENING_ROUND_DIR.parent
DESCRIPTION_ROUND_DIR = BATCH_DIR / "description_rounds"
MERGE_REPORT_DIR = BATCH_DIR / "merge_reports"
STATE_BACKUP_DIR = BATCH_DIR / "state_backups"

VALID_MODES = {"title", "description"}
VALID_LABELS = {-1, 0, 1}

STATE_REQUIRED_COLUMNS = {
    "video_id",
    "channel_id",
    "time_period",
    "published_at",
    "title",
    "description",
    "screening_round",
    "politics_title",
    "politics_title_desc",
    "politics_final",
}

DESCRIPTION_OUTPUT_COLUMNS = [
    "screening_round",
    "video_id",
    "channel_id",
    "time_period",
    "published_at",
    "title",
    "description",
    "politics_title",
    "candidate_rank",
    "rank_within_period",
    "window_type",
]


# ============================================================
# GENERAL LOADING AND VALIDATION
# ============================================================

def read_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(
            path,
            dtype={"video_id": "string"},
            low_memory=False,
        )
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(
            path,
            dtype={"video_id": "string"},
        )
    raise ValueError(
        f"Unsupported file type for {path}. Use CSV or Excel."
    )


def normalize_video_ids(
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


def convert_label_column(
    data: pd.DataFrame,
    column: str,
    source_name: str,
    *,
    allow_missing: bool,
) -> pd.DataFrame:
    if column not in data.columns:
        raise ValueError(
            f"{source_name} is missing label column {column!r}."
        )

    converted = data.copy()
    raw = converted[column]
    numeric = pd.to_numeric(raw, errors="coerce")

    invalid_nonmissing = raw.notna() & numeric.isna()
    if invalid_nonmissing.any():
        invalid_values = sorted(
            raw.loc[invalid_nonmissing].astype(str).unique().tolist()
        )
        raise ValueError(
            f"{source_name}.{column} contains non-numeric labels: "
            f"{invalid_values[:10]}"
        )

    if not allow_missing and numeric.isna().any():
        raise ValueError(
            f"{source_name}.{column} contains "
            f"{int(numeric.isna().sum()):,} missing labels."
        )

    invalid_labels = numeric.notna() & ~numeric.isin(VALID_LABELS)
    if invalid_labels.any():
        invalid_values = sorted(
            numeric.loc[invalid_labels].unique().tolist()
        )
        raise ValueError(
            f"{source_name}.{column} contains invalid labels: "
            f"{invalid_values}. Expected only -1, 0, or 1."
        )

    converted[column] = numeric.astype("Int8")
    return converted


def load_state(state_path: Path) -> pd.DataFrame:
    state = normalize_video_ids(
        read_table(state_path),
        "screening state",
    )

    missing = STATE_REQUIRED_COLUMNS - set(state.columns)
    if missing:
        raise ValueError(
            "Screening state is missing columns: "
            f"{sorted(missing)}"
        )

    state["channel_id"] = (
        state["channel_id"].astype("string").str.strip()
    )
    invalid_channels = (
        state["channel_id"].isna()
        | state["channel_id"].eq("")
    )
    if invalid_channels.any():
        raise ValueError(
            f"Screening state contains "
            f"{int(invalid_channels.sum()):,} invalid channel IDs."
        )

    state["screening_round"] = pd.to_numeric(
        state["screening_round"],
        errors="coerce",
    ).astype("Int16")

    for column in [
        "politics_title",
        "politics_title_desc",
        "politics_final",
    ]:
        state = convert_label_column(
            state,
            column,
            "screening state",
            allow_missing=True,
        )

    validate_state_consistency(state)
    return state


def validate_state_consistency(state: pd.DataFrame) -> None:
    direct = state["politics_title"].isin([0, 1])
    inconsistent_direct = direct & (
        state["politics_final"].isna()
        | state["politics_final"].ne(state["politics_title"])
    )
    if inconsistent_direct.any():
        raise ValueError(
            f"{int(inconsistent_direct.sum()):,} direct title labels do "
            "not match politics_final."
        )

    description_present = state["politics_title_desc"].notna()
    invalid_description_source = (
        description_present
        & ~state["politics_title"].eq(-1).fillna(False)
    )
    if invalid_description_source.any():
        raise ValueError(
            f"{int(invalid_description_source.sum()):,} description labels "
            "exist although politics_title is not -1."
        )

    inconsistent_description = description_present & (
        state["politics_final"].isna()
        | state["politics_final"].ne(state["politics_title_desc"])
    )
    if inconsistent_description.any():
        raise ValueError(
            f"{int(inconsistent_description.sum()):,} description labels do "
            "not match politics_final."
        )

    deferred_final_without_description = (
        state["politics_title"].eq(-1)
        & state["politics_final"].notna()
        & state["politics_title_desc"].isna()
    )
    if deferred_final_without_description.any():
        raise ValueError(
            f"{int(deferred_final_without_description.sum()):,} deferred "
            "title labels have politics_final but no description label."
        )

    final_without_title = (
        state["politics_final"].notna()
        & state["politics_title"].isna()
    )
    if final_without_title.any():
        raise ValueError(
            f"{int(final_without_title.sum()):,} final labels exist without "
            "a title label."
        )


# ============================================================
# REGISTRY AND RESULT FILE
# ============================================================

def load_run_and_results(
    registry_path: Path,
    run_id: str,
    expected_target: str,
) -> tuple[dict, pd.DataFrame, Path]:
    registry = RunRegistry(registry_path)
    run = registry.get_run(run_id)
    metadata = (
        run.to_dict()
        if hasattr(run, "to_dict")
        else dict(run)
    )

    status = str(metadata.get("status", "")).strip()
    if status != "downloaded":
        raise ValueError(
            f"Run {run_id} has status {status!r}, not 'downloaded'. "
            "Only fully validated runs may update the screening state."
        )

    target_variable = str(
        metadata.get("target_variable", "")
    ).strip()
    if target_variable != expected_target:
        raise ValueError(
            f"Run {run_id} targets {target_variable!r}; "
            f"expected {expected_target!r} for this mode."
        )

    raw_results_path = metadata.get("results_path")
    if pd.isna(raw_results_path) or not str(raw_results_path).strip():
        raise ValueError(
            f"Run {run_id} has no results_path in the Registry."
        )

    results_path = Path(str(raw_results_path))
    results = normalize_video_ids(
        read_table(results_path),
        f"results for {run_id}",
    )

    candidates = [
        expected_target,
        f"{expected_target}_model",
    ]
    present = [column for column in candidates if column in results.columns]
    if len(present) != 1:
        raise ValueError(
            f"Results for {run_id} must contain exactly one of "
            f"{candidates}; found {present}."
        )

    source_label_column = present[0]
    results = convert_label_column(
        results,
        source_label_column,
        f"results for {run_id}",
        allow_missing=False,
    )
    results = results[
        ["video_id", source_label_column]
    ].rename(columns={source_label_column: expected_target})

    metadata["run_id"] = run_id
    return metadata, results, results_path


def require_exact_id_match(
    expected: pd.DataFrame,
    results: pd.DataFrame,
    context: str,
) -> None:
    expected_ids = set(expected["video_id"])
    result_ids = set(results["video_id"])
    missing = sorted(expected_ids - result_ids)
    unexpected = sorted(result_ids - expected_ids)

    if missing or unexpected:
        raise ValueError(
            f"Video IDs differ for {context}. "
            f"Expected: {len(expected_ids):,}; "
            f"results: {len(result_ids):,}; "
            f"missing: {len(missing):,} {missing[:10]}; "
            f"unexpected: {len(unexpected):,} {unexpected[:10]}."
        )


# ============================================================
# MERGE LOGIC
# ============================================================

def expected_title_rows(
    state: pd.DataFrame,
    round_number: int,
) -> pd.DataFrame:
    round_mask = state["screening_round"].eq(round_number)
    expected = state.loc[
        round_mask & state["politics_title"].isna()
    ].copy()

    if expected.empty:
        round_count = int(round_mask.sum())
        if round_count == 0:
            raise ValueError(
                f"No videos are assigned to screening round {round_number}."
            )
        raise ValueError(
            f"Round {round_number} has no pending title labels. It may "
            "already have been merged."
        )
    return expected


def expected_description_rows(
    state: pd.DataFrame,
    round_number: int,
) -> pd.DataFrame:
    round_mask = state["screening_round"].eq(round_number)
    expected = state.loc[
        round_mask
        & state["politics_title"].eq(-1)
        & state["politics_title_desc"].isna()
        & state["politics_final"].isna()
    ].copy()

    if expected.empty:
        unresolved_in_round = state.loc[
            round_mask
            & state["politics_title"].eq(-1)
            & state["politics_final"].isna()
        ]
        if unresolved_in_round.empty:
            raise ValueError(
                f"Round {round_number} has no pending description labels. "
                "There may have been no title-deferred videos, or the "
                "description results may already have been merged."
            )
        raise ValueError(
            "The pending description state is internally inconsistent."
        )
    return expected


def merge_title_results(
    state: pd.DataFrame,
    results: pd.DataFrame,
    round_number: int,
    run_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    expected = expected_title_rows(state, round_number)
    require_exact_id_match(
        expected=expected,
        results=results,
        context=f"title merge for round {round_number}",
    )

    result_map = results.set_index("video_id")["politics_title"]
    updated = state.copy()
    mask = (
        updated["screening_round"].eq(round_number)
        & updated["politics_title"].isna()
    )

    updated.loc[mask, "politics_title"] = (
        updated.loc[mask, "video_id"].map(result_map).astype("Int8")
    )

    direct = mask & updated["politics_title"].isin([0, 1])
    updated.loc[direct, "politics_final"] = updated.loc[
        direct,
        "politics_title",
    ]

    for column in [
        "politics_title",
        "politics_title_desc",
        "politics_final",
    ]:
        updated[column] = updated[column].astype("Int8")

    description_candidates = updated.loc[
        mask
        & updated["politics_title"].eq(-1)
        & updated["politics_final"].isna()
    ].copy()
    sort_columns = [
        column
        for column in [
            "channel_id",
            "time_period",
            "candidate_rank",
        ]
        if column in description_candidates.columns
    ]
    description_candidates = description_candidates.sort_values(
        sort_columns,
        na_position="last",
    )

    audit = expected[
        [
            "video_id",
            "channel_id",
            "time_period",
            "screening_round",
        ]
    ].copy()
    audit["run_id"] = run_id
    audit["merge_mode"] = "title"
    audit["old_politics_title"] = pd.NA
    audit["new_politics_title"] = audit["video_id"].map(result_map)
    audit["new_politics_final"] = audit["new_politics_title"].where(
        audit["new_politics_title"].isin([0, 1]),
        pd.NA,
    )
    audit["resolution_status"] = audit["new_politics_title"].map(
        {
            1: "political_direct",
            0: "nonpolitical_direct",
            -1: "awaiting_description",
        }
    )

    validate_state_consistency(updated)
    return updated, description_candidates, audit


def merge_description_results(
    state: pd.DataFrame,
    results: pd.DataFrame,
    round_number: int,
    run_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    expected = expected_description_rows(state, round_number)
    require_exact_id_match(
        expected=expected,
        results=results,
        context=f"description merge for round {round_number}",
    )

    result_map = results.set_index("video_id")[
        "politics_title_desc"
    ]
    updated = state.copy()
    mask = (
        updated["screening_round"].eq(round_number)
        & updated["politics_title"].eq(-1)
        & updated["politics_title_desc"].isna()
        & updated["politics_final"].isna()
    )

    updated.loc[mask, "politics_title_desc"] = (
        updated.loc[mask, "video_id"].map(result_map).astype("Int8")
    )
    updated.loc[mask, "politics_final"] = updated.loc[
        mask,
        "politics_title_desc",
    ]

    for column in [
        "politics_title",
        "politics_title_desc",
        "politics_final",
    ]:
        updated[column] = updated[column].astype("Int8")

    audit = expected[
        [
            "video_id",
            "channel_id",
            "time_period",
            "screening_round",
            "politics_title",
        ]
    ].copy()
    audit["run_id"] = run_id
    audit["merge_mode"] = "description"
    audit["old_politics_title_desc"] = pd.NA
    audit["new_politics_title_desc"] = audit["video_id"].map(result_map)
    audit["new_politics_final"] = audit["new_politics_title_desc"]
    audit["resolution_status"] = audit[
        "new_politics_title_desc"
    ].map(
        {
            1: "political_after_description",
            0: "nonpolitical_after_description",
            -1: "retained_uncertain",
        }
    )

    validate_state_consistency(updated)
    return updated, audit


# ============================================================
# OUTPUT AND REPORTING
# ============================================================

def atomic_write_csv(
    data: pd.DataFrame,
    output_path: Path,
    *,
    encoding: str = "utf-8-sig",
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(
        output_path.suffix + ".tmp"
    )
    data.to_csv(
        temporary_path,
        index=False,
        encoding=encoding,
        date_format="%Y-%m-%dT%H:%M:%SZ",
    )
    temporary_path.replace(output_path)


def build_output_paths(
    mode: str,
    round_number: int,
    run_id: str,
) -> dict[str, Path]:
    round_label = f"{round_number:03d}"
    paths = {
        "audit": MERGE_REPORT_DIR
        / f"screening_round_{round_label}_{mode}_{run_id}_merge.csv",
        "backup": STATE_BACKUP_DIR
        / f"politics_screening_state_before_{run_id}.csv",
    }
    if mode == "title":
        paths["description_candidates"] = (
            DESCRIPTION_ROUND_DIR
            / (
                f"screening_round_{round_label}_"
                "description_candidates.csv"
            )
        )
    return paths


def require_new_output_paths(
    paths: dict[str, Path],
    *,
    description_candidates_exist: bool,
) -> None:
    checked = ["audit", "backup"]
    if description_candidates_exist:
        checked.append("description_candidates")

    existing = [
        paths[key]
        for key in checked
        if paths[key].exists()
    ]
    if existing:
        raise FileExistsError(
            "The merge would overwrite existing audit/backup files: "
            f"{[str(path) for path in existing]}. "
            "This run may already have been applied."
        )


def print_merge_plan(
    mode: str,
    round_number: int,
    run_id: str,
    results_path: Path,
    audit: pd.DataFrame,
    paths: dict[str, Path],
    description_candidates: pd.DataFrame | None,
    dry_run: bool,
    state_path: Path,
) -> None:
    print("\n" + "=" * 68)
    print(f"SCREENING STATE MERGE: {mode.upper()}")
    print("=" * 68)
    print(f"Screening round       : {round_number}")
    print(f"Registry run          : {run_id}")
    print(f"Validated results     : {results_path}")
    print(f"Rows to merge         : {len(audit):,}")
    print(f"Dry run               : {dry_run}")

    print("\nResolution counts:")
    print(
        audit["resolution_status"]
        .value_counts(dropna=False)
        .to_string()
    )

    if description_candidates is not None:
        print(
            "\nDescription candidates : "
            f"{len(description_candidates):,}"
        )
        if not description_candidates.empty:
            print(
                "Description file       : "
                f"{paths['description_candidates']}"
            )

    print(f"Audit report           : {paths['audit']}")
    print(f"State backup           : {paths['backup']}")
    print(f"Updated state          : {state_path}")

    preview_columns = [
        column
        for column in [
            "video_id",
            "channel_id",
            "time_period",
            "new_politics_title",
            "new_politics_title_desc",
            "new_politics_final",
            "resolution_status",
        ]
        if column in audit.columns
    ]
    print("\nFirst merge rows:")
    print(audit[preview_columns].head(10).to_string(index=False))
    print("=" * 68)


def write_merge_outputs(
    original_state_path: Path,
    updated_state: pd.DataFrame,
    audit: pd.DataFrame,
    paths: dict[str, Path],
    description_candidates: pd.DataFrame | None,
) -> None:
    has_description_candidates = (
        description_candidates is not None
        and not description_candidates.empty
    )
    require_new_output_paths(
        paths,
        description_candidates_exist=has_description_candidates,
    )

    paths["backup"].parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original_state_path, paths["backup"])

    atomic_write_csv(audit, paths["audit"])

    if has_description_candidates:
        output_columns = [
            column
            for column in DESCRIPTION_OUTPUT_COLUMNS
            if column in description_candidates.columns
        ]
        atomic_write_csv(
            description_candidates[output_columns],
            paths["description_candidates"],
        )

    atomic_write_csv(
        updated_state,
        original_state_path,
        encoding="utf-8",
    )


# ============================================================
# MAIN
# ============================================================

def update_screening_state(
    mode: str,
    round_number: int,
    run_id: str,
    state_path: Path = STATE_FILE,
    registry_path: Path = REGISTRY_PATH,
    dry_run: bool = True,
    confirm_before_write: bool = True,
) -> dict:
    if mode not in VALID_MODES:
        raise ValueError(
            f"mode must be one of {sorted(VALID_MODES)}, got {mode!r}."
        )
    if round_number < 1:
        raise ValueError("round_number must be at least 1.")
    if not run_id or run_id == "run_0000":
        raise ValueError(
            "Set RUN_ID to the downloaded Registry run that should be "
            "merged."
        )

    target_variable = (
        "politics_title"
        if mode == "title"
        else "politics_title_desc"
    )

    state = load_state(state_path)
    metadata, results, results_path = load_run_and_results(
        registry_path=registry_path,
        run_id=run_id,
        expected_target=target_variable,
    )

    description_candidates = None
    if mode == "title":
        updated_state, description_candidates, audit = (
            merge_title_results(
                state=state,
                results=results,
                round_number=round_number,
                run_id=run_id,
            )
        )
    else:
        updated_state, audit = merge_description_results(
            state=state,
            results=results,
            round_number=round_number,
            run_id=run_id,
        )

    paths = build_output_paths(
        mode=mode,
        round_number=round_number,
        run_id=run_id,
    )
    print_merge_plan(
        mode=mode,
        round_number=round_number,
        run_id=run_id,
        results_path=results_path,
        audit=audit,
        paths=paths,
        description_candidates=description_candidates,
        dry_run=dry_run,
        state_path=state_path,
    )

    if dry_run:
        print("DRY RUN: no files or State values were changed.")
        return {
            "status": "dry_run",
            "metadata": metadata,
            "audit": audit,
            "description_candidates": description_candidates,
            "paths": paths,
        }

    if confirm_before_write:
        answer = input("Apply this merge to the screening state? [Y/n] ")
        if answer.strip().lower() != "y":
            print("Aborted. No files or State values were changed.")
            return {
                "status": "aborted",
                "metadata": metadata,
                "audit": audit,
                "description_candidates": description_candidates,
                "paths": paths,
            }

    write_merge_outputs(
        original_state_path=state_path,
        updated_state=updated_state,
        audit=audit,
        paths=paths,
        description_candidates=description_candidates,
    )

    print(f"Saved State backup      : {paths['backup']}")
    print(f"Saved merge audit       : {paths['audit']}")
    if (
        description_candidates is not None
        and not description_candidates.empty
    ):
        print(
            "Saved description input : "
            f"{paths['description_candidates']}"
        )
    print(f"Updated screening State : {state_path}")

    return {
        "status": "merged",
        "metadata": metadata,
        "audit": audit,
        "description_candidates": description_candidates,
        "paths": paths,
    }


def main() -> None:
    update_screening_state(
        mode=MODE,
        round_number=ROUND_NUMBER,
        run_id=RUN_ID,
        state_path=STATE_FILE,
        registry_path=REGISTRY_PATH,
        dry_run=DRY_RUN,
        confirm_before_write=CONFIRM_BEFORE_WRITE,
    )


if __name__ == "__main__":
    main()

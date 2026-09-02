"""
Create the next adaptive title-screening round.

The script reads ``politics_screening_state.csv`` and selects new, previously
unassigned title candidates separately for every channel and one-month period.
A channel-period is skipped when:

- 12 final political videos have already been found;
- title results from an earlier round are still pending;
- title-uncertain videos still await description classification; or
- no unused candidates remain.

The output CSV can be passed to the existing grouped title-batch pipeline.
Selected videos are reserved in the state through ``screening_round`` so they
cannot accidentally be submitted twice.
"""

import math
from pathlib import Path

import pandas as pd

from youtube_code.step2_baseline_channels.longitudinal.screening_config import (
    INITIAL_CANDIDATES_PER_PERIOD,
    MAX_CANDIDATES_PER_PERIOD_PER_ROUND,
    MIN_CANDIDATES_PER_PERIOD_PER_ROUND,
    POLITICAL_RATE_FLOOR,
    ROUND_SAFETY_FACTOR,
    SCREENING_ROUND_DIR,
    SCREENING_ROUND_SUMMARY_DIR,
    STATE_FILE,
    TARGET_WITH_BUFFER_PER_PERIOD,
    TITLES_PER_REQUEST,
)


# First inspect the printed plan with DRY_RUN=True. Change it to False only
# after the counts and the sample rows look plausible.
DRY_RUN = False


REQUIRED_COLUMNS = {
    "video_id",
    "channel_id",
    "published_at",
    "title",
    "time_period",
    "rank_within_period",
    "candidate_rank",
    "politics_title",
    "politics_final",
    "screening_round",
}

LABEL_COLUMNS = [
    "politics_title",
    "politics_title_desc",
    "politics_final",
]

ROUND_OUTPUT_COLUMNS = [
    "screening_round",
    "video_id",
    "channel_id",
    "time_period",
    "published_at",
    "title",
    "description",
    "candidate_rank",
    "rank_within_period",
    "window_type",
]


def load_screening_state(state_path: Path) -> pd.DataFrame:
    if not state_path.exists():
        raise FileNotFoundError(f"Screening state not found: {state_path}")

    state = pd.read_csv(
        state_path,
        dtype={
            "video_id": "string",
            "channel_id": "string",
            "title": "string",
            "description": "string",
            "time_period": "string",
            "window_type": "string",
        },
        low_memory=False,
    )

    missing = REQUIRED_COLUMNS - set(state.columns)
    if missing:
        raise ValueError(
            f"Screening state is missing columns: {sorted(missing)}"
        )

    state["video_id"] = state["video_id"].str.strip()
    state["channel_id"] = state["channel_id"].str.strip()
    state["title"] = state["title"].fillna("").str.strip()

    invalid_identity = (
        state["video_id"].isna()
        | state["video_id"].eq("")
        | state["channel_id"].isna()
        | state["channel_id"].eq("")
    )
    if invalid_identity.any():
        raise ValueError(
            f"{int(invalid_identity.sum()):,} rows have an invalid video_id "
            "or channel_id."
        )

    duplicate_ids = state.loc[
        state["video_id"].duplicated(keep=False),
        "video_id",
    ].unique()
    if len(duplicate_ids):
        raise ValueError(
            "Duplicate video IDs in screening state: "
            f"{sorted(duplicate_ids.tolist())[:10]}"
        )

    for column in LABEL_COLUMNS:
        if column in state.columns:
            state[column] = pd.to_numeric(
                state[column],
                errors="coerce",
            ).astype("Int8")

            invalid_labels = (
                state[column].notna()
                & ~state[column].isin([-1, 0, 1])
            )
            if invalid_labels.any():
                values = sorted(
                    state.loc[invalid_labels, column]
                    .dropna()
                    .unique()
                    .tolist()
                )
                raise ValueError(
                    f"Invalid labels in {column}: {values}"
                )

    state["screening_round"] = pd.to_numeric(
        state["screening_round"],
        errors="coerce",
    ).astype("Int16")

    for column in ["rank_within_period", "candidate_rank"]:
        state[column] = pd.to_numeric(
            state[column],
            errors="raise",
        ).astype("int32")

    direct_labels = state["politics_title"].isin([0, 1])
    inconsistent_direct = (
        direct_labels
        & (
            state["politics_final"].isna()
            | state["politics_final"].ne(state["politics_title"])
        )
    )
    if inconsistent_direct.any():
        raise ValueError(
            f"{int(inconsistent_direct.sum()):,} directly classified videos "
            "have a missing or inconsistent politics_final. Merge the title "
            "results into the state before creating another round."
        )

    unresolved_without_title = (
        state["politics_final"].notna()
        & state["politics_title"].isna()
    )
    if unresolved_without_title.any():
        raise ValueError(
            f"{int(unresolved_without_title.sum()):,} rows have "
            "politics_final but no politics_title."
        )

    return state


def get_next_round_number(state: pd.DataFrame) -> int:
    existing_rounds = state["screening_round"].dropna()
    if existing_rounds.empty:
        return 1
    return int(existing_rounds.max()) + 1


def calculate_candidate_count(
    political_found: int,
    final_classified: int,
    available_candidates: int,
    target_with_buffer: int,
    initial_candidates: int,
    minimum_candidates: int,
    maximum_candidates: int,
    political_rate_floor: float,
    safety_factor: float,
) -> int:
    """Calculate how many new titles should be screened in this period."""
    if available_candidates <= 0 or political_found >= target_with_buffer:
        return 0

    needed_political = target_with_buffer - political_found

    if final_classified == 0:
        requested = initial_candidates
    else:
        observed_rate = political_found / final_classified
        effective_rate = max(observed_rate, political_rate_floor)
        requested = math.ceil(
            needed_political / effective_rate * safety_factor
        )
        requested = max(requested, minimum_candidates)

    requested = min(requested, maximum_candidates)
    return min(requested, available_candidates)


def plan_screening_round(
    state: pd.DataFrame,
    round_number: int,
    target_with_buffer: int = TARGET_WITH_BUFFER_PER_PERIOD,
    initial_candidates: int = INITIAL_CANDIDATES_PER_PERIOD,
    minimum_candidates: int = MIN_CANDIDATES_PER_PERIOD_PER_ROUND,
    maximum_candidates: int = MAX_CANDIDATES_PER_PERIOD_PER_ROUND,
    political_rate_floor: float = POLITICAL_RATE_FLOOR,
    safety_factor: float = ROUND_SAFETY_FACTOR,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if target_with_buffer < 1:
        raise ValueError("target_with_buffer must be at least 1.")
    if not 0 < political_rate_floor <= 1:
        raise ValueError("political_rate_floor must lie in (0, 1].")
    if safety_factor < 1:
        raise ValueError("safety_factor must be at least 1.")

    selected_parts = []
    summary_rows = []

    grouped = state.groupby(
        ["channel_id", "time_period"],
        sort=True,
        observed=True,
    )

    for (channel_id, time_period), period in grouped:
        political_found = int(period["politics_final"].eq(1).sum())
        final_classified = int(period["politics_final"].notna().sum())
        pending_title = int(
            (
                period["screening_round"].notna()
                & period["politics_title"].isna()
            ).sum()
        )
        pending_description = int(
            (
                period["politics_title"].eq(-1)
                & period["politics_final"].isna()
            ).sum()
        )

        unused = period.loc[
            period["screening_round"].isna()
            & period["politics_title"].isna()
        ].copy()
        unused = unused.loc[unused["title"].fillna("").str.strip().ne("")]
        unused = unused.sort_values(
            ["rank_within_period", "candidate_rank", "published_at"],
            ascending=[True, True, True],
        )

        if political_found >= target_with_buffer:
            status = "target_reached"
            number_to_select = 0
        elif pending_title:
            status = "awaiting_title_results"
            number_to_select = 0
        elif pending_description:
            status = "awaiting_description_results"
            number_to_select = 0
        elif unused.empty:
            status = "candidate_pool_exhausted"
            number_to_select = 0
        else:
            status = "selected_for_next_round"
            number_to_select = calculate_candidate_count(
                political_found=political_found,
                final_classified=final_classified,
                available_candidates=len(unused),
                target_with_buffer=target_with_buffer,
                initial_candidates=initial_candidates,
                minimum_candidates=minimum_candidates,
                maximum_candidates=maximum_candidates,
                political_rate_floor=political_rate_floor,
                safety_factor=safety_factor,
            )

        if number_to_select:
            selected = unused.head(number_to_select).copy()
            selected["screening_round"] = round_number
            selected_parts.append(selected)

        summary_rows.append(
            {
                "screening_round": round_number,
                "channel_id": channel_id,
                "time_period": time_period,
                "status_before_round": status,
                "candidate_videos_total": len(period),
                "final_classified": final_classified,
                "political_found": political_found,
                "political_still_needed": max(
                    target_with_buffer - political_found,
                    0,
                ),
                "pending_title_results": pending_title,
                "pending_description_results": pending_description,
                "unused_candidates_before_round": len(unused),
                "selected_this_round": number_to_select,
                "target_with_buffer": target_with_buffer,
            }
        )

    if selected_parts:
        selected_round = pd.concat(
            selected_parts,
            ignore_index=True,
        )
        selected_round = selected_round.sort_values(
            [
                "channel_id",
                "time_period",
                "rank_within_period",
            ],
            ascending=[True, True, True],
        ).reset_index(drop=True)
    else:
        selected_round = state.head(0).copy()
        selected_round["screening_round"] = pd.Series(dtype="Int16")

    summary = pd.DataFrame(summary_rows)
    return selected_round, summary


def update_state_with_round(
    state: pd.DataFrame,
    selected_round: pd.DataFrame,
    round_number: int,
) -> pd.DataFrame:
    updated = state.copy()
    selected_ids = set(selected_round["video_id"].astype(str))

    if not selected_ids:
        return updated

    selected_mask = updated["video_id"].astype(str).isin(selected_ids)
    if int(selected_mask.sum()) != len(selected_ids):
        raise RuntimeError(
            "Not every selected video could be found in the screening state."
        )
    if updated.loc[selected_mask, "screening_round"].notna().any():
        raise RuntimeError(
            "At least one selected video was already assigned to a round."
        )

    updated.loc[selected_mask, "screening_round"] = round_number
    updated["screening_round"] = updated["screening_round"].astype("Int16")
    return updated


def atomic_write_csv(
    data: pd.DataFrame,
    output_path: Path,
    *,
    encoding: str = "utf-8-sig",
):
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


def print_round_plan(
    selected_round: pd.DataFrame,
    summary: pd.DataFrame,
    round_number: int,
):
    selected_count = len(selected_round)
    expected_requests = (
        math.ceil(selected_count / TITLES_PER_REQUEST)
        if selected_count
        else 0
    )

    print("\n" + "=" * 60)
    print(f"SCREENING ROUND {round_number:03d}")
    print("=" * 60)
    print(f"Channel-periods in state : {len(summary):,}")
    print(f"Selected title candidates: {selected_count:,}")
    print(f"Expected model requests   : {expected_requests:,}")
    print(
        "Selected channels        : "
        f"{selected_round['channel_id'].nunique():,}"
        if selected_count
        else "Selected channels        : 0"
    )

    print("\nChannel-period status:")
    print(
        summary["status_before_round"]
        .value_counts()
        .to_string()
    )

    if selected_count:
        print("\nSelected candidates by period:")
        print(
            selected_round["time_period"]
            .value_counts()
            .sort_index()
            .to_string()
        )

        print("\nFirst selected rows:")
        preview_columns = [
            "channel_id",
            "time_period",
            "video_id",
            "title",
        ]
        print(
            selected_round[preview_columns]
            .head(10)
            .to_string(index=False)
        )

    print("=" * 60)


def create_screening_round(
    state_path: Path = STATE_FILE,
    round_dir: Path = SCREENING_ROUND_DIR,
    summary_dir: Path = SCREENING_ROUND_SUMMARY_DIR,
    dry_run: bool = DRY_RUN,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    state = load_screening_state(state_path)
    round_number = get_next_round_number(state)

    selected_round, summary = plan_screening_round(
        state=state,
        round_number=round_number,
    )
    print_round_plan(
        selected_round=selected_round,
        summary=summary,
        round_number=round_number,
    )

    if selected_round.empty:
        print(
            "No new title candidates were selected. Check whether results "
            "or description classifications are still pending."
        )
        return selected_round, summary

    round_path = (
        round_dir
        / f"screening_round_{round_number:03d}_title_candidates.csv"
    )
    summary_path = (
        summary_dir
        / f"screening_round_{round_number:03d}_selection_summary.csv"
    )

    if dry_run:
        print("DRY RUN: no files or state values were changed.")
        print(f"Planned round file: {round_path}")
        print(f"Planned summary   : {summary_path}")
        return selected_round, summary

    if round_path.exists() or summary_path.exists():
        raise FileExistsError(
            "A file for the next round already exists. Resolve the existing "
            f"round before continuing: {round_path}"
        )

    output_columns = [
        column
        for column in ROUND_OUTPUT_COLUMNS
        if column in selected_round.columns
    ]
    atomic_write_csv(
        selected_round[output_columns],
        round_path,
    )
    atomic_write_csv(summary, summary_path)

    updated_state = update_state_with_round(
        state=state,
        selected_round=selected_round,
        round_number=round_number,
    )
    atomic_write_csv(
        updated_state,
        state_path,
        encoding="utf-8",
    )

    print(f"Saved round candidates: {round_path}")
    print(f"Saved round summary   : {summary_path}")
    print(f"Updated screening state: {state_path}")
    return selected_round, summary


if __name__ == "__main__":
    create_screening_round()

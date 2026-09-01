"""
Create the final video selection after politics screening.

For every channel and relative one-month period:

1. select political videos (politics_final == 1) first;
2. then select uncertain videos (politics_final == -1);
3. fill remaining slots with non-political videos (politics_final == 0);
4. mark the first TARGET_POLITICAL_PER_PERIOD videos as ``primary``;
5. retain additional videos up to TARGET_WITH_BUFFER_PER_PERIOD as
   ``reserve``.

Never-screened videos are not selected.
Within the same political class, selection is reproducibly randomized using
SELECTION_SEED and stable video identifiers.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from youtube_code.step2_baseline_channels.screening_config import (
    SCREENING_DIR,
    SELECTION_SEED,
    STATE_FILE,
    TARGET_POLITICAL_PER_PERIOD,
    TARGET_WITH_BUFFER_PER_PERIOD,
    WINDOW_MONTHS,
)


# ============================================================
# CONFIG
# ============================================================

DRY_RUN = False
CONFIRM_BEFORE_WRITE = True

# False protects an existing final selection from accidental replacement.
# Set True only when deliberately rebuilding it after a changed State or
# changed selection configuration.
OVERWRITE_EXISTING = False

OUTPUT_DIR = SCREENING_DIR / "final_selection"
ALL_SELECTED_FILE = OUTPUT_DIR / "final_video_selection_with_reserve.csv"
PRIMARY_FILE = OUTPUT_DIR / "final_video_selection_primary.csv"
SUMMARY_FILE = OUTPUT_DIR / "final_video_selection_by_channel_period.csv"
OVERVIEW_FILE = OUTPUT_DIR / "final_video_selection_overview.json"


VALID_LABELS = {-1, 0, 1}
REQUIRED_COLUMNS = {
    "video_id",
    "channel_id",
    "time_period",
    "published_at",
    "title",
    "politics_title",
    "politics_title_desc",
    "politics_final",
}


# ============================================================
# LOADING AND VALIDATION
# ============================================================

def parse_label_column(
    data: pd.DataFrame,
    column: str,
) -> pd.Series:
    raw = data[column]
    numeric = pd.to_numeric(raw, errors="coerce")

    invalid_text = raw.notna() & numeric.isna()
    if invalid_text.any():
        values = sorted(
            raw.loc[invalid_text].astype(str).unique().tolist()
        )
        raise ValueError(
            f"{column} contains non-numeric values: {values[:10]}"
        )

    invalid_labels = numeric.notna() & ~numeric.isin(VALID_LABELS)
    if invalid_labels.any():
        values = sorted(
            numeric.loc[invalid_labels].unique().tolist()
        )
        raise ValueError(
            f"{column} contains labels outside -1/0/1: {values}"
        )

    return numeric.astype("Int8")


def load_and_validate_state() -> pd.DataFrame:
    if not STATE_FILE.exists():
        raise FileNotFoundError(
            f"Screening State not found: {STATE_FILE}"
        )

    state = pd.read_csv(
        STATE_FILE,
        dtype={
            "video_id": "string",
            "channel_id": "string",
            "time_period": "string",
            "title": "string",
        },
        low_memory=False,
    )

    missing = REQUIRED_COLUMNS - set(state.columns)
    if missing:
        raise ValueError(
            f"Screening State is missing columns: {sorted(missing)}"
        )
    if state.empty:
        raise ValueError("Screening State contains no videos.")

    for column in ["video_id", "channel_id", "time_period"]:
        state[column] = state[column].astype("string").str.strip()
        invalid = state[column].isna() | state[column].eq("")
        if invalid.any():
            raise ValueError(
                f"Screening State contains {int(invalid.sum()):,} "
                f"missing or empty {column} values."
            )

    duplicated_ids = state["video_id"].duplicated(keep=False)
    if duplicated_ids.any():
        values = sorted(
            state.loc[duplicated_ids, "video_id"].unique().tolist()
        )
        raise ValueError(
            f"Screening State contains duplicate video IDs: {values[:10]}"
        )

    state["published_at"] = pd.to_datetime(
        state["published_at"],
        utc=True,
        errors="coerce",
    )
    if state["published_at"].isna().any():
        invalid_ids = (
            state.loc[
                state["published_at"].isna(),
                "video_id",
            ]
            .head(10)
            .tolist()
        )
        raise ValueError(
            "Screening State contains invalid publication dates for: "
            f"{invalid_ids}"
        )

    for column in [
        "politics_title",
        "politics_title_desc",
        "politics_final",
    ]:
        state[column] = parse_label_column(state, column)

    invalid_direct_final = (
        state["politics_title"].isin([0, 1])
        & (
            state["politics_final"].isna()
            | state["politics_final"].ne(
                state["politics_title"]
            ).fillna(True)
        )
    )
    if invalid_direct_final.any():
        ids = (
            state.loc[invalid_direct_final, "video_id"]
            .head(10)
            .tolist()
        )
        raise ValueError(
            "Direct title labels 0/1 do not match politics_final for: "
            f"{ids}"
        )

    description_present = state["politics_title_desc"].notna()
    invalid_description_source = (
        description_present
        & ~state["politics_title"].eq(-1).fillna(False)
    )
    if invalid_description_source.any():
        ids = (
            state.loc[invalid_description_source, "video_id"]
            .head(10)
            .tolist()
        )
        raise ValueError(
            "Description labels exist although politics_title is not -1 "
            f"for: {ids}"
        )

    invalid_description_final = (
        description_present
        & (
            state["politics_final"].isna()
            | state["politics_final"].ne(
                state["politics_title_desc"]
            ).fillna(True)
        )
    )
    if invalid_description_final.any():
        ids = (
            state.loc[invalid_description_final, "video_id"]
            .head(10)
            .tolist()
        )
        raise ValueError(
            "Description labels do not match politics_final for: "
            f"{ids}"
        )

    pending_descriptions = (
        state["politics_title"].eq(-1)
        & state["politics_title_desc"].isna()
        & state["politics_final"].isna()
    )
    if pending_descriptions.any():
        pending_by_period = (
            state.loc[pending_descriptions]
            .groupby(
                ["channel_id", "time_period"],
                observed=True,
            )
            .size()
            .sort_values(ascending=False)
        )
        raise ValueError(
            f"{int(pending_descriptions.sum()):,} title-uncertain videos "
            "are still waiting for description classification. Complete "
            "Prompt 33 before creating the final selection.\n"
            f"Largest pending channel-periods:\n"
            f"{pending_by_period.head(10).to_string()}"
        )

    labelled_without_final = (
        state["politics_title"].notna()
        & state["politics_final"].isna()
    )
    if labelled_without_final.any():
        ids = (
            state.loc[labelled_without_final, "video_id"]
            .head(10)
            .tolist()
        )
        raise ValueError(
            "Screened videos without a final label remain after the "
            f"description check: {ids}"
        )

    return state


def validate_configuration() -> None:
    if TARGET_POLITICAL_PER_PERIOD < 1:
        raise ValueError(
            "TARGET_POLITICAL_PER_PERIOD must be at least 1."
        )
    if TARGET_WITH_BUFFER_PER_PERIOD < TARGET_POLITICAL_PER_PERIOD:
        raise ValueError(
            "TARGET_WITH_BUFFER_PER_PERIOD must be at least as large as "
            "TARGET_POLITICAL_PER_PERIOD."
        )
    if WINDOW_MONTHS < 1:
        raise ValueError("WINDOW_MONTHS must be at least 1.")


# ============================================================
# REPRODUCIBLE SELECTION
# ============================================================

def stable_random_key(
    video_id: str,
    channel_id: str,
    time_period: str,
) -> str:
    """Create a deterministic pseudo-random ordering key."""
    value = (
        f"{SELECTION_SEED}|{channel_id}|"
        f"{time_period}|{video_id}"
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def select_videos(state: pd.DataFrame) -> pd.DataFrame:
    eligible = state.loc[
        state["politics_final"].isin([-1, 0, 1])
    ].copy()

    eligible["_selection_priority"] = eligible[
        "politics_final"
    ].map(
        {
            1: 0,
            -1: 1,
            0: 2,
        }
    ).astype("int8")

    eligible["selection_random_key"] = [
        stable_random_key(
            video_id=str(video_id),
            channel_id=str(channel_id),
            time_period=str(time_period),
        )
        for video_id, channel_id, time_period in zip(
            eligible["video_id"],
            eligible["channel_id"],
            eligible["time_period"],
        )
    ]

    # Political videos come first, followed by uncertain videos and finally
    # non-political fill-up videos.
    # The hash key randomizes reproducibly within each label.
    eligible = eligible.sort_values(
        [
            "channel_id",
            "time_period",
            "_selection_priority",
            "selection_random_key",
            "video_id",
        ],
        ascending=[True, True, True, True, True],
    )

    eligible["selection_rank"] = (
        eligible.groupby(
            ["channel_id", "time_period"],
            observed=True,
            sort=False,
        )
        .cumcount()
        .add(1)
        .astype("int16")
    )

    selected = eligible.loc[
        eligible["selection_rank"].le(
            TARGET_WITH_BUFFER_PER_PERIOD
        )
    ].copy()

    selected["selection_status"] = "reserve"
    primary = selected["selection_rank"].le(
        TARGET_POLITICAL_PER_PERIOD
    )
    selected.loc[primary, "selection_status"] = "primary"

    selected["selection_label_role"] = selected[
        "politics_final"
    ].map(
        {
            1: "political_priority",
            -1: "uncertain_priority",
            0: "nonpolitical_fill",
        }
    )
    selected["selection_reason"] = (
        selected["selection_status"]
        + "__"
        + selected["selection_label_role"]
    )

    selected["rank_within_selected_label"] = (
        selected.groupby(
            [
                "channel_id",
                "time_period",
                "politics_final",
            ],
            observed=True,
            sort=False,
        )
        .cumcount()
        .add(1)
        .astype("int16")
    )

    selected = selected.sort_values(
        ["channel_id", "time_period", "selection_rank"]
    ).drop(columns="_selection_priority").reset_index(drop=True)

    if selected["video_id"].duplicated().any():
        raise RuntimeError(
            "Internal error: final selection contains duplicate video IDs."
        )

    maximum_group_size = (
        selected.groupby(
            ["channel_id", "time_period"],
            observed=True,
        )
        .size()
        .max()
    )
    if (
        pd.notna(maximum_group_size)
        and maximum_group_size > TARGET_WITH_BUFFER_PER_PERIOD
    ):
        raise RuntimeError(
            "Internal error: a channel-period exceeds the buffer target."
        )

    return selected


# ============================================================
# SUMMARY AND CONTROLS
# ============================================================

def build_channel_period_grid(
    state: pd.DataFrame,
) -> pd.DataFrame:
    channels = sorted(state["channel_id"].unique().tolist())
    periods = [
        f"period_{period_number}"
        for period_number in range(1, WINDOW_MONTHS + 1)
    ]

    grid = pd.MultiIndex.from_product(
        [channels, periods],
        names=["channel_id", "time_period"],
    ).to_frame(index=False)

    channel_metadata_columns = [
        column
        for column in [
            "channel_title",
            "window_type",
            "window_start",
            "window_end",
            "channel_first_video",
        ]
        if column in state.columns
    ]
    if channel_metadata_columns:
        channel_metadata = (
            state[
                ["channel_id", *channel_metadata_columns]
            ]
            .drop_duplicates("channel_id")
        )
        grid = grid.merge(
            channel_metadata,
            on="channel_id",
            how="left",
            validate="many_to_one",
        )

    return grid


def grouped_count(
    data: pd.DataFrame,
    mask: pd.Series,
    output_name: str,
) -> pd.DataFrame:
    return (
        data.loc[mask]
        .groupby(
            ["channel_id", "time_period"],
            observed=True,
        )
        .size()
        .rename(output_name)
        .reset_index()
    )


def build_summary(
    state: pd.DataFrame,
    selected: pd.DataFrame,
) -> pd.DataFrame:
    summary = build_channel_period_grid(state)

    state_counts = [
        grouped_count(
            state,
            pd.Series(True, index=state.index),
            "candidate_videos",
        ),
        grouped_count(
            state,
            state["politics_final"].eq(1),
            "available_political",
        ),
        grouped_count(
            state,
            state["politics_final"].eq(0),
            "available_nonpolitical",
        ),
        grouped_count(
            state,
            state["politics_final"].eq(-1),
            "available_uncertain",
        ),
        grouped_count(
            state,
            state["politics_title"].isna(),
            "never_screened",
        ),
    ]

    primary = selected["selection_status"].eq("primary")
    reserve = selected["selection_status"].eq("reserve")
    selected_counts = [
        grouped_count(
            selected,
            primary,
            "primary_total",
        ),
        grouped_count(
            selected,
            primary & selected["politics_final"].eq(1),
            "primary_political",
        ),
        grouped_count(
            selected,
            primary & selected["politics_final"].eq(-1),
            "primary_uncertain",
        ),
        grouped_count(
            selected,
            primary & selected["politics_final"].eq(0),
            "primary_nonpolitical",
        ),
        grouped_count(
            selected,
            reserve,
            "reserve_total",
        ),
        grouped_count(
            selected,
            reserve & selected["politics_final"].eq(1),
            "reserve_political",
        ),
        grouped_count(
            selected,
            reserve & selected["politics_final"].eq(-1),
            "reserve_uncertain",
        ),
        grouped_count(
            selected,
            reserve & selected["politics_final"].eq(0),
            "reserve_nonpolitical",
        ),
    ]

    for counts in [*state_counts, *selected_counts]:
        summary = summary.merge(
            counts,
            on=["channel_id", "time_period"],
            how="left",
            validate="one_to_one",
        )

    count_columns = [
        "candidate_videos",
        "available_political",
        "available_nonpolitical",
        "available_uncertain",
        "never_screened",
        "primary_total",
        "primary_political",
        "primary_uncertain",
        "primary_nonpolitical",
        "reserve_total",
        "reserve_political",
        "reserve_uncertain",
        "reserve_nonpolitical",
    ]
    summary[count_columns] = (
        summary[count_columns].fillna(0).astype("int32")
    )

    summary["primary_shortfall"] = (
        TARGET_POLITICAL_PER_PERIOD - summary["primary_total"]
    ).clip(lower=0)
    summary["buffer_shortfall"] = (
        TARGET_WITH_BUFFER_PER_PERIOD
        - summary["primary_total"]
        - summary["reserve_total"]
    ).clip(lower=0)

    def describe_primary_fill(row: pd.Series) -> str:
        if row["primary_total"] == 0:
            return "no_eligible_classified_videos"

        components = []
        if row["primary_political"] > 0:
            components.append("politics")
        if row["primary_uncertain"] > 0:
            components.append("uncertain")
        if row["primary_nonpolitical"] > 0:
            components.append("nonpolitics")

        composition = "_and_".join(components)
        if row["primary_total"] < TARGET_POLITICAL_PER_PERIOD:
            return f"target_not_reached__{composition}"
        return composition

    summary["primary_fill_type"] = summary.apply(
        describe_primary_fill,
        axis=1,
    )

    summary["screening_coverage"] = (
        "all_candidate_videos_screened"
    )
    summary.loc[
        summary["never_screened"].gt(0),
        "screening_coverage",
    ] = "screening_stopped_after_target"
    summary.loc[
        summary["candidate_videos"].eq(0),
        "screening_coverage",
    ] = "no_candidate_video_in_period"

    period_numbers = pd.to_numeric(
        summary["time_period"].str.extract(r"(\d+)$")[0],
        errors="coerce",
    )
    summary["_period_number"] = period_numbers
    summary = (
        summary.sort_values(["channel_id", "_period_number"])
        .drop(columns="_period_number")
        .reset_index(drop=True)
    )

    return summary


def distribution(values: pd.Series) -> dict:
    if values.empty:
        return {
            "mean": None,
            "median": None,
            "percentile_25": None,
            "percentile_75": None,
            "min": None,
            "max": None,
        }
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return {
            "mean": None,
            "median": None,
            "percentile_25": None,
            "percentile_75": None,
            "min": None,
            "max": None,
        }
    return {
        "mean": float(numeric.mean()),
        "median": float(numeric.median()),
        "percentile_25": float(numeric.quantile(0.25)),
        "percentile_75": float(numeric.quantile(0.75)),
        "min": int(numeric.min()),
        "max": int(numeric.max()),
    }


def build_overview(
    state: pd.DataFrame,
    selected: pd.DataFrame,
    summary: pd.DataFrame,
) -> dict:
    primary = selected.loc[
        selected["selection_status"].eq("primary")
    ]
    reserve = selected.loc[
        selected["selection_status"].eq("reserve")
    ]

    all_channels = pd.Index(
        sorted(state["channel_id"].unique()),
        name="channel_id",
    )
    selected_per_channel = (
        selected.groupby("channel_id", observed=True)
        .size()
        .reindex(all_channels, fill_value=0)
    )
    primary_per_channel = (
        primary.groupby("channel_id", observed=True)
        .size()
        .reindex(all_channels, fill_value=0)
    )

    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_state": str(STATE_FILE),
        "configuration": {
            "primary_target_per_channel_period": (
                TARGET_POLITICAL_PER_PERIOD
            ),
            "target_with_buffer_per_channel_period": (
                TARGET_WITH_BUFFER_PER_PERIOD
            ),
            "reserve_slots_per_channel_period": (
                TARGET_WITH_BUFFER_PER_PERIOD
                - TARGET_POLITICAL_PER_PERIOD
            ),
            "window_months": WINDOW_MONTHS,
            "selection_seed": SELECTION_SEED,
            "political_priority_rule": (
                "politics_final=1 before politics_final=-1 "
                "before politics_final=0"
            ),
            "excluded_labels": [
                "politics_final missing",
            ],
        },
        "state": {
            "videos": int(len(state)),
            "channels": int(state["channel_id"].nunique()),
            "channel_periods_with_candidates": int(
                state[
                    ["channel_id", "time_period"]
                ].drop_duplicates().shape[0]
            ),
            "political_videos": int(
                state["politics_final"].eq(1).sum()
            ),
            "nonpolitical_videos": int(
                state["politics_final"].eq(0).sum()
            ),
            "uncertain_videos": int(
                state["politics_final"].eq(-1).sum()
            ),
            "never_screened_videos": int(
                state["politics_title"].isna().sum()
            ),
        },
        "selection": {
            "all_selected_videos": int(len(selected)),
            "primary_videos": int(len(primary)),
            "reserve_videos": int(len(reserve)),
            "primary_political": int(
                primary["politics_final"].eq(1).sum()
            ),
            "primary_uncertain": int(
                primary["politics_final"].eq(-1).sum()
            ),
            "primary_nonpolitical": int(
                primary["politics_final"].eq(0).sum()
            ),
            "reserve_political": int(
                reserve["politics_final"].eq(1).sum()
            ),
            "reserve_uncertain": int(
                reserve["politics_final"].eq(-1).sum()
            ),
            "reserve_nonpolitical": int(
                reserve["politics_final"].eq(0).sum()
            ),
            "primary_target_reached_channel_periods": int(
                summary["primary_shortfall"].eq(0).sum()
            ),
            "primary_target_not_reached_channel_periods": int(
                summary["primary_shortfall"].gt(0).sum()
            ),
            "fill_type_counts": {
                str(key): int(value)
                for key, value in (
                    summary["primary_fill_type"]
                    .value_counts()
                    .sort_index()
                    .items()
                )
            },
            "selected_videos_per_channel": distribution(
                selected_per_channel
            ),
            "primary_videos_per_channel": distribution(
                primary_per_channel
            ),
        },
    }


def validate_outputs(
    selected: pd.DataFrame,
    primary: pd.DataFrame,
    summary: pd.DataFrame,
) -> None:
    if not set(primary["video_id"]).issubset(
        set(selected["video_id"])
    ):
        raise RuntimeError(
            "Internal error: primary IDs are not a subset of all selected."
        )
    if len(primary) != selected["selection_status"].eq("primary").sum():
        raise RuntimeError(
            "Internal error: primary output count is inconsistent."
        )
    if summary.duplicated(["channel_id", "time_period"]).any():
        raise RuntimeError(
            "Internal error: duplicate channel-period summary rows."
        )
    if summary["primary_total"].gt(
        TARGET_POLITICAL_PER_PERIOD
    ).any():
        raise RuntimeError(
            "Internal error: primary target was exceeded."
        )
    if (
        summary["primary_total"] + summary["reserve_total"]
    ).gt(TARGET_WITH_BUFFER_PER_PERIOD).any():
        raise RuntimeError(
            "Internal error: buffer target was exceeded."
        )


# ============================================================
# OUTPUT
# ============================================================

def print_preflight(
    state: pd.DataFrame,
    selected: pd.DataFrame,
    summary: pd.DataFrame,
    overview: dict,
) -> None:
    selection = overview["selection"]

    print("\n" + "=" * 72)
    print("FINAL VIDEO SELECTION")
    print("=" * 72)
    print(f"State file                    : {STATE_FILE}")
    print(
        f"Channels in State             : "
        f"{state['channel_id'].nunique():,}"
    )
    print(
        f"Channel-periods in full grid  : "
        f"{len(summary):,}"
    )
    print(
        f"Primary target per period     : "
        f"{TARGET_POLITICAL_PER_PERIOD}"
    )
    print(
        f"Target including reserve      : "
        f"{TARGET_WITH_BUFFER_PER_PERIOD}"
    )
    print(f"Selection seed                : {SELECTION_SEED}")
    print(
        f"Selected primary videos       : "
        f"{selection['primary_videos']:,}"
    )
    print(
        f"Selected reserve videos       : "
        f"{selection['reserve_videos']:,}"
    )
    print(
        f"Primary political             : "
        f"{selection['primary_political']:,}"
    )
    print(
        f"Primary uncertain             : "
        f"{selection['primary_uncertain']:,}"
    )
    print(
        f"Primary non-political fill    : "
        f"{selection['primary_nonpolitical']:,}"
    )
    print(
        f"Periods reaching primary goal : "
        f"{selection['primary_target_reached_channel_periods']:,}"
    )
    print(
        f"Periods with primary shortfall: "
        f"{selection['primary_target_not_reached_channel_periods']:,}"
    )
    print(f"Dry run                       : {DRY_RUN}")

    print("\nPrimary fill types:")
    print(
        summary["primary_fill_type"]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print("\nScreening coverage:")
    print(
        summary["screening_coverage"]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print("\nFirst selected rows:")
    preview_columns = [
        "video_id",
        "channel_id",
        "time_period",
        "politics_final",
        "selection_rank",
        "selection_status",
        "selection_reason",
        "title",
    ]
    print(
        selected[preview_columns]
        .head(12)
        .to_string(index=False)
    )
    print("=" * 72)


def require_writable_outputs() -> None:
    existing = [
        path
        for path in [
            ALL_SELECTED_FILE,
            PRIMARY_FILE,
            SUMMARY_FILE,
            OVERVIEW_FILE,
        ]
        if path.exists()
    ]
    if existing and not OVERWRITE_EXISTING:
        paths = "\n".join(str(path) for path in existing)
        raise FileExistsError(
            "Final selection output already exists. Set "
            "OVERWRITE_EXISTING=True only for a deliberate rebuild:\n"
            f"{paths}"
        )


def write_outputs(
    selected: pd.DataFrame,
    primary: pd.DataFrame,
    summary: pd.DataFrame,
    overview: dict,
) -> None:
    require_writable_outputs()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    selected.to_csv(
        ALL_SELECTED_FILE,
        index=False,
        encoding="utf-8-sig",
        date_format="%Y-%m-%dT%H:%M:%SZ",
    )
    primary.to_csv(
        PRIMARY_FILE,
        index=False,
        encoding="utf-8-sig",
        date_format="%Y-%m-%dT%H:%M:%SZ",
    )
    summary.to_csv(
        SUMMARY_FILE,
        index=False,
        encoding="utf-8-sig",
    )
    with OVERVIEW_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            overview,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print("\nSaved final selection:")
    print(f"  All primary + reserve: {ALL_SELECTED_FILE}")
    print(f"  Primary only         : {PRIMARY_FILE}")
    print(f"  Channel-period report: {SUMMARY_FILE}")
    print(f"  Overview             : {OVERVIEW_FILE}")


def main() -> None:
    validate_configuration()
    state = load_and_validate_state()
    selected = select_videos(state)
    primary = selected.loc[
        selected["selection_status"].eq("primary")
    ].copy()
    summary = build_summary(state, selected)
    overview = build_overview(
        state=state,
        selected=selected,
        summary=summary,
    )
    validate_outputs(
        selected=selected,
        primary=primary,
        summary=summary,
    )
    print_preflight(
        state=state,
        selected=selected,
        summary=summary,
        overview=overview,
    )

    if DRY_RUN:
        print(
            "\nDRY RUN: no files were written. If the counts are "
            "plausible, set DRY_RUN=False."
        )
        return

    if CONFIRM_BEFORE_WRITE:
        answer = input("\nWrite final selection files? [y/N] ")
        if answer.strip().lower() != "y":
            print("Aborted.")
            return

    write_outputs(
        selected=selected,
        primary=primary,
        summary=summary,
        overview=overview,
    )


if __name__ == "__main__":
    main()

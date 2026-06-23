"""
Channel Activity Analysis
==========================

Analyzes how active YouTube channels were over time, broken down by
their political ideology and populism classification.

Inputs
------
1. An Excel file with one row per channel, containing at least:
   - a channel name column
   - a political ideology score (0-10)
   - a populism score (0-10)

2. A JSON file containing a list of video objects, each with at least:
   - the channel name (must match the Excel channel name EXACTLY,
     see MATCHING SETTINGS below)
   - a video title
   - a publish date

Outputs (written to OUTPUT_DIR)
--------------------------------
- activity_total_by_ideology_group.csv / .png
- activity_avg_by_ideology_group.csv  / .png
- activity_total_by_populism_group.csv / .png
- activity_avg_by_populism_group.csv  / .png
- unmatched_channels.csv (only if some video channel names could not be
  matched to a classified channel)

"total" = raw number of uploads per period and group.
"avg"   = uploads per period, divided by the TOTAL number of classified
          channels in that group (not just the active ones). This gives
          a fairer comparison when groups contain different numbers of
          channels.

Requirements: pandas, matplotlib, openpyxl
    pip install pandas matplotlib openpyxl --break-system-packages

Adjust the CONFIG section below to match your actual file paths and
column/field names, then run:
    python channel_activity_analysis.py
"""

import json
import os

import matplotlib.pyplot as plt
import pandas as pd

from youtube_code.config import OUTPUT_GEMINI, SAMPLES, ACTIVITY

# =============================================================================
# CONFIG
# =============================================================================

# --- File paths -------------------------------------------------------------
EXCEL_PATH = OUTPUT_GEMINI / "channel_results_051.xlsx"
JSON_PATH = SAMPLES / "conflict_over_time" / "keyword_videos_50k_channels.json"
OUTPUT_DIR = ACTIVITY

# --- Excel column names (channel classification file) -----------------------
EXCEL_CHANNEL_NAME_COLUMN = "channel_title"
EXCEL_IDEOLOGY_COLUMN = "ideology_channel_median"
EXCEL_POPULISM_COLUMN = "populism_channel_median"

# --- JSON field names (video file) ------------------------------------------
JSON_CHANNEL_NAME_FIELD = "channel_title"
JSON_TITLE_FIELD = "video_id"
JSON_DATE_FIELD = "published_at"

# --- Matching settings -------------------------------------------------------
# Channels are matched between the two files via an EXACT channel name match.
# These two flags control how "exact" that match is:
STRIP_WHITESPACE = True       # remove leading/trailing whitespace before matching
CASE_SENSITIVE_MATCH = True   # set to False to ignore upper/lower case differences

# --- Time range ---------------------------------------------------------------
START_DATE = "2023-07-07"
END_DATE = "2025-12-31"

# --- Time resolution ------------------------------------------------------------
# "D" = daily, "W" = weekly (weeks ending on Sunday; use "W-MON" etc. if you
# want a different week start). Switch freely between "D" and "W".
TIME_RESOLUTION = "W"

# --- Grouping thresholds (0-10 scale) ---------------------------------------
# Adjust the cut points and/or labels as needed. Bins are interpreted as
# (lower, upper] except for the lowest bin, which also includes the lower edge.
IDEOLOGY_BINS = [-0.01, 4.5, 5.5, 10.01]
IDEOLOGY_LABELS = ["Links", "Mitte", "Rechts"]

POPULISM_BINS = [-0.01, 3, 7, 10.01]
POPULISM_LABELS = ["Niedrig", "Mittel", "Hoch"]

# =============================================================================
# DATA LOADING
# =============================================================================


def _build_match_key(series: pd.Series) -> pd.Series:
    """Builds the key used for matching channel names between the two files,
    applying the configured whitespace/case-sensitivity rules."""
    key = series.astype(str)
    if STRIP_WHITESPACE:
        key = key.str.strip()
    if not CASE_SENSITIVE_MATCH:
        key = key.str.lower()
    return key


def add_group_columns(channels_df: pd.DataFrame) -> pd.DataFrame:
    """Adds categorical ideology/populism group columns based on the
    configured bins and labels."""
    channels_df["ideology_group"] = pd.cut(
        channels_df["ideology"],
        bins=IDEOLOGY_BINS,
        labels=IDEOLOGY_LABELS,
        include_lowest=True,
    )
    channels_df["populism_group"] = pd.cut(
        channels_df["populism"],
        bins=POPULISM_BINS,
        labels=POPULISM_LABELS,
        include_lowest=True,
    )
    return channels_df


def load_channels(path: str) -> pd.DataFrame:
    """Loads the channel classification Excel file and prepares it for
    merging with the video data."""
    df = pd.read_excel(path)

    required = [EXCEL_CHANNEL_NAME_COLUMN, EXCEL_IDEOLOGY_COLUMN, EXCEL_POPULISM_COLUMN]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing column(s) in Excel file: {missing}. "
            f"Available columns: {list(df.columns)}"
        )

    df = df.rename(
        columns={
            EXCEL_CHANNEL_NAME_COLUMN: "channel_name",
            EXCEL_IDEOLOGY_COLUMN: "ideology",
            EXCEL_POPULISM_COLUMN: "populism",
        }
    )

    df["channel_name"] = df["channel_name"].astype(str)
    if STRIP_WHITESPACE:
        df["channel_name"] = df["channel_name"].str.strip()
    df["channel_name_key"] = _build_match_key(df["channel_name"])

    # Drop channels with duplicate names (keep the first occurrence) since a
    # 1:1 mapping is required for the merge below.
    duplicated = df["channel_name_key"].duplicated(keep="first")
    if duplicated.any():
        dup_names = sorted(df.loc[duplicated, "channel_name"].unique().tolist())
        print(
            f"Warning: {len(dup_names)} duplicate channel name(s) found in the "
            f"Excel file, only the first occurrence is kept: {dup_names}"
        )
        df = df.loc[~duplicated].copy()

    df = add_group_columns(df)
    return df


def load_videos(path: str) -> pd.DataFrame:
    """Loads the video JSON file and prepares it for merging with the
    channel classification data."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    df = pd.DataFrame(raw)

    required = [JSON_CHANNEL_NAME_FIELD, JSON_TITLE_FIELD, JSON_DATE_FIELD]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing field(s) in JSON file: {missing}. "
            f"Available fields: {list(df.columns)}"
        )

    df = df.rename(
        columns={
            JSON_CHANNEL_NAME_FIELD: "channel_name",
            JSON_TITLE_FIELD: "title",
            JSON_DATE_FIELD: "publish_date",
        }
    )

    df["channel_name"] = df["channel_name"].astype(str)
    if STRIP_WHITESPACE:
        df["channel_name"] = df["channel_name"].str.strip()
    df["channel_name_key"] = _build_match_key(df["channel_name"])

    df["publish_date"] = pd.to_datetime(df["publish_date"], errors="coerce").dt.tz_localize(None)
    n_unparsed = int(df["publish_date"].isna().sum())
    if n_unparsed:
        print(
            f"Warning: {n_unparsed} video(s) had a publish date that could not "
            "be parsed and will be dropped."
        )
        df = df.dropna(subset=["publish_date"])

    return df


def merge_and_filter(videos_df: pd.DataFrame, channels_df: pd.DataFrame, start_date: str, end_date: str):
    """Filters videos to the analysis time window and merges them with the
    channel classification. Returns the merged DataFrame plus a list of
    channel names from the video data that could not be matched."""
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    in_range = videos_df[
        (videos_df["publish_date"] >= start) & (videos_df["publish_date"] <= end)
    ].copy()

    channel_lookup = channels_df[
        ["channel_name_key", "ideology", "populism", "ideology_group", "populism_group"]
    ]

    merged = in_range[["channel_name_key", "channel_name", "title", "publish_date"]].merge(
        channel_lookup, on="channel_name_key", how="inner"
    )

    unmatched_mask = ~in_range["channel_name_key"].isin(channels_df["channel_name_key"])
    unmatched_channels = sorted(in_range.loc[unmatched_mask, "channel_name"].unique().tolist())

    return merged, unmatched_channels


# =============================================================================
# AGGREGATION
# =============================================================================


def aggregate_activity(merged_df: pd.DataFrame, channels_df: pd.DataFrame, group_col: str,
    group_labels: list, resolution: str, start_date: str, end_date: str,):
    """Aggregates video counts per time period and group, plus the same
    counts divided by the total number of classified channels in each
    group (average uploads per channel)."""
    full_period_index = pd.date_range(start=start_date, end=end_date, freq=resolution)

    counts = (
        merged_df.groupby([pd.Grouper(key="publish_date", freq=resolution), group_col])
        .size()
        .rename("video_count")
        .reset_index()
    )

    pivot_total = counts.pivot(index="publish_date", columns=group_col, values="video_count")
    # pivot() leaves NaN for (period, group) combinations with zero videos -
    # these are genuine zeros, not missing data, so they must be filled in
    # before reindexing (reindex's fill_value only affects newly added
    # rows/columns, not existing NaN cells).
    pivot_total = pivot_total.fillna(0)
    pivot_total = pivot_total.reindex(index=full_period_index, fill_value=0)
    pivot_total = pivot_total.reindex(columns=group_labels, fill_value=0)
    pivot_total.index.name = "period_start"

    channels_per_group = channels_df.groupby(group_col)["channel_name"].nunique()
    channels_per_group = channels_per_group.reindex(group_labels)

    # Avoid division by zero for groups with no classified channels at all.
    pivot_avg = pivot_total.divide(channels_per_group.replace(0, pd.NA), axis=1)

    return pivot_total, pivot_avg, channels_per_group


def compute_relative_activity(pivot_avg: pd.DataFrame, event_date="2023-10-07"):
    """
    Converts average uploads per channel into relative activity.
    Baseline = mean activity before the event date.

    1.0 means normal activity.
    2.0 means double activity.
    """

    baseline = pivot_avg.loc[:pd.Timestamp(event_date) - pd.Timedelta(days=1)].mean()

    relative_activity = pivot_avg.divide(baseline)

    return relative_activity, baseline


# =============================================================================
# PLOTTING
# =============================================================================


def plot_activity(
    pivot_total: pd.DataFrame, pivot_avg: pd.DataFrame, group_col: str, label: str, output_dir: str
):
    """Creates and saves a two-panel plot (total uploads + average uploads
    per channel) for one grouping variable."""
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    pivot_total.plot(ax=axes[0], marker="o", markersize=3)
    axes[0].set_title(f"Total video uploads over time by {label} group")
    axes[0].set_ylabel("Number of videos")
    axes[0].legend(title=label)
    axes[0].grid(alpha=0.3)

    pivot_avg.plot(ax=axes[1], marker="o", markersize=3)
    axes[1].set_title(f"Average uploads per channel over time by {label} group")
    axes[1].set_ylabel("Avg. videos / channel")
    axes[1].set_xlabel("Date")
    axes[1].legend(title=label)
    axes[1].grid(alpha=0.3)

    fig.tight_layout()
    out_path = os.path.join(output_dir, f"activity_by_{group_col}.png")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved plot: {out_path}")


def plot_relative_activity(relative_activity: pd.DataFrame, label: str,
        output_dir: str, event_date="2023-10-07"):

    fig, ax = plt.subplots(figsize=(12,6))

    # optional smoothing
    smoothed = relative_activity.rolling(
        window=4,
        center=True,
        min_periods=1
    ).mean()

    smoothed.plot(ax=ax, linewidth=2)

    ax.axvline(
        pd.Timestamp(event_date),
        color="red",
        linestyle="--",
        linewidth=2,
        label="7 Oct 2023"
    )

    ax.axhline(
        1,
        color="black",
        linestyle=":",
        alpha=0.7
    )

    ax.set_ylabel("Relative activity")
    ax.set_xlabel("Date")

    ax.set_title(
        f"Relative channel activity by {label} group\n"
        "(baseline = average activity before 7 Oct 2023)"
    )

    ax.grid(alpha=0.3)
    ax.legend()

    fig.tight_layout()

    out_path = os.path.join(
        output_dir,
        f"relative_activity_{label}.png"
    )

    fig.savefig(out_path, dpi=300)
    plt.close(fig)

    print(f"Saved plot: {out_path}")


# =============================================================================
# MAIN
# =============================================================================


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Loading channels from '{EXCEL_PATH}' ...")
    channels_df = load_channels(EXCEL_PATH)
    print(f"  -> {len(channels_df)} classified channels loaded.")

    print(f"Loading videos from '{JSON_PATH}' ...")
    videos_df = load_videos(JSON_PATH)
    print(f"  -> {len(videos_df)} videos loaded (before date filtering).")

    merged_df, unmatched_channels = merge_and_filter(videos_df, channels_df, START_DATE, END_DATE)
    print(
        f"  -> {len(merged_df)} videos fall within [{START_DATE}, {END_DATE}] "
        "and matched a classified channel."
    )

    if unmatched_channels:
        print(
            f"Warning: {len(unmatched_channels)} channel name(s) from the video "
            "data did not match any channel in the Excel file (within the date "
            "range). These videos are excluded from the analysis."
        )
        pd.Series(unmatched_channels, name="unmatched_channel_name").to_csv(
            os.path.join(OUTPUT_DIR, "unmatched_channels.csv"), index=False
        )
        print(f"  -> Full list saved to {os.path.join(OUTPUT_DIR, 'unmatched_channels.csv')}")

    grouping_configs = [
        ("ideology_group", IDEOLOGY_LABELS, "Ideologie"),
        ("populism_group", POPULISM_LABELS, "Populismus"),
    ]

    for group_col, group_labels, label in grouping_configs:
        pivot_total, pivot_avg, channels_per_group = aggregate_activity(
            merged_df, channels_df, group_col, group_labels, TIME_RESOLUTION, START_DATE, END_DATE
        )

        print(f"\nChannels per {label} group: {channels_per_group.to_dict()}")

        total_path = os.path.join(OUTPUT_DIR, f"activity_total_by_{group_col}.csv")
        avg_path = os.path.join(OUTPUT_DIR, f"activity_avg_by_{group_col}.csv")
        pivot_total.to_csv(total_path)
        pivot_avg.to_csv(avg_path)
        print(f"Saved tables: {total_path}, {avg_path}")

        relative_activity, baseline = compute_relative_activity(
            pivot_avg,
            event_date="2023-10-07"
        )

        plot_relative_activity(
            relative_activity,
            label,
            OUTPUT_DIR,
            event_date="2023-10-07"
        )

        plot_activity(pivot_total, pivot_avg, group_col, label, OUTPUT_DIR)


    print(f"\nDone. All results were written to '{OUTPUT_DIR}'.")


if __name__ == "__main__":
    main()
"""
nahost_data_utils.py

Shared utilities for the YouTube channel analysis scripts:
    - success_trend_analysis.py    (relative view trends, weighting schemes, keyword success)
    - success_advanced_analysis.py (views decomposition, ITS regression, decay, format shift, engagement)

This module is imported, not run directly - it has no __main__ block and no analysis-specific
config (event date, plot ranges, etc. live in each analysis script's own config block).

Three groups of functions:
    1. DATA LOADING   - read raw metadata, merge channel classification, attach subscriber counts
    2. BASELINE TOOLS - normalize a time series to a baseline period ("baseline month(s) = 100%"),
                         optionally per-channel-weighted to avoid large channels dominating the picture
    3. PLOT HELPER    - Covers every "metric per month, one line per group" plot
                        used across both analysis scripts - baseline-relative trends, decay/format/
                        engagement plots, and the panels of multi-panel figures (via the `ax` parameter).
"""

import os
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from youtube_code.config import IDEOLOGY_LABELS, IDEOLOGY_BINS, IDEOLOGY_BINS_STRICT, POPULISM_BINS, POPULISM_LABELS
from youtube_code.utils import load_json


# ======================================================================
# 1. DATA LOADING
# ======================================================================

def prepare_metadata(metadata_input, metadata_output, channel_list_path, start_date, end_date):
    """
    Read raw video metadata (JSONL), keep only videos from channels in `channel_list_path`
    and within [start_date, end_date], parse dates/duration, and cache the result as CSV
    at `metadata_output` (so subsequent runs can skip this expensive step - see load_video_data).
    """
    print("Reading raw metadata...")
    channel_list = load_json(channel_list_path)
    df = pd.read_json(metadata_input, lines=True)

    print("Filtering by channel list and date range...")
    df = df[df["channel_id"].isin(channel_list)]
    df["published_at"] = pd.to_datetime(df["published_at"])
    df["month"] = df["published_at"].dt.to_period("M")
    df = df[(df["month"] >= start_date) & (df["month"] <= end_date)]
    df["duration"] = pd.to_timedelta(df["duration"])

    print(f"Videos remaining after filtering: {len(df)}")
    df.to_csv(metadata_output, index=False)
    return df


def load_classification(classification_path, media_path):
    """
    Load the channel-level ideology/populism scores and bucket them into categorical
    groups using the bin edges/labels defined in youtube_code.config.
    """
    class_df = pd.read_excel(classification_path)

    class_df["ideology_group"] = pd.cut(
        class_df["ideology_channel_mean"], bins=IDEOLOGY_BINS, labels=IDEOLOGY_LABELS, include_lowest=True
    )
    class_df["populism_group"] = pd.cut(
        class_df["populism_channel_mean"], bins=POPULISM_BINS, labels=POPULISM_LABELS, include_lowest=True
    )
    media_df = pd.read_excel(media_path)
    media_df = media_df[media_df["type"] != 4]
    class_df = pd.merge(class_df, media_df[["channel_title", "type"]], on = "channel_title", how = "left")
    return class_df


def add_subscriber_normalization(df, subscriber_source_path, subscriber_column):
    """
    Attach each video's channel subscriber count and compute views_per_subscriber.
    Channels missing a subscriber count are logged to 'missing.csv' rather than silently
    producing NaNs - check that file if views_per_subscriber looks incomplete.
    """
    sub_df = pd.read_excel(subscriber_source_path)
    df = df.merge(sub_df[["channel_title", subscriber_column]], on="channel_title", how="left")

    missing = df[df[subscriber_column].isna()]
    if not missing.empty:
        print(f"Warning: subscriber count missing for some channels - exported to 'missing.csv'.")
        missing.groupby("channel_title")[subscriber_column].first().reset_index().to_csv(
            "missing.csv", index=False
        )

    df["views_per_subscriber"] = df["view_count"] / df[subscriber_column]
    return df


def load_video_data(metadata_input, metadata_output, channel_list_path, classification_path, media_path,
                     start_date, end_date, include_shorts):
    """
    Full video-level data loading pipeline:
        1. Load video metadata (from cache if it exists, otherwise rebuild via prepare_metadata)
        2. Merge in channel-level ideology_group / populism_group classification

    Returns one row per video with (among others) the columns:
        channel_title, published_at, view_count, duration, title, ideology_group, populism_group
    """
    if os.path.exists(metadata_output):
        df = pd.read_csv(metadata_output)
        df["published_at"] = pd.to_datetime(df["published_at"])
    else:
        df = prepare_metadata(metadata_input, metadata_output, channel_list_path, start_date, end_date)

    df["duration"] = pd.to_timedelta(df["duration"])
    df["is_short"] = df["duration"] < pd.Timedelta("1 min")
    if not include_shorts:
        len_before = len(df)
        df = df[~df["is_short"]]
        len_after = len(df)
        removed_shorts = len_before - len_after
        print(f"Removed {removed_shorts} shorts.")

    class_df = load_classification(classification_path, media_path)
    df = pd.merge(df, class_df[["channel_title", "ideology_group", "populism_group", "type"]],
                  on="channel_title", how="left")
    df["published_at"] = pd.to_datetime(df["published_at"]).dt.tz_localize(None)
    return df


def aggregate_monthly(df, group_col, value_col, agg="sum", date_col="published_at"):
    """Aggregate value_col by calendar month and group_col (e.g. monthly view sum per group)."""
    return (
        df.groupby([pd.Grouper(key=date_col, freq="ME"), group_col])[value_col]
        .agg(agg)
        .reset_index()
    )


# ======================================================================
# 2. BASELINE TOOLS
# ======================================================================

def format_baseline_label(baseline_month, baseline_window_months=1):
    """Format the baseline period for plot legends, e.g. '2023-09' or '2023-07 to 2023-09'."""
    if baseline_window_months <= 1:
        return str(baseline_month)
    end_period = pd.Period(baseline_month, freq="M")
    start_period = end_period - (baseline_window_months - 1)
    return f"{start_period} to {end_period}"


def rebase_to_baseline(df_grouped, group_col, value_col, date_col, baseline_month,
                        baseline_window_months=1, baseline_mask=None):
    """
    Normalize value_col per group so the average over the baseline period = 100.

    baseline_window_months: number of months counted BACKWARDS from baseline_month
    (inclusive). 1 = only that month; 3 = that month plus the two before it. The window only
    ever extends backwards, so it can never bleed into the post-event period.

    baseline_mask: optional boolean mask on df_grouped restricting which ROWS are used to
    COMPUTE the baseline (e.g. only 'All videos' rows, not 'Keyword videos' rows). The
    resulting baseline is still applied to ALL rows of that group, including masked-out ones -
    this lets two series (e.g. a small keyword-video subset and the full population) share one
    stable baseline instead of the small subset getting its own unstable one.

    Groups with no data in the baseline period get NaN (not division-by-zero/inf).
    """
    df_grouped = df_grouped.copy()
    end_period = pd.Period(baseline_month, freq="M")
    start_period = end_period - (baseline_window_months - 1)

    months = df_grouped[date_col].dt.to_period("M")
    month_mask = (months >= start_period) & (months <= end_period)
    if baseline_mask is not None:
        month_mask = month_mask & baseline_mask

    baselines = df_grouped.loc[month_mask].groupby(group_col)[value_col].mean().astype(float)
    baselines = baselines.replace(0, pd.NA)  # avoid division by zero

    df_grouped[value_col] = df_grouped[value_col].astype(float)
    df_grouped["baseline"] = df_grouped[group_col].map(baselines)
    # Explicit re-cast: mapping a categorical group_col can return a categorical Series in some
    # pandas versions, which would break the division below - force it back to float.
    df_grouped["baseline"] = df_grouped["baseline"].astype(float)
    df_grouped["relative_pct"] = (df_grouped[value_col] / df_grouped["baseline"]) * 100
    return df_grouped


def weighted_relative_trend(df, group_col, baseline_month, baseline_window_single=1,
                             date_col="published_at", value_col="view_count", weight_power=0.0):
    """
    Compute a per-CHANNEL growth index (each channel rebased to its OWN baseline), then
    aggregate to a per-group index using a WEIGHTED average across channels. The weight of a
    channel is (its own baseline value) ** weight_power:

        weight_power = 0   -> every channel counts equally (pure equal-weighted index;
                               growth at small channels is no longer hidden inside a group sum)
        weight_power = 1   -> weight = baseline views directly. Mathematically (almost)
                               identical to the ratio of GROUP SUMS (= aggregate_monthly +
                               rebase_to_baseline at group level, the "value-weighted" view) -
                               pure size-weighting leads almost straight back to that.
        weight_power = 0.5 -> compromise (sqrt-weighting): big channels count for more than
                               small ones, but not in direct proportion to their size.

    Channels with no data in the baseline period get no baseline (NaN) and are excluded
    entirely, including from the weight sum - how many is printed.
    """
    channel_monthly = (
        df.groupby([pd.Grouper(key=date_col, freq="ME"), "channel_title", group_col])[value_col]
        .sum()
        .reset_index()
    )
    channel_monthly = rebase_to_baseline(channel_monthly, "channel_title", value_col, date_col,
                                          baseline_month, baseline_window_single)

    n_total = channel_monthly["channel_title"].nunique()
    valid = channel_monthly.dropna(subset=["relative_pct"]).copy()
    n_valid = valid["channel_title"].nunique()
    if n_valid < n_total:
        label = format_baseline_label(baseline_month, baseline_window_single)
        print(f"[weighted_relative_trend] power={weight_power}, {value_col}: "
              f"{n_total - n_valid} of {n_total} channels have no baseline data in {label} "
              f"and are excluded.")

    valid["weight"] = valid["baseline"] ** weight_power
    valid["weighted_value"] = valid["relative_pct"] * valid["weight"]

    agg = (
        valid.groupby([date_col, group_col])
        .agg(weighted_value_sum=("weighted_value", "sum"), weight_sum=("weight", "sum"))
        .reset_index()
    )
    agg["relative_pct"] = agg["weighted_value_sum"] / agg["weight_sum"]
    return agg[[date_col, group_col, "relative_pct"]]


def plot_group_trend(df_long, group_col, date_col, value_col, title, ylabel, plot_start,
                      event_date=None, reference_line=None, reference_label=None,
                      smooth=False, smooth_span=3, ax=None, show_legend=True):
    """
    Generic single-panel line plot of value_col over time, one line per group_col category.

    event_date        : if given, draws a vertical dotted line marking it (e.g. event day).
    reference_line     : if given (e.g. 100), draws a horizontal dashed reference line.
    reference_label    : legend label for that reference line.
    smooth              : if True, apply an exponentially-weighted moving average (span=smooth_span)
                          per group before plotting - useful for noisy monthly series.
    ax                  : pass an existing matplotlib Axes to draw into a multi-panel figure;
                          otherwise a new standalone figure is created and shown immediately.
    """
    standalone = ax is None
    plot_df = df_long[df_long[date_col] >= plot_start].copy()

    if smooth:
        plot_df[value_col] = (
            plot_df.groupby(group_col)[value_col]
            .transform(lambda x: x.ewm(span=smooth_span, adjust=False).mean())
        )

    if standalone:
        plt.figure(figsize=(14, 7))
        sns.set_theme(style="whitegrid")
        ax = plt.gca()

    sns.lineplot(data=plot_df, x=date_col, y=value_col, hue=group_col, marker="o",
                 linewidth=2, ax=ax, legend=show_legend)

    if reference_line is not None:
        ax.axhline(reference_line, color="red", linestyle="--", linewidth=1.5, label=reference_label)
    if event_date is not None:
        ax.axvline(pd.to_datetime(event_date), color="grey", linestyle=":", linewidth=1.5,
                   label="Event date")

    ax.set_title(title, fontsize=13 if standalone else 11)
    ax.set_xlabel("Month")
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=45)

    if standalone:
        if show_legend:
            ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
        plt.tight_layout()
        plt.show()
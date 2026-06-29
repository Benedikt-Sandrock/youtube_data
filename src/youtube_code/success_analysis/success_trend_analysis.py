"""
success_trend_analysis.py

Relative view-trend analysis of German YouTube channels around the 7 Oct 2023 event,
broken down by ideology group. Three complementary perspectives on "did this group's
videos do better after the event":

    STEP 1: Load data
    STEP 2: Group-level trend (raw views, and subscriber-normalized views)
            -> simple sum-per-group, so large channels dominate the picture
    STEP 3: Weighting-scheme comparison (equal- / sqrt- / value-weighted channel index)
            -> reveals whether growth is concentrated in a few large channels or
               broadly shared across small ones (see WEIGHT_POWER below)
    STEP 4: Keyword-specific success vs. the group's general baseline
            -> e.g. "how do videos mentioning Gaza/Israel/Hamas perform vs. a typical video"

Shared building blocks live in success_data_utils.py (data loading, baseline normalization)
and success_plot_utils.py (generic trend plotting) - both must be importable (same folder
or on PYTHONPATH) when running this script.
"""

import re

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

from youtube_code.config import RAW, CHANNEL_LISTS, SAMPLES, OUTPUT_GEMINI, KEYWORDS

from success_data_utils import (
    load_video_data, add_subscriber_normalization, aggregate_monthly,
    rebase_to_baseline, format_baseline_label, weighted_relative_trend, plot_group_trend
)


# ======================================================================
# CONFIG
# ======================================================================

# --- Event & baseline period ---
EVENT_DATE = "2023-10-07"
BASELINE_MONTH = "2023-09"        # last month of the baseline period
BASELINE_WINDOW_MONTHS = 1        # number of months counted backwards from BASELINE_MONTH (incl.)
BASELINE_WINDOW_SINGLE = 3        # number of months for channel-wise baseline calculation
PLOT_START_DATE = "2022-10-01"

# --- Data source paths ---
METADATA_INPUT = RAW / "video_metadata_total.jsonl"
METADATA_OUTPUT = SAMPLES / "combined" / "video_metadata_relevant.csv"
CHANNEL_LIST_PATH = CHANNEL_LISTS / "combined" / "channel_list.json"
CLASSIFICATION_PATH = OUTPUT_GEMINI / "channel_results_051.xlsx"
START_DATE = "2022-10"
END_DATE = "2025-12"

# --- Grouping column (switch to 'populism_group' to re-run everything by populism instead) ---
GROUP_COL = "ideology_group"

# --- Subscriber normalization (STEP 2's second plot, and STEP 4's keyword analysis) ---
SUBSCRIBER_COLUMN = "subscribers"
SUBSCRIBER_SOURCE_PATH = CLASSIFICATION_PATH

# --- STEP 3: weighting-scheme comparison ---
# WEIGHT_POWER is the "compromise" scheme: weight = channel_baseline_views ** WEIGHT_POWER.
# 0 = equal-weighted, 1 = value-weighted (~ the group-sum ratio from STEP 2). Try values
# between 0 and 1 to see how sensitive the result is to this choice.
WEIGHT_POWER = 0.5

# --- STEP 4: keyword analysis ---
# KEYWORDS is imported from youtube_code.config

# --- Plot smoothing (applied to all trend plots below) ---
# rolling window approach ist used with triangular method
SMOOTH_PLOTS = True
SMOOTH_SPAN = 3


# ======================================================================
# STEP 3 HELPERS: weighting-scheme comparison
# ======================================================================

def build_weighting_comparison(df, group_col, baseline_month, baseline_window_single,
                                weight_schemes, value_col="view_count"):
    """
    Run weighted_relative_trend() once per (weight_power, label) pair in `weight_schemes`
    and stack the results into one long DataFrame (with a 'weighting' column) for easy
    side-by-side plotting.
    """
    frames = []
    for power, label in weight_schemes:
        trend = weighted_relative_trend(df, group_col, baseline_month, baseline_window_single,
                                         value_col=value_col, weight_power=power)
        trend["weighting"] = label
        frames.append(trend)
    return pd.concat(frames, ignore_index=True)


def plot_weighting_comparison(df_combined, group_col, date_col, value_col, weighting_col,
                               plot_start, event_date, baseline_label,
                               smooth=False, smooth_span=3):
    """
    Faceted comparison of multiple weighting schemes: one subplot per group, with one line
    per weighting scheme inside each. Separate subplots (rather than one crowded plot) because
    N groups x M weighting schemes in a single panel quickly becomes unreadable.
    """
    plot_df = df_combined[df_combined[date_col] >= plot_start].copy()
    if smooth:
        plot_df[value_col] = (
            plot_df.groupby([group_col, weighting_col])[value_col]
            .transform(lambda x: x.rolling(window = smooth_span, center=True, win_type="triang").mean())
        )

    sns.set_theme(style="whitegrid")
    g = sns.relplot(
        data=plot_df, x=date_col, y=value_col, hue=weighting_col,
        col=group_col, kind="line", marker="o", linewidth=2,
        height=4, aspect=1.3, col_wrap=3, facet_kws={"sharey": False},
    )
    for ax in g.axes.flat:
        ax.axhline(100, color="red", linestyle="--", linewidth=1.2)
        ax.axvline(pd.to_datetime(event_date), color="grey", linestyle=":", linewidth=1.2)
        ax.tick_params(axis="x", rotation=45)

    g.set_titles("{col_name}")
    g.set_axis_labels("Month", f"relative to {baseline_label} (%)")
    g.fig.suptitle("Weighting-scheme comparison per group", y=1.02)
    plt.tight_layout()
    plt.show()


# ======================================================================
# STEP 4 HELPERS: keyword-specific success
# ======================================================================

def keyword_relative_success(df, keywords, group_col, baseline_month, baseline_window_months=1,
                              date_col="published_at", value_col="views_per_subscriber"):
    """
    Compare videos whose title contains at least one of `keywords` to ALL videos of the same
    group, both subscriber-normalized.

    Both series ('All videos' and the keyword series) are normalized to the SAME baseline -
    the one computed from 'All videos' in the baseline period. A keyword-only baseline would
    be unreliable, since almost no videos mention these keywords before the event. The
    resulting value reads as: "how does a keyword video compare to a TYPICAL video of this
    group in the reference period?" (100 = exactly as well as normal).
    """
    df = df.copy()
    pattern = "|".join(re.escape(kw) for kw in keywords)
    df["has_keyword"] = df["title"].str.contains(pattern, case=False, na=False, regex=True)

    print("Matches per keyword (a video can contain more than one keyword):")
    for kw in keywords:
        n = df["title"].str.contains(re.escape(kw), case=False, na=False, regex=True).sum()
        print(f"  '{kw}': {n}")

    if df["has_keyword"].sum() == 0:
        print(f"No videos match any of {keywords} in the title - skipping the keyword "
              "analysis (check spelling/regex, or pick different keywords).")
        return None

    end_period = pd.Period(baseline_month, freq="M")
    start_period = end_period - (baseline_window_months - 1)
    months = df[date_col].dt.to_period("M")
    baseline_label = format_baseline_label(baseline_month, baseline_window_months)
    n_keyword_before = df.loc[df["has_keyword"] & (months >= start_period) & (months <= end_period)].shape[0]
    print(f"Keyword videos in the baseline period ({baseline_label}): {n_keyword_before} "
          "-> hence normalizing to the 'All videos' baseline instead of a dedicated one.")

    def monthly_mean(sub_df, label):
        out = (
            sub_df.groupby([pd.Grouper(key=date_col, freq="ME"), group_col])[value_col]
            .mean()
            .reset_index()
        )
        out["series"] = label
        return out

    overall = monthly_mean(df, "All videos")
    keyword_label = "Videos with keyword (" + ", ".join(keywords) + ")"
    keyword_only = monthly_mean(df[df["has_keyword"]], keyword_label)

    combined = pd.concat([overall, keyword_only], ignore_index=True)
    combined["group_series"] = combined[group_col].astype(str) + " - " + combined["series"]

    # Compute the baseline only from the 'All videos' rows, then apply it to both series:
    combined = rebase_to_baseline(
        combined, group_col, value_col, date_col, baseline_month, baseline_window_months,
        baseline_mask=(combined["series"] == "All videos"),
    )
    return combined


def plot_keyword_focus_trend(df_grouped, group_col, series_col, focus_series, date_col, value_col,
                              title, ylabel, plot_start, event_date, baseline_label,
                              smooth=False, smooth_span=3):
    """
    Keyword-analysis plot: colour = group (same colour for a group's keyword line and its
    'All videos' line, so they're easy to pair up). The keyword series (focus_series) is drawn
    thick and solid (the actual focus); the 'All videos' series thin, dashed and semi-transparent
    in the background, for context.
    """
    plot_df = df_grouped[df_grouped[date_col] >= plot_start].copy()
    if smooth:
        plot_df[value_col] = (
            plot_df.groupby([group_col, series_col])[value_col]
            .transform(lambda x: x.rolling(window = smooth_span, center= True, win_type = "triang").mean())
        )

    groups = sorted(plot_df[group_col].astype(str).unique())
    palette = sns.color_palette("tab10", n_colors=len(groups))
    color_map = dict(zip(groups, palette))

    plt.figure(figsize=(14, 7))
    sns.set_theme(style="whitegrid")
    ax = plt.gca()

    for group in groups:
        color = color_map[group]
        group_df = plot_df[plot_df[group_col].astype(str) == group]
        background = group_df[group_df[series_col] != focus_series].sort_values(date_col)
        focus = group_df[group_df[series_col] == focus_series].sort_values(date_col)

        if not background.empty:
            ax.plot(background[date_col], background[value_col], color=color, linewidth=1.2,
                     linestyle="--", alpha=0.55, label=f"{group} - All videos")
        if not focus.empty:
            ax.plot(focus[date_col], focus[value_col], color=color, linewidth=2.8,
                     linestyle="-", marker="o", markersize=4, label=f"{group} - {focus_series}")

    ax.axhline(100, color="red", linestyle="--", linewidth=1.5, label=f"Baseline ({baseline_label} = 100%)")
    ax.axvline(pd.to_datetime(event_date), color="grey", linestyle=":", linewidth=1.5, label="Event date")

    ax.set_title(title, fontsize=14)
    ax.set_xlabel("Month")
    ax.set_ylabel(ylabel)
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=9)
    ax.tick_params(axis="x", rotation=45)
    plt.tight_layout()
    plt.show()


# ======================================================================
# MAIN
# ======================================================================

def main():
    baseline_label = format_baseline_label(BASELINE_MONTH, BASELINE_WINDOW_MONTHS)

    # ---- STEP 1: Load data ----
    # Adjust paths/dates above if the data location or time window changes.
    df = load_video_data(METADATA_INPUT, METADATA_OUTPUT, CHANNEL_LIST_PATH, CLASSIFICATION_PATH,
                          START_DATE, END_DATE)
    df = add_subscriber_normalization(df, SUBSCRIBER_SOURCE_PATH, SUBSCRIBER_COLUMN)

    # ---- STEP 2: Group-level trend (large channels dominate the group sum here) ----
    views_monthly = aggregate_monthly(df, GROUP_COL, "view_count", agg="sum")
    views_rebased = rebase_to_baseline(views_monthly, GROUP_COL, "view_count", "published_at",
                                        BASELINE_MONTH, BASELINE_WINDOW_MONTHS)
    plot_group_trend(
        views_rebased, GROUP_COL, "published_at", "relative_pct",
        title="Monthly total views relative to baseline, by group (value-weighted)",
        ylabel=f"views relative to {baseline_label} (%)",
        plot_start=PLOT_START_DATE, event_date=EVENT_DATE,
        reference_line=100, reference_label=f"Baseline ({baseline_label} = 100%)",
        smooth=SMOOTH_PLOTS, smooth_span=SMOOTH_SPAN,
    )

    subnorm_monthly = aggregate_monthly(df, GROUP_COL, "views_per_subscriber", agg="sum")
    subnorm_rebased = rebase_to_baseline(subnorm_monthly, GROUP_COL, "views_per_subscriber",
                                          "published_at", BASELINE_MONTH, BASELINE_WINDOW_MONTHS)
    plot_group_trend(
        subnorm_rebased, GROUP_COL, "published_at", "relative_pct",
        title="Monthly subscriber-normalized views relative to baseline, by group",
        ylabel=f"views/subscriber relative to {baseline_label} (%)",
        plot_start=PLOT_START_DATE, event_date=EVENT_DATE,
        reference_line=100, reference_label=f"Baseline ({baseline_label} = 100%)",
        smooth=SMOOTH_PLOTS, smooth_span=SMOOTH_SPAN,
    )

    # ---- STEP 3: Weighting-scheme comparison (equal- / sqrt- / value-weighted) ----
    # Adjust WEIGHT_POWER above to change the "compromise" scheme.
    weight_schemes = [
        (0.0, "Equal-weighted"),
        (WEIGHT_POWER, f"Sqrt-weighted (power={WEIGHT_POWER})"),
        (1.0, "Value-weighted"),
    ]
    comparison_df = build_weighting_comparison(df, GROUP_COL, BASELINE_MONTH, BASELINE_WINDOW_SINGLE,
                                                weight_schemes, value_col="view_count")
    plot_weighting_comparison(
        comparison_df, GROUP_COL, "published_at", "relative_pct", "weighting",
        plot_start=PLOT_START_DATE, event_date=EVENT_DATE, baseline_label=baseline_label,
        smooth=SMOOTH_PLOTS, smooth_span=SMOOTH_SPAN,
    )

    # ---- STEP 4: Keyword-specific success vs. group baseline ----
    # Adjust KEYWORDS above to analyze a different set of keywords.
    keyword_df = keyword_relative_success(df, KEYWORDS, GROUP_COL, BASELINE_MONTH, BASELINE_WINDOW_MONTHS)
    if keyword_df is not None:
        focus_series = next(s for s in keyword_df["series"].unique() if s != "All videos")
        plot_keyword_focus_trend(
            keyword_df, GROUP_COL, "series", focus_series, "published_at", "relative_pct",
            title=f"Keyword video performance vs. general baseline (subscriber-normalized): {KEYWORDS}",
            ylabel=f"views/subscriber relative to {baseline_label} (%)",
            plot_start=PLOT_START_DATE, event_date=EVENT_DATE, baseline_label=baseline_label,
            smooth=SMOOTH_PLOTS, smooth_span=SMOOTH_SPAN,
        )


if __name__ == "__main__":
    main()

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
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.lines as mlines

from youtube_code.config import RAW, CHANNEL_LISTS, SAMPLES, OUTPUT_GEMINI, KEYWORDS, EXTERNAL

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
BASELINE_WINDOW_MONTHS = 3        # number of months counted backwards from BASELINE_MONTH (incl.)
BASELINE_WINDOW_SINGLE = 6        # number of months for channel-wise baseline calculation
PLOT_START_DATE = "2022-10-01"

# --- Data source paths ---
METADATA_INPUT = RAW / "video_metadata_total.jsonl"
METADATA_OUTPUT = SAMPLES / "combined" / "video_metadata_relevant.csv"
CHANNEL_LIST_PATH = CHANNEL_LISTS / "combined" / "channel_list.json"
CLASSIFICATION_PATH = OUTPUT_GEMINI / "channel_results_051.xlsx"
MEDIA_PATH = EXTERNAL / "media_type.xlsx"
START_DATE = "2022-10"
END_DATE = "2026-03"

# --- Inclusion of YouTube Shorts (videos below one minute)
INCLUDE_SHORTS = True

# --- Grouping column (switch to 'populism_group' to re-run everything by populism instead) ---
GROUP_COL = "type"

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
SMOOTH_PLOTS = False
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
    Faceted weighting-scheme comparison: one subplot per ideology group.

    Layout
    ------
    - Left y-axis  : Value-weighted & Sqrt-weighted (solid lines, circle markers).
    - Right y-axis : Equal-weighted (dashed line, x markers).
    - Both axes share a **single global scale** across all panels so groups can be
      compared at a glance.
    - A shared legend sits below the figure and never overlaps the data.
    """
    equal_label = "Equal-weighted"

    plot_df = df_combined[df_combined[date_col] >= plot_start].copy()
    if smooth:
        plot_df[value_col] = (
            plot_df.groupby([group_col, weighting_col])[value_col]
            .transform(
                lambda x: x.rolling(window=smooth_span, center=True, win_type="triang").mean()
            )
        )

    groups = sorted(plot_df[group_col].astype(str).unique())
    n_groups = len(groups)
    cols = min(3, n_groups)
    rows = (n_groups - 1) // cols + 1

    # ------------------------------------------------------------------
    # Global y-limits: computed once, applied to every panel
    # ------------------------------------------------------------------
    def _limits(series):
        s = series.dropna()
        if s.empty:
            return 80.0, 120.0
        lo, hi = s.min(), s.max()
        margin = max((hi - lo) * 0.12, 5.0)
        return lo - margin, hi + margin

    y1_min, y1_max = _limits(plot_df.loc[plot_df[weighting_col] != equal_label, value_col])
    y2_min, y2_max = _limits(plot_df.loc[plot_df[weighting_col] == equal_label, value_col])

    # ------------------------------------------------------------------
    # Color map (consistent across panels)
    # ------------------------------------------------------------------
    weightings = list(plot_df[weighting_col].unique())
    palette = sns.color_palette("tab10", len(weightings))
    color_map = dict(zip(weightings, palette))

    # ------------------------------------------------------------------
    # Build figure
    # ------------------------------------------------------------------
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(rows, cols, figsize=(5.5 * cols, 4.2 * rows), squeeze=False)
    axes_flat = axes.flatten()

    for i, group in enumerate(groups):
        ax1 = axes_flat[i]
        ax2 = ax1.twinx()

        group_df = plot_df[plot_df[group_col].astype(str) == group]

        # Left axis: value- and sqrt-weighted
        for w in [w for w in weightings if w != equal_label]:
            w_df = group_df[group_df[weighting_col] == w].sort_values(date_col)
            ax1.plot(w_df[date_col], w_df[value_col],
                     color=color_map[w], marker="o", markersize=4,
                     linewidth=2, label=w)

        # Right axis: equal-weighted
        eq_df = group_df[group_df[weighting_col] == equal_label].sort_values(date_col)
        if not eq_df.empty:
            ax2.plot(eq_df[date_col], eq_df[value_col],
                     color=color_map[equal_label], marker="x", markersize=5,
                     linestyle="--", linewidth=2, label=equal_label)

        # Shared global limits
        ax1.set_ylim(y1_min, y1_max)
        ax2.set_ylim(y2_min, y2_max)

        # Reference lines
        ax1.axhline(100, color="red", linestyle="--", linewidth=1.2, zorder=0)
        ax1.axvline(pd.to_datetime(event_date), color="grey",
                    linestyle=":", linewidth=1.2, zorder=0)

        ax1.set_title(group, fontsize=11, fontweight="bold", pad=6)
        ax1.tick_params(axis="x", rotation=45)
        ax2.grid(False)  # avoid double grid

        # y-axis labels only at the outer edges
        col_pos = i % cols
        is_leftmost  = col_pos == 0
        is_rightmost = (col_pos == cols - 1) or (i == n_groups - 1)

        if is_leftmost:
            ax1.set_ylabel(f"Value / Sqrt-weighted (%)\n(rel. to {baseline_label})", fontsize=9)
        else:
            ax1.set_ylabel("")
            ax1.set_yticklabels([])

        if is_rightmost:
            ax2.set_ylabel(f"Equal-weighted (%)\n(rel. to {baseline_label})", fontsize=9)
        else:
            ax2.set_ylabel("")
            ax2.set_yticklabels([])

    # Hide unused subplots
    for j in range(n_groups, len(axes_flat)):
        axes_flat[j].set_visible(False)

    # ------------------------------------------------------------------
    # Shared legend below the figure
    # ------------------------------------------------------------------
    legend_handles = [
        mlines.Line2D([], [], color=color_map[w], marker="o" if w != equal_label else "x",
                      linestyle="-" if w != equal_label else "--",
                      linewidth=2, markersize=5,
                      label=w)
        for w in weightings
    ]
    legend_handles += [
        mlines.Line2D([], [], color="red",  linestyle="--", linewidth=1.2,
                      label=f"Baseline ({baseline_label} = 100 %)"),
        mlines.Line2D([], [], color="grey", linestyle=":",  linewidth=1.2,
                      label="Event date (Oct 7, 2023)"),
    ]

    # tight_layout with rect reserves space at the bottom for the legend;
    # bbox_to_anchor (0, 0) is relative to the rect's lower-left corner.
    fig.suptitle("Weighting-scheme comparison per group", fontsize=14)

    fig.legend(handles=legend_handles,
               loc="lower center",
               bbox_to_anchor=(0.5, 0.01),
               ncol=min(len(legend_handles), 4),
               frameon=True, fontsize=9)
    fig.tight_layout(rect=[0, 0.10, 1, 0.97])
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

    df["log_views_per_subscriber"] = np.log1p(df["views_per_subscriber"])
    tdf = df[(df["ideology_group"] == "right") & ((df["month"] == "2023-10") | (df["month"] == "2023-09") | (df["month"] == "2023-11"))
             & (df["has_keyword"] == True)]

    tdf.to_csv("keyword_df.csv", index=False)
    df["views_per_subscriber"] = np.log1p(df["views_per_subscriber"])
    overall = monthly_mean(df, "All videos")
    keyword_label = "Videos with keyword)"
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
    Keyword-analysis plot: colour = group (same color for a group's keyword line and its
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
# STEP 5 HELPERS: Shorts vs. long videos
# ======================================================================

def build_shorts_comparisons(df, keywords, group_col, baseline_month, baseline_window_months,
                             date_col = "published_at", value_col = "views_per_subscriber"):
    """
    Creates dataframes for three shorts-comparisons. Uses logged views per subscriber.
    """
    df = df.copy()
    if "has_keyword" not in df.columns:
        pattern = "|".join(re.escape(kw) for kw in keywords)
        df["has_keyword"] = df["title"].str.contains(pattern, case = False, na = False, regex = True)
    df[value_col] = np.log1p(df[value_col])


    valid_shorts = [
        ("center", "2024-08"),
        ("center", "2025-06"),
        ("center", "2025-10"),
        ("left", "2024-11"),
        ("left", "2024-12"),
        ("left", "2025-05"),
        ("right", "2023-10"),
        ("right", "2025-05"),
        ("right", "2025-10")
    ]

    valid_videos = [
        ("center", "2023-10"),
        ("center", "2024-10"),
        ("center", "2025-07"),
        ("left", "2023-01"),
        ("left", "2023-10"),
        ("left", "2024-09"),
        ("right", "2023-02"),
        ("right", "2023-03"),
        ("right", "2023-10"),
        ("right", "2024-05"),
        ("right", "2024-12"),
        ("right", "2025-05"),
    ]

    kdf = df[df["has_keyword"] == True]

    shorts_mean_value = df[df["is_short"] == True].groupby(group_col)[value_col].mean().reset_index()
    videos_mean_value = df[df["is_short"] == False].groupby(group_col)[value_col].mean().reset_index()
    kw_shorts_mean_value = kdf[kdf["is_short"] == True].groupby(group_col)[value_col].mean().reset_index()
    kw_videos_mean_value = kdf[kdf["is_short"] == False].groupby(group_col)[value_col].mean().reset_index()

    with open("temp_output/view_stats.txt", "w+") as f:
        f.write(f"{'=' * 5} Mean views per subscriber comparison {'=' * 5}\n")
        f.write("Shorts mean logged views per subscriber:\n")
        f.write(shorts_mean_value.to_string())
        f.write("\n\nVideos mean logged views per subscriber:\n")
        f.write(videos_mean_value.to_string())
        f.write("\n\nKeyword shorts mean logged views per subscriber:\n")
        f.write(kw_shorts_mean_value.to_string())
        f.write("\n\nKeyword videos mean logged views per subscriber:\n")
        f.write(kw_videos_mean_value.to_string())
        f.write(f"\n{"="*50}")

        f.seek(0)
        print(f.read())

    tdf = kdf[kdf.set_index([group_col, "month"]).index.isin(valid_shorts) & (kdf["is_short"] == True)]
    vdf = kdf[kdf.set_index([group_col, "month"]).index.isin(valid_videos) & (kdf["is_short"] == False)]

    tdf.to_csv("shorts_df.csv", index=False)
    vdf.to_csv("videos_df.csv", index=False)

    def get_monthly_mean(sub_df, label_col_name, label_val):
        out = (
            sub_df.groupby([pd.Grouper(key=date_col, freq="ME"), group_col])[value_col]
            .mean().reset_index()
        )
        out[label_col_name] = label_val
        return out

    # --- 1. All shorts vs. all other videos ---
    shorts_all = get_monthly_mean(df[df["is_short"] == True], "video_type", "Shorts")
    long_all = get_monthly_mean(df[df["is_short"] == False], "video_type", "Long videos")
    comp1 = pd.concat([shorts_all, long_all], ignore_index=True)

    # Baseline: Shorts vs. shorts, longs vs. longs
    comp1["group_type_combo"] = comp1[group_col].astype(str) + " | " + comp1["video_type"]
    comp1_rebased = rebase_to_baseline(
        comp1, group_col="group_type_combo", value_col=value_col, baseline_month = baseline_month,
        baseline_window_months =baseline_window_months, date_col = "published_at")
    comp1_rebased[group_col] = comp1_rebased["group_type_combo"].apply(lambda x: x.split(" | ")[0])

    # --- 2. Shorts with keyword vs. shorts without keyword ---
    kw_shorts = get_monthly_mean(df[(df["is_short"] == True) & (df["has_keyword"] == True)], "series", "Keyword Shorts")
    non_kw_shorts = get_monthly_mean(df[(df["is_short"] == True) & (df["has_keyword"] == False)], "series",
                                     "Non-Keyword Shorts")
    all_shorts_baseline = get_monthly_mean(df[df["is_short"] == True], "series", "All Shorts")

    comp2 = pd.concat([kw_shorts, non_kw_shorts, all_shorts_baseline], ignore_index=True)
    comp2_rebased = rebase_to_baseline(
        comp2, group_col=group_col, value_col=value_col, date_col=date_col,
        baseline_month=baseline_month, baseline_window_months=baseline_window_months,
        baseline_mask=(comp2["series"] == "All Shorts")
    )
    comp2_rebased = comp2_rebased[comp2_rebased["series"].isin(["Keyword Shorts", "Non-Keyword Shorts"])]

    # --- 3. Shorts with keyword vs. videos with keyword ---
    kw_shorts_3 = get_monthly_mean(df[(df["is_short"] == True) & (df["has_keyword"] == True)], "video_type",
                                   "Keyword Shorts")
    kw_long_3 = get_monthly_mean(df[(df["is_short"] == False) & (df["has_keyword"] == True)], "video_type",
                                 "Keyword Long Videos")

    all_shorts_3 = get_monthly_mean(df[df["is_short"] == True], "video_type", "All Shorts (Baseline)")
    all_long_3 = get_monthly_mean(df[df["is_short"] == False], "video_type", "All Long Videos (Baseline)")

    # Rebasing Shorts
    comp3_shorts = pd.concat([kw_shorts_3, all_shorts_3], ignore_index=True)
    comp3_shorts_rebased = rebase_to_baseline(
        comp3_shorts, group_col=group_col, value_col=value_col, date_col=date_col,
        baseline_month=baseline_month, baseline_window_months=baseline_window_months,
        baseline_mask=(comp3_shorts["video_type"] == "All Shorts (Baseline)")
    )

    # Rebasing Long Videos
    comp3_long = pd.concat([kw_long_3, all_long_3], ignore_index=True)
    comp3_long_rebased = rebase_to_baseline(
        comp3_long, group_col=group_col, value_col=value_col, date_col=date_col,
        baseline_month=baseline_month, baseline_window_months=baseline_window_months,
        baseline_mask=(comp3_long["video_type"] == "All Long Videos (Baseline)")
    )

    comp3_rebased = pd.concat([
        comp3_shorts_rebased[comp3_shorts_rebased["video_type"] == "Keyword Shorts"],
        comp3_long_rebased[comp3_long_rebased["video_type"] == "Keyword Long Videos"]
    ], ignore_index=True)

    # --- 4. Videos with keyword vs. videos without keyword ---
    kw_videos = get_monthly_mean(df[(df["is_short"] == False) & (df["has_keyword"] == True)], "series", "Keyword Videos")
    non_kw_videos = get_monthly_mean(df[(df["is_short"] == False) & (df["has_keyword"] == False)], "series",
                                     "Non-Keyword Videos")
    all_videos_baseline = get_monthly_mean(df[df["is_short"] == False], "series", "All Videos")

    comp4 = pd.concat([kw_videos, non_kw_videos, all_videos_baseline], ignore_index=True)
    comp4_rebased = rebase_to_baseline(
        comp4, group_col=group_col, value_col=value_col, date_col=date_col,
        baseline_month=baseline_month, baseline_window_months=baseline_window_months,
        baseline_mask=(comp4["series"] == "All Videos")
    )
    comp4_rebased = comp4_rebased[comp4_rebased["series"].isin(["Keyword Videos", "Non-Keyword Videos"])]

    return comp1_rebased, comp2_rebased, comp3_rebased, comp4_rebased


def plot_shorts_comparison(df_plot, date_col, value_col, group_col, hue_col,
                           title, ylabel, plot_start, event_date, baseline_label,
                           smooth=False, smooth_span=3):
    """
    Faceted Shorts-comparison plot: one subplot per ideology group.

    Layout
    ------
    - All panels share a **single global y-axis scale** so differences in magnitude
      between groups are immediately visible.
    - The shared legend is placed below the figure and never overlaps the data.
    """
    plot_df = df_plot[df_plot[date_col] >= plot_start].copy()
    if smooth:
        plot_df[value_col] = (
            plot_df.groupby([group_col, hue_col])[value_col]
            .transform(
                lambda x: x.rolling(window=smooth_span, center=True, win_type="triang").mean()
            )
        )

    # ------------------------------------------------------------------
    # Global y-limits
    # ------------------------------------------------------------------
    s = plot_df[value_col].dropna()
    if not s.empty:
        lo, hi = s.min(), s.max()
        margin = max((hi - lo) * 0.12, 5.0)
        y_min, y_max = lo - margin, hi + margin
    else:
        y_min, y_max = 80.0, 120.0

    groups = sorted(plot_df[group_col].astype(str).unique())
    hues   = list(plot_df[hue_col].unique())
    n_groups = len(groups)
    cols = min(3, n_groups)
    rows = (n_groups - 1) // cols + 1

    palette   = sns.color_palette("tab10", len(hues))
    color_map = dict(zip(hues, palette))

    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(rows, cols, figsize=(5.5 * cols, 4.2 * rows), squeeze=False)
    axes_flat = axes.flatten()

    for i, group in enumerate(groups):
        ax = axes_flat[i]
        group_df = plot_df[plot_df[group_col].astype(str) == group]

        for h in hues:
            h_df = group_df[group_df[hue_col] == h].sort_values(date_col)
            ax.plot(h_df[date_col], h_df[value_col],
                    color=color_map[h], marker="o", markersize=4,
                    linewidth=2, label=h)

        # Shared global y-limits
        ax.set_ylim(y_min, y_max)

        ax.set_title(group, fontsize=11, fontweight="bold", pad=6)
        ax.axhline(100, color="red",  linestyle="--", linewidth=1.2)
        ax.axvline(pd.to_datetime(event_date), color="grey", linestyle=":", linewidth=1.2)
        ax.tick_params(axis="x", rotation=45)
        ax.set_xlabel("Month")

        if i % cols == 0:
            ax.set_ylabel(ylabel)
        else:
            ax.set_ylabel("")

    # Hide unused subplots
    for j in range(n_groups, len(axes_flat)):
        axes_flat[j].set_visible(False)

    # ------------------------------------------------------------------
    # Shared legend below the figure
    # ------------------------------------------------------------------
    legend_handles = [
        mlines.Line2D([], [], color=color_map[h], marker="o", linewidth=2,
                      markersize=5, label=h)
        for h in hues
    ]
    legend_handles += [
        mlines.Line2D([], [], color="red",  linestyle="--", linewidth=1.2,
                      label=f"Baseline ({baseline_label} = 100 %)"),
        mlines.Line2D([], [], color="grey", linestyle=":",  linewidth=1.2,
                      label="Event date (Oct 7, 2023)"),
    ]
    fig.suptitle(title, fontsize=14)

    fig.legend(handles=legend_handles,
               loc="lower center",
               bbox_to_anchor=(0.5, 0),
               ncol=min(len(legend_handles), 4),
               frameon=True, fontsize=9)

    fig.tight_layout(rect=[0, 0.1, 1, 0.97])
    plt.show()


# ======================================================================
# MAIN
# ======================================================================

def main():
    baseline_label = format_baseline_label(BASELINE_MONTH, BASELINE_WINDOW_MONTHS)

    # ---- STEP 1: Load data ----
    # Adjust paths/dates above if the data location or time window changes.
    df = load_video_data(METADATA_INPUT, METADATA_OUTPUT, CHANNEL_LIST_PATH, CLASSIFICATION_PATH,
                          MEDIA_PATH, START_DATE, END_DATE, INCLUDE_SHORTS)
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
    # keyword_df = keyword_relative_success(df, KEYWORDS, GROUP_COL, BASELINE_MONTH, BASELINE_WINDOW_MONTHS,
    #                                       value_col = "views_per_subscriber")
    # if keyword_df is not None:
    #     focus_series = next(s for s in keyword_df["series"].unique() if s != "All videos")
    #     plot_keyword_focus_trend(
    #         keyword_df, GROUP_COL, "series", focus_series, "published_at", "relative_pct",
    #         title=f"Keyword video performance vs. general baseline (subscriber-normed, logged values)",
    #         ylabel=f"views/subscriber relative to {baseline_label} (%)",
    #         plot_start=PLOT_START_DATE, event_date=EVENT_DATE, baseline_label=baseline_label,
    #         smooth=SMOOTH_PLOTS, smooth_span=SMOOTH_SPAN,
    #     )

    # ---- STEP 5: Shorts vs. long videos ----
    comp1, comp2, comp3, comp4 = build_shorts_comparisons(
        df, KEYWORDS, GROUP_COL, BASELINE_MONTH, BASELINE_WINDOW_MONTHS,
        value_col="views_per_subscriber"
    )

    # Comparison 1: Shorts vs. long videos (All shorts and videos, respectively)
    plot_shorts_comparison(
        comp1, "published_at", "relative_pct", GROUP_COL, "video_type",
        title="1. All Shorts vs. All Long Videos",
        ylabel=f"relative to own baseline (%)",
        plot_start=PLOT_START_DATE, event_date=EVENT_DATE, baseline_label=baseline_label,
        smooth=SMOOTH_PLOTS, smooth_span=SMOOTH_SPAN
    )

    # Comparison 2: Keyword shorts vs. non-Keyword shorts (Baseline: All shorts)
    plot_shorts_comparison(
        comp2, "published_at", "relative_pct", GROUP_COL, "series",
        title="2. Keyword Shorts vs. Non-Keyword Shorts",
        ylabel=f"relative to All Shorts baseline (%)",
        plot_start=PLOT_START_DATE, event_date=EVENT_DATE, baseline_label=baseline_label,
        smooth=SMOOTH_PLOTS, smooth_span=SMOOTH_SPAN
    )

    # Comparison 3: Keyword shorts vs. Keyword Long Videos (Baseline: All shorts and videos, respectively)
    plot_shorts_comparison(
        comp3, "published_at", "relative_pct", GROUP_COL, "video_type",
        title="3. Keyword Shorts vs. Keyword Long Videos",
        ylabel=f"relative to respective general baseline (%)",
        plot_start=PLOT_START_DATE, event_date=EVENT_DATE, baseline_label=baseline_label,
        smooth=SMOOTH_PLOTS, smooth_span=SMOOTH_SPAN
    )

    # Comparison 4: Keyword videos vs. non-Keyword videos (Baseline: All videos)
    plot_shorts_comparison(
        comp4, "published_at", "relative_pct", GROUP_COL, "series",
        title="4. Keyword Videos vs. Non-Keyword Videos",
        ylabel=f"relative to All Videos baseline (%)",
        plot_start=PLOT_START_DATE, event_date=EVENT_DATE, baseline_label=baseline_label,
        smooth=SMOOTH_PLOTS, smooth_span=SMOOTH_SPAN
    )

if __name__ == "__main__":
    main()
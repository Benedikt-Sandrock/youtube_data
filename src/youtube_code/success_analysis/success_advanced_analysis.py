"""
success_advanced_analysis.py

Deeper analyses of channel performance around the 7 Oct 2023 event, complementing
success_trend_analysis.py:

    STEP 1: Load data
    STEP 2: Channel-/video-count transparency per group
    STEP 2b: Keyword flag (Nahost-related videos) + combined "group x keyword" grouping
    STEP 3: Views decomposition (more uploads vs. better-performing uploads)
    STEP 4: Pre-event trend extrapolation ("organic growth" counterfactual baseline)
    STEP 5: Interrupted Time Series regression (formal significance test, group interactions)
    STEP 6: Decay / half-life of the post-event peak (exploratory)
    STEP 7: Format shift - share of short videos over time
    STEP 8: Engagement rate (likes+comments per view), if the columns are available

KEYWORD vs. NON-KEYWORD COMPARISON (new):
    As of this version, every analysis from STEP 3 onward runs on a COMBINED grouping
    column that crosses ideology group with the keyword flag, e.g.

        "Rechtspopulistisch – Keyword"      "Rechtspopulistisch – kein Keyword"
        "Mainstream – Keyword"              "Mainstream – kein Keyword"
        ...

    instead of just the ideology group. This lets you see, WITHIN each ideology group,
    whether Nahost-keyword videos behave differently (bigger post-event spike? faster
    decay? more shorts? higher engagement?) than that same group's non-keyword output.
    See flag_keyword_videos() and add_group_keyword_combo() below.

    IMPORTANT: the keyword flag is per VIDEO, not per channel - a single channel
    contributes to both the "Keyword" and "kein Keyword" line of its group. This is
    intentional (a channel isn't "a keyword channel", individual uploads are), but it
    also means group sizes (in videos, not channels) can get quite small for some
    group x keyword combinations in some months - check print_video_counts() output
    before trusting any single monthly value.

NOT included (data not available yet, see comments at the end of main()):
    - Linking these metrics to the sentiment/framing/populism LLM classification
    - Subscriber GROWTH (only a current snapshot exists, no historical series)

NEW DEPENDENCIES compared to success_trend_analysis.py:
    pip install statsmodels scipy --break-system-packages
    (scipy is likely already installed as a seaborn/pandas dependency; statsmodels probably not)

Shared building blocks live in success_data_utils.py and success_plot_utils.py - both must be
importable (same folder or on PYTHONPATH) when running this script.
"""

import re

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import statsmodels.formula.api as smf
from scipy.optimize import curve_fit

from youtube_code.config import RAW, CHANNEL_LISTS, SAMPLES, OUTPUT_GEMINI, KEYWORDS, EXTERNAL

from success_data_utils import load_video_data, rebase_to_baseline, format_baseline_label, plot_group_trend


# ======================================================================
# CONFIG
# ======================================================================

# --- Event & baseline period ---
EVENT_DATE = "2023-10-07"
BASELINE_MONTH = "2023-09"
BASELINE_WINDOW_MONTHS = 3
PLOT_START_DATE = "2022-10-01"

# --- Data source paths ---
METADATA_INPUT = RAW / "video_metadata_total.jsonl"
METADATA_OUTPUT = SAMPLES / "combined" / "video_metadata_relevant.csv"
CHANNEL_LIST_PATH = CHANNEL_LISTS / "combined" / "channel_list.json"
CLASSIFICATION_PATH = OUTPUT_GEMINI / "channel_results_051.xlsx"
MEDIA_PATH = EXTERNAL / "media_type.xlsx"
START_DATE = "2022-10"
END_DATE = "2025-12"

# --- Inclusion of YouTube Shorts (videos below one minute)
INCLUDE_SHORTS = False

# --- Grouping column ---
GROUP_COL = "ideology_group"

# --- Keyword flag (Nahost-related videos) ---
TITLE_COL = "title"
KEYWORD_COL = "has_keyword"
# Combined grouping column used by all analyses from STEP 3 onward: crosses GROUP_COL with
# KEYWORD_COL so every ideology group is split into its "Keyword" and "kein Keyword" trajectory.
GROUP_KEYWORD_COL = "group_x_keyword"


# --- STEP 4: pre-event trend extrapolation ---
PRE_EVENT_TREND_MONTHS = 6   # number of months BEFORE the event used to fit the linear trend

# --- STEP 5: ITS regression ---
ITS_HAC_LAGS = 3             # Newey-West HAC lags for autocorrelation-robust standard errors

# --- STEP 7: format shift ---
SHORT_VIDEO_THRESHOLD_SECONDS = 60   # YouTube's usual Shorts definition (adjust if needed)


# ======================================================================
# STEP 2: channel-/video-count transparency
# ======================================================================

def print_channel_counts(df, group_col):
    """
    Print how many channels make up each group. Important context for interpreting the
    equal-/sqrt-weighted indices from success_trend_analysis.py: a noisy median computed from
    3 channels is far less reliable than one computed from 40, even though both plots look
    equally "official".

    NOTE: once group_col is the group x keyword combo, this counts how many DISTINCT
    channels ever contributed at least one video to that combo - not how many videos.
    A channel can appear in both the "Keyword" and "kein Keyword" row of its group.
    See print_video_counts() for the video-level equivalent, which matters more for the
    monthly time series (a channel contributing 1 keyword video still only counts once here).
    """
    counts = df.groupby(group_col)["channel_title"].nunique().reset_index(name="n_channels")
    print("\n=== Number of channels per group ===")
    print(counts.to_string(index=False))
    return counts


def print_video_counts(df, group_col):
    """
    Print how many VIDEOS make up each group. Especially important once group_col is the
    group x keyword combo: a group's "Keyword" row can have far fewer videos than its
    "kein Keyword" row (Nahost coverage is usually a minority of total output even for
    channels that cover it a lot), which makes the monthly aggregates in STEP 3 onward
    noisier for that row - check this table before trusting a single spike/dip.
    """
    counts = df.groupby(group_col).size().reset_index(name="n_videos")
    print("\n=== Number of videos per group ===")
    print(counts.to_string(index=False))
    return counts


# ======================================================================
# STEP 2b: keyword flag + combined "group x keyword" grouping column
# ======================================================================

def flag_keyword_videos(df, title_col=TITLE_COL, keywords=KEYWORDS, out_col=KEYWORD_COL):
    """
    Flags each video as keyword-related (True) or not (False) via a case-insensitive
    substring match of `keywords` against `title_col`. Mirrors the keyword-based topic
    flagging already used in nahost_descriptive_analysis.py - keep KEYWORDS in sync
    with that script if you want "keyword video" to mean the same thing in both places.

    CAUTION: title-only matching will miss videos whose title doesn't mention Nahost-related
    terms even if the content/transcript does (and vice versa: a title mention doesn't
    guarantee the video is actually about the topic). If nahost_descriptive_analysis.py
    matches against a different field (e.g. transcript or description) as well, consider
    reusing that column directly instead of re-deriving it here from title only.
    """
    if not keywords:
        raise ValueError(
            "KEYWORDS ist leer - bitte die Keyword-Liste oben in der CONFIG-Sektion "
            "eintragen (siehe nahost_descriptive_analysis.py), bevor dieses Skript laeuft."
        )

    df = df.copy()
    pattern = "|".join(re.escape(kw) for kw in keywords)
    df[out_col] = df[title_col].str.contains(pattern, case=False, na=False, regex=True)

    share = df[out_col].mean() * 100
    print(f"\nKeyword flag: {df[out_col].sum()} / {len(df)} videos ({share:.1f}%) matched "
          f"{len(keywords)} keyword(s) in '{title_col}'.")
    return df


def add_group_keyword_combo(df, group_col, keyword_col=KEYWORD_COL, out_col=GROUP_KEYWORD_COL):
    """
    Combines the ideology group and the keyword flag into a single categorical column, e.g.
    "Rechtspopulistisch - Keyword" / "Rechtspopulistisch - kein Keyword". This lets every
    existing group-based function below (which only knows about a single `group_col`) be
    reused UNCHANGED to compare keyword vs. non-keyword videos WITHIN each ideology group -
    each combo is simply treated as "a group" by decompose_views(), plot_group_trend(),
    run_interrupted_time_series(), etc.

    Trade-off: with G ideology groups this doubles the number of lines/categories (2G) in
    every plot and regression. For readability you may want to plot/inspect one ideology
    group's two lines at a time rather than all 2G lines at once - the plotting functions
    already accept a pre-filtered dataframe, so just filter on group_col before calling
    plot_*() if a given chart gets too crowded.
    """
    df = df.copy()
    label = df[keyword_col].map({True: "Keyword", False: "kein Keyword"})
    df[out_col] = df[group_col].astype(str) + " - " + label
    return df


# ======================================================================
# STEP 3: views decomposition
# ======================================================================

def decompose_views(df, group_col, date_col="published_at", view_col="view_count"):
    """
    Split total monthly views per group into number of videos and views per video. This
    distinguishes two different stories: a rise driven by MORE uploads (posting behaviour)
    vs. a rise driven by BETTER-PERFORMING uploads (audience interest).

    With group_col = GROUP_KEYWORD_COL, comparing the "Keyword" and "kein Keyword" rows of
    the same ideology group tells you whether a post-event rise in that group's Nahost
    coverage was driven mainly by posting MORE keyword videos, by keyword videos performing
    BETTER per video, or both - and how that compares to the group's non-keyword baseline.
    """
    monthly = (
        df.groupby([pd.Grouper(key=date_col, freq="ME"), group_col])
        .agg(total_views=(view_col, "sum"), n_videos=(view_col, "count"))
        .reset_index()
    )
    monthly["views_per_video"] = monthly["total_views"] / monthly["n_videos"]
    return monthly


def plot_views_decomposition(monthly, group_col, date_col, plot_start, event_date,
                              baseline_month, baseline_window_months):
    """Three panels side by side: total views, number of videos, views per video - each
    relative to the baseline, so you can see at a glance which component drives a rise."""
    metrics = [("total_views", "Total views"), ("n_videos", "Number of videos"),
               ("views_per_video", "Views per video")]
    baseline_label = format_baseline_label(baseline_month, baseline_window_months)

    fig, axes = plt.subplots(1, 3, figsize=(20, 6), sharex=True)
    sns.set_theme(style="whitegrid")

    for i, (ax, (col, label)) in enumerate(zip(axes, metrics)):
        rebased = rebase_to_baseline(monthly, group_col, col, date_col, baseline_month, baseline_window_months)
        plot_group_trend(
            rebased, group_col, date_col, "relative_pct", title=label,
            ylabel=f"relative to {baseline_label} (%)" if i == 0 else "",
            plot_start=plot_start, event_date=event_date,
            reference_line=100, reference_label=f"Baseline ({baseline_label})",
            ax=ax, show_legend=(i == len(metrics) - 1),
        )

    fig.suptitle("Views decomposition: more content, or better-performing content?", y=1.03)
    plt.tight_layout()
    plt.show()


# ======================================================================
# STEP 4: pre-event trend extrapolation (organic-growth counterfactual)
# ======================================================================

def trend_extrapolated_baseline(monthly, group_col, event_date, pre_event_months,
                                 date_col="published_at", value_col="total_views"):
    """
    Fit a linear trend per group using ONLY the `pre_event_months` months before the event,
    extrapolate it forward as a counterfactual ("what would have happened without the
    event"), and compare the actual trajectory to it. relative_to_trend_pct = 100 means
    "exactly as expected"; >100 means "more than expected without the event" - a stronger
    claim than comparing to a single fixed baseline month, because organic growth/decline is
    factored out.

    Purely descriptive/exploratory: assuming a LINEAR pre-event trend is a simplification,
    not a causal test (see run_interrupted_time_series() for that).

    CAUTION with group_col = GROUP_KEYWORD_COL: pre-event keyword-video volume can be very
    low for some groups (Nahost coverage before Oct 2023 may have been sparse or absent for
    some channels), so the pre-event linear fit for a "Keyword" row can be based on very few,
    noisy months - the function already warns if fewer than 2 months are available, but even
    a fit on 2-3 thin months should be treated with caution.
    """
    event_period = pd.Period(event_date, freq="M")
    results = []

    for group, gdf in monthly.groupby(group_col):
        gdf = gdf.sort_values(date_col).copy()
        gdf["month_period"] = gdf[date_col].dt.to_period("M")
        gdf["month_idx"] = gdf["month_period"].apply(lambda p: p.ordinal)

        pre = gdf[gdf["month_period"] < event_period].tail(pre_event_months)
        if len(pre) < 2:
            print(f"Warning: too few pre-event months ({len(pre)}) for group '{group}' - "
                  "skipping trend extrapolation.")
            continue

        slope, intercept = np.polyfit(pre["month_idx"], pre[value_col], 1)
        gdf["expected"] = slope * gdf["month_idx"] + intercept

        if (gdf["expected"] <= 0).any():
            print(f"Warning: linear trend goes <= 0 at some point for group '{group}' "
                  "(unrealistic) - affected months are set to NaN.")
            gdf.loc[gdf["expected"] <= 0, "expected"] = np.nan

        gdf["relative_to_trend_pct"] = gdf[value_col] / gdf["expected"] * 100
        results.append(gdf)

    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()


def plot_trend_extrapolated(df_trend, group_col, date_col, plot_start, event_date):
    plot_group_trend(
        df_trend, group_col, date_col, "relative_to_trend_pct",
        title='Actual trajectory vs. extrapolated pre-event trend ("counterfactual without event")',
        ylabel="Actual / expected (%)",
        plot_start=plot_start, event_date=event_date,
        reference_line=100, reference_label="Expected without event (100%)",
    )


# ======================================================================
# STEP 5: Interrupted Time Series regression
# ======================================================================

def run_interrupted_time_series(monthly, group_col, event_date, date_col="published_at",
                                 value_col="total_views", hac_lags=ITS_HAC_LAGS):
    """
    Segmented regression (Interrupted Time Series) with a level shift and a slope shift at the
    event, each interacted with the group:

        log(1+views) ~ t + post + t_since_event + C(group)
                        + post:C(group) + t_since_event:C(group)

    t              : month index (linear time trend)
    post           : 1 from the event month onward, else 0 (level shift)
    t_since_event  : months since the event (0 before it) -> slope shift
    interactions with C(group): test whether the effect differs between groups (the reference
    group is whichever category sorts first).

    Log1p transform, because view counts are typically skewed/multiplicative - coefficients
    are then roughly interpretable as percentage effects.

    HAC-robust standard errors (Newey-West, hac_lags lags), because monthly time series
    typically have autocorrelated residuals - with plain OLS standard errors, p-values would
    be too optimistic (falsely "significant" too often).

    CAUTION: with only ~36-40 monthly observations per group, the sample is small. This
    limits statistical power, especially for the interaction terms - a non-significant result
    here often means "not enough data to tell", not "no effect".

    WITH group_col = GROUP_KEYWORD_COL: each "group" in this model is now an ideology x
    keyword combo, so the C(group) interaction terms compare EVERY combo against the
    reference combo - including cross-cutting comparisons (e.g. group A's keyword videos vs.
    group B's non-keyword videos) that are not the comparison you actually care about. To
    read off "does the keyword effect differ from the non-keyword effect WITHIN group X",
    look specifically at the post:C(group) and t_since_event:C(group) rows whose combo label
    contains group X, and compare its "Keyword" and "kein Keyword" coefficients to each other
    (not just to the reference category) - subtract them manually from the printed table, or
    re-run the model with the "kein Keyword" row of the SAME ideology group as the reference
    category (relevel via C(group, Treatment(reference=...))) if you want that as a direct
    coefficient with its own p-value. With 2x as many categories as before, also expect the
    per-category sample size (and therefore power) to be lower than in the ideology-only run.
    """
    model_df = monthly.copy()
    model_df["month_period"] = model_df[date_col].dt.to_period("M")
    model_df["t"] = model_df["month_period"].apply(lambda p: p.ordinal)
    model_df["t"] -= model_df["t"].min()

    event_period = pd.Period(event_date, freq="M")
    model_df["post"] = (model_df["month_period"] >= event_period).astype(int)
    event_t_series = model_df.loc[model_df["month_period"] == event_period, "t"]
    event_t = event_t_series.iloc[0] if len(event_t_series) else model_df.loc[model_df["post"] == 1, "t"].min()
    model_df["t_since_event"] = np.where(model_df["post"] == 1, model_df["t"] - event_t, 0)

    model_df["log_value"] = np.log1p(model_df[value_col].astype(float))
    model_df[group_col] = model_df[group_col].astype(str)

    formula = (f"log_value ~ t + post + t_since_event + C({group_col}) "
               f"+ post:C({group_col}) + t_since_event:C({group_col})")

    model = smf.ols(formula, data=model_df).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})

    print("\n=== Interrupted Time Series Regression ===")
    print(model.summary())

    print("\n--- Compact view: interaction terms (between-group differences) ---")
    interaction_terms = [t for t in model.params.index if ":" in t]
    summary_rows = [{
        "term": term,
        "coef": model.params[term],
        "p_value": model.pvalues[term],
        "significant (p<0.05)": model.pvalues[term] < 0.05,
    } for term in interaction_terms]
    print(pd.DataFrame(summary_rows).to_string(index=False))

    return model


# ======================================================================
# STEP 6: decay / half-life of the post-event peak (exploratory)
# ======================================================================

def estimate_decay_halflife(monthly_rebased, group_col, event_date, date_col="published_at",
                             value_col="relative_pct"):
    """
    Exploratory estimate of the post-event peak's half-life per group: fits an exponential
    decay to the trajectory AFTER the peak:

        y(t) = 100 + amplitude * exp(-lambda * t)

    (100 = baseline level, since value_col should already be normalized to baseline = 100,
    see rebase_to_baseline()). Half-life (in months) = ln(2) / lambda.

    CAUTION: with typically only ~10-20 post-peak data points per group, this is an
    exploratory, NOT a robust estimator. For groups without a genuine peak (e.g. the event
    didn't actually affect that group), the fit can produce absurd/unstable values (very
    short or very long "half-lives") - that's a symptom, not a bug: fitting a decay model to
    essentially flat data isn't meaningful. Sanity-check every estimate against its plot
    before citing it.

    WITH group_col = GROUP_KEYWORD_COL: this is arguably the most direct test of "does
    interest in keyword videos fade faster than the group's baseline" - compare the
    halflife_months of a group's "Keyword" row to its "kein Keyword" row. But also the step
    where the small-sample caveat above bites hardest, since "kein Keyword" post-event
    months usually have much more data (and a much smaller/less clean peak, if any) than
    "Keyword" months. A short keyword half-life next to a non-existent or unstable
    non-keyword half-life is not an apples-to-apples comparison - check both plots.
    """
    event_period = pd.Period(event_date, freq="M")
    results = []

    for group, gdf in monthly_rebased.groupby(group_col):
        gdf = gdf.sort_values(date_col).reset_index(drop=True)
        post = gdf[gdf[date_col].dt.to_period("M") >= event_period].reset_index(drop=True)

        if len(post) < 4:
            print(f"Warning: too little post-event data ({len(post)} months) for group "
                  f"'{group}' - skipping decay estimation.")
            continue

        peak_idx = post[value_col].idxmax()
        decay_part = post.loc[peak_idx:].reset_index(drop=True)

        if len(decay_part) < 3:
            print(f"Warning: too few data points after the peak ({len(decay_part)}) for "
                  f"group '{group}' - skipping decay fit.")
            continue

        t = np.arange(len(decay_part))
        y = decay_part[value_col].values
        amplitude_guess = y[0] - 100

        def decay_func(t, amplitude, lam):
            return 100 + amplitude * np.exp(-lam * t)

        try:
            popt, _ = curve_fit(decay_func, t, y, p0=[amplitude_guess, 0.3], maxfev=5000)
            amplitude, lam = popt
            halflife = np.log(2) / lam if lam > 0 else np.inf
            results.append({
                group_col: group,
                "peak_month": post.loc[peak_idx, date_col],
                "peak_value": post.loc[peak_idx, value_col],
                "halflife_months": halflife,
                "lambda": lam,
            })
        except RuntimeError:
            print(f"Decay fit did not converge for group '{group}'.")

    result_df = pd.DataFrame(results)
    if not result_df.empty:
        print("\n=== Estimated half-life of the post-event peak (exploratory!) ===")
        print(result_df.to_string(index=False))
    return result_df


# ======================================================================
# STEP 7: format shift - share of short videos
# ======================================================================

def format_shift_analysis(df, group_col, date_col="published_at", duration_col="duration",
                           short_threshold_seconds=SHORT_VIDEO_THRESHOLD_SECONDS):
    """
    Share of short videos (<= short_threshold_seconds, e.g. YouTube Shorts) per month and
    group. Checks whether the event triggered a shift towards shorter, more attention-grabbing
    formats - consistent with the idea that populist/emotionalized communication favours
    simplification.

    WITH group_col = GROUP_KEYWORD_COL: lets you check whether keyword videos specifically
    (rather than the group's output in general) shifted format around the event - e.g. Nahost
    content going short-form even if the rest of a channel's output didn't.
    """
    df = df.copy()
    df["duration_seconds"] = pd.to_timedelta(df[duration_col]).dt.total_seconds()
    df["is_short"] = df["duration_seconds"] <= short_threshold_seconds

    monthly = (
        df.groupby([pd.Grouper(key=date_col, freq="ME"), group_col])
        .agg(n_videos=("is_short", "size"), n_shorts=("is_short", "sum"))
        .reset_index()
    )
    monthly["short_share_pct"] = monthly["n_shorts"] / monthly["n_videos"] * 100
    return monthly


def plot_format_shift(monthly, group_col, date_col, plot_start, event_date, short_threshold_seconds):
    plot_group_trend(
        monthly, group_col, date_col, "short_share_pct",
        title=f"Share of short videos (<= {short_threshold_seconds}s) per month and group",
        ylabel="Share of short videos (%)",
        plot_start=plot_start, event_date=event_date,
        # no reference_line here: there's no meaningful "100%" baseline for this metric
    )


# ======================================================================
# STEP 8: engagement rate (if the columns are available)
# ======================================================================

def engagement_analysis(df, group_col, date_col="published_at"):
    """
    Engagement rate ((likes+comments)/views) per month and group - ONLY if matching columns
    exist in the metadata. These columns weren't used by earlier scripts - if they're named
    differently, adjust `candidate_columns` below. Engagement often carries more signal than
    raw views for the populism question (controversy/polarization shows up in comments more
    than in views).

    WITH group_col = GROUP_KEYWORD_COL: compares a group's Nahost-keyword engagement rate to
    its own non-keyword baseline - useful because engagement rate is somewhat self-normalizing
    across channels of different sizes, so this comparison is less distorted by "a few very
    large channels" than the raw-views comparisons above.
    """
    candidate_columns = {"likes": ["like_count", "likes"], "comments": ["comment_count", "comments"]}
    found = {}
    for key, candidates in candidate_columns.items():
        for c in candidates:
            if c in df.columns:
                found[key] = c
                break

    if not found:
        print("No engagement columns (like_count/comment_count or similar) found in the "
              "metadata - skipping the engagement analysis. If the data exists under a "
              "different name, update `candidate_columns` in engagement_analysis().")
        return None

    df = df.copy()
    df["engagement_count"] = 0
    for key, col in found.items():
        df["engagement_count"] += df[col].fillna(0)

    df["engagement_rate"] = df["engagement_count"] / df["view_count"].replace(0, np.nan)

    monthly = (
        df.groupby([pd.Grouper(key=date_col, freq="ME"), group_col])["engagement_rate"]
        .mean()
        .reset_index()
    )
    return monthly


def plot_engagement(monthly, group_col, date_col, plot_start, event_date):
    plot_group_trend(
        monthly, group_col, date_col, "engagement_rate",
        title="Engagement rate ((likes+comments)/views) per month and group",
        ylabel="Engagement rate",
        plot_start=plot_start, event_date=event_date,
    )


# ======================================================================
# MAIN
# ======================================================================

def main():
    # ---- STEP 1: Load data ----
    # Note: unlike success_trend_analysis.py, this script does NOT call
    # add_subscriber_normalization() - none of the analyses below use views_per_subscriber.
    df = load_video_data(METADATA_INPUT, METADATA_OUTPUT, CHANNEL_LIST_PATH, CLASSIFICATION_PATH,
                          MEDIA_PATH, START_DATE, END_DATE, INCLUDE_SHORTS)

    # ---- STEP 2: Channel-count transparency (plain ideology groups, for reference) ----
    print_channel_counts(df, GROUP_COL)

    # ---- STEP 2b: Keyword flag + combined "group x keyword" grouping column ----
    # Requires KEYWORDS to be filled in above (raises otherwise).
    df = flag_keyword_videos(df)
    df = add_group_keyword_combo(df, GROUP_COL)
    print_channel_counts(df, GROUP_KEYWORD_COL)
    print_video_counts(df, GROUP_KEYWORD_COL)

    # From here on, every analysis runs on the combined group x keyword column, so each
    # ideology group is split into its "Keyword" and "kein Keyword" trajectory. Swap back to
    # GROUP_COL below if you ever want the original ideology-only versions instead.
    analysis_group_col = GROUP_KEYWORD_COL

    # ---- STEP 3: Views decomposition (more uploads vs. better-performing uploads) ----
    monthly_decomposed = decompose_views(df, analysis_group_col)
    plot_views_decomposition(monthly_decomposed, analysis_group_col, "published_at", PLOT_START_DATE,
                              EVENT_DATE, BASELINE_MONTH, BASELINE_WINDOW_MONTHS)

    # ---- STEP 4: Organic-growth counterfactual (pre-event trend instead of a fixed baseline) ----
    # Adjust PRE_EVENT_TREND_MONTHS above to change how many months the trend is fit on.
    df_trend = trend_extrapolated_baseline(monthly_decomposed, analysis_group_col, EVENT_DATE,
                                            PRE_EVENT_TREND_MONTHS, value_col="total_views")
    if not df_trend.empty:
        plot_trend_extrapolated(df_trend, analysis_group_col, "published_at", PLOT_START_DATE, EVENT_DATE)

    # ---- STEP 5: Interrupted Time Series regression ----
    its_model = run_interrupted_time_series(monthly_decomposed, analysis_group_col, EVENT_DATE,
                                             value_col="total_views")

    # ---- STEP 6: Decay / half-life of the post-event peak (exploratory) ----
    monthly_rebased = rebase_to_baseline(monthly_decomposed, analysis_group_col, "total_views",
                                          "published_at", BASELINE_MONTH, BASELINE_WINDOW_MONTHS)
    halflife_df = estimate_decay_halflife(monthly_rebased, analysis_group_col, EVENT_DATE)

    # ---- STEP 7: Format shift (share of short videos) ----
    monthly_format = format_shift_analysis(df, analysis_group_col)
    plot_format_shift(monthly_format, analysis_group_col, "published_at", PLOT_START_DATE, EVENT_DATE,
                       SHORT_VIDEO_THRESHOLD_SECONDS)

    # ---- STEP 8: Engagement analysis (if the data is available) ----
    monthly_engagement = engagement_analysis(df, analysis_group_col)
    if monthly_engagement is not None:
        plot_engagement(monthly_engagement, analysis_group_col, "published_at", PLOT_START_DATE, EVENT_DATE)

    # ---- Placeholders for later (data not available yet) ----
    # NLP linkage: once sentiment/framing/populism scores per video exist from the LLM
    # classification (see success_sentiment_analysis.py), this is the place to check whether
    # framing intensity correlates with views - independent of channel ideology.
    #
    # Subscriber GROWTH (rather than just a current snapshot) would be a stronger indicator
    # of audience migration than raw views, but isn't available yet (only one subscriber
    # count exists, no historical series).

    return its_model, halflife_df


if __name__ == "__main__":
    main()
"""
success_advanced_analysis.py

Deeper analyses of channel performance around the 7 Oct 2023 event, complementing
success_trend_analysis.py:

    STEP 1: Load data
    STEP 2: Channel-count transparency per group
    STEP 3: Views decomposition (more uploads vs. better-performing uploads)
    STEP 4: Pre-event trend extrapolation ("organic growth" counterfactual baseline)
    STEP 5: Interrupted Time Series regression (formal significance test, group interactions)
    STEP 6: Decay / half-life of the post-event peak (exploratory)
    STEP 7: Format shift - share of short videos over time
    STEP 8: Engagement rate (likes+comments per view), if the columns are available

NOT included (data not available yet, see comments at the end of main()):
    - Linking these metrics to the sentiment/framing/populism LLM classification
    - Subscriber GROWTH (only a current snapshot exists, no historical series)

NEW DEPENDENCIES compared to success_trend_analysis.py:
    pip install statsmodels scipy --break-system-packages
    (scipy is likely already installed as a seaborn/pandas dependency; statsmodels probably not)

Shared building blocks live in success_data_utils.py and success_plot_utils.py - both must be
importable (same folder or on PYTHONPATH) when running this script.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import statsmodels.formula.api as smf
from scipy.optimize import curve_fit

from youtube_code.config import RAW, CHANNEL_LISTS, SAMPLES, OUTPUT_GEMINI

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
START_DATE = "2022-10"
END_DATE = "2025-12"

# --- Grouping column ---
GROUP_COL = "ideology_group"

# --- STEP 4: pre-event trend extrapolation ---
PRE_EVENT_TREND_MONTHS = 6   # number of months BEFORE the event used to fit the linear trend

# --- STEP 5: ITS regression ---
ITS_HAC_LAGS = 3             # Newey-West HAC lags for autocorrelation-robust standard errors

# --- STEP 7: format shift ---
SHORT_VIDEO_THRESHOLD_SECONDS = 60   # YouTube's usual Shorts definition (adjust if needed)


# ======================================================================
# STEP 2: channel-count transparency
# ======================================================================

def print_channel_counts(df, group_col):
    """
    Print how many channels make up each group. Important context for interpreting the
    equal-/sqrt-weighted indices from success_trend_analysis.py: a noisy median computed from
    3 channels is far less reliable than one computed from 40, even though both plots look
    equally "official".
    """
    counts = df.groupby(group_col)["channel_title"].nunique().reset_index(name="n_channels")
    print("\n=== Number of channels per group ===")
    print(counts.to_string(index=False))
    return counts


# ======================================================================
# STEP 3: views decomposition
# ======================================================================

def decompose_views(df, group_col, date_col="published_at", view_col="view_count"):
    """
    Split total monthly views per group into number of videos and views per video. This
    distinguishes two different stories: a rise driven by MORE uploads (posting behaviour)
    vs. a rise driven by BETTER-PERFORMING uploads (audience interest).
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
    event, each interacted with the ideology group:

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
                          START_DATE, END_DATE)

    # ---- STEP 2: Channel-count transparency ----
    print_channel_counts(df, GROUP_COL)

    # ---- STEP 3: Views decomposition (more uploads vs. better-performing uploads) ----
    monthly_decomposed = decompose_views(df, GROUP_COL)
    plot_views_decomposition(monthly_decomposed, GROUP_COL, "published_at", PLOT_START_DATE,
                              EVENT_DATE, BASELINE_MONTH, BASELINE_WINDOW_MONTHS)

    # ---- STEP 4: Organic-growth counterfactual (pre-event trend instead of a fixed baseline) ----
    # Adjust PRE_EVENT_TREND_MONTHS above to change how many months the trend is fit on.
    df_trend = trend_extrapolated_baseline(monthly_decomposed, GROUP_COL, EVENT_DATE,
                                            PRE_EVENT_TREND_MONTHS, value_col="total_views")
    if not df_trend.empty:
        plot_trend_extrapolated(df_trend, GROUP_COL, "published_at", PLOT_START_DATE, EVENT_DATE)

    # ---- STEP 5: Interrupted Time Series regression ----
    its_model = run_interrupted_time_series(monthly_decomposed, GROUP_COL, EVENT_DATE,
                                             value_col="total_views")

    # ---- STEP 6: Decay / half-life of the post-event peak (exploratory) ----
    monthly_rebased = rebase_to_baseline(monthly_decomposed, GROUP_COL, "total_views",
                                          "published_at", BASELINE_MONTH, BASELINE_WINDOW_MONTHS)
    halflife_df = estimate_decay_halflife(monthly_rebased, GROUP_COL, EVENT_DATE)

    # ---- STEP 7: Format shift (share of short videos) ----
    monthly_format = format_shift_analysis(df, GROUP_COL)
    plot_format_shift(monthly_format, GROUP_COL, "published_at", PLOT_START_DATE, EVENT_DATE,
                       SHORT_VIDEO_THRESHOLD_SECONDS)

    # ---- STEP 8: Engagement analysis (if the data is available) ----
    monthly_engagement = engagement_analysis(df, GROUP_COL)
    if monthly_engagement is not None:
        plot_engagement(monthly_engagement, GROUP_COL, "published_at", PLOT_START_DATE, EVENT_DATE)

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

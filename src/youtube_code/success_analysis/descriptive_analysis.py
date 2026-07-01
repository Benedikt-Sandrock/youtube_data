"""
nahost_descriptive_analysis.py

Deskriptive Zeitreihenanalyse zur politischen YouTube-Landschaft in Deutschland
mit Fokus auf Nahost-Keyword-Videos.

Erstellt automatisch alle Grafiken getrennt nach:
    1. ideology_group
    2. type (Medientyp)

Figures pro Gruppierung:
    Figure 1: Agenda-Setting
        A) Anteil Keyword-Videos an allen Videos
        B) Gesamtzahl aller Videos

    Figure 2: Populismus
        A) Durchschnittlicher Populismus-Score der Keyword-Videos
           + horizontale Baseline aus populism_channel_mean der jeweiligen Gruppe
        B) Differenz des Video-Populismus zur jeweiligen Gruppen-Baseline

    Figure 3: Erfolg
        A) Gesamtviews der Keyword-Videos
        B) Mean Views pro Keyword-Video
        C) Median Views pro Keyword-Video
        D) Anteil der Keyword-Views an allen Views

Zusätzlich werden aggregierte CSVs gespeichert:
    - channel_period_panel_*.csv
    - group_period_summary_*.csv

Annahme:
    Der Video-Populismus-Datensatz enthält mindestens:
        video_id
        populism_score

Benötigt:
    pandas, numpy, matplotlib, seaborn, openpyxl
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

from youtube_code.config import RAW, CHANNEL_LISTS, SAMPLES, OUTPUT_GEMINI, KEYWORDS, EXTERNAL
from success_data_utils import load_video_data

# =============================================================================
# CONFIG
# =============================================================================

EVENT_DATE = "2023-10-07"

# "M" = monatlich, "W" = wöchentlich
TIME_UNIT = "M"

# Gruppierungen, die nacheinander geplottet werden
GROUPINGS = ["ideology_group", "type"]

# Datenquellen, analog zu deinen bestehenden Skripten
METADATA_INPUT = RAW / "video_metadata_total.jsonl"
METADATA_OUTPUT = SAMPLES / "combined" / "video_metadata_relevant.csv"
CHANNEL_LIST_PATH = CHANNEL_LISTS / "combined" / "channel_list.json"
CLASSIFICATION_PATH = OUTPUT_GEMINI / "channel_results_051.xlsx"
MEDIA_PATH = EXTERNAL / "media_type.xlsx"

# Zeitraum
START_DATE = "2022-01"
END_DATE = "2026-03"
PLOT_START_DATE = "2022-01-01"

# Shorts einschließen?
INCLUDE_SHORTS = False

# Titelspalte für Keyword-Matching
TITLE_COL = "title"
KEYWORD_COL = "has_keyword"

# Pfad zum Video-Populismus-Datensatz.
# Muss mindestens Spalten enthalten: video_id, populism_score
#
# Beispiel:
# KEYWORD_POPULISM_PATH = OUTPUT_GEMINI / "nahost_video_populism_scores.xlsx"
# KEYWORD_POPULISM_PATH = SAMPLES / "combined" / "keyword_video_populism_scores.csv"
KEYWORD_POPULISM_PATH = OUTPUT_GEMINI / "keyword_videos_populism.csv"

VIDEO_ID_COL = "video_id"
VIDEO_POPULISM_COL = "populism_score"
CHANNEL_BASELINE_COL = "populism_channel_mean"

VIEW_COL = "view_count"
DATE_COL = "published_at"
CHANNEL_COL = "channel_title"

# Output
OUTPUT_DIR = OUTPUT_GEMINI / "nahost_descriptive_figures"
SAVE_FIGURES = True
SHOW_FIGURES = False
FIG_DPI = 300

# Darstellung
SMOOTH = False
SMOOTH_WINDOW = 3

# Bei Views können große Unterschiede auftreten.
# True = View-Panels mit log-y-Achse darstellen.
LOG_SCALE_VIEW_PANELS = False

# Mindestanzahl Keyword-Videos pro Gruppe x Zeitraum, damit Populismuswerte geplottet werden.
# Werte darunter bleiben im Plot sichtbar, können aber optional als NaN gesetzt werden.
MIN_KEYWORD_VIDEOS_FOR_POPULISM = 1

# Optional: feste Reihenfolge für Gruppen.
# Wenn None, wird alphabetisch bzw. nach Kategorie-Reihenfolge sortiert.
GROUP_ORDER = {
    "ideology_group": None,
    "type": None,
}


# =============================================================================
# HILFSFUNKTIONEN: VALIDIERUNG & LOADING
# =============================================================================

def require_columns(df: pd.DataFrame, required: Iterable[str], df_name: str) -> None:
    """Raise a helpful error if required columns are missing."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"{df_name} enthält nicht alle benötigten Spalten. "
            f"Fehlend: {missing}. Vorhanden: {list(df.columns)}"
        )


def get_time_freq(time_unit: str) -> str:
    """
    Convert user-friendly TIME_UNIT to pandas Grouper frequency.

    M  -> month end
    W  -> week ending Sunday
    """
    time_unit = time_unit.upper().strip()
    if time_unit in {"M", "MONTH", "MONTHLY"}:
        return "ME"
    if time_unit in {"W", "WEEK", "WEEKLY"}:
        return "W-SUN"
    raise ValueError("TIME_UNIT muss 'M' oder 'W' sein.")


def get_freqs(time_unit: str) -> tuple[str, str]:
    """
    Returns:
        period_freq: for .dt.to_period()
        range_freq: for pd.date_range() / Grouper()
    """
    time_unit = time_unit.upper().strip()

    if time_unit in {"M", "MONTH", "MONTHLY"}:
        return "M", "ME"

    if time_unit in {"W", "WEEK", "WEEKLY"}:
        return "W-SUN", "W-SUN"

    raise ValueError("TIME_UNIT muss 'M' oder 'W' sein.")


def get_time_label(time_unit: str) -> str:
    time_unit = time_unit.upper().strip()
    if time_unit.startswith("M"):
        return "Monat"
    if time_unit.startswith("W"):
        return "Woche"
    return "Zeitraum"


def safe_group_label(value) -> str:
    """Make group labels safe for filenames."""
    text = str(value)
    text = text.replace("/", "-").replace("\\", "-")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Za-z0-9_.-]+", "", text)
    return text


def read_table(path: Path) -> pd.DataFrame:
    """Read CSV, Excel, JSONL, or JSON into a DataFrame."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Datei nicht gefunden: {path}\n"
            "Bitte KEYWORD_POPULISM_PATH oben im Skript anpassen."
        )

    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".jsonl":
        return pd.read_json(path, lines=True)
    if suffix == ".json":
        return pd.read_json(path)

    raise ValueError(
        f"Unbekanntes Dateiformat für {path}. "
        "Unterstützt werden .xlsx, .xls, .csv, .jsonl, .json."
    )


def load_video_populism_scores(path: Path) -> pd.DataFrame:
    """
    Load video-level populism scores.

    Expected columns:
        video_id
        populism_score
    """
    scores = read_table(path)
    require_columns(scores, [VIDEO_ID_COL, VIDEO_POPULISM_COL], "Video-Populismus-Datensatz")

    scores = scores[[VIDEO_ID_COL, VIDEO_POPULISM_COL]].copy()
    scores[VIDEO_ID_COL] = scores[VIDEO_ID_COL].astype(str)
    scores[VIDEO_POPULISM_COL] = pd.to_numeric(scores[VIDEO_POPULISM_COL], errors="coerce")

    before = len(scores)
    scores = scores.dropna(subset=[VIDEO_ID_COL, VIDEO_POPULISM_COL])
    scores = scores.drop_duplicates(subset=[VIDEO_ID_COL], keep="last")
    after = len(scores)

    if after < before:
        print(f"[Info] Video-Populismus: {before - after} leere/duplizierte Zeilen entfernt.")

    return scores


def load_channel_populism_baseline(classification_path: Path) -> pd.DataFrame:
    """
    Load channel-level populism baseline from classification file.

    Expected columns:
        channel_title
        populism_channel_mean
    """
    class_df = pd.read_excel(classification_path)
    require_columns(class_df, [CHANNEL_COL, CHANNEL_BASELINE_COL], "Channel-Klassifikation")

    out = class_df[[CHANNEL_COL, CHANNEL_BASELINE_COL]].copy()
    out[CHANNEL_BASELINE_COL] = pd.to_numeric(out[CHANNEL_BASELINE_COL], errors="coerce")
    out = out.drop_duplicates(subset=[CHANNEL_COL], keep="last")
    return out


def load_and_prepare_base_data() -> pd.DataFrame:
    """
    Load metadata, merge channel classifications, add channel-level populism baseline,
    flag keyword videos, and merge video-level populism scores.
    """
    print("\n=== Lade Videodaten ===")
    df = load_video_data(
        METADATA_INPUT,
        METADATA_OUTPUT,
        CHANNEL_LIST_PATH,
        CLASSIFICATION_PATH,
        MEDIA_PATH,
        START_DATE,
        END_DATE,
        INCLUDE_SHORTS,
    )

    require_columns(
        df,
        [VIDEO_ID_COL, CHANNEL_COL, DATE_COL, TITLE_COL, VIEW_COL, "ideology_group", "type"],
        "Videodaten nach load_video_data()",
    )

    df = df.copy()
    df[VIDEO_ID_COL] = df[VIDEO_ID_COL].astype(str)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL]).dt.tz_localize(None)
    df[VIEW_COL] = pd.to_numeric(df[VIEW_COL], errors="coerce").fillna(0)

    # Channel-Baseline zusätzlich mergen, weil load_video_data sie in deinen Utils
    # bisher nicht in df übernimmt.
    print("\n=== Merge Channel-Populismus-Baseline ===")
    channel_baseline = load_channel_populism_baseline(CLASSIFICATION_PATH)
    df = df.merge(channel_baseline, on=CHANNEL_COL, how="left")

    missing_baseline_channels = (
        df.loc[df[CHANNEL_BASELINE_COL].isna(), CHANNEL_COL]
        .dropna()
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    if missing_baseline_channels:
        print(
            f"[Warnung] Für {len(missing_baseline_channels)} Kanäle fehlt "
            f"{CHANNEL_BASELINE_COL}. Beispiele: {missing_baseline_channels[:10]}"
        )

    # Keyword-Flag
    print("\n=== Flagge Keyword-Videos ===")
    if not KEYWORDS:
        raise ValueError(
            "KEYWORDS ist leer. Bitte KEYWORDS in youtube_code.config definieren "
            "oder im Skript explizit setzen."
        )

    pattern = "|".join(re.escape(str(kw)) for kw in KEYWORDS)
    df[KEYWORD_COL] = df[TITLE_COL].astype(str).str.contains(
        pattern,
        case=False,
        na=False,
        regex=True,
    )

    n_keyword = int(df[KEYWORD_COL].sum())
    print(
        f"Keyword-Videos: {n_keyword:,} / {len(df):,} "
        f"({df[KEYWORD_COL].mean() * 100:.2f}%)"
    )

    print("\nMatches pro Keyword, Mehrfachtreffer möglich:")
    for kw in KEYWORDS:
        n = df[TITLE_COL].astype(str).str.contains(
            re.escape(str(kw)),
            case=False,
            na=False,
            regex=True,
        ).sum()
        print(f"  {kw}: {int(n):,}")

    # Video-Populismus mergen
    print("\n=== Merge Video-Populismus-Scores ===")
    scores = load_video_populism_scores(KEYWORD_POPULISM_PATH)
    df = df.merge(scores, on=VIDEO_ID_COL, how="left")
    df["is_unpolitical"] = df[VIDEO_POPULISM_COL] == -1
    df["is_political_score"] = df[VIDEO_POPULISM_COL] >= 0
    df["populism_score_clean"] = df[VIDEO_POPULISM_COL].where(
        df[VIDEO_POPULISM_COL] >= 0, np.nan,
    )

    keyword_without_score = df[df[KEYWORD_COL] & df[VIDEO_POPULISM_COL].isna()]
    if not keyword_without_score.empty:
        print(
            f"[Warnung] {len(keyword_without_score):,} Keyword-Videos haben keinen "
            f"{VIDEO_POPULISM_COL}. Diese fehlen in Populismus-Figure 2."
        )
        missing_path = OUTPUT_DIR / "keyword_videos_missing_populism_score.csv"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        keyword_without_score[
            [VIDEO_ID_COL, CHANNEL_COL, DATE_COL, TITLE_COL, "ideology_group", "type"]
        ].to_csv(missing_path, index=False)
        print(f"Fehlende Scores gespeichert unter: {missing_path}")

    return df


# =============================================================================
# AGGREGATION
# =============================================================================

def make_complete_period_group_grid(
    df: pd.DataFrame,
    group_col: str,
    period_freq: str,
    date_col: str = DATE_COL,
) -> pd.DataFrame:
    """Create complete period x group grid with the same timestamp convention as .dt.to_period(...).dt.to_timestamp()."""
    plot_df = df.dropna(subset=[group_col]).copy()
    if plot_df.empty:
        raise ValueError(f"Keine Daten mit gültigem group_col={group_col}.")

    min_period = plot_df[date_col].min().to_period(period_freq)
    max_period = plot_df[date_col].max().to_period(period_freq)

    periods = pd.period_range(
        start=min_period,
        end=max_period,
        freq=period_freq,
    ).to_timestamp()

    groups = get_groups(plot_df, group_col)

    grid = pd.MultiIndex.from_product(
        [periods, groups],
        names=["period", group_col],
    ).to_frame(index=False)

    grid[group_col] = grid[group_col].astype(str)

    return grid


def get_groups(df: pd.DataFrame, group_col: str) -> list:
    """Return stable group ordering."""
    explicit_order = GROUP_ORDER.get(group_col)
    existing = df[group_col].dropna()

    if explicit_order is not None:
        return [g for g in explicit_order if g in set(existing.astype(str)) or g in set(existing)]

    if pd.api.types.is_categorical_dtype(existing):
        return [g for g in existing.cat.categories if g in set(existing)]

    return sorted(existing.astype(str).unique())


def build_channel_period_panel(
    df: pd.DataFrame,
    group_col: str,
    freq: str,
    date_col: str = DATE_COL,
) -> pd.DataFrame:
    """
    Build channel x period panel.

    This is useful for later regressions:
        channel_title x period x group

    Main descriptive figures use group-level summaries derived consistently from this logic.
    """
    work = df.dropna(subset=[group_col]).copy()
    work["period"] = work[date_col].dt.to_period(freq).dt.to_timestamp()

    # Insgesamt pro Kanal x Periode
    total = (
        work.groupby(["period", CHANNEL_COL, group_col], observed=True)
        .agg(
            n_videos=(VIDEO_ID_COL, "count"),
            total_views=(VIEW_COL, "sum"),
            channel_baseline=(CHANNEL_BASELINE_COL, "first"),
        )
        .reset_index()
    )

    # Keyword pro Kanal x Periode
    kw = work[work[KEYWORD_COL]].copy()
    keyword = (
        kw.groupby(["period", CHANNEL_COL, group_col], observed=True)
        .agg(
            n_keyword_videos=(VIDEO_ID_COL, "count"),
            keyword_views=(VIEW_COL, "sum"),
            mean_keyword_views=(VIEW_COL, "mean"),
            median_keyword_views=(VIEW_COL, "median"),
            mean_keyword_populism=(VIDEO_POPULISM_COL, "mean"),
            n_keyword_populism=(VIDEO_POPULISM_COL, lambda s: s.notna().sum()),
        )
        .reset_index()
    )

    panel = total.merge(
        keyword,
        on=["period", CHANNEL_COL, group_col],
        how="left",
    )

    fill_zero_cols = ["n_keyword_videos", "keyword_views"]
    panel[fill_zero_cols] = panel[fill_zero_cols].fillna(0)

    panel["share_keyword_videos"] = np.where(
        panel["n_videos"] > 0,
        panel["n_keyword_videos"] / panel["n_videos"],
        np.nan,
    )
    panel["share_keyword_views"] = np.where(
        panel["total_views"] > 0,
        panel["keyword_views"] / panel["total_views"],
        np.nan,
    )
    panel["has_keyword_video"] = panel["n_keyword_videos"] > 0

    return panel


def build_group_period_summary(
    df: pd.DataFrame,
    group_col: str,
    period_freq: str,
    range_freq: str,
    date_col: str = DATE_COL,
) -> pd.DataFrame:
    """
    Build period x group summary for all requested figures.

    Metrics:
        n_videos
        n_keyword_videos
        share_keyword_videos
        n_active_channels
        n_keyword_channels
        share_keyword_channels

        mean_keyword_populism
        group_populism_baseline
        keyword_populism_minus_baseline

        total_views
        keyword_views
        mean_keyword_views
        median_keyword_views
        share_keyword_views
    """
    work = df.dropna(subset=[group_col]).copy()
    work[group_col] = work[group_col].astype(str)
    work["period"] = work[date_col].dt.to_period(period_freq).dt.to_timestamp()
    # Alle Videos
    total = (
        work.groupby(["period", group_col], observed=True)
        .agg(
            n_videos=(VIDEO_ID_COL, "count"),
            total_views=(VIEW_COL, "sum"),
            n_active_channels=(CHANNEL_COL, "nunique"),
        )
        .reset_index()
    )

    # Keyword-Videos
    kw = work[work[KEYWORD_COL]].copy()
    keyword = (
        kw.groupby(["period", group_col], observed=True)
        .agg(
            n_keyword_videos=(VIDEO_ID_COL, "count"),
            keyword_views=(VIEW_COL, "sum"),
            mean_keyword_views=(VIEW_COL, "mean"),
            median_keyword_views=(VIEW_COL, "median"),
            mean_keyword_populism=("populism_score_clean", "mean"),
            n_keyword_populism=(VIDEO_POPULISM_COL, lambda s: s.notna().sum()),
            n_keyword_channels=(CHANNEL_COL, "nunique"),
            n_unpolitical_keyword=("is_unpolitical", "sum"),
        )
        .reset_index()
    )

    # Baseline: ungewichteter Durchschnitt der Kanäle einer Gruppe
    # Ein Kanal zählt einmal, nicht pro Video.
    channel_group = (
        work[[CHANNEL_COL, group_col, CHANNEL_BASELINE_COL]]
        .drop_duplicates(subset=[CHANNEL_COL, group_col])
        .dropna(subset=[CHANNEL_BASELINE_COL])
    )
    baseline = (
        channel_group.groupby(group_col, observed=True)[CHANNEL_BASELINE_COL]
        .mean()
        .reset_index(name="group_populism_baseline")
    )

    summary = total.merge(keyword, on=["period", group_col], how="left")
    summary = summary.merge(baseline, on=group_col, how="left")

    fill_zero_cols = [
        "n_keyword_videos",
        "keyword_views",
        "n_keyword_channels",
        "n_keyword_populism",
    ]
    summary[fill_zero_cols] = summary[fill_zero_cols].fillna(0)

    summary["share_keyword_videos"] = np.where(
        summary["n_videos"] > 0,
        summary["n_keyword_videos"] / summary["n_videos"],
        np.nan,
    )
    summary["share_keyword_views"] = np.where(
        summary["total_views"] > 0,
        summary["keyword_views"] / summary["total_views"],
        np.nan,
    )
    summary["share_keyword_channels"] = np.where(
        summary["n_active_channels"] > 0,
        summary["n_keyword_channels"] / summary["n_active_channels"],
        np.nan,
    )
    summary["keyword_populism_minus_baseline"] = (
        summary["mean_keyword_populism"] - summary["group_populism_baseline"]
    )
    summary["share_unpolitical_all_videos"] = (
        summary["n_unpolitical_keyword"] / summary["n_videos"]
    )

    # Optional: sehr dünne Populismus-Zellen ausblenden
    if MIN_KEYWORD_VIDEOS_FOR_POPULISM > 1:
        thin = summary["n_keyword_populism"] < MIN_KEYWORD_VIDEOS_FOR_POPULISM
        summary.loc[thin, ["mean_keyword_populism", "keyword_populism_minus_baseline"]] = np.nan

    # Complete grid: fehlende Perioden/Gruppen explizit ergänzen
    grid = make_complete_period_group_grid(work, group_col, period_freq, date_col="period")
    summary = grid.merge(summary, on=["period", group_col], how="left")

    zero_after_grid = [
        "n_videos",
        "total_views",
        "n_active_channels",
        "n_keyword_videos",
        "keyword_views",
        "n_keyword_channels",
        "n_keyword_populism",
    ]
    summary[zero_after_grid] = summary[zero_after_grid].fillna(0)

    # Baseline nach Grid-Merge erneut ergänzen
    summary = summary.drop(columns=["group_populism_baseline"], errors="ignore")
    summary = summary.merge(baseline, on=group_col, how="left")

    summary["share_keyword_videos"] = np.where(
        summary["n_videos"] > 0,
        summary["n_keyword_videos"] / summary["n_videos"],
        np.nan,
    )
    summary["share_keyword_views"] = np.where(
        summary["total_views"] > 0,
        summary["keyword_views"] / summary["total_views"],
        np.nan,
    )
    summary["share_keyword_channels"] = np.where(
        summary["n_active_channels"] > 0,
        summary["n_keyword_channels"] / summary["n_active_channels"],
        np.nan,
    )
    summary["keyword_populism_minus_baseline"] = (
        summary["mean_keyword_populism"] - summary["group_populism_baseline"]
    )

    return summary.sort_values(["period", group_col]).reset_index(drop=True)


# =============================================================================
# PLOTTING
# =============================================================================

def apply_smoothing(
    df: pd.DataFrame,
    group_col: str,
    value_col: str,
    window: int = SMOOTH_WINDOW,
) -> pd.DataFrame:
    """Apply centered rolling mean per group."""
    if not SMOOTH:
        return df

    out = df.copy()
    out[value_col] = (
        out.groupby(group_col, observed=True)[value_col]
        .transform(lambda s: s.rolling(window=window, min_periods=1, center=True).mean())
    )
    return out


def percent_formatter(x, pos=None) -> str:
    return f"{x:.0%}"


def compact_number_formatter(x, pos=None) -> str:
    if pd.isna(x):
        return ""
    abs_x = abs(x)
    if abs_x >= 1_000_000_000:
        return f"{x / 1_000_000_000:.1f}B"
    if abs_x >= 1_000_000:
        return f"{x / 1_000_000:.1f}M"
    if abs_x >= 1_000:
        return f"{x / 1_000:.0f}K"
    return f"{x:.0f}"


def add_event_line(ax: plt.Axes) -> None:
    ax.axvline(
        pd.to_datetime(EVENT_DATE),
        color="grey",
        linestyle=":",
        linewidth=1.4,
        label="7. Oktober 2023",
        zorder=0,
    )


def style_time_axis(ax: plt.Axes, time_label: str) -> None:
    ax.set_xlabel(time_label)
    ax.tick_params(axis="x", rotation=45)


def plot_line_metric(
    ax: plt.Axes,
    data: pd.DataFrame,
    group_col: str,
    y_col: str,
    title: str,
    ylabel: str,
    palette: dict,
    y_formatter: Optional[mticker.Formatter] = None,
    log_scale: bool = False,
    time_label: str = "Zeit",
) -> None:
    """Generic line plot for one metric."""
    plot_df = data.copy()
    plot_df = apply_smoothing(plot_df, group_col, y_col)

    sns.lineplot(
        data=plot_df,
        x="period",
        y=y_col,
        hue=group_col,
        hue_order=list(palette.keys()),
        palette=palette,
        marker="o",
        linewidth=2,
        markersize=4,
        ax=ax,
        legend=False,
    )

    add_event_line(ax)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_ylabel(ylabel)
    style_time_axis(ax, time_label)

    if y_formatter is not None:
        ax.yaxis.set_major_formatter(y_formatter)

    if log_scale:
        positive_values = plot_df[y_col].dropna()
        positive_values = positive_values[positive_values > 0]
        if not positive_values.empty:
            ax.set_yscale("log")


def add_shared_legend(fig: plt.Figure, axes: Iterable[plt.Axes], palette: dict) -> None:
    """Create one shared legend below figure."""
    handles = [
        plt.Line2D(
            [],
            [],
            color=color,
            marker="o",
            linewidth=2,
            markersize=5,
            label=str(group),
        )
        for group, color in palette.items()
    ]
    handles.append(
        plt.Line2D(
            [],
            [],
            color="grey",
            linestyle=":",
            linewidth=1.4,
            label="7. Oktober 2023",
        )
    )

    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.01),
        ncol=min(len(handles), 4),
        frameon=True,
        fontsize=9,
    )


def save_or_show(fig: plt.Figure, output_path_base: Path) -> None:
    """Save and/or show figure."""
    if SAVE_FIGURES:
        output_path_base.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path_base.with_suffix(".png"), dpi=FIG_DPI, bbox_inches="tight")
        fig.savefig(output_path_base.with_suffix(".pdf"), bbox_inches="tight")
        print(f"Gespeichert: {output_path_base.with_suffix('.png')}")
        print(f"Gespeichert: {output_path_base.with_suffix('.pdf')}")

    if SHOW_FIGURES:
        plt.show()
    else:
        plt.close(fig)


def make_palette(groups: list) -> dict:
    colors = sns.color_palette("tab10", n_colors=max(len(groups), 3))
    return dict(zip(groups, colors))


def filter_plot_start(summary: pd.DataFrame) -> pd.DataFrame:
    start = pd.to_datetime(PLOT_START_DATE)
    return summary[summary["period"] >= start].copy()


def plot_figure_1_agenda(
    summary: pd.DataFrame,
    group_col: str,
    time_label: str,
    output_dir: Path,
) -> None:
    """
    Figure 1:
        A) Share Keyword Videos
        B) Total Uploads
    """
    plot_df = filter_plot_start(summary)
    groups = get_groups(plot_df, group_col)
    palette = make_palette(groups)

    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)

    plot_line_metric(
        axes[0],
        plot_df,
        group_col,
        "share_keyword_videos",
        "A) Anteil Keyword-Videos an allen Videos",
        "Keyword-Videos / alle Videos",
        palette,
        y_formatter=mticker.FuncFormatter(percent_formatter),
        time_label=time_label,
    )

    plot_line_metric(
        axes[1],
        plot_df,
        group_col,
        "n_videos",
        "B) Gesamtzahl aller Videos",
        "Alle Videos",
        palette,
        y_formatter=mticker.FuncFormatter(compact_number_formatter),
        time_label=time_label,
    )

    fig.suptitle(
        f"Figure 1: Agenda-Setting über die Zeit — gruppiert nach {group_col}",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    add_shared_legend(fig, axes, palette)
    fig.tight_layout(rect=[0, 0.08, 1, 0.95])

    save_or_show(fig, output_dir / f"figure_1_agenda_{group_col}_{TIME_UNIT}")


def plot_figure_2_populism(
    summary: pd.DataFrame,
    group_col: str,
    time_label: str,
    output_dir: Path,
) -> None:
    """
    Figure 2:
        A) Mean populism in keyword videos + baseline lines
        B) Difference to group baseline
    """
    plot_df = filter_plot_start(summary)
    groups = get_groups(plot_df, group_col)
    palette = make_palette(groups)

    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)

    # Panel A: mean keyword populism
    plot_line_metric(
        axes[0],
        plot_df,
        group_col,
        "mean_keyword_populism",
        "A) Durchschnittlicher Populismus in Keyword-Videos",
        "Ø Populismus-Score",
        palette,
        time_label=time_label,
    )

    # Baseline horizontal lines per group
    baseline_df = (
        plot_df[[group_col, "group_populism_baseline"]]
        .dropna()
        .drop_duplicates(subset=[group_col])
    )
    for _, row in baseline_df.iterrows():
        group = row[group_col]
        baseline = row["group_populism_baseline"]
        if pd.notna(baseline) and group in palette:
            axes[0].axhline(
                baseline,
                color=palette[group],
                linestyle="--",
                linewidth=1.4,
                alpha=0.75,
            )

    axes[0].text(
        0.01,
        0.02,
        "Gestrichelte Linien = Gruppen-Baseline aus populism_channel_mean",
        transform=axes[0].transAxes,
        fontsize=9,
        alpha=0.8,
    )

    # Panel B: difference from baseline
    plot_line_metric(
        axes[1],
        plot_df,
        group_col,
        "keyword_populism_minus_baseline",
        "B) Abweichung vom üblichen Channel-Populismus der Gruppe",
        "Ø Video-Populismus − Gruppen-Baseline",
        palette,
        time_label=time_label,
    )
    axes[1].axhline(0, color="black", linestyle="--", linewidth=1.1, alpha=0.8)

    fig.suptitle(
        f"Figure 2: Populismus in Nahost-Keyword-Videos — gruppiert nach {group_col}",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    add_shared_legend(fig, axes, palette)
    fig.tight_layout(rect=[0, 0.08, 1, 0.95])

    save_or_show(fig, output_dir / f"figure_2_populism_{group_col}_{TIME_UNIT}")


def plot_figure_3_success(
    summary: pd.DataFrame,
    group_col: str,
    time_label: str,
    output_dir: Path,
) -> None:
    """
    Figure 3:
        A) Total keyword views
        B) Mean views per keyword video
        C) Median views per keyword video
        D) Share keyword views / all views
    """
    plot_df = filter_plot_start(summary)
    groups = get_groups(plot_df, group_col)
    palette = make_palette(groups)

    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(17, 10), sharex=True)
    axes_flat = axes.flatten()

    plot_line_metric(
        axes_flat[0],
        plot_df,
        group_col,
        "keyword_views",
        "A) Gesamtviews der Keyword-Videos",
        "Views Keyword-Videos",
        palette,
        y_formatter=mticker.FuncFormatter(compact_number_formatter),
        log_scale=LOG_SCALE_VIEW_PANELS,
        time_label=time_label,
    )

    plot_line_metric(
        axes_flat[1],
        plot_df,
        group_col,
        "mean_keyword_views",
        "B) Mean Views pro Keyword-Video",
        "Mean Views / Video",
        palette,
        y_formatter=mticker.FuncFormatter(compact_number_formatter),
        log_scale=LOG_SCALE_VIEW_PANELS,
        time_label=time_label,
    )

    plot_line_metric(
        axes_flat[2],
        plot_df,
        group_col,
        "median_keyword_views",
        "C) Median Views pro Keyword-Video",
        "Median Views / Video",
        palette,
        y_formatter=mticker.FuncFormatter(compact_number_formatter),
        log_scale=LOG_SCALE_VIEW_PANELS,
        time_label=time_label,
    )

    plot_line_metric(
        axes_flat[3],
        plot_df,
        group_col,
        "share_keyword_views",
        "D) Anteil Keyword-Views an allen Views",
        "Keyword-Views / alle Views",
        palette,
        y_formatter=mticker.FuncFormatter(percent_formatter),
        time_label=time_label,
    )

    fig.suptitle(
        f"Figure 3: Erfolg von Nahost-Keyword-Videos — gruppiert nach {group_col}",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    add_shared_legend(fig, axes_flat, palette)
    fig.tight_layout(rect=[0, 0.08, 1, 0.95])

    save_or_show(fig, output_dir / f"figure_3_success_{group_col}_{TIME_UNIT}")


def plot_optional_channel_spread(
    summary: pd.DataFrame,
    group_col: str,
    time_label: str,
    output_dir: Path,
) -> None:
    """
    Optional extra figure:
        A) Active channels
        B) Share of active channels with at least one keyword video

    This helps distinguish:
        - more keyword videos because a few channels upload more
        - more keyword videos because more channels cover the topic
    """
    plot_df = filter_plot_start(summary)
    groups = get_groups(plot_df, group_col)
    palette = make_palette(groups)

    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)

    plot_line_metric(
        axes[0],
        plot_df,
        group_col,
        "n_active_channels",
        "A) Aktive Kanäle",
        "Anzahl Kanäle mit Upload",
        palette,
        y_formatter=mticker.FuncFormatter(compact_number_formatter),
        time_label=time_label,
    )

    plot_line_metric(
        axes[1],
        plot_df,
        group_col,
        "share_keyword_channels",
        "B) Anteil aktiver Kanäle mit mindestens einem Keyword-Video",
        "Keyword-Kanäle / aktive Kanäle",
        palette,
        y_formatter=mticker.FuncFormatter(percent_formatter),
        time_label=time_label,
    )

    fig.suptitle(
        f"Zusatz: Verbreitung der Nahost-Berichterstattung — gruppiert nach {group_col}",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    add_shared_legend(fig, axes, palette)
    fig.tight_layout(rect=[0, 0.08, 1, 0.95])

    save_or_show(fig, output_dir / f"figure_4_channel_spread_{group_col}_{TIME_UNIT}")


def plot_channel_change_boxplot(
    df: pd.DataFrame,
    group_col: str,
    output_dir: Path,
    min_pre_videos: int = 20,
    min_post_videos: int = 20,
) -> None:
    """
    Figure 5: Kanalbasierte Veränderung des Keyword-Anteils.

    Jeder Kanal zählt genau einmal.

    Panels:
        A) Anteil Keyword-Videos vor dem 7.10.
        B) Anteil Keyword-Videos nach dem 7.10.
        C) Veränderung: Post - Pre
    """

    work = df.dropna(subset=[group_col]).copy()
    work[group_col] = work[group_col].astype(str)
    work["post"] = work[DATE_COL] >= pd.to_datetime(EVENT_DATE)

    agg = (
        work.groupby([CHANNEL_COL, group_col, "post"], observed=True)
        .agg(
            n_videos=(VIDEO_ID_COL, "count"),
            n_keyword=(KEYWORD_COL, "sum"),
        )
        .reset_index()
    )

    agg["share_keyword"] = np.where(
        agg["n_videos"] > 0,
        agg["n_keyword"] / agg["n_videos"],
        np.nan,
    )

    wide = agg.pivot(
        index=[CHANNEL_COL, group_col],
        columns="post",
        values=["share_keyword", "n_videos"],
    )

    wide.columns = [
        f"{metric}_{'post' if is_post else 'pre'}"
        for metric, is_post in wide.columns
    ]

    wide = wide.reset_index()

    required_cols = [
        "share_keyword_pre",
        "share_keyword_post",
        "n_videos_pre",
        "n_videos_post",
    ]
    missing_cols = [c for c in required_cols if c not in wide.columns]
    if missing_cols:
        print(
            f"[Warnung] Figure 5 für {group_col} übersprungen. "
            f"Fehlende Spalten nach Pivot: {missing_cols}"
        )
        return

    wide = wide[
        (wide["n_videos_pre"] >= min_pre_videos)
        & (wide["n_videos_post"] >= min_post_videos)
    ].copy()

    if wide.empty:
        print(
            f"[Warnung] Figure 5 für {group_col} übersprungen. "
            f"Keine Kanäle mit mindestens {min_pre_videos} Pre- und "
            f"{min_post_videos} Post-Videos."
        )
        return

    wide["delta_share_keyword"] = (
        wide["share_keyword_post"] - wide["share_keyword_pre"]
    )

    plot_long = pd.concat(
        [
            wide[[CHANNEL_COL, group_col, "share_keyword_pre"]]
            .rename(columns={"share_keyword_pre": "value"})
            .assign(panel="A) Vor dem 7.10."),

            wide[[CHANNEL_COL, group_col, "share_keyword_post"]]
            .rename(columns={"share_keyword_post": "value"})
            .assign(panel="B) Nach dem 7.10."),

            wide[[CHANNEL_COL, group_col, "delta_share_keyword"]]
            .rename(columns={"delta_share_keyword": "value"})
            .assign(panel="C) Veränderung: Post − Pre"),
        ],
        ignore_index=True,
    )

    groups = get_groups(wide, group_col)
    palette = make_palette(groups)

    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharex=False)

    panels = [
        ("A) Vor dem 7.10.", "Anteil Keyword-Videos"),
        ("B) Nach dem 7.10.", "Anteil Keyword-Videos"),
        ("C) Veränderung: Post − Pre", "Δ Anteil Keyword-Videos"),
    ]

    for ax, (panel_name, ylabel) in zip(axes, panels):
        panel_df = plot_long[plot_long["panel"] == panel_name].copy()

        sns.boxplot(
            data=panel_df,
            x=group_col,
            y="value",
            order=groups,
            palette=palette,
            showfliers=False,
            ax=ax,
        )

        sns.stripplot(
            data=panel_df,
            x=group_col,
            y="value",
            order=groups,
            color="black",
            alpha=0.35,
            size=3,
            jitter=0.18,
            ax=ax,
        )

        ax.axhline(0, color="black", linestyle="--", linewidth=1.0, alpha=0.75)
        ax.set_title(panel_name, fontsize=11, fontweight="bold")
        ax.set_xlabel("")
        ax.set_ylabel(ylabel)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(percent_formatter))

        # Für Pre/Post sind negative Werte unmöglich.
        if panel_name.startswith(("A)", "B)")):
            ax.set_ylim(bottom=0)

    fig.suptitle(
        f"Figure 5: Kanalbasierte Veränderung des Keyword-Anteils — gruppiert nach {group_col}",
        fontsize=14,
        fontweight="bold",
        y=1.02,
    )

    fig.text(
        0.5,
        -0.02,
        (
            f"Jeder Punkt ist ein Kanal. Eingeschlossen sind nur Kanäle mit mindestens "
            f"{min_pre_videos} Videos vor und {min_post_videos} Videos nach dem 7.10.2023."
        ),
        ha="center",
        fontsize=9,
    )

    fig.tight_layout()

    save_or_show(
        fig,
        output_dir / f"figure_5_channel_boxplot_{group_col}_{TIME_UNIT}",
    )

    # Optional: zugrunde liegende Kanalwerte speichern
    channel_change_path = (
        output_dir / f"channel_change_keyword_share_{group_col}_{TIME_UNIT}.csv"
    )
    wide.to_csv(channel_change_path, index=False)
    print(f"Kanalbasierte Veränderungswerte gespeichert: {channel_change_path}")


def plot_keyword_populism_channel_deviation(
    df: pd.DataFrame,
    group_col: str,
    output_dir: Path,
    min_keyword_videos_per_period: int = 1,
) -> None:
    """
    Figure 6: Durchschnittliche Abweichung des Video-Populismus vom eigenen Channel-Durchschnitt.

    Für jedes politische Keyword-Video:
        deviation = populism_score_clean - populism_channel_mean

    Danach wird pro Zeitraum x Gruppe der Durchschnitt dieser Abweichung geplottet.

    Interpretation:
        > 0: Keyword-Videos sind populistischer als der typische Kanalstil.
        < 0: Keyword-Videos sind weniger populistisch als der typische Kanalstil.
    """

    required_cols = [
        DATE_COL,
        VIDEO_ID_COL,
        KEYWORD_COL,
        VIDEO_POPULISM_COL,
        "populism_score_clean",
        CHANNEL_BASELINE_COL,
        group_col,
    ]
    require_columns(df, required_cols, "plot_keyword_populism_channel_deviation input")

    period_freq, _ = get_freqs(TIME_UNIT)

    work = df[
        df[KEYWORD_COL]
        & df["populism_score_clean"].notna()
        & df[CHANNEL_BASELINE_COL].notna()
        & df[group_col].notna()
    ].copy()

    if work.empty:
        print(
            f"[Warnung] Figure 6 für {group_col} übersprungen: "
            "keine Keyword-Videos mit gültigem Populismus-Score und Channel-Baseline."
        )
        return

    work[group_col] = work[group_col].astype(str)
    work["period"] = work[DATE_COL].dt.to_period(period_freq).dt.to_timestamp()

    work["populism_deviation_from_channel"] = (
        work["populism_score_clean"] - work[CHANNEL_BASELINE_COL]
    )

    summary = (
        work.groupby(["period", group_col], observed=True)
        .agg(
            mean_deviation=("populism_deviation_from_channel", "mean"),
            median_deviation=("populism_deviation_from_channel", "median"),
            n_keyword_videos=(VIDEO_ID_COL, "count"),
            n_channels=(CHANNEL_COL, "nunique"),
        )
        .reset_index()
    )

    if min_keyword_videos_per_period > 1:
        summary.loc[
            summary["n_keyword_videos"] < min_keyword_videos_per_period,
            ["mean_deviation", "median_deviation"],
        ] = np.nan

    # Vollständiges Zeitraum-Gruppen-Raster ergänzen
    grid = make_complete_period_group_grid(
        work,
        group_col=group_col,
        period_freq=period_freq,
        date_col="period",
    )

    summary = grid.merge(summary, on=["period", group_col], how="left")

    groups = get_groups(summary, group_col)
    palette = make_palette(groups)

    plot_df = filter_plot_start(summary)

    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)

    plot_line_metric(
        axes[0],
        plot_df,
        group_col,
        "mean_deviation",
        "A) Durchschnittliche Abweichung vom eigenen Kanal-Durchschnitt",
        "Ø Video-Populismus − Kanal-Durchschnitt",
        palette,
        time_label=get_time_label(TIME_UNIT),
    )
    axes[0].axhline(0, color="black", linestyle="--", linewidth=1.1, alpha=0.8)

    plot_line_metric(
        axes[1],
        plot_df,
        group_col,
        "n_keyword_videos",
        "B) Anzahl politischer Keyword-Videos mit gültiger Kanal-Baseline",
        "Anzahl Videos",
        palette,
        y_formatter=mticker.FuncFormatter(compact_number_formatter),
        time_label=get_time_label(TIME_UNIT),
    )

    fig.suptitle(
        f"Figure 6: Populismus-Abweichung von Keyword-Videos vom eigenen Kanal — gruppiert nach {group_col}",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )

    add_shared_legend(fig, axes, palette)
    fig.tight_layout(rect=[0, 0.08, 1, 0.95])

    save_or_show(
        fig,
        output_dir / f"figure_6_keyword_populism_channel_deviation_{group_col}_{TIME_UNIT}",
    )

    summary_path = (
        output_dir
        / f"keyword_populism_channel_deviation_summary_{group_col}_{TIME_UNIT}.csv"
    )
    summary.to_csv(summary_path, index=False)
    print(f"Keyword-Populismus-Abweichung gespeichert: {summary_path}")


def plot_keyword_view_overperformance(
    df: pd.DataFrame,
    group_col: str,
    output_dir: Path,
    min_channel_videos_per_period: int = 5,
    min_channel_keyword_videos_per_period: int = 1,
    clip_lift_at: float | None = 10.0,
) -> None:
    """
    Figure 7: Reichweiten-Overperformance von Keyword-Videos.

    Vergleicht:
        Anteil Keyword-Videos an allen Videos
        vs.
        Anteil Keyword-Views an allen Views

    Zwei Ebenen:
        A) Gruppenaggregiert / videogewichtet:
            Große Kanäle dominieren. Gut für die Frage:
            "Wie groß ist der Reichweitenanteil von Nahost in der Gruppe insgesamt?"

        B-D) Kanalbasiert / equal-weighted:
            Jeder Kanal zählt pro Zeitraum gleich. Gut für die Frage:
            "Performen Nahost-Videos für den durchschnittlichen Kanal überdurchschnittlich?"

    Kennzahlen:
        share_keyword_videos = n_keyword_videos / n_videos
        share_keyword_views  = keyword_views / total_views

        view_lift = share_keyword_views / share_keyword_videos

            > 1: Keyword-Videos erzeugen überproportional viele Views
            = 1: proportional
            < 1: unterproportional

        overperformance_pp = share_keyword_views - share_keyword_videos
            positive Werte: Keyword-Videos erzielen mehr View-Anteil als Video-Anteil
    """

    required_cols = [
        DATE_COL,
        VIDEO_ID_COL,
        CHANNEL_COL,
        KEYWORD_COL,
        VIEW_COL,
        group_col,
    ]
    require_columns(df, required_cols, "plot_keyword_view_overperformance input")

    period_freq, _ = get_freqs(TIME_UNIT)

    work = df.dropna(subset=[group_col]).copy()
    work[group_col] = work[group_col].astype(str)
    work["period"] = work[DATE_COL].dt.to_period(period_freq).dt.to_timestamp()
    work[VIEW_COL] = pd.to_numeric(work[VIEW_COL], errors="coerce").fillna(0)

    # ------------------------------------------------------------------
    # A) Gruppenaggregierte / videogewichtete Variante
    # ------------------------------------------------------------------
    group_summary = (
        work.groupby(["period", group_col], observed=True)
        .agg(
            n_videos=(VIDEO_ID_COL, "count"),
            n_keyword_videos=(KEYWORD_COL, "sum"),
            total_views=(VIEW_COL, "sum"),
            keyword_views=(VIEW_COL, lambda s: work.loc[s.index, VIEW_COL][work.loc[s.index, KEYWORD_COL]].sum()),
        )
        .reset_index()
    )

    group_summary["share_keyword_videos"] = np.where(
        group_summary["n_videos"] > 0,
        group_summary["n_keyword_videos"] / group_summary["n_videos"],
        np.nan,
    )

    group_summary["share_keyword_views"] = np.where(
        group_summary["total_views"] > 0,
        group_summary["keyword_views"] / group_summary["total_views"],
        np.nan,
    )

    group_summary["view_lift_group_aggregated"] = np.where(
        group_summary["share_keyword_videos"] > 0,
        group_summary["share_keyword_views"] / group_summary["share_keyword_videos"],
        np.nan,
    )

    group_summary["overperformance_pp_group_aggregated"] = (
        group_summary["share_keyword_views"] - group_summary["share_keyword_videos"]
    )

    # ------------------------------------------------------------------
    # B) Kanalbasierte / equal-weighted Variante
    # ------------------------------------------------------------------
    channel_summary = (
        work.groupby(["period", CHANNEL_COL, group_col], observed=True)
        .agg(
            n_videos=(VIDEO_ID_COL, "count"),
            n_keyword_videos=(KEYWORD_COL, "sum"),
            total_views=(VIEW_COL, "sum"),
            keyword_views=(VIEW_COL, lambda s: work.loc[s.index, VIEW_COL][work.loc[s.index, KEYWORD_COL]].sum()),
        )
        .reset_index()
    )

    channel_summary["share_keyword_videos"] = np.where(
        channel_summary["n_videos"] > 0,
        channel_summary["n_keyword_videos"] / channel_summary["n_videos"],
        np.nan,
    )

    channel_summary["share_keyword_views"] = np.where(
        channel_summary["total_views"] > 0,
        channel_summary["keyword_views"] / channel_summary["total_views"],
        np.nan,
    )

    channel_summary["view_lift"] = np.where(
        channel_summary["share_keyword_videos"] > 0,
        channel_summary["share_keyword_views"] / channel_summary["share_keyword_videos"],
        np.nan,
    )

    channel_summary["overperformance_pp"] = (
        channel_summary["share_keyword_views"] - channel_summary["share_keyword_videos"]
    )

    # Nur Kanäle mit genug Gesamtvideos und mindestens einem Keywordvideo im Zeitraum.
    valid_channel_summary = channel_summary[
        (channel_summary["n_videos"] >= min_channel_videos_per_period)
        & (channel_summary["n_keyword_videos"] >= min_channel_keyword_videos_per_period)
        & channel_summary["view_lift"].notna()
        & np.isfinite(channel_summary["view_lift"])
    ].copy()

    if clip_lift_at is not None:
        valid_channel_summary["view_lift_plot"] = valid_channel_summary["view_lift"].clip(
            upper=clip_lift_at
        )
    else:
        valid_channel_summary["view_lift_plot"] = valid_channel_summary["view_lift"]

    channel_group_summary = (
        valid_channel_summary.groupby(["period", group_col], observed=True)
        .agg(
            mean_view_lift=("view_lift", "mean"),
            median_view_lift=("view_lift", "median"),
            mean_view_lift_plot=("view_lift_plot", "mean"),
            median_view_lift_plot=("view_lift_plot", "median"),
            mean_overperformance_pp=("overperformance_pp", "mean"),
            median_overperformance_pp=("overperformance_pp", "median"),
            n_channels=(CHANNEL_COL, "nunique"),
        )
        .reset_index()
    )

    # ------------------------------------------------------------------
    # Vollständiges Raster ergänzen
    # ------------------------------------------------------------------
    grid = make_complete_period_group_grid(
        work,
        group_col=group_col,
        period_freq=period_freq,
        date_col="period",
    )

    group_summary = grid.merge(group_summary, on=["period", group_col], how="left")
    channel_group_summary = grid.merge(channel_group_summary, on=["period", group_col], how="left")

    groups = get_groups(work, group_col)
    palette = make_palette(groups)
    plot_start = pd.to_datetime(PLOT_START_DATE)

    group_plot = group_summary[group_summary["period"] >= plot_start].copy()
    channel_plot = channel_group_summary[channel_group_summary["period"] >= plot_start].copy()

    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(17, 10), sharex=True)
    axes_flat = axes.flatten()

    # ------------------------------------------------------------------
    # Panel A: Gruppenaggregierter View Lift
    # ------------------------------------------------------------------
    plot_line_metric(
        axes_flat[0],
        group_plot,
        group_col,
        "view_lift_group_aggregated",
        "A) View Lift, gruppenaggregiert",
        "Keyword-View-Anteil / Keyword-Video-Anteil",
        palette,
        time_label=get_time_label(TIME_UNIT),
    )
    axes_flat[0].axhline(1, color="black", linestyle="--", linewidth=1.1, alpha=0.8)

    # ------------------------------------------------------------------
    # Panel B: Kanalbasierter View Lift
    # ------------------------------------------------------------------
    y_col_lift = "median_view_lift_plot" if clip_lift_at is not None else "median_view_lift"

    plot_line_metric(
        axes_flat[1],
        channel_plot,
        group_col,
        y_col_lift,
        "B) Median View Lift pro Kanal",
        "Median Kanal-Lift",
        palette,
        time_label=get_time_label(TIME_UNIT),
    )
    axes_flat[1].axhline(1, color="black", linestyle="--", linewidth=1.1, alpha=0.8)

    if clip_lift_at is not None:
        axes_flat[1].text(
            0.01,
            0.02,
            f"Für die Darstellung bei {clip_lift_at:g} gekappt; CSV enthält ungekappte Werte.",
            transform=axes_flat[1].transAxes,
            fontsize=8,
            alpha=0.75,
        )

    # ------------------------------------------------------------------
    # Panel C: Kanalbasierte Overperformance in Prozentpunkten
    # ------------------------------------------------------------------
    plot_line_metric(
        axes_flat[2],
        channel_plot,
        group_col,
        "median_overperformance_pp",
        "C) Median Overperformance pro Kanal",
        "Keyword-View-Anteil − Keyword-Video-Anteil",
        palette,
        y_formatter=mticker.FuncFormatter(percent_formatter),
        time_label=get_time_label(TIME_UNIT),
    )
    axes_flat[2].axhline(0, color="black", linestyle="--", linewidth=1.1, alpha=0.8)

    # ------------------------------------------------------------------
    # Panel D: Anzahl gültiger Kanäle
    # ------------------------------------------------------------------
    plot_line_metric(
        axes_flat[3],
        channel_plot,
        group_col,
        "n_channels",
        "D) Anzahl Kanäle mit gültigem Lift",
        "Kanäle",
        palette,
        y_formatter=mticker.FuncFormatter(compact_number_formatter),
        time_label=get_time_label(TIME_UNIT),
    )

    fig.suptitle(
        f"Figure 7: Reichweiten-Overperformance von Keyword-Videos — gruppiert nach {group_col}",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )

    fig.text(
        0.5,
        0.015,
        (
            "View Lift > 1 bedeutet: Keyword-Videos erzielen einen höheren Anteil an Views "
            "als ihr Anteil an Videos. Kanalbasierte Werte gewichten jeden Kanal gleich."
        ),
        ha="center",
        fontsize=9,
    )

    add_shared_legend(fig, axes_flat, palette)
    fig.tight_layout(rect=[0, 0.08, 1, 0.95])

    save_or_show(
        fig,
        output_dir / f"figure_7_keyword_view_overperformance_{group_col}_{TIME_UNIT}",
    )

    # ------------------------------------------------------------------
    # CSVs speichern
    # ------------------------------------------------------------------
    group_path = output_dir / f"keyword_view_overperformance_group_aggregated_{group_col}_{TIME_UNIT}.csv"
    channel_path = output_dir / f"keyword_view_overperformance_channel_level_{group_col}_{TIME_UNIT}.csv"
    channel_group_path = output_dir / f"keyword_view_overperformance_channel_group_summary_{group_col}_{TIME_UNIT}.csv"

    group_summary.to_csv(group_path, index=False)
    channel_summary.to_csv(channel_path, index=False)
    channel_group_summary.to_csv(channel_group_path, index=False)

    print(f"Gruppenaggregierte Keyword-View-Overperformance gespeichert: {group_path}")
    print(f"Kanalbasierte Keyword-View-Overperformance gespeichert: {channel_path}")
    print(f"Kanalbasierte Gruppenzusammenfassung gespeichert: {channel_group_path}")


def plot_channel_view_lift_boxplot(
    df: pd.DataFrame,
    group_col: str,
    output_dir: Path,
    min_pre_videos: int = 20,
    min_post_videos: int = 20,
    min_pre_keyword_videos: int = 1,
    min_post_keyword_videos: int = 1,
    clip_lift_at: float | None = 10.0,
) -> None:
    """
    Figure 8: Kanalbasierter Pre/Post-Vergleich des View Lifts von Keyword-Videos.

    Für jeden Kanal wird separat vor und nach dem 7.10. berechnet:

        share_keyword_videos = Keyword-Videos / alle Videos
        share_keyword_views  = Keyword-Views / alle Views

        view_lift = share_keyword_views / share_keyword_videos

    Interpretation:
        view_lift > 1:
            Keyword-Videos erzeugen mehr Views, als aufgrund ihres Video-Anteils zu erwarten wäre.

        view_lift = 1:
            Keyword-Videos erzeugen proportional viele Views.

        view_lift < 1:
            Keyword-Videos erzeugen unterproportional viele Views.

    Panels:
        A) View Lift vor dem 7.10.
        B) View Lift nach dem 7.10.
        C) Veränderung: Post - Pre

    Jeder Punkt ist ein Kanal.
    """

    required_cols = [
        DATE_COL,
        VIDEO_ID_COL,
        CHANNEL_COL,
        KEYWORD_COL,
        VIEW_COL,
        group_col,
    ]
    require_columns(df, required_cols, "plot_channel_view_lift_boxplot input")

    work = df.dropna(subset=[group_col]).copy()
    work[group_col] = work[group_col].astype(str)
    work[VIEW_COL] = pd.to_numeric(work[VIEW_COL], errors="coerce").fillna(0)
    work["post"] = work[DATE_COL] >= pd.to_datetime(EVENT_DATE)

    # ------------------------------------------------------------
    # Kanal x Gruppe x Pre/Post aggregieren
    # ------------------------------------------------------------
    agg = (
        work.groupby([CHANNEL_COL, group_col, "post"], observed=True)
        .agg(
            n_videos=(VIDEO_ID_COL, "count"),
            n_keyword_videos=(KEYWORD_COL, "sum"),
            total_views=(VIEW_COL, "sum"),
            keyword_views=(
                VIEW_COL,
                lambda s: work.loc[s.index, VIEW_COL][work.loc[s.index, KEYWORD_COL]].sum(),
            ),
        )
        .reset_index()
    )

    agg["share_keyword_videos"] = np.where(
        agg["n_videos"] > 0,
        agg["n_keyword_videos"] / agg["n_videos"],
        np.nan,
    )

    agg["share_keyword_views"] = np.where(
        agg["total_views"] > 0,
        agg["keyword_views"] / agg["total_views"],
        np.nan,
    )

    agg["view_lift"] = np.where(
        agg["share_keyword_videos"] > 0,
        agg["share_keyword_views"] / agg["share_keyword_videos"],
        np.nan,
    )

    agg["overperformance_pp"] = (
        agg["share_keyword_views"] - agg["share_keyword_videos"]
    )

    # ------------------------------------------------------------
    # Wide-Format: eine Zeile pro Kanal
    # ------------------------------------------------------------
    wide = agg.pivot(
        index=[CHANNEL_COL, group_col],
        columns="post",
        values=[
            "n_videos",
            "n_keyword_videos",
            "share_keyword_videos",
            "share_keyword_views",
            "view_lift",
            "overperformance_pp",
        ],
    )

    wide.columns = [
        f"{metric}_{'post' if is_post else 'pre'}"
        for metric, is_post in wide.columns
    ]

    wide = wide.reset_index()

    required_after_pivot = [
        "n_videos_pre",
        "n_videos_post",
        "n_keyword_videos_pre",
        "n_keyword_videos_post",
        "view_lift_pre",
        "view_lift_post",
    ]
    missing_after_pivot = [c for c in required_after_pivot if c not in wide.columns]
    if missing_after_pivot:
        print(
            f"[Warnung] Figure 8 für {group_col} übersprungen. "
            f"Fehlende Spalten nach Pivot: {missing_after_pivot}"
        )
        return

    # ------------------------------------------------------------
    # Mindestfallzahlen
    # ------------------------------------------------------------
    wide = wide[
        (wide["n_videos_pre"] >= min_pre_videos)
        & (wide["n_videos_post"] >= min_post_videos)
        & (wide["n_keyword_videos_pre"] >= min_pre_keyword_videos)
        & (wide["n_keyword_videos_post"] >= min_post_keyword_videos)
        & wide["view_lift_pre"].notna()
        & wide["view_lift_post"].notna()
        & np.isfinite(wide["view_lift_pre"])
        & np.isfinite(wide["view_lift_post"])
    ].copy()

    if wide.empty:
        print(
            f"[Warnung] Figure 8 für {group_col} übersprungen. "
            "Keine Kanäle erfüllen die Mindestfallzahlen."
        )
        return

    wide["delta_view_lift"] = wide["view_lift_post"] - wide["view_lift_pre"]

    # Für die Grafik optional extreme View-Lift-Werte kappen.
    # Die CSV enthält weiterhin die ungekappte Version.
    if clip_lift_at is not None:
        wide["view_lift_pre_plot"] = wide["view_lift_pre"].clip(upper=clip_lift_at)
        wide["view_lift_post_plot"] = wide["view_lift_post"].clip(upper=clip_lift_at)
        wide["delta_view_lift_plot"] = wide["delta_view_lift"].clip(
            lower=-clip_lift_at,
            upper=clip_lift_at,
        )
    else:
        wide["view_lift_pre_plot"] = wide["view_lift_pre"]
        wide["view_lift_post_plot"] = wide["view_lift_post"]
        wide["delta_view_lift_plot"] = wide["delta_view_lift"]

    plot_long = pd.concat(
        [
            wide[[CHANNEL_COL, group_col, "view_lift_pre_plot"]]
            .rename(columns={"view_lift_pre_plot": "value"})
            .assign(panel="A) Vor dem 7.10."),

            wide[[CHANNEL_COL, group_col, "view_lift_post_plot"]]
            .rename(columns={"view_lift_post_plot": "value"})
            .assign(panel="B) Nach dem 7.10."),

            wide[[CHANNEL_COL, group_col, "delta_view_lift_plot"]]
            .rename(columns={"delta_view_lift_plot": "value"})
            .assign(panel="C) Veränderung: Post − Pre"),
        ],
        ignore_index=True,
    )

    groups = get_groups(wide, group_col)
    palette = make_palette(groups)

    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), sharex=False)

    panels = [
        ("A) Vor dem 7.10.", "View Lift"),
        ("B) Nach dem 7.10.", "View Lift"),
        ("C) Veränderung: Post − Pre", "Δ View Lift"),
    ]

    for ax, (panel_name, ylabel) in zip(axes, panels):
        panel_df = plot_long[plot_long["panel"] == panel_name].copy()

        sns.boxplot(
            data=panel_df,
            x=group_col,
            y="value",
            order=groups,
            palette=palette,
            showfliers=False,
            ax=ax,
        )

        sns.stripplot(
            data=panel_df,
            x=group_col,
            y="value",
            order=groups,
            color="black",
            alpha=0.35,
            size=3,
            jitter=0.18,
            ax=ax,
        )

        if panel_name.startswith(("A)", "B)")):
            ax.axhline(1, color="black", linestyle="--", linewidth=1.0, alpha=0.75)
            ax.set_ylim(bottom=0)
        else:
            ax.axhline(0, color="black", linestyle="--", linewidth=1.0, alpha=0.75)

        ax.set_title(panel_name, fontsize=11, fontweight="bold")
        ax.set_xlabel("")
        ax.set_ylabel(ylabel)

    if clip_lift_at is not None:
        fig.text(
            0.5,
            -0.035,
            (
                f"Für die Darstellung wurden View-Lift-Werte bei ±{clip_lift_at:g} gekappt. "
                "Die gespeicherte CSV enthält die ungekappte Version."
            ),
            ha="center",
            fontsize=9,
        )

    fig.suptitle(
        f"Figure 8: Kanalbasierter View Lift von Keyword-Videos — gruppiert nach {group_col}",
        fontsize=14,
        fontweight="bold",
        y=1.02,
    )

    fig.text(
        0.5,
        -0.005,
        (
            "Jeder Punkt ist ein Kanal. View Lift > 1 bedeutet: Keyword-Videos erzielen "
            "überproportional viele Views. Eingeschlossen sind nur Kanäle mit ausreichend "
            "Pre- und Post-Videos sowie mindestens einem Keyword-Video in beiden Perioden."
        ),
        ha="center",
        fontsize=9,
    )

    fig.tight_layout()

    save_or_show(
        fig,
        output_dir / f"figure_8_channel_view_lift_boxplot_{group_col}_{TIME_UNIT}",
    )

    # ------------------------------------------------------------
    # CSV speichern
    # ------------------------------------------------------------
    channel_lift_path = (
        output_dir / f"channel_view_lift_pre_post_{group_col}_{TIME_UNIT}.csv"
    )
    wide.to_csv(channel_lift_path, index=False)
    print(f"Kanalbasierter Pre/Post-View-Lift gespeichert: {channel_lift_path}")

    # ------------------------------------------------------------
    # Kurze deskriptive Tabelle in der Konsole
    # ------------------------------------------------------------
    desc = (
        wide.groupby(group_col, observed=True)
        .agg(
            n_channels=(CHANNEL_COL, "nunique"),
            median_lift_pre=("view_lift_pre", "median"),
            median_lift_post=("view_lift_post", "median"),
            median_delta_lift=("delta_view_lift", "median"),
            mean_delta_lift=("delta_view_lift", "mean"),
            share_channels_positive_delta=(
                "delta_view_lift",
                lambda s: (s > 0).mean(),
            ),
        )
        .reset_index()
    )

    print("\n=== Kanalbasierter View Lift Pre/Post ===")
    print(desc.to_string(index=False))


def plot_keyword_view_audience_shift(
    df: pd.DataFrame,
    group_col: str,
    output_dir: Path,
    min_keyword_views_per_period: int = 1,
) -> None:
    """
    Figure 9: Audience Shift bei Keyword-Videos.

    Frage:
        Verlagern sich Views von Zentrum/Mainstream zu Rändern/alternativen Medien?

    Für ideology_group:
        - center vs left/right
        - Edge Share = (left + right keyword views) / all keyword views
        - Edge/Center Ratio = (left + right keyword views) / center keyword views

    Für type:
        - 1 = ÖRR
        - 2 = traditionelle Medien
        - 3 = alternative Medien
        - Alternative Share = type 3 keyword views / all keyword views
        - Alternative/Mainstream Ratio = type 3 / (type 1 + type 2)
    """

    required_cols = [
        DATE_COL,
        VIDEO_ID_COL,
        KEYWORD_COL,
        VIEW_COL,
        group_col,
    ]
    require_columns(df, required_cols, "plot_keyword_view_audience_shift input")

    period_freq, _ = get_freqs(TIME_UNIT)

    work = df[
        df[KEYWORD_COL]
        & df[group_col].notna()
    ].copy()

    if work.empty:
        print(f"[Warnung] Figure 9 für {group_col} übersprungen: keine Keyword-Videos.")
        return

    work[group_col] = work[group_col].astype(str)
    work[VIEW_COL] = pd.to_numeric(work[VIEW_COL], errors="coerce").fillna(0)
    work["period"] = work[DATE_COL].dt.to_period(period_freq).dt.to_timestamp()

    # ------------------------------------------------------------------
    # Keyword-Views und Keyword-Videos pro Periode x Gruppe
    # ------------------------------------------------------------------
    summary = (
        work.groupby(["period", group_col], observed=True)
        .agg(
            keyword_views=(VIEW_COL, "sum"),
            n_keyword_videos=(VIDEO_ID_COL, "count"),
            n_channels=(CHANNEL_COL, "nunique") if CHANNEL_COL in work.columns else (VIDEO_ID_COL, "count"),
        )
        .reset_index()
    )

    totals = (
        summary.groupby("period", observed=True)
        .agg(
            all_keyword_views=("keyword_views", "sum"),
            all_keyword_videos=("n_keyword_videos", "sum"),
        )
        .reset_index()
    )

    summary = summary.merge(totals, on="period", how="left")

    summary["share_keyword_views_all"] = np.where(
        summary["all_keyword_views"] > 0,
        summary["keyword_views"] / summary["all_keyword_views"],
        np.nan,
    )

    summary["share_keyword_videos_all"] = np.where(
        summary["all_keyword_videos"] > 0,
        summary["n_keyword_videos"] / summary["all_keyword_videos"],
        np.nan,
    )

    # Optional: Perioden mit extrem wenigen Gesamtviews ausblenden
    summary.loc[
        summary["all_keyword_views"] < min_keyword_views_per_period,
        ["share_keyword_views_all", "share_keyword_videos_all"],
    ] = np.nan

    # Vollständiges Grid
    grid = make_complete_period_group_grid(
        work,
        group_col=group_col,
        period_freq=period_freq,
        date_col="period",
    )
    summary = grid.merge(summary, on=["period", group_col], how="left")

    # ------------------------------------------------------------------
    # Spezialmetriken: Ränder vs Zentrum oder Alternative vs Mainstream
    # ------------------------------------------------------------------
    wide_views = (
        summary.pivot_table(
            index="period",
            columns=group_col,
            values="keyword_views",
            aggfunc="sum",
        )
        .reset_index()
    )

    # Spaltennamen sicher als string
    wide_views.columns = [str(c) if c != "period" else c for c in wide_views.columns]

    special = wide_views.copy()

    if group_col == "ideology_group":
        for col in ["left", "center", "right"]:
            if col not in special.columns:
                special[col] = 0

        special["edge_views"] = special["left"].fillna(0) + special["right"].fillna(0)
        special["center_views"] = special["center"].fillna(0)
        special["all_views"] = special["edge_views"] + special["center_views"]

        special["edge_share"] = np.where(
            special["all_views"] > 0,
            special["edge_views"] / special["all_views"],
            np.nan,
        )

        special["edge_center_ratio"] = np.where(
            special["center_views"] > 0,
            special["edge_views"] / special["center_views"],
            np.nan,
        )

        special_share_col = "edge_share"
        special_ratio_col = "edge_center_ratio"
        special_share_title = "C) Anteil der Ränder an allen Keyword-Views"
        special_ratio_title = "D) Verhältnis Ränder / Zentrum"
        special_share_ylabel = "(left + right) / alle Keyword-Views"
        special_ratio_ylabel = "(left + right) / center"

    elif group_col == "type":
        # type kann als 1.0/2.0/3.0 oder 1/2/3 als string vorliegen
        possible_1 = [c for c in special.columns if c in {"1", "1.0"}]
        possible_2 = [c for c in special.columns if c in {"2", "2.0"}]
        possible_3 = [c for c in special.columns if c in {"3", "3.0"}]

        col_1 = possible_1[0] if possible_1 else "1.0"
        col_2 = possible_2[0] if possible_2 else "2.0"
        col_3 = possible_3[0] if possible_3 else "3.0"

        for col in [col_1, col_2, col_3]:
            if col not in special.columns:
                special[col] = 0

        special["mainstream_views"] = special[col_1].fillna(0) + special[col_2].fillna(0)
        special["alternative_views"] = special[col_3].fillna(0)
        special["all_views"] = special["mainstream_views"] + special["alternative_views"]

        special["alternative_share"] = np.where(
            special["all_views"] > 0,
            special["alternative_views"] / special["all_views"],
            np.nan,
        )

        special["alternative_mainstream_ratio"] = np.where(
            special["mainstream_views"] > 0,
            special["alternative_views"] / special["mainstream_views"],
            np.nan,
        )

        special_share_col = "alternative_share"
        special_ratio_col = "alternative_mainstream_ratio"
        special_share_title = "C) Anteil alternativer Medien an allen Keyword-Views"
        special_ratio_title = "D) Verhältnis Alternative / Mainstream"
        special_share_ylabel = "Alternative / alle Keyword-Views"
        special_ratio_ylabel = "Alternative / ÖRR+traditionelle"

    else:
        print(
            f"[Info] Für {group_col} werden nur Panel A/B geplottet. "
            "Panel C/D sind nur für ideology_group und type definiert."
        )
        special = None

    groups = get_groups(summary.dropna(subset=[group_col]), group_col)
    palette = make_palette(groups)

    plot_df = filter_plot_start(summary)
    if special is not None:
        special_plot = special[special["period"] >= pd.to_datetime(PLOT_START_DATE)].copy()

    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(17, 10), sharex=True)
    axes_flat = axes.flatten()

    # ------------------------------------------------------------------
    # A) Anteil Keyword-Views
    # ------------------------------------------------------------------
    plot_line_metric(
        axes_flat[0],
        plot_df,
        group_col,
        "share_keyword_views_all",
        "A) Anteil an allen Keyword-Views",
        "Keyword-Views der Gruppe / alle Keyword-Views",
        palette,
        y_formatter=mticker.FuncFormatter(percent_formatter),
        time_label=get_time_label(TIME_UNIT),
    )

    # ------------------------------------------------------------------
    # B) Anteil Keyword-Videos
    # ------------------------------------------------------------------
    plot_line_metric(
        axes_flat[1],
        plot_df,
        group_col,
        "share_keyword_videos_all",
        "B) Anteil an allen Keyword-Videos",
        "Keyword-Videos der Gruppe / alle Keyword-Videos",
        palette,
        y_formatter=mticker.FuncFormatter(percent_formatter),
        time_label=get_time_label(TIME_UNIT),
    )

    # ------------------------------------------------------------------
    # C/D Spezialmetriken
    # ------------------------------------------------------------------
    if special is not None:
        axes_flat[2].plot(
            special_plot["period"],
            special_plot[special_share_col],
            marker="o",
            linewidth=2,
        )
        add_event_line(axes_flat[2])
        axes_flat[2].set_title(special_share_title, fontsize=11, fontweight="bold")
        axes_flat[2].set_ylabel(special_share_ylabel)
        axes_flat[2].yaxis.set_major_formatter(mticker.FuncFormatter(percent_formatter))
        style_time_axis(axes_flat[2], get_time_label(TIME_UNIT))

        axes_flat[3].plot(
            special_plot["period"],
            special_plot[special_ratio_col],
            marker="o",
            linewidth=2,
        )
        add_event_line(axes_flat[3])
        axes_flat[3].axhline(1, color="black", linestyle="--", linewidth=1.0, alpha=0.75)
        axes_flat[3].set_title(special_ratio_title, fontsize=11, fontweight="bold")
        axes_flat[3].set_ylabel(special_ratio_ylabel)
        style_time_axis(axes_flat[3], get_time_label(TIME_UNIT))
    else:
        axes_flat[2].set_visible(False)
        axes_flat[3].set_visible(False)

    fig.suptitle(
        f"Figure 9: Verlagerung der Keyword-Views — gruppiert nach {group_col}",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )

    fig.text(
        0.5,
        0.015,
        (
            "Panel A zeigt, wohin die tatsächlichen Keyword-Views fließen. "
            "Panel B zeigt, wer wie viele Keyword-Videos produziert. "
            "Wenn A stärker als B steigt, spricht das für überproportionale Aufmerksamkeit."
        ),
        ha="center",
        fontsize=9,
    )

    add_shared_legend(fig, axes_flat[:2], palette)
    fig.tight_layout(rect=[0, 0.08, 1, 0.95])

    save_or_show(
        fig,
        output_dir / f"figure_9_keyword_view_audience_shift_{group_col}_{TIME_UNIT}",
    )

    summary_path = output_dir / f"keyword_view_audience_shift_{group_col}_{TIME_UNIT}.csv"
    summary.to_csv(summary_path, index=False)
    print(f"Audience-Shift-Daten gespeichert: {summary_path}")

    if special is not None:
        special_path = output_dir / f"keyword_view_audience_shift_special_{group_col}_{TIME_UNIT}.csv"
        special.to_csv(special_path, index=False)
        print(f"Audience-Shift-Spezialmetriken gespeichert: {special_path}")


def plot_populism_success_bins(
    work: pd.DataFrame,
    group_label: str,
    output_dir: Path,
) -> None:
    """
    Deskriptive Ergänzung zur Regression:
        Populismus-Bins -> median log views

    Erwartet bereits vorbereitete work-Daten aus run_populism_success_regressions():
        - log_views
        - populism_score_clean
        - group_var
        - post
    """

    plot_df = work.copy()

    plot_df["populism_bin"] = pd.cut(
        plot_df["populism_score_clean"],
        bins=[-0.01, 2, 4, 6, 8, 10],
        labels=["0–2", "2–4", "4–6", "6–8", "8–10"],
        include_lowest=True,
    )

    summary = (
        plot_df.groupby(["populism_bin", "group_var", "post"], observed=True)
        .agg(
            median_log_views=("log_views", "median"),
            mean_log_views=("log_views", "mean"),
            n_videos=(VIDEO_ID_COL, "count"),
        )
        .reset_index()
    )

    summary["period"] = summary["post"].map({0: "Vor 7.10.", 1: "Nach 7.10."})

    groups = sorted(summary["group_var"].dropna().astype(str).unique())
    palette = make_palette(groups)

    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(16, 6), sharey=True)

    for ax, period in zip(axes, ["Vor 7.10.", "Nach 7.10."]):
        sub = summary[summary["period"] == period].copy()

        sns.lineplot(
            data=sub,
            x="populism_bin",
            y="median_log_views",
            hue="group_var",
            hue_order=groups,
            palette=palette,
            marker="o",
            linewidth=2,
            ax=ax,
            legend=(period == "Nach 7.10."),
        )

        ax.set_title(period, fontsize=11, fontweight="bold")
        ax.set_xlabel("Populismus-Score")
        ax.set_ylabel("Median log(Views + 1)")
        ax.tick_params(axis="x", rotation=0)

        # n anzeigen: kleine Fallzahlen sichtbar machen
        for _, row in sub.iterrows():
            if pd.notna(row["median_log_views"]):
                ax.text(
                    row["populism_bin"],
                    row["median_log_views"],
                    f"n={int(row['n_videos'])}",
                    fontsize=7,
                    alpha=0.65,
                    ha="center",
                    va="bottom",
                )

    fig.suptitle(
        f"Populismus und Video-Erfolg — gruppiert nach {group_label}",
        fontsize=14,
        fontweight="bold",
        y=1.02,
    )

    fig.tight_layout()

    save_or_show(
        fig,
        output_dir / f"figure_10_populism_success_bins_{group_label}_{TIME_UNIT}",
    )

    summary_path = output_dir / f"populism_success_bins_{group_label}_{TIME_UNIT}.csv"
    summary.to_csv(summary_path, index=False)
    print(f"Populismus-Erfolg-Bins gespeichert: {summary_path}")


def plot_populism_success_bins_event_phase(
    work: pd.DataFrame,
    group_label: str,
    output_dir: Path,
) -> None:
    """
    Deskriptive Ergänzung zur Event-Phasen-Regression:
        Populismus-Bins -> median log views
        getrennt nach Event-Phase.

    Erwartet bereits vorbereitete work-Daten aus run_populism_success_regressions():
        - log_views
        - populism_score_clean
        - group_var
        - event_phase
    """

    plot_df = work.copy()

    plot_df["populism_bin"] = pd.cut(
        plot_df["populism_score_clean"],
        bins=[-0.01, 2, 4, 6, 8, 10],
        labels=["0–2", "2–4", "4–6", "6–8", "8–10"],
        include_lowest=True,
    )

    summary = (
        plot_df.groupby(["event_phase", "populism_bin", "group_var"], observed=True)
        .agg(
            median_log_views=("log_views", "median"),
            mean_log_views=("log_views", "mean"),
            n_videos=(VIDEO_ID_COL, "count"),
        )
        .reset_index()
    )

    phase_order = ["pre", "shock", "medium_term", "long_term"]
    phase_titles = {
        "pre": "Pre: bis Sep 2023",
        "shock": "Shock: Okt–Nov 2023",
        "medium_term": "Medium-term: Dez 2023–Jun 2024",
        "long_term": "Long-term: ab Jul 2024",
    }

    groups = sorted(summary["group_var"].dropna().astype(str).unique())
    palette = make_palette(groups)

    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(18, 11), sharey=True)
    axes_flat = axes.flatten()

    for ax, phase in zip(axes_flat, phase_order):
        sub = summary[summary["event_phase"].astype(str) == phase].copy()

        if sub.empty:
            ax.set_visible(False)
            continue

        sns.lineplot(
            data=sub,
            x="populism_bin",
            y="median_log_views",
            hue="group_var",
            hue_order=groups,
            palette=palette,
            marker="o",
            linewidth=2,
            ax=ax,
            legend=False,
        )

        ax.set_title(phase_titles.get(phase, phase), fontsize=11, fontweight="bold")
        ax.set_xlabel("Populismus-Score")
        ax.set_ylabel("Median log(Views + 1)")

        for _, row in sub.iterrows():
            if pd.notna(row["median_log_views"]):
                ax.text(
                    row["populism_bin"],
                    row["median_log_views"],
                    f"n={int(row['n_videos'])}",
                    fontsize=7,
                    alpha=0.65,
                    ha="center",
                    va="bottom",
                )

    handles = [
        plt.Line2D(
            [],
            [],
            color=palette[group],
            marker="o",
            linewidth=2,
            markersize=5,
            label=str(group),
        )
        for group in groups
    ]

    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.02),
        ncol=min(len(handles), 4),
        frameon=True,
        fontsize=9,
    )

    fig.suptitle(
        f"Populismus und Video-Erfolg nach Event-Phasen — gruppiert nach {group_label}",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )

    fig.tight_layout(rect=[0, 0.07, 1, 0.95])

    save_or_show(
        fig,
        output_dir / f"figure_11_populism_success_bins_event_phases_{group_label}_{TIME_UNIT}",
    )

    summary_path = output_dir / f"populism_success_bins_event_phases_{group_label}_{TIME_UNIT}.csv"
    summary.to_csv(summary_path, index=False)
    print(f"Populismus-Erfolg-Bins nach Event-Phasen gespeichert: {summary_path}")


# =============================================================================
# DIAGNOSTICS
# =============================================================================

def print_group_diagnostics(df: pd.DataFrame, group_col: str) -> None:
    """Print basic diagnostics per group."""
    print(f"\n=== Diagnostics für {group_col} ===")

    diag = (
        df.dropna(subset=[group_col])
        .groupby(group_col, observed=True)
        .agg(
            n_channels=(CHANNEL_COL, "nunique"),
            n_videos=(VIDEO_ID_COL, "count"),
            n_keyword_videos=(KEYWORD_COL, "sum"),
            total_views=(VIEW_COL, "sum"),
            keyword_views=(VIEW_COL, lambda s: df.loc[s.index, VIEW_COL][df.loc[s.index, KEYWORD_COL]].sum()),
            mean_channel_populism=(CHANNEL_BASELINE_COL, "mean"),
        )
        .reset_index()
    )

    diag["share_keyword_videos"] = diag["n_keyword_videos"] / diag["n_videos"]
    diag["share_keyword_views"] = np.where(
        diag["total_views"] > 0,
        diag["keyword_views"] / diag["total_views"],
        np.nan,
    )

    with pd.option_context("display.max_columns", None, "display.width", 180):
        print(diag.to_string(index=False))


def run_populism_success_panel_regressions(
    df: pd.DataFrame,
    group_col: str,
    output_dir: Path,
    only_keyword_videos: bool = True,
    min_views: int = 0,
) -> None:
    """
    Populismus -> Video-Erfolg mit absorbierten Fixed Effects.

    Nutzt linearmodels.PanelOLS statt statsmodels mit C(channel_title).

    Fixed Effects:
        - Channel FE über entity_effects=True
        - Month FE über time_effects=True

    Wichtig:
        Mit Month FE sind reine event_phase-Haupteffekte nicht identifizierbar,
        weil event_phase vollständig aus dem Monat abgeleitet ist.
        Deshalb verwenden wir event_phase nur in Interaktionen mit populism_score_clean.

    AV:
        log_views = log(views + 1)

    Wichtigste Interpretation:
        populism_score_clean:
            Zusammenhang zwischen Populismus und Views innerhalb desselben Kanals,
            unter Kontrolle für Monatsunterschiede.

        pop_x_shock / pop_x_medium / pop_x_long:
            Ist der Populismus-Erfolg-Zusammenhang in diesen Phasen stärker/schwächer
            als in der Pre-Phase?

        pop_x_group_*:
            Unterscheidet sich der Populismus-Erfolg-Zusammenhang zwischen Gruppen?

        pop_x_phase_x_group_*:
            Unterscheidet sich die zeitliche Veränderung des Populismus-Effekts
            zwischen Gruppen?
    """

    from linearmodels.panel import PanelOLS

    required_cols = [
        DATE_COL,
        VIDEO_ID_COL,
        CHANNEL_COL,
        VIEW_COL,
        "populism_score_clean",
        group_col,
    ]
    if only_keyword_videos:
        required_cols.append(KEYWORD_COL)

    require_columns(df, required_cols, "run_populism_success_panel_regressions input")

    work = df.copy()

    if only_keyword_videos:
        work = work[work[KEYWORD_COL]].copy()

    work = work[
        work["populism_score_clean"].notna()
        & work[group_col].notna()
        & work[CHANNEL_COL].notna()
        & work[DATE_COL].notna()
    ].copy()

    work[VIEW_COL] = pd.to_numeric(work[VIEW_COL], errors="coerce")
    work = work[work[VIEW_COL].notna()].copy()

    if min_views > 0:
        work = work[work[VIEW_COL] >= min_views].copy()

    if work.empty:
        print(f"[Warnung] Keine Daten für Panel-Regression mit {group_col}.")
        return

    work[DATE_COL] = pd.to_datetime(work[DATE_COL]).dt.tz_localize(None)
    work[CHANNEL_COL] = work[CHANNEL_COL].astype(str)
    work[group_col] = work[group_col].astype(str)

    work["month"] = work[DATE_COL].dt.to_period("M").dt.to_timestamp()
    work["log_views"] = np.log1p(work[VIEW_COL])

    # ------------------------------------------------------------
    # Event-Phasen
    # ------------------------------------------------------------
    work["shock"] = (
        (work[DATE_COL] >= pd.to_datetime("2023-10-01"))
        & (work[DATE_COL] <= pd.to_datetime("2023-11-30"))
    ).astype(int)

    work["medium_term"] = (
        (work[DATE_COL] >= pd.to_datetime("2023-12-01"))
        & (work[DATE_COL] <= pd.to_datetime("2024-06-30"))
    ).astype(int)

    work["long_term"] = (
        work[DATE_COL] >= pd.to_datetime("2024-07-01")
    ).astype(int)

    work["post"] = (
        work[DATE_COL] >= pd.to_datetime(EVENT_DATE)
    ).astype(int)

    # Interaktionen mit Populismus
    work["pop_x_post"] = work["populism_score_clean"] * work["post"]
    work["pop_x_shock"] = work["populism_score_clean"] * work["shock"]
    work["pop_x_medium"] = work["populism_score_clean"] * work["medium_term"]
    work["pop_x_long"] = work["populism_score_clean"] * work["long_term"]

    # Kanalrelative AV als Zusatz
    work["relative_log_views"] = (
        work["log_views"]
        - work.groupby(CHANNEL_COL)["log_views"].transform("median")
    )

    # ------------------------------------------------------------
    # Gruppen-Dummies und Interaktionen
    # ------------------------------------------------------------
    # Referenzgruppe: alphabetisch erste Gruppe, z.B. center bei ideology_group
    # oder 1.0 bei type, abhängig von deinen Daten.
    group_dummies = pd.get_dummies(
        work[group_col],
        prefix="group",
        drop_first=True,
        dtype=float,
    )

    work = pd.concat([work, group_dummies], axis=1)

    group_dummy_cols = list(group_dummies.columns)

    for col in group_dummy_cols:
        work[f"pop_x_{col}"] = work["populism_score_clean"] * work[col]
        work[f"post_x_{col}"] = work["post"] * work[col]
        work[f"pop_x_post_x_{col}"] = work["populism_score_clean"] * work["post"] * work[col]

        work[f"pop_x_shock_x_{col}"] = work["populism_score_clean"] * work["shock"] * work[col]
        work[f"pop_x_medium_x_{col}"] = work["populism_score_clean"] * work["medium_term"] * work[col]
        work[f"pop_x_long_x_{col}"] = work["populism_score_clean"] * work["long_term"] * work[col]

    # ------------------------------------------------------------
    # Panel-Index setzen
    # ------------------------------------------------------------
    # PanelOLS braucht MultiIndex entity x time.
    # Achtung: Mehrere Videos pro Kanal-Monat sind erlaubt.
    work = work.set_index([CHANNEL_COL, "month"]).sort_index()

    output_dir.mkdir(parents=True, exist_ok=True)

    regression_data_path = (
        output_dir / f"panel_regression_data_populism_success_{group_col}_{TIME_UNIT}.csv"
    )
    work.reset_index().to_csv(regression_data_path, index=False)
    print(f"Panel-Regressionsdaten gespeichert: {regression_data_path}")

    print("\n" + "=" * 80)
    print(f"PANEL-REGRESSIONEN POPULISMUS → ERFOLG | group_col = {group_col}")
    print("=" * 80)
    print(f"N Videos: {len(work):,}")
    print(f"N Channels: {work.index.get_level_values(0).nunique():,}")
    print(f"N Months: {work.index.get_level_values(1).nunique():,}")

    # ------------------------------------------------------------
    # Modelle definieren
    # ------------------------------------------------------------
    models = {
        "P1_FE_basic": [
            "populism_score_clean",
        ],

        "P2_FE_post": [
            "populism_score_clean",
            "pop_x_post",
        ],

        "P3_FE_event_phases": [
            "populism_score_clean",
            "pop_x_shock",
            "pop_x_medium",
            "pop_x_long",
        ],

        "P4_FE_group": [
            "populism_score_clean",
            *[f"pop_x_{col}" for col in group_dummy_cols],
        ],

        "P5_FE_post_group": [
            "populism_score_clean",
            "pop_x_post",
            *[f"pop_x_{col}" for col in group_dummy_cols],
            *[f"pop_x_post_x_{col}" for col in group_dummy_cols],
        ],

        "P6_FE_event_phase_group": [
            "populism_score_clean",
            "pop_x_shock",
            "pop_x_medium",
            "pop_x_long",
            *[f"pop_x_{col}" for col in group_dummy_cols],
            *[f"pop_x_shock_x_{col}" for col in group_dummy_cols],
            *[f"pop_x_medium_x_{col}" for col in group_dummy_cols],
            *[f"pop_x_long_x_{col}" for col in group_dummy_cols],
        ],
    }

    all_rows = []

    def fit_panel_model(model_name: str, y_col: str, x_cols: list[str]) -> None:
        nonlocal all_rows

        model_df = work[[y_col, *x_cols]].dropna().copy()

        y = model_df[y_col]
        X = model_df[x_cols]

        print("\n" + "-" * 80)
        print(model_name)
        print(f"DV: {y_col}")
        print(f"X: {x_cols}")
        print("-" * 80)

        try:
            mod = PanelOLS(
                y,
                X,
                entity_effects=True,
                time_effects=True,
                drop_absorbed=True,
                check_rank=False,
            )

            res = mod.fit(
                cov_type="clustered",
                cluster_entity=True,
            )

            print(res.summary)

            coef_table = pd.DataFrame({
                "term": res.params.index,
                "coef": res.params.values,
                "std_err": res.std_errors.values,
                "p_value": res.pvalues.values,
                "ci_low": res.conf_int().iloc[:, 0].values,
                "ci_high": res.conf_int().iloc[:, 1].values,
                "model": model_name,
                "dv": y_col,
                "nobs": res.nobs,
                "rsquared_within": res.rsquared_within,
            })

            coef_path = output_dir / f"panel_regression_{model_name}_{group_col}_{y_col}.csv"
            coef_table.to_csv(coef_path, index=False)
            print(f"Koeffizienten gespeichert: {coef_path}")

            all_rows.append(coef_table)

        except Exception as e:
            print(f"[Fehler] {model_name} konnte nicht geschätzt werden: {e}")

    # log_views-Modelle
    for model_name, x_cols in models.items():
        fit_panel_model(model_name, "log_views", x_cols)

    # kanalrelative Erfolgsmodelle als Robustheit
    for model_name, x_cols in models.items():
        fit_panel_model(f"{model_name}_relative", "relative_log_views", x_cols)

    if all_rows:
        all_coefs = pd.concat(all_rows, ignore_index=True)
        all_path = output_dir / f"panel_regression_populism_success_all_models_{group_col}_{TIME_UNIT}.csv"
        all_coefs.to_csv(all_path, index=False)
        print(f"\nAlle Panel-Koeffizienten gespeichert: {all_path}")

        key_terms = all_coefs[
            all_coefs["term"].str.contains(
                "populism|pop_x",
                regex=True,
                na=False,
            )
        ].copy()

        key_path = output_dir / f"panel_regression_populism_success_key_terms_{group_col}_{TIME_UNIT}.csv"
        key_terms.to_csv(key_path, index=False)
        print(f"Zentrale Panel-Koeffizienten gespeichert: {key_path}")


def run_populism_success_by_group_panel_regressions(
    df: pd.DataFrame,
    group_col: str,
    output_dir: Path,
    only_keyword_videos: bool = True,
    min_views: int = 0,
    min_videos_per_group: int = 30,
    min_channels_per_group: int = 3,
) -> None:
    """
    Separate Panel-Regressionen pro Gruppe.

    Geschätzt werden nur die Basismodelle:

    P1:
        log_views ~ populism_score_clean
        + Channel FE
        + Month FE

    P2:
        log_views ~ populism_score_clean + pop_x_post
        + Channel FE
        + Month FE

    Vorteil:
        Keine komplizierten Triple-Interactions.
        Direkte Interpretation pro Gruppe.

    Beispiel:
        Für ideology_group:
            center, left, right jeweils separat.

        Für type:
            1.0, 2.0, 3.0 jeweils separat.
    """

    from linearmodels.panel import PanelOLS

    required_cols = [
        DATE_COL,
        VIDEO_ID_COL,
        CHANNEL_COL,
        VIEW_COL,
        "populism_score_clean",
        group_col,
    ]
    if only_keyword_videos:
        required_cols.append(KEYWORD_COL)

    require_columns(df, required_cols, "run_populism_success_by_group_panel_regressions input")

    work = df.copy()

    if only_keyword_videos:
        work = work[work[KEYWORD_COL]].copy()

    work = work[
        work["populism_score_clean"].notna()
        & work[group_col].notna()
        & work[CHANNEL_COL].notna()
        & work[DATE_COL].notna()
    ].copy()

    work[VIEW_COL] = pd.to_numeric(work[VIEW_COL], errors="coerce")
    work = work[work[VIEW_COL].notna()].copy()

    if min_views > 0:
        work = work[work[VIEW_COL] >= min_views].copy()

    if work.empty:
        print(f"[Warnung] Keine Daten für separate Gruppen-Regressionen mit {group_col}.")
        return

    work[DATE_COL] = pd.to_datetime(work[DATE_COL]).dt.tz_localize(None)
    work[CHANNEL_COL] = work[CHANNEL_COL].astype(str)
    work[group_col] = work[group_col].astype(str)

    work["month"] = work[DATE_COL].dt.to_period("M").dt.to_timestamp()
    work["log_views"] = np.log1p(work[VIEW_COL])
    work["post"] = (work[DATE_COL] >= pd.to_datetime(EVENT_DATE)).astype(int)
    work["pop_x_post"] = work["populism_score_clean"] * work["post"]

    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 80)
    print(f"SEPARATE PANEL-REGRESSIONEN PRO GRUPPE | group_col = {group_col}")
    print("=" * 80)

    group_counts = (
        work.groupby(group_col, observed=True)
        .agg(
            n_videos=(VIDEO_ID_COL, "count"),
            n_channels=(CHANNEL_COL, "nunique"),
            n_months=("month", "nunique"),
            mean_populism=("populism_score_clean", "mean"),
            median_views=(VIEW_COL, "median"),
        )
        .reset_index()
    )

    print("\nGruppenübersicht:")
    print(group_counts.to_string(index=False))

    overview_path = output_dir / f"by_group_regression_sample_overview_{group_col}_{TIME_UNIT}.csv"
    group_counts.to_csv(overview_path, index=False)
    print(f"Gruppenübersicht gespeichert: {overview_path}")

    all_rows = []

    models = {
        "P1_FE_basic": ["populism_score_clean"],
        "P2_FE_post": ["populism_score_clean", "pop_x_post"],
    }

    def fit_one_group_model(
        group_value: str,
        group_df: pd.DataFrame,
        model_name: str,
        x_cols: list[str],
    ) -> None:
        nonlocal all_rows

        model_df = group_df[[CHANNEL_COL, "month", "log_views", *x_cols]].dropna().copy()

        n_videos = len(model_df)
        n_channels = model_df[CHANNEL_COL].nunique()
        n_months = model_df["month"].nunique()

        if n_videos < min_videos_per_group or n_channels < min_channels_per_group:
            print(
                f"[Übersprungen] {group_col}={group_value}, {model_name}: "
                f"zu wenig Daten: n_videos={n_videos}, n_channels={n_channels}"
            )
            return

        model_df = model_df.set_index([CHANNEL_COL, "month"]).sort_index()

        y = model_df["log_views"]
        X = model_df[x_cols]

        print("\n" + "-" * 80)
        print(f"{model_name} | {group_col} = {group_value}")
        print(f"N Videos: {n_videos:,} | N Channels: {n_channels:,} | N Months: {n_months:,}")
        print(f"X: {x_cols}")
        print("-" * 80)

        try:
            mod = PanelOLS(
                y,
                X,
                entity_effects=True,
                time_effects=True,
                drop_absorbed=True,
                check_rank=False,
            )

            res = mod.fit(
                cov_type="clustered",
                cluster_entity=True,
            )

            print(res.summary)

            coef_table = pd.DataFrame({
                "group_col": group_col,
                "group_value": str(group_value),
                "model": model_name,
                "term": res.params.index,
                "coef": res.params.values,
                "std_err": res.std_errors.values,
                "p_value": res.pvalues.values,
                "ci_low": res.conf_int().iloc[:, 0].values,
                "ci_high": res.conf_int().iloc[:, 1].values,
                "nobs": res.nobs,
                "n_channels": n_channels,
                "n_months": n_months,
                "rsquared_within": res.rsquared_within,
            })

            all_rows.append(coef_table)

            coef_path = (
                output_dir
                / f"by_group_panel_regression_{model_name}_{group_col}_{safe_group_label(group_value)}_{TIME_UNIT}.csv"
            )
            coef_table.to_csv(coef_path, index=False)
            print(f"Koeffizienten gespeichert: {coef_path}")

        except Exception as e:
            print(f"[Fehler] {model_name} für {group_col}={group_value} konnte nicht geschätzt werden: {e}")

    groups = get_groups(work, group_col)

    for group_value in groups:
        group_df = work[work[group_col] == str(group_value)].copy()

        for model_name, x_cols in models.items():
            fit_one_group_model(
                group_value=str(group_value),
                group_df=group_df,
                model_name=model_name,
                x_cols=x_cols,
            )

    if all_rows:
        all_coefs = pd.concat(all_rows, ignore_index=True)

        all_path = output_dir / f"by_group_panel_regression_all_models_{group_col}_{TIME_UNIT}.csv"
        all_coefs.to_csv(all_path, index=False)
        print(f"\nAlle separaten Gruppen-Koeffizienten gespeichert: {all_path}")

        # Kompakte Übersicht: eine Zeile pro Gruppe x Modell x Term
        compact = all_coefs[
            all_coefs["term"].isin(["populism_score_clean", "pop_x_post"])
        ].copy()

        compact_path = output_dir / f"by_group_panel_regression_key_terms_{group_col}_{TIME_UNIT}.csv"
        compact.to_csv(compact_path, index=False)
        print(f"Zentrale separate Gruppen-Koeffizienten gespeichert: {compact_path}")

        print("\nKompakte Ergebnisübersicht:")
        print(
            compact[
                [
                    "group_value",
                    "model",
                    "term",
                    "coef",
                    "std_err",
                    "p_value",
                    "ci_low",
                    "ci_high",
                    "nobs",
                    "n_channels",
                ]
            ].to_string(index=False)
        )

# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    warnings.filterwarnings("ignore", category=FutureWarning)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    period_freq, range_freq = get_freqs(TIME_UNIT)
    time_label = get_time_label(TIME_UNIT)

    print("\n" + "=" * 80)
    print("NAHOST DESCRIPTIVE ANALYSIS")
    print("=" * 80)
    print(f"TIME_UNIT: {TIME_UNIT} -> pandas freq: {period_freq}")
    print(f"EVENT_DATE: {EVENT_DATE}")
    print(f"INCLUDE_SHORTS: {INCLUDE_SHORTS}")
    print(f"OUTPUT_DIR: {OUTPUT_DIR}")

    df = load_and_prepare_base_data()

    # Speichere vollständigen Arbeitsdatensatz mit Flags/Scores
    prepared_path = OUTPUT_DIR / f"prepared_video_level_data_{TIME_UNIT}.csv"
    df.to_csv(prepared_path, index=False)
    print(f"\nPrepared video-level data gespeichert: {prepared_path}")

    for group_col in GROUPINGS:
        print("\n" + "=" * 80)
        print(f"GRUPPIERUNG: {group_col}")
        print("=" * 80)

        if group_col not in df.columns:
            print(f"[Warnung] Gruppierungsspalte {group_col} fehlt. Überspringe.")
            continue

        print_group_diagnostics(df, group_col)

        channel_panel = build_channel_period_panel(df, group_col=group_col, freq=period_freq)
        group_summary = build_group_period_summary(
            df,
            group_col=group_col,
            period_freq=period_freq,
            range_freq=range_freq,
        )
        # CSVs speichern
        safe_name = safe_group_label(group_col)
        channel_panel_path = OUTPUT_DIR / f"channel_period_panel_{safe_name}_{TIME_UNIT}.csv"
        group_summary_path = OUTPUT_DIR / f"group_period_summary_{safe_name}_{TIME_UNIT}.csv"

        channel_panel.to_csv(channel_panel_path, index=False)
        group_summary.to_csv(group_summary_path, index=False)

        print(f"Channel-period panel gespeichert: {channel_panel_path}")
        print(f"Group-period summary gespeichert: {group_summary_path}")

        # Figures
        plot_figure_1_agenda(
            group_summary,
            group_col=group_col,
            time_label=time_label,
            output_dir=OUTPUT_DIR,
        )

        plot_figure_2_populism(
            group_summary,
            group_col=group_col,
            time_label=time_label,
            output_dir=OUTPUT_DIR,
        )

        plot_keyword_populism_channel_deviation(
            df,
            group_col=group_col,
            output_dir=OUTPUT_DIR,
            min_keyword_videos_per_period=3,
        )

        plot_figure_3_success(
            group_summary,
            group_col=group_col,
            time_label=time_label,
            output_dir=OUTPUT_DIR,
        )

        plot_keyword_view_overperformance(
            df,
            group_col=group_col,
            output_dir=OUTPUT_DIR,
            min_channel_videos_per_period=5,
            min_channel_keyword_videos_per_period=1,
            clip_lift_at=10.0,
        )

        plot_channel_view_lift_boxplot(
            df,
            group_col=group_col,
            output_dir=OUTPUT_DIR,
            min_pre_videos=20,
            min_post_videos=20,
            min_pre_keyword_videos=1,
            min_post_keyword_videos=1,
            clip_lift_at=10.0,
        )

        plot_optional_channel_spread(
            group_summary,
            group_col=group_col,
            time_label=time_label,
            output_dir=OUTPUT_DIR,
        )

        plot_channel_change_boxplot(
            df,
            group_col=group_col,
            output_dir=OUTPUT_DIR,
            min_pre_videos=20,
            min_post_videos=20,
        )

        plot_keyword_view_audience_shift(
            df,
            group_col=group_col,
            output_dir=OUTPUT_DIR,
            min_keyword_views_per_period=1,
        )

        run_populism_success_panel_regressions(
            df,
            group_col=group_col,
            output_dir=OUTPUT_DIR,
            only_keyword_videos=True,
            min_views=0,
        )

        run_populism_success_by_group_panel_regressions(
            df,
            group_col=group_col,
            output_dir=OUTPUT_DIR,
            only_keyword_videos=True,
            min_views=0,
            min_videos_per_group=30,
            min_channels_per_group=3,
        )

    print("\nFertig.")


if __name__ == "__main__":
    main()
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

2. A JSON file containing ALL videos uploaded by the channels.

3. A JSON file containing only KEYWORD videos uploaded by the channels.

Outputs (written to OUTPUT_DIR)
--------------------------------
- relative_activity_general_*.png
- relative_activity_keyword_*.png
- Plus the total/avg absolute counts as CSV for deep dives.

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

# NEU: Pfade für beide JSON Dateien
JSON_ALL_VIDEOS_PATH = SAMPLES / "combined" / "all_videos_50k_channels.json"
JSON_KEYWORD_VIDEOS_PATH = SAMPLES / "combined" / "keyword_videos_50k_channels.json"

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
STRIP_WHITESPACE = True
CASE_SENSITIVE_MATCH = True

# --- Time range & Baseline ---------------------------------------------------
START_DATE = "2023-07-07"
END_DATE = "2025-12-31"

EVENT_DATE = "2023-10-07"
BASELINE_START = "2023-07-07"  # 3 Monate vor dem Event

# --- Time resolution ------------------------------------------------------------
TIME_RESOLUTION = "W"

# --- Grouping thresholds (0-10 scale) ---------------------------------------
IDEOLOGY_BINS = [-0.01, 4.5, 5.49, 10.01]
IDEOLOGY_LABELS = ["Links", "Mitte", "Rechts"]

POPULISM_BINS = [-0.01, 3, 7, 10.01]
POPULISM_LABELS = ["Niedrig", "Mittel", "Hoch"]


# =============================================================================
# DATA LOADING
# =============================================================================

def _build_match_key(series: pd.Series) -> pd.Series:
    key = series.astype(str)
    if STRIP_WHITESPACE:
        key = key.str.strip()
    if not CASE_SENSITIVE_MATCH:
        key = key.str.lower()
    return key


def add_group_columns(channels_df: pd.DataFrame) -> pd.DataFrame:
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


def load_channels(path) -> pd.DataFrame:
    df = pd.read_excel(path)

    required = [EXCEL_CHANNEL_NAME_COLUMN, EXCEL_IDEOLOGY_COLUMN, EXCEL_POPULISM_COLUMN]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing column(s) in Excel: {missing}")

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

    duplicated = df["channel_name_key"].duplicated(keep="first")
    if duplicated.any():
        df = df.loc[~duplicated].copy()

    df = add_group_columns(df)
    return df


def load_videos(path) -> pd.DataFrame:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    df = pd.DataFrame(raw)

    df = df.rename(
        columns={
            JSON_CHANNEL_NAME_FIELD: "channel_name",
            JSON_TITLE_FIELD: "video_id",
            JSON_DATE_FIELD: "publish_date",
        }
    )

    df["channel_name"] = df["channel_name"].astype(str)
    if STRIP_WHITESPACE:
        df["channel_name"] = df["channel_name"].str.strip()
    df["channel_name_key"] = _build_match_key(df["channel_name"])

    df["publish_date"] = pd.to_datetime(df["publish_date"], errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=["publish_date"])

    print("\n=== LOAD DEBUG ===")
    print(df.columns)
    print(df.head())

    print("\nVideoanzahl pro Kanal:")
    print(
        df.groupby("channel_name")
        .size()
        .sort_values(ascending=False)
        .head(20)
    )

    print("==================\n")
    return df


def merge_and_filter(videos_df: pd.DataFrame, channels_df: pd.DataFrame, start_date: str, end_date: str):
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
    raw_unmatched = in_range.loc[unmatched_mask, "channel_name"].dropna().unique()
    unmatched_channels = sorted([str(name) for name in raw_unmatched])

    print("\n=== MERGE DEBUG ===")
    print("Spalten:")
    print(merged.columns)

    print("\nHead:")
    print(merged.head())

    print("\nKanalhäufigkeiten:")
    print(
        merged["channel_name"]
        .value_counts()
        .head(20)
    )

    print("\nAnzahl eindeutiger Kanäle:")
    print(merged["channel_name"].nunique())

    print("====================\n")

    return merged, unmatched_channels


# =============================================================================
# AGGREGATION
# =============================================================================

def aggregate_activity(merged_df: pd.DataFrame, channels_df: pd.DataFrame, group_col: str,
                       group_labels: list, resolution: str, start_date: str, end_date: str):
    print("\n=== AGGREGATION INPUT DEBUG ===")

    print("merged_df shape:", merged_df.shape)

    print("\nSpalten:")
    print(merged_df.columns)

    print("\nHead:")
    print(merged_df.head())

    print("\nVideos pro Kanal:")
    print(
        merged_df.groupby("channel_name")
        .size()
        .sort_values(ascending=False)
        .head(20)
    )

    print("\nVideos pro Kanal und Woche:")
    tmp = (
        merged_df.groupby(
            [pd.Grouper(key="publish_date", freq=resolution),
             "channel_name"]
        )
        .size()
        .sort_values(ascending=False)
    )

    print(tmp.head(50))

    print("===============================\n")

    video_count = (
        merged_df.groupby(
            [pd.Grouper(key="publish_date", freq=resolution), group_col]
        )
        .size()
    )

    channel_count = (
        merged_df.groupby(
            [pd.Grouper(key="publish_date", freq=resolution), group_col]
        )["channel_name"]
        .nunique()
    )

    grouped = pd.concat(
        [video_count, channel_count],
        axis=1
    ).reset_index()

    grouped.columns = [
        "publish_date",
        group_col,
        "video_count",
        "number_of_channels"
    ]
    print("\n=== GROUPED DEBUG ===")
    print(grouped.head(30))

    print(
        (grouped["video_count"] ==
         grouped["number_of_channels"]).value_counts()
    )

    print("=====================\n")

    print(grouped.head(20))
    print(
        (grouped["video_count"] == grouped["number_of_channels"]).value_counts()
    )
    channels_per_group = channels_df[group_col].value_counts()

    pivot_total = grouped.pivot(index="publish_date", columns=group_col, values="video_count").fillna(0)
    pivot_channels = grouped.pivot(index="publish_date", columns=group_col, values="number_of_channels").fillna(0)

    print("\n=== PIVOT DEBUG ===")

    print("\npivot_total:")
    print(pivot_total.head())

    print("\npivot_channels:")
    print(pivot_channels.head())

    print("\nDifferenz:")
    print((pivot_total - pivot_channels).head())

    print("===================\n")

    pivot_total = pivot_total.reindex(columns=group_labels, fill_value=0)
    pivot_channels = pivot_channels.reindex(columns=group_labels, fill_value=0)

    pivot_avg = pivot_total.divide(channels_per_group.replace(0, pd.NA), axis=1)

    # =========================================================================
    # REPARIERT: Richtige Reihenfolge für das wöchentliche Verschieben
    # =========================================================================
    if resolution == "W":
        # 1. Die echten Daten zuerst von Sonntag auf Montag schieben
        pivot_total.index = pivot_total.index - pd.Timedelta(days=6)
        pivot_avg.index = pivot_avg.index - pd.Timedelta(days=6)
        pivot_channels.index = pivot_channels.index - pd.Timedelta(days=6)

        # 2. Die lückenlose Zeitreihe ebenfalls als Montags-Reihe generieren
        full_date_range = pd.date_range(start=start_date, end=end_date, freq=resolution) - pd.Timedelta(days=6)

        # 3. Jetzt reindexen (jetzt matchen Montage auf Montage!)
        pivot_total = pivot_total.reindex(index=full_date_range, fill_value=0)
        pivot_avg = pivot_avg.reindex(index=full_date_range, fill_value=0)
        pivot_channels = pivot_channels.reindex(index=full_date_range, fill_value=0)

        pivot_total.index.name = "week_start"
        pivot_avg.index.name = "week_start"
        pivot_channels.index.name = "week_start"

    else:
        # Falls du irgendwann mal "D" (Tage) oder "M" (Monate) nutzt
        full_date_range = pd.date_range(start=start_date, end=end_date, freq=resolution)
        pivot_total = pivot_total.reindex(index=full_date_range, fill_value=0)
        pivot_avg = pivot_avg.reindex(index=full_date_range, fill_value=0)
        pivot_channels = pivot_channels.reindex(index=full_date_range, fill_value=0)

    return pivot_total, pivot_avg, pivot_channels


def compute_baselines_and_relatives(pivot_avg_all: pd.DataFrame, pivot_avg_kw: pd.DataFrame):
    """
    Berechnet die Baseline der *generellen* Aktivität (3 Monate vor Event)
    und teilt beide Datensätze durch diese Baseline.
    """
    baseline_start_ts = pd.Timestamp(BASELINE_START)
    event_date_ts = pd.Timestamp(EVENT_DATE) - pd.Timedelta(days=1)

    # Baseline: Generelle Uploadaktivität im definierten Fenster
    baseline_mask = (pivot_avg_all.index >= baseline_start_ts) & (pivot_avg_all.index <= event_date_ts)
    baseline = pivot_avg_all.loc[baseline_mask].mean()

    # Vermeidung von Division durch Null
    baseline_safe = baseline.replace(0, pd.NA)

    # 1. Relative generelle Uploadaktivität
    relative_general = pivot_avg_all.divide(baseline_safe)

    # 2. Relative Keyword Uploadaktivität (Keyword-Uploads / generelle Upload-Baseline)
    relative_keyword = pivot_avg_kw.divide(baseline_safe)

    return relative_general, relative_keyword, baseline


# =============================================================================
# PLOTTING
# =============================================================================

def plot_relative_activity(relative_activity: pd.DataFrame, label: str,
                           activity_type: str, output_dir: str):
    fig, ax = plt.subplots(figsize=(12, 6))

    relative_activity.plot(ax=ax, linewidth=1, marker = "o", markersize = 2)

    #ax.axvline(pd.Timestamp(EVENT_DATE), color="red", linestyle="--", linewidth=2, label="7 Oct 2023")

    # Für die generelle Grafik ist die Baseline-Linie bei 1.0 sinnvoll
    if activity_type == "general":
        ax.axhline(1, color="black", linestyle=":", alpha=0.7, label="Baseline (Generell)")

    ax.set_ylabel(f"Relative Aktivität ({activity_type})")
    ax.set_xlabel("Datum")

    title_desc = "Gesamte Uploadaktivität" if activity_type == "general" else "Keyword-Video Uploadaktivität"
    ax.set_title(
        f"{title_desc} nach {label} Gruppe\n"
        "(Referenz: Generelle Uploadaktivität vor dem 7. Okt 2023)"
    )

    ax.grid(alpha=0.3)
    ax.legend()

    fig.tight_layout()

    filename = f"relative_activity_{activity_type}_by_{label}.png"
    out_path = os.path.join(output_dir, filename)

    fig.savefig(out_path, dpi=300)
    plt.close(fig)

    print(f"Saved plot: {out_path}")


def plot_channel_activity(pivot_channels: pd.DataFrame, label: str,
                          activity_type: str, output_dir: str):
    """
    Plottet die absolute Anzahl der einzigartigen Kanäle, die pro Woche aktiv waren.
    """
    fig, ax = plt.subplots(figsize=(12, 6))

    # Wir plotten die absoluten Zahlen direkt mit Markern für die Montage
    pivot_channels.plot(ax=ax, linewidth=1, marker="o", markersize=2)

    # Die rote Linie für den 7. Oktober
    #ax.axvline(pd.Timestamp(EVENT_DATE), color="red", linestyle="--", linewidth=2, label="7 Oct 2023")

    ax.set_ylabel("Anzahl aktiver Kanäle (einzigartig)")
    ax.set_xlabel("Wochenstart (Montag)")

    title_desc = "Einzigartige aktive Kanäle (Gesamt)" if activity_type == "general" else "Einzigartige aktive Kanäle (Keyword-Videos)"
    ax.set_title(
        f"{title_desc} nach {label} Gruppe\n"
        "(Kanäle mit mindestens 1 Upload in der jeweiligen Woche)"
    )

    ax.grid(alpha=0.3)
    ax.legend()

    fig.tight_layout()

    filename = f"active_channels_{activity_type}_by_{label}.png"
    out_path = os.path.join(output_dir, filename)

    fig.savefig(out_path, dpi=300)
    plt.close(fig)

    print(f"Saved channel plot: {out_path}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Loading channels from '{EXCEL_PATH}' ...")
    channels_df = load_channels(EXCEL_PATH)

    # 1. Alle Videos laden
    print(f"Loading ALL videos from '{JSON_ALL_VIDEOS_PATH}' ...")
    videos_all_df = load_videos(JSON_ALL_VIDEOS_PATH)
    merged_all_df, _ = merge_and_filter(videos_all_df, channels_df, START_DATE, END_DATE)

    print("\n=== ALL DATASET DEBUG ===")

    print("Videos:", len(merged_all_df))
    print("Kanäle:", merged_all_df["channel_name"].nunique())

    print(
        merged_all_df.groupby(
            [pd.Grouper(key="publish_date", freq="W")]
        ).agg(
            videos=("title", "size"),
            channels=("channel_name", "nunique")
        ).head(20)
    )

    print("==========================\n")

    # 2. Keyword Videos laden
    print(f"Loading KEYWORD videos from '{JSON_KEYWORD_VIDEOS_PATH}' ...")
    videos_kw_df = load_videos(JSON_KEYWORD_VIDEOS_PATH)
    merged_kw_df, unmatched_channels = merge_and_filter(videos_kw_df, channels_df, START_DATE, END_DATE)

    agg_dict = {
        "channel_name_key": "count",
        "ideology_group": "first",
        "populism_group": "first"
    }
    merged_kw_df_grouped = (merged_kw_df.groupby([pd.Grouper(key="publish_date", freq=TIME_RESOLUTION),"channel_name"
                                                ]).agg(agg_dict).reset_index())

    merged_kw_df_grouped.to_csv("merged_kw_grouped_channel.csv", index = False)
    merged_kw_channel = merged_kw_df_grouped.groupby("channel_name").agg(
        video_count = ("channel_name_key", "sum"),
        ideology = ("ideology_group","first")
    ).reset_index()
    merged_kw_channel.to_csv("merged_kw_channel.csv", index =False)

    merged_kw_ideology = merged_kw_df.groupby(["ideology_group", pd.Grouper(key="publish_date", freq=TIME_RESOLUTION)]).agg(
        video_count = ("channel_name_key", "size"),
        channel_count = ("channel_name_key", "nunique")
    ).reset_index()
    print("Nach Groupby:", merged_kw_ideology.head())
    merged_kw_ideology = merged_kw_ideology.pivot(index = "publish_date", columns = "ideology_group", values = "channel_count").fillna(0)
    print("Nach Pivot (vor reset_index):\n", merged_kw_ideology.head())
    merged_kw_ideology = merged_kw_ideology.reset_index()
    merged_kw_ideology.to_csv("merged_ideology.csv", index=False)
    merged_kw_ideology = merged_kw_ideology[merged_kw_ideology["Links"] >= merged_kw_ideology["Rechts"]]
    merged_kw_ideology.to_csv("merged_ideology_left.csv", index = False)
    grouping_configs = [
        ("ideology_group", IDEOLOGY_LABELS, "Ideologie"),
        #("populism_group", POPULISM_LABELS, "Populismus"),
    ]

    print("\n=== CODELOCK-DIAGNOSE ===")
    print(f"Anzahl Kanäle laut Excel-Datei: {channels_df['channel_name_key'].nunique()}")
    print(f"Gesamte Zeilen (Videos) in merged_kw_df: {len(merged_kw_df)}")
    print(f"Einzigartige Kanäle in merged_kw_df: {merged_kw_df['channel_name_key'].nunique()}")

    # Teste eine Stichprobe aus der Aggregation
    test_counts = merged_kw_df.groupby([pd.Grouper(key="publish_date", freq=TIME_RESOLUTION)]).agg(
        zeilen_count=('title', 'size'),
        kanäle_count=('channel_name_key', 'nunique')
    )
    print("\nStichprobe der Wochen-Aktivität (Rohdaten):")
    print(test_counts.head(5))
    print("=========================\n")

    for group_col, group_labels, label in grouping_configs:
        print(f"\nProcessing Grouping: {label}...")


        # channels_to_remove = ["acTVism Munich", "NachDenkSeiten"]
        # merged_all_df = merged_all_df[~merged_all_df["channel_name"].isin(channels_to_remove)]
        # merged_kw_df = merged_kw_df[~merged_kw_df["channel_name"].isin(channels_to_remove)]
        # Aggregation: Alle Videos
        pivot_all_total, pivot_all_avg, pivot_all_channels = aggregate_activity(
            merged_all_df, channels_df, group_col, group_labels, TIME_RESOLUTION, START_DATE, END_DATE
        )
        pivot_all_channels.to_csv("pivot_channels.csv", index = False)
        pivot_all_total.to_csv("pivot_all.csv", index = False)

        # Aggregation: Keyword Videos
        pivot_kw_total, pivot_kw_avg, pivot_kw_channels = aggregate_activity(
            merged_kw_df, channels_df, group_col, group_labels, TIME_RESOLUTION, START_DATE, END_DATE
        )

        # Baseline und Relatives berechnen
        rel_general, rel_keyword, baseline = compute_baselines_and_relatives(pivot_all_avg, pivot_kw_avg)

        # Plot 1: Generelle Aktivität (relativ zur eigenen Baseline)
        plot_relative_activity(rel_general, label, "general", OUTPUT_DIR)

        # Plot 2: Keyword Aktivität (relativ zur generellen Baseline)
        plot_relative_activity(rel_keyword, label, "keyword", OUTPUT_DIR)

        # Plot 3: Channel activity
        plot_channel_activity(pivot_kw_channels, label, "keyword", OUTPUT_DIR)

    print(f"\nDone. All results were written to '{OUTPUT_DIR}'.")


if __name__ == "__main__":
    main()
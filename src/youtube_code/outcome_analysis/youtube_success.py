import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os
import time

from youtube_code.config import (RAW, CHANNEL_LISTS, SAMPLES, OUTPUT_GEMINI, IDEOLOGY_LABELS, IDEOLOGY_BINS,
                                 POPULISM_BINS, POPULISM_LABELS, KEYWORDS)
from youtube_code.utils import load_json

starting_time = time.perf_counter()

# === PATHS AND CONFIG ===
EVENT_DATE = "2023-10-07"
BASELINE_MONTH = "2023-09"
PLOT_START_DATE = "2022-10-01"

METADATA_INPUT = RAW / "video_metadata_total.jsonl"
METADATA_OUTPUT = SAMPLES / "combined" / "video_metadata_relevant.csv"
CHANNEL_LIST_PATH = CHANNEL_LISTS / "combined" / "channel_list.json"
CLASSIFICATION_PATH = OUTPUT_GEMINI / "channel_results_051.xlsx"


START_DATE = "2022-10"
END_DATE = "2025-12"

# --- Configuration Part 2 (Keyword-Analysis) ---
SUBSCRIBER_COLUMN = "subscribers"
SUBSCRIBER_SOURCE_PATH = CLASSIFICATION_PATH


# === FUNKTIONEN ===

def prepare_metadata(metadata_input, metadata_output, channel_list_path, start_date, end_date):
    """Reads and filters metadata for relevant channels and time period."""

    print("Reading input files...")
    channel_list = load_json(channel_list_path)
    temp_df = pd.read_json(metadata_input, lines=True)

    print("Filtering for channels and period and adjusting duration...")
    temp_df = temp_df[temp_df["channel_id"].isin(channel_list)]
    temp_df['published_at'] = pd.to_datetime(temp_df['published_at'])
    temp_df["month"] = temp_df["published_at"].dt.to_period("M")
    temp_df = temp_df[(temp_df["month"] >= start_date) & (temp_df["month"] <= end_date)]
    temp_df["duration"] = pd.to_timedelta(temp_df["duration"])

    print(f"Videos left in data: {len(temp_df)}")
    temp_df.to_csv(metadata_output, index=False)
    return temp_df


def load_classification(classification_path):
    """Loads channel classification, creates populism/ideology groups."""
    class_df = pd.read_excel(classification_path)
    class_df["ideology_group"] = pd.cut(class_df["ideology_channel_mean"], bins=IDEOLOGY_BINS,
                                         labels=IDEOLOGY_LABELS, include_lowest=True)
    class_df["populism_group"] = pd.cut(class_df["populism_channel_mean"], bins=POPULISM_BINS,
                                         labels=POPULISM_LABELS, include_lowest=True)

    return class_df


def rebase_to_baseline(df_grouped, group_col, value_col, date_col, baseline_month):
    """Normiert value_col pro Gruppe so, dass der Wert im baseline_month = 100 ist."""
    df_grouped = df_grouped.copy()
    baseline_period = pd.Period(baseline_month, freq='M')
    mask = df_grouped[date_col].dt.to_period('M') == baseline_period
    baselines = df_grouped.loc[mask].set_index(group_col)[value_col].astype(float)

    df_grouped[value_col] = df_grouped[value_col].astype(float)
    df_grouped['baseline'] = df_grouped[group_col].map(baselines)
    df_grouped["baseline"] = df_grouped["baseline"].astype(float)
    df_grouped[value_col] = df_grouped[value_col].astype(float)
    df_grouped['relative_pct'] = (df_grouped[value_col] / df_grouped['baseline']) * 100
    return df_grouped


def plot_relative_trend(df_grouped, group_col, date_col, value_col, title, ylabel,
                         plot_start, event_date, baseline_month, smooth = False):
    plot_df = df_grouped[df_grouped[date_col] >= plot_start]
    if smooth:
        plot_df[value_col] = plot_df.groupby(group_col)[value_col].transform(lambda x: x.ewm(span = 3, adjust=False).mean())
    plt.figure(figsize=(14, 7))
    sns.set_theme(style="whitegrid")
    sns.lineplot(data=plot_df, x=date_col, y=value_col, hue=group_col, marker='o', linewidth=2)

    plt.axhline(100, color='red', linestyle='--', linewidth=1.5, label=f'Baseline ({baseline_month} = 100%)')
    plt.axvline(pd.to_datetime(event_date), color='grey', linestyle=':', linewidth=1.5, label='7. Oktober 2023')

    plt.title(title, fontsize=14, pad=15)
    plt.xlabel('Monat', fontsize=12)
    plt.ylabel(ylabel, fontsize=12)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()


def add_subscriber_normalization(df, subscriber_source_path, subscriber_column):
    """Fuegt pro Video die Subscriber-Zahl des Kanals hinzu und berechnet views_per_subscriber."""
    sub_df = pd.read_excel(subscriber_source_path)  # TODO: ggf. read_csv/read_json, je nach Quelle
    df = df.merge(sub_df[["channel_title", subscriber_column]], on="channel_title", how="left")

    missing = df[subscriber_column].isna().sum()
    if missing:
        print(f"Warnung: Fuer {missing} Videos wurde keine Subscriber-Zahl gefunden.")

    df["views_per_subscriber"] = df["view_count"] / df[subscriber_column]
    return df


def keyword_relative_success(df, keyword, group_col, baseline_month,
                              date_col='published_at', value_col='views_per_subscriber'):
    """
    Vergleicht Videos mit `keyword` im Titel mit ALLEN Videos derselben Gruppe
    (= 'allgemeine Baseline'), jeweils subscriber-normiert und auf baseline_month = 100 indexiert.
    """
    df = df.copy()
    df['has_keyword'] = df['title'].str.contains(keyword, case=False, na=False)

    def monthly_mean(sub_df, label):
        out = (
            sub_df.groupby([pd.Grouper(key=date_col, freq='ME'), group_col])[value_col]
            .mean()
            .reset_index()
        )
        out['series'] = label
        return out

    overall = monthly_mean(df, 'Alle Videos')
    keyword_only = monthly_mean(df[df['has_keyword']], f"Videos mit '{keyword}'")

    combined = pd.concat([overall, keyword_only], ignore_index=True)
    combined['group_series'] = combined[group_col].astype(str) + " - " + combined['series']

    combined = rebase_to_baseline(combined, 'group_series', value_col, date_col, baseline_month)
    return combined


# === MAIN ===
if __name__ == "__main__":
    if os.path.exists(METADATA_OUTPUT):
        df = pd.read_csv(METADATA_OUTPUT)
    else:
        df = prepare_metadata(METADATA_INPUT, METADATA_OUTPUT, CHANNEL_LIST_PATH, START_DATE, END_DATE)

    class_df = load_classification(CLASSIFICATION_PATH)
    df = pd.merge(df, class_df[["channel_title", "ideology_group", "populism_group"]],
                  on="channel_title", how="left")
    df['published_at'] = pd.to_datetime(df['published_at']).dt.tz_localize(None)

    # --- Teil 1: Wie haben sich die Gesamtviews je Ideologiegruppe seit dem 7.10.2023 entwickelt? ---
    df_monthly = (
        df.groupby([pd.Grouper(key='published_at', freq='ME'), 'ideology_group'])['view_count']
        .sum()
        .reset_index()
    )
    df_monthly = rebase_to_baseline(df_monthly, 'ideology_group', 'view_count',
                                     'published_at', BASELINE_MONTH)

    plot_relative_trend(
        df_monthly, group_col='ideology_group', date_col='published_at', value_col='relative_pct',
        title='Verlauf der monatlichen Gesamtviews relativ zur Baseline (nach Ideologiegruppe)',
        ylabel=f'Views relativ zu {BASELINE_MONTH} (%)',
        plot_start=PLOT_START_DATE, event_date=EVENT_DATE, baseline_month=BASELINE_MONTH, smooth= True
    )

    # --- Teil 2: Schneiden Videos mit einem bestimmten Keyword im Titel besser/schlechter ab
    #             als die allgemeine Baseline (subscriber-normiert)? ---
    # df = add_subscriber_normalization(df, SUBSCRIBER_SOURCE_PATH, SUBSCRIBER_COLUMN)
    #
    # keyword_df = keyword_relative_success(
    #     df, keyword=KEYWORD, group_col='ideology_group', baseline_month=BASELINE_MONTH
    # )
    #
    # plot_relative_trend(
    #     keyword_df, group_col='group_series', date_col='published_at', value_col='relative_pct',
    #     title=f"Erfolg von Videos mit Keyword '{KEYWORD}' vs. allgemeine Baseline (subscriber-normiert)",
    #     ylabel=f'Views/Subscriber relativ zu {BASELINE_MONTH} (%)',
    #     plot_start=PLOT_START_DATE, event_date=EVENT_DATE, baseline_month=BASELINE_MONTH
    # )

end_time = time.perf_counter()
script_duration = end_time - starting_time
print(f"Duration of code execution: {script_duration:.2f}")
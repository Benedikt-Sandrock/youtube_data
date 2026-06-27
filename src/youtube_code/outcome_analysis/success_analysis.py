import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os
import re
import time

from youtube_code.config import (RAW, CHANNEL_LISTS, SAMPLES, OUTPUT_GEMINI, IDEOLOGY_LABELS, IDEOLOGY_BINS,
                                 POPULISM_BINS, POPULISM_LABELS, KEYWORDS)
from youtube_code.utils import load_json

starting_time = time.perf_counter()

# === PATHS AND CONFIG ===
EVENT_DATE = "2023-10-07"
BASELINE_MONTH = "2023-09"          # letzter Monat des Baseline-Zeitraums
BASELINE_WINDOW_MONTHS = 3          # Anzahl Monate rueckwaerts ab BASELINE_MONTH (inkl.)
                                     # 1 = nur dieser Monat; 3 = dieser Monat + die 2 davor usw.
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

# --- Configuration Teil 1c (Gewichtungsvergleich) ---
WEIGHT_POWER = 0.5  # Kompromiss zwischen Equal-Weighted (0) und Value-Weighted (1)


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


def format_baseline_label(baseline_month, baseline_window_months=1):
    """Formatiert den Baseline-Zeitraum fuer Plot-Legenden, z.B. '2023-09' oder '2023-07 bis 2023-09'."""
    if baseline_window_months <= 1:
        return str(baseline_month)
    end_period = pd.Period(baseline_month, freq='M')
    start_period = end_period - (baseline_window_months - 1)
    return f"{start_period} bis {end_period}"


def rebase_to_baseline(df_grouped, group_col, value_col, date_col, baseline_month,
                        baseline_window_months=1, baseline_mask=None):
    """
    Normiert value_col pro Gruppe so, dass der Durchschnitt im Baseline-Zeitraum = 100 ist.

    baseline_window_months: Anzahl Monate, die in die Baseline einfliessen, gezaehlt
    RUECKWAERTS ab baseline_month (inklusive). 1 = nur baseline_month selbst, 3 = baseline_month
    und die zwei Monate davor usw. Geht bewusst nur rueckwaerts, damit die Baseline nie ins
    Post-Event-Gebiet (nach dem 7.10.) rutscht. Ein Fenster > 1 macht die Baseline robuster
    gegenueber Einzelmonats-Ausreissern (z.B. ein Kanal ohne Upload genau im Referenzmonat).

    baseline_mask: optionale boolesche Maske auf df_grouped. Schraenkt zusaetzlich ein, aus
    welchen Zeilen die Baseline berechnet wird (z.B. nur die 'Alle Videos'-Zeilen, nicht die
    'Keyword Videos'-Zeilen). Die berechnete Baseline wird trotzdem auf ALLE Zeilen der
    jeweiligen Gruppe angewendet (auch auf die, die durch die Maske ausgeschlossen wurden).
    """
    df_grouped = df_grouped.copy()
    end_period = pd.Period(baseline_month, freq='M')
    start_period = end_period - (baseline_window_months - 1)

    months = df_grouped[date_col].dt.to_period('M')
    month_mask = (months >= start_period) & (months <= end_period)

    if baseline_mask is not None:
        month_mask = month_mask & baseline_mask

    baselines = df_grouped.loc[month_mask].groupby(group_col)[value_col].mean().astype(float)
    baselines = baselines.replace(0, pd.NA)

    df_grouped[value_col] = df_grouped[value_col].astype(float)
    df_grouped['baseline'] = df_grouped[group_col].map(baselines)
    df_grouped['baseline'] = df_grouped['baseline'].astype(float)
    df_grouped['relative_pct'] = (df_grouped[value_col] / df_grouped['baseline']) * 100
    return df_grouped


def weighted_relative_trend(df, group_col, baseline_month, baseline_window_months=1,
                             date_col='published_at', value_col='view_count', weight_power=0.0):
    """
    Berechnet fuer JEDEN KANAL eine eigene Baseline (statt einer gemeinsamen Gruppen-Baseline)
    und bildet anschliessend pro Gruppe einen GEWICHTETEN Durchschnitt ueber die Wachstums-
    Indizes aller zugehoerigen Kanaele. Gewicht eines Kanals = (eigene Baseline) ** weight_power:

        weight_power = 0   -> alle Kanaele gleich gewichtet (reiner Equal-Weighted Index;
                               Wachstum kleiner Kanaele geht nicht mehr in der Gruppensumme unter)
        weight_power = 1   -> Gewicht = Baseline-Views direkt. Das ist rechnerisch (fast)
                               identisch zum Verhaeltnis der GRUPPENSUMMEN (= "value-weighted",
                               Teil 1) - eine reine Groessen-Gewichtung fuehrt also wieder fast
                               zum Ausgangsproblem zurueck.
        weight_power = 0.5 -> Kompromiss (Wurzel-Gewichtung): grosse Kanaele zaehlen mehr als
                               kleine, aber nicht proportional zu ihrer vollen Groesse.

    Kanaele ohne Videos im Baseline-Zeitraum bekommen keine Baseline (NaN) und werden komplett
    ausgeschlossen (auch aus dem Gewicht) - wie viele das betrifft, wird ausgegeben.
    """
    df_channel_monthly = (
        df.groupby([pd.Grouper(key=date_col, freq='ME'), 'channel_title', group_col])[value_col]
        .sum()
        .reset_index()
    )

    df_channel_monthly = rebase_to_baseline(df_channel_monthly, 'channel_title', value_col,
                                             date_col, baseline_month,
                                             baseline_window_months=baseline_window_months)

    n_total = df_channel_monthly['channel_title'].nunique()
    valid = df_channel_monthly.dropna(subset=['relative_pct']).copy()
    n_valid = valid['channel_title'].nunique()
    if n_valid < n_total:
        baseline_label = format_baseline_label(baseline_month, baseline_window_months)
        print(f"Weighted Index (power={weight_power}, {value_col}): {n_total - n_valid} von "
              f"{n_total} Kanaelen ohne Baseline im Zeitraum ({baseline_label}) werden ausgeschlossen.")

    valid['weight'] = valid['baseline'] ** weight_power
    valid['weighted_value'] = valid['relative_pct'] * valid['weight']

    agg = (
        valid.groupby([date_col, group_col])
        .agg(weighted_value_sum=('weighted_value', 'sum'), weight_sum=('weight', 'sum'))
        .reset_index()
    )
    agg['relative_pct'] = agg['weighted_value_sum'] / agg['weight_sum']
    return agg[[date_col, group_col, 'relative_pct']]





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


def plot_keyword_focus_trend(df_grouped, group_col, series_col, focus_series, date_col, value_col,
                              title, ylabel, plot_start, event_date, baseline_month, smooth=False):
    """
    Spezieller Plot fuer die Keyword-Analyse: Farbe = Ideologiegruppe (gleiche Farbe fuer
    Keyword-Linie und zugehoerige 'Alle Videos'-Linie -> leicht zuordenbar). Die Keyword-Serie
    (focus_series) wird dick und durchgezogen dargestellt (Fokus), die jeweilige Baseline-Serie
    ('Alle Videos') duenn, gestrichelt und transparenter im Hintergrund.
    """
    plot_df = df_grouped[df_grouped[date_col] >= plot_start].copy()

    if smooth:
        plot_df[value_col] = (
            plot_df.groupby([group_col, series_col])[value_col]
            .transform(lambda x: x.ewm(span=3, adjust=False).mean())
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
            ax.plot(background[date_col], background[value_col],
                     color=color, linewidth=1.2, linestyle='--', alpha=0.55,
                     label=f"{group} - Alle Videos")
        if not focus.empty:
            ax.plot(focus[date_col], focus[value_col],
                     color=color, linewidth=2.8, linestyle='-', marker='o', markersize=4,
                     label=f"{group} - {focus_series}")

    plt.axhline(100, color='red', linestyle='--', linewidth=1.5, label=f'Baseline ({baseline_month} = 100%)')
    plt.axvline(pd.to_datetime(event_date), color='grey', linestyle=':', linewidth=1.5, label='7. Oktober 2023')

    plt.title(title, fontsize=14, pad=15)
    plt.xlabel('Monat', fontsize=12)
    plt.ylabel(ylabel, fontsize=12)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()


def plot_weighting_comparison(df_combined, group_col, date_col, value_col, weighting_col,
                               plot_start, event_date, baseline_month, smooth=False):
    """
    Facettierter Vergleich mehrerer Gewichtungsschemata (z.B. Equal-/Wurzel-/Value-Weighted):
    ein Subplot pro Gruppe (group_col), darin je eine Linie pro Schema (weighting_col).
    Getrennte Subplots statt einer gemeinsamen Linienflut, weil N Gruppen x M Schemata in
    einem einzigen Plot schnell unleserlich wird.
    """
    plot_df = df_combined[df_combined[date_col] >= plot_start].copy()

    if smooth:
        plot_df[value_col] = (
            plot_df.groupby([group_col, weighting_col])[value_col]
            .transform(lambda x: x.ewm(span=3, adjust=False).mean())
        )

    sns.set_theme(style="whitegrid")
    g = sns.relplot(
        data=plot_df, x=date_col, y=value_col, hue=weighting_col,
        col=group_col, kind='line', marker='o', linewidth=2,
        height=4, aspect=1.3, col_wrap=3, facet_kws={'sharey': False}
    )

    for ax in g.axes.flat:
        ax.axhline(100, color='red', linestyle='--', linewidth=1.2)
        ax.axvline(pd.to_datetime(event_date), color='grey', linestyle=':', linewidth=1.2)
        ax.tick_params(axis='x', rotation=45)

    g.set_titles("{col_name}")
    g.set_axis_labels("Monat", f"relativ zu {baseline_month} (%)")
    g.fig.suptitle("Vergleich der Gewichtungsschemata pro Ideologiegruppe", y=1.02)
    plt.tight_layout()
    plt.show()


def add_subscriber_normalization(df, subscriber_source_path, subscriber_column):
    """Fuegt pro Video die Subscriber-Zahl des Kanals hinzu und berechnet views_per_subscriber."""
    sub_df = pd.read_excel(subscriber_source_path)
    df = df.merge(sub_df[["channel_title", subscriber_column]], on="channel_title", how="left")

    missing = df[df[subscriber_column].isna()]
    if not missing.empty:
        print(f"Warning: Subscriber not for all channels available."
              f"\nExported to 'missing.csv'")
        missing = missing.groupby("channel_title")[subscriber_column].first().reset_index()
        missing.to_csv("missing.csv", index=False)

    df["views_per_subscriber"] = df["view_count"] / df[subscriber_column]
    return df


def keyword_relative_success(df, keywords, group_col, baseline_month, baseline_window_months=1,
                              date_col='published_at', value_col='views_per_subscriber'):
    """
    Vergleicht Videos, deren Titel mind. eines der `keywords` enthaelt, mit ALLEN Videos
    derselben Gruppe, jeweils subscriber-normiert.

    Wichtig: Beide Serien ('Alle Videos' und 'Keyword Videos') werden auf DIESELBE Baseline
    normiert - die von 'Alle Videos' im Baseline-Zeitraum. Eine eigene Keyword-Baseline waere
    unzuverlaessig, weil vor dem Event praktisch keine Videos mit diesen Keywords existieren.
    Der Wert sagt damit direkt: "Wie gut laufen Keyword-Videos verglichen mit einem
    durchschnittlichen Video dieser Gruppe im Referenzzeitraum?" (100 = genauso gut wie normal).
    """
    df = df.copy()
    pattern = "|".join(re.escape(kw) for kw in keywords)
    df['has_keyword'] = df['title'].str.contains(pattern, case=False, na=False, regex=True)

    print("Treffer pro Keyword (ein Video kann mehrere Keywords gleichzeitig enthalten):")
    for kw in keywords:
        n = df['title'].str.contains(re.escape(kw), case=False, na=False, regex=True).sum()
        print(f"  '{kw}': {n}")

    end_period = pd.Period(baseline_month, freq='M')
    start_period = end_period - (baseline_window_months - 1)
    months = df[date_col].dt.to_period('M')
    baseline_label = format_baseline_label(baseline_month, baseline_window_months)
    n_keyword_before = df.loc[df['has_keyword'] & (months >= start_period) & (months <= end_period)].shape[0]
    print(f"Keyword-Videos im Baseline-Zeitraum ({baseline_label}): {n_keyword_before} "
          "-> deshalb wird auf die Baseline von 'Alle Videos' normiert, nicht auf eine eigene.")

    def monthly_mean(sub_df, label):
        out = (
            sub_df.groupby([pd.Grouper(key=date_col, freq='ME'), group_col])[value_col]
            .mean()
            .reset_index()
        )
        out['series'] = label
        return out

    overall = monthly_mean(df, 'Alle Videos')
    keyword_label = "Videos mit Keyword"
    keyword_only = monthly_mean(df[df['has_keyword']], keyword_label)

    combined = pd.concat([overall, keyword_only], ignore_index=True)
    combined['group_series'] = combined[group_col].astype(str) + " - " + combined['series']

    # Baseline NUR aus den 'Alle Videos'-Zeilen berechnen, dann auf beide Serien anwenden:
    combined = rebase_to_baseline(
        combined, group_col, value_col, date_col, baseline_month,
        baseline_window_months=baseline_window_months,
        baseline_mask=(combined['series'] == 'Alle Videos')
    )
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
    df = add_subscriber_normalization(df, SUBSCRIBER_SOURCE_PATH, SUBSCRIBER_COLUMN)
    df_monthly = (
        df.groupby([pd.Grouper(key='published_at', freq='ME'), 'ideology_group'])['view_count']
        .sum()
        .reset_index()
    )

    df_normed_monthly = (
        df.groupby([pd.Grouper(key="published_at", freq='ME'), 'ideology_group'])['views_per_subscriber']
        .sum().reset_index()
    )

    df_monthly_rebased = rebase_to_baseline(df_monthly, 'ideology_group', 'view_count',
                                     'published_at', BASELINE_MONTH)
    df_normed_rebased = rebase_to_baseline(df_normed_monthly, "ideology_group", "views_per_subscriber",
                                           "published_at", BASELINE_MONTH)

    plot_relative_trend(
        df_monthly_rebased, group_col='ideology_group', date_col='published_at', value_col='relative_pct',
        title='Verlauf der monatlichen Gesamtviews relativ zur Baseline (nach Ideologiegruppe)',
        ylabel=f'Views relativ zu {BASELINE_MONTH} (%)',
        plot_start=PLOT_START_DATE, event_date=EVENT_DATE, baseline_month=BASELINE_MONTH, smooth= True
    )

    plot_relative_trend(
        df_normed_rebased, group_col='ideology_group', date_col='published_at', value_col='relative_pct',
        title='Verlauf der monatlichen Gesamtviews relativ zur Baseline (nach Ideologiegruppe)',
        ylabel=f'Views relativ zu {BASELINE_MONTH} (%)',
        plot_start=PLOT_START_DATE, event_date=EVENT_DATE, baseline_month=BASELINE_MONTH, smooth=True
    )

    # --- Teil 1c: Vergleich Equal-/Wurzel-/Value-Weighted Index ---
    # Gleiche Logik (Kanal-eigene Baseline), aber mit unterschiedlicher Gewichtung der
    # Kanaele beim Aggregieren - so sieht man, ob Wachstum vor allem bei kleinen oder
    # bei grossen Kanaelen stattfindet.
    weighting_schemes = [
        (0.0, 'Equal-Weighted'),
        (WEIGHT_POWER, f'Wurzel-gewichtet (power={WEIGHT_POWER})'),
        (1.0, 'Value-Weighted'),
    ]

    comparison_frames = []
    for power, label in weighting_schemes:
        trend = weighted_relative_trend(
            df, group_col='ideology_group', baseline_month=BASELINE_MONTH,
            value_col='view_count', weight_power=power
        )
        trend['weighting'] = label
        comparison_frames.append(trend)

    df_weighting_comparison = pd.concat(comparison_frames, ignore_index=True)

    plot_weighting_comparison(
        df_weighting_comparison, group_col='ideology_group', date_col='published_at',
        value_col='relative_pct', weighting_col='weighting',
        plot_start=PLOT_START_DATE, event_date=EVENT_DATE, baseline_month=BASELINE_MONTH, smooth=True
    )

    # --- Teil 2: Schneiden Videos mit bestimmten Keywords im Titel besser/schlechter ab
    #             als die allgemeine Baseline (subscriber-normiert)? ---
    keyword_df = keyword_relative_success(
        df, keywords=KEYWORDS, group_col='ideology_group', baseline_month=BASELINE_MONTH
    )
    focus_series = [s for s in keyword_df['series'].unique() if s != 'Alle Videos'][0]

    plot_keyword_focus_trend(
        keyword_df, group_col='ideology_group', series_col='series', focus_series=focus_series,
        date_col='published_at', value_col='relative_pct',
        title="Erfolg von Videos mit Keywords vs. allgemeine Baseline (subscriber-normiert)",
        ylabel=f'Views/Subscriber relativ zu {BASELINE_MONTH} (%)',
        plot_start=PLOT_START_DATE, event_date=EVENT_DATE, baseline_month=BASELINE_MONTH, smooth=True
    )



end_time = time.perf_counter()
script_duration = end_time - starting_time
print(f"Duration of code execution: {script_duration:.2f}")
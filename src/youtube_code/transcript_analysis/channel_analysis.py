import pandas as pd
import numpy as np
import matplotlib.pyplot as  plt
import seaborn as sns
from youtube_code.config import EXPLORATION, SAMPLES, OUTPUT_GEMINI

# ===================================================
# CONFIGURATION AND PATHS
# ===================================================

PROMPT_NUMBER = "051"

RESULTS_PATH = OUTPUT_GEMINI / "classification_cot_total" / f"classification_results_{PROMPT_NUMBER}_gemini-2.5-flash.csv"
VIDEOS_PATH = SAMPLES / "cot_50k_channels" / "all_videos_50k_channels_name.json"
OUTPUT_PATH_07 = OUTPUT_GEMINI / "channel_results_07.xlsx"
OUTPUT_PATH_051 = OUTPUT_GEMINI / "channel_results_051.xlsx"

channels_map = {
    "UCjSkyrjqPeMwubZU0CnScXA": "SchrangTV",
    "UCE7b8qctaEGmST38-sfdOsA": "NachDenkSeiten",
    "UCQGqiGhMjc_p4lZEhSTb12g": "NIUS",
    "UCs-G8CXCziErSY1459e7U8A": "Gegenpol",
    "UC5NOEUbkLheQcaaRldYW5GA": "tagesschau",
    "UCgvFsn6bRKqND1cW3HpzDrA": "Compact",
}

# ===================================================
# FUNCTIONS
# ===================================================

def aggregation(results_path, videos_path, output_path):
    df = pd.read_csv(results_path)
    df_videos = pd.read_json(videos_path)

    df = pd.merge(df, df_videos[["video_id", "channel_id", "channel_title"]], on ="video_id", how = "left")
    df = df.drop(columns = ["published_at", "creator_sentiment"], errors = "ignore")
    print(df.columns)

    #df["channel_name"] = df["channel_id"].replace(channels_map)

    df.to_excel("ratings_merged.xlsx", index = False)

    df["ideology_score"] = df["ideology_score"].astype(float)
    df["populism_score"] = df["populism_score"].astype(float)

    df["ideology_minus_one"] = (df["ideology_score"] == -1).astype(int)
    df["populism_minus_one"] = (df["populism_score"] == -1).astype(int)

    minus_one_counts = df.groupby("channel_title").agg(
        total_videos = ("video_id", "count"),
        ideology_minus_1_count = ("ideology_minus_one", "sum"),
        populism_minus_1_count = ("populism_minus_one", "sum")
    ).reset_index()

    minus_one_counts["share_ideology_minus_1"] = minus_one_counts["ideology_minus_1_count"] / minus_one_counts["total_videos"]
    minus_one_counts["share_populism_minus_1"] = minus_one_counts["populism_minus_1_count"] / minus_one_counts["total_videos"]

    df["ideology_score"] = df["ideology_score"].replace(-1, np.nan)
    df["populism_score"] = df["populism_score"].replace(-1, np.nan)

    new_df = df.groupby("channel_title").agg(
        ideology_channel_mean = ("ideology_score", "mean"),
        populism_channel_mean = ("populism_score", "mean"),
        ideology_channel_median = ("ideology_score", "median"),
        populism_channel_median = ("populism_score", "median"),
    ).reset_index()

    r_df = df[df["video_type"] == "Standard"]
    r_df = r_df.groupby("channel_title").agg(
        ideology_channel = ("ideology_score", "mean"),
        populism_channel = ("populism_score", "mean"),
    ).reset_index()

    new_df = pd.merge(new_df, r_df, on = "channel_title", how ="inner")
    new_df = pd.merge(new_df, minus_one_counts[["channel_title", "total_videos", "share_ideology_minus_1", "share_populism_minus_1"]],
                      on= "channel_title", how = "left")

    if PROMPT_NUMBER == "07":
        OUTPUT_PATH = OUTPUT_PATH_07
    if PROMPT_NUMBER == "051":
        OUTPUT_PATH = OUTPUT_PATH_051
    else:
        print("No correct path specified.")
        exit()

    new_df.to_excel(output_path, index = False)


def comparison_stats(output_path_07, output_path_051):
    df_07 = pd.read_excel(output_path_07, usecols = ["channel_title", "ideology_channel_mean", "populism_channel_mean"])
    df_051 = pd.read_excel(output_path_051, usecols = ["channel_title", "ideology_channel_mean", "populism_channel_mean"])

    df = pd.merge(df_07, df_051, on= "channel_title", how = "inner")
    print(f"Number of channels: {len(df)}")
    df["diff_ideology"] = abs(df["ideology_channel_mean_x"] - df["ideology_channel_mean_y"])
    df["diff_populism"] = abs(df["populism_channel_mean_x"] - df["populism_channel_mean_y"])

    print("\n", "="*20, "AGGREGATION STATS", "="*20)
    mean_ideo_07 = df["ideology_channel_mean_x"].mean()
    mean_ideo_051 = df["ideology_channel_mean_y"].mean()
    print(f"Mean ideology 07: {mean_ideo_07}")
    print(f"Mean ideology 051: {mean_ideo_051}")

    mean_pop_07 = df["populism_channel_mean_x"].mean()
    mean_pop_051 = df["populism_channel_mean_y"].mean()
    print(f"Mean populism 07: {mean_pop_07}")
    print(f"Mean populism 051: {mean_pop_051}")

    mean_diff_ideo = df["diff_ideology"].mean()
    mean_diff_pop = df["diff_populism"].mean()
    print(f"Mean abs diff ideology: {mean_diff_ideo}")
    print(f"Mean abs diff populism: {mean_diff_pop}")

    df["dist_ideo_07"] = abs(df["ideology_channel_mean_x"] - 5)
    df["dist_ideo_051"] = abs(df["ideology_channel_mean_y"] - 5)
    mean_dist_ideo_07 = df["dist_ideo_07"].mean()
    mean_dist_ideo_051 = df["dist_ideo_051"].mean()
    print(f"Mean diff from 5 (ideo, 07): {mean_dist_ideo_07}")
    print(f"Mean diff from 5 (ideo, 051): {mean_dist_ideo_051}")
    print("="*60)


def main_graphs(file_path):
    print(f"Creating main graphs for file: {file_path.name}")
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        print(f"Error when loading the file: {e}")
        return

    required_columns = ["channel_title", "ideology_channel_mean", "populism_channel_mean"]
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Column '{col}' missiung in input file.")

    sns.set_theme(style="whitegrid")

    # -----------------------------------------------------------------
    # DISTRIBUTIONS
    # -----------------------------------------------------------------

    # A: Distribution Ideology
    plt.figure(figsize=(8, 5))
    sns.histplot(df['ideology_channel_mean'], kde=True, bins=15, color='skyblue')
    plt.title('Distribution of ideology')
    plt.xlabel('Ideology (0-10)')
    plt.ylabel('Number of channels')
    plt.xlim(0, 10)
    plt.tight_layout()
    plt.show()

    # B: Distribution Populism
    plt.figure(figsize=(8, 5))
    sns.histplot(df['populism_channel_mean'], kde=True, bins=15, color='salmon')
    plt.title('Distribution of populism')
    plt.xlabel('Populism (0-10)')
    plt.ylabel('Number of channels')
    plt.xlim(0, 10)
    plt.tight_layout()
    plt.show()

    # -----------------------------------------------------------------
    # 2. POPULISM BY IDEOLOGY
    # -----------------------------------------------------------------

    # [0, 2.5]   -> Entspricht 0-2 (unten geschlossen durch include_lowest)
    # (2.5, 4.5] -> Entspricht 3-4
    # (4.5, 5.5] -> Entspricht 5
    # (5.5, 7.5] -> Entspricht 6-7
    # (7.5, 10.0]-> Entspricht 8-10
    bins = [0, 2.5, 4.5, 5.5, 7.5, 10.0]
    labels = ['0-2', '3-4', '5', '6-7', '8-10']

    df['ideology_group'] = pd.cut(
        df['ideology_channel_mean'],
        bins=bins,
        labels=labels,
        include_lowest=True
    )

    plt.figure(figsize=(10, 6))
    sns.boxplot(
        x='ideology_group',
        y='populism_channel_mean',
        data=df,
        palette='Set2',
        hue='ideology_group',
        legend=False
    )

    plt.title('Populism by ideology')
    plt.xlabel('Ideology')
    plt.ylabel('Populism (0-10)')
    plt.ylim(0, 10)
    plt.tight_layout()
    plt.show()


def test_graphs(df):
    import matplotlib.pyplot as plt
    import seaborn as sns

    # 2. Styling-Schnittstelle aufsetzen
    sns.set_theme(style="whitegrid")
    plt.figure(figsize=(12, 7))

    # 3. Grafik erstellen (Dichtediagramm / KDE-Plot)
    # 'hue' trennt die Daten nach Kanälen, 'fill=True' füllt die Flächen transparent
    sns.kdeplot(
        data=df,
        x="ideology_score",
        hue="channel_name",
        fill=True,
        common_norm=False,  # Verhindert, dass Kanäle mit weniger Videos winzig wirken
        palette="tab10",  # Schöne, kontrastreiche Farbpalette
        alpha=0.4,  # Transparenz der Flächen
        linewidth=2.5,  # Dicke der Linien
    )

    # 4. Achsen und Titel beschriften
    plt.title(
        "Vergleich der Ideologie-Bewertungen nach YouTube-Kanal",
        fontsize=16,
        fontweight="bold",
        pad=20,
    )
    plt.xlabel("Ideology Score (Skala 1 - 10)", fontsize=12, labelpad=10)
    plt.ylabel("Dichte (Häufigkeit)", fontsize=12, labelpad=10)

    # X-Achse auf deine Skala von 1 bis 10 einschränken mit Schritten
    plt.xlim(1, 10)
    plt.xticks(range(1, 11))

    # Layout optimieren und anzeigen
    plt.tight_layout()
    plt.show()


    plt.figure(figsize=(12, 7))

    # 3. Grafik erstellen (Dichtediagramm / KDE-Plot)
    # 'hue' trennt die Daten nach Kanälen, 'fill=True' füllt die Flächen transparent
    sns.kdeplot(
        data=df,
        x="populism_score",
        hue="channel_name",
        fill=True,
        common_norm=False,  # Verhindert, dass Kanäle mit weniger Videos winzig wirken
        palette="tab10",  # Schöne, kontrastreiche Farbpalette
        alpha=0.4,  # Transparenz der Flächen
        linewidth=2.5,  # Dicke der Linien
    )

    # 4. Achsen und Titel beschriften
    plt.title(
        "Vergleich der Populismus-Bewertungen nach YouTube-Kanal",
        fontsize=16,
        fontweight="bold",
        pad=20,
    )
    plt.xlabel("Populism Score (Skala 0 - 10)", fontsize=12, labelpad=10)
    plt.ylabel("Dichte (Häufigkeit)", fontsize=12, labelpad=10)

    # X-Achse auf deine Skala von 1 bis 10 einschränken mit Schritten
    plt.xlim(0, 10)
    plt.xticks(range(0, 11))

    # Layout optimieren und anzeigen
    plt.tight_layout()
    plt.show()


# ===================================================
# MAIN
# ===================================================

if __name__ == "__main__":
    aggregation(RESULTS_PATH, VIDEOS_PATH, OUTPUT_PATH_051)
    comparison_stats(OUTPUT_PATH_07, OUTPUT_PATH_051)

    # main_graphs(OUTPUT_PATH_07)
    # main_graphs(OUTPUT_PATH_051)


import pandas as pd
from youtube_code.config import EXPLORATION, SAMPLES

# ===================================================
# CONFIGURATION AND PATHS
# ===================================================

TEST_RUN = False

RESULTS_PATH = EXPLORATION / "ratings_merged.xlsx"
VIDEOS_PATH = SAMPLES / "cot_50k_channels" / "all_videos_50k_channels.json"
OUTPUT_PATH = EXPLORATION / "channel_results.xlsx"

channels_map = {
    "UCjSkyrjqPeMwubZU0CnScXA": "SchrangTV",
    "UCE7b8qctaEGmST38-sfdOsA": "NachDenkSeiten",
    "UCQGqiGhMjc_p4lZEhSTb12g": "NIUS",
    "UCs-G8CXCziErSY1459e7U8A": "Gegenpol",
    "UC5NOEUbkLheQcaaRldYW5GA": "tagesschau",
    "UCgvFsn6bRKqND1cW3HpzDrA": "Compact",
}

# ===================================================
# MAIN CODE
# ===================================================

df = pd.read_excel(RESULTS_PATH)
df_videos = pd.read_json(VIDEOS_PATH)

#df = pd.merge(df, df_videos[["video_id", "channel_id"]], on ="video_id", how = "left")
df = df.drop(columns = ["published_at", "creator_sentiment"], errors = "ignore")
print(df.columns)

df["channel_name"] = df["channel_id"].replace(channels_map)

df.to_excel("ratings_merged.xlsx", index = False)

df["ideology_score"] = df["ideology_score"].astype(float)
df["populism_score"] = df["populism_score"].astype(float)

new_df = df.groupby("channel_name").agg(
    ideology_channel_mean = ("ideology_score", "mean"),
    populism_channel_mean = ("populism_score", "mean"),
    ideology_channel_median = ("ideology_score", "median"),
    populism_channel_median = ("populism_score", "median"),
).reset_index()

r_df = df[df["video_type"] == "Standard"]
r_df = r_df.groupby("channel_name").agg(
    ideology_channel = ("ideology_score", "mean"),
    populism_channel = ("populism_score", "mean"),
).reset_index()

new_df = pd.merge(new_df, r_df, on = "channel_name", how ="inner")

new_df.to_excel(OUTPUT_PATH, index = False)


# ===================================================
# GRAPHS FOR TEST CLASSIFICATION
# ===================================================

if TEST_RUN:
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


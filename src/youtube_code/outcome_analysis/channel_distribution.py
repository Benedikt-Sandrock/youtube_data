import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from youtube_code.config import EXTERNAL, OUTPUT_GEMINI, IDEOLOGY_LABELS, IDEOLOGY_BINS, POPULISM_LABELS, POPULISM_BINS

# === CONFIG ===

MEDIA_PATH = EXTERNAL / "media_type.xlsx"
CLASSIFIED_PATH = OUTPUT_GEMINI / "channel_results_051.xlsx"

column_pairs = [("ideology_channel_mean", "media_type"),("populism_channel_mean", "media_type")]

label_mapping = {
    "ideology_channel_mean": "Political Ideology",
    "populism_channel_mean": "Populism",
    "media_type": "Media Type"
}

media_mapping = {
    1: "ÖRR",
    2: "Traditionelle Medien",
    3: "Alternative Medien",
    4: "Politiker/Parteien"
}

media_types = ["ÖRR", "Traditionelle Medien", "Alternative Medien", "Politiker/Parteien"]
# === LOAD AND MERGE DATA ===

df = pd.read_excel(CLASSIFIED_PATH)
print(len(df))
df = df.dropna(subset = ["ideology_channel_mean", "populism_channel_mean"])
channel_number = len(df)
print(channel_number)

df_media = pd.read_excel(MEDIA_PATH)
df_media = df_media.rename(columns = {"type": "media_type"})
df_media["media_type"] = df_media["media_type"].map(media_mapping)

df = pd.merge(df, df_media[["channel_title", "media_type"]], on = "channel_title", how = "left")
df.to_excel("channels_complete.xlsx", index = False)

# === GRAPHS ===

sns.set_theme(style="whitegrid", rc={
    "figure.facecolor": "#f8f9fa",  # Sehr helles Graublau für den gesamten Hintergrund
    "axes.facecolor": "#f1f3f5",    # Etwas dunkleres Grau für die Plot-Fläche
    "grid.color": "#e9ecef",        # Sehr dezente Gitterlinien
    "grid.linestyle": "--",         # Gestrichelte statt durchgezogene Linien
    "font.family": "sans-serif"
})
MY_PALETTE = ["#2b7bba", "#e65c00", "#2ca02c", "#9467bd"]

# SCATTERPLOT FOR IDEOLOGY AND POPULISM
def scatterplot_ideology_populism(dataframe, channels = "All"):
    plt.figure(figsize=(10, 8))
    sns.set_theme(style="whitegrid")

    sns.scatterplot(
        data=dataframe,
        x="ideology_channel_mean",
        y="populism_channel_mean",
        color="#9e1b1b",
        s=70,
        alpha=0.8,
        edgecolor="w",
        linewidth=1,
        zorder=3,
    )

    plt.title(f"Ideology vs. Populism: {channels}", fontsize=16, weight="bold", pad=20, color="#212529")
    plt.xlabel("Ideology (Channel Mean)", fontsize=13, labelpad=12, color="#212529")
    plt.ylabel("Populism (Channel Mean)", fontsize=13, labelpad=12, color="#212529")
    plt.tight_layout()
    plt.show()


scatterplot_ideology_populism(df)

for mtype in media_types:
    temp_df = df[df["media_type"] == mtype]
    scatterplot_ideology_populism(temp_df, mtype)


# IDEOLOGY/POPULISM VS. MEDIA TYPE
cols = df.columns
if "media_type" in cols:

    for var1, var2 in column_pairs:

        var1_label = label_mapping.get(var1, var1)
        var2_label = label_mapping.get(var2, var2)

        plt.figure(figsize=(11, 7))  # Etwas breiteres Format


        ax = sns.stripplot(
            data=df,
            x=var1,
            y=var2,
            palette=MY_PALETTE,
            size=7,
            alpha=0.7,
            jitter=0.25,
            linewidth=0.8,
            edgecolor="gray",
            zorder=3
        )

        plt.xticks(fontsize=11, color="#495057")
        plt.yticks(fontsize=12, weight="bold", color="#495057")  # Kategorien in fett

        plt.xlabel(var1_label, fontsize=13, weight="bold", labelpad=15, color="#212529")
        plt.ylabel("")

        plt.title(
            f"{var1_label} by {var2_label}",
            fontsize=16,
            weight="bold",
            pad=22,
            color="#212529",
            loc="left"
        )

        sns.despine(left=True, bottom=True)

        plt.tight_layout()
        plt.show()
        plt.close()


import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from youtube_code.config import EXTERNAL, OUTPUT_GEMINI, IDEOLOGY_LABELS, IDEOLOGY_BINS, POPULISM_LABELS, POPULISM_BINS

# === CONFIG ===

MEDIA_PATH = EXTERNAL / ""
CLASSIFIED_PATH = OUTPUT_GEMINI / "channel_results_051.xlsx"

COLUMN_PAIRS = [("ideology_channel_mean", "media_type"),("populism_channel_mean", "media_type")]

LABEL_MAPPING = {
    "ideology_group": "Ideology",
    "populism_group": "Populism",
    "media_type": "Media Type"
}

# === LOAD AND MERGE DATA ===

df = pd.read_excel(CLASSIFIED_PATH)
print(len(df))
df = df.dropna(subset = ["ideology_channel_mean", "populism_channel_mean"])
channel_number = len(df)
print(channel_number)
# df_media = pd.read_csv(MEDIA_PATH)
#
# df = pd.merge(df, df_media[["channel_title", ""]])


# === GRAPHS ===

# SCATTERPLOT FOR IDEOLOGY AND POPULISM
plt.figure(figsize=(10, 8))
sns.set_theme(style="whitegrid")

sns.scatterplot(
    data=df,
    x="ideology_channel_mean",
    y="populism_channel_mean",
    color="darkred",
    s=50,
    zorder=2,
)
plt.tight_layout()
plt.show()


# IDEOLOGY/POPULISM VS. MEDIA TYPE
cols = df.columns
if "media_type" in cols:

    for var1, var2 in COLUMN_PAIRS:

        var1_label = LABEL_MAPPING.get(var1, var1)
        var2_label = LABEL_MAPPING.get(var2, var2)

        np.random.seed(42)

        # add some random variation to each point so that they don't overlap
        df["y_jitter"] = df[var2].astype("category").cat.codes + np.random.uniform(
            -0.2, 0.2, len(df))

        plt.figure(figsize=(10, 8))
        sns.set_theme(style="whitegrid")

        ax = sns.scatterplot(
            data=df,
            x=var1,
            y="y_jitter",
            alpha=1,
        )

        y_categories = df[var2].astype("category").cat.categories
        plt.yticks(ticks=range(len(y_categories)), labels=y_categories, fontsize=12)

        plt.ylim(-0.5, len(y_categories) - 0.5)

        plt.xlabel(var1_label, fontsize=14, labelpad=15)
        plt.ylabel(var2_label, fontsize=14, labelpad=15)
        plt.title(
            f"Channels: {var1_label} by {var2_label}", fontsize=16, weight="bold", pad=20
        )

        plt.tight_layout()
        plt.show()
        plt.close()


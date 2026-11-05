from youtube_code.config import CLAUDE, STATA_OUTPUT

import pandas as pd
import os
from sklearn.metrics import (
    confusion_matrix, cohen_kappa_score, classification_report
)
if os.path.exists("temp.csv"):
    df = pd.read_csv("temp.csv")
else:
    print("Loading and merging data")
    df_claude = pd.read_csv(CLAUDE / "angebot" / "video_results.csv")
    df_stata = pd.read_stata(STATA_OUTPUT / "videos_roh.dta", columns = ["video_id", "post_war", "politisch",
                                                                     "rel_russia_ukraine_war_core",
                                                                     "rel_russia_ukraine_war_cw",
                                                                     "rel_politics_general_core",
                                                                     "rel_politics_general_cw"])
    df = pd.merge(df_claude, df_stata, on ="video_id", how = "inner")
    df_channels = pd.read_excel(STATA_OUTPUT / "channels_check.xlsx")
    df_channels = df_channels[["channel_id","media_category", "sample"]]
    df = pd.merge(df, df_channels, on = "channel_id", how = "left")
    print(len(df_claude), len(df_stata), len(df))
    df.to_csv("temp.csv", index=False)

# print(df["thema_krieg_ukraine"].describe())

df["ukraine_claude_core"] = df["thema_krieg_ukraine"] >= 0.5
df["ukraine_claude_wide"] = df["thema_krieg_ukraine"] > 0
df["ukraine_kw_core"] = df["rel_russia_ukraine_war_core"] == "ja"
df["ukraine_kw_cw"] = df["rel_russia_ukraine_war_cw"] == "ja"

gold = "ukraine_claude_core"

df_core = df.copy()
df_alt = df[df["media_category"] == 5]
df_main = df[df["media_category"].isin([1,2])]

df_dict = {
    "All channels": df_core,
    "Alternative Media": df_alt,
    "Mainstream Media": df_main
}

def evaluate_classification(df_dict):
    for name, df in df_dict.items():
        print(f"\n{20*"="}"
              f"\nAuswertung: {name}"
              f"\n{20*"="}")

        for i, col in enumerate(["ukraine_kw_core", "ukraine_kw_cw"], 1):
            print(f"\n--- Auswertung für Klassifikation {col} gegen {gold} ---")

            y_true = df[gold]
            y_pred = df[col]

            print("Konfusionsmatrix:")
            print("\nGold/Classification")
            print("false/false  false/true"
                  "\ntrue/false true/true")
            print(confusion_matrix(y_true, y_pred))

            print("\nKlassifikationsreport:")
            print(classification_report(y_true, y_pred))

            kappa = cohen_kappa_score(y_true, y_pred)
            print(f"Cohen's Kappa: {kappa:.3f}\n")


evaluate_classification(df_dict)
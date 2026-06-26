from youtube_code.config import TRANSCRIPTS, RAW, OUTPUT_GEMINI
from src.youtube_code.utils.io import load_json, merge_channel_name
import json
import pandas as pd

df = pd.read_json("keyword_videos_50k_channels.json")
print(len(df))
#merge_channel_name("all_videos_50k_channels.json", RAW/"video_metadata_total.jsonl", "all_videos_50k_channels.json")
# df = pd.read_csv("keyword_videos_50k_channels.csv")
# df_2 = pd.read_excel(OUTPUT_GEMINI / "channel_results_051.xlsx")
#
# IDEOLOGY_BINS = [-0.01, 4.5, 5.49, 7.5,  10.01]
# IDEOLOGY_LABELS = ["Links", "Mitte", "Rechts", "Sehr rechts"]
#
# POPULISM_BINS = [-0.01, 3, 7, 10.01]
# POPULISM_LABELS = ["Niedrig", "Mittel", "Hoch"]
#
# df_2["ideology_group"] = pd.cut(
#     df_2["ideology_channel"], bins= IDEOLOGY_BINS, labels= IDEOLOGY_LABELS, include_lowest= True
# )
#
# df = pd.merge(df, df_2[["channel_title", "ideology_group"]], on = "channel_title", how = "left")
# df.to_csv("keyword_videos_50k_channels.csv", index = False)
import pandas as pd
import random

df = pd.read_json("metadata_all_videos_100k_channels_keywords.json")

df["video_duration"] = pd.to_timedelta(df["duration"])
print(df["video_duration"].describe(percentiles = [0.25, 0.5, 0.75, 0.9, 0.95, 0.99]))

df_sorted = df.sort_values(by="video_duration", ascending = False)
print(df_sorted.head(10))
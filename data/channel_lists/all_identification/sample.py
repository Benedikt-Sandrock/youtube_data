from idlelib.iomenu import encoding

import pandas as pd
from youtube_code.config import RAW, CHANNEL_LISTS
import json

with open("all_channel_ids_discovered.json", "r", encoding= "utf-8") as f:
    data = json.load(f)
print(data)
df2 = pd.read_json(RAW / "channel_metadata_total.json")
df3 = pd.read_json(RAW / "classified_channels_total.json")
print(len(data), len(df2), len(df3))

channels_10k = df2[df2["subscribers"] >= 10000]
channels_10k = channels_10k["channel_id"].to_list()

channels_50k = df2[df2["subscribers"] >= 50000]
channels_50k = channels_50k["channel_id"].to_list()
print(len(channels_10k), len(channels_50k))

data = [v for v in data if v in channels_10k]
print(data)
print(len(data))

with open("german_channels_10k.json", "w", encoding = "utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent = 2)
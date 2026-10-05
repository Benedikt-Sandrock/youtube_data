import pandas as pd
from youtube_code.config import RAW, CHANNEL_LISTS
import json

with open("all_channel_ids_discovered.json", "r", encoding= "utf-8") as f:
    data = json.load(f)
# print(data)
df2 = pd.read_json(RAW / "channel_metadata_total.json")
df3 = pd.read_json(RAW / "classified_channels_total.json")
print(len(data), len(df2), len(df3))

german_channels = df3[df3["is_german"] == True]
german_channels = german_channels["channel_id"].to_list()
print(f"German channels: {len(german_channels)}")

channels_all = df2["channel_id"].to_list()

channels_10k = df2[df2["subscribers"] >= 10000]
channels_10k = channels_10k["channel_id"].to_list()

channels_50k = df2[df2["subscribers"] >= 50000]
channels_50k = channels_50k["channel_id"].to_list()
print(len(channels_all), len(channels_10k), len(channels_50k))

new_data = [c for c in data if c in channels_50k]
print(len(new_data), "/", len(data))

new_data = [c for c in new_data if c in german_channels]
print(len(new_data), "/", len(data))

with open("german_channels_50k.json", "w", encoding = "utf-8") as f:
    json.dump(new_data, f, ensure_ascii = False, indent = 4)



# data = [v for v in data if v in channels_10k]
# print(data)
# print(len(data))

# with open("identification_vids.json") as f:
#     data = json.load(f)
#
# print(len(data))
#
# with open("german_channels_10k.json", "w", encoding = "utf-8") as f:
#     json.dump(data, f, ensure_ascii=False, indent = 2)
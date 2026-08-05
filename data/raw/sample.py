import json
import pandas as pd
from youtube_code.config import CHANNEL_LISTS, RAW
from youtube_code.utils import get_channel_metadata

# with open("sample_russia_ukraine.json", encoding = "utf-8") as f:
#     data = json.load(f)
#
# print(len(data))
metadata = pd.read_json(RAW / "channel_metadata_total.json")
df = pd.read_json("classified_channels_total.json")
print("Share german channels of alL:")
print(df["is_german"].mean())
ids_german = df["channel_id"].to_list()
print("All Channels:")
print(len(df))

df2 = pd.read_json(CHANNEL_LISTS / "all_identification" / "all_channel_ids_discovered.json" )
print("discovered relevant channels:")
print(len(df2))

cid = df2[0].to_list()
ids_both = [c for c in cid if c in ids_german]
print("relevant channels that are in classification")
print(len(ids_both))
# print(cid)

df = df[df["channel_id"].isin(cid)]
print(len(df))

df = df[df["is_german"] == True]
print(df["is_german"].mean())
print(f"German channels in sample: {len(df)}")

metadata_list = metadata["channel_id"].to_list()

df = df[df["channel_id"].isin(metadata_list)]
print(f"German channels in sample w/ metadata: {len(df)}")

relevant_channels = df["channel_id"].to_list()

channels_10k = metadata[metadata["channel_id"].isin(relevant_channels)]
channels_10k = channels_10k[channels_10k["subscribers"] > 10000]
print(f"German channels above 10k: {len(channels_10k)}")


# import json
# import pandas as pd
# from youtube_code.config import CHANNEL_LISTS, RAW
# from youtube_code.utils import get_channel_metadata
#
# # with open("sample_russia_ukraine.json", encoding = "utf-8") as f:
# #     data = json.load(f)
# #
# # print(len(data))
# metadata = pd.read_json(RAW / "channel_metadata_total.json")
# df = pd.read_json("classified_channels_total.json")
# print("Share german channels of alL:")
# print(df["is_german"].mean())
# ids_german = df["channel_id"].to_list()
# print("All Channels:")
# print(len(df))
#
# df2 = pd.read_json(CHANNEL_LISTS / "all_identification" / "all_channel_ids_discovered.json" )
# print("discovered relevant channels:")
# print(len(df2))
#
# cid = df2[0].to_list()
# ids_both = [c for c in cid if c in ids_german]
# print("relevant channels that are in classification")
# print(len(ids_both))
# # print(cid)
#
# df = df[df["channel_id"].isin(cid)]
# print(len(df))
#
# df = df[df["is_german"] == True]
# print(df["is_german"].mean())
# print(f"German channels in sample: {len(df)}")
#
# metadata_list = metadata["channel_id"].to_list()
#
# df = df[df["channel_id"].isin(metadata_list)]
# print(f"German channels in sample w/ metadata: {len(df)}")
#
# relevant_channels = df["channel_id"].to_list()
#
# channels_10k = metadata[metadata["channel_id"].isin(relevant_channels)]
# channels_10k = channels_10k[channels_10k["subscribers"] > 10000]
# print(f"German channels above 10k: {len(channels_10k)}")
#

# import json
#
# with open("sample_50k_channels_russia_ukraine.json", "r", encoding = "utf-8") as infile, open("sample_50k_channels_russia_urkaine.jsonl", "w", encoding = "utf-8") as outfile:
#     data = json.load(infile)
#
#     for item in data:
#         outfile.write(json.dumps(item) + "\n")
import json

from youtube_code.config import CHANNEL_LISTS

# PATH = "sample_50k_channels_russia_urkaine.jsonl"
# OUT_PATH = "sample_50k_channels_russia_ukraine_controlled.jsonl"
# CHANNEL_LIST = CHANNEL_LISTS / "all_identification" / "german_channels_50k.json"
#
# n_gelesen = n_behalten = n_gestrichen = n_ohne_id = 0
#
# with open(CHANNEL_LIST, "r", encoding = "utf-8") as f:
#     channel_list = json.load(f)
#
# print(len(channel_list))
# channel_list = set(channel_list)
#
# with open(PATH, encoding = "utf-8") as fin, open(OUT_PATH, "w", encoding = "utf-8") as fout:
#     for line in fin:
#         line = line.strip()
#         if not line:
#             continue
#
#         r = json.loads(line)
#         n_gelesen += 1
#         channel_id = r.get("channel_id")
#         if channel_id in channel_list:
#             fout.write(json.dumps(r, ensure_ascii=False) + "\n")
#             n_behalten += 1
#
#         else:
#             n_gestrichen += 1
# print(f"Gelesen: {n_gelesen}")
# print(f"Behalten: {n_behalten}")
# print(f"Gestrichen: {n_gestrichen}")

INFILE = "video_metadata_detailed_total.json"
OUTFILE = "video_metadata_detailed_total.jsonl"

with open(INFILE, encoding = "utf-8") as inf, open(OUTFILE, "w", encoding ="utf-8") as outf:
    data= json.load(inf)

    for item in data:
        outf.write(json.dumps(item) + "\n")

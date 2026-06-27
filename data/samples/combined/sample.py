import json
from youtube_code.utils import load_json, merge_channel_name, save_json
from youtube_code.config import RAW, OUTPUT_GEMINI, TRANSCRIPTS
import pandas as pd


df = pd.read_json("../party_identification/keyword_videos_50k_channels.json")
df2 = pd.read_json("../conflict_over_time/keyword_videos_50k_channels.json")

ids1 = set(df["video_id"].to_list())
ids2 = set(df2["video_id"].to_list())

intersection = ids1 & ids2
total = ids1 | ids2
only1 = ids1 - ids2
only2 = ids2 - ids1

print(len(intersection), len(total), len(only1), len(only2))
kw = load_json("keyword_videos_50k_channels.json")
kw = set(v["channel_id"] for v in kw)

data = load_json("sampled_50k_channels.json")
print(len(data))

data = [v for v in data if v["channel_id"] in kw]
print(len(data))

save_json("relevant_sampled_50k_channels.json", data)




# kw = pd.read_json("keyword_videos_50k_channels.json")
# print(len(kw))
# kw = kw.groupby("channel_title", group_keys=False).apply(
#     lambda x: x.sample(n=100, random_state=42) if len(x) > 100 else x
# ).reset_index()
# print(len(kw))
#
# video_ids = kw["video_id"].to_list()
#
# kw_max100 = load_json("keyword_videos_50k_channels.json")
#
# kw_max100 = [v for v in kw_max100 if v["video_id"] in video_ids]
# print(len(kw_max100))
# with open("kw_vids.json", "w", encoding = "utf-8") as f:
#     json.dump(kw_max100, f, ensure_ascii = False, indent = 2)


# df = pd.read_csv(TRANSCRIPTS / "all_transcripts.csv")
# #
# # ids = [v["video_id"] for v in kw]
# #
# df = df[df["video_id"].isin(video_ids)]
# #
# print(len(df))
# df = df[df["status"] =="OK"]
# print(len(df))
# df.to_csv("transcripts_combined_max100.csv", index = False)
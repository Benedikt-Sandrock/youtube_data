import json
import pandas as pd

from youtube_code.config import TRANSCRIPTS

df = pd.read_csv("pilot_videos.csv")
df = df[df["primary"] == True]
df.to_csv("pilot_videos_primary.csv")
# videos = df["video_id"].to_list()
# print(len(videos))
#
# df2 = pd.read_csv(TRANSCRIPTS / "all_transcripts_segments.csv", usecols = ["video_id"])
#
# transcripts = df2["video_id"].to_list()
# transcripts = set(transcripts)
#
# downloaded = [v for v in videos if v in transcripts]
#
# print(len(downloaded))
#
# #
# with open("primary_pilot_ids.json", "w", encoding = "utf-8") as f:
#     json.dump(videos, f, ensure_ascii= False, indent = 2)


# z = pd.read_csv("pilot_zellen.csv")
# k = pd.read_csv("pilot_kanaele.csv")
#
# el = z[z.channel_id.isin(k.channel_id)]                  # geeignete Kanaele
# print(el[el.ok].groupby("channel_id").size().value_counts().sort_index())
#
# gez = z[z.channel_id.isin(k.loc[k.gezogen, "channel_id"])]
# print(gez[gez.ok].groupby("fenster").size())             # Besetzung je Fenster
#
# g = k[k.gezogen][["channel_id", "label"]]
# x = gez[gez.ok].merge(g, on="channel_id")
#
# print(x.groupby("label")["fenster"].value_counts().unstack(fill_value=0))
# print(x.groupby(["label", "channel_id"]).size().groupby("label").mean().round(2))
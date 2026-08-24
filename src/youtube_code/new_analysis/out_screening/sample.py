import json
import pandas as pd

df = pd.read_csv("pilot_videos.csv")
df = df[df["primary"] == True]
videos = df["video_id"].to_list()
print(len(videos))

with open("primary_pilot_ids.json", "w", encoding = "utf-8") as f:
    json.dump(videos, f, ensure_ascii= False, indent = 2)


z = pd.read_csv("pilot_zellen.csv")
k = pd.read_csv("pilot_kanaele.csv")

el = z[z.channel_id.isin(k.channel_id)]                  # geeignete Kanaele
print(el[el.ok].groupby("channel_id").size().value_counts().sort_index())

gez = z[z.channel_id.isin(k.loc[k.gezogen, "channel_id"])]
print(gez[gez.ok].groupby("fenster").size())             # Besetzung je Fenster

g = k[k.gezogen][["channel_id", "label"]]
x = gez[gez.ok].merge(g, on="channel_id")

print(x.groupby("label")["fenster"].value_counts().unstack(fill_value=0))
print(x.groupby(["label", "channel_id"]).size().groupby("label").mean().round(2))
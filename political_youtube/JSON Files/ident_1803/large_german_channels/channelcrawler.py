import pandas as pd
import json

df = pd.read_excel("top200_channelcrawler.xlsx", engine = "openpyxl")

df = df["name"]

print(df.head())
df["name_clean"] = df.str.strip().str.lower()
print(df.head())

with open("german_channels_10000k.json", "r", encoding = "utf-8") as f:
    data = json.load(f)

json_df = pd.DataFrame(data)

json_df["name_clean"] = json_df["name"].str.strip().str.lower()

df_merged = pd.merge(df, json_df[["name", "channel_id", "name_clean"]], on="name_clean", how = "left")
treffer  = df_merged["channel_id"].count()
print(treffer)
df_merged = df_merged[["name", "channel_id"]]
print(df_merged.head())
df_merged.to_excel("top200_channelcrawler.xlsx", index = False)
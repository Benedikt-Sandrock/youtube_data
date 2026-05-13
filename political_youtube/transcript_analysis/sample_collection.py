import pandas as pd

df = pd.read_csv("../Transcript files/transcripts_conflict_over_time_sampled.csv")
print(len(df))

df2 = pd.read_csv("../conflict_over_time/classification/sampled_per_channel.csv")
print(len(df2))

df = pd.merge(df, df2, on ="video_id", how = "left")
print(len(df))


channel_ids = [
    "UC1w6pNGiiLdZgyNpXUnA4Zw",
    "UC3AdN1bEmEonuSwXNS8LixQ",
    "UCE7b8qctaEGmST38-sfdOsA"]

df = df[df["channel_id"].isin(channel_ids)]
df = df[df["channel_id"] == "UCE7b8qctaEGmST38-sfdOsA"]
print(len(df))
df = df[["video_id", "transcript"]]

df.to_csv("transcripts_channel.csv", index = False)

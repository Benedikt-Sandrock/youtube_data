import pandas as pd
import matplotlib.pyplot as plt

keywords = ["nahe osten", "naher osten", "nahen osten", "nahost",
            "israel", "palästina", "gaza", "hamas", "IDF", "Jerusalem", "netanjahu", "netanyahu"]

pattern = '|'.join(keywords)

treatment_day = "2023-10-07T00:00:00Z"
news_channels = pd.read_excel("german_channels.xlsx", usecols=["channel_id", "news_channel"])
df = pd.read_json("../../JSON Files/ident_1803/large_german_channels/video_files/all_videos_100k_channels.json")

print(f"Total number of video_files: {len(df)}")

df = pd.merge(df, news_channels, on = "channel_id", how = "left")

df["published_at"] = pd.to_datetime(df["published_at"])
channels_old = df["channel_id"].unique()
print(len(channels_old))
df = df[(df["published_at"] > "2022-10-07T00:00:00Z") & (df["published_at"] < "2023-10-20T00:00:00Z")]

channels_new = df["channel_id"].unique()
print(f"Number of channels: {len(channels_new)}")

channels_new = set(channels_new)
channels_old = set(channels_old)
channels_dropped = channels_old - channels_new
print(channels_dropped)

df["post_oct_7"] = df["published_at"] >= treatment_day
df["keyword_video"] = df["title"].str.contains(pattern, case = False, na = False)


df_after = df[(df["published_at"] >= treatment_day) & (df["keyword_video"] == 1)]
df_before = df[(df["published_at"] < treatment_day) & (df["keyword_video"] == 1)]
print(f"Videos before treatment: {len(df_before)}")
print(f"Videos after treatment: {len(df_after)}")

stats = df.groupby('post_oct_7').agg(
    keyword_share = ("keyword_video", "mean"),
    )

stats_2 = df.groupby(["post_oct_7", "channel_id"])["keyword_video"].any().reset_index()
stats_2 = stats_2.groupby("post_oct_7").agg(
    any_keyword_video = ("keyword_video", "mean")
    )

print("Share of keyword video_files before and after October 7:")
print(stats)
print(stats_2)

df_without_news = df[df["news_channel"] == 0.0]

channels = df_without_news.groupby("channel_id")
print(f"Number of channels without news channels: {len(channels)}")

df_after = df_without_news[(df_without_news["published_at"] >= treatment_day) & (df_without_news["keyword_video"] == 1)]
df_before = df_without_news[(df_without_news["published_at"] < treatment_day) & (df_without_news["keyword_video"] == 1)]
print(f"Videos before treatment: {len(df_before)}")
print(f"Videos after treatment: {len(df_after)}")

channels_posting_after = df_after.groupby("channel_id")
print(f"By {len(channels_posting_after)} different channels")

df_after.to_csv("videos_after_treatment.csv", index = False)

stats_without_news = df_without_news.groupby("post_oct_7").agg(
    keyword_share=("keyword_video", "mean"),
    )

stats_without_news_2 = df_without_news.groupby(["post_oct_7", "channel_id"])["keyword_video"].any().reset_index()
stats_without_news_2 = stats_without_news_2.groupby("post_oct_7").agg(
    any_keyword_video = ("keyword_video", "mean")
    )
print("Share of keyword video_files excluding news channels:")
print(stats_without_news)
print(stats_without_news_2)

#df.to_csv("filtered.csv", index = False)


df_length = pd.read_json("../../JSON Files/ident_1803/large_german_channels/video_files/"
                         "metadata_all_videos_100k_channels_keywords.json")

df_length["duration"] = pd.to_timedelta(df_length["duration"])
df_length["duration"] = (df_length["duration"].dt.total_seconds()) / 60
print(df_length["duration"].describe())

bins = [0, 1, 5, 20, 60, df_length["duration"].max()]
labels = ["<1", "1-5", "5-20", "20-60", ">60"]
df_length["binned"] = pd.cut(df_length["duration"], bins = bins, labels = labels)
bin_counts = df_length["binned"].value_counts().sort_index()

plt.figure(figsize = (10, 6))
bin_counts.plot(kind = "bar", color = "skyblue", edgecolor ="black", width = 0.7)
plt.title("Videos by length", fontsize=14)
plt.xlabel("Duration in minutes", fontsize=12)
plt.ylabel("Number of videos", fontsize=12)

plt.xticks(rotation = 45)

plt.grid(axis = "y", linestyle ="--", alpha = 0.7)
plt.tight_layout()
plt.savefig("videos_by_length.png", format = "png", dpi = 300)
plt.show()
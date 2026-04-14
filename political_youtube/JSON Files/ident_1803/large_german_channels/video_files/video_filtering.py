import pandas as pd

keywords = ["nahe osten", "naher osten", "nahen osten", "nahost",
            "israel", "palästina", "gaza", "hamas", "IDF", "Jerusalem", "netanjahu", "netanyahu"]

pattern = '|'.join(keywords)

treatment_day = "2023-10-07T00:00:00Z"
news_channels = pd.read_excel("german_channels.xlsx", usecols=["channel_id", "news_channel"])
df = pd.read_json("all_videos_100k_channels.json")

print(f"Total number of videos: {len(df)}")

df = pd.merge(df, news_channels, on = "channel_id", how = "left")

df["published_at"] = pd.to_datetime(df["published_at"])
df = df[(df["published_at"] > "2023-07-07T00:00:00Z") & (df["published_at"] < "2023-11-07T00:00:00Z")]
df["treated"] = df["published_at"] >= treatment_day
df["keyword_video"] = df["title"].str.contains(pattern, case = False, na = False)
#df["any_keyword_video"] = df.groupby("channel_id")["keyword_video"].transform("any")

channels = df.groupby("channel_id")
print(f"Number of channels: {len(channels)}")

stats = df.groupby('treated').agg(
    keyword_share = ("keyword_video", "mean"),
)

stats_2 = df.groupby(["treated", "channel_id"])["keyword_video"].any().reset_index()
stats_2 = stats_2.groupby("treated").agg(
    any_keyword_video = ("keyword_video", "mean")
)
print("Share of keyword videos before and after October 7:")
print(stats)
print(stats_2)

df_without_news = df[df["news_channel"] == 0.0]
channels = df_without_news.groupby("channel_id")

print(f"Number of channels without news channels: {len(channels)}")

stats_without_news = df_without_news.groupby("treated").agg(
    keyword_share=("keyword_video", "mean"),
)

stats_without_news_2 = df_without_news.groupby(["treated", "channel_id"])["keyword_video"].any().reset_index()
stats_without_news_2 = stats_without_news_2.groupby("treated").agg(
    any_keyword_video = ("keyword_video", "mean")
)
print("Share of keyword videos excluding news channels:")
print(stats_without_news)
print(stats_without_news_2)



df.to_csv("filtered.csv")
#print(len(df))
#print(df[["title", "keyword_video"]].head())


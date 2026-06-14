import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from src.config.paths import OUTPUTS


df_videos = pd.read_json(
    "../../JSON Files/ident_1803/large_german_channels/video_files/metadata_all_videos_100k_channels_keywords.json")

df_comments = pd.read_csv("comment_data.csv")

df_videos["published_at"] = pd.to_datetime(df_videos["published_at"], utc = True)
df_comments["date"] = pd.to_datetime(df_comments["date"], utc = True)

print(df_videos.head())
print(df_comments.head())

df_videos_small = df_videos[["video_id", "published_at", "title"]]
df_comments = df_comments[["video_id", "date"]]

df_merged = pd.merge(df_comments, df_videos_small, on= "video_id", how = "inner")

df_merged["diff_time"] = df_merged["date"] - df_merged["published_at"]
df_merged["days_since_upload"] = df_merged["diff_time"].dt.total_seconds() / (24*3600)
#df_merged =  df_merged.sort_values(by = "days_since_upload")

# with pd.option_context("display.max_columns", None):
#     print(df_merged.head())

print("Anzahl Kommentare gesamt:")
print(len(df_merged))

df_negative = df_merged[df_merged["days_since_upload"] < 0]
print("Anzahl Kommentare vor offiziellem Upload-Datum:")
print(len(df_negative))

bins = [0, 1, 7, 30, 90, 365, 5000]
labels = ["Tag 1", "Woche 1", "Monat 1", "Monat 2-3", "Jahr 1", "älter"]

df_merged["period"] = pd.cut(df_merged["days_since_upload"], bins = bins, labels = labels, include_lowest = True)

# with pd.option_context("display.max_columns", None):
#     print(df_merged.head())

distribution = df_merged['period'].value_counts(normalize=True).sort_index() * 100
print(distribution)


ax = distribution.plot(kind='bar', color='teal', figsize=(10, 6))

for p in ax.patches:
    ax.annotate(f'{p.get_height():.1f}%', # Text: Wert auf 1 Nachkommastelle gerundet
                (p.get_x() + p.get_width() / 2., p.get_height()), # Position: Mitte des Balkens, oben
                ha='center', va='center', # Ausrichtung
                xytext=(0, 9), # Text-Versatz (9 Punkte nach oben)
                textcoords='offset points',
                fontsize=10,
                fontweight='bold')

plt.title('When do people comment?')
plt.ylabel('Share of comments in %')
plt.xlabel('Period after release')
plt.xticks(rotation=45)
plt.ylim(0, distribution.max() * 1.15)

plt.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(OUTPUTS / "comment_distribution.png", format="png", dpi=300)
plt.show()

df_channel_match = df_videos[["video_id", "channel_title", "comment_count", "like_count", "view_count"]]

df_channel_match['is_empty'] = df_channel_match['comment_count'].isna() | (df_channel_match['comment_count'] == 0)
channel_stats = df_channel_match.groupby('channel_title').agg(
    proportion_empty = ("is_empty", "mean"),
    average_views = ("view_count", "mean"),
    average_likes = ("like_count", "mean"),
    average_comments = ("comment_count", "mean")
).reset_index()



channel_stats = channel_stats.sort_values(by="proportion_empty", ascending = False)
channel_stats.to_csv("channel_stats.csv")



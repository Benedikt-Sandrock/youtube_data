import json
from googleapiclient.discovery import build
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib_venn import venn2, venn2_circles
import numpy as np
import matplotlib.dates as mdates

from youtube_code.config import API_KEY, RAW

all_metadata_path = RAW / "metadata_all_videos.jsonl"
channel_metadata_path = RAW / "channel_metadata.json"

published_after_analysis = "2022-10-07T00:00:00Z"
published_before_analysis = "2026-01-31T00:00:00Z"


YOUTBUE = build("youtube", "v3", developerKey = API_KEY)


pattern = '|'.join(keywords)
treatment_day = "2023-10-07T00:00:00Z"

### LOADING AND PREPARING DATA ###

df = pd.read_json(all_metadata_path, lines= True)

right_wing_channels = ["Tichys Einblick", "JUNGE FREIHEIT", "Oli", "COMPACT", "COMPACT-TV", "Carsten Jahn - TEAM HEIMAT",
                       "Clownswelt", "Oli investiert", "Marc Friedrich", "Alice Weidel", "NachDenkSeiten", "NIUS",
                       "Roger Beckamp", "Kettner-Edelmetalle (Gold & Silber)", "Schuler! Fragen, was ist",
                       "Steuern mit Kopf", "Ketzer der Neuzeit", "Gegenpol", "Hallo Meinung", "Vermietertagebuch - Alexander Raue",
                       "POLITIK SPEZIAL - Stimme der Vernunft ", "Digitaler Chronist"]

df["right_wing"] = df["channel_title"].isin(right_wing_channels)

major_news_channels = [
    "WELT Nachrichtensender", "tagesschau", "ZDFheute Nachrichten", "AFP Deutsch", "faz", "phoenix",
    "BILD", "DIE ZEIT", "WELT Netzreporter", "ntv Nachrichten",
    ":newstime", "DER SPIEGEL", "Handelsblatt", "euronews (deutsch)", "FOCUS online"]

df["major_news_channel"] = df["channel_title"].isin(major_news_channels)
print(f"Percentage of videos form major news channels: {df["major_news_channel"].mean():.2f}")

with open("../../JSON Files/ident_1803/large_german_channels/german_channels_100000k.json", "r", encoding = "utf-8") as f:
    large_channels = json.load(f)

large_channels = {v["channel_id"] for v in large_channels}

df["large_channel"] = df["channel_id"].isin(large_channels)
share_large_channel = df["large_channel"].mean()
print(f"Share of videos from 100k channels: {share_large_channel:.2f}")

#filtering out shorts and videos before analysis period
print(f"Len before filtering out shorts: {len(df)}")
df["duration"] = pd.to_timedelta(df["duration"])
df["duration"] = (df["duration"].dt.total_seconds()) / 60
df = df[df["duration"] > 1]
print(f"Len after filtering out shorts: {len(df)}")
print(f"Median video duration: {df["duration"].median():.2f}")

df["published_at"] = pd.to_datetime(df["published_at"])
# df = df[df["published_at"] > "2022-10-07T00:00:00Z"]
# print(f"Len after filtering out videos before Oct 7 2022: {len(df)}")

#creating engagement metrics
df["comment_ratio"] = df["comment_count"] / df["view_count"] *100
df["like_ratio"] = df["like_count"] / df["view_count"] *100
df["engagement_ratio"] = (df["like_count"] + df["comment_count"]) /df["view_count"] *100

df_comments = pd.read_csv("../comment_analysis/comment_data.csv")

df_comments = df_comments.groupby("video_id").agg(
    all_comments = ("text", "count")
).reset_index()

df = pd.merge(df, df_comments, on = "video_id", how = "left")
df["all_comments_ratio"] = df["all_comments"] / df["view_count"] * 100

df["keyword_video"] = df["title"].str.contains(pattern, case = False, na =False)

df["post_oct7"] = df["published_at"] >= treatment_day

metrics_relative = ["view_count", "like_ratio", "comment_ratio"]
metrics_absolute = ["view_count", "like_count", "comment_count"]
metrics = ["view_count", "like_count", "like_ratio", "comment_count", "comment_ratio", "all_comments", "all_comments_ratio"]

#group by pre- and post-treatment
df_average = df.groupby(["channel_title", "post_oct7", "keyword_video"])[metrics].mean().reset_index()

df["starting_date"] = df["published_at"] - pd.Timedelta(days = 6)
df["starting_date"] = df["starting_date"].dt.to_period("M").dt.to_timestamp()
df["starting_date"] = df["starting_date"].apply(lambda x: x.replace(day = 7))

#group by month (month always starting on 7th)
df_monthly = df.groupby(["channel_title", "starting_date", "keyword_video"])[metrics].mean().reset_index()




### PREPARING CHANNEL DATASET ###

df_channels = pd.read_json(channel_metadata_path)

with open("../../JSON Files/ident_1803/large_german_channels/german_channels_50000k.json", "r", encoding = "utf-8") as f:
    fifty_channels = json.load(f)

fifty_channels = {v["channel_id"] for v in fifty_channels}
df_channels["in_50"] = df_channels["channel_id"].isin(fifty_channels)
df_channels = df_channels[df_channels["in_50"] == True]
df_channels["total_videos"] = df_channels["videos"].combine_first(df_channels["video_files"])

df_channels = df_channels.drop(columns = ["videos", "video_files"])
df_channels["average_views"] = df_channels["total_videos"] / df_channels["views"]

### DESCRIPTIVES ###
# !!!!!
# if the next line is activated, only 100k channels are analyzed. Otherwise, channels with at least 50k subscribers are included
#df = df[df["large_channel"] == True]
#df = df[df["view_count"] >= 5000]
# !!!!!

# df_percent = df.groupby(["channel_id", "post_oct7"]).agg(
#     keyword_share = ("keyword_video", "mean")
# )
# print(df_percent.describe())
print(df.groupby("post_oct7")["keyword_video"].mean())
print(df.groupby("major_news_channel")["duration"].median())


print("\n\n### DESCRIPTIVES ###\n")
# os.makedirs("../../../outputs/sample_analysis/sample_description/graphs/metrics/median", exist_ok=True)
# os.makedirs("../../../outputs/sample_analysis/sample_description/graphs/metrics/mean", exist_ok=True)
# os.makedirs("../../../outputs/sample_analysis/sample_description/graphs/channel_stats", exist_ok=True)
# os.makedirs("../../../outputs/sample_analysis/sample_description/graphs/trends", exist_ok=True)


# Number of channels
number_of_channels = len(df["channel_id"].unique())
number_of_large_channels = len(df[df["large_channel"] == True]["channel_id"].unique())

print(f"Total number of channels: {number_of_channels}")
print(f"Number of channels with at least 100k subscribers: {number_of_large_channels}")

print(f"Total number of videos: {len(df)}")
keyword_count = df[df["keyword_video"] == True]
print(f"Number of keyword videos: {len(keyword_count)}")

# general channel stats
#plots for subscribers, average views, and number of videos
fig, axes = plt.subplots(1, 3, figsize = (18, 6))

subscriber_bins = [0, 100000, 200000, 500000, 1000000, df_channels["subscribers"].max()]
subscriber_bins_labels = ["50-100k", "100-200k", "200-500k", "500k- 1M", ">1M"]

print(f"Subscriber max:")
top_channels = df_channels.sort_values(by="subscribers", ascending=False).head(5)
print(top_channels)

df_channels["binned_subscribers"] = pd.cut(df_channels["subscribers"], bins = subscriber_bins, labels = subscriber_bins_labels)

bin_counts_subscribers = df_channels["binned_subscribers"].value_counts().sort_index()
print(bin_counts_subscribers)

bin_counts_subscribers.plot(kind = "bar", color ="skyblue", ax = axes[0], edgecolor ="black", width = 0.7)
axes[0].set_title("Distribution of subscribers", fontsize = 15)
axes[0].set_ylabel("Number of channels", fontsize = 14)
axes[0].set_xlabel("Number of subscribers", fontsize = 14)

channel_stats = df.groupby("channel_id")["view_count"].agg(["count", "mean"]).reset_index()
channel_stats.columns = ["channel_id", "video_count", "avg_views"]
print(channel_stats["video_count"].describe(percentiles = [0.25, 0.5, 0.75, 0.9, 0.95]))
print(channel_stats["avg_views"].describe(percentiles = [0.25, 0.5, 0.75, 0.9, 0.95]))

video_count_bins = [0, 100, 200, 500, 1000, 5000, channel_stats["video_count"].max()]
video_count_labels = ["0-100","100-200", "200-500", "500-1000", "1000-5000", ">5000"]

print(f"Video count max:")
top_channels = channel_stats.sort_values(by="video_count", ascending=False).head(5)
print(top_channels)

channel_stats["binned_count"] = pd.cut(channel_stats["video_count"], bins = video_count_bins, labels = video_count_labels)
bin_counts_count = channel_stats["binned_count"].value_counts().sort_index()
print(bin_counts_count)

bin_counts_count.plot(kind = "bar", color = "skyblue", ax = axes[1], edgecolor = "black", width = 0.7)
axes[1].set_title("Distribution of videos", fontsize = 15)
axes[1].set_xlabel("Number of videos", fontsize = 14)

avg_views_bins = [0, 10000, 20000, 50000, 100000, 200000, channel_stats["avg_views"].max()]
avg_views_labels = ["<10k", "10-20k", "20-50k", "50-100k", "100-200k", ">200k"]

print(f"Avg views max:")
top_channels = channel_stats.sort_values(by="avg_views", ascending=False).head(5)
print(top_channels)

channel_stats["binned_views"] = pd.cut(channel_stats["avg_views"], bins = avg_views_bins, labels = avg_views_labels)
bin_counts_views = channel_stats["binned_views"].value_counts().sort_index()
print(bin_counts_views)

bin_counts_views.plot(kind = "bar", color = "skyblue", ax = axes[2], edgecolor = "black", width = 0.7)
axes[2].set_title("Distribution of average views", fontsize = 15)
axes[2].set_xlabel("Average views", fontsize = 14)

plt.tight_layout()
plt.savefig("graphs/channel_stats/channel_stats.png", format = "png", dpi = 300)
#plt.show()

### Keyword Videos by length ###
df_length_keywords = df[df["keyword_video"] == True]
bins = [1, 5, 20, 60, df_length_keywords["duration"].max()]
labels = ["1-5", "5-20", "20-60", ">60"]
df_length_keywords["binned"] = pd.cut(df_length_keywords["duration"], bins = bins, labels = labels)
bin_counts = df_length_keywords["binned"].value_counts().sort_index()
print(bin_counts)
plt.figure(figsize = (10, 6))
bin_counts.plot(kind = "bar", color = "skyblue", edgecolor ="black", width = 0.7)
plt.title("Videos by length", fontsize=16)
plt.xlabel("Duration in minutes", fontsize=14)
plt.ylabel("Number of videos", fontsize=14)

plt.xticks(rotation = 45)

plt.grid(axis = "y", linestyle ="--", alpha = 0.7)
plt.tight_layout()
plt.savefig("graphs/channel_stats/videos_by_length.png", format = "png", dpi = 300)


### How many different channels uploaded keyword videos? ###
keyword_df = df.groupby(["channel_id", "post_oct7"])["keyword_video"].agg("max").reset_index()

keyword_total = keyword_df.groupby("channel_id")["keyword_video"].agg("max").reset_index()
keyword_total = keyword_total[keyword_total["keyword_video"] == True]

df_pre = keyword_df[keyword_df["post_oct7"] == False]
df_pre = df_pre[df_pre["keyword_video"] == True]

df_post = keyword_df[keyword_df["post_oct7"] == True]
df_post = df_post[df_post["keyword_video"] == True]


print(f"{len(keyword_total)} channels uploaded at least one keyword video in the total period.")
print(f"{len(df_pre)} channels uploaded at least one keyword video before October 7.")
print(f"{len(df_post)} channels uploaded at least one keyword video after October 7.")
print(f"{number_of_channels - len(keyword_total)} channels uploaded no keyword video at all.")


all_channels = set(df["channel_id"])

set_pre = set(df[(df["post_oct7"] == False) & (df["keyword_video"] == True)]["channel_id"])
set_post = set(df[(df["post_oct7"] == True) & (df["keyword_video"] == True)]["channel_id"])
set_keyword_total = set_pre | set_post
set_never = all_channels - set_keyword_total

print(f"Channels that posted before but not after: {set_keyword_total - set_post}")

# (10) = Nur Vorher, (01) = Nur Nachher, (11) = Beide
subsets = (len(keyword_total) - len(df_post), len(df_post) - len(df_pre), len(df_pre))
total_channels = len(all_channels)
inactive_count = total_channels - (len(set_keyword_total))

plt.figure(figsize=(12, 8), facecolor='white')
v = venn2(subsets=subsets,
          set_labels = None,
          )
venn2_circles(subsets=subsets, linestyle='--', linewidth=1, color="gray")

label_map = {'10': f'Only before\n({subsets[0]})',
             '01': f'Only after\n({subsets[1]})',
             '11': f'Before and after\n({subsets[2]})'}

for id, text in label_map.items():
    lbl = v.get_label_by_id(id)
    if lbl:
        lbl.set_text(text)
        lbl.set_fontsize(22)
        lbl.set_fontweight('bold')

        # Spezifische Korrektur für das mittlere Label
        if id == '11':
            x, y = lbl.get_position()
            lbl.set_position((x, y - 0.1))

stats_box = (
    f"Total number of channels: {total_channels}\n"
    f"Inactive channels:     {inactive_count}\n"
)

# Platzierung oben rechts (xy: 1=ganz rechts, 1=ganz oben)
plt.text(0.85, 0.75, stats_box, transform=plt.gca().transAxes,
         fontsize=15,
         #verticalalignment='top',
         bbox=dict(boxstyle='round,pad=0.8', fc='#f9f9f9', ec='#d1d1d1'))


plt.tight_layout()
plt.savefig("graphs/channel_stats/keyword_activity_venn_final.png", dpi=300)
#plt.show()


### Keyword videos by channel ###

all_keyword_df = df[df["keyword_video"] == True]
print(len(all_keyword_df))
temp_df = all_keyword_df[all_keyword_df["post_oct7"] == False]
temp_df_2 = all_keyword_df[all_keyword_df["post_oct7"] == True]

print(len(temp_df))
print(len(temp_df_2))
print(f"\nDescriptives of views of keyword videos:")
print(f"{all_keyword_df["view_count"].describe()}")

#keyword_df = all_keyword_df[all_keyword_df["view_count"] > 10000]
#print(f"Keyword videos with at least 10000 views: {len(keyword_df)}")
keyword_df = all_keyword_df

keyword_df = keyword_df.groupby(["channel_title", "post_oct7"])["video_id"].agg("count").reset_index()
keyword_df = keyword_df.rename(columns={"video_id": "video_count"})
keyword_df.to_csv("gaga.csv")

keyword_pre = keyword_df[keyword_df["post_oct7"] == False]

plt.figure(figsize = (10, 6))
sns.histplot(keyword_pre["video_count"])

keyword_post = keyword_df[keyword_df["post_oct7"] == True]
#keyword_post = keyword_post[keyword_post["video_count"] < 300]

plt.figure(figsize = (10, 6))
sns.histplot(keyword_post["video_count"], log_scale=True)
plt.title("Keyword videos by channel", fontsize = 20)
plt.ylabel("Number of channels", fontsize = 16)
plt.xlabel("Number of videos", fontsize = 16)
plt.savefig("graphs/channel_stats/keyword_vids_by_channel.png", format = "png", dpi = 300)
#plt.show()


### OUTCOME ANALYSIS ###

# correlation between top-level comments and all comments

# df_comments.to_csv("comms.csv")
#
# all_keyword_df = pd.merge(all_keyword_df, df_comments, on ="video_id", how = "left")
# all_keyword_df.to_csv("merged.csv")

p_comm_correlation = df["comment_count"].corr(df["all_comments"], method = "pearson")
s_comm_correlation = df["comment_count"].corr(df["all_comments"], method = "spearman")

print("\nCorrelation of both comment measures")
print(f"Pearson correlation: {p_comm_correlation}")
print(f"Spearman correlation: {s_comm_correlation}")



### COMPARISON OF MEAN AND TOTAL METRICS ###
for m in metrics:
    plt.figure(figsize = (10, 6))
    ax = sns.barplot(
        data = df,
        x = "post_oct7",
        y = m,
        hue = "keyword_video",
        palette="muted",
        capsize = .1,
        errorbar=None,
        estimator = np.median,
    )

    plt.title(f'Videos before and after Oct 7: {m}', fontsize=20)
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    ax.set_xticklabels(['before Oct 7', 'after Oct 7'])
    h, l = ax.get_legend_handles_labels()
    ax.legend(h, ['no keyword', 'Keyword'], title="video type", fontsize = 16)
    plt.savefig(f"graphs/metrics/median/{m}_before_after")
#plt.show()


### TOTAL NUMBER OF VIEWS AND CHANNELS POSTING ###
df = df[df["keyword_video"] == True]
print(f"Percentage of videos by {len(major_news_channels)} news channels:{df["major_news_channel"].mean():.2f}")
#df = df[df["major_news_channel"] == False]
keyword_monthly_stats = df[df["keyword_video"] == True].groupby("starting_date").agg(
    total_views = ("view_count", "sum"),
    unique_channels = ("channel_id", "nunique"),
    total_videos = ("channel_id", "count")
).reset_index().sort_values("starting_date")

stats_wo_news = df[(df["keyword_video"] == True) & (df["major_news_channel"] == False)].groupby("starting_date").agg(
    total_views=("view_count", "sum"),
    unique_channels=("channel_id", "nunique")).reset_index().sort_values("starting_date")

fig, ax1 = plt.subplots(figsize=(15, 8), facecolor='white')

color_views = '#2c7fb8'
lns1 = ax1.plot(keyword_monthly_stats["starting_date"], keyword_monthly_stats["total_views"],
                marker='o', markersize=4, color=color_views, linewidth=2, label="Sum of Views")

lns2 = ax1.plot(stats_wo_news["starting_date"], stats_wo_news["total_views"],
                linestyle='--', color=color_views, linewidth=2, label="Views (w/o News)", alpha=0.7)

ax1.set_ylabel("Total Views", color=color_views, fontsize=16, fontweight='bold')
ax1.tick_params(axis='y', labelcolor=color_views, labelsize = 14)
ax1.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f'{x*1e-6:g}M' if x >= 1e6 else f'{x*1e-3:g}k'))
ax1.set_ylim(0, keyword_monthly_stats["total_views"].max() * 1.1) # start at 0

ax2 = ax1.twinx()
color_channels = '#f1a340'
lns3 = ax2.plot(keyword_monthly_stats["starting_date"], keyword_monthly_stats["unique_channels"],
                marker='s', markersize=4, color=color_channels, linewidth=2, label="Unique Channels", alpha = 0.8)
lns4 = ax2.plot(stats_wo_news["starting_date"], stats_wo_news["unique_channels"],
                linestyle='--', color=color_channels, linewidth=2, label="Channels (w/o News)", alpha=0.7)

ax2.set_ylabel("Unique Channels", color=color_channels, fontsize=16, fontweight='bold')
ax2.tick_params(axis='y', labelcolor=color_channels, labelsize = 14)
ax2.set_ylim(0, keyword_monthly_stats["unique_channels"].max() * 1.1) # start at 0

treatment_dt = pd.to_datetime("2023-10-07")
ax1.axvline(treatment_dt, color='#d73027', linestyle='--', linewidth=2)
ax1.text(treatment_dt, ax1.get_ylim()[1]*0.92, ' Oct 7 Attack', color='#d73027', fontweight='bold', ha='left', fontsize = 14)

israel_iran_dt = pd.to_datetime("2025-06-07")
ax1.axvline(israel_iran_dt, color='#d73027', linestyle='--', linewidth=2)
ax1.text(israel_iran_dt, ax1.get_ylim()[1]*0.85, ' Twelve-Day War', color='#d73027', fontweight='bold', ha='left', fontsize = 14)

iran_war_dt = pd.to_datetime("2026-02-07")
iran_war_dt_text = iran_war_dt - pd.Timedelta(days = 8)
ax1.axvline(iran_war_dt, color='#d73027', linestyle='--', linewidth=2)
ax1.text(iran_war_dt_text, ax1.get_ylim()[1]*0.7, ' Iran War', color='#d73027', fontweight='bold', ha='right', fontsize = 14)

lns = lns1 + lns2 + lns3 + lns4
labs = [l.get_label() for l in lns]
ax1.legend(lns, labs, loc='upper left', frameon=True, shadow=True, ncol = 2)

plt.title("Keyword Video Trends: Views and Channels", fontsize=20, pad=20)
ax1.set_xlabel("Month (starting on the 7th of each month)", fontsize=16)
ax1.grid(True, which='both', linestyle=':', alpha=0.7)

plt.tight_layout()
plt.savefig("graphs/trends/linegraph_views_channels_comparison.png", format = "png", dpi = 300)
plt.close()

fig, ax = plt.subplots(figsize = (10, 6))

sns.lineplot(data = keyword_monthly_stats, x="starting_date", y = "total_videos",
             color = color_views, linewidth = 2.5, label = "Number of Videos", ax = ax)

ax.axvline(treatment_dt, color='red', linestyle='--', linewidth=2)
ax.text(treatment_dt, ax.get_ylim()[1] * 0.9, 'Oct 7 Attack', color='red', fontweight='bold', ha='left')

ax.axvline(israel_iran_dt, color='#d73027', linestyle='--', linewidth=2)
ax.text(israel_iran_dt, ax.get_ylim()[1]*0.85, ' Twelve-Day War', color='#d73027', fontweight='bold', ha='right')

ax.axvline(iran_war_dt, color='#d73027', linestyle='--', linewidth=2)
ax.text(iran_war_dt_text, ax.get_ylim()[1]*0.7, ' Iran War', color='#d73027', fontweight='bold', ha='right')

ax.set_ylabel("Number of videos")
ax.set_xlabel("Month (starting on the 7th of each month")
plt.title("Total Keyword Videos per Month")
plt.grid(True, alpha=0.3)
plt.savefig("graphs/trends/number_of_videos_comparison.png", format = "png", dpi = 300)
plt.close()
#plt.show()

# 1. Den "Geburtstag" jedes Kanals bestimmen (erstes Keyword-Video)
first_posts = df[df["keyword_video"] == True].groupby("channel_id")["published_at"].min().reset_index()
first_posts = first_posts.sort_values("published_at")

# 2. Anzahl der neuen Kanäle pro Tag zählen
daily_new_channels = first_posts.groupby("published_at").size().reset_index(name="new_count")
daily_new_channels["published_at"] = daily_new_channels["published_at"].dt.tz_localize(None)
# 3. Kumulierte Summe berechnen
daily_new_channels["cumulative_channels"] = daily_new_channels["new_count"].cumsum()

# 4. Grafik erstellen
fig, ax = plt.subplots(figsize=(15, 8), facecolor='white')

# Die Fläche unter der Kurve füllen (wirkt oft professioneller)
ax.fill_between(daily_new_channels["published_at"], daily_new_channels["cumulative_channels"],
                color='#2c7fb8', alpha=0.2)

# Die Hauptlinie plotten
ax.plot(daily_new_channels["published_at"], daily_new_channels["cumulative_channels"],
        color='#2c7fb8', linewidth=3)

# --- Achsen-Styling (wie gewünscht vergrößert) ---
ax.set_title("Channel entries", fontsize=20, pad=20, fontweight='bold')
ax.set_ylabel("Number of channels", fontsize=16, fontweight='bold')
ax.set_xlabel("Date", fontsize=16)

ax.tick_params(axis='both', labelsize=14)
ax.grid(True, linestyle=':', alpha=0.6)

# X-Achse Formatierung (alle 2 Monate ein Label für die Übersicht)
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
plt.xticks(rotation=45)

# --- Vertikale Linien für Ereignisse ---
event_color = '#d73027'
events = [
    (pd.to_datetime("2023-10-07"), "Oct 7 Attack"),
    (pd.to_datetime("2025-06-07"), "Twelve-Day War"),
    (pd.to_datetime("2026-02-07"), "Iran War")
]

for dt, label in events:
    if dt >= daily_new_channels["published_at"].min() and dt <= daily_new_channels["published_at"].max():
        ax.axvline(dt, color=event_color, linestyle='--', linewidth=2)
        # Positionierung des Textes dynamisch über der Linie
        ax.text(dt -pd.Timedelta(days=5), ax.get_ylim()[1] * 0.05, f' {label}', color=event_color,
                fontweight='bold', fontsize=12, ha = "right")

# Legende
#ax.legend(loc='upper left', fontsize=14, frameon=True, shadow=True)

# Spines (Rahmen) säubern
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.tight_layout()
plt.savefig("entries.png", format = "png", dpi = 300)
plt.close()








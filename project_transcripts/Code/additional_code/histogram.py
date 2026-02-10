import pandas as pd
import json
import matplotlib.pyplot as plt
import seaborn as sns

#transcript_filepath = "../Transcript files/youtube_transkripte_2.csv"
meta_info_filepath = "../../JSON Files/videos_keywords_total.json"

#df = pd.read_csv(transcript_filepath)
with open(meta_info_filepath, "r", encoding = "utf-8") as f:
    json_data = json.load(f)

metadata = pd.DataFrame(json_data)
#merged_df = pd.merge(df, metadata, on = "video_id")

channel_counts = metadata["channel_id"].value_counts()
filtered_counts_small = channel_counts[channel_counts <=200]
filtered_counts_large = channel_counts[channel_counts > 200]
print(f"channel gesamt: {len(channel_counts)}. Channels nach Filterung: {len(filtered_counts_small)}")
value_counts_per_channel_small = filtered_counts_small.values

value_counts_per_channel_large = filtered_counts_large.values
print(f"small channels: {len(filtered_counts_small)}")
print(f"large channels: {len(filtered_counts_large)}")
plt.figure(figsize=(10, 6))
sns.histplot(value_counts_per_channel_small,
             bins = range(1, value_counts_per_channel_small.max() +2),
             kde = False,
             color = "skyblue",
             discrete=True)

plt.title("Häufigkeit der Video-Anzahl pro Kanal")
plt.xlabel("Anzahl der Videos")
plt.ylabel("Anzahl der Kanäle")

plt.show()


plt.figure(figsize=(10, 6))
sns.histplot(value_counts_per_channel_large,
             bins = range(1, value_counts_per_channel_large.max() +2),
             kde = False,
             color = "skyblue",
             discrete=True)

plt.title("Häufigkeit der Video-Anzahl pro Kanal")
plt.xlabel("Anzahl der Videos")
plt.ylabel("Anzahl der Kanäle")

plt.show()
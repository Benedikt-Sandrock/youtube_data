import time
import json
import os
from dotenv import load_dotenv
from googleapiclient.discovery import build
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

published_after_analysis = "2022-10-07T00:00:00Z"
published_before_analysis = "2026-01-31T00:00:00Z"


load_dotenv()
api_key = os.getenv("API_KEY")
api_key_c = os.getenv("API_KEY_C")

youtube = build("youtube", "v3", developerKey = api_key)

relevant_channels = {
    "Vermietertagebuch - Alexander Raue": "UCiTJladOHCMkKndVBsn23VQ"
}

print(os.getcwd())

def chunk_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


def get_channel_metadata(youtube_client, input_path, output_path):
    with open(input_path, "r", encoding = "utf-8") as f:
        channel_ids = json.load(f)

    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            try:
                all_data = json.load(f)
            except json.JSONDecodeError:
                all_data = []
    else:
        all_data = []


    already_requested = {c["channel_id"] for c in all_data}
    channel_ids_filtered = [c for c in channel_ids if c not in already_requested]
    y = len(channel_ids) - len(channel_ids_filtered)

    print(f"Channel IDs: {len(channel_ids)}"
          f"\nOf which already classfied: {y}")

    print(f"Requesting metadata for {len(channel_ids_filtered)} channels...")

    for batch in chunk_list(channel_ids_filtered, 50):
        request = youtube_client.channels().list(
            part="snippet,statistics",
            id=",".join(batch)
        )
        response = request.execute()

        for item in response.get('items', []):
            data = {
                'name': item['snippet']['title'],
                'subscribers': int(item['statistics'].get('subscriberCount', 0)),
                'views': int(item['statistics'].get('viewCount', 0)),
                'video_files': int(item['statistics'].get('videoCount', 0)),
                'channel_id': item['id']
            }
            all_data.append(data)

    with open(output_path, "w", encoding = "utf-8") as f:
        json.dump(all_data, f, indent = 2, ensure_ascii= False)


import json
import os


def get_channel_metadata_2(youtube_client, input_path, output_path):
    with open(input_path, "r", encoding="utf-8") as f:
        channel_ids = json.load(f)
    channel_ids = [c["channel_id"] for c in channel_ids]

    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            try:
                all_data = json.load(f)
            except json.JSONDecodeError:
                all_data = []
    else:
        all_data = []

    # Wir nutzen 'id' statt 'channel_id', da das Original-API-Objekt 'id' verwendet
    already_requested = {c["id"] for c in all_data if "id" in c}
    channel_ids_filtered = [c for c in channel_ids if c not in already_requested]

    y = len(channel_ids) - len(channel_ids_filtered)
    print(f"Channel IDs: {len(channel_ids)}\nBereits verarbeitet: {y}")
    print(f"Requesting full metadata for {len(channel_ids_filtered)} channels...")

    # Parts, die alle relevanten Informationen abdecken
    # Hinweis: 'auditDetails' oder 'contentOwnerDetails' benötigen spezielle Berechtigungen/OAuth
    all_parts = "snippet,statistics,contentDetails,brandingSettings,topicDetails,status"

    for batch in chunk_list(channel_ids_filtered, 50):
        request = youtube_client.channels().list(
            part=all_parts,
            id=",".join(batch)
        )
        response = request.execute()

        for item in response.get('items', []):
            # Wir speichern hier das komplette 'item' Objekt.
            # So hast du Zugriff auf Keywords, Banner, Topic-IDs etc.
            all_data.append(item)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)


def get_video_metadata(youtube_client, input_path, output_path):
    """
    Takes YouTube client and list of video IDs as input and returns a dictionary with metadata for the respective
    video_files.
    """
    print("Getting video metadata...")

    print(f"\nLoading input file: {input_path}")
    with open(input_path, "r", encoding = "utf-8") as f:
        video_ids = json.load(f)

    if isinstance(video_ids[0], dict): #if a list of dicts is imported, only video ids are extracted
        print("Dict imported is transferred to list.")
        video_ids = [v["video_id"] for v in video_ids]

    already_requested = set()
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    already_requested.add(data["video_id"])
                except json.JSONDecodeError:
                    continue

    video_ids_filtered = [v for v in video_ids if v not in already_requested]
    y = len(video_ids) - len(video_ids_filtered)

    print(f"Total number ideo IDs: {len(video_ids)}"
          f"\nFor {y} video IDs, metadata already exists.")

    print(f"Requesting metadata for {len(video_ids_filtered)} video_files...")
    chunk = 1
    with open(output_path, "a", encoding = "utf-8") as f_out:
        for batch in chunk_list(video_ids_filtered, 50):
            all_videos = []
            request = youtube_client.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(batch)
            )
            response = request.execute()

            for item in response.get("items", []):
                video_data = {
                    "video_id": item["id"],
                    "title": item["snippet"]["title"],
                    "channel_title": item["snippet"]["channelTitle"],
                    "channel_id": item["snippet"]["channelId"],
                    "published_at": item["snippet"]["publishedAt"],
                    "duration": item["contentDetails"].get("duration"),
                    "view_count": item["statistics"].get("viewCount"),
                    "like_count": item["statistics"].get("likeCount"),
                    "comment_count": item["statistics"].get("commentCount"),
                }
                f_out.write(json.dumps(video_data, ensure_ascii=False) + "\n")
            f_out.flush()

            if chunk % 10 ==0:
                print(f"Processed {chunk*50} videos.")
            time.sleep(0.1)
            chunk += 1
    # print(f"Saving metadata file to: {output_path}")
    # with open(output_path, "w", encoding = "utf-8") as f:
    #     json.dump(all_videos, f, indent = 2, ensure_ascii=False)


def get_channel_videos(channel_id, published_after, published_before):
# Uploads-Playlist-ID
    channel_response = youtube.channels().list(
        part="contentDetails",
        id=channel_id
    ).execute()

    uploads_playlist_id = channel_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    # Videos aus der Playlist abrufen
    videos = []
    next_page = None

    while True:
        pl_request = youtube.playlistItems().list(
            part="contentDetails,snippet",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page
        )
        pl_response = pl_request.execute()

        for item in pl_response.get("items", []):
            content_details = item.get("contentDetails")
            snippet = item.get("snippet", {})

            if not isinstance(content_details, dict):
                video_id = snippet.get("resourceId", {}).get("videoId")
                pub_date = snippet.get("publishedAt")
            else:
                video_id = content_details.get("videoId")
                pub_date = content_details.get("videoPublishedAt") or snippet.get("publishedAt")

            title = snippet.get("title")

            if not video_id or not pub_date:
                continue
            # Abbruch, wenn Video vor dem Zeitraum liegt
            if pub_date < published_after:
                next_page = None  # Stoppe Paging
                break

            # Video innerhalb des Zeitrahmens speichern
            if pub_date <= published_before:
                videos.append({
                    "video_id": video_id,
                    "channel_id": channel_id,
                    "published_at": pub_date,
                    "title": title
                })

        next_page = pl_response.get("nextPageToken")
        if not next_page:
            break

    return videos

# with open("../../JSON Files/ident_1803/large_german_channels/video_files/metadata_all_videos_100k_channels_keywords.json", "r", encoding ="utf-8") as f:
#     data = json.load(f)
#
# data = [v for v in data if v["channel_id"] == "UCQGqiGhMjc_p4lZEhSTb12g"]
# print(len(data))

#print(df.head())
#
#
# with open("videos_nius.json", "w", encoding = "utf-8") as f:
#     json.dump(data, f, indent=2, ensure_ascii=False)

#list_of_vids = get_channel_videos("UCLoWcRy-ZjA-Erh0p_VDLjQ", published_after_analysis, published_before_analysis)

#with open("videos.json", "w", encoding = "utf-8") as f:
#    json.dump(list_of_vids, f, indent = 2, ensure_ascii= False)

#get_video_metadata(youtube, "videos_nius.json", "videos_nius_metadata.json")

keywords = ["nahe osten", "naher osten", "nahen osten", "nahost",
            "israel", "palästina", "gaza", "hamas", "IDF", "Jerusalem", "netanjahu", "netanyahu"]

pattern = '|'.join(keywords)
treatment_day = "2023-10-07T00:00:00Z"

df = pd.read_json("../../JSON Files/ident_1803/large_german_channels/video_files/metadata_all_videos.jsonl", lines= True)
right_wing_channels = ["Tichys Einblick", "JUNGE FREIHEIT", "Oli", "COMPACT", "COMPACT-TV", "Carsten Jahn - TEAM HEIMAT",
                       "Clownswelt", "Oli investiert", "Marc Friedrich", "Alice Weidel", "NachDenkSeiten", "NIUS",
                       "Roger Beckamp", "Kettner-Edelmetalle (Gold & Silber)", "Schuler! Fragen, was ist",
                       "Steuern mit Kopf", "Ketzer der Neuzeit", "Gegenpol", "Hallo Meinung", "Vermietertagebuch - Alexander Raue",
                       "POLITIK SPEZIAL - Stimme der Vernunft ", "Digitaler Chronist", "Achtung, Reichelt!"]
df["category"] = df["channel_title"].isin(right_wing_channels)

df = df[df["channel_title"] =="Gegenpol"]
#df = df[df["channel_title"].isin(right_wing_channels)]
#print(df["channel_title"].head(20))
print(f"Len before filtering out shorts: {len(df)}")
df["duration"] = pd.to_timedelta(df["duration"])
df["duration"] = (df["duration"].dt.total_seconds()) / 60
df = df[df["duration"] > 1]
print(f"Len after filtering out shorts: {len(df)}")

df["published_at"] = pd.to_datetime(df["published_at"])
df = df[df["published_at"] > "2022-10-07T00:00:00Z"]
print(f"Len after filtering out videos before Oct 7 2022: {len(df)}")


df["comment_ratio"] = df["comment_count"] / df["view_count"] *100
df["like_ratio"] = df["like_count"] / df["view_count"] *100
df["engagement_ratio"] = (df["like_count"] + df["comment_count"]) /df["view_count"] *100

df["keyword_video"] = df["title"].str.contains(pattern, case = False, na =False)
keyword_count = df[df["keyword_video"] == True]

print(f"Number of keyword videos: {len(keyword_count)}")


df["post_oct7"] = df["published_at"] >= treatment_day

metrics_relative = ["view_count", "like_ratio", "comment_ratio"]
metrics_absolute = ["view_count", "like_count", "comment_count"]
metrics = ["view_count", "like_count", "like_ratio", "comment_count", "comment_ratio"]
df_average = df.groupby(["channel_title", "post_oct7", "keyword_video"])[metrics].mean().reset_index()

df["starting_date"] = df["published_at"] - pd.Timedelta(days = 6)
df["starting_date"] = df["starting_date"].dt.to_period("M").dt.to_timestamp()
df["starting_date"] = df["starting_date"].apply(lambda x: x.replace(day = 7))

df_monthly = df.groupby(["channel_title", "starting_date", "keyword_video"])[metrics].mean().reset_index()


keyword_channels = df[df["keyword_video"] == True]["channel_id"].unique()
keyword_df = df[df["channel_id"].isin(keyword_channels)]


videos_nov22 = df[(df["starting_date"] == "2022-11-07") & (df["keyword_video"] == True)]
videos_nov22 = videos_nov22.sort_values(by = "comment_count", ascending =False)
videos_nov22.to_csv("videos_nov22.csv", index = False)
df.to_csv("all_videos.csv", index = False)
###
# Bar diagram
###
#restrict sample to channels with at least one keyword video
# print(len(keyword_df))
# plt.figure(figsize=(10, 6))
#
# ax = sns.countplot(
#     data=keyword_df,
#     x='post_oct7',
#     hue='keyword_video',
#     palette='muted'
# )
#
# ax.set_xticklabels(['before Oct 7', 'after Oct 7'])
# h, l = ax.get_legend_handles_labels()
# ax.legend(h, ['no keyword', 'keyword'], title="video type")
#
# plt.title('Number of videos per category')
# plt.ylabel('number of videos')
#
# plt.show()
#
#
# for m in metrics:
#     plt.figure(figsize = (10, 6))
#     ax = sns.barplot(
#         data = keyword_df,
#         x = "post_oct7",
#         y = m,
#         hue = "keyword_video",
#         palette="muted",
#         capsize = .1
#     )
#
#     plt.title(f'Videos before and after Oct 7: {m}', fontsize=14)
#     ax.set_xticklabels(['before Oct 7', 'after Oct 7'])
#     h, l = ax.get_legend_handles_labels()
#     ax.legend(h, ['no keyword', 'Keyword'], title="video type")
#     plt.show()
#
# plt.figure(figsize = (10, 6))
#
# sns.barplot(
#     data=df_average,
#     x="post_oct7",
#     y="view_count",
#     hue="keyword_video",
#     estimator = "mean",
#     palette = "muted",
#     capsize = .1
#
# )
# plt.title("Durchschnittliche Views (Jeder Kanal zählt gleich viel)")
# plt.show()
#
# plt.figure(figsize = (10, 6))
#
# sns.barplot(
#     data=df_average,
#     x="post_oct7",
#     y="view_count",
#     hue="keyword_video",
#     estimator = "median",
#     palette = "muted",
#     capsize = .1
#
# )
# plt.title("Median Views (Jeder Kanal zählt gleich viel)")
# plt.show()
dfs = [df, df_monthly]
# for d in dfs:
#     for m in metrics:
#         plt.figure(figsize = (10, 6))
#         sns.lineplot(
#             data=d,
#             x="starting_date",
#             y=m,
#             hue="keyword_video",
#             estimator = "mean",
#             palette = "muted",
#             marker = "o",
#             errorbar = None
#         )
#
#         plt.axvline(pd.Timestamp('2023-10-07'), color='red', linestyle='--', label='Treatment Start')
#         plt.title("Monatliche Analyse (Intervalle: 7. bis 6. des Folgemonats)")
#         plt.xlabel("Beginn des Intervalls")
#         plt.legend(title="Keyword Video")
#         plt.grid(True, alpha=0.3)
#         plt.show()

# for d in dfs:
#     for m in metrics_relative:
#         plt.figure(figsize=(12, 6))
#
#         # 1. Den Basis-Plot erstellen
#         ax = sns.lineplot(
#             data=d, x="starting_date", y=m, hue="keyword_video",
#             estimator="sum", palette="muted", marker="o", errorbar=None
#         )
#
#         # 2. Die Anzahlen (Counts) berechnen
#         # Wir gruppieren nach Datum und Keyword-Status, um die n-Größe zu erhalten
#         counts = d.groupby(["starting_date", "keyword_video"]).size().reset_index(name="n")
#
#         # 3. Mittelwerte berechnen (damit wir wissen, auf welcher Höhe der Text stehen muss)
#         means = d.groupby(["starting_date", "keyword_video"])[m].sum().reset_index()
#
#         # Beides zusammenführen
#         stats = pd.merge(means, counts, on=["starting_date", "keyword_video"])
#
#         # 4. Die Zahlen an die Punkte schreiben
#         for i in range(len(stats)):
#             row = stats.iloc[i]
#             if row["keyword_video"] == True:
#                 ax.annotate(
#                     text=f'{int(row["n"])}',  # Der Text
#                     xy=(row["starting_date"], row[m]),  # Die exakte Position des Datenpunkts
#                     xytext=(0, 8),  # Versatz: 0 Pixel horizontal, 7 Pixel vertikal
#                     textcoords="offset points",  # Sagt Matplotlib, dass (0,7) Pixel-Verschiebungen sind
#                     ha="center",  # Text horizontal zentrieren
#                     fontsize=9,
#                     color="black"
#                 )
#
#         # Optik & Treatment-Linie
#         plt.axvline(pd.Timestamp('2023-10-07'), color='red', linestyle='--')
#         plt.title(f"Analyse: {m} (mit Fallzahlen n)")
#         plt.grid(True, alpha=0.2)
#         plt.show()
# for d in dfs:
#     for m in metrics_absolute:
#         fig, ax1 = plt.subplots(figsize=(12, 6))
#
#         # 1. Daten für beide Gruppen vorbereiten
#         data_true = d[d["keyword_video"] == True].groupby("starting_date")[m].sum().reset_index()
#         counts_true = d[d["keyword_video"] == True].groupby("starting_date").size().reset_index(name="n")
#
#         data_false = d[d["keyword_video"] == False].groupby("starting_date")[m].sum().reset_index()
#
#         # 2. Erste Linie (Keyword = True) auf ax1
#         color_true = "tab:blue"
#         sns.lineplot(data=data_true, x="starting_date", y=m, ax=ax1,
#                      marker="o", color=color_true, label="Keyword-Videos (Summe)")
#         ax1.set_ylabel(f"Summe {m} (Keyword)", color=color_true, fontweight="bold")
#         ax1.tick_params(axis='y', labelcolor=color_true)
#
#         # 3. Zweite Y-Achse für Keyword = False
#         ax2 = ax1.twinx()
#         color_false = "tab:orange"
#         sns.lineplot(data=data_false, x="starting_date", y=m, ax=ax2,
#                      marker="o", color=color_false, label="Andere Videos (Summe)")
#         ax2.set_ylabel(f"Summe {m} (Andere)", color=color_false, fontweight="bold")
#         ax2.tick_params(axis='y', labelcolor=color_false)
#
#         # 4. Fallzahlen nur für Keyword-Videos hinzufügen
#         stats_true = pd.merge(data_true, counts_true, on="starting_date")
#         for i in range(len(stats_true)):
#             row = stats_true.iloc[i]
#             ax1.annotate(
#                 text=f'{int(row["n"])}',
#                 xy=(row["starting_date"], row[m]),
#                 xytext=(0, 10),
#                 textcoords="offset points",
#                 ha="center", fontsize=9, color=color_true
#             )
#
#         # Optik & Treatment-Linie
#         plt.axvline(pd.Timestamp('2023-10-07'), color='red', linestyle='--', label='Treatment Start')
#         plt.title(f"Vergleich der Summen: {m}\n(Unabhängige Skalierung)")
#
#         # Legenden zusammenführen
#         lines, labels = ax1.get_legend_handles_labels()
#         lines2, labels2 = ax2.get_legend_handles_labels()
#         ax2.legend(lines + lines2, labels + labels2, loc="upper left")
#         ax1.get_legend().remove()  # Entfernt die Standard-Legende von ax1
#
#         ax1.grid(True, alpha=0.2)
#         plt.show()

# Beispiel: Wir teilen nach der Spalte 'category' auf
split_col = "category"

# for d in dfs:
#     for m in metrics:
#         fig, ax1 = plt.subplots(figsize=(14, 7))
#         ax2 = ax1.twinx()
#
#         # Farben definieren (Blautöne für Keywords, Orangetöne für Andere)
#         colors_true = ["#1f77b4", "#aec7e8"]
#         colors_false = ["#ff7f0e", "#ffbb78"]
#
#         # 1. KEYWORD-VIDEOS (Linke Achse - ax1)
#         # Wir loopen durch die Kategorien innerhalb der Keyword-Gruppe
#         data_kw = d[d["keyword_video"] == True]
#         categories = data_kw[split_col].unique()
#
#         for i, cat in enumerate(categories):
#             subset = data_kw[data_kw[split_col] == cat].groupby("starting_date")[m].sum().reset_index()
#             counts = data_kw[data_kw[split_col] == cat].groupby("starting_date").size().reset_index(name="n")
#
#             sns.lineplot(data=subset, x="starting_date", y=m, ax=ax1, marker="o",
#                          label=f"KW: {cat}", color=colors_true[i % len(colors_true)])
#
#             # Annotationen für die Keyword-Subgruppen
#             stats = pd.merge(subset, counts, on="starting_date")
#             for _, row in stats.iterrows():
#                 ax1.annotate(f'n={int(row["n"])}', (row["starting_date"], row[m]),
#                              xytext=(0, 10), textcoords="offset points", ha="center",
#                              fontsize=8, color=colors_true[i % len(colors_true)])
#
#         # 2. ANDERE VIDEOS (Rechte Achse - ax2)
#         data_other = d[d["keyword_video"] == False]
#         for i, cat in enumerate(categories):
#             subset = data_other[data_other[split_col] == cat].groupby("starting_date")[m].sum().reset_index()
#             sns.lineplot(data=subset, x="starting_date", y=m, ax=ax2, marker="x", linestyle="--",
#                          label=f"Andere: {cat}", color=colors_false[i % len(colors_false)])
#
#         # Design-Anpassungen
#         ax1.set_ylabel(f"Summe {m} (Keyword Groups)", fontweight="bold", color="#1f77b4")
#         ax2.set_ylabel(f"Summe {m} (Andere Groups)", fontweight="bold", color="#ff7f0e")
#         plt.axvline(pd.Timestamp('2023-10-07'), color='red', linestyle='--', alpha=0.7)
#
#         # Gemeinsame Legende
#         h1, l1 = ax1.get_legend_handles_labels()
#         h2, l2 = ax2.get_legend_handles_labels()
#         ax1.legend(h1 + h2, l1 + l2, loc='upper left', bbox_to_anchor=(1.1, 1))
#
#         plt.title(f"Aufgeschlüsselte Summen-Analyse: {m} nach {split_col}")
#         ax1.grid(True, alpha=0.2)
#         plt.tight_layout()
#         plt.show()
#
# import matplotlib.pyplot as plt
# import seaborn as sns

# Variable für die Aufteilung (stelle sicher, dass diese Spalte existiert)
# split_col = "category"

# for d in dfs:
#     for m in metrics:
#         # Erstellt zwei Subplots untereinander
#         fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 12), sharex=True)
#
#         # --- 1. PLOT: KEYWORD-VIDEOS ---
#         data_kw = d[d["keyword_video"] == True]
#         sns.lineplot(
#             data=data_kw, x="starting_date", y=m, hue=split_col,
#             estimator="sum", marker="o", errorbar=None, ax=ax1
#         )
#
#         # Fallzahlen (n) für Keyword-Videos hinzufügen
#         stats_kw = data_kw.groupby(["starting_date", split_col])[m].sum().reset_index()
#         counts_kw = data_kw.groupby(["starting_date", split_col]).size().reset_index(name="n")
#         stats_kw = stats_kw.merge(counts_kw, on=["starting_date", split_col])
#
#         for _, row in stats_kw.iterrows():
#             ax1.annotate(f'n={int(row["n"])}', (row["starting_date"], row[m]),
#                          xytext=(0, 8), textcoords="offset points", ha="center", fontsize=8)
#
#         ax1.set_title(f"SUMME {m.upper()}: Keyword-Videos nach {split_col}", fontsize=14, fontweight='bold')
#         ax1.set_ylabel("Summe (Keyword)")
#         ax1.grid(True, alpha=0.3)
#
#         # --- 2. PLOT: ANDERE VIDEOS ---
#         data_other = d[d["keyword_video"] == False]
#         sns.lineplot(
#             data=data_other, x="starting_date", y=m, hue=split_col,
#             estimator="sum", marker="x", linestyle="--", errorbar=None, ax=ax2
#         )
#
#         ax2.set_title(f"SUMME {m.upper()}: Andere Videos nach {split_col}", fontsize=14, fontweight='bold')
#         ax2.set_ylabel("Summe (Andere)")
#         ax2.grid(True, alpha=0.3)
#
#         # Gemeinsame Einstellungen
#         plt.axvline(pd.Timestamp('2023-10-07'), color='red', linestyle='--', label='Treatment Start')
#
#         # Layout optimieren
#         plt.tight_layout()
#         plt.show()

# for d_idx, d in enumerate(dfs):
#     # Datensatz-Label bestimmen
#     label_type = "Kanal-Ebene" if d_idx == 0 else "Video-Ebene"
#
#     for m in metrics:
#         # Wir trennen nach Keyword-Status
#         for is_keyword in [True, False]:
#             subset_all = d[d["keyword_video"] == is_keyword]
#             typename = "Keyword-Videos" if is_keyword else "Andere Videos"
#             categories = subset_all["category"].unique()
#
#             # Für jede Kategorie eine eigene Grafik (eigene Y-Achse)
#             for cat in categories:
#                 subset_cat = subset_all[subset_all["category"] == cat]
#
#                 # Berechnung der Summen und Counts für die Beschriftung
#                 plot_data = subset_cat.groupby("starting_date")[m].sum().reset_index()
#                 counts = subset_cat.groupby("starting_date").size().reset_index(name="n")
#                 stats = pd.merge(plot_data, counts, on="starting_date")
#
#                 plt.figure(figsize=(12, 5))
#
#                 # Der Plot
#                 ax = sns.lineplot(
#                     data=plot_data, x="starting_date", y=m,
#                     marker="o", color="tab:blue" if is_keyword else "tab:orange"
#                 )
#
#                 # Annotationen (n-Zahlen) hinzufügen
#                 for _, row in stats.iterrows():
#                     ax.annotate(
#                         f'n={int(row["n"])}',
#                         (row["starting_date"], row[m]),
#                         xytext=(0, 10), textcoords="offset points",
#                         ha="center", fontsize=9, fontweight="bold"
#                     )
#
#                 # Optik & Treatment-Linie
#                 plt.axvline(pd.Timestamp('2023-10-07'), color='red', linestyle='--')
#
#                 # Titel enthält alle wichtigen Infos
#                 plt.title(f"{typename} | Kategorie: {cat} | Metrik: {m}\n({label_type})", fontsize=13)
#                 plt.ylabel(f"Summe {m}")
#                 plt.xlabel("Startdatum des Intervalls")
#                 plt.grid(True, alpha=0.3)
#
#                 plt.tight_layout()
#                 plt.show()

###
# Aggregation
###


agg_logic = {m: "mean" for m in metrics}
agg_logic["video_id"] = "count"

grouped = keyword_df.groupby(["channel_id", "channel_title", "post_oct7", "keyword_video"]).agg(agg_logic).unstack(level = [2,3])
print(grouped.columns)
new_cols = []

for col, post, key in grouped.columns:
    p_val = int(post)
    k_val = int(key)

    if col =="video_id":
        new_cols.append(f"video_count_post{p_val}_key{k_val}")
    else:
        new_cols.append(f"{col}_mean_post{p_val}_key{k_val}")
print(new_cols)

grouped.columns = new_cols

df_final = grouped.reset_index().fillna(0)

with pd.option_context("display.max_columns", None):
    print(df_final.head())

df_final.to_csv("all_videos_metrics.csv", index = False)
top_engagement = df.nlargest(5, "engagement_ratio")
top_likes = df.nlargest(5, "like_ratio")
top_comments = df.nlargest(5, "comment_ratio")



with pd.option_context("display.max_columns", None):
    print(df.describe(percentiles=[0.25, 0.5, 0.75, 0.9, 0.95]).round(2))
    print(top_engagement)
    print(top_likes)
    print(top_comments)



get_video_metadata(youtube,
                   "../../conflict_over_time/channel_identification/large_german_channels/video_files/all_videos_50k_channels.json",
                   "../../JSON Files/ident_1803/large_german_channels/video_files/metadata_all_videos.jsonl")

#get_channel_metadata_2(youtube, "../../JSON Files/ident_1803/large_german_channels/german_channels_100000k.json",
                       #"complete_metadata.json")
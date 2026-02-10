from googleapiclient.discovery import build
import json
import os
from polyt_key_variables import published_before_analysis, published_after_analysis

# -----------------------------
# API-Key und Einstellungen
# -----------------------------
api_key = "AIzaSyBUg0XIryem2_WtenRUKDA1bwLsiDzMLYE"
api_key_c = "AIzaSyBjtKhLfb-EyaWxc-vCROX6VTWA66j8sHE"


youtube = build('youtube', 'v3', developerKey=api_key_c)

videos_total_file = "../../JSON Files/videos_by_channel_total_german.json"
videos_total_file_2 = "../../JSON Files/videos_by_channel_total_german_3years.json"

if os.path.exists(videos_total_file):
    with open(videos_total_file, "r", encoding = "utf-8") as f:
        videos_total = json.load(f)
else:
    videos_total = []

processed_channel_ids = {v["channel_id"] for v in videos_total}
print(f"Bereits verarbeitete Channels: {len(processed_channel_ids)}")

# Channel IDs

with open(f"../../JSON Files/channel_ids_classified/all_channel_ids_german_3years.json", "r", encoding="utf-8") as f:
    channel_ids = json.load(f)


# -----------------------------
# Funktion: Videos aus Uploads-Playlist eines Kanals holen
# -----------------------------
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
            video_id = item["contentDetails"]["videoId"]
            pub_date = item["contentDetails"]["videoPublishedAt"]
            title = item["snippet"]["title"]

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


# -----------------------------
# Hauptprogramm: nur neue Kanäle abfragen
# -----------------------------
new_videos = []

for cid in channel_ids:

    if cid in processed_channel_ids:
        print(f"Channel bereits vorhanden, übersprungen: {cid}")
        continue

    print(f"Neue Channel ID: {cid}")
    channel_videos = get_channel_videos(cid, published_after_analysis, published_before_analysis)
    print(f"Gefundene Videos: {len(channel_videos)}")
    new_videos.extend(channel_videos)

# -----------------------------
# Deduplication nach Video-ID
# -----------------------------
all_videos = videos_total + new_videos
unique_videos = {v["video_id"]: v for v in all_videos}
videos_total = list(unique_videos.values())

with open(videos_total_file_2, "w", encoding = "utf-8") as f:
    json.dump(videos_total, f, ensure_ascii = False, indent = 2)

# with open(f"json_files/query_list/files_{query}/videos_by_channel_{query}.json", "w", encoding = "utf-8") as f:
#     json.dump(new_videos, f, ensure_ascii = False, indent= 2)

# with open(videos_total_file, "r", encoding = "utf-8") as f:
#     data = json.load(f)

# all_processed_ids = list({v["channel_id"] for v in videos_total})
#
# with open("json_files/all_channel_ids_processed.json", "w", encoding ="utf-8") as f:
#     json.dump(all_processed_ids, f, ensure_ascii = False, indent =2)

print("\nVerarbeitung abgeschlossen")
print(f"Gesamtvidoes: {len(videos_total)}")
print(f"Neu hinzugefügte Videos: {len(new_videos)}")
from googleapiclient.discovery import build
import json
import os
from settings_variables import published_before_analysis, published_after_analysis
from dotenv import load_dotenv
"""
To change from updating to checking new channels, comment out updating block and activate new channels block
and deduplication block
Otherwise, only updating block needs to be activated
"""

# -----------------------------
# API-Key und Einstellungen
# -----------------------------
load_dotenv()
api_key = os.getenv("API_KEY")
api_key_c = os.getenv("API_KEY_C")


youtube = build('youtube', 'v3', developerKey=api_key_c)


# -----------------------------
# Configuration
# -----------------------------
#videos are always saved in the same file to have a collection of all videos ever identified.
#Only channel_input needs to be adjusted.
videos_total_file = "../JSON Files/video_files/videos_total.json"
videos_total_file_2 = "../JSON Files/video_files/videos_total.json"

channel_input = f"../conflict_over_time/channel_identification/large_german_channels/german_channels_50000k.json"



newest_video_per_channel = {}
if os.path.exists(videos_total_file):
    with open(videos_total_file, "r", encoding = "utf-8") as f:
        videos_total = json.load(f)

    for v in videos_total:
        cid = v["channel_id"]
        pub_at = v["published_at"]
        if "no_video_found" in pub_at: continue

        if cid not in newest_video_per_channel or pub_at > newest_video_per_channel[cid]:
            newest_video_per_channel[cid] = pub_at
else:
    videos_total = []

#
# Channel IDs

with open(channel_input, "r", encoding="utf-8") as f:
    channel_ids_dict = json.load(f)

channel_ids = [c["channel_id"] for c in channel_ids_dict]


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


def get_new_channel_videos(channel_id, published_after, published_before, last_known_newest):

    channel_response = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    if not channel_response.get("items"): return []

    uploads_playlist_id = channel_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
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
            snippet = item.get("snippet", {})
            video_id = item.get("contentDetails", {}).get("videoId")
            pub_date = item.get("contentDetails", {}).get("videoPublishedAt") or snippet.get("publishedAt")

            if not video_id or not pub_date: continue

            # STOPP-BEDINGUNG: Sobald wir ein Video sehen, das wir schon kennen (oder älter ist)
            if last_known_newest and pub_date <= last_known_newest:
                return videos  # Wir haben alle neuen Videos gefunden!

            # Zeitrahmen-Check (für das neue obere Limit)
            if pub_date <= published_before and pub_date >= published_after:
                videos.append({
                    "video_id": video_id,
                    "channel_id": channel_id,
                    "published_at": pub_date,
                    "title": snippet.get("title")
                })

            # Falls das Video schon älter als unser Suchzeitraum ist, können wir auch aufhören
            if pub_date < published_after:
                return videos

        next_page = pl_response.get("nextPageToken")
        if not next_page: break

    return videos
# -----------------------------
# Hauptprogramm: nur neue Kanäle abfragen  ## if new channels are requested
# -----------------------------

processed_channel_ids = {v["channel_id"] for v in videos_total}
print(f"Insgesamt bereits verarbeitete Channels: {len(processed_channel_ids)}")
print(f"Neue Channels: {len(channel_ids)}")
channel_ids_set = set(channel_ids)
new_channel_ids = channel_ids_set - processed_channel_ids
print(f"Davon noch nicht überprüft: {len(new_channel_ids)}")

new_videos = []

for cid in channel_ids:
    try:
        if cid in processed_channel_ids:
            #print(f"Channel bereits vorhanden, übersprungen: {cid}")
            continue

        print(f"Neue Channel ID: {cid}")
        channel_videos = get_channel_videos(cid, published_after_analysis, published_before_analysis)
        print(f"Gefundene Videos: {len(channel_videos)}")
        new_videos.extend(channel_videos)
        if not channel_videos:
            new_videos.append({"video_id": f"no_video_found_{cid}",
                                    "channel_id": cid,
                                    "published_at": f"no_video_found_{cid}",
                                    "title": f"no_video_found_{cid}"})
    except Exception as e:
       print(e)
       break

# -----------------------------
# Hauptprogramm - update existing channels
# -----------------------------

# new_videos_added = []
# #channel_ids = ["UCZHpIFMfoJJ_1QxNGLJTzyA"]
# for cid in channel_ids:
#     # Wir überspringen den "processed_channel_ids" Check von früher,
#     # da wir jetzt gezielt NACH neuen Inhalten in bekannten Kanälen suchen.
#
#     last_known = newest_video_per_channel.get(cid)
#     print(f"Prüfe Kanal {cid} auf neue Videos seit {last_known if last_known else 'Anfang'}...")
#
#     found = get_new_channel_videos(
#         cid,
#         published_after_analysis,
#         published_before_analysis,
#         last_known
#     )
#
#     if found:
#         print(f"--> {len(found)} neue Videos gefunden!")
#         new_videos_added.extend(found)
#
# # Zusammenführen und Speichern
# all_videos = videos_total + new_videos_added
# unique_videos = {v["video_id"]: v for v in all_videos}  # Sicherung gegen Dubletten
# final_list = list(unique_videos.values())
#
# with open(videos_total_file, "w", encoding="utf-8") as f:
#     json.dump(final_list, f, ensure_ascii=False, indent=2)
#
# print(f"\nUpdate abgeschlossen. {len(new_videos_added)} neue Videos hinzugefügt.")
# -----------------------------
# Deduplication nach Video-ID
# -----------------------------
all_videos = videos_total + new_videos
unique_videos = {v["video_id"]: v for v in all_videos}
videos_total = list(unique_videos.values())

with open(videos_total_file, "w", encoding = "utf-8") as f:
    json.dump(videos_total, f, ensure_ascii = False, indent = 2)

print("\nVerarbeitung abgeschlossen")
print(f"Gesamtvidoes: {len(videos_total)}")
print(f"Neu hinzugefügte Videos: {len(new_videos)}")

# -----------------------------
# End of Deduplication block
# -----------------------------


# with open(f"json_files/query_list/files_{query}/videos_by_channel_{query}.json", "w", encoding = "utf-8") as f:
#     json.dump(new_videos, f, ensure_ascii = False, indent= 2)

# with open(videos_total_file, "r", encoding = "utf-8") as f:
#     data = json.load(f)

# all_processed_ids = list({v["channel_id"] for v in videos_total})
#
# with open("json_files/all_channel_ids_processed.json", "w", encoding ="utf-8") as f:
#     json.dump(all_processed_ids, f, ensure_ascii = False, indent =2)


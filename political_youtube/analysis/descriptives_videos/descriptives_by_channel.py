import time
import json
import os
from dotenv import load_dotenv
from googleapiclient.discovery import build
import pandas as pd


published_after_analysis = "2022-10-07T00:00:00Z"
published_before_analysis = "2026-01-31T00:00:00Z"


load_dotenv()
api_key = os.getenv("API_KEY")
api_key_c = os.getenv("API_KEY_C")

youtube = build("youtube", "v3", developerKey = api_key_c)

relevant_channels = {
    "Y-Kollektiv": "UCLoWcRy-ZjA-Erh0p_VDLjQ"
}

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

    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            try:
                all_videos = json.load(f)
            except json.JSONDecodeError:
                all_videos = []
    else:
        all_videos = []

    already_requested = {v["video_id"] for v in all_videos}
    video_ids_filtered = [v for v in video_ids if v not in already_requested]
    y = len(video_ids) - len(video_ids_filtered)

    print(f"Total number ideo IDs: {len(video_ids)}"
          f"\nFor {y} video IDs, metadata already exists.")

    print(f"Requesting metadata for {len(video_ids_filtered)} video_files...")

    for batch in chunk_list(video_ids_filtered, 50):
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
                "duration": item["contentDetails"]["duration"],
                "view_count": item["statistics"].get("viewCount"),
                "like_count": item["statistics"].get("likeCount"),
                "comment_count": item["statistics"].get("commentCount"),
            }
            all_videos.append(video_data)

        time.sleep(0.1)
    print(f"Saving metadata file to: {output_path}")
    with open(output_path, "w", encoding = "utf-8") as f:
        json.dump(all_videos, f, indent = 2, ensure_ascii=False)


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

#df = pd.read_json("videos_metadata.json")
df = pd.read_json("../../JSON Files/ident_1803/large_german_channels/video_files/metadata_all_videos_100k_channels_keywords.json")
df = df[df["channel_id"] == "UCQGqiGhMjc_p4lZEhSTb12g"]
print(len(df))
df["comment_ratio"] = df["comment_count"] / df["view_count"] *100
df["like_ratio"] = df["like_count"] / df["view_count"] *100
df["engagement_ratio"] = (df["like_count"] + df["comment_count"]) /df["view_count"] *100
df["duration"] = pd.to_timedelta(df["duration"])
df["duration"] = (df["duration"].dt.total_seconds()) / 60

df_no_shorts = df[df["duration"] > 1]
top_engagement = df_no_shorts.nlargest(5, "engagement_ratio")
top_likes = df_no_shorts.nlargest(5, "like_ratio")
top_comments = df_no_shorts.nlargest(5, "comment_ratio")

print(len(df))
print(len(df_no_shorts))

with pd.option_context("display.max_columns", None):
    print(df_no_shorts.describe(percentiles=[0.25, 0.5, 0.75, 0.9, 0.95]).round(2))
    print(top_engagement)
    print(top_likes)
    print(top_comments)

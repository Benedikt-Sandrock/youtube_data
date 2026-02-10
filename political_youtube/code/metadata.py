from googleapiclient.discovery import build
import time
import pandas as pd
import json
from help_functions import classify_channels_from_json

api_key = "AIzaSyBUg0XIryem2_WtenRUKDA1bwLsiDzMLYE"
api_key_c = "AIzaSyBjtKhLfb-EyaWxc-vCROX6VTWA66j8sHE"

youtube = build("youtube", "v3", developerKey=api_key_c)


def get_channel_metadata(youtube, channel_ids):

    all_data = []
    for batch in chunk_list(channel_ids, 50):
        request = youtube.channels().list(
            part="snippet,statistics",
            id=",".join(batch)
        )
        response = request.execute()

        for item in response.get('items', []):
            data = {
                'Name': item['snippet']['title'],
                'Subscribers': int(item['statistics'].get('subscriberCount', 0)),
                'Views': int(item['statistics'].get('viewCount', 0)),
                'Videos': int(item['statistics'].get('videoCount', 0)),
                'Channel_ID': item['id']
            }
            all_data.append(data)

    return all_data



def get_video_metadata(video_ids):
    all_videos = []

    for batch in chunk_list(video_ids, 50):
        request = youtube.videos().list(
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

    return all_videos


def chunk_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


if __name__ == "__main__":

    # region video metadata from json dict
    # with open("../../JSON Files/videos_keywords_total_3years.json", "r", encoding ="utf-8") as f:
    #     data = json.load(f)
    #
    # video_ids = [v["video_id"] for v in data]
    #
    # all_videos_metadata = get_video_metadata(video_ids)
    #
    # with open("../../JSON Files/keyword_vids/videos_keywords_total_3years_metadata.json", "w", encoding ="utf-8") as f:
    #     json.dump(all_videos_metadata, f, ensure_ascii=False, indent=4)
    # endregion


    # region channel metadata from json list
    with open("../JSON Files/all_channel_ids_discovered.json", "r", encoding ="utf-8") as f:
        data = set(json.load(f))
    with open("../JSON Files/all_channel_ids_metadata.json", "r", encoding ="utf-8") as f:
        metadata = json.load(f)

    existing_channels = {c["Channel_ID"] for c in metadata}
    print(f"Bereits verarbeitete channels: {len(existing_channels)}")
    new_data = data - existing_channels
    new_data = list(new_data)
    print(f"Neue Channels: {len(new_data)}")

    new_metadata = get_channel_metadata(youtube, new_data)
    print(len(new_metadata))

    metadata.extend(new_metadata)
    with open("../JSON Files/all_channel_ids_metadata.json", "w", encoding = "utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)

    # endregion

    with open("../JSON Files/all_channel_ids_metadata.json", "r", encoding = "utf-8") as f:
        data_all = json.load(f)
    print(len(data_all))

    with open("../JSON Files/channel_ids_classified/all_channel_ids_german.json", "r", encoding = "utf-8") as f:
        german_channels = json.load(f)


    data = [c for c in data_all if c["Channel_ID"] in german_channels]

    large_channels = [c for c in data if int(c["Subscribers"]) > 10000]
    print(len(large_channels))

    with open("../JSON Files/large_channels.json", "w", encoding = "utf-8") as f:
        json.dump(large_channels, f, ensure_ascii=False, indent=4)

    # region classify channels from json
    # input_path = "../JSON Files/all_channel_ids_discovered.json"
    # output_german_only = "../JSON Files/channel_ids_classified/all_channel_ids_german.json"
    # output_foreign_only = "../JSON Files/channel_ids_classified/all_channel_ids_foreign.json"
    # output_all_channels = "../JSON Files/channel_ids_classified/all_channel_ids_classified.json"
    #
    # classify_channels_from_json(youtube, input_path, output_german_only, output_foreign_only, output_all_channels)
    # endregion


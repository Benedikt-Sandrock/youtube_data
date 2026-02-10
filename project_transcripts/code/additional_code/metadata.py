from googleapiclient.discovery import build
import time
import pandas as pd
import json

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
    with open("../../JSON Files/channel_metadata.json", "r", encoding ="utf-8") as f:
        data = json.load(f)
    large_channels = [c for c in data if int(c["Subscribers"]) > 10000]
    print(len(large_channels))
    # with open("../../JSON Files/videos_keywords_total_3years.json", "r", encoding ="utf-8") as f:
    #     data = json.load(f)
    #
    # video_ids = [v["video_id"] for v in data]
    #
    # all_videos_metadata = get_video_metadata(video_ids)
    #
    # with open("../../JSON Files/keyword_vids/videos_keywords_total_3years_metadata.json", "w", encoding ="utf-8") as f:
    #     json.dump(all_videos_metadata, f, ensure_ascii=False, indent=4)
    # results = get_channel_metadata(youtube, data)
    #
    # with open("../JSON Files/channel_metadata_1year.json", "w", encoding = "utf-8")as f:
    #     json.dump(results, f, ensure_ascii=False, indent = 2)
    # file_path = "../Transcript files/youtube_transkripte_2.csv"
    # df = pd.read_csv(file_path)
    # video_ids = df["video_id"].head(50).tolist()
    # print(len(video_ids))
    #
    # metadata = get_video_metadata(video_ids)
    # print(f"{len(metadata)} Videos geladen")
    #
    # with open("../JSON Files/metadata.json", "w", encoding ="utf-8") as f:
    #     json.dump(metadata, f, ensure_ascii = False, indent = 2)



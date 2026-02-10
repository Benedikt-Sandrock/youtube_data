from googleapiclient.discovery import build

api_key = "AIzaSyBUg0XIryem2_WtenRUKDA1bwLsiDzMLYE"

youtube = build('youtube', 'v3', developerKey=api_key)

published_after = "2022-10-07T00:00:00Z"
published_before = "2023-10-07T00:00:00Z"
query = "palästina"

results = []
next_page_token = None

while True:
    request = youtube.search().list(
        part="id,snippet",
        q="query",
        type="video",
        publishedAfter=published_after,
        publishedBefore=published_before,
        order="date",
        maxResults=50,
        pageToken=next_page_token
    )

    response = request.execute()
    results.extend(response.get("items", []))
    next_page_token = response.get("nextPageToken")
    if not next_page_token:
        break

# Extraktion der Video-IDs und Channel-IDs
videos = [
    {
        "video_id": item["id"]["videoId"],
        "channel_id": item["snippet"]["channelId"],
        "published_at": item["snippet"]["publishedAt"],
        "title": item["snippet"]["title"]
    }
    for item in results
]

print(f"Gefundene Videos: {len(videos)}")
print(videos)

channel_ids = {video["channel_id"] for video in videos}
print(f"Einzigartige Kanäle: {len(channel_ids)}")
print(channel_ids)

channel_ids = ["UCBA2L-XIgGYVn_t_8B0VMMg"]

all_channel_videos = []

for cid in channel_ids:
    next_page = None
    while True:
        request = youtube.search().list(
            part="id,snippet",
            channelId=cid,
            type="video",
            publishedAfter=published_after,
            publishedBefore=published_before,
            order="date",
            maxResults=50,
            pageToken=next_page
        )
        response = request.execute()
        all_channel_videos.extend([
            {
                "video_id": item["id"]["videoId"],
                "channel_id": item["snippet"]["channelId"],
                "published_at": item["snippet"]["publishedAt"],
                "title": item["snippet"]["title"]
            }
            for item in response.get("items", [])
        ])
        next_page = response.get("nextPageToken")
        if not next_page:
            break

print(f"Gesamtanzahl Videos von allen Channels: {len(all_channel_videos)}")

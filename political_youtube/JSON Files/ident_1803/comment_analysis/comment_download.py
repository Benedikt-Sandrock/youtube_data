import os
import pandas as pd
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()
api_key = os.getenv("API_KEY")
api_key_c = os.getenv("API_KEY_C")

df = pd.read_json("../large_german_channels/video_files/metadata_all_videos_100k_channels_keywords.json")

df = df[df["comment_count"].notna() & (df["comment_count"] != 0)]
print(len(df))
print(df["comment_count"].sum())

list_of_ids = df["video_id"].tolist()
print(len(list_of_ids))

youtube = build("youtube", "v3", developerKey=api_key)

output_file = "comment_data.csv"
checkpoint_file = "processed_ids.txt"


def get_comments_for_videos(id_list):
    print(f"Total number of IDs: {len(id_list)}")
    if os.path.exists(output_file):
        processed_df = pd.read_csv(output_file, usecols=["video_id"])
        processed_ids = set(processed_df["video_id"].unique())
        print(f"Already processed IDs: {len(processed_ids)}")
    else:
        processed_ids = {}
        print("No processed IDs")

    for v_id in id_list:
        if v_id in processed_ids:
            continue

        video_comments = []

        try:
            request = youtube.commentThreads().list(
                part = "snippet",
                videoId = v_id,
                maxResults = 100,
                textFormat = "plainText"
            )

            while request:
                response = request.execute()
                for item in response["items"]:
                    comment = item["snippet"]["topLevelComment"]["snippet"]
                    video_comments.append({
                        "video_id": v_id,
                        "author": comment["authorDisplayName"],
                        "text": comment["textDisplay"],
                        "date": comment["publishedAt"],
                        "likes": comment["likeCount"]
                    })

                if "nextPageToken" in response:
                    request = youtube.commentThreads().list_next(request, response)
                else:
                    request = None

            if video_comments:
                df_temp = pd.DataFrame(video_comments)
                df_temp.to_csv(output_file, mode = "a", index = False, header=not os.path.exists(output_file))

        except HttpError as e:
            print(f"Error at id {v_id}: {e}")
            continue

#get_comments_for_videos(list_of_ids)
df = pd.read_csv(output_file)
print(len(df))
import os
import pandas as pd
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()
api_key = os.getenv("API_KEY")
api_key_c = os.getenv("API_KEY_C")

df = pd.read_json(
    "../../JSON Files/ident_1803/large_german_channels/video_files/metadata_all_videos.jsonl", lines = True)

df_control = pd.read_json(
    "../../JSON Files/ident_1803/large_german_channels/video_files/all_videos_50k_channels_keywords.json")


print(f"Number of keyword videos: {len(df_control)}")

keyword_ids = df_control["video_id"].tolist()
df = df[df["video_id"].isin(keyword_ids)]
print(len(df))
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
            if e.resp.status == 403:
                if not "disabled" in str(e):
                    break
            print(f"Error at id {v_id}: {e}")
            continue


def get_everything_from_videos(video_ids, output_file, api_keys):
    key_index = 0
    youtube = build("youtube", "v3", developerKey=api_keys[key_index])
    checkpoint_file = "finished_videos.txt"

    finished_videos = set()
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, "r") as f:
            finished_videos = set(line.strip() for line in f)

    # Use a while loop with an index so we can "retry" the same video after switching keys
    i = 0
    while i < len(video_ids):
        v_id = video_ids[i]

        if v_id in finished_videos:
            i += 1
            continue

        print(f"Processing Video {i + 1}/{len(video_ids)}: {v_id}")

        try:
            request = youtube.commentThreads().list(
                part="snippet",
                videoId=v_id,
                maxResults=100,
                textFormat="plainText"
            )

            while request:
                response = request.execute()
                all_data_this_page = []

                for item in response["items"]:
                    # Capture Top-Level
                    top_snippet = item["snippet"]["topLevelComment"]["snippet"]
                    parent_id = item["snippet"]["topLevelComment"]["id"]

                    all_data_this_page.append({
                        "video_id": v_id,
                        "comment_id": parent_id,
                        "parent_id": "None",
                        "type": "top_level",
                        "text": top_snippet["textDisplay"],
                        "author": top_snippet["authorDisplayName"],
                        "date": top_snippet["publishedAt"]
                    })

                    # Capture Replies
                    if item["snippet"]["totalReplyCount"] > 0:
                        reply_request = youtube.comments().list(
                            part="snippet",
                            parentId=parent_id,
                            maxResults=100,
                            textFormat="plainText"  # Keep formatting consistent
                        )
                        while reply_request:
                            rep_res = reply_request.execute()
                            for rep_item in rep_res["items"]:
                                rep_snippet = rep_item["snippet"]
                                all_data_this_page.append({
                                    "video_id": v_id,
                                    "comment_id": rep_item["id"],
                                    "parent_id": parent_id,
                                    "type": "reply",
                                    "text": rep_snippet["textDisplay"],
                                    "author": rep_snippet["authorDisplayName"],
                                    "date": rep_snippet["publishedAt"]
                                })
                            reply_request = youtube.comments().list_next(reply_request, rep_res)

                # Save current page
                if all_data_this_page:
                    pd.DataFrame(all_data_this_page).to_csv(
                        output_file, mode="a", index=False,
                        header=not os.path.exists(output_file),
                        encoding="utf-8-sig"
                    )

                request = youtube.commentThreads().list_next(request, response)

            # Success! Mark video as finished and move to next
            with open(checkpoint_file, "a") as f:
                f.write(f"{v_id}\n")
            finished_videos.add(v_id)
            i += 1

        except HttpError as e:
            if e.resp.status == 403:
                print(f"Quota Hit on key {key_index + 1}")
                key_index += 1
                if key_index < len(api_keys):
                    youtube = build("youtube", "v3", developerKey=api_keys[key_index])
                    print(f"Switched to key {key_index + 1}. Retrying current video...")
                    # Note: We do NOT increment 'i' here, so it retries the SAME video
                    continue
                else:
                    print("All API keys exhausted. Exiting.")
                    return

            # Handle disabled comments or private videos
            print(f"Skipping video {v_id} (Comments might be disabled): {e}")
            i += 1
            continue

#get_comments_for_videos(list_of_ids)
get_everything_from_videos(list_of_ids, "complete_dataset.csv", [api_key, api_key_c])
#df = pd.read_csv("complete_dataset.csv")
#print(len(df))

df = pd.read_csv("comment_data.csv")
print(len(df))
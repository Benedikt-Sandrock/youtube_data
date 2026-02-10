import pandas as pd
import json
import os

def remove_blocked_videos(file_path):
    df = pd.read_csv(file_path)

    length = len(df)
    df = df[~df["status"].str.contains("blocking", na = False)]
    length2 = len(df)
    removed = length - length2

    print(removed)
    print(len(df))
    print(df.shape)
    df.to_csv(file_path, index = False)

def total_number_channel_ids(videos_total_file, query_list):
    if os.path.exists(videos_total_file):
        with open(videos_total_file, "r", encoding="utf-8") as f:
            videos_total = json.load(f)

    else:
        videos_total = []

    processed_channel_ids = {v["channel_id"] for v in videos_total}
    print(f"Bereits verarbeitete Channels: {len(processed_channel_ids)}")

    for query in query_list:
        target_file = f"../Code/json_files/query_list/files_{query}/channel_ids_{query}.json"

        with open(target_file, "r") as f:
            collected_channel_ids = set(json.load(f))
        new_channel_ids = collected_channel_ids - processed_channel_ids

        print(
            f"Query '{query}': "
            f"{len(new_channel_ids)} neue Channels "
            f"(gesamt gefunden: {len(collected_channel_ids)})"
        )

        processed_channel_ids.update(new_channel_ids)


if __name__ == "__main__":
    file_path = f"../Transcript files/youtube_transkripte_2.csv"
    videos_total_file = f"../Code/json_files/videos_by_channel_total.json"

    query_list = ["Nahostkonflikt", "Gaza-Krieg", "Israel Palästina Konflikt", "Palästina Israel Konflikt",
                  "Konflikt Israel Palästina", "Konflikt Palästina Israel"]

    #total_number_channel_ids(videos_total_file, query_list)

    df = pd.read_csv(file_path)
    print(len(df))
    print(df.loc[df["video_id"] == "d5X371Q92yE", "status"])


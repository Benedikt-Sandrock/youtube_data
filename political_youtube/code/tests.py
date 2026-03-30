import pandas as pd
import json
import random
import os

def collect_downloaded_transcripts(list_of_files: list[str], list_of_ids: list[str]):
    """
    Takes a list of files and a list of IDs as Input. Searches existing transcript files for transcripts
    to these IDs. Returns a df with video ID, transcript, and status for all IDs is found in another file.
    """
    print("Collecting already downloaded transcripts...")
    id_to_file = {}

    for file in list_of_files:
        if not os.path.exists(file):
            print(f"File not found: {file}")
            continue
        df = pd.read_csv(file, usecols = ["video_id"])
        for video_id in df["video_id"].dropna().unique():
            if str(video_id) not in id_to_file:
                id_to_file[str(video_id)] = file

    print(f"Found {len(id_to_file)} already downloaded transcripts in existing files.")

    file_to_ids = {}
    for video_id in list_of_ids:
        file = id_to_file.get(str(video_id))
        if file is None:
            continue
        file_to_ids.setdefault(file, set()).add(video_id)

    results = []
    for file, ids in file_to_ids.items():
        df = pd.read_csv(file, usecols = ["video_id", "transcript", "status"])
        matched = df[df["video_id"].isin(ids)].copy()
        results.append(matched)

    if not results:
        return pd.DataFrame(columns = ["video_id", "transcript", "status"])

    return pd.concat(results, ignore_index = True)
# df = pd.read_csv("../Transcript files/political_yt_transcripts.csv")
#
# df_filtered = df.loc[df["status"].str.contains("retries")]
# print(len(df_filtered))
# print(df_filtered.head(12))

with open("../JSON Files/ident_1803/large_german_channels/video_files/all_videos_100k_channels_keywords.json", "r", encoding = "utf-8") as f:
    data = json.load(f)

video_list = [c["video_id"] for c in data]
video_list = random.sample(video_list, 100)
print(video_list)

downloaded_transcripts = collect_downloaded_transcripts(transcript_files, keyword_vids)
downloaded_transcripts.to_csv(export_file, index = False)
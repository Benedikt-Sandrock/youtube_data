"""
Generates a sample of random transcripts that can be used for manual grading.
"""

import pandas as pd
import json
import random
import os
from src.youtube_code.config.paths import EXPLORATION, SAMPLES, TRANSCRIPTS

seed_number = 42
sample_path = SAMPLES / "sampled_per_channel.json"
export_file = EXPLORATION / "training_data" / f"training_data_sample_vids_{seed_number}.csv"
transcript_files = TRANSCRIPTS / "all_transcripts.csv"


def collect_downloaded_transcripts(list_of_files: list[str], list_of_ids: list[str]):
    """
    Takes a list of files and a list of IDs as Input. Searches existing transcript files for transcripts
    to these IDs. Returns a df with video ID, transcript, and status for all IDs is found in another file.
    """
    if not isinstance(list_of_files, list):
        list_of_files = [list_of_files]
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

extreme_channels = ["UCT0wo1uc6G3UTuM_MiacA9g", "UCXJBRgiZRZvfilIGQ4wN5CQ", "UCB37CFICVTUlewYdbMSChIA",
                    "UCcoQ3WG2J_Xjwwyt-sJqh-w", "UCQGqiGhMjc_p4lZEhSTb12g", "UC_dZp8bZipnjntBGLVHm6rw",
                    "UCiTKi7Ahf3E2yMGpmIxSvgw", "UCR_iFmLcHBFxc3x3CA71xvw", "UCUYQypt91KuQPHRgr1k8wlg",
                    "UCSiFC1DCXr3p1YDzyu9rogA", "UCPH3ZPeqWqRVZ_ef4vOZgSw", "UCv1WDP5EiipMQ__C4Cg6aow",
                    "UCA95T5bSGxNOAODBdbR2rYQ", "UCqLv2nTsMB_FXtQRFNXjWhA", "UCNNEMxGKV1LsKZRt4vaIbvw",
                    "UCK4LDHLxBqiAtcwCm4z7DRg", "UC1cQzKmbx9x0KipvoCt4NJg", "UCjhkuC_Pi85wGjnB0I1ydxw",
                    "UCw-SjGVT0HK7czJkLgdv3Fw", "UCUuab1dctZzN5ZmRmQnTzkg", "UChkELlk5GBaUCVx8-94IK_Q",
                    "UCbanHTRuGv2Fi7flpO735yw", "UCgvFsn6bRKqND1cW3HpzDrA","UCAsMARoXqla-WJpclxZjABg",
                    "UC1RJJZSO2GYBrPQuiLUp1dA", "UCK78LteBgoyE1XlSwBZWd0A", "UCICWTMc7Jni_u5ORVXBOnLQ"]
with open(sample_path, "r", encoding ="utf-8") as f:
    data = json.load(f)

random.seed(seed_number)
# channel_vids = defaultdict(list)
# for v in data:
#     c_id = v["channel_id"]
#     v_id = v["video_id"]
#     channel_vids[c_id].append(v_id)
#
# print(channel_vids)
#
# video_list = []
# for c_id, video_ids in channel_vids.items():
#     video = random.choice(video_ids)
#     video_list.append(video)
#
# print(video_list)
video_ids = [c["video_id"] for c in data ]
video_list = random.sample(video_ids,50)
print(video_list)

downloaded_transcripts = collect_downloaded_transcripts(transcript_files, video_list)
print(len(downloaded_transcripts))

downloaded_transcripts = downloaded_transcripts[downloaded_transcripts["status"] == "OK"]
print(len(downloaded_transcripts))
downloaded_transcripts.to_csv(export_file, index = False)
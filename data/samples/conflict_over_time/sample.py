from youtube_code.config import TRANSCRIPTS, RAW
from src.youtube_code.utils.io import load_json
import json
import pandas as pd

def merge_channel_name(input_path, channel_path, output_path):
    data = load_json(input_path)
    meta = load_json(channel_path)

    channel_mapping = {
        video["video_id"]: video.get("channel_title") for video in meta if "video_id" in video
    }
    for video in data:
        video_id = video.get("video_id")
        video["channel_title"] = channel_mapping.get(video_id)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

#merge_channel_name("sampled_50k_channels.json", "all_videos_50k_channels_name.json", "sampled_50k_channels.json")

data = load_json("all_videos_50k_channels.json")
print(len(data))
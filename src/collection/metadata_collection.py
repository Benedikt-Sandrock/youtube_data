"""
Uses the file with all videos ("video_total.json") to collect (new) metadata for channels and videos
as well as classifying the language of channels.
"""

from googleapiclient.discovery import build
from src.utils.io import get_channel_metadata, get_video_metadata, load_json, save_json
from src.config.paths import RAW
from src.config.settings import API_KEY, API_KEY_C

videos_input_path = RAW / "videos_total.json"
metadata_path = RAW / "channel_metadata_total.json"


YOUTUBE = build("youtube", "v3", developerKey=API_KEY)

data = load_json(videos_input_path)

video_ids = {v["video_id"] for v in data}
channel_ids = {v["channel_id"] for v in data}

get_channel_metadata(channel_ids, metadata_path, YOUTUBE)

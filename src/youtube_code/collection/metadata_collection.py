"""
Uses the file with all videos ("video_total.json") to collect (new) metadata for channels and videos
"""

from googleapiclient.discovery import build
from youtube_code.utils import get_channel_metadata, get_video_metadata, load_json
from youtube_code.config import RAW, SAMPLES, API_KEY_C, API_KEY

api_keys = [API_KEY_C, API_KEY]

# ─────────────────────────────────────────────
# CONFIGURATION AND PATHS
# ─────────────────────────────────────────────
channel_metadata = False
video_metadata = True
DETAILED = True

VIDEOS_INPUT_PATH = SAMPLES / "russia" / "videos_wo_shorts_russia_ukraine.json"
CHANNEL_METADATA_PATH = RAW / "channel_metadata_total.json"

if DETAILED:
    VIDEOS_METADATA_PATH = RAW / "video_metadata_detailed_total.jsonl"
else:
    VIDEOS_METADATA_PATH = RAW / "video_metadata_total.jsonl"


YOUTUBE = build("youtube", "v3", developerKey=api_keys[1])

# ─────────────────────────────────────────────

data = load_json(VIDEOS_INPUT_PATH)

video_ids = [v["video_id"] for v in data]
channel_ids = {v["channel_id"] for v in data}


if channel_metadata:
    get_channel_metadata(channel_ids, CHANNEL_METADATA_PATH, YOUTUBE)

if video_metadata:
    get_video_metadata(video_ids, VIDEOS_METADATA_PATH, YOUTUBE, DETAILED)
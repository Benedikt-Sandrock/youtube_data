"""
Uses the file with all videos ("video_total.json") to collect (new) metadata for channels and videos.
Beide Fetch-Funktionen lesen bereits vorhandene IDs aus der zentralen
video_registry (data/store/video_registry.sqlite) und schreiben neu
abgefragte Metadaten auch nur noch dorthin - keine separaten JSON/JSONL-
Dateien mehr.
"""

import pandas as pd
from googleapiclient.discovery import build

from youtube_code.utils import get_channel_metadata, get_video_metadata, load_json
from youtube_code.config import RAW, SAMPLES, API_KEY_C, API_KEY, CHANNEL_LISTS, OUTPUTS
from youtube_code.store import video_registry

api_keys = [API_KEY_C, API_KEY]

# ─────────────────────────────────────────────
# CONFIGURATION AND PATHS
# ─────────────────────────────────────────────
channel_metadata = True
video_metadata = False
DETAILED = False

VIDEOS_INPUT_PATH = SAMPLES / "russia_longitudinal_v1" / "identification_videos_missing_metadata.json"
# VIDEOS_INPUT_PATH = RAW / "sample_50k_channels_russia_ukraine.json"


YOUTUBE = build("youtube", "v3", developerKey=api_keys[0])

# ─────────────────────────────────────────────
if channel_metadata:
    channel_ids = load_json(SAMPLES / "russia_longitudinal_v1" / "eligible_channels_current.json")

    get_channel_metadata(channel_ids, YOUTUBE)


if video_metadata:
    if VIDEOS_INPUT_PATH.suffix.lower() == ".json":
        data = load_json(VIDEOS_INPUT_PATH)
        video_ids = [v["video_id"] for v in data]
    else:
        df = pd.read_csv(VIDEOS_INPUT_PATH)
        video_ids = df["video_id"].to_list()
        # channel_ids = df["channel_id"].to_list()
        # channel_ids = set(channel_ids)
        # channel_ids = list(channel_ids)
    get_video_metadata(video_ids, YOUTUBE, DETAILED)

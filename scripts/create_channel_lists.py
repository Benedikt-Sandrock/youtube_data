"""
First step: Creates a list (saved as json) of all unique channel ids within a directory for a given filename.
Second step: Gets all videos for channels of a given list and saves them in "SAMPLES"
"""

from src.config.paths import CHANNEL_LISTS, RAW, SAMPLES
from src.utils.io import collect_unique_channel_ids, save_json, load_json


# ─────────────────────────────────────────────
# CONFIGURATION AND PATHS
# ─────────────────────────────────────────────
FIRST_STEP = False
SECOND_STEP = False
SAMPLE_NAME = "all_videos_50k_channels.json"
DIR_NAME = "conflict_over_time"


DIRECTORY = CHANNEL_LISTS / f"{DIR_NAME}"
FILENAME = "all_channel_ids_discovered.json"
METADATA = RAW / "channel_metadata_total.json"
CHANNEL_LIST = DIRECTORY / "channel_list.json"
ALL_VIDEOS_FILE = RAW / "videos_total.json"
SAMPLE_FILE = SAMPLES / f"{SAMPLE_NAME}"

# ─────────────────────────────────────────────
# MAIN CODE
# ─────────────────────────────────────────────
if FIRST_STEP:
    print(f"\nCreate a list of all unique IDs in '{DIRECTORY}' for files '{FILENAME}'")
    data = collect_unique_channel_ids(DIRECTORY, FILENAME)

    metadata = load_json(METADATA)
    metadata = [c["channel_id"] for c in metadata if c["subscribers"] >= 50000]


    data = [c for c in data if c in metadata]

    save_json(CHANNEL_LIST, data)


if SECOND_STEP:
    print(f"\nCreate a sample for all videos from channels on '{CHANNEL_LIST}'")
    channel_list = load_json(CHANNEL_LIST)
    video_data = load_json(ALL_VIDEOS_FILE)

    sample_data = [v for v in video_data if v["channel_id"] in channel_list]

    save_json(SAMPLE_FILE, sample_data)

    channel_length = [c["channel_id"] for c in sample_data]

    print(f"Number of videos in sample: {len(sample_data)}")
    print(f"Number of unique channels in sample: {len(channel_length)}")


data = load_json(SAMPLES / "sampled_50k_channels.json")
print(len(data))

data = load_json(SAMPLES / "sampled_per_channel.json")
print(len(data))
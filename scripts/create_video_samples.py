"""
sample_videos.py
----------------
Draws a weighted random sample for a JSON file.

Arguments:
    --input             Path to input JSON file
    --output            Path to output JSON file
    --time_deltas       Values for time_delta (Space-separated)
    --max_per_group     Max. number of videos per channel (channel_id × time_delta)-combination
    --prioritize_politics  If used: politics_classification=1 is prioritized
    --seed              Random seed
"""

import json
import random
import pandas as pd
from datetime import datetime, timezone
from collections import defaultdict

from youtube_code.config import SAMPLES, RAW, KEYWORDS, CHANNEL_LISTS, TRANSCRIPTS
from youtube_code.utils import load_set

# ─────────────────────────────────────────────
# CONFIGURATION AND PATHS
# ─────────────────────────────────────────────
### CENTRAL CONFIGURATION ###
sample_name = "combined"   # ["conflict_over_time", "party_identification"]

all_videos_file_name = "all_videos_50k_channels.json"
output_file_name_sampled = "sampled_50k_channels.json"
output_file_name_keyword = "keyword_videos_50k_channels.json"


REFERENCE_DATE = datetime(2023, 10, 7, tzinfo=timezone.utc)
FILE_ALL_VIDEOS = SAMPLES / f"{sample_name}" / all_videos_file_name
METADATA_PATH = RAW / "video_metadata_total.jsonl"
OUTPUT_FILE = SAMPLES / sample_name / output_file_name_sampled
TIME_DELTAS = [-1, -2, -3,]
MAX_PER_GROUP = 20
PRIORITIZE_POLITICS = False
SEED = 42

CHANNEL_LIST = CHANNEL_LISTS / f"{sample_name}" / "channel_list.json"
OUTPUT_KEYWORD_VIDEOS = SAMPLES / f"{sample_name}" / output_file_name_keyword

COT_SAMPLE_VIDEOS = SAMPLES / "conflict_over_time" / "sampled_50k_channels.json"
TRANSCRIPTS_PATH = TRANSCRIPTS / "all_transcripts.csv"


def get_all_videos(channel_list_path, output_path, metadata_path):
    print("Creating file with all videos uploaded from channels on the list.")
    print(f"Channels: {channel_list_path}")
    channel_set = load_set(channel_list_path)

    KEYS_TO_KEEP = ["video_id", "title", "channel_id", "channel_title", "published_at"]

    with open(metadata_path, "r", encoding = "utf-8") as infile, \
        open(output_path, "w", encoding = "utf-8") as outfile:

        outfile.write("[\n")
        is_first_item = True
        counter = 0

        for line in infile:
            if not line.strip():
                continue

            try:
                data = json.loads(line)
                if data.get("channel_id") in channel_set:
                    filtered_data = {key: data[key] for key in KEYS_TO_KEEP}
                    if not is_first_item:
                        outfile.write(",\n")
                    else:
                        is_first_item = False

                    outfile.write("  " + json.dumps(filtered_data, ensure_ascii = False))
                    counter += 1
            except json.JSONDecodeError:
                print(f"Error when reading a line.")
        outfile.write("\n]")
    print(f"{counter} videos added to list.")


def compute_time_delta(published_at: str) -> int:
    """
    Calculates the distance between published_at and Oct. 7th 2023 in months.

    Logic:
      - Complete months are counted starting at the 7th of each month.
      - Example: 07.10.2023–06.11.2023 → 0
                  07.11.2023–06.12.2023 → 1
                  07.09.2023–06.10.2023 → -1
    """
    dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))

    # Difference in complete months: (year-delta * 12) + month-delta
    month_diff = (dt.year - REFERENCE_DATE.year) * 12 + (dt.month - REFERENCE_DATE.month)

    # If the date hasn't reached the 7th of the target month
    # it belongs to the previous period → subtract one month.
    if dt.day < REFERENCE_DATE.day:
        month_diff -= 1

    return month_diff


def load_data(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Input-JSON must be a list of dicts.")
    return data


def enrich_with_time_delta(data: list[dict]) -> list[dict]:
    """Adds calculated time_delta-variable to each entry."""
    for entry in data:
        entry["time_delta"] = compute_time_delta(entry["published_at"])
    return data


def filter_by_keywords(data: list[dict], keywords: list[str]) -> list[dict]:
    """
    Removes videos whose title contains any of the given keywords.
    Matching is case-insensitive, i.e. "Israel" and "israel" are treated the same.
    If a video has no title, it is kept.

    Args:
        data:     List of video dicts.
        keywords: List of keywords to exclude.

    Returns:
        Filtered list without matching videos.
    """
    if not keywords:
        return data
    print(f"Keywords: {keywords}")
    # Convert all keywords to lowercase once — so we don't repeat this for every video.
    keywords_lower = [kw.lower() for kw in keywords]

    keyword_videos = []
    filtered = []
    for video in data:
        title = video.get("title", "").lower()
        if any(kw in title for kw in keywords_lower):
            keyword_videos.append(video)
        else:
            filtered.append(video)

    print(f"{len(keyword_videos)} keyword videos identified."
          f"\nSaving to: {OUTPUT_KEYWORD_VIDEOS}")

    with open(OUTPUT_KEYWORD_VIDEOS, "w", encoding = "utf-8") as f:
        json.dump(keyword_videos, f, ensure_ascii = False, indent = 2)

    return filtered


def parse_iso_duration_greater_than_1m(duration_str: str) -> bool:
    """
    Checks whether an ISO-8601 duration is greater than one minute.
    """

    if "H" in duration_str:
        return True
    if "M" not in duration_str:
        return False

    try:
        minutes_part = duration_str.split("M")[0]
        minutes = int(minutes_part.replace("PT", ""))

        if minutes == 1:
            seconds_part = duration_str.split("M")[1]
            return len(seconds_part) > 1 and "S" in seconds_part

        return minutes > 1
    except ValueError:
        return False


def filter_by_length(data: list[dict], metadata_path):
    """
    Reads metadata file and removes videos with a duration below one minute from data.

    Args:
        data:           List of video dicts.
        metadata_path:  Path to metadata file.

    Returns:
        Filtered list without videos below one minute.
    """
    valid_video_ids = set()

    with open(metadata_path, "r", encoding = "utf-8") as f:
        for line in f:
            meta = json.loads(line)
            duration_str = meta.get("duration")
            if duration_str and parse_iso_duration_greater_than_1m(duration_str):
                valid_video_ids.add(meta["video_id"])
    return [video for video in data if video.get("video_id") in valid_video_ids]


def load_priority_video_ids(csv_path: str | None) -> set[str]:
    """Reads a CSV file that contains (among others) a 'video_id' column
    and returns the set of all video IDs found in it.

    These video IDs are treated as mandatory inclusions: if a video with
    one of these IDs shows up in the new data, it must end up in the final
    sample (still subject to the max_per_group cap, see sample_videos()).
    """
    priority_ids: set[str] = set()

    if not csv_path:
        return priority_ids

    try:
        df = pd.read_csv(csv_path, usecols = ["video_id"], dtype={"video_id": str})
        return set(df["video_id"].dropna())

    except Exception as e:
        print(f"Note: Could not load priority CSV ({e}). Continuing without it.")

    return priority_ids


def sample_videos(
    data: list[dict],
    time_deltas: list[int],
    max_per_group: int,
    prioritize_politics: bool,
    existing_videos_path: str,
    priority_ids_csv_path: str | None = None,
    seed: int | None = None,
) -> list[dict]:
    """Draws a sample using the following logic:

    1. Loads existing videos and identifies all channels present in that file.
    2. For these existing channels, takes EXACTLY the videos from the file
       (filtered by time_delta). These channels are fully excluded from any
       further sampling below.
    3. Loads a list of "priority" video IDs from a CSV file
       (priority_ids_csv_path). Any video from `data` whose video_id is in
       that list is forced into the sample for its (channel_id, time_delta)
       group, as long as the channel is not already covered by step 2.
    4. For all other channels, the remaining slots in each
       (channel_id, time_delta) group are filled using the standard sampling
       logic (with optional politics prioritization).

    The max_per_group limit is ALWAYS strictly enforced per
    (channel_id, time_delta) group - this includes priority videos from the
    CSV. If more priority videos exist for a group than max_per_group
    allows, only max_per_group of them (randomly chosen) are kept.
    """
    rng = random.Random(seed)
    sample: list[dict] = []

    # --- STEP 1: LOAD EXISTING VIDEOS & IDENTIFY CHANNELS ---
    existing_channels = set()
    existing_videos_to_keep = []

    if existing_videos_path:
        try:
            with open(existing_videos_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)

            for video in existing_data:
                channel_id = video.get("channel_id")
                if channel_id:
                    # Remember which channels need to be blocked from new sampling
                    existing_channels.add(channel_id)

                    # Only keep videos that also fall into the desired time window
                    if video.get("time_delta") in time_deltas:
                        existing_videos_to_keep.append(video)

        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(
                f"Note: Could not load file ({e}). Running normal sampling for all channels."
            )

    # Carry over the videos of existing channels unfiltered into the final sample
    sample.extend(existing_videos_to_keep)

    # --- STEP 2: LOAD PRIORITY VIDEO IDS FROM CSV ---
    priority_video_ids = load_priority_video_ids(priority_ids_csv_path)

    # --- STEP 3: FILTER NEW DATA (ONLY FOR CHANNELS NOT ALREADY COVERED) ---
    # Only take data that falls into the time window AND whose channel was
    # NOT already part of the existing videos (step 1)
    filtered_new_data = [
        v
        for v in data
        if v["time_delta"] in time_deltas
        and v["channel_id"] not in existing_channels
    ]

    # --- STEP 4: GROUP THE NEW DATA ---
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for video in filtered_new_data:
        key = (video["channel_id"], video["time_delta"])
        groups[key].append(video)

    # --- STEP 5: NORMAL SAMPLING FOR THE REMAINING CHANNELS ---
    for key, videos in groups.items():
        # Split the group into priority videos (must be included if possible)
        # and the rest of the candidates
        priority_videos = [
            v for v in videos if v.get("video_id") in priority_video_ids
        ]
        other_videos = [
            v for v in videos if v.get("video_id") not in priority_video_ids
        ]

        rng.shuffle(priority_videos)
        # Even priority videos must respect the max_per_group cap
        selected = priority_videos[:max_per_group]
        remaining_slots = max_per_group - len(selected)

        if remaining_slots > 0:
            if prioritize_politics:
                politics_1 = [
                    v for v in other_videos if v.get("politics_classification") == 1
                ]
                politics_other = [
                    v for v in other_videos if v.get("politics_classification") != 1
                ]

                rng.shuffle(politics_1)
                rng.shuffle(politics_other)

                selected.extend(politics_1[:remaining_slots])
                remaining_slots = max_per_group - len(selected)
                if remaining_slots > 0:
                    selected.extend(politics_other[:remaining_slots])
            else:
                shuffled = other_videos[:]
                rng.shuffle(shuffled)
                selected.extend(shuffled[:remaining_slots])

        sample.extend(selected)

    return sample


def get_random_sample(input_file, output_file, exclude_keywords, time_deltas, max_per_group, prioritize_politics = False, seed = 42):
    # Loading and adding time delta
    print(f"Loading data from: {input_file}")
    data = load_data(input_file)
    data = enrich_with_time_delta(data)
    print(f"  → {len(data)} videos loaded.")

    # Excluding videos with duration < 1 minute
    before = len(data)
    data = filter_by_length(data, METADATA_PATH)
    print(f"  → {before - len(data)} videos removed by length filter.")
    print(f"  → {len(data)} videos remaining.")

    # Excluding keyword videos
    before = len(data)
    data = filter_by_keywords(data, exclude_keywords)
    print(f"  → {before - len(data)} videos removed by keyword filter.")
    print(f"  → {len(data)} videos remaining.")

    # Sampling
    sample = sample_videos(
        data=data,
        time_deltas=time_deltas,
        max_per_group=max_per_group,
        existing_videos_path=COT_SAMPLE_VIDEOS,
        priority_ids_csv_path= TRANSCRIPTS_PATH,
        prioritize_politics=prioritize_politics,
        seed=seed,
    )

    # Output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)

    # Summary
    print(f"\nSample saved under: {output_file}")
    print(f"  → {len(sample)} videos in sample.")

    # Breakdown by time delta
    td_counts: dict[int, int] = defaultdict(int)
    for v in sample:
        td_counts[v["time_delta"]] += 1
    print("\nVideos per time_delta:")
    for td in sorted(td_counts):
        print(f"  time_delta={td:+d}: {td_counts[td]} videos")


if __name__ == "__main__":
    #get_all_videos(CHANNEL_LIST, FILE_ALL_VIDEOS, METADATA_PATH)

    get_random_sample(FILE_ALL_VIDEOS, OUTPUT_FILE, KEYWORDS, TIME_DELTAS, MAX_PER_GROUP, PRIORITIZE_POLITICS, SEED)
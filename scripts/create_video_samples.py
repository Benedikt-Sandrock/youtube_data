"""
sample_videos.py
----------------
Draws e weighted random sample for a JSON file.

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
from datetime import datetime, timezone
from collections import defaultdict
from src.config.paths import SAMPLES
from src.config.settings import KEYWORDS


# ─────────────────────────────────────────────
# CONFIGURATION AND PATHS
# ─────────────────────────────────────────────
input_file_name = "all_videos_50k_channels.json"
output_file_name = "sampled_50k_channels.json"

REFERENCE_DATE = datetime(2023, 10, 7, tzinfo=timezone.utc)
INPUT_FILE = SAMPLES / input_file_name
OUTPUT_FILE = SAMPLES / output_file_name
TIME_DELTAS = [-1, -2, -3,]
MAX_PER_GROUP = 20
PRIORITIZE_POLITICS = False
SEED = 42



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

    filtered = []
    for video in data:
        title = video.get("title", "").lower()
        if not any(kw in title for kw in keywords_lower):
            filtered.append(video)

    return filtered


def sample_videos(data: list[dict], time_deltas: list[int], max_per_group: int,
    prioritize_politics: bool, seed: int | None = None,) -> list[dict]:
    """
    Draws a sample using the following logic:
      1. Filtering for given time_delta-values.
      2. Grouping by (channel_id, time_delta).
      3. Per group: Draw max. max_per_group videos.
         - If prioritize_politics=True: first, all politics=1 in sample,
           then fill with politics=0 until limit is hit.
         - Within each subset is randomly mixed.
    """
    rng = random.Random(seed)

    # Step 1: Filteirng
    filtered = [v for v in data if v["time_delta"] in time_deltas]

    # Step 2: Grouping
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for video in filtered:
        key = (video["channel_id"], video["time_delta"])
        groups[key].append(video)

    # Step 3: Sampling per group
    sample: list[dict] = []

    for (channel_id, td), videos in groups.items():
        if prioritize_politics:
            politics_1 = [v for v in videos if v.get("politics_classification") == 1]
            politics_other = [v for v in videos if v.get("politics_classification") != 1]

            rng.shuffle(politics_1)
            rng.shuffle(politics_other)

            selected = politics_1[:max_per_group]
            remaining_slots = max_per_group - len(selected)
            if remaining_slots > 0:
                selected += politics_other[:remaining_slots]
        else:
            shuffled = videos[:]
            rng.shuffle(shuffled)
            selected = shuffled[:max_per_group]

        sample.extend(selected)

    return sample


def main(input_file, output_file, exclude_keywords, time_deltas, max_per_group, prioritize_politics = False, seed = 42):
    # Loading and adding time delta
    print(f"Loading data from: {input_file}")
    data = load_data(input_file)
    data = enrich_with_time_delta(data)
    print(f"  → {len(data)} videos loaded.")

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

    # Breakdown by channel_id × time_delta
    # group_counts: dict[tuple, int] = defaultdict(int)
    # for v in sample:
    #     group_counts[(v["channel_id"], v["time_delta"])] += 1
    # print("\nVideos per (channel_id × time_delta):")
    # for (ch, td) in sorted(group_counts):
    #     print(f"  channel={ch}, time_delta={td:+d}: {group_counts[(ch, td)]} Videos")


if __name__ == "__main__":
    main(INPUT_FILE, OUTPUT_FILE, KEYWORDS, TIME_DELTAS, MAX_PER_GROUP, PRIORITIZE_POLITICS, SEED)
"""
sample_videos.py
----------------
Draws a sample from a JSON file, based on the last N videos per channel
before a reference event (with optional fill-up from videos after the event).

Arguments:
    --input             Path to input JSON file
    --output            Path to output JSON file
    --n_videos          Target number of videos per channel (before the cutoff,
                         filled up with videos after the cutoff if necessary)
    --prioritize_politics  If used: politics_classification=1 is prioritized
                            both in the "before" and the "after" pool
    --seed              Random seed (only used to break ties between videos
                         with identical published_at timestamps)
"""

import json
import random
import pandas as pd
from datetime import datetime, timezone
from collections import defaultdict

from youtube_code.config import SAMPLES, RAW, KEYWORDS_MIDDLE_EAST, KEYWORDS_RUSSIA_UKRAINE, CHANNEL_LISTS, TRANSCRIPTS
from youtube_code.utils import load_set

# ─────────────────────────────────────────────
# CONFIGURATION AND PATHS
# ─────────────────────────────────────────────
### CENTRAL CONFIGURATION ###
KEYWORDS = KEYWORDS_RUSSIA_UKRAINE

sample_name = "russia"   # ["conflict_over_time", "party_identification"]

all_videos_file_name = "all_videos_russia_ukraine.json"
output_file_name_sampled = "sampled_50k_channels.json"
output_file_name_keyword = "keyword_videos_50k_channels.json"
output_file_name_summary = "summary_statistics_50k_channels.json"
no_shorts_output = "videos_wo_shorts_russia_ukraine.json"

REFERENCE_DATE = datetime(2022, 2, 24, tzinfo=timezone.utc)
FILE_ALL_VIDEOS = SAMPLES / f"{sample_name}" / all_videos_file_name
OUTPUT_NO_SHORTS = SAMPLES / f"{sample_name}" / no_shorts_output
METADATA_PATH = RAW / "video_metadata_total.jsonl"
OUTPUT_FILE = SAMPLES / sample_name / output_file_name_sampled
OUTPUT_SUMMARY_FILE = SAMPLES / sample_name / output_file_name_summary

# Target number of videos per channel: the most recent videos published
# BEFORE the exact reference timestamp. If a channel doesn't have
# enough videos before the cutoff, the remainder is filled with the
# earliest videos published ON/AFTER the cutoff.
N_VIDEOS_PER_CHANNEL = 50
PRIORITIZE_POLITICS = False
SEED = 42

CHANNEL_LIST = CHANNEL_LISTS / f"all_identification" / "german_channels_10k.json"
OUTPUT_KEYWORD_VIDEOS = SAMPLES / f"{sample_name}" / output_file_name_keyword

COT_SAMPLE_VIDEOS = SAMPLES / "russia" / "sampled_50k_channels_test.json"
TRANSCRIPTS_PATH = TRANSCRIPTS / "no_file.csv"


def get_all_videos(channel_list_path, output_path, metadata_path):
    print("Creating file with all videos uploaded from channels on the list.")
    print(f"Channels: {channel_list_path}")
    channel_set = load_set(channel_list_path)

    KEYS_TO_KEEP = [
        "video_id",
        "title",
        "channel_id",
        "channel_title",
        "published_at",
        "politics_classification",
    ]

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
                    filtered_data = {key: data.get(key) for key in KEYS_TO_KEEP}
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


def parse_published_at(published_at: str) -> datetime:
    """Parses an ISO-8601 timestamp and normalizes it to UTC."""
    dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_before_reference_date(published_at: str) -> bool:
    """True only if the complete timestamp lies before REFERENCE_DATE."""
    return parse_published_at(published_at) < REFERENCE_DATE


def compute_time_delta(published_at: str) -> int:
    """
    Calculates the month bin relative to REFERENCE_DATE for downstream use.

    Important: this value is not used for the before/after cutoff. Sampling
    uses is_before_reference_date(), which compares the complete timestamps.
    """
    dt = parse_published_at(published_at)
    month_diff = (dt.year - REFERENCE_DATE.year) * 12 + (dt.month - REFERENCE_DATE.month)

    reference_boundary = (
        REFERENCE_DATE.day,
        REFERENCE_DATE.hour,
        REFERENCE_DATE.minute,
        REFERENCE_DATE.second,
        REFERENCE_DATE.microsecond,
    )
    timestamp_position = (dt.day, dt.hour, dt.minute, dt.second, dt.microsecond)
    if timestamp_position < reference_boundary:
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


def filter_by_keywords(data: list[dict], keywords: list[str]) -> tuple[list[dict], list[dict]]:
    """
    Removes videos whose title contains any of the given keywords.
    Matching is case-insensitive, i.e. "Israel" and "israel" are treated the same.
    If a video has no title, it is kept.

    Args:
        data:     List of video dicts.
        keywords: List of keywords to exclude.

    Returns:
        Tuple of the filtered list and the identified keyword videos.
    """
    if not keywords:
        return data, []
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

    OUTPUT_KEYWORD_VIDEOS.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_KEYWORD_VIDEOS, "w", encoding = "utf-8") as f:
        json.dump(keyword_videos, f, ensure_ascii = False, indent = 2)

    return filtered, keyword_videos


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
    sample (still subject to the n_videos cap, see sample_videos()).
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


def _select_prioritized(pool: list[dict], slots: int, prioritize_politics: bool) -> list[dict]:
    """
    Picks up to `slots` videos from an already-sorted `pool` (sort order,
    i.e. "most relevant first", is preserved from the caller).

    If prioritize_politics is True, videos with politics_classification == 1
    are taken first (in the pool's existing order), and only once those are
    exhausted are the remaining (non-political) videos added — also in the
    pool's existing order.
    """
    if slots <= 0 or not pool:
        return []

    if not prioritize_politics:
        return pool[:slots]

    politics_videos = [v for v in pool if v.get("politics_classification") == 1]
    other_videos = [v for v in pool if v.get("politics_classification") != 1]

    selected = politics_videos[:slots]
    remaining = slots - len(selected)
    if remaining > 0:
        selected.extend(other_videos[:remaining])
    return selected


def sample_videos(
    data: list[dict],
    n_videos: int,
    prioritize_politics: bool,
    existing_videos_path: str,
    priority_ids_csv_path: str | None = None,
    seed: int | None = None,
) -> list[dict]:
    """Builds the sample per channel using the following logic:

    1. Loads existing videos and identifies all channels present in that file.
       For these existing channels, ALL of their videos from that file are
       carried over unfiltered. These channels are fully excluded from any
       further sampling below.
    2. Loads a list of "priority" video IDs from a CSV file
       (priority_ids_csv_path). Any video from `data` whose video_id is in
       that list is forced into the sample for its channel, as long as the
       channel is not already covered by step 1. These forced videos count
       towards the n_videos cap.
    3. For every remaining channel, videos are split into:
         - a "before" pool: full timestamp < REFERENCE_DATE
         - an "after" pool: full timestamp >= REFERENCE_DATE
       The "before" pool is sorted most-recent-first and the top n_videos
       (minus any slots already used by priority videos) are selected. If
       prioritize_politics is True, videos with politics_classification == 1
       are selected first (still most-recent-first among themselves), and
       only once those are exhausted are non-political videos added.
       If the "before" pool doesn't provide enough videos to fill the quota,
       the remaining slots are filled from the "after" pool, sorted
       soonest-after-cutoff-first, using the same prioritize_politics logic.
    4. The n_videos cap is always strictly enforced per channel, including
       forced priority videos from step 2.

    Ties between videos with an identical published_at timestamp are broken
    randomly (seeded) before sorting, so results are reproducible.
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
                    if "time_delta" not in video and video.get("published_at"):
                        video["time_delta"] = compute_time_delta(video["published_at"])
                    # Remember which channels need to be blocked from new sampling
                    existing_channels.add(channel_id)
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
    filtered_new_data = [
        v for v in data if v["channel_id"] not in existing_channels
    ]

    # --- STEP 4: GROUP THE NEW DATA BY CHANNEL ---
    channel_groups: dict[str, list[dict]] = defaultdict(list)
    for video in filtered_new_data:
        channel_groups[video["channel_id"]].append(video)

    # --- STEP 5: PER-CHANNEL SELECTION ---
    for channel_id, videos in channel_groups.items():
        priority_videos = [
            v for v in videos if v.get("video_id") in priority_video_ids
        ]
        other_videos = [
            v for v in videos if v.get("video_id") not in priority_video_ids
        ]

        rng.shuffle(priority_videos)
        # Even priority videos must respect the n_videos cap
        selected = priority_videos[:n_videos]
        remaining_slots = n_videos - len(selected)

        if remaining_slots > 0:
            before_pool = [
                v for v in other_videos if is_before_reference_date(v["published_at"])
            ]
            after_pool = [
                v for v in other_videos if not is_before_reference_date(v["published_at"])
            ]

            # Randomize first so identical published_at timestamps get a
            # reproducible (seeded) but non-biased tie order, then sort.
            rng.shuffle(before_pool)
            before_pool.sort(key=lambda v: v["published_at"], reverse=True)  # most recent first

            rng.shuffle(after_pool)
            after_pool.sort(key=lambda v: v["published_at"])  # soonest after cutoff first

            from_before = _select_prioritized(before_pool, remaining_slots, prioritize_politics)
            selected.extend(from_before)
            remaining_slots = n_videos - len(selected)

            if remaining_slots > 0:
                from_after = _select_prioritized(after_pool, remaining_slots, prioritize_politics)
                selected.extend(from_after)

        sample.extend(selected)

    return sample


def _distribution(values: list[int]) -> dict:
    """Returns stable descriptive statistics, including zero values."""
    if not values:
        return {
            "mean": None,
            "median": None,
            "percentile_25": None,
            "percentile_75": None,
            "min": None,
            "max": None,
        }

    series = pd.Series(values, dtype="float64")
    return {
        "mean": float(series.mean()),
        "median": float(series.median()),
        "percentile_25": float(series.quantile(0.25)),
        "percentile_75": float(series.quantile(0.75)),
        "min": int(series.min()),
        "max": int(series.max()),
    }


def _load_existing_channel_ids(existing_videos_path: str | None) -> set[str]:
    if not existing_videos_path:
        return set()
    try:
        with open(existing_videos_path, "r", encoding="utf-8") as f:
            return {
                video["channel_id"]
                for video in json.load(f)
                if video.get("channel_id")
            }
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def build_summary_statistics(
    candidate_data: list[dict],
    keyword_videos: list[dict],
    sample: list[dict],
    n_videos: int,
    existing_videos_path: str | None,
    priority_ids_csv_path: str | None,
) -> dict:
    """Builds an overview of channels, keyword videos, and fill-up methods."""
    candidate_channel_ids = {
        video["channel_id"] for video in candidate_data if video.get("channel_id")
    }
    keyword_counts = {channel_id: 0 for channel_id in candidate_channel_ids}
    for video in keyword_videos:
        channel_id = video.get("channel_id")
        if channel_id in keyword_counts:
            keyword_counts[channel_id] += 1

    sample_by_channel: dict[str, list[dict]] = defaultdict(list)
    for video in sample:
        if video.get("channel_id"):
            sample_by_channel[video["channel_id"]].append(video)

    existing_channel_ids = _load_existing_channel_ids(existing_videos_path)
    priority_video_ids = load_priority_video_ids(priority_ids_csv_path)

    fill_methods: dict[str, int] = defaultdict(int)
    period_composition: dict[str, int] = defaultdict(int)
    politics_composition: dict[str, int] = defaultdict(int)
    period_x_politics: dict[str, int] = defaultdict(int)
    channels_with_priority_videos = 0

    for channel_id, videos in sample_by_channel.items():
        before_count = sum(
            is_before_reference_date(v["published_at"])
            for v in videos
            if v.get("published_at")
        )
        after_count = sum(
            not is_before_reference_date(v["published_at"])
            for v in videos
            if v.get("published_at")
        )
        politics_count = sum(v.get("politics_classification") == 1 for v in videos)
        non_politics_count = len(videos) - politics_count

        if before_count and after_count:
            period = "before_and_on_or_after_reference_date"
        elif before_count:
            period = "only_before_reference_date"
        elif after_count:
            period = "only_on_or_after_reference_date"
        else:
            period = "missing_publication_date"

        if politics_count and non_politics_count:
            politics = "politics_and_non_politics"
        elif politics_count:
            politics = "only_politics"
        else:
            politics = "only_non_politics"

        period_composition[period] += 1
        politics_composition[politics] += 1
        period_x_politics[f"{period}__{politics}"] += 1

        if channel_id in existing_channel_ids:
            fill_methods["existing_channel_carried_over"] += 1
        elif len(videos) < n_videos:
            fill_methods["quota_not_reached_even_after_fill_up"] += 1
        elif after_count:
            fill_methods["quota_reached_using_on_or_after_videos"] += 1
        else:
            fill_methods["quota_reached_with_before_videos_only"] += 1

        if any(v.get("video_id") in priority_video_ids for v in videos):
            channels_with_priority_videos += 1

    before_sample = sum(
        is_before_reference_date(v["published_at"])
        for v in sample
        if v.get("published_at")
    )
    after_sample = sum(
        not is_before_reference_date(v["published_at"])
        for v in sample
        if v.get("published_at")
    )
    politics_sample = sum(v.get("politics_classification") == 1 for v in sample)

    return {
        "reference_date": REFERENCE_DATE.isoformat(),
        "cutoff_rule": "published_at < reference_date; exact timestamp comparison in UTC",
        "channels": {
            "total_in_length_filtered_input": len(candidate_channel_ids),
            "total_in_final_sample": len(sample_by_channel),
            "with_at_least_one_keyword_video": sum(v > 0 for v in keyword_counts.values()),
            "with_priority_video_in_final_sample": channels_with_priority_videos,
        },
        "keyword_videos": {
            "total": len(keyword_videos),
            "per_channel_including_zero_counts": _distribution(list(keyword_counts.values())),
        },
        "sample_videos": {
            "total": len(sample),
            "before_reference_date": before_sample,
            "on_or_after_reference_date": after_sample,
            "politics": politics_sample,
            "non_politics": len(sample) - politics_sample,
            "per_channel": _distribution([len(v) for v in sample_by_channel.values()]),
        },
        "channel_fill_methods": dict(sorted(fill_methods.items())),
        "channel_period_composition": dict(sorted(period_composition.items())),
        "channel_politics_composition": dict(sorted(politics_composition.items())),
        "channel_period_x_politics_composition": dict(sorted(period_x_politics.items())),
    }


def get_random_sample(input_file, output_no_shorts, output_file, exclude_keywords, n_videos, prioritize_politics = False, seed = 42):
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
    candidate_data = data

    # Excluding keyword videos
    before = len(data)
    data, keyword_videos = filter_by_keywords(data, exclude_keywords)
    print(f"  → {before - len(data)} videos removed by keyword filter.")
    print(f"  → {len(data)} videos remaining.")

    with open(output_no_shorts, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nAll videos w/o shorts saved to: '{output_no_shorts}'")

    # Sampling
    sample = sample_videos(
        data=data,
        n_videos=n_videos,
        existing_videos_path=COT_SAMPLE_VIDEOS,
        priority_ids_csv_path= TRANSCRIPTS_PATH,
        prioritize_politics=prioritize_politics,
        seed=seed,
    )

    # Output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)

    summary = build_summary_statistics(
        candidate_data=candidate_data,
        keyword_videos=keyword_videos,
        sample=sample,
        n_videos=n_videos,
        existing_videos_path=COT_SAMPLE_VIDEOS,
        priority_ids_csv_path=TRANSCRIPTS_PATH,
    )
    OUTPUT_SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Summary
    print(f"\nSample saved under: {output_file}")
    print(f"  → {len(sample)} videos in sample.")
    print(f"Summary statistics saved under: {OUTPUT_SUMMARY_FILE}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    get_all_videos(CHANNEL_LIST, FILE_ALL_VIDEOS, METADATA_PATH)

    get_random_sample(FILE_ALL_VIDEOS, OUTPUT_NO_SHORTS, OUTPUT_FILE, KEYWORDS, N_VIDEOS_PER_CHANNEL, PRIORITIZE_POLITICS, SEED)
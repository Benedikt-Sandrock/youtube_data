import hashlib
import json
import pandas as pd
from pathlib import Path

from youtube_code.step2_baseline_channels.screening_config import (
    EXCLUDED_CHANNELS_FILE,
    EXCLUDE_CHANNELS_WITHOUT_KEYWORD_VIDEO,
    INTERVAL_SIZE,
    INTERVAL_START,
    KEYWORD_VIDEOS_FILE,
    MAIN_VIDEO_FILE,
    READ_CHUNK_SIZE,
    SELECTION_SEED,
    STATE_FILE,
    TARGET_POLITICAL_PER_INTERVAL,
    TARGET_WITH_BUFFER_PER_INTERVAL,
)

INPUT_FILE = MAIN_VIDEO_FILE

REQUIRED_COLUMNS = [
    "video_id",
    "channel_id",
    "channel_title",
    "published_at",
    "title",
    "description",
    "time_delta",
]

LABEL_COLUMNS = [
    "politics_title",
    "politics_title_desc",
    "politics_final",
]


def load_keyword_videos(keyword_videos_path: Path) -> pd.DataFrame:
    """
    Load the separate keyword-video file.

    Both a JSON list and JSONL are accepted. Only the columns needed for
    channel eligibility are retained.
    """
    if not keyword_videos_path.exists():
        raise FileNotFoundError(
            "Keyword channel filtering requires this file, but it was not "
            f"found: {keyword_videos_path}"
        )

    with open(keyword_videos_path, "r", encoding="utf-8") as file:
        first_character = ""
        while not first_character:
            character = file.read(1)
            if not character:
                break
            if not character.isspace():
                first_character = character
        file.seek(0)

        if first_character == "[":
            records = json.load(file)
        else:
            records = [
                json.loads(line)
                for line in file
                if line.strip()
            ]

    keyword_videos = pd.DataFrame(records)
    required = {"channel_id"}
    missing = required - set(keyword_videos.columns)
    if missing:
        raise ValueError(
            "Keyword-video file is missing columns: "
            f"{sorted(missing)}"
        )

    keyword_videos = keyword_videos[["channel_id"]].copy()
    keyword_videos["channel_id"] = keyword_videos["channel_id"].astype(
        "string"
    )
    keyword_videos = keyword_videos.dropna(subset=["channel_id"])

    return keyword_videos


def stable_random_key(video_id: str, seed: int) -> int:
    """Return a reproducible pseudo-random key without global RNG state."""
    value = f"{seed}|{video_id}".encode("utf-8")
    return int.from_bytes(
        hashlib.blake2b(value, digest_size=8).digest(),
        byteorder="big",
        signed=False,
    )


def assign_intervals(
    period: pd.Series,
    interval_start: int,
    interval_size: int,
) -> tuple[pd.Series, pd.Series]:
    """
    Group consecutive periods into fixed-width intervals.

    Intervals are anchored at interval_start, e.g. with interval_start=-12
    and interval_size=3: [-12,-11,-10], [-9,-8,-7], ..., [0,1,2], [3,4,5], ...
    Requires period >= interval_start.
    """
    interval_index = (
        (period - interval_start) // interval_size
    ).astype("int32")
    interval_start_period = interval_start + interval_index * interval_size
    interval_end_period = interval_start_period + interval_size - 1
    interval_label = (
        interval_start_period.astype("string")
        + "_to_"
        + interval_end_period.astype("string")
    )
    return interval_index, interval_label


def initialize_screening_state(
    input_json: Path,
    state_path: Path,
    keyword_videos_path: Path,
    excluded_channels_path: Path,
    interval_start: int = -12,
    interval_size: int = 3,
    target_political_per_interval: int = 10,
    target_with_buffer_per_interval: int = 12,
    exclude_channels_without_keyword_video: bool = False,
    selection_seed: int = 42,
    chunk_size: int = 50_000,
):
    if target_political_per_interval < 1:
        raise ValueError("target_political_per_interval must be at least 1.")
    if target_with_buffer_per_interval < target_political_per_interval:
        raise ValueError(
            "target_with_buffer_per_interval must be greater than or equal "
            "to target_political_per_interval."
        )

    print("Loading separate keyword-video file.")
    keyword_videos = load_keyword_videos(keyword_videos_path)
    keyword_channel_counts = (
        keyword_videos.groupby("channel_id").size()
        if not keyword_videos.empty
        else pd.Series(dtype="int64")
    )
    print(
        f"{len(keyword_videos):,} valid keyword videos loaded, covering "
        f"{len(keyword_channel_counts):,} channels."
    )

    print("Reading period-labeled videos.")
    chunks = []
    reader = pd.read_json(input_json, lines=True, chunksize=chunk_size)

    for chunk_number, chunk in enumerate(reader, start=1):
        missing = set(REQUIRED_COLUMNS) - set(chunk.columns)
        if missing:
            raise ValueError(
                f"Missing columns in chunk {chunk_number}: {sorted(missing)}"
            )

        chunk = chunk[REQUIRED_COLUMNS].copy()
        chunk["published_at"] = pd.to_datetime(
            chunk["published_at"],
            utc=True,
            errors="coerce",
        )
        chunk = chunk.dropna(
            subset=["video_id", "channel_id", "published_at", "time_delta"]
        )
        chunk["video_id"] = chunk["video_id"].astype("string")
        chunk["channel_id"] = chunk["channel_id"].astype("string")
        chunk["period"] = chunk["time_delta"].astype("int64")
        chunk = chunk.drop(columns="time_delta")

        chunks.append(chunk)
        print(f"Read chunk {chunk_number}: {len(chunk):,} videos")

    if not chunks:
        raise ValueError("No videos found in the input file.")

    df = pd.concat(chunks, ignore_index=True)
    del chunks

    print(f"Videos before duplicate removal: {len(df):,}")
    df = df.drop_duplicates(subset="video_id", keep="last")
    print(f"Videos after duplicate removal: {len(df):,}")

    below_start = df["period"].lt(interval_start)
    if below_start.any():
        print(
            f"Dropping {below_start.sum():,} videos with period below "
            f"interval_start={interval_start}."
        )
        df = df.loc[~below_start].copy()

    if df.empty:
        raise ValueError("No videos remain at or after interval_start.")

    max_period = int(df["period"].max())
    print(f"Period range in data: {interval_start} to {max_period}.")

    df["interval_index"], df["interval_label"] = assign_intervals(
        period=df["period"],
        interval_start=interval_start,
        interval_size=interval_size,
    )

    has_keyword_video = df["channel_id"].isin(keyword_channel_counts.index)
    excluded_channels = (
        df.loc[~has_keyword_video, "channel_id"]
        .drop_duplicates()
        .to_frame(name="channel_id")
    )
    excluded_channels_path.parent.mkdir(parents=True, exist_ok=True)
    excluded_channels.to_csv(excluded_channels_path, index=False)

    print(
        "Keyword channel filter: "
        f"{'enabled' if exclude_channels_without_keyword_video else 'disabled'}."
    )
    print(
        f"{df['channel_id'].nunique():,} channels total; "
        f"{len(excluded_channels):,} without a keyword video in the "
        "entire dataset."
    )

    if exclude_channels_without_keyword_video:
        df = df.loc[has_keyword_video].copy()

    if df.empty:
        raise ValueError(
            "No eligible videos remain after the keyword activity filter."
        )

    # Reproducible random order within each channel-period.
    df["_random_order"] = df["video_id"].map(
        lambda video_id: stable_random_key(
            video_id=str(video_id),
            seed=selection_seed,
        )
    )
    df = df.sort_values(
        ["channel_id", "period", "_random_order", "published_at"],
        ascending=[True, True, True, False],
    )
    df["rank_within_period"] = (
        df.groupby(["channel_id", "period"], sort=False)
        .cumcount()
        .astype("int32")
    )

    # Interleave periods within each interval: first randomized video from
    # each period in the interval, then the second from each period, etc.
    df = df.sort_values(
        ["channel_id", "interval_index", "rank_within_period", "period"],
        ascending=[True, True, True, True],
    )
    df["candidate_rank"] = (
        df.groupby(["channel_id", "interval_index"], sort=False)
        .cumcount()
        .astype("int32")
    )
    df = df.drop(columns="_random_order")

    df["target_political_per_interval"] = target_political_per_interval
    df["target_with_buffer_per_interval"] = target_with_buffer_per_interval

    for column in LABEL_COLUMNS:
        df[column] = pd.Series(pd.NA, index=df.index, dtype="Int8")

    df["screening_round"] = pd.Series(pd.NA, index=df.index, dtype="Int16")
    df["selected_for_transcript"] = pd.Series(
        pd.NA, index=df.index, dtype="boolean"
    )
    df["is_transcript_reserve"] = pd.Series(
        pd.NA, index=df.index, dtype="boolean"
    )

    state_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(
        state_path,
        index=False,
        date_format="%Y-%m-%dT%H:%M:%SZ",
    )

    print(f"{len(df):,} candidate videos.")
    print(f"{df['channel_id'].nunique():,} channels with candidates.")
    print(f"{df['interval_index'].nunique():,} intervals.")
    print(
        "Channels without a keyword video in the dataset were saved to "
        f"{excluded_channels_path}."
    )
    print(f"Saved to {state_path}.")


if __name__ == "__main__":
    if STATE_FILE.exists():
        print(
            f"Screening state already exists: {STATE_FILE}\n"
            "Initialization was skipped to preserve existing labels."
        )
    else:
        initialize_screening_state(
            input_json=INPUT_FILE,
            state_path=STATE_FILE,
            keyword_videos_path=KEYWORD_VIDEOS_FILE,
            excluded_channels_path=EXCLUDED_CHANNELS_FILE,
            interval_start=INTERVAL_START,
            interval_size=INTERVAL_SIZE,
            target_political_per_interval=TARGET_POLITICAL_PER_INTERVAL,
            target_with_buffer_per_interval=TARGET_WITH_BUFFER_PER_INTERVAL,
            exclude_channels_without_keyword_video=(
                EXCLUDE_CHANNELS_WITHOUT_KEYWORD_VIDEO
            ),
            selection_seed=SELECTION_SEED,
            chunk_size=READ_CHUNK_SIZE,
        )
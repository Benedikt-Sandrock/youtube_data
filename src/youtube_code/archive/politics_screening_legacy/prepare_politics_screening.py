import hashlib
import json
import pandas as pd
from pathlib import Path

from youtube_code.step2_baseline_channels.longitudinal.screening_config import (
    MAIN_VIDEO_FILE,
    EXCLUDED_CHANNELS_FILE,
    EXCLUDE_CHANNELS_WITHOUT_KEYWORD_VIDEO,
    KEYWORD_ACTIVITY_SCOPE,
    KEYWORD_VIDEOS_FILE,
    READ_CHUNK_SIZE,
    REFERENCE_DATE,
    SELECTION_SEED,
    STATE_FILE,
    TARGET_POLITICAL_PER_PERIOD,
    TARGET_WITH_BUFFER_PER_PERIOD,
    WINDOW_MONTHS,
)

INPUT_FILE = MAIN_VIDEO_FILE

REQUIRED_COLUMNS = [
    "video_id",
    "channel_id",
    "published_at",
    "title",
    "description",
]

LABEL_COLUMNS = [
    "politics_title",
    "politics_title_desc",
    "politics_final",
]


def parse_reference_date(reference_date: str) -> pd.Timestamp:
    reference = pd.Timestamp(reference_date)

    if reference.tzinfo is None:
        return reference.tz_localize("UTC")

    return reference.tz_convert("UTC")


def load_keyword_videos(keyword_videos_path: Path) -> pd.DataFrame:
    """
    Load the separate keyword-video file.

    Both a JSON list and JSONL are accepted. Only the columns needed for
    channel eligibility and documentation are retained.
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
    required = {"channel_id", "published_at"}
    missing = required - set(keyword_videos.columns)
    if missing:
        raise ValueError(
            "Keyword-video file is missing columns: "
            f"{sorted(missing)}"
        )

    columns = ["channel_id", "published_at"]
    if "video_id" in keyword_videos.columns:
        columns.insert(0, "video_id")

    keyword_videos = keyword_videos[columns].copy()
    keyword_videos["channel_id"] = keyword_videos["channel_id"].astype(
        "string"
    )
    keyword_videos["published_at"] = pd.to_datetime(
        keyword_videos["published_at"],
        utc=True,
        errors="coerce",
    )
    keyword_videos = keyword_videos.dropna(
        subset=["channel_id", "published_at"]
    )

    if "video_id" in keyword_videos.columns:
        keyword_videos["video_id"] = keyword_videos["video_id"].astype(
            "string"
        )
        keyword_videos = keyword_videos.drop_duplicates(
            subset="video_id",
            keep="last",
        )
    else:
        keyword_videos = keyword_videos.drop_duplicates()

    return keyword_videos


def add_keyword_activity_to_channel_activity(
    channel_activity: pd.DataFrame,
    keyword_videos: pd.DataFrame,
) -> pd.DataFrame:
    """
    Include keyword videos when estimating the first and last observed video.

    This matters because INPUT_FILE may intentionally contain only
    non-keyword videos. Without this union, a channel's observed start could
    be shifted forward when its earliest upload is a keyword video.
    """
    if keyword_videos.empty:
        return channel_activity

    keyword_activity = (
        keyword_videos.groupby("channel_id")["published_at"]
        .agg(
            channel_start_date="min",
            channel_last_video="max",
        )
    )

    combined = pd.concat([channel_activity, keyword_activity])
    combined = (
        combined.groupby(level=0)
        .agg(
            channel_start_date=("channel_start_date", "min"),
            channel_last_video=("channel_last_video", "max"),
        )
        .sort_index()
    )
    combined.index = combined.index.astype("string")
    combined.index.name = "channel_id"
    return combined


def add_keyword_eligibility(
    channel_windows: pd.DataFrame,
    keyword_videos: pd.DataFrame,
    activity_scope: str,
) -> pd.DataFrame:
    """
    Count keyword videos per channel in the configured eligibility scope.
    """
    valid_scopes = {"channel_window", "entire_dataset"}
    if activity_scope not in valid_scopes:
        raise ValueError(
            "keyword_activity_scope must be one of "
            f"{sorted(valid_scopes)}, got {activity_scope!r}."
        )

    windows = channel_windows.copy()

    if keyword_videos.empty:
        counts = pd.Series(dtype="int64")
    elif activity_scope == "entire_dataset":
        counts = keyword_videos.groupby("channel_id").size()
    else:
        keyword_with_window = keyword_videos.merge(
            windows[["window_start", "window_end"]],
            left_on="channel_id",
            right_index=True,
            how="inner",
            validate="many_to_one",
        )
        keyword_with_window = keyword_with_window.loc[
            keyword_with_window["published_at"].ge(
                keyword_with_window["window_start"]
            )
            & keyword_with_window["published_at"].lt(
                keyword_with_window["window_end"]
            )
        ]
        counts = keyword_with_window.groupby("channel_id").size()

    windows["keyword_video_count_in_scope"] = (
        counts.reindex(windows.index, fill_value=0)
        .astype("int32")
    )
    windows["has_keyword_video_in_scope"] = (
        windows["keyword_video_count_in_scope"].gt(0)
    )
    return windows


def stable_random_key(video_id: str, seed: int) -> int:
    """Return a reproducible pseudo-random key without global RNG state."""
    value = f"{seed}|{video_id}".encode("utf-8")
    return int.from_bytes(
        hashlib.blake2b(value, digest_size=8).digest(),
        byteorder="big",
        signed=False,
    )


def scan_channel_activity(
    input_json: Path,
    chunk_size: int,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    """
    First pass over the JSONL file.

    The earliest observed video is used as a proxy for the channel's start.
    This is exact only if the input contains the channel's complete video
    history or an actual channel creation date is not available separately.
    """
    activity_parts = []
    dataset_last_observed = None

    reader = pd.read_json(
        input_json,
        lines=True,
        chunksize=chunk_size,
    )

    for chunk_number, chunk in enumerate(reader, start=1):
        required = {"channel_id", "published_at"}
        missing = required - set(chunk.columns)

        if missing:
            raise ValueError(
                f"Missing columns in chunk {chunk_number}: "
                f"{sorted(missing)}"
            )

        chunk = chunk[["channel_id", "published_at"]].copy()
        chunk["published_at"] = pd.to_datetime(
            chunk["published_at"],
            utc=True,
            errors="coerce",
        )
        chunk = chunk.dropna(
            subset=["channel_id", "published_at"]
        )
        chunk["channel_id"] = chunk["channel_id"].astype(
            "string"
        )

        if chunk.empty:
            print(
                f"Activity scan, chunk {chunk_number}: "
                "no valid rows"
            )
            continue

        chunk_activity = (
            chunk.groupby("channel_id")["published_at"]
            .agg(channel_start_date="min", channel_last_video="max")
        )
        activity_parts.append(chunk_activity)

        chunk_last_observed = chunk["published_at"].max()
        if (
            dataset_last_observed is None
            or chunk_last_observed > dataset_last_observed
        ):
            dataset_last_observed = chunk_last_observed

        print(
            f"Activity scan, chunk {chunk_number}: "
            f"{chunk['channel_id'].nunique():,} channels"
        )

    if not activity_parts or dataset_last_observed is None:
        raise ValueError("No valid channel activity found in the input file.")

    channel_activity = (
        pd.concat(activity_parts)
        .groupby(level=0)
        .agg(
            channel_start_date=("channel_start_date", "min"),
            channel_last_video=("channel_last_video", "max"),
        )
        .sort_index()
    )
    channel_activity.index = channel_activity.index.astype("string")
    channel_activity.index.name = "channel_id"

    return channel_activity, dataset_last_observed


def build_channel_windows(
    channel_activity: pd.DataFrame,
    reference: pd.Timestamp,
    months: int,
    dataset_last_observed: pd.Timestamp,
) -> pd.DataFrame:
    """Create a channel-specific observation window.

    Established channel:
        [reference - months, reference)

    Channel first observed shortly before or after the reference date:
        [first observed video, first observed video + months)
    """
    if months < 1:
        raise ValueError("months must be at least 1.")

    windows = channel_activity.copy()
    regular_window_start = reference - pd.DateOffset(months=months)

    established = windows["channel_start_date"].le(
        regular_window_start
    )
    near_reference = (
        windows["channel_start_date"].gt(regular_window_start)
        & windows["channel_start_date"].lt(reference)
    )
    after_reference = windows["channel_start_date"].ge(reference)

    windows["window_start"] = windows["channel_start_date"]
    windows.loc[established, "window_start"] = regular_window_start

    windows["window_end"] = pd.Series(
        [
            date + pd.DateOffset(months=months)
            for date in windows["channel_start_date"]
        ],
        index=windows.index,
        dtype="datetime64[ns, UTC]",
    )
    windows.loc[established, "window_end"] = reference

    windows["window_type"] = pd.Series(
        pd.NA,
        index=windows.index,
        dtype="string",
    )
    windows.loc[established, "window_type"] = (
        "established_pre_reference"
    )
    windows.loc[near_reference, "window_type"] = (
        "new_near_reference"
    )
    windows.loc[after_reference, "window_type"] = (
        "new_after_reference"
    )

    # These cutoffs define calendar months relative to each channel's
    # individual window start, rather than fixed calendar months.
    for period_number in range(1, months + 1):
        windows[f"period_{period_number}_end"] = pd.Series(
            [
                date + pd.DateOffset(months=period_number)
                for date in windows["window_start"]
            ],
            index=windows.index,
            dtype="datetime64[ns, UTC]",
        )

    # This describes temporal coverage of the complete input dataset. It is
    # not a statement about whether an individual channel kept uploading.
    windows["dataset_covers_window_end"] = (
        dataset_last_observed >= windows["window_end"]
    )

    return windows


def initialize_screening_state(
    input_json: Path,
    state_path: Path,
    reference_date: str,
    keyword_videos_path: Path,
    excluded_channels_path: Path,
    observation_months: int = 3,
    target_political_per_period: int = 10,
    target_with_buffer_per_period: int = 12,
    exclude_channels_without_keyword_video: bool = True,
    keyword_activity_scope: str = "channel_window",
    selection_seed: int = 42,
    chunk_size: int = 50_000,
):
    if target_political_per_period < 1:
        raise ValueError("target_political_per_period must be at least 1.")
    if target_with_buffer_per_period < target_political_per_period:
        raise ValueError(
            "target_with_buffer_per_period must be greater than or equal to "
            "target_political_per_period."
        )

    reference = parse_reference_date(reference_date)

    print("Loading separate keyword-video file.")
    keyword_videos = load_keyword_videos(keyword_videos_path)
    print(f"{len(keyword_videos):,} valid keyword videos loaded.")

    print("First pass: determining each channel's first observed video.")
    channel_activity, dataset_last_observed = scan_channel_activity(
        input_json=input_json,
        chunk_size=chunk_size,
    )
    channel_activity = add_keyword_activity_to_channel_activity(
        channel_activity=channel_activity,
        keyword_videos=keyword_videos,
    )
    if not keyword_videos.empty:
        dataset_last_observed = max(
            dataset_last_observed,
            keyword_videos["published_at"].max(),
        )

    channel_windows = build_channel_windows(
        channel_activity=channel_activity,
        reference=reference,
        months=observation_months,
        dataset_last_observed=dataset_last_observed,
    )
    channel_windows = add_keyword_eligibility(
        channel_windows=channel_windows,
        keyword_videos=keyword_videos,
        activity_scope=keyword_activity_scope,
    )

    channel_windows["excluded_by_keyword_filter"] = (
        ~channel_windows["has_keyword_video_in_scope"]
        & exclude_channels_without_keyword_video
    )

    excluded_channels = channel_windows.loc[
        ~channel_windows["has_keyword_video_in_scope"]
    ].reset_index()
    excluded_channels_path.parent.mkdir(parents=True, exist_ok=True)
    excluded_channels.to_csv(
        excluded_channels_path,
        index=False,
        date_format="%Y-%m-%dT%H:%M:%SZ",
    )

    if exclude_channels_without_keyword_video:
        eligible_channel_windows = channel_windows.loc[
            channel_windows["has_keyword_video_in_scope"]
        ].copy()
    else:
        eligible_channel_windows = channel_windows.copy()

    if eligible_channel_windows.empty:
        raise ValueError(
            "No eligible channels remain after the keyword activity filter."
        )

    regular_window_start = reference - pd.DateOffset(
        months=observation_months
    )
    print(
        "Established channels: selecting videos from "
        f"{regular_window_start} until {reference}."
    )
    print(
        "New channels: selecting the first "
        f"{observation_months} months from their first observed video."
    )
    print(
        "Monthly target: "
        f"{target_political_per_period} political videos plus "
        f"{target_with_buffer_per_period - target_political_per_period} "
        "reserve videos."
    )
    print(
        "Keyword channel filter: "
        f"{'enabled' if exclude_channels_without_keyword_video else 'disabled'} "
        f"(scope={keyword_activity_scope})."
    )
    print(
        f"{len(eligible_channel_windows):,} eligible channels; "
        f"{len(excluded_channels):,} channels without keyword videos in scope."
    )

    merge_columns = [
        "channel_start_date",
        "channel_last_video",
        "window_start",
        "window_end",
        "window_type",
        "dataset_covers_window_end",
        "keyword_video_count_in_scope",
        "has_keyword_video_in_scope",
    ] + [
        f"period_{period_number}_end"
        for period_number in range(1, observation_months + 1)
    ]

    filtered_chunks = []
    reader = pd.read_json(
        input_json,
        lines=True,
        chunksize=chunk_size,
    )

    for chunk_number, chunk in enumerate(reader, start=1):
        missing = set(REQUIRED_COLUMNS) - set(chunk.columns)

        if missing:
            raise ValueError(
                f"Missing columns in chunk {chunk_number}: "
                f"{sorted(missing)}"
            )

        chunk = chunk[REQUIRED_COLUMNS].copy()
        chunk["published_at"] = pd.to_datetime(
            chunk["published_at"],
            utc=True,
            errors="coerce",
        )
        chunk = chunk.dropna(
            subset=["video_id", "channel_id", "published_at"]
        )
        chunk["video_id"] = chunk["video_id"].astype("string")
        chunk["channel_id"] = chunk["channel_id"].astype("string")

        chunk = chunk.merge(
            eligible_channel_windows[merge_columns],
            left_on="channel_id",
            right_index=True,
            how="inner",
            validate="many_to_one",
        )

        chunk = chunk.loc[
            chunk["published_at"].ge(chunk["window_start"])
            & chunk["published_at"].lt(chunk["window_end"])
        ].copy()

        if not chunk.empty:
            filtered_chunks.append(chunk)

        print(
            f"Selection pass, chunk {chunk_number}: "
            f"{len(chunk):,} candidate videos"
        )

    if not filtered_chunks:
        raise ValueError("No videos found in the channel-specific windows.")

    df = pd.concat(filtered_chunks, ignore_index=True)
    del filtered_chunks

    print(f"Videos before duplicate removal: {len(df):,}")
    df = df.drop_duplicates(subset="video_id", keep="last")
    print(f"Videos after duplicate removal: {len(df):,}")

    period_labels = [
        f"period_{period_number}"
        for period_number in range(1, observation_months + 1)
    ]
    df["time_period"] = pd.Series(
        pd.NA,
        index=df.index,
        dtype="string",
    )

    previous_end = df["window_start"]
    for period_number, label in enumerate(period_labels, start=1):
        period_end_column = f"period_{period_number}_end"
        in_period = (
            df["published_at"].ge(previous_end)
            & df["published_at"].lt(df[period_end_column])
        )
        df.loc[in_period, "time_period"] = label
        previous_end = df[period_end_column]

    if df["time_period"].isna().any():
        raise RuntimeError(
            "At least one selected video could not be assigned to a period."
        )

    df["time_period"] = pd.Categorical(
        df["time_period"],
        categories=period_labels,
        ordered=True,
    )
    df["publication_month"] = (
        df["published_at"]
        .dt.tz_localize(None)
        .dt.to_period("M")
        .astype("string")
    )

    # Reproducible random order within each channel-period. This prevents
    # systematic selection of only the newest videos in a month.
    df["_random_order"] = df["video_id"].map(
        lambda video_id: stable_random_key(
            video_id=str(video_id),
            seed=selection_seed,
        )
    )
    df = df.sort_values(
        [
            "channel_id",
            "time_period",
            "_random_order",
            "published_at",
        ],
        ascending=[True, True, True, False],
    )
    df["rank_within_period"] = (
        df.groupby(
            ["channel_id", "time_period"],
            observed=True,
            sort=False,
        )
        .cumcount()
        .astype("int32")
    )

    # Interleave periods: first randomized video from each period, followed
    # by the second randomized video from each period, and so on.
    df = df.sort_values(
        ["channel_id", "rank_within_period", "time_period"],
        ascending=[True, True, True],
    )
    df["candidate_rank"] = (
        df.groupby("channel_id", sort=False)
        .cumcount()
        .astype("int32")
    )

    helper_columns = [
        f"period_{period_number}_end"
        for period_number in range(1, observation_months + 1)
    ] + ["_random_order"]
    df = df.drop(columns=helper_columns)

    df["target_political_per_period"] = (
        target_political_per_period
    )
    df["target_with_buffer_per_period"] = (
        target_with_buffer_per_period
    )

    for column in LABEL_COLUMNS:
        df[column] = pd.Series(
            pd.NA,
            index=df.index,
            dtype="Int8",
        )

    df["screening_round"] = pd.Series(
        pd.NA,
        index=df.index,
        dtype="Int16",
    )
    df["selected_for_transcript"] = pd.Series(
        pd.NA,
        index=df.index,
        dtype="boolean",
    )
    df["is_transcript_reserve"] = pd.Series(
        pd.NA,
        index=df.index,
        dtype="boolean",
    )

    state_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(
        state_path,
        index=False,
        date_format="%Y-%m-%dT%H:%M:%SZ",
    )

    selected_channel_ids = set(df["channel_id"].dropna())
    selected_channels = len(selected_channel_ids)
    channels_without_candidates = eligible_channel_windows.index[
        ~eligible_channel_windows.index.isin(selected_channel_ids)
    ]
    established_without_candidates = eligible_channel_windows.loc[
        channels_without_candidates,
        "window_type",
    ].eq("established_pre_reference").sum()

    print(f"{len(df):,} candidate videos.")
    print(f"{selected_channels:,} channels with candidates.")
    print(
        f"{established_without_candidates:,} established channels had no "
        "video in the pre-reference window."
    )
    print(
        "Channels without a keyword video in the configured scope were "
        f"saved to {excluded_channels_path}."
    )
    print("Channels by window type:")
    print(
        df.drop_duplicates("channel_id")["window_type"]
        .value_counts()
        .to_string()
    )

    uncovered = (
        df.drop_duplicates("channel_id")[
            "dataset_covers_window_end"
        ]
        .eq(False)
        .sum()
    )
    if uncovered:
        print(
            f"Warning: for {uncovered:,} selected channels, the input "
            "dataset does not extend to the planned window end."
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
            reference_date=REFERENCE_DATE,
            keyword_videos_path=KEYWORD_VIDEOS_FILE,
            excluded_channels_path=EXCLUDED_CHANNELS_FILE,
            observation_months=WINDOW_MONTHS,
            target_political_per_period=TARGET_POLITICAL_PER_PERIOD,
            target_with_buffer_per_period=TARGET_WITH_BUFFER_PER_PERIOD,
            exclude_channels_without_keyword_video=(
                EXCLUDE_CHANNELS_WITHOUT_KEYWORD_VIDEO
            ),
            keyword_activity_scope=KEYWORD_ACTIVITY_SCOPE,
            selection_seed=SELECTION_SEED,
            chunk_size=READ_CHUNK_SIZE,
        )

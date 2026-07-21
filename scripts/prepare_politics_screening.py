import pandas as pd
from pathlib import Path

from youtube_code.config import SAMPLES


INPUT_FILE = (
    SAMPLES
    / "russia"
    / "videos_wo_shorts_description.jsonl"
)

STATE_FILE = (
    SAMPLES
    / "russia"
    / "politics_screening_state.csv"
)

REFERENCE_DATE = "2022-02-24T00:00:00Z"
MONTHS_BEFORE = 3

READ_CHUNK_SIZE = 50_000

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
    months_before: int = 3,
    chunk_size: int = 50_000,
):
    reference = parse_reference_date(reference_date)

    print("First pass: determining each channel's first observed video.")
    channel_activity, dataset_last_observed = scan_channel_activity(
        input_json=input_json,
        chunk_size=chunk_size,
    )

    channel_windows = build_channel_windows(
        channel_activity=channel_activity,
        reference=reference,
        months=months_before,
        dataset_last_observed=dataset_last_observed,
    )

    regular_window_start = reference - pd.DateOffset(
        months=months_before
    )
    print(
        "Established channels: selecting videos from "
        f"{regular_window_start} until {reference}."
    )
    print(
        "New channels: selecting the first "
        f"{months_before} months from their first observed video."
    )

    merge_columns = [
        "channel_start_date",
        "channel_last_video",
        "window_start",
        "window_end",
        "window_type",
        "dataset_covers_window_end",
    ] + [
        f"period_{period_number}_end"
        for period_number in range(1, months_before + 1)
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
            channel_windows[merge_columns],
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
        for period_number in range(1, months_before + 1)
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

    df = df.sort_values(
        ["channel_id", "time_period", "published_at"],
        ascending=[True, True, False],
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

    # Interleave periods: newest video from every period first, followed by
    # the second-newest video from every period, and so on. Within the same
    # rank, the most recently published video comes first.
    df = df.sort_values(
        ["channel_id", "rank_within_period", "published_at"],
        ascending=[True, True, False],
    )
    df["candidate_rank"] = (
        df.groupby("channel_id", sort=False)
        .cumcount()
        .astype("int32")
    )

    helper_columns = [
        f"period_{period_number}_end"
        for period_number in range(1, months_before + 1)
    ]
    df = df.drop(columns=helper_columns)

    for column in LABEL_COLUMNS:
        df[column] = pd.Series(
            pd.NA,
            index=df.index,
            dtype="Int8",
        )

    state_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(
        state_path,
        index=False,
        date_format="%Y-%m-%dT%H:%M:%SZ",
    )

    selected_channel_ids = set(df["channel_id"].dropna())
    selected_channels = len(selected_channel_ids)
    channels_without_candidates = channel_windows.index[
        ~channel_windows.index.isin(selected_channel_ids)
    ]
    established_without_candidates = channel_windows.loc[
        channels_without_candidates,
        "window_type",
    ].eq("established_pre_reference").sum()

    print(f"{len(df):,} candidate videos.")
    print(f"{selected_channels:,} channels with candidates.")
    print(
        f"{established_without_candidates:,} established channels had no "
        "video in the pre-reference window."
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
            months_before=MONTHS_BEFORE,
            chunk_size=READ_CHUNK_SIZE,
        )

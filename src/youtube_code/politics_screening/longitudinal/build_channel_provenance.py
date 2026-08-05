"""
Build the channel-level provenance table for the longitudinal Russia–Ukraine
YouTube analysis.

The script combines:

1. channels discovered through party-name searches,
2. the videos through which each channel was discovered,
3. the registry describing the party-name search runs,
4. channel-language classifications,
5. channel metadata, and
6. all videos in MAIN_VIDEO_FILE.

The resulting table keeps every discovered channel. Eligibility flags determine
which channels enter the current analysis. This makes it possible to lower the
subscriber threshold later without reconstructing the sample provenance.

Important date definitions
--------------------------
channel_created_at:
    The creation timestamp reported by the YouTube Channels API.

first_observed_video_date:
    The earliest video for the channel contained in MAIN_VIDEO_FILE. If
    MAIN_VIDEO_FILE excludes Shorts or unavailable videos, this is the first
    observed eligible video, not necessarily the channel's first-ever upload.

first_identification_video_date:
    The earliest publication date among the videos returned by the party-name
    searches. This is based on the video's publication date, not the date on
    which the API search was executed.

Channel types
-------------
keyword_before_reference:
    At least one identification video was published before REFERENCE_DATE.

active_before_keyword_after:
    The channel had an observed video before REFERENCE_DATE, but its first
    identification video was published on or after REFERENCE_DATE.

first_active_after_reference:
    The channel's first observed video was published on or after REFERENCE_DATE.

unclassified_missing_dates:
    A required activity or identification date could not be reconstructed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pandas as pd

from youtube_code.config import CHANNEL_LISTS, RAW, SAMPLES
from youtube_code.politics_screening.screening_config import MAIN_VIDEO_FILE


# =============================================================================
# CONFIGURATION
# =============================================================================

ANALYSIS_ID = "russia_longitudinal_v1"

REFERENCE_DATE = "2022-02-24T00:00:00Z"

# "More than 50,000" is implemented as subscribers > MIN_SUBSCRIBERS.
# Set this to 10_000 later to create the corresponding eligibility flag without
# changing the provenance logic.
MIN_SUBSCRIBERS = 50_000

# Additional thresholds are stored as reusable columns such as eligible_10k and
# eligible_50k. MIN_SUBSCRIBERS does not have to be listed here.
REUSABLE_SUBSCRIBER_THRESHOLDS = (10_000, 50_000)

DISCOVERED_CHANNELS_FILE = (
    CHANNEL_LISTS
    / "all_identification"
    / "all_channel_ids_discovered.json"
)

IDENTIFICATION_VIDEOS_FILE = (
    CHANNEL_LISTS
    / "all_identification"
    / "identification_vids.json"
)

IDENTIFICATION_RUNS_FILE = (
    CHANNEL_LISTS
    / "all_identification"
    / "runs_registry.json"
)

LANGUAGE_CLASSIFICATION_FILE = (
    RAW
    / "classified_channels_total.json"
)

CHANNEL_METADATA_FILE = (
    RAW
    / "channel_metadata_total.json"
)

OUTPUT_DIR = (
    SAMPLES
    / "russia"
    / "longitudinal"
)

PROVENANCE_FILE = (
    OUTPUT_DIR
    / "channel_sample_provenance.csv"
)

SUMMARY_FILE = (
    OUTPUT_DIR
    / "channel_sample_provenance_summary.json"
)

ISSUES_FILE = (
    OUTPUT_DIR
    / "channel_sample_provenance_issues.csv"
)

ELIGIBLE_CHANNELS_FILE = (
    OUTPUT_DIR
    / "eligible_channels_current.json"
)

# Identification videos referenced by identification_vids.json but not found
# with a valid published_at in MAIN_VIDEO_FILE are written here (video_id,
# channel_id) so their metadata can be collected separately. Written whenever
# such videos exist, regardless of DRY_RUN or FAIL_ON_MISSING_...METADATA.
MISSING_IDENTIFICATION_METADATA_FILE = (
    OUTPUT_DIR
    / "identification_videos_missing_metadata.json"
)

READ_CHUNK_SIZE = 50_000

# First run with True. Set to False after checking the printed overview.
DRY_RUN = False

# If False, an existing provenance output cannot be replaced accidentally.
OVERWRITE_EXISTING = False

# Missing identification-video metadata prevents reliable assignment of the
# first identification date. Only videos belonging to channels relevant to
# the current analysis (German, subscribers > MIN_SUBSCRIBERS) can trigger
# this; missing metadata from irrelevant channels never blocks the run.
# Keep this strict unless missing cases have been investigated explicitly.
FAIL_ON_MISSING_IDENTIFICATION_VIDEO_METADATA = False


# =============================================================================
# GENERAL HELPERS
# =============================================================================

def require_columns(
    df: pd.DataFrame,
    required: set[str],
    source_name: str,
) -> None:
    """Raise a readable error when required input columns are absent."""
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"{source_name} is missing columns: {sorted(missing)}"
        )


def ensure_unique(
    df: pd.DataFrame,
    key: str,
    source_name: str,
) -> None:
    """Ensure that a supposed key is unique."""
    duplicated = df.loc[df[key].duplicated(keep=False), key]
    if not duplicated.empty:
        examples = duplicated.astype(str).head(10).tolist()
        raise ValueError(
            f"{source_name} contains duplicate {key} values. "
            f"Examples: {examples}"
        )


def as_utc(
    values: pd.Series,
) -> pd.Series:
    """Parse timestamps and normalize them to UTC."""
    return pd.to_datetime(
        values,
        utc=True,
        errors="coerce",
    )


def read_json_records(
    path: Path,
) -> list[dict]:
    """Read a regular JSON file expected to contain a list of dictionaries."""
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(
            f"{path} must contain a JSON list, found {type(data).__name__}."
        )

    if data and not isinstance(data[0], dict):
        raise ValueError(
            f"{path} must contain a list of JSON objects."
        )

    return data


def read_json_object(
    path: Path,
) -> dict:
    """Read a regular JSON file expected to contain a dictionary."""
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(
            f"{path} must contain a JSON object, "
            f"found {type(data).__name__}."
        )

    return data


def read_discovered_channels(
    path: Path,
) -> pd.DataFrame:
    """Read the JSON list of discovered channel IDs."""
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(
            f"{path} must contain a JSON list of channel IDs."
        )

    channels = pd.DataFrame(
        {"channel_id": pd.Series(data, dtype="string")}
    )

    if channels["channel_id"].isna().any():
        raise ValueError(
            f"{path} contains missing channel IDs."
        )

    ensure_unique(
        channels,
        "channel_id",
        "discovered-channel file",
    )

    return channels


def iter_main_video_chunks(
    path: Path,
    chunk_size: int,
) -> Iterator[pd.DataFrame]:
    """
    Yield chunks from JSONL or a regular JSON list.

    JSONL is strongly recommended for the large MAIN_VIDEO_FILE.
    """
    if path.suffix.lower() == ".jsonl":
        yield from pd.read_json(
            path,
            lines=True,
            chunksize=chunk_size,
        )
        return

    complete = pd.read_json(path)
    for start in range(0, len(complete), chunk_size):
        yield complete.iloc[start : start + chunk_size].copy()


def join_sorted_unique(
    values: pd.Series,
) -> str:
    """Join non-missing unique values in deterministic order."""
    unique_values = sorted(
        {
            str(value)
            for value in values
            if pd.notna(value) and str(value).strip()
        }
    )
    return "|".join(unique_values)


def write_json(
    data: dict | list,
    path: Path,
) -> None:
    """Write UTF-8 JSON with stable, readable formatting."""
    with path.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )


# =============================================================================
# INPUT PREPARATION
# =============================================================================

def load_language_classification(
    path: Path,
) -> pd.DataFrame:
    """Load one language-classification row per channel."""
    df = pd.read_json(path)

    require_columns(
        df,
        {"channel_id", "is_german"},
        "language-classification file",
    )

    df["channel_id"] = df["channel_id"].astype("string")
    ensure_unique(
        df,
        "channel_id",
        "language-classification file",
    )

    optional_columns = [
        "german_ratio",
        "defaultLanguage",
        "country",
    ]
    for column in optional_columns:
        if column not in df.columns:
            df[column] = pd.NA

    return df[
        [
            "channel_id",
            "is_german",
            "german_ratio",
            "defaultLanguage",
            "country",
        ]
    ].rename(
        columns={
            "defaultLanguage": "default_language",
            "country": "classification_country",
        }
    )


def load_channel_metadata(
    path: Path,
) -> pd.DataFrame:
    """Load channel metadata needed for eligibility and creation dates."""
    df = pd.read_json(path)

    require_columns(
        df,
        {
            "channel_id",
            "subscribers",
            "published_at",
        },
        "channel-metadata file",
    )

    df["channel_id"] = df["channel_id"].astype("string")
    ensure_unique(
        df,
        "channel_id",
        "channel-metadata file",
    )

    optional_columns = [
        "title",
        "hidden_subscriber_count",
        "country",
        "video_count",
    ]
    for column in optional_columns:
        if column not in df.columns:
            df[column] = pd.NA

    df["subscribers"] = pd.to_numeric(
        df["subscribers"],
        errors="coerce",
    ).astype("Int64")

    df["video_count"] = pd.to_numeric(
        df["video_count"],
        errors="coerce",
    ).astype("Int64")

    df["channel_created_at"] = as_utc(
        df["published_at"]
    )

    return df[
        [
            "channel_id",
            "title",
            "subscribers",
            "hidden_subscriber_count",
            "channel_created_at",
            "country",
            "video_count",
        ]
    ].rename(
        columns={
            "title": "channel_title",
            "country": "metadata_country",
        }
    )


def load_and_validate_identification_videos(
    path: Path,
    run_registry: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load identification videos and normalize their found_by entries.

    Returns
    -------
    videos:
        One row per identification video.
    discoveries:
        One row per video × run × query combination.
    """
    records = read_json_records(path)
    videos = pd.DataFrame(records)

    require_columns(
        videos,
        {"video_id", "channel_id", "found_by"},
        "identification-video file",
    )

    videos["video_id"] = videos["video_id"].astype("string")
    videos["channel_id"] = videos["channel_id"].astype("string")
    ensure_unique(
        videos,
        "video_id",
        "identification-video file",
    )

    discovery_rows: list[dict] = []
    malformed_found_by: list[str] = []

    for row in videos.itertuples(index=False):
        found_by = row.found_by

        if not isinstance(found_by, list) or not found_by:
            malformed_found_by.append(str(row.video_id))
            continue

        for discovery in found_by:
            if not isinstance(discovery, dict):
                malformed_found_by.append(str(row.video_id))
                continue

            run_id = str(discovery.get("run_id", "")).strip()
            query = str(discovery.get("query", "")).strip()

            if not run_id or not query:
                malformed_found_by.append(str(row.video_id))
                continue

            if run_id not in run_registry:
                raise ValueError(
                    f"Identification video {row.video_id} references "
                    f"unknown run_id {run_id}."
                )

            registered_queries = {
                str(value)
                for value in run_registry[run_id].get("queries", [])
            }
            if query not in registered_queries:
                raise ValueError(
                    f"Query {query!r} for video {row.video_id} is not "
                    f"registered for run {run_id}."
                )

            discovery_rows.append(
                {
                    "video_id": str(row.video_id),
                    "channel_id": str(row.channel_id),
                    "run_id": run_id,
                    "query": query,
                }
            )

    if malformed_found_by:
        examples = malformed_found_by[:10]
        raise ValueError(
            "Malformed or empty found_by entries detected. "
            f"Example video IDs: {examples}"
        )

    discoveries = pd.DataFrame(discovery_rows)
    if discoveries.empty:
        raise ValueError(
            "No valid identification discoveries were found."
        )

    discoveries = discoveries.drop_duplicates(
        ["video_id", "channel_id", "run_id", "query"]
    )

    return (
        videos[["video_id", "channel_id"]].copy(),
        discoveries,
    )


# =============================================================================
# MAIN-VIDEO SCAN
# =============================================================================

def scan_main_video_file(
    main_video_file: Path,
    discovered_channel_ids: set[str],
    identification_video_ids: set[str],
    chunk_size: int,
) -> tuple[pd.Series, pd.DataFrame, dict]:
    """
    Scan MAIN_VIDEO_FILE once.

    The function obtains:
    - the earliest observed publication date per discovered channel, and
    - metadata for all identification videos.
    """
    chunk_minima: list[pd.Series] = []
    identification_matches: list[pd.DataFrame] = []

    total_rows = 0
    invalid_dates = 0
    relevant_rows = 0

    for chunk_number, chunk in enumerate(
        iter_main_video_chunks(
            main_video_file,
            chunk_size,
        ),
        start=1,
    ):
        require_columns(
            chunk,
            {"video_id", "channel_id", "published_at"},
            f"MAIN_VIDEO_FILE chunk {chunk_number}",
        )

        chunk = chunk[
            ["video_id", "channel_id", "published_at"]
        ].copy()

        chunk["video_id"] = chunk["video_id"].astype("string")
        chunk["channel_id"] = chunk["channel_id"].astype("string")
        chunk["published_at"] = as_utc(chunk["published_at"])

        total_rows += len(chunk)
        invalid_dates += int(chunk["published_at"].isna().sum())

        relevant = chunk.loc[
            chunk["channel_id"].isin(discovered_channel_ids)
        ].dropna(
            subset=["channel_id", "published_at"]
        )

        relevant_rows += len(relevant)

        if not relevant.empty:
            chunk_minima.append(
                relevant.groupby(
                    "channel_id",
                    sort=False,
                )["published_at"].min()
            )

        identification_match = chunk.loc[
            chunk["video_id"].isin(identification_video_ids)
        ].dropna(
            subset=["video_id", "channel_id", "published_at"]
        )

        if not identification_match.empty:
            identification_matches.append(
                identification_match
            )

        print(
            f"MAIN_VIDEO_FILE chunk {chunk_number}: "
            f"{len(chunk):,} rows, "
            f"{len(relevant):,} discovered-channel videos, "
            f"{len(identification_match):,} identification videos"
        )

    if not chunk_minima:
        first_observed = pd.Series(
            dtype="datetime64[ns, UTC]",
            name="first_observed_video_date",
        )
    else:
        first_observed = (
            pd.concat(chunk_minima)
            .groupby(level=0)
            .min()
            .rename("first_observed_video_date")
        )

    if not identification_matches:
        identification_metadata = pd.DataFrame(
            columns=[
                "video_id",
                "channel_id",
                "published_at",
            ]
        )
    else:
        identification_metadata = pd.concat(
            identification_matches,
            ignore_index=True,
        )

        duplicate_counts = (
            identification_metadata
            .groupby("video_id", sort=False)
            .agg(
                channel_count=("channel_id", "nunique"),
                date_count=("published_at", "nunique"),
            )
        )

        conflicting = duplicate_counts.loc[
            duplicate_counts["channel_count"].gt(1)
            | duplicate_counts["date_count"].gt(1)
        ]

        if not conflicting.empty:
            raise ValueError(
                "Conflicting duplicate identification-video metadata "
                f"found for {len(conflicting):,} video IDs. Examples: "
                f"{conflicting.index.astype(str).tolist()[:10]}"
            )

        identification_metadata = (
            identification_metadata
            .drop_duplicates("video_id", keep="first")
        )

    scan_summary = {
        "main_video_rows": int(total_rows),
        "main_video_rows_with_invalid_date": int(invalid_dates),
        "discovered_channel_video_rows": int(relevant_rows),
        "channels_with_observed_video": int(len(first_observed)),
        "identification_videos_matched": int(
            identification_metadata["video_id"].nunique()
        ),
    }

    return (
        first_observed,
        identification_metadata,
        scan_summary,
    )


# =============================================================================
# IDENTIFICATION PROVENANCE
# =============================================================================

def determine_relevant_channel_ids(
    language: pd.DataFrame,
    metadata: pd.DataFrame,
) -> set[str]:
    """
    Determine channels relevant to the current analysis threshold.

    Relevance mirrors the eligibility logic used later in
    build_channel_table: German-language channels with subscribers strictly
    greater than MIN_SUBSCRIBERS. This is computed early so that missing
    identification-video metadata from irrelevant channels does not block
    the pipeline.
    """
    merged = language.merge(
        metadata,
        on="channel_id",
        how="outer",
    )

    relevant = (
        merged["is_german"].eq(True)
        & merged["subscribers"].gt(MIN_SUBSCRIBERS)
    )

    return set(
        merged.loc[relevant, "channel_id"].astype(str)
    )


def write_missing_identification_metadata(
    missing_metadata: pd.DataFrame,
) -> None:
    """
    Persist relevant identification videos without MAIN_VIDEO_FILE metadata.

    Only videos belonging to channels relevant to the current analysis
    (German, subscribers > MIN_SUBSCRIBERS) are written, since those are the
    ones worth collecting metadata for. Written unconditionally (also under
    DRY_RUN, and before any FAIL_ON_MISSING_IDENTIFICATION_VIDEO_METADATA
    error is raised). If none are missing, a stale file from a previous run
    is removed to avoid a misleading leftover.
    """
    if missing_metadata.empty:
        if MISSING_IDENTIFICATION_METADATA_FILE.exists():
            MISSING_IDENTIFICATION_METADATA_FILE.unlink()
        return

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    records = (
        missing_metadata[["video_id", "channel_id"]]
        .astype(str)
        .to_dict("records")
    )

    write_json(
        records,
        MISSING_IDENTIFICATION_METADATA_FILE,
    )

    print(
        f"Saved {len(records):,} identification videos (relevant "
        f"channels only) without MAIN_VIDEO_FILE metadata to "
        f"{MISSING_IDENTIFICATION_METADATA_FILE}"
    )


def build_identification_provenance(
    identification_videos: pd.DataFrame,
    discoveries: pd.DataFrame,
    identification_metadata: pd.DataFrame,
    relevant_channel_ids: set[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create one identification-provenance row per channel."""
    merged = identification_videos.merge(
        identification_metadata.rename(
            columns={
                "channel_id": "metadata_channel_id",
                "published_at": "identification_video_date",
            }
        ),
        on="video_id",
        how="left",
        validate="one_to_one",
    )

    channel_mismatch = (
        merged["metadata_channel_id"].notna()
        & merged["channel_id"].ne(
            merged["metadata_channel_id"]
        )
    )

    if channel_mismatch.any():
        examples = (
            merged.loc[
                channel_mismatch,
                [
                    "video_id",
                    "channel_id",
                    "metadata_channel_id",
                ],
            ]
            .head(10)
            .to_dict("records")
        )
        raise ValueError(
            "Channel IDs disagree between identification_vids and "
            f"MAIN_VIDEO_FILE. Examples: {examples}"
        )

    missing_metadata = merged.loc[
        merged["identification_video_date"].isna(),
        ["video_id", "channel_id"],
    ].copy()

    missing_metadata["channel_relevant"] = (
        missing_metadata["channel_id"].isin(
            relevant_channel_ids
        )
    )

    missing_relevant = missing_metadata.loc[
        missing_metadata["channel_relevant"],
        ["video_id", "channel_id"],
    ]

    write_missing_identification_metadata(missing_relevant)

    if (
        FAIL_ON_MISSING_IDENTIFICATION_VIDEO_METADATA
        and not missing_relevant.empty
    ):
        raise ValueError(
            f"{len(missing_relevant):,} identification videos from "
            "channels relevant to the current analysis (German, "
            f"subscribers > {MIN_SUBSCRIBERS:,}) were not found with "
            "valid metadata in MAIN_VIDEO_FILE. Examples: "
            f"{missing_relevant['video_id'].astype(str).head(10).tolist()}"
        )

    dated = merged.dropna(
        subset=["identification_video_date"]
    ).copy()

    if dated.empty:
        raise ValueError(
            "No identification video could be assigned a publication date."
        )

    dated_discoveries = discoveries.merge(
        dated[
            [
                "video_id",
                "channel_id",
                "identification_video_date",
            ]

        ],
        on=["video_id", "channel_id"],
        how="inner",
        validate="many_to_one",
    )

    first_dates = (
        dated.groupby(
            "channel_id",
            sort=False,
        )["identification_video_date"]
        .min()
        .rename("first_identification_video_date")
    )

    first_rows = dated.merge(
        first_dates,
        on="channel_id",
        how="inner",
        validate="many_to_one",
    )

    first_rows = first_rows.loc[
        first_rows["identification_video_date"].eq(
            first_rows["first_identification_video_date"]
        )
    ]

    first_discoveries = dated_discoveries.merge(
        first_dates,
        on="channel_id",
        how="inner",
        validate="many_to_one",
    )

    first_discoveries = first_discoveries.loc[
        first_discoveries[
            "identification_video_date"
        ].eq(
            first_discoveries[
                "first_identification_video_date"
            ]
        )
    ]

    basic = (
        dated.groupby(
            "channel_id",
            sort=False,
        )
        .agg(
            identification_video_count=(
                "video_id",
                "nunique",
            ),
        )
        .join(first_dates)
    )

    first_video_ids = (
        first_rows.groupby(
            "channel_id",
            sort=False,
        )["video_id"]
        .agg(join_sorted_unique)
        .rename("first_identification_video_ids")
    )

    first_queries = (
        first_discoveries.groupby(
            "channel_id",
            sort=False,
        )["query"]
        .agg(join_sorted_unique)
        .rename("first_identification_queries")
    )

    first_run_ids = (
        first_discoveries.groupby(
            "channel_id",
            sort=False,
        )["run_id"]
        .agg(join_sorted_unique)
        .rename("first_identification_run_ids")
    )

    all_queries = (
        dated_discoveries.groupby(
            "channel_id",
            sort=False,
        )["query"]
        .agg(join_sorted_unique)
        .rename("identification_queries")
    )

    query_count = (
        dated_discoveries.groupby(
            "channel_id",
            sort=False,
        )["query"]
        .nunique()
        .rename("identification_query_count")
    )

    provenance = (
        basic
        .join(first_video_ids)
        .join(first_queries)
        .join(first_run_ids)
        .join(all_queries)
        .join(query_count)
        .reset_index()
    )

    return provenance, missing_metadata


# =============================================================================
# CHANNEL TABLE
# =============================================================================

def classify_channel_type(
    channels: pd.DataFrame,
    reference: pd.Timestamp,
) -> pd.Series:
    """Assign mutually exclusive channel types."""
    result = pd.Series(
        "unclassified_missing_dates",
        index=channels.index,
        dtype="string",
    )

    has_dates = (
        channels["first_observed_video_date"].notna()
        & channels["first_identification_video_date"].notna()
    )

    keyword_before = (
        has_dates
        & channels["first_identification_video_date"].lt(
            reference
        )
    )

    active_before_keyword_after = (
        has_dates
        & channels["first_observed_video_date"].lt(
            reference
        )
        & channels["first_identification_video_date"].ge(
            reference
        )
    )

    first_active_after = (
        has_dates
        & channels["first_observed_video_date"].ge(
            reference
        )
        & channels["first_identification_video_date"].ge(
            reference
        )
    )

    result.loc[keyword_before] = (
        "keyword_before_reference"
    )
    result.loc[active_before_keyword_after] = (
        "active_before_keyword_after"
    )
    result.loc[first_active_after] = (
        "first_active_after_reference"
    )

    return result


def build_channel_table(
    discovered: pd.DataFrame,
    language: pd.DataFrame,
    metadata: pd.DataFrame,
    first_observed: pd.Series,
    identification_provenance: pd.DataFrame,
    reference: pd.Timestamp,
) -> pd.DataFrame:
    """Merge all channel-level sources and create analysis flags."""
    channels = discovered.merge(
        language,
        on="channel_id",
        how="left",
        validate="one_to_one",
    )

    channels = channels.merge(
        metadata,
        on="channel_id",
        how="left",
        validate="one_to_one",
    )

    channels = channels.merge(
        first_observed.reset_index(),
        on="channel_id",
        how="left",
        validate="one_to_one",
    )

    channels = channels.merge(
        identification_provenance,
        on="channel_id",
        how="left",
        validate="one_to_one",
    )

    channels["language_classification_available"] = (
        channels["is_german"].notna()
    )

    channels["metadata_available"] = (
        channels["channel_created_at"].notna()
        | channels["subscribers"].notna()
    )

    channels["subscriber_count_available"] = (
        channels["subscribers"].notna()
    )

    channels["eligible_german"] = (
        channels["is_german"].eq(True)
    )

    thresholds = sorted(
        set(REUSABLE_SUBSCRIBER_THRESHOLDS)
        | {MIN_SUBSCRIBERS}
    )

    for threshold in thresholds:
        label = f"{threshold // 1_000}k"
        channels[f"eligible_{label}"] = (
            channels["eligible_german"]
            & channels["subscribers"].gt(threshold)
        )

    current_label = (
        f"eligible_{MIN_SUBSCRIBERS // 1_000}k"
    )

    channels["eligible_current_analysis"] = (
        channels[current_label]
    )

    channels["active_before_reference"] = (
        channels["first_observed_video_date"].lt(
            reference
        )
    )

    channels["identifiable_before_reference"] = (
        channels["first_identification_video_date"].lt(
            reference
        )
    )

    channels["created_before_reference"] = (
        channels["channel_created_at"].lt(
            reference
        )
    )

    channels["channel_type"] = classify_channel_type(
        channels,
        reference,
    )

    type_labels = {
        "keyword_before_reference": (
            "vor Referenzdatum auffindbar"
        ),
        "active_before_keyword_after": (
            "vorher aktiv, erst danach auffindbar"
        ),
        "first_active_after_reference": (
            "erst nach Referenzdatum beobachtet"
        ),
        "unclassified_missing_dates": (
            "nicht klassifizierbar: fehlende Datumsangabe"
        ),
    }

    channels["channel_type_label"] = (
        channels["channel_type"].map(type_labels)
    )

    # Integrity flags
    channels["issue_missing_language_classification"] = (
        ~channels["language_classification_available"]
    )

    channels["issue_missing_channel_metadata"] = (
        ~channels["metadata_available"]
    )

    channels["issue_missing_first_observed_video"] = (
        channels["first_observed_video_date"].isna()
    )

    channels["issue_missing_identification_date"] = (
        channels["first_identification_video_date"].isna()
    )

    channels["issue_identification_before_first_observed"] = (
        channels["first_identification_video_date"].notna()
        & channels["first_observed_video_date"].notna()
        & channels["first_identification_video_date"].lt(
            channels["first_observed_video_date"]
        )
    )

    channels["issue_observed_before_channel_creation"] = (
        channels["first_observed_video_date"].notna()
        & channels["channel_created_at"].notna()
        & channels["first_observed_video_date"].lt(
            channels["channel_created_at"]
        )
    )

    return channels


def build_issues_table(
    channels: pd.DataFrame,
) -> pd.DataFrame:
    """Return one row per channel with at least one integrity issue."""
    issue_columns = [
        column
        for column in channels.columns
        if column.startswith("issue_")
    ]

    issue_mask = channels[issue_columns].any(axis=1)

    columns = [
        "channel_id",
        "channel_title",
        "is_german",
        "subscribers",
        "eligible_current_analysis",
        "channel_created_at",
        "first_observed_video_date",
        "first_identification_video_date",
        "channel_type",
        *issue_columns,
    ]

    return channels.loc[
        issue_mask,
        columns,
    ].copy()


# =============================================================================
# REPORTING AND OUTPUT
# =============================================================================

def counts_by_type(
    channels: pd.DataFrame,
    mask: pd.Series,
) -> dict[str, int]:
    """Return stable channel-type counts for a subset."""
    counts = (
        channels.loc[mask, "channel_type"]
        .value_counts(dropna=False)
        .sort_index()
    )
    return {
        str(key): int(value)
        for key, value in counts.items()
    }


def create_summary(
    channels: pd.DataFrame,
    issues: pd.DataFrame,
    missing_identification_metadata: pd.DataFrame,
    identification_videos_total: int,
    scan_summary: dict,
    run_registry: dict,
) -> dict:
    """Create a machine-readable audit summary."""
    german = channels["eligible_german"]
    eligible = channels["eligible_current_analysis"]

    run_starts = [
        value.get("search_start")
        for value in run_registry.values()
        if value.get("search_start")
    ]
    run_ends = [
        value.get("search_end")
        for value in run_registry.values()
        if value.get("search_end")
    ]

    reusable_counts = {}
    for threshold in sorted(
        set(REUSABLE_SUBSCRIBER_THRESHOLDS)
        | {MIN_SUBSCRIBERS}
    ):
        column = f"eligible_{threshold // 1_000}k"
        reusable_counts[column] = int(
            channels[column].sum()
        )

    return {
        "analysis_id": ANALYSIS_ID,
        "created_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "configuration": {
            "reference_date": REFERENCE_DATE,
            "minimum_subscribers_strictly_greater_than": (
                MIN_SUBSCRIBERS
            ),
            "reusable_subscriber_thresholds": list(
                sorted(REUSABLE_SUBSCRIBER_THRESHOLDS)
            ),
            "main_video_file": str(MAIN_VIDEO_FILE),
        },
        "search_registry": {
            "runs": int(len(run_registry)),
            "earliest_search_start": (
                min(run_starts) if run_starts else None
            ),
            "latest_search_end_exclusive": (
                max(run_ends) if run_ends else None
            ),
        },
        "counts": {
            "discovered_channels": int(len(channels)),
            "channels_with_language_classification": int(
                channels[
                    "language_classification_available"
                ].sum()
            ),
            "german_language_channels": int(german.sum()),
            "german_channels_with_metadata": int(
                (
                    german
                    & channels["metadata_available"]
                ).sum()
            ),
            **reusable_counts,
            "eligible_current_analysis": int(
                eligible.sum()
            ),
            "channels_with_integrity_issue": int(
                len(issues)
            ),
            "eligible_channels_with_integrity_issue": int(
                issues[
                    "eligible_current_analysis"
                ].sum()
            ),
            "identification_videos_total": int(
                identification_videos_total
            ),
            "identification_videos_without_metadata_total": int(
                len(missing_identification_metadata)
            ),
            "identification_videos_without_metadata_relevant": int(
                missing_identification_metadata[
                    "channel_relevant"
                ].sum()
            ),
        },
        "channel_types_all_discovered": counts_by_type(
            channels,
            pd.Series(
                True,
                index=channels.index,
            ),
        ),
        "channel_types_current_analysis": counts_by_type(
            channels,
            eligible,
        ),
        "main_video_scan": scan_summary,
    }


def print_overview(
    summary: dict,
) -> None:
    """Print the most important audit statistics."""
    counts = summary["counts"]

    print("\n" + "=" * 72)
    print("CHANNEL SAMPLE PROVENANCE")
    print("=" * 72)
    print(f"Analysis ID: {ANALYSIS_ID}")
    print(f"Reference date: {REFERENCE_DATE}")
    print(
        "Subscriber rule: subscribers > "
        f"{MIN_SUBSCRIBERS:,}"
    )
    print("-" * 72)
    print(
        f"Discovered channels: "
        f"{counts['discovered_channels']:,}"
    )
    print(
        f"With language classification: "
        f"{counts['channels_with_language_classification']:,}"
    )
    print(
        f"German-language channels: "
        f"{counts['german_language_channels']:,}"
    )
    print(
        f"German channels with metadata: "
        f"{counts['german_channels_with_metadata']:,}"
    )

    for threshold in sorted(
        set(REUSABLE_SUBSCRIBER_THRESHOLDS)
        | {MIN_SUBSCRIBERS}
    ):
        key = f"eligible_{threshold // 1_000}k"
        print(
            f"German channels above {threshold:,}: "
            f"{counts[key]:,}"
        )

    print(
        f"Current analysis channels: "
        f"{counts['eligible_current_analysis']:,}"
    )

    print("\nCurrent-analysis channels by type:")
    for channel_type, count in (
        summary["channel_types_current_analysis"].items()
    ):
        print(f"  {channel_type}: {count:,}")

    print("\nIntegrity:")
    print(
        f"  Channels with an issue: "
        f"{counts['channels_with_integrity_issue']:,}"
    )
    print(
        f"  Eligible channels with an issue: "
        f"{counts['eligible_channels_with_integrity_issue']:,}"
    )
    print(
        f"  Identification videos total: "
        f"{counts['identification_videos_total']:,}"
    )
    print(
        f"  Identification videos without metadata (total): "
        f"{counts['identification_videos_without_metadata_total']:,}"
    )
    print(
        f"  ...of which from relevant channels (German, > "
        f"{MIN_SUBSCRIBERS:,} subscribers): "
        f"{counts['identification_videos_without_metadata_relevant']:,}"
    )
    print("=" * 72)


def save_outputs(
    channels: pd.DataFrame,
    issues: pd.DataFrame,
    summary: dict,
) -> None:
    """Persist all provenance outputs after overwrite protection."""
    output_paths = [
        PROVENANCE_FILE,
        SUMMARY_FILE,
        ISSUES_FILE,
        ELIGIBLE_CHANNELS_FILE,
    ]

    existing = [
        path
        for path in output_paths
        if path.exists()
    ]

    if existing and not OVERWRITE_EXISTING:
        formatted = "\n".join(
            f"  - {path}"
            for path in existing
        )
        raise FileExistsError(
            "Output files already exist and "
            "OVERWRITE_EXISTING=False:\n"
            f"{formatted}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    channels.to_csv(
        PROVENANCE_FILE,
        index=False,
        date_format="%Y-%m-%dT%H:%M:%SZ",
    )

    issues.to_csv(
        ISSUES_FILE,
        index=False,
        date_format="%Y-%m-%dT%H:%M:%SZ",
    )

    write_json(
        summary,
        SUMMARY_FILE,
    )

    eligible_channel_ids = (
        channels.loc[
            channels["eligible_current_analysis"],
            "channel_id",
        ]
        .astype(str)
        .sort_values()
        .tolist()
    )

    write_json(
        eligible_channel_ids,
        ELIGIBLE_CHANNELS_FILE,
    )

    print("\nSaved:")
    for path in output_paths:
        print(f"  {path}")


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    reference = pd.Timestamp(REFERENCE_DATE)
    if reference.tzinfo is None:
        reference = reference.tz_localize("UTC")
    else:
        reference = reference.tz_convert("UTC")

    required_files = [
        DISCOVERED_CHANNELS_FILE,
        IDENTIFICATION_VIDEOS_FILE,
        IDENTIFICATION_RUNS_FILE,
        LANGUAGE_CLASSIFICATION_FILE,
        CHANNEL_METADATA_FILE,
        MAIN_VIDEO_FILE,
    ]

    missing_files = [
        path
        for path in required_files
        if not path.exists()
    ]

    if missing_files:
        formatted = "\n".join(
            f"  - {path}"
            for path in missing_files
        )
        raise FileNotFoundError(
            "Required input files are missing:\n"
            f"{formatted}"
        )

    print("Loading discovered channels.")
    discovered = read_discovered_channels(
        DISCOVERED_CHANNELS_FILE
    )

    print("Loading language classifications.")
    language = load_language_classification(
        LANGUAGE_CLASSIFICATION_FILE
    )

    print("Loading channel metadata.")
    metadata = load_channel_metadata(
        CHANNEL_METADATA_FILE
    )

    print("Loading and validating identification registry.")
    run_registry = read_json_object(
        IDENTIFICATION_RUNS_FILE
    )

    print("Loading and validating identification videos.")
    (
        identification_videos,
        discoveries,
    ) = load_and_validate_identification_videos(
        IDENTIFICATION_VIDEOS_FILE,
        run_registry,
    )

    discovered_ids = set(
        discovered["channel_id"].astype(str)
    )

    identification_channel_ids = set(
        identification_videos["channel_id"].astype(str)
    )

    if identification_channel_ids != discovered_ids:
        missing_identification = (
            discovered_ids - identification_channel_ids
        )
        unexpected_identification = (
            identification_channel_ids - discovered_ids
        )

        raise ValueError(
            "Discovered-channel IDs and identification-video channel IDs "
            "do not match. "
            f"Without identification video: "
            f"{len(missing_identification):,}; "
            f"unexpected: {len(unexpected_identification):,}."
        )

    print("Scanning MAIN_VIDEO_FILE.")
    (
        first_observed,
        identification_metadata,
        scan_summary,
    ) = scan_main_video_file(
        MAIN_VIDEO_FILE,
        discovered_channel_ids=discovered_ids,
        identification_video_ids=set(
            identification_videos[
                "video_id"
            ].astype(str)
        ),
        chunk_size=READ_CHUNK_SIZE,
    )

    print("Determining channels relevant to the current analysis.")
    relevant_channel_ids = determine_relevant_channel_ids(
        language,
        metadata,
    )

    print("Building identification provenance.")
    (
        identification_provenance,
        missing_identification_metadata,
    ) = build_identification_provenance(
        identification_videos,
        discoveries,
        identification_metadata,
        relevant_channel_ids,
    )

    print("Building channel-level provenance table.")
    channels = build_channel_table(
        discovered,
        language,
        metadata,
        first_observed,
        identification_provenance,
        reference,
    )

    issues = build_issues_table(channels)

    summary = create_summary(
        channels,
        issues,
        missing_identification_metadata,
        len(identification_videos),
        scan_summary,
        run_registry,
    )

    print_overview(summary)

    if DRY_RUN:
        print(
            "\nDRY RUN: no files were written. "
            "If the counts and channel types are plausible, "
            "set DRY_RUN=False."
        )
        return

    save_outputs(
        channels,
        issues,
        summary,
    )


if __name__ == "__main__":
    main()
"""
Build the channel-level provenance table for a keyword-search-based YouTube
sample - the central "Sample-Zugehoerigkeits"-Skript aus COMPLETE_PROCESS.md
Schritt 1.

The script combines, entirely from the live `video_registry.sqlite` store
(no JSON intermediate files, no one-off migration - see the module docstring
of `youtube_code.store.video_registry`):

1. channels discovered through keyword searches (video_registry.get_search_provenance),
2. the videos through which each channel was discovered (same call),
3. channel-language classifications (video_registry.get_language_classification),
4. channel metadata (video_registry.get_channels), and
5. the first-observed video date per channel and the publish date of every
   identification video (video_registry.first_observed_dates / get_video_rows).

PROVENANCE_FILE only ever contains channels that actually enter the current
analysis (eligible_current_analysis == True). Every discovered channel -
including ineligible ones - still flows into ISSUES_FILE/SUMMARY_FILE, so
integrity checks and audit counts keep covering the full discovery set even
though the eligibility threshold could still change later.

QUERY_FILTER / SEARCH_PERIOD_FILTER select which part of the store's search
history counts as "the sample" for this run - e.g. all channels found via
"CDU" or "SPD" within 2021-02-24..2022-02-23. ANALYSIS_ID names the run and
therefore its output subfolder (SAMPLES / ANALYSIS_ID), so a run with a
different filter/ANALYSIS_ID (e.g. a CDU/SPD sample) never overwrites an
existing one (e.g. the Russia/Ukraine longitudinal sample).

Important date definitions
--------------------------
channel_created_at:
    The creation timestamp reported by the YouTube Channels API.

first_observed_video_date:
    The earliest video for the channel in video_registry.sqlite. Since the
    registry is fed live by the collection scripts, this reflects whatever
    has been fetched for the channel so far, not necessarily its first-ever
    upload.

first_identification_video_date:
    The earliest publication date among the videos returned by the keyword
    searches selected via QUERY_FILTER/SEARCH_PERIOD_FILTER. This is based
    on the video's publication date, not the date on which the API search
    was executed.

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

import pandas as pd

from youtube_code.config import SAMPLES
from youtube_code.store import video_registry


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

# Which slice of the store's search history defines "the sample" for this
# run. None = no restriction on that dimension.
#   QUERY_FILTER = ["CDU", "SPD"]                          -> only these queries
#   SEARCH_PERIOD_FILTER = ("2021-02-24", "2022-02-23")    -> only runs whose
#       full search window (search_runs.search_start/search_end) lies within
#       this period (same semantics as video_identification.select_run_ids)
QUERY_FILTER: list[str] | None = None
SEARCH_PERIOD_FILTER: tuple[str, str] | None = None

OUTPUT_DIR = SAMPLES / ANALYSIS_ID

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

# Identification videos selected by QUERY_FILTER/SEARCH_PERIOD_FILTER but not
# found with a valid published_at in video_registry.sqlite (videos table) are
# written here (video_id, channel_id) so their metadata can be collected
# separately. Written whenever such videos exist, regardless of DRY_RUN or
# FAIL_ON_MISSING_IDENTIFICATION_VIDEO_METADATA.
MISSING_IDENTIFICATION_METADATA_FILE = (
    OUTPUT_DIR
    / "identification_videos_missing_metadata.json"
)

# First run with True. Set to False after checking the printed overview.
DRY_RUN = False

# If False, an existing provenance output cannot be replaced accidentally.
OVERWRITE_EXISTING = True

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
    """
    Parse timestamps and normalize them to UTC.

    format="ISO8601" is required here: video_registry.sqlite stores
    published_at in two ISO-8601 variants depending on the fetch source
    (with and without fractional seconds, e.g. "...T13:00:00Z" vs.
    "...T12:00:00.000Z"). Without an explicit format, pandas infers a single
    format from the first values of a large Series and silently coerces
    every row that does not match that exact format to NaT (even though it
    is a valid, just differently-formatted, timestamp) - this previously
    caused a handful of videos with valid published_at values to be
    misreported as "missing metadata".
    """
    return pd.to_datetime(
        values,
        utc=True,
        errors="coerce",
        format="ISO8601",
    )


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
# INPUT PREPARATION (all from video_registry.sqlite)
# =============================================================================

def load_search_provenance(
    queries: list[str] | None,
    search_period: tuple[str, str] | None,
) -> pd.DataFrame:
    """
    Load one row per (video_id, channel_id, run_id, query) search hit from
    the store, restricted to QUERY_FILTER/SEARCH_PERIOD_FILTER. This single
    call replaces the former DISCOVERED_CHANNELS_FILE, IDENTIFICATION_VIDEOS_FILE
    and IDENTIFICATION_RUNS_FILE (their found_by/run-registry validation is
    already enforced when video_identification.py writes to the store).
    """
    provenance = video_registry.get_search_provenance(
        queries=queries,
        search_period=search_period,
    )

    require_columns(
        provenance,
        {"video_id", "channel_id", "run_id", "query"},
        "video_registry.get_search_provenance()",
    )

    if provenance.empty:
        raise ValueError(
            "video_registry.get_search_provenance() returned no rows for "
            f"QUERY_FILTER={queries!r}, SEARCH_PERIOD_FILTER={search_period!r}."
        )

    for column in ("video_id", "channel_id", "run_id", "query"):
        provenance[column] = provenance[column].astype("string")

    missing_channel = provenance["channel_id"].isna()
    if missing_channel.any():
        examples = provenance.loc[missing_channel, "video_id"].head(10).tolist()
        raise ValueError(
            "Some search hits have no channel_id in the videos table yet "
            f"(collection incomplete). Example video IDs: {examples}"
        )

    return provenance


def load_language_classification() -> pd.DataFrame:
    """Load one language-classification row per channel from the store."""
    df = video_registry.get_language_classification()

    require_columns(
        df,
        {"channel_id", "is_german"},
        "video_registry.get_language_classification()",
    )

    df["channel_id"] = df["channel_id"].astype("string")
    ensure_unique(
        df,
        "channel_id",
        "video_registry.get_language_classification()",
    )

    return df.rename(
        columns={"country": "classification_country"}
    )[
        [
            "channel_id",
            "is_german",
            "german_ratio",
            "classification_country",
        ]
    ]


def load_channel_metadata() -> pd.DataFrame:
    """Load channel metadata needed for eligibility and creation dates."""
    df = video_registry.get_channels()

    require_columns(
        df,
        {
            "channel_id",
            "subscribers",
            "published_at",
        },
        "video_registry.get_channels()",
    )

    df["channel_id"] = df["channel_id"].astype("string")
    ensure_unique(
        df,
        "channel_id",
        "video_registry.get_channels()",
    )

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


# =============================================================================
# VIDEO-REGISTRY LOOKUP (replaces the former MAIN_VIDEO_FILE scan)
# =============================================================================

def lookup_first_observed_and_identification_dates(
    discovered_channel_ids: set[str],
    identification_video_ids: set[str],
) -> tuple[pd.Series, pd.DataFrame, dict]:
    """
    Direct SQL lookups against video_registry.sqlite instead of streaming a
    MAIN_VIDEO_FILE JSONL:

    - the earliest observed publication date per discovered channel
      (video_registry.first_observed_dates), and
    - metadata (channel_id, published_at) for all identification videos
      (video_registry.get_video_rows).
    """
    first_observed = video_registry.first_observed_dates(discovered_channel_ids)
    first_observed = as_utc(first_observed).rename("first_observed_video_date")

    identification_metadata = video_registry.get_video_rows(identification_video_ids)
    identification_metadata["video_id"] = identification_metadata["video_id"].astype("string")
    identification_metadata["channel_id"] = identification_metadata["channel_id"].astype("string")
    identification_metadata["published_at"] = as_utc(identification_metadata["published_at"])
    identification_metadata = identification_metadata.dropna(
        subset=["video_id", "channel_id", "published_at"]
    )

    ensure_unique(
        identification_metadata,
        "video_id",
        "video_registry.get_video_rows() for identification videos",
    )

    lookup_summary = {
        "discovered_channels_queried": int(len(discovered_channel_ids)),
        "channels_with_observed_video": int(len(first_observed)),
        "identification_videos_queried": int(len(identification_video_ids)),
        "identification_videos_matched": int(len(identification_metadata)),
    }

    return (
        first_observed,
        identification_metadata,
        lookup_summary,
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
    Persist relevant identification videos without video_registry metadata.

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
        f"channels only) without video_registry metadata to "
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
            "Channel IDs disagree between video_search_hits/videos and "
            f"video_registry.get_video_rows(). Examples: {examples}"
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
            "valid metadata in video_registry.sqlite. Examples: "
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
    lookup_summary: dict,
    discoveries: pd.DataFrame,
) -> dict:
    """Create a machine-readable audit summary."""
    german = channels["eligible_german"]
    eligible = channels["eligible_current_analysis"]

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
            "query_filter": QUERY_FILTER,
            "search_period_filter": (
                list(SEARCH_PERIOD_FILTER)
                if SEARCH_PERIOD_FILTER
                else None
            ),
        },
        "search_registry": {
            "runs_referenced": int(discoveries["run_id"].nunique()),
            "queries_referenced": int(discoveries["query"].nunique()),
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
        "video_registry_lookup": lookup_summary,
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
    print(f"Query filter: {QUERY_FILTER or 'alle Suchbegriffe'}")
    print(f"Search period filter: {SEARCH_PERIOD_FILTER or 'alle Laeufe'}")
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
    """
    Persist all provenance outputs after overwrite protection.

    PROVENANCE_FILE is restricted to eligible_current_analysis == True
    (the channels that actually enter the sample); ISSUES_FILE/SUMMARY_FILE/
    ELIGIBLE_CHANNELS_FILE keep covering every discovered channel.
    """
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

    channels.loc[
        channels["eligible_current_analysis"]
    ].to_csv(
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

    print("Loading search provenance from video_registry.sqlite "
          f"(QUERY_FILTER={QUERY_FILTER!r}, SEARCH_PERIOD_FILTER={SEARCH_PERIOD_FILTER!r}).")
    provenance = load_search_provenance(QUERY_FILTER, SEARCH_PERIOD_FILTER)

    discovered_ids = set(provenance["channel_id"].astype(str))
    discovered = pd.DataFrame(
        {"channel_id": pd.Series(sorted(discovered_ids), dtype="string")}
    )

    identification_videos = (
        provenance[["video_id", "channel_id"]]
        .drop_duplicates(subset="video_id")
        .reset_index(drop=True)
    )
    ensure_unique(
        identification_videos,
        "video_id",
        "video_registry.get_search_provenance() (video_id -> channel_id)",
    )

    discoveries = provenance[
        ["video_id", "channel_id", "run_id", "query"]
    ].drop_duplicates()

    print("Loading language classifications.")
    language = load_language_classification()

    print("Loading channel metadata.")
    metadata = load_channel_metadata()

    print("Looking up first-observed and identification-video dates in video_registry.sqlite.")
    (
        first_observed,
        identification_metadata,
        lookup_summary,
    ) = lookup_first_observed_and_identification_dates(
        discovered_channel_ids=discovered_ids,
        identification_video_ids=set(
            identification_videos["video_id"].astype(str)
        ),
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
        lookup_summary,
        discoveries,
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

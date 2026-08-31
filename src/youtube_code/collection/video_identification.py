"""
YouTube video identification and channel discovery script.

Searches YouTube for videos matching the configured queries within a date
range, extracts the channels behind those videos, and keeps a "found_by"
history on every video recording which run(s) discovered it.

Storage model
--------------
Everything lives in ONE consolidated project store (no more per-query
directories): all_channel_ids_discovered.json and identification_vids.json.
Provenance is tracked per video/run instead of via folder structure, so the
same video found by different queries/runs is merged, not duplicated.

Videos are stored with only video_id and channel_id (plus found_by); title,
channel title, and publish date are deliberately left out here and merged
in later from a separate metadata file/pipeline.

Each execution gets a run_id (a timestamp). For that run_id, this script
records in runs_registry.json:
  - which queries were searched
  - the searched video date range (search_start / search_end)
  - the month_interval used to chunk that range
  - the moment the run was actually executed (executed_at)
A human-readable copy of the same information is appended to
configuration.txt for quick manual review.

Both the project store and the run registry are only updated once ALL
queries for this run have completed successfully. If a query raises an
error partway through, nothing from this run is written to disk, so a
failed run never ends up half-saved or registered.

This makes it possible to later select run_ids by search term and/or by
date range and recover exactly which videos/channels they identified - see
`select_run_ids` and `filter_by_run_ids` at the bottom of this file.

Every successful run appends to the existing project store (no overwrite
prompt). To deliberately wipe the store and start over, call
`reset_project()`.

Run pattern: this script is meant to be executed directly (`python video_identification.py`),
never imported. That is why `from settings_variables import ...` below works as a bare
sibling import (Python puts the script's own directory on sys.path[0]), while
`from youtube_code... import ...` still resolves normally because that package is
importable independent of cwd.
"""

from datetime import datetime
import json
import os

from dateutil.relativedelta import relativedelta
from googleapiclient.discovery import build

from settings_variables import (
    query_list,
    target_directory,
    start_date,
    final_end_date,
    month_interval,
)
from youtube_code.utils import load_set
from youtube_code.utils.video_registry import upsert_videos as _registry_upsert
from youtube_code.config import API_KEY, API_KEY_C

YOUTUBE = build("youtube", "v3", developerKey=API_KEY)


# ---------------------------------------------------------------------------
# Run setup / configuration
# ---------------------------------------------------------------------------

def generate_run_id() -> str:
    """Create a sortable, unique identifier for this script execution."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def build_config_summary(run_id, query_list, target_directory, start_date, final_end_date, month_interval) -> str:
    return (
        f"Run ID: {run_id}\n"
        f"Query: {query_list}\n"
        f'Target directory: "{target_directory}"\n'
        f"Search from {start_date} to {final_end_date}\n"
        f"Search interval: {month_interval} month(s)\n"
        f"{'-' * 60}\n"
    )


def confirm_configuration(config_text: str) -> None:
    print(config_text)
    answer = input("Configuration correct? [y/n] ")
    if answer.strip().lower() != "y":
        print("Configuration rejected. Please check 'settings_variables.py'.")
        exit()


def append_run_to_config_log(config_path: str, config_text: str) -> None:
    """Append this run's configuration to the running log file (human-readable
    counterpart to runs_registry.json)."""
    with open(config_path, "a", encoding="utf-8") as f:
        f.write(config_text)
    print(f"Run configuration appended to {config_path}")


# ---------------------------------------------------------------------------
# Output file handling
# ---------------------------------------------------------------------------

def resolve_output_paths(target_directory: str) -> dict:
    return {
        "all_channels": os.path.join(target_directory, "all_channel_ids_discovered.json"),
        "identification_vids": os.path.join(target_directory, "identification_vids.json"),
        "config_log": os.path.join(target_directory, "configuration.txt"),
        "runs_registry": os.path.join(target_directory, "runs_registry.json"),
    }


def load_existing_data(paths: dict) -> tuple:
    """
    Always loads the existing project store, i.e. every run appends to it.
    With run_id-based provenance tracking there's no longer a meaningful
    "overwrite" choice to make on every single run - if you ever want to
    deliberately start over, call reset_project() instead (see below).
    """
    all_channel_ids = load_set(paths["all_channels"])

    if os.path.exists(paths["identification_vids"]):
        with open(paths["identification_vids"], "r", encoding="utf-8") as f:
            ident_vids = json.load(f)
    else:
        ident_vids = []

    return all_channel_ids, ident_vids


def print_project_status(all_channel_ids: set, ident_vids: list, registry: dict) -> None:
    """Quick overview of what's already in the project store, so you always
    know what this run is appending to."""
    if not ident_vids and not registry:
        print("No existing project store found - starting fresh.")
        return
    print(
        f"Existing project store: {len(ident_vids)} videos, "
        f"{len(all_channel_ids)} channels, {len(registry)} run(s) recorded so far."
    )


def save_outputs(paths: dict, all_channel_ids: set, ident_vids: list) -> None:
    with open(paths["all_channels"], "w", encoding="utf-8") as f:
        json.dump(sorted(all_channel_ids), f, indent=2, ensure_ascii=False)

    with open(paths["identification_vids"], "w", encoding="utf-8") as f:
        json.dump(ident_vids, f, indent=2, ensure_ascii=False)


def reset_project(target_directory: str) -> None:
    """
    Deliberately wipe the consolidated project store (all_channel_ids,
    identification_vids, configuration.txt, runs_registry.json). NOT called
    automatically by main() - run it explicitly if you really want to start
    over, e.g. from a Python shell:

        from video_identification import reset_project
        reset_project("/path/to/target_directory")
    """
    paths = resolve_output_paths(target_directory)
    for path in paths.values():
        if os.path.exists(path):
            os.remove(path)
    print(f"Project store at '{target_directory}' has been reset.")


# ---------------------------------------------------------------------------
# YouTube search
# ---------------------------------------------------------------------------

def search_videos_for_query(query: str, start_date, final_end_date, month_interval) -> list:
    """Query YouTube in chunks of `month_interval` months. Chunking by date
    avoids hitting the API's results cap for a single query."""
    results = []
    current_start = start_date

    while current_start < final_end_date:
        current_end = min(current_start + relativedelta(months=month_interval), final_end_date)

        published_after = current_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        published_before = current_end.strftime("%Y-%m-%dT%H:%M:%SZ")

        next_page_token = None
        while True:
            request = YOUTUBE.search().list(
                part="id,snippet",
                q=query,
                type="video",
                publishedAfter=published_after,
                publishedBefore=published_before,
                order="date",
                maxResults=50,
                pageToken=next_page_token,
                relevanceLanguage="de",
                regionCode="DE",
            )
            response = request.execute()
            results.extend(response.get("items", []))
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        current_start = current_end

    return results


def parse_video_items(items: list) -> list:
    """
    Extract only the identifying fields needed at this stage. Title,
    channel title, and publish date are intentionally NOT stored here -
    they get merged in later from a separate metadata file/pipeline.
    """
    return [
        {
            "video_id": item["id"]["videoId"],
            "channel_id": item["snippet"]["channelId"],
        }
        for item in items
    ]


# ---------------------------------------------------------------------------
# Video history tracking (run_id / query per discovery)
# ---------------------------------------------------------------------------

def update_video_history(ident_vids: list, existing_video_ids: set, videos: list, run_id: str, query: str) -> list:
    """
    Merge newly found videos into ident_vids.

    Every video carries a 'found_by' list of {run_id, query} entries, so a
    video's full discovery history is preserved across runs. New videos get
    a fresh 'found_by' list; videos seen before get this run's entry added
    (skipped if an identical entry is already present).
    """
    ident_vids_by_id = {v["video_id"]: v for v in ident_vids}

    for video in videos:
        entry = {"run_id": run_id, "query": query}

        if video["video_id"] not in existing_video_ids:
            video["found_by"] = [entry]
            ident_vids.append(video)
            ident_vids_by_id[video["video_id"]] = video
            existing_video_ids.add(video["video_id"])
        else:
            existing_video = ident_vids_by_id[video["video_id"]]
            if entry not in existing_video["found_by"]:
                existing_video["found_by"].append(entry)

    return ident_vids


def filter_by_run_ids(ident_vids: list, run_ids) -> tuple:
    """
    Select the subset of videos discovered by one or more given run_ids, and
    the channel_ids referenced by that subset.

    Example:
        with open("identification_vids.json", encoding="utf-8") as f:
            ident_vids = json.load(f)
        videos, channel_ids = filter_by_run_ids(ident_vids, {"20260615_141200"})
    """
    run_ids = set(run_ids)
    matched_videos = [
        v for v in ident_vids
        if any(entry["run_id"] in run_ids for entry in v.get("found_by", []))
    ]
    matched_channel_ids = {v["channel_id"] for v in matched_videos}
    return matched_videos, matched_channel_ids


# ---------------------------------------------------------------------------
# Run registry (structured, queryable run metadata for ~100s of runs)
# ---------------------------------------------------------------------------

def to_iso_date(value) -> str:
    """Normalize a date/datetime/ISO-string into an ISO 'YYYY-MM-DD' string."""
    if isinstance(value, str):
        return value[:10]
    return value.strftime("%Y-%m-%d")


def to_iso_datetime(value, end_of_day: bool = False) -> str:
    """
    Normalize a date/datetime/ISO-string into a comparable ISO datetime
    string. Plain dates (no time component) are expanded to the start or
    end of that day, so a date-only filter bound still compares correctly
    against full timestamps.
    """
    if isinstance(value, str):
        if "T" in value:
            return value
        return f"{value}T23:59:59" if end_of_day else f"{value}T00:00:00"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M:%S")
    suffix = "23:59:59" if end_of_day else "00:00:00"
    return f"{value.strftime('%Y-%m-%d')}T{suffix}"


def load_run_registry(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_run_registry(path: str, registry: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


def register_run(registry: dict, run_id: str, queries: list, search_start, search_end, month_interval, executed_at) -> dict:
    registry[run_id] = {
        "queries": list(queries),
        "search_start": to_iso_date(search_start),
        "search_end": to_iso_date(search_end),
        "month_interval": month_interval,
        "executed_at": to_iso_datetime(executed_at),
    }
    return registry


def select_run_ids(registry: dict, queries=None, search_period=None, execution_period=None) -> set:
    """
    Select run_ids from the run registry matching ALL given filters
    (filters are combined with AND; omit a filter to skip it).

    queries:          list of search terms - a run matches if at least one
                       of its own queries is in this list.
    search_period:    (start, end) - a run matches if its *search* date
                       range (search_start, search_end) is FULLY CONTAINED
                       within this period.
    execution_period: (start, end) - a run matches if the moment it was
                       actually executed (executed_at) is FULLY CONTAINED
                       within this period. Date-only bounds are treated as
                       whole days.

    Example:
        with open("runs_registry.json", encoding="utf-8") as f:
            registry = json.load(f)

        run_ids = select_run_ids(
            registry,
            queries=["Gaza", "Nahost-Konflikt"],
            search_period=("2023-10-01", "2023-12-31"),
        )

        with open("identification_vids.json", encoding="utf-8") as f:
            ident_vids = json.load(f)
        videos, channel_ids = filter_by_run_ids(ident_vids, run_ids)
    """
    matched = set()

    for run_id, meta in registry.items():
        if queries is not None and not set(meta["queries"]) & set(queries):
            continue

        if search_period is not None:
            period_start = to_iso_date(search_period[0])
            period_end = to_iso_date(search_period[1])
            if not (period_start <= meta["search_start"] and meta["search_end"] <= period_end):
                continue

        if execution_period is not None:
            period_start = to_iso_datetime(execution_period[0], end_of_day=False)
            period_end = to_iso_datetime(execution_period[1], end_of_day=True)
            if not (period_start <= meta["executed_at"] <= period_end):
                continue

        matched.add(run_id)

    return matched


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    run_id = generate_run_id()

    config_text = build_config_summary(
        run_id, query_list, target_directory, start_date, final_end_date, month_interval
    )
    confirm_configuration(config_text)

    os.makedirs(target_directory, exist_ok=True)
    paths = resolve_output_paths(target_directory)

    registry = load_run_registry(paths["runs_registry"])
    all_channel_ids, ident_vids = load_existing_data(paths)
    print_project_status(all_channel_ids, ident_vids, registry)

    existing_video_ids = {v["video_id"] for v in ident_vids}

    # Everything below only touches in-memory data. Nothing is written to
    # disk - and therefore this run is not recorded anywhere - unless every
    # query in query_list completes without error.
    try:
        for query in query_list:
            print(f"\nQuery: {query}")
            print(f"Full period: {start_date} to {final_end_date}")

            items = search_videos_for_query(query, start_date, final_end_date, month_interval)
            videos = parse_video_items(items)
            print(f"Videos found: {len(videos)}")

            update_video_history(ident_vids, existing_video_ids, videos, run_id, query)
            print("Video list updated.")

            # Zentrale Video-Registry mitfuehren (nur video_id/channel_id an
            # dieser Stelle - siehe Modul-Docstring; published_at/title
            # kommen spaeter per COALESCE aus der Metadaten-Pipeline dazu).
            _registry_upsert(videos)

            channel_ids = {video["channel_id"] for video in videos}
            print(f"Unique channels in this query: {len(channel_ids)}")
            print(channel_ids)
            all_channel_ids.update(channel_ids)
    except Exception as exc:
        print(f"\nError while processing query '{query}': {exc}")
        print("This run will NOT be saved or registered. Fix the issue and re-run.")
        raise

    save_outputs(paths, all_channel_ids, ident_vids)
    append_run_to_config_log(paths["config_log"], config_text)

    register_run(registry, run_id, query_list, start_date, final_end_date, month_interval, datetime.now())
    save_run_registry(paths["runs_registry"], registry)

    print(f"\nDone. Run ID for this execution: {run_id}")


if __name__ == "__main__":
    main()
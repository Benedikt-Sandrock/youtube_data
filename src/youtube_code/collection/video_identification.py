"""

ANPASSUNGEN:
- nicht jedes Mal Abfrage, ob Datei schon existiert
- abfangen, wenn ein Fehler bei der Anfrage auftritt: nicht in config/registry übernehmen, wenn Anfrage nicht gespeichert wird
- In der Video datei sollen nicht so viele Daten gespeichert werden: nur video und channel id -> Rest wird über Metadaten erfasst
- Wenn neues Skript von Claude übernommen wird, wieder month_interval Speicherung einfügen



YouTube video identification and channel discovery script.

Searches YouTube for videos matching the configured queries within a date
range, extracts the channels behind those videos, and keeps a "found_by"
history on every video recording which run(s) discovered it.

Storage model
--------------
Everything lives in ONE consolidated project store:
 all_channel_ids_discovered.json and identification_vids.json.
Provenance is tracked per video/run instead of via folder structure, so the
same video found by different queries/runs is merged, not duplicated.

Each execution gets a run_id (a timestamp). For that run_id, this script
records in runs_registry.json:
  - which queries were searched
  - the searched video date range (search_start / search_end)
  - the moment the run was actually executed (executed_at)
A human-readable copy of the same information is appended to
configuration.txt for quick manual review.

This makes it possible to later select run_ids by search term and/or by
date range and recover exactly which videos/channels they identified - see
`select_run_ids` and `filter_by_run_ids` at the bottom of this file.
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
from src.youtube_code.utils import load_set
from src.youtube_code.config import API_KEY, API_KEY_C

YOUTUBE = build("youtube", "v3", developerKey=API_KEY_C)


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


def ask_overwrite_or_append(paths: dict) -> bool:
    """Returns True if existing output files should be overwritten, False if
    new results should be appended to them."""
    existing_files = [p for p in paths.values() if os.path.exists(p)]
    if not existing_files:
        return False

    print("\nWarning: the following output files already exist:\n")
    for f in existing_files:
        print(" -", f)

    if os.path.exists(paths["config_log"]):
        print("\nPrevious runs recorded in configuration.txt:\n")
        with open(paths["config_log"], "r", encoding="utf-8") as f:
            print(f.read())

    while True:
        choice = input(
            "\n[a] append data\n"
            "[o] overwrite data\n"
            "[q] abort\n"
            "Choice: "
        ).lower()
        if choice == "a":
            return False
        if choice == "o":
            return True
        if choice == "q":
            print("Aborting.")
            exit()
        print("Invalid input.")


def load_existing_data(paths: dict, overwrite: bool):
    if overwrite:
        return set(), []

    all_channel_ids = load_set(paths["all_channels"])

    if os.path.exists(paths["identification_vids"]):
        with open(paths["identification_vids"], "r", encoding="utf-8") as f:
            ident_vids = json.load(f)
    else:
        ident_vids = []

    return all_channel_ids, ident_vids


def save_outputs(paths: dict, all_channel_ids: set, ident_vids: list) -> None:
    with open(paths["all_channels"], "w", encoding="utf-8") as f:
        json.dump(sorted(all_channel_ids), f, indent=2, ensure_ascii=False)

    with open(paths["identification_vids"], "w", encoding="utf-8") as f:
        json.dump(ident_vids, f, indent=2, ensure_ascii=False)


def reset_logs_if_overwrite(paths: dict, overwrite: bool) -> None:
    """If the channel/video stores are being reset, reset the configuration
    log and run registry too, so old run_ids referencing now-deleted data
    don't linger around."""
    if not overwrite:
        return
    open(paths["config_log"], "w", encoding="utf-8").close()
    save_run_registry(paths["runs_registry"], {})


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
    return [
        {
            "video_id": item["id"]["videoId"],
            "title": item["snippet"]["title"],
            "channel_id": item["snippet"]["channelId"],
            "channel_title": item["snippet"]["channelTitle"],
            "published_at": item["snippet"]["publishedAt"],
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


def register_run(registry: dict, run_id: str, queries: list, month_interval, search_start, search_end, executed_at) -> dict:
    registry[run_id] = {
        "queries": list(queries),
        "interval": month_interval,
        "search_start": to_iso_date(search_start),
        "search_end": to_iso_date(search_end),
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

    overwrite = ask_overwrite_or_append(paths)
    reset_logs_if_overwrite(paths, overwrite)
    append_run_to_config_log(paths["config_log"], config_text)

    registry = load_run_registry(paths["runs_registry"])
    register_run(registry, run_id, query_list, month_interval, start_date, final_end_date, datetime.now())
    save_run_registry(paths["runs_registry"], registry)

    print("Loading existing files...")
    all_channel_ids, ident_vids = load_existing_data(paths, overwrite)
    existing_video_ids = {v["video_id"] for v in ident_vids}

    for query in query_list:
        print(f"\nQuery: {query}")
        print(f"Full period: {start_date} to {final_end_date}")

        items = search_videos_for_query(query, start_date, final_end_date, month_interval)
        videos = parse_video_items(items)
        print(f"Videos found: {len(videos)}")

        update_video_history(ident_vids, existing_video_ids, videos, run_id, query)
        print("Video list updated.")

        channel_ids = {video["channel_id"] for video in videos}
        print(f"Unique channels in this query: {len(channel_ids)}")
        print(channel_ids)
        all_channel_ids.update(channel_ids)

        save_outputs(paths, all_channel_ids, ident_vids)

    print(f"\nDone. Run ID for this execution: {run_id}")


if __name__ == "__main__":
    main()
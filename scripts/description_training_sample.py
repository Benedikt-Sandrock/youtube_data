"""Create or extend a reproducible Excel sample of YouTube metadata."""

import json
import random
from pathlib import Path

import pandas as pd

from youtube_code.config import RAW, SAMPLES


DETAILED_METADATA_FILE = RAW / "video_metadata_detailed_total.jsonl"
ALL_VIDEOS_FILE = SAMPLES / "russia" / "videos_wo_shorts_russia_ukraine.json"
OUTPUT_DIRECTORY = SAMPLES / "russia"
METADATA_FIELDS = ["title", "description"]
N = 200
SEED_NUMBER = 42


def load_json_list(path: Path) -> list[dict]:
    """Load a JSON file and verify that it contains a list of dictionaries."""
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError(f"{path} must contain a JSON list of dictionaries.")
    return data


def normalize_metadata_fields(metadata_fields: list[str]) -> list[str]:
    """Validate field names and remove duplicates while preserving their order."""
    fields = []
    for field in metadata_fields:
        field = field.strip()
        if field and field != "video_id" and field not in fields:
            fields.append(field)

    if not fields:
        raise ValueError("At least one metadata field must be specified.")
    return fields


def find_metadata_in_jsonl(
    path: Path,
    target_video_ids: set[str],
    metadata_fields: list[str],
) -> dict[str, dict]:
    """Read a JSONL file once and return requested fields for target IDs."""
    records_by_id = {}
    if not target_video_ids:
        return records_by_id

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            try:
                video = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON in {path}, line {line_number}."
                ) from error

            video_id = video.get("video_id")
            if video_id is None:
                continue

            video_id = str(video_id)
            if video_id in target_video_ids and video_id not in records_by_id:
                records_by_id[video_id] = {
                    "video_id": video_id,
                    **{field: video.get(field) for field in metadata_fields},
                }

                if len(records_by_id) == len(target_video_ids):
                    break

    return records_by_id


def create_description_sample(
    detailed_metadata_path: Path,
    all_videos_path: Path,
    output_directory: Path,
    n: int,
    seed_number: int,
    metadata_fields: list[str] | None = None,
) -> Path:
    """Create an Excel sample or append newly found sampled video IDs to it."""
    if n < 1:
        raise ValueError("N must be at least 1.")
    metadata_fields = normalize_metadata_fields(metadata_fields or METADATA_FIELDS)

    all_videos = load_json_list(all_videos_path)
    # Sample unique video IDs even if the source file contains duplicates.
    candidate_ids = list(
        dict.fromkeys(
            str(video["video_id"])
            for video in all_videos
            if video.get("video_id") is not None
        )
    )

    if n > len(candidate_ids):
        raise ValueError(
            f"N={n} exceeds the number of videos with a video_id "
            f"({len(candidate_ids)}) in {all_videos_path}."
        )

    rng = random.Random(seed_number)
    sampled_video_ids = rng.sample(candidate_ids, n)

    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"description_training_sample_{seed_number}.xlsx"

    if output_path.exists():
        existing_df = pd.read_excel(output_path, dtype={"video_id": str})
        if "video_id" not in existing_df.columns:
            raise ValueError(f"Existing output file {output_path} has no video_id column.")
        existing_ids = set(existing_df["video_id"].dropna().astype(str))
        existing_df.loc[existing_df["video_id"].notna(), "video_id"] = (
            existing_df.loc[existing_df["video_id"].notna(), "video_id"].astype(str)
        )
    else:
        existing_df = pd.DataFrame(columns=["video_id", *metadata_fields])
        existing_ids = set()

    new_sampled_ids = [
        video_id for video_id in sampled_video_ids if video_id not in existing_ids
    ]
    records_by_id = find_metadata_in_jsonl(
        detailed_metadata_path,
        set(new_sampled_ids),
        metadata_fields,
    )

    # Preserve the deterministic sample order when appending new rows.
    new_rows = [
        records_by_id[video_id]
        for video_id in new_sampled_ids
        if video_id in records_by_id
    ]

    if new_rows:
        new_df = pd.DataFrame(new_rows, columns=["video_id", *metadata_fields])
        combined_df = pd.concat([existing_df, new_df], ignore_index=True, sort=False)

        # Keep existing columns (including manually added labels) and append only
        # newly requested metadata columns that were not present before.
        ordered_columns = list(existing_df.columns)
        ordered_columns.extend(
            column
            for column in ["video_id", *metadata_fields]
            if column not in ordered_columns
        )
        combined_df.to_excel(output_path, index=False, columns=ordered_columns)
    elif not output_path.exists():
        existing_df.to_excel(output_path, index=False)

    not_found_ids = [
        video_id for video_id in new_sampled_ids if video_id not in records_by_id
    ]
    print(f"Sampled video IDs: {n}")
    print(f"Sampled IDs already present in Excel: {n - len(new_sampled_ids)}")
    print(f"New IDs found in detailed metadata: {len(new_rows)}")
    print(f"New IDs not found in detailed metadata: {len(not_found_ids)}")
    print(f"Requested metadata fields: {', '.join(metadata_fields)}")
    print(f"Excel file saved to: {output_path}")
    return output_path




if __name__ == "__main__":
    create_description_sample(
        detailed_metadata_path=DETAILED_METADATA_FILE,
        all_videos_path=ALL_VIDEOS_FILE,
        output_directory=OUTPUT_DIRECTORY,
        n=N,
        seed_number=SEED_NUMBER,
        metadata_fields=METADATA_FIELDS,
    )
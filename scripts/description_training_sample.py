"""Create a reproducible Excel sample of YouTube video descriptions."""

import json
import random
from pathlib import Path

import pandas as pd

from youtube_code.config import RAW, SAMPLES


# Default configuration. Every value can also be overridden via CLI arguments.
DETAILED_METADATA_FILE = RAW / "video_metadata_detailed_total.json"
ALL_VIDEOS_FILE = SAMPLES / "russia" / "all_videos_russia_ukraine.json"
OUTPUT_DIRECTORY = SAMPLES / "russia"
N = 100
SEED_NUMBER = 42


def load_json_list(path: Path) -> list[dict]:
    """Load a JSON file and verify that it contains a list of dictionaries."""
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError(f"{path} must contain a JSON list of dictionaries.")
    return data


def create_description_sample(
    detailed_metadata_path: Path,
    all_videos_path: Path,
    output_directory: Path,
    n: int,
    seed_number: int,
) -> Path:
    """Sample videos, find their descriptions, and save the matches as Excel."""
    if n < 1:
        raise ValueError("N must be at least 1.")

    all_videos = load_json_list(all_videos_path)
    sample_candidates = [video for video in all_videos if video.get("video_id")]

    if n > len(sample_candidates):
        raise ValueError(
            f"N={n} exceeds the number of videos with a video_id "
            f"({len(sample_candidates)}) in {all_videos_path}."
        )

    rng = random.Random(seed_number)
    sampled_videos = rng.sample(sample_candidates, n)
    sampled_video_ids = [str(video["video_id"]) for video in sampled_videos]
    sampled_id_set = set(sampled_video_ids)

    detailed_metadata = load_json_list(detailed_metadata_path)
    descriptions_by_id = {
        str(video["video_id"]): video.get("description")
        for video in detailed_metadata
        if video.get("video_id") is not None
        and str(video["video_id"]) in sampled_id_set
    }

    # Iterating over sampled_video_ids preserves the reproducible sample order.
    output_rows = [
        {
            "video_id": video_id,
            "description": descriptions_by_id[video_id],
        }
        for video_id in sampled_video_ids
        if video_id in descriptions_by_id
    ]

    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"description_training_sample_{seed_number}.xlsx"
    pd.DataFrame(output_rows, columns=["video_id", "description"]).to_excel(
        output_path,
        index=False,
    )

    missing_count = n - len(output_rows)
    print(f"Sampled video IDs: {n}")
    print(f"Descriptions found: {len(output_rows)}")
    print(f"Video IDs not found in detailed metadata: {missing_count}")
    print(f"Excel file saved to: {output_path}")
    return output_path




if __name__ == "__main__":
    create_description_sample(
        detailed_metadata_path=DETAILED_METADATA_FILE,
        all_videos_path=ALL_VIDEOS_FILE,
        output_directory=OUTPUT_DIRECTORY,
        n=N,
        seed_number=SEED_NUMBER,
    )

import json
import math

import pandas as pd

from youtube_code.step2_baseline_channels.screening_config import (
    BATCH_INPUT_DIR,
    GROUPING_SEED,
    MANIFEST_DIR,
    TITLES_PER_REQUEST,
    TRAINING_SAMPLE_FILE,
)


PROMPT_KEY = "PROMPT_31"
MODEL_NAME = "gemini_25_flash"

PROMPT_NUMBER = PROMPT_KEY.removeprefix("PROMPT_")

JSONL_FILE = (
    BATCH_INPUT_DIR
    / f"batch_input_{PROMPT_NUMBER}_{MODEL_NAME}.jsonl"
)

MANIFEST_FILE = (
    MANIFEST_DIR
    / f"dry_run_{PROMPT_NUMBER}_{MODEL_NAME}_manifest.csv"
)

INPUT_MARKER = "EINGABE:\n"


def add_error(errors: list[str], condition: bool, message: str):
    if not condition:
        errors.append(message)


def read_source_data(path) -> pd.DataFrame:
    source = pd.read_csv(
        path,
        dtype={"video_id": "string", "title": "string"},
        keep_default_na=False,
    )

    required = {"video_id", "title"}
    missing = required - set(source.columns)
    if missing:
        raise ValueError(
            f"Missing columns in training sample: {sorted(missing)}"
        )

    source["video_id"] = source["video_id"].str.strip()
    source["title"] = source["title"].str.strip()

    valid = source.loc[
        source["video_id"].ne("")
        & source["title"].ne("")
    ].copy()

    duplicate_ids = valid.loc[
        valid["video_id"].duplicated(keep=False),
        "video_id",
    ].unique()
    if len(duplicate_ids):
        raise ValueError(
            "Duplicate video IDs in training sample: "
            f"{sorted(duplicate_ids.tolist())[:10]}"
        )

    return valid


def read_jsonl_requests(path) -> list[dict]:
    requests = []

    with path.open("r", encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            if not line.strip():
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON in JSONL line {line_number}: {error}"
                ) from error

            request["_line_number"] = line_number
            requests.append(request)

    return requests


def extract_group(
    request: dict,
    errors: list[str],
) -> tuple[str | None, list[dict]]:
    line_number = request.get("_line_number", "unknown")
    request_id = request.get("custom_id")

    add_error(
        errors,
        isinstance(request_id, str) and bool(request_id.strip()),
        f"Line {line_number}: missing or invalid custom_id.",
    )

    try:
        text = request["request"]["contents"][0]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        errors.append(
            f"Line {line_number}: prompt text could not be located."
        )
        return request_id, []

    if INPUT_MARKER not in text:
        errors.append(
            f"Line {line_number}: input marker {INPUT_MARKER!r} is missing."
        )
        return request_id, []

    input_text = text.split(INPUT_MARKER, 1)[1]
    try:
        input_payload = json.loads(input_text)
    except json.JSONDecodeError as error:
        errors.append(
            f"Line {line_number}: embedded input JSON is invalid: {error}"
        )
        return request_id, []

    videos = input_payload.get("videos")
    if not isinstance(videos, list):
        errors.append(
            f"Line {line_number}: input payload has no videos list."
        )
        return request_id, []

    add_error(
        errors,
        1 <= len(videos) <= TITLES_PER_REQUEST,
        f"Line {line_number}: invalid group size {len(videos)}.",
    )

    for position, video in enumerate(videos, start=1):
        if not isinstance(video, dict):
            errors.append(
                f"Line {line_number}, position {position}: "
                "video entry is not an object."
            )
            continue

        add_error(
            errors,
            set(video) == {"video_id", "title"},
            f"Line {line_number}, position {position}: unexpected fields "
            f"{sorted(set(video) - {'video_id', 'title'})} or missing fields.",
        )
        add_error(
            errors,
            isinstance(video.get("video_id"), str)
            and bool(video["video_id"].strip()),
            f"Line {line_number}, position {position}: invalid video_id.",
        )
        add_error(
            errors,
            isinstance(video.get("title"), str)
            and bool(video["title"].strip()),
            f"Line {line_number}, position {position}: invalid title.",
        )

    try:
        config = request["request"]["generationConfig"]
        schema = config["responseSchema"]
        classifications = schema["properties"]["classifications"]
        label_schema = classifications["items"]["properties"][
            "politics_title"
        ]
    except (KeyError, TypeError):
        errors.append(
            f"Line {line_number}: response schema is missing or malformed."
        )
        return request_id, videos

    add_error(
        errors,
        config.get("responseMimeType") == "application/json",
        f"Line {line_number}: responseMimeType is not application/json.",
    )
    add_error(
        errors,
        config.get("temperature") == 0,
        f"Line {line_number}: temperature is not 0.",
    )
    add_error(
        errors,
        config.get("thinkingConfig", {}).get("thinkingBudget") == 0,
        f"Line {line_number}: thinkingBudget is not 0.",
    )
    add_error(
        errors,
        classifications.get("minItems") == len(videos)
        and classifications.get("maxItems") == len(videos),
        f"Line {line_number}: schema item count does not match "
        f"group size {len(videos)}.",
    )
    add_error(
        errors,
        label_schema.get("type") == "STRING"
        and set(label_schema.get("enum", [])) == {"-1", "0", "1"},
        f"Line {line_number}: label enum is not -1/0/1.",
    )

    return request_id, videos


def validate_manifest(
    manifest: pd.DataFrame,
    jsonl_groups: dict[str, list[dict]],
    errors: list[str],
):
    required_columns = {
        "request_id",
        "position",
        "video_id",
        "title",
        "titles_per_request",
        "grouping_seed",
    }
    missing = required_columns - set(manifest.columns)
    if missing:
        errors.append(
            f"Manifest is missing columns: {sorted(missing)}"
        )
        return

    add_error(
        errors,
        not manifest["video_id"].duplicated().any(),
        "Manifest contains duplicate video IDs.",
    )
    add_error(
        errors,
        set(manifest["request_id"]) == set(jsonl_groups),
        "Request IDs differ between JSONL and manifest.",
    )
    add_error(
        errors,
        manifest["titles_per_request"].eq(TITLES_PER_REQUEST).all(),
        "Manifest contains an unexpected titles_per_request value.",
    )
    add_error(
        errors,
        manifest["grouping_seed"].eq(GROUPING_SEED).all(),
        "Manifest contains an unexpected grouping_seed value.",
    )

    for request_id, videos in jsonl_groups.items():
        manifest_group = (
            manifest.loc[manifest["request_id"].eq(request_id)]
            .sort_values("position")
        )

        expected_positions = list(range(1, len(videos) + 1))
        add_error(
            errors,
            manifest_group["position"].tolist() == expected_positions,
            f"{request_id}: manifest positions are incomplete or unordered.",
        )

        json_pairs = [
            (video.get("video_id"), video.get("title"))
            for video in videos
        ]
        manifest_pairs = list(
            zip(
                manifest_group["video_id"],
                manifest_group["title"],
            )
        )
        add_error(
            errors,
            manifest_pairs == json_pairs,
            f"{request_id}: JSONL and manifest contents differ.",
        )


def main():
    for path in [TRAINING_SAMPLE_FILE, JSONL_FILE, MANIFEST_FILE]:
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

    source = read_source_data(TRAINING_SAMPLE_FILE)
    requests = read_jsonl_requests(JSONL_FILE)
    manifest = pd.read_csv(
        MANIFEST_FILE,
        dtype={
            "request_id": "string",
            "video_id": "string",
            "title": "string",
        },
        keep_default_na=False,
    )

    errors = []
    jsonl_groups = {}

    for request in requests:
        request_id, videos = extract_group(request, errors)
        if request_id in jsonl_groups:
            errors.append(f"Duplicate request ID in JSONL: {request_id}")
        elif request_id is not None:
            jsonl_groups[request_id] = videos

    jsonl_rows = [
        {
            "request_id": request_id,
            "position": position,
            "video_id": video.get("video_id"),
            "title": video.get("title"),
        }
        for request_id, videos in jsonl_groups.items()
        for position, video in enumerate(videos, start=1)
    ]
    jsonl_df = pd.DataFrame(jsonl_rows)

    expected_request_count = math.ceil(
        len(source) / TITLES_PER_REQUEST
    )
    add_error(
        errors,
        len(requests) == expected_request_count,
        f"Expected {expected_request_count} requests, found {len(requests)}.",
    )
    add_error(
        errors,
        len(jsonl_df) == len(source),
        f"Expected {len(source)} videos in JSONL, found {len(jsonl_df)}.",
    )
    add_error(
        errors,
        not jsonl_df["video_id"].duplicated().any(),
        "JSONL contains duplicate video IDs.",
    )
    add_error(
        errors,
        len(manifest) == len(source),
        f"Expected {len(source)} manifest rows, found {len(manifest)}.",
    )

    source_ids = set(source["video_id"])
    jsonl_ids = set(jsonl_df["video_id"])
    manifest_ids = set(manifest["video_id"])

    add_error(
        errors,
        jsonl_ids == source_ids,
        "Video IDs differ between training sample and JSONL.",
    )
    add_error(
        errors,
        manifest_ids == source_ids,
        "Video IDs differ between training sample and manifest.",
    )

    source_titles = source.set_index("video_id")["title"].to_dict()
    jsonl_titles = jsonl_df.set_index("video_id")["title"].to_dict()
    add_error(
        errors,
        jsonl_titles == source_titles,
        "At least one title differs between training sample and JSONL.",
    )

    validate_manifest(manifest, jsonl_groups, errors)

    print("\nTITLE BATCH INPUT VALIDATION")
    print("=" * 60)
    print(f"Training videos: {len(source):,}")
    print(f"JSONL requests: {len(requests):,}")
    print(f"JSONL videos: {len(jsonl_df):,}")
    print(f"Manifest rows: {len(manifest):,}")
    print(f"Titles per request: {TITLES_PER_REQUEST}")
    print(f"Grouping seed: {GROUPING_SEED}")

    if errors:
        print(f"\nFAILED: {len(errors)} problem(s) found")
        for number, error in enumerate(errors, start=1):
            print(f"  {number}. {error}")
        raise SystemExit(1)

    first_request_id = next(iter(jsonl_groups))
    print("\nFirst request for manual spot-check:")
    print(f"  Request ID: {first_request_id}")
    for position, video in enumerate(
        jsonl_groups[first_request_id],
        start=1,
    ):
        print(
            f"  {position:>2}. {video['video_id']} | {video['title']}"
        )

    print("\nPASSED: JSONL, manifest and training sample are consistent.")


if __name__ == "__main__":
    main()

import json
from pathlib import Path

import pandas as pd
from google import genai
from google.cloud import storage

from youtube_code.config import OUTPUTS, PROJECT_ID, LOCATION
from youtube_code.step2_baseline_channels.longitudinal.screening_config import LLM_RUN_SOURCE, MANIFEST_DIR
from youtube_code.store import llm_run_store


# ============================================================
# CONFIG
# ============================================================

# Konsolidierter Ablageort (Phase 4e der Restrukturierung, .claude/plans/
# phase_4.md): outputs/llm_results/screening_active__<run_id>/, statt der
# frueheren nach target_variable getrennten Ordner unter
# outputs/llm/longitudinal/.
RESULTS_ROOT = OUTPUTS / "llm_results"
SUPPORTED_GROUPED_TARGETS = {
    "politics_title",
    "politics_title_desc",
}
SAVE_FORMAT = "CSV"

client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION,
)
storage_client = storage.Client(project=PROJECT_ID)


# ============================================================
# GENERAL HELPERS
# ============================================================

def extract_response_text(data: dict) -> str:
    """Extract the generated text from supported Vertex batch formats."""
    response_obj = data.get("response", {})

    if "candidates" in response_obj:
        candidates = response_obj["candidates"]
    elif "generateContentResponse" in response_obj:
        candidates = response_obj[
            "generateContentResponse"
        ]["candidates"]
    else:
        raise ValueError("No candidates found (possibly safety filter).")

    return candidates[0]["content"]["parts"][0]["text"]


def parse_response_json(
    response_text: str,
    request_id: str,
) -> dict:
    """Parse model JSON and use json_repair only as a fallback."""
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        from json_repair import repair_json

        repaired = repair_json(response_text)
        try:
            parsed = (
                repaired
                if isinstance(repaired, dict)
                else json.loads(repaired)
            )
            print(f"  Repaired JSON for request {request_id}.")
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Could not repair response JSON: {error}"
            ) from error

    if not isinstance(parsed, dict):
        raise ValueError("Parsed response is not a JSON object.")

    return parsed


def download_batch_records(output_uris: list[str]) -> list[dict]:
    """Download every prediction shard and parse its JSONL records."""
    records = []

    for output_uri in output_uris:
        print(f"  Downloading results from {output_uri}...")
        uri_parts = output_uri.replace("gs://", "").split("/", 1)
        if len(uri_parts) != 2:
            raise ValueError(f"Invalid GCS URI: {output_uri}")

        bucket_name, blob_name = uri_parts
        bucket = storage_client.bucket(bucket_name)
        content = bucket.blob(blob_name).download_as_text()

        for line_number, line in enumerate(
            content.splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSONL in {output_uri}, line "
                    f"{line_number}: {error}"
                ) from error

            data["_output_uri"] = output_uri
            data["_line_number"] = line_number
            records.append(data)

    return records


def save_dataframe(
    df: pd.DataFrame,
    output_path: Path,
    save_format: str,
):
    if save_format == "CSV":
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
    else:
        df.to_excel(output_path, index=False)
    print(f"  Saved: {output_path}")


def get_results_dir(run_id: str) -> Path:
    """Consolidated per-run output folder (outputs/llm_results/<source>__<run_id>/)."""
    return RESULTS_ROOT / f"{LLM_RUN_SOURCE}__{run_id}"


# ============================================================
# LEGACY: ONE VIDEO PER REQUEST
# ============================================================

def parse_single_request_results(records: list[dict]) -> pd.DataFrame:
    """Preserve the previous parser for non-grouped model requests."""
    results = []

    for data in records:
        video_id = str(data.get("custom_id", "unknown"))

        if "error" in data:
            print(f"  Error for video {video_id}: {data['error']}")
            results.append(
                {
                    "video_id": video_id,
                    "error": str(data["error"]),
                }
            )
            continue

        try:
            response_text = extract_response_text(data)
            parsed_response = parse_response_json(
                response_text=response_text,
                request_id=video_id,
            )
        except (ValueError, KeyError, IndexError, TypeError) as error:
            print(f"  Could not process answer for {video_id}: {error}")
            parsed_response = {
                "error": "Formatting error",
                "error_detail": str(error),
            }

        row_data = {"video_id": video_id}
        row_data.update(parsed_response)
        results.append(row_data)

    return pd.DataFrame(results)


# ============================================================
# GROUPED TITLE REQUESTS
# ============================================================

def is_single_character_edit(first: str, second: str) -> bool:
    """Return True only when two strings differ by exactly one edit."""
    if first == second or abs(len(first) - len(second)) > 1:
        return False

    if len(first) == len(second):
        return sum(a != b for a, b in zip(first, second)) == 1

    shorter, longer = (
        (first, second)
        if len(first) < len(second)
        else (second, first)
    )
    short_index = 0
    long_index = 0
    edits = 0

    while short_index < len(shorter) and long_index < len(longer):
        if shorter[short_index] == longer[long_index]:
            short_index += 1
            long_index += 1
            continue

        edits += 1
        if edits > 1:
            return False
        long_index += 1

    if long_index < len(longer):
        edits += 1

    return edits == 1

def load_group_manifest(manifest_path: Path) -> pd.DataFrame:
    manifest = pd.read_csv(
        manifest_path,
        dtype={
            "request_id": "string",
            "item_id": "string",
            "video_id": "string",
            "title": "string",
        },
        keep_default_na=False,
    )

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
        raise ValueError(
            f"Manifest is missing columns: {sorted(missing)}"
        )

    manifest["request_id"] = manifest["request_id"].str.strip()
    manifest["video_id"] = manifest["video_id"].str.strip()

    if "item_id" in manifest.columns:
        manifest["item_id"] = manifest["item_id"].str.strip()
        if manifest["item_id"].eq("").any():
            raise ValueError(
                "Manifest contains empty item IDs."
            )
        if manifest.duplicated(["request_id", "item_id"]).any():
            raise ValueError(
                "Manifest contains duplicate request_id/item_id pairs."
            )

    if manifest["video_id"].duplicated().any():
        duplicate_ids = manifest.loc[
            manifest["video_id"].duplicated(keep=False),
            "video_id",
        ].unique()
        raise ValueError(
            "Manifest contains duplicate video IDs: "
            f"{sorted(duplicate_ids.tolist())[:10]}"
        )

    if manifest.duplicated(["request_id", "position"]).any():
        raise ValueError(
            "Manifest contains duplicate request_id/position pairs."
        )

    return manifest


def resolve_grouped_target_variable(
    manifest: pd.DataFrame,
    registry_target_variable: str | None,
) -> str:
    """
    Resolve the label column and guard against mixing runs/manifests.

    New manifests contain target_variable. Older title manifests do not, so
    they remain compatible through the registry value (or politics_title as
    the final legacy fallback).
    """
    requested_target = str(registry_target_variable or "").strip()
    manifest_target = ""

    if "target_variable" in manifest.columns:
        manifest_targets = {
            str(value).strip()
            for value in manifest["target_variable"]
            if str(value).strip()
        }
        if len(manifest_targets) > 1:
            raise ValueError(
                "Manifest contains multiple target variables: "
                f"{sorted(manifest_targets)}"
            )
        if manifest_targets:
            manifest_target = next(iter(manifest_targets))

    if (
        requested_target
        and manifest_target
        and requested_target != manifest_target
    ):
        raise ValueError(
            "Target-variable mismatch between registry and manifest: "
            f"{requested_target!r} != {manifest_target!r}."
        )

    target_variable = (
        manifest_target
        or requested_target
        or "politics_title"
    )
    if target_variable not in SUPPORTED_GROUPED_TARGETS:
        raise ValueError(
            f"Unsupported grouped target variable: {target_variable!r}. "
            f"Supported values: {sorted(SUPPORTED_GROUPED_TARGETS)}"
        )

    return target_variable


def validate_group_response_with_item_ids(
    request_id: str,
    parsed_response: dict,
    expected_group: pd.DataFrame,
    target_variable: str,
) -> tuple[list[dict], list[str], list[str]]:
    """Validate a grouped response through short manifest item IDs."""
    errors = []
    classifications = parsed_response.get("classifications")

    if not isinstance(classifications, list):
        return [], ["Response has no classifications list."], []

    if len(classifications) != len(expected_group):
        errors.append(
            f"Expected {len(expected_group)} classifications, "
            f"received {len(classifications)}."
        )

    returned_rows = []
    returned_item_ids = []

    for response_position, item in enumerate(
        classifications,
        start=1,
    ):
        if not isinstance(item, dict):
            errors.append(
                f"Response position {response_position} is not an object."
            )
            continue

        item_id = str(item.get("item_id", "")).strip()
        raw_label = item.get(target_variable)

        if not item_id:
            errors.append(
                f"Response position {response_position} has no item_id."
            )
            continue

        try:
            label = int(raw_label)
        except (TypeError, ValueError):
            errors.append(
                f"Invalid label for {item_id}: {raw_label!r}."
            )
            continue

        if label not in {-1, 0, 1}:
            errors.append(
                f"Label outside -1/0/1 for {item_id}: {label}."
            )
            continue

        returned_item_ids.append(item_id)
        returned_rows.append(
            {
                "item_id": item_id,
                target_variable: label,
                "request_id": request_id,
                "response_position": response_position,
            }
        )

    duplicate_item_ids = pd.Series(
        returned_item_ids,
        dtype="string",
    ).duplicated(keep=False)
    if duplicate_item_ids.any():
        duplicates = sorted(
            pd.Series(returned_item_ids, dtype="string")
            .loc[duplicate_item_ids]
            .unique()
            .tolist()
        )
        errors.append(
            f"Duplicate returned item IDs: {duplicates}."
        )

    expected_item_ids = expected_group["item_id"].tolist()
    expected_item_id_set = set(expected_item_ids)
    returned_item_id_set = set(returned_item_ids)

    missing_item_ids = sorted(
        expected_item_id_set - returned_item_id_set
    )
    unexpected_item_ids = sorted(
        returned_item_id_set - expected_item_id_set
    )
    if missing_item_ids:
        errors.append(
            f"Missing item IDs: {missing_item_ids}."
        )
    if unexpected_item_ids:
        errors.append(
            f"Unexpected item IDs: {unexpected_item_ids}."
        )

    if errors:
        return [], errors, []

    response_by_item_id = {
        row["item_id"]: row
        for row in returned_rows
    }
    order_matches = returned_item_ids == expected_item_ids

    accepted_rows = []
    for manifest_row in expected_group.itertuples(index=False):
        response_row = response_by_item_id[manifest_row.item_id]
        accepted_rows.append(
            {
                "video_id": manifest_row.video_id,
                "returned_video_id": pd.NA,
                "video_id_corrected": False,
                "item_id": manifest_row.item_id,
                "returned_item_id": response_row["item_id"],
                "item_id_corrected": False,
                target_variable: response_row[target_variable],
                "request_id": request_id,
                "group_position": int(manifest_row.position),
                "response_position": response_row["response_position"],
                "response_order_matches_manifest": order_matches,
            }
        )

    return accepted_rows, [], []


def validate_group_response(
    request_id: str,
    parsed_response: dict,
    expected_group: pd.DataFrame,
    target_variable: str,
) -> tuple[list[dict], list[str], list[str]]:
    """Validate a legacy grouped response containing real video IDs."""
    errors = []
    classifications = parsed_response.get("classifications")

    if not isinstance(classifications, list):
        return [], ["Response has no classifications list."], []

    if len(classifications) != len(expected_group):
        errors.append(
            f"Expected {len(expected_group)} classifications, "
            f"received {len(classifications)}."
        )

    returned_rows = []
    returned_ids = []

    for response_position, item in enumerate(
        classifications,
        start=1,
    ):
        if not isinstance(item, dict):
            errors.append(
                f"Response position {response_position} is not an object."
            )
            continue

        video_id = str(item.get("video_id", "")).strip()
        raw_label = item.get(target_variable)

        if not video_id:
            errors.append(
                f"Response position {response_position} has no video_id."
            )
            continue

        try:
            label = int(raw_label)
        except (TypeError, ValueError):
            errors.append(
                f"Invalid label for {video_id}: {raw_label!r}."
            )
            continue

        if label not in {-1, 0, 1}:
            errors.append(
                f"Label outside -1/0/1 for {video_id}: {label}."
            )
            continue

        returned_ids.append(video_id)
        returned_rows.append(
            {
                "video_id": video_id,
                "returned_video_id": video_id,
                "video_id_corrected": False,
                target_variable: label,
                "request_id": request_id,
                "response_position": response_position,
            }
        )

    duplicate_returned_ids = pd.Series(
        returned_ids,
        dtype="string",
    ).duplicated(keep=False)
    if duplicate_returned_ids.any():
        duplicates = sorted(
            pd.Series(returned_ids, dtype="string")
            .loc[duplicate_returned_ids]
            .unique()
            .tolist()
        )
        errors.append(f"Duplicate returned video IDs: {duplicates}.")

    expected_ids = expected_group["video_id"].tolist()
    original_returned_ids = returned_ids.copy()
    expected_id_set = set(expected_ids)
    returned_id_set = set(returned_ids)

    missing_ids = sorted(expected_id_set - returned_id_set)
    unexpected_ids = sorted(returned_id_set - expected_id_set)

    correction_notes = []
    mismatched_positions = [
        position
        for position, (expected_id, returned_id) in enumerate(
            zip(expected_ids, returned_ids),
            start=1,
        )
        if expected_id != returned_id
    ]

    # Strict recovery for one copied-ID typo. It is only safe when the group
    # has the expected length, every other ID is at the exact manifest
    # position, there is exactly one missing and one unexpected ID, and those
    # two values differ by one character. All other cases remain rejected.
    can_correct_single_id = (
        not errors
        and len(returned_rows) == len(expected_ids)
        and len(mismatched_positions) == 1
        and len(missing_ids) == 1
        and len(unexpected_ids) == 1
        and is_single_character_edit(
            missing_ids[0],
            unexpected_ids[0],
        )
    )

    if can_correct_single_id:
        mismatch_position = mismatched_positions[0]
        expected_id = expected_ids[mismatch_position - 1]
        returned_row = returned_rows[mismatch_position - 1]

        # The set difference and the positional mismatch must describe the
        # same pair; otherwise no automatic repair is allowed.
        if (
            expected_id == missing_ids[0]
            and returned_row["video_id"] == unexpected_ids[0]
        ):
            returned_row["video_id"] = expected_id
            returned_row["video_id_corrected"] = True
            returned_ids[mismatch_position - 1] = expected_id
            returned_id_set = set(returned_ids)
            missing_ids = sorted(expected_id_set - returned_id_set)
            unexpected_ids = sorted(returned_id_set - expected_id_set)
            correction_notes.append(
                "Corrected one-character video_id copy error at "
                f"response position {mismatch_position}: "
                f"{returned_row['returned_video_id']} -> {expected_id}."
            )

    if missing_ids:
        errors.append(f"Missing video IDs: {missing_ids}.")
    if unexpected_ids:
        errors.append(f"Unexpected video IDs: {unexpected_ids}.")

    if errors:
        return [], errors, correction_notes

    response_by_id = {
        row["video_id"]: row
        for row in returned_rows
    }
    order_matches = original_returned_ids == expected_ids

    accepted_rows = []
    for manifest_row in expected_group.itertuples(index=False):
        response_row = response_by_id[manifest_row.video_id]
        accepted_rows.append(
            {
                "video_id": manifest_row.video_id,
                "returned_video_id": response_row["returned_video_id"],
                "video_id_corrected": response_row["video_id_corrected"],
                "item_id": pd.NA,
                "returned_item_id": pd.NA,
                "item_id_corrected": False,
                target_variable: response_row[target_variable],
                "request_id": request_id,
                "group_position": int(manifest_row.position),
                "response_position": response_row["response_position"],
                "response_order_matches_manifest": order_matches,
            }
        )

    return accepted_rows, [], correction_notes


def parse_grouped_results(
    records: list[dict],
    manifest: pd.DataFrame,
    target_variable: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Explode valid grouped responses to one row per video.

    A group is accepted only if every expected ID is returned exactly once
    with a valid -1/0/1 label. Rejected groups are written to a retry file.
    """
    accepted_rows = []
    validation_rows = []

    expected_request_ids = set(manifest["request_id"])
    seen_request_ids = set()

    for data in records:
        request_id = str(data.get("custom_id", "")).strip()
        output_uri = data.get("_output_uri")
        line_number = data.get("_line_number")

        if not request_id:
            validation_rows.append(
                {
                    "request_id": "",
                    "status": "rejected",
                    "error": "Response record has no custom_id.",
                    "output_uri": output_uri,
                    "line_number": line_number,
                }
            )
            continue

        if request_id in seen_request_ids:
            validation_rows.append(
                {
                    "request_id": request_id,
                    "status": "rejected",
                    "error": "Duplicate response for request_id.",
                    "output_uri": output_uri,
                    "line_number": line_number,
                }
            )
            continue
        seen_request_ids.add(request_id)

        if request_id not in expected_request_ids:
            validation_rows.append(
                {
                    "request_id": request_id,
                    "status": "rejected",
                    "error": "Unexpected request_id not found in manifest.",
                    "output_uri": output_uri,
                    "line_number": line_number,
                }
            )
            continue

        expected_group = (
            manifest.loc[manifest["request_id"].eq(request_id)]
            .sort_values("position")
            .copy()
        )

        if "error" in data:
            validation_rows.append(
                {
                    "request_id": request_id,
                    "status": "rejected",
                    "error": f"Vertex error: {data['error']}",
                    "output_uri": output_uri,
                    "line_number": line_number,
                }
            )
            continue

        try:
            response_text = extract_response_text(data)
            parsed_response = parse_response_json(
                response_text=response_text,
                request_id=request_id,
            )
            uses_item_ids = (
                "item_id" in expected_group.columns
                and expected_group["item_id"].ne("").all()
            )
            validator = (
                validate_group_response_with_item_ids
                if uses_item_ids
                else validate_group_response
            )
            group_rows, group_errors, correction_notes = validator(
                request_id=request_id,
                parsed_response=parsed_response,
                expected_group=expected_group,
                target_variable=target_variable,
            )
        except (ValueError, KeyError, IndexError, TypeError) as error:
            group_rows = []
            group_errors = [str(error)]
            correction_notes = []

        if group_errors:
            validation_rows.append(
                {
                    "request_id": request_id,
                    "status": "rejected",
                    "error": " | ".join(group_errors),
                    "warning": " | ".join(correction_notes),
                    "output_uri": output_uri,
                    "line_number": line_number,
                }
            )
            continue

        accepted_rows.extend(group_rows)
        validation_rows.append(
            {
                "request_id": request_id,
                "status": "accepted",
                "error": "",
                "warning": " | ".join(correction_notes),
                "output_uri": output_uri,
                "line_number": line_number,
            }
        )

    missing_request_ids = sorted(
        expected_request_ids - seen_request_ids
    )
    for request_id in missing_request_ids:
        validation_rows.append(
            {
                "request_id": request_id,
                "status": "rejected",
                "error": "No response record returned by Vertex.",
                "output_uri": "",
                "line_number": pd.NA,
            }
        )

    results_df = pd.DataFrame(
        accepted_rows,
        columns=[
            "video_id",
            "returned_video_id",
            "video_id_corrected",
            "item_id",
            "returned_item_id",
            "item_id_corrected",
            target_variable,
            "request_id",
            "group_position",
            "response_position",
            "response_order_matches_manifest",
        ],
    )
    validation_df = pd.DataFrame(validation_rows)

    rejected_request_ids = set(
        validation_df.loc[
            validation_df["status"].eq("rejected"),
            "request_id",
        ]
    ) & expected_request_ids

    # If Vertex returned the same request more than once, an earlier response
    # may already have looked valid. Once any response for a request is
    # rejected, exclude the complete group from accepted results.
    if rejected_request_ids and not results_df.empty:
        results_df = results_df.loc[
            ~results_df["request_id"].isin(rejected_request_ids)
        ].reset_index(drop=True)

    retry_columns = [
        "request_id",
        "position",
    ]
    if "item_id" in manifest.columns:
        retry_columns.append("item_id")
    retry_columns.extend(["video_id", "title"])
    retry_columns.extend(
        column
        for column in [
            "items_per_request",
            "titles_per_request",
            "grouping_seed",
            "input_mode",
            "target_variable",
        ]
        if column in manifest.columns
    )

    retry_df = (
        manifest.loc[
            manifest["request_id"].isin(rejected_request_ids),
            retry_columns,
        ]
        .sort_values(["request_id", "position"])
        .reset_index(drop=True)
    )

    return results_df, validation_df, retry_df


def save_grouped_results(
    records: list[dict],
    manifest_path: Path,
    output_path: Path,
    save_format: str,
    registry_target_variable: str | None,
) -> dict:
    manifest = load_group_manifest(manifest_path)
    target_variable = resolve_grouped_target_variable(
        manifest=manifest,
        registry_target_variable=registry_target_variable,
    )
    print(f"  Validating response field: {target_variable}")

    results_df, validation_df, retry_df = parse_grouped_results(
        records=records,
        manifest=manifest,
        target_variable=target_variable,
    )

    save_dataframe(results_df, output_path, save_format)

    validation_path = output_path.with_name(
        f"{output_path.stem}_group_validation.csv"
    )
    validation_df.to_csv(
        validation_path,
        index=False,
        encoding="utf-8-sig",
    )
    print(f"  Saved validation report: {validation_path}")

    rejected_groups = validation_df.loc[
        validation_df["status"].eq("rejected")
    ]

    retry_path = None
    if not retry_df.empty:
        retry_path = output_path.with_name(
            f"{output_path.stem}_retry.csv"
        )
        retry_df.to_csv(
            retry_path,
            index=False,
            encoding="utf-8-sig",
        )
        print(f"  Saved retry input: {retry_path}")

    expected_videos = len(manifest)
    accepted_videos = len(results_df)
    expected_groups = manifest["request_id"].nunique()
    rejected_expected_ids = set(retry_df["request_id"])
    accepted_request_ids = (
        set(
            validation_df.loc[
                validation_df["status"].eq("accepted"),
                "request_id",
            ]
        )
        - rejected_expected_ids
    )
    accepted_groups = len(accepted_request_ids)

    print(
        f"  Group validation: {accepted_groups}/{expected_groups} "
        "groups accepted."
    )
    print(
        f"  Video validation: {accepted_videos}/{expected_videos} "
        "videos accepted."
    )

    return {
        "all_valid": rejected_groups.empty
        and accepted_groups == expected_groups
        and accepted_videos == expected_videos,
        "accepted_groups": int(accepted_groups),
        "expected_groups": int(expected_groups),
        "accepted_videos": int(accepted_videos),
        "expected_videos": int(expected_videos),
        "validation_path": str(validation_path),
        "retry_path": str(retry_path) if retry_path else None,
    }


# ============================================================
# DOWNLOAD + JOB MANAGEMENT
# ============================================================

def saving_results(
    output_uris: list[str],
    output_path: str | Path,
    save_format: str,
    manifest_path: Path | None = None,
    target_variable: str | None = None,
) -> dict:
    records = download_batch_records(output_uris)
    output_path = Path(output_path)

    grouped_request_detected = any(
        str(record.get("custom_id", "")).startswith(
            ("title_group_", "title_description_group_")
        )
        for record in records
    )

    if grouped_request_detected and manifest_path is None:
        raise ValueError(
            "Grouped screening responses were detected, but no matching "
            "manifest was found."
        )

    if manifest_path is not None:
        print(f"  Group manifest found: {manifest_path}")
        return save_grouped_results(
            records=records,
            manifest_path=manifest_path,
            output_path=output_path,
            save_format=save_format,
            registry_target_variable=target_variable,
        )

    print("  No group manifest found; using single-request parser.")
    results_df = parse_single_request_results(records)
    save_dataframe(results_df, output_path, save_format)
    return {
        "all_valid": True,
        "accepted_videos": len(results_df),
        "expected_videos": len(results_df),
    }


def find_output_urls(status_job) -> list[str]:
    """Return every prediction JSONL shard in the output directory."""
    output_folder = status_job.output_info.gcs_output_directory
    path_parts = output_folder.replace("gs://", "").split("/", 1)
    if len(path_parts) != 2:
        return []

    bucket_name, prefix = path_parts
    bucket = storage_client.bucket(bucket_name)
    blobs = list(bucket.list_blobs(prefix=prefix))

    return sorted(
        f"gs://{bucket_name}/{blob.name}"
        for blob in blobs
        if blob.name.endswith(".jsonl")
        and "prediction" in blob.name.lower()
    )


def process_run(run_id: str, save_format: str = "CSV") -> str:
    """Check a registered job, download and validate finished output."""
    run = llm_run_store.get_run(LLM_RUN_SOURCE, run_id)
    job_id = run["job_id"]
    raw_target_variable = run.get("target_variable", "")
    target_variable = (
        ""
        if pd.isna(raw_target_variable)
        else str(raw_target_variable).strip()
    )

    results_dir = get_results_dir(run_id)
    results_dir.mkdir(parents=True, exist_ok=True)
    extension = "csv" if save_format == "CSV" else "xlsx"
    output_path = results_dir / f"{run_id}.{extension}"
    manifest_path = MANIFEST_DIR / f"{run_id}_manifest.csv"

    print(
        f"\n[{run_id}] Prompt: {run['prompt_id']} | "
        f"Model: {run['model']} | Dataset: "
        f"{run['dataset_id']} ({run['dataset_version']}) | "
        f"Target: {target_variable or 'not specified'}"
    )

    try:
        status_job = client.batches.get(name=job_id)
        current_state = (
            status_job.state.name
            if hasattr(status_job.state, "name")
            else str(status_job.state)
        )
        print(f"  Status: {current_state}")
    except Exception as error:
        print(f"  Could not fetch job status: {error}")
        return "error"

    if current_state in {
        "JOB_STATE_FAILED",
        "JOB_STATE_CANCELLED",
    }:
        print("  Job failed/cancelled.")
        print(f"  Error: {status_job.error}")
        llm_run_store.update_run(LLM_RUN_SOURCE, run_id, status="failed")
        return "failed"

    if current_state != "JOB_STATE_SUCCEEDED":
        print("  Still running - skipping.")
        return "pending"

    if output_path.exists():
        print(f"  Output file already exists: {output_path}")
        answer = input("  Overwrite? [y/N] ")
        if answer.strip().lower() != "y":
            print("  Skipping.")
            return "skipped"

    output_uris = find_output_urls(status_job)
    if not output_uris:
        print("  No prediction JSONL found in GCS output folder.")
        llm_run_store.update_run(LLM_RUN_SOURCE, run_id, status="error")
        return "error"

    try:
        validation = saving_results(
            output_uris=output_uris,
            output_path=output_path,
            save_format=save_format,
            manifest_path=(
                manifest_path if manifest_path.exists() else None
            ),
            target_variable=target_variable,
        )
    except Exception as error:
        print(f"  Download or validation failed: {error}")
        llm_run_store.update_run(LLM_RUN_SOURCE, run_id, status="validation_failed")
        return "validation_failed"

    if not validation["all_valid"]:
        print(
            "  Group validation failed. The run was not marked as "
            "downloaded."
        )
        llm_run_store.update_run(
            LLM_RUN_SOURCE,
            run_id,
            status="validation_failed",
            results_path=str(output_path),
        )
        return "validation_failed"

    llm_run_store.update_run(
        LLM_RUN_SOURCE,
        run_id,
        status="downloaded",
        results_path=str(output_path),
    )
    print(f"  Registry updated for {run_id}")
    return "downloaded"


# ============================================================
# MAIN
# ============================================================

def main():
    open_runs = llm_run_store.get_runs(source=LLM_RUN_SOURCE, status="submitted")

    if open_runs.empty:
        print("No open runs (status='submitted') found in the registry.")
        return

    print(f"\n{'=' * 60}")
    print(f"Found {len(open_runs)} open run(s) to check:")
    for run_id in open_runs["run_id"]:
        print(f"  {run_id}")
    print(f"{'=' * 60}")

    answer = input("\nCheck all and download finished results? [Y/n] ")
    if answer.strip().lower() != "y":
        print("Aborted.")
        return

    summary = {
        "downloaded": [],
        "pending": [],
        "failed": [],
        "validation_failed": [],
        "skipped": [],
        "error": [],
    }

    for run_id in open_runs["run_id"]:
        result = process_run(run_id, SAVE_FORMAT)
        summary.setdefault(result, []).append(run_id)

    print(f"\n{'=' * 60}")
    print("Summary:")
    print(
        f"  Downloaded        : {len(summary['downloaded'])} "
        f"{summary['downloaded']}"
    )
    print(
        f"  Pending           : {len(summary['pending'])} "
        f"{summary['pending']}"
    )
    print(
        f"  Failed            : {len(summary['failed'])} "
        f"{summary['failed']}"
    )
    print(
        "  Validation failed : "
        f"{len(summary['validation_failed'])} "
        f"{summary['validation_failed']}"
    )
    print(
        f"  Skipped           : {len(summary['skipped'])} "
        f"{summary['skipped']}"
    )
    print(
        f"  Errors            : {len(summary['error'])} "
        f"{summary['error']}"
    )
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()

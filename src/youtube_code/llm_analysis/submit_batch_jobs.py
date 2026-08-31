import os
import json
import uuid
from pathlib import Path

import pandas as pd
from google import genai
from google.cloud import storage

from youtube_code.config import PROJECT_ID, LOCATION, BUCKET_NAME, EXPLORATION, SAMPLES
from youtube_code.politics_screening.screening_config import LLM_RUN_SOURCE
from youtube_code.store import llm_run_store
# ===============================================
# CONFIG
# ===============================================

BATCH_INPUT_JSONL_TEMPLATE = "batch_input_{prompt_number}_{model_name}.jsonl"
DEFAULT_MANIFEST_DIR = Path("batch_manifests")
DEFAULT_MAX_DESCRIPTION_CHARS = 5_000
DEFAULT_PREVIOUS_TITLE_LABEL_COLUMN = "politics_title_model"

MODEL_ALIASES = {
    "gemini_25_flash": "gemini-2.5-flash",
    "gemini_25_pro": "gemini-2.5-pro",
}

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

# ===============================================
# FUNCTIONS
# ===============================================

def get_prompt_number(prompt_key: str) -> str:
    if prompt_key.startswith("PROMPT_") and prompt_key[7:].isdigit():
        return prompt_key.split("_")[1]
    elif prompt_key.startswith("GPT_") and prompt_key[4:].isdigit():
        return "gpt" + prompt_key.split("_")[1]
    else:
        return "0"


def clean_text(value) -> str:
    """Convert missing table values to an empty string."""
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def select_title_uncertain_rows(
    df: pd.DataFrame,
    previous_title_label_column: str,
) -> pd.DataFrame:
    """
    Select exactly the videos deferred by the preceding title screening.

    The column must contain a complete Prompt-32 result with labels -1/0/1.
    Missing or invalid labels are treated as a pipeline error rather than
    silently excluding videos from the description stage.
    """
    if not previous_title_label_column:
        raise ValueError(
            "previous_title_label_column must be specified for "
            "input_mode='title_description'."
        )
    if previous_title_label_column not in df.columns:
        raise ValueError(
            "The title-description filter column "
            f"{previous_title_label_column!r} is missing. Available columns: "
            f"{sorted(df.columns.tolist())}"
        )

    raw_labels = df[previous_title_label_column]
    numeric_labels = pd.to_numeric(
        raw_labels,
        errors="coerce",
    )

    invalid_nonmissing = raw_labels.notna() & numeric_labels.isna()
    if invalid_nonmissing.any():
        invalid_values = (
            raw_labels.loc[invalid_nonmissing]
            .astype(str)
            .unique()
            .tolist()
        )
        raise ValueError(
            f"{previous_title_label_column!r} contains non-numeric labels: "
            f"{sorted(invalid_values)[:10]}"
        )

    if numeric_labels.isna().any():
        raise ValueError(
            f"{previous_title_label_column!r} contains "
            f"{int(numeric_labels.isna().sum()):,} missing title labels. "
            "Prompt 32 must be complete before Prompt 33 is submitted."
        )

    numeric_labels = numeric_labels.astype(int)
    invalid_labels = ~numeric_labels.isin([-1, 0, 1])
    if invalid_labels.any():
        invalid_values = sorted(
            numeric_labels.loc[invalid_labels].unique().tolist()
        )
        raise ValueError(
            f"{previous_title_label_column!r} contains invalid labels: "
            f"{invalid_values}. Expected only -1, 0, or 1."
        )

    selected = df.loc[numeric_labels.eq(-1)].copy()
    print(
        "Title-description filter: "
        f"{len(selected):,}/{len(df):,} rows selected because "
        f"{previous_title_label_column} == -1."
    )

    if selected.empty:
        raise ValueError(
            "No title-uncertain videos were found. There is nothing to "
            "submit to Prompt 33."
        )

    return selected


def build_input_text(
    row: pd.Series,
    input_mode: str,
    max_description_chars: int = DEFAULT_MAX_DESCRIPTION_CHARS,
) -> str | None:
    title = clean_text(row.get("title"))
    description = clean_text(row.get("description"))
    transcript = clean_text(row.get("transcript"))

    if max_description_chars < 1:
        raise ValueError("max_description_chars must be at least 1.")
    description = description[:max_description_chars]

    if input_mode == "title":
        if not title:
            return None
        return f"Titel:\n{title}"

    if input_mode == "title_description":
        if not title and not description:
            return None
        return (
            f"Titel:\n{title}\n\n"
            f"Beschreibung:\n{description}"
        )

    if input_mode == "transcript":
        if not transcript:
            return None
        return f"Hier ist das Transkript:\n\n{transcript}"

    raise ValueError(f"Unknown input_mode: {input_mode}")


def validate_grouped_mode_and_target(
    input_mode: str,
    target_variable: str,
):
    expected_targets = {
        "title": "politics_title",
        "title_description": "politics_title_desc",
    }
    if input_mode not in expected_targets:
        raise ValueError(
            "Grouped requests are only supported for "
            "input_mode='title' or 'title_description'."
        )

    expected_target = expected_targets[input_mode]
    if target_variable != expected_target:
        raise ValueError(
            f"input_mode={input_mode!r} requires "
            f"target_variable={expected_target!r}, got "
            f"{target_variable!r}."
        )


def build_grouped_response_schema(
    group_size: int,
    target_variable: str,
) -> dict:
    """Structured response schema for a grouped screening request."""
    if group_size < 1:
        raise ValueError("group_size must be at least 1.")
    if target_variable not in {
        "politics_title",
        "politics_title_desc",
    }:
        raise ValueError(
            f"Unsupported grouped target variable: {target_variable!r}."
        )

    return {
        "type": "OBJECT",
        "properties": {
            "classifications": {
                "type": "ARRAY",
                "minItems": group_size,
                "maxItems": group_size,
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "item_id": {
                            "type": "STRING",
                        },
                        target_variable: {
                            "type": "INTEGER",
                        },
                    },
                    "required": [
                        "item_id",
                        target_variable,
                    ],
                    "propertyOrdering": [
                        "item_id",
                        target_variable,
                    ],
                },
            }
        },
        "required": ["classifications"],
        "propertyOrdering": ["classifications"],
    }


def prepare_grouped_screening_data(
    df: pd.DataFrame,
    input_mode: str,
    target_variable: str,
    grouping_seed: int,
    max_description_chars: int,
) -> pd.DataFrame:
    validate_grouped_mode_and_target(
        input_mode=input_mode,
        target_variable=target_variable,
    )

    required_columns = {"video_id", "title"}
    if input_mode == "title_description":
        required_columns.add("description")

    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(
            "Missing columns for grouped screening: "
            f"{sorted(missing)}"
        )
    if max_description_chars < 1:
        raise ValueError("max_description_chars must be at least 1.")

    data = df.copy()
    data["video_id"] = data["video_id"].map(clean_text).astype("string")
    data["title"] = data["title"].map(clean_text).astype("string")

    if input_mode == "title_description":
        data["description"] = (
            data["description"]
            .map(clean_text)
            .astype("string")
            .str.slice(0, max_description_chars)
        )

    data = data.loc[
        data["video_id"].ne("") & data["title"].ne("")
    ].copy()

    duplicated = data["video_id"].duplicated(keep=False)
    if duplicated.any():
        duplicate_ids = sorted(
            data.loc[duplicated, "video_id"].unique().tolist()
        )
        raise ValueError(
            "Duplicate video IDs are not allowed: "
            f"{duplicate_ids[:10]}"
        )

    # Fixed random order prevents groups from being dominated by neighbouring
    # rows or by one channel, while remaining completely reproducible.
    return data.sample(
        frac=1,
        random_state=grouping_seed,
    ).reset_index(drop=True)


def grouped_screening_to_jsonl(
    df: pd.DataFrame,
    jsonl_path: Path,
    manifest_path: Path,
    system_prompt: str,
    input_mode: str,
    target_variable: str,
    items_per_request: int,
    grouping_seed: int,
    thinking_budget: int | None,
    max_description_chars: int,
) -> tuple[int, int]:
    if items_per_request < 2:
        raise ValueError("items_per_request must be at least 2 here.")

    data = prepare_grouped_screening_data(
        df=df,
        input_mode=input_mode,
        target_variable=target_variable,
        grouping_seed=grouping_seed,
        max_description_chars=max_description_chars,
    )
    if data.empty:
        raise ValueError("No valid videos for grouped screening found.")

    manifest_rows = []
    written_requests = 0
    request_prefix = (
        "title_group"
        if input_mode == "title"
        else "title_description_group"
    )

    with jsonl_path.open("w", encoding="utf-8") as output_file:
        for start in range(0, len(data), items_per_request):
            group = data.iloc[start:start + items_per_request]
            request_id = f"{request_prefix}_{written_requests + 1:06d}"

            group_items = []
            for position, row in enumerate(
                group.itertuples(index=False),
                start=1,
            ):
                item = {
                    "item_id": f"item_{position:02d}",
                    "video_id": str(row.video_id),
                    "title": str(row.title),
                }
                if input_mode == "title_description":
                    item["description"] = str(row.description)
                group_items.append(item)

            # The model sees only a short identifier. The real YouTube ID is
            # retained exclusively in the manifest and never has to be copied
            # by the model.
            videos = []
            for item in group_items:
                video = {
                    "item_id": item["item_id"],
                    "title": item["title"],
                }
                if input_mode == "title_description":
                    video["description"] = item["description"]
                videos.append(video)

            input_text = json.dumps(
                {"videos": videos},
                ensure_ascii=False,
                indent=2,
            )

            generation_config = {
                "responseMimeType": "application/json",
                "responseSchema": build_grouped_response_schema(
                    group_size=len(videos),
                    target_variable=target_variable,
                ),
                "temperature": 0,
            }

            label_schema = (
                generation_config["responseSchema"]
                ["properties"]["classifications"]
                ["items"]["properties"][target_variable]
            )

            if label_schema != {"type": "INTEGER"}:
                raise ValueError(
                    f"Invalid {target_variable} schema: "
                    f"{label_schema!r}"
                )

            if thinking_budget is not None:
                generation_config["thinkingConfig"] = {
                    "thinkingBudget": thinking_budget
                }

            api_request = {
                "custom_id": request_id,
                "request": {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "text": (
                                        f"{system_prompt}\n\n"
                                        "EINGABE:\n"
                                        f"{input_text}"
                                    )
                                }
                            ],
                        }
                    ],
                    "generationConfig": generation_config,
                },
            }
            output_file.write(
                json.dumps(api_request, ensure_ascii=False) + "\n"
            )

            for position, item in enumerate(group_items, start=1):
                manifest_rows.append(
                    {
                        "request_id": request_id,
                        "position": position,
                        "item_id": item["item_id"],
                        "video_id": item["video_id"],
                        "title": item["title"],
                        # Retained for compatibility with the existing
                        # download/validation scripts.
                        "titles_per_request": items_per_request,
                        "items_per_request": items_per_request,
                        "grouping_seed": grouping_seed,
                        "input_mode": input_mode,
                        "target_variable": target_variable,
                    }
                )

            written_requests += 1

    pd.DataFrame(manifest_rows).to_csv(
        manifest_path,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"{len(data)} videos written as {written_requests} grouped "
        f"{input_mode} requests."
    )
    print(f"Manifest saved temporarily to {manifest_path}.")
    return written_requests, len(data)


def csv_to_jsonl(
    csv_path,
    jsonl_path,
    system_prompt,
    input_mode: str,
    target_variable: str,
    thinking_budget: int | None = None,
    items_per_request: int = 1,
    grouping_seed: int = 42,
    manifest_path: str | Path | None = None,
    max_description_chars: int = DEFAULT_MAX_DESCRIPTION_CHARS,
    previous_title_label_column: str = (
        DEFAULT_PREVIOUS_TITLE_LABEL_COLUMN
    ),
):
    print(f"Converting CSV to JSONL -> {jsonl_path}")
    df = pd.read_csv(
        csv_path,
        dtype={"video_id": "string"},
        low_memory=False,
    )

    if input_mode == "title_description":
        df = select_title_uncertain_rows(
            df=df,
            previous_title_label_column=previous_title_label_column,
        )

    jsonl_path = Path(jsonl_path)

    if (
        input_mode in {"title", "title_description"}
        and items_per_request > 1
    ):
        if manifest_path is None:
            manifest_path = jsonl_path.with_suffix(".manifest.csv")
        return grouped_screening_to_jsonl(
            df=df,
            jsonl_path=jsonl_path,
            manifest_path=Path(manifest_path),
            system_prompt=system_prompt,
            input_mode=input_mode,
            target_variable=target_variable,
            items_per_request=items_per_request,
            grouping_seed=grouping_seed,
            thinking_budget=thinking_budget,
            max_description_chars=max_description_chars,
        )

    if items_per_request != 1:
        raise ValueError(
            "Grouped requests are only implemented for input_mode='title' "
            "or 'title_description'."
        )

    written_requests = 0

    with jsonl_path.open("w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            video_id = clean_text(row.get("video_id"))
            if not video_id:
                continue

            input_text = build_input_text(
                row=row,
                input_mode=input_mode,
                max_description_chars=max_description_chars,
            )

            if input_text is None:
                continue

            generation_config = {
                "responseMimeType": "application/json",
                "temperature": 0,
            }

            if thinking_budget is not None:
                generation_config["thinkingConfig"] = {
                    "thinkingBudget": thinking_budget
                }

            api_request = {
                "custom_id": video_id,
                "request": {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "text": (
                                        f"{system_prompt}\n\n"
                                        f"{input_text}"
                                    )
                                }
                            ],
                        }
                    ],
                    "generationConfig": generation_config,
                },
            }

            f.write(
                json.dumps(api_request, ensure_ascii=False) + "\n"
            )
            written_requests += 1

    print(f"{written_requests} requests written to {jsonl_path}.")
    return written_requests, written_requests


def start_batch_job(jsonl_path, model):
    jsonl_path = Path(jsonl_path)
    print(f"Uploading {jsonl_path} to GCS...")
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)

    upload_id = uuid.uuid4().hex
    blob_name = (
        f"batch_inputs/{jsonl_path.stem}_"
        f"{upload_id}{jsonl_path.suffix}"
    )
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(str(jsonl_path))

    gcs_uri = f"gs://{BUCKET_NAME}/{blob_name}"
    print("File successfully uploaded.")
    print(f"Batch input URI: {gcs_uri}")

    print("Starting batch job...")
    job = client.batches.create(model=model, src=gcs_uri)

    os.remove(jsonl_path)
    print(f"JSONL file ('{jsonl_path}') locally deleted.")
    return job.name


def run_all_prompts(
    csv_path: str,
    prompt_keys: list[str] | str,
    prompts: dict,
    dataset_id: str,
    dataset_version: str,
    target_variable: str,
    input_mode: str = "transcript",
    validation_basis: str = "manual",
    model_name: str = "gemini_25_flash",
    thinking_budget: int | None = None,
    prompt_version: str = "v1",
    items_per_request: int = 1,
    grouping_seed: int = 42,
    batch_input_dir: str | Path = ".",
    manifest_dir: str | Path = DEFAULT_MANIFEST_DIR,
    max_description_chars: int = DEFAULT_MAX_DESCRIPTION_CHARS,
    previous_title_label_column: str = (
        DEFAULT_PREVIOUS_TITLE_LABEL_COLUMN
    ),
    dry_run: bool = False,
):
    """
    Schickt Batch-Jobs für eine Liste von Prompts ab und trägt jeden Job
    sofort als Run in die zentrale Registry ein (status="submitted").

    Neu gegenüber der alten Version:
        - dataset_id / dataset_version: welcher Textkorpus wurde verwendet
        - target_variable: welche Zielgröße wird bewertet (ideology_score, populism_score, ...)
        - validation_basis: "manual" oder "all_statements" -> ersetzt die alte
          Prompt-Nummern-Logik im Auswertungsskript
        - thinking_budget: wird direkt ins JSONL übernommen UND in der Registry
          gespeichert, damit du später nach Thinking Budget filtern kannst
    """
    if model_name not in MODEL_ALIASES:
        raise ValueError(
            f"Unknown model name '{model_name}'. "
            f"Available aliases: {sorted(MODEL_ALIASES)}"
        )
    model_alias = MODEL_ALIASES[model_name]
    if isinstance(prompt_keys, str):
        prompt_keys = [prompt_keys]
    if items_per_request < 1:
        raise ValueError("items_per_request must be at least 1.")
    if max_description_chars < 1:
        raise ValueError("max_description_chars must be at least 1.")

    manifest_dir = Path(manifest_dir)
    batch_input_dir = Path(batch_input_dir)
    batch_input_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(
        csv_path,
        dtype={"video_id": "string"},
        low_memory=False,
    )
    input_rows = len(df)
    rows_to_submit = input_rows
    if input_mode == "title_description":
        description_input = select_title_uncertain_rows(
            df=df,
            previous_title_label_column=previous_title_label_column,
        )
        rows_to_submit = len(description_input)

    print(f"\n{'=' * 60}")
    print(f"Input: '{csv_path}'")
    print(f"Dataset: {dataset_id} ({dataset_version})")
    print(f"Model: {model_alias} | Thinking budget: {thinking_budget}")
    print(f"Target variable: {target_variable} | Validation basis: {validation_basis}")
    print(f"Prompts to run: {len(prompt_keys)} -> {prompt_keys}")
    print(f"Number of input rows: {input_rows}")
    print(f"Number of rows to submit: {rows_to_submit}")
    print(f"Items per model request: {items_per_request}")
    if input_mode == "title_description":
        print(
            "Previous title label column: "
            f"{previous_title_label_column} (only -1 is submitted)"
        )
        print(
            "Maximum description length per video: "
            f"{max_description_chars:,} characters"
        )
    print(f"Grouping seed: {grouping_seed}")
    print(f"Dry run: {dry_run}")
    print(f"{'=' * 60}\n")

    confirmation_text = (
        "Create dry-run files? [Y/n] "
        if dry_run
        else "Start all jobs? [Y/n] "
    )
    answer = input(confirmation_text)
    if answer.strip().lower() != "y":
        print("Aborted.")
        return

    results = {}
    failed = []

    for i, prompt_key in enumerate(prompt_keys, 1):
        prompt_number = get_prompt_number(prompt_key)
        system_prompt = prompts[prompt_key]
        jsonl_path = batch_input_dir / BATCH_INPUT_JSONL_TEMPLATE.format(
            prompt_number=prompt_number,
            model_name=model_name,
        )
        temporary_manifest_path = Path(jsonl_path).with_suffix(
            ".manifest.csv"
        )

        print(f"\n[{i}/{len(prompt_keys)}] Processing {prompt_key}")

        try:
            request_count, video_count = csv_to_jsonl(
                csv_path=csv_path,
                jsonl_path=jsonl_path,
                system_prompt=system_prompt,
                input_mode=input_mode,
                target_variable=target_variable,
                thinking_budget=thinking_budget,
                items_per_request=items_per_request,
                grouping_seed=grouping_seed,
                manifest_path=temporary_manifest_path,
                max_description_chars=max_description_chars,
                previous_title_label_column=(
                    previous_title_label_column
                ),
            )

            if not dry_run:
                job_id = start_batch_job(jsonl_path, model_alias)
            else:
                print(
                    f"[DRY RUN] Created {jsonl_path}; no job was submitted."
                )
                manifest_dir.mkdir(parents=True, exist_ok=True)
                final_manifest_path = None
                if temporary_manifest_path.exists():
                    final_manifest_path = manifest_dir / (
                        f"dry_run_{prompt_number}_{model_name}_manifest.csv"
                    )
                    temporary_manifest_path.replace(final_manifest_path)
                    print(f"Manifest saved to {final_manifest_path}.")

                results[prompt_key] = {
                    "run_id": None,
                    "job_id": None,
                    "status": "dry_run",
                    "requests": request_count,
                    "videos": video_count,
                    "manifest_path": (
                        str(final_manifest_path)
                        if final_manifest_path is not None
                        else None
                    ),
                }
                continue

            run_id = llm_run_store.add_run(
                LLM_RUN_SOURCE,
                prompt_id=prompt_key,
                prompt_number=prompt_number,
                prompt_version=prompt_version,
                model=model_alias,
                thinking_budget=thinking_budget,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                target_variable=target_variable,
                validation_basis=validation_basis,
                job_id=job_id,
                status="submitted",
            )

            final_manifest_path = None
            if temporary_manifest_path.exists():
                manifest_dir.mkdir(parents=True, exist_ok=True)
                final_manifest_path = (
                    manifest_dir / f"{run_id}_manifest.csv"
                )
                temporary_manifest_path.replace(final_manifest_path)
                print(f"Manifest saved to {final_manifest_path}.")

            results[prompt_key] = {
                "run_id": run_id,
                "job_id": job_id,
                "status": "submitted",
                "requests": request_count,
                "videos": video_count,
                "manifest_path": (
                    str(final_manifest_path)
                    if final_manifest_path is not None
                    else None
                ),
            }
            print(f"Registry entry created: {run_id}")

        except Exception as e:
            print(f"Error for {prompt_key}: {e}")
            failed.append(prompt_key)
            results[prompt_key] = {"run_id": None, "job_id": None, "status": f"Error: {e}"}

    print(f"\n{'=' * 60}")
    action = "prepared in dry run" if dry_run else "submitted"
    print(
        f"Summary: {len(prompt_keys) - len(failed)}/{len(prompt_keys)} "
        f"jobs {action} successfully."
    )
    if failed:
        print(f"Failed: {failed}")
    for key, info in results.items():
        status_icon = "✓" if info["status"] in {"submitted", "dry_run"} else "✗"
        print(f"  {status_icon} {key}: {info.get('run_id')} ({info.get('job_id')})")
    print(f"{'=' * 60}\n")

    return results


# ===============================================
# MAIN
# ===============================================

if __name__ == "__main__":
    from youtube_code.llm_analysis.prompts import prompts_title_classification
    from youtube_code.politics_screening.screening_config import (
        BATCH_INPUT_DIR,
        GROUPING_SEED,
        MANIFEST_DIR,
        TITLES_PER_REQUEST,
        DESCRIPTIONS_PER_REQUEST,
    )

    prompts = {"PROMPT_33": prompts_title_classification["PROMPT_33"]}
    PROMPTS_TO_RUN = list(prompts.keys())
    csv_file = Path(
        r"C:\Users\bened\PycharmProjects\youtube_data\outputs\llm\longitudinal"
        r"\description_classification\run_0006_retry.csv"
    )

    run_all_prompts(
        csv_path=csv_file,
        prompt_keys=PROMPTS_TO_RUN,
        prompts=prompts,
        dataset_id="politics_screening_round_002_description_retry",
        input_mode="title_description",
        dataset_version="v1",
        target_variable="politics_title_desc",
        validation_basis="screening_state",
        model_name="gemini_25_flash",
        thinking_budget=0,
        items_per_request=DESCRIPTIONS_PER_REQUEST,
        grouping_seed=GROUPING_SEED,
        batch_input_dir=BATCH_INPUT_DIR,
        manifest_dir=MANIFEST_DIR,
        prompt_version="v1",
        dry_run=False,   # erst prüfen, dann auf False
    )

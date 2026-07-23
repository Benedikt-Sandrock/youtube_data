import os
import json
import uuid
from pathlib import Path

import pandas as pd
from google import genai
from google.cloud import storage

from youtube_code.config import PROJECT_ID, LOCATION, BUCKET_NAME, EXPLORATION, SAMPLES
from .registry.run_registry import RunRegistry
from youtube_code.politics_screening.screening_config import REGISTRY_PATH
# ===============================================
# CONFIG
# ===============================================

BATCH_INPUT_JSONL_TEMPLATE = "batch_input_{prompt_number}_{model_name}.jsonl"
DEFAULT_MANIFEST_DIR = Path("batch_manifests")

MODEL_ALIASES = {
    "gemini_25_flash": "gemini-2.5-flash",
    "gemini_25_pro": "gemini-2.5-pro",
}

registry = RunRegistry(REGISTRY_PATH)
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


def build_input_text(row: pd.Series, input_mode: str) -> str | None:
    title = str(row.get("title", "") or "").strip()
    description = str(row.get("description", "") or "").strip()
    transcript = str(row.get("transcript", "") or "").strip()

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


def build_grouped_title_response_schema(group_size: int) -> dict:
    """Response schema for one request containing several titles."""
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
                        "politics_title": {
                            "type": "INTEGER",
                        },
                    },
                    "required": [
                        "item_id",
                        "politics_title",
                    ],
                    "propertyOrdering": [
                        "item_id",
                        "politics_title",
                    ],
                },
            }
        },
        "required": ["classifications"],
        "propertyOrdering": ["classifications"],
    }


def prepare_title_data(
    df: pd.DataFrame,
    grouping_seed: int,
) -> pd.DataFrame:
    required_columns = {"video_id", "title"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing columns for title classification: {sorted(missing)}"
        )

    data = df.copy()
    data = data.dropna(subset=["video_id", "title"])
    data["video_id"] = data["video_id"].astype("string").str.strip()
    data["title"] = data["title"].astype("string").str.strip()
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


def grouped_titles_to_jsonl(
    df: pd.DataFrame,
    jsonl_path: Path,
    manifest_path: Path,
    system_prompt: str,
    titles_per_request: int,
    grouping_seed: int,
    thinking_budget: int | None,
) -> tuple[int, int]:
    if titles_per_request < 2:
        raise ValueError("titles_per_request must be at least 2 here.")

    data = prepare_title_data(df, grouping_seed)
    if data.empty:
        raise ValueError("No valid videos with titles found.")

    manifest_rows = []
    written_requests = 0

    with jsonl_path.open("w", encoding="utf-8") as output_file:
        for start in range(0, len(data), titles_per_request):
            group = data.iloc[start:start + titles_per_request]
            request_id = f"title_group_{written_requests + 1:06d}"

            group_items = [
                {
                    "item_id": f"item_{position:02d}",
                    "video_id": str(row.video_id),
                    "title": str(row.title),
                }
                for position, row in enumerate(
                    group.itertuples(index=False),
                    start=1,
                )
            ]

            # The model sees only a short identifier. The real YouTube ID is
            # retained exclusively in the manifest and never has to be copied
            # by the model.
            videos = [
                {
                    "item_id": item["item_id"],
                    "title": item["title"],
                }
                for item in group_items
            ]

            input_text = json.dumps(
                {"videos": videos},
                ensure_ascii=False,
                indent=2,
            )

            generation_config = {
                "responseMimeType": "application/json",
                "responseSchema": build_grouped_title_response_schema(
                    group_size=len(videos)
                ),
                "temperature": 0,
            }

            label_schema = (
                generation_config["responseSchema"]
                ["properties"]["classifications"]
                ["items"]["properties"]["politics_title"]
            )

            if label_schema != {"type": "INTEGER"}:
                raise ValueError(
                    "Invalid politics_title schema: "
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
                        "titles_per_request": titles_per_request,
                        "grouping_seed": grouping_seed,
                    }
                )

            written_requests += 1

    pd.DataFrame(manifest_rows).to_csv(
        manifest_path,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"{len(data)} videos written as {written_requests} grouped requests."
    )
    print(f"Manifest saved temporarily to {manifest_path}.")
    return written_requests, len(data)


def csv_to_jsonl(
    csv_path,
    jsonl_path,
    system_prompt,
    input_mode: str,
    thinking_budget: int | None = None,
    titles_per_request: int = 1,
    grouping_seed: int = 42,
    manifest_path: str | Path | None = None,
):
    print(f"Converting CSV to JSONL -> {jsonl_path}")
    df = pd.read_csv(csv_path)

    jsonl_path = Path(jsonl_path)

    if input_mode == "title" and titles_per_request > 1:
        if manifest_path is None:
            manifest_path = jsonl_path.with_suffix(".manifest.csv")
        return grouped_titles_to_jsonl(
            df=df,
            jsonl_path=jsonl_path,
            manifest_path=Path(manifest_path),
            system_prompt=system_prompt,
            titles_per_request=titles_per_request,
            grouping_seed=grouping_seed,
            thinking_budget=thinking_budget,
        )

    if titles_per_request != 1:
        raise ValueError(
            "Grouped requests are currently only implemented for "
            "input_mode='title'."
        )

    written_requests = 0

    with jsonl_path.open("w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            video_id = str(row["video_id"])
            input_text = build_input_text(row, input_mode)

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

    manifest_dir = Path(manifest_dir)
    batch_input_dir = Path(batch_input_dir)
    batch_input_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(csv_path)
    input_rows = len(df)

    print(f"\n{'=' * 60}")
    print(f"Input: '{csv_path}'")
    print(f"Dataset: {dataset_id} ({dataset_version})")
    print(f"Model: {model_alias} | Thinking budget: {thinking_budget}")
    print(f"Target variable: {target_variable} | Validation basis: {validation_basis}")
    print(f"Prompts to run: {len(prompt_keys)} -> {prompt_keys}")
    print(f"Number of input rows: {input_rows}")
    print(f"Items per model request: {items_per_request}")
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
                thinking_budget=thinking_budget,
                titles_per_request=items_per_request,
                grouping_seed=grouping_seed,
                manifest_path=temporary_manifest_path,
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

            run_id = registry.add_run(
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
    # --- Specify prompts to import ---
    from youtube_code.llm_analysis.prompts import prompts_populism_all

    prompts = {"PROMPT_28": prompts_populism_all["PROMPT_28"]}
    PROMPTS_TO_RUN = list(prompts.keys())
    #csv_file = EXPLORATION / "training_data" /"sample_vids_41"
    csv_file = SAMPLES / "combined" / "keyword_videos_50k_channels.csv"

    run_all_prompts(
        csv_path= csv_file,
        prompt_keys=PROMPTS_TO_RUN,
        prompts=prompts,
        dataset_id= csv_file.stem,
        input_mode= "transcript",
        dataset_version="v1",
        target_variable="populism_score",
        validation_basis="all_statements",  # ["manual", "all_statements"]
        model_name="gemini_25_flash",
        thinking_budget=0,   # None means no limit is specified. In this case, the models decides flexibly how many
                             # tokens it uses (up to 8192).
        prompt_version="v1",
        dry_run=False,
    )

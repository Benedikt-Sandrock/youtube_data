import os
import json
import pandas as pd
from google import genai
from google.cloud import storage

from youtube_code.config import PROJECT_ID, LOCATION, BUCKET_NAME, EXPLORATION, SAMPLES
from registry.run_registry import RunRegistry

# ===============================================
# CONFIG
# ===============================================

REGISTRY_PATH = "registry/runs_registry.csv"
BATCH_INPUT_JSONL_TEMPLATE = "batch_input_{prompt_number}_{model_name}.jsonl"

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


def csv_to_jsonl(csv_path, jsonl_path, system_prompt, thinking_budget: int | None = None):
    print(f"Converting CSV to JSONL -> {jsonl_path}")
    df = pd.read_csv(csv_path)

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            v_id = str(row["video_id"])
            transcript = str(row.get("transcript", ""))

            if not transcript.strip():
                continue

            generation_config = {
                "responseMimeType": "application/json",
                "temperature": 0,
            }
            if thinking_budget is not None:
                generation_config["thinkingConfig"] = {"thinkingBudget": thinking_budget}

            api_request = {
                "custom_id": v_id,
                "request": {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": f"{system_prompt}\n\nHier ist das Transkript:\n\n{transcript}"}],
                        }
                    ],
                    "generationConfig": generation_config,
                },
            }
            f.write(json.dumps(api_request, ensure_ascii=False) + "\n")

    print(f"File {jsonl_path} was successfully created.")
    return True


def start_batch_job(jsonl_path, model):
    print(f"Uploading {jsonl_path} to GCS...")
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)

    blob_name = f"batch_inputs/{jsonl_path}"
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(jsonl_path)

    gcs_uri = f"gs://{BUCKET_NAME}/{blob_name}"
    print("File successfully uploaded.")

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
    validation_basis: str = "manual",
    model_name: str = "gemini_25_flash",
    thinking_budget: int | None = None,
    prompt_version: str = "v1",
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
    model_alias = MODEL_ALIASES.get(model_name, "unknown_model")
    if isinstance(prompt_keys, str):
        prompt_keys = [prompt_keys]
    list_name = f"{prompts=}".split("=")[0]

    df = pd.read_csv(csv_path)
    transcripts = len(df)

    print(f"\n{'=' * 60}")
    print(f"Input: '{csv_path}'")
    print(f"Dataset: {dataset_id} ({dataset_version})")
    print(f"Model: {model_alias} | Thinking budget: {thinking_budget}")
    print(f"Target variable: {target_variable} | Validation basis: {validation_basis}")
    print(f"Prompts to run: {len(prompt_keys)} -> {prompt_keys}")
    print(f"Number of transcripts to be rated: {transcripts}")
    print(f"Dry run: {dry_run}")
    print(f"{'=' * 60}\n")

    answer = input("Start all jobs? [Y/n] ")
    if answer.strip().lower() != "y":
        print("Aborted.")
        return

    results = {}
    failed = []

    for i, prompt_key in enumerate(prompt_keys, 1):
        prompt_number = get_prompt_number(prompt_key)
        system_prompt = prompts[prompt_key]
        jsonl_path = BATCH_INPUT_JSONL_TEMPLATE.format(
            prompt_number=prompt_number, model_name=model_name
        )

        print(f"\n[{i}/{len(prompt_keys)}] Processing {prompt_key}")

        try:
            if not dry_run:
                csv_to_jsonl(csv_path, jsonl_path, system_prompt, thinking_budget)
                job_id = start_batch_job(jsonl_path, model_alias)
            else:
                print(f"[DRY RUN] Would create {jsonl_path} and submit job.")
                job_id = f"dry-run-job-{prompt_number}"

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

            results[prompt_key] = {"run_id": run_id, "job_id": job_id, "status": "submitted"}
            print(f"Registry entry created: {run_id}")

        except Exception as e:
            print(f"Error for {prompt_key}: {e}")
            failed.append(prompt_key)
            results[prompt_key] = {"run_id": None, "job_id": None, "status": f"Error: {e}"}

    print(f"\n{'=' * 60}")
    print(f"Summary: {len(prompt_keys) - len(failed)}/{len(prompt_keys)} jobs submitted successfully.")
    if failed:
        print(f"Failed: {failed}")
    for key, info in results.items():
        status_icon = "✓" if info["status"] == "submitted" else "✗"
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
        dataset_version="v1",
        target_variable="populism_score",
        validation_basis="all_statements",  # ["manual", "all_statements"]
        model_name="gemini_25_flash",
        thinking_budget=0,   # None means no limit is specified. In this case, the models decides flexibly how many
                             # tokens it uses (up to 8192).
        prompt_version="v1",
        dry_run=False,
    )

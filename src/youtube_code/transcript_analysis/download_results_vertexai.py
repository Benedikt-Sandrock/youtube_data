import os
import shutil
import json
import pandas as pd
from pathlib import Path
from google import genai
from google.cloud import storage

from youtube_code.config import OUTPUT_GEMINI, PROJECT_ID, LOCATION

# ============================================================
# CONFIG
# ============================================================

seed_number = "pi_total"

SAVE_FORMAT = "CSV"
OUTPUT_EXCEL_BASE = OUTPUT_GEMINI / f"classification_{seed_number}" / "classification_results"
ID_FILES_DIR = Path("id_files")
ID_FILES_DONE_DIR = Path("id_files_done")

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
storage_client = storage.Client(project=PROJECT_ID)


# ============================================================
# HELPERS
# ============================================================

def saving_results(output_uri: str, output_path: str, save_format):
    """Download JSONL from GCS and save as Excel/CSV."""
    print(f"  Downloading results from {output_uri}...")

    uri_parts = output_uri.replace("gs://", "").split("/", 1)
    bucket_name = uri_parts[0]
    blob_name = uri_parts[1]

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    content = blob.download_as_text()

    results = []
    for i, line in enumerate(content.strip().split("\n")):
        if not line:
            continue
        try:
            data = json.loads(line)
            v_id = data.get("custom_id", "unknown")

            if i == 0:
                print(f"\n  --- DEBUG INFO FOR VIDEO: {v_id} ---")
                print("  Main levels in JSON:", list(data.keys()))
                if "response" in data and isinstance(data["response"], dict):
                    print("  Levels below 'response':", list(data["response"].keys()))
                print("  ------------------------------------\n")

            if "error" in data:
                print(f"  Error for video {v_id}: {data['error']}")
                results.append({"video_id": v_id, "error": str(data["error"])})
                continue

            try:
                response_obj = data.get("response", {})
                if "candidates" in response_obj:
                    response_text = response_obj["candidates"][0]["content"]["parts"][0]["text"]
                elif "generateContentResponse" in response_obj:
                    response_text = response_obj["generateContentResponse"]["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    print(f"  Safety filter or unknown format for {v_id}.")
                    results.append({"video_id": v_id, "error": "No answer (Safety Filter)"})
                    continue

                parsed_response = json.loads(response_text)

            except json.JSONDecodeError:
                from json_repair import repair_json
                try:
                    repaired_string = repair_json(response_text)
                    parsed_response = json.loads(repaired_string)
                    print(f"  Repaired JSON for video {v_id}.")
                except json.JSONDecodeError as inner_e:
                    print(f"  CRITICAL: Could not repair JSON for {v_id}: {inner_e}")
                    parsed_response = {"error": "Formatting error", "raw_text": response_text}

            except (KeyError, IndexError) as e:
                print(f"  Could not process answer for {v_id}: {e}")
                parsed_response = {"error": "Formatting error"}

            row_data = {"video_id": v_id}
            row_data.update(parsed_response)
            results.append(row_data)

        except Exception as e:
            print(f"  Error reading row: {e}")

    df = pd.DataFrame(results)


    if save_format == "CSV":
        df.to_csv(output_path, index = False)
    else:
        df.to_excel(output_path, index=False)
    print(f"  ✓ Saved: {output_path}")


def find_output_url(status_job) -> str | None:
    """Find the prediction JSONL output file in GCS."""
    output_folder = status_job.output_info.gcs_output_directory
    path_parts = output_folder.replace("gs://", "").split("/", 1)
    bucket_name = path_parts[0]
    prefix = path_parts[1]

    bucket = storage_client.bucket(bucket_name)
    blobs = list(bucket.list_blobs(prefix=prefix))

    for blob in blobs:
        if blob.name.endswith(".jsonl") and "prediction" in blob.name.lower():
            return f"gs://{bucket_name}/{blob.name}"
    return None


def process_id_file(id_file_path: Path, save_format = "CSV") -> str:
    """
    Check job status and download results if ready.
    Returns: 'downloaded', 'pending', 'failed', 'skipped', 'error'
    """
    try:
        lines = id_file_path.read_text().splitlines()
        job_id = lines[0]
        prompt_number = lines[1]
        model_alias = lines[2]
    except (IndexError, FileNotFoundError) as e:
        print(f"  Could not read ID file {id_file_path.name}: {e}")
        return "error"

    csv_path = f"{OUTPUT_EXCEL_BASE}_{prompt_number}_{model_alias}.csv"
    excel_path = f"{OUTPUT_EXCEL_BASE}_{prompt_number}_{model_alias}.xlsx"

    if save_format == "CSV":
        output_path = csv_path
    else:
        output_path = excel_path

    print(f"\n[{id_file_path.name}]  Prompt: {prompt_number} | Model: {model_alias}")

    try:
        status_job = client.batches.get(name=job_id)
        current_state = status_job.state.name if hasattr(status_job.state, "name") else str(status_job.state)
        print(f"  Status: {current_state}")
    except Exception as e:
        print(f"  Could not fetch job status: {e}")
        return "error"

    if current_state in ["JOB_STATE_FAILED", "JOB_STATE_CANCELLED"]:
        print(f"  ✗ Job failed/cancelled.")
        if hasattr(status_job, "error") and status_job.error:
            print(f"  Original error: {status_job.error}")
        return "failed"

    elif current_state == "JOB_STATE_SUCCEEDED":
        if os.path.exists(output_path):
            print(f"  Output file already exists: {output_path}")
            answer = input("  Overwrite? [y/N] ")
            if answer.lower() != "y":
                print("  Skipping.")
                return "skipped"

        output_url = find_output_url(status_job)
        if not output_url:
            print("  ✗ No prediction JSONL found in GCS output folder.")
            return "error"

        saving_results(output_url, output_path, SAVE_FORMAT)

        # Move ID file to done folder
        ID_FILES_DONE_DIR.mkdir(exist_ok=True)
        dest = ID_FILES_DONE_DIR / id_file_path.name
        shutil.move(str(id_file_path), str(dest))
        print(f"  ✓ ID file moved to: {dest}")
        return "downloaded"

    else:
        print(f"  Still running – skipping.")
        return "pending"


# ============================================================
# MAIN
# ============================================================

def main():
    id_files = sorted(ID_FILES_DIR.glob("job_id_*.txt"))

    if not id_files:
        print(f"No ID files found in '{ID_FILES_DIR}/'.")
        return

    print(f"\n{'='*60}")
    print(f"Found {len(id_files)} ID file(s) to check:")
    for f in id_files:
        print(f"  {f.name}")
    print(f"{'='*60}")

    answer = input("\nCheck all and download finished results? [Y/n] ")
    if answer.strip().lower() != "y":
        print("Aborted.")
        return

    summary = {"downloaded": [], "pending": [], "failed": [], "skipped": [], "error": []}

    for id_file_path in id_files:
        result = process_id_file(id_file_path, SAVE_FORMAT)
        summary[result].append(id_file_path.name)

    # Summary
    print(f"\n{'='*60}")
    print("Summary:")
    print(f"  ✓ Downloaded : {len(summary['downloaded'])}  {summary['downloaded']}")
    print(f"  ⏳ Pending   : {len(summary['pending'])}  {summary['pending']}")
    print(f"  ✗ Failed     : {len(summary['failed'])}  {summary['failed']}")
    print(f"  ⊘ Skipped    : {len(summary['skipped'])}  {summary['skipped']}")
    print(f"  ! Errors     : {len(summary['error'])}  {summary['error']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
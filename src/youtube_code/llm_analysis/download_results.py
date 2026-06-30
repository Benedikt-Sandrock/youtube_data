import json
import pandas as pd
from google import genai
from google.cloud import storage

from youtube_code.config import OUTPUT_GEMINI, PROJECT_ID, LOCATION
from registry.run_registry import RunRegistry

# ============================================================
# CONFIG
# ============================================================

REGISTRY_PATH = "registry/runs_registry.csv"
RESULTS_DIR = OUTPUT_GEMINI / "results"
SAVE_FORMAT = "CSV"

registry = RunRegistry(REGISTRY_PATH)
client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
storage_client = storage.Client(project=PROJECT_ID)


# ============================================================
# HELPERS
# ============================================================

def saving_results(output_uri: str, output_path: str, save_format: str):
    """Download JSONL from GCS and save as CSV/Excel. (unverändert ggü. Original)"""
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
        df.to_csv(output_path, index=False)
    else:
        df.to_excel(output_path, index=False)
    print(f"  ✓ Saved: {output_path}")


def find_output_url(status_job) -> str | None:
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


def process_run(run_id: str, save_format: str = "CSV") -> str:
    """
    Prüft den Job-Status für einen Run aus der Registry und lädt die
    Ergebnisse herunter, falls fertig. Aktualisiert Status + results_path
    direkt in der Registry -- kein separates id_files/done-Verschieben mehr nötig.
    """
    run = registry.get_run(run_id)
    job_id = run["job_id"]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    extension = "csv" if save_format == "CSV" else "xlsx"
    output_path = RESULTS_DIR / f"{run_id}.{extension}"

    print(f"\n[{run_id}]  Prompt: {run['prompt_id']} | Model: {run['model']} "
          f"| Dataset: {run['dataset_id']} ({run['dataset_version']})")

    try:
        status_job = client.batches.get(name=job_id)
        current_state = status_job.state.name if hasattr(status_job.state, "name") else str(status_job.state)
        print(f"  Status: {current_state}")
    except Exception as e:
        print(f"  Could not fetch job status: {e}")
        return "error"

    if current_state in ["JOB_STATE_FAILED", "JOB_STATE_CANCELLED"]:
        print("  ✗ Job failed/cancelled.")
        print(f"Error: {status_job.error}")
        registry.update_run(run_id, status="failed")
        return "failed"

    elif current_state == "JOB_STATE_SUCCEEDED":
        if output_path.exists():
            print(f"  Output file already exists: {output_path}")
            answer = input("  Overwrite? [y/N] ")
            if answer.lower() != "y":
                print("  Skipping.")
                return "skipped"

        output_url = find_output_url(status_job)
        if not output_url:
            print("  ✗ No prediction JSONL found in GCS output folder.")
            registry.update_run(run_id, status="error")
            return "error"

        saving_results(output_url, str(output_path), save_format)
        registry.update_run(run_id, status="downloaded", results_path=str(output_path))
        print(f"  ✓ Registry updated for {run_id}")
        return "downloaded"

    else:
        print("  Still running – skipping.")
        return "pending"


# ============================================================
# MAIN
# ============================================================

def main():
    open_runs = registry.get_runs(status="submitted")

    if open_runs.empty:
        print("Keine offenen Runs (status='submitted') in der Registry gefunden.")
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

    summary = {"downloaded": [], "pending": [], "failed": [], "skipped": [], "error": []}

    for run_id in open_runs["run_id"]:
        result = process_run(run_id, SAVE_FORMAT)
        summary[result].append(run_id)

    print(f"\n{'=' * 60}")
    print("Summary:")
    print(f"  ✓ Downloaded : {len(summary['downloaded'])}  {summary['downloaded']}")
    print(f"  ⏳ Pending   : {len(summary['pending'])}  {summary['pending']}")
    print(f"  ✗ Failed     : {len(summary['failed'])}  {summary['failed']}")
    print(f"  ⊘ Skipped    : {len(summary['skipped'])}  {summary['skipped']}")
    print(f"  ! Errors     : {len(summary['error'])}  {summary['error']}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()

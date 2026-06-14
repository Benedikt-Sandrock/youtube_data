from dotenv import load_dotenv
import os
from google import genai
import pandas as pd
import json
from google.cloud import storage
from api_request_vertexai import prompt_number, model_name

OUTPUT_EXCEL = "downloaded_results/classification_results"

id_file = f"job_id_{prompt_number}_{model_name}.txt"

load_dotenv()
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = "us-central1"

client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION
)

storage_client = storage.Client(project=PROJECT_ID)

def saving_results(output_uri, excel_path):
    print("Downloading and formatting results from Cloud Storage...")

    uri_parts = output_uri.replace("gs://", "").split("/", 1)
    bucket_name = uri_parts[0]
    blob_name = uri_parts[1]

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    content = blob.download_as_text()

    results = []
    # use of enumerate to get a counter for lines
    for i, line in enumerate(content.strip().split("\n")):
        if not line:
            continue

        try:
            data = json.loads(line)

            v_id = data.get("custom_id", "unknown")

            # --- DEBUG INFO (ONLY FOR THE FIRST VIDEO) ---
            if i == 0:
                print(f"\n--- DEBUG INFO FOR VIDEO: {v_id} ---")
                print("Main levels in JSON:", list(data.keys()))
                if "response" in data and isinstance(data["response"], dict):
                    print("Levels below 'response':", list(data["response"].keys()))
                print("--------------------------------------\n")

            if "error" in data:
                print(f"Error for video {v_id}: {data['error']}")
                results.append({"video_id": v_id, "error": str(data["error"])})
                continue

            # Reading the model answer
            try:
                response_obj = data.get("response", {})

                # Case A: Normal format
                if "candidates" in response_obj:
                    response_text = response_obj["candidates"][0]["content"]["parts"][0]["text"]

                # Case B: Nested format by Vertex AI
                elif "generateContentResponse" in response_obj:
                    response_text = response_obj["generateContentResponse"]["candidates"][0]["content"]["parts"][0][
                        "text"]

                # Case C: Safety-Filter-Block
                else:
                    # Print everything we get from Google
                    print(f"DEBUG-INFO for {v_id}: Complete content of 'data': {json.dumps(data, indent=2)}")

                    results.append({"video_id": v_id, "error": "No answer (Safety Filter)"})
                    continue

                parsed_response = json.loads(response_text)

            except json.JSONDecodeError as e:
                from json_repair import repair_json

                try:
                    repaired_string = repair_json(response_text)
                    parsed_response = json.loads(repaired_string)
                    print(f"Successfully repaired JSON for video {v_id} using json_repair.")
                except json.JSONDecodeError as inner_e:
                    print(f"CRITICAL: Couldn't process answer for {v_id} even after robust repair: {inner_e}")
                    parsed_response = {"error": "Formatting error", "raw_text": response_text}

            except (KeyError, IndexError) as e:
                print(f"Couldn't process answer for {v_id}: {e}")
                parsed_response = {"error": "Formatting error"}

                print(f"\n--- DEBUG INFO FOR VIDEO: {v_id} ---")
                print("Main levels in JSON:", list(data.keys()))
                if "response" in data and isinstance(data["response"], dict):
                    print("Levels below 'response':", list(data["response"].keys()))
                print(f"Raw Model Response text:\n{response_text}")
                print("--------------------------------------\n")

            row_data = {"video_id": v_id}
            row_data.update(parsed_response)
            results.append(row_data)

        except Exception as e:
            print(f"Error when reading a row: {e}")

    print("Saving data in excel file...")
    df = pd.DataFrame(results)
    df.to_excel(excel_path, index=False)
    print(f"Success! Results saved under: {excel_path}")



if __name__ == "__main__":

    print(f"ID file: '{id_file}'")
    answer = input("ID file correct? [y/n]")

    if not answer.lower() == "y":
        print("Wrong ID file.")
        exit()

    with open(id_file, "r") as f:
        lines = f.read().splitlines()

    job_id = lines[0]
    prompt_number = lines[1]
    model_number = lines[2]

    status_job = client.batches.get(name = job_id)
    OUTPUT_EXCEL = f"{OUTPUT_EXCEL}_{prompt_number}_{model_number}.xlsx"

    current_state = status_job.state.name if hasattr(status_job.state, "name") else str(status_job.state)
    print(f"Current status: {current_state}")

    if current_state in ["JOB_STATE_FAILED", "JOB_STATE_CANCELLED"]:
        print(f"Error. Status: {current_state}")

        if hasattr(status_job, "error") and status_job.error:
            print(f"Original error: {status_job.error}")

    elif current_state == "JOB_STATE_SUCCEEDED":
        print("Analysis ready. Downloading results.")

        output_folder = status_job.output_info.gcs_output_directory

        path_parts = output_folder.replace("gs://", "").split("/", 1)
        bucket_name = path_parts[0]
        prefix = path_parts[1]

        bucket = storage_client.bucket(bucket_name)
        blobs = list(bucket.list_blobs(prefix = prefix))

        output_url = None
        for blob in blobs:
            if blob.name.endswith(".jsonl") and "prediction" in blob.name.lower():
                output_url = f"gs://{bucket_name}/{blob.name}"
                break

        if output_url:
            if os.path.exists(OUTPUT_EXCEL):
                answer = input(f"Warning: File in output path ('{OUTPUT_EXCEL}') already exsits."
                               f"\nMake sure that no important file is overwritten."
                               f"\nContinue? [Y/n]")
                if answer.lower() == "y":
                    saving_results(output_url, OUTPUT_EXCEL)
                    print("Output saved to excel.")
                else:
                    print("Stopping Script. No file is saved. Make sure to use the right output path.")
            else:
                saving_results(output_url, OUTPUT_EXCEL)
                print("Output saved to excel.")


    else:
        print(f"Analysis not done yet. Status: {current_state}")
        if hasattr(status_job, "error") and status_job.error:
            print(f"Original error: {status_job.error}")
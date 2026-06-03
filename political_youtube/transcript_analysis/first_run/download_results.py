from dotenv import load_dotenv
import os
from google import genai
import pandas as pd
import json
from google.cloud import storage

OUTPUT_EXCEL = "classification_results.xlsx"

load_dotenv()
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = "us-central1"

client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION
)


def saving_results(output_uri, excel_path):
    print("Downloading and formatting results from Cloud Storage...")

    uri_parts = output_uri.replace("gs://", "").split("/", 1)
    bucket_name = uri_parts[0]
    blob_name = uri_parts[1]

    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    content = blob.download_as_text()

    results = []
    # enumerate gibt uns einen Zähler (i) für die Zeilen mit
    for i, line in enumerate(content.strip().split("\n")):
        if not line:
            continue

        try:
            data = json.loads(line)

            # 1. KORREKTUR: Die Video-ID liegt direkt auf der Hauptebene!
            v_id = data.get("custom_id", "Unbekannt")

            # --- DEBUG-INFO FÜR DAS ERSTE VIDEO ---
            if i == 0:
                print(f"\n--- DEBUG INFO FÜR VIDEO: {v_id} ---")
                print("Hauptebenen im JSON:", list(data.keys()))
                if "response" in data and isinstance(data["response"], dict):
                    print("Ebenen unter 'response':", list(data["response"].keys()))
                print("--------------------------------------\n")

            if "error" in data:
                print(f"Fehler bei Video {v_id}: {data['error']}")
                results.append({"video_id": v_id, "error": str(data["error"])})
                continue

            # 2. Die Modellantwort auslesen (mit Absicherung)
            try:
                response_obj = data.get("response", {})

                # Möglichkeit A: Normales Format
                if "candidates" in response_obj:
                    response_text = response_obj["candidates"][0]["content"]["parts"][0]["text"]

                # Möglichkeit B: Verschachteltes Format von Vertex AI
                elif "generateContentResponse" in response_obj:
                    response_text = response_obj["generateContentResponse"]["candidates"][0]["content"]["parts"][0][
                        "text"]

                # Möglichkeit C: Wahrscheinlich ein Safety-Filter-Block!
                else:

                    # HIER DRUCKEN WIR ALLES AUS, WAS WIR VON GOOGLE BEKOMMEN
                    print(f"DEBUG-INFO für {v_id}: Kompletter Inhalt von 'data': {json.dumps(data, indent=2)}")

                    results.append({"video_id": v_id, "error": "Keine Antwort erhalten (ggf. Safety Filter)"})
                    continue

                parsed_response = json.loads(response_text)

            except (KeyError, IndexError, json.JSONDecodeError) as e:
                print(f"Konnte Antwort für {v_id} nicht verarbeiten: {e}")
                parsed_response = {"error": "Formatierungsfehler"}

            row_data = {"video_id": v_id}
            row_data.update(parsed_response)
            results.append(row_data)

        except Exception as e:
            print(f"Allgemeiner Fehler beim Lesen einer Zeile: {e}")

    print("Speichere Daten in Excel-Datei...")
    df = pd.DataFrame(results)
    df.to_excel(excel_path, index=False)
    print(f"Erfolg! Die Ergebnisse wurden gespeichert unter: {excel_path}")



if __name__ == "__main__":

    with open("job_id.txt", "r") as f:
        job_id = f.read().strip()

    status_job = client.batches.get(name = job_id)

    current_state = status_job.state.name if hasattr(status_job.state, "name") else str(status_job.state)
    print(f"Current status: {current_state}")

    if current_state in ["JOB_STATE_FAILED", "JOB_STATE_CANCELLED"]:
        print(f"Error. Status: {current_state}")

        if hasattr(status_job, "error") and status_job.error:
            print(f"Original error: {status_job.error}")
    elif current_state == "JOB_STATE_SUCCEEDED":
        print("Analysis ready. Downloading results.")

        output_folder = status_job.output_info.gcs_output_directory
        storage_client = storage.Client(project = PROJECT_ID)

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
            answer = input(f"Is this the correct path?"
                           f"\n'{OUTPUT_EXCEL}'"
                           f"\nMake sure that no file is overwritten."
                           f"\nContinue? [Y/n]")
            if answer.lower() == "y":
                saving_results(output_url, OUTPUT_EXCEL)
                print("Output saved to excel.")
            else:
                print("No file is saved. Make sure to use the right output path.")



    else:
        print(f"Analysis not done yet. Status: {current_state}")
        if hasattr(status_job, "error") and status_job.error:
            print(f"Original error: {status_job.error}")
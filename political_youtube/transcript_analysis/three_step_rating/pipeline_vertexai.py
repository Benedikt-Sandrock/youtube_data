from dotenv import load_dotenv
import os
import json
import time
import pandas as pd
from google import genai
from google.cloud import storage

load_dotenv()
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = "us-central1"
BUCKET_NAME = os.getenv("GCP_BUCKET_NAME")

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
storage_client = storage.Client(project=PROJECT_ID)

# ==================================
# Configuration
# ==================================

INPUT_CSV = "test_transcripts.csv"
MODEL_NAME = "gemini-2.5-flash"
OUTPUT_EXCEL = "downloaded_results/classification_results_9_g25_f.xlsx"

# How often and how long to poll for batch job results
POLL_INTERVAL_SECONDS = 150
MAX_POLL_ATTEMPTS = 20  # 20 attempts * 150s = up to 50 minutes per step

PROMPTS = {
    "step_1_extraction": """Du erhältst das Transkript eines deutschen YouTube-Videos.

Deine Aufgabe ist ausschließlich die Extraktion politisch relevanter Signale. Führe keine Bewertung der politischen Position oder des Populismus durch.

WICHTIG:
- Beschreibe nur Aussagen des Creators.
- Bei Reaction-Videos dürfen Aussagen Dritter nur berücksichtigt werden, wenn der Creator ihnen ausdrücklich zustimmt, sie verteidigt oder positiv paraphrasiert.
- Verwende möglichst kurze Stichpunkte.
- Wenn etwas nicht vorkommt, schreibe "Keine erkennbaren Aussagen".

Gib ausschließlich folgendes JSON zurück:

{
  "video_type": "Reaction oder Standard",
  "political_topics": ["..."],
  "positive_targets": ["Personen, Gruppen, Institutionen oder Ideen, die positiv dargestellt werden"],
  "negative_targets": ["Personen, Gruppen, Institutionen oder Ideen, die negativ dargestellt werden"],
  "problem_descriptions": ["Welche gesellschaftlichen Probleme beschreibt der Creator?"],
  "proposed_solutions": ["Welche Lösungen schlägt der Creator vor?"],
  "economic_signals": ["Marktwirtschaft, Umverteilung, Sozialstaat, Regulierung, Steuern usw."],
  "cultural_signals": ["Migration, Identität, Diversität, Tradition, Familie, Nation usw."],
  "state_signals": ["Aussagen über Staat, Behörden, Regulierung oder Eingriffe"],
  "media_signals": ["Aussagen über Medien, Journalisten oder Berichterstattung"],
  "elite_signals": ["Aussagen über politische Eliten, Establishment oder Machtgruppen"],
  "institution_trust": ["Vertrauen oder Misstrauen gegenüber Institutionen"]
}""",

    "step_2_ideology": """Du erhältst die strukturierte Extraktion eines YouTube-Videos.

Bewerte die politische Ideologie so, wie ein durchschnittlicher politisch interessierter deutscher Zuschauer den Creator nach dem Konsum des Videos wahrnehmen würde.

WICHTIG:
- Bewerte den Gesamteindruck.
- Berücksichtige Themenauswahl, Framing, positive und negative Bezugspunkte sowie konkrete Forderungen.
- Nicht nur politische Lösungen zählen.
- Wiederkehrende Narrative dürfen berücksichtigt werden.
- Populismus ist KEINE Ideologie.
- Elitenkritik allein verschiebt den Wert nicht nach links oder rechts.

Skala:
0.0 = extrem links
1.0 = sehr links
2.0 = klar links
3.0 = moderat links
4.0 = leicht links
5.0 = politisch neutral, ausgewogen oder nicht eindeutig einordenbar
6.0 = leicht rechts
7.0 = moderat rechts
8.0 = klar rechts
9.0 = sehr rechts
10.0 = extrem rechts

Sonderregel: Wenn das Video keine erkennbaren politischen oder gesellschaftlichen Inhalte enthält, gib -1.0 zurück.

Gib ausschließlich folgendes JSON zurück:

{
  "ideology_score": 0.0,
  "ideology_reason": "Maximal zwei kurze Sätze."
}""",

    "step_3_populism": """Du erhältst die strukturierte Extraktion eines YouTube-Videos.

Bewerte den Populismusgrad so, wie ein durchschnittlicher deutscher Zuschauer die Kommunikation wahrnehmen würde.

Populismus ist unabhängig von linker oder rechter Ideologie.

Berücksichtige ausschließlich:
- Volk-vs-Elite-Framing
- Anti-Establishment-Rhetorik
- Pauschale Elitenkritik
- Misstrauen gegenüber Institutionen
- Misstrauen gegenüber Medien
- Darstellung des Volkes als moralisch überlegen
- Darstellung von Eliten als korrupt, eigennützig oder volksfern
- Behauptungen, dass etablierte Institutionen systematisch gegen normale Bürger arbeiten

Nicht berücksichtigen:
- Konservativ oder progressiv sein
- Wirtschaftspolitische Positionen
- Migration, Klima oder Sozialpolitik an sich
- Reine Sachkritik ohne Volk-vs-Elite-Element

Skala:
0.0 = keinerlei populistische Kommunikation
2.0 = gelegentliche Kritik an Institutionen
4.0 = wiederkehrende Systemkritik
6.0 = deutliches Establishment-vs-Bürger-Framing
8.0 = starkes Volk-vs-Elite-Narrativ
10.0 = nahezu vollständiges Weltbild basiert auf korrupten Eliten gegen das Volk

Sonderregel: Wenn das Video keinerlei politische oder gesellschaftliche Inhalte enthält, gib -1.0 zurück.

Gib ausschließlich folgendes JSON zurück:

{
  "populism_score": 0.0,
  "populism_reason": "Maximal zwei kurze Sätze."
}""",
}


# ==================================
# Helper: CSV -> JSONL
# ==================================

def csv_to_jsonl(input_data: list[dict], prompt: str, jsonl_path: str):
    """
    input_data: list of dicts with keys "video_id" and "content".
    "content" is either the raw transcript (step 1) or the JSON extraction result (steps 2 & 3).
    """
    print(f"  Writing {len(input_data)} entries to {jsonl_path}...")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for item in input_data:
            api_request = {
                "custom_id": item["video_id"],
                "request": {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": f"{prompt}\n\nHier sind die Daten:\n\n{item['content']}"}],
                        }
                    ],
                    "generationConfig": {
                        "responseMimeType": "application/json",
                        "temperature": 0,
                    },
                },
            }
            f.write(json.dumps(api_request, ensure_ascii=False) + "\n")


# ==================================
# Helper: Upload JSONL + start job
# ==================================

def start_batch_job(jsonl_path: str, step_label: str) -> str:
    blob_name = f"batch_inputs/{step_label}_{jsonl_path}"
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(jsonl_path)
    gcs_uri = f"gs://{BUCKET_NAME}/{blob_name}"
    print(f"  Uploaded to {gcs_uri}")

    job = client.batches.create(model=MODEL_NAME, src=gcs_uri)
    print(f"  Job started: {job.name}")
    return job.name


# ==================================
# Helper: Poll until done
# ==================================

def wait_for_job(job_id: str) -> object:
    print(f"  Polling job {job_id} ...")
    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        job = client.batches.get(name=job_id)
        state = job.state.name if hasattr(job.state, "name") else str(job.state)

        if state == "JOB_STATE_SUCCEEDED":
            print(f"  Job succeeded after {attempt} poll(s).")
            return job
        elif state in ("JOB_STATE_FAILED", "JOB_STATE_CANCELLED"):
            raise RuntimeError(f"Job {job_id} ended with state: {state}. Error: {getattr(job, 'error', 'unknown')}")
        else:
            print(f"  [{attempt}/{MAX_POLL_ATTEMPTS}] State: {state} – waiting {POLL_INTERVAL_SECONDS}s ...")
            time.sleep(POLL_INTERVAL_SECONDS)

    raise TimeoutError(f"Job {job_id} did not finish within the allotted time.")


# ==================================
# Helper: Download + parse results
# ==================================

def download_results(job: object) -> dict[str, dict]:
    """Returns a dict mapping video_id -> parsed JSON response."""
    output_folder = job.output_info.gcs_output_directory
    path_parts = output_folder.replace("gs://", "").split("/", 1)
    bucket_name, prefix = path_parts[0], path_parts[1]

    bucket = storage_client.bucket(bucket_name)
    blobs = list(bucket.list_blobs(prefix=prefix))

    output_blob = None
    for blob in blobs:
        if blob.name.endswith(".jsonl") and "prediction" in blob.name.lower():
            output_blob = blob
            break

    if output_blob is None:
        raise FileNotFoundError("Could not find prediction JSONL in output folder.")

    content = output_blob.download_as_text()
    results = {}

    for line in content.strip().split("\n"):
        if not line:
            continue
        data = json.loads(line)
        v_id = data.get("custom_id", "unknown")

        if "error" in data:
            print(f"  Warning: Error for {v_id}: {data['error']}")
            results[v_id] = {"error": str(data["error"])}
            continue

        response_obj = data.get("response", {})
        try:
            if "candidates" in response_obj:
                text = response_obj["candidates"][0]["content"]["parts"][0]["text"]
            elif "generateContentResponse" in response_obj:
                text = response_obj["generateContentResponse"]["candidates"][0]["content"]["parts"][0]["text"]
            else:
                print(f"  Warning: Unexpected response structure for {v_id}")
                results[v_id] = {"error": "Unexpected response structure"}
                continue

            results[v_id] = json.loads(text)

        except (KeyError, IndexError, json.JSONDecodeError) as e:
            print(f"  Warning: Could not parse response for {v_id}: {e}")
            results[v_id] = {"error": f"Parse error: {e}"}

    print(f"  Downloaded {len(results)} results.")
    return results


# ==================================
# Main pipeline
# ==================================

def run_pipeline():
    os.makedirs("downloaded_results", exist_ok=True)

    # --- Load transcripts ---
    print("Loading transcripts from CSV...")
    df = pd.read_csv(INPUT_CSV)
    transcripts = [
        {"video_id": str(row["video_id"]), "content": str(row.get("transcript", ""))}
        for _, row in df.iterrows()
        if str(row.get("transcript", "")).strip()
    ]
    print(f"Loaded {len(transcripts)} transcripts.\n")

    # ==================
    # STEP 1: Extraction
    # ==================
    print("=== STEP 1: Signal Extraction ===")
    jsonl_1 = "batch_step1.jsonl"
    csv_to_jsonl(transcripts, PROMPTS["step_1_extraction"], jsonl_1)
    job_id_1 = start_batch_job(jsonl_1, "step1")
    job_1 = wait_for_job(job_id_1)
    step1_results = download_results(job_1)
    print()

    # ==================
    # STEP 2: Ideology
    # ==================
    print("=== STEP 2: Ideology Scoring ===")

    # Pass the step-1 JSON extraction as input text for step 2
    step2_inputs = [
        {
            "video_id": vid,
            "content": json.dumps(extraction, ensure_ascii=False, indent=2),
        }
        for vid, extraction in step1_results.items()
        if "error" not in extraction
    ]

    jsonl_2 = "batch_step2.jsonl"
    csv_to_jsonl(step2_inputs, PROMPTS["step_2_ideology"], jsonl_2)
    job_id_2 = start_batch_job(jsonl_2, "step2")
    job_2 = wait_for_job(job_id_2)
    step2_results = download_results(job_2)
    print()

    # ==================
    # STEP 3: Populism
    # ==================
    print("=== STEP 3: Populism Scoring ===")

    # Step 3 also receives the step-1 extraction (same input as step 2)
    step3_inputs = step2_inputs  # same extraction data, different prompt

    jsonl_3 = "batch_step3.jsonl"
    csv_to_jsonl(step3_inputs, PROMPTS["step_3_populism"], jsonl_3)
    job_id_3 = start_batch_job(jsonl_3, "step3")
    job_3 = wait_for_job(job_id_3)
    step3_results = download_results(job_3)
    print()

    # ==================
    # Merge & Save
    # ==================
    print("=== Merging results and saving to Excel ===")

    all_video_ids = sorted(
        set(step1_results) | set(step2_results) | set(step3_results)
    )
    rows = []
    for vid in all_video_ids:
        row = {"video_id": vid}

        # Flatten step-1 list fields as JSON strings to keep Excel readable
        s1 = step1_results.get(vid, {})
        for key, value in s1.items():
            row[f"s1_{key}"] = json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value

        row.update(step2_results.get(vid, {}))
        row.update(step3_results.get(vid, {}))
        rows.append(row)

    result_df = pd.DataFrame(rows)
    result_df.to_excel(OUTPUT_EXCEL, index=False)
    print(f"Done! Results saved to: {OUTPUT_EXCEL}")


if __name__ == "__main__":
    answer = input(
        f"Pipeline configuration:\n"
        f"  Model:  {MODEL_NAME}\n"
        f"  Input:  {INPUT_CSV}\n"
        f"  Output: {OUTPUT_EXCEL}\n"
        f"  Steps:  extraction → ideology → populism\n"
        f"\nStart pipeline? [Y/n] "
    )
    if answer.strip().lower() != "y":
        print("Aborted.")
    else:
        run_pipeline()

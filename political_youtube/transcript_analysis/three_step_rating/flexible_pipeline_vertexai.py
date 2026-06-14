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
# General Configuration
# ==================================

INPUT_CSV = "test_transcripts.csv"
MODEL_NAME = "gemini-2.5-flash"

POLL_INTERVAL_SECONDS = 150
MAX_POLL_ATTEMPTS = 20  # 20 * 150s = up to 50 minutes per step


# ==================================
# Pipeline Variants
# ==================================
# Each variant is a list of steps. Each step is a dict with:
#
#   "label"       : str  – used in filenames and log output
#   "prompt"      : str  – the system prompt sent to the model
#   "input_from"  : str  – where this step gets its input content:
#                           "transcript"  → raw transcript from the CSV
#                           "<label>"     → JSON output of the step with that label
#   "output_cols" : list – which keys from the JSON response to include in the
#                          final Excel file (None = include all keys)
#   "col_prefix"  : str  – prefix added to output column names (empty string = no prefix)
# ==================================

VARIANTS: dict[str, list[dict]] = {

    # ---------------------------------------------------------
    # Variant A: Three-step pipeline (extraction → scoring)
    # ---------------------------------------------------------
    "three_step_structured": [
        {
            "label": "extraction",
            "prompt": """Du erhältst das Transkript eines deutschen YouTube-Videos.

Deine Aufgabe ist ausschließlich die Extraktion politisch relevanter Signale. Führe keine Bewertung der politischen Position oder des Populismus durch.

WICHTIG:
- Beschreibe nur Aussagen des Creators.
- Bei Reaction-Videos dürfen Aussagen Dritter nur berücksichtigt werden, wenn der Creator ihnen ausdrücklich zustimmt, sie verteidigt oder positiv paraphrasiert.
- Verwende möglichst kurze Stichpunkte.
- Wenn ein Feld keine relevanten Inhalte hat, füge exakt den String "Keine erkennbaren Aussagen" als einziges Listenelement ein. Lasse keine Liste leer.

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
            "input_from": "transcript",
            "output_cols": None,   # include all fields
            "col_prefix": "s1_",
        },
        {
            "label": "ideology",
            "prompt": """Du erhältst die strukturierte Extraktion eines YouTube-Videos.

Bewerte die politische Ideologie so, wie ein durchschnittlicher politisch interessierter deutscher Zuschauer den Creator nach dem Konsum des Videos wahrnehmen würde.

WICHTIG:
- Bewerte den Gesamteindruck.
- Berücksichtige Themenauswahl, Framing, positive und negative Bezugspunkte sowie konkrete Forderungen.
- Nicht nur politische Lösungen zählen; Wiederkehrende Narrative dürfen berücksichtigt werden.
- Populismus ist KEINE Ideologie. Elitenkritik allein verschiebt den Wert nicht nach links oder rechts.

Skala (Orientierungspunkte – Zwischenwerte sind ausdrücklich erwünscht):
0.0–2.0 = klar links bis extrem links
3.0–4.0 = moderat bis leicht links
5.0     = neutral, ausgewogen oder nicht eindeutig einordenbar
6.0–7.0 = leicht bis moderat rechts
8.0–10.0 = klar bis extrem rechts

Bei gemischten Signalen: Gewichte kulturelle und wirtschaftliche Signale gleichwertig.
Wenn ein Bereich klar dominiert, folge diesem – setze NICHT automatisch 5.0.
Sonderregel: Wenn das Video keine erkennbaren politischen oder gesellschaftlichen Inhalte enthält, gib -1.0 zurück.

Gib ausschließlich folgendes JSON zurück:

{
  "ideology_score": 0.0,
  "ideology_reason": "Maximal zwei kurze Sätze."
}""",
            "input_from": "extraction",
            "output_cols": ["ideology_score", "ideology_reason"],
            "col_prefix": "",
        },
        {
            "label": "populism",
            "prompt": """Du erhältst die strukturierte Extraktion eines YouTube-Videos.

Bewerte den Populismusgrad so, wie ein durchschnittlicher deutscher Zuschauer die Kommunikation wahrnehmen würde.
Populismus ist unabhängig von linker oder rechter Ideologie.

Berücksichtige ausschließlich:
- Volk-vs-Elite-Framing
- Anti-Establishment-Rhetorik
- Pauschale Elitenkritik
- Misstrauen gegenüber Institutionen oder Medien
- Darstellung des Volkes als moralisch überlegen
- Darstellung von Eliten als korrupt, eigennützig oder volksfern
- Behauptungen, dass Institutionen systematisch gegen normale Bürger arbeiten

Nicht berücksichtigen:
- Konservativ oder progressiv sein
- Wirtschaftspolitische Positionen
- Migration, Klima oder Sozialpolitik an sich
- Reine Sachkritik ohne Volk-vs-Elite-Element
- Emotionale Sprache ohne Volk-vs-Elite-Bezug
- Kritik an einzelnen Politikern ohne pauschale Systemkritik

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
            "input_from": "extraction",   # also uses step-1 output, not ideology output
            "output_cols": ["populism_score", "populism_reason"],
            "col_prefix": "",
        },
    ],

    # ---------------------------------------------------------
    # Variant B: Direct classification (single step)
    # ---------------------------------------------------------
    "direct": [
        {
            "label": "classification",
            "prompt": """Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

1. VIDEO-TYP:
Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

2. SOZIO-KULTURELLE IDEOLOGIE (Skala 0 bis 10):
Bewerte die Position des Creators auf einer Skala von 0 (extrem links) bis 10 (extrem rechts).
- Neutral/ausgewogen = 5.0.
- Populismus ist KEINE Ideologie. Elitenkritik allein verschiebt den Wert nicht.
- LINKS (0.0–4.9): soziale Gerechtigkeit, Umverteilung, staatliche Regulierung, progressive Gesellschaftspolitik.
- RECHTS (5.1–10.0): individuelle Freiheit, Marktmechanismen, traditionelle Werte, Nationalstaat.
- Zwischenwerte sind ausdrücklich erwünscht. Bei gemischten Signalen: folge dem dominierenden Bereich, setze NICHT automatisch 5.0.
- Wenn die im Video behandelten Themen vollständig unpolitisch/ideologiefrei sind (z. B. reines Gaming, Kochvideo, Lifestyle ohne gesellschaftlichen Bezug), setze den Score zwingend auf -1.0.
- Wenn das Video ein vollständig neutraler Bericht über politische Ereignisse ist, setze den Score auf 5.0.


3. POPULISMUS (Skala 0 bis 10):
Bewerte den Populismusgrad basierend auf dem ideationellen Ansatz.
- 0.0 = keinerlei populistische Kommunikation. Unpolitisches Video = -1.0.
- Berücksichtige: Volk-vs-Elite-Framing, Anti-Establishment-Rhetorik, Misstrauen gegenüber Institutionen/Medien.
- Nicht berücksichtigen: wirtschaftspolitische Positionen, reine Sachkritik ohne Volk-vs-Elite-Element.

4. EVALUATIONS-REGEL:
Bewerte ausschließlich Aussagen des Creators. Ignoriere Aussagen Dritter, es sei denn, der Creator stimmt ihnen explizit zu.

5. BEGRÜNDUNGEN: Maximal 2 Sätze pro Begründung.

Gib ausschließlich folgendes JSON zurück:

{
  "video_type": "Reaction",
  "ideology_score": 5.0,
  "ideology_reason": "Kurzer Grund.",
  "populism_score": 0.0,
  "populism_reason": "Kurzer Grund."
}""",
            "input_from": "transcript",
            "output_cols": None,
            "col_prefix": "",
        },
    ],

    # ---------------------------------------------------------
    # Variant B: Two-step ideology classification (hierarchical
    # summary → scoring)
    # ---------------------------------------------------------
    "structured_ideology": [
        {
            "label": "hierarchical_summary",
            "prompt": """Du erhältst das Transkript eines deutschen YouTube-Videos.

Deine Aufgabe ist ausschließlich die Extraktion politisch relevanter Signale. Führe keine Bewertung der politischen Position durch.

WICHTIG:
- Beschreibe nur Aussagen des Creators.
- Bei Reaction-Videos dürfen Aussagen Dritter nur berücksichtigt werden, wenn der Creator ihnen ausdrücklich zustimmt, sie verteidigt oder positiv paraphrasiert.
- Verwende möglichst kurze Stichpunkte.
- Wenn ein Feld keine relevanten Inhalte hat, füge exakt den String "Keine erkennbaren Aussagen" als einziges Listenelement ein. Lasse keine Liste leer.

Gib ausschließlich folgendes JSON zurück:

{
  "video_type": "Reaction oder Standard",
  "main_topic": "Zentrales Thema des Videos",
  "main_argument": "Das wichtigste Argument/die wichtigste Botschaft, die das Video vermitteln soll",
  "dominant_topics": ["Themen, die zum zentralen Thema des Videos passen und ausführlich behandelt werden"],
  "secondary_topics": ["Themen, die kurz besprochen werden, aber nicht zentral für die Botschaft des Videos sind"],
  "brief_mentions": ["Themen, die eine kurze Erwähnung finden, ohne dass sie zum zentralen Thema des Videos passen"],
  "dominant_positive_targets": ["Personen, Gruppen, Institutionen oder Ideen, die positiv dargestellt werden"],
  "dominant_negative_targets": ["Personen, Gruppen, Institutionen oder Ideen, die negativ dargestellt werden"],
  "core_solitions": ["Welche Lösungen schlägt der Creator vor?"],
}""",
            "input_from": "transcript",
            "output_cols": None,   # include all fields
            "col_prefix": "i1_",
        },
        {
            "label": "ideology_classification",
            "prompt": """Du erhältst die strukturierte Extraktion eines YouTube-Videos.

Bewerte die politische Ideologie des Creators im Kontext Deutschlands.

WICHTIG:
- Bewerte den Gesamteindruck.
- Berücksichtige Themenauswahl, Framing, positive und negative Bezugspunkte sowie konkrete Forderungen.
- Nicht nur politische Lösungen zählen; Wiederkehrende Narrative dürfen berücksichtigt werden.
- Populismus ist KEINE Ideologie. Elitenkritik allein verschiebt den Wert nicht nach links oder rechts.

Skala (Orientierungspunkte – Zwischenwerte sind ausdrücklich erwünscht):
0.0–2.0 = klar links bis extrem links
3.0–4.0 = moderat bis leicht links
5.0     = neutral, ausgewogen oder nicht eindeutig einordenbar
6.0–7.0 = leicht bis moderat rechts
8.0–10.0 = klar bis extrem rechts

Bei gemischten Signalen: Gewichte kulturelle und wirtschaftliche Signale gleichwertig.
Wenn ein Bereich klar dominiert, folge diesem – setze NICHT automatisch 5.0.
Sonderregel: Wenn das Video keine erkennbaren politischen oder gesellschaftlichen Inhalte enthält, gib -1.0 zurück.

Gib ausschließlich folgendes JSON zurück:

{
  "ideology_score": 0.0,
  "ideology_reason": "Maximal zwei kurze Sätze."
}""",
            "input_from": "hierarchical_summary",
            "output_cols": ["ideology_score", "ideology_reason"],
            "col_prefix": "",
        },
    ]

    # ---------------------------------------------------------
    # Add further variants here following the same structure.
    # Example: two-step variant without extraction columns in output
    # ---------------------------------------------------------
    # "my_variant": [
    #     {
    #         "label": "step_name",
    #         "prompt": "...",
    #         "input_from": "transcript",   # or label of a preceding step
    #         "output_cols": None,          # None = all columns; list = filtered columns
    #         "col_prefix": "",
    #     },
    # ],
}


# ==================================
# Select active variant here
# ==================================
ACTIVE_VARIANT = "structured_ideology"


# ==================================
# Helper: CSV -> JSONL
# ==================================

def csv_to_jsonl(input_data: list[dict], prompt: str, jsonl_path: str):
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
    blob_name = f"batch_inputs/{ACTIVE_VARIANT}_{step_label}_{jsonl_path}"
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
# Main pipeline (variant-agnostic)
# ==================================

def run_pipeline():
    os.makedirs("downloaded_results", exist_ok=True)

    steps = VARIANTS[ACTIVE_VARIANT]
    output_excel = f"downloaded_results/classification_results_{ACTIVE_VARIANT}.xlsx"

    # Load transcripts once – available to any step that needs them
    print("Loading transcripts from CSV...")
    df = pd.read_csv(INPUT_CSV)
    transcripts: dict[str, str] = {
        str(row["video_id"]): str(row.get("transcript", ""))
        for _, row in df.iterrows()
        if str(row.get("transcript", "")).strip()
    }
    print(f"Loaded {len(transcripts)} transcripts.\n")

    # step_outputs maps step label -> {video_id: parsed_json}
    step_outputs: dict[str, dict[str, dict]] = {}

    for step in steps:
        label = step["label"]
        prompt = step["prompt"]
        input_from = step["input_from"]

        print(f"=== STEP: {label.upper()} (input: {input_from}) ===")

        # Build input list for this step
        if input_from == "transcript":
            input_data = [
                {"video_id": vid, "content": text}
                for vid, text in transcripts.items()
            ]
        elif input_from in step_outputs:
            input_data = [
                {
                    "video_id": vid,
                    "content": json.dumps(result, ensure_ascii=False, indent=2),
                }
                for vid, result in step_outputs[input_from].items()
                if "error" not in result
            ]
        else:
            raise ValueError(
                f"Step '{label}' references input_from='{input_from}', "
                f"but that step has not been executed yet. "
                f"Check the order of steps in your variant definition."
            )

        jsonl_path = f"batch_{ACTIVE_VARIANT}_{label}.jsonl"
        csv_to_jsonl(input_data, prompt, jsonl_path)
        job_id = start_batch_job(jsonl_path, label)
        job = wait_for_job(job_id)
        step_outputs[label] = download_results(job)
        print()

    # ==================================
    # Merge all step outputs into Excel
    # ==================================
    print("=== Merging results and saving to Excel ===")

    all_video_ids = sorted(
        set(vid for results in step_outputs.values() for vid in results)
    )

    rows = []
    for vid in all_video_ids:
        row: dict = {"video_id": vid}

        for step in steps:
            label = step["label"]
            prefix = step["col_prefix"]
            output_cols = step["output_cols"]
            result = step_outputs.get(label, {}).get(vid, {})

            for key, value in result.items():
                # Skip keys not in output_cols if a filter is defined
                if output_cols is not None and key not in output_cols:
                    continue
                col_name = f"{prefix}{key}" if prefix else key
                # Serialize lists to JSON strings so Excel can display them
                row[col_name] = (
                    json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
                )

        rows.append(row)

    result_df = pd.DataFrame(rows)
    result_df.to_excel(output_excel, index=False)
    print(f"Done! Results saved to: {output_excel}")


if __name__ == "__main__":
    steps_summary = " → ".join(s["label"] for s in VARIANTS[ACTIVE_VARIANT])
    answer = input(
        f"Pipeline configuration:\n"
        f"  Variant: {ACTIVE_VARIANT}\n"
        f"  Steps:   {steps_summary}\n"
        f"  Model:   {MODEL_NAME}\n"
        f"  Input:   {INPUT_CSV}\n"
        f"\nStart pipeline? [Y/n] "
    )
    if answer.strip().lower() != "y":
        print("Aborted.")
    else:
        run_pipeline()
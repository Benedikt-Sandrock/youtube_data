from dotenv import load_dotenv
import os
import json
import pandas as pd
from google import genai

from google.genai import types

"""
1. Defines function to convert transcript file to the needed jsonl file for Gemini
2. Defines function
3. Defines function
4. Starts the api request
"""


load_dotenv()
API_KEY = os.getenv("API_KEY_GEMINI")


client = genai.Client(api_key = API_KEY)

MODEL_NAME = "gemini-2.5-flash"  #cheapest model
INPUT_CSV = "../../Transcript files/transcripts_conflict_over_time_sampled.csv"
BATCH_INPUT_JSONL = "gemini_batch_input.jsonl"
OUTPUT_EXCEL = "classification_results.xlsx"


SYSTEM_PROMPT = """
!!! INSERT PROMPT !!!
"""


# ==================================
# 1. Convert CSV to JSONL
# ==================================

def csv_to_jsonl(csv_path, jsonl_path):
    print("Converting CSV to JSONL...")
    df = pd.read_csv(csv_path)

    with open(jsonl_path, "w", encoding = "utf-8") as f:
        for index, row in df.iterrows():
            v_id = str(row["video_id"])
            transcript = str(row.get("transcript", ""))

            if not transcript.strip():
                continue

            api_request = {
                "custom_id": v_id,
                "model": MODEL_NAME,
                "request": {
                    "contents": [{"parts": [{"text": f"Hier ist das Transkript:\n\n{transcript}"}]}],
                    "config": {
                        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                        "response_mime_type": "application/json",
                        "response_schema": {
                            "type": "OBJECT",
                            "properties": {
                                "video_type": {"type": "STRING", "enum": ["Reaction", "Standard"]},
                                "ideology_score": {"type": "NUMBER"},
                                "ideology_reason": {"type": "STRING", "description": "MUSS exakt 1 oder maximal 2 kurze, präzise Sätze lang sein."},
                                "populism_score": {"type": "NUMBER"},
                                "populism_reason": {"type": "STRING", "description": "MUSS exakt 1 oder maximal 2 kurze, präzise Sätze lang sein."}
                            },
                            "required": ["video_type", "ideology_score", "ideology_reason", "populism_score", "populism_reason"]
                        },
                        "temperature": 0.0
                    }
                }
            }

            #wirte as row in jsonl file
            f.write(json.dumps(api_request, ensure_ascii=False) + "\n")
        print(f"File {jsonl_path} was successfully created.")


# ==================================
# 2. Uploading and starting batch job
# ==================================

def start_batch_job(jsonl_path):
    print("Uploading JSONL-file to Google...")
    uploaded_file = client.files.upload(file = jsonl_path)

    print("Starting batch job...")
    job = client.batches.create(
        model = MODEL_NAME,
        src = uploaded_file.uri,
    )

    job_id = job.name
    print(f"Job successfully transmitted. Job-ID: {job_id}")











# ==================================
# 4. Main program
# ==================================

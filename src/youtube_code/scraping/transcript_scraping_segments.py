from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound
import pandas as pd
import time
import random
import os
import json
from datetime import datetime, timezone

from youtube_code.config import TRANSCRIPTS, SAMPLES, OUTPUTS, SRC

# =====================================================
# CONFIGURATION
# =====================================================

STOP_WORD = "blocking"
SPEED_DOWNLOAD = 1

# VIDEO_LIST = OUTPUTS / "sample_feasibility" / "descriptive_download_list.json"
VIDEO_LIST =  SRC / "new_analysis" / "out_screening" / "primary_pilot_ids.json"
# VIDEO_LIST = SAMPLES / "russia" / "political_ids.json"  # "keyword_videos_50k_channels.json"
#FILE_PATH_ALL = [TRANSCRIPTS / "all_transcripts.csv", TRANSCRIPTS /"all_transcripts_2.csv"]
OUTPUT_FILE = TRANSCRIPTS / "all_transcripts_segments.csv"
FILE_PATH_BACKUP = TRANSCRIPTS / "all_transcripts_backup.csv"

BATCH_SIZE = 5  # API-Batches
REQUIRED_COLUMNS = ["video_id", "transcript_segments", "language_code", "is_generated", "status"]

# =====================================================
# FUNCTIONS
# =====================================================

def get_transcript(video_id):
    yta = YouTubeTranscriptApi()
    return yta.fetch(video_id, languages=['de'])


def save_to_csv(daten_chunk, file_path):
    df = pd.DataFrame(daten_chunk)
    write_header = not os.path.exists(file_path)
    df.to_csv(
        file_path,
        mode="a",
        header=write_header,
        index=False,
        encoding="utf-8"
    )


# =====================================================
# LOADING DATA
# =====================================================

print(f"Speed download: {SPEED_DOWNLOAD}")
if SPEED_DOWNLOAD:
    answer = input("Speed download activated. Continue? [y/N] ")
    if answer.lower() != "y":
        print("Abort.")
        exit()

print("Reading sample videos...")
with open(VIDEO_LIST, "r", encoding="utf-8") as f:
    data = json.load(f)

print(type(data))
if isinstance(data, list) and len(data) > 0:
    print(type(data[0]))

    if isinstance(data[0], dict):
        video_ids_sorted = [str(item["video_id"]) for item in data]
    elif isinstance(data[0], str):  # <- Hier MUSS 'elif' stehen!
        video_ids_sorted = data
    else:
        print("Ungültiger Datentyp innerhalb der Liste.")
        exit()
else:
    print("No valid format for video ids. Revise import.")
    exit()

print(f"Number of video-IDs: {len(video_ids_sorted)}")

# Loading processed video-IDs

if os.path.exists(OUTPUT_FILE):
    print("Existing CSV found – Loading already processed video IDs…")
    existing_df = pd.read_csv(OUTPUT_FILE, usecols = ["video_id"])

    processed_video_ids = set(existing_df["video_id"].astype(str))
    print(f"Type of processed videi ids: {type(processed_video_ids)}")
    print(f"Type of video ids sorted: {type(video_ids_sorted)}")

    print(f"\n➡️ {len(processed_video_ids)} video IDs already existing.")

    already_downloaded = [v for v in video_ids_sorted if v in processed_video_ids]
    print(f"\n{len(already_downloaded)}/{len(video_ids_sorted)} videos of this set already downloaded.")

    num_remaining_vids = len(video_ids_sorted) - len(already_downloaded)

else:
    print("No existing CSV found")
    processed_video_ids = set()
    num_remaining_vids = len(video_ids_sorted)
videos_to_process = [v for v in video_ids_sorted if v not in processed_video_ids]

# random.shuffle(videos_to_process)
# print(f"\n🎲 {len(videos_to_process)} videos left to process. Order has been randomized.")


# =====================================================
# DOWNLOAD
# =====================================================

daten = []
api_request_count = 0
last_skipped_id = None

for video_id in videos_to_process:

    # Skip already processed IDs
    if video_id in processed_video_ids:
        last_skipped_id = video_id
        continue

    if last_skipped_id is not None:
        print(f"Last skipped ID: {last_skipped_id}")
        last_skipped_id = None

    print(f"Processing video-ID: {video_id}")

    try:
        segments = get_transcript(video_id)

        # Segments with timestamps - das ist jetzt die einzige Textquelle.
        transcript_segments = [
            {"start": seg.start, "duration": seg.duration, "text": seg.text}
            for seg in segments
        ]

        daten.append({
            "video_id": video_id,
            "transcript_segments": json.dumps(transcript_segments, ensure_ascii=False),
            "language_code": getattr(segments, "language_code", None),
            "is_generated": getattr(segments, "is_generated", None),
            "status": "OK"
        })

    except NoTranscriptFound:
        print(f"   -> No transcript for {video_id}")
        daten.append({
            "video_id": video_id,
            "transcript_segments": None,
            "language_code": None,
            "is_generated": None,
            "status": "Kein Transkript"
        })

    except Exception as e:
        error_msg = str(e).lower()
        if STOP_WORD in error_msg:
            timestamp = (datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"))
            print(f"{timestamp}: IP blocked – Loop is terminated\n"
                  f"Terminated after {api_request_count} requests")
            print(error_msg)
            break
        else:
            print(f"   -> Error at {video_id}: {e}")
            daten.append({
                "video_id": video_id,
                "transcript_segments": None,
                "language_code": None,
                "is_generated": None,
                "status": f"Fehler: {e}"
        })

    # Count only real API requests
    api_request_count += 1

    # Break after each API-request
    pause = random.uniform(15, 20) if SPEED_DOWNLOAD else random.uniform(26, 36) #26,36
    print(f"→ Break: {pause:.2f} seconds")
    time.sleep(pause)

    # Batch-break after 5 requests
    if api_request_count % BATCH_SIZE == 0:
        print(f"\n Saving …")
        save_to_csv(daten, OUTPUT_FILE)
        daten.clear()
        batch_break = random.uniform(20, 40) if SPEED_DOWNLOAD else random.uniform(45, 85) # 45, 85
        remaining_requests = num_remaining_vids - api_request_count
        print(f"Batch break after {api_request_count} requests: {batch_break:.2f} seconds."
              f"\n{remaining_requests} requests remaining.\n")
        time.sleep(batch_break)

    if api_request_count % 100 == 0:
        long_break = random.uniform(290, 310) # 290, 310
        print(f"Long break: {long_break:.2f} seconds")
        time.sleep(long_break)

    if api_request_count % 500 == 0:
        transcripts = pd.read_csv(OUTPUT_FILE)
        num_transcripts = len(transcripts)
        print(f"Back up after {num_transcripts} transcripts")
        transcripts.to_csv(FILE_PATH_BACKUP, index = False)

# Saving

if daten:
    print("\n💾 Saving remaining data …")
    save_to_csv(daten, OUTPUT_FILE)

print("\n✅ Done!")
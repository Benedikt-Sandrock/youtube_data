from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound
import pandas as pd
import time
import random
import os
import json
from datetime import datetime, timezone

from youtube_code.config import TRANSCRIPTS, SAMPLES


stop_word = "blocking"
speed_download = False
print(f"Speed download: {speed_download}")
# Daten laden
# Muss konfiguriert werden
#video_list : Liste mit Videos, für die Transkripte heruntergeladen werden soll
#file_path : Speicherort der Datei mit Transkripten

video_list = SAMPLES / "party_identification" / "sampled_50k_channels.json"
file_path_existing = TRANSCRIPTS / "all_transcripts.csv"
file_path = TRANSCRIPTS / "all_transcripts_2.csv"

file_path_backup = TRANSCRIPTS / "all_transcripts_backup.csv"

#os.makedirs((file_path), exist_ok=True)

print("Reading sample videos...")
with open(video_list, "r", encoding="utf-8") as f:
    data = json.load(f)

video_ids_sorted = [item["video_id"] for item in data]

print(f"Number of video-IDs: {len(video_ids_sorted)}")

# Funktionen

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

# Verarbeitete Video-IDs laden

processed_df = pd.read_csv(file_path_existing, usecols = ["video_id"])
processed_video_ids = set(processed_df["video_id"].astype(str))
print(f"{len(processed_video_ids)} IDs in first file.")

if os.path.exists(file_path):
    existing_df = pd.read_csv(file_path, usecols = ["video_id"])
    new_processed_ids = set(existing_df["video_id"].astype(str))
else:
    new_processed_ids = set()

print(f"{len(new_processed_ids)} IDs in second file.")
processed_video_ids = processed_video_ids | new_processed_ids
print(f"{len(processed_video_ids)} IDs in total.")

already_downloaded = [v for v in video_ids_sorted if v in processed_video_ids]
print(f"\n{len(already_downloaded)}/{len(video_ids_sorted)} videos of this set already downloaded.")


videos_to_process = [v for v in video_ids_sorted if v not in processed_video_ids]

random.shuffle(videos_to_process)

print(f"\n🎲 {len(videos_to_process)} videos left to process. Order has been randomized.")
# ----------------------------------------------

# Download

daten = []

batch_size = 5             # API-Batches
save_every = 25             # Zwischenspeichern nach 25 Videos
api_request_count = 0
last_skipped_id = None

for video_id in video_ids_sorted:

    # Bereits vorhandene IDs überspringen
    if video_id in processed_video_ids:
        last_skipped_id = video_id
        continue

    if last_skipped_id is not None:
        print(f"Last skipped ID: {last_skipped_id}")
        last_skipped_id = None

    print(f"Processing video-ID: {video_id}")

    try:
        segments = get_transcript(video_id)
        full_transcript = " ".join(seg.text for seg in segments)

        daten.append({
            "video_id": video_id,
            "transcript": full_transcript,
            "status": "OK"
        })

    except NoTranscriptFound:
        print(f"   -> No transcript for {video_id}")
        daten.append({
            "video_id": video_id,
            "transcript": None,
            "status": "Kein Transkript"
        })

    except Exception as e:
        error_msg = str(e).lower()
        if stop_word in error_msg:
            timestamp = (datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"))
            print(f"{timestamp}: IP blocked – Loop is terminated\n"
                  f"Terminated after {api_request_count} requests")
            print(error_msg)
            break
        else:
            print(f"   -> Error at {video_id}: {e}")
            daten.append({
                "video_id": video_id,
                "transcript": None,
                "status": f"Fehler: {e}"
        })

    # Nur echte API-Anfragen zählen
    api_request_count += 1

    # Pause nach jedem API-Request
    pause = random.uniform(0, 20) if speed_download else random.uniform(26, 36) #26,36
    print(f"→ Break: {pause:.2f} seconds")
    time.sleep(pause)

    # Batch-Pause nach 5 Requests
    if api_request_count % batch_size == 0:
        print(f"\n Saving …")
        save_to_csv(daten, file_path)
        daten.clear()
        batch_pause = random.uniform(0, 20) if speed_download else random.uniform(45, 85) # 45, 85
        print(f"Batch break after {api_request_count} requests: {batch_pause:.2f} seconds")
        time.sleep(batch_pause)

    if api_request_count % 100 == 0:
        lange_pause = random.uniform(290, 310) # 290, 310
        print(f"Long break: {lange_pause:.2f} seconds")
        time.sleep(lange_pause)

    if api_request_count % 500 == 0:
        transcripts = pd.read_csv(file_path)
        num_transcripts = len(transcripts)
        print(f"Back up after {num_transcripts} transcripts")
        transcripts.to_csv(file_path_backup, index = False)

# Restdaten speichern

if daten:
    print("\n💾 Saving remaining data …")
    save_to_csv(daten, file_path)

print("\n✅ Done!")

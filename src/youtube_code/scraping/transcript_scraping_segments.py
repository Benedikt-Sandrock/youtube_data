from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound
import pandas as pd
import time
import random
import os
import json
from datetime import datetime, timezone

from youtube_code.config import TRANSCRIPTS, SAMPLES, OUTPUTS, SRC
from youtube_code.utils.video_registry import get_channel_map, get_videos_for_channels

# =====================================================
# CONFIGURATION
# =====================================================

STOP_WORD = "blocking"
SPEED_DOWNLOAD = 1
VIDEO_LIST = "baseline_now_sufficient_fill_vids.json"
# VIDEO_LIST = OUTPUTS / "sample_feasibility" / "war_vids.json"
# VIDEO_LIST =  SRC / "new_analysis" / "out_screening" / "primary_pilot_ids.json"
# VIDEO_LIST = SAMPLES / "russia" / "political_ids.json"  # "keyword_videos_50k_channels.json"
#FILE_PATH_ALL = [TRANSCRIPTS / "all_transcripts.csv", TRANSCRIPTS /"all_transcripts_2.csv"]
OUTPUT_FILE = TRANSCRIPTS / "all_transcripts_segments.csv"
FILE_PATH_BACKUP = TRANSCRIPTS / "all_transcripts_backup.csv"

BATCH_SIZE = 5  # API-Batches
REQUIRED_COLUMNS = ["video_id", "transcript_segments", "language_code", "is_generated", "status"]

# Kanal-Vorfilter: Kanaele, fuer die schon MIN_ATTEMPTS_FOR_CHANNEL_CHECK
# Transkripte abgefragt wurden, aber weniger als MIN_AVAILABLE_REQUIRED
# davon tatsaechlich existieren ("status" == "OK"), werden komplett
# uebersprungen - fuer sie werden keine weiteren Transkripte abgefragt.
MIN_ATTEMPTS_FOR_CHANNEL_CHECK = 10
MIN_AVAILABLE_REQUIRED = 2

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
video_channel_map = {}  # video_id -> channel_id, soweit im Input vorhanden
if isinstance(data, list) and len(data) > 0:
    print(type(data[0]))

    if isinstance(data[0], dict):
        video_ids_sorted = [str(item["video_id"]) for item in data]
        for item in data:
            cid = item.get("channel_id")
            if cid:
                video_channel_map[str(item["video_id"])] = str(cid)
    elif isinstance(data[0], str):  # <- Hier MUSS 'elif' stehen!
        video_ids_sorted = data
    else:
        print("Ungültiger Datentyp innerhalb der Liste.")
        exit()
else:
    print("No valid format for video ids. Revise import.")
    exit()

print(f"Number of video-IDs: {len(video_ids_sorted)}")

# Loading processed video-IDs (inkl. status, fuer den Kanal-Vorfilter unten)

if os.path.exists(OUTPUT_FILE):
    print("Existing CSV found – Loading already processed video IDs…")
    existing_df = pd.read_csv(OUTPUT_FILE, usecols=["video_id", "status"])
    existing_df["video_id"] = existing_df["video_id"].astype(str)

    processed_video_ids = set(existing_df["video_id"])
    status_by_video_id = dict(zip(existing_df["video_id"], existing_df["status"]))

    print(f"\n➡️ {len(processed_video_ids)} video IDs already existing.")

    already_downloaded = [v for v in video_ids_sorted if v in processed_video_ids]
    print(f"\n{len(already_downloaded)}/{len(video_ids_sorted)} videos of this set already downloaded.")

else:
    print("No existing CSV found")
    processed_video_ids = set()
    status_by_video_id = {}

# =====================================================
# KANAL-VORFILTER
# =====================================================
# Fuer jede Video-ID im Input wird - soweit moeglich - die channel_id
# bestimmt (zuerst aus dem Input selbst, sonst aus der zentralen
# video_registry.sqlite). Fuer jeden so bekannten Kanal wird ueber ALLE
# in der Registry bekannten Videos dieses Kanals (nicht nur die im
# aktuellen Input) geprueft, wie viele Transkripte davon schon abgefragt
# wurden (Eintrag in OUTPUT_FILE) und wie viele davon tatsaechlich
# existieren (status == "OK"). Kanaele mit >= MIN_ATTEMPTS_FOR_CHANNEL_CHECK
# Abfragen, aber < MIN_AVAILABLE_REQUIRED tatsaechlichen Transkripten,
# werden komplett uebersprungen.

missing_channel_ids = [v for v in video_ids_sorted if v not in video_channel_map]
if missing_channel_ids:
    video_channel_map.update(get_channel_map(missing_channel_ids))

known_channel_ids = {cid for cid in video_channel_map.values() if cid}
unmapped_count = len(video_ids_sorted) - sum(1 for v in video_ids_sorted if v in video_channel_map)

if known_channel_ids:
    videos_by_channel = get_videos_for_channels(known_channel_ids)

    blocked_channels = set()
    for cid in known_channel_ids:
        registry_videos = videos_by_channel.get(cid, set())
        attempted_ids = registry_videos & processed_video_ids
        attempted = len(attempted_ids)
        available = sum(1 for v in attempted_ids if status_by_video_id.get(v) == "OK")

        if attempted >= MIN_ATTEMPTS_FOR_CHANNEL_CHECK and available < MIN_AVAILABLE_REQUIRED:
            blocked_channels.add(cid)

    if blocked_channels:
        before = len(video_ids_sorted)
        video_ids_sorted = [
            v for v in video_ids_sorted
            if video_channel_map.get(v) not in blocked_channels
        ]
        removed = before - len(video_ids_sorted)
        print(
            f"\n🚫 {len(blocked_channels)} Kanal/Kanäle ohne ausreichend verfügbare Transkripte "
            f"(>= {MIN_ATTEMPTS_FOR_CHANNEL_CHECK} abgefragt, < {MIN_AVAILABLE_REQUIRED} vorhanden) "
            f"— {removed} Video-IDs dadurch entfernt."
        )
    else:
        print(f"\n✅ Kanal-Vorfilter: kein Kanal erreicht die Sperr-Schwelle.")

    if unmapped_count:
        print(f"ℹ️ {unmapped_count} Video-IDs ohne bekannte channel_id — für sie entfällt der Kanal-Vorfilter.")
else:
    print("\nℹ️ Keine channel_id verfügbar (weder im Input noch in der Registry) — Kanal-Vorfilter wird übersprungen.")

num_remaining_vids = len([v for v in video_ids_sorted if v not in processed_video_ids])
videos_to_process = [v for v in video_ids_sorted if v not in processed_video_ids]

random.shuffle(videos_to_process)
print(f"\n🎲 {len(videos_to_process)} videos left to process. Order has been randomized.")


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
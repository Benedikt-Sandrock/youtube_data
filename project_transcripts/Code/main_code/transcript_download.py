from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound
import pandas as pd
import time
import random
import os
import json
from datetime import datetime, timezone

#retry: d5X371Q92yE, M5x_IiZYbFY, sYd2OTcu-3s, RhzwrL3bMHc  !!!!!

stop_word = "blocking"

# Daten laden
video_list = f"../JSON Files/videos_sampled_total.json"
print("Lese Sample Videos ein...")
with open(video_list, "r", encoding="utf-8") as f:
    data = json.load(f)

video_ids_sorted = [item["video_id"] for item in data]

print(f"Anzahl Video-IDs: {len(video_ids_sorted)}")

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


file_path = f"../../Transcript files/youtube_transkripte_sampledvideos.csv"
file_path_backup = f"../../Transcript files/youtube_transkripte_sampledvideos_backup.csv"

# Verarbeitete Video-IDs laden

processed_video_ids = set()

if os.path.exists(file_path):
    print("Bestehende CSV gefunden – lade bereits verarbeitete Video-IDs …")
    existing_df = pd.read_csv(file_path, usecols=["video_id"])
    processed_video_ids = set(existing_df["video_id"].astype(str))
    print(f"➡️ {len(processed_video_ids)} Video-IDs bereits vorhanden")
else:
    print("Keine bestehende CSV gefunden")


# Download

daten = []

batch_size = 5              # API-Batches
save_every = 25             # Zwischenspeichern nach 25 Videos
api_request_count = 0
last_skipped_id = None

for video_id in video_ids_sorted:

    # Bereits vorhandene IDs überspringen
    if video_id in processed_video_ids:
        last_skipped_id = video_id
        continue

    if last_skipped_id is not None:
        print(f"Letzte übersprungene ID: {last_skipped_id}")
        last_skipped_id = None

    print(f"Verarbeite Video-ID: {video_id}")

    try:
        segments = get_transcript(video_id)
        full_transcript = " ".join(seg.text for seg in segments)

        daten.append({
            "video_id": video_id,
            "transcript": full_transcript,
            "status": "OK"
        })

    except NoTranscriptFound:
        print(f"   -> Kein Transkript für {video_id}")
        daten.append({
            "video_id": video_id,
            "transcript": None,
            "status": "Kein Transkript"
        })

    except Exception as e:
        error_msg = str(e).lower()
        if stop_word in error_msg:
            timestamp = (datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"))
            print(f"{timestamp}: IP geblockt – Schleife wird abgebrochen\n"
                  f"Abgebrochen nach {api_request_count} Requests")
            print(error_msg)
            break
        else:
            print(f"   -> Fehler bei {video_id}: {e}")
            daten.append({
                "video_id": video_id,
                "transcript": None,
                "status": f"Fehler: {e}"
        })

    processed_video_ids.add(video_id)

    # Nur echte API-Anfragen zählen
    api_request_count += 1

    # Pause nach jedem API-Request
    pause = random.uniform(26, 36)
    print(f"→ Pause: {pause:.2f} Sekunden")
    time.sleep(pause)

    # Batch-Pause nach 5 Requests
    if api_request_count % batch_size == 0:
        print(f"\n Speichern …")
        save_to_csv(daten, file_path)
        daten.clear()
        batch_pause = random.uniform(45, 85)
        print(f"Batch Pause nach {api_request_count} Requests: {batch_pause:.2f} Sekunden")
        time.sleep(batch_pause)

    if api_request_count % 100 == 0:
        lange_pause = random.uniform(290, 310)
        print(f"lange Pause: {lange_pause:.2f} Sekunden")
        time.sleep(lange_pause)

    if api_request_count % 500 == 0:
        transcripts = pd.read_csv(file_path)
        num_transcripts = len(transcripts)
        print(f"Back up nach {num_transcripts} Transcripts")
        transcripts.to_csv(file_path_backup, index = False)

# Restdaten speichern

if daten:
    print("\n💾 Speichere verbleibende Daten …")
    save_to_csv(daten, file_path)

print("\n✅ Fertig!")

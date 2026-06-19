from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound
import pandas as pd
import os


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

file_path = "../../../data/transcripts/single_transcripts.csv"
video_id = "Aaj1uXTGF7I"
daten = []

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

save_to_csv(daten, file_path)
print("Transcript downloaded and saved.")
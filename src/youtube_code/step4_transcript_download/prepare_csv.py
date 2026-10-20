import pandas as pd
import json
from youtube_code.config import ADHOC_OUTPUT
from youtube_code.store.transcript_store import get_transcripts
from youtube_code.store.video_registry import get_video_metadata

def get_ids_from_sample():
    df = pd.read_csv(ADHOC_OUTPUT / "zufallsstichprobe_videos_20261016_170433.csv")

    ids = df["video_id"].tolist()

    with open("ids_right.json", "w") as f:
        json.dump(ids, f, ensure_ascii=False, indent = 2)

def get_transcript_segments(data):
    df = get_transcripts(data)

    df = pd.DataFrame.from_dict(df, orient="index")
    df = df.reset_index().rename(columns={"index": "video_id"})

    print(df)
    df.to_csv("segments_new.csv", index = False)


with open("ids_right.json") as f:
    data = json.load(f)

video_metadata = get_video_metadata(video_ids = data, min_duration_seconds=None)

print(video_metadata.head())

video_metadata.to_csv("metadata_new.csv", index = False)

get_transcript_segments(data)
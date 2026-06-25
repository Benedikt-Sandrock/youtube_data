import json
from youtube_code.utils import load_json, merge_channel_name
from youtube_code.config import RAW, OUTPUT_GEMINI, TRANSCRIPTS
import pandas as pd

kw = load_json("keyword_videos_50k_channels_max300.json")

df = pd.read_csv(TRANSCRIPTS / "all_transcripts.csv")

ids = [v["video_id"] for v in kw]

df = df[df["video_id"].isin(ids)]

print(len(df))
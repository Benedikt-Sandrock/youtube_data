import json
from youtube_code.utils import load_json, load_set, merge_channel_name
from youtube_code.config import TRANSCRIPTS, OUTPUT_GEMINI, RAW
import pandas as pd

# df = pd.read_json("keyword_videos_50k_channels.json")
# print(len(df))
df = pd.read_csv(TRANSCRIPTS / "all_transcripts.csv")
print(f"all transcripts:{len(df)}")

classi = pd.read_csv(OUTPUT_GEMINI / "classification_cot_total" / "classification_results_051_gemini-2.5-flash.csv")
classi2 = pd.read_csv(OUTPUT_GEMINI / "classification_pi_total" / "classification_results_051_gemini-2.5-flash.csv")
classi = pd.concat([classi, classi2])
print(f"all classified:{len(classi)}")

data = load_json("sampled_50k_channels.json")

data = [v["video_id"] for v in data]
print(f"sample vids: {len(data)}")

classified = classi["video_id"].to_list()

data = [v for v in data if v not in classified]
print(f"all left: {len(data)}")

df = df[df["video_id"].isin(data)]
print(f"Transcripts to rate: {len(df)}")

df.to_csv("transcripts_party_identification_2.csv", index = False)
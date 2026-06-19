from src.youtube_code.config.paths import TRANSCRIPTS
from src.youtube_code.utils.io import load_json
import pandas as pd

data = load_json("sampled_50k_channels.json")
df = pd.read_csv(TRANSCRIPTS / "all_transcripts.csv")

print(len(df))
videos = {v["video_id"] for v in data}
print(len(videos))

df = df[df["video_id"].isin(videos)]
print(len(df))

df = df[df["status"] == "OK"]
print(len(df))
print(df.head())
df.to_csv("transcripts_cot_50k.csv", index = False)
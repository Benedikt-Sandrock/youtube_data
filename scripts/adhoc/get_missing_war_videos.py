import pandas as pd

from youtube_code.store.transcript_store import get_transcripts
from youtube_code.store import llm_run_store
from youtube_code.config import OUTPUTS, EXPLORATION

PROMPT = "POPULISMUS_P"
SOURCE = "segment_analysis_active"
OUTPUT_DIR = EXPLORATION

runs = llm_run_store.get_runs(source= SOURCE)
runs = runs[runs["prompt_id"] == PROMPT]

ids = set()
for _,run in runs.iterrows():
    results_path= run["results_path"]
    df = pd.read_csv(results_path, usecols = ["video_id"])
    ids.update(df["video_id"].dropna().unique().tolist())

print(len(ids))

df = pd.read_csv(OUTPUTS / "sample_feasibility" / "videos_compact_pol_labels.csv")

df = df[(df["is_war_core"] == True) | (df["is_war_wide"] == True)]
print(len(df))

missing_ids = set(df["video_id"].tolist())

possible_ids = missing_ids - ids
available_transcripts = get_transcripts(possible_ids)
print(len(available_transcripts))

video_list = list(available_transcripts)
print(video_list[0:5])

df = pd.DataFrame(video_list, columns = ["video_id"])
df.to_csv(EXPLORATION / "war_vids.csv", index = False)

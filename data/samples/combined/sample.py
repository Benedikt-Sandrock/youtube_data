import json
from youtube_code.utils import load_json, merge_channel_name
from youtube_code.config import RAW, OUTPUT_GEMINI
import pandas as pd

kw_at_all = load_json("keyword_videos_50k_channels.json")
kw_at_all = {c["channel_title"] for c in kw_at_all}

df = pd.read_excel(OUTPUT_GEMINI / "classification_pi_total" / "channel_results_051.xlsx")
print(len(df))

df = df[df["channel_title"].isin(kw_at_all)]
print(len(df))

df.to_excel(OUTPUT_GEMINI / "classification_pi_total" / "channel_results_051_onlykw.xlsx")

import json
import pandas as pd

from youtube_code.utils.transcript_store import attempted_video_ids
from youtube_code.utils.screening_state_store import get_state

df = get_state()[
    ["video_id", "channel_id", "channel_title", "interval_index", "politics_final"]
]

# --- Vorkriegs-27-Kanäle-Projekt ---
todo = pd.read_csv("outputs/segment_analysis/kanaele_baseline_collection_todo.csv", dtype={"channel_id": "string"})
prewar_ids = set(todo["channel_id"])
prewar = df[df["channel_id"].isin(prewar_ids) & df["interval_index"].isin([0, 1, 2, 3])]
prewar_cnt = prewar.groupby("channel_id")["politics_final"].apply(lambda s: (s == 1).sum())
prewar_qual = set(prewar_cnt[prewar_cnt >= 10].index)

# --- Postwar-Kanäle ---
postwar = df[df["interval_index"] == -1]
postwar_cnt = postwar.groupby("channel_id")["politics_final"].apply(lambda s: (s == 1).sum())
postwar_qual = set(postwar_cnt[postwar_cnt >= 10].index)

# Alle politischen Video-IDs der jetzt qualifizierenden Kanäle im jeweiligen Fenster
new_prewar = prewar[prewar["channel_id"].isin(prewar_qual) & (prewar["politics_final"] == 1)]
new_postwar = postwar[postwar["channel_id"].isin(postwar_qual) & (postwar["politics_final"] == 1)]
new_all = pd.concat([new_prewar, new_postwar])[["video_id", "channel_id"]].drop_duplicates()

# Gegen bereits versuchte Transkripte abgleichen (Source of Truth seit Phase 4c: transcript_store)
tried = attempted_video_ids()
fill_vids = new_all[~new_all["video_id"].isin(tried)]

print(f"{len(new_all)} politische Videos in qualifizierenden Kanälen, davon {len(fill_vids)} noch offen")

fill_vids.to_json(
    "src/youtube_code/scraping/baseline_now_sufficient_fill_vids.json",
    orient="records",
)
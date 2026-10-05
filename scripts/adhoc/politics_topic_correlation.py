"""
Vergleich die Korrelation von der Politik-Klassifikation über die YouTube-Metadaten mit der
Klassifikation der Video-Titel und -Beschreibungen durch LLMs.
Benötigt:
Video Registry: Video IDs, topics-classification
Screening State: Video IDs, politics-classification -> politics_final
"""

import pandas as pd

from youtube_code.store.video_registry import politics_topic_lookup
from youtube_code.store.screening_state_store import get_state


state = get_state(politics_final_not_null=True)
state = state[["video_id", "politics_final"]]

print(f"Number of Videos with LLM-classification: {len(state)}")
print(f"Positive: {len(state[state["politics_final"] == 1])}"
      f"\nNegative: {len(state[state["politics_final"] == 0])}"
      f"\nUnsure: {len(state[state["politics_final"] == -1])}")


ids = state["video_id"].tolist()

topics_dict = politics_topic_lookup(ids)

print(f"Thereof with Metadata-Classification: {len(topics_dict)}")

df = pd.DataFrame(topics_dict.items(), columns = ["video_id", "is_politics"])
print(df.head())

df = pd.merge(df, state, on= "video_id", how = "left")

df["politics_llm_restrictive"] = df["politics_final"] == 1
df["politics_llm_generous"] = df["politics_final"] != 0


corr = df.corr(method = "spearman", numeric_only = True)

with pd.option_context("display.max_columns", None):
      print(corr)



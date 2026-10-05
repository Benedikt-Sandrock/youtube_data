import pandas as pd
from pathlib import Path

# STATE_FILE = Path(r"Users\bened\PycharmProjects\youtube_data\data\samples"
#                   r"\russia\longitudinal_screening_state.csv")
# RETRY_FILE = Path(
#     r"C:\Users\bened\PycharmProjects\youtube_data\outputs\llm\longitudinal"
#     r"\description_classification\run_0006_retry.csv"
# )
#
# state = pd.read_csv(STATE_FILE, dtype={"video_id": "string"}, low_memory=False)
# retry = pd.read_csv(RETRY_FILE, dtype={"video_id": "string"}, low_memory=False)
#
# lookup = state.set_index("video_id")[["description", "politics_title"]]
# retry = retry.join(lookup, on="video_id")
#
# missing = retry["description"].isna().sum()
# assert missing == 0, f"{missing} video_ids ohne Treffer im State – vor dem Speichern prüfen!"

# retry.to_csv(RETRY_FILE, index=False, encoding="utf-8-sig")

import pandas as pd

df = pd.read_csv("run_0007.csv")
df2 = pd.read_csv("run_0006.csv")

print(len(df), len(df2))

df = pd.concat([df, df2])
print(len(df))
df.to_csv("run_0006.csv", index = False)
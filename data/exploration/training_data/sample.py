import pandas as pd
from youtube_code.config import SAMPLES, LLM

df = pd.read_excel("added_training_sample_40.xlsx")
# df["politics_title"] = int(df["politics_title"])
# df["politics_title_desc"] = int(df["politics_title_desc"])

def final_score(row):
    if row["politics_title"] in [0,1]:
        return row["politics_title"]

    return row["politics_title_desc"]

df["politics_final_manual"] = df.apply(final_score, axis=1)

df.to_csv(SAMPLES/ "russia/description_training_sample_40.csv", index = False)

# df2 = pd.read_csv(LLM / "title_classification" / "run_0008.csv")
# print(len(df), len(df2))
# df = pd.merge(df, df2[["video_id", "politics_title"]], on = "video_id", how = "outer")
# print(len(df))
#
# df.to_excel("added_training_sample_40.xlsx", index = False)
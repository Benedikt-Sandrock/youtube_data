import pandas as pd
from youtube_code.config import SAMPLES

df = pd.read_excel("description_training_sample_40.xlsx")
# df["politics_title"] = int(df["politics_title"])
# df["politics_title_desc"] = int(df["politics_title_desc"])

def final_score(row):
    if row["politics_title"] in [0,1]:
        return row["politics_title"]

    return row["politics_title_desc"]

df["politics_final_manual"] = df.apply(final_score, axis=1)

df.to_csv(SAMPLES/ "russia/description_training_sample_40.csv", index = False)
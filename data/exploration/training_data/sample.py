import pandas as pd

df = pd.read_excel("description_training_sample_42.xlsx")
# df["politics_title"] = int(df["politics_title"])
# df["politics_title_desc"] = int(df["politics_title_desc"])

def final_score(row):
    if row["politics_title"] in [0,1]:
        return row["politics_title"]

    return row["politics_title_desc"]

df["politics_final_manual"] = df.apply(final_score, axis=1)

df.to_csv("description_training_sample_42.csv", index = False)
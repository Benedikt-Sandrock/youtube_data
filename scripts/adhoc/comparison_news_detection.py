import pandas as pd
from youtube_code.step3_topic_relevance.news_show_patterns import (
    classify_frame, PATTERN_VERSION,
)

df = pd.read_excel("outputs/alt_kanaele_long_sample.xlsx")

df["auto"] = classify_frame(df)

df["auto"] = df["auto"].fillna(1)
df["auto"] = df["auto"].replace({"nachrichtensendung": 0,})
df["difference"] = df["auto"] - df["single_topic"]

df.to_csv("outputs/comparison.csv", index = False)
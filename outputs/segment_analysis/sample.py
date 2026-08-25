import pandas as pd
import numpy as np
from youtube_code.config import SAMPLES

df = pd.read_csv("run_0003_IDEOLOGIE_I.csv")

dfc = pd.read_csv(SAMPLES / "russia" / "out_segments"/ "descriptive_sample_baseline.csv", usecols = ["video_id", "channel_id"])

df = df[["video_id", "wirtschaft", "gesellschaft"]]

# df["wirtschaft"] = pd.to_numeric(df["wirtschaft"].replace("null", np.nan))
# df["gesellschaft"] = pd.to_numeric(df["gesellschaft"].replace("null", np.nan))

df = pd.merge(df, dfc, on ="video_id", how = "left")
print(len(df))

df_agg = df.groupby("channel_id").agg(
    gesellschaft = ("gesellschaft", "mean"),
    wirtschaft = ("wirtschaft", "mean")
)
print(df_agg)

df = df[df["channel_id"] == "UC9qdoYTVU413M6EvqDRZDtA"]
print(df)
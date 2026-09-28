from youtube_code.config import OUTPUTS, EXTERNAL

import pandas as pd

df = pd.read_csv(OUTPUTS / "segment_analysis" / "channel_video_populism.csv")
df2 = pd.read_excel(EXTERNAL / "media_type_russia_merged.xlsx")

df = pd.merge(df, df2[["channel_id", "type"]])

df = df.groupby("type").agg(
    populism = ("populismus_gesamt", "mean"),
    volkszentrismus = ("volkszentrismus", "mean"),
    antielitismus = ("antielitismus", "mean"),
    manichaeische_moralisierung = ("manichaeische_moralisierung", "mean"),
    emotionale_intensitaet = ("emotionale_intensitaet", "mean")
).reset_index()
with pd.option_context("display.max_columns", None):
    print(df)

df= pd.read_csv(OUTPUTS / "segment_analysis" / "channel_video_position.csv")

df = pd.merge(df, df2[["channel_id", "type"]])
df = df.groupby("type").agg(
    position_russland = ("position_russland", "mean"),
    position_westpolitik = ("position_westpolitik", "mean")
).reset_index()

with pd.option_context("display.max_columns", None):
    print(df)

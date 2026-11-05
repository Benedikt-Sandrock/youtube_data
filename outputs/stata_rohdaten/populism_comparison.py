import pandas as pd

df = pd.read_stata("kanaele_roh.dta")
df2 = pd.read_excel("channels_check.xlsx")

df = pd.merge(df, df2, on ="channel_id", how = "right")

df = df[["channel_id", "kanal_name", "pop_baseline", "media_category", "sample"]]
alt_df = df[(df["media_category"] == 5) & (df["sample"] == 1)]

print(alt_df["pop_baseline"].describe())

df.to_csv("temp.csv", index = False)
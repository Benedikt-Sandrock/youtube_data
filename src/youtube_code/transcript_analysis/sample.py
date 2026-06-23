import pandas as pd

df = pd.read_excel("ratings_merged.xlsx")

df = df[df["channel_title"] == "BILD"]

df.to_excel("ratings_BILD.xlsx", index = False)
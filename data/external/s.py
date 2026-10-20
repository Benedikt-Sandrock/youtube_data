import pandas as pd
df  = pd.read_csv("kanal_typologie.csv")

df[["channel_id", "kanal_name", "typ_code", "typ"]].to_excel("channels.xlsx", index = False)
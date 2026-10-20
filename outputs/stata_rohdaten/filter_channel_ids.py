import pandas as pd

df = pd.read_stata("views_aug21-jan22.dta")
df2 = pd.read_stata("views_jan22.dta")

df_top10 = (df.sort_values(by=["media_category", "views"], ascending = [True, False])
            .groupby("media_category").head(10))

df_top10.to_csv("top10_channels.csv", index = False)

channel_ids = df_top10["channel_id"].tolist()
print(channel_ids)

import pandas as pd
from youtube_code.config import RAW, EXTERNAL

df= pd.read_csv("classification_results_051_complete.csv")
print(len(df))
df = df[df[""]]

ids = set(df["video_id"].to_list())
print(len(ids))

# df = pd.read_excel("channel_results_051.xlsx")
# df2 = pd.read_json(RAW / "channel_metadata_total.json")
# df2 = df2.rename(columns= {"title": "channel_title"})
# df = pd.merge(df, df2[["channel_title", "subscribers"]], on = "channel_title", how = "left")
# df.to_excel("channel_results_051.xlsx", index = False)


# df_1 = pd.read_excel("classification_cot_total/channel_results_051.xlsx")
# df_2 = pd.read_excel("classification_pi_total/channel_results_051_onlykw.xlsx")
# print(len(df_1))
# print(len(df_2))
# clist = df_1["channel_title"].to_list()
# df_2 = df_2[~df_2["channel_title"].isin(clist)]
# print(len(df_2))
# df = pd.concat([df_1, df_2])
# print(len(df))
# df = df.drop_duplicates()
# df.to_excel("channel_results_051.xlsx", index = False)
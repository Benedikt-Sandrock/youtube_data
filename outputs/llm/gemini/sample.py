import pandas as pd
from youtube_code.config import RAW

df = pd.read_excel("channel_results_051.xlsx")
df= df.drop(columns = ["ideology_channel", "populism_channel"])

df.to_excel("channel_results_051.xlsx", index = False)

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
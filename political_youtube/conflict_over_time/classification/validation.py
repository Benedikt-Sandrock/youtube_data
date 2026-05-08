import pandas as pd
seed_number = 41
df_auto = pd.read_json(f"classified_videos_{seed_number}.json")
df_self = pd.read_excel(f"video_titles_sample_{seed_number}.xlsx")
df_auto["politics_sure"] = df_auto["politik_confidence"] > 0.8
#df_auto.columns = ["title", "category", "confidence"]
# df_auto["value"] = df_auto["category"] == "Politik"
print(len(df_auto))
print(len(df_self))
df_complete = pd.merge(df_auto, df_self, on = "title", how = "inner")

print(len(df_complete))
df_complete.to_excel("combined.xlsx", engine = "openpyxl", index = False)

sub_df = df_complete[["is_politics", "politics_sure", "politics_manual"]]
correlation = sub_df.corr()
print(correlation)
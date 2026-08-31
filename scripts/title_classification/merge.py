import pandas as pd
import numpy as np


df = pd.read_csv("../../outputs/archive/title_classification/results_all_models_41.csv")
print(df["title"].duplicated().sum())
print(len(df))
df = df.drop_duplicates(subset = ["title"])
print(len(df))


df_2 = pd.read_json("../channel_identification/large_german_channels/video_files/all_videos_50k_channels_sampled.json")
print(df_2["title"].duplicated().sum())
print(len(df_2))
df_2 = df_2.drop_duplicates(subset = ["title"])
print(len(df_2))

df = pd.merge(df, df_2, on = "title", how= "inner")
print(len(df))


rename_dict = {
    "mDeBERTa-v3_politik_confidence": "confidence_score",
    "mDeBERTa-v3_is_politics": "politics_classification"
}

df = df.rename(columns = rename_dict)

df.to_csv("sampled_videos_classified.csv", index = False)

print(df["politics_classification"].mean())


df["random_number"] = np.random.permutation(len(df))

df_sorted = df.sort_values(by =["channel_id", "time_delta", "politics_classification", "random_number"],
                           ascending = [True, True, False, True])

new_df = df_sorted.groupby(["channel_id", "time_delta"]).head(20)
new_df = new_df.reset_index(drop=True)
new_df = new_df.drop(columns =["selection", "random_number"])
new_df.to_csv("sampled_per_channel.csv", index = False)
new_df.to_json("sampled_per_channel.json", orient = "records", force_ascii = False, indent = 4)





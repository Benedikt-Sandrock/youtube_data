import pandas as pd

# keep only transcripts from manually graded list

all_sample_vids = "../../conflict_over_time/classification/sampled_per_channel.json"
manually_graded = "../../analysis/training_data/rating/training_data_sample_vids.csv"
transcripts_sample_vids = "../../Transcript files/transcripts_conflict_over_time_sampled.csv"

df = pd.read_csv(manually_graded)

relevant_ids = df["video_id"].tolist()
relevant_ids = set(relevant_ids)
print(len(relevant_ids))


df = pd.read_csv(transcripts_sample_vids)
print(len(df))

df = df[df["video_id"].isin(relevant_ids)]
print(len(df))

df = df[df["status"] == "OK"]
print(len(df))

df.to_csv("test_transcripts.csv", index = False)


# df = pd.read_json("sampled_w_metadata.json")
#
# df["duration"] = pd.to_timedelta(df["duration"])
#
# df["duration"] = df["duration"].dt.total_seconds() / 60
#
# print(df["duration"].median())
# print(df["duration"].mean())


# df = pd.read_csv("../../Transcript files/transcripts_conflict_over_time_sampled.csv")
# print(len(df))
# df = df[~df.status.str.contains("retries")]
# print(len(df))
# df.to_csv("../../Transcript files/transcripts_conflict_over_time_sampled.csv", index = False)
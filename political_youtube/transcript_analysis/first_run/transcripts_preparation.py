import pandas as pd

# keep only transcripts from manually graded list




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
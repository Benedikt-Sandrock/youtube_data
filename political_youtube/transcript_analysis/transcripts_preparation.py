import pandas as pd

df = pd.read_json("sampled_w_metadata.json")

df["duration"] = pd.to_timedelta(df["duration"])

df["duration"] = df["duration"].dt.total_seconds() / 60

print(df["duration"].median())
print(df["duration"].mean())
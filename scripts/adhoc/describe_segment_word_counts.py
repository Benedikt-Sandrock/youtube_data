import pandas as pd

CHANNELS = [
    "UCQGqiGhMjc_p4lZEhSTb12g",
    "UCcoQ3WG2J_Xjwwyt-sJqh-w",
    "UCXJBRgiZRZvfilIGQ4wN5CQ",
    "UC5NOEUbkLheQcaaRldYW5GA",
    "UCqLv2nTsMB_FXtQRFNXjWhA",
    "UC9qdoYTVU413M6EvqDRZDtA"
]

CHANNELS_POPULISM = [
    "UCksi8_CDUF0DbnLrgIoRrRg",
    "UCgvFsn6bRKqND1cW3HpzDrA",
    "UCbanHTRuGv2Fi7flpO735yw",
    "UCACdxU3VrJIJc7ujxtHWs1w",
    "UCZHpIFMfoJJ_1QxNGLJTzyA",
]

df = pd.read_csv("descriptive_sample_baseline_segments.csv")

print(df["n_woerter"].mean())
print(df["n_woerter"].median())

df = df.sort_values(by = "n_woerter", ascending = False)
print(df["n_woerter"].describe())
# df = df[df["channel_id"] == "UCiTJladOHCMkKndVBsn23VQ"]

# df = df[df["channel_id"].isin(CHANNELS)]

# print(len(df))

# print(df["channel_id"].unique())
# df.to_csv("single_channels_test_populism.csv")
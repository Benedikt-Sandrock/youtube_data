import pandas as pd

from youtube_code.config import OUTPUTS, SAMPLES, EXTERNAL

VIDEO_PATH = OUTPUTS / "sample_feasibility" / "videos_compact_pol_labels.csv"
RESULTS_PATH = OUTPUTS / "segment_analysis"
MEDIA_PATH = EXTERNAL / "media_type_russia_merged.xlsx"

df2 = pd.read_excel(MEDIA_PATH)
df = pd.read_csv(RESULTS_PATH / "channel_video_position.csv")
df = pd.merge(df, df2, on = "channel_id", how = "left")

vars = ["n_deskriptiv_russland", "position_russland", "type"]
df = df.groupby(["channel_title", "rel_monat"]).agg(
    n_deskriptiv_russland = ("n_deskriptiv_russland", "sum"),
    position_russland = ("position_russland", "mean"),
    type = ("type", "first"),
    n_videos = ("channel_id", "count")
).reset_index()

# vars = ["position_russland", "position_westpolitik"]
# df = df.groupby("channel_title")[vars].mean().reset_index()
print(len(df))
df.to_csv("temp.csv", index = False)
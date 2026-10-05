import pandas as pd
import numpy as np
import json
from youtube_code.config import SAMPLES, OUTPUTS, SRC
from youtube_code.store.transcript_store import attempted_video_ids

IDS ={"DoH_MWRZhIE", "5_Qi6u23hPc", "3ZXGvYQI5Y8", "YjKKy361zZ0"}

POPULISM_VARS = ["volkszentrismus", "antielitismus", "manichaeische_moralisierung",
                 "emotionale_intensitaet"]

RESULTS_PATH_IDEOLOGIE = "run_0005_IDEOLOGIE_I.csv"
RESULTS_PATH_POPULISMUS = "run_0009_POPULISMUS_P.csv"

METADATA_PATH = SAMPLES / "russia" / "out_segments"/ "descriptive_sample_baseline.csv"

def check_ideologie_results(results_path, metadata_path):
    dfc = pd.read_csv(metadata_path, usecols = ["video_id", "channel_id"])
    df = pd.read_csv(results_path)
    df = df[["video_id", "wirtschaft", "gesellschaft"]]

    # df["wirtschaft"] = pd.to_numeric(df["wirtschaft"].replace("null", np.nan))
    # df["gesellschaft"] = pd.to_numeric(df["gesellschaft"].replace("null", np.nan))

    df = pd.merge(df, dfc, on ="video_id", how = "left")
    print(len(df))

    df_agg = df.groupby("channel_id").agg(
        gesellschaft = ("gesellschaft", "mean"),
        wirtschaft = ("wirtschaft", "mean")
    )
    print(df_agg)

    df = df[df["channel_id"] == "UCgvFsn6bRKqND1cW3HpzDrA"]
    print(df)

def check_populismus_results(results_path, metadata_path):
    dfc = pd.read_csv(metadata_path, usecols = ["video_id", "channel_id"])
    df = pd.read_csv(results_path)
    print(df.columns)
    df = df[["video_id", "volkszentrismus", "antielitismus", "manichaeische_moralisierung",
                "emotionale_intensitaet"]]

    df = pd.merge(df, dfc, on="video_id", how="left")
    print(len(df))

    df_agg = df.groupby("channel_id").agg(
        volkszentrismus = ("volkszentrismus", "mean"),
        antielitismus = ("antielitismus", "mean"),
        manichaeische_moralisierung = ("manichaeische_moralisierung", "mean"),
        emotionale_intensitaet = ("emotionale_intensitaet", "mean")
    )
    pd.set_option('display.max_columns', None)
    print(df_agg)

    # df = df[df["channel_id"] == "UCZHpIFMfoJJ_1QxNGLJTzyA"]
    # print(df)
    print(df[df["video_id"].isin(IDS)])

# check_populismus_results(RESULTS_PATH_POPULISMUS, METADATA_PATH)

def check_open_transcripts(paths):
    df = pd.concat(
        [pd.read_csv(p) for p in paths], ignore_index= True
    )
    with open(OUTPUTS / "sample_feasibility" / "vids_right.json", "r", encoding = "utf-8") as f:
        vids_right = json.load(f)

    with open(OUTPUTS / "sample_feasibility" / "wide.json", "r", encoding = "utf-8") as f:
        wide = json.load(f)

    with open(OUTPUTS / "sample_feasibility" / "wide_right.json", "r", encoding = "utf-8") as f:
        wide_right = json.load(f)

    transcripts = attempted_video_ids()

    classified = df["video_id"].to_list()
    classified = set(classified)

    new_vids_right = [v for v in vids_right if v not in classified]
    new_wide = [v for v in wide if v not in classified]
    new_wide_right = [v for v in wide_right if v not in classified]

    new_complete = new_vids_right + new_wide_right
    print(len(new_vids_right), len(new_wide), len(new_wide_right))

    available_right = [v for v in new_vids_right if v in transcripts]
    available_wide = [v for v in new_wide if v in transcripts]
    available_wide_right = [v for v in new_wide_right if v in transcripts]

    print(len(available_right), len(available_wide), len(available_wide_right))

    available_right_complete = available_right + available_wide_right

    df = pd.DataFrame(available_right_complete, columns = ["video_id"])
    df.to_csv("right_videos_to_classify.csv", index = False)

    with open("../../src/youtube_code/scraping/right_videos_to_scrape.json", "w") as f:
        json.dump(new_complete, f, ensure_ascii = False, indent = 2)


paths = ["run_0011_POSITION_V1.csv", "run_0010_POPULISMUS_P.csv"]

# check_open_transcripts(paths)




# df = pd.read_csv("../sample_feasibility/war_vids.csv")
# ids = df["video_id"].to_list()
#
# df2 = pd.read_csv(TRANSCRIPTS / "all_transcripts_segments.csv", usecols = ["video_id"])
# transcripts = df2["video_id"].to_list()
#
# df3 = pd.read_csv("run_0010_POPULISMUS_P_corrected.csv")
# classified = df3["video_id"].to_list()
# classified = set(classified)
#
# new_ids = [i for i in ids if i not in classified]
#
# available_ids = [i for i in new_ids if i in transcripts]
# unavailable_ids = [i for i in new_ids if i not in transcripts]
# print(f"available:{len(available_ids)}")
# print(f"NOT available: {len(unavailable_ids)}")
#
# df = pd.DataFrame({"video_id": available_ids})
#
# splits = np.array_split(np.arange(len(df)), 4)
#
# df1, df2, df3, df4 = (df.iloc[idx] for idx in splits)
#
# df1.to_csv("videos_to_classify_populism1.csv", index = False)
# df2.to_csv("videos_to_classify_populism2.csv", index = False)
# df3.to_csv("videos_to_classify_populism3.csv", index = False)
# df4.to_csv("videos_to_classify_populism4.csv", index = False)

# df = pd.read_csv("run_0019_POPULISMUS_P.csv")
# print(len(df))
# mask = df["kodierbar"] == False
# df.loc[mask, POPULISM_VARS] = np.nan
# # df = df[df["parse_error"].isnull()]
# # df = df[df["ok_score"] == True]
# print(len(df))
# df.to_csv("run_0019_POPULISMUS_P_corrected.csv")
# print(len(df))
# print(df.loc[mask, "antielitismus"].mean())

# files = [
#     "run_0010_POPULISMUS_P.csv",
#     "run_0016_POPULISMUS_P.csv",
#     "run_0017_POPULISMUS_P.csv",
#     "run_0018_POPULISMUS_P.csv",
#     "run_0019_POPULISMUS_P.csv",
#     "run_0015_POPULISMUS_P.csv",
# ]
# dfs = [pd.read_csv(f, engine="pyarrow") for f in files]
# df = pd.concat(dfs, ignore_index=True)
# df.to_csv("populism_runs_combined.csv", index = False)
#
# print(len(df))

df = pd.read_csv("channel_video_populism.csv")
df = df[df["channel_id"] == "UC0sfnuCUaYV2twmfZDtXZng"]
print(len(df))
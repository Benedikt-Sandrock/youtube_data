import pandas as pd
import json

from youtube_code.config import SAMPLES, EXPLORATION
from youtube_code.store.video_registry import  get_video_metadata, topic_relevant_video_ids, coverage_report
from youtube_code.store.screening_state_store import get_state
from youtube_code.store.transcript_store import attempted_video_ids, has_transcript
from youtube_code.store.llm_run_store import get_video_ids_for_prompt

CHANNELS_PATH = SAMPLES / "russia_longitudinal_v1" / "channel_sample_provenance.csv"

channels = pd.read_csv(CHANNELS_PATH, usecols = ["channel_id"])["channel_id"].tolist()
print(f"# Channels: {len(channels)}")

baseline_periods = [-1,0,1,2,3]


def create_channel_overview():
    df = get_video_metadata(channels)

    topic_ids = topic_relevant_video_ids("russia_ukraine_war")

    df["is_relevant"] = df["video_id"].isin(topic_ids)

    df_grouped = df.groupby(["channel_id"]).agg(
        channel_title = ("channel_title", "first"),
        topic_vids = ("is_relevant", "sum"),
        all_vids = ("video_id", "count")
    ).reset_index()

    print(f"# Channels after aggregation: {len(df_grouped)}")

    new = df_grouped["channel_id"].tolist()
    out = [c for c in channels if c not in new]
    print(f"Dropped IDs: {out}")
    added = [c for c in new if c not in channels]
    print(f"Added IDs: {added}")

    df_grouped.to_csv("output/topic_vids_per_channel.csv", index = False)

    active_channels = set(df_grouped[df_grouped["topic_vids"] > 4]["channel_id"].tolist())

    coverage_df = coverage_report(active_channels)
    coverage_df.to_csv("output/coverage_active_channels.csv", index = False)
    # df = df["channel_id"].isin(active_channels)


def compare_to_screening_state():
    print("getting state")
    state_df = get_state(channel_ids=active)

    print("grouping state")
    grouped_state = state_df.groupby("channel_id").agg(
        all_vids_state=("video_id", "count")
    ).reset_index()

    print("merging")
    merged = pd.merge(df_topic_vids, grouped_state, on="channel_id", how="outer")

    merged["problem"] = merged["all_vids_state"] != merged["all_vids"]
    merged["diff"] = merged["all_vids"] - merged["all_vids_state"]

    merged.to_csv("output/merged.csv", index=False)


def create_baseline_vids_overview():
    state = get_state(channel_ids=active)
    print(f"len before: {len(state)}")

    state["baseline"] = state["interval_index"].isin(baseline_periods)

    state = state[state["baseline"] == True]
    print(f"len after: {len(state)}")

    ids = state[state["politics_final"] == 1]["video_id"].tolist()
    print(f"There are {len(ids)} baseline videos in total.")
    attempted = attempted_video_ids()
    todo = {i for i in ids if i not in attempted}
    print(f"For {len(todo)} IDs (political baseline videos), the transcript can be requested.")

    transcript_available = has_transcript(ids)
    classified = get_video_ids_for_prompt("IDEOLOGIE_I")

    do_classification = [i for i in ids if i in transcript_available and i not in classified]
    print(f"{len(do_classification)} videos can be classified via LLM.")

    state["politics"] = state["politics_final"] == 1
    state["unsure"] = state["politics_final"] == -1
    state["non_politics"] = state["politics_final"] == 0
    state["not_classified"] = state["politics_final"].isna()
    state["classified"] = state["video_id"].isin(classified)
    state["attempted"] = state["video_id"].isin(attempted)
    state["available"] = state["video_id"].isin(transcript_available)

    state_grouped = state.groupby(["channel_id"]).agg(
        # channel_title = ("channel_title", "first"),
        all_vids=("video_id", "count"),
        politics_vids=("politics", "sum"),
        unsure_vids=("unsure", "sum"),
        non_politics_vids=("non_politics", "sum"),
        leftover=("not_classified", "sum"),
        classified = ("classified", "sum"),
        attempted = ("attempted", "sum"),
        available = ("available", "sum")
    ).reset_index()

    state_grouped["quote"] = state_grouped["available"] / state_grouped["attempted"]
    state_grouped["quote"] = state_grouped["quote"].fillna(9)

    state_grouped = pd.merge(state_grouped, df_topic_vids[["channel_id", "channel_title"]], on="channel_id", how="left")
    state_grouped.to_csv("output/state_grouped.csv", index=False)

    # find IDs to download
    # exclude channels with >=10 classified videos OR a availability-ratio < 0.1

    satisfied = state_grouped[state_grouped["classified"] >= 10]["channel_id"].tolist()
    low_quote = state_grouped[state_grouped["quote"] < 0.1]["channel_id"].tolist()
    print(len(state))

    state = state[(~state["channel_id"].isin(satisfied))]
    print(len(state))

    channels_todo = (state_grouped[(state_grouped["classified"] < 10)
                                  & (~state_grouped["channel_id"].isin(low_quote))]["channel_id"]
                     .tolist())
    with open(EXPLORATION / "channels_add_screening.json", "w") as f:
        json.dump(channels_todo, f, ensure_ascii=False, indent=2)

    ids = state[state["politics_final"] == 1]["video_id"].tolist()
    print(f"There are {len(ids)} baseline videos after filtering.")
    todo = {i for i in ids if i not in attempted}
    print(f"For {len(todo)} of those IDs (political baseline videos), the transcript can be requested.")

    todo = list(todo)
    with open("../../src/youtube_code/step4_transcript_download/request_transcripts.json", "w") as f:
        json.dump(todo, f, ensure_ascii = False, indent = 2)

    transcript_available = has_transcript(ids)
    classified = get_video_ids_for_prompt("IDEOLOGIE_I")

    do_classification = [i for i in ids if i in transcript_available and i not in classified]
    print(f"{len(do_classification)} videos can be classified via LLM.")
    do_classification = pd.DataFrame(do_classification, columns = ["video_id"])
    do_classification.to_csv(EXPLORATION / "todo_ideology.csv", index = False)




# create_channel_overview()

active = pd.read_csv("output/coverage_active_channels.csv")["channel_id"].tolist()
print(f"# Active channels: {len(active)}")

df_topic_vids = pd.read_csv("output/topic_vids_per_channel.csv")
df_topic_vids = df_topic_vids[df_topic_vids["topic_vids"] > 4]
before = df_topic_vids["channel_id"].tolist()

dropped = [c for c in before if c not in active]
print(dropped)

# compare_to_screening_state()

create_baseline_vids_overview()

import pandas as pd
import sqlite3

from youtube_code.store.video_registry import coverage_report, get_video_metadata
from youtube_code.store.transcript_store import has_transcript
from youtube_code.store.llm_run_store import get_video_ids_for_prompt
from youtube_code.config import SAMPLES, EXPLORATION, STORE


DB_PATH = STORE / "video_registry.sqlite"
channel_path = SAMPLES / "russia_longitudinal_v1" / "channel_sample_provenance.csv"
channels = pd.read_csv(channel_path, usecols =["channel_id", "channel_title"])
channel_ids = channels["channel_id"].tolist()

df = get_video_metadata(channel_ids, duration_filter=False)

query_2 = "SELECT video_id, is_relevant FROM video_topic_relevance"

with sqlite3.connect(DB_PATH) as con:
    t_data = pd.read_sql_query(query_2, con)

df = pd.merge(df, t_data, on = "video_id", how = "left")

print(f"Total videos: {len(df)}")
print(f"Videos longer than 180 seconds: {len(df[df["meets_min_duration"] == True])}")
print(f"Topic Videos: {len(df[(df["is_relevant"] == 1) &  (df["meets_min_duration"] == True)])}")

topic_df = df[df["is_relevant"] == True]
topic_ids = topic_df["video_id"].tolist()

available_transcripts = has_transcript(topic_ids)
print(f"Topic Videos with available transcript: {len(available_transcripts)}")

classified_pos = get_video_ids_for_prompt("POSITION_V1")
classified_pop = get_video_ids_for_prompt("POPULISMUS_P")
classified_ide = get_video_ids_for_prompt("IDEOLOGIE_I")

topic_pop = [v for v in topic_ids if v in classified_pop]
topic_pos = [v for v in topic_ids if v in classified_pos]


print(f"Thereof classified with Position/Populism: {len(topic_pos), len(topic_pop)}")
print(f"Total classified Position/Populism: {len(classified_pos), len(classified_pop)}")
print(f"Total classified Ideology: {len(classified_ide)}")


def create_todo_lists():
    todo_pop = [v for v in available_transcripts if v not in classified_pop]
    todo_pos = [v for v in available_transcripts if v not in classified_pos]

    df_pop = pd.DataFrame(todo_pop, columns=["video_id"])
    df_pos = pd.DataFrame(todo_pos, columns=["video_id"])

    df_pop.to_csv(EXPLORATION / "populism_todo.csv", index=False)
    df_pos.to_csv(EXPLORATION / "position_todo.csv", index=False)


def create_coverage_report():
    placeholders = ",".join("?"* len(channel_ids))
    query = f"SELECT channel_id, published_at FROM channels WHERE channel_id IN ({placeholders})"

    with sqlite3.connect(DB_PATH) as con:
        c_data = pd.read_sql_query(query, con, params = channel_ids)

    c_data = c_data.rename(columns = {"published_at": "created_at"})
    print(c_data.head())
    df = coverage_report(channel_ids)

    df = pd.merge(df, c_data, on = "channel_id", how = "left")

    df["aeltestes_video"] = pd.to_datetime(df["aeltestes_video"], format="ISO8601")
    df["created_at"] = pd.to_datetime(df["created_at"], format="ISO8601")

    df["first_video_after"] = (df["aeltestes_video"] - df["created_at"]).dt.days


    df.to_csv(EXPLORATION / "coverage_report.csv", index = False)
import pandas as pd

from youtube_code.config import RAW, OUTPUTS
from youtube_code.utils.transcript_store import get_transcripts

POPULISM_RUNS = OUTPUTS / "segment_analysis" / "populism_runs_combined.csv"
POSITION_RUN = OUTPUTS/ "segment_analysis" / "run_0011_POSITION_V1.csv"
DB_TRANSCRIPTS = RAW / "transcripts.sqlite"


dfpop = pd.read_csv(POPULISM_RUNS)
dfpos = pd.read_csv(POSITION_RUN)

pos_ids= set(dfpos["video_id"])
pop_ids = set(dfpop["video_id"])


print(len(pop_ids), len(pos_ids))

new_ids = pop_ids - pos_ids
print(len(new_ids))
total_len = len(new_ids)


chunk_size = (total_len +3) // 4
for i, chunk in enumerate(chunks):
    output_path = OUTPUTS / "segment_analysis" / f"missing_position_{i}.csv"

    chunk.to_csv(output_path, index = False)


df.to_csv("missing_position.csv")

# query = """
#     SELECT t.video_id, t.status, t.transcript_segments, l.source
#     FROM transcripts t
#     JOIN llm_runs l USING(video_id)
#     WHERE t.status = 'OK' AND l.source = 'segment_analysis_active'
# """
#
# with sqlite3.connect(DB_TRANSCRIPTS) as db:
#
#     db.execute("ATTACH DATABASE ? AS LLM", (str(DB_LLM)))
#     df = pd.read_sql_query(query, db)
#
# print(len(df))
import pandas as pd

from youtube_code.config import RAW, OUTPUTS
from youtube_code.utils.transcript_store import get_transcripts

POPULISM_RUNS = OUTPUTS / "segment_analysis" / "populism_runs_combined.csv"
DB_TRANSCRIPTS = RAW / "transcripts.sqlite"


dfpop = pd.read_csv(POPULISM_RUNS)
IDS = set(dfpop["video_id"])
print(len(IDS))


transcripts = get_transcripts(IDS)
print(len(transcripts))

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
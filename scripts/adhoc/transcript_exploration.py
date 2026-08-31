import pandas as pd
import sqlite3

from youtube_code.config import RAW

DB_TRANSCRIPTS = RAW / "transcripts.sqlite"


query = """
    SELECT t.video_id, t.status, t.transcript_segments, l.source
    FROM transcripts t 
    JOIN llm_runs l USING(video_id)
    WHERE t.status = 'OK' AND l.source = 'segment_analysis_active'
"""

with sqlite3.connect(DB_TRANSCRIPTS) as db:

    db.execute("ATTACH DATABASE ? AS LLM", (str(DB_LLM)))
    df = pd.read_sql_query(query, db)

print(len(df))
from youtube_code.store.transcript_store import attempted_video_ids, has_transcript
import json

ids = attempted_video_ids()
available = has_transcript(ids)
print(len(ids), len(available))

available = list(available)
with open("ids_to_scrape.json", "w", encoding = "utf-8") as f:
    json.dump(available, f, ensure_ascii=False, indent = 2)
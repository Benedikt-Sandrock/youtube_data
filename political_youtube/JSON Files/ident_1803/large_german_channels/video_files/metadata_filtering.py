import json
import isodate

limit = 60

with open("metadata_all_videos_100k_channels_keywords.json", "r", encoding = "utf-8") as f:
    data = json.load(f)
print(len(data))
data = [item for item in data if isodate.parse_duration(item["duration"]).total_seconds() > limit]

with open("metadata_100k_channels_keywords_wo_shorts.json", "w", encoding = "utf-8") as f:
    json.dump(data, f, indent= 2, ensure_ascii=False)
print(len(data))
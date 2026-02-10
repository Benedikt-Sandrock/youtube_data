import json

with open("../../JSON Files/keyword_vids/videos_keywords_total_3years_metadata.json", "r", encoding ="utf-8") as f:
    data = json.load(f)

print(len(data))
viewed_videos = [v for v in data if int(v["view_count"]) > 10000]
print(len(viewed_videos))

with open("../../JSON Files/keyword_vids/videos_keywords_3years_viewed.json", "w", encoding="utf-8") as f:
    json.dump(viewed_videos, f, ensure_ascii=False, indent=4)
import json

file_path = "../JSON Files/videos/videos_total.json"

with open(file_path, "r", encoding = "utf-8") as f:
    data = json.load(f)

for video in data:
    if video["title"] == None:
        cid = video["channel_id"]
        video["title"] = f"no_video_found_{cid}"
        video["published_at"] = f"no_video_found_{cid}"

with open("../JSON Files/videos/videos_total.json", "w", encoding = "utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent = 2)

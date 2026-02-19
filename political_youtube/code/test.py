import json

file_path = "../JSON Files/videos/videos_keywords_total.json"

with open(file_path, "r", encoding = "utf-8") as f:
    data = json.load(f)

unique_channels = {v["channel_id"] for v in data}
print(len(unique_channels))

with open("../JSON Files/large_channels.json") as f:
    data_2 = json.load(f)

print(len(data_2))
# for video in data:
#     if video["title"] == None:
#         cid = video["channel_id"]
#         video["title"] = f"no_video_found_{cid}"
#         video["published_at"] = f"no_video_found_{cid}"

# with open("../JSON Files/videos/videos_total.json", "w", encoding = "utf-8") as f:
#     json.dump(data, f, ensure_ascii=False, indent = 2)

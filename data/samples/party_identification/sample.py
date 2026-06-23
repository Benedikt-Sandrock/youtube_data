import json
from youtube_code.utils import load_json, load_set

data = load_json("keyword_videos_50k_channels_name.json")
cids = {item["channel_id"] for item in data}

data = load_json("sampled_50k_channels.json")
print(len(data))
data = [item for item in data if item["channel_id"] in cids]
print(len(data))
with open("sampled_50k_channels_filtered.json", "w", encoding = "utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent = 2)

import json
import random
from collections import defaultdict
from datetime import datetime, timezone

input_file = f"../../JSON Files/videos_by_channel_total_german_3years.json"

keyword_file = f"../../JSON Files/videos_keywords_total_3years.json"
sampled_file = f"../../JSON Files/videos_sampled_total_3years.json"

keywords = [
    "nahost",
    "israel",
    "palästina",
    "gaza",
    "hamas",
    "IDF",
    "Jerusalem"
]

stichtag = "2023-10-07T00:00:00Z"
stichtag_dt = datetime.fromisoformat(stichtag.replace("Z", "+00:00"))

sample_size = 100

random.seed(42)

# JSON laden
with open(input_file, "r", encoding="utf-8") as f:
    data = json.load(f)

# Nach Channel gruppieren
channels = defaultdict(list)
for v in data:
    channels[v["channel_id"]].append(v)

keyword_videos = []
sampled_videos = []

for channel_id, videos in channels.items():

    with_keywords = []
    without_keywords = []

    for v in videos:
        title = v.get("title", "").lower()

        if any(k.lower() in title for k in keywords):
            with_keywords.append(v)
        else:
            without_keywords.append(v)

    keyword_videos.extend(with_keywords)

    before = []
    after = []

    for v in without_keywords:
        published = datetime.fromisoformat(
            v["published_at"].replace("Z", "+00:00")
        )

        if published < stichtag_dt:
            before.append(v)
        else:
            after.append(v)

    if len(before) > sample_size:
        before = random.sample(before, sample_size)

    if len(after) > sample_size:
        after = random.sample(after, sample_size)

    sampled_videos.extend(before + after)

# Dateien speichern
with open(keyword_file, "w", encoding="utf-8") as f:
    json.dump(keyword_videos, f, ensure_ascii=False, indent=2)

with open(sampled_file, "w", encoding="utf-8") as f:
    json.dump(sampled_videos, f, ensure_ascii=False, indent=2)

print("Fertig!")
print(f"Keyword-Videos: {len(keyword_videos)}")
print(f"Gesampelte Videos: {len(sampled_videos)}")


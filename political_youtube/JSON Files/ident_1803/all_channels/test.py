import json

with open("channel_metadata_control.json", "r", encoding = "utf-8") as f:
    data = json.load(f)

with open("complete_channel_list.json", "r", encoding="utf-8") as f:
    channels = json.load(f)

ids_metadata = [c["channel_id"] for c in data]

print(len(channels))
print(len(ids_metadata))

ids_metadata =set(ids_metadata)
channels = set(channels)

not_classified = channels - ids_metadata
classified = ids_metadata & channels
print(len(not_classified))
print(len(classified))

kek = [item for item in data if item["channel_id"] in classified]
kek = [item["name"] for item in kek]
with open("classified", "w", encoding="utf-8")as f:
    json.dump(kek, f, indent =2, ensure_ascii=False)

kek = set(kek)

with open("../large_german_channels/german_channels_100000k_backup.json", "r", encoding="utf-8") as f:
    large_channels = json.load(f)

large_channels = [item["name"] for item in large_channels]

large_channels = set(large_channels)
print(len(large_channels))
not_anymore = large_channels - kek
both = large_channels & kek
new = kek - large_channels

print(both)
print(len(both))
print(not_anymore)
print(new)


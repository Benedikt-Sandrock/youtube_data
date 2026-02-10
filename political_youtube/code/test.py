import json

file_path = "../JSON Files/large_channels.json"

with open(file_path, "r", encoding = "utf-8") as f:
    data = json.load(f)

large_channels_list = [c["Channel_ID"] for c in data]

with open("../JSON Files/large_channels_list.json", "w", encoding = "utf-8") as f:
    json.dump(large_channels_list, f, ensure_ascii=False, indent = 2)

from youtube_code.utils import load_set
import json
list_1 = load_set("../conflict_over_time/channel_list.json")
list_2 = load_set("../party_identification/channel_list.json")

all_channels = list_1 | list_2

all_channels = list(all_channels)

with open("channel_list.json", "w", encoding ="utf-8") as f:
    json.dump(all_channels, f, ensure_ascii = False, indent = 2)
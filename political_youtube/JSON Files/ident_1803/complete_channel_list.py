import os
import json


def collect_unique_ids(directory, filename):
    unique_ids = set()

    for root, dirs, files in os.walk(directory):
        if filename in files:
            path = os.path.join(root, filename)

            with open(path, 'r', encoding='utf-8') as f:
                daten = json.load(f)
                unique_ids.update(daten)

    return list(unique_ids)


# result = collect_unique_ids("../ident_1803", "all_channel_ids_discovered.json")
# print(f"Gefundene unterschiedliche Einträge: {len(result)}")
# print(result)
#
# with open("complete_channel_list.json", "w", encoding="utf-8") as f:
#     json.dump(result, f, indent=2, ensure_ascii=False)

with open("complete_channel_list_classified.json", "r", encoding="utf-8") as f:
    data = json.load(f)

german_channels = [c["channel_id"] for c in data if c["is_german"]]
print(len(german_channels))
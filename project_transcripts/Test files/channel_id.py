from googleapiclient.discovery import build
import json

api_key = "AIzaSyBUg0XIryem2_WtenRUKDA1bwLsiDzMLYE"
youtube = build('youtube', 'v3', developerKey=api_key)

# with open("../Code/json_files/all_channel_ids.json") as f:
#     all_ids = json.load(f)

def channel_id_to_name(list_of_ids):
    results = []
    for channel_id in list_of_ids:
        try:
            request = youtube.channels().list(
                part="snippet",
                id = channel_id
            )
            response = request.execute()
            items = response.get("items", [])
            if items:
                channel_title = items[0]["snippet"]["title"]
                results.append(channel_title)
                print(f"{channel_id} -> {channel_title}")
            else:
                # Kanal existiert nicht oder gesperrt
                results.append(None)
                print(f"{channel_id} -> Kein Kanal gefunden")

        except Exception as e:
            results.append(None)
            print(f"{channel_id} -> Fehler: {e}")
    return results



import json
with open("../JSON Files/all_channel_ids_discovered.json", "r") as f:
    data = json.load(f)

channel_id_to_name(data)

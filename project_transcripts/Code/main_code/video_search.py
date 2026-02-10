from googleapiclient.discovery import build
import json
import os
from project_transcripts.Code.main_code.key_variables import ziel_directory, query_list, start_date, final_end_date
from help_functions import is_german_channel, load_set, set_to_json
from dateutil.relativedelta import relativedelta


api_key = "AIzaSyBUg0XIryem2_WtenRUKDA1bwLsiDzMLYE"

youtube = build('youtube', 'v3', developerKey=api_key)

ziel_directory = os.path.join(ziel_directory, "monthly")
os.makedirs(ziel_directory, exist_ok=True)

###
#Dateipfade definieren
###

all_channels_path = os.path.join(ziel_directory, "all_channel_ids_discovered_monthly.json")
german_channels_path = os.path.join(ziel_directory, "channel_ids_classified", "all_channel_ids_german_monthly.json")
foreign_channels_path = os.path.join(ziel_directory, "channel_ids_classified", "all_channel_ids_foreign_monthly.json")
german_channels_reference = "../JSON Files/channel_ids_classified/all_channel_ids_german_3years.json"
foreign_channels_reference = "../JSON Files/channel_ids_classified/all_channel_ids_foreign_3years.json"

###
#Dateien laden
###
german_ref = load_set(german_channels_reference)
foreign_ref = load_set(foreign_channels_reference)

all_channel_ids = load_set(all_channels_path)
german_channels = load_set(german_channels_path)
foreign_channels = load_set(foreign_channels_path)

###
#Suche nach Stichwörtern
###

for query in query_list:
    print(f"Suchanfrage: {query}")
    print(f"Gesamter Zeitraum: {start_date} bis {final_end_date}")

    # dir_path = f"{ziel_directory}/files_queries/files_{query}"
    # os.makedirs(dir_path, exist_ok=True)

    #monatliche Abfrage
    current_start = start_date
    results = []

    while current_start < final_end_date:
        current_end = current_start + relativedelta(months = 1)
        if current_end > final_end_date:
            current_end = final_end_date

        published_after_ident = current_start.strftime('%Y-%m-%dT%H:%M:%SZ')
        published_before_ident = current_end.strftime('%Y-%m-%dT%H:%M:%SZ')
        #print(f"Aktueller Zeitraum: {published_after_ident} bis {published_before_ident}")

        #Anfrage an Youtube
        next_page_token = None

        while True:
            request = youtube.search().list(
                part="id,snippet",
                q=query,
                type="video",
                publishedAfter=published_after_ident,
                publishedBefore=published_before_ident,
                order="date",
                maxResults=50,
                pageToken=next_page_token,
                relevanceLanguage = "de"
            )

            response = request.execute()
            results.extend(response.get("items", []))
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        current_start = current_end

    #Zwischenspeicherung der Daten
    videos = [
        {
            "video_id": item["id"]["videoId"],
            "channel_id": item["snippet"]["channelId"],
            "published_at": item["snippet"]["publishedAt"],
            "title": item["snippet"]["title"]
        }
        for item in results
    ]
    print(f"Gefundene Videos: {len(videos)}")
    # with open(f"{ziel_directory}/files_queries/files_{query}/videos_{query}.json", "w", encoding ="utf-8") as f:
    #     json.dump(videos, f, indent=2, ensure_ascii=False)

    #Extraktion der Channel IDs
    channel_ids = {video["channel_id"] for video in videos}
    print(f"Einzigartige Kanäle: {len(channel_ids)}")
    print(channel_ids)
    all_channel_ids.update(channel_ids)

    #Überprüfung, ob bereits gefunden. Wenn nicht, Klassifikation deutsch/nicht deutsch
    already_classified = german_channels | foreign_channels
    new_channels = channel_ids - already_classified
    print(f"Neue Kanäle: {len(new_channels)}")

    in_list_count = 0
    for idx, cid in enumerate(new_channels, start = 1):
        try:
            if cid in german_ref:
                german_channels.add(cid)
                print(f"[{idx}/{len(new_channels)}] {cid} → DE")
                in_list_count += 1

            elif cid in foreign_ref:
                foreign_channels.add(cid)
                print(f"[{idx}/{len(new_channels)}] {cid} → NON-DE")
                in_list_count +=1

            else:
                is_german, _ = is_german_channel(youtube, cid)
                if is_german:
                    german_channels.add(cid)
                    german_ref.add(cid)
                    print(f"[{idx}/{len(new_channels)}] {cid} → DE")
                else:
                    foreign_channels.add(cid)
                    foreign_ref.add(cid)
                    print(f"[{idx}/{len(new_channels)}] {cid} → NON-DE")

        except Exception as e:
            print(f"Fehler bei Channel {cid}: {e}")
            break
    print(f"{in_list_count} von {len(new_channels)} waren bereits klassifiziert.")


    #Speichern der Ergebnisse

    # with open(f"{ziel_directory}/files_queries/files_{query}/channel_ids_{query}.json", "w", encoding="utf-8") as f:
    #     json.dump(sorted(channel_ids), f, indent=2)

    with open(all_channels_path, "w", encoding="utf-8") as f:
        json.dump(sorted(all_channel_ids), f, indent=2, ensure_ascii=False)

    with open(german_channels_path, "w", encoding="utf-8") as f:
        json.dump(sorted(german_channels), f, indent=2, ensure_ascii=False)

    with open(foreign_channels_path, "w", encoding="utf-8") as f:
        json.dump(sorted(foreign_channels), f, indent=2, ensure_ascii=False)
    print("Klassifizierte Channels gespeichert")

    #safe_json(foreign_channels_path, foreign_channels)
    set_to_json(german_channels_reference, german_ref)
    set_to_json(foreign_channels_reference, foreign_ref)
    print("Referenzlisten aktualisiert")



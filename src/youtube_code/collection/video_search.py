from googleapiclient.discovery import build
import json
import os
from dateutil.relativedelta import relativedelta

from settings_variables import query_list, target_directory, start_date, final_end_date, month_interval
from src.youtube_code.utils import load_set
from src.youtube_code.config import API_KEY, API_KEY_C

YOUTUBE = build('youtube', 'v3', developerKey=API_KEY)


config_text = (
    "Configuration:\n"
    f"Query: {query_list}\n"
    f'Target directory: "{target_directory}"\n'
    f"Search from {start_date} to {final_end_date}\n"
    f"Search interval: {month_interval} month(s)")

print(config_text)

answer = input("Right specification? [y/n]")
if not answer.lower() == "y":
    print("Wrong specification. Check 'settings_variables.py'")
    exit()

config_path = os.path.join(target_directory, "configuration.txt")
os.makedirs(target_directory, exist_ok=True)

with open(config_path, "w", encoding = "utf-8") as f:
    f.write(config_text)

print(f"Configuration saved to {config_path}")
print("Directory is created and video search is initiated...")
os.makedirs(target_directory, exist_ok=True)

###
#Dateipfade definieren
###

all_channels_path = os.path.join(target_directory, "all_channel_ids_discovered.json")
# german_channels_path = os.path.join(target_directory, "channel_ids_classified", "all_channel_ids_german.json")
# foreign_channels_path = os.path.join(target_directory, "channel_ids_classified", "all_channel_ids_foreign.json")
# german_channels_reference = "../JSON Files/channel_ids_classified/all_channel_ids_german_reference.json"
# foreign_channels_reference = "../JSON Files/channel_ids_classified/all_channel_ids_foreign_reference.json"
identification_vids = os.path.join(target_directory, "identification_vids.json")

output_files = [all_channels_path, identification_vids, config_path]
existing_files = [f for f in output_files if os.path.exists(f)]

overwrite = False
if existing_files:
    print("\nWarning: The following output files already exist:\n")
    for f in existing_files:
        print(f" -", f)

    if config_path in existing_files:
        print("\nSearches already performed:\n")
        with open(config_path, "r") as f:
            file_content = f.read()
            print(file_content)
    while True:
        choice = input(
            "\n[a] append data\n"
            "[o] overwrite data\n"
            "[q] abort\n"
            "Choice: "
        ).lower()

        if choice == "a":
            overwrite = False
            break
        elif choice == "o":
            overwrite = True
            break
        elif choice == "q":
            print("Exit program.")
            exit()
        else:
            print("Invalid input")


###
#Dateien laden
###
print("Dateien werden geladen:")
# german_ref = load_set(german_channels_reference)
# foreign_ref = load_set(foreign_channels_reference)
if overwrite:
    all_channel_ids = set()
else:
    all_channel_ids = load_set(all_channels_path)
# german_channels = load_set(german_channels_path)
# foreign_channels = load_set(foreign_channels_path)

if overwrite:
    ident_vids = []
elif os.path.exists(identification_vids):
    with open(identification_vids, "r", encoding="utf-8") as f:
            ident_vids = json.load(f)
else:
    ident_vids = []

existing_video_ids = {v["video_id"] for v in ident_vids}

###
#Suche nach Stichwörtern
###

for query in query_list:
    print(f"\nSuchanfrage: {query}")
    print(f"Gesamter Zeitraum: {start_date} bis {final_end_date}")

    # dir_path = f"{target_directory}/files_queries/files_{query}"
    # os.makedirs(dir_path, exist_ok=True)

    #3-monatliche Abfrage
    current_start = start_date
    results = []

    while current_start < final_end_date:
        current_end = current_start + relativedelta(months = month_interval)
        if current_end > final_end_date:
            current_end = final_end_date

        published_after_ident = current_start.strftime('%Y-%m-%dT%H:%M:%SZ')
        published_before_ident = current_end.strftime('%Y-%m-%dT%H:%M:%SZ')
        #print(f"Aktueller Zeitraum: {published_after_ident} bis {published_before_ident}")

        #Anfrage an Youtube
        next_page_token = None

        while True:
            request = YOUTUBE.search().list(
                part="id,snippet",
                q=query,
                type="video",
                publishedAfter=published_after_ident,
                publishedBefore=published_before_ident,
                order="date",
                maxResults=50,
                pageToken=next_page_token,
                relevanceLanguage = "de",
                regionCode ="DE"
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
            "title": item["snippet"]["title"],
            "channel_id": item["snippet"]["channelId"],
            "channel_title": item["snippet"]["channelTitle"],
            "published_at": item["snippet"]["publishedAt"]
        }
        for item in results
    ]
    print(f"Gefundene Videos: {len(videos)}")

    for video in videos:
        if video["video_id"] not in existing_video_ids:
            ident_vids.append(video)
            existing_video_ids.add(video["video_id"])
    print("Video-Liste aktualisiert.")
    # with open(f"{target_directory}/files_queries/files_{query}/videos_{query}.json", "w", encoding ="utf-8") as f:
    #     json.dump(video_files, f, indent=2, ensure_ascii=False)

    #Extraktion der Channel IDs
    channel_ids = {video["channel_id"] for video in videos}
    print(f"\nEinzigartige Kanäle: {len(channel_ids)}")
    print(channel_ids)
    all_channel_ids.update(channel_ids)

    # region channel_classification
    #Überprüfung, ob bereits gefunden. Wenn nicht, Klassifikation deutsch/nicht deutsch
    # already_classified = german_channels | foreign_channels
    # new_channels = channel_ids - already_classified
    # print(f"Neue Kanäle: {len(new_channels)}")
    #
    # in_list_count = 0
    # for idx, cid in enumerate(new_channels, start = 1):
    #     try:
    #         if cid in german_ref:
    #             german_channels.add(cid)
    #             print(f"[{idx}/{len(new_channels)}] {cid} → DE")
    #             in_list_count += 1
    #
    #         elif cid in foreign_ref:
    #             foreign_channels.add(cid)
    #             print(f"[{idx}/{len(new_channels)}] {cid} → NON-DE")
    #             in_list_count +=1
    #
    #         else:
    #             is_german, _ = is_german_channel(youtube, cid)
    #             if is_german:
    #                 german_channels.add(cid)
    #                 german_ref.add(cid)
    #                 print(f"[{idx}/{len(new_channels)}] {cid} → DE")
    #             else:
    #                 foreign_channels.add(cid)
    #                 foreign_ref.add(cid)
    #                 print(f"[{idx}/{len(new_channels)}] {cid} → NON-DE")
    #
    #     except Exception as e:
    #         print(f"Fehler bei Channel {cid}: {e}")
    #         break
    # print(f"{in_list_count} von {len(new_channels)} waren bereits klassifiziert.")
    # endregion

    #Speichern der Ergebnisse
    with open(all_channels_path, "w", encoding="utf-8") as f:
        json.dump(sorted(all_channel_ids), f, indent=2, ensure_ascii=False)

    with open(identification_vids, "w", encoding = "utf-8") as f:
        json.dump(ident_vids, f, indent=2, ensure_ascii=False)


    # with open(german_channels_path, "w", encoding="utf-8") as f:
    #     json.dump(sorted(german_channels), f, indent=2, ensure_ascii=False)
    #
    # with open(foreign_channels_path, "w", encoding="utf-8") as f:
    #     json.dump(sorted(foreign_channels), f, indent=2, ensure_ascii=False)
    # print("\nKlassifizierte Channels gespeichert")

    #safe_json(foreign_channels_path, foreign_channels)
    # set_to_json(german_channels_reference, german_ref)
    # set_to_json(foreign_channels_reference, foreign_ref)
    # print("Referenzlisten aktualisiert")



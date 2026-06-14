from googleapiclient.discovery import build
from langdetect import detect, LangDetectException
from collections import Counter
from typing import Tuple
import os
import time
import pandas as pd
import json


def filter_blacklist(total_videos_input, blacklist_file, german_videos_output):
    #filters all video_files from total video_files that are not from german channels
    with open(total_videos_input, "r", encoding="utf-8") as f:
        data = json.load(f)

    with open(blacklist_file, "r") as f:
        blacklist = set(json.load(f))

    filtered_data = [
        item for item in data
        if item.get("channel_id") not in blacklist
    ]

    with open(german_videos_output, "w", encoding="utf-8") as f:
        json.dump(filtered_data, f, ensure_ascii=False, indent=2)

    print(f"Gefiltert: {len(data)} zu {len(filtered_data)} Videos")


def load_set(path):
    if os.path.exists(path):
        print(f"Datei wird eingelesen: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    print(f"{path} existiert nicht. Leeres Set wird erstellt.")
    return set()


def set_to_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(data), f, indent=2, ensure_ascii=False)


def get_channel_metadata(youtube, channel_ids):

    all_data = []
    for batch in chunk_list(channel_ids, 50):
        request = youtube.channels().list(
            part="snippet,statistics",
            id=",".join(batch)
        )
        response = request.execute()

        for item in response.get('items', []):
            data = {
                'name': item['snippet']['title'],
                'subscribers': int(item['statistics'].get('subscriberCount', 0)),
                'views': int(item['statistics'].get('viewCount', 0)),
                'video_files': int(item['statistics'].get('videoCount', 0)),
                'channel_id': item['id']
            }
            all_data.append(data)

    return all_data


def get_video_metadata(video_ids, youtube):
    all_videos = []

    for batch in chunk_list(video_ids, 50):
        request = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(batch)
        )
        response = request.execute()

        for item in response.get("items", []):
            video_data = {
                "video_id": item["id"],
                "title": item["snippet"]["title"],
                "channel_title": item["snippet"]["channelTitle"],
                "channel_id": item["snippet"]["channelId"],
                "published_at": item["snippet"]["publishedAt"],
                "duration": item["contentDetails"]["duration"],
                "view_count": item["statistics"].get("viewCount"),
                "like_count": item["statistics"].get("likeCount"),
                "comment_count": item["statistics"].get("commentCount"),
            }
            all_videos.append(video_data)

        time.sleep(0.1)

    return all_videos


def load_json(path):
    print(f"Reading file: '{path}'")
    with open(path, "r", encoding = "utf-8") as f:
        data = json.load(f)
        return data


def save_json(path, data, name = "data"):
    print(f"Saving {name} to '{path}'")
    with open(path, "w", encoding = "utf-8") as f:
        json.dump(data, f, indent = 2, ensure_ascii=False)


def chunk_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


def collect_unique_channel_ids(directory, filenames):
    if isinstance(filenames, str):
        filenames = [filenames]

    unique_ids = set()
    target_files = set(filenames)

    for root, dirs, files in os.walk(directory):
        found_files = target_files.intersection(files)

        for filename in found_files:
            path = os.path.join(root, filename)

            with open(path, 'r', encoding='utf-8') as f:
                daten = json.load(f)
                if isinstance(daten, list):
                    unique_ids.update(daten)
                else:
                    unique_ids.add(daten)

    return list(unique_ids)


def is_german_channel(youtube, channel_id: str, max_videos: int = 10, german_threshold: float = 0.7) -> Tuple[bool, dict]:
    """
    Prüft, ob ein YouTube-Kanal überwiegend deutschsprachig ist.
    """

    details = {
        "channel_id": channel_id,
        "defaultLanguage": None,
        "country": None,
        "german_ratio": 0.0
    }

    #Kanal-Metadaten
    channel_response = youtube.channels().list(
        part="snippet,contentDetails",
        id=channel_id
    ).execute()

    if not channel_response["items"]:
        return False, details

    snippet = channel_response["items"][0]["snippet"]
    details["defaultLanguage"] = snippet.get("defaultLanguage")
    details["country"] = snippet.get("country")

    #Harte Entscheidung
    if details["defaultLanguage"] == "de":
        return True, details

    #Upload-Playlist
    uploads_playlist_id = channel_response["items"][0]["contentDetails"][
        "relatedPlaylists"
    ]["uploads"]

    playlist_items = youtube.playlistItems().list(
        part="snippet",
        playlistId=uploads_playlist_id,
        maxResults=max_videos
    ).execute()

    video_ids = [
        item["snippet"]["resourceId"]["videoId"]
        for item in playlist_items.get("items", [])
    ]

    if not video_ids:
        return False, details

    #Videos abrufen
    videos_response = youtube.videos().list(
        part="snippet",
        id=",".join(video_ids)
    ).execute()

    languages = []

    for video in videos_response.get("items", []):
        text = f"{video['snippet']['title']} {video['snippet'].get('description', '')}"

        try:
            lang = detect(text)
            languages.append(lang)
        except LangDetectException:
            continue

    if not languages:
        return False, details

    counter = Counter(languages)
    german_ratio = counter.get("de", 0) / len(languages)
    details["german_ratio"] = round(german_ratio, 2)

    is_german = german_ratio >= german_threshold

    # Weiches Zusatzsignal
    if not is_german and details["country"] == "DE" and german_ratio >= 0.5:
        is_german = True

    return is_german, details


def classify_channels_from_json(youtube, input_json_path: str, output_all_channels_path: str, max_videos: int = 10):
    print("Classifying channels...")
    with open(input_json_path, "r", encoding="utf-8") as f:
        channel_ids = json.load(f)

    if os.path.exists(output_all_channels_path):
        with open(output_all_channels_path, "r", encoding="utf-8") as f:
            try:
                all_channels = json.load(f)
            except json.JSONDecodeError:
                all_channels = []
    else:
        all_channels = []

    reference_set = {v["channel_id"] for v in all_channels}
    german_channels = []
    foreign_channels = []
    counter = 0
    for idx, channel_id in enumerate(channel_ids, start=1):
        if channel_id in reference_set:
            #print(f"[{idx}/{len(channel_ids)}] {channel_id} → Übersprungen (bereits vorhanden)")
            counter +=1
            continue
        try:
            is_german, details = is_german_channel(
                youtube=youtube,
                channel_id=channel_id,
                max_videos=max_videos
            )
        except Exception as e:
            # Failsafe: Kanal als nicht-deutsch markieren
            is_german = False
            details = {
                "channel_id": channel_id,
                "error": str(e)
            }

        if is_german:
            german_channels.append(channel_id)

        if not is_german:
            foreign_channels.append(channel_id)

        all_channels.append({
            "channel_id": channel_id,
            "is_german": is_german,
            **details
        })

        print(f"[{idx}/{len(channel_ids)}] {channel_id} → {'DE' if is_german else 'NON-DE'}")

        # Output: Alle Channels mit Flag
        if idx % 10 == 0:
            print(f"Saving output to: '{output_all_channels_path}'")
            with open(output_all_channels_path, "w", encoding="utf-8") as f:
                json.dump(all_channels, f, ensure_ascii=False, indent=2)

    print(f"{counter}/{len(channel_ids)} were already classified.")
    save_json(output_all_channels_path, all_channels)


def channel_id_to_name_batched(youtube, list_of_ids):
    results_dict = {}
    # Wir verarbeiten die IDs in 50er-Schritten
    for i in range(0, len(list_of_ids), 50):
        chunk = list_of_ids[i:i + 50]
        # Die IDs müssen für die API mit Komma verbunden werden
        id_string = ",".join(chunk)

        try:
            request = youtube.channels().list(
                part="snippet",
                id=id_string,
                maxResults=50
            )
            response = request.execute()

            # Wir speichern die Ergebnisse kurz in einem Dictionary {ID: Name}
            # damit wir die Reihenfolge der ursprünglichen Liste beibehalten können
            found_channels = {
                item["id"]: item["snippet"]["title"]
                for item in response.get("items", [])
            }

            # Ergebnisse für diesen Batch loggen
            for channel_id in chunk:
                name = found_channels.get(channel_id)
                if name:
                    print(f"{channel_id} -> {name}")
                    results_dict[channel_id] = name
                else:
                    print(f"{channel_id} -> Kein Kanal gefunden")
                    results_dict[channel_id] = None

        except Exception as e:
            print(f"Fehler beim Batch {i // 50 + 1}: {e}")
            for channel_id in chunk:
                results_dict[channel_id] = None

    # Die Liste in der ursprünglichen Reihenfolge zurückgeben
    return [results_dict.get(cid) for cid in list_of_ids]












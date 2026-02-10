import json
from googleapiclient.discovery import build
from langdetect import detect, LangDetectException
from collections import Counter
from typing import Tuple
import os

# region is_german_channel
def is_german_channel(
    youtube,
    channel_id: str,
    max_videos: int = 10,
    german_threshold: float = 0.7
) -> Tuple[bool, dict]:
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
# endregion

# region classify_channels_from_json
def classify_channels_from_json(
    youtube,
    input_json_path: str,
    output_german_only_path: str,
    output_foreign_only_path: str,
    output_all_channels_path: str,
    max_videos: int = 10
):
    """
    Liest Channel IDs aus einer JSON-Datei und erzeugt zwei Output-Dateien.
    """

    with open(input_json_path, "r", encoding="utf-8") as f:
        channel_ids = json.load(f)

    german_channels = []
    foreign_channels = []
    all_channels = []

    for idx, channel_id in enumerate(channel_ids, start=1):
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

    # Output 1: Nur deutsche Channels
    with open(output_german_only_path, "w", encoding="utf-8") as f:
        json.dump(german_channels, f, ensure_ascii=False, indent=2)

    # Output 2: Nur nicht-deutsche Channels
    with open(output_foreign_only_path, "w", encoding="utf-8") as f:
        json.dump(foreign_channels, f, ensure_ascii=False, indent=2)

    # Output 3: Alle Channels mit Flag
    with open(output_all_channels_path, "w", encoding="utf-8") as f:
        json.dump(all_channels, f, ensure_ascii=False, indent=2)

# endregion

channel_classifier_inputs = ["../JSON Files/all_channel_ids_discovered.json",
    "../JSON Files/channel_ids_classified/all_channel_ids_german.json",
    "../JSON Files/channel_ids_classified/all_channel_ids_foreign.json",
    "../JSON Files/channel_ids_classified/all_channel_ids_classified.json"]

# region channel_id_to_name
def channel_id_to_name(youtube, list_of_ids):
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
# endregion


total_videos_input = "../JSON Files/videos_by_channel_total.json"
blacklist_file = "../../JSON Files/channel_ids_classified/all_channel_ids_foreign.json"
german_videos_output = "../JSON Files/videos_by_channel_total_german.json"
german_videos_output_2 = "../JSON Files/videos_by_channel_total_german_2.json"

# region filter_blacklist
def filter_blacklist(total_videos_input, blacklist_file, german_videos_output):
    #filters all videos from total videos that are not from german channels
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
# endregion

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


def choose_random_transcripts(file_path):
    import pandas as pd
    df = pd.read_csv("../../Transcript files/transcript_other_channels.csv")
    state = 40
    print(len(df))
    print(f"Random state: {state}")
    random_samples = df.sample(n=10, random_state=state)
    for index, row in random_samples.iterrows():
        print(f"Nummer: {index}")
        print(f"Video ID: {row['video_id']}")
        print(f"Transkript: {row['transcript']}")
        print("Eigene Bewertung:"
              "\nPopulismus:"
              "\nlinks-rechts:"
              "\nStance:")
        print("-" * 40)


def check_classification(file_path, key = "german_ratio", value =0.7):
    with open(file_path, "r", encoding ="utf-8") as f:
        data = json.load(f)
    total = len(data)

    matches = sum(1 for entry in data if entry.get(key) >= value)
    ratio = (matches/total)
    print(f"Gesamtanzahl: {total}")
    print(f"matches: {matches}")
    print(f"ratio: {ratio}")
    threshold_channels = []
    for channel in data:
        if 0.7 <= channel.get("german_ratio") < 1.0:
            threshold_channels.append(channel)
    print(threshold_channels)
    print(len(threshold_channels))


if __name__ == "__main__":
    api_key = "AIzaSyBUg0XIryem2_WtenRUKDA1bwLsiDzMLYE"
    youtube = build('youtube', 'v3', developerKey=api_key)

    with open("../../JSON Files/channel_ids_classified/all_channel_ids_german_3years.json", "r", encoding ="utf-8") as f:
        channel_list = json.load(f)

    channel_id_to_name(youtube, channel_list)

    # input_path = "../JSON Files/all_channel_ids_discovered.json"
    # output_german_only = "../JSON Files/channel_ids_classified/all_channel_ids_german.json"
    # output_foreign_only = "../JSON Files/channel_ids_classified/all_channel_ids_foreign.json"
    # output_all_channels = "../JSON Files/channel_ids_classified/all_channel_ids_classified.json"
    #
    # #classify_channels_from_json(youtube, input_path, output_german_only, output_foreign_only, output_all_channels)
    # classify_channels_from_json(youtube, *channel_classifier_inputs)

    #filter_blacklist(german_videos_output_2, blacklist_file, german_videos_output_2)















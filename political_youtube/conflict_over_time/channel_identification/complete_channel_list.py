"""
complete_channel_list.py

NECESSARY FILES TO RUN THE SCRIPT:
 - JSON file with video_files of upload playlists (obtained via "channel_all_vids.py")
 - Input files with already downloaded transcripts

List of functions: ["load_json", "save_json", "get_channel_metadata", "get_video_metadata", "chunk_list",
"collect_unique_ids", "is_german_channel", "classify_channels_from_json"]

Workflow:
1. Collects all channel ids from lists in subfolders of the directory. Saves all unique ids in a
new JSON file "complete_channel_list.json".
Note: This list is used in all following steps. The reference files (metadata + classifier) contain
data from all lists previously used. However, only channels from the new channel-list are used
for new output files.

2. Gets metadata for all channels and saves it as "channel_metadata.json".

3. Isolates large channels (>10,000 subscribers) and classifies large channels: german/non-german
-> "complete_channel_list_classified.json".

4. Combines metadata and classification data to generate files of german channels with different
subscriber thresholds (10k, 20k, 30k, 50k, 100k). Generates Excel file with all german channels
(including their metadata) with more than 10k subscribers.

"""

import os
import json
import pandas as pd
from googleapiclient.discovery import build
from langdetect import detect, LangDetectException
from collections import Counter
from typing import Tuple
import time


# measuring duration of the whole script
starting_time_whole_script = time.perf_counter()

#loading api keys
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("API_KEY")
api_key_c = os.getenv("API_KEY_C")

youtube = build("youtube", "v3", developerKey=api_key)

def load_json(path):
    print(f"Reading file: '{path}'")
    with open(path, "r", encoding = "utf-8") as f:
        data = json.load(f)
        return data


def save_json(path, data, name = "data"):
    print(f"Saving {name} to '{path}'")
    with open(path, "w", encoding = "utf-8") as f:
        json.dump(data, f, indent = 2, ensure_ascii=False)


def get_channel_metadata(youtube_client, input_path, output_path):
    with open(input_path, "r", encoding = "utf-8") as f:
        channel_ids = json.load(f)

    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            try:
                all_data = json.load(f)
            except json.JSONDecodeError:
                all_data = []
    else:
        all_data = []


    already_requested = {c["channel_id"] for c in all_data}
    channel_ids_filtered = [c for c in channel_ids if c not in already_requested]
    y = len(channel_ids) - len(channel_ids_filtered)

    print(f"Channel IDs: {len(channel_ids)}"
          f"\nOf which already classfied: {y}")

    print(f"Requesting metadata for {len(channel_ids_filtered)} channels...")

    for batch in chunk_list(channel_ids_filtered, 50):
        request = youtube_client.channels().list(
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

    with open(output_path, "w", encoding = "utf-8") as f:
        json.dump(all_data, f, indent = 2, ensure_ascii= False)


def get_video_metadata(youtube_client, input_path, output_path):
    """
    Takes YouTube client and list of video IDs as input and returns a dictionary with metadata for the respective
    video_files.
    """
    print("Getting video metadata...")

    print(f"\nLoading input file: {input_path}")
    with open(input_path, "r", encoding = "utf-8") as f:
        video_ids = json.load(f)

    if isinstance(video_ids[0], dict): #if a list of dicts is imported, only video ids are extracted
        video_ids = [v["video_id"] for v in video_ids]

    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            try:
                all_videos = json.load(f)
            except json.JSONDecodeError:
                all_videos = []
    else:
        all_videos = []

    already_requested = {v["video_id"] for v in all_videos}
    video_ids_filtered = [v for v in video_ids if v not in already_requested]
    y = len(video_ids) - len(video_ids_filtered)

    print(f"Total number ideo IDs: {len(video_ids)}"
          f"\nFor {y} video IDs, metadata already exists.")

    print(f"Requesting metadata for {len(video_ids_filtered)} video_files...")

    for batch in chunk_list(video_ids_filtered, 50):
        request = youtube_client.videos().list(
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
    print(f"Saving metadata file to: {output_path}")
    with open(output_path, "w", encoding = "utf-8") as f:
        json.dump(all_videos, f, indent = 2, ensure_ascii=False)


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


def collect_downloaded_transcripts(list_of_files: list[str], list_of_ids: list[str]):
    """
    Takes a list of files and a list of IDs as Input. Searches existing transcript files for transcripts
    to these IDs. Returns a df with video ID, transcript, and status for all IDs is found in another file.
    """
    print("Collecting already downloaded transcripts...")
    id_to_file = {}

    for file in list_of_files:
        if not os.path.exists(file):
            print(f"File not found: {file}")
            continue
        df = pd.read_csv(file, usecols = ["video_id"])
        for video_id in df["video_id"].dropna().unique():
            if str(video_id) not in id_to_file:
                id_to_file[str(video_id)] = file

    print(f"Found {len(id_to_file)} already downloaded transcripts in existing files.")

    file_to_ids = {}
    for video_id in list_of_ids:
        file = id_to_file.get(str(video_id))
        if file is None:
            continue
        file_to_ids.setdefault(file, set()).add(video_id)

    results = []
    for file, ids in file_to_ids.items():
        df = pd.read_csv(file, usecols = ["video_id", "transcript", "status"])
        matched = df[df["video_id"].isin(ids)].copy()
        results.append(matched)

    if not results:
        return pd.DataFrame(columns = ["video_id", "transcript", "status"])

    return pd.concat(results, ignore_index = True)


def is_german_channel(
    youtube, channel_id: str, max_videos: int = 10, german_threshold: float = 0.7) -> Tuple[bool, dict]:
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


def classify_channels_from_json(
    youtube, input_json_path: str, output_german_only_path: str, output_foreign_only_path: str,
    output_all_channels_path: str, max_videos: int = 10):
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

        # # Output 1: Nur deutsche Channels
        # with open(output_german_only_path, "w", encoding="utf-8") as f:
        #     json.dump(german_channels, f, ensure_ascii=False, indent=2)
        #
        # # Output 2: Nur nicht-deutsche Channels
        # with open(output_foreign_only_path, "w", encoding="utf-8") as f:
        #     json.dump(foreign_channels, f, ensure_ascii=False, indent=2)
        #
        # Output 3: Alle Channels mit Flag
        if idx % 10 == 0:
            print(f"Saving output to: '{output_all_channels_path}'")
            with open(output_all_channels_path, "w", encoding="utf-8") as f:
                json.dump(all_channels, f, ensure_ascii=False, indent=2)

    print(f"{counter}/{len(channel_ids)} were already classified.")
    save_json(output_all_channels_path, all_channels)

"""
1. aggregate all lists to one list
"""
print(f"\nCurrent working directory: {os.getcwd()}")

print("\nAggregating all channel IDs to a combined list:")

result = collect_unique_channel_ids("keyword", ["all_channel_ids_discovered.json",
                                                             "all_channel_ids_discovered_2.json"])
print(f"Number of unique IDs found: {len(result)}")
#print(result)

with open("all_channels/complete_channel_list.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)


"""
2. get metadata
"""
print("\n\nGetting metadata:")

get_channel_metadata(youtube, "all_channels/complete_channel_list.json","all_channels/channel_metadata.json")

print("\n")
channels = load_json("all_channels/complete_channel_list.json")
metadata =  load_json("all_channels/channel_metadata.json")

print(f"Number of channels: {len(channels)}")
#print(f"Number of channels with metadata available: {len(metadata)}")

list_metadata = [c["channel_id"] for c in metadata]
extra = [c for c in channels if c not in list_metadata]
y2 = len(channels) - len(extra)
print(f"Of which metadata available: {y2}")
if extra:
    print(f"Channels with no metadata available: {extra}")

"""
3. remove small channels and classify language
"""

print("\n\nRemoving small channels and classifying the language:")

channels = load_json("all_channels/complete_channel_list.json")
channels_set = set(channels)
channel_metadata = load_json("all_channels/channel_metadata.json")

channel_metadata = [item for item in channel_metadata if item["channel_id"] in channels_set]

print(f"All channels: {len(channel_metadata)}")

large_channels = [c["channel_id"] for c in channel_metadata if c["subscribers"] > 50000]
print(f"Large channels: {len(large_channels)} (>10,000 subscribers)")

save_json("all_channels/complete_channel_list_large.json", large_channels)

print("\n")

classify_channels_from_json(youtube, "all_channels/complete_channel_list_large.json",
                                "complete_channel_list_german.json",
                                "complete_channel_list_foreign.json",
                            "all_channels/complete_channel_list_classified.json")


"""
4. create lists of German channels with different thresholds
"""
print("\n\nCreating different lists of channels with different thresholds:")

with open("all_channels/complete_channel_list_classified.json", "r", encoding="utf-8") as f:
    classifier = json.load(f)

with open("all_channels/channel_metadata.json", "r", encoding ="utf-8")as f:
    metadata = json.load(f)

with open("all_channels/complete_channel_list.json", "r", encoding ="utf-8")as f:
    relevant_channels = set(json.load(f))

classifier = [item for item in classifier if item["channel_id"] in relevant_channels]
metadata = [item for item in metadata if item["channel_id"] in relevant_channels]

thresholds = [10000, 20000, 30000, 50000, 100000]
print(f"Total number of channels: {len(relevant_channels)}")

os.makedirs("large_german_channels", exist_ok=True)

for t in thresholds:
    large = [v["channel_id"] for v in metadata if v["subscribers"] > t]
    print(f"Channels with more than {t} subscribers: {len(large)}")

    german_channels = [c["channel_id"] for c in classifier if c["is_german"]
                       and c["channel_id"] in large]
    print(f"Of which German channels: {len(german_channels)}")

    german_channels_tk = [c for c in metadata if c["channel_id"] in german_channels]
    with open(f"large_german_channels/german_channels_{t}k.json", "w", encoding = "utf-8") as f:
        json.dump(german_channels_tk, f, indent = 2, ensure_ascii=False)

with open("large_german_channels/german_channels_10000k.json", "r", encoding = "utf-8") as f:
    data = json.load(f)

df = pd.DataFrame(data)
df = df.sort_values(by="name")

#df.to_excel("german_channels.xlsx", index = False, engine="openpyxl")


"""
5. generate a file with video_files downloaded via all_channel_vids for the respective channel list 
"""
print("\nFiltering video_files from all video_files scanned according to relevant channel list")
start_time = time.perf_counter()

all_videos_downloaded = load_json("../video_files/videos_total.json")
relevant_channels = load_json("large_german_channels/german_channels_50000k.json")

relevant_channels = {c["channel_id"] for c in relevant_channels}
print("\nKeeping only video_files from channels on the list...")
filtered_videos = [v for v in all_videos_downloaded if v["channel_id"] in relevant_channels]

os.makedirs("large_german_channels/video_files/videos", exist_ok = True
            )
save_json("large_german_channels/video_files/all_videos_50k_channels.json", filtered_videos,
          "filtered_videos")

print(f"Total number of video_files uploaded by relevant channels: {len(filtered_videos)}")
end_time = time.perf_counter()
execution_time = end_time - start_time

print(f"\nFiltering video_files took {execution_time:.2f} seconds to run.")

"""
6. identify keyword video_files
"""

import random
from collections import defaultdict
from datetime import datetime

input_file = f"large_german_channels/video_files/all_videos_50k_channels.json"

keyword_file = f"large_german_channels/video_files/all_videos_50k_channels_keywords.json"
sampled_file = f"large_german_channels/video_files/all_videos_50k_channels_sampled.json"

keywords = ["nahe osten", "naher osten", "nahen osten", "nahost", "israel", "palästina", "gaza", "hamas", "IDF", "Jerusalem", "netanjahu", "netanyahu"]

cutoff_day = "2023-10-07T00:00:00Z"
cutoff_day_dt = datetime.fromisoformat(cutoff_day.replace("Z", "+00:00"))

sample_size = 100

random.seed(42)

# load JSON
with open(input_file, "r", encoding="utf-8") as f:
    data = json.load(f)

data = [v for v in data if not v["title"].startswith("no_video_found")]

# group by channel
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

        if published < cutoff_day_dt:
            before.append(v)
        else:
            after.append(v)

    if len(before) > sample_size:
        before = random.sample(before, sample_size)

    if len(after) > sample_size:
        after = random.sample(after, sample_size)

    sampled_videos.extend(before + after)

# save files
with open(keyword_file, "w", encoding="utf-8") as f:
    json.dump(keyword_videos, f, ensure_ascii=False, indent=2)

with open(sampled_file, "w", encoding="utf-8") as f:
    json.dump(sampled_videos, f, ensure_ascii=False, indent=2)


print(f"\nKeyword video_files: {len(keyword_videos)}")
print(f"Sampled video_files: {len(sampled_videos)}")


"""
7. create a list of keyword/sampled video_files and compare this list to all downloaded transcripts
"""
print("\nGetting already downloaded transcripts...")
# !!! Specify export file to also be loaded in order not to lose any files !!!
export_file = "../../Transcript files/political_yt_transcripts_new.csv"
# create list of video_files from dict
keyword_file = f"large_german_channels/video_files/all_videos_50k_channels_keywords.json"
sampled_file = f"large_german_channels/video_files/all_videos_50k_channels_sampled.json"

keyword_vids = load_json(keyword_file)
keyword_vids = [v["video_id"] for v in keyword_vids]

sample_vids = load_json(sampled_file)
sample_vids = [v["video_id"] for v in sample_vids]

# collect downloaded transcripts
transcript_files = [
    export_file,
    "../../Transcript files/political_yt_transcripts.csv",
    "../../Transcript files/youtube_transcripts_sampledvideos.csv",
    "../../../project_transcripts/Transcript files/youtube_transkripte_2.csv"
]

if export_file in transcript_files:
    downloaded_transcripts = collect_downloaded_transcripts(transcript_files, keyword_vids)
    downloaded_transcripts.to_csv(export_file, index = False)

    print(f"{len(downloaded_transcripts)} relevant transcripts are already downloaded.")
    print("\nHead of transcript file:")
    print(downloaded_transcripts.head())
else:
    print("Export file was not loaded. No export, to ensure that no data is lost.")

"""
8. get metadata for all relevant video_files
"""

print("\n")

#keyword file as input
# metadata_keyword_vids = f"large_german_channels/video_files/metadata_all_videos_100k_channels_keywords.json"
#
# get_video_metadata(youtube, keyword_file, metadata_keyword_vids)
#
# #inspect data
# video_metadata = pd.read_json(metadata_keyword_vids)



"""
measuring time of code execution
"""

ending_time_whole_script = time.perf_counter()
execution_time_whole_script = ending_time_whole_script - starting_time_whole_script
print(f"\n\nWhole script took {execution_time_whole_script:.2f} seconds to run.")

"""
channel_all_videos.py

Modes:
  - NEW_CHANNELS  : Collect videos from channels not yet in videos_total.json,
                    then classify them for German language.
  - UPDATE        : Fetch new videos (since last known video) for already-known channels.

Switch between modes by setting MODE below.
"""

from googleapiclient.discovery import build
from collections import Counter
from langdetect import detect, LangDetectException
from typing import Tuple
import json
import os

from settings_variables import published_before_analysis, published_after_analysis
from youtube_code.config import API_KEY, RAW, CHANNEL_LISTS
from youtube_code.utils import save_json

# ─────────────────────────────────────────────
# MODE SWITCH  ←  change this line to switch
#   "NEW_CHANNELS"  |  "UPDATE"
# ─────────────────────────────────────────────
MODE = "NEW_CHANNELS"

YOUTUBE = build("youtube", "v3", developerKey=API_KEY)

# ─────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────
VIDEOS_TOTAL_FILE = RAW / "videos_total.json"
CHANNEL_INPUT     = CHANNEL_LISTS / "party_identification" / "channel_list.json"
CLASSIFIED_CHANNELS_FILE = RAW / "classified_channels_total.json"

# Language-classification settings
MAX_VIDEOS_FOR_CLASSIFICATION = 10
GERMAN_THRESHOLD = 0.7


# ─────────────────────────────────────────────
# Load existing data
# ─────────────────────────────────────────────
if os.path.exists(VIDEOS_TOTAL_FILE):
    with open(VIDEOS_TOTAL_FILE, "r", encoding="utf-8") as f:
        videos_total: list[dict] = json.load(f)
else:
    videos_total = []

# newest known publication date per channel (used by UPDATE mode)
newest_video_per_channel: dict[str, str] = {}
for v in videos_total:
    cid    = v["channel_id"]
    pub_at = v["published_at"]
    if "no_video_found" in pub_at:
        continue
    if cid not in newest_video_per_channel or pub_at > newest_video_per_channel[cid]:
        newest_video_per_channel[cid] = pub_at

with open(CHANNEL_INPUT, "r", encoding="utf-8") as f:
    channel_ids= json.load(f)

if isinstance(channel_ids[0], dict):
    channel_ids = [c["channel_id"] for c in channel_ids]

processed_channel_ids: set[str] = {v["channel_id"] for v in videos_total}


# ─────────────────────────────────────────────
# Helper: fetch uploads-playlist ID
# ─────────────────────────────────────────────
def _get_uploads_playlist_id(channel_id: str) -> str | None:
    resp = YOUTUBE.channels().list(part="contentDetails", id=channel_id).execute()
    items = resp.get("items")
    if not items:
        return None
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


# ─────────────────────────────────────────────
# Video fetching
# ─────────────────────────────────────────────
def get_channel_videos(channel_id: str, published_after: str, published_before: str) -> list[dict]:
    """
    Fetch all videos for a channel within [published_after, published_before].
    Stops pagination early once a video older than published_after is encountered.
    """
    uploads_playlist_id = _get_uploads_playlist_id(channel_id)
    if not uploads_playlist_id:
        return []

    videos: list[dict] = []
    next_page = None
    stop = False

    while not stop:
        pl_response = YOUTUBE.playlistItems().list(
            part="contentDetails,snippet",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page,
        ).execute()

        for item in pl_response.get("items", []):
            snippet        = item.get("snippet", {})
            content_details = item.get("contentDetails", {})

            video_id = content_details.get("videoId") or snippet.get("resourceId", {}).get("videoId")
            pub_date = content_details.get("videoPublishedAt") or snippet.get("publishedAt")
            title    = snippet.get("title")

            if not video_id or not pub_date:
                continue

            if pub_date < published_after:
                stop = True  # everything from here on is older – no need to page further
                break

            if pub_date <= published_before:
                videos.append({
                    "video_id":    video_id,
                    "channel_id":  channel_id,
                    "published_at": pub_date,
                    "title":       title,
                })

        next_page = pl_response.get("nextPageToken")
        if not next_page:
            break

    return videos


def get_new_channel_videos(channel_id: str, published_after: str, published_before: str,
    last_known_newest: str | None,) -> list[dict]:
    """
    Fetch only videos newer than last_known_newest for an already-known channel.
    Stops as soon as a video at or before last_known_newest is encountered.
    """
    uploads_playlist_id = _get_uploads_playlist_id(channel_id)
    if not uploads_playlist_id:
        return []

    videos: list[dict] = []
    next_page = None

    while True:
        pl_response = YOUTUBE.playlistItems().list(
            part="contentDetails,snippet",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page,
        ).execute()

        for item in pl_response.get("items", []):
            snippet         = item.get("snippet", {})
            content_details = item.get("contentDetails", {})

            video_id = content_details.get("videoId") or snippet.get("resourceId", {}).get("videoId")
            pub_date = content_details.get("videoPublishedAt") or snippet.get("publishedAt")

            if not video_id or not pub_date:
                continue

            # Already seen this video (or older) – we're done
            if last_known_newest and pub_date <= last_known_newest:
                return videos

            if published_after <= pub_date <= published_before:
                videos.append({
                    "video_id":    video_id,
                    "channel_id":  channel_id,
                    "published_at": pub_date,
                    "title":       snippet.get("title"),
                })

            if pub_date < published_after:
                return videos

        next_page = pl_response.get("nextPageToken")
        if not next_page:
            break

    return videos


# ─────────────────────────────────────────────
# Language classification
# ─────────────────────────────────────────────
def is_german_channel(channel_id: str, max_videos: int = MAX_VIDEOS_FOR_CLASSIFICATION,
    german_threshold: float = GERMAN_THRESHOLD,) -> Tuple[bool, dict]:
    """
    Determines whether a YouTube channel is predominantly German-language.

    Strategy (in order):
    1. Channel metadata: defaultLanguage == "de"  →  True immediately
    2. Detect language of the last `max_videos` video titles + descriptions
    3. Soft signal: country == "DE" and german_ratio >= 0.5
    """
    details: dict = {
        "channel_id":      channel_id,
        "defaultLanguage": None,
        "country":         None,
        "german_ratio":    0.0,
    }

    channel_response = YOUTUBE.channels().list(
        part="snippet,contentDetails", id=channel_id
    ).execute()

    if not channel_response.get("items"):
        return False, details

    snippet = channel_response["items"][0]["snippet"]
    details["defaultLanguage"] = snippet.get("defaultLanguage")
    details["country"]         = snippet.get("country")

    # Fast path
    if details["defaultLanguage"] == "de":
        details["german_ratio"] = 1.0
        return True, details

    # Fetch recent video IDs from uploads playlist
    uploads_playlist_id = (
        channel_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    )
    playlist_items = YOUTUBE.playlistItems().list(
        part="snippet",
        playlistId=uploads_playlist_id,
        maxResults=max_videos,
    ).execute()

    video_ids = [
        item["snippet"]["resourceId"]["videoId"]
        for item in playlist_items.get("items", [])
        if item.get("snippet", {}).get("resourceId", {}).get("videoId")
    ]

    if not video_ids:
        return False, details

    # Batch-fetch video snippets and detect language
    videos_response = YOUTUBE.videos().list(
        part="snippet", id=",".join(video_ids)
    ).execute()

    detected_languages: list[str] = []
    for video in videos_response.get("items", []):
        vs = video.get("snippet", {})
        text = f"{vs.get('title', '')} {vs.get('description', '')}"
        try:
            detected_languages.append(detect(text))
        except LangDetectException:
            continue

    if not detected_languages:
        return False, details

    counter      = Counter(detected_languages)
    german_ratio = counter.get("de", 0) / len(detected_languages)
    details["german_ratio"] = round(german_ratio, 2)

    is_german = german_ratio >= german_threshold
    # Soft signal: country-level hint
    if not is_german and details["country"] == "DE" and german_ratio >= 0.5:
        is_german = True

    return is_german, details


def classify_new_channels(new_channel_ids: list[str]) -> None:
    """
    Classifies a list of channel IDs and appends results to CLASSIFIED_CHANNELS_FILE.
    Skips channels that are already present in the file.
    Saves incrementally every 10 channels.
    """
    if not new_channel_ids:
        print("No new channels to classify.")
        return

    # Load existing classifications
    if os.path.exists(CLASSIFIED_CHANNELS_FILE):
        with open(CLASSIFIED_CHANNELS_FILE, "r", encoding="utf-8") as f:
            try:
                all_classified: list[dict] = json.load(f)
            except json.JSONDecodeError:
                all_classified = []
    else:
        all_classified = []

    already_classified: set[str] = {c["channel_id"] for c in all_classified}

    to_classify = [cid for cid in new_channel_ids if cid not in already_classified]
    print(f"Channels to classify: {len(to_classify)} "
          f"({len(new_channel_ids) - len(to_classify)} already classified, skipped)")

    for idx, cid in enumerate(to_classify, start=1):
        try:
            is_german, details = is_german_channel(cid)
        except Exception as e:
            is_german = False
            details   = {"channel_id": cid, "error": str(e)}

        all_classified.append({"channel_id": cid, "is_german": is_german, **details})
        print(f"  [{idx}/{len(to_classify)}] {cid} → {'DE' if is_german else 'NON-DE'}")

        if idx % 10 == 0:
            save_json(CLASSIFIED_CHANNELS_FILE, all_classified)
            print(f"  Intermediate status saved ({idx} classified)")

    save_json(CLASSIFIED_CHANNELS_FILE, all_classified)
    german_count = sum(1 for c in all_classified if c.get("is_german"))
    print(f"Classification done. {german_count}/{len(all_classified)} German channels in total.")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
if __name__ == "__main__":

    new_videos: list[dict] = []

    if MODE == "NEW_CHANNELS":
        # ── Neue Kanäle abfragen ────────────────
        new_channel_ids = [cid for cid in channel_ids if cid not in processed_channel_ids]
        print(f"Already processed channels : {len(processed_channel_ids)}")
        print(f"Channels in input          : {len(channel_ids)}")
        print(f"Of which new               : {len(new_channel_ids)}")

        # ── Language-classification of new channels ──
        print("\nStarting language classification of new channels...")
        classify_new_channels(new_channel_ids)

        with open(CLASSIFIED_CHANNELS_FILE, "r", encoding = "utf-8") as f:
            classified = json.load(f)

        german_new_channel_ids = {
            c["channel_id"] for c in classified
            if c["channel_id"] in set(new_channel_ids) and c.get("is_german")
        }
        print(f"Of which German: {len(german_new_channel_ids)}")

        for cid in german_new_channel_ids:
            try:
                print(f"New channel ID: {cid}")
                channel_videos = get_channel_videos(cid, published_after_analysis, published_before_analysis)
                print(f"  Videos found: {len(channel_videos)}")
                if channel_videos:
                    new_videos.extend(channel_videos)
                else:
                    new_videos.append({
                        "video_id":    f"no_video_found_{cid}",
                        "channel_id":  cid,
                        "published_at": f"no_video_found_{cid}",
                        "title":       f"no_video_found_{cid}",
                    })

            except Exception as e:
                if "quotaExceeded" in str(e):
                    print(f"  API-Quota hit, abort.")
                    break
                print(f"  Error at {cid}: {e}")
                continue

    elif MODE == "UPDATE":
        # ── Bestehende Kanäle auf neue Videos prüfen ──
        print(f"Update-mode: Search {len(channel_ids)} channels for new videos...")
        for cid in channel_ids:
            last_known = newest_video_per_channel.get(cid)
            print(f"Channel {cid} – last known video: {last_known or 'unknown'}")
            try:
                found = get_new_channel_videos(
                    cid,
                    published_after_analysis,
                    published_before_analysis,
                    last_known,
                )
                if found:
                    print(f"  → {len(found)} new videos found")
                    new_videos.extend(found)
            except Exception as e:
                print(f"  Error at {cid}: {e}")

    else:
        raise ValueError(f"Unknown MODE: '{MODE}'. Permitted: 'NEW_CHANNELS' oder 'UPDATE'.")

    # ─────────────────────────────────────────────
    # Deduplizierung & Speichern
    # ─────────────────────────────────────────────
    all_videos   = videos_total + new_videos
    unique_dict  = {v["video_id"]: v for v in all_videos}  # last-write-wins
    videos_total = list(unique_dict.values())

    save_json(VIDEOS_TOTAL_FILE, videos_total)

    print("\n── Process complete ──")
    print(f"Total videos        : {len(videos_total)}")
    print(f"Newly added         : {len(new_videos)}")
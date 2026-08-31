"""
channel_all_videos.py

Modes:
  - NEW_CHANNELS        : Collect videos from channels not yet in videos_total.json,
                          then classify them for German language.
  - UPDATE              : Fetch new videos (since last known video) for already-known channels.
  - TARGETED_SEARCH     : Full-window video search via playlistItems.list (uploads playlist) for
                          a small, explicit list of already-known channels (e.g. channels with a
                          gap in a specific time window). Unlike UPDATE, this pages through the
                          entire window regardless of the newest known video, so it also finds
                          older/missing videos. No language classification, channels are known.

                          CAVEAT: playlistItems.list on the uploads playlist silently stops after
                          roughly 20,000 items (nextPageToken becomes empty even though more
                          videos exist) - a known YouTube Data API limitation for very large
                          playlists. For channels with >~15,000 total videos, this mode can miss
                          a window that lies further back than item #20,000, and will silently
                          report 0 results instead of erroring. Use TARGETED_SEARCH_API for those.
  - TARGETED_SEARCH_YTDLP : For the same very large channels, neither playlistItems.list nor
                          search().list reaches an old window reliably: playlistItems silently
                          stops around item #20,000 (see above), and search().list's index turned
                          out to only cover a tiny recent slice for these channels (e.g. 155 of
                          tagesschau's 35,889 videos, 0 of Habibiflo's 36,912 - verified directly
                          via pageInfo.totalResults) - so both official Data API listing methods
                          are structural dead ends here, not a quota/timing problem.
                          This mode instead enumerates video IDs via yt-dlp's flat-playlist
                          extraction of the channel's public /videos tab, which reaches much
                          further back (verified: found tagesschau videos from Oct 2021 that
                          neither other method could reach). yt-dlp's own upload-date guess in
                          flat mode is unreliable, so it is not trusted - the enumerated IDs are
                          instead looked up in batches of 50 via videos().list (1 quota unit per
                          batch) to get the real, authoritative publishedAt, which is what the
                          window filter actually uses.

Switch between modes by setting MODE below.

Run pattern: this script is meant to be executed directly (`python channel_all_videos.py`),
never imported. That is why `from settings_variables import ...` below works as a bare
sibling import (Python puts the script's own directory on sys.path[0]), while
`from youtube_code... import ...` still resolves normally because that package is
importable independent of cwd.
"""

import csv
import sys

# Windows-Konsolen laufen oft im Legacy-Codepage (cp1252) statt UTF-8. Ohne
# das hier crasht der Script-Erfolg am Schluss noch an einem simplen print()
# mit Sonderzeichen (z.B. "──"), obwohl die eigentliche Arbeit (API-Abfragen,
# Speichern) laengst durch ist. errors="replace" statt "strict", damit ein
# unerwartetes Zeichen nie wieder das ganze Skript zum Absturz bringt.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from googleapiclient.discovery import build
from collections import Counter
from langdetect import detect, LangDetectException
from typing import Tuple
import json
import os

import yt_dlp

from settings_variables import published_before_analysis, published_after_analysis
from youtube_code.config import API_KEY, API_KEY_C, RAW, CHANNEL_LISTS, OUTPUTS
from youtube_code.utils import save_json
from youtube_code.utils.video_registry import upsert_videos as _registry_upsert

# ─────────────────────────────────────────────
# MODE SWITCH  ←  change this line to switch
#   "NEW_CHANNELS"  |  "UPDATE"  |  "TARGETED_SEARCH"  |  "TARGETED_SEARCH_YTDLP"
# ─────────────────────────────────────────────
MODE = "TARGETED_SEARCH_YTDLP"

YOUTUBE = build("youtube", "v3", developerKey=API_KEY)

# ─────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────
VIDEOS_TOTAL_FILE = RAW / "sample_50k_channels_russia_ukraine.json"
CHANNEL_INPUT     = CHANNEL_LISTS / "all_identification" / "german_channels_50k.json"
CLASSIFIED_CHANNELS_FILE = RAW / "classified_channels_total.json"

# ── TARGETED_SEARCH: Konfiguration ──
# Kanalliste: CSV mit "channel_id"-Spalte oder JSON (Liste von IDs oder von
# Dicts mit "channel_id"). Standard: die 38 Kanaele ohne Baseline-Video aus
# outputs/segment_analysis/baseline_still_missing_channels.csv.
TARGETED_CHANNEL_INPUT = OUTPUTS / "segment_analysis" / "baseline_still_missing_channels.csv"

# Zeitfenster fuer die gezielte Suche: Monat -12 bis direkt vor Kriegsbeginn
# (2022-02-24), nicht nur bis Monat -3 wie das engere Baseline-Fenster in
# check_baseline_coverage.py.
TARGETED_PUBLISHED_AFTER  = "2021-02-24T00:00:00Z"
TARGETED_PUBLISHED_BEFORE = "2022-02-23T23:59:59Z"

# ── TARGETED_SEARCH_YTDLP: Konfiguration ──
# Kanalliste im selben Format wie TARGETED_CHANNEL_INPUT. Standard: die 5
# sehr grossen Kanaele (>~15.000 Videos insgesamt), bei denen weder
# TARGETED_SEARCH (playlistItems-20k-Grenze) noch eine search().list-Variante
# (winziger, nicht repraesentativer Suchindex) das Zeitfenster erreichen.
TARGETED_SEARCH_YTDLP_CHANNEL_INPUT = OUTPUTS / "segment_analysis" / "baseline_unreliable_large_channels.csv"
# Nutzt dasselbe Zeitfenster wie TARGETED_SEARCH (TARGETED_PUBLISHED_AFTER/_BEFORE).

# videos().list erlaubt max. 50 IDs pro Aufruf.
YTDLP_LOOKUP_BATCH_SIZE = 50

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


def list_channel_video_ids_ytdlp(channel_id: str) -> list[str]:
    """
    Enumerate all video IDs yt-dlp can reach on a channel's public /videos tab via flat
    (metadata-only) playlist extraction - no per-video downloads, no per-video requests.

    This reaches much further back into a channel's history than playlistItems.list does
    for very large channels (verified: found videos from over a year before playlistItems
    stopped paginating for the same channel). The upload-date guess yt-dlp can attach in
    flat mode is unreliable and deliberately NOT used here - only the IDs are taken; the
    real publishedAt is looked up afterwards via the Data API.
    """
    url = f"https://www.youtube.com/channel/{channel_id}/videos"
    ydl_opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    entries = (info or {}).get("entries") or []
    return [e["id"] for e in entries if e and e.get("id")]


def get_channel_videos_via_ytdlp(channel_id: str, published_after: str, published_before: str) -> list[dict]:
    """
    Fetch all videos for a channel within [published_after, published_before] by first
    enumerating video IDs via yt-dlp (list_channel_video_ids_ytdlp), then looking up their
    real metadata in batches of YTDLP_LOOKUP_BATCH_SIZE via videos().list - 1 quota unit per
    batch, regardless of batch size. Videos outside the window, or no longer retrievable
    (deleted/private), are silently dropped.

    Use this for very large channels where TARGETED_SEARCH (playlistItems.list, caps around
    item #20,000) and a search().list-based approach (sparse, non-exhaustive search index -
    verified to cover as little as 0-300 of tens of thousands of videos for these channels)
    both fail to reach the window.
    """
    video_ids = list_channel_video_ids_ytdlp(channel_id)
    if not video_ids:
        return []

    videos: list[dict] = []
    for i in range(0, len(video_ids), YTDLP_LOOKUP_BATCH_SIZE):
        batch = video_ids[i:i + YTDLP_LOOKUP_BATCH_SIZE]
        response = YOUTUBE.videos().list(part="snippet", id=",".join(batch)).execute()

        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            pub_date = snippet.get("publishedAt")
            if not pub_date:
                continue
            if not (published_after <= pub_date <= published_before):
                continue

            videos.append({
                "video_id":    item.get("id"),
                "channel_id":  snippet.get("channelId", channel_id),
                "published_at": pub_date,
                "title":       snippet.get("title"),
            })

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
# TARGETED_SEARCH: Kanalliste laden
# ─────────────────────────────────────────────
def load_targeted_channel_ids(path) -> list[str]:
    """
    Laedt eine Kanal-ID-Liste fuer TARGETED_SEARCH.

    Akzeptiert:
      - .csv mit einer "channel_id"-Spalte (z.B. baseline_still_missing_channels.csv)
      - .json als Liste von IDs oder Liste von Dicts mit "channel_id"
    """
    suffix = str(path).lower().rsplit(".", 1)[-1]

    if suffix == "csv":
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if "channel_id" not in (reader.fieldnames or []):
                raise ValueError(f"{path} hat keine 'channel_id'-Spalte.")
            ids = [row["channel_id"].strip() for row in reader if row.get("channel_id")]
    elif suffix == "json":
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if raw and isinstance(raw[0], dict):
            ids = [r["channel_id"] for r in raw]
        else:
            ids = list(raw)
    else:
        raise ValueError(f"Nicht unterstuetztes Format fuer TARGETED_CHANNEL_INPUT: {path}")

    # Dubletten entfernen, Reihenfolge beibehalten
    seen: set[str] = set()
    deduped = []
    for cid in ids:
        if cid not in seen:
            seen.add(cid)
            deduped.append(cid)
    return deduped


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
        print(f"German channels to check: {len(german_new_channel_ids)}")

        channel_counter = 1
        for cid in german_new_channel_ids:
            try:
                print(f"New channel ID: {cid} ({channel_counter}/{len(german_new_channel_ids)})")
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

            channel_counter += 1

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

    elif MODE == "TARGETED_SEARCH":
        # ── Gezielte Voll-Fenster-Suche fuer eine kleine, bereits bekannte
        #    Kanalliste (z.B. Baseline-Luecken). Im Unterschied zu UPDATE wird
        #    das gesamte Fenster durchpaginiert, unabhaengig vom bisher
        #    bekannten neuesten Video – findet also auch aeltere/fehlende
        #    Videos, keine reine Delta-Abfrage. Keine Sprachklassifikation,
        #    die Kanaele sind bereits bekannt.
        targeted_channel_ids = load_targeted_channel_ids(TARGETED_CHANNEL_INPUT)
        print(f"Targeted-Search-Modus: {len(targeted_channel_ids)} Kanaele aus "
              f"{TARGETED_CHANNEL_INPUT}")
        print(f"Zeitfenster: {TARGETED_PUBLISHED_AFTER} bis {TARGETED_PUBLISHED_BEFORE}")

        channel_counter = 1
        for cid in targeted_channel_ids:
            try:
                print(f"Kanal: {cid} ({channel_counter}/{len(targeted_channel_ids)})")
                channel_videos = get_channel_videos(
                    cid, TARGETED_PUBLISHED_AFTER, TARGETED_PUBLISHED_BEFORE
                )
                print(f"  Videos gefunden: {len(channel_videos)}")
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
                    print(f"  API-Quota erreicht, Abbruch.")
                    break
                print(f"  Fehler bei {cid}: {e}")
                continue

            channel_counter += 1

    elif MODE == "TARGETED_SEARCH_YTDLP":
        # ── Gezielte Suche ueber yt-dlp-Enumeration + videos().list-Verifikation,
        #    fuer sehr grosse Kanaele, bei denen weder TARGETED_SEARCH
        #    (playlistItems-20k-Grenze) noch search().list (winziger,
        #    unrepraesentativer Suchindex) das Zeitfenster erreichen (siehe
        #    Docstring oben). Gleiches Zeitfenster wie TARGETED_SEARCH.
        targeted_channel_ids = load_targeted_channel_ids(TARGETED_SEARCH_YTDLP_CHANNEL_INPUT)
        print(f"Targeted-Search-yt-dlp-Modus: {len(targeted_channel_ids)} Kanaele aus "
              f"{TARGETED_SEARCH_YTDLP_CHANNEL_INPUT}")
        print(f"Zeitfenster: {TARGETED_PUBLISHED_AFTER} bis {TARGETED_PUBLISHED_BEFORE}")

        channel_counter = 1
        for cid in targeted_channel_ids:
            try:
                print(f"Kanal: {cid} ({channel_counter}/{len(targeted_channel_ids)})")
                channel_videos = get_channel_videos_via_ytdlp(
                    cid, TARGETED_PUBLISHED_AFTER, TARGETED_PUBLISHED_BEFORE
                )
                print(f"  Videos gefunden: {len(channel_videos)}")
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
                    print(f"  API-Quota erreicht, Abbruch.")
                    break
                print(f"  Fehler bei {cid}: {e}")
                continue

            channel_counter += 1

    else:
        raise ValueError(
            f"Unknown MODE: '{MODE}'. Permitted: 'NEW_CHANNELS', 'UPDATE', 'TARGETED_SEARCH' "
            "oder 'TARGETED_SEARCH_YTDLP'."
        )

    # ─────────────────────────────────────────────
    # Deduplizierung & Speichern
    # ─────────────────────────────────────────────
    all_videos   = videos_total + new_videos
    unique_dict  = {v["video_id"]: v for v in all_videos}  # last-write-wins
    videos_total = list(unique_dict.values())

    save_json(VIDEOS_TOTAL_FILE, videos_total)

    # Zentrale Video-Registry mitfuehren (data/raw/video_registry.sqlite),
    # unabhaengig vom Modus - siehe youtube_code.utils.video_registry.
    n_registry = _registry_upsert(new_videos)
    print(f"In zentrale Registry geschrieben: {n_registry}")

    print("\n── Process complete ──")
    print(f"Total videos        : {len(videos_total)}")
    print(f"Newly added         : {len(new_videos)}")
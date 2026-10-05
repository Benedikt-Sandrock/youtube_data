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
                          window filter actually uses. IDs already in the registry are not
                          looked up again, and the lookup stops once the /videos tab (newest
                          first) has passed the window start - so the quota cost scales with
                          the number of NEW in-window videos, not with the channel's total.
                          Quota-safe: results are saved after every channel, a quota error
                          keeps the partial result of the current channel, and a status file
                          next to the channel list (<list>_status.csv) lets a follow-up run
                          with the same list skip channels already marked "komplett".

Switch between modes by setting MODE below.

Output: writes to the central registry (data/store/video_registry.sqlite)
by default. The separate JSON snapshot (VIDEOS_TOTAL_FILE) is only written
when SAVE_JSON_SNAPSHOT is set to True below. Likewise, "already known"
channels/videos (NEW_CHANNELS/UPDATE modes) are looked up directly in the
registry, not read back from that JSON file.

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
from youtube_code.config import API_KEY, API_KEY_C, RAW, CHANNEL_LISTS, OUTPUTS, ADHOC_OUTPUT
from youtube_code.utils import save_json
from youtube_code.store import video_registry
from youtube_code.store.video_registry import upsert_videos as _registry_upsert

# ─────────────────────────────────────────────
# MODE SWITCH  ←  change this line to switch
#   "NEW_CHANNELS"  |  "UPDATE"  |  "TARGETED_SEARCH"  |  "TARGETED_SEARCH_YTDLP"
# ─────────────────────────────────────────────
MODE = "TARGETED_SEARCH_YTDLP"

# Ob zusaetzlich zur zentralen Registry (data/store/video_registry.sqlite,
# immer geschrieben) noch eine JSON-Datei (VIDEOS_TOTAL_FILE) gepflegt wird.
# Standardmaessig aus: die Registry ist seit der Restrukturierung die
# massgebliche, laufend aktuelle Quelle - auch NEW_CHANNELS/UPDATE erkennen
# bereits bekannte Kanaele/Videos direkt aus der Registry (siehe
# video_registry.known_channel_ids_with_videos()/newest_video_per_channel()),
# nicht mehr aus dieser Datei. Die JSON-Datei ist nur noch ein optionales
# Nebenprodukt, z.B. wenn ein anderes Skript sie gezielt als Input braucht.
SAVE_JSON_SNAPSHOT = False

YOUTUBE = build("youtube", "v3", developerKey=API_KEY_C)

# ─────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────
VIDEOS_TOTAL_FILE = RAW / "sample_50k_channels_russia_ukraine.json"
# UPDATE-Lauf 2026-09: die 292 Kanaele des Frage-1-Stufe-1-Samples (>= 5
# Kriegsvideos, siehe frage1_stichprobe.py/frage1_stichprobe_kanalstatus.csv),
# neu abgerufen ueber scripts/adhoc/output/frage1_stufe1_channel_ids_292.json
# (Ad-hoc-Ableitung, siehe .claude/CLAUDE.md). Vorheriger Wert (alle
# identifizierten deutschen Kanaele) auskommentiert stehen gelassen.
# CHANNEL_INPUT     = CHANNEL_LISTS / "all_identification" / "german_channels_50k.json"
CHANNEL_INPUT     = ADHOC_OUTPUT / "frage1_stufe1_channel_ids_292.json"
CLASSIFIED_CHANNELS_FILE = RAW / "classified_channels_total.json"

# ── TARGETED_SEARCH: Konfiguration ──
# Kanalliste: CSV mit "channel_id"-Spalte oder JSON (Liste von IDs oder von
# Dicts mit "channel_id"). Standard: die 38 Kanaele ohne Baseline-Video aus
# outputs/segment_analysis/baseline_still_missing_channels.csv.
TARGETED_CHANNEL_INPUT = OUTPUTS / "segment_analysis" / "whitelist_ab_150.csv"

# Zeitfenster fuer die gezielte Suche. Aktuell 2021-01-01 bis Ende 2026Q2 =
# der volle Beobachtungszeitraum des Quartals-Luecken-Screenings
# (scripts/adhoc/videos_pro_quartal_whitelist.py), dessen Luecken bis in
# 2021Q1 reichen. Frueherer Wert fuer die Baseline-Nachsuche: "2021-02-24T00:00:00Z"
# (Monat -12 vor Kriegsbeginn).
TARGETED_PUBLISHED_AFTER  = "2021-01-01T00:00:00Z"
TARGETED_PUBLISHED_BEFORE = "2026-06-30T23:59:59Z"

# ── TARGETED_SEARCH_YTDLP: Konfiguration ──
# Kanalliste im selben Format wie TARGETED_CHANNEL_INPUT. Standard: die 5
# sehr grossen Kanaele (>~15.000 Videos insgesamt), bei denen weder
# TARGETED_SEARCH (playlistItems-20k-Grenze) noch eine search().list-Variante
# (winziger, nicht repraesentativer Suchindex) das Zeitfenster erreichen.

# Aktuell: Nachscraping-Liste aus dem Quartals-Luecken-Screening
# (scripts/adhoc/export_nachscraping_ytdlp_liste.py). Erledigt: Testlauf
# WELT + OE24 (nachscraping_ytdlp_test.csv) und Teil 1 (12 Kanaele, +16.695
# Videos). Jetzt Teil 2 (30 Kanaele mit >= 100 geschaetzt fehlenden Videos).
# Pruefung per scripts/adhoc/vergleich_nachscraping.py vorher/nachher.
TARGETED_SEARCH_YTDLP_CHANNEL_INPUT = (
    OUTPUTS / "segment_analysis" / "datenluecken_quartale" / "nachscraping_ytdlp_kanaele_teil2.csv"
)
# TARGETED_SEARCH_YTDLP_CHANNEL_INPUT = "missing_channels.csv"
# TARGETED_SEARCH_YTDLP_CHANNEL_INPUT = OUTPUTS / "segment_analysis" / "baseline_unreliable_large_channels.csv"
# Nutzt dasselbe Zeitfenster wie TARGETED_SEARCH (TARGETED_PUBLISHED_AFTER/_BEFORE).

# Statusdatei neben der Kanalliste (<liste>_status.csv): eine Zeile pro
# bearbeitetem Kanal; Kanaele mit Status "komplett" (fuer dasselbe
# Zeitfenster) werden in einem Folgelauf uebersprungen. Zum kompletten
# Neu-Durchlauf die Datei loeschen.
TARGETED_SEARCH_YTDLP_STATUS_FILE = str(TARGETED_SEARCH_YTDLP_CHANNEL_INPUT).rsplit(".", 1)[0] + "_status.csv"

# videos().list erlaubt max. 50 IDs pro Aufruf.
YTDLP_LOOKUP_BATCH_SIZE = 50
# Abbruch der Nachschlage-Schleife, sobald so viele aufeinanderfolgende
# 50er-Batches komplett vor TARGETED_PUBLISHED_AFTER liegen (/videos-Tab ist
# neueste zuerst sortiert) - 2 statt 1 als Puffer gegen einzelne Ausreisser.
YTDLP_EARLY_STOP_BATCHES = 2

# Language-classification settings
MAX_VIDEOS_FOR_CLASSIFICATION = 10
GERMAN_THRESHOLD = 0.7


# ─────────────────────────────────────────────
# Load existing data
# ─────────────────────────────────────────────
# Bereits bekannte Kanaele bzw. deren juengstes bekanntes Video kommen aus
# der zentralen Registry, nicht mehr aus VIDEOS_TOTAL_FILE - siehe
# video_registry.known_channel_ids_with_videos()/newest_video_per_channel()
# fuer die jeweilige Einschraenkung (u.a. Kanaele mit 0 Treffern gelten
# nicht als "bekannt").
processed_channel_ids: set[str] = video_registry.known_channel_ids_with_videos()
newest_video_per_channel: dict[str, str] = video_registry.newest_video_per_channel()

# videos_total wird nur noch fuer den optionalen JSON-Snapshot gebraucht
# (SAVE_JSON_SNAPSHOT=True) - eine vorhandene Datei wird dafuer geladen,
# damit beim Schreiben nichts verloren geht; sonst bleibt sie leer.
if SAVE_JSON_SNAPSHOT and os.path.exists(VIDEOS_TOTAL_FILE):
    with open(VIDEOS_TOTAL_FILE, "r", encoding="utf-8") as f:
        videos_total: list[dict] = json.load(f)
else:
    videos_total = []

with open(CHANNEL_INPUT, "r", encoding="utf-8") as f:
    channel_ids= json.load(f)

if isinstance(channel_ids[0], dict):
    channel_ids = [c["channel_id"] for c in channel_ids]


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


class YtdlpQuotaExceeded(Exception):
    """Quota-Abbruch mitten in get_channel_videos_via_ytdlp - traegt das bis
    dahin gesammelte Teilergebnis (videos) und die Zahl der bereits
    ausgefuehrten videos().list-Aufrufe (n_lookup), damit nichts verloren geht."""

    def __init__(self, videos: list[dict], n_lookup: int, message: str):
        super().__init__(message)
        self.videos = videos
        self.n_lookup = n_lookup


def _is_quota_error(e: Exception) -> bool:
    return "quota" in str(e).lower()


def get_channel_videos_via_ytdlp(channel_id: str, published_after: str,
                                 published_before: str) -> tuple[list[dict], int]:
    """
    Fetch all videos for a channel within [published_after, published_before] that are NOT
    yet in the registry, by first enumerating video IDs via yt-dlp
    (list_channel_video_ids_ytdlp), then looking up the real publishedAt of the unknown IDs
    in batches of YTDLP_LOOKUP_BATCH_SIZE via videos().list - 1 quota unit per call,
    regardless of batch size. Videos outside the window, or no longer retrievable
    (deleted/private), are silently dropped.

    Quota savings (both do not change which in-window videos end up in the registry):
      - IDs already known in the registry are not looked up again (their published_at is
        taken from the registry) and not returned - the return value is only NEW videos.
      - The /videos tab lists newest first. Once YTDLP_EARLY_STOP_BATCHES consecutive
        batches lie entirely before published_after, the rest (older) is skipped instead of
        looking up the channel's entire history.

    On a quota error, raises YtdlpQuotaExceeded carrying the partial result collected so far.
    Returns (new_videos, number_of_videos().list_calls).

    Use this for very large channels where TARGETED_SEARCH (playlistItems.list, caps around
    item #20,000) and a search().list-based approach (sparse, non-exhaustive search index -
    verified to cover as little as 0-300 of tens of thousands of videos for these channels)
    both fail to reach the window.
    """
    video_ids = list_channel_video_ids_ytdlp(channel_id)
    if not video_ids:
        return [], 0

    bekannt_df = video_registry.get_video_rows_for_channels([channel_id])
    bekannt = {
        vid: pub for vid, pub in zip(bekannt_df["video_id"], bekannt_df["published_at"])
        if isinstance(pub, str) and pub[:1].isdigit()
    }
    print(f"  yt-dlp: {len(video_ids)} IDs, davon {sum(v in bekannt for v in video_ids)} bereits in Registry")

    videos: list[dict] = []
    n_lookup = 0
    alte_batches = 0
    for i in range(0, len(video_ids), YTDLP_LOOKUP_BATCH_SIZE):
        batch = video_ids[i:i + YTDLP_LOOKUP_BATCH_SIZE]
        daten = [bekannt[v] for v in batch if v in bekannt]
        unbekannt = [v for v in batch if v not in bekannt]

        if unbekannt:
            try:
                response = YOUTUBE.videos().list(part="snippet", id=",".join(unbekannt)).execute()
            except Exception as e:
                if _is_quota_error(e):
                    raise YtdlpQuotaExceeded(videos, n_lookup, str(e)) from e
                raise
            n_lookup += 1

            for item in response.get("items", []):
                snippet = item.get("snippet", {})
                pub_date = snippet.get("publishedAt")
                if not pub_date:
                    continue
                daten.append(pub_date)
                if not (published_after <= pub_date <= published_before):
                    continue

                videos.append({
                    "video_id":    item.get("id"),
                    "channel_id":  snippet.get("channelId", channel_id),
                    "published_at": pub_date,
                    "title":       snippet.get("title"),
                })

        if daten and max(daten) < published_after:
            alte_batches += 1
            if alte_batches >= YTDLP_EARLY_STOP_BATCHES:
                print(f"  Fenster-Anfang erreicht nach {i + len(batch)} von {len(video_ids)} IDs -> Stopp")
                break
        else:
            alte_batches = 0

    return videos, n_lookup


# ─────────────────────────────────────────────
# TARGETED_SEARCH_YTDLP: Statusdatei (Fortsetzen nach Quota-Abbruch)
# ─────────────────────────────────────────────
_YTDLP_STATUS_FIELDS = ["zeitpunkt", "channel_id", "status", "n_neue_videos", "aeltestes_neues_video",
                        "n_videos_list_aufrufe", "fenster_von", "fenster_bis", "detail"]


def append_ytdlp_status(path, channel_id: str, status: str, videos: list[dict],
                        n_lookup: int, detail: str = "") -> None:
    """Haengt eine Zeile pro bearbeitetem Kanal an die Statusdatei an
    (status: komplett | teilweise_quota | fehler)."""
    from datetime import datetime

    neu_anlegen = not os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_YTDLP_STATUS_FIELDS)
        if neu_anlegen:
            writer.writeheader()
        writer.writerow({
            "zeitpunkt": datetime.now().isoformat(timespec="seconds"),
            "channel_id": channel_id,
            "status": status,
            "n_neue_videos": len(videos),
            "aeltestes_neues_video": min((v["published_at"] for v in videos), default=""),
            "n_videos_list_aufrufe": n_lookup,
            "fenster_von": TARGETED_PUBLISHED_AFTER,
            "fenster_bis": TARGETED_PUBLISHED_BEFORE,
            "detail": detail,
        })


def load_ytdlp_completed_channels(path, published_after: str, published_before: str) -> set[str]:
    """Kanaele, die laut Statusdatei fuer GENAU dieses Zeitfenster schon
    komplett durchlaufen sind (ein spaeterer Eintrag ueberschreibt einen
    frueheren)."""
    if not os.path.exists(path):
        return set()
    letzter: dict[str, str] = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["fenster_von"] == published_after and row["fenster_bis"] == published_before:
                letzter[row["channel_id"]] = row["status"]
    return {cid for cid, s in letzter.items() if s == "komplett"}


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

        classified_entry = {"channel_id": cid, "is_german": is_german, **details}
        all_classified.append(classified_entry)
        # Zentrale Registry mitfuehren (data/store/video_registry.sqlite,
        # Tabelle language_classification) - einzeln pro Kanal, kleine
        # Batches je Lauf machen das unproblematisch.
        video_registry.upsert_language_classification([classified_entry])
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
        #    Robust gegen Quota-Abbruch: Speichern nach JEDEM Kanal, Teilergebnis
        #    des laufenden Kanals bleibt erhalten, und die Statusdatei
        #    (TARGETED_SEARCH_YTDLP_STATUS_FILE) laesst einen Folgelauf mit
        #    derselben Kanalliste bereits komplett erledigte Kanaele ueberspringen.
        targeted_channel_ids = load_targeted_channel_ids(TARGETED_SEARCH_YTDLP_CHANNEL_INPUT)
        print(f"Targeted-Search-yt-dlp-Modus: {len(targeted_channel_ids)} Kanaele aus "
              f"{TARGETED_SEARCH_YTDLP_CHANNEL_INPUT}")
        print(f"Zeitfenster: {TARGETED_PUBLISHED_AFTER} bis {TARGETED_PUBLISHED_BEFORE}")
        print(f"Statusdatei: {TARGETED_SEARCH_YTDLP_STATUS_FILE}")

        erledigt = load_ytdlp_completed_channels(
            TARGETED_SEARCH_YTDLP_STATUS_FILE, TARGETED_PUBLISHED_AFTER, TARGETED_PUBLISHED_BEFORE
        )
        if erledigt:
            print(f"Bereits komplett laut Statusdatei, werden uebersprungen: {len(erledigt)}")

        for channel_counter, cid in enumerate(targeted_channel_ids, start=1):
            print(f"Kanal: {cid} ({channel_counter}/{len(targeted_channel_ids)})")
            if cid in erledigt:
                print("  bereits komplett -> uebersprungen")
                continue

            status, detail = "komplett", ""
            try:
                channel_videos, n_lookup = get_channel_videos_via_ytdlp(
                    cid, TARGETED_PUBLISHED_AFTER, TARGETED_PUBLISHED_BEFORE
                )
            except YtdlpQuotaExceeded as e:
                channel_videos, n_lookup = e.videos, e.n_lookup
                status, detail = "teilweise_quota", "Quota erreicht"
            except Exception as e:
                print(f"  Fehler bei {cid}: {e}")
                append_ytdlp_status(TARGETED_SEARCH_YTDLP_STATUS_FILE, cid, "fehler", [], 0, str(e)[:300])
                continue

            n_gespeichert = _registry_upsert(channel_videos)
            new_videos.extend(channel_videos)
            append_ytdlp_status(TARGETED_SEARCH_YTDLP_STATUS_FILE, cid, status, channel_videos, n_lookup, detail)
            print(f"  Neue Videos im Fenster: {len(channel_videos)} (gespeichert: {n_gespeichert}, "
                  f"videos().list-Aufrufe: {n_lookup})")

            if status != "komplett":
                print("  API-Quota erreicht - Abbruch. Alle bisherigen Ergebnisse sind gespeichert; "
                      "ein Folgelauf mit derselben Kanalliste setzt bei diesem Kanal wieder an.")
                break

    else:
        raise ValueError(
            f"Unknown MODE: '{MODE}'. Permitted: 'NEW_CHANNELS', 'UPDATE', 'TARGETED_SEARCH' "
            "oder 'TARGETED_SEARCH_YTDLP'."
        )

    # ─────────────────────────────────────────────
    # Deduplizierung & Speichern
    # ─────────────────────────────────────────────
    # Zentrale Video-Registry mitfuehren (data/store/video_registry.sqlite),
    # unabhaengig vom Modus und von SAVE_JSON_SNAPSHOT - siehe
    # youtube_code.store.video_registry.
    n_registry = _registry_upsert(new_videos)
    print(f"In zentrale Registry geschrieben: {n_registry}")

    if SAVE_JSON_SNAPSHOT:
        all_videos   = videos_total + new_videos
        unique_dict  = {v["video_id"]: v for v in all_videos}  # last-write-wins
        videos_total = list(unique_dict.values())

        save_json(VIDEOS_TOTAL_FILE, videos_total)
        print(f"JSON-Snapshot geschrieben: {VIDEOS_TOTAL_FILE} ({len(videos_total)} Videos total)")
    else:
        print("JSON-Snapshot uebersprungen (SAVE_JSON_SNAPSHOT=False) - nur Registry aktualisiert.")

    print("\n── Process complete ──")
    print(f"Newly added         : {len(new_videos)}")
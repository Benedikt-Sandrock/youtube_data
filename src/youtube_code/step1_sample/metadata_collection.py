"""
Uses the file with all videos ("video_total.json") to collect (new) metadata for channels and videos.
Beide Fetch-Funktionen lesen bereits vorhandene IDs aus der zentralen
video_registry (data/store/video_registry.sqlite) und schreiben neu
abgefragte Metadaten auch nur noch dorthin - keine separaten JSON/JSONL-
Dateien mehr.

REFRESH_MODE (Schalter unten): steuert, welche der beiden Video-Fetch-
Funktionen video_metadata=True verwendet.
  - False (Standard): get_video_metadata() - ueberspringt video_ids, die laut
    Registry schon einen Eintrag haben (einmaliger Snapshot, view_count/
    like_count/comment_count bleiben fuer immer beim ersten abgerufenen Wert
    stehen, siehe video_registry.upsert_videos()-Docstring).
  - True: refresh_video_stats() - ruft die API fuer ALLE uebergebenen
    video_ids erneut auf (kein "schon bekannt"-Filter) und ueberschreibt
    view_count/like_count/comment_count bewusst mit dem neuen Wert (siehe
    video_registry.refresh_video_stats()-Docstring). Gedacht fuer gezielte
    Aktualisierungslaeufe, z.B. Views fuer Videos eines noch laufenden
    Zeitraums bei einem periodischen Registry-Update neu abrufen.
"""

import pandas as pd
from googleapiclient.discovery import build

from youtube_code.utils import get_channel_metadata, get_video_metadata, load_json, refresh_video_stats
from youtube_code.config import RAW, SAMPLES, API_KEY_C, API_KEY, CHANNEL_LISTS, OUTPUTS, ADHOC_OUTPUT
from youtube_code.store import video_registry

api_keys = [API_KEY_C, API_KEY]

# ─────────────────────────────────────────────
# CONFIGURATION AND PATHS
# ─────────────────────────────────────────────
channel_metadata = False
video_metadata = True
DETAILED = False
REFRESH_MODE = True  # True = view/like/comment_count fuer VIDEOS_INPUT_PATH bewusst ueberschreiben (siehe Docstring oben)

# VIDEOS_INPUT_PATH = SAMPLES / "russia_longitudinal_v1" / "identification_videos_missing_metadata.json"
# VIDEOS_INPUT_PATH = RAW / "sample_50k_channels_russia_ukraine.json"
# VIDEOS_INPUT_PATH = OUTPUTS / "segment_analysis" / "screening_state_missing_description_backfill_ids.csv"
# Refresh-Lauf 2026-09: view/like/comment_count fuer alle Videos im Fenster
# 1.1.-30.6.2026 der 292 Kanaele des Frage-1-Stufe-1-Samples auffrischen (Ad-hoc-
# Ableitung aus video_registry, siehe .claude/CLAUDE.md).
VIDEOS_INPUT_PATH = ADHOC_OUTPUT / "frage1_2026h1_video_ids_to_refresh.csv"

YOUTUBE = build("youtube", "v3", developerKey=api_keys[0])

# ─────────────────────────────────────────────
if channel_metadata:
    channel_ids = load_json(SAMPLES / "russia_longitudinal_v1" / "eligible_channels_current.json")
    # channel_ids = ["UCf4WJRXsgDEP7KH2eNGv8Hw"]
    get_channel_metadata(channel_ids, YOUTUBE)


if video_metadata:
    if VIDEOS_INPUT_PATH.suffix.lower() == ".json":
        data = load_json(VIDEOS_INPUT_PATH)
        video_ids = [v["video_id"] for v in data]
    else:
        df = pd.read_csv(VIDEOS_INPUT_PATH)
        video_ids = df["video_id"].to_list()
        # channel_ids = df["channel_id"].to_list()
        # channel_ids = set(channel_ids)
        # channel_ids = list(channel_ids)

    if REFRESH_MODE:
        refresh_video_stats(video_ids, YOUTUBE, DETAILED)
    else:
        get_video_metadata(video_ids, YOUTUBE, DETAILED)

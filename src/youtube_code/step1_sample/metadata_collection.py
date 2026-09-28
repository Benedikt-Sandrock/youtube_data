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

CHECK_CHANNELS_MODE (Schalter unten, seit 2026-09-10): Alternative zu einer
manuell kuratierten VIDEOS_INPUT_PATH-Liste - nimmt stattdessen eine
Kanalliste (MISSING_METADATA_CHANNEL_INPUT) entgegen und prueft ueber
get_missing_metadata_for_channels() fuer ALLE in der Registry bereits
bekannten Videos dieser Kanaele, ob Metadaten fehlen (Kriterium haengt von
DETAILED ab - siehe dortiger Docstring), und fragt nur die fehlenden gezielt
nach. Anlass: Diagnose von Datenluecken in
outputs/segment_analysis/kanaluebersicht_marktanteil_bericht.csv (Session
vom 2026-09-10, siehe outputs/segment_analysis/datenluecken_kanaluebersicht/
README.md) - dort betraf die Luecke ganze Kanal x Periode-Zellen, nicht eine
von vornherein bekannte Video-ID-Liste. KEINE Video-Discovery (keine
playlistItems.list-Anfrage) - fuer Kanaele/Zeitfenster, die in der Registry
noch gar kein Video haben, meldet die Funktion 0 fehlende Videos (das ist
eine Discovery-Luecke, siehe step1_sample/channel_all_videos.py,
TARGETED_SEARCH-Modus, nicht dieses Skript hier).
"""

import csv
import json

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
DETAILED = True
REFRESH_MODE = False  # True = view/like/comment_count fuer VIDEOS_INPUT_PATH bewusst ueberschreiben (siehe Docstring oben)

# CHECK_CHANNELS_MODE = True: video_metadata-Block nimmt eine Kanalliste
# (MISSING_METADATA_CHANNEL_INPUT) statt einer fertigen Video-ID-Liste
# entgegen und prueft selbst, welche der bereits bekannten Videos dieser
# Kanaele Metadaten fehlen - siehe get_missing_metadata_for_channels()
# unten sowie Moduldocstring. VIDEOS_INPUT_PATH/REFRESH_MODE werden in
# diesem Modus ignoriert (get_missing_metadata_for_channels() nutzt intern
# immer get_video_metadata(), nicht refresh_video_stats() - fuer Videos, die
# noch NIE erfolgreich abgefragt wurden, macht der "schon bekannt"-Filter
# keinen Unterschied, siehe Docstring dort).
CHECK_CHANNELS_MODE = True

# VIDEOS_INPUT_PATH = SAMPLES / "russia_longitudinal_v1" / "identification_videos_missing_metadata.json"
# VIDEOS_INPUT_PATH = RAW / "sample_50k_channels_russia_ukraine.json"
# Refresh-Lauf 2026-09: view/like/comment_count fuer alle Videos im Fenster
# 1.1.-30.6.2026 der 292 Kanaele des Frage-1-Stufe-1-Samples auffrischen (Ad-hoc-
# Ableitung aus video_registry, siehe .claude/CLAUDE.md).

# VIDEOS_INPUT_PATH = OUTPUTS / "segment_analysis" / "datenluecken_kanaluebersicht" / "kategorie1_fehlender_topic_nur.csv"
VIDEOS_INPUT_PATH = OUTPUTS / "segment_analysis" / "datenluecken_kanaluebersicht" / "kategorie1_fehlende_stats.csv"

# VIDEOS_INPUT_PATH = ADHOC_OUTPUT / "frage1_2026h1_video_ids_to_refresh.csv"

# Nur relevant bei CHECK_CHANNELS_MODE = True. CSV mit "channel_id"-Spalte
# oder JSON (Liste von IDs oder von Dicts mit "channel_id") - gleiches
# Format wie TARGETED_CHANNEL_INPUT in channel_all_videos.py.
MISSING_METADATA_CHANNEL_INPUT = (
    OUTPUTS / "segment_analysis" / "whitelist_ab_150.csv"
)

YOUTUBE = build("youtube", "v3", developerKey=api_keys[0])


def _load_channel_ids(path) -> list[str]:
    """
    Laedt eine Kanal-ID-Liste fuer CHECK_CHANNELS_MODE. Gleiches Format wie
    channel_all_videos.load_targeted_channel_ids() (bewusst dupliziert statt
    importiert - jenes Skript ist laut eigenem Docstring nicht zum Import
    gedacht, sein bare sibling import "from settings_variables import ..."
    funktioniert nur bei Direktausfuehrung).

    Akzeptiert:
      - .csv mit einer "channel_id"-Spalte (z.B. kategorie2_keine_videos.csv -
        Dubletten aus mehreren Perioden desselben Kanals werden entfernt)
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
        ids = [r["channel_id"] for r in raw] if raw and isinstance(raw[0], dict) else list(raw)
    else:
        raise ValueError(f"Nicht unterstuetztes Format fuer MISSING_METADATA_CHANNEL_INPUT: {path}")

    seen: set[str] = set()
    deduped = []
    for cid in ids:
        if cid not in seen:
            seen.add(cid)
            deduped.append(cid)
    return deduped


def get_missing_metadata_for_channels(channel_ids, youtube_client, detailed=False):
    """
    Nimmt eine Liste von channel_ids und prueft fuer ALLE in der Registry
    bereits bekannten Videos dieser Kanaele (video_registry.get_video_stats()),
    ob Metadaten fehlen - Kriterium haengt von detailed ab, analog zum
    "schon bekannt"-Filter von get_video_metadata() selbst:

      - detailed=False: view_count IS NULL - Basis-Statistik wurde nie
        abgefragt. Typischer Zustand direkt nach einer reinen Video-Discovery
        (channel_all_videos.py schreibt beim Anlegen nur video_id/channel_id/
        published_at/title, siehe dortiger upsert_videos()-Aufruf ohne
        view_count-Feld - COALESCE(alt, neu) laesst view_count dadurch NULL,
        bis eine Metadaten-Abfrage einmal einen Wert liefert).
      - detailed=True: video_id hat KEINE Zeile in video_details
        (video_registry.known_video_detail_ids()) - deckt sowohl "gar keine
        Metadaten" als auch "nur Basis-Metadaten (view_count etc.), aber
        keine Details/topic_categories" ab, unabhaengig vom view_count-
        Status.

    Ruft fuer die so ermittelten fehlenden video_ids get_video_metadata()
    auf (NICHT refresh_video_stats() - fuer Videos ohne jeden bisherigen
    Abruf macht der "schon bekannt"-Filter keinen Unterschied, siehe
    Moduldocstring). Schreibt wie gehabt direkt in video_registry.sqlite.

    Bewusst KEINE Video-Discovery (keine playlistItems.list-Anfrage): fuer
    einen Kanal, der in der Registry noch gar kein Video hat (oder nur fuer
    ein anderes Zeitfenster als das gesuchte), meldet diese Funktion 0
    fehlende Videos - das ist eine Discovery-Luecke, kein Metadaten-Problem,
    und muss stattdessen ueber channel_all_videos.py (TARGETED_SEARCH- bzw.
    TARGETED_SEARCH_YTDLP-Modus) geschlossen werden.
    """
    stats = video_registry.get_video_stats(channel_ids=channel_ids)
    print(f"[Kanal-Check] {len(channel_ids)} Kanaele, {len(stats)} bereits bekannte Videos "
          f"insgesamt (video_registry.get_video_stats()).")

    ohne_jedes_video = [cid for cid in channel_ids if cid not in set(stats["channel_id"])]
    if ohne_jedes_video:
        print(f"[Kanal-Check] Achtung: {len(ohne_jedes_video)} Kanal/Kanaele OHNE JEDES "
              f"bekannte Video in der Registry - das ist eine Discovery-Luecke, kein "
              f"Metadaten-Problem (channel_all_videos.py TARGETED_SEARCH-Modus verwenden): "
              f"{ohne_jedes_video}")

    if detailed:
        vorhanden = video_registry.known_video_detail_ids()
        fehlend = stats.loc[~stats["video_id"].isin(vorhanden), "video_id"].tolist()
        print(f"[Kanal-Check] Ohne video_details (topic_categories etc.): {len(fehlend)} von "
              f"{len(stats)} bekannten Videos.")
    else:
        fehlend = stats.loc[stats["view_count"].isna(), "video_id"].tolist()
        print(f"[Kanal-Check] Ohne view_count (Basis-Metadaten nie abgefragt): {len(fehlend)} "
              f"von {len(stats)} bekannten Videos.")

    if not fehlend:
        print("[Kanal-Check] Keine fehlenden Metadaten gefunden - nichts abzufragen.")
        return

    get_video_metadata(fehlend, youtube_client, detailed)


# ─────────────────────────────────────────────
if channel_metadata:
    channel_ids = load_json(SAMPLES / "russia_longitudinal_v1" / "eligible_channels_current.json")
    # channel_ids = ["UCf4WJRXsgDEP7KH2eNGv8Hw"]
    get_channel_metadata(channel_ids, YOUTUBE)


if video_metadata:
    if CHECK_CHANNELS_MODE:
        channel_ids = _load_channel_ids(MISSING_METADATA_CHANNEL_INPUT)
        print(f"[Kanal-Check] {len(channel_ids)} Kanal-IDs aus {MISSING_METADATA_CHANNEL_INPUT}")
        get_missing_metadata_for_channels(channel_ids, YOUTUBE, DETAILED)
    else:
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

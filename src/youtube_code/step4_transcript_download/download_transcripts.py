"""
Laedt Transkripte fuer eine Liste von Video-IDs herunter und schreibt sie in
transcript_store (COMPLETE_PROCESS.md Schritt 4). Verschoben und zu einer
importierbaren Funktion extrahiert aus
youtube_code/scraping/transcript_scraping_segments.py - Kernschleife
(Attempted-Filter, Kanal-Vorfilter, STOP_WORD-Notbremse, batchweises
upsert_transcripts, randomisierte Sleeps) unveraendert uebernommen.

Aufruf als Bibliothek (z.B. aus run_transcript_selection.py):
    from youtube_code.step4_transcript_download.download_transcripts import download_transcripts
    download_transcripts(video_ids, channel_map=channel_map, confirm_speed=False)

Aufruf als Skript (bisheriges Verhalten, liest VIDEO_LIST):
    PYTHONPATH=src .venv/Scripts/python.exe -m youtube_code.step4_transcript_download.download_transcripts
"""
import json
import random
import time
from datetime import datetime, timezone

import pandas as pd
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound

from youtube_code.config import MIN_VIDEO_DURATION_SECONDS
from youtube_code.store.transcript_store import attempted_video_ids, get_transcripts, upsert_transcripts
from youtube_code.store.video_registry import duration_lookup, get_channel_map, get_videos_for_channels

# =====================================================
# CONFIGURATION (Defaults - als Funktionsparameter ueberschreibbar)
# =====================================================

STOP_WORD = "blocking"
SPEED_DOWNLOAD = 1
VIDEO_LIST = "fill_vids_extended.json"  # nur fuer den __main__-Block

BATCH_SIZE = 5  # API-Batches
REQUIRED_COLUMNS = ["video_id", "transcript_segments", "language_code", "is_generated", "status"]

# Kanal-Vorfilter: Kanaele, fuer die schon MIN_ATTEMPTS_FOR_CHANNEL_CHECK
# Transkripte abgefragt wurden, aber weniger als MIN_AVAILABLE_REQUIRED davon
# tatsaechlich existieren ("status" == "OK"), werden komplett uebersprungen.
MIN_ATTEMPTS_FOR_CHANNEL_CHECK = 10
MIN_AVAILABLE_REQUIRED = 2


def get_transcript(video_id):
    yta = YouTubeTranscriptApi()
    return yta.fetch(video_id, languages=["de"])


def _load_video_list(path) -> list:
    """
    Liest eine VIDEO_LIST-JSON-Datei (Liste von Video-ID-Strings oder von
    {"video_id": ..., "channel_id": ...}-Dicts, siehe
    step2_baseline_channels/README.md §4) - nur fuer den __main__-Block,
    download_transcripts() selbst nimmt
    video_ids/channel_map bereits als Parameter entgegen.

    Rueckgabe: (video_ids_sorted, channel_map).
    """
    print("Reading sample videos...")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    channel_map = {}
    if isinstance(data, list) and len(data) > 0:
        if isinstance(data[0], dict):
            video_ids_sorted = [str(item["video_id"]) for item in data]
            for item in data:
                cid = item.get("channel_id")
                if cid:
                    channel_map[str(item["video_id"])] = str(cid)
        elif isinstance(data[0], str):
            video_ids_sorted = data
        else:
            raise ValueError("Ungueltiger Datentyp innerhalb der Liste.")
    else:
        raise ValueError("No valid format for video ids. Revise import.")

    print(f"Number of video-IDs: {len(video_ids_sorted)}")
    return video_ids_sorted, channel_map


def download_transcripts(
    video_ids: list,
    channel_map: dict | None = None,
    *,
    min_attempts_for_channel_check: int = MIN_ATTEMPTS_FOR_CHANNEL_CHECK,
    min_available_required: int = MIN_AVAILABLE_REQUIRED,
    batch_size: int = BATCH_SIZE,
    speed_download: bool = SPEED_DOWNLOAD,
    confirm_speed: bool = True,
    min_duration_seconds: int | None = MIN_VIDEO_DURATION_SECONDS,
) -> pd.DataFrame:
    """
    Laedt Transkripte fuer video_ids herunter (bereits per transcript_store
    attempted_video_ids() versuchte IDs werden uebersprungen) und schreibt sie
    batchweise per upsert_transcripts() in transcript_store.

    channel_map: optionales video_id -> channel_id Mapping (z.B. aus einer
    select_*_targets()-Ausgabe). Fehlende Eintraege werden aus
    video_registry.get_channel_map() nachgeladen. Dient nur dem
    Kanal-Vorfilter unten.

    confirm_speed: bei True UND speed_download wird wie im urspruenglichen
    Top-Level-Skript ein "Speed download activated. Continue? [y/N]"-Prompt
    gestellt; bei Ablehnung wird ein leeres DataFrame zurueckgegeben (statt
    exit(), was den gesamten aufrufenden Prozess beenden wuerde). Fuer den
    programmatischen Aufruf (z.B. aus run_transcript_selection.py) auf False
    setzen, um den Prompt zu ueberspringen.

    min_duration_seconds: letzte Absicherung (Default: MIN_VIDEO_DURATION_SECONDS
    aus youtube_code.config) - video_ids unter dieser Laenge oder mit
    unbekannter Dauer werden VOR jedem API-Call verworfen, unabhaengig davon,
    ob der Aufrufer (select_targets.py oder eine eigene Liste) schon gefiltert
    hat. min_duration_seconds=None deaktiviert die Pruefung.

    Rueckgabewert: DataFrame (Spalten REQUIRED_COLUMNS) aller in diesem Aufruf
    verarbeiteten Zeilen (unabhaengig vom bereits erfolgten upsert_transcripts).
    """
    print(f"Speed download: {speed_download}")
    if speed_download and confirm_speed:
        answer = input("Speed download activated. Continue? [y/N] ")
        if answer.lower() != "y":
            print("Abort.")
            return pd.DataFrame(columns=REQUIRED_COLUMNS)

    video_ids_sorted = [str(v) for v in video_ids]
    video_channel_map = dict(channel_map or {})

    if min_duration_seconds is not None:
        duration_by_id = duration_lookup(video_ids_sorted)
        too_short_or_unknown = {
            v for v in video_ids_sorted
            if duration_by_id.get(v) is None or duration_by_id.get(v) < min_duration_seconds
        }
        if too_short_or_unknown:
            video_ids_sorted = [v for v in video_ids_sorted if v not in too_short_or_unknown]
            print(
                f"\n⏱️ {len(too_short_or_unknown)} Video-IDs unter Mindestlaenge "
                f"({min_duration_seconds}s) oder mit unbekannter Dauer verworfen - "
                "kein Transkript-Download fuer diese IDs."
            )

    print("Loading already processed video IDs from transcript_store…")
    processed_video_ids = attempted_video_ids()
    print(f"\n➡️ {len(processed_video_ids)} video IDs already existing.")

    already_downloaded = [v for v in video_ids_sorted if v in processed_video_ids]
    print(f"\n{len(already_downloaded)}/{len(video_ids_sorted)} videos of this set already downloaded.")

    # =====================================================
    # KANAL-VORFILTER
    # =====================================================
    missing_channel_ids = [v for v in video_ids_sorted if v not in video_channel_map]
    if missing_channel_ids:
        video_channel_map.update(get_channel_map(missing_channel_ids))

    known_channel_ids = {cid for cid in video_channel_map.values() if cid}
    unmapped_count = len(video_ids_sorted) - sum(1 for v in video_ids_sorted if v in video_channel_map)

    if known_channel_ids:
        videos_by_channel = get_videos_for_channels(known_channel_ids)

        all_registry_videos = set()
        for cid in known_channel_ids:
            all_registry_videos |= videos_by_channel.get(cid, set())
        attempted_registry_ids = all_registry_videos & processed_video_ids
        status_by_video_id = {
            vid: rec.get("status")
            for vid, rec in get_transcripts(attempted_registry_ids).items()
        } if attempted_registry_ids else {}

        blocked_channels = set()
        for cid in known_channel_ids:
            registry_videos = videos_by_channel.get(cid, set())
            attempted_ids = registry_videos & processed_video_ids
            attempted = len(attempted_ids)
            available = sum(1 for v in attempted_ids if status_by_video_id.get(v) == "OK")

            if attempted >= min_attempts_for_channel_check and available < min_available_required:
                blocked_channels.add(cid)

        if blocked_channels:
            before = len(video_ids_sorted)
            video_ids_sorted = [
                v for v in video_ids_sorted
                if video_channel_map.get(v) not in blocked_channels
            ]
            removed = before - len(video_ids_sorted)
            print(
                f"\n🚫 {len(blocked_channels)} Kanal/Kanäle ohne ausreichend verfügbare Transkripte "
                f"(>= {min_attempts_for_channel_check} abgefragt, < {min_available_required} vorhanden) "
                f"— {removed} Video-IDs dadurch entfernt."
            )
        else:
            print(f"\n✅ Kanal-Vorfilter: kein Kanal erreicht die Sperr-Schwelle.")

        if unmapped_count:
            print(f"ℹ️ {unmapped_count} Video-IDs ohne bekannte channel_id — für sie entfällt der Kanal-Vorfilter.")
    else:
        print("\nℹ️ Keine channel_id verfügbar (weder im Input noch in der Registry) — Kanal-Vorfilter wird übersprungen.")

    num_remaining_vids = len([v for v in video_ids_sorted if v not in processed_video_ids])
    videos_to_process = [v for v in video_ids_sorted if v not in processed_video_ids]

    random.shuffle(videos_to_process)
    print(f"\n🎲 {len(videos_to_process)} videos left to process. Order has been randomized.")

    # =====================================================
    # DOWNLOAD
    # =====================================================

    daten = []
    all_rows = []
    api_request_count = 0
    last_skipped_id = None

    for video_id in videos_to_process:
        if video_id in processed_video_ids:
            last_skipped_id = video_id
            continue

        if last_skipped_id is not None:
            print(f"Last skipped ID: {last_skipped_id}")
            last_skipped_id = None

        print(f"Processing video-ID: {video_id}")

        try:
            segments = get_transcript(video_id)

            transcript_segments = [
                {"start": seg.start, "duration": seg.duration, "text": seg.text}
                for seg in segments
            ]

            row = {
                "video_id": video_id,
                "transcript_segments": json.dumps(transcript_segments, ensure_ascii=False),
                "language_code": getattr(segments, "language_code", None),
                "is_generated": getattr(segments, "is_generated", None),
                "status": "OK",
            }

        except NoTranscriptFound:
            print(f"   -> No transcript for {video_id}")
            row = {
                "video_id": video_id,
                "transcript_segments": None,
                "language_code": None,
                "is_generated": None,
                "status": "Kein Transkript",
            }

        except Exception as e:
            error_msg = str(e).lower()
            if STOP_WORD in error_msg:
                timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
                print(f"{timestamp}: IP blocked – Loop is terminated\n"
                      f"Terminated after {api_request_count} requests")
                print(error_msg)
                break
            else:
                print(f"   -> Error at {video_id}: {e}")
                row = {
                    "video_id": video_id,
                    "transcript_segments": None,
                    "language_code": None,
                    "is_generated": None,
                    "status": f"Fehler: {e}",
                }

        daten.append(row)
        all_rows.append(row)

        api_request_count += 1

        pause = random.uniform(15, 20) if speed_download else random.uniform(26, 36)
        print(f"→ Break: {pause:.2f} seconds")
        time.sleep(pause)

        if api_request_count % batch_size == 0:
            print(f"\n Saving …")
            upsert_transcripts(daten)
            daten.clear()
            batch_break = random.uniform(20, 40) if speed_download else random.uniform(45, 85)
            remaining_requests = num_remaining_vids - api_request_count
            print(f"Batch break after {api_request_count} requests: {batch_break:.2f} seconds."
                  f"\n{remaining_requests} requests remaining.\n")
            time.sleep(batch_break)

        if api_request_count % 100 == 0:
            long_break = random.uniform(290, 310)
            print(f"Long break: {long_break:.2f} seconds")
            time.sleep(long_break)

    if daten:
        print("\n💾 Saving remaining data …")
        upsert_transcripts(daten)

    print("\n✅ Done!")
    return pd.DataFrame(all_rows, columns=REQUIRED_COLUMNS)


if __name__ == "__main__":
    video_ids_sorted, channel_map = _load_video_list(VIDEO_LIST)
    download_transcripts(video_ids_sorted, channel_map=channel_map, confirm_speed=True)

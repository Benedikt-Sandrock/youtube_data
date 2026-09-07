"""
Laedt Kommentare fuer eine Liste von Video-IDs herunter und schreibt sie in
comment_store (COMPLETE_PROCESS.md Schritt 7). Extrahiert und generalisiert
aus youtube_code/archive/collection/comment_download.py
(get_everything_from_videos) - Kernlogik (Top-Level + optionale Replies,
403-Key-Rotation, "disabled" als separater Fall) uebernommen, aber:
- Resume/Dedupe laeuft jetzt ueber comment_store statt CSV +
  processed_ids.txt/finished_videos.txt.
- Key-Liste ist konfigurierbar (nicht mehr hart auf 2 Keys kodiert).
- Videos ohne erkennbare Kommentare werden VOR dem API-Call anhand von
  video_registry.comment_count_lookup() (comment_count NULL/0) aussortiert,
  statt jedes Video anzufragen und "Comments disabled" erst aus der
  403-Antwort zu erkennen - Vorfilter-Idee analog zum
  comment_count-Filter in archive/collection/comment_download.py.
- Kein STOP_WORD/Sleep-Regime wie beim Transkript-Download
  (download_transcripts.py): die offizielle YouTube Data API begrenzt nur
  ueber das taegliche Quota, nicht ueber IP-Sperren bei zu schnellen
  Requests - ein kurzer Hoeflichkeits-Sleep reicht.

Aufruf als Bibliothek (z.B. aus run_comment_selection.py):
    from youtube_code.step7_comments.download_comments import download_comments
    download_comments(video_ids, channel_map=channel_map, include_replies=False)

Aufruf als Skript: Modus und Eingabe werden ueber den CONFIG-Block unten
(MODE/VIDEO_LIST/CHANNEL_LIST_CSV/INCLUDE_REPLIES) gesteuert, nicht ueber
Kommandozeilenargumente - vor dem Lauf dort eintragen, dann:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step7_comments.download_comments

MODE = "video_list" (Default): laedt die Video-ID-Liste aus VIDEO_LIST
(JSON, Liste von IDs oder von {"video_id": ...}-Objekten).

MODE = "channels": laedt ALLE in video_registry bekannten Videos der
Kanaele aus CHANNEL_LIST_CSV (CSV mit channel_id-Spalte, Muster analog zu
step2_baseline_channels/append_channels_to_state.py) ueber
select_targets.py::select_channel_targets.
"""
import random
import time

import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from youtube_code.config import API_KEY, API_KEY_C, SAMPLES
from youtube_code.store.comment_store import attempted_video_ids, upsert_comment_status, upsert_comments
from youtube_code.store.video_registry import comment_count_lookup

# =====================================================
# CONFIGURATION (Defaults - als Funktionsparameter ueberschreibbar)
# =====================================================

API_KEYS = [API_KEY, API_KEY_C]
BATCH_SIZE = 20  # Anzahl Videos zwischen zwei Status-/Kommentar-Upserts

# --- nur fuer den __main__-Block ---
MODE = "channels"  # "video_list" (VIDEO_LIST-JSON) oder "channels" (CHANNEL_LIST_CSV)
VIDEO_LIST = "request_comments.json"  # nur bei MODE="video_list"
CHANNEL_LIST_CSV = SAMPLES / "russia_longitudinal_v1" / "topic_channels_sample.csv"  # nur bei MODE="channels": CSV mit channel_id-Spalte
INCLUDE_REPLIES = False


def _fetch_video_comments(youtube, video_id: str, include_replies: bool) -> list[dict]:
    """
    Holt alle Top-Level-Kommentare eines Videos (und bei include_replies=True
    zusaetzlich alle Antworten) ueber commentThreads().list()/comments().list().
    Wirft HttpError unveraendert weiter (Quota-/Disabled-/sonstige Fehler
    werden im Aufrufer unterschieden).
    """
    rows = []
    request = youtube.commentThreads().list(
        part="snippet",
        videoId=video_id,
        maxResults=100,
        textFormat="plainText",
    )
    while request:
        response = request.execute()
        for item in response["items"]:
            top_snippet = item["snippet"]["topLevelComment"]["snippet"]
            parent_id = item["snippet"]["topLevelComment"]["id"]
            rows.append({
                "comment_id": parent_id,
                "video_id": video_id,
                "parent_id": None,
                "type": "top_level",
                "author": top_snippet.get("authorDisplayName"),
                "author_channel_id": (top_snippet.get("authorChannelId") or {}).get("value"),
                "text": top_snippet.get("textDisplay"),
                "published_at": top_snippet.get("publishedAt"),
                "updated_at": top_snippet.get("updatedAt"),
                "like_count": top_snippet.get("likeCount"),
            })

            if include_replies and item["snippet"]["totalReplyCount"] > 0:
                reply_request = youtube.comments().list(
                    part="snippet",
                    parentId=parent_id,
                    maxResults=100,
                    textFormat="plainText",
                )
                while reply_request:
                    reply_response = reply_request.execute()
                    for reply_item in reply_response["items"]:
                        reply_snippet = reply_item["snippet"]
                        rows.append({
                            "comment_id": reply_item["id"],
                            "video_id": video_id,
                            "parent_id": parent_id,
                            "type": "reply",
                            "author": reply_snippet.get("authorDisplayName"),
                            "author_channel_id": (reply_snippet.get("authorChannelId") or {}).get("value"),
                            "text": reply_snippet.get("textDisplay"),
                            "published_at": reply_snippet.get("publishedAt"),
                            "updated_at": reply_snippet.get("updatedAt"),
                            "like_count": reply_snippet.get("likeCount"),
                        })
                    reply_request = youtube.comments().list_next(reply_request, reply_response)

        request = youtube.commentThreads().list_next(request, response)

    return rows


def download_comments(
    video_ids: list,
    channel_map: dict | None = None,
    *,
    include_replies: bool = False,
    api_keys: list | None = None,
    batch_size: int = BATCH_SIZE,
    sleep_range: tuple[float, float] = (0.1, 0.3),
) -> pd.DataFrame:
    """
    Laedt Kommentare fuer video_ids herunter (Videos, die laut
    comment_store.attempted_video_ids(include_replies) die angefragte Tiefe
    schon abdecken, werden uebersprungen) und schreibt sie batchweise per
    upsert_comments()/upsert_comment_status() in comment_store.

    Vor dem eigentlichen Abruf werden zusaetzlich Videos aussortiert, fuer
    die video_registry.comment_count_lookup() comment_count NULL oder 0
    liefert - laut Metadaten sind fuer diese Videos keine Kommentare
    verfuegbar (z.B. deaktiviert), ein API-Call waere verschwendet. Videos,
    die (noch) gar nicht in video_registry stehen, werden dabei ebenfalls
    uebersprungen, da ihr comment_count-Status unbekannt ist - sie muessten
    erst per metadata_collection.py erfasst werden.

    channel_map wird hier nicht fuer einen Vorfilter genutzt (anders als bei
    download_transcripts) - Platzhalterparameter fuer Aufruf-Symmetrie mit
    select_targets.py-Ergebnissen (video_id/channel_id-DataFrames); kann
    kuenftig fuer einen kanalbasierten Vorfilter genutzt werden, falls sich
    das als noetig erweist.

    include_replies: siehe comment_store-Moduldocstring - steuert sowohl,
    welche Videos als "schon erledigt" gelten, als auch, ob fuer neu
    abgefragte Videos Antworten mitgeholt werden.

    api_keys: Liste von YouTube-API-Keys fuer Rotation bei Quota-Fehlern
    (403). Default: [API_KEY, API_KEY_C] aus youtube_code.config.

    Rueckgabewert: DataFrame aller in diesem Aufruf gespeicherten
    Kommentar-Zeilen (nicht der Status-Zeilen).
    """
    keys = list(api_keys) if api_keys else API_KEYS
    keys = [k for k in keys if k]
    if not keys:
        raise ValueError("Kein YouTube-API-Key verfuegbar (API_KEY/API_KEY_C in .env pruefen).")

    key_index = 0
    youtube = build("youtube", "v3", developerKey=keys[key_index])

    video_ids_sorted = sorted({str(v) for v in video_ids if v})
    already_done = attempted_video_ids(include_replies=include_replies)
    videos_to_process = [v for v in video_ids_sorted if v not in already_done]

    print(f"{len(video_ids_sorted)} Video-IDs uebergeben, {len(video_ids_sorted) - len(videos_to_process)} "
          f"davon bereits mit include_replies={include_replies} erfasst.")

    # Videos ohne erkennbare Kommentare (comment_count laut video_registry
    # NULL oder 0 - siehe get_video_stats()-Docstring: ein fehlender Wert
    # bedeutet "von der API nie geliefert", z.B. bei deaktivierten
    # Kommentaren) werden gar nicht erst angefragt, statt fuer sie einen
    # API-Call zu "verbrauchen" und danach den Status "Comments disabled"
    # zu speichern.
    counts = comment_count_lookup(videos_to_process)
    no_comments = [v for v in videos_to_process if not counts.get(v)]
    if no_comments:
        print(f"{len(no_comments)} Video(s) laut Metadaten ohne Kommentare (comment_count NULL/0) - werden uebersprungen.")
    videos_to_process = [v for v in videos_to_process if counts.get(v)]

    print(f"{len(videos_to_process)} Videos werden abgefragt.")

    status_batch = []
    comments_batch = []
    all_comment_rows = []

    for i, video_id in enumerate(videos_to_process, start=1):
        print(f"[{i}/{len(videos_to_process)}] {video_id}")

        try:
            rows = _fetch_video_comments(youtube, video_id, include_replies)
            n_top = sum(1 for r in rows if r["type"] == "top_level")
            n_replies = sum(1 for r in rows if r["type"] == "reply")
            status_batch.append({
                "video_id": video_id,
                "status": "OK",
                "include_replies": include_replies,
                "n_top_level": n_top,
                "n_replies": n_replies,
            })
            comments_batch.extend(rows)
            all_comment_rows.extend(rows)

        except HttpError as e:
            error_msg = str(e)
            if e.resp.status == 403 and "disabled" in error_msg.lower():
                print(f"   -> Kommentare deaktiviert fuer {video_id}")
                status_batch.append({
                    "video_id": video_id,
                    "status": "Comments disabled",
                    "include_replies": include_replies,
                    "n_top_level": 0,
                    "n_replies": 0,
                })
            elif e.resp.status == 403:
                print(f"   -> Quota erschoepft auf Key {key_index + 1}")
                key_index += 1
                if key_index < len(keys):
                    youtube = build("youtube", "v3", developerKey=keys[key_index])
                    print(f"   -> Wechsel zu Key {key_index + 1}, {video_id} wird erneut versucht.")
                    videos_to_process.insert(i, video_id)  # gleiches Video erneut versuchen
                    continue
                else:
                    print("   -> Alle API-Keys erschoepft. Breche ab.")
                    break
            else:
                print(f"   -> Fehler bei {video_id}: {e}")
                status_batch.append({
                    "video_id": video_id,
                    "status": f"Fehler: {e}",
                    "include_replies": include_replies,
                    "n_top_level": 0,
                    "n_replies": 0,
                })

        except Exception as e:
            print(f"   -> Fehler bei {video_id}: {e}")
            status_batch.append({
                "video_id": video_id,
                "status": f"Fehler: {e}",
                "include_replies": include_replies,
                "n_top_level": 0,
                "n_replies": 0,
            })

        time.sleep(random.uniform(*sleep_range))

        if len(status_batch) >= batch_size:
            print(f"   Speichere Batch ({len(status_batch)} Videos, {len(comments_batch)} Kommentare) …")
            upsert_comments(comments_batch)
            upsert_comment_status(status_batch)
            comments_batch.clear()
            status_batch.clear()

    if status_batch:
        print(f"Speichere letzten Batch ({len(status_batch)} Videos, {len(comments_batch)} Kommentare) …")
        upsert_comments(comments_batch)
        upsert_comment_status(status_batch)

    print("Fertig.")
    return pd.DataFrame(all_comment_rows)


if __name__ == "__main__":
    import json

    if MODE == "channels":
        from youtube_code.step7_comments.select_targets import select_channel_targets

        channels_df = pd.read_csv(CHANNEL_LIST_CSV, dtype={"channel_id": "string"})
        channel_ids = sorted(set(channels_df["channel_id"]))
        print(f"{len(channel_ids)} Zielkanaele aus {CHANNEL_LIST_CSV}.")

        targets = select_channel_targets(channel_ids, include_replies=INCLUDE_REPLIES)
        download_comments(targets["video_id"].tolist(), include_replies=INCLUDE_REPLIES)
    elif MODE == "video_list":
        with open(VIDEO_LIST, "r", encoding="utf-8") as f:
            data = json.load(f)
        ids = [str(item["video_id"]) if isinstance(item, dict) else str(item) for item in data]
        download_comments(ids, include_replies=INCLUDE_REPLIES)
    else:
        raise ValueError(f"Unbekannter MODE: {MODE!r} (erwartet 'video_list' oder 'channels').")

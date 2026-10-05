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
- 403-Fehler werden anhand des API-Fehlergrunds (_error_reason)
  unterschieden: nur Quota-Gruende (QUOTA_REASONS) loesen die
  Key-Rotation aus, "commentsDisabled" wird als "Comments disabled"
  gespeichert, alle anderen 403 (z.B. Mitglieder-exklusive/private Videos)
  als "Kein Zugriff: <reason>" - diese Videos werden uebersprungen, statt
  alle Keys zu durchlaufen und den Lauf abzubrechen.
- Kein STOP_WORD/Sleep-Regime wie beim Transkript-Download
  (download_transcripts.py): die offizielle YouTube Data API begrenzt nur
  ueber das taegliche Quota, nicht ueber IP-Sperren bei zu schnellen
  Requests - ein kurzer Hoeflichkeits-Sleep reicht.

Aufruf als Bibliothek (z.B. aus run_comment_selection.py):
    from youtube_code.step7_comments.download_comments import download_comments
    download_comments(video_ids, channel_map=channel_map, include_replies=False)

Aufruf als Skript: Modus und Eingabe werden ueber den CONFIG-Block unten
(MODE/VIDEO_LIST/CHANNEL_LIST_CSV/TOPIC/INCLUDE_REPLIES) gesteuert, nicht ueber
Kommandozeilenargumente - vor dem Lauf dort eintragen, dann:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step7_comments.download_comments

MODE = "video_list": laedt die Video-ID-Liste aus VIDEO_LIST
(JSON, Liste von IDs oder von {"video_id": ...}-Objekten).

MODE = "channels": laedt ALLE in video_registry bekannten Videos der
Kanaele aus CHANNEL_LIST_CSV (CSV mit channel_id-Spalte, Muster analog zu
step2_baseline_channels/append_channels_to_state.py) ueber
select_targets.py::select_channel_targets.

MODE = "channels_topic": wie "channels", aber nur die Videos der Kanaele
aus CHANNEL_LIST_CSV, die fuer TOPIC (Default "russia_ukraine_war") in
video_topic_relevance als relevant klassifiziert sind - d.h. nur die
Kriegsvideos des Samples (gleiche Definition wie ist_kriegsvideo in
step6_auswertung), ueber select_targets.py::select_topic_targets. Die
Abfragereihenfolge innerhalb dieser Videos ist wie in allen Modi zufaellig
(siehe download_comments(), shuffle_seed).
"""
import json
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
SHUFFLE_SEED = None  # None = bei jedem Lauf neue Zufallsreihenfolge; int = reproduzierbare Reihenfolge

# --- nur fuer den __main__-Block ---
MODE = "channels_topic"  # "video_list" (VIDEO_LIST-JSON), "channels" (alle Videos aus CHANNEL_LIST_CSV) oder "channels_topic" (nur TOPIC-Videos aus CHANNEL_LIST_CSV)
VIDEO_LIST = "request_comments.json"  # nur bei MODE="video_list"
CHANNEL_LIST_CSV = SAMPLES / "russia_longitudinal_v1" / "topic_channels_sample.csv"  # bei MODE="channels"/"channels_topic": CSV mit channel_id-Spalte
TOPIC = "russia_ukraine_war"  # nur bei MODE="channels_topic": Topic aus video_topic_relevance (Kriegsvideos = ist_kriegsvideo in step6)
INCLUDE_REPLIES = False


QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded", "userRateLimitExceeded"}


def _error_reason(e: HttpError) -> str | None:
    """
    Liest den maschinenlesbaren Fehlergrund (z.B. "quotaExceeded",
    "commentsDisabled", "forbidden") aus einer HttpError-Antwort der Data API.
    None, falls die Antwort keinen Grund enthaelt/nicht parsebar ist.
    """
    try:
        details = e.error_details
        if details and isinstance(details, list) and details[0].get("reason"):
            return details[0]["reason"]
    except Exception:
        pass
    try:
        content = json.loads(e.content.decode("utf-8"))
        return content["error"]["errors"][0]["reason"]
    except Exception:
        return None


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
    shuffle_seed: int | None = SHUFFLE_SEED,
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

    Reihenfolge: die nach allen Vorfiltern verbleibenden Videos werden in
    zufaelliger Reihenfolge abgefragt, damit bei einem Abbruch (z.B. Quota
    aller Keys erschoepft) die bis dahin erfassten Videos eine
    Zufallsstichprobe sind statt eines alphabetischen Ausschnitts nach
    Video-ID. shuffle_seed=None (Default) mischt bei jedem Lauf neu; ein int
    macht die Reihenfolge reproduzierbar.

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

    # Zufaellige Abfragereihenfolge (siehe Docstring) - erst nach den
    # Vorfiltern, auf der sortierten Liste, damit ein fester shuffle_seed
    # unabhaengig von der Eingabereihenfolge dieselbe Reihenfolge liefert.
    random.Random(shuffle_seed).shuffle(videos_to_process)

    print(f"{len(videos_to_process)} Videos werden in zufaelliger Reihenfolge abgefragt"
          f"{f' (Seed {shuffle_seed})' if shuffle_seed is not None else ''}.")

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
            reason = _error_reason(e)
            # Nur echte Quota-Fehler loesen die Key-Rotation aus. Andere 403
            # (z.B. Mitglieder-exklusive oder private Videos, reason
            # "forbidden") werden als Fehlerstatus gespeichert und
            # uebersprungen - sonst wuerde ein einzelnes gesperrtes Video
            # nacheinander alle Keys "verbrauchen" und den Lauf abbrechen.
            is_quota = (reason in QUOTA_REASONS) if reason else ("quota" in error_msg.lower())
            if e.resp.status == 403 and (reason == "commentsDisabled" or "disabled" in error_msg.lower()):
                print(f"   -> Kommentare deaktiviert fuer {video_id}")
                status_batch.append({
                    "video_id": video_id,
                    "status": "Comments disabled",
                    "include_replies": include_replies,
                    "n_top_level": 0,
                    "n_replies": 0,
                })
            elif e.resp.status == 403 and is_quota:
                print(f"   -> Quota erschoepft auf Key {key_index + 1} ({reason})")
                key_index += 1
                if key_index < len(keys):
                    youtube = build("youtube", "v3", developerKey=keys[key_index])
                    print(f"   -> Wechsel zu Key {key_index + 1}, {video_id} wird erneut versucht.")
                    videos_to_process.insert(i, video_id)  # gleiches Video erneut versuchen
                    continue
                else:
                    print("   -> Alle API-Keys erschoepft. Breche ab.")
                    break
            elif e.resp.status == 403:
                print(f"   -> Kein Zugriff auf {video_id} ({reason}, z.B. Mitglieder-exklusiv/privat) - uebersprungen")
                status_batch.append({
                    "video_id": video_id,
                    "status": f"Kein Zugriff: {reason}",
                    "include_replies": include_replies,
                    "n_top_level": 0,
                    "n_replies": 0,
                })
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
    if MODE == "channels":
        from youtube_code.step7_comments.select_targets import select_channel_targets

        channels_df = pd.read_csv(CHANNEL_LIST_CSV, dtype={"channel_id": "string"})
        channel_ids = sorted(set(channels_df["channel_id"]))
        print(f"{len(channel_ids)} Zielkanaele aus {CHANNEL_LIST_CSV}.")

        targets = select_channel_targets(channel_ids, include_replies=INCLUDE_REPLIES)
        download_comments(targets["video_id"].tolist(), include_replies=INCLUDE_REPLIES)
    elif MODE == "channels_topic":
        from youtube_code.step7_comments.select_targets import select_topic_targets

        channels_df = pd.read_csv(CHANNEL_LIST_CSV, dtype={"channel_id": "string"})
        channel_ids = sorted(set(channels_df["channel_id"].dropna()))
        print(f"{len(channel_ids)} Zielkanaele aus {CHANNEL_LIST_CSV}, Topic {TOPIC!r}.")

        targets = select_topic_targets(topic=TOPIC, channel_ids=channel_ids, include_replies=INCLUDE_REPLIES)
        print(f"{len(targets)} {TOPIC}-Videos ohne bisherigen Kommentar-Fetch in "
              f"{targets['channel_id'].nunique()} Kanaelen.")
        channel_map = targets.set_index("video_id")["channel_id"].to_dict()
        download_comments(targets["video_id"].tolist(), channel_map=channel_map, include_replies=INCLUDE_REPLIES)
    elif MODE == "video_list":
        with open(VIDEO_LIST, "r", encoding="utf-8") as f:
            data = json.load(f)
        ids = [str(item["video_id"]) if isinstance(item, dict) else str(item) for item in data]
        download_comments(ids, include_replies=INCLUDE_REPLIES)
    else:
        raise ValueError(f"Unbekannter MODE: {MODE!r} (erwartet 'video_list', 'channels' oder 'channels_topic').")

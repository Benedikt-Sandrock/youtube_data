"""
channel_video_formats.py

Ermittelt fuer eine Kanalliste das Format jedes Videos im Zeitfenster
[PUBLISHED_AFTER, PUBLISHED_BEFORE] - Short, normales Video (long-form) oder
Livestream - und schreibt es in die Tabelle video_format der zentralen
Registry (data/store/video_registry.sqlite). Videos, die dabei gefunden werden,
aber noch nicht in der Registry stehen, werden mit detaillierten Metadaten
(videos + video_details) nachgetragen.

Warum Playlists: Die YouTube Data API hat kein isShort-Feld. Jeder Kanal hat
aber automatisch erzeugte, nach Format getrennte Upload-Playlists, deren ID sich
aus der Channel-ID ableitet (UC<rest> ->):
    UUSH<rest>  nur Shorts
    UULF<rest>  nur normale Videos (long-form)
    UULV<rest>  nur Livestreams
Die Herkunfts-Playlist liefert das Format (undokumentiert, aber stabil; per
HEAD_CHECK_SAMPLE gegen https://www.youtube.com/shorts/<id> stichprobenartig
validiert).

Ablauf pro Kanal:
  1. playlistItems.list fuer UUSH/UULF/UULV (1 Quota-Einheit je 50 Eintraege),
     neueste zuerst, Stopp sobald eine ganze Seite vor PUBLISHED_AFTER liegt.
     Fehlende Playlist (404, z.B. Kanal ohne Livestreams) = 0 Videos.
  2. Abbruch-Erkennung: YouTube haelt nur die neuesten ~20.000 Uploads eines
     Kanals per playlistItems abrufbar, und die drei Format-Playlists sind
     gefilterte Ansichten genau dieses gekappten Bestands - sie teilen sich
     die Grenze (tagesschau: 14.901 + 3.963 + 1.137 ~ 20.000, alle enden im
     Juli 2022). pageInfo.totalResults meldet dabei schon die gekappte Zahl,
     taugt also nicht zur Erkennung. Stattdessen: meldet die normale Upload-
     Playlist UU<rest> >= UPLOADS_CAP_THRESHOLD Eintraege (1 Quota-Einheit),
     gilt jede Format-Playlist, die den Fensteranfang nicht erreicht, als
     abgeschnitten.
  3. yt-dlp-Fallback nur fuer abgeschnittene Playlists: der passende Kanal-Tab
     (/shorts, /videos, /streams) wird per yt-dlp aufgezaehlt
     (youtube_code/utils/ytdlp.py, lazy in 50er-Bloecken); in der Registry
     bekannte IDs bekommen ihr published_at von dort, unbekannte werden per
     videos.list nachgeschlagen. Sobald YTDLP_EARLY_STOP_BATCHES Bloecke
     komplett vor dem Fensteranfang liegen, wird das Blaettern beendet.
  4. Konflikte (ID in zwei Formaten): Prioritaet live > short > long, gezaehlt.
  5. Neue Videos (nicht in der Registry) werden per
     utils.io.fetch_video_metadata_records(detailed=True) abgefragt.
  6. Schreiben: video_registry.write_channel_format_result() in EINER
     Transaktion, danach Status-Zeile "komplett".

Quota-Abbruch (Alles-oder-nichts pro Kanal): Alle Ergebnisse eines Kanals
liegen bis zum Schluss nur im Speicher. Bei einem Quota-Fehler wird der
laufende Kanal verworfen (nichts im Store), als "abgebrochen_quota" in der
Statusdatei vermerkt und das Skript beendet. Ein Folgelauf mit derselben
Kanalliste und demselben Fenster ueberspringt alle "komplett"-Kanaele und
fragt den Abbruchkanal komplett neu ab.

Ausgaben:
  - Statusdatei <liste>_formats_status.csv neben der Kanalliste (eine Zeile pro
    bearbeitetem Kanal; zum kompletten Neu-Durchlauf loeschen).
  - Report outputs/video_formats/<liste>_formats_report.md (bei DRY_RUN mit
    Suffix _dryrun): Formate je Kanal, neue Videos, Abbrueche/Fallbacks,
    Registry-Videos ohne Format, Dauer-Plausibilitaet, HEAD-Validierung.

DRY_RUN = True: Alles wird abgefragt (kostet Quota), aber nichts in den Store
oder die Statusdatei geschrieben - nur der Report.

Nachgelagert: Fuer neu eingetragene Videos fehlt die Themen-Relevanz ->
step3_topic_relevance/classify_topic_relevance.py fuer diese Kanaele laufen
lassen.

Run pattern: direkt ausfuehren (`python channel_video_formats.py`), nicht
importieren (baut beim Start einen API-Client).
"""

import csv
import json
import os
import random
import sys
import time
from collections import Counter
from datetime import datetime, timezone

# Windows-Konsole (cp1252) -> UTF-8, siehe channel_all_videos.py
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from youtube_code.config import API_KEY_C, CHANNEL_LISTS, OUTPUTS
from youtube_code.store import video_registry
from youtube_code.utils.io import chunk_list, fetch_video_metadata_records, get_channel_metadata
from youtube_code.utils.ytdlp import iter_channel_video_id_batches

# ─────────────────────────────────────────────
# Konfiguration
# ─────────────────────────────────────────────
# Kanalliste: CSV mit "channel_id"-Spalte oder JSON (Liste von IDs bzw. Dicts
# mit "channel_id").
CHANNEL_INPUT = CHANNEL_LISTS / "video_formats" / "alt_kanaele.csv"

PUBLISHED_AFTER = "2021-01-01T00:00:00Z"
PUBLISHED_BEFORE = "2026-06-30T23:59:59Z"

DRY_RUN = False

# Anzahl Videos (je zur Haelfte Shorts / Nicht-Shorts) fuer die HEAD-Validierung
# gegen https://www.youtube.com/shorts/<id>. 0 = aus. Kostet keine Quota.
HEAD_CHECK_SAMPLE = 0

# Nur fuer Tests der Abbruchlogik: nach so vielen API-Aufrufen wird ein
# Quota-Fehler simuliert. None = aus.
SIMULATE_QUOTA_AFTER_CALLS = None

# Meldet die normale Upload-Playlist (UU<rest>) mindestens so viele Eintraege,
# gilt der Kanal als gekappt: YouTube haelt nur die neuesten ~20.000 Uploads
# abrufbar, und UULF/UUSH/UULV sind Filter dieses gekappten Bestands (siehe
# uploads_total()). Jede Format-Playlist, die dann den Fensteranfang nicht
# erreicht, wird per yt-dlp ergaenzt. Puffer unter 20.000, falls die Grenze
# leicht schwankt.
UPLOADS_CAP_THRESHOLD = 19_500

# yt-dlp-Fallback: Abbruch, sobald so viele aufeinanderfolgende 50er-Batches
# komplett vor PUBLISHED_AFTER liegen (Tab ist neueste zuerst sortiert). Spart
# videos.list-Aufrufe UND das Abrufen der aelteren Tab-Seiten.
YTDLP_EARLY_STOP_BATCHES = 2

STATUS_FILE = str(CHANNEL_INPUT).rsplit(".", 1)[0] + "_formats_status.csv"
REPORT_DIR = OUTPUTS / "video_formats"

YOUTUBE = build("youtube", "v3", developerKey=API_KEY_C)

# Format -> (Playlist-Praefix, yt-dlp-Tab). Reihenfolge = aufsteigende
# Prioritaet bei Konflikten (spaeter ueberschreibt frueher).
FORMAT_SOURCES = {
    "long": ("UULF", "videos"),
    "short": ("UUSH", "shorts"),
    "live": ("UULV", "streams"),
}

# Seit dem 15.10.2024 duerfen Shorts bis zu 3 Minuten lang sein, davor 60 s.
SHORTS_3MIN_SINCE = "2024-10-15"


# ─────────────────────────────────────────────
# Quota-Behandlung
# ─────────────────────────────────────────────
class QuotaExceeded(Exception):
    """Quota-Fehler der Data API (echt oder per SIMULATE_QUOTA_AFTER_CALLS)."""


_api_calls = 0


def _is_quota_error(e: Exception) -> bool:
    text = str(e).lower()
    return "quota" in text or "dailylimitexceeded" in text


def _tick() -> None:
    """Zaehlt einen API-Aufruf und simuliert ggf. einen Quota-Fehler."""
    global _api_calls
    if SIMULATE_QUOTA_AFTER_CALLS is not None and _api_calls >= SIMULATE_QUOTA_AFTER_CALLS:
        raise QuotaExceeded(f"simulierter Quota-Fehler nach {_api_calls} Aufrufen")
    _api_calls += 1


def _execute(request):
    _tick()
    try:
        return request.execute()
    except HttpError as e:
        if _is_quota_error(e):
            raise QuotaExceeded(str(e)) from e
        raise


def _fetch_records(video_ids) -> list[dict]:
    """fetch_video_metadata_records() mit Aufrufzaehlung und Quota-Erkennung."""
    records = []
    for batch in chunk_list(list(video_ids), 50):
        _tick()
        try:
            records.extend(fetch_video_metadata_records(batch, YOUTUBE, detailed=True))
        except HttpError as e:
            if _is_quota_error(e):
                raise QuotaExceeded(str(e)) from e
            raise
    return records


# ─────────────────────────────────────────────
# Kanalliste / Status
# ─────────────────────────────────────────────
def load_channel_ids(path) -> list[str]:
    """CSV mit "channel_id"-Spalte oder JSON-Liste (IDs oder Dicts); dedupliziert,
    Reihenfolge bleibt erhalten (gleiche Logik wie load_targeted_channel_ids()
    in channel_all_videos.py)."""
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
        raise ValueError(f"Nicht unterstuetztes Format fuer CHANNEL_INPUT: {path}")
    return list(dict.fromkeys(ids))


_STATUS_FIELDS = [
    "zeitpunkt", "channel_id", "status",
    "n_short", "n_long", "n_live",
    "abgeschnitten", "fallback", "n_neu", "n_nicht_abrufbar", "n_konflikte",
    "n_api_aufrufe", "fenster_von", "fenster_bis", "detail",
]


def append_status(row: dict) -> None:
    neu_anlegen = not os.path.exists(STATUS_FILE)
    with open(STATUS_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_STATUS_FIELDS)
        if neu_anlegen:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in _STATUS_FIELDS})


def load_completed_channels() -> set[str]:
    """Kanaele, die laut Statusdatei fuer GENAU dieses Fenster komplett sind
    (ein spaeterer Eintrag ueberschreibt einen frueheren)."""
    if not os.path.exists(STATUS_FILE):
        return set()
    letzter: dict[str, str] = {}
    with open(STATUS_FILE, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row["fenster_von"] == PUBLISHED_AFTER and row["fenster_bis"] == PUBLISHED_BEFORE:
                letzter[row["channel_id"]] = row["status"]
    return {cid for cid, s in letzter.items() if s == "komplett"}


# ─────────────────────────────────────────────
# Abfrage
# ─────────────────────────────────────────────
def format_playlist_id(channel_id: str, prefix: str) -> str:
    """UC<rest> -> <prefix><rest>, z.B. UUSH<rest> fuer die Shorts-Playlist."""
    if not channel_id.startswith("UC"):
        raise ValueError(f"Unerwartete Channel-ID {channel_id!r} (erwartet 'UC...')")
    return prefix + channel_id[2:]


def fetch_playlist_window(playlist_id: str) -> dict:
    """
    Liest eine Format-Playlist per playlistItems.list bis zum Fensteranfang.
    Gibt {"items": {video_id: published_at}, "n_read", "total_results",
    "reached_start", "truncated", "missing"} zurueck.
    """
    items: dict[str, str] = {}
    n_read = 0
    total_results = None
    reached_start = False
    next_page = None

    while True:
        try:
            resp = _execute(YOUTUBE.playlistItems().list(
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page,
            ))
        except HttpError as e:
            if e.resp.status == 404:
                return {"items": {}, "n_read": 0, "total_results": 0,
                        "reached_start": True, "truncated": False, "missing": True}
            raise

        if total_results is None:
            total_results = (resp.get("pageInfo") or {}).get("totalResults")

        page_dates = []
        for item in resp.get("items", []):
            n_read += 1
            cd = item.get("contentDetails", {})
            vid = cd.get("videoId")
            pub = cd.get("videoPublishedAt")  # fehlt bei privaten/geloeschten Videos
            if not vid or not pub:
                continue
            page_dates.append(pub)
            if PUBLISHED_AFTER <= pub <= PUBLISHED_BEFORE:
                items[vid] = pub

        if page_dates and max(page_dates) < PUBLISHED_AFTER:
            reached_start = True
            break
        next_page = resp.get("nextPageToken")
        if not next_page:
            break

    # Ob die Playlist abgeschnitten ist, laesst sich hier nicht erkennen
    # (totalResults meldet bereits die gekappte Zahl) - das entscheidet
    # process_channel() ueber uploads_total() des Kanals.
    return {"items": items, "n_read": n_read, "total_results": total_results,
            "reached_start": reached_start, "missing": False}


def uploads_total(channel_id: str) -> int:
    """
    pageInfo.totalResults der normalen Upload-Playlist (UU<rest>), 1 Quota-
    Einheit. Das ist NICHT die echte Videozahl, sondern hoechstens ~20.000:
    YouTube haelt nur die neuesten ~20.000 Uploads abrufbar, und die
    Format-Playlists UULF/UUSH/UULV sind gefilterte Ansichten genau dieses
    gekappten Bestands (verifiziert 2026-10-06 an tagesschau: UU = 20.000 bei
    36.785 Videos laut channels.list; UULF + UUSH + UULV = 14.901 + 3.963 +
    1.137, alle drei enden am 08./10.07.2022).
    """
    resp = _execute(YOUTUBE.playlistItems().list(
        part="id", playlistId=format_playlist_id(channel_id, "UU"), maxResults=1,
    ))
    return (resp.get("pageInfo") or {}).get("totalResults") or 0


def fetch_tab_window_ytdlp(channel_id: str, tab: str, known_pub: dict[str, str]) -> tuple[dict, list]:
    """
    yt-dlp-Fallback: blaettert den Kanal-Tab in 50er-Bloecken (neueste zuerst,
    iter_channel_video_id_batches) und bestimmt published_at aus der Registry
    (known_pub) bzw. per videos.list (detailed) fuer unbekannte IDs. Sobald
    YTDLP_EARLY_STOP_BATCHES aufeinanderfolgende Bloecke komplett vor
    PUBLISHED_AFTER liegen, wird abgebrochen - die aelteren Tab-Seiten werden
    dann gar nicht mehr abgerufen.
    Gibt ({video_id: published_at} im Fenster, [Metadaten-Records neuer
    Videos im Fenster]) zurueck.
    """
    items: dict[str, str] = {}
    new_records: list[dict] = []
    alte_batches = 0
    n_ids = n_bekannt = 0
    stopp = False
    for batch in iter_channel_video_id_batches(channel_id, tab=tab):
        n_ids += len(batch)
        daten = []
        for v in batch:
            if v in known_pub:
                n_bekannt += 1
                daten.append(known_pub[v])
                if PUBLISHED_AFTER <= known_pub[v] <= PUBLISHED_BEFORE:
                    items[v] = known_pub[v]
        unbekannt = [v for v in batch if v not in known_pub]
        if unbekannt:
            for rec in _fetch_records(unbekannt):
                pub = rec.get("published_at")
                if not pub:
                    continue
                daten.append(pub)
                if PUBLISHED_AFTER <= pub <= PUBLISHED_BEFORE:
                    items[rec["video_id"]] = pub
                    new_records.append(rec)

        if daten and max(daten) < PUBLISHED_AFTER:
            alte_batches += 1
            if alte_batches >= YTDLP_EARLY_STOP_BATCHES:
                stopp = True
                break
        else:
            alte_batches = 0
    print(f"    yt-dlp /{tab}: {n_ids} IDs gelesen, davon {n_bekannt} bereits bekannt"
          f" -> {'Fensteranfang erreicht, Stopp' if stopp else 'Tab-Ende erreicht'}")
    return items, new_records


def process_channel(channel_id: str, known_ids: set[str]) -> dict:
    """
    Fragt alle Formate eines Kanals ab und gibt das komplette Ergebnis zurueck,
    ohne etwas zu schreiben. Wirft QuotaExceeded bei einem Quota-Fehler.
    """
    observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    known_rows = video_registry.get_video_rows_for_channels([channel_id])
    known_pub = {
        vid: pub for vid, pub in zip(known_rows["video_id"], known_rows["published_at"])
        if isinstance(pub, str) and pub[:1].isdigit()
    }

    assigned: dict[str, dict] = {}   # video_id -> {"format", "source", "published_at"}
    new_records: dict[str, dict] = {}
    truncated, fallback = [], []
    n_conflicts = 0

    # Gekappter Kanal: die Upload-Liste (und damit alle drei Format-Playlists)
    # reicht nur ~20.000 Uploads zurueck. Dann ist jede Format-Playlist, die
    # den Fensteranfang nicht erreicht, abgeschnitten - auch wenn
    # totalResults == gelesene Eintraege.
    n_uploads = uploads_total(channel_id)
    capped = n_uploads >= UPLOADS_CAP_THRESHOLD
    print(f"  UU (alle Uploads): totalResults {n_uploads}"
          + (" -> gekappt, Format-Playlists reichen evtl. nicht bis zum Fensteranfang" if capped else ""))

    for fmt, (prefix, tab) in FORMAT_SOURCES.items():
        playlist_id = format_playlist_id(channel_id, prefix)
        res = fetch_playlist_window(playlist_id)
        found = {vid: (pub, f"api_{prefix}") for vid, pub in res["items"].items()}
        info = ("fehlt (404)" if res["missing"] else
                f"{len(res['items'])} im Fenster, {res['n_read']}/{res['total_results']} gelesen"
                + (", Fensteranfang erreicht" if res["reached_start"] else ""))
        print(f"  {prefix} ({fmt}): {info}")

        if capped and not res["reached_start"]:
            truncated.append(fmt)
            print(f"    -> abgeschnitten, yt-dlp-Fallback ueber /{tab}")
            # Bereits per API gefundene IDs nicht erneut per videos.list nachschlagen
            tab_items, tab_records = fetch_tab_window_ytdlp(
                channel_id, tab, {**known_pub, **res["items"]})
            fallback.append(fmt)
            for vid, pub in tab_items.items():
                found.setdefault(vid, (pub, f"ytdlp_{tab}"))
            for rec in tab_records:
                new_records[rec["video_id"]] = rec

        for vid, (pub, source) in found.items():
            if vid in assigned and assigned[vid]["format"] != fmt:
                n_conflicts += 1
            assigned[vid] = {"format": fmt, "source": source, "published_at": pub}

    # Neue Videos: nicht in der Registry und noch nicht ueber yt-dlp abgefragt
    new_records = {v: r for v, r in new_records.items() if v in assigned and v not in known_ids}
    to_fetch = [v for v in assigned if v not in known_ids and v not in new_records]
    if to_fetch:
        print(f"  Metadaten fuer {len(to_fetch)} neue Videos abfragen ...")
        for rec in _fetch_records(to_fetch):
            new_records[rec["video_id"]] = rec

    # Format nur fuer Videos schreiben, die danach auch in videos stehen.
    # published_at wird nicht gespeichert (steht in videos), nur fuer den Report genutzt.
    nicht_abrufbar = {v for v in assigned if v not in known_ids and v not in new_records}
    formats = [
        {"video_id": vid, "channel_id": channel_id, "format": a["format"],
         "source": a["source"], "observed_at": observed_at, "published_at": a["published_at"]}
        for vid, a in assigned.items() if vid not in nicht_abrufbar
    ]

    in_window_known = {v for v, p in known_pub.items() if PUBLISHED_AFTER <= p <= PUBLISHED_BEFORE}
    counts = Counter(f["format"] for f in formats)
    new_counts = Counter(assigned[v]["format"] for v in new_records)
    return {
        "channel_id": channel_id,
        "formats": formats,
        "new_records": list(new_records.values()),
        "counts": counts,
        "new_counts": new_counts,
        "truncated": truncated,
        "fallback": fallback,
        "n_conflicts": n_conflicts,
        "n_nicht_abrufbar": len(nicht_abrufbar),
        "n_registry_ohne_format": len(in_window_known - set(assigned)),
        "n_registry_im_fenster": len(in_window_known),
    }


# ─────────────────────────────────────────────
# Validierung / Report
# ─────────────────────────────────────────────
def head_check(video_id: str) -> str:
    """'short' | 'kein_short' | 'unklar' laut https://www.youtube.com/shorts/<id>."""
    try:
        r = requests.head(
            f"https://www.youtube.com/shorts/{video_id}",
            allow_redirects=False,
            cookies={"SOCS": "CAI", "CONSENT": "YES+"},
            timeout=10,
        )
    except requests.RequestException:
        return "unklar"
    if r.status_code == 200:
        return "short"
    if r.status_code in (301, 302, 303, 307, 308) and "/watch" in r.headers.get("Location", ""):
        return "kein_short"
    return "unklar"


def run_head_check(results: list[dict]) -> dict:
    formats = [f for res in results for f in res["formats"]]
    shorts = [f for f in formats if f["format"] == "short"]
    others = [f for f in formats if f["format"] != "short"]
    rng = random.Random(42)
    half = HEAD_CHECK_SAMPLE // 2
    sample = rng.sample(shorts, min(half, len(shorts))) + rng.sample(others, min(half, len(others)))

    tab = Counter()
    abweichungen = []
    for f in sample:
        erwartet = "short" if f["format"] == "short" else "kein_short"
        ergebnis = head_check(f["video_id"])
        tab[(f["format"], ergebnis)] += 1
        if ergebnis != "unklar" and ergebnis != erwartet:
            abweichungen.append((f["video_id"], f["format"], ergebnis))
        time.sleep(0.3)
    eindeutig = sum(n for (_, e), n in tab.items() if e != "unklar")
    return {"n": len(sample), "tab": tab, "abweichungen": abweichungen,
            "uebereinstimmung": (eindeutig - len(abweichungen)) / eindeutig if eindeutig else None}


def duration_check(results: list[dict]) -> dict:
    """Shorts laenger als erlaubt (60 s bis 14.10.2024, danach 180 s) und
    normale Videos <= 60 s - nur zur Plausibilisierung."""
    formats = [f for res in results for f in res["formats"]]
    dur = video_registry.duration_lookup([f["video_id"] for f in formats])
    # Bei DRY_RUN stehen neue Videos nicht in der Registry -> Dauer aus den Records
    dur.update({r["video_id"]: video_registry.duration_to_seconds(r.get("duration"))
                for res in results for r in res["new_records"]})
    out = Counter()
    for f in formats:
        sec = dur.get(f["video_id"])
        if sec is None:
            out["ohne_dauer"] += 1
            continue
        if f["format"] == "short":
            limit = 180 if f["published_at"] >= SHORTS_3MIN_SINCE else 60
            if sec > limit + 1:
                out["short_zu_lang"] += 1
        elif f["format"] == "long" and sec <= 60:
            out["long_max_60s"] += 1
    return out


def write_report(channel_ids, results, aborted, head, durations) -> str:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stem = os.path.basename(str(CHANNEL_INPUT)).rsplit(".", 1)[0]
    path = REPORT_DIR / f"{stem}_formats_report{'_dryrun' if DRY_RUN else ''}.md"
    titles = {}
    ch = video_registry.get_channels(channel_ids)
    if len(ch):
        titles = dict(zip(ch["channel_id"], ch["title"]))

    lines = [
        f"# Video-Formate: {stem}",
        "",
        f"- Lauf: {datetime.now().isoformat(timespec='seconds')}"
        f"{' (DRY_RUN - nichts gespeichert)' if DRY_RUN else ''}",
        f"- Kanalliste: `{CHANNEL_INPUT}` ({len(channel_ids)} Kanaele)",
        f"- Fenster: {PUBLISHED_AFTER} bis {PUBLISHED_BEFORE}",
        f"- API-Aufrufe in diesem Lauf: {_api_calls}",
        f"- Abgebrochen: {aborted or 'nein'}",
        "",
        "## Formate je Kanal (dieser Lauf)",
        "",
        "| Kanal | short | long | live | davon neu (s/l/live) | abgeschnitten -> yt-dlp | Konflikte "
        "| nicht abrufbar | Registry im Fenster | Registry ohne Format |",
        "| --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for res in results:
        c, n = res["counts"], res["new_counts"]
        lines.append(
            f"| {titles.get(res['channel_id'], res['channel_id'])} | {c['short']} | {c['long']} | {c['live']} "
            f"| {n['short']}/{n['long']}/{n['live']} | {', '.join(res['fallback']) or '-'} "
            f"| {res['n_conflicts']} | {res['n_nicht_abrufbar']} | {res['n_registry_im_fenster']} "
            f"| {res['n_registry_ohne_format']} |"
        )
    lines += [
        "",
        "*Registry ohne Format*: Videos, die schon vor dem Lauf in der Registry im Fenster lagen, "
        "aber in keiner Format-Playlist auftauchen (geloescht/privat oder Abdeckungsluecke). "
        "*nicht abrufbar*: in der Playlist gelistet, aber per videos.list nicht (mehr) abrufbar - "
        "kein Format gespeichert.",
        "",
        "## Dauer-Plausibilitaet",
        "",
        f"- Shorts laenger als erlaubt (60 s bis 14.10.2024, danach 180 s): {durations['short_zu_lang']}",
        f"- Normale Videos <= 60 s: {durations['long_max_60s']}",
        f"- Ohne Dauer: {durations['ohne_dauer']}",
        "",
        "## HEAD-Validierung (/shorts/<id>)",
        "",
    ]
    if head is None:
        lines.append("Nicht durchgefuehrt (HEAD_CHECK_SAMPLE = 0 oder keine Ergebnisse).")
    else:
        quote = f"{head['uebereinstimmung']:.1%}" if head["uebereinstimmung"] is not None else "n/a"
        lines += [f"Stichprobe: {head['n']} Videos, Uebereinstimmung (ohne 'unklar'): {quote}", "",
                  "| Playlist-Format | HEAD-Ergebnis | n |", "| --- | --- | ---: |"]
        lines += [f"| {f} | {e} | {n} |" for (f, e), n in sorted(head["tab"].items())]
        if head["abweichungen"]:
            lines += ["", "Abweichungen:", ""]
            lines += [f"- `{v}`: Playlist {f}, HEAD {e}" for v, f, e in head["abweichungen"]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
if __name__ == "__main__":
    channel_ids = load_channel_ids(CHANNEL_INPUT)
    completed = set() if DRY_RUN else load_completed_channels()
    todo = [c for c in channel_ids if c not in completed]
    print(f"Kanaele in Liste: {len(channel_ids)}, bereits komplett: {len(completed & set(channel_ids))}, "
          f"zu bearbeiten: {len(todo)}{'  [DRY_RUN]' if DRY_RUN else ''}")

    if not DRY_RUN:
        # Kanal-Metadaten nur fuer noch unbekannte Kanaele (Kanal-Ebene,
        # unabhaengig von der Alles-oder-nichts-Logik pro Kanal).
        get_channel_metadata(todo, YOUTUBE)

    known_ids = video_registry.known_video_ids()
    results: list[dict] = []
    aborted = None

    for i, cid in enumerate(todo, start=1):
        print(f"\n[{i}/{len(todo)}] {cid}")
        calls_before = _api_calls
        try:
            res = process_channel(cid, known_ids)
        except QuotaExceeded as e:
            aborted = f"Quota bei {cid}: {e}"
            print(f"  QUOTA-ABBRUCH - Kanal verworfen, nichts gespeichert. Folgelauf fragt ihn neu ab.")
            if not DRY_RUN:
                append_status({"zeitpunkt": datetime.now().isoformat(timespec="seconds"),
                               "channel_id": cid, "status": "abgebrochen_quota",
                               "n_api_aufrufe": _api_calls - calls_before,
                               "fenster_von": PUBLISHED_AFTER, "fenster_bis": PUBLISHED_BEFORE,
                               "detail": str(e)[:200]})
            break
        except Exception as e:
            print(f"  FEHLER: {e} - Kanal uebersprungen")
            if not DRY_RUN:
                append_status({"zeitpunkt": datetime.now().isoformat(timespec="seconds"),
                               "channel_id": cid, "status": "fehler",
                               "n_api_aufrufe": _api_calls - calls_before,
                               "fenster_von": PUBLISHED_AFTER, "fenster_bis": PUBLISHED_BEFORE,
                               "detail": str(e)[:200]})
            continue

        results.append(res)
        c = res["counts"]
        print(f"  -> short {c['short']}, long {c['long']}, live {c['live']}, "
              f"neu {len(res['new_records'])}, Konflikte {res['n_conflicts']}")

        if not DRY_RUN:
            n_v, n_d, n_f = video_registry.write_channel_format_result(
                res["new_records"], res["new_records"], res["formats"])
            known_ids.update(r["video_id"] for r in res["new_records"])
            print(f"  gespeichert: {n_v} neue Videos, {n_f} Format-Zeilen")
            append_status({
                "zeitpunkt": datetime.now().isoformat(timespec="seconds"),
                "channel_id": cid, "status": "komplett",
                "n_short": c["short"], "n_long": c["long"], "n_live": c["live"],
                "abgeschnitten": ",".join(res["truncated"]), "fallback": ",".join(res["fallback"]),
                "n_neu": len(res["new_records"]), "n_nicht_abrufbar": res["n_nicht_abrufbar"],
                "n_konflikte": res["n_conflicts"], "n_api_aufrufe": _api_calls - calls_before,
                "fenster_von": PUBLISHED_AFTER, "fenster_bis": PUBLISHED_BEFORE,
            })

    head = run_head_check(results) if (HEAD_CHECK_SAMPLE and results) else None
    durations = duration_check(results)
    report = write_report(channel_ids, results, aborted, head, durations)
    print(f"\nAPI-Aufrufe: {_api_calls}. Report: {report}")
    if aborted:
        print(f"Abgebrochen: {aborted}")

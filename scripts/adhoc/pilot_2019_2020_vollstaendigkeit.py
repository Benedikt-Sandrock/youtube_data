# -*- coding: utf-8 -*-
"""
pilot_2019_2020_vollstaendigkeit.py

Vollstaendigkeitstest fuer die Erweiterung auf 2019-2020 (Plan:
.claude/plans/datenbasis_2019_2020.md, Schritt 1.2). Fuer jeden Pilotkanal
wird die Upload-Playlist UU<rest> im Fenster per playlistItems gezaehlt und
mit der Vereinigung der Format-Playlists UULF/UUSH/UULV verglichen. Es wird
nichts gespeichert ausser dem Markdown-Report.

Die Funktionen bilden channel_all_videos.get_channel_videos() nach, importieren
das Modul aber nicht (der Import baut einen API-Client und laedt Dateien).
Kanaele mit gekappter UU-Playlist (>= UU_CAP Eintraege) werden uebersprungen:
dort ist UU nicht vollstaendig und der yt-dlp-Pfad ist zu bewerten.

Ausfuehren aus dem Repo-Root:
    PYTHONPATH=src .venv/Scripts/python.exe scripts/adhoc/pilot_2019_2020_vollstaendigkeit.py
"""

import time
from datetime import datetime

import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from youtube_code.config import API_KEY, CHANNEL_LISTS, OUTPUTS

# =========================================================
# KONFIGURATION
# =========================================================
# Kanalliste (Spalte channel_id; Fenster aus fenster_von/fenster_bis)
KANALLISTE = CHANNEL_LISTS / "video_formats" / "pilot_2019_2020.csv"
# Ab so vielen Eintraegen in UU gilt die Playlist als gekappt -> Kanal wird uebersprungen
UU_CAP = 19_500
# Report-Ausgabe
AUSGABE = OUTPUTS / "video_formats" / "pilot_2019_2020_vollstaendigkeit.md"
# Maximale Zahl ausgegebener Beispiel-IDs pro Differenzmenge
MAX_BEISPIELE = 10


def lese_fenster(youtube, playlist_id, von, bis):
    """Liest eine Playlist bis zum Fensteranfang. Gibt (dict id->pub, totalResults, missing) zurueck."""
    items, total, token = {}, None, None
    while True:
        try:
            resp = youtube.playlistItems().list(
                part="contentDetails", playlistId=playlist_id, maxResults=50, pageToken=token
            ).execute()
        except HttpError as e:
            if e.resp.status == 404:
                return {}, 0, True
            raise
        if total is None:
            total = (resp.get("pageInfo") or {}).get("totalResults")
        daten = []
        for it in resp.get("items", []):
            cd = it.get("contentDetails", {})
            vid, pub = cd.get("videoId"), cd.get("videoPublishedAt")
            if not vid or not pub:
                continue
            daten.append(pub)
            if von <= pub <= bis:
                items[vid] = pub
        if daten and max(daten) < von:
            break
        token = resp.get("nextPageToken")
        if not token:
            break
        time.sleep(0.05)
    return items, total, False


def main():
    if not KANALLISTE.exists():
        raise SystemExit(f"Kanalliste fehlt: {KANALLISTE}")
    liste = pd.read_csv(KANALLISTE)
    for sp in ("channel_id", "fenster_von", "fenster_bis"):
        if sp not in liste.columns:
            raise SystemExit(f"Spalte {sp!r} fehlt in {KANALLISTE}")
    youtube = build("youtube", "v3", developerKey=API_KEY)

    zeilen, beispiele = [], []
    for _, r in liste.iterrows():
        cid, von, bis = r["channel_id"], r["fenster_von"], r["fenster_bis"]
        name = r.get("channel_title", cid)
        uu, uu_total, _ = lese_fenster(youtube, "UU" + cid[2:], von, bis)
        if uu_total is not None and uu_total >= UU_CAP:
            zeilen.append((name, None, None, None, None, f"UU gekappt ({uu_total}) - uebersprungen"))
            continue
        fmt = {}
        for praefix in ("UULF", "UUSH", "UULV"):
            d, _, _ = lese_fenster(youtube, praefix + cid[2:], von, bis)
            fmt.update(d)
        nur_uu = sorted(set(uu) - set(fmt))
        nur_fmt = sorted(set(fmt) - set(uu))
        quote = 100 * len(nur_uu) / len(uu) if uu else 0.0
        zeilen.append((name, len(uu), len(fmt), len(nur_uu), len(nur_fmt), f"{quote:.2f} % Verlust"))
        if nur_uu:
            beispiele.append((name, "nur in UU", nur_uu[:MAX_BEISPIELE]))
        if nur_fmt:
            beispiele.append((name, "nur in Format-Playlists", nur_fmt[:MAX_BEISPIELE]))
        print(f"{name}: UU {len(uu)}, Formate {len(fmt)}, nur UU {len(nur_uu)}, nur Formate {len(nur_fmt)}")

    out = [
        "# Pilot 2019-2020: Vollstaendigkeit Format-Playlists vs. UU",
        "",
        f"- Lauf: {datetime.now().isoformat(timespec='seconds')}",
        f"- Kanalliste: `{KANALLISTE}`",
        "",
        "| Kanal | UU im Fenster | UULF+UUSH+UULV | nur UU | nur Format | Bewertung |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for name, a, b, c, d, bew in zeilen:
        out.append(f"| {name} | {a if a is not None else '-'} | {b if b is not None else '-'} | "
                   f"{c if c is not None else '-'} | {d if d is not None else '-'} | {bew} |")
    if beispiele:
        out += ["", "## Beispiel-IDs der Differenzen", ""]
        for name, art, ids in beispiele:
            out.append(f"- {name} ({art}): " + ", ".join(f"`{i}`" for i in ids))
    AUSGABE.parent.mkdir(parents=True, exist_ok=True)
    AUSGABE.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Report: {AUSGABE}")


if __name__ == "__main__":
    main()

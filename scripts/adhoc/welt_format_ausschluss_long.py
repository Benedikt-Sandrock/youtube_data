"""Ad-hoc: WELT-Videos ohne Format im Zeitraum per Ausschluss als "long" in den Store.

Hintergrund (Pruefung 04.11.2026): Fuer WELT Nachrichtensender laesst sich das
Format der Videos ab Mai 2022 nicht nachscrapen - der yt-dlp-Tab /videos
endet zu frueh (Quelle ytdlp_videos reicht nur bis 30.04.2022, api_UULF erst
ab 07/2025; siehe step1_sample/README.md). Shorts und Livestreams sind fuer
2022 aber vollstaendig:
  - Livestreams: ytdlp_streams lueckenlos 2019-01 bis 2025-07, 2022 jeden Monat
    47-86 Streams (gleiches Niveau wie im vollstaendigen Jan-Apr 2022); 98 %
    der bekannten Streams haben "live" im Titel, von den formatlosen Videos
    nur eines (als normales Wort).
  - Shorts: api_UUSH reicht bis 05.01.2021 zurueck; 2022 hatten Shorts max.
    60 s, nur 39 von 4.175 formatlosen Videos (Zeitraum 2022-01-01 bis
    2022-10-26) sind so kurz und sehen nach normalen Nachrichtenclips aus.
  - Summe je Monat (ohne Format + live + short) liegt Mai-Okt 2022 auf dem
    Niveau von Jan-Apr 2022 (long + live + short).
Daher gelten alle Videos des Kanals im Zeitraum, die in video_format noch
GAR KEINE Zeile haben, als long (auch die <= 60 s, Entscheidung 04.11.2026).

Geschrieben wird in video_format (data/store/video_registry.sqlite) mit
source = SOURCE ("ausschluss_long"), damit die Zuordnung erkennbar bleibt.
Bestehende Zeilen werden nie ueberschrieben. Rueckgaengig machen:
    DELETE FROM video_format WHERE source = 'ausschluss_long'

Export: export_stata_rohdaten.py setzt fuer WELT ohnehin alle Videos ohne
Format im FORMAT_FENSTER per Ausschluss auf long (FORMAT_AUSSCHLUSS_LONG) und
zaehlt Zeilen mit format_quelle == "ausschluss_long" ebenfalls als
format_derived = 1 - format/format_derived im Export aendern sich durch
dieses Skript also nicht, nur format_quelle ist fuer diese Videos jetzt
gesetzt.

Zeitraum: Datum in Ortszeit (ZEITZONE), wie in
random_video_ids_for_channel_period.py.
"""

import sys
from datetime import datetime, timezone

import pandas as pd

from youtube_code.store.video_registry import (get_video_formats, get_video_rows_for_channels,
                                               upsert_video_formats)

# ============================================================================
# KONFIGURATION
# ============================================================================

CHANNEL_IDS = ["UCZMsvbAhhRblVGXmEXW8TSA"]   # Kanaele, fuer die die Ausschluss-Regel geprueft ist
                                             # (bisher nur WELT Nachrichtensender)
START = "2022-01-01"                         # erster Tag (inkl.), JJJJ-MM-TT, Ortszeit
ENDE = "2022-10-26"                          # letzter Tag (inkl.), JJJJ-MM-TT, Ortszeit
ZEITZONE = "Europe/Berlin"                   # Zeitzone fuer die Tagesgrenzen
SOURCE = "ausschluss_long"                   # Wert fuer video_format.source (nicht aendern,
                                             # export_stata_rohdaten.py erkennt ihn)
DRY_RUN = False                              # True = nur zaehlen, nichts schreiben


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    try:
        start, ende = pd.Timestamp(START), pd.Timestamp(ENDE)
    except ValueError as e:
        sys.exit(f"START/ENDE muessen Datumsangaben 'JJJJ-MM-TT' sein: {e}")
    if ende < start:
        sys.exit("ENDE liegt vor START.")
    if not CHANNEL_IDS or not all(isinstance(c, str) and c.startswith("UC") for c in CHANNEL_IDS):
        sys.exit("CHANNEL_IDS muss eine nicht-leere Liste von Channel-IDs (UC...) sein.")
    if not isinstance(DRY_RUN, bool):
        sys.exit("DRY_RUN muss True oder False sein.")

    v = get_video_rows_for_channels(CHANNEL_IDS)
    v["datum"] = (pd.to_datetime(v["published_at"], utc=True, format="mixed")
                  .dt.tz_convert(ZEITZONE).dt.tz_localize(None).dt.normalize())
    v = v[(v["datum"] >= start) & (v["datum"] <= ende)]
    vorhanden = set(get_video_formats(CHANNEL_IDS)["video_id"])
    ohne = v[~v["video_id"].isin(vorhanden)]

    print(f"[Daten] {len(v):,} Videos im Zeitraum {START} bis {ENDE}, davon {len(ohne):,} ohne Format")
    print(ohne.groupby(ohne["datum"].dt.strftime("%Y-%m")).size().to_string())

    if DRY_RUN or ohne.empty:
        print("[Store] DRY_RUN - nichts geschrieben." if DRY_RUN else "[Store] Nichts zu tun.")
        return
    jetzt = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    n = upsert_video_formats([{"video_id": r.video_id, "channel_id": r.channel_id, "format": "long",
                               "source": SOURCE, "observed_at": jetzt} for r in ohne.itertuples()])
    print(f"[Store] {n:,} Zeilen in video_format geschrieben (format = long, source = {SOURCE})")


if __name__ == "__main__":
    main()

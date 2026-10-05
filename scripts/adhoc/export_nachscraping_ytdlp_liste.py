# -*- coding: utf-8 -*-
"""
export_nachscraping_ytdlp_liste.py

Leitet aus dem Datenluecken-Screening (`videos_pro_quartal_whitelist.py` ->
`outputs/segment_analysis/datenluecken_quartale/auffaelligkeiten.csv`) die
Kanalliste fuer ein Nachscraping mit
`src/youtube_code/step1_sample/channel_all_videos.py` im Modus
TARGETED_SEARCH_YTDLP ab.

Aufgenommen werden
  - alle Kanaele mit Flag `playlist_limit` (Registry ~20.000 Videos, API
    deutlich mehr -> Uploads-Playlist-Limit), sowie
  - alle Kanaele, deren geschaetzt fehlende Videos aus `einbruch`/
    `null_luecke`/`anhaltende_luecke` in Summe >= MIN_GESCHAETZT_FEHLEND sind
    (kleinere Einbrueche sind ueberwiegend echte Upload-Pausen, siehe README
    des Screenings).

channel_all_videos.py liest nur die Spalte `channel_id`; die uebrigen Spalten
dienen der Nachvollziehbarkeit. Sortierung nach Prioritaet (geschaetzt
fehlend absteigend), damit bei einem Quota-Abbruch die wichtigsten Kanaele
schon durch sind.

Ausgeschlossen werden Kanaele, die schon nachgescrapt wurden: ERLEDIGT
(Testlauf WELT/OE24) sowie alle Kanaele mit Status `komplett` in einer
Statusdatei `nachscraping_ytdlp_kanaele_teil*_status.csv` (von
channel_all_videos.py geschrieben). Jeder Aufruf schreibt genau eine neue
Portion TEIL; fruehere Teil-Dateien bleiben unveraendert.

Historie:
  - Teil 1 (MIN_GESCHAETZT_FEHLEND = 500, 12 Kanaele, alle playlist_limit-
    Kanaele): +16.695 Videos, 541 Quota-Einheiten, siehe
    nachscraping_vergleich_nachscraping_ytdlp_kanaele_teil1.md. Damals noch
    mit Quota-Aufteilung auf Tagesportionen und Uebersicht
    nachscraping_ytdlp_kanaele.csv (seitdem nicht mehr geschrieben).
  - Teil 2: Schwelle auf 100 gesenkt, weil channel_all_videos.py bekannte IDs
    nicht mehr nachschlaegt und am Fensteranfang stoppt (Kosten ~ neue
    Videos / 50 + Overhead). In Teil 1 brachten die reinen Luecken-Kanaele
    (exxpressTV, FPOE TV, NuoViso, VOL.AT) aber praktisch nichts -> die
    kleineren Luecken sind ueberwiegend echte Upload-Pausen, Ertrag
    entsprechend unsicher.

`geschaetzte_quota` = ceil(geschaetzt_fehlend / 50) + QUOTA_OVERHEAD (grobe
Schaetzung; in Teil 1 kosteten Kanaele ohne neue Videos 1-17 Einheiten).

Ausgabe (outputs/segment_analysis/datenluecken_quartale/):
  - nachscraping_ytdlp_kanaele_teil<TEIL>.csv  (direkt als
                                               TARGETED_SEARCH_YTDLP_CHANNEL_INPUT)

    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        scripts/adhoc/export_nachscraping_ytdlp_liste.py
"""
import math
import sqlite3

import pandas as pd

from youtube_code.config import OUTPUTS, STORE

ORDNER = OUTPUTS / "segment_analysis" / "datenluecken_quartale"
PFAD_FLAGS = ORDNER / "auffaelligkeiten.csv"

TEIL = 2
PFAD_AUSGABE = ORDNER / f"nachscraping_ytdlp_kanaele_teil{TEIL}.csv"
# Teil 1: 500; ab Teil 2: 100 (siehe Docstring)
MIN_GESCHAETZT_FEHLEND = 100
QUOTA_OVERHEAD = 20
# Bereits nachgescrapt (Testlauf mit nachscraping_ytdlp_test.csv, Ergebnis in
# nachscraping_vergleich.md: WELT +24.850, OE24 +10.449 Videos, Luecken gefuellt).
ERLEDIGT = {
    "UCZMsvbAhhRblVGXmEXW8TSA",  # WELT Nachrichtensender
    "UCyQpfuhftLvrmjxgEzVH78Q",  # OE24.TV
}
LUECKEN_FLAGS = ["einbruch", "null_luecke", "anhaltende_luecke"]


def lade_komplett_gescrapte():
    """channel_ids mit Status `komplett` aus allen Teil-Statusdateien."""
    ids = set()
    for pfad in ORDNER.glob("nachscraping_ytdlp_kanaele_teil*_status.csv"):
        status = pd.read_csv(pfad)
        letzter = status.sort_values("zeitpunkt").groupby("channel_id").tail(1)
        ids |= set(letzter.loc[letzter["status"] == "komplett", "channel_id"])
    return ids


def main():
    flags = pd.read_csv(PFAD_FLAGS)
    luecken = flags[flags["flag"].isin(LUECKEN_FLAGS)]

    je_kanal = luecken.groupby(["channel_id", "title", "medientyp"]).agg(
        geschaetzt_fehlend=("geschaetzt_fehlend", "sum"),
        luecken_quartale=("quartal", lambda s: ", ".join(sorted(s))),
    ).reset_index()
    limit_ids = set(flags.loc[flags["flag"] == "playlist_limit", "channel_id"])
    je_kanal["playlist_limit"] = je_kanal["channel_id"].isin(limit_ids)

    # playlist_limit-Kanaele ohne eigenes Luecken-Flag trotzdem aufnehmen
    ohne_luecke = flags[(flags["flag"] == "playlist_limit") & ~flags["channel_id"].isin(je_kanal["channel_id"])]
    je_kanal = pd.concat([je_kanal, ohne_luecke[["channel_id", "title", "medientyp"]].assign(
        geschaetzt_fehlend=0, luecken_quartale="", playlist_limit=True)], ignore_index=True)

    auswahl = je_kanal[je_kanal["playlist_limit"] | (je_kanal["geschaetzt_fehlend"] >= MIN_GESCHAETZT_FEHLEND)].copy()
    if PFAD_AUSGABE.exists():
        raise SystemExit(f"{PFAD_AUSGABE.name} existiert schon -> TEIL erhoehen oder Datei bewusst loeschen")
    erledigt = ERLEDIGT | lade_komplett_gescrapte()
    auswahl = auswahl[~auswahl["channel_id"].isin(erledigt)]

    con = sqlite3.connect(f"file:{STORE / 'video_registry.sqlite'}?mode=ro", uri=True)
    try:
        api = pd.read_sql_query("SELECT channel_id, video_count AS api_video_count FROM channels", con)
    finally:
        con.close()
    auswahl = auswahl.merge(api, on="channel_id", how="left")
    auswahl["geschaetzte_quota"] = auswahl["geschaetzt_fehlend"].apply(
        lambda n: math.ceil(n / 50) + QUOTA_OVERHEAD)
    auswahl["grund"] = auswahl.apply(
        lambda r: "+".join(g for g, ok in [("playlist_limit", r["playlist_limit"]),
                                           ("luecke", r["geschaetzt_fehlend"] >= MIN_GESCHAETZT_FEHLEND)] if ok),
        axis=1)
    auswahl = auswahl.sort_values(["geschaetzt_fehlend", "api_video_count"], ascending=[False, True])
    spalten = ["channel_id", "title", "medientyp", "grund", "luecken_quartale", "geschaetzt_fehlend",
               "api_video_count", "geschaetzte_quota"]
    auswahl[spalten].to_csv(PFAD_AUSGABE, index=False, encoding="utf-8")

    with pd.option_context("display.width", 250, "display.max_colwidth", 60):
        print(auswahl[["title", "grund", "geschaetzt_fehlend", "api_video_count", "geschaetzte_quota"]]
              .to_string(index=False))
    print(f"\n{len(auswahl)} Kanaele, geschaetzte Quota gesamt: {auswahl['geschaetzte_quota'].sum():.0f}")
    print(f"-> {PFAD_AUSGABE}")


if __name__ == "__main__":
    main()

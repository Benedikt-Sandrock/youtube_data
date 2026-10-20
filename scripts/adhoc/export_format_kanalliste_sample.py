# -*- coding: utf-8 -*-
"""
export_format_kanalliste_sample.py

Schreibt die Kanalliste fuer einen Lauf von
`src/youtube_code/step1_sample/channel_video_formats.py` ueber das gesamte
Kanal-Sample (ANALYSIS_ID), damit `videos_roh.dta`
(`step6_auswertung/export_stata_rohdaten.py`) fuer alle Kanaele ein Format
(short/long/live) bekommt.

Aufgenommen werden alle Kanaele mit eligible_current_analysis == True aus
data/samples/<ANALYSIS_ID>/channel_sample_provenance.csv, OHNE die Kanaele der
bereits abgefragten Listen (alt_kanaele.csv, upload_starke_kanaele.csv).
Kanaele der Frage-1-Whitelist stehen vorne, danach nach Anzahl Videos in der
Registry aufsteigend - bei einem Quota-Abbruch sind so moeglichst viele
Analysekanaele schon durch. channel_video_formats.py liest nur `channel_id`;
die uebrigen Spalten dienen der Nachvollziehbarkeit.

Ausgabe: data/channel_lists/video_formats/sample_<ANALYSIS_ID>.csv
(Statusdatei des Formatlaufs entsteht daneben als *_formats_status.csv).

Ausfuehren aus dem Repo-Root:
    PYTHONPATH=src .venv/Scripts/python.exe scripts/adhoc/export_format_kanalliste_sample.py
"""

import pandas as pd

from youtube_code.config import CHANNEL_LISTS, OUTPUTS, SAMPLES
from youtube_code.store import video_registry

ANALYSIS_ID = "russia_longitudinal_v1"
FORMAT_LISTEN_DIR = CHANNEL_LISTS / "video_formats"
BEREITS_ABGEFRAGT = ["alt_kanaele.csv", "upload_starke_kanaele.csv"]
WHITELIST_PFAD = OUTPUTS / "segment_analysis" / "frage1_kanal_whitelist.csv"
AUSGABE = FORMAT_LISTEN_DIR / f"sample_{ANALYSIS_ID}.csv"


def main():
    sample = pd.read_csv(SAMPLES / ANALYSIS_ID / "channel_sample_provenance.csv",
                         usecols=["channel_id", "eligible_current_analysis"])
    ids = set(sample.loc[sample["eligible_current_analysis"] == True, "channel_id"].astype(str))
    erledigt = set()
    for datei in BEREITS_ABGEFRAGT:
        erledigt |= set(pd.read_csv(FORMAT_LISTEN_DIR / datei)["channel_id"].astype(str))
    offen = sorted(ids - erledigt)

    whitelist = set(pd.read_csv(WHITELIST_PFAD)["channel_id"].astype(str))
    meta = video_registry.get_channels(offen)[["channel_id", "title"]]
    n_videos = {cid: len(vids) for cid, vids in video_registry.get_videos_for_channels(offen).items()}
    liste = pd.DataFrame({"channel_id": offen}).merge(meta, on="channel_id", how="left")
    liste["n_videos_registry"] = liste["channel_id"].map(n_videos).fillna(0).astype(int)
    liste["whitelist"] = liste["channel_id"].isin(whitelist).astype(int)
    liste = liste.sort_values(["whitelist", "n_videos_registry"], ascending=[False, True])

    liste.to_csv(AUSGABE, index=False, encoding="utf-8")
    print(f"Sample {ANALYSIS_ID}: {len(ids)} Kanaele, bereits abgefragt: {len(ids & erledigt)}, "
          f"neu in Liste: {len(liste)} (davon Whitelist: {int(liste['whitelist'].sum())}, "
          f"Videos in Registry: {int(liste['n_videos_registry'].sum())})")
    print(f"Geschrieben: {AUSGABE}")


if __name__ == "__main__":
    main()

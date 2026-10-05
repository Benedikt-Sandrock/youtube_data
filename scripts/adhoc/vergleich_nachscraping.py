# -*- coding: utf-8 -*-
"""
vergleich_nachscraping.py

Prueft, ob ein Nachscraping-Lauf (channel_all_videos.py, Modus
TARGETED_SEARCH_YTDLP) neue Videos in die Registry gebracht hat.
channel_all_videos.py selbst zeigt das nicht an: "Videos gefunden" und
"In zentrale Registry geschrieben" zaehlen auch bereits bekannte Videos mit
(Upsert).

Zwei Schritte, mit derselben Kanalliste (CSV mit Spalte channel_id):

  1. VOR dem Lauf:   ... vergleich_nachscraping.py vorher
     -> sichert alle bekannten video_ids der Kanaele als Snapshot
  2. NACH dem Lauf:  ... vergleich_nachscraping.py nachher
     -> zaehlt neue video_ids je Kanal x Quartal (vorher/nachher/neu) und
        schreibt das Ergebnis als Markdown-Tabelle

Kanalliste: PFAD_KANALLISTE unten (muss zu TARGETED_SEARCH_YTDLP_CHANNEL_INPUT
in channel_all_videos.py passen). Dateien in
outputs/segment_analysis/datenluecken_quartale/, Suffix = Name der Kanalliste
(ohne Suffix fuer den Testlauf nachscraping_ytdlp_test.csv):
  - nachscraping_snapshot_vorher[_<liste>].csv   (video_id, channel_id, published_at)
  - nachscraping_vergleich[_<liste>].md          (Ergebnis)

    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        scripts/adhoc/vergleich_nachscraping.py vorher|nachher
"""
import sqlite3
import sys

import pandas as pd

from youtube_code.config import OUTPUTS, STORE

ORDNER = OUTPUTS / "segment_analysis" / "datenluecken_quartale"
# Testlauf (WELT + OE24): nachscraping_ytdlp_test.csv -> nachscraping_vergleich.md
# Teil 1: nachscraping_ytdlp_kanaele_teil1.csv (erledigt)
PFAD_KANALLISTE = ORDNER / "nachscraping_ytdlp_kanaele_teil2.csv"
# Snapshot/Ergebnis je Kanalliste getrennt, damit fruehere Laeufe erhalten bleiben.
_SUFFIX = "" if PFAD_KANALLISTE.stem == "nachscraping_ytdlp_test" else f"_{PFAD_KANALLISTE.stem}"
PFAD_SNAPSHOT = ORDNER / f"nachscraping_snapshot_vorher{_SUFFIX}.csv"
PFAD_ERGEBNIS = ORDNER / f"nachscraping_vergleich{_SUFFIX}.md"


def lade_videos(channel_ids):
    platzhalter = ",".join("?" * len(channel_ids))
    con = sqlite3.connect(f"file:{STORE / 'video_registry.sqlite'}?mode=ro", uri=True)
    try:
        return pd.read_sql_query(
            f"SELECT video_id, channel_id, published_at, channel_title FROM videos "
            f"WHERE channel_id IN ({platzhalter})", con, params=channel_ids)
    finally:
        con.close()


def quartal(df):
    return pd.to_datetime(df["published_at"], utc=True, errors="coerce").dt.tz_localize(None).dt.to_period("Q")


def main(schritt):
    kanaele = pd.read_csv(PFAD_KANALLISTE)
    ids = kanaele["channel_id"].astype(str).tolist()
    titel = dict(zip(kanaele["channel_id"], kanaele.get("title", kanaele["channel_id"])))
    aktuell = lade_videos(ids)

    if schritt == "vorher":
        aktuell[["video_id", "channel_id", "published_at"]].to_csv(PFAD_SNAPSHOT, index=False, encoding="utf-8")
        print(f"Snapshot: {len(aktuell)} Videos von {aktuell['channel_id'].nunique()} Kanaelen -> {PFAD_SNAPSHOT}")
        return

    vorher = pd.read_csv(PFAD_SNAPSHOT)
    aktuell["neu"] = ~aktuell["video_id"].isin(set(vorher["video_id"]))
    aktuell["quartal"] = quartal(aktuell)
    aktuell = aktuell[aktuell["quartal"] >= pd.Period("2021Q1", freq="Q")]

    zeilen = ["# Nachscraping-Vergleich (vorher/nachher)", "",
              f"Kanalliste: `{PFAD_KANALLISTE.name}`, Snapshot: `{PFAD_SNAPSHOT.name}`. "
              "Zellen: Videos vorher → nachher (neu).", ""]
    for cid in ids:
        g = aktuell[aktuell["channel_id"] == cid]
        n_neu = int(g["neu"].sum())
        zeilen += [f"## {titel.get(cid, cid)} — {n_neu} neue Videos", "",
                   "| Quartal | vorher | nachher | neu |", "| --- | --- | --- | --- |"]
        tab = g.groupby("quartal").agg(nachher=("video_id", "size"), neu=("neu", "sum"))
        tab["vorher"] = tab["nachher"] - tab["neu"]
        for q, r in tab.iterrows():
            zeilen.append(f"| {q} | {r['vorher']} | {r['nachher']} | {r['neu']} |")
        zeilen.append("")
        print(f"{titel.get(cid, cid)}: {n_neu} neue Videos")
    PFAD_ERGEBNIS.write_text("\n".join(zeilen), encoding="utf-8")
    print(f"-> {PFAD_ERGEBNIS}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("vorher", "nachher"):
        sys.exit("Aufruf: vergleich_nachscraping.py vorher|nachher")
    main(sys.argv[1])

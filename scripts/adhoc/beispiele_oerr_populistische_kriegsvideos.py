# -*- coding: utf-8 -*-
"""
beispiele_oerr_populistische_kriegsvideos.py

Ad-hoc-Skript (.claude/CLAUDE.md) fuer die Nutzerfrage "Beispiele fuer populistische
OeRR-Kriegsvideos mit vielen Views", im Anschluss an
diagnose_oerr_populismuspraemie.py. Reine Illustration/Anschauungsmaterial, kein
neuer statistischer Test.

Holt Video-Titel ueber video_registry.get_video_metadata() (in
channel_video_populism.csv/channel_video_erfolg.csv nicht enthalten) fuer die
OeRR-Kriegsvideos mit populismus_gesamt in der Top-Quartile UND view_count in der
Top-Quartile (innerhalb OeRR-Kriegsvideos) - Videos, die BEIDES gleichzeitig sind,
statt nur nach Views ODER nur nach Populismus zu sortieren (sonst dominieren bei
reiner Views-Sortierung tagesschau-Nachrichten mit populismus_gesamt nahe 0).

Ausfuehrung (aus dem Projekt-Root):
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/adhoc/beispiele_oerr_populistische_kriegsvideos.py

Schreibt scripts/adhoc/output/beispiele_oerr_populistische_kriegsvideos.csv.
"""

from pathlib import Path

import pandas as pd

from youtube_code.store import video_registry
from youtube_code.step6_auswertung.deskriptiv_aggregation import lade_medientyp

PROJEKT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_PATH = PROJEKT_ROOT / "outputs" / "segment_analysis"
PFAD_POPULISMUS = RESULTS_PATH / "channel_video_populism.csv"
PFAD_ERFOLG = RESULTS_PATH / "channel_video_erfolg.csv"

AUSGABE = PROJEKT_ROOT / "scripts" / "adhoc" / "output" / "beispiele_oerr_populistische_kriegsvideos.csv"

POPULISMUS_QUANTIL = 0.75   # untere Schwelle: Top-Quartil bzgl. populismus_gesamt
VIEWS_QUANTIL = 0.75        # untere Schwelle: Top-Quartil bzgl. view_count
N_BEISPIELE = 25


def lade_oerr_kriegsvideos():
    pop = pd.read_csv(PFAD_POPULISMUS)
    pop["channel_id"] = pop["channel_id"].astype(str)
    pop = pop[["channel_id", "video_id", "populismus_gesamt", "volkszentrismus",
               "antielitismus", "manichaeische_moralisierung", "emotionale_intensitaet"]]

    erfolg = pd.read_csv(PFAD_ERFOLG)
    erfolg["channel_id"] = erfolg["channel_id"].astype(str)

    merged = pop.merge(
        erfolg[["channel_id", "channel_title", "video_id", "view_count", "log_views", "ist_kriegsvideo"]],
        on=["channel_id", "video_id"], how="inner",
    )
    kv = merged[merged["ist_kriegsvideo"] == 1].copy()

    # lade_medientyp() dedupliziert Duplikatzeilen in PFAD_MEDIENTYP (siehe dortiger
    # Docstring) - ein roher Merge ohne diese Funktion wuerde betroffene Kanaele
    # (2026-09-08 entdeckt: ARTEde, WDR aktuell) verdoppeln.
    med = lade_medientyp()
    kv = kv.merge(med[["channel_id", "medientyp"]], on="channel_id", how="left")
    return kv[kv["medientyp"] == "ÖRR"].dropna(subset=["populismus_gesamt", "view_count"])


def main():
    oerr = lade_oerr_kriegsvideos()
    print(f"[Basis] {len(oerr)} OeRR-Kriegsvideos.")

    pop_schwelle = oerr["populismus_gesamt"].quantile(POPULISMUS_QUANTIL)
    views_schwelle = oerr["view_count"].quantile(VIEWS_QUANTIL)
    print(f"[Schwellen] populismus_gesamt >= {pop_schwelle:.3f} (Top-{int((1-POPULISMUS_QUANTIL)*100)}%), "
          f"view_count >= {views_schwelle:.0f} (Top-{int((1-VIEWS_QUANTIL)*100)}%)")

    kandidaten = oerr[(oerr["populismus_gesamt"] >= pop_schwelle) & (oerr["view_count"] >= views_schwelle)].copy()
    print(f"[Filter] {len(kandidaten)} Videos erfuellen beide Kriterien gleichzeitig.")

    titel = video_registry.get_video_metadata(video_ids=kandidaten["video_id"].tolist())
    kandidaten = kandidaten.merge(titel[["video_id", "title", "published_at"]], on="video_id", how="left")

    kandidaten = kandidaten.sort_values(["populismus_gesamt", "view_count"], ascending=False)
    top = kandidaten.head(N_BEISPIELE)

    spalten = ["channel_title", "title", "published_at", "view_count", "populismus_gesamt",
               "volkszentrismus", "antielitismus", "manichaeische_moralisierung", "emotionale_intensitaet"]
    print(f"\n=== Top {len(top)} Beispiele (hoher Populismus-Score UND viele Views) ===")
    for _, zeile in top.iterrows():
        print(f"\n[{zeile['channel_title']}] {zeile['title']}")
        print(f"  {pd.to_datetime(zeile['published_at']).date()} | {int(zeile['view_count']):,} Views | "
              f"populismus_gesamt={zeile['populismus_gesamt']:.2f} "
              f"(volkszentrismus={zeile['volkszentrismus']:.2f}, antielitismus={zeile['antielitismus']:.2f}, "
              f"moralisierung={zeile['manichaeische_moralisierung']:.2f}, "
              f"emotion={zeile['emotionale_intensitaet']:.2f})")

    kandidaten[spalten].to_csv(AUSGABE, index=False, encoding="utf-8")
    print(f"\n[Ausgabe] {len(kandidaten)} Zeilen -> {AUSGABE}")


if __name__ == "__main__":
    main()

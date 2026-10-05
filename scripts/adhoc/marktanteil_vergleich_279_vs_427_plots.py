# -*- coding: utf-8 -*-
"""
marktanteil_vergleich_279_vs_427_plots.py

Ad-hoc-Nachfrage im Chat (2026-09-28) zu marktanteil_vergleich_279_vs_427.py: der dortige
Phasen-Bericht zeigt Differenzen zwischen 279er-Whitelist und 427er-Kanon-Sample nur als
6 grobe Phasen-Buckets. Hier stattdessen der monatliche Trendverlauf (rel_monat) je
Gruppe5-Kategorie als Grafik, fuer die zwei Umfaenge mit den groessten Differenzen im
Phasen-Bericht ("andere politische Videos" und "alle Videos" - "Kriegsberichterstattung"
zeigte dort <1.1pp Differenz ueberall und wird deshalb hier NICHT geplottet, siehe
marktanteil_vergleich_279_vs_427.md).

NICHT Teil der zentralen Codebasis (daher scripts/adhoc/, siehe CLAUDE.md) - reine
Visualisierung derselben Sensitivitaetsfrage, kein neuer regulaerer Analyseschritt.

Methodik/Datengrundlage: VOLLSTAENDIG wiederverwendet, keine neue Logik:
  - Video-Ebene Basisdaten: lade_basisdaten() (279er-Whitelist) aus
    frage4_kriegspraemie_relative_views_plots.py und lade_basisdaten(kanalquelle="kanon")
    (427er-Kanon-Sample, inkl. defensivem Ideologie-Dedup) aus derselben Datei - echte
    Importe, siehe dortige Docstrings und marktanteil_vergleich_279_vs_427.py fuer die volle
    Herleitung (u.a. warum
    effektiv 260 von 279 bzw. 367 von 427 Kanaelen ein gueltiges gruppe5 haben).
  - Umfangs-Filter (andere_politische_videos/alle_videos): UMFAENGE aus
    frage4_kriegspraemie_marktanteil_phasen_bericht.py, echter Import.
  - Monatlicher Marktanteil je Zelle (rel_monat x gruppe5): berechne_marktanteile() aus
    frage4_kriegspraemie_marktanteil_plots.py, echter Import - GLEICHE Formel wie im
    Phasen-Bericht (anteil = views(Gruppe)/views(alle 5 Gruppen)*100), nur auf Monats- statt
    Phasen-Ebene aggregiert und mit MIN_VIDEOS_GESAMT_PRO_PERIODE=20 statt
    MIN_VIDEOS_GESAMT_PRO_PHASE=100 (kleinere Zeiteinheit braucht eine kleinere
    Mindestbesetzung, sonst wuerden zu viele Monate wegfallen - identisch zur bestehenden
    Konvention aus frage4_kriegspraemie_marktanteil_plots.py).
  - Plot: plotte_kombinierte_grafik() aus frage2_sensitivitaet_plots.py, echter Import -
    eine Linie je Gruppe5-Kategorie (feste Farbe je Gruppe), LOWESS-geglaettet; dick =
    279er-Whitelist (hauptfokus), duenn/transparent = 427er-Kanon-Sample (vergleich) in
    DERSELBEN Farbe - direkter visueller Vergleich, ob sich der Trendverlauf je Gruppe
    zwischen den beiden Kanallisten unterscheidet (nicht nur das Niveau wie im Phasen-
    Bericht).

Schreibt 2 PNGs (je Umfang eine Grafik) nach
scripts/adhoc/output/plots_marktanteil_vergleich_279_vs_427/.

Ausfuehren (im Ordner src/youtube_code/step6_auswertung/, wegen sibling-Importen, wie die
anderen scripts/adhoc/marktanteil_*-Skripte):

    PYTHONPATH=src PYTHONIOENCODING=utf-8 ../../../.venv/Scripts/python.exe \
        ../../../scripts/adhoc/marktanteil_vergleich_279_vs_427_plots.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "youtube_code", "step6_auswertung"))

from youtube_code.config import ROOT

from frage2_sensitivitaet_plots import plotte_kombinierte_grafik
from frage4_kriegspraemie_relative_views_plots import lade_basisdaten
from frage4_kriegspraemie_marktanteil_plots import berechne_marktanteile
from frage4_kriegspraemie_marktanteil_phasen_bericht import UMFAENGE

# "kriegsvideos" bewusst ausgelassen - siehe Moduldocstring (Phasen-Bericht zeigte dort
# durchgehend <1.1pp Differenz, kein sichtbarer Trendunterschied zu erwarten).
GEPLOTTETE_UMFAENGE = ["andere_politische_videos", "alle_videos"]

PFAD_PLOTS = ROOT / "scripts" / "adhoc" / "output" / "plots_marktanteil_vergleich_279_vs_427"


def main():
    print("[Basisdaten] Lade 279er-Whitelist ...")
    basisdaten_279 = lade_basisdaten()
    print("[Basisdaten] Lade 427er-Kanon-Sample ...")
    basisdaten_427 = lade_basisdaten(kanalquelle="kanon")

    erzeugt = []
    for umfang_key in GEPLOTTETE_UMFAENGE:
        cfg = UMFAENGE[umfang_key]
        teil_279 = basisdaten_279[cfg["filter"](basisdaten_279)]
        teil_427 = basisdaten_427[cfg["filter"](basisdaten_427)]

        anteile_279 = berechne_marktanteile(teil_279)
        anteile_427 = berechne_marktanteile(teil_427)

        dateiname = f"marktanteil_vergleich_279_vs_427_{umfang_key}.png"
        titel = (f"Marktanteil je Gruppe5-Kategorie - {cfg['titel']}\n"
                 "dick=279er-Whitelist, duenn=427er-Kanon-Sample")
        if plotte_kombinierte_grafik(
                anteile_279, anteile_427, dateiname, titel, "Marktanteil an Views (%)",
                hauptfokus_label="279er-Whitelist", vergleichs_label="427er-Kanon-Sample",
                pfad_plots=PFAD_PLOTS):
            erzeugt.append(dateiname)

    print(f"\n[Fertig] {len(erzeugt)} von {len(GEPLOTTETE_UMFAENGE)} moeglichen Grafiken "
          f"erzeugt -> {PFAD_PLOTS}")


if __name__ == "__main__":
    main()

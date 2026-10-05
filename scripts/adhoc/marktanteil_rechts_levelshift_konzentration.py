# -*- coding: utf-8 -*-
"""
marktanteil_rechts_levelshift_konzentration.py

Ad-hoc-Nachfrage im Chat (2026-09-10) zum "Marktanteil rechte Alternative Medien"-Befund aus
marktanteil_themen_plots.py (dick=Energie/alle_politische_videos-Szenarien): dort zeigte die
geglaettete (LOWESS) Kurve fuer "Alternative Medien (rechts)" einen scheinbar scharfen Anstieg
um rel_monat ~27-29 (siehe Chat). Zwei offene Fragen dazu, NICHT Teil der zentralen Codebasis
(daher hier in scripts/adhoc/, siehe CLAUDE.md):

1. Level-Shift-Check: Bleibt der erhoehte Marktanteil ueber das gesamte verfuegbare Fenster
   (bis rel_monat=48) erhalten (= dauerhafter Niveauwechsel), oder faellt er nach dem Peak
   wieder auf das Vorniveau zurueck (= temporaerer Schock)? Nutzt die ROHEN (ungeglaetteten)
   Monatswerte aus berechne_marktanteile() (echter Import aus
   frage4_kriegspraemie_marktanteil_plots.py, kein Duplikat) fuer das Szenario
   "alle politischen Videos" (ist_politics_topic == True) - robuster als das duenn besetzte
   "energy"-Szenario (siehe Chat: 52-254 Videos/Monat dort, zu verrauscht fuer diese Frage).

2. Konzentrationscheck: Wird der erhoehte Marktanteil im vermuteten Level-Shift-Fenster von
   vielen Kanaelen getragen (breiter Trend) oder von wenigen Kanaelen mit viralen Ausreissern
   dominiert (Einzelkanal-Artefakt)? Vergleicht Top-1-/Top-5-Kanal-Anteil an den Views und den
   Herfindahl-Index (HHI, auf Kanalanteilen an den Views der Gruppe "Alternative Medien
   (rechts)" innerhalb "alle politische Videos") zwischen einem Vorher- und einem
   Nachher-Fenster (Cutoff bei rel_monat=20, siehe Chat-Level-Shift-Diskussion).

Datenquelle: lade_basisdaten() aus frage4_kriegspraemie_relative_views_plots.py (Video-Ebene,
Whitelist-gefiltert, inkl. gruppe5/ist_politics_topic) - echter Import, kein Duplikat.

Nur Konsolen-Output, keine neuen Dateien (reine explorative Zwischenfrage, kein regulaerer
Analyseschritt - bei Bedarf spaeter als eigener Bericht in step6_auswertung/ ausbauen).

Ausfuehren (im Ordner src/youtube_code/step6_auswertung/, wegen sibling-Importen):

    PYTHONPATH=src PYTHONIOENCODING=utf-8 ../../../.venv/Scripts/python.exe \
        ../../../scripts/adhoc/marktanteil_rechts_levelshift_konzentration.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "youtube_code", "step6_auswertung"))

import pandas as pd

from frage4_kriegspraemie_relative_views_plots import lade_basisdaten
from frage4_kriegspraemie_marktanteil_plots import berechne_marktanteile
from deskriptiv_plots import GRUPPE5_REIHENFOLGE

GRUPPE = "Alternative Medien (rechts)"  # Hauptgruppe fuer den Konzentrationscheck (Schritt 2)
# Schritt 1 (Level-Shift) laeuft ueber ALLE 5 Gruppen (Nutzervorgabe im Chat: "dieselbe Logik
# auch fuer OERR und Alternative Medien links/mitte", hier auf alle 5 erweitert fuer den
# direkten Vergleich in einer Tabelle statt getrennter Laeufe).
CUTOFF = 20  # rel_monat-Grenze zwischen "vorher" (< 20) und "nachher" (>= 20), siehe Docstring
MIN_VIDEOS_GESAMT_PRO_PERIODE = 20  # identisch zu marktanteil_themen_plots.py


def level_shift_check(politik_df):
    print("\n" + "=" * 70)
    print("SCHRITT 1: LEVEL-SHIFT-CHECK (rohe Monatswerte, ungeglaettet), ALLE 5 GRUPPEN")
    print("=" * 70)
    anteile = berechne_marktanteile(politik_df, MIN_VIDEOS_GESAMT_PRO_PERIODE)

    zusammenfassung = []
    for gruppe in GRUPPE5_REIHENFOLGE:
        reihe = anteile[anteile["gruppe5"] == gruppe].sort_values("rel_monat")
        vor = reihe[reihe["rel_monat"] < CUTOFF]["wert"]
        nach = reihe[reihe["rel_monat"] >= CUTOFF]["wert"]
        ende = reihe[reihe["rel_monat"] >= 40]["wert"]
        zusammenfassung.append({
            "gruppe": gruppe,
            "vor_mean": vor.mean(), "vor_sd": vor.std(), "vor_n": len(vor),
            "nach_mean": nach.mean(), "nach_sd": nach.std(), "nach_n": len(nach),
            "ende_mean": ende.mean(), "ende_sd": ende.std(), "ende_n": len(ende),
        })
        if gruppe == GRUPPE:
            print(f"\nMarktanteil '{gruppe}' an 'alle politische Videos', je rel_monat "
                  f"(rohe Werte, KEINE LOWESS-Glaettung):\n")
            print(reihe[["rel_monat", "wert", "n_videos", "views_summe"]].to_string(index=False))

    tab = pd.DataFrame(zusammenfassung)
    print("\n[Zusammenfassung ALLE GRUPPEN] Marktanteil (%) an 'alle politische Videos', "
          f"vor (< {CUTOFF}) vs. nach (>= {CUTOFF}) vs. Sample-Ende (>= 40):\n")
    pd.set_option("display.width", 160)
    print(tab.round(1).to_string(index=False))
    print("\n-> Wenn 'ende_mean' nahe an 'nach_mean' bleibt (nicht zurueck Richtung "
          "'vor_mean'): dauerhafter Niveauwechsel. Wenn 'ende_mean' zurueck Richtung "
          "'vor_mean' faellt: eher temporaerer Schock/Peak.")


def konzentrations_check(politik_df):
    print("\n" + "=" * 70)
    print("SCHRITT 2: KONZENTRATIONSCHECK (Kanalebene, nur '" + GRUPPE + "')")
    print("=" * 70)
    gruppe_df = politik_df[politik_df["gruppe5"] == GRUPPE].copy()

    for label, teil in [
        (f"VORHER (rel_monat < {CUTOFF})", gruppe_df[gruppe_df["rel_monat"] < CUTOFF]),
        (f"NACHHER (rel_monat >= {CUTOFF})", gruppe_df[gruppe_df["rel_monat"] >= CUTOFF]),
    ]:
        kanal_views = teil.groupby("channel_id")["view_count"].sum().sort_values(ascending=False)
        gesamt_views = kanal_views.sum()
        anteile = kanal_views / gesamt_views
        top1 = anteile.iloc[0] * 100 if len(anteile) > 0 else float("nan")
        top5 = anteile.iloc[:5].sum() * 100 if len(anteile) > 0 else float("nan")
        hhi = (anteile ** 2).sum() * 10000  # Standard-HHI-Skala (0-10000)

        print(f"\n--- {label} ---")
        print(f"  Videos: {len(teil)}, Kanaele: {teil['channel_id'].nunique()}, "
              f"Views gesamt: {gesamt_views:,.0f}")
        print(f"  Top-1-Kanal-Anteil an Views: {top1:.1f}%")
        print(f"  Top-5-Kanal-Anteil an Views: {top5:.1f}%")
        print(f"  HHI (0-10000, >2500 = stark konzentriert): {hhi:.0f}")
        if len(anteile) > 0:
            print("  Top-5-Kanaele (channel_id -> Anteil an Gruppen-Views):")
            for cid, a in anteile.iloc[:5].items():
                print(f"    {cid}: {a * 100:.1f}%")


def main():
    basisdaten = lade_basisdaten()
    politik_df = basisdaten[basisdaten["ist_politics_topic"] == True].copy()
    print(f"\n[Filter] {len(politik_df)} von {len(basisdaten)} Videos mit "
          f"ist_politics_topic == True (Szenario 'alle politische Videos').")

    level_shift_check(politik_df)
    konzentrations_check(politik_df)


if __name__ == "__main__":
    main()

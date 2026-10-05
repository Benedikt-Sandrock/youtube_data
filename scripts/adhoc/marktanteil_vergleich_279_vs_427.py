# -*- coding: utf-8 -*-
"""
marktanteil_vergleich_279_vs_427.py

Ad-hoc-Robustheitscheck im Chat (2026-09-28): "Was passiert mit den Marktanteils-Ergebnissen aus
`frage4_kriegspraemie_marktanteil_phasen_bericht.py`, wenn man statt der 279er-Frage-1-Whitelist
alle 427 Kanaele des kanonischen Samples (`russia_longitudinal_v1`, eligible_current_analysis ==
True) verwendet?" NICHT Teil der zentralen Codebasis (daher hier in scripts/adhoc/, siehe
CLAUDE.md) - reine Sensitivitaetsfrage zur Kanalauswahl, kein neuer regulaerer Analyseschritt.

WICHTIG - "427" ist nur die Ausgangsmenge, nicht die tatsaechlich verwendete Kanalzahl:
gruppe5 (die Marktanteils-Gruppen) braucht Medientyp UND - fuer "Alternatives Medium" - eine
Ideologie-Einordnung (siehe deskriptiv_plots.py::baue_gruppe5()). Von den 427 kanonischen
Kanaelen bleiben nach diesem Filter 367 uebrig (Chat-Diagnose 2026-09-28):
  - 38 "Alternatives Medium" ohne Ideologie-Einordnung (24 davon OHNE JEDE LLM-Klassifikation -
    das waere ein neuer Klassifikationslauf, kein Excel-Fix) - auf Nutzerentscheidung NICHT
    nachklassifiziert, diese Luecke bleibt bestehen.
  - 19 "Politiker/Partei" (fallen laut bestehender Konvention IMMER aus gruppe5 raus, unabhaengig
    von der Kanalliste).
  - 3 ganz ohne Medientyp.
Von der 279er-Whitelist selbst bleiben aus demselben Grund nur 260 (nicht alle 279) mit
gueltigem gruppe5 - das faellt in der bestehenden Pipeline bereits heute still unter den Tisch
(kein neuer Befund dieses Skripts, nur hier zum ersten Mal explizit gegenuebergestellt).

Methodik: IDENTISCH zu `frage4_kriegspraemie_marktanteil_phasen_bericht.py` (`baue_phasenliste()`/
`berechne_tabelle()`, echter Import, kein Duplikat) - nur die Video-Ebene-Basisdaten
unterscheiden sich:
  - Variante 279: `lade_basisdaten()` aus `frage4_kriegspraemie_relative_views_plots.py` (echter
    Import, bitwise identisch zu den bereits berichteten Zahlen).
  - Variante 427: `lade_basisdaten(kanalquelle="kanon")` aus
    `frage4_kriegspraemie_relative_views_plots.py` (bis 2026-09-28 als `lade_basisdaten_kanon()`
    in diesem Skript, fuer AP 2 dorthin verschoben) - dieselbe Konstruktion
    (video_registry.get_video_stats() + get_topic_relevance() fuer ist_kriegsvideo +
    screening_state_store.get_state() fuer politics_final + politics_topic_lookup() fuer
    ist_politics_topic + ergaenze_periodenspalten() aus prepare_channel_scores.py, echter
    Import), aber ausgehend von der vollen kanonischen Kanalliste statt der Whitelist -
    analog zur "breiteren Kanalpopulation" in schockfenster_bericht.py, dort aber ohne
    Marktanteilsberechnung.

Bekannter Nebenbefund (Chat-Diagnose 2026-09-28, hier NUR dokumentiert und defensiv umgangen,
NICHT in der zentralen Codebasis gefixt): `deskriptiv_aggregation.py::lade_ideologie()`
dedupliziert NICHT auf channel_id, obwohl `channel_classification_ideology.csv` fuer 3
channel_id's (UCKbigI3YRqL7wFliRr7R8Mw, UCf4WJRXsgDEP7KH2eNGv8Hw, UCjvVn-oLzoY0aZhVvdQPSTQ)
Duplikatzeilen enthaelt (gleiche ideologie_gruppe, leicht unterschiedlicher ideologie_wert). Ein
ungeschuetzter merge(..., on="channel_id") dupliziert dadurch JEDE Videozeile dieser Kanaele - 2
davon (UCf4.../UCjvV...) sind in der 279er-Whitelist, ihre Views wuerden in jedem gruppe5-
basierten Bericht (inkl. der bereits vorliegenden Marktanteils-/Frage-1-Ergebnisse!) doppelt
gezaehlt. Der Kanon-Lader dedupliziert `lade_medientyp()`/`lade_ideologie()` defensiv
(`drop_duplicates(subset="channel_id", keep="first")`) vor jedem Merge, um den Bug nicht in den
eigenen Vergleich zu importieren - das bestehende `frage4_kriegspraemie_marktanteil_phasen_
bericht.csv` selbst bleibt davon unberuehrt (dort nicht gefixt). Separates Thema, nicht Teil
dieser Nutzerfrage - ggf. als eigener Fix in `lade_ideologie()` nachziehen.

Schreibt `scripts/adhoc/output/marktanteil_vergleich_279_vs_427.md` (Anteil je Phase x Umfang x
Gruppe5, beide Varianten nebeneinander plus Differenz in Prozentpunkten). Reine Konsolen-
Diagnostik zusaetzlich zur Kanalzahl je Variante.

Ausfuehren (im Ordner src/youtube_code/step6_auswertung/, wegen sibling-Importen, wie die anderen
scripts/adhoc/marktanteil_*-Skripte):

    PYTHONPATH=src PYTHONIOENCODING=utf-8 ../../../.venv/Scripts/python.exe \
        ../../../scripts/adhoc/marktanteil_vergleich_279_vs_427.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "youtube_code", "step6_auswertung"))

import pandas as pd

from youtube_code.config import ROOT

from deskriptiv_plots import GRUPPE5_REIHENFOLGE
from frage4_kriegspraemie_relative_views_plots import lade_basisdaten
from frage4_kriegspraemie_marktanteil_phasen_bericht import (
    baue_phasenliste, berechne_tabelle, UMFAENGE,
)

PFAD_ERGEBNIS_MD = ROOT / "scripts" / "adhoc" / "output" / "marktanteil_vergleich_279_vs_427.md"


# =========================================================
# SCHRITT 1: Vergleich der beiden Marktanteils-Tabellen
# =========================================================

def vergleiche(tabelle_279, tabelle_427):
    """Inner-Join auf (Phase, Umfang, Gruppe5) - Zellen, die in EINER der beiden Varianten wegen
    Mindestbesetzung uebersprungen wurden (siehe berechne_tabelle()), fehlen dadurch im
    Vergleich statt mit einem falschen 0%-Wert aufzutauchen."""
    schluessel = ["phase", "phase_label", "monat_min", "monat_max", "umfang", "umfang_titel", "gruppe5"]
    merged = tabelle_279[schluessel + ["anteil_pct", "n_videos_gesamt"]].merge(
        tabelle_427[schluessel + ["anteil_pct", "n_videos_gesamt"]],
        on=schluessel, suffixes=("_279", "_427"),
    )
    merged["differenz_pp"] = merged["anteil_pct_427"] - merged["anteil_pct_279"]
    return merged


def baue_vergleichsbericht(merged, n_kanaele_279, n_kanaele_427):
    zeilen = [
        "# Marktanteils-Vergleich: 279er-Whitelist vs. 427er-Kanonisches Sample",
        "",
        "Robustheitscheck (Chat-Nachfrage 2026-09-28): veraendert sich die Marktanteils-"
        "verteilung aus `frage4_kriegspraemie_marktanteil_phasen_bericht.py`, wenn statt der "
        "279er-Frage-1-Whitelist das volle kanonische Sample (`russia_longitudinal_v1`) "
        "verwendet wird? Identische Methodik (`baue_phasenliste()`/`berechne_tabelle()`, echter "
        "Import, kein Duplikat) - nur die zugrunde liegende Kanalliste unterscheidet sich. Siehe "
        "Moduldocstring von `marktanteil_vergleich_279_vs_427.py` fuer die vollstaendige "
        "Herleitung (u.a. warum es effektiv 260 vs. 367 statt 279 vs. 427 Kanaele sind).",
        "",
        f"- **279er-Whitelist**: {n_kanaele_279} Kanaele mit gueltigem gruppe5 (von 279).",
        f"- **427er-Kanon-Sample**: {n_kanaele_427} Kanaele mit gueltigem gruppe5 (von 427).",
        "",
        "Zellen, die in einer der beiden Varianten unter der Mindestbesetzung "
        "(`MIN_VIDEOS_GESAMT_PRO_PHASE`) liegen, fehlen hier (kein 0%-Platzhalter).",
        "",
    ]
    for umfang_key, umfang_cfg in UMFAENGE.items():
        teil = merged[merged["umfang"] == umfang_key]
        if teil.empty:
            continue
        zeilen.append(f"## Umfang: {umfang_cfg['titel']}")
        zeilen.append("")
        phase_ids = list(teil[["monat_min", "phase"]].drop_duplicates()
                          .sort_values("monat_min")["phase"])
        header = ["Phase", "Gruppe5", "Anteil 279 (%)", "Anteil 427 (%)", "Differenz (pp)"]
        zeilen.append("| " + " | ".join(header) + " |")
        zeilen.append("|" + "---|" * len(header))
        for phase_id in phase_ids:
            phase_teil = teil[teil["phase"] == phase_id]
            if phase_teil.empty:
                continue
            label = phase_teil["phase_label"].iloc[0]
            for g in GRUPPE5_REIHENFOLGE:
                reihe = phase_teil[phase_teil["gruppe5"] == g]
                if reihe.empty:
                    continue
                r = reihe.iloc[0]
                zeilen.append(f"| {label} | {g} | {r['anteil_pct_279']:.1f} | "
                              f"{r['anteil_pct_427']:.1f} | {r['differenz_pp']:+.1f} |")
        zeilen.append("")
    return "\n".join(zeilen) + "\n"


# =========================================================
# MAIN
# =========================================================

def main():
    print("=" * 70)
    print("VARIANTE A: 279er-Whitelist (bestehende Pipeline, echter Import, unveraendert)")
    print("=" * 70)
    basisdaten_279 = lade_basisdaten()
    phasenliste_279 = baue_phasenliste(basisdaten_279)
    tabelle_279 = berechne_tabelle(basisdaten_279, phasenliste_279)
    n_kanaele_279 = basisdaten_279["channel_id"].nunique()

    print()
    print("=" * 70)
    print("VARIANTE B: 427er-Kanonisches Sample")
    print("=" * 70)
    basisdaten_427 = lade_basisdaten(kanalquelle="kanon")
    phasenliste_427 = baue_phasenliste(basisdaten_427)
    tabelle_427 = berechne_tabelle(basisdaten_427, phasenliste_427)
    n_kanaele_427 = basisdaten_427["channel_id"].nunique()

    merged = vergleiche(tabelle_279, tabelle_427)
    bericht = baue_vergleichsbericht(merged, n_kanaele_279, n_kanaele_427)

    PFAD_ERGEBNIS_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(PFAD_ERGEBNIS_MD, "w", encoding="utf-8") as f:
        f.write(bericht)
    print(f"\n[Bericht] {PFAD_ERGEBNIS_MD}")


if __name__ == "__main__":
    main()

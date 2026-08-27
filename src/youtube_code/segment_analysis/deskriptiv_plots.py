# -*- coding: utf-8 -*-
"""
deskriptiv_plots.py

Plottet die Ausgabe von deskriptiv_aggregation.py.

Populismus: Index (letzte Vorkriegsperioden = 100) im Zeitverlauf.
Stance:     Rohwerte der Kriegsvideos im Zeitverlauf, ohne Baseline.

Aggregation ueber Kanaele: ungewichteter Mittelwert der Kanalwerte + 95%-CI.

Granularitaet (Quartal/Monat) ueber GRANULARITAET waehlbar - muss zu der Datei
passen, die mit dieser Granularitaet in deskriptiv_aggregation.py erzeugt wurde
(deskriptiv_{modus}_{granularitaet}.csv).
"""

import os
from itertools import cycle

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from youtube_code.config import OUTPUTS

# =========================================================
# CONFIG
# =========================================================

MODUS = "stance"          # "populismus" | "stance"
GRANULARITAET = "monat"     # "quartal" | "monat" - muss zur eingelesenen deskriptiv_*.csv passen

# --- Granularitaets-Definitionen (Periodenspalte, Fensterbereich, Achsenbeschriftung) ---
GRANULARITAETEN = {
    "quartal": {
        "spalte": "rel_quartal",
        "periode_min": -4,
        "periode_max": 12,
        "achsenlabel": "Quartal relativ zum Kriegsbeginn",
        "referenzlinie_text": "Kriegsbeginn",
    },
    "monat": {
        "spalte": "rel_monat",
        "periode_min": -12,
        "periode_max": 48,
        "achsenlabel": "Monat relativ zum Kriegsbeginn",
        "referenzlinie_text": "Kriegsbeginn",
    },
}

_GRAN_CFG = GRANULARITAETEN[GRANULARITAET]
SPALTE_PERIODE = _GRAN_CFG["spalte"]
PERIODE_MIN = _GRAN_CFG["periode_min"]
PERIODE_MAX = _GRAN_CFG["periode_max"]
ACHSENLABEL = _GRAN_CFG["achsenlabel"]

PFAD_EINGABE = OUTPUTS / "segment_analysis" / "deskriptiv_{modus}_{granularitaet}.csv"
PFAD_PLOTS = OUTPUTS / "segment_analysis" / "plots"

SPLIT = "medientyp"           # "keiner" | "medientyp" | "ideologie"

DIMENSIONEN_PLOTTEN = None    # None = alle; sonst z.B. ["populismus_gesamt", "antielitismus"]

MIN_KANAELE_PRO_ZELLE = 5     # Zellen mit weniger Kanaelen werden nicht geplottet
ZEIGE_CI = True
ZEIGE_N = True                # n je Punkt in die Konsole schreiben

GRUPPEN_REIHENFOLGE = None    # z.B. ["ÖRR", "Traditionelles Medium", "Alternatives Medium", "Politiker/Partei"]

ABBILDUNG_GROESSE = (9, 5)
DPI = 150

# --- Filterkombinationen: mehrere Dimensionen in EINER Grafik, gefiltert auf ---
# --- eine bestimmte Kanalgruppe (z.B. "rechte alternative Medien"). ---
# Liest denselben MODUS/GRANULARITAET-CSV wie oben; alle Dimensionen muessen also
# aus derselben deskriptiv_{modus}_{granularitaet}.csv stammen.
FILTERKOMBINATIONEN = [
    {
        "name": "rechte_alternative_medien",
        "filter": {"medientyp": ["Alternatives Medium"], "ideologie_gruppe": ["rechts"]},
        "dimensionen": ["position_russland", "position_westpolitik", "emotion"],
    },
]

# Dimensionen aus FILTERKOMBINATIONEN, die auf einer zweiten y-Achse (rechts) geplottet werden,
# weil ihre Skala nicht zu den uebrigen Dimensionen passt (z.B. Emotion 0-3 vs. Stance -2 bis +2).
SEKUNDAERACHSE_DIMENSIONEN = ["emotion", "emotionale_intensitaet", "populismus_gesamt"]

# Optionale feste Farbzuordnung je Dimension (matplotlib-Farbnamen oder Hex). Dimensionen
# ohne Eintrag bekommen automatisch die naechste freie Farbe aus einem gemeinsamen Zyklus,
# der ueber Haupt- und Sekundaerachse hinweg laeuft (verhindert zufaellige Farbkollisionen
# zwischen den beiden Achsen). Leer lassen fuer rein automatische Zuordnung.
DIMENSION_FARBEN = {}


# =========================================================
# HILFSFUNKTIONEN
# =========================================================

def gruppenspalte():
    return {"keiner": None, "medientyp": "medientyp", "ideologie": "ideologie_gruppe"}[SPLIT]


def wertspalte():
    return "index_100" if MODUS == "populismus" else "wert_roh"


def aggregiere(df, gruppe, wert):
    schluessel = [SPALTE_PERIODE] + ([gruppe] if gruppe else [])
    agg = df.groupby(schluessel, as_index=False).agg(
        mittel=(wert, "mean"),
        sd=(wert, "std"),
        n_kanaele=("channel_id", "nunique"),
    )
    agg["se"] = agg["sd"] / np.sqrt(agg["n_kanaele"].clip(lower=1))
    agg["ci_unten"] = agg["mittel"] - 1.96 * agg["se"]
    agg["ci_oben"] = agg["mittel"] + 1.96 * agg["se"]
    return agg[agg["n_kanaele"] >= MIN_KANAELE_PRO_ZELLE]


def plotte_dimension(df, dimension, gruppe, wert):
    teil = df[df["dimension"] == dimension].dropna(subset=[wert])
    teil = teil[(teil[SPALTE_PERIODE] >= PERIODE_MIN) & (teil[SPALTE_PERIODE] <= PERIODE_MAX)]
    if teil.empty:
        print(f"[Skip] Keine Daten fuer '{dimension}'.")
        return

    agg = aggregiere(teil, gruppe, wert)
    if agg.empty:
        print(f"[Skip] '{dimension}': alle Zellen unter MIN_KANAELE_PRO_ZELLE.")
        return

    fig, ax = plt.subplots(figsize=ABBILDUNG_GROESSE)

    if gruppe:
        gruppen = GRUPPEN_REIHENFOLGE or sorted(agg[gruppe].dropna().unique())
        gruppen = [g for g in gruppen if g in set(agg[gruppe])]
    else:
        gruppen = [None]

    for g in gruppen:
        reihe = agg if g is None else agg[agg[gruppe] == g]
        reihe = reihe.sort_values(SPALTE_PERIODE)
        label = "alle Kanaele" if g is None else str(g)
        ax.plot(reihe[SPALTE_PERIODE], reihe["mittel"], marker="o", label=label)
        if ZEIGE_CI:
            ax.fill_between(reihe[SPALTE_PERIODE], reihe["ci_unten"], reihe["ci_oben"], alpha=0.15)

    # Referenzlinien
    ax.axvline(-0.5, color="black", linestyle="--", linewidth=1)
    ax.text(-0.45, ax.get_ylim()[1], f" {_GRAN_CFG['referenzlinie_text']}", va="top", fontsize=8)

    if MODUS == "populismus":
        ax.axhline(100, color="grey", linewidth=0.8)
        ax.set_ylabel("Index (Baselineperiode = 100)")
        hinweis = ("Vor dem Strich: allgemeinpolitische Baselinevideos. "
                   "Nach dem Strich: Kriegsvideos.")
    else:
        ax.axhline(0, color="grey", linewidth=0.8)
        ax.set_ylabel("Skalenwert")
        hinweis = "Nur Kriegsvideos, keine Vorkriegsbaseline verfuegbar."

    ax.set_xlabel(ACHSENLABEL)
    ax.set_title(f"{dimension} ({MODUS}, {GRANULARITAET})")
    ax.set_xticks(sorted(agg[SPALTE_PERIODE].unique()))
    if gruppe:
        ax.legend(fontsize=8)
    fig.text(0.01, 0.005, hinweis, fontsize=7, color="dimgrey")
    fig.tight_layout(rect=(0, 0.03, 1, 1))

    PFAD_PLOTS.mkdir(parents=True, exist_ok=True)
    datei = PFAD_PLOTS / f"{MODUS}_{dimension}_{SPLIT}_{GRANULARITAET}.png"
    fig.savefig(datei, dpi=DPI)
    plt.close(fig)
    print(f"[Plot] {datei}")

    if ZEIGE_N:
        spalten = [SPALTE_PERIODE] + ([gruppe] if gruppe else []) + ["n_kanaele", "mittel"]
        print(agg[spalten].to_string(index=False))
        print()


def plotte_filterkombination(df, eintrag):
    """Mehrere Dimensionen in einer Grafik, gefiltert auf eine beliebige Kombination
    aus Kanalmerkmalen (z.B. medientyp + ideologie_gruppe). Aggregation ist immer
    ungruppiert (ein Mittelwert je Periode ueber die gefilterten Kanaele)."""

    name = eintrag.get("name", "filterkombination")
    filt = eintrag.get("filter", {})
    dimensionen = eintrag["dimensionen"]
    wert = wertspalte()

    teil = df.copy()
    beschreibung = []
    for spalte, werte in filt.items():
        if spalte not in teil.columns:
            raise KeyError(f"Filterkombination '{name}': Spalte '{spalte}' nicht in den Daten.")
        teil = teil[teil[spalte].isin(werte)]
        beschreibung.append(f"{spalte}={'+'.join(map(str, werte))}")

    if teil.empty:
        print(f"[Skip] Filterkombination '{name}': keine Kanaele nach Filter uebrig.")
        return

    fig, ax = plt.subplots(figsize=ABBILDUNG_GROESSE)
    ax2 = None
    irgendwas_geplottet = False
    standardfarben = cycle(plt.rcParams["axes.prop_cycle"].by_key()["color"])

    for dim in dimensionen:
        teil_dim = teil[teil["dimension"] == dim].dropna(subset=[wert])
        teil_dim = teil_dim[(teil_dim[SPALTE_PERIODE] >= PERIODE_MIN) & (teil_dim[SPALTE_PERIODE] <= PERIODE_MAX)]
        if teil_dim.empty:
            print(f"[Skip] '{name}' / '{dim}': keine Daten.")
            continue

        agg = aggregiere(teil_dim, None, wert)
        if agg.empty:
            print(f"[Skip] '{name}' / '{dim}': alle Zellen unter MIN_KANAELE_PRO_ZELLE.")
            continue
        agg = agg.sort_values(SPALTE_PERIODE)

        ziel_achse = ax
        if dim in SEKUNDAERACHSE_DIMENSIONEN:
            if ax2 is None:
                ax2 = ax.twinx()
            ziel_achse = ax2

        farbe = DIMENSION_FARBEN.get(dim) or next(standardfarben)

        ziel_achse.plot(agg[SPALTE_PERIODE], agg["mittel"], marker="o", label=dim, color=farbe)
        if ZEIGE_CI:
            ziel_achse.fill_between(agg[SPALTE_PERIODE], agg["ci_unten"], agg["ci_oben"],
                                     alpha=0.15, color=farbe)
        irgendwas_geplottet = True

        if ZEIGE_N:
            print(f"  [{name} / {dim}]")
            print(agg[[SPALTE_PERIODE, "n_kanaele", "mittel"]].to_string(index=False))

    if not irgendwas_geplottet:
        print(f"[Skip] Filterkombination '{name}': keine Dimension hatte ausreichend Daten.")
        plt.close(fig)
        return

    ax.axvline(-0.5, color="black", linestyle="--", linewidth=1)
    ax.axhline(0, color="grey", linewidth=0.8)
    ax.set_xlabel(ACHSENLABEL)
    ax.set_ylabel("Skalenwert (Hauptachse)")
    if ax2:
        ax2.set_ylabel("Skalenwert (Sekundärachse: " + ", ".join(
            d for d in dimensionen if d in SEKUNDAERACHSE_DIMENSIONEN) + ")")

    ax.set_title(f"{name} ({', '.join(beschreibung)}, {GRANULARITAET})")

    linien, labels = ax.get_legend_handles_labels()
    if ax2:
        linien2, labels2 = ax2.get_legend_handles_labels()
        linien += linien2
        labels += labels2
    ax.legend(linien, labels, fontsize=8)

    fig.tight_layout()

    PFAD_PLOTS.mkdir(parents=True, exist_ok=True)
    datei = PFAD_PLOTS / f"{MODUS}_{name}_{GRANULARITAET}.png"
    fig.savefig(datei, dpi=DPI)
    plt.close(fig)
    print(f"[Plot] {datei}")


# =========================================================
# MAIN
# =========================================================

def main():
    pfad = str(PFAD_EINGABE).format(modus=MODUS, granularitaet=GRANULARITAET)
    df = pd.read_csv(pfad)
    print(f"[Eingabe][{GRANULARITAET}] {len(df)} Zeilen aus {pfad}")

    if SPALTE_PERIODE not in df.columns:
        raise KeyError(f"Spalte '{SPALTE_PERIODE}' nicht in '{pfad}' gefunden - passt GRANULARITAET "
                        f"zu der eingelesenen Datei? Vorhanden: {list(df.columns)}")

    gruppe = gruppenspalte()
    wert = wertspalte()

    if gruppe and df[gruppe].isna().all():
        raise ValueError(f"Spalte '{gruppe}' ist komplett leer - Split nicht moeglich.")

    dimensionen = DIMENSIONEN_PLOTTEN or sorted(df["dimension"].unique())
    for d in dimensionen:
        plotte_dimension(df, d, gruppe, wert)

    for eintrag in FILTERKOMBINATIONEN:
        plotte_filterkombination(df, eintrag)


if __name__ == "__main__":
    main()
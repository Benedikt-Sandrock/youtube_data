"""
Wöchentliche Themenanteile nach fünf Kanaltypen (ÖRR, traditionelle Medien,
alternative Medien links/mitte/rechts) – welche Themen waren für welche
Akteure wann prominent?

Gegenstück zu weekly_war_share_5types_plot.py (Daten, Gruppen, Farben,
LOWESS-Glättung und Achsenformat werden von dort importiert), aber für alle
share_*-Variablen aus outputs/stata_rohdaten/weekly_data_5types.dta
(erzeugt von outputs/stata_rohdaten/supply_reaction.do).

Datenbasis laut supply_reaction.do: nur format == "long", Titel-Topics in der
cw-Variante (rel_*_cw = core oder wide, Hauptspezifikation), je Video durch die
Zahl der Topics geteilt.

Themen: Krieg, Politik, Corona, Wirtschaft, Energie, Nahost, Iran, USA.
share_energy wird hier als share_energy_economy − share_economy abgeleitet
(im .do ist nur die Summe Wirtschaft + Energie angelegt; da beide Variablen
Mittelwerte derselben Kanal-Wochen sind, ist die Differenz exakt der
Energieanteil). Die Anteile summieren sich nicht zu 100 %, weil nicht alle
Topics als share_* exportiert werden.

Ausgabe nach outputs/stata_rohdaten/grafiken/:
- weekly_topic_shares_5types_grid.png     ein Panel je Thema, fünf Gruppen
  als LOWESS-Linien (getrennt vor/ab Kriegsbeginn), eigene y-Achse je Panel
- topic_shares_5types/weekly_<thema>_share_5types.png
  je Thema eine große Overlay-Grafik (wie weekly_war_share_5types.png)
- monthly_topic_heatmap_5types.png        je Gruppe eine Heatmap Thema × Monat;
  Farbe = Monatsanteil relativ zum Maximum des Themas über alle Gruppen
  (macht kleine Themen wie Iran sichtbar und bleibt zwischen Gruppen vergleichbar);
  Zahl in der Legende rechts = absolutes Maximum je Thema

Mit --vorkrieg wird stattdessen weekly_data_5types_vorkrieg.dta gelesen (nur
Kanäle mit sample_vorkrieg == 1, im .do vor dem Collapse auf Kanalebene
gefiltert). Alle Dateinamen bekommen dann das Suffix _vorkrieg, die Einzel-
grafiken landen in topic_shares_5types_vorkrieg/. Hinweis: Die Variable
sample_vorkrieg in weekly_data_5types.dta taugt NICHT als Filter – sie ist per
(first) kollabiert und enthält nur den Wert des ersten Kanals je Gruppen-Woche.

Mit --gewichtet werden die sqrt-gewichteten Exporte gelesen
(weekly_data_5types[_vorkrieg]_sqrt.dta): Kanal-Wochen zählen im Gruppenmittel
mit sqrt(Zahl der Videos), uploadstarke Kanäle also etwas mehr, ohne zu
dominieren. Dateisuffix _sqrt; beide Optionen sind kombinierbar
(Suffix _vorkrieg_sqrt).

Ausführen aus dem Repo-Root:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/adhoc/weekly_topic_shares_5types_plot.py [--vorkrieg] [--gewichtet]
"""

import argparse

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from weekly_war_share_5types_plot import (
    GRUPPEN, INK_MUTED, KRIEGSBEGINN, PFAD_AUSGABE, PFAD_EINGABE,
    formatiere_achse, plotte_geglaettet,
)

# =========================================================
# CONFIG
# =========================================================

THEMEN = {
    "share_war": "Russland-Ukraine-Krieg",
    "share_politics": "Politik",
    "share_corona": "Corona",
    "share_economy": "Wirtschaft",
    "share_energy": "Energie",
    "share_mideast": "Nahost",
    "share_iran": "Iran",
    "share_usa": "USA",
}

QUELLE = ("Nur Long-Videos, Titel-Topics rel_*_cw (anteilig gewichtet); "
          "{gewichtung} Mittelwert der Kanal-Wochenanteile; Ideologie: "
          "ideo_gesellschaft_baseline, Schnitte ±0,5.")


def variante(vorkrieg, gewichtet):
    """Eingabepfad, Dateisuffix, Titelzusatz und Quellenzeile je Option."""
    suffix = ("_vorkrieg" if vorkrieg else "") + ("_sqrt" if gewichtet else "")
    pfad = PFAD_EINGABE.with_name(f"weekly_data_5types{suffix}.dta")
    zusaetze = (["nur Vorkriegs-Sample"] if vorkrieg else []) +                (["sqrt-gewichtet"] if gewichtet else [])
    titel = (" – " + ", ".join(zusaetze)) if zusaetze else ""
    gewichtung = ("mit sqrt(Videos) gewichteter" if gewichtet
                  else "ungewichteter")
    quelle = f"Quelle: {pfad.name}. " + QUELLE.format(gewichtung=gewichtung)
    return pfad, {"suffix": suffix, "titel": titel, "quelle": quelle}


def lade_daten(pfad):
    d = pd.read_stata(pfad, convert_categoricals=False)
    d = d.dropna(subset=["media_category"])
    d["media_category"] = d["media_category"].astype(int)
    d = d.sort_values(["media_category", "week_var"])
    print(f"[Daten] {pfad.name}: {len(d)} Gruppen-Wochen, "
          f"{d['week_var'].min():%d.%m.%Y} bis {d['week_var'].max():%d.%m.%Y}")
    return d


def bereite_vor(d):
    d = d.copy()
    d["share_energy"] = (d["share_energy_economy"] - d["share_economy"]).clip(lower=0)
    return d


# =========================================================
# SCHRITT 1: Grid – ein Panel je Thema
# =========================================================

def plotte_grid(d, v):
    fig, achsen = plt.subplots(4, 2, figsize=(13, 13), sharex=True)
    for ax, (var, titel) in zip(achsen.flat, THEMEN.items()):
        for code, (label, farbe) in GRUPPEN.items():
            g = d[d["media_category"] == code]
            plotte_geglaettet(ax, g["week_var"], g[var], color=farbe,
                              linewidth=1.8, label=label)
        formatiere_achse(ax)
        ax.set_ylim(bottom=0)
        ax.set_title(titel, loc="left", fontsize=11)
    handles, labels = achsen.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=5, frameon=False,
               bbox_to_anchor=(0.5, 0.965))
    fig.suptitle("Wöchentliche Themenanteile nach Kanaltyp (LOWESS-geglättet, "
                 f"y-Achse je Thema eigen skaliert){v['titel']}", x=0.01, ha="left",
                 fontsize=13)
    fig.text(0.01, 0.005, v["quelle"], fontsize=8, color=INK_MUTED)
    fig.tight_layout(rect=(0, 0.015, 1, 0.94))
    pfad = PFAD_AUSGABE / f"weekly_topic_shares_5types_grid{v['suffix']}.png"
    fig.savefig(pfad, dpi=200)
    plt.close(fig)
    print(f"[Plot] {pfad}")


# =========================================================
# SCHRITT 2: Einzelgrafiken je Thema
# =========================================================

def plotte_einzeln(d, v):
    pfad_einzel = PFAD_AUSGABE / f"topic_shares_5types{v['suffix']}"
    pfad_einzel.mkdir(parents=True, exist_ok=True)
    for var, titel in THEMEN.items():
        fig, ax = plt.subplots(figsize=(11, 5.5))
        for code, (label, farbe) in GRUPPEN.items():
            g = d[d["media_category"] == code]
            plotte_geglaettet(ax, g["week_var"], g[var], color=farbe,
                              linewidth=2, label=label)
        formatiere_achse(ax)
        ax.set_ylim(bottom=0)
        ax.text(KRIEGSBEGINN, ax.get_ylim()[1], " Kriegsbeginn", color=INK_MUTED,
                va="top", ha="left", fontsize=9)
        ax.set_ylabel(f"Anteil {titel} (Kanalmittel)", color=INK_MUTED)
        ax.set_title(f"Wöchentlicher Anteil von Videos zum Thema {titel} nach "
                     f"Kanaltyp (LOWESS-geglättet){v['titel']}", loc="left", fontsize=12)
        ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(1.0, 1.0))
        fig.text(0.01, 0.01, v["quelle"], fontsize=8, color=INK_MUTED)
        fig.tight_layout(rect=(0, 0.03, 1, 1))
        pfad = pfad_einzel / (f"weekly_{var.removeprefix('share_')}_share_5types"
                              f"{v['suffix']}.png")
        fig.savefig(pfad, dpi=200)
        plt.close(fig)
        print(f"[Plot] {pfad}")


# =========================================================
# SCHRITT 3: Heatmap Thema × Monat je Gruppe
# =========================================================

def plotte_heatmap(d, v):
    themen = list(THEMEN)
    # Monatsmittel der Wochenwerte (Woche dem Monat ihres Startdatums zugeordnet)
    m = (d.assign(monat=d["week_var"].dt.to_period("M"))
          .groupby(["media_category", "monat"])[themen].mean())
    maxima = m.max()  # je Thema über alle Gruppen und Monate
    monate = m.index.get_level_values("monat").unique().sort_values()
    x_kante = mdates.date2num(pd.PeriodIndex(list(monate) + [monate[-1] + 1])
                              .to_timestamp())

    fig, achsen = plt.subplots(len(GRUPPEN), 1, figsize=(13, 14), sharex=True)
    for ax, (code, (label, _)) in zip(achsen, GRUPPEN.items()):
        g = m.loc[code].reindex(monate)
        z = (g / maxima).T.values  # Zeilen = Themen
        bild = ax.pcolormesh(x_kante, np.arange(len(themen) + 1), z,
                             cmap="Blues", vmin=0, vmax=1, shading="flat")
        ax.set_yticks(np.arange(len(themen)) + 0.5)
        ax.set_yticklabels([THEMEN[t] for t in themen], fontsize=9)
        ax.invert_yaxis()
        ax.axvline(mdates.date2num(KRIEGSBEGINN), color="#c0392b", linewidth=1.2)
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.tick_params(colors=INK_MUTED, length=0)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_title(f"{label}  (Ø {d.loc[d['media_category'] == code, 'all_vids'].mean():.0f} "
                     "Videos/Woche)", loc="left", fontsize=10)
    leiste = fig.colorbar(bild, ax=achsen, fraction=0.02, pad=0.01)
    leiste.set_label("Monatsanteil relativ zum Themen-Maximum (über alle Gruppen)",
                     color=INK_MUTED)
    max_text = ", ".join(f"{THEMEN[t]} {maxima[t]:.0%}" for t in themen)
    fig.suptitle(f"Themenprominenz nach Kanaltyp und Monat{v['titel']}", x=0.01, ha="left",
                 fontsize=13)
    fig.text(0.01, 0.005, f"Maxima (=1): {max_text}. Rote Linie = Kriegsbeginn.\n"
             + v["quelle"], fontsize=7.5, color=INK_MUTED)
    fig.subplots_adjust(left=0.13, right=0.86, top=0.95, bottom=0.05, hspace=0.35)
    pfad = PFAD_AUSGABE / f"monthly_topic_heatmap_5types{v['suffix']}.png"
    fig.savefig(pfad, dpi=200)
    plt.close(fig)
    print(f"[Plot] {pfad}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vorkrieg", action="store_true",
                        help="nur Kanäle mit sample_vorkrieg == 1")
    parser.add_argument("--gewichtet", action="store_true",
                        help="Kanal-Wochen mit sqrt(Zahl der Videos) gewichtet")
    args = parser.parse_args()
    pfad, v = variante(args.vorkrieg, args.gewichtet)

    PFAD_AUSGABE.mkdir(parents=True, exist_ok=True)
    d = bereite_vor(lade_daten(pfad))
    plotte_grid(d, v)
    plotte_einzeln(d, v)
    plotte_heatmap(d, v)


if __name__ == "__main__":
    main()

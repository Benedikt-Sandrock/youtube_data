"""
Wöchentlicher Kriegsanteil nach fünf Kanaltypen (ÖRR, traditionelle Medien,
alternative Medien links/mitte/rechts).

Eingabe: outputs/stata_rohdaten/weekly_data_5types.dta, erzeugt von
outputs/stata_rohdaten/supply_reaction.do. Dort:
- je Video werden die rel_*-Topic-Indikatoren durch die Zahl der Topics geteilt
  (ein Video mit zwei Topics zählt je 0,5), Videos ohne Topic fallen raus;
- share_war = Kriegsanteil je Kanal-Woche, danach ungewichteter Mittelwert über
  die Kanäle einer Gruppe (jeder Kanal mit Uploads in der Woche zählt gleich);
- Ideologie nach ideo_gesellschaft_baseline: links <= -0,5, rechts >= 0,5,
  mitte dazwischen (nur medientyp 4 = Creator & alternative Medien).
  media_category = . (Partei/Politiker, alternative Medien ohne Baseline) wird
  hier verworfen.

Ausgabe nach outputs/stata_rohdaten/grafiken/:
- weekly_war_share_5types.png         alle fünf Gruppen, LOWESS-geglättet
  (getrennt vor/ab Kriegsbeginn, keine Glättung über den Bruch)
- weekly_war_share_5types_facets.png  je Gruppe ein Panel, Wochenwerte + LOWESS

Ausführen aus dem Repo-Root:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/adhoc/weekly_war_share_5types_plot.py
"""

import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from statsmodels.nonparametric.smoothers_lowess import lowess

from youtube_code.config import OUTPUTS

# =========================================================
# CONFIG
# =========================================================

PFAD_EINGABE = OUTPUTS / "stata_rohdaten" / "weekly_data_5types.dta"
PFAD_AUSGABE = OUTPUTS / "stata_rohdaten" / "grafiken"

KRIEGSBEGINN = pd.Timestamp("2022-02-24")
GLAETTUNG_LOWESS_FRAC = 0.08  # ca. 23 Wochen Fensterbreite bei 286 Wochen

# Gleiche Reihenfolge und Farben wie marktanteil_rohdaten_plots.py
GRUPPEN = {
    1: ("ÖRR", "#2a78d6"),
    2: ("Traditionelle Medien", "#eb6834"),
    3: ("Alternative (links)", "#1baf7a"),
    4: ("Alternative (mitte)", "#eda100"),
    5: ("Alternative (rechts)", "#e87ba4"),
}

INK_MUTED = "#52514e"
GRID = "#e5e4e0"


# =========================================================
# SCHRITT 1: Daten laden
# =========================================================

def lade_daten():
    d = pd.read_stata(PFAD_EINGABE, convert_categoricals=False)
    d = d.dropna(subset=["media_category"])
    d["media_category"] = d["media_category"].astype(int)
    d = d.sort_values(["media_category", "week_var"])
    print(f"[Daten] {len(d)} Gruppen-Wochen, {d['week_var'].min():%d.%m.%Y} bis "
          f"{d['week_var'].max():%d.%m.%Y}")
    return d


def glaette(x, y):
    """LOWESS getrennt vor und ab Kriegsbeginn, damit der Sprung nicht in die
    Vorkriegswochen hinein verschmiert wird. Gibt eine Serie mit NaN an der
    Bruchstelle zurück (die Linie wird dort unterbrochen)."""
    x = pd.Series(pd.to_datetime(x).values)
    y = pd.Series(pd.Series(y).values)
    teile = []
    for maske in [x < KRIEGSBEGINN, x >= KRIEGSBEGINN]:
        xn = mdates.date2num(x[maske])
        # frac relativ zur Gesamtlänge halten (gleiche Fensterbreite in Wochen)
        frac = min(1.0, GLAETTUNG_LOWESS_FRAC * len(x) / maske.sum())
        teile.append(pd.Series(lowess(y[maske], xn, frac=frac, xvals=xn,
                                      return_sorted=False, it=0), index=x[maske].index))
    lücke = pd.Series([float("nan")], index=[teile[0].index[-1] + 0.5])
    return pd.concat([teile[0], lücke, teile[1]]).sort_index()


def plotte_geglaettet(ax, x, y, **kwargs):
    x = pd.Series(pd.to_datetime(x).values)
    s = glaette(x, y)
    xs = pd.concat([x, pd.Series([pd.NaT], index=[s.index[s.isna()][0]])]).sort_index()
    ax.plot(xs.values, s.values, **kwargs)


def formatiere_achse(ax):
    ax.axvline(KRIEGSBEGINN, color=INK_MUTED, linestyle="--", linewidth=1)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=INK_MUTED, length=0)


# =========================================================
# SCHRITT 2: Grafiken
# =========================================================

def plotte_overlay(d):
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for code, (label, farbe) in GRUPPEN.items():
        g = d[d["media_category"] == code]
        plotte_geglaettet(ax, g["week_var"], g["share_war"],
                color=farbe, linewidth=2, label=label)
    formatiere_achse(ax)
    ax.text(KRIEGSBEGINN, ax.get_ylim()[1], " Kriegsbeginn", color=INK_MUTED,
            va="top", ha="left", fontsize=9)
    ax.set_ylabel("Anteil Kriegsvideos (Kanalmittel)", color=INK_MUTED)
    ax.set_title("Wöchentlicher Anteil von Kriegsvideos nach Kanaltyp (LOWESS-geglättet)",
                 loc="left", fontsize=12)
    ax.legend(frameon=False, loc="upper right")
    fig.text(0.01, 0.01, "Quelle: weekly_data_5types.dta. Ungewichteter Mittelwert der "
             "Kanal-Wochenanteile; Topics anteilig gewichtet; Ideologie: "
             "ideo_gesellschaft_baseline, Schnitte ±0,5.", fontsize=8, color=INK_MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    pfad = PFAD_AUSGABE / "weekly_war_share_5types.png"
    fig.savefig(pfad, dpi=200)
    plt.close(fig)
    print(f"[Plot] {pfad}")


def plotte_facets(d):
    fig, achsen = plt.subplots(5, 1, figsize=(11, 12), sharex=True, sharey=True)
    for ax, (code, (label, farbe)) in zip(achsen, GRUPPEN.items()):
        g = d[d["media_category"] == code]
        ax.scatter(g["week_var"], g["share_war"], s=8, color=farbe, alpha=0.35,
                   linewidths=0)
        plotte_geglaettet(ax, g["week_var"], g["share_war"],
                color=farbe, linewidth=2)
        formatiere_achse(ax)
        ax.set_title(f"{label}  (Ø {g['all_vids'].mean():.0f} Videos/Woche)",
                     loc="left", fontsize=10)
    achsen[0].set_ylim(bottom=0)
    fig.suptitle("Wöchentlicher Anteil von Kriegsvideos nach Kanaltyp "
                 "(Punkte = Wochenwerte, Linie = LOWESS)", x=0.01, ha="left", fontsize=12)
    fig.tight_layout()
    pfad = PFAD_AUSGABE / "weekly_war_share_5types_facets.png"
    fig.savefig(pfad, dpi=200)
    plt.close(fig)
    print(f"[Plot] {pfad}")


def main():
    PFAD_AUSGABE.mkdir(parents=True, exist_ok=True)
    d = lade_daten()
    plotte_overlay(d)
    plotte_facets(d)


if __name__ == "__main__":
    main()

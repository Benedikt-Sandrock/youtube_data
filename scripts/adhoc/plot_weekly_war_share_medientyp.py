"""Angebotsreaktion auf den Kriegsbeginn: wöchentlicher Kriegsanteil am Video-Angebot
je Medientyp und je Populismus-Terzil.

Bildet ``outputs/stata_rohdaten/supply_reaction.do`` nach, aber auf Kanal-Ebene,
damit sich Gruppen und Formatfilter frei wählen lassen. Input ist
``outputs/stata_rohdaten/weekly_war_share.dta`` – ein Video-Datensatz nach dem
Topic-Schritt des Do-Files (frühere Version des Do-Files: ``save`` lief nach dem
automatischen ``restore``, deshalb enthält die Datei Videos statt Wochenanteilen).
Die vom aktuellen Do-File erzeugten ``weekly_data_medientyp.dta`` /
``weekly_data_populism.dta`` taugen nicht als Input: Ihnen fehlen Kanal-ID und
Format, und ``weekly_data_populism.dta`` ist nach dem stetigen ``pop_baseline``
kollabiert (267 Werte ≈ ein Kanal je Wert; Kanäle mit gleichem Wert, z. B. 9 × 1/3,
werden dort vermischt). Die Kollabierung:

1. Nur Videos mit mindestens einem ``rel_<topic>_cw == 1`` (Themenvideos).
2. Jedes Video verteilt Gewicht 1 gleichmäßig auf seine Themen
   (``rel_* / n_topics``) – ein Video mit Krieg + USA zählt 0,5 Kriegsvideo.
3. Kanal x Woche (Stata-Woche ``wofd``, Variable ``week_var``): Summe je Thema.
4. ``share_war`` = Kriegsgewicht / alle Themenvideos des Kanals in der Woche.

Gruppierungen:
- **Medientyp** (``medientyp`` aus ``kanaele_roh``).
- **Populismus-Terzile**: Kanäle nach ``pop_baseline`` in drei gleich große Gruppen
  (Grenzen über alle Kanäle mit ``pop_baseline``, für alle Varianten fest; Kanäle
  ohne ``pop_baseline`` fallen heraus, derzeit 111 von 421). Das obere Terzil
  besteht überwiegend aus Creator- und Partei-Kanälen – deshalb zusätzlich die
  Terzil-Grafik nur innerhalb ``medientyp == 4`` (Creator & alternative Medien),
  um Populismus von Medientyp zu trennen.

Je Gruppe zwei Aggregationen (oberes und mittleres Panel):
- **Kanal-Mittel** (wie im Do-File: ``collapse (mean) share_war``): jeder Kanal mit
  mindestens einem Themenvideo in der Woche zählt gleich; Kanäle ohne
  Themenvideo in der Woche fehlen (nicht 0).
- **Gepoolt**: Summe Kriegsgewicht / Summe Themenvideos aller Kanäle der Gruppe
  (große Upload-Kanäle dominieren; analog zum gepoolten Views-Kriegsanteil in
  ``plot_monthly_views_ausgewaehlte_kanaele.py``).
Unteres Panel: Anzahl Kanäle mit Themenvideo je Woche (Zusammensetzung).

Zusätzlich ``weekly_supply_marktanteil_*.png``: Anteil je Gruppe am gesamten
Themenvideo-Angebot / Kriegsvideo-Angebot / übrigen Angebot (analog
``monthly_views_marktanteil_medientyp*.png``, aber Videoanzahl statt Views).

Dünne Linien = Wochenwerte, dicke Linien = zentriertes gleitendes 5-Wochen-Mittel.
Hinweis Stata-Wochen: Woche 52 umfasst 8 (Schaltjahr: 9) Tage – für Anteile
unproblematisch, bei Zählungen (Kanäle) kleiner Ausschlag am Jahresende.

Varianten (Suffix): ohne = alle Formate (wie Do-File); ``long`` = nur
``format == "long"``; ``long_vorkrieg`` = zusätzlich nur ``sample_vorkrieg == 1``.

Ausgaben in ``scripts/adhoc/outputs/`` (``<g>`` = ``medientyp`` | ``populismus``):
- ``weekly_war_share_<g>[_suffix].png``, ``weekly_supply_marktanteil_<g>[_suffix].png``
- ``weekly_war_share_populismus_creator[_suffix].png`` (Terzile nur unter Creator & alt. Medien)

Aufruf: ``.venv/Scripts/python.exe scripts/adhoc/plot_weekly_war_share_medientyp.py``
"""
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from plot_monthly_views_ausgewaehlte_kanaele import (MEDIENTYPEN, OUT_DIR, SERIEN_FARBEN,
                                                     TOPICS_REST, style_achse)

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "outputs" / "stata_rohdaten" / "weekly_war_share.dta"
REL = ["rel_russia_ukraine_war_cw"] + [f"rel_{t}_cw" for t in TOPICS_REST]
FENSTER = 5  # Wochen, zentriert
CREATOR = 4  # medientyp-Code "Creator & alternative Medien"
# Terzil-Farben: sequentiell hell -> dunkel (geordnete Kategorie)
TERZIL_FARBEN = ["#9ec5f0", "#2a78d6", "#0b3a75"]


def lade_videos() -> pd.DataFrame:
    v = pd.read_stata(INPUT, convert_categoricals=False,
                      columns=["channel_id", "week_var", "format", "sample_vorkrieg",
                               "medientyp", "pop_baseline", "n_topics", *REL])
    v = v[v["n_topics"] > 0].dropna(subset=["medientyp"])
    # Do-File hat rel_* bereits durch n_topics geteilt; Zeilensumme muss 1 sein
    summe = v[REL].sum(axis=1)
    if not summe.between(0.999, 1.001).all():
        raise ValueError("rel_* nicht auf n_topics normiert – Input passt nicht zum Do-File")
    v["week_var"] = v["week_var"].astype("datetime64[ns]")
    return v


def populismus_terzile(v: pd.DataFrame) -> tuple[pd.Series, list[float]]:
    """Terzil (0/1/2) je Kanal nach ``pop_baseline`` plus Terzilgrenzen."""
    k = v.drop_duplicates("channel_id").set_index("channel_id")["pop_baseline"].dropna()
    terzil, grenzen = pd.qcut(k, 3, labels=False, retbins=True)
    return terzil, list(grenzen)


def terzil_labels(v: pd.DataFrame, grenzen: list[float]) -> dict[int, str]:
    """Legendenlabels mit Grenzen und Kanalzahl im jeweiligen Teildatensatz."""
    n = v.dropna(subset=["pop_terzil"]).groupby("pop_terzil")["channel_id"].nunique()
    namen = ["niedrig", "mittel", "hoch"]
    return {i: f"Populismus {namen[i]} ({grenzen[i]:.2f}–{grenzen[i + 1]:.2f}, "
               f"{n.get(i, 0)} Kanäle)".replace(".", ",")
            for i in range(3)}


def kanal_wochen(v: pd.DataFrame, gruppe: str) -> pd.DataFrame:
    kw = (v.assign(rest=v[REL[1:]].sum(axis=1))
            .groupby([gruppe, "channel_id", "week_var"])
            .agg(krieg=("rel_russia_ukraine_war_cw", "sum"), rest=("rest", "sum"))
            .reset_index()
            .rename(columns={gruppe: "gruppe"}))
    kw["alle"] = kw["krieg"] + kw["rest"]
    kw["share_war"] = kw["krieg"] / kw["alle"]
    return kw


def wochenraster(df: pd.DataFrame) -> pd.DataFrame:
    """Gruppen-Spalten auf vollständigem Raster der vorhandenen Stata-Wochen."""
    wochen = sorted(df.index.unique())
    return df.reindex(wochen)


def linien(ax, wide: pd.DataFrame, gruppen: dict, farben: list, glatt: bool = True) -> None:
    for (code, label), farbe in zip(gruppen.items(), farben):
        if code not in wide:
            continue
        s = wide[code]
        if glatt:
            ax.plot(s.index, s.values, color=farbe, linewidth=0.6, alpha=0.35)
            s = s.rolling(FENSTER, center=True, min_periods=3).mean()
        ax.plot(s.index, s.values, color=farbe, linewidth=2, label=label)


def prozent_achse(ax, ylabel: str) -> None:
    ax.set_ylim(0, None)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
    ax.set_ylabel(ylabel)


def plot_kriegsanteil(kw: pd.DataFrame, gruppen: dict, farben: list,
                      name: str, titel_gruppe: str, suffix: str) -> Path:
    mittel = wochenraster(kw.pivot_table(index="week_var", columns="gruppe",
                                         values="share_war", aggfunc="mean")) * 100
    sums = kw.groupby(["week_var", "gruppe"])[["krieg", "alle"]].sum()
    gepoolt = wochenraster((sums["krieg"] / sums["alle"]).unstack("gruppe")) * 100
    n_kan = wochenraster(kw.pivot_table(index="week_var", columns="gruppe",
                                        values="channel_id", aggfunc="nunique")).fillna(0)

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 11), sharex=True,
                                        gridspec_kw={"height_ratios": [3, 3, 1.3]})
    linien(ax1, mittel, gruppen, farben)
    prozent_achse(ax1, "Kriegsanteil (Kanal-Mittel)")
    ax1.set_title("Kanal-Mittel: jeder Kanal mit Themenvideo in der Woche zählt gleich "
                  "(wie supply_reaction.do)", loc="left", fontsize=11)
    linien(ax2, gepoolt, gruppen, farben)
    prozent_achse(ax2, "Kriegsanteil (gepoolt)")
    ax2.set_title("Gepoolt: Summe Kriegsvideos / Summe Themenvideos aller Kanäle der Gruppe",
                  loc="left", fontsize=11)
    linien(ax3, n_kan, gruppen, farben, glatt=False)
    ax3.set_ylim(bottom=0)
    ax3.set_ylabel("Kanäle mit\nThemenvideo", fontsize=9)
    for ax in (ax1, ax2, ax3):
        style_achse(ax)
    ax1.legend(frameon=False, fontsize=9, loc="upper right")
    titel = (f"Anteil Kriegsvideos am Themenvideo-Angebot {titel_gruppe}, wöchentlich "
             f"(dick: {FENSTER}-Wochen-Mittel; gestrichelt: Kriegsbeginn)")
    fig.suptitle(titel + (f" – {suffix}" if suffix else ""), x=0.01, ha="left", fontsize=12)
    fig.tight_layout()
    out = OUT_DIR / f"weekly_war_share_{name}{'_' + suffix if suffix else ''}.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_marktanteil(kw: pd.DataFrame, gruppen: dict, farben: list,
                     name: str, titel_gruppe: str, suffix: str) -> Path:
    sums = kw.groupby(["week_var", "gruppe"])[["alle", "krieg", "rest"]].sum()
    panels = {"Alle Themenvideos (Krieg + Rest)": "alle",
              "Nur Kriegsvideos": "krieg",
              "Nur übrige Themenvideos (Rest)": "rest"}

    fig, axes = plt.subplots(3, 1, figsize=(12, 11), sharex=True, sharey=True)
    for ax, (titel, spalte) in zip(axes, panels.items()):
        wide = wochenraster(sums[spalte].unstack("gruppe")).fillna(0)
        glatt = wide.rolling(FENSTER, center=True, min_periods=3).mean()
        anteile = glatt.div(glatt.sum(axis=1), axis=0) * 100
        linien(ax, anteile, gruppen, farben, glatt=False)
        ax.set_ylim(0, 100)
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
        ax.set_ylabel("Anteil am Videoangebot")
        ax.set_title(titel, loc="left", fontsize=11)
        style_achse(ax)
    axes[0].legend(frameon=False, fontsize=9, loc="upper left", ncol=2)
    titel = (f"Angebots-Marktanteil {titel_gruppe} (Anzahl Themenvideos, themengewichtet; "
             f"{FENSTER}-Wochen-Mittel; gestrichelt: Kriegsbeginn)")
    fig.suptitle(titel + (f" – {suffix}" if suffix else ""), x=0.01, ha="left", fontsize=12)
    fig.tight_layout()
    out = OUT_DIR / f"weekly_supply_marktanteil_{name}{'_' + suffix if suffix else ''}.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    v = lade_videos()
    terzil, grenzen = populismus_terzile(v)
    v["pop_terzil"] = v["channel_id"].map(terzil)
    varianten = {"": v,
                 "long": v[v["format"] == "long"],
                 "long_vorkrieg": v[(v["format"] == "long") & (v["sample_vorkrieg"] == 1)]}
    for suffix, teil in varianten.items():
        kw_typ = kanal_wochen(teil, "medientyp")
        kw_pop = kanal_wochen(teil.dropna(subset=["pop_terzil"]), "pop_terzil")
        creator = teil[teil["medientyp"] == CREATOR]
        kw_pop_cr = kanal_wochen(creator.dropna(subset=["pop_terzil"]), "pop_terzil")
        lab_pop, lab_cr = terzil_labels(teil, grenzen), terzil_labels(creator, grenzen)
        outs = [
            plot_kriegsanteil(kw_typ, MEDIENTYPEN, SERIEN_FARBEN, "medientyp", "je Medientyp", suffix),
            plot_marktanteil(kw_typ, MEDIENTYPEN, SERIEN_FARBEN, "medientyp", "je Medientyp", suffix),
            plot_kriegsanteil(kw_pop, lab_pop, TERZIL_FARBEN, "populismus",
                              "je Populismus-Terzil (pop_baseline)", suffix),
            plot_marktanteil(kw_pop, lab_pop, TERZIL_FARBEN, "populismus",
                             "je Populismus-Terzil (pop_baseline)", suffix),
            plot_kriegsanteil(kw_pop_cr, lab_cr, TERZIL_FARBEN, "populismus_creator",
                              "je Populismus-Terzil, nur Creator & alt. Medien", suffix),
        ]
        for out in outs:
            print(f"Gespeichert: {out}")


if __name__ == "__main__":
    main()

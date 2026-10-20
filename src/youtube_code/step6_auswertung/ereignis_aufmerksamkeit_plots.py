# -*- coding: utf-8 -*-
"""
ereignis_aufmerksamkeit_plots.py

Stufe 1 der Ereignisanalyse (deskriptiv): Steigt die Aufmerksamkeit fuer
Russland-Ukraine-Videos nach bestimmten Ereignissen, und fuer welche Gruppen?
Datenbasis ist der zentrale Analysedatensatz outputs/stata_rohdaten/
(videos_roh.dta, kanaele_roh.dta; Spezifikation docs/codebuch_rohdatensatz.md).

Ereignisse
----------
Aus kriegsvideos_zeitreihen_plots.EREIGNISSE. a-d (Kriegsbeginn, Zeitenwende,
Butscha, schwere Waffen) liegen innerhalb von neun Wochen und sind nicht
trennbar; sie bilden zusammen die "Schockphase 2022" mit Anker a (24.02.2022).
e-i werden einzeln betrachtet. Fenster: FENSTER_VOR Wochen vor bis
FENSTER_NACH Wochen nach dem Ereignis; Woche 0 = [Ereignistag, +7 Tage).
Hinweis: Das Vorfenster von e (Gas) enthaelt d (schwere Waffen).

Gruppen
-------
Medientyp x Ideologie wie in marktanteil_rohdaten_plots.bilde_gruppen():
OeRR, traditionelle Medien, alternative Medien links/mitte/rechts nach
ideo_gesellschaft_baseline (Schnitte +-0,5). Partei/Politiker und alternative
Medien ohne Ideologie-Baseline fallen raus.

Kennzahlen je Ereignis x Gruppe x Woche
---------------------------------------
1. Angebot: Anteil der Kriegsvideos an allen Uploads der Gruppe (%).
2. Views-Anteil: Anteil der Kriegsvideos an allen Views der Gruppe (%);
   verbindet Angebot und Nachfrage.
3. Nachfrage (kanalintern): je Kriegsvideo log(views+1) minus Median von
   log(views+1) der Nicht-Kriegsvideos desselben Kanals in derselben Woche;
   davon der Median ueber die Kriegsvideos der Gruppe, als Faktor exp(.)
   dargestellt (1 = so viele Views wie ein typisches anderes Video des Kanals).
   Vergleich innerhalb von Kanal und Woche neutralisiert Kanalgroesse,
   Plattformtrends und die kumulierte Messung der views (gleich lange
   Sammelzeit). Kriegsvideos ohne Nicht-Kriegsvideo des Kanals in der Woche
   fallen hier raus.
Zellen mit < MIN_KRIEGSVIDEOS Kriegsvideos werden fuer 3. ausgeblendet.

Definitionen: Kriegsvideo = rel_russia_ukraine_war_core == "ja" (Titel,
core-Liste); Population format == "long" (wie kriegsvideos_zeitreihen_plots).

Ausgabe nach OUTPUTS / "segment_analysis" / "ereignis_aufmerksamkeit":
- ereignis_angebot.png, ereignis_views_anteil.png, ereignis_nachfrage.png
  (je ein Panel pro Ereignis, Linien = Gruppen)
- ereignis_wochen.csv  (alle Wochenwerte)
- ereignis_aufmerksamkeit.md  (Methodik, Vorher/Nachher-Tabelle je Ereignis
  und Gruppe, Abdeckung der Ereignis-Stichwoerter durch die Kriegsdefinition)

Ausfuehren aus dem Repo-Root:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.ereignis_aufmerksamkeit_plots
"""

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from youtube_code.config import OUTPUTS
from youtube_code.step6_auswertung.kriegsvideos_zeitreihen_plots import EREIGNISSE
from youtube_code.step6_auswertung.marktanteil_rohdaten_plots import (
    KLASSIFIKATIONEN, bilde_gruppen, lade_kanaele,
)

# =========================================================
# CONFIG
# =========================================================

ROHDATEN_PFAD = OUTPUTS / "stata_rohdaten"
PFAD_OUT = OUTPUTS / "segment_analysis" / "ereignis_aufmerksamkeit"

FENSTER_VOR = 6
FENSTER_NACH = 6
VORHER = (-FENSTER_VOR, -1)   # Vergleichsfenster fuer die Tabelle (Wochen, inklusive)
NACHHER = (0, 3)
MIN_KRIEGSVIDEOS = 5
NACHFRAGE_TICKS = [0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4]

SCHOCK_KUERZEL = ["a", "b", "c", "d"]
_ereignis = {k: (pd.Timestamp(d), n) for k, d, n in EREIGNISSE}
ANALYSE_EREIGNISSE = [("a–d", _ereignis["a"][0], "Schockphase 2022 (a–d)")] + [
    (k, t, n) for k, (t, n) in _ereignis.items() if k not in SCHOCK_KUERZEL
]

# Stichwoerter je Ereignis fuer den Abdeckungscheck (Titel, case-insensitive):
# Welcher Anteil der Videos zum Ereignis wird von der Kriegsdefinition erfasst?
EREIGNIS_STICHWORTE = {
    "a–d": r"zeitenwende|butscha|bucha|schwere waffen",
    "e": r"alarmstufe|gasmangel|gasnotfall|notfallplan gas|gasversorgung",
    "f": r"nord ?stream",
    "g": r"selenskyj|selensky|zelensky",
    "h": r"reichweite|taurus",
    "i": r"alaska|gipfel",
}

GRUPPEN = KLASSIFIKATIONEN["medientyp_ideologie"]["gruppen"]
FARBEN = dict(zip(GRUPPEN, KLASSIFIKATIONEN["medientyp_ideologie"]["farben"]))
FARBE_TEXT = "#52514e"
FARBE_GRID = "#e5e4e0"

KENNZAHLEN = {
    "angebot": ("Anteil Kriegsvideos an allen Uploads (%)", "ereignis_angebot.png"),
    "views_anteil": ("Anteil Kriegsvideos an allen Views (%)", "ereignis_views_anteil.png"),
    "nachfrage": ("Views eines Kriegsvideos relativ zu anderen Videos\n"
                  "desselben Kanals in derselben Woche (Faktor, Median)", "ereignis_nachfrage.png"),
}


# =========================================================
# SCHRITT 1: Daten
# =========================================================

def lade_videos(kanaele):
    v = pd.read_stata(ROHDATEN_PFAD / "videos_roh.dta",
                      columns=["channel_id", "titel", "upload_ts", "views", "format",
                               "rel_russia_ukraine_war_core"])
    v["format"] = v["format"].astype(str)
    v["krieg"] = v["rel_russia_ukraine_war_core"].astype(str) == "ja"
    v = v[(v["format"] == "long") & v["views"].notna()]
    v = v.merge(kanaele[["channel_id", "medientyp_ideologie"]], on="channel_id", how="left")
    v = v.rename(columns={"medientyp_ideologie": "gruppe"})
    v = v[v["gruppe"].notna()].copy()
    v["log_views"] = np.log1p(v["views"])
    print(f"[Videos] {len(v)} Long-Videos mit Gruppe; Kriegsvideos: {int(v['krieg'].sum())}")
    return v


def ereignisfenster(v):
    """Videos je Ereignisfenster mit relativer Woche."""
    teile = []
    for kuerzel, datum, name in ANALYSE_EREIGNISSE:
        tage = (v["upload_ts"] - datum).dt.total_seconds() / 86400
        woche = np.floor(tage / 7)
        im = woche.between(-FENSTER_VOR, FENSTER_NACH)
        t = v[im].copy()
        t["woche"] = woche[im].astype(int)
        t["ereignis"] = kuerzel
        teile.append(t)
    f = pd.concat(teile, ignore_index=True)

    # kanalinterne Referenz: Median log_views der Nicht-Kriegsvideos je Kanal x Ereignis x Woche
    ref = (f[~f["krieg"]].groupby(["ereignis", "channel_id", "woche"])["log_views"]
           .median().rename("ref_log_views"))
    f = f.join(ref, on=["ereignis", "channel_id", "woche"])
    f["rel_log_views"] = f["log_views"] - f["ref_log_views"]
    return f


# =========================================================
# SCHRITT 2: Kennzahlen
# =========================================================

def kennzahlen(f, schluessel):
    """Kennzahlen je Zelle aus `schluessel` (gepoolt)."""
    def zelle(d):
        k = d[d["krieg"]]
        rel = k["rel_log_views"].dropna()
        return pd.Series({
            "n_videos": len(d),
            "n_krieg": len(k),
            "n_krieg_mit_referenz": len(rel),
            "angebot": len(k) / len(d) * 100 if len(d) else np.nan,
            "views_anteil": k["views"].sum() / d["views"].sum() * 100 if d["views"].sum() else np.nan,
            "nachfrage": np.exp(rel.median()) if len(rel) >= MIN_KRIEGSVIDEOS else np.nan,
        })
    return f.groupby(schluessel).apply(zelle, include_groups=False).reset_index()


def vorher_nachher(f):
    f = f.copy()
    f["phase"] = np.where(f["woche"].between(*VORHER), "vorher",
                          np.where(f["woche"].between(*NACHHER), "nachher", None))
    f = f[f["phase"].notna()]
    return kennzahlen(f, ["ereignis", "gruppe", "phase"])


# =========================================================
# SCHRITT 3: Grafiken
# =========================================================

def plotte(wochen, kennzahl):
    ylabel, dateiname = KENNZAHLEN[kennzahl]
    n = len(ANALYSE_EREIGNISSE)
    fig, achsen = plt.subplots(2, (n + 1) // 2, figsize=(14, 8), sharex=True)
    for ax, (kuerzel, datum, name) in zip(achsen.flat, ANALYSE_EREIGNISSE):
        w = wochen[wochen["ereignis"] == kuerzel]
        for g in GRUPPEN:
            r = w[w["gruppe"] == g].sort_values("woche")
            ax.plot(r["woche"], r[kennzahl], color=FARBEN[g], linewidth=1.6,
                    marker="o", markersize=3, label=g)
        ax.axvline(-0.5, color=FARBE_TEXT, linestyle="--", linewidth=1)
        if kennzahl == "nachfrage":
            ax.axhline(1, color=FARBE_TEXT, linewidth=0.8)
            ax.set_yscale("log")
            ax.yaxis.set_major_locator(mticker.FixedLocator(NACHFRAGE_TICKS))
            ax.yaxis.set_minor_locator(mticker.NullLocator())
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:g}×".replace(".", ",")))
        else:
            ax.set_ylim(bottom=0)
        ax.set_title(f"{kuerzel}: {name} ({datum:%d.%m.%Y})", fontsize=10)
        ax.grid(axis="y", color=FARBE_GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for s in ["top", "right"]:
            ax.spines[s].set_visible(False)
        ax.tick_params(colors=FARBE_TEXT, labelsize=8)
    for ax in achsen[-1]:
        ax.set_xlabel("Woche relativ zum Ereignis (0 = Ereigniswoche)")
    for ax in achsen[:, 0]:
        ax.set_ylabel(ylabel, fontsize=9)
    for ax in list(achsen.flat)[n:]:
        ax.set_visible(False)
    h, l = achsen.flat[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=len(l), frameon=False, fontsize=9)
    fig.suptitle(f"{ylabel.splitlines()[0]} um Ereignisse – Long-Videos, Kriegsdefinition core",
                 fontsize=12)
    fig.tight_layout(rect=(0, 0.05, 1, 0.97))
    fig.savefig(PFAD_OUT / dateiname, dpi=150)
    plt.close(fig)
    print(f"[Plot] {PFAD_OUT / dateiname}")


# =========================================================
# SCHRITT 4: Markdown
# =========================================================

def stichwort_abdeckung(f):
    zeilen = ["| Ereignis | Stichwörter (Titel) | Videos mit Stichwort (Woche 0–3) | davon als Kriegsvideo erfasst |",
              "|---|---|---|---|"]
    for kuerzel, _, name in ANALYSE_EREIGNISSE:
        muster = EREIGNIS_STICHWORTE.get(kuerzel)
        t = f[(f["ereignis"] == kuerzel) & f["woche"].between(*NACHHER)]
        treffer = t["titel"].str.contains(muster, case=False, regex=True, na=False)
        n = int(treffer.sum())
        anteil = t.loc[treffer, "krieg"].mean() * 100 if n else np.nan
        zeilen.append(f"| {kuerzel}: {name} | `{muster}` | {n} | "
                      f"{'–' if np.isnan(anteil) else f'{anteil:.0f} %'} |")
    return "\n".join(zeilen)


def tabelle_vorher_nachher(vn):
    zeilen = ["| Ereignis | Gruppe | Angebot vorher → nachher (%) | Views-Anteil vorher → nachher (%) | "
              "Nachfrage-Faktor vorher → nachher | Kriegsvideos vorher / nachher |",
              "|---|---|---|---|---|---|"]

    def fmt(x, nachkomma=1):
        return "–" if pd.isna(x) else f"{x:.{nachkomma}f}"

    for kuerzel, _, name in ANALYSE_EREIGNISSE:
        for g in GRUPPEN:
            z = vn[(vn["ereignis"] == kuerzel) & (vn["gruppe"] == g)].set_index("phase")
            if not {"vorher", "nachher"} <= set(z.index):
                continue
            v_, n_ = z.loc["vorher"], z.loc["nachher"]
            zeilen.append(
                f"| {kuerzel} | {g} | {fmt(v_['angebot'])} → {fmt(n_['angebot'])} | "
                f"{fmt(v_['views_anteil'])} → {fmt(n_['views_anteil'])} | "
                f"{fmt(v_['nachfrage'], 2)} → {fmt(n_['nachfrage'], 2)} | "
                f"{int(v_['n_krieg'])} / {int(n_['n_krieg'])} |")
    return "\n".join(zeilen)


def schreibe_md(f, vn, kanaele):
    n_kanaele = kanaele["medientyp_ideologie"].value_counts().reindex(GRUPPEN)
    t = ["# Aufmerksamkeit für Kriegsvideos um Ereignisse (Stufe 1, deskriptiv)", "",
         f"Erzeugt von `src/youtube_code/step6_auswertung/ereignis_aufmerksamkeit_plots.py` "
         f"am {pd.Timestamp.now():%d.%m.%Y}.", "",
         "## Methodik", "",
         "- Datenbasis: `videos_roh.dta`/`kanaele_roh.dta`; Long-Videos (`format == \"long\"`) mit `views`.",
         "- Kriegsvideo: `rel_russia_ukraine_war_core == \"ja\"` (Titel, core-Liste).",
         "- Gruppen: Medientyp × Ideologie wie `marktanteil_rohdaten_plots.bilde_gruppen()` "
         "(alternative Medien nach `ideo_gesellschaft_baseline`, Schnitte ±0,5). Kanäle je Gruppe: "
         + ", ".join(f"{g} {int(n)}" for g, n in n_kanaele.items()) + ".",
         f"- Fenster: {FENSTER_VOR} Wochen vor bis {FENSTER_NACH} Wochen nach dem Ereignis, "
         "Woche 0 = Ereignistag + 6 Tage. a–d (Kriegsbeginn, Zeitenwende, Butscha, schwere Waffen) "
         "sind zur Schockphase 2022 mit Anker 24.02.2022 zusammengefasst; das Vorfenster von e enthält d.",
         "- **Angebot:** Kriegsvideos / alle Uploads der Gruppe. **Views-Anteil:** Views der Kriegsvideos / "
         "alle Views der Gruppe. **Nachfrage-Faktor:** Median über Kriegsvideos von exp(log(views+1) − "
         "Median log(views+1) der Nicht-Kriegsvideos desselben Kanals in derselben Woche); 1 = gleich viele "
         "Views wie ein typisches anderes Video des Kanals. Der kanalinterne Vergleich neutralisiert "
         "Kanalgröße, Plattformtrends und die kumulierte Views-Messung.",
         f"- Nachfrage-Faktor nur bei ≥ {MIN_KRIEGSVIDEOS} Kriegsvideos mit Referenz in der Zelle.",
         f"- Tabelle: vorher = Wochen {VORHER[0]} bis {VORHER[1]}, nachher = Wochen {NACHHER[0]} bis "
         f"{NACHHER[1]}, jeweils gepoolt (nicht Mittel der Wochenwerte).",
         "- **Rein deskriptiv, keine Inferenz.** Bei 6 Ereignissen × 5 Gruppen × 3 Kennzahlen sind zufällige "
         "Ausschläge zu erwarten; belastbar erst mit Placebo-Ereignissen (Stufe 2). Vor Kriegsbeginn gibt es "
         "kaum Kriegsvideos, daher ist das Vorfenster der Schockphase nahe 0 bzw. leer.",
         "",
         "## Abdeckung der Ereignis-Stichwörter durch die Kriegsdefinition", "",
         "Anteil der Videos mit ereignistypischem Stichwort im Titel (Wochen 0–3), die auch als "
         "Kriegsvideo zählen. Ein niedriger Wert heißt: Die Aufmerksamkeit für dieses Ereignis "
         "wird von der Kriegsdefinition nur teilweise erfasst.", "",
         stichwort_abdeckung(f), "",
         "## Vorher/Nachher je Ereignis und Gruppe", "",
         tabelle_vorher_nachher(vn), ""]
    pfad = PFAD_OUT / "ereignis_aufmerksamkeit.md"
    pfad.write_text("\n".join(t), encoding="utf-8")
    print(f"[Markdown] {pfad}")


# =========================================================
# MAIN
# =========================================================

def main():
    PFAD_OUT.mkdir(parents=True, exist_ok=True)
    kanaele, _ = bilde_gruppen(lade_kanaele())
    v = lade_videos(kanaele)
    f = ereignisfenster(v)
    wochen = kennzahlen(f, ["ereignis", "gruppe", "woche"])
    for k in KENNZAHLEN:
        plotte(wochen, k)
    wochen.to_csv(PFAD_OUT / "ereignis_wochen.csv", index=False)
    schreibe_md(f, vorher_nachher(f), kanaele)


if __name__ == "__main__":
    main()

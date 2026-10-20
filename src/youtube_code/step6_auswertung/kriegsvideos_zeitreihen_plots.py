# -*- coding: utf-8 -*-
"""
kriegsvideos_zeitreihen_plots.py

Deskriptive Zeitreihen der Russland-Ukraine-Videos auf Basis des zentralen
Analysedatensatzes outputs/stata_rohdaten/videos_roh.dta (erzeugt von
export_stata_rohdaten.py, Spezifikation docs/codebuch_rohdatensatz.md).
Noch ohne Gruppentrennung (alle Kanaele zusammen).

Kennzahlen je Kalendermonat (`monat`, UTC):
1. Gesamtviews (Summe `views`)
2. Anzahl Videos
3. Mittelwert und Median der Views je Video

Jede Kennzahl wird fuer drei Reihen berechnet: Kriegsvideos (dicke Linie)
sowie zum Vergleich alle Videos und politics_general-Videos (duenne Linien).
Bei Summe und Anzahl liegen die Reihen um Groessenordnungen auseinander; das
linke Panel zeigt sie deshalb auf einer logarithmischen Achse, das rechte
Panel setzt sie in Relation: Anteil der Kriegsvideos (dick) und der
politics_general-Videos (duenn) an allen Videos in %, auf einer gemeinsamen
Achse. politics_general ist keine Obermenge der Kriegsvideos (geringe
Ueberschneidung, siehe Methodik-Datei), ein direkter Quotient Krieg/politics_general
waere daher kein Teilmengenanteil und wird nur in der Tabelle berichtet.

Definitionen
------------
- Kriegsvideos: rel_russia_ukraine_war_<def> == "ja"
- politics_general: rel_politics_general_<def> == "ja"
  (Titel-Stichwortsuche aus topic_keywords; <def> = "core" als Hauptdefinition,
  "cw" = core+wide als Robustheit, je Definition ein Satz Grafiken)
- Population: format == "long" (YouTube-Format, ohne Shorts und Livestreams;
  seit 14.10.2026 statt min_dauer == "ja"), views vorhanden, Monate
  01/2021 bis 06/2026 (vollstaendig abgedeckt).
- Mittelwert/Median der Kriegsvideos nur fuer Monate mit >= MIN_VIDEOS_MITTEL
  Kriegsvideos (vor Kriegsbeginn sehr duenn besetzt).

Ereignisse (EREIGNISSE, a-i: Kriegsbeginn bis Gipfel Trump-Putin) sind als
duenne vertikale Linien mit Buchstaben-Kuerzel eingezeichnet, die Erlaeuterung
steht in einer Fusszeile. Monatswerte werden in der Monatsmitte gezeichnet.

Achtung: `views` sind kumulierte Aufrufe zum Abrufzeitpunkt (2026). Aeltere
Videos hatten laenger Zeit, Views zu sammeln; der Verlauf ist daher kein
reiner Nachfrage-Zeitverlauf (gilt fuer alle drei Reihen gleichermassen, die
Anteile im rechten Panel sind davon weniger betroffen).

Ausgabe nach OUTPUTS / "segment_analysis" / "plots_kriegsvideos_zeitreihen":
- kriegsvideos_views_summe_<def>.png
- kriegsvideos_anzahl_<def>.png
- kriegsvideos_views_mittel_median_<def>.png
- kriegsvideos_zeitreihen_monat.csv  (alle Monatswerte, Long-Format)
- kriegsvideos_zeitreihen_methodik.md  (Methodik, Fallzahlen, Phasenwerte)

Ausfuehren aus dem Repo-Root:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.kriegsvideos_zeitreihen_plots
"""

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from youtube_code.config import OUTPUTS
from youtube_code.step6_auswertung.prepare_channel_scores import KRIEGSBEGINN

# =========================================================
# CONFIG
# =========================================================

ROHDATEN_PFAD = OUTPUTS / "stata_rohdaten"
PFAD_PLOTS = OUTPUTS / "segment_analysis" / "plots_kriegsvideos_zeitreihen"

MONAT_MIN = pd.Timestamp("2021-01-01")
MONAT_MAX = pd.Timestamp("2026-06-01")
MIN_VIDEOS_MITTEL = 20

DEFINITIONEN = {"core": "core-Liste", "cw": "core+wide"}

# Reihen: (Schluessel, Label, Farbe, Linienbreite). Farben = erste drei Slots der
# validierten Referenzpalette (wie marktanteil_rohdaten_plots.py), feste Reihenfolge.
REIHEN = [
    ("krieg", "Russland-Ukraine-Videos", "#2a78d6", 2.4),
    ("politik", "politics_general-Videos", "#eb6834", 1.1),
    ("alle", "alle Videos", "#1baf7a", 1.1),
]
FARBE_TEXT = "#52514e"
FARBE_GRID = "#e5e4e0"
FARBE_EREIGNIS = "#9a9893"

# Ereignisse als duenne vertikale Linien; Kuerzel an der Linie, Erlaeuterung
# als Fusszeile (a/b und c/d liegen auf der Monatsachse zu dicht fuer Volltext).
EREIGNISSE = [
    ("a", "2022-02-24", "Kriegsbeginn"),
    ("b", "2022-02-27", "Zeitenwende-Rede"),
    ("c", "2022-04-03", "Butscha"),
    ("d", "2022-04-26", "erste Zusage schwerer Waffen"),
    ("e", "2022-06-23", "Alarmstufe Notfallplan Gas"),
    ("f", "2022-09-26", "Sprengung Nord Stream"),
    ("g", "2025-02-28", "Eklat Trump–Selenskyj"),
    ("h", "2025-05-26", "keine Reichweitenbeschränkung mehr"),
    ("i", "2025-08-15", "Gipfel Trump–Putin"),
]
EREIGNIS_MIN_ABSTAND_TAGE = 30   # naeher beieinander -> Kuerzel versetzt

PHASEN = {
    "Vorkrieg (01/2021–01/2022)": ("2021-01-01", "2022-01-01"),
    "02/2022–01/2023": ("2022-02-01", "2023-01-01"),
    "02/2023–01/2024": ("2023-02-01", "2024-01-01"),
    "02/2024–01/2025": ("2024-02-01", "2025-01-01"),
    "02/2025–06/2026": ("2025-02-01", "2026-06-01"),
}


# =========================================================
# SCHRITT 1: Daten laden
# =========================================================

def lade_videos():
    spalten = ["video_id", "monat", "views", "format", "format_derived"]
    for d in DEFINITIONEN:
        spalten += [f"rel_russia_ukraine_war_{d}", f"rel_politics_general_{d}"]
    v = pd.read_stata(ROHDATEN_PFAD / "videos_roh.dta", columns=spalten)
    for c in spalten[3:]:  # format, format_derived und die rel_*-Spalten
        v[c] = v[c].astype(str)
    n_roh = len(v)
    v = v[v["format"] == "long"]
    n_ohne_views = int(v["views"].isna().sum())
    v = v[v["views"].notna() & v["monat"].between(MONAT_MIN, MONAT_MAX)]
    print(f"[Videos] {len(v)} von {n_roh} Videos (format long, Fenster "
          f"{MONAT_MIN:%m/%Y}–{MONAT_MAX:%m/%Y}; {n_ohne_views} ohne views verworfen); davon format_derived: {int((v['format_derived'] == 'ja').sum())}")
    return v


# =========================================================
# SCHRITT 2: Monatswerte
# =========================================================

def monatswerte(v, definition):
    masken = {
        "krieg": v[f"rel_russia_ukraine_war_{definition}"] == "ja",
        "politik": v[f"rel_politics_general_{definition}"] == "ja",
        "alle": pd.Series(True, index=v.index),
    }
    teile = []
    for key, maske in masken.items():
        g = v[maske].groupby("monat")["views"].agg(
            views_summe="sum", n_videos="size", views_mittel="mean", views_median="median")
        g = g.reindex(pd.date_range(MONAT_MIN, MONAT_MAX, freq="MS"))
        g["n_videos"] = g["n_videos"].fillna(0)
        g["views_summe"] = g["views_summe"].fillna(0)
        g.index.name = "monat"
        g["reihe"] = key
        teile.append(g.reset_index())
    m = pd.concat(teile, ignore_index=True)
    m["definition"] = definition

    # Mittelwert/Median bei zu duenn besetzten Monaten ausblenden
    duenn = m["n_videos"] < MIN_VIDEOS_MITTEL
    m.loc[duenn, ["views_mittel", "views_median"]] = np.nan

    # Anteile der Kriegsvideos an den Vergleichsreihen
    breit = m.pivot(index="monat", columns="reihe", values=["views_summe", "n_videos"])
    anteile = pd.DataFrame({
        "anteil_views_alle": breit[("views_summe", "krieg")] / breit[("views_summe", "alle")] * 100,
        "anteil_views_politik": breit[("views_summe", "krieg")] / breit[("views_summe", "politik")] * 100,
        "anteil_n_alle": breit[("n_videos", "krieg")] / breit[("n_videos", "alle")] * 100,
        "anteil_n_politik": breit[("n_videos", "krieg")] / breit[("n_videos", "politik")] * 100,
        "anteil_views_politik_an_alle": breit[("views_summe", "politik")] / breit[("views_summe", "alle")] * 100,
        "anteil_n_politik_an_alle": breit[("n_videos", "politik")] / breit[("n_videos", "alle")] * 100,
    }).reset_index()
    overlap = int(((masken["krieg"]) & (masken["politik"])).sum())
    return m, anteile, overlap, {k: int(mk.sum()) for k, mk in masken.items()}


# =========================================================
# SCHRITT 3: Grafiken
# =========================================================

def mitte(monat):
    """Monatswerte in der Monatsmitte zeichnen, damit sie zu den taggenauen
    Ereignislinien passen (der Wert gilt fuer den ganzen Monat)."""
    return monat + pd.Timedelta(days=14)


def ereignisse_zeichnen(ax):
    ebene, letztes = 0, None
    for kuerzel, datum, _ in EREIGNISSE:
        t = pd.Timestamp(datum)
        ebene = 1 - ebene if letztes is not None and (t - letztes).days < EREIGNIS_MIN_ABSTAND_TAGE else 0
        letztes = t
        kriegsbeginn = t == pd.Timestamp(KRIEGSBEGINN)
        ax.axvline(t, color=FARBE_TEXT if kriegsbeginn else FARBE_EREIGNIS,
                   linestyle="--" if kriegsbeginn else "-",
                   linewidth=1 if kriegsbeginn else 0.7, zorder=1)
        ax.text(t + pd.Timedelta(days=8), 0.99 - 0.055 * ebene, kuerzel,
                transform=ax.get_xaxis_transform(), va="top", ha="left",
                fontsize=8, fontweight="bold", color=FARBE_TEXT, zorder=4,
                bbox=dict(facecolor="white", edgecolor="none", pad=0.6))


def ereignis_fusszeile(fig):
    teile = [f"{k} {name} ({pd.Timestamp(d):%d.%m.%Y})" for k, d, name in EREIGNISSE]
    zeilen = ["   ".join(teile[:5]), "   ".join(teile[5:])]
    fig.text(0.5, 0.012, "\n".join(zeilen), ha="center", va="bottom", fontsize=7.5,
             color=FARBE_TEXT, linespacing=1.5)


def achse_stylen(ax):
    ereignisse_zeichnen(ax)
    ax.grid(axis="y", color=FARBE_GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=FARBE_TEXT, labelsize=8)


def zahl_format(x, _pos=None):
    if x >= 1e9:
        return f"{x / 1e9:g} Mrd."
    if x >= 1e6:
        return f"{x / 1e6:g} Mio."
    if x >= 1e3:
        return f"{x / 1e3:g} Tsd."
    return f"{x:g}"


def linien(ax, m, spalte):
    for key, label, farbe, lw in REIHEN:
        r = m[m["reihe"] == key].sort_values("monat")
        ax.plot(mitte(r["monat"]), r[spalte], color=farbe, linewidth=lw, label=label,
                zorder=3 if key == "krieg" else 2)


def plot_absolut_und_anteil(m, anteile, spalte, anteil_prefix, titel, ylabel, dateiname, def_label):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6))
    linien(ax1, m[m[spalte] > 0], spalte)
    ax1.set_yscale("log")
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(zahl_format))
    ax1.set_ylabel(f"{ylabel} (log. Skala)")
    ax1.set_title("Absolut", fontsize=11)

    a = anteile.sort_values("monat")
    (_, _, f_krieg, lw_krieg), (_, _, f_pol, lw_pol) = REIHEN[0], REIHEN[1]
    ax2.plot(mitte(a["monat"]), a[f"{anteil_prefix}_politik_an_alle"], color=f_pol, linewidth=lw_pol, zorder=2)
    ax2.plot(mitte(a["monat"]), a[f"{anteil_prefix}_alle"], color=f_krieg, linewidth=lw_krieg, zorder=3)
    ax2.set_ylim(bottom=0)
    ax2.set_ylabel("Anteil an allen Videos (%)")
    ax2.set_title("Anteil an allen Videos", fontsize=11)

    for ax in (ax1, ax2):
        achse_stylen(ax)
    h, l = ax1.get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", bbox_to_anchor=(0.5, 0.075), ncol=len(l),
               frameon=False, fontsize=9)
    ereignis_fusszeile(fig)
    fig.suptitle(f"{titel} je Monat – Stichwortdefinition {def_label}, nur Long-Videos",
                 fontsize=12)
    fig.tight_layout(rect=(0, 0.13, 1, 0.97))
    speichern(fig, dateiname)


def plot_mittel_median(m, dateiname, def_label):
    fig, achsen = plt.subplots(1, 2, figsize=(13, 6), sharey=True)
    for ax, (spalte, titel) in zip(achsen, [("views_mittel", "Mittelwert"),
                                            ("views_median", "Median")]):
        linien(ax, m, spalte)
        ax.set_title(f"{titel} der Views je Video", fontsize=11)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(zahl_format))
        achse_stylen(ax)
    achsen[0].set_ylim(bottom=0)
    achsen[0].set_ylabel("Views je Video")
    h, l = achsen[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", bbox_to_anchor=(0.5, 0.075), ncol=len(l),
               frameon=False, fontsize=9)
    ereignis_fusszeile(fig)
    fig.suptitle(f"Views je Video – Stichwortdefinition {def_label}, nur Long-Videos "
                 f"(Monate mit < {MIN_VIDEOS_MITTEL} Videos ausgeblendet)", fontsize=12)
    fig.tight_layout(rect=(0, 0.13, 1, 0.97))
    speichern(fig, dateiname)


def speichern(fig, dateiname):
    PFAD_PLOTS.mkdir(parents=True, exist_ok=True)
    fig.savefig(PFAD_PLOTS / dateiname, dpi=150)
    plt.close(fig)
    print(f"[Plot] {PFAD_PLOTS / dateiname}")


# =========================================================
# SCHRITT 4: Methodik-Datei
# =========================================================

def tsd(n):
    """Ganzzahl mit deutschem Tausenderpunkt."""
    return f"{n:,.0f}".replace(",", ".")


def zahl_tabelle(x):
    if pd.isna(x):
        return "–"
    for grenze, einheit in [(1e9, "Mrd."), (1e6, "Mio."), (1e3, "Tsd.")]:
        if x >= grenze:
            return f"{x / grenze:.1f} {einheit}".replace(".", ",", 1)
    return f"{x:.0f}"


def phasentabelle(m, anteile):
    zeilen = []
    for phase, (a, b) in PHASEN.items():
        im = m["monat"].between(pd.Timestamp(a), pd.Timestamp(b))
        k = m[im & (m["reihe"] == "krieg")]
        an = anteile[anteile["monat"].between(pd.Timestamp(a), pd.Timestamp(b))]
        zeilen.append({
            "Phase": phase,
            "Kriegsvideos/Monat": tsd(k['n_videos'].mean()),
            "Kriegsviews/Monat": zahl_tabelle(k["views_summe"].mean()),
            "Krieg: Views-Anteil an alle (%)": f"{an['anteil_views_alle'].mean():.1f}",
            "Krieg: Anzahl-Anteil an alle (%)": f"{an['anteil_n_alle'].mean():.1f}",
            "pol.: Views-Anteil an alle (%)": f"{an['anteil_views_politik_an_alle'].mean():.1f}",
            "Krieg-Views / pol.-Views (%)": f"{an['anteil_views_politik'].mean():.0f}",
            "Median-Views Krieg (Ø Monat)": zahl_tabelle(k["views_median"].mean()),
        })
    df = pd.DataFrame(zeilen)
    kopf = "| " + " | ".join(df.columns) + " |"
    trenn = "|" + "---|" * len(df.columns)
    rumpf = ["| " + " | ".join(str(x) for x in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([kopf, trenn, *rumpf])


def schreibe_methodik(ergebnisse, n_gesamt, n_derived):
    t = ["# Kriegsvideos: Views und Anzahl über die Zeit", "",
         f"Erzeugt von `src/youtube_code/step6_auswertung/kriegsvideos_zeitreihen_plots.py` "
         f"am {pd.Timestamp.now():%d.%m.%Y}.", "",
         "## Methodik", "",
         "- Datenbasis: `outputs/stata_rohdaten/videos_roh.dta`, alle Kanäle, keine Gruppentrennung.",
         f"- Population: `format == \"long\"` (ohne Shorts und Livestreams), `views` vorhanden, Monate "
         f"{MONAT_MIN:%m/%Y}–{MONAT_MAX:%m/%Y} (`monat`, UTC): {tsd(n_gesamt)} Videos.",
         f"- Davon {tsd(n_derived)} mit `format_derived == \"ja\"` (WELT-Videos ohne Format, per Ausschluss "
         "als long gesetzt; können gelöschte/private Videos einschließen).",
         "- Abweichung zur früheren Population `min_dauer == \"ja\"`: Long-Videos unter 181 s bzw. ohne "
         "bekannte Dauer sind jetzt enthalten, Livestreams ≥ 181 s nicht mehr.",
         "- Kriegsvideos: `rel_russia_ukraine_war_<def>`, Vergleich: `rel_politics_general_<def>` "
         "und alle Videos (Titel-Stichwortsuche; core = Hauptdefinition, cw = core+wide als Robustheit).",
         "- Summe und Anzahl: links absolut auf log. Achse, rechts Anteil von Kriegs- und politics_general-Videos "
         "an allen Videos. politics_general ist keine Obermenge der Kriegsvideos (Überschneidung siehe unten); "
         "der Quotient Krieg/politics_general steht nur in der Tabelle und kann > 100 % sein.",
         f"- Mittelwert/Median nur für Monate mit ≥ {MIN_VIDEOS_MITTEL} Videos der jeweiligen Reihe.",
         "- `views` sind kumuliert zum Abrufzeitpunkt (2026); ältere Videos hatten länger Zeit, "
         "Views zu sammeln. Mittelwerte sind stark von einzelnen viralen Videos getrieben, der Median ist robuster.",
         ""]
    for d, (n, overlap) in ergebnisse.items():
        m, anteile = n["m"], n["anteile"]
        t += [f"## Definition {DEFINITIONEN[d]} (`{d}`)", "",
              f"- Kriegsvideos: {tsd(n['n']['krieg'])}; politics_general: {tsd(n['n']['politik'])}; "
              f"beides: {tsd(overlap)} ({overlap / max(n['n']['krieg'], 1) * 100:.1f} % der Kriegsvideos)",
              "", "Phasenmittel (ungewichtete Mittel der Monatswerte):", "",
              phasentabelle(m, anteile), ""]
    pfad = PFAD_PLOTS / "kriegsvideos_zeitreihen_methodik.md"
    pfad.write_text("\n".join(t), encoding="utf-8")
    print(f"[Methodik] {pfad}")


# =========================================================
# MAIN
# =========================================================

def main():
    v = lade_videos()
    ergebnisse, alle_monate = {}, []
    for d, d_label in DEFINITIONEN.items():
        m, anteile, overlap, n = monatswerte(v, d)
        print(f"[{d}] Kriegsvideos {n['krieg']}, politics_general {n['politik']}, Überschneidung {overlap}")
        plot_absolut_und_anteil(m, anteile, "views_summe", "anteil_views", "Gesamtviews",
                                "Views (Summe)", f"kriegsvideos_views_summe_{d}.png", d_label)
        plot_absolut_und_anteil(m, anteile, "n_videos", "anteil_n", "Anzahl Videos",
                                "Videos", f"kriegsvideos_anzahl_{d}.png", d_label)
        plot_mittel_median(m, f"kriegsvideos_views_mittel_median_{d}.png", d_label)
        ergebnisse[d] = ({"m": m, "anteile": anteile, "n": n}, overlap)
        alle_monate.append(m.merge(anteile, on="monat", how="left"))
    pd.concat(alle_monate).to_csv(PFAD_PLOTS / "kriegsvideos_zeitreihen_monat.csv", index=False)
    schreibe_methodik(ergebnisse, len(v), int((v["format_derived"] == "ja").sum()))


if __name__ == "__main__":
    main()

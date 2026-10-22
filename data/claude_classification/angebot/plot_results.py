"""Grafiken zur Angebotsstudie (Claude-Klassifikation) auf Videoebene.

Liest ``video_results.csv`` (erzeugt von ``process_results.py``) und erstellt:

1. Kriegsaspekte (``plots_kriegsaspekte/<gruppierung>/``):
   Anteil der Videos mit Ukraine-Krieg-Thema, in denen der jeweilige Kriegsaspekt vorkommt, und/oder
   absolute Anzahl dieser Videos (Dateien mit Präfix ``anzahl_``; Konstante ``KRIEG_MASSE``) –
   wöchentlich je Aspekt, als Small-Multiples-Übersicht und als Balken für die Zeit ab Kriegsbeginn.

2. Establishment-Kritik nach Thema (``plots_establishment/<gruppierung>/<zeiteinheit>/``):
   Eine Grafik pro Thema. Ein Video gehört zu einem Thema, wenn das Thema in mindestens einem
   Segment vorkommt (``thema_<x> > 0``). Je Thema sechs Panels nach Medientyp und Zeiteinheit:
   Anteil ``estab_status == bewertend``, Anteil ``estab_status == deskriptiv``, Ø ``estab_score``
   (nur Videos mit Bewertung) und Anteil der Videos je ``estab_intensitaet``-Stufe
   (sachlich / abwertend / delegitimierung). Zusätzlich ``kennzahlen.csv`` mit allen Werten und Fallzahlen.

   Achtung: Die Establishment-Variablen sind in ``process_results.py`` auf Videoebene aggregiert
   (Status/Intensität = stärkste Ausprägung über alle Segmente, Score = wortgewichteter Mittelwert).
   Sie beziehen sich also auf das ganze Video, nicht nur auf die Segmente des jeweiligen Themas.

3. Establishment: Ukraine-Krieg vs. andere Videos (``plots_establishment/<gruppierung>/krieg_vs_andere_<zeiteinheit>/``):
   Dieselben sechs Kennzahlen wie in 2. im Zeitverlauf (wöchentlich oder monatlich), Videos mit Ukraine-Krieg-Thema
   (in ≥ 1 Segment, durchgezogen) vs. alle übrigen Videos (gestrichelt), Farbe = Medientyp. Plus ``kennzahlen.csv``.

Medientypen: entweder Mainstream (ÖRR + Traditionell) vs. Alternativ oder ÖRR / Traditionell / Alternativ
(Konstante ``MEDIENTYP_GRUPPIERUNG``).
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd

# ===================== KONFIGURATION =====================
INPUT_FILE = Path("video_results.csv")      # Videodatensatz aus process_results.py
MEDIENTYP_GRUPPIERUNG = "mainstream"        # "mainstream" (ÖRR + Traditionell zusammen) | "drei" (ÖRR, Traditionell, Alternativ)
PLOT_KRIEGSASPEKTE = True                   # True | False
PLOT_ESTABLISHMENT = True                   # True | False
PLOT_ESTAB_KRIEG_VS_ANDERE = True           # True | False: Zeitverlauf Ukraine-Krieg-Videos vs. alle anderen Videos

# Kriegsaspekte
KRIEG_PLOT_DIR = Path("plots_kriegsaspekte")   # Ausgabeordner
KRIEG_MIN_N_WEEK = 5                           # int >= 1: min. Kriegsvideos pro Woche & Medientyp, sonst Lücke (nur Anteile)
KRIEG_MASSE = ["anteil", "anzahl"]             # Teilmenge von ["anteil", "anzahl"]: Anteil an Kriegsvideos und/oder
                                               # absolute Anzahl Videos mit dem Aspekt (Dateien mit Präfix "anzahl_")

# Establishment
ESTAB_PLOT_DIR = Path("plots_establishment")   # Ausgabeordner
ESTAB_ZEITEINHEIT = "phase"                    # "phase" (Vorher/Eskalation/Kriegsbeginn) | "monat" | "woche"
ESTAB_THEMEN = None                            # None = alle Themen, sonst Liste ohne Präfix, z.B. ["corona", "migration"]
ESTAB_MIN_N = 5                                # int >= 1: min. Videos pro Zelle (Zeiteinheit x Medientyp), sonst kein Wert
ESTAB_INTENS_BASIS = "alle"                    # "alle" = Anteil an allen Videos des Themas
                                               # "negativ" = Anteil an Videos mit negativer Bewertung (Intensität kodiert)
VERGLEICH_ZEITEINHEIT = "woche"                # "woche" | "monat": Zeitachse für Krieg-vs.-andere-Vergleich
                                               # (nutzt ebenfalls ESTAB_MIN_N und ESTAB_INTENS_BASIS)
# ==========================================================

KRIEGSBEGINN = pd.to_datetime("2022-02-24")
PHASEN = ["Vorher", "Eskalation", "Kriegsbeginn"]

MEDIENTYP_LABELS = {"oerr": "ÖRR", "traditionell": "Traditionell", "alternativ_rechts": "Alternativ",
                    "mainstream": "Mainstream"}
MEDIENTYP_COLORS = {"oerr": "#2a78d6", "traditionell": "#eb6834", "alternativ_rechts": "#1baf7a",
                    "mainstream": "#2a78d6"}
INTENS_STUFEN = ["sachlich", "abwertend", "delegitimierung"]


# ===================== HILFSFUNKTIONEN =====================

def load_videos():
    df = pd.read_csv(INPUT_FILE)
    df["datum_lokal"] = pd.to_datetime(df["datum_lokal"])
    if MEDIENTYP_GRUPPIERUNG == "mainstream":
        df["medientyp"] = df["medientyp"].replace(["oerr", "traditionell"], "mainstream")
    return df


def active_types(df):
    """Medientypen, die nach der (optionalen) Aggregation tatsächlich vorkommen, in fester Reihenfolge."""
    return [t for t in MEDIENTYP_LABELS if t in set(df["medientyp"])]


def gruppierung_dir():
    return "mainstream_vs_alternativ" if MEDIENTYP_GRUPPIERUNG == "mainstream" else "drei_medientypen"


def label_from_col(col, prefix):
    return col.removeprefix(prefix).replace("_", " ").capitalize()


def style_axis(ax, percent = True):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis = "y", color = "#e5e5e3", linewidth = 0.8)
    ax.set_axisbelow(True)
    if percent:
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals = 0))


def add_periode(df, zeiteinheit):
    """Spalte 'periode' gemäß zeiteinheit ("phase" | "monat" | "woche")."""
    df = df.copy()
    if zeiteinheit == "phase":
        df["periode"] = pd.Categorical(df["phase"], categories = PHASEN, ordered = True)
    elif zeiteinheit == "monat":
        df["periode"] = df["datum_lokal"].dt.to_period("M").dt.start_time
    else:
        df["periode"] = df["datum_lokal"].dt.to_period("W").dt.start_time
    return df


# ===================== 1. KRIEGSASPEKTE =====================
# Kriegsaspekte werden nur in Segmenten mit Ukraine-Kriegsbezug kodiert (krieg_aspekt_* = 1 impliziert
# thema_krieg_ukraine > 0). Daher: Anteil der Videos, die den Ukraine-Krieg thematisieren, in denen
# der jeweilige Aspekt vorkommt – nach Medientyp, wöchentlich und für die Zeit ab Kriegsbeginn.

def plot_kriegsaspekte(df_video):
    aspect_cols = sorted(c for c in df_video.columns if c.startswith("krieg_aspekt_"))
    war_videos = df_video[df_video["thema_krieg_ukraine"] > 0].copy()
    war_videos["woche"] = war_videos["datum_lokal"].dt.to_period("W").dt.start_time
    types = active_types(war_videos)

    plot_dir = KRIEG_PLOT_DIR / gruppierung_dir()
    plot_dir.mkdir(parents = True, exist_ok = True)

    week_n = war_videos.groupby(["woche", "medientyp"]).size().unstack()
    week_values = {"anteil": war_videos.groupby(["woche", "medientyp"])[aspect_cols].mean(),
                   "anzahl": war_videos.groupby(["woche", "medientyp"])[aspect_cols].sum()}
    # Mass -> (Dateipräfix, y-Achsen-Beschriftung, Titelanfang)
    mass_info = {"anteil": ("", "Anteil an Videos mit Ukraine-Krieg-Thema",
                            "Anteil der Ukraine-Kriegsvideos mit dem jeweiligen Aspekt"),
                 "anzahl": ("anzahl_", "Anzahl Videos mit dem Aspekt",
                            "Anzahl der Videos mit dem jeweiligen Aspekt")}

    def aspect_label(col):
        return label_from_col(col, "krieg_aspekt_")

    def plot_weekly(ax, col, mass, show_legend):
        for typ in types:
            series = week_values[mass][col].xs(typ, level = "medientyp")
            if mass == "anteil":
                series = series.where(week_n[typ].reindex(series.index) >= KRIEG_MIN_N_WEEK)
            else:
                series = series.reindex(week_n.index, fill_value = 0)   # Woche ohne Kriegsvideos = 0, nicht Lücke
            ax.plot(series.index, series.values, color = MEDIENTYP_COLORS[typ], linewidth = 2,
                    marker = "o", markersize = 4, label = MEDIENTYP_LABELS[typ])
        ax.axvline(KRIEGSBEGINN, color = "#8a8985", linestyle = "--", linewidth = 1)
        ax.set_ylim(bottom = 0)
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        style_axis(ax, percent = (mass == "anteil"))
        if show_legend:
            ax.legend(frameon = False, fontsize = 9)

    after = war_videos[war_videos["datum_lokal"] >= KRIEGSBEGINN]
    after_n = after["medientyp"].value_counts()

    for mass in KRIEG_MASSE:
        prefix, ylabel, title = mass_info[mass]
        luecke = (f"Lücke bei < {KRIEG_MIN_N_WEEK} Kriegsvideos pro Woche und Medientyp. " if mass == "anteil"
                  else "")

        # 1a. Ein Plot pro Aspekt (wöchentlich)
        for col in aspect_cols:
            fig, ax = plt.subplots(figsize = (8, 4.5))
            plot_weekly(ax, col, mass, show_legend = True)
            ax.set_title(f"Kriegsaspekt: {aspect_label(col)}", loc = "left", fontsize = 12)
            ax.set_ylabel(ylabel)
            ax.text(0, -0.15, f"Wochenwerte; {luecke}Gestrichelt: Kriegsbeginn (24.02.2022).",
                    transform = ax.transAxes, fontsize = 8, color = "#52514e")
            fig.tight_layout()
            fig.savefig(plot_dir / f"{prefix}woche_{col}.png", dpi = 150)
            plt.close(fig)

        # 1b. Übersicht: alle Aspekte als Small Multiples (eigene y-Achse je Aspekt, Niveaus unterscheiden sich stark)
        n_cols = 4
        n_rows = int(np.ceil(len(aspect_cols) / n_cols))
        fig, axes = plt.subplots(n_rows, n_cols, figsize = (16, 3.2 * n_rows), sharex = True)
        for i, (ax, col) in enumerate(zip(axes.flat, aspect_cols)):
            plot_weekly(ax, col, mass, show_legend = (i == 0))
            ax.set_title(aspect_label(col), loc = "left", fontsize = 10)
        for ax in axes.flat[len(aspect_cols):]:
            ax.set_visible(False)
        fig.suptitle(f"{title}, nach Medientyp (wöchentlich)", x = 0.01, ha = "left", fontsize = 13)
        fig.tight_layout()
        fig.savefig(plot_dir / f"{prefix}uebersicht_woche_alle_aspekte.png", dpi = 150)
        plt.close(fig)

        # 1c. Übersicht: Anteil bzw. Anzahl ab Kriegsbeginn je Aspekt und Medientyp (gruppierte Balken)
        grouped = after.groupby("medientyp")[aspect_cols]
        after_values = (grouped.mean() if mass == "anteil" else grouped.sum()).T
        after_values = after_values.loc[after_values.mean(axis = 1).sort_values().index]

        fig, ax = plt.subplots(figsize = (9, 9))
        bar_height = 0.8 / len(types)
        y = np.arange(len(after_values))
        for j, typ in enumerate(types):
            offset = ((len(types) - 1) / 2 - j) * bar_height
            ax.barh(y + offset, after_values[typ], height = bar_height - 0.03, color = MEDIENTYP_COLORS[typ],
                    label = f"{MEDIENTYP_LABELS[typ]} (n Kriegsvideos = {after_n.get(typ, 0)})")
        ax.set_yticks(y, [aspect_label(c) for c in after_values.index])
        if mass == "anteil":
            ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals = 0))
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis = "x", color = "#e5e5e3", linewidth = 0.8)
        ax.set_axisbelow(True)
        ax.set_xlabel(f"{ylabel} (ab 24.02.2022)")
        ax.set_title("Kriegsaspekte nach Medientyp seit Kriegsbeginn", loc = "left", fontsize = 12)
        ax.legend(frameon = False, loc = "lower right")
        fig.tight_layout()
        fig.savefig(plot_dir / f"{prefix}uebersicht_ab_kriegsbeginn.png", dpi = 150)
        plt.close(fig)

        print(f"\n{mass.capitalize()} ab Kriegsbeginn:\n{after_values.round(3)}")

    print(f"\nAnzahl Ukraine-Kriegsvideos pro Woche und Medientyp:\n{week_n}")
    print(f"Kriegsaspekt-Plots gespeichert in {plot_dir.resolve()}")


# ===================== 2. ESTABLISHMENT-KRITIK NACH THEMA =====================

# Kennzahl -> (Panel-Titel, Spalte mit der zugehörigen Fallzahl, Prozentachse?)
ESTAB_PANELS = {
    "anteil_bewertend": ("Status: bewertend", "n_videos", True),
    "anteil_deskriptiv": ("Status: deskriptiv", "n_videos", True),
    "score_mittel": ("Ø estab_score (nur bewertende Videos)", "n_score", False),
    **{f"anteil_{s}": (f"Intensität: {s}", "n_videos" if ESTAB_INTENS_BASIS == "alle" else "n_intens", True)
       for s in INTENS_STUFEN},
}


def estab_kennzahlen(videos):
    """Kennzahlen je Periode und Medientyp für eine Menge von Videos (ein Thema)."""
    v = videos.assign(
        bewertend = (videos["estab_status"] == "bewertend").astype(float),
        deskriptiv = (videos["estab_status"] == "deskriptiv").astype(float),
        **{f"ist_{s}": (videos["estab_intensitaet"] == s).astype(float) for s in INTENS_STUFEN},
    )
    g = v.groupby(["periode", "medientyp"], observed = True)
    out = pd.DataFrame({
        "n_videos": g.size(),
        "anteil_bewertend": g["bewertend"].mean(),
        "anteil_deskriptiv": g["deskriptiv"].mean(),
        "n_score": g["estab_score"].count(),
        "score_mittel": g["estab_score"].mean(),
        "n_intens": g["estab_intensitaet"].count(),
    })
    for s in INTENS_STUFEN:
        count = g[f"ist_{s}"].sum()
        basis = out["n_videos"] if ESTAB_INTENS_BASIS == "alle" else out["n_intens"]
        out[f"anteil_{s}"] = count / basis.where(basis > 0)
    return out


def draw_panel(ax, table, metric, n_col, percent, types, periods):
    """Ein Panel: Linien (Monat/Woche) bzw. gruppierte Balken (Phase) je Medientyp."""
    for j, typ in enumerate(types):
        if typ in table.index.get_level_values("medientyp"):
            sub = table.xs(typ, level = "medientyp").reindex(periods)
        else:
            sub = pd.DataFrame(index = periods, columns = table.columns, dtype = float)
        values = sub[metric].where(sub[n_col] >= ESTAB_MIN_N)
        if ESTAB_ZEITEINHEIT == "phase":
            width = 0.8 / len(types)
            x = np.arange(len(periods)) + (j - (len(types) - 1) / 2) * width
            ax.bar(x, values.values, width = width - 0.02, color = MEDIENTYP_COLORS[typ],
                   label = MEDIENTYP_LABELS[typ])
        else:
            ax.plot(periods, values.values, color = MEDIENTYP_COLORS[typ], linewidth = 2,
                    marker = "o", markersize = 4, label = MEDIENTYP_LABELS[typ])

    if ESTAB_ZEITEINHEIT == "phase":
        ax.set_xticks(np.arange(len(periods)), periods)
    else:
        ax.axvline(KRIEGSBEGINN, color = "#8a8985", linestyle = "--", linewidth = 1)
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    if percent:
        ax.set_ylim(0, 1)
    else:
        ax.set_ylim(-2, 2)
        ax.axhline(0, color = "#8a8985", linewidth = 0.8)
    style_axis(ax, percent = percent)


def plot_establishment(df_video):
    df_video = add_periode(df_video, ESTAB_ZEITEINHEIT)
    types = active_types(df_video)
    if ESTAB_ZEITEINHEIT == "phase":
        periods = PHASEN
    else:
        periods = sorted(df_video["periode"].unique())

    all_topics = sorted(c.removeprefix("thema_") for c in df_video.columns if c.startswith("thema_"))
    topics = all_topics if ESTAB_THEMEN is None else ESTAB_THEMEN

    plot_dir = ESTAB_PLOT_DIR / gruppierung_dir() / ESTAB_ZEITEINHEIT
    plot_dir.mkdir(parents = True, exist_ok = True)

    intens_note = ("Intensität: Anteil an allen Videos des Themas." if ESTAB_INTENS_BASIS == "alle"
                   else "Intensität: Anteil an Videos mit negativer Bewertung (Intensität kodiert).")
    note = (f"Video zählt zum Thema, wenn das Thema in ≥ 1 Segment vorkommt. Establishment-Werte beziehen sich "
            f"auf das ganze Video (Status/Intensität: stärkste Ausprägung; Score: wortgewichteter Mittelwert, "
            f"−2 = scharfe Kritik, +2 = Zustimmung).\n{intens_note} Kein Wert bei < {ESTAB_MIN_N} Videos pro Zelle.")

    alle_kennzahlen = []
    for topic in topics:
        videos = df_video[df_video[f"thema_{topic}"] > 0]
        table = estab_kennzahlen(videos)
        alle_kennzahlen.append(table.reset_index().assign(thema = topic))

        n_by_type = videos["medientyp"].value_counts()
        fig, axes = plt.subplots(2, 3, figsize = (15, 8), sharex = True)
        for ax, (metric, (title, n_col, percent)) in zip(axes.flat, ESTAB_PANELS.items()):
            draw_panel(ax, table, metric, n_col, percent, types, periods)
            ax.set_title(title, loc = "left", fontsize = 10)
        handles, labels = axes.flat[0].get_legend_handles_labels()
        labels = [f"{l} (n = {n_by_type.get(t, 0)})" for l, t in zip(labels, types)]
        fig.legend(handles, labels, frameon = False, loc = "upper right", ncol = len(types), fontsize = 9)
        fig.suptitle(f"Establishment-Bewertung in Videos zum Thema „{label_from_col(topic, '')}“",
                     x = 0.01, ha = "left", fontsize = 13)
        fig.text(0.01, 0.01, note, fontsize = 8, color = "#52514e", va = "bottom")
        fig.tight_layout(rect = (0, 0.06, 1, 0.95))
        fig.savefig(plot_dir / f"estab_{topic}.png", dpi = 150)
        plt.close(fig)

    kennzahlen = pd.concat(alle_kennzahlen, ignore_index = True)
    kennzahlen = kennzahlen[["thema", "periode", "medientyp"] + [c for c in kennzahlen.columns
                                                                 if c not in ("thema", "periode", "medientyp")]]
    kennzahlen.to_csv(plot_dir / "kennzahlen.csv", index = False)
    print(f"\nVideos je Thema und Medientyp:\n"
          f"{kennzahlen.groupby(['thema', 'medientyp'])['n_videos'].sum().unstack()}")
    print(f"Establishment-Plots gespeichert in {plot_dir.resolve()}")


# ===================== 3. ESTABLISHMENT: UKRAINE-KRIEG VS. ANDERE VIDEOS =====================

def plot_estab_krieg_vs_andere(df_video):
    """Zeitverlauf der Establishment-Kennzahlen: Videos mit Ukraine-Krieg-Thema (durchgezogen) vs. alle
    anderen Videos (gestrichelt), Farbe = Medientyp."""
    df_video = add_periode(df_video, VERGLEICH_ZEITEINHEIT)
    types = active_types(df_video)
    periods = sorted(df_video["periode"].unique())
    ist_krieg = df_video["thema_krieg_ukraine"] > 0
    gruppen = {"Ukraine-Krieg": (df_video[ist_krieg], "-"), "Andere Videos": (df_video[~ist_krieg], "--")}
    tables = {name: estab_kennzahlen(videos) for name, (videos, _) in gruppen.items()}

    plot_dir = ESTAB_PLOT_DIR / gruppierung_dir() / f"krieg_vs_andere_{VERGLEICH_ZEITEINHEIT}"
    plot_dir.mkdir(parents = True, exist_ok = True)

    fig, axes = plt.subplots(2, 3, figsize = (15, 8), sharex = True)
    for ax, (metric, (title, n_col, percent)) in zip(axes.flat, ESTAB_PANELS.items()):
        for name, (videos, linestyle) in gruppen.items():
            table = tables[name]
            n_by_type = videos["medientyp"].value_counts()
            for typ in types:
                if typ not in table.index.get_level_values("medientyp"):
                    continue
                sub = table.xs(typ, level = "medientyp").reindex(periods)
                values = sub[metric].where(sub[n_col] >= ESTAB_MIN_N)
                ax.plot(periods, values.values, color = MEDIENTYP_COLORS[typ], linestyle = linestyle,
                        linewidth = 2, marker = "o", markersize = 3,
                        label = f"{MEDIENTYP_LABELS[typ]} – {name} (n = {n_by_type.get(typ, 0)})")
        ax.axvline(KRIEGSBEGINN, color = "#8a8985", linestyle = ":", linewidth = 1)
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        if percent:
            ax.set_ylim(0, 1)
        else:
            ax.set_ylim(-2, 2)
            ax.axhline(0, color = "#8a8985", linewidth = 0.8)
        style_axis(ax, percent = percent)
        ax.set_title(title, loc = "left", fontsize = 10)

    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon = False, loc = "upper right", ncol = 2, fontsize = 8)
    zeit = "Wochenwerte" if VERGLEICH_ZEITEINHEIT == "woche" else "Monatswerte"
    intens_note = ("Intensität: Anteil an allen Videos der Gruppe." if ESTAB_INTENS_BASIS == "alle"
                   else "Intensität: Anteil an Videos mit negativer Bewertung (Intensität kodiert).")
    note = (f"{zeit}. Ukraine-Krieg = Thema in ≥ 1 Segment, Andere = alle übrigen Videos. Establishment-Werte "
            f"beziehen sich auf das ganze Video (Score: −2 = scharfe Kritik, +2 = Zustimmung).\n{intens_note} "
            f"Lücke bei < {ESTAB_MIN_N} Videos pro Zelle. Gepunktet: Kriegsbeginn (24.02.2022).")
    fig.suptitle("Establishment-Bewertung: Ukraine-Krieg-Videos vs. andere Videos", x = 0.01, ha = "left",
                 fontsize = 13)
    fig.text(0.01, 0.01, note, fontsize = 8, color = "#52514e", va = "bottom")
    fig.tight_layout(rect = (0, 0.06, 1, 0.9))
    fig.savefig(plot_dir / "estab_krieg_vs_andere.png", dpi = 150)
    plt.close(fig)

    kennzahlen = pd.concat([t.reset_index().assign(gruppe = name) for name, t in tables.items()],
                           ignore_index = True)
    kennzahlen = kennzahlen[["gruppe", "periode", "medientyp"] + [c for c in kennzahlen.columns
                                                                  if c not in ("gruppe", "periode", "medientyp")]]
    kennzahlen.to_csv(plot_dir / "kennzahlen.csv", index = False)
    print(f"\nVideos je Gruppe, {zeit} und Medientyp:\n"
          f"{kennzahlen.pivot_table(index = 'periode', columns = ['gruppe', 'medientyp'], values = 'n_videos')}")
    print(f"Krieg-vs.-andere-Plot gespeichert in {plot_dir.resolve()}")


# ===================== MAIN =====================

def main():
    if MEDIENTYP_GRUPPIERUNG not in ("mainstream", "drei"):
        raise ValueError(f"MEDIENTYP_GRUPPIERUNG muss 'mainstream' oder 'drei' sein, nicht {MEDIENTYP_GRUPPIERUNG!r}.")
    if ESTAB_ZEITEINHEIT not in ("phase", "monat", "woche"):
        raise ValueError(f"ESTAB_ZEITEINHEIT muss 'phase', 'monat' oder 'woche' sein, nicht {ESTAB_ZEITEINHEIT!r}.")
    if VERGLEICH_ZEITEINHEIT not in ("woche", "monat"):
        raise ValueError(f"VERGLEICH_ZEITEINHEIT muss 'woche' oder 'monat' sein, nicht {VERGLEICH_ZEITEINHEIT!r}.")
    if not KRIEG_MASSE or not set(KRIEG_MASSE) <= {"anteil", "anzahl"}:
        raise ValueError(f"KRIEG_MASSE muss eine nicht-leere Teilmenge von ['anteil', 'anzahl'] sein, nicht {KRIEG_MASSE!r}.")
    if ESTAB_INTENS_BASIS not in ("alle", "negativ"):
        raise ValueError(f"ESTAB_INTENS_BASIS muss 'alle' oder 'negativ' sein, nicht {ESTAB_INTENS_BASIS!r}.")
    for name, value in [("KRIEG_MIN_N_WEEK", KRIEG_MIN_N_WEEK), ("ESTAB_MIN_N", ESTAB_MIN_N)]:
        if not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} muss eine ganze Zahl >= 1 sein, nicht {value!r}.")
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"{INPUT_FILE} nicht gefunden – zuerst process_results.py ausführen.")

    df_video = load_videos()
    if ESTAB_THEMEN is not None:
        unknown = [t for t in ESTAB_THEMEN if f"thema_{t}" not in df_video.columns]
        if unknown:
            raise ValueError(f"Unbekannte Themen in ESTAB_THEMEN: {unknown}")

    if PLOT_KRIEGSASPEKTE:
        plot_kriegsaspekte(df_video)
    if PLOT_ESTABLISHMENT:
        plot_establishment(df_video)
    if PLOT_ESTAB_KRIEG_VS_ANDERE:
        plot_estab_krieg_vs_andere(df_video)


if __name__ == "__main__":
    main()

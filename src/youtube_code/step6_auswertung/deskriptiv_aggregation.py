# -*- coding: utf-8 -*-
"""
deskriptiv_aggregation.py

Liest die bereits aggregierten Kanal x Periode Zeitreihen ein (Populismus/
Position-Stance aus prepare_channel_scores.py, Erfolg/Views-Engagement aus
prepare_success_metrics.py), ergaenzt Kanalmetadaten (Medientyp, Ideologie),
filtert Kanaele und berechnet fuer Populismus zusaetzlich zum Rohwert einen
Baseline-Index (letzte Vorkriegsperioden = 100). Der Rohwert (wert_roh)
bleibt dabei fuer ALLE Kanal-Perioden-Zellen erhalten, auch fuer Kanaele
ohne besetztes Vorkriegsfenster (deren index_100 = NaN bleibt) -
deskriptiv_plots.py plottet standardmaessig den Rohwert, nicht den Index
(siehe dortiger Docstring und frage1_methodik_und_stichprobe.md
Abschnitt 3c). MODUS = "erfolg" (Forschungsfrage 2, siehe
frage2_4_methodik_und_stichprobe.md) bekommt wie "stance" KEINEN
Baseline-Index - rohe Views/Engagement werden bewusst NICHT auf eine
Vorkriegsperiode normiert, siehe Docstring von prepare_success_metrics.py.
MODUS = "erfolg_kriegsvideos" (Forschungsfrage 4, siehe deskriptiv_plots.py::
NUR_TOPICVIDEOS) ist dieselbe Aufbereitung wie "erfolg", nur mit der auf
Kriegsvideos gefilterten Zeitreihe (channel_{gran}_erfolg_kriegsvideos_
timeseries.csv) als Eingabe - ebenfalls kein Baseline-Index.

Granularitaet (Quartal/Monat) ueber GRANULARITAET_LISTE waehlbar - die jeweilige
Quellzeitreihe schreibt fuer beide Granularitaeten je eine eigene Datei, dieses
Skript liest je Kombination aus MODUS_LISTE x GRANULARITAET_LISTE eine ein und
produziert dazu eine passende deskriptiv_{modus}_{granularitaet}.csv.

Segment -> Video -> Kanal x Periode passiert NICHT mehr hier, sondern in
prepare_channel_scores.py. Dieses Skript setzt bei der bereits aggregierten
Tabelle an.

MODUS_LISTE und GRANULARITAET_LISTE nehmen jeweils eine Liste von Werten -
main() iteriert automatisch ueber alle Kombinationen (kartesisches Produkt)
und schreibt fuer jede eine eigene deskriptiv_{modus}_{granularitaet}.csv.
"""

import os
from itertools import product
from types import SimpleNamespace

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from youtube_code.config import OUTPUTS, EXTERNAL

# =========================================================
# CONFIG
# =========================================================

MODUS_LISTE = ["populismus", "stance", "erfolg", "erfolg_kriegsvideos"]  # Teilmenge von {"populismus", "stance", "erfolg", "erfolg_kriegsvideos"}
# "erfolg_kriegsvideos": wie "erfolg", aber nur ueber Kriegsvideos aggregiert (channel_{gran}_
# erfolg_kriegsvideos_timeseries.csv aus prepare_success_metrics.py) - Grundlage fuer
# deskriptiv_plots.py::NUR_TOPICVIDEOS (Forschungsfrage 4). Standardmaessig NICHT in MODUS_LISTE,
# weil nur fuer diesen einen Anwendungsfall gebraucht - bei Bedarf hier ergaenzen, bevor
# deskriptiv_plots.py mit NUR_TOPICVIDEOS = True laeuft (sonst fehlt deskriptiv_erfolg_
# kriegsvideos_{granularitaet}.csv).
GRANULARITAET_LISTE = ["quartal", "monat"]     # Teilmenge von {"quartal", "monat"}

# --- Granularitaets-Definitionen -------------------------------------------
# Jede Granularitaet bringt ihre eigene Periodenspalte, Dateibenennung und
# sinnvolle Standardfenster mit (ein Vorkriegs-"Baseline"-Fenster von 6 Monaten
# entspricht z.B. BASELINE_PERIODEN=[-2,-1] bei Quartalen, aber [-6..-1] bei Monaten).
GRANULARITAETEN = {
    "quartal": {
        "spalte": "rel_quartal",
        "datei_suffix": "quartal",
        "periode_min": -4,
        "periode_max": 18,
        "baseline_perioden": [-2, -1],
        "min_videos_pro_periode": 3,
    },
    "monat": {
        "spalte": "rel_monat",
        "datei_suffix": "monat",
        "periode_min": -12,
        "periode_max": 52,
        "baseline_perioden": [-6, -5, -4, -3, -2, -1],
        "min_videos_pro_periode": 1,
    },
}

# --- Eingabedateien (Output von prepare_channel_scores.py bzw. -----------
# --- prepare_success_metrics.py fuer "erfolg"/"erfolg_kriegsvideos") ------
DATEISTAMM_MODUS = {
    "populismus": "populism",
    "stance": "position",
    "erfolg": "erfolg",
    "erfolg_kriegsvideos": "erfolg_kriegsvideos",
}


def baue_konfiguration(modus, granularitaet):
    """Buendelt alle von (modus, granularitaet) abhaengigen Ableitungen (Periodenspalte,
    Fenster, Eingabedatei) in einem Objekt, das durch einen main()-Durchlauf gereicht wird."""
    gran_cfg = GRANULARITAETEN[granularitaet]
    pfad_zeitreihe = (
        OUTPUTS / "segment_analysis" /
        f"channel_{gran_cfg['datei_suffix']}_{DATEISTAMM_MODUS[modus]}_timeseries.csv"
    )
    return SimpleNamespace(
        modus=modus,
        granularitaet=granularitaet,
        spalte_periode=gran_cfg["spalte"],
        periode_min=gran_cfg["periode_min"],
        periode_max=gran_cfg["periode_max"],
        baseline_perioden=gran_cfg["baseline_perioden"],
        min_videos_pro_periode=gran_cfg["min_videos_pro_periode"],
        pfad_zeitreihe=pfad_zeitreihe,
    )


# --- Kanal-Metadaten -------------------------------------------------------
PFAD_MEDIENTYP = EXTERNAL / "media_type_russia_merged.xlsx"
SPALTE_KANAL_ID_MEDIENTYP = "channel_id"
SPALTE_MEDIENTYP = "type"

# Typ 1-4 = eindeutig, Typ 5 = Sonderfaelle (aktuell 2 Kanaele).
# TYP5_ZU_1 = True  -> Typ 5 wird zu Typ 1 (OeRR) gezaehlt (vermerkt in der Konsole)
# TYP5_ZU_1 = False -> Typ 5 wird komplett aus der Analyse gedroppt
TYP5_ZU_1 = True

MEDIENTYP_LABELS = {
    1: "ÖRR",
    2: "Traditionelles Medium",
    3: "Alternatives Medium",
    4: "Politiker/Partei",
}

# Ideologie: aus channel_classification_ideology.csv (prepare_ideology_results)
PFAD_IDEOLOGIE = OUTPUTS / "segment_analysis" / "channel_classification_ideology.csv"
IDEOLOGIE_DIMENSION = "gesellschaft_mean"     # aktuell bewusst nur die gesellschaftliche Achse
IDEOLOGIE_SCHNITTE = [-0.5, 0.5]              # Grenzen zwischen den Gruppen
IDEOLOGIE_LABELS = ["links", "mitte", "rechts"]

PFAD_AUSGABE = OUTPUTS / "segment_analysis" / "deskriptiv_{modus}_{granularitaet}.csv"

# --- Baseline (nur MODUS = "populismus") ----------------------------------
BASELINE_GEWICHTUNG = "periode"   # "periode" = jede Periode gleich, "video" = jedes Video gleich

MIN_BASELINE_PERIODEN_BESETZT = 1     # wie viele der BASELINE_PERIODEN besetzt sein muessen
MIN_VIDEOS_BASELINE_GESAMT = 5        # Mindestzahl Videos im Baselinefenster (absolut, granularitaetsunabhaengig)
MIN_BASELINE_WERT = 0.15              # Index nur bilden, wenn Baseline >= diesem Wert

# --- Kanalauswahl -----------------------------------------------------------
MEDIENTYPEN = None                    # z.B. ["ÖRR", "Traditionelles Medium"]; None = alle
# Fuer Frage 1 (Populismus) auf die Whitelist aus frage1_stichprobe.py beschraenkt
# (>= 5 Kriegsvideos im gesamten Upload-Verlauf UND mind. 1 klassifiziertes Video -
# siehe dort und outputs/segment_analysis/frage1_methodik_und_stichprobe.md).
# MODUS = "erfolg"/"erfolg_kriegsvideos" (Frage 2/4) nutzen dieselbe Whitelist
# (bereits in prepare_success_metrics.py angewendet, hier also ein No-Op-Filter
# zur Konsistenz). Fuer andere Auswertungen (z.B. MODUS="stance") ggf. auf None
# zuruecksetzen.
KANAL_WHITELIST = OUTPUTS / "segment_analysis" / "frage1_kanal_whitelist.csv"
KANAL_BLACKLIST = None

# --- Uebersicht Ideologie x Medientyp (separate Hilfsfunktion, nicht Teil von main()) ---
# Granularitaetsunabhaengig: channel_classification_populism.csv ist ein einmaliger Kanalwert,
# keine Zeitreihe, daher hier keine GRANULARITAET-Abhaengigkeit.
PFAD_POPULISMUS_KLASSIFIKATION = OUTPUTS / "segment_analysis" / "channel_classification_populism.csv"
PFAD_UEBERSICHT_TABELLE = OUTPUTS / "segment_analysis" / "uebersicht_ideologie_medientyp.csv"
PFAD_UEBERSICHT_PLOT = OUTPUTS / "segment_analysis" / "plots" / "boxplot_gesellschaft_je_medientyp.png"

MIN_VIDEOS_KLASSIFIKATION = 3

IDEOLOGIE_RUNDUNG = 0.25          # Rundungsschritt fuer die Gruppierung ueberlappender Punkte
PUNKTGROESSE_PRO_KANAL = 25       # Flaeche (matplotlib "s") je zusammengefasstem Kanal


# =========================================================
# HILFSFUNKTIONEN
# =========================================================

def lade_kanalliste(quelle):
    if quelle is None:
        return None
    if isinstance(quelle, (list, tuple, set)):
        return set(quelle)
    if str(quelle).lower().endswith((".csv", ".parquet")):
        df = pd.read_csv(quelle) if str(quelle).endswith(".csv") else pd.read_parquet(quelle)
        return set(df.iloc[:, 0].astype(str))
    with open(quelle, encoding="utf-8") as f:
        return {z.strip() for z in f if z.strip()}


# =========================================================
# SCHRITT 1: Zeitreihe einlesen
# =========================================================

def lade_zeitreihe(cfg):
    pfad = cfg.pfad_zeitreihe
    if not os.path.exists(pfad):
        raise FileNotFoundError(f"Datei nicht gefunden: {pfad}")

    df = pd.read_csv(pfad)

    # Populismus-Output nennt die Wertspalte "wert", Position-Output "wert_roh" -> vereinheitlichen
    if "wert" in df.columns and "wert_roh" not in df.columns:
        df = df.rename(columns={"wert": "wert_roh"})

    pruefe = ["channel_id", cfg.spalte_periode, "dimension", "wert_roh", "n_videos"]
    fehlend = [s for s in pruefe if s not in df.columns]
    if fehlend:
        raise KeyError(f"In '{pfad}' fehlen Spalten {fehlend}. Vorhanden: {list(df.columns)}")

    print(f"[Eingabe][{cfg.granularitaet}] {len(df)} Zeilen, {df['channel_id'].nunique()} Kanaele aus {pfad}")
    return df


# =========================================================
# SCHRITT 2: Kanal-Perioden-Zellen mit zu wenig Videos verwerfen
# =========================================================

def filtere_duenne_zellen(df, cfg):
    zu_duenn = df["n_videos"] < cfg.min_videos_pro_periode
    print(f"[Periode] {int(zu_duenn.sum())} Kanal-Perioden-Zellen unter "
          f"MIN_VIDEOS_PRO_PERIODE={cfg.min_videos_pro_periode} -> verworfen.")
    return df[~zu_duenn]


# =========================================================
# SCHRITT 3: Kanalmerkmale ergaenzen (Medientyp, Ideologie)
# =========================================================

def lade_medientyp():
    med = pd.read_excel(PFAD_MEDIENTYP)
    fehlend = [s for s in [SPALTE_KANAL_ID_MEDIENTYP, SPALTE_MEDIENTYP] if s not in med.columns]
    if fehlend:
        raise KeyError(f"In '{PFAD_MEDIENTYP}' fehlen Spalten {fehlend}. Vorhanden: {list(med.columns)}")

    med = med[[SPALTE_KANAL_ID_MEDIENTYP, SPALTE_MEDIENTYP]].rename(
        columns={SPALTE_KANAL_ID_MEDIENTYP: "channel_id", SPALTE_MEDIENTYP: "typ_code"}
    )
    med["typ_code"] = pd.to_numeric(med["typ_code"], errors="coerce")

    n_typ5 = (med["typ_code"] == 5).sum()
    if n_typ5:
        if TYP5_ZU_1:
            print(f"[Medientyp] {n_typ5} Kanaele mit Typ 5 -> zu Typ 1 (ÖRR) gezaehlt.")
            med.loc[med["typ_code"] == 5, "typ_code"] = 1
        else:
            print(f"[Medientyp] {n_typ5} Kanaele mit Typ 5 -> aus der Analyse gedroppt.")
            med = med[med["typ_code"] != 5]

    med["medientyp"] = med["typ_code"].map(MEDIENTYP_LABELS)
    unbekannt = med["medientyp"].isna() & med["typ_code"].notna()
    if unbekannt.any():
        print(f"[Warnung] {int(unbekannt.sum())} Kanaele mit unbekanntem typ_code "
              f"(nicht in {list(MEDIENTYP_LABELS)}) -> medientyp bleibt NaN.")

    return med[["channel_id", "medientyp"]]


def lade_ideologie():
    ideo = pd.read_csv(PFAD_IDEOLOGIE)
    if "channel_id" not in ideo.columns or IDEOLOGIE_DIMENSION not in ideo.columns:
        raise KeyError(f"In '{PFAD_IDEOLOGIE}' fehlt 'channel_id' oder '{IDEOLOGIE_DIMENSION}'. "
                        f"Vorhanden: {list(ideo.columns)}")

    ideo = ideo[["channel_id", IDEOLOGIE_DIMENSION]].rename(
        columns={IDEOLOGIE_DIMENSION: "ideologie_wert"}
    )
    ideo["ideologie_gruppe"] = pd.cut(
        ideo["ideologie_wert"],
        bins=[-np.inf] + list(IDEOLOGIE_SCHNITTE) + [np.inf],
        labels=IDEOLOGIE_LABELS,
    ).astype(str)
    return ideo


def ergaenze_kanalmerkmale(df):
    med = lade_medientyp()
    df = df.merge(med, on="channel_id", how="left")

    fehlende_ids = df.loc[df["medientyp"].isna(), "channel_id"].unique()
    if len(fehlende_ids):
        print(f"[Medientyp] {len(fehlende_ids)} Kanaele ohne Eintrag in '{PFAD_MEDIENTYP}' "
              f"-> medientyp = NaN: {list(fehlende_ids)}")

    ideo = lade_ideologie()
    df = df.merge(ideo, on="channel_id", how="left")

    fehlende_ideo_ids = df.loc[df["ideologie_gruppe"].isna(), "channel_id"].unique()
    if len(fehlende_ideo_ids):
        print(f"[Ideologie] {len(fehlende_ideo_ids)} Kanaele ohne Eintrag in '{PFAD_IDEOLOGIE}' "
              f"-> ideologie_gruppe = NaN: {list(fehlende_ideo_ids)}")

    return df


# =========================================================
# SCHRITT 4: Kanalauswahl
# =========================================================

def filtere_kanaele(df, cfg):
    if MEDIENTYPEN:
        vorher = df["channel_id"].nunique()
        df = df[df["medientyp"].isin(MEDIENTYPEN)]
        print(f"[Auswahl] Medientyp-Filter: {vorher} -> {df['channel_id'].nunique()} Kanaele.")

    white = lade_kanalliste(KANAL_WHITELIST)
    if white is not None:
        df = df[df["channel_id"].astype(str).isin(white)]
        print(f"[Auswahl] Whitelist: {df['channel_id'].nunique()} Kanaele.")

    black = lade_kanalliste(KANAL_BLACKLIST)
    if black is not None:
        df = df[~df["channel_id"].astype(str).isin(black)]

    df = df[(df[cfg.spalte_periode] >= cfg.periode_min) & (df[cfg.spalte_periode] <= cfg.periode_max)]
    return df


# =========================================================
# SCHRITT 5: Baseline und Index (nur Populismus)
# =========================================================

def berechne_index(df, cfg):
    basis = df[df[cfg.spalte_periode].isin(cfg.baseline_perioden)]

    if BASELINE_GEWICHTUNG == "periode":
        ref = basis.groupby(["channel_id", "dimension"], as_index=False).agg(
            baseline=("wert_roh", "mean"),
            n_baseline_perioden=("wert_roh", "size"),
            n_baseline_videos=("n_videos", "sum"),
        )
    else:
        basis = basis.copy()
        basis["gewichtet"] = basis["wert_roh"] * basis["n_videos"]
        ref = basis.groupby(["channel_id", "dimension"], as_index=False).agg(
            summe=("gewichtet", "sum"),
            n_baseline_videos=("n_videos", "sum"),
            n_baseline_perioden=("wert_roh", "size"),
        )
        ref["baseline"] = ref["summe"] / ref["n_baseline_videos"]
        ref = ref.drop(columns=["summe"])

    n_vor = ref["channel_id"].nunique()
    ref = ref[ref["n_baseline_perioden"] >= MIN_BASELINE_PERIODEN_BESETZT]
    ref = ref[ref["n_baseline_videos"] >= MIN_VIDEOS_BASELINE_GESAMT]
    print(f"[Baseline] {n_vor} -> {ref['channel_id'].nunique()} Kanaele mit gueltiger Baseline.")

    # LEFT-Join (nicht INNER): Kanal-Dimension-Zeilen ohne gueltige Vorkriegs-Baseline
    # bleiben mit ihrem Rohwert (wert_roh) erhalten, bekommen nur index_100 = NaN. Vor
    # dieser Umstellung wurden sie hier komplett verworfen - das war fuer den (nicht mehr
    # standardmaessig geplotteten) Index noetig, hat aber auch die absoluten Rohwerte
    # dieser Kanaele aus den Plots entfernt (u.a. neu seit Kriegsbeginn dazugekommene
    # Kanaele ohne Vorkriegsfenster). Siehe frage1_methodik_und_stichprobe.md Abschnitt 3c.
    df = df.merge(ref, on=["channel_id", "dimension"], how="left")

    ohne_baseline = df["baseline"].isna()
    if ohne_baseline.any():
        n_ohne = df.loc[ohne_baseline, "channel_id"].nunique()
        print(f"[Baseline] {n_ohne} Kanaele ohne gueltige Vorkriegs-Baseline -> index_100 = NaN, "
              f"wert_roh bleibt erhalten.")

    zu_klein = df["baseline"] < MIN_BASELINE_WERT
    if zu_klein.any():
        betroffen = df.loc[zu_klein, ["channel_id", "dimension"]].drop_duplicates()
        print(f"[Baseline] {len(betroffen)} Kanal-Dimension-Paare mit Baseline < "
              f"{MIN_BASELINE_WERT} -> Index auf NaN gesetzt.")

    df["index_100"] = np.where(zu_klein, np.nan, df["wert_roh"] / df["baseline"] * 100)
    return df


# =========================================================
# ZUSATZ: Uebersicht Ideologie x Medientyp (granularitaetsunabhaengig)
# =========================================================

def erstelle_uebersicht_ideologie_medientyp():
    """Tabelle + Scatterplot: gesellschaft_mean (Ideologie) und populismus_gesamt je Kanal,
    gruppiert nach Medientyp. Nutzt dieselben Ladefunktionen wie die Hauptpipeline."""

    pop = pd.read_csv(PFAD_POPULISMUS_KLASSIFIKATION)
    fehlend = [s for s in ["channel_id", "populismus_gesamt", "n_videos_total"] if s not in pop.columns]
    if fehlend:
        raise KeyError(f"In '{PFAD_POPULISMUS_KLASSIFIKATION}' fehlen Spalten {fehlend}. "
                        f"Vorhanden: {list(pop.columns)}")

    n_vor = len(pop)
    pop = pop[pop["n_videos_total"] >= MIN_VIDEOS_KLASSIFIKATION]
    print(f"[Uebersicht] {n_vor} -> {len(pop)} Kanaele mit >= {MIN_VIDEOS_KLASSIFIKATION} "
          f"Baseline-Videos (n_videos_total).")

    pop = pop[["channel_id", "channel_title", "populismus_gesamt"]]

    ideo = lade_ideologie()
    med = lade_medientyp()

    tab = pop.merge(ideo, on="channel_id", how="left").merge(med, on="channel_id", how="left")
    tab = tab[["channel_id", "channel_title", "ideologie_wert", "populismus_gesamt", "medientyp"]]

    os.makedirs(os.path.dirname(PFAD_UEBERSICHT_TABELLE), exist_ok=True)
    tab.to_csv(PFAD_UEBERSICHT_TABELLE, index=False, encoding="utf-8")
    print(f"[Uebersicht] {len(tab)} Kanaele -> {PFAD_UEBERSICHT_TABELLE}")

    fehlend = tab["medientyp"].isna().sum()
    if fehlend:
        print(f"[Warnung] {fehlend} Kanaele ohne Medientyp -> im Boxplot ausgeschlossen.")

    plot_df = tab.dropna(subset=["medientyp", "ideologie_wert"]).copy()
    plot_df["ideologie_gerundet"] = (plot_df["ideologie_wert"] / IDEOLOGIE_RUNDUNG).round() * IDEOLOGIE_RUNDUNG

    gruppen = sorted(plot_df["medientyp"].unique())
    x_position = {g: i for i, g in enumerate(gruppen)}

    punkte = plot_df.groupby(["medientyp", "ideologie_gerundet"], as_index=False).agg(
        n_kanaele=("channel_id", "nunique")
    )
    punkte["x"] = punkte["medientyp"].map(x_position)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(
        punkte["x"], punkte["ideologie_gerundet"],
        s=punkte["n_kanaele"] * PUNKTGROESSE_PRO_KANAL,
        alpha=0.6, edgecolor="black", linewidth=0.5,
    )
    ax.axhline(0, color="grey", linewidth=0.8)
    ax.set_xticks(list(x_position.values()))
    ax.set_xticklabels(list(x_position.keys()))
    ax.set_xlim(-0.5, len(gruppen) - 0.5)
    ax.set_ylabel(f"Ideologie (gesellschaft_mean, gerundet auf {IDEOLOGIE_RUNDUNG})")
    ax.set_title("Ideologische Ausrichtung je Medientyp")

    legenden_werte = sorted(set(punkte["n_kanaele"]))
    legenden_werte = [legenden_werte[i] for i in
                       np.linspace(0, len(legenden_werte) - 1, min(4, len(legenden_werte)), dtype=int)]
    for n in legenden_werte:
        ax.scatter([], [], s=n * PUNKTGROESSE_PRO_KANAL, color="grey", alpha=0.6,
                   edgecolor="black", linewidth=0.5, label=f"{n} Kanal/Kanäle")
    ax.legend(title="Punktgröße", fontsize=8, loc="best")

    fig.tight_layout()

    PFAD_UEBERSICHT_PLOT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(PFAD_UEBERSICHT_PLOT, dpi=150)
    plt.close(fig)
    print(f"[Uebersicht] Scatterplot -> {PFAD_UEBERSICHT_PLOT}")

    for g in gruppen:
        n = plot_df.loc[plot_df["medientyp"] == g, "channel_id"].nunique()
        print(f"  {g}: n={n}")

    return tab


# =========================================================
# MAIN
# =========================================================

def verarbeite(cfg):
    """Fuehrt Schritte 1-5 fuer eine einzelne (modus, granularitaet)-Kombination aus
    und schreibt die dazu passende deskriptiv_{modus}_{granularitaet}.csv."""
    print(f"=== MODUS: {cfg.modus} | GRANULARITAET: {cfg.granularitaet} ===")

    df = lade_zeitreihe(cfg)
    df = filtere_duenne_zellen(df, cfg)
    df = ergaenze_kanalmerkmale(df)
    df = filtere_kanaele(df, cfg)

    if cfg.modus == "populismus":
        df = berechne_index(df, cfg)
    else:
        df["baseline"] = np.nan
        df["index_100"] = np.nan
        df["n_baseline_videos"] = np.nan
        df["n_baseline_perioden"] = np.nan

    df["modus"] = cfg.modus
    df["granularitaet"] = cfg.granularitaet
    spalten = ["modus", "granularitaet", "channel_id", "medientyp", "ideologie_wert", "ideologie_gruppe",
               cfg.spalte_periode, "dimension", "wert_roh", "n_videos", "n_deskriptiv",
               "baseline", "n_baseline_videos", "n_baseline_perioden", "index_100"]
    df = df[[s for s in spalten if s in df.columns]].sort_values(
        ["dimension", "channel_id", cfg.spalte_periode])

    pfad = str(PFAD_AUSGABE).format(modus=cfg.modus, granularitaet=cfg.granularitaet)
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    df.to_csv(pfad, index=False, encoding="utf-8")

    print(f"\n[Ausgabe] {len(df)} Zeilen, {df['channel_id'].nunique()} Kanaele -> {pfad}")
    print(f"\nKanaele je {cfg.spalte_periode} (ueber alle Dimensionen):")
    print(df.groupby(cfg.spalte_periode)["channel_id"].nunique().to_string())


def main():
    for modus, granularitaet in product(MODUS_LISTE, GRANULARITAET_LISTE):
        cfg = baue_konfiguration(modus, granularitaet)
        verarbeite(cfg)
        print()


if __name__ == "__main__":
    main()
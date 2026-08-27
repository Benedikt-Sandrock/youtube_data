# -*- coding: utf-8 -*-
"""
deskriptiv_aggregation.py

Liest die bereits von prepare_channel_scores.py aggregierten Kanal x Periode
Zeitreihen ein (Populismus bzw. Position/Stance), ergaenzt Kanalmetadaten
(Medientyp, Ideologie), filtert Kanaele und berechnet fuer Populismus den
Baseline-Index (letzte Vorkriegsperioden = 100).

Granularitaet (Quartal/Monat) ueber GRANULARITAET waehlbar - prepare_channel_scores.py
schreibt fuer beide Granularitaeten je eine eigene Zeitreihen-Datei, dieses Skript liest
davon eine ein und produziert eine dazu passende deskriptiv_{modus}_{granularitaet}.csv.

Segment -> Video -> Kanal x Periode passiert NICHT mehr hier, sondern in
prepare_channel_scores.py. Dieses Skript setzt bei der bereits aggregierten
Tabelle an.
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from youtube_code.config import OUTPUTS, EXTERNAL

# =========================================================
# CONFIG
# =========================================================

MODUS = "populismus"          # "populismus" | "stance"
GRANULARITAET = "monat"     # "quartal" | "monat"

# --- Granularitaets-Definitionen -------------------------------------------
# Jede Granularitaet bringt ihre eigene Periodenspalte, Dateibenennung und
# sinnvolle Standardfenster mit (ein Vorkriegs-"Baseline"-Fenster von 6 Monaten
# entspricht z.B. BASELINE_PERIODEN=[-2,-1] bei Quartalen, aber [-6..-1] bei Monaten).
GRANULARITAETEN = {
    "quartal": {
        "spalte": "rel_quartal",
        "datei_suffix": "quartal",
        "periode_min": -4,
        "periode_max": 14,
        "baseline_perioden": [-2, -1],
        "min_videos_pro_periode": 3,
    },
    "monat": {
        "spalte": "rel_monat",
        "datei_suffix": "monat",
        "periode_min": -12,
        "periode_max": 42,
        "baseline_perioden": [-6, -5, -4, -3, -2, -1],
        "min_videos_pro_periode": 1,
    },
}

_GRAN_CFG = GRANULARITAETEN[GRANULARITAET]
SPALTE_PERIODE = _GRAN_CFG["spalte"]
PERIODE_MIN = _GRAN_CFG["periode_min"]
PERIODE_MAX = _GRAN_CFG["periode_max"]
BASELINE_PERIODEN = _GRAN_CFG["baseline_perioden"]
MIN_VIDEOS_PRO_PERIODE = _GRAN_CFG["min_videos_pro_periode"]

# --- Eingabedateien (Output von prepare_channel_scores.py) ---------------
DATEISTAMM_MODUS = {"populismus": "populism", "stance": "position"}
PFAD_ZEITREIHE = (
    OUTPUTS / "segment_analysis" /
    f"channel_{_GRAN_CFG['datei_suffix']}_{DATEISTAMM_MODUS[MODUS]}_timeseries.csv"
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
KANAL_WHITELIST = None                # Liste von channel_ids oder Pfad zu einer TXT/CSV; None = alle
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

def lade_zeitreihe():
    pfad = PFAD_ZEITREIHE
    if not os.path.exists(pfad):
        raise FileNotFoundError(f"Datei nicht gefunden: {pfad}")

    df = pd.read_csv(pfad)

    # Populismus-Output nennt die Wertspalte "wert", Position-Output "wert_roh" -> vereinheitlichen
    if "wert" in df.columns and "wert_roh" not in df.columns:
        df = df.rename(columns={"wert": "wert_roh"})

    pruefe = ["channel_id", SPALTE_PERIODE, "dimension", "wert_roh", "n_videos"]
    fehlend = [s for s in pruefe if s not in df.columns]
    if fehlend:
        raise KeyError(f"In '{pfad}' fehlen Spalten {fehlend}. Vorhanden: {list(df.columns)}")

    print(f"[Eingabe][{GRANULARITAET}] {len(df)} Zeilen, {df['channel_id'].nunique()} Kanaele aus {pfad}")
    return df


# =========================================================
# SCHRITT 2: Kanal-Perioden-Zellen mit zu wenig Videos verwerfen
# =========================================================

def filtere_duenne_zellen(df):
    zu_duenn = df["n_videos"] < MIN_VIDEOS_PRO_PERIODE
    print(f"[Periode] {int(zu_duenn.sum())} Kanal-Perioden-Zellen unter "
          f"MIN_VIDEOS_PRO_PERIODE={MIN_VIDEOS_PRO_PERIODE} -> verworfen.")
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

    ideo = lade_ideologie()
    df = df.merge(ideo, on="channel_id", how="left")

    return df


# =========================================================
# SCHRITT 4: Kanalauswahl
# =========================================================

def filtere_kanaele(df):
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

    df = df[(df[SPALTE_PERIODE] >= PERIODE_MIN) & (df[SPALTE_PERIODE] <= PERIODE_MAX)]
    return df


# =========================================================
# SCHRITT 5: Baseline und Index (nur Populismus)
# =========================================================

def berechne_index(df):
    basis = df[df[SPALTE_PERIODE].isin(BASELINE_PERIODEN)]

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

    df = df.merge(ref, on=["channel_id", "dimension"], how="inner")

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

def main():
    print(f"=== MODUS: {MODUS} | GRANULARITAET: {GRANULARITAET} ===")

    df = lade_zeitreihe()
    df = filtere_duenne_zellen(df)
    df = ergaenze_kanalmerkmale(df)
    df = filtere_kanaele(df)

    if MODUS == "populismus":
        df = berechne_index(df)
    else:
        df["baseline"] = np.nan
        df["index_100"] = np.nan
        df["n_baseline_videos"] = np.nan
        df["n_baseline_perioden"] = np.nan

    df["modus"] = MODUS
    df["granularitaet"] = GRANULARITAET
    spalten = ["modus", "granularitaet", "channel_id", "medientyp", "ideologie_wert", "ideologie_gruppe",
               SPALTE_PERIODE, "dimension", "wert_roh", "n_videos", "n_deskriptiv",
               "baseline", "n_baseline_videos", "n_baseline_perioden", "index_100"]
    df = df[[s for s in spalten if s in df.columns]].sort_values(
        ["dimension", "channel_id", SPALTE_PERIODE])

    pfad = str(PFAD_AUSGABE).format(modus=MODUS, granularitaet=GRANULARITAET)
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    df.to_csv(pfad, index=False, encoding="utf-8")

    print(f"\n[Ausgabe] {len(df)} Zeilen, {df['channel_id'].nunique()} Kanaele -> {pfad}")
    print(f"\nKanaele je {SPALTE_PERIODE} (ueber alle Dimensionen):")
    print(df.groupby(SPALTE_PERIODE)["channel_id"].nunique().to_string())


if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
"""
frage1_bruchpunkt_exploration.py

Ad-hoc-Exploration zu Forschungsfrage 1 (.claude/CLAUDE.md): Gibt es einen erkennbaren
Zeitpunkt, an dem sich die einzelnen Populismus-Dimensionen veraendert haben - und war das
unmittelbar nach Kriegsbeginn oder zu einem anderen Zeitpunkt? Wiederholt dieselbe Methodik
wie step6_auswertung/geglaettete_kurve.py (LOWESS-Kurve + Cluster-Bootstrap-Konfidenzband,
kanal-perioden-gleichgewichtet, kriegsniveau-referenziert), aber:

- auf der formalen Frage-1-Whitelist (frage1_kanal_whitelist.csv) statt der Gesamtmenge
- getrennt nach vier Gruppen statt einer einzigen Gesamtkurve (Absprache 2026-09-07):
    "traditionell_oerr"   Traditionelles Medium + OeRR zusammengefasst (beide fuer eine
                           eigene Ideologie-Aufspaltung zu klein/homogen - dieselbe
                           Begruendung wie TEILGRUPPEN_INTERAKTIONEN in
                           frage1_populismus_bericht.py)
    "alternative_rechts"  Alternative Medien, ideologie_gruppe == "rechts"
    "alternative_mitte"   Alternative Medien, ideologie_gruppe == "mitte"
    "alternative_links"   Alternative Medien, ideologie_gruppe == "links"
  Politiker/Partei wird bewusst ausgeschlossen (zu klein, 17 Kanaele auf der Whitelist).
- fuer alle 5 Dimensionen aus channel_video_populism.csv (4 Populismus-Dimensionen +
  Kontrollgroesse emotionale_intensitaet), nur Monatsgranularitaet.

Re-implementiert die Aggregations-/Bootstrap-Logik aus geglaettete_kurve.py direkt hier,
statt sie zu importieren: dort haengen alle abgeleiteten Konstanten (Dateipfade etc.) an
modul-globalen CONFIG-Werten (DIMENSION, FILTER, ...), die fuer eine Schleife ueber 20
Kombinationen nicht wiederverwendbar waeren, ohne das Originalskript selbst umzubauen.

Schreibt je Gruppe x Dimension eine Tabelle (CSV) + Plot (PNG) nach
scripts/adhoc/output/frage1_bruchpunkt/, sowie eine zusammenfassende
frage1_bruchpunkt_zusammenfassung.csv (erste vom Referenzniveau abweichende Periode ab
Kriegsbeginn, Liste aller abweichenden Perioden je Kombination).

Ausfuehrung (aus dem Projekt-Root):
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/adhoc/frage1_bruchpunkt_exploration.py

Adhoc-Skript nach .claude/CLAUDE.md - einmalige Auswertung fuer die Bruchpunkt-Frage,
kein Teil der wiederverwendbaren step6-Pipeline.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.nonparametric.smoothers_lowess import lowess

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable

PROJEKT_ROOT = Path(__file__).resolve().parents[2]

# =========================================================
# CONFIG
# =========================================================

PFAD_VIDEO = PROJEKT_ROOT / "outputs" / "segment_analysis" / "channel_video_populism.csv"
PFAD_WHITELIST = PROJEKT_ROOT / "outputs" / "segment_analysis" / "frage1_kanal_whitelist.csv"
PFAD_MEDIENTYP = PROJEKT_ROOT / "data" / "external" / "media_type_russia_merged.xlsx"
PFAD_IDEOLOGIE = PROJEKT_ROOT / "outputs" / "segment_analysis" / "channel_classification_ideology.csv"

AUSGABE_DIR = PROJEKT_ROOT / "scripts" / "adhoc" / "output" / "frage1_bruchpunkt"
PFAD_ZUSAMMENFASSUNG = PROJEKT_ROOT / "scripts" / "adhoc" / "output" / "frage1_bruchpunkt_zusammenfassung.csv"

SPALTE_PERIODE = "rel_monat"

DIMENSIONEN = [
    "volkszentrismus",
    "antielitismus",
    "manichaeische_moralisierung",
    "populismus_gesamt",
    "emotionale_intensitaet",  # Kontrollgroesse, siehe frage1_populismus_bericht.py
]
KONTROLLGROESSEN = {"emotionale_intensitaet"}

# Medientyp-Codes wie in deskriptiv_aggregation.py::lade_medientyp() (Typ 5 -> OeRR)
MEDIENTYP_LABELS = {1: "ÖRR", 2: "Traditionelles Medium", 3: "Alternatives Medium",
                    4: "Politiker/Partei", 5: "ÖRR"}
IDEOLOGIE_SCHNITTE = [-0.5, 0.5]
IDEOLOGIE_LABELS = ["links", "mitte", "rechts"]

GRUPPEN = {
    "traditionell_oerr": lambda df: df["medientyp"].isin(["ÖRR", "Traditionelles Medium"]),
    "alternative_rechts": lambda df: (df["medientyp"] == "Alternatives Medium") & (df["ideologie_gruppe"] == "rechts"),
    "alternative_mitte": lambda df: (df["medientyp"] == "Alternatives Medium") & (df["ideologie_gruppe"] == "mitte"),
    "alternative_links": lambda df: (df["medientyp"] == "Alternatives Medium") & (df["ideologie_gruppe"] == "links"),
}

# Dieselben Defaults wie geglaettete_kurve.py, fuer Vergleichbarkeit mit der dort bereits
# vorhandenen (engeren) antielitismus-Kurve.
LOWESS_FRAC = 0.15
N_BOOTSTRAP = 150
ALPHA = 0.05
RANDOM_SEED = 42
PERIODE_REFERENZ_MIN = 0  # theta_c je Kanal = Mittelwert nur ueber Perioden >= 0 (Kriegsniveau)

KRIEGSBEGINN = "2022-02-24"
EREIGNISSE = [
    {"name": "Bucha-Massaker", "datum": "2022-04-03"},
    {"name": "Energiepreisschock", "datum": "2022-08-01"},
    {"name": "Gas-/Energiepreisbremse beschlossen", "datum": "2022-12-15"},
    {"name": "Gegenoffensive der Ukraine", "datum": "2023-06-04"},
    {"name": "US-Wahl", "datum": "2024-11-05"},
    {"name": "Bundestagswahl", "datum": "2025-02-23"},
    {"name": "Waffenstillstandsverhandlungen (Istanbul)", "datum": "2025-05-16"},
    {"name": "Alaska-Gipfel Trump-Putin", "datum": "2025-08-15"},
    {"name": "28-Punkte-Friedensplan", "datum": "2025-11-21"},
]


def periode_aus_datum(datum_str):
    datum = pd.Timestamp(datum_str)
    start = pd.Timestamp(KRIEGSBEGINN)
    monate = (datum.year - start.year) * 12 + (datum.month - start.month)
    monate -= 1 if datum.day < start.day else 0
    return monate


# =========================================================
# DATEN LADEN
# =========================================================

def lade_basisdaten():
    df = pd.read_csv(PFAD_VIDEO)
    df["channel_id"] = df["channel_id"].astype(str)

    whitelist = pd.read_csv(PFAD_WHITELIST)
    whitelist_ids = set(whitelist["channel_id"].astype(str))
    n_vor = df["channel_id"].nunique()
    df = df[df["channel_id"].isin(whitelist_ids)]
    print(f"[Whitelist] {n_vor} -> {df['channel_id'].nunique()} Kanaele.")

    med = pd.read_excel(PFAD_MEDIENTYP)[["channel_id", "type"]]
    med["channel_id"] = med["channel_id"].astype(str)
    med["medientyp"] = pd.to_numeric(med["type"], errors="coerce").map(MEDIENTYP_LABELS)
    df = df.merge(med[["channel_id", "medientyp"]], on="channel_id", how="left")

    ideo = pd.read_csv(PFAD_IDEOLOGIE)[["channel_id", "gesellschaft_mean"]]
    ideo["channel_id"] = ideo["channel_id"].astype(str)
    ideo["ideologie_gruppe"] = pd.cut(
        ideo["gesellschaft_mean"], bins=[-np.inf] + IDEOLOGIE_SCHNITTE + [np.inf],
        labels=IDEOLOGIE_LABELS,
    ).astype(str)
    df = df.merge(ideo[["channel_id", "ideologie_gruppe"]], on="channel_id", how="left")

    return df


# =========================================================
# AGGREGATION + BOOTSTRAP (analog geglaettete_kurve.py)
# =========================================================

def aggregiere_kanal_periode(df, dimension):
    daten = df.rename(columns={dimension: "y"}).dropna(subset=["y"]).copy()
    return daten.groupby(["channel_id", SPALTE_PERIODE], as_index=False).agg(
        y=("y", "mean"), n_videos=("y", "size"),
    )


def berechne_kriegsniveau_referenz(kanal_periode):
    kriegsdaten = kanal_periode[kanal_periode[SPALTE_PERIODE] >= PERIODE_REFERENZ_MIN]
    theta = kriegsdaten.groupby("channel_id")["y"].mean().to_dict()
    alle = set(kanal_periode["channel_id"].unique())
    return theta, alle - set(theta.keys())


def geglaettete_kurve_mit_bootstrap(kanal_periode, theta, bezeichnung):
    grid = np.array(sorted(kanal_periode[SPALTE_PERIODE].unique()), dtype=float)
    kanaele = kanal_periode["channel_id"].unique()

    glatt = lowess(kanal_periode["y_bereinigt"], kanal_periode[SPALTE_PERIODE],
                    frac=LOWESS_FRAC, xvals=grid, return_sorted=False)

    rng = np.random.default_rng(RANDOM_SEED)
    bootstrap_kurven = np.full((N_BOOTSTRAP, len(grid)), np.nan)

    for i in tqdm(range(N_BOOTSTRAP), desc=f"Bootstrap {bezeichnung}", unit="rep"):
        sample_kanaele = rng.choice(kanaele, size=len(kanaele), replace=True)
        counts = pd.Series(sample_kanaele).value_counts()
        frames = []
        for k, n in counts.items():
            teil = kanal_periode[kanal_periode["channel_id"] == k]
            if n > 1:
                teil = pd.concat([teil] * int(n), ignore_index=True)
            frames.append(teil)
        boot_df = pd.concat(frames, ignore_index=True)
        try:
            bootstrap_kurven[i] = lowess(boot_df["y_bereinigt"], boot_df[SPALTE_PERIODE],
                                          frac=LOWESS_FRAC, xvals=grid, return_sorted=False)
        except Exception:
            continue

    unten = np.nanpercentile(bootstrap_kurven, 100 * ALPHA / 2, axis=0)
    oben = np.nanpercentile(bootstrap_kurven, 100 * (1 - ALPHA / 2), axis=0)
    theta_quer = np.mean(list(theta.values()))

    tab = pd.DataFrame({SPALTE_PERIODE: grid, "geglaettet": glatt, "ci_unten": unten, "ci_oben": oben})
    tab["abweichend_von_referenz"] = ~((tab["ci_unten"] <= theta_quer) & (theta_quer <= tab["ci_oben"]))
    return tab, theta_quer


def plotte(tab, theta_quer, gruppe, dimension, n_kanaele):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(tab[SPALTE_PERIODE], tab["geglaettet"], color="tab:blue", linewidth=2, label="geglaettet (LOWESS)")
    ax.fill_between(tab[SPALTE_PERIODE], tab["ci_unten"], tab["ci_oben"], alpha=0.2, color="tab:blue",
                     label=f"{int((1 - ALPHA) * 100)}%-Bootstrap-Band")
    ax.axhline(theta_quer, color="grey", linewidth=0.8, linestyle="--", label="mittleres Kriegsniveau")
    ax.axvline(-0.5, color="black", linestyle="--", linewidth=1)

    y_min, y_max = ax.get_ylim()
    spanne = y_max - y_min
    for idx, ereignis in enumerate(EREIGNISSE):
        pos = periode_aus_datum(ereignis["datum"])
        if pos < tab[SPALTE_PERIODE].min() or pos > tab[SPALTE_PERIODE].max():
            continue
        ax.axvline(pos, color="tab:red", linestyle=":", linewidth=0.8, alpha=0.6)
        ax.text(pos, y_max - spanne * (0.03 + 0.06 * (idx % 3)), ereignis["name"], rotation=90,
                fontsize=6.5, color="tab:red", ha="right", va="top", alpha=0.8)

    ax.set_xlabel("Periode (Monat relativ zum Kriegsbeginn)")
    ax.set_ylabel(f"{dimension} (kanalbereinigt)")
    ax.set_title(f"{dimension} - {gruppe} (n={n_kanaele} Kanaele, Frage-1-Whitelist, monatlich)")
    ax.legend(fontsize=8)
    fig.tight_layout()

    pfad = AUSGABE_DIR / f"geglaettet_{gruppe}_{dimension}_monat.png"
    fig.savefig(pfad, dpi=150)
    plt.close(fig)
    return pfad


def abweichende_perioden_zusammenfassen(tab):
    """Fasst zusammenhaengende Bloecke von 'abweichend_von_referenz'-Perioden ab
    Kriegsbeginn (periode >= 0) zu lesbaren Intervallen zusammen, z.B. '11-13, 34-36'."""
    ab_krieg = tab[tab[SPALTE_PERIODE] >= 0].sort_values(SPALTE_PERIODE)
    abweichend = ab_krieg[ab_krieg["abweichend_von_referenz"]][SPALTE_PERIODE].astype(int).tolist()
    if not abweichend:
        return "", None
    bloecke = []
    start = vorherige = abweichend[0]
    for p in abweichend[1:]:
        if p == vorherige + 1:
            vorherige = p
            continue
        bloecke.append((start, vorherige))
        start = vorherige = p
    bloecke.append((start, vorherige))
    text = ", ".join(f"{a}-{b}" if a != b else f"{a}" for a, b in bloecke)
    return text, abweichend[0]


# =========================================================
# MAIN
# =========================================================

def main():
    AUSGABE_DIR.mkdir(parents=True, exist_ok=True)
    df = lade_basisdaten()

    zeilen_zusammenfassung = []

    for gruppe, filter_fn in GRUPPEN.items():
        df_gruppe = df[filter_fn(df)]
        n_kanaele_gruppe = df_gruppe["channel_id"].nunique()
        print(f"\n{'=' * 70}\nGRUPPE: {gruppe} ({n_kanaele_gruppe} Kanaele)\n{'=' * 70}")

        for dimension in DIMENSIONEN:
            kontrolle = " [KONTROLLGROESSE]" if dimension in KONTROLLGROESSEN else ""
            print(f"\n--- {dimension}{kontrolle} ---")

            kanal_periode = aggregiere_kanal_periode(df_gruppe, dimension)
            if kanal_periode["channel_id"].nunique() < 5:
                print(f"  [Warnung] Nur {kanal_periode['channel_id'].nunique()} Kanaele -> uebersprungen.")
                continue

            theta, ohne_kriegsdaten = berechne_kriegsniveau_referenz(kanal_periode)
            if ohne_kriegsdaten:
                kanal_periode = kanal_periode[~kanal_periode["channel_id"].isin(ohne_kriegsdaten)]
                print(f"  [Referenz-Filter] {len(ohne_kriegsdaten)} Kanaele ohne Kriegsdaten -> ausgeschlossen.")

            if kanal_periode["channel_id"].nunique() < 5:
                print(f"  [Warnung] Nur {kanal_periode['channel_id'].nunique()} Kanaele nach Referenz-Filter -> uebersprungen.")
                continue

            kanal_periode["theta_c"] = kanal_periode["channel_id"].map(theta)
            theta_quer_vorab = np.mean(list(theta.values()))
            kanal_periode["y_bereinigt"] = kanal_periode["y"] - kanal_periode["theta_c"] + theta_quer_vorab

            n_kanaele_final = kanal_periode["channel_id"].nunique()
            tab, theta_quer = geglaettete_kurve_mit_bootstrap(kanal_periode, theta, f"{gruppe}/{dimension}")

            pfad_tabelle = AUSGABE_DIR / f"geglaettet_{gruppe}_{dimension}_monat.csv"
            tab.to_csv(pfad_tabelle, index=False, encoding="utf-8")
            pfad_plot = plotte(tab, theta_quer, gruppe, dimension, n_kanaele_final)

            intervalle, erste_periode = abweichende_perioden_zusammenfassen(tab)
            print(f"  n_kanaele={n_kanaele_final}, theta_quer={theta_quer:.4f}")
            print(f"  Abweichende Perioden ab Kriegsbeginn: {intervalle or '(keine)'}")
            print(f"  -> {pfad_tabelle.name}")

            zeilen_zusammenfassung.append({
                "gruppe": gruppe,
                "dimension": dimension,
                "ist_kontrollgroesse": dimension in KONTROLLGROESSEN,
                "n_kanaele": n_kanaele_final,
                "theta_quer": theta_quer,
                "erste_abweichende_periode_ab_krieg": erste_periode,
                "abweichende_perioden_ab_krieg": intervalle,
                "wert_periode_0": float(tab.loc[tab[SPALTE_PERIODE] == 0, "geglaettet"].iloc[0])
                    if (tab[SPALTE_PERIODE] == 0).any() else np.nan,
                "wert_letzte_periode": float(tab["geglaettet"].iloc[-1]),
                "pfad_tabelle": str(pfad_tabelle.relative_to(PROJEKT_ROOT)),
                "pfad_plot": str(pfad_plot.relative_to(PROJEKT_ROOT)),
            })

    zusammenfassung = pd.DataFrame(zeilen_zusammenfassung)
    zusammenfassung.to_csv(PFAD_ZUSAMMENFASSUNG, index=False, encoding="utf-8")
    print(f"\n{'=' * 70}\n[Zusammenfassung] {len(zusammenfassung)} Kombinationen -> {PFAD_ZUSAMMENFASSUNG}\n{'=' * 70}")


if __name__ == "__main__":
    main()

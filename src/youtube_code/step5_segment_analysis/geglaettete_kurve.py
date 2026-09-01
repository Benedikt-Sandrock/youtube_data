# -*- coding: utf-8 -*-
"""
geglaettete_kurve.py

Deskriptiv-explorativer erster Schritt vor formalen Bruchpunkt-/Phasen-Tests: zeigt eine
geglaettete Kurve des kanalbereinigten Signals ueber die Zeit, mit einem
Cluster-Bootstrap-Konfidenzband. Macht sichtbar, ob es ueberhaupt erkennbare Phasen/Peaks
gibt, ohne vorab eine Form (linear, quadratisch, Bruchpunkt) anzunehmen.

Ablauf (Hauptspezifikation):
1. Aggregation auf Kanal x Periode: pro Kanal und Periode wird zuerst der Videomittelwert
   gebildet. Jeder Kanal zaehlt an jedem Zeitpunkt GLEICH viel, unabhaengig davon, wie
   viele Videos er dort hat - behebt die Verzerrung, die entsteht, wenn Kanaele mit
   hohem/niedrigem Niveau systematisch mehr/weniger Videos zu bestimmten Zeiten haben.
2. Referenzniveau je Kanal (theta_c) aus dem KRIEGSNIVEAU DES KANALS SELBST (Mittelwert
   nur ueber Perioden >= PERIODE_REFERENZ_MIN, standardmaessig 0 = Kriegsbeginn) - NICHT
   aus der Vorkriegs-Baseline. Dadurch bleiben auch Kanaele ohne gueltige Baseline
   enthalten (jeder Kanal in der Stichprobe hat per Definition Kriegsvideos). Baseline-
   Perioden (falls in den Daten vorhanden) werden bei der Referenzberechnung ausgeklammert,
   fliessen aber weiterhin in die geglaettete Kurve selbst ein.
   y_bereinigt_{c,t} = y_{c,t} - theta_c + theta_quer
   theta_quer = ungewichteter Mittelwert von theta_c UEBER DIE VERWENDETEN KANAELE
   (nicht videogewichtet - vermeidet, dass videostarke Kanaele die Referenzlinie dominieren).
3. LOWESS-Glaettung des kanalbereinigten Signals ueber die Periode, auf Kanal-Perioden-Ebene.
4. Cluster-Bootstrap (Kanaele MIT Zuruecklegen resamplen, nicht einzelne Videos/Zellen -
   wegen der Panel-Struktur), um ein punktweises Konfidenzband um die geglaettete Kurve
   zu legen. theta_c bleibt dabei fix (aus der Baseline-Datei), nur die Kanalauswahl wird
   resampelt.

Nutzt dieselbe gefilterte Video-Datengrundlage wie fe_signifikanz_test.py (Import von
dort) - CONFIG (MODUS, GRANULARITAET, DIMENSION, FILTER, PERIODE_MIN/MAX) wird dort
gepflegt.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.nonparametric.smoothers_lowess import lowess

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        """Fallback ohne Fortschrittsbalken, falls tqdm nicht installiert ist
        (pip install tqdm --break-system-packages)."""
        return iterable

from youtube_code.config import OUTPUTS
from fe_signifikanz_test import lade_gefilterte_daten, DIMENSION, SPALTE_PERIODE, MODUS, GRANULARITAET, FILTER

# =========================================================
# CONFIG
# =========================================================

LOWESS_FRAC = 0.15        # Anteil der Daten im gleitenden Fenster (kleiner = welliger, groesser = glatter)
N_BOOTSTRAP = 150         # Anzahl Cluster-Bootstrap-Wiederholungen
ALPHA = 0.05              # fuer (1-ALPHA)-Konfidenzband
RANDOM_SEED = 42

# Referenzniveau theta_c je Kanal wird nur aus Perioden >= diesem Wert berechnet
# (Kriegsniveau, nicht Vorkriegs-Baseline). 0 = Kriegsbeginn.
PERIODE_REFERENZ_MIN = 0

# Ereignis-Marker fuer den Plot.
# ACHTUNG: Daten aus dem Gedaechtnis/einer kurzen Recherche zusammengestellt, insbesondere
# "Energiepreisschock" (Prozess ueber Monate, kein singulaeres Datum) und
# "Waffenstillstandsverhandlungen" (mehrere Runden 2025, hier: direkte Ukraine-Russland-
# Gespraeche in Istanbul) vor Verwendung in der Arbeit noch mal gegenpruefen.
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
    {"name": "28-Punkte-Friedensplan", "datum": "2025-11-21"}
]


def periode_aus_datum(datum_str):
    """Wandelt ein Kalenderdatum in dieselbe Periodenzaehlung um wie SPALTE_PERIODE
    (tagesgenau relativ zu KRIEGSBEGINN, konsistent mit prepare_channel_scores.py)."""
    datum = pd.Timestamp(datum_str)
    start = pd.Timestamp(KRIEGSBEGINN)
    monate_pro_periode = {"quartal": 3, "monat": 1}[GRANULARITAET]
    monate = (datum.year - start.year) * 12 + (datum.month - start.month)
    monate -= 1 if datum.day < start.day else 0
    return monate // monate_pro_periode

PFAD_PLOT = OUTPUTS / "segment_analysis" / "plots" / f"geglaettet_{MODUS}_{DIMENSION}_{GRANULARITAET}.png"
PFAD_TABELLE = OUTPUTS / "segment_analysis" / f"geglaettet_{MODUS}_{DIMENSION}_{GRANULARITAET}.csv"


# =========================================================
# SCHRITT 1: Kanal x Periode Aggregation
# =========================================================

def aggregiere_kanal_periode(df):
    """Video -> Kanal x Periode Mittelwert. Jede Zeile danach = ein Kanal an einer
    Periode, unabhaengig davon wie viele Videos zugrunde lagen (n_videos wird als
    Zusatzinfo mitgefuehrt, aber NICHT als Gewicht verwendet)."""
    daten = df.rename(columns={DIMENSION: "y", SPALTE_PERIODE: "periode_num"}).copy()
    daten["channel_id"] = daten["channel_id"].astype(str)

    kanal_periode = daten.groupby(["channel_id", "periode_num"], as_index=False).agg(
        y=("y", "mean"),
        n_videos=("y", "size"),
    )
    return kanal_periode


# =========================================================
# SCHRITT 2: Referenzniveau je Kanal aus der reinen Baseline
# =========================================================

def berechne_kriegsniveau_referenz(kanal_periode):
    """theta_c je Kanal als Mittelwert NUR ueber Kriegsperioden (periode_num >=
    PERIODE_REFERENZ_MIN), unabhaengig von MODUS. Vorkriegs-Baseline-Perioden (falls in
    den Daten vorhanden) werden hier ausgeklammert, aber nicht aus der Kurve selbst
    entfernt. Kanaele ganz ohne Kriegsperiode-Beobachtung (sollte praktisch nicht
    vorkommen) werden separat zurueckgegeben."""
    kriegsdaten = kanal_periode[kanal_periode["periode_num"] >= PERIODE_REFERENZ_MIN]
    theta = kriegsdaten.groupby("channel_id")["y"].mean().to_dict()

    alle_kanaele = set(kanal_periode["channel_id"].unique())
    ohne_kriegsdaten = alle_kanaele - set(theta.keys())
    return theta, ohne_kriegsdaten


# =========================================================
# SCHRITT 3+4: GEGLAETTETE KURVE + CLUSTER-BOOTSTRAP
# =========================================================

def geglaettete_kurve_mit_bootstrap(kanal_periode, theta):
    grid = np.array(sorted(kanal_periode["periode_num"].unique()), dtype=float)
    kanaele = kanal_periode["channel_id"].unique()

    glatt = lowess(kanal_periode["y_bereinigt"], kanal_periode["periode_num"],
                    frac=LOWESS_FRAC, xvals=grid, return_sorted=False)

    rng = np.random.default_rng(RANDOM_SEED)
    bootstrap_kurven = np.full((N_BOOTSTRAP, len(grid)), np.nan)

    print(f"[Bootstrap] {N_BOOTSTRAP} Wiederholungen ueber {len(kanaele)} Kanaele "
          f"(Kanal-Perioden-Ebene, theta_c fix) ...")
    for i in tqdm(range(N_BOOTSTRAP), desc="Cluster-Bootstrap", unit="rep"):
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
            kurve = lowess(boot_df["y_bereinigt"], boot_df["periode_num"],
                            frac=LOWESS_FRAC, xvals=grid, return_sorted=False)
            bootstrap_kurven[i] = kurve
        except Exception:
            continue  # z.B. zu wenig Datenpunkte an einer Stelle in diesem Replikat

    unten = np.nanpercentile(bootstrap_kurven, 100 * ALPHA / 2, axis=0)
    oben = np.nanpercentile(bootstrap_kurven, 100 * (1 - ALPHA / 2), axis=0)

    theta_quer = np.mean(list(theta.values()))

    tab = pd.DataFrame({
        SPALTE_PERIODE: grid,
        "geglaettet": glatt,
        "ci_unten": unten,
        "ci_oben": oben,
    })
    tab["abweichend_von_referenz"] = ~((tab["ci_unten"] <= theta_quer) & (theta_quer <= tab["ci_oben"]))
    return tab, theta_quer


# =========================================================
# PLOT
# =========================================================

def plotte(tab, theta_quer):
    fig, ax = plt.subplots(figsize=(10, 5))

    ax.plot(tab[SPALTE_PERIODE], tab["geglaettet"], color="tab:blue", linewidth=2,
            label="geglaettet (LOWESS, kanal-perioden-gleichgewichtet, kriegsniveau-referenziert)")
    ax.fill_between(tab[SPALTE_PERIODE], tab["ci_unten"], tab["ci_oben"],
                     alpha=0.2, color="tab:blue", label=f"{int((1-ALPHA)*100)}%-Bootstrap-Band")

    ax.axhline(theta_quer, color="grey", linewidth=0.8, linestyle="--",
               label="mittleres Kriegsniveau (ungewichtet ueber Kanaele)")
    ax.axvline(-0.5, color="black", linestyle="--", linewidth=1)

    y_min, y_max = ax.get_ylim()
    spanne = y_max - y_min
    for idx, ereignis in enumerate(EREIGNISSE):
        pos = periode_aus_datum(ereignis["datum"])
        if pos < tab[SPALTE_PERIODE].min() or pos > tab[SPALTE_PERIODE].max():
            continue  # Ereignis liegt ausserhalb des dargestellten Zeitfensters
        ax.axvline(pos, color="tab:red", linestyle=":", linewidth=0.8, alpha=0.6)
        y_text = y_max - spanne * (0.03 + 0.06 * (idx % 3))
        ax.text(pos, y_text, ereignis["name"], rotation=90, fontsize=6.5,
                color="tab:red", ha="right", va="top", alpha=0.8)

    ax.set_xlabel(f"Periode ({SPALTE_PERIODE.replace('rel_', '')} relativ zum Kriegsbeginn)")
    ax.set_ylabel(f"{DIMENSION} (kanalbereinigt)")
    ax.set_title(f"{DIMENSION} ({MODUS}, {GRANULARITAET}) - geglaettet mit Bootstrap-Band\n"
                 f"Kanal-perioden-gleichgewichtet, Kriegsniveau-referenziert | Filter: {FILTER}")
    ax.legend(fontsize=8)
    fig.tight_layout()

    PFAD_PLOT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(PFAD_PLOT, dpi=150)
    plt.close(fig)
    print(f"[Plot] {PFAD_PLOT}")


# =========================================================
# MAIN
# =========================================================

def main():
    print(f"=== Geglaettete Kurve: {DIMENSION} ({MODUS}, {GRANULARITAET}) ===")
    print(f"Filter: {FILTER}")

    df = lade_gefilterte_daten()
    if df["channel_id"].nunique() < 2:
        raise ValueError("Weniger als 2 Kanaele nach Filterung -> Bereinigung nicht sinnvoll.")

    kanal_periode = aggregiere_kanal_periode(df)
    print(f"[Aggregation] {len(kanal_periode)} Kanal-Perioden-Zellen aus "
          f"{kanal_periode['channel_id'].nunique()} Kanaelen.")

    kanaele_vorhanden = set(kanal_periode["channel_id"].unique())
    theta, ohne_kriegsdaten = berechne_kriegsniveau_referenz(kanal_periode)

    if ohne_kriegsdaten:
        vor = kanal_periode["channel_id"].nunique()
        kanal_periode = kanal_periode[~kanal_periode["channel_id"].isin(ohne_kriegsdaten)]
        print(f"[Referenz-Filter] {len(ohne_kriegsdaten)} von {vor} Kanaelen ganz ohne "
              f"Beobachtung ab Periode {PERIODE_REFERENZ_MIN} -> ausgeschlossen "
              f"(kein Kriegsniveau berechenbar). {kanal_periode['channel_id'].nunique()} Kanaele verbleiben.")

    kanal_periode["theta_c"] = kanal_periode["channel_id"].map(theta)
    theta_quer_vorab = np.mean(list(theta.values()))
    kanal_periode["y_bereinigt"] = kanal_periode["y"] - kanal_periode["theta_c"] + theta_quer_vorab

    if kanal_periode["channel_id"].nunique() < 2:
        raise ValueError("Weniger als 2 Kanaele nach Referenz-Filter -> Abbruch.")

    tab, theta_quer = geglaettete_kurve_mit_bootstrap(kanal_periode, theta)

    tab.to_csv(PFAD_TABELLE, index=False, encoding="utf-8")
    print(f"[Tabelle] {PFAD_TABELLE}")

    abweichend = tab[tab["abweichend_von_referenz"]]
    print(f"\n[Abweichende Perioden] {len(abweichend)} von {len(tab)} Perioden, in denen das "
          f"Bootstrap-Band das mittlere Referenzniveau ({theta_quer:.4f}) NICHT einschliesst:")
    if not abweichend.empty:
        print(abweichend[[SPALTE_PERIODE, "geglaettet", "ci_unten", "ci_oben"]].to_string(index=False))
    else:
        print("  (keine)")

    plotte(tab, theta_quer)


if __name__ == "__main__":
    main()
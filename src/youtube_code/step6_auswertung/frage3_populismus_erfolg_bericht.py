# -*- coding: utf-8 -*-
"""
frage3_populismus_erfolg_bericht.py

Konsolidierte, formale Antwort auf Forschungsfrage 3 (.claude/CLAUDE.md):
"Werden Kanaele, die populistischer werden, auch erfolgreicher?"

Populismus-Score liegt nur fuer LLM-klassifizierte Videos vor
(channel_{quartal,monat}_populism_timeseries.csv, Dimension
populismus_gesamt), die Erfolgsmetrik dagegen fuer alle Whitelist-Videos
(channel_{quartal,monat}_erfolg_timeseries.csv, Dimension log_views) -
Merge daher auf Kanal x Periode-Ebene (nicht Video-Ebene), sonst
verschenkt man die breitere Erfolgs-Stichprobe. Beide Eingabedateien
kommen aus prepare_channel_scores.py (Schritt 0) bzw.
prepare_success_metrics.py (Schritt 0c), zusaetzlich gefiltert auf die
Whitelist aus frage1_stichprobe.py (Schritt 0b, siehe
.claude/plans/success_analysis.md Punkt 3). Alle drei Skripte MUESSEN
vorher einmal gelaufen sein.

Zwei Bausteine je Granularitaet:

(a) Panel mit Kanal-FE + Perioden-FE (primaer):
    log_views ~ populismus_gesamt + C(channel_id) + C(periode)
    Standardfehler auf Kanalebene geclustert. Kontrolliert Kanal-
    Fixeffekte UND gemeinsame Zeittrends (sonst Scheinkorrelation durch
    allgemeines Wachstum ueber die Zeit). Der Koeffizient ist die reine
    Innerhalb-Kanal-Korrelation zwischen Populismus-Niveau und Erfolg in
    derselben Periode - KEINE Kausalaussage (siehe Limitationen unten).

(b) Delta-Delta-Korrelation je Kanal (Robustheit/Visualisierung): je
    Kanal mean(post) - mean(pre) fuer populismus_gesamt und fuer
    log_views, Pearson- und Spearman-Korrelation ueber alle Kanaele plus
    eine einfache OLS-Gerade, als Scatterplot. Antwortet auf dieselbe
    Frage aus einer anderen, robusteren Perspektive (Kanal-Niveau-
    Veraenderung statt Perioden-Panel).

Methodische Limitation: Frage 3 ist rein korrelativ, es gibt keine
exogene Variation fuer Δpopulismus selbst (anders als der Kriegsbeginn
fuer Frage 1/2) - moegliche Rueckwaertskausalitaet (erfolgreiche Kanaele
werden populistischer, nicht umgekehrt) oder gemeinsame Drittvariablen
koennen mit diesem Design nicht ausgeschlossen werden.

Schreibt frage3_populismus_erfolg_bericht_{granularitaet}.csv (beide
Bausteine in einer Tabelle, Spalte "baustein" unterscheidet sie) sowie
einen Scatterplot je Granularitaet nach outputs/segment_analysis/plots/.
Direkt im Ordner ausfuehren, nicht als -m-Modul.
"""

import matplotlib.pyplot as plt
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import pearsonr, spearmanr

from youtube_code.config import OUTPUTS

# =========================================================
# CONFIG
# =========================================================

RESULTS_PATH = OUTPUTS / "segment_analysis"
PFAD_WHITELIST = RESULTS_PATH / "frage1_kanal_whitelist.csv"
PFAD_AUSGABE = RESULTS_PATH / "frage3_populismus_erfolg_bericht_{granularitaet}.csv"
PFAD_PLOT = RESULTS_PATH / "plots" / "frage3_delta_delta_{granularitaet}.png"

GRANULARITAETEN = {
    "quartal": {"spalte": "rel_quartal", "periode_min": -4, "periode_max": 14},
    "monat":   {"spalte": "rel_monat",   "periode_min": -12, "periode_max": 42},
}


# =========================================================
# DATEN LADEN
# =========================================================

def lade_merged_daten(granularitaet, spalte_periode):
    pop_pfad = RESULTS_PATH / f"channel_{granularitaet}_populism_timeseries.csv"
    erfolg_pfad = RESULTS_PATH / f"channel_{granularitaet}_erfolg_timeseries.csv"

    pop = pd.read_csv(pop_pfad)
    pop = pop[pop["dimension"] == "populismus_gesamt"][["channel_id", spalte_periode, "wert"]] \
        .rename(columns={"wert": "populismus_gesamt"})
    pop["channel_id"] = pop["channel_id"].astype(str)

    erfolg = pd.read_csv(erfolg_pfad)
    erfolg = erfolg[erfolg["dimension"] == "log_views"][["channel_id", "channel_title", spalte_periode, "wert"]] \
        .rename(columns={"wert": "log_views"})
    erfolg["channel_id"] = erfolg["channel_id"].astype(str)

    n_pop, n_erfolg = pop["channel_id"].nunique(), erfolg["channel_id"].nunique()
    merged = pop.merge(erfolg, on=["channel_id", spalte_periode], how="inner")

    whitelist = pd.read_csv(PFAD_WHITELIST)
    whitelist_ids = set(whitelist["channel_id"].astype(str))
    n_vor_whitelist = merged["channel_id"].nunique()
    merged = merged[merged["channel_id"].isin(whitelist_ids)]

    print(f"[Merge][{granularitaet}] Populismus-Zeitreihe: {n_pop} Kanaele, Erfolgs-Zeitreihe: "
          f"{n_erfolg} Kanaele -> {len(merged)} gemeinsame Kanal-Perioden-Zeilen "
          f"({n_vor_whitelist} -> {merged['channel_id'].nunique()} Kanaele nach zusaetzlichem "
          f"Whitelist-Filter auf {PFAD_WHITELIST}).")
    return merged


def _fenster(df, spalte_periode, periode_min, periode_max):
    return df[(df[spalte_periode] >= periode_min) & (df[spalte_periode] <= periode_max)]


# =========================================================
# BAUSTEIN (a): Panel mit Kanal-FE + Perioden-FE
# =========================================================

def panel_fe_test(df, spalte_periode):
    daten = df.dropna(subset=["populismus_gesamt", "log_views"]).copy()
    daten["channel_id"] = daten["channel_id"].astype(str)

    n_kanaele = daten["channel_id"].nunique()
    if n_kanaele < 2 or daten[spalte_periode].nunique() < 2:
        print(f"  [Skip][Panel-FE] zu wenig Variation (Kanaele={n_kanaele}).")
        return None

    formel = f"log_views ~ populismus_gesamt + C(channel_id) + C({spalte_periode})"
    modell = smf.ols(formel, data=daten).fit(
        cov_type="cluster", cov_kwds={"groups": daten["channel_id"]}
    )

    return {
        "n_beobachtungen": len(daten),
        "n_kanaele": n_kanaele,
        "koeffizient": modell.params["populismus_gesamt"],
        "se": modell.bse["populismus_gesamt"],
        "p": modell.pvalues["populismus_gesamt"],
    }


# =========================================================
# BAUSTEIN (b): Delta-Delta-Korrelation je Kanal
# =========================================================

def delta_delta_korrelation(df, spalte_periode):
    daten = df.dropna(subset=["populismus_gesamt", "log_views"]).copy()
    daten["post"] = (daten[spalte_periode] >= 0).astype(int)

    def _delta(gruppe):
        vor = gruppe.loc[gruppe["post"] == 0]
        nach = gruppe.loc[gruppe["post"] == 1]
        if vor.empty or nach.empty:
            return pd.Series({"delta_populismus": None, "delta_log_views": None})
        return pd.Series({
            "delta_populismus": nach["populismus_gesamt"].mean() - vor["populismus_gesamt"].mean(),
            "delta_log_views": nach["log_views"].mean() - vor["log_views"].mean(),
        })

    delta = daten.groupby("channel_id").apply(_delta, include_groups=False).reset_index()
    n_vor = len(delta)
    delta = delta.dropna(subset=["delta_populismus", "delta_log_views"])
    print(f"  [Delta-Delta] {n_vor} -> {len(delta)} Kanaele mit sowohl Vor- als auch "
          f"Nachkriegsbeobachtung in beiden Dimensionen.")

    if len(delta) < 3:
        print("  [Skip][Delta-Delta] zu wenige Kanaele fuer eine Korrelation.")
        return None, delta

    pearson_r, pearson_p = pearsonr(delta["delta_populismus"], delta["delta_log_views"])
    spearman_r, spearman_p = spearmanr(delta["delta_populismus"], delta["delta_log_views"])
    modell = smf.ols("delta_log_views ~ delta_populismus", data=delta).fit()

    ergebnis = {
        "n_kanaele": len(delta),
        "pearson_r": pearson_r,
        "pearson_p": pearson_p,
        "spearman_r": spearman_r,
        "spearman_p": spearman_p,
        "koeffizient": modell.params["delta_populismus"],
        "se": modell.bse["delta_populismus"],
        "p": modell.pvalues["delta_populismus"],
    }
    return ergebnis, delta


def _plotte_delta_delta(delta, granularitaet, ergebnis):
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(delta["delta_populismus"], delta["delta_log_views"], alpha=0.6, edgecolor="black", linewidth=0.4)
    ax.axhline(0, color="grey", linewidth=0.8)
    ax.axvline(0, color="grey", linewidth=0.8)
    ax.set_xlabel("Δ populismus_gesamt (Nachkrieg-Mittel − Vorkrieg-Mittel)")
    ax.set_ylabel("Δ log_views (Nachkrieg-Mittel − Vorkrieg-Mittel)")
    titel = f"Δ Populismus vs. Δ Erfolg je Kanal ({granularitaet})"
    if ergebnis:
        titel += f"\nn={ergebnis['n_kanaele']}, Pearson r={ergebnis['pearson_r']:.3f} (p={ergebnis['pearson_p']:.4f})"
    ax.set_title(titel)
    fig.tight_layout()

    pfad = str(PFAD_PLOT).format(granularitaet=granularitaet)
    PFAD_PLOT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(pfad, dpi=150)
    plt.close(fig)
    print(f"  [Plot] -> {pfad}")


# =========================================================
# MAIN
# =========================================================

def verarbeite_granularitaet(granularitaet, gran_cfg):
    spalte_periode = gran_cfg["spalte"]
    df = lade_merged_daten(granularitaet, spalte_periode)
    df_g = _fenster(df, spalte_periode, gran_cfg["periode_min"], gran_cfg["periode_max"])
    print(f"[Fenster][{granularitaet}] {len(df)} -> {len(df_g)} Kanal-{granularitaet}-Beobachtungen "
          f"({df_g['channel_id'].nunique()} Kanaele).")

    zeilen = []

    print(f"\n=== Baustein (a): Panel-FE ({granularitaet}) ===")
    panel = panel_fe_test(df_g, spalte_periode)
    if panel:
        print(f"  koeffizient_populismus={panel['koeffizient']:+.4f} (p={panel['p']:.4f}), "
              f"n_kanaele={panel['n_kanaele']}, n_beobachtungen={panel['n_beobachtungen']}")
        zeilen.append({"baustein": "panel_fe", **panel})

    print(f"\n=== Baustein (b): Delta-Delta-Korrelation ({granularitaet}) ===")
    delta_ergebnis, delta = delta_delta_korrelation(df_g, spalte_periode)
    if delta_ergebnis:
        print(f"  Pearson r={delta_ergebnis['pearson_r']:+.3f} (p={delta_ergebnis['pearson_p']:.4f}), "
              f"Spearman r={delta_ergebnis['spearman_r']:+.3f} (p={delta_ergebnis['spearman_p']:.4f}), "
              f"OLS-Koeffizient={delta_ergebnis['koeffizient']:+.4f} (p={delta_ergebnis['p']:.4f})")
        zeilen.append({"baustein": "delta_delta", **delta_ergebnis})
        _plotte_delta_delta(delta, granularitaet, delta_ergebnis)

    ergebnis = pd.DataFrame(zeilen)
    ergebnis["granularitaet"] = granularitaet
    pfad = str(PFAD_AUSGABE).format(granularitaet=granularitaet)
    ergebnis.to_csv(pfad, index=False, encoding="utf-8")
    print(f"\n[Ausgabe][{granularitaet}] {len(ergebnis)} Zeilen -> {pfad}")
    return ergebnis


def main():
    alle_ergebnisse = []
    for granularitaet, gran_cfg in GRANULARITAETEN.items():
        alle_ergebnisse.append(verarbeite_granularitaet(granularitaet, gran_cfg))

    gesamt = pd.concat(alle_ergebnisse, ignore_index=True)

    print("\n" + "=" * 70)
    print("KURZZUSAMMENFASSUNG (p < 0.05)")
    print("=" * 70)
    for _, zeile in gesamt.iterrows():
        sig = "signifikant" if zeile["p"] < 0.05 else "nicht signifikant"
        richtung = "positiv" if zeile["koeffizient"] > 0 else "negativ"
        print(f"  [{zeile['baustein']}] ({zeile['granularitaet']}): {richtung}er Zusammenhang "
              f"({zeile['koeffizient']:+.4f}, {sig}, p={zeile['p']:.4f})")


if __name__ == "__main__":
    main()

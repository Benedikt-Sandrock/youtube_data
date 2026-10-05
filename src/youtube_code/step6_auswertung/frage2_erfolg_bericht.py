# -*- coding: utf-8 -*-
"""
frage2_erfolg_bericht.py

Konsolidierte, formale Antwort auf Forschungsfrage 2 (.claude/CLAUDE.md):
"Wie hat sich der Erfolg der Kanaele entwickelt? Werden bestimmte
Medientypen erfolgreicher? Sind populistische Kanaele seit Kriegsbeginn
erfolgreicher geworden? Gibt es Unterschiede zwischen rechten und linken
Kanaelen?"

Baut auf dem Kanal x Periode-Output von prepare_success_metrics.py auf
(channel_{quartal,monat}_erfolg_timeseries.csv, Long-Format: eine Zeile
je Kanal x Periode x Dimension), gefiltert auf dieselbe Whitelist wie
Forschungsfrage 1 (frage1_kanal_whitelist.csv aus frage1_stichprobe.py,
siehe .claude/plans/success_analysis.md Punkt 3). Beide Skripte
(prepare_success_metrics.py, frage1_stichprobe.py) MUESSEN vorher einmal
gelaufen sein.

Anders als frage1_*_bericht.py ist hier KEINE eigene Video -> Kanal x
Periode-Aggregation noetig: prepare_success_metrics.py hat diese
Aggregation bereits erledigt (Mittelwert je Dimension PLUS Gesamt-Views
je Kanal x Periode). Dieses Skript pivotiert das Long-Format lediglich zu
einer Zeile je Kanal x Periode mit einer Spalte je Dimension (analog zu
aggregiere_kanal_periode() in den Frage-1-Berichten, aber ohne erneute
Mittelwertbildung).

DIMENSIONEN:
  - log_views: durchschnittlicher Log-View-Erfolg pro Video (Reichweite
    pro Video, wegen Rechtsschiefe logarithmiert). roher view_count ist
    nur Zusatzkontext in der Eingabedatei, keine eigene Testgroesse hier.
  - log_views_summe: log1p(Summe der Views aller Videos des Kanals in der
    Periode) - macht Kanaele sichtbar, die durch hoehere Aktivitaet (mehr
    Videos) insgesamt mehr Reichweite erzielen, OHNE dass der
    Durchschnitt pro Video (log_views) steigt. Ein positiver
    post-Koeffizient bei log_views_summe OHNE entsprechenden Effekt bei
    log_views deutet auf gestiegene Aktivitaet statt hoeheren
    Durchschnittserfolg hin - dieser Kontrast gehoert in die
    Ergebnis-Interpretation.
  - engagement_rate: (likes + comments) / views, NaN bei fehlenden
    Like-/Kommentarzahlen (z.B. deaktivierte Kommentare) - NICHT als 0
    interpretiert (siehe prepare_success_metrics.py).

GRUPPEN_SPALTEN wie Frage 1 (ideologie_gruppe, medientyp) PLUS
populismus_gruppe: Tertile aus
channel_classification_populism.csv::populismus_gesamt (niedrig/mittel/
hoch, pd.qcut) - beantwortet direkt "Sind populistische Kanaele seit
Kriegsbeginn erfolgreicher geworden?" ueber den Interaktionstest.

post_dummy_test()/interaktions_test() aus bericht_utils.py importiert
(bare sibling import), unveraendert gegenueber frage1_populismus_bericht.py.
Schreibt frage2_erfolg_bericht_{granularitaet}.csv, druckt eine
Kurzzusammenfassung. Direkt im Ordner ausfuehren, nicht als -m-Modul.
"""

import pandas as pd

from youtube_code.config import OUTPUTS
from deskriptiv_aggregation import lade_medientyp, lade_ideologie
from bericht_utils import post_dummy_test, interaktions_test

# =========================================================
# CONFIG
# =========================================================

PFAD_EINGABE = OUTPUTS / "segment_analysis" / "channel_{granularitaet}_erfolg_timeseries.csv"
PFAD_WHITELIST = OUTPUTS / "segment_analysis" / "frage1_kanal_whitelist.csv"
PFAD_POPULISMUS_KLASSIFIKATION = OUTPUTS / "segment_analysis" / "channel_classification_populism.csv"
PFAD_AUSGABE = OUTPUTS / "segment_analysis" / "frage2_erfolg_bericht_{granularitaet}.csv"

DIMENSIONEN = ["log_views", "log_views_summe", "engagement_rate"]

# Identisch zu den Fenstern in frage1_populismus_bericht.py, damit dieselben
# Kanal-Perioden ueber alle Berichte hinweg vergleichbar bleiben.
GRANULARITAETEN = {
    "quartal": {"spalte": "rel_quartal", "periode_min": -4, "periode_max": 14},
    "monat":   {"spalte": "rel_monat",   "periode_min": -12, "periode_max": 42},
}

GRUPPEN_SPALTEN = {
    "ideologie_gruppe": ["links", "mitte", "rechts"],
    "medientyp": ["ÖRR", "Traditionelles Medium", "Alternatives Medium", "Politiker/Partei"],
    "populismus_gruppe": ["niedrig", "mittel", "hoch"],
}

MIN_KANAELE_JE_GRUPPE = 5

POPULISMUS_TERTIL_LABELS = ["niedrig", "mittel", "hoch"]


# =========================================================
# DATEN LADEN
# =========================================================

def _lade_populismus_gruppe():
    """Tertile aus populismus_gesamt (channel_classification_populism.csv) - dieselbe
    Kanal-Klassifikation wie in prepare_channel_scores.py::prepare_populism_results()
    (Baseline-Fenster, siehe dort), NICHT die Zeitreihe. pd.qcut bildet ungefaehr
    gleich grosse Gruppen (niedrig/mittel/hoch)."""
    pop = pd.read_csv(PFAD_POPULISMUS_KLASSIFIKATION)
    pop["channel_id"] = pop["channel_id"].astype(str)
    pop["populismus_gruppe"] = pd.qcut(pop["populismus_gesamt"], 3, labels=POPULISMUS_TERTIL_LABELS)
    return pop[["channel_id", "populismus_gruppe"]]


def lade_kanal_periode_daten(granularitaet, spalte_periode):
    pfad = str(PFAD_EINGABE).format(granularitaet=granularitaet)
    df = pd.read_csv(pfad)
    df["channel_id"] = df["channel_id"].astype(str)
    n_vor = df["channel_id"].nunique()

    whitelist = pd.read_csv(PFAD_WHITELIST)
    whitelist_ids = set(whitelist["channel_id"].astype(str))
    df = df[df["channel_id"].isin(whitelist_ids)]
    print(f"[Whitelist][{granularitaet}] {n_vor} -> {df['channel_id'].nunique()} Kanaele nach Filter auf "
          f"{PFAD_WHITELIST} (dieselbe Whitelist wie Forschungsfrage 1).")

    # Long -> breit: eine Zeile je Kanal x Periode, eine Spalte je Dimension.
    breit = df.pivot_table(
        index=["channel_id", "channel_title", spalte_periode],
        columns="dimension", values="wert", aggfunc="first",
    ).reset_index()
    breit.columns.name = None

    n_videos = df.groupby(["channel_id", spalte_periode], as_index=False)["n_videos"].first()
    breit = breit.merge(n_videos, on=["channel_id", spalte_periode], how="left")

    med = lade_medientyp()
    ideo = lade_ideologie()
    populismus = _lade_populismus_gruppe()
    breit = breit.merge(med, on="channel_id", how="left") \
                 .merge(ideo, on="channel_id", how="left") \
                 .merge(populismus, on="channel_id", how="left")

    print(f"[Eingabe][{granularitaet}] {len(breit)} Kanal-Perioden-Beobachtungen, "
          f"{breit['channel_id'].nunique()} Kanaele aus {pfad}")
    return breit


def _fenster(df, spalte_periode, periode_min, periode_max):
    return df[(df[spalte_periode] >= periode_min) & (df[spalte_periode] <= periode_max)]


# =========================================================
# MAIN
# =========================================================

def verarbeite_granularitaet(granularitaet, gran_cfg):
    spalte_periode = gran_cfg["spalte"]
    df = lade_kanal_periode_daten(granularitaet, spalte_periode)
    df_g = _fenster(df, spalte_periode, gran_cfg["periode_min"], gran_cfg["periode_max"])
    print(f"[Fenster][{granularitaet}] {len(df)} -> {len(df_g)} Kanal-{granularitaet}-Beobachtungen "
          f"({df_g['channel_id'].nunique()} Kanaele).")

    zeilen = []
    for dimension in DIMENSIONEN:
        print(f"\n=== {dimension} ({granularitaet}) ===")

        # --- Gesamtstichprobe ---
        res = post_dummy_test(df_g, dimension, spalte_periode, bezeichnung="gesamt")
        if res:
            print(f"  [Gesamt] post={res['koeffizient_post']:+.4f} (p={res['p']:.4f}), "
                  f"Vorkrieg-Mittel={res['mittel_vorkrieg']:.3f}, Nachkrieg-Mittel={res['mittel_nachkrieg']:.3f}, "
                  f"n_kanaele={res['n_kanaele']}")
            zeilen.append({"dimension": dimension, "ebene": "gesamt", **res})

        # --- je Gruppierungsspalte: Interaktionstest + getrennte Gruppentests ---
        for gruppen_spalte, gruppen_werte in GRUPPEN_SPALTEN.items():
            inter = interaktions_test(df_g, dimension, spalte_periode, gruppen_spalte, gruppen_werte,
                                       min_kanaele_je_gruppe=MIN_KANAELE_JE_GRUPPE)
            if inter:
                signifikanz = "signifikant unterschiedlich" if inter["p"] < 0.05 else "kein signifikanter Unterschied"
                print(f"  [Interaktion {gruppen_spalte}] F({inter['df_num']},{inter['df_denom']})="
                      f"{inter['f_stat']:.3f}, p={inter['p']:.4f} -> {signifikanz} zwischen "
                      f"{inter['gruppen']}")
                zeilen.append({"dimension": dimension, "ebene": f"interaktion_{gruppen_spalte}",
                                "gruppe": "+".join(inter["gruppen"]), "n_beobachtungen": inter["n_beobachtungen"],
                                "n_kanaele": inter["n_kanaele"], "f_stat": inter["f_stat"],
                                "df_num": inter["df_num"], "df_denom": inter["df_denom"], "p": inter["p"]})

                for gruppe in inter["gruppen"]:
                    teil = df_g[df_g[gruppen_spalte] == gruppe]
                    res_g = post_dummy_test(teil, dimension, spalte_periode, bezeichnung=gruppe)
                    if res_g:
                        print(f"    [{gruppen_spalte}={gruppe}] post={res_g['koeffizient_post']:+.4f} "
                              f"(p={res_g['p']:.4f}), n_kanaele={res_g['n_kanaele']}")
                        zeilen.append({"dimension": dimension, "ebene": gruppen_spalte, **res_g})

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
    print("KURZZUSAMMENFASSUNG (Gesamtstichprobe, post_dummy_test, p < 0.05)")
    print("=" * 70)
    ueberblick = gesamt[gesamt["ebene"] == "gesamt"]
    for _, zeile in ueberblick.iterrows():
        richtung = "gestiegen" if zeile["koeffizient_post"] > 0 else "gesunken"
        sig = "signifikant" if zeile["p"] < 0.05 else "nicht signifikant"
        print(f"  {zeile['dimension']} ({zeile['granularitaet']}): "
              f"{richtung} um {abs(zeile['koeffizient_post']):.4f} ({sig}, p={zeile['p']:.4f})")


if __name__ == "__main__":
    main()

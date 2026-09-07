# -*- coding: utf-8 -*-
"""
frage4_kriegsvideos_erfolg_bericht.py

Konsolidierte, formale Antwort auf Forschungsfrage 4 (.claude/CLAUDE.md):
"Bei erfolgreicher werdenden Kanaelen: Betrifft das nur Kriegsvideos oder
auch andere Videos?"

Baut auf channel_video_erfolg.csv (Video-Ebene, Output von
prepare_success_metrics.py) auf, gefiltert auf dieselbe Whitelist wie
Forschungsfrage 1 (frage1_kanal_whitelist.csv). prepare_success_metrics.py
MUSS vorher einmal gelaufen sein.

Anders als Ideologie/Medientyp bei Frage 1/2 ist ist_kriegsvideo NICHT
zeitkonstant je Kanal - Kanal-Fixed-Effects absorbieren einen
Kriegsvideo-Haupteffekt hier also NICHT automatisch. interaktions_test()
aus bericht_utils.py (bewusst OHNE eigenen Gruppen-Haupteffekt, siehe
dortiger Docstring) darf deshalb NICHT unveraendert uebernommen werden -
dieses Skript verwendet stattdessen post_kriegsvideo_interaktion_test()
mit explizitem Kriegsvideo-Haupteffekt:

    y ~ C(channel_id) + post + ist_kriegsvideo + post:ist_kriegsvideo

post:ist_kriegsvideo beantwortet direkt Frage 4: ein signifikanter,
positiver Koeffizient bedeutet, der Post-Effekt ist bei Kriegsvideos
STAERKER als bei anderen Videos.

Die Regression laeuft NICHT auf Video-Ebene, sondern auf Kanal x Periode x
Kriegsvideo-Zellen (aggregiere_kanal_periode_kriegsvideo(), Mittelwert je
Zelle) - sonst wuerden Kanal-Perioden mit ueberdurchschnittlich vielen
Videos die Schaetzung staerker gewichten (dasselbe Argument wie
aggregiere_kanal_periode() in den Frage-1-Berichten). MIN_VIDEOS_PRO_ZELLE
filtert duenn besetzte Zellen (analog deskriptiv_aggregation.py::
filtere_duenne_zellen()).

Ergaenzend: post_dummy_test() (aus bericht_utils, unveraendert) getrennt
auf drei Teilstichproben {alle Videos, nur Kriegsvideos, nur sonstige
Videos} fuer einen direkten Effektgroessenvergleich - "alle Videos" nutzt
dabei die channel_{gran}_erfolg_timeseries.csv aus prepare_success_metrics.py
(dieselbe Kanal x Periode-Aggregation OHNE Kriegsvideo-Aufspaltung), die
beiden anderen die entsprechend gefilterten Zellen aus
aggregiere_kanal_periode_kriegsvideo().

GRANULARITAET = "quartal" ist die primaere Spezifikation (Kriegsvideos
sind pro Kanal-Monat oft duenn besetzt), "monat" laeuft als
Zusatzcheck mit.

Schreibt frage4_kriegsvideos_erfolg_bericht_{granularitaet}.csv, druckt
eine Kurzzusammenfassung. Direkt im Ordner ausfuehren, nicht als
-m-Modul.
"""

import pandas as pd
import statsmodels.formula.api as smf

from youtube_code.config import OUTPUTS
from bericht_utils import post_dummy_test

# =========================================================
# CONFIG
# =========================================================

RESULTS_PATH = OUTPUTS / "segment_analysis"
PFAD_EINGABE = RESULTS_PATH / "channel_video_erfolg.csv"
PFAD_WHITELIST = RESULTS_PATH / "frage1_kanal_whitelist.csv"
PFAD_AUSGABE = RESULTS_PATH / "frage4_kriegsvideos_erfolg_bericht_{granularitaet}.csv"

DIMENSIONEN = ["log_views", "engagement_rate"]

# "quartal" primaer (siehe Moduldocstring), "monat" als Zusatzcheck - beide
# werden erzeugt, wie bei den Frage-1-Berichten.
GRANULARITAETEN = {
    "quartal": {"spalte": "rel_quartal", "periode_min": -4, "periode_max": 14},
    "monat":   {"spalte": "rel_monat",   "periode_min": -12, "periode_max": 42},
}

MIN_VIDEOS_PRO_ZELLE = 3   # analog deskriptiv_aggregation.py::min_videos_pro_periode, hier je Kanal x Periode x Kriegsvideo-Zelle


# =========================================================
# DATEN LADEN
# =========================================================

def lade_video_daten():
    df = pd.read_csv(PFAD_EINGABE)
    df["channel_id"] = df["channel_id"].astype(str)
    n_vor = df["channel_id"].nunique()

    whitelist = pd.read_csv(PFAD_WHITELIST)
    whitelist_ids = set(whitelist["channel_id"].astype(str))
    df = df[df["channel_id"].isin(whitelist_ids)]
    print(f"[Whitelist] {n_vor} -> {df['channel_id'].nunique()} Kanaele nach Filter auf "
          f"{PFAD_WHITELIST} (dieselbe Whitelist wie Forschungsfrage 1).")

    n_kriegsvideos = int(df["ist_kriegsvideo"].sum())
    print(f"[Eingabe] {len(df)} Video-Beobachtungen ({n_kriegsvideos} Kriegsvideos), "
          f"{df['channel_id'].nunique()} Kanaele aus {PFAD_EINGABE}")
    return df


def _fenster(df, spalte_periode, periode_min, periode_max):
    return df[(df[spalte_periode] >= periode_min) & (df[spalte_periode] <= periode_max)]


def aggregiere_kanal_periode_kriegsvideo(df, spalte_periode):
    """Video-Ebene -> Kanal x Periode x Kriegsvideo-Flag: Mittelwert je Dimension
    ueber alle Videos einer Zelle. Getrennt von ist_kriegsvideo, weil das (anders
    als Ideologie/Medientyp) NICHT zeitkonstant je Kanal ist - siehe Moduldocstring."""
    agg = df.groupby(["channel_id", spalte_periode, "ist_kriegsvideo"], as_index=False).agg(
        **{d: (d, "mean") for d in DIMENSIONEN},
        n_videos=("video_id", "count"),
    )
    return agg


def _filtere_duenne_zellen(df):
    zu_duenn = df["n_videos"] < MIN_VIDEOS_PRO_ZELLE
    print(f"  [Zellfilter] {int(zu_duenn.sum())} von {len(df)} Kanal-Perioden-Kriegsvideo-Zellen "
          f"unter MIN_VIDEOS_PRO_ZELLE={MIN_VIDEOS_PRO_ZELLE} -> verworfen.")
    return df[~zu_duenn]


# =========================================================
# BAUSTEIN: Post x Kriegsvideo-Interaktion (MIT Haupteffekt)
# =========================================================

def post_kriegsvideo_interaktion_test(df, dimension, spalte_periode):
    """Kanal-FE + post + ist_kriegsvideo + post:ist_kriegsvideo, SE geclustert
    auf Kanalebene. Bewusst MIT eigenem ist_kriegsvideo-Haupteffekt (anders als
    interaktions_test() in bericht_utils.py) - siehe Moduldocstring."""
    daten = df.dropna(subset=[dimension]).copy()
    daten["channel_id"] = daten["channel_id"].astype(str)
    daten["y"] = daten[dimension]
    daten["post"] = (daten[spalte_periode] >= 0).astype(int)

    n_kanaele = daten["channel_id"].nunique()
    if (daten["post"].nunique() < 2 or daten["ist_kriegsvideo"].nunique() < 2 or n_kanaele < 2):
        print(f"  [Skip] zu wenig Variation (Kanaele={n_kanaele}) fuer post_kriegsvideo_interaktion_test.")
        return None

    modell = smf.ols(
        "y ~ C(channel_id) + post + ist_kriegsvideo + post:ist_kriegsvideo", data=daten
    ).fit(cov_type="cluster", cov_kwds={"groups": daten["channel_id"]})

    if "post:ist_kriegsvideo" not in modell.params.index:
        print("  [Skip] Interaktionsterm nicht im Modell (zu wenig Variation innerhalb Kanaelen).")
        return None

    return {
        "n_beobachtungen": len(daten),
        "n_kanaele": n_kanaele,
        "koeffizient_post": modell.params["post"],
        "p_post": modell.pvalues["post"],
        "koeffizient_kriegsvideo": modell.params["ist_kriegsvideo"],
        "p_kriegsvideo": modell.pvalues["ist_kriegsvideo"],
        "koeffizient_interaktion": modell.params["post:ist_kriegsvideo"],
        "se_interaktion": modell.bse["post:ist_kriegsvideo"],
        "p_interaktion": modell.pvalues["post:ist_kriegsvideo"],
    }


# =========================================================
# MAIN
# =========================================================

def verarbeite_granularitaet(df, granularitaet, gran_cfg):
    spalte_periode = gran_cfg["spalte"]
    df_fenster = _fenster(df, spalte_periode, gran_cfg["periode_min"], gran_cfg["periode_max"])

    df_zellen = aggregiere_kanal_periode_kriegsvideo(df_fenster, spalte_periode)
    df_zellen = _filtere_duenne_zellen(df_zellen)
    print(f"[Aggregation][{granularitaet}] {len(df_fenster)} Video-Beobachtungen -> "
          f"{len(df_zellen)} Kanal-{granularitaet}-Kriegsvideo-Zellen "
          f"({df_zellen['channel_id'].nunique()} Kanaele).")

    # "Alle Videos" nutzt die ungetrennte Kanal x Periode-Aggregation aus
    # prepare_success_metrics.py (channel_{gran}_erfolg_timeseries.csv) statt
    # df_zellen wieder ueber ist_kriegsvideo zu summieren.
    alle_pfad = RESULTS_PATH / f"channel_{granularitaet}_erfolg_timeseries.csv"
    alle_lang = pd.read_csv(alle_pfad)
    alle_lang["channel_id"] = alle_lang["channel_id"].astype(str)
    whitelist_ids = set(pd.read_csv(PFAD_WHITELIST)["channel_id"].astype(str))
    alle_lang = alle_lang[alle_lang["channel_id"].isin(whitelist_ids)]
    alle_breit = alle_lang.pivot_table(
        index=["channel_id", spalte_periode], columns="dimension", values="wert", aggfunc="first"
    ).reset_index()
    alle_breit.columns.name = None

    zeilen = []
    for dimension in DIMENSIONEN:
        print(f"\n=== {dimension} ({granularitaet}) ===")

        inter = post_kriegsvideo_interaktion_test(df_zellen, dimension, spalte_periode)
        if inter:
            signifikanz = "signifikant" if inter["p_interaktion"] < 0.05 else "nicht signifikant"
            print(f"  [Interaktion post:ist_kriegsvideo] {inter['koeffizient_interaktion']:+.4f} "
                  f"(p={inter['p_interaktion']:.4f}) -> {signifikanz}, "
                  f"n_kanaele={inter['n_kanaele']}, n_beobachtungen={inter['n_beobachtungen']}")
            zeilen.append({"dimension": dimension, "ebene": "interaktion_post_kriegsvideo", **inter})

        # --- Effektgroessenvergleich: post_dummy_test() getrennt je Teilstichprobe ---
        teilstichproben = {
            "alle_videos": alle_breit,
            "nur_kriegsvideos": df_zellen[df_zellen["ist_kriegsvideo"] == 1],
            "nur_sonstige_videos": df_zellen[df_zellen["ist_kriegsvideo"] == 0],
        }
        for bezeichnung, teil in teilstichproben.items():
            if dimension not in teil.columns:
                continue
            res = post_dummy_test(teil, dimension, spalte_periode, bezeichnung=bezeichnung)
            if res:
                print(f"    [{bezeichnung}] post={res['koeffizient_post']:+.4f} (p={res['p']:.4f}), "
                      f"n_kanaele={res['n_kanaele']}")
                zeilen.append({"dimension": dimension, "ebene": bezeichnung, **res})

    ergebnis = pd.DataFrame(zeilen)
    ergebnis["granularitaet"] = granularitaet
    pfad = str(PFAD_AUSGABE).format(granularitaet=granularitaet)
    ergebnis.to_csv(pfad, index=False, encoding="utf-8")
    print(f"\n[Ausgabe][{granularitaet}] {len(ergebnis)} Zeilen -> {pfad}")
    return ergebnis


def main():
    df = lade_video_daten()

    alle_ergebnisse = []
    for granularitaet, gran_cfg in GRANULARITAETEN.items():
        alle_ergebnisse.append(verarbeite_granularitaet(df, granularitaet, gran_cfg))

    gesamt = pd.concat(alle_ergebnisse, ignore_index=True)

    print("\n" + "=" * 70)
    print("KURZZUSAMMENFASSUNG (post:ist_kriegsvideo-Interaktion, p < 0.05)")
    print("=" * 70)
    ueberblick = gesamt[gesamt["ebene"] == "interaktion_post_kriegsvideo"]
    for _, zeile in ueberblick.iterrows():
        richtung = "staerker" if zeile["koeffizient_interaktion"] > 0 else "schwaecher"
        sig = "signifikant" if zeile["p_interaktion"] < 0.05 else "nicht signifikant"
        print(f"  {zeile['dimension']} ({zeile['granularitaet']}): Post-Effekt bei Kriegsvideos "
              f"{richtung} um {abs(zeile['koeffizient_interaktion']):.4f} ({sig}, p={zeile['p_interaktion']:.4f})")


if __name__ == "__main__":
    main()

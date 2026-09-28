# -*- coding: utf-8 -*-
"""
diagnose_oerr_populismuspraemie.py

Ad-hoc-Diagnose (.claude/CLAUDE.md) zur Nutzerfrage "warum zeigt OeRR so einen
starken Effekt?" im Interaktionsmodell aus
step6_auswertung/populismuspraemie_kriegsvideos_bericht.py
(log_views ~ C(channel_id) + populismus_gesamt:C(medientyp), nur Kriegsvideos).

Prueft drei moegliche Erklaerungen fuer den ungewoehnlich starken, mit Alternativen
Medien vergleichbaren OeRR-Koeffizienten:

1. Stichprobengroesse: wie viele OeRR-Kanaele/-Kriegsvideos gehen ein, wie ist die
   Videozahl auf die Kanaele verteilt (dominieren wenige grosse Nachrichtenkanaele)?
2. Zusammensetzung der Gruppe: TYP5_ZU_1 in deskriptiv_aggregation.py zaehlt Kanaele
   mit typ_code 5 (laut media_type_russia_merged.xlsx: "Der Dunkle Parabelritter",
   "WALULIS" - beide satirische funk-Formate von ARD/ZDF) zu OeRR. Diese aehneln
   stilistisch eher alternativen/populistischen Kommentar-Formaten als klassischen
   Nachrichtensendungen - moeglicherweise treiben sie den Effekt ueberproportional.
3. Kanaltreiber: Jackknife (Leave-one-channel-out) auf der OeRR-Teilstichprobe -
   haengt der starke Koeffizient von einzelnen Kanaelen ab, oder ist er breit
   getragen? Ergaenzend die within-Kanal-Korrelation (Populismus vs. Views) je
   OeRR-Kanal mit >= 10 klassifizierten Kriegsvideos.

Wiederholt die Datenaufbereitung aus populismuspraemie_kriegsvideos_bericht.py
direkt hier (kein Import - reines Diagnose-Skript, siehe dortiger Docstring fuer die
kanonische Definition).

Ausfuehrung (aus dem Projekt-Root):
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/adhoc/diagnose_oerr_populismuspraemie.py

Schreibt scripts/adhoc/output/diagnose_oerr_populismuspraemie_kanaluebersicht.csv.
"""

import sys
from pathlib import Path

import pandas as pd
import statsmodels.formula.api as smf

PROJEKT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJEKT_ROOT / "src"))
from youtube_code.step6_auswertung.deskriptiv_aggregation import lade_medientyp
RESULTS_PATH = PROJEKT_ROOT / "outputs" / "segment_analysis"
PFAD_POPULISMUS = RESULTS_PATH / "channel_video_populism.csv"
PFAD_ERFOLG = RESULTS_PATH / "channel_video_erfolg.csv"
PFAD_MEDIENTYP = PROJEKT_ROOT / "data" / "external" / "media_type_russia_merged.xlsx"

AUSGABE = PROJEKT_ROOT / "scripts" / "adhoc" / "output" / "diagnose_oerr_populismuspraemie_kanaluebersicht.csv"

DIMENSION = "populismus_gesamt"
MIN_VIDEOS_FUER_KANALKORRELATION = 10


# =========================================================
# DATEN LADEN (Kopie der Aufbereitung aus populismuspraemie_kriegsvideos_bericht.py)
# =========================================================

def lade_oerr_kriegsvideos():
    pop = pd.read_csv(PFAD_POPULISMUS)
    pop["channel_id"] = pop["channel_id"].astype(str)
    pop = pop[["channel_id", "video_id", DIMENSION]]

    erfolg = pd.read_csv(PFAD_ERFOLG)
    erfolg["channel_id"] = erfolg["channel_id"].astype(str)

    merged = pop.merge(
        erfolg[["channel_id", "channel_title", "video_id", "log_views", "view_count", "ist_kriegsvideo"]],
        on=["channel_id", "video_id"], how="inner",
    )
    kv = merged[merged["ist_kriegsvideo"] == 1].copy()

    # lade_medientyp() dedupliziert seit 2026-09-08 automatisch echte Duplikatzeilen
    # desselben channel_id in PFAD_MEDIENTYP (siehe dortiger Docstring - beim
    # Nachgehen dieser OeRR-Frage entdeckt: ARTEde/WDR aktuell waren je zweimal
    # enthalten und wurden dadurch bei einem rohen Merge auf channel_id verdoppelt).
    med = lade_medientyp()
    typ5_roh = pd.read_excel(PFAD_MEDIENTYP)
    typ5_roh["channel_id"] = typ5_roh["channel_id"].astype(str)
    typ5_kanaele = set(typ5_roh.loc[pd.to_numeric(typ5_roh["type"], errors="coerce") == 5, "channel_id"])

    kv = kv.merge(med[["channel_id", "medientyp"]], on="channel_id", how="left")
    kv["typ5_kanal"] = kv["channel_id"].isin(typ5_kanaele)

    oerr = kv[kv["medientyp"] == "ÖRR"].dropna(subset=[DIMENSION, "log_views"]).copy()
    print(f"[Laden] {len(oerr)} OeRR-Kriegsvideos, {oerr['channel_id'].nunique()} Kanaele "
          f"(davon {int(oerr['typ5_kanal'].sum())} Videos von urspruenglich typ_code=5-Kanaelen).")
    return oerr


# =========================================================
# 1 + 2: Stichprobenzusammensetzung
# =========================================================

def kanaluebersicht(oerr):
    uebersicht = oerr.groupby(["channel_id", "channel_title", "typ5_kanal"]).agg(
        n_videos=("video_id", "size"),
        populismus_mean=(DIMENSION, "mean"),
        populismus_std=(DIMENSION, "std"),
        log_views_mean=("log_views", "mean"),
    ).reset_index().sort_values("n_videos", ascending=False)

    print("\n=== Kanaluebersicht (sortiert nach n_videos) ===")
    print(uebersicht.to_string(index=False))

    print(f"\n[Konzentration] Top-5-Kanaele (nach n_videos) stellen "
          f"{uebersicht['n_videos'].head(5).sum()} von {uebersicht['n_videos'].sum()} "
          f"Videos ({100 * uebersicht['n_videos'].head(5).sum() / uebersicht['n_videos'].sum():.1f}%).")

    uebersicht.to_csv(AUSGABE, index=False, encoding="utf-8")
    print(f"[Ausgabe] -> {AUSGABE}")
    return uebersicht


def modell_ohne_typ5(oerr):
    """Wiederholt das OeRR-Modell einmal mit, einmal ohne die typ_code=5-Kanaele
    (Der Dunkle Parabelritter, WALULIS) - zeigt, ob diese beiden Satire-Kanaele den
    Effekt ueberproportional treiben."""
    print("\n=== Mit vs. ohne typ_code=5-Kanaele (Der Dunkle Parabelritter, WALULIS) ===")
    for bezeichnung, teil in [("mit typ5", oerr), ("ohne typ5", oerr[~oerr["typ5_kanal"]])]:
        if teil["channel_id"].nunique() < 2:
            continue
        modell = smf.ols(f"log_views ~ {DIMENSION} + C(channel_id)", data=teil).fit(
            cov_type="cluster", cov_kwds={"groups": teil["channel_id"]}
        )
        print(f"  [{bezeichnung}] koeffizient={modell.params[DIMENSION]:+.4f} "
              f"(se={modell.bse[DIMENSION]:.4f}, p={modell.pvalues[DIMENSION]:.4f}), "
              f"n={len(teil)} Videos, {teil['channel_id'].nunique()} Kanaele.")


# =========================================================
# 3: Jackknife (Leave-one-channel-out) + Kanal-Korrelationen
# =========================================================

def jackknife(oerr):
    print("\n=== Jackknife: OeRR-Koeffizient bei Ausschluss je eines Kanals ===")
    kanaele = sorted(oerr["channel_id"].unique())

    voll = smf.ols(f"log_views ~ {DIMENSION} + C(channel_id)", data=oerr).fit(
        cov_type="cluster", cov_kwds={"groups": oerr["channel_id"]}
    )
    koef_voll, p_voll = voll.params[DIMENSION], voll.pvalues[DIMENSION]
    print(f"  Volle OeRR-Stichprobe: koeffizient={koef_voll:+.4f}, p={p_voll:.4f}")

    titel = oerr.drop_duplicates("channel_id").set_index("channel_id")["channel_title"]
    ergebnisse = []
    for k in kanaele:
        teil = oerr[oerr["channel_id"] != k]
        if teil["channel_id"].nunique() < 2:
            continue
        modell = smf.ols(f"log_views ~ {DIMENSION} + C(channel_id)", data=teil).fit(
            cov_type="cluster", cov_kwds={"groups": teil["channel_id"]}
        )
        ergebnisse.append({
            "ausgeschlossener_kanal": titel.get(k, k),
            "koeffizient": modell.params[DIMENSION],
            "p": modell.pvalues[DIMENSION],
        })

    res = pd.DataFrame(ergebnisse).sort_values("koeffizient")
    print(res.to_string(index=False))
    print(f"\n  Spannweite der Jackknife-Koeffizienten: {res['koeffizient'].min():.4f} bis "
          f"{res['koeffizient'].max():.4f} (voll: {koef_voll:.4f})")
    kippt = res[res["p"] >= 0.05]
    if not kippt.empty:
        print(f"  -> {len(kippt)} Ausschluesse lassen den Koeffizienten insignifikant werden "
              f"(p >= 0.05): {kippt['ausgeschlossener_kanal'].tolist()}")
    else:
        print("  -> KEIN einzelner Kanalausschluss kippt die Signifikanz - der Effekt haengt "
              "nicht von einem einzelnen Kanal ab.")


def kanalkorrelationen(oerr):
    print(f"\n=== Within-Kanal-Korrelation (Populismus vs. log_views), Kanaele mit >= "
          f"{MIN_VIDEOS_FUER_KANALKORRELATION} klassifizierten Kriegsvideos ===")
    zeilen = []
    for (cid, title), gruppe in oerr.groupby(["channel_id", "channel_title"]):
        if len(gruppe) < MIN_VIDEOS_FUER_KANALKORRELATION:
            continue
        if gruppe[DIMENSION].nunique() < 2:
            continue
        korr = gruppe[DIMENSION].corr(gruppe["log_views"])
        zeilen.append({"channel_title": title, "n_videos": len(gruppe), "pearson_r": korr})

    res = pd.DataFrame(zeilen).sort_values("pearson_r", ascending=False)
    print(res.to_string(index=False))
    print(f"\n  {int((res['pearson_r'] > 0).sum())} von {len(res)} Kanaelen mit positiver "
          f"Korrelation.")


# =========================================================
# MAIN
# =========================================================

def main():
    oerr = lade_oerr_kriegsvideos()
    kanaluebersicht(oerr)
    modell_ohne_typ5(oerr)
    jackknife(oerr)
    kanalkorrelationen(oerr)


if __name__ == "__main__":
    main()

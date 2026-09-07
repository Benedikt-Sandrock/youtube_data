# -*- coding: utf-8 -*-
"""
bericht_utils.py

Gemeinsame Regressions-Bausteine fuer alle Kanal-FE + Post-Dummy-Berichte
in diesem Ordner (frage1_populismus_bericht.py, frage1_stance_bericht.py,
frage2_erfolg_bericht.py, frage3_populismus_erfolg_bericht.py). Reiner
Funktions-Umzug aus frage1_populismus_bericht.py (siehe .claude/plans/
success_analysis.md, Abschnitt "Architekturentscheidung") - post_dummy_test()
und interaktions_test() waren dort und in frage1_stance_bericht.py
wortidentisch dupliziert; ab jetzt importieren alle Berichte von hier
(bare sibling import: `from bericht_utils import post_dummy_test,
interaktions_test`, direkt im Ordner ausgefuehrt).

Beide Funktionen erwarten ein DataFrame auf Kanal x Periode-Ebene (eine
Zeile je Kanal-Monat bzw. Kanal-Quartal, NICHT je einzelnes Video/Segment)
- die jeweils aufrufenden Berichte sind fuer diese Aggregation zustaendig
(aggregiere_kanal_periode() in den Frage-1-Berichten, bereits fertig
aggregierte Eingabedateien bei Frage 2/3).
"""

import pandas as pd
import statsmodels.formula.api as smf

# =========================================================
# BAUSTEIN 1: Post-Dummy-Test (Gesamt oder je Gruppe)
# =========================================================

def post_dummy_test(df, dimension, spalte_periode, bezeichnung="gesamt"):
    """Kanal-FE + EIN Post-Dummy (post = periode >= 0), SE geclustert auf
    Kanalebene. Gibt ein dict mit Koeffizient/SE/p/n zurueck, oder None wenn
    nicht schaetzbar (z.B. nur eine Seite der Periode vorhanden)."""

    daten = df.dropna(subset=[dimension]).copy()
    daten["channel_id"] = daten["channel_id"].astype(str)
    daten["y"] = daten[dimension]
    daten["post"] = (daten[spalte_periode] >= 0).astype(int)

    n_kanaele = daten["channel_id"].nunique()
    if daten["post"].nunique() < 2 or n_kanaele < 2:
        print(f"  [Skip][{bezeichnung}] zu wenig Variation (Kanaele={n_kanaele}) fuer post_dummy_test.")
        return None

    modell_reduziert = smf.ols("y ~ C(channel_id)", data=daten).fit()
    modell = smf.ols("y ~ C(channel_id) + post", data=daten).fit(
        cov_type="cluster", cov_kwds={"groups": daten["channel_id"]}
    )

    partielles_r2 = (modell_reduziert.ssr - modell.ssr) / modell_reduziert.ssr

    return {
        "gruppe": bezeichnung,
        "n_beobachtungen": len(daten),
        "n_kanaele": n_kanaele,
        "mittel_vorkrieg": daten.loc[daten["post"] == 0, "y"].mean(),
        "mittel_nachkrieg": daten.loc[daten["post"] == 1, "y"].mean(),
        "koeffizient_post": modell.params["post"],
        "se": modell.bse["post"],
        "p": modell.pvalues["post"],
        "partielles_r2": partielles_r2,
    }


# =========================================================
# BAUSTEIN 2: Interaktionstest (Post x Gruppe)
# =========================================================

def interaktions_test(df, dimension, spalte_periode, gruppen_spalte, gruppen_werte, min_kanaele_je_gruppe=5):
    """Ein Modell ueber ALLE Kanaele der uebergebenen Gruppen: Kanal-FE + post +
    post:Gruppe-Interaktion (bewusst OHNE eigenen Gruppen-Haupteffekt, da
    Gruppenzugehoerigkeit zeitkonstant ist und daher vollstaendig mit den
    Kanal-FE kollinear waere). Gemeinsamer F-Test: sind alle
    post:Gruppe-Interaktionsterme gemeinsam 0 -> unterscheidet sich der
    Post-Effekt zwischen den Gruppen? min_kanaele_je_gruppe: unterhalb dieser
    Kanalzahl wird eine Gruppe aus dem Test ausgeschlossen (Aufrufer steuert
    das ueber ihre eigene MIN_KANAELE_JE_GRUPPE-Konstante)."""

    daten = df.dropna(subset=[dimension, gruppen_spalte]).copy()
    daten = daten[daten[gruppen_spalte].isin(gruppen_werte)]
    daten["channel_id"] = daten["channel_id"].astype(str)
    daten["y"] = daten[dimension]
    daten["post"] = (daten[spalte_periode] >= 0).astype(int)

    vorhandene_gruppen = [g for g in gruppen_werte if (daten[gruppen_spalte] == g).any()
                          and daten.loc[daten[gruppen_spalte] == g, "channel_id"].nunique() >= min_kanaele_je_gruppe]
    if len(vorhandene_gruppen) < 2:
        print(f"  [Skip][Interaktion {gruppen_spalte}] zu wenig Gruppen mit >= "
              f"{min_kanaele_je_gruppe} Kanaelen ({vorhandene_gruppen}).")
        return None
    daten = daten[daten[gruppen_spalte].isin(vorhandene_gruppen)]

    if daten["post"].nunique() < 2 or daten["channel_id"].nunique() < 2:
        print(f"  [Skip][Interaktion {gruppen_spalte}] zu wenig Variation.")
        return None

    referenz = vorhandene_gruppen[0]
    daten[gruppen_spalte] = pd.Categorical(daten[gruppen_spalte], categories=vorhandene_gruppen)

    formel = f"y ~ C(channel_id) + post + post:C({gruppen_spalte}, Treatment(reference='{referenz}'))"
    modell = smf.ols(formel, data=daten).fit(
        cov_type="cluster", cov_kwds={"groups": daten["channel_id"]}
    )

    interaktions_terme = [p for p in modell.params.index if p.startswith("post:C(")]
    if not interaktions_terme:
        print(f"  [Skip][Interaktion {gruppen_spalte}] keine Interaktionsterme im Modell.")
        return None

    hypothese = ", ".join(f"{p} = 0" for p in interaktions_terme)
    f_test = modell.f_test(hypothese)

    return {
        "referenzgruppe": referenz,
        "gruppen": vorhandene_gruppen,
        "n_beobachtungen": len(daten),
        "n_kanaele": daten["channel_id"].nunique(),
        "f_stat": float(f_test.fvalue),
        "df_num": int(f_test.df_num),
        "df_denom": int(f_test.df_denom),
        "p": float(f_test.pvalue),
    }

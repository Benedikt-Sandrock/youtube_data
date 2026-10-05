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
.claude/plans/success_analysis.md Punkt 3). Seit 2026-09-09 zusaetzlich
channel_video_populism.csv (Video-Ebene der Populismus-Klassifikation,
ebenfalls aus prepare_channel_scores.py - definiert die Videopopulation
fuer die Videolaengen-Kontrolle, siehe lade_kanal_periode_kontrollen())
und channel_video_erfolg.csv (liefert dazu die Dauer je video_id) sowie
das Medientyp-Excel/die Ideologie-CSV ueber lade_medientyp()/
lade_ideologie() aus deskriptiv_aggregation.py (gruppe5-Zuordnung fuer
Baustein (c), siehe lade_gruppe5()). Alle noetigen Vorlaeuferskripte
MUESSEN vorher einmal gelaufen sein.

Drei Bausteine je Granularitaet:

(a) Panel mit Kanal-FE + Perioden-FE (primaer):
    log_views ~ populismus_gesamt + log_duration_mean + C(channel_id) + C(periode)
    Standardfehler auf Kanalebene geclustert. Kontrolliert Kanal-
    Fixeffekte UND gemeinsame Zeittrends (sonst Scheinkorrelation durch
    allgemeines Wachstum ueber die Zeit). Der Koeffizient ist die reine
    Innerhalb-Kanal-Korrelation zwischen Populismus-Niveau und Erfolg in
    derselben Periode - KEINE Kausalaussage (siehe Limitationen unten).
    Seit 2026-09-09 (Nutzervorgabe "Fuege die Videodauer als Kontrolle
    ein") mit log_duration_mean als Kontrollvariable (Zellmittel von
    log_duration_seconds NUR ueber die klassifizierten Videos, aus denen
    auch populismus_gesamt der Zelle gemittelt wird - NICHT ueber alle
    Videos des Kanals in der Periode, siehe Korrektur-Docstring in
    lade_kanal_periode_kontrollen()).

(b) Delta-Delta-Korrelation je Kanal (Robustheit/Visualisierung): je
    Kanal mean(post) - mean(pre) fuer populismus_gesamt und fuer
    log_views, Pearson- und Spearman-Korrelation ueber alle Kanaele plus
    eine einfache OLS-Gerade, als Scatterplot. Antwortet auf dieselbe
    Frage aus einer anderen, robusteren Perspektive (Kanal-Niveau-
    Veraenderung statt Perioden-Panel). Pearson/Spearman bleiben bewusst
    UNKONTROLLIERTE bivariate Korrelationsmasse (kein Kovariaten-Konzept,
    unveraendert seit der urspruenglichen Fassung). Seit 2026-09-09
    (Nutzervorgabe: "Pruef, ob Baustein (b) dieselbe Videopopulation
    nutzen sollte") zusaetzlich EIN robustheitspruefendes OLS-Modell
    delta_log_views ~ delta_populismus + delta_log_duration_mean,
    delta_log_duration_mean = mean(post) - mean(pre) von log_duration_mean
    - DERSELBEN, bereits auf die klassifizierten Videos beschraenkten
    Kontrollvariable wie in (a)/(c) (siehe lade_kanal_periode_kontrollen()),
    NICHT einer eigenen, anders abgegrenzten Videopopulation.

(c) Heterogenitaet nach gruppe5 (Nutzervorgabe 2026-09-09: "Gilt das fuer
    bestimmte Typen besonders stark?"): Erweiterung von (a) um eine
    gruppe5-Interaktion,
    log_views ~ C(channel_id) + C(periode) + log_duration_mean
        + populismus_gesamt:C(gruppe5)
    bewusst OHNE eigenen populismus_gesamt-Haupteffekt (dadurch ist
    C(gruppe5) innerhalb der Interaktion automatisch vollrangig kodiert,
    jeder Interaktionsterm direkt der gruppenspezifische Populismus-
    Erfolgs-Zusammenhang - identisches Designprinzip wie
    kriegspraemie_je_gruppe_test() in frage4_kriegspraemie_medientyp_
    bericht.py) plus anschliessendem F-Test, ob sich die fuenf
    gruppenspezifischen Koeffizienten gemeinsam unterscheiden. gruppe5
    (OeRR/Traditionelles Medium/Alternative Medien links-mitte-rechts,
    siehe deskriptiv_plots.py::baue_gruppe5()) kommt ueber lade_gruppe5()
    aus denselben Quelldateien (Medientyp-Excel, Ideologie-CSV) wie in
    frage4_kriegspraemie_medientyp_bericht.py.

Methodische Limitation: Frage 3 ist rein korrelativ, es gibt keine
exogene Variation fuer Δpopulismus selbst (anders als der Kriegsbeginn
fuer Frage 1/2) - moegliche Rueckwaertskausalitaet (erfolgreiche Kanaele
werden populistischer, nicht umgekehrt) oder gemeinsame Drittvariablen
koennen mit diesem Design nicht ausgeschlossen werden. Das gilt auch fuer
Baustein (c): eine gruppenspezifisch staerkere Korrelation ist keine
Aussage darueber, dass Populismus dort Erfolg KAUSAL staerker treibt.

Schreibt frage3_populismus_erfolg_bericht_{granularitaet}.csv (alle drei
Bausteine in einer Tabelle, Spalte "baustein" unterscheidet sie) sowie
einen Scatterplot je Granularitaet nach outputs/segment_analysis/plots/.
Direkt im Ordner ausfuehren, nicht als -m-Modul.
"""

import matplotlib.pyplot as plt
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import pearsonr, spearmanr

from deskriptiv_aggregation import lade_ideologie, lade_medientyp
from deskriptiv_plots import GRUPPE5_REIHENFOLGE

from youtube_code.config import OUTPUTS

# =========================================================
# CONFIG
# =========================================================

RESULTS_PATH = OUTPUTS / "segment_analysis"
PFAD_WHITELIST = RESULTS_PATH / "frage1_kanal_whitelist.csv"
PFAD_VIDEO_ERFOLG = RESULTS_PATH / "channel_video_erfolg.csv"
PFAD_VIDEO_POPULISMUS = RESULTS_PATH / "channel_video_populism.csv"
PFAD_AUSGABE = RESULTS_PATH / "frage3_populismus_erfolg_bericht_{granularitaet}.csv"
PFAD_PLOT = RESULTS_PATH / "plots" / "frage3_delta_delta_{granularitaet}.png"

MIN_KANAELE_JE_GRUPPE = 5  # wie frage1/frage4 - Mindestanzahl Kanaele je gruppe5 fuer Baustein (c)

GRANULARITAETEN = {
    "quartal": {"spalte": "rel_quartal", "periode_min": -4, "periode_max": 14},
    "monat":   {"spalte": "rel_monat",   "periode_min": -12, "periode_max": 42},
}


# =========================================================
# DATEN LADEN
# =========================================================

def lade_kanal_periode_kontrollen(spalte_periode):
    """Kanal x Periode-Kontrollvariable log_duration_mean - Zellmittel von
    log_duration_seconds NUR ueber die Videos, die auch tatsaechlich in den
    populismus_gesamt-Zellwert der Periode eingeflossen sind (Korrektur
    2026-09-09, Nutzervorgabe: "Das Zellmittel soll nur ueber die Videos gebildet
    werden, die in der Analyse enthalten sind" - ein Mittel ueber ALLE Videos des
    Kanals, wie zuvor, passt nicht zur X-Variable, wenn diese selbst nur aus einer
    Teilmenge der Videos gebildet wird). Population kommt aus
    channel_video_populism.csv (eine Zeile je LLM-klassifiziertem Video, GENAU die
    Menge, aus der prepare_channel_scores.py::prepare_populism_results()
    populismus_gesamt je Kanal-Periode mittelt) - das umfasst NICHT nur
    Kriegsvideos, sondern auch die klassifizierten Vorkriegs-Baseline-Videos
    (BASELINE_INTERVAL_INDIZES dort), da populismus_gesamt in der Zeitreihe ueber
    ALLE klassifizierten Videos der Periode gemittelt wird, nicht nur Kriegsvideos.
    Dauer wird erst NACH dieser Einschraenkung ueber channel_video_erfolg.csv
    dazugemergt (video_id-Merge). Gibt [channel_id, spalte_periode,
    log_duration_mean] zurueck, zum Mergen auf (channel_id, periode)."""
    klassifizierte_videos = pd.read_csv(
        PFAD_VIDEO_POPULISMUS, usecols=["channel_id", "video_id", spalte_periode]
    )
    klassifizierte_videos["channel_id"] = klassifizierte_videos["channel_id"].astype(str)

    dauer = pd.read_csv(PFAD_VIDEO_ERFOLG, usecols=["channel_id", "video_id", "log_duration_seconds"])
    dauer["channel_id"] = dauer["channel_id"].astype(str)

    video_dauer = klassifizierte_videos.merge(dauer, on=["channel_id", "video_id"], how="left")
    n_ohne_dauer = int(video_dauer["log_duration_seconds"].isna().sum())
    if n_ohne_dauer:
        print(f"  [Kontrolle] {n_ohne_dauer} von {len(video_dauer)} klassifizierten Videos ohne "
              f"bekannte Dauer in {PFAD_VIDEO_ERFOLG}.")

    kontrollen = (video_dauer.groupby(["channel_id", spalte_periode])["log_duration_seconds"]
                  .mean().reset_index().rename(columns={"log_duration_seconds": "log_duration_mean"}))
    return kontrollen


def lade_gruppe5():
    """Kanal -> gruppe5-Zuordnung (OeRR/Traditionelles Medium/Alternative Medien
    links-mitte-rechts, siehe deskriptiv_plots.py::baue_gruppe5()) fuer die
    Heterogenitaetsanalyse in Baustein (c) - lokale Nachbildung wie in
    frage4_kriegspraemie_medientyp_bericht.py::baue_gruppe5_lokal(), hier direkt
    auf Kanalebene (gruppe5 ist kanalkonstant, kein Video-Merge noetig). Kanaele
    ohne Medientyp-/Ideologie-Eintrag oder mit Politiker/Partei bzw. Alternativem
    Medium ohne Ideologie-Einordnung fallen raus (isin(GRUPPE5_REIHENFOLGE))."""
    kanal_meta = lade_medientyp().merge(lade_ideologie(), on="channel_id", how="left")
    kanal_meta["channel_id"] = kanal_meta["channel_id"].astype(str)
    ist_alt = kanal_meta["medientyp"] == "Alternatives Medium"
    kanal_meta["gruppe5"] = kanal_meta["medientyp"]
    kanal_meta.loc[ist_alt, "gruppe5"] = (
        "Alternative Medien (" + kanal_meta.loc[ist_alt, "ideologie_gruppe"].astype(str) + ")"
    )
    vor = kanal_meta["channel_id"].nunique()
    kanal_meta = kanal_meta[kanal_meta["gruppe5"].isin(GRUPPE5_REIHENFOLGE)]
    print(f"  [Gruppe5] {vor - kanal_meta['channel_id'].nunique()} Kanaele ausgeschlossen "
          f"(Politiker/Partei oder Alternatives Medium ohne Ideologie-Einordnung).")
    return kanal_meta[["channel_id", "gruppe5"]]


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

    kontrollen = lade_kanal_periode_kontrollen(spalte_periode)
    n_vor_kontrolle = len(merged)
    merged = merged.merge(kontrollen, on=["channel_id", spalte_periode], how="left")
    print(f"[Kontrolle][{granularitaet}] log_duration_mean fuer {merged['log_duration_mean'].notna().sum()} "
          f"von {n_vor_kontrolle} Kanal-Perioden-Zeilen gefunden.")

    gruppe5 = lade_gruppe5()
    merged = merged.merge(gruppe5, on="channel_id", how="left")
    print(f"[Gruppe5][{granularitaet}] {merged.loc[merged['gruppe5'].notna(), 'channel_id'].nunique()} "
          f"von {merged['channel_id'].nunique()} Kanaelen mit gueltiger gruppe5-Zuordnung.")
    return merged


def _fenster(df, spalte_periode, periode_min, periode_max):
    return df[(df[spalte_periode] >= periode_min) & (df[spalte_periode] <= periode_max)]


# =========================================================
# BAUSTEIN (a): Panel mit Kanal-FE + Perioden-FE
# =========================================================

def panel_fe_test(df, spalte_periode):
    daten = df.dropna(subset=["populismus_gesamt", "log_views", "log_duration_mean"]).copy()
    daten["channel_id"] = daten["channel_id"].astype(str)

    n_kanaele = daten["channel_id"].nunique()
    if n_kanaele < 2 or daten[spalte_periode].nunique() < 2:
        print(f"  [Skip][Panel-FE] zu wenig Variation (Kanaele={n_kanaele}).")
        return None

    formel = f"log_views ~ populismus_gesamt + log_duration_mean + C(channel_id) + C({spalte_periode})"
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
            return pd.Series({"delta_populismus": None, "delta_log_views": None, "delta_log_duration_mean": None})
        # log_duration_mean kann fehlen (Kanal-Periode-Zelle ohne klassifizierte
        # Videos in EINER der beiden Haelften, siehe lade_kanal_periode_kontrollen())
        # - .mean() ueberspringt NaN automatisch, ergibt aber selbst NaN, wenn ALLE
        # Werte einer Haelfte fehlen.
        return pd.Series({
            "delta_populismus": nach["populismus_gesamt"].mean() - vor["populismus_gesamt"].mean(),
            "delta_log_views": nach["log_views"].mean() - vor["log_views"].mean(),
            "delta_log_duration_mean": nach["log_duration_mean"].mean() - vor["log_duration_mean"].mean(),
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

    # Robustheitspruefung mit Laengenkontrolle (siehe Moduldocstring "Seit 2026-09-09"):
    # delta_log_duration_mean nutzt DIESELBE, auf die klassifizierten Videos beschraenkte
    # Population wie log_duration_mean in (a)/(c) - kein eigener Populationszuschnitt.
    # Pearson/Spearman oben bleiben davon unberuehrt (bivariate Masse ohne Kovariate).
    delta_kontrolle = delta.dropna(subset=["delta_log_duration_mean"])
    if len(delta_kontrolle) >= 3:
        modell_kontrolle = smf.ols("delta_log_views ~ delta_populismus + delta_log_duration_mean",
                                    data=delta_kontrolle).fit()
        ergebnis.update({
            "n_kanaele_mit_laengenkontrolle": len(delta_kontrolle),
            "koeffizient_mit_laengenkontrolle": modell_kontrolle.params["delta_populismus"],
            "se_mit_laengenkontrolle": modell_kontrolle.bse["delta_populismus"],
            "p_mit_laengenkontrolle": modell_kontrolle.pvalues["delta_populismus"],
        })
    else:
        print(f"  [Skip][Delta-Delta mit Laengenkontrolle] nur {len(delta_kontrolle)} Kanaele mit "
              f"delta_log_duration_mean.")
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
# BAUSTEIN (c): Heterogenitaet nach gruppe5 (OeRR/Trad./Alt-links/-mitte/-rechts)
# =========================================================

def gruppe5_heterogenitaet_test(df, spalte_periode, min_kanaele_je_gruppe=MIN_KANAELE_JE_GRUPPE):
    """y ~ C(channel_id) + C(periode) + log_duration_mean + populismus_gesamt:C(gruppe5),
    SE geclustert auf Kanalebene - Erweiterung von Baustein (a) um eine gruppe5-
    Interaktion, bewusst OHNE eigenen populismus_gesamt-Haupteffekt (dadurch ist
    C(gruppe5) innerhalb der Interaktion automatisch vollrangig kodiert, jeder
    Interaktionsterm direkt der gruppenspezifische Populismus-Erfolgs-Zusammenhang -
    identisches Designprinzip wie kriegspraemie_je_gruppe_test() in
    frage4_kriegspraemie_medientyp_bericht.py). Anschliessender F-Test: sind alle
    gruppenspezifischen Koeffizienten gemeinsam gleich? Gruppen mit weniger als
    min_kanaele_je_gruppe Kanaelen werden vorher ausgeschlossen (wie interaktions_test()
    in bericht_utils.py)."""
    daten = df.dropna(subset=["populismus_gesamt", "log_views", "log_duration_mean", "gruppe5"]).copy()
    daten["channel_id"] = daten["channel_id"].astype(str)

    vorhandene_gruppen = [g for g in GRUPPE5_REIHENFOLGE if (daten["gruppe5"] == g).any()
                          and daten.loc[daten["gruppe5"] == g, "channel_id"].nunique() >= min_kanaele_je_gruppe]
    if len(vorhandene_gruppen) < 2:
        print(f"  [Skip][Heterogenitaet gruppe5] zu wenig Gruppen mit >= {min_kanaele_je_gruppe} "
              f"Kanaelen ({vorhandene_gruppen}).")
        return None
    daten = daten[daten["gruppe5"].isin(vorhandene_gruppen)]
    daten["gruppe5"] = pd.Categorical(daten["gruppe5"], categories=vorhandene_gruppen)

    n_kanaele = daten["channel_id"].nunique()
    if n_kanaele < 2 or daten[spalte_periode].nunique() < 2:
        print(f"  [Skip][Heterogenitaet gruppe5] zu wenig Variation (Kanaele={n_kanaele}).")
        return None

    formel = (f"log_views ~ C(channel_id) + C({spalte_periode}) + log_duration_mean "
              f"+ populismus_gesamt:C(gruppe5)")
    modell = smf.ols(formel, data=daten).fit(
        cov_type="cluster", cov_kwds={"groups": daten["channel_id"]}
    )

    interaktions_terme = [p for p in modell.params.index if p.startswith("populismus_gesamt:C(gruppe5)")]
    if not interaktions_terme:
        print("  [Skip][Heterogenitaet gruppe5] keine Interaktionsterme im Modell "
              "(zu wenig Variation innerhalb Kanaelen).")
        return None

    je_gruppe = pd.DataFrame([{
        "gruppe5": term.split("[")[1].rstrip("]"),
        "koeffizient": modell.params[term],
        "se": modell.bse[term],
        "p": modell.pvalues[term],
    } for term in interaktions_terme])

    heterogenitaet = None
    if len(interaktions_terme) >= 2:
        hypothese = ", ".join(f"{interaktions_terme[0]} = {t}" for t in interaktions_terme[1:])
        f_test = modell.f_test(hypothese)
        heterogenitaet = {
            "f_stat": float(f_test.fvalue),
            "df_num": int(f_test.df_num),
            "df_denom": int(f_test.df_denom),
            "p": float(f_test.pvalue),
        }

    return {
        "je_gruppe": je_gruppe,
        "heterogenitaet": heterogenitaet,
        "n_beobachtungen": len(daten),
        "n_kanaele": n_kanaele,
    }


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
        if "koeffizient_mit_laengenkontrolle" in delta_ergebnis:
            print(f"  Mit Laengenkontrolle (delta_log_duration_mean): "
                  f"koeffizient={delta_ergebnis['koeffizient_mit_laengenkontrolle']:+.4f} "
                  f"(p={delta_ergebnis['p_mit_laengenkontrolle']:.4f}), "
                  f"n_kanaele={delta_ergebnis['n_kanaele_mit_laengenkontrolle']}")
        zeilen.append({"baustein": "delta_delta", **delta_ergebnis})
        _plotte_delta_delta(delta, granularitaet, delta_ergebnis)

    print(f"\n=== Baustein (c): Heterogenitaet nach gruppe5 ({granularitaet}) ===")
    heterogenitaet = gruppe5_heterogenitaet_test(df_g, spalte_periode)
    if heterogenitaet:
        for _, zeile in heterogenitaet["je_gruppe"].iterrows():
            sig = "signifikant" if zeile["p"] < 0.05 else "nicht signifikant"
            print(f"  [{zeile['gruppe5']}] Koeffizient (populismus_gesamt) = "
                  f"{zeile['koeffizient']:+.4f} (p={zeile['p']:.4f}) -> {sig}")
            zeilen.append({
                "baustein": "gruppe5_populismus", "gruppe5": zeile["gruppe5"],
                "koeffizient": zeile["koeffizient"], "se": zeile["se"], "p": zeile["p"],
                "n_beobachtungen": heterogenitaet["n_beobachtungen"], "n_kanaele": heterogenitaet["n_kanaele"],
            })
        if heterogenitaet["heterogenitaet"]:
            h = heterogenitaet["heterogenitaet"]
            sig = "signifikant" if h["p"] < 0.05 else "nicht signifikant"
            print(f"  [Heterogenitaet] F({h['df_num']}, {h['df_denom']}) = {h['f_stat']:.3f}, "
                  f"p = {h['p']:.4f} -> {sig} unterschiedliche Koeffizienten zwischen den Gruppen")
            zeilen.append({
                "baustein": "gruppe5_heterogenitaet_ftest", "gruppe5": "alle",
                "f_stat": h["f_stat"], "df_num": h["df_num"], "df_denom": h["df_denom"], "p": h["p"],
                "n_beobachtungen": heterogenitaet["n_beobachtungen"], "n_kanaele": heterogenitaet["n_kanaele"],
            })

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
        if zeile["baustein"] == "gruppe5_heterogenitaet_ftest":
            # F-Test hat keine Richtung/keinen einzelnen Koeffizienten (siehe koeffizient
            # ist NaN in dieser Zeile, gruppe5_populismus-Zeilen liefern die Einzelwerte).
            print(f"  [{zeile['baustein']}] ({zeile['granularitaet']}): F={zeile['f_stat']:.3f} "
                  f"-> {sig} unterschiedliche Koeffizienten zwischen den gruppe5-Kategorien "
                  f"(p={zeile['p']:.4f})")
            continue
        gruppe_praefix = f"gruppe5={zeile['gruppe5']} " if zeile["baustein"] == "gruppe5_populismus" else ""
        richtung = "positiv" if zeile["koeffizient"] > 0 else "negativ"
        print(f"  [{zeile['baustein']}] {gruppe_praefix}({zeile['granularitaet']}): {richtung}er Zusammenhang "
              f"({zeile['koeffizient']:+.4f}, {sig}, p={zeile['p']:.4f})")


if __name__ == "__main__":
    main()

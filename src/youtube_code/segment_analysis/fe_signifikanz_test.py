# -*- coding: utf-8 -*-
"""
fe_signifikanz_test.py

Prueft formal, ob eine Dimension (z.B. position_russland) innerhalb einer gefilterten
Kanalgruppe wirklich ueber die Zeit schwankt, oder ob die im Plot sichtbaren Ausschlaege
mit reinem Rauschen vertraeglich sind.

Modell: wert ~ Kanal-Fixed-Effects + Perioden-Dummies, Standardfehler geclustert auf
Kanalebene (wegen wiederholter Beobachtungen desselben Kanals ueber die Zeit).
F-Test: sind die Perioden-Dummies gemeinsam signifikant von 0 verschieden?
H0 = kein Unterschied zwischen den Perioden, nur Kanal-Niveauunterschiede.

Arbeitet auf VIDEO-Ebene (channel_video_populism.csv / channel_video_position.csv aus
prepare_channel_scores.py), nicht auf der aggregierten Kanal-Periode-Zeitreihe. Das
entspricht rechnerisch automatisch einer nach n_videos gewichteten Regression auf
Zellenebene, ohne das Gewicht explizit modellieren zu muessen - Kanal-Perioden-Zellen
mit mehr Videos bekommen dadurch mehr Einfluss.

ZWEI ROBUSTHEITSCHECKS gegen diese implizite Gewichtung:
- vergleiche_gewichtung(): derselbe lineare Trend auf der kanal-gleichgewichteten
  aggregierten Tabelle (deskriptiv_{modus}_{granularitaet}.csv) als Vergleich.
- jackknife_trend_test(): Leave-one-channel-out - zeigt, ob der Trend von einzelnen
  Kanaelen getragen wird.

Medientyp/Ideologie werden ueber die bereits vorhandenen Ladefunktionen aus
deskriptiv_aggregation.py gemergt (setzt voraus, dass beide Skripte im selben
Verzeichnis liegen).

Benoetigt statsmodels (pip install statsmodels --break-system-packages, falls noch
nicht installiert).
"""

import pandas as pd
import statsmodels.formula.api as smf

from youtube_code.config import OUTPUTS
from deskriptiv_aggregation import lade_medientyp, lade_ideologie

# =========================================================
# CONFIG
# =========================================================

MODUS = "stance"          # "populismus" | "stance"
GRANULARITAET = "monat"       # "quartal" | "monat"

SPALTE_PERIODE = {"quartal": "rel_quartal", "monat": "rel_monat"}[GRANULARITAET]

DATEINAME_VIDEO_EBENE = {
    "populismus": "channel_video_populism.csv",
    "stance": "channel_video_position.csv",
}
PFAD_EINGABE = OUTPUTS / "segment_analysis" / DATEINAME_VIDEO_EBENE[MODUS]

# Aggregierte Kanal x Periode Tabelle (Output von deskriptiv_aggregation.py) - fuer Populismus
# durch berechne_index() per Inner-Join auf Kanaele MIT gueltiger Vorkriegs-Baseline beschraenkt.
PFAD_AGGREGIERT = OUTPUTS / "segment_analysis" / "deskriptiv_{modus}_{granularitaet}.csv"

# Rohe, NICHT Baseline-gefilterte Kanal x Periode Zeitreihe direkt aus prepare_channel_scores.py -
# enthaelt auch Kanaele, die erst waehrend des Kriegs aktiv wurden und keine Baseline haben.
DATEINAME_ZEITREIHE_ROH = {
    "populismus": f"channel_{GRANULARITAET}_populism_timeseries.csv",
    "stance": f"channel_{GRANULARITAET}_position_timeseries.csv",
}
PFAD_ZEITREIHE_ROH = OUTPUTS / "segment_analysis" / DATEINAME_ZEITREIHE_ROH[MODUS]

# Spaltenname der zu testenden Dimension IN DER VIDEO-EBENE-DATEI, z.B.
# "position_russland", "position_westpolitik", "emotion" (stance) oder
# "volkszentrismus", "antielitismus", "manichaeische_moralisierung",
# "emotionale_intensitaet", "populismus_gesamt" (populismus).
DIMENSION = "position_russland"

# Gleiche Filterlogik wie FILTERKOMBINATIONEN in deskriptiv_plots.py: mehrere Spalten (UND),
# je Spalte eine Liste erlaubter Werte (ODER).
# Medientypen: ÖRR, Traditionelles Medium, Alternatives Medium, Politiker/Partei
FILTER = {
    # "medientyp": ["Alternatives Medium"],
    "medientyp": ["ÖRR"],
    # "ideologie_gruppe": ["rechts"],
}

# Nur Perioden im Fenster testen (z.B. um sehr duenn besetzte Randperioden auszuschliessen,
# oder um wie hier NUR die Kriegszeit zu betrachten, PERIODE_MIN=0). None = kein Limit.
PERIODE_MIN = -12
PERIODE_MAX = None

# Periode, die als "Schock" separat getestet wird (z.B. 0 = erste Periode nach Kriegsbeginn)
SCHOCKPERIODE = 0

# Vermuteter Strukturbruch (z.B. aus visueller Musterpruefung der Perioden-Koeffizienten)
BRUCHPUNKT = 30

# Wie die Kanalmenge zwischen video-gewichtetem und kanal-gleichgewichtetem Vergleich
# angeglichen wird (siehe vergleiche_gewichtung):
# "alle"        -> beide Versionen nutzen dieselbe Kanalmenge (Schnittmenge der Kanaele,
#                  die ueberhaupt in beiden Dateien vorkommen), unabhaengig davon, ob ein
#                  Kanal in jeder Periode vertreten ist.
# "durchgehend" -> zusaetzlich nur Kanaele, die in JEDER gemeinsamen Periode in BEIDEN
#                  Dateien mindestens eine Beobachtung haben (voll balanciertes Panel).
GEWICHTS_VERGLEICH_MODUS = "alle"

# Zusatzfilter fuer vergleiche_gewichtung: nur Kanaele mit gueltiger Vorkriegs-Baseline
# verwenden (auf BEIDEN Seiten des Vergleichs). Gegenprobe zur Frage, ob ein Trend von
# Kanaelen getrieben wird, die erst waehrend des Kriegs eingestiegen sind (keine Baseline) -
# bei True bleiben genau diese Kriegs-Neuzugaenge aussen vor.
NUR_KANAELE_MIT_BASELINE = False

# Mindestanzahl Videos je Kanal-Periode-Zelle fuer die UNGEFILTERTE Kanal-Zeitreihe
# (lade_kanalgewichtete_daten_ungefiltert). Anders als deskriptiv_aggregation.py's
# MIN_VIDEOS_PRO_PERIODE wird das hier nicht automatisch angewendet, da die rohe
# Zeitreihe direkt aus prepare_channel_scores.py gelesen wird. Ohne diesen Filter zaehlt
# eine Zelle mit 1 Video genauso viel wie eine mit 20 Videos.
MIN_VIDEOS_PRO_ZELLE_KANALGEWICHTET = 1


# =========================================================
# DATEN LADEN UND FILTERN
# =========================================================

def _wende_filter_an(df):
    """Gemeinsame Filterlogik (FILTER-Dict, PERIODE_MIN/MAX) fuer Video- und
    kanalgewichtete Daten."""
    for spalte, werte in FILTER.items():
        if spalte not in df.columns:
            raise KeyError(f"Filterspalte '{spalte}' nicht in den Daten.")
        df = df[df[spalte].isin(werte)]

    if PERIODE_MIN is not None:
        df = df[df[SPALTE_PERIODE] >= PERIODE_MIN]
    if PERIODE_MAX is not None:
        df = df[df[SPALTE_PERIODE] <= PERIODE_MAX]

    return df


def lade_gefilterte_daten():
    df = pd.read_csv(PFAD_EINGABE)
    print(f"[Eingabe] {len(df)} Video-Beobachtungen aus {PFAD_EINGABE}")

    if DIMENSION not in df.columns:
        raise KeyError(f"Dimension '{DIMENSION}' nicht in '{PFAD_EINGABE}'. "
                        f"Vorhanden: {list(df.columns)}")
    if SPALTE_PERIODE not in df.columns:
        raise KeyError(f"Spalte '{SPALTE_PERIODE}' nicht in '{PFAD_EINGABE}'. "
                        f"Vorhanden: {list(df.columns)}")

    med = lade_medientyp()
    ideo = lade_ideologie()
    df = df.merge(med, on="channel_id", how="left").merge(ideo, on="channel_id", how="left")

    df = _wende_filter_an(df)
    df = df.dropna(subset=[DIMENSION])

    print(f"[Filter] {len(df)} Video-Beobachtungen, {df['channel_id'].nunique()} Kanaele, "
          f"{df[SPALTE_PERIODE].nunique()} Perioden.")
    return df


def lade_kanalgewichtete_daten():
    """Aggregierte Kanal x Periode Tabelle (jede Zelle zaehlt gleich, unabhaengig von
    n_videos) - Gegenstueck zur video-gewichteten Hauptanalyse. ACHTUNG: bei
    MODUS='populismus' per Inner-Join auf Kanaele MIT gueltiger Vorkriegs-Baseline
    beschraenkt (siehe berechne_index() in deskriptiv_aggregation.py). Fuer einen
    Vergleich, der auch Kanaele ohne Baseline einschliesst, siehe
    lade_kanalgewichtete_daten_ungefiltert()."""
    pfad = str(PFAD_AGGREGIERT).format(modus=MODUS, granularitaet=GRANULARITAET)
    df = pd.read_csv(pfad)
    print(f"[Eingabe][kanalgewichtet] {len(df)} Zeilen aus {pfad}")

    df = df[df["dimension"] == DIMENSION]
    if df.empty:
        raise KeyError(f"Dimension '{DIMENSION}' nicht in '{pfad}' gefunden.")

    df = _wende_filter_an(df)
    df = df.dropna(subset=["wert_roh"])
    df = df.rename(columns={"wert_roh": DIMENSION})

    print(f"[Filter][kanalgewichtet] {len(df)} Kanal-Perioden-Beobachtungen, "
          f"{df['channel_id'].nunique()} Kanaele, {df[SPALTE_PERIODE].nunique()} Perioden.")
    return df


def lade_baseline_kanalliste():
    """Kanaele mit gueltiger Vorkriegs-Baseline, wie in deskriptiv_aggregation.py's
    berechne_index() definiert (MIN_BASELINE_QUARTALE_BESETZT, MIN_VIDEOS_BASELINE_GESAMT).
    Unabhaengig vom aktuellen MODUS dieses Skripts, da Baseline-Gueltigkeit eine
    Eigenschaft der Populismus-Klassifikation ist (nur dort wird ueberhaupt eine
    Vorkriegs-Baseline gebildet)."""
    pfad = str(PFAD_AGGREGIERT).format(modus="populismus", granularitaet=GRANULARITAET)
    df = pd.read_csv(pfad)
    kanaele = set(df["channel_id"].astype(str).unique())
    print(f"[Baseline-Liste] {len(kanaele)} Kanaele mit gueltiger Vorkriegs-Baseline (aus {pfad}).")
    return kanaele


def lade_kanalgewichtete_daten_ungefiltert():
    """Wie lade_kanalgewichtete_daten(), aber OHNE die Baseline-Anforderung aus
    berechne_index() (deskriptiv_aggregation.py) - liest die rohe Zeitreihe direkt aus
    prepare_channel_scores.py, bevor irgendein Inner-Join Kanaele ausschliesst. Dadurch
    bleiben auch Kanaele erhalten, die erst waehrend des Kriegs aktiv wurden und keine
    gueltige Vorkriegs-Baseline haben. Medientyp/Ideologie werden hier selbst gemergt,
    da die rohe Zeitreihe diese Spalten (anders als deskriptiv_aggregation.py-Output)
    noch nicht enthaelt."""
    df = pd.read_csv(PFAD_ZEITREIHE_ROH)
    print(f"[Eingabe][kanalgewichtet, ungefiltert] {len(df)} Zeilen aus {PFAD_ZEITREIHE_ROH}")

    df = df[df["dimension"] == DIMENSION]
    if df.empty:
        raise KeyError(f"Dimension '{DIMENSION}' nicht in '{PFAD_ZEITREIHE_ROH}' gefunden.")

    med = lade_medientyp()
    ideo = lade_ideologie()
    df = df.merge(med, on="channel_id", how="left").merge(ideo, on="channel_id", how="left")

    df = _wende_filter_an(df)

    vor_videofilter = len(df)
    df = df[df["n_videos"] >= MIN_VIDEOS_PRO_ZELLE_KANALGEWICHTET]
    verworfen = vor_videofilter - len(df)
    if verworfen:
        print(f"[Filter][kanalgewichtet, ungefiltert] {verworfen} Zellen unter "
              f"MIN_VIDEOS_PRO_ZELLE_KANALGEWICHTET={MIN_VIDEOS_PRO_ZELLE_KANALGEWICHTET} -> verworfen.")

    df = df.dropna(subset=["wert"])
    df = df.rename(columns={"wert": DIMENSION})

    print(f"[Filter][kanalgewichtet, ungefiltert] {len(df)} Kanal-Perioden-Beobachtungen, "
          f"{df['channel_id'].nunique()} Kanaele, {df[SPALTE_PERIODE].nunique()} Perioden "
          f"(inkl. Kanaele ohne Vorkriegs-Baseline).")
    return df


# =========================================================
# FE-MODELL + F-TEST
# =========================================================

def fe_signifikanz_test(df):
    """OLS mit Kanal-FE und Perioden-Dummies auf Video-Ebene, SE geclustert auf
    Kanalebene. F-Test: sind alle Perioden-Dummies gemeinsam 0?"""

    daten = df.rename(columns={DIMENSION: "y", SPALTE_PERIODE: "periode_num"}).copy()
    daten["channel_id"] = daten["channel_id"].astype(str)

    # Kategorien numerisch sortieren, damit die Referenzperiode die zeitlich fruehste ist
    # (sonst sortiert patsy Perioden-Strings alphabetisch, was bei negativen Zahlen
    # nicht der numerischen Reihenfolge entspricht).
    periode_reihenfolge = sorted(daten["periode_num"].unique())
    daten["periode"] = pd.Categorical(
        daten["periode_num"], categories=periode_reihenfolge, ordered=True
    )

    modell = smf.ols("y ~ C(channel_id) + C(periode)", data=daten).fit(
        cov_type="cluster", cov_kwds={"groups": daten["channel_id"]}
    )

    periode_koeffizienten = [p for p in modell.params.index if p.startswith("C(periode)")]
    if not periode_koeffizienten:
        print("[Warnung] Nur eine Periode nach Filterung -> kein Zeitvergleich moeglich.")
        return modell, None

    hypothese = ", ".join(f"{p} = 0" for p in periode_koeffizienten)
    f_test = modell.f_test(hypothese)

    print(f"\n[F-Test] H0: alle Perioden-Dummies = 0 (kein Unterschied ueber die Zeit, "
          f"nur Kanal-Niveauunterschiede)")
    print(f"  F({int(f_test.df_num)}, {int(f_test.df_denom)}) = {float(f_test.fvalue):.3f}, "
          f"p = {float(f_test.pvalue):.4f}")
    if f_test.pvalue < 0.05:
        print("  -> signifikant: die Werte unterscheiden sich ueber die Zeit, mehr als "
              "durch reine Kanal-Niveauunterschiede erklaerbar.")
    else:
        print("  -> NICHT signifikant: die im Plot sichtbaren Schwankungen sind mit "
              "reinem Rauschen (bei gegebener Kanalzusammensetzung) vertraeglich.")

    print(f"\nGeschaetzte Abweichungen je Periode (Referenzperiode = {periode_reihenfolge[0]}, "
          f"geclusterte SE):")
    tab = modell.summary2().tables[1].loc[periode_koeffizienten].copy()
    tab.index = [i.split("T.")[1].rstrip("]") for i in tab.index]

    coef_spalte = next(c for c in tab.columns if c.startswith("Coef"))
    se_spalte = next(c for c in tab.columns if "Std.Err" in c)
    p_spalte = next(c for c in tab.columns if c.startswith("P>"))

    tab = tab.rename(columns={coef_spalte: "koeffizient", se_spalte: "se", p_spalte: "p"})
    tab = tab[["koeffizient", "se", "p"]]
    tab.index = tab.index.astype(float)
    tab = tab.sort_index()
    print(tab.to_string())

    return modell, f_test


# =========================================================
# ZUSATZ 1: Schock-Test (nur "Periode 0 vs. Rest" statt volle Saettigung)
# =========================================================

def schock_test(df, schockperiode=0):
    """Vergleicht ein sparsames Modell (Kanal-FE + EIN Dummy fuer die Schockperiode)
    mit dem Nullmodell (nur Kanal-FE). Die Signifikanz des Schock-Koeffizienten (t-Test
    mit geclusterter SE) beantwortet direkt: weicht die Schockperiode signifikant vom
    Rest ab? Zusaetzlich: partielles R² (Varianzanteil, den der Schock-Dummy UEBER die
    Kanal-FE hinaus erklaert) als Effektstaerken-Mass."""

    daten = df.rename(columns={DIMENSION: "y", SPALTE_PERIODE: "periode_num"}).copy()
    daten["channel_id"] = daten["channel_id"].astype(str)
    daten["schock"] = (daten["periode_num"] == schockperiode).astype(int)

    if daten["schock"].nunique() < 2:
        print(f"[Warnung] Schockperiode {schockperiode} nicht in den Daten -> Schock-Test uebersprungen.")
        return None

    modell_reduziert = smf.ols("y ~ C(channel_id)", data=daten).fit()
    modell_schock = smf.ols("y ~ C(channel_id) + schock", data=daten).fit(
        cov_type="cluster", cov_kwds={"groups": daten["channel_id"]}
    )

    koef = modell_schock.params["schock"]
    se = modell_schock.bse["schock"]
    p = modell_schock.pvalues["schock"]

    # Partielles R²: Anteil der von channel-FE unerklaerten Varianz, den der Schock-Dummy
    # zusaetzlich erklaert. Nutzt die (nicht-geclusterte) SSR beider Modelle, rein deskriptiv
    # als Effektstaerke - die Signifikanzaussage kommt aus dem geclusterten t-Test oben.
    ssr_reduziert = modell_reduziert.ssr
    ssr_voll = modell_schock.ssr
    partielles_r2 = (ssr_reduziert - ssr_voll) / ssr_reduziert

    print(f"\n[Schock-Test] Periode {schockperiode} vs. Rest (ein einzelner Dummy statt "
          f"voller Perioden-Saettigung):")
    print(f"  Koeffizient (Periode {schockperiode} - Rest) = {koef:.4f}, "
          f"SE = {se:.4f}, p = {p:.4f}")
    if p < 0.05:
        print(f"  -> signifikant: Periode {schockperiode} weicht vom Rest ab.")
    else:
        print(f"  -> NICHT signifikant: Periode {schockperiode} unterscheidet sich nicht "
              f"robust vom Rest.")
    print(f"  Partielles R² (Schock-Dummy ueber Kanal-FE hinaus) = {partielles_r2:.4f}")

    return modell_schock


# =========================================================
# ZUSATZ 3: Linearer Trend statt voller Perioden-Saettigung
# =========================================================

def linearer_trend_test(df, bezeichnung="Video-Ebene"):
    """Sparsames Modell: Kanal-FE + EIN stetiger Zeit-Koeffizient (statt einem Dummy je
    Periode). Beantwortet direkt: gibt es einen monotonen Trend ueber die Zeit? Behebt
    nebenbei das Rang-Deffizienz-Problem der vollen Saettigung, da nur 1 zusaetzlicher
    Parameter statt einem je Periode geschaetzt wird."""

    daten = df.rename(columns={DIMENSION: "y", SPALTE_PERIODE: "periode_num"}).copy()
    daten["channel_id"] = daten["channel_id"].astype(str)

    modell = smf.ols("y ~ C(channel_id) + periode_num", data=daten).fit(
        cov_type="cluster", cov_kwds={"groups": daten["channel_id"]}
    )

    koef = modell.params["periode_num"]
    se = modell.bse["periode_num"]
    p = modell.pvalues["periode_num"]

    spannweite = daten["periode_num"].max() - daten["periode_num"].min()
    impliziert = koef * spannweite

    print(f"\n[Linearer Trend][{bezeichnung}] {DIMENSION} ~ Kanal-FE + Periode (stetig):")
    print(f"  Steigung = {koef:.5f} pro {SPALTE_PERIODE.replace('rel_', '')}, "
          f"SE = {se:.5f}, p = {p:.4f}")
    if p < 0.05:
        print(f"  -> signifikanter Trend: ueber die beobachtete Spannweite von "
              f"{int(spannweite)} Perioden impliziert das eine Gesamtveraenderung von "
              f"~{impliziert:.3f}.")
    else:
        print("  -> kein signifikanter linearer Trend.")

    return modell


# =========================================================
# ZUSATZ 5: Vergleich video-gewichtet vs. kanal-gleichgewichtet
# =========================================================

def _kanaele_durchgehend_vertreten(df, kanaele, perioden):
    """Liefert die Teilmenge von 'kanaele', die im gegebenen df in JEDER Periode aus
    'perioden' mindestens eine Beobachtung hat."""
    teil = df[df["channel_id"].astype(str).isin(kanaele)]
    besetzte_perioden_je_kanal = teil.groupby(teil["channel_id"].astype(str))[SPALTE_PERIODE].nunique()
    return set(besetzte_perioden_je_kanal[besetzte_perioden_je_kanal == len(perioden)].index)


def vergleiche_gewichtung(df_video):
    """Wiederholt den linearen Trend-Test auf der kanal-gleichgewichteten aggregierten
    Tabelle - auf EXAKT derselben Kanal- und Periodenmenge wie die Video-Ebene, damit der
    verbleibende Unterschied wirklich nur noch an der Gewichtung liegt (nicht an
    unterschiedlichen Stichproben, z.B. weil die aggregierte Tabelle Kanaele ohne
    Vorkriegs-Baseline oder Perioden jenseits eines Cutoffs bereits ausgeschlossen hat)."""

    print("\n" + "=" * 60)
    print("VERGLEICH: video-gewichtet vs. kanal-gleichgewichtet")
    print(f"(Angleichungs-Modus: {GEWICHTS_VERGLEICH_MODUS})")
    print("=" * 60)

    df_kanal = lade_kanalgewichtete_daten_ungefiltert()
    if df_kanal["channel_id"].nunique() < 2:
        print("[Warnung] Zu wenig Kanaele in der Zeitreihe -> Vergleich uebersprungen.")
        return None, None

    if NUR_KANAELE_MIT_BASELINE:
        baseline_kanaele = lade_baseline_kanalliste()
        vor_video = df_video["channel_id"].astype(str).nunique()
        vor_kanal = df_kanal["channel_id"].astype(str).nunique()
        df_video = df_video[df_video["channel_id"].astype(str).isin(baseline_kanaele)]
        df_kanal = df_kanal[df_kanal["channel_id"].astype(str).isin(baseline_kanaele)]
        print(f"[Baseline-Filter] Video-Ebene: {vor_video} -> {df_video['channel_id'].nunique()} "
              f"Kanaele (nur mit Baseline).")
        print(f"[Baseline-Filter] Kanal-Ebene: {vor_kanal} -> {df_kanal['channel_id'].nunique()} "
              f"Kanaele (nur mit Baseline).")

    # Gemeinsame Periodenspanne
    perioden_video = set(df_video[SPALTE_PERIODE].unique())
    perioden_kanal = set(df_kanal[SPALTE_PERIODE].unique())
    gemeinsame_perioden = perioden_video & perioden_kanal
    if perioden_video != perioden_kanal:
        print(f"[Angleichung] Perioden nur in Video-Datei: {sorted(perioden_video - perioden_kanal)}")
        print(f"[Angleichung] Perioden nur in Kanal-Datei: {sorted(perioden_kanal - perioden_video)}")
    print(f"[Angleichung] Gemeinsame Perioden: {len(gemeinsame_perioden)}")

    df_video = df_video[df_video[SPALTE_PERIODE].isin(gemeinsame_perioden)]
    df_kanal = df_kanal[df_kanal[SPALTE_PERIODE].isin(gemeinsame_perioden)]

    # Gemeinsame Kanalmenge (in beiden Dateien ueberhaupt vorhanden, nach Periodenfilter)
    kanaele_video = set(df_video["channel_id"].astype(str))
    kanaele_kanal = set(df_kanal["channel_id"].astype(str))
    gemeinsame_kanaele = kanaele_video & kanaele_kanal
    print(f"[Angleichung] Kanaele nur in Video-Datei: {len(kanaele_video - kanaele_kanal)}")
    print(f"[Angleichung] Kanaele nur in Kanal-Datei: {len(kanaele_kanal - kanaele_video)}")
    print(f"[Angleichung] Gemeinsame Kanaele: {len(gemeinsame_kanaele)}")

    if GEWICHTS_VERGLEICH_MODUS == "durchgehend":
        durchgehend_video = _kanaele_durchgehend_vertreten(df_video, gemeinsame_kanaele, gemeinsame_perioden)
        durchgehend_kanal = _kanaele_durchgehend_vertreten(df_kanal, gemeinsame_kanaele, gemeinsame_perioden)
        finale_kanaele = durchgehend_video & durchgehend_kanal
        print(f"[Angleichung] Davon durchgehend (in jeder gemeinsamen Periode, in beiden "
              f"Dateien) vertreten: {len(finale_kanaele)}")
    elif GEWICHTS_VERGLEICH_MODUS == "alle":
        finale_kanaele = gemeinsame_kanaele
    else:
        raise ValueError(f"Unbekannter GEWICHTS_VERGLEICH_MODUS: {GEWICHTS_VERGLEICH_MODUS}")

    if len(finale_kanaele) < 2:
        print("[Warnung] Weniger als 2 Kanaele nach Angleichung -> Vergleich uebersprungen.")
        return None, None

    df_video = df_video[df_video["channel_id"].astype(str).isin(finale_kanaele)]
    df_kanal = df_kanal[df_kanal["channel_id"].astype(str).isin(finale_kanaele)]
    print(f"[Angleichung] Finale Stichprobe fuer beide Versionen: {len(finale_kanaele)} Kanaele, "
          f"{len(gemeinsame_perioden)} Perioden.")

    modell_video = linearer_trend_test(df_video, bezeichnung="video-gewichtet, angeglichen")
    modell_kanal = linearer_trend_test(df_kanal, bezeichnung="kanal-gleichgewichtet, angeglichen")

    koef_video = modell_video.params["periode_num"]
    koef_kanal = modell_kanal.params["periode_num"]
    p_video = modell_video.pvalues["periode_num"]
    p_kanal = modell_kanal.pvalues["periode_num"]
    print(f"\n[Vergleich] Steigung video-gewichtet = {koef_video:.5f} (p={p_video:.4f}) vs. "
          f"kanal-gleichgewichtet = {koef_kanal:.5f} (p={p_kanal:.4f})")

    gleiche_richtung = (koef_video > 0) == (koef_kanal > 0)
    beide_signifikant = p_video < 0.05 and p_kanal < 0.05
    nur_eines_signifikant = (p_video < 0.05) != (p_kanal < 0.05)

    if not gleiche_richtung:
        print("  -> UNTERSCHIEDLICHE Richtung je nach Gewichtung: Befund ist nicht robust, "
              "vermutlich von einzelnen videostarken Kanaelen getrieben.")
    elif beide_signifikant:
        print("  -> gleiche Richtung, BEIDE signifikant: Befund robust gegen die Gewichtungsfrage.")
    elif nur_eines_signifikant:
        seite = "video-gewichtet" if p_video < 0.05 else "kanal-gleichgewichtet"
        print(f"  -> gleiche Richtung, aber NUR {seite} signifikant: Befund haengt von der "
              f"Gewichtung ab, nicht robust in beiden Spezifikationen.")
    else:
        print("  -> gleiche Richtung, aber KEINE der beiden Versionen signifikant: "
              "kein belastbarer Trend in dieser Stichprobe.")

    return modell_video, modell_kanal


# =========================================================
# ZUSATZ 6: Leave-one-channel-out Jackknife
# =========================================================

def jackknife_trend_test(df):
    """Wiederholt den linearen Trend-Test einmal je Kanal, mit genau diesem Kanal
    ausgeschlossen. Zeigt, ob die Steigung/Signifikanz von einzelnen Kanaelen abhaengt,
    statt sich gleichmaessig ueber die Stichprobe zu verteilen."""

    daten = df.rename(columns={DIMENSION: "y", SPALTE_PERIODE: "periode_num"}).copy()
    daten["channel_id"] = daten["channel_id"].astype(str)
    kanaele = sorted(daten["channel_id"].unique())

    print(f"\n[Jackknife] Wiederhole den linearen Trend-Test {len(kanaele)}x, "
          f"jeweils ein Kanal ausgeschlossen ...")

    ergebnisse = []
    for k in kanaele:
        teil = daten[daten["channel_id"] != k]
        if teil["channel_id"].nunique() < 2:
            continue
        modell = smf.ols("y ~ C(channel_id) + periode_num", data=teil).fit(
            cov_type="cluster", cov_kwds={"groups": teil["channel_id"]}
        )
        ergebnisse.append({
            "ausgeschlossener_kanal": k,
            "koeffizient": modell.params["periode_num"],
            "p": modell.pvalues["periode_num"],
        })

    res = pd.DataFrame(ergebnisse)

    voll = smf.ols("y ~ C(channel_id) + periode_num", data=daten).fit(
        cov_type="cluster", cov_kwds={"groups": daten["channel_id"]}
    )
    koef_voll = voll.params["periode_num"]
    p_voll = voll.pvalues["periode_num"]
    war_signifikant = p_voll < 0.05

    print(f"  Vollstaendige Stichprobe: Steigung = {koef_voll:.5f}, p = {p_voll:.4f}")
    print(f"  Jackknife-Steigungen: min = {res['koeffizient'].min():.5f}, "
          f"max = {res['koeffizient'].max():.5f}, "
          f"mean = {res['koeffizient'].mean():.5f}, "
          f"sd = {res['koeffizient'].std():.5f}")
    print(f"  Vorzeichen: {(res['koeffizient'] > 0).sum()} von {len(res)} weiterhin positiv")

    if war_signifikant:
        kippt_insignifikant = res[res["p"] >= 0.05]
        print(f"  {len(kippt_insignifikant)} von {len(res)} Ausschluessen lassen die Steigung "
              f"insignifikant werden (p >= 0.05):")
        if not kippt_insignifikant.empty:
            print(kippt_insignifikant.sort_values("p", ascending=False).to_string(index=False))
    else:
        wird_signifikant = res[res["p"] < 0.05]
        print(f"  {len(wird_signifikant)} von {len(res)} Ausschluessen wuerden die Steigung "
              f"signifikant machen (p < 0.05):")
        if not wird_signifikant.empty:
            print(wird_signifikant.sort_values("p").to_string(index=False))

    if res["koeffizient"].std() > 0 and abs(koef_voll) > 0:
        variationskoeffizient = res["koeffizient"].std() / abs(koef_voll)
        if variationskoeffizient > 0.5:
            print(f"  -> Hohe Schwankung der Jackknife-Steigungen relativ zum Gesamteffekt "
                  f"(Variationskoeffizient = {variationskoeffizient:.2f}): Befund koennte von "
                  f"einzelnen Kanaelen getrieben sein.")
        else:
            print(f"  -> Steigung bleibt ueber alle Ausschluesse hinweg stabil "
                  f"(Variationskoeffizient = {variationskoeffizient:.2f}): kein Hinweis auf "
                  f"einzelne dominante Kanaele.")

    return res


# =========================================================
# ZUSATZ 4: Bruchpunkt-Test (Chow-Test-artig)
# =========================================================

def bruchpunkt_test(df, bruchpunkt=BRUCHPUNKT):
    """Piecewise-linear: eigener Achsenabschnitt-Sprung UND eigene Steigung ab dem
    Bruchpunkt, zusaetzlich zum linearen Trend davor. Joint-F-Test auf beide neuen
    Parameter (Sprung + Steigungsaenderung) prueft, ob ueberhaupt ein Strukturbruch
    an dieser Stelle vorliegt (Chow-Test-Logik)."""

    daten = df.rename(columns={DIMENSION: "y", SPALTE_PERIODE: "periode_num"}).copy()
    daten["channel_id"] = daten["channel_id"].astype(str)
    daten["post"] = (daten["periode_num"] >= bruchpunkt).astype(int)

    if daten["post"].nunique() < 2:
        print(f"[Warnung] Bruchpunkt {bruchpunkt} liegt ausserhalb der Daten -> Test uebersprungen.")
        return None, None

    modell = smf.ols("y ~ C(channel_id) + periode_num * post", data=daten).fit(
        cov_type="cluster", cov_kwds={"groups": daten["channel_id"]}
    )

    f_test = modell.f_test("post = 0, periode_num:post = 0")

    print(f"\n[Bruchpunkt-Test] Strukturbruch bei Periode {bruchpunkt} "
          f"(Chow-Test-Logik, geclusterte SE):")
    print(f"  Trend vor dem Bruchpunkt: {modell.params['periode_num']:.5f} "
          f"(p = {modell.pvalues['periode_num']:.4f})")
    print(f"  Niveausprung bei Periode {bruchpunkt}: {modell.params['post']:.5f} "
          f"(p = {modell.pvalues['post']:.4f})")
    print(f"  Steigungsaenderung ab Periode {bruchpunkt}: "
          f"{modell.params['periode_num:post']:.5f} "
          f"(p = {modell.pvalues['periode_num:post']:.4f})")
    print(f"  Gemeinsamer F-Test (Sprung + Steigungsaenderung = 0): "
          f"F({int(f_test.df_num)}, {int(f_test.df_denom)}) = {float(f_test.fvalue):.3f}, "
          f"p = {float(f_test.pvalue):.4f}")
    if f_test.pvalue < 0.05:
        print(f"  -> signifikanter Strukturbruch bei Periode {bruchpunkt}.")
    else:
        print(f"  -> kein signifikanter Strukturbruch bei Periode {bruchpunkt} "
              f"(bei diesem Bruchpunkt-Kandidaten).")

    return modell, f_test


# =========================================================
# ZUSATZ 2: F-Test auf die uebrigen Perioden OHNE die Schockperiode
# =========================================================

def test_rest_ohne_schockperiode(df, schockperiode=0):
    """Schliesst die Schockperiode komplett aus und wiederholt den vollen FE-Test auf
    den verbleibenden Perioden. Falls DIESER F-Test nicht mehr signifikant ist, war die
    urspruengliche Signifikanz vor allem durch die Schockperiode getrieben - der Rest der
    Zeitreihe ist dann mit Rauschen um ein stabiles Niveau vertraeglich."""

    print(f"\n[Ohne Periode {schockperiode}] Wiederhole den FE-Test nur auf den "
          f"uebrigen Perioden:")

    df_rest = df[df[SPALTE_PERIODE] != schockperiode]
    if df_rest["channel_id"].nunique() < 2 or df_rest[SPALTE_PERIODE].nunique() < 2:
        print("  [Warnung] Zu wenig Kanaele/Perioden nach Ausschluss -> Test uebersprungen.")
        return None, None

    return fe_signifikanz_test(df_rest)


# =========================================================
# MAIN
# =========================================================

def main():
    print(f"=== FE-Signifikanztest: {DIMENSION} ({MODUS}, {GRANULARITAET}, Video-Ebene) ===")
    print(f"Filter: {FILTER}")

    df = lade_gefilterte_daten()
    if df["channel_id"].nunique() < 2:
        raise ValueError("Weniger als 2 Kanaele nach Filterung -> Kanal-FE nicht sinnvoll schaetzbar.")

    fe_signifikanz_test(df)
    schock_test(df, schockperiode=SCHOCKPERIODE)
    vergleiche_gewichtung(df)
    # jackknife_trend_test(df)
    # bruchpunkt_test(df, bruchpunkt=BRUCHPUNKT)
    # test_rest_ohne_schockperiode(df, schockperiode=SCHOCKPERIODE)


if __name__ == "__main__":
    main()
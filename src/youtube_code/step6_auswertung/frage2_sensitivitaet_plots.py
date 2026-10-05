# -*- coding: utf-8 -*-
"""
frage2_sensitivitaet_plots.py

Sensitivitaetsanalyse zu Forschungsfrage 2 (Kanalerfolg, .claude/CLAUDE.md): prueft, wie
robust die deskriptiven Kernaussagen aus deskriptiv_plots.py (MODUS="erfolg") und
frage2_erfolg_bericht.py gegenueber mehreren methodischen Einzelentscheidungen sind, BEVOR
die formale Regression darauf aufbaut. Dafuer wird dieselbe Standard-Gruppierung (5 Gruppen:
OERR, Traditionelles Medium, Alternative Medien links/mitte/rechts, siehe baue_gruppe5_lokal())
ueber eine strukturierte Matrix aus Aggregationsebene x Metrik x Ausgangsbasis geplottet.
Siehe .claude/plans/frage2_sensitivitaet_plots.md fuer die vollstaendige Herleitung.

Feste methodische Eckdaten (siehe Plan, vom Nutzer bestaetigt):
  - GRANULARITAET fix auf "monat" (Kanal-Monat als Beobachtungseinheit, wie der Standard in
    deskriptiv_plots.py).
  - KANALFILTER fix auf "beide_perioden": nur Kanaele mit mindestens einem Video vor UND
    mindestens einem Video ab Kriegsbeginn (siehe filtere_kanalfilter_beide_perioden()) -
    wird EINMAL auf die komplette Video-Ebene (alle Videos, vor dem Umfang-Split) angewendet,
    damit alle Grafiken der Matrix denselben Kanalbestand zugrunde legen.
  - Winsorisierter Mittelwert: BEIDE Grenzen parallel (5%/95% UND 1%/99%), je eigene Grafik.

Kombinationsmatrix (siehe Plan fuer die vollstaendige Herleitung des mathematischen Dedups):

  Aggregationsebenen:
    - "zellen_ungewichtet" (A1): erst je Kanal x Monat eine Zelle (Mittelwert/Summe der
      Videos), dann UNGEWICHTETER Mittelwert/Median ueber die Kanaele - der bestehende
      Standard aus deskriptiv_plots.py/aggregiere().
    - "video_ebene" (A2): keine Kanal-Monats-Zelle, alle Videos der Gruppe im Monat werden
      direkt gepoolt (= lineare Gewichtung nach n_videos).
    - "zellen_gewichtet" (A3): wie A1, aber beim Kombinieren zaehlt jede Zelle mit gedaempftem
      Gewicht n_videos ** GEWICHT_EXPONENT (Standard sqrt(n_videos)) - bewusst zwischen A1
      (jede Zelle gleich) und A2 (volle lineare Dominanz vieluploadender Kanaele) positioniert.

  Metriken: Mittelwert, winsorisierter Mittelwert (5/95 und 1/99, je eigene Grafik), Median,
  Summe. Wegen der gedaempften (nicht linearen) A3-Gewichtung unterscheiden sich A1/A2/A3 bei
  Mittelwert/Winsor/Median jeweils rechnerisch (3 Grafiken je Metrik, 6 fuer Winsor wegen
  zweier Grenzen) - NUR bei der Summe sind A2 und A3 identisch ("gepoolt" = Gesamtsumme aller
  Videos der Gruppe/Periode, kennt keine Gewichtung), zusaetzlich A1 ("zellen_ungewichtet" =
  Mittelwert der Kanal-Monats-Summen ueber Kanaele, wie die bestehende log_views_summe-Logik)
  -> 2 Grafiken. Macht 3+6+3+2 = 14 Grafiken je (Ausgangsbasis x Umfang).

  Ausgangsbasis:
    - "absolut": rohe view_count-Werte. 14 Grafiken.
    - "index_vorkriegsmittel_mean" / "index_vorkriegsmittel_median": jeder Kanal auf sein
      EIGENES Vorkriegs-Mittel bzw. -Median (ueber ALLE Videos im Baseline-Fenster, siehe
      berechne_baseline()) indexiert (=100). Kanaele ohne gueltige Baseline fallen raus.
      "_mean" ist die urspruengliche Definition; bei rechtsschiefen View-Verteilungen
      (typisch fuer YouTube) liegt das Mittel eines Kanals aber strukturell UEBER seinem
      Median-Video, wodurch die Metrik "median" auf "_mean"-Basis systematisch unter
      Index=100 landet, selbst OHNE echte Veraenderung (siehe Chatverlauf-Diagnose: bei
      OERR lag das Mittel je Kanal im Median beim 2,14-fachen des Kanal-Medians).
      "_median" behebt das fuer die Metrik "median" (Index=100 = "gleich wie das eigene
      mediane Vorkriegsvideo") und wird als zusaetzliche, mit "_mean" direkt vergleichbare
      Variante gefuehrt (beide standardmaessig aktiv in BASIS_KONFIG).
    - "subscriber_norm": view_count / subscribers (Snapshot aus channel_erfolg_snapshot.csv).
      LIMITATION (siehe Methodik-Datei): nur ein EINMALIGER, aktueller Abo-Snapshot je Kanal,
      kein historischer Stand zum jeweiligen Video-Zeitpunkt - derselbe (heutige) Wert wird
      fuer alle Perioden des Kanals verwendet. Kanaele ohne Eintrag/mit subscribers <= 0
      fallen raus.
    Bei beiden normierten Basen ergibt die Metrik "Summe" keinen sinnvoll interpretierbaren
    Wert (Summe von Verhaeltniszahlen) -> dort je 12 statt 14 Grafiken.

  Umfang: "alle" Videos vs. "topic" (nur Kriegsvideos, ist_kriegsvideo == 1) - wie
  NUR_TOPICVIDEOS in deskriptiv_plots.py.

  Gesamtzahl: (14 absolut + 12 Index-Mittel + 12 Index-Median + 12 Subscriber-Norm) x 2
  Umfaenge = 100 Liniendiagramme im theoretischen Vollausbau (alle BASIS_KONFIG-Eintraege
  aktiv; Standard-Konfiguration hat nur die beiden Index-Basen aktiv, siehe BASIS_KONFIG),
  je 5 Linien, eine je Gruppe5-Kategorie, plus eine Methodik-Uebersichtsdatei.

Kombinierte Grafik (KOMBI_*, siehe CONFIG): zusaetzlich zur Kombinationsmatrix erzeugt
erzeuge_kombinierte_grafiken() je Kombination aus KOMBI_METRIKEN x KOMBI_AGGREGATIONSEBENEN x
KOMBI_BASEN (alle drei als Listen im CONFIG-Block, damit mehrere Spezifikationen in einem
Lauf entstehen) EINE Grafik mit 2 x 5 Linien: je Gruppe5-Kategorie eine dicke Linie fuer den
Hauptfokus KOMBI_HAUPTFOKUS_UMFANG (Standard "topic" = nur Kriegsvideos) und eine duennere,
transparentere Linie in DERSELBEN Farbe fuer den Vergleichswert KOMBI_VERGLEICHS_UMFANG
(Standard "alle" Videos) - direkter visueller Vergleich, ob der Gruppentrend bei Kriegsvideos
vom Gesamttrend des Kanals abweicht. Standard-Spezifikation (Nutzervorgabe): Median,
video-Ebene, Index - standardmaessig fuer BEIDE Baseline-Varianten (Vorkriegsmittel UND
-median, siehe BASIS_KONFIG) in einem Lauf, zum direkten Vergleich der beiden Index-
Definitionen. Nutzt dieselben Bausteine (ergaenze_wert_video(), baue_zellen(),
kombiniere(), glaette()) wie die Kombinationsmatrix. Dateinamen:
erfolg_kombi_<ebene>_<metrik>_<basis>_<hauptfokus>-vs-<vergleich>_monat.png.

Datenquelle: outputs/segment_analysis/channel_video_erfolg.csv (Video-Ebene, bereits
Whitelist-gefiltert, aus prepare_success_metrics.py) - Kanal-Monats-Zellen werden fuer volle
Kontrolle (inkl. n_videos je Zelle, fuer die A3-Gewichtung) selbst per groupby gebildet, nicht
aus channel_monat_erfolg_timeseries.csv nachgeladen. Keine 95%-CI-Baender (Signifikanztests
laufen bereits separat in frage2_erfolg_bericht.py) und keine Ereignis-Marker (reiner
Methodenvergleich, keine Ereignisanalyse, anders als deskriptiv_plots.py::EREIGNISSE).

Smoothing (GLAETTUNG_LOWESS_FRAC, dieselbe Methode/Funktion glaette() wie in
deskriptiv_plots.py und geglaettete_kurve.py): die 5 Gruppenlinien je Grafik sind bei den
monatlichen Rohwerten oft sehr zackig und ueberlagern sich schwer lesbar. Jede Linie wird
deshalb standardmaessig LOWESS-geglaettet; die rohen Periodenwerte werden zusaetzlich als
blasse Punkte eingezeichnet, sofern ZEIGE_ROHWERT_PUNKTE = True (Standard) - reine
Darstellungshilfe, die zugrunde liegende Kombinationsmatrix (Schritt 4) bleibt unveraendert.
GLAETTUNG_LOWESS_FRAC = 0/None schaltet die Glaettung ab (rohe Linie mit Punktmarkern wie
vor dieser Aenderung).

Laeuft direkt als Skript (sibling-Importe wie die anderen step6_auswertung-Dateien, kein -m):

    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe frage2_sensitivitaet_plots.py

(im Ordner src/youtube_code/step6_auswertung/ ausgefuehrt).
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy.stats.mstats import winsorize
from statsmodels.nonparametric.smoothers_lowess import lowess

from youtube_code.config import OUTPUTS
from deskriptiv_aggregation import lade_medientyp, lade_ideologie, GRANULARITAETEN as AGG_GRANULARITAETEN
from deskriptiv_plots import GRUPPE5_REIHENFOLGE

# =========================================================
# CONFIG
# =========================================================

GRANULARITAET = "monat"       # fix (siehe Docstring) - Kanal-Monat als Beobachtungseinheit
SPALTE_PERIODE = "rel_monat"
PERIODE_MIN = -12
PERIODE_MAX = 48
ACHSENLABEL = "Monat relativ zum Kriegsbeginn"

KANALFILTER = "beide_perioden"    # fix (siehe Docstring), keine weitere Variante

# Beide Winsorisierungsgrenzen parallel, je eigene Grafik (Nutzervorgabe).
WINSOR_GRENZEN = {"winsor_5_95": 0.05, "winsor_1_99": 0.01}

# Exponent fuer die gedaempfte Zellgewichtung A3 ("zellen_gewichtet"): Gewicht je Zelle =
# n_videos ** GEWICHT_EXPONENT. 0.5 = sqrt(n_videos) (Nutzervorgabe: gedaempft, NICHT linear
# proportional zur Videoanzahl - das waere rechnerisch identisch mit "video_ebene"/A2 gewesen).
GEWICHT_EXPONENT = 0.5

MIN_KANAELE_PRO_ZELLE = 5              # wie deskriptiv_plots.py::MIN_KANAELE_PRO_ZELLE
MIN_VIDEOS_PRO_ZELLE_VIDEOEBENE = 10   # zusaetzliche Mindestbesetzung fuer "video_ebene" (A2)

# Baseline fuer "index_vorkriegsmittel_mean"/"_median": dieselben Vorkriegsmonate und
# dieselbe Mindestbesetzung wie deskriptiv_aggregation.py (dort nur fuer
# MODUS="populismus" aktiv).
_MONAT_CFG = AGG_GRANULARITAETEN["monat"]
BASELINE_PERIODEN = _MONAT_CFG["baseline_perioden"]     # [-6, -5, -4, -3, -2, -1]
MIN_VIDEOS_BASELINE_GESAMT = 5

PFAD_VIDEO_EBENE = OUTPUTS / "segment_analysis" / "channel_video_erfolg.csv"
PFAD_SNAPSHOT = OUTPUTS / "segment_analysis" / "channel_erfolg_snapshot.csv"
PFAD_PLOTS = OUTPUTS / "segment_analysis" / "plots_sensitivitaet_frage2"
PFAD_METHODIK = PFAD_PLOTS / "frage2_sensitivitaet_methodik.md"

ABBILDUNG_GROESSE = (9, 5)
DPI = 150

# LOWESS-Glaettung der Gruppenlinien (dieselbe Methode/Funktion glaette() wie in
# deskriptiv_plots.py und geglaettete_kurve.py) - reine Darstellungshilfe gegen das
# Monat-zu-Monat-Zickzack bei den 5 ueberlagerten Gruppen5-Linien (siehe Docstring).
# None/0 = keine Glaettung (rohe Linie mit Punktmarkern wie bisher).
GLAETTUNG_LOWESS_FRAC = 0.15
# True (Standard) = zusaetzlich zur geglaetteten Linie die rohen Periodenwerte als kleine,
# blasse Punkte einzeichnen (Nachvollziehbarkeit); bei GLAETTUNG_LOWESS_FRAC = 0 wirkungslos,
# da die Linie dort bereits die rohen Werte mit Punktmarkern zeigt.
ZEIGE_ROHWERT_PUNKTE = True

# --- Kombinationsmatrix: Metrik -> Liste der Aggregationsebenen, die dafuer eine eigene ---
# --- Grafik bekommen (siehe Docstring, Abschnitt "Kombinationsmatrix"). ---
METRIK_AGGREGATIONSEBENEN = {
    # "mittelwert": ["zellen_ungewichtet", "video_ebene", "zellen_gewichtet"],
    "winsor_5_95": ["zellen_ungewichtet", "video_ebene", "zellen_gewichtet"],
    # "winsor_1_99": ["zellen_ungewichtet", "video_ebene", "zellen_gewichtet"],
    "median": ["zellen_ungewichtet", "video_ebene", "zellen_gewichtet"],
    "summe": ["zellen_ungewichtet", "gepoolt"],
}

# --- Ausgangsbasis: Anzeigename fuer y-Achse/Titel + ob die Metrik "Summe" dort sinnvoll ist ---
# Die beiden "index_vorkriegsmittel_*"-Eintraege unterscheiden sich NUR in der Baseline-
# Aggregation (siehe berechne_baseline()): "_mean" (Standard bisher) nimmt das arithmetische
# Mittel der Vorkriegsviews je Kanal, "_median" den Median. Bei rechtsschiefen View-
# Verteilungen (typisch fuer YouTube: viele Videos mit wenig Views, wenige virale
# Ausreisser) liegt der Mittelwert eines Kanals strukturell UEBER seinem Median-Video -
# dadurch landet die Metrik "median" bei "_mean"-Baseline systematisch unter 100, selbst
# wenn sich nichts veraendert hat (siehe Chatverlauf-Diagnose: bei OERR im Baseline-Fenster
# lag das Mittel je Kanal im Median bei 2,14x dem eigenen Kanal-Median). "_median" behebt
# das fuer die Metrik "median": Index=100 bedeutet dort "gleich wie das eigene mediane
# Vorkriegsvideo". Beide Varianten sind hier bewusst gleichzeitig aktiv fuer den direkten
# Vergleich; eine der beiden auskommentieren, um nur eine davon zu erzeugen.
BASIS_KONFIG = {
    "absolut": {"y_label": "Views (absolut)", "hat_summe": True,
                "titel": "absolute Views"},
    "index_vorkriegsmittel_mean": {"y_label": "Index (eigenes Vorkriegsmittel = 100)",
                                    "hat_summe": False, "titel": "Index (Vorkriegsmittel=100)",
                                    "baseline_aggregation": "mean"},
    "index_vorkriegsmittel_median": {"y_label": "Index (eigener Vorkriegs-Median = 100)",
                                      "hat_summe": False, "titel": "Index (Vorkriegsmedian=100)",
                                      "baseline_aggregation": "median"},
    # "subscriber_norm": {"y_label": "Views / Abonnenten", "hat_summe": False,
    #                      "titel": "Subscriber-normiert"},
}

# Welche Baseline-Aggregationen tatsaechlich berechnet werden muessen - automatisch aus den
# AKTIVEN BASIS_KONFIG-Eintraegen abgeleitet (kein separates Config-Flag noetig): wird ein
# "index_vorkriegsmittel_*"-Eintrag oben auskommentiert, entfaellt hier automatisch die
# zugehoerige (ungenutzte) Baseline-Berechnung in main().
BASELINE_AGGREGATIONEN = sorted({
    cfg["baseline_aggregation"] for cfg in BASIS_KONFIG.values() if "baseline_aggregation" in cfg
})

UMFAENGE = [("alle", "alle Videos"), ("topic", "nur Kriegsvideos (ist_kriegsvideo==1)")]


def _video_basis_fuer_umfang(basisdaten, umfang):
    """Filtert basisdaten nach Umfang - gemeinsame Stelle fuer main() (UMFAENGE-Schleife),
    erzeuge_kombinierte_grafiken() und main_todo0(), damit die Umfang-Definition nicht an
    mehreren Stellen dupliziert ist. 'alle' = unveraendert, 'topic' = nur Kriegsvideos
    (ist_kriegsvideo == 1, wie in UMFAENGE), 'nicht_topic' = echte Nichtkriegsvideos
    (ist_kriegsvideo == 0) - NICHT Teil von UMFAENGE/der Sensitivitaetsmatrix oben
    (die vergleicht bewusst gegen 'alle'), sondern nur fuer main_todo0() gebraucht
    (.claude/Aufgaben.md TODO 0: Kriegs- vs. ECHTE Nichtkriegsvideos, keine Mischung)."""
    if umfang == "alle":
        return basisdaten
    if umfang == "topic":
        return basisdaten[basisdaten["ist_kriegsvideo"] == 1]
    if umfang == "nicht_topic":
        return basisdaten[basisdaten["ist_kriegsvideo"] == 0]
    raise ValueError(f"Unbekannter umfang {umfang!r} (nur 'alle'/'topic'/'nicht_topic').")


# --- .claude/Aufgaben.md TODO 0 ("Vorbereitung: Absolute Views (Summe, Median,
# winsorisierter Mittelwert) mit Kriegs- und Nicht-Kriegsvideos im Vergleich zur Baseline.
# Wie ist der allgemeine Trend?") - Nutzervorgabe: bewusst kurz gehalten, max. 3 Grafiken
# statt einer vollen Sensitivitaetsmatrix-Kombination. Eigener, schlanker Einstiegspunkt
# main_todo0() weiter unten nutzt dieselben Bausteine wie erzeuge_kombinierte_grafiken()
# (ergaenze_wert_video/baue_zellen/kombiniere/plotte_kombinierte_grafik), OHNE main() oder
# die KOMBI_*-Config oben zu beruehren - der bestehende plots_sensitivitaet_frage2/-Bestand
# bleibt unveraendert. "zellen_ungewichtet" ist die einzige Aggregationsebene, die fuer
# ALLE drei Metriken gueltig ist (siehe METRIK_AGGREGATIONSEBENEN: "summe" kennt nur
# "zellen_ungewichtet"/"gepoolt", nicht "video_ebene") - dadurch ein einheitlicher Aufruf
# fuer alle drei Grafiken ohne Sonderfall.
TODO0_METRIKEN = ["summe", "median", "winsor_5_95"]
TODO0_EBENE = "zellen_ungewichtet"
TODO0_BASIS = "absolut"
TODO0_HAUPTFOKUS_UMFANG = "topic"        # dicke Linie: Kriegsvideos
TODO0_VERGLEICHS_UMFANG = "nicht_topic"  # duenne Linie: ECHTE Nichtkriegsvideos (nicht "alle")


# --- Kombinierte Grafik: Kriegsvideos (Hauptfokus, dicke Linie) vs. alle Videos --------
# --- (Vergleich, duenne Linie) in EINER Grafik, je Gruppe5-Kategorie in derselben Farbe. ---
# Zusaetzlich zur Kombinationsmatrix oben: pro Spezifikation (Metrik x
# Aggregationsebene x Ausgangsbasis) entsteht EIN Plot mit 2 x 5 Linien (5 Gruppe5-
# Kategorien, je einmal dick fuer KOMBI_HAUPTFOKUS_UMFANG und einmal duenn/transparent
# fuer KOMBI_VERGLEICHS_UMFANG, jeweils gleiche Farbe) - so ist auf einen Blick sichtbar,
# ob ein Gruppentrend bei Kriegsvideos vom Gesamttrend des Kanals abweicht. Nutzt
# dieselben Bausteine wie die Matrix oben (ergaenze_wert_video/baue_zellen/kombiniere).
#
# Exakte Spezifikation (Nutzervorgabe): Median, video-Ebene, Index (Vorkriegsmittel=100).
# Alle drei Parameter sind LISTEN - das kartesische Produkt aus KOMBI_METRIKEN x
# KOMBI_AGGREGATIONSEBENEN x KOMBI_BASEN ergibt die tatsaechlich erzeugten Kombi-Grafiken,
# d.h. mehrere Spezifikationen lassen sich in einem Lauf erzeugen, indem man hier weitere
# Listeneintraege ergaenzt (z.B. KOMBI_METRIKEN = ["median", "winsor_5_95"]). Eine Basis
# aus KOMBI_BASEN, die nicht in BASIS_KONFIG aktiv ist, wird uebersprungen (Konsolenhinweis).
KOMBI_AKTIV = True
KOMBI_METRIKEN = ["winsor_5_95"]
KOMBI_AGGREGATIONSEBENEN = ["video_ebene"]
# Beide Baseline-Varianten (siehe BASIS_KONFIG) fuer den direkten Vergleich in einem Lauf -
# eine davon entfernen, um nur die andere zu erzeugen.
KOMBI_BASEN = ["index_vorkriegsmittel_mean"] # "index_vorkriegsmittel_median"
KOMBI_HAUPTFOKUS_UMFANG = "topic"   # dicke Linie - Hauptfokus laut Nutzervorgabe: Kriegsvideos
KOMBI_VERGLEICHS_UMFANG = "alle"    # duenne, transparente Linie - Vergleichswert: alle Videos
KOMBI_HAUPTFOKUS_LINIENBREITE = 2.4
KOMBI_VERGLEICHS_LINIENBREITE = 1.0
KOMBI_VERGLEICHS_ALPHA = 0.55


# =========================================================
# SCHRITT 1: Basisdaten
# =========================================================

def baue_gruppe5_lokal(df):
    """Lokale Nachbildung von deskriptiv_plots.py::baue_gruppe5() - dieselbe Logik, dieselbe
    Kategorienliste (GRUPPE5_REIHENFOLGE wird von dort importiert, damit beide Skripte
    garantiert dieselben fuenf Gruppen verwenden): OERR und Traditionelles Medium bleiben als
    Ganzes, Alternatives Medium wird nach Ideologie in links/mitte/rechts aufgespalten.
    Politiker/Partei sowie Alternative-Medium-Kanaele ohne Ideologie-Einordnung fallen raus."""
    df = df.copy()
    ist_alt = df["medientyp"] == "Alternatives Medium"
    df["gruppe5"] = df["medientyp"]
    df.loc[ist_alt, "gruppe5"] = "Alternative Medien (" + df.loc[ist_alt, "ideologie_gruppe"].astype(str) + ")"

    vor = df["channel_id"].nunique()
    df = df[df["gruppe5"].isin(GRUPPE5_REIHENFOLGE)]
    nach = df["channel_id"].nunique()
    if nach < vor:
        print(f"[Gruppe5] {vor - nach} Kanaele ausgeschlossen (Politiker/Partei oder "
              f"Alternatives Medium ohne Ideologie-Einordnung).")
    return df


def lade_basisdaten():
    """Liest channel_video_erfolg.csv (Video-Ebene), ergaenzt medientyp/ideologie_gruppe
    (dieselben Ladefunktionen wie deskriptiv_aggregation.py) und die Abonnentenzahl aus
    channel_erfolg_snapshot.csv, bildet gruppe5 und filtert auf Kanaele mit gueltiger
    gruppe5-Zuordnung."""
    df = pd.read_csv(PFAD_VIDEO_EBENE)
    df["channel_id"] = df["channel_id"].astype(str)

    med = lade_medientyp()
    ideo = lade_ideologie()
    df = df.merge(med, on="channel_id", how="left").merge(ideo, on="channel_id", how="left")

    snapshot = pd.read_csv(PFAD_SNAPSHOT)
    snapshot["channel_id"] = snapshot["channel_id"].astype(str)
    df = df.merge(snapshot[["channel_id", "subscribers"]], on="channel_id", how="left")

    df = baue_gruppe5_lokal(df)
    df = df[(df[SPALTE_PERIODE] >= PERIODE_MIN) & (df[SPALTE_PERIODE] <= PERIODE_MAX)]
    print(f"[Basisdaten] {len(df)} Videos, {df['channel_id'].nunique()} Kanaele mit "
          f"gueltiger gruppe5-Zuordnung.")
    return df


def filtere_kanalfilter_beide_perioden(df):
    """KANALFILTER = 'beide_perioden' (fix, siehe Docstring): nur Kanaele mit mindestens
    einem Video vor UND mindestens einem Video ab Kriegsbeginn - wie
    kanaele_mit_beiden_perioden() in deskriptiv_plots.py, hier direkt auf der kompletten
    Video-Ebene (ALLE Videos, VOR dem Umfang-Split alle/nur Kriegsvideos) angewendet, damit
    der Kanalbestand fuer alle Grafiken der Matrix identisch ist."""
    vor_kanaele = set(df.loc[df[SPALTE_PERIODE] < 0, "channel_id"])
    nach_kanaele = set(df.loc[df[SPALTE_PERIODE] >= 0, "channel_id"])
    kanaele = vor_kanaele & nach_kanaele

    n_vor = df["channel_id"].nunique()
    df = df[df["channel_id"].isin(kanaele)]
    print(f"[Kanalfilter=beide_perioden] {n_vor} -> {df['channel_id'].nunique()} Kanaele "
          f"(mindestens ein Vor- UND ein Nachkriegsvideo).")
    return df


def berechne_baseline(df, aggregation="mean"):
    """Vorkriegs-Baseline von view_count je Kanal ueber BASELINE_PERIODEN (dieselben
    Vorkriegsmonate wie deskriptiv_aggregation.py::GRANULARITAETEN['monat']
    ['baseline_perioden']), inkl. Mindestanzahl-Filter MIN_VIDEOS_BASELINE_GESAMT. Wird
    IMMER aus ALLEN Videos des Kanals im Baseline-Fenster berechnet (nicht nur
    Topic-Videos) - konsistent mit dem Grundsatz in prepare_success_metrics.py, dass die
    Vorkriegsperiode alle Videos enthaelt; unabhaengig vom spaeter gewaehlten Umfang
    (alle/nur Kriegsvideos).

    aggregation: "mean" (Standard, arithmetisches Mittel) oder "median" - siehe
    BASIS_KONFIG/BASELINE_AGGREGATIONEN. "mean" ist bei rechtsschiefen View-Verteilungen
    (typisch fuer YouTube) strukturell HOEHER als das mediane Vorkriegsvideo eines Kanals,
    wodurch die Metrik "median" auf dieser Basis systematisch unter Index=100 landet, auch
    ohne echte Veraenderung (siehe Chatverlauf-Diagnose zu OERR). "median" liefert dagegen
    eine mit der Metrik "median" konsistente Referenz (Index=100 = "gleich wie das eigene
    mediane Vorkriegsvideo").

    Gibt ein channel_id -> baseline-Mapping zurueck; Kanaele ohne gueltige Baseline fehlen
    im Mapping (map() liefert dafuer NaN, ergaenze_wert_video() droppt diese Zeilen
    anschliessend)."""
    if aggregation not in ("mean", "median"):
        raise ValueError(f"Unbekannte aggregation {aggregation!r} (nur 'mean'/'median').")
    basis = df[df[SPALTE_PERIODE].isin(BASELINE_PERIODEN)]
    ref = basis.groupby("channel_id", as_index=False).agg(
        baseline=("view_count", aggregation),
        n_baseline_videos=("view_count", "size"),
    )
    n_vor = ref["channel_id"].nunique()
    ref = ref[ref["n_baseline_videos"] >= MIN_VIDEOS_BASELINE_GESAMT]
    print(f"[Baseline={aggregation}] {n_vor} -> {ref['channel_id'].nunique()} Kanaele mit "
          f"gueltiger Vorkriegs-Baseline (>= {MIN_VIDEOS_BASELINE_GESAMT} Videos in "
          f"{SPALTE_PERIODE}={BASELINE_PERIODEN}).")
    return dict(zip(ref["channel_id"], ref["baseline"]))


# =========================================================
# SCHRITT 2: Ausgangsbasis anwenden + Kanal-Monats-Zellen bilden
# =========================================================

def ergaenze_wert_video(df, basis, baseline_maps, subscriber_map, kontext=""):
    """Fuegt die Spalte 'wert' hinzu - view_count fuer basis='absolut', view_count/
    baseline*100 fuer basis='index_vorkriegsmittel_mean'/'index_vorkriegsmittel_median'
    (baseline aus berechne_baseline(), passende Aggregation ueber
    BASIS_KONFIG[basis]['baseline_aggregation'] aus baseline_maps ausgewaehlt - siehe
    BASELINE_AGGREGATIONEN), view_count/subscribers fuer basis='subscriber_norm' (Snapshot
    aus channel_erfolg_snapshot.csv, LIMITATION siehe Moduldocstring). Kanaele ohne
    gueltige Baseline bzw. ohne Eintrag/mit subscribers <= 0 bekommen 'wert' = NaN und
    werden anschliessend gedroppt (siehe Aufrufer)."""
    df = df.copy()
    basis_cfg = BASIS_KONFIG.get(basis, {})
    if basis == "absolut":
        df["wert"] = df["view_count"]
    elif "baseline_aggregation" in basis_cfg:
        baseline_map = baseline_maps[basis_cfg["baseline_aggregation"]]
        baseline = df["channel_id"].map(baseline_map)
        df["wert"] = df["view_count"] / baseline * 100
    elif basis == "subscriber_norm":
        subs = df["channel_id"].map(subscriber_map)
        gueltig = subs.notna() & (subs > 0)
        df["wert"] = np.where(gueltig, df["view_count"] / subs, np.nan)
    else:
        raise ValueError(f"Unbekannte basis {basis!r}.")

    n_ohne = df.loc[df["wert"].isna(), "channel_id"].nunique()
    if n_ohne:
        print(f"[Basis={basis}][{kontext}] {n_ohne} Kanaele ohne gueltigen Wert -> "
              f"ausgeschlossen.")
    return df.dropna(subset=["wert"])


def baue_zellen(df):
    """Kanal x Monat-Zellen aus der basis-transformierten Video-Tabelle (Spalte 'wert',
    siehe ergaenze_wert_video()): wert_mean/wert_summe/n_videos je Kanal-Monat, plus
    gruppe5 (kanalkonstant - genau eine Auspraegung je Kanal-Monat)."""
    return df.groupby(["channel_id", "gruppe5", SPALTE_PERIODE], as_index=False).agg(
        wert_mean=("wert", "mean"),
        wert_summe=("wert", "sum"),
        n_videos=("wert", "size"),
    )


# =========================================================
# SCHRITT 3: Aggregationsbausteine (Winsorisierung, gewichteter Median)
# =========================================================

def winsorisiere(werte, grenze):
    """Wrapper um scipy.stats.mstats.winsorize: begrenzt die unteren und oberen `grenze`-
    Anteile (z.B. grenze=0.05 -> 5%/95%-Winsorisierung) auf den jeweiligen Perzentilwert,
    statt sie zu verwerfen. Bei < 4 Werten (zu wenig fuer eine sinnvolle Perzentilbildung)
    werden die Werte unveraendert zurueckgegeben."""
    werte = np.asarray(werte, dtype=float)
    if len(werte) < 4:
        return werte
    return np.asarray(winsorize(werte, limits=(grenze, grenze)), dtype=float)


def gewichteter_median(werte, gewichte):
    """Gewichteter Median ueber kumulierte Gewichte: (werte, gewichte) nach werte sortiert,
    Gewichte auf 1 normiert kumuliert, erster Wert zurueckgegeben, bei dem die kumulierte
    Gewichtssumme >= 0.5 erreicht wird. Gewichte sind hier immer n_videos ** GEWICHT_EXPONENT
    > 0 (siehe A3-Aggregationsebene)."""
    werte = np.asarray(werte, dtype=float)
    gewichte = np.asarray(gewichte, dtype=float)
    reihenfolge = np.argsort(werte)
    werte_sortiert = werte[reihenfolge]
    kumuliert = np.cumsum(gewichte[reihenfolge]) / gewichte.sum()
    idx = min(int(np.searchsorted(kumuliert, 0.5)), len(werte_sortiert) - 1)
    return werte_sortiert[idx]


def _mittelwert_funktion(werte, gewichte):
    return np.average(werte, weights=gewichte) if gewichte is not None else np.mean(werte)


def _median_funktion(werte, gewichte):
    return gewichteter_median(werte, gewichte) if gewichte is not None else np.median(werte)


def _winsor_funktion(grenze):
    def _f(werte, gewichte):
        wins = winsorisiere(werte, grenze)
        return np.average(wins, weights=gewichte) if gewichte is not None else np.mean(wins)
    return _f


# Metrik -> Funktion(werte, gewichte) -> Skalar. gewichte ist None fuer "zellen_ungewichtet"
# (A1) und "video_ebene" (A2), das Gewichtsarray n_videos ** GEWICHT_EXPONENT fuer
# "zellen_gewichtet" (A3) - siehe kombiniere(). Deckt den mathematischen Dedup aus dem
# Moduldocstring direkt ab: A1 winsorisiert/mittelt/medianisiert dieselben Zellmittel wie A3,
# aber ungewichtet, waehrend A2 auf den rohen Videowerten arbeitet.
_METRIK_FUNKTIONEN = {
    "mittelwert": _mittelwert_funktion,
    "winsor_5_95": _winsor_funktion(WINSOR_GRENZEN["winsor_5_95"]),
    "winsor_1_99": _winsor_funktion(WINSOR_GRENZEN["winsor_1_99"]),
    "median": _median_funktion,
}


# =========================================================
# SCHRITT 4: Kombinieren (Kernstueck der Matrix)
# =========================================================

def kombiniere(zellen_oder_videos, aggregationsebene, metrik, gruppen_spalte="gruppe5"):
    """Liefert je (Periode, Gruppe5) EINEN Wert, je nach aggregationsebene/metrik aus der
    Kombinationsmatrix (siehe Moduldocstring). 'zellen_oder_videos' ist entweder die
    Video-Tabelle (Spalte 'wert', fuer aggregationsebene='video_ebene') oder die
    Zellen-Tabelle aus baue_zellen() (Spalten wert_mean/wert_summe/n_videos, fuer
    'zellen_ungewichtet'/'zellen_gewichtet'/'gepoolt') - beide bereits basis-transformiert
    (siehe ergaenze_wert_video()). Wendet zusaetzlich die jeweilige Mindestbesetzung
    (MIN_KANAELE_PRO_ZELLE bzw. MIN_VIDEOS_PRO_ZELLE_VIDEOEBENE) an."""
    schluessel = [SPALTE_PERIODE, gruppen_spalte]
    df = zellen_oder_videos

    if metrik == "summe":
        if aggregationsebene == "zellen_ungewichtet":
            agg = df.groupby(schluessel, as_index=False).agg(
                wert=("wert_summe", "mean"), n_kanaele=("channel_id", "nunique"))
        elif aggregationsebene == "gepoolt":
            agg = df.groupby(schluessel, as_index=False).agg(
                wert=("wert_summe", "sum"), n_kanaele=("channel_id", "nunique"))
        else:
            raise ValueError(f"Metrik 'summe' kennt nur 'zellen_ungewichtet'/'gepoolt', "
                              f"nicht {aggregationsebene!r}.")
        return agg[agg["n_kanaele"] >= MIN_KANAELE_PRO_ZELLE]

    funktion = _METRIK_FUNKTIONEN[metrik]

    if aggregationsebene == "video_ebene":
        wertspalte, gewicht_spalte = "wert", None
    elif aggregationsebene == "zellen_ungewichtet":
        wertspalte, gewicht_spalte = "wert_mean", None
    elif aggregationsebene == "zellen_gewichtet":
        wertspalte, gewicht_spalte = "wert_mean", "n_videos"
    else:
        raise ValueError(f"Unbekannte aggregationsebene {aggregationsebene!r}.")

    zeilen = []
    for keys, g in df.groupby(schluessel):
        keys = keys if isinstance(keys, tuple) else (keys,)
        werte = g[wertspalte].to_numpy(dtype=float)
        gewichte = g[gewicht_spalte].to_numpy(dtype=float) ** GEWICHT_EXPONENT if gewicht_spalte else None
        zeilen.append({
            **dict(zip(schluessel, keys)),
            "wert": funktion(werte, gewichte),
            "n_kanaele": g["channel_id"].nunique(),
            "n_zeilen": len(g),
        })
    agg = pd.DataFrame(zeilen)
    if agg.empty:
        return agg

    agg = agg[agg["n_kanaele"] >= MIN_KANAELE_PRO_ZELLE]
    if aggregationsebene == "video_ebene":
        agg = agg[agg["n_zeilen"] >= MIN_VIDEOS_PRO_ZELLE_VIDEOEBENE]
    return agg


# =========================================================
# SCHRITT 5: Plotten
# =========================================================

def glaette(x, y):
    """LOWESS-Glaettung einer einzelnen Gruppenlinie - identische Funktion wie
    deskriptiv_plots.py::glaette() (siehe GLAETTUNG_LOWESS_FRAC). Gibt bei zu wenigen
    Punkten oder deaktivierter Glaettung die rohen Werte unveraendert zurueck.

    it=0 (keine robustifizierenden Iterationen): statsmodels' lowess() gewichtet per
    Standard (it=3) Punkte mit grossem Residuum ueber mehrere Iterationen zusaetzlich
    herunter (Ausreisser-Robustheit) - bei einem lokalen Fenster mit einem extremen
    Ausreisser-Block (z.B. "Alternative Medien (rechts)" bei view_count-Indexwerten,
    Monate mit einzelnen viralen Videos) koennen dabei ALLE Gewichte im Fenster auf ~0
    kollabieren, die gewichtete Regression wird singulaer und lowess() liefert NaN
    zurueck - matplotlib zeichnet durch NaN-Punkte keine Linie, sichtbar als Luecke in
    der Kurve. it=0 verhindert das (reine ungewichtete lokale Regression je Fenster,
    keine Robustifizierung) und ist fuer die hier ohnehin schon winsorisierten/
    gemittelten Zeitreihen ausreichend."""
    if not GLAETTUNG_LOWESS_FRAC or len(x) < 4:
        return y
    return lowess(y, x, frac=GLAETTUNG_LOWESS_FRAC, xvals=x, return_sorted=False, it=0)


def plotte_kombination(werte_df, dateiname, titel, y_label, gruppen_liste=None,
                        gruppen_spalte="gruppe5", pfad_plots=None):
    """Eine Grafik, eine Linie je Eintrag in gruppen_liste (Default None -> GRUPPE5_REIHENFOLGE,
    Spalte gruppen_spalte, Default "gruppe5" - beide Parameter seit 2026-09-10 ergaenzt, damit
    andere Skripte diese Funktion per echtem Import auch mit einer eigenen, konfigurierbaren
    Gruppenliste/-spalte wiederverwenden koennen, z.B. marktanteil_themen_plots.py mit
    Themen/Szenarien statt Gruppe5-Kategorien als "Linien"), Kriegsbeginn-Referenzlinie bei
    Periode -0.5 (wie deskriptiv_plots.py), keine 95%-CI-Baender und keine
    Ereignis-Marker (siehe Moduldocstring). Jede Linie wird ueber glaette() LOWESS-
    geglaettet (GLAETTUNG_LOWESS_FRAC); bei aktiver Glaettung ohne Punktmarker auf der
    Linie selbst, die rohen Periodenwerte werden stattdessen als blasse Punkte
    eingezeichnet (ZEIGE_ROHWERT_PUNKTE). Bei GLAETTUNG_LOWESS_FRAC = 0 identisch zum
    bisherigen Verhalten (rohe Linie mit Punktmarkern). pfad_plots (Default: das PFAD_PLOTS
    dieses Moduls) - seit 2026-09-10 ergaenzt, analog zu plotte_kombinierte_grafik(), damit
    importierende Skripte ihre PNGs in einen eigenen Ordner statt plots_sensitivitaet_frage2/
    schreiben koennen."""
    if gruppen_liste is None:
        gruppen_liste = GRUPPE5_REIHENFOLGE
    if pfad_plots is None:
        pfad_plots = PFAD_PLOTS
    if werte_df.empty:
        print(f"[Skip] {dateiname}: keine Zelle erreicht die Mindestbesetzung.")
        return False

    fig, ax = plt.subplots(figsize=ABBILDUNG_GROESSE)
    gezeichnet = False
    for g in gruppen_liste:
        reihe = werte_df[werte_df[gruppen_spalte] == g].sort_values(SPALTE_PERIODE)
        if reihe.empty:
            continue
        x = reihe[SPALTE_PERIODE].to_numpy(dtype=float)
        y = reihe["wert"].to_numpy(dtype=float)
        y_glatt = glaette(x, y)

        if GLAETTUNG_LOWESS_FRAC:
            linie, = ax.plot(x, y_glatt, linewidth=2.2, label=g)
            if ZEIGE_ROHWERT_PUNKTE:
                ax.scatter(x, y, s=14, color=linie.get_color(), alpha=0.35, zorder=3)
        else:
            ax.plot(x, y_glatt, marker="o", markersize=3, linewidth=1.8, label=g)
        gezeichnet = True

    if not gezeichnet:
        print(f"[Skip] {dateiname}: keine Gruppe5-Kategorie mit Daten.")
        plt.close(fig)
        return False

    ax.axvline(-0.5, color="black", linestyle="--", linewidth=1)
    ax.text(-0.45, ax.get_ylim()[1], " Kriegsbeginn", va="top", fontsize=8)
    ax.set_xlabel(ACHSENLABEL)
    ax.set_ylabel(y_label)
    ax.set_title(titel)
    ax.legend(fontsize=7)
    fig.tight_layout()

    pfad_plots.mkdir(parents=True, exist_ok=True)
    pfad = pfad_plots / dateiname
    fig.savefig(pfad, dpi=DPI)
    plt.close(fig)
    print(f"[Plot] {pfad}")
    return True


def plotte_kombinierte_grafik(werte_hauptfokus, werte_vergleich, dateiname, titel, y_label,
                               hauptfokus_label=None, vergleichs_label=None, pfad_plots=None,
                               gruppen_liste=None, gruppen_spalte="gruppe5"):
    """Eine Grafik, 2 x len(gruppen_liste) Linien: je Eintrag in gruppen_liste (Default None ->
    GRUPPE5_REIHENFOLGE, Spalte gruppen_spalte, Default "gruppe5" - beide Parameter seit
    2026-09-10 ergaenzt, analog zu plotte_kombination(), damit z.B. marktanteil_themen_plots.py
    diese Funktion per echtem Import mit einer eigenen, konfigurierbaren Anzeigegruppenliste
    statt der festen Gruppe5-Kategorien aufrufen kann) eine dicke Linie fuer den Hauptfokus
    und eine duenne, transparente Linie in DERSELBEN Farbe fuer den Vergleichswert - direkter
    visueller Vergleich, ob der Gruppentrend beim Hauptfokus vom Vergleichstrend abweicht.
    Beide Linien werden wie in plotte_kombination() ueber glaette() LOWESS-geglaettet. Die
    Legende oben links nennt nur die Gruppen (Farbe), eine zweite Legende unten
    rechts erklaert die Linienstaerke (dick/duenn) ueber hauptfokus_label/vergleichs_label
    (Default: KOMBI_HAUPTFOKUS_UMFANG/KOMBI_VERGLEICHS_UMFANG - so bleibt der bestehende
    Aufruf aus erzeuge_kombinierte_grafiken() unveraendert; main_todo0() uebergibt eigene
    Labels ('Kriegsvideos'/'Nichtkriegsvideos'), da dort andere Umfaenge verglichen werden).
    pfad_plots (Default: das PFAD_PLOTS dieses Moduls, plots_sensitivitaet_frage2/) steuert den
    Speicherort - wird als echter Import in ANDEREN Dateien wiederverwendet (z.B.
    frage4_kriegspraemie_marktanteil_plots.py, marktanteil_themen_plots.py), die ihre PNGs in
    einen eigenen Ordner schreiben wollen; ohne diesen Parameter wuerde die Grafik sonst am
    modulinternen PFAD_PLOTS dieser Datei landen, nicht am PFAD_PLOTS des aufrufenden Skripts
    (Python loest globale Namen einer importierten Funktion immer im DEFINIERENDEN Modul auf,
    nicht im aufrufenden)."""
    if hauptfokus_label is None:
        hauptfokus_label = KOMBI_HAUPTFOKUS_UMFANG
    if vergleichs_label is None:
        vergleichs_label = KOMBI_VERGLEICHS_UMFANG
    if pfad_plots is None:
        pfad_plots = PFAD_PLOTS
    if gruppen_liste is None:
        gruppen_liste = GRUPPE5_REIHENFOLGE

    if werte_hauptfokus.empty and werte_vergleich.empty:
        print(f"[Skip] {dateiname}: keine Zelle erreicht die Mindestbesetzung "
              f"(weder Hauptfokus={hauptfokus_label} noch Vergleich={vergleichs_label}).")
        return False

    fig, ax = plt.subplots(figsize=ABBILDUNG_GROESSE)
    farbzyklus = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    gezeichnet = False

    for i, g in enumerate(gruppen_liste):
        farbe = farbzyklus[i % len(farbzyklus)]

        reihe_vergleich = werte_vergleich[werte_vergleich[gruppen_spalte] == g].sort_values(SPALTE_PERIODE)
        if not reihe_vergleich.empty:
            x = reihe_vergleich[SPALTE_PERIODE].to_numpy(dtype=float)
            y = glaette(x, reihe_vergleich["wert"].to_numpy(dtype=float))
            ax.plot(x, y, color=farbe, linewidth=KOMBI_VERGLEICHS_LINIENBREITE,
                    alpha=KOMBI_VERGLEICHS_ALPHA, zorder=2)

        reihe_haupt = werte_hauptfokus[werte_hauptfokus[gruppen_spalte] == g].sort_values(SPALTE_PERIODE)
        if not reihe_haupt.empty:
            x = reihe_haupt[SPALTE_PERIODE].to_numpy(dtype=float)
            y = glaette(x, reihe_haupt["wert"].to_numpy(dtype=float))
            ax.plot(x, y, color=farbe, linewidth=KOMBI_HAUPTFOKUS_LINIENBREITE, label=g, zorder=3)
            gezeichnet = True

    if not gezeichnet:
        print(f"[Skip] {dateiname}: keine Gruppe5-Kategorie mit Hauptfokus-Daten "
              f"({hauptfokus_label}).")
        plt.close(fig)
        return False

    ax.axvline(-0.5, color="black", linestyle="--", linewidth=1)
    ax.text(-0.45, ax.get_ylim()[1], " Kriegsbeginn", va="top", fontsize=8)
    ax.set_xlabel(ACHSENLABEL)
    ax.set_ylabel(y_label)
    ax.set_title(titel)

    gruppen_legende = ax.legend(fontsize=7, loc="upper left")
    ax.add_artist(gruppen_legende)
    linienart_handles = [
        Line2D([0], [0], color="grey", linewidth=KOMBI_HAUPTFOKUS_LINIENBREITE,
               label=f"dick = {hauptfokus_label}"),
        Line2D([0], [0], color="grey", linewidth=KOMBI_VERGLEICHS_LINIENBREITE,
               alpha=KOMBI_VERGLEICHS_ALPHA, label=f"duenn = {vergleichs_label}"),
    ]
    ax.legend(handles=linienart_handles, fontsize=7, loc="lower right")
    fig.tight_layout()

    pfad_plots.mkdir(parents=True, exist_ok=True)
    pfad = pfad_plots / dateiname
    fig.savefig(pfad, dpi=DPI)
    plt.close(fig)
    print(f"[Plot][Kombi] {pfad}")
    return True


def erzeuge_kombinierte_grafiken(basisdaten, baseline_maps, subscriber_map):
    """Erzeugt fuer jede Kombination aus KOMBI_METRIKEN x KOMBI_AGGREGATIONSEBENEN x
    KOMBI_BASEN eine kombinierte Grafik (siehe plotte_kombinierte_grafik()). Cached
    video_df/zellen_df je (basis, umfang), damit bei mehreren Metriken/Aggregations-
    ebenen in den Config-Listen nicht mehrfach dieselbe Basistransformation laeuft.
    Gibt die Liste der erzeugten Dateinamen zurueck (leer, wenn KOMBI_AKTIV=False)."""
    if not KOMBI_AKTIV:
        return []

    cache = {}

    def hole_werte(basis, umfang, metrik, ebene):
        schluessel = (basis, umfang)
        if schluessel not in cache:
            video_basis = _video_basis_fuer_umfang(basisdaten, umfang)
            video_df = ergaenze_wert_video(video_basis, basis, baseline_maps, subscriber_map,
                                            kontext=f"{basis}/{umfang}/kombi")
            cache[schluessel] = (video_df, baue_zellen(video_df))
        video_df, zellen_df = cache[schluessel]
        quelle = video_df if ebene == "video_ebene" else zellen_df
        return kombiniere(quelle, ebene, metrik)

    erzeugt = []
    for basis in KOMBI_BASEN:
        basis_cfg = BASIS_KONFIG.get(basis)
        if basis_cfg is None:
            print(f"[Kombi][Skip] Basis {basis!r} ist nicht (mehr) in BASIS_KONFIG aktiv.")
            continue
        for metrik in KOMBI_METRIKEN:
            if metrik == "summe" and not basis_cfg["hat_summe"]:
                print(f"[Kombi][Skip] Metrik 'summe' fuer Basis {basis!r} nicht sinnvoll "
                      "(siehe BASIS_KONFIG['hat_summe']).")
                continue
            for ebene in KOMBI_AGGREGATIONSEBENEN:
                werte_haupt = hole_werte(basis, KOMBI_HAUPTFOKUS_UMFANG, metrik, ebene)
                werte_vergleich = hole_werte(basis, KOMBI_VERGLEICHS_UMFANG, metrik, ebene)

                dateiname = (f"erfolg_kombi_{ebene}_{metrik}_{basis}_"
                             f"{KOMBI_HAUPTFOKUS_UMFANG}-vs-{KOMBI_VERGLEICHS_UMFANG}_monat.png")
                titel = (f"{metrik} | {ebene} | {basis_cfg['titel']}\n"
                         f"dick={KOMBI_HAUPTFOKUS_UMFANG}, duenn={KOMBI_VERGLEICHS_UMFANG} "
                         f"({GRANULARITAET}, Kanalfilter={KANALFILTER})")
                if plotte_kombinierte_grafik(werte_haupt, werte_vergleich, dateiname, titel,
                                              basis_cfg["y_label"]):
                    erzeugt.append(dateiname)
    return erzeugt


# =========================================================
# SCHRITT 6: Methodik-Uebersichtsdatei
# =========================================================

def schreibe_methodik(erzeugte_dateien):
    """Schreibt frage2_sensitivitaet_methodik.md - Pflichtdokumentation fuer
    Vorher/Nachher-Vergleiche (siehe document-comparative-analysis-methodology). Enthaelt
    die Kombinationsmatrix, die exakten Formeln je Aggregationsebene, die
    Dedup-Begruendung sowie die Baseline- und Subscriber-Snapshot-Limitation."""
    zeilen = [
        "# Methodik: Sensitivitaetsanalyse Forschungsfrage 2 (Kanalerfolg)",
        "",
        "Diese Datei dokumentiert die Kombinationsmatrix hinter "
        "`frage2_sensitivitaet_plots.py` - siehe `.claude/plans/frage2_sensitivitaet_plots.md` "
        "fuer die vollstaendige Herleitung und den Modul-Docstring des Skripts fuer die "
        "genaue Implementierung.",
        "",
        "## Feste Eckdaten",
        "",
        f"- Granularitaet: `{GRANULARITAET}` (Kanal-Monat als Beobachtungseinheit).",
        f"- Kanalfilter: `{KANALFILTER}` - nur Kanaele mit mindestens einem Video vor UND "
        "mindestens einem Video ab Kriegsbeginn, einmalig auf der kompletten Video-Ebene "
        "angewendet (vor dem Umfang-Split alle/nur Kriegsvideos), damit alle Grafiken "
        "denselben Kanalbestand zugrunde legen.",
        f"- Mindestbesetzung: `MIN_KANAELE_PRO_ZELLE={MIN_KANAELE_PRO_ZELLE}` (alle "
        "Aggregationsebenen), zusaetzlich `MIN_VIDEOS_PRO_ZELLE_VIDEOEBENE="
        f"{MIN_VIDEOS_PRO_ZELLE_VIDEOEBENE}` fuer die Aggregationsebene 'video_ebene'.",
        f"- Gewichtsexponent A3 ('zellen_gewichtet'): `GEWICHT_EXPONENT={GEWICHT_EXPONENT}` "
        "-> Gewicht je Kanal-Monats-Zelle = `n_videos ** GEWICHT_EXPONENT` (Standard: "
        "sqrt(n_videos)) - bewusst gedaempft statt linear proportional zur Videoanzahl "
        "(linear waere rechnerisch identisch mit der Aggregationsebene 'video_ebene').",
        f"- Darstellung: `GLAETTUNG_LOWESS_FRAC={GLAETTUNG_LOWESS_FRAC}` (0/None = aus) - "
        "LOWESS-Glaettung jeder Gruppenlinie, reine Darstellungshilfe (dieselbe Methode wie "
        "deskriptiv_plots.py), die zugrunde liegende Kombinationsmatrix bleibt unveraendert. "
        f"Rohe Periodenwerte zusaetzlich als blasse Punkte, wenn "
        f"`ZEIGE_ROHWERT_PUNKTE={ZEIGE_ROHWERT_PUNKTE}`.",
        "",
        "## Aggregationsebenen",
        "",
        "| Kuerzel | Name | Formel |",
        "|---|---|---|",
        "| A1 | zellen_ungewichtet | Erst je Kanal x Monat eine Zelle (Mittelwert/Summe der "
        "Videos), dann UNGEWICHTETER Mittelwert/Median ueber die Kanaele. |",
        "| A2 | video_ebene | Keine Kanal-Monats-Zelle - alle Videos der Gruppe/Periode "
        "werden direkt gepoolt (= lineare Gewichtung nach n_videos). |",
        "| A3 | zellen_gewichtet | Wie A1, aber jede Zelle zaehlt mit Gewicht "
        "`n_videos ** GEWICHT_EXPONENT` beim Kombinieren ueber Kanaele. |",
        "",
        "## Metriken je Aggregationsebene (mathematischer Dedup)",
        "",
        "| Metrik | A1 | A2 | A3 | Grafiken |",
        "|---|---|---|---|---|",
        "| Mittelwert | ungewichteter Mittelwert der Zellmittel | Mittelwert der rohen "
        "Videowerte | gewichteter Mittelwert der Zellmittel | 3 |",
        "| Winsor. Mittelwert (5/95 UND 1/99) | Mittelwert der winsorisierten Zellmittel | "
        "Mittelwert der winsorisierten Videowerte | gewichteter Mittelwert derselben "
        "winsorisierten Zellmittel wie A1 | 3 x 2 = 6 |",
        "| Median | ungewichteter Median der Zellmittel | Median der rohen Videowerte | "
        "gewichteter Median der Zellmittel | 3 |",
        "| Summe | Mittelwert der Kanal-Monats-Summen ueber Kanaele | gepoolt (= "
        "Gesamtsumme aller Videos der Gruppe/Periode) | = A2 (identisch, keine Gewichtung "
        "bei einer Summe sinnvoll) | 2 |",
        "",
        "**Warum A2 und A3 bei der Summe identisch sind, sonst aber nicht**: Die gedaempfte "
        "(nicht lineare) A3-Gewichtung `n_videos ** 0.5` unterscheidet sich rechnerisch von "
        "A1 und A2 bei Mittelwert/Winsor/Median. Nur bei der Summe gibt es keinen "
        "Gewichtungs-Freiheitsgrad - eine Summe UEBER Kanaele ist immer die Gesamtsumme, "
        "unabhaengig davon, wie stark einzelne Kanaele gewichtet wuerden.",
        "",
        "-> 3 + 6 + 3 + 2 = **14 Grafiken** je (Ausgangsbasis x Umfang).",
        "",
        "## Kombinierte Grafik (Kriegsvideos dick vs. alle Videos duenn)",
        "",
        "Zusaetzlich zur Kombinationsmatrix oben erzeugt `erzeuge_kombinierte_grafiken()` je "
        "Eintrag im kartesischen Produkt aus `KOMBI_METRIKEN x KOMBI_AGGREGATIONSEBENEN x "
        "KOMBI_BASEN` EINE Grafik mit 2 x 5 Linien (5 Gruppe5-Kategorien, je einmal dick fuer "
        f"`KOMBI_HAUPTFOKUS_UMFANG={KOMBI_HAUPTFOKUS_UMFANG!r}` und einmal duenn/transparent "
        f"(Alpha={KOMBI_VERGLEICHS_ALPHA}) in DERSELBEN Farbe fuer "
        f"`KOMBI_VERGLEICHS_UMFANG={KOMBI_VERGLEICHS_UMFANG!r}`) - direkter visueller Vergleich, "
        "ob ein Gruppentrend bei Kriegsvideos vom Gesamttrend des Kanals abweicht. Aktuelle "
        f"Spezifikation (Nutzervorgabe): `KOMBI_METRIKEN={KOMBI_METRIKEN}`, "
        f"`KOMBI_AGGREGATIONSEBENEN={KOMBI_AGGREGATIONSEBENEN}`, `KOMBI_BASEN={KOMBI_BASEN}` "
        "-> Median, video-Ebene, Index (standardmaessig BEIDE Baseline-Varianten "
        "Vorkriegsmittel und -median in einem Lauf, siehe Abschnitt 'Ausgangsbasis' unten). "
        "Alle drei Parameter sind Listen im CONFIG-Block und lassen sich dort erweitern, um "
        "mehrere Spezifikationen in einem Lauf zu erzeugen. Dateinamen: "
        "`erfolg_kombi_<ebene>_<metrik>_<basis>_<hauptfokus>-vs-<vergleich>_monat.png`.",
        "",
        "## Ausgangsbasis",
        "",
        "- **absolut**: rohe `view_count`-Werte. 14 Grafiken (Summe eingeschlossen).",
        "- **index_vorkriegsmittel_mean** / **index_vorkriegsmittel_median**: "
        "`wert = view_count / baseline_kanal * 100`. `baseline_kanal` = Mittelwert "
        "(`_mean`) bzw. Median (`_median`) von `view_count` ueber ALLE Videos des Kanals "
        f"(nicht nur Topic-Videos) in den Vorkriegsmonaten {BASELINE_PERIODEN} "
        f"(`{SPALTE_PERIODE}`), mit Mindestbesetzung "
        f"`MIN_VIDEOS_BASELINE_GESAMT={MIN_VIDEOS_BASELINE_GESAMT}`. Kanaele ohne gueltige "
        "Baseline fallen aus dieser Basis komplett raus (Konsolenausgabe beim Skriptlauf "
        "zeigt die Anzahl). **Warum zwei Varianten**: Bei rechtsschiefen View-Verteilungen "
        "(typisch fuer YouTube) liegt der Mittelwert eines Kanals strukturell UEBER seinem "
        "Median-Video - die Metrik 'median' landet auf `_mean`-Basis dadurch systematisch "
        "unter Index=100, selbst OHNE echte Veraenderung (Diagnosebeispiel: bei OERR lag "
        "das Kanal-Mittel im Baseline-Fenster im Median beim 2,14-fachen des jeweiligen "
        "Kanal-Medians). `_median` ist fuer die Metrik 'median' konsistent definiert "
        "(Index=100 = 'gleich wie das eigene mediane Vorkriegsvideo') und wird deshalb "
        "standardmaessig zusaetzlich zu `_mean` erzeugt, zum direkten Vergleich.",
        "- **subscriber_norm**: `wert = view_count / subscribers`. `subscribers` aus "
        "`channel_erfolg_snapshot.csv` (`prepare_success_metrics.py`). **Limitation**: dort "
        "steht nur ein EINMALIGER, aktueller Snapshot je Kanal (kein historischer Abo-Stand "
        "zum jeweiligen Video-Zeitpunkt) - derselbe (heutige) Abonnentenwert wird fuer ALLE "
        "Perioden des Kanals verwendet. Kanaele ohne Eintrag/mit `subscribers <= 0` fallen "
        "raus.",
        "- Bei beiden normierten Basen entfaellt die Metrik 'Summe' (Summe von "
        "Verhaeltniszahlen ist nicht sinnvoll interpretierbar) -> je 14 - 2 = **12 "
        "Grafiken**.",
        "",
        "## Umfang",
        "",
        "- **alle**: alle Videos des Kanals im Periodenfenster.",
        "- **topic**: nur Kriegsvideos (`ist_kriegsvideo == 1`, Topic `russia_ukraine_war`, "
        "wie `NUR_TOPICVIDEOS` in `deskriptiv_plots.py`).",
        "",
        "## Gesamtzahl",
        "",
        "(14 absolut + 12 Index-Mittel + 12 Index-Median + 12 Subscriber-Norm) x 2 Umfaenge "
        "= **100 Liniendiagramme** im theoretischen Vollausbau (alle BASIS_KONFIG-Eintraege "
        "aktiv, je 5 Linien, eine je Gruppe5-Kategorie: OERR, Traditionelles Medium, "
        "Alternative Medien links/mitte/rechts - Politiker/Partei ausgeschlossen, siehe "
        "`baue_gruppe5_lokal()`). Standardmaessig sind nur die beiden Index-Basen aktiv "
        "(`absolut`/`subscriber_norm` auskommentiert), siehe tatsaechliche Anzahl unten.",
        "",
        f"## Tatsaechlich erzeugte Grafiken bei diesem Lauf: {len(erzeugte_dateien)}",
        "",
        "(Kombinationsmatrix + kombinierte Grafik(en), siehe Dateinamenspraefix "
        "`erfolg_sensitivitaet_` bzw. `erfolg_kombi_`.)",
        "",
    ]
    for d in erzeugte_dateien:
        zeilen.append(f"- `{d}`")

    PFAD_PLOTS.mkdir(parents=True, exist_ok=True)
    with open(PFAD_METHODIK, "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen) + "\n")
    print(f"[Methodik] {PFAD_METHODIK}")


# =========================================================
# MAIN
# =========================================================

def main():
    basisdaten = lade_basisdaten()
    basisdaten = filtere_kanalfilter_beide_perioden(basisdaten)
    baseline_maps = {agg: berechne_baseline(basisdaten, aggregation=agg)
                      for agg in BASELINE_AGGREGATIONEN}

    snap = basisdaten.drop_duplicates("channel_id")
    subscriber_map = dict(zip(snap["channel_id"], snap["subscribers"]))

    erzeugte_dateien = []

    for umfang, umfang_label in UMFAENGE:
        video_basis = _video_basis_fuer_umfang(basisdaten, umfang)

        for basis, basis_cfg in BASIS_KONFIG.items():
            kontext = f"{basis}/{umfang}"
            video_df = ergaenze_wert_video(video_basis, basis, baseline_maps, subscriber_map,
                                            kontext=kontext)
            zellen_df = baue_zellen(video_df)

            for metrik, ebenen in METRIK_AGGREGATIONSEBENEN.items():
                if metrik == "summe" and not basis_cfg["hat_summe"]:
                    continue
                for ebene in ebenen:
                    quelle = video_df if ebene == "video_ebene" else zellen_df
                    werte_df = kombiniere(quelle, ebene, metrik)

                    dateiname = f"erfolg_sensitivitaet_{ebene}_{metrik}_{basis}_{umfang}_monat.png"
                    titel = (f"{metrik} | {ebene} | {basis_cfg['titel']} | {umfang_label}\n"
                             f"({GRANULARITAET}, Kanalfilter={KANALFILTER})")
                    if plotte_kombination(werte_df, dateiname, titel, basis_cfg["y_label"]):
                        erzeugte_dateien.append(dateiname)

    print(f"\n[Fertig] {len(erzeugte_dateien)} Grafiken der Kombinationsmatrix erzeugt "
          f"(theoretischer Vollausbau: 100, siehe Moduldocstring) -> {PFAD_PLOTS}")

    kombi_dateien = erzeuge_kombinierte_grafiken(basisdaten, baseline_maps, subscriber_map)
    if kombi_dateien:
        print(f"[Fertig] {len(kombi_dateien)} kombinierte Grafik(en) "
              f"({KOMBI_HAUPTFOKUS_UMFANG} dick vs. {KOMBI_VERGLEICHS_UMFANG} duenn) erzeugt "
              f"-> {PFAD_PLOTS}")
    erzeugte_dateien = erzeugte_dateien + kombi_dateien

    schreibe_methodik(erzeugte_dateien)


def main_todo0():
    """.claude/Aufgaben.md TODO 0 - siehe Konfigurationsblock TODO0_* oben fuer die
    Herleitung. Erzeugt genau 3 Grafiken (Summe/Median/winsorisierter Mittelwert 5/95,
    absolute Views, zellen_ungewichtet), je Kriegsvideos (dick) vs. echte Nichtkriegsvideos
    (duenn), 5 Gruppe5-Linien. Kein eigenes Methodik-Dokument (Nutzervorgabe: kurz halten) -
    nur eine kurze Konsolen-Zusammenfassung. Separater Einstiegspunkt, NICHT Teil von
    main()/__main__ (siehe unten) - Aufruf:

        PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -c
            "from frage2_sensitivitaet_plots import main_todo0; main_todo0()"

    (im Ordner src/youtube_code/step6_auswertung/ ausgefuehrt, wie die anderen
    bare-sibling-Importe dieser Datei)."""
    basisdaten = lade_basisdaten()
    basisdaten = filtere_kanalfilter_beide_perioden(basisdaten)
    basis_cfg = BASIS_KONFIG[TODO0_BASIS]

    erzeugt = []
    for metrik in TODO0_METRIKEN:
        video_haupt = _video_basis_fuer_umfang(basisdaten, TODO0_HAUPTFOKUS_UMFANG)
        video_vergleich = _video_basis_fuer_umfang(basisdaten, TODO0_VERGLEICHS_UMFANG)
        df_haupt = ergaenze_wert_video(video_haupt, TODO0_BASIS, {}, {},
                                        kontext=f"todo0/{metrik}/{TODO0_HAUPTFOKUS_UMFANG}")
        df_vergleich = ergaenze_wert_video(video_vergleich, TODO0_BASIS, {}, {},
                                            kontext=f"todo0/{metrik}/{TODO0_VERGLEICHS_UMFANG}")
        werte_haupt = kombiniere(baue_zellen(df_haupt), TODO0_EBENE, metrik)
        werte_vergleich = kombiniere(baue_zellen(df_vergleich), TODO0_EBENE, metrik)

        dateiname = f"todo0_trend_{metrik}_{TODO0_HAUPTFOKUS_UMFANG}-vs-{TODO0_VERGLEICHS_UMFANG}_monat.png"
        titel = (f"{metrik} | {TODO0_EBENE} | {basis_cfg['titel']}\n"
                 f"dick=Kriegsvideos, duenn=Nichtkriegsvideos ({GRANULARITAET}, "
                 f"Kanalfilter={KANALFILTER})")
        if plotte_kombinierte_grafik(werte_haupt, werte_vergleich, dateiname, titel,
                                      basis_cfg["y_label"], hauptfokus_label="Kriegsvideos",
                                      vergleichs_label="Nichtkriegsvideos"):
            erzeugt.append(dateiname)

    print(f"\n[TODO 0] {len(erzeugt)} von {len(TODO0_METRIKEN)} Grafik(en) erzeugt -> {PFAD_PLOTS}")
    return erzeugt


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
deskriptiv_plots.py

Plottet die Ausgabe von deskriptiv_aggregation.py.

Zeigt fuer beide Modi die absoluten Rohwerte (wert_roh) im Zeitverlauf, KEINE
Baseline-Normierung (der Index_100 aus deskriptiv_aggregation.py wird hier
nicht mehr geplottet, siehe frage1_methodik_und_stichprobe.md Abschnitt 3c).
Beobachtungseinheit ist der Kanal-Monat (GRANULARITAET = "monat", Standard) -
ein Punkt je Kanal x Monat ist bereits der Mittelwert ueber alle Videos
dieses Kanals in diesem Monat (siehe prepare_channel_scores.py::
_kanal_periode_aus_video()); GRANULARITAET = "quartal" bleibt als Alternative
verfuegbar.

Aggregation ueber Kanaele: ungewichteter Mittelwert der Kanalwerte + 95%-CI.

plotte_dimension() erzeugt je Dimension IMMER zwei Plot-Varianten
(KANALFILTER_VARIANTEN): "alle" (jeder Kanal mit einem Wert in der jeweiligen
Periode, inkl. seit Kriegsbeginn neu dazugekommene Kanaele ohne
Vorkriegsfenster) und "beide_perioden" (nur Kanaele mit mindestens einem
Vor- UND einem Nachkriegswert - der within-Kanal-Vergleich). Dateiname traegt
die Variante als Suffix.

NUR_VORKRIEGS_KANAELE (Standard: False): globaler Zusatzfilter, der VOR allen
anderen Plot-Funktionen einmal auf den kompletten eingelesenen df angewendet wird
(siehe main() und filtere_vorkriegs_kanaele()) - behaelt nur Kanaele mit
mindestens einem Wert vor Kriegsbeginn (SPALTE_PERIODE < 0), unabhaengig davon,
ob derselbe Kanal auch nach Kriegsbeginn noch aktiv ist. Anders als
KANALFILTER_VARIANTEN = "beide_perioden" (das zusaetzlich einen Nachkriegswert
verlangt und nur die eine Plot-Variante betrifft) schliesst dieser Filter bei
True in JEDEM Plot dieses Skripts (auch der Variante "alle" sowie den
Gruppen5/Gruppe4-Uebersichten und der Index-Vorkriegsmonat-Variante) Kanaele
aus, die es vor Kriegsbeginn schlicht noch nicht gab.

Jede Gruppenlinie wird zusaetzlich LOWESS-geglaettet (GLAETTUNG_LOWESS_FRAC, dieselbe
Methode wie geglaettete_kurve.py) - reine Darstellungshilfe gegen das Perioden-zu-
Perioden-Zickzack, sobald mehrere Gruppen (Split) in einem Plot ueberlagert werden. Die
rohen Periodenmittel werden zusaetzlich als blasse Punkte eingezeichnet, sofern
ZEIGE_ROHWERT_PUNKTE = True (Standard); bei False zeigt jeder Plot NUR die geglaetteten
Linien. Die 95%-CI-Baender sind bei mehreren Gruppen standardmaessig aus (ZEIGE_CI =
False), da sie sich sonst schnell gegenseitig verdecken.

Zusaetzlich zur schwarzen Kriegsbeginn-Referenzlinie zeichnet jeder Plot fuer jedes
Ereignis aus EREIGNISSE eine duenne rote gepunktete senkrechte Linie samt gedrehter
Beschriftung ein (zeichne_ereignislinien(), Ereignisdatum -> Periode ueber
periode_aus_datum(), dieselbe tagesgenaue Logik wie prepare_channel_scores.py::
relativ_periode()). Ereignisse ausserhalb des jeweils dargestellten Periodenfensters
werden automatisch uebersprungen.

Granularitaet (Quartal/Monat) ueber GRANULARITAET waehlbar - muss zu der Datei
passen, die mit dieser Granularitaet in deskriptiv_aggregation.py erzeugt wurde
(deskriptiv_{modus}_{granularitaet}.csv).

MODUS = "erfolg" (Forschungsfrage 2, deskriptive Ergaenzung zu
frage2_erfolg_bericht.py): plottet dieselben Kanal x Periode-Erfolgsmetriken
(log_views, log_views_summe, engagement_rate, plus die rohen view_count/
view_count_summe als Zusatzkontext) wie deskriptiv_aggregation.py fuer
MODUS="erfolg" erzeugt - rohe Werte, KEINE Alters-Normalisierung und KEINE
Baseline-Index-Bildung (siehe dortiger Docstring und
prepare_success_metrics.py). Anders als bei "populismus"/"stance" enthalten
die Vorkriegsperioden hier ALLE Videos des Kanals (kein reines
Kriegsvideo-Sample), der Referenzstrich markiert daher nur den
Kriegsbeginn als Zeitpunkt, nicht einen Wechsel der Video-Grundgesamtheit.

NUR_TOPICVIDEOS (Standard: False, nur wirksam bei MODUS="erfolg", siehe
Forschungsfrage 4 in .claude/CLAUDE.md - "Betrifft das nur Kriegsvideos oder
auch andere Videos?"): schaltet die Eingabedatei auf deskriptiv_erfolg_
kriegsvideos_{granularitaet}.csv um (deskriptiv_aggregation.py::MODUS =
"erfolg_kriegsvideos", das seinerseits channel_{gran}_erfolg_kriegsvideos_
timeseries.csv aus prepare_success_metrics.py liest - dort auf Videos mit
ist_kriegsvideo == 1 gefiltert, VOR der Kanal x Periode-Aggregation, nicht
danach: die Info, welches Video ein Kriegsvideo ist, geht bei der
Aggregation zu Kanal x Periode verloren, ein Filtern auf der bereits
aggregierten deskriptiv_erfolg_{granularitaet}.csv ist also nicht moeglich).
Alle uebrigen Plot-Mechaniken (KANALFILTER_VARIANTEN, Gruppen4/5-Uebersichten,
Index-Vorkriegsmonat) bleiben unveraendert, nur mit weniger Videos je Zelle -
bei GRANULARITAET="monat" (Standard) sind Kriegsvideo-Zellen oft duenn besetzt,
GRANULARITAET="quartal" ist hier ggf. die robustere Wahl (vgl.
frage4_kriegsvideos_erfolg_bericht.py). Ausgabedateien tragen den Zusatz
"_kriegsvideos" im Dateinamen (MODUS_DATEI statt MODUS), damit sie die
Rohwert-Plots ueber ALLE Videos derselben Dimension nicht ueberschreiben.

ZUSATZ 4-Gruppen-Uebersicht (plotte_dimension_gruppe4, siehe dortige
Funktionsdocstring): fuer MODUS="erfolg" der primaere Blick auf die vier
Forschungsfrage-2-Vergleichsgruppen aus .claude/CLAUDE.md ("Unterschiede
zwischen rechten und linken Kanaelen") - ÖRR und Traditionelles Medium
bleiben zusammengefasst (zu klein/homogen fuer eine weitere Aufspaltung,
siehe baue_gruppe4()-Docstring), Alternatives Medium wird nach Ideologie in
links/mitte/rechts aufgespalten. Nutzt dieselbe Rendering-Logik
(_rendere_gruppenplot) wie die bestehende 5-Gruppen-Uebersicht
(plotte_dimension_gruppen5, ÖRR und Traditionelles Medium getrennt) fuer
Populismus/Stance.

ZUSATZVARIANTE Index letzter Vorkriegsmonat (plotte_dimension_index_vorkriegsmonat,
gesteuert ueber INDEX_LETZTER_VORKRIEGSMONAT_DIMENSIONEN, Standard: nur
"view_count"): abweichend vom sonstigen Rohwert-Prinzip dieses Skripts wird hier
JEDER Kanal auf seinen eigenen Wert in der letzten Vorkriegsperiode indexiert (= 100,
siehe ergaenze_index_letzter_vorkriegsmonat()) - macht die relative Steigung sichtbar,
unabhaengig vom absoluten Kanal-Niveau (bei der Summe der Views sonst durch
Groessenordnungsunterschiede zwischen Kanaelen verdeckt). Eigene Ausgabedatei
(Suffix "index_vorkriegsmonat"), die Rohwert-Varianten aus plotte_dimension() bleiben
fuer dieselbe(n) Dimension(en) unveraendert zusaetzlich bestehen. Dieselbe Indexbildung
gibt es zusaetzlich fuer die 5-Gruppen-Uebersicht (plotte_dimension_gruppen5_index_
vorkriegsmonat, Suffix "gruppen5_index_vorkriegsmonat", nur wenn GRUPPEN5_PLOTTEN aktiv
ist) - Rendering ueber dieselbe _rendere_gruppenplot()-Funktion wie plotte_dimension_
gruppen5()/plotte_dimension_gruppe4(), nur mit Referenzlinie bei 100 statt 0.

WICHTIG - Median statt Mittelwert fuer diese Index-Variante: Weil der Index jedes
Kanals auf dessen eigenem (haeufig sehr kleinem) Vorkriegswert basiert, reicht EIN
einzelner viraler Ausreisser, um den Index eines Kanals in Zehntausende Prozent zu
treiben und damit den GRUPPEN-Mittelwert komplett zu verzerren (Fallstudie: der Kanal
"LYDOM - Vulkan Studio" hatte im August 2023 ein Einzelvideo mit 54,7 Mio. Views bei
einer Vorkriegsbaseline von nur ~571 Views/Video -> Index ~300.000 % in diesem einen
Monat, dadurch schoss der Mittelwert der Gruppe "Alternative Medien (links)" von
~195 auf ~10.900 hoch, obwohl 27 der 28 Kanaele der Gruppe unauffaellig blieben; ein
zweiter Kanal, "Westend Verlag", verstaerkte denselben Effekt in einem Nachbarmonat
durch ein Einzelvideo in einem Monat mit nur einem Upload). Deshalb bilden
aggregiere(..., zentral="median") sowie plotte_dimension_index_vorkriegsmonat() und
plotte_dimension_gruppen5_index_vorkriegsmonat() (ueber _rendere_gruppenplot(...,
zentral="median")) hier den MEDIAN statt des Mittelwerts ueber die Kanaele je
Periode - robust gegen einzelne Extremwerte. Alle anderen Aggregationen in diesem
Skript (plotte_dimension(), plotte_dimension_gruppen5(), plotte_dimension_gruppe4())
bleiben beim ungewichteten Mittelwert, siehe deren Docstrings/Titeltext. Die CI-Baender
(ci_unten/ci_oben in aggregiere()) basieren weiterhin auf der klassischen
Standardfehler-Formel fuer den Mittelwert und sind fuer den Median nur eine grobe
Naeherung - unkritisch, da ZEIGE_CI fuer Mehrgruppen-Plots standardmaessig aus ist.
"""

import os
from itertools import cycle

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.nonparametric.smoothers_lowess import lowess

from youtube_code.config import OUTPUTS

# =========================================================
# CONFIG
# =========================================================

MODUS = "erfolg"              # "populismus" | "stance" | "erfolg"
GRANULARITAET = "monat"       # "quartal" | "monat" - muss zur eingelesenen deskriptiv_*.csv passen.
                               # "monat" = Kanal-Monat als Beobachtungseinheit (Standard, siehe Docstring).

# True = nur Kriegsvideos (ist_kriegsvideo == 1) statt aller Videos (Forschungsfrage 4, siehe
# Docstring) - nur zusammen mit MODUS = "erfolg" sinnvoll, main() bricht sonst mit ValueError ab.
# Setzt voraus, dass deskriptiv_aggregation.py vorher einmal mit "erfolg_kriegsvideos" in
# MODUS_LISTE gelaufen ist (deskriptiv_erfolg_kriegsvideos_{granularitaet}.csv).
NUR_TOPICVIDEOS = True

# Bestimmt Eingabedatei UND Praefix von Ausgabedateiname/Plot-Titel (siehe NUR_TOPICVIDEOS) -
# MODUS selbst bleibt fuer die inhaltliche Verzweigung (z.B. der Hinweistext in
# _plotte_dimension_variante()) auf "erfolg" stehen, nur der Datenursprung wechselt.
MODUS_DATEI = f"{MODUS}_kriegsvideos" if NUR_TOPICVIDEOS else MODUS

# --- Granularitaets-Definitionen (Periodenspalte, Fensterbereich, Achsenbeschriftung) ---
GRANULARITAETEN = {
    "quartal": {
        "spalte": "rel_quartal",
        "periode_min": -4,
        "periode_max": 18,
        "achsenlabel": "Quartal relativ zum Kriegsbeginn",
        "referenzlinie_text": "Kriegsbeginn",
    },
    "monat": {
        "spalte": "rel_monat",
        "periode_min": -12,
        "periode_max": 52,
        "achsenlabel": "Monat relativ zum Kriegsbeginn",
        "referenzlinie_text": "Kriegsbeginn",
    },
}

_GRAN_CFG = GRANULARITAETEN[GRANULARITAET]
SPALTE_PERIODE = _GRAN_CFG["spalte"]
PERIODE_MIN = _GRAN_CFG["periode_min"]
PERIODE_MAX = _GRAN_CFG["periode_max"]
ACHSENLABEL = _GRAN_CFG["achsenlabel"]

PFAD_EINGABE = OUTPUTS / "segment_analysis" / "deskriptiv_{modus}_{granularitaet}.csv"
PFAD_PLOTS = OUTPUTS / "segment_analysis" / "plots"

SPLIT = "ideologie"           # "keiner" | "medientyp" | "ideologie"

# Zwei Kanal-Varianten, die plotte_dimension() je Dimension IMMER beide erzeugt (siehe
# Docstring): "alle" = kein Zusatzfilter (alle Kanaele mit einem Wert in der jeweiligen
# Periode), "beide_perioden" = nur Kanaele mit mindestens einem Vor- UND einem
# Nachkriegswert. Werte hier sind Dateiname-Suffixe, keine Schalter.
KANALFILTER_VARIANTEN = ["alle", "beide_perioden"]

# True = in JEDEM Plot dieses Skripts (siehe Docstring) nur Kanaele zeigen, die schon
# VOR Kriegsbeginn mindestens einen Wert hatten - ein Nachkriegswert wird dafuer NICHT
# verlangt (anders als KANALFILTER_VARIANTEN = "beide_perioden"). Wird einmal global in
# main() angewendet (filtere_vorkriegs_kanaele()), bevor die einzelnen Plot-Funktionen
# ihre eigenen, dimensionsspezifischen Filter (KANALFILTER_VARIANTEN, Gruppe4/5, Index-
# Vorkriegsmonat) darauf aufsetzen.
NUR_VORKRIEGS_KANAELE = False

DIMENSIONEN_PLOTTEN = None    # None = alle; sonst z.B. ["populismus_gesamt", "antielitismus"]

MIN_KANAELE_PRO_ZELLE = 5     # Zellen mit weniger Kanaelen werden nicht geplottet
ZEIGE_CI = False               # bei mehreren Gruppen ueberlagern sich die Baender schnell -> Standard aus
ZEIGE_N = True                # n je Punkt in die Konsole schreiben
ZEIGE_ROHWERT_PUNKTE = False    # False = nur die geglaetteten Linien zeigen, keine rohen Periodenmittel als Punkte

# LOWESS-Glaettung der Gruppenlinien (dieselbe Methode wie in geglaettete_kurve.py),
# reine Darstellungshilfe gegen das Perioden-zu-Perioden-Zickzack bei mehreren
# ueberlagerten Gruppen - die rohen Periodenmittel werden zusaetzlich als kleine, blasse
# Punkte gezeigt, damit die zugrunde liegenden Werte nachvollziehbar bleiben.
# None/0 = keine Glaettung (rohe Linie wie bisher).
GLAETTUNG_LOWESS_FRAC = 0

GRUPPEN_REIHENFOLGE = None    # z.B. ["ÖRR", "Traditionelles Medium", "Alternatives Medium", "Politiker/Partei"]

ABBILDUNG_GROESSE = (9, 5)
DPI = 150

# --- Filterkombinationen: mehrere Dimensionen in EINER Grafik, gefiltert auf ---
# --- eine bestimmte Kanalgruppe (z.B. "rechte alternative Medien"). ---
# Liest denselben MODUS/GRANULARITAET-CSV wie oben; alle Dimensionen muessen also
# aus derselben deskriptiv_{modus}_{granularitaet}.csv stammen.
FILTERKOMBINATIONEN = [
    {
        "name": "rechte_alternative_medien",
        "filter": {"medientyp": ["Alternatives Medium"], "ideologie_gruppe": ["rechts"]},
        "dimensionen": ["position_russland", "position_westpolitik", "emotion"],
    },
]

# Dimensionen aus FILTERKOMBINATIONEN, die auf einer zweiten y-Achse (rechts) geplottet werden,
# weil ihre Skala nicht zu den uebrigen Dimensionen passt (z.B. Emotion 0-3 vs. Stance -2 bis +2).
SEKUNDAERACHSE_DIMENSIONEN = ["emotion", "emotionale_intensitaet", "populismus_gesamt"]

# Optionale feste Farbzuordnung je Dimension (matplotlib-Farbnamen oder Hex). Dimensionen
# ohne Eintrag bekommen automatisch die naechste freie Farbe aus einem gemeinsamen Zyklus,
# der ueber Haupt- und Sekundaerachse hinweg laeuft (verhindert zufaellige Farbkollisionen
# zwischen den beiden Achsen). Leer lassen fuer rein automatische Zuordnung.
DIMENSION_FARBEN = {}

# --- 5-Gruppen-Uebersicht (plotte_dimension_gruppen5): OERR/Traditionell bleiben ---
# --- als Ganzes, Alternatives Medium wird zusaetzlich nach Ideologie aufgespalten, ---
# --- Politiker/Partei wird ausgeschlossen. Siehe baue_gruppe5(). ---
GRUPPEN5_PLOTTEN = True      # True = main() erzeugt zusaetzlich je Dimension einen Gruppen5-Plot
GRUPPE5_REIHENFOLGE = [
    "ÖRR",
    "Traditionelles Medium",
    "Alternative Medien (links)",
    "Alternative Medien (mitte)",
    "Alternative Medien (rechts)",
]

# --- 4-Gruppen-Uebersicht (plotte_dimension_gruppe4): wie Gruppe5, aber OERR und ---
# --- Traditionelles Medium werden zu EINER Gruppe zusammengefasst (Nutzervorgabe fuer ---
# --- die Forschungsfrage-2-Erfolgsplots, siehe baue_gruppe4()). Politiker/Partei wird ---
# --- ausgeschlossen. Standardmaessig an (True), da dies die primaer angefragte ---
# --- Standardansicht fuer den aktuellen MODUS="erfolg" ist - bei Rueckwechsel auf ---
# --- MODUS="populismus"/"stance" ggf. wieder auf False setzen (dort ist GRUPPEN5_PLOTTEN ---
# --- die passendere Uebersicht, ÖRR/Traditionelles Medium getrennt). ---
GRUPPE4_PLOTTEN = True        # True = main() erzeugt zusaetzlich je Dimension einen Gruppe4-Plot
GRUPPE4_REIHENFOLGE = [
    "ÖRR + Traditionelle Medien",
    "Alternative Medien (links)",
    "Alternative Medien (mitte)",
    "Alternative Medien (rechts)",
]

# --- Ereignis-Marker: werden in JEDEN Plot als duenne rote gepunktete senkrechte ---
# --- Linie samt gedrehter Beschriftung eingezeichnet (siehe zeichne_ereignislinien()), ---
# --- zusaetzlich zur schwarzen Kriegsbeginn-Referenzlinie. Ereignisse ausserhalb des ---
# --- aktuell dargestellten Periodenfensters [PERIODE_MIN, PERIODE_MAX] werden je Plot ---
# --- automatisch uebersprungen. Datum -> Periode ueber KRIEGSBEGINN, dieselbe ---
# --- tagesgenaue Logik wie prepare_channel_scores.py::relativ_periode() und ---
# --- geglaettete_kurve.py::periode_aus_datum() (siehe periode_aus_datum() unten).
# --- ACHTUNG: Daten aus dem Gedaechtnis/einer kurzen Recherche zusammengestellt, ---
# --- insbesondere "Energiepreisschock" (Prozess ueber Monate, kein singulaeres Datum) ---
# --- und "Waffenstillstandsverhandlungen" (mehrere Runden 2025, hier: direkte ---
# --- Ukraine-Russland-Gespraeche in Istanbul) vor Verwendung in der Arbeit noch mal ---
# --- gegenpruefen. ---
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

# --- Zusatzvariante: Index zum letzten Vorkriegsmonat (nur fuer ausgewaehlte Dimensionen) ---
# Statt des absoluten Rohwerts wird jeder Kanal auf seinen EIGENEN Wert in der letzten
# Vorkriegsperiode (SPALTE_PERIODE == -1) indexiert (= 100) - anders als der Baseline-Index
# in deskriptiv_aggregation.py (gemitteltes Vorkriegsfenster, fuer MODUS="erfolg" bewusst
# deaktiviert, siehe dortiger Docstring) ein EINZELNER, praeziser Referenzzeitpunkt kurz vor
# Kriegsbeginn. Macht die RELATIVE Veraenderung ("Steigung") sichtbar, unabhaengig vom
# absoluten Niveau des Kanals (z.B. schwankt die Summe der Views zwischen Kanaelen um
# Groessenordnungen, was im Rohwert-Plot kleinere Kanaele optisch verschwinden laesst).
# Bei GRANULARITAET = "monat" (Standard) ist Periode -1 exakt der letzte Kalendermonat vor
# Kriegsbeginn; bei "quartal" waere es das letzte Vorkriegsquartal (weniger praezise).
# Kanaele ohne (gueltigen, > 0) Wert in dieser Referenzperiode werden fuer diese Variante
# ausgeschlossen (kein Index berechenbar) - siehe ergaenze_index_letzter_vorkriegsmonat().
INDEX_LETZTER_VORKRIEGSMONAT_DIMENSIONEN = ["view_count_summe", "view_count"]   # [] = Zusatzvariante deaktiviert

# =========================================================
# HILFSFUNKTIONEN
# =========================================================

def gruppenspalte():
    return {"keiner": None, "medientyp": "medientyp", "ideologie": "ideologie_gruppe"}[SPLIT]


def wertspalte():
    """Immer der absolute Rohwert, kein Baseline-Index (siehe Docstring). Eigene Funktion
    bleibt bestehen, damit ein spaeterer Wechsel zurueck auf index_100 an einer Stelle
    moeglich ist."""
    return "wert_roh"


def ergaenze_index_letzter_vorkriegsmonat(df, dimension):
    """Filtert df auf eine einzelne Dimension und ergaenzt die Spalte
    'index_letzter_vorkriegsmonat': wert_roh jeder Kanal-Periode-Zeile geteilt durch den
    wert_roh DESSELBEN Kanals in der letzten Vorkriegsperiode (SPALTE_PERIODE == -1), mal
    100 (siehe INDEX_LETZTER_VORKRIEGSMONAT_DIMENSIONEN). Kanaele ohne gueltigen (> 0)
    Wert in dieser Referenzperiode bekommen NaN und fallen damit aus der Plot-Variante
    raus. Referenz wird ueber groupby().mean() gebildet statt ueber set_index() (nicht
    ueber drop_duplicates()), weil deskriptiv_{modus}_{granularitaet}.csv fuer eine
    kleine Zahl Kanaele doppelte Kanal-Perioden-Zeilen enthalten kann (Duplikate aus
    einem Upstream-Join, vgl. deskriptiv_aggregation.py::ergaenze_kanalmerkmale() -
    channel_classification_ideology.csv hat fuer diese Kanaele offenbar mehr als einen
    Eintrag) - set_index() waere dort an einem nicht eindeutigen Index gescheitert."""
    teil = df[df["dimension"] == dimension].copy()
    referenz = (teil.loc[teil[SPALTE_PERIODE].isin([-1,-2, -3, -4, -5, -6])]
                .groupby("channel_id")["wert_roh"].mean())
    referenz = referenz[referenz > 0]   # Division durch 0/negative Referenz ausschliessen

    teil["index_letzter_vorkriegsmonat"] = (
        teil["wert_roh"] / teil["channel_id"].map(referenz) * 100
    )

    n_ohne = teil.loc[teil["index_letzter_vorkriegsmonat"].isna(), "channel_id"].nunique()
    if n_ohne:
        print(f"[Index-Vorkriegsmonat] '{dimension}': {n_ohne} Kanaele ohne gueltigen Wert "
              f"in {SPALTE_PERIODE}=-1 -> von dieser Variante ausgeschlossen.")
    return teil


def aggregiere(df, gruppe, wert, zentral="mean"):
    """zentral='mean' (Standard, ueberall ausser den beiden Index-letzter-
    Vorkriegsmonat-Funktionen): ungewichteter Mittelwert der Kanalwerte je Periode.
    zentral='median': Median statt Mittelwert - robust gegen einzelne Kanaele mit
    extremen Indexwerten (siehe Modul-Docstring, Abschnitt 'Median statt Mittelwert',
    Fallstudie LYDOM/Westend Verlag). ci_unten/ci_oben bleiben in beiden Faellen ueber
    die Standardfehler-Formel des Mittelwerts berechnet (fuer den Median nur eine grobe
    Naeherung, aber unkritisch, da ZEIGE_CI fuer Mehrgruppen-Plots standardmaessig aus ist)."""
    schluessel = [SPALTE_PERIODE] + ([gruppe] if gruppe else [])
    funktion = "median" if zentral == "median" else "mean"
    agg = df.groupby(schluessel, as_index=False).agg(
        mittel=(wert, funktion),
        sd=(wert, "std"),
        n_kanaele=("channel_id", "nunique"),
    )
    agg["se"] = agg["sd"] / np.sqrt(agg["n_kanaele"].clip(lower=1))
    agg["ci_unten"] = agg["mittel"] - 1.96 * agg["se"]
    agg["ci_oben"] = agg["mittel"] + 1.96 * agg["se"]
    return agg[agg["n_kanaele"] >= MIN_KANAELE_PRO_ZELLE]


def glaette(x, y):
    """LOWESS-Glaettung einer einzelnen Gruppenlinie (reine Darstellungshilfe, siehe
    GLAETTUNG_LOWESS_FRAC). Gibt bei zu wenigen Punkten oder deaktivierter Glaettung
    die rohen Werte unveraendert zurueck."""
    if not GLAETTUNG_LOWESS_FRAC or len(x) < 4:
        return y
    return lowess(y, x, frac=GLAETTUNG_LOWESS_FRAC, xvals=x, return_sorted=False)


def periode_aus_datum(datum_str):
    """Wandelt ein Kalenderdatum in dieselbe Periodenzaehlung um wie SPALTE_PERIODE
    (tagesgenau relativ zu KRIEGSBEGINN, konsistent mit prepare_channel_scores.py::
    relativ_periode() und geglaettete_kurve.py::periode_aus_datum())."""
    datum = pd.Timestamp(datum_str)
    start = pd.Timestamp(KRIEGSBEGINN)
    monate_pro_periode = {"quartal": 3, "monat": 1}[GRANULARITAET]
    monate = (datum.year - start.year) * 12 + (datum.month - start.month)
    monate -= 1 if datum.day < start.day else 0
    return monate // monate_pro_periode


def zeichne_ereignislinien(ax):
    """Zeichnet fuer jedes Ereignis aus EREIGNISSE eine duenne rote gepunktete
    senkrechte Referenzlinie samt um 90 Grad gedrehter Beschriftung, sofern das
    Ereignis im aktuell dargestellten Periodenfenster [PERIODE_MIN, PERIODE_MAX]
    liegt - Stil (Farbe, gestaffelte Label-Hoehe gegen Ueberlappung benachbarter
    Ereignisse) analog zu geglaettete_kurve.py::plotte(). Wird von allen
    Render-Funktionen NACH dem Setzen der finalen y-Achsengrenzen aufgerufen (sonst
    verzerrt ax.get_ylim() die Label-Position)."""
    if not EREIGNISSE:
        return
    y_min, y_max = ax.get_ylim()
    spanne = y_max - y_min
    for idx, ereignis in enumerate(EREIGNISSE):
        pos = periode_aus_datum(ereignis["datum"])
        if pos < PERIODE_MIN or pos > PERIODE_MAX:
            continue
        ax.axvline(pos, color="tab:red", linestyle=":", linewidth=0.8, alpha=0.6, zorder=1)
        y_text = y_max - spanne * (0.03 + 0.06 * (idx % 3))
        ax.text(pos, y_text, ereignis["name"], rotation=90, fontsize=6.5,
                color="tab:red", ha="right", va="top", alpha=0.8)


def kanaele_mit_beiden_perioden(teil, spalte_periode):
    """channel_ids mit mindestens einem Wert VOR und mindestens einem Wert AB Kriegsbeginn,
    bezogen auf die uebergebene (bereits auf Dimension/Wert/Periodenfenster gefilterte)
    Tabelle. Grundlage fuer die Plot-Variante 'beide_perioden' (siehe Docstring)."""
    vor = set(teil.loc[teil[spalte_periode] < 0, "channel_id"])
    nach = set(teil.loc[teil[spalte_periode] >= 0, "channel_id"])
    return vor & nach


def filtere_vorkriegs_kanaele(df):
    """Behaelt nur Zeilen von Kanaelen, die MINDESTENS EINEN Wert vor Kriegsbeginn
    (SPALTE_PERIODE < 0) haben - ueber alle Dimensionen hinweg, da Kanalexistenz eine
    Kanal-, keine Dimensionseigenschaft ist. Anders als kanaele_mit_beiden_perioden()
    wird KEIN Nachkriegswert verlangt (siehe NUR_VORKRIEGS_KANAELE-Docstring). Wird von
    main() einmal auf den kompletten eingelesenen df angewendet, VOR der Aufteilung nach
    Dimension/Gruppe in den einzelnen Plot-Funktionen."""
    kanaele = set(df.loc[df[SPALTE_PERIODE] < 0, "channel_id"])
    vor = df["channel_id"].nunique()
    df = df[df["channel_id"].isin(kanaele)]
    print(f"[NUR_VORKRIEGS_KANAELE] {vor} -> {df['channel_id'].nunique()} Kanaele "
          f"(nur Kanaele mit mindestens einem Wert vor Kriegsbeginn, {SPALTE_PERIODE} < 0).")
    return df


def plotte_dimension(df, dimension, gruppe, wert):
    teil_basis = df[df["dimension"] == dimension].dropna(subset=[wert])
    teil_basis = teil_basis[(teil_basis[SPALTE_PERIODE] >= PERIODE_MIN) & (teil_basis[SPALTE_PERIODE] <= PERIODE_MAX)]
    if teil_basis.empty:
        print(f"[Skip] Keine Daten fuer '{dimension}'.")
        return

    for variante in KANALFILTER_VARIANTEN:
        if variante == "beide_perioden":
            kanaele = kanaele_mit_beiden_perioden(teil_basis, SPALTE_PERIODE)
            teil = teil_basis[teil_basis["channel_id"].isin(kanaele)]
        else:
            teil = teil_basis
        if teil.empty:
            print(f"[Skip][{variante}] '{dimension}': keine Kanaele nach Variantenfilter uebrig.")
            continue
        _plotte_dimension_variante(teil, dimension, gruppe, wert, variante)


def _plotte_dimension_variante(teil, dimension, gruppe, wert, variante):
    agg = aggregiere(teil, gruppe, wert)
    if agg.empty:
        print(f"[Skip][{variante}] '{dimension}': alle Zellen unter MIN_KANAELE_PRO_ZELLE.")
        return

    fig, ax = plt.subplots(figsize=ABBILDUNG_GROESSE)

    if gruppe:
        gruppen = GRUPPEN_REIHENFOLGE or sorted(agg[gruppe].dropna().unique())
        gruppen = [g for g in gruppen if g in set(agg[gruppe])]
    else:
        gruppen = [None]

    for g in gruppen:
        reihe = agg if g is None else agg[agg[gruppe] == g]
        reihe = reihe.sort_values(SPALTE_PERIODE)
        label = "alle Kanaele" if g is None else str(g)
        x = reihe[SPALTE_PERIODE].to_numpy(dtype=float)
        y = reihe["mittel"].to_numpy(dtype=float)
        y_glatt = glaette(x, y)

        linie, = ax.plot(x, y_glatt, linewidth=2.2, label=label)
        farbe = linie.get_color()
        if ZEIGE_ROHWERT_PUNKTE:
            ax.scatter(x, y, s=14, color=farbe, alpha=0.35, zorder=3)  # rohe Periodenmittel, blass
        if ZEIGE_CI:
            ax.fill_between(x, reihe["ci_unten"], reihe["ci_oben"], alpha=0.12, color=farbe)

    # Referenzlinien
    ax.axvline(-0.5, color="black", linestyle="--", linewidth=1)
    ax.text(-0.45, ax.get_ylim()[1], f" {_GRAN_CFG['referenzlinie_text']}", va="top", fontsize=8)

    ax.axhline(0, color="grey", linewidth=0.8)
    zeichne_ereignislinien(ax)
    ax.set_ylabel("Skalenwert (absolut)")
    varianten_hinweis = ("nur Kanaele mit Vor- UND Nachkriegswerten" if variante == "beide_perioden"
                          else "alle Kanaele, inkl. seit Kriegsbeginn neu dazugekommene")
    if MODUS == "populismus":
        hinweis = ("Vor dem Strich: allgemeinpolitische Baselinevideos. Nach dem Strich: "
                    f"Kriegsvideos. Variante: {varianten_hinweis}.")
    elif MODUS == "erfolg":
        videos_hinweis = ("Nur Kriegsvideos (ist_kriegsvideo == 1, Topic 'russia_ukraine_war')"
                           if NUR_TOPICVIDEOS else
                           "Alle Videos des Kanals (Baseline- und Kriegsperiode, keine Themenfilterung)")
        hinweis = (f"{videos_hinweis}, rohe Werte ohne Alters-Normalisierung. "
                   f"Variante: {varianten_hinweis}.")
    else:
        hinweis = f"Nur Kriegsvideos, keine Vorkriegsbaseline verfuegbar. Variante: {varianten_hinweis}."

    ax.set_xlabel(ACHSENLABEL)
    ax.set_title(f"{dimension} ({MODUS_DATEI}, {GRANULARITAET}, {variante})")
    ax.set_xticks(sorted(agg[SPALTE_PERIODE].unique()))
    if gruppe:
        ax.legend(fontsize=8)
    fig.text(0.01, 0.005, hinweis, fontsize=7, color="dimgrey")
    fig.tight_layout(rect=(0, 0.03, 1, 1))

    PFAD_PLOTS.mkdir(parents=True, exist_ok=True)
    datei = PFAD_PLOTS / f"{MODUS_DATEI}_{dimension}_{SPLIT}_{GRANULARITAET}_{variante}.png"
    fig.savefig(datei, dpi=DPI)
    plt.close(fig)
    print(f"[Plot][{variante}] {datei}")

    if ZEIGE_N:
        spalten = [SPALTE_PERIODE] + ([gruppe] if gruppe else []) + ["n_kanaele", "mittel"]
        print(agg[spalten].to_string(index=False))
        print()


def plotte_dimension_index_vorkriegsmonat(df, dimension):
    """Zusatzvariante zu plotte_dimension(): dieselbe Gruppenaufteilung (SPLIT), aber
    jeder Kanal auf seinen eigenen Wert in der letzten Vorkriegsperiode indexiert (= 100)
    statt auf den Rohwert geplottet - siehe INDEX_LETZTER_VORKRIEGSMONAT_DIMENSIONEN und
    ergaenze_index_letzter_vorkriegsmonat(). Kein KANALFILTER_VARIANTEN-Loop noetig: die
    Indexbildung selbst filtert bereits auf Kanaele mit einem gueltigen Wert in Periode -1
    (aehnlich streng wie die Variante 'beide_perioden', aber praeziser - ein Wert GENAU in
    Periode -1, nicht irgendein beliebiger Vorkriegswert). Aggregation ueber MEDIAN statt
    Mittelwert (aggregiere(..., zentral='median')) - siehe Modul-Docstring, Abschnitt
    'Median statt Mittelwert'."""
    gruppe = gruppenspalte()
    teil = ergaenze_index_letzter_vorkriegsmonat(df, dimension)
    teil = teil.dropna(subset=["index_letzter_vorkriegsmonat"])
    teil = teil[(teil[SPALTE_PERIODE] >= PERIODE_MIN) & (teil[SPALTE_PERIODE] <= PERIODE_MAX)]
    if teil.empty:
        print(f"[Skip][index_vorkriegsmonat] Keine Daten fuer '{dimension}'.")
        return

    agg = aggregiere(teil, gruppe, "index_letzter_vorkriegsmonat", zentral="median")
    if agg.empty:
        print(f"[Skip][index_vorkriegsmonat] '{dimension}': alle Zellen unter MIN_KANAELE_PRO_ZELLE.")
        return

    fig, ax = plt.subplots(figsize=ABBILDUNG_GROESSE)

    if gruppe:
        gruppen = GRUPPEN_REIHENFOLGE or sorted(agg[gruppe].dropna().unique())
        gruppen = [g for g in gruppen if g in set(agg[gruppe])]
    else:
        gruppen = [None]

    for g in gruppen:
        reihe = agg if g is None else agg[agg[gruppe] == g]
        reihe = reihe.sort_values(SPALTE_PERIODE)
        label = "alle Kanaele" if g is None else str(g)
        x = reihe[SPALTE_PERIODE].to_numpy(dtype=float)
        y = reihe["mittel"].to_numpy(dtype=float)
        y_glatt = glaette(x, y)

        linie, = ax.plot(x, y_glatt, linewidth=2.2, label=label)
        farbe = linie.get_color()
        if ZEIGE_ROHWERT_PUNKTE:
            ax.scatter(x, y, s=14, color=farbe, alpha=0.35, zorder=3)  # rohe Periodenmittel, blass
        if ZEIGE_CI:
            ax.fill_between(x, reihe["ci_unten"], reihe["ci_oben"], alpha=0.12, color=farbe)

    # Referenzlinien: Kriegsbeginn (wie ueberall) + Index-Referenzwert 100 statt 0
    ax.axvline(-0.5, color="black", linestyle="--", linewidth=1)
    ax.text(-0.45, ax.get_ylim()[1], f" {_GRAN_CFG['referenzlinie_text']}", va="top", fontsize=8)
    ax.axhline(100, color="grey", linewidth=0.8, linestyle="--")
    zeichne_ereignislinien(ax)

    ax.set_ylabel("Index (Median, letzter Vorkriegsmonat = 100)")
    ax.set_xlabel(ACHSENLABEL)
    ax.set_title(f"{dimension} ({MODUS_DATEI}, {GRANULARITAET}, Index letzter Vorkriegsmonat, Median)")
    ax.set_xticks(sorted(agg[SPALTE_PERIODE].unique()))
    if gruppe:
        ax.legend(fontsize=8)

    hinweis = ("Jeder Kanal auf seinen eigenen Wert in der letzten Vorkriegsperiode "
               f"({SPALTE_PERIODE}=-1) indexiert (=100). Nur Kanaele mit gueltigem Wert dort "
               "enthalten. Median statt Mittelwert ueber die Kanaele je Periode (robust gegen "
               "einzelne Kanaele mit Extremindex durch virale Einzelvideos, siehe Modul-Docstring) "
               "- fuer absolute Werte siehe die Rohwert-Variante(n) derselben Dimension.")
    fig.text(0.01, 0.005, hinweis, fontsize=7, color="dimgrey")
    fig.tight_layout(rect=(0, 0.03, 1, 1))

    PFAD_PLOTS.mkdir(parents=True, exist_ok=True)
    datei = PFAD_PLOTS / f"{MODUS_DATEI}_{dimension}_{SPLIT}_{GRANULARITAET}_index_vorkriegsmonat.png"
    fig.savefig(datei, dpi=DPI)
    plt.close(fig)
    print(f"[Plot][index_vorkriegsmonat] {datei}")

    if ZEIGE_N:
        spalten = [SPALTE_PERIODE] + ([gruppe] if gruppe else []) + ["n_kanaele", "mittel"]
        print(agg[spalten].to_string(index=False))
        print()


def plotte_filterkombination(df, eintrag):
    """Mehrere Dimensionen in einer Grafik, gefiltert auf eine beliebige Kombination
    aus Kanalmerkmalen (z.B. medientyp + ideologie_gruppe). Aggregation ist immer
    ungruppiert (ein Mittelwert je Periode ueber die gefilterten Kanaele)."""

    name = eintrag.get("name", "filterkombination")
    filt = eintrag.get("filter", {})
    dimensionen = eintrag["dimensionen"]
    wert = wertspalte()

    teil = df.copy()
    beschreibung = []
    for spalte, werte in filt.items():
        if spalte not in teil.columns:
            raise KeyError(f"Filterkombination '{name}': Spalte '{spalte}' nicht in den Daten.")
        teil = teil[teil[spalte].isin(werte)]
        beschreibung.append(f"{spalte}={'+'.join(map(str, werte))}")

    if teil.empty:
        print(f"[Skip] Filterkombination '{name}': keine Kanaele nach Filter uebrig.")
        return

    fig, ax = plt.subplots(figsize=ABBILDUNG_GROESSE)
    ax2 = None
    irgendwas_geplottet = False
    standardfarben = cycle(plt.rcParams["axes.prop_cycle"].by_key()["color"])

    for dim in dimensionen:
        teil_dim = teil[teil["dimension"] == dim].dropna(subset=[wert])
        teil_dim = teil_dim[(teil_dim[SPALTE_PERIODE] >= PERIODE_MIN) & (teil_dim[SPALTE_PERIODE] <= PERIODE_MAX)]
        if teil_dim.empty:
            print(f"[Skip] '{name}' / '{dim}': keine Daten.")
            continue

        agg = aggregiere(teil_dim, None, wert)
        if agg.empty:
            print(f"[Skip] '{name}' / '{dim}': alle Zellen unter MIN_KANAELE_PRO_ZELLE.")
            continue
        agg = agg.sort_values(SPALTE_PERIODE)

        ziel_achse = ax
        if dim in SEKUNDAERACHSE_DIMENSIONEN:
            if ax2 is None:
                ax2 = ax.twinx()
            ziel_achse = ax2

        farbe = DIMENSION_FARBEN.get(dim) or next(standardfarben)

        x = agg[SPALTE_PERIODE].to_numpy(dtype=float)
        y = agg["mittel"].to_numpy(dtype=float)
        y_glatt = glaette(x, y)

        ziel_achse.plot(x, y_glatt, linewidth=2.2, label=dim, color=farbe)
        if ZEIGE_ROHWERT_PUNKTE:
            ziel_achse.scatter(x, y, s=14, color=farbe, alpha=0.35, zorder=3)
        if ZEIGE_CI:
            ziel_achse.fill_between(x, agg["ci_unten"], agg["ci_oben"], alpha=0.12, color=farbe)
        irgendwas_geplottet = True

        if ZEIGE_N:
            print(f"  [{name} / {dim}]")
            print(agg[[SPALTE_PERIODE, "n_kanaele", "mittel"]].to_string(index=False))

    if not irgendwas_geplottet:
        print(f"[Skip] Filterkombination '{name}': keine Dimension hatte ausreichend Daten.")
        plt.close(fig)
        return

    ax.axvline(-0.5, color="black", linestyle="--", linewidth=1)
    ax.axhline(0, color="grey", linewidth=0.8)
    zeichne_ereignislinien(ax)
    ax.set_xlabel(ACHSENLABEL)
    ax.set_ylabel("Skalenwert (Hauptachse)")
    if ax2:
        ax2.set_ylabel("Skalenwert (Sekundärachse: " + ", ".join(
            d for d in dimensionen if d in SEKUNDAERACHSE_DIMENSIONEN) + ")")

    ax.set_title(f"{name} ({', '.join(beschreibung)}, {GRANULARITAET})")

    linien, labels = ax.get_legend_handles_labels()
    if ax2:
        linien2, labels2 = ax2.get_legend_handles_labels()
        linien += linien2
        labels += labels2
    ax.legend(linien, labels, fontsize=8)

    fig.tight_layout()

    PFAD_PLOTS.mkdir(parents=True, exist_ok=True)
    datei = PFAD_PLOTS / f"{MODUS_DATEI}_{name}_{GRANULARITAET}.png"
    fig.savefig(datei, dpi=DPI)
    plt.close(fig)
    print(f"[Plot] {datei}")


# =========================================================
# ZUSATZ: 5-Gruppen-Uebersicht (OERR, Traditionell, Alternative x Ideologie)
# =========================================================

def baue_gruppe5(df):
    """Baut die Spalte 'gruppe5' fuer plotte_dimension_gruppen5(): OeRR und
    Traditionelles Medium bleiben als Ganzes, Alternatives Medium wird zusaetzlich nach
    Ideologie in links/mitte/rechts aufgespalten (mit Abstand die groesste und
    ideologisch heterogenste Medientyp-Gruppe, dieselbe Aufspaltung wie
    frage1_populismus_bericht.py::TEILGRUPPEN_INTERAKTIONEN). Politiker/Partei wird
    ausgeschlossen (auf Wunsch), ebenso Alternative-Medium-Kanaele ohne
    Ideologie-Einordnung (koennen keiner der drei Untergruppen zugeordnet werden)."""
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


def baue_gruppe4(df):
    """Baut die Spalte 'gruppe4' fuer plotte_dimension_gruppe4() - Nutzervorgabe fuer die
    Forschungsfrage-2-Erfolgsplots (siehe .claude/CLAUDE.md, Frage 2: 'Gibt es
    Unterschiede zwischen rechten und linken Kanaelen?'): ÖRR und Traditionelles Medium
    werden ANDERS als bei baue_gruppe5() zu EINER Gruppe zusammengefasst (dieselbe
    Begruendung wie dort - beide fuer sich zu klein/ideologisch zu homogen fuer eine
    eigene Zeitreihe), Alternatives Medium wird weiterhin nach Ideologie in
    links/mitte/rechts aufgespalten (mit Abstand die groesste und ideologisch
    heterogenste Medientyp-Gruppe). Politiker/Partei wird ausgeschlossen (auf Wunsch),
    ebenso Alternative-Medium-Kanaele ohne Ideologie-Einordnung."""
    df = df.copy()
    ist_alt = df["medientyp"] == "Alternatives Medium"
    df["gruppe4"] = df["medientyp"]
    df.loc[df["medientyp"].isin(["ÖRR", "Traditionelles Medium"]), "gruppe4"] = "ÖRR + Traditionelle Medien"
    df.loc[ist_alt, "gruppe4"] = "Alternative Medien (" + df.loc[ist_alt, "ideologie_gruppe"].astype(str) + ")"

    vor = df["channel_id"].nunique()
    df = df[df["gruppe4"].isin(GRUPPE4_REIHENFOLGE)]
    nach = df["channel_id"].nunique()
    if nach < vor:
        print(f"[Gruppe4] {vor - nach} Kanaele ausgeschlossen (Politiker/Partei oder "
              f"Alternatives Medium ohne Ideologie-Einordnung).")
    return df


def _rendere_gruppenplot(df, dimension, wert, gruppen_spalte, reihenfolge, dateiname_suffix, titel_zusatz,
                          referenzlinie_y=0, y_label="Skalenwert (absolut)", hinweis_zusatz=None,
                          zentral="mean"):
    """Gemeinsame Rendering-Logik fuer die Mehrgruppen-Uebersichtsplots (aktuell:
    plotte_dimension_gruppen5(), plotte_dimension_gruppe4() und die Index-Variante
    plotte_dimension_gruppen5_index_vorkriegsmonat()) - je Gruppe eine dicke Hauptlinie
    (nur Kanaele mit Vor- UND Nachkriegswerten, wie Variante 'beide_perioden') und eine
    duennere Linie in DERSELBEN Farbe (alle Kanaele der Gruppe, inkl. seit Kriegsbeginn
    neu dazugekommene ohne Vorkriegsfenster, wie Variante 'alle') in EINEM Plot statt in
    getrennten Dateien. df muss bereits auf Dimension/Fenster gefiltert sein UND die
    Spalte gruppen_spalte enthalten (siehe baue_gruppe5()/baue_gruppe4()).
    referenzlinie_y/y_label/hinweis_zusatz erlauben die Wiederverwendung fuer die
    Index-Variante (Referenzwert 100 statt 0, andere Achsenbeschriftung, zusaetzlicher
    Hinweistext) - Standardwerte entsprechen dem bisherigen Rohwert-Verhalten. zentral wird
    unveraendert an aggregiere() durchgereicht ('mean' fuer plotte_dimension_gruppen5()/
    plotte_dimension_gruppe4(), 'median' fuer plotte_dimension_gruppen5_index_
    vorkriegsmonat() - siehe Modul-Docstring, Abschnitt 'Median statt Mittelwert'). Schreibt
    bei ZEIGE_N = True (Standard) zusaetzlich n_kanaele je Periode/Gruppe auf die Konsole (fuer
    beide Teil-Aggregationen agg_alle/agg_beide, also sowohl fuer die duenne als auch die
    dicke Linie) - dieselbe Kanalanzahl-Anzeige wie in _plotte_dimension_variante(), damit
    sie auch fuer die Alternative-Medien-links/mitte/rechts-Aufspaltung (Gruppe4/Gruppe5)
    verfuegbar ist."""
    agg_alle = aggregiere(df, gruppen_spalte, wert, zentral=zentral)
    kanaele_beide = kanaele_mit_beiden_perioden(df, SPALTE_PERIODE)
    teil_beide = df[df["channel_id"].isin(kanaele_beide)]
    agg_beide = aggregiere(teil_beide, gruppen_spalte, wert, zentral=zentral)

    vorhandene_gruppen = [g for g in reihenfolge
                           if g in set(agg_alle[gruppen_spalte]) | set(agg_beide[gruppen_spalte])]
    if not vorhandene_gruppen:
        print(f"[Skip][{dateiname_suffix}] '{dimension}': alle Zellen unter MIN_KANAELE_PRO_ZELLE.")
        return

    fig, ax = plt.subplots(figsize=ABBILDUNG_GROESSE)
    standardfarben = cycle(plt.rcParams["axes.prop_cycle"].by_key()["color"])
    alle_perioden = set()

    for g in vorhandene_gruppen:
        farbe = next(standardfarben)

        # duenne Linie: alle Kanaele der Gruppe (inkl. Kriegs-Neuzugaenge ohne Vorkriegsfenster)
        reihe_alle = agg_alle[agg_alle[gruppen_spalte] == g].sort_values(SPALTE_PERIODE)
        if not reihe_alle.empty:
            x = reihe_alle[SPALTE_PERIODE].to_numpy(dtype=float)
            y = glaette(x, reihe_alle["mittel"].to_numpy(dtype=float))
            ax.plot(x, y, linewidth=1.0, color=farbe, alpha=0.55, zorder=2)
            alle_perioden.update(x)

        # dicke Hauptlinie: nur Kanaele mit Vor- UND Nachkriegswerten
        reihe_beide = agg_beide[agg_beide[gruppen_spalte] == g].sort_values(SPALTE_PERIODE)
        if not reihe_beide.empty:
            x = reihe_beide[SPALTE_PERIODE].to_numpy(dtype=float)
            y_roh = reihe_beide["mittel"].to_numpy(dtype=float)
            y = glaette(x, y_roh)
            ax.plot(x, y, linewidth=2.4, color=farbe, label=g, zorder=4)
            if ZEIGE_ROHWERT_PUNKTE:
                ax.scatter(x, y_roh, s=14, color=farbe, alpha=0.35, zorder=5)
            alle_perioden.update(x)
        else:
            # Gruppe hat keine Kanaele mit beiden Perioden -> trotzdem Legendeneintrag
            ax.plot([], [], linewidth=2.4, color=farbe, label=f"{g} (nur duenne Linie)")

    ax.axvline(-0.5, color="black", linestyle="--", linewidth=1)
    ax.text(-0.45, ax.get_ylim()[1], f" {_GRAN_CFG['referenzlinie_text']}", va="top", fontsize=8)
    ax.axhline(referenzlinie_y, color="grey", linewidth=0.8, linestyle=("-" if referenzlinie_y == 0 else "--"))
    zeichne_ereignislinien(ax)
    ax.set_xlabel(ACHSENLABEL)
    ax.set_ylabel(y_label)
    ax.set_title(f"{dimension} ({MODUS_DATEI}, {GRANULARITAET}, {titel_zusatz})")
    if alle_perioden:
        ax.set_xticks(sorted(alle_perioden))
    ax.legend(fontsize=8)

    punkte_hinweis = " + Punkte" if ZEIGE_ROHWERT_PUNKTE else ""
    hinweis = (f"Dicke Linie{punkte_hinweis}: nur Kanaele mit Vor- UND Nachkriegswerten (Hauptlinie). "
               "Duennere Linie in derselben Farbe: alle Kanaele der Gruppe, inkl. seit "
               "Kriegsbeginn neu dazugekommene ohne Vorkriegsfenster. Politiker/Partei "
               "ausgeschlossen.")
    if hinweis_zusatz:
        hinweis = f"{hinweis_zusatz} {hinweis}"
    fig.text(0.01, 0.005, hinweis, fontsize=7, color="dimgrey")
    fig.tight_layout(rect=(0, 0.03, 1, 1))

    PFAD_PLOTS.mkdir(parents=True, exist_ok=True)
    datei = PFAD_PLOTS / f"{MODUS_DATEI}_{dimension}_{dateiname_suffix}_{GRANULARITAET}.png"
    fig.savefig(datei, dpi=DPI)
    plt.close(fig)
    print(f"[Plot][{dateiname_suffix}] {datei}")

    if ZEIGE_N:
        spalten = [SPALTE_PERIODE, gruppen_spalte, "n_kanaele", "mittel"]
        print(f"  [{dateiname_suffix}] n_kanaele je Periode - alle Kanaele (duenne Linie):")
        print(agg_alle[spalten].to_string(index=False))
        print(f"  [{dateiname_suffix}] n_kanaele je Periode - nur Kanaele mit Vor- UND "
              f"Nachkriegswerten (dicke Hauptlinie):")
        print(agg_beide[spalten].to_string(index=False))
        print()


def plotte_dimension_gruppen5(df, dimension, wert):
    """Wie plotte_dimension(), aber mit der 5-Gruppen-Einteilung aus baue_gruppe5()
    (ÖRR und Traditionelles Medium bleiben getrennt) - Rendering siehe
    _rendere_gruppenplot()."""
    teil_basis = df[df["dimension"] == dimension].dropna(subset=[wert])
    teil_basis = teil_basis[(teil_basis[SPALTE_PERIODE] >= PERIODE_MIN) & (teil_basis[SPALTE_PERIODE] <= PERIODE_MAX)]
    if teil_basis.empty:
        print(f"[Skip][Gruppen5] Keine Daten fuer '{dimension}'.")
        return

    teil_basis = baue_gruppe5(teil_basis)
    if teil_basis.empty:
        print(f"[Skip][Gruppen5] '{dimension}': keine Kanaele nach Gruppe5-Zuordnung uebrig.")
        return

    _rendere_gruppenplot(teil_basis, dimension, wert, "gruppe5", GRUPPE5_REIHENFOLGE,
                          "gruppen5", "5-Gruppen-Uebersicht")


def plotte_dimension_gruppen5_index_vorkriegsmonat(df, dimension):
    """Wie plotte_dimension_gruppen5(), aber mit den Werten indexiert auf den letzten
    Vorkriegsmonat des jeweiligen Kanals (= 100) statt auf den Rohwert - dieselbe
    Indexlogik wie plotte_dimension_index_vorkriegsmonat() (einfache SPLIT-Ansicht),
    hier auf die 5-Gruppen-Einteilung aus baue_gruppe5() angewendet. Gesteuert ueber
    INDEX_LETZTER_VORKRIEGSMONAT_DIMENSIONEN (dieselbe Dimensionsliste wie bei der
    einfachen Ansicht) UND GRUPPEN5_PLOTTEN (kein Aufruf, wenn die 5-Gruppen-Uebersicht
    insgesamt deaktiviert ist, siehe main()). Aggregation ueber MEDIAN statt Mittelwert
    (_rendere_gruppenplot(..., zentral='median')) - siehe Modul-Docstring, Abschnitt
    'Median statt Mittelwert' (Fallstudie: ohne den Median haette 2023 ein einzelnes
    virales Video des Kanals "LYDOM - Vulkan Studio" den Mittelwert der Gruppe
    "Alternative Medien (links)" von ~195 auf ~10.900 hochgezogen)."""
    teil_basis = ergaenze_index_letzter_vorkriegsmonat(df, dimension)
    teil_basis = teil_basis.dropna(subset=["index_letzter_vorkriegsmonat"])
    teil_basis = teil_basis[(teil_basis[SPALTE_PERIODE] >= PERIODE_MIN) & (teil_basis[SPALTE_PERIODE] <= PERIODE_MAX)]
    if teil_basis.empty:
        print(f"[Skip][Gruppen5-index_vorkriegsmonat] Keine Daten fuer '{dimension}'.")
        return

    teil_basis = baue_gruppe5(teil_basis)
    if teil_basis.empty:
        print(f"[Skip][Gruppen5-index_vorkriegsmonat] '{dimension}': keine Kanaele nach "
              f"Gruppe5-Zuordnung uebrig.")
        return

    _rendere_gruppenplot(
        teil_basis, dimension, "index_letzter_vorkriegsmonat", "gruppe5", GRUPPE5_REIHENFOLGE,
        "gruppen5_index_vorkriegsmonat", "5-Gruppen-Uebersicht, Index letzter Vorkriegsmonat, Median",
        referenzlinie_y=100, y_label="Index (Median, letzter Vorkriegsmonat = 100)",
        hinweis_zusatz=("Jeder Kanal auf seinen eigenen Wert in der letzten Vorkriegsperiode "
                         f"({SPALTE_PERIODE}=-1) indexiert (=100). Median statt Mittelwert ueber "
                         "die Kanaele je Periode (robust gegen einzelne Kanaele mit Extremindex "
                         "durch virale Einzelvideos, siehe Modul-Docstring)."),
        zentral="median",
    )


def plotte_dimension_gruppe4(df, dimension, wert):
    """Wie plotte_dimension_gruppen5(), aber mit der 4-Gruppen-Einteilung aus
    baue_gruppe4() (ÖRR + Traditionelles Medium zusammengefasst) - primaere
    Standardansicht fuer MODUS='erfolg' (Forschungsfrage 2), Rendering siehe
    _rendere_gruppenplot()."""
    teil_basis = df[df["dimension"] == dimension].dropna(subset=[wert])
    teil_basis = teil_basis[(teil_basis[SPALTE_PERIODE] >= PERIODE_MIN) & (teil_basis[SPALTE_PERIODE] <= PERIODE_MAX)]
    if teil_basis.empty:
        print(f"[Skip][Gruppe4] Keine Daten fuer '{dimension}'.")
        return

    teil_basis = baue_gruppe4(teil_basis)
    if teil_basis.empty:
        print(f"[Skip][Gruppe4] '{dimension}': keine Kanaele nach Gruppe4-Zuordnung uebrig.")
        return

    _rendere_gruppenplot(teil_basis, dimension, wert, "gruppe4", GRUPPE4_REIHENFOLGE,
                          "gruppe4", "4-Gruppen-Uebersicht")


# =========================================================
# MAIN
# =========================================================

def main():
    if NUR_TOPICVIDEOS and MODUS != "erfolg":
        raise ValueError("NUR_TOPICVIDEOS ist nur zusammen mit MODUS = 'erfolg' vorgesehen "
                          "(siehe Docstring) - fuer 'populismus'/'stance' gibt es keine "
                          "deskriptiv_{modus}_kriegsvideos_{granularitaet}.csv.")

    pfad = str(PFAD_EINGABE).format(modus=MODUS_DATEI, granularitaet=GRANULARITAET)
    df = pd.read_csv(pfad)
    print(f"[Eingabe][{GRANULARITAET}] {len(df)} Zeilen aus {pfad}")

    if SPALTE_PERIODE not in df.columns:
        raise KeyError(f"Spalte '{SPALTE_PERIODE}' nicht in '{pfad}' gefunden - passt GRANULARITAET "
                        f"zu der eingelesenen Datei? Vorhanden: {list(df.columns)}")

    if NUR_VORKRIEGS_KANAELE:
        df = filtere_vorkriegs_kanaele(df)

    gruppe = gruppenspalte()
    wert = wertspalte()

    if gruppe and df[gruppe].isna().all():
        raise ValueError(f"Spalte '{gruppe}' ist komplett leer - Split nicht moeglich.")

    dimensionen = DIMENSIONEN_PLOTTEN or sorted(df["dimension"].unique())
    for d in dimensionen:
        plotte_dimension(df, d, gruppe, wert)

    for eintrag in FILTERKOMBINATIONEN:
        plotte_filterkombination(df, eintrag)

    if GRUPPEN5_PLOTTEN:
        for d in dimensionen:
            plotte_dimension_gruppen5(df, d, wert)

    if GRUPPE4_PLOTTEN:
        for d in dimensionen:
            plotte_dimension_gruppe4(df, d, wert)

    for d in INDEX_LETZTER_VORKRIEGSMONAT_DIMENSIONEN:
        if d not in df["dimension"].unique():
            print(f"[Skip][index_vorkriegsmonat] Dimension '{d}' nicht in den Daten.")
            continue
        plotte_dimension_index_vorkriegsmonat(df, d)
        if GRUPPEN5_PLOTTEN:
            plotte_dimension_gruppen5_index_vorkriegsmonat(df, d)


if __name__ == "__main__":
    main()
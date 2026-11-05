# -*- coding: utf-8 -*-
"""
marktanteil_rohdaten_plots.py

Marktanteils-Grafiken (Kapitel D der Masterarbeit) auf Basis des zentralen
Analysedatensatzes outputs/stata_rohdaten/ (videos_roh.dta, kanaele_roh.dta,
erzeugt von export_stata_rohdaten.py, Spezifikation docs/codebuch_rohdatensatz.md).
Loest fuer die Marktanteile die bisherige Datenbasis ab
(channel_video_erfolg.csv + lade_basisdaten() aus
frage4_kriegspraemie_relative_views_plots.py, genutzt von
frage4_kriegspraemie_marktanteil_plots.py und marktanteil_themen_plots.py).

Marktanteil je Zelle (Gruppe x rel_monat x Umfang), gepoolt auf Video-Ebene:

    anteil = sum(views | Gruppe, Umfang, Monat) / sum(views | alle Gruppen der Klassifikation, Umfang, Monat) * 100

Die Anteile einer Klassifikation summieren sich je Monat zu 100 %. Monate mit
< MIN_VIDEOS_PRO_MONAT Videos (ueber alle Gruppen zusammen) fallen ganz weg.

Angebot (untere Grafikreihe), gleiche Zellen und Mindestbesetzung:

    angebot_anteil = n_videos(Gruppe, Umfang, Monat) / n_videos(alle Gruppen der Klassifikation, Umfang, Monat) * 100

ANGEBOT_METRIK = "anzahl" zeigt stattdessen die absolute Zahl n_videos. Der
Vergleich beider Reihen trennt Output (mehr Uploads) von Reichweite pro Video
(Views-Anteil > Upload-Anteil).

QUARTALSWEISE = True ersetzt die Monate durch Quartale relativ zum
Kriegsbeginn (rel_quartal; Quartal 0 = [24.02.2022, 24.05.2022), Quartal -1 =
[24.11.2021, 24.02.2022)), gleiche Formeln je Quartal, aber OHNE LOWESS-Glaettung
und ohne BETONUNG_MONATE (Quartalswerte als verbundene Punkte). Monatsangaben der
CONFIG (PERIODE_MIN/-MAX, PHASEN, STREU_START/-INTERVALL) werden auf die
vollstaendig darin liegenden Quartale umgerechnet. Alle Dateinamen bekommen den
Zusatz _quartal (marktanteil_..._<format>_quartal.png, marktanteil_quartal.csv,
marktanteil_methodik_quartal.md), die Monatsdateien werden also nicht ueberschrieben.

ABSOLUT_VERSION = True erzeugt je Grafik zusaetzlich eine Version mit absoluten
Zahlen (gleiche Zellen und Mindestbesetzung): oben views_summe (Mio. Views je
Gruppe und Monat), unten n_videos (Uploads je Gruppe und Monat), eigene y-Achse
je Panel. Vorsicht: absolute Views juengerer Monate sind wegen der kuerzeren
Zeit bis zum Abruf systematisch niedriger; anders als bei den Anteilen kuerzt
sich dieser Alterseffekt nicht heraus.

Umfaenge
--------
- "alle Videos": kein Themenfilter (genereller Marktanteil).
- "politische Videos": politisch == "ja" (YouTube-topic_categories "Politics"),
  Kriegsvideos eingeschlossen.
- "Kriegsvideos": rel_russia_ukraine_war_cw == "ja" (Stichwortsuche
  russia_ukraine_war, core+wide, seit 13.10.2026 NUR Titel - vorher Titel +
  Beschreibung), ungefiltert nach politisch (wie in den bisherigen
  Marktanteils-Skripten).
- "politische Videos (Stichworte)": mindestens eine der Titel-Stichwortsuchen
  rel_<topic>_<KEYWORD_VARIANTE> der Themen in KEYWORD_THEMEN (Default: alle
  Themen aus topic_keywords.TOPIC_KEYWORDS, Variante cw = core+wide) == "ja";
  Alternative zur YouTube-Klassifikation politisch, Kriegsvideos eingeschlossen.
- Population: nur Videos mit format == "long" (keine Shorts, keine Livestreams,
  keine Videos ohne Formatzuordnung); vorher min_dauer == "ja" (> 180 s).

Klassifikationen
----------------
1. "medientyp_ideologie": OeRR, traditionelle Medien, alternative Medien
   links/mitte/rechts. Alternative Medien (medientyp "Creator & alternative
   Medien") nach ideo_gesellschaft_baseline mit den bisherigen Schnitten
   IDEOLOGIE_SCHNITTE = (-0.5, 0.5) aus deskriptiv_aggregation.py. Abweichung zu
   frueher: die Ideologie stammt jetzt aus der Baseline (Vorkriegsfenster, ohne
   Kriegsvideos) statt aus channel_classification_ideology.csv. Alternative
   Medien ohne Ideologie-Baseline und Partei/Politiker fallen raus.
   OERR_DOKU_CODES (CONFIG) trennt ÖRR-Kanaele mit diesen sample-Codes in
   channels_check.xlsx (z. B. [2] = politische Recherche/Doku) als eigene Gruppe
   "ÖRR (Recherche/Doku)" ab; die uebrigen ÖRR-Kanaele (tagesschau, phoenix
   usw.) bleiben "ÖRR". Beide zusammen ergeben die ÖRR-Linie ohne Trennung.
   Die Kanaele muessen ueber KANALLISTE im Sample sein; alle Ausgabedateien
   tragen dann den Zusatz _oerrdoku.
2. "populismus_tertile": Kanaele aus OeRR, traditionellen und alternativen
   Medien (Partei/Politiker wie in 1. ausgeschlossen) mit pop_baseline, in
   Tertile nach pop_baseline (ungewichtet je Kanal). Die Tertilgrenzen werden
   wie der Median in 3. auf den Kanaelen im tatsaechlichen Sample gebildet
   (nach KANALLISTE, Sample "alle"; dieselben Grenzen fuer "vorkrieg"), damit
   die Tertile im Sample gleich gross sind. Die Baseline ist vor
   Kriegsbeginn gemessen, die Gruppenzugehoerigkeit ist also nicht durch das
   Verhalten nach Kriegsbeginn beeinflusst. Die Konsole zeigt je Sample, wie
   viele Medien-Kanaele mangels pop_baseline herausfallen, und die Besetzung
   der Tertile nach Medientyp (ÖRR/traditionell/alternativ). POPULISMUS_TERTILE = False
   schaltet diese Klassifikation ab (keine Grafiken, keine Zeilen in CSV und
   Methodik-Datei).
3. "populismus_median": ÖRR und traditionelle Medien (alle) sowie alternative
   Medien (Gruppe "Alternative (...)" aus 1., inkl. MANUELL_ALT_RECHTS) mit
   pop_baseline, geteilt am Median von pop_baseline ueber die alternativen
   Kanaele im tatsaechlichen Sample (nach KANALLISTE, Sample "alle"; fuer
   "vorkrieg" gilt derselbe Median, damit die Gruppen identisch definiert
   sind; "über" = > Median). Trennt den Populismus vom Medientyp, da das
   obere Tertil in 2. fast nur alternative Medien enthaelt. Alternative Medien
   ohne pop_baseline fallen heraus (Anzahl je Sample auf der Konsole).
   POPULISMUS_MEDIAN = False schaltet die Klassifikation ab.
4. "medientyp_gesamt": ÖRR, traditionelle Medien und alle alternativen Medien
   als eine Gruppe, nach der MANUELLEN media_category in channels_check.xlsx
   (1 = ÖRR, 2 = traditionell, 3/4/5 = "Alternative Medien"; 6 und fehlender
   Code fallen raus). Unabhaengig von medientyp/Ideologie-Baseline aus
   kanaele_roh, deshalb nicht deckungsgleich mit der Summe der drei
   Alternative-Gruppen aus 1. (Konsole und Methodik-Datei zeigen die
   Abweichung). MEDIENTYP_GESAMT = False schaltet die Klassifikation ab.

Kanal-Samples (je Sample ein Satz Grafiken, siehe AP 2 Stichprobenbias)
-----------------------------------------------------------------------
- "alle": alle Kanaele aus kanaele_roh (427er-Kanon-Sample).
- "vorkrieg": nur sample_vorkrieg == "ja" (vor Kriegsbeginn aktive Kanaele);
  zeigt, ob eine Verschiebung auch ohne erst spaeter gestartete Kanaele besteht.
- KANALLISTE (CONFIG) schraenkt beide Samples zusaetzlich auf die gelisteten
  channel_ids ein (leer = keine Einschraenkung). Medientyp x Ideologie wird vorher
  auf allen Kanaelen gebildet; Tertilgrenzen und Populismus-Median dagegen erst
  auf den Kanaelen der Liste (haengen also von KANALLISTE ab).
- KANAELE_AUSSCHLIESSEN (CONFIG, Robustheitscheck): einzelne Kanaele per channel_id
  oder Kanaltitel (kanal_name bzw. channel_title in channels_check.xlsx, exakt bis auf
  Gross-/Kleinschreibung) aus beiden Samples entfernen, um zu pruefen, ob sie den
  Verlauf treiben. Der Ausschluss greift NACH KANALLISTE, MANUELL_ALT_RECHTS,
  Tertilgrenzen und Populismus-Median, die Gruppendefinition bleibt also identisch
  zum Lauf ohne Ausschluss. Konsole und Methodik-Datei zeigen je Kanal seinen Anteil
  an Views und Uploads seiner Gruppe vor bzw. ab Kriegsbeginn (vor dem Ausschluss).
  Alle Ausgabedateien tragen den Zusatz _ohne_<kanal> (bis 3 Kanaele) bzw.
  _ohne<N>kanaele (auch ueber datei_zusatz(), nachdem main() gelaufen ist).
- MANUELL_ALT_RECHTS (CONFIG, Robustheitscheck): Kanaele ohne Baseline-Gruppe
  (kein medientyp bzw. keine Ideologie in kanaele_roh, ausser Partei/Politiker),
  die in channels_check.xlsx manuell als media_category == 5 (alternativ rechts)
  codiert sind, zaehlen bei True zu "Alternative (rechts)". Die Liste dieser
  Kanaele wird immer auf der Konsole und in marktanteil_methodik.md ausgegeben;
  bei True tragen alle Ausgabedateien (PNG, HTML, CSV, MD) den Zusatz _manuell.

Ausgabe nach OUTPUTS / "segment_analysis" / "plots_marktanteil_rohdaten":
- marktanteil_<klassifikation>_<sample>_<format>.png  (Hauptgrafik, nur bei
  KOMBI_VERSION "getrennt"/"alle"; nur alle Videos; obere Reihe Views-Anteil, untere Reihe
  Angebot nach ANGEBOT_METRIK; Punkte = Monatswerte, Linie = LOWESS-Glaettung;
  Monate in BETONUNG_MONATE (Default -3 bis 3) zusaetzlich als deckende,
  verbundene Rohwerte, damit ein Sprung zu Kriegsbeginn nicht in der Glaettung
  verschwindet; senkrechte Linien: Kriegsbeginn (gestrichelt) und EREIGNISSE, Default
  Bundestagswahlen 2021/2025 und US-Wahlen 2020/2024 (gepunktet), tagesgenau
  innerhalb des Monats platziert. Achsenkonvention: der Punkt der Periode k liegt
  bei x = k und markiert deren Beginn, die Periode umfasst [k, k + 1); der
  Kriegsbeginn liegt damit exakt auf dem Punkt von Periode 0, Ereignisse
  zwischen dem Punkt ihrer Periode und dem der folgenden)
- Zusatz-Umfaenge aus UMFANG_ZUSATZ (Default politische Videos (Stichworte))
  je nach UMFANG_LAYOUT: "einzeln" -> marktanteil_<klassifikation>_<sample>_<umfang>_<format>.png
  (eine Grafik je Umfang); "kombiniert" -> marktanteil_<klassifikation>_<sample>_umfaenge_<format>.png
  (Spalten alle Videos + Zusatz-Umfaenge); "beide" -> beides. Der Namenszusatz
  (_<umfang> bzw. _umfaenge) gilt genauso fuer die ..._absolut- und
  ..._kombiniert-Varianten unten (z. B. marktanteil_<klassifikation>_kombiniert_krieg_<format>.png)
- marktanteil_<klassifikation>_kombiniert_<format>.png  (nur bei
  KOMBI_VERSION "kombi"/"alle"; gleicher Aufbau wie marktanteil_<klassifikation>_<sample>_...,
  Hauptlinie + Monatspunkte = Sample "alle", gestrichelte LOWESS-Linie in
  derselben Farbe = Sample "vorkrieg"; zeigt direkt, wie viel einer
  Verschiebung auf erst spaeter gestartete Kanaele zurueckgeht; bei
  ABSOLUT_VERSION zusaetzlich ..._kombiniert_<format>_absolut.png, dort ist
  der Abstand beider Linien direkt der Beitrag der spaeteren Kanaele)
- marktanteil_<klassifikation>_<sample>_<format>_absolut.png  (nur bei
  ABSOLUT_VERSION: gleicher Aufbau, oben Views in Mio., unten Uploads absolut)
- uploads_vs_views_<klassifikation>_<umfang>_<sample>_<format>.png  (fuer die
  Umfaenge in STREU_UMFAENGE und die Gruppen in STREU_GRUPPEN, Default ÖRR,
  traditionelle Medien, Alternative rechts: x = Upload-Anteil, y = Views-Anteil;
  blasse Punkte = Monatswerte, verbundene Marker = Mittel je STREU_INTERVALL-
  Monats-Block ab STREU_START, Default halbjaehrlich ab Monat -24; oberhalb
  der Diagonale mehr Views pro Video als der Schnitt aller Gruppen; duenne
  Parallelen y = x + c im Abstand STREU_DIAGONAL_ABSTAND pp zeigen, ob sich
  Upload- oder Views-Anteil staerker veraendert; kommt keine der STREU_GRUPPEN
  im Sample vor, entfaellt das Streudiagramm mit Hinweis). Je nach STREU_LAYOUT
  zusaetzlich/stattdessen ..._getrennt.png: ein Panel je Gruppe, jedes nach
  STREU_ZOOM auf seine eigenen Daten gezoomt (Massstab je Panel verschieden,
  innerhalb eines Panels x = y), Diagonalen am Rand mit c (pp) beschriftet)
- marktanteil_monat.csv  (alle Monatswerte inkl. angebot_anteil, Long-Format,
  Spalten monat_start/monat_ende = Datumsbereich inklusive, z. B. Monat 0 =
  24.02.2022-23.03.2022; bei QUARTALSWEISE marktanteil_quartal.csv mit Spalten
  rel_quartal, quartal_start, quartal_ende)
- marktanteil_woche.csv  (nur bei WOECHENTLICH: dieselben Werte je Woche relativ
  zum Kriegsbeginn, Spalten rel_woche, woche_start, woche_ende (Do-Mi, inklusive);
  Woche 0 = [24.02.2022, 03.03.2022); nur Wochen vollstaendig im Monats-/
  Quartalsfenster, Mindestbesetzung MIN_VIDEOS_PRO_WOCHE; keine Grafiken. Gleicher
  Zusatz _manuell/_oerrdoku wie die Monats-CSV, unabhaengig von QUARTALSWEISE)
- Wochenweise Zeitreihen (nur bei WOCHEN_PLOT): dieselben Zeitreihen-Grafiken wie
  oben (KOMBI_VERSION, UMFANG_ZUSATZ/-LAYOUT, ABSOLUT_VERSION, INTERAKTIV gelten
  genauso), aber je Woche (rel_woche, Woche 0 = 24.02.-02.03.2022, Do-Mi) im eigenen
  Fenster WOCHEN_FENSTER (Datum oder rel_woche, unabhaengig von PERIODE_MIN/-MAX und
  QUARTALSWEISE): marktanteil_<klassifikation>_<sample|kombiniert>[_<umfang>]_<format>_woche_<JJJJMMTT>-<JJJJMMTT>[_absolut].png,
  Werte in marktanteil_woche_<JJJJMMTT>-<JJJJMMTT>.csv. Mindestbesetzung
  MIN_VIDEOS_PRO_WOCHE, Glaettung WOCHEN_LOWESS_FRAC (0 = ungeglaettet), dazu
  optional eine duenne, halbtransparente LOWESS-Linie im Hintergrund
  (WOCHEN_LOWESS_HINTERGRUND, 0 = keine; nur Hauptlinie, nicht Vergleich), keine
  BETONUNG_MONATE; x-Achse mit Wochennummer und Datum des Wochenbeginns.
- marktanteil_methodik.md  (Methodik, Fallzahlen, Phasenmittel Views und Uploads;
  bei QUARTALSWEISE marktanteil_methodik_quartal.md)
Bei QUARTALSWEISE tragen alle PNG-Namen hinter <format> den Zusatz _quartal.
- interaktiv/<name>.html  (nur bei INTERAKTIV, Plotly): je Zeitreihen- und
  Streudiagramm-PNG eine HTML-Fassung gleichen Namens (Streudiagramm nur als
  gemeinsame Grafik, Zoom statt _getrennt). Hover zeigt je Monats-/Quartalspunkt
  Gruppe, Periode mit Datumsbereich, Views-/Upload-Anteil, Views und Videos, auf
  den Intervallmitteln das Intervall und beide Mittelwerte; Legendenklick blendet
  Gruppen aus. plotly.min.js liegt einmal daneben (offline lesbar, Ordner nur
  komplett weitergeben).
- kanalindex_<klassifikation>_<format>.png, kanalindex_<periode>.csv,
  kanalindex_methodik.md  (nur bei KANALINDEX, siehe unten)

Robustheitsvariante Kanalindex (KANALINDEX = True)
--------------------------------------------------
Die gepoolten Anteile werden von wenigen grossen Kanaelen bestimmt (z. B.
WELT/BILD/SPIEGEL bei den Traditionellen). Der Kanalindex normiert deshalb die
Views jedes Kanals auf dessen eigenes Vorkriegsniveau (nur Umfang alle Videos,
Sample = alle Kanaele mit ausreichender Basis):

    basis_c   = mittlere Views je Periode von Kanal c in KANALINDEX_BASIS (Perioden ohne Upload = 0)
    index_ct  = views_ct / basis_c * 100 (gekappt bei KANALINDEX_KAPPUNG)
    anteil_gt = sum_{c in g} index_ct * basis_c^e / sum_c index_ct * basis_c^e * 100

mit e = 1 ("linear", ungekappt = gepoolte Views der Basis-Kanaele), 0.5
("wurzel", gedaempft) oder 0 ("gleich", jeder Kanal zaehlt gleich). Kanaele mit
Upload in weniger als KANALINDEX_MIN_AKTIV der Basisperioden (v. a. spaeter
gestartete) fallen raus. Grafik: oben je Gewichtung eine Spalte mit den
Anteilen, unten Median-Index je Gruppe und Anteil der Kanaele ueber ihrer Basis.
kanalindex_methodik.md enthaelt Phasenmittel (inkl. gepoolter Hauptgrafik zum
Vergleich) und den Index je Kanal und Phase. Keine HTML-Fassung bei INTERAKTIV.

Ausfuehren aus dem Repo-Root:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.marktanteil_rohdaten_plots
"""

import re

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, MultipleLocator
from statsmodels.nonparametric.smoothers_lowess import lowess

from youtube_code.config import OUTPUTS, STATA_OUTPUT
from youtube_code.step3_topic_relevance.topic_keywords import TOPIC_KEYWORDS
from youtube_code.step6_auswertung.prepare_channel_scores import KRIEGSBEGINN, relativ_periode
# from scripts.adhoc.zufallsstichprobe_videos import KANAELE


# =========================================================
# CONFIG
# =========================================================

ROHDATEN_PFAD = OUTPUTS / "stata_rohdaten"
PFAD_PLOTS = OUTPUTS / "segment_analysis" / "plots_marktanteil_rohdaten"

# Format (long vs. short)
FORMAT = ["long"]

# Einschraenkung des Kanal-Samples auf eine Liste von channel_ids (Strings wie in
# kanaele_roh.channel_id); leere Liste = keine Einschraenkung. Gilt fuer alle
# SAMPLES; Medientyp x Ideologie wird vorher auf allen Kanaelen gebildet,
# Tertilgrenzen und Populismus-Median auf den Kanaelen dieser Liste.
# Codes der manuell gepflegten Spalte "sample" in channels_check.xlsx (auch Blatt "Codebuch"):
#   0 = keiner Gruppe zugeordnet
#   1 = uploadstarke News-Kanaele mit hohem Politikfokus, ohne regionalen Fokus
#   2 = politische Recherche-/Magazin-/Doku-Kanaele (>= 35 % der Views politisch laut
#       YouTube-Klassifikation, lange Videos ab 24.01.2020)
#   3 = Nachrichtenkanaele mit regionalem Fokus
#   4 = kein eigener Content (Verbreitung von Ausschnitten aus Interviews, Reden etc.)
#   5 = Recherche/Doku mit ueberwiegend unpolitischem Content (< 35 % politische Views);
#       nur fuer Robustheitschecks

df = pd.read_excel(STATA_OUTPUT / "channels_check.xlsx")
cats = [1,2,5]
df = df[df["media_category"].isin(cats)]
print(df["sample"].describe())
df = df[(df["sample"].isin([1,2,3])) & (df["foreign"] != 1)]
CHANNELS = df["channel_id"].tolist()
print(f"Number of channels: {len(CHANNELS)}")

KANALLISTE = CHANNELS

# Robustheitscheck: einzelne Kanaele aus dem Sample ausschliessen, um zu pruefen, ob
# sie den Verlauf ihrer Gruppe treiben. Eintraege = channel_id (z. B. "UC...") ODER
# Kanaltitel (kanal_name in kanaele_roh bzw. channel_title in channels_check.xlsx;
# exakter Titel, Gross-/Kleinschreibung und Leerzeichen am Rand egal); beides mischbar.
# Leere Liste = kein Ausschluss. Unbekannte oder mehrdeutige Titel -> Abbruch mit
# Vorschlaegen. Gruppen, Tertilgrenzen und Populismus-Median werden VOR dem Ausschluss
# gebildet (gleiche Gruppendefinition wie im Lauf ohne Ausschluss, es faellt nur der
# Beitrag dieser Kanaele weg). Ausgabedateien tragen den Zusatz _ohne_<kanal>
# (bis 3 Kanaele, Titel gekuerzt) bzw. _ohne<N>kanaele.
# Beispiel: ["UCxxxxxxxxxxxxxxxxxxxxxx", "WELT Nachrichtensender"]
KANAELE_AUSSCHLIESSEN = [] # "Vermietertagebuch - Alexander Raue", "Achtung, Reichelt!"

# Robustheitscheck (True/False): Kanaele ohne Gruppe in medientyp_ideologie (kein
# medientyp bzw. keine Ideologie-Baseline in kanaele_roh), die in channels_check.xlsx
# vorlaeufig manuell mit media_category == 5 (= alternativ rechts) codiert sind,
# der Gruppe "Alternative (rechts)" zuordnen. Partei/Politiker-Kanaele bleiben
# ausgeschlossen. Die Liste der betroffenen Kanaele wird immer ausgegeben; bei True
# tragen alle Ausgabedateien den Zusatz _manuell.
MANUELL_ALT_RECHTS = True

# ÖRR-Kanaele mit diesen sample-Codes aus channels_check.xlsx als eigene Gruppe
# OERR_DOKU_GRUPPE zeigen (getrennt von tagesschau, phoenix usw.); Codes 0-5,
# z. B. [2] (politische Recherche/Doku) oder [2, 5]; leere Liste = eine
# gemeinsame ÖRR-Linie. Die Codes muessen ueber KANALLISTE im Sample sein. Bei
# nicht leerer Liste tragen alle Ausgabedateien den Zusatz _oerrdoku.
OERR_DOKU_CODES = []
OERR_DOKU_GRUPPE = "ÖRR (Recherche/Doku)"
OERR_DOKU_FARBE = "#9cc3ee"   # helleres ÖRR-Blau

# Monat 0 = [24.02.2022, 24.03.2022). Daten reichen vom 01.01.2019 bis 30.06.2026,
# -37 und 51 sind die aeussersten vollstaendig abgedeckten Monate.
PERIODE_MIN = -37
PERIODE_MAX = 51
# Mindestzahl Videos je Periode (Monat bzw. Quartal, alle Gruppen zusammen)
MIN_VIDEOS_PRO_MONAT = 20
GLAETTUNG_LOWESS_FRAC = 0

# Quartalsweise statt monatliche Betrachtung. True/False.
# True: Quartale relativ zum Kriegsbeginn (Quartal 0 = [24.02.2022, 24.05.2022),
# Quartal -1 = [24.11.2021, 24.02.2022) usw.), KEINE LOWESS-Glaettung (Quartalswerte
# direkt verbunden), keine BETONUNG_MONATE. PERIODE_MIN/-MAX, PHASEN, STREU_START und
# STREU_INTERVALL bleiben in Monaten angegeben; verwendet werden nur Quartale, die
# vollstaendig in den jeweiligen Monatsbereich fallen (z. B. -37..51 -> Quartale -12..16).
# STREU_START und STREU_INTERVALL muessen dann durch 3 teilbar sein. Alle Ausgabedateien
# bekommen den Zusatz _quartal (CSV: marktanteil_quartal.csv, Spalte rel_quartal).
QUARTALSWEISE = True
# Zusaetzlich Wochenwerte als Tabelle marktanteil_woche<zusatz>.csv (keine Grafiken),
# gleiche Samples/Klassifikationen/Umfaenge/Formeln wie die Monats-CSV. True/False.
# Woche k = [24.02.2022 + 7k Tage, + 7 Tage), also Donnerstag bis Mittwoch, Woche 0
# beginnt am Kriegsbeginn; nur Wochen, die vollstaendig im Fenster PERIODE_MIN..
# PERIODE_MAX (bzw. dessen Quartalen) liegen. Mindestbesetzung MIN_VIDEOS_PRO_WOCHE.
WOECHENTLICH = False
MIN_VIDEOS_PRO_WOCHE = 20   # Mindestzahl Videos je Woche (alle Gruppen zusammen), >= 1
# Wochenweise Zeitreihen-Grafiken mit eigenem Zeitfenster WOCHEN_FENSTER
# (marktanteil_..._<format>_woche_<JJJJMMTT>-<JJJJMMTT>.png, Tabelle
# marktanteil_woche_<JJJJMMTT>-<JJJJMMTT>.csv). Uebernimmt alle uebrigen Einstellungen
# (Klassifikationen, Samples, KOMBI_VERSION, ABSOLUT_VERSION, UMFANG_ZUSATZ/-LAYOUT,
# ANGEBOT_METRIK, EREIGNISSE, INTERAKTIV, KANALLISTE, KANAELE_AUSSCHLIESSEN usw.),
# ist aber unabhaengig von PERIODE_MIN/-MAX, QUARTALSWEISE und WOECHENTLICH.
# Mindestbesetzung MIN_VIDEOS_PRO_WOCHE; keine BETONUNG_MONATE. True/False.
WOCHEN_PLOT = False
# (von, bis), inklusive: je ein Datum "JJJJ-MM-TT" (= die Woche, die das Datum enthaelt)
# oder eine ganze Zahl rel_woche (Woche 0 = 24.02.-02.03.2022, Do-Mi); mischbar, von <= bis.
# Muss innerhalb der Daten liegen (01.01.2019 bis 30.06.2026).
WOCHEN_FENSTER = ("2022-01-01", "2022-12-31")
# LOWESS-Glaettung der Wochenwerte: Anteil der Punkte je Fenster, 0 <= x <= 1;
# 0 = keine Glaettung (Wochenwerte als Linie verbunden).
WOCHEN_LOWESS_FRAC = 0
# Zusaetzliche duenne LOWESS-Linie im Hintergrund der Wochengrafiken (gleiche Farbe,
# halbtransparent, nur Hauptlinie, nicht die gestrichelte Vergleichslinie):
# Anteil der Punkte je Fenster, 0 < x <= 1 (z. B. 0.3); 0 = keine Hintergrundlinie.
WOCHEN_LOWESS_HINTERGRUND = 0.15
# Monatswerte um den Kriegsbeginn hervorheben, die die LOWESS-Linie verwischt:
# (von, bis) in rel_monat, inklusive, von <= -1 < 0 <= bis; die Punkte werden
# dort groesser und deckend gezeichnet und mit einer duennen Linie verbunden.
# None = keine Hervorhebung.
BETONUNG_MONATE = (-3, 3)

# Untere Grafikreihe (Angebot = hochgeladene Videos je Gruppe und Monat):
# "anteil" = Anteil an allen Uploads der Klassifikation (%), direkt mit dem
#            Views-Marktanteil der oberen Reihe vergleichbar;
# "anzahl" = absolute Zahl der Uploads (haengt stark von der Kanalzahl je Gruppe ab).
ANGEBOT_METRIK = "anteil"

# Weitere senkrechte Linien in den Zeitreihen-Grafiken (marktanteil_*.png):
# {Beschriftung: "JJJJ-MM-TT"}; Daten ausserhalb der mit Daten belegten Monate
# werden uebersprungen; leeres Dict = nur Kriegsbeginn.
EREIGNISSE = {
    # "US-Wahl 2020": "2020-11-03",
    "BTW 2021 / RT DE deleted": "2021-09-26",
    "US-Wahl 2024 / Ampel Ende": "2024-11-05",
    "BTW 2025": "2025-02-23",
    "KenFM deleted": "2021-01-22",
    # "RT DE deleted": "2021-09-28",
    # "Ende Ampelkoalition": "2024-11-06"
}

# Zusaetzliche Grafik mit absoluten Zahlen (..._absolut.png): oben Views je Gruppe
# und Monat (Mio.), unten Uploads je Gruppe und Monat. True/False.
ABSOLUT_VERSION = True

# Welche Zeitreihen-Grafiken (marktanteil_*.png) je Sample erzeugt werden:
# "kombi"    = nur die kombinierte Grafik (..._kombiniert_....png): Sample "alle"
#              als Hauptlinie mit Monatspunkten, Sample "vorkrieg" gestrichelt in
#              derselben Farbe (nur Linie);
# "getrennt" = nur die getrennten Grafiken je Sample (..._alle_... und ..._vorkrieg_...);
# "alle"     = beide Varianten.
# Gilt jeweils auch fuer ABSOLUT_VERSION (..._absolut.png). Streudiagramme,
# CSV und Methodik-Datei entstehen unabhaengig davon fuer beide Samples.
KOMBI_VERSION = "kombi"

# Hauptgrafiken (marktanteil_<klassifikation>_<sample>_<format>.png) zeigen nur
# "Alle Videos". Zusaetzliche Umfaenge (Schluessel aus UMFAENGE ausser "alle":
# "politisch", "politisch_kw", "krieg"; leere Liste = nur Hauptgrafiken):
UMFANG_ZUSATZ = []
# Darstellung der Zusatz-Umfaenge (gilt auch fuer ABSOLUT_VERSION/KOMBI_VERSION):
# "einzeln"    = je Umfang eine eigene Grafik (..._<sample>_<umfang>_<format>.png);
# "kombiniert" = eine Grafik mit Spalten "Alle Videos" + Zusatz-Umfaenge
#                (..._<sample>_umfaenge_<format>.png, Aufbau wie frueher);
# "beide"      = beide Varianten.
UMFANG_LAYOUT = "einzeln"

# Grafiken (Zeitreihen + Streudiagramme) auch fuer die Populismus-Tertile
# erzeugen; False = nur Medientyp x Ideologie (Tertile entfallen dann auch in
# marktanteil_monat.csv und der Methodik-Datei). True/False.
POPULISMUS_TERTILE = False
# Grafiken (Zeitreihen + Streudiagramme) fuer "populismus_median": ÖRR, traditionelle
# Medien und alternative Medien geteilt am Median von pop_baseline (Median nur ueber
# die alternativen Kanaele im Sample nach KANALLISTE). False = Klassifikation entfaellt. True/False.
POPULISMUS_MEDIAN = True
# Grafiken (Zeitreihen + Streudiagramme) fuer "medientyp_gesamt": ÖRR, traditionelle
# Medien und alle alternativen Medien als EINE Gruppe, nach der manuellen
# media_category in channels_check.xlsx (1 = ÖRR, 2 = traditionell, 3/4/5 =
# alternativ; 6 und ohne Code fallen raus). False = Klassifikation entfaellt. True/False.
MEDIENTYP_GESAMT = False

# Mindestbreite der Zeitreihen-Grafiken in Zoll (> 0); greift v. a. bei den
# einspaltigen Grafiken, mehrspaltige sind 5.2 Zoll je Spalte breit (falls groesser).
GRAFIK_MINDESTBREITE = 14.0

# Zusaetzlich interaktive HTML-Fassungen (Plotly) aller Zeitreihen- und
# Streudiagramme nach PFAD_PLOTS / "interaktiv": Hover zeigt je Punkt Gruppe,
# Periode mit Datumsbereich, Views-/Upload-Anteil, Views und Videos; Zoom,
# Gruppen per Legendenklick ausblendbar. Die PNGs bleiben unveraendert.
# Benoetigt das Paket plotly. True/False.
INTERAKTIV = False

# Streudiagramm Upload-Anteil (x) vs. Views-Anteil (y): fuer welche(n) Umfang/Umfaenge
# (Schluessel aus UMFAENGE: "alle", "politisch", "politisch_kw", "krieg"; leere Liste = keins).
STREU_UMFAENGE = []
# Gezeigte Gruppen je Klassifikation (Namen aus KLASSIFIKATIONEN[...]["gruppen"]);
# Klassifikationen ohne Eintrag bekommen kein Streudiagramm. Die Anteile bleiben
# Anteile an ALLEN Gruppen der Klassifikation (Nenner unveraendert).
STREU_GRUPPEN = {
    "medientyp_ideologie": ["ÖRR", "Traditionelle Medien", "Alternative (rechts)"],
}
# Zeitintervalle der Trajektorie: ab STREU_START (rel_monat, >= PERIODE_MIN) in
# Bloecken zu STREU_INTERVALL Monaten bis PERIODE_MAX (letzter Block ggf. kuerzer).
STREU_START = -3
STREU_INTERVALL = 6   # 6 = halbjaehrlich
# Abstand (Prozentpunkte) der duennen Hilfslinien parallel zur Diagonale (y = x + c);
# laeuft eine Trajektorie parallel dazu, aendern sich Upload- und Views-Anteil um
# gleich viele pp. 0 = keine Hilfslinien.
STREU_DIAGONAL_ABSTAND = 5
# "gemeinsam" = alle Gruppen in einer Grafik; "getrennt" = ein Panel je Gruppe
# (jedes eigens gezoomt); "beide" = beide Dateien.
STREU_LAYOUT = "beide"
# Zoom der getrennten Panels: "intervalle" = auf die Intervallmittel (Trajektorie),
# Monatswerte ausserhalb werden abgeschnitten; "monate" = alle Monatswerte sichtbar.
# Jedes Panel bekommt seinen eigenen Achsenabschnitt (quadratisch, x und y gleich
# lang -> Diagonalen bleiben 45°), die Massstaebe unterscheiden sich zwischen Panels.
STREU_ZOOM = "intervalle"

# Umfang "politisch_kw": ein Video gilt als politisch, wenn mindestens eine der
# Titel-Stichwortsuchen rel_<thema>_<KEYWORD_VARIANTE> aus videos_roh anschlaegt.
# KEYWORD_THEMEN = Schluessel aus topic_keywords.TOPIC_KEYWORDS (nicht leer);
# KEYWORD_VARIANTE = "core" (nur core-Liste) oder "cw" (core oder wide).
KEYWORD_THEMEN = list(TOPIC_KEYWORDS)
KEYWORD_VARIANTE = "cw"

IDEOLOGIE_SCHNITTE = (-0.5, 0.5)   # wie deskriptiv_aggregation.IDEOLOGIE_SCHNITTE

MEDIENTYP_ALT = "Creator & alternative Medien"
MEDIENTYP_OERR = "ÖRR"
MEDIENTYP_TRAD = "traditionelle Medien"

# Phasen fuer die Mittelwert-Tabelle in der Methodik-Datei (rel_monat, inklusive)
PHASEN = {
    "Vorkrieg (-13 bis -1)": (-25, -1),
    "Jahr 1 (0 bis 11)": (0, 11),
    "Jahr 2 (12 bis 23)": (12, 23),
    "Jahr 3 (24 bis 35)": (24, 35),
    "Jahr 4+ (36 bis 51)": (36, 51),

}

# Robustheitsvariante "Kanalindex" (kanalindex_<klassifikation>_<format>.png,
# kanalindex_<periode>.csv, kanalindex_methodik.md): Views je Kanal auf dessen
# Vorkriegsniveau normiert, damit nicht wenige grosse Kanaele die Gruppenanteile
# bestimmen (Formeln im Moduldocstring). Nur Umfang "alle Videos". True/False.
KANALINDEX = False
# Basiszeitraum in rel_monat (von, bis), inklusive, PERIODE_MIN <= von <= bis <= -1;
# Basis eines Kanals = mittlere Views je Periode in diesem Zeitraum
KANALINDEX_BASIS = (-25, -1)
# Mindestanteil der Basisperioden mit mindestens einem Upload (0 < x <= 1);
# Kanaele darunter (z. B. erst kurz vor Kriegsbeginn gestartet) fallen raus
KANALINDEX_MIN_AKTIV = 0.5
# Gewichtung der Kanaele in den Gruppenanteilen (nicht leer, Teilmenge von):
# "linear" = Gewicht Basis-Views (ohne Kappung identisch mit gepoolten Views der Basis-Kanaele),
# "wurzel" = Gewicht Wurzel der Basis-Views (gedaempft), "gleich" = jeder Kanal Gewicht 1
KANALINDEX_GEWICHTUNGEN = ["linear", "wurzel", "gleich"]
# Obergrenze des Index (Basis = 100) gegen Ausreisser kleiner Kanaele; Zahl > 100 oder None
KANALINDEX_KAPPUNG = 1000

# =========================================================
# CONFIG ENDE
# =========================================================

UMFAENGE = {
    "alle": ("Alle Videos", lambda v: pd.Series(True, index=v.index)),
    "politisch": ("Politische Videos", lambda v: v["politisch"] == "ja"),
    "politisch_kw": ("Politische Videos (Stichworte)", lambda v: v["politisch_kw"] == "ja"),
    "krieg": ("Kriegsvideos", lambda v: v["krieg"] == "ja"),
}

SAMPLES = {
    "alle": ("alle Kanäle", lambda k: pd.Series(True, index=k.index)),
    "vorkrieg": ("nur vor Kriegsbeginn aktive Kanäle", lambda k: k["sample_vorkrieg"] == "ja"),
}

# Farben: kategorisch in fester Reihenfolge (validierte Referenzpalette des
# dataviz-Skills), Tertile sequentiell in einem Farbton (hell -> dunkel).
KLASSIFIKATIONEN = {
    "medientyp_ideologie": {
        "titel": "Medientyp und Ideologie",
        "gruppen": ["ÖRR", "Traditionelle Medien", "Alternative (links)",
                    "Alternative (mitte)", "Alternative (rechts)"],
        "farben": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"],
    },
    "populismus_tertile": {
        "titel": "Populismus-Baseline (Tertile)",
        "gruppen": ["Tertil 1 (niedrig)", "Tertil 2 (mittel)", "Tertil 3 (hoch)"],
        "farben": ["#9cc3ee", "#2a78d6", "#0d3a73"],
    },
    "populismus_median": {
        "titel": "Alternative Medien nach Populismus-Median",
        "gruppen": ["ÖRR", "Traditionelle Medien", "Alternative (unter Median)",
                    "Alternative (über Median)"],
        "farben": ["#2a78d6", "#eb6834", "#eda100", "#e87ba4"],
    },
    "medientyp_gesamt": {
        "titel": "Medientyp (alternative Medien zusammengefasst)",
        "gruppen": ["ÖRR", "Traditionelle Medien", "Alternative Medien"],
        "farben": ["#2a78d6", "#eb6834", "#1baf7a"],
    },
}
SCHALTER = {"populismus_tertile": "POPULISMUS_TERTILE", "populismus_median": "POPULISMUS_MEDIAN",
            "medientyp_gesamt": "MEDIENTYP_GESAMT"}
# media_category (channels_check.xlsx) -> Gruppe in "medientyp_gesamt"
MEDIA_CATEGORY_GESAMT = {1: "ÖRR", 2: "Traditionelle Medien",
                         3: "Alternative Medien", 4: "Alternative Medien", 5: "Alternative Medien"}


# =========================================================
# Zeitliche Aufloesung (Monat oder Quartal, siehe QUARTALSWEISE)
# =========================================================

def monate_pro_periode():
    return 3 if QUARTALSWEISE else 1


def periode_name():
    return "quartal" if QUARTALSWEISE else "monat"


# Zusatz fuer KANAELE_AUSSCHLIESSEN (_ohne_...), wird in main() nach dem Aufloesen
# der Kanaele gesetzt; bleibt leer, wenn main() nicht laeuft (Import durch andere Skripte)
_AUSSCHLUSS_ZUSATZ = ""


def datei_zusatz():
    """Zusatz fuer alle Ausgabedateien: _manuell (MANUELL_ALT_RECHTS), _oerrdoku
    (OERR_DOKU_CODES), _ohne_... (KANAELE_AUSSCHLIESSEN, erst nach main() gesetzt)."""
    return (("_manuell" if MANUELL_ALT_RECHTS else "") + ("_oerrdoku" if OERR_DOKU_CODES else "")
            + _AUSSCHLUSS_ZUSATZ)


def ausschluss_zusatz(ausschluss):
    """Dateizusatz fuer die tatsaechlich ausgeschlossenen Kanaele: bis 3 Kanaele
    _ohne_<titel1>_<titel2>... (Titel klein, nur a-z0-9, max. 20 Zeichen), sonst _ohne<N>kanaele."""
    if ausschluss.empty:
        return ""
    if len(ausschluss) > 3:
        return f"_ohne{len(ausschluss)}kanaele"
    ersatz = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
    teile = [re.sub(r"[^a-z0-9]+", "", t.lower().translate(ersatz))[:20] or c
             for c, t in zip(ausschluss["channel_id"], ausschluss["titel"])]
    return "_ohne_" + "_".join(teile)


def setze_oerr_doku_gruppe():
    """Fuegt OERR_DOKU_GRUPPE (hinter "ÖRR") in KLASSIFIKATIONEN["medientyp_ideologie"]
    ein bzw. entfernt sie bei leerem OERR_DOKU_CODES (wiederholte main()-Aufrufe)."""
    cfg = KLASSIFIKATIONEN["medientyp_ideologie"]
    if OERR_DOKU_GRUPPE in cfg["gruppen"]:
        i = cfg["gruppen"].index(OERR_DOKU_GRUPPE)
        del cfg["gruppen"][i], cfg["farben"][i]
    if OERR_DOKU_CODES:
        i = cfg["gruppen"].index("ÖRR") + 1
        cfg["gruppen"].insert(i, OERR_DOKU_GRUPPE)
        cfg["farben"].insert(i, OERR_DOKU_FARBE)


def perioden_bereich(von, bis):
    """Monatsbereich (rel_monat, inklusive) -> Bereich der Perioden, die
    vollstaendig darin liegen (bei Monaten unveraendert)."""
    m = monate_pro_periode()
    return -(-von // m), (bis + 1) // m - 1


# =========================================================
# SCHRITT 1: Daten laden und Gruppen bilden
# =========================================================

def lade_kanaele():
    k = pd.read_stata(ROHDATEN_PFAD / "kanaele_roh.dta")
    for c in ["medientyp", "sample_vorkrieg"]:
        k[c] = k[c].astype(str)
    print(f"[Kanaele] {len(k)} Kanaele; Medientyp: {k['medientyp'].value_counts().to_dict()}")
    return k


def bilde_gruppen(k):
    """Haengt je Klassifikation eine Gruppenspalte an (NaN = nicht zugeordnet).
    Gibt zusaetzlich die Tertilgrenzen zurueck."""
    k = k.copy()
    medien = k["medientyp"].isin([MEDIENTYP_OERR, MEDIENTYP_TRAD, MEDIENTYP_ALT])

    ideo = pd.cut(k["ideo_gesellschaft_baseline"],
                  bins=[-np.inf, *IDEOLOGIE_SCHNITTE, np.inf], labels=["links", "mitte", "rechts"])
    g1 = pd.Series(np.nan, index=k.index, dtype=object)
    g1[k["medientyp"] == MEDIENTYP_OERR] = "ÖRR"
    if OERR_DOKU_CODES:
        check = pd.read_excel(STATA_OUTPUT / "channels_check.xlsx", usecols=["channel_id", "sample"])
        doku = set(check.loc[check["sample"].isin(OERR_DOKU_CODES), "channel_id"])
        g1[(k["medientyp"] == MEDIENTYP_OERR) & k["channel_id"].isin(doku)] = OERR_DOKU_GRUPPE
    g1[k["medientyp"] == MEDIENTYP_TRAD] = "Traditionelle Medien"
    ist_alt = (k["medientyp"] == MEDIENTYP_ALT) & ideo.notna()
    g1[ist_alt] = "Alternative (" + ideo[ist_alt].astype(str) + ")"
    k["medientyp_ideologie"] = g1

    k, grenzen = bilde_tertil_gruppen(k)
    k, _ = bilde_median_gruppen(k)
    k = bilde_medientyp_gesamt(k)

    for name in KLASSIFIKATIONEN:
        print(f"[Gruppen] {name}: {k[name].value_counts().to_dict()}, "
              f"nicht zugeordnet: {int(k[name].isna().sum())}")
    print(f"[Gruppen] Tertilgrenzen pop_baseline (alle Kanaele): {grenzen[0]:.3f} / {grenzen[1]:.3f}")
    return k, grenzen


def bilde_tertil_gruppen(k):
    """Spalte populismus_tertile: OeRR, traditionelle und alternative Medien mit
    pop_baseline, in Tertile nach pop_baseline ueber genau diese Kanaele in k
    (ungewichtet). Wird in main() nach KANALLISTE erneut aufgerufen, damit die
    Grenzen nur auf dem tatsaechlichen Sample beruhen. Gibt (k, Grenzen) zurueck."""
    k = k.copy()
    mit_pop = (k["medientyp"].isin([MEDIENTYP_OERR, MEDIENTYP_TRAD, MEDIENTYP_ALT])
               & k["pop_baseline"].notna())
    grenzen = k.loc[mit_pop, "pop_baseline"].quantile([1 / 3, 2 / 3]).to_list()
    g2 = pd.Series(np.nan, index=k.index, dtype=object)
    g2[mit_pop] = pd.qcut(k.loc[mit_pop, "pop_baseline"], 3,
                          labels=KLASSIFIKATIONEN["populismus_tertile"]["gruppen"]).astype(str)
    k["populismus_tertile"] = g2
    return k, grenzen


def bilde_median_gruppen(k):
    """Spalte populismus_median: OeRR und traditionelle Medien (alle) sowie alternative
    Medien (Gruppe "Alternative (...)" in medientyp_ideologie) mit pop_baseline, geteilt
    am Median von pop_baseline ueber genau diese alternativen Kanaele in k ("über" =
    > Median). Wird in main() nach KANALLISTE/MANUELL_ALT_RECHTS erneut aufgerufen,
    damit der Median nur auf dem tatsaechlichen Sample beruht. Gibt (k, Median) zurueck."""
    k = k.copy()
    alt_pop = k["medientyp_ideologie"].str.startswith("Alternative", na=False) & k["pop_baseline"].notna()
    median = k.loc[alt_pop, "pop_baseline"].median()
    g3 = pd.Series(np.nan, index=k.index, dtype=object)
    g3[k["medientyp"] == MEDIENTYP_OERR] = "ÖRR"
    g3[k["medientyp"] == MEDIENTYP_TRAD] = "Traditionelle Medien"
    g3[alt_pop] = np.where(k.loc[alt_pop, "pop_baseline"] > median,
                           "Alternative (über Median)", "Alternative (unter Median)")
    k["populismus_median"] = g3
    return k, median


def bilde_medientyp_gesamt(k):
    """Spalte medientyp_gesamt aus der manuellen media_category in channels_check.xlsx
    (MEDIA_CATEGORY_GESAMT; andere/fehlende Codes = NaN). Gibt die Abweichung zu
    medientyp aus kanaele_roh auf der Konsole aus."""
    k = k.copy()
    check = pd.read_excel(STATA_OUTPUT / "channels_check.xlsx", usecols=["channel_id", "media_category"])
    doppelt = check["channel_id"].duplicated(keep=False)
    if doppelt.any():
        raise SystemExit(f"channels_check.xlsx: channel_id mehrfach vorhanden: "
                         f"{sorted(check.loc[doppelt, 'channel_id'].unique())}")
    kat = k["channel_id"].map(check.set_index("channel_id")["media_category"])
    k["medientyp_gesamt"] = kat.map(MEDIA_CATEGORY_GESAMT)
    print(f"[medientyp_gesamt] media_category -> Gruppe vs. medientyp (kanaele_roh):")
    tab = pd.crosstab(k["medientyp_gesamt"].fillna("nicht zugeordnet"), k["medientyp"])
    print(tab.rename_axis(index=None, columns=None).to_string())
    return k


def berichte_populismus(k, aktive):
    """Konsolenausgabe je Sample fuer die aktiven Populismus-Klassifikationen:
    Tertile = Medien-Kanaele (OeRR, traditionell, alternativ), die mangels
    pop_baseline herausfallen, und Tertil x Medientyp; Median = Kanaele je Gruppe
    (alternative Medien ohne pop_baseline fallen heraus)."""
    kurz = {MEDIENTYP_OERR: "ÖRR", MEDIENTYP_TRAD: "traditionell", MEDIENTYP_ALT: "alternativ"}
    for s_key, (s_label, s_filter) in SAMPLES.items():
        ks = k[s_filter(k) & k["medientyp"].isin(kurz)]
        ohne = ks["pop_baseline"].isna()
        if "populismus_tertile" in aktive:
            print(f"[Tertile] {s_label}: {len(ks)} Medien-Kanaele, davon {int(ohne.sum())} ohne pop_baseline "
                  f"ausgeschlossen {ks.loc[ohne, 'medientyp'].map(kurz).value_counts().to_dict()}")
            tab = pd.crosstab(ks.loc[~ohne, "populismus_tertile"], ks.loc[~ohne, "medientyp"].map(kurz),
                              margins=True, margins_name="Summe")
            tab = tab.reindex(index=[*KLASSIFIKATIONEN["populismus_tertile"]["gruppen"], "Summe"],
                              columns=[*kurz.values(), "Summe"], fill_value=0)
            print(tab.rename_axis(index=None, columns=None).to_string())
        if "populismus_median" in aktive:
            s = k[s_filter(k)]
            n_alt_ohne = int((s["medientyp_ideologie"].str.startswith("Alternative", na=False)
                              & s["pop_baseline"].isna()).sum())
            gruppen = s["populismus_median"].value_counts().reindex(
                KLASSIFIKATIONEN["populismus_median"]["gruppen"], fill_value=0).to_dict()
            print(f"[Median] {s_label}: {gruppen}; {n_alt_ohne} alternative Kanaele ohne "
                  "pop_baseline ausgeschlossen")


def manuell_alt_rechts(k):
    """Kanaele ohne medientyp_ideologie-Gruppe (ausser Partei/Politiker), die in
    channels_check.xlsx manuell als media_category == 5 (alternativ rechts) codiert
    sind. Gibt sie immer aus; bei MANUELL_ALT_RECHTS werden sie "Alternative (rechts)"
    zugeordnet. Rueckgabe: (k, Tabelle der betroffenen Kanaele)."""
    check = pd.read_excel(STATA_OUTPUT / "channels_check.xlsx",
                          usecols=["channel_id", "channel_title", "media_category"])
    manuell = set(check.loc[check["media_category"] == 5, "channel_id"])
    treffer = (k["medientyp_ideologie"].isna() & (k["medientyp"] != "Partei/Politiker")
               & k["channel_id"].isin(manuell))
    liste = (k.loc[treffer, ["channel_id", "medientyp"]]
             .merge(check[["channel_id", "channel_title"]], on="channel_id", how="left")
             .sort_values("channel_title"))
    status = "-> Alternative (rechts)" if MANUELL_ALT_RECHTS else "ausgeschlossen (MANUELL_ALT_RECHTS = False)"
    print(f"[Manuell] {len(liste)} Kanaele ohne Baseline-Gruppe, manuell media_category 5: {status}")
    for _, r in liste.iterrows():
        print(f"    {r['channel_id']}  {str(r['channel_title']).strip()}  (medientyp: {r['medientyp']})")
    if MANUELL_ALT_RECHTS:
        k = k.copy()
        k.loc[treffer, "medientyp_ideologie"] = "Alternative (rechts)"
    return k, liste


def loese_ausschluss_auf(kanaele):
    """KANAELE_AUSSCHLIESSEN (channel_ids oder Kanaltitel) -> DataFrame channel_id, titel.
    Titel werden gegen kanal_name (kanaele_roh) und channel_title (channels_check.xlsx)
    abgeglichen (exakt, ohne Gross-/Kleinschreibung und Randleerzeichen). Bricht bei
    unbekannten oder mehrdeutigen Eintraegen mit Vorschlaegen ab."""
    check = pd.read_excel(STATA_OUTPUT / "channels_check.xlsx", usecols=["channel_id", "channel_title"])
    titel = pd.concat([kanaele[["channel_id", "kanal_name"]].rename(columns={"kanal_name": "titel"}),
                       check.rename(columns={"channel_title": "titel"})])
    titel = titel[titel["titel"].notna() & titel["channel_id"].isin(kanaele["channel_id"])]
    titel["titel"] = titel["titel"].astype(str).str.strip()
    titel["schluessel"] = titel["titel"].str.casefold()
    namen = kanaele.set_index("channel_id")["kanal_name"]
    ids, fehler = [], []
    for eintrag in KANAELE_AUSSCHLIESSEN:
        e = eintrag.strip()
        if e in namen.index:
            ids.append(e)
            continue
        treffer = list(titel.loc[titel["schluessel"] == e.casefold(), "channel_id"].unique())
        if len(treffer) == 1:
            ids.append(treffer[0])
        elif treffer:
            fehler.append(f"{eintrag!r}: mehrdeutig ({treffer}), bitte channel_id angeben")
        else:
            aehnlich = sorted(set(titel.loc[titel["schluessel"].str.contains(e.casefold(), regex=False),
                                            "titel"]))[:10]
            fehler.append(f"{eintrag!r}: weder channel_id noch Kanaltitel in kanaele_roh"
                          + (f"; aehnliche Titel: {aehnlich}" if aehnlich else ""))
    if fehler:
        raise SystemExit("KANAELE_AUSSCHLIESSEN:\n  " + "\n  ".join(fehler))
    ids = list(dict.fromkeys(ids))
    return pd.DataFrame({"channel_id": ids, "titel": [str(namen.get(c, c)).strip() for c in ids]})


def berichte_ausschluss(videos, ausschluss, aktive):
    """Je ausgeschlossenem Kanal und aktiver Klassifikation: Gruppe, Zahl der Videos
    und Anteil des Kanals an den Views bzw. Uploads seiner Gruppe vor und ab
    Kriegsbeginn (Sample alle, Umfang alle Videos, ganzes Fenster, vor dem Ausschluss).
    Zeigt, wie stark der Kanal seine Gruppe praegen kann. Gibt die Tabelle zurueck."""
    zeilen = []
    for _, r in ausschluss.iterrows():
        vk = videos[videos["channel_id"] == r["channel_id"]]
        for klass in aktive:
            gruppe = vk[klass].dropna().unique()
            if not len(gruppe):
                zeilen.append({"kanal": r["titel"], "channel_id": r["channel_id"],
                               "klassifikation": klass, "gruppe": "nicht zugeordnet",
                               "n_videos": len(vk)})
                continue
            g = videos[videos[klass] == gruppe[0]]
            zeile = {"kanal": r["titel"], "channel_id": r["channel_id"], "klassifikation": klass,
                     "gruppe": gruppe[0], "n_videos": len(vk)}
            for phase, maske_g, maske_k in [("vor", g["rel_periode"] < 0, vk["rel_periode"] < 0),
                                            ("ab", g["rel_periode"] >= 0, vk["rel_periode"] >= 0)]:
                v_g = g.loc[maske_g, "views"].sum()
                zeile[f"views_anteil_{phase}"] = vk.loc[maske_k, "views"].sum() / v_g * 100 if v_g else np.nan
                n_g = int(maske_g.sum())
                zeile[f"upload_anteil_{phase}"] = int(maske_k.sum()) / n_g * 100 if n_g else np.nan
            zeilen.append(zeile)
    tab = pd.DataFrame(zeilen)
    print(f"[Ausschluss] {len(ausschluss)} Kanaele ausgeschlossen (Anteile an ihrer Gruppe vor dem "
          "Ausschluss, % der Views/Uploads vor bzw. ab Kriegsbeginn):")
    with pd.option_context("display.width", 200, "display.max_columns", None):
        print(tab.drop(columns="channel_id").round(1).to_string(index=False))
    return tab


def lade_videos():
    # videos_roh hat seit 13.10.2026 keinen Laengenfilter mehr -> format == "long"
    # schliesst Shorts/Livestreams/unklassifizierte Videos aus; "krieg" ist jetzt
    # die Titel-Stichwortsuche rel_russia_ukraine_war_cw (core+wide)
    kw_spalten = [f"rel_{t}_{KEYWORD_VARIANTE}" for t in KEYWORD_THEMEN]
    v = pd.read_stata(ROHDATEN_PFAD / "videos_roh.dta",
                      columns=list(dict.fromkeys(
                          ["video_id", "channel_id", "upload_ts", "views", "politisch",
                           "rel_russia_ukraine_war_cw", "format", *kw_spalten])))
    # politisch_kw = "ja", wenn mindestens eine Stichwortsuche anschlaegt
    v["politisch_kw"] = np.where((v[kw_spalten].astype(str) == "ja").any(axis=1), "ja", "nein")
    v = v.drop(columns=[c for c in kw_spalten if c != "rel_russia_ukraine_war_cw"])
    v = v.rename(columns={"rel_russia_ukraine_war_cw": "krieg"})
    for c in ["politisch", "krieg", "format"]:
        v[c] = v[c].astype(str)
    v = v[v["format"].isin(FORMAT)]
    # rel_periode = Monat bzw. Quartal relativ zum Kriegsbeginn (QUARTALSWEISE)
    v["rel_periode"] = relativ_periode(v["upload_ts"], pd.Timestamp(KRIEGSBEGINN), monate_pro_periode())
    # rel_woche = Woche relativ zum Kriegsbeginn (WOECHENTLICH), Woche 0 ab 24.02.2022
    v["rel_woche"] = ((v["upload_ts"] - pd.Timestamp(KRIEGSBEGINN)).dt.days // 7).astype(int)
    n_ohne_views = int(v["views"].isna().sum())
    p_von, p_bis = perioden_bereich(PERIODE_MIN, PERIODE_MAX)
    # Perioden-Fenster plus ggf. WOCHEN_FENSTER (kann ausserhalb liegen); main()
    # trennt danach in Perioden- und Wochen-Videos
    im_fenster = v["rel_periode"].between(p_von, p_bis)
    if WOCHEN_PLOT:
        im_fenster |= v["rel_woche"].between(*wochen_fenster())
    v = v[v["views"].notna() & im_fenster]
    print(f"[Videos] {len(v)} Videos im Fenster {periode_name()} {p_von}..{p_bis}"
          + (f" bzw. Woche {wochen_fenster()[0]}..{wochen_fenster()[1]}" if WOCHEN_PLOT else "")
          + f" ({n_ohne_views} ohne views verworfen)")
    return v


# =========================================================
# SCHRITT 2: Marktanteile
# =========================================================

def berechne_marktanteile(v, gruppen_spalte, min_videos=None, name=None):
    """Anteile je Gruppe und Periode (Spalte rel_periode: Monat, Quartal oder
    Woche). Nenner = Summe ueber alle Gruppen der Klassifikation; Perioden unter
    min_videos (Default MIN_VIDEOS_PRO_MONAT) fallen ganz weg. name = Periodenname
    fuer die Konsole (Default periode_name())."""
    min_videos = MIN_VIDEOS_PRO_MONAT if min_videos is None else min_videos
    d = v[v[gruppen_spalte].notna()]
    zellen = d.groupby(["rel_periode", gruppen_spalte], as_index=False).agg(
        views_summe=("views", "sum"), n_videos=("views", "size"))
    monat = zellen.groupby("rel_periode", as_index=False).agg(
        views_gesamt=("views_summe", "sum"), n_gesamt=("n_videos", "sum"))
    weg = monat.loc[monat["n_gesamt"] < min_videos, "rel_periode"].to_list()
    if weg:
        print(f"[Marktanteil] {gruppen_spalte}: Perioden ({name or periode_name()}) unter "
              f"Mindestbesetzung entfernt: {weg}")
    zellen = zellen.merge(monat[monat["n_gesamt"] >= min_videos], on="rel_periode")
    zellen["anteil"] = zellen["views_summe"] / zellen["views_gesamt"] * 100
    zellen["angebot_anteil"] = zellen["n_videos"] / zellen["n_gesamt"] * 100
    zellen = zellen.rename(columns={gruppen_spalte: "gruppe"})

    for spalte in ["anteil", "angebot_anteil"]:
        abw = (zellen.groupby("rel_periode")[spalte].sum() - 100).abs().max()
        if abw > 0.01:
            raise ValueError(f"{spalte} summiert sich nicht zu 100 % (max. Abweichung {abw:.4f} pp)")
    return zellen


def phasenmittel(anteile, spalte="anteil", phasen=None):
    """Ungewichteter Mittelwert der Perioden-Werte von `spalte` je Phase.
    Default PHASEN (in Monaten, auf vollstaendige Perioden umgerechnet);
    explizit uebergebene `phasen` sind bereits in Perioden angegeben."""
    if phasen is None:
        phasen = {p: perioden_bereich(a, b) for p, (a, b) in PHASEN.items()}
    zeilen = []
    for phase, (a, b) in phasen.items():
        teil = anteile[anteile["rel_periode"].between(a, b)]
        mittel = teil.groupby("gruppe")[spalte].mean()
        zeilen.append(mittel.rename(phase))
    return pd.DataFrame(zeilen).T


def wochen_bereich():
    """(von, bis) in rel_woche: Wochen, die vollstaendig im Fenster der Perioden
    PERIODE_MIN..PERIODE_MAX (lade_videos) liegen."""
    start, m = pd.Timestamp(KRIEGSBEGINN), monate_pro_periode()
    p_von, p_bis = perioden_bereich(PERIODE_MIN, PERIODE_MAX)
    fenster_von = start + pd.DateOffset(months=p_von * m)
    fenster_bis = start + pd.DateOffset(months=(p_bis + 1) * m)   # exklusiv
    return -(-(fenster_von - start).days // 7), (fenster_bis - start).days // 7 - 1


DATEN_START, DATEN_ENDE = pd.Timestamp("2019-01-01"), pd.Timestamp("2026-06-30")   # inklusive


def wochen_fenster():
    """WOCHEN_FENSTER -> (von, bis) in rel_woche (Datum = Woche, die es enthaelt)."""
    kb = pd.Timestamp(KRIEGSBEGINN)
    return tuple(w if isinstance(w, int) else (pd.Timestamp(w) - kb).days // 7 for w in WOCHEN_FENSTER)


def woche_start(k):
    """Erster Tag (Donnerstag) der Woche rel_woche = k."""
    return pd.Timestamp(KRIEGSBEGINN) + pd.Timedelta(days=7 * int(k))


def wochen_marktanteile(teil, gruppen_spalte, bereich=None):
    """Marktanteile je Woche mit Datumsspalten woche_start/woche_ende (inklusive).
    bereich = (von, bis) in rel_woche; Default wochen_bereich() (WOECHENTLICH),
    fuer WOCHEN_PLOT wochen_fenster()."""
    w_von, w_bis = bereich or wochen_bereich()
    teil = teil[teil["rel_woche"].between(w_von, w_bis)].assign(rel_periode=lambda d: d["rel_woche"])
    w = berechne_marktanteile(teil, gruppen_spalte, MIN_VIDEOS_PRO_WOCHE, "woche")
    start = pd.Timestamp(KRIEGSBEGINN) + pd.to_timedelta(w["rel_periode"] * 7, unit="D")
    return w.assign(woche_start=start.dt.date, woche_ende=(start + pd.Timedelta(days=6)).dt.date)


# =========================================================
# SCHRITT 3: Grafik
# =========================================================

def glaette(x, y, frac=None):
    """LOWESS mit frac (Default GLAETTUNG_LOWESS_FRAC); 0 = ungeglaettet."""
    frac = GLAETTUNG_LOWESS_FRAC if frac is None else frac
    if not frac or len(x) < 4:
        return y
    return lowess(y, x, frac=frac, xvals=x, return_sorted=False, it=0)


def zeitachse(woche=False):
    """Eigenschaften der Zeitachse der Zeitreihen-Grafiken: Monat/Quartal (nach
    QUARTALSWEISE) oder Woche (WOCHEN_PLOT). Der Punkt von Periode k liegt bei
    x = k (Periodenbeginn), die Periode umfasst [k, k + 1); der Kriegsbeginn
    liegt exakt auf dem Punkt von Periode 0 (x = 0)."""
    if woche:
        return dict(wort="Woche", plural="Wochen", verbunden=False, frac=WOCHEN_LOWESS_FRAC,
                    betonung=None, text_versatz=0.3, woche=True, hintergrund=WOCHEN_LOWESS_HINTERGRUND,
                    xlabel="Woche relativ zum Kriegsbeginn (Woche 0 = 24.02.–02.03.2022, Do–Mi)",
                    pos=lambda d: (pd.Timestamp(d) - pd.Timestamp(KRIEGSBEGINN)).days / 7)
    m = monate_pro_periode()
    return dict(wort="Quartal" if QUARTALSWEISE else "Monat",
                plural="Quartale" if QUARTALSWEISE else "Monate",
                verbunden=QUARTALSWEISE, frac=GLAETTUNG_LOWESS_FRAC,
                betonung=None if QUARTALSWEISE else BETONUNG_MONATE, text_versatz=0.3 / m, woche=False,
                hintergrund=0,
                xlabel=("Quartal relativ zum Kriegsbeginn (Quartal 0 = 24.02.–23.05.2022)"
                        if QUARTALSWEISE else "Monat relativ zum Kriegsbeginn (24.02.2022)"),
                pos=lambda d: ereignis_position(d, m))


def x_tick_abstand(z, n_perioden):
    """Abstand der x-Hilfslinien: 6 Monate bzw. 2 Quartale; bei Wochen so, dass
    hoechstens ca. 16 Hilfslinien entstehen (1, 2, 4, 8, 13, 26 oder 52 Wochen)."""
    if not z["woche"]:
        return 6 // monate_pro_periode()
    return next((s for s in (1, 2, 4, 8, 13, 26) if n_perioden / s <= 16), 52)


def ereignis_position(datum, monate=1):
    """x-Position eines Datums auf der Periodenachse (monate = Monate je
    Periode, 1 = rel_monat, 3 = rel_quartal). Der Punkt von Periode k liegt
    bei x = k (Periodenbeginn), die Periode umfasst [k, k + 1) (Kriegsbeginn
    liegt bei 0, exakt auf dem Punkt von Periode 0); innerhalb der Periode
    tagesgenau linear interpoliert."""
    datum = pd.Timestamp(datum)
    start = pd.Timestamp(KRIEGSBEGINN)
    k = int(relativ_periode(pd.Series([datum]), start, monate).iloc[0])
    beginn = start + pd.DateOffset(months=k * monate)
    ende = start + pd.DateOffset(months=(k + 1) * monate)
    return k + (datum - beginn) / (ende - beginn)


def grafik_reihen(absolut, wort=None):
    """[(Spalte, y-Beschriftung)] fuer obere und untere Grafikreihe; wort =
    Periodenname (Default Monat bzw. Quartal nach QUARTALSWEISE)."""
    wort = wort or ("Quartal" if QUARTALSWEISE else "Monat")
    if absolut:
        return [("views_mio", f"Views je {wort} (Mio.)"),
                ("n_videos", f"Hochgeladene Videos je {wort}")]
    if ANGEBOT_METRIK == "anteil":
        return [("anteil", "Anteil an allen Views (%)"),
                ("angebot_anteil", "Anteil an allen Uploads (%)")]
    return [("anteil", "Anteil an allen Views (%)"),
            ("n_videos", f"Hochgeladene Videos je {wort}")]


def plotte(anteile_je_umfang, klass_key, sample_label, dateiname, absolut=False,
           vergleich=None, woche=False):
    """Obere Reihe: Views-Marktanteil, untere Reihe: Angebot (Uploads) nach
    ANGEBOT_METRIK; je Spalte ein Umfang. absolut=True: oben Views (Mio.),
    unten Uploads, beides als absolute Zahlen je Gruppe und Periode.
    vergleich = optional zweites {Umfang: Anteile} (z. B. Sample "vorkrieg"),
    zusaetzlich als gestrichelte LOWESS-Linie je Gruppe in derselben Farbe
    (ohne Monatspunkte). Bei QUARTALSWEISE keine Glaettung: Quartalswerte als
    verbundene Marker, Vergleich als ungeglaettete gestrichelte Linie.
    woche=True: rel_periode = rel_woche (WOCHEN_PLOT), Glaettung WOCHEN_LOWESS_FRAC,
    keine BETONUNG_MONATE, x-Achse mit Wochenstart-Datum.
    Gibt die erzeugten Dateien zurueck (bei INTERAKTIV inkl. HTML-Fassung)."""
    if all(a.empty for a in anteile_je_umfang.values()):
        print(f"[Plot] {dateiname}: keine Periode mit ausreichender Besetzung - uebersprungen")
        return []
    cfg = KLASSIFIKATIONEN[klass_key]
    n = len(anteile_je_umfang)
    z = zeitachse(woche)
    wort = z["wort"]
    if absolut:
        anteile_je_umfang = {u: a.assign(views_mio=a["views_summe"] / 1e6)
                             for u, a in anteile_je_umfang.items()}
        if vergleich is not None:
            vergleich = {u: a.assign(views_mio=a["views_summe"] / 1e6)
                         for u, a in vergleich.items()}
    reihen = grafik_reihen(absolut, wort)
    # Absolute Zahlen unterscheiden sich zwischen den Umfaengen um Groessenordnungen
    # -> dann eigene y-Achse je Panel; Anteile teilen die Achse je Reihe.
    geteilt = not absolut and ANGEBOT_METRIK == "anteil"
    # Mindestbreite, damit Legende und Titel auch bei einer Spalte passen
    fig, achsen = plt.subplots(2, n, figsize=(max(5.2 * n, GRAFIK_MINDESTBREITE), 9.6), sharex=True,
                               sharey="row" if geteilt else False, squeeze=False)
    # Ereignisse nur im tatsaechlich belegten Periodenbereich zeichnen, sonst
    # verlaengert axvline die x-Achse in leere Perioden
    alle_monate = pd.concat([a["rel_periode"] for a in anteile_je_umfang.values()])
    x_von, x_bis = alle_monate.min(), alle_monate.max() + 1   # Punkte bei k, Periode [k, k + 1)
    for zeile, (spalte, ylabel) in enumerate(reihen):
        for spalte_nr, (umfang_key, anteile) in enumerate(anteile_je_umfang.items()):
            ax = achsen[zeile, spalte_nr]
            for gruppe, farbe in zip(cfg["gruppen"], cfg["farben"]):
                r = anteile[anteile["gruppe"] == gruppe].sort_values("rel_periode")
                if r.empty:
                    continue
                x = r["rel_periode"].to_numpy(dtype=float)
                y = r[spalte].to_numpy(dtype=float)
                if z["verbunden"]:
                    # ungeglaettet: Quartalswerte direkt verbunden
                    ax.plot(x, y, color=farbe, linewidth=2, marker="o", markersize=4.5,
                            markeredgecolor="white", markeredgewidth=0.5, label=gruppe, zorder=3)
                else:
                    ax.scatter(x, y, s=10, color=farbe, alpha=0.3, linewidths=0, zorder=2)
                    ax.plot(x, glaette(x, y, z["frac"]), color=farbe, linewidth=2, label=gruppe, zorder=3)
                if z["hintergrund"] and len(x) >= 4:
                    # duenne LOWESS-Linie hinter den Wochenwerten (WOCHEN_LOWESS_HINTERGRUND)
                    ax.plot(x, glaette(x, y, z["hintergrund"]), color=farbe, linewidth=1.1,
                            alpha=0.55, solid_capstyle="round", zorder=2.5)
                if z["betonung"]:
                    # Rohwerte um den Kriegsbeginn ungeglaettet, damit ein Sprung sichtbar bleibt
                    m = (x >= z["betonung"][0]) & (x <= z["betonung"][1])
                    ax.plot(x[m], y[m], color=farbe, linewidth=0.9, marker="o", markersize=4,
                            markeredgecolor="white", markeredgewidth=0.5, zorder=4)
                if vergleich is not None:
                    rv = vergleich[umfang_key]
                    rv = rv[rv["gruppe"] == gruppe].sort_values("rel_periode")
                    if not rv.empty:
                        xv = rv["rel_periode"].to_numpy(dtype=float)
                        yv = rv[spalte].to_numpy(dtype=float)
                        ax.plot(xv, yv if z["verbunden"] else glaette(xv, yv, z["frac"]), color=farbe,
                                linewidth=1.6, linestyle="--", zorder=3)
            # Kriegsbeginn nur im belegten Bereich (Wochenfenster kann ihn ausschliessen)
            if x_von <= 0 <= x_bis:
                ax.axvline(0, color="#52514e", linestyle="--", linewidth=1)
                ax.text(z["text_versatz"], 0.98, "Kriegsbeginn", transform=ax.get_xaxis_transform(),
                        va="top", fontsize=8, color="#52514e")
            for name, datum in EREIGNISSE.items():
                xe = z["pos"](datum)
                if not (x_von <= xe <= x_bis):
                    continue
                ax.axvline(xe, color="#8a8883", linestyle=":", linewidth=1.2, zorder=1)
                ax.text(xe + z["text_versatz"], 0.98, name, transform=ax.get_xaxis_transform(), rotation=90,
                        va="top", ha="left", fontsize=7, color="#8a8883")
            if zeile == 0:
                ax.set_title(UMFAENGE[umfang_key][0], fontsize=11)
            else:
                ax.set_xlabel(z["xlabel"])
            if spalte_nr == 0 or not geteilt:
                ax.set_ylim(bottom=0)
            ax.grid(axis="y", color="#e5e4e0", linewidth=0.8)
            # Duenne senkrechte Hilfslinien alle 6 Monate bzw. 2 Quartale (ab Kriegsbeginn),
            # bei Wochen nach x_tick_abstand(); wegen sharex in beiden Reihen deckungsgleich
            ax.xaxis.set_major_locator(MultipleLocator(x_tick_abstand(z, x_bis - x_von)))
            if woche:
                # Wochennummer und Datum des Wochenbeginns (Donnerstag)
                ax.xaxis.set_major_formatter(FuncFormatter(
                    lambda xt, _: f"{int(round(xt))}\n{woche_start(round(xt)):%d.%m.%y}"))
            ax.grid(axis="x", color="#e5e4e0", linewidth=0.5)
            ax.set_axisbelow(True)
            for s in ["top", "right"]:
                ax.spines[s].set_visible(False)
        achsen[zeile, 0].set_ylabel(ylabel)
    handles, labels = achsen[0, 0].get_legend_handles_labels()
    if z["hintergrund"]:
        handles.append(Line2D([], [], color="#52514e", linewidth=1.1, alpha=0.55))
        labels.append(f"LOWESS (frac={z['hintergrund']})")
    if vergleich is not None:
        handles += [Line2D([], [], color="#52514e", linewidth=2),
                    Line2D([], [], color="#52514e", linewidth=1.6, linestyle="--")]
        labels += [f"{SAMPLES['alle'][0]} (Punkte = {wort}{'n' if woche else 's'}werte)",
                   SAMPLES["vorkrieg"][0]]
    # Bei schmalen Grafiken (< 3 Spalten) Legende zweizeilig, Sample-Label in eigener Titelzeile
    zweizeilig = n < 3 and len(labels) > 4
    fig.legend(handles, labels, loc="lower center", frameon=False, fontsize=9,
               ncol=-(-len(labels) // 2) if zweizeilig else len(labels))
    art = "Absolute Zahlen" if absolut else "Marktanteil"
    fig.suptitle(f"{art} (oben: Views, unten: Uploads) nach {cfg['titel']}"
                 f"{chr(10) if n < 3 else ' – '}{sample_label}", fontsize=12)
    if absolut:
        fig.text(0.01, 0.005, f"Views = Stand zum Abrufzeitpunkt: jüngere {z['plural']} hatten weniger Zeit, "
                 "Views zu sammeln (Alterseffekt, kürzt sich anders als bei Anteilen nicht heraus).",
                 fontsize=7.5, color="#52514e")
    fig.tight_layout(rect=(0, 0.07 if zweizeilig else 0.04, 1, 0.95 if n < 3 else 0.97))
    PFAD_PLOTS.mkdir(parents=True, exist_ok=True)
    fig.savefig(PFAD_PLOTS / dateiname, dpi=150)
    plt.close(fig)
    print(f"[Plot] {PFAD_PLOTS / dateiname}")
    if INTERAKTIV:
        return [dateiname, plotte_html(anteile_je_umfang, klass_key, sample_label,
                                       dateiname.replace(".png", ".html"), absolut, vergleich, woche)]
    return [dateiname]


def grafik_sets():
    """Zeitreihen-Grafiken je Klassifikation und Sample als [(Namenszusatz,
    [Umfaenge])]: Hauptgrafik nur "alle", dazu nach UMFANG_LAYOUT je
    Zusatz-Umfang eine eigene Grafik und/oder eine kombinierte mit allen Spalten."""
    sets = [("", ["alle"])]
    if UMFANG_LAYOUT in ("einzeln", "beide"):
        sets += [(f"_{u}", [u]) for u in UMFANG_ZUSATZ]
    if UMFANG_LAYOUT in ("kombiniert", "beide") and UMFANG_ZUSATZ:
        sets.append(("_umfaenge", ["alle", *UMFANG_ZUSATZ]))
    return sets


def zeitreihen_grafiken(je_sample, aktive, fmt, woche=False):
    """Zeitreihen-Grafiken nach KOMBI_VERSION, grafik_sets() und ABSOLUT_VERSION.
    je_sample = {(Sample, Klassifikation): {Umfang: Anteile}}; fmt = Dateinamenszusatz
    hinter dem Umfang; woche wie in plotte(). Gibt die erzeugten Dateien zurueck."""
    erzeugt = []
    if KOMBI_VERSION in ("getrennt", "alle"):
        for s_key, (s_label, _) in SAMPLES.items():
            for k_key in aktive:
                for zusatz, umfaenge in grafik_sets():
                    auswahl = {u: je_sample[(s_key, k_key)][u] for u in umfaenge}
                    for absolut in [False, True] if ABSOLUT_VERSION else [False]:
                        dateiname = f"marktanteil_{k_key}_{s_key}{zusatz}_{fmt}{'_absolut' if absolut else ''}.png"
                        erzeugt += plotte(auswahl, k_key, s_label, dateiname, absolut=absolut, woche=woche)
    if KOMBI_VERSION in ("kombi", "alle"):
        label = f"{SAMPLES['alle'][0]} (durchgezogen) vs. {SAMPLES['vorkrieg'][0]} (gestrichelt)"
        for k_key in aktive:
            for zusatz, umfaenge in grafik_sets():
                haupt = {u: je_sample[("alle", k_key)][u] for u in umfaenge}
                vergleich = {u: je_sample[("vorkrieg", k_key)][u] for u in umfaenge}
                for absolut in [False, True] if ABSOLUT_VERSION else [False]:
                    dateiname = f"marktanteil_{k_key}_kombiniert{zusatz}_{fmt}{'_absolut' if absolut else ''}.png"
                    erzeugt += plotte(haupt, k_key, label, dateiname, absolut=absolut,
                                      vergleich=vergleich, woche=woche)
    return erzeugt


def streu_phasen():
    """Intervalle {Label: (von, bis)} in Perioden ab STREU_START in
    STREU_INTERVALL-Monats-Bloecken; Label = Startperiode relativ zum
    Kriegsbeginn als blosse Zahl (z. B. -8, 0, 4; Monat bzw. Quartal je nach
    QUARTALSWEISE)."""
    m = monate_pro_periode()
    start, schritt = STREU_START // m, STREU_INTERVALL // m
    ende = perioden_bereich(PERIODE_MIN, PERIODE_MAX)[1]
    return {str(a): (a, min(a + schritt - 1, ende))
            for a in range(start, ende + 1, schritt)}


def _diagonalen(ax, xlo, xhi, ylo, yhi, beschriften):
    """Hauptdiagonale y = x (gestrichelt) und Parallelen y = x + c im Abstand
    STREU_DIAGONAL_ABSTAND; optional beschriftet mit c (pp) am oberen/rechten Rand."""
    ax.axline((0, 0), slope=1, color="#52514e", linestyle="--", linewidth=1, zorder=1)
    a = STREU_DIAGONAL_ABSTAND
    if not a:
        return
    for c in np.arange(np.floor((ylo - xhi) / a) * a, np.ceil((yhi - xlo) / a) * a + a, a):
        if c != 0:
            ax.axline((0, c), slope=1, color="#c9c7c1", linewidth=0.5, zorder=1)
        if not beschriften:
            continue
        text = f"{c:+.0f}" if c else "0"
        if xlo <= yhi - c <= xhi:      # Schnitt mit dem oberen Rand
            ax.text(yhi - c, yhi, text, fontsize=7, color="#8a8883", ha="center", va="bottom")
        elif ylo <= xhi + c <= yhi:    # sonst mit dem rechten Rand
            ax.text(xhi, xhi + c, " " + text, fontsize=7, color="#8a8883", ha="left", va="center")


def _zeichne_gruppe(ax, r, x, y, labels, vorkrieg, farbe, gruppe):
    """Monatswerte (blass) und Trajektorie der Intervallmittel einer Gruppe."""
    ax.scatter(r["angebot_anteil"], r["anteil"], s=9, color=farbe, alpha=0.2,
               linewidths=0, zorder=2)
    ok = ~(np.isnan(x) | np.isnan(y))
    ax.plot(x[ok], y[ok], color=farbe, linewidth=1.5, zorder=3, label=gruppe)
    vor, nach = ok & vorkrieg, ok & ~vorkrieg
    ax.scatter(x[vor], y[vor], s=50, facecolors="white", edgecolors=farbe, linewidths=1.5, zorder=4)
    ax.scatter(x[nach], y[nach], s=50, color=farbe, edgecolors="white", linewidths=1, zorder=4)
    for i in np.flatnonzero(ok):
        ax.annotate(labels[i], (x[i], y[i]), xytext=(5, 4), textcoords="offset points",
                    fontsize=7, color=farbe, fontweight="bold", zorder=5)


def _achsen_stil(ax, xlo, xhi, ylo, yhi):
    ax.set_xlim(xlo, xhi)
    ax.set_ylim(ylo, yhi)
    ax.set_aspect("equal")
    ax.set_xlabel("Anteil an allen Uploads (%)")
    ax.grid(color="#e5e4e0", linewidth=0.6)
    ax.set_axisbelow(True)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)


def _speichere_streu(fig, phasen, getrennt, dateiname):
    letzte = list(phasen.values())[-1]
    einheit = "Quartal" if QUARTALSWEISE else "Monat"
    fussnote = (
        f"Große Punkte = Mittel je {STREU_INTERVALL}-Monats-Intervall, beschriftet mit dem Start"
        f"{einheit.lower()} relativ zum Kriegsbeginn\n(hohl = vor, gefüllt = ab Kriegsbeginn; letztes "
        f"Intervall {einheit} {letzte[0]} bis {letzte[1]}). Blasse Punkte = {einheit}swerte.\n"
        f"Anteile an allen Gruppen der "
        f"Klassifikation, auch den nicht gezeigten.")
    if STREU_DIAGONAL_ABSTAND:
        fussnote += (f"\nGraue Diagonalen im Abstand von {STREU_DIAGONAL_ABSTAND} pp (y = x + c): "
                     f"Bewegung parallel dazu = Upload- und Views-Anteil ändern sich gleich stark.")
    if getrennt:
        fussnote += ("\nJedes Panel ist eigens gezoomt: Achsenmaßstäbe unterscheiden sich zwischen den "
                     "Panels (Abstände über die Achsenwerte bzw. c am Rand in pp vergleichen).")
        if STREU_ZOOM == "intervalle":
            fussnote += f" Zoom auf die Intervallmittel, {einheit}swerte außerhalb abgeschnitten."
    fig.text(0.01, 0.01, fussnote, fontsize=7.5, color="#52514e")
    PFAD_PLOTS.mkdir(parents=True, exist_ok=True)
    fig.savefig(PFAD_PLOTS / dateiname, dpi=150)
    plt.close(fig)
    print(f"[Plot] {PFAD_PLOTS / dateiname}")


def plotte_streu(anteile, klass_key, umfang_key, sample_label, dateiname):
    """Upload-Anteil (x) gegen Views-Anteil (y) fuer die Gruppen aus
    STREU_GRUPPEN. Blasse Punkte = Monatswerte, verbundene Marker = Mittel je
    Intervall (streu_phasen()) in zeitlicher Reihenfolge, beschriftet mit dem
    Startmonat; hohl = vor, gefuellt = ab Kriegsbeginn. Oberhalb der Diagonale
    erzielt eine Gruppe mehr Views pro Video als der Durchschnitt ALLER Gruppen
    der Klassifikation.

    STREU_LAYOUT "gemeinsam": alle Gruppen in einer Grafik (`dateiname`);
    "getrennt": ein Panel je Gruppe (`dateiname` mit Suffix _getrennt), jedes
    nach STREU_ZOOM auf seine eigenen Daten gezoomt (quadratischer Ausschnitt,
    Massstab je Panel verschieden); "beide": beide Dateien. Gibt die
    Dateinamen zurueck."""
    cfg = KLASSIFIKATIONEN[klass_key]
    phasen = streu_phasen()
    pm_views = phasenmittel(anteile, "anteil", phasen)
    pm_uploads = phasenmittel(anteile, "angebot_anteil", phasen)
    vorkrieg = np.array([b < 0 for _, b in phasen.values()])
    labels = np.array(list(phasen))
    titel = f"Uploads vs. Views ({UMFAENGE[umfang_key][0]}) – {sample_label}"

    daten = []   # (gruppe, farbe, Monatswerte, x-Mittel, y-Mittel)
    for gruppe, farbe in zip(cfg["gruppen"], cfg["farben"]):
        r = anteile[anteile["gruppe"] == gruppe]
        if gruppe not in STREU_GRUPPEN[klass_key] or r.empty:
            continue
        daten.append((gruppe, farbe, r,
                      pm_uploads.loc[gruppe].reindex(labels).to_numpy(dtype=float),
                      pm_views.loc[gruppe].reindex(labels).to_numpy(dtype=float)))
    erzeugt = []
    if not daten:
        print(f"[Streu] {dateiname}: keine der STREU_GRUPPEN {STREU_GRUPPEN[klass_key]} im Sample "
              "-> Streudiagramm entfaellt")
        return erzeugt

    if STREU_LAYOUT in ("gemeinsam", "beide"):
        fig, ax = plt.subplots(figsize=(7.5, 8.2))
        for gruppe, farbe, r, x, y in daten:
            _zeichne_gruppe(ax, r, x, y, labels, vorkrieg, farbe, gruppe)
        grenze = max(max(r["anteil"].max(), r["angebot_anteil"].max()) for _, _, r, _, _ in daten) * 1.05
        _diagonalen(ax, 0, grenze, 0, grenze, beschriften=False)
        ax.text(grenze * 0.97, grenze * 0.93, "Views-Anteil = Upload-Anteil", rotation=45,
                ha="right", va="top", fontsize=8, color="#52514e", rotation_mode="anchor")
        _achsen_stil(ax, 0, grenze, 0, grenze)
        ax.set_ylabel("Anteil an allen Views (%)")
        ax.legend(loc="upper left", frameon=False, fontsize=9)
        fig.suptitle(titel, fontsize=11)
        fig.tight_layout(rect=(0, 0.1, 1, 0.97))
        _speichere_streu(fig, phasen, False, dateiname)
        erzeugt.append(dateiname)

    if STREU_LAYOUT in ("getrennt", "beide"):
        fig, achsen = plt.subplots(1, len(daten), figsize=(6.2 * len(daten), 7.4))
        achsen = np.atleast_1d(achsen)
        for ax, (gruppe, farbe, r, x, y) in zip(achsen, daten):
            # Eigene quadratische Spannweite je Panel = groessere x- oder
            # y-Ausdehnung der Zoom-Basis plus Rand fuer die Beschriftungen
            if STREU_ZOOM == "intervalle":
                ok = ~(np.isnan(x) | np.isnan(y))
                basis = (x[ok], y[ok])
            else:
                basis = (r["angebot_anteil"].to_numpy(), r["anteil"].to_numpy())
            spanne = max(np.ptp(w) for w in basis) * 1.15 + 1.5
            grenzen = []
            for werte in basis:
                lo = max(0.0, (werte.min() + werte.max()) / 2 - spanne / 2)
                grenzen += [lo, lo + spanne]
            _zeichne_gruppe(ax, r, x, y, labels, vorkrieg, farbe, gruppe)
            _diagonalen(ax, *grenzen, beschriften=True)
            _achsen_stil(ax, *grenzen)
            ax.set_title(gruppe, fontsize=11, color=farbe, pad=14)
        achsen[0].set_ylabel("Anteil an allen Views (%)")
        fig.suptitle(titel, fontsize=11)
        fig.tight_layout(rect=(0, 0.13, 1, 0.97))
        name = dateiname.replace(".png", "_getrennt.png")
        _speichere_streu(fig, phasen, True, name)
        erzeugt.append(name)
    if INTERAKTIV:
        erzeugt.append(plotte_streu_html(anteile, klass_key, umfang_key, sample_label,
                                         dateiname.replace(".png", ".html")))
    return erzeugt


# =========================================================
# SCHRITT 3b: Interaktive HTML-Fassungen (INTERAKTIV)
# =========================================================

PFAD_HTML = PFAD_PLOTS / "interaktiv"

# Hover je Perioden-Punkt; customdata = _hover_daten()
HOVER = ("<b>%{customdata[0]}</b><br>%{customdata[1]}<br>"
         "Views-Anteil: %{customdata[2]:.2f} %<br>Upload-Anteil: %{customdata[3]:.2f} %<br>"
         "Views: %{customdata[4]:,.0f}<br>Videos: %{customdata[5]:,.0f}<extra></extra>")


def periode_text(k, woche=False):
    """Hover-Beschriftung einer Periode, z. B. 'Quartal -1 (24.11.2021–23.02.2022)'."""
    if woche:
        start = woche_start(k)
        return f"Woche {int(k)} ({start:%d.%m.%Y}–{start + pd.Timedelta(days=6):%d.%m.%Y})"
    m = monate_pro_periode()
    start = pd.Timestamp(KRIEGSBEGINN) + pd.DateOffset(months=int(k) * m)
    ende = start + pd.DateOffset(months=m) - pd.Timedelta(days=1)
    return f"{'Quartal' if QUARTALSWEISE else 'Monat'} {int(k)} ({start:%d.%m.%Y}–{ende:%d.%m.%Y})"


def _hover_daten(r, label, woche=False):
    """customdata-Zeilen fuer HOVER (Reihenfolge wie r)."""
    return pd.DataFrame({
        "label": label, "periode": r["rel_periode"].map(lambda k: periode_text(k, woche)),
        "anteil": r["anteil"], "angebot": r["angebot_anteil"],
        "views": r["views_summe"].astype(float), "videos": r["n_videos"].astype(float),
    }).values.tolist()


def _schreibe_html(fig, dateiname):
    # plotly.min.js einmal als Datei neben die HTMLs -> offline lesbar, HTMLs klein
    PFAD_HTML.mkdir(parents=True, exist_ok=True)
    fig.write_html(PFAD_HTML / dateiname, include_plotlyjs="directory")
    print(f"[HTML] {PFAD_HTML / dateiname}")
    return f"interaktiv/{dateiname}"


def plotte_html(anteile_je_umfang, klass_key, sample_label, dateiname, absolut=False,
                vergleich=None, woche=False):
    """Interaktive Fassung von plotte() mit gleichem Aufbau (Reihen, Spalten,
    Glaettung, Vergleichslinie, Ereignisse). Hover auf jedem Perioden-Punkt
    (bei Monaten/Wochen auf den Punkten, nicht auf der LOWESS-Linie); Legendenklick
    blendet eine Gruppe in allen Panels aus. woche wie in plotte(). Gibt den Pfad
    relativ zu PFAD_PLOTS zurueck."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    cfg = KLASSIFIKATIONEN[klass_key]
    umfaenge = list(anteile_je_umfang)
    z = zeitachse(woche)
    reihen = grafik_reihen(absolut, z["wort"])
    fig = make_subplots(rows=2, cols=len(umfaenge), shared_xaxes=True, vertical_spacing=0.08,
                        horizontal_spacing=0.05,
                        subplot_titles=[UMFAENGE[u][0] for u in umfaenge] + [""] * len(umfaenge))
    alle = pd.concat([a["rel_periode"] for a in anteile_je_umfang.values()])
    x_von, x_bis = alle.min(), alle.max() + 1

    def linie(r, spalte, gruppe, farbe, label, gestrichelt, legende, zeile, sp):
        r = r.sort_values("rel_periode").assign(views_mio=r["views_summe"] / 1e6)
        x = r["rel_periode"].to_numpy(dtype=float)
        y = r[spalte].to_numpy(dtype=float)
        cd = _hover_daten(r, label, woche)
        stil = dict(color=farbe, width=1.6 if gestrichelt else 2, dash="dash" if gestrichelt else "solid")
        if z["verbunden"]:
            fig.add_trace(go.Scatter(
                x=x, y=y, mode="lines+markers", line=stil, name=gruppe, legendgroup=gruppe,
                showlegend=legende,
                marker=dict(size=6 if gestrichelt else 8, color="white" if gestrichelt else farbe,
                            line=dict(color=farbe, width=1.5)),
                customdata=cd, hovertemplate=HOVER), row=zeile, col=sp)
            return
        # Monate: Hover auf den Rohwerten, LOWESS-Linie ohne Hover
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="markers", legendgroup=gruppe, showlegend=False,
            marker=dict(size=5 if gestrichelt else 6, color=farbe, opacity=0.5,
                        symbol="circle-open" if gestrichelt else "circle"),
            customdata=cd, hovertemplate=HOVER), row=zeile, col=sp)
        fig.add_trace(go.Scatter(
            x=x, y=glaette(x, y, z["frac"]), mode="lines", line=stil, name=gruppe, legendgroup=gruppe,
            showlegend=legende, hoverinfo="skip"), row=zeile, col=sp)
        if z["hintergrund"] and not gestrichelt and len(x) >= 4:
            # duenne LOWESS-Linie hinter den Wochenwerten (WOCHEN_LOWESS_HINTERGRUND)
            fig.add_trace(go.Scatter(
                x=x, y=glaette(x, y, z["hintergrund"]), mode="lines", opacity=0.55,
                line=dict(color=farbe, width=1.1), legendgroup=gruppe, showlegend=False,
                hoverinfo="skip"), row=zeile, col=sp)

    for zeile, (spalte, ylabel) in enumerate(reihen, start=1):
        for sp, u in enumerate(umfaenge, start=1):
            for gruppe, farbe in zip(cfg["gruppen"], cfg["farben"]):
                r = anteile_je_umfang[u]
                r = r[r["gruppe"] == gruppe]
                if r.empty:
                    continue
                linie(r, spalte, gruppe, farbe, gruppe, False, zeile == 1 and sp == 1, zeile, sp)
                if vergleich is not None:
                    rv = vergleich[u]
                    rv = rv[rv["gruppe"] == gruppe]
                    if not rv.empty:
                        linie(rv, spalte, gruppe, farbe, f"{gruppe} – {SAMPLES['vorkrieg'][0]}",
                              True, False, zeile, sp)
            fig.update_yaxes(title_text=ylabel if sp == 1 else None, rangemode="tozero",
                             gridcolor="#e5e4e0", row=zeile, col=sp)
    if x_von <= 0 <= x_bis:
        fig.add_vline(x=0, line=dict(color="#52514e", dash="dash", width=1),
                      annotation_text="Kriegsbeginn", annotation_position="top right",
                      annotation_font=dict(size=10, color="#52514e"))
    for name, datum in EREIGNISSE.items():
        xe = z["pos"](datum)
        if x_von <= xe <= x_bis:
            fig.add_vline(x=xe, line=dict(color="#8a8883", dash="dot", width=1.2),
                          annotation_text=name, annotation_position="top right",
                          annotation_textangle=-90, annotation_font=dict(size=9, color="#8a8883"))
    fig.update_xaxes(dtick=x_tick_abstand(z, x_bis - x_von), gridcolor="#e5e4e0")
    fig.update_xaxes(title_text=z["xlabel"], row=2)
    titel = (f"{'Absolute Zahlen' if absolut else 'Marktanteil'} (oben: Views, unten: Uploads) "
             f"nach {cfg['titel']} – {sample_label}")
    if vergleich is not None:
        titel += f"<br><sup>durchgezogen = {SAMPLES['alle'][0]}, gestrichelt = {SAMPLES['vorkrieg'][0]}</sup>"
    fig.update_layout(title=titel, template="plotly_white", separators=",.", hovermode="closest",
                      height=850, legend=dict(orientation="h", yanchor="top", y=-0.08, x=0))
    return _schreibe_html(fig, dateiname)


def plotte_streu_html(anteile, klass_key, umfang_key, sample_label, dateiname):
    """Interaktive Fassung von plotte_streu(): alle Gruppen aus STREU_GRUPPEN
    in einer zoombaren Grafik (das getrennte Layout entfaellt, Zoomen ersetzt
    es). Hover auf Perioden-Werten wie in plotte_html(), auf Intervallmitteln
    Intervall, beide Mittelwerte und deren Differenz. Gibt den Pfad relativ
    zu PFAD_PLOTS zurueck."""
    import plotly.graph_objects as go

    cfg = KLASSIFIKATIONEN[klass_key]
    phasen = streu_phasen()
    pm_views = phasenmittel(anteile, "anteil", phasen)
    pm_uploads = phasenmittel(anteile, "angebot_anteil", phasen)
    vorkrieg = np.array([b < 0 for _, b in phasen.values()])
    labels = np.array(list(phasen))
    einheit = "Quartal" if QUARTALSWEISE else "Monat"
    intervalle = np.array([f"{einheit} {a} bis {b}" for a, b in phasen.values()], dtype=object)

    fig = go.Figure()
    grenze = 0.0
    for gruppe, farbe in zip(cfg["gruppen"], cfg["farben"]):
        r = anteile[anteile["gruppe"] == gruppe].sort_values("rel_periode")
        if gruppe not in STREU_GRUPPEN[klass_key] or r.empty:
            continue
        grenze = max(grenze, r["anteil"].max(), r["angebot_anteil"].max())
        fig.add_trace(go.Scatter(
            x=r["angebot_anteil"], y=r["anteil"], mode="markers", legendgroup=gruppe,
            showlegend=False, marker=dict(size=6, color=farbe, opacity=0.3),
            customdata=_hover_daten(r, gruppe), hovertemplate=HOVER))
        x = pm_uploads.loc[gruppe].reindex(labels).to_numpy(dtype=float)
        y = pm_views.loc[gruppe].reindex(labels).to_numpy(dtype=float)
        ok = ~(np.isnan(x) | np.isnan(y))
        fig.add_trace(go.Scatter(
            x=x[ok], y=y[ok], mode="lines+markers+text", text=labels[ok], textposition="top right",
            textfont=dict(color=farbe, size=10), name=gruppe, legendgroup=gruppe,
            line=dict(color=farbe, width=1.5),
            marker=dict(size=10, color=["white" if v else farbe for v in vorkrieg[ok]],
                        line=dict(color=farbe, width=2)),
            customdata=intervalle[ok],
            hovertemplate=(f"<b>{gruppe}</b><br>Intervall %{{text}}: %{{customdata}}<br>"
                           "Upload-Anteil (Mittel): %{x:.2f} %<br>Views-Anteil (Mittel): %{y:.2f} %<br>"
                           "<extra></extra>")))
    grenze *= 1.05
    # Diagonale y = x und Parallelen y = x + c (als Linien-Traces, damit sie geclippt werden)
    a = STREU_DIAGONAL_ABSTAND
    abstaende = np.arange(-np.ceil(grenze / a) * a, np.ceil(grenze / a) * a + a, a) if a else [0]
    for c in abstaende:
        fig.add_trace(go.Scatter(
            x=[0, grenze], y=[c, grenze + c], mode="lines", showlegend=False, hoverinfo="skip",
            line=dict(color="#52514e" if c == 0 else "#c9c7c1", width=1 if c == 0 else 0.5,
                      dash="dash" if c == 0 else "solid")))
    fig.update_xaxes(range=[0, grenze], title_text="Anteil an allen Uploads (%)", gridcolor="#e5e4e0")
    fig.update_yaxes(range=[0, grenze], title_text="Anteil an allen Views (%)", gridcolor="#e5e4e0",
                     scaleanchor="x", scaleratio=1)
    fussnote = (f"Große Punkte = Mittel je {STREU_INTERVALL}-Monats-Intervall (hohl = vor, gefüllt = ab "
                f"Kriegsbeginn), blasse Punkte = {einheit}swerte. Gestrichelt: Views-Anteil = Upload-Anteil"
                + (f"; graue Parallelen im Abstand von {a} pp." if a else "."))
    fig.update_layout(
        title=f"Uploads vs. Views ({UMFAENGE[umfang_key][0]}) – {sample_label}<br><sup>{fussnote}</sup>",
        template="plotly_white", separators=",.", hovermode="closest", width=900, height=900,
        legend=dict(orientation="h", yanchor="top", y=-0.1, x=0))
    return _schreibe_html(fig, dateiname)


# =========================================================
# SCHRITT 4: Methodik-Datei
# =========================================================

def tabelle_md(df):
    df = df.round(1)
    kopf = "| Gruppe | " + " | ".join(df.columns) + " |"
    trenn = "|---|" + "---:|" * len(df.columns)
    zeilen = [f"| {idx} | " + " | ".join(f"{w:.1f}" if pd.notna(w) else "–" for w in row) + " |"
              for idx, row in df.iterrows()]
    return [kopf, trenn, *zeilen]


def schreibe_methodik(kanaele, grenzen, fallzahlen, phasen_tabellen, erzeugt, aktive, dateiname,
                      manuell=None, median=None, ausschluss_tab=None):
    p_von, p_bis = perioden_bereich(PERIODE_MIN, PERIODE_MAX)
    if QUARTALSWEISE:
        zeitraum = (f"- **Quartalsweise Betrachtung** (`QUARTALSWEISE = True`): Periode = `rel_quartal` "
                    f"{p_von} bis {p_bis} (Quartal 0 = 3 Monate ab dem {KRIEGSBEGINN}; nur Quartale, die "
                    f"vollständig in den Monaten {PERIODE_MIN} bis {PERIODE_MAX} liegen). In allen Formeln "
                    "und Tabellen steht „Monat“ dann für das Quartal.")
        grafik = ("- Grafik: Quartalswerte als verbundene Punkte, **ohne Glättung**; Vergleichslinien "
                  "ebenfalls ungeglättet.")
    else:
        zeitraum = f"- Monate `rel_monat` {PERIODE_MIN} bis {PERIODE_MAX} (Monat 0 beginnt am {KRIEGSBEGINN})."
        grafik = (f"- Grafik: Punkte = Monatswerte, Linie = LOWESS (frac={GLAETTUNG_LOWESS_FRAC}, it=0)"
                  + (f"; Monate {BETONUNG_MONATE[0]} bis {BETONUNG_MONATE[1]} zusaetzlich als deckende, "
                     "verbundene Rohwerte hervorgehoben" if BETONUNG_MONATE else "") + ".")
    z = [
        "# Methodik: Marktanteile aus dem Rohdatensatz",
        "",
        "Skript: `src/youtube_code/step6_auswertung/marktanteil_rohdaten_plots.py` "
        "(Herleitung im Moduldocstring). Datenbasis: `outputs/stata_rohdaten/videos_roh.dta`, "
        "`kanaele_roh.dta`.",
        "",
        "## Formel",
        "",
        "```",
        "anteil = sum(views | Gruppe, Umfang, Monat) / sum(views | alle Gruppen der Klassifikation, Umfang, Monat) * 100",
        "angebot_anteil = n_videos(Gruppe, Umfang, Monat) / n_videos(alle Gruppen der Klassifikation, Umfang, Monat) * 100",
        "```",
        "",
        "- Obere Grafikreihe: `anteil` (Views). Untere Reihe: Angebot = hochgeladene Videos, "
        + ("als `angebot_anteil` (%)." if ANGEBOT_METRIK == "anteil"
           else "als absolute Zahl `n_videos` je Monat (eigene y-Achse je Panel).")
        + " Liegt der Views-Anteil einer Gruppe über ihrem Upload-Anteil, erzielt sie "
        "überdurchschnittlich viele Views pro Video; steigt nur der Upload-Anteil, wächst sie "
        "über mehr Output.",
        *(["- Zusätzlich `…_absolut.png`: gleiche Zellen, oben `views_summe` (Mio. Views), unten "
           "`n_videos` je Gruppe und Monat, eigene y-Achse je Panel. Der Alterseffekt der Views "
           "(siehe unten) kürzt sich hier nicht heraus: der Verlauf in jüngeren Monaten ist nach "
           "unten verzerrt, nur Vergleiche zwischen Gruppen im selben Monat sind belastbar."]
          if ABSOLUT_VERSION else []),
        *(["- Zusätzlich `…_kombiniert_….png`: alle Kanäle (durchgezogene Linie, Punkte = "
           "Monatswerte) und nur vor Kriegsbeginn aktive Kanäle (gestrichelt, gleiche Farbe) in "
           "einer Grafik. Der Abstand beider Linien zeigt den Beitrag erst später gestarteter Kanäle"
           + (" (in `…_kombiniert_…_absolut.png` direkt in Views bzw. Uploads)."
              if ABSOLUT_VERSION else ".")]
          if KOMBI_VERSION in ("kombi", "alle") else []),
        *(["- Getrennte Zeitreihen je Sample (`…_alle_….png`, `…_vorkrieg_….png`) in diesem Lauf "
           "nicht erzeugt (`KOMBI_VERSION = \"kombi\"`)."]
          if KOMBI_VERSION == "kombi" else []),
        zeitraum,
        f"- {'Quartale' if QUARTALSWEISE else 'Monate'} mit < {MIN_VIDEOS_PRO_MONAT} Videos "
        "(alle Gruppen zusammen) entfallen.",
        "- Views = Stand zum Abrufzeitpunkt; jüngere Videos hatten weniger Zeit, Views zu sammeln. "
        "Das betrifft alle Gruppen, verzerrt Anteile aber, wenn sich der Views-Verlauf über das "
        "Videoalter zwischen den Gruppen unterscheidet.",
        grafik + " Senkrechte Linien: Kriegsbeginn (gestrichelt, exakt auf dem Punkt von Periode 0; "
        "jeder Punkt markiert den Beginn seiner Periode)"
        + ("; gepunktet " + ", ".join(f"{n} ({d})" for n, d in EREIGNISSE.items())
           + " (tagesgenau in der Periode platziert, nur innerhalb der belegten Perioden)" if EREIGNISSE else "")
        + ".",
        "- Umfänge: politische Videos = `politisch == ja` (inkl. Kriegsvideos); "
        "politische Videos (Stichworte) = mindestens eines von "
        + ", ".join(f"`rel_{t}_{KEYWORD_VARIANTE}`" for t in KEYWORD_THEMEN)
        + " `== ja` (Titel-Stichworte, inkl. Kriegsvideos); "
        "Kriegsvideos = `rel_russia_ukraine_war_cw == ja` (Titel-Stichworte core+wide; vor dem "
        "13.10.2026 Titel + Beschreibung), ohne zusätzlichen Politik-Filter; alle Videos = "
        "kein Themenfilter. Nur Videos mit `format == long` (keine Shorts/Livestreams).",
        "",
        "## Klassifikationen",
        "",
        "1. **Medientyp × Ideologie:** ÖRR, traditionelle Medien, alternative Medien nach "
        f"`ideo_gesellschaft_baseline` (Schnitte {IDEOLOGIE_SCHNITTE[0]} / {IDEOLOGIE_SCHNITTE[1]}). "
        "Alternative Medien ohne Ideologie-Baseline und Partei/Politiker sind ausgeschlossen. "
        "Anders als in den früheren Grafiken stammt die Ideologie aus dem Vorkriegsfenster "
        "(ohne Kriegsvideos), nicht aus `channel_classification_ideology.csv`.",
        "2. **Populismus-Tertile:** ÖRR, traditionelle und alternative Medien mit `pop_baseline`, "
        f"Tertile über die Kanäle im Sample nach `KANALLISTE` (ungewichtet; dieselben Grenzen "
        f"für „nur vor Kriegsbeginn aktive“). Grenzen: {grenzen[0]:.3f} / {grenzen[1]:.3f}. "
        "Kanäle ohne Populismus-Baseline sind ausgeschlossen."
        + ("" if POPULISMUS_TERTILE else " **In diesem Lauf deaktiviert** (`POPULISMUS_TERTILE = False`)."),
        "3. **Alternative Medien nach Populismus-Median:** ÖRR und traditionelle Medien (alle, "
        "unabhängig von `pop_baseline`) sowie alternative Medien mit `pop_baseline`, geteilt am "
        f"Median über die alternativen Kanäle im Sample nach `KANALLISTE` und `MANUELL_ALT_RECHTS` "
        f"({median:.3f}; > Median = „über“; für „nur vor Kriegsbeginn aktive“ derselbe Median). Alternative "
        "Medien ohne Populismus-Baseline und Partei/Politiker sind ausgeschlossen."
        + ("" if POPULISMUS_MEDIAN else " **In diesem Lauf deaktiviert** (`POPULISMUS_MEDIAN = False`)."),
        "4. **Medientyp (alternative Medien zusammengefasst):** nach der manuellen `media_category` "
        "in `channels_check.xlsx`: 1 = ÖRR, 2 = traditionelle Medien, 3/4/5 = Alternative Medien "
        "(eine Gruppe); Code 6 und Kanäle ohne Code sind ausgeschlossen. Unabhängig von `medientyp` "
        "und Ideologie-Baseline aus `kanaele_roh`, daher nicht deckungsgleich mit der Summe der "
        "Alternative-Gruppen aus 1."
        + ("" if MEDIENTYP_GESAMT else " **In diesem Lauf deaktiviert** (`MEDIENTYP_GESAMT = False`)."),
        "",
        "## Grafik-Umfänge",
        "",
        "- Hauptgrafiken `marktanteil_<klassifikation>_<sample>_<format>.png` zeigen nur alle Videos.",
        *([f"- Zusatz-Umfänge {', '.join(UMFAENGE[u][0] for u in UMFANG_ZUSATZ)}"
           + {"einzeln": " als eigene Grafiken (`…_<sample>_<umfang>_<format>.png`).",
              "kombiniert": " zusammen mit allen Videos in einer Grafik (`…_<sample>_umfaenge_<format>.png`).",
              "beide": " als eigene Grafiken (`…_<sample>_<umfang>_<format>.png`) und kombiniert "
                       "(`…_<sample>_umfaenge_<format>.png`)."}[UMFANG_LAYOUT]]
          if UMFANG_ZUSATZ else []),
        *([f"- **Wochenweise Grafiken** (`WOCHEN_PLOT = True`): gleiche Klassifikationen, Samples, "
           "Umfänge und Varianten wie oben, aber je Woche (`rel_woche`, Woche 0 = 24.02.–02.03.2022, "
           f"Do–Mi) im eigenen Fenster Woche {wochen_fenster()[0]} bis {wochen_fenster()[1]} "
           f"({woche_start(wochen_fenster()[0]):%d.%m.%Y}–"
           f"{woche_start(wochen_fenster()[1]) + pd.Timedelta(days=6):%d.%m.%Y}, `WOCHEN_FENSTER = "
           f"{WOCHEN_FENSTER}`), unabhängig von `PERIODE_MIN`/`PERIODE_MAX`. Wochen mit < "
           f"{MIN_VIDEOS_PRO_WOCHE} Videos entfallen; Glättung LOWESS frac={WOCHEN_LOWESS_FRAC} "
           "(0 = ungeglättet)"
           + (f", zusätzlich dünne LOWESS-Linie im Hintergrund (frac={WOCHEN_LOWESS_HINTERGRUND}, "
              "it=0, nur Hauptlinie)" if WOCHEN_LOWESS_HINTERGRUND else "")
           + ", keine Hervorhebung um den Kriegsbeginn. Dateien `…_woche_<von>-<bis>…`, "
           "Werte in `marktanteil_woche_<von>-<bis>.csv`."]
          if WOCHEN_PLOT else []),
        *(["", f"**Kanalliste aktiv:** Sample auf {len(kanaele)} Kanäle aus `KANALLISTE` "
           "eingeschränkt (Medientyp × Ideologie auf allen Kanälen gebildet, Tertilgrenzen und "
           "Populismus-Median auf den Kanälen der Liste)."]
          if KANALLISTE else []),
        *(["", f"**Kanäle ausgeschlossen** (`KANAELE_AUSSCHLIESSEN`, Robustheitscheck): "
           f"{ausschluss_tab['channel_id'].nunique()} Kanäle aus allen Grafiken und Tabellen entfernt. "
           "Gruppen, Tertilgrenzen und Populismus-Median sind vor dem Ausschluss gebildet (identisch "
           "zum Lauf ohne Ausschluss). Anteile des Kanals an seiner Gruppe vor dem Ausschluss "
           "(Sample alle, alle Videos, % der Views/Uploads vor bzw. ab Kriegsbeginn):",
           "",
           "| Kanal | Klassifikation | Gruppe | Videos | Views vor | Views ab | Uploads vor | Uploads ab |",
           "|---|---|---|---:|---:|---:|---:|---:|",
           *[f"| {r['kanal']} (`{r['channel_id']}`) | {r['klassifikation']} | {r['gruppe']} | "
             f"{int(r['n_videos'])} | "
             + " | ".join(f"{r.get(s, np.nan):.1f} %" if pd.notna(r.get(s, np.nan)) else "–"
                          for s in ["views_anteil_vor", "views_anteil_ab",
                                    "upload_anteil_vor", "upload_anteil_ab"]) + " |"
             for _, r in ausschluss_tab.iterrows()]]
          if ausschluss_tab is not None else []),
        *(["", f"**ÖRR getrennt:** ÖRR-Kanäle mit `sample` ∈ {list(OERR_DOKU_CODES)} in "
           f"`channels_check.xlsx` bilden die Gruppe „{OERR_DOKU_GRUPPE}“, die übrigen bleiben „ÖRR“ "
           "(`OERR_DOKU_CODES`)."]
          if OERR_DOKU_CODES else []),
        *(["", f"**Manuell klassifizierte Kanäle** ({len(manuell)}, ohne Baseline-Gruppe, in "
           "`channels_check.xlsx` `media_category` = 5 = alternativ rechts; Partei/Politiker ausgeschlossen): "
           + ("als „Alternative (rechts)“ **einbezogen** (`MANUELL_ALT_RECHTS = True`)."
              if MANUELL_ALT_RECHTS else "**nicht einbezogen** (`MANUELL_ALT_RECHTS = False`)."),
           "",
           *[f"- {str(r['channel_title']).strip()} (`{r['channel_id']}`)" for _, r in manuell.iterrows()]]
          if manuell is not None and len(manuell) else []),
        "",
        "## Kanäle je Gruppe (alle Kanäle / nur vor Kriegsbeginn aktive)",
        "",
    ]
    for klass in aktive:
        z.append(f"**{KLASSIFIKATIONEN[klass]['titel']}**")
        z.append("")
        z.append("| Gruppe | alle | vorkrieg |")
        z.append("|---|---:|---:|")
        vk = kanaele["sample_vorkrieg"] == "ja"
        for g in KLASSIFIKATIONEN[klass]["gruppen"]:
            z.append(f"| {g} | {int((kanaele[klass] == g).sum())} | "
                     f"{int(((kanaele[klass] == g) & vk).sum())} |")
        z.append(f"| nicht zugeordnet | {int(kanaele[klass].isna().sum())} | "
                 f"{int((kanaele[klass].isna() & vk).sum())} |")
        z.append("")

    z += ["## Videos je Auswertung", "", f"| Sample | Klassifikation | Umfang | Videos | {'Quartale' if QUARTALSWEISE else 'Monate'} |",
          "|---|---|---|---:|---:|"]
    for (s, k, u), (n, m) in fallzahlen.items():
        z.append(f"| {s} | {k} | {u} | {n} | {m} |")
    z.append("")

    for spalte, titel in [("anteil", "Views-Anteile"), ("angebot_anteil", "Upload-Anteile")]:
        z += [f"## Phasenmittel der {'quartalsweisen' if QUARTALSWEISE else 'monatlichen'} {titel} (%)", "",
              f"Ungewichteter Mittelwert der {'Quartalswerte' if QUARTALSWEISE else 'Monatswerte'} je "
              f"Phase (Phasengrenzen in rel_monat"
              + ("; nur vollständig enthaltene Quartale: "
                 + ", ".join(f"{p} → Q{a} bis Q{b}" for p, (a, b) in
                             ((p, perioden_bereich(*ab)) for p, ab in PHASEN.items()))
                 if QUARTALSWEISE else "") + ").", ""]
        for (s, k, u, sp), tab in phasen_tabellen.items():
            if sp != spalte:
                continue
            z.append(f"**{SAMPLES[s][0]} – {KLASSIFIKATIONEN[k]['titel']} – {UMFAENGE[u][0]}**")
            z.append("")
            z += tabelle_md(tab.reindex(KLASSIFIKATIONEN[k]["gruppen"]))
            z.append("")

    z += [f"## Erzeugte Dateien ({len(erzeugt)})", ""] + [f"- `{d}`" for d in erzeugt]
    pfad = PFAD_PLOTS / dateiname
    pfad.write_text("\n".join(z) + "\n", encoding="utf-8")
    print(f"[Methodik] {pfad}")


# =========================================================
# SCHRITT 5: Robustheitsvariante Kanalindex (KANALINDEX)
# =========================================================

GEWICHT_EXPONENT = {"gleich": 0.0, "wurzel": 0.5, "linear": 1.0}
GEWICHT_LABEL = {"gleich": "gleich gewichtet (je Kanal 1)",
                 "wurzel": "gedämpft (√ Basis-Views)",
                 "linear": "linear (Basis-Views ≈ gepoolt)"}


def kanal_panel(v, gruppen_spalte):
    """Kanal x Periode-Panel (views, n_videos; Perioden ohne Upload = 0, erst ab
    dem ersten Upload des Kanals im Fenster) fuer Kanaele mit Gruppe und
    ausreichender Basis. index = views / basis_views * 100, gekappt bei
    KANALINDEX_KAPPUNG. Gibt zusaetzlich die ausgeschlossenen Kanaele zurueck
    (Series channel_id -> Gruppe)."""
    d = v[v[gruppen_spalte].notna()]
    p_von, p_bis = perioden_bereich(PERIODE_MIN, PERIODE_MAX)
    b_von, b_bis = perioden_bereich(*KANALINDEX_BASIS)
    gruppe = d.groupby("channel_id")[gruppen_spalte].first()
    zellen = d.groupby(["channel_id", "rel_periode"]).agg(
        views=("views", "sum"), n_videos=("views", "size"))
    voll = pd.MultiIndex.from_product([gruppe.index, range(p_von, p_bis + 1)],
                                      names=["channel_id", "rel_periode"])
    panel = zellen.reindex(voll, fill_value=0).reset_index()
    erster = panel[panel["n_videos"] > 0].groupby("channel_id")["rel_periode"].min()
    panel = panel[panel["rel_periode"] >= panel["channel_id"].map(erster)]

    basis = panel[panel["rel_periode"].between(b_von, b_bis)].groupby("channel_id").agg(
        basis_views=("views", "mean"), aktiv=("n_videos", lambda n: int((n > 0).sum())))
    ok = basis[(basis["aktiv"] >= KANALINDEX_MIN_AKTIV * (b_bis - b_von + 1))
               & (basis["basis_views"] > 0)]
    panel = panel[panel["channel_id"].isin(ok.index)].copy()
    panel["basis_views"] = panel["channel_id"].map(ok["basis_views"])
    panel["gruppe"] = panel["channel_id"].map(gruppe)
    panel["index"] = panel["views"] / panel["basis_views"] * 100
    if KANALINDEX_KAPPUNG is not None:
        panel["index"] = panel["index"].clip(upper=KANALINDEX_KAPPUNG)
    ausgeschlossen = gruppe.drop(ok.index)
    print(f"[Kanalindex] {gruppen_spalte}: {len(ok)} Kanaele mit Basis, "
          f"{len(ausgeschlossen)} ohne ausreichende Basis ausgeschlossen")
    return panel, ausgeschlossen


def kanalindex_werte(panel):
    """Je Gruppe und Periode: Views-Anteile je Gewichtung, Median-Index und
    Anteil der Kanaele ueber ihrer Basis. Perioden unter MIN_VIDEOS_PRO_MONAT
    (Basis-Kanaele zusammen) fallen wie in berechne_marktanteile() weg."""
    n_je = panel.groupby("rel_periode")["n_videos"].sum()
    p = panel[panel["rel_periode"].isin(n_je[n_je >= MIN_VIDEOS_PRO_MONAT].index)].copy()
    # Beitrag = index * basis^e: e = 1 ergibt (ungekappt) wieder die Views selbst
    for gew in KANALINDEX_GEWICHTUNGEN:
        p[f"beitrag_{gew}"] = p["index"] / 100 * p["basis_views"] ** GEWICHT_EXPONENT[gew]
    werte = p.groupby(["rel_periode", "gruppe"], as_index=False).agg(
        n_kanaele=("channel_id", "size"),
        median_index=("index", "median"),
        ueber_basis=("index", lambda x: (x > 100).mean() * 100),
        **{f"anteil_{g}": (f"beitrag_{g}", "sum") for g in KANALINDEX_GEWICHTUNGEN})
    for gew in KANALINDEX_GEWICHTUNGEN:
        spalte = f"anteil_{gew}"
        werte[spalte] = werte[spalte] / werte.groupby("rel_periode")[spalte].transform("sum") * 100
    return werte


def _zeitreihe(ax, werte, spalte, cfg, m_per):
    """Ein Panel im Stil von plotte(): Punkte + LOWESS (bzw. verbundene
    Quartalswerte), Kriegsbeginn und EREIGNISSE als senkrechte Linien."""
    for gruppe, farbe in zip(cfg["gruppen"], cfg["farben"]):
        r = werte[werte["gruppe"] == gruppe].sort_values("rel_periode")
        if r.empty:
            continue
        x = r["rel_periode"].to_numpy(dtype=float)
        y = r[spalte].to_numpy(dtype=float)
        if QUARTALSWEISE:
            ax.plot(x, y, color=farbe, linewidth=2, marker="o", markersize=4.5,
                    markeredgecolor="white", markeredgewidth=0.5, label=gruppe, zorder=3)
        else:
            ax.scatter(x, y, s=10, color=farbe, alpha=0.3, linewidths=0, zorder=2)
            ax.plot(x, glaette(x, y), color=farbe, linewidth=2, label=gruppe, zorder=3)
    ax.axvline(0, color="#52514e", linestyle="--", linewidth=1)
    ax.text(0.3 / m_per, 0.98, "Kriegsbeginn", transform=ax.get_xaxis_transform(),
            va="top", fontsize=8, color="#52514e")
    x_von, x_bis = werte["rel_periode"].min(), werte["rel_periode"].max() + 1
    for name, datum in EREIGNISSE.items():
        xe = ereignis_position(datum, m_per)
        if x_von <= xe <= x_bis:
            ax.axvline(xe, color="#8a8883", linestyle=":", linewidth=1.2, zorder=1)
            ax.text(xe + 0.3 / m_per, 0.98, name, transform=ax.get_xaxis_transform(), rotation=90,
                    va="top", ha="left", fontsize=7, color="#8a8883")
    ax.xaxis.set_major_locator(MultipleLocator(6 // m_per))
    ax.grid(color="#e5e4e0", linewidth=0.6)
    ax.set_axisbelow(True)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)


def plotte_kanalindex(werte, klass_key, n_kanaele, dateiname):
    """Obere Reihe: Views-Anteile je Gewichtung (eine Spalte je Gewichtung,
    gleiche y-Achse). Untere Reihe: Median-Index je Gruppe (Basis = 100) und
    Anteil der Kanaele ueber ihrer Basis."""
    cfg = KLASSIFIKATIONEN[klass_key]
    m_per = monate_pro_periode()
    n = max(len(KANALINDEX_GEWICHTUNGEN), 2)
    fig, achsen = plt.subplots(2, n, figsize=(max(5.2 * n, GRAFIK_MINDESTBREITE), 9.6),
                               sharex=True, squeeze=False)
    y_max = max(werte[f"anteil_{g}"].max() for g in KANALINDEX_GEWICHTUNGEN) * 1.05
    for i, gew in enumerate(KANALINDEX_GEWICHTUNGEN):
        ax = achsen[0, i]
        _zeitreihe(ax, werte, f"anteil_{gew}", cfg, m_per)
        ax.set_ylim(0, y_max)
        ax.set_title(GEWICHT_LABEL[gew], fontsize=11)
    achsen[0, 0].set_ylabel("Anteil an allen Views (%)")
    unten = [("median_index", "Median-Index der Kanäle (Basis = 100)", 100),
             ("ueber_basis", "Kanäle über ihrer Basis (%)", 50)]
    for i, (spalte, ylabel, referenz) in enumerate(unten):
        ax = achsen[1, i]
        _zeitreihe(ax, werte, spalte, cfg, m_per)
        ax.axhline(referenz, color="#52514e", linewidth=0.8, zorder=1)
        ax.set_ylim(bottom=0)
        ax.set_ylabel(ylabel)
        ax.set_xlabel("Quartal relativ zum Kriegsbeginn" if QUARTALSWEISE
                      else "Monat relativ zum Kriegsbeginn (24.02.2022)")
    # leere Panels ausblenden; darueberliegende Panels brauchen dann eigene x-Beschriftung
    for i in range(len(unten), n):
        achsen[1, i].axis("off")
        achsen[0, i].tick_params(labelbottom=True)
    for i in range(len(KANALINDEX_GEWICHTUNGEN), n):
        achsen[0, i].axis("off")
    handles, labels = achsen[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.02), frameon=False,
               fontsize=9, ncol=len(labels))
    fig.suptitle(f"Kanalindex (Robustheit): Views je Kanal normiert auf die Vorkriegsbasis – "
                 f"{cfg['titel']}", fontsize=12)
    kappung = f", Index gekappt bei {KANALINDEX_KAPPUNG}" if KANALINDEX_KAPPUNG is not None else ""
    fig.text(0.01, 0.005, f"{n_kanaele} Kanäle mit Basis (mittlere Views je {'Quartal' if QUARTALSWEISE else 'Monat'} "
             f"in Monat {KANALINDEX_BASIS[0]} bis {KANALINDEX_BASIS[1]}, mind. "
             f"{KANALINDEX_MIN_AKTIV:.0%} der Basisperioden mit Upload{kappung}); ohne erst später "
             "gestartete Kanäle.", fontsize=7.5, color="#52514e")
    fig.tight_layout(rect=(0, 0.07, 1, 0.97))
    PFAD_PLOTS.mkdir(parents=True, exist_ok=True)
    fig.savefig(PFAD_PLOTS / dateiname, dpi=150)
    plt.close(fig)
    print(f"[Plot] {PFAD_PLOTS / dateiname}")
    return [dateiname]


def schreibe_kanalindex_methodik(ergebnisse, gepoolt, kanaele, dateiname):
    """ergebnisse = {Klassifikation: (panel, werte, ausgeschlossen)};
    gepoolt = {Klassifikation: Anteile aus berechne_marktanteile() (Sample alle,
    Umfang alle)} als Vergleich zur Hauptgrafik."""
    name = kanaele.set_index("channel_id")["kanal_name"]
    b_von, b_bis = KANALINDEX_BASIS
    z = [
        "# Robustheit: Kanalindex statt gepoolter Views",
        "",
        "Skript: `src/youtube_code/step6_auswertung/marktanteil_rohdaten_plots.py` (`KANALINDEX = True`). "
        "Umfang: alle Videos, " + ", ".join(f"`format == {f}`" for f in FORMAT) + ".",
        "",
        "## Formel",
        "",
        "```",
        f"basis_c      = mittlere Views je Periode des Kanals c in rel_monat {b_von} bis {b_bis}",
        "               (Perioden ohne Upload = 0, gezaehlt ab dem ersten Upload des Kanals im Fenster)",
        "index_ct     = views_ct / basis_c * 100"
        + (f", gekappt bei {KANALINDEX_KAPPUNG}" if KANALINDEX_KAPPUNG is not None else ""),
        "anteil_gt    = sum_{c in g} index_ct * basis_c^e / sum_c index_ct * basis_c^e * 100",
        "               e = 1 (linear), 0.5 (wurzel), 0 (gleich)",
        "median_index = Median von index_ct ueber die Kanaele der Gruppe",
        "ueber_basis  = Anteil der Kanaele der Gruppe mit index_ct > 100 (%)",
        "```",
        "",
        f"- Nur Kanäle, die in mindestens {KANALINDEX_MIN_AKTIV:.0%} der Basisperioden etwas hochgeladen "
        "haben (erst kurz vor oder nach Kriegsbeginn gestartete Kanäle fallen raus). Nach dem letzten "
        "Upload zählen Perioden als 0 (eingestellte/gelöschte Kanäle = Verlust an Reichweite).",
        f"- Perioden mit < {MIN_VIDEOS_PRO_MONAT} Videos (Basis-Kanäle zusammen) entfallen.",
        "- **Lesehilfe:** *gepoolt (Hauptgrafik)* → *linear*: Effekt der Kanalauswahl (ohne später "
        "gestartete Kanäle" + (", plus Kappung" if KANALINDEX_KAPPUNG is not None else "") + "). "
        "*linear* → *wurzel* → *gleich*: Einfluss der Kanalgröße. Bei *gleich* entspricht der "
        "Vorkriegsanteil einer Gruppe ungefähr ihrem Anteil an den Kanälen; eine Verschiebung nach "
        "Kriegsbeginn heißt, dass der typische Kanal der Gruppe relativ zu den anderen gewachsen ist.",
        "- Unterschiede zwischen gepoolt und gleich gewichtet widerlegen die Hauptgrafik nicht, sondern "
        "zeigen, wie stark eine Verschiebung von wenigen großen Kanälen getragen wird.",
        "",
    ]
    for klass, (panel, werte, ausgeschlossen) in ergebnisse.items():
        cfg = KLASSIFIKATIONEN[klass]
        z += [f"## {cfg['titel']}", "", "### Kanäle je Gruppe", "",
              "| Gruppe | mit Basis | ausgeschlossen |", "|---|---:|---:|"]
        mit = panel.groupby("gruppe")["channel_id"].nunique()
        ohne = ausgeschlossen.value_counts()
        for g in cfg["gruppen"]:
            z.append(f"| {g} | {int(mit.get(g, 0))} | {int(ohne.get(g, 0))} |")
        if len(ausgeschlossen):
            z += ["", "Ausgeschlossen (keine ausreichende Basis): "
                  + "; ".join(f"{name.get(c, c)} ({g})" for c, g in ausgeschlossen.sort_values().items())]
        z.append("")

        z += ["### Phasenmittel der Views-Anteile (%)", "",
              "Ungewichteter Mittelwert der Periodenwerte je Phase (Phasen aus `PHASEN`).", ""]
        varianten = [("gepoolt, alle Kanäle (Hauptgrafik)", gepoolt[klass], "anteil")]
        varianten += [(GEWICHT_LABEL[g] + ", Basis-Kanäle", werte, f"anteil_{g}")
                      for g in KANALINDEX_GEWICHTUNGEN]
        for titel, daten, spalte in varianten:
            z += [f"**{titel}**", ""] + tabelle_md(phasenmittel(daten, spalte).reindex(cfg["gruppen"])) + [""]
        for spalte, titel in [("median_index", "Median-Index (Basis = 100)"),
                              ("ueber_basis", "Anteil Kanäle über ihrer Basis (%)")]:
            z += [f"### Phasenmittel {titel}", ""]
            z += tabelle_md(phasenmittel(werte, spalte).reindex(cfg["gruppen"])) + [""]

        # Index je Kanal: zeigt, welche Kanaele eine Gruppe treiben
        phasen = {p: perioden_bereich(a, b) for p, (a, b) in PHASEN.items()}
        je_kanal = pd.DataFrame({p: panel[panel["rel_periode"].between(a, b)]
                                .groupby("channel_id")["index"].mean() for p, (a, b) in phasen.items()})
        basis = panel.groupby("channel_id")[["basis_views", "gruppe"]].first()
        z += ["### Index je Kanal (Phasenmittel, Basis = 100)", "",
              f"Basis in Tsd. Views je {'Quartal' if QUARTALSWEISE else 'Monat'}; sortiert nach Gruppe und Basis.", "",
              "| Kanal | Gruppe | Basis | " + " | ".join(phasen) + " |",
              "|---|---|---:|" + "---:|" * len(phasen)]
        basis["rang"] = basis["gruppe"].map({g: i for i, g in enumerate(cfg["gruppen"])})
        for c, r in basis.sort_values(["rang", "basis_views"], ascending=[True, False]).iterrows():
            werte_k = " | ".join(f"{w:.0f}" if pd.notna(w) else "–" for w in je_kanal.loc[c])
            z.append(f"| {name.get(c, c)} | {r['gruppe']} | {r['basis_views'] / 1e3:.0f} | {werte_k} |")
        z.append("")
    pfad = PFAD_PLOTS / dateiname
    pfad.write_text("\n".join(z) + "\n", encoding="utf-8")
    print(f"[Kanalindex] {pfad}")


# =========================================================
# MAIN
# =========================================================

def main():
    if ANGEBOT_METRIK not in ("anteil", "anzahl"):
        raise SystemExit(f"ANGEBOT_METRIK muss 'anteil' oder 'anzahl' sein, nicht {ANGEBOT_METRIK!r}.")
    for name, datum in EREIGNISSE.items():
        try:
            pd.Timestamp(datum)
        except (ValueError, TypeError):
            raise SystemExit(f"EREIGNISSE[{name!r}]: {datum!r} ist kein gueltiges Datum (Format JJJJ-MM-TT).")
    if BETONUNG_MONATE is not None and not (
            len(BETONUNG_MONATE) == 2 and BETONUNG_MONATE[0] <= -1 and BETONUNG_MONATE[1] >= 0):
        raise SystemExit(f"BETONUNG_MONATE muss None oder (von, bis) mit von <= -1 und bis >= 0 sein, "
                         f"nicht {BETONUNG_MONATE!r}.")
    if not isinstance(ABSOLUT_VERSION, bool):
        raise SystemExit(f"ABSOLUT_VERSION muss True oder False sein, nicht {ABSOLUT_VERSION!r}.")
    if not isinstance(QUARTALSWEISE, bool):
        raise SystemExit(f"QUARTALSWEISE muss True oder False sein, nicht {QUARTALSWEISE!r}.")
    if QUARTALSWEISE and (STREU_START % 3 or STREU_INTERVALL % 3):
        raise SystemExit(f"Bei QUARTALSWEISE muessen STREU_START ({STREU_START}) und STREU_INTERVALL "
                         f"({STREU_INTERVALL}) durch 3 teilbar sein (Monate -> ganze Quartale).")
    if not isinstance(WOECHENTLICH, bool):
        raise SystemExit(f"WOECHENTLICH muss True oder False sein, nicht {WOECHENTLICH!r}.")
    if not isinstance(MIN_VIDEOS_PRO_WOCHE, int) or MIN_VIDEOS_PRO_WOCHE < 1:
        raise SystemExit(f"MIN_VIDEOS_PRO_WOCHE muss eine ganze Zahl >= 1 sein, nicht {MIN_VIDEOS_PRO_WOCHE!r}.")
    if not isinstance(WOCHEN_PLOT, bool):
        raise SystemExit(f"WOCHEN_PLOT muss True oder False sein, nicht {WOCHEN_PLOT!r}.")
    if WOCHEN_PLOT:
        if not (isinstance(WOCHEN_FENSTER, (list, tuple)) and len(WOCHEN_FENSTER) == 2):
            raise SystemExit(f"WOCHEN_FENSTER muss (von, bis) sein, nicht {WOCHEN_FENSTER!r}.")
        for w in WOCHEN_FENSTER:
            if isinstance(w, bool) or not isinstance(w, (int, str)):
                raise SystemExit(f"WOCHEN_FENSTER: {w!r} ist weder Datum 'JJJJ-MM-TT' noch ganze Zahl (rel_woche).")
            if isinstance(w, str):
                try:
                    pd.Timestamp(w)
                except (ValueError, TypeError):
                    raise SystemExit(f"WOCHEN_FENSTER: {w!r} ist kein gueltiges Datum (Format JJJJ-MM-TT).")
        w_von, w_bis = wochen_fenster()
        if w_von > w_bis:
            raise SystemExit(f"WOCHEN_FENSTER {WOCHEN_FENSTER}: von (Woche {w_von}) liegt nach bis (Woche {w_bis}).")
        if woche_start(w_von) < DATEN_START or woche_start(w_bis) + pd.Timedelta(days=6) > DATEN_ENDE:
            raise SystemExit(f"WOCHEN_FENSTER {WOCHEN_FENSTER} = {woche_start(w_von):%d.%m.%Y}–"
                             f"{woche_start(w_bis) + pd.Timedelta(days=6):%d.%m.%Y} liegt nicht vollstaendig in "
                             f"den Daten ({DATEN_START:%d.%m.%Y}–{DATEN_ENDE:%d.%m.%Y}).")
        if not (isinstance(WOCHEN_LOWESS_FRAC, (int, float)) and 0 <= WOCHEN_LOWESS_FRAC <= 1):
            raise SystemExit(f"WOCHEN_LOWESS_FRAC muss eine Zahl in [0, 1] sein, nicht {WOCHEN_LOWESS_FRAC!r}.")
        if (isinstance(WOCHEN_LOWESS_HINTERGRUND, bool)
                or not isinstance(WOCHEN_LOWESS_HINTERGRUND, (int, float))
                or not 0 <= WOCHEN_LOWESS_HINTERGRUND <= 1):
            raise SystemExit(f"WOCHEN_LOWESS_HINTERGRUND muss eine Zahl in [0, 1] sein (0 = keine "
                             f"Hintergrundlinie), nicht {WOCHEN_LOWESS_HINTERGRUND!r}.")
    if not isinstance(INTERAKTIV, bool):
        raise SystemExit(f"INTERAKTIV muss True oder False sein, nicht {INTERAKTIV!r}.")
    if INTERAKTIV:
        try:
            import plotly  # noqa: F401
        except ImportError:
            raise SystemExit("INTERAKTIV = True braucht das Paket plotly "
                             "(.venv/Scripts/python.exe -m pip install plotly).")
    if KOMBI_VERSION not in ("kombi", "getrennt", "alle"):
        raise SystemExit(f"KOMBI_VERSION muss 'kombi', 'getrennt' oder 'alle' sein, nicht {KOMBI_VERSION!r}.")
    falsch = [u for u in UMFANG_ZUSATZ if u not in UMFAENGE or u == "alle"]
    if falsch:
        raise SystemExit(f"UMFANG_ZUSATZ enthaelt ungueltige Umfaenge {falsch}; "
                         f"erlaubt: {[u for u in UMFAENGE if u != 'alle']}.")
    if UMFANG_LAYOUT not in ("einzeln", "kombiniert", "beide"):
        raise SystemExit(f"UMFANG_LAYOUT muss 'einzeln', 'kombiniert' oder 'beide' sein, nicht {UMFANG_LAYOUT!r}.")
    if not isinstance(POPULISMUS_TERTILE, bool):
        raise SystemExit(f"POPULISMUS_TERTILE muss True oder False sein, nicht {POPULISMUS_TERTILE!r}.")
    if not isinstance(GRAFIK_MINDESTBREITE, (int, float)) or GRAFIK_MINDESTBREITE <= 0:
        raise SystemExit(f"GRAFIK_MINDESTBREITE muss eine Zahl > 0 (Zoll) sein, nicht {GRAFIK_MINDESTBREITE!r}.")
    unbekannt = [t for t in KEYWORD_THEMEN if t not in TOPIC_KEYWORDS]
    if not KEYWORD_THEMEN or unbekannt:
        raise SystemExit(f"KEYWORD_THEMEN darf nicht leer sein und nur Themen aus TOPIC_KEYWORDS "
                         f"enthalten; unbekannt: {unbekannt}, erlaubt: {list(TOPIC_KEYWORDS)}.")
    if KEYWORD_VARIANTE not in ("core", "cw"):
        raise SystemExit(f"KEYWORD_VARIANTE muss 'core' oder 'cw' sein, nicht {KEYWORD_VARIANTE!r}.")
    if not isinstance(POPULISMUS_MEDIAN, bool):
        raise SystemExit(f"POPULISMUS_MEDIAN muss True oder False sein, nicht {POPULISMUS_MEDIAN!r}.")
    if not isinstance(MEDIENTYP_GESAMT, bool):
        raise SystemExit(f"MEDIENTYP_GESAMT muss True oder False sein, nicht {MEDIENTYP_GESAMT!r}.")
    aktive = [k for k in KLASSIFIKATIONEN if k not in SCHALTER or globals()[SCHALTER[k]]]
    unbekannt = [u for u in STREU_UMFAENGE if u not in UMFAENGE]
    if unbekannt:
        raise SystemExit(f"STREU_UMFAENGE enthaelt unbekannte Umfaenge {unbekannt}; "
                         f"erlaubt: {list(UMFAENGE)}.")
    for k, gruppen in STREU_GRUPPEN.items():
        if k not in KLASSIFIKATIONEN:
            raise SystemExit(f"STREU_GRUPPEN: unbekannte Klassifikation {k!r}; erlaubt: {list(KLASSIFIKATIONEN)}.")
        falsch = [g for g in gruppen if g not in KLASSIFIKATIONEN[k]["gruppen"]]
        if falsch:
            raise SystemExit(f"STREU_GRUPPEN[{k!r}]: unbekannte Gruppen {falsch}; "
                             f"erlaubt: {KLASSIFIKATIONEN[k]['gruppen']}.")
    if STREU_LAYOUT not in ("gemeinsam", "getrennt", "beide"):
        raise SystemExit(f"STREU_LAYOUT muss 'gemeinsam', 'getrennt' oder 'beide' sein, nicht {STREU_LAYOUT!r}.")
    if STREU_ZOOM not in ("intervalle", "monate"):
        raise SystemExit(f"STREU_ZOOM muss 'intervalle' oder 'monate' sein, nicht {STREU_ZOOM!r}.")
    if STREU_DIAGONAL_ABSTAND < 0:
        raise SystemExit("STREU_DIAGONAL_ABSTAND muss >= 0 sein (0 = keine Hilfslinien).")
    if not (PERIODE_MIN <= STREU_START <= PERIODE_MAX) or STREU_INTERVALL < 1:
        raise SystemExit(f"STREU_START muss in [{PERIODE_MIN}, {PERIODE_MAX}] liegen und "
                         f"STREU_INTERVALL >= 1 sein.")
    if not isinstance(KANALLISTE, (list, tuple, set)) or not all(isinstance(c, str) for c in KANALLISTE):
        raise SystemExit("KANALLISTE muss eine Liste von channel_id-Strings sein (leer = alle Kanaele).")
    if (not isinstance(KANAELE_AUSSCHLIESSEN, (list, tuple, set))
            or not all(isinstance(c, str) and c.strip() for c in KANAELE_AUSSCHLIESSEN)):
        raise SystemExit("KANAELE_AUSSCHLIESSEN muss eine Liste nicht leerer Strings (channel_id oder "
                         "Kanaltitel) sein (leer = kein Ausschluss).")
    global _AUSSCHLUSS_ZUSATZ
    _AUSSCHLUSS_ZUSATZ = ""
    if not isinstance(MANUELL_ALT_RECHTS, bool):
        raise SystemExit(f"MANUELL_ALT_RECHTS muss True oder False sein, nicht {MANUELL_ALT_RECHTS!r}.")
    if not isinstance(KANALINDEX, bool):
        raise SystemExit(f"KANALINDEX muss True oder False sein, nicht {KANALINDEX!r}.")
    if not isinstance(OERR_DOKU_CODES, (list, tuple)) or not set(OERR_DOKU_CODES) <= {0, 1, 2, 3, 4, 5}:
        raise SystemExit(f"OERR_DOKU_CODES muss eine Liste von sample-Codes 0-5 sein (leer = keine "
                         f"Trennung), nicht {OERR_DOKU_CODES!r}.")
    setze_oerr_doku_gruppe()
    if KANALINDEX:
        if not (len(KANALINDEX_BASIS) == 2 and PERIODE_MIN <= KANALINDEX_BASIS[0] <= KANALINDEX_BASIS[1] <= -1):
            raise SystemExit(f"KANALINDEX_BASIS muss (von, bis) mit {PERIODE_MIN} <= von <= bis <= -1 "
                             f"sein, nicht {KANALINDEX_BASIS!r}.")
        b_von, b_bis = perioden_bereich(*KANALINDEX_BASIS)
        if b_von > b_bis:
            raise SystemExit(f"KANALINDEX_BASIS {KANALINDEX_BASIS} enthaelt kein vollstaendiges Quartal.")
        if not 0 < KANALINDEX_MIN_AKTIV <= 1:
            raise SystemExit(f"KANALINDEX_MIN_AKTIV muss in (0, 1] liegen, nicht {KANALINDEX_MIN_AKTIV!r}.")
        falsch = [g for g in KANALINDEX_GEWICHTUNGEN if g not in GEWICHT_EXPONENT]
        if not KANALINDEX_GEWICHTUNGEN or falsch:
            raise SystemExit(f"KANALINDEX_GEWICHTUNGEN darf nicht leer sein; ungueltig: {falsch}, "
                             f"erlaubt: {list(GEWICHT_EXPONENT)}.")
        if KANALINDEX_KAPPUNG is not None and not (
                isinstance(KANALINDEX_KAPPUNG, (int, float)) and KANALINDEX_KAPPUNG > 100):
            raise SystemExit(f"KANALINDEX_KAPPUNG muss None oder eine Zahl > 100 sein, nicht {KANALINDEX_KAPPUNG!r}.")
    kanaele, grenzen = bilde_gruppen(lade_kanaele())
    # Ausschluss gegen alle Kanaele aufloesen, damit Kanaele ausserhalb von
    # KANALLISTE nur eine Warnung statt "unbekannt" erzeugen
    ausschluss = loese_ausschluss_auf(kanaele) if KANAELE_AUSSCHLIESSEN else None
    ausschluss_tab = None
    if KANALLISTE:
        fehlend = sorted(set(KANALLISTE) - set(kanaele["channel_id"]))
        if fehlend:
            print(f"[Kanalliste] {len(fehlend)} channel_ids nicht in kanaele_roh: {fehlend}")
        kanaele = kanaele[kanaele["channel_id"].isin(KANALLISTE)]
        if kanaele.empty:
            raise SystemExit("KANALLISTE: keine der channel_ids kommt in kanaele_roh vor.")
        print(f"[Kanalliste] Sample auf {len(kanaele)} Kanaele eingeschraenkt.")
        print(f"[Kanalliste] Medientyp: {kanaele['medientyp'].value_counts(dropna=False).to_dict()}")
    if OERR_DOKU_CODES and not (kanaele["medientyp_ideologie"] == OERR_DOKU_GRUPPE).any():
        raise SystemExit(f"OERR_DOKU_CODES = {OERR_DOKU_CODES}: kein ÖRR-Kanal mit diesen sample-Codes "
                         "im Sample; KANALLISTE (Filter auf sample) muss die Codes enthalten.")
    kanaele, manuell = manuell_alt_rechts(kanaele)
    # Tertilgrenzen und Median erst hier: nur ueber die Kanaele im tatsaechlichen
    # Sample (nach KANALLISTE und MANUELL_ALT_RECHTS), fest fuer beide SAMPLES
    kanaele, grenzen = bilde_tertil_gruppen(kanaele)
    kanaele, median = bilde_median_gruppen(kanaele)
    if POPULISMUS_TERTILE:
        print(f"[Tertile] Tertilgrenzen pop_baseline im Sample: {grenzen[0]:.3f} / {grenzen[1]:.3f}")
    if POPULISMUS_MEDIAN:
        print(f"[Median] pop_baseline-Median der alternativen Kanaele im Sample: {median:.3f}")
    videos = lade_videos().merge(
        kanaele[["channel_id", "sample_vorkrieg", *aktive]], on="channel_id", how="left")
    # Wochen-Videos (WOCHEN_PLOT) getrennt, Periodenfenster fuer alles andere
    videos_w = videos[videos["rel_woche"].between(*wochen_fenster())] if WOCHEN_PLOT else None
    videos = videos[videos["rel_periode"].between(*perioden_bereich(PERIODE_MIN, PERIODE_MAX))]
    if ausschluss is not None:
        # erst nach Gruppen-/Tertil-/Median-Bildung: Gruppendefinition bleibt wie ohne
        # Ausschluss, nur der Beitrag dieser Kanaele faellt weg
        im_sample = ausschluss["channel_id"].isin(kanaele["channel_id"])
        for _, r in ausschluss[~im_sample].iterrows():
            print(f"[Ausschluss] {r['titel']} ({r['channel_id']}) ist nach KANALLISTE ohnehin nicht "
                  "im Sample - ignoriert.")
        ausschluss = ausschluss[im_sample].reset_index(drop=True)
        if ausschluss.empty:
            print("[Ausschluss] Keiner der Kanaele aus KANAELE_AUSSCHLIESSEN ist im Sample; kein Ausschluss.")
            ausschluss = None
        else:
            ausschluss_tab = berichte_ausschluss(videos, ausschluss, aktive)
            kanaele = kanaele[~kanaele["channel_id"].isin(ausschluss["channel_id"])]
            videos = videos[~videos["channel_id"].isin(ausschluss["channel_id"])]
            if videos_w is not None:
                videos_w = videos_w[~videos_w["channel_id"].isin(ausschluss["channel_id"])]
            _AUSSCHLUSS_ZUSATZ = ausschluss_zusatz(ausschluss)
    berichte_populismus(kanaele, aktive)

    # Dateinamenszusatz: Format(e), bei QUARTALSWEISE zusaetzlich _quartal
    # bei MANUELL_ALT_RECHTS zusaetzlich _manuell, bei OERR_DOKU_CODES _oerrdoku
    # (auch an CSV-/Methodik-Dateien)
    zusatz_man = datei_zusatz()
    fmt = "_".join(FORMAT) + ("_quartal" if QUARTALSWEISE else "") + zusatz_man
    erzeugt, alle_werte, fallzahlen, phasen_tabellen = [], [], {}, {}
    wochen_werte = []   # nur bei WOECHENTLICH
    je_sample = {}   # (Sample, Klassifikation) -> {Umfang: Anteile}, fuer KOMBI_VERSION
    for s_key, (s_label, s_filter) in SAMPLES.items():
        s_ids = set(kanaele.loc[s_filter(kanaele), "channel_id"])
        v_s = videos[videos["channel_id"].isin(s_ids)]
        for k_key in aktive:
            je_umfang = {}
            for u_key, (_, u_filter) in UMFAENGE.items():
                teil = v_s[u_filter(v_s)]
                anteile = berechne_marktanteile(teil, k_key)
                je_umfang[u_key] = anteile
                fallzahlen[(s_key, k_key, u_key)] = (int(teil[k_key].notna().sum()),
                                                     anteile["rel_periode"].nunique())
                for spalte in ["anteil", "angebot_anteil"]:
                    phasen_tabellen[(s_key, k_key, u_key, spalte)] = phasenmittel(anteile, spalte)
                alle_werte.append(anteile.assign(sample=s_key, klassifikation=k_key, umfang=u_key))
                if WOECHENTLICH:
                    wochen_werte.append(wochen_marktanteile(teil, k_key).assign(
                        sample=s_key, klassifikation=k_key, umfang=u_key))
                if u_key in STREU_UMFAENGE and k_key in STREU_GRUPPEN:
                    streu_name = f"uploads_vs_views_{k_key}_{u_key}_{s_key}_{fmt}.png"
                    erzeugt += plotte_streu(anteile, k_key, u_key, s_label, streu_name)
            je_sample[(s_key, k_key)] = je_umfang
    erzeugt += zeitreihen_grafiken(je_sample, aktive, fmt)

    if WOCHEN_PLOT:
        # Wochenweise Zeitreihen im eigenen Fenster, sonst gleiche Einstellungen
        w_von, w_bis = wochen_fenster()
        fenster = f"{woche_start(w_von):%Y%m%d}-{woche_start(w_bis) + pd.Timedelta(days=6):%Y%m%d}"
        print(f"[Wochen] Fenster Woche {w_von}..{w_bis} ({fenster})")
        je_sample_w, w_plot_werte = {}, []
        for s_key, (_, s_filter) in SAMPLES.items():
            v_s = videos_w[videos_w["channel_id"].isin(set(kanaele.loc[s_filter(kanaele), "channel_id"]))]
            for k_key in aktive:
                je_sample_w[(s_key, k_key)] = {}
                for u_key, (_, u_filter) in UMFAENGE.items():
                    w = wochen_marktanteile(v_s[u_filter(v_s)], k_key, (w_von, w_bis))
                    je_sample_w[(s_key, k_key)][u_key] = w
                    w_plot_werte.append(w.assign(sample=s_key, klassifikation=k_key, umfang=u_key))
        fmt_w = "_".join(FORMAT) + f"_woche_{fenster}" + zusatz_man
        erzeugt += zeitreihen_grafiken(je_sample_w, aktive, fmt_w, woche=True)
        wp_name = f"marktanteil_woche_{fenster}{zusatz_man}.csv"
        pd.concat(w_plot_werte)[["sample", "klassifikation", "umfang", "rel_periode", "woche_start",
                                 "woche_ende", "gruppe", "anteil", "angebot_anteil", "views_summe",
                                 "n_videos", "views_gesamt", "n_gesamt"]].rename(
            columns={"rel_periode": "rel_woche"}).to_csv(PFAD_PLOTS / wp_name, index=False)
        erzeugt.append(wp_name)

    if KANALINDEX:
        # Robustheit: Views je Kanal auf Vorkriegsbasis normiert (nur Umfang "alle")
        ergebnisse, ki_werte = {}, []
        for k_key in aktive:
            panel, ausgeschlossen = kanal_panel(videos, k_key)
            werte = kanalindex_werte(panel)
            ergebnisse[k_key] = (panel, werte, ausgeschlossen)
            ki_werte.append(werte.assign(klassifikation=k_key))
            erzeugt += plotte_kanalindex(werte, k_key, panel["channel_id"].nunique(),
                                         f"kanalindex_{k_key}_{fmt}.png")
        ki_csv = f"kanalindex_{periode_name()}{zusatz_man}.csv"
        pd.concat(ki_werte).rename(columns={"rel_periode": f"rel_{periode_name()}"}).to_csv(
            PFAD_PLOTS / ki_csv, index=False)
        ki_md = ("kanalindex_methodik_quartal" if QUARTALSWEISE else "kanalindex_methodik") + zusatz_man + ".md"
        schreibe_kanalindex_methodik(ergebnisse, {k: je_sample[("alle", k)]["alle"] for k in aktive},
                                     kanaele, ki_md)
        erzeugt += [ki_csv, ki_md]

    csv =pd.concat(alle_werte)[["sample", "klassifikation", "umfang", "rel_periode", "gruppe",
                                 "anteil", "angebot_anteil", "views_summe", "n_videos",
                                 "views_gesamt", "n_gesamt"]]
    # Datumsbereich je Periode (inklusive), wie woche_start/woche_ende der Wochen-CSV
    m_per, kb = monate_pro_periode(), pd.Timestamp(KRIEGSBEGINN)
    beginn = {p: kb + pd.DateOffset(months=int(p) * m_per) for p in csv["rel_periode"].unique()}
    csv.insert(4, f"{periode_name()}_start", csv["rel_periode"].map(lambda p: beginn[p].date()))
    csv.insert(5, f"{periode_name()}_ende", csv["rel_periode"].map(
        lambda p: (beginn[p] + pd.DateOffset(months=m_per) - pd.Timedelta(days=1)).date()))
    csv = csv.rename(columns={"rel_periode": f"rel_{periode_name()}"})
    csv_name = f"marktanteil_{periode_name()}{zusatz_man}.csv"
    csv.to_csv(PFAD_PLOTS / csv_name, index=False)
    erzeugt.append(csv_name)
    if WOECHENTLICH:
        w_csv = pd.concat(wochen_werte)[["sample", "klassifikation", "umfang", "rel_periode", "woche_start",
                                         "woche_ende", "gruppe", "anteil", "angebot_anteil", "views_summe",
                                         "n_videos", "views_gesamt", "n_gesamt"]]
        w_name = f"marktanteil_woche{zusatz_man}.csv"
        w_csv.rename(columns={"rel_periode": "rel_woche"}).to_csv(PFAD_PLOTS / w_name, index=False)
        erzeugt.append(w_name)
    schreibe_methodik(kanaele, grenzen, fallzahlen, phasen_tabellen, erzeugt, aktive,
                      ("marktanteil_methodik_quartal" if QUARTALSWEISE else "marktanteil_methodik")
                      + zusatz_man + ".md", manuell, median, ausschluss_tab)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
frage4_kriegspraemie_medientyp_bericht.py

Erweiterung von Forschungsfrage 4 (.claude/CLAUDE.md) um die Medientyp-Dimension:
gibt es fuer BESTIMMTE Medientypen eine "Kriegspraemie" - sind ihre Kriegsvideos
(ist_kriegsvideo == 1) erfolgreicher als ihre sonstigen Videos, kontrolliert fuer
Kanal-Fixed-Effects UND volle Perioden-Fixed-Effects (nicht nur einen Post-Dummy)?
Baut auf denselben Grundlagen wie frage4_kriegsvideos_erfolg_bericht.py
(channel_video_erfolg.csv, frage1_kanal_whitelist.csv) auf, ergaenzt aber Medientyp/
Ideologie (Alternative Medien getrennt nach links/mitte/rechts, siehe
alternative-medien-ideologie-differenzierung) als Interaktionsdimension statt nur
den Vorher/Nachher-Post-Dummy zu testen. Siehe frage2_4_methodik_und_stichprobe.md
Abschnitt 7 fuer die formale Modellgleichung.

ANDERS als frage4_kriegsvideos_erfolg_bericht.py (dort: post x ist_kriegsvideo,
also "wird der Post-Effekt durch Kriegsvideos verstaerkt?") ist die hier
beantwortete Frage EBENENVERSCHIEDEN: "ist ein Kriegsvideo - unabhaengig von der
Periode, in der es erscheint - erfolgreicher als ein sonstiges Video DESSELBEN
Kanals in DERSELBEN Periode, und unterscheidet sich das nach Medientyp?" Die
Perioden-FE (volle Saettigung wie in fe_signifikanz_test.py, nicht nur ein
Post-Dummy) fangen dabei gemeinsame Zeittrends/den allgemeinen Kriegsbeginn-Schub
auf, sodass ist_kriegsvideo:gruppe5 wirklich nur die THEMENSPEZIFISCHE Praemie
misst (nicht "alle Videos wurden nach Kriegsbeginn erfolgreicher").

Modell (je Metrik, siehe DIMENSIONEN; seit 2026-09-08 zusaetzlich mit
log_duration_mean als Kontrollvariable, siehe Abschnitt "VIDEOLAENGE" unten, und
log_upload_dichte_mean, siehe Abschnitt "UPLOAD-DICHTE" unten):

    y ~ C(channel_id) + C(periode) + log_duration_mean + log_upload_dichte_mean
        + ist_kriegsvideo:C(gruppe5)

Bewusst OHNE eigenen gruppe5-Haupteffekt (gruppe5 ist zeitkonstant je Kanal und
daher vollstaendig mit den Kanal-FE kollinear, analog interaktions_test() in
bericht_utils.py) und OHNE eigenen ist_kriegsvideo-Haupteffekt: weil gruppe5
NIRGENDS sonst als eigenstaendiger Term im Modell auftaucht, kodiert patsy
C(gruppe5) INNERHALB der Interaktion automatisch VOLLRANGIG (ein Dummy je Gruppe,
keine Referenzgruppe faellt weg) - jeder Koeffizient
"ist_kriegsvideo:C(gruppe5)[G]" ist dadurch DIREKT als "geschaetzte Kriegspraemie
der Gruppe G" interpretierbar (kein Vergleich gegen eine Referenzkategorie noetig).
Verifiziert mit einem synthetischen Beispiel (eingebauter Effekt nur in einer
Gruppe wird nur dort und korrekt in der Groessenordnung wiedergefunden, alle
anderen Gruppen ~0) - siehe .claude/plans (Chatverlauf-Diagnose dieser
Skripterstellung). Zusaetzlich ein gemeinsamer F-Test (paarweise Gleichheits-
Constraints zwischen allen Interaktionskoeffizienten), der direkt prueft, ob sich
die Kriegspraemie ZWISCHEN den Medientyp/Ideologie-Gruppen unterscheidet, sowie
ein gepooltes Vergleichsmodell OHNE Gruppenaufspaltung (ein einzelner
ist_kriegsvideo-Koeffizient) als Effektgroessen-Baseline.

Die Regression laeuft wie bei frage4_kriegsvideos_erfolg_bericht.py NICHT auf
Video-Ebene, sondern auf Kanal x Periode x Kriegsvideo-Zellen
(aggregiere_zellen()) - sonst wuerden Kanal-Perioden mit ueberdurchschnittlich
vielen Videos die Schaetzung staerker gewichten. Anders als dort wird je Zelle
NICHT nur ein Mittelwert gebildet, sondern gleich mehrere View-Metriken
(Mittelwert, Median, winsorisierter Mittelwert 5%/95% UND 1%/99%, log_views-
Mittelwert) - deckt die vom Nutzer gewuenschten "verschiedenen Metriken" als
Robustheitscheck ab (dieselbe Winsorisierungsfunktion wie
frage2_sensitivitaet_plots.py, per bare sibling import wiederverwendet).
MIN_VIDEOS_PRO_ZELLE filtert duenn besetzte Zellen (wie dort), MIN_KANAELE_JE_GRUPPE
schliesst gruppe5-Kategorien mit zu wenigen Kanaelen MIT mindestens einer
Kriegsvideo-Zelle aus dem Interaktionsmodell aus (analog bericht_utils.py::
interaktions_test()).

GRANULARITAET = "quartal" ist die primaere Spezifikation (Kriegsvideos sind pro
Kanal-Monat oft duenn besetzt, wie bei frage4_kriegsvideos_erfolg_bericht.py),
"monat" laeuft als Zusatzcheck mit.

PHASENAUFTEILUNG (PHASEN_AKTIV/PHASEN, Nutzervorgabe): der Kriegsbeginn ist keine
gleichmaessig saliente exogene Variation - die politische/mediale Aufmerksamkeit
fuer das Thema schwankt stark ueber die gut drei Kriegsjahre, mit jeweils eigener
Erwartung an eine sichtbare Kriegspraemie:

    P1 Schock und Konsens             (Monat  0-6,  Feb-Aug 2022)
    P2 Energiekrise und Bruch         (Monat  7-18, Sep 2022-Aug 2023)
    P3 Aufmerksamkeitsverdraengung    (Monat 19-26, Okt 2023-Mai 2024)
    P4 Wahlkampfphase                 (Monat 27-36, Jun 2024-Feb 2025)
    P5 Nachwahlphase                  (Monat 37+,   ab Maer 2025)

(volle Begruendung samt Ereignissen je Phase in PHASEN unten). Ist PHASEN_AKTIV =
True (Standard), laeuft NEBEN der bestehenden Gesamtzeitraum-Analyse ("gesamt",
unveraendertes Verhalten) zusaetzlich je Phase EIN EIGENER, in sich abgeschlossener
Lauf desselben Modells (eigene Kanal-FE + Perioden-FE NUR ueber die Perioden
innerhalb dieser Phase, eigene Zellfilter/Gruppenfilter) - zeigt, OB und WANN eine
Kriegspraemie ueberhaupt sichtbar wird, statt sie ueber den gesamten Zeitraum
gemittelt (und damit ggf. verwaschen) zu schaetzen. Phasengrenzen werden IMMER in
rel_monat gefiltert (_phase_fenster()), unabhaengig von GRANULARITAET - bei
GRANULARITAET="quartal" entsprechen die Phasengrenzen dadurch exakt den oben
vorgegebenen Monaten (keine Rundung auf Quartalsgrenzen), die C(periode)-FE werden
aber weiterhin auf rel_quartal gebildet. PHASEN_AKTIV = False schaltet auf das
urspruengliche Verhalten zurueck (nur die Gesamtzeitraum-Analyse).

VIDEOLAENGE (DAUER_TEILSTICHPROBEN_AKTIV/DAUER_TEILSTICHPROBEN, seit 2026-09-08,
.claude/Aufgaben.md letzter Absatz + Nutzervorgabe "Integriere die Videodauer... als
Kontrollvariable... und eine laengen-eingegrenzte Sensitivitaets-Teilstichprobe"):
Kriegsvideos sind in JEDER Gruppe5-Kategorie deutlich laenger als sonstige Videos
(siehe scripts/adhoc/videolaenge_diagnose.py, Faktor 1,7x-5,3x im Median) UND laengere
Videos bekommen (v.a. bei Kriegsvideos) mehr Views - ein Teil der hier gefundenen
Kriegspraemie koennte damit ein reiner Laengeneffekt sein. ZWEI Massnahmen dagegen:
(1) Kontrollvariable log_duration_mean (Zellmittel von log_duration_seconds, analog zu
log_views als View-Metrik) wird in BEIDE Modelle (kriegspraemie_je_gruppe_test(),
kriegspraemie_gesamt_test()) als zusaetzlicher additiver Term aufgenommen - haelt den
Effekt konstant fuer die durchschnittliche Videolaenge der Zelle, wird selbst NICHT
separat ausgegeben (reine Kontrollgroesse). (2) DAUER_TEILSTICHPROBEN definiert
konfigurierbare, feste Minuten-Intervalle (Nutzervorgabe: feste statt perzentilbasierte
Grenzen, dafuer frei anpassbar/erweiterbar als Dict) - jedes Intervall filtert die
Video-Ebene VOR aggregiere_zellen() (gemeinsame Filterfunktion
bericht_utils.py::dauer_teilstichprobe()) und laeuft als eigener, vollstaendiger
Analyselauf (wie eine zusaetzliche PHASE) neben der "voll"-Stichprobe (keine
Laengenbeschraenkung) - fuer JEDE Kombination aus Zeitfenster (Gesamtzeitraum + jede
PHASE) x Stichprobe (voll + jede DAUER_TEILSTICHPROBE), siehe verarbeite_granularitaet().
Ergebnis-CSV bekommt dafuer zwei zusaetzliche Spalten "stichprobe"/"stichprobe_label"
(analog "phase"/"phase_label").

UPLOAD-DICHTE (seit 2026-09-08, Nutzervorgabe "Bau jetzt die Upload-Dichte als
Kontrollvariable ein" - auf die Frage "gibt es noch weitere Kontrollvariablen"):
log_upload_dichte_mean (Zellmittel von log_upload_dichte, bericht_utils.py::
berechne_upload_dichte()) misst die Konkurrenz um Aufmerksamkeit INNERHALB des
Kanals. ANDERS als age_days (siehe populismuspraemie_kriegsvideos_bericht.py, dort
bewusst NICHT hier ergaenzt) wird diese Variable NICHT durch die vorhandenen
Perioden-FE (C(periode)) redundant: die Perioden-FE kontrollieren gemeinsame
Zeittrends UEBER alle Kanaele hinweg, nicht die kanalspezifische Aktivitaet INNERHALB
einer Periode - ein Kanal, der kurz vor/nach einem Video besonders viele weitere
Videos postet, kann das unabhaengig vom allgemeinen Zeittrend tun.

Seit 2026-09-09 (Nutzervorgabe: "es kommt auf Videos kurz vor und nach dem jeweiligen
Video an") ist log_upload_dichte log1p der Anzahl ANDERER Videos DESSELBEN Kanals
(ALLE Themen), deren published_at innerhalb von +/- 48 Stunden um das published_at
des jeweiligen Videos liegt (statt vorher: alle Videos derselben rel_monat/
rel_quartal-Periode) - eine Periodengrenze trennte vorher benachbarte Videos, die nur
Stunden auseinander lagen, kuenstlich in unterschiedliche Zellen. Die Dichte ist
dadurch eine VIDEO-eigene, granularitaetsUNABHAENGIGE Kennzahl geworden (frueher:
Kanal x Periode-Kennzahl, separat je Granularitaet) - lade_video_daten() berechnet
sie deshalb nur noch EINMAL (Spalte "log_upload_dichte", nicht mehr
log_upload_dichte_monat/_quartal) auf der VOLLEN, noch ungefilterten Video-Menge
(nicht erst nach Phasen-/Dauer-Teilstichproben-Filterung, damit die Dichte die
tatsaechliche Kanalaktivitaet abbildet); aggregiere_zellen()/
aggregiere_kanal_periode_anteil() bilden daraus wie bei log_duration_mean ein
Zellmittel (die Dichte variiert jetzt INNERHALB einer Kanal-Periode-Zelle zwischen
den einzelnen Videos, der Mittelwert ist hier also - anders als bei der frueheren
periodenbasierten Zaehlung - eine echte Aggregation, kein reiner Formalismus mehr).

ZUSATZSPEZIFIKATIONEN: alternative Beobachtungseinheiten (VIDEO_EBENE_AKTIV/
ANTEIL_DESIGN_AKTIV, seit 2026-09-08, Nutzerfrage im Chat "Lass uns zwei neue
Beobachtungseinheiten ausprobieren"): Baustein 1/2 oben aggregiert IMMER zu
Kanal x Periode x ist_kriegsvideo-Zellen (Begruendung siehe oben) - zwei alternative
Designs pruefen, ob dieses Wahl der Beobachtungseinheit das Ergebnisbild veraendert:

    BAUSTEIN 3 (VIDEO_EBENE_AKTIV, _fuehre_lauf_video_ebene()/verarbeite_video_ebene()):
    dieselbe ist_kriegsvideo:C(gruppe5)-Interaktion wie Baustein 1, aber OHNE
    Zellenaggregation - jedes Video ist eine eigene Beobachtung, Kanal-FE + volle
    Perioden-FE + Laengen-/Upload-Dichte-Kontrolle bleiben (jetzt als Video-eigene
    Werte statt Zellmittel: log_duration_seconds statt log_duration_mean). Explizit
    GEWOLLTER Nebeneffekt (Nutzervorgabe: "in dem Wissen, dass grosse Kanaele dann
    dominieren werden"): Kanaele mit vielen Videos je Kanal-Periode wiegen hier
    automatisch staerker, waehrend Baustein 1 durch die Zellmittelung jede
    Kanal-Periode gleich gewichtet - ein Vergleich beider zeigt, ob die
    Kriegspraemie robust gegen diese Gewichtungsfrage ist. Nur DIMENSION="log_views"
    (Median/winsorisierter Mittelwert aus DIMENSIONEN sind auf Einzelvideo-Ebene
    bedeutungslos, die gehoeren zu Baustein 1's Zellmittelung). Laeuft NUR fuer
    GRANULARITAET="quartal" (Entscheidung 1, .claude/plans/frage4_kriegspraemie_
    vergleichsgruppen_und_beobachtungseinheiten.md, 2026-09-08): auf Video-Ebene macht
    die Granularitaet ausser der Aufloesung der Perioden-FE keinen Unterschied mehr
    (jedes Video bleibt ohnehin eine eigene Zeile), ein zusaetzlicher "monat"-Lauf
    lohnt sich bei den hohen Zeilenzahlen (siehe unten) nicht. Seit 2026-09-08
    zusaetzlich (Entscheidung 2) ueber DAUER_TEILSTICHPROBEN gekreuzt (verarbeite_
    video_ebene()) - reduziert die Zeilenzahl in den Teilstichproben spuerbar UND
    verbessert die Laengen-Vergleichbarkeit von Kriegs-/Nichtkriegsvideos.

    BAUSTEIN 4 (ANTEIL_DESIGN_AKTIV, _fuehre_lauf_anteil()/verarbeite_anteil(),
    aggregiere_kanal_periode_anteil()): aggregiert wie Baustein 1 zu Kanal x
    Periode-Zellen, aber OHNE Aufspaltung nach ist_kriegsvideo - stattdessen wird je
    Zelle ueber ALLE Videos (Kriegs- UND sonstige) der Anteil an Kriegsvideos
    (anteil_kriegsvideos = n_kriegsvideos / n_videos_gesamt) berechnet und als
    (mit gruppe5 interagierte) erklaerende Variable statt der ist_kriegsvideo-Dummy
    verwendet: y ~ C(channel_id) + C(periode) + log_duration_mean +
    log_upload_dichte_mean + anteil_kriegsvideos:C(gruppe5). ANDERE Frage als
    Baustein 1 ("ist ein Kriegsvideo erfolgreicher als ein sonstiges Video
    DESSELBEN Kanals in DERSELBEN Periode?"): hier "korreliert ein HOEHERER
    Kriegsvideo-ANTEIL in einer Kanal-Periode mit mehr/weniger Erfolg IN DIESER
    PERIODE (ueber alle Videos der Periode gemittelt)?" - strukturell verwandt mit
    Frage 3's Panel-Design (log_views ~ populismus_gesamt + Kanal-FE + Perioden-FE,
    siehe frage3_populismus_erfolg_bericht.py). MIN_VIDEOS_PRO_ZELLE filtert wie bei
    Baustein 1 duenn besetzte Zellen (hier: zu wenige Videos insgesamt, nicht
    speziell zu wenige Kriegsvideos); der Gruppenfilter (_filtere_duenne_gruppen_
    anteil()) verlangt nur genuegend Kanaele je gruppe5, KEINE Mindestzahl an
    Kanaelen mit Kriegsvideo-Zellen (die gibt es in diesem Design nicht - jede
    Kanal-Periode hat einen anteil_kriegsvideos-Wert, auch wenn er 0 ist). Laeuft
    weiterhin fuer BEIDE Granularitaeten, nur Gesamtzeitraum + volle Stichprobe
    (Laenge) - KEIN Dauer-Kreuzprodukt wie Baustein 3 (nicht vom Nutzer gefordert).

Beide Bausteine wiederverwenden kriegspraemie_je_gruppe_test()/kriegspraemie_
gesamt_test() ueber neue Parameter treatment_var/kontroll_spalten (Default:
treatment_var="ist_kriegsvideo", kontroll_spalten=("log_duration_mean",
"log_upload_dichte_mean") - identisch zu Baustein 1/2, KEIN Verhaltensunterschied
dort) statt eigener Modellformeln, sowie die neue gemeinsame Ausgabe-/Druckfunktion
_teste_und_baue_zeilen(). Schreiben je eigene Ausgabedatei
(frage4_kriegspraemie_video_bericht_quartal.csv bzw. frage4_kriegspraemie_
anteil_bericht_{granularitaet}.csv), NICHT in dieselbe CSV wie Baustein 1/2 (andere
Beobachtungseinheit/Spaltenschema - Vermischung waere irrefuehrend).

VERGLEICHSGRUPPEN-DIMENSION (seit 2026-09-08, .claude/plans/frage4_kriegspraemie_
vergleichsgruppen_und_beobachtungseinheiten.md, Nutzervorgabe): die "sonstigen
Videos" (Nenner/Vergleich zu den Kriegsvideos in JEDEM der vier Bausteine) laufen
NEBENEINANDER (nicht ersetzend) in DREI Varianten (VERGLEICHSGRUPPEN, bericht_
utils.py::vergleichsgruppe_filter()): "alle_videos" (Status quo, unveraendert),
"nur_politische_videos" (verwirft ist_kriegsvideo == 0 UND KEINE bestaetigte
Politik-Klassifikation ueber topic_categories/video_registry.
politics_topic_lookup(), Entscheidung A: hohe Abdeckung, ~99,7% der Whitelist-
Videos, siehe lade_video_daten()) sowie, seit 2026-09-09 als zusaetzlicher
Robustheitscheck (Nutzervorgabe "auch meine LLM-Klassifikation aus dem
screening_state mit politics_final verwenden"), "nur_politische_videos_llm"
(verwirft ist_kriegsvideo == 0 UND politics_final != 1, siehe
screening_state_store.get_state() - manuelle/LLM-Klassifikation aus dem
longitudinalen Politik-Screening, deutlich geringere Abdeckung von nur ~12%
aller Videos - reine Zufallsstichprobe je Kanal x 3-Monats-Intervall statt
erschoepfender Klassifikation, siehe is_politics_topic()-Docstring, druckt
daher voraussichtlich deutlich mehr "zu wenig Variation"-Skips als die beiden
anderen Varianten). Kriegsvideos selbst bleiben in ALLEN DREI Varianten IMMER
ungefiltert. Wird auf Video-Ebene angewendet, NACH der Dauer-Teilstichprobe
(falls vorhanden) und VOR jeder Zellenaggregation - die alle_videos-Variante
ist dadurch bitwise identisch zu den bereits berichteten Baustein-1/2-Zahlen
(vergleichsgruppe_filter() gibt df bei modus="alle_videos" unveraendert
zurueck). Bei Baustein 4 bewirkt die Filterung eine Nenner-Restriktion der
Anteilsberechnung (anteil_kriegsvideos = n_kriegsvideos /
n_politische_videos_gesamt statt / n_videos_gesamt), OHNE dass
aggregiere_kanal_periode_anteil() selbst angepasst werden muss - analog zur
Marktanteil-Logik in frage4_kriegspraemie_marktanteil_plots.py. Alle vier
Bausteine bekommen dafuer die zusaetzlichen Spalten "vergleichsgruppe"/
"vergleichsgruppe_label" in ihrer jeweiligen Ausgabedatei.

KONTROLLE "ANTEIL POLITISCHER VIDEOS" NUR BEI VERGLEICHSGRUPPE "alle_videos" (seit
2026-09-09, Nutzervorgabe "Fuege eine Kontrolle ein, wie hoch der Anteil der
politischen Videos des Kanals in der jeweiligen Periode war"): NUR fuer Baustein 1/2
(aggregiere_zellen()) und NUR wenn vergleichsgruppe_id == "alle_videos" bekommt jedes
Modell zusaetzlich anteil_politischer_videos als Kontrollvariable - den Anteil der
Videos MIT topic_categories="Politics" (dieselbe hochabdeckende Klassifikation wie bei
"nur_politische_videos", NICHT politics_final - Entscheidung A gilt hier analog: eine
Kanal-Perioden-Kennzahl aus nur ~12% Abdeckung waere zu verrauscht) an ALLEN Videos des
Kanals in dieser Periode, unabhaengig vom ist_kriegsvideo-Split (aggregiere_zellen()
bildet ihn deshalb VOR der Aufspaltung nach ist_kriegsvideo - beide Zellen [Kriegsvideo
0/1] eines Kanal-Perioden-Paars bekommen denselben Wert). Begruendung: bei "alle_videos"
geht die Vergleichsgruppe ("sonstige Videos") unkontrolliert ueber das gesamte
thematische Spektrum des Kanals - ein Kanal, der in einer Periode ohnehin ueberwiegend
politisch berichtet, koennte dadurch eine hoehere/niedrigere Kriegspraemie zeigen, nur
weil "politisch berichten" selbst mit Erfolg korreliert ist, nicht weil Kriegsvideos
spezifisch heraussstechen. Bei den beiden "nur_politische_videos*"-Vergleichsgruppen
entfaellt diese Kontrolle bewusst: dort ist die Vergleichsgruppe per Filter bereits auf
(nahezu) durchgehend politische Videos beschraenkt, ein zusaetzlicher Anteils-Regressor
haette dort kaum verbleibende Variation und wuerde primaer Freiheitsgrade kosten. Wird
selbst NICHT separat im Bericht ausgegeben (reine Kontrollgroesse, analog log_duration_
mean/log_upload_dichte_mean).

Schreibt frage4_kriegspraemie_medientyp_bericht_{granularitaet}.csv (Baustein 1/2,
siehe oben) mit den zusaetzlichen Spalten "phase" ("gesamt" oder eine der PHASEN-
Kennungen), "stichprobe" ("voll" oder eine der DAUER_TEILSTICHPROBEN-Kennungen) und
"vergleichsgruppe" (siehe oben), druckt eine Kurzzusammenfassung je Phase. Direkt
im Ordner ausfuehren, nicht als -m-Modul (bare sibling imports von bericht_utils/
deskriptiv_aggregation/deskriptiv_plots/frage2_sensitivitaet_plots, wie die
anderen frageN_*.py-Berichte hier).

BEGLEITBERICHT (seit 2026-09-09, Nutzervorgabe "ich verstehe den Output ... nicht so
gut"): zusaetzlich zur CSV schreibt verarbeite_granularitaet() eine menschenlesbare
frage4_kriegspraemie_medientyp_bericht_{granularitaet}.md (PFAD_REPORT) mit denselben
Zahlen, aber je Modell (= je Kombination aus DIMENSION x Zeitfenster x Stichprobe x
Vergleichsgruppe) einem eigenen, ueberschriebenen Block: abhaengige Variable,
einbezogene Kontrollvariablen (inkl. Kanal-/Perioden-FE), Aggregationsebene,
Sample-Charakteristika (Zeitfenster/Videolaenge/Vergleichsgruppe) und Anzahl
Beobachtungen (_baue_modell_kopf()), gefolgt von den Ergebniszeilen. Reine
Formatierungsergaenzung, aendert KEINE der in der CSV berichteten Zahlen. NUR fuer
Baustein 1/2 - Baustein 3/4 (VIDEO_EBENE_AKTIV/ANTEIL_DESIGN_AKTIV) bleiben bei reiner
CSV-Ausgabe, da beide aktuell deaktiviert und nicht Gegenstand der Nutzervorgabe waren.

ERGEBNISSE ALS MARKDOWN-TABELLE (seit 2026-09-09, Nutzervorgabe "die Ergebnisse fuer
jede Gruppe innerhalb eines Modells sollen eine einzelne Zeile erhalten, damit es
uebersichtlicher ist"): urspruenglich wurden die Ergebniszeilen ([Gepoolt]/[Gruppe]/
[Heterogenitaet]) als Freitext ueber "\n" aneinandergereiht - ohne Leerzeile dazwischen
zieht Markdown das beim Rendern faelschlich zu EINEM Absatz zusammen, die einzelnen
Ergebnisse waren dadurch nicht als getrennte Zeilen erkennbar. _baue_ergebnis_tabelle()
baut stattdessen je Modell EINE Markdown-Tabelle (Spalten: Gruppe | Kriegspraemie | SE |
p | Signifikant), mit je einer Zeile fuer "Gepoolt (alle)", jede gruppe5-Kategorie und
(falls vorhanden) "Heterogenitaet (F-Test)" - Tabellenzeilen sind durch die "|"-Syntax
IMMER als eigene Zeile erkennbar, unabhaengig von Leerzeilen. Reine
Darstellungsaenderung des Begleitberichts, die Konsolen-Ausgabe (print()) UND die
CSV-Zahlen bleiben unveraendert.

EXECUTIVE SUMMARY (seit 2026-09-09, Nutzervorgabe "Executive summary ... aufgeteilt
nach den wesentlichen Kriterien [Vergleichsgruppe/Videolaenge-Stichprobe/Phasen vs.
Gesamtzeitraum] ... in wie vielen Spezifikationen der Koeffizient fuer einen
Medientyp signifikant ist"): verarbeite_granularitaet() schreibt VOR den 108
Einzelmodell-Bloecken eine kompakte Sektion (_baue_executive_summary()) mit einer
Gesamtuebersichtszeile plus drei Breakdown-Tabellen (nach Vergleichsgruppe, nach
Stichprobe/Videolaenge, nach Zeitfenster inkl. je Phase einzeln) - je Zeile eine
Auspraegung, je Spalte "Gepoolt (alle)"/je gruppe5-Kategorie/"Heterogenitaet
(F-Test)", Zelle "signifikant/gesamt" (p<0,05) ueber alle Spezifikationen, die auf
den jeweils anderen Kriterien (inkl. beider DIMENSIONEN) variieren. Reine
Umaggregation der bereits in PFAD_AUSGABE/den Modell-Bloecken berichteten p-Werte,
keine neuen Zahlen.
"""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from youtube_code.config import OUTPUTS
from youtube_code.store.video_registry import politics_topic_lookup
from youtube_code.store.screening_state_store import get_state
from bericht_utils import dauer_teilstichprobe, berechne_upload_dichte, vergleichsgruppe_filter
from deskriptiv_aggregation import lade_medientyp, lade_ideologie
from deskriptiv_plots import GRUPPE5_REIHENFOLGE
from frage2_sensitivitaet_plots import winsorisiere

# =========================================================
# CONFIG
# =========================================================

RESULTS_PATH = OUTPUTS / "segment_analysis"
PFAD_EINGABE = RESULTS_PATH / "channel_video_erfolg.csv"
PFAD_WHITELIST = RESULTS_PATH / "frage1_kanal_whitelist.csv"
PFAD_AUSGABE = RESULTS_PATH / "frage4_kriegspraemie_medientyp_bericht_{granularitaet}.csv"
# Menschenlesbarer Begleitbericht zu PFAD_AUSGABE (seit 2026-09-09, Nutzervorgabe "ich
# verstehe den Output ... nicht so gut"): dieselben Zahlen wie in der CSV, aber je
# Modell (= je Kombination aus Dimension x Zeitfenster x Stichprobe x Vergleichsgruppe)
# in einem eigenen, mit voller Spezifikation ueberschriebenen Textblock statt als
# CSV-Zeilen ohne sofort sichtbaren Kontext - siehe baue_modell_kopf()/verarbeite_
# granularitaet(). NUR fuer Baustein 1/2 (das eigentliche "medientyp_bericht"); Baustein
# 3/4 (VIDEO_EBENE_AKTIV/ANTEIL_DESIGN_AKTIV) bleiben bei reiner CSV-Ausgabe, da beide
# Bausteine aktuell deaktiviert sind und nicht Gegenstand der Nutzervorgabe waren.
PFAD_REPORT = RESULTS_PATH / "frage4_kriegspraemie_medientyp_bericht_{granularitaet}.md"

# Verschiedene View-Metriken je Zelle (siehe aggregiere_zellen()) als Robustheitscheck -
# "log_views" (log1p-Mittelwert, das im restlichen Projekt uebliche Standardmass),
# "view_count_mean" (roh), "view_count_median", zwei winsorisierte Mittelwerte.
DIMENSIONEN = ["log_views", "view_count_median",] # "view_count_winsor_5_95"

# Menschenlesbare Beschreibung je moeglicher DIMENSION (fuer die "Abhaengige Variable"-
# Zeile im Bericht, siehe PFAD_REPORT) - deckt auch die aktuell auskommentierten
# DIMENSIONEN mit ab, damit ein spaeteres Wiedereinschalten nicht zusaetzlich hier
# nachgezogen werden muss.
DIMENSIONEN_LABEL = {
    "log_views": "log(1 + view_count), Zellmittel (Standardmass im restlichen Projekt)",
    "view_count_mean": "view_count, rohes Zellmittel",
    "view_count_median": "view_count, Zellmedian",
    "view_count_winsor_5_95": "view_count, winsorisiertes Zellmittel (5%/95%-Grenzen)",
    "view_count_winsor_1_99": "view_count, winsorisiertes Zellmittel (1%/99%-Grenzen)",
}

# Menschenlesbare Beschreibung je moeglicher Kontrollspalte (fuer die "Kontrollvariablen"-
# Zeile im Bericht) - Kanal-/Perioden-FE sind in Baustein 1/2 IMMER Teil des Modells und
# werden deshalb in baue_modell_kopf() unabhaengig von kontroll_spalten vorangestellt.
KONTROLLVARIABLEN_LABEL = {
    "log_duration_mean": "log_duration_mean (Zellmittel log(Videolaenge in Sekunden))",
    "log_upload_dichte_mean": "log_upload_dichte_mean (Zellmittel log1p(Anzahl anderer "
                               "Videos desselben Kanals in +/-48h um das jeweilige Video))",
    "anteil_politischer_videos": "anteil_politischer_videos (Anteil politischer Videos "
                                  "[topic_categories='Politics'] des Kanals in der jeweiligen "
                                  "Periode, ueber ALLE Videos der Kanal-Periode-Zelle unabhaengig "
                                  "von ist_kriegsvideo - nur bei Vergleichsgruppe 'alle_videos')",
}

WINSOR_GRENZEN = {"winsor_5_95": 0.05, "winsor_1_99": 0.01}

# "quartal" primaer (siehe Moduldocstring), "monat" als Zusatzcheck - beide werden
# erzeugt, identische Fenster wie frage4_kriegsvideos_erfolg_bericht.py.
GRANULARITAETEN = {
    "quartal": {"spalte": "rel_quartal", "periode_min": -4, "periode_max": 16},
    "monat":   {"spalte": "rel_monat",   "periode_min": -12, "periode_max": 48},
}

MIN_VIDEOS_PRO_ZELLE = 3     # wie frage4_kriegsvideos_erfolg_bericht.py, je Kanal x Periode x Kriegsvideo-Zelle
MIN_KANAELE_JE_GRUPPE = 5    # wie frage1/frage2 - Mindestanzahl Kanaele MIT >= 1 Kriegsvideo-Zelle je gruppe5

# --- Phasenaufteilung (Nutzervorgabe, siehe Moduldocstring) --------------------
# True = zusaetzlich zur Gesamtzeitraum-Analyse ("gesamt") je Phase ein eigener,
# in sich abgeschlossener Lauf (eigene Kanal-FE + Perioden-FE nur innerhalb der
# Phase). False = nur die urspruengliche Gesamtzeitraum-Analyse.
PHASEN_AKTIV = True

# monat_min/monat_max IMMER in rel_monat (siehe _phase_fenster()), unabhaengig von
# GRANULARITAET. monat_max = None -> kein oberes Ende (laeuft bis zum Datenrand).
# "beschreibung" ist die inhaltliche Begruendung/Erwartung je Phase (Nutzervorgabe),
# rein dokumentarisch - fliesst nicht in die Berechnung ein.
PHASEN = {
    "P1_schock_konsens": {
        "monat_min": 0, "monat_max": 6,
        "label": "P1: Schock und Konsens (Feb-Aug 2022)",
        "beschreibung": "Zeitenwende-Rede, Bucha, erste Sanktionspakete, "
                         "Waffenlieferungsdebatte. Hohe Elitenkohaesion, breite "
                         "mediale Aufmerksamkeit - Erwartung: groesstes "
                         "Topic-Premium bei allen Medientypen.",
    },
    "P2_energiekrise_bruch": {
        "monat_min": 7, "monat_max": 18,
        "label": "P2: Energiekrise und Bruch des Konsenses (Sep 2022-Aug 2023)",
        "beschreibung": "Nord-Stream-Sabotage (M7), Gasumlage, Inflationswinter, "
                         "Leopard-Debatte (M11), 'Aufstand fuer Frieden' (M12) - "
                         "der Krieg wird innenpolitisch uebersetzt und damit "
                         "erstmals kontrovers.",
    },
    "P3_aufmerksamkeitsverdraengung": {
        "monat_min": 19, "monat_max": 26,
        "label": "P3: Aufmerksamkeitsverdraengung (Okt 2023-Mai 2024)",
        "beschreibung": "Beginn des Gaza-Kriegs (M19) zieht Aufmerksamkeit ab, "
                         "parallel Correctiv/Demos gegen rechts und BSW-Gruendung "
                         "(M23) - Erwartung: wenn die Praemien irgendwo "
                         "verschwinden, dann hier.",
    },
    "P4_wahlkampfphase": {
        "monat_min": 27, "monat_max": 36,
        "label": "P4: Wahlkampfphase (Jun 2024-Feb 2025)",
        "beschreibung": "Europawahl (M27), Landtagswahlen Sachsen/Thueringen/"
                         "Brandenburg (M30, 'Friedens'-Wahlkampf von AfD/BSW), "
                         "US-Wahl und Ampel-Bruch am selben Tag (M32), "
                         "Bundestagswahl (M36).",
    },
    "P5_nachwahlphase": {
        "monat_min": 37, "monat_max": None,
        "label": "P5: Nachwahlphase (ab Maer 2025)",
        "beschreibung": "Sondervermoegen/Grundgesetzaenderung, Regierung Merz, "
                         "Trump-Verhandlungslinie - der Krieg wird vom "
                         "Oppositions- zum Regierungsthema.",
    },
}

# --- Laengenbeschraenkte Sensitivitaets-Teilstichproben (Nutzervorgabe, siehe
# Moduldocstring) -------------------------------------------------------------
# True = zusaetzlich zur vollen Stichprobe ("voll") je Zeitfenster (Gesamtzeitraum
# + jede PHASE, falls PHASEN_AKTIV) ein eigener Lauf je DAUER_TEILSTICHPROBE.
# False = nur die volle Stichprobe (urspruengliches Verhalten).
DAUER_TEILSTICHPROBEN_AKTIV = True

# Feste, frei anpassbare Minuten-Intervalle (minuten_max=None -> keine Obergrenze).
# Beliebig erweiterbar/veraenderbar - einfach weitere Eintraege ergaenzen. Default
# deckt zwei Nutzerinteressen ab: kurze Videos bis 10 Minuten (Vergleichbarkeit mit
# News-Clips) und ein mittleres Band 3-30 Minuten (deckt den Grossteil beider
# Verteilungen ab, siehe scripts/adhoc/videolaenge_diagnose.py).
DAUER_TEILSTICHPROBEN = {
    "kurz_bis_10min": {"minuten_min": 0, "minuten_max": 10,
                        "label": "Kurzvideos (0-10 Minuten)"},
    "mittel_3_30min": {"minuten_min": 3, "minuten_max": 30,
                        "label": "Mittellange Videos (3-30 Minuten)"},
}

# --- Zusatzspezifikationen: alternative Beobachtungseinheiten (Nutzervorgabe, siehe
# Moduldocstring "ZUSATZSPEZIFIKATIONEN") -------------------------------------
# True = zusaetzlich zu Baustein 1/2 (Zellen-Design) ein eigener Lauf mit der jeweils
# anderen Beobachtungseinheit. Baustein 3 (Video-Ebene) laeuft NUR fuer
# GRANULARITAET="quartal" (siehe Moduldocstring "ZUSATZSPEZIFIKATIONEN" Entscheidung 1),
# gekreuzt mit DAUER_TEILSTICHPROBEN UND VERGLEICHSGRUPPEN; Baustein 4 (Anteil-Design)
# laeuft weiterhin fuer BEIDE Granularitaeten, nur Gesamtzeitraum + volle Stichprobe,
# aber ebenfalls gekreuzt mit VERGLEICHSGRUPPEN.
VIDEO_EBENE_AKTIV = True
ANTEIL_DESIGN_AKTIV = True

# --- Vergleichsgruppen-Dimension (Nutzervorgabe, seit 2026-09-08, siehe .claude/plans/
# frage4_kriegspraemie_vergleichsgruppen_und_beobachtungseinheiten.md) ---------
# Die "sonstigen Videos" (Nenner/Vergleich zu den Kriegsvideos, treatment_spalte == 0 in
# vergleichsgruppe_filter()) koennen wahlweise ALLE sonstigen Videos sein (Status quo,
# bitwise identisch zu den bereits berichteten Zahlen) oder NUR andere POLITISCHE
# sonstige Videos (topic_categories enthaelt "Politics", siehe lade_video_daten()) - fuer
# Baustein 1-4 laufen BEIDE Varianten parallel (Nutzervorgabe: "Das soll bei Baustein 1
# und 2 aber auch geschehen"), Kriegsvideos selbst bleiben in BEIDEN Varianten immer
# ungefiltert. Politik-Quelle bewusst NUR topic_categories, NICHT zusaetzlich
# politics_final (Nutzerentscheidung A im obigen Plan: hohe Abdeckung vs. duenne
# Zufallsstichprobe, siehe video_registry.is_politics_topic()-Docstring).
VERGLEICHSGRUPPEN = {
    "alle_videos": {"label": "alle sonstigen Videos (Status quo)"},
    "nur_politische_videos": {"label": "nur andere politische Videos "
                                        "(topic_categories='Politics')"},
    "nur_politische_videos_llm": {"label": "nur andere politische Videos "
                                            "(politics_final == 1, LLM/manuelles Screening)"},
}

# Welche Spalte vergleichsgruppe_filter() je VERGLEICHSGRUPPEN-Key als politik_spalte
# verwendet (siehe bericht_utils.py::vergleichsgruppe_filter()-Docstring fuer die
# beiden Politik-Quellen) - "alle_videos" braucht keine, da vergleichsgruppe_filter()
# dort sofort unveraendert zurueckgibt.
POLITIK_SPALTE_JE_VERGLEICHSGRUPPE = {
    "nur_politische_videos": "ist_politisches_video",
    "nur_politische_videos_llm": "ist_politisches_video_llm",
}


# =========================================================
# DATEN LADEN
# =========================================================

def baue_gruppe5_lokal(df):
    """Lokale Nachbildung von deskriptiv_plots.py::baue_gruppe5()/
    frage2_sensitivitaet_plots.py::baue_gruppe5_lokal() - OERR und Traditionelles
    Medium bleiben als Ganzes, Alternatives Medium wird nach Ideologie in
    links/mitte/rechts aufgespalten (GRUPPE5_REIHENFOLGE importiert, damit alle drei
    Skripte garantiert dieselben Gruppen verwenden). Politiker/Partei sowie
    Alternative-Medium-Kanaele ohne Ideologie-Einordnung fallen raus."""
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


def lade_video_daten():
    df = pd.read_csv(PFAD_EINGABE)
    df["channel_id"] = df["channel_id"].astype(str)
    n_vor = df["channel_id"].nunique()

    whitelist = pd.read_csv(PFAD_WHITELIST)
    whitelist_ids = set(whitelist["channel_id"].astype(str))
    df = df[df["channel_id"].isin(whitelist_ids)]
    print(f"[Whitelist] {n_vor} -> {df['channel_id'].nunique()} Kanaele nach Filter auf "
          f"{PFAD_WHITELIST} (dieselbe Whitelist wie Forschungsfrage 1).")

    med = lade_medientyp()
    ideo = lade_ideologie()
    df = df.merge(med, on="channel_id", how="left").merge(ideo, on="channel_id", how="left")
    df = baue_gruppe5_lokal(df)

    # Upload-Dichte (siehe Moduldocstring "UPLOAD-DICHTE") EINMAL berechnen und mergen,
    # auf der VOLLEN, noch ungefilterten Video-Menge (df an dieser Stelle ist bereits
    # whitelist-/gruppe5-gefiltert, aber noch VOR Phasen-/Dauer-Teilstichproben-
    # Filterung, die erst in verarbeite_granularitaet() greift) - seit 2026-09-09
    # granularitaetsunabhaengig (Video-eigene, fenster-basierte Kennzahl statt
    # periodenbasiert), daher EINE Spalte statt zwei (siehe Moduldocstring).
    dichte = berechne_upload_dichte(df)
    df = df.merge(dichte[["channel_id", "video_id", "log_upload_dichte"]],
                   on=["channel_id", "video_id"], how="left")

    # Politik-Klassifikation fuer die Vergleichsgruppen-Dimension (siehe VERGLEICHSGRUPPEN/
    # vergleichsgruppe_filter()) - topic_categories (Entscheidung A, siehe Moduldocstring,
    # hohe Abdeckung) UND, seit 2026-09-09 als zusaetzlicher Robustheitscheck (Nutzervorgabe:
    # "auch meine LLM-Klassifikation aus dem screening_state mit politics_final verwenden"),
    # politics_final aus screening_state_store (manuelle/LLM-Klassifikation, deutlich
    # geringere Abdeckung - siehe Print unten). NaN bei fehlendem video_details- bzw.
    # screening_state-Eintrag.
    topic_map = politics_topic_lookup(df["video_id"].tolist())
    df["ist_politisches_video"] = df["video_id"].map(topic_map)
    n_mit_topic = df["ist_politisches_video"].notna().sum()
    n_politisch = int((df["ist_politisches_video"] == True).sum())  # noqa: E712
    print(f"[Politik-Klassifikation] {n_mit_topic} von {len(df)} Videos ({n_mit_topic / len(df):.1%}) "
          f"haben einen video_details-Eintrag, davon {n_politisch} ({n_politisch / len(df):.1%}) "
          f"mit topic_categories='Politics'.")

    state = get_state()[["video_id", "politics_final"]]
    state["video_id"] = state["video_id"].astype(str)
    df = df.merge(state, on="video_id", how="left")
    df["ist_politisches_video_llm"] = df["politics_final"] == 1
    n_mit_state = df["politics_final"].notna().sum()
    n_llm_politisch = int((df["politics_final"] == 1).sum())
    print(f"[Politik-Klassifikation LLM] {n_mit_state} von {len(df)} Videos ({n_mit_state / len(df):.1%}) "
          f"haben einen screening_state-Eintrag, davon {n_llm_politisch} "
          f"({n_llm_politisch / len(df):.1%}) mit politics_final == 1 (Robustheitscheck mit deutlich "
          f"geringerer Abdeckung als topic_categories, siehe Moduldocstring).")

    n_kriegsvideos = int(df["ist_kriegsvideo"].sum())
    print(f"[Eingabe] {len(df)} Video-Beobachtungen ({n_kriegsvideos} Kriegsvideos), "
          f"{df['channel_id'].nunique()} Kanaele mit gueltiger gruppe5-Zuordnung aus {PFAD_EINGABE}")
    return df


def _fenster(df, spalte_periode, periode_min, periode_max):
    return df[(df[spalte_periode] >= periode_min) & (df[spalte_periode] <= periode_max)]


def _phase_fenster(df, monat_min, monat_max):
    """Filtert IMMER auf rel_monat (siehe PHASEN/Moduldocstring), unabhaengig von
    GRANULARITAET - dadurch entsprechen die Phasengrenzen exakt den vom Nutzer
    vorgegebenen Monaten, auch wenn die C(periode)-FE anschliessend auf rel_quartal
    gebildet werden (keine Rundung auf Quartalsgrenzen an den Phasenraendern)."""
    df_f = df[df["rel_monat"] >= monat_min]
    if monat_max is not None:
        df_f = df_f[df_f["rel_monat"] <= monat_max]
    return df_f


# =========================================================
# ZELLENAGGREGATION MIT MEHREREN METRIKEN
# =========================================================

def _winsorisierter_mittelwert(werte, grenze):
    wins = winsorisiere(werte, grenze)
    return float(np.mean(wins)) if len(wins) else np.nan


def aggregiere_zellen(df, spalte_periode):
    """Video-Ebene -> Kanal x Periode x Kriegsvideo-Flag-Zellen, analog
    frage4_kriegsvideos_erfolg_bericht.py::aggregiere_kanal_periode_kriegsvideo(),
    hier aber mit mehreren View-Metriken je Zelle statt nur einem Mittelwert (siehe
    Moduldocstring/DIMENSIONEN). gruppe5 ist innerhalb eines Kanals konstant und wird
    daher einfach mitgruppiert (kein Informationsverlust). log_upload_dichte ist seit
    2026-09-09 granularitaetsunabhaengig (siehe Moduldocstring "UPLOAD-DICHTE"), daher
    fest referenziert statt ueber einen Parameter ausgewaehlt.

    anteil_politischer_videos (seit 2026-09-09, siehe Moduldocstring "KONTROLLE 'ANTEIL
    POLITISCHER VIDEOS'") wird VOR der Aufspaltung nach ist_kriegsvideo je (channel_id,
    spalte_periode) ueber ALLE Videos berechnet (Anteil mit ist_politisches_video ==
    True, NaN-Videos ohne topic_categories-Eintrag werden dabei ausgeklammert statt als
    "nicht politisch" gezaehlt) - beide Kriegsvideo-Zellen (0/1) desselben Kanal-
    Perioden-Paars bekommen dadurch bewusst DENSELBEN Wert (keine kriegsvideo-bedingte
    Verzerrung des Anteils)."""
    politik_float = df["ist_politisches_video"].astype(float)
    anteil_politisch_je_periode = (
        df.assign(_politik_float=politik_float)
        .groupby(["channel_id", spalte_periode])["_politik_float"].mean()
    )

    zeilen = []
    for (channel_id, gruppe5, periode, ist_kv), g in df.groupby(
            ["channel_id", "gruppe5", spalte_periode, "ist_kriegsvideo"]):
        views = g["view_count"].to_numpy(dtype=float)
        zeilen.append({
            "channel_id": channel_id,
            "gruppe5": gruppe5,
            spalte_periode: periode,
            "ist_kriegsvideo": ist_kv,
            "view_count_mean": views.mean(),
            "view_count_median": float(np.median(views)),
            "view_count_winsor_5_95": _winsorisierter_mittelwert(views, WINSOR_GRENZEN["winsor_5_95"]),
            "view_count_winsor_1_99": _winsorisierter_mittelwert(views, WINSOR_GRENZEN["winsor_1_99"]),
            "log_views": g["log_views"].mean(),
            "log_duration_mean": g["log_duration_seconds"].mean(),
            "log_upload_dichte_mean": g["log_upload_dichte"].mean(),
            "anteil_politischer_videos": anteil_politisch_je_periode.get((channel_id, periode), np.nan),
            "n_videos": len(g),
        })
    return pd.DataFrame(zeilen)


def aggregiere_kanal_periode_anteil(df, spalte_periode):
    """Video-Ebene -> Kanal x Periode-Zellen OHNE Aufspaltung nach ist_kriegsvideo
    (anders als aggregiere_zellen()) - Grundlage fuer BAUSTEIN 4 (ANTEIL-DESIGN, siehe
    Moduldocstring "ZUSATZSPEZIFIKATIONEN"): pro Kanal-Periode wird ueber ALLE Videos
    (Kriegs- UND sonstige) der Anteil an Kriegsvideos (anteil_kriegsvideos =
    n_kriegsvideos / n_videos_gesamt) berechnet sowie dieselben View-/Kontroll-Metriken
    wie aggregiere_zellen()."""
    zeilen = []
    for (channel_id, gruppe5, periode), g in df.groupby(["channel_id", "gruppe5", spalte_periode]):
        views = g["view_count"].to_numpy(dtype=float)
        zeilen.append({
            "channel_id": channel_id,
            "gruppe5": gruppe5,
            spalte_periode: periode,
            "n_videos": len(g),
            "n_kriegsvideos": int(g["ist_kriegsvideo"].sum()),
            "anteil_kriegsvideos": float(g["ist_kriegsvideo"].mean()),
            "view_count_mean": views.mean(),
            "view_count_median": float(np.median(views)),
            "view_count_winsor_5_95": _winsorisierter_mittelwert(views, WINSOR_GRENZEN["winsor_5_95"]),
            "view_count_winsor_1_99": _winsorisierter_mittelwert(views, WINSOR_GRENZEN["winsor_1_99"]),
            "log_views": g["log_views"].mean(),
            "log_duration_mean": g["log_duration_seconds"].mean(),
            "log_upload_dichte_mean": g["log_upload_dichte"].mean(),
        })
    return pd.DataFrame(zeilen)


def _filtere_duenne_zellen(df, bezeichnung="Kanal-Perioden-Kriegsvideo-Zellen"):
    zu_duenn = df["n_videos"] < MIN_VIDEOS_PRO_ZELLE
    print(f"  [Zellfilter] {int(zu_duenn.sum())} von {len(df)} {bezeichnung} "
          f"unter MIN_VIDEOS_PRO_ZELLE={MIN_VIDEOS_PRO_ZELLE} -> verworfen.")
    return df[~zu_duenn]


def _filtere_duenne_gruppen(df):
    """Behaelt nur gruppe5-Kategorien mit >= MIN_KANAELE_JE_GRUPPE Kanaelen, die
    MINDESTENS EINE Kriegsvideo-Zelle (ist_kriegsvideo == 1) in der gefilterten Zellen-
    Tabelle haben - ohne das waere fuer diese Gruppe gar keine Kriegspraemie
    identifizierbar. Analog interaktions_test() in bericht_utils.py. Funktioniert
    unveraendert auch auf Video-Ebene (Baustein 3) - dort zaehlt "Kriegsvideo-Zelle"
    einfach als "Kriegsvideo", jede Zeile ist bereits ein einzelnes Video."""
    kanaele_je_gruppe = (df.loc[df["ist_kriegsvideo"] == 1]
                         .groupby("gruppe5")["channel_id"].nunique())
    gueltige_gruppen = [g for g in GRUPPE5_REIHENFOLGE
                        if kanaele_je_gruppe.get(g, 0) >= MIN_KANAELE_JE_GRUPPE]
    ausgeschlossen = [g for g in GRUPPE5_REIHENFOLGE if g not in gueltige_gruppen]
    if ausgeschlossen:
        print(f"  [Gruppenfilter] Ausgeschlossen (< {MIN_KANAELE_JE_GRUPPE} Kanaele mit "
              f">= 1 Kriegsvideo-Zelle): {ausgeschlossen}")
    return df[df["gruppe5"].isin(gueltige_gruppen)], gueltige_gruppen


def _filtere_duenne_gruppen_anteil(df):
    """Analog _filtere_duenne_gruppen(), aber fuer das ANTEIL-DESIGN (Baustein 4, siehe
    Moduldocstring): dort gibt es keine ist_kriegsvideo-Aufspaltung mehr (jede
    Kanal-Periode-Zelle hat einen anteil_kriegsvideos-Wert, auch wenn er 0 ist) - die
    Bedingung "mindestens eine Kriegsvideo-Zelle" entfaellt daher, es zaehlt nur die
    Mindestzahl an Kanaelen je gruppe5."""
    kanaele_je_gruppe = df.groupby("gruppe5")["channel_id"].nunique()
    gueltige_gruppen = [g for g in GRUPPE5_REIHENFOLGE
                        if kanaele_je_gruppe.get(g, 0) >= MIN_KANAELE_JE_GRUPPE]
    ausgeschlossen = [g for g in GRUPPE5_REIHENFOLGE if g not in gueltige_gruppen]
    if ausgeschlossen:
        print(f"  [Gruppenfilter][Anteil-Design] Ausgeschlossen (< {MIN_KANAELE_JE_GRUPPE} "
              f"Kanaele): {ausgeschlossen}")
    return df[df["gruppe5"].isin(gueltige_gruppen)], gueltige_gruppen


# =========================================================
# BAUSTEIN 1: Kriegspraemie je Gruppe (Kanal-FE + Perioden-FE + Interaktion, vollrangig)
# =========================================================

def kriegspraemie_je_gruppe_test(df, dimension, spalte_periode, gueltige_gruppen,
                                  treatment_var="ist_kriegsvideo",
                                  kontroll_spalten=("log_duration_mean", "log_upload_dichte_mean")):
    """y ~ C(channel_id) + C(periode) + <kontroll_spalten> + <treatment_var>:C(gruppe5),
    SE geclustert auf Kanalebene. treatment_var/kontroll_spalten sind seit 2026-09-08
    parametrisiert (Baustein 3/4, siehe Moduldocstring "ZUSATZSPEZIFIKATIONEN") - mit den
    Defaults hier identisch zum urspruenglichen Baustein 1 (ist_kriegsvideo, Zellmittel-
    Kontrollen). Siehe Moduldocstring fuer die Vollrang-Kodierung von C(gruppe5)
    innerhalb der Interaktion (kein Referenzgruppen-Vergleich noetig) und den
    zusaetzlichen Heterogenitaets-F-Test (paarweise Gleichheit aller
    Interaktionskoeffizienten)."""
    daten = df.dropna(subset=[dimension, treatment_var, *kontroll_spalten]).copy()
    daten["channel_id"] = daten["channel_id"].astype(str)
    daten["y"] = daten[dimension]
    daten["gruppe5"] = pd.Categorical(daten["gruppe5"], categories=gueltige_gruppen)

    # Perioden numerisch sortieren, damit patsy sie nicht alphabetisch (falsch bei
    # negativen Zahlen) ordnet - dieselbe Kategorienbildung wie fe_signifikanz_test.py.
    periode_reihenfolge = sorted(daten[spalte_periode].unique())
    daten["periode"] = pd.Categorical(daten[spalte_periode], categories=periode_reihenfolge, ordered=True)

    n_kanaele = daten["channel_id"].nunique()
    if daten[treatment_var].nunique() < 2 or n_kanaele < 2 or daten["gruppe5"].nunique() < 1:
        print(f"  [Skip] zu wenig Variation (Kanaele={n_kanaele}) fuer kriegspraemie_je_gruppe_test.")
        return None

    # kontroll_spalten (siehe Moduldocstring "VIDEOLAENGE"/"UPLOAD-DICHTE") werden selbst
    # nicht separat ausgegeben.
    kontroll_terme = " + ".join(kontroll_spalten)
    modell = smf.ols(f"y ~ C(channel_id) + C(periode) + {kontroll_terme} "
                      f"+ {treatment_var}:C(gruppe5)",
                      data=daten).fit(
        cov_type="cluster", cov_kwds={"groups": daten["channel_id"]}
    )

    interaktions_terme = [p for p in modell.params.index if p.startswith(f"{treatment_var}:C(gruppe5)")]
    if not interaktions_terme:
        print("  [Skip] keine Interaktionsterme im Modell (zu wenig Variation innerhalb Kanaelen).")
        return None

    je_gruppe = pd.DataFrame([{
        "gruppe5": term.split("[")[1].rstrip("]"),
        "koeffizient_kriegspraemie": modell.params[term],
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
# BAUSTEIN 2: Gepoolte Kriegspraemie (ohne Gruppenaufspaltung, Effektgroessen-Baseline)
# =========================================================

def kriegspraemie_gesamt_test(df, dimension, spalte_periode,
                               treatment_var="ist_kriegsvideo",
                               kontroll_spalten=("log_duration_mean", "log_upload_dichte_mean")):
    """y ~ C(channel_id) + C(periode) + <kontroll_spalten> + <treatment_var> - EIN
    gepoolter Koeffizient ueber alle Gruppen, als Effektgroessen-Vergleichswert zu
    kriegspraemie_je_gruppe_test(). treatment_var/kontroll_spalten seit 2026-09-08
    parametrisiert, siehe dortigen Docstring."""
    daten = df.dropna(subset=[dimension, treatment_var, *kontroll_spalten]).copy()
    daten["channel_id"] = daten["channel_id"].astype(str)
    daten["y"] = daten[dimension]
    periode_reihenfolge = sorted(daten[spalte_periode].unique())
    daten["periode"] = pd.Categorical(daten[spalte_periode], categories=periode_reihenfolge, ordered=True)

    n_kanaele = daten["channel_id"].nunique()
    if daten[treatment_var].nunique() < 2 or n_kanaele < 2:
        print(f"  [Skip] zu wenig Variation (Kanaele={n_kanaele}) fuer kriegspraemie_gesamt_test.")
        return None

    # kontroll_spalten als Kontrollvariablen, siehe kriegspraemie_je_gruppe_test().
    kontroll_terme = " + ".join(kontroll_spalten)
    modell = smf.ols(f"y ~ C(channel_id) + C(periode) + {kontroll_terme} "
                      f"+ {treatment_var}", data=daten).fit(
        cov_type="cluster", cov_kwds={"groups": daten["channel_id"]}
    )

    return {
        "koeffizient_kriegspraemie": modell.params[treatment_var],
        "se": modell.bse[treatment_var],
        "p": modell.pvalues[treatment_var],
        "n_beobachtungen": len(daten),
        "n_kanaele": n_kanaele,
    }


# =========================================================
# GEMEINSAMER BAUSTEIN-KERN (von Baustein 1/2 UND 3/4 genutzt)
# =========================================================

def _teste_und_baue_zeilen(df, dimension, spalte_periode, gueltige_gruppen,
                            treatment_var="ist_kriegsvideo",
                            kontroll_spalten=("log_duration_mean", "log_upload_dichte_mean")):
    """Ruft kriegspraemie_gesamt_test() und kriegspraemie_je_gruppe_test() fuer EINE
    Dimension auf, druckt die Ergebnisse und baut die Ergebniszeilen im selben Format
    wie _fuehre_lauf_aus() - seit 2026-09-08 von den neuen Bausteinen 3 (Video-Ebene)
    und 4 (Anteil-Design) genutzt (siehe Moduldocstring "ZUSATZSPEZIFIKATIONEN"), damit
    Formel-/Ausgabelogik nur an einer Stelle gepflegt wird. _fuehre_lauf_aus() (Baustein
    1/2) bleibt bewusst UNVERAENDERT bei seiner eigenen, inline duplizierten Fassung
    dieser Logik, um das Risiko einer versehentlichen Verhaltensaenderung an den
    bereits berichteten Baustein-1/2-Zahlen auszuschliessen."""
    zeilen = []
    gesamt = kriegspraemie_gesamt_test(df, dimension, spalte_periode, treatment_var, kontroll_spalten)
    if gesamt:
        sig = "signifikant" if gesamt["p"] < 0.05 else "nicht signifikant"
        print(f"  [Gepoolt] Koeffizient ({treatment_var}) = {gesamt['koeffizient_kriegspraemie']:+.4f} "
              f"(p={gesamt['p']:.4f}) -> {sig}, n_kanaele={gesamt['n_kanaele']}")
        zeilen.append({"dimension": dimension, "ebene": "gepoolt", "gruppe5": "alle", **gesamt})

    je_gruppe = kriegspraemie_je_gruppe_test(df, dimension, spalte_periode, gueltige_gruppen,
                                              treatment_var, kontroll_spalten)
    if je_gruppe:
        for _, zeile in je_gruppe["je_gruppe"].iterrows():
            sig = "signifikant" if zeile["p"] < 0.05 else "nicht signifikant"
            print(f"  [{zeile['gruppe5']}] Koeffizient ({treatment_var}) = "
                  f"{zeile['koeffizient_kriegspraemie']:+.4f} (p={zeile['p']:.4f}) -> {sig}")
            zeilen.append({
                "dimension": dimension, "ebene": "je_gruppe", "gruppe5": zeile["gruppe5"],
                "koeffizient_kriegspraemie": zeile["koeffizient_kriegspraemie"],
                "se": zeile["se"], "p": zeile["p"],
                "n_beobachtungen": je_gruppe["n_beobachtungen"], "n_kanaele": je_gruppe["n_kanaele"],
            })
        if je_gruppe["heterogenitaet"]:
            h = je_gruppe["heterogenitaet"]
            sig = "signifikant" if h["p"] < 0.05 else "nicht signifikant"
            print(f"  [Heterogenitaet] F({h['df_num']}, {h['df_denom']}) = {h['f_stat']:.3f}, "
                  f"p = {h['p']:.4f} -> {sig} unterschiedliche Koeffizienten zwischen den Gruppen")
            zeilen.append({
                "dimension": dimension, "ebene": "heterogenitaet_ftest", "gruppe5": "alle",
                "f_stat": h["f_stat"], "df_num": h["df_num"], "df_denom": h["df_denom"], "p": h["p"],
                "n_beobachtungen": je_gruppe["n_beobachtungen"], "n_kanaele": je_gruppe["n_kanaele"],
            })
    return zeilen


# =========================================================
# BAUSTEIN 3: Kriegspraemie auf VIDEO-Ebene (keine Zellenaggregation)
# =========================================================

def _fuehre_lauf_video_ebene(df_fenster, granularitaet, spalte_periode):
    """Siehe Moduldocstring "ZUSATZSPEZIFIKATIONEN". df_fenster ist bereits auf das
    Periodenfenster der Granularitaet UND (seit 2026-09-08, siehe verarbeite_video_ebene())
    auf Stichprobe/Vergleichsgruppe gefiltert, aber NOCH NICHT auf Video-Ebene aggregiert -
    hier findet ueberhaupt keine Aggregation statt, jedes Video bleibt eine eigene
    Beobachtung. Nur DIMENSION="log_views"."""
    df_video, gueltige_gruppen = _filtere_duenne_gruppen(df_fenster)
    print(f"[Video-Ebene][{granularitaet}] {len(df_fenster)} -> {len(df_video)} Video-"
          f"Beobachtungen nach Gruppenfilter ({df_video['channel_id'].nunique()} Kanaele, "
          f"Gruppen: {gueltige_gruppen}).")

    dimension = "log_views"
    print(f"\n--- {dimension} | video-ebene | {granularitaet} ---")
    kontroll_spalten = ("log_duration_seconds", "log_upload_dichte")
    zeilen = _teste_und_baue_zeilen(df_video, dimension, spalte_periode, gueltige_gruppen,
                                     treatment_var="ist_kriegsvideo", kontroll_spalten=kontroll_spalten)
    for zeile in zeilen:
        zeile["beobachtungseinheit"] = "video"
    return zeilen


def verarbeite_video_ebene(df, granularitaet, gran_cfg):
    """Baustein 3 (Video-Ebene), seit 2026-09-08 (.claude/plans/frage4_kriegspraemie_
    vergleichsgruppen_und_beobachtungseinheiten.md, Entscheidungen 1-3): laeuft NUR fuer
    Gesamtzeitraum (keine PHASEN-Aufteilung wie Baustein 1/2 - nicht vom Nutzer
    gefordert), aber ueber das Kreuzprodukt aus Stichprobe (voll + DAUER_TEILSTICHPROBEN,
    Entscheidung 2 - reduziert die andernfalls ~824k/783k Videos der vollen Stichprobe
    UND verbessert die Kriegs-/Nichtkriegsvideo-Vergleichbarkeit, siehe Moduldocstring
    "VIDEOLAENGE") x Vergleichsgruppe (VERGLEICHSGRUPPEN, Entscheidung 3). Wird vom
    Aufrufer NUR mit granularitaet="quartal" aufgerufen (Entscheidung 1 - auf Video-Ebene
    macht die Granularitaet ausser der Aufloesung der Perioden-FE keinen Unterschied
    mehr, ein zusaetzlicher "monat"-Lauf lohnt den Mehraufwand nicht)."""
    spalte_periode = gran_cfg["spalte"]
    df_fenster = _fenster(df, spalte_periode, gran_cfg["periode_min"], gran_cfg["periode_max"])

    stichproben = [("voll", "Volle Stichprobe (keine Laengenbeschraenkung)", None)]
    if DAUER_TEILSTICHPROBEN_AKTIV:
        stichproben += [(st_id, st_cfg["label"], st_cfg) for st_id, st_cfg in DAUER_TEILSTICHPROBEN.items()]

    alle_zeilen = []
    for st_id, st_label, st_cfg in stichproben:
        df_stichprobe = df_fenster if st_cfg is None else dauer_teilstichprobe(
            df_fenster, st_cfg["minuten_min"], st_cfg["minuten_max"])
        for vg_id, vg_cfg in VERGLEICHSGRUPPEN.items():
            df_lauf = vergleichsgruppe_filter(
                df_stichprobe, vg_id,
                politik_spalte=POLITIK_SPALTE_JE_VERGLEICHSGRUPPE.get(vg_id, "ist_politisches_video"))
            zeilen = _fuehre_lauf_video_ebene(df_lauf, granularitaet, spalte_periode)
            for zeile in zeilen:
                zeile["stichprobe"] = st_id
                zeile["stichprobe_label"] = st_label
                zeile["vergleichsgruppe"] = vg_id
                zeile["vergleichsgruppe_label"] = vg_cfg["label"]
            alle_zeilen += zeilen
    return alle_zeilen


# =========================================================
# BAUSTEIN 4: Kriegsvideo-ANTEIL als erklaerende Variable (Kanal x Periode, ohne
# ist_kriegsvideo-Split)
# =========================================================

def _fuehre_lauf_anteil(df_fenster, granularitaet, spalte_periode):
    """Siehe Moduldocstring "ZUSATZSPEZIFIKATIONEN". Aggregiert df_fenster zu Kanal x
    Periode-Zellen (aggregiere_kanal_periode_anteil(), OHNE ist_kriegsvideo-Split) und
    testet anteil_kriegsvideos statt ist_kriegsvideo als erklaerende Variable. Alle
    DIMENSIONEN (wie Baustein 1, Zellmittelung ueber mehrere Videos ist hier weiterhin
    sinnvoll), nur Gesamtzeitraum + volle Stichprobe (Laenge; siehe verarbeite_anteil()
    fuer die seit 2026-09-08 zusaetzliche Vergleichsgruppen-Dimension)."""
    df_zellen = aggregiere_kanal_periode_anteil(df_fenster, spalte_periode)
    df_zellen = _filtere_duenne_zellen(df_zellen, bezeichnung="Kanal-Perioden-Zellen (Anteil-Design)")
    df_zellen, gueltige_gruppen = _filtere_duenne_gruppen_anteil(df_zellen)
    print(f"[Anteil-Design][{granularitaet}] {len(df_fenster)} Video-Beobachtungen -> "
          f"{len(df_zellen)} Kanal-{granularitaet}-Zellen ({df_zellen['channel_id'].nunique()} "
          f"Kanaele, Gruppen: {gueltige_gruppen}).")

    zeilen = []
    for dimension in DIMENSIONEN:
        print(f"\n--- {dimension} | anteil-design | {granularitaet} ---")
        zeilen += _teste_und_baue_zeilen(df_zellen, dimension, spalte_periode, gueltige_gruppen,
                                          treatment_var="anteil_kriegsvideos")
    for zeile in zeilen:
        zeile["beobachtungseinheit"] = f"kanal_{granularitaet}_anteil"
    return zeilen


def verarbeite_anteil(df, granularitaet, gran_cfg):
    """Baustein 4 (Anteil-Design), seit 2026-09-08 um die Vergleichsgruppen-Dimension
    ergaenzt (.claude/plans/frage4_kriegspraemie_vergleichsgruppen_und_
    beobachtungseinheiten.md, Entscheidung C): weiterhin NUR Gesamtzeitraum + volle
    Stichprobe (Laenge, keine DAUER_TEILSTICHPROBEN wie Baustein 3 - nicht vom Nutzer
    gefordert), aber gekreuzt mit VERGLEICHSGRUPPEN. Bei vergleichsgruppe_id=
    "nur_politische_videos" verwirft vergleichsgruppe_filter() VOR
    aggregiere_kanal_periode_anteil() alle nicht-politischen sonstigen Videos - der
    Nenner der Anteilsberechnung (n_videos_gesamt in aggregiere_kanal_periode_anteil())
    entspricht dadurch automatisch n_politische_videos_gesamt (Kriegsvideos + andere
    politische Videos), OHNE dass aggregiere_kanal_periode_anteil() selbst angepasst
    werden muss - analog zur Nenner-Restriktion in frage4_kriegspraemie_
    marktanteil_plots.py."""
    spalte_periode = gran_cfg["spalte"]
    df_fenster = _fenster(df, spalte_periode, gran_cfg["periode_min"], gran_cfg["periode_max"])

    alle_zeilen = []
    for vg_id, vg_cfg in VERGLEICHSGRUPPEN.items():
        df_lauf = vergleichsgruppe_filter(
            df_fenster, vg_id,
            politik_spalte=POLITIK_SPALTE_JE_VERGLEICHSGRUPPE.get(vg_id, "ist_politisches_video"))
        zeilen = _fuehre_lauf_anteil(df_lauf, granularitaet, spalte_periode)
        for zeile in zeilen:
            zeile["vergleichsgruppe"] = vg_id
            zeile["vergleichsgruppe_label"] = vg_cfg["label"]
        alle_zeilen += zeilen
    return alle_zeilen


# =========================================================
# MODELL-KOPF FUER DEN LESBAREN BEGLEITBERICHT (PFAD_REPORT)
# =========================================================

def _baue_modell_kopf(dimension, granularitaet, spalte_periode, phase_label, stichprobe_label,
                       vergleichsgruppe_label, n_beobachtungen, n_kanaele,
                       kontroll_spalten=("log_duration_mean", "log_upload_dichte_mean")):
    """Baut den Spezifikations-Kopf EINES Modells fuer PFAD_REPORT (seit 2026-09-09,
    Nutzervorgabe - siehe PFAD_REPORT-Kommentar): Abhaengige Variable, einbezogene
    Kontrollvariablen (inkl. der immer vorhandenen Kanal-/Perioden-FE), Aggregations-
    ebene, Sample-Charakteristika (Zeitfenster/Videolaenge/Vergleichsgruppe) und
    Beobachtungszahl - GENAU die vom Nutzer verlangten fuenf Angaben, in dieser
    Reihenfolge, vor den Ergebniszeilen im bisherigen Format."""
    kontroll_text = ["Kanal-Fixed-Effects (C(channel_id))",
                      f"Perioden-Fixed-Effects (C(periode), {spalte_periode})"]
    kontroll_text += [KONTROLLVARIABLEN_LABEL.get(spalte, spalte) for spalte in kontroll_spalten]
    zeilen = [
        f"### Modell: {dimension} | {granularitaet} | {phase_label} | {stichprobe_label} | "
        f"{vergleichsgruppe_label}",
        "",
        f"- **Abhaengige Variable:** {DIMENSIONEN_LABEL.get(dimension, dimension)}",
        f"- **Kontrollvariablen:** {'; '.join(kontroll_text)}",
        f"- **Aggregation:** Kanal x Periode x Kriegsvideo-Zelle (aggregiere_zellen(), "
        f"Granularitaet {granularitaet}, Periodenspalte {spalte_periode})",
        f"- **Sample-Charakteristika:** Zeitfenster: {phase_label}; Videolaenge: "
        f"{stichprobe_label}; Vergleichsgruppe ('sonstige Videos'): {vergleichsgruppe_label}",
        f"- **Anzahl Beobachtungen:** {n_beobachtungen} Kanal-{granularitaet}-Kriegsvideo-Zellen "
        f"({n_kanaele} Kanaele)",
        "",
        "**Ergebnisse:**",
        "",
    ]
    return "\n".join(zeilen)


# =========================================================
# ERGEBNISTABELLE FUER DEN LESBAREN BEGLEITBERICHT (PFAD_REPORT)
# =========================================================

def _signifikanz_text(p):
    return "ja" if p < 0.05 else "nein"


def _baue_ergebnis_tabelle(gesamt, je_gruppe):
    """Baut die Ergebnistabelle EINES Modells fuer PFAD_REPORT (seit 2026-09-09,
    Nutzervorgabe "die Ergebnisse fuer jede Gruppe... eine einzelne Zeile", siehe
    Moduldocstring "ERGEBNISSE ALS MARKDOWN-TABELLE"): je eine Zeile fuer "Gepoolt
    (alle)" (falls gesamt vorhanden), jede gruppe5-Kategorie aus
    je_gruppe["je_gruppe"] und, falls vorhanden, den Heterogenitaets-F-Test. gesamt/
    je_gruppe sind dieselben dicts wie von kriegspraemie_gesamt_test()/
    kriegspraemie_je_gruppe_test() zurueckgegeben (oder None, wenn der jeweilige Test
    uebersprungen wurde/keine Interaktionsterme lieferte). Gibt None zurueck, wenn
    weder gesamt noch je_gruppe ein Ergebnis liefert (kein Tabellenblock fuer dieses
    Modell)."""
    if not gesamt and not je_gruppe:
        return None
    zeilen = ["| Gruppe | Kriegspraemie | SE | p | Signifikant (p<0,05) |",
              "|---|---|---|---|---|"]
    if gesamt:
        zeilen.append(f"| Gepoolt (alle) | {gesamt['koeffizient_kriegspraemie']:+.4f} | "
                       f"{gesamt['se']:.4f} | {gesamt['p']:.4f} | {_signifikanz_text(gesamt['p'])} |")
    if je_gruppe:
        for _, zeile in je_gruppe["je_gruppe"].iterrows():
            zeilen.append(f"| {zeile['gruppe5']} | {zeile['koeffizient_kriegspraemie']:+.4f} | "
                           f"{zeile['se']:.4f} | {zeile['p']:.4f} | {_signifikanz_text(zeile['p'])} |")
        if je_gruppe["heterogenitaet"]:
            h = je_gruppe["heterogenitaet"]
            zeilen.append(f"| Heterogenitaet (F-Test) | F({h['df_num']}, {h['df_denom']}) = "
                           f"{h['f_stat']:.3f} | - | {h['p']:.4f} | {_signifikanz_text(h['p'])} |")
    return "\n".join(zeilen)


def _executive_summary_bruch(sub):
    """'signifikant/gesamt' (p<0,05) ueber die uebergebene Teilmenge von ergebnis-
    Zeilen, oder '-' wenn die Teilmenge leer ist (z.B. eine gruppe5-Kategorie, die in
    KEINER Spezifikation dieser Zeile MIN_KANAELE_JE_GRUPPE erreicht hat)."""
    gesamt = len(sub)
    if gesamt == 0:
        return "-"
    sig = int((sub["p"] < 0.05).sum())
    return f"{sig}/{gesamt}"


def _baue_executive_summary(ergebnis):
    """Baut die Executive-Summary-Sektion fuer PFAD_REPORT (seit 2026-09-09,
    Nutzervorgabe "Executive Summary ... aufgeteilt nach den wesentlichen Kriterien
    [Vergleichsgruppe, Videolaenge-Stichprobe, Phasen/Gesamtzeitraum] ... in wie
    vielen Spezifikationen der Koeffizient fuer einen Medientyp signifikant ist"):
    eine Gesamtuebersichtszeile plus DREI Breakdown-Tabellen (Vergleichsgruppe,
    Stichprobe/Videolaenge, Zeitfenster). Jede Tabellenzeile ist EINE Auspraegung der
    jeweiligen Dimension, jede Spalte "Gepoolt (alle)" + jede gruppe5-Kategorie
    (GRUPPE5_REIHENFOLGE) + "Heterogenitaet (F-Test)", jede Zelle "signifikant/
    gesamt" (p<0,05) UEBER ALLE Spezifikationen, die auf den jeweils ANDEREN
    Dimensionen variieren (beide DIMENSIONEN [log_views/view_count_median] UND die
    jeweils anderen Breakdown-Kriterien sind darin zusammengefasst - z.B. zaehlt die
    Vergleichsgruppen-Tabelle je Zeile ueber alle 6 Zeitfenster x 3 Stichproben x
    2 Dimensionen = 36 Spezifikationen). "Heterogenitaet (F-Test)" testet NICHT eine
    einzelne Gruppe, sondern ob sich die Gruppen INSGESAMT unterscheiden - andere
    Interpretation als die Gruppen-Spalten, deshalb separat ausgewiesen statt als
    weitere "Gruppe". ergebnis ist dieselbe Long-Format-Tabelle wie PFAD_AUSGABE
    (eine Zeile je Gruppe5/Gepoolt/Heterogenitaet UND Modell) - reine
    Umaggregation der dort bereits berichteten p-Werte, keine neuen Zahlen."""
    n_modelle = int((ergebnis["ebene"] == "gepoolt").sum())
    spalten = [("alle", "Gepoolt (alle)")] + [(g, g) for g in GRUPPE5_REIHENFOLGE]
    spalten_namen = ["Kriterium"] + [label for _, label in spalten] + ["Heterogenitaet (F-Test)"]

    def zeile_fuer(teil, label):
        zeile = {"Kriterium": label}
        for gruppe5_wert, spalten_label in spalten:
            if gruppe5_wert == "alle":
                sub = teil[teil["ebene"] == "gepoolt"]
            else:
                sub = teil[(teil["ebene"] == "je_gruppe") & (teil["gruppe5"] == gruppe5_wert)]
            zeile[spalten_label] = _executive_summary_bruch(sub)
        zeile["Heterogenitaet (F-Test)"] = _executive_summary_bruch(
            teil[teil["ebene"] == "heterogenitaet_ftest"])
        return zeile

    def tabelle(zeilen):
        kopf = "| " + " | ".join(spalten_namen) + " |"
        trenn = "|" + "---|" * len(spalten_namen)
        rumpf = ["| " + " | ".join(str(z[s]) for s in spalten_namen) + " |" for z in zeilen]
        return "\n".join([kopf, trenn] + rumpf)

    gesamt_tabelle = tabelle([zeile_fuer(ergebnis, f"Alle {n_modelle} Spezifikationen")])

    vg_zeilen = [zeile_fuer(ergebnis[ergebnis["vergleichsgruppe"] == vg_id], vg_cfg["label"])
                 for vg_id, vg_cfg in VERGLEICHSGRUPPEN.items()]
    vg_tabelle = tabelle(vg_zeilen)

    st_reihenfolge = [("voll", "Volle Stichprobe (keine Laengenbeschraenkung)")] + [
        (st_id, st_cfg["label"]) for st_id, st_cfg in DAUER_TEILSTICHPROBEN.items()]
    st_zeilen = [zeile_fuer(ergebnis[ergebnis["stichprobe"] == st_id], st_label)
                 for st_id, st_label in st_reihenfolge]
    st_tabelle = tabelle(st_zeilen)

    zf_reihenfolge = [("gesamt", "Gesamtzeitraum (keine Phasenaufteilung)")] + [
        (phase_id, phase_cfg["label"]) for phase_id, phase_cfg in PHASEN.items()]
    zf_zeilen = [zeile_fuer(ergebnis[ergebnis["phase"] == phase_id], phase_label)
                 for phase_id, phase_label in zf_reihenfolge]
    zf_tabelle = tabelle(zf_zeilen)

    return "\n\n".join([
        "## Executive Summary: In wie vielen Spezifikationen ist die Kriegspraemie "
        "je Medientyp signifikant?",
        "Jede Zelle zeigt \"signifikant (p<0,05) / gesamt\" ueber alle "
        "Spezifikationen, die auf den jeweils anderen Kriterien variieren (beide "
        "abhaengigen Variablen UND die uebrigen Breakdown-Dimensionen). \"-\" "
        "bedeutet: diese gruppe5-Kategorie kam in keiner Spezifikation dieser Zeile "
        f"auf mindestens {MIN_KANAELE_JE_GRUPPE} Kanaele und wurde deshalb "
        "ausgeschlossen (siehe MIN_KANAELE_JE_GRUPPE). \"Heterogenitaet (F-Test)\" "
        "testet NICHT eine einzelne Gruppe, sondern ob sich alle Gruppen INSGESAMT "
        "unterscheiden - direkt mit den Gruppen-Spalten zu vergleichen waere "
        "irrefuehrend.",
        "### Gesamtuebersicht",
        gesamt_tabelle,
        "### Nach Vergleichsgruppe (\"sonstige Videos\")",
        vg_tabelle,
        "### Nach Stichprobe (Videolaenge)",
        st_tabelle,
        "### Nach Zeitfenster (Gesamtzeitraum vs. Phasen)",
        zf_tabelle,
    ]) + "\n"


# =========================================================
# EIN ANALYSELAUF (Gesamtzeitraum ODER eine einzelne Phase aus PHASEN)
# =========================================================

def _fuehre_lauf_aus(df_teil, granularitaet, spalte_periode, phase_id, phase_label,
                      stichprobe_id="voll", stichprobe_label="Volle Stichprobe (keine Laengenbeschraenkung)",
                      vergleichsgruppe_id="alle_videos",
                      vergleichsgruppe_label="alle sonstigen Videos (Status quo)"):
    """Ein einzelner, in sich abgeschlossener Analyselauf: Zellenaggregation ->
    Duennzellenfilter -> Gruppenfilter -> je DIMENSION die drei Bausteine (gepoolt,
    je_gruppe, heterogenitaet_ftest). Wird fuer JEDE Kombination aus Zeitfenster
    (Gesamtzeitraum "gesamt" oder eine Phase aus PHASEN), Stichprobe ("voll" oder
    eine DAUER_TEILSTICHPROBE) UND Vergleichsgruppe (VERGLEICHSGRUPPEN, seit 2026-09-08)
    aufgerufen (siehe verarbeite_granularitaet()/Moduldocstring "VIDEOLAENGE"/
    "ZUSATZSPEZIFIKATIONEN") - Kanal-FE und C(periode)-FE beziehen sich dabei NUR auf
    die in df_teil enthaltenen Perioden/Videos, ein Phasen- bzw. Dauer-Lauf 'sieht'
    also keine anderen Phasen/die volle Stichprobe nicht. df_teil ist bei
    vergleichsgruppe_id in ("nur_politische_videos", "nur_politische_videos_llm")
    bereits ueber vergleichsgruppe_filter() gefiltert (Aufgabe des Aufrufers, NICHT
    dieser Funktion - die Modellformel/Aggregationslogik hier bleibt dadurch bitwise
    identisch zur alle_videos-Variante, nur die Eingabedaten unterscheiden sich).
    kontroll_spalten bekommt zusaetzlich anteil_politischer_videos, wenn
    vergleichsgruppe_id == "alle_videos" (siehe Moduldocstring "KONTROLLE 'ANTEIL
    POLITISCHER VIDEOS'"). Gibt (zeilen, report_bloecke) zurueck: zeilen wie bisher
    (Ausgabe/CSV-Schreiben macht der Aufrufer), report_bloecke ist seit 2026-09-09 eine
    Liste fertig formatierter Textbloecke (ein Block je DIMENSION, Kopf aus
    _baue_modell_kopf() + Tabelle aus _baue_ergebnis_tabelle()) fuer PFAD_REPORT -
    reine Formatierung derselben bereits berechneten Werte, aendert die CSV-Zahlen
    NICHT."""
    df_zellen = aggregiere_zellen(df_teil, spalte_periode)
    df_zellen = _filtere_duenne_zellen(df_zellen)
    df_zellen, gueltige_gruppen = _filtere_duenne_gruppen(df_zellen)
    print(f"[Aggregation][{granularitaet}][{phase_label}][{stichprobe_label}] "
          f"{len(df_teil)} Video-Beobachtungen -> {len(df_zellen)} Kanal-{granularitaet}-"
          f"Kriegsvideo-Zellen ({df_zellen['channel_id'].nunique()} Kanaele, Gruppen: {gueltige_gruppen}).")

    kontroll_spalten = ("log_duration_mean", "log_upload_dichte_mean")
    if vergleichsgruppe_id == "alle_videos":
        kontroll_spalten = kontroll_spalten + ("anteil_politischer_videos",)

    zeilen = []
    report_bloecke = []
    for dimension in DIMENSIONEN:
        print(f"\n--- {dimension} | {granularitaet} | {phase_label} | {stichprobe_label} ---")

        gesamt = kriegspraemie_gesamt_test(df_zellen, dimension, spalte_periode,
                                            kontroll_spalten=kontroll_spalten)
        if gesamt:
            sig = "signifikant" if gesamt["p"] < 0.05 else "nicht signifikant"
            print(f"  [Gepoolt] Kriegspraemie = {gesamt['koeffizient_kriegspraemie']:+.4f} "
                  f"(p={gesamt['p']:.4f}) -> {sig}, n_kanaele={gesamt['n_kanaele']}")
            zeilen.append({"dimension": dimension, "ebene": "gepoolt", "gruppe5": "alle", **gesamt})

        je_gruppe = kriegspraemie_je_gruppe_test(df_zellen, dimension, spalte_periode, gueltige_gruppen,
                                                  kontroll_spalten=kontroll_spalten)
        if je_gruppe:
            for _, zeile in je_gruppe["je_gruppe"].iterrows():
                sig = "signifikant" if zeile["p"] < 0.05 else "nicht signifikant"
                print(f"  [{zeile['gruppe5']}] Kriegspraemie = {zeile['koeffizient_kriegspraemie']:+.4f} "
                      f"(p={zeile['p']:.4f}) -> {sig}")
                zeilen.append({
                    "dimension": dimension, "ebene": "je_gruppe", "gruppe5": zeile["gruppe5"],
                    "koeffizient_kriegspraemie": zeile["koeffizient_kriegspraemie"],
                    "se": zeile["se"], "p": zeile["p"],
                    "n_beobachtungen": je_gruppe["n_beobachtungen"], "n_kanaele": je_gruppe["n_kanaele"],
                })
            if je_gruppe["heterogenitaet"]:
                h = je_gruppe["heterogenitaet"]
                sig = "signifikant" if h["p"] < 0.05 else "nicht signifikant"
                print(f"  [Heterogenitaet] F({h['df_num']}, {h['df_denom']}) = {h['f_stat']:.3f}, "
                      f"p = {h['p']:.4f} -> {sig} unterschiedliche Kriegspraemien zwischen den Gruppen")
                zeilen.append({
                    "dimension": dimension, "ebene": "heterogenitaet_ftest", "gruppe5": "alle",
                    "f_stat": h["f_stat"], "df_num": h["df_num"], "df_denom": h["df_denom"], "p": h["p"],
                    "n_beobachtungen": je_gruppe["n_beobachtungen"], "n_kanaele": je_gruppe["n_kanaele"],
                })

        # n_beobachtungen/n_kanaele fuer den Modell-Kopf: bevorzugt aus je_gruppe (deckt
        # auch den Heterogenitaets-F-Test-Sample ab), sonst aus gesamt - beide Tests
        # laufen auf derselben df_zellen und liefern damit praktisch immer dieselbe
        # Zahl, aber je_gruppe kann in seltenen Faellen (zu wenig Variation innerhalb
        # Kanaelen) scheitern, waehrend gesamt noch erfolgreich ist.
        quelle_n = je_gruppe or gesamt
        tabelle = _baue_ergebnis_tabelle(gesamt, je_gruppe)
        if tabelle and quelle_n:
            kopf = _baue_modell_kopf(dimension, granularitaet, spalte_periode, phase_label,
                                      stichprobe_label, vergleichsgruppe_label,
                                      quelle_n["n_beobachtungen"], quelle_n["n_kanaele"],
                                      kontroll_spalten=kontroll_spalten)
            report_bloecke.append(kopf + "\n" + tabelle)

    for zeile in zeilen:
        zeile["phase"] = phase_id
        zeile["phase_label"] = phase_label
        zeile["stichprobe"] = stichprobe_id
        zeile["stichprobe_label"] = stichprobe_label
        zeile["vergleichsgruppe"] = vergleichsgruppe_id
        zeile["vergleichsgruppe_label"] = vergleichsgruppe_label
    return zeilen, report_bloecke


# =========================================================
# MAIN
# =========================================================

def verarbeite_granularitaet(df, granularitaet, gran_cfg):
    """Iteriert ueber das volle Kreuzprodukt aus Zeitfenster (Gesamtzeitraum "gesamt"
    + jede PHASE, falls PHASEN_AKTIV) x Stichprobe ("voll" + jede DAUER_TEILSTICHPROBE,
    falls DAUER_TEILSTICHPROBEN_AKTIV) x Vergleichsgruppe (VERGLEICHSGRUPPEN, seit
    2026-09-08, siehe Moduldocstring "VIDEOLAENGE"/"ZUSATZSPEZIFIKATIONEN"). Die
    Dauer-Teilstichprobe filtert IMMER auf Video-Ebene (dauer_teilstichprobe()), die
    Vergleichsgruppe DANACH ebenfalls auf Video-Ebene (vergleichsgruppe_filter()) -
    beide VOR aggregiere_zellen() in _fuehre_lauf_aus(). Die alle_videos-Variante bleibt
    dadurch bitwise identisch zu den bereits berichteten Zahlen (vergleichsgruppe_
    filter() gibt df bei modus="alle_videos" unveraendert zurueck)."""
    spalte_periode = gran_cfg["spalte"]

    zeitfenster = [("gesamt", "Gesamtzeitraum (keine Phasenaufteilung)",
                     _fenster(df, spalte_periode, gran_cfg["periode_min"], gran_cfg["periode_max"]))]
    if PHASEN_AKTIV:
        zeitfenster += [
            (phase_id, phase_cfg["label"], _phase_fenster(df, phase_cfg["monat_min"], phase_cfg["monat_max"]))
            for phase_id, phase_cfg in PHASEN.items()
        ]

    stichproben = [("voll", "Volle Stichprobe (keine Laengenbeschraenkung)", None)]
    if DAUER_TEILSTICHPROBEN_AKTIV:
        stichproben += [(st_id, st_cfg["label"], st_cfg) for st_id, st_cfg in DAUER_TEILSTICHPROBEN.items()]

    alle_zeilen = []
    alle_report_bloecke = []
    for phase_id, phase_label, df_zeitfenster in zeitfenster:
        for st_id, st_label, st_cfg in stichproben:
            df_stichprobe = df_zeitfenster if st_cfg is None else dauer_teilstichprobe(
                df_zeitfenster, st_cfg["minuten_min"], st_cfg["minuten_max"])
            for vg_id, vg_cfg in VERGLEICHSGRUPPEN.items():
                df_lauf = vergleichsgruppe_filter(
                    df_stichprobe, vg_id,
                    politik_spalte=POLITIK_SPALTE_JE_VERGLEICHSGRUPPE.get(vg_id, "ist_politisches_video"))
                zeilen, report_bloecke = _fuehre_lauf_aus(df_lauf, granularitaet, spalte_periode,
                                                           phase_id, phase_label, st_id, st_label,
                                                           vg_id, vg_cfg["label"])
                alle_zeilen += zeilen
                alle_report_bloecke += report_bloecke

    ergebnis = pd.DataFrame(alle_zeilen)
    ergebnis["granularitaet"] = granularitaet
    pfad = str(PFAD_AUSGABE).format(granularitaet=granularitaet)
    ergebnis.to_csv(pfad, index=False, encoding="utf-8")
    n_laeufe = len(zeitfenster) * len(stichproben) * len(VERGLEICHSGRUPPEN)
    print(f"\n[Ausgabe][{granularitaet}] {len(ergebnis)} Zeilen aus {n_laeufe} Laeufen "
          f"({len(zeitfenster)} Zeitfenster x {len(stichproben)} Stichproben x "
          f"{len(VERGLEICHSGRUPPEN)} Vergleichsgruppen) -> {pfad}")

    # Lesbarer Begleitbericht (PFAD_REPORT, siehe dortigen Kommentar) - ein Textblock je
    # in _fuehre_lauf_aus() berechnetem Modell, mit vorangestelltem, EINMALIGEM Kopf zur
    # Methodik (analog document-comparative-analysis-methodology). Dieselben Zahlen wie
    # in `ergebnis`, nur menschenlesbar gruppiert statt als CSV-Zeilen.
    report_kopf = (
        f"# Kriegspraemie x Medientyp - {granularitaet}\n\n"
        f"Jedes Modell schaetzt `y ~ C(channel_id) + C(periode) + log_duration_mean + "
        f"log_upload_dichte_mean [+ anteil_politischer_videos] + "
        f"ist_kriegsvideo:C(gruppe5)` auf Kanal x Periode x Kriegsvideo-Zellen, "
        f"Standardfehler geclustert auf Kanalebene (kriegspraemie_je_gruppe_test()/"
        f"kriegspraemie_gesamt_test() in frage4_kriegspraemie_medientyp_bericht.py) - "
        f"anteil_politischer_videos NUR bei Vergleichsgruppe 'alle_videos' (siehe "
        f"jeweilige 'Kontrollvariablen'-Zeile je Modell). Die Ergebnistabelle je Modell "
        f"hat eine Zeile 'Gepoolt (alle)' (ein einzelner ist_kriegsvideo-Koeffizient "
        f"ueber alle Gruppen, Effektgroessen-Baseline), je eine Zeile pro gruppe5-"
        f"Kategorie (vollrangig kodierter Koeffizient, direkt als deren Kriegspraemie "
        f"interpretierbar) und eine Zeile 'Heterogenitaet (F-Test)' (gemeinsamer F-Test "
        f"auf Gleichheit aller Gruppenkoeffizienten). {len(alle_report_bloecke)} Modelle "
        f"aus {n_laeufe} Laeufen ({len(zeitfenster)} Zeitfenster x "
        f"{len(stichproben)} Stichproben x {len(VERGLEICHSGRUPPEN)} Vergleichsgruppen x "
        f"{len(DIMENSIONEN)} Dimension(en)).\n"
    )
    report_pfad = str(PFAD_REPORT).format(granularitaet=granularitaet)
    executive_summary = _baue_executive_summary(ergebnis)
    with open(report_pfad, "w", encoding="utf-8") as f:
        f.write(report_kopf + "\n" + executive_summary + "\n\n" + "\n\n".join(alle_report_bloecke) + "\n")
    print(f"[Ausgabe][{granularitaet}] {len(alle_report_bloecke)} Modell-Bloecke "
          f"(+ Executive Summary) -> {report_pfad}")
    return ergebnis


def main():
    df = lade_video_daten()

    if PHASEN_AKTIV:
        print("\n[Phasen] Zusaetzlich zum Gesamtzeitraum wird das Sample in folgende "
              "Phasen aufgeteilt (siehe PHASEN fuer die volle Begruendung):")
        for phase_id, cfg in PHASEN.items():
            bereich = f"Monat {cfg['monat_min']}" + (
                f"-{cfg['monat_max']}" if cfg["monat_max"] is not None else "+")
            print(f"  {phase_id} ({bereich}): {cfg['label']}")

    if DAUER_TEILSTICHPROBEN_AKTIV:
        print("\n[Dauer-Teilstichproben] Zusaetzlich zur vollen Stichprobe laeuft jedes "
              "Zeitfenster mit folgenden Laengenbeschraenkungen (siehe DAUER_TEILSTICHPROBEN):")
        for st_id, cfg in DAUER_TEILSTICHPROBEN.items():
            obergrenze = cfg["minuten_max"] if cfg["minuten_max"] is not None else "unbegrenzt"
            print(f"  {st_id} ({cfg['minuten_min']}-{obergrenze} Min): {cfg['label']}")

    alle_ergebnisse = []
    for granularitaet, gran_cfg in GRANULARITAETEN.items():
        alle_ergebnisse.append(verarbeite_granularitaet(df, granularitaet, gran_cfg))

    if VIDEO_EBENE_AKTIV or ANTEIL_DESIGN_AKTIV:
        print("\n" + "=" * 70)
        print("ZUSATZSPEZIFIKATIONEN: alternative Beobachtungseinheiten")
        print("=" * 70)

    if VIDEO_EBENE_AKTIV:
        # Baustein 3 NUR "quartal" (Entscheidung 1, siehe verarbeite_video_ebene()).
        granularitaet = "quartal"
        zeilen = verarbeite_video_ebene(df, granularitaet, GRANULARITAETEN[granularitaet])
        ausgabe = pd.DataFrame(zeilen)
        ausgabe["granularitaet"] = granularitaet
        pfad = str(RESULTS_PATH / f"frage4_kriegspraemie_video_bericht_{granularitaet}.csv")
        ausgabe.to_csv(pfad, index=False, encoding="utf-8")
        print(f"[Ausgabe][Video-Ebene][{granularitaet}] {len(ausgabe)} Zeilen -> {pfad}")

    if ANTEIL_DESIGN_AKTIV:
        for granularitaet, gran_cfg in GRANULARITAETEN.items():
            zeilen = verarbeite_anteil(df, granularitaet, gran_cfg)
            ausgabe = pd.DataFrame(zeilen)
            ausgabe["granularitaet"] = granularitaet
            pfad = str(RESULTS_PATH / f"frage4_kriegspraemie_anteil_bericht_{granularitaet}.csv")
            ausgabe.to_csv(pfad, index=False, encoding="utf-8")
            print(f"[Ausgabe][Anteil-Design][{granularitaet}] {len(ausgabe)} Zeilen -> {pfad}")

    gesamt = pd.concat(alle_ergebnisse, ignore_index=True)

    print("\n" + "=" * 70)
    print("KURZZUSAMMENFASSUNG (Kriegspraemie je Gruppe, p < 0.05)")
    print("=" * 70)
    ueberblick = gesamt[(gesamt["ebene"] == "je_gruppe") & (gesamt["p"] < 0.05)]
    if ueberblick.empty:
        print("  Keine Gruppe mit signifikanter Kriegspraemie in dieser Spezifikation.")
    for _, zeile in ueberblick.sort_values(
            ["granularitaet", "phase", "stichprobe", "vergleichsgruppe", "dimension"]).iterrows():
        richtung = "positive" if zeile["koeffizient_kriegspraemie"] > 0 else "negative"
        print(f"  [{zeile['phase']}][{zeile['stichprobe']}][{zeile['vergleichsgruppe']}] "
              f"{zeile['dimension']} ({zeile['granularitaet']}), {zeile['gruppe5']}: "
              f"{richtung} Kriegspraemie {zeile['koeffizient_kriegspraemie']:+.4f} (p={zeile['p']:.4f})")


if __name__ == "__main__":
    main()

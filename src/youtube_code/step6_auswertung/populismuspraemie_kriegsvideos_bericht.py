# -*- coding: utf-8 -*-
"""
populismuspraemie_kriegsvideos_bericht.py

Antwort auf TODO 2 aus .claude/Aufgaben.md:
"Gibt es eine 'Populismuspraemie': Erhalten populistische Kriegsvideos innerhalb
eines Kanals signifikant mehr Aufrufe als weniger populistische Videos?"

Seit 2026-09-08 ueber MODUS auc h auf die Haltung gegenueber Russland/westlicher
Ukraine-Politik anwendbar (Nutzervorgabe: "moechte ebenfalls die Option haben, auf
die Ergebnisse zur Haltung gegenueber Russland/dem Westen zuzugreifen") - dieselbe
Frage, nur mit den Haltungs- statt den Populismus-Dimensionen: sind Kriegsvideos
mit einer prononcierteren Position innerhalb eines Kanals erfolgreicher? Strukturell
identisches MODUS-Konzept wie fe_signifikanz_test.py/deskriptiv_aggregation.py
("populismus" | "stance", channel_video_populism.csv vs. channel_video_position.csv).

Anders als frage3_populismus_erfolg_bericht.py (Forschungsfrage 3, Kanal x Periode-
Ebene, Populismus-NIVEAU eines Kanals ueber die Zeit vs. dessen Erfolg) arbeitet
dieses Skript auf VIDEO-Ebene und NUR auf Kriegsvideos: hat ein einzelnes
Kriegsvideo, das populistischer (bzw. bei MODUS="stance" prononcierter positioniert)
ist als die anderen Kriegsvideos DESSELBEN Kanals, auch mehr Views? Kanal-Fixed-
Effects halten dabei alle zeitkonstanten Kanaleigenschaften (Groesse, Thema,
Ideologie, Medientyp als Haupteffekt) konstant - der Koeffizient ist die reine
Innerhalb-Kanal-Korrelation zwischen Dimension und Erfolg EINES Videos,
ausschliesslich unter den Kriegsvideos dieses Kanals.

Datengrundlage: Merge von channel_video_{populism,position}.csv (Video-Ebene,
Schritt 0 aus prepare_channel_scores.py, Datei je nach MODUS) und
channel_video_erfolg.csv (Video-Ebene, Views + ist_kriegsvideo-Flag, Schritt 0c aus
prepare_success_metrics.py) auf video_id (Inner-Join - Dimensionen liegen nur fuer
LLM-klassifizierte Videos vor). channel_video_erfolg.csv ist bereits auf die
Frage-1-Kanal-Whitelist beschraenkt (siehe _lade_whitelist() in
prepare_success_metrics.py) - eine zusaetzliche explizite Whitelist-Filterung ist
hier deshalb NICHT noetig, anders als bei frage3_populismus_erfolg_bericht.py (dort
wird auf den rohen, NICHT whitelist-gefilterten Zeitreihen gemergt). Anschliessend
Filter auf ist_kriegsvideo == 1.

ZWEI BAUSTEINE, je Dimension (bei MODUS="populismus": Gesamtscore + die vier
Einzeldimensionen; bei MODUS="stance": position_russland, position_westpolitik und
die Kontrollgroesse emotion):

(a) Gesamtmodell (gesamtmodell_test(), gesamte Stichprobe, gesamter
    Zeitraum, KEINE Periodenaufspaltung - das ist der "erste Schritt"; seit
    2026-09-08 zusaetzlich mit log_duration_seconds als Kontrollvariable,
    siehe Abschnitt "VIDEOLAENGE..." unten):
        log_views ~ dimension + log_duration_seconds + C(channel_id)
    SE geclustert auf Kanalebene. Der Koeffizient beantwortet die Kernfrage direkt:
    ist ein Kriegsvideo mit hoeherem Dimensionswert innerhalb desselben Kanals
    erfolgreicher?

(b) Interaktion mit Medientyp (interaktion_medientyp_test()): prueft, ob der
    Effekt aus (a) fuer bestimmte Medientypen staerker ist. Medientyp ist
    zeitkonstant je Kanal und daher als eigener Haupteffekt vollstaendig kollinear
    mit den Kanal-FE (wie ueberall in diesem Ordner, siehe bericht_utils.py und
    frage4_kriegspraemie_medientyp_bericht.py). Formel (vollrangige Kodierung von
    C(medientyp) INNERHALB der Interaktion, kein eigener dimension-Haupteffekt noetig
    - dieselbe Vollrang-Logik wie "ist_kriegsvideo:C(gruppe5)" in
    frage4_kriegspraemie_medientyp_bericht.py, dort am synthetischen Beispiel
    verifiziert; seit 2026-09-08 zusaetzlich mit log_duration_seconds als
    Kontrollvariable):
        log_views ~ C(channel_id) + log_duration_seconds + dimension:C(medientyp)
    Jeder Koeffizient "dimension:C(medientyp)[X]" ist direkt als "Effekt fuer
    Medientyp X" interpretierbar (kein Referenzgruppen-Vergleich noetig).
    Zusaetzlich ein Heterogenitaets-F-Test (paarweise Gleichheit aller
    Medientyp-Slopes) - unterscheidet sich der Effekt zwischen Medientypen?
    Medientypen mit weniger als MIN_KANAELE_JE_GRUPPE Kanaelen (mit mindestens
    einem klassifizierten Kriegsvideo) werden vorher ausgeschlossen.

Bewusst NOCH KEINE Ideologie-Interaktion oder Zellen-Mindestbesetzung wie in
frage4_kriegspraemie_medientyp_bericht.py - "einfaches Skript" fuer den ersten Schritt
(Nutzervorgabe), Erweiterungen folgen bei Bedarf.

BAUSTEIN (d) - INTERAKTION MIT ZEITPERIODE (seit 2026-09-08, Nutzervorgabe: "Setze die
Zeitperioden-Interaktion um", als automatisierte Antwort auf die Frage, ob der Effekt
einer Dimension in bestimmten Zeitraeumen besonders hoch ist): strukturell identisch zu
(b), nur mit Zeitperiode statt Medientyp als Gruppierung (seit 2026-09-08
ebenfalls mit log_duration_seconds als Kontrollvariable) -
        log_views ~ C(channel_id) + log_duration_seconds + dimension:C(zeitperiode)
Zeitperiode wird aus ZEITPERIODEN_SPALTE (rel_quartal/rel_monat relativ zu KRIEGSBEGINN,
siehe ergaenze_periodenspalten() in prepare_channel_scores.py) ueber die konfigurierbaren
ZEITPERIODEN_GRENZEN in Bins gruppiert (erstelle_zeitperiode()), z.B. "Q0-Q3"/"Q4-Q7"/
"Q8+". Wie bei (b) vollrangige Kodierung (kein dimension-Haupteffekt, kein
C(zeitperiode)-Haupteffekt) - jeder Koeffizient "dimension:C(zeitperiode)[X]" ist direkt
als "Effekt in Zeitperiode X" interpretierbar, ergaenzt um denselben
Heterogenitaets-F-Test wie bei (b) (unterscheidet sich der Effekt zwischen den
Zeitperioden?). Zeitperioden mit weniger als MIN_KANAELE_JE_GRUPPE Kanaelen werden wie
bei (b) vorher ausgeschlossen.

BAUSTEIN (c) - KOMBINIERTES MODELL (seit 2026-09-08, Nutzervorgabe: "kombinierte
Regression, bei der die Position gegenueber Russland und Populismus enthalten sind"):
anders als (a)/(b), die IMMER nur Dimensionen aus EINER Datei testen (gesteuert ueber
MODUS), enthaelt dieses Modell mehrere Dimensionen GLEICHZEITIG als Regressoren -
unabhaengig von MODUS und ggf. aus BEIDEN Dateien (channel_video_populism.csv UND
channel_video_position.csv) gemischt (seit 2026-09-08 zusaetzlich mit
log_duration_seconds als Kontrollvariable):
    log_views ~ KOMBI_VARIABLEN[0] + KOMBI_VARIABLEN[1] + ... + log_duration_seconds + C(channel_id)
SE wieder geclustert auf Kanalebene. Jeder Koeffizient ist damit der Effekt DIESER
Dimension, HALTEND fuer alle anderen KOMBI_VARIABLEN (z.B. der Populismus-Effekt
NETTO der Position ggue. Russland, und umgekehrt) - beantwortet, ob sich Populismus
und Positionierung gegenseitig "wegerklaeren" oder beide unabhaengig zum Erfolg
beitragen. Welche Dimensionen einfliessen, ist ueber den CONFIG-Block KOMBI_VARIABLEN
frei einstellbar (DATEINAME_JE_VARIABLE ordnet jeder moeglichen Dimension automatisch
ihre Quelldatei zu, sodass beliebige Mischungen aus beiden Dateien funktionieren).
Zusaetzlich (Nutzervorgabe: "Tabelle, wie stark die einbezogenen Variablen miteinander
korrelieren") paarweise Pearson-Korrelationen zwischen allen KOMBI_VARIABLEN
(kombiniertes_modell_korrelation(), auf derselben Stichprobe wie das Modell selbst) -
ein Multikollinearitaets-Check: je hoeher die Korrelation zwischen zwei Regressoren,
desto instabiler/schwerer trennbar sind ihre Koeffizienten im kombinierten Modell.
Eigene Ausgabedatei kombiniertes_modell_korrelation.csv (PFAD_AUSGABE_KOMBI_KORRELATION).

BAUSTEIN (e) - KOMBINIERTES MODELL x ZEITPERIODE (seit 2026-09-08, Nutzervorgabe:
"Ich moechte, dass in dem kombinierten Modell die Effekte in verschiedenen Zeitraeumen
verglichen werden"): wie (c), aber jede KOMBI_VARIABLE bekommt zusaetzlich vollrangige,
periodenspezifische Koeffizienten statt eines einzigen Effekts ueber den gesamten
Zeitraum - Formel (dieselben ZEITPERIODEN_GRENZEN/erstelle_zeitperiode() wie Baustein
(d), seit 2026-09-08 ebenfalls mit log_duration_seconds als Kontrollvariable):
    log_views ~ C(channel_id) + log_duration_seconds + KOMBI_VARIABLEN[0]:C(zeitperiode) + ...
Jeder Koeffizient "variable:C(zeitperiode)[X]" ist direkt als "Effekt dieser Variable in
Zeitperiode X, HALTEND fuer die anderen KOMBI_VARIABLEN (ebenfalls periodenspezifisch)"
interpretierbar. Zusaetzlich je KOMBI_VARIABLE ein eigener Heterogenitaets-F-Test
(unterscheidet sich DIESE Variable zwischen den Zeitperioden?). Zeitperioden mit
weniger als MIN_KANAELE_JE_GRUPPE Kanaelen werden vorher ausgeschlossen (wie (b)/(d)).

BAUSTEIN (f) - KOMBINIERTES MODELL x ZEITPERIODE JE MEDIENTYP/IDEOLOGIE-GRUPPE (seit
2026-09-08, Nutzervorgabe: "wenn moeglich sogar aufgeteilt nach Medientyp. Also konnten
z.B. rechte alternative Medien durch eine starke pro-Russland-Positionierung besonders
ihre Views steigern"): fuehrt Baustein (e) SEPARAT innerhalb jeder gruppe5-Kategorie aus
(ÖRR, Traditionelles Medium, Alternative Medien links/mitte/rechts - siehe
baue_gruppe5_lokal(), lokale Nachbildung von deskriptiv_plots.py::baue_gruppe5() wie in
frage4_kriegspraemie_medientyp_bericht.py; da main() ausschliesslich ueber
GRUPPE5_REIHENFOLGE iteriert, fallen Politiker/Partei sowie Alternative Medien ohne
Ideologie-Einordnung fuer Baustein (f) implizit raus - Baustein (c)/(e) bleiben davon
unberuehrt und nutzen weiterhin ALLE Kanaele). "Medientyp" wird hier bewusst als gruppe5
(Medientyp UND, bei Alternativen Medien, Ideologie) verstanden statt als reiner
Medientyp - siehe alternative-medien-ideologie-differenzierung: nur so laesst sich die
Nutzerfrage nach "rechten alternativen Medien" ueberhaupt beantworten, ein reiner
Medientyp-Schnitt wuerde linke/mittige/rechte Alternativmedien vermischen. BEWUSST als
getrennte Modelle je Gruppe (statt einer gemeinsamen dreifachen Interaktion
dimension:C(zeitperiode):C(gruppe5)) - eine dreifache Interaktion haette bei 4
KOMBI_VARIABLEN x 4 Zeitperioden x 5 gruppe5-Kategorien = bis zu 80 Interaktionsterme,
was angesichts der Kanalzahl je Gruppe nicht mehr robust schaetzbar waere. gruppe5-
Kategorien mit weniger als MIN_KANAELE_JE_GRUPPE Kanaelen (mit klassifiziertem
Kriegsvideo) werden komplett uebersprungen; INNERHALB einer Gruppe gilt zusaetzlich
dieselbe Zeitperioden-Mindestbesetzung wie bei (e).

BAUSTEIN (g) - INTERAKTION POPULISMUS x POSITION (seit 2026-09-10, Nutzervorgabe: "Setz
Punkt 2 mit dem Interaktionsterm um" - als Antwort auf die Rueckfrage, was mit der
"Wechselwirkung zwischen Position und Populismus" gemeint war: verstaerkt Populismus die
Positionspraemie (TODO 3), bzw. symmetrisch: verstaerkt Position die Populismuspraemie
(TODO 2)? Anders als Baustein (c)/(e)/(f), die populismus_gesamt und die Positions-
Dimensionen als GETRENNTE additive Regressoren behandeln (haelt jeweils fuer die andere
Dimension, testet aber keine Verstaerkung), enthaelt dieser Baustein fuer jedes Paar aus
INTERAKTIONS_PAARE_POPULISMUS_POSITION ein eigenes MULTIPLIKATIVES Modell
(interaktion_populismus_position_test(), unabhaengig von MODUS, arbeitet wie (c)/(e)/(f)
auf kombi_df, da beide Dimensionsarten gleichzeitig benoetigt werden):
    log_views ~ center(position) * center(populismus_gesamt) + Kontrollvariablen + C(channel_id)
Zentrierung (patsy center()) macht die beiden Haupteffekt-Koeffizienten direkt
interpretierbar (Effekt der einen Dimension BEIM DURCHSCHNITTSWERT der anderen), ohne den
eigentlichen Interaktionskoeffizienten zu veraendern. Der entscheidende Koeffizient ist
der Interaktionsterm "center(position):center(populismus_gesamt)" - ein signifikant
positiver Wert bedeutet: je populistischer ein Kriegsvideo, desto STAERKER schlaegt seine
Position auf die Views durch (bzw. symmetrisch umgekehrt). Ergebniszeilen bekommen eine
zusaetzliche Spalte "term" ("position_haupteffekt" | "populismus_haupteffekt" |
"interaktion"), da hier - anders als bei (b)/(d) - kein "je Gruppe"-Konzept existiert.
Laeuft, wie (c)/(e)/(f), NUR wenn kombi_df >= 2 Kanaele mit gemeinsamer Klassifikation
hat, und wie alle anderen Bausteine je DAUER_TEILSTICHPROBE (siehe unten) erneut.

VIDEOLAENGE ALS KONTROLLVARIABLE UND SENSITIVITAETS-TEILSTICHPROBE (seit 2026-09-08,
.claude/Aufgaben.md letzter Absatz + Nutzervorgabe "Integriere die Videodauer in die
Analyse... als Kontrollvariable... und eine laengen-eingegrenzte Sensitivitaets-
Teilstichprobe"): auch wenn dieses Skript NUR auf Kriegsvideos arbeitet (der Kriegs-
vs.-Nichtkriegsvideo-Laengenunterschied aus scripts/adhoc/videolaenge_diagnose.py
betrifft es also nicht direkt), koennte innerhalb der Kriegsvideos selbst die
Videolaenge sowohl mit der jeweiligen Dimension (z.B. laengere Videos = mehr Raum fuer
Polemik/Emotion) als auch mit dem Erfolg zusammenhaengen - ein Konfundierungsrisiko fuer
JEDEN hier getesteten Koeffizienten. Zwei Massnahmen, konsequent in JEDEM Baustein
(a/b/c/d/e/f/g) angewendet (Nutzervorgabe: "ueberall"):
(1) log_duration_seconds wird als zusaetzlicher additiver Term in JEDE Modellformel
    aufgenommen (gesamtmodell_test(), interaktion_medientyp_test(),
    interaktion_zeitperiode_test(), kombiniertes_modell_test(),
    kombiniertes_modell_zeitperiode_test(), interaktion_populismus_position_test()) -
    haelt die Videolaenge konstant, wird selbst NICHT separat ausgegeben (reine
    Kontrollgroesse, analog log_duration_mean in
    frage4_kriegspraemie_medientyp_bericht.py).
(2) DAUER_TEILSTICHPROBEN (dieselbe Konfigurationslogik wie in
    frage4_kriegspraemie_medientyp_bericht.py, gemeinsame Filterfunktion
    bericht_utils.py::dauer_teilstichprobe(), feste statt perzentilbasierte
    Minuten-Intervalle, frei anpassbar/erweiterbar) - der GESAMTE main()-Ablauf
    (alle Bausteine a-g) laeuft je Stichprobe ("voll" + jede DAUER_TEILSTICHPROBE)
    komplett eigenstaendig durch (fuehre_analyse_aus(), von main() je Stichprobe
    aufgerufen, gekapselt aus dem
    frueheren main()-Koerper), Ergebniszeilen bekommen dafuer eine zusaetzliche Spalte
    "stichprobe" ("voll" oder eine DAUER_TEILSTICHPROBEN-Kennung); ebenso die
    Korrelationstabelle aus Baustein (c) (PFAD_AUSGABE_KOMBI_KORRELATION, dieselbe
    zusaetzliche Spalte, gesammelt statt bei jedem Stichprobenlauf ueberschrieben).

TESTWEISE KONTROLLVARIABLEN age_days/category_id (seit 2026-09-08, Nutzervorgabe
"Nimm age_days und category_id testweise dazu" - als Antwort auf die Frage "gibt es
noch weitere Kontrollvariablen, die ich verwenden koennte?"): anders als Videolaenge
ist das noch keine endgueltige, "ueberall"-verankerte Entscheidung, sondern ein Test,
ob diese beiden zusaetzlichen Kontrollvariablen die Ergebnisse veraendern:
- age_days (Tage zwischen Veroeffentlichung und Datenabruf, bereits vorher Teil von
  channel_video_erfolg.csv, siehe prepare_success_metrics.py) adressiert einen
  Konfundierer, den KEIN Baustein hier bisher kontrolliert hat: Baustein (a) hat gar
  keine Periodenkontrolle, Baustein (d)/(e)/(f) nur die groben ZEITPERIODEN_GRENZEN-
  Bins - wenn populistischere/prononcierter positionierte Videos systematisch aelter
  oder juenger sind, hatten sie schlicht mehr/weniger Zeit, Views zu sammeln.
- category_id (YouTubes eigene numerische Video-Kategorie, z.B. "25" = News &
  Politics, "24" = Entertainment - video_registry.category_id_lookup(), 100%
  Abdeckung) ist anders als Medientyp/Ideologie KEINE kanalkonstante Eigenschaft
  (ein Kanal kann z.B. sowohl News-Content als auch Unterhaltung posten) und damit
  ein zusaetzlicher, von der Dauer unabhaengiger Inhalts-Proxy. Seltene Kategorien
  (< KATEGORIE_MIN_VIDEOS Kriegsvideos in der jeweiligen Stichprobe) werden zu
  "Sonstige" zusammengefasst (_gruppiere_kategorie()), sonst waere C(kategorie_gruppe)
  mit vielen fast leeren Dummy-Spalten kaum robust schaetzbar.

Beide Variablen sind in KONTROLLVARIABLEN_FORMEL/KONTROLLVARIABLEN_SPALTEN NEBEN
log_duration_seconds ZUSAMMENGEFASST und werden dadurch automatisch in DENSELBEN
sieben Bausteinen (a-g) mitgefuehrt wie die Videolaenge (dieselbe additive
Kontrollvariablen-Logik, an einer Stelle gepflegt statt fuenffach dupliziert) - selbst
nicht separat ausgegeben. ANDERS als bei der Videolaenge gibt es dafuer KEINE eigene
Sensitivitaets-Teilstichprobe (DAUER_TEILSTICHPROBEN bleibt ausschliesslich an die
Videolaenge gekoppelt) - der Vergleich "mit vs. ohne diese beiden Kontrollvariablen"
laesst sich stattdessen direkt gegen den vorherigen Lauf (nur mit Videolaengen-
Kontrolle, siehe outputs/segment_analysis/zentrale_ergebnisse.md) ablesen. Befund
(2026-09-08): keine relevante Veraenderung gegenueber der reinen Laengenkontrolle -
log_duration_seconds war bereits der dominante Kontrollfaktor.

UPLOAD-DICHTE (seit 2026-09-08, Nutzervorgabe "Bau jetzt die Upload-Dichte als
Kontrollvariable ein" - anders als age_days/category_id KEIN Test, sondern eine feste
Ergaenzung): log_upload_dichte (bericht_utils.py::berechne_upload_dichte()) misst die
Konkurrenz um Aufmerksamkeit INNERHALB des Kanals: postet ein Kanal kurz vor/nach einem
Video viele weitere Videos, teilt sich die Aufmerksamkeit der Abonnenten womoeglich
staerker auf ein einzelnes Video auf. Seit 2026-09-09 (Nutzervorgabe: "es kommt auf
Videos kurz vor und nach dem jeweiligen Video an") log1p der Anzahl ANDERER Videos
DESSELBEN Kanals (ALLE Themen, nicht nur Kriegsvideos), deren published_at innerhalb
von +/- 48 Stunden um das published_at des jeweiligen Videos liegt (statt vorher: alle
Videos derselben ZEITPERIODEN_SPALTE-Periode) - eine Periodengrenze trennte vorher
benachbarte Videos, die nur Stunden auseinander lagen, kuenstlich in unterschiedliche
Zellen. _ergaenze_upload_dichte() berechnet das auf der VOLLEN, in
lade_merged_daten()/lade_kombiniertes_modell_daten() ohnehin schon geladenen
channel_video_erfolg.csv (nicht nur auf den gemeinsam klassifizierten Kriegsvideos),
damit die Dichte die tatsaechliche Kanalaktivitaet abbildet, und wird ueber
(channel_id, video_id) auf kriegsvideos gemergt (frueher: (channel_id,
ZEITPERIODEN_SPALTE), als die Dichte noch periodenbasiert war). Ebenfalls Teil von
KONTROLLVARIABLEN_FORMEL/KONTROLLVARIABLEN_SPALTEN und damit automatisch in allen
sieben Bausteinen (a-g) mitgefuehrt. ANDERS als age_days/category_id AUCH in
frage4_kriegspraemie_medientyp_bericht.py ergaenzt (log_upload_dichte_mean je Zelle) -
Begruendung siehe dortiger Moduldocstring: die Kanalaktivitaet um ein Video herum ist
NICHT durch die dortigen Perioden-Fixed-Effects abgedeckt (die kontrollieren nur
gemeinsame Zeittrends UEBER Kanaele hinweg, nicht kanalspezifische Aktivitaet
INNERHALB einer Periode).

Schreibt {modus}praemie_kriegsvideos_bericht.csv nach outputs/segment_analysis/
(fuer MODUS="populismus" identisch zum urspruenglichen Dateinamen
populismuspraemie_kriegsvideos_bericht.csv), mit der zusaetzlichen Spalte "stichprobe".
Direkt im Ordner ausfuehren (bare sibling import von deskriptiv_aggregation.py/
bericht_utils.py), nicht als -m-Modul.
"""

import pandas as pd
import statsmodels.formula.api as smf

from youtube_code.config import OUTPUTS
from bericht_utils import dauer_teilstichprobe, berechne_upload_dichte
from deskriptiv_aggregation import lade_medientyp, lade_ideologie
from deskriptiv_plots import GRUPPE5_REIHENFOLGE

# =========================================================
# CONFIG
# =========================================================

MODUS = "populismus"      # "populismus" | "stance" (Default passend zum Dateinamen;
                          # beide Modi wurden bereits ausgefuehrt, siehe
                          # populismuspraemie_kriegsvideos_bericht.csv/
                          # stancepraemie_kriegsvideos_bericht.csv in outputs/segment_analysis/)

RESULTS_PATH = OUTPUTS / "segment_analysis"

DATEINAME_VIDEO_EBENE = {
    "populismus": "channel_video_populism.csv",
    "stance": "channel_video_position.csv",
}
PFAD_DIMENSIONEN_DATEI = RESULTS_PATH / DATEINAME_VIDEO_EBENE[MODUS]
PFAD_ERFOLG = RESULTS_PATH / "channel_video_erfolg.csv"
PFAD_AUSGABE = RESULTS_PATH / f"{MODUS}praemie_kriegsvideos_bericht.csv"

# Gesamtscore zuerst, danach die vier Einzeldimensionen (populismus, siehe
# prepare_channel_scores.py::prepare_populism_results()) bzw. die beiden
# Positionierungs-Dimensionen plus Kontrollgroesse emotion (stance, siehe
# prepare_position_results() und frage1_stance_bericht.py). emotionale_intensitaet/
# emotion sind KONTROLLGROESSEN, keine inhaltliche Positionierung/Populismus - werden
# trotzdem mitgetestet, wie in frage1_populismus_bericht.py/frage1_stance_bericht.py.
DIMENSIONEN_JE_MODUS = {
    "populismus": [
        "populismus_gesamt",
        "volkszentrismus",
        "antielitismus",
        "manichaeische_moralisierung",
        "emotionale_intensitaet",
    ],
    "stance": [
        "position_russland",
        "position_westpolitik",
        "emotion",
    ],
}
DIMENSIONEN = DIMENSIONEN_JE_MODUS[MODUS]

# Unterhalb dieser Kanalzahl (mit >= 1 klassifiziertem Kriegsvideo) wird ein
# Medientyp bzw. eine Zeitperiode aus dem jeweiligen Interaktionsmodell ausgeschlossen
# (wie frage1/frage2/frage4b).
MIN_KANAELE_JE_GRUPPE = 5

# ---------------------------------------------------------
# CONFIG: Testweise Kontrollvariablen age_days/category_id (seit 2026-09-08,
# Nutzervorgabe "Nimm age_days und category_id testweise dazu")
# ---------------------------------------------------------
# category_id (YouTubes eigene Video-Kategorie, siehe video_registry.
# category_id_lookup()) ist auf Video-, nicht auf Kanalebene definiert und kann daher
# sehr viele seltene Auspraegungen haben, die bei einer C(kategorie_gruppe)-FE zu
# instabilen/kaum schaetzbaren Dummy-Koeffizienten fuehren wuerden. Kategorien mit
# WENIGER als KATEGORIE_MIN_VIDEOS Kriegsvideos werden daher zu "Sonstige"
# zusammengefasst (siehe _gruppiere_kategorie()) - analog zum MIN_KANAELE_JE_GRUPPE-
# Muster, hier aber auf Video- statt Kanalebene, weil category_id selbst video- und
# nicht kanalspezifisch ist.
KATEGORIE_MIN_VIDEOS = 200

# ---------------------------------------------------------
# CONFIG: Baustein (d), Interaktion mit Zeitperiode
# ---------------------------------------------------------
# Spalte aus channel_video_erfolg.csv, die die Zeit relativ zu KRIEGSBEGINN
# (24.02.2022, siehe prepare_channel_scores.py) angibt: 0 = Periode des
# Kriegsbeginns, negative Werte davor, positive Werte danach.
# "rel_quartal" | "rel_monat" (beide werden von ergaenze_periodenspalten()
# bereitgestellt, siehe prepare_channel_scores.py).
ZEITPERIODEN_SPALTE = "rel_monat"

# Linke, EINSCHLIESSENDE Grenzen der Zeitperioden-Bins (in Einheiten von
# ZEITPERIODEN_SPALTE), erzeugt via erstelle_zeitperiode(). Mit dem Default [0, 4, 8]
# ergeben sich vier Perioden: "< Q0" (vor Kriegsbeginn, nur falls in den Daten
# vorhanden - Kriegsvideos koennen z.B. durch fruehe Berichterstattung ueber den
# Truppenaufmarsch auch kurz vor dem 24.02.2022 liegen), "Q0-Q3", "Q4-Q7", "Q8+".
# Frei anpassbar, je nachdem wie fein die Zeitachse aufgeloest werden soll -
# feinere Bins (mehr Grenzen) brauchen entsprechend mehr Kanaele mit klassifizierten
# Kriegsvideos pro Bin, um MIN_KANAELE_JE_GRUPPE zu erfuellen.
ZEITPERIODEN_GRENZEN = [0, 6, 18]

# ---------------------------------------------------------
# CONFIG: Baustein (c), kombiniertes Modell
# ---------------------------------------------------------
# Dimensionen, die GEMEINSAM als Regressoren in EIN Modell
# (log_views ~ KOMBI_VARIABLEN[0] + KOMBI_VARIABLEN[1] + ... + C(channel_id)) sollen -
# unabhaengig von MODUS oben, beliebig gemischt aus channel_video_populism.csv und
# channel_video_position.csv (siehe DATEINAME_JE_VARIABLE fuer die Zuordnung). Einfach
# hier die gewuenschten Spaltennamen eintragen/austauschen, z.B. um statt des
# Gesamtscores eine Einzeldimension zu testen oder position_westpolitik zu ergaenzen.
KOMBI_VARIABLEN = ["populismus_gesamt", "emotionale_intensitaet", "position_russland", "position_westpolitik"]

# Ordnet jeder in DIMENSIONEN_JE_MODUS moeglichen Dimension ihre Quelldatei zu, damit
# lade_kombiniertes_modell_daten() fuer KOMBI_VARIABLEN automatisch die richtige(n)
# Datei(en) laedt und mergt - unabhaengig davon, ob alle Variablen aus derselben Datei
# stammen oder aus beiden.
DATEINAME_JE_VARIABLE = {
    dimension: DATEINAME_VIDEO_EBENE[modus]
    for modus, dimensionen in DIMENSIONEN_JE_MODUS.items()
    for dimension in dimensionen
}

PFAD_AUSGABE_KOMBI_KORRELATION = RESULTS_PATH / "kombiniertes_modell_korrelation.csv"

# ---------------------------------------------------------
# CONFIG: Laengenbeschraenkte Sensitivitaets-Teilstichproben (Nutzervorgabe, siehe
# Moduldocstring "VIDEOLAENGE ALS KONTROLLVARIABLE UND SENSITIVITAETS-TEILSTICHPROBE")
# ---------------------------------------------------------
# True = zusaetzlich zur vollen Stichprobe ("voll") laeuft main() je
# DAUER_TEILSTICHPROBE komplett eigenstaendig durch. False = nur die volle
# Stichprobe (urspruengliches Verhalten).
DAUER_TEILSTICHPROBEN_AKTIV = True

# Dieselben festen, frei anpassbaren Minuten-Intervalle wie in
# frage4_kriegspraemie_medientyp_bericht.py (minuten_max=None -> keine Obergrenze) -
# bewusst hier separat gepflegt statt geteilt importiert (Konfigurationswerte sind in
# diesem Ordner projektweit je Skript dupliziert, z.B. MIN_KANAELE_JE_GRUPPE), damit
# beide Skripte unabhaengig voneinander angepasst werden koennen.
DAUER_TEILSTICHPROBEN = {
    "kurz_bis_10min": {"minuten_min": 0, "minuten_max": 10,
                        "label": "Kurzvideos (0-10 Minuten)"},
    "mittel_3_30min": {"minuten_min": 3, "minuten_max": 30,
                        "label": "Mittellange Videos (3-30 Minuten)"},
}

# Gemeinsamer Formel-/Spaltenbaustein fuer ALLE Kontrollvariablen (Videolaenge fest,
# age_days/category_id testweise, siehe Moduldocstring) - an EINER Stelle gepflegt,
# damit alle sieben Bausteine (a)-(g) garantiert dieselben Kontrollvariablen in
# derselben Formel-Notation verwenden. KONTROLLVARIABLEN_SPALTEN wird fuer dropna()
# gebraucht (kategorie_gruppe statt category_id - dropna() muss auf der Spalte
# laufen, die auch tatsaechlich im Modell steht).
KONTROLLVARIABLEN_FORMEL = "log_duration_seconds + age_days + C(kategorie_gruppe) + log_upload_dichte"
KONTROLLVARIABLEN_SPALTEN = ["log_duration_seconds", "age_days", "kategorie_gruppe", "log_upload_dichte"]

# ---------------------------------------------------------
# CONFIG: Baustein (g), Interaktion Populismus x Position (seit 2026-09-10,
# Nutzervorgabe "Setz Punkt 2 mit dem Interaktionsterm um", siehe Moduldocstring)
# ---------------------------------------------------------
# Jedes Paar (Positions-Dimension, Populismus-Dimension) wird als eigenes
# multiplikatives Modell log_views ~ center(position) * center(populismus) +
# Kontrollvariablen + C(channel_id) geschaetzt (interaktion_populismus_position_test()).
# populismus_gesamt statt einer der vier Einzeldimensionen, weil es der zentrale
# Populismus-Befund aus TODO 2 ist (siehe Moduldocstring) - bei Interesse an einer
# spezifischen Subdimension (z.B. antielitismus, der robusteste Einzelbefund aus TODO 2)
# hier einfach ein weiteres Paar ergaenzen.
INTERAKTIONS_PAARE_POPULISMUS_POSITION = [
    ("position_russland", "populismus_gesamt"),
    ("position_westpolitik", "populismus_gesamt"),
]


# =========================================================
# DATEN LADEN
# =========================================================

def baue_gruppe5_lokal(df):
    """Lokale Nachbildung von deskriptiv_plots.py::baue_gruppe5()/
    frage4_kriegspraemie_medientyp_bericht.py::baue_gruppe5_lokal() (siehe
    alternative-medien-ideologie-differenzierung): OERR und Traditionelles Medium
    bleiben als Ganzes, Alternatives Medium wird nach Ideologie in links/mitte/rechts
    aufgespalten (GRUPPE5_REIHENFOLGE importiert, damit alle Skripte garantiert
    dieselben Gruppen verwenden). Erwartet die Spalten "medientyp" und
    "ideologie_gruppe" bereits gemerged. Anders als die anderen Skripte wird HIER NICHT
    gefiltert (Politiker/Partei bzw. Alternative Medien ohne Ideologie-Einordnung
    bleiben mit ihrem gruppe5-Wert außerhalb von GRUPPE5_REIHENFOLGE im DataFrame) - der
    Rueckgabewert wird auch fuer Baustein (c)/(e) (gepoolt, ALLE Kanaele) verwendet, nur
    Baustein (f) iteriert anschliessend ausschliesslich ueber GRUPPE5_REIHENFOLGE und
    schliesst die uebrigen Kanaele dadurch implizit aus."""
    df = df.copy()
    ist_alt = df["medientyp"] == "Alternatives Medium"
    df["gruppe5"] = df["medientyp"]
    df.loc[ist_alt, "gruppe5"] = "Alternative Medien (" + df.loc[ist_alt, "ideologie_gruppe"].astype(str) + ")"
    return df


def _gruppiere_kategorie(df):
    """Bildet kategorie_gruppe aus category_id (siehe CONFIG-Block "Testweise
    Kontrollvariablen"): category_id-Werte mit WENIGER als KATEGORIE_MIN_VIDEOS
    Kriegsvideos in `df` werden zu "Sonstige" zusammengefasst - ohne das haette eine
    C(kategorie_gruppe)-FE sehr viele fast leere Dummy-Spalten (category_id ist video-,
    nicht kanalspezifisch, siehe Moduldocstring). NaN (category_id unbekannt) bleibt
    NaN, faellt also ueber dropna() aus den betroffenen Modellen raus, wie ueberall
    sonst in diesem Skript. category_id kommt aus channel_video_erfolg.csv als Zahl
    (CSV-Rundtrip von der TEXT-Spalte in video_registry.sqlite) - hier zuerst zu einem
    sauberen String ohne Nachkommastelle normalisiert ("25" statt "25.0"), damit die
    Modellkoeffizienten lesbar heissen (z.B. "kategorie_gruppe[25]")."""
    df = df.copy()
    kategorie_str = df["category_id"].apply(lambda x: str(int(x)) if pd.notna(x) else pd.NA)

    haeufigkeit = kategorie_str.value_counts()
    haeufige_kategorien = set(haeufigkeit[haeufigkeit >= KATEGORIE_MIN_VIDEOS].index)
    df["kategorie_gruppe"] = kategorie_str.where(kategorie_str.isin(haeufige_kategorien), "Sonstige")
    df.loc[kategorie_str.isna(), "kategorie_gruppe"] = pd.NA

    ausgeschlossen = sorted(set(haeufigkeit.index) - haeufige_kategorien)
    if ausgeschlossen:
        print(f"  [Kategoriefilter] category_id mit < {KATEGORIE_MIN_VIDEOS} Videos "
              f"-> 'Sonstige' zusammengefasst: {ausgeschlossen}")
    return df


def _ergaenze_upload_dichte(kriegsvideos, erfolg_voll):
    """Mergt log_upload_dichte (bericht_utils.py::berechne_upload_dichte(), siehe
    Moduldocstring "UPLOAD-DICHTE...") auf kriegsvideos - berechnet auf erfolg_voll
    (die VOLLE, ungefilterte channel_video_erfolg.csv, wie sie lade_merged_daten()/
    lade_kombiniertes_modell_daten() ohnehin schon laden), damit die Dichte die
    tatsaechliche Kanalaktivitaet abbildet und nicht nur die Aktivitaet unter den
    gemeinsam klassifizierten Kriegsvideos. Merge seit 2026-09-09 ueber (channel_id,
    video_id) statt (channel_id, ZEITPERIODEN_SPALTE) - die Dichte ist jetzt eine
    Video-eigene, fenster-basierte Kennzahl (siehe Moduldocstring), keine
    Periodenkennzahl mehr."""
    dichte = berechne_upload_dichte(erfolg_voll)
    return kriegsvideos.merge(
        dichte[["channel_id", "video_id", "log_upload_dichte"]],
        on=["channel_id", "video_id"], how="left")


def lade_merged_daten():
    dim = pd.read_csv(PFAD_DIMENSIONEN_DATEI)
    dim["channel_id"] = dim["channel_id"].astype(str)
    dim_spalten = ["channel_id", "video_id"] + DIMENSIONEN
    dim = dim[dim_spalten]

    erfolg = pd.read_csv(PFAD_ERFOLG)
    erfolg["channel_id"] = erfolg["channel_id"].astype(str)

    merged = dim.merge(
        erfolg[["channel_id", "channel_title", "video_id", "log_views", "ist_kriegsvideo",
                ZEITPERIODEN_SPALTE, "duration_seconds", "log_duration_seconds",
                "age_days", "category_id"]],
        on=["channel_id", "video_id"], how="inner",
    )
    print(f"[Merge][{MODUS}] Dimensions-Video-Ebene ({PFAD_DIMENSIONEN_DATEI.name}): "
          f"{dim['channel_id'].nunique()} Kanaele ({len(dim)} Videos), Erfolgs-Video-Ebene: "
          f"{erfolg['channel_id'].nunique()} Kanaele ({len(erfolg)} Videos) -> "
          f"{len(merged)} gemeinsam klassifizierte Videos ({merged['channel_id'].nunique()} Kanaele).")

    kriegsvideos = merged[merged["ist_kriegsvideo"] == 1].copy()
    print(f"[Filter] {len(kriegsvideos)} von {len(merged)} gemeinsamen Videos sind "
          f"Kriegsvideos ({kriegsvideos['channel_id'].nunique()} Kanaele).")

    med = lade_medientyp()
    kriegsvideos = kriegsvideos.merge(med[["channel_id", "medientyp"]], on="channel_id", how="left")
    kriegsvideos = _gruppiere_kategorie(kriegsvideos)
    kriegsvideos = _ergaenze_upload_dichte(kriegsvideos, erfolg)

    return kriegsvideos


def lade_kombiniertes_modell_daten(variablen):
    """Wie lade_merged_daten(), aber unabhaengig von MODUS: laedt nur die fuer
    `variablen` benoetigten Spalten, ggf. aus BEIDEN Dateien (channel_video_populism.csv
    UND channel_video_position.csv), gemergt ueber DATEINAME_JE_VARIABLE. Laedt seit
    Baustein (e)/(f) zusaetzlich ZEITPERIODEN_SPALTE (fuer die Zeitperioden-Interaktion)
    sowie Medientyp+Ideologie als gruppe5 (fuer die Aufschluesselung je Medientyp/
    Ideologie-Gruppe in Baustein (f), siehe baue_gruppe5_lokal())."""
    benoetigte_dateien = sorted({DATEINAME_JE_VARIABLE[v] for v in variablen})

    dim = None
    for dateiname in benoetigte_dateien:
        teil = pd.read_csv(RESULTS_PATH / dateiname)
        teil["channel_id"] = teil["channel_id"].astype(str)
        spalten_hier = [v for v in variablen if DATEINAME_JE_VARIABLE[v] == dateiname]
        teil = teil[["channel_id", "video_id"] + spalten_hier]
        dim = teil if dim is None else dim.merge(teil, on=["channel_id", "video_id"], how="outer")

    erfolg = pd.read_csv(PFAD_ERFOLG)
    erfolg["channel_id"] = erfolg["channel_id"].astype(str)

    merged = dim.merge(
        erfolg[["channel_id", "channel_title", "video_id", "log_views", "ist_kriegsvideo",
                ZEITPERIODEN_SPALTE, "duration_seconds", "log_duration_seconds",
                "age_days", "category_id"]],
        on=["channel_id", "video_id"], how="inner",
    )
    kriegsvideos = merged[merged["ist_kriegsvideo"] == 1].copy()
    print(f"[Merge][kombiniert] {variablen} aus {benoetigte_dateien} -> "
          f"{len(kriegsvideos)} Kriegsvideos ({kriegsvideos['channel_id'].nunique()} Kanaele).")

    med = lade_medientyp()
    kriegsvideos = kriegsvideos.merge(med[["channel_id", "medientyp"]], on="channel_id", how="left")

    ideo = lade_ideologie()
    ideo["channel_id"] = ideo["channel_id"].astype(str)
    kriegsvideos = kriegsvideos.merge(ideo[["channel_id", "ideologie_gruppe"]], on="channel_id", how="left")
    kriegsvideos = baue_gruppe5_lokal(kriegsvideos)
    kriegsvideos = _gruppiere_kategorie(kriegsvideos)
    kriegsvideos = _ergaenze_upload_dichte(kriegsvideos, erfolg)

    return kriegsvideos


# =========================================================
# BAUSTEIN (a): Gesamtmodell, gesamte Stichprobe
# =========================================================

def gesamtmodell_test(df, dimension):
    """log_views ~ dimension + Kontrollvariablen + C(channel_id), SE geclustert auf
    Kanalebene. Kontrollvariablen (siehe KONTROLLVARIABLEN_FORMEL, Moduldocstring
    "VIDEOLAENGE..." und "Testweise Kontrollvariablen") werden selbst nicht separat
    ausgegeben."""
    daten = df.dropna(subset=[dimension, "log_views"] + KONTROLLVARIABLEN_SPALTEN).copy()

    n_kanaele = daten["channel_id"].nunique()
    n_kanaele_mit_variation = (
        daten.groupby("channel_id")[dimension].nunique().gt(1).sum()
    )
    if n_kanaele < 2:
        print(f"  [Skip][{dimension}] zu wenig Kanaele (n={n_kanaele}).")
        return None

    modell = smf.ols(f"log_views ~ {dimension} + {KONTROLLVARIABLEN_FORMEL} + C(channel_id)", data=daten).fit(
        cov_type="cluster", cov_kwds={"groups": daten["channel_id"]}
    )

    return {
        "n_beobachtungen": len(daten),
        "n_kanaele": n_kanaele,
        "n_kanaele_mit_variation": int(n_kanaele_mit_variation),
        "koeffizient": modell.params[dimension],
        "se": modell.bse[dimension],
        "p": modell.pvalues[dimension],
    }


# =========================================================
# BAUSTEIN (b): Interaktion mit Medientyp (vollrangig, Heterogenitaets-F-Test)
# =========================================================

def interaktion_medientyp_test(df, dimension):
    """log_views ~ C(channel_id) + dimension:C(medientyp), vollrangige Kodierung von
    C(medientyp) innerhalb der Interaktion (siehe Moduldocstring). Gibt (je_gruppe,
    heterogenitaet, n_beobachtungen, n_kanaele) zurueck, oder None wenn nicht
    schaetzbar."""
    daten = df.dropna(subset=[dimension, "log_views", "medientyp"] + KONTROLLVARIABLEN_SPALTEN).copy()

    kanaele_je_medientyp = daten.groupby("medientyp")["channel_id"].nunique()
    gueltige_gruppen = [g for g in kanaele_je_medientyp.index
                        if kanaele_je_medientyp[g] >= MIN_KANAELE_JE_GRUPPE]
    ausgeschlossen = [g for g in kanaele_je_medientyp.index if g not in gueltige_gruppen]
    if ausgeschlossen:
        print(f"  [Gruppenfilter][{dimension}] Ausgeschlossen (< {MIN_KANAELE_JE_GRUPPE} "
              f"Kanaele): {ausgeschlossen}")
    if len(gueltige_gruppen) < 2:
        print(f"  [Skip][{dimension}] zu wenig Medientypen mit >= "
              f"{MIN_KANAELE_JE_GRUPPE} Kanaelen ({gueltige_gruppen}).")
        return None

    daten = daten[daten["medientyp"].isin(gueltige_gruppen)]
    daten["medientyp"] = pd.Categorical(daten["medientyp"], categories=gueltige_gruppen)

    n_kanaele = daten["channel_id"].nunique()
    if n_kanaele < 2:
        print(f"  [Skip][{dimension}] zu wenig Kanaele (n={n_kanaele}) nach Gruppenfilter.")
        return None

    modell = smf.ols(f"log_views ~ C(channel_id) + {KONTROLLVARIABLEN_FORMEL} + {dimension}:C(medientyp)",
                      data=daten).fit(
        cov_type="cluster", cov_kwds={"groups": daten["channel_id"]}
    )

    interaktions_terme = [p for p in modell.params.index if p.startswith(f"{dimension}:C(medientyp)")]
    if not interaktions_terme:
        print(f"  [Skip][{dimension}] keine Interaktionsterme im Modell (zu wenig "
              f"Variation innerhalb Kanaelen).")
        return None

    # Vollrangige Kodierung (kein dimension-Haupteffekt außerhalb der Interaktion,
    # kein C(medientyp)-Haupteffekt) -> patsy nennt die Terme "...[Kategorie]" statt
    # "...[T.Kategorie]" (Treatment-Kodierung mit Referenzgruppe), da hier keine
    # Referenzgruppe existiert - jede Kategorie bekommt einen eigenen Koeffizienten.
    je_gruppe = pd.DataFrame([{
        "medientyp": term.split("[")[-1].rstrip("]"),
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
# BAUSTEIN (d): Interaktion mit Zeitperiode (vollrangig, Heterogenitaets-F-Test)
# =========================================================

def _zeitperioden_labels(grenzen):
    """Erzeugt die chronologisch geordneten Bin-Labels zu ZEITPERIODEN_GRENZEN, z.B.
    [0, 4, 8] -> ["< Q0", "Q0-Q3", "Q4-Q7", "Q8+"]."""
    grenzen = sorted(grenzen)
    labels = [f"< Q{grenzen[0]}"]
    for unten, oben_exklusiv in zip(grenzen, grenzen[1:]):
        oben = oben_exklusiv - 1
        labels.append(f"Q{unten}-Q{oben}" if oben > unten else f"Q{unten}")
    labels.append(f"Q{grenzen[-1]}+")
    return labels


def erstelle_zeitperiode(werte, grenzen):
    """Bildet aus einer numerischen Zeitspalte (ZEITPERIODEN_SPALTE, z.B. rel_quartal)
    kategoriale Zeitperioden-Bins gemaess ZEITPERIODEN_GRENZEN (siehe Moduldocstring,
    Baustein (d)). Grenzen sind linke, einschliessende Bin-Grenzen - die erste Periode
    deckt alles davor ab (-unendlich bis zur ersten Grenze), die letzte alles danach
    (letzte Grenze bis +unendlich). Gibt eine geordnete kategoriale Series zurueck."""
    grenzen = sorted(grenzen)
    bins = [-float("inf")] + grenzen + [float("inf")]
    labels = _zeitperioden_labels(grenzen)
    return pd.cut(werte, bins=bins, labels=labels, right=False, ordered=True)


def interaktion_zeitperiode_test(df, dimension):
    """log_views ~ C(channel_id) + dimension:C(zeitperiode), vollrangige Kodierung von
    C(zeitperiode) innerhalb der Interaktion - strukturell identisch zu
    interaktion_medientyp_test(), nur mit den ZEITPERIODEN_GRENZEN-Bins aus
    ZEITPERIODEN_SPALTE statt Medientyp als Gruppierung (siehe Moduldocstring,
    Baustein (d)). Gibt (je_periode, heterogenitaet, n_beobachtungen, n_kanaele)
    zurueck, oder None wenn nicht schaetzbar."""
    daten = df.dropna(subset=[dimension, "log_views", ZEITPERIODEN_SPALTE] + KONTROLLVARIABLEN_SPALTEN).copy()
    daten["zeitperiode"] = erstelle_zeitperiode(daten[ZEITPERIODEN_SPALTE], ZEITPERIODEN_GRENZEN)

    alle_perioden = _zeitperioden_labels(ZEITPERIODEN_GRENZEN)
    kanaele_je_periode = daten.groupby("zeitperiode", observed=True)["channel_id"].nunique()
    gueltige_perioden = [p for p in alle_perioden
                         if kanaele_je_periode.get(p, 0) >= MIN_KANAELE_JE_GRUPPE]
    ausgeschlossen = [p for p in alle_perioden if p not in gueltige_perioden]
    if ausgeschlossen:
        print(f"  [Gruppenfilter][{dimension}] Ausgeschlossen (< {MIN_KANAELE_JE_GRUPPE} "
              f"Kanaele oder keine Beobachtungen): {ausgeschlossen}")
    if len(gueltige_perioden) < 2:
        print(f"  [Skip][{dimension}] zu wenig Zeitperioden mit >= "
              f"{MIN_KANAELE_JE_GRUPPE} Kanaelen ({gueltige_perioden}).")
        return None

    daten = daten[daten["zeitperiode"].isin(gueltige_perioden)]
    daten["zeitperiode"] = pd.Categorical(daten["zeitperiode"], categories=gueltige_perioden)

    n_kanaele = daten["channel_id"].nunique()
    if n_kanaele < 2:
        print(f"  [Skip][{dimension}] zu wenig Kanaele (n={n_kanaele}) nach Gruppenfilter.")
        return None

    modell = smf.ols(f"log_views ~ C(channel_id) + {KONTROLLVARIABLEN_FORMEL} + {dimension}:C(zeitperiode)",
                      data=daten).fit(
        cov_type="cluster", cov_kwds={"groups": daten["channel_id"]}
    )

    interaktions_terme = [p for p in modell.params.index if p.startswith(f"{dimension}:C(zeitperiode)")]
    if not interaktions_terme:
        print(f"  [Skip][{dimension}] keine Interaktionsterme im Modell (zu wenig "
              f"Variation innerhalb Kanaelen).")
        return None

    je_periode = pd.DataFrame([{
        "zeitperiode": term.split("[")[-1].rstrip("]"),
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
        "je_periode": je_periode,
        "heterogenitaet": heterogenitaet,
        "n_beobachtungen": len(daten),
        "n_kanaele": n_kanaele,
    }


# =========================================================
# BAUSTEIN (c): Kombiniertes Modell (mehrere Dimensionen gleichzeitig)
# =========================================================

def kombiniertes_modell_test(df, variablen):
    """log_views ~ variablen[0] + variablen[1] + ... + Kontrollvariablen + C(channel_id),
    SE geclustert auf Kanalebene. Alle `variablen` gleichzeitig als Regressoren -> jeder
    Koeffizient ist der Effekt dieser Dimension, HALTEND fuer die anderen KOMBI_VARIABLEN
    UND die Kontrollvariablen (KONTROLLVARIABLEN_FORMEL, siehe Moduldocstring
    "VIDEOLAENGE..."/"Testweise Kontrollvariablen", selbst nicht separat ausgegeben)."""
    daten = df.dropna(subset=list(variablen) + ["log_views"] + KONTROLLVARIABLEN_SPALTEN).copy()

    n_kanaele = daten["channel_id"].nunique()
    if n_kanaele < 2:
        print(f"  [Skip][kombiniert] zu wenig Kanaele (n={n_kanaele}).")
        return None

    formel = "log_views ~ " + " + ".join(variablen) + f" + {KONTROLLVARIABLEN_FORMEL} + C(channel_id)"
    modell = smf.ols(formel, data=daten).fit(
        cov_type="cluster", cov_kwds={"groups": daten["channel_id"]}
    )

    return [{
        "dimension": var, "baustein": "kombiniertes_modell", "gruppe": "alle",
        "koeffizient": modell.params[var], "se": modell.bse[var], "p": modell.pvalues[var],
        "n_beobachtungen": len(daten), "n_kanaele": n_kanaele,
    } for var in variablen]


def kombiniertes_modell_korrelation(df, variablen):
    """Paarweise Pearson-Korrelationen zwischen den KOMBI_VARIABLEN, auf exakt derselben
    Stichprobe wie kombiniertes_modell_test() (dropna auf alle variablen + log_views +
    KONTROLLVARIABLEN_SPALTEN) - zeigt, wie stark die gleichzeitig als Regressoren
    eingesetzten Dimensionen miteinander zusammenhaengen (Multikollinearitaets-Check:
    eine hohe Korrelation macht die einzelnen Koeffizienten aus
    kombiniertes_modell_test() schwerer interpretierbar/instabiler)."""
    daten = df.dropna(subset=list(variablen) + ["log_views"] + KONTROLLVARIABLEN_SPALTEN).copy()

    zeilen = []
    for i, var1 in enumerate(variablen):
        for var2 in variablen[i + 1:]:
            paar = daten[[var1, var2]].dropna()
            zeilen.append({
                "variable_1": var1,
                "variable_2": var2,
                "korrelation": paar[var1].corr(paar[var2]),
                "n": len(paar),
            })
    return pd.DataFrame(zeilen)


# =========================================================
# BAUSTEIN (e)/(f): Kombiniertes Modell x Zeitperiode (ggf. je gruppe5)
# =========================================================

def kombiniertes_modell_zeitperiode_test(df, variablen, bezeichnung="alle"):
    """log_views ~ C(channel_id) + Kontrollvariablen + variablen[0]:C(zeitperiode) +
    variablen[1]:C(zeitperiode) + ... , SE geclustert auf Kanalebene. Wie
    kombiniertes_modell_test(), aber jede Variable bekommt vollrangige,
    periodenspezifische Koeffizienten statt eines einzigen Effekts ueber den gesamten
    Zeitraum (siehe Moduldocstring, Baustein (e)); Kontrollvariablen wie ueberall in
    diesem Skript (KONTROLLVARIABLEN_FORMEL). `bezeichnung` ist nur fuer Log-Ausgaben
    (z.B. der gruppe5-Name bei Baustein (f)). Gibt {variable: {"je_periode": DataFrame,
    "heterogenitaet": dict|None}}, n_beobachtungen, n_kanaele zurueck, oder None wenn
    nicht schaetzbar."""
    daten = df.dropna(
        subset=list(variablen) + ["log_views", ZEITPERIODEN_SPALTE] + KONTROLLVARIABLEN_SPALTEN).copy()
    daten["zeitperiode"] = erstelle_zeitperiode(daten[ZEITPERIODEN_SPALTE], ZEITPERIODEN_GRENZEN)

    alle_perioden = _zeitperioden_labels(ZEITPERIODEN_GRENZEN)
    kanaele_je_periode = daten.groupby("zeitperiode", observed=True)["channel_id"].nunique()
    gueltige_perioden = [p for p in alle_perioden
                         if kanaele_je_periode.get(p, 0) >= MIN_KANAELE_JE_GRUPPE]
    ausgeschlossen = [p for p in alle_perioden if p not in gueltige_perioden]
    if ausgeschlossen:
        print(f"  [Gruppenfilter][{bezeichnung}] Ausgeschlossen (< {MIN_KANAELE_JE_GRUPPE} "
              f"Kanaele oder keine Beobachtungen): {ausgeschlossen}")
    if len(gueltige_perioden) < 2:
        print(f"  [Skip][{bezeichnung}] zu wenig Zeitperioden mit >= "
              f"{MIN_KANAELE_JE_GRUPPE} Kanaelen ({gueltige_perioden}).")
        return None

    daten = daten[daten["zeitperiode"].isin(gueltige_perioden)]
    daten["zeitperiode"] = pd.Categorical(daten["zeitperiode"], categories=gueltige_perioden)

    n_kanaele = daten["channel_id"].nunique()
    if n_kanaele < 2:
        print(f"  [Skip][{bezeichnung}] zu wenig Kanaele (n={n_kanaele}) nach Gruppenfilter.")
        return None

    formel = (f"log_views ~ C(channel_id) + {KONTROLLVARIABLEN_FORMEL} + "
              + " + ".join(f"{v}:C(zeitperiode)" for v in variablen))
    modell = smf.ols(formel, data=daten).fit(
        cov_type="cluster", cov_kwds={"groups": daten["channel_id"]}
    )

    ergebnis_je_variable = {}
    for var in variablen:
        interaktions_terme = [p for p in modell.params.index if p.startswith(f"{var}:C(zeitperiode)")]
        if not interaktions_terme:
            print(f"  [Skip][{bezeichnung}][{var}] keine Interaktionsterme im Modell "
                  f"(zu wenig Variation innerhalb Kanaelen).")
            continue

        je_periode = pd.DataFrame([{
            "zeitperiode": term.split("[")[-1].rstrip("]"),
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

        ergebnis_je_variable[var] = {"je_periode": je_periode, "heterogenitaet": heterogenitaet}

    if not ergebnis_je_variable:
        return None

    return {
        "je_variable": ergebnis_je_variable,
        "n_beobachtungen": len(daten),
        "n_kanaele": n_kanaele,
    }


def _sammle_kombi_zeitperiode_zeilen(ergebnis, gruppe5, zeilen):
    """Druckt und sammelt die Ergebnisse von kombiniertes_modell_zeitperiode_test() in
    `zeilen` (main()::zeilen, gemeinsame Ausgabetabelle). `gruppe5` ist "alle" fuer den
    gepoolten Baustein (e) bzw. der gruppe5-Name fuer Baustein (f) - steuert nur die
    baustein-Bezeichnung in der Ausgabe (kombiniert_zeitperiode vs.
    kombiniert_zeitperiode_gruppe5), damit beide Bausteine in derselben CSV
    unterscheidbar bleiben."""
    baustein = "kombiniert_zeitperiode" if gruppe5 == "alle" else "kombiniert_zeitperiode_gruppe5"
    baustein_heterogenitaet = f"heterogenitaet_{baustein}_ftest"

    for var, teilergebnis in ergebnis["je_variable"].items():
        print(f"  [{var}]")
        for _, zeile in teilergebnis["je_periode"].iterrows():
            sig = "signifikant" if zeile["p"] < 0.05 else "n.s."
            print(f"    {zeile['zeitperiode']}: koeffizient={zeile['koeffizient']:+.4f} "
                  f"(se={zeile['se']:.4f}, p={zeile['p']:.4f}, {sig})")
            zeilen.append({
                "dimension": var, "baustein": baustein, "gruppe": gruppe5,
                "gruppe_zeitperiode": zeile["zeitperiode"], "koeffizient": zeile["koeffizient"],
                "se": zeile["se"], "p": zeile["p"],
                "n_beobachtungen": ergebnis["n_beobachtungen"], "n_kanaele": ergebnis["n_kanaele"],
            })
        if teilergebnis["heterogenitaet"]:
            h = teilergebnis["heterogenitaet"]
            print(f"    [Heterogenitaet] F({h['df_num']}, {h['df_denom']}) = "
                  f"{h['f_stat']:.3f}, p = {h['p']:.4f}")
            zeilen.append({
                "dimension": var, "baustein": baustein_heterogenitaet, "gruppe": gruppe5,
                "gruppe_zeitperiode": None, "koeffizient": None, "se": None, "p": h["p"],
                "f_stat": h["f_stat"], "df_num": h["df_num"], "df_denom": h["df_denom"],
                "n_beobachtungen": ergebnis["n_beobachtungen"], "n_kanaele": ergebnis["n_kanaele"],
            })


# =========================================================
# BAUSTEIN (g): Interaktion Populismus x Position (verstaerkt Populismus die
# Positionspraemie bzw. Position die Populismuspraemie?)
# =========================================================

def interaktion_populismus_position_test(df, position_var, populismus_var):
    """log_views ~ center(position_var) * center(populismus_var) + Kontrollvariablen +
    C(channel_id), SE geclustert auf Kanalebene (siehe Moduldocstring, Baustein (g)).
    Zentrierung (patsy center()) macht die beiden Haupteffekt-Koeffizienten direkt
    interpretierbar ("position_haupteffekt" = Effekt von position_var BEIM
    Durchschnittswert von populismus_var in dieser Stichprobe, und symmetrisch fuer
    "populismus_haupteffekt") - der Interaktionskoeffizient "interaktion" selbst ist von
    der Zentrierung unberuehrt. Ein signifikanter Interaktionskoeffizient beantwortet die
    Kernfrage direkt: haengt die Staerke der Positionspraemie (TODO 3) vom
    Populismus-Niveau desselben Videos ab (bzw. umgekehrt die Staerke der
    Populismuspraemie, TODO 2, von dessen Position)? Gibt {"je_term": {...},
    "n_beobachtungen", "n_kanaele"} zurueck, oder None wenn nicht schaetzbar."""
    daten = df.dropna(subset=[position_var, populismus_var, "log_views"] + KONTROLLVARIABLEN_SPALTEN).copy()

    n_kanaele = daten["channel_id"].nunique()
    if n_kanaele < 2:
        print(f"  [Skip][{position_var} x {populismus_var}] zu wenig Kanaele (n={n_kanaele}).")
        return None

    formel = (f"log_views ~ center({position_var}) * center({populismus_var}) + "
              f"{KONTROLLVARIABLEN_FORMEL} + C(channel_id)")
    modell = smf.ols(formel, data=daten).fit(
        cov_type="cluster", cov_kwds={"groups": daten["channel_id"]}
    )

    term_position = f"center({position_var})"
    term_populismus = f"center({populismus_var})"
    term_interaktion = f"{term_position}:{term_populismus}"
    if term_interaktion not in modell.params.index:
        print(f"  [Skip][{position_var} x {populismus_var}] Interaktionsterm nicht im "
              f"Modell (zu wenig gemeinsame Variation innerhalb der Kanaele).")
        return None

    je_term = {}
    for bezeichnung, term in [
        ("position_haupteffekt", term_position),
        ("populismus_haupteffekt", term_populismus),
        ("interaktion", term_interaktion),
    ]:
        je_term[bezeichnung] = {
            "koeffizient": modell.params[term],
            "se": modell.bse[term],
            "p": modell.pvalues[term],
        }

    return {
        "je_term": je_term,
        "n_beobachtungen": len(daten),
        "n_kanaele": n_kanaele,
    }


# =========================================================
# EIN ANALYSELAUF (volle Stichprobe ODER eine DAUER_TEILSTICHPROBE)
# =========================================================

def fuehre_analyse_aus(df, kombi_df, stichprobe_id, stichprobe_label):
    """Fuehrt ALLE Bausteine (a/b/d auf df, c/e/f auf kombi_df) fuer EINE Stichprobe
    durch - "voll" (keine Laengenbeschraenkung) oder eine DAUER_TEILSTICHPROBEN-Kennung
    (siehe Moduldocstring "VIDEOLAENGE..."). Reiner Funktionsumzug des frueheren
    main()-Koerpers, unveraendert bis auf die stichprobe-Markierung am Ende. Gibt
    (zeilen, korrelation_zeilen) zurueck - main() sammelt beide ueber alle Stichproben
    und schreibt am Ende je EINE gemeinsame CSV."""
    zeilen = []

    print("\n" + "=" * 70)
    print(f"[{stichprobe_label}] BAUSTEIN (a): Gesamtmodell ({MODUS}, gesamte Stichprobe, gesamter Zeitraum)")
    print("=" * 70)
    for dimension in DIMENSIONEN:
        ergebnis = gesamtmodell_test(df, dimension)
        if ergebnis is None:
            continue
        sig = "signifikant" if ergebnis["p"] < 0.05 else "nicht signifikant"
        print(f"  [{dimension}] koeffizient={ergebnis['koeffizient']:+.4f} "
              f"(se={ergebnis['se']:.4f}, p={ergebnis['p']:.4f}, {sig}), "
              f"n={ergebnis['n_beobachtungen']} Videos, {ergebnis['n_kanaele']} Kanaele "
              f"({ergebnis['n_kanaele_mit_variation']} mit Variation in der Dimension).")
        zeilen.append({"dimension": dimension, "baustein": "gesamtmodell", "gruppe": "alle", **ergebnis})

    print("\n" + "=" * 70)
    print(f"[{stichprobe_label}] BAUSTEIN (b): Interaktion {MODUS} x Medientyp")
    print("=" * 70)
    for dimension in DIMENSIONEN:
        ergebnis = interaktion_medientyp_test(df, dimension)
        if ergebnis is None:
            continue
        print(f"  [{dimension}]")
        for _, zeile in ergebnis["je_gruppe"].iterrows():
            sig = "signifikant" if zeile["p"] < 0.05 else "n.s."
            print(f"    {zeile['medientyp']}: koeffizient={zeile['koeffizient']:+.4f} "
                  f"(se={zeile['se']:.4f}, p={zeile['p']:.4f}, {sig})")
            zeilen.append({
                "dimension": dimension, "baustein": "interaktion_medientyp",
                "gruppe": zeile["medientyp"], "koeffizient": zeile["koeffizient"],
                "se": zeile["se"], "p": zeile["p"],
                "n_beobachtungen": ergebnis["n_beobachtungen"], "n_kanaele": ergebnis["n_kanaele"],
            })
        if ergebnis["heterogenitaet"]:
            h = ergebnis["heterogenitaet"]
            print(f"    [Heterogenitaet] F({h['df_num']}, {h['df_denom']}) = "
                  f"{h['f_stat']:.3f}, p = {h['p']:.4f}")
            zeilen.append({
                "dimension": dimension, "baustein": "heterogenitaet_ftest", "gruppe": "alle",
                "koeffizient": None, "se": None, "p": h["p"],
                "f_stat": h["f_stat"], "df_num": h["df_num"], "df_denom": h["df_denom"],
                "n_beobachtungen": ergebnis["n_beobachtungen"], "n_kanaele": ergebnis["n_kanaele"],
            })

    print("\n" + "=" * 70)
    print(f"[{stichprobe_label}] BAUSTEIN (d): Interaktion {MODUS} x Zeitperiode "
          f"({ZEITPERIODEN_SPALTE}, Grenzen {ZEITPERIODEN_GRENZEN})")
    print("=" * 70)
    for dimension in DIMENSIONEN:
        ergebnis = interaktion_zeitperiode_test(df, dimension)
        if ergebnis is None:
            continue
        print(f"  [{dimension}]")
        for _, zeile in ergebnis["je_periode"].iterrows():
            sig = "signifikant" if zeile["p"] < 0.05 else "n.s."
            print(f"    {zeile['zeitperiode']}: koeffizient={zeile['koeffizient']:+.4f} "
                  f"(se={zeile['se']:.4f}, p={zeile['p']:.4f}, {sig})")
            zeilen.append({
                "dimension": dimension, "baustein": "interaktion_zeitperiode",
                "gruppe": zeile["zeitperiode"], "koeffizient": zeile["koeffizient"],
                "se": zeile["se"], "p": zeile["p"],
                "n_beobachtungen": ergebnis["n_beobachtungen"], "n_kanaele": ergebnis["n_kanaele"],
            })
        if ergebnis["heterogenitaet"]:
            h = ergebnis["heterogenitaet"]
            print(f"    [Heterogenitaet] F({h['df_num']}, {h['df_denom']}) = "
                  f"{h['f_stat']:.3f}, p = {h['p']:.4f}")
            zeilen.append({
                "dimension": dimension, "baustein": "heterogenitaet_zeitperiode_ftest", "gruppe": "alle",
                "koeffizient": None, "se": None, "p": h["p"],
                "f_stat": h["f_stat"], "df_num": h["df_num"], "df_denom": h["df_denom"],
                "n_beobachtungen": ergebnis["n_beobachtungen"], "n_kanaele": ergebnis["n_kanaele"],
            })

    print("\n" + "=" * 70)
    print(f"[{stichprobe_label}] BAUSTEIN (c): Kombiniertes Modell ({' + '.join(KOMBI_VARIABLEN)})")
    print("=" * 70)
    korrelation_zeilen = []
    if kombi_df["channel_id"].nunique() < 2:
        print("  [Skip] weniger als 2 Kanaele mit klassifizierten Kriegsvideos.")
    else:
        kombi_zeilen = kombiniertes_modell_test(kombi_df, KOMBI_VARIABLEN)
        if kombi_zeilen:
            for zeile in kombi_zeilen:
                sig = "signifikant" if zeile["p"] < 0.05 else "nicht signifikant"
                print(f"  [{zeile['dimension']}] koeffizient={zeile['koeffizient']:+.4f} "
                      f"(se={zeile['se']:.4f}, p={zeile['p']:.4f}, {sig})")
            zeilen.extend(kombi_zeilen)

        korrelation_df = kombiniertes_modell_korrelation(kombi_df, KOMBI_VARIABLEN)
        print("  [Korrelation der KOMBI_VARIABLEN]")
        for _, zeile in korrelation_df.iterrows():
            print(f"    {zeile['variable_1']} <-> {zeile['variable_2']}: "
                  f"r={zeile['korrelation']:+.4f} (n={zeile['n']})")
        korrelation_zeilen = korrelation_df.to_dict("records")

        print("\n" + "=" * 70)
        print(f"[{stichprobe_label}] BAUSTEIN (e): Kombiniertes Modell x Zeitperiode "
              f"({ZEITPERIODEN_SPALTE}, Grenzen {ZEITPERIODEN_GRENZEN}, gepoolt ueber alle Kanaele)")
        print("=" * 70)
        ergebnis_e = kombiniertes_modell_zeitperiode_test(kombi_df, KOMBI_VARIABLEN, bezeichnung="alle")
        if ergebnis_e:
            _sammle_kombi_zeitperiode_zeilen(ergebnis_e, "alle", zeilen)

        print("\n" + "=" * 70)
        print(f"[{stichprobe_label}] BAUSTEIN (f): Kombiniertes Modell x Zeitperiode je "
              f"Medientyp/Ideologie-Gruppe (gruppe5)")
        print("=" * 70)
        kanaele_je_gruppe5 = kombi_df.groupby("gruppe5")["channel_id"].nunique()
        for gruppe5 in GRUPPE5_REIHENFOLGE:
            if kanaele_je_gruppe5.get(gruppe5, 0) < MIN_KANAELE_JE_GRUPPE:
                print(f"  [Skip][{gruppe5}] < {MIN_KANAELE_JE_GRUPPE} Kanaele mit "
                      f"klassifiziertem Kriegsvideo (n={kanaele_je_gruppe5.get(gruppe5, 0)}).")
                continue
            print(f"  --- {gruppe5} ---")
            gruppe5_df = kombi_df[kombi_df["gruppe5"] == gruppe5]
            ergebnis_f = kombiniertes_modell_zeitperiode_test(gruppe5_df, KOMBI_VARIABLEN, bezeichnung=gruppe5)
            if ergebnis_f:
                _sammle_kombi_zeitperiode_zeilen(ergebnis_f, gruppe5, zeilen)

        print("\n" + "=" * 70)
        print(f"[{stichprobe_label}] BAUSTEIN (g): Interaktion Populismus x Position "
              f"(verstaerkt Populismus die Positionspraemie?)")
        print("=" * 70)
        for position_var, populismus_var in INTERAKTIONS_PAARE_POPULISMUS_POSITION:
            ergebnis_g = interaktion_populismus_position_test(kombi_df, position_var, populismus_var)
            if ergebnis_g is None:
                continue
            print(f"  [{position_var} x {populismus_var}]")
            for term_bezeichnung, werte in ergebnis_g["je_term"].items():
                sig = "signifikant" if werte["p"] < 0.05 else "n.s."
                print(f"    {term_bezeichnung}: koeffizient={werte['koeffizient']:+.4f} "
                      f"(se={werte['se']:.4f}, p={werte['p']:.4f}, {sig})")
                zeilen.append({
                    "dimension": f"{position_var}_x_{populismus_var}",
                    "baustein": "interaktion_populismus_position", "gruppe": "alle",
                    "term": term_bezeichnung, "koeffizient": werte["koeffizient"],
                    "se": werte["se"], "p": werte["p"],
                    "n_beobachtungen": ergebnis_g["n_beobachtungen"], "n_kanaele": ergebnis_g["n_kanaele"],
                })

    for zeile in zeilen:
        zeile["stichprobe"] = stichprobe_id
    for zeile in korrelation_zeilen:
        zeile["stichprobe"] = stichprobe_id
    return zeilen, korrelation_zeilen


# =========================================================
# MAIN
# =========================================================

def main():
    df_basis = lade_merged_daten()
    if df_basis["channel_id"].nunique() < 2:
        raise ValueError("Weniger als 2 Kanaele mit klassifizierten Kriegsvideos -> "
                          "Kanal-FE nicht sinnvoll schaetzbar.")
    kombi_df_basis = lade_kombiniertes_modell_daten(KOMBI_VARIABLEN)

    stichproben = [("voll", "Volle Stichprobe (keine Laengenbeschraenkung)", None)]
    if DAUER_TEILSTICHPROBEN_AKTIV:
        print("\n[Dauer-Teilstichproben] Zusaetzlich zur vollen Stichprobe laufen alle "
              "Bausteine mit folgenden Laengenbeschraenkungen (siehe DAUER_TEILSTICHPROBEN):")
        for st_id, cfg in DAUER_TEILSTICHPROBEN.items():
            obergrenze = cfg["minuten_max"] if cfg["minuten_max"] is not None else "unbegrenzt"
            print(f"  {st_id} ({cfg['minuten_min']}-{obergrenze} Min): {cfg['label']}")
        stichproben += [(st_id, st_cfg["label"], st_cfg) for st_id, st_cfg in DAUER_TEILSTICHPROBEN.items()]

    alle_zeilen = []
    alle_korrelation_zeilen = []
    for st_id, st_label, st_cfg in stichproben:
        if st_cfg is None:
            df_lauf, kombi_df_lauf = df_basis, kombi_df_basis
        else:
            df_lauf = dauer_teilstichprobe(df_basis, st_cfg["minuten_min"], st_cfg["minuten_max"])
            kombi_df_lauf = dauer_teilstichprobe(kombi_df_basis, st_cfg["minuten_min"], st_cfg["minuten_max"])
        zeilen, korrelation_zeilen = fuehre_analyse_aus(df_lauf, kombi_df_lauf, st_id, st_label)
        alle_zeilen += zeilen
        alle_korrelation_zeilen += korrelation_zeilen

    ergebnis_df = pd.DataFrame(alle_zeilen)
    ergebnis_df.to_csv(PFAD_AUSGABE, index=False, encoding="utf-8")
    print(f"\n[Ausgabe] {len(ergebnis_df)} Zeilen aus {len(stichproben)} Stichproben -> {PFAD_AUSGABE}")

    korrelation_df = pd.DataFrame(alle_korrelation_zeilen)
    korrelation_df.to_csv(PFAD_AUSGABE_KOMBI_KORRELATION, index=False, encoding="utf-8")
    print(f"[Ausgabe] {len(korrelation_df)} Zeilen -> {PFAD_AUSGABE_KOMBI_KORRELATION}")


if __name__ == "__main__":
    main()

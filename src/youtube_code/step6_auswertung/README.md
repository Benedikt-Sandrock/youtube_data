   # Schritt 6 — Auswertung von Transkripten

Aggregiert und analysiert die LLM-Klassifikationsergebnisse aus Schritt 5
(`COMPLETE_PROCESS.md` Schritt 6). Baut auf dem Output von
`step5_segment_analysis/download_segments_simple.py` auf; geteilt wird nur
`outputs/segment_analysis/` als Lese-/Schreibort für abgeleitete
Zwischen- und Endergebnisse.

Diese Dateien lagen bis zur Aufräumarbeit im Zuge der Schritt-5-Bereinigung
noch in `step5_segment_analysis/` (siehe dortige README-Historie); der
Ordner hier fasst sie unter Schritt 6 zusammen, wie in `COMPLETE_PROCESS.md`
vorgesehen.

## Ablauf (0–8)

```
youtube_code/step6_auswertung/
    prepare_channel_scores.py            0: Segment- -> Video- -> Kanal x Periode
    frage1_stichprobe.py                 0b: Kanal-Whitelist + Methodik-Dokumentation
                                              (Forschungsfrage 1, siehe unten)
    prepare_success_metrics.py           0c: Video-Erfolgsmetriken (Views/Engagement)
                                              -> Kanal x Periode (Forschungsfragen 2-4),
                                              inkl. separater Kriegsvideo-Zeitreihe fuer
                                              Frage 4
    deskriptiv_aggregation.py            1: Zeitreihen laden, Baseline-Index bilden
    deskriptiv_plots.py                  2a: Zeitverlaufsplots
    frage2_sensitivitaet_plots.py        2a-Erweiterung: Sensitivitaetsplots zu Frage 2
                                              (Aggregationsebene x Metrik x Ausgangsbasis)
    fe_signifikanz_test.py               2b: FE-Regression + Robustheitschecks
    geglaettete_kurve.py                 2c: LOWESS-Kurve + Cluster-Bootstrap-CI
    bericht_utils.py                     gemeinsame Regressions-Bausteine
                                              (post_dummy_test/interaktions_test/
                                              dauer_teilstichprobe/
                                              berechne_upload_dichte [Video-eigen,
                                              48h-Fenster]/berechne_upload_dichte_
                                              periode [Kanal x Periode, fuer
                                              aggregierte Beobachtungseinheiten])
    frage1_populismus_bericht.py         5: Konsolidierter Vorkrieg/Nachkrieg-Bericht
                                              (Forschungsfrage 1)
    frage1_stance_bericht.py             5b: Dasselbe Verfahren fuer die Haltung
                                              gegenueber Russland/westlicher
                                              Ukraine-Politik (kein Teil der vier
                                              nummerierten Forschungsfragen, aber
                                              dieselbe Vorkriegs/Nachkriegs-Anlage)
    frage2_erfolg_bericht.py             6: Kanalerfolg vor/nach Kriegsbeginn
                                              (Forschungsfrage 2)
    frage3_populismus_erfolg_bericht.py  7: Populismus x Erfolg (Forschungsfrage 3)
    
    frage4_kriegsvideos_erfolg_bericht.py 8: Kriegs- vs. sonstige Videos
                                              (Forschungsfrage 4)
    frage4_kriegspraemie_medientyp_bericht.py 8b: Kriegspraemie x Medientyp
                                              (Forschungsfrage 4, Erweiterung)
    frage4_kriegspraemie_relative_views_plots.py 8c: relative Views (Index)
                                              statt Regression, deskriptiv
    frage4_kriegspraemie_marktanteil_plots.py 8d: Marktanteil je Gruppe5
                                              (Aufgaben.md TODO 1, Zusatzfrage)
    frage4_kriegspraemie_marktanteil_phasen_bericht.py 8e: Marktanteil je
                                              Gruppe5, phasenweise Tabelle statt
                                              Zeitreihe, 3 Umfaenge + absolute
                                              Gesamtnachfrage (Nachfrageperspektive)
    export_stata_rohdaten.py             S: Rohdatensatz fuer Stata (videos_roh.dta,
                                              kanaele_roh.dta) nach
                                              docs/codebuch_rohdatensatz.md
    kanaluebersicht_marktanteil_bericht.py 8f: Kanal-Ebenen-Zerlegung von 8e -
                                              Konzentrationscheck (treiben wenige
                                              grosse Kanaele einen Gruppentrend?)
    marktanteil_themen_plots.py          8g: Marktanteil je (konfigurierbarer)
                                              Anzeigegruppe, ueber alle 5 Themen +
                                              nicht-exklusive "alle politischen
                                              Videos" (Erweiterung von 8d)
    marktanteil_themen_treiber_plots.py  8h: Zerlegung von 8g in die beiden rohen
                                              Treiber Anzahl Videos x Views/Video
                                              (Shift-Share-Zerlegung, monatlich,
                                              rohe statt normierte Werte)
    marktanteil_rohdaten_plots.py        8i: Marktanteile aus dem Stata-Rohdatensatz
                                              (Medientyp x Ideologie, Populismus-
                                              Tertile; politische vs. Kriegsvideos)
    populismuspraemie_kriegsvideos_bericht.py 9: Populismus-/Haltungspraemie bei
                                              Kriegsvideos (.claude/Aufgaben.md TODO 2,
                                              MODUS = "populismus" | "stance")
    select_political_nonwar_targets.py   9b: Zielauswahl-Vorbereitung fuer den
                                              Gegentest "gilt die Praemie aus
                                              Schritt 9 auch fuer politische
                                              Nicht-Kriegsvideos?"
```

**Reihenfolge für Forschungsfrage 1 beachten**: `frage1_stichprobe.py` (0b)
muss NACH `prepare_channel_scores.py` (0) und VOR `deskriptiv_aggregation.py`
(1) sowie `frage1_populismus_bericht.py` (5) laufen — beide lesen die von 0b
erzeugte `frage1_kanal_whitelist.csv`.

**Reihenfolge für Forschungsfragen 2–4 beachten**: `prepare_success_metrics.py`
(0c) braucht `frage1_kanal_whitelist.csv` aus Schritt 0b (dieselbe Whitelist
wie Frage 1, siehe `frage2_4_methodik_und_stichprobe.md`) und muss VOR
`frage2_erfolg_bericht.py`/`frage3_populismus_erfolg_bericht.py`/
`frage4_kriegsvideos_erfolg_bericht.py` laufen. `frage3_populismus_erfolg_bericht.py`
braucht zusätzlich die Populismus-Zeitreihe aus Schritt 0
(`channel_{gran}_populism_timeseries.csv`).

0. **`prepare_channel_scores.py`**: sucht sich für jeden der drei Prompts
   (Ideologie, Populismus, Position/Stance) automatisch alle passenden
   `downloaded`-Runs aus `llm_runs.sqlite` (`source`+`prompt_id`, siehe
   `llm_run_store.get_results_for_prompt()`), schließt Test-/Pilot-Runs per
   Namensmuster aus, korrigiert die LLM-Rohergebnisse und aggregiert
   Segment → Video → Kanal×Periode für beide Granularitäten (Monat/Quartal).
   Schreibt u. a. `channel_{monat,quartal}_populism_timeseries.csv`,
   `channel_{monat,quartal}_position_timeseries.csv`,
   `channel_classification_{ideology,populism}.csv`,
   `channel_video_{populism,position}.csv` nach `outputs/segment_analysis/`.
   Muss laufen, bevor eines der folgenden Skripte sinnvolle Eingaben findet.
0b. **`frage1_stichprobe.py`**: dokumentiert und erzeugt die Kanal-Whitelist
   für Forschungsfrage 1 — Auswahltrichter kanonisches Sample →
   `>= MIN_KRIEGSVIDEOS` (Default 5) Kriegsvideos im gesamten Upload-Verlauf
   (`scripts/adhoc/output/topic_vids_per_channel.csv`) → mindestens
   `MIN_KLASSIFIZIERTE_VIDEOS` (Default 5) klassifizierte Videos
   (`channel_video_populism.csv` aus Schritt 0).
   Schreibt `frage1_kanal_whitelist.csv` (Eingabe für `KANAL_WHITELIST` in
   Schritt 1 und für `frage1_populismus_bericht.py`), die vollständige
   Audit-Spur `frage1_stichprobe_kanalstatus.csv` (eine Zeile je Kanal aus
   dem kanonischen Sample, mit einer Spalte je Filterstufe, inkl.
   `n_baseline_videos_ideologie`) sowie `frage1_methodik_und_stichprobe.md`
   — die verbindliche Dokumentation, WAS als „Baseline“ gilt und WIE
   „Veränderung nach Kriegsbeginn“ gemessen wird (inkl. der Abgrenzung
   zwischen der Klassifikations-Baseline aus Schritt 2, der
   Post-Dummy-Definition in `frage1_populismus_bericht.py` und der
   Index-Normierungs-Baseline in Schritt 1 — drei unterschiedliche, leicht zu
   verwechselnde Konzepte). Berichtet zusätzlich rein informativ (ohne die
   Whitelist zu filtern), wie viele Whitelist-Kanäle bei einer
   Mindestbesetzung von 5 bzw. 10 Baseline-Videos für die
   Ideologie-Klassifikation (`channel_classification_ideology.csv::n_videos`)
   übrig blieben.
1. **`deskriptiv_aggregation.py`**: liest die Zeitreihen aus Schritt 0 bzw.
   0c (`MODUS = "erfolg"` liest `channel_{gran}_erfolg_timeseries.csv`,
   `MODUS = "erfolg_kriegsvideos"` liest `channel_{gran}_erfolg_kriegsvideos_
   timeseries.csv` — beide aus `prepare_success_metrics.py`), ergänzt
   Medientyp (`lade_medientyp()`, aus
   `data/external/media_type_russia_merged.xlsx`) und Ideologie
   (`lade_ideologie()`, aus `channel_classification_ideology.csv`), filtert
   Kanäle und bildet für `MODUS = "populismus"` zusätzlich zum Rohwert
   einen Baseline-Index (letzte Vorkriegsperioden = 100); `"stance"`,
   `"erfolg"` und `"erfolg_kriegsvideos"` bekommen KEINEN Index (bei
   `"erfolg"`/`"erfolg_kriegsvideos"` bewusst, siehe
   `youtube-success-metric-raw-views` — rohe Views/Engagement werden nicht
   auf eine Vorkriegsperiode normiert). Der Rohwert (`wert_roh`) bleibt dabei
   für ALLE Kanal-Perioden-Zellen erhalten, auch für Kanäle ohne besetztes
   Vorkriegsfenster (deren `index_100` bleibt `NaN`) — `deskriptiv_plots.py`
   plottet standardmäßig den Rohwert, nicht den Index. `main()` iteriert
   automatisch über das kartesische Produkt aus `MODUS_LISTE` x
   `GRANULARITAET_LISTE` und schreibt je Kombination eine eigene
   `deskriptiv_{modus}_{granularitaet}.csv`.
2. **`deskriptiv_plots.py`**: plottet den Output von Schritt 1 als absolute
   Rohwerte (`wert_roh`, keine Baseline-Normierung — siehe Abschnitt 3c in
   `frage1_methodik_und_stichprobe.md`), mit optionalem Split nach Medientyp
   oder Ideologie. Beobachtungseinheit ist standardmäßig der Kanal-Monat
   (`GRANULARITAET = "monat"`); `"quartal"` bleibt als Alternative wählbar.
   Erzeugt je Dimension immer zwei Plot-Varianten (`KANALFILTER_VARIANTEN`):
   `"alle"` (alle Kanäle mit einem Wert in der jeweiligen Periode, inkl. seit
   Kriegsbeginn neu dazugekommene) und `"beide_perioden"` (nur Kanäle mit
   mindestens einem Vor- UND einem Nachkriegswert). Jede Gruppenlinie wird zur
   besseren Lesbarkeit bei mehreren ueberlagerten Gruppen LOWESS-geglaettet
   (`GLAETTUNG_LOWESS_FRAC`, rohe Periodenmittel werden zusaetzlich als blasse
   Punkte eingezeichnet, sofern `ZEIGE_ROHWERT_PUNKTE = True` — Standard; bei
   `False` zeigen die Plots nur die geglaetteten Linien); die 95%-CI-Baender
   sind bei mehreren Gruppen standardmaessig aus
   (`ZEIGE_CI = False`), da sie sich sonst gegenseitig verdecken. Schreibt
   PNGs (`{modus}_{dimension}_{split}_{granularitaet}_{variante}.png`) nach
   `outputs/segment_analysis/plots/`. Für `MODUS = "erfolg"` (deskriptive
   Ergänzung zu `frage2_erfolg_bericht.py`, Forschungsfrage 2) zusätzlich
   `GRUPPE4_PLOTTEN = True` setzen: `plotte_dimension_gruppe4()` zeichnet je
   Erfolgsmetrik einen eigenen Zeitverlaufsplot mit genau den vier Gruppen
   „ÖRR + Traditionelle Medien“, „Alternative Medien (links/mitte/rechts)“
   (`baue_gruppe4()`, PNGs `erfolg_{dimension}_gruppe4_{granularitaet}.png`)
   — dieselbe Rendering-Logik wie die bestehende 5-Gruppen-Übersicht für
   Populismus/Stance (`plotte_dimension_gruppen5()`/`baue_gruppe5()`, ÖRR und
   Traditionelles Medium dort weiterhin getrennt), nur mit ÖRR und
   Traditionellem Medium zu einer Gruppe zusammengefasst (siehe
   `alternative-medien-ideologie-differenzierung`: nur „Alternative Medien“
   lohnt eine weitere Ideologie-Aufschlüsselung). Zusatzoption
   `NUR_TOPICVIDEOS` (Standard `False`, nur mit `MODUS = "erfolg"`,
   Forschungsfrage 4): schaltet die Eingabedatei auf
   `deskriptiv_erfolg_kriegsvideos_{granularitaet}.csv` um (`MODUS =
   "erfolg_kriegsvideos"` in Schritt 1 muss dafür vorher gelaufen sein) —
   Ausgabedateien/-titel bekommen den Zusatz `_kriegsvideos`, damit sie die
   Rohwert-Plots über alle Videos derselben Dimension nicht überschreiben.
2a-Erweiterung. **`frage2_sensitivitaet_plots.py`**: eigenständige
   Sensitivitätsanalyse zu Forschungsfrage 2 — prüft, wie robust die
   deskriptiven Kernaussagen aus `deskriptiv_plots.py` (`MODUS = "erfolg"`)
   und `frage2_erfolg_bericht.py` gegenüber mehreren methodischen
   Einzelentscheidungen sind (Aggregationsebene über Kanäle, Metrik,
   Ausgangsbasis), sinnvoll direkt NACH `deskriptiv_plots.py` und VOR der
   formalen Regression zu laufen. Arbeitet auf `channel_video_erfolg.csv`
   (Video-Ebene aus Schritt 0c), bildet Kanal-Monats-Zellen selbst per
   `groupby` (inkl. `n_videos` je Zelle für die gedämpfte Gewichtung) und
   plottet dieselbe 5-Gruppen-Einteilung wie `baue_gruppe5()` (lokale
   Nachbildung, `GRUPPE5_REIHENFOLGE` importiert). Iteriert über die volle
   Matrix aus drei Aggregationsebenen (`zellen_ungewichtet` = bestehender
   Standard, `video_ebene` = gepoolt/linear gewichtet, `zellen_gewichtet` =
   gedämpft mit `n_videos ** GEWICHT_EXPONENT`), vier Metriken (Mittelwert,
   winsorisierter Mittelwert bei 5%/95% UND 1%/99%, Median, Summe) und bis
   zu vier Ausgangsbasen (absolute Views, Index auf das eigene
   Vorkriegsmittel bzw. den eigenen Vorkriegsmedian, Views/Abonnenten —
   standardmäßig sind nur die beiden Index-Basen aktiv), jeweils für alle
   Videos UND nur Kriegsvideos — im theoretischen Vollausbau 100
   Liniendiagramme nach `outputs/segment_analysis/plots_sensitivitaet_frage2/`,
   plus `frage2_sensitivitaet_methodik.md` mit der vollständigen
   Kombinationsmatrix, den Formeln je Zelle und der Subscriber-Snapshot-
   Limitation. Die beiden Index-Basen (`index_vorkriegsmittel_mean`/
   `_median`) unterscheiden sich NUR in der Baseline-Aggregation
   (`berechne_baseline()`): bei rechtsschiefen View-Verteilungen (typisch
   für YouTube) liegt der Mittelwert eines Kanals strukturell über seinem
   Median-Video, wodurch die Metrik `"median"` auf `_mean`-Basis
   systematisch unter Index=100 landet, auch ohne echte Veränderung;
   `_median` behebt das (Index=100 = „gleich wie das eigene mediane
   Vorkriegsvideo") und wird standardmäßig zusätzlich zu `_mean` erzeugt.
   Jede der 5 Gruppenlinien wird standardmäßig LOWESS-geglättet
   (`GLAETTUNG_LOWESS_FRAC`, dieselbe Methode wie `deskriptiv_plots.py`) —
   reine Darstellungshilfe gegen das Monat-zu-Monat-Zickzack, abschaltbar
   über `GLAETTUNG_LOWESS_FRAC = 0`. Keine 95%-CI-Bänder (Signifikanztests
   laufen bereits separat in `frage2_erfolg_bericht.py`) und keine
   Ereignis-Marker (reiner Methodenvergleich). Zusätzlich zur Matrix
   erzeugt `erzeuge_kombinierte_grafiken()` (CONFIG-Block `KOMBI_*`, alle
   Parameter als Listen für mehrere Spezifikationen in einem Lauf) je
   Kombination aus `KOMBI_METRIKEN` × `KOMBI_AGGREGATIONSEBENEN` ×
   `KOMBI_BASEN` eine kombinierte Grafik mit 2×5 Linien: je Gruppe5-Kategorie
   eine dicke Linie für den Hauptfokus `KOMBI_HAUPTFOKUS_UMFANG` (Standard
   „topic" = nur Kriegsvideos) und eine dünnere, transparente Linie in
   derselben Farbe für den Vergleichswert `KOMBI_VERGLEICHS_UMFANG`
   (Standard „alle" Videos) — direkter visueller Vergleich, ob der
   Gruppentrend bei Kriegsvideos vom Gesamttrend abweicht. Standard-
   Spezifikation: Median, video-Ebene, Index — standardmäßig für BEIDE
   Baseline-Varianten (Vorkriegsmittel UND -median) in einem Lauf, zum
   direkten Vergleich. Siehe Moduldocstring und
   `.claude/plans/frage2_sensitivitaet_plots.md` für die vollständige
   Herleitung.
3. **`fe_signifikanz_test.py`**: formale Prüfung, ob eine Dimension
   innerhalb einer gefilterten Kanalgruppe über die Zeit wirklich schwankt
   (Kanal-Fixed-Effects + Perioden-Dummies, auf Kanalebene geclusterte
   Standardfehler, F-Test auf gemeinsame Signifikanz der Perioden-Dummies).
   Arbeitet auf Video-Ebene (`channel_video_{populism,position}.csv`).
   Robustheitschecks: `vergleiche_gewichtung()` (kanal- vs. videogewichtet),
   `jackknife_trend_test()` (Leave-one-channel-out).
4. **`geglaettete_kurve.py`**: deskriptiv-explorativer Schritt vor formalen
   Bruchpunkt-/Phasentests — LOWESS-geglättete Kurve des kanalbereinigten
   Signals mit Cluster-Bootstrap-Konfidenzband, plus Ereignismarkern.
5. **`frage1_populismus_bericht.py`**: konsolidierte, formale Antwort auf
   Forschungsfrage 1 (`.claude/CLAUDE.md`) — arbeitet auf
   `channel_video_populism.csv` (Video-Ebene aus Schritt 0), gefiltert auf die
   Whitelist aus Schritt 0b (`frage1_kanal_whitelist.csv`) und VOR der
   Regression zu Kanal x Periode aggregiert (`aggregiere_kanal_periode()`,
   Mittelwert je Dimension über alle Videos eines Kanals innerhalb der
   jeweiligen Periode) — eine Beobachtung ist damit ein Kanal-Monat (bzw.
   Kanal-Quartal), kein einzelnes Video mehr. Für jede der vier
   Populismus-Dimensionen plus Gesamtscore (und die Kontrollgröße
   `emotionale_intensitaet`) und für beide Granularitäten (Quartal/Monat):
   ein Kanal-FE + Nachkriegs-Dummy-Test (`post_dummy_test()`, geclusterte SE)
   für die Gesamtstichprobe, sowie je Ideologie und Medientyp ein formaler
   Post×Gruppe-Interaktionstest (`interaktions_test()`, gemeinsamer F-Test auf
   die Interaktionsterme — testet direkt, ob sich der Nachkriegseffekt
   zwischen den Gruppen unterscheidet, nicht nur ob er in jeder Gruppe für
   sich signifikant ist) plus die einzelnen Gruppenkoeffizienten. Schreibt
   `frage1_populismus_bericht_{granularitaet}.csv` und druckt eine
   Kurzzusammenfassung.
5b. **`frage1_stance_bericht.py`**: strukturell identischer Bericht wie
   Schritt 5, aber fuer `channel_video_position.csv` (Prompt `POSITION_V1`)
   statt `channel_video_populism.csv` — Dimensionen `position_russland`
   (Haltung gegenueber Russland), `position_westpolitik` (Haltung gegenueber
   westlicher Ukraine-Politik) und `emotion` (Kontrollgroesse, analog zu
   `emotionale_intensitaet`). Nutzt dieselbe Whitelist aus Schritt 0b, dasselbe
   Kanal-FE + Post-Dummy/Interaktions-Modell und dieselben Gruppierungen.
   Inhaltlich keine der vier nummerierten Forschungsfragen aus
   `.claude/CLAUDE.md`, sondern zusaetzlicher Kontext zur selben
   Vorkriegs/Nachkriegs-Vergleichsanlage — die Wiederverwendung der Whitelist
   ist in `frage1_methodik_und_stichprobe.md` (Schritt 0b) dokumentiert.
   Schreibt `frage1_stance_bericht_{granularitaet}.csv`.
6. **`frage2_erfolg_bericht.py`**: konsolidierte, formale Antwort auf
   Forschungsfrage 2 (`.claude/CLAUDE.md`) — arbeitet auf dem bereits zu
   Kanal x Periode aggregierten Output von `prepare_success_metrics.py`
   (Schritt 0c, `channel_{gran}_erfolg_timeseries.csv`), gefiltert auf
   dieselbe Whitelist wie Forschungsfrage 1. Dimensionen: `log_views`
   (Reichweite pro Video), `log_views_summe` (Gesamtreichweite des Kanals
   in der Periode — macht Aktivitätssteigerungen ohne höheren
   Durchschnittserfolg pro Video sichtbar), `engagement_rate`. Wie Schritt
   5: Kanal-FE + Nachkriegs-Dummy-Test (`post_dummy_test()` aus
   `bericht_utils.py`) für die Gesamtstichprobe sowie Interaktionstests
   nach Ideologie, Medientyp UND (neu) `populismus_gruppe` (Tertile aus
   `channel_classification_populism.csv::populismus_gesamt`) — beantwortet
   direkt „sind populistische Kanäle seit Kriegsbeginn erfolgreicher
   geworden?“. Schreibt `frage2_erfolg_bericht_{granularitaet}.csv`.
7. **`frage3_populismus_erfolg_bericht.py`**: formale Antwort auf
   Forschungsfrage 3 („Werden Kanäle, die populistischer werden, auch
   erfolgreicher?“) — merged die Populismus-Zeitreihe (Schritt 0,
   `channel_{gran}_populism_timeseries.csv`) und die Erfolgs-Zeitreihe
   (Schritt 0c) auf Kanal x Periode-Ebene (Inner-Join, da Populismus nur
   für klassifizierte Videos vorliegt), zusätzlich auf die Frage-1-
   Whitelist gefiltert. Drei Bausteine: (a) Panel-Regression mit Kanal-FE
   UND Perioden-FE (`log_views ~ populismus_gesamt + log_duration_mean +
   C(channel_id) + C(periode)`, kontrolliert gemeinsame Zeittrends UND
   seit 2026-09-09 die Videolänge, rein korrelativ — keine Kausalaussage),
   (b) Δ-Δ-Korrelation je Kanal (`mean(post) - mean(pre)` für Populismus
   und Erfolg, Pearson/Spearman + OLS, mit Scatterplot — Pearson/Spearman
   bleiben bewusst unkontrollierte bivariate Maße, seit 2026-09-09 aber
   zusätzlich ein robustheitsprüfendes OLS-Modell `delta_log_views ~
   delta_populismus + delta_log_duration_mean` mit derselben, auf
   klassifizierte Videos beschränkten Längenkontrolle wie (a)/(c) — siehe
   Moduldocstring), (c) seit 2026-09-09
   Heterogenitätsanalyse nach `gruppe5` (ÖRR/Traditionelles Medium/
   Alternative Medien links-mitte-rechts): dieselbe Panel-Spezifikation
   wie (a), aber mit `populismus_gesamt:C(gruppe5)`-Interaktion (ohne
   eigenen Haupteffekt, vollrangig kodiert wie bei
   `frage4_kriegspraemie_medientyp_bericht.py::kriegspraemie_je_gruppe_test()`)
   und anschließendem Heterogenitäts-F-Test. Videolänge kommt aus
   `channel_video_erfolg.csv`, aber als Zellmittel NUR über die Videos aus
   `channel_video_populism.csv` (also genau die Videos, aus denen auch
   `populismus_gesamt` der Zelle gemittelt wird — nicht über alle Videos
   des Kanals in der Periode), `gruppe5` aus dem Medientyp-Excel/der
   Ideologie-CSV (`lade_medientyp()`/`lade_ideologie()` aus
   `deskriptiv_aggregation.py`). Schreibt
   `frage3_populismus_erfolg_bericht_{granularitaet}.csv` (Spalte
   `baustein` unterscheidet a/b/c) und
   `plots/frage3_delta_delta_{granularitaet}.png`.
8. **`frage4_kriegsvideos_erfolg_bericht.py`**: formale Antwort auf
   Forschungsfrage 4 („Betrifft eine Erfolgssteigerung nur Kriegsvideos
   oder auch andere Videos?“) — arbeitet auf der Video-Ebene aus Schritt 0c
   (`channel_video_erfolg.csv`), zu Kanal x Periode x Kriegsvideo-Flag-
   Zellen aggregiert (`ist_kriegsvideo` ist anders als Ideologie/Medientyp
   NICHT zeitkonstant je Kanal — Kanal-FE absorbieren einen
   Kriegsvideo-Haupteffekt hier NICHT automatisch). Modell MIT explizitem
   Haupteffekt: `y ~ C(channel_id) + post + ist_kriegsvideo +
   post:ist_kriegsvideo` — der Interaktionsterm beantwortet Frage 4 direkt.
   Ergänzend `post_dummy_test()` getrennt auf {alle Videos, nur
   Kriegsvideos, nur sonstige Videos} für einen Effektgrößenvergleich.
   `GRANULARITAET = "quartal"` primär (Kriegsvideos pro Kanal-Monat oft
   dünn besetzt), `"monat"` als Zusatzcheck. Schreibt
   `frage4_kriegsvideos_erfolg_bericht_{granularitaet}.csv`.
**8b.** **`frage4_kriegspraemie_medientyp_bericht.py`**: Erweiterung von
   Forschungsfrage 4 um die Medientyp-Dimension — „gibt es für bestimmte
   Medientypen eine Kriegsprämie?“ (Alternative Medien getrennt nach
   Ideologie, siehe `alternative-medien-ideologie-differenzierung`).
   Arbeitet wie Schritt 8 auf Kanal x Periode x Kriegsvideo-Zellen aus
   `channel_video_erfolg.csv`, bildet je Zelle aber gleich mehrere
   View-Metriken (Mittelwert, Median, winsorisierter Mittelwert 5%/95% UND
   1%/99%, log_views-Mittelwert — `DIMENSIONEN`) statt nur einer. Modell
   MIT vollen Perioden-FE (nicht nur einem Post-Dummy, anders als Schritt
   8): `y ~ C(channel_id) + C(periode) + ist_kriegsvideo:C(gruppe5)` —
   bewusst OHNE eigenen `gruppe5`- oder `ist_kriegsvideo`-Haupteffekt, da
   patsy `C(gruppe5)` dadurch INNERHALB der Interaktion vollrangig kodiert
   (ein Koeffizient je Gruppe, kein Referenzgruppen-Vergleich nötig — jeder
   Koeffizient ist direkt als „Kriegsprämie dieser Gruppe“ interpretierbar,
   siehe Moduldocstring für die Verifikation an einem synthetischen
   Beispiel). Zusätzlich ein Heterogenitäts-F-Test (paarweise Gleichheit
   aller Interaktionskoeffizienten — unterscheidet sich die Kriegsprämie
   zwischen den Gruppen?) sowie ein gepooltes Vergleichsmodell ohne
   Gruppenaufspaltung. `GRANULARITAET = "quartal"` primär wie Schritt 8.
   Zusätzlich optional (`PHASEN_AKTIV`, Standard `True`) eine
   **Phasenaufteilung**: neben der Gesamtzeitraum-Analyse läuft je Phase aus
   `PHASEN` (P1 Schock/Konsens Monat 0–6, P2 Energiekrise/Bruch 7–18, P3
   Aufmerksamkeitsverdrängung 19–26, P4 Wahlkampfphase 27–36, P5
   Nachwahlphase ab 37) ein eigener, in sich abgeschlossener Lauf desselben
   Modells (eigene Kanal-FE + Perioden-FE nur innerhalb der Phase) — zeigt,
   OB und WANN eine Kriegsprämie sichtbar wird, statt sie über den
   gesamten Zeitraum gemittelt zu schätzen. Phasengrenzen filtern IMMER auf
   `rel_monat` (`_phase_fenster()`), unabhängig von `GRANULARITAET`.
   Seit 2026-09-08 (Videolänge als Störfaktor, siehe
   `scripts/adhoc/videolaenge_diagnose.py` und Aufgaben.md-Absatz unten)
   zusätzlich zwei Maßnahmen: (1) `log_duration_mean` (Zellmittel von
   `log_duration_seconds`) als Kontrollvariable in JEDEM Modell (gepoolt UND
   je Gruppe), selbst nicht separat ausgegeben; (2) optional
   (`DAUER_TEILSTICHPROBEN_AKTIV`, Standard `True`) läuft JEDES Zeitfenster
   (Gesamtzeitraum + jede Phase) zusätzlich zur vollen Stichprobe je
   `DAUER_TEILSTICHPROBEN`-Intervall (feste, frei konfigurierbare
   Minutengrenzen) ein weiteres Mal, gefiltert auf Video-Ebene VOR der
   Zellenaggregation (`bericht_utils.py::dauer_teilstichprobe()`). Ebenfalls seit
   2026-09-08 (Nutzervorgabe „Bau jetzt die Upload-Dichte als Kontrollvariable
   ein“) zusätzlich `log_upload_dichte_mean` (Zellmittel, `bericht_utils.py::
   berechne_upload_dichte()` — misst, wie viele andere Videos der Kanal
   insgesamt veröffentlicht hat) in JEDEM Modell, analog `log_duration_mean`.
   Seit 2026-09-09 (Nutzervorgabe „es kommt auf Videos kurz vor und nach dem
   jeweiligen Video an“) fenster- statt periodenbasiert: gezählt werden
   andere Videos desselben Kanals mit `published_at` innerhalb von ±48
   Stunden um das jeweilige Video (statt alle Videos derselben
   `rel_monat`/`rel_quartal`-Periode) — dadurch granularitätsunabhängig,
   `lade_video_daten()` berechnet nur noch EINE Spalte `log_upload_dichte`
   statt vorher zwei (`log_upload_dichte_monat`/`_quartal`). Schreibt
   `frage4_kriegspraemie_medientyp_bericht_{granularitaet}.csv` mit den
   zusätzlichen Spalten `phase` (`"gesamt"` oder eine der `PHASEN`-
   Kennungen), `stichprobe` (`"voll"` oder eine der
   `DAUER_TEILSTICHPROBEN`-Kennungen) und `vergleichsgruppe` (`"alle_videos"`,
   `"nur_politische_videos"` oder `"nur_politische_videos_llm"`, siehe unten
   „Vergleichsgruppen-Dimension“).
   Seit 2026-09-09 (Nutzervorgabe „ich verstehe den Output ... nicht so gut“)
   schreibt `verarbeite_granularitaet()` zusätzlich einen menschenlesbaren
   Begleitbericht `frage4_kriegspraemie_medientyp_bericht_{granularitaet}.md`
   (`PFAD_REPORT`) mit denselben Zahlen wie die CSV, aber je Modell (= je
   Kombination aus `DIMENSION` x Zeitfenster x Stichprobe x Vergleichsgruppe)
   einem eigenen, überschriebenen Block: abhängige Variable, einbezogene
   Kontrollvariablen (inkl. Kanal-/Perioden-FE), Aggregationsebene,
   Sample-Charakteristika (Zeitfenster/Videolänge/Vergleichsgruppe) und
   Anzahl Beobachtungen (`_baue_modell_kopf()`), gefolgt von einer
   Ergebnistabelle (`_baue_ergebnis_tabelle()`, seit 2026-09-09 statt der
   vorherigen Freitextzeilen — Nutzervorgabe „die Ergebnisse für jede
   Gruppe … eine einzelne Zeile, damit es übersichtlicher ist“: ohne
   Leerzeile dazwischen zog Markdown die Freitextzeilen beim Rendern
   fälschlich zu einem Absatz zusammen) mit den Spalten Gruppe /
   Kriegsprämie / SE / p / Signifikant — je eine Zeile für „Gepoolt
   (alle)“, jede `gruppe5`-Kategorie und „Heterogenität (F-Test)“ —
   dadurch ist immer klar ersichtlich, welche Ergebnisse zu welcher
   Spezifikation gehören. Reine Formatierungsergänzung, ändert keine der
   berichteten Zahlen; nur für Baustein 1/2, nicht für die aktuell
   deaktivierten Bausteine 3/4.
   Seit 2026-09-09 (Nutzervorgabe „Executive Summary … aufgeteilt nach den
   wesentlichen Kriterien [Vergleichsgruppe/Videolänge-Stichprobe/Phasen vs.
   Gesamtzeitraum] … in wie vielen Spezifikationen der Koeffizient für einen
   Medientyp signifikant ist“) schreibt `verarbeite_granularitaet()` VOR den
   Einzelmodell-Blöcken zusätzlich eine Executive-Summary-Sektion
   (`_baue_executive_summary()`): eine Gesamtübersichtszeile plus drei
   Breakdown-Tabellen (nach Vergleichsgruppe, nach Stichprobe/Videolänge,
   nach Zeitfenster — Gesamtzeitraum und jede Phase einzeln). Je Zeile eine
   Ausprägung der jeweiligen Dimension, je Spalte „Gepoolt (alle)“/jede
   `gruppe5`-Kategorie/„Heterogenität (F-Test)“, Zelle „signifikant/gesamt“
   (p<0,05) über alle Spezifikationen, die auf den jeweils anderen Kriterien
   (inkl. beider `DIMENSIONEN`) variieren. Reine Umaggregation der bereits
   berichteten p-Werte, keine neuen Zahlen.

   **Zusatzspezifikationen — alternative Beobachtungseinheiten** (seit
   2026-09-08, Nutzerfrage nach der Beobachtungseinheit der Kriegsprämie),
   jeweils in eigener Ausgabedatei.
   `VIDEO_EBENE_AKTIV` (Baustein 3, `_fuehre_lauf_video_ebene()`/
   `verarbeite_video_ebene()`): dieselbe `ist_kriegsvideo:C(gruppe5)`-
   Interaktion, aber OHNE Zellenaggregation — jedes Video ist eine eigene
   Beobachtung (Kontrollvariablen als Video-eigene Werte statt Zellmittel),
   bewusst mit dem Nebeneffekt, dass Kanäle mit vielen Videos stärker
   wiegen als im Zellen-Design. Läuft NUR für `GRANULARITAET="quartal"`
   (auf Video-Ebene macht die Granularität außer der Auflösung der
   Perioden-FE keinen Unterschied mehr) und NUR für den Gesamtzeitraum
   (keine Phasenaufteilung wie Baustein 1/2), aber seit 2026-09-08
   zusätzlich über `DAUER_TEILSTICHPROBEN` gekreuzt (reduziert die sonst
   sehr hohe Zeilenzahl auf Video-Ebene spürbar). Schreibt
   `frage4_kriegspraemie_video_bericht_quartal.csv`.
   `ANTEIL_DESIGN_AKTIV` (Baustein 4, `_fuehre_lauf_anteil()`/
   `verarbeite_anteil()`, `aggregiere_kanal_periode_anteil()`): weiterhin
   Kanal×Periode-Zellen, aber ohne `ist_kriegsvideo`-Split — stattdessen
   `anteil_kriegsvideos = n_kriegsvideos / n_videos_gesamt` je Zelle als
   (mit `gruppe5` interagierte) erklärende Variable statt der
   `ist_kriegsvideo`-Dummy; beantwortet "korreliert ein höherer
   Kriegsvideo-Anteil in einer Kanal-Periode mit mehr/weniger Erfolg in
   dieser Periode?" statt "ist ein Kriegsvideo erfolgreicher als ein
   sonstiges Video derselben Kanal-Periode?". Läuft für BEIDE
   Granularitäten, nur Gesamtzeitraum + volle Stichprobe (Länge, kein
   Dauer-Kreuzprodukt wie Baustein 3). Schreibt
   `frage4_kriegspraemie_anteil_bericht_{granularitaet}.csv`. Beide
   Bausteine nutzen `kriegspraemie_je_gruppe_test()`/`kriegspraemie_
   gesamt_test()` über neue Parameter `treatment_var`/`kontroll_spalten`
   sowie die neue gemeinsame Funktion `_teste_und_baue_zeilen()` — die
   Zellen-Design-Funktion `_fuehre_lauf_aus()` bleibt in ihrer
   Modellformel-Logik unverändert, um die bereits berichteten Zahlen nicht
   zu gefährden. Siehe `frage2_4_methodik_und_stichprobe.md` Abschnitt 7
   für die volle Modellgleichung.

   **Vergleichsgruppen-Dimension** (seit 2026-09-08, Nutzervorgabe — gilt
   für ALLE VIER Bausteine, nicht nur die alternativen
   Beobachtungseinheiten): die "sonstigen Videos" (Nenner/Vergleich zu den
   Kriegsvideos) laufen NEBENEINANDER in drei Varianten
   (`VERGLEICHSGRUPPEN`, `bericht_utils.py::vergleichsgruppe_filter()`) —
   `"alle_videos"` (Status quo, unverändert, bitwise identisch zu den
   bereits berichteten Zahlen), `"nur_politische_videos"` (verwirft
   `ist_kriegsvideo == 0` UND keine bestätigte Politik-Klassifikation über
   `topic_categories`/`video_registry.politics_topic_lookup()`, hohe
   Abdeckung ~99,7 %) sowie, seit 2026-09-09 als zusätzlicher
   Robustheitscheck (Nutzervorgabe "auch meine LLM-Klassifikation aus dem
   screening_state mit politics_final verwenden"),
   `"nur_politische_videos_llm"` (verwirft `ist_kriegsvideo == 0` UND
   `politics_final != 1` aus `screening_state_store.get_state()` —
   manuelle/LLM-Klassifikation, deutlich geringere Abdeckung von nur ~12 %
   aller Videos, siehe Moduldocstring). Kriegsvideos selbst bleiben in
   ALLEN DREI Varianten IMMER ungefiltert. Wird auf Video-Ebene angewendet,
   NACH einer eventuellen Dauer-Teilstichprobe und VOR jeder
   Zellenaggregation; bei Baustein 4 bewirkt die Filterung eine
   Nenner-Restriktion der Anteilsberechnung (`anteil_kriegsvideos =
   n_kriegsvideos / n_politische_videos_gesamt`), analog zur
   Marktanteil-Logik in Schritt 8d. Alle vier Ausgabedateien bekommen dafür
   die zusätzlichen Spalten `vergleichsgruppe`/`vergleichsgruppe_label`.
   Seit 2026-09-09 (Nutzervorgabe „Füge eine Kontrolle ein, wie hoch der
   Anteil der politischen Videos des Kanals in der jeweiligen Periode
   war“) bekommt Baustein 1/2 zusätzlich `anteil_politischer_videos` als
   Kontrollvariable, aber NUR bei Vergleichsgruppe `"alle_videos"`:
   `aggregiere_zellen()` berechnet je Kanal-Periode (über ALLE Videos,
   unabhängig von `ist_kriegsvideo`) den Anteil mit
   `topic_categories='Politics'` — dieselbe hochabdeckende Klassifikation
   wie bei `"nur_politische_videos"`, nicht `politics_final`. Bei den
   beiden `"nur_politische_videos*"`-Vergleichsgruppen entfällt die
   Kontrolle bewusst (die Vergleichsgruppe ist dort bereits per Filter auf
   politische Videos beschränkt, kaum verbleibende Variation). Wird wie
   `log_duration_mean`/`log_upload_dichte_mean` selbst nicht separat
   ausgegeben.
8c. **`frage4_kriegspraemie_relative_views_plots.py`**: deskriptive
   Ergänzung zu Schritt 8b und zu TODO 1 aus `.claude/Aufgaben.md`
   („Kriegsprämie“) — zeigt die relativen Views von Kriegsvideos direkt als
   Zeitreihen-Index statt als Regressionskoeffizient. Arbeitet wie 8b auf
   `channel_video_erfolg.csv` (Video-Ebene aus Schritt 0c), poolt Videos
   aber direkt (keine Kanal-Zwischenaggregation, „auf der Video-Ebene“) je
   Gruppe5-Kategorie x `rel_monat`. Index je Zelle: `metrik(view_count |
   Kriegsvideos) / metrik(view_count | Vergleichsgruppe) * 100`, mit
   `metrik` ∈ {Median, Mittelwert} und drei Vergleichsgruppen — der
   Kriegsvideo-Zähler ist für alle drei identisch (Kriegsvideos werden
   NICHT nach `politics_final`/`topic_categories` gefiltert):
   - **alle_videos**: `ist_kriegsvideo == 0` (unabhängig von
     `politics_final`/`topic_categories`).
   - **andere_politische_videos**: `ist_kriegsvideo == 0 UND
     politics_final == 1` (manuelle/LLM-Klassifikation aus
     `data/store/screening_state.sqlite`, gemergt über `video_id`).
   - **andere_politische_videos_topic** (seit 2026-09-08, Nutzervorgabe):
     `ist_kriegsvideo == 0 UND topic_categories enthält "Politics"`
     (YouTube-eigene automatische Themenkategorisierung aus
     `data/store/video_registry.sqlite::video_details`, siehe
     `video_registry.is_politics_topic()`/`politics_topic_lookup()`) —
     deutlich höhere Abdeckung als `politics_final` (siehe unten), aber
     inhaltlich eine andere, breiter gefasste Definition von "politisch";
     ergänzende, nicht ersetzende Vergleichsgruppe.

   → 6 Liniendiagramme (3 Vergleiche x 2 Metriken), je 5 Linien
   (Gruppe5-Reihenfolge), mit gestrichelter Referenzlinie bei Index=100
   zusätzlich zur Kriegsbeginn-Vertikale. **Limitation `andere_politische_
   videos`** (ausführlich in der Methodik-Datei dokumentiert):
   `screening_state.sqlite` enthält nur eine per Zufallsseed gezogene
   Stichprobe von Kandidaten je Kanal x 3-Monats-Intervall aus dem
   longitudinalen Politik-Screening (Schritt 2) — nur ~12 % der Videos in
   `channel_video_erfolg.csv` haben überhaupt einen `screening_state`-
   Eintrag. Da die Auswahl nachweislich zufällig (nicht nach Views
   sortiert) erfolgt, betrifft das nur die (reduzierte) Zellbesetzung
   dieses Vergleichs, nicht dessen Repräsentativität.
   **`andere_politische_videos_topic`** hat dieses Abdeckungsproblem NICHT
   (~99,7 % der Whitelist-Videos haben einen `video_details`-Eintrag,
   ~53,9 % davon Kategorie "Politics", Stand 2026-09-08), dafür die oben
   beschriebene inhaltliche Einschränkung (breiter gefasste, automatische
   statt manuelle/LLM-Klassifikation). Wiederverwendet `baue_gruppe5_lokal()`
   und `glaette()` aus Schritt 2a-Erweiterung (`frage2_sensitivitaet_
   plots.py`) als echten Import. Schreibt PNGs sowie
   `kriegspraemie_relative_views_methodik.md` nach
   `outputs/segment_analysis/plots_frage4_kriegspraemie_relative_views/`.
   Siehe Moduldocstring und
   `.claude/plans/frage4_kriegspraemie_relative_views.md` für die
   vollständige Herleitung.
8d. **`frage4_kriegspraemie_marktanteil_plots.py`** (neu, 2026-09-08):
   Antwort auf die Zusatzfrage aus TODO 1 ("...oder können sie hier einen
   höheren Marktanteil als bei anderen (politischen) Videos erzielen?").
   Anders als Schritt 8c (Index INNERHALB derselben Gruppe: Kriegsvideo-
   Views vs. Vergleichsgruppen-Views derselben Gruppe) misst dieses Skript
   den Anteil, den jede Gruppe5-Kategorie an der GESAMTEN Reichweite
   (Summe aller Views) innerhalb eines Umfangs hat — eine echte
   Marktanteils-Kennzahl über die Gruppen hinweg:
   `anteil = sum(view_count | Gruppe, Umfang, Periode) /
   sum(view_count | alle 5 Gruppen, Umfang, Periode) * 100`. Zwei Umfänge
   (Kriegsvideos vs. `andere_politische_videos_topic`, siehe Schritt 8c)
   in EINER kombinierten Grafik (dick=Kriegsvideos, dünn=andere politische
   Videos, je Gruppe5-Kategorie in derselben Farbe) — wiederverwendet
   `plotte_kombinierte_grafik()` aus `frage2_sensitivitaet_plots.py` (seit
   2026-09-08 mit optionalem `pfad_plots`-Parameter, damit importierende
   Skripte in ihren eigenen Plot-Ordner statt `plots_sensitivitaet_
   frage2/` schreiben) sowie `lade_basisdaten()` aus Schritt 8c, jeweils
   als echter Import. Mindestbesetzung wirkt auf die GESAMTE Periode (alle
   5 Gruppen gemeinsam), nicht auf einzelne Gruppen/Zellen — dadurch
   summieren sich die 5 Anteile je Periode/Umfang immer exakt zu 100 %
   (Sanity-Check in `main()`). Schreibt eine PNG sowie
   `kriegspraemie_marktanteil_methodik.md` nach `outputs/segment_analysis/
   plots_frage4_kriegspraemie_relative_views/`.
8e. **`frage4_kriegspraemie_marktanteil_phasen_bericht.py`** (neu,
   2026-09-09): Nutzervorgabe nach Schritt 8d ("Ich möchte eine
   phasenweise Tabelle ... Marktanteile ... UND die absolute
   Gesamtnachfrage ... um zu sehen, ob der Kuchen wächst oder nur
   umverteilt wird") — dieselbe Marktanteils-Formel wie 8d, aber
   phasenweise statt als Monatszeitreihe aggregiert (`PHASEN` +
   `_phase_fenster()` aus `frage4_kriegspraemie_medientyp_bericht.py`,
   echter Import, ergänzt um eine eigene Phase "Vorkriegszeitraum" als
   Baseline) und mit DREI statt zwei Umfängen (`UMFAENGE`): Kriegsvideos,
   andere politische Videos (`topic_categories='Politics'`, seit
   2026-09-10 EXPLIZIT ohne Kriegsvideos — Nutzervorgabe, analog zu 8c/8d;
   bis dahin hieß dieser Umfang "politische_videos" und schloss
   Kriegsvideos MIT ein) und alle Videos ohne Themen-Einschränkung —
   "kriegsvideos" und "andere_politische_videos" sind seit 2026-09-10
   disjunkt, "alle_videos" bleibt eine echte Obermenge beider Umfänge,
   damit sich weiterhin ablesen lässt, ob eine Dominanz kriegsspezifisch
   ist oder sich auch auf Politik/Content generell erstreckt. Zusätzlich
   zum Marktanteil wird je Zelle
   `sum(view_count | alle 5 Gruppen)` als "Gesamtnachfrage" sowie durch die
   Monatsanzahl der Phase geteilt als "Gesamtnachfrage/Monat" ausgegeben
   (Phasen sind unterschiedlich lang) — das beantwortet direkt, ob der
   Aufmerksamkeits-Kuchen wächst oder nur umverteilt wird, unabhängig von
   den Anteilen. Mindestbesetzung wirkt wie bei 8d auf die GESAMTE
   (Phase, Umfang)-Zelle (`MIN_VIDEOS_GESAMT_PRO_PHASE=100`), nicht auf
   einzelne Gruppen. Schreibt
   `frage4_kriegspraemie_marktanteil_phasen_bericht.csv` (eine Zeile je
   Phase x Umfang x Gruppe5) und `..._bericht.md` (eine Tabelle je Umfang,
   Zeilen = Phasen) nach `outputs/segment_analysis/`. **Shift-Share-Erweiterung**
   (2026-09-09, Nutzervorgabe, urspruenglich nur fuer den Umfang
   "kriegsvideos" eingefuehrt und am selben Tag auf Nutzerwunsch auf ALLE
   DREI Umfaenge erweitert): der Marktanteil wird je Umfang zusaetzlich
   multiplikativ zerlegt in
   `Marktanteil(g) = output_anteil(g) x relative_reichweite(g)` mit
   `output_anteil(g) = n_videos_gruppe(g) / n_videos_gesamt(alle, im Umfang)` und
   `relative_reichweite(g) = views_pro_video_gruppe(g) / views_pro_video_alle(im Umfang)`
   (`views_pro_video_gruppe` = arithmetisches Mittel auf Einzelvideo-Ebene,
   NICHT Kanal-Periode-vorgemittelt — mit dem Nutzer abgestimmt, da nur so die
   Zerlegung exakt multiplikativ mit dem bereits berichteten, video-gepoolten
   Marktanteil konsistent ist). Die CSV bekommt fuenf neue Spalten
   (`views_gruppe_summe`, `views_pro_video_gruppe`, `output_anteil`,
   `relative_reichweite`, `n_videos_gruppe_pro_monat`, fuer alle drei Umfaenge
   befuellt); die bestehende `n_videos_gruppe`-Spalte entspricht fuer den
   Umfang "kriegsvideos" bereits `n_kriegsvideos(g)`. Validiert
   `output_anteil x relative_reichweite` je Umfang gegen den bestehenden
   Marktanteil (Toleranz `TOLERANZ_SHIFT_SHARE=1e-6`) — bei Abweichung
   bricht `berechne_tabelle()` mit `ValueError` ab (keine stille Korrektur).
   Der Bericht bekommt dafuer unter JEDER der drei Umfangs-Tabellen einen
   eigenen Abschnitt "Shift-Share-Zerlegung" (gleiche Phase x
   Gruppe5-Struktur, vier Teiltabellen: n Videos/Kriegsvideos, n
   Videos/Kriegsvideos pro Monat, Output-Anteil, relative Reichweite —
   Beschriftung passt sich am Umfang an).
8f. **`kanaluebersicht_marktanteil_bericht.py`** (neu, 2026-09-10): Kanal-
   Ebenen-Zerlegung des Gruppen-Marktanteils aus 8d/8e — ausgelöst durch die
   Nutzerfrage, ob der in der Marktanteilsgrafik sichtbare Vorkriegs-Trend
   (Anstieg Traditionelles Medium, Abschwung Alternative Medien rechts) von
   wenigen großen Kanälen getrieben wird. Zwei Kennzahlen je Kanal x Periode
   x Umfang (`UMFAENGE`, echter Import aus Schritt 8e):
   `anteil_am_markt_pct` (Kanal-Anteil an der Views-Summe ALLER 5 Gruppen —
   summiert sich je Gruppe zum bereits berichteten Gruppen-Marktanteil) und
   `anteil_an_gruppe_pct` (Kanal-Anteil an der Views-Summe der EIGENEN
   Gruppe5-Kategorie — die eigentliche Konzentrationskennzahl: nahe 100% =
   ein/zwei Kanäle dominieren die Gruppe). Perioden: zwei nicht
   überlappende Vorkriegsfenster (`vorkrieg_fern` Monat -12 bis -7,
   `vorkrieg_nah` Monat -6 bis -1) PLUS die 5 Nachkriegsphasen (`PHASEN`,
   echter Import aus Schritt 8b). Mindestbesetzung wie 8e
   (`MIN_VIDEOS_GESAMT_PRO_PHASE`, echter Import). Schreibt
   `kanaluebersicht_marktanteil_bericht.csv` (eine Zeile je Kanal x Periode
   x Umfang) sowie `..._bericht.md` (fokussierter Ausschnitt: Top-Kanäle je
   Gruppe für die beiden Vorkriegsperioden im Umfang
   "andere_politische_videos", inkl. Top-2-Konzentrationskennzahl).
   Ergebnis der Konzentrationsanalyse (siehe Chat-Verlauf 2026-09-10): der
   Anstieg von Traditionelles Medium ist breit getragen (Top-2-Kanäle
   erklären nur ~36% des Gruppenanstiegs, ihr Anteil AN der Gruppe sinkt
   sogar leicht), der Abschwung von Alternative Medien (rechts) dagegen
   überwiegend ein Einzelkanal-Effekt (Boris Reitschuster allein erklärt
   ~48%, die Top-2-Kanäle zusammen ~63% des Gruppenrückgangs).
8g. **`marktanteil_themen_plots.py`** (neu, 2026-09-10): Erweiterung von 8d
   auf alle fünf klassifizierten Themen (`video_topic_relevance`, nicht nur
   Ukraine-Krieg) — Nutzervorgabe „Ich möchte, dass die anderen Themen auch
   eingearbeitet werden … für jedes einzelne Thema und für alle politischen
   Videos (diesmal wieder nicht-exklusiv) einen Verlauf … im CONFIG Block
   einstellen können, welche Medientypen, welche Themen und ggf. kombinierte
   Typen dargestellt werden.“ Dieselbe Marktanteils-Formel wie 8d
   (`berechne_marktanteile()`/`pruefe_summe_100()`, echte Importe aus 8d),
   aber über konfigurierbare **Anzeigegruppen** (`ANZEIGE_GRUPPEN`/
   `ANZEIGE_GRUPPEN_AKTIV` — Name → Liste roher Gruppe5-Kategorien, die zu
   einer Linie summiert werden, z. B. ein kombinierter Typ „ÖRR +
   Traditionell“) und **Szenarien** (`THEMEN`/`THEMEN_AKTIV`: die fünf
   Themen aus `step3_topic_relevance/topic_keywords.TOPIC_KEYWORDS`, PLUS
   `alle_politische_videos` — `topic_categories='Politics'`, anders als 8d/
   8e bewusst NICHT-exklusiv zu den Themen). Zwei Grafik-Typen: **Typ A**
   (dick/dünn je Szenario, wie 8d, aber je Anzeigegruppe statt fester
   Gruppe5-Liste — dünn ist bei jedem Themen-Szenario `alle_politische_
   videos`, bei dessen eigener Grafik `alle_videos`) und **Typ B** (je
   aktive Anzeigegruppe eine Grafik, eine Linie je Szenario, ohne Dick/
   Dünn-Vergleich — Antwort auf die Rückfrage „18 Linien wären zu
   unübersichtlich“). Wiederverwendet `plotte_kombinierte_grafik()`/
   `plotte_kombination()` aus `frage2_sensitivitaet_plots.py` — seit
   2026-09-10 mit optionalen `gruppen_liste`/`gruppen_spalte`(/`pfad_plots`
   bei `plotte_kombination()`)-Parametern (Default weiterhin
   `GRUPPE5_REIHENFOLGE`/`"gruppe5"`, bestehende Aufrufe unverändert).
   Schreibt PNGs (Typ A + Typ B), `marktanteil_themen_monat.csv` (eine
   Zeile je Szenario x Periode x Anzeigegruppe) sowie
   `marktanteil_themen_methodik.md` nach `outputs/segment_analysis/
   plots_marktanteil_themen/`.
8h. **`marktanteil_themen_treiber_plots.py`** (neu, 2026-09-10):
   Zerlegungs-Erweiterung von 8g — Nutzervorgabe „Ich möchte, dass du ein
   neues Skript erstellst, das sie [die Marktanteilsgrafiken] etwas
   abändert: Ich möchte die durchschnittlichen Views pro Video und die
   Anzahl der Videos (also eine Shift-Share-Zerlegung wie im
   Marktanteilsbericht).“ Nach Rückfrage (Basis nur 8g, nicht 8d; rohe statt
   normierte Werte) entschieden. Formel:
   `views_summe(g) = n_videos(g) x views_pro_video(g)`, deren Verhältnis zur
   Gesamtsumme aller 5 rohen Gruppe5-Kategorien exakt den in 8g berichteten
   Marktanteil ergibt — `views_pro_video(g)` wird dabei NACH dem Kombinieren
   roher Gruppe5-Kategorien zu einer Anzeigegruppe neu aus der summierten
   `views_summe`/`n_videos` berechnet (nicht als Summe/Mittel einzelner
   Kategorie-Durchschnitte, siehe `aggregiere_anzeigegruppen_treiber()`).
   Anders als die phasenweise, normierte Shift-Share-Tabelle in 8e
   (`output_anteil` in %, `relative_reichweite` als Index) zeigt dieses
   Skript dieselbe Zerlegung monatlich UND als rohe Werte (Anzahl Videos,
   durchschnittliche Views/Video). Übernimmt Szenarien, Anzeigegruppen und
   Mindestbesetzung 1:1 als echte Importe aus 8g (keine Neudefinition).
   Zwei Grafik-Typen (Typ A dick/dünn je Szenario, Typ B je Anzeigegruppe
   über alle Szenarien — dieselbe Struktur wie 8g) für JEDE der beiden
   Metriken, also doppelt so viele PNGs wie 8g. Schreibt PNGs,
   `marktanteil_themen_treiber_monat.csv` (eine Zeile je Szenario x Periode
   x Anzeigegruppe, Spalten `n_videos`/`views_pro_video`/`views_summe`)
   sowie `marktanteil_themen_treiber_methodik.md` nach
   `outputs/segment_analysis/plots_marktanteil_themen_treiber/`.
8i. **`marktanteil_rohdaten_plots.py`** (neu, 2026-10-02): Marktanteils-
   Grafiken auf Basis des zentralen Analysedatensatzes
   `outputs/stata_rohdaten/` (`videos_roh.dta`, `kanaele_roh.dta`, siehe
   `export_stata_rohdaten.py`) statt `channel_video_erfolg.csv`/
   `lade_basisdaten()`. Anteil = Views der Gruppe / Views aller Gruppen der
   Klassifikation je `rel_monat` (−13 bis 51). Zwei Umfänge je Grafik
   (links `politisch == ja` inkl. Kriegsvideos, rechts `krieg == ja`), zwei
   Klassifikationen: (1) ÖRR, traditionelle Medien, alternative Medien
   links/mitte/rechts nach `ideo_gesellschaft_baseline` (Schnitte ±0,5;
   Ideologie jetzt aus dem Vorkriegsfenster), (2) Tertile von `pop_baseline`
   (über Kanäle, Partei/Politiker ausgeschlossen). Beides für alle Kanäle
   und für `sample_vorkrieg == ja`. Schreibt 4 PNGs, `marktanteil_monat.csv`
   und `marktanteil_methodik.md` (inkl. Phasenmitteln) nach
   `outputs/segment_analysis/plots_marktanteil_rohdaten/`. Aufruf:
   `PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.marktanteil_rohdaten_plots`.
9. **`populismuspraemie_kriegsvideos_bericht.py`**: Antwort auf TODO 2 aus
   `.claude/Aufgaben.md` ("Populismusprämie" — erhalten populistische
   Kriegsvideos innerhalb eines Kanals mehr Aufrufe als weniger populistische?),
   inhaltlich KEINE der vier nummerierten Forschungsfragen aus `.claude/CLAUDE.md`.
   Arbeitet auf VIDEO-Ebene (Merge von `channel_video_{populism,position}.csv`,
   Schritt 0, und `channel_video_erfolg.csv`, Schritt 0c, auf `video_id`), gefiltert
   auf `ist_kriegsvideo == 1` — anders als Forschungsfrage 3
   (`frage3_populismus_erfolg_bericht.py`, Kanal x Periode-Ebene, Populismus-Niveau
   eines Kanals über die Zeit) misst dieses Skript, ob EIN Kriegsvideo, das
   populistischer (bzw. prononcierter positioniert) ist als die anderen
   Kriegsvideos DESSELBEN Kanals, auch mehr Views hat. Seit 2026-09-08 über `MODUS`
   auch auf die Haltung gegenüber Russland/westlicher Ukraine-Politik anwendbar
   (Nutzervorgabe) — strukturell identisches `MODUS`-Konzept wie
   `fe_signifikanz_test.py`/`deskriptiv_aggregation.py` (`"populismus"` |
   `"stance"`, steuert Eingabedatei UND Dimensionsliste, siehe Konfigurationstabelle
   unten). `channel_video_erfolg.csv` ist bereits auf die Frage-1-Kanal-Whitelist
   beschränkt, eine zusätzliche explizite Whitelist-Filterung entfällt daher.
   Vier Bausteine je Dimension (bei `MODUS="populismus"`: Gesamtscore + vier
   Einzeldimensionen; bei `MODUS="stance"`: `position_russland`,
   `position_westpolitik` + Kontrollgröße `emotion`): (a) Gesamtmodell über die
   gesamte Stichprobe/den gesamten Zeitraum (`log_views ~ dimension +
   C(channel_id)`, geclusterte SE), (b) Interaktion mit Medientyp (`log_views ~
   C(channel_id) + dimension:C(medientyp)`, vollrangige Kodierung von
   `C(medientyp)` innerhalb der Interaktion wie in
   `frage4_kriegspraemie_medientyp_bericht.py` — jeder Koeffizient ist direkt als
   "Effekt dieser Dimension für diesen Medientyp" interpretierbar, ergänzt um einen
   Heterogenitäts-F-Test). Bewusst noch ohne Ideologie-Interaktion oder
   Zellen-Mindestbesetzung ("einfaches Skript" für den ersten Schritt,
   Nutzervorgabe). Seit 2026-09-08 zusätzlich (d) dieselbe Interaktionslogik wie
   (b), nur mit Zeitperiode statt Medientyp als Gruppierung (`log_views ~
   C(channel_id) + dimension:C(zeitperiode)`, Nutzervorgabe: "Setze die
   Zeitperioden-Interaktion um" — automatisierte Antwort auf die Frage, ob der
   Effekt einer Dimension in bestimmten Zeiträumen besonders hoch ist).
   `zeitperiode` wird aus `ZEITPERIODEN_SPALTE` (`rel_quartal`/`rel_monat`
   relativ zu `KRIEGSBEGINN`, siehe `ergaenze_periodenspalten()` in
   `prepare_channel_scores.py`) über die konfigurierbaren `ZEITPERIODEN_GRENZEN`
   in Bins gruppiert (`erstelle_zeitperiode()`), z. B. `"Q0-Q3"`/`"Q4-Q7"`/
   `"Q8+"`. Ebenfalls seit 2026-09-08 zusätzlich (c) ein kombiniertes Modell
   (Nutzervorgabe) — anders als (a)/(b), die je EINE Dimension aus der über `MODUS`
   gewählten Datei testen, enthält dieses Modell mehrere über `KOMBI_VARIABLEN`
   konfigurierbare Dimensionen GLEICHZEITIG als Regressoren, unabhängig von `MODUS`
   und bei Bedarf aus beiden Dateien gemischt (`log_views ~ KOMBI_VARIABLEN[0] + ... +
   C(channel_id)`, geclusterte SE) — jeder Koeffizient ist damit der Effekt dieser
   Dimension HALTEND für die anderen `KOMBI_VARIABLEN` (Default: `populismus_gesamt`
   und `position_russland`). Zusätzlich (Nutzervorgabe) eine paarweise
   Pearson-Korrelationstabelle zwischen allen `KOMBI_VARIABLEN`
   (`kombiniertes_modell_korrelation()`, gleiche Stichprobe wie das Modell) als
   Multikollinearitäts-Check — eigene Ausgabedatei
   `kombiniertes_modell_korrelation.csv`. Seit 2026-09-08 (Videolänge als möglicher
   Konfundierer auch INNERHALB der Kriegsvideos, Nutzervorgabe "überall") ergänzt
   `log_duration_seconds` als Kontrollvariable JEDEN der Bausteine (a)–(g) (eigener
   additiver Term je Modellformel, selbst nicht separat ausgegeben); zusätzlich läuft
   optional (`DAUER_TEILSTICHPROBEN_AKTIV`, Standard `True`) der GESAMTE `main()`-
   Ablauf (alle Bausteine a–g) je `DAUER_TEILSTICHPROBEN`-Intervall (feste, frei
   konfigurierbare Minutengrenzen, dieselbe Konfigurationslogik wie in
   `frage4_kriegspraemie_medientyp_bericht.py`) zusätzlich zur vollen Stichprobe
   komplett eigenständig durch (`fuehre_analyse_aus()`, von `main()` je Stichprobe aufgerufen, gekapselt aus dem
   früheren `main()`-Körper). Ebenfalls seit 2026-09-08, aber TESTWEISE (Nutzervorgabe
   „Nimm age_days und category_id testweise dazu“, Befund: keine relevante
   Veränderung ggü. reiner Längenkontrolle): `age_days` (Tage bis zum
   Datenabruf) und `category_id` (YouTube-Kategorie, seltene Kategorien zu
   "Sonstige" zusammengefasst, siehe `KATEGORIE_MIN_VIDEOS`) ergänzen
   `log_duration_seconds`. Seit 2026-09-08 zusätzlich, aber ANDERS als
   age_days/category_id als FESTE Ergänzung (Nutzervorgabe „Bau jetzt die
   Upload-Dichte als Kontrollvariable ein“): `log_upload_dichte`
   (`bericht_utils.py::berechne_upload_dichte()` — misst die Konkurrenz um
   Aufmerksamkeit INNERHALB des Kanals, siehe Moduldocstring
   „UPLOAD-DICHTE“; seit 2026-09-09 fenster- statt periodenbasiert: andere
   Videos desselben Kanals innerhalb von ±48 Stunden um das jeweilige
   Video). Alle drei sind in einem gemeinsamen
   `KONTROLLVARIABLEN_FORMEL`-Baustein zusammengefasst, der automatisch in
   denselben sieben Bausteinen (a)–(g) mitläuft — ohne eigene Sensitivitäts-
   Teilstichprobe (die bleibt an die Videolänge gekoppelt). Seit 2026-09-10
   zusätzlich (g) — Nutzervorgabe „Setz Punkt 2 mit dem Interaktionsterm um“,
   als Antwort auf die Rückfrage, was mit einer „Wechselwirkung zwischen
   Position und Populismus“ gemeint war: verstärkt Populismus die
   Positionsprämie (TODO 3, bzw. symmetrisch: verstärkt Position die
   Populismusprämie, TODO 2)? Anders als (c)/(e)/(f), die
   `populismus_gesamt` und die Positions-Dimensionen als GETRENNTE additive
   Regressoren behandeln, schätzt `interaktion_populismus_position_test()`
   für jedes Paar aus `INTERAKTIONS_PAARE_POPULISMUS_POSITION` (Default:
   `position_russland`/`position_westpolitik`, je mit `populismus_gesamt`)
   ein eigenes MULTIPLIKATIVES Modell (`log_views ~ center(position) *
   center(populismus_gesamt) + Kontrollvariablen + C(channel_id)`) —
   Zentrierung (`patsy.center()`) macht die beiden Haupteffekt-Koeffizienten
   direkt interpretierbar (Effekt der einen Dimension beim Durchschnittswert
   der anderen), ohne den Interaktionskoeffizienten selbst zu verändern. Der
   entscheidende Koeffizient ist der Interaktionsterm — ein signifikant
   positiver Wert bedeutet: je populistischer ein Kriegsvideo, desto stärker
   schlägt seine Position auf die Views durch. Ergebniszeilen bekommen dafür
   eine zusätzliche Spalte `term` (`"position_haupteffekt"` |
   `"populismus_haupteffekt"` | `"interaktion"`). Schreibt
   `{modus}praemie_kriegsvideos_bericht.csv`
   (bei `MODUS="populismus"` identisch zum ursprünglichen Dateinamen
   `populismuspraemie_kriegsvideos_bericht.csv`) sowie
   `kombiniertes_modell_korrelation.csv`, beide mit der zusätzlichen Spalte
   `stichprobe` (`"voll"` oder eine `DAUER_TEILSTICHPROBEN`-Kennung).
9b. **`select_political_nonwar_targets.py`**: Zielauswahl-VORBEREITUNG (kein
   Bericht) für einen Gegentest zu Schritt 9 — ist die dort gefundene
   Populismus-Views-Beziehung bei politischen NICHT-Kriegsvideos genauso hoch
   wie bei Kriegsvideos? Dafür braucht eine ausreichende Zahl politischer
   Nicht-Kriegsvideos je Kanal-Monat zunächst ein Transkript (Schritt 4) und
   eine Populismus-Klassifikation (Schritt 5) — dieses Skript deckt nur den
   Transkript-Zielauswahl-Teil ab. Ruft
   `step4_transcript_download.select_targets.select_cell_fill_targets()` mit
   `include_war=False` auf (Pool "politisch klassifizierte
   Nicht-Kriegsvideos", `politics_final == 1` aus `screening_state_store` —
   dieselbe ~12%-Abdeckungs-Limitation wie bei
   `frage4_kriegspraemie_relative_views_plots.py`), gefiltert auf dieselbe
   `frage1_kanal_whitelist.csv` wie überall sonst in diesem Ordner (damit der
   spätere Vergleich auf denselben Kanälen läuft wie Schritt 9). Je
   Kanal-Monats-Zelle werden bis zu `VIDEOS_PER_CELL` (Default 3) Videos
   ausgewählt, Videos mit bereits vorhandenem Transkript zuerst (siehe
   `_top_n_per_group()`-Doku in `select_targets.py`). Schreibt
   `political_nonwar_download_ids.csv` (video_id, channel_id) — bereits gegen
   `transcript_store.attempted_video_ids()` gefiltert, enthält also nur noch
   Videos ohne bestehenden Download-Versuch. Startet selbst KEINEN Download
   (`.claude/CLAUDE.md`: Testläufe brauchen vorherige Rückfrage) — die Liste
   ist der Input für `download_transcripts()`/`run_transcript_selection.py`.
10. **`schockfenster_bericht.py`** (neu, 2026-09-10): Antwort auf TODO 3 aus
   `.claude/Aufgaben.md` ("Schockfenster" — kurze Zeiträume vor/nach
   wichtigen Ereignissen wie Kriegsbeginn oder der US-Wahl 2024,
   Reichweiten-Sprünge mit Heterogenität nach Kanalgruppe). Anders als alle
   bisherigen Vorher/Nachher-Berichte (gröbste Auflösung: `rel_monat`)
   arbeitet dieses Skript auf einer TAGESGENAUEN Periodenspalte
   (`tage_relativ = published_at − Ereignisdatum`, je Schock neu berechnet)
   und iteriert automatisch über ein Kreuzprodukt aus `SCHOCKS` (Ereignis +
   Datum, Default: Kriegsbeginn, US-Wahl 2024, US-Wahl 2024/nur Kriegsvideos,
   seit 2026-09-10 zusätzlich Bucha bekannt am 3.4.2022 — Nutzervorgabe,
   siehe `schockfenster_methodik.md` Abschnitt "Schock bucha" für die
   Begründung und die Einschränkung, dass die vorhandene Monats-Zeitreihe
   dafür VORAB kein eigenständiges Signal zeigt), `FENSTER_BREITEN_TAGE`
   (mehrere Fensterbreiten als eingebaute Sensitivitätsprüfung, Default
   `[7, 14, 30]`) und `HETEROGENITAETS_DIMENSIONEN` (`gruppe5`/`medientyp`/
   `ideologie_gruppe`) — neue Kombinationen lassen sich über diesen
   Konfigurationsblock ergänzen, ohne den restlichen Code anzufassen.
   `METRIKEN` sind seit 2026-09-10 nicht mehr nur `view_count`/`log_views`,
   sondern zusätzlich `position_russland`/`position_westpolitik` (Haltung
   gegenüber Russland bzw. westlicher Ukraine-Politik, aus
   `channel_video_position.csv` in `lade_basisdaten()` an die Video-Ebene
   gemergt) — laufen technisch unverändert durch dieselbe
   `post_dummy_test()`/`interaktions_test()`-Maschinerie, sind aber nur für
   die LLM-klassifizierte Teilmenge belegt (NaN-Zeilen werden automatisch
   per `dropna()` ausgeschlossen), was die Power bei engen Fenstern für
   diese beiden Metriken zusätzlich verringert.
   Kanalpopulation bewusst BREITER als die Frage-1-Whitelist — alle Kanäle
   mit Medientyp-Klassifikation (`lade_medientyp()`), da eine reine
   Reichweiten-Analyse keinen Populismus-Score braucht und enge Tage-Fenster
   ohnehin knapp besetzt sind (`baue_gruppe5()` filtert die Population
   zusätzlich auf vollständig klassifizierte Kanäle, dieselbe Population
   gilt dann auch für `medientyp`/`ideologie_gruppe`). Zwei
   Beobachtungsebenen laufen als GETRENNTE Robustheits-Durchläufe (Projekt-
   Konvention, siehe `berechne_upload_dichte()`/`berechne_upload_dichte_
   periode()` in `bericht_utils.py`): Video-Ebene (`tage_relativ`
   kontinuierlich) und Kanal×Fensterseite aggregiert (`fenster_bucket =
   −1`/`+1`, Ereignistag zählt zu "nach", über die bereits vorhandene
   `prepare_success_metrics.aggregiere_kanal_periode_erfolg()` gebildet).
   Wiederverwendet `post_dummy_test()`/`interaktions_test()` aus
   `bericht_utils.py` UNVERÄNDERT (beide funktionieren bereits mit jeder
   numerischen Periodenspalte, nicht nur `rel_monat`/`rel_quartal`) — keine
   neue Regressionslogik. Schreibt `schockfenster_ergebnisse.csv` (eine
   Zeile je Schock × Fensterbreite × Beobachtungsebene × Dimension × Metrik
   × Testtyp × Gruppe/Referenzgruppe) sowie `schockfenster_methodik.md` nach
   `outputs/segment_analysis/`. Erster Wurf bewusst nur mit der
   Kern-Regressionstabelle (kein Marktanteil-Vergleich, keine Plots — siehe
   `.claude/plans/schockfenster_bericht.md` für die vollständige Herleitung
   und mögliche Ausbauschritte).

## Konfiguration

Jedes Skript trägt seine Konfiguration als Modul-Level-Konstanten am
Dateikopf (Muster wie in den anderen Schritt-Ordnern).

### `prepare_channel_scores.py`

| Parameter | Bedeutung |
|---|---|
| `SOURCE` | `llm_runs`-Quelle, aus der Runs gesucht werden (`"segment_analysis_active"`) |
| `PROMPT_IDEOLOGIE`/`_POPULISMUS`/`_POSITION` | `prompt_id`-Werte (`IDEOLOGIE_I`/`POPULISMUS_P`/`POSITION_V1`), über die passende Runs automatisch gefunden werden (`llm_run_store.get_results_for_prompt()`) |
| `EXCLUDE_DATASET_SUBSTRING` | Runs, deren `dataset_id` diesen Substring enthält (case-insensitiv, Default `"test"`), werden als Test-/Pilot-Läufe ausgeschlossen |
| `ANALYSIS_ID` / `CHANNEL_SAMPLE_PATH` | kanonische Sample-Definition (`data/samples/<ANALYSIS_ID>/channel_sample_provenance.csv`, siehe `step1_sample/build_channel_provenance.py`) — schränkt die Video-Auswahl auf `eligible_current_analysis == True`-Kanäle ein |
| `BASELINE_INTERVAL_INDIZES` | `interval_index`-Werte aus `screening_state_store`, die als Vorkriegs-/Postwar-Baseline-Fenster für `channel_classification_populism.csv` zählen (`[-1, 0, 1, 2, 3]`, dasselbe Rezept wie `select_baseline_targets()`) |
| `GRANULARITAETEN` | Definiert Perioden-Länge (Monat/Quartal) je Zeitreihen-Output |

Die frühere manuelle Kuratierungsstufe zwischen dem automatischen
LLM-Download (`download_segments_simple.py`) und diesem Skript (`_corrected.csv`-
Dateien, handverlesene `populism_runs_combined.csv`, feste Einzel-`run_NNNN`-Pfade)
entfällt damit: Runs werden automatisch per `prompt_id`/`source` gefunden,
Test-Runs per Namensmuster ausgeschlossen, doppelt klassifizierte `video_id`s
lösen sich zugunsten des jeweils neuesten Runs auf, und die beiden fachlich
nötigen Korrekturen (`kodierbar == False` → Populismus-Dimensionen/emotionale
Intensität auf `NaN`; `rus_status`/`west_status == "deskriptiv"` →
`rus_score`/`west_score` auf `0`) sind fest im Code (`_korrigiere_populismus()`,
`_korrigiere_position()`).

### `deskriptiv_aggregation.py`

| Parameter | Bedeutung |
|---|---|
| `MODUS_LISTE` | Teilmenge von `["populismus", "stance", "erfolg", "erfolg_kriegsvideos"]` — für jeden Wert wird eine eigene Ausgabedatei erzeugt. `"erfolg"` liest `channel_{gran}_erfolg_timeseries.csv`, `"erfolg_kriegsvideos"` liest `channel_{gran}_erfolg_kriegsvideos_timeseries.csv` (beide `prepare_success_metrics.py`, Forschungsfragen 2/4) statt der LLM-Score-Zeitreihen. `"erfolg_kriegsvideos"` steht standardmäßig NICHT in `MODUS_LISTE` — nur ergänzen, wenn `deskriptiv_plots.py::NUR_TOPICVIDEOS` gebraucht wird |
| `GRANULARITAET_LISTE` | Teilmenge von `["quartal", "monat"]` — muss zu vorhandenen Zeitreihen-Dateien passen |
| `BASELINE_PERIODEN` / `MIN_BASELINE_*` | nur für `MODUS = "populismus"`: welche Vorkriegsperioden den Index-Nenner (=100) bilden. `"stance"`, `"erfolg"` und `"erfolg_kriegsvideos"` bekommen keinen Index (bei `"erfolg"`/`"erfolg_kriegsvideos"` bewusst — rohe Views/Engagement werden nicht auf eine Vorkriegsperiode normiert) |
| `MEDIENTYPEN` / `KANAL_WHITELIST` / `KANAL_BLACKLIST` | Kanalfilter, `None` = alle. `KANAL_WHITELIST` zeigt standardmäßig auf `frage1_kanal_whitelist.csv` (Output von `frage1_stichprobe.py`) — gilt für **alle** `MODUS_LISTE`-Werte gleichermaßen (bei `"erfolg"` bereits in `prepare_success_metrics.py` angewendet, hier also ein No-Op-Filter zur Konsistenz); für eine Auswertung ohne diesen Frage-1-spezifischen Filter (z. B. eine eigenständige `stance`-Analyse) auf `None` zurücksetzen |
| `IDEOLOGIE_DIMENSION` / `IDEOLOGIE_SCHNITTE` | Schwellenwerte für links/mitte/rechts-Einteilung |

Exportiert `lade_medientyp()` und `lade_ideologie()` — werden von
`fe_signifikanz_test.py` und `scripts/adhoc/video_sample_uebersicht.py`
importiert (siehe unten). `lade_medientyp()` dedupliziert seit 2026-09-08
automatisch echte Duplikatzeilen desselben `channel_id` in
`data/external/media_type_russia_merged.xlsx` (z. B. "ARTEde"/"WDR aktuell"
waren je zweimal enthalten — ein Pflegefehler in der extern gepflegten
Excel-Datei, entdeckt beim Nachgehen eines auffaellig starken OeRR-Koeffizienten
in `populismuspraemie_kriegsvideos_bericht.py`; ohne Dedup bekamen betroffene
Kanaele bei jedem Merge auf `channel_id` unbemerkt doppeltes Gewicht) und wirft
einen `ValueError`, falls Duplikatzeilen widersprüchliche Medientyp-Werte tragen.

### `deskriptiv_plots.py`

| Parameter | Bedeutung |
|---|---|
| `MODUS` / `GRANULARITAET` | muss zur `deskriptiv_{modus}_{granularitaet}.csv` aus Schritt 1 passen (`"populismus"` \| `"stance"` \| `"erfolg"`). `GRANULARITAET = "monat"` ist Standard (Kanal-Monat als Beobachtungseinheit) |
| `NUR_TOPICVIDEOS` | `True` = nur Kriegsvideos (`ist_kriegsvideo == 1`) statt aller Videos (Forschungsfrage 4) — nur zusammen mit `MODUS = "erfolg"` zulässig (sonst `ValueError`), liest `deskriptiv_erfolg_kriegsvideos_{granularitaet}.csv` (`MODUS = "erfolg_kriegsvideos"` aus Schritt 1 muss vorher gelaufen sein). Standard `False` |
| `SPLIT` | `"keiner"` \| `"medientyp"` \| `"ideologie"` |
| `KANALFILTER_VARIANTEN` | Liste der Plot-Varianten, die `plotte_dimension()` je Dimension erzeugt — Standard `["alle", "beide_perioden"]` (siehe Schritt 2 oben) |
| `NUR_VORKRIEGS_KANAELE` | `True` = globaler Zusatzfilter, wirkt in **allen** Plots dieses Skripts (auch der Variante `"alle"` sowie den Gruppen5/Gruppe4-Übersichten und der Index-Vorkriegsmonat-Variante): behält nur Kanäle mit mindestens einem Wert vor Kriegsbeginn (`SPALTE_PERIODE < 0`), ohne — anders als `"beide_perioden"` — zusätzlich einen Nachkriegswert zu verlangen (`filtere_vorkriegs_kanaele()`). Standard `False` |
| `GRUPPEN5_PLOTTEN` / `GRUPPE5_REIHENFOLGE` | zusätzlicher Übersichtsplot je Dimension mit ÖRR/Traditionelles Medium getrennt + Alternative Medien nach Ideologie gesplittet (`plotte_dimension_gruppen5()`/`baue_gruppe5()`). Standard `False` |
| `GRUPPE4_PLOTTEN` / `GRUPPE4_REIHENFOLGE` | wie `GRUPPEN5_PLOTTEN`, aber ÖRR und Traditionelles Medium zu EINER Gruppe zusammengefasst (`plotte_dimension_gruppe4()`/`baue_gruppe4()`) — primäre Standardansicht für `MODUS = "erfolg"` (Forschungsfrage 2: „Unterschiede zwischen rechten und linken Kanälen?“), dafür explizit auf `True` setzen. Standard `False` |
| `ZEIGE_ROHWERT_PUNKTE` | `False` blendet die rohen Periodenmittel als blasse Punkte in allen Plot-Varianten aus, sodass nur noch die LOWESS-geglätteten Linien zu sehen sind. Standard `True` |
| `ZEIGE_N` | schreibt `n_kanaele` je Periode (und Gruppe, falls `SPLIT` gesetzt) auf die Konsole — gilt für `plotte_dimension()` UND für die Gruppen-Übersichtsplots (`plotte_dimension_gruppen5()`/`plotte_dimension_gruppe4()`, jeweils getrennt für die dünne „alle Kanäle“- und die dicke „beide Perioden“-Linie), also auch für die Alternative-Medien-links/mitte/rechts-Aufspaltung. Standard `True` |

### `frage2_sensitivitaet_plots.py`

| Parameter | Bedeutung |
|---|---|
| `GRANULARITAET` / `KANALFILTER` | fix auf `"monat"` bzw. `"beide_perioden"` — keine weiteren Varianten (siehe Docstring) |
| `WINSOR_GRENZEN` | beide Winsorisierungsgrenzen parallel (`{"winsor_5_95": 0.05, "winsor_1_99": 0.01}`), je eigene Grafik |
| `GEWICHT_EXPONENT` | Exponent für die gedämpfte Zellgewichtung der Aggregationsebene `zellen_gewichtet` (`n_videos ** GEWICHT_EXPONENT`), Standard `0.5` (= `sqrt(n_videos)`) — bewusst gedämpft statt linear (linear wäre identisch mit `video_ebene`) |
| `MIN_KANAELE_PRO_ZELLE` / `MIN_VIDEOS_PRO_ZELLE_VIDEOEBENE` | Mindestbesetzung wie `deskriptiv_plots.py`, zusätzlich eine Videomindestzahl für die Aggregationsebene `video_ebene` |
| `BASELINE_PERIODEN` / `MIN_VIDEOS_BASELINE_GESAMT` | wie `deskriptiv_aggregation.py` (`GRANULARITAETEN["monat"]`) — Basis für die Ausgangsbasen `index_vorkriegsmittel_mean`/`_median` |
| `METRIK_AGGREGATIONSEBENEN` | die Kombinationsmatrix selbst (Metrik → Liste der dafür geplotteten Aggregationsebenen), siehe Moduldocstring für den mathematischen Dedup |
| `BASIS_KONFIG` | die vier möglichen Ausgangsbasen (`absolut`, `index_vorkriegsmittel_mean`, `index_vorkriegsmittel_median`, `subscriber_norm`) mit Achsenbeschriftung, ob die Metrik `"summe"` dort sinnvoll ist, und bei den beiden Index-Basen zusätzlich `baseline_aggregation` (`"mean"`/`"median"`, steuert `berechne_baseline()`). Standardmäßig sind `absolut` und beide Index-Basen aktiv, nur `subscriber_norm` auskommentiert (Stand 2026-09-08 — `absolut` wurde seither aktiviert, u. a. für `main_todo0()`, siehe unten). **`_mean` vs. `_median`**: Die Baseline als Mittelwert (`_mean`, ursprüngliche Definition) liegt bei rechtsschiefen View-Verteilungen (typisch für YouTube) strukturell über dem Median-Video eines Kanals — die Metrik `"median"` landet dadurch systematisch unter Index=100, auch ohne echte Veränderung (Diagnosebeispiel: bei ÖRR lag das Kanal-Mittel im Baseline-Fenster im Median beim 2,14-fachen des jeweiligen Kanal-Medians). `_median` verwendet stattdessen den Kanal-Median als Baseline und ist damit für die Metrik `"median"` konsistent definiert (Index=100 = „gleich wie das eigene mediane Vorkriegsvideo"); wird standardmäßig zusätzlich zu `_mean` erzeugt, zum direkten Vergleich. |
| `BASELINE_AGGREGATIONEN` | **automatisch** aus den aktiven `BASIS_KONFIG`-Einträgen abgeleitet (kein eigenes Config-Flag) — legt fest, welche Baseline-Varianten `main()` tatsächlich berechnet |
| `GLAETTUNG_LOWESS_FRAC` | LOWESS-Glättung jeder der 5 Gruppenlinien (dieselbe Methode wie `deskriptiv_plots.py`/`geglaettete_kurve.py`), reine Darstellungshilfe gegen das Monat-zu-Monat-Zickzack. Standard `0.15`; `0`/`None` = aus (rohe Linie mit Punktmarkern wie vor dieser Option) |
| `ZEIGE_ROHWERT_PUNKTE` | bei aktiver Glättung zusätzlich die rohen Periodenwerte als blasse Punkte einzeichnen. Standard `True`; wirkungslos bei `GLAETTUNG_LOWESS_FRAC = 0` |
| `KOMBI_AKTIV` | `True`/`False` — schaltet die zusätzliche kombinierte Grafik (`erzeuge_kombinierte_grafiken()`) an/aus. Standard `True` |
| `KOMBI_METRIKEN` / `KOMBI_AGGREGATIONSEBENEN` / `KOMBI_BASEN` | je eine **Liste** — das kartesische Produkt daraus ergibt die erzeugten Kombi-Grafiken (mehrere Spezifikationen in einem Lauf möglich). Standard `["median"]` / `["video_ebene"]` / `["index_vorkriegsmittel_mean", "index_vorkriegsmittel_median"]` (Nutzervorgabe: Median, video-Ebene, Index — standardmäßig beide Baseline-Varianten in einem Lauf, zum direkten Vergleich) |
| `KOMBI_HAUPTFOKUS_UMFANG` / `KOMBI_VERGLEICHS_UMFANG` | Umfang für die dicke bzw. dünne Linie je Gruppe5-Kategorie (gleiche Farbe, unterschiedliche Linienstärke). Standard `"topic"` (Kriegsvideos, Hauptfokus) / `"alle"` (Vergleichswert) |
| `KOMBI_HAUPTFOKUS_LINIENBREITE` / `KOMBI_VERGLEICHS_LINIENBREITE` / `KOMBI_VERGLEICHS_ALPHA` | Linienstärke bzw. Transparenz der dicken/dünnen Linie. Standard `2.4` / `1.0` / `0.55` |

**`main_todo0()`** (seit 2026-09-08, `.claude/Aufgaben.md` TODO 0 —
"Vorbereitung: Absolute Views (Summe, Median, winsorisierter Mittelwert) mit
Kriegs- und Nicht-Kriegsvideos im Vergleich zur Baseline"): eigener,
schlanker Einstiegspunkt neben `main()`, NICHT Teil von `__main__` — separat
aufrufen via
`python -c "from frage2_sensitivitaet_plots import main_todo0; main_todo0()"`
(im selben Ordner). Nutzervorgabe: bewusst kurz gehalten, erzeugt genau 3
Grafiken (`TODO0_METRIKEN = ["summe", "median", "winsor_5_95"]`, feste
Aggregationsebene `TODO0_EBENE = "zellen_ungewichtet"` — die einzige, die für
alle drei Metriken gültig ist — feste Basis `TODO0_BASIS = "absolut"`) statt
der vollen Kombinationsmatrix, rührt `main()`/die bestehende
Sensitivitätsmatrix nicht an. Vergleicht Kriegsvideos
(`TODO0_HAUPTFOKUS_UMFANG = "topic"`, dicke Linie) gegen ECHTE
Nichtkriegsvideos (`TODO0_VERGLEICHS_UMFANG = "nicht_topic"`, dünne Linie) —
anders als der bestehende `KOMBI_VERGLEICHS_UMFANG = "alle"`, der
Kriegsvideos mit einmischt. `"nicht_topic"` ist eine neue, dritte
`umfang`-Option (`_video_basis_fuer_umfang()`, gemeinsame Stelle für
`main()`, `erzeuge_kombinierte_grafiken()` und `main_todo0()` — löst die
frühere Code-Duplikation der Umfang-Filterung auf), NICHT Teil von
`UMFAENGE`/der Sensitivitätsmatrix oben (die vergleicht bewusst weiter gegen
`"alle"`). Schreibt
`todo0_trend_{metrik}_topic-vs-nicht_topic_monat.png` nach
`plots_sensitivitaet_frage2/` (kein eigenes Methodik-Dokument). Dafür wurde
`plotte_kombinierte_grafik()` um optionale `hauptfokus_label`/
`vergleichs_label`-Parameter erweitert (Default: die `KOMBI_*_UMFANG`-Werte,
bestehendes Verhalten unverändert) — `main_todo0()` übergibt eigene Labels
("Kriegsvideos"/"Nichtkriegsvideos"), da es andere Umfänge als die
`KOMBI_*_UMFANG`-Globals vergleicht. Ebenso neu ein optionaler
`pfad_plots`-Parameter (Default: das `PFAD_PLOTS` dieses Moduls) — ohne ihn
würde eine Grafik aus einem ANDEREN, importierenden Skript (Python löst
globale Namen einer importierten Funktion im definierenden Modul auf) immer
in `plots_sensitivitaet_frage2/` landen statt im Plot-Ordner des
aufrufenden Skripts; `frage4_kriegspraemie_marktanteil_plots.py` (Schritt
8d) übergibt so ihr eigenes `PFAD_PLOTS`. Ergebnis:
[`zentrale_ergebnisse.md`](../../../outputs/segment_analysis/zentrale_ergebnisse.md).

### `fe_signifikanz_test.py`

| Parameter | Bedeutung |
|---|---|
| `MODUS` / `GRANULARITAET` | wie oben |
| `DIMENSION` | z. B. `"position_russland"` — Spalte aus `channel_video_{populism,position}.csv` |
| `FILTER` | Kanalfilter für die Regression |

### `geglaettete_kurve.py`

Nutzt dieselbe `CONFIG` (`MODUS`, `GRANULARITAET`, `DIMENSION`, `FILTER`,
`PERIODE_MIN`/`_MAX`) wie `fe_signifikanz_test.py` — dort gepflegt, hier nur
importiert (siehe Imports unten).

### `frage1_stichprobe.py`

| Parameter | Bedeutung |
|---|---|
| `ANALYSIS_ID` / `CHANNEL_SAMPLE_PATH` | wie in `prepare_channel_scores.py` |
| `TOPIC_VIDS_PATH` | `scripts/adhoc/output/topic_vids_per_channel.csv` — Quelle für `topic_vids` je Kanal (siehe dortige Erzeugung in `scripts/adhoc/sample_creation_diagnostics.py::create_channel_overview()`) |
| `MIN_KRIEGSVIDEOS` | Schwelle für Stufe 1 des Auswahltrichters (Default 5) |
| `MIN_KLASSIFIZIERTE_VIDEOS` | Schwelle für Stufe 2 des Auswahltrichters — Mindestanzahl klassifizierter Baseline-Videos je Kanal (Default 5, vor 2026-09-04 war die Schwelle `> 0`) |
| `IDEOLOGIE_MIN_VIDEOS_SCHWELLEN` | rein informative Schwellenwerte (Default `[5, 10]`) — wie viele Whitelist-Kanäle hätten mindestens so viele Baseline-Videos in `channel_classification_ideology.csv::n_videos`; filtert die Whitelist NICHT |

### `frage1_populismus_bericht.py`

| Parameter | Bedeutung |
|---|---|
| `DIMENSIONEN` / `KONTROLLGROESSEN` | die vier Populismus-Dimensionen + Gesamtscore; `emotionale_intensitaet` ist als Kontrollgröße markiert |
| `GRANULARITAETEN` | Quartal und Monat, gleichwertig, beide werden geschrieben |
| `GRUPPEN_SPALTEN` | Gruppierungsspalten für den Interaktionstest (Ideologie, Medientyp), mit fester Referenzgruppen-Reihenfolge |
| `MIN_KANAELE_JE_GRUPPE` | unterhalb dieser Kanalzahl wird eine Gruppe aus dem Interaktionstest ausgeschlossen |
| `TEILGRUPPEN_INTERAKTIONEN` | zusätzliche Interaktionstests (Ideologie x Post), vorher auf einen einzelnen Medientyp gefiltert — Standard: nur `"Alternatives Medium"` (größte, ideologisch heterogenste Gruppe; bei ÖRR/Traditionelles Medium/Politiker-Partei zu klein bzw. zu homogen für eine sinnvolle weitere Aufspaltung) |

### `frage1_stance_bericht.py`

Strukturell identische Parameter wie `frage1_populismus_bericht.py` (siehe
oben), abweichend nur:

| Parameter | Bedeutung |
|---|---|
| `PFAD_EINGABE` | `channel_video_position.csv` statt `channel_video_populism.csv` |
| `DIMENSIONEN` / `KONTROLLGROESSEN` | `position_russland` (Haltung gegenüber Russland) + `position_westpolitik` (Haltung gegenüber westlicher Ukraine-Politik); `emotion` ist als Kontrollgröße markiert |
| `PFAD_WHITELIST` | dieselbe `frage1_kanal_whitelist.csv` wie beim Populismus-Bericht (siehe `frage1_methodik_und_stichprobe.md`) |

### `bericht_utils.py`

Kein eigenes CONFIG — `post_dummy_test()` und `interaktions_test()` sind
reine, konfigurationsfreie Funktionen (die aufrufenden Berichte steuern
Fenster/Gruppen über ihre eigenen CONFIG-Konstanten und übergeben
`min_kanaele_je_gruppe` explizit an `interaktions_test()`).

### `prepare_success_metrics.py`

| Parameter | Bedeutung |
|---|---|
| `PFAD_WHITELIST` | `frage1_kanal_whitelist.csv` (dieselbe Whitelist wie Forschungsfrage 1) |
| `TOPIC` | Topic-Schlüssel für `video_registry.get_topic_relevance()` (`"russia_ukraine_war"`) |
| `REFERENZDATUM` | Näherung für `age_days` (kein gespeicherter Fetch-Zeitstempel, siehe Docstring) — reine Kontext-/Diagnosespalte, nicht Teil der Erfolgsmetrik selbst (seit 2026-09-08 aber testweise als Kontrollvariable in `populismuspraemie_kriegsvideos_bericht.py` verwendet, siehe dort) |

Schreibt neben `channel_{gran}_erfolg_timeseries.csv` (alle Videos) zusätzlich
`channel_{gran}_erfolg_kriegsvideos_timeseries.csv` (dieselbe Aggregation, nur
über Videos mit `ist_kriegsvideo == 1`) — Grundlage für
`deskriptiv_plots.py::NUR_TOPICVIDEOS` (Forschungsfrage 4).

Seit 2026-09-08 (`.claude/Aufgaben.md`, letzter Absatz — Nutzervorgabe „Integriere
die Videodauer in die Analyse“) ergänzt `ergaenze_videodauer()` zusätzlich
`duration_seconds`/`log_duration_seconds` je Video (`video_registry.
duration_lookup()`, 100 % Abdeckung auf der Whitelist-Stichprobe) in
`channel_video_erfolg.csv` — Grundlage für die Kontrollvariable und die
längenbeschränkte Sensitivitäts-Teilstichprobe in
`frage4_kriegspraemie_medientyp_bericht.py` und `populismuspraemie_kriegsvideos_
bericht.py` (siehe deren Konfigurationstabellen unten). Vorausgegangene Diagnose:
`scripts/adhoc/videolaenge_diagnose.py`.

Ebenfalls seit 2026-09-08, aber TESTWEISE (Nutzervorgabe „Nimm age_days und
category_id testweise dazu“ — anders als die Videodauer noch keine endgültige
Entscheidung) ergänzt `ergaenze_videokategorie()` zusätzlich `category_id` je Video
(`video_registry.category_id_lookup()`, YouTubes eigene numerische Video-Kategorie,
z. B. „25“ = News & Politics, 100 % Abdeckung) — anders als Medientyp/Ideologie KEINE
kanalkonstante Eigenschaft. Grundlage für die (ebenfalls testweise) Kontrollvariable
in `populismuspraemie_kriegsvideos_bericht.py`, NICHT in
`frage4_kriegspraemie_medientyp_bericht.py` verwendet (Begründung siehe dortiger
Moduldocstring bzw. `populismuspraemie_kriegsvideos_bericht.py`).

### `frage2_erfolg_bericht.py`

| Parameter | Bedeutung |
|---|---|
| `DIMENSIONEN` | `log_views`, `log_views_summe`, `engagement_rate` |
| `GRUPPEN_SPALTEN` | wie Frage 1, plus `populismus_gruppe` (Tertile aus `populismus_gesamt`) |
| `MIN_KANAELE_JE_GRUPPE` | wie Frage 1 (Default 5) |

### `frage3_populismus_erfolg_bericht.py`

| Parameter | Bedeutung |
|---|---|
| `GRANULARITAETEN` | Fenster wie Frage 1/2 |
| `MIN_KANAELE_JE_GRUPPE` | Mindestanzahl Kanäle je `gruppe5`-Kategorie für Baustein (c) (Default 5, wie Frage 1/4) |
| Bausteine (a)/(b) laufen ohne Gruppenfilter auf der gesamten (Whitelist-)Stichprobe, Baustein (c) schlüsselt zusätzlich nach `gruppe5` auf |

### `frage4_kriegsvideos_erfolg_bericht.py`

| Parameter | Bedeutung |
|---|---|
| `DIMENSIONEN` | `log_views`, `engagement_rate` |
| `MIN_VIDEOS_PRO_ZELLE` | Mindestbesetzung je Kanal x Periode x Kriegsvideo-Zelle (Default 3) |

### `frage4_kriegspraemie_medientyp_bericht.py`

| Parameter | Bedeutung |
|---|---|
| `DIMENSIONEN` | `log_views`, `view_count_mean`, `view_count_median`, `view_count_winsor_5_95`, `view_count_winsor_1_99` — mehrere View-Metriken je Zelle als Robustheitscheck |
| `WINSOR_GRENZEN` | beide Winsorisierungsgrenzen parallel (wie `frage2_sensitivitaet_plots.py`) |
| `MIN_VIDEOS_PRO_ZELLE` | wie Schritt 8 (Default 3) |
| `MIN_KANAELE_JE_GRUPPE` | Mindestanzahl Kanäle MIT >= 1 Kriegsvideo-Zelle je `gruppe5`-Kategorie, sonst wird die Gruppe aus dem Interaktionsmodell ausgeschlossen (Default 5, wie Frage 1/2) |
| `PHASEN_AKTIV` | `True` (Standard) = zusätzlich zur Gesamtzeitraum-Analyse je Phase aus `PHASEN` ein eigener Lauf; `False` = nur die Gesamtzeitraum-Analyse (ursprüngliches Verhalten) |
| `PHASEN` | fünf Phasen (`monat_min`/`monat_max` in `rel_monat`, `label`, `beschreibung`) — Nutzervorgabe zur inhaltlichen Periodisierung des Kriegsverlaufs, siehe Moduldocstring für die volle Begründung je Phase |
| `DAUER_TEILSTICHPROBEN_AKTIV` | seit 2026-09-08 (`.claude/Aufgaben.md`, Nutzervorgabe „Integriere die Videodauer... als Kontrollvariable... und eine längen-eingegrenzte Sensitivitäts-Teilstichprobe“). `True` (Standard) = jedes Zeitfenster (Gesamtzeitraum + jede `PHASE`) läuft zusätzlich zur vollen Stichprobe ("voll") je `DAUER_TEILSTICHPROBEN`-Eintrag ein weiteres Mal, gefiltert auf Video-Ebene VOR `aggregiere_zellen()` (`bericht_utils.py::dauer_teilstichprobe()`); `False` = nur die volle Stichprobe |
| `DAUER_TEILSTICHPROBEN` | feste, frei anpassbare Minuten-Intervalle je Sensitivitätslauf (Nutzervorgabe: feste statt perzentilbasierte Grenzen, dafür beliebig erweiterbar als Dict) — Default `kurz_bis_10min` (0–10 Min) und `mittel_3_30min` (3–30 Min); zusätzlich wird in JEDEM Modell `log_duration_mean` (Zellmittel von `log_duration_seconds`) als Kontrollvariable mitgeführt, unabhängig von dieser Konfiguration |
| — (kein eigenes Config-Flag) | seit 2026-09-08 (Nutzervorgabe „Bau jetzt die Upload-Dichte als Kontrollvariable ein“) wird zusätzlich `log_upload_dichte_mean` (Zellmittel, `bericht_utils.py::berechne_upload_dichte()`) in JEDEM Modell mitgeführt, analog `log_duration_mean` — anders als `age_days`/`category_id` (nur in `populismuspraemie_kriegsvideos_bericht.py`, siehe dort) auch HIER ergänzt, weil sie nicht durch `C(periode)` redundant wird (siehe Moduldocstring „UPLOAD-DICHTE“). Seit 2026-09-09 fenster- statt periodenbasiert (log1p der Anzahl anderer Videos desselben Kanals innerhalb von ±48 Stunden um das jeweilige Video) und dadurch granularitätsunabhängig — `lade_video_daten()` berechnet nur noch EINE Spalte `log_upload_dichte` (vorher zwei, je Granularität) |

### `frage4_kriegspraemie_relative_views_plots.py`

| Parameter | Bedeutung |
|---|---|
| `PERIODE_MIN` / `PERIODE_MAX` | Fenster in `rel_monat`, wie `frage2_sensitivitaet_plots.py` (Default `-12`/`48`) |
| `VERGLEICHE` | die drei Vergleichsgruppen (`alle_videos`, `andere_politische_videos`, `andere_politische_videos_topic`) mit Anzeigename, ob zusätzlich auf `politics_final == 1` bzw. `ist_politics_topic == True` gefiltert wird, und der jeweiligen Mindestbesetzung des Nenners |
| `MIN_VIDEOS_KRIEGSVIDEOS` | Mindestbesetzung der Kriegsvideo-Zelle (Zähler, für alle drei Vergleiche identisch, Default `10`) |
| `MIN_VIDEOS_VERGLEICH_ALLE` / `MIN_VIDEOS_VERGLEICH_POLITICS_FINAL` / `MIN_VIDEOS_VERGLEICH_TOPIC` | Mindestbesetzung der Vergleichsgruppen-Zelle (Nenner) je Vergleich, Default je `10` |
| `METRIKEN` | `median`/`mean` — je eine eigene Grafik pro Vergleich |
| `GLAETTUNG_LOWESS_FRAC` | LOWESS-Glättung wie `frage2_sensitivitaet_plots.py`, Default `0.15` |
| `KANON_ANALYSIS_ID` / `KANON_SAMPLE_PFAD` / `KANON_TOPIC` | nur für `lade_basisdaten(kanalquelle="kanon")`: volles kanonisches Sample (`russia_longitudinal_v1`, 427 Kanäle, 367 mit gruppe5) direkt aus der `video_registry` statt der 279er-Whitelist, mit defensivem Dedup von `lade_ideologie()`. Default `kanalquelle="whitelist"` ist unverändert. Genutzt von `scripts/masterarbeit/ap2_marktanteil_stichprobenbias.py` und `scripts/adhoc/marktanteil_vergleich_279_vs_427*.py` |

### `frage4_kriegspraemie_marktanteil_plots.py`

| Parameter | Bedeutung |
|---|---|
| `MIN_VIDEOS_GESAMT_PRO_PERIODE` | Mindestbesetzung, wirkt auf die GESAMTE Periode (Summe über alle 5 Gruppe5-Kategorien), nicht auf einzelne Gruppen — sonst würden die Anteile sich nicht mehr zu 100 % aufsummieren. Default `20` |

### `marktanteil_themen_plots.py`

| Parameter | Bedeutung |
|---|---|
| `ANZEIGE_GRUPPEN` | Name → Liste roher Gruppe5-Kategorien, die zu einer Linie summiert werden (Nenner bleibt immer die Summe über alle 5 rohen Kategorien). Default: die 5 Gruppe5-Kategorien je einzeln; ein kombinierter Typ (z. B. `"ÖRR + Traditionell": ["ÖRR", "Traditionelles Medium"]`) lässt sich hier ergänzen |
| `ANZEIGE_GRUPPEN_AKTIV` | Teilmenge von `ANZEIGE_GRUPPEN.keys()`, die tatsächlich als Linien gezeichnet wird (Typ A) bzw. wofür Typ B eine eigene Grafik bekommt — Default alle |
| `THEMEN` | Themenschlüssel (aus `video_topic_relevance`) → Anzeigetitel — Default alle 5 klassifizierten Themen |
| `THEMEN_AKTIV` | Teilmenge von `THEMEN.keys()`, die tatsächlich geplottet wird — Default alle |
| `MIN_VIDEOS_GESAMT_PRO_PERIODE` | wie 8d (Default `20`) |

### `populismuspraemie_kriegsvideos_bericht.py`

| Parameter | Bedeutung |
|---|---|
| `MODUS` | `"populismus"` (Default) \| `"stance"` — steuert sowohl die Eingabedatei (`DATEINAME_VIDEO_EBENE`, `channel_video_populism.csv` bzw. `channel_video_position.csv`) als auch `DIMENSIONEN` (`DIMENSIONEN_JE_MODUS`) und den Ausgabedateinamen (`{modus}praemie_kriegsvideos_bericht.csv`) |
| `DIMENSIONEN_JE_MODUS` | Gesamtscore + die vier Populismus-Dimensionen (`"populismus"`) bzw. `position_russland`/`position_westpolitik` + Kontrollgröße `emotion` (`"stance"`, wie `frage1_stance_bericht.py`) |
| `MIN_KANAELE_JE_GRUPPE` | Mindestanzahl Kanäle MIT >= 1 klassifiziertem Kriegsvideo je Medientyp bzw. Zeitperiode, sonst Ausschluss aus dem jeweiligen Interaktionsmodell (Default 5, wie Frage 1/2/4b) |
| `ZEITPERIODEN_SPALTE` | Spalte aus `channel_video_erfolg.csv` für Baustein (d), die die Zeit relativ zu `KRIEGSBEGINN` angibt — `"rel_quartal"` (Default) \| `"rel_monat"` |
| `ZEITPERIODEN_GRENZEN` | linke, einschließende Grenzen der Zeitperioden-Bins in Einheiten von `ZEITPERIODEN_SPALTE` (Default `[0, 4, 8]` → Perioden `"< Q0"`, `"Q0-Q3"`, `"Q4-Q7"`, `"Q8+"`); feinere Bins brauchen entsprechend mehr Kanäle pro Bin für `MIN_KANAELE_JE_GRUPPE` |
| `KOMBI_VARIABLEN` | Liste der Dimensionen für Baustein (c), das kombinierte Modell (`log_views ~ KOMBI_VARIABLEN[0] + ... + C(channel_id)`) — unabhängig von `MODUS`, beliebig gemischt aus `channel_video_populism.csv`/`channel_video_position.csv`. Default `["populismus_gesamt", "position_russland"]` |
| `DATEINAME_JE_VARIABLE` | automatisch aus `DIMENSIONEN_JE_MODUS`/`DATEINAME_VIDEO_EBENE` abgeleitete Zuordnung Dimension → Quelldatei, steuert für `KOMBI_VARIABLEN`, welche Datei(en) `lade_kombiniertes_modell_daten()` lädt — nicht händisch anpassen |
| `PFAD_AUSGABE_KOMBI_KORRELATION` | Ausgabepfad der paarweisen Korrelationstabelle zwischen den `KOMBI_VARIABLEN` (Default `outputs/segment_analysis/kombiniertes_modell_korrelation.csv`) |
| `DAUER_TEILSTICHPROBEN_AKTIV` / `DAUER_TEILSTICHPROBEN` | seit 2026-09-08, strukturell identisch zu `frage4_kriegspraemie_medientyp_bericht.py` (dieselben Default-Intervalle, separat gepflegt, siehe dortige Config-Tabelle) — hier läuft bei `True` der GESAMTE `main()`-Ablauf (alle Bausteine a–g) zusätzlich zur vollen Stichprobe je Intervall komplett eigenständig durch (`fuehre_analyse_aus()`, von `main()` je Stichprobe aufgerufen); `log_duration_seconds` wird zusätzlich, unabhängig von dieser Konfiguration, in JEDEM Baustein als Kontrollvariable mitgeführt (Nutzervorgabe: „überall“) |
| `KONTROLLVARIABLEN_FORMEL` / `KONTROLLVARIABLEN_SPALTEN` | an einer Stelle gepflegter Formel-/Spaltenbaustein für ALLE Kontrollvariablen (seit 2026-09-08 `log_duration_seconds + age_days + C(kategorie_gruppe) + log_upload_dichte`), wird automatisch in denselben sieben Bausteinen (a–g) mitgeführt. `age_days`/`category_id` (Nutzervorgabe „Nimm age_days und category_id testweise dazu“) sind TESTWEISE (anders als Videodauer/Upload-Dichte keine „überall“-Endentscheidung, Befund: keine relevante Veränderung ggü. reiner Längenkontrolle) und bekommen KEINE eigene Sensitivitäts-Teilstichprobe; `log_upload_dichte` (seit 2026-09-08, Nutzervorgabe „Bau jetzt die Upload-Dichte als Kontrollvariable ein“, `bericht_utils.py::berechne_upload_dichte()` — seit 2026-09-09 fenster- statt periodenbasiert, siehe dortiger Docstring) ist wie die Videodauer eine feste Ergänzung, ebenfalls ohne eigene Teilstichprobe. Vorher/Nachher-Vergleiche laufen direkt gegen die jeweils vorherigen Läufe (siehe `zentrale_ergebnisse.md`) |
| `INTERAKTIONS_PAARE_POPULISMUS_POSITION` | seit 2026-09-10 (Nutzervorgabe „Setz Punkt 2 mit dem Interaktionsterm um“), Liste von `(position_var, populismus_var)`-Paaren für Baustein (g) — Default `[("position_russland", "populismus_gesamt"), ("position_westpolitik", "populismus_gesamt")]`; für eine Subdimension statt des Gesamtscores (z. B. `antielitismus`) hier einfach ein weiteres Paar ergänzen |
| `KATEGORIE_MIN_VIDEOS` | Mindestanzahl Kriegsvideos je `category_id` (in der jeweils aktiven Stichprobe), unterhalb derer eine Kategorie zu `"Sonstige"` zusammengefasst wird (`_gruppiere_kategorie()`, Default 200) — ohne das hätte `C(kategorie_gruppe)` sehr viele fast leere Dummy-Spalten, da `category_id` video- statt kanalspezifisch ist |

### `select_political_nonwar_targets.py`

| Parameter | Bedeutung |
|---|---|
| `VIDEOS_PER_CELL` | wie viele politische Nicht-Kriegsvideos je Kanal-Periode-Zelle maximal ausgewählt werden (Default 3) |
| `GRANULARITY` | `"monat"` \| `"quartal"`, wie `select_cell_fill_targets()` (Default `"monat"`) |
| `TOPIC` | Topic-Schlüssel für den Kriegsvideo-Ausschluss (`"russia_ukraine_war"`) |

### `schockfenster_bericht.py`

| Parameter | Bedeutung |
|---|---|
| `SCHOCKS` | Dict je Ereignis: `datum` (ISO-String), `label`, `video_filter` (`"alle_videos"` \| `"nur_kriegsvideos"`). Default: `kriegsbeginn` (2022-02-24), `us_wahl_2024`/`us_wahl_2024_kriegsvideos` (2024-11-05, Trump-Wahl) und seit 2026-09-10 `bucha` (2022-04-03, Bekanntwerden des Massakers von Butscha) plus vier Validierungs-Schocks für dasselbe Muster: `olenivka` (2022-07-29, strittige Verantwortung), `isjum` (2022-09-16, Analogon zu Bucha), `nord_stream` (2022-09-26, Kontrastfall mit umstrittener Verantwortung), `annexion_mobilisierung` (2022-09-21, russische Eskalation statt Aufdeckung) — siehe `schockfenster_methodik.md` Abschnitt "Validierungs-Schocks" für die Begründung je Ereignis; weiteres Ereignis: einfach neuen Eintrag ergänzen |
| `FENSTER_BREITEN_TAGE` | Liste der Fensterbreiten in Tagen um jedes Ereignis, alle parallel als eingebaute Sensitivitätsprüfung (Default `[7, 14, 30]`) |
| `HETEROGENITAETS_DIMENSIONEN` | Dict je Dimension: `spalte` + `werte`-Liste für `interaktions_test()`. Default `gruppe5`/`medientyp`/`ideologie_gruppe` — neue Dimension: Spalte muss vorher in `lade_basisdaten()` an die Video-Ebene gemerged sein |
| `METRIKEN` | Liste der Metriken, die als y-Variable durch `post_dummy_test()`/`interaktions_test()` laufen. Default `["view_count", "log_views", "position_russland", "position_westpolitik"]` — die ersten beiden sind Erfolgsmetriken aus `channel_video_erfolg`-Spalten (volle Kanalpopulation), die letzten beiden (seit 2026-09-10) sind aus `channel_video_position.csv` in `lade_basisdaten()` gemergt und nur für die LLM-klassifizierte Teilmenge belegt (NaN wird per `dropna()` automatisch ausgeschlossen, siehe `PFAD_POSITION`) |
| `MIN_KANAELE_JE_GRUPPE` | wie überall sonst in diesem Ordner: Mindestanzahl Kanäle je Gruppe für `interaktions_test()` (Default 5) |

Kanalpopulation kommt NICHT aus `channel_video_erfolg.csv` (Frage-1-Whitelist),
sondern eigenständig über `lade_basisdaten()` aus `video_registry.
get_video_stats()` für alle Kanäle mit Medientyp-Klassifikation (siehe
Abschnitt 10 oben und `.claude/plans/schockfenster_bericht.md`).

### `export_stata_rohdaten.py`

Erzeugt den Stata-Rohdatensatz nach `docs/codebuch_rohdatensatz.md` in
`outputs/stata_rohdaten/` (`videos_roh.dta`, `kanaele_roh.dta`,
`export_log.txt`, `check_rohdaten.do`). Liest ausschließlich aus den Stores
(Original-Runs); bricht bei einem Verstoß gegen die Konsistenzprüfungen des
Codebuchs ab. Steuerung nur über den CONFIG-Block:

| Parameter | Bedeutung |
|---|---|
| `ANALYSIS_ID` / `KANAL_SAMPLE_PFAD` | Kanal-Sample (wie `prepare_channel_scores.py`) |
| `MIN_DAUER_SEK` | Längenfilter der Video-Population (`MIN_VIDEO_DURATION_SECONDS` = 181, also > 180 s) |
| `VORKRIEG_START`, `VORKRIEG_MIN_VIDEOS` | `sample_vorkrieg` = Whitelist UND ≥ n Videos in [24.02.2021, 24.02.2022) |
| `MEDIENTYP_PFAD`, `MEDIENTYP_UMKODIERUNG` | Rohcodes der Excel → Codebuch-Kodierung (3 ↔ 4 getauscht, Typ 5 → ÖRR) |
| `TOPICS`, `KRIEG_TOPIC` | Themen aus `video_topic_relevance` → Exportvariablen (alle Themen aus `TOPIC_KEYWORDS`, Labels von dort; fehlt ein Thema in `TOPICS`, bricht `main()` ab); je Thema und für `krieg` zusätzlich `<name>_core` (nur core-Stichworte) |
| `API_ABBRUCH_PFAD` | Kanäle mit Flag `playlist_limit` (nachgescrapt) → `api_abbruch` |
| `KANAL_HINWEISE` | Freitext je Kanal für `kanal_hinweis` |
| `BASELINE_TOLERANZ` | Toleranz für Prüfung 6 (Baseline-Nachberechnung) |

Abweichungen von `prepare_channel_scores.py`: LLM-Ergebnisse werden auf
Segmentebene dedupliziert (dort Videoebene; beim Lauf vom 02.10.2026
identisches Ergebnis, weil alle Mehrfach-Runs ganze Videos umfassten); Kanal-
Baselines nach `channel_id` statt `channel_id` + `channel_title`;
Ideologie-Baseline nur aus Baseline-Videos ohne Kriegsbezug.

## Ausführung

`prepare_channel_scores.py` und `prepare_success_metrics.py`, wie die
entsprechenden Skripte in `step1`–`step5`, als Paketmodul:

```
PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.prepare_channel_scores
PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.prepare_success_metrics
PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.select_political_nonwar_targets
PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.schockfenster_bericht
PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.export_stata_rohdaten
PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.marktanteil_rohdaten_plots
```

`prepare_success_metrics.py` importiert `GRANULARITAETEN`/
`ergaenze_periodenspalten()` aus `prepare_channel_scores.py` als echten
Paketimport (`from youtube_code.step6_auswertung.prepare_channel_scores
import ...`) — deshalb `-m`-Modul, nicht bare sibling import.
`select_political_nonwar_targets.py` importiert ebenso als echten Paketimport
`select_cell_fill_targets` aus `step4_transcript_download.select_targets`
(andere Verzeichnisebene) — deshalb ebenfalls `-m`-Modul.
`schockfenster_bericht.py` importiert sowohl `youtube_code.store.
video_registry` als auch mehrere Sibling-Module (`deskriptiv_aggregation`,
`deskriptiv_plots`, `prepare_success_metrics`, `bericht_utils`) als echte
Paketimporte — ebenfalls `-m`-Modul, nicht bare sibling import (anders als
z. B. `frage2_sensitivitaet_plots.py`, das dieselben Sibling-Module bare
importiert, aber `video_registry` nicht direkt braucht).

`frage1_stichprobe.py`, `deskriptiv_aggregation.py`, `deskriptiv_plots.py`,
`frage2_sensitivitaet_plots.py`, `fe_signifikanz_test.py`,
`geglaettete_kurve.py`, `bericht_utils.py`, `frage1_populismus_bericht.py`,
`frage1_stance_bericht.py`, `frage2_erfolg_bericht.py`,
`frage3_populismus_erfolg_bericht.py`,
`frage4_kriegsvideos_erfolg_bericht.py`,
`frage4_kriegspraemie_medientyp_bericht.py`,
`frage4_kriegspraemie_relative_views_plots.py`,
`frage4_kriegspraemie_marktanteil_plots.py`, `marktanteil_themen_plots.py` und
`populismuspraemie_kriegsvideos_bericht.py` dagegen **direkt im Ordner
ausführen** (`python deskriptiv_aggregation.py` usw.), nicht als `-m`-Modul:
`fe_signifikanz_test.py` importiert `deskriptiv_aggregation`,
`geglaettete_kurve.py` importiert `fe_signifikanz_test`,
`frage2_sensitivitaet_plots.py` importiert `deskriptiv_aggregation` UND
`deskriptiv_plots` (für `GRUPPE5_REIHENFOLGE`),
`frage4_kriegspraemie_medientyp_bericht.py` importiert zusätzlich
`frage2_sensitivitaet_plots` (für `winsorisiere()`),
`frage4_kriegspraemie_relative_views_plots.py` importiert ebenfalls
`frage2_sensitivitaet_plots` (für `baue_gruppe5_lokal()` und `glaette()`)
sowie `deskriptiv_aggregation`/`deskriptiv_plots` direkt,
`frage4_kriegspraemie_marktanteil_plots.py` importiert
`plotte_kombinierte_grafik` aus `frage2_sensitivitaet_plots` (mit
explizitem `pfad_plots`-Argument, siehe dortige Config-Tabelle) sowie
`lade_basisdaten`/`SPALTE_PERIODE` aus
`frage4_kriegspraemie_relative_views_plots`,
`marktanteil_themen_plots.py` importiert `plotte_kombinierte_grafik`
UND `plotte_kombination` aus `frage2_sensitivitaet_plots` (beide seit
2026-09-10 mit optionalen `gruppen_liste`/`gruppen_spalte`/`pfad_plots`-
Parametern, siehe dortige Docstrings), `lade_basisdaten`/`SPALTE_PERIODE`
aus `frage4_kriegspraemie_relative_views_plots` sowie
`berechne_marktanteile`/`pruefe_summe_100` aus
`frage4_kriegspraemie_marktanteil_plots` (Schritt 8d, echter Import statt
Duplikat) und `get_topic_relevance` aus `youtube_code.store.video_registry`,
`populismuspraemie_kriegsvideos_bericht.py` importiert `deskriptiv_aggregation`
(für `lade_medientyp()`) als bare sibling import, und
`frage1_populismus_bericht.py`/`frage1_stance_bericht.py`/
`frage2_erfolg_bericht.py`/`frage4_kriegsvideos_erfolg_bericht.py`/
`frage4_kriegspraemie_medientyp_bericht.py`/`populismuspraemie_
kriegsvideos_bericht.py` (die beiden letzteren seit 2026-09-08, für
`dauer_teilstichprobe()`) importieren `bericht_utils` jeweils als
**bare sibling import** (kein
`youtube_code.step6_auswertung....`-Pfad) — das funktioniert nur, wenn
Python das Skriptverzeichnis selbst auf `sys.path[0]` legt, also bei
direkter Ausführung im selben Ordner. Diese Entscheidung ist bewusst so
belassen (siehe `.claude/restructuring/RESTRUCTURING_PROGRESS.md`): eine
Umstellung auf Paket-relative Importe würde diesen Ausführungsweg brechen.

## Zusammenhang mit `scripts/adhoc/`

Mehrere reine Diagnose-/Ad-hoc-Skripte, die auf denselben Zwischen-
ergebnissen aufsetzen, liegen bewusst **nicht** hier, sondern in
`scripts/adhoc/` (gemäß `.claude/CLAUDE.md`) — u. a.:

- `check_baseline_coverage.py` — für Kanäle ohne Baseline-Klassifikation,
  die laut `video_registry.sqlite` im/vor dem Baseline-Fenster existierten:
  wie viele ihrer Videos sind (nicht) klassifiziert.
- `finde_download_kandidaten.py` — findet für dünn besetzte
  Kanal-Perioden-Zellen konkrete unklassifizierte Kriegsvideo-Kandidaten zum
  Nachdownloaden.
- `video_sample_uebersicht.py` — Übersicht über bereits klassifizierte
  Videos nach Medientyp×Periode, identifiziert dünn besetzte Zellen
  (Grundlage für `finde_download_kandidaten.py`). Importiert
  `lade_medientyp()` aus diesem Ordner als echten Paketimport
  (`from youtube_code.step6_auswertung.deskriptiv_aggregation import lade_medientyp`),
  da es — anders als die vier Skripte oben — in einem anderen Verzeichnis
  liegt als `deskriptiv_aggregation.py`.
- `videolaenge_diagnose.py` (2026-09-08) — Diagnose zum letzten Absatz aus
  `.claude/Aufgaben.md` (Videolänge als möglicher Störfaktor): Verteilung
  der Videolänge je Gruppe5 x Kriegsvideo-Flag sowie eine Kanal-FE-
  Regression `log_views ~ log_duration_seconds` (Within-Schätzer statt
  `C(channel_id)`, siehe Moduldocstring). Dieser Befund ("Videolänge ist
  ein relevanter Störfaktor") hat noch am selben Tag zur Integration von
  `duration_seconds`/`log_duration_seconds` in `prepare_success_metrics.py`
  sowie zur Kontrollvariable/Sensitivitäts-Teilstichprobe in
  `frage4_kriegspraemie_medientyp_bericht.py`/`populismuspraemie_
  kriegsvideos_bericht.py` geführt (siehe deren Abschnitte oben) — dieses
  Diagnose-Skript bleibt trotzdem als eigenständige, rein deskriptive
  Zusatzauswertung bestehen und liest die Dauer inzwischen direkt aus
  `channel_video_erfolg.csv` (kein eigener `duration_lookup()`-Aufruf mehr).
  Importiert `lade_medientyp()`/`lade_ideologie()`/`GRUPPE5_REIHENFOLGE` als
  echte Paketimporte (wie `video_sample_uebersicht.py`); `baue_gruppe5_
  lokal()` aus `frage2_sensitivitaet_plots.py` ist NICHT paketimportierbar
  (dessen eigene bare-sibling-Importe) und wird deshalb als kurze lokale
  Kopie nachgebildet. Ergebnis: `outputs/segment_analysis/
  zentrale_ergebnisse.md` Abschnitt "Videolänge: Diagnose".

Alle setzen `prepare_channel_scores.py` (Schritt 0 hier) voraus
(`videolaenge_diagnose.py` zusätzlich `prepare_success_metrics.py`,
Schritt 0c).

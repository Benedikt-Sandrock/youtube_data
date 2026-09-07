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
    fe_signifikanz_test.py               2b: FE-Regression + Robustheitschecks
    geglaettete_kurve.py                 2c: LOWESS-Kurve + Cluster-Bootstrap-CI
    bericht_utils.py                     gemeinsame Regressions-Bausteine
                                              (post_dummy_test/interaktions_test)
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
   Whitelist gefiltert. Zwei Bausteine: (a) Panel-Regression mit Kanal-FE
   UND Perioden-FE (`log_views ~ populismus_gesamt + C(channel_id) +
   C(periode)`, kontrolliert gemeinsame Zeittrends, rein korrelativ — keine
   Kausalaussage), (b) Δ-Δ-Korrelation je Kanal (`mean(post) - mean(pre)`
   für Populismus und Erfolg, Pearson/Spearman + OLS, mit Scatterplot).
   Schreibt `frage3_populismus_erfolg_bericht_{granularitaet}.csv` und
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
importiert (siehe unten).

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
| `REFERENZDATUM` | Näherung für `age_days` (kein gespeicherter Fetch-Zeitstempel, siehe Docstring) — reine Kontext-/Diagnosespalte, nicht Teil der Erfolgsmetrik |

Schreibt neben `channel_{gran}_erfolg_timeseries.csv` (alle Videos) zusätzlich
`channel_{gran}_erfolg_kriegsvideos_timeseries.csv` (dieselbe Aggregation, nur
über Videos mit `ist_kriegsvideo == 1`) — Grundlage für
`deskriptiv_plots.py::NUR_TOPICVIDEOS` (Forschungsfrage 4).

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
| Kein Gruppenfilter — beide Bausteine laufen auf der gesamten (Whitelist-)Stichprobe |

### `frage4_kriegsvideos_erfolg_bericht.py`

| Parameter | Bedeutung |
|---|---|
| `DIMENSIONEN` | `log_views`, `engagement_rate` |
| `MIN_VIDEOS_PRO_ZELLE` | Mindestbesetzung je Kanal x Periode x Kriegsvideo-Zelle (Default 3) |

## Ausführung

`prepare_channel_scores.py` und `prepare_success_metrics.py`, wie die
entsprechenden Skripte in `step1`–`step5`, als Paketmodul:

```
PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.prepare_channel_scores
PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.prepare_success_metrics
```

`prepare_success_metrics.py` importiert `GRANULARITAETEN`/
`ergaenze_periodenspalten()` aus `prepare_channel_scores.py` als echten
Paketimport (`from youtube_code.step6_auswertung.prepare_channel_scores
import ...`) — deshalb `-m`-Modul, nicht bare sibling import.

`frage1_stichprobe.py`, `deskriptiv_aggregation.py`, `deskriptiv_plots.py`,
`fe_signifikanz_test.py`, `geglaettete_kurve.py`, `bericht_utils.py`,
`frage1_populismus_bericht.py`, `frage1_stance_bericht.py`,
`frage2_erfolg_bericht.py`, `frage3_populismus_erfolg_bericht.py` und
`frage4_kriegsvideos_erfolg_bericht.py` dagegen **direkt im Ordner
ausführen** (`python deskriptiv_aggregation.py` usw.), nicht als `-m`-Modul:
`fe_signifikanz_test.py` importiert `deskriptiv_aggregation`,
`geglaettete_kurve.py` importiert `fe_signifikanz_test`, und
`frage1_populismus_bericht.py`/`frage1_stance_bericht.py`/
`frage2_erfolg_bericht.py`/`frage4_kriegsvideos_erfolg_bericht.py`
importieren `bericht_utils` jeweils als **bare sibling import** (kein
`youtube_code.step6_auswertung....`-Pfad) — das funktioniert nur, wenn
Python das Skriptverzeichnis selbst auf `sys.path[0]` legt, also bei
direkter Ausführung im selben Ordner. Diese Entscheidung ist bewusst so
belassen (siehe `.claude/restructuring/RESTRUCTURING_PROGRESS.md`): eine
Umstellung auf Paket-relative Importe würde diesen Ausführungsweg brechen.

## Zusammenhang mit `scripts/adhoc/`

Drei reine Diagnose-/Ad-hoc-Skripte, die auf denselben Zwischenergebnissen
aufsetzen, liegen bewusst **nicht** hier, sondern in `scripts/adhoc/`
(gemäß `.claude/CLAUDE.md`):

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

Alle drei setzen `prepare_channel_scores.py` (Schritt 0 hier) voraus.

# Relative Views von Kriegsvideos vs. anderen Videos (neues Skript)

## Kontext

TODO 1 in `.claude/Aufgaben.md` ("Kriegsprämie": Erzielen Kriegsvideos für bestimmte Medientypen/
Ideologien verglichen mit anderen (politischen) Videos überdurchschnittlich viele Views?) wird bisher
nur formal über eine FE-Regression beantwortet (`frage4_kriegspraemie_medientyp_bericht.py`). Der
Nutzer möchte zusätzlich eine direkte, deskriptive Zeitreihe der **relativen** Views: Kriegsvideos
verglichen mit (1) allen anderen Videos und (2) nur anderen **politischen** Videos (Klassifikation
`politics_final` aus `data/store/screening_state.sqlite`), auf Video-Ebene, für Median UND Mittelwert.
Kein Ad-hoc-Skript (§ CLAUDE.md) — dauerhaft nutzbare Ergänzung zur Schritt-6-Pipeline, daher neue
Datei in `src/youtube_code/step6_auswertung/`.

**Vom Nutzer bestätigte Parameter (siehe AskUserQuestion im Chatverlauf):**
- Aufschlüsselung nach Gruppe5 (ÖRR, Traditionelles Medium, Alternative Medien links/mitte/rechts) —
  wie in `frage2_sensitivitaet_plots.py`/`frage4_kriegspraemie_medientyp_bericht.py`.
- Darstellung als Zeitreihe pro Monat (`rel_monat`), nicht als einzelne Gesamtkennzahl.
- `politics_final` trotz eingeschränkter Abdeckung verwenden (Limitation dokumentieren). Kriegsvideos
  selbst werden NICHT nach `politics_final` gefiltert — sie gehen vollständig (unabhängig davon, ob
  sie je gescreent wurden) in beide Vergleiche als Zähler ein; nur die jeweilige Vergleichsgruppe
  (Nenner) wird bei Vergleich 2 zusätzlich auf `politics_final == 1` eingeschränkt.

## Diagnose: `politics_final`-Abdeckung (siehe Chatverlauf)

`screening_state.sqlite` ist eine **zufällige** (seed-basierte `stable_random_key`, NICHT nach Views
sortierte) Stichprobe von Kandidaten je Kanal×3-Monats-Intervall aus dem longitudinalen
Politik-Screening (`step2_baseline_channels/`) — keine erschöpfende Klassifikation aller Videos.
Deckungsgrad gegen `channel_video_erfolg.csv` (857.271 Videos, Stand Diagnose):
- Insgesamt nur **~12 %** der Videos haben überhaupt einen `screening_state`-Eintrag.
- Von den 806.474 Nicht-Kriegsvideos haben 96.877 einen Eintrag (44.120 `politics_final == 1`,
  46.527 `== 0`, 6.230 `== -1` unklar/wartend).
- Von den 50.797 Kriegsvideos haben nur 5.473 einen Eintrag (4.597 politisch, 767 nicht, 109 unklar)
  — irrelevant für die Zählerseite, da Kriegsvideos ungefiltert eingehen (s.o.), aber es zeigt: die
  meisten Kriegsvideos wurden nie durchs longitudinale Screening gezogen (das Kriegsvideo-Flag stammt
  aus einer separaten Keyword-Klassifikation, `classify_topic_relevance.py`, nicht aus dem
  Politik-Screening).

Da die Auswahl nachweislich zufällig (nicht view-sortiert) ist, ist KEINE systematische
View-Verzerrung durch die Stichprobenziehung selbst zu erwarten — die Limitation ist rein eine
Frage der (reduzierten) Zellbesetzung/statistischen Power, nicht der Repräsentativität. Wird in der
Methodik-Datei explizit dokumentiert (wie die Subscriber-Snapshot-Limitation in
`frage2_sensitivitaet_plots.py`).

## Metrik: Index (relative Views)

Für jede Zelle (Gruppe5-Kategorie × `rel_monat`) und jeden Vergleich (`alle_videos` /
`andere_politische_videos`) wird gepoolt (alle Videos der Gruppe/Periode direkt zusammengefasst,
KEINE Kanal-Zwischenaggregation — "auf der Video-Ebene", Nutzervorgabe) je einmal für Median und
Mittelwert berechnet:

```
index = median(view_count | Kriegsvideos in Zelle) / median(view_count | Vergleichsgruppe in Zelle) * 100
index = mean(view_count | Kriegsvideos in Zelle)   / mean(view_count | Vergleichsgruppe in Zelle)   * 100
```

`index == 100` bedeutet "Kriegsvideos performen genauso gut wie die Vergleichsgruppe" — wird als
gestrichelte horizontale Referenzlinie bei y=100 eingezeichnet (zusätzlich zur bestehenden
Kriegsbeginn-Vertikale bei Periode −0.5). `index > 100` = Kriegsprämie, `< 100` = Kriegsabschlag.

Zwei Vergleichsgruppen (Nenner), Kriegsvideo-Zähler ist für beide identisch:
- **`alle_videos`**: `ist_kriegsvideo == 0` (unabhängig von `politics_final`).
- **`andere_politische_videos`**: `ist_kriegsvideo == 0 AND politics_final == 1`.

→ 2 Vergleiche × 2 Metriken (Median/Mittelwert) = **4 Liniendiagramme**, je 5 Linien (Gruppe5).

Mindestbesetzung je Zelle (Zähler UND Nenner müssen die Schwelle separat erreichen, sonst wird die
Zelle als fehlender Punkt übersprungen — wie `MIN_VIDEOS_PRO_ZELLE_VIDEOEBENE` in
`frage2_sensitivitaet_plots.py`): `MIN_VIDEOS_KRIEGSVIDEOS = 10` (Zähler, für beide Vergleiche
identisch), `MIN_VIDEOS_VERGLEICH_ALLE = 10` (Nenner bei `alle_videos`),
`MIN_VIDEOS_VERGLEICH_POLITICS_FINAL = 10` (Nenner bei `andere_politische_videos` — trotz
geringerer Abdeckung zunächst dieselbe Schwelle wie bei `alle_videos`, damit beide Vergleiche direkt
vergleichbar bleiben; bei zu vielen übersprungenen Zellen in der Praxis ggf. absenken).

## Datenquelle und Wiederverwendung

- `outputs/segment_analysis/channel_video_erfolg.csv` (Video-Ebene, bereits Whitelist-gefiltert,
  Schritt 0c) — dieselbe Quelle wie `frage2_sensitivitaet_plots.py`/
  `frage4_kriegspraemie_medientyp_bericht.py`.
- `screening_state_store.get_state()` (`politics_final`), Merge über `video_id`.
- `deskriptiv_aggregation.lade_medientyp()` / `lade_ideologie()` — Kanalmerkmale.
- `frage2_sensitivitaet_plots.baue_gruppe5_lokal()` und `.glaette()` — als echter Import
  wiederverwendet (kein Duplikat), analog zu `frage4_kriegspraemie_medientyp_bericht.py`, das
  bereits `winsorisiere()` von dort importiert (siehe README, Abschnitt "Ausführung").
  `GRUPPE5_REIHENFOLGE` kommt (wie bei `frage2_sensitivitaet_plots.py`) direkt aus
  `deskriptiv_plots.py`.

**Kein** Kanalfilter "beide_perioden": die Zellen werden direkt aus gepoolten Videos gebildet, nicht
aus Kanal-Zeitreihen — ein Kanalfilter auf gemeinsame Vor-/Nachkriegsaktivität ist für eine reine
Video-Pool-Kennzahl nicht nötig und würde die (ohnehin schon knappe) Kriegsvideo-Stichprobe weiter
verkleinern. `PERIODE_MIN=-12`/`PERIODE_MAX=48` (`rel_monat`) wie in `frage2_sensitivitaet_plots.py`,
zur Vergleichbarkeit der Fenstergrenzen über die Skripte hinweg.

## Neue Datei

`src/youtube_code/step6_auswertung/frage4_kriegspraemie_relative_views_plots.py` — läuft direkt als
Skript (sibling-Import von `frage2_sensitivitaet_plots`/`deskriptiv_plots`/`deskriptiv_aggregation`,
kein `-m`, wie die übrigen `step6_auswertung`-Dateien außer `prepare_*`).

**Struktur:**
1. `lade_basisdaten()` — `channel_video_erfolg.csv` einlesen, Medientyp/Ideologie/`gruppe5` ergänzen
   (`baue_gruppe5_lokal()`), `politics_final` aus `screening_state_store.get_state()` mergen, auf
   `PERIODE_MIN`/`PERIODE_MAX` filtern.
2. `baue_vergleichsgruppen(df)` — liefert die beiden Vergleichsgruppen-DataFrames
   (`ist_kriegsvideo == 0`, ggf. zusätzlich `politics_final == 1`) plus das gemeinsame
   Kriegsvideo-DataFrame (`ist_kriegsvideo == 1`).
3. `berechne_index(kriegsvideos, vergleich, metrik)` — group by (`rel_monat`, `gruppe5`), Median/
   Mittelwert je Seite, Mindestbesetzungsfilter, Index-Berechnung.
4. `plotte_index(...)` — 5 Linien (Gruppe5-Reihenfolge), LOWESS-geglättet (`glaette()` aus
   `frage2_sensitivitaet_plots`), Kriegsbeginn-Vertikale + **neue** y=100-Referenzlinie.
5. `schreibe_methodik(...)` — Pflichtdokumentation (siehe
   `document-comparative-analysis-methodology`): Index-Formel, Mindestbesetzung,
   `politics_final`-Abdeckungs-Limitation mit den obigen Diagnosezahlen.
6. `main()` — iteriert über 2 Vergleiche × 2 Metriken, ruft `berechne_index()` + `plotte_index()`.

**Config-Konstanten am Dateikopf** (Stil wie die übrigen Skripte): `PERIODE_MIN=-12`,
`PERIODE_MAX=48`, `MIN_VIDEOS_KRIEGSVIDEOS=10`, `MIN_VIDEOS_VERGLEICH_ALLE=10`,
`MIN_VIDEOS_VERGLEICH_POLITICS_FINAL=10`, `GLAETTUNG_LOWESS_FRAC=0.15` (dieselbe Methode wie die
übrigen Skripte), `PFAD_PLOTS = OUTPUTS / "segment_analysis" / "plots_frage4_kriegspraemie_relative_views"`.

## Output

- `outputs/segment_analysis/plots_frage4_kriegspraemie_relative_views/
  kriegspraemie_relative_views_{vergleich}_{metrik}_monat.png` (4 Dateien: `vergleich` ∈
  {`alle_videos`, `andere_politische_videos`}, `metrik` ∈ {`median`, `mean`}).
- `.../kriegspraemie_relative_views_methodik.md` — Index-Formel, Mindestbesetzung,
  `politics_final`-Abdeckungs-Limitation (Pflichtdokumentation).

## Docstrings/READMEs anpassen

`src/youtube_code/step6_auswertung/README.md`: neuer Eintrag im Ablauf (nach
`frage4_kriegspraemie_medientyp_bericht.py`, als weitere 8b/8c-Ergänzung), Config-Tabelle, Hinweis in
"Ausführung" (sibling-Import von `frage2_sensitivitaet_plots`).

## Verifikation

- Skript NICHT selbstständig ausführen (857k Videos + Merge gegen `screening_state.sqlite`,
  767k Zeilen — laut CLAUDE.md vor Testläufen mit größerem Rechenaufwand explizit nachfragen).
- Nach Freigabe: `PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe
  frage4_kriegspraemie_relative_views_plots.py` (im Ordner `step6_auswertung/` ausgeführt),
  Konsolenausgabe auf übersprungene Zellen (Mindestbesetzung) prüfen, 4 PNGs + Methodik-Datei
  verifizieren, stichprobenartig gegen `frage4_kriegspraemie_medientyp_bericht.py`-Ergebnisse
  (Vorzeichen/Größenordnung der Kriegsprämie je Gruppe) auf Plausibilität vergleichen.

## Update 2026-09-08: dritte Vergleichsgruppe `andere_politische_videos_topic`

Umgesetzt im Rahmen von `.claude/plans/lies-aufgaben-md-in-claude-compressed-cascade.md`
(Nutzervorgabe): `politics_final` deckt nur ~12 % der Videos ab (Zufallsstichprobe aus dem
longitudinalen Screening). Als deutlich breiter besetzte, ERGÄNZENDE Alternative wurde
`video_details.topic_categories` (YouTube-eigene Themenkategorisierung, Kategorie
"Politics") herangezogen — neue Hilfsfunktionen `video_registry.is_politics_topic()`/
`politics_topic_lookup()`. Abdeckung auf der Whitelist: 99,7 % der Videos haben einen
`video_details`-Eintrag, 53,9 % davon Kategorie "Politics" (vs. 11,9 % `politics_final`-
Abdeckung). `VERGLEICHE` um `andere_politische_videos_topic` erweitert (jetzt 6 statt 4
PNGs: 3 Vergleiche × 2 Metriken), `politics_final`-Vergleich bleibt unverändert bestehen —
beide Klassifikationen sind inhaltlich unterschiedlich (siehe Moduldocstring des Skripts)
und ergänzen sich, ersetzen sich nicht. Dieselbe `topic_categories`-Klassifikation ist
zusätzlich Grundlage des neuen Geschwisterskripts
`frage4_kriegspraemie_marktanteil_plots.py` (Marktanteils-Zusatzfrage aus TODO 1).

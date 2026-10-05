# Kriegsprämie: Vergleichsgruppen-Dimension + alternative Beobachtungseinheiten

## Kontext

TODO 1 in `.claude/Aufgaben.md` ("Kriegsprämie") wird bisher über
`frage4_kriegspraemie_medientyp_bericht.py` mit EINER Beobachtungseinheit
beantwortet: Kanal×Periode×`ist_kriegsvideo`-Zellen (Baustein 1: je Gruppe5,
Baustein 2: gepoolt) — bereits produktiv gelaufen, Zahlen in
`outputs/segment_analysis/zentrale_ergebnisse.md` (Abschnitt "TODO 1:
Kriegsprämie") berichtet.

Im Chat vom 2026-09-08 wurden dazu zwei Erweiterungswünsche besprochen:

1. **Zwei neue Beobachtungseinheiten "ausprobieren"** (Nutzer-Zitat): Video-
   Ebene (keine Aggregation, "in dem Wissen, dass große Kanäle dann
   dominieren werden") und Kanal-Monats-Zelle mit dem **Anteil** der
   Kriegsvideos als Haupt-Prädiktor statt der `ist_kriegsvideo`-Dummy.
   → als Baustein 3 (Video-Ebene) und Baustein 4 (Anteil-Design) bereits als
   Code in `frage4_kriegspraemie_medientyp_bericht.py` umgesetzt (siehe
   unten, "Bereits umgesetzt"), **aber noch nie gelaufen**.
2. **Neue Vergleichsgruppen-Dimension**: die "sonstigen Videos" (Nenner/
   Vergleich zu den Kriegsvideos) sollen wahlweise ALLE sonstigen Videos
   ODER nur andere **politische** Videos sein — UND ZWAR NICHT NUR für
   Baustein 3, sondern auch rückwirkend für die bereits produktiven
   Bausteine 1/2 (Nutzer-Zitat: "Das soll bei Baustein 1 und 2 aber auch
   geschehen"). Beide Varianten sollen nebeneinander laufen (nicht nur
   eine ersetzen).

Dieser Plan hält fest, was schon umgesetzt ist, was noch zu entscheiden ist,
und in welcher Reihenfolge wir das umsetzen — **vor** dem nächsten
Implementierungsschritt zur Bestätigung.

## Bereits umgesetzt (diese Session, ungelaufen)

In `src/youtube_code/step6_auswertung/frage4_kriegspraemie_medientyp_bericht.py`:

- `kriegspraemie_je_gruppe_test()`/`kriegspraemie_gesamt_test()` generalisiert
  um Parameter `treatment_var`/`kontroll_spalten` (Default identisch zum
  bisherigen Verhalten — Baustein 1/2 unverändert, weiterhin über die
  unangetastete `_fuehre_lauf_aus()`).
- Neue gemeinsame Funktion `_teste_und_baue_zeilen()` (Modell aufrufen,
  drucken, Zeilen bauen) — von Baustein 3/4 genutzt.
- **Baustein 3** (`_fuehre_lauf_video_ebene()`): `ist_kriegsvideo:C(gruppe5)`
  auf Video-Ebene (keine Zellenaggregation), Kontrollen als Video-eigene
  Werte (`log_duration_seconds`, `log_upload_dichte_{granularität}`). Bisher
  NUR Gesamtzeitraum + volle Stichprobe, BEIDE Granularitäten (Quartal UND
  Monat).
- **Baustein 4** (`_fuehre_lauf_anteil()`, `aggregiere_kanal_periode_
  anteil()`): Kanal×Periode-Zellen ohne `ist_kriegsvideo`-Split,
  `anteil_kriegsvideos = n_kriegsvideos / n_videos_gesamt` als (mit
  `gruppe5` interagierte) erklärende Variable. Bisher NUR Gesamtzeitraum +
  volle Stichprobe, beide Granularitäten.
- Docstring von `frage4_kriegspraemie_medientyp_bericht.py`,
  `frage2_4_methodik_und_stichprobe.md` (Abschnitt 7) und `README.md`
  (Punkt 8b) bereits um die Beschreibung dieser zwei Bausteine ergänzt.

**Zeilenzahlen-Check (siehe Chatverlauf):** Baustein 4 ist unproblematisch
(5.255 Zellen Quartal / 14.722 Zellen Monat, ähnliche Größenordnung wie
Baustein 1/2's 6.601 Zellen). Baustein 3 ist das eigentliche Speicher-/
Laufzeitthema: **824.186 Videos** (Quartal-Fenster) bzw. **782.786** (Monat-
Fenster) auf Video-Ebene, mit `C(channel_id)` (≈260 Dummies) +
`C(periode)` (≈20–60 Dummies) als dichte Design-Matrix — grob 2 GB allein
für die Matrix, mehrere GB transient für die OLS-Lösung.

## In diesem Chat bereits entschiedene Punkte

1. **Baustein 3 nur EINE Granularität (Quartal), nicht beide.** Begründung:
   der Grund für "Quartal primär, Monat als Zusatzcheck" bei Baustein 1/2
   ist die dünnere Zellbesetzung auf Monatsebene — entfällt bei Baustein 3
   komplett, da dort gar nicht aggregiert wird (jedes Video bleibt ohnehin
   eine eigene Zeile, unabhängig von der Granularität). Der einzige
   verbleibende Unterschied wäre die Auflösung der Perioden-FE, kein
   ausreichender Grund für zwei separate, teure Läufe. → **TODO: Code in
   `_fuehre_lauf_video_ebene()`-Aufruf in `main()` auf `granularitaet ==
   "quartal"` beschränken statt über beide `GRANULARITAETEN` zu loopen.**
2. **Baustein 3 bekommt zusätzlich die Längen-Teilstichproben**
   (`DAUER_TEILSTICHPROBEN`, wie Baustein 1/2) statt nur der vollen
   Stichprobe — reduziert die Zeilenzahl in den Teilstichproben spürbar
   und verbessert die Vergleichbarkeit von Kriegs-/Nichtkriegsvideos
   (deckt sich mit der bereits dokumentierten Längenproblematik, Abschnitt
   "Videolänge" in `zentrale_ergebnisse.md`).
3. **Neue Vergleichsgruppen-Dimension, BEIDE Varianten parallel, für
   Baustein 1, 2 UND 3** (Nutzervorgabe): "sonstige Videos" (Nenner) wahl-
   weise (a) alle sonstigen Videos (Status quo) oder (b) nur andere
   **politische** sonstige Videos. Kriegsvideos selbst bleiben in BEIDEN
   Varianten ungefiltert (Zähler/Kriegsvideo-Flag wird nie nach dem
   Politik-Kriterium eingeschränkt) — konsistent mit der bereits etablierten
   Konvention aus `frage4_kriegspraemie_relative_views_plots.py`
   (`andere_politische_videos`/`andere_politische_videos_topic`).

## Entscheidungen zu A–D (2026-09-08, Rückmeldung Nutzer)

- **A:** Nur `topic_categories` als Politik-Klassifikation (keine zusätzliche
  `politics_final`-Variante).
- **B:** Technischer Umsetzungsvorschlag bestätigt (`vergleichsgruppe_filter()`
  in `bericht_utils.py`, orthogonale Kreuzprodukt-Dimension neben
  `phase`/`stichprobe`, neue CSV-Spalte(n) `vergleichsgruppe`/
  `vergleichsgruppe_label`, akzeptierte Verdopplung der Laufzahl bei
  Baustein 1/2).
- **C:** Vergleichsgruppen-Dimension zieht auch bei Baustein 4 mit
  (Nenner-Restriktion: `anteil_kriegsvideos = n_kriegsvideos /
  n_politische_videos_gesamt` als zusätzliche Variante, analog zur
  Marktanteil-Logik in `frage4_kriegspraemie_marktanteil_plots.py`).
- **D:** `MIN_VIDEOS_PRO_ZELLE`/`MIN_KANAELE_JE_GRUPPE` bleiben vorerst
  unverändert (3 bzw. 5); Prüfung anhand des Konsolen-Outputs nach dem
  ersten Lauf, Absenkung nur bei Bedarf.

→ Umsetzung erfolgt gemäß "Umsetzungsschritte" unten, Schritt 5 (Baustein 4)
ist damit nicht mehr optional, sondern Teil des Umfangs.

## Offene Designfragen (historisch, mittlerweile durch obige Entscheidungen beantwortet)

### A. Welche Politik-Klassifikation für "politische Videos"?

Zwei bereits im Projekt vorhandene Quellen (siehe
`frage4_kriegspraemie_relative_views_plots.py`/README Punkt 8c):

| Quelle | Abdeckung | Bemerkung |
|---|---|---|
| `politics_final` (`data/store/screening_state.sqlite`) | ~12 % aller Videos | manuelle/LLM-Klassifikation, aber nur eine zufällige Stichprobe je Kanal×3-Monats-Intervall — die meisten Videos haben gar keinen Eintrag |
| `topic_categories` (`data/store/video_registry.sqlite::video_details`, `video_registry.is_politics_topic()`/`politics_topic_lookup()`) | ~99,7 % aller Whitelist-Videos | YouTube-eigene automatische Themenkategorisierung, breiter gefasste Definition von "politisch" |

**Empfehlung:** `topic_categories` als Standard — deckt sich mit der bereits
gespeicherten Projekt-Präferenz ("`video_details.topic_categories` bevorzugen,
wenn eine breit abgedeckte Politik-Klassifikation gebraucht wird") UND mit der
bereits im Projekt vollzogenen Erweiterung von `frage4_kriegspraemie_
marktanteil_plots.py`/`frage4_kriegspraemie_relative_views_plots.py` um genau
diese Variante. Bei `MIN_VIDEOS_PRO_ZELLE`/`MIN_KANAELE_JE_GRUPPE` sollte
das kaum zusätzliche Zellen kosten (hohe Abdeckung) — im Gegensatz zu
`politics_final`, wo die dünne Abdeckung viele Zellen unter die
Mindestbesetzung drücken würde. **→ Bitte bestätigen, ob `topic_categories`
reicht oder `politics_final` zusätzlich gewünscht ist.**

### B. Technische Umsetzung der Vergleichsgruppen-Dimension

Vorschlag: neue gemeinsame Filterfunktion (Ort: `bericht_utils.py`, analog
`dauer_teilstichprobe()`) — z. B. `vergleichsgruppe_filter(df, modus,
spalte_politik)`: bei `modus="nur_politische_videos"` werden Zeilen mit
`ist_kriegsvideo == 0 UND NICHT politisch` verworfen, Kriegsvideos bleiben
immer erhalten. Eingebaut als **weitere, orthogonale Kreuzprodukt-Dimension**
neben `phase`/`stichprobe` (Baustein 1/2: `verarbeite_granularitaet()`,
Baustein 3: `main()`) — analoges Muster zu `DAUER_TEILSTICHPROBEN_AKTIV`.
CSV-Schema bekommt eine neue Spalte `vergleichsgruppe`/`vergleichsgruppe_
label`. **→ Ergibt für Baustein 1/2 eine Verdopplung der Laufzahl
(Zeitfenster × Stichprobe × Vergleichsgruppe × Dimension) — auf
Zellenebene (6.601 Zeilen) rechnerisch unkritisch, nur mehr Konsolen-
Output/CSV-Zeilen. Für Baustein 3 (Video-Ebene) ist die Kombination aus
Längenfilter UND Politikfilter der Haupthebel, um die ~824k Zeilen der
vollen Stichprobe zu reduzieren — Zeilenzahl nach beiden Filtern sollte VOR
dem echten Lauf empirisch geprüft werden (kleines Diagnose-Skript wie im
Chat, siehe Schritt 4 unten).**

### C. Betrifft die Vergleichsgruppen-Dimension auch Baustein 4 (Anteil-Design)?

Vom Nutzer nur für Baustein 1/2 (und implizit 3, da dort ohnehin schon
geplant) explizit gefordert — für Baustein 4 nicht erwähnt. Wäre inhaltlich
möglich (Nenner der Anteilsberechnung auf politische Videos einschränken:
`anteil_kriegsvideos = n_kriegsvideos / n_politische_videos_gesamt` statt
`/ n_videos_gesamt`, analog zur "Marktanteil"-Logik in `frage4_kriegspraemie_
marktanteil_plots.py`), ist aber ein zusätzlicher Schritt über die reine
Beobachtungseinheiten-Frage hinaus. **→ Bitte bestätigen: mitziehen oder erst
mal nur Baustein 1/2/3?**

### D. MIN_VIDEOS_PRO_ZELLE / MIN_KANAELE_JE_GRUPPE bei "nur politische Videos"

Auch mit `topic_categories` (hohe Abdeckung) werden Zellen in der
`nur_politische_videos`-Variante tendenziell dünner besetzt sein als bei
`alle_videos` (Nenner wird kleiner). Vorschlag: zunächst dieselben Schwellen
wie bisher (`MIN_VIDEOS_PRO_ZELLE = 3`, `MIN_KANAELE_JE_GRUPPE = 5`)
verwenden und die tatsächliche Zahl ausgeschlossener Zellen/Gruppen beim
ersten Lauf aus dem Konsolen-Output ablesen (wie bereits an mehreren Stellen
im Projekt üblich) — nur bei Bedarf nachträglich absenken.

## Umsetzungsschritte (nach Klärung der offenen Fragen A–D)

1. `video_registry.is_politics_topic()`/`politics_topic_lookup()` in
   `lade_video_daten()` mergen → neue Spalte (z. B. `ist_politisches_video`)
   auf Video-Ebene.
2. `vergleichsgruppe_filter()` in `bericht_utils.py` ergänzen (gemeinsame
   Basis für Baustein 1–3, ggf. 4).
3. Baustein 1/2 (`verarbeite_granularitaet()`/`_fuehre_lauf_aus()`): neue
   Kreuzprodukt-Dimension `vergleichsgruppe` einbauen, CSV-Schema erweitern.
   **Ändert die Modellformel NICHT für die bereits berichteten Zahlen** (die
   `alle_videos`-Variante bleibt bitwise identisch zum Status quo) — nur ein
   zusätzlicher, paralleler Lauf.
4. Baustein 3: Granularität auf `"quartal"` reduzieren (Punkt 1 oben),
   `DAUER_TEILSTICHPROBEN`- UND `vergleichsgruppe`-Kreuzprodukt einbauen.
   Vor dem echten Lauf: Zeilenzahl nach beiden Filtern empirisch schätzen
   (kleines Diagnose-Skript, wie im Chat vorgeführt) und mit dem Nutzer
   das tatsächliche Speicher-/Zeitrisiko neu bewerten.
5. Falls unter C bestätigt: Baustein 4 um Nenner-Restriktion erweitern.
6. Docstrings (`frage4_kriegspraemie_medientyp_bericht.py`), `README.md`
   Punkt 8b und `frage2_4_methodik_und_stichprobe.md` Abschnitt 7 auf den
   finalen Stand bringen (CLAUDE.md-Pflicht).
7. **Testlauf-Reihenfolge** (jeweils mit Nutzerfreigabe vor dem Start, siehe
   CLAUDE.md "Testläufe"): zuerst Baustein 3/4 isoliert (neu, noch nie
   gelaufen, höchstes Risiko/größter Erkenntnisgewinn), danach Baustein 1/2
   komplett neu (jetzt mit `vergleichsgruppe`-Dimension).
8. Ergebnisse in `zentrale_ergebnisse.md` (Abschnitt "TODO 1: Kriegsprämie")
   und `frage2_4_methodik_und_stichprobe.md` einpflegen — bestehende
   Zahlen aus der `alle_videos`-Variante von Baustein 1/2 NUR ersetzen, wenn
   sich inhaltliche Aussagen durch den Re-Lauf tatsächlich ändern (sollten
   sie nicht, da Modellformel/Daten für diese Variante unverändert bleiben).

## Status (2026-09-08)

Umsetzungsschritte 1–6 sind erledigt: `ist_politisches_video` (via
`video_registry.politics_topic_lookup()`) in `lade_video_daten()` gemergt,
`vergleichsgruppe_filter()` in `bericht_utils.py` ergänzt, Baustein 1/2
(`verarbeite_granularitaet()`), Baustein 3 (neue `verarbeite_video_ebene()`,
NUR `"quartal"` + `DAUER_TEILSTICHPROBEN`-Kreuzprodukt) und Baustein 4 (neue
`verarbeite_anteil()`) um die Vergleichsgruppen-Dimension erweitert,
Docstrings/`README.md`/`frage2_4_methodik_und_stichprobe.md` Abschnitt 7
aktualisiert.

**Testlauf durchgeführt** (Nutzer hat für diese Session auf Rückfrage vor
Testläufen verzichtet): `frage4_kriegspraemie_medientyp_bericht.py` komplett
(Baustein 1–4, beide Granularitäten) fehlerfrei durchgelaufen. Kennzahlen:

- Baustein 1/2: 738 Zeilen (quartal) / 726 Zeilen (monat) aus je 36 Läufen
  (6 Zeitfenster × 3 Stichproben × 2 Vergleichsgruppen).
- Baustein 3 (NUR quartal): 42 Zeilen aus 6 Läufen (3 Stichproben × 2
  Vergleichsgruppen). Zeilenzahlen wie vorab per Diagnoseskript geschätzt
  (`scripts/adhoc/diagnose_baustein3_zeilenzahl.py`): voll×alle_videos
  783.237 Videos, bis runter zu mittel_3_30min×nur_politische_videos
  181.961 Videos — deutlich unter dem ursprünglich befürchteten Worst-Case.
- Baustein 4: 42 Zeilen je Granularität aus je 2 Vergleichsgruppen-Läufen.

Wichtiger Zwischenstopp während der Umsetzung: `.claude/Aufgaben.md` enthält
die Anweisung, vor JEDER neuen Regression auf die noch ausstehende Korrektur
der Upload-Dichte-Berechnung (periodenbasiert statt fenster-um-das-Video)
hinzuweisen. Nutzer hat entschieden: Testläufe für DIESEN Plan laufen mit der
aktuellen (periodenbasierten) Upload-Dichte, die Korrektur ist ein separater,
späterer Schritt.

**Offen (Umsetzungsschritt 8):** Ergebnisse inhaltlich sichten und ggf. in
`zentrale_ergebnisse.md` (Abschnitt "TODO 1: Kriegsprämie") einpflegen —
noch nicht gemacht, da das eine inhaltliche Bewertung braucht, die über die
reine Implementierung hinausgeht.

## Nächster Schritt

Rückmeldung zu den offenen Fragen A–D, danach Umsetzung gemäß obiger
Reihenfolge.

# Energiekrise und Wachstum der Alternativmedien: Plan

**Erstellt: 2026-10-29.** Anlass: Die Marktanteils-Grafik
`marktanteil_monat_manuell` zeigt für „Alternative (rechts)“ in Monat 5 und 6
(24.07.–23.09.2022) einen sprunghaften, danach anhaltenden Anstieg der Views.
Die Detailanalyse (Session 2026-10-29) ergab:
- Der Anstieg kommt fast nur aus Videos **ohne** Kriegsbezug (Kriegsvideos der
  Alternativen konstant 1–3 Mio. Views pro Monat).
- Etwa 60 % des Zuwachses von Monat 4 bis 7 (+23 Mio.) stammen von
  Vermietertagebuch, Erfolgskanal und Achtung, Reichelt!; Inhalte vor allem zu
  Energiekrise, Inflation und Regierungskritik.
- Die Uploads steigen in Monat 6 ebenfalls (+21 %).
- Dieselbe Zeit bringt auch das Ende der parlamentarischen Sommerpause und der
  Talkshow-Sommerpause, den Tod der Queen sowie die Charkiw-Offensive und die
  russische Teilmobilmachung.

## Deskriptive Befunde zum Sprung in Monat 5/6 (Nachtrag 2026-10-29)

Nachgerechnet auf dem aktuellen Sample (93 Kanäle „Alternative (rechts)“ inkl.
`_manuell`, nur long). Quellen: `scripts/adhoc/alt_rechts_sprung_m5_m6.py`
→ `scripts/adhoc/alt_rechts_sprung/ergebnis.md` (+ `kanaele.csv`,
`monate.csv`) und `scripts/adhoc/alt_rechts_sprung_benchmark.py` →
`scripts/adhoc/alt_rechts_sprung/benchmark_fenster.md`. Fenster (rel_monat):
VOR 1–4, SPRUNG 5–8, SPÄTER 9–20; mittlere Views je Monat.

**Konzentration.** Views der Gruppe: 27,8 → 45,7 → 58,0 Mio./Monat
(VOR → SPRUNG → SPÄTER). Vom Zuwachs (+18 Mio.) tragen die Top 3 60 %, die
Top 5 71 %, die Top 10 88 %:
| Kanal | VOR | SPRUNG | SPÄTER | Anteil Zuwachs |
|---|---|---|---|---|
| Vermietertagebuch | 0,24 | 4,64 | 8,90 | 25 % |
| Achtung, Reichelt! (`sample_vorkrieg` = 0) | 0,79 | 5,00 | 4,43 | 23 % |
| Erfolgskanal | 3,31 | 5,47 | 3,99 | 12 % |
| Kettner-Edelmetalle | 1,93 | 3,13 | 2,87 | 7 % |
- Reichelt ist ein neuer Kanal (erstes Video 04/2022, Aufbau ab Monat 3), also
  teils ein Markteintritt. Vermietertagebuch springt genau in Monat 6 (Median
  pro Video 15 Tsd. → 157 Tsd.) mit einem Formatwechsel von Immobilien zu
  allgemeinem Krisen-Clickbait. Erfolgskanal ist bis Monat 12 wieder auf dem
  alten Niveau.
- Ohne die Top 5: 20,9 → 26,1 → 37,1 Mio./Monat.

**Angebot vs. Nachfrage.** Uploads +18 %, Views pro Video +39 %; in der
log-Zerlegung kommt ein Drittel aus der Menge und zwei Drittel aus den Views
pro Video. Keine Einzelhits: Die Top-10-Videos machen in jedem Monat 10–18 %
der Views aus.

**Themen (Titel).** Kriegsvideos tragen nichts bei (konstant ca. 2,3–2,5 Mio.).
Anteil am Zuwachs (Mehrfachzuordnung möglich):
- Regierungs-/Ampelbezug (lokale Regex: Habeck, Baerbock, Scholz, Grüne …):
  ca. 40 %
- Energie (breit, inkl. Blackout, Strommangel, Heizen): ca. 24 %; geht in
  SPÄTER zurück (6,6 → 3,4 Mio.)
- Titel ohne Stichwortthema: ca. 53 %, vor allem Clickbait des Erfolgskanals

Typisch ist die Krisenerzählung als Regierungskritik (Enteignung, Blackout,
Euro-Crash, „frieren für Waffen“), nicht das Kriegsgeschehen.

**Breite – mit Vergleichsmaßstab kein Strukturbruch.** Median-Faktor
SPRUNG/VOR über die Kanäle: 1,22, und 40 % der Kanäle wachsen um mehr als 50 %
(Kanäle mit ≥ 3 aktiven Monaten in VOR). Über alle 4-Monats-Fensterpaare
2019–2025 schwankt der Median zwischen 0,78 und 1,47, der Anteil > 1,5
zwischen 5 und 50 %.
- **Saisonalität:** Dieselben Kalendermonate (Ende Juli bis Ende November)
  liefern 2023 einen Median von 1,21 und 2024 von 1,18. Die Traditionellen
  wachsen 2022 nicht mit (Median 1,01); ein reiner Saisoneffekt ist damit nicht
  ganz sicher, aber naheliegend.
- **Erholung:** Das Vorfenster Monat 1–4 war schwach (Median 0,85, 41 % der
  Kanäle verlieren mehr als 20 %). Ein Teil des Anstiegs ist Rückkehr zum Niveau
  zu Kriegsbeginn.
- **Außergewöhnlich ist nur der gepoolte Faktor** (1,64, Maximum der Reihe),
  und der stammt von den Top-Kanälen.
- Bei n ≈ 52 Kanälen streut der Median über Verhältnisse stark.

**Folgerungen für die Schritte unten.**
- Ein breiter Strukturbruch in Monat 5/6 ist nicht belegt. Strukturell ist
  eher das langsame, breite Niveauwachstum über die Jahre (zweiter Schub ab
  Monat 15, Mai 2023).
- Für Schritt 2 heißt das:
  - Gruppe×Monat-FE sind nötig, weil sie Saison und gemeinsame Schocks
    herausnehmen.
  - Der Leave-out-Test (ohne Vermietertagebuch, Erfolgskanal, Kettner;
    zusätzlich ohne Achtung, Reichelt!, weil der Kanal neu ist) ist
    entscheidend.
  - Keine weiteren Zerlegungen der Breite in diesem einen Fenster, sonst wird
    es Spezifikationssuche.
- Hinweis zum Sample: Die aktuelle `KANALLISTE` in `marktanteil_rohdaten_plots.py`
  filtert zusätzlich auf `media_category` in [1, 2, 5] und enthält damit nur
  die rechten Alternativen. Für Vergleiche mit Traditionellen und ÖRR wurde
  nur nach `sample` in [1, 2, 3] und `foreign` ≠ 1 gefiltert.

## Deskriptive Befunde zum zweiten Schub ab Monat 15 (Nachtrag 2026-10-29)

Anlass: In `marktanteil_medientyp_ideologie_kombiniert_long_manuell_absolut.png`
steigen die absoluten Views der Alternativen (rechts) ab Monat 15
(24.05.2023) erneut stark. Gefragt war, ob man von einer durchgängigen Phase
von Monat 15 bis zur Bundestagswahl sprechen kann (Monat 35 = 24.01.–23.02.2025).
Sample wie oben (93 Kanäle, nur long), Monate 6 bis 51. Quelle:
`scripts/adhoc/alt_rechts_zweiter_schub.py` →
`scripts/adhoc/alt_rechts_zweiter_schub/ergebnis.md` (+ `kanaele.csv`,
`monate.csv`).

**Niveau (Mio. Views pro Monat, Phasenmittel).** „Etablierte“ sind die 54
Kanäle mit erstem Video bis Monat 0.
| Phase | Monate | alle 93 Kanäle | nur Etablierte |
|---|---|---|---|
| A | 6–14 | 49 | 44 |
| B1 | 15–24 | 75 | 65 |
| B2 | 25–33 (bis Ampel-Aus/Dez. 2024) | 103 | 75 |
| Wahl | 34–36 | 179 | 123 |
| danach | 37–51 | 134 | 76 |
- Monatsverlauf (alle Kanäle): von 56 Mio. (Monat 15) über 94 Mio. (Monat 22)
  und einen Einbruch in Monat 25/26 (73–78 Mio.) auf 128 Mio. (Monat 33).
  Danach folgt der Wahlpeak (Monat 35: 203 Mio.). Nach der Wahl entsteht ein
  Plateau von etwa 120–145 Mio. ohne weiteres Wachstum.

**B1 (15–24): Wachstum der bestehenden Kanäle über mehr Views pro Video.**
- Uploads 1260 → 1541 pro Monat, Median-Views pro Video 15 Tsd. → 20 Tsd.
- Median-Wachstumsfaktor der etablierten Kanäle 1,26. Ohne die Top 10 wären
  es nur etwa +16 % statt +53 %.
- Top 5 tragen 57 % des Zuwachses gegenüber A: Aktien mit Kopf (18 %),
  Vermietertagebuch (17 %), COMPACT-TV, Erfolgskanal, Oli investiert, Oli.
  Neu sind Landwirtschaft erLEEben (ab Monat 14) und NIUS (ab Monat 16).
- Themen (Titel-Regex, Mio./Monat A → B1):
  - AfD 1,1 → 9,9; der Sprung liegt genau in Monat 15 (Umfragehoch,
    Sonneberg).
  - Ampel/Grüne 9,5 → 18,1.
  - Clip/Reaktion 2,2 → 7,4.
  - Bauern 0,3 → 2,7.
  - Kaum verändert: Ukraine +0,5, Energie −1,3 (`rel_energy_cw`), Corona −0,5.
- Finanzkanäle werden zu politischen Clip-Kanälen. Bei Aktien mit Kopf fallen
  die Finanztitel von 18 % auf 3 % der Views, die AfD-Titel steigen von 1 % auf
  21 %.

**B2 (25–33): Wachstum über neue Kanäle und mehr Uploads, nicht über mehr
Views pro Video.**
- Uploads 1541 → 2093 pro Monat, mittlere Views pro Video gleich (49 Tsd.).
  Median-Faktor der etablierten Kanäle nur 1,08.
- Weniger konzentriert: Top 5 tragen 42 %, Top 10 64 % des Zuwachses
  (+27 Mio.). 22 Kanäle mit erstem Video ab Monat 22 bringen 38 % des Zuwachses,
  die 54 etablierten Kanäle (erstes Video bis Monat 0) ebenfalls nur 38 %.
- Gewinner:
  - Aktien mit Kopf (12 %), Politik & Co (10 %), Landwirtschaft erLEEben
    (8 %), NIUS (7 %).
  - Neu: Alexander Raue Klartext, Weichreite TV, Enrico Rudolph, Amnas.
- Verlierer: Vermietertagebuch (−1,9), Erfolgskanal (−1,0), Schuler!, Oli
  investiert.
- **Etablierte Kanäle allein wachsen in B2 nur noch um 16 %** (B1: +48 %). Nach
  der Wahl fallen sie auf das Niveau von B2 zurück (76 gegenüber 75).
- Themen (Mio./Monat B1 → B2):
  - Gleich bleibende Treiber: AfD 9,9 → 16,3, Ampel/Regierung 18,1 → 20,3,
    Clip/Reaktion 7,4 → 9,4.
  - Neu dazu: Migration/Kriminalität 3,1 → 6,6 (Spitzen Monat 30
    Solingen, Monat 33 Magdeburg), Trump/USA 1,2 → 4,7, Merz/CDU ab
    Monat 30–32 (Ampel-Aus).
  - Weggefallen: Bauern (2,7 → 0,4).
  - Ukraine bleibt klein (4,7 → 6,2).
  - Unter den Top-Videos sind auch unpolitische Comedy- und TV-Clips (Nuhr,
    Mario Barth, Gottschalk).
- **Wahl (34–36)** wird zu einem Drittel von Aktien mit Kopf getragen
  (10 → 35 Mio./Monat), dazu kommen die neuen Kanäle Politik mit Kopf und ANDI
  in Deutschland. Themen: AfD 37, Merz/CDU 32, Trump/USA 25 Mio./Monat.
  Nach der Wahl brechen die Ampel-Titel ein (5,5), Merz/CDU (20) und AfD (19)
  bleiben die Leitthemen.

**Einschätzung.**
- Die Gesamtkurve steigt von Monat 15 bis 33 zwar fast durchgehend, die
  Mechanik dahinter wechselt aber. Statt „15 bis zur Wahl“ besser einteilen in
  B1 (Wachstum bestehender Kanäle, AfD/Ampel) + B2 (Markteintritte) + Wahl als
  Ereignis + Plateau danach.
- **Selektionsvorbehalt:** Das Sample wurde nachträglich gezogen. Kanäle, die
  2024 gegründet wurden und später groß waren, sind sicher drin. Gescheiterte
  Neugründungen fehlen. Den Zuwachs in B2 kann man deshalb nur eingeschränkt
  als Marktwachstum deuten.
- Mit Krieg oder Energie hat keine der Phasen nennenswert zu tun.

**Folgerungen für die Schritte unten.**
- **Schritt 2, kurzfristig vs. nachhaltig:**
  - Die Phasen „Abklingen“ (11–22) und „Spätphase“ (ab 23) überlagern sich mit
    dem innenpolitischen Schub. Ein anhaltender Vorsprung energie-exponierter
    Kanäle ist daher nicht automatisch ein Nachwirken der Energiekrise.
  - Das gilt besonders, wenn dieselben Kanäle auch den AfD-Clip-Boom tragen
    (Vermietertagebuch, Erfolgskanal). Die Gruppe×Monat-FE nehmen nur den
    gemeinsamen Teil heraus.
  - Den Leave-out-Test deshalb auch für die Spätphase berichten.
- **Kanal-Panels für Frage 2:**
  - Nur Kanäle mit erstem Video vor Kriegsbeginn verwenden (balanced panel)
    oder Kanal-FE mit Eintrittskontrolle. Sonst misst man ab 2024 vor allem die
    Zusammensetzung des Samples.
  - Den Wahlmonat 35 (und ggf. 34–36) per Dummy oder Ausschluss behandeln.
- Keine weitere Zerlegung des zweiten Schubs. Für die Forschungsfragen reicht
  ein kurzer deskriptiver Absatz („zweite, innenpolitisch getriebene
  Wachstumsphase“).

## Frage

Hat die Energiekrise (Sommer/Herbst 2022) das Wachstum der rechten
Alternativmedien verursacht? Wenn ja: War der Effekt nur **kurzfristig**
(verschwindet, wenn das Thema abklingt) oder **nachhaltig** (die Reichweite
bleibt auch bei anderen Themen und nach 2023 höher)?

Bezug zu den Forschungsfragen: Die Energiekrise ist ein möglicher
**Mechanismus** zwischen Kriegsbeginn und Kanalerfolg (Frage 2), und die
Unterscheidung zwischen Energie-Videos und anderen Videos entspricht Frage 4.

## Ehrliche Vorbemerkung zur Identifikation

Einen Kausaleffekt im strengen Sinn wird man hier kaum identifizieren:
- **Kein scharfer Schock:** Die Krise baut sich schrittweise auf
  (Preisanstieg ab Frühjahr, Wartung von Nord Stream 1 ab 11.07., Gasumlage
  Anfang August, Lieferstopp ab 31.08., Gaspreisbremse im Dezember).
- **Viele gleichzeitige Ereignisse:** Inflation, Ende der Sommerpause und
  Kriegsereignisse fallen in dieselben Wochen. Eine reine Zeitreihe trennt
  das nicht.
- **Das Exposure ist selbst gewählt:** Finanz- und Wirtschaftskanäle
  (Erfolgskanal, Kettner, Vermietertagebuch) sind ohnehin mit der
  Inflation/Zinswende gewachsen.

Erreichbar ist **exposure-basierte Evidenz**: Wenn Kanäle, die das Thema schon
vor der Krise stark bedient haben, ab Juli 2022 stärker wachsen und dieser
Vorsprung beim Abklingen des Themas wieder schrumpft (oder eben nicht), dann
ist das konsistent mit einem Effekt der Energiekrise. In der Arbeit sollte es
auch so formuliert werden. **Bei einem Nullbefund oder deutlichen Vortrends:
abbrechen und nicht nachjustieren.** Laut `masterarbeit_strategie.md` sind
weitere Schockfenster-Varianten ausdrücklich Spezifikationssuche.

## Vorab festgelegte Definitionen (nicht nachträglich ändern)

- **Phasen (rel_monat bzw. Kalender):**
  - Vorkrieg: 2021-06 bis 23.02.2022
  - Kriegsbeginn: Monat 0–4 (24.02.–23.07.2022)
  - Akute Energiekrise: Monat 5–10 (24.07.2022–23.01.2023)
  - Abklingen: Monat 11–22 (Gaspreise fallen, Thema verliert an Sichtbarkeit)
  - Spätphase: ab Monat 23 (Heizungsgesetz 2023 als möglicher zweiter
    Energieschub, nur deskriptiv)
- **Ereignisdatum (festgelegt 2026-10-29, vor Ansicht von Ergebnissen):**
  - **Hauptdatum: 02.09.2022.** Gazprom stoppt Nord Stream 1 auf unbestimmte
    Zeit; im Umfeld liegen die Börsenpreisspitze (26.08.), das Ende von
    9-Euro-Ticket und Tankrabatt (31.08.) und die zweistellige Inflation
    (September). Gilt als Übergang von „Drosselung“ zu „kein russisches Gas“.
  - **Robustheit: 23.06.2022.** Habeck ruft die Alarmstufe des Notfallplans
    Gas aus, die erste offizielle Eskalation.
  - Verwendung: Event-Study-Achsen (Wochen bzw. Tage relativ zum Datum) und
    Vorher/Nachher-Dummies in Schritt 1 und 2, jeweils zusätzlich zu den
    Phasen nach rel_monat. Keine weiteren Daten nachträglich hinzunehmen.
  - Vorbehalt: Keines der Daten ist ein Überraschungsschock (der Lieferstopp
    zeichnete sich seit Juni ab). Am 06.09. beginnt zudem die Haushaltswoche
    des Bundestags, und die Talkshow-Sommerpausen enden. Ein reines
    Ereignisfenster um den 02.09. vermischt das; deshalb gilt der
    Exposure-Vergleich innerhalb der Gruppen (Schritt 2) als Hauptdesign.
  - Die Daten stammen aus dem Gedächtnis und sind vor der Verwendung in der
    Arbeit an einer Chronik (Bundesnetzagentur, Tagesschau) zu prüfen.
- **Energie-Video:** `rel_energy_cw == ja` (Titel). Robustheit:
  `rel_energy_core`, und das Bündel Energie oder Wirtschaft
  (`rel_economy_general_cw`).
- **Population:** wie in den Marktanteils-Grafiken: `format == long`,
  KANALLISTE-Sample, Gruppen aus `medientyp_ideologie` inkl. `_manuell`.
- **Erfolg:** rohe Views (log), siehe Memory zu Erfolgsmaßen.

## Schritt 0: Stichwortliste prüfen (klein, Voraussetzung)

Die Energieliste enthält absichtlich keine mehrdeutigen Einzelwörter („Gas“,
„Strom“). Typische Titel der Alternativen fehlen dadurch, z. B. „Strommangel“,
„Blackout“, „Heizung“, „frieren“. Deshalb:
1. Zufallsstichprobe von 150 Titeln der Alternativen aus Monat 4–8 ziehen und
   von Hand codieren (Energie ja/nein).
2. Precision und Recall von `rel_energy_cw` berechnen.
3. Wenn der Recall unter ca. 70 % liegt: Liste in `topic_keywords.py` gezielt
   ergänzen (Komposita wie `strommangel`, `blackout\w*`, `heizkosten`). Das
   ändert `rel_energy_*` im Rohdatensatz, also ist ein **Neu-Export** fällig
   (ca. 40 min, vorher fragen). Alternativ für dieses AP eine lokale,
   dokumentierte Zusatzliste im Skript verwenden und den Export später
   nachziehen.

## Schritt 1: Nachfrage nach Energie-Inhalten im Kanal (Video-Ebene)

Frage: Belohnt das Publikum Energie-Videos in der Krise stärker als andere
Videos desselben Kanals, und bei den Alternativen mehr als bei anderen
Gruppen?

```
log_views_vc = α_c + λ_m + Σ_p β_p · energie_v · phase_p
             + Σ_p δ_p · energie_v · phase_p · alternativ_c + Kontrollen + ε
```
- Kanal-FE, Monats-FE, Kontrollen: Länge (log Dauer), Upload-Dichte des Kanals
  im Monat (beide Varianten, siehe Memory), Kriegsvideo-Dummy.
- Monatliche Event-Study-Version der Energieprämie (Basis: Vorkrieg) als
  Grafik je Gruppe.
- Cluster: Kanal.
- Aussage: kurzfristig, wenn die Prämie nur in der akuten Phase erhöht ist.
- Bauplan wie bei der Kriegsprämie (`frage4_kriegspraemie_*.md`), Code dort
  wiederverwenden.

Was das **nicht** beantwortet: ob der Kanal insgesamt gewachsen ist.

## Schritt 2: Exposure-DiD auf Kanalebene (Kernstück)

Frage: Wachsen Kanäle mit hohem Energie-Exposure vor der Krise ab Juli 2022
stärker, und hält der Vorsprung an?

- **Exposure_c:** Anteil der Energie-Videos (Robustheit: Energie+Wirtschaft)
  an den Uploads im **Vorkriegsfenster** (vor 24.02.2022). So kann das
  Exposure nicht auf die Krise selbst reagiert haben. Kanäle mit < 30 Uploads
  im Fenster ausschließen.
- **Panel:** Kanal × Monat, Outcome log(Views-Summe + 1) und log(Median-Views).
- **Modell (Event-Study):**
  ```
  y_cm = α_c + λ_{g(c),m} + Σ_k θ_k · Exposure_c · 1[m = k] + ε
  ```
  Gruppe-×-Monat-FE (λ_{g,m}): Verglichen wird nur innerhalb von Alternativ,
  Traditionell und ÖRR. Damit fallen gemeinsame Schocks (Sommerpause, Queen,
  Alterseffekt der Views) heraus.
- **Prüfungen:**
  - **Vortrends:** θ_k für Monat −12 bis 4 sollte nahe 0 liegen. Wenn nicht:
    Befund als nicht kausal interpretierbar berichten.
  - **Kurzfristig vs. nachhaltig:** θ_k in der akuten Phase gegenüber
    Abklingen und Spätphase.
  - **Übertragung auf andere Inhalte (Frage 4):** dasselbe Modell nur mit den
    Views von Nicht-Energie-Videos als Outcome. Steigen auch die: Hinweis auf
    neues, gebundenes Publikum statt nur Themennachfrage.
  - **Angebot vs. Nachfrage:** zusätzlich Uploads als Outcome und Views pro
    Video. So lässt sich trennen, ob die Kanäle nur mehr produziert haben.
  - **Finanzkanal-Trend:** Robustheit mit einem Dummy für Finanz- und
    Wirtschaftskanäle × Monat (Zuordnung von Hand aus `channels_check.xlsx`)
    bzw. ohne Erfolgskanal, Kettner, Vermietertagebuch und Silberjunge
    (Leave-out). Bricht der Effekt dann zusammen, misst Exposure den
    Inflations-/Finanzboom und nicht die Energiekrise.
  - **Placebo:** Exposure gegenüber einem Thema ohne Krise in diesem Zeitraum
    (z. B. `rel_education_cw`) mit demselben Modell. Erwartung θ ≈ 0.
- **Heterogenität:** θ getrennt für Alternative und Traditionelle. Die Frage
  ist, ob die Alternativen ihr Exposure stärker in Reichweite umsetzen.

## Schritt 3 (optional): Publikumsbindung über Kommentare

Direktester Test für „nachhaltig“. `comments.sqlite` enthält 13,2 Mio.
Kommentare, ab 2022 etwa 2.700–3.700 Videos pro Monat mit Kommentaren.
1. **Abdeckung prüfen:** Welche Kanäle und Videos sind enthalten (Auswahl per
   `step7_comments/select_targets.py`)? Ist die Auswahl nach Views
   geschichtet, sind die Kohorten verzerrt. Ohne ausreichende Abdeckung der
   Alternativen 2022/23: abbrechen.
2. **Kohorten:** Kommentierende (`author_channel_id`), die bei einem
   alternativen Kanal zum **ersten Mal** kommentieren, je Monat. Die
   „Energie-Kohorte“ ist der Erstkommentar unter einem Energie-Video in
   Monat 5–10.
3. **Bindung:** Anteil der Kohorte, der 3, 6 und 12 Monate später noch beim
   selben (oder einem anderen alternativen) Kanal kommentiert, auch unter
   Nicht-Energie-Videos. Vergleich mit Kohorten aus anderen Monaten und
   anderen Themen desselben Kanals.

## Was wir nicht machen

- Keine Google-Trends-Intensität × Exposure (Bartik). Zusätzliche Datenquelle
  ohne zusätzliche Identifikation. Nur wenn Schritt 2 klar ist, als
  Illustration.
- Keine weiteren Phasengrenzen oder Schwellen nach Ansicht der Ergebnisse.
- Keine LLM-Klassifikation der Energie-Videos (Kosten). Schritt 0 reicht.

## Ausgaben

- Skript: `scripts/masterarbeit/ap10_energiekrise.py` (falls als AP in
  `masterarbeit_strategie.md` aufgenommen, sonst `scripts/adhoc/`),
  Konfigurationsblock statt argparse.
- Ergebnisse: `outputs/masterarbeit/ap10_energiekrise/`, Regressionen in
  `regression_results/energiekrise_exposure.md`, Event-Study-Grafiken je
  Gruppe, Methodik-Markdown mit Phasen und Definitionen.

## Aufwand und realistische Erwartung

- **Aufwand:** Schritt 0 und 1 eine Session, Schritt 2 eine Session,
  Schritt 3 eine weitere Session (optional).
- **Erwartung:**
  - Schritt 1 zeigt sehr wahrscheinlich eine Energieprämie in der akuten
    Phase. Das ist wenig überraschend und allein nur deskriptiv.
  - Schritt 2 ist der eigentliche Test. Ein Vortrend durch den
    Finanzkanal-Boom ist das wahrscheinlichste Problem. Fällt der Effekt im
    Leave-out weg, lautet die ehrliche Aussage: „Wachstum einzelner
    Finanz-/Krisenkanäle, nicht als Effekt der Energiekrise identifizierbar.“
  - In der Arbeit gehört das als Mechanismus-Abschnitt zu Kapitel D (Markt)
    oder in den Anhang, nicht als Hauptbefund.

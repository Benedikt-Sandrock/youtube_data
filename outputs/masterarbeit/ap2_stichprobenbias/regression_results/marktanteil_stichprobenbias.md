# AP 2: Stichproben-Bias beim Marktanteil der rechten Alternativmedien

Erzeugt von `scripts/masterarbeit/ap2_marktanteil_stichprobenbias.py`, Plan: `.claude/plans/ap2_stichprobenbias.md`.

## 1. Methodik-Übersicht

**Frage:** Ist der Anstieg des Marktanteils der rechten Alternativmedien nach Kriegsbeginn ein Artefakt der Stichprobe? Das Sample wurde nach Erfolg am Ende des Zeitraums gezogen (>50k Abonnenten 2026), gelöschte Kanäle fehlen.

**Ausgangsmenge:** kanonisches Sample `russia_longitudinal_v1` (427 Kanäle, `eligible_current_analysis == True`), Videos direkt aus der `video_registry` (`lade_basisdaten(kanalquelle="kanon")`), Fenster rel_monat -12…48. Videos ohne `view_count` sind verworfen.

**Varianten (vorab festgelegt):**

| Kürzel | Kanalpopulation | adressiert |
|---|---|---|
| V0 | alle Kanäle mit gültigem gruppe5 | Referenz |
| V0w | V0 ∩ 279er-Whitelist (`frage1_kanal_whitelist.csv`) | Referenzzeile |
| V1 | `activity_phases`-Kategorie `aktivitaet_deckt_kriegsbeginn` (Lückenschwelle 12 Monate → mind. ein Upload in −12…−1) | Eintritt neuer Kanäle |
| V2 | V1 und ≥1 Upload in rel_monat 43…48 | streng balanciert, informativ |
| V3 | V1 und Summe der Views aller Videos aus −12…−1 > Median der V1-Kanäle (5,047,594 Views) | Auswahl nach Erfolg am Ende (Näherung) |

**Formel** (`berechne_marktanteile()`, identisch zu `marktanteil_themen_plots.py`):

```
Anteil(g, Monat) = Σ view_count(g, Szenario, Monat) / Σ view_count(alle 5 gruppe5, Szenario, Monat) × 100
```

Monate mit weniger als 20 Videos (über alle 5 Gruppen) entfallen. Der Nenner umfasst jeweils nur die Kanäle der Variante.

**Perioden:** Mittelwert der Monatsanteile in vorher (−12…−1), 0…19, ≥20, ≥40. Monate, in denen eine Gruppe kein Video hat, zählen mit 0 %. Abweichend von `marktanteil_rechts_levelshift_konzentration.py` (dort „<20“ inkl. Vorkriegsmonaten) ist die Zwischenperiode hier 0…19; das Entscheidungskriterium ist davon nicht betroffen. Deshalb liegt der Vorher-Wert der rechten Alternativmedien hier niedriger als die ~17 % aus `zentrale_ergebnisse.md` (Kernbotschaft 1), die die Monate 0…19 einschließen.

**Δ** = Anteil(≥20) − Anteil(vorher). **Szenarien:** Hauptszenario alle politischen Videos (`ist_politics_topic`), Nebenszenario Kriegsvideos.

**Bootstrap:** 1000 Ziehungen, Kanäle mit Zurücklegen innerhalb ihrer gruppe5 (Seed 20260928); je Ziehung werden Monatsanteile, Periodenmittel und Δ neu berechnet. 95-%-Perzentil-KI. Kanäle ohne Video im Szenario bleiben in der Ziehungsmenge.

**Entscheidungskriterium** (Hauptvariante V1, Robustheit V3, Gruppe rechte Alternativmedien, Hauptszenario):

- **hält:** Δ(V) ≥ 50 % von Δ(V0) und KI schließt 0 aus
- **abgeschwächt:** Δ(V) > 0 mit KI ohne 0, aber < 50 % von Δ(V0)
- **hält nicht:** KI von Δ(V) enthält 0

## 2. Kategorien der Kanalaktivität je gruppe5

Alle 427 Kanon-Kanäle, Klassifikation mit `classify_channels_bulk()` (Uploads aus der `video_registry`, Gründungsdatum aus `channels`).

| Kategorie | ÖRR | Traditionelles Medium | Alternative Medien (links) | Alternative Medien (mitte) | Alternative Medien (rechts) | (ohne gruppe5) | Summe |
|---|---|---|---|---|---|---|---|
| aktivitaet_deckt_kriegsbeginn | 53 | 42 | 54 | 56 | 81 | 48 | 334 |
| nachkrieg_verzoegerter_start | 6 | 2 | 6 | 10 | 37 | 6 | 67 |
| reaktiviert_faelschlich_vorkrieg | 1 | 0 | 2 | 3 | 14 | 6 | 26 |
| Summe | 60 | 44 | 62 | 69 | 132 | 60 | 427 |

**Herkunft der Zahl „90“:** `channel_sample_provenance.csv`, Spalte `active_before_reference == False` (erstes beobachtetes Video am oder nach dem 24.02.2022, `build_channel_provenance.py`): 90 Kanäle. Abgleich mit den Aktivitätskategorien:

| Kategorie | active_before_reference=False | active_before_reference=True |
|---|---|---|
| aktivitaet_deckt_kriegsbeginn | 0 | 334 |
| nachkrieg_verzoegerter_start | 67 | 0 |
| reaktiviert_faelschlich_vorkrieg | 23 | 3 |

**Rechte Alternativmedien:** 51 von 132 Kanälen sind nicht in V1 (keine Aktivitätsphase über den Kriegsbeginn), davon 51 Nachkriegskanäle.

Kanäle je Variante:

| Variante | ÖRR | Traditionelles Medium | Alternative Medien (links) | Alternative Medien (mitte) | Alternative Medien (rechts) | Summe |
|---|---|---|---|---|---|---|
| V0 | 60 | 44 | 62 | 69 | 132 | 367 |
| V0w | 44 | 38 | 34 | 44 | 100 | 260 |
| V1 | 53 | 42 | 54 | 56 | 81 | 286 |
| V2 | 50 | 40 | 51 | 56 | 78 | 275 |
| V3 | 42 | 32 | 19 | 25 | 25 | 143 |

## 3. Level-Shift-Tabellen mit Δ und Bootstrap-KI

### Alle politischen Videos (topic_categories='Politics')

**Alternative Medien (rechts):**

| Variante | Kanäle | mit Videos | Videos | Anteil vorher (−12…−1) | Anteil 0…19 | Anteil ≥20 | Anteil ≥40 | Δ (pp) | 95-%-KI | Δ / Δ(V0) | Einstufung |
|---|---|---|---|---|---|---|---|---|---|---|---|
| V0 | 132 | 130 | 115596 | 10.8 | 19.4 | 39.1 | 39.0 | 28.3 | [18.3; 39.1] | 100 % | – |
| V0w | 100 | 100 | 109277 | 10.8 | 18.5 | 38.6 | 39.3 | 27.8 | [16.5; 39.5] | 98 % | hält |
| V1 | 81 | 79 | 70060 | 10.8 | 17.0 | 28.5 | 25.6 | 17.7 | [7.6; 30.1] | 62 % | hält |
| V2 | 78 | 76 | 69915 | 10.8 | 16.8 | 28.4 | 25.6 | 17.6 | [7.5; 29.8] | 62 % | hält |
| V3 | 25 | 24 | 33046 | 9.7 | 10.3 | 16.8 | 16.1 | 7.1 | [-1.4; 19.8] | 25 % | hält nicht |

**Alle Gruppen (Δ mit KI):**

| gruppe5 | V0 | V0w | V1 | V2 | V3 |
|---|---|---|---|---|---|
| ÖRR | 35.6 → 21.9: -13.7 [-27.4; -3.8] | 35.3 → 23.0: -12.3 [-25.8; -2.7] | 35.6 → 28.7: -6.9 [-20.0; 3.4] | 35.1 → 28.7: -6.3 [-19.6; 3.5] | 36.8 → 37.5: 0.7 [-11.7; 11.0] |
| Traditionelles Medium | 45.5 → 25.1: -20.4 [-35.0; -5.7] | 46.7 → 27.3: -19.4 [-32.7; -3.6] | 45.5 → 32.7: -12.8 [-26.3; 1.3] | 46.0 → 32.7: -13.3 [-26.2; 0.6] | 47.1 → 41.1: -6.0 [-19.9; 8.1] |
| Alternative Medien (links) | 4.0 → 5.0: 1.0 [-2.7; 4.2] | 3.6 → 4.7: 1.2 [-2.6; 4.4] | 4.0 → 4.1: 0.1 [-3.1; 2.8] | 4.0 → 4.1: 0.1 [-3.1; 3.0] | 3.2 → 1.6: -1.6 [-4.2; 0.1] |
| Alternative Medien (mitte) | 4.1 → 8.9: 4.8 [0.1; 9.8] | 3.6 → 6.3: 2.7 [-1.9; 7.6] | 4.1 → 6.0: 1.9 [-2.7; 7.6] | 4.2 → 6.0: 1.9 [-3.2; 7.5] | 3.3 → 3.0: -0.2 [-3.3; 2.8] |
| Alternative Medien (rechts) | 10.8 → 39.1: 28.3 [18.3; 39.1] | 10.8 → 38.6: 27.8 [16.5; 39.5] | 10.8 → 28.5: 17.7 [7.6; 30.1] | 10.8 → 28.4: 17.6 [7.5; 29.8] | 9.7 → 16.8: 7.1 [-1.4; 19.8] |

Zellen: Anteil vorher → Anteil ≥20: Δ [95-%-KI], jeweils in %/pp.

### Kriegsvideos (russia_ukraine_war, is_relevant=1)

**Alternative Medien (rechts):**

| Variante | Kanäle | mit Videos | Videos | Anteil vorher (−12…−1) | Anteil 0…19 | Anteil ≥20 | Anteil ≥40 | Δ (pp) | 95-%-KI | Δ / Δ(V0) | Einstufung |
|---|---|---|---|---|---|---|---|---|---|---|---|
| V0 | 132 | 122 | 9280 | 7.0 | 9.1 | 19.3 | 23.3 | 12.2 | [2.6; 26.8] | 100 % | – |
| V0w | 100 | 100 | 9239 | 7.3 | 9.2 | 19.4 | 23.4 | 12.2 | [2.0; 26.7] | 99 % | hält |
| V1 | 81 | 78 | 6663 | 7.0 | 8.6 | 16.3 | 18.9 | 9.3 | [-1.2; 24.9] | 76 % | hält nicht |
| V2 | 78 | 75 | 6655 | 7.2 | 8.6 | 16.4 | 18.9 | 9.2 | [-0.8; 24.0] | 75 % | hält nicht |
| V3 | 25 | 24 | 3534 | 5.4 | 5.4 | 7.7 | 7.0 | 2.3 | [-3.3; 11.5] | 19 % | hält nicht |

**Alle Gruppen (Δ mit KI):**

| gruppe5 | V0 | V0w | V1 | V2 | V3 |
|---|---|---|---|---|---|
| ÖRR | 47.8 → 35.9: -12.0 [-32.1; 10.0] | 47.5 → 35.4: -12.2 [-31.8; 10.5] | 47.8 → 38.5: -9.4 [-29.4; 13.5] | 47.5 → 38.5: -9.0 [-30.2; 14.9] | 50.7 → 44.1: -6.6 [-29.6; 18.8] |
| Traditionelles Medium | 31.0 → 36.1: 5.1 [-12.6; 20.4] | 31.6 → 36.5: 4.9 [-12.6; 19.2] | 31.0 → 39.0: 8.0 [-9.9; 23.9] | 31.0 → 39.0: 8.0 [-10.7; 24.2] | 33.0 → 45.0: 12.0 [-9.9; 31.0] |
| Alternative Medien (links) | 8.3 → 3.2: -5.1 [-13.7; 0.9] | 7.6 → 3.2: -4.5 [-13.0; 1.3] | 8.3 → 2.8: -5.5 [-14.3; -0.0] | 8.6 → 2.8: -5.7 [-14.6; 0.3] | 7.0 → 0.6: -6.3 [-14.6; -0.7] |
| Alternative Medien (mitte) | 5.7 → 5.5: -0.2 [-5.9; 5.3] | 5.9 → 5.6: -0.4 [-6.2; 5.1] | 5.7 → 3.3: -2.4 [-8.0; 0.9] | 5.8 → 3.3: -2.5 [-7.5; 1.2] | 4.0 → 2.6: -1.4 [-5.8; 2.1] |
| Alternative Medien (rechts) | 7.0 → 19.3: 12.2 [2.6; 26.8] | 7.3 → 19.4: 12.2 [2.0; 26.7] | 7.0 → 16.3: 9.3 [-1.2; 24.9] | 7.2 → 16.4: 9.2 [-0.8; 24.0] | 5.4 → 7.7: 2.3 [-3.3; 11.5] |

Zellen: Anteil vorher → Anteil ≥20: Δ [95-%-KI], jeweils in %/pp.

## 4. Zerlegung des Anstiegs und Konzentration

Rechte Alternativmedien, Alle politischen Videos (topic_categories='Politics'), vorher (−12…−1) gegen nachher (≥20):

| Komponente | pp |
|---|---|
| Δ gesamt = Anteil≥20(V0) − Anteil_vorher(V0) | 28.3 |
| (a) Wachstum der Bestandskanäle = Anteil≥20(V1) − Anteil_vorher(V0) | 17.7 |
| (b) Beitrag der Nicht-Bestandskanäle = Anteil≥20(V0) − Anteil≥20(V1) | 10.6 |
| Kontrolle: Anteil_vorher(V1) − Anteil_vorher(V0) | 0.0 |
| Δ innerhalb V1 = Anteil≥20(V1) − Anteil_vorher(V1) | 17.7 |

(a) + (b) = Δ gesamt. Anteil (a) am Gesamtanstieg: 62 %. Die Nicht-Bestandskanäle in (b) sind überwiegend neue Kanäle, dazu reaktivierte und vor dem Krieg eingeschlafene Kanäle (siehe Abschnitt 2). (b) enthält auch den Nenner-Effekt: Neue Kanäle anderer Gruppen senken den Anteil der rechten Kanäle in V0.

**Konzentration innerhalb von (a):** Beitrag der einzelnen rechten V1-Kanäle zum V1-internen Δ (17.7 pp; Kanalanteil = Kanal-Views / alle V1-Views des Monats, gemittelt wie der Gruppenanteil, Summe der Beiträge = Δ).

- Top-1-Kanal: 3.2 pp = 18 % des Zuwachses
- Top-5-Kanäle: 11.6 pp = 66 % des Zuwachses
- Kanäle mit positivem Beitrag: 57 von 81

| Rang | Kanal | Anteil vorher | Anteil ≥20 | Beitrag (pp) |
|---|---|---|---|---|
| 1 | COMPACT-TV | 0.14 | 3.31 | 3.17 |
| 2 | Vermietertagebuch - Alexander Raue | 0.00 | 2.82 | 2.82 |
| 3 | Aktien mit Kopf | 0.00 | 2.64 | 2.64 |
| 4 | Berlin360° | 0.00 | 1.53 | 1.53 |
| 5 | DIE WELTWOCHE | 0.42 | 1.89 | 1.47 |
| 6 | Red Scorpion | 0.00 | 1.47 | 1.47 |
| 7 | Marc Friedrich | 0.18 | 1.23 | 1.05 |
| 8 | Politik & Co  | 0.00 | 0.94 | 0.94 |
| 9 | Carsten Jahn - TEAM HEIMAT | 0.19 | 1.01 | 0.82 |
| 10 | Tichys Einblick | 0.15 | 0.89 | 0.74 |

Konzentration der Views innerhalb der rechten V1-Kanäle (Anteile an den Gruppen-Views der Periode):

| Periode | Top-1 (%) | Top-5 (%) | HHI | Kanäle mit Videos |
|---|---|---|---|---|
| vorher (−12…−1) | 21.1 | 54.6 | 832 | 66 |
| ≥20 | 11.3 | 43.3 | 546 | 78 |

## 5. Survivorship

### Quantitativ

**Suchläufe:** 17 Läufe in `search_runs`, ausgeführt zwischen 2026-06-30 und 2026-07-05. Die Suchfenster reichen zwar zurück bis 2021, die Suche selbst lief aber erst 2026. Videos und Kanäle, die vorher gelöscht wurden, konnten deshalb gar nicht gefunden werden. Treffer ohne Metadaten messen folglich keine Löschungen:

| Suchjahr | Treffer | ohne `videos`-Zeile | ohne channel_id | ohne view_count | davon nie abgerufen (kein Titel, keine Details) |
|---|---|---|---|---|---|
| 2021 | 12744 | 0 | 0 | 7319 | 7319 |
| 2022 | 7976 | 0 | 0 | 5166 | 5166 |
| 2023 | 2675 | 0 | 0 | 969 | 969 |
| 2024 | 6284 | 0 | 0 | 2266 | 2266 |
| 2025 | 3921 | 0 | 0 | 1890 | 1890 |

Jeder Treffer hat eine `videos`-Zeile mit channel_id. Fehlende view_counts betreffen Videos von Kanälen außerhalb des Samples, für die nie Statistiken abgerufen wurden („nie abgerufen“ oder nur Titel aus der Suche). Ein Metadaten-Refetch über `metadata_collection.py` würde nur Löschungen **nach** Juni 2026 zeigen und ist für die Frage wertlos. **Deshalb wurde kein Refetch durchgeführt.**

**Innerhalb des Samples:** Anteil der Registry-Videos der V0-Kanäle ohne view_count (in den Marktanteilen verworfen):

| gruppe5 | vorher (%) | 0…19 (%) | ≥20 (%) | Videos vorher |
|---|---|---|---|---|
| ÖRR | 0.0 | 0.2 | 2.5 | 16078 |
| Traditionelles Medium | 0.0 | 0.1 | 0.1 | 58427 |
| Alternative Medien (links) | 0.0 | 0.1 | 0.8 | 6330 |
| Alternative Medien (mitte) | 0.0 | 0.2 | 0.1 | 12154 |
| Alternative Medien (rechts) | 23.4 | 0.1 | 0.8 | 18521 |

Kanäle mit mehr als 20 % Videos ohne view_count in einer Periode (Größenordnung: Anteil des Kanals an den Views seiner Gruppe im Hauptszenario ab Monat 20):

| Periode | Kanal | gruppe5 | Videos | ohne view_count | Anteil an Gruppen-Views ≥20 (%) |
|---|---|---|---|---|---|
| vorher (−12…−1) | Habibiflo Dawah Produktion | Alternative Medien (rechts) | 4332 | 4331 | 0.00 |
| ≥20 | JENsationelle Meinung | Alternative Medien (rechts) | 572 | 477 | 0.09 |
| ≥20 | DER GLÜCKSRITTER | Alternative Medien (rechts) | 1525 | 316 | 0.65 |

Im Chat geprüft (2026-09-28) wurde der Vorkriegsfall „Habibiflo Dawah Produktion“: Dort fehlen neben view_count auch Dauer und `video_details` für alle Videos bis März 2022, ab April 2022 sind sie vollständig. Die Videos wurden also nie abgerufen und sind nicht gelöscht. Der größte Anteil eines aufgeführten Kanals an den Gruppen-Views liegt bei 0.65 %. Die Lücken verschieben die Marktanteile damit kaum.

### Qualitativ: gesperrte oder gelöschte Kanäle im Suchzeitraum

| Kanal | Datum | Vorgang | Wirkung auf das Fenster | Quelle |
|---|---|---|---|---|
| KenFM (Ken Jebsen) | 22.01.2021 | YouTube löscht den Kanal endgültig (Corona-Richtlinien) | kurz vor Fensterbeginn (rel_monat −12 = Feb. 2021): fehlt im gesamten Vorkriegsfenster | [Link](https://www.heise.de/news/KenFM-Youtube-sperrt-Ken-Jebsens-Kanal-endgueltig-5033216.html) |
| Querdenken 711 | 26.05.2021 | Löschung wegen Falschinformationen (~75k Abonnenten) | fehlt in den Vorkriegsmonaten −9…−1 und danach | [Link](https://netzpolitik.org/2021/desinformation-youtube-loescht-kanal-von-stuttgarter-querdenkern/) |
| RT DE und „Der Fehlende Part“ | 29.09.2021 | Strike am 21.09.2021 (Corona-Fehlinformation), Umgehung über Zweitkanal, beide gelöscht | fehlt in den Vorkriegsmonaten −5…−1 und danach | [Link](https://www.dwdl.de/nachrichten/84672/youtube_loescht_konto_von_rt_deutsch_dauerhaft/) |
| RT- und Sputnik-Kanäle (europaweit) | 01.03.2022 | Geoblocking in Europa wegen des Kriegs, global ab 11.03.2022 | nach Kriegsbeginn: fehlt im Nachher-Fenster (Bias dort in Gegenrichtung) | [Link](https://www.tagesspiegel.de/gesellschaft/panorama/youtube-blockiert-kanale-von-rt-und-sputnik-6853780.html) |

Namensabgleich mit dem Kanon-Sample (`KenFM|Querdenken|RT DE|RT Deutsch|Fehlende Part|Sputnik`): TRT Deutsch, CaspianReport DE.

**Richtung des Bias:** Kanäle, die vor dem Krieg gelöscht wurden (KenFM, Querdenken 711, RT DE), fehlen im Vorkriegsfenster. Soweit sie als rechte Alternativmedien einzuordnen wären, ist der Vorkriegsanteil zu niedrig und der Anstieg überschätzt. Die Sperrung der RT-/Sputnik-Kanäle ab März 2022 wirkt in die Gegenrichtung (fehlende Reichweite nach Kriegsbeginn). Zuschauer gelöschter Kanäle können zudem zu verbliebenen Kanälen im Sample abgewandert sein; dann ist ein Teil des gemessenen Anstiegs eine Verlagerung und kein Wachstum der Nachfrage. Die Größe lässt sich mit den Projektdaten nicht beziffern.

## 6. Einstufung

- Δ(V0) = 28.3 pp [18.3; 39.1]
- Δ(V1) = 17.7 pp [7.6; 30.1] → **hält**
- Δ(V3) = 7.1 pp [-1.4; 19.8] → **hält nicht**

**Formulierung für die Arbeit:** Der Anstieg bleibt im balancierten Panel erhalten, wird aber von Kanälen getragen, die vor dem Krieg klein waren. Da das Sample nach Erfolg am Ende des Zeitraums gezogen wurde, sind gerade gewachsene kleine Kanäle überrepräsentiert; dieser Teil des Anstiegs kann ein Auswahleffekt sein.

Einschränkungen: V3 ist nur eine Näherung an eine Auswahl nach Anfangsgröße, weil historische Abonnentenzahlen fehlen. Kanäle, die 2021 groß waren und bis 2026 unter die Aufnahmeschwelle gefallen sind, fehlen auch in V3. Survivorship ist nur qualitativ abschätzbar (Abschnitt 5).


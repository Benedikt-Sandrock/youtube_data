# Masterarbeit: Strategie und Arbeitsplan

**Erstellt: 2026-09-28.** Grundlage ist die Durchsicht von
`outputs/segment_analysis/zentrale_ergebnisse.md` sowie der Methodik- und
Marktanteils-Berichte. Der Plan ist in **Arbeitspakete (AP)** gegliedert,
die jeweils in **einer eigenen Session** mit leerem Kontext abgearbeitet
werden können. Jedes AP ist ohne diese Chat-Historie verständlich.

**Status-Pflege:** Nach Abschluss eines AP die Checkbox abhaken, eine
Ergebniszeile ergänzen und `zentrale_ergebnisse.md` aktualisieren.

---

## 0. Leitidee und Gliederung der Arbeit

Die bisher lose nebeneinanderstehenden Forschungsfragen 1–4 werden in
einen **Angebot–Nachfrage–Markt-Rahmen** überführt.

Arbeitstitel: *„Was das Publikum belohnt: Angebot und Nachfrage
politischer YouTube-Inhalte in Deutschland seit dem russischen Angriff auf
die Ukraine"*

| Kapitel | Frage | Datenbasis | Identifikation |
|---|---|---|---|
| **A. Angebot** | Wie verändern Kanäle Populismus und Position nach Kriegsbeginn? Driften etablierte und rechte Alternativmedien auseinander? | Frage 1 und Stance, nach AP 1 neu geschätzt | Kriegsbeginn als Schock. Kriegsvideos gegen andere politische Videos desselben Kanals, vor und nach Kriegsbeginn (DiD) |
| **B. Nachfrage** | Welche Inhalte belohnt das Publikum innerhalb eines Kanals? | Positionsprämie (Kern), Populismusprämie, Kriegsprämie | Within-Kanal-Vergleich, Kontrollen für Länge und Upload-Dichte |
| **C. Rückkopplung** (neu) | Passen Kanäle ihr Angebot an das an, was belohnt wurde? | AP 6 | Verzögertes Panel |
| **D. Markt** | Wie verschiebt sich die Reichweite zwischen den Gruppen? | Marktanteile, Schockfenster | Deskriptiv, ausdrücklich **nicht** kausal auf den Krieg zurückgeführt |

**Kernbefunde nach heutigem Stand:**
- **Positionsprämie (belastbarster Befund):** Pro-russische und
  westkritische Kriegsvideos erhalten innerhalb eines Kanals mehr Views.
  Der Effekt übersteht alle Kontrollen und Längenbänder.
- **Marktanteil der rechten Alternativmedien:** Er steigt von ~17 % auf
  ~39 %, themenübergreifend, graduell und breit über die Kanäle verteilt.
  Vorbehalt: AP 2 muss ihn noch absichern.
- **Frage 1:** Die Befunde sind vorläufig. AP 1 muss die Auswahl der
  Vergleichsvideos erst klären.

**In den Anhang bzw. nur kurz erwähnen:**
- die Varianten der Kriegsprämie (Bausteine 1–4, Phasen)
- die Populismusprämie (überwiegend Längenartefakt)
- das Schockfenster (Nullbefund, ein Absatz)

**Nicht mehr verfolgen:**
- weitere Schockfenster- oder Prämien-Spezifikationen (wäre
  Spezifikationssuche)
- Nahost als zweiter Krieg (zu großer neuer Klassifikationsaufwand)

---

## Reihenfolge und Abhängigkeiten

```
AP 1 (Selektions-Asymmetrie Frage 1)  ──► AP 5 (Frage 1 als DiD neu)
AP 2 (Stichproben-Bias Marktanteil)   ──► Kapitel D
AP 3 (LLM-Validierung)                  parallel, unabhängig
AP 4 (Positionsprämie Heterogenität)  ──► AP 6 (Rückkopplung)
AP 7 (Themenaufmerksamkeit)             unabhängig, klein
AP 8 (Kommentare)                       optional, nur wenn Zeit bleibt
AP 9 (Hauptmodelle festschreiben)       nach AP 1–6
```

Priorität: **AP 1 > AP 2 > AP 3 > AP 4 > AP 7 > AP 5 > AP 6 > AP 9 > AP 8**

---

## AP 1: Selektions-Asymmetrie in Frage 1 klären  ☑ (2026-09-28)

**Ergebnis:** Die Ursache ist gefunden. Nicht Prompt, Segmentierung oder
Aggregation sind verantwortlich, sondern die Zusammensetzung der Nachher-Videos.

- **Ursache:** 10.784 der 11.125 Nicht-Kriegsvideos nach Kriegsbeginn sind
  Kurzclips unter 181 s. Sie haben keine Themenklassifikation, weil
  `get_videos_with_text()` sie ausfiltert, und gelten deshalb per Default als
  Nicht-Kriegsvideo. Sie stammen aus der alten Kriegsvideo-Liste.
- **Regel:** Videos unter 181 s werden bei allen transkriptbasierten
  Analysen ausgeschlossen.
- **Analysepopulation:** Dauer ≥ 181 s **und** (Kriegsvideo **oder**
  `politics_final == 1`).
- **Effekte nach der Bereinigung:** Der Einbruch der Nicht-Kriegsvideos
  verschwindet (+0,02 n. s.).

**Kriegsvideos** (Tabellen A und C in `frage1_selektionscheck.md`):
- **Vergleich A** (Kriegsvideos nachher gegen politische Videos desselben
  Kanals vorher):
  - Bei den rechten Alternativmedien sind die Kriegsvideos populistischer
    (+0,16*, Antielitismus +0,23**).
  - Bei ÖRR und traditionellen Medien sind sie deutlich russlandkritischer
    (ÖRR −0,77***).
- **Vergleich C** (Kriegsvideos über die Kriegsjahre 1–4):
  - Die Kriegsvideos der rechten Alternativmedien werden bis Jahr 4
    populistischer (+0,14*) und russlandfreundlicher (+0,19**).
  - ÖRR wird in Jahr 4 weniger populistisch (−0,17**).
  - In fast allen Gruppen wird die Bewertung der Westpolitik negativer.
  - Im balancierten Panel (C2, nur Kanäle mit Kriegsvideos in allen vier
    Jahren) bleiben diese Befunde erhalten. Der Anstieg der ungewichteten
    Mittelwerte insgesamt (C1) geht dagegen großteils auf die veränderte
    Kanalzusammensetzung zurück.

**Zurückgestellt: Vergleich B** (Krieg gegen Nicht-Krieg im selben
Kanal-Monat nach Kriegsbeginn).
- Nach Kriegsbeginn gibt es nur 341 klassifizierte politische
  Nicht-Kriegsvideos.
- Die Klassifikation der 3.035 bereits transkribierten Videos aus
  `political_nonwar_ids.json` ist vorerst zu aufwendig. Sie läge bei etwa
  7.000 Segmenten je Prompt.

Skripte liegen in `scripts/masterarbeit/ap1_*.py`, Berichte in
`outputs/masterarbeit/ap1_selektion/`.

**Folge für AP 2, 4, 7 und die Kriegsprämie:**
- In `channel_video_erfolg.csv` sind 48 % der Videos (37,5 % der Views)
  kürzer als 181 s.
- Alle haben `ist_kriegsvideo = 0`, ihr Kriegsbezug ist also unbekannt.
- Vergleiche von Kriegs- und Nicht-Kriegsvideos sowie Themenanteile
  mindestens als Robustheitsprüfung auf ≥ 181 s filtern.

**Ursprüngliche Aufgabenstellung:**

**Problem (Schnellcheck vom 2026-09-28).** Grundlage:
`outputs/segment_analysis/channel_video_populism.csv`, gemergt mit
`ist_kriegsvideo` aus `channel_video_erfolg.csv`, 279er-Whitelist.

| | Videos | davon Kriegsvideos | Volkszentrismus (Nicht-Kriegsvideos) | Emotionale Intensität (Nicht-Kriegsvideos) |
|---|---|---|---|---|
| Vor Kriegsbeginn | 2.420 | 10 % | 0,90 | 1,52 |
| Nach Kriegsbeginn | 33.372 | 67 % | 0,23 | 0,97 |

Der Post-Effekt auf Populismus gesamt hängt komplett von der
Zusammensetzung ab. Modell: Kanal-FE, Kanal-Monat, geclusterte SE.

| Spezifikation | Populismus gesamt | Antielitismus | Volkszentrismus |
|---|---|---|---|
| Wie im Bericht (alle Videos) | +0,02 (n. s.) | +0,02 (n. s.) | −0,09 |
| Mit Kontrolle `ist_kriegsvideo` | −0,21 (p<0,001) | −0,25 | −0,31 |
| Nur Nicht-Kriegsvideos | −0,25 (p<0,001) | −0,30 | −0,39 |

Der Einbruch bei den Nicht-Kriegsvideos nach Kriegsbeginn ist inhaltlich
unplausibel und deutet auf ein Auswahl- oder Messartefakt hin.
Nominell verlangen sowohl `select_baseline_targets()` als auch
`select_cell_fill_targets()` (`step4_transcript_download/select_targets.py`)
`politics_final == 1`. Die Ursache ist also noch unklar.

**Schritte:**
1. **Herkunft diagnostizieren.** Für die Nicht-Kriegsvideos nach
   Kriegsbeginn in `channel_video_populism.csv` prüfen:
   - Aus welchem LLM-Run stammen sie? (`llm_run_store`)
   - Welche Prompt-Version wurde verwendet?
   - Welchen Wert hat `politics_final` in `screening_state_store`?
   - Welche `topic_categories` haben sie?
   - Wie ist ihre Längenverteilung?

   Zum Vergleich dieselben Kennzahlen für die Baseline-Videos vor
   Kriegsbeginn.
2. **Hypothesen gezielt prüfen:**
   - (a) Ein Teil der Videos stammt aus einem anderen Auswahlweg,
     z. B. `select_war_period_targets()` mit weiter Keyword-Stufe, aber
     `ist_kriegsvideo == 0` wegen abweichender Definition.
   - (b) Die Videos sind wenig politisch, obwohl `politics_final == 1`
     gesetzt ist.
   - (c) Die Segmentierung oder der Prompt unterscheiden sich
     zwischen den Runs.
   - (d) Die Aggregation Segment → Video unterscheidet sich
     (`prepare_channel_scores.py`).
3. **Vergleichbare Analysepopulation definieren.** Vor und nach
   Kriegsbeginn gilt dasselbe Kriterium, z. B. `politics_final == 1`
   **und** `topic_categories` enthält Politics, identische
   Prompt-Version. Die Definition wird im Docstring von
   `frage1_stichprobe.py` bzw. `prepare_channel_scores.py` und in
   `frage1_methodik_und_stichprobe.md` festgehalten.
4. **Robustheitstabelle schreiben:** alle drei Spezifikationen oben mit
   der bereinigten Population, für Populismus UND Stance. Ausgabe nach
   `outputs/masterarbeit/ap1_selektion/regression_results/frage1_selektionscheck.md`.
   Das Skript gehört nach `scripts/masterarbeit/ap1_selektionscheck.py`.

**Fertig, wenn:** Die Ursache ist benannt, und eine einheitliche
Analysepopulation ist definiert und dokumentiert.
`zentrale_ergebnisse.md` Frage 1 trägt einen Warnhinweis, bis AP 5
abgeschlossen ist.

**Achtung:** Falls Videos nachklassifiziert werden müssen (LLM-Kosten),
vorher Umfang und Kosten beziffern und rückfragen.

---

## AP 2: Stichproben-Bias beim Marktanteil prüfen  ☑ (2026-09-28)

**Ergebnis:** Kernbotschaft 1 **hält im balancierten Panel** (V1: +17,7 pp
[7,6; 30,1] = 62 % von V0), **hält nicht bei vor dem Krieg großen Kanälen**
(V3: +7,1 pp [−1,4; 19,8]). ~38 % des Anstiegs stammen von erst nach
Kriegsbeginn aktiven Kanälen. Survivorship ist nur qualitativ abschätzbar,
weil alle Suchläufe erst 2026 stattfanden. Kein Refetch, kein 10k-Lauf.
Details: `outputs/masterarbeit/ap2_stichprobenbias/regression_results/marktanteil_stichprobenbias.md`.

**Detailplan:** `.claude/plans/ap2_stichprobenbias.md`. Dort stehen die
vorab festgelegten Varianten V0–V3, das Entscheidungskriterium und die
Abgrenzung zu AP 1 bei paralleler Bearbeitung.

**Problem 1: Auswahl nach Erfolg am Ende des Zeitraums.** Das Sample
`russia_longitudinal_v1` enthält Kanäle mit >50k Abonnenten **zum
Abrufzeitpunkt**, gefunden über Parteinamen-Suchen 2021–2026.
- 90 der 427 Kanäle sind erst nach Kriegsbeginn aktiv geworden.
- Kanäle, die bis heute gewachsen sind, sind dadurch mechanisch
  überrepräsentiert.
- Das kann den Anstieg der rechten Alternativmedien künstlich erzeugen
  oder verstärken.

**Problem 2: Survivorship.** Gelöschte Videos und Kanäle fehlen, z. B.
die Corona-Löschungen 2021 oder RT DE. Ihr Fehlen kann den Vorkriegsanteil
rechter Kanäle drücken.

**Schritte:**
1. **Balanciertes Panel:** nur Kanäle mit Upload-Aktivität schon in den
   12 Monaten vor Kriegsbeginn (Typ „Aktivitätsphase deckt Kriegsbeginn
   ab", siehe `step2_baseline_channels/activity_phases.py`). Die
   Marktanteils-Zeitreihe von `marktanteil_themen_plots.py` für diese
   Teilmenge neu berechnen, als Monatsreihe und als Level-Shift-Tabelle
   (<20 / ≥20 / ≥40).
2. **Eigenes Wachstum herausrechnen:** Anteil der rechten Alternativmedien
   ohne die 90 erst nach Kriegsbeginn aktiven Kanäle. Zusätzlich eine
   Zerlegung des Anstiegs in (a) Wachstum bestehender Kanäle und (b) neu
   hinzukommende Kanäle.
3. **Survivorship grob schätzen:** Für Videos aus `video_search_hits`
   (Suchen 2021/22) je Gruppe den Anteil bestimmen, der heute keine
   Metadaten mehr liefert. Falls nötig, einen kleinen Metadaten-Refetch
   über `metadata_collection.py` machen (vorher rückfragen). Zusätzlich
   eine Liste bekannter gesperrter Kanäle im Suchzeitraum aufstellen
   (nur qualitativ, für die Limitationen).
4. **Optional, falls 1–3 Zweifel lassen:** 10k-Schwelle
   (`eligible_10k`, 812 Kanäle). Dafür fehlen Video-Metadaten der
   zusätzlichen Kanäle. Das ist ein größerer API-Lauf, Aufwand vorher
   beziffern und rückfragen.

**Ausgabe:**
`outputs/masterarbeit/ap2_stichprobenbias/regression_results/marktanteil_stichprobenbias.md`
(Skript: `scripts/masterarbeit/ap2_marktanteil_stichprobenbias.py`) mit einer ausdrücklichen Methodik-Übersicht (siehe Memory
„document-comparative-analysis-methodology").

**Fertig, wenn:** Klar ist, ob Kernbotschaft 1 im balancierten Panel
bestehen bleibt, und das in `zentrale_ergebnisse.md` eingetragen ist.

---

## AP 3: Validierung der LLM-Klassifikation  ☐

**Problem:** `step5_segment_analysis/README.md` hält fest, dass eine
Validierung gegen Handkodierung fehlt. Für eine Masterarbeit ist das
Pflicht.

**Schritte:**
1. **Stichprobe ziehen:** je Prompt (`POPULISMUS_P`, `POSITION_V1`,
   optional `IDEOLOGIE_I`) 150–200 Segmente, geschichtet nach gruppe5,
   vor/nach Kriegsbeginn und dem Score-Wert (Extremwerte überrepräsentieren).
   Skript nach `scripts/masterarbeit/ap3_validierung_stichprobe.py`.
2. **Kodierbogen erstellen:** CSV oder Excel mit Segmenttext, leeren
   Spalten je Dimension und dem Codebuch-Auszug aus
   `segment_prompts_simple.py`. Das LLM-Ergebnis bleibt verdeckt
   (blind kodieren).
3. **Handkodierung** durch den Nutzer, idealerweise mit einer zweiten
   Person für eine Teilmenge (Intercoder-Reliabilität).
4. **Auswertung:** Krippendorffs α (ordinal), Spearman, Konfusionsmatrix
   und systematischer Bias je Gruppe. Besonders wichtig: Kodiert das LLM
   rechte Kanäle systematisch anders?

**Ausgabe:** `outputs/masterarbeit/ap3_validierung/llm_validierung.md`
(dort auch Stichprobe und Kodierbogen; Auswertungsskript
`scripts/masterarbeit/ap3_validierung_auswertung.py`)

**Fertig, wenn:** Für jede in der Arbeit verwendete Dimension liegt ein
Reliabilitätswert vor. Dimensionen mit α < 0,6 werden in der Arbeit
herabgestuft.

---

## AP 4: Heterogenität der Positionsprämie  ☐

**Frage:** Gilt die Positionsprämie (pro-russisch/westkritisch → mehr
Views) auch bei ÖRR und traditionellen Medien? Dann spräche sie für eine
allgemeine Nachfrage. Oder gilt sie nur bei Alternativmedien? Dann spräche
sie für ein Nischenpublikum.

**Schritte:**
1. In `populismuspraemie_kriegsvideos_bericht.py` (`MODUS="stance"`)
   einen Baustein `dimension:C(gruppe5)` mit Heterogenitäts-F-Test
   ergänzen, falls es ihn noch nicht gibt. Das Muster liefert
   `frage4_kriegspraemie_medientyp_bericht.py::kriegspraemie_je_gruppe_test()`.
2. **Zweite Erfolgsgröße:** `engagement_rate` sowie Kommentare pro View
   als abhängige Variable. Fragestellung: Erzeugen pro-russische Videos
   mehr Interaktion?
3. **Nichtlinearität prüfen:** Position als Kategorien (−2…+2) statt
   linear. Werden Extreme belohnt oder nur eine Richtung?
   (Polarisierung vs. Richtungseffekt)
4. **Phasen:** P1–P5 wie in der Kriegsprämie, nur deskriptiv, keine neue
   Suche nach Signifikanz.

**Ausgabe:**
`outputs/masterarbeit/ap4_positionspraemie/regression_results/positionspraemie_heterogenitaet.md`
(die Erweiterung bleibt im step6-Skript, nur der neue Bericht landet hier)

**Fertig, wenn:** Es gibt eine Aussage „allgemeine Nachfrage vs.
Nischenpublikum" und „Richtung vs. Extremität".

---

## AP 5: Frage 1 als DiD neu schätzen  ☐ (nach AP 1)

**Modell** auf der bereinigten Population aus AP 1, Kanal-Periode-Thema-Zellen:

```
y = α_c + λ_t + β1·krieg + β2·(post × krieg) [+ Gruppen-Interaktionen]
```

`post` selbst entfällt, es wird von λ_t absorbiert. `β2` misst, wie sich
Kriegsvideos gegenüber anderen politischen Videos desselben Kanals
verändern. Zusätzlich die einfache Vorher/Nachher-Schätzung nur auf den
Nicht-Kriegsvideos (allgemeiner Wandel im Programm).

**Schritte:**
1. Die bestehenden Skripte `frage1_populismus_bericht.py` und
   `frage1_stance_bericht.py` um eine Spezifikation mit
   Themenkontrolle erweitern, statt neue Skripte zu schreiben.
2. Gruppenvergleich nach gruppe5 (Medientyp × Ideologie nur für
   Alternativmedien, siehe Memory).
3. Die Kernaussage prüfen, dass etablierte Medien und rechte
   Alternativmedien auseinanderdriften (Antielitismus, Russland-Haltung).
   **Vorab als Hauptspezifikation festgelegt:** ein formaler
   Interaktionstest (`post × gruppe5` bzw. `krieg × post × gruppe5`, F-Test)
   auf der bereinigten Population. Getrennte Schätzungen je Gruppe, bei
   denen eine signifikant ist und eine nicht, gelten nicht als Beleg für
   eine Divergenz. Die alten F-Tests in `zentrale_ergebnisse.md` sind durch
   das Kurzclip-Artefakt verzerrt, das sich auf traditionelle Medien
   konzentriert (siehe Warnhinweis dort).

**Ausgabe:** Die bestehenden Berichte werden an ihrem Ort aktualisiert, dazu
`outputs/masterarbeit/ap5_frage1_did/regression_results/frage1_did.md`.

**Fertig, wenn:** Frage 1 in `zentrale_ergebnisse.md` ist auf die neue
Spezifikation umgestellt und der Warnhinweis aus AP 1 ist entfernt.

---

## AP 6: Rückkopplung zwischen Nachfrage und Angebot  ☐ (nach AP 4, möglichst nach AP 5)

**Neue Forschungsfrage:** Verschieben Kanäle ihre Position oder ihren
Antielitismus in Richtung dessen, was ihnen in der Vorperiode Reichweite
gebracht hat?

**Design:**
1. Je Kanal und Quartal t die kanalspezifische Prämie schätzen: die
   Steigung `log_views ~ position_russland` innerhalb des Kanals im
   Quartal, mit Längenkontrolle. Nur Zellen mit ≥ 8 klassifizierten
   Videos verwenden; Shrinkage oder Gewichtung nach Präzision erwägen.
2. `Δposition_{c,t+1} = α_c + γ·prämie_{c,t} + λ_t + ε`
3. **Alternative mit weniger Rauschen:** Views-Residuen der pro-russischsten
   gegen die übrigen Videos im Quartal t als Anreizmaß.
4. **Placebo:** Die Prämie in t+1 sagt die Positionsänderung in t
   **nicht** voraus.

**Realistische Erwartung:** Die Kennzahlen je Kanal und Quartal sind
verrauscht, ein Nullbefund ist gut möglich. Er wäre trotzdem berichtbar
(„keine Hinweise auf eine Anpassung an das Publikum"). Es werden nur die
vorab festgelegten Spezifikationen gerechnet, keine Nachjustierung.

**Ausgabe:**
`outputs/masterarbeit/ap6_rueckkopplung/regression_results/rueckkopplung_nachfrage_angebot.md`
(Skript: `scripts/masterarbeit/ap6_rueckkopplung.py`)

---

## AP 7: Themenaufmerksamkeit: wer bleibt beim Krieg?  ☐

**Frage:** Wie entwickelt sich der Anteil der Kriegsvideos am
**Upload-Output** je gruppe5 über die Zeit? Das beschreibt die
Angebotsseite und passt zur These der Aufmerksamkeitsverdrängung (P3).

**Schritte:**
1. Aus `video_topic_relevance` und `channel_video_erfolg.csv` den
   Monatsanteil der Kriegsvideos an allen Uploads bzw. an allen
   politischen Uploads je Gruppe berechnen. Dazu dieselben Anteile für
   die vier Vergleichsthemen.
2. Eine Grafik (Monat, gruppe5) und eine Level-Tabelle je Phase P1–P5.
3. **Einfacher Test:** Kanal-FE-Regression des Kriegsvideo-Anteils auf
   Phase × gruppe5.

**Ausgabe:** Plot und Methodik-Markdown unter
`outputs/masterarbeit/ap7_themenaufmerksamkeit/` (Skript:
`scripts/masterarbeit/ap7_themenaufmerksamkeit.py`)

**Aufwand:** klein, eine Session.

---

## AP 8 (optional): Rezeption über Kommentare  ☐

**Frage:** Ist das Publikum russlandfreundlicher oder populistischer als
der Kanal selbst? Und unterscheidet sich die Rezeption derselben Position
zwischen den Gruppen?

**Bestand:** `comments.sqlite` enthält 153.324 Kommentare zu 588 Videos.
Die Zielauswahl ist offen (`step7_comments/README.md`).

**Schritte:** Nur angehen, wenn AP 1–7 erledigt sind.
1. Geschichtete Videostichprobe: gruppe5 × Position des Videos, etwa
   1.500 Videos.
2. Top-Level-Kommentare laden (nur API-Quote).
3. Kommentare per LLM (Batch) auf Russland-Haltung und Antielitismus
   klassifizieren.

Kosten und Laufzeit vorab beziffern und rückfragen.

---

## AP 9: Hauptmodelle festschreiben und Anhang ordnen  ☐ (nach AP 1–6)

**Problem:** Das Projekt enthält sehr viele Spezifikationen. Ohne klare
Hierarchie wirkt das wie eine Suche nach Signifikanz.

**Schritte:**
1. `outputs/masterarbeit/hauptmodelle.md` anlegen: je Kapitel (A–D)
   **genau ein** Hauptmodell mit Gleichung, Stichprobe, Kontrollen,
   Granularität und Begründung. Alles andere wird als Robustheitsprüfung
   im Anhang gelistet.
2. Eine Tabelle „Befund → Hauptmodell → Robustheitsprüfungen → hält/hält
   nicht".
3. Eine Limitationsliste: Views als einmaliger Snapshot, Auswahl nach
   Erfolg am Ende des Zeitraums, Survivorship, keyword-basierte
   Themenzuordnung, LLM-Validität, keine Kausalität beim Marktanteil,
   Mehrfachtests (z. B. Benjamini-Hochberg für die Heterogenitätstests).
4. `zentrale_ergebnisse.md` auf die Kapitelstruktur A–D umbauen, alte
   Abschnitte in einen Anhang-Teil verschieben.
5. **Offener Bug (aus AP 2):** `deskriptiv_aggregation.py::lade_ideologie()`
   dedupliziert nicht auf channel_id (3 doppelte channel_ids in
   `channel_classification_ideology.csv`). Jede Videozeile dieser Kanäle wird
   dadurch in allen gruppe5-basierten Berichten der Whitelist-Pipeline
   verdoppelt. `lade_basisdaten(kanalquelle="kanon")` umgeht das lokal. Den
   zentralen Fix vornehmen und die betroffenen Berichte neu erzeugen.

---

## Hinweise für jede Session

- Zuerst `.claude/CLAUDE.md`, dann diesen Plan (nur das jeweilige AP),
  dann die im AP genannten Dateien lesen. `zentrale_ergebnisse.md` nicht
  komplett lesen (über 1.000 Zeilen), sondern gezielt per Suche.
- Längere Läufe und API- oder LLM-Aufrufe **vor dem Start** rückfragen.
- **Ablage:** Neue Ergebnisse landen in `outputs/masterarbeit/apN_<thema>/`
  (Konstante `MASTERARBEIT_OUTPUTS` in `config/paths.py`),
  Regressionsausgaben als Markdown im Unterordner `regression_results/`.
  Eingangsdaten (`channel_video_*.csv` usw.) bleiben in
  `outputs/segment_analysis/`. Übersicht:
  `outputs/masterarbeit/README.md` und `scripts/masterarbeit/README.md`.
- Einmalige AP-Skripte kommen nach `scripts/masterarbeit/apN_<thema>.py`.
  Dauerhaft genutzte Erweiterungen kommen in die bestehenden
  `step6_auswertung/`-Skripte; dabei Docstrings und READMEs mit anpassen.
- Nach Abschluss eines AP die Status-Spalte in
  `outputs/masterarbeit/README.md` aktualisieren.
- Transkript-Verfügbarkeit nur über den `transcript_store` prüfen.

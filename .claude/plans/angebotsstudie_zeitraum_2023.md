# Plan: Angebotsstudie (claude_classification) um Juni–Oktober 2022 erweitern

**Einstieg für eine neue Session:** erst `.claude/CLAUDE.md`, `README.md`, `COMPLETE_PROCESS.md`, dann
`data/claude_classification/anleitung_codierlauf.md` und diesen Plan. Der Abschnitt „Stand“ zeigt, was erledigt ist.
**Erstellt:** 27.10.2026. **Umfang festgelegt:** 28.10.2026 (Schritt 0). Der Dateiname stammt noch aus der
ursprünglichen Variante bis Ende 2023 und bleibt, damit Verweise gültig bleiben.

## Ziel
Die Angebotsstudie (Codebuch 2.0, Sonnet-Teilaufträge, blinde Batches) über den bisherigen Zeitraum
01.01.–30.04.2022 hinaus auf **01.06.2022–31.10.2022** ausdehnen. Gleiche 34 Kanäle, gleiches Codebuch,
gleiche Segmentierung und Ziehungslogik. **Wochenlimit 14 Videos je Kanal-Woche**, reihum nach Tagen gezogen
(also möglichst 2 Videos je Tag, Tage mit weniger Videos geben Plätze ab, wie bisher in `videoauswahl()`).
Bereits codierte Segmente (Batches 0001–0186, 9.084 Segmente) bleiben unverändert und werden nicht neu codiert.

Nutzen für die Forschungsfragen: FF1 (hält der Anstieg nach Kriegsbeginn an oder klingt er ab? Verschiebung auf
Energie/Inflation/Gasumlage im Sommer/Herbst 2022) und als Inhaltsvariable für FF2–FF4.

**Lücke Mai 2022:** Der Mai wird nicht gezogen. Die Zeitreihe ist daher nicht durchgehend. Für den Vergleich
„Kriegsbeginn (bis 30.04.)“ vs. „Sommer/Herbst 2022“ ist das unkritisch. Für Wochen-Verlaufsgrafiken muss die
Lücke sichtbar bleiben (keine Linie über den Mai interpolieren). Den Mai kann man später mit demselben Verfahren
nachziehen, ohne dass sich etwas an der Auswahl Jun–Okt ändert.

## Ausgangslage (Bestandsaufnahme 27./28.10.2026)
- Kette: `scripts/adhoc/zufallsstichprobe_videos.py` (Video-IDs, long, N je Kanal-Woche) →
  `src/youtube_code/step4_transcript_download/prepare_csv.py` (schreibt `metadata_new.csv`/`segments_new.csv`
  aus Registry bzw. transcript_store) → `aufbereitung_angebotsstudie.py` (Fenster, Segmente, `schluessel.csv`) →
  `ziehung_angebotsstudie.py` (Limit 21 Videos/Kanal-Woche, 4 Segmente/Video, Batches append-only) →
  Codierung nach `anleitung_codierlauf.md` → `status_codierlauf.py`/`pruefung_v2.py` →
  `angebot/check_results.py` (xlsx) → `angebot/process_results.py` (Video-Ebene, `video_results.csv`) →
  `angebot/plot_results.py`, `scripts/adhoc/plot_*_wochen_medientyp.py`.
- Bisher: 34 Kanäle (11 alt. links, 13 alt. rechts, 5 ÖRR, 5 traditionell), 4.638 gezogene Videos,
  9.210 ausgewählte Segmente, ~2,0 Segmente je gezogenem Video. Jan–Apr lief mit Limit **21** (bis zu 3/Tag).
- **01.06.–31.10.2022 in der Registry** (diese 34 Kanäle, Stand 28.10.2026): 10.051 long-Videos mit Format,
  dazu **3.545 WELT-Videos ohne `video_format`** (WELT hat im ganzen Zeitraum kein Format, fiele mit
  `VIDEO_FORMAT = "long"` komplett heraus). Davon haben nur **784 ein Transkript** im `transcript_store`.

### Volumen (Schätzung 28.10.2026, WELT ohne Format als long gezählt = Obergrenze)

| Limit Videos/Kanal-Woche | Videos | Segmente (~2/Video) | Batches (~49 Segm.) |
|---|---|---|---|
| 5 | ~2.600 | ~5.200 | ~105 |
| 10 | ~4.200 | ~8.400 | ~170 |
| **14 (gewählt)** | **~5.100** | **~10.100** | **~205** |
| 21 | ~6.300 | ~12.500 | ~255 |

- Annahme: alle Transkripte ladbar. Realistisch 5–10 % Ausfall, also eher ~4.700 Videos / ~190 Batches.
  Das ist etwa so viel wie die bisherigen 186 Batches, bei 35–40 Batches/Tag **~5–6 Tage Codierzeit**.
- **Transkript-Downloads: ~4.500–5.000 neue** (nur 784 vorhanden), plus Nachladen für Ausfälle.
- Das Limit greift fast nur bei den großen Kanälen: ÖRR/traditionell (tagesschau, phoenix, WELT, BILD, faz,
  DW, ZDFheute, SPIEGEL) sowie Erfolgskanal, FinanzmarktWelt, NachDenkSeiten, Deutschland Kurier, Gerald Grosz
  (je ~220–320 Videos). Kleine Kanäle (Rayk Anders 2, Volksverpetzer 6, LEO 21, Höfgen 22, MrWissen2go 23 …)
  gehen vollständig ein. Bei alternativen Kanälen bleibt die Fallzahl also klein, unabhängig vom Limit.

### Wochengrenzen
Wochen sind am 24.02.2022 (Donnerstag) verankert. Das Fenster 01.06. (Mi) – 31.10. (Mo) ergibt 23 Wochen,
davon zwei Teilwochen: Woche 13 (26.05.–01.06.) enthält nur den 01.06., Woche 35 (27.10.–02.11.) nur 27.–31.10.
Für die Ziehung ist das unkritisch (Gewicht je Kanal-Woche). **In Wochengrafiken die Randwochen ausblenden oder
als Teilwochen kennzeichnen.** Alternative: Fenster auf volle Wochen legen (02.06.–02.11.2022, 22 Wochen).
→ offen, Nutzer fragen (Default: Daten wie vom Nutzer genannt).
Zur bisherigen Periode gibt es keine Überschneidung: Die letzte alte Woche ist 28.04.–04.05., die erste neue
26.05.–01.06. Das zeitabhängige Limit lässt sich also eindeutig über den Wochenbeginn zuordnen.

## Schritte

### 0. Entscheidungen (Nutzer, 28.10.2026)
- [x] Zeitraum der Erweiterung: **01.06.2022–31.10.2022** (statt 05/2022–12/2023).
- [x] Wochenlimit: **14**, reihum nach Tagen (möglichst 2/Tag). Jan–Apr bleibt bei 21.
- [ ] Segmente je Video bleiben bei 4 (Empfehlung: ja, wegen Vergleichbarkeit).
- [ ] Randwochen: Fenster wie genannt oder auf volle Wochen (02.06.–02.11.) legen.
- Kanalliste auf die bisherigen 34 Kanäle **einfrieren** (siehe Schritt 3). Neue Kanäle wären eine eigene Entscheidung.

### 1. Backup
`angebot/batches/` (inkl. `manifest.csv`), `angebot/codierung/`, `angebot/schluessel.csv`,
`angebot/segmente_alle.csv`, `angebot/stichprobe_videos.csv`, `angebot/stichprobe_segmente.csv`,
`codierung_gesamt.jsonl`, `metadata_new.csv` nach `angebot/archiv_vor_erweiterung_2022h2/` kopieren.
Nach Abschluss zur Löschung melden.

### 2. Datenbasis: Formate und Transkripte
1. **WELT-Formate nachholen:** `step1_sample/channel_video_formats.py` für WELT, Fenster 2022-06-01 bis
   2022-10-31 (~3.550 Videos, yt-dlp-Pfad, kaum Quota). Vorher fragen.
2. **Video-IDs für den Download nach der Ziehungspriorität bestimmen (jetzt Pflicht, nicht optional):**
   `zufallsstichprobe_videos.py` zieht zufällig N Videos je **Kalenderwoche** und kennt die Reihum-nach-Tagen-
   Logik nicht. Bei Limit 14 würde eine zufällige Vorauswahl einzelne Tage leer lassen, und das Ziel „möglichst
   2 pro Tag“ wäre schon vor der Ziehung verfehlt. Deshalb: Prioritätslogik aus `videoauswahl()` in eine
   Funktion auslagern, die auf **allen long-Videos der Registry** (nicht nur mit Transkript) die `prio_woche`
   berechnet und die IDs mit `prio_woche <= 14` ausgibt (gleicher `SEED`, gleiche Hashes, Wochenanker 24.02.).
3. **Transkripte laden** (step4, `download_transcripts()`) für diese ~5.100 IDs (minus 784 vorhandene).
   Vorher fragen (Laufzeit, IP-Sperren). Verfügbarkeit nur über `transcript_store` (`has_transcript()`).
4. **Nachladen für Ausfälle:** Kanal-Wochen, in denen nach dem Download weniger als min(14, n_woche) Videos ein
   Transkript haben, rücken mit den nächsten Prioritäten (15, 16, …) nach, bis das Limit erreicht oder die
   Kanal-Woche erschöpft ist. 1–2 Runden genügen. Ergebnis je Monat und Kanal mit `has_transcript()` prüfen.
   Hinweis: Die Ziehung (Schritt 4) rechnet die Priorität dann auf den Videos **mit** Transkript neu. Weil ein
   ausgefallenes Video einfach übersprungen wird, entspricht das genau dem Nachrücken.

### 3. Aufbereitung (`aufbereitung_angebotsstudie.py`) umstellen
- **Eingabe direkt aus Registry und `transcript_store`** statt über `metadata_new.csv`/`segments_new.csv`.
  Das ist laut CLAUDE.md die maßgebliche Quelle. Neue Konstante `VIDEO_IDS_DATEI` (Liste aus Schritt 2 plus
  die bisherigen IDs aus `metadata_new.csv`). `prepare_csv.py` entfällt für diesen Zweck.
- **Zwei Zeitfenster** statt eines: `ZEITFENSTER = [("2022-01-01", "2022-04-30"), ("2022-06-01", "2022-10-31")]`.
  `phase` bleibt binär (vor/nach). Feinere Perioden erst in der Auswertung.
- **Kanalliste einfrieren:** `KANAELE_STUDIE` (34 channel_ids) als Konstante. Der Medientyp wird für diese Kanäle
  aus dem bisherigen `schluessel.csv` übernommen und nicht neu aus `kanaele_roh.dta` hergeleitet. Sonst verschiebt
  ein Neu-Export (Ideologie-Grenzen ±0,5) Kanäle zwischen links/zentral/rechts, und die Ziehung bricht ab
  (Manifest-Prüfung) oder ändert die Stichprobe.
- **Neue Konsistenzprüfung:** Für alle Segmente aus `batches/manifest.csv` muss der Text identisch mit dem bisherigen
  `segmente_alle.csv` sein. Bisher wird das nur für die Pilotsegmente geprüft. Ein erneut geladenes oder
  aktualisiertes Transkript im Store würde sonst still andere Segmentgrenzen erzeugen.
- Kollisionsprüfung der anonymen IDs (40 bit) bleibt (bei ~17.000 Videos praktisch kein Risiko).
- Docstring anpassen (Datenquelle, Zeitfenster, Einfrieren).

### 4. Ziehung (`ziehung_angebotsstudie.py`) anpassen
1. **Zeitabhängiges Limit:** `LIMIT_PRO_WOCHE` wird zu einer Liste von Perioden:
   `[("2022-01-01", "2022-04-30", 21), ("2022-06-01", "2022-10-31", 14)]`. Zuordnung einer Kanal-Woche über ihren
   Wochenbeginn (keine Woche überspannt beide Perioden, siehe „Wochengrenzen“). Die Manifest-Prüfung „Senken nicht
   vorgesehen“ läuft dann **je Periode** (sonst bricht sie ab, weil 14 < 21). Im Manifest stehen
   `limit_pro_woche` und eine neue Spalte `periode_limit`.
2. Die bisherige Auswahl für Jan–Apr muss exakt reproduziert werden. Prüfung: Die Menge der ausgewählten Segmente
   bis 30.04.2022 ist identisch mit der bisherigen `stichprobe_segmente.csv`. Sonst Abbruch.
3. Prioritätsfunktion gemeinsam mit Schritt 2.2 nutzen (eine Implementierung, kein Duplikat).
4. **Ziehungsgewicht:** Bisher `n_woche (mit Transkript) / gezogen`. Zusätzlich `n_woche_registry`
   (alle long-Videos der Kanal-Woche) ausgeben, damit Hochrechnungen über Perioden mit verschieden dichter
   Transkriptabdeckung vergleichbar sind. In Jan–Apr hatten nur 5.606 von 10.952 long-Videos ein Transkript;
   in Jun–Okt wird die Abdeckung durch den gezielten Download ganz anders aussehen.
5. Docstring (Regel 1 nennt Limit 14 als Beispiel, Konstante steht auf 21 – vereinheitlichen) und Log je Periode.

### 5. Codebuch und Anleitung
- **Codebuch 2.1, nur die Gegenstandsbeschreibung ändern, keine Regeln:**
  - Abschnitt 1 „Material“: Zeitraum 01.01.–30.04.2022 und 01.06.–31.10.2022.
  - Block E (Minister): im Zeitraum keine Änderung (Pistorius erst ab 01/2023), nichts zu ergänzen.
  - Abschnitt „Versionierung“: 2.1 = nur Gegenstand erweitert, Codierregeln unverändert.
  - `codebuch_angebotsstudie_v2.md` nicht überschreiben. `codebuch_angebotsstudie_v2_1.md` neu anlegen.
- `status_codierlauf.py`: Codebuch-Version aus Batch-Zuordnung (Batch ≤ 0186 → 2.0, danach → 2.1) statt hart
  „2.0“. `anleitung_codierlauf.md`: Pfad zum Codebuch 2.1 und Hinweis, dass ab Batch 0187 die Erweiterung beginnt.
- **Drift-Check vor dem Massenlauf:** Je Medientyp einen alten Batch (insgesamt 4–5 Batches, ~200–250 Segmente)
  mit Codebuch 2.1 und dem aktuellen Sonnet neu codieren. Übereinstimmung mit der Erstcodierung je Feld
  ausweisen (kodierbar, hauptthema, krieg_bezug, rus_status/score, estab_status/score). Neue Ausgaben nach
  `angebot/codierung_driftcheck/`, nicht nach `codierung/`. Kriterium vorab festlegen, z. B. Übereinstimmung
  nicht schlechter als Opus/Sonnet in `hand50_opus_vs_sonnet.csv`.

### 6. Codierung
Unverändert nach `anleitung_codierlauf.md` ab Batch 0187. Fortschritt mit `status_codierlauf.py` prüfen.
~190–205 Batches, also ~5–6 Tage beim bisherigen Tempo. Die Batch-Reihenfolge ist zufällig über Videos, ein
Abbruch nach einem Teil der Batches bleibt also auswertbar.

### 7. Ergebnisverarbeitung und Auswertung anpassen
- `angebot/check_results.py`: Batchbereich ist hart codiert (126–186). Stattdessen alle fertigen Batches oder
  einen konfigurierbaren Bereich verwenden. Langfristig `codierung_gesamt.jsonl` + `segmente_alle.csv` statt der
  xlsx-Zwischenstufe nutzen.
- `angebot/process_results.py`: `phasen_grenzen` endet am 30.04.2022, spätere Videos bekämen `phase = NaN`.
  Perioden ergänzen (Vorschlag: Vorher / Eskalation / Kriegsbeginn bis 30.04. / Sommer 01.06.–31.08. /
  Herbst 01.09.–31.10.). Ziehungsgewichte übernehmen.
- `angebot/plot_results.py`, `scripts/adhoc/plot_themen_wochen_medientyp.py`,
  `scripts/adhoc/plot_ukraine_anteil_wochen_medientyp.py`: x-Achse mit Lücke Mai (nicht durchverbinden),
  Teilwochen am Rand kennzeichnen.
- Wenn die Ergebnisse in den zentralen Datensatz sollen: `export_stata_rohdaten.py` + Codebuch erweitern.
  Dann ist ein Neu-Export fällig (~40 min, vorher fragen). Das ist eine eigene Entscheidung.

### 8. Doku
`anleitung_codierlauf.md`, Docstrings aller geänderten Skripte, ggf. `COMPLETE_PROCESS.md` (die Angebotsstudie
ist dort bisher nicht beschrieben).

## Stand
- [x] Bestandsaufnahme und Volumenschätzung (27.10.2026, für Jun–Okt 2022 neu geschätzt 28.10.2026)
- [x] Schritt 0: Zeitraum 01.06.–31.10.2022 und Limit 14 festgelegt (28.10.2026); Segmente/Video und
      Randwochen noch offen
- [x] 28.10.2026, **Vereinfachung durch den Nutzer** (ersetzt Schritt 2.2): Video-IDs mit
      `scripts/adhoc/random_video_ids_for_channel_period.py` gezogen: Sample aus `channels_check.xlsx`
      (media_category 1/2/5, sample 1–5, ohne Ausland, **150 Kanäle, nicht die 34**), volle Wochen
      02.06.–02.11.2022 (22 Wochen, Anker Do 24.02.), max 14 long-Videos je Kanal-Woche, reihum nach Tagen.
      Ergebnis: 11.537 Videos aus 105 Kanälen, 1.163 davon mit Transkript. WELT: 3.569 von 3.925 Videos ohne
      Format → Liste `data/channel_lists/video_formats/angebot_2022h2_fehlende_formate.csv`, Formate noch nachholen.
- [ ] Schritte 1–8 (Kanalumfang für Aufbereitung/Ziehung noch klären: 34 oder 105/150 Kanäle)
## TO DOs

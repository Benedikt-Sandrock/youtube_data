# Plan: Keyword-Klassifikation als billiger Vorfilter für LLM-Themenkodierung

Stand: 04.11.2026. Ziel: Vor einer teuren LLM-Klassifikation lokal prüfen, ob es Trends
(vor/nach Kriegsbeginn, nach Medientyp, nach Kanal) gibt, die eine genauere Analyse lohnen.
Erfasst werden nur **Themen** (15 Kategorien, Mehrfachnennung, plus Hauptthema) und
**Kriegsaspekte** (15 Aspekte, nur wenn `krieg_ukraine` Thema ist). Andere Variablen nicht.

## Daten

- Eingabe: `data/claude_classification/angebot/results_segment_level.csv`
  (nicht direkt in `claude_classification/`!). 9214 kodierbare Segmente, 4548 Videos,
  34 Kanäle, Jan–Apr 2022 (Phase „vor“ 01.01.–23.02., „nach“ 24.02.–30.04.).
  Spalten u. a. `text` (klein, ohne Satzzeichen), `themen`, `hauptthema`, `krieg_aspekte`
  (Listen als String → `ast.literal_eval`), `video_id`, `channel_id`, `medientyp`, `phase`, `datum_lokal`.
  Enthält 176 exakte Dubletten (je das letzte Segment eines Batches, Fehler in `check_results.py`, behoben):
  eindeutig sind 9038 Segmente. Training und Holdout-Lauf nutzen die Datei noch mit Dubletten.
- Kategorien-Definitionen: `data/claude_classification/codebuch_angebotsstudie_v2.md`.
- Erzeugt von `data/claude_classification/angebot/process_results.py` (nicht verändert).

## Umsetzung (fertig)

Skript: `scripts/adhoc/keyword_klassifikation_segmente.py` (mit `.venv/Scripts/python` ausführen;
System-Python hat kein sklearn; `tabulate` fehlt → eigener `md_table`-Helfer).

Zwei Klassifikatoren:
- **Dict**: Regex-Stämme aus dem Codebuch (`LEXIKON_THEMEN`, `LEXIKON_ASPEKTE`); Mindest-Trefferzahl
  je Label F1-optimal auf Train (1–15). `unpolitisch` = kein anderes Thema; Aspekt `sonstiges`
  hat kein Lexikon (immer 0).
- **LR**: TF-IDF (Uni+Bigramme, `min_df=3`, `max_df=0.5`, sublinear) + logistische Regression je Label
  (`class_weight="balanced"`, liblinear, C=4), Schwelle F1-optimal per 5-facher gruppierter CV.
- Aspekte nur auf LLM-Kriegssegmenten trainiert; End-to-End nur vergeben, wo der Klassifikator
  selbst `krieg_ukraine` erkennt.

Schalter `SPLIT_MODUS` im Konfigurationsblock (aktuell `"kanal"`):
- `"video"`: ein Split nach `video_id`, Testanteil 0,4, Seed 42 (Train 5564 / Test 3650 Segmente).
  ~4 min. Ausgabe `bericht.md`, `test_vorhersagen.csv`.
- `"kanal"`: Kanal-Holdout per Kreuzanpassung, 3 Folds (Kanäle je Medientyp verteilt), innere CV
  nach Kanal gruppiert; Testset = alle 9214 Segmente. ~9 min. Ausgabe `bericht_kanal_holdout.md`,
  `test_vorhersagen_kanal_holdout.csv` (inkl. F1-Vergleich mit dem Video-Split in Abschnitt 0).

Ausgaben in `scripts/adhoc/keyword_klassifikation_segmente/`.

## Ergebnisse

### Segmentgüte (F1; Video-Split → Kanal-Holdout)

| Label | Dict | LR |
|---|---|---|
| krieg_ukraine | 0,92 → 0,92 | 0,94 → 0,93 |
| corona | 0,85 → 0,83 | 0,89 → 0,86 |
| energie | 0,81 → 0,82 | 0,78 → 0,78 |
| wirtschaft | 0,76 → 0,77 | 0,80 → 0,81 |
| unpolitisch | 0,64 → 0,66 | 0,83 → 0,76 |
| migration / klima / innenpolitik | 0,58–0,73 | 0,57–0,66 |
| eu / usa / gender / sonstiges_politisch | 0,39–0,48 | 0,47–0,57 |

Hauptthema-Übereinstimmung: Dict 73 % (beide Splits), LR 79,0 % → 77,5 %.
Aspekte (bedingt auf LLM-Krieg, Kanal-Holdout): sanktionen 0,85/0,76, energie_preise_inland 0,84/0,79,
waffenlieferungen 0,77/0,76, kriegsgeschehen 0,71/0,78, zivilisten 0,62/0,75, gefluechtete 0,72/0,73;
schwach: finanzhilfe 0,37/0,45, russland_innen 0,39/0,56, truppen_einsatz 0,46/0,56, sonstiges –/0,42.

**Kanal-Holdout kostet kaum Güte** → Übertragbarkeit auf neue Kanäle (gleicher Zeitraum) gegeben.
Verlust nur bei LR für `unpolitisch` und `usa` (kanaltypisches Vokabular). Dict-Schwellen über
Folds stabil → Dict robuster, LR bei Kriegsaspekten etwas genauer.

### Trendtreue (Kanal-Holdout, Δ = nach − vor, LLM / Dict / LR)

- Gut: krieg +0,42/+0,40/+0,38, corona −0,18/−0,16/−0,18, energie +0,10/+0,09/+0,11; sanktionen,
  gefluechtete, zivilisten, energiepreise, sondervermögen ebenfalls. Wochen-r meist > 0,9,
  Kanal-Δ-r 0,8–0,97 (32 Kanäle). Medientyp-Deltas für Krieg/Corona/Energie stimmen.
- **Fehlalarme / falsche Stärke:**
  - verhandlungen_diplomatie bei oerr: LLM +0,011, Dict +0,098, LR +0,058
  - truppen_einsatz gesamt: LLM +0,038, Dict +0,099
  - nato_eu_beitritt gesamt: LLM +0,001, Dict +0,037
  - finanzhilfe gesamt: LLM +0,034, LR +0,076
  - wirtschaft bei alternativ_links: LLM −0,016, beide positiv (Vorzeichen falsch, auch im Video-Split)
  - wirtschaft Wochen-r Dict nur 0,63; eu/usa/gender/iran/nahost/sonstiges_politisch Kanal-Δ kaum verlässlich

## Einschätzung

- Brauchbar als Vorfilter für **große Verschiebungen (≳ 5 Prozentpunkte)** bei häufigen Themen
  (Krieg, Corona, Energie, Wirtschaft, Migration) und häufigen Kriegsaspekten.
- **Nicht** belastbar für kleine Effekte, Medientyp-Unterschiede von wenigen Prozentpunkten und
  die schwachen Kategorien. Ein nur per Keyword gefundener kleiner Trend ist ein Prüfauftrag
  fürs LLM, kein Befund.
- Ungetestet: **anderer Zeitraum** (z. B. 2023, vgl. `.claude/plans/angebotsstudie_zeitraum_2023.md`).
  Vokabular verschiebt sich (neue Orte, Waffensysteme, Corona weg).
- Bezug zu den Forschungsfragen: nur Vorarbeit für Themenanteile; Populismus/Erfolg nicht erfasst.

## Mögliche nächste Schritte (nicht begonnen)

1. **Zeitliche Validierung**: kleine LLM-kodierte Stichprobe aus dem Zielzeitraum (≈ 300–500 Segmente)
   als Kalibrierung; Klassifikatoren auf 2022 trainieren, dort testen.
2. **Anwendung auf die gezogenen Video-IDs (Jan–Okt 2022)**: Skript eingerichtet (04.11.2026), noch nicht
   gelaufen: `src/youtube_code/step3_topic_relevance/classify_segment_topics.py` (Training auf allen 9214
   Segmenten, LR-Schwellen per Kanal-CV, Batches, fortsetzbar, Ausgabe
   `scripts/adhoc/keyword_klassifikation_segmente/anwendung_2022/`). Segmentierung reproduziert die
   Angebotsstudie exakt. 2210 gezogene Videos liegen im Trainingsset (`im_training = 1`).
   Ursprüngliche Notiz – **Anwendung aufs Gesamtkorpus**: Transkripte aus dem `transcript_store`
   (`data/store/transcripts.sqlite`, `get_transcripts()`), gleiche Segmentierung wie in der
   Angebotsstudie nötig (prüfen, wie `ziehung_angebotsstudie.py`/`aufbereitung_angebotsstudie.py`
   segmentieren). Vor dem Start fragen (langer Lauf). Für dauerhafte Nutzung ggf. als
   wiederverwendbares Modul nach `src/youtube_code/` und Ergebnis in den Rohdaten-Export
   (dann Codebuch `docs/codebuch_rohdatensatz.md` + Export-Neulauf ~40 min, vorher fragen).
3. Optional: Lexikon für schwache Kategorien (truppen_einsatz, nato_eu_beitritt, diplomatie)
   schärfen – Fehlalarme dort stammen v. a. aus zu breiten Stämmen (z. B. „neutral“, „gespräche“,
   „atomwaff“, „weltkrieg“); auf Train-Fehlern prüfen, nicht auf Test (Überanpassung vermeiden).

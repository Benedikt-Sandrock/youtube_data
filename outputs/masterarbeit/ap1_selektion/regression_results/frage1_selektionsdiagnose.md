# AP 1 – Diagnose der Selektions-Asymmetrie in Frage 1

*Erzeugt von `scripts/masterarbeit/ap1_selektionsdiagnose.py`.*

## Methodik-Übersicht

- **Grundgesamtheit:** alle Videos in `channel_video_populism.csv` von Kanälen der 279er-Whitelist (`frage1_kanal_whitelist.csv`): **35,792 Videos**, 279 Kanäle. Das ist exakt der Input von `frage1_populismus_bericht.py`.
- **vor/nach:** `rel_monat < 0` bzw. `>= 0` (Kalendermonat relativ zum 24.02.2022). Die Regressionen nutzen das Fenster `rel_monat` -12…42 wie der Frage-1-Bericht; die deskriptiven Tabellen nutzen alle Videos.
- **Kriegsvideo:** `ist_kriegsvideo` aus `channel_video_erfolg.csv` (`video_topic_relevance.is_relevant` für `russia_ukraine_war`, Keyword-basiert).
- **Herkunft/Auswahlweg:** Nirgends gespeichert. Hier rekonstruiert (a) über die `dataset_id` des LLM-Runs, aus dem das Video stammt, und (b) heuristisch über `screening_state.interval_index`, `politics_final`, `political_nonwar_ids.json` und das Kriegsfenster 2022-02-20–2022-03-10.
- **Post-Effekt in Teilmengen (Abschnitt D):** Nur Nicht-Kriegsvideos. Sie werden zu Kanal-Monat-Mitteln aggregiert; darauf läuft `y ~ C(channel_id) + post` mit SE geclustert nach Kanal (`bericht_utils.post_dummy_test`). Das entspricht Spezifikation 3 des Schnellchecks.
- **Prompt/Modell:** Alle Produktions-Runs für `POPULISMUS_P` verwenden Prompt-Version v4 (`prompt_sha1` 1aac52e5…), `gemini-2.5-flash`, Temperatur 0, thinking_budget 0 (`llm_runs.sqlite`, geprüft).

## Reproduktion des Schnellchecks

| post | n | anteil_krieg | volkszentrismus (Nichtkrieg) | emotionale_intensitaet (Nichtkrieg) |
|---|---|---|---|---|
| vor | 2420 | 0.103 | 0.896 | 1.524 |
| nach | 33372 | 0.667 | 0.232 | 0.975 |

## A. Zusammensetzung: Herkunft der Videos

### A1. Nach LLM-Datensatz (`dataset_id`)

| dataset_id | nach / Krieg | nach / Nichtkrieg | vor / Krieg | vor / Nichtkrieg |
|---|---|---|---|---|
| descriptive_sample_baseline_populism_segments | 0 | 0 | 0 | 1763 |
| descriptive_sample_war_segments | 6062 | 1490 | 0 | 0 |
| parse_errors_POPULISMUS_P_segments | 13 | 1 | 0 | 0 |
| pilot_classification_segments | 0 | 479 | 0 | 315 |
| populism_todo_segments | 1405 | 0 | 2 | 0 |
| videos_to_classify_populism1_segments | 1615 | 3104 | 0 | 0 |
| videos_to_classify_populism2_segments | 3099 | 2119 | 0 | 0 |
| videos_to_classify_populism3_segments | 3435 | 1829 | 1 | 0 |
| videos_to_classify_populism4_segments | 2630 | 1090 | 227 | 89 |
| war_vids_segments | 3988 | 1013 | 19 | 4 |

### A2. Nach rekonstruiertem Auswahlweg

| herkunft | nach / Krieg | nach / Nichtkrieg | vor / Krieg | vor / Nichtkrieg |
|---|---|---|---|---|
| baseline_nach (Intervall -1) | 208 | 0 | 0 | 0 |
| baseline_vor (Intervall 0-3, pf=1) | 0 | 0 | 136 | 1770 |
| cellfill_krieg / sonstige Kriegsvideos | 19224 | 0 | 94 | 0 |
| kriegsfenster | 243 | 0 | 19 | 0 |
| kurzclip < 181 s ohne Themenklassifikation | 0 | 10784 | 0 | 401 |
| screening_nach (Intervall >= 4, pf=1) | 2572 | 341 | 0 | 0 |

## B. Kennzahlen je Zelle (alle Videos, ohne Fensterbeschränkung)

| index | nach / Krieg | nach / Nichtkrieg | vor / Krieg | vor / Nichtkrieg |
|---|---|---|---|---|
| n_videos | 22247.000 | 11125.000 | 249.000 | 2171.000 |
| Anteil pf=1 | 0.121 | 0.031 | 0.546 | 0.815 |
| Anteil pf=0 | 0.021 | 0.000 | 0.024 | 0.000 |
| Anteil pf fehlt | 0.855 | 0.969 | 0.430 | 0.185 |
| Anteil topic_politics | 0.867 | 0.913 | 0.795 | 0.482 |
| Anteil Kat. 25 (News&Politics) | 0.785 | 0.869 | 0.807 | 0.550 |
| Anteil kw_teiltreffer | 0.000 | 0.000 | 0.000 | 0.000 |
| Anteil in_screening | 1.000 | 0.031 | 0.996 | 0.815 |
| Dauer Median (min) | 12.300 | 1.583 | 14.117 | 10.717 |
| n_segmente Median | 2.000 | 1.000 | 3.000 | 2.000 |
| Zeichen/Segment Median | 4705.000 | 1339.000 | 4742.500 | 4425.667 |
| Anteil nicht kodierbar | 0.036 | 0.028 | 0.029 | 0.093 |
| Anteil ukraine_bezug | 0.765 | 0.841 | 0.536 | 0.041 |
| Populismus gesamt | 0.988 | 0.369 | 1.161 | 1.068 |
| Volkszentrismus | 0.717 | 0.232 | 0.852 | 0.896 |

### B2. Segmentierung je LLM-Datensatz

| dataset_id | n_videos | n_segmente_median | zeichen_je_segment_median | zeichen_gesamt_median | dauer_median_min | anteil_krieg | anteil_post | populismus_gesamt |
|---|---|---|---|---|---|---|---|---|
| descriptive_sample_baseline_populism_segments | 1763 | 2.000 | 4460.500 | 10259.000 | 11.517 | 0.000 | 0.000 | 1.075 |
| descriptive_sample_war_segments | 7552 | 2.000 | 4486.267 | 9486.500 | 10.467 | 0.803 | 1.000 | 1.166 |
| parse_errors_POPULISMUS_P_segments | 14 | 8.500 | 4815.667 | 42526.500 | 48.950 | 0.929 | 1.000 | 1.130 |
| pilot_classification_segments | 794 | 2.000 | 4445.500 | 7521.000 | 8.525 | 0.000 | 0.603 | 1.143 |
| populism_todo_segments | 1407 | 1.000 | 4580.000 | 6172.000 | 7.100 | 1.000 | 0.999 | 0.748 |
| videos_to_classify_populism1_segments | 4719 | 1.000 | 1458.000 | 1458.000 | 1.867 | 0.342 | 1.000 | 0.268 |
| videos_to_classify_populism2_segments | 5218 | 1.000 | 3536.500 | 3804.500 | 4.417 | 0.594 | 1.000 | 0.338 |
| videos_to_classify_populism3_segments | 5265 | 1.000 | 4187.000 | 5367.000 | 5.900 | 0.653 | 1.000 | 0.515 |
| videos_to_classify_populism4_segments | 4036 | 2.000 | 4238.500 | 7372.000 | 8.450 | 0.708 | 0.922 | 1.063 |
| war_vids_segments | 5024 | 2.000 | 4568.167 | 10504.000 | 11.892 | 0.798 | 0.995 | 1.248 |

## C. Populismus der Nicht-Kriegsvideos je Merkmal, vor vs. nach

### LLM-Datensatz

| dataset_id | post | n | populismus_gesamt | volkszentrismus | antielitismus |
|---|---|---|---|---|---|
| descriptive_sample_baseline_populism_segments | vor | 1763 | 1.075 | 0.915 | 1.256 |
| descriptive_sample_war_segments | nach | 1490 | 0.604 | 0.389 | 0.653 |
| parse_errors_POPULISMUS_P_segments | nach | 1 | 0.000 | 0.000 | 0.000 |
| pilot_classification_segments | vor | 315 | 1.228 | 0.991 | 1.430 |
| pilot_classification_segments | nach | 479 | 1.087 | 0.838 | 1.296 |
| videos_to_classify_populism1_segments | nach | 3104 | 0.138 | 0.066 | 0.067 |
| videos_to_classify_populism2_segments | nach | 2119 | 0.182 | 0.104 | 0.075 |
| videos_to_classify_populism3_segments | nach | 1829 | 0.222 | 0.131 | 0.155 |
| videos_to_classify_populism4_segments | vor | 89 | 0.358 | 0.198 | 0.383 |
| videos_to_classify_populism4_segments | nach | 1090 | 0.603 | 0.335 | 0.645 |
| war_vids_segments | vor | 4 | 0.083 | 0.000 | 0.000 |
| war_vids_segments | nach | 1013 | 0.915 | 0.646 | 0.950 |

### Auswahlweg

| herkunft | post | n | populismus_gesamt | volkszentrismus | antielitismus |
|---|---|---|---|---|---|
| baseline_vor (Intervall 0-3, pf=1) | vor | 1770 | 1.150 | 0.970 | 1.348 |
| kurzclip < 181 s ohne Themenklassifikation | vor | 401 | 0.679 | 0.547 | 0.757 |
| kurzclip < 181 s ohne Themenklassifikation | nach | 10784 | 0.338 | 0.206 | 0.298 |
| screening_nach (Intervall >= 4, pf=1) | nach | 341 | 1.342 | 1.038 | 1.626 |

### politics_final (NaN = nicht im Screening)

| politics_final | post | n | populismus_gesamt | volkszentrismus | antielitismus |
|---|---|---|---|---|---|
| 1.000 | vor | 1770 | 1.150 | 0.970 | 1.348 |
| 1.000 | nach | 341 | 1.342 | 1.038 | 1.626 |
| fehlt | vor | 401 | 0.679 | 0.547 | 0.757 |
| fehlt | nach | 10784 | 0.338 | 0.206 | 0.298 |

### topic_categories enthält Politics

| topic_politics | post | n | populismus_gesamt | volkszentrismus | antielitismus |
|---|---|---|---|---|---|
| False | vor | 1124 | 0.930 | 0.765 | 1.117 |
| False | nach | 965 | 0.640 | 0.387 | 0.683 |
| True | vor | 1047 | 1.205 | 1.027 | 1.373 |
| True | nach | 10160 | 0.351 | 0.221 | 0.315 |

### Keyword-Teiltreffer ohne is_relevant

| kw_teiltreffer | post | n | populismus_gesamt | volkszentrismus | antielitismus |
|---|---|---|---|---|---|
| 0 | vor | 2171 | 1.068 | 0.896 | 1.245 |
| 0 | nach | 11125 | 0.369 | 0.232 | 0.339 |

### Längenband

| dauer_band | post | n | populismus_gesamt | volkszentrismus | antielitismus |
|---|---|---|---|---|---|
| 15-30 min | vor | 360 | 1.095 | 0.908 | 1.315 |
| 15-30 min | nach | 63 | 1.387 | 1.038 | 1.698 |
| 30-60 min | vor | 272 | 1.191 | 0.998 | 1.436 |
| 30-60 min | nach | 61 | 1.170 | 0.956 | 1.400 |
| 5-15 min | vor | 733 | 1.169 | 0.988 | 1.361 |
| 5-15 min | nach | 139 | 1.541 | 1.174 | 1.864 |
| <5 min | vor | 631 | 0.904 | 0.739 | 1.018 |
| <5 min | nach | 10831 | 0.342 | 0.209 | 0.303 |
| >60 min | vor | 175 | 0.945 | 0.850 | 1.074 |
| >60 min | nach | 31 | 0.831 | 0.772 | 0.929 |

### gruppe5

| gruppe5 | post | n | populismus_gesamt | volkszentrismus | antielitismus |
|---|---|---|---|---|---|
| Alternative Medien (links) | vor | 282 | 0.999 | 0.737 | 1.217 |
| Alternative Medien (links) | nach | 194 | 0.821 | 0.429 | 0.942 |
| Alternative Medien (mitte) | vor | 358 | 0.977 | 0.832 | 1.165 |
| Alternative Medien (mitte) | nach | 461 | 1.072 | 0.626 | 1.288 |
| Alternative Medien (rechts) | vor | 580 | 1.575 | 1.265 | 1.834 |
| Alternative Medien (rechts) | nach | 1115 | 1.249 | 0.804 | 1.439 |
| Traditionelles Medium | vor | 424 | 0.452 | 0.479 | 0.482 |
| Traditionelles Medium | nach | 8452 | 0.179 | 0.108 | 0.097 |
| fehlt | vor | 214 | 1.638 | 1.368 | 1.848 |
| fehlt | nach | 319 | 1.532 | 1.074 | 1.814 |
| ÖRR | vor | 313 | 0.644 | 0.605 | 0.782 |
| ÖRR | nach | 584 | 0.351 | 0.244 | 0.296 |

## D. Hypothesenprüfung

### D1. Post-Effekt der Nicht-Kriegsvideos in Teilmengen (Kanal-Monat, Kanal-FE)

| Teilmenge | Dimension | post | p | n_vor | n_nach | Kanäle |
|---|---|---|---|---|---|---|
| Alle Nicht-Kriegsvideos (= Schnellcheck Spez. 3) | populismus_gesamt | -0.252 | 0.000 | 2171 | 9204 | 244 |
| Alle Nicht-Kriegsvideos (= Schnellcheck Spez. 3) | volkszentrismus | -0.374 | 0.000 | 2171 | 9204 | 244 |
| Alle Nicht-Kriegsvideos (= Schnellcheck Spez. 3) | antielitismus | -0.306 | 0.000 | 2171 | 9204 | 244 |
| politics_final == 1 | populismus_gesamt | 0.019 | 0.731 | 1770 | 341 | 197 |
| politics_final == 1 | volkszentrismus | -0.046 | 0.391 | 1770 | 341 | 197 |
| politics_final == 1 | antielitismus | 0.072 | 0.218 | 1770 | 341 | 197 |
| topic_politics | populismus_gesamt | -0.322 | 0.000 | 1047 | 8367 | 225 |
| topic_politics | volkszentrismus | -0.448 | 0.000 | 1047 | 8367 | 225 |
| topic_politics | antielitismus | -0.380 | 0.000 | 1047 | 8367 | 225 |
| politics_final == 1 & topic_politics | populismus_gesamt | -0.061 | 0.375 | 790 | 214 | 163 |
| politics_final == 1 & topic_politics | volkszentrismus | -0.120 | 0.039 | 790 | 214 | 163 |
| politics_final == 1 & topic_politics | antielitismus | -0.006 | 0.944 | 790 | 214 | 163 |
| ohne Keyword-Teiltreffer | populismus_gesamt | -0.252 | 0.000 | 2171 | 9204 | 244 |
| ohne Keyword-Teiltreffer | volkszentrismus | -0.374 | 0.000 | 2171 | 9204 | 244 |
| ohne Keyword-Teiltreffer | antielitismus | -0.306 | 0.000 | 2171 | 9204 | 244 |
| ohne jedes Segment mit ukraine_bezug | populismus_gesamt | -0.208 | 0.000 | 2013 | 1460 | 226 |
| ohne jedes Segment mit ukraine_bezug | volkszentrismus | -0.315 | 0.000 | 2013 | 1460 | 226 |
| ohne jedes Segment mit ukraine_bezug | antielitismus | -0.177 | 0.001 | 2013 | 1460 | 226 |
| pf == 1 & topic_politics & ohne Teiltreffer | populismus_gesamt | -0.061 | 0.375 | 790 | 214 | 163 |
| pf == 1 & topic_politics & ohne Teiltreffer | volkszentrismus | -0.120 | 0.039 | 790 | 214 | 163 |
| pf == 1 & topic_politics & ohne Teiltreffer | antielitismus | -0.006 | 0.944 | 790 | 214 | 163 |
| Dauer >= 15 min | populismus_gesamt | 0.067 | 0.364 | 807 | 155 | 160 |
| Dauer >= 15 min | volkszentrismus | 0.043 | 0.595 | 807 | 155 | 160 |
| Dauer >= 15 min | antielitismus | 0.080 | 0.322 | 807 | 155 | 160 |
| n_segmente >= 3 | populismus_gesamt | 0.042 | 0.542 | 954 | 175 | 170 |
| n_segmente >= 3 | volkszentrismus | 0.007 | 0.912 | 954 | 175 | 170 |
| n_segmente >= 3 | antielitismus | 0.063 | 0.424 | 954 | 175 | 170 |
| nur Screening-Videos (in_screening) | populismus_gesamt | 0.019 | 0.731 | 1770 | 341 | 197 |
| nur Screening-Videos (in_screening) | volkszentrismus | -0.046 | 0.391 | 1770 | 341 | 197 |
| nur Screening-Videos (in_screening) | antielitismus | 0.072 | 0.218 | 1770 | 341 | 197 |

### D2. Alternative Aggregation Segment → Video (Hypothese d)

| Aggregation Segment→Video | Dimension | post | p |
|---|---|---|---|
| Mittelwert über Segmente (Standard) | populismus_gesamt | -0.252 | 0.000 |
| Mittelwert über Segmente (Standard) | volkszentrismus | -0.374 | 0.000 |
| nur erstes Segment | populismus_gesamt | -0.198 | 0.000 |
| nur erstes Segment | volkszentrismus | -0.347 | 0.000 |
| Maximum über Segmente | populismus_gesamt | -0.424 | 0.000 |
| Maximum über Segmente | volkszentrismus | -0.547 | 0.000 |

### D3. Videos, die in mehreren Runs klassifiziert wurden (Hypothese c)

| n_videos | Run-Paare | n_seg früh (Median) | n_seg spät (Median) | Populismus früh | Populismus spät | Korrelation |
|---|---|---|---|---|---|---|
| 55 | descriptive_sample_baseline_populism_segments → videos_to_classify_populism4_segments, descriptive_sample_war_segments → parse_errors_POPULISMUS_P_segments, war_vids_segments → parse_errors_POPULISMUS_P_segments | 3.000 | 3.000 | 1.275 | 1.292 | 0.977 |

### D4. Urteile zu den Hypothesen

*Die Urteile sind von Hand formuliert (Stand 2026-09-28). Die ausführliche Fassung steht in `outputs/segment_analysis/frage1_methodik_und_stichprobe.md`, Abschnitt 4a.*

- **(a) Anderer Auswahlweg bzw. abweichende Kriegsvideo-Definition: TRIFFT ZU (Hauptursache).** 10.784 der 11.125 Nachher-Nichtkriegsvideos haben keine Zeile in `video_topic_relevance`. Sie sind zu 97 % kürzer als 181 s, und die Themenklassifikation (`get_videos_with_text()`) lässt sie deshalb aus. Sie gelten per Default als Nicht-Kriegsvideo. Zu 96 % stammen sie aus der alten Liste `archive/sample_feasibility/war_vids.csv` (Batches `videos_to_classify_populism1-4`); dort sind 79 % Kern-Kriegsvideos.
- **(b) Wenig politisch: TEILWEISE.** Nur 3 % haben `politics_final == 1`, weil sie gar nicht im Screening sind. `topic_politics` trifft auf 91 % zu. Das Problem ist also nicht fehlende Politik, sondern Kürze und falsche Themenzuordnung. Mit `politics_final == 1` verschwindet der Effekt (+0,02 n. s.).
- **(c) Prompt oder Segmentierung: TRIFFT NICHT ZU.** Alle Runs nutzen dieselbe Prompt-Version v4, dasselbe Modell und dieselbe Temperatur. Mehrfach klassifizierte Videos korrelieren über die Runs mit r = 0,98. Die kleinen Segmentzahlen der Batches 1–3 folgen aus der Videolänge.
- **(d) Aggregation Segment → Video: TRIFFT NICHT ZU.** Der Effekt bleibt bei jeder Aggregationsregel bestehen (D2), verschwindet aber bei Dauer ≥ 15 min oder ≥ 3 Segmenten (D1).
- **(e) Realer Rückgang: NICHT GESTÜTZT.** In allen Teilmengen mit vergleichbarem Auswahlweg ist der Post-Effekt der Nicht-Kriegsvideos nahe null und nicht signifikant. Einzige Ausnahme: Volkszentrismus in der strengen Teilmenge, −0,12, p = 0,04. Allerdings hat dieser Vergleich wenig Power: 341 Nachher-Videos, 197 Kanäle.

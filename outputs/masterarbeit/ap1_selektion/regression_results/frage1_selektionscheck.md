# AP 1 – Selektionscheck Frage 1: Robustheitstabelle

*Erzeugt von `scripts/masterarbeit/ap1_selektionscheck.py`; Diagnose in `frage1_selektionsdiagnose.md` (gleicher Ordner).*

## Methodik-Übersicht

- **Vergleich:** Nachkriegseffekt `post` (`rel_monat >= 0`, Fenster -12…42) innerhalb eines Kanals (Kanal-FE), SE geclustert nach Kanal. Die Beobachtungseinheit ist der Kanal-Monat (Mittel über Videos) wie in `frage1_populismus_bericht.py`.
- **Spezifikationen:** (1) alle Videos je Kanal-Monat; (2) Zellen Kanal × Monat × `ist_kriegsvideo` mit Kriegsvideo-Dummy als Kontrolle; (3) nur Nicht-Kriegsvideos.
- **Populationen:**
  - **P0 original:** alle Videos der 279er-Whitelist in `channel_video_populism.csv`.
  - **P1 bereinigt:** Dauer ≥ 181 s (`MIN_VIDEO_DURATION_SECONDS`) **und** (Kriegsvideo **oder** `politics_final == 1`). Nicht-Kriegsvideos stammen damit vorher und nachher aus demselben Auswahlweg (Screening mit LLM-Politikfilter). Kriegsvideos stammen vorher und nachher aus der Keyword-Klassifikation, die ebenfalls erst ab 181 s greift.
  - **P2 streng:** P1, Nicht-Kriegsvideos zusätzlich mit YouTube-`topic_categories` = Politics.
- **Stance:** `channel_video_position.csv`, inner join auf die Videos der Diagnose (34,873 Videos mit Stance-Klassifikation). Nicht thematisierte Positionen sind NaN und fallen je Dimension heraus.
- Signifikanz: * p<0,05, ** p<0,01, *** p<0,001; in Klammern der Cluster-SE.

## Fallzahlen

| Population | Videos | Krieg vor | Krieg nach | Nichtkrieg vor | Nichtkrieg nach | Kanäle | Kanäle ≥5 Videos | Kanäle mit Nichtkrieg vor UND nach |
|---|---|---|---|---|---|---|---|---|
| P0 original | 28936 | 248 | 17313 | 2171 | 9204 | 277 | 273 | 142 |
| P1 bereinigt | 19672 | 248 | 17313 | 1770 | 341 | 277 | 270 | 43 |
| P2 streng | 18565 | 248 | 17313 | 790 | 214 | 277 | 267 | 35 |

## Populismus

| Population | Dimension | (1) alle | (2) + Kriegskontrolle | (3) nur Nichtkrieg | Kanäle (3) |
|---|---|---|---|---|---|
| P0 original | populismus_gesamt | +0.006 (0.024) | -0.199*** (0.028) | -0.252*** (0.033) | 244 |
| P0 original | antielitismus | +0.003 (0.030) | -0.247*** (0.036) | -0.306*** (0.043) | 244 |
| P0 original | volkszentrismus | -0.098*** (0.023) | -0.298*** (0.027) | -0.374*** (0.033) | 244 |
| P0 original | manichaeische_moralisierung | +0.113*** (0.027) | -0.053 (0.033) | -0.076* (0.038) | 244 |
| P0 original | emotionale_intensitaet | +0.114*** (0.024) | -0.029 (0.032) | -0.011 (0.037) | 244 |
| P1 bereinigt | populismus_gesamt | +0.041 (0.026) | +0.068* (0.032) | +0.019 (0.055) | 197 |
| P1 bereinigt | antielitismus | +0.051 (0.031) | +0.100** (0.034) | +0.072 (0.059) | 197 |
| P1 bereinigt | volkszentrismus | -0.067** (0.024) | +0.012 (0.036) | -0.046 (0.054) | 197 |
| P1 bereinigt | manichaeische_moralisierung | +0.139*** (0.030) | +0.092* (0.041) | +0.031 (0.071) | 197 |
| P1 bereinigt | emotionale_intensitaet | +0.136*** (0.025) | +0.095** (0.034) | +0.088 (0.058) | 197 |
| P2 streng | populismus_gesamt | -0.050 (0.034) | +0.037 (0.037) | -0.061 (0.069) | 163 |
| P2 streng | antielitismus | -0.047 (0.040) | +0.056 (0.040) | -0.006 (0.085) | 163 |
| P2 streng | volkszentrismus | -0.140*** (0.032) | -0.014 (0.040) | -0.120* (0.058) | 163 |
| P2 streng | manichaeische_moralisierung | +0.037 (0.039) | +0.069 (0.047) | -0.058 (0.090) | 163 |
| P2 streng | emotionale_intensitaet | +0.066* (0.032) | +0.062 (0.035) | +0.030 (0.076) | 163 |

## Stance (Position)

Skala −2…+2 gemäß `POSITION_V1` (`segment_prompts_simple.py`). `position_russland`: +2 heißt russisches Handeln wird gerechtfertigt. `position_westpolitik`: +2 heißt deutliche Unterstützung der westlichen Politik, −2 heißt grundsätzliche Ablehnung.

| Population | Dimension | (1) alle | (2) + Kriegskontrolle | (3) nur Nichtkrieg | Kanäle (3) |
|---|---|---|---|---|---|
| P0 original | position_russland | -0.231*** (0.052) | -0.254*** (0.052) | -0.257** (0.084) | 208 |
| P0 original | position_westpolitik | +0.088* (0.044) | +0.150** (0.049) | +0.193** (0.068) | 207 |
| P1 bereinigt | position_russland | -0.234*** (0.054) | -0.244*** (0.064) | -0.274 (0.164) | 134 |
| P1 bereinigt | position_westpolitik | +0.070 (0.045) | -0.023 (0.048) | +0.040 (0.088) | 134 |
| P2 streng | position_russland | -0.251*** (0.066) | -0.254*** (0.073) | -0.309 (0.297) | 85 |
| P2 streng | position_westpolitik | +0.051 (0.056) | -0.033 (0.055) | +0.114 (0.115) | 97 |

## Kriegsvideos (nur P1 bereinigt)

Vor Kriegsbeginn gibt es kaum Kriegsvideos (249 in P1). Ein direkter Vergleich „Kriegsvideos vorher vs. nachher“ ist deshalb nicht möglich. Vergleich B (Krieg vs. Nichtkrieg im selben Kanal-Monat nach Kriegsbeginn) ist zurückgestellt: Dafür fehlen klassifizierte politische Nicht-Kriegsvideos nach Kriegsbeginn.

### A. Kriegsvideos nach Kriegsbeginn vs. politische Videos desselben Kanals vorher

Stichprobe: vorher nur politische Nicht-Kriegsvideos, nachher nur Kriegsvideos. Kanal-Monat, Kanal-FE, Koeffizient `post`, je Gruppe getrennt geschätzt. Die Schätzung trennt nicht zwischen einem Effekt des Kriegs und einem Effekt des Themas: Sie misst, wie sich der Kanal verändert, wenn er über den Krieg spricht, verglichen mit seinem politischen Programm vorher.

Zellformat: `Koeffizient Sterne (Cluster-SE) [identifizierende Kanäle / alle Kanäle]`. Identifizierend sind wegen der Kanal-FE nur Kanäle mit Kanal-Monaten vorher **und** nachher; Kanäle mit nur einer Seite gehen ins Modell ein, tragen aber nichts zum `post`-Koeffizienten bei.

| Dimension | gesamt | ÖRR | Traditionelles Medium | Alternative Medien (links) | Alternative Medien (mitte) | Alternative Medien (rechts) |
|---|---|---|---|---|---|---|
| populismus_gesamt | +0.034 (0.027) [197/277] | -0.031 (0.039) [33/44] | -0.020 (0.057) [30/38] | -0.028 (0.059) [27/34] | -0.042 (0.054) [34/44] | +0.157* (0.062) [57/99] |
| antielitismus | +0.039 (0.034) [197/277] | -0.095 (0.053) [33/44] | -0.056 (0.080) [30/38] | -0.030 (0.070) [27/34] | -0.055 (0.078) [34/44] | +0.231** (0.074) [57/99] |
| volkszentrismus | -0.081** (0.026) [197/277] | -0.106* (0.046) [33/44] | -0.212*** (0.054) [30/38] | -0.111 (0.062) [27/34] | -0.110* (0.050) [34/44] | -0.009 (0.051) [57/99] |
| manichaeische_moralisierung | +0.144*** (0.031) [197/277] | +0.108** (0.042) [33/44] | +0.207*** (0.061) [30/38] | +0.056 (0.070) [27/34] | +0.039 (0.052) [34/44] | +0.249*** (0.073) [57/99] |
| emotionale_intensitaet | +0.143*** (0.027) [197/277] | +0.152** (0.052) [33/44] | +0.183*** (0.040) [30/38] | +0.036 (0.068) [27/34] | +0.018 (0.050) [34/44] | +0.239*** (0.058) [57/99] |

| Dimension | gesamt | ÖRR | Traditionelles Medium | Alternative Medien (links) | Alternative Medien (mitte) | Alternative Medien (rechts) |
|---|---|---|---|---|---|---|
| position_russland | -0.216*** (0.065) [127/276] | -0.774*** (0.142) [15/44] | -0.414** (0.149) [20/38] | -0.161 (0.168) [17/34] | -0.181 (0.138) [25/44] | -0.022 (0.097) [43/99] |
| position_westpolitik | +0.098* (0.049) [129/275] | +0.311* (0.137) [14/44] | +0.162 (0.268) [14/37] | +0.224 (0.131) [18/33] | +0.323* (0.142) [25/44] | -0.100 (0.051) [46/99] |

### C. Entwicklung der Kriegsvideos nach Kriegsbeginn (Kriegsjahr 1–4)

Nur Kriegsvideos, `rel_monat` 0…42. Jahr 1 = Monate 0–11, Jahr 4 = Monate 36–42. Mittelwerte über Kanal-Monate. Δ aus einem Modell Kanal-FE + Jahr-Dummies mit Referenz Jahr 1 und Cluster-SE. Das Δ misst also die Veränderung innerhalb desselben Kanals.

#### C1. Alle Kanäle (unbalanciert)

Die Mittel J1–J4 enthalten auch Verschiebungen in der Kanalzusammensetzung (welche Kanäle in welchem Jahr über den Krieg berichten); für die Veränderung innerhalb der Kanäle zählt das Δ. „Kanäle“ zählt auch Kanäle, die nur in einem Jahr vorkommen und nichts zum Δ beitragen.

| Dimension | Gruppe | Kanäle | Mittel J1 | Mittel J2 | Mittel J3 | Mittel J4 | Δ J2 vs J1 | Δ J3 vs J1 | Δ J4 vs J1 |
|---|---|---|---|---|---|---|---|---|---|
| populismus_gesamt | gesamt | 277 | 1.121 | 1.173 | 1.255 | 1.269 | +0.018 | +0.057* | +0.036 |
| populismus_gesamt | ÖRR | 44 | 0.678 | 0.712 | 0.714 | 0.533 | +0.003 | -0.001 | -0.173** |
| populismus_gesamt | Traditionelles Medium | 38 | 0.530 | 0.489 | 0.605 | 0.555 | -0.049 | +0.020 | -0.065 |
| populismus_gesamt | Alternative Medien (links) | 34 | 1.026 | 1.192 | 1.148 | 1.226 | +0.032 | +0.007 | +0.003 |
| populismus_gesamt | Alternative Medien (mitte) | 44 | 0.954 | 1.083 | 1.181 | 1.175 | -0.050 | +0.035 | +0.013 |
| populismus_gesamt | Alternative Medien (rechts) | 99 | 1.615 | 1.674 | 1.736 | 1.764 | +0.062 | +0.109* | +0.143* |
| antielitismus | gesamt | 277 | 1.299 | 1.373 | 1.474 | 1.495 | +0.032 | +0.085** | +0.069* |
| antielitismus | ÖRR | 44 | 0.718 | 0.798 | 0.835 | 0.627 | +0.043 | +0.082 | -0.106 |
| antielitismus | Traditionelles Medium | 38 | 0.513 | 0.456 | 0.651 | 0.629 | -0.048 | +0.094 | +0.034 |
| antielitismus | Alternative Medien (links) | 34 | 1.254 | 1.418 | 1.412 | 1.549 | -0.018 | -0.001 | +0.021 |
| antielitismus | Alternative Medien (mitte) | 44 | 1.141 | 1.329 | 1.432 | 1.387 | -0.036 | +0.052 | -0.007 |
| antielitismus | Alternative Medien (rechts) | 99 | 1.910 | 2.021 | 2.049 | 2.081 | +0.104 | +0.122* | +0.175* |
| volkszentrismus | gesamt | 277 | 0.879 | 0.866 | 0.935 | 0.941 | -0.023 | +0.009 | -0.030 |
| volkszentrismus | ÖRR | 44 | 0.543 | 0.547 | 0.574 | 0.430 | -0.003 | +0.002 | -0.162** |
| volkszentrismus | Traditionelles Medium | 38 | 0.467 | 0.397 | 0.485 | 0.416 | -0.082 | -0.037 | -0.140** |
| volkszentrismus | Alternative Medien (links) | 34 | 0.723 | 0.841 | 0.691 | 0.723 | +0.063 | -0.052 | -0.051 |
| volkszentrismus | Alternative Medien (mitte) | 44 | 0.747 | 0.775 | 0.884 | 0.889 | -0.072 | +0.008 | -0.004 |
| volkszentrismus | Alternative Medien (rechts) | 99 | 1.248 | 1.206 | 1.280 | 1.308 | -0.026 | +0.026 | +0.019 |
| manichaeische_moralisierung | gesamt | 277 | 1.185 | 1.280 | 1.357 | 1.371 | +0.045 | +0.077** | +0.067 |
| manichaeische_moralisierung | ÖRR | 44 | 0.774 | 0.791 | 0.734 | 0.543 | -0.032 | -0.087 | -0.249*** |
| manichaeische_moralisierung | Traditionelles Medium | 38 | 0.608 | 0.614 | 0.680 | 0.619 | -0.018 | +0.005 | -0.088 |
| manichaeische_moralisierung | Alternative Medien (links) | 34 | 1.100 | 1.318 | 1.340 | 1.405 | +0.049 | +0.075 | +0.040 |
| manichaeische_moralisierung | Alternative Medien (mitte) | 44 | 0.975 | 1.146 | 1.229 | 1.248 | -0.042 | +0.044 | +0.050 |
| manichaeische_moralisierung | Alternative Medien (rechts) | 99 | 1.686 | 1.793 | 1.878 | 1.904 | +0.109 | +0.179** | +0.233** |
| emotionale_intensitaet | gesamt | 277 | 1.675 | 1.714 | 1.783 | 1.813 | +0.005 | +0.038 | +0.047 |
| emotionale_intensitaet | ÖRR | 44 | 1.463 | 1.488 | 1.462 | 1.383 | +0.005 | -0.023 | -0.080 |
| emotionale_intensitaet | Traditionelles Medium | 38 | 1.236 | 1.192 | 1.282 | 1.211 | -0.043 | +0.019 | -0.083 |
| emotionale_intensitaet | Alternative Medien (links) | 34 | 1.582 | 1.682 | 1.726 | 1.806 | +0.005 | +0.025 | +0.027 |
| emotionale_intensitaet | Alternative Medien (mitte) | 44 | 1.421 | 1.509 | 1.584 | 1.590 | -0.061 | +0.022 | +0.013 |
| emotionale_intensitaet | Alternative Medien (rechts) | 99 | 2.076 | 2.136 | 2.182 | 2.226 | +0.045 | +0.077 | +0.149** |

| Dimension | Gruppe | Kanäle | Mittel J1 | Mittel J2 | Mittel J3 | Mittel J4 | Δ J2 vs J1 | Δ J3 vs J1 | Δ J4 vs J1 |
|---|---|---|---|---|---|---|---|---|---|
| position_russland | gesamt | 276 | -0.509 | -0.435 | -0.405 | -0.327 | +0.057* | +0.069* | +0.117*** |
| position_russland | ÖRR | 44 | -0.992 | -0.899 | -0.960 | -0.983 | +0.128 | +0.110 | +0.069 |
| position_russland | Traditionelles Medium | 38 | -0.995 | -0.908 | -0.902 | -0.824 | +0.089 | +0.060 | +0.088 |
| position_russland | Alternative Medien (links) | 34 | -0.642 | -0.429 | -0.602 | -0.643 | +0.105 | +0.082 | +0.049 |
| position_russland | Alternative Medien (mitte) | 44 | -0.310 | -0.237 | -0.144 | -0.129 | -0.035 | +0.040 | +0.067 |
| position_russland | Alternative Medien (rechts) | 99 | -0.114 | -0.065 | -0.028 | 0.061 | +0.032 | +0.072 | +0.193** |
| position_westpolitik | gesamt | 275 | -0.912 | -1.002 | -1.098 | -1.160 | -0.092** | -0.125*** | -0.174*** |
| position_westpolitik | ÖRR | 44 | -0.274 | -0.357 | -0.528 | -0.490 | -0.100 | -0.268*** | -0.266** |
| position_westpolitik | Traditionelles Medium | 37 | -0.072 | -0.184 | -0.310 | -0.387 | -0.148 | -0.214* | -0.278* |
| position_westpolitik | Alternative Medien (links) | 33 | -0.939 | -1.183 | -1.080 | -1.156 | -0.090 | -0.016 | -0.068 |
| position_westpolitik | Alternative Medien (mitte) | 44 | -0.960 | -1.124 | -1.134 | -1.171 | -0.013 | -0.013 | -0.043 |
| position_westpolitik | Alternative Medien (rechts) | 99 | -1.462 | -1.570 | -1.593 | -1.608 | -0.101* | -0.127** | -0.172*** |

#### C2. Balanciertes Panel (nur Kanäle mit Kriegsvideos in allen vier Jahren)

Gleiche Rechnung, aber nur Kanäle, die in jedem Kriegsjahr mindestens einen Kanal-Monat mit Wert in der jeweiligen Dimension haben. Die Mittel J1–J4 sind damit frei von Zusammensetzungseffekten auf Kanalebene (Gewichtung weiterhin je Kanal-Monat).

| Dimension | Gruppe | Kanäle | Mittel J1 | Mittel J2 | Mittel J3 | Mittel J4 | Δ J2 vs J1 | Δ J3 vs J1 | Δ J4 vs J1 |
|---|---|---|---|---|---|---|---|---|---|
| populismus_gesamt | gesamt | 142 | 1.170 | 1.208 | 1.236 | 1.222 | +0.039 | +0.066* | +0.033 |
| populismus_gesamt | ÖRR | 24 | 0.686 | 0.702 | 0.720 | 0.540 | +0.050 | +0.039 | -0.146** |
| populismus_gesamt | Traditionelles Medium | 25 | 0.569 | 0.502 | 0.611 | 0.562 | -0.057 | +0.007 | -0.077 |
| populismus_gesamt | Alternative Medien (links) | 13 | 1.204 | 1.460 | 1.323 | 1.217 | +0.083 | +0.047 | -0.032 |
| populismus_gesamt | Alternative Medien (mitte) | 24 | 1.089 | 1.141 | 1.177 | 1.158 | -0.032 | +0.031 | +0.015 |
| populismus_gesamt | Alternative Medien (rechts) | 44 | 1.617 | 1.696 | 1.719 | 1.760 | +0.080 | +0.109* | +0.142* |
| antielitismus | gesamt | 142 | 1.364 | 1.412 | 1.461 | 1.450 | +0.053 | +0.093** | +0.060 |
| antielitismus | ÖRR | 24 | 0.713 | 0.760 | 0.837 | 0.634 | +0.102 | +0.139* | -0.074 |
| antielitismus | Traditionelles Medium | 25 | 0.552 | 0.464 | 0.670 | 0.647 | -0.068 | +0.074 | +0.012 |
| antielitismus | Alternative Medien (links) | 13 | 1.558 | 1.769 | 1.651 | 1.577 | -0.001 | +0.000 | -0.036 |
| antielitismus | Alternative Medien (mitte) | 24 | 1.321 | 1.404 | 1.438 | 1.385 | -0.018 | +0.039 | -0.009 |
| antielitismus | Alternative Medien (rechts) | 44 | 1.925 | 2.056 | 2.048 | 2.082 | +0.124* | +0.125* | +0.159* |
| volkszentrismus | gesamt | 142 | 0.905 | 0.889 | 0.913 | 0.895 | -0.004 | +0.016 | -0.026 |
| volkszentrismus | ÖRR | 24 | 0.564 | 0.538 | 0.570 | 0.422 | +0.016 | +0.016 | -0.140* |
| volkszentrismus | Traditionelles Medium | 25 | 0.486 | 0.404 | 0.464 | 0.410 | -0.083 | -0.052 | -0.146*** |
| volkszentrismus | Alternative Medien (links) | 13 | 0.762 | 0.991 | 0.801 | 0.718 | +0.159* | +0.018 | -0.048 |
| volkszentrismus | Alternative Medien (mitte) | 24 | 0.820 | 0.804 | 0.860 | 0.833 | -0.058 | +0.011 | -0.014 |
| volkszentrismus | Alternative Medien (rechts) | 44 | 1.243 | 1.229 | 1.254 | 1.302 | -0.007 | +0.014 | +0.038 |
| manichaeische_moralisierung | gesamt | 142 | 1.240 | 1.321 | 1.334 | 1.322 | +0.067* | +0.090** | +0.064 |
| manichaeische_moralisierung | ÖRR | 24 | 0.782 | 0.809 | 0.753 | 0.562 | +0.031 | -0.038 | -0.224*** |
| manichaeische_moralisierung | Traditionelles Medium | 25 | 0.670 | 0.637 | 0.700 | 0.628 | -0.019 | -0.002 | -0.096 |
| manichaeische_moralisierung | Alternative Medien (links) | 13 | 1.291 | 1.621 | 1.518 | 1.356 | +0.090 | +0.122 | -0.013 |
| manichaeische_moralisierung | Alternative Medien (mitte) | 24 | 1.125 | 1.214 | 1.233 | 1.254 | -0.019 | +0.044 | +0.067 |
| manichaeische_moralisierung | Alternative Medien (rechts) | 44 | 1.683 | 1.803 | 1.854 | 1.897 | +0.122* | +0.190** | +0.230** |
| emotionale_intensitaet | gesamt | 142 | 1.709 | 1.734 | 1.760 | 1.760 | +0.015 | +0.052* | +0.043 |
| emotionale_intensitaet | ÖRR | 24 | 1.445 | 1.482 | 1.474 | 1.400 | +0.051 | +0.022 | -0.045 |
| emotionale_intensitaet | Traditionelles Medium | 25 | 1.259 | 1.225 | 1.303 | 1.204 | -0.025 | +0.024 | -0.080 |
| emotionale_intensitaet | Alternative Medien (links) | 13 | 1.687 | 1.857 | 1.814 | 1.725 | +0.001 | +0.060 | -0.035 |
| emotionale_intensitaet | Alternative Medien (mitte) | 24 | 1.509 | 1.535 | 1.590 | 1.568 | -0.062 | +0.025 | +0.012 |
| emotionale_intensitaet | Alternative Medien (rechts) | 44 | 2.087 | 2.135 | 2.157 | 2.223 | +0.042 | +0.082 | +0.151* |

| Dimension | Gruppe | Kanäle | Mittel J1 | Mittel J2 | Mittel J3 | Mittel J4 | Δ J2 vs J1 | Δ J3 vs J1 | Δ J4 vs J1 |
|---|---|---|---|---|---|---|---|---|---|
| position_russland | gesamt | 131 | -0.479 | -0.439 | -0.406 | -0.342 | +0.051 | +0.061 | +0.113** |
| position_russland | ÖRR | 21 | -1.034 | -0.941 | -0.990 | -0.946 | +0.110 | +0.106 | +0.106 |
| position_russland | Traditionelles Medium | 24 | -1.031 | -0.935 | -0.898 | -0.834 | +0.112 | +0.097 | +0.117 |
| position_russland | Alternative Medien (links) | 12 | -0.494 | -0.354 | -0.395 | -0.417 | +0.074 | +0.092 | +0.070 |
| position_russland | Alternative Medien (mitte) | 22 | -0.198 | -0.197 | -0.123 | -0.132 | -0.027 | +0.012 | +0.044 |
| position_russland | Alternative Medien (rechts) | 42 | -0.064 | -0.057 | -0.002 | 0.121 | +0.008 | +0.038 | +0.167* |
| position_westpolitik | gesamt | 127 | -0.948 | -1.006 | -1.078 | -1.125 | -0.096** | -0.136*** | -0.183*** |
| position_westpolitik | ÖRR | 19 | -0.276 | -0.318 | -0.533 | -0.584 | -0.131 | -0.320*** | -0.341*** |
| position_westpolitik | Traditionelles Medium | 22 | -0.037 | -0.147 | -0.331 | -0.382 | -0.139 | -0.250** | -0.294* |
| position_westpolitik | Alternative Medien (links) | 10 | -1.294 | -1.466 | -1.236 | -1.317 | -0.131 | +0.022 | -0.052 |
| position_westpolitik | Alternative Medien (mitte) | 22 | -1.046 | -1.145 | -1.153 | -1.148 | -0.023 | +0.006 | -0.027 |
| position_westpolitik | Alternative Medien (rechts) | 42 | -1.473 | -1.558 | -1.604 | -1.627 | -0.078 | -0.128** | -0.158*** |

# Kriegsanteil (t-1) und Kanalerfolg (t)

Erzeugt von `scripts/adhoc/kriegsanteil_lag_erfolg.py` (Details im Docstring). Kanal-Monats-Panel, nur Long-Videos, 01/2021–06/2026. WLS mit Kanal- und Monats-FE, Gewicht sqrt(n Videos), SE geclustert nach Kanal. Kriegsanteil fehlt bei < 3 Videos im Nenner, Outcome bei < 3 Videos.

**Variablen:** `anteil` = Kriegsanteil im Monat t (Hauptspezifikation: Kriegsvideos cw / Videos mit irgendeinem rel_*_cw-Treffer), `_l1..3` = Lags, `_f1` = Lead (Placebo). `y_alle` = Median log(1+Views) aller Long-Videos in t, `y_nk` = dto. nur Nicht-Kriegsvideos. Koeffizient × 0,1 ≈ Veränderung der Median-Views (log) bei +10 Prozentpunkten Kriegsanteil.

Signifikanz: * p<0,1, ** p<0,05, *** p<0,01; Standardfehler in Klammern.

## Deskriptiv (Hauptspezifikation)

- Zellen mit Kriegsanteil: 8.725 aus 343 Kanälen
- Mittlerer Kriegsanteil vor Kriegsbeginn: 0.035, ab 02/2022: 0.152 (Median 0.030)
- SD Kriegsanteil gesamt: 0.210, innerhalb der Kanäle: 0.157
- Zellen mit Outcome alle/Nicht-Krieg: 19.338 / 19.180
- Autokorrelation Anteil(t) vs. Anteil(t-1): 0.711

| Jahr | Mittel | Median | Zellen |
|---|---|---|---|
| 2021 | 0.031 | 0.0 | 1144 |
| 2022 | 0.263 | 0.167 | 1395 |
| 2023 | 0.17 | 0.032 | 1414 |
| 2024 | 0.118 | 0.0 | 1832 |
| 2025 | 0.116 | 0.017 | 2010 |
| 2026 | 0.093 | 0.0 | 930 |

## Haupt (cw, Nenner Themen, Dichte Periode)

| Modell | Outcome | anteil_l1 | anteil | anteil_l2 | anteil_l3 | anteil_f1 | y_nk_l1 | N Zellen | N Kanäle |
|---|---|---|---|---|---|---|---|---|---|
| M1 | y_alle | 0.321*** (0.095) |  |  |  |  |  | 8.334 | 309 |
| M2 | y_alle | 0.307*** (0.082) | 0.206** (0.094) |  |  |  |  | 6.989 | 263 |
| M3 | y_nk | 0.140* (0.084) |  |  |  |  |  | 8.263 | 308 |
| M3b | y_nk | 0.199** (0.084) | -0.065 (0.099) |  |  |  |  | 6.936 | 263 |
| M4 | y_nk | 0.094* (0.050) |  |  |  |  | 0.700*** (0.028) | 8.216 | 308 |
| M5 | y_nk | 0.086 (0.091) |  | -0.025 (0.081) | 0.142 (0.087) |  |  | 5.881 | 222 |
| M6 | y_nk | 0.184** (0.083) |  |  |  | -0.007 (0.109) |  | 6.614 | 256 |

M5 Summe der Lags t-1..t-3: 0.203 (SE 0.170, p = 0.232)

M3: +10 pp Kriegsanteil in t-1 ⇒ Median-Views der Nicht-Kriegsvideos in t +1.4 %.

## Upload-Dichte Fenster ±48 h

| Modell | Outcome | anteil_l1 | anteil | anteil_l2 | anteil_l3 | anteil_f1 | y_nk_l1 | N Zellen | N Kanäle |
|---|---|---|---|---|---|---|---|---|---|
| M1 | y_alle | 0.317*** (0.093) |  |  |  |  |  | 8.334 | 309 |
| M2 | y_alle | 0.306*** (0.082) | 0.198** (0.093) |  |  |  |  | 6.989 | 263 |
| M3 | y_nk | 0.139* (0.083) |  |  |  |  |  | 8.263 | 308 |
| M3b | y_nk | 0.200** (0.082) | -0.068 (0.098) |  |  |  |  | 6.936 | 263 |
| M4 | y_nk | 0.094* (0.049) |  |  |  |  | 0.696*** (0.030) | 8.216 | 308 |
| M5 | y_nk | 0.081 (0.088) |  | -0.022 (0.079) | 0.141* (0.086) |  |  | 5.881 | 222 |
| M6 | y_nk | 0.182** (0.082) |  |  |  | -0.010 (0.107) |  | 6.614 | 256 |

M5 Summe der Lags t-1..t-3: 0.200 (SE 0.168, p = 0.235)

M3: +10 pp Kriegsanteil in t-1 ⇒ Median-Views der Nicht-Kriegsvideos in t +1.4 %.

## core (Zähler und Nenner)

| Modell | Outcome | anteil_l1 | anteil | anteil_l2 | anteil_l3 | anteil_f1 | y_nk_l1 | N Zellen | N Kanäle |
|---|---|---|---|---|---|---|---|---|---|
| M1 | y_alle | 0.274** (0.119) |  |  |  |  |  | 6.489 | 265 |
| M2 | y_alle | 0.236** (0.111) | 0.090 (0.119) |  |  |  |  | 5.206 | 212 |
| M3 | y_nk | 0.186* (0.112) |  |  |  |  |  | 6.473 | 265 |
| M3b | y_nk | 0.205* (0.114) | -0.090 (0.113) |  |  |  |  | 5.196 | 212 |
| M4 | y_nk | 0.117** (0.050) |  |  |  |  | 0.709*** (0.032) | 6.458 | 265 |
| M5 | y_nk | 0.084 (0.122) |  | -0.041 (0.107) | 0.066 (0.105) |  |  | 4.367 | 185 |
| M6 | y_nk | 0.218** (0.107) |  |  |  | -0.031 (0.138) |  | 4.977 | 203 |

M5 Summe der Lags t-1..t-3: 0.109 (SE 0.230, p = 0.636)

M3: +10 pp Kriegsanteil in t-1 ⇒ Median-Views der Nicht-Kriegsvideos in t +1.9 %.

## Nenner alle Long-Videos

| Modell | Outcome | anteil_l1 | anteil | anteil_l2 | anteil_l3 | anteil_f1 | y_nk_l1 | N Zellen | N Kanäle |
|---|---|---|---|---|---|---|---|---|---|
| M1 | y_alle | 0.848*** (0.173) |  |  |  |  |  | 17.766 | 400 |
| M2 | y_alle | 0.506*** (0.113) | 0.705*** (0.159) |  |  |  |  | 17.766 | 400 |
| M3 | y_nk | 0.544*** (0.190) |  |  |  |  |  | 17.642 | 400 |
| M3b | y_nk | 0.423*** (0.139) | 0.273 (0.180) |  |  |  |  | 17.642 | 400 |
| M4 | y_nk | 0.282*** (0.093) |  |  |  |  | 0.662*** (0.023) | 17.550 | 400 |
| M5 | y_nk | 0.559*** (0.183) |  | -0.091 (0.129) | 0.155 (0.143) |  |  | 15.668 | 382 |
| M6 | y_nk | 0.413*** (0.153) |  |  |  | 0.403** (0.198) |  | 16.554 | 388 |

M5 Summe der Lags t-1..t-3: 0.624 (SE 0.267, p = 0.020)

M3: +10 pp Kriegsanteil in t-1 ⇒ Median-Views der Nicht-Kriegsvideos in t +5.6 %.

## ohne format_derived (WELT)

| Modell | Outcome | anteil_l1 | anteil | anteil_l2 | anteil_l3 | anteil_f1 | y_nk_l1 | N Zellen | N Kanäle |
|---|---|---|---|---|---|---|---|---|---|
| M1 | y_alle | 0.275*** (0.090) |  |  |  |  |  | 8.281 | 309 |
| M2 | y_alle | 0.275*** (0.081) | 0.168* (0.092) |  |  |  |  | 6.936 | 263 |
| M3 | y_nk | 0.134 (0.087) |  |  |  |  |  | 8.211 | 308 |
| M3b | y_nk | 0.191** (0.086) | -0.064 (0.103) |  |  |  |  | 6.884 | 263 |
| M4 | y_nk | 0.093* (0.052) |  |  |  |  | 0.700*** (0.028) | 8.165 | 308 |
| M5 | y_nk | 0.087 (0.095) |  | -0.026 (0.085) | 0.146 (0.090) |  |  | 5.829 | 222 |
| M6 | y_nk | 0.177** (0.087) |  |  |  | -0.007 (0.113) |  | 6.562 | 256 |

M5 Summe der Lags t-1..t-3: 0.208 (SE 0.181, p = 0.251)

M3: +10 pp Kriegsanteil in t-1 ⇒ Median-Views der Nicht-Kriegsvideos in t +1.3 %.

## nur Nachkriegsmonate (t ≥ 03/2022)

| Modell | Outcome | anteil_l1 | anteil | anteil_l2 | anteil_l3 | anteil_f1 | y_nk_l1 | N Zellen | N Kanäle |
|---|---|---|---|---|---|---|---|---|---|
| M1 | y_alle | 0.296** (0.117) |  |  |  |  |  | 7.120 | 293 |
| M2 | y_alle | 0.265** (0.103) | 0.184 (0.124) |  |  |  |  | 6.008 | 253 |
| M3 | y_nk | 0.150 (0.114) |  |  |  |  |  | 7.057 | 290 |
| M3b | y_nk | 0.167 (0.108) | -0.074 (0.134) |  |  |  |  | 5.962 | 252 |
| M4 | y_nk | 0.107* (0.060) |  |  |  |  | 0.669*** (0.035) | 7.016 | 290 |
| M5 | y_nk | 0.094 (0.121) |  | -0.021 (0.105) | 0.136 (0.098) |  |  | 5.179 | 218 |
| M6 | y_nk | 0.159 (0.114) |  |  |  | 0.009 (0.138) |  | 5.650 | 248 |

M5 Summe der Lags t-1..t-3: 0.209 (SE 0.253, p = 0.409)

M3: +10 pp Kriegsanteil in t-1 ⇒ Median-Views der Nicht-Kriegsvideos in t +1.5 %.

## nur sample_kern

| Modell | Outcome | anteil_l1 | anteil | anteil_l2 | anteil_l3 | anteil_f1 | y_nk_l1 | N Zellen | N Kanäle |
|---|---|---|---|---|---|---|---|---|---|
| M1 | y_alle | 0.436*** (0.124) |  |  |  |  |  | 5.464 | 163 |
| M2 | y_alle | 0.363*** (0.106) | 0.318*** (0.114) |  |  |  |  | 4.798 | 152 |
| M3 | y_nk | 0.230** (0.102) |  |  |  |  |  | 5.409 | 162 |
| M3b | y_nk | 0.262** (0.103) | 0.008 (0.119) |  |  |  |  | 4.757 | 152 |
| M4 | y_nk | 0.144** (0.068) |  |  |  |  | 0.702*** (0.036) | 5.378 | 162 |
| M5 | y_nk | 0.184* (0.107) |  | -0.006 (0.096) | 0.174 (0.115) |  |  | 4.162 | 138 |
| M6 | y_nk | 0.269*** (0.102) |  |  |  | 0.093 (0.125) |  | 4.581 | 150 |

M5 Summe der Lags t-1..t-3: 0.352 (SE 0.194, p = 0.070)

M3: +10 pp Kriegsanteil in t-1 ⇒ Median-Views der Nicht-Kriegsvideos in t +2.3 %.

## Heterogenität (Hauptspezifikation)

### Anteil(t-1) × medientyp (Outcome y_nk, Effekt je Gruppe)

| Gruppe | Koeffizient (SE) | p | +10 pp | N Kanäle |
|---|---|---|---|---|
| Creator/alternativ | 0.149 (0.133) | 0.262 | +1.5 % | 210 |
| Partei/Politiker | 0.217 (0.403) | 0.590 | +2.2 % | 19 |
| traditionell | 0.143 (0.152) | 0.347 | +1.4 % | 39 |
| ÖRR | 0.095 (0.175) | 0.589 | +0.9 % | 40 |

### Anteil(t-1) × ideo_gruppe (Outcome y_nk, Effekt je Gruppe)

| Gruppe | Koeffizient (SE) | p | +10 pp | N Kanäle |
|---|---|---|---|---|
| links | 0.204 (0.169) | 0.226 | +2.1 % | 83 |
| mitte | 0.166 (0.139) | 0.231 | +1.7 % | 88 |
| rechts | 0.215 (0.154) | 0.164 | +2.2 % | 110 |

# Keyword-Annäherung der LLM-Themenklassifikation (Segmentebene)

Quelle: `data/claude_classification/angebot/results_segment_level.csv` (nur `kodierbar == 1`).  
Split nach Video gruppiert, Seed 42: **Train 5564 Segmente / 2728 Videos, Test 3650 Segmente / 1820 Videos** (Test vor/nach: 1619/2031).

- **Dict** = Stichwort-Diktionär (Regex-Stämme aus dem Codebuch, Mindest-Trefferzahl je Label auf Train F1-optimal).
- **LR** = TF-IDF (1–2-Gramme) + logistische Regression je Label, Schwelle per 5-facher gruppierter CV auf Train.
- Alle Kennzahlen unten auf dem **Testset**. Anteile = ungewichtete Segmentanteile.

## 1. Themen – Segmentgüte

| Label | n LLM | Anteil LLM | Anteil Dict | P Dict | R Dict | F1 Dict | Anteil LR | P LR | R LR | F1 LR |
|---|---|---|---|---|---|---|---|---|---|---|
| krieg_ukraine | 1493 | 0.41 | 0.42 | 0.91 | 0.94 | 0.92 | 0.41 | 0.94 | 0.95 | 0.94 |
| corona | 752 | 0.21 | 0.18 | 0.92 | 0.79 | 0.85 | 0.19 | 0.92 | 0.86 | 0.89 |
| migration | 168 | 0.05 | 0.03 | 0.79 | 0.57 | 0.66 | 0.06 | 0.52 | 0.68 | 0.59 |
| wirtschaft | 924 | 0.25 | 0.28 | 0.72 | 0.79 | 0.76 | 0.30 | 0.73 | 0.88 | 0.80 |
| energie | 583 | 0.16 | 0.17 | 0.79 | 0.83 | 0.81 | 0.16 | 0.77 | 0.79 | 0.78 |
| klima | 207 | 0.06 | 0.05 | 0.81 | 0.66 | 0.73 | 0.06 | 0.56 | 0.58 | 0.57 |
| gender | 60 | 0.02 | 0.01 | 0.71 | 0.28 | 0.40 | 0.02 | 0.37 | 0.48 | 0.42 |
| nahost | 23 | 0.01 | 0.01 | 0.64 | 0.91 | 0.75 | 0.01 | 0.61 | 0.87 | 0.71 |
| iran | 8 | 0.00 | 0.00 | 0.50 | 0.25 | 0.33 | 0.00 | 0.44 | 0.88 | 0.58 |
| eu | 91 | 0.02 | 0.04 | 0.33 | 0.57 | 0.41 | 0.04 | 0.47 | 0.66 | 0.55 |
| usa | 125 | 0.03 | 0.05 | 0.38 | 0.59 | 0.46 | 0.05 | 0.46 | 0.67 | 0.55 |
| bildung | 62 | 0.02 | 0.02 | 0.60 | 0.58 | 0.59 | 0.02 | 0.47 | 0.65 | 0.54 |
| innenpolitik_sonstige | 537 | 0.15 | 0.15 | 0.57 | 0.59 | 0.58 | 0.16 | 0.62 | 0.69 | 0.65 |
| sonstiges_politisch | 406 | 0.11 | 0.10 | 0.47 | 0.42 | 0.45 | 0.13 | 0.55 | 0.65 | 0.60 |
| unpolitisch | 519 | 0.14 | 0.18 | 0.57 | 0.74 | 0.64 | 0.15 | 0.80 | 0.87 | 0.83 |

**Hauptthema** (eine Kategorie je Segment): Übereinstimmung mit LLM – Dict 73.2%, LR 79.0%.

## 2. Themen – Trendtreue vor/nach Kriegsbeginn

Anteil der Segmente mit dem Thema vor (01.01.–23.02.2022) und nach (24.02.–30.04.2022) Kriegsbeginn.

| Label | LLM vor | LLM nach | LLM Δ | Dict vor | Dict nach | Dict Δ | LR vor | LR nach | LR Δ |
|---|---|---|---|---|---|---|---|---|---|
| krieg_ukraine | 0.169 | 0.601 | 0.432 | 0.189 | 0.608 | 0.419 | 0.191 | 0.592 | 0.401 |
| corona | 0.307 | 0.126 | -0.181 | 0.266 | 0.104 | -0.162 | 0.298 | 0.111 | -0.187 |
| migration | 0.022 | 0.065 | 0.044 | 0.020 | 0.044 | 0.024 | 0.014 | 0.097 | 0.083 |
| wirtschaft | 0.239 | 0.264 | 0.025 | 0.259 | 0.293 | 0.035 | 0.272 | 0.328 | 0.056 |
| energie | 0.090 | 0.215 | 0.125 | 0.107 | 0.218 | 0.110 | 0.106 | 0.209 | 0.103 |
| klima | 0.059 | 0.055 | -0.005 | 0.049 | 0.044 | -0.006 | 0.061 | 0.058 | -0.004 |
| gender | 0.022 | 0.012 | -0.010 | 0.007 | 0.006 | -0.002 | 0.029 | 0.016 | -0.013 |
| nahost | 0.008 | 0.005 | -0.003 | 0.010 | 0.008 | -0.002 | 0.011 | 0.008 | -0.003 |
| iran | 0.001 | 0.003 | 0.003 | 0.000 | 0.002 | 0.002 | 0.004 | 0.004 | 0.000 |
| eu | 0.025 | 0.025 | 0.000 | 0.038 | 0.048 | 0.010 | 0.027 | 0.042 | 0.016 |
| usa | 0.043 | 0.027 | -0.016 | 0.059 | 0.049 | -0.011 | 0.054 | 0.046 | -0.007 |
| bildung | 0.023 | 0.012 | -0.012 | 0.024 | 0.010 | -0.014 | 0.036 | 0.013 | -0.023 |
| innenpolitik_sonstige | 0.177 | 0.123 | -0.054 | 0.175 | 0.131 | -0.044 | 0.195 | 0.136 | -0.059 |
| sonstiges_politisch | 0.141 | 0.088 | -0.053 | 0.111 | 0.090 | -0.021 | 0.165 | 0.104 | -0.061 |
| unpolitisch | 0.170 | 0.120 | -0.051 | 0.241 | 0.138 | -0.103 | 0.190 | 0.125 | -0.065 |

Korrelation der Wochenanteile (18 Wochen) und der Kanal-Veränderungen nach − vor (26 Kanäle mit ≥ 10 Testsegmenten je Phase):

| Label | r Woche Dict | r Kanal-Δ Dict | Vorzeichen Kanal-Δ gleich Dict | r Woche LR | r Kanal-Δ LR | Vorzeichen Kanal-Δ gleich LR |
|---|---|---|---|---|---|---|
| krieg_ukraine | 0.99 | 0.97 | 0.96 | 1.00 | 0.96 | 0.96 |
| corona | 0.98 | 0.90 | 0.73 | 0.99 | 0.96 | 0.92 |
| migration | 0.94 | 0.74 | 0.88 | 0.90 | 0.71 | 0.65 |
| wirtschaft | 0.72 | 0.54 | 0.81 | 0.73 | 0.79 | 0.85 |
| energie | 0.97 | 0.81 | 0.92 | 0.96 | 0.80 | 0.88 |
| klima | 0.83 | 0.69 | 0.85 | 0.63 | 0.34 | 0.65 |
| gender | 0.54 | 0.44 | 0.62 | 0.39 | 0.86 | 0.69 |
| nahost | 0.96 | 0.90 | 0.88 | 0.89 | 0.82 | 0.92 |
| iran | 0.56 | 0.00 | 0.85 | 0.65 | -0.04 | 0.81 |
| eu | 0.13 | 0.54 | 0.69 | 0.12 | 0.58 | 0.69 |
| usa | 0.52 | 0.66 | 0.65 | 0.80 | 0.19 | 0.58 |
| bildung | 0.74 | 0.88 | 0.69 | 0.73 | 0.73 | 0.77 |
| innenpolitik_sonstige | 0.69 | 0.70 | 0.73 | 0.75 | 0.86 | 0.77 |
| sonstiges_politisch | 0.21 | 0.26 | 0.58 | 0.81 | 0.64 | 0.69 |
| unpolitisch | 0.90 | 0.58 | 0.50 | 0.94 | 0.88 | 0.73 |

### Veränderung nach − vor je Medientyp (ausgewählte Themen)

| Medientyp | Label | n vor/nach | Δ LLM | Δ Dict | Δ LR |
|---|---|---|---|---|---|
| alternativ_links | krieg_ukraine | 146/199 | +0.300 | +0.324 | +0.291 |
| alternativ_links | corona | 146/199 | -0.091 | -0.063 | -0.119 |
| alternativ_links | energie | 146/199 | +0.079 | +0.093 | +0.046 |
| alternativ_links | wirtschaft | 146/199 | -0.056 | +0.010 | +0.028 |
| alternativ_links | migration | 146/199 | +0.025 | +0.025 | +0.005 |
| alternativ_rechts | krieg_ukraine | 630/702 | +0.358 | +0.356 | +0.318 |
| alternativ_rechts | corona | 630/702 | -0.114 | -0.076 | -0.124 |
| alternativ_rechts | energie | 630/702 | +0.193 | +0.158 | +0.189 |
| alternativ_rechts | wirtschaft | 630/702 | +0.082 | +0.066 | +0.100 |
| alternativ_rechts | migration | 630/702 | -0.000 | +0.003 | +0.007 |
| oerr | krieg_ukraine | 513/659 | +0.534 | +0.496 | +0.490 |
| oerr | corona | 513/659 | -0.271 | -0.263 | -0.253 |
| oerr | energie | 513/659 | +0.125 | +0.122 | +0.099 |
| oerr | wirtschaft | 513/659 | +0.002 | +0.020 | +0.064 |
| oerr | migration | 513/659 | +0.089 | +0.047 | +0.179 |
| traditionell | krieg_ukraine | 330/471 | +0.451 | +0.434 | +0.441 |
| traditionell | corona | 330/471 | -0.194 | -0.203 | -0.223 |
| traditionell | energie | 330/471 | +0.065 | +0.051 | +0.026 |
| traditionell | wirtschaft | 330/471 | +0.075 | +0.080 | +0.080 |
| traditionell | migration | 330/471 | +0.059 | +0.024 | +0.094 |

## 3. Kriegsaspekte – Segmentgüte

### 3a. Bedingt: nur Testsegmente, die laut LLM `krieg_ukraine` enthalten

| Label | n LLM | Anteil LLM | Anteil Dict | P Dict | R Dict | F1 Dict | Anteil LR | P LR | R LR | F1 LR |
|---|---|---|---|---|---|---|---|---|---|---|
| kriegsgeschehen_militaer | 442 | 0.30 | 0.40 | 0.60 | 0.81 | 0.69 | 0.33 | 0.74 | 0.83 | 0.78 |
| kriegsverbrechen_zivilisten | 322 | 0.22 | 0.28 | 0.56 | 0.74 | 0.64 | 0.23 | 0.75 | 0.80 | 0.78 |
| verhandlungen_diplomatie | 422 | 0.28 | 0.30 | 0.67 | 0.71 | 0.69 | 0.27 | 0.73 | 0.70 | 0.71 |
| waffenlieferungen | 324 | 0.22 | 0.17 | 0.89 | 0.69 | 0.78 | 0.25 | 0.69 | 0.81 | 0.74 |
| sanktionen | 538 | 0.36 | 0.37 | 0.83 | 0.85 | 0.84 | 0.40 | 0.73 | 0.82 | 0.77 |
| finanzhilfe | 95 | 0.06 | 0.06 | 0.34 | 0.35 | 0.35 | 0.04 | 0.53 | 0.33 | 0.40 |
| nato_eu_beitritt | 158 | 0.11 | 0.15 | 0.51 | 0.72 | 0.59 | 0.14 | 0.54 | 0.72 | 0.61 |
| truppen_einsatz | 165 | 0.11 | 0.11 | 0.45 | 0.44 | 0.44 | 0.10 | 0.59 | 0.52 | 0.55 |
| gefluechtete | 184 | 0.12 | 0.12 | 0.70 | 0.70 | 0.70 | 0.13 | 0.73 | 0.74 | 0.74 |
| energie_preise_inland | 441 | 0.30 | 0.29 | 0.85 | 0.82 | 0.84 | 0.34 | 0.73 | 0.84 | 0.78 |
| wirtschaft_inland | 191 | 0.13 | 0.17 | 0.50 | 0.66 | 0.57 | 0.23 | 0.43 | 0.77 | 0.56 |
| bundeswehr_sondervermoegen | 118 | 0.08 | 0.09 | 0.60 | 0.71 | 0.65 | 0.09 | 0.65 | 0.73 | 0.69 |
| russland_innen | 125 | 0.08 | 0.07 | 0.37 | 0.31 | 0.34 | 0.07 | 0.62 | 0.50 | 0.56 |
| medien_desinformation | 247 | 0.17 | 0.15 | 0.66 | 0.62 | 0.64 | 0.17 | 0.64 | 0.66 | 0.65 |
| sonstiges | 168 | 0.11 | 0.00 |  | 0.00 | 0.00 | 0.20 | 0.34 | 0.60 | 0.43 |

### 3b. End-to-End: alle Testsegmente; Aspekt nur, wenn der Klassifikator selbst Krieg erkennt

| Label | n LLM | Anteil LLM | Anteil Dict | F1 Dict | Anteil LR | F1 LR |
|---|---|---|---|---|---|---|
| kriegsgeschehen_militaer | 442 | 0.12 | 0.17 | 0.67 | 0.14 | 0.78 |
| kriegsverbrechen_zivilisten | 322 | 0.09 | 0.12 | 0.61 | 0.09 | 0.77 |
| verhandlungen_diplomatie | 422 | 0.12 | 0.13 | 0.67 | 0.11 | 0.71 |
| waffenlieferungen | 324 | 0.09 | 0.07 | 0.78 | 0.10 | 0.74 |
| sanktionen | 538 | 0.15 | 0.15 | 0.81 | 0.17 | 0.75 |
| finanzhilfe | 95 | 0.03 | 0.03 | 0.33 | 0.02 | 0.40 |
| nato_eu_beitritt | 158 | 0.04 | 0.06 | 0.59 | 0.06 | 0.61 |
| truppen_einsatz | 165 | 0.05 | 0.05 | 0.43 | 0.04 | 0.55 |
| gefluechtete | 184 | 0.05 | 0.05 | 0.66 | 0.05 | 0.73 |
| energie_preise_inland | 441 | 0.12 | 0.11 | 0.78 | 0.14 | 0.72 |
| wirtschaft_inland | 191 | 0.05 | 0.07 | 0.56 | 0.09 | 0.52 |
| bundeswehr_sondervermoegen | 118 | 0.03 | 0.04 | 0.58 | 0.04 | 0.65 |
| russland_innen | 125 | 0.03 | 0.03 | 0.32 | 0.03 | 0.55 |
| medien_desinformation | 247 | 0.07 | 0.07 | 0.61 | 0.07 | 0.63 |
| sonstiges | 168 | 0.05 | 0.00 | 0.00 | 0.09 | 0.38 |

`sonstiges` hat kein Diktionär (Residualkategorie).

## 4. Kriegsaspekte – Trendtreue (Anteil an allen Segmenten, End-to-End)

| Label | LLM vor | LLM nach | LLM Δ | Dict vor | Dict nach | Dict Δ | LR vor | LR nach | LR Δ |
|---|---|---|---|---|---|---|---|---|---|
| kriegsgeschehen_militaer | 0.054 | 0.175 | 0.121 | 0.068 | 0.251 | 0.183 | 0.066 | 0.197 | 0.131 |
| kriegsverbrechen_zivilisten | 0.002 | 0.157 | 0.154 | 0.032 | 0.197 | 0.165 | 0.009 | 0.163 | 0.155 |
| verhandlungen_diplomatie | 0.089 | 0.137 | 0.048 | 0.078 | 0.164 | 0.086 | 0.099 | 0.122 | 0.023 |
| waffenlieferungen | 0.032 | 0.134 | 0.103 | 0.023 | 0.106 | 0.082 | 0.048 | 0.148 | 0.100 |
| sanktionen | 0.056 | 0.221 | 0.165 | 0.057 | 0.226 | 0.169 | 0.083 | 0.232 | 0.149 |
| finanzhilfe | 0.007 | 0.041 | 0.035 | 0.008 | 0.043 | 0.035 | 0.002 | 0.028 | 0.026 |
| nato_eu_beitritt | 0.040 | 0.046 | 0.007 | 0.037 | 0.080 | 0.043 | 0.061 | 0.058 | -0.003 |
| truppen_einsatz | 0.021 | 0.065 | 0.043 | 0.015 | 0.072 | 0.057 | 0.030 | 0.047 | 0.017 |
| gefluechtete | 0.001 | 0.090 | 0.089 | 0.004 | 0.086 | 0.081 | 0.002 | 0.090 | 0.088 |
| energie_preise_inland | 0.051 | 0.177 | 0.126 | 0.042 | 0.156 | 0.114 | 0.070 | 0.187 | 0.117 |
| wirtschaft_inland | 0.007 | 0.088 | 0.081 | 0.025 | 0.103 | 0.078 | 0.033 | 0.135 | 0.102 |
| bundeswehr_sondervermoegen | 0.005 | 0.054 | 0.049 | 0.008 | 0.059 | 0.051 | 0.007 | 0.063 | 0.056 |
| russland_innen | 0.005 | 0.058 | 0.053 | 0.016 | 0.045 | 0.029 | 0.006 | 0.046 | 0.041 |
| medien_desinformation | 0.023 | 0.103 | 0.079 | 0.030 | 0.094 | 0.064 | 0.022 | 0.106 | 0.084 |
| sonstiges | 0.016 | 0.070 | 0.054 | 0.000 | 0.000 | 0.000 | 0.046 | 0.120 | 0.074 |

| Label | r Woche Dict | r Kanal-Δ Dict | Vorzeichen Kanal-Δ gleich Dict | r Woche LR | r Kanal-Δ LR | Vorzeichen Kanal-Δ gleich LR |
|---|---|---|---|---|---|---|
| kriegsgeschehen_militaer | 0.97 | 0.85 | 0.81 | 0.99 | 0.92 | 0.77 |
| kriegsverbrechen_zivilisten | 0.97 | 0.60 | 0.65 | 0.98 | 0.93 | 0.85 |
| verhandlungen_diplomatie | 0.90 | 0.73 | 0.69 | 0.93 | 0.51 | 0.69 |
| waffenlieferungen | 0.99 | 0.95 | 0.88 | 0.94 | 0.87 | 0.92 |
| sanktionen | 0.99 | 0.90 | 0.96 | 0.98 | 0.87 | 0.88 |
| finanzhilfe | 0.93 | 0.34 | 0.77 | 0.87 | 0.87 | 0.85 |
| nato_eu_beitritt | 0.82 | 0.45 | 0.65 | 0.93 | 0.95 | 0.81 |
| truppen_einsatz | 0.81 | 0.79 | 0.73 | 0.78 | -0.06 | 0.65 |
| gefluechtete | 0.93 | 0.89 | 0.85 | 0.97 | 0.94 | 0.88 |
| energie_preise_inland | 0.98 | 0.85 | 0.92 | 0.98 | 0.71 | 0.88 |
| wirtschaft_inland | 0.92 | 0.75 | 0.85 | 0.96 | 0.84 | 0.92 |
| bundeswehr_sondervermoegen | 0.92 | 0.25 | 0.69 | 0.79 | 0.48 | 0.85 |
| russland_innen | 0.73 | 0.35 | 0.62 | 0.94 | 0.81 | 0.73 |
| medien_desinformation | 0.93 | 0.58 | 0.81 | 0.91 | 0.76 | 0.88 |
| sonstiges |  |  | 0.19 | 0.86 | 0.73 | 0.88 |

### Veränderung nach − vor je Medientyp (ausgewählte Aspekte)

| Medientyp | Label | n vor/nach | Δ LLM | Δ Dict | Δ LR |
|---|---|---|---|---|---|
| alternativ_links | sanktionen | 146/199 | +0.137 | +0.132 | +0.137 |
| alternativ_links | waffenlieferungen | 146/199 | +0.067 | +0.043 | +0.032 |
| alternativ_links | energie_preise_inland | 146/199 | +0.065 | +0.075 | +0.077 |
| alternativ_links | verhandlungen_diplomatie | 146/199 | +0.034 | +0.095 | -0.001 |
| alternativ_links | medien_desinformation | 146/199 | +0.113 | +0.086 | +0.139 |
| alternativ_rechts | sanktionen | 630/702 | +0.199 | +0.183 | +0.209 |
| alternativ_rechts | waffenlieferungen | 630/702 | +0.071 | +0.066 | +0.048 |
| alternativ_rechts | energie_preise_inland | 630/702 | +0.190 | +0.160 | +0.216 |
| alternativ_rechts | verhandlungen_diplomatie | 630/702 | +0.056 | +0.076 | +0.001 |
| alternativ_rechts | medien_desinformation | 630/702 | +0.066 | +0.054 | +0.052 |
| oerr | sanktionen | 513/659 | +0.198 | +0.213 | +0.158 |
| oerr | waffenlieferungen | 513/659 | +0.150 | +0.116 | +0.167 |
| oerr | energie_preise_inland | 513/659 | +0.139 | +0.139 | +0.097 |
| oerr | verhandlungen_diplomatie | 513/659 | +0.016 | +0.099 | +0.031 |
| oerr | medien_desinformation | 513/659 | +0.085 | +0.067 | +0.103 |
| traditionell | sanktionen | 330/471 | +0.077 | +0.104 | +0.053 |
| traditionell | waffenlieferungen | 330/471 | +0.096 | +0.072 | +0.103 |
| traditionell | energie_preise_inland | 330/471 | +0.046 | +0.031 | +0.025 |
| traditionell | verhandlungen_diplomatie | 330/471 | +0.073 | +0.067 | +0.039 |
| traditionell | medien_desinformation | 330/471 | +0.077 | +0.066 | +0.080 |

## 5. Gewählte Diktionär-Schwellen (Mindest-Treffer je Segment)

| Label | Typ | Schwelle |
|---|---|---|
| krieg_ukraine | Thema | 3 |
| corona | Thema | 3 |
| migration | Thema | 3 |
| wirtschaft | Thema | 3 |
| energie | Thema | 3 |
| klima | Thema | 2 |
| gender | Thema | 4 |
| nahost | Thema | 4 |
| iran | Thema | 4 |
| eu | Thema | 5 |
| usa | Thema | 6 |
| bildung | Thema | 5 |
| innenpolitik_sonstige | Thema | 8 |
| sonstiges_politisch | Thema | 5 |
| kriegsgeschehen_militaer | Aspekt | 4 |
| kriegsverbrechen_zivilisten | Aspekt | 2 |
| verhandlungen_diplomatie | Aspekt | 2 |
| waffenlieferungen | Aspekt | 1 |
| sanktionen | Aspekt | 1 |
| finanzhilfe | Aspekt | 1 |
| nato_eu_beitritt | Aspekt | 1 |
| truppen_einsatz | Aspekt | 2 |
| gefluechtete | Aspekt | 2 |
| energie_preise_inland | Aspekt | 3 |
| wirtschaft_inland | Aspekt | 5 |
| bundeswehr_sondervermoegen | Aspekt | 2 |
| russland_innen | Aspekt | 3 |
| medien_desinformation | Aspekt | 2 |

## 6. Top-Terme der logistischen Regression (datengetriebene Stichwortlisten)

- **krieg_ukraine**: ukraine, russland, der ukraine, putin, krieg, die ukraine, russischen, russische, gas, sanktionen, russen, nato, ukrainische, ukrainischen, kiew
- **corona**: corona, impfpflicht, maßnahmen, pandemie, lauterbach, virus, impfen, geimpft, pflicht, korona, impfung, die impfpflicht, omikron, maske, der pandemie
- **migration**: flüchtlinge, geflüchteten, der ukraine, polen, kinder, flucht, migranten, ukraine, flüchtlingen, menschen, frauen, migration, deutschland, geflüchtete, 2015
- **wirtschaft**: inflation, euro, geld, unternehmen, wirtschaft, prozent, preise, milliarden, die inflation, ezb, steuern, banken, die preise, staat, zentralbank
- **energie**: gas, energie, öl, russland, strom, nord stream, nord, energiepreise, deutschland, stream, sanktionen, energien, aus russland, preise, habeck
- **klima**: klima, co2, klimaschutz, klimawandel, energien, umwelt, grünen, energie, erneuerbaren, förderung, klimaneutral, atomkraft, den klimawandel, energiewende, strom
- **gender**: frauen, gender, frau, männer, sprache, eine frau, geschlecht, spiegel, frauen in, geschlechter, frauen die, männern, grünen, gesellschaft, mann
- **nahost**: israel, israelische, palästinenser, israelischen, in israel, die israelische, israels, israelis, palästinensischen, gaza, gazastreifen, palästinensern, westjordanland, juden, palästinensische
- **iran**: iran, der iran, den iran, dem iran, saudi, saudi arabien, arabien, im iran, abkommen, israel, deal, gespräche, jemen, dialog, atom
- **eu**: eu, die eu, der eu, europäischen, kommission, europa, europäische, der europäischen, eu kommission, brüssel, union, die europäische, europäische union, europäischen union, frankreich
- **usa**: usa, us, trump, amerikaner, den usa, die usa, china, biden, amerikanischen, beiden, die amerikaner, joe, washington, joe biden, vereinigten staaten
- **bildung**: kinder, schulen, unterricht, schule, schüler, die kinder, kindern, lehrer, eltern, der schule, bildung, schülerinnen und, schülerinnen, und schüler, kinder und
- **innenpolitik_sonstige**: partei, spd, cdu, grünen, bundeswehr, die grünen, polizei, fdp, ampel, bundestag, politiker, demokratie, parteien, der cdu, die spd
- **sonstiges_politisch**: china, makro, le, le pen, pen, assange, in china, regierung, taiwan, chinas, chinesen, kasachstan, chinesische, gegen, frankreich
- **unpolitisch**: musik, gold, du, meter, wasser, ein bisschen, verletzt, wackelig, auto, roman, bisschen, feuerwehr, silber, bewegung, halt
- **aspekt:kriegsgeschehen_militaer**: truppen, soldaten, kiew, armee, ukrainische, russischen, stadt, russische, ukrainischen, ukraine, die ukraine, streitkräfte, russen, panzer, der russischen
- **aspekt:kriegsverbrechen_zivilisten**: zivilisten, kriegsverbrechen, mario, mario pohl, pohl, stadt, kiew, bilder, zivilbevölkerung, armee, angriffe, ukrainischen, menschen, getötet, zerstört
- **aspekt:verhandlungen_diplomatie**: verhandlungen, gespräche, diplomatie, putin, moskau, russland, ukraine, außenminister, präsidenten, frieden, dialog, lösung, waffenstillstand, die ukraine, konflikt
- **aspekt:waffenlieferungen**: waffen, waffenlieferungen, liefern, die ukraine, ukraine, nato, geliefert, waffen liefern, schwere waffen, zu liefern, lieferung, panzer, unterstützung, schwere, der ukraine
- **aspekt:sanktionen**: sanktionen, russland, die sanktionen, öl, gegen russland, sanktionen gegen, gas, embargo, aus russland, putin, eu, nord stream, gegen, nord, rubel
- **aspekt:finanzhilfe**: hilfe, unterstützung, helfen, humanitäre, unterstützen, die ukraine, ukraine, der ukraine, waffen, humanitäre hilfe, spenden, zusammen, zu unterstützen, menschen, deutschland
- **aspekt:nato_eu_beitritt**: nato, die nato, der nato, die ukraine, beitritt, eu, mitgliedschaft, ukraine, russland, neutralität, osterweiterung, erweiterung, finnland, nato beitritt, ukraine in
- **aspekt:truppen_einsatz**: nato, die nato, der nato, flugverbotszone, soldaten, krieg, liefern, konflikt, militärisch, waffen, polen, truppen, kriegspartei, der ukraine, staaten
- **aspekt:gefluechtete**: flüchtlinge, kinder, menschen, flucht, geflüchteten, fliehen, polen, aus der, der ukraine, flüchtlingen, millionen, geflohen, geflüchtete, der flucht, familien
- **aspekt:energie_preise_inland**: gas, energie, nord stream, stream, öl, nord, sanktionen, aus russland, abhängigkeit, deutschland, pipeline, preise, öl und, embargo, kohle
- **aspekt:wirtschaft_inland**: inflation, unternehmen, wirtschaft, industrie, prozent, energie, aus russland, gas, preise, auswirkungen, die wirtschaft, oben, euro, weniger, krise
- **aspekt:bundeswehr_sondervermoegen**: bundeswehr, die bundeswehr, 100 milliarden, milliarden, 100, milliarden euro, sondervermögen, der bundeswehr, zeitenwende, aufrüstung, euro, deutschland, waffen, schuldenbremse, verteidigung
- **aspekt:russland_innen**: in russland, putin, russland, moskau, krieg, propaganda, kreml, in moskau, russische, russischen, oligarchen, russen, putins, medien, leute
- **aspekt:medien_desinformation**: propaganda, medien, in russland, russen, krieg, russland, russische, berichterstattung, journalisten, lügen, staatsfernsehen, informationen, unabhängige, berichten, informationskrieg
- **aspekt:sonstiges**: china, welt, sowjetunion, weizen, le pen, unter, mehr oder, le, oder weniger, macht, die internationale, tschernobyl, indien, zeiten, dass china

Dateien: `test_vorhersagen.csv` (LLM-Labels und beide Vorhersagen je Testsegment).
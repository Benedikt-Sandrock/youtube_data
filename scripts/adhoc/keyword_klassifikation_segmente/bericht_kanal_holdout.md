# Keyword-Annäherung der LLM-Themenklassifikation – Kanal-Holdout

Quelle: `data/claude_classification/angebot/results_segment_level.csv` (nur `kodierbar == 1`).  
**Kanal-Holdout per Kreuzanpassung, 3 Folds** (Seed 42): Die 34 Kanäle sind je Medientyp auf die Folds verteilt; jeder Fold wird mit Modellen vorhergesagt, die die Kanäle dieses Folds **nie gesehen** haben. Testset = alle 9214 Segmente (vor/nach: 4058/5156).

- **Dict** = Stichwort-Diktionär (Regex-Stämme aus dem Codebuch, Mindest-Trefferzahl je Label auf Train F1-optimal).
- **LR** = TF-IDF (1–2-Gramme) + logistische Regression je Label, Schwelle per 5-facher nach Kanal gruppierter CV auf Train.
- Alle Kennzahlen unten auf dem **Testset**. Anteile = ungewichtete Segmentanteile.

### Kanal-Folds

| fold | medientyp | Kanäle | Segmente | Namen |
|---|---|---|---|---|
| 1 | alternativ_links | 3 | 390 | Marvin Neumann, Staiy, Wohlstand für Alle |
| 1 | alternativ_rechts | 4 | 1238 | Erfolgskanal - Community für Finanzen & Wirtschaft, Kettner-Edelmetalle (Gold & Silber), Neverforgetniki, POLITIK SPEZIAL - Stimme der Vernunft  |
| 1 | oerr | 2 | 1317 | DW Deutsch, phoenix |
| 1 | traditionell | 2 | 781 | DER SPIEGEL, faz |
| 2 | alternativ_links | 4 | 320 | Druschba FM, Malternativ, NachDenkSeiten, Rayk Anders |
| 2 | alternativ_rechts | 4 | 841 | Carsten Jahn - TEAM HEIMAT, Deutschland Kurier, Marc Friedrich, Oli |
| 2 | oerr | 1 | 732 | ZDFheute Nachrichten |
| 2 | traditionell | 1 | 703 | BILD |
| 3 | alternativ_links | 4 | 300 | Ernst Wolff, Geld für die Welt — Maurice Höfgen, Volksverpetzer, acTVism Munich |
| 3 | alternativ_rechts | 5 | 1251 | Boris Reitschuster, FinanzmarktWelt.de, Gerald Grosz, LEO "Ketzer der Neuzeit", Oli redet |
| 3 | oerr | 2 | 793 | MrWissen2go, tagesschau |
| 3 | traditionell | 2 | 548 | WELT Nachrichtensender, stern TV |

## 0. Vergleich: Video-Split vs. Kanal-Holdout (F1)

Video-Split = Testset aus `test_vorhersagen.csv` (Kanäle auch im Training); Kanal-Holdout = dieser Lauf (alle Segmente, Kanäle nie im Training). Aspekte End-to-End.

| Label | Typ | F1 Dict Video | F1 Dict Kanal | F1 LR Video | F1 LR Kanal |
|---|---|---|---|---|---|
| krieg_ukraine | Thema | 0.92 | 0.92 | 0.94 | 0.93 |
| corona | Thema | 0.85 | 0.83 | 0.89 | 0.86 |
| migration | Thema | 0.66 | 0.64 | 0.59 | 0.62 |
| wirtschaft | Thema | 0.76 | 0.77 | 0.80 | 0.81 |
| energie | Thema | 0.81 | 0.82 | 0.78 | 0.78 |
| klima | Thema | 0.73 | 0.71 | 0.57 | 0.58 |
| gender | Thema | 0.40 | 0.39 | 0.42 | 0.48 |
| nahost | Thema | 0.75 | 0.76 | 0.71 | 0.81 |
| iran | Thema | 0.33 | 0.56 | 0.58 | 0.60 |
| eu | Thema | 0.41 | 0.48 | 0.55 | 0.51 |
| usa | Thema | 0.46 | 0.48 | 0.55 | 0.47 |
| bildung | Thema | 0.59 | 0.62 | 0.54 | 0.61 |
| innenpolitik_sonstige | Thema | 0.58 | 0.59 | 0.65 | 0.66 |
| sonstiges_politisch | Thema | 0.45 | 0.44 | 0.60 | 0.57 |
| unpolitisch | Thema | 0.64 | 0.66 | 0.83 | 0.76 |
| kriegsgeschehen_militaer | Aspekt (E2E) | 0.67 | 0.69 | 0.78 | 0.77 |
| kriegsverbrechen_zivilisten | Aspekt (E2E) | 0.61 | 0.59 | 0.77 | 0.74 |
| verhandlungen_diplomatie | Aspekt (E2E) | 0.67 | 0.67 | 0.71 | 0.70 |
| waffenlieferungen | Aspekt (E2E) | 0.78 | 0.76 | 0.74 | 0.75 |
| sanktionen | Aspekt (E2E) | 0.81 | 0.83 | 0.75 | 0.74 |
| finanzhilfe | Aspekt (E2E) | 0.33 | 0.36 | 0.40 | 0.44 |
| nato_eu_beitritt | Aspekt (E2E) | 0.59 | 0.59 | 0.61 | 0.63 |
| truppen_einsatz | Aspekt (E2E) | 0.43 | 0.44 | 0.55 | 0.55 |
| gefluechtete | Aspekt (E2E) | 0.66 | 0.69 | 0.73 | 0.72 |
| energie_preise_inland | Aspekt (E2E) | 0.78 | 0.78 | 0.72 | 0.72 |
| wirtschaft_inland | Aspekt (E2E) | 0.56 | 0.54 | 0.52 | 0.56 |
| bundeswehr_sondervermoegen | Aspekt (E2E) | 0.58 | 0.62 | 0.65 | 0.61 |
| russland_innen | Aspekt (E2E) | 0.32 | 0.37 | 0.55 | 0.56 |
| medien_desinformation | Aspekt (E2E) | 0.61 | 0.61 | 0.63 | 0.60 |
| sonstiges | Aspekt (E2E) | 0.00 | 0.00 | 0.38 | 0.36 |

## 1. Themen – Segmentgüte

| Label | n LLM | Anteil LLM | Anteil Dict | P Dict | R Dict | F1 Dict | Anteil LR | P LR | R LR | F1 LR |
|---|---|---|---|---|---|---|---|---|---|---|
| krieg_ukraine | 3704 | 0.40 | 0.42 | 0.90 | 0.93 | 0.92 | 0.41 | 0.92 | 0.94 | 0.93 |
| corona | 1802 | 0.20 | 0.18 | 0.86 | 0.80 | 0.83 | 0.18 | 0.88 | 0.83 | 0.86 |
| migration | 437 | 0.05 | 0.04 | 0.69 | 0.60 | 0.64 | 0.05 | 0.60 | 0.64 | 0.62 |
| wirtschaft | 2487 | 0.27 | 0.29 | 0.74 | 0.79 | 0.77 | 0.30 | 0.77 | 0.86 | 0.81 |
| energie | 1491 | 0.16 | 0.17 | 0.79 | 0.84 | 0.82 | 0.18 | 0.73 | 0.83 | 0.78 |
| klima | 504 | 0.05 | 0.05 | 0.75 | 0.68 | 0.71 | 0.07 | 0.52 | 0.66 | 0.58 |
| gender | 144 | 0.02 | 0.02 | 0.38 | 0.40 | 0.39 | 0.02 | 0.41 | 0.58 | 0.48 |
| nahost | 66 | 0.01 | 0.01 | 0.72 | 0.80 | 0.76 | 0.01 | 0.74 | 0.88 | 0.81 |
| iran | 29 | 0.00 | 0.00 | 0.60 | 0.52 | 0.56 | 0.00 | 0.61 | 0.59 | 0.60 |
| eu | 244 | 0.03 | 0.03 | 0.47 | 0.48 | 0.48 | 0.04 | 0.41 | 0.68 | 0.51 |
| usa | 334 | 0.04 | 0.05 | 0.41 | 0.56 | 0.48 | 0.06 | 0.38 | 0.62 | 0.47 |
| bildung | 141 | 0.02 | 0.01 | 0.64 | 0.60 | 0.62 | 0.02 | 0.55 | 0.69 | 0.61 |
| innenpolitik_sonstige | 1359 | 0.15 | 0.16 | 0.56 | 0.61 | 0.59 | 0.17 | 0.62 | 0.71 | 0.66 |
| sonstiges_politisch | 1013 | 0.11 | 0.10 | 0.46 | 0.42 | 0.44 | 0.14 | 0.51 | 0.66 | 0.57 |
| unpolitisch | 1332 | 0.14 | 0.18 | 0.58 | 0.75 | 0.66 | 0.19 | 0.67 | 0.89 | 0.76 |

**Hauptthema** (eine Kategorie je Segment): Übereinstimmung mit LLM – Dict 73.3%, LR 77.5%.

## 2. Themen – Trendtreue vor/nach Kriegsbeginn

Anteil der Segmente mit dem Thema vor (01.01.–23.02.2022) und nach (24.02.–30.04.2022) Kriegsbeginn.

| Label | LLM vor | LLM nach | LLM Δ | Dict vor | Dict nach | Dict Δ | LR vor | LR nach | LR Δ |
|---|---|---|---|---|---|---|---|---|---|
| krieg_ukraine | 0.168 | 0.586 | 0.418 | 0.191 | 0.592 | 0.401 | 0.198 | 0.579 | 0.380 |
| corona | 0.293 | 0.119 | -0.175 | 0.269 | 0.113 | -0.156 | 0.287 | 0.104 | -0.182 |
| migration | 0.018 | 0.071 | 0.053 | 0.023 | 0.055 | 0.033 | 0.010 | 0.083 | 0.073 |
| wirtschaft | 0.253 | 0.283 | 0.030 | 0.265 | 0.306 | 0.041 | 0.283 | 0.317 | 0.034 |
| energie | 0.105 | 0.207 | 0.102 | 0.121 | 0.211 | 0.090 | 0.122 | 0.231 | 0.109 |
| klima | 0.069 | 0.044 | -0.025 | 0.062 | 0.041 | -0.022 | 0.077 | 0.064 | -0.013 |
| gender | 0.020 | 0.012 | -0.008 | 0.018 | 0.016 | -0.002 | 0.032 | 0.014 | -0.017 |
| nahost | 0.008 | 0.007 | -0.001 | 0.009 | 0.008 | -0.001 | 0.009 | 0.008 | -0.002 |
| iran | 0.003 | 0.003 | 0.000 | 0.003 | 0.003 | 0.000 | 0.004 | 0.002 | -0.002 |
| eu | 0.026 | 0.027 | 0.002 | 0.025 | 0.029 | 0.004 | 0.035 | 0.052 | 0.016 |
| usa | 0.043 | 0.031 | -0.012 | 0.055 | 0.044 | -0.012 | 0.068 | 0.052 | -0.016 |
| bildung | 0.019 | 0.013 | -0.006 | 0.019 | 0.010 | -0.009 | 0.026 | 0.013 | -0.013 |
| innenpolitik_sonstige | 0.174 | 0.126 | -0.048 | 0.180 | 0.148 | -0.032 | 0.203 | 0.139 | -0.063 |
| sonstiges_politisch | 0.126 | 0.097 | -0.029 | 0.105 | 0.093 | -0.012 | 0.161 | 0.129 | -0.032 |
| unpolitisch | 0.171 | 0.124 | -0.047 | 0.226 | 0.152 | -0.074 | 0.229 | 0.166 | -0.063 |

Korrelation der Wochenanteile (18 Wochen) und der Kanal-Veränderungen nach − vor (32 Kanäle mit ≥ 10 Testsegmenten je Phase):

| Label | r Woche Dict | r Kanal-Δ Dict | Vorzeichen Kanal-Δ gleich Dict | r Woche LR | r Kanal-Δ LR | Vorzeichen Kanal-Δ gleich LR |
|---|---|---|---|---|---|---|
| krieg_ukraine | 1.00 | 0.94 | 0.94 | 1.00 | 0.96 | 0.97 |
| corona | 0.99 | 0.90 | 0.81 | 0.99 | 0.95 | 0.91 |
| migration | 0.95 | 0.86 | 0.84 | 0.96 | 0.86 | 0.69 |
| wirtschaft | 0.63 | 0.62 | 0.78 | 0.87 | 0.83 | 0.84 |
| energie | 0.98 | 0.93 | 0.91 | 0.97 | 0.90 | 0.94 |
| klima | 0.89 | 0.74 | 0.78 | 0.80 | 0.27 | 0.66 |
| gender | 0.32 | 0.88 | 0.50 | 0.47 | 0.84 | 0.69 |
| nahost | 0.93 | 0.67 | 0.72 | 0.98 | 0.44 | 0.81 |
| iran | 0.68 | 0.58 | 0.72 | 0.64 | 0.44 | 0.88 |
| eu | 0.54 | 0.49 | 0.66 | 0.58 | 0.68 | 0.78 |
| usa | 0.80 | 0.77 | 0.72 | 0.46 | 0.79 | 0.69 |
| bildung | 0.79 | 0.87 | 0.75 | 0.81 | 0.89 | 0.84 |
| innenpolitik_sonstige | 0.90 | 0.67 | 0.75 | 0.94 | 0.87 | 0.78 |
| sonstiges_politisch | 0.56 | 0.10 | 0.47 | 0.95 | 0.84 | 0.91 |
| unpolitisch | 0.93 | 0.65 | 0.56 | 0.95 | 0.82 | 0.62 |

### Veränderung nach − vor je Medientyp (ausgewählte Themen)

| Medientyp | Label | n vor/nach | Δ LLM | Δ Dict | Δ LR |
|---|---|---|---|---|---|
| alternativ_links | krieg_ukraine | 423/587 | +0.238 | +0.232 | +0.207 |
| alternativ_links | corona | 423/587 | -0.042 | -0.020 | -0.054 |
| alternativ_links | energie | 423/587 | +0.046 | +0.057 | +0.051 |
| alternativ_links | wirtschaft | 423/587 | -0.016 | +0.032 | +0.026 |
| alternativ_links | migration | 423/587 | +0.017 | +0.010 | +0.005 |
| alternativ_rechts | krieg_ukraine | 1557/1773 | +0.342 | +0.332 | +0.304 |
| alternativ_rechts | corona | 1557/1773 | -0.125 | -0.087 | -0.120 |
| alternativ_rechts | energie | 1557/1773 | +0.167 | +0.131 | +0.178 |
| alternativ_rechts | wirtschaft | 1557/1773 | +0.082 | +0.062 | +0.069 |
| alternativ_rechts | migration | 1557/1773 | -0.007 | -0.004 | +0.002 |
| oerr | krieg_ukraine | 1223/1619 | +0.522 | +0.494 | +0.467 |
| oerr | corona | 1223/1619 | -0.240 | -0.236 | -0.261 |
| oerr | energie | 1223/1619 | +0.099 | +0.106 | +0.113 |
| oerr | wirtschaft | 1223/1619 | +0.029 | +0.059 | +0.049 |
| oerr | migration | 1223/1619 | +0.110 | +0.072 | +0.150 |
| traditionell | krieg_ukraine | 855/1177 | +0.466 | +0.446 | +0.445 |
| traditionell | corona | 855/1177 | -0.225 | -0.227 | -0.239 |
| traditionell | energie | 855/1177 | +0.048 | +0.037 | +0.039 |
| traditionell | wirtschaft | 855/1177 | +0.031 | +0.034 | +0.033 |
| traditionell | migration | 855/1177 | +0.085 | +0.046 | +0.104 |

## 3. Kriegsaspekte – Segmentgüte

### 3a. Bedingt: nur Testsegmente, die laut LLM `krieg_ukraine` enthalten

| Label | n LLM | Anteil LLM | Anteil Dict | P Dict | R Dict | F1 Dict | Anteil LR | P LR | R LR | F1 LR |
|---|---|---|---|---|---|---|---|---|---|---|
| kriegsgeschehen_militaer | 1130 | 0.31 | 0.37 | 0.65 | 0.79 | 0.71 | 0.32 | 0.76 | 0.79 | 0.78 |
| kriegsverbrechen_zivilisten | 777 | 0.21 | 0.27 | 0.55 | 0.71 | 0.62 | 0.23 | 0.72 | 0.79 | 0.75 |
| verhandlungen_diplomatie | 1028 | 0.28 | 0.31 | 0.65 | 0.73 | 0.68 | 0.31 | 0.67 | 0.74 | 0.71 |
| waffenlieferungen | 824 | 0.22 | 0.17 | 0.90 | 0.68 | 0.77 | 0.23 | 0.74 | 0.77 | 0.76 |
| sanktionen | 1277 | 0.34 | 0.36 | 0.83 | 0.87 | 0.85 | 0.43 | 0.69 | 0.86 | 0.76 |
| finanzhilfe | 250 | 0.07 | 0.08 | 0.35 | 0.41 | 0.37 | 0.14 | 0.33 | 0.70 | 0.45 |
| nato_eu_beitritt | 419 | 0.11 | 0.15 | 0.52 | 0.68 | 0.59 | 0.14 | 0.57 | 0.71 | 0.63 |
| truppen_einsatz | 403 | 0.11 | 0.25 | 0.33 | 0.75 | 0.46 | 0.13 | 0.51 | 0.61 | 0.56 |
| gefluechtete | 470 | 0.13 | 0.12 | 0.73 | 0.70 | 0.72 | 0.13 | 0.72 | 0.74 | 0.73 |
| energie_preise_inland | 1079 | 0.29 | 0.29 | 0.85 | 0.84 | 0.84 | 0.32 | 0.75 | 0.82 | 0.79 |
| wirtschaft_inland | 510 | 0.14 | 0.19 | 0.50 | 0.69 | 0.58 | 0.20 | 0.51 | 0.76 | 0.61 |
| bundeswehr_sondervermoegen | 294 | 0.08 | 0.09 | 0.63 | 0.73 | 0.68 | 0.09 | 0.62 | 0.71 | 0.66 |
| russland_innen | 310 | 0.08 | 0.10 | 0.36 | 0.43 | 0.39 | 0.11 | 0.49 | 0.66 | 0.56 |
| medien_desinformation | 572 | 0.15 | 0.14 | 0.67 | 0.62 | 0.65 | 0.19 | 0.58 | 0.70 | 0.63 |
| sonstiges | 444 | 0.12 | 0.00 |  | 0.00 | 0.00 | 0.21 | 0.33 | 0.59 | 0.42 |

### 3b. End-to-End: alle Testsegmente; Aspekt nur, wenn der Klassifikator selbst Krieg erkennt

| Label | n LLM | Anteil LLM | Anteil Dict | F1 Dict | Anteil LR | F1 LR |
|---|---|---|---|---|---|---|
| kriegsgeschehen_militaer | 1130 | 0.12 | 0.16 | 0.69 | 0.13 | 0.77 |
| kriegsverbrechen_zivilisten | 777 | 0.08 | 0.11 | 0.59 | 0.10 | 0.74 |
| verhandlungen_diplomatie | 1028 | 0.11 | 0.13 | 0.67 | 0.12 | 0.70 |
| waffenlieferungen | 824 | 0.09 | 0.07 | 0.76 | 0.09 | 0.75 |
| sanktionen | 1277 | 0.14 | 0.15 | 0.83 | 0.18 | 0.74 |
| finanzhilfe | 250 | 0.03 | 0.03 | 0.36 | 0.06 | 0.44 |
| nato_eu_beitritt | 419 | 0.05 | 0.06 | 0.59 | 0.06 | 0.63 |
| truppen_einsatz | 403 | 0.04 | 0.10 | 0.44 | 0.05 | 0.55 |
| gefluechtete | 470 | 0.05 | 0.05 | 0.69 | 0.05 | 0.72 |
| energie_preise_inland | 1079 | 0.12 | 0.11 | 0.78 | 0.13 | 0.72 |
| wirtschaft_inland | 510 | 0.06 | 0.08 | 0.54 | 0.08 | 0.56 |
| bundeswehr_sondervermoegen | 294 | 0.03 | 0.04 | 0.62 | 0.04 | 0.61 |
| russland_innen | 310 | 0.03 | 0.04 | 0.37 | 0.05 | 0.56 |
| medien_desinformation | 572 | 0.06 | 0.06 | 0.61 | 0.08 | 0.60 |
| sonstiges | 444 | 0.05 | 0.00 | 0.00 | 0.10 | 0.36 |

`sonstiges` hat kein Diktionär (Residualkategorie).

## 4. Kriegsaspekte – Trendtreue (Anteil an allen Segmenten, End-to-End)

| Label | LLM vor | LLM nach | LLM Δ | Dict vor | Dict nach | Dict Δ | LR vor | LR nach | LR Δ |
|---|---|---|---|---|---|---|---|---|---|
| kriegsgeschehen_militaer | 0.062 | 0.171 | 0.109 | 0.073 | 0.221 | 0.148 | 0.065 | 0.182 | 0.117 |
| kriegsverbrechen_zivilisten | 0.004 | 0.147 | 0.143 | 0.030 | 0.182 | 0.152 | 0.011 | 0.162 | 0.150 |
| verhandlungen_diplomatie | 0.093 | 0.126 | 0.034 | 0.086 | 0.162 | 0.075 | 0.101 | 0.144 | 0.043 |
| waffenlieferungen | 0.034 | 0.133 | 0.099 | 0.024 | 0.101 | 0.076 | 0.044 | 0.132 | 0.088 |
| sanktionen | 0.056 | 0.204 | 0.148 | 0.057 | 0.216 | 0.159 | 0.097 | 0.240 | 0.143 |
| finanzhilfe | 0.008 | 0.042 | 0.034 | 0.007 | 0.052 | 0.045 | 0.017 | 0.093 | 0.076 |
| nato_eu_beitritt | 0.045 | 0.046 | 0.001 | 0.038 | 0.075 | 0.037 | 0.061 | 0.054 | -0.007 |
| truppen_einsatz | 0.022 | 0.061 | 0.038 | 0.049 | 0.148 | 0.099 | 0.039 | 0.064 | 0.025 |
| gefluechtete | 0.001 | 0.091 | 0.090 | 0.006 | 0.083 | 0.077 | 0.004 | 0.091 | 0.087 |
| energie_preise_inland | 0.051 | 0.170 | 0.119 | 0.045 | 0.155 | 0.110 | 0.060 | 0.179 | 0.118 |
| wirtschaft_inland | 0.007 | 0.093 | 0.086 | 0.027 | 0.116 | 0.089 | 0.026 | 0.122 | 0.095 |
| bundeswehr_sondervermoegen | 0.003 | 0.055 | 0.052 | 0.007 | 0.059 | 0.052 | 0.009 | 0.062 | 0.053 |
| russland_innen | 0.006 | 0.056 | 0.050 | 0.022 | 0.060 | 0.038 | 0.013 | 0.074 | 0.061 |
| medien_desinformation | 0.026 | 0.091 | 0.065 | 0.029 | 0.087 | 0.057 | 0.029 | 0.113 | 0.085 |
| sonstiges | 0.016 | 0.073 | 0.057 | 0.000 | 0.000 | 0.000 | 0.051 | 0.135 | 0.084 |

| Label | r Woche Dict | r Kanal-Δ Dict | Vorzeichen Kanal-Δ gleich Dict | r Woche LR | r Kanal-Δ LR | Vorzeichen Kanal-Δ gleich LR |
|---|---|---|---|---|---|---|
| kriegsgeschehen_militaer | 0.97 | 0.83 | 0.72 | 0.99 | 0.90 | 0.78 |
| kriegsverbrechen_zivilisten | 0.98 | 0.81 | 0.75 | 0.97 | 0.96 | 0.84 |
| verhandlungen_diplomatie | 0.91 | 0.68 | 0.75 | 0.94 | 0.74 | 0.78 |
| waffenlieferungen | 0.98 | 0.96 | 0.94 | 0.96 | 0.86 | 0.84 |
| sanktionen | 0.99 | 0.91 | 0.97 | 0.99 | 0.95 | 0.97 |
| finanzhilfe | 0.91 | 0.66 | 0.81 | 0.91 | 0.83 | 0.62 |
| nato_eu_beitritt | 0.70 | 0.51 | 0.69 | 0.92 | 0.62 | 0.56 |
| truppen_einsatz | 0.90 | 0.55 | 0.75 | 0.87 | 0.65 | 0.72 |
| gefluechtete | 0.98 | 0.93 | 0.78 | 0.99 | 0.97 | 0.81 |
| energie_preise_inland | 0.99 | 0.92 | 1.00 | 0.99 | 0.77 | 0.91 |
| wirtschaft_inland | 0.96 | 0.88 | 0.84 | 0.98 | 0.75 | 0.91 |
| bundeswehr_sondervermoegen | 0.92 | 0.83 | 0.91 | 0.90 | 0.84 | 0.88 |
| russland_innen | 0.88 | 0.20 | 0.62 | 0.97 | 0.54 | 0.75 |
| medien_desinformation | 0.94 | 0.84 | 0.91 | 0.96 | 0.74 | 0.84 |
| sonstiges |  |  | 0.09 | 0.96 | 0.58 | 0.88 |

### Veränderung nach − vor je Medientyp (ausgewählte Aspekte)

| Medientyp | Label | n vor/nach | Δ LLM | Δ Dict | Δ LR |
|---|---|---|---|---|---|
| alternativ_links | sanktionen | 423/587 | +0.110 | +0.122 | +0.103 |
| alternativ_links | waffenlieferungen | 423/587 | +0.029 | +0.028 | +0.024 |
| alternativ_links | energie_preise_inland | 423/587 | +0.061 | +0.051 | +0.070 |
| alternativ_links | verhandlungen_diplomatie | 423/587 | +0.013 | +0.046 | +0.003 |
| alternativ_links | medien_desinformation | 423/587 | +0.089 | +0.077 | +0.081 |
| alternativ_rechts | sanktionen | 1557/1773 | +0.190 | +0.186 | +0.206 |
| alternativ_rechts | waffenlieferungen | 1557/1773 | +0.062 | +0.045 | +0.036 |
| alternativ_rechts | energie_preise_inland | 1557/1773 | +0.170 | +0.152 | +0.197 |
| alternativ_rechts | verhandlungen_diplomatie | 1557/1773 | +0.052 | +0.064 | +0.021 |
| alternativ_rechts | medien_desinformation | 1557/1773 | +0.048 | +0.048 | +0.050 |
| oerr | sanktionen | 1223/1619 | +0.167 | +0.192 | +0.136 |
| oerr | waffenlieferungen | 1223/1619 | +0.151 | +0.116 | +0.153 |
| oerr | energie_preise_inland | 1223/1619 | +0.130 | +0.131 | +0.102 |
| oerr | verhandlungen_diplomatie | 1223/1619 | +0.011 | +0.098 | +0.058 |
| oerr | medien_desinformation | 1223/1619 | +0.077 | +0.064 | +0.105 |
| traditionell | sanktionen | 855/1177 | +0.072 | +0.088 | +0.069 |
| traditionell | waffenlieferungen | 855/1177 | +0.114 | +0.087 | +0.099 |
| traditionell | energie_preise_inland | 855/1177 | +0.060 | +0.047 | +0.046 |
| traditionell | verhandlungen_diplomatie | 855/1177 | +0.033 | +0.060 | +0.057 |
| traditionell | medien_desinformation | 855/1177 | +0.063 | +0.053 | +0.109 |

## 5. Gewählte Diktionär-Schwellen (Mindest-Treffer je Segment)

| Label | Typ | Schwelle Fold 1 | Schwelle Fold 2 | Schwelle Fold 3 |
|---|---|---|---|---|
| krieg_ukraine | Thema | 3 | 3 | 3 |
| corona | Thema | 2 | 3 | 3 |
| migration | Thema | 3 | 2 | 3 |
| wirtschaft | Thema | 3 | 3 | 3 |
| energie | Thema | 3 | 3 | 3 |
| klima | Thema | 2 | 2 | 2 |
| gender | Thema | 3 | 3 | 3 |
| nahost | Thema | 4 | 7 | 4 |
| iran | Thema | 4 | 2 | 3 |
| eu | Thema | 7 | 6 | 7 |
| usa | Thema | 6 | 6 | 7 |
| bildung | Thema | 6 | 5 | 6 |
| innenpolitik_sonstige | Thema | 7 | 7 | 8 |
| sonstiges_politisch | Thema | 5 | 5 | 5 |
| kriegsgeschehen_militaer | Aspekt | 5 | 4 | 4 |
| kriegsverbrechen_zivilisten | Aspekt | 2 | 2 | 2 |
| verhandlungen_diplomatie | Aspekt | 2 | 2 | 2 |
| waffenlieferungen | Aspekt | 1 | 1 | 1 |
| sanktionen | Aspekt | 1 | 1 | 1 |
| finanzhilfe | Aspekt | 1 | 1 | 1 |
| nato_eu_beitritt | Aspekt | 1 | 1 | 1 |
| truppen_einsatz | Aspekt | 1 | 1 | 1 |
| gefluechtete | Aspekt | 2 | 2 | 2 |
| energie_preise_inland | Aspekt | 3 | 3 | 3 |
| wirtschaft_inland | Aspekt | 5 | 4 | 5 |
| bundeswehr_sondervermoegen | Aspekt | 2 | 2 | 2 |
| russland_innen | Aspekt | 3 | 2 | 3 |
| medien_desinformation | Aspekt | 2 | 2 | 2 |

## 6. Top-Terme der logistischen Regression (datengetriebene Stichwortlisten)

Aus dem Modell von Fold 1 (trainiert ohne die Kanäle von Fold 1).

- **krieg_ukraine**: ukraine, russland, der ukraine, putin, krieg, die ukraine, russischen, russische, gas, russen, sanktionen, nato, kiew, ukrainischen, ukrainische
- **corona**: corona, impfpflicht, maßnahmen, pandemie, lauterbach, pflicht, impfung, impfen, virus, korona, geimpft, die impfpflicht, omikron, maske, masken
- **migration**: flüchtlinge, migranten, kinder, polen, flucht, geflüchteten, menschen, flüchtlingen, frauen, deutschland, 2015, nach deutschland, migration, der ukraine, grenze
- **wirtschaft**: inflation, euro, geld, wirtschaft, unternehmen, preise, prozent, die inflation, milliarden, ezb, steuern, die preise, fed, energie, staat
- **energie**: gas, energie, öl, russland, strom, energiepreise, nord stream, deutschland, nord, stream, abhängigkeit, aus russland, preise, sanktionen, euro
- **klima**: klima, co2, klimaschutz, klimawandel, energien, grünen, energie, atomkraft, förderung, grüne, umwelt, fossilen, steuer, das klima, erneuerbaren
- **gender**: frauen, gender, frau, männer, grünen, eine frau, geschlechter, kirche, metoo, feministische, familie, spiegel, den grünen, frauen in, mann
- **nahost**: israel, israelischen, palästinenser, israelische, in israel, die israelische, israels, antisemitismus, der israelischen, juden, westjordanland, palästinensischen, gazastreifen, israelis, gaza
- **iran**: iran, der iran, israel, dem iran, den iran, saudi, saudi arabien, arabien, jemen, im iran, deal, im jemen, israels, nahen, atom
- **eu**: eu, der eu, die eu, europäischen, europäische, union, europa, brüssel, kommission, ungarn, der europäischen, eu kommission, der leyen, leyen, die europäische
- **usa**: usa, us, trump, die usa, amerikaner, biden, beiden, vereinigten, den usa, joe, vereinigten staaten, joe biden, die amerikaner, amerikanischen, washington
- **bildung**: schulen, kinder, schüler, schule, unterricht, kindern, die kinder, lehrer, die schulen, schülerinnen, eltern, den schulen, bildung, die schule, schülerinnen und
- **innenpolitik_sonstige**: partei, spd, cdu, grünen, bundeswehr, fdp, steinmeier, bundestag, die grünen, kanzler, bundespräsident, amt, opposition, der spd, ampel
- **sonstiges_politisch**: china, le, peking, assange, pen, le pen, chinas, in china, chinesen, welt, kanada, frankreich, kasachstan, kirche, in frankreich
- **unpolitisch**: meter, wackelig, polizei, unfall, verletzt, markt, musik, bewegung, tier, die polizei, schnee, feuerwehr, stunden, du, der kurs
- **aspekt:kriegsgeschehen_militaer**: truppen, kiew, soldaten, armee, russen, ukrainische, russischen, stadt, russische, die russen, streitkräfte, ukrainischen, panzer, ukraine, die ukraine
- **aspekt:kriegsverbrechen_zivilisten**: zivilisten, kriegsverbrechen, stadt, mario, mario pohl, pohl, kiew, bilder, menschen, zerstört, angriffe, zivilbevölkerung, armee, butter, ukrainische
- **aspekt:verhandlungen_diplomatie**: verhandlungen, putin, diplomatie, moskau, gespräche, lösung, waffenstillstand, russland, präsidenten, ukraine, diplomatischen, frieden, diplomatische, der ukraine, mit putin
- **aspekt:waffenlieferungen**: waffen, waffenlieferungen, liefern, die ukraine, ukraine, geliefert, nato, schwere waffen, panzer, unterstützung, lieferung, deutschland, schwere, zu liefern, der ukraine
- **aspekt:sanktionen**: sanktionen, die sanktionen, öl, russland, gegen russland, gas, sanktionen gegen, embargo, eu, aus russland, nord, banken, gegen, putin, wirtschaft
- **aspekt:finanzhilfe**: hilfe, unterstützung, der ukraine, die ukraine, ukraine, humanitäre, helfen, unterstützen, finanzielle, waffen, brauchen, natalia, hilfsbereitschaft, menschen, hilfe für
- **aspekt:nato_eu_beitritt**: nato, die nato, der nato, beitritt, die ukraine, eu, russland, ukraine, mitgliedschaft, osterweiterung, nato osterweiterung, neutralität, russlands, finnland, westen
- **aspekt:truppen_einsatz**: nato, die nato, flugverbotszone, der nato, krieg, polen, baltikum, litauen, soldaten, liefern, kriegspartei, eine flugverbotszone, waffen, der ukraine, konflikt
- **aspekt:gefluechtete**: flüchtlinge, kinder, menschen, flucht, flüchtlingen, geflüchteten, fliehen, polen, aus der, die menschen, menschen die, geflüchtete, kindern, millionen, der flucht
- **aspekt:energie_preise_inland**: gas, energie, öl, nord stream, stream, nord, abhängigkeit, aus russland, sanktionen, pipeline, deutschland, embargo, kohle, öl und, rubel
- **aspekt:wirtschaft_inland**: inflation, wirtschaft, energie, gas, prozent, sanktionen, preise, industrie, getreide, die wirtschaft, preis, weizen, unternehmen, auswirkungen, produktion
- **aspekt:bundeswehr_sondervermoegen**: bundeswehr, die bundeswehr, 100 milliarden, milliarden, 100, milliarden euro, der bundeswehr, sondervermögen, zeitenwende, verteidigung, aufrüstung, euro, waffen, verteidigen, lindner
- **aspekt:russland_innen**: in russland, putin, russland, propaganda, moskau, krieg, in moskau, russische, kreml, russen, russischen, von putin, fernsehen, putins, der russischen
- **aspekt:medien_desinformation**: propaganda, medien, in russland, krieg, russen, russland, staatsfernsehen, die propaganda, russischen, russische, berichterstattung, die wahrheit, bilder, moskau, wahrheit
- **aspekt:sonstiges**: china, sowjetunion, schwesig, unter, interessen, menschen, ist auch, mit dem, leben, spielt, indien, pro, manuela, weizen, russland und

Dateien: `test_vorhersagen_kanal_holdout.csv` (LLM-Labels und beide Vorhersagen je Testsegment).
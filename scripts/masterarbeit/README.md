# scripts/masterarbeit — Skripte der Arbeitspakete

Einmalige, AP-spezifische Auswertungsskripte für die Arbeitspakete aus
[`.claude/plans/masterarbeit_strategie.md`](../../.claude/plans/masterarbeit_strategie.md).
Sie liegen hier statt in `scripts/adhoc/`, damit die Masterarbeits-Analysen
gebündelt auffindbar sind. Pfad-Konstante im Code:
`youtube_code.config.paths.MASTERARBEIT_SCRIPTS`.

**Regeln:**
- Dateiname mit AP-Präfix: `apN_<thema>.py`.
- Ausgaben nach `MASTERARBEIT_OUTPUTS / "apN_<thema>"` (siehe
  [`outputs/masterarbeit/README.md`](../../outputs/masterarbeit/README.md)),
  Regressionsausgaben als Markdown in dessen Unterordner `regression_results/`.
- Pfade ausschließlich aus `youtube_code.config.paths` importieren.
- Dauerhaft genutzte Erweiterungen (z. B. AP 4, AP 5) gehören nicht hierher,
  sondern in die bestehenden Skripte unter `src/youtube_code/step6_auswertung/`.
- Ausführen aus dem Repo-Root mit `PYTHONPATH=src`, z. B.
  `PYTHONPATH=src python scripts/masterarbeit/ap1_selektionscheck.py`.

## Übersicht

| AP | Skript | Output |
|---|---|---|
| 1 | `ap1_selektionsdiagnose.py` (zuerst, schreibt `ap1_diagnose_videos.csv`), `ap1_selektionscheck.py` | `outputs/masterarbeit/ap1_selektion/` |
| 2 | `ap2_marktanteil_stichprobenbias.py` (nur lesend; `--n-bootstrap`, Default 1000; Datenbasis `lade_basisdaten(kanalquelle="kanon")` aus `step6_auswertung/frage4_kriegspraemie_relative_views_plots.py`) | `outputs/masterarbeit/ap2_stichprobenbias/` |
| 3 | `ap3_validierung_stichprobe.py`, `ap3_validierung_auswertung.py` | `outputs/masterarbeit/ap3_validierung/` |
| 4 | Erweiterung von `step6_auswertung/populismuspraemie_kriegsvideos_bericht.py` | `outputs/masterarbeit/ap4_positionspraemie/` |
| 5 | Erweiterung von `step6_auswertung/frage1_{populismus,stance}_bericht.py` | `outputs/masterarbeit/ap5_frage1_did/` |
| 6 | `ap6_rueckkopplung.py` | `outputs/masterarbeit/ap6_rueckkopplung/` |
| 7 | `ap7_themenaufmerksamkeit.py` | `outputs/masterarbeit/ap7_themenaufmerksamkeit/` |

Die Skripte werden in den jeweiligen AP-Sessions angelegt; die Tabelle nennt
die geplanten Namen.

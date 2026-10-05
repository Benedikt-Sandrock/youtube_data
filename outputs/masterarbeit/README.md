# outputs/masterarbeit — Ergebnisse der Arbeitspakete

Hier landen alle **neuen** Ergebnisse der Arbeitspakete (AP) aus
[`.claude/plans/masterarbeit_strategie.md`](../../.claude/plans/masterarbeit_strategie.md),
je AP ein Unterordner. Regressionsausgaben liegen jeweils in einem eigenen
`regression_results/` innerhalb des AP-Ordners (Regel aus `.claude/CLAUDE.md`).
Pfad-Konstante im Code: `youtube_code.config.paths.MASTERARBEIT_OUTPUTS`.

**Nicht hier:**
- Eingangsdaten der Analysen (`channel_video_*.csv`, Kanal-Periode-Zeitreihen,
  Whitelist) bleiben in [`../segment_analysis/`](../segment_analysis/). Sie
  werden von der step6-Pipeline erzeugt und von vielen Skripten geteilt.
- Bereits bestehende Berichte der step6-Skripte bleiben an ihrem Ort. Nur
  **neue** Berichte aus AP-Erweiterungen dieser Skripte (AP 4, AP 5) werden
  hierher geschrieben.
- Das inhaltliche Ergebnis-Dokument bleibt
  [`../segment_analysis/zentrale_ergebnisse.md`](../segment_analysis/zentrale_ergebnisse.md).

Die zugehörigen AP-spezifischen Skripte liegen in
[`scripts/masterarbeit/`](../../scripts/masterarbeit/README.md).

## Übersicht

| AP | Ordner | Hauptergebnis | Status |
|---|---|---|---|
| 1 Selektions-Asymmetrie Frage 1 | `ap1_selektion/` | `regression_results/frage1_selektionsdiagnose.md`, `regression_results/frage1_selektionscheck.md`, `ap1_diagnose_videos.csv` | erledigt (B zurückgestellt) |
| 2 Stichproben-Bias Marktanteil | `ap2_stichprobenbias/` | `regression_results/marktanteil_stichprobenbias.md` (+ `marktanteil_varianten_monat.csv`, `ap2_kanaele.csv`, Plot) | erledigt (2026-09-28): hält in V1, nicht in V3 |
| 3 LLM-Validierung | `ap3_validierung/` | `llm_validierung.md` (+ Stichprobe, Kodierbogen) | offen |
| 4 Heterogenität Positionsprämie | `ap4_positionspraemie/` | `regression_results/positionspraemie_heterogenitaet.md` | offen |
| 5 Frage 1 als DiD | `ap5_frage1_did/` | `regression_results/frage1_did.md` | offen |
| 6 Rückkopplung Nachfrage → Angebot | `ap6_rueckkopplung/` | `regression_results/rueckkopplung_nachfrage_angebot.md` | offen |
| 7 Themenaufmerksamkeit | `ap7_themenaufmerksamkeit/` | Plot + Methodik-Markdown | offen |
| 8 Kommentare (optional) | `ap8_kommentare/` | – | offen |
| 9 Hauptmodelle | (dieser Ordner) | `hauptmodelle.md` | offen |

Status nach Abschluss eines AP hier und in der Strategie-Datei aktualisieren.

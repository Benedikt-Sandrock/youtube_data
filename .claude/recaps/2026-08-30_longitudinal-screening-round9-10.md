# Recap: Longitudinal-Screening Runde 9/10 & Baseline-Video-Listen (2026-08-30)

Kontext-Briefing für eine neue Claude-Code-Session in diesem Repo
(`C:\Users\bened\PycharmProjects\youtube_data`). Schließt inhaltlich an
`outputs/segment_analysis/HANDOFF_baseline_collection_27_channels.md` und
`outputs/segment_analysis/HANDOFF_STEP3_ONWARDS.md` an — die dort beschriebene
Runde 9 wurde in dieser Session abgeschickt, vervollständigt und um eine
Runde 10 erweitert.

## Sofortiger nächster Schritt (das war unterbrochen)

Runde-10-**Titel**-Ergebnisse sind fertig heruntergeladen (`run_0024`,
385/385 Gruppen, 3.844/3.844 Videos akzeptiert), aber **noch nicht in den
State gemergt**. Die Konfigurationsdateien stehen bereits korrekt dafür:

```bash
# 1. Erst Dry-Run pruefen (Datei steht schon auf DRY_RUN=True):
PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
  src/youtube_code/politics_screening/update_screening_state.py
# MODE="title", ROUND_NUMBER=10, RUN_ID="run_0024" sind schon gesetzt.

# 2. Wenn Plan plausibel: DRY_RUN=False in der Datei setzen, dann:
echo y | PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
  src/youtube_code/politics_screening/update_screening_state.py
```

Danach prüfen, ob Description-Kandidaten entstanden sind
(`data/samples/russia/batches_longitudinal/description_rounds/screening_round_010_description_candidates.csv`).
Falls ja: in `run_longitudinal_screening_batch.py` `MODE="description"` setzen
(Datei steht aktuell auf `ROUND_NUMBER=10, MODE="title", DRY_RUN=False` —
**erst DRY_RUN=True setzen**, dry-run prüfen, dann False, submitten), Job
abwarten (`download_results.py` bzw. Polling-Helper s.u.), dann wieder
`update_screening_state.py` mit `MODE="description", RUN_ID=<neue Run-ID>`
mergen. Erst dann ist **Runde 10 vollständig** — Auftrag des Nutzers war
"Runde 9 vervollständigen + eine vollständige Runde 10".

## Was in dieser Session erledigt wurde

### Runde 9 — vollständig abgeschlossen
- Titel-Batch `run_0022` (403 Requests, 4.021 Videos, vom Nutzer selbst
  abgeschickt) fertig, gemergt: 748 direkt politisch, 2.677 direkt
  unpolitisch, 596 titelseitig unklar → Description-Kandidaten.
- Description-Batch `run_0023` (120 Requests, 596 Videos) abgeschickt,
  fertig, gemergt: 143 politisch, 266 unpolitisch, 187 bleiben
  `politics_final = -1` (bewusst offen für manuelle/Transkript-Prüfung).
- Runde 9 gesamt: **891 neue politische Videos** state-weit.

### Runde 10 — Titel-Stufe fertig, Merge ausstehend (siehe oben)
- `create_longitudinal_screening.py` real gelaufen: 3.844 Kandidaten,
  21 Kanäle, 385 erwartete Requests. State bereits mit
  `screening_round=10` markiert für diese Zeilen.
- Titel-Batch `run_0024` abgeschickt und heruntergeladen (385/385 Gruppen,
  3.844/3.844 Videos akzeptiert) — **Merge in den State noch nicht
  ausgeführt** (siehe "Sofortiger nächster Schritt").

### Baseline-Video-ID-Listen für den Transkript-Download
Zwei Listen für `src/youtube_code/scraping/transcript_scraping_segments.py`
gebaut (Format: `[{"video_id": ..., "channel_id": ...}, ...]`):

1. `postwar_baseline_35channels_fill_vids.json` — 635 IDs für die 35
   Post-Kriegs-Kanäle, die zum damaligen Zeitpunkt schon ≥10 politische
   Videos hatten. **War ein No-Op**: alle 635 IDs hatten schon einen
   Eintrag in `all_transcripts_segments.csv` (597 OK, 13 kein Transkript,
   25 permanente Fehler wie deaktivierte Untertitel). Kann ggf. gelöscht
   werden, ist reine Dokumentation.
2. `baseline_now_sufficient_fill_vids.json` — **aktuelle** Liste (Stand:
   nach Runde-9-Merge, **vor** Runde-10-Merge), 764 IDs für 40 Kanäle:
   - Vorkriegs-27-Kanäle-Projekt (Fenster 2021-02-24 bis 2022-02-23,
     `interval_label` in `{-12_to_-10, -9_to_-7, -6_to_-4}`): alle 3
     großen Kanäle (euronews deutsch: 30, WELT Nachrichtensender: 37,
     OE24.TV: 35 politische Videos) qualifizieren jetzt (≥10). Die 24
     "normalen" Kanäle aus diesem Projekt haben weiterhin 0 Kandidaten im
     Fenster — brauchen echten Video-Nachdownload, nicht Transkript-Download.
   - Postwar-85-Kanäle-Set (`interval_index == -1`): **37 von 85**
     qualifizieren jetzt mit ≥10 politischen Videos (waren vorher 35 —
     Runde 9 hat 2 weitere über die Schwelle gebracht).
   - Abgleich mit `all_transcripts_segments.csv`: 662 der 764 IDs schon
     versucht, **102 tatsächlich neu** — diese Liste ist kein No-Op.

**Bewusst noch nicht abschließend behandelt:**
   - Die restlichen ~48 Postwar-Kanäle ohne ausreichend politische Videos
     (~31 mit 0 Kandidaten im Fenster brauchen echten Video-Nachdownload
     via `channel_all_videos.py` mit kanal-individuellem Zeitfenster; ~17
     haben Kandidaten, aber noch nicht genug klassifiziert — könnten durch
     weitere Screening-Runden wachsen, kein Video-Download nötig).
   - Die 24 "normalen" Kanäle aus dem 27er-Projekt (weiterhin 0 Kandidaten,
     Pool gilt als erschöpft, siehe
     `outputs/segment_analysis/baseline_reach_check_24channels.json`).

### Transkript-Download-Listen im Scraping-Verzeichnis (zu Sessionbeginn geprüft)
Abgleich aller `*.json`-Video-ID-Listen in `src/youtube_code/scraping/`
gegen `all_transcripts_segments.csv` (Stand: Sessionbeginn, vor allen
Baseline-Änderungen — sollte bei Bedarf neu geprüft werden):

| Datei | Gesamt | noch offen |
|---|---:|---:|
| `baseline_fill_vids.json` | 306 | 0 |
| `fill_vids.json` | 1.398 | 0 |
| `kriegsvideo_luecken_fill_vids.json` | 3.184 | 0 |
| `fill_vids_extended.json` | 3.641 | 3.517 |
| `right_videos_to_scrape.json` | 5.973 | 3.357 |
| `vids_right.json` | 4.598 | 1.856 |
| `vids.json` | 15.482 | 7.950 |

`fill_vids_extended.json` war entgegen der Erwartung des Nutzers NICHT
fertig abgearbeitet (3.517 offen) — falls das noch relevant ist, mit dem
Nutzer klären, ob das ein abgebrochener Lauf war.

## Wichtige technische Hinweise (diese Session gelernt/bestätigt)

- `.venv/Scripts/python.exe` verwenden (kein `python3` im PATH),
  `PYTHONPATH=src PYTHONIOENCODING=utf-8` immer voranstellen.
- `run_longitudinal_screening_batch.py`, `download_results.py` (im
  interaktiven `main()`) und `update_screening_state.py` (bei
  `CONFIRM_BEFORE_WRITE=True`) haben `input()`-Bestätigungsprompts — beim
  automatisierten Ausführen mit `echo y | ...` beantworten. Für
  reines Polling ohne Prompt: `download_results.process_run(run_id)`
  direkt aus Python importieren (nicht `main()`), siehe
  `wait_and_download.py`-Muster unten.
- Lange Skripte (State-Verarbeitung auf der 1.2GB-CSV, Batch-Job-Polling)
  IMMER mit `run_in_background` laufen lassen, nicht im Vordergrund pollen.
  Ein kleines Hilfsskript (`wait_and_download.py`, poll_seconds=300) ruft
  `download_results.process_run(run_id)` in einer Schleife auf, bis Status
  `downloaded` oder ein Fehlerstatus erreicht ist — vermeidet die
  interaktiven Prompts von `download_results.main()` komplett. Lag diese
  Session im Scratchpad-Verzeichnis (session-spezifisch, nicht mehr
  vorhanden) — bei Bedarf neu anlegen, Vorlage steht im Session-Transkript.
- **Kein `ScheduleWakeup` für reines Warten auf einen bereits laufenden
  Background-Task verwenden** — der Tool-Abschluss benachrichtigt ohnehin
  automatisch. `ScheduleWakeup` ist nur für `/loop`-Dynamic-Mode gedacht.
- Ein Background-Task wurde einmal ohne erkennbaren Grund von außen
  gekillt (Status `killed`, keine Ausgabe). Da unklar war, ob das ein
  bewusster Eingriff war, wurde pausiert und nachgefragt statt sofort neu
  zu starten — nach Bestätigung ganz normal weitergemacht. Bei ähnlichem
  Verhalten wieder erst nachfragen.
- State-Datei (`data/samples/russia/longitudinal_screening_state.csv`,
  ~1,2GB) hat keine Git-Historie. Merge-Skripte legen automatisch Backups
  in `data/samples/russia/batches_longitudinal/state_backups/` an — kein
  manuelles Backup vor dem Merge-Schritt nötig (anders als bei
  `append_channels_to_state.py`, das kein automatisches Backup macht).
- Nur `data/transcripts/all_transcripts_segments.csv` zählt projektweit als
  "hat schon ein Transkript" (Projektregel, siehe `.claude/CLAUDE.md`).

## Referenz: Pipeline-Kurzübersicht

Vollständige Anleitung: `src/youtube_code/politics_screening/README_ADD_NEW_CHANNELS.md`.

| Skript | Zweck |
|---|---|
| `politics_screening/longitudinal/create_longitudinal_screening.py` | Nächste Runde planen (state-weit, adaptiv) |
| `llm_analysis/run_longitudinal_screening_batch.py` | Batch-Job einreichen (Prompt 32 title / 33 description) |
| `llm_analysis/download_results.py` | Ergebnisse abholen (`process_run()` direkt importieren fürs Polling) |
| `politics_screening/update_screening_state.py` | Ergebnisse in State mergen |

Wichtige Konstanten: `TARGET_POLITICAL_PER_INTERVAL=10`,
`TARGET_WITH_BUFFER_PER_INTERVAL=12` (`screening_config.py`).

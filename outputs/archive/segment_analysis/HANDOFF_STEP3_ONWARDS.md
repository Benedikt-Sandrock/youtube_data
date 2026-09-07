# Handoff: Baseline-Datenerhebung 27 Kanäle — STATUS: Titel-Screening vorbereitet, wartet auf Abschicken

Ursprüngliche Handoff-Kette: `HANDOFF_baseline_collection_27_channels.md` (Schritte
1–6) → diese Datei (Fortsetzung ab Schritt 3). **Schritte 1–4 aus dieser Datei sind
jetzt ebenfalls abgeschlossen.** Es fehlt nur noch das eigentliche Abschicken des
Batch-Jobs — das macht der Nutzer bewusst selbst.

## Was in dieser Session erledigt wurde

### Schritt 3 — State erweitert (abgeschlossen)

- Backup angelegt: `data/samples/russia/longitudinal_screening_state.csv.bak_pre_27channels_step3`.
- `append_channels_to_state.py` mit `--videos data/raw/video_metadata_detailed_total.jsonl`
  crashte zunächst mit `MemoryError` (2GB-JSONL, `pd.read_json(lines=True)` — nicht
  memory-effizient bei dieser Größe, unabhängig davon, wie wenige Zeilen am Ende
  gebraucht werden). **Workaround:** die JSONL vorher zeilenweise (streaming
  `json.loads`, kein Pandas) auf die 27 Ziel-`channel_id`s gefiltert (139.390 von
  1.073.309 Zeilen passten) → kleinere Zwischen-JSONL (~248MB), danach lief das
  Append-Skript sauber durch. Diese Zwischen-JSONL wurde nach dem Lauf wieder gelöscht
  (regenerierbar). Der komplette Ablauf inkl. dieses Workarounds ist jetzt dokumentiert
  in `src/youtube_code/politics_screening/README_ADD_NEW_CHANNELS.md`.
- Dry-Run und echter Lauf bestätigten die erwartete Verteilung: **28.412 neue
  Baseline-Kandidatenzeilen für die 3 großen Kanäle** (euronews 8.645-Fenster-Anteil,
  WELT, OE24.TV — Aufteilung über `interval_index` 0–3), **0 neue Zeilen für die
  anderen 24 Kanäle** (wie erwartet, siehe Ursprungs-Diagnose unten). State: 983.794 →
  1.012.206 Zeilen.

### Schritt 4 — Screening-Runde 009 erzeugt (abgeschlossen)

- `create_longitudinal_screening.py`: erst `DRY_RUN=True` geprüft, Plan plausibel
  (siehe unten), dann `DRY_RUN=False` real ausgeführt.
- Runde 009 ist **State-weit** geplant (nicht nur für die 27 Kanäle) — 27 Kanäle
  insgesamt ausgewählt, 4.021 Titel-Kandidaten, 403 erwartete Modell-Requests, verteilt
  über 253 Kanal-Interval-Zellen (6.717 Zellen bereits `candidate_pool_exhausted`,
  6.694 bereits `target_reached`). Das ist normales Verhalten des Skripts (adaptive
  Runde über den gesamten State), nicht auf die 27 Kanäle beschränkt.
- Erzeugte Dateien:
  - `data/samples/russia/batches_longitudinal/screening_rounds/screening_round_009_title_candidates.csv`
  - `data/samples/russia/batches_longitudinal/screening_round_summaries/screening_round_009_selection_summary.csv`
  - State aktualisiert (`screening_round=9` für die 4.021 ausgewählten Zeilen).

### Schritt 5 (Batch-Einreichung) — vorbereitet, NICHT abgeschickt (bewusst)

`src/youtube_code/llm_analysis/run_longitudinal_screening_batch.py` ist konfiguriert:

```
ROUND_NUMBER = 9
MODE = "title"
DRY_RUN = True
ALLOW_EXISTING_RUN = False
```

Ein `DRY_RUN=True`-Lauf wurde bereits ausgeführt und die Preflight-Validierung war
**vollständig erfolgreich**: Kandidaten-IDs stimmen exakt mit den offenen State-Zeilen
für Runde 9 überein, keine leeren Titel, keine Dubletten, 4.021 Videos / 27 Kanäle /
403 Requests, Prompt `PROMPT_32`, Modell `gemini_25_flash`. Der Lauf endete an der
interaktiven Bestätigung (`Create dry-run files? [Y/n]`) — diese wurde bewusst nicht
automatisiert durchgeklickt (Nutzerwunsch: "Das Abschicken erledige ich dann selber").

**Für den Nutzer, um wirklich abzuschicken:**

```bash
PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
  src/youtube_code/llm_analysis/run_longitudinal_screening_batch.py
```

1. Läuft mit `DRY_RUN=True` — bei der Frage `Create dry-run files? [Y/n]` mit `Y`
   bestätigen (schreibt nur lokale Vorschau-Dateien, reicht noch nichts ein). Vorschau
   (JSONL, Manifest) bei Bedarf inspizieren.
2. In der Datei `DRY_RUN = False` setzen.
3. Skript erneut laufen lassen → reicht den Batch-Job wirklich bei Vertex AI ein und
   trägt ihn in `src/youtube_code/llm_analysis/registry/runs_registry.csv` ein.
4. Danach dem restlichen Zyklus aus `src/youtube_code/politics_screening/README_ADD_NEW_CHANNELS.md`
   folgen (Schritt 7 dort: `download_results.py`, dann `update_screening_state.py`
   MODE="title", dann Description-Runde für die `-1`-Fälle, dann erneut
   `create_longitudinal_screening.py`).

## Nebenbefund (unverändert relevant)

Alle 24 "normalen" Kanäle haben verifiziert 0 Baseline-Videos (öffentliche
Upload-Historie reicht nicht bis 2021/2022 zurück oder echte Aktivitätslücke) — siehe
`outputs/segment_analysis/baseline_reach_check_24channels.json`. Kandidatenpool für
diese 24 gilt als erschöpft, unabhängig vom Ergebnis der Titel-Klassifikation für die 3
großen Kanäle.

## Aufräumhinweis für eine künftige Session

Neu entstandener State-Backup `longitudinal_screening_state.csv.bak_pre_27channels_step3`
(~1.2GB, keine Git-Historie) liegt jetzt neben der aktuellen State-Datei in
`data/samples/russia/`. Analog zu den in der Restrukturierung (Phase 1) bereits
gelöschten älteren Backups sollte dieser irgendwann wieder aufgeräumt werden, sobald er
nicht mehr als Rückfallebene gebraucht wird (z.B. nachdem Runde 9 erfolgreich verarbeitet
wurde) — nicht vorschnell löschen, so lange die Runde 9 noch nicht abgeschickt/verarbeitet
ist.

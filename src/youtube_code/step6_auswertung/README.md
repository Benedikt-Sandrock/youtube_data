# Schritt 6 — Auswertung von Transkripten

Aggregiert und analysiert die LLM-Klassifikationsergebnisse aus Schritt 5
(`COMPLETE_PROCESS.md` Schritt 6). Baut auf dem Output von
`step5_segment_analysis/download_segments_simple.py` auf; geteilt wird nur
`outputs/segment_analysis/` als Lese-/Schreibort für abgeleitete
Zwischen- und Endergebnisse.

Diese Dateien lagen bis zur Aufräumarbeit im Zuge der Schritt-5-Bereinigung
noch in `step5_segment_analysis/` (siehe dortige README-Historie); der
Ordner hier fasst sie unter Schritt 6 zusammen, wie in `COMPLETE_PROCESS.md`
vorgesehen.

## Ablauf (0–3)

```
youtube_code/step6_auswertung/
    prepare_channel_scores.py     0: Segment- -> Video- -> Kanal x Periode
    deskriptiv_aggregation.py     1: Zeitreihen laden, Baseline-Index bilden
    deskriptiv_plots.py           2a: Zeitverlaufsplots
    fe_signifikanz_test.py        2b: FE-Regression + Robustheitschecks
    geglaettete_kurve.py          2c: LOWESS-Kurve + Cluster-Bootstrap-CI
```

0. **`prepare_channel_scores.py`**: liest die drei rohen LLM-Ergebnisdateien
   (Ideologie, Populismus, Position/Stance) sowie `populism_runs_combined.csv`
   und aggregiert Segment → Video → Kanal×Periode für beide Granularitäten
   (Monat/Quartal). Schreibt u. a. `channel_{monat,quartal}_populism_timeseries.csv`,
   `channel_{monat,quartal}_position_timeseries.csv`,
   `channel_classification_{ideology,populism}.csv`,
   `channel_video_{populism,position}.csv` nach `outputs/segment_analysis/`.
   Muss laufen, bevor eines der folgenden Skripte sinnvolle Eingaben findet.
1. **`deskriptiv_aggregation.py`**: liest die Zeitreihen aus Schritt 0,
   ergänzt Medientyp (`lade_medientyp()`, aus `data/external/media_type_russia_merged.xlsx`)
   und Ideologie (`lade_ideologie()`, aus `channel_classification_ideology.csv`),
   filtert Kanäle und bildet für `MODUS = "populismus"` einen Baseline-Index
   (letzte Vorkriegsperioden = 100). Schreibt
   `deskriptiv_{modus}_{granularitaet}.csv`.
2. **`deskriptiv_plots.py`**: plottet den Output von Schritt 1 (Index bei
   Populismus, Rohwerte bei Stance), mit optionalem Split nach Medientyp
   oder Ideologie. Schreibt PNGs nach `outputs/segment_analysis/plots/`.
3. **`fe_signifikanz_test.py`**: formale Prüfung, ob eine Dimension
   innerhalb einer gefilterten Kanalgruppe über die Zeit wirklich schwankt
   (Kanal-Fixed-Effects + Perioden-Dummies, auf Kanalebene geclusterte
   Standardfehler, F-Test auf gemeinsame Signifikanz der Perioden-Dummies).
   Arbeitet auf Video-Ebene (`channel_video_{populism,position}.csv`).
   Robustheitschecks: `vergleiche_gewichtung()` (kanal- vs. videogewichtet),
   `jackknife_trend_test()` (Leave-one-channel-out).
4. **`geglaettete_kurve.py`**: deskriptiv-explorativer Schritt vor formalen
   Bruchpunkt-/Phasentests — LOWESS-geglättete Kurve des kanalbereinigten
   Signals mit Cluster-Bootstrap-Konfidenzband, plus Ereignismarkern.

## Konfiguration

Jedes Skript trägt seine Konfiguration als Modul-Level-Konstanten am
Dateikopf (Muster wie in den anderen Schritt-Ordnern).

### `prepare_channel_scores.py`

| Parameter | Bedeutung |
|---|---|
| `VIDEO_PATH` | `outputs/sample_feasibility/videos_compact_pol_labels.csv` — Video-Metadaten für den Merge |
| `RESULTS_PATH_IDEOLOGY`/`_POPULISM_BASE`/`_STANCE` | rohe LLM-Ergebnisdateien unter `outputs/llm_results/segment_analysis_active__<run_id>/` (Output von `download_segments_simple.py`, siehe unten) |
| `RESULTS_PATH_POPULISM_MAIN` | `populism_runs_combined.csv`, flach unter `outputs/segment_analysis/` |
| `GRANULARITAETEN` | Definiert Perioden-Länge (Monat/Quartal) je Zeitreihen-Output |

**Offener Punkt:** `RESULTS_PATH_IDEOLOGY`/`_POPULISM_BASE`/`_STANCE` zeigen
auf `_corrected.csv`-Varianten der Rohergebnisse; `RESULTS_PATH_POPULISM_MAIN`
auf `populism_runs_combined.csv`. Beide Dateiarten sind **manuell kuratiert**
— im Repo existiert kein Skript, das sie erzeugt (nur auskommentierter Code
in `scripts/adhoc/segment_analysis_result_checks.py`, der auf eine manuelle
`to_csv()`-Korrektur hindeutet). Zwischen dem automatischen Output von
`download_segments_simple.py` und dem Input dieses Skripts liegt also aktuell
eine nirgends im Code abgebildete manuelle Kuratierungs-/Kombinationsstufe.
Analog zum "Validierung gegen Handkodierung"-Punkt in
`step5_segment_analysis/README.md`: vor dem Berichten von Ergebnissen sollte
geklärt werden, wie diese Korrektur nachvollziehbar/reproduzierbar gemacht
wird.

### `deskriptiv_aggregation.py`

| Parameter | Bedeutung |
|---|---|
| `MODUS` | `"populismus"` \| `"stance"` |
| `GRANULARITAET` | `"quartal"` \| `"monat"` — muss zur eingelesenen Zeitreihen-Datei passen |
| `BASELINE_PERIODEN` / `MIN_BASELINE_*` | nur für `MODUS = "populismus"`: welche Vorkriegsperioden den Index-Nenner (=100) bilden |
| `MEDIENTYPEN` / `KANAL_WHITELIST` / `KANAL_BLACKLIST` | Kanalfilter, `None` = alle |
| `IDEOLOGIE_DIMENSION` / `IDEOLOGIE_SCHNITTE` | Schwellenwerte für links/mitte/rechts-Einteilung |

Exportiert `lade_medientyp()` und `lade_ideologie()` — werden von
`fe_signifikanz_test.py` und `scripts/adhoc/video_sample_uebersicht.py`
importiert (siehe unten).

### `deskriptiv_plots.py`

| Parameter | Bedeutung |
|---|---|
| `MODUS` / `GRANULARITAET` | muss zur `deskriptiv_{modus}_{granularitaet}.csv` aus Schritt 1 passen |
| `SPLIT` | `"keiner"` \| `"medientyp"` \| `"ideologie"` |

### `fe_signifikanz_test.py`

| Parameter | Bedeutung |
|---|---|
| `MODUS` / `GRANULARITAET` | wie oben |
| `DIMENSION` | z. B. `"position_russland"` — Spalte aus `channel_video_{populism,position}.csv` |
| `FILTER` | Kanalfilter für die Regression |

### `geglaettete_kurve.py`

Nutzt dieselbe `CONFIG` (`MODUS`, `GRANULARITAET`, `DIMENSION`, `FILTER`,
`PERIODE_MIN`/`_MAX`) wie `fe_signifikanz_test.py` — dort gepflegt, hier nur
importiert (siehe Imports unten).

## Ausführung

`prepare_channel_scores.py`, wie die entsprechenden Skripte in `step1`–`step5`,
als Paketmodul:

```
PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.prepare_channel_scores
```

`deskriptiv_aggregation.py`, `deskriptiv_plots.py`, `fe_signifikanz_test.py`
und `geglaettete_kurve.py` dagegen **direkt im Ordner ausführen**
(`python deskriptiv_aggregation.py` usw.), nicht als `-m`-Modul:
`fe_signifikanz_test.py` importiert `deskriptiv_aggregation` und
`geglaettete_kurve.py` importiert `fe_signifikanz_test` jeweils als **bare
sibling import** (kein `youtube_code.step6_auswertung....`-Pfad) — das
funktioniert nur, wenn Python das Skriptverzeichnis selbst auf `sys.path[0]`
legt, also bei direkter Ausführung im selben Ordner. Diese Entscheidung ist
bewusst so belassen (siehe
`.claude/restructuring/RESTRUCTURING_PROGRESS.md`): eine Umstellung auf
Paket-relative Importe würde diesen Ausführungsweg brechen.

## Zusammenhang mit `scripts/adhoc/`

Drei reine Diagnose-/Ad-hoc-Skripte, die auf denselben Zwischenergebnissen
aufsetzen, liegen bewusst **nicht** hier, sondern in `scripts/adhoc/`
(gemäß `.claude/CLAUDE.md`):

- `check_baseline_coverage.py` — für Kanäle ohne Baseline-Klassifikation,
  die laut `video_registry.sqlite` im/vor dem Baseline-Fenster existierten:
  wie viele ihrer Videos sind (nicht) klassifiziert.
- `finde_download_kandidaten.py` — findet für dünn besetzte
  Kanal-Perioden-Zellen konkrete unklassifizierte Kriegsvideo-Kandidaten zum
  Nachdownloaden.
- `video_sample_uebersicht.py` — Übersicht über bereits klassifizierte
  Videos nach Medientyp×Periode, identifiziert dünn besetzte Zellen
  (Grundlage für `finde_download_kandidaten.py`). Importiert
  `lade_medientyp()` aus diesem Ordner als echten Paketimport
  (`from youtube_code.step6_auswertung.deskriptiv_aggregation import lade_medientyp`),
  da es — anders als die vier Skripte oben — in einem anderen Verzeichnis
  liegt als `deskriptiv_aggregation.py`.

Alle drei setzen `prepare_channel_scores.py` (Schritt 0 hier) voraus.

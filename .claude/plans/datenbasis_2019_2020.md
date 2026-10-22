# Plan: Datenbasis auf 2019–2020 erweitern (nur Metadaten)

**Einstieg für eine neue Session:** erst `.claude/CLAUDE.md`, `README.md` und `COMPLETE_PROCESS.md`
lesen (Session-Regeln), dann diesen Plan. Der Abschnitt „Stand“ unten zeigt, was erledigt ist.
**Erstellt:** 22.10.2026. Plan und Vorarbeit sind auf einem Rechner entstanden, dessen Arbeitskopie
unvollständig war. **Ausgeführt wird er auf dem Hauptrechner** mit den vollständigen Stores und
Outputs.

## Ziel
Für die Kanäle des Samples `russia_longitudinal_v1` alle Videos ab **2019-01-01** in die Registry
holen, mit Views, Dauer, Format (short/long/live), Details/topic_categories und Titel-Topics.
Danach `videos_roh.dta` neu exportieren. Bisher enthält die Registry für diese Kanäle **0 Videos
vor 2021** (2021–2026: ~1,09 Mio.).
**Nicht im Umfang:** Transkripte und LLM-Kodierung (`pop_*`/`pos_*`) für 2019–2020. Das ist eine
bewusste Entscheidung des Nutzers und kann später separat entschieden werden.

Nutzen für die Forschungsfragen: längere Vortrends beim Kanalerfolg (FF2, FF4) und eine Phase
vor Corona (2019) als ruhige Referenz.

## Bekannte Grenzen (im Codebuch dokumentieren, nicht „wegrechnen“)
- **2020 ist kein sauberer Vorkriegszeitraum:** Corona hat YouTube-Nutzung und alternative Kanäle
  stark verändert. Der eigentliche Gewinn ist 2019.
- **Survivorship:** YouTube hat 2020/21 viele Corona-Videos gelöscht, und Kanäle stellen alte Videos
  privat. Bei alternativen Kanälen fehlen ältere Videos deshalb systematisch eher.
- **View-Snapshot:** Views sind kumuliert. 2019er-Videos hatten ~7 Jahre Zeit, Views zu sammeln, und
  sie werden zu einem anderen Zeitpunkt abgerufen als der Bestand. Die Registry hat keine
  Spalte mit dem Abrufzeitpunkt. Analysen brauchen also Kanal-FE und eine Alterskontrolle,
  ein Niveauvergleich der Views 2019 vs. 2023 ist nur eingeschränkt aussagekräftig.
- 90 der 437 Sample-Kanäle wurden erst ab 2021 gegründet. Für sie kommt nichts dazu.

## Vorgehen: `channel_video_formats.py` als Hauptweg
`src/youtube_code/step1_sample/channel_video_formats.py` liefert alles in **einem** Durchgang:
- Videos über die Format-Playlists UUSH/UULF/UULV; das liefert zugleich das Format.
- Unbekannte Videos werden mit `fetch_video_metadata_records(detailed=True)` nachgetragen
  (snippet, statistics, contentDetails, status, topicDetails).
- Bei Kanälen mit ≥ 19.500 Uploads greift automatisch yt-dlp.
- Alles-oder-nichts pro Kanal bei Quota-Abbruch.
- Die Statusdatei wird **pro Fenster** geführt, Folgeläufe überspringen `komplett`.

Ein zweiter playlistItems-Durchlauf über `channel_all_videos.py` (TARGETED_SEARCH) entfällt
dadurch. Er läuft nur, wenn der Pilot zeigt, dass die Format-Playlists Videos verlieren (Schritt 3b).

**Quota-Schätzung:** playlistItems beginnt bei den neuesten Videos und muss 2021–2026 nochmal
durchblättern. Das sind ~1,3–1,5 Mio. Einträge / 50 ≈ 26–30k Einheiten. Dazu kommt videos.list
für geschätzt 150–250k neue Videos (≈ 3–5k Einheiten). **Insgesamt ≈ 30–35k Einheiten, also
3–4 Tage** mit einem Key (`API_KEY`, 10k/Tag). yt-dlp kostet kaum Quota, aber Laufzeit.

## Stand (22.10.2026)
- [x] `scripts/adhoc/export_kanalliste_2019_2020.py` ist geschrieben (Konfigurationsblock oben).
  Es schreibt
  - `data/channel_lists/video_formats/sample_2019_2020.csv`: alle `eligible_current_analysis`-Kanäle
    mit `channel_created_at < 2021-01-01`. Whitelist (`sample_whitelist` aus `kanaele_roh.dta`)
    zuerst, dann nach `video_count` aufsteigend. Spalten `fenster_von`/`fenster_bis` =
    `2019-01-01T00:00:00Z`/`2020-12-31T23:59:59Z`.
  - `pilot_2019_2020.csv`: 2 kleine (< 2.000 Uploads), 2 mittlere und 1 großer (≥ 19.500) Kanal,
    Seed 2019.
  - Testlauf auf dem Vorarbeits-Rechner: 347 Kanäle, 230 Whitelist, 16 mit ≥ 19.500 Uploads.
    Pilot dort: Druschba FM, Dr. Bernd Baumann, Schweinfurter Nachrichten, MDR, tvberlin.
- [x] `channel_video_formats.py`: `CHANNEL_INPUT = .../pilot_2019_2020.csv`, `DRY_RUN = True`,
  `PUBLISHED_AFTER = PUBLISHED_BEFORE = None` (das Fenster kommt aus der Liste).
- [x] Vermerk im `step1_sample/README.md` (Hinweise-Abschnitt).
- [ ] Alles ab Schritt 0.

## Schritte

### 0. Auf dem Hauptrechner vorbereiten
- Pullen und prüfen, ob die drei Änderungen oben angekommen sind.
- Prüfen, ob Folgendes vorhanden ist (fehlte auf dem Vorarbeits-Rechner):
  - `outputs/segment_analysis/frage1_kanal_whitelist.csv`
  - in `data/channel_lists/video_formats/`: `sample_russia_longitudinal_v1*.csv`,
    `bsw_kanaele*.csv` und deren `*_formats_status.csv`
  - eine aktuelle `outputs/stata_rohdaten/kanaele_roh.dta`, die neuer ist als der Stand mit
    427 Zeilen ohne `kanaltyp`
- **Die Listen neu erzeugen** (die Registry kann sich unterscheiden):
  `PYTHONPATH=src .venv/Scripts/python.exe scripts/adhoc/export_kanalliste_2019_2020.py`.
  Die Ausgabe (Anzahl Kanäle, Pilotkanäle) mit dem Stand oben vergleichen.
- **Backup** von `data/store/video_registry.sqlite` anlegen, z. B. mit
  `sqlite3 data/store/video_registry.sqlite ".backup _backups/video_registry_vor_2019.sqlite"`.
- **Referenz für den Regressionstest:** die aktuelle `videos_roh.dta`/`kanaele_roh.dta` nach
  `_backups/stata_rohdaten_vor_2019/` kopieren.

### 1. Pilot (vorher den Nutzer fragen: Quota)
1. Der Dry-Run mit `channel_video_formats.py` (Konfiguration steht schon) kostet etwa 1–2k Einheiten
   und schreibt nur den Report `outputs/video_formats/pilot_2019_2020_formats_report_dryrun.md`.
   Ausführen: `cd src/youtube_code/step1_sample && PYTHONPATH=../.. ../../../.venv/Scripts/python.exe channel_video_formats.py`
   (direkt ausführen, siehe README; Pfad zur venv gegebenenfalls anpassen).
2. **Vollständigkeitstest:** Pro Pilotkanal die Upload-Playlist `UU<rest>` im Fenster zählen
   (playlistItems, ohne zu schreiben). Dafür ein kleines Ad-hoc-Skript
   `scripts/adhoc/pilot_2019_2020_vollstaendigkeit.py` schreiben, das `get_channel_videos()` aus
   `channel_all_videos.py` nachbildet, aber nicht importiert, weil der Import einen API-Client baut
   und Dateien lädt. Damit prüfen, ob die Videos aus UU in UULF ∪ UUSH ∪ UULV enthalten sind.
   Für tvberlin geht das nicht, weil UU auf 20k gekappt ist; dort wird der yt-dlp-Pfad bewertet.
   Ergebnis als Markdown in `outputs/video_formats/`.
3. Ist alles plausibel, mit `DRY_RUN = False` wiederholen. Prüfen:
   - Status `komplett` in `pilot_2019_2020_formats_status.csv`
   - neue Videos in `videos` (mit `view_count`, `duration`), `video_details` und `video_format`
     (read-only-Abfrage)
   - Stichprobe von 10 neuen Videos auf youtube.com (Datum, Format)

### 2. Hauptlauf
- a) `CHANNEL_INPUT = .../sample_2019_2020.csv`, `DRY_RUN = False`. Täglich neu starten, bis alle
  Kanäle `komplett` sind. Die Pilotkanäle stehen dann zwar erneut in der Liste, aber in einer
  anderen Statusdatei. Entweder vorher aus der Liste entfernen oder akzeptieren, dass sie ein
  zweites Mal abgefragt werden (~1–2k Einheiten). Danach die Kanäle mit `fehler`/`unvollstaendig`
  nachfassen.
- b) **Nur wenn der Pilot Verluste > 1–2 % zeigt:** `channel_all_videos.py` TARGETED_SEARCH mit dem
  Fenster 2019–2020. Vorher eine Statusdatei/Fortsetzung ergänzen, analog zu
  `append_ytdlp_status`/`load_ytdlp_completed_channels` im selben Skript. Der Modus hat bisher
  keine und bricht bei Quota einfach ab. Außerdem die `no_video_found_<cid>`-Platzhalter
  abschaltbar machen.
- c) Sicherheitsnetz: `metadata_collection.py` mit `CHECK_CHANNELS_MODE = True` und
  `MISSING_METADATA_CHANNEL_INPUT = CHANNEL_LISTS / "video_formats" / "sample_2019_2020.csv"`,
  je einmal mit `DETAILED = False` (fehlende Views) und `DETAILED = True` (fehlende Details).
  Billig, weil nur Lücken abgefragt werden.

### 3. Themen-Relevanz
- `step3_topic_relevance/classify_topic_relevance.py`: `NUR_FEHLENDE = True`, Kanalliste (`channel_path`,
  ~Zeile 72) = `sample_2019_2020.csv`.
- Plausibilitätscheck je Jahr (Trefferquote je Thema): Corona sollte ab 2020 breit treffen,
  `russia_ukraine_war` 2019–2020 nur selten (Krim/Donbass/Nawalny). Ergebnis in den Lauf-Output.

### 4. Lückenprüfung
- `scripts/adhoc/videos_pro_quartal_whitelist.py`: `QUARTAL_START = pd.Period("2019Q1", freq="Q")`,
  die Docstring-Notiz („Registry nur Videos ab 2021“, ~Zeile 37) anpassen.
- Neu laufen lassen und Quartale mit Einbrüchen gegen den API-`video_count` prüfen.
- Kanäle, die vor 2019 gegründet wurden, aber 0 Videos 2019–2020 haben, einzeln ansehen (inaktiv
  oder Datenlücke?).

### 5. Export `step6_auswertung/export_stata_rohdaten.py` (Neu-Export ~40 min: vorher fragen)
- **Bug, der sonst entsteht:** `lade_format_status()` (~Zeile 378) nimmt pro `channel_id` den
  *neuesten* Status über **alle** `*_formats_status.csv`, egal für welches Fenster. Nach dem Lauf
  würde der 2019–2020-Status den 2021–2026-Status überschreiben. Deshalb nach
  `(channel_id, fenster_von, fenster_bis)` auswerten und einen Kanal pro Fenster bewerten,
  z. B. eigene Variable `format_status_2019` oder nur `komplett`, wenn beide Fenster `komplett`
  sind. Im Codebuch festlegen.
- `FORMAT_FENSTER = ("2019-01-01", "2026-07-01")`.
- `VORKRIEG_START = "2021-02-24"` **bleibt** (`sample_vorkrieg` unverändert).
- Kanalgrößen `n_videos` und `erstes_video_ts` würden sich verschieben. **Empfehlung:** die bisherigen
  Definitionen ab 2021 einfrieren (expliziter Filter `published_at >= 2021-01-01`) für die
  Vergleichbarkeit mit bisherigen Ergebnissen. Gegebenenfalls zusätzlich `erstes_video_ts_ab2019`.
  Die Entscheidung mit dem Nutzer abstimmen.
- Neue Konsistenzprüfungen:
  - Videos vor 2021 haben kein `pop_*`/`pos_*` und kein `baseline_stichprobe`.
  - Ins Log: Videos je Jahr und Formatabdeckung je Jahr.
- `post_war`/`monat` sind datumsbasiert und kommen ohne Änderung aus. In `00_aufbereitung.do`
  prüfen, dass `kriegsmonat` jetzt bis ca. −38 reicht und `$FENSTER_START` die bisherigen
  Analysen weiter auf ihr Fenster beschränkt.
- `docs/codebuch_rohdatensatz.md` (Population ab 2019, Abdeckung, die Grenzen oben) und den
  Docstring des Exports anpassen.

### 6. Downstream absichern
- `step2_baseline_channels/activity_phases.py` liest die Upload-Historie aus der Registry. Die
  Videos von 2019–2020 können die Aktivitätsphasen und damit die Baseline-Zuordnung verschieben.
  **Schritt 2 nicht neu laufen lassen.** Falls doch: vorher/nachher vergleichen, ob sich ein
  Baseline-Fenster ändert. Im step2-README vermerken.
- Implizite Annahmen „alles ab 2021“ suchen, Fenster dort explizit halten:
  `prepare_success_metrics.py`, `step8_targeted_analysis/preparation.py` (`FORMAT_WINDOW`),
  `kriegsvideos_zeitreihen_plots.py` (`MONAT_MIN`), `frage4_kriegspraemie_relative_views_plots.py`,
  `schockfenster_bericht.py`, Do-Files `outputs/stata_rohdaten/10_*.do`/`11_*.do`. Suche z. B. mit
  `grep -rn "get_video_stats\|published_at" src/youtube_code/step6_auswertung`.

### 7. Doku
- `COMPLETE_PROCESS.md` Schritt 1: „Daten für ALLE Videos seit dem 24.02.2021“ → Metadaten ab
  2019-01-01, LLM-Analysen weiter ab 2021.
- `step1_sample/README.md`: Lauf-Stand aktualisieren, Hinweis auf den Pilot ersetzen.
- `settings_variables.py`: `published_after_analysis = "2019-01-01T00:00:00Z"`, damit künftige
  NEW_CHANNELS-Läufe (z. B. neue Kanäle) konsistent sind.
- `channel_video_formats.py`: den Kommentar „Bisher (Sample-Listen)“ beim Fenster ergänzen, nach
  dem Lauf `DRY_RUN` wieder auf `False` setzen.

## Verifikation
1. Pilot: UU vs. Format-Playlists je Kanal, Stichprobe von 10 Videos, Einträge in allen drei
   Tabellen.
2. Hauptlauf: Videos je Jahr und Kanal (read-only), Quartalsscreening ohne neue Lücken, alle
   Kanäle `komplett`.
3. **Regressionstest Export (am wichtigsten):** alle Checks in `export_log.txt` grün,
   `check_rohdaten.do` läuft. Auf den Videos ab 2021 sind Fallzahlen, `pop_baseline`,
   `sample_vorkrieg`, `n_videos` und `format`-Verteilung **identisch** zur Referenz-Kopie aus
   Schritt 0. Kleines Vergleichsskript in `scripts/adhoc/`, Ergebnis als Markdown.

## Rückfragen-Pflichten (CLAUDE.md)
- Vor jedem API-Lauf (Pilot, Hauptlauf) und vor dem Export (~40 min) den Nutzer fragen.
- Nach Schritt 5 darauf hinweisen, dass `videos_roh.dta` neu ist und die bisherigen
  Stata-Ergebnisse auf Fensterfilter geprüft werden sollten.

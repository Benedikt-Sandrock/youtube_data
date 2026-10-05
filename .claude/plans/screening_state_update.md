# Screening-State an Registry angleichen + Duplikat-Spalten entfernen

## Kontext

`scripts/adhoc/sample_creation_diagnostics.py` zeigte, dass die Video-Anzahl je
Kanal in `screening_state` (SQLite, `src/youtube_code/store/screening_state_store.py`)
fast durchweg von der Anzahl in `video_registry` (SQLite,
`src/youtube_code/store/video_registry.py`) abweicht. Diagnose ergab zwei
Ursachen:

1. **Eingefrorener Snapshot vs. wachsende Registry**: `screening_state` wurde
   einmalig aus einem JSON-Snapshot initialisiert
   (`src/youtube_code/archive/politics_screening_legacy/prepare_longitudinal_screening.py`)
   und nie erneut aus der Registry aufgebaut. `video_registry` wird dagegen
   laufend von `metadata_collection.py` weiter befüllt. Betrifft praktisch
   alle 292 Kanäle, am stärksten upload-starke News-Kanäle (WELT: +3489
   Video-IDs, phoenix: +2017, ZDFheute: +1640, ...).
2. **`channel_id`-Drift**: Bei einer Handvoll Kanäle (RTL: -21, DIE
   BLITZMELDUNG: -11, DER GLÜCKSRITTER: -9, Real Stories Deutschland: -1)
   wurde die `channel_id` einzelner Videos in der Registry nachträglich
   korrigiert (z.B. RTL-Videos gehören jetzt laut Registry zu "RTL Soap
   Classics", `UCMV91VRyrPWMyy7H2smNYsw`), der State hält aber weiter die
   alte `channel_id`.

Zusätzlich dupliziert `screening_state` die Spalten `channel_title`,
`published_at`, `title`, `description` aus `video_registry` als eigene
Kopie zum Zeitpunkt der Kandidatenauswahl - dieselbe Bug-Klasse wie der
`channel_id`-Drift (Kopie veraltet, Original in der Registry ändert sich
weiter). Deshalb werden diese vier Spalten entfernt und stattdessen bei
Bedarf per `video_id`-Join aus `video_registry` nachgeladen.

**Vom Nutzer bereits getroffene Entscheidungen:**
- State soll um die in der Registry vorhandenen, aber im State fehlenden
  Videos ergänzt werden (nicht nur für neue Kanäle wie bisher, sondern auch
  für längst im State stehende Kanäle).
- Der Sync soll künftig automatisch bei jeder neuen Screening-Runde laufen
  (`create_screening_round()`), nicht nur manuell.
- Duplikat-Spalten (`channel_title`, `published_at`, `title`, `description`)
  werden aus `screening_state` entfernt; Konsumenten joinen bei Bedarf gegen
  `video_registry`.
- `channel_id`-Drift bei bereits vorhandenen State-Zeilen wird automatisch
  auf den aktuellen Registry-Stand korrigiert.
- Der Sync-Lauf muss einen Überblick liefern, welche `video_id`s pro Kanal
  und Zeitraum ergänzt/korrigiert wurden (um z.B. zu erkennen, ob nur ein
  bestimmter Zeitraum fehlt).

## Schritt 1: Schema-Refactor `screening_state_store.py`

- `COLUMNS`/`_SCHEMA`/`_UPDATE_CLAUSE` in
  `src/youtube_code/store/screening_state_store.py` um `channel_title`,
  `published_at`, `title`, `description` kürzen.
- Neue Funktion `get_state_with_text(...)` (gleiche Filterparameter wie
  `get_state()`) ergänzen: ruft intern `get_state()` auf und joint das
  Ergebnis per `video_id` gegen
  `video_registry.get_videos_with_text(video_ids=..., min_duration_seconds=None)`
  (⚠️ `min_duration_seconds=None` ist zwingend, sonst verschwinden bereits
  ausgewählte Kandidaten mit unbekannter/kurzer Dauer stillschweigend aus dem
  Join). Damit müssen die vier Konsumenten unten den Join nicht jeweils neu
  bauen.
- Modul-Docstring entsprechend aktualisieren.

**Migration der bestehenden SQLite-Datei** (einmalig, daher nach Projektregel
in `scripts/adhoc/`, analog zu den bestehenden `migrate_*_to_store.py`-
Skripten): neues Skript `scripts/adhoc/drop_screening_state_text_columns.py`,
das vor dem `ALTER TABLE screening_state DROP COLUMN ...` (SQLite ≥3.35,
lokal 3.42 vorhanden) einen Backup-Export via
`screening_state_store.export_csv()` schreibt.

## Schritt 2: Konsumenten auf Join umstellen

Laut Recherche schreibt **keine** Stelle diese vier Spalten in den Store
zurück - überall reiner Lesezugriff, daher überall unkritisch ersetzbar:

- `src/youtube_code/step2_baseline_channels/longitudinal/create_longitudinal_screening.py`:
  `load_screening_state()` auf `get_state_with_text()` umstellen (Join muss
  VOR dem Leerstring-Filter, Zeile 306, und der Sortierung nach
  `published_at`, Zeile 310, passieren, da `title`/`published_at`/
  `description` 1:1 in `screening_round_XXX_title_candidates.csv` geschrieben
  werden - das ist der LLM-Input). `REQUIRED_COLUMNS` und
  `validate_state_consistency()` entsprechend anpassen.
- `src/youtube_code/step2_baseline_channels/longitudinal/update_screening_state.py`:
  `load_state()`/`STATE_REQUIRED_COLUMNS` analog anpassen; vor dem Export der
  `description_candidates`-CSV (Prompt-33-Input) ebenfalls
  `get_state_with_text()` verwenden.
- `src/youtube_code/step2_baseline_channels/assign_postwar_baseline.py`:
  `state["published_at"]`-Parsing durch Join über `get_state_with_text()`
  ersetzen - behebt nebenbei den dort bereits dokumentierten
  `published_at`-Inkonsistenz-Bug.
- `src/youtube_code/step4_transcript_download/select_targets.py`
  (`select_baseline_targets`): `published_at` für die Sortierung ebenfalls
  über `get_state_with_text()` beziehen.
- `scripts/adhoc/check_min_duration_violations.py`: `extra_cols` für
  `channel_title`/`title` per Join befüllen (reiner Debug-Report).
- `scripts/adhoc/archive_short_screening_state.py`: `_ARCHIVE_SCHEMA` bleibt
  bewusst **mit** den vier Text-Spalten bestehen (dauerhafter Snapshot für
  Videos, die aus der weiteren Verarbeitung ausscheiden) - die
  `INSERT`-Logik wird so angepasst, dass sie die Werte per Join aus
  `video_registry` statt aus dem (jetzt schlankeren) State-DataFrame zieht.
- `src/youtube_code/step2_baseline_channels/append_channels_to_state.py`:
  kein Codechange nötig (Spaltenfilter `c in state.columns` passt sich
  automatisch an) - wird in Schritt 3 ohnehin überarbeitet.

## Schritt 3: Sync-Funktion verallgemeinern (fehlende Videos + channel_id-Drift)

`src/youtube_code/step2_baseline_channels/append_channels_to_state.py`
umbauen (Datei/Modul bleibt, Zweck erweitert sich von "neue Kanäle" auf
"State mit Registry synchronisieren"):

- Bugfix der falschen Annahme in Zeile 95-97 (`nur_baseline_maske`): für
  Kanäle, die schon im State stehen, wurden bisher alle Kriegsperioden-Videos
  verworfen ("schon im State" wurde fälschlich als vollständig angenommen).
  Neue Logik: für **jeden** Zielkanal `neue video_ids = video_registry-IDs
  (nach `INTERVAL_START`-Filter) MINUS bereits im State vorhandene
  video_ids` - unabhängig vom Vorzeichen der `period`.
- Neue Zeilen erhalten `interval_index`/`interval_label`/`rank_within_period`/
  `candidate_rank` über die bestehenden, bereits wiederverwendbaren
  Funktionen aus `src/youtube_code/step2_baseline_channels/interval_assignment.py`
  (`assign_intervals`, `stable_random_key`) - gleiche Logik wie bisher.
- **channel_id-Drift-Korrektur**: für video_ids, die bereits im State stehen,
  aber deren `video_registry`-`channel_id` von der State-`channel_id`
  abweicht, wird ein gezieltes `upsert_state_rows()` mit der aktuellen
  `channel_id` geschrieben (COALESCE-Update-Pattern übernimmt automatisch
  den neuen, nicht-NULL-Wert).
- **Report-Ausgabe** (neu, ergänzt die bestehende Konsolen-Ausgabe): zwei
  CSVs in einem neuen Verzeichnis (Konstante `STATE_SYNC_LOG_DIR` in
  `screening_config.py`, z.B. `SCREENING_DIR / "state_sync_logs"`):
  - Detail-CSV: alle neu ergänzten `video_id`s mit `channel_id`,
    `channel_title`, `published_at`, `period`, `interval_index`,
    `interval_label`.
  - Summary-CSV: gruppiert nach `channel_id`+`interval_label`, mit Anzahl
    sowie `published_at`-Min/Max je Gruppe (damit erkennbar ist, ob die
    Lücke auf einen bestimmten Zeitraum konzentriert ist).
  - Dritte CSV nur bei Korrekturen: `video_id`, alte `channel_id`, neue
    `channel_id`, `channel_title`.
- Bekannte, hier bewusst nicht behobene Einschränkung: `candidate_rank` wird
  für neu angehängte Zeilen wie bisher pro Batch neu ab 0 vergeben und kann
  daher mit bereits vorhandenen `candidate_rank`-Werten im selben
  Kanal-Intervall kollidieren (nur Sortier-Tiebreaker, keine Unique-
  Constraint - bestand schon vor diesem Fix genauso).

## Schritt 4: Automatische Einbindung in `create_screening_round()`

In `src/youtube_code/step2_baseline_channels/longitudinal/create_longitudinal_screening.py::create_screening_round()`
wird der Sync aus Schritt 3 für alle aktuell im State vorkommenden
`channel_id`s **vor** `load_screening_state()` aufgerufen, Report-Pfade und
-Zusammenfassung werden mit ausgegeben. Der bestehende `DRY_RUN`-Schalter
gilt auch für den Sync (kein Schreiben, nur Report-Vorschau).

## Schritt 5: Doku aktualisieren

Docstrings/READMEs, die auf die geänderte Struktur Bezug nehmen, anpassen
(Projektregel): `screening_state_store.py`-Moduldocstring,
`append_channels_to_state.py`-Moduldocstring, `step2_baseline_channels/README.md`,
`create_longitudinal_screening.py`-Moduldocstring (neuer automatischer
Sync-Schritt).

## Schritt 6: Verifikation & Rollout

1. Nach Schema-Migration: `screening_state_store.total_count()`/
   `round_counts()`/`label_counts()` als Sanity-Check, sowie
   `create_longitudinal_screening.load_screening_state()` (nur lesend, ruft
   `validate_state_consistency()` auf) probeweise ausführen.
2. `create_longitudinal_screening.py` einmal mit `DRY_RUN=True` laufen
   lassen und die Konsolen-Vorschau (Titel, Kandidatenzahlen) mit dem Stand
   vor dem Refactor vergleichen.
3. Sync-Funktion aus Schritt 3 zunächst im **Dry-Run** für alle 292 Kanäle
   aus `channel_sample_provenance.csv` laufen lassen, Report gemeinsam mit
   dem Nutzer durchsehen (Überblick über neue Video-IDs/Korrekturen nach
   Kanal und Zeitraum).
4. **Erst nach ausdrücklicher Freigabe des Nutzers** (Projektregel: Testläufe
   vorher genehmigen lassen) den echten Sync-Lauf für alle 292 Kanäle
   ausführen, der den aktuellen Rückstand aufholt.
5. `sample_creation_diagnostics.py` erneut laufen lassen zur Bestätigung,
   dass `all_vids` und `all_vids_state` danach übereinstimmen.

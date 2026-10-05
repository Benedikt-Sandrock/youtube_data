# Baseline-Fensterzuweisung: Umstellung auf Aktivitätsphasen

Stand: 2026-09-03. Diese Datei fasst eine abgeschlossene Diskussions- und
Code-Session zusammen, damit in einer neuen Session direkt weitergearbeitet
werden kann.

## Ausgangsproblem

Die Baseline-Fensterzuweisung (siehe `src/youtube_code/step2_baseline_channels/README.md`
Abschnitt 1) unterschied Vorkriegs- vs. Nachkriegskanäle bisher allein anhand
von `channel_created_at` (Kanal-Gründungsdatum). Das versagt bei Kanälen mit
langen Aktivitätslücken:

- **Reaktivierte Kanäle**: alt, aber ursprüngliche Aktivität eingestellt und
  erst Jahre später — teils erst nach Kriegsbeginn — wieder aufgenommen.
  Wurden fälschlich als "vorkriegskanal" behandelt und bekamen ein leeres
  Vorkriegsfenster.
- **Verzögert gestartete Nachkriegskanäle**: nach Kriegsbeginn gegründet,
  aber erste Videos erst Jahre nach der Gründung hochgeladen (vom Nutzer
  während der Session als Zusatzfall genannt). `assign_postwar_baseline.py`
  setzte den Fensteranfang bisher auf `channel_created_at` — dort lagen dann
  ebenfalls keine Kandidaten.

## Nutzerentscheidungen aus der Diskussion

- Kanäle, deren letzte Aktivität schon vor Kriegsbeginn beendet war und die
  seither nie wieder aktiv wurden ("tot_zum_kriegsbeginn"): **ausschließen**,
  nicht künstlich ein Fenster erzwingen.
- Anchor für Ersatzfenster: **Beginn der tatsächlichen Aktivitätsphase**
  (nicht Kriegsbeginn selbst als fixer Anchor).
- Priorität bei Tradeoffs: **möglichst viele Kanäle retten** (Datenmenge
  maximieren) wichtiger als strikte zeitliche Nähe zum Kriegsbeginn.

## Was umgesetzt wurde

### Neues Modul: `src/youtube_code/step2_baseline_channels/activity_phases.py`

Zentrale, wiederverwendbare Logik (Docstring dort enthält die vollständige
Herleitung):

- `find_activity_phases(dates, gap_threshold_months=12)`: segmentiert die
  chronologisch sortierten Upload-Daten eines Kanals in zusammenhängende
  Aktivitätsphasen (Lücke ≥ 12 Monate = neue Phase).
- `classify_channel_activity(channel_created_at, phases)`: ordnet einen
  Kanal einer von 7 Kategorien zu und bestimmt den `anchor_date`:
  - `aktivitaet_deckt_kriegsbeginn` → `war_group="vorkriegskanal"`, globales
    Fenster greift (Normalfall, unproblematisch).
  - `reaktiviert_faelschlich_vorkrieg` → `war_group="nachkriegskanal"`,
    Anchor = Beginn der ersten Phase nach Kriegsbeginn.
  - `nachkrieg_verzoegerter_start` → `war_group="nachkriegskanal"`, Anchor =
    Beginn der ersten Phase (Lücke zu `channel_created_at` ≥ 12 Monate).
  - `nachkrieg_konsistent` → `war_group="nachkriegskanal"`, Anchor ≈
    `channel_created_at` (Normalfall für neu gegründete Kanäle).
  - `tot_zum_kriegsbeginn`, `nachkrieg_keine_aktivitaet`,
    `keine_videos_bekannt` → `war_group="ausgeschlossen"`.
- `classify_channels_bulk(channels, uploads)`: vektorisiertes Frontend für
  mehrere Kanäle gleichzeitig.

### `assign_postwar_baseline.py` umgebaut

- Kandidatenkriterium: `war_group == "nachkriegskanal"` (statt
  `channel_created_at ≥ Kriegsbeginn`) — deckt jetzt auch reaktivierte und
  verzögert gestartete Kanäle in der **gesamten** `video_registry` ab
  (is_german + ≥50k Abos), nicht nur die alten "echten" Postwar-Kanäle.
- Fensteranfang: `anchor_date` aus `activity_phases` statt
  `channel_created_at`.
- `interval_label` kodiert die Kategorie mit: `postwar_new_0_to_N` /
  `postwar_reactivated_0_to_N` / `postwar_delayed_0_to_N` (Präfix-Mapping in
  `LABEL_PREFIX_BY_KATEGORIE`) — rückwärtskompatibel zu alten
  `postwar_0_to_N`-Zeilen ohne Suffix, damit spätere Auswertungen (Schritt 6)
  bei Bedarf Robustheitschecks mit/ohne reaktivierte bzw. verzögerte Kanäle
  fahren können.
- **`DRY_RUN = True` ist jetzt der Default** (vorher `False`) — bewusste
  Sicherheitsänderung, damit ein versehentlicher Lauf nach der
  Logikumstellung nicht sofort in den State schreibt.

### `check_baseline_availability.py` umgebaut

- `load_channels()` liefert jetzt nur Rohdaten; neue Funktion
  `classify_war_groups(channels, all_videos)` hängt die
  Aktivitätsphasen-Klassifikation an (`kategorie`, `war_group`,
  `anchor_date`).
- `compute_available_video_counts()`: Postwar-Zweig nutzt `anchor_date`
  statt `channel_created_at` als Fensteranfang; Regex für `fenster_monate`
  generalisiert auf `_0_to_(\d+)$` (matcht alle drei neuen Label-Präfixe).
- Gruppe "unbekannt" umbenannt in "ausgeschlossen" (deckt jetzt auch
  `tot_zum_kriegsbeginn` etc. ab, nicht nur fehlende Metadaten).

### Diagnoseskript: `scripts/adhoc/diagnose_reactivated_baseline_channels.py`

Ursprünglich hier die Logik entwickelt, jetzt auf `activity_phases.py`
refaktoriert (reine Reporting-Schicht, keine Duplikation mehr). Schreibt
`scripts/adhoc/output/reactivated_baseline_channels_diagnosis.csv`.

### READMEs aktualisiert

- `src/youtube_code/step2_baseline_channels/README.md` Abschnitt 1: neue
  Aktivitätsphasen-Logik dokumentiert; dabei auch veraltete `longitudinal/`-
  Pfadangaben korrigiert, die schon vorher falsch waren (`append_channels_to_state.py`,
  `assign_postwar_baseline.py`, `interval_assignment.py`, `activity_phases.py`
  liegen direkt in `step2_baseline_channels/`, nicht in `longitudinal/`).
- `COMPLETE_PROCESS.md` Abschnitt 2 entsprechend angepasst.

## Testergebnisse (nur Lesezugriffe, `screening_state.sqlite` unverändert)

**Diagnose über die 427 Sample-Kanäle** (`build_channel_provenance`-Output,
`data/samples/russia_longitudinal_v1/channel_sample_provenance.csv`):

| Kategorie | Anzahl |
|---|---:|
| `aktivitaet_deckt_kriegsbeginn` (unproblematisch) | 334 |
| `nachkrieg_konsistent` (unproblematisch) | 53 |
| `reaktiviert_faelschlich_vorkrieg` (Hauptproblem) | 36 |
| `nachkrieg_verzoegerter_start` | 4 |
| `tot_zum_kriegsbeginn` | 0 |

→ 40 von 427 Kanälen (9,4 %) betroffen, darunter zentrale Kanäle wie Tim
Kellner, Florian Schroeder, Apollo News, funk.

**`check_baseline_availability.py`** (aktualisierte Version): 334
vorkriegskanal / 93 nachkriegskanal / 0 ausgeschlossen.

**`assign_postwar_baseline.py`** (Dry-Run, registry-weiter Kandidatenpool
von 620 is_german+≥50k-Abos-Kanälen): 284 Kandidaten (201 reaktiviert, 77
konsistent neu, 6 verzögert). Davon:
- 69 Kanäle haben schon ausreichend (≥12) Kandidatenzeilen im neuen Fenster
  im State.
- 10 Kanäle haben >0, aber zu wenige Kandidaten.
- **205 Kanäle haben noch gar keine Kandidatenzeilen im neuen Fenster** —
  für die reicht das reine Umlabeln nicht, siehe nächste Schritte.

## Was NICHT gemacht wurde

`data/store/screening_state.sqlite` wurde bewusst **nicht** verändert — nur
Code-Änderungen, keine Schreiboperationen. Das war eine explizite
Nutzervorgabe während der Session.

## Nachtrag (gleicher Tag): Fensterwahl-Kriterium geklärt und angepasst

Nutzerfrage: Wird die Fensterlänge (3→6→9→12 Monate) in
`assign_postwar_baseline.py` schon anhand der bloßen Video-Anzahl bestimmt,
oder erst nach der Klassifikation dynamisch anhand der Anzahl gefundener
politischer Videos erweitert?

Antwort/Befund: Die Fensterlänge wird **vor** der Klassifikation rein anhand
der rohen Kandidatenzeilen-Anzahl im State bestimmt (`politics_final` ist zu
diesem Zeitpunkt für die meisten Kandidaten noch leer). Eine echte,
politik-ratenbasierte Nachsteuerung existiert im Projekt bereits, aber an
anderer Stelle: `longitudinal/create_longitudinal_screening.py`
(`plan_screening_round()`) zieht pro Screening-Runde anhand der beobachteten
Politik-Trefferquote (`POLITICAL_RATE_FLOOR`, `ROUND_SAFETY_FACTOR`) mehr
Kandidaten nach — aber nur *innerhalb* eines bereits fixen Kalenderfensters,
nicht durch Verlängerung des Fensters selbst.

Nutzerentscheidung: Rohe-Anzahl-Kriterium für die Fensterwahl beibehalten,
aber den Schwellenwert von 12 auf **30** erhöhen (mehr Puffer, falls viele
der rohen Kandidaten später unpolitisch klassifiziert werden). Umgesetzt:

- Neue Konstante `WINDOW_RAW_CANDIDATE_TARGET = 30` in
  `assign_postwar_baseline.py`, getrennt von `TARGET_WITH_BUFFER_PER_INTERVAL`
  (bleibt bei 12 — das ist weiterhin das an `create_longitudinal_screening.py`
  weitergereichte Rundenplanungsziel, unverändert).
- Fensterwahl-Schleife (`assign_postwar_intervals()`) nutzt jetzt
  `WINDOW_RAW_CANDIDATE_TARGET` statt `TARGET_WITH_BUFFER_PER_INTERVAL` als
  Abbruchkriterium.
- Modul-Docstring, Konstanten-Kommentar, Print-Ausgaben in `main()` und
  `README.md` Abschnitt 1b entsprechend angepasst.
- **Noch nicht erneut getestet** — die in diesem Dokument oben dokumentierten
  Testergebnisse (69/10/205-Aufteilung) stammen noch vom alten
  12er-Schwellenwert und müssen vor Schritt 2/3 unten mit dem neuen
  Schwellenwert (30) neu erzeugt werden (`DRY_RUN=True`-Lauf).

## Nachtrag (gleicher Tag): Bug beim ersten echten Schreiblauf gefunden und behoben

Nutzer hat Schritt 1 (Backup) bereits durchgeführt
(`data/store/screening_state.sqlite.bak_activity_phases_umstellung`
existiert) und dann `assign_postwar_baseline.py` direkt mit `DRY_RUN=False`
laufen lassen. Ergebnis: `sqlite3.IntegrityError: NOT NULL constraint
failed: screening_state.channel_id`.

Ursache (vorbestehender Bug, nicht durch die 12→30-Umstellung verursacht):
Der Schreib-Block in `main()` baute `changed` nur aus den Spalten
`video_id, interval_index, interval_label, target_political_per_interval,
target_with_buffer_per_interval` — **ohne `channel_id`**. Da
`screening_state_store.upsert_state_rows()` fehlende Spalten als `None`
interpretiert, versuchte der `INSERT ... ON CONFLICT(video_id) DO UPDATE`
mit `channel_id = NULL`. SQLite prüft NOT-NULL-Constraints auf Spalten, die
nicht Teil des Conflict-Targets sind, bereits beim Aufbau der einzufügenden
Zeile — bevor der PK-Konflikt zum UPDATE-Zweig führt. Der komplette Batch
schlug daher fehl, obwohl inhaltlich nur bestehende Zeilen aktualisiert
werden sollten.

Verifiziert: `screening_state.sqlite` und das Backup sind byteidentisch
(MD5-Hash gleich) — der fehlgeschlagene Lauf hat **nichts** geschrieben,
kein Datenverlust.

Fix: `channel_id` zur Spaltenliste von `changed` in `assign_postwar_baseline.py`
hinzugefügt. Modul-Docstring entsprechend ergänzt.

## Nachtrag (gleicher Tag): Echter Schreiblauf erfolgreich durchgeführt

Nutzer hat `assign_postwar_baseline.py` mit dem Fix erneut mit `DRY_RUN=False`
laufen lassen — **diesmal erfolgreich**. Verifiziert (nur Lesezugriff):

- `screening_state.sqlite` hat jetzt 4.702 Zeilen mit `interval_index = -1`
  (vorher 1.678 — Differenz von 3.024 Zeilen stammt aus diesem Lauf).
- `interval_label`-Verteilung der neuen Zeilen enthält die erwarteten neuen
  Präfixe (`postwar_new_0_to_*`, `postwar_reactivated_0_to_*`,
  `postwar_delayed_0_to_*`) sowie unveränderte alte `postwar_0_to_*`-Zeilen
  ohne Suffix (rückwärtskompatibel, wie im Modul-Docstring beschrieben).

Die Aktivitätsphasen-Umstellung (Kernziel dieses Plandokuments) ist damit
inhaltlich abgeschlossen. Backup
(`data/store/screening_state.sqlite.bak_activity_phases_umstellung`) bleibt
als Wiederherstellungspunkt vor der Umstellung bestehen.

## Nachtrag (gleicher Tag): Neuer Fokus — Mindestanzahl Topic-Videos pro Kanal

Nutzervorgabe für die nächsten Schritte: Der weitere Fokus soll auf Kanälen
liegen, die **mindestens 5 Topic-Videos** (relevante Videos zum Thema
Russland/Ukraine-Krieg) hochgeladen haben — Kanäle mit weniger Topic-Videos
sind für die weitere Bearbeitung erstmal nachrangig.

Dafür existiert bereits ein Diagnose-Skript: `scripts/adhoc/sample_creation_diagnostics.py`.
Es lädt die Kanäle aus
`data/samples/russia_longitudinal_v1/channel_sample_provenance.csv`, holt
deren Video-Metadaten (`video_registry.get_video_metadata`), markiert Videos
als relevant über `video_registry.topic_relevant_video_ids("russia_ukraine_war")`,
aggregiert die Anzahl relevanter Videos pro Kanal und schreibt das Ergebnis
nach `scripts/adhoc/output/topic_vids_per_channel.csv` (Spalten: `channel_id`,
`channel_title`, `is_relevant` = Anzahl Topic-Videos je Kanal). Es druckt
außerdem, welche Kanal-IDs zwischen Sample-Liste und Video-Metadaten
abweichen (`Dropped IDs` / `Added IDs`).

## Nachtrag (2026-09-03, neue Session): Datumsformat-Bug in `assign_postwar_intervals()` gefunden und behoben

Nutzerfrage zum bereits durchgefuehrten Schreiblauf: Fuer den Kanal "Alexander
Raue Klartext" (erste Videos ab 28.02.2024) stand `interval_index` im State
weiterhin auf `12` (normales Kalenderintervall `24_to_26`, d.h. Monate 24-26
nach Kriegsbeginn) statt auf dem erwarteten Sentinel `-1`.

Diagnose (nur Lesezugriffe): Der Kanal wird von `load_postwar_candidate_channels()`
korrekt als Kandidat erkannt (`kategorie="nachkrieg_verzoegerter_start"`,
Anchor = 2024-02-28 01:46:52, passend zu `activity_phases.classify_channel_activity`).
`assign_postwar_intervals()` fand aber in **jeder** Fenstergroesse (3/6/9/12
Monate) null Treffer fuer diesen Kanal, obwohl 91+ Zeilen im ersten 3-Monats-
Fenster liegen.

Ursache: `state["published_at_dt"] = pd.to_datetime(state["published_at"],
errors="coerce", utc=True)` (ohne `format=`) in `assign_postwar_intervals()`.
`screening_state.sqlite.published_at` enthaelt zwei unterschiedliche
ISO8601-Schreibweisen, je nach Schreibpfad:

- `YYYY-MM-DDTHH:MM:SSZ` (725.132 Zeilen, Mehrheit)
- `YYYY-MM-DD HH:MM:SS+00:00` (14.741 Zeilen, Minderheit)

Ohne explizites `format` leitet pandas ein einziges Format fuer die gesamte
Spalte ab; jede Zeile, die nicht dazu passt, wird mit `errors="coerce"` zu
`NaT`. Alle 319 Zeilen von "Alexander Raue Klartext" liegen im Minderheits-
format -> wurden komplett zu `NaT` -> der Fenster-Filter
(`published_at_dt >= erstellt`) fand nie einen Treffer, obwohl die
Klassifikation korrekt war. Alle anderen `pd.to_datetime`-Aufrufe im selben
Modul (Zeile 145, 160) sowie in `check_baseline_availability.py` uebergeben
bereits `format="ISO8601"` - nur dieser eine Aufruf nicht.

Umfang quantifiziert (Nachstellung des bereits durchgefuehrten Schreiblaufs
vs. gefixte Variante, nur Lesezugriffe): Von den 284 Kandidatenkanaelen sind
**2 vollstaendig durch den Bug durchgefallen** (0 statt korrekt gefundener
Kandidatenzeilen):

- `UCair4tGwkIovC3UQlkc3-zQ` - Alexander Raue Klartext (94 Zeilen betroffen)
- `UC94WBmb8xvVUcV_b9Px0P3A` - Wieder Zensiert - Alles Ausser Mainstream
  Boschimo (33 Zeilen betroffen)

Zusammen 127 Zeilen, die im bereits geschriebenen State weiterhin ihr altes
Kalender-`interval_index` haben statt `-1` (State hat aktuell 4.702 Zeilen
mit `interval_index=-1`, mit Fix waeren es 4.829).

Fix: `format="ISO8601"` zum `pd.to_datetime()`-Aufruf in
`assign_postwar_intervals()` ergaenzt (`assign_postwar_baseline.py:192-201`),
inkl. erklaerendem Kommentar. **Noch kein erneuter Lauf durchgefuehrt** -
Nutzervorgabe war ausdruecklich nur den Fix einzubauen, `screening_state.sqlite`
bleibt unveraendert.

## Nächste Schritte

0. **Erneuter Schreiblauf mit dem Datumsformat-Fix** (siehe Nachtrag oben):
   `DRY_RUN=True`-Vorschau gegenprüfen (erwartet: 4.829 statt 4.702 Zeilen mit
   `interval_index=-1`, 2 zusätzliche Kandidatenkanäle), dann nach
   Nutzerfreigabe Backup + `DRY_RUN=False`-Lauf wie beim vorherigen
   Schreiblauf.
1. **`sample_creation_diagnostics.py` laufen lassen** (falls der Output noch
   nicht mit dem aktuellen State übereinstimmt) und
   `scripts/adhoc/output/topic_vids_per_channel.csv` nach Kanälen mit
   `is_relevant >= 5` filtern — das ist ab jetzt die Zielgruppe für die
   folgenden Schritte.
2. **Downstream-Skripte auf diesen Fokus einschränken**: prüfen, wo im
   weiteren Verlauf (Screening-Runden, Baseline-Zuweisung, Auswertung) eine
   Filterung auf die `>=5`-Topic-Video-Kanäle sinnvoll ergänzt werden sollte,
   statt weiter mit dem vollen Sample zu arbeiten.
3. **Downstream prüfen**: `select_baseline_targets()`
   (`step4_transcript_download/select_targets.py`) filtert nur über
   `interval_index == -1`, kein Label-Parsing nötig — sollte ohne weitere
   Änderung funktionieren, aber im Lichte des neuen `>=5`-Topic-Video-Fokus
   einmal gegenprüfen, ob/wo diese Einschränkung mit einfließen muss.
4. **Optional, nicht dringend**: Der durch die Aktivitätsphasen-Umstellung
   entstandene, deutlich breitere Kandidatenpool bedeutet mehr
   Video-Nachdownload-Aufwand als ursprünglich erwartet — jetzt zusätzlich
   zu betrachten im Licht des neuen `>=5`-Topic-Video-Fokus (Kanäle unter
   dieser Schwelle müssen ggf. gar nicht erst nachbearbeitet werden).

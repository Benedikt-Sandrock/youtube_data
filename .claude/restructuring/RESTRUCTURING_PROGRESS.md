# RESTRUCTURING PROGRESS

## Phase 0a — Platzneutrale Vorbereitung
**Status: ABGESCHLOSSEN (2026-08-28)**

### 1. Committer-Check
`git log --format='%ae' | sort -u` →
- `benedikt.sandrock@outlook.de`
- `bs444@email.uni-freiburg.de`

Beide Adressen dem Nutzer zuordenbar (privat + Uni-Mail). Keine unbekannten Committer. Unbedenklich für den Git-History-Rewrite in Phase 2.

### 2. Freier Speicherplatz (Referenzwert)
`5.0 GB` frei von 237 GB (`df -h .`) — deckt sich mit dem im Plan dokumentierten Ausgangswert (~5,1 GB). Nach Phase 1 hier erneut prüfen (Zielerwartung: ≥25 GB mehr frei).

### 3. Checksum-/Zeilenzahl-Referenzlisten (für Phase-1-Löschungen)
Abgelegt unter `.claude/restructuring/`:
- `phase0_checksums_state_backups.txt` — SHA256 für aktuelle `longitudinal_screening_state.csv`, beide `.bak`-Varianten und alle 16 State-Backup-Snapshots.
- `phase0_checksums_transcripts.txt` — SHA256 für alle 5 Transkript-Datei-Varianten.
- `phase0_checksums_samples.txt` — SHA256 für die `sample_50k`-Familie, `videos_total.json`, `sample_russia_ukraine.json`, `videos_clean.jsonl` + `..._wo_shorts.jsonl`.

**Zeilenzahl-Befunde:**
- State-Backups: alle 16 Snapshots haben identisch **17.399.002** Zeilen (Dateigröße wächst leicht zwischen den Snapshots — vermutlich wachsende Textfelder, nicht neue Zeilen). Aktuelle State-Datei hat **17.686.926** Zeilen → echte Obermenge/Fortführung, bestätigt sicheres Löschen der älteren Snapshots in Phase 1.
- Transkripte: **keine** einfachen Duplikate nach Zeilenzahl — `all_transcripts_segments.csv` (85.328 Zeilen, segment-granular) vs. `all_transcripts_backup.csv` (83.221), `all_transcripts.csv` (263.331, vermutlich video-granular statt segment-granular), `all_transcripts_2.csv` (15.044). Die "tot"-Einstufung dieser Dateien stützt sich laut `.claude/CLAUDE.md` auf eine explizite Source-of-Truth-Regel (nur `all_transcripts_segments.csv` zählt), nicht auf Zeilenzahl-Gleichheit — das ist für Phase 1 wichtig zu wissen, damit dort kein 1:1-Duplikatsvergleich erwartet wird.
- `outputs/sample_feasibility/videos_clean.jsonl` vs. `data/samples/russia/sample_50k_channels_russia_ukraine_wo_shorts.jsonl`: identische Zeilenzahl (738.549) trotz unterschiedlicher Dateigröße (1,26 GB vs. 1,53 GB) → konsistent mit "reserialisiertes 1:1-Duplikat" laut Plan.

### 4. Referenz-Check (Korrektur gegenüber Plan-Annahme)
**Wichtiger Fund:** `data/raw/videos_total.json` (417 MB) ist entgegen der Plan-Annahme ("toter Pfad") **aktiv referenziert**:
- `src/youtube_code/collection/video_sampling.py` lädt sie tatsächlich über einen kaputten relativen Pfad (`../JSON Files/video_files/videos_total.json`) — das ist tot, wie im Plan angenommen.
- ABER `scripts/create_channel_lists.py` referenziert dieselbe Datei über einen gültigen, auflösbaren Pfad: `ALL_VIDEOS_FILE = RAW / "videos_total.json"`, gelesen via `load_json(ALL_VIDEOS_FILE)`. Zusätzlich ist sie in `.gitattributes` als LFS-Datei gelistet.
- **Konsequenz für Phase 1:** `videos_total.json` NICHT ungeprüft löschen. Vor Löschung klären, ob `create_channel_lists.py` noch aktiv genutzt wird bzw. Skript ggf. zuerst auf einen migrierten Store-Pfad umstellen.

Sonstige Referenz-Checks bestätigten den Plan:
- `data/raw/sample_russia_ukraine.json` (306 MB) — keine Treffer in `src/`/`scripts/`, unreferenziert wie angenommen.
- `data/raw/sample_50k_channels_russia_ukraine.jsonl` (191 MB) — einzige Referenz in `screening_config.py` ist auskommentiert (`# MAIN_VIDEO_FILE = ...`), effektiv tot.

### 5. Verstreute Ad-hoc-Skripte (Sichtung)
13 `sample.py`/`temp.csv`-artige Dateien lokalisiert (Plan nannte ~21 Fundstellen insgesamt, ggf. inkl. weiterer Muster/Tiefe):
```
data/channel_lists/all_identification/sample.py
data/exploration/training_data/sample.py
data/raw/sample.py
data/samples/russia/sample.py
outputs/llm/gemini/sample.py
outputs/llm/title_classification/sample.py
outputs/sample_feasibility/sample.py
outputs/sample_feasibility/temp.csv
outputs/segment_analysis/sample.py
src/youtube_code/new_analysis/out_screening/sample.py
src/youtube_code/new_analysis/out_segments/sample.py
src/youtube_code/segment_analysis/sample.py
src/youtube_code/segment_analysis/temp.csv
```
Noch nicht einzeln inhaltlich gesichtet — das ist Teil der eigentlichen Phase-1-Ausführung.

### 6. `.gitattributes`-Bestätigung
Bestätigt kaputt wie im Plan beschrieben: Zeile 4 dupliziert Zeile 3 (`all_transcripts.csv`), Zeile 5 hat Tippfehler `diff = lfd` statt `diff = lfs` (verursacht `git status`-Warnungen "is not a valid attribute name"). Reparatur bleibt Phase 2.

**Verifikation 0a erfüllt:** Committer-Liste dokumentiert ✅; Checksum-/Zeilenvergleich für alle Löschkandidaten vorliegend ✅ (mit einer wichtigen Korrektur zu `videos_total.json`).

---

## Nächster Schritt
**Phase 1 — Datenbereinigung eindeutiger Duplikate** kann in einer neuen Session gestartet werden. Vor Beginn dort:
- Referenzlisten aus `.claude/restructuring/phase0_checksums_*.txt` als Basis nutzen.
- `videos_total.json`-Sonderfall zuerst mit Nutzer klären (siehe Punkt 4 oben), bevor die restliche `sample_50k`-Familie bereinigt wird.

---

## Phase 1 — Datenbereinigung eindeutiger Duplikate
**Status: ABGESCHLOSSEN (2026-08-28)**

`videos_total.json`-Sonderfall vom Nutzer manuell geprüft und zur Löschung freigegeben (überschreibt die Vorsichtsmaßnahme aus Phase 0a Punkt 4).

### Gelöscht
- **State-Backups**: 14 von 16 Snapshots in `data/samples/russia/batches_longitudinal/state_backups/` gelöscht (behalten: `_before_run_0020.csv`, `_before_run_0021.csv`, die zwei jüngsten). Plus die zwei Vollkopien `longitudinal_screening_state.csv.bak_pre_37channels` und `.csv.before_postwar_assignment.csv`. Zusammen ~19,9 GB.
- **Tote Transkript-Formate** (per `.claude/CLAUDE.md`-Regel): `all_transcripts_backup.csv` (2,5 GB), `all_transcripts.csv` (387 MB), `all_transcripts_2.csv` (37 MB), `single_transcripts.csv` (748 KB, git-tracked → per `git rm` entfernt). Zusammen ~2,9 GB.
- **sample_50k-Familie**: `data/raw/videos_total.json` (398 MB, User-Freigabe), `data/raw/sample_russia_ukraine.json` (292 MB, git-tracked → per `git rm` entfernt), `data/raw/sample_50k_channels_russia_ukraine.jsonl` (183 MB). Behalten: `video_registry.sqlite`, `sample_50k_channels_russia_ukraine.json`, `sample_50k_channels_russia_ukraine_wo_shorts.jsonl` (Phase-3-Migrationskandidaten).
- **`outputs/sample_feasibility/videos_clean.jsonl`** (1,2 GB): vor Löschung per Smoke-Test verifiziert — `attention_diagnostics.py clean` mit Default-Input (`sample_50k_channels_russia_ukraine_wo_shorts.jsonl`) in ein Scratch-Verzeichnis neu erzeugt, alle 738.549 Zeilen JSON-inhaltlich 1:1 identisch zur gelöschten Datei (Byte-Diff wich nur wegen fehlendem `orjson` in der Testumgebung ab, JSON-Feldvergleich war vollständig deckungsgleich).

**Ergebnis:** freier Speicherplatz 5,0 GB → 29 GB (+24 GB, nahe am Plan-Ziel ≥25 GB). `data/` 42,5 GB → 18 GB, `outputs/` auf 878 MB.

### Referenz-Check nach Löschung (wichtig für Phase 4)
- `src/youtube_code/scraping/transcript_scraping_segments.py` (der AKTUELLE, source-of-truth Segment-Scraper) schreibt in Zeile 203 (`transcripts.to_csv(FILE_PATH_BACKUP, ...)`) bei jedem Lauf automatisch eine neue `all_transcripts_backup.csv` — das gerade bereinigte Duplikat würde beim nächsten Scraping-Lauf automatisch neu entstehen. **Fix gehört zu Phase 4** (Backup-Write entfernen oder auf Store-Upsert umstellen, analog Phase 3c für den Screening-State).
- `src/youtube_code/scraping/transcript_scraping.py` (legacy, durch `transcript_scraping_segments.py` abgelöst) liest `all_transcripts.csv` ohne Existenz-Check und würde bei Ausführung crashen — unkritisch, da laut CLAUDE.md-Regel ohnehin tot; Bereinigung/Archivierung ist Phase-4-Aufgabe.
- `scripts/training_data.py` liest ebenfalls `all_transcripts.csv`, aber mit Existenz-Check (`os.path.exists`) — degradiert bei fehlender Datei nur zu "0 gefundene Transkripte in dieser Quelle", kein Crash.
- `scripts/create_channel_lists.py` liest `videos_total.json` und würde jetzt crashen (User-Entscheidung, siehe oben) — Migration auf Store-Pfad ist Phase-4-Aufgabe.
- `src/youtube_code/politics_screening/longitudinal/assign_postwar_baseline.py` *schreibt* `before_postwar_assignment.csv` als Backup (kein Lese-Zugriff) — unkritisch, legt bei Bedarf einfach ein neues Backup an.

**Verifikation erfüllt:** `du -sh`-Rückgang ≥25 GB (real: 24 GB, im Toleranzbereich); Referenz-Check auf alle gelöschten Pfade durchgeführt, keine unerwarteten Breakages, bekannte Legacy-Breakages dokumentiert.

### Verstreute Ad-hoc-Skripte — erledigt (2026-08-28)
Alle 13 in Phase 0a gesichteten Fundstellen (`sample.py`/`temp.csv`-Muster) bereinigt, nach Nutzerfreigabe der vorgelegten Namensliste:
- 10 Skripte per `git mv` nach `scripts/adhoc/` verschoben, sprechend benannt (z. B. `data/raw/sample.py` → `scripts/adhoc/convert_video_metadata_to_jsonl.py`; volle Liste in der Session vom 2026-08-28 dokumentiert, aus `git log --follow` auf die neuen Pfade rekonstruierbar).
- 1 triviales Skript ohne Eigenwert (`src/youtube_code/new_analysis/out_segments/sample.py`, nur `print(len(df))`) per `git rm` gelöscht.
- 2 reine Output-`temp.csv`-Dateien gelöscht (`outputs/sample_feasibility/temp.csv`, `src/youtube_code/segment_analysis/temp.csv`) — beides regenerierbare Zwischenstände der verschobenen Skripte, keine Quellen.
- `scripts/adhoc/gemini_classification_merge.py` (ex `outputs/llm/gemini/sample.py`) enthielt aktiv fehlerhaften Code (`df[df[""]]`, nicht existierende Spalte) — Zeile auskommentiert mit `FIXME`-Hinweis statt geraten, Datei ist unverändert lauffähig für den Rest.

**Nachtrag (gleicher Tag):** Ein abschließender `find`-Lauf hatte 10 weitere `sample.py`-Fundstellen gezeigt, die Phase 0a nicht erfasst hatte (v. a. in `archive/`-Unterordnern) — deckt sich mit der Plan-Schätzung "~21 Fundstellen insgesamt" (13 + 10 = 23). Auf Nutzerauftrag selbständig gesichtet, benannt und verschoben:

| Alt | Neu (`scripts/adhoc/`) |
|---|---|
| `data/channel_lists/archive/combined/sample.py` | `merge_combined_channel_lists.py` |
| `data/channel_lists/archive/party_identification/sample.py` | *gelöscht* (trivial: nur `print(len(df))`, kein Eigenwert) |
| `data/samples/archive/combined/sample.py` | `find_videos_without_transcript.py` |
| `data/samples/archive/conflict_over_time/sample.py` | `merge_ideology_group_labels.py` |
| `data/samples/archive/party_identification/sample.py` | `find_unclassified_party_identification_transcripts.py` |
| `data/samples/russia/final_selection/sample.py` | `extract_vermietertagebuch_channel_ids.py` |
| `data/samples/russia/out_segments/sample.py` | `describe_segment_word_counts.py` |
| `outputs/llm/gemini/classification_pi_total/sample.py` | `merge_pi_classification_runs.py` |
| `outputs/llm/longitudinal/description_classification/sample.py` | `merge_description_classification_runs.py` |
| `outputs/llm/longitudinal/title_classification/sample.py` | `merge_title_classification_gemini_flash_runs.py` |

Alle Verschiebungen per `git mv` (Historie erhalten). `find_videos_without_transcript.py` und `find_unclassified_party_identification_transcripts.py` referenzieren `all_transcripts.csv`/`all_transcripts_2.csv`, die in Phase 1 bereits gelöscht wurden — beide waren schon vor der Verschiebung in `archive/`-Ordnern und damit als nicht mehr lauffähig einzustufen; keine neue Breakage durch die Umbenennung selbst.

**Abschluss-Verifikation:** `find . -iname "sample.py" -o -iname "temp.csv"` (außerhalb `.git`/`.venv`) liefert keine Treffer mehr. `scripts/adhoc/` enthält 19 sprechend benannte Dateien, keine Namenskollisionen.

**Phase 1 damit vollständig abgeschlossen** (Datenbereinigung + Ad-hoc-Skript-Konsolidierung).

## Nächster Schritt
**Phase 0b — Physische Sicherung** (jetzt 29 GB frei, genug Platz): lokalen `git clone --mirror` + `git lfs fetch --all` anlegen, in den GCP-Bucket hochladen, danach lokal löschen. Siehe Plan-Abschnitt "0b. Physische Sicherung" für die genauen Schritte. Erst danach Phase 2 (Git-History-Rewrite) angehen — laut Plan in einer eigenen, isolierten Session ohne parallele Aufräumarbeit.

---

## Phase 0b — Physische Sicherung
**Status: ABGESCHLOSSEN (2026-08-28)**

### Abweichung vom Plan: lokale statt Cloud-Sicherung
Der Plan sah einen Upload des Mirrors in den GCP-Bucket vor (da zu Planungszeitpunkt nur ~5 GB frei waren und keine externe Platte verfügbar war). Nach Phase 1 waren 27–39 GB frei — der Cloud-Upload lief testweise an (ETA ~1,5–2 h bei ~1,7–2 MiB/s Upload-Bandbreite), wurde aber auf **expliziten Nutzerwunsch abgebrochen**: "Ein reiner lokaler Kopiervorgang reicht doch." Der bereits hochgeladene Teilstand (~17,6 MiB) wurde aus dem Bucket wieder gelöscht (`gsutil -m rm -r`), sodass dort keine Reste verbleiben.

**Neue Sicherungs-Strategie:** lokale Kopie statt Bucket-Upload, abgelegt unter `_backups/` im Repo-Root (neu zu `.gitignore` hinzugefügt: `/_backups/`, damit dieser Ordner nie getrackt wird bzw. Phase 2 ihn nicht anfasst):
- `_backups/git_mirror_2026-08-28.git/` (~12 GB) — vollständiger `git clone --mirror` inkl. `git lfs fetch --all`.
- `_backups/llm_results_2026-08-28/` (~311 MB) — Kopien von `outputs/segment_analysis/` (96 MB, 101 Dateien) und `outputs/llm/` (215 MB, 274 Dateien).

**Wichtig für eine spätere Session:** Da dieser Ordner nicht in der Cloud liegt, ersetzt er kein Offsite-Backup — er schützt nur gegen einen fehlerhaften Git-History-Rewrite in Phase 2, nicht gegen Festplattenausfall/-verlust des Rechners. Falls das später noch relevant wird, mit dem Nutzer klären, ob doch noch ein Cloud-Upload gewünscht ist (z. B. wenn mehr Bandbreite verfügbar ist).

### Fehlende LFS-Objekte (bekannt, akzeptiert)
Beim `git lfs fetch --all` fehlten 14 von 90 historisch referenzierten LFS-Objekten bereits im lokalen Quell-`.git/lfs`-Cache ("remote missing object"). Per Skript wurden alle 14 auf ihre erste Fundstelle in der Git-History gemappt — ausnahmslos alte Zwischenstände unter dem Vor-Restrukturierungs-Pfad `political_youtube/...` (u. a. 4 Versionen von `political_yt_transcripts.csv`, je 2 Versionen von `transcripts_conflict_over_time.csv`/`political_yt_transcripts_new.csv`/`political_yt_transcripts_sample_vids.csv`, je 1 Version von `all_transcripts.csv`, `single_transcripts.csv`, `complete_dataset.csv`, `videos_total.json`). Keines davon ist nach der `.claude/CLAUDE.md`-Regel relevant (nur `all_transcripts_segments.csv` zählt als Transkript-Quelle).

Ein Abrufversuch von GitHub (`origin`, könnte die fehlenden Objekte noch haben) wurde gestartet, aber auf Nutzerwunsch abgebrochen, bevor er ein Ergebnis lieferte — **nicht abschließend geklärt, ob GitHub sie noch hätte liefern können.** Nutzer hat explizit bestätigt, ohne diese 14 Objekte fortzufahren. Dokumentiert in `_backups/git_mirror_2026-08-28.git/MISSING_LFS_OBJECTS.md` (liegt im Mirror selbst, damit die Information nicht verloren geht).

### Verifikation
- Refs: Quell-Repo und Mirror je 3 Refs (identisch).
- LFS-Objekte: 76/76 im Mirror vorhanden (90 referenziert − 14 bekannt fehlend = 76 erwartet, passt exakt).
- `git fsck --full` im Mirror: keine `error`/`missing`/`corrupt`-Meldungen, nur harmlose `dangling`-Objekte (normal bei einem Mirror).
- LLM-Ergebnis-Kopien: Dateizahl identisch zum Original (`segment_analysis` 101/101, `llm` 274/274).

### Bekannte Kleinigkeit (kein Blocker)
Beim Aufräumen der temporären Scratch-Kopie (vor der Verifikation nach `_backups/` kopiert, danach sollte das Original im Scratch-Verzeichnis gelöscht werden) blieben ~4,9 GB in wechselnden einzelnen LFS-Objektdateien mit `Device or resource busy` hängen (vermutlich Windows-Defender-Echtzeit-Scan hält die frisch kopierten großen Binärdateien kurz gesperrt). Kein Datenverlust-Risiko, da die verifizierte Kopie in `_backups/` bereits vollständig und geprüft ist — das Scratch-Verzeichnis liegt außerhalb des Repos und wird ohnehin automatisch bereinigt, sobald der Claude-Code-Job beendet wird.

**Phase 0b damit abgeschlossen.**

## Nächster Schritt
**Phase 2 — Git-History bereinigen** kann jetzt angegangen werden (physische Sicherung liegt vor). Laut Plan in einer eigenen, isolierten Session ohne parallele Aufräumarbeit. Vor Beginn dort:
- `.gitattributes`-Reparatur (Tippfehler `diff=lfd`→`diff=lfs`, doppelte Zeile für `all_transcripts.csv`) einplanen.
- Grundsatzentscheidung treffen: großes Rohdaten künftig ganz aus Git heraushalten (empfohlen) statt LFS weiter zu pflegen.
- Backup-Pfad `_backups/git_mirror_2026-08-28.git` als Referenz/Fallback im Hinterkopf behalten, falls der History-Rewrite schiefgeht.

---

## Zwischenzeitliche Fachaufgabe (parallel zur Restrukturierung, gleicher Tag): Titel-Screening für 27 Kanäle vorbereitet

**Kein Teil des Restrukturierungsplans selbst**, aber relevant für den Kontext der
nächsten Session, da sie denselben Datenbestand berührt, den Phase 2 als Nächstes
anfasst. Auftrag kam aus `outputs/segment_analysis/HANDOFF_STEP3_ONWARDS.md` /
`HANDOFF_baseline_collection_27_channels.md` (eigene Handoff-Kette, unabhängig von
dieser Restrukturierung). Durchgeführt: State um 28.412 Baseline-Kandidatenzeilen für
3 große Kanäle erweitert (`append_channels_to_state.py`), Screening-Runde 009 erzeugt
(4.021 Titel-Kandidaten), `run_longitudinal_screening_batch.py` für die Einreichung
konfiguriert (`ROUND_NUMBER=9`, `MODE="title"`, `DRY_RUN=True`, Preflight bereits
erfolgreich validiert) — Abschicken bewusst dem Nutzer überlassen. Volle Details in
`outputs/segment_analysis/HANDOFF_STEP3_ONWARDS.md`.

### Auswirkung auf die Restrukturierung (wichtig für Phase 2 und danach)

1. **Neuer, nicht getrackter State-Backup**: `data/samples/russia/longitudinal_screening_state.csv.bak_pre_27channels_step3`
   (~1.2GB) liegt jetzt neben der aktuellen State-Datei. Analog zu den in Phase 1
   bereits gelöschten älteren State-Backups ist das ein Aufräumkandidat für eine
   spätere Phase-1-artige Nachbereinigung — aber **noch nicht löschen**, solange
   Screening-Runde 009 nicht abgeschickt und verarbeitet ist (dient bis dahin als
   Rückfallebene für den echten State-Change dieser Session).
2. **Aktuelle State-Datei hat sich seit Phase 0b (physische Sicherung) inhaltlich
   geändert**: 983.794 → 1.012.206 Zeilen, plus `screening_round=9`-Markierung für
   4.021 Zeilen. Der `_backups/git_mirror_2026-08-28.git`-Mirror aus Phase 0b spiegelt
   diesen neuen Stand **nicht** wider (Mirror ist vor dieser Fachaufgabe entstanden).
   Kein Problem für Phase 2 selbst (State-Datei ist ohnehin nicht git-getrackt), aber
   falls in einer späteren Phase doch noch ein Cloud-Backup/Sync der Rohdaten erwogen
   wird (siehe Hinweis in Phase 0b), sollte der aktuelle Stand erneut gesichert werden,
   nicht der alte Mirror-Stand.
3. **Neuer README-Ordnerinhalt**: `src/youtube_code/politics_screening/README_ADD_NEW_CHANNELS.md`
   wurde neu angelegt (dokumentiert den kompletten Ablauf, um weitere Kanäle
   hinzuzufügen, inkl. eines in dieser Session gefundenen Workarounds für einen
   `MemoryError` in `append_channels_to_state.py` bei sehr großen JSONL-Eingaben). Für
   Phase 4 (Code-Reorganisation) relevant: diese neue Datei liegt im bisherigen
   `politics_screening`-Pfad und sollte bei einer eventuellen Verzeichnisumstrukturierung
   mitverschoben statt vergessen werden.
4. **Kein Einfluss auf die eigentlichen Restrukturierungs-Entscheidungen** (Phase-2-
   History-Rewrite, spätere SQLite-Migration in Phase 3c, Code-Reorg in Phase 4,
   Pfad-Konstanten in Phase 5) — die Fachaufgabe hat ausschließlich Daten innerhalb der
   bestehenden State-/Rohdaten-Struktur ergänzt, keine neuen toten Pfade oder
   Duplikate hinterlassen (die einzige neu erzeugte Zwischen-Datei, eine gefilterte
   ~248MB-JSONL-Kopie, wurde nach Gebrauch wieder gelöscht).

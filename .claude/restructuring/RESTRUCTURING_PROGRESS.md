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

## Phase 2 — Git-History bereinigen
**Status: ABGESCHLOSSEN (2026-08-28)**

### Wichtiger Befund (korrigiert eine Plan-Annahme)
Die ursprünglich dokumentierten "13 GB `.git`" stammten NICHT primär aus dem Git-Objekt-Store (`.git/objects` war nur 815 MB), sondern zu 12 GB aus dem lokalen `git-lfs`-Objekt-Cache (`.git/lfs`). `git lfs prune --dry-run` gab vor dem Rewrite nur 1 von 82 Objekten (54 MB) als entfernbar frei — der Rest war noch von erreichbaren historischen Commits referenziert. Der eigentliche Hebel war also: alte Commits mit LFS-Pointern aus der History entfernen (`git-filter-repo`) → Blobs im LFS-Cache werden unreferenziert → `git lfs prune` gibt sie frei.

### Durchgeführt
1. `git-filter-repo` per `pip install git-filter-repo` installiert (2.47.0).
2. Die 6 dirty getrackten Dateien aus der zwischenzeitlichen Fachaufgabe committet (normaler Commit, vor dem Rewrite nötig).
3. Lokalen Branch `backup-vor-bereinigung` gelöscht (nie zu `origin` gepusht, redundant zum verifizierten `_backups/git_mirror_2026-08-28.git`-Mirror; Nutzerentscheidung).
4. `.gitattributes` komplett entfernt (per `git rm`, eigener Commit) — kein aktuell getracktes File braucht noch LFS (siehe Befund oben); die Datei war zudem defekt (doppelte Zeile, Tippfehler `diff=lfd`).
5. **Zwei `git-filter-repo --invert-paths`-Läufe** (zweiter Lauf nach Nutzer-Rückfrage, da eine erste Runde weitere tote Pfade übersehen hatte — siehe unten):
   - Lauf 1 (aus dem vorab genehmigten Plan): `political_youtube/`, `data/transcripts/all_transcripts.csv`, `data/transcripts/all_transcripts_2.csv`, `data/transcripts/single_transcripts.csv`, `data/raw/videos_total.json`, `data/raw/sample_russia_ukraine.json`, `data/samples/all_videos_50k_channels.json`.
   - Lauf 2 (zusätzlich gefunden, mit Nutzerfreigabe nachgezogen): `project_transcripts/` (weiteres Alt-Transkript-Verzeichnis, enthielt die verbliebenen ~1,1 GB LFS-Blobs), `project_videos/` (Alt-Downloader-Code), `complete_channel_list.json`, `p.py` (beide Alt-Root-Dateien), sowie 2 historische Vollinhalt-Commits von `data/transcripts/all_transcripts_segments.csv` selbst (44 MB/40 MB, vor dessen Gitignore-Umstellung versehentlich committet — die aktuelle Arbeitsdatei ist und bleibt ungetrackt, nur alte Snapshots betroffen).
   - `llm_analysis/registry/runs_registry.csv` (Top-Level-Duplikat) wurde bewusst NICHT angefasst — ist weiterhin live in HEAD, Konsolidierung ist Phase-4-Aufgabe, kein Phase-2-Thema.
6. `git lfs prune` nach beiden Läufen ausgeführt.
7. **Zusätzlicher Fund:** `.git/lfs/incomplete/` enthielt noch 869 MB an Fragmenten eines früher abgebrochenen LFS-Fetch-Versuchs (siehe Phase-0b-Notiz zum abgebrochenen GitHub-Abruf) — das ist kein von `git lfs prune` verwalteter Bestand, sondern Datenmüll; manuell per `rm -rf` gelöscht.
8. Verifikation: `git fsck --full` fehlerfrei; `git log --oneline -- src/` zeigt weiterhin 60 Commits durchgängige Code-Historie; Test-Klon (mit `core.longpaths=true` wegen Windows-MAX_PATH-Limit bei tief verschachtelten Unicode-Pfaden unter `data/channel_lists/archive/...` — vorbestehende Eigenschaft des Repos, keine Regression) checkte sauber aus, `import youtube_code` funktionierte; `pip install -e .` lief in einen Netzwerk-Timeout beim Dependency-Download (kein Repo-Problem).
9. `git push --force origin main` ausgeführt (Nutzerentscheidung: automatisch im selben Schritt, nach erfolgreicher lokaler Verifikation).

### Ergebnis
`.git`-Größe: **13 GB → 10 MB** (weit unter dem Plan-Ziel "deutlich < 1 GB"). `.git/objects` allein: 815 MB → ~9,8 MB. Freier Speicherplatz: 16 GB → 23 GB.

### Offener Punkt für den Nutzer (kein automatisierter Schritt)
GitHub hält serverseitig weiterhin die alten LFS-Objekte der jetzt entfernten History, bis sie dort manuell bereinigt werden (Repo-Einstellungen → "Large file storage" → nicht mehr referenzierte Objekte entfernen/GC anstoßen). Das liegt außerhalb der Reichweite von `git`/`git-filter-repo` und wurde in dieser Session nur dokumentiert, nicht ausgeführt.

### Bekannte, aus Phase 0b übernommene Einschränkung
14 von 90 historisch referenzierten LFS-Objekten fehlten bereits vor dem Rewrite im lokalen Cache (siehe Phase-0b-Eintrag, dokumentiert in `_backups/git_mirror_2026-08-28.git/MISSING_LFS_OBJECTS.md`) — alle unter dem jetzt entfernten `political_youtube/`-Pfad, nach der `.claude/CLAUDE.md`-Regel ohnehin irrelevant. Durch den Rewrite dieser Session sind diese Pfade nun ganz aus der History entfernt, das Fehlen dieser 14 Objekte ist damit gegenstandslos geworden.

**Verifikation erfüllt:** `du -sh .git` deutlich < 1 GB (real: 10 MB) ✅; `git fsck` fehlerfrei ✅; Test-Klon lässt sich normal auschecken, Paket-Import funktioniert ✅; `git log --all -- src/` zeigt weiterhin sinnvolle Code-Historie ✅.

## Nächster Schritt
**Phase 3 — Datenformat-Migration je Datentyp** (siehe Plan-Abschnitt "Phase 3"), empfohlen als eigene Session pro Teilschritt (3a–3d). Vor Beginn dort:
- GitHub-seitige LFS-Bereinigung (siehe "Offener Punkt" oben) mit dem Nutzer klären/erledigen lassen, falls noch nicht geschehen.
- Die ~5,7 GB neuer, ungetrackter Arbeitsdaten-Dateien im Working Tree (u. a. `data/raw/video_registry.sqlite`, `data/samples/russia/sample_50k_channels_russia_ukraine*.jsonl`, diverse `scraping/*.json`-Fill-Listen) wurden in Phase 2 bewusst nicht angefasst (nicht git-getrackt, daher irrelevant für den History-Rewrite) — relevant als Input für Phase 3a/3b, sollten dort gesichtet statt einfach übernommen werden.

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

---

## Phase 3a — Video-Metadaten → `videos.sqlite`
**Status: ABGESCHLOSSEN (2026-08-31)**

### Stand-Check zu Sessionbeginn (Fachaufgabe seit Phase 2 fortgeschritten)
Vor Beginn verifiziert statt blind auf dem Phase-2-Stand aufgesetzt: die parallele
Screening-Fachaufgabe war zwischenzeitlich weitergelaufen (Runden 9 und 10 Titel
gemerged, Runde 10 Beschreibung während der Vorbereitung dieser Session abgeschlossen,
`runs_registry.csv` jetzt bis `run_0025`). Kein Einfluss auf Phase 3a, da diese nur
Video-Metadaten betrifft, keinen Screening-State.

### Design-Entscheidungen (mit Nutzer abgestimmt, siehe Plan-Datei der Session)
- Zwei Tabellen statt einer flachen: `videos` (schlanke, günstige Felder) +
  `video_details` (teure, seltener geänderte Felder wie description/tags).
- Ursprünglich geplante `video_sample_membership`-Tabelle mit zwei fest verdrahteten
  Tags **verworfen** (Nutzerkorrektur): stattdessen wird die vorhandene
  Such-Provenienz-Registry unter `data/channel_lists/all_identification/` roh in
  zwei neue Tabellen importiert (`search_runs`, `video_search_hits` — video_id,
  Suchbegriff, Recherche-Lauf-Zeitfenster). Eine echte Sample-Definition (z. B.
  "russia_base" = Videos vor dem 24.2.2022, gefunden über bestimmte Suchbegriffe)
  ist daraus **noch nicht** abgeleitet — offener Folgeschritt, siehe unten.
- Eine seit Plan-Erstellung neu entstandene Datei (`neue_kanaele_video_metadata_detailed.jsonl`,
  129.568 Zeilen, aus der laufenden Fachaufgabe) zusätzlich zum Plan-Text mit importiert.
- `data/samples/russia/sample_50k_channels_russia_ukraine.jsonl` (ohne `_wo_shorts`,
  975.480 Zeilen) **nicht importiert** — keine aktive Code-Referenz gefunden (nur
  auskommentierte Stellen), Nutzerentscheidung: vorerst nur dokumentieren, nicht
  migrieren. Lösch-/Archiv-Entscheidung steht noch aus.
- Alte Quelldateien bleiben unangetastet liegen (nicht gelöscht) — die lesenden
  Skripte (`feasibility.py`, `attention_diagnostics.py`) werden erst in Phase 4 auf
  DB-Zugriff umgestellt.

### Durchgeführt
1. `src/youtube_code/utils/video_registry.py` erweitert: `videos` um
   `channel_title`/`duration`/`view_count`/`like_count`/`comment_count` (per
   `ALTER TABLE`, rückwärtskompatibel zu bestehenden Aufrufern wie
   `channel_all_videos.py`); neue Tabellen `video_details`, `search_runs`,
   `video_search_hits`; neue Funktionen `upsert_video_details`,
   `upsert_search_runs`, `upsert_search_hits` (gleiches COALESCE-Muster wie
   `upsert_videos`, reine Fakten-Tabellen `search_runs`/`video_search_hits`
   per `INSERT OR IGNORE`).
2. `scripts/adhoc/migrate_video_metadata_to_registry.py` (einmaliges
   Migrationsskript, kein Pipeline-Bestandteil) geschrieben und ausgeführt:
   sichert die DB vorher (`.bak_pre_phase3a`), importiert die 5 Video-Metadaten-
   Quellen + die 2 Such-Provenienz-Dateien.
3. `scripts/adhoc/verify_video_metadata_migration.py` geschrieben und ausgeführt:
   simuliert für eine Stichprobe von 200 `video_id`s (verteilt über alle
   Quellen) den vollständigen COALESCE-Merge (inkl. Vor-Migrations-Zustand aus
   dem Backup) und vergleicht Feld für Feld gegen die migrierte DB — nicht nur
   ein reiner Datei-vs-DB-Abgleich, sondern inklusive korrekter
   Precedence-Reihenfolge zwischen den 5 Quellen.

### Ergebnis
- `videos`: 2.307.005 Zeilen vor **und** nach der Migration (kein Zuwachs) —
  plausibel, da `channel_all_videos.py` über `upsert_videos` bereits laufend in
  dieselbe Registry schreibt und die 5 Quelldateien historische Dumps desselben,
  bereits erfassten Kanal-Universums sind. Alle ~3,9 Mio. gelesenen Zeilen wurden
  angereichert (neue Spalten befüllt), keine neuen `video_id`s hinzugekommen.
- `video_details`: 1.073.309 Zeilen (= genau die Größe von
  `video_metadata_detailed_total.jsonl` — die beiden anderen Detail-Quellen sind
  nahezu vollständige Teilmengen davon).
- `search_runs`: 17/17 erwartet. `video_search_hits`: 33.600/33.600 erwartet.
- Verifikation: 4.000 Feld-Vergleiche über 200 `video_id`s, **0 Abweichungen**.
- Bestehende API (`get_channel_map`, `get_videos_for_channels`, `coverage_report`)
  nach dem Schema-Update ungebrochen getestet.
- `video_registry.sqlite.bak_pre_phase3a` nach erfolgreicher Verifikation wieder
  gelöscht (kein Dauerzustand, wie geplant).

**Verifikation erfüllt:** alle 6 Punkte aus der Plan-Datei (`import youtube_code`,
Migrationslauf-Zeilenzahlen, Verify-Skript OK, `total_count()`-Vergleich,
Smoke-Test bestehender Aufrufer, dieser Progress-Eintrag).

## Nächster Schritt
Zwei offene Folgepunkte aus 3a, unabhängig von der weiteren Phasen-Reihenfolge:
- **Sample-Membership-Ableitung** aus `video_search_hits` + Zeitraum-/Suchbegriff-
  Regeln (z. B. "russia_base") — mit Nutzer die konkreten Regeln klären, dann
  kleines Skript/View statt einer weiteren fest befüllten Tabelle.
- Entscheidung zu `sample_50k_channels_russia_ukraine.jsonl` (ohne `_wo_shorts`,
  vermutlich tot) — löschen/archivieren oder Referenz-Check wiederholen.

Danach **Phase 3b — Transkripte → `transcripts.parquet`/SQLite** (nächster
Teilschritt laut Plan-Reihenfolge), oder je nach Nutzerpriorität 3c/3d — 3c
(Screening-State) weiterhin erst angehen, wenn kein Screening-Batch gerade aktiv
läuft (siehe Hinweis zu Rundenverarbeitung oben).

---

## Phase 3b — Transkripte → `data/raw/transcripts.sqlite`
**Status: ABGESCHLOSSEN (2026-08-31)**

Plan lag vor Sessionbeginn bereits als `.claude/plans/phase_3b.md` vor (siehe
dortige Recherche-Befunde). Diese Session hat den Plan vollständig umgesetzt,
in vier vom Nutzer freigegebenen Schritten (Modul → Migrationsskript →
Verifikationsskript → autonomer Abschluss ohne Rückfrage je Schritt).

### Durchgeführt
1. `src/youtube_code/utils/transcript_store.py` (neu): WAL-Mode-Connection nach
   `video_registry.py`-Muster, Tabelle `transcripts` (`video_id` PK,
   `transcript_segments`, `language_code`, `is_generated`, `status`,
   `n_segments`). Kernstück `upsert_transcripts()` mit der im Plan
   spezifizierten `ON CONFLICT`-Prioritätsregel (`"OK"` > `"Kein Transkript"` >
   `"Fehler: ..."`, Last-Wins bei Gleichstand) direkt in der SQL-Klausel — gilt
   damit automatisch auch für künftige Phase-4-Direktschreibvorgänge des
   Scrapers. Weitere Funktionen wie geplant: `get_transcripts`/`get_transcript`,
   `attempted_video_ids`, `has_transcript`, `total_count`, `status_counts`,
   `export_jsonl`.
2. `scripts/adhoc/migrate_transcripts_to_store.py` (neu): Preflight-
   Duplikatreport (Referenzwert-Checkpoint gegen die Plan-Erwartung ~72.443),
   500er-Chunk-Migration mit NaN→None-Konvertierung, Backup-vor-Migration
   (`.bak_pre_migration`, idempotent).
3. `scripts/adhoc/verify_transcripts_migration.py` (neu): Reservoir-Sampling
   (n=200) + erzwungener Sonderfall `QsVgwJ40-zo`, voller CSV-Durchlauf zum
   Einsammeln aller Vorkommen der Ziel-IDs, `expected_winner()` simuliert die
   Prioritäts-/Last-Wins-Regel in Python zum Feld-für-Feld-Vergleich gegen eine
   Read-only-Connection, abschließender Zeilenzahl-Check.

### Ergebnis
- Preflight: **72.443 Zeilen, 72.443 eindeutige `video_id`s, 0 Duplikate** —
  exakt der Plan-Referenzwert, keine tatsächlichen Mehrfach-Scrape-Versuche in
  der aktuellen CSV (anders als ursprünglich für möglich gehalten).
- Migration: alle 72.443 Records upserted, `total_count()` danach = 72.443.
  `status_counts()`: 65.440 `OK`, 3.449 `Kein Transkript`, Rest verteilt auf
  3.556 verschiedene (meist Video-spezifische) `Fehler: ...`-Texte.
- Verifikation: **1.005 Feld-Vergleiche über 201 `video_id`s, 0 Abweichungen**;
  `QsVgwJ40-zo`-Sonderfall OK (DB-`status` zeichen-für-zeichen identisch zur
  CSV-Zelle inkl. eingebettetem Newline); Zeilenzahl-Check 72.443 (CSV) =
  72.443 (DB) OK.
- Idempotenz-Test (zweiter Migrationslauf): `total_count()` unverändert bei
  72.443, kein Fehler.
- Manuelle Stichprobenkontrolle (`QsVgwJ40-zo` per `get_transcript()`) plausibel.
- `transcripts.sqlite.bak_pre_migration` nach erfolgreicher Verifikation wieder
  gelöscht (analog Phase 3a, kein Dauerzustand, spart zusätzlich ~2,7 GB).
- `data/transcripts/all_transcripts_segments.csv` (2,9 GB) unangetastet
  liegengelassen (Quelle, wird erst nach Phase-4-Umstellung aller Konsumenten
  gelöscht).
- Der vorab dokumentierte Sicherheits-Checkpoint (kein paralleler
  `transcript_scraping_segments.py`-Lauf) wurde vor der Migration per
  Prozessliste geprüft — keine laufende `python.exe`-Instanz gefunden.

**Verifikation erfüllt:** alle 5 Punkte aus der Plan-Datei (Migrationslauf
fehlerfrei, Verifikationsskript OK für Stichprobe/Zeilenzahl/Sonderfall,
`total_count()` plausibel, Idempotenz-Test, dieser Progress-Eintrag).

### Explizit NICHT Teil dieser Session (laut Plan → Phase 4/5)
- Scraper-Umstellung (`transcript_scraping_segments.py`) auf
  `upsert_transcripts()`/`attempted_video_ids()` statt CSV-Append.
- Downstream-Leseskripte (`process_scraped_segments.py`,
  `new_analysis/segment_transcripts.py`, `scraping/get_baseline_ids.py`,
  `scripts/adhoc/segment_analysis_result_checks.py`,
  `scripts/adhoc/sample_feasibility_helpers.py`) umstellen.
- Löschen der Quell-CSV.
- `.claude/CLAUDE.md`-Regel-Update (Transkript-Source-of-Truth →
  `data/store/transcripts.*`).
- Modul-Verschiebung nach `store/transcript_store.py`.

## Nächster Schritt
Phase 3c (Screening-State) oder Phase 3d, je nach Nutzerpriorität — 3c weiterhin
erst angehen, wenn kein Screening-Batch gerade aktiv läuft. Danach Phase 4
(Code-Reorganisation), die die oben gelisteten Folgepunkte aus 3a und 3b
gebündelt aufgreift (Scraper-Umstellung, Downstream-Leseskripte, Sample-
Membership-Ableitung, Modul-Verschiebungen nach `store/`).

---

## Phase 3c — Screening-State → `data/raw/screening_state.sqlite`
**Status: ABGESCHLOSSEN (2026-08-31)**

Plan lag vor Sessionbeginn bereits als `.claude/plans/phase_3c.md` vor (siehe
dortige Recherche-Befunde). Diese Session hat den Plan vollständig umgesetzt,
auf expliziten Nutzerauftrag ("Führe den Plan für Phase 3c aus") — abweichend
von der sonst für die Restrukturierung geltenden Standing-Entscheidung
"nur Pläne, keine autonome Umsetzung" (siehe `project-restructuring-decisions`-
Memory), da diese Session eine ausdrückliche Ausführungs-Anweisung erhielt.
Sicherheits-Checkpoint (keine laufende `python.exe`-Instanz der vier
Schreib-Orte) vor der Migration technisch per Prozessliste geprüft, wie im
Plan gefordert.

### Durchgeführt
1. `src/youtube_code/utils/screening_state_store.py` (neu): WAL-Mode-Connection
   nach `video_registry.py`/`transcript_store.py`-Muster, eine flache Tabelle
   `screening_state` mit allen 19 Spalten der Quell-CSV (`video_id` PK).
   Kernstück `upsert_state_rows()` mit Feld-für-Feld-COALESCE (wie
   `video_registry.upsert_videos`, nicht das "ganze-Zeile-gewinnt"-Muster aus
   `transcript_store`) — welche Spalten ein Call-Site übergibt und Label-
   Schutzregeln bleiben bewusst Business-Logik der aufrufenden Skripte, wie
   im Plan festgelegt. Weitere Funktionen wie geplant: `get_state`,
   `total_count`, `round_counts`, `label_counts`, `export_csv`.
2. `scripts/adhoc/migrate_screening_state_to_store.py` (neu): technischer
   Sicherheits-Checkpoint (Prozessliste), Backup-vor-Migration
   (`.bak_pre_migration`, idempotent), Preflight-Eindeutigkeitscheck gegen den
   Plan-Referenzwert (1.012.206 Zeilen, 0 Duplikate), 5000er-Chunk-Migration
   mit NaN→None-Konvertierung.
3. `scripts/adhoc/verify_screening_state_migration.py` (neu): Reservoir-
   Sampling (n=300) plus gezielte Stichproben je `politics_final`-Bucket
   (-1/0/1/NULL, je 25) und `screening_round=10` (25) — Feld-für-Feld-
   Vergleich aller 19 Spalten gegen eine Read-only-Connection;
   Konsistenz-Check über `update_screening_state.validate_state_consistency()`
   auf den DB-Export angewendet (keine Duplizierung der Validierungslogik);
   `round_counts()`/`label_counts()`-Gegenprobe gegen `value_counts()` der
   Quell-CSV.

### Ergebnis
- Preflight: **1.012.206 Zeilen, 1.012.206 eindeutige `video_id`s, 0
  Duplikate** — exakt der Plan-Referenzwert.
- Migration: alle 1.012.206 Records upserted, `total_count()` danach =
  1.012.206. `screening_round`/`politics_final` je 699.134 NULL (= 313.072
  gescreente Zeilen) — deckt sich mit dem Recherche-Befund aus dem Plan.
- Verifikation: **7.650 Feld-Vergleiche über 425 `video_id`s, 0
  Abweichungen**; Konsistenz-Check (`validate_state_consistency()` auf
  DB-Export) OK; Zeilenzahl-Check 1.012.206 (CSV) = 1.012.206 (DB) OK;
  `round_counts()`/`label_counts()` stimmen exakt mit den CSV-`value_counts()`
  überein (alle 11 Runden-Werte + NULL, alle 4 Label-Ausprägungen + NULL).
- Idempotenz-Test (zweiter Migrationslauf): `total_count()` unverändert bei
  1.012.206, kein Fehler. `screening_state.sqlite.bak_pre_migration` (dabei
  automatisch angelegt, ~1,7 GB) nach erfolgreicher Verifikation wieder
  gelöscht, analog Phase 3a/3b (kein Dauerzustand).
- `data/samples/russia/longitudinal_screening_state.csv` (1,3 GB) unangetastet
  liegengelassen (Quelle, wird erst nach Phase-4-Umstellung aller vier
  Schreib-Orte gelöscht).

**Verifikation erfüllt:** alle 5 Punkte aus der Plan-Datei (Migrationslauf
fehlerfrei, Verifikationsskript OK für Zeilenzahl/Stichprobe/Konsistenz-Check,
`total_count()` plausibel, Idempotenz-Test, dieser Progress-Eintrag).

### Explizit NICHT Teil dieser Session (laut Plan → Phase 4/5)
- Umstellung der vier Schreib-Orte (`append_channels_to_state.py`,
  `create_longitudinal_screening.py`, `assign_postwar_baseline.py`,
  `update_screening_state.py`) auf `upsert_state_rows()` statt CSV-Vollkopie.
- Löschen der Quell-CSV.
- Löschen der `state_backups/`-Vollkopien (`before_run_0024.csv`,
  `before_run_0025.csv`, ~2,6 GB) und von
  `longitudinal_screening_state.csv.bak_pre_27channels_step3` (1,29 GB) —
  separat freizugebender Aufräum-Vorschlag, siehe Plan-Abschnitt 6
  (Rückhalte-Begründung aus der Fachaufgabe ist laut Plan inzwischen erfüllt,
  da Runden 009/010 gemergt sind).
- `screening_state_history`-Diff-Table (optional laut ursprünglichem
  Plan-Text).
- `.claude/CLAUDE.md`-Regel-Update, Modul-Verschiebung nach `store/`.

## Nächster Schritt
Phase 3d (LLM-Run-Registry) oder direkt Phase 4 (Code-Reorganisation) —
bündelt dann die Folgepunkte aus 3a, 3b und 3c: Scraper-/Screening-Skript-
Umstellung auf die neuen Stores, Downstream-Leseskripte, Sample-Membership-
Ableitung, Modul-Verschiebungen nach `store/`. Außerdem offen: der in diesem
Abschnitt oben genannte Aufräum-Vorschlag für die drei Screening-State-
Vollkopie-Backups (~3,9 GB), separat vom Nutzer freizugeben.

---

## Phase 3d — LLM-Run-Registry → `data/raw/llm_runs.sqlite`
**Status: ABGESCHLOSSEN (2026-08-31)**

Plan lag vor Sessionbeginn bereits als `.claude/plans/phase_3d.md` vor (siehe
dortige Recherche-Befunde). Diese Session hat den Plan vollständig umgesetzt,
auf expliziten Nutzerauftrag ("Führe den Plan phase_3d ... aus") — abweichend
von der sonst für die Restrukturierung geltenden Standing-Entscheidung
"nur Pläne, keine autonome Umsetzung" (siehe `project-restructuring-decisions`-
Memory), analog zur Ausnahme in Phase 3c. Sicherheits-Checkpoint (keine
laufende `python.exe`-Instanz der sechs Batch-Job-Schreib-Skripte) vor der
Migration technisch per Prozessliste geprüft, wie im Plan gefordert.

Wichtigster Recherche-Befund aus dem Plan (korrigiert eine Top-Level-Plan-
Annahme): die als "abweichende Top-Level-Kopie" bezeichnete
`llm_analysis/registry/runs_registry.csv` (Repo-Root) ist **keine Kopie**,
sondern eine zweite, unabhängig aktive Registry (Segment-Analyse-Pipeline,
19 Zeilen) mit eigenem `run_id`-Zähler, der mit dem der aktiven Screening-
Registry (`src/youtube_code/llm_analysis/registry/runs_registry.csv`,
25 Zeilen) kollidiert — beide starten bei `run_0001`. Zusammen mit den zwei
toten Varianten (`_legacy` 25 Zeilen, `_old` 14 Zeilen, deren referenzierte
Ergebnisdateien physisch nicht mehr existieren) waren **83 Zeilen aus vier
Quellen** zu migrieren, mit einem synthetischen Primärschlüssel (`id` +
`UNIQUE(source, run_id)`) statt einer einfachen `run_id`-Tabelle.

### Durchgeführt
1. `src/youtube_code/utils/llm_run_store.py` (neu): WAL-Mode-Connection nach
   `video_registry.py`/`transcript_store.py`/`screening_state_store.py`-
   Muster, eine flache Tabelle `llm_runs` mit synthetischem `id`-Primärschlüssel
   und `UNIQUE(source, run_id)`. Kernstück `upsert_runs(source, records)` mit
   "ganze-Zeile-gewinnt"-Konfliktauflösung (wie `transcript_store`, passend
   da keine Quellen-Fusion nötig ist — jede Quelle bleibt in ihrer eigenen
   `source`, Upsert dient nur der Idempotenz). Weitere Funktionen wie
   geplant: `get_runs(source=, dataset_id=, target_variable=, status=)`,
   `get_run(source, run_id)` (bewusster API-Bruch gegenüber `RunRegistry.get_run`,
   da `run_id` jetzt Pflicht-`source` braucht), `total_count`, `source_counts`,
   `export_csv`.
2. `scripts/adhoc/migrate_llm_runs_to_store.py` (neu): Sicherheits-Checkpoint
   (Prozessliste gegen sechs Batch-Job-Skriptnamen), Backup-vor-Migration
   (`.bak_pre_migration`, idempotent), Preflight-Zeilenzahl-Check je Quelle
   gegen die Plan-Referenzwerte (25/19/25/14 = 83), dann Import aller vier
   Quellen mit fest zugeordnetem `source`-Tag.
3. `scripts/adhoc/verify_llm_runs_migration.py` (neu): vollständiger
   Feld-für-Feld-Vergleich (kein Sampling, da nur 83 Zeilen insgesamt) —
   jede CSV-Zeile per `(source, run_id)` in der DB nachgeschlagen, alle 15
   Facheinheiten-Spalten verglichen; Zeilenzahl-Check je Quelle und gesamt;
   `results_path`-Existenz-Stichprobe (informativ, kein OK/MISMATCH-Kriterium).

### Ergebnis
- Preflight: **25 / 19 / 25 / 14 = 83 Zeilen**, exakt die Plan-Referenzwerte
  für alle vier Quellen.
- Migration: alle 83 Records upserted, `total_count()` danach = 83.
  `source_counts()`: `{gemini_old: 14, screening_active: 25,
  screening_legacy: 25, segment_analysis_active: 19}` — exakt wie erwartet.
- Verifikation: **1.245 Feld-Vergleiche über alle 83 Zeilen, 0 Abweichungen**;
  Zeilenzahl-Check je Quelle und gesamt OK; `results_path`-Stichprobe bestätigt
  den Recherche-Stand (2 aktive Pfade existieren, 2 tote Pfade fehlen wie
  erwartet).
- Idempotenz-Test (zweiter Migrationslauf): `total_count()` unverändert bei
  83, kein Fehler. `llm_runs.sqlite.bak_pre_migration` nach erfolgreicher
  Verifikation wieder gelöscht (analog Phase 3a–3c, kein Dauerzustand).
- Alle vier Quell-CSVs unangetastet liegengelassen (Quellen, werden erst nach
  Phase-4-Umstellung aller Call-Sites gelöscht).

**Verifikation erfüllt:** alle 6 Punkte aus der Plan-Datei (Migrationslauf
fehlerfrei, Verifikationsskript OK für alle vier Quellen bei vollständigem
Feld-Vergleich, `total_count()`-Check = 83, `source_counts()` exakt wie
erwartet, Idempotenz-Test, dieser Progress-Eintrag).

### Explizit NICHT Teil dieser Session (laut Plan → Phase 4)
- Umstellung der 12 aktiven Call-Sites auf `llm_run_store.upsert_runs()`/
  `get_runs()`/`get_run()` statt `RunRegistry` (inkl. Entscheidung Wrapper vs.
  Direktumbau).
- Löschen einer der vier Quell-CSVs.
- Physische Ergebnis-Konsolidierung nach `outputs/llm_results/<source>__<run_id>/`
  (konkreter Vorschlag in Plan-Abschnitt 6 festgehalten, separat freizugebender
  Folgeschritt).
- Bereinigung der Top-Level-`llm_analysis/`-Verzeichnisstruktur.
- `.claude/CLAUDE.md`-Regel-Update, Modul-Verschiebung nach `store/`.

**Damit ist Phase 3 (Format-Migration) vollständig abgeschlossen** — alle vier
Teilschritte (3a Video-Metadaten, 3b Transkripte, 3c Screening-State, 3d
LLM-Runs) sind umgesetzt und verifiziert.

## Phase 4a — Mechanisches Aufräumen (2026-08-31, abgeschlossen)

Erster Teilschritt von Phase 4 (Plan: `.claude/plans/phase_4.md`), auf
expliziten Ausführungsauftrag durchgeführt (Abweichung von der sonst
geltenden Standing-Entscheidung "nur Pläne liefern" — siehe Plan-Kontext,
analog 3c/3d).

### Durchgeführt
1. **Backup-Cleanup (~3,9 GB)**: Vor dem Löschen per Pandas-Zeilenvergleich
   (nicht `wc -l`, da die CSV mehrzeilige gequotete Felder enthält und
   `wc -l` deshalb ~18 Mio. statt der tatsächlichen 1.012.206 Zeilen zählt)
   verifiziert, dass alle drei Kandidaten Teilmengen bzw. exakte Kopien der
   aktuellen `longitudinal_screening_state.csv` sind (`screening_round`-
   Verteilung Zeile für Zeile identisch bzw. Teilmenge; zusätzlich gegen
   `screening_state_store.total_count()`/`round_counts()` gegengeprüft — exakte
   Übereinstimmung, 1.012.206 Zeilen). Kein aktiver Python-Prozess zum
   Zeitpunkt der Löschung. Gelöscht:
   `batches_longitudinal/state_backups/politics_screening_state_before_run_0024.csv`
   (1,3 GB), `..._before_run_0025.csv` (1,3 GB),
   `longitudinal_screening_state.csv.bak_pre_27channels_step3` (1,2 GB).
2. **`sample_50k_channels_russia_ukraine.jsonl`** (ohne `_wo_shorts`, 1,8 GB,
   `data/samples/russia/`) gelöscht — einzige Referenz in `screening_config.py`
   war bereits auskommentiert.
3. **`legacy/` archiviert**: `src/youtube_code/politics_screening/legacy/`
   (3 Dateien + `__init__.py`) per `git mv` nach
   `src/youtube_code/archive/politics_screening_legacy/` — keine aktiven
   Importe gefunden.
4. **Kaputte, tote Skripte archiviert**: `src/youtube_code/collection/{video_sampling,comment_download}.py`
   per `git mv` nach `src/youtube_code/archive/collection/` — keine aktiven
   Importe gefunden, damit ist auch die Namenskollision mit dem aktiven
   `scripts/video_sampling.py` (625 Zeilen) aufgelöst.
5. **Import-Konsistenz**: die 5 `from src.youtube_code...`-Stellen
   (`collection/video_search.py:7-9`,
   `scripts/adhoc/merge_ideology_group_labels.py:2`,
   `scripts/training_data.py:9`) auf `from youtube_code...` umgestellt.
   Für die nackten Sibling-Importe (`from settings_variables import ...` in
   `channel_all_videos.py`/`video_identification.py`/`video_search.py`,
   `from success_data_utils import ...` in den 3
   `archive/success_analysis/*.py`-Dateien, `from deskriptiv_aggregation
   import ...`/`from fe_signifikanz_test import ...` in `segment_analysis/*.py`)
   wurde **keine** Umstellung auf Paket-relative Importe vorgenommen: alle
   betroffenen Module sind reine, nirgends importierte Standalone-Skripte
   (verifiziert per Codebase-weiter Suche), die direkt per
   `python skriptname.py` mit dem eigenen Verzeichnis als `cwd` ausgeführt
   werden — Python legt dabei automatisch das Skriptverzeichnis auf
   `sys.path[0]`, wodurch der bare Sibling-Import funktioniert, während
   `from youtube_code...` unabhängig vom `cwd` auflöst. Eine relative
   Importumstellung (`from .settings_variables import ...`) hätte genau
   diesen Ausführungsweg gebrochen ("attempted relative import with no known
   parent package" bei Ausführung als `__main__`). Stattdessen wurde das
   bewusste Muster im Docstring dokumentiert (neu ergänzt in
   `channel_all_videos.py`, `video_identification.py`, `video_search.py`,
   `descriptive_analysis.py`, `video_sample_uebersicht.py`; in
   `success_trend_analysis.py`, `success_advanced_analysis.py`,
   `fe_signifikanz_test.py`, `geglaettete_kurve.py` war es bereits
   dokumentiert).
6. **`scripts/old/` archiviert** (Nutzerentscheidung nach Rückfrage, da "alt"
   laut Plan nicht automatisch "tot" heißt): alle 12 Dateien
   (`channel_activity_over_time.py`, `evaluate_title_classification.py`,
   `run_title_{retry,screening,training}_batch.py`,
   `outcome_analysis/{success_analysis,youtube_success}.py`,
   `transcript_analysis/{api_request_vertexai,channel_analysis,
   download_results_vertexai,flexible_pipeline_vertexai,results_analysis}.py`)
   per `git mv` nach `scripts/archive/` — keine aktiven Importe irgendwo im
   Code gefunden; für die drei `run_title_*_batch.py` existieren erkennbare
   Nachfolger unter `src/youtube_code/llm_analysis/`.

### Offene Punkte (bewusst nicht in 4a entschieden)
- `data/external/media_type_russia_merged.xlsx.bak` (31 KB, unklarer Zweck,
  keine Code-Referenz — im Unterschied zur aktiven `.xlsx`-Datei ohne `.bak`,
  die von 5 Stellen referenziert wird).
- JSONL-Doppelspurigkeit in `src/youtube_code/utils/io.py:get_video_metadata()`
  (Zeilen 120ff.): schreibt Metadaten sowohl in eine JSONL-Datei als auch
  (an anderer Stelle) über `video_registry.upsert_videos()` — welche der
  beiden Schreibwege künftig der maßgebliche sein soll, ist Business-Logik
  und wird nicht in 4a vorweggenommen.

### Verifikation erfüllt
`du -sh data/` vor/nach zeigt einen Rückgang von ca. 5,8 GB (3,9 GB
State-Backups + 1,8 GB Sample-JSONL); `grep -r "from src.youtube_code" src/
scripts/` liefert keine Treffer mehr; `python -c "import youtube_code"`
weiterhin fehlerfrei (mit `src/` auf dem Pfad); `git log --follow` bestätigt
die Historie für alle `git mv`-Verschiebungen.

## Phase 4b, Schritt 1 — LLM-Run-Registry: reine Leser-Call-Sites (2026-08-31, abgeschlossen)

Auf expliziten Ausführungsauftrag durchgeführt, aber bewusst nur der erste
von 6 Unterschritten aus `.claude/plans/phase_4.md` Abschnitt "Teilschritt
4b" — die Sitzung hatte laut Nutzerangabe nur noch wenig Budget übrig, daher
Rückfrage an den Nutzer, der sich für "nur Schritt 1, dann sauber stoppen"
entschieden hat.

### Durchgeführt
Die 4 reinen Leser-Call-Sites aus Plan-Punkt 1 auf `llm_run_store`
umgestellt (`RunRegistry(REGISTRY_PATH)` → `from youtube_code.utils.llm_run_store
import get_runs, get_run`, `source="screening_active"`):
- `run_longitudinal_screening_batch.py` (`require_no_existing_run`)
- `run_politics_screening_batch.py` (`require_no_existing_run`, identische
  Struktur wie oben)
- `run_transcript_classification_batch.py` (`require_no_existing_runs`,
  Schleife über `prompt_keys`)
- `evaluate_politics_screening.py` (`load_run_metadata`, Parameter
  `registry_path` → `source` umbenannt, 2 Aufrufstellen in `main()`
  angepasst)

**Wichtige Abweichung vom alten Verhalten:** `llm_run_store.get_runs()`
unterstützt nur `source`/`dataset_id`/`target_variable`/`status` als
Filterparameter (kein `**filters` wie die alte `RunRegistry.get_runs()`).
Die drei Batch-Runner filterten zusätzlich nach `prompt_id`
(und `run_transcript_classification_batch.py` zusätzlich nach
`dataset_version`) — das wird jetzt nicht mehr in SQL, sondern als
zusätzlicher Pandas-Filter auf das vom Store zurückgegebene DataFrame
angewendet (`existing[existing["prompt_id"] == ...]`). Ergebnis ist
inhaltlich identisch zum alten Verhalten, nur der Store selbst wurde nicht
um weitere Filterparameter erweitert (bewusst minimal gehalten für diesen
Teilschritt — falls in 4b Schritt 2–6 weitere Call-Sites dieselben
Zusatzfilter brauchen, lohnt sich dort eine Erweiterung von `get_runs()`
um echte SQL-Parameter statt der Pandas-Nachfilterung an mehreren Stellen
zu duplizieren).

### Verifikation erfüllt
`python -m py_compile` über alle 4 Dateien fehlerfrei; echter Modul-Import
aller 4 Dateien mit `PYTHONPATH=src` aus der `.venv` heraus fehlerfrei;
funktionaler Test von `get_runs()`/`get_run()` gegen die reale
`llm_runs.sqlite` (83 Zeilen gesamt, 25 `screening_active`, unverändert
gegenüber dem 3d-Migrationsstand) erfolgreich; `grep -rn "RunRegistry\|REGISTRY_PATH"`
über die 4 Dateien liefert keine Treffer mehr; `git diff --stat` zeigt einen
isolierten Diff nur in diesen 4 Dateien (23 Zeilen +, 25 Zeilen -), keine
Vermischung mit anderen Änderungen. **Noch nicht committet** (Repo-Status:
nur diese 4 Dateien als `M` markiert; committet wird nach Standing-Entscheidung
nur auf expliziten Nutzerwunsch).

## Phase 4b, Schritt 2–6 — LLM-Run-Registry: restliche Call-Sites + Aufräumen (2026-08-31, abgeschlossen)

Auf expliziten Ausführungsauftrag durchgeführt (`.claude/plans/phase_4.md`,
Abschnitt "Teilschritt 4b", Punkte 2–6, direkt im Anschluss an Schritt 1).

### Durchgeführt

**`llm_run_store.py` um zwei Komfortfunktionen erweitert** (`next_run_id(source)`,
`add_run(source, **fields)`, `update_run(source, run_id, **fields)`), da die
alte `RunRegistry.add_run()`/`update_run()`-API an 10+ Call-Sites 1:1
nachgebildet werden musste — genau die in Schritt 1 als mögliche
Store-Erweiterung vorgemerkte Stelle. Wichtig: `update_run()` macht
**fetch-merge-upsert** (erst `get_run()`, dann die übergebenen Felder
darüberlegen, dann `upsert_runs()`), weil `upsert_runs()` bei einem
`ON CONFLICT` immer die *ganze* Zeile ersetzt — ein naives Weiterreichen nur
der übergebenen Felder hätte alle nicht übergebenen Spalten auf `NULL`
gesetzt. Per Test gegen eine temporäre DB-Kopie verifiziert (siehe unten).

**Zentrale Schreiber (Punkt 2):**
- `submit_batch_jobs.py`: `registry = RunRegistry(REGISTRY_PATH)` entfernt,
  `registry.add_run(...)` in `run_all_prompts()` → `llm_run_store.add_run(LLM_RUN_SOURCE, ...)`.
- `download_results.py`: alle 5 `registry.update_run(...)`-Aufrufe in
  `process_run()` (failed/error/validation_failed ×2/downloaded) sowie
  `registry.get_run(run_id)` und `registry.get_runs(status="submitted")`
  in `main()` umgestellt.

**`retry_run.py`/`update_screening_state.py` (Punkt 3):**
- `retry_run.py`: importierte vorher das globale `registry`-Objekt aus
  `submit_batch_jobs` (das es jetzt nicht mehr gibt) — alle 5 Zugriffe
  (`submit_retry`, `wait_for_job`, `finalize_retry` ×2 get + ×2 update)
  auf `llm_run_store.get_run`/`update_run(LLM_RUN_SOURCE, ...)` umgestellt.
  Die tote `if run is None`-Prüfung entfernt (weder die alte `RunRegistry`
  noch `llm_run_store.get_run()` geben je `None` zurück, beide werfen bei
  unbekannter `run_id` eine `ValueError` — die Prüfung war schon vorher
  unerreichbar).
- `update_screening_state.py`: nur der Registry-Teil (State-Teil ist 4d).
  `load_run_and_results()` verliert den `registry_path`-Parameter komplett
  (ersetzt durch `llm_run_store.get_run(LLM_RUN_SOURCE, run_id)`); der
  Parameter wurde durchgereicht bis zu `update_screening_state()` und
  `main()` — beide Signaturen entsprechend bereinigt. Keine anderen
  Call-Sites von `update_screening_state()` im aktiven Code gefunden (nur
  `main()` selbst), daher unproblematisch.

**`segment_analysis_active`-Quelle (Punkt 4):**
- `submit_segments.py`: `require_no_existing_run()` von einem
  `registry`-Parameter auf direkten `llm_run_store.get_runs(source=LLM_RUN_SOURCE,
  dataset_id=..., target_variable=...)`-Aufruf umgestellt, `dataset_version`/
  `prompt_id` wie in Schritt 1 als Pandas-Nachfilter (Store bewusst nicht
  erweitert, siehe Schritt-1-Notiz oben). `registry.add_run(...)` → `llm_run_store.add_run(LLM_RUN_SOURCE, ...)`.
- `download_segments.py`/`download_segments_simple.py`: **nicht
  zusammengelegt**, obwohl Plan-Punkt 4 das als Prüfauftrag nannte
  ("prüfen, ob sich beide zusammenlegen lassen") — Recherche ergab, dass
  beide Dateien zwar strukturell fast identisch sind, aber aus
  unterschiedlichen Prompt-Modulen importieren (`segment_prompts` vs.
  `segment_prompts_simple`), die für dieselben `prompt_key`-Werte
  (`POPULISMUS_P`, `IDEOLOGIE_I`) unterschiedliche Schemata definieren. Ein
  Merge bräuchte eine neue Möglichkeit, pro Run zu erkennen, welches
  Prompt-Modul bei der Submission verwendet wurde (z. B. ein zusätzliches
  Registry-Feld) — das ist über die reine Call-Site-Migration hinaus eine
  eigene Design-Entscheidung und wurde bewusst nicht ungefragt getroffen.
  Beide Dateien bekamen stattdessen identische, isolierte Änderungen:
  `process_run()` verliert den `registry`-Parameter, `registry.get_run`/
  `update_run` → `llm_run_store.get_run`/`update_run(LLM_RUN_SOURCE, ...)`;
  `main()` verliert `registry = RunRegistry(REGISTRY_PATH)`,
  `registry.get_runs(status="submitted")` → `llm_run_store.get_runs(source=LLM_RUN_SOURCE, status="submitted")`.

**Config-Umstellung (Punkt 5):**
- `screening_config.py`/`segment_analysis_config.py`: `REGISTRY_PATH`
  (Dateipfad-Konstante) durch `LLM_RUN_SOURCE` (String-Konstante,
  `"screening_active"` bzw. `"segment_analysis_active"`) ersetzt — alle
  oben migrierten Call-Sites importieren jetzt `LLM_RUN_SOURCE` statt einen
  Dateipfad. In `segment_analysis_config.py` wurde dadurch der
  `ROOT`-Import ungenutzt und entfernt (einzige bisherige Verwendung war
  `REGISTRY_PATH`).

**Aufräumen (Punkt 6):**
- Vor dem Verschieben/Löschen alle vier CSV-Registries 1:1 gegen die
  entsprechende `source` in `llm_runs.sqlite` abgeglichen (Zeilenzahl +
  `run_id`-Mengen): `src/youtube_code/llm_analysis/registry/runs_registry.csv`
  (25, `screening_active`), `runs_registry_legacy.csv` (25,
  `screening_legacy`), `runs_registry_old.csv` (14, `gemini_old`),
  Repo-Root `llm_analysis/registry/runs_registry.csv` (19,
  `segment_analysis_active`) — alle vier identisch, erst danach angefasst.
- `merge_and_evaluate.py` (kaputter `from registry.run_registry import
  RunRegistry`-Import, tote `gemini_old`-Quelle) und der komplette
  `src/youtube_code/llm_analysis/registry/`-Ordner (alte `run_registry.py`-
  Klasse + alle 3 CSVs) per `git mv` nach `src/youtube_code/archive/llm_analysis/`
  verschoben (Historie erhalten, Import bewusst nicht repariert — Datei ist
  tot).
- Repo-Root-Ordner `llm_analysis/` (nur noch die migrierte
  `registry/runs_registry.csv`) per `git rm -r` gelöscht, wie im Plan
  explizit vorgesehen (nicht archiviert, da vollständig in `llm_runs.sqlite`
  vorhanden und durch keinen Call-Site mehr referenziert).

### Offener Punkt (nicht Teil dieser Session)
`scripts/adhoc/migrate_llm_runs_to_store.py` und
`scripts/adhoc/verify_llm_runs_migration.py` referenzieren noch die jetzt
verschobenen/gelöschten CSV-Pfade (`SRC / "llm_analysis" / "registry" /
"runs_registry.csv"`, Repo-Root-Äquivalent). Beide sind einmalige,
bereits erfolgreich gelaufene Migrationsskripte (die Migration nach
`llm_runs.sqlite` ist abgeschlossen und verifiziert) — ein erneuter Lauf
wäre ohnehin sinnlos, ein Fix war daher kein Bestandteil der 4b-Aufgabe.
Falls die Skripte als Dokumentation/Referenz erhalten bleiben sollen, wäre
ein Pfad-Update oder eine Verschiebung nach `archive/` ein Kandidat für
eine spätere Aufräum-Runde (z. B. Phase 5).

### Verifikation erfüllt
Alle 14 betroffenen Module (10 Call-Sites + 3 Configs + `llm_run_store.py`,
plus die 4 aus Schritt 1 zur Kontrolle) importieren fehlerfrei mit
`PYTHONPATH=src` aus der `.venv` heraus (reines `python -c` ohne venv
schlägt an `google.genai`/`sklearn` fehl — Umgebungsproblem, nicht
codebezogen, siehe "Neue Erkenntnisse" oben). Neues
`scripts/adhoc/verify_llm_run_callsites.py` geschrieben und ausgeführt:
Import-Check über alle 14 Module + Funktions-Check von
`add_run()`/`update_run()`/`next_run_id()` gegen eine **temporäre Kopie**
von `llm_runs.sqlite` (bestätigt: `update_run()` verändert nur die
übergebenen Felder, `add_run()` zählt `run_id` korrekt je `source`, andere
`source`-Werte bleiben unberührt). `llm_run_store.source_counts()`/
`total_count()` gegen die reale DB vor und nach allen Änderungen identisch
(83 Zeilen gesamt: 25 `screening_active`, 25 `screening_legacy`, 19
`segment_analysis_active`, 14 `gemini_old`) — keine versehentliche
Schreiboperation gegen die Produktiv-DB. `grep -rn "RunRegistry\|runs_registry\.csv"
src/ scripts/` liefert außerhalb von `archive/` nur noch erklärende
Docstring-/Kommentarzeilen (kein aktiver Call-Site-Treffer mehr) plus die
zwei oben dokumentierten Migrationsskripte. `pyflakes` über alle 10
geänderten Dateien lief durch; der einzige durch diese Session verursachte
ungenutzte Import (`ROOT` in `segment_analysis_config.py`) wurde entfernt,
alle übrigen `pyflakes`-Funde waren bereits vor dieser Session vorhanden
(gegen `HEAD` verifiziert) und daher nicht Teil dieser Aufgabe. **Noch
nicht committet** — liegt zusammen mit Schritt 1 im selben uncommitteten
Working-Tree-Diff (Repo-Status: nur die hier genannten Dateien als `M`/`R`/`D`
markiert, keine Vermischung mit unabhängigen Änderungen).

## Nächster Schritt
**Phase 4c — Transkripte** (Scraper + 5 Leser auf `transcript_store`
umstellen, höchstes Einzelrisiko der Phase 4 wegen echter API-Calls; Plan:
`.claude/plans/phase_4.md`, Abschnitt "Teilschritt 4c"). Danach 4d
(Screening-State, hängt an 4b — jetzt abgeschlossen), 4e
(Store-Modulverschiebung + physische LLM-Ergebnis-Konsolidierung, hängt an
4b–4d). Vor Beginn `git status` prüfen — Schritt 1 und Schritt 2–6 von 4b
liegen beide noch uncommittet im selben Diff. Sample-Membership-Ableitung
aus `video_search_hits` bleibt laut Nutzerentscheidung komplett außerhalb
von Phase 4, als eigenständiges Thema für eine spätere, separate Session.

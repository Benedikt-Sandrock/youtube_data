# Codebuch Rohdatensatz (Entwurf)
Stand: 02.10.2026 · Zweck: Export aus Python → Stata, Grundlage für alle Do-Files (Blöcke 1–3, ggf. Lerntest)

## Grundsätze
- **Zwei Dateien**, Verknüpfung im Do-File über `merge m:1 channel_id`:
  - `videos_roh.dta` – eine Zeile pro Video
  - `kanaele_roh.dta` – eine Zeile pro Kanal
- **Population Videos:** alle Videos aller Kanäle in `kanaele_roh.dta`, Dauer > 180 s (wie in allen bisherigen Analysen). Kein Zeitfenster-Filter im Export, das Analysefenster wird im Do-File gesetzt.
- **Population Kanäle:** alle Kanäle, für die Videos vorliegen; die Sample-Zugehörigkeit steht als Kennzeichen in der Datei (kein Vorab-Ausschluss).
- **Keine Umformungen** im Export: keine Logs, keine Phasen, keine Aggregation über Videos. Ausnahme: die bereits festgelegte Regel `deskriptiv`-Segmente = 0 (ist Teil der Messung).
- **Fehlende Werte:** `pandas.to_stata` schreibt NaN als `.` (keine erweiterten Missings wie `.a`). Daher gilt: Wert fehlt = `.`, **der Grund steht in einer eigenen Kennzeichenvariable** (`*_klass`, `*_verfuegbar`). Nie 0 als Ersatz für „fehlt“.
- **Datentypen:** IDs als String; Zählwerte als `double` (nicht `float`); Kennzeichen als `byte` (0/1); Zeitpunkte als Stata-`%tc` in **UTC** (`convert_dates={'...': 'tc'}`).
- **Variablennamen:** ≤ 32 Zeichen, Kleinbuchstaben, keine Umlaute. Variablen- und Wertelabels werden im Export gesetzt (`variable_labels`, Wertelabels über Kategorien bzw. im ersten Do-File).
- **Log des Exports:** Anzahl Videos vor/nach Längenfilter je Kanal, Anzahl Videos ohne Kanalzuordnung, Merge-Bilanz je Quelldatei.

---

## Datei 1: `videos_roh.dta` (Videoebene)

### Identifikation und Zeit
| Variable | Typ | Inhalt | Codierung / Hinweis | Quelle (zu prüfen) |
|---|---|---|---|---|
| `video_id` | str11 | YouTube-Video-ID | eindeutig, Schlüssel | Video-Metadaten |
| `channel_id` | str24 | YouTube-Kanal-ID | Schlüssel zu `kanaele_roh` | Video-Metadaten |
| `upload_ts` | %tc | Veröffentlichungszeitpunkt (`published_at`) | UTC; Tage relativ zum 24.02.2022 im Do-File | Video-Metadaten |
| `abruf_ts` | %tc | Zeitpunkt des Abrufs der Metriken | UTC; für Videoalter. Falls nur auf Kanalebene bekannt: Kanalwert übernehmen und im Log vermerken | Scraping-Metadaten |
| `dauer_sek` | long | Videolänge in Sekunden | > 180 per Definition | Video-Metadaten |
| `live_typ` | byte | Art des Videos | 0 = regulär, 1 = (aufgezeichneter) Livestream, 2 = Premiere; `.` = unbekannt | `liveStreamingDetails` / `liveBroadcastContent`, falls vorhanden |

### Erfolgsmetriken (Stand: `abruf_ts`)
| Variable | Typ | Inhalt | Codierung / Hinweis |
|---|---|---|---|
| `views` | double | Aufrufe kumuliert | `.` nur bei fehlendem Feld |
| `likes` | double | Likes kumuliert | `.`, wenn ausgeblendet |
| `kommentare` | double | Kommentare kumuliert | `.`, wenn deaktiviert |
| `likes_verfuegbar` | byte | Likes sichtbar | 1 = Feld vorhanden; 0 = Feld fehlt in API-Antwort (ausgeblendet) |
| `komm_verfuegbar` | byte | Kommentare aktiv | 1 = Feld vorhanden; 0 = Feld fehlt (deaktiviert) |

### Klassifikation politisch / Topics
| Variable | Typ | Inhalt | Codierung / Hinweis |
|---|---|---|---|
| `politisch` | byte | Video politisch | 1/0; `.` = nicht klassifiziert |
| `politisch_klass` | byte | Klassifikation liegt vor | 1/0 |
| `krieg` | byte | Kriegsvideo (Russland-Ukraine) | 1/0; `.` = nicht klassifiziert |
| `krieg_klass` | byte | Klassifikation liegt vor | 1/0 |
| `krieg_quelle` | str | Grundlage der Zuordnung | z. B. `titel`, `beschreibung`, `transkript` (letzte entscheidende Runde) |
| `topic_*` | byte | weitere Topics | **offen**, welche (siehe Offene Fragen); je Topic 1/0/`.` |

### Populismus (Videoebene)
| Variable | Typ | Inhalt | Codierung / Hinweis |
|---|---|---|---|
| `pop_gesamt` | double | Gesamtscore Video | auf Videoebene berechnet (vor Periodenaggregation); `.` = nicht klassifiziert |
| `pop_<dimension>` | double | Teildimensionen | **Namen nach Schema der Pipeline** (z. B. `pop_antielite`, `pop_volk`, …) |
| `pop_klass` | byte | Populismus klassifiziert | 1/0 |
| `pop_n_seg` | long | Anzahl Segmente | Präzision des Videoscores |
| `pop_n_seg_deskr` | long | davon `deskriptiv` (= 0 gesetzt) | Transparenz der Post-Processing-Regel |
| `pop_run` | str | Run-ID der Klassifikation | aus `runs_registry.csv`; Replikation, Messinvarianz |
| `baseline_stichprobe` | byte | Video gehört zur Baseline-Stichprobe | 1/0; erlaubt Nachrechnen der Kanal-Baseline in Stata |

### Position (Videoebene, nur ab Kriegsbeginn)
| Variable | Typ | Inhalt | Codierung / Hinweis |
|---|---|---|---|
| `pos_russland` | double | Position gegenüber Russland | bipolare Skala, **Wertebereich laut Schema** (z. B. −2 … +2); Richtung im Label |
| `pos_westpolitik` | double | Position gegenüber westlicher Politik | bipolar, wie oben |
| `pos_klass` | byte | Position klassifiziert | 1/0 |
| `pos_run` | str | Run-ID | wie oben |

### Sonstiges
| Variable | Typ | Inhalt | Codierung / Hinweis |
|---|---|---|---|
| `transkript` | byte | Transkript vorhanden | 1/0; Grundlage für Populismus/Position |

*Nicht im Rohdatensatz:* Titel, Beschreibung, Transkripttext (Größe, `strL`). Falls für Stichproben-Checks nötig: separate Datei `videos_texte.dta` mit `video_id`.

---

## Datei 2: `kanaele_roh.dta` (Kanalebene)

### Identifikation
| Variable | Typ | Inhalt | Codierung / Hinweis | Quelle (zu prüfen) |
|---|---|---|---|---|
| `channel_id` | str24 | Kanal-ID | eindeutig, Schlüssel | `channel_metadata_total.json` |
| `kanal_name` | str | Kanalname (Stand Abruf) | | dto. |
| `kanal_erstellt` | %tc | Erstellungsdatum des Kanals | `format="ISO8601"` beim Einlesen (gemischte Formate) | dto. |
| `erstes_video_ts` | %tc | ältestes Video im Datensatz (nach Längenfilter) | Abdeckung der Vorkriegszeit | aus Videodaten |
| `abonnenten` | double | Abonnenten zum Abruf | nur deskriptiv | dto. |
| `kanal_hinweis` | str | Freitext für Sonderfälle | z. B. Umbenennung (NIUS) | manuell |

### Sample
| Variable | Typ | Inhalt | Codierung / Hinweis |
|---|---|---|---|
| `sample_vorkrieg` | byte | aktiv vor 24.02.2022 | 1/0; **Definition „aktiv“ festlegen** (siehe Offene Fragen) |
| `sample_baseline` | byte | Baseline-Populismus vorhanden | 1/0; entspricht `NUR_KANAELE_MIT_BASELINE` |
| `sample_whitelist` | byte | in `frage1_kanal_whitelist.csv` | 1/0; nur falls weiterhin relevant |

### Medientyp
| Variable | Typ | Inhalt | Codierung / Hinweis |
|---|---|---|---|
| `medientyp` | byte | Kategorie | 1 = ÖRR, 2 = traditionelle Medien, 3 = Partei/Politiker, 4 = Creator & alternative Medien |
| `krit_creator` | byte | Kriterium Creator (Newman et al. 2025) | 1/0; `.` = noch nicht codiert |
| `krit_korrektiv` | byte | Kriterium Korrektiv-Anspruch (Holt et al. 2019) | 1/0; `.` = noch nicht codiert |

### Baseline (Vorkrieg)
| Variable | Typ | Inhalt | Codierung / Hinweis |
|---|---|---|---|
| `pop_baseline` | double | Baseline-Populismus | Aggregation Segment → Video → Quartal → Kanal, Quartale gleich gewichtet; wie in `prepare_channel_scores.py` |
| `pop_baseline_n` | long | Anzahl Baseline-Videos | Präzision |
| `pop_baseline_nq` | long | Anzahl Baseline-Quartale | Präzision |
| `ideologie_baseline` | ? | Baseline-Ideologie | **Format laut Klassifikation** (Skala oder Kategorie, siehe Offene Fragen) |

### Datenqualität
| Variable | Typ | Inhalt | Codierung / Hinweis |
|---|---|---|---|
| `api_abbruch` | byte | vom API-Abbruch (~20.000 Videos) betroffen | 1/0 |
| `n_videos_api` | long | Anzahl abgerufener Videos (vor Längenfilter) | |
| `n_videos` | long | Anzahl Videos nach Längenfilter | Abgleich mit `videos_roh` |

---

## Konsistenzprüfungen im Export (Abbruch bei Verstoß)
1. `video_id` eindeutig; `channel_id` in `kanaele_roh` eindeutig.
2. Jede `channel_id` in `videos_roh` existiert in `kanaele_roh`.
3. `dauer_sek` > 180 für alle Videos.
4. `pos_klass` = 1 nur für `upload_ts` ≥ 24.02.2022.
5. `*_klass` = 0 ⇔ zugehöriger Wert `.`.
6. `pop_baseline` aus `kanaele_roh` stimmt mit der Nachberechnung aus den Baseline-Videos überein (Toleranz dokumentieren).
7. Klassifizierte Videos, die im Export fehlen (z. B. durch Längenfilter oder fehlende Metadaten): Anzahl ausweisen.

## Offene Fragen (vor dem Export klären)
1. **Weitere Topics:** Welche sollen hinein (z. B. Nahost, Corona, Migration)? Liegen sie für alle Videos vor oder nur für politische?
2. **Kriegsvideo-Klassifikation:** Für alle Videos oder nur für politische? Falls nur politische: `krieg` = 0 für nicht-politische setzen oder `.`?
3. **Ideologie-Baseline:** Skala oder Kategorie (z. B. links/rechts × unabhängig)?
4. **Definition `sample_vorkrieg`:** erstes Video vor 24.02.2022 oder Mindestaktivität (z. B. ≥ n Videos im Jahr davor)? Entspricht das den „gut 200 Kanälen“?
5. **Abrufdatum:** auf Video- oder nur auf Kanalebene gespeichert?
6. **Live/Premiere:** Sind die Felder in den Rohdaten vorhanden?
7. **Mehrfachklassifikationen:** Gibt es Videos mit mehreren Runs (z. B. korrigierte Runs wie `run_0013_..._corrected`)? Regel: welcher Run gilt?
8. **Populismus-Teildimensionen:** genaue Namen und Wertebereiche laut Schema.
---

## Entscheidungen zur Umsetzung (02.10.2026)
Umgesetzt in `src/youtube_code/step6_auswertung/export_stata_rohdaten.py`, Ausgabe in `outputs/stata_rohdaten/`. Wo dieser Abschnitt von den Tabellen oben abweicht, gilt dieser Abschnitt.

**Datenquellen:** ausschließlich die Stores (`video_registry`, `screening_state`, `transcripts`, `llm_runs`); immer die Original-Runs (nicht `run_0013_..._corrected.csv`, das nur 0 → NaN gesetzt hatte). Kanal-Population: 427 Kanäle aus `data/samples/russia_longitudinal_v1/channel_sample_provenance.csv`.

**Offene Fragen – Antworten:**
1. **Topics:** `topic_corona`, `topic_migration`, `topic_wirtschaft`, `topic_energie` aus `video_topic_relevance` (Stichwortsuche in Titel/Beschreibung, für alle Videos > 180 s, nicht nur politische); gemeinsames Kennzeichen `topic_klass`, dazu `topic_nur_titel` (Beschreibung fehlte).
2. **Krieg:** `krieg` = `is_relevant` für `russia_ukraine_war` (alle Videos); `krieg_quelle` = Trefferstufen (`ukr_core_title`, `ukr_wide_desc` …), so dass core/wide im Do-File getrennt werden kann. **Zusätzlich** `krieg_transkript` (≥ 1 Segment mit `ukraine_bezug` im Populismus-Prompt; `.` ohne Populismus-Klassifikation) und `pop_n_seg_ukraine`.
3. **Ideologie-Baseline:** zwei Skalen statt einer Variable: `ideo_gesellschaft_baseline` (−2 progressiv … +2 konservativ) und `ideo_wirtschaft_baseline` (−2 Umverteilung … +2 marktliberal), dazu `ideo_baseline_n`. Nur Baseline-Fenster-Videos (`interval_index` −1…3), ohne Kriegsvideos (`krieg` = 1 oder `krieg_transkript` = 1 ausgeschlossen); Segment → Video → Kanal.
4. **`sample_vorkrieg`** = in der Frage-1-Whitelist (279) UND ≥ 1 Video > 180 s in [24.02.2021, 24.02.2022).
5. **Abrufdatum:** nirgends gespeichert → `abruf_ts` durchgehend `.`.
6. **Live/Premiere:** nur `live_broadcast_content` vorhanden (durchgehend „none“) → `live_typ` durchgehend `.`.
7. **Mehrfachklassifikationen:** Deduplizierung auf Segmentebene (`video_id`, `segment_index`): Segmente ohne `parse_error` vor fehlerhaften, danach neuester Run. `pop_run`/`pos_run` listen alle beteiligten Runs (`;`-getrennt).
8. **Populismus-Dimensionen:** `pop_volk`, `pop_antielite`, `pop_manich`, `pop_emotion` (je 0–3); `pop_gesamt` = Mittel der ersten drei.

**Weitere Abweichungen:**
- `pop_n_seg_deskr` entfällt (Populismus kennt keinen Status `deskriptiv`); stattdessen `pop_n_seg_nichtkodierbar` (`kodierbar` = false → Werte `.`). Die Regel `deskriptiv` = 0 betrifft nur die Position: `pos_n_seg_deskr_rus`, `pos_n_seg_deskr_west`, `pos_n_seg`.
- **Medientyp:** Rohcodes der Excel 3 (Alternatives Medium) → 4 und 4 (Politiker/Partei) → 3; Rohcode 5 (Der Dunkle Parabelritter, WALULIS) → 1 ÖRR mit Vermerk in `kanal_hinweis`.
- **`politisch`** aus YouTube-`topic_categories` (Politics), nicht aus dem LLM-Screening (`politics_final`).
- **Prüfung 4** weist nur die Anzahl aus: positionsklassifizierte Videos vor Kriegsbeginn bleiben drin.
- **Prüfung 5** wird in Richtung „`*_klass` = 0 ⇒ Wert `.`“ erzwungen; klassifizierte Videos mit `.` (z. B. alle Segmente nicht kodierbar/nicht thematisiert) werden nur gezählt.
- **`baseline_stichprobe`** ist die einzige Verwendung von `interval_index`; alle übrigen Zeitbezüge kommen aus `published_at`.
- **`api_abbruch`** = 1 für die 10 Kanäle mit Flag `playlist_limit`; der Abbruch gilt durch das yt-dlp-Nachscraping (01.10.2026) als behoben, das Kennzeichen bleibt für Robustheitschecks erhalten.
- Zählwerte, die fehlen können (`pop_n_seg`, `pos_n_seg` …), werden als `long` mit `.` geschrieben; Kennzeichen als `byte` mit `.`; Wertelabels werden direkt in die `.dta` geschrieben.

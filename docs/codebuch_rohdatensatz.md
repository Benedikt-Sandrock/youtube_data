# Codebuch Rohdatensatz (Entwurf)
Stand: 02.10.2026, ergänzt 13.10. und 14.10.2026 (letzte Abschnitte) · Zweck: Export aus Python → Stata, Grundlage für alle Do-Files (Blöcke 1–3, ggf. Lerntest)

## Grundsätze
- **Zwei Dateien**, Verknüpfung im Do-File über `merge m:1 channel_id`:
  - `videos_roh.dta` – eine Zeile pro Video
  - `kanaele_roh.dta` – eine Zeile pro Kanal
- **Population Videos:** alle Videos aller Kanäle in `kanaele_roh.dta` (seit 13.10.2026 ohne Längenfilter, Kennzeichen `min_dauer`; siehe letzter Abschnitt). Kein Zeitfenster-Filter im Export, das Analysefenster wird im Do-File gesetzt.
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
| `topic_*` | byte | weitere Topics | je Topic 1/0/`.`; Liste siehe Entscheidungen zur Umsetzung, Punkt 1 |

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
1. **Topics:** alle Themen aus `step3_topic_relevance/topic_keywords.TOPIC_KEYWORDS` außer dem Krieg (Stand 05.10.2026: `topic_politik` (politics_general, nur Abgrenzung „politisch“), `topic_corona`, `topic_migration`, `topic_wirtschaft`, `topic_energie`, `topic_klima`, `topic_gender`, `topic_nahost`, `topic_iran`, `topic_eu`, `topic_usa`, `topic_bildung`) aus `video_topic_relevance` (Stichwortsuche in Titel/Beschreibung, core+wide, für alle Videos > 180 s, nicht nur politische). Gemeinsames Kennzeichen `topic_klass` = 1 nur, wenn **alle** Vergleichsthemen klassifiziert sind; die Themen stammen aus verschiedenen Klassifikationsläufen über verschiedene Videomengen, daher kann ein einzelnes `topic_*` auch bei `topic_klass` = 0 gesetzt sein (je Topic `.` = nicht klassifiziert). Dazu `topic_nur_titel` (Beschreibung fehlte; aus dem ersten klassifizierten Thema). Zu jedem Topic und zu `krieg` zusätzlich `<name>_core` (z. B. `topic_klima_core`, `krieg_core`): 1 nur bei Treffer in der core-Liste (Titel oder Beschreibung), gleiche Missings wie die core+wide-Variable. Laut `topic_keywords.py` für Kontrastanalysen core als Themendefinition bevorzugen, core+wide als Robustheit (wide-Listen von Klima/Gender enthalten Kampfbegriffe).
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

---

## Änderungen 13.10.2026: `videos_roh` als Hauptdatensatz
Gilt vor allen Abschnitten oben, wo sie abweichen. `videos_roh.dta` ersetzt damit auch `scripts/adhoc/output/kriegspraemie/videos_kriegspraemie.dta` (aus `step8_targeted_analysis/preparation.py`).

**Population Videos:** alle Videos der Sample-Kanäle, **kein Längenfilter** mehr (vorher Dauer > 180 s). Stattdessen gibt es das Kennzeichen `min_dauer` (1 = `dauer_sek` ≥ 181; unbekannte Dauer → 0).
- **LLM-Analysen (`pop_*`, `pos_*`, `krieg_transkript`) immer mit `if min_dauer == 1`.** Die Werte sind auch für ca. 11.400 kürzere Videos bzw. Videos ohne Dauer exportiert (roh). Kurze Ukraine-Clips aus einer alten Kriegsvideo-Liste hatten in AP 1 einen scheinbaren Rückgang des Populismus nach Kriegsbeginn erzeugt.
- **Kanalgrößen unverändert auf `min_dauer == 1`:** `n_videos`, `erstes_video_ts`, `sample_vorkrieg`, `baseline_stichprobe`, `pop_baseline*`, `ideo_*_baseline`. Neu ist `n_videos_alle` (alle Längen); es ersetzt `n_videos_api`.

**Topics nur aus dem Titel:** `rel_<topic>_core` (nur core-Liste = Hauptdefinition) und `rel_<topic>_cw` (core oder wide = Robustheit) für alle Themen in `topic_keywords.TOPIC_KEYWORDS`. Die Werte werden live aus den Regexen (`KW_RE`) berechnet und decken alle Videos ab; die Namen sind identisch mit `videos_kriegspraemie`. Ein fehlender Titel ergibt 0.
- **Entfallen** sind `krieg`, `krieg_klass`, `krieg_quelle`, `krieg_core`, `topic_*`, `topic_*_core`, `topic_klass` und `topic_nur_titel` (Titel + Beschreibung aus `video_topic_relevance`, nur > 180 s). Intern wird `video_topic_relevance[russia_ukraine_war]` nur noch für den Kriegsausschluss in der Ideologie-Baseline gelesen, damit diese unverändert bleibt.
- Mapping zu `videos_kriegspraemie`: `rel_russia_ukraine_war_core` ↔ früher ungefähr `krieg_core`, aber nur Titel.
- **`rel_politics_general_*` ab Version v2 (2026-10-14):** Die Listen enthalten jetzt auch Österreich (Parteien, Nationalrat, Landeshauptmann, Spitzenpolitiker) und den Parlamentsbetrieb (`62. Sitzung`, Ausschuss, Fragestunde, Abgeordnete). Gegenüber v1 kommen titelbasiert ca. +11 k core- und +16 k cw-Treffer hinzu, v. a. bei OE24.TV, FPÖ TV, Krone und Deutscher Bundestag. Ein Export vor diesem Datum enthält noch v1.

**Videoformat** (Tabelle `video_format`, `step1_sample/channel_video_formats.py`):
- `format`: short/long/live; leer = nicht zugeordnet.
- `format_quelle`: `api_UULF`/`api_UUSH`/`api_UULV`/`ytdlp_*`.
- `format_klass` = 1, wenn der letzte Laufstatus des Kanals `komplett` ist (alle `data/channel_lists/video_formats/*_formats_status.csv`) **und** das Video im Format-Fenster [01.01.2021, 01.07.2026) liegt.
- `format_derived` = 1: WELT-Videos ohne Format im Fenster, per Ausschluss als `long` gesetzt (yt-dlp `/videos` endet ca. Juli 2025, Shorts/Livestreams sind vollständig). Das betrifft sehr viele WELT-Videos (Teiltest 13.10.2026: 43.075 von 63.191) und kann gelöschte/private Videos einschließen. Robustheit: ohne `format_derived == 1`.
- Kanalebene: `format_status` (letzter Status, `fehlt` = nie abgefragt) und `format_liste` (0 keine, 1 upload-starke Kanäle, 2 `alt_kanaele`, 3 `weitere_kanaele`, seit 14.10.2026).
- **Stand Export 13.10.2026 (nach Formatlauf für alle 427 Kanäle):** 424 Kanäle `komplett`, OE24.TV `unvollstaendig` (Livestream-Tab endet zu früh, 73 ältere Videos ohne Format → alle OE24-Videos haben `format_klass` = 0, obwohl `format` fast überall gesetzt ist), WDR aktuell und ZyproX `fehler` (Kanal gelöscht, 404). `format_klass` = 1 bei 1.043.754 von 1.093.796 Videos; davon 11.536 ohne Format (vermutlich gelöschte/private Videos). Der Formatlauf hat auch Videos ab 01.01.2021 in die Registry nachgetragen (vorher ab 24.02.2021); dadurch verschieben sich bei wenigen Kanälen `erstes_video_ts` und `n_videos`.
- `live_typ` entfällt (war durchgehend `.`); Livestreams erkennt man jetzt über `format == "live"`.

**Sendungen:** `news_show` (ganze Nachrichtensendung), `special_show` (Sondersendung/Themen-Update) und `pk_sitzung` (Pressekonferenz, Regierungsbefragung/Fragestunde oder ganzer Bundestags-Sitzungstag; seit 14.10.2026, nur Jung & Naiv, Deutscher Bundestag, AfD-Fraktion) per Titelmuster aus `step3_topic_relevance/news_show_patterns.py`. Die drei Kennzeichen schließen sich aus. Sie gelten nur für Kanäle mit geprüften Mustern (`format_liste` > 0), sonst `.`. **Teaser-Regel:** Auch Shorts/kurze Videos, deren Titel mehrere Meldungen aufzählt, zählen als `news_show`; die Muster hängen nicht von der Dauer ab. Für die Liste 3 (`weitere_kanaele.csv`, 10 Kanäle) sind die Muster auf allen Formaten geprüft, für die Listen 1 und 2 nur auf long-Videos. Für LLM-Variablen gilt ohnehin `min_dauer == 1`, Teaser sind nur für View-Analysen relevant. Hinweis NIUS: „| NIUS Live“-Videos sind bewusst `news_show = 0` (long = Einzelthema-Segmente).

**Weitere Variablen:**
- `titel` (strL)
- `post_war` (1 = `upload_ts` ≥ 24.02.2022)
- `monat` (`%tm`, UTC)

Aus `videos_kriegspraemie` umbenannt bzw. verlagert:
- `view_count`/`like_count`/`comment_count` → `views`/`likes`/`kommentare`
- `duration_sec` → `dauer_sek`
- `published_at` → `upload_ts`
- `channel_title` → `kanal_name` (in `kanaele_roh`)
- `alt_kanal` → `format_liste == 2` (in `kanaele_roh`)

**Konsistenzprüfungen, angepasst:**
- Prüfung 3: `min_dauer` = (`dauer_sek` ≥ 181) und `baseline_stichprobe = 1 ⇒ min_dauer = 1`.
- Prüfung 7 zählt klassifizierte Videos mit `min_dauer = 0` sowie klassifizierte Videos außerhalb der Sample-Kanäle.
- Neu: `rel_*_core = 1 ⇒ rel_*_cw = 1`; `format` ∈ {short, long, live, leer}; `format_derived = 1 ⇒ format = long`; `news_show`/`special_show`/`pk_sitzung` = `.` genau bei `format_liste = 0`; `news_show + special_show + pk_sitzung ≤ 1`.

---

## Änderungen 14.10.2026: Kanaltypologie (`kanaele_roh`)
Manuelle Typologie der 279 Whitelist-Kanäle. Quelle: `data/external/kanal_typologie.csv`. Die Grenzfallprüfung vom 14.10.2026 (Kriterien, 22 Umcodierungen, dokumentierte Abweichungen) steht in `scripts/adhoc/outputs/kanal_typologie_grenzfaelle.md` (Skript `scripts/adhoc/kanal_typologie_grenzfaelle.py`). Nicht-Whitelist-Kanäle haben `.`.

### Variablen
| Variable | Typ | Inhalt | Codierung / Hinweis |
|---|---|---|---|
| `kanaltyp` | byte | Kanaltyp | Zehnerstelle = Gruppe, Einerstelle = Typ (11 = A1 … 34 = C4), Wertelabels mit Code und Kurzname; `.` = nicht Whitelist |
| `kanaltyp_gruppe` | byte | Obergruppe | 1 = A Etablierte Medien, 2 = B Politisch-alternativ & Akteure, 3 = C Themenkanäle |
| `kanaltyp_subtyp` | str | Subtyp | Freitext (ca. 230 Ausprägungen), nur deskriptiv, nicht als Analysevariable |
| `kanaltyp_org` | str | Organisationsform | Freitext (Einzelperson, ÖRR, Privates Medienhaus, Anonym …), nur deskriptiv |
| `kanaltyp_sicher` | byte | Sicherheit der Zuordnung | 1 = hoch, 2 = mittel, 3 = niedrig (nach Grenzfallprüfung keine `niedrig` mehr) |
| `sample_kern` | byte | Kernstichprobe | 1 = `kanaltyp` ∈ {A1, A2, A5, B1, B2, B3, C1} und kein Einzelausschluss (Kurbel TV, umgewidmeter Kanal); Stand 14.10.2026: 174 Kanäle, davon 125 mit `sample_vorkrieg` |

### Typen
| Code | Typ | Definition | n (Whitelist) |
|---|---|---|---|
| A1 | ÖRR-Nachrichten | Nachrichtenkanäle öffentlich-rechtlicher Anstalten (tagesschau, ZDFheute, phoenix, Regional-Nachrichten) | 9 |
| A2 | Private Nachrichten | Nachrichtenangebote privater Medienhäuser (TV, überregionale Presse, Boulevard) inkl. AT/CH | 20 |
| A3 | Private Nachrichten regional/lokal | Lokal-/Regional-TV und Regionalzeitungen | 8 |
| A4 | Auslandsrundfunk | Staatlicher/internationaler Auslandsrundfunk (DW, TRT, euronews) | 3 |
| A5 | Magazin/Reportage/Doku | Magazin-, Reportage-, Doku- und Erklärformate etablierter Häuser inkl. funk | 17 |
| A6 | Satire & Comedy | Politsatire, Kabarett, Comedy etablierter Häuser | 12 |
| A7 | Unterhaltung/Sport/Kinder | Unterhaltungs-, Sport- und Kinderprogramm etablierter Häuser | 7 |
| A8 | Senderhauptkanal Mischprogramm | Hauptkanäle von Sendern mit gemischtem Programm (ARD, WDR, SWR, HR, rbb, MDR), kein reines Nachrichtenangebot | 6 |
| B1 | Alternative Portale | Alternative Nachrichten- und Meinungsportale: redaktionelle Marke oder mehrere Köpfe (inkl. Personality-Formate eines Portals) | 27 |
| B2 | Einzelkommentatoren/Journalisten-Creator | Identifizierbare Einzelperson ohne politisches Mandat mit überwiegend politischem Kommentar, auch Aktivisten | 55 |
| B3 | Anonyme Politikkanäle | Politischer Content ohne identifizierbare verantwortliche Person (Kompilationen, Clips, Demo-Livestreams) | 19 |
| B4 | Parteien/Politiker/Organisationen | Absender ist Partei/Fraktion, Person mit politischem Amt/Mandat als Hauptrolle im Untersuchungszeitraum oder Organisation (NGO, Thinktank, Verband, Parlament) | 22 |
| C1 | Wirtschaft & Finanzen | Wirtschaft/Finanzen als roter Faden, auch mit politischer Rahmung (Krisennarrative) | 28 |
| C2 | Wissen/Bildung/Technik | Wissen, Bildung, Recht, Technik, Geschichte | 17 |
| C3 | Unterhaltung/Reaction/Podcasts | Unterhaltung, Reaction, Streamer, Interview-Podcasts ohne politischen Schwerpunkt | 18 |
| C4 | Lifestyle/Coaching/Esoterik | Lifestyle, Coaching, Esoterik, Alternativmedizin, Themenfremdes | 11 |

### Zuordnungsregeln
- Entscheidend ist der überwiegende Inhalt des Kanals (Titelstichprobe), nicht Name oder Selbstbeschreibung.
- **B4 vs. B2:** Ausschlaggebend ist, wer sendet, nicht wofür jemand bekannt ist. Kurzzeitige Kandidaturen (Grosz, Otte 2022) reichen nicht für B4.
- **B1 vs. B2:** redaktionelle Marke / mehrere Köpfe vs. Einzelperson. **B3:** keine identifizierbare Person.
- **B2 vs. B3 (Präzisierung 15.10.2026, bisher nur in `data/external/channels.xlsx` umgesetzt):** Entscheidend ist das Format, nicht der Name im Impressum. Eigener Kommentar einer wiederkehrenden Person (Klarname oder festes Pseudonym/Künstlername) → B2; überwiegend neu verpacktes Fremdmaterial (Clips, Kompilationen, Aggregatoren, Demo-Livestreams) → B3, auch wenn ein Impressum eine Person nennt. Kanäle mit nur geringem Politikanteil gehen nach C3/C4. Umgesetzt: HABITAT, Meinungsmache, Politik & Co, Politik mit Kopf, Vindex - Shorts, Der kleine Nihilist, Der Schattenmacher, imp → B2; BOSS DELUXE, Neuste.news → C3; GELDDRUCKER → C4.
- **C1 vs. B2:** Finanzbezug als roter Faden → C1; Politik ohne Finanzbezug → B2.

### Hinweise für Analysen
- **Abweichungen zu `medientyp`** sind gewollt und dokumentiert: Serge Menga (B2, `medientyp` Partei/Politiker; `medientyp` bewusst unverändert, damit Frage-1-Ergebnisse stabil bleiben), exxpressTV (B1, traditionell), Schweinfurter Nachrichten (A3, Creator), B4-Organisationen, Gysi-Kanäle und Peter Boehringer (B4, Creator). Die Kreuztabelle steht in `export_log.txt` (Prüfung 8).
- **B3** hat nur 3 Kanäle mit `sample_vorkrieg` (ohne Kurbel TV). Für Vergleiche innerhalb von Kanälen vor/nach Kriegsbeginn ist B3 praktisch leer; geeignet ist es für Neueintritte und Marktanteile.
- **Typen nicht vollständig exogen:** Die Zuordnung beruht auf Titeln aus dem gesamten Zeitraum. Kanäle, die sich erst nach 2022 politisiert haben (z. B. Krissy Rieger, mym by Simo), sind nach ihrem späteren Profil typisiert.
- Oli, Olli und MENTALE FITNESS werden möglicherweise von einem Betreiber gespeist (`kanal_hinweis`).
- Ideologisch ist die Typologie stark mit `ideo_*_baseline` verknüpft (B-Typen überwiegend rechts, A-Typen links). Typunterschiede sind daher nicht ohne Ideologiekontrolle als Medientyp-Effekt zu lesen.

### Konsistenzprüfung 8 (neu)
`kanaltyp` gesetzt genau bei `sample_whitelist = 1`; `kanaltyp_gruppe` = Zehnerstelle von `kanaltyp`; `sample_kern = 1 ⇒ kanaltyp` ∈ Kerntypen. Zusätzlich beim Laden: `channel_id` eindeutig, nur bekannte Typcodes und Sicherheitsstufen.

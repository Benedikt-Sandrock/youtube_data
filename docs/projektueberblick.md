# Projektüberblick Masterarbeit

Teil 1 von 3: Datenentstehung und Datenbestand. Stand: 05.11.2026.

| Session | Inhalt | Status |
|---|---|---|
| 1 | Wie sind die Daten entstanden, welche Daten gibt es, wo sind Lücken? | dieses Dokument |
| 2 | Auswertungen, Forschungsrichtungen, Abbrüche | offen, Einstieg in Abschnitt 9 |
| 3 | Befunde bewerten, in einer Woche analysierbare Fragestellungen vorschlagen | offen |

**Kennzeichnung der Herkunft**

- **[G]** geprüft: in dieser Session aus Daten oder Code nachgerechnet bzw. gelesen.
- **[D]** nur aus der Dokumentation (README, Codebuch, Pläne, Log), nicht nachgerechnet.
- **[E]** eigene Einschätzung auf Basis von [G] und [D].

`.claude/plans/masterarbeit_strategie.md` gilt nicht mehr. Stellen aus dieser Datei sind höchstens historischer Beleg. Die übrigen Pläne können ebenfalls überholt sein.

---

## 1. Das Wichtigste

1. **Der zentrale Datensatz ist für die Metadaten aktuell.** Videos, Views, Likes, Kommentare und Formatwerte stimmen mit den Stores überein. Nur die Variable `transkript` hinkt nach (8.430 Videos). Ein Neu-Export ist für die Kernvariablen nicht fällig (Abschnitt 2).
2. **Auf diesem Rechner fehlen wichtige Dateien.** `outputs/llm_results/` (bezahlte LLM-Ergebnisse, laut README nicht regenerierbar), fast der ganze Inhalt von `outputs/segment_analysis/`, `kanal_typologie.csv` und die meisten Format-Statusdateien sind nicht da. In den naheliegenden Ordnern habe ich sie nicht gefunden. Ein Neu-Export würde hier scheitern, und Session 2 kann die älteren Berichte nicht lesen, solange der Verbleib ungeklärt ist.
3. **Die LLM-Stichprobe ist nach Medientyp und Zeit stark selektiert.** Nach Kriegsbeginn haben 92 % der populismuscodierten Videos traditioneller Medien einen Kriegstitel, bei rechten alternativen Kanälen 50 %, bei mittleren 33 %. Vor Kriegsbeginn sind es unter 7 %. Ein Vor-/Nachher-Vergleich vergleicht deshalb auch andere Videotypen (Abschnitt 6).
4. **Die Titelverzerrung ist jetzt beziffert.** Gegen die blinde Segmentcodierung (24.02.–30.04.2022) findet die Titel-Stichwortsuche 81 % der Kriegsvideos bei traditionellen Medien, 63 % beim ÖRR, 39 % bei linken und 19 % bei rechten alternativen Kanälen (Abschnitt 7).
5. **Auch `politisch` misst ungleich.** Die YouTube-Kategorie erfasst 86 % der inhaltlich politischen Videos beim ÖRR, aber nur 44 % bei rechten alternativen Kanälen. Das ist eine zweite grobe Verzerrung neben den Titeln (Abschnitt 7).
6. **`format == "long"` bedeutet nicht „langes Video“.** 37 % aller long-Videos sind höchstens 3 Minuten lang, bei traditionellen Medien 61 %. Formate von Sendungen sind nur für 34 Kanäle erfasst. Eine durchgehende Variable für Genre oder Talkformat gibt es nicht (Abschnitt 5).
7. **Das Kanal-Sample ist nach Erfolg am Ende gezogen.** Es besteht aus Kanälen, die heute über 50.000 Abonnenten haben. Die Suche lief über Parteinamen, nicht über Russland oder Ukraine. Das Kanalwachstum bei rechten alternativen Kanälen (47 aktive Kanäle 2019, 107 im Jahr 2025) ist deshalb zum Teil Auswahl (Abschnitt 4).
8. **Die brauchbarste Vergleichsgruppe ist manuell gepflegt und schlecht dokumentiert.** `channels_check.xlsx` trennt Unterhaltung, Regionales und Ausland heraus, steht aber nicht im Export oder Codebuch. Der aktuelle Filter (`media_category` 1, 2, 5) schließt linke und mittlere alternative Kanäle aus. Ein Vergleich rechts gegen links ist damit nicht möglich (Abschnitt 4).

---

## 2. Aktualität des zentralen Datensatzes

**Urteil [E]:** Für Metadaten, Format, Titelthemen und LLM-Werte ist kein Neu-Export nötig. Er wäre nötig, wenn (a) `transkript` genutzt wird oder (b) die Angebotscodierung, die Keyword-Themen oder `channels_check` in den zentralen Datensatz sollen. Fall (b) ist nach der Projektregel eigentlich offen, die Entscheidung liegt bei dir. Ein Export wurde nicht gestartet.

| Prüfpunkt | Ergebnis | Herkunft |
|---|---|---|
| Erzeugt | `videos_roh.dta` 28.10.2026 11:57, `kanaele_roh.dta` 12:01 (Stata-Zeitstempel) | [G] |
| Umfang | 1.295.830 Videos, 69 Variablen; 437 Kanäle, 32 Variablen; passt zu `export_log.txt` | [G] |
| Videomenge | Registry und dta identisch (je 1.295.830 IDs, 0 Abweichungen) | [G] |
| Views, Likes, Kommentare | 0 Abweichungen zur Registry | [G] |
| Format | Werte gleich. Bei 4.175 WELT-Videos 2022 fehlt in der dta nur `format_quelle` = `ausschluss_long`; als `long` zählen sie schon über die Export-Regel | [G] |
| Transkripte | dta 68.761, Store 77.191 in Sample-Kanälen: 8.430 neu, davon 8.247 aus Kriegsbeginn bis Ende 2022 (überwiegend Juni bis Oktober), fast nur Alt. rechts, traditionell, ÖRR | [G] |
| LLM-Runs | letzter Run 07.09.2026; Anzahl je Prompt (14/10/13) passt zum Log | [G] |
| Keywords und Sendungsmuster | Dateidatum 22.10.2026, also vor dem Export; nur Datum geprüft | [G] |
| Whitelist, Typologie | lokal nicht vorhanden, nicht vergleichbar; Kennzeichen nur in der dta | [G] |
| Nicht im Export | Angebotscodierung, Keyword-Segmentthemen, Kommentare, `channels_check.xlsx` | [G] |

**Warum ein Neu-Export hier scheitern würde [G, aus Code, nicht ausgeführt]:** `export_stata_rohdaten.py` liest die Whitelist (Zeile 673), die Typologie (547), `auffaelligkeiten.csv` (713) und die Status-CSVs. Die LLM-Ergebnisse kommen über `results_path` aus dem Laufregister. Alle 37 registrierten Segment-Ergebnisdateien fehlen.

**Fehlende Dateien auf diesem Rechner [G]**

- `outputs/llm_results/` (kompletter Ordner)
- `outputs/segment_analysis/*` (nur zwei Plot-Ordner sind da), darunter `frage1_kanal_whitelist.csv`, `channel_video_populism.csv`, `README.md` und die Berichte
- `data/external/kanal_typologie.csv`
- `data/channel_lists/video_formats/`: `weitere_kanaele.csv` und alle Statusdateien außer `alt_kanaele` und `upload_starke_kanaele`
- `scripts/adhoc/output/topic_vids_per_channel.csv`

Gesucht habe ich bis Tiefe 4–5 in `PycharmProjects`, `Documents`, `Desktop` und `OneDrive*`. Der Ordner `PycharmProjects/backup` wurde dabei mit durchsucht, ohne Treffer. `_backups/` im Repo existiert nicht. Die Dateien sind git-ignoriert, also nicht über Git wiederherstellbar. Ob sie auf einem anderen Rechner oder Laufwerk liegen, weiß ich nicht.

---

## 3. Pipeline je Schritt

### Schritt 1: Sample

- **Eingang:** Suchbegriffe und Zeiträume. Maßgeblich für das Sample sind die sieben Begriffe AfD, BSW, CDU, Die Grünen, Die Linke, FDP, SPD [G]. Sie liefern 51.883 Suchtreffer im Store. Die Laufzeiten sind nur kommentiert (Parteien 2021–2026, BSW ab 07/2023) [D].
- **Verfahren:** YouTube-Suche, Sprachklassifikation, Kanal-Metadaten, dann Filter „deutsch und über 50.000 Abonnenten“ (`build_channel_provenance.py`) [G]. Danach alle Videos dieser Kanäle per API, bei großen Kanälen ergänzt per yt-dlp [D].
- **Ergebnis [G]:** 8.642 entdeckte Kanäle → 4.241 deutschsprachig → 3.244 mit Metadaten → 437 im Sample (Stand 14.10.2026). Die Registry enthält insgesamt 2.577.223 Videos, davon 1.295.830 aus dem Sample. Daten reichen bis 30.06.2026.
- **Abdeckung:** Abgefragt wurden Videos ab 2021 für alle Kanäle [D]. Für 2019–2020 liegen nur Metadaten vor, und nur für 347 vor 2021 gegründete Kanäle [D]. Die Upload-Playlist ist auf etwa 20.000 Einträge gekappt, zehn Kanäle wurden nachgescrapt (`api_abbruch`) [D].
- **Verzerrungen:**
  - Die Abonnentenschwelle gilt für den heutigen Stand. Gewachsene Kanäle sind drin, gleich kleine erfolglose nicht [E].
  - Gelöschte Kanäle und Videos fehlen [D]. WDR aktuell und ZyproX sind bereits verschwunden [D].
  - Die Suche über Parteinamen bevorzugt Kanäle, die Parteien in Titel oder Beschreibung nennen [E]. Sie bringt trotzdem Unterhaltung ins Sample, z. B. Gronkh, TryReact, inKev [G].
  - Der Name `russia_longitudinal_v1` führt in die Irre, und `COMPLETE_PROCESS.md` nennt die Parteibegriffe nicht [G].
  - Yt-dlp kann Tabs still zu früh beenden; ältere `komplett`-Läufe können unvollständig sein [D]. WELT hatte so Lücken, die teils nachgetragen wurden [D].

### Schritt 2: Baseline und Politik-Screening

- **Eingang:** Upload-Historie, Titel und Beschreibungen.
- **Verfahren:** Aktivitätsphasen bestimmen das Baseline-Fenster: die zwölf Monate vor Kriegsbeginn oder, wenn keine Phase den Kriegsbeginn abdeckt, ein Ersatzfenster nach Kriegsbeginn (`interval_index` −1) [D]. Gemini 2.5 Flash klassifiziert zweistufig erst Titel, dann Beschreibung. Ziel sind 10–12 politische Videos je Zelle [D].
- **Ergebnis [G]:** 767.291 Zeilen im State, 256.331 davon gelabelt (93.012 politisch, 147.901 nicht, 15.418 unklar).
- **Abdeckung [G]:** 409 von 437 Kanälen. 310 haben `sample_baseline`. Bei 77 davon stammt der Wert aus weniger als fünf Videos.
- **Verzerrungen:**
  - Titel-Screening lässt Videos mit unklarem Titel eher durchfallen; alternative Kanäle dürften stärker betroffen sein [E, nicht geprüft].
  - Ersatzfenster sind ungleich verteilt: 41 rechte alternative Kanäle haben solche Zeilen, dagegen 2 traditionelle und 8 ÖRR. Bei 25 rechten Kanälen stammt die genutzte Baseline überwiegend aus Videos nach Kriegsbeginn, beim ÖRR bei 4, bei traditionellen Medien bei 2 [G]. Dort misst die „Baseline“ Nachkriegsinhalte.
  - Die Fenster nicht neu berechnen: Die Ergänzung um 2019–2020 könnte Aktivitätsphasen verschieben [D].

### Schritt 3: Themen

- **Eingang:** Titel und Beschreibungen, im Export nur Titel.
- **Verfahren:** Regex-Listen je Thema (13 Themen, je core und wide). `video_topic_relevance` nutzt Titel + Beschreibung; `rel_*` im Export wird live aus dem Titel berechnet [G]. Dazu `news_show`, `special_show`, `pk_sitzung` per kanalspezifischer Titelmuster [D].
- **Ergebnis:** `rel_*` für alle Videos [G]. Kriegstitel: 48.880 core, 76.811 core oder wide [D, Log].
- **Abdeckung:** `video_topic_relevance` für Ukraine: 662.716 Videos [G], nur über 180 s [D]. Laut README für `politics_general` teils noch Version 1 und alte Boilerplate-Bereinigung [D].
- **Verzerrungen:** siehe Abschnitt 7. Keyword-Kriegsvideos dienen in Schritt 4 und 7 auch als Auswahlgrundlage, die Verzerrung pflanzt sich also fort [G].

### Schritt 4: Transkripte

- **Eingang:** Video-IDs aus den Zielauswahlen (Baseline, Zellenauffüllung, Kriegszeiträume).
- **Verfahren:** `youtube_transcript_api`, seit Einführung der Formatvariable nur `format == long` [D]. Damit gilt nicht mehr die 181-Sekunden-Regel, sodass auch kurze Clips Transkripte bekommen [G].
- **Ergebnis [G]:** 100.548 Abrufversuche, 91.384 erfolgreich, 77.191 davon im Sample.
- **Abdeckung [G]:** Für 10 % der long-Videos ab dem Vorkriegsjahr gab es einen Abrufversuch, für 2019–2020 keinen. Erfolgsquote nach Versuch: ÖRR 80 %, Alt. ohne Ideologie 77 %, traditionell 92 %, Alt. rechts 98 %.
- **Verzerrungen:** Auswahl nach Kriegsbezug und Politiklabel, nicht zufällig [G]. Fehlschläge treffen ÖRR stärker als rechte Kanäle [G]. Von den Fehlversuchen im gesamten Store sind 4.312 „Kein Transkript“, weitere 4.852 haben einen sonstigen Fehlerstatus; ob diese gehäuft nach Zeit oder Kanal auftreten, habe ich nicht geprüft [G].

### Schritt 5: LLM-Kodierung (Gemini)

- **Eingang:** Transkripte, zerlegt in Segmente von etwa 800 Wörtern. Höchstens 12 Segmente je Video laut Konfiguration; für Ideologie 3.000 Wörter aus vier Ausschnitten [G, aktueller Code; ältere Runs nicht geprüft].
- **Verfahren:** Prompts `POPULISMUS_P`, `POSITION_V1`, `IDEOLOGIE_I`, alle Gemini 2.5 Flash [G], ohne Thinking-Budget [D]. Alle Runs liefen zwischen 25.08. und 07.09.2026, das Modell ist also einheitlich [G]. Prompt-Versionen je Run habe ich nicht verglichen.
- **Ergebnis:** Populismus 36.605 Videos im Export, davon 25.161 mit `min_dauer` = 1 [G]. Position 35.648 [D, Log]. Ideologie als Kanalwert für 348 Kanäle [G].
- **Abdeckung:** siehe Abschnitt 6.
- **Verzerrungen:**
  - Keine Validierung gegen Handkodierung auffindbar: Das Schritt-5-README nennt sie offen, und `outputs/segment_analysis/` konnte ich nicht durchsuchen [G/D].
  - 861 populismuscodierte Videos haben keinen Wert, und 11.444 codierte Videos sind wegen `min_dauer` = 0 von Analysen ausgeschlossen [D, Log].
  - Position hat 2.670 Videos vor Kriegsbeginn [D, Log].
  - Der Prompt gibt Kontext aus dem Vorsegment; die Angebotsstudie nicht. Ergebnisse sind nicht direkt vergleichbar [D].

### Schritt 6: Export und Auswertung

- **Eingang:** Stores und manuelle Dateien.
- **Verfahren:** `export_stata_rohdaten.py`, Details im Codebuch. Auswertungen sind Thema von Session 2.
- **Ergebnis:** `videos_roh.dta`, `kanaele_roh.dta` [G].
- **Hinweise:**
  - `abruf_ts` ist durchgehend leer. Das Abrufdatum der Views ist nicht gespeichert, die Werte stammen aus unterschiedlichen Abrufwellen [G/D].
  - Views sind kumuliert. 2019–2020 wurde laut Doku erst im Oktober 2026 abgerufen [D]. Vergleiche über die Zeit brauchen deshalb Vorsicht.
  - Die älteren Tabellen im Codebuch sind teils überholt; die Abschnitte am Ende gelten vor. Es nennt z. B. noch 427 Kanäle [G].

### Schritt 7: Kommentare

- **Eingang:** Video-IDs, ausgewählt über Kriegsbezug und Kanallisten.
- **Verfahren:** YouTube-API, nur Top-Level-Kommentare [G].
- **Ergebnis [G]:** 16,63 Mio. Kommentare, 58.880 Videos mit Status OK, 57.687 Abrufversuche im Sample über 385 Kanäle.
- **Abdeckung [G]:** 94 % der Versuche sind long-Videos, 29 % haben einen Kriegstitel. 19.348 stammen aus Kriegsbeginn bis Ende 2022, nur 5.926 aus dem Vorkriegsjahr und keine aus 2019–2020.
- **Verzerrungen:** keine Zufallsauswahl, Schwerpunkt auf Alt. rechts (19.245) und traditionell (14.800) [G]. Ein Zweck für die Forschungsfragen ist laut README offen [D]. Einmaliger Abruf, keine Zeitreihe [D].

### Zusatzdaten: Angebotsstudie und Keyword-Segmente

Beide laufen außerhalb der nummerierten Pipeline und außerhalb des Exports.

**Angebotsstudie (Claude Sonnet)**

- Blinde Codierung von Transkriptsegmenten ohne Kanal, Datum oder Titel, Codebuch 2.0 [D].
- 34 Kanäle: 11 alternativ links, 13 alternativ rechts, 5 ÖRR, 5 traditionell [G].
- 4.548 Videos und 9.214 Segmente aus dem 01.01.–30.04.2022 [G]. Ziehung bis 21 Videos je Kanal-Woche und vier Segmente je Video [G].
- Ergebnisdateien reichen bis Batch 186. Die Erweiterung auf Juni bis Oktober 2022 ist geplant, die Transkripte sind größtenteils geladen, Codierergebnisse liegen hier nicht [G]. Der Mai fehlt absichtlich [D].
- Grenzen [G]: Die Kanalauswahl ist nicht repräsentativ. Bei „alternativ rechts“ stammen 722 von 1.619 Videos aus vier dem Namen nach finanznahen Kanälen (Erfolgskanal, FinanzmarktWelt, Kettner, Marc Friedrich). Die Videos sind in meinen Zahlen ungewichtet. Das Modell ist selbst nicht gegen Menschen validiert; für 28 Videos gibt es ein Handkennzeichen (`hand`), die Auswertung habe ich nicht geprüft.

**Keyword-Segmente (Lexikon und logistische Regression)**

- Auf der Angebotscodierung trainiert und im Kanal-Holdout gegen sie geprüft (nur Januar bis April 2022, also Übereinstimmung mit dem LLM, nicht mit Menschen): Krieg auf Videoebene F1 0,94, alternative Kanäle 0,87–0,88, etablierte 0,96 [D, Bericht].
- Kriegsaspekte sind deutlich schwächer und bei alternativen Kanälen oft unbrauchbar (z. B. Finanzhilfe F1 0,16–0,20) [D, Bericht].
- Angewendet auf 14.806 Videos aus 27.568 gezogenen IDs; Schwerpunkt 05–10/2022 [D, Bericht].
- Für Mai bis Oktober 2022 nicht validiert. Der Bericht rät, nur große Verschiebungen zu werten [D].

---

## 4. Sample-Abgrenzungen

### Kanäle je Abgrenzung

Gruppen nach `marktanteil_rohdaten_plots.py`: `medientyp` und bei alternativen Kanälen `ideo_gesellschaft_baseline` mit Schnitten bei ±0,5. Die Zeilen „ohne Ideologie“ und „ohne Zuordnung“ habe ich ergänzt, damit alle 437 Kanäle sichtbar sind. [G]

| Gruppe | alle | `sample_vorkrieg` | `sample_baseline` | `sample_whitelist` | `sample_kern` | Plots-Filter* |
|---|---:|---:|---:|---:|---:|---:|
| ÖRR | 60 | 52 | 42 | 44 | 24 | 15 |
| Traditionell | 44 | 41 | 37 | 38 | 23 | 22 |
| Alt. links | 68 | 59 | 62 | 40 | 23 | 0 |
| Alt. mitte | 67 | 56 | 58 | 48 | 23 | 0 |
| Alt. rechts | 107 | 66 | 89 | 84 | 75 | 78 |
| Alt. ohne Ideologie | 60 | 38 | 4 | 9 | 5 | 10 |
| Partei/Politiker | 19 | 17 | 18 | 16 | 1 | 2 |
| Ohne Zuordnung | 12 | 5 | 0 | 0 | 0 | 5 |
| **Summe** | **437** | **334** | **310** | **279** | **174** | **132** |

\* `channels_check.xlsx`: `media_category` ∈ {1, 2, 5}, `sample` ∈ {1, 2, 3}, nicht `foreign`; so aktuell in `marktanteil_rohdaten_plots.py`.

### Wie gut sind die Abgrenzungen?

| Abgrenzung | Definition | Stärke | Problem [E, soweit nicht markiert] |
|---|---|---|---|
| Alle 437 | deutsch, über 50.000 Abos heute | vollständig | enthält Gaming, Reaction, Lifestyle; keine sinnvolle Vergleichsbasis |
| `sample_vorkrieg` | mindestens ein long-Video im Jahr vor Kriegsbeginn | klar, prüfbar | sehr schwach: ein Video genügt, Unterhaltung bleibt drin; bleibt Auswahl nach heutigem Erfolg |
| `sample_baseline` | Baseline-Populismus vorhanden | direkt für FF1 | hängt an der Download- und LLM-Auswahl; auch Ersatzfenster nach Kriegsbeginn |
| `sample_whitelist` | mindestens 5 Kriegsvideos und 5 Populismuswerte | für FF1 ausreichend besetzt | **Auswahl auf die untersuchte Sache:** Kriegsstichwörter messen je Medientyp ungleich. Kanäle mit wenig Kriegsinhalt fallen raus (laut Codebuch 97 von 112) |
| `sample_kern` | Typologie A1, A2, A5, B1, B2, B3, C1 | inhaltlich am besten erklärt, Codebuch vorhanden | nur Whitelist-Kanäle; typisiert über den Gesamtzeitraum, daher nicht exogen; C1 mischt Finanzkanäle zu den politischen. Typ und Ideologie hängen eng zusammen [D] |
| `channels_check.sample` | manuell: 1 News, 2 Recherche/Doku, 3 regional, 4 Clips, 5 unpolitische Doku | trennt das Unterhaltungsproblem am direktesten; auch nicht-Whitelist-Kanäle | **nicht im Export oder Codebuch**; Kriterien nur teils dokumentiert. Der Codebuch-Reiter nennt die `media_category`-Werte 3, 4, 6 und `sample` 7 nicht [G] |

`media_category` entspricht den Daten nach: 3 = alt. links, 4 = alt. mitte, 6 = Partei/Politiker [G: Kreuztabelle, 68 von 69 bzw. 67 von 68]. Das ist meine Lesart und sollte bestätigt werden.

### Vorläufiger Vorschlag für Session 3 [E]

Für Vergleiche über Medientypen scheint am ehesten geeignet: `sample` ∈ {1, 2, 3}, nicht `foreign`, `sample_vorkrieg` = 1, alle Medienkategorien einschließlich links und mitte. Das ergibt 123 Kanäle [G]:

| Kategorie | Kanäle | davon mindestens 5 / 10 Populismuswerte vor und nach Kriegsbeginn | Finanzkanal-Flag | Typ C1 |
|---|---:|---:|---:|---:|
| ÖRR | 15 | 12 / 9 | 0 | 0 |
| Traditionell | 20 | 12 / 6 | 0 | 0 |
| Alt. links | 17 | 13 / 7 | 0 | 3 |
| Alt. mitte | 16 | 14 / 8 | 2 | 4 |
| Alt. rechts | 55 | 44 / 27 | 4 | 10 |

Noch ungeklärt: Ist die Einordnung von links und mitte in `sample` so sorgfältig geprüft wie die von rechts? `foreign` nimmt zudem AUF1, exxpressTV, ServusTV und OE24 heraus, was für rechte Medien inhaltlich relevant sein kann.

### Weitere Vergleichsprobleme [G]

- **Kanäle treten neu ein.** Aktive Kanäle mit mindestens einem long-Video:

  | Jahr | ÖRR | Traditionell | Alt. links | Alt. mitte | Alt. rechts |
  |---|---:|---:|---:|---:|---:|
  | 2019 | 42 | 38 | 44 | 44 | 47 |
  | 2021 | 51 | 41 | 59 | 56 | 65 |
  | 2023 | 54 | 44 | 65 | 64 | 88 |
  | 2025 | 57 | 43 | 65 | 66 | 107 |

  28 der 107 rechten Kanäle wurden nach Kriegsbeginn gegründet, beim ÖRR 7 von 60, bei traditionellen Medien 1 von 44.

- **Finanzkanäle sind uneinheitlich markiert.** `finanzkanal` trifft 15 Kanäle, Typ C1 28. Die nach long-Views größten alternativen Kanäle im Plots-Filter sind Aktien mit Kopf (10,6 %) und Vermietertagebuch (8,4 %). Beide und auch Erfolgskanal und Kettner sind dem Namen nach finanznah, tragen aber kein `finanzkanal`-Flag. Rechnet man nur mit dem Flag, wirkt der Finanzanteil daher vermutlich zu klein (Views 1–6 %) [E].
- **Politisierung über die Zeit.** YouTube-`politisch` steigt bei long-Videos rechter Kanäle von 37 % (Vorkriegsjahr) auf 74 % (2025), bei „ohne Ideologie“ von 1 % auf 28 %. Das kann echte Politisierung, Eintritt neuer Kanäle oder ein Messartefakt der Kategorie sein; ich habe es nicht getrennt.
- **Konzentration.** Die zehn größten Kanäle stellen 38 % aller long-Videos (WELT 68.869, euronews 62.206, OE24 52.556). Die drei größten stellen beim ÖRR 47 %, bei traditionellen Medien 40 %, bei Alt. rechts 14 %.
- **Ideologie ist dünn gemessen.** Unter den Kanälen mit Wert stützen sich 7 von 46 ÖRR, 3 von 40 traditionellen, 14 von 68 Alt. links, 10 von 67 Alt. mitte und 11 von 107 Alt. rechts auf weniger als fünf Videos. Gruppen „links, mitte, rechts“ sind feste Schnitte auf einer unvalidierten LLM-Skala. Für 89 der 437 Kanäle gibt es keinen Wert.

---

## 5. Videoformat und Formatvariablen

### Variablen im Datensatz

| Variable | Inhalt | Güte |
|---|---|---|
| `format` | short, long, live, aus Kanal-Playlists | gut als technisches Format. 96,1 % mit `format_klass` = 1; 13.744 ohne Wert [G]. **Kein Maß für die Länge oder das Genre** |
| `format_klass` | Formatlauf des Kanals vollständig | OE24 ist komplett 0 (47.915 Videos), obwohl fast überall ein Format steht [G] |
| `format_derived` | WELT per Ausschluss long | 43.042 Videos [G], kann gelöschte Videos enthalten [D]. Robustheit prüfen |
| `dauer_sek`, `min_dauer` | Dauer; Kennzeichen ab 181 s | zuverlässig bis auf Einzelfälle: 2 Videos über 2 Tage, 151 mit Dauer 0 [G] |
| `news_show`, `special_show`, `pk_sitzung` | Ganzsendung, Sondersendung, Pressekonferenz per Titel | gut für 34 Kanäle, sonst `.`. Geprüft für Liste 3 auf allen Formaten, Listen 1 und 2 nur auf long [D] |
| `politisch` | YouTube-Kategorie Politics | siehe Abschnitt 7: hohe Präzision, ungleiche Trefferquote |
| `kanaltyp`, `channels_check.sample` | Kanalebene | keine Videoebene; Kanäle sind nicht einheitlich in einem Format |

**Fehlt:** Talkshow oder Interview als Kategorie. Talkshows zählen als Einzelthema (etwa 1.900 long-Videos der upload-starken Kanäle) [D]. Eine einheitliche Genrevariable gibt es nicht.

### Format und Dauer passen nur grob zusammen [G]

| Format | Videos | Median Dauer | Anmerkung |
|---|---:|---:|---|
| long | 961.643 | 5,3 min | 85.959 bis 60 s, 268.167 von 61 bis 180 s: zusammen **37 %** |
| short | 270.368 | 49 s | 61.707 von 61 bis 180 s; `min_dauer` = 1 nur bei 250 |
| live | 50.075 | 52 min | 49.610 mit `min_dauer` = 1. Sie kommen also in LLM-Analysen vor, wenn nur `min_dauer` filtert (1.675 codiert) |
| leer | 13.744 | 5,3 min | v. a. WDR aktuell, BR24, ZyproX; steigt ab 2023. Vermutlich gelöschte oder private Videos [D] |

Das hat zwei Folgen:

- `FORMAT = long` (Marktanteile) und `min_dauer == 1` (LLM) grenzen **verschiedene Grundgesamtheiten** ab.
- Der neue Transkriptfilter folgt `format`, sodass kurze Clips dazukommen. In der Angebotsstudie sind nur 51,5 % der traditionellen Videos mindestens 181 s lang, gegenüber 99 % bei Alt. links [G].

### Was je Gruppe hochgeladen wird [G]

| Gruppe | long bis 3 min | 3–10 min | 10–30 min | über 30 min | Median long (Vorkrieg → 2026) | Shorts-Anteil 2021 → 2025 |
|---|---:|---:|---:|---:|---:|---:|
| ÖRR | 16,7 % | 45,5 % | 24,7 % | 13,0 % | 7,0 → 7,7 min | 5,7 → 29,6 % |
| Traditionell | **61,2 %** | 22,2 % | 11,7 % | 4,8 % | 2,0 → 2,8 min | 0,4 → 17,5 % |
| Alt. links | 8,6 % | 27,9 % | 42,0 % | 21,5 % | 13,4 → 17,1 min | 1,9 → 43,4 % |
| Alt. mitte | 20,4 % | 32,0 % | 32,5 % | 15,1 % | 7,8 → 14,5 min | 4,2 → 50,9 % |
| Alt. rechts | 7,7 % | 40,9 % | 40,0 % | 11,4 % | 9,4 → 12,1 min | 1,5 → 33,2 % |
| Partei/Politiker | 19,8 % | 51,2 % | 11,2 % | 17,8 % | 4,8 → 6,0 min | 4,7 → 23,8 % |

**Einschätzung [E]:** Traditionelle Medien laden überwiegend Kurzclips hoch, alternative Kanäle längere Einzelformate. Ein Vergleich von Video-Views je Gruppe vergleicht daher auch Formate. Sinnvoll sind getrennte Dauerklassen oder Vergleiche auf Zellen wie Kanal × Monat × Dauerklasse. Der steigende Shorts-Anteil verschiebt zudem den Inhalt der long-Stichprobe im Zeitverlauf.

**Abdeckung der Sendungsmuster [G]:** Anteil der long-Videos aus Kanälen mit geprüften Mustern: ÖRR 55 %, traditionell 54 %, Alt. rechts 38 %, Partei 37 %, Alt. mitte 17 %, Alt. links 15 %.

---

## 6. Fallzahlen

Alle Zahlen [G], aus `videos_roh.dta` und `kanaele_roh.dta` vom 28.10.2026.

### Videos nach Format und Jahr

| Jahr | long | short | live | leer | gesamt | Herkunft |
|---|---:|---:|---:|---:|---:|---|
| 2019 | 77.822 | 180 | 1.979 | 0 | 79.981 | nur Metadaten |
| 2020 | 99.619 | 397 | 6.996 | 0 | 107.012 | nur Metadaten, Corona-Jahr |
| 2021 | 115.842 | 3.127 | 6.833 | 265 | 126.067 | LLM möglich |
| 2022 | 128.681 | 12.266 | 6.364 | 331 | 147.642 | |
| 2023 | 130.415 | 42.621 | 6.412 | 1.642 | 181.090 | |
| 2024 | 148.961 | 68.018 | 7.705 | 4.575 | 229.259 | |
| 2025 | 175.852 | 88.857 | 8.747 | 4.838 | 278.294 | |
| 2026 (bis 30.06.) | 84.451 | 54.902 | 5.039 | 2.091 | 146.483 | Halbjahr |
| **Summe** | **961.643** | **270.368** | **50.075** | **13.744** | **1.295.830** | inkl. 2 ohne Datum |

### long-Videos nach Gruppe und Zeitraum

| Gruppe | 2019–20 | 01.01.–23.02.21 | Vorkriegsjahr | Krieg bis 12/22 | 2023 | 2024 | 2025 | 2026 H1 | gesamt |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ÖRR | 25.852 | 1.945 | 14.520 | 12.978 | 15.006 | 15.766 | 20.207 | 9.914 | 116.188 |
| Traditionell | 93.161 | 8.377 | 60.155 | 55.757 | 59.952 | 64.007 | 76.057 | 36.728 | 454.194 |
| Alt. links | 10.456 | 1.029 | 6.573 | 6.801 | 9.997 | 10.727 | 11.468 | 4.930 | 61.981 |
| Alt. mitte | 17.651 | 1.655 | 11.266 | 10.381 | 11.187 | 11.945 | 11.372 | 5.002 | 80.459 |
| Alt. rechts | 14.161 | 1.897 | 12.638 | 12.924 | 18.646 | 26.930 | 33.947 | 17.581 | 138.724 |
| Alt. ohne Ideologie | 7.963 | 967 | 7.642 | 6.847 | 10.454 | 12.540 | 14.160 | 6.085 | 66.658 |
| Partei/Politiker | 7.866 | 640 | 4.468 | 4.356 | 4.429 | 4.928 | 5.441 | 2.709 | 34.837 |
| Ohne Zuordnung | 331 | 30 | 307 | 370 | 744 | 2.118 | 3.200 | 1.502 | 8.602 |

Formatsummen je Gruppe:

| Gruppe | long | short | live | leer |
|---|---:|---:|---:|---:|
| ÖRR | 116.188 | 29.594 | 13.516 | 5.965 |
| Traditionell | 454.194 | 51.559 | 16.044 | 1.312 |
| Alt. links | 61.981 | 28.713 | 1.995 | 822 |
| Alt. mitte | 80.459 | 36.900 | 6.215 | 267 |
| Alt. rechts | 138.724 | 56.634 | 7.935 | 3.653 |
| Alt. ohne Ideologie | 66.658 | 57.208 | 2.107 | 1.680 |
| Partei/Politiker | 34.837 | 5.670 | 2.013 | 39 |

### Abgrenzungen in Videos

| Abgrenzung | Kanäle | Videos | long | Populismus (`min_dauer` = 1) |
|---|---:|---:|---:|---:|
| Alle | 437 | 1.295.830 | 961.643 | 25.161 |
| `sample_vorkrieg` | 334 | 1.119.273 | 893.376 | 22.579 |
| `sample_whitelist` | 279 | 1.094.445 | 839.566 | 24.607 |
| `sample_kern` | 174 | 757.029 | 579.455 | 20.353 |
| Plots-Filter | 132 | 666.083 | 538.537 | 15.885 |

### Transkripte und Populismus nach Gruppe und Zeitraum (`min_dauer` = 1)

Zelle: Transkripte in der dta / Populismus-Videos. Vor 2021 gibt es keine LLM-Werte.

| Gruppe | Vorkriegsjahr | Krieg bis 12/22 | 2023 | 2024 | 2025 | 2026 H1 |
|---|---:|---:|---:|---:|---:|---:|
| ÖRR | 1.233 / 327 | 1.918 / 561 | 1.362 / 890 | 1.362 / 834 | 1.770 / 1.222 | 561 / 373 |
| Traditionell | 1.504 / 289 | 2.393 / 686 | 1.847 / 1.332 | 1.927 / 1.402 | 4.423 / 3.824 | 1.020 / 771 |
| Alt. links | 1.034 / 525 | 910 / 431 | 827 / 473 | 1.141 / 641 | 1.247 / 766 | 620 / 377 |
| Alt. mitte | 983 / 462 | 906 / 538 | 800 / 401 | 707 / 327 | 824 / 416 | 335 / 137 |
| Alt. rechts | 2.119 / 631 | 2.751 / 932 | 1.847 / 864 | 2.345 / 1.001 | 2.796 / 1.598 | 1.358 / 696 |
| Alt. ohne Ideologie | 14 / 11 | 25 / 9 | 112 / 87 | 142 / 84 | 293 / 205 | 104 / 51 |
| Partei/Politiker | 465 / 184 | 403 / 249 | 315 / 177 | 336 / 148 | 310 / 163 | 149 / 65 |

### Die LLM-Auswahl ist nicht zufällig

Abdeckung von long-Videos mit `min_dauer` = 1:

| Zeitraum | ohne Kriegstitel: Videos, Populismus-Anteil | mit Kriegstitel: Videos, Populismus-Anteil |
|---|---:|---:|
| Vorkriegsjahr | 66.273, 3,4 % | 1.135, 4,3 % |
| Krieg bis 12/22 | 59.214, 2,8 % | 7.663, **20,6 %** |
| 2023 | 77.144, 1,8 % | 5.136, 50,8 % |
| 2024 | 95.100, 1,4 % | 5.011, 55,5 % |
| 2025 | 117.339, 1,5 % | 8.102, **70,0 %** |
| 2026 H1 | 58.691, 1,4 % | 2.894, 50,1 % |

Zusammensetzung der populismuscodierten Videos:

| Gruppe | vor Krieg: n, Kriegstitel | nach Krieg: n, Kriegstitel | nach Krieg: YouTube-politisch |
|---|---:|---:|---:|
| ÖRR | 327, 3 % | 3.880, 77 % | 85 % |
| Traditionell | 289, 5 % | 8.015, **92 %** | 96 % |
| Alt. links | 525, 1 % | 2.688, 48 % | 87 % |
| Alt. mitte | 462, 1 % | 1.819, **33 %** | 64 % |
| Alt. rechts | 631, 2 % | 5.091, 50 % | 80 % |
| Partei/Politiker | 185, 7 % | 802, 42 % | 98 % |

**Einschätzung [E]:** Das ist für die Forschungsfragen 1 und 3 die wichtigste Datengrenze.

- Vor dem Krieg stehen meist ausgewählte politische Baseline-Videos, nach dem Krieg meist titelerkannte Kriegsvideos, und zwar je Medientyp in anderem Verhältnis.
- Die Abdeckung der Kriegsvideos steigt von 21 % (2022) auf 70 % (2025). Ausgerechnet das Kernjahr 2022 ist am dünnsten besetzt.
- Mittelwerte aus Populismuswerten sind daher keine Schätzung für das gesamte politische Angebot eines Kanals. Vergleiche müssen auf dasselbe Inhaltsprofil beschränkt oder neu gewichtet werden. Kriegsvideos vor Kriegsbeginn gibt es nur wenige.

### Panelfähigkeit (Populismus, `min_dauer` = 1)

Kanäle mit mindestens n codierten Videos vor **und** nach Kriegsbeginn:

| Gruppe | Kanäle | n ≥ 1 | n ≥ 5 | n ≥ 10 | n ≥ 20 | Median vor / nach |
|---|---:|---:|---:|---:|---:|---:|
| ÖRR | 60 | 37 | 27 | 15 | 2 | 3 / 13 |
| Traditionell | 44 | 35 | 23 | 10 | 2 | 6 / 34,5 |
| Alt. links | 68 | 45 | 27 | 16 | 2 | 9 / 6 |
| Alt. mitte | 67 | 47 | 34 | 19 | 2 | 9 / 15 |
| Alt. rechts | 107 | 59 | 47 | 28 | 2 | 6 / 25 |
| Alt. ohne Ideologie | 60 | 5 | 0 | 0 | 0 | 0 / 0 |
| Partei/Politiker | 19 | 17 | 15 | 6 | 3 | 7 / 25 |

Kurze Zeitfenster sind damit oft zu dünn: Im Quartal 2022Q2 haben z. B. nur 22 linke und 28 traditionelle Kanäle überhaupt Populismuswerte; im Vorkriegsquartal 2021Q3 sind es 43 und 17.

---

## 7. Messgüte: Titelstichwörter und `politisch`

Prüfung [G] gegen die blinde Angebotscodierung (Claude Sonnet). Die Codierer sahen weder Kanal noch Titel. Videos vom 24.02. bis 30.04.2022, ungewichtet. „Krieg“ heißt: `krieg_ukraine` ist in mindestens einem Segment des Videos Thema, auch implizit.

| Medientyp | Videos | Krieg laut Codierung | Kriegstitel (core oder wide) | Recall | Precision | Recall nur core |
|---|---:|---:|---:|---:|---:|---:|
| Traditionell | 716 | 65,6 % | 53,4 % | **81 %** | 100 % | 64 % |
| ÖRR | 707 | 84,6 % | 53,5 % | **63 %** | 100 % | 49 % |
| Alt. links | 205 | 47,3 % | 18,5 % | **39 %** | 100 % | 21 % |
| Alt. rechts | 856 | 55,0 % | 10,3 % | **19 %** | 100 % | 10 % |

Mit der strengeren Definition „Krieg ist Hauptthema“ bleibt das Muster bestehen: Recall 87 %, 69 %, 53 % und 28 %; die Precision sinkt bei Alt. rechts auf 67 %.

**Einordnung [E]:**

- Die bekannte Verzerrung ist also groß und in der Richtung bestätigt. Titelbasierte Kriegsanteile unterschätzen alternative Kanäle um ein Vielfaches. Ein Treffer ist fast sicher richtig; das Problem sind die Fehlenden.
- Der Wert gilt für den 24.02. bis 30.04.2022. Für später gibt es keine vergleichbare Prüfung. Auch der Abstand zwischen Medien kann sich verändern, sodass ein konstanter Korrekturfaktor nicht gerechtfertigt ist.
- Innerhalb der Gemini-codierten Videos zeigt sich dasselbe (Titeltreffer unter Videos mit Ukraine-Segment, Nachkrieg bis 2023: traditionell 89 %, ÖRR 77 %, Alt. links 48 %, Alt. rechts 46 %, Alt. mitte 38 %) [G]. Diese Zahlen sind wegen der Auswahl nach Kriegsbezug weniger aussagekräftig.

**`politisch` (YouTube `topic_categories`)** gegen „nicht unpolitisch“ laut Codierung, alle 4.548 Videos:

| Medientyp | inhaltlich politisch | YouTube-politisch | Recall | Precision |
|---|---:|---:|---:|---:|
| ÖRR | 95,6 % | 82,4 % | 86 % | 99 % |
| Traditionell | 76,6 % | 60,6 % | 76 % | 97 % |
| Alt. links | 76,8 % | 50,1 % | 65 % | 99 % |
| Alt. rechts | 89,6 % | 39,0 % | **44 %** | 100 % |
| Alt. rechts ohne vier finanznahe Kanäle | 99,0 % | 64,1 % | 65 % | 100 % |
| Vier finanznahe Kanäle | 78,0 % | 7,9 % | 10 % | 100 % |

**Einordnung [E]:** Die Vergleichsgruppe „politische Videos“ ist nicht neutral. YouTube-`politisch` lässt besonders alternative Kanäle und politisch rahmende Finanzkanäle aus. `rel_politics_general` (Titel, core oder wide) trifft nur 11–19 % der Videos und ist damit als Vollerhebung ungeeignet. Marktanteile unter „politischen Videos“ können dadurch schon im Niveau verzerrt sein. Sollte sich die Trefferquote der Kategorie über die Zeit ändern, wäre auch der Trend betroffen; das habe ich nicht geprüft.

**Bessere Datenbasis für Themen [E]:** Für den begrenzten Zeitraum Januar bis April 2022 die Angebotscodierung; für die Monate danach die Keyword-Segmentklassifikation mit den genannten Grenzen. Auf den Gesamtzeitraum hochgerechnet gibt es keine gleich gute Messung.

---

## 8. Offene Lücken und Risiken

**Datenbestand**

1. **Verbleib der fehlenden Dateien klären**, vor allem `outputs/llm_results/` (Abschnitt 2). Wenn dies die einzige Kopie war, wäre die dta die letzte Fassung der LLM-Werte auf Videoebene, und die Segmentwerte wären weg. [E]
2. Für `data/store/*.sqlite` gibt es kein Git-Backup [D].
3. Kanäle ohne Werte: 12 ohne `medientyp`, 89 ohne Ideologie, Typologie nur für die Whitelist [G].

**Messung**

4. Keine auffindbare Validierung von Populismus, Position und Ideologie gegen Menschen (Abschnitt 3).
5. Kein Abrufdatum der Views. Ein zweiter Abruf zur Messung des Wachstums fehlt [D]. Abonnentenzahlen gibt es nur als einmaligen Stand [D].
6. Keine durchgehende Variable für Genre, Talk oder Interview [D].
7. Themen hängen außerhalb der Stichproben an Titeln (Abschnitt 7).

**Abdeckung**

8. 2019–2020: nur Metadaten, ausschließlich überlebende Kanäle und Videos, Corona-Sonderlage [D]. Als Vorlauf für Views und Upload-Mengen nutzbar, nicht für Populismus [E].
9. Kernjahr 2022: geringste Abdeckung der Kriegsvideos im Populismus (Abschnitt 6).
10. Angebotscodierung: nur Januar bis April 2022, 34 Kanäle.
11. Kommentare: keine Zufallsstichprobe, Zweck offen.

**Dokumentation**

12. `CLAUDE.md`, README und `paths.py` verweisen noch auf `masterarbeit_strategie.md` als geltend [G].
13. `channels_check.xlsx` fehlt im Codebuch, und die Codes 3, 4, 6 und 7 sind unbeschrieben [G].
14. README: „vier Stores“, tatsächlich fünf. Codebuch: alte Kanalzahl 427 [G].
15. Schritt 1 in `COMPLETE_PROCESS.md` nennt die Parteisuche nicht [G].

**Technische Sicherheit**

16. YouTube-API-Schlüssel stehen in Klartext in auskommentiertem Code (`step1_sample/settings_variables.py`, in Git) und in Fehlermeldungen in `comments.sqlite` [G]. Sie sind hier absichtlich nicht wiedergegeben.

**Nicht geprüft in dieser Session**

- Inhalte der Prompts und deren Stabilität im Detail.
- Ob Hand-Stichproben der Angebotsstudie (`hand50_opus_vs_sonnet.csv`) ausgewertet wurden.
- Zeitliche Stabilität der YouTube-Kategorie.
- Vollständigkeit einzelner Kanäle über `format_status` hinaus.
- Korrektheit der Medientyp-Zuordnung je Kanal.
- Do-Files und ihre Filter (Session 2).

---

## 9. Übergabe an Session 2

**Vorab zu klären:** Liegt `outputs/segment_analysis/` (mit `README.md`, Whitelist-Methodik, Berichten zu Frage 1–4) noch irgendwo? Das README nennt ihn als Einstiegspunkt für die Auswertungen. Ohne ihn stützt sich Session 2 auf Code, Pläne und die wenigen lokalen Ergebnisse.

**Vorhandene Quellen für Session 2 [G]**

- `.claude/plans/` (14 Pläne plus Unterordner), `src/youtube_code/step6_auswertung/README.md` (ab Zeile 528 hier nicht gelesen)
- `outputs/masterarbeit/` (6 Dateien; `ap1_selektion`, `ap2_stichprobenbias`)
- `outputs/segment_analysis/plots_marktanteil_rohdaten`, `plots_marktanteil_topics`
- `outputs/stata_analyse/`, `outputs/stata_rohdaten/*.do`
- `outputs/kommentare/medientyp_ueberschneidung/`
- `outputs/kriegsanteil_lag/`, `outputs/video_formats/`
- `data/claude_classification/angebot/` (`plot_results.py`, `plots_*`)
- `scripts/adhoc/` samt `outputs/` und `keyword_klassifikation_segmente/`

**Prüffragen je bisheriger Auswertung** (aus diesem Dokument):

1. Welches Sample? Enthält es Unterhaltungskanäle oder neu eingetretene Kanäle?
2. Welcher Filter: `format`, `min_dauer` oder beides? Sind Dauerklassen oder Sendungen berücksichtigt?
3. Woher kommt die Thema- oder Politik-Abgrenzung (Titel, Titel + Beschreibung, YouTube, Segmentcodierung)? Hängt das Ergebnis von ihrer ungleichen Trefferquote ab?
4. Bei LLM-Werten: Vergleicht die Auswertung vor und nach dem Krieg unterschiedliche Videotypen?
5. Vor oder nach dem 28.10.2026 entstanden? Die neue Definition von `sample_vorkrieg` (334 statt zuvor rund 224 Kanälen) und ältere Sample-Stände (427 statt 437) verändern Zahlen.
6. Bei Views: Spielt das Alter der Videos oder das unbekannte Abrufdatum eine Rolle?

**Reproduktion:** Die Zahlen stammen aus rein lesenden Skripten im Session-Scratchpad; ins Repo wurde außer diesem Dokument nichts geschrieben. Stores wurden über ihre Module gelesen, nicht verändert.

# Plan: Auswertungspipeline "Kanalerfolg" (Forschungsfragen 2–4)

## Context

`outputs/segment_analysis/README.md` und `zentrale_ergebnisse.md` bestätigen:
Forschungsfrage 1 (Populismus/Haltung vor-nach Kriegsbeginn) ist über die
Schritt-6-Pipeline vollständig beantwortet (279-Kanal-Whitelist, Kanal-FE +
Post-Dummy-Regression). Forschungsfragen 2–4 aus `.claude/CLAUDE.md`
(Kanalerfolg, Populismus×Erfolg, Kriegs- vs. andere Videos) sind laut
README **komplett offen** — es fehlt eine Erfolgsmetrik-Auswertung, die
Views/Engagement aus `data/store/video_registry.sqlite` analog zur
bestehenden LLM-Score-Pipeline aufbereitet und mit demselben
Kanal-FE-Regressionsmuster auswertet. Dieser Plan legt fest, wie diese
Lücke geschlossen wird, ohne die bestehende, funktionierende Frage-1-Pipeline
anzufassen.

Zwei zentrale Datenlimitationen wurden in der Exploration festgestellt und
bestimmen das Design:

1. `video_registry.sqlite` speichert Views/Abos nur als **einmaligen
   Snapshot** (COALESCE-Upsert überschreibt nie einen bestehenden Wert) —
   es gibt **keine Zeitreihe für Abonnentenwachstum**. Deshalb: Erfolg wird
   ausschließlich über **Video-Performance** (Views/Engagement pro Video,
   über `published_at` in Vorkriegs-/Nachkriegsperioden einsortiert)
   gemessen; Abo-/Kanalgröße bleibt rein deskriptiver Kontext. Kein neuer
   API-Pull für einen zweiten Snapshot (Nutzerentscheidung).
2. **Erfolgsmetrik-Definition (Nutzerentscheidung, überschreibt eine frühere
   Alters-Normalisierungs-Idee):** Rohe kumulierte `view_count`-Werte und
   Engagement (`like_count`, `comment_count`) werden direkt verwendet, OHNE
   Division durch Tage-seit-Veröffentlichung. Begründung des Nutzers: Die
   meisten Videos sammeln den Großteil ihrer Views innerhalb kurzer Zeit
   nach Veröffentlichung und danach kaum noch etwas — eine
   Views-pro-Tag-Normalisierung würde ältere (längst plateauierte) Videos
   systematisch bestrafen, nur weil der Nenner (verstrichene Tage) weiter
   wächst. Restrisiko (sehr junge Videos nah am Datenabruf haben ihr
   Plateau evtl. noch nicht erreicht) wird als Limitation dokumentiert statt
   modelliert.
3. Stichprobe: dieselbe **Frage-1-Whitelist** (279 Kanäle,
   `outputs/segment_analysis/frage1_kanal_whitelist.csv`) wird wiederverwendet
   — maximale Vergleichbarkeit zwischen allen vier Forschungsfragen, und
   Frage 3/4 brauchen ohnehin Populismus-Score bzw. Kriegsvideo-Flag, die nur
   für diese Whitelist-Kanäle systematisch vorliegen.

## Architekturentscheidung: gemeinsames Modul statt dritter Kopie

`frage1_populismus_bericht.py` und `frage1_stance_bericht.py` sind fast
wortgleiche Kopien (`post_dummy_test()`, `interaktions_test()`,
`aggregiere_kanal_periode()` sind code-identisch). Für Frage 2–4 kommen
jedoch echte neue Bausteine dazu (Populismus-Tertile bei Frage 2, Δ-Δ-Test
bei Frage 3, ein Interaktionstest MIT Haupteffekt bei Frage 4 — siehe unten),
kein reiner Copy-Paste-Fall mehr. **Empfehlung: `post_dummy_test()` und
`interaktions_test()` unverändert aus `frage1_populismus_bericht.py` in ein
neues Geschwistermodul `bericht_utils.py` verschieben**, `frage1_*_bericht.py`
importieren sie künftig von dort (bare sibling import, wie bereits
`fe_signifikanz_test.py` `deskriptiv_aggregation` importiert). Reiner
Funktions-Umzug ohne Verhaltensänderung — Verifikation: beide bestehenden
Frage-1-Berichte laufen lassen, Output-CSVs müssen bitidentisch bleiben.

## Neue/geänderte Dateien

### 1. `src/youtube_code/store/video_registry.py` — neue Funktion `get_video_stats()`

Nach `get_video_metadata()` einfügen (gleiches Chunking-Muster wie
`get_channels()`/`get_video_rows_for_channels()`): `SELECT video_id,
channel_id, channel_title, published_at, view_count, like_count,
comment_count, duration FROM videos WHERE channel_id/video_id IN (...)`.
Docstring erklärt explizit, warum `get_video_metadata()` diese Spalten
bewusst nicht mitliefert und wofür diese neue Funktion gedacht ist
(`prepare_success_metrics.py`).

### 2. `src/youtube_code/step6_auswertung/prepare_success_metrics.py` (neu, Schritt 0c)

Läuft NACH `prepare_channel_scores.py` (0) und `frage1_stichprobe.py` (0b),
als `-m`-Modul wie `prepare_channel_scores.py` (echter Paketimport von dort
für `ergaenze_periodenspalten()`/`relativ_periode()` — nicht duplizieren).

- `_lade_whitelist()` — liest `frage1_kanal_whitelist.csv`.
- `_lade_video_stats(channel_ids)` — ruft `video_registry.get_video_stats()`.
- `_ergaenze_kriegsvideo_flag(df)` — merged
  `video_registry.get_topic_relevance(topic="russia_ukraine_war", ...)`;
  Videos ohne Eintrag gelten explizit als `ist_kriegsvideo = 0`
  ("nicht als kriegsbezogen klassifiziert", nicht "unbekannt" — im Docstring
  festhalten).
- `berechne_erfolgsmetriken(df)`:
  ```python
  df["log_views"] = np.log1p(df["view_count"])
  df["engagement_rate"] = (df["like_count"] + df["comment_count"]) \
                            / df["view_count"].replace(0, np.nan)
  df["age_days"] = (REFERENZDATUM - df["published_at"]).dt.days  # nur Kontext/Diagnose, s.u.
  ```
  **Wichtig — kein `fillna(0)` auf `like_count`/`comment_count`:**
  Beide Spalten sind in `video_registry.sqlite` nullable
  (`video_registry.py:50-52`) und werden nie mit einem Default `0`
  überschrieben (`_to_int()`, `video_registry.py:266-273`; COALESCE-Upsert,
  Docstring `upsert_videos()`). `NULL` kommt roh aus der API
  (`statistics.get("likeCount"/"commentCount")` in `utils/io.py:174-176`
  liefert `None`, wenn YouTube das Feld nicht sendet — typischerweise bei
  deaktivierten Likes/Kommentaren). `NULL` (deaktiviert/unbekannt) und `0`
  (aktiviert, aber niemand hat interagiert) sind inhaltlich verschiedene
  Zustände und dürfen nicht gleichgesetzt werden — ein `fillna(0)` würde
  Kanäle mit deaktivierten Likes/Kommentaren künstlich als "wenig
  Engagement" einstufen statt sie korrekt aus dem Engagement-Vergleich
  auszuschließen. Pandas propagiert `NaN` automatisch durch `+`/`/`, d.h.
  `engagement_rate` wird für betroffene Videos korrekt `NaN`.
  `view_count.replace(0, np.nan)` bleibt (Division durch 0 vermeiden) —
  das betrifft nur `view_count`, nicht die Engagement-Zähler.
  Primäre Dimensionen: `view_count`/`log_views` (Reichweite) und
  `engagement_rate` (likes+comments/views). `age_days` wird NICHT zur
  Normalisierung verwendet, sondern nur für eine spätere
  Sensitivitätsanalyse (Ausschluss sehr junger Videos) mitgeführt.
  Videos mit `view_count is NaN` werden mit Log-Meldung verworfen (Anzahl
  ausgeben, analog bestehender `[...] X -> Y Kanäle`-Meldungen). Zusätzlich
  wird die Anzahl Videos mit `engagement_rate is NaN` geloggt (Format
  `[Label] X -> Y ...`, analog `deskriptiv_aggregation.py:193-194`/`:318`),
  damit die Größenordnung fehlender Like-/Kommentarzahlen sichtbar bleibt.
- `aggregiere_kanal_periode_erfolg(df, spalte_periode)` — Kanal×Periode-
  Aggregation je Dimension:
  ```python
  grouped = df.groupby(["channel_id", "channel_title", spalte_periode], as_index=False).agg(
      view_count=("view_count", "mean"),
      log_views=("log_views", "mean"),
      engagement_rate=("engagement_rate", "mean"),
      view_count_summe=("view_count", "sum"),
      n_videos=("video_id", "count"),
      n_videos_engagement=("engagement_rate", "count"),  # nur Videos mit gueltiger engagement_rate
  )
  grouped["log_views_summe"] = np.log1p(grouped["view_count_summe"])
  ```
  Neben den bisherigen Mittelwert-Dimensionen (`view_count`, `log_views`,
  `engagement_rate`) wird zusätzlich die **Summe aller Views** je
  Kanal×Periode berechnet (`view_count_summe`, davon abgeleitet
  `log_views_summe`), um Kanäle sichtbar zu machen, die durch höhere
  Aktivität (mehr Videos) insgesamt mehr Reichweite erzielen, ohne dass
  der Durchschnitt pro Video steigt (Nutzeranmerkung). `log_views_summe`
  ist `log1p(Summe der Views)`, NICHT die Summe der bereits
  logarithmierten `log_views`-Werte — `log1p(sum(x)) ≠ sum(log1p(x))`.
  `engagement_rate` nutzt weiterhin `mean` (schließt `NaN` automatisch
  aus); die zugehörige Zählspalte ist bewusst dimensionsspezifisch
  (`n_videos_engagement`, zählt nur Nicht-`NaN`-Werte via `count()` — Muster
  analog `prepare_channel_scores.py:339-347`) statt identisch mit dem
  allgemeinen `n_videos`, sonst wäre der Nenner der
  Aggregations-Transparenz irreführend.

**Outputs** (`outputs/segment_analysis/`):
1. `channel_video_erfolg.csv` — Video-Ebene: `channel_id, channel_title,
   video_id, published_at, rel_quartal, rel_monat, view_count, like_count,
   comment_count, log_views, engagement_rate, age_days, ist_kriegsvideo`.
2. `channel_{quartal,monat}_erfolg_timeseries.csv` — long-Format wie die
   bestehenden `channel_{gran}_populism_timeseries.csv`: `channel_id,
   channel_title, rel_{quartal|monat}, dimension ∈ {view_count, log_views,
   engagement_rate, view_count_summe, log_views_summe}, wert, n_videos,
   n_videos_engagement`. Bei `view_count_summe`/`log_views_summe` enthält
   `wert` die Summe (bzw. `log1p` der Summe) statt des Mittelwerts;
   `n_videos_engagement` ist nur bei `dimension == "engagement_rate"`
   relevant (sonst gleich `n_videos`).
3. `channel_erfolg_snapshot.csv` — rein deskriptiver Kanal-Kontext
   (`video_registry.get_channels()`: `subscribers, views, video_count`),
   explizit NICHT Teil der Pre/Post-Regression.

### 3. `bericht_utils.py` (neu) + Anpassung `frage1_populismus_bericht.py`/`frage1_stance_bericht.py`

`post_dummy_test()`/`interaktions_test()` unverändert hierher verschieben,
Frage-1-Skripte importieren sie. Sonst keine Verhaltensänderung.

### 4. `frage2_erfolg_bericht.py` (neu, Schritt 6) — Forschungsfrage 2

Struktur wie `frage1_populismus_bericht.py`, Eingabe
`channel_{quartal,monat}_erfolg_timeseries.csv` (Kanal×Periode-Ebene, da
`view_count_summe`/`log_views_summe` nur dort existieren).
- `DIMENSIONEN = ["log_views", "log_views_summe", "engagement_rate"]`
  (roher `view_count` als Zusatzkontext, `log_views`/`log_views_summe`
  sind die Testgrößen wegen Rechtsschiefe). `log_views_summe` beantwortet
  gezielt die Nutzeranmerkung: ein positiver `post`-Koeffizient bei
  `log_views_summe` OHNE entsprechenden Effekt bei `log_views` deutet auf
  gestiegene Aktivität (mehr Videos, gleicher Durchschnittserfolg pro
  Video) statt auf höheren Durchschnittserfolg hin — dieser Kontrast
  gehört explizit in die Ergebnis-Interpretation.
- `GRUPPEN_SPALTEN` wie Frage 1 (`ideologie_gruppe`, `medientyp`) **plus
  neu `populismus_gruppe`**: Tertile aus
  `channel_classification_populism.csv::populismus_gesamt`
  (`pd.qcut(..., 3, labels=["niedrig","mittel","hoch"])`) — beantwortet
  direkt "Sind populistische Kanäle seit Kriegsbeginn erfolgreicher
  geworden?" über `interaktions_test(df, "log_views", periode,
  "populismus_gruppe", [...])` (und analog für `log_views_summe`).
- Modell (aus `bericht_utils` importiert):
  `y_cm = alpha_c + beta*post_cm + epsilon_cm`, plus Interaktionsvariante
  je Gruppierung — identisch zum Frage-1-Muster.
- Output: `frage2_erfolg_bericht_{granularitaet}.csv`.

### 5. `frage3_populismus_erfolg_bericht.py` (neu, Schritt 7) — Forschungsfrage 3

Populismus-Score liegt nur für LLM-klassifizierte Videos vor, Erfolgsmetrik
für alle Whitelist-Videos — **Merge auf Kanal×Periode-Ebene** (nicht
Video-Ebene), sonst verschenkt man die breite Erfolgs-Stichprobe:
`channel_{gran}_populism_timeseries.csv` (Dimension `populismus_gesamt`)
inner-join `channel_{gran}_erfolg_timeseries.csv` (Dimension `log_views`)
über `channel_id` + Periode. Sample-Schrumpfung vor/nach Merge loggen.

Zwei Bausteine:

**(a) Panel mit Kanal-FE + Perioden-FE (primär):**
```python
smf.ols("log_views ~ populismus_gesamt + C(channel_id) + C(periode)", data=daten)
   .fit(cov_type="cluster", cov_kwds={"groups": daten["channel_id"]})
```
Kontrolliert Kanal-Fixeffekte UND gemeinsame Zeittrends (sonst
Scheinkorrelation durch allgemeines Wachstum). Koeffizient = reine
Innerhalb-Kanal-Korrelation zwischen Populismus-Niveau und Erfolg —
**keine Kausalaussage** (siehe Limitationen).

**(b) Δ-Δ-Korrelation je Kanal (Robustheit/Visualisierung):** je Kanal
`mean(post) - mean(pre)` für `populismus_gesamt` und für `log_views`,
Pearson/Spearman-Korrelation + OLS über alle Kanäle, als Scatterplot.

Output: `frage3_populismus_erfolg_bericht_{granularitaet}.csv`.

### 6. `frage4_kriegsvideos_erfolg_bericht.py` (neu, Schritt 8) — Forschungsfrage 4

`ist_kriegsvideo` ist anders als Ideologie/Medientyp **nicht zeitkonstant je
Kanal** — Kanal-FE absorbieren einen Kriegsvideo-Haupteffekt hier NICHT
automatisch. `interaktions_test()` (ohne Haupteffekt) darf daher nicht
unverändert übernommen werden; neue Funktion mit explizitem Haupteffekt:

```python
def post_kriegsvideo_interaktion_test(df, dimension, spalte_periode):
    daten["post"] = (daten[spalte_periode] >= 0).astype(int)
    smf.ols("y ~ C(channel_id) + post + ist_kriegsvideo + post:ist_kriegsvideo",
            data=daten).fit(cov_type="cluster", cov_kwds={"groups": daten["channel_id"]})
```
`post:ist_kriegsvideo` beantwortet direkt Frage 4. Ergänzend:
`post_dummy_test()` (aus `bericht_utils`, unverändert) getrennt auf den
Teilstichproben {alle Videos, nur Kriegsvideos, nur sonstige Videos} für
einen direkten Effektgrößenvergleich.

`GRANULARITAET = "quartal"` als primäre Spezifikation (Kriegsvideos sind
pro Kanal-Monat oft dünn besetzt), `"monat"` nur als Zusatzcheck, plus
`MIN_VIDEOS_PRO_ZELLE`-Filter analog `deskriptiv_aggregation`.

Output: `frage4_kriegsvideos_erfolg_bericht_{granularitaet}.csv`.

## Reihenfolge (Ergänzung der bestehenden Pipeline-Tabelle)

```
0.  prepare_channel_scores.py            (unveraendert)
0b. frage1_stichprobe.py                 (unveraendert)
0c. prepare_success_metrics.py           NEU
1.  deskriptiv_aggregation.py            (unveraendert)
2a. deskriptiv_plots.py                  (unveraendert)
2b. fe_signifikanz_test.py               (unveraendert)
2c. geglaettete_kurve.py                 (unveraendert)
    bericht_utils.py                     NEU (post_dummy_test/interaktions_test)
5.  frage1_populismus_bericht.py         importiert aus bericht_utils
5b. frage1_stance_bericht.py             importiert aus bericht_utils
6.  frage2_erfolg_bericht.py             NEU — Frage 2
7.  frage3_populismus_erfolg_bericht.py  NEU — Frage 3 (braucht 0 + 0c)
8.  frage4_kriegsvideos_erfolg_bericht.py NEU — Frage 4 (braucht 0c)
```

`prepare_success_metrics.py` läuft als `-m`-Modul; `frage{2,3,4}_*.py` laufen
direkt im Ordner (bare sibling imports, wie `frage1_*_bericht.py`).

## Doku-Updates (Projektregel: READMEs/Docstrings immer mitpflegen)

- `src/youtube_code/step6_auswertung/README.md`: Ablauf-Tabelle um
  0c/6/7/8 + `bericht_utils.py` erweitern.
- `outputs/segment_analysis/zentrale_ergebnisse.md`: Platzhalter-Abschnitt
  "## Forschungsfragen 2–4" durch echte Ergebnisse ersetzen, sobald die
  Berichte gelaufen sind.
- Neue Datei `outputs/segment_analysis/frage2_4_methodik_und_stichprobe.md`
  (analog `frage1_methodik_und_stichprobe.md`): Erfolgsmetrik-Definition
  (kein Alters-Normalisierung, Begründung), Kanal×Periode-Merge-Logik bei
  Frage 3, exakte Modellgleichungen für Frage 2/3/4, Sample-Schrumpfung.
- `video_registry.py`: Docstring von `get_video_metadata()` um Verweis auf
  `get_video_stats()` ergänzen.

## Methodische Limitationen (explizit im Bericht auszuweisen)

1. **Snapshot-Charakter:** Views/Abos sind Einmal-Stand beim ersten
   API-Abruf, keine echte Zeitreihe — "Erfolgsentwicklung" wird über
   Vorkriegs-/Nachkriegs-Videos approximiert, nicht über wiederholte
   Messung desselben Videos.
2. **Kein Fetch-Zeitstempel:** sehr junge Videos (nah am Datenabruf) haben
   ihr View-Plateau evtl. noch nicht erreicht — als Sensitivitätsanalyse
   (nicht als Korrektur im Hauptmodell) eine robuste Variante mit
   Mindestalter-Untergrenze (z. B. Ausschluss der letzten ~60–90 Tage vor
   Referenzdatum) ergänzen.
3. **Frage 3 ist rein korrelativ**, keine exogene Variation für
   Δpopulismus selbst — Kausalitäts-Einschränkung explizit benennen
   (Rückwärtskausalität, gemeinsame Drittvariablen).
4. **Sparsamkeit bei Frage 3/4:** Kanal×Periode-Merge (Frage 3) bzw.
   Kanal×Periode×Kriegsvideo-Aufspaltung (Frage 4) reduziert die effektive
   Stichprobe unter die 279-Kanal-Whitelist — transparent loggen.
5. **Kein zweiter Abo-Snapshot** — Subscriber/Channel-Views bleiben rein
   deskriptiver Kontext, keine Wachstumsmetrik (akzeptierte Einschränkung).

## Verifikation

- `get_video_stats()`: `PYTHONPATH=src python -c "from youtube_code.store import video_registry; print(video_registry.get_video_stats(channel_ids=['<eine Whitelist-ID>']).head())"` — prüft Spalten und Non-Null-Anteil.
- `prepare_success_metrics.py`: nach Lauf `channel_video_erfolg.csv`
  Zeilenzahl mit `865.751` (bekannte Video-Gesamtzahl der 279 Whitelist-
  Kanäle) grob abgleichen, Anteil `view_count`-NaN gegen die bekannten ~99%
  Abdeckung prüfen.
- `engagement_rate`-Berechnung: Stichprobe von Videos mit
  `comment_count is NULL` prüfen — `engagement_rate` muss `NaN` sein,
  nicht `0` oder eine künstlich niedrige Zahl (kein `fillna(0)`-Verhalten).
- `channel_{gran}_erfolg_timeseries.csv`: `n_videos_engagement` muss
  überall `<= n_videos` sein; `log_views_summe` für 2-3 Kanal×Perioden-
  Zeilen von Hand gegen `log1p(view_count_summe)` nachrechnen (Abgrenzung
  zum `log_views`-Mittelwert sicherstellen).
- Refactor `bericht_utils.py`: `frage1_populismus_bericht.py` und
  `frage1_stance_bericht.py` vor/nach dem Umzug laufen lassen, Diff der
  Output-CSVs muss leer sein.
- `frage2/3/4_*_bericht.py`: Konsolen-Output (Koeffizienten, p-Werte,
  n_kanaele) gegen die Stichprobengrößen aus Abschnitt "Limitationen"
  plausibilisieren, dann Ergebnisse in `zentrale_ergebnisse.md` und die neue
  Methodik-Datei übertragen.

**Hinweis zu Testläufen:** Laut `.claude/CLAUDE.md` vorher fragen, bevor
längere/speicherintensive Skript-Läufe (insbesondere `prepare_success_metrics.py`
über 865k Videos) tatsächlich ausgeführt werden.

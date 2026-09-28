# Schritt 3 — Themen-Relevanz-Klassifikation

Klassifiziert Videos nach Themen-Relevanz per Stichwortsuche in Titel und
Beschreibung (`COMPLETE_PROCESS.md` Schritt 3) und schreibt das Ergebnis in
die Tabelle `video_topic_relevance` in `data/store/video_registry.sqlite`.
Fünf Themen: `russia_ukraine_war` (Ukraine-Krieg), `corona_pandemic`,
`migration`, `economy_general`, `energy` — die letzten vier dienen als
Vergleichs-/Kontrollthemen für Forschungsfrage 4 (betrifft eine
Erfolgsveränderung nur Kriegsvideos oder auch andere politische Themen?),
siehe `.claude/plans/new_topics.md`.

## Tabellen-Schema

```sql
CREATE TABLE video_topic_relevance (
    video_id            TEXT NOT NULL,
    topic               TEXT NOT NULL,
    is_relevant         INTEGER,
    matched_keywords    TEXT,   -- JSON-Liste, z.B. ["ukr_core_title", "ukr_wide_desc"]
    title_only          INTEGER, -- 1 = video_details.description fehlt/leer, nur Titel geprueft
    keyword_set_version TEXT,
    classified_at       TEXT,
    PRIMARY KEY (video_id, topic)
)
```

Pro Thema ein eigener `keyword_set_version`-String (siehe
`topic_keywords.KEYWORD_SET_VERSION`, jetzt ein Dict statt eines einzelnen
Strings) — erlaubt, ein einzelnes Thema unabhängig von den anderen vier neu
zu klassifizieren, ohne deren Version ungewollt mitzuändern.

**Nicht zu verwechseln** mit `video_details.topic_relevant_topic_ids` — das ist
eine YouTube-API-eigene Spalte (Freebase-Topic-IDs), inhaltlich unabhängig von
dieser Tabelle. Reine Namensähnlichkeit.

**COALESCE-Richtung:** `upsert_topic_relevance()` lässt einen neuen Wert einen
alten überschreiben (`COALESCE(excluded.col, table.col)`), anders als
`upsert_channels`/`upsert_videos` (dort gewinnt für immer der zuerst
beobachtete Wert). Grund: ein Re-Klassifizierungslauf mit neuer
`keyword_set_version` (z. B. nach Keyword-Erweiterung) muss bestehende Zeilen
überschreiben können.

## Keyword-Quelle

`topic_keywords.py` ist die einzige Stelle, an der neue Skripte diese Muster
importieren sollen. `TOPIC_KEYWORDS` ordnet jedem Thema ein `prefix` (für die
Flag-/Spaltennamen, z. B. `ukr_core_title`) sowie eine `core`- und eine
`wide`-Regex zu.

- **russia_ukraine_war** (`ukr_core`/`ukr_wide`): 1:1 aus
  `src/youtube_code/new_analysis/feasibility.py` übernommen (dort bereits im
  Rahmen der Feasibility-Analyse validiert). `feasibility.py` bleibt
  unverändert. `ukr_risky` (nato/krieg/sanktion/eu) wird bewusst nicht
  übernommen — in `feasibility.py` selbst als "nie für die
  Treatment-Definition, nur Diagnose" markiert.
- **corona_pandemic, migration, economy_general, energy**: neu erarbeitete
  Keyword-Sets (nicht aus dem Archiv übernommen), breite Themenfelder ohne
  enge Ereignisfenster, bewusst ohne hochgradig polyseme Einzelwörter bare
  (z. B. `Grenze`, `Preis`, `Gas`, `Strom`, `Integration`) und ohne
  Politiker-Nachnamen (anders als bei Ukraine/Selenskyj/Putin, da diese
  breitere Themen-Portfolios haben und die Abgrenzung verwischen würden) —
  siehe die FP-Risiko-Kommentare direkt bei den Regex-Konstanten in
  `topic_keywords.py`. Wirtschaft und Energie sind bewusst zwei getrennte
  Themen statt einem gemeinsamen (Sanktionen/Gaspreise/Nord Stream verknüpfen
  sie inhaltlich eng mit dem Ukraine-Krieg); Überschneidungen zwischen Themen
  (v. a. `energy` ∩ `russia_ukraine_war`, `energy` ∩ `economy_general`) sind
  gewollt und werden über die `video_id` x `topic`-Struktur der Tabelle
  abgebildet, nicht durch gegenseitigen Ausschluss der Keyword-Sets
  verhindert.

Titel und Beschreibung werden **getrennt** geprüft und per ODER verknüpft
(`topic_keywords.is_relevant()` = `any(flags.values())` über alle Tiers eines
Themas), nicht konkateniert — spiegelt für `russia_ukraine_war` die
validierte Logik aus `feasibility.py` exakt.

## Boilerplate-Filter

`boilerplate.py` portiert den zweistufigen Boilerplate-Lernprozess aus
`feasibility.py` (`cmd_boilerplate`/`cmd_extract`) auf den Store: pro Kanal
werden aus einer Stichprobe von Videobeschreibungen die Zeilen ermittelt, die
in ≥ `BOILERPLATE_THRESHOLD` (60 %) der Videos wortgleich vorkommen (z. B.
feste Hashtag-Ketten, Spendenblöcke) — diese werden vor dem Keyword-Matching
aus der Beschreibung entfernt. Ohne diesen Filter würden Kanäle mit einer
festen, keyword-haltigen Beschreibungszeile fälschlich zu 100 % als
themenrelevant gelten. `learn_boilerplate()` läuft unabhängig davon, wie
viele Themen klassifiziert werden, nur **einmal** pro geladenem DataFrame.

## Ausführung

```
PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step3_topic_relevance.classify_topic_relevance
```

`classify_topic_relevance.py`: Config-Konstanten am Kopf (`TOPICS_TO_RUN`,
`CHANNEL_FILTER`, `DRY_RUN`). `TOPICS_TO_RUN` steuert, welche Themen aus
`topic_keywords.TOPIC_KEYWORDS` klassifiziert werden (Default: alle fünf) —
für Testläufe auf ein einzelnes Thema einschränken, z. B. `["energy"]`. Erst
mit `DRY_RUN=True` die gedruckte Zusammenfassung/Stichprobe je Thema prüfen,
dann auf `False` setzen.

Ausführungsdauer 9/2/26 für 518k Videos, ein Thema (`russia_ukraine_war`
allein): 1298 Sek. (634 Sek. Boilerplate, 552 Sek. Klassifikation, 112 Sek.
Speicherung). Die Boilerplate-Phase ist unabhängig von der Themenzahl; die
Klassifikations- und Speicherphase skalieren näherungsweise linear mit der
Anzahl der Themen in `TOPICS_TO_RUN`, da jedes Thema eine eigene
Ergebniszeile je Video erzeugt.

## Weiteres Thema ergänzen

Ein neues Thema (z. B. Nahost, `KEYWORDS_MIDDLE_EAST` existiert bereits in
`config/settings.py`) braucht nur einen neuen Eintrag in
`topic_keywords.TOPIC_KEYWORDS` (mit eigenem `prefix`, `core`- und
`wide`-Regex) sowie einen passenden Eintrag in
`topic_keywords.KEYWORD_SET_VERSION` — kein Schema-Umbau in
`video_registry.py` nötig, da die Tabelle generisch über die `topic`-Spalte
funktioniert. `TOPICS_TO_RUN` in `classify_topic_relevance.py` nimmt das neue
Thema automatisch mit auf (Default `list(TOPIC_KEYWORDS.keys())`), sofern es
nicht explizit auf eine Teilmenge eingeschränkt wurde.

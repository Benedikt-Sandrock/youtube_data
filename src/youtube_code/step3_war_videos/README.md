# Schritt 3 — Kriegsvideo-Identifikation

Klassifiziert Videos nach Themen-Relevanz per Stichwortsuche in Titel und
Beschreibung (`COMPLETE_PROCESS.md` Schritt 3) und schreibt das Ergebnis in
die neue Tabelle `video_topic_relevance` in `data/store/video_registry.sqlite`.

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

Die Regex-Muster (`ukr_core`/`ukr_wide`) in `topic_keywords.py` sind 1:1 aus
`src/youtube_code/new_analysis/feasibility.py` übernommen (dort bereits im
Rahmen der Feasibility-Analyse validiert). `feasibility.py` bleibt
unverändert — `topic_keywords.py` ist die einzige Stelle, an der neue Skripte
diese Muster importieren sollen. `ukr_risky` (nato/krieg/sanktion/eu) wird
bewusst nicht übernommen — in `feasibility.py` selbst als "nie für die
Treatment-Definition, nur Diagnose" markiert.

Titel und Beschreibung werden **getrennt** geprüft und per ODER verknüpft
(`topic_keywords.is_relevant()`), nicht konkateniert — spiegelt die validierte
Logik aus `feasibility.py` exakt.

## Boilerplate-Filter

`boilerplate.py` portiert den zweistufigen Boilerplate-Lernprozess aus
`feasibility.py` (`cmd_boilerplate`/`cmd_extract`) auf den Store: pro Kanal
werden aus einer Stichprobe von Videobeschreibungen die Zeilen ermittelt, die
in ≥ `BOILERPLATE_THRESHOLD` (60 %) der Videos wortgleich vorkommen (z. B.
feste Hashtag-Ketten, Spendenblöcke) — diese werden vor dem Keyword-Matching
aus der Beschreibung entfernt. Ohne diesen Filter würden Kanäle mit einer
festen, keyword-haltigen Beschreibungszeile fälschlich zu 100 % als
themenrelevant gelten.

## Ausführung

```
PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step3_war_videos.classify_topic_relevance
```

`classify_topic_relevance.py`: Config-Konstanten am Kopf (`TOPIC`,
`CHANNEL_FILTER`, `DRY_RUN`). Erst mit `DRY_RUN=True` die gedruckte
Zusammenfassung/Stichprobe prüfen, dann auf `False` setzen.

## Weiteres Thema ergänzen

Ein zweites Topic (z. B. Nahost, `KEYWORDS_MIDDLE_EAST` existiert bereits in
`config/settings.py`) braucht nur einen neuen Eintrag in
`topic_keywords.TOPIC_KEYWORDS` sowie einen neuen `TOPIC`-Wert in
`classify_topic_relevance.py` — kein Schema-Umbau in `video_registry.py`
nötig, da die Tabelle generisch über die `topic`-Spalte funktioniert.

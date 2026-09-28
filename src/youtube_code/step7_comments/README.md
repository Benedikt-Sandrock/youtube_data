# Schritt 7 — Kommentar-Download

Laedt Video-Kommentare ueber die YouTube Data API und schreibt sie in den
zentralen Store `data/store/comments.sqlite`
(`src/youtube_code/store/comment_store.py`, siehe Moduldocstring dort fuer
Schema und Upsert-/Resume-Logik im Detail). Ersetzt fuer neue Kommentar-
Downloads das archivierte
`src/youtube_code/archive/collection/comment_download.py` (CSV-basiert,
kein zentraler Store, hart auf 2 API-Keys kodiert).

## Offene Folgeentscheidung

Anders als bei Schritt 4 (Transkripte) ist noch nicht abschliessend
festgelegt, welcher Videopool Kommentare bekommen soll und welche der vier
Forschungsfragen aus `.claude/CLAUDE.md` die Kommentardaten beantworten
sollen (z.B. Rezeption/Engagement-Qualitaet als weitere Erfolgsdimension).
`select_targets.py` enthaelt deshalb bislang erst zwei Funktionen -
`select_topic_targets()` (Kommentare fuer themenrelevante Videos aus
Schritt 3) und `select_channel_targets()` (ALLE Videos einer festen
Kanal-Liste, ohne Themen-/Klassifikations-Filter) - statt der drei fest
dokumentierten Konfigurationen wie in Schritt 4. Weitere `select_*`-
Funktionen ergaenzen, sobald der Zweck geklaert ist. Sobald ein
Analyseschritt tatsaechlich auf Kommentardaten aufbaut, gehoert dieser
Abschnitt hier UND `COMPLETE_PROCESS.md` Schritt 7 entsprechend
praezisiert.

## `comment_store.py` — Kernpunkte

- Zwei Tabellen: `comment_fetch_status` (ein Datensatz pro Video, Resume-
  Tracking) und `comments` (die eigentlichen Kommentar-Datensaetze,
  dedupefaehig ueber `comment_id`).
- **Reply-Tiefe konfigurierbar**: `include_replies=False` (Default) laedt
  nur Top-Level-Kommentare (guenstiger, weniger Quota-Verbrauch);
  `include_replies=True` laedt zusaetzlich alle Antworten. Ein Video, das
  bereits mit Replies erfasst wurde, gilt automatisch auch als
  Top-Level-erledigt; ein spaeterer "jetzt auch Replies"-Lauf holt fuer
  bislang nur Top-Level-erfasste Videos gezielt die fehlenden Antworten
  nach (kein Datenverlust, kein Downgrade moeglich).
- **Snapshot-Charakter**: ein Kommentar-Fetch ist - anders als ein
  Transkript-Fetch - kein endgueltiger Zustand, da neue Kommentare nach dem
  Abruf dazukommen koennen. V1 behandelt jeden Fetch als einmaligen
  Snapshot (kein automatisches Re-Fetch bereits versuchter Videos), analog
  zur bewusst akzeptierten Snapshot-Logik von
  `videos.view_count`/`like_count`/`comment_count` in `video_registry.py`.

## `download_comments()` (`download_comments.py`)

Extrahiert und generalisiert aus
`archive/collection/comment_download.py::get_everything_from_videos()`:
Top-Level + optionale Replies, 403-Quota-Erkennung mit Key-Rotation ueber
eine konfigurierbare Key-Liste (Default `[API_KEY, API_KEY_C]` aus
`youtube_code.config`), "disabled" als eigener Status statt Quota-Abbruch.
**Vorfilter ueber Metadaten**: bevor ein Video ueberhaupt angefragt wird,
sortiert `download_comments()` Videos aus, fuer die
`video_registry.comment_count_lookup()` `comment_count` NULL oder 0 liefert
(inkl. Videos, die noch gar nicht in `video_registry` stehen) - laut
Metadaten sind fuer diese Videos keine Kommentare verfuegbar, ein API-Call
waere verschwendet (Muster analog zum `comment_count`-Filter im
archivierten Skript).
Anders als `download_transcripts.py` (unoffizielle `youtube_transcript_api`,
Risiko einer IP-Sperre bei zu schnellen Requests, daher `STOP_WORD` +
lange Zufalls-Sleeps) braucht die offizielle Data API nur einen kurzen
Hoeflichkeits-Sleep - das taegliche Quota ist die eigentliche Grenze.

```python
download_comments(video_ids, channel_map=None, include_replies=False)
```

## Ausfuehrung

Modus und Eingabe werden ueber den `CONFIG`-Block oben in
`download_comments.py` gesteuert (kein Kommandozeilenargument):

- `MODE = "video_list"` (Default): laedt die Video-ID-Liste aus `VIDEO_LIST`
  (JSON).
- `MODE = "channels"`: laedt ALLE in `video_registry` bekannten Videos der
  Kanaele aus `CHANNEL_LIST_CSV` (CSV mit `channel_id`-Spalte, Muster
  analog zu `step2_baseline_channels/append_channels_to_state.py`) ueber
  `select_targets.py::select_channel_targets`.
- `INCLUDE_REPLIES` gilt fuer beide Modi.

Vor dem Lauf die passenden Werte im `CONFIG`-Block eintragen, dann:

```
PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step7_comments.download_comments
```

Fuer den programmatischen Aufruf ueber eine Zielauswahl:

```python
from youtube_code.step7_comments.select_targets import select_topic_targets, select_channel_targets
from youtube_code.step7_comments.download_comments import download_comments

targets = select_topic_targets(topic="russia_ukraine_war")
channel_map = targets.set_index("video_id")["channel_id"].to_dict()
download_comments(targets["video_id"].tolist(), channel_map=channel_map)

# oder: alle Videos einer festen Kanal-Liste
targets = select_channel_targets(channel_ids=["UCxxxx", "UCyyyy"])
download_comments(targets["video_id"].tolist())
```

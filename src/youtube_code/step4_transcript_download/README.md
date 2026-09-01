# Schritt 4 — Transkript-Download-Orchestrierung

Extrahiert aus gespeicherten Videodaten eine Liste von Video-IDs fuer eine der
drei in `COMPLETE_PROCESS.md` genannten Konfigurationen und uebergibt sie an
den Transkript-Download (`COMPLETE_PROCESS.md` Schritt 4).

## Die drei Konfigurationen (`select_targets.py`)

1. **`select_baseline_targets(channel_ids=None)`** — fuer alle Kanaele die
   Baseline pruefen und alle Video-IDs qualifizierender Kanaele extrahieren.
   Verallgemeinerung von `archive/scraping/get_baseline_ids.py` (dort hart
   auf eine 27-Kanal-Todo-CSV kodiert) nach dem in
   `step2_baseline_channels/README.md` §4 dokumentierten Rezept — hier ueber
   alle Kanaele im `screening_state`, nicht nur eine feste Liste.
2. **`select_cell_fill_targets(channel_ids, videos_per_cell, topic=..., granularity=...)`**
   — Kanal-Perioden-Zellen identifizieren und Kriegs-/politisch klassifizierte
   Nicht-Kriegsvideos einfuellen, bis jede Zelle `videos_per_cell` Videos hat.
3. **`select_war_period_targets(start_date, end_date, channel_ids=None, topic=...)`**
   — alle Kriegsvideos in einem bestimmten Zeitraum identifizieren (z. B. kurz
   vor/nach einem wichtigen Event).

Alle drei filtern das Ergebnis bereits gegen
`transcript_store.attempted_video_ids()` — Videos mit bestehendem
Transkript-Versuch werden nie erneut vorgeschlagen.

## Warum `rel_monat`/`rel_quartal` statt `interval_index` (Konfiguration 2)

`select_cell_fill_targets()` berechnet die Zellen-Periode neu aus
`published_at` (`period.py`, `relativ_periode()` — bewusst aus
`step5_segment_analysis/finde_download_kandidaten.py` gespiegelt statt importiert,
um Schritt 4 nicht an den dortigen legacy CSV-Pfad zu koppeln), statt
`interval_index` aus `screening_state_store` zu nutzen. `interval_index` ist
nur fuer das Baseline-Fenster definiert (siehe
`step2_baseline_channels/README.md`); `rel_monat`/`rel_quartal`
deckt dagegen auch die Zeit nach Kriegsbeginn ab und bietet mit `rel_monat`
eine feinere Granularitaet als die 3-Monats-Fenster des Screenings.

Abhaengigkeit: `select_cell_fill_targets()`/`select_war_period_targets()`
setzen voraus, dass `video_registry.video_topic_relevance` bereits befuellt
ist (Schritt 3, `classify_topic_relevance.py`).

## `download_transcripts()` (`download_transcripts.py`)

Verschoben und zu einer importierbaren Funktion extrahiert aus
`scraping/transcript_scraping_segments.py` (Kernschleife unveraendert:
Attempted-Filter, Kanal-Vorfilter, `STOP_WORD`-Notbremse, batchweises
`upsert_transcripts`, randomisierte Sleeps).

```python
download_transcripts(video_ids, channel_map=None, confirm_speed=True)
```

`confirm_speed`: bei `True` **und** `speed_download` wird wie im
urspruenglichen Skript ein "Speed download activated. Continue? [y/N]"-Prompt
gestellt; bei Ablehnung wird ein leeres DataFrame zurueckgegeben (statt
`exit()`, das den ganzen aufrufenden Prozess beenden wuerde). Der
programmatische Aufruf aus `run_transcript_selection.py` setzt
`confirm_speed=False`, um den Prompt zu ueberspringen — nur der manuelle
`if __name__ == "__main__":`-Aufruf (liest weiterhin `VIDEO_LIST`) fragt
interaktiv nach.

## Ausfuehrung

```
PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step4_transcript_download.run_transcript_selection
```

`run_transcript_selection.py`: Config-Konstante `MODE = "baseline" | "cell_fill" | "war_period"`
plus die zugehoerigen Parameter am Kopf der Datei, ruft die passende
`select_*`-Funktion auf und uebergibt das Ergebnis an `download_transcripts()`.

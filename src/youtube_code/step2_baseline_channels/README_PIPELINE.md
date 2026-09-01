# Longitudinale Screening-Pipeline — Kurzreferenz

Diese Tabelle listet die tatsächlich aktuellen Skripte der Pipeline (Stand:
Phase 5 der Restrukturierung). Die vier zuvor hier gelisteten Namen
(`create_longitudinal_screening_round.py`, `update_longitudinal_state.py`,
`select_longitudinal_transcripts.py`, `analyze_longitudinal_coverage.py`)
existieren unter diesen Namen nirgends im Repo und tauchen auch in der
gesamten Git-History nicht auf — vermutlich Altlast einer nie umgesetzten
früheren Planung. Für den Schritt-für-Schritt-Ablauf (inkl. Konfiguration,
Reihenfolge, Stolpersteine) siehe `README_ADD_NEW_CHANNELS.md` im selben
Verzeichnis — die dortige "Kurzreferenz"-Tabelle ist die maßgebliche. Für die
Definition des Baseline-Fensters pro Kanal und den Abruf der Baseline-Videos
siehe `README_BASELINE_WINDOW.md`.

`build_channel_provenance.py` (Zeile 1 der Tabelle) ist seit der
Restrukturierung das zentrale Sample-Definitions-Skript aus
COMPLETE_PROCESS.md Schritt 1 und liegt entsprechend unter
`src/youtube_code/step1_sample/`, nicht in diesem Verzeichnis — hier gelistet,
weil sein Output (`eligible_channels_current.json`) die Kanalliste liefert,
mit der die eigentliche Schritt-2-Pipeline (ab Zeile 2) arbeitet.

| Skript                                                                     | Eingabe                              | Ausgabe                            | Ausführung        |
| --------------------------------------------------------------------------- | ------------------------------------ | ----------------------------------- | ------------------ |
| `../step1_sample/build_channel_provenance.py` (Schritt 1, gehört nicht mehr hierher, siehe unten) | video_registry.sqlite (Suchtreffer, Sprache, Kanal-Metadaten) | Provenienzdatei + `eligible_channels_current.json` | einmal              |
| `longitudinal/append_channels_to_state.py`                                  | Videos und Provenienz                | neue Kandidatenzeilen im State      | pro neue Kanalgruppe |
| `longitudinal/create_longitudinal_screening.py`                             | State (state-weit, adaptiv)          | Batch-Kandidaten (Screening-Runde)  | wiederholt          |
| `../llm_analysis/run_longitudinal_screening_batch.py`                       | Batch-Kandidaten                     | eingereichter Batch-Job (Registry)  | pro Runde × 2 Stufen |
| `../llm_analysis/download_results.py`                                       | Registry (Job-Status)                | Ergebnis-CSV                        | pro Runde × 2 Stufen |
| `update_screening_state.py`                                                 | Modelloutput                         | aktualisierter State                | pro Runde × 2 Stufen |

`prepare_longitudinal_screening.py` (früheres "einmal"-Bootstrap-Skript, baute
den State auf einer festen CSV-Rohdatendatei komplett neu auf) ist seit der
SQLite-Store-Migration nicht mehr sinnvoll ausführbar und liegt inzwischen
unter `src/youtube_code/archive/politics_screening_legacy/`.

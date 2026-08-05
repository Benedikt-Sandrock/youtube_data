| Skript                                   | Eingabe                              | Ausgabe              | Ausführung                  |
| ---------------------------------------- | ------------------------------------ | -------------------- | --------------------------- |
| `build_channel_provenance.py`            | Identifikationsdateien und Metadaten | Provenienzdatei      | einmal                      |
| `prepare_longitudinal_screening.py`      | Videos und Provenienz                | State-Datei          | einmal                      |
| `create_longitudinal_screening_round.py` | State-Datei                          | Batch-Kandidaten     | wiederholt                  |
| `update_longitudinal_state.py`           | Modelloutput                         | aktualisierter State | nach jedem Run              |
| `select_longitudinal_transcripts.py`     | fertiger State                       | Transkriptauswahl    | einmal bzw. nach Änderungen |
| `analyze_longitudinal_coverage.py`       | State und Auswahl                    | Kontrollstatistiken  | nach Bedarf                 |

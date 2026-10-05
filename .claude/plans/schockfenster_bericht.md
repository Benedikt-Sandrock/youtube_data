# Schockfenster-Skript (Aufgaben.md TODO 3)

## Ausgangsfrage

`.claude/Aufgaben.md` TODO 3: Gibt es "Schockfenster" – kurze Zeiträume vor
und nach wichtigen Ereignissen (Kriegsbeginn, Trump-Wahl) – in denen
bestimmte Kanalgruppen einen Reichweiten-Sprung erlebt haben? Mit Fokus auf
Heterogenität (z.B. Russland-freundliche vs. -kritische Kanäle nach der
Trump-Wahl). Inhaltlich eine Verfeinerung von Forschungsfrage 2 ("Wie hat
sich der Erfolg der Kanäle entwickelt?") mit Fokus auf sehr kurze,
ereignisnahe Zeitfenster statt der bisherigen Monats-/Quartals-Auflösung.

Alle bisherigen Vorher/Nachher-Analysen im Projekt (`frage2_erfolg_bericht.py`,
`frage4_kriegspraemie_medientyp_bericht.py` u.a.) arbeiten mit `rel_monat`/
`rel_quartal` (gröbste Auflösung: Monat) und einem festen Referenzdatum
(Kriegsbeginn). Es gab noch kein Skript, das mehrere Ereignisse, mehrere
Fensterbreiten (Tage) und mehrere Heterogenitätsdimensionen parallel und
leicht konfigurierbar durchrechnet – das ist die Lücke, die
`schockfenster_bericht.py` schließt. Der Plan ist bewusst so entworfen, dass
er fast vollständig bestehende, bereits getestete Bausteine wiederverwendet
statt neue Regressionslogik zu schreiben.

## Nutzerentscheidungen aus der Planungsphase (2026-09-10)

- **Kanalstichprobe**: breiter als die Frage-1-Whitelist – alle Kanäle mit
  Medientyp-Klassifikation (`media_type_russia_merged.xlsx`), nicht nur die
  Kanäle mit ≥5 klassifizierten Baseline-Videos. Grund: bei engen
  Tage-Fenstern ist Power ohnehin knapp (viele Kanäle haben keine Videos in
  Vor- UND Nachfenster); die Whitelist-Einschränkung ist nur für die
  Populismus-Klassifikation nötig, nicht für eine reine Reichweiten-Analyse.
- **Umfang des ersten Wurfs**: nur die Kern-Regressionstabelle (Post-Dummy +
  Gruppen-Interaktion je Schock × Fensterbreite × Heterogenitätsdimension ×
  Metrik). Marktanteil-Verschiebung und Plots sind bewusst zurückgestellt für
  einen späteren Ausbauschritt.

## Architektur

`src/youtube_code/step6_auswertung/schockfenster_bericht.py`, als
Paket-Modul ausgeführt (analog zu `prepare_success_metrics.py`, weil es
sowohl `youtube_code.store.video_registry` als auch mehrere Sibling-Module
braucht; alle Sibling-Importe als volle Paketpfade).

**Konfigurationsblock** (Kopf der Datei, "leicht anpassbar"): `SCHOCKS`
(Ereignis-Dict, Default Kriegsbeginn + US-Wahl 2024), `FENSTER_BREITEN_TAGE`
(Liste, Default `[7, 14, 30]`), `HETEROGENITAETS_DIMENSIONEN` (`gruppe5`/
`medientyp`/`ideologie_gruppe`), `METRIKEN` (`view_count`/`log_views`),
`MIN_KANAELE_JE_GRUPPE`.

**Datenpipeline** (fast vollständig Wiederverwendung bestehender Funktionen):

1. `lade_basisdaten()`: Kanalpopulation aus `deskriptiv_aggregation.
   lade_medientyp()`, Video-Rohdaten aus `video_registry.get_video_stats()`,
   Erfolgsmetriken über `prepare_success_metrics.berechne_erfolgsmetriken()`
   (kein neuer Metrik-Code), Kanalmerkmale über `lade_ideologie()` +
   `deskriptiv_plots.baue_gruppe5()`. `baue_gruppe5()` filtert dabei die
   Kanalpopulation zusätzlich auf vollständig klassifizierte Kanäle (ÖRR/
   Traditionell/Alternative Medien mit Ideologie-Einordnung, kein
   Politiker/Partei) – bewusst übernommen, dieselbe Population gilt dann auch
   für die Dimensionen `medientyp`/`ideologie_gruppe`.
2. `berechne_tage_relativ(df, event_datum)`: `tage_relativ = (published_at −
   event_datum).dt.days`, je Schock neu berechnet.
3. `filtere_fenster(df, fenster_breite_tage)`: `abs(tage_relativ) <=
   fenster_breite_tage`.
4. Zwei Beobachtungsebenen als getrennte Robustheits-Durchläufe (Projekt-
   Konvention, siehe `berechne_upload_dichte()` vs.
   `berechne_upload_dichte_periode()` in `bericht_utils.py`): Video-Ebene
   (`periode = tage_relativ`, kontinuierlich) und Kanal×Fensterseite
   aggregiert (`fenster_bucket = −1`/`+1`, Ereignistag selbst zählt zu
   "nach"; Aggregation über die bereits vorhandene
   `prepare_success_metrics.aggregiere_kanal_periode_erfolg()`).
5. `post_dummy_test()`/`interaktions_test()` aus `bericht_utils.py`
   UNVERÄNDERT importiert – funktionieren bereits mit jeder numerischen
   Periodenspalte (Test ist `periode >= 0`), nicht nur `rel_monat`/
   `rel_quartal`.
6. `main()`: Schleife über `SCHOCKS × FENSTER_BREITEN_TAGE ×
   HETEROGENITAETS_DIMENSIONEN × METRIKEN`, sammelt alle Ergebnisse in einer
   Tabelle.

**Outputs** (`outputs/segment_analysis/`): `schockfenster_ergebnisse.csv`
(eine Zeile je Schock/Fensterbreite/Beobachtungsebene/Dimension/Metrik/
Gruppe) und `schockfenster_methodik.md` (Formel, Ereignistag-Konvention,
Begründung der breiteren Kanalpopulation, Sparsity-Limitation bei engen
Fenstern).

## Verifikation

1. Vor jedem tatsächlichen Lauf erst Rückfrage an den Nutzer (`.claude/
   CLAUDE.md`: Testläufe nur nach Genehmigung).
2. Kleiner Trockentest zuerst mit 1 Schock × 1 Fensterbreite × 1 Dimension.
3. `n_kanaele`/`n_beobachtungen` bei den engsten Fenstern (7 Tage) auf
   Plausibilität prüfen (ggf. `FENSTER_BREITEN_TAGE` um größere Werte
   ergänzen, falls 7 Tage durchgehend zu dünn besetzt ist).
4. Kanalzahl der breiteren Population gegen die Frage-1-Whitelist-Größe
   gegenrechnen (Log-Ausgabe beim Laden).
5. Nach Abschluss: 2-3 Kernbefunde gemeinsam mit dem Nutzer durchgehen –
   passend zu TODO 1 in `Aufgaben.md`.

## Mögliche Ausbauschritte (nicht Teil des ersten Wurfs)

- Marktanteil-Verschiebung: `berechne_marktanteile()` aus
  `frage4_kriegspraemie_marktanteil_plots.py` auf "vor Fenster" vs. "nach
  Fenster" als zwei Phasen adaptieren.
- Plots: Balkendiagramme (% Änderung je Gruppe) oder Zeitreihen mit
  Ereignis-Marker, analog `deskriptiv_plots.py`-Stil.
- Weitere Heterogenitätsdimension "Russland-Haltung" (Pro-/Anti-Russland),
  sobald eine kanalkonstante Aggregation der `position_russland`-Dimension
  (analog `lade_ideologie()`) vorbereitet ist.

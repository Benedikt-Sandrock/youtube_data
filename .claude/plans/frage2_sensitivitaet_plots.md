# Sensitivitätsplots für Frage 2 (Kanalerfolg) über Aggregations-/Metrik-Varianten

## Kontext

Die bestehende Auswertung zu Forschungsfrage 2 (`deskriptiv_plots.py` mit `MODUS="erfolg"`,
`frage2_erfolg_bericht.py`) trifft mehrere methodische Einzelentscheidungen fest: Kanal-Monat
als Beobachtungseinheit, ungewichteter Mittelwert über Kanäle, rohe Views ohne
Baseline-Normierung. Der Nutzer möchte prüfen, wie robust die deskriptiven Kernaussagen zu
Frage 2 gegenüber diesen Entscheidungen sind, bevor die formale Auswertung (Regression) darauf
aufbaut. Dafür entsteht ein neues, eigenständiges Skript, das dieselbe Standard-Gruppierung
(5 Gruppen: ÖRR, Traditionelles Medium, Alternative Medien links/mitte/rechts) über eine
strukturierte Matrix aus Aggregationsebene × Metrik × Ausgangsbasis × Umfang plottet, in einen
separaten Output-Ordner. Kein Ad-hoc-Skript (§ CLAUDE.md) — es ist eine dauerhaft nutzbare
Ergänzung zur Schritt-6-Pipeline und gehört daher nach `src/youtube_code/step6_auswertung/`.

**Vom Nutzer bestätigte Parameter:**
- Winsorisierter Mittelwert: **beide** Grenzen parallel plotten (5%/95% UND 1%/99%).
- Kanalfilter: **nur** die Variante "beide Perioden" (Kanäle mit mindestens einem Vor- UND
  einem Nachkriegswert) — kein zusätzlicher "alle Kanäle"-Durchlauf.
- Granularität: **nur** Monat (Kanal-Monat als Beobachtungseinheit, wie im bestehenden Standard).
- Kombinationsmatrix: reduziert um mathematisch redundante Fälle, **ohne** 95%-CI-Bänder
  (Signifikanztests laufen bereits separat in `frage2_erfolg_bericht.py`).
- "Zellen gewichtet" (A3) heißt **gedämpfte** Gewichtung mit `sqrt(n_videos)`, nicht linear
  proportional zur Videoanzahl (das wäre rechnerisch identisch mit reinem Pooling/A2 gewesen) —
  als konfigurierbare Konstante `GEWICHT_EXPONENT = 0.5` am Dateikopf.
- Zusätzliche dritte Ausgangsbasis: **Subscriber-Normierung** (`view_count / subscribers`),
  neben "Absolute Views" und "Index (Vorkriegsmittel=100)".

## Kombinationsmatrix (Kernstück des Plans)

**Aggregationsebenen:**
- **A1 „Zellen, ungewichtet"**: erst je Kanal×Monat eine Zelle bilden (Mittelwert/Summe der
  Videos dieses Kanals in diesem Monat), dann über Kanäle **ungewichtet** kombinieren — der
  bestehende Standard aus `deskriptiv_plots.py`/`aggregiere()`.
- **A2 „Video-Ebene"**: keine Kanal-Monats-Zelle — alle Videos der Gruppe im Monat werden
  direkt gepoolt (entspricht linearer Gewichtung nach `n_videos`).
- **A3 „Zellen, gewichtet"**: wie A1, aber beim Kombinieren über Kanäle zählt jede Zelle mit
  **gedämpftem** Gewicht = `n_videos ** GEWICHT_EXPONENT` (Standard `GEWICHT_EXPONENT = 0.5`,
  also `sqrt(n_videos)`, konfigurierbare Modul-Konstante) — bewusst zwischen A1 (jede Zelle
  zählt gleich) und A2 (volle, lineare Dominanz vieluploadender Kanäle) positioniert.

**Metriken:** Mittelwert, winsorisierter Mittelwert (5/95 und 1/99, je eigene Grafik), Median,
Summe.

**Mathematischer Dedup** (dieselbe Begründung, mit der der Nutzer der reduzierten Matrix
zugestimmt hat — durch die gedämpfte statt lineare A3-Gewichtung gilt der Dedup jetzt NUR noch
für die Summe, nicht mehr für den Mittelwert):
- *Mittelwert*: A1 (ungewichtet), A2 (gepoolt/linear gewichtet) und A3 (`sqrt(n_videos)`-
  gewichtet) sind jetzt drei **unterschiedliche** Werte → 3 Grafiken.
- *Winsorisierter Mittelwert*: A1/A2/A3 unterscheiden sich ohnehin (Winsorisierung wirkt auf
  unterschiedliche Wertemengen — Zellmittel vs. rohe Videowerte) → 3 Grafiken × 2 Grenzen =
  6 Grafiken.
- *Median*: A1 (ungewichteter Median der Zellmittel), A2 (Median der rohen Videowerte) und A3
  (mit `sqrt(n_videos)` gewichteter Median der Zellmittel) unterscheiden sich → 3 Grafiken.
- *Summe*: A1 = Mittelwert der Kanal-Monats-**Summen** über Kanäle (= bestehende
  `log_views_summe`-Logik). A2 und A3 sind hier weiterhin identisch — eine Summe kennt keine
  Gewichtung, "gepoolt" ist in jedem Fall die Gesamtsumme aller Videos der Gruppe/Periode →
  **eine** gemeinsame Grafik "gepoolt", zusätzlich A1. → 2 Grafiken.

→ **14 Grafiken** je (Ausgangsbasis × Umfang) für Metrik-/Aggregationskombinationen (3+6+3+2).

**Ausgangsbasis:**
- *Absolute Views*: wie oben, `view_count` in der jeweiligen Aggregation. → 14 Grafiken.
- *Index (Vorkriegsmittel = 100)*: jeder Kanal wird auf sein **eigenes** Vorkriegsmittel
  (Mittelwert über die Baseline-Monate, wie `berechne_index()` in `deskriptiv_aggregation.py`,
  dort aktuell nur für `MODUS="populismus"` aktiv) indexiert — `index_video =
  view_count_video / baseline_channel * 100`. Die Baseline wird **immer aus allen Videos**
  des Kanals im Vorkriegsfenster berechnet (nicht nur Topic-Videos, konsistent mit dem
  bestehenden Grundsatz in `prepare_success_metrics.py`, dass die Vorkriegsperiode alle
  Videos enthält), Mindestanzahl Baseline-Videos wie bisher (`MIN_VIDEOS_BASELINE_GESAMT=5`).
  Kanäle ohne gültige Baseline fallen aus den Index-Grafiken raus (dokumentiert in der
  Konsolenausgabe, wie bei `berechne_index()`).
- *Subscriber-Normierung*: `view_count_normiert = view_count / subscribers` je Video (bzw. auf
  Zellebene: Zellmittel/-summe geteilt durch `subscribers`), Abonnentenzahl aus
  `channel_erfolg_snapshot.csv` (`prepare_success_metrics.py`). **Limitation, wird in der
  Methodik-Datei dokumentiert**: dort steht nur ein EINMALIGER, aktueller Snapshot je Kanal
  (kein historischer Abo-Stand zum jeweiligen Video-Zeitpunkt) — derselbe (heutige)
  Abonnentenwert wird für alle Perioden des Kanals verwendet. Kanäle ohne Eintrag/mit
  `subscribers <= 0` in `channel_erfolg_snapshot.csv` werden ausgeschlossen (dokumentiert in
  der Konsolenausgabe).
  **Bei beiden normierten Basen (Index UND Subscriber) ergibt "Summe" keinen sinnvoll
  interpretierbaren Wert** (Summe von Verhältniszahlen) → Metrik "Summe" entfällt dort jeweils.
  → **12 Grafiken** je normierter Basis (14 − 2).

**Umfang:** alle Videos vs. nur Topic-Videos (`ist_kriegsvideo == 1`, wie
`NUR_TOPICVIDEOS` in `deskriptiv_plots.py`).

**Gesamtzahl:** (14 absolut + 12 Index + 12 Subscriber-Norm) × 2 Umfänge = **76 Liniendiagramme**
(je 5 Linien, eine je Gruppe5-Kategorie), plus eine Methodik-Übersichtsdatei. Deutlich mehr als
die ursprünglich grob geschätzten ~48, weil die gedämpfte (statt linearer) A3-Gewichtung den
Mittelwert-Dedup aufhebt und die Subscriber-Normierung als dritte Basis dazukommt — beides
auf ausdrücklichen Wunsch des Nutzers.

## Neue Datei

`src/youtube_code/step6_auswertung/frage2_sensitivitaet_plots.py` — läuft direkt als Skript
(sibling-Importe wie die übrigen `step6_auswertung`-Dateien, kein `-m`).

**Wiederverwendete Bausteine** (Reuse-Prinzip aus CLAUDE.md):
- `deskriptiv_aggregation.lade_medientyp()` / `lade_ideologie()` — Kanalmerkmale laden.
- Gruppe5-Zuordnung: kleine lokale Nachbildung von `deskriptiv_plots.baue_gruppe5()`-Logik
  (Import der Konstante `GRUPPE5_REIHENFOLGE` aus `deskriptiv_plots.py`, um dieselbe
  Kategorienliste/-reihenfolge zu garantieren).
- `outputs/segment_analysis/channel_video_erfolg.csv` (Video-Ebene, bereits Whitelist-gefiltert,
  enthält `view_count`, `rel_monat`, `ist_kriegsvideo`) als alleinige Datenquelle — Kanal-Monats-
  Zellen werden für volle Kontrolle (inkl. `n_videos` je Zelle) selbst per `groupby` gebildet,
  nicht aus `channel_{gran}_erfolg_timeseries.csv` nachgeladen.
- Kriegsbeginn-Referenzlinie (senkrechter Strich bei Periode −0.5) wie in `deskriptiv_plots.py`;
  auf die zusätzlichen Ereignis-Marker (`EREIGNISSE`) wird hier bewusst verzichtet, um die
  Vergleichs-Grafiken nicht zu überladen (nur Methodenvergleich, keine Ereignisanalyse).

**Struktur (Funktionen):**
1. `lade_basisdaten()` — `channel_video_erfolg.csv` einlesen, `medientyp`/`ideologie_gruppe`/
   `gruppe5` ergänzen, Abonnentenzahl aus `channel_erfolg_snapshot.csv` mergen, auf Kanäle mit
   gültigem `gruppe5` filtern.
2. `berechne_baseline(df)` — je Kanal Vorkriegsmittel von `view_count` über die Baseline-Monate
   (analog `GRANULARITAETEN["monat"]["baseline_perioden"]` aus `deskriptiv_aggregation.py`),
   inkl. Mindestanzahl-Filter; gibt `channel_id -> baseline`-Mapping zurück.
3. `filtere_kanalfilter_beide_perioden(df)` — nur Kanäle mit mindestens einem Vor- und einem
   Nachkriegswert (wie `kanaele_mit_beiden_perioden()` in `deskriptiv_plots.py`).
4. `baue_zellen(df)` — Kanal×Monat-Zellen: `view_count_mean`, `view_count_summe`, `n_videos`.
5. `winsorisiere(werte, grenze)` — Wrapper um `scipy.stats.mstats.winsorize`.
6. `gewichteter_median(werte, gewichte)` — eigene kleine Implementierung (kumulierte Gewichte),
   Gewichte je nach Aufrufkontext linear (`n_videos`, A2-äquivalent bei Video-Ebene) oder
   gedämpft (`n_videos ** GEWICHT_EXPONENT`, A3).
7. `kombiniere(zellen_oder_videos, aggregationsebene, metrik, basis, gruppen_spalte="gruppe5")` —
   liefert je (Periode, Gruppe5) EINEN Wert, je nach `aggregationsebene`/`metrik`/`basis` aus
   der Matrix oben (inkl. Division durch `baseline`- bzw. `subscribers`-Wert bei den beiden
   normierten Basen).
8. `plotte_kombination(werte_df, dateiname, titel, referenzlinie_y, y_label)` — eine Grafik,
   5 Linien (Gruppe5-Reihenfolge, Kriegsbeginn-Strich, `MIN_KANAELE_PRO_ZELLE`/
   `MIN_VIDEOS_PRO_ZELLE`-Schwellen wie gehabt), Speicherort `PFAD_PLOTS`.
9. `main()` — iteriert über die vollständige (bereits geprunte) Matrix und ruft
   `kombiniere()` + `plotte_kombination()` auf; schreibt zusätzlich eine
   `frage2_sensitivitaet_methodik.md` mit der Matrix-Tabelle und den exakten Formeln
   (Dokumentationspflicht laut Nutzervorgabe für Vorher/Nachher-Vergleiche).

**Config-Konstanten am Dateikopf** (Stil wie die übrigen `step6_auswertung`-Skripte):
`GRANULARITAET="monat"` (fix), `KANALFILTER="beide_perioden"` (fix), `WINSOR_GRENZEN=[0.05, 0.01]`,
`GEWICHT_EXPONENT=0.5` (Exponent für die gedämpfte Zellgewichtung A3, `n_videos **
GEWICHT_EXPONENT`), `MIN_KANAELE_PRO_ZELLE=5`, `MIN_VIDEOS_PRO_ZELLE_VIDEOEBENE=10`,
`MIN_VIDEOS_BASELINE_GESAMT=5` (konsistent mit `deskriptiv_aggregation.py`),
`PFAD_PLOTS = OUTPUTS / "segment_analysis" / "plots_sensitivitaet_frage2"`.

## Output

- `outputs/segment_analysis/plots_sensitivitaet_frage2/*.png` (76 Dateien, Namensschema
  `erfolg_sensitivitaet_{aggregationsebene}_{metrik}_{basis}_{umfang}_monat.png`, `basis` ∈
  {`absolut`, `index_vorkriegsmittel`, `subscriber_norm`}).
- `outputs/segment_analysis/plots_sensitivitaet_frage2/frage2_sensitivitaet_methodik.md` —
  Matrix-Tabelle, Formeln je Zelle, Dedup-Begründung, Baseline-Definition, Subscriber-Snapshot-
  Limitation (Pflichtdokumentation bei Vorher/Nachher-Vergleichen laut Nutzervorgabe).

## Docstrings/READMEs anpassen

`src/youtube_code/step6_auswertung/README.md` um einen Eintrag für
`frage2_sensitivitaet_plots.py` (Schritt 2a-Erweiterung) ergänzen — Kurzbeschreibung, wann es
nach `deskriptiv_plots.py` sinnvoll ist es laufen zu lassen, Verweis auf die Methodik-Datei.

## Verifikation

- Skript zunächst NICHT selbstständig ausführen (857k Videos, 76 Grafiken — laut CLAUDE.md vor
  Testläufen mit größerem Rechenaufwand explizit nachfragen).
- Nach Freigabe: `PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe
  src/youtube_code/step6_auswertung/frage2_sensitivitaet_plots.py` laufen lassen, Konsolenausgabe
  auf Kanalanzahlen je Zelle/Kombination prüfen, Anzahl erzeugter PNGs (76) verifizieren,
  stichprobenartig 2-3 Grafiken (z.B. "Zellen, ungewichtet, Mittelwert, absolut, alle Videos" vs.
  bestehender `erfolg_view_count_gruppen5_monat.png`) auf Plausibilität mit der bestehenden
  Standard-Grafik vergleichen.

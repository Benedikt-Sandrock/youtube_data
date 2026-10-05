# AP 2: Stichproben-Bias beim Marktanteil – Detailplan

**Erstellt: 2026-09-28**, parallel zu AP 1. Er ergänzt den AP-2-Abschnitt in
`masterarbeit_strategie.md` und ist ohne Chat-Historie verständlich.

**Ziel:** Klären, ob der Anstieg des Marktanteils der rechten
Alternativmedien (~17 % → ~39 % bei allen politischen Videos) ein Artefakt
der Stichprobenziehung ist. Die Stichprobe wurde nach Erfolg am Ende des
Zeitraums gezogen, und gelöschte Kanäle fehlen (Survivorship).

---

## 0. Abgrenzung zu AP 1 (parallele Bearbeitung)

| Berührungspunkt | Risiko | Regel für AP 2 |
|---|---|---|
| Datenbasis `channel_video_erfolg.csv` ist auf die 279er-Whitelist gefiltert (`frage1_stichprobe.py`). AP 1 definiert möglicherweise die Analysepopulation neu. | Die Whitelist oder die CSV ändert sich während AP 2 läuft. | Hauptbasis ist das **kanonische Sample** (`russia_longitudinal_v1`, 427 Kanäle, davon 367 mit gültigem gruppe5). Es wird direkt aus `video_registry` gebaut, wie `lade_basisdaten_kanon()` in `scripts/adhoc/marktanteil_vergleich_279_vs_427.py`. Die 279er-Variante läuft nur als Referenzzeile mit. Laut diesem Skript unterscheiden sich 279 und 427 kaum (Kriegsvideos ≤ 1 pp, alle politischen Videos vor Kriegsbeginn bis ±7 pp bei ÖRR und traditionellen Medien, rechte Alternativmedien −1,1 pp). |
| `deskriptiv_aggregation.py::lade_ideologie()` dedupliziert nicht (3 doppelte channel_ids) | Ein zentraler Fix würde die Zahlen von AP 1 mitten im Lauf verschieben. | Nur lokal im AP-2-Skript deduplizieren (`drop_duplicates("channel_id")`), zentral **nicht** anfassen. Den Bug als offenen Punkt für AP 9 notieren. |
| `zentrale_ergebnisse.md`, `outputs/masterarbeit/README.md`, Checkboxen in der Strategie | Konkurrierende Edits | Erst ganz am Ende bearbeiten, direkt vorher neu einlesen. Nur den eigenen Abschnitt ändern. |
| Schreibzugriffe auf Stores (Metadaten-Refetch in Schritt 4) | Kollision mit eventuellen Schreibvorgängen von AP 1 | Den Refetch erst nach Rückfrage machen, möglichst nach Abschluss von AP 1. Alle anderen Schritte lesen nur. |
| Git | Beide Sessions arbeiten im selben Working Tree. | Nur eigene Dateien stagen (`git add <pfad>`), nie `git add -A`. |

---

## 1. Vorab festgelegte Spezifikationen (keine Nachjustierung)

Alle Varianten verwenden **dieselbe** Marktanteils-Formel wie
`marktanteil_themen_plots.py` (Import von `berechne_marktanteile()`, Nenner =
alle 5 rohen gruppe5-Kategorien, `MIN_VIDEOS_GESAMT_PRO_PERIODE = 20`).
Hauptszenario: **alle politischen Videos** (`ist_politics_topic`). Als
Nebenszenario laufen die Kriegsvideos mit.

| Kürzel | Kanalpopulation | adressiert |
|---|---|---|
| **V0** | kanonisch, alle 367 gruppe5-Kanäle (Referenz). Zusätzlich die 279er-Whitelist als Zeile V0w | Reproduktion des Ausgangsbefunds |
| **V1** | balanciertes Panel: `activity_phases`-Kategorie `aktivitaet_deckt_kriegsbeginn` (daraus folgt bei einer 12-Monats-Lückenschwelle mindestens ein Upload in den Monaten −12…−1) | Eintritt neuer Kanäle |
| **V2** | V1 **und** Uploads in den letzten 6 Monaten des Beobachtungsfensters | streng balanciert, rein informativ |
| **V3** | V1, eingeschränkt auf Kanäle, die **schon vor dem Krieg groß** waren: Die Summe der Views ihrer Videos aus den Monaten −12…−1 liegt über dem Median aller V1-Kanäle. Die Schwelle ist vorab fest, keine Variation. | Auswahl nach Erfolg am Ende (siehe unten) |

**Warum V3 nötig ist:** Das balancierte Panel beseitigt nur den Eintritt
neuer Kanäle. Die Auswahl nach Erfolg am Ende bleibt bestehen. Ein rechter
Kanal, der 2021 klein war und bis heute >50k Abonnenten erreicht hat, ist
im Sample. Ein gleich kleiner, der nicht gewachsen ist, fehlt. Historische
Abonnentenzahlen haben wir nicht. V3 wählt deshalb nach der
**Vorkriegs-Reichweite** statt nach der Größe am Ende aus. Das ist die
beste verfügbare Näherung, aber keine vollständige Korrektur. So wird es
auch berichtet.

**Kennzahlen je Variante** (für rechte Alternativmedien, zusätzlich alle
5 Gruppen in der Tabelle):
- Marktanteil vor Kriegsbeginn (rel_monat −12…−1), <20, ≥20, ≥40
  (Level-Shift-Tabelle wie in `marktanteil_rechts_levelshift_konzentration.py`)
- Δ Anteil (≥20 minus vor Kriegsbeginn) mit **Kanal-Bootstrap-KI**: 1.000
  Ziehungen, Kanäle mit Zurücklegen innerhalb von gruppe5 ziehen. Das ist
  billig und zeigt, wie stark wenige Kanäle das Ergebnis tragen.
- Anzahl Kanäle und Videos je Gruppe und Variante

**Vorab festgelegtes Entscheidungskriterium für Kernbotschaft 1**
(Hauptvariante V1, Robustheit V3):
- **hält:** Δ in V1 ≥ 50 % des Δ in V0, und das Bootstrap-KI schließt 0 aus
- **abgeschwächt:** Δ in V1 > 0 mit KI ohne 0, aber < 50 % von V0
- **hält nicht:** das KI von Δ in V1 enthält 0

Für V3 wird dieselbe Einstufung berichtet. Wenn V1 hält und V3 nicht, lautet
die Formulierung: „getragen von Kanälen, die vor dem Krieg klein waren", mit
dem Vorbehalt der Auswahl nach Erfolg am Ende.

---

## 2. Schritte

### Schritt 1: Datenbasis und Kanalklassifikation
- `lade_basisdaten_kanon()` wiederverwenden. Die Funktion liegt in
  `scripts/adhoc/`. Entweder per `sys.path` importieren wie die
  Adhoc-Skripte, oder, falls sie dauerhaft gebraucht wird, als
  `lade_basisdaten(kanalquelle="kanon"|"whitelist")` nach
  `frage4_kriegspraemie_relative_views_plots.py` verschieben. Empfehlung:
  **verschieben**. Diese Datei berührt AP 1 nicht. Docstring und README
  anpassen.
- `classify_channels_bulk()` aus `step2_baseline_channels/activity_phases.py`
  auf die 427 Kanäle anwenden (Uploads über
  `video_registry.get_video_rows_for_channels`, `channel_created_at` aus
  `channels`).
- **Prüfen, woher die Zahl „90 nach Kriegsbeginn aktive Kanäle" stammt**
  (vermutlich `war_group == "nachkriegskanal"`) und die Verteilung der
  Kategorien je gruppe5 ausgeben. Das ist die erste Tabelle im Bericht.
  Wichtig ist, **wie viele** der neuen Kanäle rechte Alternativmedien sind.

### Schritt 2: Marktanteile V0–V3
- Monatsreihe und Level-Shift-Tabelle je Variante, Bootstrap-KI für Δ.
- Eine Grafik: Marktanteil der rechten Alternativmedien je Monat, eine
  Linie je Variante V0/V1/V3, ungeglättet plus LOWESS. Vor dem Plotcode den
  `dataviz`-Skill laden.

### Schritt 3: Zerlegung des Anstiegs
Für die rechten Alternativmedien, Szenario alle politischen Videos, vorher
(−12…−1) gegen nachher (≥20):

```
Δ Anteil_gesamt = [Anteil_nachher(V1) − Anteil_vorher]        (a) Wachstum der Bestandskanäle
                + [Anteil_nachher(V0) − Anteil_nachher(V1)]   (b) Beitrag der neuen Kanäle
```

Vor Kriegsbeginn sind V0 und V1 fast identisch, weil neue Kanäle noch keine
Videos haben. Die Abweichung wird ausgewiesen.

Ergänzend eine **Konzentration innerhalb von (a)**: Anteil der Top-1- und
Top-5-Bestandskanäle am Zuwachs. Dafür wird die Logik von
`marktanteil_rechts_levelshift_konzentration.py` wiederverwendet.

### Schritt 4: Survivorship grob schätzen
1. **Zuerst prüfen, ob machbar ist:** Liefert `video_search_hits` für Videos
   ohne Eintrag in `videos` einen `channel_id`? Die Abfrage macht einen
   LEFT JOIN auf `videos`, fehlende Videos haben also keinen Kanal. Falls
   nicht: In `identification_vids.json` (Quelle von `upsert_search_hits`)
   nach `channel_id` bzw. Kanalname suchen.
2. Für Suchläufe 2021/22: Anteil der Treffer ohne Metadaten. Wenn eine
   Kanalzuordnung möglich ist: je gruppe5 (nur für bekannte Kanäle), sonst
   nur insgesamt. **Einschränkung:** „Keine Metadaten" kann auch „nie
   abgerufen" heißen. Beides muss unterschieden werden, sonst ist die Zahl
   wertlos.
3. Falls nötig, ein kleiner Metadaten-Refetch über `metadata_collection.py`.
   **Vorher Umfang (Anzahl IDs, API-Quota) beziffern und rückfragen.**
4. Eine qualitative Liste gesperrter oder gelöschter Kanäle im Suchzeitraum,
   mit Quelle und Datum, etwa RT DE (Sperrung durch YouTube 2021) und weitere
   Corona-Löschungen 2021. Nur für den Limitationen-Abschnitt. Die Richtung
   des Bias wird benannt: Fehlen solche Kanäle vor dem Krieg, fällt der
   Vorkriegsanteil der rechten Alternativmedien zu niedrig aus, und der
   Anstieg wird überschätzt.

### Schritt 5 (optional): 10k-Schwelle
Nur wenn V1 und V3 widersprüchlich sind. Größe des API-Laufs für die
zusätzlichen Kanäle aus `eligible_10k` (812 Kanäle) beziffern und
**rückfragen**. Nicht eigenständig starten.

---

## 3. Ausgaben

- Skript: `scripts/masterarbeit/ap2_marktanteil_stichprobenbias.py`
- `outputs/masterarbeit/ap2_stichprobenbias/regression_results/marktanteil_stichprobenbias.md`
  mit folgenden Abschnitten:
  1. **Methodik-Übersicht**: Definition der Varianten, Formel, Perioden,
     Entscheidungskriterium, Bootstrap (Memory
     „document-comparative-analysis-methodology")
  2. Kategorien der Kanalaktivität je gruppe5
  3. Level-Shift-Tabelle V0/V0w/V1/V2/V3 mit Δ und KI
  4. Zerlegung (a)/(b) und Konzentration
  5. Survivorship (quantitativ, soweit machbar, plus qualitative Liste)
  6. **Einstufung:** hält / abgeschwächt / hält nicht, dazu die
     Formulierung für die Arbeit
- `outputs/masterarbeit/ap2_stichprobenbias/marktanteil_varianten_monat.csv`
  und der Plot im selben Ordner

**Laufzeit:** Die Varianten V0–V3 sind reine pandas-Arbeit auf der
Video-Ebene (einige 100k Zeilen). Der Bootstrap mit 1.000 Ziehungen über
4 Varianten liegt voraussichtlich im Minutenbereich. Vor dem ersten
vollständigen Lauf trotzdem kurz rückfragen (CLAUDE.md), vorher mit
`N_BOOTSTRAP = 50` testen.

## 4. Abschluss
- Einstufung in `zentrale_ergebnisse.md` beim Marktanteilsbefund eintragen
  (vorher neu einlesen, siehe Abschnitt 0).
- Status in `outputs/masterarbeit/README.md` und die Checkbox in
  `masterarbeit_strategie.md` setzen.
- `scripts/masterarbeit/README.md` um das Skript ergänzen.

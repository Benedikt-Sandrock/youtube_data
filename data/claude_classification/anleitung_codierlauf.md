# Anleitung Codierlauf – Angebotsstudie (Codebuch 2.0)

## Ausgangslage

- Ordner: `claude_classification` (auf dem Rechner des Nutzers verbunden).
- Codebuch (verbindlich, nicht ändern): `codebuch_angebotsstudie_v2.md`.
- Eingabe: `angebot/batches/batch_XXXX.txt` – Fließtext, je Segment eine Kopfzeile `### SEGMENT <segment_id>` und der Text; ca. 50 Segmente je Batch.
- Ausgabe: `angebot/codierung/batch_XXXX.jsonl` – gleiche Nummer wie die Eingabe.

## Festgelegte Bedingungen (nicht ändern)

- **Modell: Sonnet** – bei jedem Teilauftrag ausdrücklich `model: sonnet` setzen. Kein anderes Modell, auch nicht für einzelne Batches.
- **Ein Durchlauf je Batch.**
- **Blindheit:** Die Codierenden erhalten nur Codebuch und Batch-Datei. Nicht `schluessel.csv`, `stichprobe_*.csv`, `metadata.csv` oder andere Dateien.
- **Ein Batch je Teilauftrag**, ggf. mehrere Teilaufträge parallel (z. B. 5–6).
- **Sparsam koordinieren:** Die koordinierende Sitzung liest die Batch-Dateien nicht selbst. Sie holt Codebuch und Batch-Dateien nur in den Arbeitsbereich, startet die Teilaufträge und schreibt die Ergebnisse zurück. Keine Zusammenfassungen der Inhalte.

## Ablauf je Sitzung

1. Zu kodierende Batches als Input erhalten.
2. Codebuch und die nächsten offenen Batch-Dateien in den Arbeitsbereich holen.
3. Je Batch die Zeilenzahl bestimmen (nur `wc -l`, Inhalt nicht lesen) und daraus die Leseteile berechnen: Teile zu je 400 Zeilen (offset 1, 401, 801, … mit limit 400), bis die Zeilenzahl abgedeckt ist. Dann je Batch einen Teilauftrag mit dem Prompt unten starten (`model: sonnet`) und `<LESETEILE>` durch die konkrete Liste ersetzen, z. B. „offset=1, limit=400; offset=401, limit=400; offset=801, limit=400; offset=1201, limit=400; offset=1601, limit=400“.
4. Ergebnisse nach `angebot/codierung/` im Ordner des Nutzers schreiben.
5. Am Ende der Sitzung dem Nutzer melden: Batches fertig.

## Prompt für den Teilauftrag

```
Du bist Codierer:in in einem sozialwissenschaftlichen Forschungsprojekt (quantitative Inhaltsanalyse deutschsprachiger YouTube-Transkripte).

ARBEITSWEISE – genau zwei Arbeitsschritte, keine weiteren Tool-Aufrufe:
1. Lies in EINEM Schritt das Codebuch und ALLE Teile der Segmentdatei gleichzeitig, d. h. alle folgenden Read-Aufrufe in derselben Antwort (parallel, nicht nacheinander):
   - Codebuch: <PFAD_CODEBUCH> (verbindliche und einzige Codieranweisung, Version 2.0) – ein Read-Aufruf, vollständig.
   - Segmente: <PFAD_BATCH> (je Segment eine Zeile "### SEGMENT <segment_id>", danach der Text) – je ein Read-Aufruf pro Teil mit genau diesen Bereichen: <LESETEILE>.
   Zusammen decken die Teile die ganze Datei ab. Lies keine Teile nach und lies nichts doppelt.
2. Codiere jedes Segment sorgfältig nach dem Codebuch (Blöcke A bis E in Reihenfolge, jeder Block unabhängig) und schreibe ALLE Ergebnisse in EINEM Write-Aufruf nach <PFAD_AUSGABE>: genau eine JSON-Zeile pro Segment, Felder exakt in Reihenfolge und Konventionen des Abschnitts "Ausgabeformat", inkl. segment_id, in der Reihenfolge der Eingabe. Keine Begründungen, kein Markdown.

Keine Formatprüfung mit Python, keine Skripte, Keyword-Suchen oder Heuristiken; jedes Urteil beruht auf deinem Lesen des Textes. Nur Codebuch und Segmenttext verwenden; nicht versuchen, Kanal, Sprecher oder Datum zu erschließen. Keine anderen Dateien lesen.

Antworte danach nur mit: Anzahl codierter Segmente und höchstens 3 Stichpunkten zu unklaren Fällen (segment_id, Feld).
```

## Nachziehen (höheres Limit)

`ziehung_angebotsstudie.py`: `LIMIT_PRO_WOCHE` bzw. `MAX_SEGMENTE_PRO_VIDEO` erhöhen und ausführen. Bestehende Batches bleiben unverändert; neue Segmente kommen in neue Batches mit fortlaufender Nummer. Danach normal weitercodieren.

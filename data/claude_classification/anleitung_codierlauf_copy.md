# Anleitung Codierlauf – Angebotsstudie (Codebuch 2.0)

## Ausgangslage

- Ordner: `claude_classification` (auf dem Rechner des Nutzers verbunden).
- Codebuch (verbindlich, nicht ändern): `codebuch_angebotsstudie_v2.md`.
- Eingabe: `angebot/batches/batch_XXXX.txt` – Fließtext, je Segment eine Kopfzeile `### SEGMENT <segment_id>` und der Text; ca. 50 Segmente je Batch.
- Ausgabe: `angebot/codierung/batch_XXXX.jsonl` – gleiche Nummer wie die Eingabe.
- Stand prüfen: `python status_codierlauf.py` (zeigt offene Batches, prüft fertige gegen die Codebuch-Regeln und führt alle fehlerfreien zu `angebot/codierung_gesamt.jsonl` zusammen).

## Festgelegte Bedingungen (nicht ändern)

- **Modell: Sonnet** – bei jedem Teilauftrag ausdrücklich `model: sonnet` setzen. Kein anderes Modell, auch nicht für einzelne Batches.
- **Ein Durchlauf je Batch.** Ein Batch wird nur neu codiert, wenn `status_codierlauf.py` Probleme meldet.
- **Blindheit:** Die Codierenden erhalten nur Codebuch und Batch-Datei. Nicht `schluessel.csv`, `stichprobe_*.csv`, `metadata.csv` oder andere Dateien.
- **Ein Batch je Teilauftrag**, mehrere Teilaufträge parallel (z. B. 5–6).
- **Sparsam koordinieren:** Die koordinierende Sitzung liest die Batch-Dateien nicht selbst. Sie holt Codebuch und Batch-Dateien nur in den Arbeitsbereich, startet die Teilaufträge, schreibt die Ergebnisse zurück und führt `status_codierlauf.py` aus. Keine Zusammenfassungen der Inhalte.

## Ablauf je Sitzung

1. `python status_codierlauf.py` im Ordner ausführen → offene Batches ermitteln.
2. Codebuch und die nächsten offenen Batch-Dateien in den Arbeitsbereich holen.
3. Je Batch einen Teilauftrag mit dem Prompt unten starten (`model: sonnet`).
4. Ergebnisse nach `angebot/codierung/` im Ordner des Nutzers schreiben.
5. `python status_codierlauf.py` erneut ausführen; Batches mit Problemen einmal neu codieren lassen.
6. Am Ende der Sitzung dem Nutzer melden: Batches fertig / offen / mit Problemen, Token-Nutzung je Teilauftrag.

## Prompt für den Teilauftrag

```
Du bist Codierer:in in einem sozialwissenschaftlichen Forschungsprojekt (quantitative Inhaltsanalyse deutschsprachiger YouTube-Transkripte).

ARBEITSWEISE – genau zwei Arbeitsschritte, keine weiteren Tool-Aufrufe:
1. Lies in EINEM Schritt beide Dateien gleichzeitig (zwei Read-Aufrufe in derselben Antwort, jeweils vollständig, mit allow_large=true und ohne Zeilenbegrenzung):
   - Codebuch: <PFAD_CODEBUCH> (verbindliche und einzige Codieranweisung, Version 2.0)
   - Segmente: <PFAD_BATCH> (je Segment eine Zeile "### SEGMENT <segment_id>", danach der Text)
2. Codiere jedes Segment sorgfältig nach dem Codebuch (Blöcke A bis E in Reihenfolge, jeder Block unabhängig) und schreibe ALLE Ergebnisse in EINEM Write-Aufruf nach <PFAD_AUSGABE>: genau eine JSON-Zeile pro Segment, Felder exakt in Reihenfolge und Konventionen des Abschnitts "Ausgabeformat", inkl. segment_id, in der Reihenfolge der Eingabe. Keine Begründungen, kein Markdown.

Keine Formatprüfung mit Python, keine Skripte, Keyword-Suchen oder Heuristiken; jedes Urteil beruht auf deinem Lesen des Textes. Nur Codebuch und Segmenttext verwenden; nicht versuchen, Kanal, Sprecher oder Datum zu erschließen. Keine anderen Dateien lesen.

Antworte danach nur mit: Anzahl codierter Segmente und höchstens 3 Stichpunkten zu unklaren Fällen (segment_id, Feld).
```

## Nachziehen (höheres Limit)

`ziehung_angebotsstudie.py`: `LIMIT_PRO_WOCHE` bzw. `MAX_SEGMENTE_PRO_VIDEO` erhöhen und ausführen. Bestehende Batches bleiben unverändert; neue Segmente kommen in neue Batches mit fortlaufender Nummer. Danach normal weitercodieren.

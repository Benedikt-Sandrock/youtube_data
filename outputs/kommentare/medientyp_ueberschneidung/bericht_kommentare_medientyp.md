# Kommentare nach Medientyp: Überschneidung und Wanderung

Erzeugt von `src/youtube_code/step7_comments/descriptives_comments.py`.

## Datenbasis

- Videos in der Liste: 27.568, davon 104 aus Kanälen ohne eine der drei Gruppen; ausgewertet 107 Kanäle.
- Kommentare geladen: 3.888.919; ohne Autor 0, vom Kanal selbst 4.066; ausgewertet 3.884.853 von 617.864 Nutzern.
- Davon im Analysefenster 2022-01-06 bis 2022-10-26: 3.488.124.

## Grenzen beim Lesen

- **Ungleiche Abdeckung:** Der Kommentar-Download ist nicht abgeschlossen, und der Anteil abgefragter Videos unterscheidet sich zwischen den Gruppen (Tabellen unten). Absolute Zahlen und Gruppenanteile sind deshalb nicht die tatsächliche Verteilung; die Ziehung kappt zudem bei 14 Videos je Kanal-Woche, was uploadstarke Kanäle trifft. Überschneidungen sind untere Grenzen, weil nicht abgefragte Videos fehlen.
- **Nur Top-Level-Kommentare** aus einem späteren Abruf: inzwischen gelöschte Kommentare und Konten fehlen, möglicherweise je Gruppe unterschiedlich stark.
- **Überschneidung hängt von der Aktivität ab:** Wer wenig kommentiert, kann kaum in mehreren Gruppen auftauchen.
- **Gleiche Nutzer-Kennung ist nicht gleiche Person**, und Bots werden nicht herausgefiltert.
- **Vorkriegsfenster nur 7 Wochen**, Kommentare darin nur unter Videos ab 06.01.2022. Kein Kausalnachweis: Es gibt keine Kontrollgruppe, und Wanderungen können auch das veränderte Angebot widerspiegeln.
- **Konfidenzintervalle** behandeln Nutzer als unabhängig und sind bei dieser Fallzahl eng; entscheidend ist die Größe des Effekts, nicht die Signifikanz.

## 1. Überblick

Alle Kommentare der Videos (auch nach dem Analysefenster).

| Gruppe | Kanäle | Videos Liste | Videos abgefragt | Abdeckung % | Kommentare | Kommentare je abgefr. Video | Nutzer | Kommentare je Nutzer | Median | Nur diese Gruppe % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ÖRR | 20 | 4.247 | 2.197 | 51.7 | 889.565 | 404.9 | 323.511 | 2.7 | 1.0 | 58.0 |
| Traditionelle Medien | 22 | 11.217 | 4.364 | 38.9 | 776.398 | 177.9 | 265.382 | 2.9 | 1.0 | 47.1 |
| Alternative (rechts) | 65 | 12.000 | 8.659 | 72.2 | 2.218.890 | 256.3 | 248.726 | 8.9 | 2.0 | 55.0 |

| Nutzer | Mittelwert | Median | genau 1 Kommentar % | >= 5 % | >= 20 % | Kommentare der Top 1 % (Anteil %) | Kommentare der Top 10 % (Anteil %) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 617.864 | 6.3 | 1.0 | 52.3 | 20.5 | 5.7 | 30.5 | 69.0 |

### Gruppenkombinationen

![Kombinationen](kombinationen.png)

| Kommentiert bei | Nutzer (>= 1) | % (>= 1) | Nutzer (>= 5) | % (>= 5) | Nutzer (>= 20) | % (>= 20) |
| --- | --- | --- | --- | --- | --- | --- |
| ÖRR | 187.542 | 30.4 | 7.146 | 5.6 | 324 | 0.9 |
| Trad. | 125.035 | 20.2 | 2.346 | 1.9 | 75 | 0.2 |
| Alt. rechts | 136.717 | 22.1 | 18.534 | 14.6 | 3.275 | 9.4 |
| ÖRR + Trad. | 56.561 | 9.2 | 22.885 | 18.1 | 2.503 | 7.2 |
| ÖRR + Alt. rechts | 28.223 | 4.6 | 11.981 | 9.5 | 2.006 | 5.7 |
| Trad. + Alt. rechts | 32.601 | 5.3 | 17.383 | 13.7 | 5.259 | 15.0 |
| ÖRR + Trad. + Alt. rechts | 51.185 | 8.3 | 46.262 | 36.6 | 21.545 | 61.6 |

### Bedingte Überschneidung

| Mind. Kommentare | Nutzer von | n | auch ÖRR % | auch Traditionelle Medien % | auch Alternative (rechts) % |
| --- | --- | --- | --- | --- | --- |
| 1 | ÖRR | 323.511 | - | 33.3 | 24.5 |
| 1 | Traditionelle Medien | 265.382 | 40.6 | - | 31.6 |
| 1 | Alternative (rechts) | 248.726 | 31.9 | 33.7 | - |
| 5 | ÖRR | 88.274 | - | 78.3 | 66.0 |
| 5 | Traditionelle Medien | 88.876 | 77.8 | - | 71.6 |
| 5 | Alternative (rechts) | 94.160 | 61.9 | 67.6 | - |
| 20 | ÖRR | 26.378 | - | 91.2 | 89.3 |
| 20 | Traditionelle Medien | 29.382 | 81.8 | - | 91.2 |
| 20 | Alternative (rechts) | 32.085 | 73.4 | 83.5 | - |

### Größte Kanäle je Gruppe

| Gruppe | Kanal | Kommentare | Anteil an Gruppe % |
| --- | --- | --- | --- |
| ÖRR | ZDFheute Nachrichten | 324.678 | 36.5 |
| ÖRR | MrWissen2go | 114.819 | 12.9 |
| ÖRR | Der Dunkle Parabelritter | 76.628 | 8.6 |
| ÖRR | STRG_F | 74.663 | 8.4 |
| ÖRR | tagesschau | 44.584 | 5.0 |
| Traditionelle Medien | BILD | 346.779 | 44.7 |
| Traditionelle Medien | DER SPIEGEL | 185.043 | 23.8 |
| Traditionelle Medien | DW Deutsch | 83.226 | 10.7 |
| Traditionelle Medien | stern TV | 65.736 | 8.5 |
| Traditionelle Medien | tvberlin | 34.500 | 4.4 |
| Alternative (rechts) | Carsten Jahn - TEAM HEIMAT | 248.046 | 11.2 |
| Alternative (rechts) | Achtung, Reichelt! | 172.206 | 7.8 |
| Alternative (rechts) | Deutschland Kurier | 167.319 | 7.5 |
| Alternative (rechts) | Oli | 142.471 | 6.4 |
| Alternative (rechts) | DIE WELTWOCHE | 132.755 | 6.0 |

## 2. Zeitverlauf

Nur Kommentare mit Datum im Analysefenster. Die Überschneidung je Periode steigt mechanisch mit der Periodenlänge; für den Trend zählt die Grafik je Woche.

![Woche](zeitverlauf_woche.png)

| Periode | Kommentare | je Tag | Kommentare % ÖRR | Kommentare % Traditionelle Medien | Kommentare % Alternative (rechts) | Videos % ÖRR | Videos % Traditionelle Medien | Videos % Alternative (rechts) | Nutzer ÖRR/Trad. | Nutzer Alt. rechts | ÖRR/Trad. auch bei Alt. % | Alt. auch bei ÖRR/Trad. % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Vorkrieg | 521.013 | 10632.9 | 21.8 | 26.2 | 51.9 | 15.3 | 27.3 | 57.4 | 118.781 | 64.993 | 18.1 | 33.2 |
| Quartal 0 | 988.648 | 11108.4 | 22.6 | 22.8 | 54.6 | 13.9 | 30.0 | 56.0 | 181.327 | 100.092 | 18.3 | 33.1 |
| Quartal 1 | 1.017.120 | 11055.7 | 21.3 | 17.8 | 60.9 | 14.5 | 29.0 | 56.5 | 166.511 | 105.855 | 21.0 | 33.1 |
| Quartal 2 (bis 26.10.) | 961.343 | 15021.0 | 20.4 | 14.1 | 65.4 | 12.9 | 27.8 | 59.3 | 150.111 | 116.563 | 24.8 | 32.0 |

### Abdeckung: Anteil abgefragter Videos je Upload-Periode (%)

| Upload-Periode | ÖRR | Traditionelle Medien | Alternative (rechts) |
| --- | --- | --- | --- |
| Vorkrieg | 61.6 | 46.3 | 88.9 |
| Quartal 0 | 59.1 | 47.7 | 89.4 |
| Quartal 1 | 62.4 | 46.1 | 89.1 |
| Quartal 2 (bis 26.10.) | 61.0 | 45.5 | 89.7 |

Kanäle mit den meisten noch nicht abgefragten Videos im Analysefenster:

| Kanal | Gruppe | Videos | abgefragt | fehlen |
| --- | --- | --- | --- | --- |
| AFP Deutsch | Traditionelle Medien | 588 | 0 | 588 |
| faz | Traditionelle Medien | 588 | 0 | 588 |
| phoenix | ÖRR | 588 | 0 | 588 |
| WELT Nachrichtensender | Traditionelle Medien | 588 | 1 | 587 |
| Handelsblatt | Traditionelle Medien | 588 | 1 | 587 |
| WELT Netzreporter | Traditionelle Medien | 578 | 0 | 578 |
| DIE ZEIT  | Traditionelle Medien | 442 | 28 | 414 |
| tagesschau | ÖRR | 588 | 181 | 407 |

## 3. Kohorten: Wandern Nutzer von ÖRR/Traditionellen zu rechten Alternativen?

Kohorte aus Hälfte A der Periode „Vorkrieg“ (mind. 5 Kommentare, Lagerschwelle 80%). Vergleichsperioden zählen Nutzer mit mind. 3 Kommentaren. „Vorkrieg (Hälfte B)“ misst dieselben Nutzer im selben Zeitraum und zeigt die Regression zur Mitte ohne jede Verhaltensänderung. Eine Wanderung ist nur der Abstand zu diesem Benchmark, nicht zur Kohortendefinition.

![Kohorten](kohorten_alt_anteil.png)

| Kohorte | Vergleich | Kohorte n | aktiv n | aktiv % | ÖRR % | Trad. % | Alt. rechts % | KI Alt. (+/-) | überwiegend Alt. % | Paare n | Änderung ggü. Hälfte B (pp) | KI Änderung (+/-) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ÖRR/Traditionelle | Vorkrieg (Hälfte B) | 2.277 | 1.806 | 79.3 | 45.1 | 47.3 | 7.6 | 0.7 | 3.3 | 1.806 | 0.0 | 0.0 |
| Gemischt | Vorkrieg (Hälfte B) | 3.545 | 3.103 | 87.5 | 13.2 | 31.7 | 55.1 | 1.0 | 62.8 | 3.103 | 0.0 | 0.0 |
| Alternative | Vorkrieg (Hälfte B) | 5.339 | 4.737 | 88.7 | 2.3 | 7.1 | 90.6 | 0.4 | 98.2 | 4.737 | 0.0 | 0.0 |
| ÖRR/Traditionelle | Quartal 0 | 2.277 | 1.877 | 82.4 | 40.9 | 42.7 | 16.4 | 1.1 | 12.6 | 1.540 | 8.7 | 1.0 |
| Gemischt | Quartal 0 | 3.545 | 3.236 | 91.3 | 10.7 | 22.3 | 67.0 | 0.9 | 76.2 | 2.895 | 11.6 | 0.9 |
| Alternative | Quartal 0 | 5.339 | 5.017 | 94.0 | 2.2 | 5.4 | 92.4 | 0.3 | 98.8 | 4.512 | 2.2 | 0.4 |
| ÖRR/Traditionelle | Quartal 1 | 2.277 | 1.611 | 70.8 | 42.7 | 35.2 | 22.0 | 1.4 | 18.6 | 1.333 | 14.1 | 1.4 |
| Gemischt | Quartal 1 | 3.545 | 2.942 | 83.0 | 11.5 | 17.5 | 71.0 | 1.0 | 80.5 | 2.638 | 15.0 | 1.0 |
| Alternative | Quartal 1 | 5.339 | 4.611 | 86.4 | 2.8 | 4.8 | 92.4 | 0.4 | 98.3 | 4.169 | 2.1 | 0.5 |
| ÖRR/Traditionelle | Quartal 2 (bis 26.10.) | 2.277 | 1.477 | 64.9 | 42.1 | 28.9 | 29.0 | 1.6 | 28.4 | 1.239 | 21.2 | 1.6 |
| Gemischt | Quartal 2 (bis 26.10.) | 3.545 | 2.801 | 79.0 | 11.4 | 12.7 | 75.9 | 0.9 | 86.0 | 2.517 | 20.1 | 1.1 |
| Alternative | Quartal 2 (bis 26.10.) | 5.339 | 4.377 | 82.0 | 2.8 | 3.6 | 93.6 | 0.3 | 98.9 | 3.978 | 3.1 | 0.5 |

### Übergänge: Benchmark (Vorkrieg (Hälfte B), Zeilen-%)

| Kohorte (Hälfte A) | n | ÖRR/Traditionelle | Gemischt | Alternative |
| --- | --- | --- | --- | --- |
| ÖRR/Traditionelle | 1.806 | 83.2 | 16.6 | 0.2 |
| Gemischt | 3.103 | 11.4 | 66.1 | 22.5 |
| Alternative | 4.737 | 0.2 | 16.9 | 83.0 |

### Übergänge: letzte Periode (Quartal 2 (bis 26.10.), Zeilen-%)

| Kohorte (Hälfte A) | n | ÖRR/Traditionelle | Gemischt | Alternative |
| --- | --- | --- | --- | --- |
| ÖRR/Traditionelle | 1.477 | 51.8 | 37.4 | 10.8 |
| Gemischt | 2.801 | 4.0 | 38.5 | 57.5 |
| Alternative | 4.377 | 0.3 | 8.2 | 91.5 |

### Wo die ÖRR/Traditionelle-Kohorte bei rechten Alternativen kommentiert

Nach der Startperiode. Wenige Kanäle mit großem Anteil sprechen eher für einen Kanaleffekt als für einen allgemeinen Wechsel.

| Kanal | Kommentare | Nutzer | Anteil % |
| --- | --- | --- | --- |
| Achtung, Reichelt! | 3.837 | 527 | 14.8 |
| Carsten Jahn - TEAM HEIMAT | 1.746 | 231 | 6.8 |
| DIE WELTWOCHE | 1.579 | 189 | 6.1 |
| Deutschland Kurier | 1.486 | 381 | 5.7 |
| Boris Reitschuster | 1.299 | 368 | 5.0 |
| Oli investiert | 1.189 | 259 | 4.6 |
| _horizont_ | 1.181 | 264 | 4.6 |
| Erfolgskanal - Community für Finanzen & Wirtschaft | 1.133 | 317 | 4.4 |
| Vermietertagebuch - Alexander Raue | 1.054 | 357 | 4.1 |
| Oli | 968 | 263 | 3.7 |

## 4. Robustheit

Alle Tabellen zeigen den mittleren Anteil der Kommentare bei Alternative (rechts) in %.

### ÖRR und traditionelle Medien getrennt

| Kohorte | Kohorte n | Vorkrieg (Hälfte B) | Quartal 0 | Quartal 1 | Quartal 2 (bis 26.10.) |
| --- | --- | --- | --- | --- | --- |
| Alternative | 5.339 | 90.6 | 92.4 | 92.4 | 93.6 |
| Gemischt | 3.421 | 55.9 | 67.8 | 71.7 | 76.5 |
| ÖRR + Trad. gemischt | 1.075 | 8.9 | 18.2 | 24.5 | 32.2 |
| Traditionelle Medien | 731 | 11.6 | 24.6 | 32.4 | 43.6 |
| ÖRR | 595 | 3.2 | 8.1 | 10.6 | 12.9 |

### Ohne neue Kanäle (25 Kanäle ohne abgefragtes Vorkriegsvideo)

| Periode | Kommentare neuer Kanäle % |
| --- | --- |
| Vorkrieg | 0.0 |
| Quartal 0 | 0.9 |
| Quartal 1 | 7.5 |
| Quartal 2 (bis 26.10.) | 11.7 |

| Kohorte | Kohorte n | Vorkrieg (Hälfte B) | Quartal 0 | Quartal 1 | Quartal 2 (bis 26.10.) |
| --- | --- | --- | --- | --- | --- |
| Alternative | 5.339 | 90.6 | 92.3 | 91.9 | 92.9 |
| Gemischt | 3.545 | 55.1 | 66.8 | 68.6 | 72.7 |
| ÖRR/Traditionelle | 2.277 | 7.6 | 16.3 | 19.6 | 25.0 |

### Ohne BILD, Achtung, Reichelt!

| Kohorte | Kohorte n | Vorkrieg (Hälfte B) | Quartal 0 | Quartal 1 | Quartal 2 (bis 26.10.) |
| --- | --- | --- | --- | --- | --- |
| Alternative | 6.249 | 94.8 | 94.1 | 93.4 | 94.0 |
| Gemischt | 1.459 | 58.5 | 66.2 | 66.5 | 69.3 |
| ÖRR/Traditionelle | 1.237 | 5.7 | 12.0 | 13.8 | 18.8 |

### Rückwärts-Placebo

Kohorte in der letzten Periode, Blick zurück. Reine Regression zur Mitte wäre spiegelbildlich zur Vorwärtsrichtung: Die ÖRR/Traditionelle-Kohorte hätte dann früher höhere Anteile bei Alt. rechts.

| Kohorte | Kohorte n | Quartal 2 (bis 26.10.) (Hälfte B) | Quartal 1 | Quartal 0 | Vorkrieg |
| --- | --- | --- | --- | --- | --- |
| Alternative | 13.083 | 92.3 | 88.3 | 85.2 | 79.6 |
| Gemischt | 5.312 | 59.1 | 50.2 | 44.5 | 39.9 |
| ÖRR/Traditionelle | 2.902 | 8.5 | 6.9 | 5.6 | 5.6 |

### Woher die Kommentare bei Alt. rechts in der letzten Periode kommen

Das Vorkriegsfenster ist kurz: „kein Kommentar im Vorkrieg“ heißt nicht, dass der Nutzer neu ist.

| Im Vorkrieg | Kommentare | Nutzer | Anteil Kommentare % |
| --- | --- | --- | --- |
| beide Lager | 238.009 | 14.935 | 37.8 |
| kein Kommentar im Vorkrieg | 196.849 | 70.145 | 31.3 |
| nur Alt. rechts | 149.683 | 19.781 | 23.8 |
| nur ÖRR/Trad. | 44.353 | 11.702 | 7.1 |

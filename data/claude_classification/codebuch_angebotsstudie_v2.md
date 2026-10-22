# Codebuch Angebotsstudie – Kernversion
## 1. Gegenstand und Einheit

- **Material:** Automatisch erzeugte Transkripte deutschsprachiger YouTube-Videos (Nachrichten-, Politik- und Meinungskanäle aus Deutschland und Österreich), veröffentlicht zwischen 01.01. und 30.04.2022.
- **Codiereinheit:** Segment von ca. 800 Wörtern. Lange Videos bestehen aus mehreren Segmenten; Segmente können mitten im Satz beginnen.
- **Blindheit:** Kanalname, Kanaltyp, Veröffentlichungsdatum und Titel sind den Codierenden nicht bekannt und dürfen nicht erschlossen oder verwendet werden.

## 2. Grundregeln (gelten für alle Blöcke)

1. **Transkriptqualität:** Die Transkripte sind automatisch erzeugt. Eigennamen sind häufig falsch geschrieben, Satzzeichen und Großschreibung fehlen, Wörter sind verschluckt. Erschließe die Bedeutung aus dem Zusammenhang.
2. **Nur der Segmenttext zählt.** Ergänze kein Wissen über Kanal, Sprecher oder den weiteren Videoverlauf.
3. **Mehrere Sprechende:** Transkripte enthalten oft Moderation, Gäste und Einspieler ohne Kennzeichnung. Codiere das Segment als Ganzes, so wie der Kanal es veröffentlicht hat.
4. **Fremdrede:** Zitierte oder eingespielte Fremdrede (O-Töne, Zitate, Interviewpassagen) zählt NICHT zur Codierung dazu, es sei denn, den Positionen wird ausdrücklich zugestimmt oder sie werden ausdrücklich abgelehnt. In diesem Fall sind Zustimmung bzw. Ablehnung als Position des Kanals zu bewerten.
5. **Form, nicht Wahrheit:** Codiert wird, was gesagt wird, nicht ob es zutrifft. Linke und rechte Inhalte werden nach exakt denselben Kriterien bewertet. Die eigene Haltung der Codierenden ist irrelevant.
6. **Reihenfolge und Unabhängigkeit:** Die Blöcke werden in der angegebenen Reihenfolge codiert. Jeder Block wird unabhängig beurteilt; ein Urteil in einem Block begründet kein Urteil in einem anderen. Prüfe Kombinationen von Urteilen nicht auf Stimmigkeit.
7. **Im Zweifel nicht codieren:** Liste-Felder enthalten nur, was klar vorliegt. Rate nicht.
8. **Satire und Ironie:** Codiert wird die gemeinte Aussage, nicht der Wortlaut. Ironisches Lob ist Kritik; Spott über einen Akteur ist eine (negative) Bewertung dieses Akteurs.

## Block A – Gate

**`kodierbar`** (true / false)
- false, wenn das Segment ausschließlich nicht-inhaltliches Material enthält: Werbung, Sponsoring, Intro, Verabschiedung, Small Talk, Spenden- oder Abo-Aufrufe, technische Ansagen.
- Besteht ein Segment überwiegend aus solchem Material, ist es dennoch **true**, sobald es **mindestens eine inhaltliche Aussage mit Bewertung** enthält (z. B. eine spöttische Bemerkung über Corona-Regeln, eine Kritik an Politikern). Bloße Themenankündigungen, Teaser ohne Bewertung oder einzelne Stichworte machen ein Segment nicht kodierbar. Codiert wird dann nur der inhaltliche Teil.
- Bei false: alle übrigen Felder sind null bzw. leere Liste.

## Block B – Themen

**Schwelle:** Ein Thema wird codiert, wenn es im Segment **inhaltlich behandelt** wird, d. h. mindestens ein eigener inhaltlicher Gedanke dazu vorkommt (Information, Einordnung oder Bewertung). Eine bloße Nennung als Stichwort, ein Beispiel in einer Aufzählung oder eine Ankündigung („dazu später mehr“) reicht nicht. In Nachrichtenüberblicken zählt jede inhaltlich ausgeführte Meldung als eigenes Thema.

**`themen`** (Liste, Mehrfachnennung ausdrücklich erlaubt)
**`hauptthema`** (ein Wert aus `themen`: das Thema mit dem größten Anteil am Segment)

**`krieg_bezug`** (explizit / implizit; nur wenn `krieg_ukraine` in `themen`, sonst null)
- explizit = Der Krieg bzw. der Konflikt zwischen Russland und der Ukraine wird ausdrücklich genannt (Krieg, Invasion, Angriff, Ukraine-Krise, Truppenaufmarsch usw.).
- implizit = Der Konflikt wird nicht ausdrücklich genannt, ein Bezug ist aber erkennbar (siehe Abgrenzung zu `krieg_ukraine`).

**Abgrenzungsregeln Themen (ergänzend zur Tabelle):**
- `krieg_ukraine` wird **auch ohne ausdrückliche Nennung des Kriegs** codiert, wenn ein Bezug zum Russland-Ukraine-Konflikt erkennbar ist: russische Gas-, Öl- oder Kohlelieferungen bzw. deren Stopp, Nord Stream (1 oder 2), Abhängigkeit von russischer Energie, Sanktionen gegen Russland, Russland als sicherheitspolitische Bedrohung. Dann `krieg_bezug` = implizit. Ein allgemeiner Russland-Bezug ohne Konfliktbezug (z. B. Sport, Kultur, russische Innenpolitik ohne Bezug zur Ukraine oder zum Westen) reicht nicht.
- Ein „Krieg“ ohne jede Erkennbarkeit, welcher gemeint ist, wird nicht als `krieg_ukraine` codiert.
- Private Geldanlage, Trading, Charttechnik und Börsentipps ohne wirtschaftspolitischen Bezug → `unpolitisch`.

| Wert | Definition | Abgrenzung |
|---|---|---|
| `krieg_ukraine` | Der Konflikt zwischen Russland und der Ukraine, einschließlich der Eskalation vor dem 24.02.2022 (Truppenaufmarsch, Anerkennung von Donezk/Luhansk): Kriegsgeschehen, Diplomatie, Sanktionen, Waffenlieferungen, Geflüchtete aus der Ukraine, Reaktionen westlicher Regierungen, russische Innenpolitik im Zusammenhang mit dem Krieg. | Inlandsfolgen (z. B. Energiepreise) werden **zusätzlich** zu `energie`/`wirtschaft` codiert, wenn ein Bezug zum Krieg hergestellt wird. |
| `corona` | Die COVID-19-Pandemie: Infektionsgeschehen, Maßnahmen, Impfung und Impfpflicht, Belastung des Gesundheitssystems, Proteste gegen Maßnahmen. | Gesundheitspolitik ohne Pandemiebezug → `innenpolitik_sonstige`. |
| `migration` | Zuwanderung, Flucht und Asyl, Integration, Abschiebung, Grenzschutz, Staatsangehörigkeit. | Geflüchtete aus der Ukraine → `migration` **und** `krieg_ukraine`. |
| `wirtschaft` | Wirtschaftslage und Wirtschafts-, Sozial- und Finanzpolitik: Inflation, Wachstum, Arbeitsmarkt, Löhne, Renten, Sozialleistungen, Steuern, Staatsverschuldung, Unternehmen, Finanzmärkte. | Speziell Energiepreise und Energieversorgung → `energie`; allgemeine Teuerung → `wirtschaft`; beides möglich. |
| `energie` | Energieversorgung und Energiepreise: Gas, Öl, Kohle, Atomkraft, erneuerbare Energien als Versorgungsfrage, Pipelines (z. B. Nord Stream), LNG, Entlastungen bei Energiekosten. | Energiewende als Klimaschutzmaßnahme → `klima` (ggf. zusätzlich `energie`). |
| `klima` | Klimawandel und Klimaschutzpolitik: Emissionen, Klimaziele, Klimaaktivismus, klimapolitisch begründete Regulierung (z. B. Verbrennerverbot, Tempolimit). | Wetter ohne Klimabezug → `unpolitisch`. |
| `gender` | Geschlechterpolitik und geschlechtliche bzw. sexuelle Identität: Gleichstellung, Quoten, Feminismus, geschlechtergerechte Sprache, LGBTQ-Rechte, Trans-Debatten, Debatten über „Wokeness“. | — |
| `nahost` | Der Nahostkonflikt: Israel, Palästinensergebiete, Gaza, Antisemitismusdebatten mit Israel-Bezug. | Iran, Hisbollah, Huthi → `iran`. |
| `iran` | Iran: Atomprogramm und Atomabkommen, iranische Innenpolitik, Konflikte Irans mit Israel oder den USA, verbündete Gruppen (Hisbollah, Huthi). | — |
| `eu` | Die EU als politisches System: Institutionen (Kommission, Parlament, Rat), EU-Recht, EU-Haushalt, Erweiterung, Entscheidungsprozesse zwischen den Mitgliedstaaten. | Die EU als bloßer Akteur einer Maßnahme (z. B. „die EU beschließt Sanktionen“) ist nur dann `eu`, wenn die EU-Entscheidungsfindung selbst Thema ist. |
| `usa` | US-amerikanische Innen- und Außenpolitik, US-Regierung und Präsident, Beziehungen Deutschlands bzw. Europas zu den USA. | Die USA als bloßer Akteur im Ukraine-Konflikt → nur `krieg_ukraine`, außer US-Politik selbst wird behandelt. |
| `bildung` | Schule, Hochschule, Kinderbetreuung, Bildungspolitik. | Schulschließungen wegen Corona → `bildung` **und** `corona`. |
| `innenpolitik_sonstige` | Innenpolitik (Deutschland oder Österreich), die keiner obigen Kategorie zuzuordnen ist: Parteienwettbewerb, Wahlen und Umfragen, Regierungsbildung und Personalien, Parlamentsbetrieb, innere Sicherheit, Extremismus, Justiz, Gesundheitspolitik ohne Pandemiebezug, Infrastruktur, Verteidigungspolitik ohne Kriegsbezug. | — |
| `sonstiges_politisch` | Politische Themen anderer Länder, die keiner obigen Kategorie zuzuordnen sind (z. B. China, Frankreich, andere Konflikte), sowie gesellschaftspolitische Themen ohne eigene Kategorie. | — |
| `unpolitisch` | Kein politischer Inhalt: Unterhaltung, Sport, Lifestyle, Wetter, Kriminalität ohne politische Dimension, Ratgeber, private Geldanlage ohne wirtschaftspolitischen Bezug. | Nur codieren, wenn kein anderes Thema vorliegt. |

## Block C – Kriegsaspekte

Nur wenn `krieg_ukraine` in `themen`; sonst leere Liste.

**`krieg_aspekte`** (Liste aller inhaltlich behandelten Aspekte, Schwelle wie Block B)

| Wert | Definition |
|---|---|
| `kriegsgeschehen_militaer` | Militärische Lage, Kampfhandlungen, Truppenbewegungen, Waffensysteme, militärische Analyse |
| `kriegsverbrechen_zivilisten` | Leid und Opfer der Zivilbevölkerung, Angriffe auf zivile Ziele, Kriegsverbrechen |
| `verhandlungen_diplomatie` | Verhandlungen, Waffenstillstand, Diplomatie, Gipfeltreffen, Vermittlung |
| `waffenlieferungen` | Lieferung von Waffen und militärischer Ausrüstung an die Ukraine |
| `sanktionen` | Sanktionen gegen Russland und ihre Wirkung (inkl. Energie-Embargo als Sanktion) |
| `finanzhilfe` | Finanzielle oder humanitäre Hilfe für die Ukraine |
| `nato_eu_beitritt` | NATO- oder EU-Beitritt bzw. -Erweiterung (Ukraine, Finnland, Schweden), NATO-Osterweiterung |
| `truppen_einsatz` | Entsendung westlicher Truppen (z. B. NATO-Ostflanke), Flugverbotszone, direkte Kriegsbeteiligung |
| `gefluechtete` | Flucht aus der Ukraine, Aufnahme und Versorgung von Geflüchteten |
| `energie_preise_inland` | Energieversorgung und -preise in Deutschland bzw. Europa im Zusammenhang mit dem Krieg (inkl. russische Lieferungen, Lieferstopp, Nord Stream) |
| `wirtschaft_inland` | Sonstige wirtschaftliche Folgen in Deutschland bzw. Europa ohne Energiebezug: Inflation allgemein, Lieferketten, Produktion, Unternehmen, Märkte |
| `bundeswehr_sondervermoegen` | Bundeswehr, Verteidigungsausgaben, Sondervermögen, Aufrüstung |
| `russland_innen` | Russische Innenpolitik, Repression, Proteste, Stimmung in Russland |
| `medien_desinformation` | Berichterstattung, Propaganda, Desinformation, Zensur rund um den Krieg (inkl. RT-Verbot) |
| `sonstiges` | Andere Aspekte des Kriegs |

## Block D – Position gegenüber Russland

Nur wenn `krieg_ukraine` in `themen`; sonst beide Felder null.

**`rus_status`:** Beurteile, ob Russland/die russische Politik in dem Segment thematisiert und bewertet wird:
  nicht_thematisiert = Russland/die russische Politik wird nicht thematisiert
  deskriptiv = Russland/die russische Politik wird thematisiert, aber nur deskriptiv. Es werden keine Bewertungen vorgenommen.
  bewertend = Russland/die russische Politik wird thematisiert und es werden Bewertungen (positiv, negativ, oder beides) vorgenommen.

**`rus_score`** (nur bei rus_status = "bewertend", sonst null):
 +2 = Russisches Handeln wird gerechtfertigt oder als legitim/notwendig dargestellt; die Hauptverantwortung fuer den Krieg wird der Ukraine, der NATO oder dem Westen zugeschrieben.
 +1 = Russisches Handeln wird relativiert, erklaert oder entlastet (z. B. Verweis auf Provokation, Sicherheitsinteressen, doppelte Standards), ohne es voll zu legitimieren; oder Verantwortung wird deutlich geteilt zugeschrieben.
  0 = Bewertende Elemente vorhanden, aber gegenlaeufig oder ausgewogen; keine Richtung ueberwiegt.
 -1 = Russisches Handeln wird kritisiert oder Russland wird Verantwortung zugeschrieben, ohne starke Zuspitzung.
 -2 = Russisches Handeln wird als illegitim, aggressiv, verbrecherisch dargestellt; klare Alleinverantwortung Russlands; ggf. Delegitimierung der russischen Fuehrung.

**Ergänzende Regel:**
- Etablierte Bezeichnungen wie „Angriffskrieg“, „russischer Angriffskrieg“, „Invasion“ oder „Krieg Russlands gegen die Ukraine“ sind für sich genommen **keine Bewertung**. `rus_status` = bewertend erst, wenn darüber hinaus gewertet wird (z. B. verbrecherisch, Verachtung, Lügen, Rechtfertigung oder Relativierung).

## Block E – Politisches Establishment

**Gegenstand** ist das etablierte politische Lager, d. h. die politischen Akteure und Institutionen, die das politische System tragen. Erfasst wird, ob und wie sie bewertet werden. Im Mittelpunkt steht pauschale, häufig populistische Kritik an „den etablierten Parteien“ bzw. „der Politik“; es wird daher **ein gemeinsamer Score** für alle Ziele vergeben.

**Zum Establishment gehören:**
- die deutsche Bundesregierung (im gesamten Zeitraum die Koalition aus SPD, Grünen und FDP, „Ampel“): Regierung als Ganzes, Bundeskanzler (Olaf Scholz), Bundesminister:innen in ihrer Regierungsrolle (z. B. Habeck, Baerbock, Lindner, Lauterbach, Lambrecht, Faeser), die Koalition;
- etablierte Parteien außerhalb ihrer Regierungsrolle bzw. in der Opposition, v. a. CDU/CSU, sowie pauschal „die etablierten Parteien“, „die Altparteien“, „die Kartellparteien“;
- „die Politik“, „die Politiker“, „die da oben“, „die Regierenden“, „der Staat“, „das System“, wenn damit die politische Führung bzw. Klasse als unbestimmte Gesamtheit gemeint ist;
- weitere staatliche Institutionen und Amtsträger: Bundestag als Ganzes, Landesregierungen und Ministerpräsident:innen, Bundespräsident, frühere Bundesregierungen (z. B. Merkel), Behörden (z. B. RKI, Gesundheitsämter, Polizei, Gerichte) als Teil staatlichen Handelns.
- weiterhin gehören zum Establishment auch die österreichische Regierung oder die EU (oder einzelne ihrer Institutionen)

**`estab_status`** (nicht_thematisiert / deskriptiv / bewertend)
- nicht_thematisiert = Kein Akteur des Establishments kommt vor.
- deskriptiv = Akteure des Establishments kommen vor (Handlungen, Aussagen, Pläne), ohne dass sie bewertet werden.
- bewertend = Akteure des Establishments oder ihr Handeln werden positiv, negativ oder beides bewertet – explizit oder implizit (siehe `estab_explizit`).

**`estab_explizit`** (explizit / implizit; nur bei bewertend, sonst null)
- explizit = Ein Akteur des Establishments wird genannt und ausdrücklich bewertet (z. B. „die Regierung hat versagt“, „Scholz zögert unverantwortlich“, „die Politiker belügen uns“).
- implizit = Die Bewertung erschließt sich aus Ironie, Spott, Anspielung oder Übertreibung, oder es werden **konkrete politische Maßnahmen bzw. Entscheidungen** kritisiert (z. B. „die Corona-Regeln“, „2G“, „die Impfpflicht“, „die Sanktionen“), ohne dass ein Akteur ausdrücklich bewertet wird. 
- **Keine Bewertung** ist das bloße Beklagen eines Zustands ohne Bezug auf politisches Handeln oder einen Akteur (z. B. „alles wird teurer“, „die Lage ist schlimm“).

**`estab_score`** (nur bei bewertend, sonst null): Gesamtbewertung des Establishments im Segment.
 +2 = Deutliche Zustimmung oder Verteidigung.
 +1 = Überwiegend zustimmend, mit Einschränkungen.
  0 = Zustimmende und kritische Elemente halten sich die Waage.
 −1 = Überwiegend kritisch.
 −2 = Grundsätzliche Ablehnung oder scharfe Kritik.
Werden verschiedene Ziele unterschiedlich bewertet, entscheidet die im Segment überwiegende Bewertung.

**`estab_gegenstand`** (Liste; nur bei bewertend, sonst leer): Worauf bezieht sich die Bewertung?
- `kriegspolitik` = Haltung und Maßnahmen gegenüber dem Ukraine-Krieg (Waffen, Sanktionen, Diplomatie, Bündnispolitik) – auch Positionen von Oppositionsparteien dazu.
- `kriegsfolgen_inland` = Umgang mit Energiepreisen, Inflation, Versorgung als Folge des Kriegs bzw. der Sanktionen.
- `corona` = Corona-Politik (Maßnahmen, Impfpflicht).
- `migration` = Migrations- und Asylpolitik.
- `wirtschaft_soziales` = Wirtschafts-, Finanz-, Sozialpolitik ohne Kriegsbezug.
- `energie_klima` = Energie- und Klimapolitik ohne Kriegsbezug.
- `gesellschaft_kultur` = Gesellschaftspolitik (z. B. Gender, Cannabis, Staatsbürgerschaft).
- `kompetenz_fuehrung_kommunikation` = Fähigkeit, Führung, Auftreten, Glaubwürdigkeit, Kommunikation, unabhängig vom Politikfeld.
- `sonstiges`

**`estab_kritik_richtung`** (nur wenn `estab_score` < 0 **und** `kriegspolitik` in `estab_gegenstand`, sonst null)
- `zu_zoegerlich` = Die Ukraine wird zu wenig oder zu langsam unterstützt, Sanktionen sind zu mild, zu nachgiebig gegenüber Russland.
- `zu_weitgehend` = Eskalation, zu viele oder zu schwere Waffen, Sanktionen schaden dem eigenen Land mehr als Russland, zu wenig Verhandlung, Kriegstreiberei.
- `sonstige` = Kritik an der Kriegspolitik ohne eine dieser Richtungen (z. B. Abstimmung, Kommunikation, Glaubwürdigkeit).

**`estab_intensitaet`** (nur wenn `estab_score` < 0, sonst null)
- 0 = Sachliche Kritik an Entscheidungen oder Vorgehen.
- 1 = Abwertender Ton: Spott, Häme, persönliche Herabsetzung, Unfähigkeitsvorwurf.
- 2 = Delegitimierung: Das Establishment handle bewusst gegen die eigene Bevölkerung, sei illegitim, verräterisch, fremdgesteuert oder müsse „weg“, weil es gegen das Volk arbeite.
- Eine sachlich begründete Forderung nach Rücktritt, Koalitionsende oder Neuwahl ist **nicht** Stufe 2 (in der Regel 0 oder 1, je nach Ton).

**Ergänzende Regeln:**
- **Selbstdarstellung:** Rechtfertigt oder lobt ein Akteur des Establishments die eigene Politik (z. B. im O-Ton „es ist absolut notwendig, dass wir …“), ist das **bewertend** (in der Regel +1 oder +2).
- **Forderungen und Fragen:** Eine Forderung Dritter an die Politik ohne Wertung („die Regierung soll nachbessern“) und eine kritische Moderationsfrage allein sind deskriptiv. Bewertend erst, wenn das Handeln ausdrücklich oder erkennbar (implizit) als falsch, unzureichend oder richtig beurteilt wird.

## Ausgabeformat

Pro Segment **eine JSON-Zeile** mit genau diesen Feldern in genau dieser Reihenfolge, ohne Begründung, ohne Markdown:

```
segment_id, kodierbar, themen, hauptthema, krieg_bezug, krieg_aspekte,
rus_status, rus_score,
estab_status, estab_explizit, estab_score, estab_gegenstand, estab_kritik_richtung, estab_intensitaet
```

Beispiel (fiktiv, nicht kodierbar):
```
{"segment_id":"a1b2c3d4e5_s000","kodierbar":false,"themen":[],"hauptthema":null,"krieg_bezug":null,"krieg_aspekte":[],"rus_status":null,"rus_score":null,"estab_status":null,"estab_explizit":null,"estab_score":null,"estab_gegenstand":[],"estab_kritik_richtung":null,"estab_intensitaet":null}
```

**Konventionen für bedingte Felder:**
- Listen-Felder bei nicht erfüllter Bedingung: leere Liste `[]`; skalare Felder: null.
- Bei `kodierbar` = true und ohne Kriegsbezug: `krieg_bezug`, `rus_status`, `rus_score` = null, `krieg_aspekte` = [].
- Bei `kodierbar` = true ist `estab_status` immer gesetzt (mindestens „nicht_thematisiert“).

## Validierungsregeln (automatische Prüfung)

1. Enums und Wertebereiche wie oben; `hauptthema` ∈ `themen`; `unpolitisch` nur allein.
2. `kodierbar` = false ⇒ alle übrigen Felder null bzw. leer.
3. `krieg_bezug`, `krieg_aspekte`, `rus_status` nur bei `krieg_ukraine` in `themen`; dann `krieg_bezug` und `rus_status` gesetzt.
4. `rus_score` / `estab_score` genau dann gesetzt, wenn zugehöriger Status = bewertend.
5. `estab_explizit` und `estab_gegenstand` genau dann gesetzt bzw. nicht leer, wenn `estab_status` = bewertend.
6. `estab_intensitaet` genau dann gesetzt, wenn `estab_score` < 0; `estab_kritik_richtung` genau dann, wenn zusätzlich `kriegspolitik` in `estab_gegenstand`.

## Versionierung

- **2.0 (20.10.2026):** Kernversion von 1.3 für den Vollauf (Felder siehe Kopf). Regeln und Definitionen unverändert.

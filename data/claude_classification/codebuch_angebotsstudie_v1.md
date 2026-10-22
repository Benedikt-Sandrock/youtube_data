# Codebuch Angebotsstudie – Transkript-Inhaltsanalyse
Version 1.3 · Stand 19.10.2026 (Änderungen gegenüber früheren Versionen am Ende)

Dieses Codebuch ist zugleich die vollständige Codieranweisung. Es ist ohne weiteres Projektwissen anwendbar.

## 1. Gegenstand und Einheit

- **Material:** Automatisch erzeugte Transkripte deutschsprachiger YouTube-Videos (Nachrichten-, Politik- und Meinungskanäle aus Deutschland und Österreich), veröffentlicht zwischen 01.01. und 30.04.2022.
- **Codiereinheit:** Segment von ca. 800 Wörtern. Lange Videos bestehen aus mehreren Segmenten.
- **Kontext:** Zu jedem Segment kann das Ende des vorangehenden Segments desselben Videos angezeigt werden. Es dient nur dem Verständnis und wird **nicht** mitcodiert.
- **Blindheit:** Kanalname, Kanaltyp, Veröffentlichungsdatum und Titel sind den Codierenden nicht bekannt und dürfen nicht erschlossen oder verwendet werden.

## 2. Grundregeln (gelten für alle Blöcke)

1. **Transkriptqualität:** Die Transkripte sind automatisch erzeugt. Eigennamen sind häufig falsch geschrieben, Satzzeichen und Großschreibung fehlen, Wörter sind verschluckt. Erschließe die Bedeutung aus dem Zusammenhang.
2. **Nur der Segmenttext zählt.** Ergänze kein Wissen über Kanal, Sprecher oder den weiteren Videoverlauf.
3. **Mehrere Sprechende:** Transkripte enthalten oft Moderation, Gäste und Einspieler ohne Kennzeichnung. Codiere das Segment als Ganzes, so wie der Kanal es veröffentlicht hat.
4. **Fremdrede:** Zitierte oder eingespielte Fremdrede (O-Töne, Zitate, Interviewpassagen) zählt zur Codierung dazu. Die Auswahl zitierter Rede gilt als redaktionelle Entscheidung des Kanals.
5. **Zurückgewiesene Positionen:** Wird eine Position ausdrücklich als fremde eingeführt („Kritiker sagen …“) und vom Sprecher im selben Zug eindeutig zurückgewiesen oder relativiert, zählt sie nicht als Position des Kanals. Das gilt nicht für eingespielte oder zitierte Fremdrede ohne Widerspruch (dort gilt Regel 4).
6. **Form, nicht Wahrheit:** Codiert wird, was gesagt wird, nicht ob es zutrifft. Linke und rechte Inhalte werden nach exakt denselben Kriterien bewertet. Die eigene Haltung der Codierenden ist irrelevant.
7. **Reihenfolge und Unabhängigkeit:** Die Blöcke werden in der angegebenen Reihenfolge codiert. Jeder Block wird unabhängig beurteilt; ein Urteil in einem Block begründet kein Urteil in einem anderen. Prüfe Kombinationen von Urteilen nicht auf Stimmigkeit.
8. **Im Zweifel nicht codieren:** Liste-Felder enthalten nur, was klar vorliegt. Rate nicht.
9. **Satire und Ironie:** Codiert wird die gemeinte Aussage, nicht der Wortlaut. Ironisches Lob ist Kritik; Spott über einen Akteur ist eine (negative) Bewertung dieses Akteurs.
10. **Gäste vs. Fremdrede:** Eingeladene Gäste in einem live bzw. im Studio geführten Gespräch (Interview, Talk, Debatte) sind **keine Fremdrede** im Sinne von `fremdrede_dominant`. Fremdrede ist nur eingespielte, zitierte oder übertragene Rede (O-Töne, Mitschnitte, Pressekonferenzen, Parlamentsreden, Zitate). Ausnahme: Bei `estab_urheber` zählen Gäste als `fremdrede` (siehe Block F).

---

## Block A – Gate und Form

**`kodierbar`** (true / false)
- false, wenn das Segment ausschließlich nicht-inhaltliches Material enthält: Werbung, Sponsoring, Intro, Verabschiedung, Small Talk, Spenden- oder Abo-Aufrufe, technische Ansagen.
- Besteht ein Segment überwiegend aus solchem Material, ist es dennoch **true**, sobald es **mindestens eine inhaltliche Aussage mit Bewertung** enthält (z. B. eine spöttische Bemerkung über Corona-Regeln, eine Kritik an Politikern). Bloße Themenankündigungen, Teaser ohne Bewertung oder einzelne Stichworte machen ein Segment nicht kodierbar. Codiert wird dann nur der inhaltliche Teil.
- Bei false: alle Felder der Blöcke B–H sind null bzw. leere Liste. `redeform` und `fremdrede_dominant` werden trotzdem codiert.

**`redeform`** (monolog / gespraech / beitrag / unklar)
- monolog = eine Person spricht überwiegend allein (Kommentar, Vlog, Rede).
- gespraech = Interview, Diskussion, Talk, Pressekonferenz mit Fragen.
- beitrag = redaktionell geschnittener Bericht: Sprechertext mit eingespielten O-Tönen.
- unklar = nicht bestimmbar.

**`fremdrede_dominant`** (true / false)
- true, wenn der überwiegende Teil des Segments aus zitierter oder eingespielter Fremdrede besteht (z. B. übertragene Politikerrede, eingespielte Pressekonferenz), sonst false.
- Antworten eingeladener Gäste im Gespräch zählen **nicht** als Fremdrede (Grundregel 10). Ein Segment, das nur aus einer durchgehenden Rede bzw. einem Statement einer Person ohne erkennbare Moderation besteht und erkennbar eine Rede, Pressekonferenz oder ein Statement wiedergibt, ist true.

---

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

---

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

---

## Block D – Populismus

Bewerte das Segment auf vier unabhängigen Dimensionen (Skala jeweils 0 bis 3). Eine hohe Bewertung auf einer Dimension erzwingt keine hohe Bewertung auf einer anderen. Bei `kodierbar` = false alle vier null.

### `volkszentrismus`

Beruft sich der Text auf "das Volk", "die Buerger", "die Menschen", "die Mehrheit" als eine EINHEITLICHE Groesse mit einem gemeinsamen Willen, und stellt sich der Sprecher als deren Stimme dar?

0  Keine Berufung auf ein kollektives Volk, oder nur als sachliche Bevoelkerungsangabe ("40 Prozent der Befragten").
1  Vereinzelte Berufung auf "die Buerger" oder "die Menschen", ohne dass ihnen ein einheitlicher Wille zugeschrieben wird.
2  Dem Volk wird wiederholt ein gemeinsamer Wille oder gesunder Menschenverstand zugeschrieben, dem etwas entgegensteht.
3  Der Sprecher tritt ausdruecklich als Stimme des Volkes auf; der Volkswille ist eindeutig, einheitlich und wird missachtet.

Abgrenzung: Die Nennung einer konkreten Gruppe (Rentner, Landwirte, Ostdeutsche) ist NICHT Volkszentrismus, solange sie nicht mit dem Ganzen gleichgesetzt wird.

### `antielitismus`

Werden Eliten ALS GRUPPE angegriffen - als eigennuetzig, abgehoben, verlogen oder gegen die Bevoelkerung handelnd? Eliten koennen Politik, Medien, Wissenschaft, Justiz, EU, Konzerne oder NGOs sein.

0  Keine Elitenkritik, oder ausschliesslich sachliche Kritik an einer konkreten Entscheidung oder Person - auch wenn dabei mehrere belegte Einzelfaelle aufgezaehlt werden, die zusammengenommen ein Muster ergeben, solange die Darstellung differenziert bleibt (Quellenangaben, Gegenposition, eingeraeumte Unsicherheiten, auch positives oder reaktives Verhalten der kritisierten Seite werden benannt).
1  Kritik an einzelnen Akteuren mit abwertendem Unterton, aber ohne Verallgemeinerung auf eine Klasse. Ebenso hierher gehoert: Eine Institution wird fuer aus sich selbst heraus erklaerbares Eigeninteresse kritisiert (z. B. ein Unternehmen maximiert Gewinn, eine Organisation schuetzt die eigenen Leute), ohne dass ihr ein gegen die Allgemeinheit gerichtetes, koordiniertes Motiv unterstellt wird.
2  Eliten werden als Gruppe kritisiert, der ein bewusst GEGEN DIE BEVOELKERUNG gerichtetes gemeinsames Motiv oder eine gemeinsame Abgehobenheit unterstellt wird - nicht blosses Eigeninteresse, sondern eine unterstellte Frontstellung gegen "die Menschen da draussen".
3  Eliten erscheinen als geschlossenes System, das bewusst gegen die Bevoelkerung arbeitet, taeuscht oder ein Kartell bildet.

Abgrenzung: "Die Regierung hat bei der Rente falsch entschieden" ist 0. "Die da oben interessiert nicht, was mit uns passiert" ist 2 bis 3. Entscheidend ist die Unterstellung eines GEGEN DIE ALLGEMEINHEIT gerichteten gemeinsamen Motivs. Weder die Schaerfe des Tons noch die Anzahl aufgezaehlter Einzelfaelle noch die blosse Tatsache, dass eine Institution im eigenen Interesse handelt, reicht fuer sich genommen fuer Stufe 2 oder 3.

### `manichaeische_moralisierung`

Wird der Konflikt als moralische Zweiteilung dargestellt - eine Seite gut, die andere boese - ohne legitime Zwischenpositionen?

0  Positionen werden als sachlich verschieden dargestellt; Gegenargumente erscheinen als vertretbar.
1  Eine Seite wird deutlich bevorzugt, die andere aber nicht moralisch disqualifiziert.
2  Die Gegenseite wird ueberwiegend moralisch statt sachlich diskreditiert; Zwischenpositionen kommen kaum vor.
3  Vollstaendige moralische Zweiteilung: Gut gegen Boese, Wahrheit gegen Luege, keine legitime abweichende Position denkbar.

Abgrenzung: Die Verurteilung eines Kriegsverbrechens oder eines Terroranschlags ist fuer sich genommen KEINE manichaeische Moralisierung. Entscheidend ist, ob politische MEINUNGSVERSCHIEDENHEITEN moralisiert werden.

### `emotionale_intensitaet`

Wie stark ist die affektive Aufladung - Empoerung, Angst, Dramatisierung, Pathos? Diese Dimension misst NICHT Populismus, sondern dient als Kontrollgroesse.

0  Nuechtern, berichtend, analytisch.
1  Erkennbare Anteilnahme oder Zuspitzung, insgesamt sachlich.
2  Deutlich emotionalisiert: Empoerung, Dringlichkeit, drastische Bilder.
3  Durchgehend hochemotional: Alarm, Untergang, Existenzbedrohung, Pathos.

*(Wortlaut der Dimensionen übernommen aus dem Prompt POPULISMUS_P der bisherigen Populismusmessung.)*

---

## Block E – Position zum Ukraine-Krieg

Nur wenn `krieg_ukraine` in `themen`; sonst alle vier Felder null.

### Dimension 1 – Position gegenüber Russland

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

### Dimension 2 – Position gegenüber der westlichen Ukraine-Politik

Gehe fuer diese Dimension erneut an den Segmenttext. Das Urteil aus Dimension 1 ist fuer Dimension 2 ohne Bedeutung.

Gegenstand ist die Politik westlicher Akteure (Bundesregierung, EU, NATO, USA) gegenueber dem Krieg - nicht die Ukraine als Land und nicht westliche Politik im Allgemeinen.

**`west_status`:** Beurteile, ob westliche Ukraine-Politik in dem Segment thematisiert und bewertet wird:
  nicht_thematisiert = Westliche Ukraine-Politik wird nicht thematisiert
  deskriptiv = Westliche Ukraine-Politik wird thematisiert, aber nur deskriptiv. Es werden keine Bewertungen vorgenommen.
  bewertend = Westliche Ukraine-Politik wird thematisiert und es werden Bewertungen (positiv, negativ, oder beides) vorgenommen.

**`west_score`** (nur bei west_status = "bewertend", sonst null):
 +2 = Deutliche Unterstuetzung; Forderung nach mehr/staerkerem Engagement; westliche Politik erscheint als richtig und geboten.
 +1 = Ueberwiegende Zustimmung mit Einschraenkungen, oder Unterstuetzung des Ziels bei Kritik an der Umsetzung (zu langsam, zu zoegerlich).
  0 = Zustimmende und ablehnende Elemente halten sich die Waage.
 -1 = Ueberwiegende Kritik: Zweifel an Wirksamkeit, Kosten, Eskalationsrisiko; Ruf nach Zurueckhaltung oder Verhandlungen statt Unterstuetzung.
 -2 = Grundsaetzliche Ablehnung; westliche Politik erscheint als falsch, schaedlich, eskalierend oder fremdgesteuert; Forderung nach Beendigung der Unterstuetzung.

HINWEIS: Die beiden Dimensionen sind unabhaengig. Scharfe Russlandkritik bei gleichzeitiger Ablehnung westlicher Unterstuetzungspolitik ist eine regulaere, kohaerente Position und keine Inkonsistenz. Ebenso ist Zustimmung zur westlichen Politik ohne jede Russlandbewertung moeglich. Pruefe die Kombination deiner beiden Urteile nicht auf Stimmigkeit.

*(Wortlaut übernommen aus dem Prompt POSITION_V1 der bisherigen Positionsmessung.)*

**Ergänzende Regeln (Version 1.0):**
- Etablierte Bezeichnungen wie „Angriffskrieg“, „russischer Angriffskrieg“, „Invasion“ oder „Krieg Russlands gegen die Ukraine“ sind für sich genommen **keine Bewertung**. `rus_status` = bewertend erst, wenn darüber hinaus gewertet wird (z. B. verbrecherisch, Verachtung, Lügen, Rechtfertigung oder Relativierung).
- Abgrenzung `west_score` +1 / −1: Kritik, die westlichen Maßnahmen gehen **nicht weit genug** (zu langsam, zu schwach, zu zögerlich), ist +1 (Ziel unterstützt). Kritik, die Maßnahmen **brächten nichts oder schadeten** (wirkungslos, zu teuer, eskalierend), ist −1. Die **Forderung, Maßnahmen oder Unterstützung zu beenden** (auch Sanktionen), ist −2.

---

## Block F – Politisches Establishment

**Gegenstand** ist das etablierte politische Lager in Deutschland bzw. Österreich, d. h. die politischen Akteure und Institutionen, die das politische System tragen. Erfasst wird, ob und wie sie bewertet werden. Im Mittelpunkt steht pauschale, häufig populistische Kritik an „den etablierten Parteien“ bzw. „der Politik“; es wird daher **ein gemeinsamer Score** für alle Ziele vergeben.

**Zum Establishment gehören:**
- die deutsche Bundesregierung (im gesamten Zeitraum die Koalition aus SPD, Grünen und FDP, „Ampel“): Regierung als Ganzes, Bundeskanzler (Olaf Scholz), Bundesminister:innen in ihrer Regierungsrolle (z. B. Habeck, Baerbock, Lindner, Lauterbach, Lambrecht, Faeser), die Koalition;
- die österreichische Bundesregierung (Bundeskanzler, Minister:innen, Koalition);
- etablierte Parteien außerhalb ihrer Regierungsrolle bzw. in der Opposition, v. a. CDU/CSU (in Österreich z. B. ÖVP, SPÖ, Grüne, NEOS als Parteien), sowie pauschal „die etablierten Parteien“, „die Altparteien“, „die Kartellparteien“;
- „die Politik“, „die Politiker“, „die da oben“, „die Regierenden“, „der Staat“, „das System“, wenn damit die politische Führung bzw. Klasse als unbestimmte Gesamtheit gemeint ist;
- weitere staatliche Institutionen und Amtsträger: Bundestag/Nationalrat als Ganzes, Landesregierungen und Ministerpräsident:innen, Bundespräsident, frühere Bundesregierungen (z. B. Merkel), Behörden (z. B. RKI, Gesundheitsämter, Polizei, Gerichte) als Teil staatlichen Handelns.

**Werte für `estab_ziel`:**
- `bundesregierung` = die deutsche Bundesregierung (erster Punkt oben).
- `sonstiges_establishment` = alle übrigen Akteure des Establishments (alle weiteren Punkte oben).

**Nicht zum Establishment gehören:** AfD, FPÖ, Die Linke, Medien (→ Block H), die EU (→ Block E, westliche Politik), ausländische Regierungen, einzelne Experten oder Wissenschaftler ohne staatliche Funktion.

**`estab_status`** (nicht_thematisiert / deskriptiv / bewertend)
- nicht_thematisiert = Kein Akteur des Establishments kommt vor.
- deskriptiv = Akteure des Establishments kommen vor (Handlungen, Aussagen, Pläne), ohne dass sie bewertet werden.
- bewertend = Akteure des Establishments oder ihr Handeln werden positiv, negativ oder beides bewertet – explizit oder implizit (siehe `estab_explizit`).

**`estab_ziel`** (Liste; nur bei deskriptiv oder bewertend, sonst leer): `bundesregierung` und/oder `sonstiges_establishment`, je nachdem, wer vorkommt (bei bewertend: wer bewertet wird).

**`estab_explizit`** (explizit / implizit; nur bei bewertend, sonst null)
- explizit = Ein Akteur des Establishments wird genannt und ausdrücklich bewertet (z. B. „die Regierung hat versagt“, „Scholz zögert unverantwortlich“, „die Politiker belügen uns“).
- implizit = Die Bewertung erschließt sich aus Ironie, Spott, Anspielung oder Übertreibung, oder es werden **konkrete politische Maßnahmen bzw. Entscheidungen** kritisiert (z. B. „die Corona-Regeln“, „2G“, „die Impfpflicht“, „die Sanktionen“), ohne dass ein Akteur ausdrücklich bewertet wird. Implizite Kritik an Maßnahmen ohne genannten Akteur erhält das Ziel `sonstiges_establishment`, sofern nicht erkennbar die Bundesregierung gemeint ist.
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

**`estab_urheber`** (nur bei bewertend, sonst null): Von wem stammt die Bewertung überwiegend?
- `kanal` = Moderation, Kommentator oder Kanalbetreiber selbst.
- `fremdrede` = zitierte oder eingespielte Akteure (z. B. Opposition, Experten, Bürger) **sowie eingeladene Gäste im Gespräch** und Politiker:innen im O-Ton.
- `beides` = beide in nennenswertem Umfang.
- `unklar` = nicht bestimmbar.

**Ergänzende Regeln:**
- **Selbstdarstellung:** Rechtfertigt oder lobt ein Akteur des Establishments die eigene Politik (z. B. im O-Ton „es ist absolut notwendig, dass wir …“), ist das **bewertend** (in der Regel +1 oder +2) mit `estab_urheber` = `fremdrede`.
- **Forderungen und Fragen:** Eine Forderung Dritter an die Politik ohne Wertung („die Regierung soll nachbessern“) und eine kritische Moderationsfrage allein sind deskriptiv. Bewertend erst, wenn das Handeln ausdrücklich oder erkennbar (implizit) als falsch, unzureichend oder richtig beurteilt wird.
- **Abgrenzung zum Populismusblock:** `antielitismus` (Block D) misst die Form der Elitenkritik (Gruppenbezug, unterstellte Frontstellung gegen das Volk). Block F misst Ziel, Gegenstand, Richtung und Stärke der Bewertung. Beide werden unabhängig codiert.

---

## Block G – Verantwortung für Kriegsfolgen im Inland

**`folgen_verantwortung`** (Liste oder null)
- **null**, wenn keine Inlandsfolgen des Kriegs thematisiert werden (Energiepreise, Inflation, Versorgungsengpässe, Kosten durch Geflüchtete, wirtschaftliche Einbußen in Deutschland/Österreich/Europa).
- Werden Inlandsfolgen thematisiert: Liste aller Akteure, denen **Verantwortung** für diese Folgen zugeschrieben wird: `russland`, `establishment` (Bundesregierung, etablierte Parteien oder „die Politik“ im Sinne von Block F), `eu_westen_sanktionen` (EU, Westen, NATO, USA oder die Sanktionspolitik), `ukraine`, `andere` (z. B. Spekulanten, Konzerne, frühere Regierungen, österreichische Regierung).
- **Leere Liste**, wenn Inlandsfolgen thematisiert werden, aber niemandem Verantwortung zugeschrieben wird.

---

## Block H – Medienkritik

**`medienkritik`** (Liste; leer = keine)
Kritische Thematisierung anderer Medien bzw. ihrer Berichterstattung (Einseitigkeit, Lügen, Propaganda, Zensur, Versagen). Sachliche Erwähnung („wie die FAZ berichtet“) ist keine Medienkritik.
- `etablierte_medien` = öffentlich-rechtlicher Rundfunk, Zeitungen, Nachrichtensender, „die Medien“, „Mainstream“, „Systemmedien“, „Lügenpresse“.
- `alternative_medien` = Blogs, Influencer, Alternativmedien, Telegram-Kanäle, „Querdenker-Medien“.
- `russische_staatsmedien` = RT, Sputnik, russisches Staatsfernsehen, russische Propaganda.
- `soziale_medien_plattformen` = Plattformbetreiber (YouTube, Facebook, Twitter usw.): Löschungen, Sperren, Algorithmen, Zensur.

---

## Ausgabeformat

Pro Segment **eine JSON-Zeile** mit genau diesen Feldern in genau dieser Reihenfolge, ohne Begründung, ohne Markdown:

```
segment_id, kodierbar, redeform, fremdrede_dominant,
themen, hauptthema, krieg_bezug,
krieg_aspekte,
volkszentrismus, antielitismus, manichaeische_moralisierung, emotionale_intensitaet,
rus_status, rus_score, west_status, west_score,
estab_status, estab_ziel, estab_explizit, estab_score, estab_gegenstand, estab_kritik_richtung, estab_intensitaet, estab_urheber,
folgen_verantwortung,
medienkritik
```

Beispiel (fiktiv, nicht kodierbar):
```
{"segment_id":"a1b2c3d4e5_s000","kodierbar":false,"redeform":"monolog","fremdrede_dominant":false,"themen":[],"hauptthema":null,"krieg_bezug":null,"krieg_aspekte":[],"volkszentrismus":null,"antielitismus":null,"manichaeische_moralisierung":null,"emotionale_intensitaet":null,"rus_status":null,"rus_score":null,"west_status":null,"west_score":null,"estab_status":null,"estab_ziel":[],"estab_explizit":null,"estab_score":null,"estab_gegenstand":[],"estab_kritik_richtung":null,"estab_intensitaet":null,"estab_urheber":null,"folgen_verantwortung":null,"medienkritik":[]}
```

**Konventionen für bedingte Felder:**
- Listen-Felder bei nicht erfüllter Bedingung: leere Liste `[]` (Ausnahme `folgen_verantwortung`: null).
- Skalare Felder bei nicht erfüllter Bedingung: null.
- Bei `kodierbar` = true und ohne Kriegsbezug: `rus_status`/`west_status` = null (nicht „nicht_thematisiert“).
- Bei `kodierbar` = true ist `estab_status` immer gesetzt (mindestens „nicht_thematisiert“).

## Validierungsregeln (automatische Prüfung)

1. Enums und Wertebereiche wie oben; `hauptthema` ∈ `themen`; `unpolitisch` nur allein.
2. `kodierbar` = false ⇒ alle Felder der Blöcke B–H null bzw. leer.
3. Block C, E und `krieg_bezug` nur bei `krieg_ukraine` in `themen`; dann ist `krieg_bezug` gesetzt.
4. `rus_score` / `west_score` / `estab_score` genau dann gesetzt, wenn zugehöriger Status = bewertend.
5. `estab_ziel` genau dann nicht leer, wenn `estab_status` ∈ {deskriptiv, bewertend}; `estab_explizit`, `estab_gegenstand`, `estab_urheber` genau dann gesetzt, wenn bewertend.
6. `estab_intensitaet` genau dann gesetzt, wenn `estab_score` < 0; `estab_kritik_richtung` genau dann, wenn zusätzlich `kriegspolitik` in `estab_gegenstand`.

## Versionierung

- 1.0-pilot: Fassung für den Pilot (150 Segmente, doppelt codiert).
- **1.0 (19.10.2026):** Änderungen gegenüber 1.0-pilot:
  - Grundregeln 9 (Satire/Ironie) und 10 (Gäste vs. Fremdrede) ergänzt.
  - `kodierbar`: Regel für überwiegend nicht-inhaltliche Segmente mit kurzen Einschüben.
  - `fremdrede_dominant`: Gäste im Gespräch zählen nicht; durchgehende Reden/Statements zählen.
  - Neues Feld `krieg_bezug` (explizit/implizit); `krieg_ukraine` auch bei implizitem Konfliktbezug (russische Energie, Nord Stream, Sanktionen).
  - Trading/Charttechnik → `unpolitisch`.
  - Neuer Kriegsaspekt `wirtschaft_inland`.
  - „Angriffskrieg“ allein ist keine Bewertung; Abgrenzung `west_score` +1/−1/−2.
  - Block F: Selbstdarstellung der Regierung = bewertend + `fremdrede`; Bezugsregel „Regierung/Staat“; Forderungen und Moderationsfragen allein deskriptiv; Neuwahlforderung ≠ Delegitimierung; Gäste bei `reg_urheber` = `fremdrede`.
- **1.1 (19.10.2026):** Block F von „Deutsche Bundesregierung“ zu „Politisches Establishment“ erweitert (Felder `reg_*` → `estab_*`): Ziele Bundesregierung, österreichische Regierung, etablierte Parteien, „die Politik“ allgemein, sonstige Institutionen; ausgenommen AfD, FPÖ, Linke, Medien, EU. Ein gemeinsamer Score. Neues Feld `estab_explizit` (explizit/implizit); implizite Kritik inkl. Kritik an konkreten Maßnahmen ohne genannten Akteur; bloßes Beklagen eines Zustands zählt nicht. Block G: `bundesregierung` → `establishment`.
- **1.2 (19.10.2026):** Gate-Regel gelockert: Segmente mit überwiegend nicht-inhaltlichem Material sind kodierbar, sobald sie mindestens eine inhaltliche Aussage mit Bewertung enthalten.
- **1.3 (19.10.2026):** `estab_ziel` auf zwei Werte vereinfacht: `bundesregierung` und `sonstiges_establishment` (fasst österreichische Regierung, etablierte Parteien, „die Politik“ allgemein und sonstige Institutionen zusammen). Abgrenzung des Establishments unverändert; Polizei und Gerichte ausdrücklich als Behörden genannt.
- Jede spätere Änderung erzeugt eine neue Version; betroffene Segmente werden neu codiert.

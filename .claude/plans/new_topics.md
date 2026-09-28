# Erweiterung der Themen-Relevanz-Klassifikation auf Corona, Migration, Wirtschaft, Energie

## Hinweis zur Zielgerichtetheit

Dieser Vorschlag ist keiner der heutigen Hauptpunkte aus `.claude/Aufgaben.md`
(dort geht es um Kriegs-/Populismusprämien-Berichte). Er ist aber methodisch
direkt an Forschungsfrage 4 angebunden ("Betrifft eine Erfolgsveränderung nur
Kriegsvideos oder auch andere Videos?"): Corona, Migration, Wirtschaft und
Energie dienen als Vergleichs-/Kontrollthemen, um zu prüfen, ob ein
beobachteter Populismus-/Erfolgstrend seit Kriegsbeginn spezifisch für
Kriegsvideos ist oder ein allgemeiner Trend über mehrere große politische
Themen. Umsetzung sollte trotzdem erst nach den heutigen Kernaufgaben
angegangen werden, falls Zeit knapp wird.

## Context

Bisher existiert nur für den Ukraine-Krieg (`topic = "russia_ukraine_war"`)
eine Keyword-basierte Themen-Relevanz-Klassifikation
(`src/youtube_code/step3_war_videos/`), die Titel/Beschreibung jedes Videos
per Regex gegen zwei Konfidenzstufen (`core`/`wide`) prüft und das Ergebnis in
`video_topic_relevance` (`data/store/video_registry.sqlite`) schreibt. Diese
Klassifikation soll auf vier weitere, breit gefasste Themenfelder erweitert
werden: **Corona/Pandemie**, **Migration**, **Wirtschaft (allgemein)** und
**Energie** (bewusst getrennt von Wirtschaft, da inhaltlich eng mit dem
Ukraine-Krieg verknüpft — Sanktionen, Gaspreise, Nord Stream — und daher als
eigenständiges Thema trennbar bleiben soll).

Getroffene Entscheidungen (bereits mit Nutzer abgestimmt):
- **Scope**: nur Relevanz-Screening pro Thema (wie beim Krieg), keine
  Positions-/Haltungskodierung für die neuen Themen in diesem Schritt.
- **Zuschnitt**: breite Themenfelder, keine engen Ereignisfenster.
- **Wirtschaft/Energie**: zwei getrennte Themen statt einem gemeinsamen.
- **Keywords**: komplett neu erarbeitet, nicht aus dem Archiv
  (`archive/new_analysis/feasibility.py`) übernommen.

Der Store (`video_topic_relevance`, `PRIMARY KEY (video_id, topic)`) ist
bereits vollständig multi-topic-fähig — **keine Schema-Änderung nötig**.

## 1. Code-Generalisierung

### `topic_keywords.py`

Jedes Thema bekommt einen kurzen `prefix` (damit die bestehenden
`ukr_core`/`ukr_wide`-Flags unverändert bleiben und keine Ukraine-Re-Klassifizierung
nötig wird) sowie eigene `core`/`wide`-Regexe:

```python
TOPIC_KEYWORDS = {
    "russia_ukraine_war": {"prefix": "ukr",       "core": _UKR_CORE,      "wide": _UKR_WIDE},
    "corona_pandemic":    {"prefix": "corona",    "core": _CORONA_CORE,  "wide": _CORONA_WIDE},
    "migration":          {"prefix": "migration", "core": _MIGRATION_CORE, "wide": _MIGRATION_WIDE},
    "economy_general":    {"prefix": "econ",      "core": _ECON_CORE,    "wide": _ECON_WIDE},
    "energy":             {"prefix": "energy",    "core": _ENERGY_CORE,  "wide": _ENERGY_WIDE},
}

KW_RE = {
    f"{cfg['prefix']}_{tier}": _compile(pattern)
    for cfg in TOPIC_KEYWORDS.values()
    for tier, pattern in cfg.items() if tier != "prefix"
}

# Pro Thema ein eigener Versionsstring statt einem globalen - erlaubt,
# einzelne Themen unabhaengig neu zu klassifizieren.
KEYWORD_SET_VERSION = {
    "russia_ukraine_war": "ukr_core_wide_v1_2026-09-01",
    "corona_pandemic":    "corona_core_wide_v1_2026-09-09",
    "migration":          "migration_core_wide_v1_2026-09-09",
    "economy_general":    "econ_core_wide_v1_2026-09-09",
    "energy":             "energy_core_wide_v1_2026-09-09",
}
```

`match_flags`, `is_relevant`, `is_relevant_vectorized` werden themenparametrisiert
(`match_flags(topic, title, desc_clean)` etc., iterieren generisch über die
Tiers eines Themas statt die zwei Flags `ukr_core`/`ukr_wide` hart zu
verdrahten; `is_relevant` wird zu `any(flags.values())`, was mathematisch
identisch zur bisherigen Logik ist). Diese Funktionen werden nur innerhalb von
`classify_topic_relevance.py` importiert — der Signaturwechsel ist damit
risikolos.

### `classify_topic_relevance.py`

`learn_boilerplate()` bleibt **einmalig** pro geladenem DataFrame (teuerster
Schritt, 634s bei 518k Videos laut README). `classify(df, boiler, topics)`
berechnet `desc_clean` weiterhin nur einmal pro Chunk, matcht diese
Beschreibung aber gegen **alle** übergebenen Themen (Default:
`TOPICS_TO_RUN = list(TOPIC_KEYWORDS.keys())`) und gibt ein langes DataFrame
(eine Zeile pro `video_id`×`topic`) zurück — das bestehende
Batch-Upsert-Schema in `main()` bleibt unverändert, da `upsert_topic_relevance()`
schon immer pro Record eine eigene `topic`-Spalte liest. Für Testläufe kann
`TOPICS_TO_RUN` auf ein einzelnes Thema eingeschränkt werden. Die
Statistik-Ausgabe in `main()` muss von den vier hartkodierten
`ukr_*`-Flag-Namen auf einen dynamischen Loop über
`result.groupby("topic")` umgestellt werden.

## 2. Modul umbenennen

`src/youtube_code/step3_war_videos/` → `step3_topic_relevance/` (per `git mv`).
Grep-Check ergab: außerhalb des Moduls selbst importiert kein Code
`step3_war_videos` — alle anderen Fundstellen sind Doku/Kommentare. Rename ist
damit risikoarm und macht den Namen korrekt, sobald fünf statt einem Thema
klassifiziert werden. Betrifft (Import-Pfade + Doku, gemäß CLAUDE.md-Regel zu
README/Docstring-Pflege):
- die zwei Self-Imports in `classify_topic_relevance.py`
- `step3_topic_relevance/README.md` (Titel, Ausführungskommando, Abschnitt
  "Weiteres Thema ergänzen" durch die tatsächliche `prefix`/`TOPICS_TO_RUN`-Struktur
  ersetzen)
- `COMPLETE_PROCESS.md` Abschnitt 3, Root-`README.md` (Pfadreferenzen,
  "Standard-Topic ist russia_ukraine_war"-Formulierung)
- Kommentare in `video_registry.py`, `step6_auswertung/frage1_stichprobe.py`,
  `step7_comments/select_targets.py`

## 3. Keyword-Vorschläge (core/wide, `re.IGNORECASE | re.VERBOSE`)

Bewusst **keine** hochgradig polysemen Einzelwörter bare (`Grenze`, `Preis`,
`Gas`, `Strom`, `Integration`) — nur Komposita/Fachbegriffe, um
Fehlklassifikation durch Alltagssprache zu vermeiden. Politiker-Nachnamen
bewusst nicht aufgenommen (anders als bei Ukraine/Selenskyj/Putin), da diese
breitere Portfolios haben und die Themenabgrenzung verwischen würden.

**Corona/Pandemie:**
```python
_CORONA_CORE = r"""
    corona[- ]?virus | covid[-]?19 | \bcovid\b | sars[- ]?cov[- ]?2
    | pandemie\w* | impfpflicht | \blockdown\b | quarantäne
    | inzidenzwert | inzidenzzahl | maskenpflicht
    | querdenker\w* | coronaleugner | impfzwang | impfdurchbruch
    | boosterimpfung | corona[- ]?maßnahmen
"""
_CORONA_WIDE = r"""
    \bcorona\b | geimpft | ungeimpft | impfstoff\w* | impfquote
    | \brki\b | drosten | omikron | delta[- ]?variante
    | \b[23]g[- ]?regel | genesenenstatus | hygienekonzept
    | aerosole | schutzmaske\w* | corona[- ]?ausschuss
"""
```
FP-Risiko: `corona` bare (Bier, Sonnenkorona, Automodell) nur in wide, nicht
core; `impfstoff`/`geimpft`/`rki` können sich ab 2023 auf andere Impfungen/
Krankheiten beziehen (akzeptierter Recall/Precision-Trade-off im wide-Tier).

**Migration:**
```python
_MIGRATION_CORE = r"""
    asylbewerber\w* | asylrecht | asylverfahren | \basyl\b
    | flüchtling\w* | geflüchtete\w* | migrant\w* | migrations\w*
    | zuwanderung\w* | einwanderung\w* | abschieb\w* | ausweisung\w*
    | schutzsuchend\w* | bleiberecht | duldung
    | remigration | fachkräfteeinwanderung
"""
_MIGRATION_WIDE = r"""
    grenzkontrolle\w* | grenzsicherung | grenzschutz | grenzzaun\w*
    | grenzschließung\w* | grenzübertritt\w*
    | abschottung | pull[- ]?faktor | migrationspakt | migrationsabkommen
    | familiennachzug | resettlement | seenotrettung
    | balkanroute | mittelmeerroute | ankerzentrum | aufnahmezentrum
    | integrationsgesetz | integrationskurs | überfremdung | islamisierung
    | sichere\s+drittstaaten
"""
```
FP-Risiko: `Grenze`/`Integration` bare bewusst ausgeschlossen (Überlappung mit
Ukraine-Russland-Grenze/NATO-Ostgrenze bzw. generischer Alltagsbegriff) — nur
Komposita.

**Wirtschaft (allgemein):**
```python
_ECON_CORE = r"""
    wirtschaft(?:spolitik|swachstum|skrise|slage|sstandort)?
    | rezession\w* | konjunktur\w* | inflation\w* | \bbip\b
    | bruttoinlandsprodukt | wirtschaftswachstum | wirtschaftskrise
    | arbeitslosigkeit | arbeitsmarkt\w* | staatsverschuldung
    | schuldenbremse | haushaltsdefizit | haushaltsloch
    | deindustrialisierung | fachkräftemangel | bürgergeld
    | mindestlohn | leitzins\w* | ezb[- ]?leitzins
"""
_ECON_WIDE = r"""
    verbraucherpreis\w* | preissteigerung\w* | preisexplosion
    | kaufkraft\w* | lohnerhöhung\w* | tarifverhandlung\w*
    | gewerkschaft\w* | \bstreik\w* | exportüberschuss | exportweltmeister
    | insolvenzwelle | unternehmenspleite\w* | wachstumsschwäche
    | standortnachteil | ifo[- ]?institut | ifo[- ]?index | \bdax\b
    | rentenreform | sozialstaat | hartz[- ]?iv | zinserhöhung\w* | zinswende
"""
```
FP-Risiko: `Preis`/`Industrie`/`Rente` bare bewusst ausgeschlossen. Bewusste
Überschneidung mit Energie über `verbraucherpreis\w*` (wide) — energie-
spezifische Preisbegriffe (`energiepreis`, `gaspreis`, `strompreis`) liegen
primär im Energie-Core, damit ein Video wirtschaft-only, energie-only oder
beides sein kann (Trennbarkeit prüfbar, nicht erzwungen).

**Energie:**
```python
_ENERGY_CORE = r"""
    energiepreis\w* | energiekrise\w* | energiewende | energiesicherheit
    | gaspreis\w* | gasspeicher\w* | gasmangel | gasknappheit
    | gasumlage | gasversorgung | gasimport\w* | gasembargo
    | gaslieferung\w* | gasleitung\w* | nord[- ]?stream
    | lng[- ]?terminal\w* | strompreis\w* | stromkrise | stromausfall\w*
    | energiepreisbremse | energiepreisdeckel | heizungsgesetz
"""
_ENERGY_WIDE = r"""
    atomkraft\w* | atomausstieg | kernkraft\w* | kernenergie | \bakw\b
    | kohlekraft\w* | kohleausstieg | braunkohle
    | erneuerbare\s+energien | windkraft | windenergie | windrad\w*
    | solarenergie | photovoltaik | ölpreis\w* | ölembargo | ölimport\w*
    | fracking | energiekonzern\w* | netzausbau | dunkelflaute
    | versorgungssicherheit | energiearmut | flüssiggas | gaspipeline\w*
"""
```
FP-Risiko: `Gas`/`Strom` bare bewusst ausgeschlossen (Gaspedal/Lachgas bzw.
"im Strom der Zeit"). Überschneidung mit `russia_ukraine_war` (Nord Stream,
Gasembargo) ist **gewollt** — genau das erlaubt später zu prüfen, ob Effekte
kriegsnah über Energie oder allgemein wirtschaftlich laufen (Forschungsfrage 4).

## 4. Rollout/Verifikation (gestuft, Genehmigungspflicht beachten)

1. **Ohne DB-Zugriff**: Patterns gegen eine kleine handkuratierte Liste von
   Beispieltiteln/-beschreibungen testen (kein `learn_boilerplate()`, keine
   Genehmigung nötig).
2. **Kleine Stichprobe, `DRY_RUN=True`**: `TOPICS_TO_RUN` auf ein neues Thema
   beschränken, `CHANNEL_FILTER` auf ~20–30 Kanäle verschiedener Medientypen
   reduzieren.
3. Flag-Statistik prüfen (core/wide-, title/desc-Verhältnis, Gesamtanteil
   `is_relevant`).
4. Manuelle Spot-Checks: je Thema ~20 relevant markierte Videos (core- und
   nur-wide-Treffer gemischt) + ~10 knapp nicht-getroffene, gezielt auf die
   oben benannten FP-Risiken prüfen.
5. Overlap-Matrix zwischen Themen prüfen (v. a. `energy` ∩
   `russia_ukraine_war`, `energy` ∩ `economy_general`) — hohe, aber nicht
   totale Überschneidung erwartet; nahezu vollständige Übersättigung eines
   Themas wäre ein Hinweis, das wide-Set zu verschärfen.
6. **Vor dem Volldatensatz-Lauf (alle Kanäle, alle Themen, weiterhin
   `DRY_RUN=True`) explizit Genehmigung einholen** — analog zur bestehenden
   Projektregel für länger laufende/speicherintensive Skripte
   (`learn_boilerplate()` allein dauerte zuletzt 634s bei 518k Videos).
7. Erst nach positivem Ergebnis `DRY_RUN=False` setzen und schreiben.

## 5. Explizit außerhalb dieses Schritts (Folgearbeit)

- `video_registry.get_topic_relevance()`: Default-Parameter
  `topic="russia_ukraine_war"` generalisieren/zu Pflichtparameter machen.
- `step4_transcript_download/select_targets.py`,
  `run_transcript_selection.py`, `step6_auswertung/prepare_success_metrics.py`,
  `select_political_nonwar_targets.py`, `step7_comments/select_targets.py`:
  eigene `TOPIC`-Konstanten/Defaults, müssten für eine tatsächliche
  Vergleichsthemen-Auswertung (Forschungsfrage 4) später parametrisiert werden.
- `frage1_stichprobe.py` liest aus einem Ukraine-spezifischen CSV-Snapshot
  (`scripts/adhoc/output/topic_vids_per_channel.csv`) — müsste für neue
  Themen re-exportiert/generalisiert werden.
- Keine Positions-/Haltungskodierung für die neuen Themen (Scope-Entscheidung).

## Verifikation

- `PYTHONPATH=src python -c "from youtube_code.step3_topic_relevance import topic_keywords; print(list(topic_keywords.TOPIC_KEYWORDS))"`
  — prüft, dass alle fünf Themen geladen werden.
- Schritt 1 des Rollouts (Beispieltitel/-beschreibungen) manuell durchgehen.
- Nach Stufe 2–5 (kleine Stichprobe, `DRY_RUN=True`): Flag-Statistik und
  Overlap-Matrix wie oben beschrieben sichten, bevor der Volldatensatz-Lauf
  angefragt wird.
- Nach dem eigentlichen Schreiblauf:
  `PYTHONPATH=src python -c "from youtube_code.store import video_registry; print(video_registry.topic_relevance_count())"`
  und Vergleich mit der vorherigen Zeilenzahl (nur Ukraine) zur Plausibilisierung.

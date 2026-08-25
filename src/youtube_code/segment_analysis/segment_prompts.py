"""
Prompts fuer die Segment-Klassifikation.

Prompttext, responseSchema und Validierungsregeln stehen pro Prompt in
einem Bundle. Das ist Absicht: Die Reihenfolge in propertyOrdering ist
die Reihenfolge, in der das Modell generiert. Extract-then-judge
funktioniert nur, wenn die Belegfelder VOR den Score-Feldern stehen.
Waeren Prompt und Schema getrennt gepflegt, koennte das unbemerkt
auseinanderlaufen.

Der Segmenttext wird NICHT per .format() eingesetzt, sondern angehaengt
(die Prompts enthalten geschweifte Klammern im JSON-Beispiel).
"""

from __future__ import annotations

# ============================================================
# ERLAUBTE WERTE
# ============================================================

STATUS_VALUES = ["nicht_thematisiert", "deskriptiv", "kodiert"]

INSTRUMENT_VALUES = [
    "waffenlieferungen",
    "sanktionen",
    "finanzhilfe",
    "verhandlungen_diplomatie",
    "nato_eu_beitritt",
    "gefluechtete",
    "energie",
    "truppen_einsatz",
]

EMO_ZIEL_VALUES = [
    "russland_fuehrung",
    "westliche_regierungen",
    "eigene_regierung",
    "ukraine_fuehrung",
    "zivilbevoelkerung",
    "medien",
    "unklar",
]

REDEFORM_VALUES = ["monolog", "gespraech", "beitrag", "unklar"]


# ============================================================
# PROMPT: POSITION_V1
# ============================================================

POSITION_V1_TEXT = """Du bist ein Kodierer in einem sozialwissenschaftlichen Forschungsprojekt. Du kodierst ein Segment aus dem Transkript eines deutschsprachigen YouTube-Videos.

ARBEITSWEISE
Du arbeitest in jeder Dimension in zwei Schritten: Zuerst extrahierst du woertliche Belegstellen aus dem Segment. Erst danach faellst du das Urteil, und zwar ausschliesslich auf Basis der von dir extrahierten Stellen. Faelle niemals ein Urteil, fuer das du keine Belegstelle extrahiert hast.

GRUNDREGELN
1. Kodiere ausschliesslich auf Basis des vorliegenden Segmenttexts. Ergaenze kein Weltwissen ueber den Kanal, den Sprecher oder den weiteren Videokontext.
2. Zitierte oder eingespielte Fremdrede (O-Toene, Zitate, Interviewpassagen) zaehlt zur Kodierung dazu. Die Auswahl zitierter Rede wird als redaktionelle Entscheidung des Kanals gewertet. Ob Fremdrede dominiert, wird separat erfasst.
3. Kodiere, was gesagt wird, nicht, ob es zutrifft. Bewerte keine Faktizitaet.
4. Belegstellen muessen woertlich und ununterbrochen aus dem Segment stammen. Kuerze oder paraphrasiere nicht. Wenn du keine passende Stelle findest, gib eine leere Liste aus.
5. Bei Unentscheidbarkeit waehle die konservativere (naeher an 0 liegende) Auspraegung.

--------------------------------------------------------------------
DIMENSION 1 - POSITION GEGENUEBER RUSSLAND

Schritt 1a - rus_erwaehnt (true/false):
  Kommen Russland, die russische Fuehrung oder russisches Handeln im Segment ueberhaupt vor?

Schritt 1b - rus_belege (Liste, max. 3 Eintraege a max. 20 Woerter):
  Extrahiere woertliche Passagen, in denen russisches Handeln bewertet, gerechtfertigt, relativiert, verurteilt oder in denen Verantwortung fuer den Krieg zugeschrieben wird. Reine Ereignis- oder Faktenwiedergabe ist KEINE Belegstelle. Findest du keine solche Passage, gib eine leere Liste aus.

Schritt 1c - rus_status (mechanisch abzuleiten):
  rus_erwaehnt = false                  -> "nicht_thematisiert"
  rus_erwaehnt = true, rus_belege leer  -> "deskriptiv"
  rus_belege nicht leer                 -> "kodiert"

Schritt 1d - rus_score (nur bei rus_status = "kodiert", sonst null):
  Beurteile ausschliesslich die in rus_belege extrahierten Passagen.
 +2 = Russisches Handeln wird gerechtfertigt oder als legitim/notwendig dargestellt; die Hauptverantwortung fuer den Krieg wird der Ukraine, der NATO oder dem Westen zugeschrieben.
 +1 = Russisches Handeln wird relativiert, erklaert oder entlastet (z. B. Verweis auf Provokation, Sicherheitsinteressen, doppelte Standards), ohne es voll zu legitimieren; oder Verantwortung wird deutlich geteilt zugeschrieben.
  0 = Bewertende Elemente vorhanden, aber gegenlaeufig oder ausgewogen; keine Richtung ueberwiegt.
 -1 = Russisches Handeln wird kritisiert oder Russland wird Verantwortung zugeschrieben, ohne starke Zuspitzung.
 -2 = Russisches Handeln wird als illegitim, aggressiv, verbrecherisch dargestellt; klare Alleinverantwortung Russlands; ggf. Delegitimierung der russischen Fuehrung.

--------------------------------------------------------------------
DIMENSION 2 - POSITION GEGENUEBER DER WESTLICHEN UKRAINE-POLITIK

Gehe fuer diese Dimension erneut an den Segmenttext. Das Urteil aus Dimension 1 ist fuer Dimension 2 ohne Bedeutung.

Gegenstand ist die Politik westlicher Akteure (Bundesregierung, EU, NATO, USA) gegenueber dem Krieg - nicht die Ukraine als Land und nicht westliche Politik im Allgemeinen.

Schritt 2a - west_erwaehnt (true/false):
  Kommt westliche Ukraine-Politik im Segment ueberhaupt vor?

Schritt 2b - west_belege (Liste, max. 3 Eintraege a max. 20 Woerter):
  Extrahiere woertliche Passagen, in denen diese Politik befuerwortet, gefordert, kritisiert oder abgelehnt wird. Berichte ueber Beschluesse oder Massnahmen ohne erkennbare Wertung sind KEINE Belegstellen.

Schritt 2c - west_status (mechanisch abzuleiten, analog zu 1c).

Schritt 2d - west_score (nur bei west_status = "kodiert", sonst null):
  Beurteile ausschliesslich die in west_belege extrahierten Passagen.
 +2 = Deutliche Unterstuetzung; Forderung nach mehr/staerkerem Engagement; westliche Politik erscheint als richtig und geboten.
 +1 = Ueberwiegende Zustimmung mit Einschraenkungen, oder Unterstuetzung des Ziels bei Kritik an der Umsetzung (zu langsam, zu zoegerlich).
  0 = Zustimmende und ablehnende Elemente halten sich die Waage.
 -1 = Ueberwiegende Kritik: Zweifel an Wirksamkeit, Kosten, Eskalationsrisiko; Ruf nach Zurueckhaltung oder Verhandlungen statt Unterstuetzung.
 -2 = Grundsaetzliche Ablehnung; westliche Politik erscheint als falsch, schaedlich, eskalierend oder fremdgesteuert; Forderung nach Beendigung der Unterstuetzung.

HINWEIS: Die beiden Dimensionen sind unabhaengig. Scharfe Russlandkritik bei gleichzeitiger Ablehnung westlicher Unterstuetzungspolitik ist eine regulaere, kohaerente Position und keine Inkonsistenz. Ebenso ist Zustimmung zur westlichen Politik ohne jede Russlandbewertung moeglich. Pruefe die Kombination deiner beiden Urteile nicht auf Stimmigkeit.

--------------------------------------------------------------------
INSTRUMENTE (instrumente)
Liste aller im Segment inhaltlich angesprochenen Politikinstrumente, unabhaengig von der Bewertung. Leere Liste, wenn keines vorkommt. Zulaessige Werte: "waffenlieferungen", "sanktionen", "finanzhilfe", "verhandlungen_diplomatie", "nato_eu_beitritt", "gefluechtete", "energie", "truppen_einsatz"

--------------------------------------------------------------------
DIMENSION 3 - EMOTIONALE INTENSITAET

Erfasst die Emotionalisierung der Kriegsthematik, unabhaengig von deren Richtung.

Schritt 3a - emo_belege (Liste, max. 3 Eintraege a max. 20 Woerter):
  Extrahiere woertliche Passagen mit affektiv aufgeladener Sprache: Wertungen, Dramatisierung, moralische Erregung, Angst- oder Empoerungsappelle, Kriegs- oder Katastrophenrhetorik. Leere Liste bei durchgehend sachlichem Duktus.

Schritt 3b - emo_intensitaet (0-3):
  Beurteile Dichte und Schaerfe der extrahierten Passagen im Verhaeltnis zum Gesamtsegment.
  0 = emo_belege ist leer; sachlich-berichtender oder analytischer Duktus.
  1 = Vereinzelte affektive Ausdruecke, insgesamt sachlicher Ton.
  2 = Durchgehend wertungsstarke Sprache; deutliche Affektmarkierung, aber ohne dramatisierende Ueberhoehung.
  3 = Stark emotionalisiert; Dramatisierung und moralische Erregung tragen das Segment.

Schritt 3c - emo_ziel (Liste; leer bei emo_intensitaet = 0):
  Objekte, auf die sich die affektive Aufladung richtet. Zulaessige Werte: "russland_fuehrung", "westliche_regierungen", "eigene_regierung", "ukraine_fuehrung", "zivilbevoelkerung", "medien", "unklar"

--------------------------------------------------------------------
FORMALE MERKMALE
redeform: "monolog" | "gespraech" | "beitrag" | "unklar"
fremdrede_dominant: true, wenn der ueberwiegende Teil des Segments aus zitierter oder eingespielter Fremdrede besteht, sonst false.

--------------------------------------------------------------------
AUSGABEFORMAT
Antworte ausschliesslich mit einem JSON-Objekt in exakt dieser Feldreihenfolge, ohne Vorrede und ohne Markdown."""


POSITION_V1_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "rus_erwaehnt": {"type": "BOOLEAN"},
        "rus_belege": {
            "type": "ARRAY",
            "maxItems": 3,
            "items": {"type": "STRING"},
        },
        "rus_status": {"type": "STRING", "enum": STATUS_VALUES},
        "rus_score": {"type": "INTEGER", "nullable": True},
        "west_erwaehnt": {"type": "BOOLEAN"},
        "west_belege": {
            "type": "ARRAY",
            "maxItems": 3,
            "items": {"type": "STRING"},
        },
        "west_status": {"type": "STRING", "enum": STATUS_VALUES},
        "west_score": {"type": "INTEGER", "nullable": True},
        "instrumente": {
            "type": "ARRAY",
            "items": {"type": "STRING", "enum": INSTRUMENT_VALUES},
        },
        "emo_belege": {
            "type": "ARRAY",
            "maxItems": 3,
            "items": {"type": "STRING"},
        },
        "emo_intensitaet": {"type": "INTEGER"},
        "emo_ziel": {
            "type": "ARRAY",
            "items": {"type": "STRING", "enum": EMO_ZIEL_VALUES},
        },
        "redeform": {"type": "STRING", "enum": REDEFORM_VALUES},
        "fremdrede_dominant": {"type": "BOOLEAN"},
    },
    # Diese Reihenfolge ist die Generierungsreihenfolge des Modells.
    # Belege stehen vor den Scores. Nicht umsortieren.
    "propertyOrdering": [
        "rus_erwaehnt",
        "rus_belege",
        "rus_status",
        "rus_score",
        "west_erwaehnt",
        "west_belege",
        "west_status",
        "west_score",
        "instrumente",
        "emo_belege",
        "emo_intensitaet",
        "emo_ziel",
        "redeform",
        "fremdrede_dominant",
    ],
    "required": [
        "rus_erwaehnt",
        "rus_belege",
        "rus_status",
        "rus_score",
        "west_erwaehnt",
        "west_belege",
        "west_status",
        "west_score",
        "instrumente",
        "emo_belege",
        "emo_intensitaet",
        "emo_ziel",
        "redeform",
        "fremdrede_dominant",
    ],
}


# ============================================================
# PROMPT: POPULISMUS_P (Segmentebene, vier Dimensionen)
# ============================================================

POPULISM_P_TEXT = """Du kodierst deutschsprachige politische Videotranskripte fuer die sozialwissenschaftliche Forschung. Du arbeitest mit automatisch erzeugten Transkripten: Eigennamen sind haeufig falsch geschrieben, Satzzeichen fehlen oder sitzen falsch, einzelne Woerter sind verschluckt. Erschliesse die Bedeutung aus dem Zusammenhang.

Die Transkripte enthalten oft mehrere Sprechende (Moderation, Gaeste) ohne Kennzeichnung. Kodiere das Segment als Ganzes, so wie es der Kanal veroeffentlicht hat - unabhaengig davon, wer spricht.

Du bewertest die Form der Kommunikation, nicht ihren Wahrheitsgehalt und nicht ihre politische Richtung. Linke und rechte Inhalte werden nach exakt denselben Kriterien bewertet. Deine eigene Haltung zu den Aussagen ist irrelevant.

Bewerte das Segment auf vier unabhaengigen Dimensionen. Die Dimensionen werden getrennt bewertet; eine hohe Bewertung auf einer Dimension erzwingt keine hohe Bewertung auf einer anderen.

### 1. volkszentrismus

Beruft sich der Text auf "das Volk", "die Buerger", "die Menschen", "die Mehrheit" als eine EINHEITLICHE Groesse mit einem gemeinsamen Willen, und stellt sich der Sprecher als deren Stimme dar?

0  Keine Berufung auf ein kollektives Volk, oder nur als sachliche Bevoelkerungsangabe ("40 Prozent der Befragten").
1  Vereinzelte Berufung auf "die Buerger" oder "die Menschen", ohne dass ihnen ein einheitlicher Wille zugeschrieben wird.
2  Dem Volk wird wiederholt ein gemeinsamer Wille oder gesunder Menschenverstand zugeschrieben, dem etwas entgegensteht.
3  Der Sprecher tritt ausdruecklich als Stimme des Volkes auf; der Volkswille ist eindeutig, einheitlich und wird missachtet.

Abgrenzung: Die Nennung einer konkreten Gruppe (Rentner, Landwirte, Ostdeutsche) ist NICHT Volkszentrismus, solange sie nicht mit dem Ganzen gleichgesetzt wird.

### 2. antielitismus

Werden Eliten ALS GRUPPE angegriffen - als eigennuetzig, abgehoben, verlogen oder gegen die Bevoelkerung handelnd? Eliten koennen Politik, Medien, Wissenschaft, Justiz, EU, Konzerne oder NGOs sein.

0  Keine Elitenkritik, oder ausschliesslich sachliche Kritik an einer konkreten Entscheidung oder Person.
1  Kritik an einzelnen Akteuren mit abwertendem Unterton, aber ohne Verallgemeinerung auf eine Klasse.
2  Eliten werden als Gruppe kritisiert, der ein gemeinsames Eigeninteresse oder eine gemeinsame Abgehobenheit unterstellt wird.
3  Eliten erscheinen als geschlossenes System, das bewusst gegen die Bevoelkerung arbeitet, taeuscht oder ein Kartell bildet.

Abgrenzung: "Die Regierung hat bei der Rente falsch entschieden" ist 0. "Die da oben interessiert nicht, was mit uns passiert" ist 2 bis 3. Entscheidend ist die Unterstellung eines gemeinsamen Motivs, nicht die Schaerfe des Tons.

### 3. manichaeische_moralisierung

Wird der Konflikt als moralische Zweiteilung dargestellt - eine Seite gut, die andere boese - ohne legitime Zwischenpositionen?

0  Positionen werden als sachlich verschieden dargestellt; Gegenargumente erscheinen als vertretbar.
1  Eine Seite wird deutlich bevorzugt, die andere aber nicht moralisch disqualifiziert.
2  Die Gegenseite wird ueberwiegend moralisch statt sachlich diskreditiert; Zwischenpositionen kommen kaum vor.
3  Vollstaendige moralische Zweiteilung: Gut gegen Boese, Wahrheit gegen Luege, keine legitime abweichende Position denkbar.

Abgrenzung: Die Verurteilung eines Kriegsverbrechens oder eines Terroranschlags ist fuer sich genommen KEINE manichaeische Moralisierung. Entscheidend ist, ob politische MEINUNGSVERSCHIEDENHEITEN moralisiert werden.

### 4. emotionale_intensitaet

Wie stark ist die affektive Aufladung - Empoerung, Angst, Dramatisierung, Pathos? Diese Dimension misst NICHT Populismus, sondern dient als Kontrollgroesse.

0  Nuechtern, berichtend, analytisch.
1  Erkennbare Anteilnahme oder Zuspitzung, insgesamt sachlich.
2  Deutlich emotionalisiert: Empoerung, Dringlichkeit, drastische Bilder.
3  Durchgehend hochemotional: Alarm, Untergang, Existenzbedrohung, Pathos.

--------------------------------------------------------------------

Fuer jede Dimension gilt:

- belege ZUERST mit einem woertlichen Zitat aus dem Segment (5 bis 25 Woerter), das die Bewertung traegt. Das Zitat muss exakt so im Segment stehen.
- Gibt es keinen Beleg, ist die Bewertung 0 und der Beleg null.
- Bewerte danach.
- Beziehe dich NUR auf das zu kodierende Segment. Ein Kontextblock (falls vorhanden) dient dem Verstaendnis und wird nicht mitbewertet.

Enthaelt das Segment keinen politischen Inhalt (Werbung, Intro, Verabschiedung, Small Talk), setze "kodierbar": false und alle vier Werte sowie alle vier Belege auf null.

Antworte ausschliesslich mit einem JSON-Objekt in exakt dieser Feldreihenfolge, ohne Vorrede und ohne Markdown."""


_DIMENSION_OBJECT_0_3 = {
    "type": "OBJECT",
    "properties": {
        "beleg": {"type": "STRING", "nullable": True},
        "wert": {"type": "INTEGER", "nullable": True},
    },
    "propertyOrdering": ["beleg", "wert"],
    "required": ["beleg", "wert"],
}

POPULISM_P_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "kodierbar": {"type": "BOOLEAN"},
        "volkszentrismus": _DIMENSION_OBJECT_0_3,
        "antielitismus": _DIMENSION_OBJECT_0_3,
        "manichaeische_moralisierung": _DIMENSION_OBJECT_0_3,
        "emotionale_intensitaet": _DIMENSION_OBJECT_0_3,
        "ukraine_bezug": {"type": "BOOLEAN"},
    },
    # kodierbar zuerst (Gate), ukraine_bezug bewusst zuletzt: ein frueh
    # gesetztes Themenlabel koennte sonst die Dimensionsurteile anziehen.
    "propertyOrdering": [
        "kodierbar",
        "volkszentrismus",
        "antielitismus",
        "manichaeische_moralisierung",
        "emotionale_intensitaet",
        "ukraine_bezug",
    ],
    "required": [
        "kodierbar",
        "volkszentrismus",
        "antielitismus",
        "manichaeische_moralisierung",
        "emotionale_intensitaet",
        "ukraine_bezug",
    ],
}


# ============================================================
# PROMPT: IDEOLOGIE_I (Baseline, Kanalpositionierung)
# ============================================================
#
# Im urspruenglichen Design fuer GANZE Transkripte konzipiert, nicht fuer
# Segmente. Ob dieses Bundle ueber die Segment-Pipeline oder ueber die
# bestehende Transkript-Pipeline (run_transcript_classification_batch.py)
# angebunden wird, ist noch offen. Text und Schema sind pipeline-
# unabhaengig nutzbar; hier nur definiert, noch nicht verdrahtet.

IDEOLOGY_I_TEXT = """Du verortest deutschsprachige politische Videotranskripte auf ideologischen Dimensionen, fuer die sozialwissenschaftliche Forschung. Du arbeitest mit automatisch erzeugten Transkripten mit Erkennungsfehlern.

Du verortest die im Text vertretenen POSITIONEN, nicht die Person und nicht den Kanal. Du bewertest nicht, ob eine Position richtig ist.

Verorte die im Transkript vertretenen Positionen auf drei Dimensionen. Skala jeweils -3 bis +3. Ist eine Dimension nicht erkennbar, setze null - rate nicht.

### wirtschaft
-3  Starke Umverteilung, Verstaatlichung, Ausbau des Sozialstaats, Kapitalismuskritik
 0  Ausgewogen oder gemischt
+3  Marktliberal, Steuersenkung, Deregulierung, Sozialstaatskritik

### gesellschaft
-3  Progressiv: Vielfalt, Minderheitenrechte, Klimaschutz vor Wachstum, offene Migrationspolitik
 0  Ausgewogen oder gemischt
+3  Konservativ bis national: Tradition, Leitkultur, restriktive Migrationspolitik, Kritik an Klima- und Genderpolitik

### aussen_sicherheit
-3  Multilateral, EU- und NATO-freundlich, Buendnistreue
 0  Ausgewogen oder gemischt
+3  Souveraenistisch, EU- und NATO-kritisch, nationale Eigenstaendigkeit

Fuer jede Dimension: zuerst ein woertliches Belegzitat (5 bis 25 Woerter), dann der Wert. Ohne Beleg ist der Wert null.

Zusaetzlich: "positionen_gegen_kanal" auf true setzen, wenn im Transkript ueberwiegend Positionen REFERIERT oder kritisiert werden, die der Sprecher selbst nicht teilt (z. B. Nachrichtenformat, Faktencheck, Gegnerzitate). In diesem Fall sind die Werte unzuverlaessig und das Video wird in der Aggregation gewichtet ausgeschlossen.

Antworte ausschliesslich mit einem JSON-Objekt in exakt dieser Feldreihenfolge, ohne Vorrede und ohne Markdown."""


_DIMENSION_OBJECT_M3_3 = {
    "type": "OBJECT",
    "properties": {
        "beleg": {"type": "STRING", "nullable": True},
        "wert": {"type": "INTEGER", "nullable": True},
    },
    "propertyOrdering": ["beleg", "wert"],
    "required": ["beleg", "wert"],
}

IDEOLOGY_I_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "wirtschaft": _DIMENSION_OBJECT_M3_3,
        "gesellschaft": _DIMENSION_OBJECT_M3_3,
        "aussen_sicherheit": _DIMENSION_OBJECT_M3_3,
        "positionen_gegen_kanal": {"type": "BOOLEAN"},
    },
    "propertyOrdering": [
        "wirtschaft",
        "gesellschaft",
        "aussen_sicherheit",
        "positionen_gegen_kanal",
    ],
    "required": [
        "wirtschaft",
        "gesellschaft",
        "aussen_sicherheit",
        "positionen_gegen_kanal",
    ],
}


# ============================================================
# BUNDLES
# ============================================================
#
# Zwei Bundle-"kind"s:
#
#   "flat_status"      status_rules leiten status aus (erwaehnt, belege)
#                       ab, score genau dann gesetzt, wenn status ==
#                       "kodiert". Siehe POSITION_V1.
#
#   "nested_dimension"  jede Dimension ist ein Objekt {beleg, wert}.
#                       null_convention="zero": ohne Beleg ist wert 0
#                       (P). null_convention="null": ohne Beleg ist wert
#                       null (I). gate_field: optionales Top-Level-Feld,
#                       das bei gate_open_value=False alle Dimensionen
#                       auf (beleg=null, wert=null) zwingt (P:
#                       "kodierbar"). trailing_fields muessen als letzte
#                       Felder in propertyOrdering stehen.

SEGMENT_PROMPTS = {
    "POSITION_V1": {
        "kind": "flat_status",
        "text": POSITION_V1_TEXT,
        "schema": POSITION_V1_SCHEMA,
        "target_variable": "position_russia_west",
        "status_rules": [
            ("rus_erwaehnt", "rus_belege", "rus_status", "rus_score"),
            ("west_erwaehnt", "west_belege", "west_status", "west_score"),
        ],
        "score_ranges": {
            "rus_score": (-2, 2),
            "west_score": (-2, 2),
            "emo_intensitaet": (0, 3),
        },
        "evidence_fields": ["rus_belege", "west_belege", "emo_belege"],
        "enum_fields": {
            "rus_status": STATUS_VALUES,
            "west_status": STATUS_VALUES,
            "instrumente": INSTRUMENT_VALUES,
            "emo_ziel": EMO_ZIEL_VALUES,
            "redeform": REDEFORM_VALUES,
        },
    },
    "POPULISMUS_P": {
        "kind": "nested_dimension",
        "text": POPULISM_P_TEXT,
        "schema": POPULISM_P_SCHEMA,
        "target_variable": "populism_segment",
        "segment_label": "ZU KODIERENDES SEGMENT",
        "use_context": True,
        "dimensions": [
            "volkszentrismus",
            "antielitismus",
            "manichaeische_moralisierung",
            "emotionale_intensitaet",
        ],
        "wert_range": (0, 3),
        "gate_field": "kodierbar",
        "gate_open_value": True,
        "null_convention": "zero",
        "trailing_fields": {"ukraine_bezug": "bool"},
    },
    "IDEOLOGIE_I": {
        "kind": "nested_dimension",
        "text": IDEOLOGY_I_TEXT,
        "schema": IDEOLOGY_I_SCHEMA,
        "target_variable": "ideology_baseline",
        "segment_label": "TRANSKRIPT",
        "use_context": False,
        "dimensions": ["wirtschaft", "gesellschaft", "aussen_sicherheit"],
        "wert_range": (-3, 3),
        "gate_field": None,
        "null_convention": "null",
        "trailing_fields": {"positionen_gegen_kanal": "bool"},
    },
}


def get_bundle(prompt_key: str) -> dict:
    if prompt_key not in SEGMENT_PROMPTS:
        raise KeyError(
            f"Unbekannter Prompt '{prompt_key}'. "
            f"Verfuegbar: {sorted(SEGMENT_PROMPTS)}"
        )
    bundle = SEGMENT_PROMPTS[prompt_key]
    kind = bundle.get("kind", "flat_status")

    ordering = bundle["schema"]["propertyOrdering"]
    properties = set(bundle["schema"]["properties"])
    if set(ordering) != properties:
        raise ValueError(
            f"{prompt_key}: propertyOrdering und properties stimmen nicht "
            "ueberein."
        )

    if kind == "flat_status":
        for field in bundle["evidence_fields"]:
            if field not in properties:
                raise ValueError(f"{prompt_key}: evidence_field {field!r} fehlt im Schema.")
        for _, belege, status, score in bundle["status_rules"]:
            for field in (belege, status, score):
                if field not in properties:
                    raise ValueError(f"{prompt_key}: status_rule-Feld {field!r} fehlt im Schema.")
            if ordering.index(belege) > ordering.index(score):
                raise ValueError(
                    f"{prompt_key}: {belege!r} steht in propertyOrdering hinter "
                    f"{score!r}. Extract-then-judge waere ausgehebelt."
                )

    elif kind == "nested_dimension":
        dims = bundle["dimensions"]
        gate_field = bundle.get("gate_field")
        trailing = list(bundle.get("trailing_fields", {}))

        if gate_field:
            if gate_field not in properties:
                raise ValueError(f"{prompt_key}: gate_field {gate_field!r} fehlt im Schema.")
            if ordering[0] != gate_field:
                raise ValueError(
                    f"{prompt_key}: gate_field {gate_field!r} muss als erstes "
                    "Feld in propertyOrdering stehen."
                )

        if trailing:
            tail_len = len(trailing)
            if ordering[-tail_len:] != trailing:
                raise ValueError(
                    f"{prompt_key}: trailing_fields {trailing} muessen die "
                    "letzten Felder in propertyOrdering sein (Priming-Schutz)."
                )

        for dim in dims:
            if dim not in properties:
                raise ValueError(f"{prompt_key}: Dimension {dim!r} fehlt im Schema.")
            dim_schema = bundle["schema"]["properties"][dim]
            dim_order = dim_schema.get("propertyOrdering", [])
            if dim_order[:2] != ["beleg", "wert"]:
                raise ValueError(
                    f"{prompt_key}: Dimension {dim!r} muss 'beleg' vor 'wert' "
                    "ordnen (extract-then-judge)."
                )

        if bundle.get("null_convention") not in {"zero", "null"}:
            raise ValueError(
                f"{prompt_key}: null_convention muss 'zero' oder 'null' sein."
            )

    else:
        raise ValueError(f"{prompt_key}: unbekannte kind {kind!r}")

    return bundle

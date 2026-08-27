"""
Prompts fuer die Segment-Klassifikation (Vereinfachte Version).

Prompttext, responseSchema und Validierungsregeln stehen pro Prompt in
einem Bundle.
"""

from __future__ import annotations

# ============================================================
# ERLAUBTE WERTE
# ============================================================

STATUS_VALUES = ["nicht_thematisiert", "deskriptiv", "bewertend"]

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

ERKENNBAR_VALUES = ["erkennbar", "nicht_erkennbar"]


# ============================================================
# PROMPT: POSITION_V1
# ============================================================

POSITION_V1_TEXT = """Du bist ein Kodierer in einem sozialwissenschaftlichen Forschungsprojekt. Du kodierst ein Segment aus dem Transkript eines deutschsprachigen YouTube-Videos. Du arbeitest mit automatisch erzeugten Transkripten: Eigennamen sind haeufig falsch geschrieben, Satzzeichen fehlen oder sitzen falsch, einzelne Woerter sind verschluckt. Erschliesse die Bedeutung aus dem Zusammenhang.


GRUNDREGELN
1. Kodiere ausschliesslich auf Basis des vorliegenden Segmenttexts. Ergaenze kein Weltwissen ueber den Kanal, den Sprecher oder den weiteren Videokontext.
2. Zitierte oder eingespielte Fremdrede (O-Toene, Zitate, Interviewpassagen) zaehlt zur Kodierung dazu. Die Auswahl zitierter Rede wird als redaktionelle Entscheidung des Kanals gewertet. Ob Fremdrede dominiert, wird separat erfasst.
3. Kodiere, was gesagt wird, nicht, ob es zutrifft. Bewerte keine Faktizitaet.

--------------------------------------------------------------------
DIMENSION 1 - POSITION GEGENUEBER RUSSLAND

Schritt 1a - rus_status:
Beurteile, ob Russland/die russiche Politik in dem Segment thematisiert und bewertet wird:
  nicht_thematisiert = Russland/die russische Politik wird nicht thematisiert
  deskriptiv = Russland/die russische Politik wird thematisiert, aber nur deskriptiv. Es werden keine Bewertungen vorgenommen.
  bewertend = Russland/die russische Politik wird thematisiert und es werden Bewertungen (positiv, negativ, oder beides) vorgenommen.

Schritt 1b - rus_score (nur bei rus_status = "bewertend", sonst null):
 +2 = Russisches Handeln wird gerechtfertigt oder als legitim/notwendig dargestellt; die Hauptverantwortung fuer den Krieg wird der Ukraine, der NATO oder dem Westen zugeschrieben.
 +1 = Russisches Handeln wird relativiert, erklaert oder entlastet (z. B. Verweis auf Provokation, Sicherheitsinteressen, doppelte Standards), ohne es voll zu legitimieren; oder Verantwortung wird deutlich geteilt zugeschrieben.
  0 = Bewertende Elemente vorhanden, aber gegenlaeufig oder ausgewogen; keine Richtung ueberwiegt.
 -1 = Russisches Handeln wird kritisiert oder Russland wird Verantwortung zugeschrieben, ohne starke Zuspitzung.
 -2 = Russisches Handeln wird als illegitim, aggressiv, verbrecherisch dargestellt; klare Alleinverantwortung Russlands; ggf. Delegitimierung der russischen Fuehrung.

--------------------------------------------------------------------
DIMENSION 2 - POSITION GEGENUEBER DER WESTLICHEN UKRAINE-POLITIK

Gehe fuer diese Dimension erneut an den Segmenttext. Das Urteil aus Dimension 1 ist fuer Dimension 2 ohne Bedeutung.

Gegenstand ist die Politik westlicher Akteure (Bundesregierung, EU, NATO, USA) gegenueber dem Krieg - nicht die Ukraine als Land und nicht westliche Politik im Allgemeinen.

Schritt 2a - west_status
Beurteile, ob westliche Ukraine-Politik in dem Segment thematisiert und bewertet wird:
  nicht_thematisiert = Westliche Ukraine-Politik wird nicht thematisiert
  deskriptiv = Westliche Ukraine-Politik wird thematisiert, aber nur deskriptiv. Es werden keine Bewertungen vorgenommen.
  bewertend = Westliche Ukraine-Politik wird thematisiert und es werden Bewertungen (positiv, negativ, oder beides) vorgenommen.

Schritt 2b - west_score (nur bei west_status = "bewertend", sonst null):
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

Schritt 3a - emo_intensitaet (0-3):
  Beurteile die Emotionalität des Segments.
  0 = Sachlich-berichtender oder analytischer Duktus.
  1 = Vereinzelte affektive Ausdruecke, insgesamt sachlicher Ton.
  2 = Durchgehend wertungsstarke Sprache; deutliche Affektmarkierung, aber ohne dramatisierende Ueberhoehung.
  3 = Stark emotionalisiert; Dramatisierung und moralische Erregung tragen das Segment.

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
        "rus_status": {"type": "STRING", "enum": STATUS_VALUES},
        "rus_score": {"type": "INTEGER", "nullable": True},
        "west_status": {"type": "STRING", "enum": STATUS_VALUES},
        "west_score": {"type": "INTEGER", "nullable": True},
        "instrumente": {
            "type": "ARRAY",
            "items": {"type": "STRING", "enum": INSTRUMENT_VALUES},
        },
        "emo_intensitaet": {"type": "INTEGER"},
        "redeform": {"type": "STRING", "enum": REDEFORM_VALUES},
        "fremdrede_dominant": {"type": "BOOLEAN"},
    },
    "propertyOrdering": [
        "rus_status",
        "rus_score",
        "west_status",
        "west_score",
        "instrumente",
        "emo_intensitaet",
        "redeform",
        "fremdrede_dominant",
    ],
    "required": [
        "rus_status",
        "rus_score",
        "west_status",
        "west_score",
        "instrumente",
        "emo_intensitaet",
        "redeform",
        "fremdrede_dominant",
    ],
}


# ============================================================
# PROMPT: POPULISMUS_P (Segmentebene, vier Dimensionen)
# ============================================================

POPULISM_P_TEXT = """Du kodierst deutschsprachige politische Videotranskripte fuer die sozialwissenschaftliche Forschung. Du arbeitest mit automatisch erzeugten Transkripten: Eigennamen sind haeufig falsch geschrieben, Satzzeichen fehlen oder sitzen falsch, einzelne Woerter sind verschluckt. Erschliesse die Bedeutung aus dem Zusammenhang.

Die Transkripte enthalten oft mehrere Sprechende (Moderation, Gaeste) ohne Kennzeichnung. Kodiere das Segment als Ganzes, so wie es der Kanal veroeffentlicht hat - unabhaengig davon, wer spricht.

Zitierte oder eingespielte Fremdrede (O-Toene, Zitate, Interviewpassagen) zaehlt zur Kodierung dazu. Die Auswahl zitierter Rede wird als redaktionelle Entscheidung des Kanals gewertet.

Wird eine Position im Segment ausdruecklich als fremde Position eingefuehrt (z. B. "Kritiker sagen...", "Manche meinen...") und im selben Atemzug vom Sprecher selbst eindeutig als unzutreffend zurueckgewiesen oder relativiert, zaehlt sie NICHT als eigene Position des Kanals. Das gilt nur fuer eine klare eigene Zurueckweisung durch den Sprecher - nicht fuer eingespielte oder zitierte Fremdrede ohne Widerspruch, dort gilt weiterhin die Fremdrede-Regel oben.

Du bewertest die Form der Kommunikation, nicht ihren Wahrheitsgehalt und nicht ihre politische Richtung. Linke und rechte Inhalte werden nach exakt denselben Kriterien bewertet. Deine eigene Haltung zu den Aussagen ist irrelevant.

Bewerte das Segment auf vier unabhaengigen Dimensionen (Skala jeweils 0 bis 3). Die Dimensionen werden getrennt bewertet; eine hohe Bewertung auf einer Dimension erzwingt keine hohe Bewertung auf einer anderen.

### 1. volkszentrismus

Beruft sich der Text auf "das Volk", "die Buerger", "die Menschen", "die Mehrheit" als eine EINHEITLICHE Groesse mit einem gemeinsamen Willen, und stellt sich der Sprecher als deren Stimme dar?

0  Keine Berufung auf ein kollektives Volk, oder nur als sachliche Bevoelkerungsangabe ("40 Prozent der Befragten").
1  Vereinzelte Berufung auf "die Buerger" oder "die Menschen", ohne dass ihnen ein einheitlicher Wille zugeschrieben wird.
2  Dem Volk wird wiederholt ein gemeinsamer Wille oder gesunder Menschenverstand zugeschrieben, dem etwas entgegensteht.
3  Der Sprecher tritt ausdruecklich als Stimme des Volkes auf; der Volkswille ist eindeutig, einheitlich und wird missachtet.

Abgrenzung: Die Nennung einer konkreten Gruppe (Rentner, Landwirte, Ostdeutsche) ist NICHT Volkszentrismus, solange sie nicht mit dem Ganzen gleichgesetzt wird.

### 2. antielitismus

Werden Eliten ALS GRUPPE angegriffen - als eigennuetzig, abgehoben, verlogen oder gegen die Bevoelkerung handelnd? Eliten koennen Politik, Medien, Wissenschaft, Justiz, EU, Konzerne oder NGOs sein.

0  Keine Elitenkritik, oder ausschliesslich sachliche Kritik an einer konkreten Entscheidung oder Person - auch wenn dabei mehrere belegte Einzelfaelle aufgezaehlt werden, die zusammengenommen ein Muster ergeben, solange die Darstellung differenziert bleibt (Quellenangaben, Gegenposition, eingeraeumte Unsicherheiten, auch positives oder reaktives Verhalten der kritisierten Seite werden benannt).
1  Kritik an einzelnen Akteuren mit abwertendem Unterton, aber ohne Verallgemeinerung auf eine Klasse. Ebenso hierher gehoert: Eine Institution wird fuer aus sich selbst heraus erklaerbares Eigeninteresse kritisiert (z. B. ein Unternehmen maximiert Gewinn, eine Organisation schuetzt die eigenen Leute), ohne dass ihr ein gegen die Allgemeinheit gerichtetes, koordiniertes Motiv unterstellt wird.
2  Eliten werden als Gruppe kritisiert, der ein bewusst GEGEN DIE BEVOELKERUNG gerichtetes gemeinsames Motiv oder eine gemeinsame Abgehobenheit unterstellt wird - nicht blosses Eigeninteresse, sondern eine unterstellte Frontstellung gegen "die Menschen da draussen".
3  Eliten erscheinen als geschlossenes System, das bewusst gegen die Bevoelkerung arbeitet, taeuscht oder ein Kartell bildet.

Abgrenzung: "Die Regierung hat bei der Rente falsch entschieden" ist 0. "Die da oben interessiert nicht, was mit uns passiert" ist 2 bis 3. Entscheidend ist die Unterstellung eines GEGEN DIE ALLGEMEINHEIT gerichteten gemeinsamen Motivs. Weder die Schaerfe des Tons noch die Anzahl aufgezaehlter Einzelfaelle noch die blosse Tatsache, dass eine Institution im eigenen Interesse handelt, reicht fuer sich genommen fuer Stufe 2 oder 3.

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

Fuer jede Dimension gilt: Beziehe dich NUR auf das zu kodierende Segment. Ein Kontextblock (falls vorhanden) dient dem Verstaendnis und wird nicht mitbewertet.

Enthaelt das Segment keinen politischen Inhalt (Werbung, Intro, Verabschiedung, Small Talk), setze "kodierbar": false, alle vier Dimensionswerte auf null und "ukraine_bezug": false.

--------------------------------------------------------------------
UKRAINE-BEZUG (ukraine_bezug)

Pruefe als Letztes, ob in dem Segment Bezug auf den Ukraine-Krieg und/oder die westliche Politik in diesem Zusammenhang genommen wird.
- Setze "ukraine_bezug": true, wenn mindestens eines von beidem erfuellt ist.
- Setze "ukraine_bezug": false, wenn weder der Ukraine-Krieg noch die westliche Ukraine-Politik im Segment vorkommen.

--------------------------------------------------------------------
AUSGABEFORMAT
Antworte ausschliesslich mit einem JSON-Objekt in exakt dieser Feldreihenfolge, ohne Vorrede und ohne Markdown."""


POPULISM_P_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "kodierbar": {"type": "BOOLEAN"},
        "volkszentrismus": {"type": "INTEGER", "nullable": True},
        "antielitismus": {"type": "INTEGER", "nullable": True},
        "manichaeische_moralisierung": {"type": "INTEGER", "nullable": True},
        "emotionale_intensitaet": {"type": "INTEGER", "nullable": True},
        "ukraine_bezug": {"type": "BOOLEAN"},
    },
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

IDEOLOGY_I_TEXT = """Du verortest deutschsprachige politische Videotranskripte auf ideologischen Dimensionen, fuer die sozialwissenschaftliche Forschung. Du arbeitest mit automatisch erzeugten Transkripten mit Erkennungsfehlern.

Zitierte oder eingespielte Fremdrede (O-Toene, Zitate, Interviewpassagen) zaehlt zur Kodierung dazu. Die Auswahl zitierter Rede wird als redaktionelle Entscheidung des Kanals gewertet.

Du verortest die im Text vertretenen POSITIONEN, nicht die Person und nicht den Kanal. Du bewertest nicht, ob eine Position richtig ist.

Verorte die im Transkript vertretenen Positionen auf zwei unabhaengigen Dimensionen. Jede Dimension wird in zwei Schritten kodiert: zuerst, ob sich ueberhaupt eine Position erkennen laesst, danach - falls ja - deren Auspraegung.

--------------------------------------------------------------------
DIMENSION 1 - WIRTSCHAFT

Schritt 1a - wirtschaft_status:
  erkennbar = Im Transkript laesst sich eine wirtschaftspolitische Tendenz erkennen - auch dann, wenn sie ausgewogen oder gemischt ist.
  nicht_erkennbar = Das Thema kommt im Transkript nicht vor, oder es laesst sich keinerlei Tendenz erkennen. Rate nicht.

Schritt 1b - wirtschaft (nur bei wirtschaft_status = "erkennbar", sonst null):
-2  Starke Umverteilung, Verstaatlichung, Ausbau des Sozialstaats, Kapitalismuskritik
 0  Position erkennbar, aber ausgewogen oder gemischt zwischen den Polen
+2  Marktliberal, Steuersenkung, Deregulierung, Sozialstaatskritik

--------------------------------------------------------------------
DIMENSION 2 - GESELLSCHAFT

Gehe fuer diese Dimension erneut an den Text. Das Urteil aus Dimension 1 ist fuer Dimension 2 ohne Bedeutung.

Schritt 2a - gesellschaft_status:
  erkennbar = Im Transkript laesst sich eine gesellschaftspolitische Tendenz erkennen - auch dann, wenn sie ausgewogen oder gemischt ist.
  nicht_erkennbar = Das Thema kommt im Transkript nicht vor, oder es laesst sich keinerlei Tendenz erkennen. Rate nicht.

Schritt 2b - gesellschaft (nur bei gesellschaft_status = "erkennbar", sonst null):
-2  Progressiv: Vielfalt, Minderheitenrechte, Klimaschutz vor Wachstum, offene Migrationspolitik
 0  Position erkennbar, aber ausgewogen oder gemischt zwischen den Polen
+2  Konservativ bis national: Tradition, Leitkultur, restriktive Migrationspolitik, Kritik an Klima- und Genderpolitik

--------------------------------------------------------------------
AUSGABEFORMAT
Antworte ausschliesslich mit einem JSON-Objekt in exakt dieser Feldreihenfolge, ohne Vorrede und ohne Markdown."""


IDEOLOGY_I_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "wirtschaft_status": {"type": "STRING", "enum": ERKENNBAR_VALUES},
        "wirtschaft": {"type": "INTEGER", "nullable": True},
        "gesellschaft_status": {"type": "STRING", "enum": ERKENNBAR_VALUES},
        "gesellschaft": {"type": "INTEGER", "nullable": True},
    },
    "propertyOrdering": [
        "wirtschaft_status",
        "wirtschaft",
        "gesellschaft_status",
        "gesellschaft",
    ],
    "required": [
        "wirtschaft_status",
        "wirtschaft",
        "gesellschaft_status",
        "gesellschaft",
    ],
}


# ============================================================
# BUNDLES
# ============================================================

SEGMENT_PROMPTS = {
    "POSITION_V1": {
        "kind": "flat_status",
        "text": POSITION_V1_TEXT,
        "schema": POSITION_V1_SCHEMA,
        "target_variable": "position_russia_west",
        "conditional_score_rules": [
            ("rus_status", "bewertend", "rus_score"),
            ("west_status", "bewertend", "west_score"),
        ],
        "score_ranges": {
            "rus_score": (-2, 2),
            "west_score": (-2, 2),
            "emo_intensitaet": (0, 3),
        },
        "evidence_fields": [],
        "enum_fields": {
            "rus_status": STATUS_VALUES,
            "west_status": STATUS_VALUES,
            "instrumente": INSTRUMENT_VALUES,
            "redeform": REDEFORM_VALUES,
        },
        "trailing_fields": {"fremdrede_dominant": "bool"},
    },
    "POPULISMUS_P": {
        "kind": "flat_status",
        "text": POPULISM_P_TEXT,
        "schema": POPULISM_P_SCHEMA,
        "target_variable": "populism_segment",
        "segment_label": "ZU KODIERENDES SEGMENT",
        "use_context": True,
        "score_ranges": {
            "volkszentrismus": (0, 3),
            "antielitismus": (0, 3),
            "manichaeische_moralisierung": (0, 3),
            "emotionale_intensitaet": (0, 3),
        },
        "evidence_fields": [],
        "enum_fields": {},
        "gate_field": "kodierbar",
        "gate_open_value": True,
        "trailing_fields": {"ukraine_bezug": "bool"},
    },
    "IDEOLOGIE_I": {
        "kind": "flat_status",
        "text": IDEOLOGY_I_TEXT,
        "schema": IDEOLOGY_I_SCHEMA,
        "target_variable": "ideology_baseline",
        "segment_label": "TRANSKRIPT",
        "use_context": False,
        "conditional_score_rules": [
            ("wirtschaft_status", "erkennbar", "wirtschaft"),
            ("gesellschaft_status", "erkennbar", "gesellschaft"),
        ],
        "score_ranges": {
            "wirtschaft": (-2, 2),
            "gesellschaft": (-2, 2),
        },
        "evidence_fields": [],
        "enum_fields": {
            "wirtschaft_status": ERKENNBAR_VALUES,
            "gesellschaft_status": ERKENNBAR_VALUES,
        },
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
        for field in bundle.get("evidence_fields", []):
            if field not in properties:
                raise ValueError(f"{prompt_key}: evidence_field {field!r} fehlt im Schema.")

        score_ranges = bundle.get("score_ranges", {})
        enum_fields = bundle.get("enum_fields", {})
        for status_field, expected_value, score_field in bundle.get("conditional_score_rules", []):
            if status_field not in properties or score_field not in properties:
                raise ValueError(
                    f"{prompt_key}: conditional_score_rule referenziert unbekanntes "
                    f"Feld ({status_field!r}/{score_field!r})."
                )
            if score_field not in score_ranges:
                raise ValueError(
                    f"{prompt_key}: conditional_score_rule-Feld {score_field!r} "
                    "fehlt in score_ranges."
                )
            allowed = enum_fields.get(status_field)
            if allowed is not None and expected_value not in allowed:
                raise ValueError(
                    f"{prompt_key}: erwarteter Wert {expected_value!r} fuer "
                    f"{status_field!r} ist nicht in enum_fields gelistet."
                )
            if ordering.index(status_field) > ordering.index(score_field):
                raise ValueError(
                    f"{prompt_key}: {status_field!r} steht in propertyOrdering "
                    f"hinter {score_field!r}."
                )

        trailing = list(bundle.get("trailing_fields", {}))
        if trailing:
            tail_len = len(trailing)
            if ordering[-tail_len:] != trailing:
                raise ValueError(
                    f"{prompt_key}: trailing_fields {trailing} muessen die "
                    "letzten Felder in propertyOrdering sein (Priming-Schutz)."
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
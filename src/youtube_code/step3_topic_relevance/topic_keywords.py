"""
Kanonische Keyword-Definition fuer die Themen-Relevanz-Klassifikation
(video_registry.video_topic_relevance, siehe classify_topic_relevance.py).

Fuenf Themen: der Ukraine-Krieg (ukr_core/ukr_wide, 1:1 aus
youtube_code.new_analysis.feasibility Zeilen 99-113 uebernommen - dort bereits
validiert, siehe feasibility.py-Docstring und Analyseplan) sowie vier neu
erarbeitete Vergleichs-/Kontrollthemen (Corona/Pandemie, Migration,
Wirtschaft allgemein, Energie), die als Vergleichsthemen fuer Forschungsfrage
4 dienen (siehe .claude/plans/new_topics.md). feasibility.py selbst bleibt
unangetastet (nur Referenzquelle fuer den Ukraine-Krieg); dieses Modul ist die
einzige Stelle, an der neue Skripte diese Muster importieren sollen.

"ukr_risky" (nato/krieg/sanktion/eu) wird bewusst NICHT uebernommen -
feasibility.py markiert es selbst als "nie in die Treatment-Definition
aufnehmen, nur zur Diagnose" (Fehlalarm-Kontrolle gegen die Boilerplate-Regel).

Wirtschaft/Energie sind bewusst zwei getrennte Themen statt einem gemeinsamen,
obwohl sie inhaltlich eng verknuepft sind (Sanktionen, Gaspreise, Nord
Stream) - so laesst sich spaeter pruefen, ob ein Effekt kriegsnah ueber
Energie oder allgemein wirtschaftlich laeuft. Ueberschneidungen zwischen
Themen (v.a. energy <-> russia_ukraine_war, energy <-> economy_general) sind
gewollt und werden ueber die video_id x topic-Struktur von
video_topic_relevance abgebildet, nicht durch gegenseitigen Ausschluss der
Keyword-Sets verhindert. Fuer alle vier neuen Themen bewusst KEINE
hochgradig polysemen Einzelwoerter bare (z.B. "Grenze", "Preis", "Gas",
"Strom", "Integration") und KEINE Politiker-Nachnamen (anders als bei
Ukraine/Selenskyj/Putin, da diese breitere Themen-Portfolios haben und die
Abgrenzung verwischen wuerden) - nur Komposita/Fachbegriffe.
"""
import re

# ============================================================
# Ukraine-Krieg
# ============================================================

# Enger Kern: praktisch nur Kriegskontext. Das ist die Hauptdefinition.
_UKR_CORE = r"""
    ukrain | selensk | zelensk | wolodymyr
    | kyjiw | kyiw | \bkiew\b | charkiw | mariupol | bachmut | cherson
    | donbas | donezk | luhansk | saporischschja
    | butscha | asow | wagner
"""

# Erweitert: Russland/Krieg allgemein. Hohe Recall, niedrigere Precision.
_UKR_WIDE = r"""
    russland | russisch | russische[nrms]? | putin | kreml | \bmoskau\b
    | \bkrim\b | krimhalbinsel
    | waffenlieferung | panzerlieferung | \bleopard\b | \btaurus\b
    | ringtausch | kriegsverbrech | ostfront | frontverlauf
"""

# ============================================================
# Corona/Pandemie
# ============================================================

# FP-Risiko: "corona" bare (Bier, Sonnenkorona, Automodell) daher nur in wide,
# nicht core; "impfstoff"/"geimpft"/"rki" (wide) koennen sich ab 2023 auch auf
# andere Impfungen/Krankheiten beziehen (akzeptierter Recall/Precision-
# Trade-off im wide-Tier).
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

# ============================================================
# Migration
# ============================================================

# FP-Risiko: "Grenze"/"Integration" bare bewusst ausgeschlossen (Ueberlappung
# mit Ukraine-Russland-Grenze/NATO-Ostgrenze bzw. generischer Alltagsbegriff)
# - nur Komposita.
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

# ============================================================
# Wirtschaft (allgemein)
# ============================================================

# FP-Risiko: "Preis"/"Industrie"/"Rente" bare bewusst ausgeschlossen. Bewusste
# Ueberschneidung mit Energie ueber "verbraucherpreis" (wide) - energie-
# spezifische Preisbegriffe (energiepreis, gaspreis, strompreis) liegen
# primaer im Energie-Core, damit ein Video wirtschaft-only, energie-only oder
# beides sein kann.
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

# ============================================================
# Energie
# ============================================================

# FP-Risiko: "Gas"/"Strom" bare bewusst ausgeschlossen (Gaspedal/Lachgas bzw.
# "im Strom der Zeit"). Ueberschneidung mit russia_ukraine_war (Nord Stream,
# Gasembargo) ist gewollt - erlaubt spaeter zu pruefen, ob Effekte kriegsnah
# ueber Energie oder allgemein wirtschaftlich laufen (Forschungsfrage 4).
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

# Pro Thema: prefix (fuer die KW_RE-/Flag-Schluessel, haelt die bestehenden
# ukr_core/ukr_wide-Namen unveraendert - keine Ukraine-Re-Klassifizierung
# noetig) sowie die core/wide-Regexe.
TOPIC_KEYWORDS = {
    "russia_ukraine_war": {"prefix": "ukr", "core": _UKR_CORE, "wide": _UKR_WIDE},
    "corona_pandemic": {"prefix": "corona", "core": _CORONA_CORE, "wide": _CORONA_WIDE},
    "migration": {"prefix": "migration", "core": _MIGRATION_CORE, "wide": _MIGRATION_WIDE},
    "economy_general": {"prefix": "econ", "core": _ECON_CORE, "wide": _ECON_WIDE},
    "energy": {"prefix": "energy", "core": _ENERGY_CORE, "wide": _ENERGY_WIDE},
}


def _compile(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE | re.VERBOSE)


# {prefix}_{tier}: kompilierte Regex, ueber alle Themen hinweg - z.B.
# "ukr_core", "corona_wide", "energy_core".
KW_RE = {
    f"{cfg['prefix']}_{tier}": _compile(pattern)
    for cfg in TOPIC_KEYWORDS.values()
    for tier, pattern in cfg.items()
    if tier != "prefix"
}

# Pro Thema ein eigener Versionsstring statt einem globalen - erlaubt,
# einzelne Themen unabhaengig neu zu klassifizieren, ohne die anderen vier
# ungewollt mit hochzuversionieren.
KEYWORD_SET_VERSION = {
    "russia_ukraine_war": "ukr_core_wide_v1_2026-09-01",
    "corona_pandemic": "corona_core_wide_v1_2026-09-09",
    "migration": "migration_core_wide_v1_2026-09-09",
    "economy_general": "econ_core_wide_v1_2026-09-09",
    "energy": "energy_core_wide_v1_2026-09-09",
}


def _tier_names(topic: str) -> list:
    return [t for t in TOPIC_KEYWORDS[topic] if t != "prefix"]


def match_flags(topic: str, title: str, desc_clean: str) -> dict:
    """
    Berechnet fuer title und die (bereits boilerplate-bereinigte) desc_clean
    je Tier (core/wide) von topic ein Titel- und ein Beschreibungs-Flag -
    getrennt geprueft, NIE konkateniert (spiegelt fuer russia_ukraine_war
    feasibility.cmd_extract Zeilen 412-414).

    Rueckgabe z.B. fuer topic="russia_ukraine_war":
        {"ukr_core_title": bool, "ukr_core_desc": bool,
         "ukr_wide_title": bool, "ukr_wide_desc": bool}
    """
    prefix = TOPIC_KEYWORDS[topic]["prefix"]
    flags = {}
    for tier in _tier_names(topic):
        rx = KW_RE[f"{prefix}_{tier}"]
        flags[f"{prefix}_{tier}_title"] = bool(rx.search(title or ""))
        flags[f"{prefix}_{tier}_desc"] = bool(rx.search(desc_clean or ""))
    return flags


def is_relevant(flags: dict) -> bool:
    """
    Kombinationslogik: ein Video gilt als relevant, sobald irgendein Tier in
    Titel ODER Beschreibung trifft - fuer russia_ukraine_war mathematisch
    identisch zur urspruenglichen, 1:1 aus feasibility.cmd_feasibility
    (Zeilen 437-438) uebernommenen Logik
    (treat_title = ukr_core_title OR ukr_wide_title;
     treat_wide = treat_title OR ukr_core_desc OR ukr_wide_desc), da beides
    reine ODER-Verknuepfungen ueber dieselben vier Flags sind. Generalisiert
    sich unveraendert auf Themen mit mehr oder weniger als zwei Tiers.
    """
    return any(flags.values())


def is_relevant_vectorized(flags: dict):
    """
    Spaltenweise (pandas.Series[bool]) Fassung von is_relevant() fuer den
    performanten Massenbetrieb in classify_topic_relevance.classify() - exakt
    dieselbe Kombinationslogik, nur auf ganzen DataFrame-Spalten statt pro
    Zeile ausgewertet (bool-Operatoren |/&/or verhalten sich fuer
    pandas.Series und Python-bool identisch).
    """
    result = None
    for series in flags.values():
        result = series if result is None else (result | series)
    return result

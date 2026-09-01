"""
Kanonische Keyword-Definition fuer die Themen-Relevanz-Klassifikation
(video_registry.video_topic_relevance, siehe classify_topic_relevance.py).

Die Regex-Muster sind 1:1 aus youtube_code.new_analysis.feasibility (Zeilen
99-113, "ukr_core"/"ukr_wide") uebernommen - dort bereits validiert (siehe
feasibility.py-Docstring und Analyseplan). feasibility.py selbst bleibt
unangetastet (nur Referenzquelle); dieses Modul ist die einzige Stelle, an
der neue Skripte diese Muster importieren sollen.

"ukr_risky" (nato/krieg/sanktion/eu) wird bewusst NICHT uebernommen -
feasibility.py markiert es selbst als "nie in die Treatment-Definition
aufnehmen, nur zur Diagnose" (Fehlalarm-Kontrolle gegen die Boilerplate-Regel).
"""
import re

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

KEYWORDS = {
    "ukr_core": _UKR_CORE,
    "ukr_wide": _UKR_WIDE,
}


def _compile(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE | re.VERBOSE)


KW_RE = {k: _compile(v) for k, v in KEYWORDS.items()}

# Generisches Dict fuer spaetere Themen (z.B. KEYWORDS_MIDDLE_EAST aus
# config/settings.py als zweiter Eintrag) - neues Thema = neuer Eintrag,
# kein Schema-Umbau in video_registry.py noetig.
TOPIC_KEYWORDS = {
    "russia_ukraine_war": {"core": _UKR_CORE, "wide": _UKR_WIDE},
}

# Existiert in feasibility.py nicht - neu eingefuehrt, damit ein
# Re-Klassifizierungslauf mit geaenderten Mustern bestehende
# video_topic_relevance-Zeilen kontrolliert ueberschreiben kann (siehe
# COALESCE-Richtung in video_registry.upsert_topic_relevance).
KEYWORD_SET_VERSION = "ukr_core_wide_v1_2026-09-01"


def match_flags(title: str, desc_clean: str) -> dict:
    """
    Berechnet fuer title und die (bereits boilerplate-bereinigte) desc_clean
    je Keyword-Set ein Titel- und ein Beschreibungs-Flag - getrennt geprueft,
    NIE konkateniert (spiegelt feasibility.cmd_extract Zeilen 412-414).

    Rueckgabe: {"ukr_core_title": bool, "ukr_core_desc": bool,
                "ukr_wide_title": bool, "ukr_wide_desc": bool}
    """
    flags = {}
    for k, rx in KW_RE.items():
        flags[f"{k}_title"] = bool(rx.search(title or ""))
        flags[f"{k}_desc"] = bool(rx.search(desc_clean or ""))
    return flags


def is_relevant(flags: dict) -> bool:
    """
    Kombinationslogik 1:1 aus feasibility.cmd_feasibility (Zeilen 437-438):
        treat_title = ukr_core_title OR ukr_wide_title
        treat_wide  = treat_title OR ukr_core_desc OR ukr_wide_desc
    is_relevant in video_topic_relevance entspricht treat_wide.
    """
    treat_title = flags["ukr_core_title"] or flags["ukr_wide_title"]
    return treat_title or flags["ukr_core_desc"] or flags["ukr_wide_desc"]

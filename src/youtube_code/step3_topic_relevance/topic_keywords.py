r"""
Kanonische Keyword-Definition fuer die Themen-Relevanz-Klassifikation
(video_registry.video_topic_relevance, siehe classify_topic_relevance.py).
Dieses Modul ist die einzige Stelle, an der neue Skripte diese Muster
importieren sollen.

Themen (Stand 2026-10-05), jeweils mit core + wide:
    russia_ukraine_war  Ukraine-Krieg (ukr_core/ukr_wide, unveraendert 1:1 aus
                        youtube_code.new_analysis.feasibility Zeilen 99-113)
    politics_general    Politik allgemein (Parteien, Institutionen, Wahlen,
                        Spitzenpolitiker) - nur zur Abgrenzung "politisch",
                        kein Kontrastthema
    corona_pandemic     Corona/Pandemie (unveraendert)
    migration           Migration (unveraendert)
    economy_general     Wirtschaftspolitik (unveraendert)
    energy              Energiepolitik (unveraendert)
    climate             Klimapolitik (neu)
    gender              Gender/Identitaet (neu)
    mideast             Naher Osten / Israel-Palaestina (neu)
    iran                Iran inkl. Israel-Iran, Iran-USA und Iran-Innenpolitik (neu)
    eu                  EU-Politik (neu)
    usa                 USA inkl. US-Aussenpolitik (neu)
    education           Bildungspolitik (neu; einziges wenig polarisiertes Thema)

Doppelte Rolle der Themen (Entscheidung 2026-10-05):
1. Abgrenzung der Vergleichsgruppe fuer die Kriegspraemie: ein Video gilt als
   politisch, wenn irgendein Thema (inkl. politics_general) relevant ist;
   Vergleichsgruppe = politisch UND nicht russia_ukraine_war.
2. Kontrastthemen fuer Krisenopportunismus (M3): polarisierende /
   populistisch besetzte Themen (migration, corona, climate, gender), weitere
   Kriege / aussenpolitische Konflikte (mideast, iran, usa), kriegsnahe Folgen
   (energy, economy_general), Arena (eu) und ein wenig polarisierter Kontrast
   (education).

Ueberschneidungen zwischen Themen sind gewollt und werden ueber die
video_id x topic-Struktur von video_topic_relevance abgebildet, nicht durch
gegenseitigen Ausschluss der Keyword-Sets (z.B. energy <-> russia_ukraine_war,
iran <-> mideast, usa <-> iran/russia_ukraine_war, eu <-> migration/energy).
Exklusive Kontrastkategorien (z.B. "nur Gaza" / "nur Iran" / "beides")
werden erst in der Analyse gebildet.

Regeln fuer die Listen:
- Keine hochgradig polysemen Einzelwoerter (z.B. "Grenze", "Preis", "Gas",
  "Strom", "Integration", "Union", "eu", "Wahl", "Ampel" bare) - nur
  Komposita, Fachbegriffe oder Kontextmuster.
- Keine Politiker-Nachnamen in Themenlisten. Begruendete Ausnahmen, weil das
  Thema ohne sie nicht erfassbar ist bzw. die Person themenspezifisch ist:
  Selenskyj/Putin (Ukraine), Netanjahu (Nahost), Chamenei/Soleimani (Iran),
  von der Leyen (EU), Trump/Biden/Kamala Harris/Vance (USA). In
  politics_general sind Politikernamen ausdruecklich erlaubt, weil dort
  Vollstaendigkeit das Ziel ist und keine Themenabgrenzung.
- Wide-Listen von climate und gender enthalten auch Kampfbegriffe
  ("Klimahysterie", "woke"). Damit misst wide teilweise das Framing mit
  (korreliert mit Populismus) -> fuer Kontrastanalysen core als
  Themendefinition bevorzugen, core+wide als Robustheit.
- "ukr_risky" (nato/krieg/sanktion/eu) wird bewusst NICHT uebernommen -
  feasibility.py markiert es als "nie in die Treatment-Definition aufnehmen,
  nur zur Diagnose".

Offen: ob fuer russia_ukraine_war core allein oder core+wide die
Hauptdefinition ist (aktuell zaehlt beides, siehe is_relevant()).

Alle Muster werden mit re.IGNORECASE | re.VERBOSE kompiliert:
Leerzeichen im Muster werden ignoriert, echte Leerzeichen daher immer als \s.
"""
import re

TIERS = ("core", "wide")

# ============================================================
# Ukraine-Krieg (unveraendert)
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
# Politik allgemein (nur Abgrenzung "politisch", kein Kontrastthema)
# ============================================================

# FP-Risiko: "die Gruenen"/"die Linke" bare sind auch Alltagssprache ("die
# gruenen Wiesen", "die linke Hand") -> im core nur Kontextmuster, die bare
# Formen erst in wide, dort case-sensitive (Substantiv "die Linke"/"die Gruenen"
# vs. Adjektiv "die linke Hand"/"die gruenen Wiesen"). "Union" bare (EU,
# Gewerkschaft) ganz ausgeschlossen.
_POLITICS_CORE = r"""
    \bafd\b | \bspd\b | \bcdu\b | \bcsu\b | \bfdp\b | \bbsw\b
    | bündnis\s*90 | grünen[- ]?(?:chef\w*|politiker\w*|fraktion\w*|minister\w*|vorsitz\w*|parteitag)
    | grüne\s+jugend | linkspartei | linken[- ]?(?:chef\w*|politiker\w*|fraktion\w*|vorsitz\w*)
    | partei\s+die\s+linke | unionsfraktion | unionsparteien | freie\s+wähler
    | bundestag\w* | bundesregierung | bundeskanzler\w* | \bbundesrat\b
    | \bminister\w* | ampel[- ]?(?:koalition|regierung|parteien|aus)
    | koalitionsvertrag | koalitionsverhandlung\w* | koalitionsausschuss
    | \blandtag\w* | bundestagswahl\w* | landtagswahl\w* | europawahl\w*
    | wahlkampf\w* | wahlprogramm\w* | parteitag\w* | gesetzentwurf\w*
    | misstrauensvotum | vertrauensfrage | regierungserklärung
"""
_POLITICS_WIDE = r"""
    (?-i:\b[Dd]ie\s+Grünen\b) | (?-i:\b[Dd]ie\s+Linke\b) | \bdie\s+ampel\b | \bopposition\w*
    | scholz | \bmerz\b | habeck | baerbock | \blindner\b | weidel
    | wagenknecht | söder | faeser | lauterbach | steinmeier | pistorius
    | \bspahn\b | chrupalla | \bhöcke\b | kretschmer
    | politik\b | politisch\w* | verfassungsschutz | haushaltsdebatte
"""

# ============================================================
# Corona/Pandemie (unveraendert)
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
# Migration (unveraendert)
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
# Wirtschaftspolitik (unveraendert; Schluessel economy_general beibehalten)
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
# Energiepolitik (unveraendert)
# ============================================================

# FP-Risiko: "Gas"/"Strom" bare bewusst ausgeschlossen (Gaspedal/Lachgas bzw.
# "im Strom der Zeit"). Ueberschneidung mit russia_ukraine_war (Nord Stream,
# Gasembargo) ist gewollt - erlaubt spaeter zu pruefen, ob Effekte kriegsnah
# ueber Energie oder allgemein wirtschaftlich laufen.
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

# ============================================================
# Klimapolitik (neu)
# ============================================================

# Getrennt von Energie; "energiewende"/"heizungsgesetz" bleiben in Energie.
# Wide enthaelt Kampfbegriffe (Framing, s. Modul-Docstring) und
# Verkehrs-/Gebaeudeklimapolitik (Verbrenner-Aus, Tempolimit).
_CLIMATE_CORE = r"""
    klimawandel\w* | klimaschutz\w* | klimapolitik | klimakrise\w*
    | klimaziel\w* | klimaneutral\w* | klimakatastrophe | erderwärmung
    | klimakleber\w* | letzte\s+generation | fridays\s+for\s+future
    | klimaaktivist\w* | klimagipfel\w* | klimakonferenz\w* | \bcop\s?2\d\b
    | co2[- ]?(?:steuer|preis\w*|abgabe|bepreisung|zertifikat\w*)
"""
_CLIMATE_WIDE = r"""
    klimaleugner\w* | klimahysterie | klimasekte | klimawahn | klimaterror\w*
    | klimareligion | treibhausgas\w* | co2[- ]?ausstoß | emissionshandel
    | verbrenner[- ]?verbot | verbrenner[- ]?aus | heizungsverbot | tempolimit
"""

# ============================================================
# Gender/Identitaet (neu)
# ============================================================

_GENDER_CORE = r"""
    \bgendern\b | \bgendert\b | gendersprache | genderverbot
    | gender[- ]?(?:wahn|ideologie|sternchen|gaga|debatte|politik)
    | selbstbestimmungsgesetz | transgender\w* | transsexuell\w*
    | \btrans[- ]?(?:frau|mann|männer|menschen|person|jugendliche)\w*
    | geschlechtsidentität | geschlechtseintrag | \bqueer\w*
    | \blgbt\w* | drag[- ]?queen\w* | pride[- ]?monat | \bnon[- ]?binär\w*
"""
_GENDER_WIDE = r"""
    \bwoke\w* | wokeness | identitätspolitik | cancel[- ]?culture
    | regenbogen[- ]?(?:flagge|binde|fahne|ideologie)\w*
    | \bcsd\b | christopher[- ]street | geschlechtergerecht\w*
    | feminis\w* | frauenquote
"""

# ============================================================
# Naher Osten / Israel-Palaestina (neu)
# ============================================================

# Iran sowie Hisbollah/Huthi bewusst NICHT hier, sondern im Thema iran, damit
# die Abgrenzung Gaza vs. Iran scharf bleibt. "7. Oktober" nur mit Jahr
# (sonst Datumstreffer jedes Jahres).
_MIDEAST_CORE = r"""
    \bisrael\w* | \bgaza\w* | \bhamas\b | netanjahu | netanyahu
    | nahost\w* | palästin\w* | westjordanland | \bidf\b | intifada
    | zweistaatenlösung | \bunrwa\b
"""
_MIDEAST_WIDE = r"""
    antisemitismus | antisemitisch\w* | judenhass | zionis\w*
    | 7\.\s*oktober\s*2023 | jerusalem | tel[- ]?aviv | \brafah\b
    | siedlungsbau | siedlergewalt
"""

# ============================================================
# Iran (neu) - inkl. Israel-Iran, Iran-USA, Iran-Innenpolitik
# ============================================================

# Iran-Innenpolitik (z.B. Proteste 2022/23) bewusst eingeschlossen: das Thema
# misst allgemeine Aufmerksamkeit fuer Iran. FP-Risiko wide: "Rotes Meer"
# auch Tourismus (Aegypten).
_IRAN_CORE = r"""
    \biran\w* | teheran | mullah\w* | ajatollah\w* | chamenei | khamenei
    | revolutionsgarde\w* | soleimani | raisi\b | atomabkommen | atomdeal
    | \bjcpoa\b | urananreicherung | \bfordo\w* | natanz | mahsa\s+amini
"""
_IRAN_WIDE = r"""
    huthi\w* | \bhouthi\w* | rote[ns]?\s+meer | straße\s+von\s+hormus
    | hisbollah | hizbollah | frau[,]?\s+leben[,]?\s+freiheit
"""

# ============================================================
# EU-Politik (neu)
# ============================================================

# "eu" bare ausgeschlossen (in feasibility.py als ukr_risky / Fehlalarm
# markiert) - nur Komposita und Institutionennamen. Ueberschneidung mit
# Krieg (EU-Sanktionen, EU-Beitritt Ukraine), Migration (Migrationspakt) und
# Klima (Verbrenner-Aus) gewollt.
_EU_CORE = r"""
    \beu[- ]?(?:kommission\w*|parlament\w*|gipfel\w*|kommissar\w*|ratspräsidentschaft
        |beitritt\w*|mitglied\w*|recht\w*|austritt|verordnung\w*|richtlinie\w*
        |sanktion\w*|wahl\w*|politik|staaten|länder|haushalt\w*|vertrag\w*|außengrenze\w*)
    | europaparlament\w* | europäische\s+union | europäischen\s+union
    | europäische[n]?\s+kommission | europäische[n]?\s+parlament\w*
    | von\s+der\s+leyen | \bdexit\b | \bbrexit\b | europawahl\w*
"""
_EU_WIDE = r"""
    brüssel\w* | eudssr | eu[- ]?bürokrat\w* | \beurozone\b | \beuroraum\b
    | \bezb\b | schengen\w* | lissabon[- ]?vertrag | europäischer\s+rat
    | \beugh\b | europäische[nr]?\s+gerichtshof
"""

# ============================================================
# USA (neu) - inkl. US-Aussenpolitik
# ============================================================

# Aussenpolitik laesst sich per Stichwort nicht vom Rest trennen -> Thema
# misst USA-Bezug allgemein. "trump" mit Ausschluss von "Trumpf".
# "\bamerika" trifft nicht Sued-/Latein-/Nordamerika (kein \b davor).
_USA_CORE = r"""
    \busa\b | vereinigte[n]?\s+staaten | \btrump(?!f)\w* | \bbiden\b
    | kamala\s+harris | \bvance\b | weiße[ns]?\s+haus | pentagon
    | \bus[- ]?(?:regierung|präsident\w*|wahl\w*|armee|militär|außenminister\w*
        |außenpolitik|zoll|zölle\w*|demokraten|republikaner|kongress|senat\w*
        |administration|botschafter\w*|truppen)
    | \bmaga\b | us[- ]?amerikan\w*
"""
_USA_WIDE = r"""
    \bamerika\w* | washington | präsidentschaftswahl\w* | \bcia\b
    | \bmusk\b | \bdoge\b | strafzöll\w* | \bzölle\b
"""

# ============================================================
# Bildungspolitik (neu) - wenig polarisierter Kontrast
# ============================================================

# Ueberschneidung mit Corona ueber "schulschliessung" gewollt.
_EDU_CORE = r"""
    bildungspolitik | bildungsminister\w* | bildungssystem\w* | bildungsnotstand
    | bildungsgerechtigkeit | schulpolitik | schulsystem\w* | schulreform\w*
    | lehrermangel | lehrkräftemangel | \bkita[- ]?(?:plätze|platz|krise|gebühren|ausbau|streik)\w*
    | kitaplatz\w* | pisa[- ]?(?:studie|ergebnis\w*|test\w*|schock)
    | \bbafög\b | digitalpakt | schulschließung\w* | ganztagsschule\w*
    | hochschulpolitik | studiengebühr\w*
"""
_EDU_WIDE = r"""
    lehrkräfte | lehrerverband | \babitur\w* | schulpflicht | homeschooling
    | kultusminister\w* | gesamtschule\w* | gymnasi\w* | bildungschancen
"""

# Pro Thema: prefix (fuer die KW_RE-/Flag-Schluessel, haelt die bestehenden
# Namen unveraendert - keine Re-Klassifizierung der alten Themen noetig),
# label (Klartextname fuer Tabellen/Grafiken) sowie die core/wide-Regexe.
TOPIC_KEYWORDS = {
    "russia_ukraine_war": {"prefix": "ukr", "label": "Ukraine-Krieg", "core": _UKR_CORE, "wide": _UKR_WIDE},
    "politics_general": {"prefix": "pol", "label": "Politik allgemein", "core": _POLITICS_CORE, "wide": _POLITICS_WIDE},
    "corona_pandemic": {"prefix": "corona", "label": "Corona/Pandemie", "core": _CORONA_CORE, "wide": _CORONA_WIDE},
    "migration": {"prefix": "migration", "label": "Migration", "core": _MIGRATION_CORE, "wide": _MIGRATION_WIDE},
    "economy_general": {"prefix": "econ", "label": "Wirtschaftspolitik", "core": _ECON_CORE, "wide": _ECON_WIDE},
    "energy": {"prefix": "energy", "label": "Energiepolitik", "core": _ENERGY_CORE, "wide": _ENERGY_WIDE},
    "climate": {"prefix": "climate", "label": "Klimapolitik", "core": _CLIMATE_CORE, "wide": _CLIMATE_WIDE},
    "gender": {"prefix": "gender", "label": "Gender/Identität", "core": _GENDER_CORE, "wide": _GENDER_WIDE},
    "mideast": {"prefix": "mideast", "label": "Naher Osten", "core": _MIDEAST_CORE, "wide": _MIDEAST_WIDE},
    "iran": {"prefix": "iran", "label": "Iran", "core": _IRAN_CORE, "wide": _IRAN_WIDE},
    "eu": {"prefix": "eu", "label": "EU-Politik", "core": _EU_CORE, "wide": _EU_WIDE},
    "usa": {"prefix": "usa", "label": "USA", "core": _USA_CORE, "wide": _USA_WIDE},
    "education": {"prefix": "edu", "label": "Bildungspolitik", "core": _EDU_CORE, "wide": _EDU_WIDE},
}


def _compile(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE | re.VERBOSE)


# {prefix}_{tier}: kompilierte Regex, ueber alle Themen hinweg - z.B.
# "ukr_core", "corona_wide", "iran_core".
KW_RE = {
    f"{cfg['prefix']}_{tier}": _compile(cfg[tier])
    for cfg in TOPIC_KEYWORDS.values()
    for tier in TIERS
    if tier in cfg
}

# Pro Thema ein eigener Versionsstring statt einem globalen - erlaubt,
# einzelne Themen unabhaengig neu zu klassifizieren, ohne die anderen
# ungewollt mit hochzuversionieren. Unveraenderte Themen behalten ihre
# bisherige Version.
KEYWORD_SET_VERSION = {
    "russia_ukraine_war": "ukr_core_wide_v1_2026-09-01",
    "politics_general": "pol_core_wide_v1_2026-10-05",
    "corona_pandemic": "corona_core_wide_v1_2026-09-09",
    "migration": "migration_core_wide_v1_2026-09-09",
    "economy_general": "econ_core_wide_v1_2026-09-09",
    "energy": "energy_core_wide_v1_2026-09-09",
    "climate": "climate_core_wide_v1_2026-10-05",
    "gender": "gender_core_wide_v1_2026-10-05",
    "mideast": "mideast_core_wide_v1_2026-10-05",
    "iran": "iran_core_wide_v1_2026-10-05",
    "eu": "eu_core_wide_v1_2026-10-05",
    "usa": "usa_core_wide_v1_2026-10-05",
    "education": "edu_core_wide_v1_2026-10-05",
}


def _tier_names(topic: str) -> list:
    return [t for t in TIERS if t in TOPIC_KEYWORDS[topic]]


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
    Da alle Einzel-Flags gespeichert werden, laesst sich eine core-only-
    Definition jederzeit nachtraeglich bilden.
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
"""
Titel-Muster zur Erkennung allgemeiner Nachrichtensendungen.

Markiert Videos, die eine ganze (Mehr-Themen-)Nachrichtensendung sind (z.B.
"tagesschau 20:00 Uhr, 07.10.2026", "heute journal vom 21.05.2026",
"Nachrichten des Tages | 12. Mai 2026 - Morgenausgabe"), damit sie von
Videos zu einzelnen Themen unterschieden werden koennen. Thematische
Sondersendungen (z.B. "tagesthemen extra", "ZDF spezial", "Sondersendung zum
Ukraine-Konflikt") werden getrennt markiert.

Kategorien (Rueckgabe von classify_title()):
    "nachrichtensendung" - allgemeine Nachrichtensendung / taeglicher
                           Mehr-Themen-Ueberblick
    "sondersendung"      - thematische Sondersendung bzw. themenspezifisches
                           taegliches Update (z.B. ntv "Ukraine Update")
    None                 - alles andere (Einzelthemen-Video)

Gedacht nur fuer long-Videos (video_format.format = 'long'); Shorts und
Livestreams werden nicht klassifiziert.

Grundregel der Muster: Ganze Sendungen beginnen mit dem Sendungsnamen (plus
Datum/Uhrzeit). Viele Kanaele haengen den Sendungsnamen aber auch als Suffix
an Einzelthemen-Clips an ("... | ARD Morgenmagazin", "... | DW Nachrichten",
"... | heute journal vom 07.05.2026", "... | BILD Live") - deshalb sind die
Sendungsmuster am Titelanfang verankert (^\\W* erlaubt fuehrende Emojis und
Anfuehrungszeichen). Ausnahmen, bei denen der Sendungsname am Ende steht,
die Titel aber Mehr-Themen-Aufzaehlungen sind (euronews am Abend, Handelsblatt
Morning Briefing, FAZ Fruehdenker), sind einzeln begruendet.

Kanaele ohne erkennbares Ganzsendungs-Format in den Titeln (Stand 2026-10-07,
Kanalliste data/channel_lists/video_formats/upload_starke_kanaele.csv):
DW Deutsch, WELT Nachrichtensender, phoenix - dort sind alle Sendungsnamen
Clip-Suffixe ("| DW Nachrichten", "| phoenix der tag | <Datum>"), daher keine
Eintraege in NEWS_SHOW_PATTERNS.

Zweite Kanalliste data/channel_lists/video_formats/alt_kanaele.csv (Stand
2026-10-07, geprueft auf video_format.format = 'long'):
  - Eintraege: Weltwoche (alle Folgen von "Weltwoche Daily", auch
    "<Leitthema> - Weltwoche Daily DE/CH" - per Transkript-Stichprobe
    bestaetigt: ganze Mehr-Themen-Folgen; dazu Titel mit "Hubis
    Bundeshaus"), Kontrafunk (Kontrafunk aktuell,
    Abendjournal, Wochenrueckblick), Deutschland Kurier und Hallo Meinung
    (Wochen-/Monats-/Jahresrueckblick, Presseschau), Oli ("Neues aus dem
    Irrenhaus"), Vermietertagebuch (Schlagzeilen-Ketten "A + B + C", Schwelle
    einstellbar, siehe PLUS_CHAIN_CHANNELS), DER AKTIONAER TV
    (Boersen-Ueberblicke "Maerkte am Morgen", "Opening Bell", "DAX-Check",
    "Ideas Daily", meistgehandelte Aktien - zaehlen bewusst als
    Nachrichtensendung) und FinanzmarktWelt ("Fugmann's Trading Woche").
  - Viele Treffer dieser Formate sind Livestreams (format = 'live', v.a.
    Aktionaer, Kontrafunk-Abendjournal, Oli) und fallen bei long-Analysen
    ohnehin heraus.
  - Unmarkiert: FinanzmarktWelt "Marktgefluester"/"Videoausblick" (nach
    Leitthema betitelt).
  - Ohne Ganzsendungs-Format: Aktien mit Kopf, Erfolgskanal, Martin Lejeune,
    Mathias von Gersdorff, Oli investiert, Politik & Co (nur
    Einzelthemen-Videos/Clips).

Offener Punkt (Stand 2026-10-07, bewusst zurueckgestellt): Talkshows werden
nicht erkannt und landen als None bei den Einzelthemen-Videos, obwohl sie oft
mehrere Themen behandeln. Betroffen sind ca. 1.900 long-Videos der
upload-starken Kanaele (~1 %): Markus Lanz (779) und maybrit illner (171) auf
ZDFheute; maischberger (651), Caren Miosga, Anne Will und hart aber fair auf
tagesschau; ntv Talk; Presseclub auf phoenix; WELT TALK SPEZIAL (das ntv-Muster
"talk spezial" steht derzeit unter SPECIAL). Lanz und maischberger laden
meist Gast-Segmente von ca. 20-30 min hoch, Illner und Presseclub ganze Folgen
von ca. 57 min mit einem Leitthema. Moegliche Erweiterung: eigene Kategorie
"talkshow" ueber den Sendungsnamen als Suffix (pro Kanal) und die
Unterscheidung ganze Folge vs. Clip in der Analyse ueber die Dauer (z.B.
>= 40 min) statt im Modul. Generische Begriffe wie "im Gespraech" oder
"Interview" nicht aufnehmen, weil sie v.a. phoenix-Kurzinterviews treffen.
"""

import re

NEWS = "nachrichtensendung"
SPECIAL = "sondersendung"

PATTERN_VERSION = "2026-10-07"

# channel_id -> {Kategorie: [Regex, ...]}. Alle Muster case-insensitive.
# SPECIAL wird vor NEWS geprueft (z.B. "tagesthemen extra 21:15 Uhr" enthaelt
# auch das NEWS-Muster "tagesthemen <Uhrzeit>").
NEWS_SHOW_PATTERNS = {
    # tagesschau
    "UC5NOEUbkLheQcaaRldYW5GA": {
        SPECIAL: [
            r"^\W*tages(schau|themen)[\s-]+extra\b",
            # nur als Sendungsname, nicht "Brennpunkt X | tagesthemen mittendrin"
            r"\|\s*(ard[\s-])?brennpunkt\s*$|^\W*(ard[\s-])?brennpunkt:",
            r"^\W*sondersendung\b",
        ],
        NEWS: [
            # "tagesschau 20:00 Uhr, 07.10.2026", "tagesthemen 22:15 Uhr, ..."
            # (?!\s*&): "tagesschau 20 Uhr & tagesschau24 Top-Thema | <Thema>"
            # ist ein Einzelthema
            r"^\W*tages(schau|themen)\s+\d{1,2}([:.]\d{2})?\s*uhr(?!\s*&)",
            r"^\W*tagesthemen,\s*\d",
            r"^\W*tagesschau in einfacher sprache\b",
        ],
    },
    # ZDFheute Nachrichten
    "UCeqKIgPQfNInOswGRWt48kQ": {
        SPECIAL: [
            # "brennpunkt" bewusst nicht: trifft nur auslandsjournal-Themen
            # ("Brennpunkt Kosovo - ... | auslandsjournal")
            r"\bzdf\s*(heute\s*)?spezial\b",
        ],
        NEWS: [
            # "heute 19:00 Uhr vom 04.03.2025 ...", "heute 19 Uhr vom ..."
            r"^\W*heute\s+\d{1,2}([:.]\d{2})?\s*(uhr\b|vom\b|v\.)",
            # "heute journal vom 21.05.2026 ...", ukrainische Fassung
            # "heute journal 12 квітня 2024 (українською)"; ausgenommen der
            # Einzelthemen-Podcast "heute journal - der podcast" und
            # "heute journal update"
            r"^\W*heute[\s-]journal\b(?!\s*-\s*(der\s+)?podcast)(?!\s*update)",
        ],
    },
    # euronews (deutsch)
    "UCACdxU3VrJIJc7ujxtHWs1w": {
        SPECIAL: [
            r"\beuronews spezial\b",
        ],
        NEWS: [
            # "Nachrichten des Tages | 12. Mai 2026 - Morgenausgabe"
            r"^\W*nachrichten des tages\b",
            # "Von Corona, Omikron und die Schweiz - Euronews am Abend am 03.12."
            # - Name am Ende, aber Mehr-Themen-Abendsendung
            r"\beuronews am abend\b",
            # Wochenrueckblick mit mehreren Themen
            r"^\W*die woche in europa\b",
        ],
    },
    # Handelsblatt
    "UCMpW4tdyZUid2Ka9_FuDDhQ": {
        SPECIAL: [
            # "Special zu den US-Zwischenwahlen", "US-Spezial zu ...",
            # "Today-Spezial zum Krieg ...", "Klima-Wahl-Spezial"; \b am Ende
            # schliesst "Spezialkraefte" etc. aus, (?!-) "Spezial-Schiffe"
            r"\bspe[cz]ial\b(?!-)",
        ],
        NEWS: [
            r"\bmorning briefing\b",
            # Morning-Briefing- und "Handelsblatt Today"-Folgen ohne bzw. mit
            # anderem Suffix: "Thema A / Thema B"
            r"^[^|:]{5,}\s/\s[^|]{5,}",
        ],
    },
    # faz
    "UCcPcua2PF7hzik2TeOBx3uw": {
        SPECIAL: [
            # "US-Wahl Spezial: ..."; (?!-) schliesst "Spezial-Schiffe" aus
            r"\bspezial\b(?!-)",
        ],
        NEWS: [
            r"\bfeierabendbriefing\b",
            r"\bfr(ü|ue)hdenker\b",
            # Fruehdenker-Folgen: "Thema A • Thema B • Thema C"
            r"\s•\s",
        ],
    },
    # ntv Nachrichten - keine Ganzsendungen, aber taegliche Einzelthema-Updates
    "UCSeil5V81-mEGB1-VNR7YEA": {
        SPECIAL: [
            r"^\W*ukraine update\b",
            r"^\W*український дайджест\b",
            r"^\W*pa?ndemie-?lage am\b",
            r"\btalk spezial\b",
        ],
    },
    # BILD
    "UC4zcMHyrT_xyWlgy5WGpFFQ": {
        SPECIAL: [
            r"\blagezentrum spezial\b",
            r"\bsondersendung\b",
        ],
        NEWS: [
            r"^\W*bild[\s-]news des tages\b",
            r"^\W*bild news\s*[–-]\s*der tag\b",
        ],
    },
    # ------------------------------------------------------------------
    # Kanalliste data/channel_lists/video_formats/alt_kanaele.csv
    # ------------------------------------------------------------------
    # DIE WELTWOCHE
    "UCq-b0dwW97YRZWgSCikWQRA": {
        SPECIAL: [
            # "Daily-Spezial: ...", "... - Daily Spezial, 08.03.2023",
            # "«Daily»-Spezial: ..."; nicht "Gstaad-Spezial" (Geschichtsreihe).
            # Ausgenommen "Hubis Bundeshaus" (teils als "Daily Spezial"
            # betitelt, ist aber eine Mehr-Themen-Sendung, siehe NEWS)
            r"^(?!.*\bhubis bundeshaus\b).*\bdaily\W{0,3}spezial\b",
            r"^\W*sondersendung\b",
        ],
        NEWS: [
            # 2021: "Weltwoche Daily, 09.04.2021", "Weltwoche Daily
            # Deutschland, 26.10.2021"
            r"^\W*weltwoche daily\b(?!\W{0,3}spezial)",
            # ab Ende 2021: "<Leitthema> - Weltwoche Daily DE/CH(, <Datum>)",
            # "... – «Weltwoche daily» DE". Laut Transkripten ganze Folgen mit
            # mehreren Themen (Begruessung "zur internationalen/schweizerischen
            # Ausgabe von Weltwoche Daily ... am <Datum>"), der Titel nennt
            # nur das Leitthema. Ausgenommen: Reihen unter demselben Suffix
            # (Meilensteine der Schweizer Geschichte, Zauberberg, Best of) und
            # "«Weltwoche daily»-Sprechstunde/-Spezial/-Botschaft" ((?!»?-))
            r"^(?!.*\b(meilensteine|zauberberg|best[\s-]of)\b).*[-–,]\s*«?(weltwoche|wewo) daily(?!»?-)",
            # Kurzform ohne "Weltwoche", dann nur mit Ausgabe: "... – Daily DE",
            # "... - Daily CH, 16.01.2024"
            r"^(?!.*\b(meilensteine|zauberberg|best[\s-]of)\b).*[-–,]\s*daily\s+(de|ch|deutschland|schweiz)\b",
            # "Hubis Bundeshaus" (ab 2023): Bundeshaus-Redaktor Hubert "Hubi"
            # Mooser bespricht mehrere Themen aus Bern ("<Thema> – Hubis
            # Bundeshaus", "Hubis Bundeshaus: ..."). Nur Titel mit dem
            # Sendungsnamen; "Hubi (Mooser) über <Thema>" bleibt
            # Einzelthema. "Best of" wie bei Daily ausgenommen.
            r"^(?!.*\bbest[\s-]of\b).*\bhubis bundeshaus\b",
        ],
    },
    # Kontrafunk
    "UCyH9w3VhfZPdjH28VFeoHUA": {
        SPECIAL: [
            # "Sondersendung zur Landtagswahl ...", "Sondersendung: Bomben
            # gegen Mullahs"; "Yoyogaga (Spezial)" etc. bewusst nicht
            r"\bsondersendung(en)?\b",
        ],
        NEWS: [
            # "KONTRAFUNK aktuell vom 12. März 2024", "Kontrafunk aktuell mit
            # Rommy Arndt"
            r"^\W*kontrafunk aktuell\b",
            # "🔴 18/20: Das Abendjournal – live mit ..."
            r"\bdas abendjournal\b",
            # "Wochenrückblick vom 5. Juli 2025", "KONTRAFUNK: Der
            # Wochenrückblick vom ..."
            r"\bwochenr(ü|ue)ckblick\b",
            # Kontrafunk-aktuell-Folgen ohne Sendungsnamen: "Marcel Joppa im
            # Gespräch mit A, B und C. Kommentar: ..." - nur mit Gaesteliste
            # (Komma), nicht Einzelinterviews ("Forum ...: X im Gespräch mit Y")
            r"^[^:]*\bim gespr(ä|ae)ch mit:?\s[^,:]+,",
        ],
    },
    # Deutschland Kurier
    "UCiTKi7Ahf3E2yMGpmIxSvgw": {
        SPECIAL: [
            # "DK-Spezial mit Tim Kellner: ...", "DK-Wahl-Spezial ..."
            r"\bdk-(\w+-)?spezial\b",
        ],
        NEWS: [
            # "Schröders Wochenrückblick: Sanierungspflicht, Mädchenmord und
            # Corona-Impfungen", "#SchrödersWochenrückblick", "Spaniels
            # Wochenrückblick", "... | Ein Wochenrückblick von Dirk Spaniel",
            # "Monatsrückblick-Messe", "Jahresrückblick 2024: ..."
            r"(wochen|monats|jahres)r(ü|ue)ckblick",
        ],
    },
    # Hallo Meinung
    "UCbanHTRuGv2Fi7flpO735yw": {
        SPECIAL: [
            # "Sondersendung: ...", "Eilt-Sondersendung- mit Peter Weber"
            r"sondersendung\b",
        ],
        NEWS: [
            # "Der HALLO MEINUNG Wochenrückblick KW 20/2022", "Maaßens
            # Wochenrückblick Ausgabe: 11 - ..."; nicht die kurzen
            # "Ankündigung:"/"Trailer"-Clips zu diesen Sendungen
            r"^(?!\W*(ankündigung|trailer)\b).*\bwochenr(ü|ue)ckblick\b",
            # "Aktuelles und Wissenswertes - Peters Presseschau"
            r"^(?!\W*(ankündigung|trailer)\b).*\bpresseschau\b",
        ],
    },
    # Oli
    "UCqZSdUJqd2T0oqr6BEA3ONw": {
        NEWS: [
            # woechentlicher Live-Nachrichtenkommentar (2021/22, ~60 min)
            r"^\W*neues aus dem irrenhaus\b",
            # "Deutschland hat FERTIG! 2 Wochen Nachrichten Rückblick!"
            r"\bnachrichten[\s-]?r(ü|ue)ckblick\b",
        ],
    },
    # Vermietertagebuch - Alexander Raue: Schlagzeilen-Ketten "A + B + C"
    # laufen nicht ueber Regex, sondern ueber PLUS_CHAIN_CHANNELS (unten),
    # damit die Schwelle fuer Robustheitschecks einstellbar ist.
    # DER AKTIONÄR TV - Boersen-Ueberblicksformate mit mehreren Werten
    "UC62IIFhchBWQxLPSyUatD-A": {
        SPECIAL: [
            r"^\W*sondersendung\b",
        ],
        NEWS: [
            # "Märkte am Morgen: Gold, Öl, Lufthansa, ...", "Opening Bell:
            # Bitcoin, Tesla, ...", "DAX-Check LIVE: Adidas, Bayer, ..."
            r"^\W*(m(ä|ae)rkte am morgen|opening bell|dax-check)\b",
            # "Ideas Daily TV: DAX legt leicht zu / Marktidee: Continental"
            r"^\W*ideas daily\b",
            # "BioNTech, BASF und Nordex - die meistgehandelten Aktien des Tages"
            r"\bmeistgehandelten aktien des tages\b",
        ],
    },
    # FinanzmarktWelt.de
    "UCsekpwdMv9PBCOftuuKncfw": {
        NEWS: [
            # Wochenueberblick "Fugmann's Trading Woche: Arbeitsmarktdaten,
            # Broadcom & Trump-Gerüchte"; die taeglichen "Marktgeflüster"/
            # "Videoausblick" sind nach Leitthema betitelt -> nicht markiert
            r"^\W*fugmann'?s trading woche\b",
        ],
    },
}

# Schlagzeilen-Ketten: Kanaele, deren Tages-Ueberblicke als "Meldung A +
# Meldung B + Meldung C" betitelt sind (Vermietertagebuch, ab 2025: "Angriff
# auf Moskau + Probleme mit Flamingo-Raketen + Merz heult wegen ...").
# Ein Titel gilt als NEWS, wenn er mindestens plus_chain_min " + " enthaelt.
# Default PLUS_CHAIN_MIN = 2 (= drei Meldungen), weil ein einzelnes "+" oft
# nur dasselbe Thema fortsetzt ("Brutaler Angriff ... + Seine Familie
# ebenfalls in Lebensgefahr!").
# ROBUSTHEITSCHECK: plus_chain_min=1 an classify_title()/classify_frame()
# uebergeben, dann zaehlt schon ein einzelnes "+" als Nachrichtensendung.
PLUS_CHAIN_CHANNELS = {
    "UCiTJladOHCMkKndVBsn23VQ",  # Vermietertagebuch - Alexander Raue
}
PLUS_CHAIN_MIN = 2
_PLUS = re.compile(r"\s\+\s")

_COMPILED = {
    channel_id: {
        cat: [re.compile(p, re.IGNORECASE) for p in pats]
        for cat, pats in cats.items()
    }
    for channel_id, cats in NEWS_SHOW_PATTERNS.items()
}


def classify_title(channel_id, title, plus_chain_min=PLUS_CHAIN_MIN):
    """
    Gibt NEWS, SPECIAL oder None fuer einen Videotitel zurueck. Kanaele ohne
    Eintrag in NEWS_SHOW_PATTERNS bzw. PLUS_CHAIN_CHANNELS liefern immer None.
    plus_chain_min: Mindestzahl " + " fuer Schlagzeilen-Ketten-Kanaele
    (Default 2; 1 fuer den Robustheitscheck, siehe PLUS_CHAIN_CHANNELS).
    """
    channel_id = str(channel_id)
    # isinstance statt "not title": fehlende Titel kommen aus pandas als NaN
    if not isinstance(title, str) or not title:
        return None
    cats = _COMPILED.get(channel_id, {})
    for cat in (SPECIAL, NEWS):
        if any(p.search(title) for p in cats.get(cat, ())):
            return cat
    if channel_id in PLUS_CHAIN_CHANNELS and len(_PLUS.findall(title)) >= plus_chain_min:
        return NEWS
    return None


def classify_frame(df, channel_col="channel_id", title_col="title",
                   plus_chain_min=PLUS_CHAIN_MIN):
    """Vektorisierte Variante: pd.Series mit NEWS/SPECIAL/None je Zeile."""
    return df.apply(
        lambda r: classify_title(r[channel_col], r[title_col], plus_chain_min),
        axis=1,
    )

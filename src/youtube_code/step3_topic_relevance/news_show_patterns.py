"""
Titel-Muster zur Erkennung allgemeiner Nachrichtensendungen.

Markiert Videos, die eine ganze (Mehr-Themen-)Nachrichtensendung sind (z.B.
"tagesschau 20:00 Uhr, 07.10.2026", "heute journal vom 21.05.2026",
"Nachrichten des Tages | 12. Mai 2026 - Morgenausgabe"), damit sie von
Videos zu einzelnen Themen unterschieden werden koennen. Thematische
Sondersendungen (z.B. "tagesthemen extra", "ZDF spezial", "Sondersendung zum
Ukraine-Konflikt") werden getrennt markiert, ebenso Pressekonferenzen und
Parlamentsformate (Kategorie "pressekonferenz", seit 2026-10-14).

Kategorien (Rueckgabe von classify_title(); Pruefreihenfolge SPECIAL ->
PRESSE -> NEWS):
    "nachrichtensendung" - allgemeine Nachrichtensendung / taeglicher
                           Mehr-Themen-Ueberblick
    "sondersendung"      - thematische Sondersendung bzw. themenspezifisches
                           taegliches Update (z.B. ntv "Ukraine Update")
    "pressekonferenz"    - Pressekonferenz, Regierungsbefragung/Fragestunde
                           oder ganzer Sitzungstag des Bundestags (Jung &
                           Naiv, Deutscher Bundestag, AfD-Fraktion). Ueber das
                           Format definiert, unabhaengig von der Zahl der
                           Themen; getrennt von NEWS, weil dort ueberwiegend
                           Dritte (Regierungssprecher, Abgeordnete) sprechen.
    None                 - alles andere (Einzelthemen-Video)

Die Muster haengen nicht von der Dauer ab, ob ganze Sendung oder Teaser
entscheidet allein der Titel. Teaser-Regel (seit 2026-10-14): Auch kurze
Videos/Shorts, deren Titel mehrere Meldungen aufzaehlt (z.B. Tichys "Der Tag
07.07.: CDU naehert sich LINKE an; gruene Prioritaeten; ..."), gelten als
NEWS. Die Muster der Kanalliste weitere_kanaele.csv sind auf allen Formaten
(short/long/live) geprueft, die der beiden aelteren Listen nur auf long-Videos
(offener Punkt: Teaser-Regel dort nicht nachgeprueft). LLM-Analysen filtern
ohnehin auf min_dauer == 1; Shorts/Teaser sind nur fuer View-Analysen relevant.

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

Dritte Kanalliste data/channel_lists/video_formats/weitere_kanaele.csv
(Stand 2026-10-14, Pruefskript scripts/adhoc/check_news_show_gruppe_a.py,
Transkript-Stichproben fuer Tichy, NIUS, Reichelt, Meinungsmache):
  - NEWS: Tichys Einblick (TE Wecker, "Der Tag"-Teaser), NIUS (nur "NIUS
    Schlagzeilen"), Achtung, Reichelt! (datierte Folgen), Meinungsmache
    ("Alle News", "NEWS:", Wochenausgaben), Kronen Zeitung ("A ++ B",
    Krone zu Mittag), hessenschau ("hessenschau vom <Datum>"), extra 3
    (ganze Folgen und Halbfolgen), Jung & Naiv (WIRTSCHAFTSBRIEFING,
    Aufwachen).
  - PRESSE: Jung & Naiv (BPK/RegPK), Deutscher Bundestag (Fragestunde,
    Befragung der Bundesregierung), AfD-Fraktion (BUNDESTAG LIVE,
    Regierungsbefragung, Pressekonferenzen).
  - Bewusst unmarkiert: "| NIUS Live"-Videos (long = Einzelthema-Segmente,
    ganze Sendungen nur als Livestream), Bundestags-Debatten zu einzelnen
    TOPs und Ausschusssitzungen.

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
PRESSE = "pressekonferenz"

PATTERN_VERSION = "2026-10-14"

# channel_id -> {Kategorie: [Regex, ...]}. Alle Muster case-insensitive.
# Pruefreihenfolge SPECIAL -> PRESSE -> NEWS: SPECIAL vor NEWS, weil z.B.
# "tagesthemen extra 21:15 Uhr" auch das NEWS-Muster "tagesthemen <Uhrzeit>"
# enthaelt; PRESSE vor NEWS, damit ein Format nie doppelt zaehlt.
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
    # ------------------------------------------------------------------
    # Kanalliste data/channel_lists/video_formats/weitere_kanaele.csv
    # (Stand 2026-10-14, geprueft auf allen Formaten inkl. Shorts, siehe
    # scripts/adhoc/check_news_show_gruppe_a.py)
    # ------------------------------------------------------------------
    # Jung & Naiv
    "UCv1WDP5EiipMQ__C4Cg6aow": {
        PRESSE: [
            # "20. Dezember 2021 - Regierungspressekonferenz | BPK", "... |
            # Komplette BPK", "22. Januar 2021 - Bundespressekonferenz | RegPK"
            # und thematische BPKs ("Scholz, Habeck & Lindner zum Haushalt |
            # BPK 5. Juli 2024"). Alle Treffer sind ganze Pressekonferenzen
            # (long/live, 27-100 min), Einzelfrage-Clips gibt es nicht.
            r"\b(bpk|regpk)\b|\b(bundes|regierungs)pressekonferenz\b",
        ],
        NEWS: [
            # "Sparanreize, Steuersenkung, Ticketfrust | WIRTSCHAFTSBRIEFING
            # #12 mit Maurice Höfgen" - Wochenueberblick, Titel zaehlt die
            # Themen auf; nicht "BRIEFING OST" (Einzelanalyse)
            r"\bwirtschaftsbriefing\b",
            # "Aufwachen #458: Bauernproteste, Hochwasser & Schäuble" -
            # Nachrichten-Podcast mit Themenliste. Die Interviews "Jung &
            # Naiv: Folge N" bleiben unmarkiert.
            r"^\W*aufwachen\s*#\s*\d",
        ],
    },
    # Tichys Einblick
    "UCB37CFICVTUlewYdbMSChIA": {
        SPECIAL: [
            # "Bundesverfassungsgericht: ... - TE Wecker Spezial"
            r"\bte[\s-]?wecker spezial\b",
        ],
        NEWS: [
            # "<Leitthema> - TE Wecker am 21 02 2023", "TE-Wecker 21. März
            # 2025". Der Titel nennt nur das Leitthema; laut Transkripten
            # ganze Morgennachrichten mit mehreren Meldungen ("ich begrüße Sie
            # zum TE Wecker, den Morgennachrichten von Tichys Einblick am
            # Montag 12. Mai ..." bis zum Energiewende-Wetterbericht). Ohne
            # \b am Ende wegen "TE Wecker08 03 2025", "TEWecker am ...".
            r"\bte[\s-]?wecker",
            # Shorts "Der Tag 07.07.: CDU nähert sich LINKE an; grüne
            # Prioritäten; Andi Scheuer ..." (Mehr-Themen-Teaser). Nicht
            # "<Thema> | Der Tag bei Tichys Einblick" (Einzelthema-Clip).
            r"^\W*der tag \d",
            # Themenlisten "A | B | C" (Shorts 2023/24, meist "... | Der Tag
            # bei TE", und einzelne TE-Wecker-Titel); nicht "Redaktionsschluss
            # mit David Boos" (Kommentar, ungeprueft)
            r"^(?!.*\bredaktionsschluss\b)[^|]+\|[^|]+\|",
        ],
    },
    # NIUS - "<Thema> | NIUS Live (am Abend) vom <Datum>" bewusst NICHT
    # markiert: Ganze Sendungen sind nur die Livestreams (format = 'live',
    # 60-120 min); die ~1.230 long-Videos mit demselben Suffix (Median 17 min)
    # sind laut Transkripten Einzelthema-Segmente ("darueber sprechen wir
    # jetzt bei NIUS Live") und lassen sich per Titel nicht von den ganzen
    # Sendungen trennen. "Breaking NIUS" leitet nur die Live-Sendung ein.
    "UCQGqiGhMjc_p4lZEhSTb12g": {
        SPECIAL: [
            # "Das steht alles im schwarz-roten Koalitionsvertrag | NIUS Live
            # Spezial am 10. April 2025", "NIUS Live am Abend Spezial:
            # Rauchwolken und Explosionen in Teheran". Nicht "NIUS Live
            # Sommer/Winter Spezial" (Sommerpause-Clips zu Einzelthemen).
            r"\bnius live (am abend )?spezial\b",
        ],
        NEWS: [
            # "<Leitthema> | NIUS Schlagzeilen" (ab 2026, ~20-28 min): laut
            # Transkripten mehrere Meldungen ("Und hier sind die Schlagzeilen
            # des Tages", "Unser erstes Thema ...")
            r"\bnius[\s-]schlagzeilen\b",
        ],
    },
    # Achtung, Reichelt!
    "UCcoQ3WG2J_Xjwwyt-sJqh-w": {
        NEWS: [
            # "<Leitthema> | Achtung, Reichelt! vom 13. Juli 2023", "... |
            # Achtung, Reichelt! 23.06.25", "... | AR, 17.02.25". Ganze Folgen
            # ("Herzlich willkommen bei Achtung, Reichelt!" ... "Das war
            # Achtung, Reichelt!", ~18 min). Kommentarsendung mit Leitthema
            # und meist weiteren Themen; einzelne Folgen haben nur ein Thema
            # (z.B. Weihnachtsansprache). Folgen ohne Datum im Titel (v.a.
            # 2022/23) lassen sich nicht von anderen Videos trennen und
            # bleiben unmarkiert.
            r"achtung,?\s*reichelt!?,?\s*(vom\s*)?\d",
            r"\|\s*ar,?\s*\d",
        ],
    },
    # Meinungsmache
    "UCOOc_k7pKmmjq8qtGLjBW5A": {
        SPECIAL: [
            # "... | Meinungsmache Spezial", "💥 SPECIAL: Die Denkfehler der
            # Rechten EXPOSED", "... | Brexit Spezial", "XXL-Schuldenspezial:
            # ..." - Einzelthemen-Reactions/Sonderfolgen. Ohne \b am Anfang
            # wegen der Komposita; (?!-) wie bei Handelsblatt/FAZ.
            r"spe[cz]ial\b(?!-)",
        ],
        NEWS: [
            # "<Leitthema> | Alle News vom 22.03.", "... | Alle News aus
            # #KW38", "... | Alle News der Woche #KW44", "... | Alle News
            # #KW47", "... | Meinungsmache News #KW30", "... | News vom 25.03."
            r"\bnews (vom|aus|der woche)\b",
            # 2023 Wochenausgaben "... | NEWS KW32", "... #KW36" (~50 min)
            r"#?\s*\bkw\s?\d",
            # 03-09/2025 Themenlisten mit Zeitungs-Emoji bzw. "& mehr":
            # "Verblendete AfD-Wähler, Rezession in den USA & Grüne gegen
            # Sondervermögen! 📰", "Russische Spione angeklagt 🕵️‍♂️ Merz für
            # Taurus-Lieferungen 🇺🇦 & mehr"
            r"📰|&\s*mehr\b",
            # ab 10/2025 "🗞️ NEWS: <Leitthema>": laut Transkripten dasselbe
            # Format ("Wir haben heute den 7.1.2026. Der erste Artikel ...
            # Das waren die Nachrichten.")
            r"^\W*news:",
        ],
    },
    # Kronen Zeitung - Schlagzeilen-Ketten "A ++ B" (krone.tv PUSH, NEWS, NEWS
    # SHOW, "Krone News, <Datum>: A ++ B", Krone zu Mittag; 3-55 min). Schon
    # ein "++" trennt zwei Meldungen; Shorts tragen kein "++". Die 1-min-Clips
    # "<Thema> | krone.tv NEWS" bleiben unmarkiert.
    "UC4qhj5cnX0MkbwXQ5vlI1NQ": {
        NEWS: [
            r"\+\+",
            # "Krone zu Mittag" (~53 min) ohne "++": Themenliste vor dem
            # Suffix ("Großbrand, Schlagerstar Simone & WM Esel „Sunny“ |
            # KRONE ZU MITTAG") bzw. Sendungsname am Anfang. Ohne Doppelpunkt
            # in der Themenliste, weil die Einzelsegmente desselben Suffixes
            # ("Astro-Astrid im Talk: Uranus & Co | krone.tv ...") so betitelt
            # sind. Ganze Folgen mit nur einer Schlagzeile ("Naher Osten
            # versinkt im Kriegs-Chaos | KRONE ZU MITTAG") fehlen dadurch.
            r"^[^:|]*(,|\s(und|&)\s)[^:|]*\|.*\bkrone zu mittag\b",
            r"^\W*krone zu mittag\b",
        ],
    },
    # hessenschau
    "UCPhsnKyNcH3huafz_wNG_5A": {
        SPECIAL: [
            # "Corona-Weihnachten 2.0 | hessenschau extra"
            r"\bhessenschau extra\b",
        ],
        NEWS: [
            # "<Leitthema> | hessenschau vom 02.06.2022" - anders als bei der
            # heute-show ganze Sendungen (alle Treffer 20-35 min). Die
            # Einzelbeitraege enden auf "| hessenschau" ohne Datum.
            r"\bhessenschau vom\b",
        ],
    },
    # extra 3 (Satire, NDR)
    "UCjhkuC_Pi85wGjnB0I1ydxw": {
        NEWS: [
            # ganze Folgen 2021-2023: "Extra 3 vom 02.06.2021 im NDR"
            r"^\W*extra 3 vom\b",
            # 2022-2025 "Linke Spaltungen, lahme Ampel & Scheuers Maut-Fiasko |
            # extra 3 vom 10.08.2023 | NDR" (13-24 min) und ab 08/2025 Halb-
            # folgen "... | extra 3 vom 11.12.2025 · Teil 1/2" (~22 min):
            # grosse Teile einer Folge mit mehreren Themen (2023 auch kuerzere
            # Eroeffnungsbloecke von 8-13 min, per Titel nicht trennbar).
            # Ausgenommen sind
            # die Einzelsegmente "... | extra 3 vom 31.10.2024 · Teil 3"
            # (Teil 1-5 ohne "/n", ~9 min, je ein Thema), "Realer Irrsinn"
            # und die Clips "| extra 3 | NDR".
            r"\bextra 3 vom\b(?!.*\bteil \d+\b(?!\s*/))",
        ],
    },
    # Deutscher Bundestag - die meisten Videos sind Debatten zu einem
    # Tagesordnungspunkt ("59. Sitzung vom 26.02.2026. TOP 14: Abschaffung der
    # Grundsteuer") oder Ausschusssitzungen und bleiben unmarkiert.
    "UCbh5D3EdIHP4YQA5X-eK1ug": {
        PRESSE: [
            # "Fragestunde am 5. Mai", "67. Sitzung vom 25.03.2026. TOP 2:
            # Fragestunde"
            r"^\W*fragestunde\b|\btop \d+:\s*fragestunde\b",
            # "TOP 1: Befragung der Bundesregierung (BMVg und BMG)". Aeltere
            # Regierungsbefragungen sind nach Inhalt betitelt ("Helge Braun
            # äußert sich zu Digitalprojekten, Klimaschutz und Corona") und
            # fehlen; "Einfach erklärt: Die Regierungsbefragung" ist kein
            # Treffer.
            r"\bbefragung der bundes\W*regierung\b",
        ],
    },
    # AfD-Fraktion Bundestag
    "UC_dZp8bZipnjntBGLVHm6rw": {
        PRESSE: [
            # "BUNDESTAG LIVE - 224. Sitzung - AfD-Fraktion im Bundestag",
            # "BUNDESTAG LIVE - Große Generaldebatte ...", "Scholz im
            # AfD-Kreuzverhör! - BUNDESTAG LIVE - 114. Sitzung", "SCHOLZ STELLT
            # VERTRAUENSFRAGE LIVE - 205. Sitzung" (ganze Sitzungstage, fast
            # nur live)
            r"\bbundestag live\b|\blive - \d+\. sitzung\b",
            # "Regierungsbefragung: Robert Habeck im AfD-Kreuzverhör",
            # "AfD-Fraktion grillt Habeck und Schulze! - Regierungsbefragung",
            # "Kanzlerbefragung: AfD-Fraktion grillt Bundeskanzler Merz!"
            # (Zusammenschnitte der AfD-Fragen, 10-18 min)
            r"\b(regierungs|kanzler)befragung\b",
            # "LIVE: Pressekonferenz der AfD-Fraktion - Diese Woche im
            # Bundestag!", "Pressekonferenz: Albrecht Glaser zur
            # Wahlrechtsreform", "PK mit Tino Chrupalla"; nicht
            # "Pressestatement"/"Presseerklärung" (Erklaerungen der
            # Fraktionsspitze, 10-40 min) und "Bürgerdialog"
            r"\bpressekonferenz\b|\bpk mit\b",
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
    Gibt SPECIAL, PRESSE, NEWS (in dieser Pruefreihenfolge) oder None fuer
    einen Videotitel zurueck. Kanaele ohne
    Eintrag in NEWS_SHOW_PATTERNS bzw. PLUS_CHAIN_CHANNELS liefern immer None.
    plus_chain_min: Mindestzahl " + " fuer Schlagzeilen-Ketten-Kanaele
    (Default 2; 1 fuer den Robustheitscheck, siehe PLUS_CHAIN_CHANNELS).
    """
    channel_id = str(channel_id)
    # isinstance statt "not title": fehlende Titel kommen aus pandas als NaN
    if not isinstance(title, str) or not title:
        return None
    cats = _COMPILED.get(channel_id, {})
    for cat in (SPECIAL, PRESSE, NEWS):
        if any(p.search(title) for p in cats.get(cat, ())):
            return cat
    if channel_id in PLUS_CHAIN_CHANNELS and len(_PLUS.findall(title)) >= plus_chain_min:
        return NEWS
    return None


def classify_frame(df, channel_col="channel_id", title_col="title",
                   plus_chain_min=PLUS_CHAIN_MIN):
    """Vektorisierte Variante: pd.Series mit NEWS/SPECIAL/PRESSE/None je Zeile."""
    return df.apply(
        lambda r: classify_title(r[channel_col], r[title_col], plus_chain_min),
        axis=1,
    )

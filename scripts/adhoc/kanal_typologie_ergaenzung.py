"""Kanaltypologie für die Nicht-Whitelist-Kanäle der Stichprobe (einmalig, 2026-10-15).

Ergänzt die manuelle Typologie (``data/external/channels.xlsx`` bzw.
``data/external/kanal_typologie.csv``, 279 Whitelist-Kanäle) um die übrigen
158 Kanäle aus ``data/samples/russia_longitudinal_v1/channel_sample_provenance.csv``.

Grundlage je Kanal: Kanalbeschreibung, Abonnentenzahl und eine Zufalls-
stichprobe von Videotiteln aus ``data/store/video_registry.sqlite``. Es gelten
dieselben Zuordnungsregeln wie in ``kanal_typologie_grenzfaelle.py``
(überwiegender Inhalt entscheidet; B4 nur mit Mandat/Partei/Organisation;
B1 Marke/mehrere Köpfe vs. B2 Einzelperson; B3 ohne identifizierbare Person,
auch Pseudonym-Kommentarkanäle ohne Impressumsperson; C1 bei Finanzbezug als
rotem Faden). Zusätzliche Präzedenzfälle aus der bestehenden Typologie:
  - Kabarettisten/Comedians mit eigenem Kanal (Somuncu, Maschek) -> C3;
    nur Formate etablierter Häuser (inkl. funk) -> A6.
  - funk-Formate -> A5 (Doku/Talk) bzw. A6 (Satire/Comedy).
  - A0 (lokaler/regionaler ÖRR, neu in channels.xlsx) kommt unter den
    158 Kanälen nicht vor.
  - Kinderkanäle werden wie in channels.xlsx (logo!) mit Anmerkung
    "Ausschließen, Kinderkanal" markiert.

Ausgabe: ``data/external/kanal_typologie_ergaenzung.csv`` im Schema von
``kanal_typologie.csv`` (medientyp_label aus media_type_russia_merged.xlsx,
leer falls dort nicht codiert). Die Datei wird NICHT von
``export_stata_rohdaten.py`` gelesen.

Am 2026-10-15 wurden die 158 Zeilen einmalig (nicht durch dieses Skript)
an die Tabelle in ``channels.xlsx`` angehängt, zusammen mit den Spalten
subtyp/organisationsform/sicherheit für alle Kanäle. Seitdem ist
``channels.xlsx`` die führende Arbeitsdatei für die Typologie.

Aufruf:  python scripts/adhoc/kanal_typologie_ergaenzung.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EXTERNAL = ROOT / "data" / "external"
PROVENANCE = ROOT / "data" / "samples" / "russia_longitudinal_v1" / "channel_sample_provenance.csv"
CHANNELS_XLSX = EXTERNAL / "channels.xlsx"
MEDIENTYP = EXTERNAL / "media_type_russia_merged.xlsx"
OUT = EXTERNAL / "kanal_typologie_ergaenzung.csv"

TYP_LABEL = {
    "A0": "Etablierte Nachrichten – öffentlich-rechtlich regional",
    "A1": "Etablierte Nachrichten – öffentlich-rechtlich",
    "A2": "Etablierte Nachrichten – privat",
    "A3": "Etablierte Nachrichten – privat regional/lokal",
    "A4": "Staatlicher/internationaler Auslandsrundfunk",
    "A5": "Etablierte Medien – Magazin, Reportage, Doku",
    "A6": "Etablierte Medien – Satire & Comedy",
    "A7": "Etablierte Medien – Unterhaltung, Sport, Kinder",
    "A8": "Etablierte Medien – Senderhauptkanal (Mischprogramm)",
    "B1": "Alternative Nachrichten- & Meinungsportale",
    "B2": "Politische Einzelkommentatoren & Journalisten-Creator",
    "B3": "Anonyme politische Content-Kanäle",
    "B4": "Politische Akteure: Parteien, Politiker, Institutionen, Organisationen",
    "C1": "Wirtschaft & Finanzen",
    "C2": "Wissen, Bildung, Recht, Technik",
    "C3": "Unterhaltung, Reaction, Streamer, Interview-Podcasts",
    "C4": "Lifestyle, Coaching, Esoterik & Themenfremdes",
}
# Rohcodes media_type_russia_merged.xlsx -> Label (wie export_stata_rohdaten.py)
MEDIENTYP_LABEL = {1: "ÖRR", 2: "traditionelle Medien", 3: "Creator & alternative Medien",
                   4: "Partei/Politiker", 5: "ÖRR"}

KIND = "Ausschließen, Kinderkanal"
EP, OERR, PM, AMU, UN, AN, POL = ("Einzelperson", "ÖRR", "Privates Medienhaus",
                                  "Alternatives Medienunternehmen", "Unternehmen", "Anonym",
                                  "Politiker/Partei")

# channel_id: (typ_code, subtyp, organisationsform, sicherheit, anmerkung)
TYPOLOGIE = {
    "UCYJ61XIK64sp6ZFFS8sctxw": ("C3", "Gaming/Let's Play", EP, "hoch", None),
    "UCDW1yldFKWrfjrr78aP5Nkw": ("C3", "Interview-/Begegnungsformat", EP, "mittel", "bis 03/2023 funk-Format (dann A5), danach eigenständig"),
    "UCo6utge9KpJI61gXe7ngUJQ": ("C3", "Streamer-Highlights (MontanaBlack)", UN, "hoch", None),
    "UCQU3PO2g_rmqbmr8VJWvrsA": ("A7", "Kinderprogramm", PM, "hoch", KIND),
    "UCyHDQ5C6z1NDmJ4g6SerW8g": ("A5", "Wissenschaftsformat (funk/ZDF)", OERR, "hoch", None),
    "UCL5-tPmf_sttES7ZcYJRp5A": ("C3", "Show/Unterhaltung", EP, "mittel", "ab 08/2024 Seven.One-Produktion"),
    "UCr78AIw8O_HGs2jMUAGEp_g": ("C3", "Reaction/Influencer-Drama", EP, "hoch", None),
    "UCZX_5XCRE_dZ_4tNXOEYtog": ("A7", "Lifestyle-/Boulevardmagazin (ProSieben)", PM, "hoch", None),
    "UCIk-Fw1QuWJdO4sAxhXE5DA": ("C3", "Infotainment/Kuriositäten", UN, "mittel", None),
    "UC267Hlq_ACFuWzZYfazrDGQ": ("C3", "Streamer/Reaction", EP, "hoch", None),
    "UC4gENfIXqpg-CCVN7felClg": ("A7", "Kinderprogramm (RTL)", PM, "hoch", KIND),
    "UCOiG4UoE0-CBZKlDVgw1eTA": ("C3", "Musik (Band SDP)", UN, "mittel", None),
    "UCoKCF-pUbhJtSsSGs6JCLfQ": ("C3", "Reaction (Rezo-Zweitkanal)", EP, "hoch", None),
    "UCDbDbm3v-MAqL4IPR2wIA9A": ("C3", "Musikmedium Deutschrap", UN, "hoch", None),
    "UCOQFfcGRc886dXP2Oyt5OEg": ("B2", "Kommentar/Polit-Reaction (rechts)", EP, "hoch", None),
    "UCeWYsa2ynPc0VNwqL-vF2wQ": ("A5", "Reportage (funk/ZDFinfo)", OERR, "hoch", None),
    "UCol-Re86up3bOE6HRR6ePMQ": ("C4", "Lifestyle-Vlog", EP, "hoch", None),
    "UCEtYtMoD26j2BJBJ4w_hM6w": ("C4", "Drogen/Bewusstsein/Verschwörungsthemen", EP, "mittel", None),
    "UCfnNah9Q-A2OzcbqeZQiFhQ": ("C3", "Streamer-Highlights/Reaction", EP, "hoch", None),
    "UCB0H51gtgcpgYGI7LgflNJw": ("B2", "Satire/Polit-Reaction (Marc-Philipp Längert)", EP, "hoch", None),
    "UCu02GkFNrMRzwysT2SEmNrQ": ("C1", "Steuern (Steuersoftware)", UN, "hoch", None),
    "UCMbiTMFu2Sm06aiKbxQ3ibg": ("B2", "Satire/Undercover gegen rechts", EP, "mittel", "Mix aus Politik und Influencer-Themen"),
    "UCKZmirEl03pmXEwsFYjr87Q": ("C3", "Unterhaltung/Wochenshow", EP, "hoch", None),
    "UC6zXbTQEujMO-5CzyywlVDQ": ("A6", "Politsatire (Produktion für ZDF/funk)", UN, "mittel", None),
    "UCaWbn671XbI1GLTgndyI7gQ": ("C2", "Technik/Energiewende (PV, Speicher)", EP, "hoch", None),
    "UC7HpbItjae9vGSvO5bYDU3w": ("C2", "Musikunterricht", EP, "hoch", None),
    "UCE0rCXRjJkY3Pro4rm8NINQ": ("C3", "Musikkabarett", EP, "hoch", None),
    "UCt-LS-iOO2Aultxo2gtHA4g": ("C1", "Finanzen/Aktien/Steuern", EP, "hoch", None),
    "UC6eKQpThuLPOHAf_EPyB3xw": ("C4", "Fitness/Comedy", EP, "hoch", None),
    "UCueJOpg1SG9mahPjhALlvJw": ("A6", "Stand-up-Comedy (ARD)", OERR, "hoch", None),
    "UCwIOCxPAbHdcQ7bgOneCu1Q": ("A7", "Spielfilm-Clips (Rialto Film)", UN, "mittel", None),
    "UCq880QL0THPePYuGKV7PxZw": ("B2", "Satire/Polit-Kommentar", EP, "mittel", "früher Unterhaltung, zunehmend Politik"),
    "UCtg17AAUcgsfmTZ7cOojgpA": ("C1", "Investieren/Motivation", EP, "mittel", None),
    "UC2n9cj1SR8lXPnNjmFl2BBw": ("B3", "Viral-/Nachrichtenclips", AN, "mittel", "Mix aus Viralclips und Politik"),
    "UC4mTAdfgY48VtPSXVWTC9wQ": ("C4", "Elternschaft/Familie", EP, "hoch", None),
    "UCjM_J6nYvaRx3rZMxkilwLw": ("C3", "Unterhaltung/Shorts", EP, "hoch", None),
    "UCFoKXoDoExwtBWdSTCIdEVQ": ("A5", "Auslandsmagazin (ARD)", OERR, "hoch", None),
    "UCIIVvAp6DP3a2MmoIuIjvQA": ("C3", "Satire-Nachrichten", UN, "mittel", "unabhängige Satiremarke, kein etabliertes Haus"),
    "UCGZLruV9OMz7JnmXz86ELdg": ("C4", "Autohandel", UN, "hoch", None),
    "UCSFnRsoF9zANc6_s96yCw5w": ("A6", "News-Comedy für Teens (ZDF)", OERR, "mittel", "Zielgruppe Teens (Ableger von logo!)"),
    "UCf4YizfEQiftTFR4qbvb5Qw": ("A6", "Sketch-Comedy (Sat.1)", PM, "hoch", None),
    "UC6rdE0CWPOZBJdM-b5Yk-Yg": ("C3", "Musik/Comedy", EP, "hoch", None),
    "UCVUYh7UEdKW8v3cPIDA4Iow": ("C1", "Immobilien/Vermögensaufbau", UN, "hoch", None),
    "UCOgPGtSnFR6GM-AkzCnxqMQ": ("A5", "funk-Hauptkanal (gemischt)", OERR, "hoch", None),
    "UCDzjkX1p0DNmy6Mt4s29dUw": ("C3", "Reaction (TJ-Zweitkanal)", EP, "hoch", None),
    "UCtnSmfVH1brwwMk8JYmYPvw": ("C3", "Spielfilme/Serien", AN, "hoch", None),
    "UCBAj8YKmLRd8yyGFM9lwuXw": ("C2", "Geschichte/Doku Berlin", UN, "mittel", None),
    "UCrGy59kaH785Ac6KIl2y65A": ("B3", "Clips/Kompilation (rechts)", AN, "hoch", None),
    "UCjuV53YnSHDfltUSGW3Q0KA": ("C2", "Recht (Einbürgerung, Kanzlei)", UN, "hoch", None),
    "UCZOM0CqaJ5njZB_O-RyQSsw": ("A5", "Investigativ/Reportage (MDR)", OERR, "hoch", None),
    "UCycuPgtpxdu_6-1nVXgzPmg": ("B1", "Kommentar/Interview-Plattform", AMU, "mittel", "Marke um Thomas Langemann"),
    "UCjzcAEdtPjSo3hRrhVnVaQg": ("A6", "Comedy-Archiv (MySpass)", PM, "hoch", None),
    "UC19tEGPtxdnSMZnoqYUVvzA": ("C2", "Technik/Werkzeugtests", EP, "hoch", None),
    "UCUnxR8x1hsw2Zt35-P-slsw": ("C4", "Esoterik/Spiritualität", EP, "hoch", None),
    "UCO-mUnAn9Ezgh7XXi-gGvxA": ("C2", "Technik (iPhone)", UN, "hoch", None),
    "UC_cCcxd8yUwIu1-rt5dpBdw": ("C2", "Nachhilfe/Bildung", UN, "hoch", None),
    "UCXSknWhye34DTvq-oYcAlSg": ("C4", "Karriere-Coaching", EP, "hoch", None),
    "UChkELlk5GBaUCVx8-94IK_Q": ("B1", "Alternativer TV-Sender", AMU, "hoch", None),
    "UCT87TG9Rt5ThxMfAkjAJznw": ("A5", "Talk (funk)", OERR, "mittel", None),
    "UCBkfxC056lxHJ6QMUCKZHJw": ("B2", "Kommentar (Nahost/Gesellschaft)", EP, "mittel", "Mix mit Influencer-Drama"),
    "UC4V1z5uOPGL0FodEEScHd8g": ("C3", "Rap-News", EP, "hoch", None),
    "UC-5Ao5j48FBONkfprK1m5YA": ("C3", "Comedy-Interview mit Politikergästen", UN, "mittel", None),
    "UCgmB8S3f8-9dR8alVUZuZxQ": ("C2", "Technik (E-Mobilität)", UN, "hoch", None),
    "UCChHIg4Mp_k8_Wp8js6NQow": ("B3", "Clips/Kompilation (AfD-Fokus)", AN, "hoch", "Beschreibung (Finanzen) passt nicht zum Inhalt"),
    "UCx80Q7lPqzfWBRIrQ-97f3g": ("A6", "Comedy-Talk (funk)", OERR, "mittel", None),
    "UCBEbuDZ0EQWrEMd87c3rc1A": ("C4", "Trucker-Vlog", EP, "mittel", "gelegentlich politische Klartext-Videos"),
    "UCFFM_g9QSjmE45y9XtfYLdw": ("C4", "Autotuning", UN, "hoch", None),
    "UCgJ0yIYRJT13BPtQdagWORA": ("B1", "Doku/Interview-Plattform (NuoViso)", AMU, "hoch", None),
    "UCxeay89YP9XbhLNC3Zd_9cA": ("C4", "Themenfremdes (gemischt)", AN, "hoch", None),
    "UC5QXyeVn0LD-2ydrr_Owe4A": ("B3", "Gesellschaftskritik/Satire", AN, "mittel", "Pseudonym ohne Impressumsperson"),
    "UCh8EqZyAUunyl1ryHeZAaSw": ("C1", "Krypto/Bitcoin", EP, "hoch", None),
    "UCR2r-x-wLNCl957sh2-Lplw": ("C3", "Reaction/Influencer-Drama", EP, "mittel", "teils anti-woke Kommentar"),
    "UCQz0thmRLbm2mVDJwmVjsOg": ("C4", "Unternehmenskanal (Energie)", UN, "mittel", None),
    "UCXTTZIvh1UAlf0kv6XHvOtg": ("B2", "Kommentar/Live (Freiheit, Krise)", EP, "mittel", "Mix mit Selbstoptimierung/Auswandern"),
    "UCfWebHklGjJLdh4SgMVWkwg": ("C3", "Gaming", EP, "hoch", None),
    "UC1cQzKmbx9x0KipvoCt4NJg": ("A5", "Politmagazin (WDR/ARD)", OERR, "hoch", None),
    "UCGs4xGAYB_qSoWJ9EsPAKAQ": ("C4", "Kochen/Garten", EP, "hoch", None),
    "UC70-qPE5cS_aOYAOGnM_24g": ("C1", "Versicherungen", UN, "hoch", None),
    "UCxi2edl6w4Dr1-SK8CgnvKQ": ("B3", "News-Aggregator (Geopolitik/Russland)", AN, "hoch", None),
    "UC39NWHuZJnbL2yBidzlJfZQ": ("C3", "Reaction/Influencer-Drama", UN, "hoch", None),
    "UCMW8XBBRkjrF_fweALWaZyw": ("C2", "Technikjournalismus", EP, "hoch", None),
    "UCd1uEp8YZkV-soNnMstlqTg": ("C3", "Interviews (Reality-TV-Milieu)", EP, "hoch", None),
    "UCCymCsB5DpL5YydF5q_LudA": ("A6", "Late-Night-Comedy (ProSieben)", PM, "mittel", None),
    "UCE5CMv3a2bF7UTDdvjuenoA": ("B1", "Polit-Livestream (Duo)", EP, "mittel", "zwei Hosts -> B1 nach Regel 'mehrere Köpfe'"),
    "UCDG7fluFPCLOmFz_Rhc3cXw": ("B2", "Kommentar (Professor, Corona/Finanzpolitik)", EP, "hoch", None),
    "UCSiR8kjXDgvKh0Reuuj5Dgw": ("C3", "Reaction/Reality-TV", EP, "mittel", "gelegentlich Politik"),
    "UCex-tVEkNsXHikRB3RGKucA": ("A6", "TV-Satire (Kalkofe)", UN, "mittel", "Mattscheibe lief bei Tele 5/ProSieben"),
    "UCkDNRaTUFuWBRDr7lDETSkw": ("B4", "Politiker (AfD, MdL Sachsen-Anhalt)", POL, "hoch", None),
    "UCXdfGoYTQq5eQXP6OJwWSQw": ("B2", "Polit-Kommentar", EP, "hoch", None),
    "UC9wj8KPMMTnZyk0lFGlnicg": ("C4", "Bodybuilding", EP, "hoch", None),
    "UCgZw_Rxf1RYKDtQr9zdYuwg": ("C3", "Gaming/Streamer", EP, "hoch", None),
    "UCw-SjGVT0HK7czJkLgdv3Fw": ("A6", "Comedy-Show (ARD)", OERR, "hoch", None),
    "UCgcHsYmYWTmLBU034YVSSIA": ("B1", "Personality-Format (NIUS)", AMU, "mittel", "redaktionell betreut, NIUS-Umfeld"),
    "UCc2PueJVrynVhKB99Z0-jew": ("C1", "Steuern/Rente", EP, "hoch", None),
    "UCscq7owVpBCr1w3LQO1aGEw": ("B3", "Shorts-Kompilation (Politik/Motivation)", AN, "mittel", None),
    "UC0gowAwNIqEOMVSuXdJHJOw": ("B4", "Politiker (AfD, MdB)", POL, "hoch", None),
    "UC8TsX50arK9Ap1oNIBQmQgw": ("C4", "Kinder-Zeichentrick", UN, "hoch", KIND),
    "UCGVAL_wYwXMHLLYR_ER2bwg": ("C3", "Streamer-Highlights (Rap/Gossip)", EP, "hoch", None),
    "UCcUREIs52XlMUz7cDuu-mTg": ("B3", "News-Aggregator (Russland/AfD)", AN, "hoch", None),
    "UC3gJSe50HI67uKN4mO9a91g": ("A7", "Talkshow (Radio Bremen)", OERR, "mittel", None),
    "UCKbigI3YRqL7wFliRr7R8Mw": ("C3", "Reaction (Staiy-Zweitkanal)", EP, "hoch", None),
    "UCoUN_yusGiLh9uwLN2xZuYw": ("C3", "Fußball/Comedy", EP, "hoch", None),
    "UCdJUFxC2vb7xDAa5M-Mvi_A": ("C3", "Rap-News", EP, "hoch", None),
    "UC6Wkh06cSGkCDIhkk_xHhUw": ("C4", "Religion (christliche Predigten)", EP, "mittel", "teils politische Kommentare"),
    "UCP0XtrbAFWp-RkPS904VSEw": ("B2", "Polit-Clips/Verbraucherfinanzen", EP, "niedrig", "Beschreibung Finanzen, Titel überwiegend Politik und Tier-Shorts"),
    "UCJvp5iq9klHnvki_YnTmxQA": ("B4", "Politiker (Grüne, Bundesminister)", POL, "hoch", None),
    "UCI9wqAKuTelhdToktHJ4s9Q": ("C4", "Garten", EP, "hoch", None),
    "UCSEr0-U62P5qeqqpJA2_Nog": ("B3", "Archivclips (Helmut Schmidt)", AN, "hoch", None),
    "UCRvNgIlm7NnKLSL1WIc_yHQ": ("B2", "Satire/Podcast (Längert)", EP, "hoch", "Zweitkanal von Clownswelt"),
    "UCoSKQ9e_DsYpFVsuUKaus9A": ("C1", "Finanzen/Interviews (Andreas Beck)", UN, "hoch", None),
    "UCYEWIee0ApH6cBxciYxPXDg": ("C2", "Mathe-Nachhilfe", EP, "hoch", None),
    "UCrL3vhmQnFKNfdY_8yUBtcA": ("C3", "Interview-Podcast-Clips", EP, "mittel", None),
    "UCmNyt19w_SVXRik2I1X84dg": ("C1", "Finanzen/Arbeitsrecht-Shorts", EP, "hoch", None),
    "UC-ZMxS-psFAo2NahWdE3I5g": ("A7", "Radio-Kultur/Musik (rbb)", OERR, "mittel", None),
    "UCMlirlzQIUpfb3uC5LXB17Q": ("C2", "Technik/Energiewende", EP, "hoch", None),
    "UCX9NCHt0gI0nMbUWNPIKsCw": ("C3", "Interview-Podcast", EP, "mittel", "teils Politikergäste"),
    "UCWFl8y-bkvnJ9RhnTtyfPtA": ("B2", "Vlog/Undercover gegen rechts", EP, "mittel", "Zweitkanal von marcant"),
    "UCRkFMKQApHodjgV0IVuAXHQ": ("C4", "Religion (islamischer Prediger)", EP, "mittel", None),
    "UCCk8v-UmHH9jPfs3m3cRr0Q": ("C2", "Technik (KI)", EP, "hoch", None),
    "UCkP3cBG9m7nHSbOOEYugCLA": ("B3", "Polit-Kommentar/Satire", AN, "mittel", "Pseudonym ohne Impressumsperson"),
    "UC5vRhLlSCrBEBuzn51ZrpBQ": ("B2", "Polit-Reaction (rechts)", EP, "hoch", None),
    "UC3z34-ighaGmK30To86HMqw": ("C3", "Kabarett", EP, "hoch", None),
    "UCUA2wv8aKohNqTAtTDGV9wQ": ("C4", "Religion (islamischer Prediger)", EP, "mittel", None),
    "UCYyerybBwXg3GhxofPs9eHQ": ("A7", "TV-Show-Archiv (RTL/ProSieben)", PM, "hoch", None),
    "UC7CJun1Vcrn7TVgpndgqBpw": ("B2", "Militäranalyse (Torsten Heinrich)", EP, "mittel", "Clip-Kanal, laut Beschreibung im Auftrag betreut"),
    "UCuR7hglVNuxnvQffSoOwrag": ("C3", "Comedy-Archivclips (Harald Schmidt)", AN, "mittel", None),
    "UC0RBJwg8ZfRM8TLGOKTpArA": ("B3", "Clips/Kompilation", AN, "hoch", None),
    "UC6-3bNvn4FpTebBhsreWZBg": ("C4", "Unternehmenskanal (Umzug)", UN, "hoch", None),
    "UCLi8PUVEzLSShCnomkIB48A": ("B3", "Talkshow-Clips (Lanz)", AN, "hoch", None),
    "UCVJc8RKxfX00EIFo1wwJ3ow": ("A6", "Satire-Songs (extra 3)", OERR, "hoch", None),
    "UC7nW8V_NntJawOXED8zJ55A": ("C4", "Coaching/Motivation", EP, "hoch", None),
    "UCNyCbbSxjcPZta5x4UjjrFw": ("B3", "Polit-Shorts (AfD-Fokus)", AN, "mittel", "Pseudonym ohne Impressumsperson"),
    "UCigtuurEEt3QLwazM_9OvVA": ("C1", "Steuern", UN, "hoch", None),
    "UCFhuQ228JMOO9A9TBAyRKqA": ("B2", "Kommentar/News (Dominik Königs)", EP, "hoch", None),
    "UC2q758ZoKua2OKWxSHJiVXA": ("B1", "Polit-Talk (mehrere Köpfe)", AMU, "mittel", None),
    "UCVTzfXBluaApg_1HYaq4IFA": ("B3", "Satire/Memes", AN, "mittel", "Pseudonym ohne Impressumsperson; teils unpolitisch"),
    "UCN23GlvCgK9XZDsNQzln4_Q": ("C4", "Motorrad", EP, "hoch", None),
    "UCB4UKfI2Wj5xWFUUTklxy-w": ("C3", "Stand-up-Comedy", EP, "hoch", None),
    "UCtIdmHlJYcToNr3o05Cv0Nw": ("B3", "Satire/Clips", AN, "hoch", None),
    "UCSgXnWOMcVUE2He4lSx2l8A": ("C3", "Kabarett (AT)", EP, "mittel", "überwiegend Clips aus ORF 'Gute Nacht Österreich'"),
    "UCskvXSvph6FlEZa5B6uJnVg": ("C2", "Musikunterricht", EP, "hoch", None),
    "UCdPX3MNVbr5nGRthygN2JRQ": ("C4", "Religion (islamische Predigten)", AN, "mittel", None),
    "UC2_h-LYx4rEE3bsL7mZ6Udw": ("B2", "Polit-Reaction", EP, "mittel", None),
    "UCYo2MjFS5C7Wynyty9wTM7g": ("B2", "Kommentar/Reaction (rechts)", EP, "hoch", None),
    "UCeMVwcZum_Iicuo3JMuPfPg": ("C2", "Handwerk/Elektrotechnik", EP, "hoch", None),
    "UCRhB0rzRfzFNKKbPLO4BYYg": ("C4", "Baumaschinen", EP, "hoch", None),
    "UCqQ9P_ObrTQ0MhUnZffKkGA": ("B3", "Essay/Kommentar (rechts)", AN, "mittel", "Pseudonym ohne Impressumsperson"),
    "UCGhpSxT5gmwaNgz6jZbCHyg": ("B3", "Clips (AfD-Fokus)", AN, "hoch", None),
    "UC7x1zUUIrccDYILEpD-gbBA": ("B3", "Polit-Satire-Edits", AN, "mittel", None),
    "UCuzRXB-EOz1FZx2l7xw2nQQ": ("C1", "Steuern", UN, "hoch", None),
    "UCvx-64VlcyeDFBLwtR4G6vg": ("C4", "Eisenbahn/Simulator", EP, "hoch", None),
    "UC9QV7uZvrqbWUbIRifdWz5g": ("C1", "Finanzen/Statistik-Shorts", AN, "hoch", None),
    "UCdoHHeblAGGW3uy52DalI7w": ("B2", "Polit-Clips mit Kommentar/Gaming", EP, "niedrig", "Mix aus Landwirtschafts-Simulator und Polit-Clips"),
    "UCxlEazKoCv2mNFiiVPOUESQ": ("B3", "Satire-Songs/Schlager", AN, "niedrig", "Mix aus Polit-Satire-Songs und Schlager"),
    "UCUQ0WLZUAKArPdkgmZjFCWQ": ("C4", "Auto", AN, "hoch", None),
    "UC67IaTsbpkzgAaeRMnJt5AQ": ("C3", "Vlog/Reaction", EP, "mittel", "Umfeld marcant, gelegentlich Politik"),
    "UCoVxi4FUUcO5Jyx1EtpERZw": ("A5", "Wissenschaftsformat (SWR)", OERR, "hoch", None),
    "UC_54Oneq5DtXk13PRtazREQ": ("C3", "Gaming/Let's Play", EP, "hoch", None),
}


def main():
    prov = pd.read_csv(PROVENANCE)
    bestand = pd.read_excel(CHANNELS_XLSX)
    offen = prov[~prov["channel_id"].isin(bestand["Column1"])]
    fehlend = set(offen["channel_id"]) - set(TYPOLOGIE)
    extra = set(TYPOLOGIE) - set(offen["channel_id"])
    assert not fehlend, f"nicht klassifiziert: {sorted(fehlend)}"
    assert not extra, f"klassifiziert, aber nicht offen: {sorted(extra)}"

    mt = pd.read_excel(MEDIENTYP).drop_duplicates("channel_id").set_index("channel_id")["type"]
    namen = offen.set_index("channel_id")["channel_title"]
    zeilen = []
    for cid in offen.sort_values("subscribers", ascending=False)["channel_id"]:
        code, subtyp, org, sicher, anm = TYPOLOGIE[cid]
        roh = mt.get(cid)
        zeilen.append({
            "channel_id": cid,
            "kanal_name": str(namen[cid]).strip(),
            "medientyp_label": MEDIENTYP_LABEL.get(int(roh)) if pd.notna(roh) else None,
            "typ_code": code,
            "typ": TYP_LABEL[code],
            "subtyp": subtyp,
            "organisationsform": org,
            "sicherheit": sicher,
            "anmerkung": anm,
        })
    out = pd.DataFrame(zeilen)
    out.to_csv(OUT, index=False, encoding="utf-8")
    print(f"{len(out)} Kanäle -> {OUT}")
    print(out["typ_code"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()

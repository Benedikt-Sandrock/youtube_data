"""Grenzfall-Prüfung der Kanaltypologie (einmalig, 2026-10-14).

Wendet die nach Sichtung von Videotitel-Stichproben getroffenen
Umcodierungen auf ``data/external/kanal_typologie.csv`` (bis 14.10.2026 in scripts/adhoc/outputs/) an und
dokumentiert Kriterium und Entscheidungen in
``scripts/adhoc/outputs/kanal_typologie_grenzfaelle.md``.

Leitkriterium B4 vs. B2 (Absender statt Bekanntheit):
    B4 nur, wenn der Kanal von einer Partei/Fraktion, einer Person, deren
    Hauptrolle im Untersuchungszeitraum ein politisches Amt/Mandat ist, oder
    einer Organisation (NGO, Thinktank, Verband, Parlament) betrieben wird.
    Einzelpersonen ohne Mandat -> B2, unabhängig davon, wie aktivistisch sie
    sind. Kurzzeitige Kandidaturen (Grosz, Otte 2022) machen keinen B4-Kanal.
Weitere Regeln:
    B1 vs. B2: redaktionelle Marke/mehrere Köpfe (B1) vs. Einzelperson (B2).
    B3: keine identifizierbare verantwortliche Person.
    C1 vs. B2: Wirtschaft/Finanzen als roter Faden (auch mit politischer
    Rahmung) -> C1; Politik ohne Finanzbezug -> B2.
    Allgemein: überwiegender Inhalt des Kanals entscheidet, nicht Name oder
    Selbstbeschreibung.

Idempotent: bereits angewandte Änderungen werden übersprungen.
Aufruf:  python scripts/adhoc/kanal_typologie_grenzfaelle.py
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CSV = ROOT / "data" / "external" / "kanal_typologie.csv"
MD = ROOT / "scripts" / "adhoc" / "outputs" / "kanal_typologie_grenzfaelle.md"

TYP_LABEL = {
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

# channel_id: (kanal_name, neu_typ, neu_subtyp|None, neu_orgform|None, neu_sicherheit|None, begruendung)
# Schlüssel: channel_id oder (eindeutiger) kanal_name
AENDERUNGEN = {
    # --- B4 -> B2: Einzelpersonen ohne Mandat -----------------------------
    "UCfmOzrUPX4shSByl7fQPmGg": ("Für die Meinungsfreiheit!", "B2", "Kommentar/Interview (Martin Lohmann)", "Einzelperson", "mittel",
        "Titel zeigen 'LOHMANN:Kommentar' und Lohmann-Interviews (u. a. mit Maaßen); Zuordnung als Maaßen-Kanal nicht belegt -> Journalist ohne Mandat"),
    "UCf4WJRXsgDEP7KH2eNGv8Hw": ("Mutig sein für die Schwachen !", "B2", "Kommentar (Aktivist Serge Menga)", None, None,
        "Aktivist ohne Mandat, Inhalt Meinungskommentar. ACHTUNG: medientyp bleibt 'Partei/Politiker' (bewusste, dokumentierte Abweichung)"),
    # --- übrige Umcodierungen ---------------------------------------------
    "UCi5RJM_p1NajcGdBQfjyU4A": ("POLITIK SPEZIAL - Stimme der Vernunft", "B1", "Portal (Max Otte; Interviews/Formate)", "Alternatives Medienunternehmen", "mittel",
        "Portalartig mit wechselnden Gästen und Formaten (Matussek & Reinhardt, Interviews); Ottes politische Rollen 2022/23 nur kurzzeitig"),
    "UCh7UU4jFZWKzu1KxqDic_Og": ("Utopia TV Deutschland", "B3", "Demo-Livestreams (rechts)", "Anonym", "mittel",
        "Fehlzuordnung: nicht utopia.de, sondern Livestreams von AfD-/Bauern-/Friedensdemos; keine verantwortliche Person erkennbar"),
    "UCAU09OnUvIPwe19RdrJBg0w": ("Kurbel TV", "B3", "Bundestagsreden-Clips (umgewidmeter Kanal)", "Anonym", "mittel",
        "Eigene Kanalbeschreibung: überwiegend Bundestagsreden-Ausschnitte; früher Retro-Filme -> umgewidmeter Kanal, Vorher/Nachher nicht interpretierbar"),
    "UC5w2aXFKL_kLWSattQ6ekmQ": ("MENTALE FITNESS", "B3", "Reaction/Kommentar Politik", "Anonym", "mittel",
        "Impressum US-LLC, keine Person erkennbar; Titelstil identisch mit Oli/Olli (möglicher Kanalverbund)"),
    "UC71SOu9JMKd3VHJs7GipdNQ": ("Zeidgenosse", "C2", "Geschichte/Abstimmungserklärungen (CH)", None, None,
        "Überwiegend Geschichts- und Volksabstimmungs-Erklärvideos, kaum Tageskommentar"),
    "UCWZu-P34DVZUVrYAROU3Cmw": ("Prinz", "C3", "Reaction/Kommentar (Promi/Gesellschaft)", None, None,
        "Überwiegend Promi-/Gesellschaftsthemen (Taylor Swift, P. Diddy, Minions)"),
    "UCsdf_os0T0MizL_GRDYsLDQ": ("Henner - Der Nordhesse", "C3", "Vlog/Shorts", None, None,
        "Überwiegend unpolitische Vlogs/Shorts, nur vereinzelt News"),
    "UCxOGWb_OYoaz2V3QclJT3YA": ("mym by Simo", "B2", "Interview-Kanal Politik/Gesellschaft", None, None,
        "Überwiegend politische Interviews (Krall, Sarrazin, Patzelt), kein Finanzbezug als roter Faden"),
    "UCair4tGwkIovC3UQlkc3-zQ": ("Alexander Raue Klartext", "B2", "Politikkommentar (Zweitkanal)", None, None,
        "Zweitkanal ausschließlich mit Politik-/Geopolitik-Kommentar, kein Immobilien-/Finanzbezug"),
    "UCX_2-8KGmcSSAF8P0YAVpOQ": ("GabbaGandalfTV", "B2", "Livestream-Kommentar Politik", None, "mittel",
        "Überwiegend politische Live-Kommentare (AfD-Jugend, Messerdebatte, Amadeu Antonio Stiftung)"),
    "UCqZSdUJqd2T0oqr6BEA3ONw": ("Oli", "B2", None, None, "mittel",
        "Titelstil identisch mit 'Olli' -> wohl derselbe Betreiber; Typ unverändert, Doppelzählung bei Kanalzahlen beachten"),
}

for cid, name in [("Carsten Jahn - TEAM HEIMAT", "Kommentar (Aktivist, rechts)"),
                  ("Owe Schattauer", "Kommentar/Gespräche (Friedensaktivist)"),
                  ("Mathias von Gersdorff", "Kommentar (christlich-konservativ)"),
                  ("Landwirtschaft erLEEben mit Anthony Lee", "Kommentar (Bauernprotest)")]:
    AENDERUNGEN[cid] = (cid, "B2", name, None, None,
                        "Einzelperson ohne Mandat; Titel-Stichprobe zeigt überwiegend Tageskommentar")

for name in ["ARD", "WDR", "SWR", "Hessischer Rundfunk", "rbb", "MDR Mitteldeutscher Rundfunk"]:
    AENDERUNGEN[name] = (name, "A8", "Senderhauptkanal (gemischt)", None, None,
                         "Mischprogramm (Unterhaltung, Ratgeber, Regionales, Podcasts) – kein reines Nachrichtenangebot")

AENDERUNGEN.update({
    "Salim Samatou": ("Salim Samatou", "C3", "Comedy/Unterhaltung", None, "mittel",
                      "Überwiegend Comedy/Unterhaltung, vereinzelt Politik"),
})

# Geprüft, aber unverändert (für die Dokumentation)
BESTAETIGT = [
    ("Peter Boehringer, Stephan Brandner, Gottfried Curio, Roger Beckamp, Alice Weidel, Christian Hafenecker, Sahra Wagenknecht", "B4", "Mandatsträger"),
    ("Gysi gegen Guttenberg, MISSVERSTEHEN SIE MICH RICHTIG", "B4", "Gysi als aktiver MdB = Absender, obwohl Talkformat"),
    ("Unignorierbar, Atlas Initiative, EIKE, DeutscherHanfverband", "B4", "Organisationen"),
    ("Deutscher Bundestag", "B4", "Institution; bei Analysen von Parteikommunikation ggf. ausschließen"),
    ("Gerald Grosz", "B2", "Ex-Politiker; BP-Kandidatur 2022 nur kurzzeitig, Kanal = Kommentar"),
    ("Tobias Huch", "B2", "Kommentar/Aktivist ohne Mandat"),
    ("Olli", "B2", "s. Oli – möglicher Kanalverbund"),
    ("DIE WELTWOCHE", "B1", "Printtitel, YouTube-Output = Weltwoche Daily (Köppel); bleibt alternatives Portal"),
    ("exxpressTV", "B1", "Online-Boulevard (AT); medientyp 'traditionelle Medien' – dokumentierte Abweichung wie Menga"),
    ("Achtung, Reichelt!, Peter Weber", "B1", "Personality-Formate eines Portals (NIUS, Hallo Meinung)"),
    ("DER AKTIONÄR TV, Cashkurs.com, Ernst Wolff, Horst Lüning", "C1", "Finanzen als roter Faden (Wolff/Lüning/Müller mit politischer Rahmung)"),
    ("Robert Franz", "C4", "Alternativmedizin als Kerninhalt"),
    ("Weichreite TV", "B3", "Demo-Aufnahmen ohne erkennbare Person"),
    ("ServusTV On", "A2", "überwiegend politische Talkformate, daher nicht A8"),
    ("LYDOM, KÖNIGIN DER KELCHE, Frequent Traveller TV, HÄMATOM", "C2/C4",
     "themenfremd; Whitelist-Zugehörigkeit nicht Teil dieser Prüfung, liegen außerhalb der Kernstichprobe"),
]


def main() -> None:
    d = pd.read_csv(CSV)
    by_name = dict(zip(d.kanal_name, d.channel_id))
    rows = []
    for key, (name, typ, subtyp, org, sich, grund) in AENDERUNGEN.items():
        cid = key if key in set(d.channel_id) else by_name.get(key)
        if cid is None:
            raise KeyError(f"Kanal nicht gefunden: {key}")
        i = d.index[d.channel_id == cid][0]
        alt = d.at[i, "typ_code"]
        anm = d.at[i, "anmerkung"]
        if isinstance(anm, str) and "Grenzfallprüfung 2026-10-14" in anm:
            # bereits angewandt: alten Code aus dem Marker rekonstruieren
            m = re.search(r"Grenzfallprüfung 2026-10-14: (\w+)->", anm)
            rows.append((d.at[i, "kanal_name"], m.group(1) if m else alt, typ, grund))
            continue
        rows.append((d.at[i, "kanal_name"], alt, typ, grund))
        marker = f"Grenzfallprüfung 2026-10-14: {alt}->{typ}" if alt != typ else "Grenzfallprüfung 2026-10-14"
        d.at[i, "typ_code"] = typ
        d.at[i, "typ"] = TYP_LABEL[typ]
        if subtyp:
            d.at[i, "subtyp"] = subtyp
        if org:
            d.at[i, "organisationsform"] = org
        if sich:
            d.at[i, "sicherheit"] = sich
        d.at[i, "anmerkung"] = f"{anm}; {marker}" if isinstance(anm, str) else marker
    # B4-Label an neues Kriterium anpassen (Aktivismus raus)
    d.loc[d.typ_code == "B4", "typ"] = TYP_LABEL["B4"]
    d.to_csv(CSV, index=False, encoding="utf-8")

    lines = [
        "# Kanaltypologie – Grenzfallprüfung (2026-10-14)",
        "",
        "Erzeugt von `scripts/adhoc/kanal_typologie_grenzfaelle.py`. Grundlage: Stichprobe von je 7 Videotiteln",
        "aus `videos_roh.dta` für alle 98 Grenzfälle (B4, Anmerkung 'Grenzfall/prüfen', Sicherheit < hoch,",
        "Politiker-/Aktivisten-Subtypen) sowie `outputs/stata_rohdaten/channel_description.xlsx`.",
        "",
        "## Kriterien",
        "",
        "- **B4 vs. B2 (Absender statt Bekanntheit):** B4 nur bei Partei/Fraktion, Person mit politischem Amt/Mandat",
        "  als Hauptrolle im Untersuchungszeitraum oder Organisation (NGO, Thinktank, Verband, Parlament).",
        "  Einzelpersonen ohne Mandat -> B2, auch wenn sie als Aktivisten bekannt sind. Kurzzeitige Kandidaturen",
        "  (Grosz, Otte 2022) begründen kein B4.",
        "- **B1 vs. B2:** redaktionelle Marke / mehrere Köpfe (B1) vs. Einzelperson (B2).",
        "- **B3:** keine identifizierbare verantwortliche Person.",
        "- **C1 vs. B2:** Wirtschaft/Finanzen als roter Faden (auch politisch gerahmt) -> C1; Politik ohne Finanzbezug -> B2.",
        "- **A8 (neu):** Senderhauptkanäle mit Mischprogramm – kein reines Nachrichtenangebot, daher nicht A1.",
        "- **Allgemein:** überwiegender Inhalt entscheidet, nicht Name oder Selbstbeschreibung.",
        "",
        "## Umcodierungen",
        "",
        "| Kanal | alt | neu | Begründung |",
        "|---|---|---|---|",
    ]
    for name, alt, neu, grund in sorted(rows, key=lambda r: (r[1], r[0])):
        lines.append(f"| {name} | {alt} | {neu} | {grund} |")
    lines += ["", "## Geprüft, unverändert", "", "| Kanäle | Typ | Begründung |", "|---|---|---|"]
    lines += [f"| {k} | {t} | {g} |" for k, t, g in BESTAETIGT]
    lines += [
        "",
        "## Dokumentierte Abweichungen Typologie vs. `medientyp`",
        "",
        "- **Serge Menga (Mutig sein für die Schwachen !):** typ_code B2 (Kommentator ohne Mandat), `medientyp` bleibt",
        "  'Partei/Politiker'. `medientyp` wurde bewusst nicht angepasst, um bestehende Frage-1-Ergebnisse nicht zu",
        "  verschieben. Bei Analysen nach Typologie gilt B2, bei Analysen nach `medientyp` die alte Zuordnung.",
        "- **exxpressTV:** B1, `medientyp` 'traditionelle Medien'.",
        "- **Schweinfurter Nachrichten:** A3, `medientyp` 'Creator & alternative Medien'.",
        "- **B4-Organisationen, Gysi-Kanäle und Peter Boehringer:** B4, `medientyp` 'Creator & alternative Medien'.",
        "",
        "## Hinweise",
        "",
        "- **Kurbel TV** ist ein umgewidmeter Kanal (vor Kriegsbeginn Retro-Filme, danach Bundestagsreden-Clips);",
        "  in Vorher/Nachher-Schätzungen innerhalb von Kanälen ausschließen.",
        "- **Oli / Olli / MENTALE FITNESS:** identischer Titelstil, möglicherweise ein Betreiber – bei Kanalzählungen beachten.",
        "- Typzuordnung beruht auf Titeln über den gesamten Zeitraum. Für Kanäle, die sich erst nach 2022 politisiert",
        "  haben (z. B. Krissy Rieger), ist der Typ nicht exogen zum Kriegsbeginn.",
    ]
    MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows)} Fälle verarbeitet -> {CSV.name}, {MD.name}")


if __name__ == "__main__":
    main()

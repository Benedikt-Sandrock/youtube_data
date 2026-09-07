# -*- coding: utf-8 -*-
"""
frage1_stance_bericht.py

Konsolidierte, formale Auswertung der Haltung gegenueber Russland (und,
als zweite Dimension desselben Prompts, gegenueber der westlichen
Ukraine-Politik) nach demselben Verfahren wie frage1_populismus_bericht.py
fuer Forschungsfrage 1 (.claude/CLAUDE.md): "Hat sich die Position gegenueber
Russland / der westlichen Ukraine-Politik seit Kriegsbeginn veraendert? Gibt
es Unterschiede nach politischer Ideologie oder Medientyp?" Anders als
Populismus ist das keine der vier nummerierten Forschungsfragen, sondern
liefert deskriptiven/inferentiellen Kontext zur selben Vorkriegs/Nachkriegs-
Vergleichsanlage (COMPLETE_PROCESS.md: "Wo immer moeglich, Vergleich vor vs.
nach Kriegsbeginn ... um den Kriegsbeginn als exogene Variation zu nutzen").

Baut auf dem Video-Ebene-Output von prepare_channel_scores.py auf
(channel_video_position.csv: eine Zeile je Video, rel_quartal/rel_monat sind
reine Kalenderzeit relativ zum 24.02.2022 - siehe COMPLETE_PROCESS.md Schritt
2), gefiltert auf DIESELBE Whitelist wie die Populismus-Auswertung
(frage1_kanal_whitelist.csv aus frage1_stichprobe.py: >= 5 Kriegsvideos im
gesamten Upload-Verlauf UND mindestens 1 klassifiziertes Video - siehe dort
und outputs/segment_analysis/frage1_methodik_und_stichprobe.md). Die
Whitelist selbst prueft Stufe 2 ("mind. 1 klassifiziertes Video") ueber
channel_video_populism.csv, nicht channel_video_position.csv - beide Prompts
laufen ueber praktisch dieselbe Kanalmenge (380 von 381 Whitelist-Kanaelen
haben mindestens ein klassifiziertes Position-Video), ein einzelner Kanal
ohne Position-Daten traegt hier einfach nichts bei, statt einen Fehler
auszuloesen. frage1_stichprobe.py MUSS vorher einmal gelaufen sein.

WICHTIG: Wie bei Populismus wird die Video-Ebene VOR der Regression zu
Kanal x Periode aggregiert (aggregiere_kanal_periode(), Mittelwert je
Dimension ueber alle Videos eines Kanals innerhalb der jeweiligen Periode).
Eine Beobachtung in post_dummy_test()/interaktions_test() ist damit ein
Kanal-Monat (bzw. Kanal-Quartal), NICHT ein einzelnes Video - siehe
frage1_methodik_und_stichprobe.md Abschnitt 4 fuer die vollstaendige
Herleitung (identisch fuer beide Berichte).

Zwei Bausteine je Dimension x Granularitaet, identisch zu
frage1_populismus_bericht.py (siehe dortiger Docstring fuer die vollstaendige
Begruendung):

1. post_dummy_test(): Kanal-FE + EIN Nachkriegs-Dummy (post = periode >= 0),
   Standardfehler auf Kanalebene geclustert.
2. interaktions_test(): dasselbe Modell, zusaetzlich Post x Gruppe-
   Interaktion (Gruppe = Ideologie oder Medientyp), gemeinsamer F-Test auf
   die Interaktionsterme.

Ergaenzend werden je Gruppe auch die getrennten post_dummy_test()-Ergebnisse
berichtet, plus die TEILGRUPPEN_INTERAKTIONEN-Zusatzauswertung (Ideologie
INNERHALB "Alternatives Medium").

Schreibt eine konsolidierte Ergebnistabelle
(frage1_stance_bericht_{granularitaet}.csv) und druckt eine
Kurzzusammenfassung. Nutzt lade_medientyp()/lade_ideologie() aus
deskriptiv_aggregation.py sowie post_dummy_test()/interaktions_test() aus
bericht_utils.py, beide als bare sibling import - direkt im Ordner
ausfuehren, nicht als -m-Modul (gleiches Muster wie
frage1_populismus_bericht.py, siehe README).
"""

import numpy as np
import pandas as pd

from youtube_code.config import OUTPUTS
from deskriptiv_aggregation import lade_medientyp, lade_ideologie
from bericht_utils import post_dummy_test, interaktions_test

# =========================================================
# CONFIG
# =========================================================

PFAD_EINGABE = OUTPUTS / "segment_analysis" / "channel_video_position.csv"
PFAD_AUSGABE = OUTPUTS / "segment_analysis" / "frage1_stance_bericht_{granularitaet}.csv"

# Dieselbe Whitelist wie frage1_populismus_bericht.py (siehe Docstring oben
# und frage1_methodik_und_stichprobe.md) - bewusst NICHT auf None
# zurueckgesetzt, weil genau dieselbe Vorkriegs/Nachkriegs-Vergleichslogik
# nur fuer Kanaele mit nennenswertem Kriegsbezug sinnvoll ist.
PFAD_WHITELIST = OUTPUTS / "segment_analysis" / "frage1_kanal_whitelist.csv"

# position_russland ist die eigentliche "Haltung gegenueber Russland" (Ziel
# dieser Auswertung). position_westpolitik ist dieselbe Erhebung fuer die
# zweite, unabhaengige Dimension desselben Prompts (Haltung gegenueber
# westlicher Ukraine-Politik) und wird analog mitberichtet. emotion ist -
# wie emotionale_intensitaet bei Populismus - explizit eine Kontrollgroesse
# (segment_prompts_simple.py, Dimension 3), keine Positionierung.
DIMENSIONEN = [
    "position_russland",
    "position_westpolitik",
    "emotion",  # Kontrollgroesse
]
KONTROLLGROESSEN = {"emotion"}

# Identisch zu frage1_populismus_bericht.py.
GRANULARITAETEN = {
    "quartal": {"spalte": "rel_quartal", "periode_min": -4, "periode_max": 14},
    "monat":   {"spalte": "rel_monat",   "periode_min": -12, "periode_max": 42},
}

GRUPPEN_SPALTEN = {
    "ideologie_gruppe": ["links", "mitte", "rechts"],
    "medientyp": ["ÖRR", "Traditionelles Medium", "Alternatives Medium", "Politiker/Partei"],
}

MIN_KANAELE_JE_GRUPPE = 5

TEILGRUPPEN_INTERAKTIONEN = [
    {
        "bezeichnung": "alternative_medien_ideologie",
        "filter": {"medientyp": ["Alternatives Medium"]},
        "gruppen_spalte": "ideologie_gruppe",
        "gruppen_werte": ["links", "mitte", "rechts"],
    },
]


# =========================================================
# DATEN LADEN
# =========================================================

def lade_video_daten():
    df = pd.read_csv(PFAD_EINGABE)
    df["channel_id"] = df["channel_id"].astype(str)
    n_vor = df["channel_id"].nunique()

    whitelist = pd.read_csv(PFAD_WHITELIST)
    whitelist_ids = set(whitelist["channel_id"].astype(str))
    df = df[df["channel_id"].isin(whitelist_ids)]
    print(f"[Whitelist] {n_vor} -> {df['channel_id'].nunique()} Kanaele nach Filter auf "
          f"{PFAD_WHITELIST} (siehe frage1_methodik_und_stichprobe.md).")

    fehlend_in_position = whitelist_ids - set(df["channel_id"])
    if fehlend_in_position:
        print(f"[Hinweis] {len(fehlend_in_position)} Whitelist-Kanal/-Kanaele ohne klassifiziertes "
              f"Position-Video (kein Fehler, tragen einfach nichts bei): {sorted(fehlend_in_position)}")

    med = lade_medientyp()
    ideo = lade_ideologie()
    df = df.merge(med, on="channel_id", how="left").merge(ideo, on="channel_id", how="left")
    print(f"[Eingabe] {len(df)} Video-Beobachtungen, {df['channel_id'].nunique()} Kanaele aus {PFAD_EINGABE}")
    return df


def _fenster(df, spalte_periode, periode_min, periode_max):
    return df[(df[spalte_periode] >= periode_min) & (df[spalte_periode] <= periode_max)]


def aggregiere_kanal_periode(df, spalte_periode):
    """Video-Ebene -> Kanal x Periode, identisch zu
    frage1_populismus_bericht.py::aggregiere_kanal_periode() (siehe dortiger
    Docstring)."""
    agg = df.groupby(["channel_id", spalte_periode], as_index=False).agg(
        **{d: (d, "mean") for d in DIMENSIONEN},
        medientyp=("medientyp", "first"),
        ideologie_gruppe=("ideologie_gruppe", "first"),
        n_videos=("video_id", "count"),
    )
    return agg


# =========================================================
# MAIN
# =========================================================

def verarbeite_granularitaet(df, granularitaet, gran_cfg):
    spalte_periode = gran_cfg["spalte"]
    df_fenster = _fenster(df, spalte_periode, gran_cfg["periode_min"], gran_cfg["periode_max"])
    df_g = aggregiere_kanal_periode(df_fenster, spalte_periode)
    print(f"[Aggregation][{granularitaet}] {len(df_fenster)} Video-Beobachtungen -> "
          f"{len(df_g)} Kanal-{granularitaet}-Beobachtungen "
          f"({df_g['channel_id'].nunique()} Kanaele).")

    zeilen = []
    for dimension in DIMENSIONEN:
        kontrolle = " [KONTROLLGROESSE]" if dimension in KONTROLLGROESSEN else ""
        print(f"\n=== {dimension}{kontrolle} ({granularitaet}) ===")

        # --- Gesamtstichprobe ---
        res = post_dummy_test(df_g, dimension, spalte_periode, bezeichnung="gesamt")
        if res:
            print(f"  [Gesamt] post={res['koeffizient_post']:+.4f} (p={res['p']:.4f}), "
                  f"Vorkrieg-Mittel={res['mittel_vorkrieg']:.3f}, Nachkrieg-Mittel={res['mittel_nachkrieg']:.3f}, "
                  f"n_kanaele={res['n_kanaele']}")
            zeilen.append({"dimension": dimension, "ist_kontrollgroesse": dimension in KONTROLLGROESSEN,
                            "ebene": "gesamt", **res})

        # --- je Gruppierungsspalte: Interaktionstest + getrennte Gruppentests ---
        for gruppen_spalte, gruppen_werte in GRUPPEN_SPALTEN.items():
            inter = interaktions_test(df_g, dimension, spalte_periode, gruppen_spalte, gruppen_werte,
                                       min_kanaele_je_gruppe=MIN_KANAELE_JE_GRUPPE)
            if inter:
                signifikanz = "signifikant unterschiedlich" if inter["p"] < 0.05 else "kein signifikanter Unterschied"
                print(f"  [Interaktion {gruppen_spalte}] F({inter['df_num']},{inter['df_denom']})="
                      f"{inter['f_stat']:.3f}, p={inter['p']:.4f} -> {signifikanz} zwischen "
                      f"{inter['gruppen']}")
                zeilen.append({"dimension": dimension, "ist_kontrollgroesse": dimension in KONTROLLGROESSEN,
                                "ebene": f"interaktion_{gruppen_spalte}", "gruppe": "+".join(inter["gruppen"]),
                                "n_beobachtungen": inter["n_beobachtungen"], "n_kanaele": inter["n_kanaele"],
                                "f_stat": inter["f_stat"], "df_num": inter["df_num"], "df_denom": inter["df_denom"],
                                "p": inter["p"]})

                for gruppe in inter["gruppen"]:
                    teil = df_g[df_g[gruppen_spalte] == gruppe]
                    res_g = post_dummy_test(teil, dimension, spalte_periode, bezeichnung=gruppe)
                    if res_g:
                        print(f"    [{gruppen_spalte}={gruppe}] post={res_g['koeffizient_post']:+.4f} "
                              f"(p={res_g['p']:.4f}), n_kanaele={res_g['n_kanaele']}")
                        zeilen.append({"dimension": dimension, "ist_kontrollgroesse": dimension in KONTROLLGROESSEN,
                                        "ebene": gruppen_spalte, **res_g})

        # --- Teilgruppen-Interaktionstests: Ideologie INNERHALB eines einzelnen
        # Medientyps (TEILGRUPPEN_INTERAKTIONEN, siehe CONFIG) ---
        for eintrag in TEILGRUPPEN_INTERAKTIONEN:
            teil_basis = df_g
            for spalte, werte in eintrag["filter"].items():
                teil_basis = teil_basis[teil_basis[spalte].isin(werte)]

            inter = interaktions_test(teil_basis, dimension, spalte_periode,
                                       eintrag["gruppen_spalte"], eintrag["gruppen_werte"],
                                       min_kanaele_je_gruppe=MIN_KANAELE_JE_GRUPPE)
            if inter:
                signifikanz = "signifikant unterschiedlich" if inter["p"] < 0.05 else "kein signifikanter Unterschied"
                print(f"  [Interaktion {eintrag['bezeichnung']}] F({inter['df_num']},{inter['df_denom']})="
                      f"{inter['f_stat']:.3f}, p={inter['p']:.4f} -> {signifikanz} zwischen "
                      f"{inter['gruppen']}")
                zeilen.append({"dimension": dimension, "ist_kontrollgroesse": dimension in KONTROLLGROESSEN,
                                "ebene": f"interaktion_{eintrag['bezeichnung']}", "gruppe": "+".join(inter["gruppen"]),
                                "n_beobachtungen": inter["n_beobachtungen"], "n_kanaele": inter["n_kanaele"],
                                "f_stat": inter["f_stat"], "df_num": inter["df_num"], "df_denom": inter["df_denom"],
                                "p": inter["p"]})

                for gruppe in inter["gruppen"]:
                    teil = teil_basis[teil_basis[eintrag["gruppen_spalte"]] == gruppe]
                    res_g = post_dummy_test(teil, dimension, spalte_periode,
                                             bezeichnung=f"{eintrag['bezeichnung']}={gruppe}")
                    if res_g:
                        print(f"    [{eintrag['bezeichnung']}={gruppe}] post={res_g['koeffizient_post']:+.4f} "
                              f"(p={res_g['p']:.4f}), n_kanaele={res_g['n_kanaele']}")
                        zeilen.append({"dimension": dimension, "ist_kontrollgroesse": dimension in KONTROLLGROESSEN,
                                        "ebene": eintrag["bezeichnung"], **res_g})

    ergebnis = pd.DataFrame(zeilen)
    ergebnis["granularitaet"] = granularitaet
    pfad = str(PFAD_AUSGABE).format(granularitaet=granularitaet)
    ergebnis.to_csv(pfad, index=False, encoding="utf-8")
    print(f"\n[Ausgabe][{granularitaet}] {len(ergebnis)} Zeilen -> {pfad}")
    return ergebnis


def main():
    df = lade_video_daten()

    alle_ergebnisse = []
    for granularitaet, gran_cfg in GRANULARITAETEN.items():
        alle_ergebnisse.append(verarbeite_granularitaet(df, granularitaet, gran_cfg))

    gesamt = pd.concat(alle_ergebnisse, ignore_index=True)

    print("\n" + "=" * 70)
    print("KURZZUSAMMENFASSUNG (Gesamtstichprobe, post_dummy_test, p < 0.05)")
    print("=" * 70)
    ueberblick = gesamt[gesamt["ebene"] == "gesamt"]
    for _, zeile in ueberblick.iterrows():
        richtung = "gestiegen" if zeile["koeffizient_post"] > 0 else "gesunken"
        sig = "signifikant" if zeile["p"] < 0.05 else "nicht signifikant"
        kontrolle = " [Kontrollgroesse]" if zeile["ist_kontrollgroesse"] else ""
        print(f"  {zeile['dimension']}{kontrolle} ({zeile['granularitaet']}): "
              f"{richtung} um {abs(zeile['koeffizient_post']):.4f} ({sig}, p={zeile['p']:.4f})")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
frage1_populismus_bericht.py

Konsolidierte, formale Antwort auf Forschungsfrage 1 (.claude/CLAUDE.md):
"Hat der Populismus auf YouTube nach dem Beginn des Ukraine-Kriegs zugenommen?
Gibt es Unterschiede nach politischer Ideologie oder Medientyp? Bei welchen
Dimensionen des Populismus hat sich etwas veraendert?"

Baut auf dem Video-Ebene-Output von prepare_channel_scores.py auf
(channel_video_populism.csv: eine Zeile je Video, rel_quartal/rel_monat sind
reine Kalenderzeit relativ zum 24.02.2022, unabhaengig vom individuellen
Baseline-Fenster eines Kanals - siehe COMPLETE_PROCESS.md Schritt 2), gefiltert
auf die Whitelist aus frage1_stichprobe.py (>= 5 Kriegsvideos im gesamten
Upload-Verlauf UND mindestens 1 klassifiziertes Video - siehe dort und
outputs/segment_analysis/frage1_methodik_und_stichprobe.md fuer die genaue
Herleitung und die vollstaendige Dokumentation, was als "Baseline" bzw.
"Veraenderung" gilt). frage1_stichprobe.py MUSS also vorher einmal gelaufen
sein.

WICHTIG: Die Video-Ebene wird VOR der Regression zu Kanal x Periode
aggregiert (aggregiere_kanal_periode(), Mittelwert je Dimension ueber alle
Videos eines Kanals innerhalb der jeweiligen Periode). Eine Beobachtung in
post_dummy_test()/interaktions_test() ist damit ein Kanal-Monat (bei
GRANULARITAET="monat") bzw. ein Kanal-Quartal (bei "quartal"), NICHT mehr ein
einzelnes Video - sonst wuerden Kanaele mit vielen klassifizierten Videos je
Periode die Schaetzung staerker gewichten als Kanaele mit wenigen. Siehe
frage1_methodik_und_stichprobe.md Abschnitt 4.

Zwei Bausteine je Dimension x Granularitaet:

1. post_dummy_test(): Kanal-FE + EIN Nachkriegs-Dummy (post = periode >= 0),
   Standardfehler auf Kanalebene geclustert. Direkte Antwort auf "hat sich
   das Niveau nach Kriegsbeginn veraendert" (Effektgroesse + p-Wert), analog
   zu schock_test() in fe_signifikanz_test.py, aber mit post = ganze
   Nachkriegszeit statt einer einzelnen Schockperiode.
2. interaktions_test(): dasselbe Modell, zusaetzlich Post x Gruppe-Interaktion
   (Gruppe = Ideologie oder Medientyp), gemeinsamer F-Test auf die
   Interaktionsterme. Das ist die formal korrekte Antwort auf "unterscheidet
   sich der Nachkriegseffekt signifikant zwischen den Gruppen" - eine reine
   Gegenueberstellung getrennter Gruppentests koennte keinen p-Wert auf den
   UNTERSCHIED selbst liefern (Kanal-Zugehoerigkeit zu einer Gruppe ist
   zeitkonstant und daher vollstaendig mit den Kanal-FE kollinear; deshalb
   taucht in der Formel absichtlich kein eigener Gruppen-Haupteffekt auf,
   nur "post" und "post:Gruppe").

Ergaenzend werden je Gruppe (links/mitte/rechts bzw. die vier Medientypen)
auch die getrennten post_dummy_test()-Ergebnisse berichtet - fuer die
Effektgroesse/Richtung INNERHALB einer Gruppe, waehrend der Interaktionstest
die Frage nach dem GRUPPENUNTERSCHIED selbst beantwortet.

Zusaetzlich TEILGRUPPEN_INTERAKTIONEN (CONFIG): derselbe Interaktionstest,
aber vorher auf einen einzelnen Medientyp gefiltert - beantwortet "unterscheidet
sich der Nachkriegseffekt nach Ideologie INNERHALB dieses Medientyps". Aktuell
nur fuer "Alternatives Medium" (mit Abstand die groesste und ideologisch
heterogenste Medientyp-Gruppe); bei ÖRR/Traditionelles Medium/Politiker-Partei
lohnt eine weitere Aufspaltung nicht (zu klein, ideologisch zu homogen).

Schreibt eine konsolidierte Ergebnistabelle
(frage1_populismus_bericht_{granularitaet}.csv) und druckt eine
Kurzzusammenfassung. Nutzt lade_medientyp()/lade_ideologie() aus
deskriptiv_aggregation.py sowie post_dummy_test()/interaktions_test() aus
bericht_utils.py, beide als bare sibling import (siehe README, gleiches
Muster wie fe_signifikanz_test.py) - direkt im Ordner ausfuehren, nicht als
-m-Modul.
"""

import numpy as np
import pandas as pd

from youtube_code.config import OUTPUTS
from deskriptiv_aggregation import lade_medientyp, lade_ideologie
from bericht_utils import post_dummy_test, interaktions_test

# =========================================================
# CONFIG
# =========================================================

PFAD_EINGABE = OUTPUTS / "segment_analysis" / "channel_video_populism.csv"
PFAD_AUSGABE = OUTPUTS / "segment_analysis" / "frage1_populismus_bericht_{granularitaet}.csv"

# Kanal-Whitelist aus frage1_stichprobe.py (>= MIN_KRIEGSVIDEOS Kriegsvideos im gesamten
# Upload-Verlauf UND mindestens 1 klassifiziertes Video) - siehe dort und
# outputs/segment_analysis/frage1_methodik_und_stichprobe.md fuer die vollstaendige
# Herleitung. Vor dieser Filterung enthielt channel_video_populism.csv auch Kanaele mit
# kaum Kriegsbezug, fuer die ein Vorher/Nachher-Vergleich rund um den Kriegsbeginn
# inhaltlich nicht aussagekraeftig ist.
PFAD_WHITELIST = OUTPUTS / "segment_analysis" / "frage1_kanal_whitelist.csv"

# Vier inhaltliche Populismus-Dimensionen + Gesamtscore. emotionale_intensitaet
# ist laut Prompt (segment_prompts_simple.py) explizit eine Kontrollgroesse,
# KEINE Populismus-Dimension - wird separat ausgewiesen, nicht in die
# "ist Populismus gestiegen"-Aussage eingerechnet.
DIMENSIONEN = [
    "volkszentrismus",
    "antielitismus",
    "manichaeische_moralisierung",
    "populismus_gesamt",
    "emotionale_intensitaet",  # Kontrollgroesse
]
KONTROLLGROESSEN = {"emotionale_intensitaet"}

# Beide Granularitaeten gleichwertig, wie in deskriptiv_aggregation.py
GRANULARITAETEN = {
    "quartal": {"spalte": "rel_quartal", "periode_min": -4, "periode_max": 14},
    "monat":   {"spalte": "rel_monat",   "periode_min": -12, "periode_max": 42},
}

# Gruppierungsspalten fuer den Interaktionstest, mit fester Reihenfolge
# (erste = Referenzgruppe im Modell; aendert nur die Parametrisierung, nicht
# den F-Test auf die Interaktion).
GRUPPEN_SPALTEN = {
    "ideologie_gruppe": ["links", "mitte", "rechts"],
    "medientyp": ["ÖRR", "Traditionelles Medium", "Alternatives Medium", "Politiker/Partei"],
}

MIN_KANAELE_JE_GRUPPE = 5   # unterhalb dieser Kanalzahl wird der Gruppentest uebersprungen

# Zusaetzliche Interaktionstests: Ideologie-Differenzierung INNERHALB eines einzelnen
# Medientyps, wo das inhaltlich sinnvoll ist. Aktuell nur fuer "Alternatives Medium" -
# mit ~180 Kanaelen die mit Abstand groesste UND ideologisch heterogenste Gruppe (deckt
# links, mitte und rechts in nennenswerter Zahl ab). ÖRR/Traditionelles Medium/
# Politiker-Partei sind sowohl zu klein als auch ideologisch zu homogen (ueberwiegend
# mitte/links) fuer eine aussagekraeftige weitere Aufspaltung - dieselbe Logik wie
# GRUPPEN_SPALTEN, nur zusaetzlich auf eine Medientyp-Teilmenge gefiltert. Jeder Eintrag
# durchlaeuft denselben interaktions_test() + post_dummy_test()-je-Gruppe-Ablauf wie
# GRUPPEN_SPALTEN oben.
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

    med = lade_medientyp()
    ideo = lade_ideologie()
    df = df.merge(med, on="channel_id", how="left").merge(ideo, on="channel_id", how="left")
    print(f"[Eingabe] {len(df)} Video-Beobachtungen, {df['channel_id'].nunique()} Kanaele aus {PFAD_EINGABE}")
    return df


def _fenster(df, spalte_periode, periode_min, periode_max):
    return df[(df[spalte_periode] >= periode_min) & (df[spalte_periode] <= periode_max)]


def aggregiere_kanal_periode(df, spalte_periode):
    """Video-Ebene -> Kanal x Periode (Kanal-Monat bzw. Kanal-Quartal): Mittelwert je
    Dimension ueber alle Videos eines Kanals innerhalb der Periode. Macht den Kanal-Monat
    (nicht das einzelne Video) zur Beobachtungseinheit der Regression - siehe Docstring
    oben und frage1_methodik_und_stichprobe.md Abschnitt 4. medientyp/ideologie_gruppe sind
    kanalkonstant (per "first" uebernommen), n_videos zaehlt die Videos je Zelle."""
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

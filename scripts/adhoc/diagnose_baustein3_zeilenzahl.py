# -*- coding: utf-8 -*-
"""
diagnose_baustein3_zeilenzahl.py

Ad-hoc-Diagnose (.claude/CLAUDE.md: einmalige Auswertungen gehoeren nach scripts/adhoc/) VOR
dem ersten echten Lauf von Baustein 3 (Video-Ebene) in frage4_kriegspraemie_medientyp_
bericht.py mit den seit 2026-09-08 neu ergaenzten Dimensionen DAUER_TEILSTICHPROBEN x
VERGLEICHSGRUPPEN (siehe .claude/plans/frage4_kriegspraemie_vergleichsgruppen_und_
beobachtungseinheiten.md, Umsetzungsschritt 4: "Vor dem echten Lauf: Zeilenzahl nach beiden
Filtern empirisch schaetzen"). Baustein 3 aggregiert NICHT (jedes Video eine eigene Zeile mit
C(channel_id) + C(periode) als Dummy-Matrix) - die volle Stichprobe im Quartal-Fenster hat
laut fruehrerer Diagnose (siehe Plan-Datei) 824.186 Zeilen, ein GROSSES Speicher-/
Laufzeitrisiko. Dieses Skript zaehlt NUR die Zeilen-/Kanalzahl je (Stichprobe x
Vergleichsgruppe)-Kombination, OHNE irgendeine Regression zu rechnen - reine Groessen-
abschaetzung, um das Risiko VOR dem eigentlichen (teuren) main()-Lauf neu zu bewerten.

Repliziert dafuer die relevanten Filterschritte aus frage4_kriegspraemie_medientyp_
bericht.py (Whitelist, gruppe5, Quartal-Fenster, Politik-Klassifikation, DAUER_
TEILSTICHPROBEN, VERGLEICHSGRUPPEN) als eigenstaendige, schlanke Kopie statt eines echten
Imports (bare-sibling-Importe des Zielmoduls sind von hier aus nicht ohne Umwege moeglich,
siehe videolaenge_diagnose.py-Docstring fuer dasselbe Vorgehen) - Konfigurationswerte
(GRANULARITAETEN["quartal"], DAUER_TEILSTICHPROBEN, VERGLEICHSGRUPPEN) sind deshalb hier
HARDCODIERT auf den Stand von frage4_kriegspraemie_medientyp_bericht.py zum Zeitpunkt dieser
Diagnose (2026-09-08) - bei spaeteren Aenderungen dort ist dieses Skript ggf. veraltet.

Ausfuehrung (aus dem Projekt-Root):
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/adhoc/diagnose_baustein3_zeilenzahl.py

Schreibt scripts/adhoc/output/diagnose_baustein3_zeilenzahl.csv.
"""

import pandas as pd

from youtube_code.config import OUTPUTS
from youtube_code.store.video_registry import politics_topic_lookup
from youtube_code.step6_auswertung.deskriptiv_aggregation import lade_medientyp, lade_ideologie
from youtube_code.step6_auswertung.deskriptiv_plots import GRUPPE5_REIHENFOLGE

PFAD_ERFOLG = OUTPUTS / "segment_analysis" / "channel_video_erfolg.csv"
PFAD_WHITELIST = OUTPUTS / "segment_analysis" / "frage1_kanal_whitelist.csv"
PFAD_OUTPUT_DIR = OUTPUTS.parent / "scripts" / "adhoc" / "output"
AUSGABE = PFAD_OUTPUT_DIR / "diagnose_baustein3_zeilenzahl.csv"

# Hardcodierte Kopie der Quartal-Granularitaet aus frage4_kriegspraemie_medientyp_bericht.py.
PERIODE_SPALTE = "rel_quartal"
PERIODE_MIN, PERIODE_MAX = -4, 16

# Hardcodierte Kopie von DAUER_TEILSTICHPROBEN dort.
DAUER_TEILSTICHPROBEN = {
    "voll": {"minuten_min": None, "minuten_max": None},
    "kurz_bis_10min": {"minuten_min": 0, "minuten_max": 10},
    "mittel_3_30min": {"minuten_min": 3, "minuten_max": 30},
}

VERGLEICHSGRUPPEN = ["alle_videos", "nur_politische_videos"]


def baue_gruppe5_lokal(df):
    """Kurze lokale Kopie, siehe videolaenge_diagnose.py fuer dasselbe Vorgehen/Begruendung."""
    df = df.copy()
    ist_alt = df["medientyp"] == "Alternatives Medium"
    df["gruppe5"] = df["medientyp"]
    df.loc[ist_alt, "gruppe5"] = "Alternative Medien (" + df.loc[ist_alt, "ideologie_gruppe"].astype(str) + ")"
    df = df[df["gruppe5"].isin(GRUPPE5_REIHENFOLGE)]
    return df


def lade_basisdaten():
    df = pd.read_csv(PFAD_ERFOLG)
    df["channel_id"] = df["channel_id"].astype(str)
    df["video_id"] = df["video_id"].astype(str)

    whitelist_ids = set(pd.read_csv(PFAD_WHITELIST)["channel_id"].astype(str))
    df = df[df["channel_id"].isin(whitelist_ids)]

    med = lade_medientyp()
    ideo = lade_ideologie()
    df = df.merge(med, on="channel_id", how="left").merge(ideo, on="channel_id", how="left")
    df = baue_gruppe5_lokal(df)

    topic_map = politics_topic_lookup(df["video_id"].tolist())
    df["ist_politisches_video"] = df["video_id"].map(topic_map)

    df = df[(df[PERIODE_SPALTE] >= PERIODE_MIN) & (df[PERIODE_SPALTE] <= PERIODE_MAX)]
    print(f"[Basisdaten] {len(df)} Video-Beobachtungen im Quartal-Fenster "
          f"({df['channel_id'].nunique()} Kanaele).")
    return df


def main():
    df = lade_basisdaten()

    zeilen = []
    for st_id, st_cfg in DAUER_TEILSTICHPROBEN.items():
        if st_cfg["minuten_min"] is None:
            df_st = df
        else:
            dauer_minuten = df["duration_seconds"] / 60
            maske = dauer_minuten >= st_cfg["minuten_min"]
            if st_cfg["minuten_max"] is not None:
                maske &= dauer_minuten <= st_cfg["minuten_max"]
            df_st = df[maske]

        for vg in VERGLEICHSGRUPPEN:
            if vg == "alle_videos":
                df_vg = df_st
            else:
                ist_politisch = df_st["ist_politisches_video"].fillna(False).astype(bool)
                verwerfen = (df_st["ist_kriegsvideo"] == 0) & ~ist_politisch
                df_vg = df_st[~verwerfen]

            n_kriegsvideos = int(df_vg["ist_kriegsvideo"].sum())
            zeile = {
                "stichprobe": st_id,
                "vergleichsgruppe": vg,
                "n_zeilen": len(df_vg),
                "n_kanaele": df_vg["channel_id"].nunique(),
                "n_kriegsvideos": n_kriegsvideos,
                "n_sonstige_videos": len(df_vg) - n_kriegsvideos,
            }
            zeilen.append(zeile)
            print(f"[{st_id}][{vg}] {zeile['n_zeilen']} Zeilen, {zeile['n_kanaele']} Kanaele "
                  f"({n_kriegsvideos} Kriegsvideos, {zeile['n_sonstige_videos']} sonstige).")

    tabelle = pd.DataFrame(zeilen)
    PFAD_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tabelle.to_csv(AUSGABE, index=False, encoding="utf-8")
    print(f"\n-> {AUSGABE}")


if __name__ == "__main__":
    main()

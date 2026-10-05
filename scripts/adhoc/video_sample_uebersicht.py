# -*- coding: utf-8 -*-
"""
video_sample_uebersicht.py

Uebersicht ueber das SAMPLE DER BEREITS KLASSIFIZIERTEN Videos (channel_video_populism.csv /
channel_video_position.csv aus prepare_channel_scores.py), aufgeschluesselt nach
Medientyp x Periode. Zeigt, wo die Zellen zu duenn besetzt sind, um belastbare Vergleiche
zu erlauben (z.B. fuer die Regressionen in fe_signifikanz_test.py), und listet die
konkreten Kanaele auf, bei denen sich gezieltes Nachdownloaden/-klassifizieren am meisten
lohnt (groesstes Defizit zum Zielwert).

Bezieht sich NUR auf bereits klassifizierte Videos - keine Aussage darueber, ob es im
Rohsample (YouTube-Metadaten) ueberhaupt noch unklassifizierte Videos fuer eine duenne
Zelle gibt.

Run pattern: this script is meant to be executed directly
(`python scripts/adhoc/video_sample_uebersicht.py`). `lade_medientyp()` lives in
`step6_auswertung/deskriptiv_aggregation.py` - a different folder than this script (unlike the
step6 scripts, which stay bare-sibling-importable because they moved together), so it is
imported as a real package import instead, with the same manual sys.path setup used by
scripts/adhoc/consolidate_llm_results.py.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from youtube_code.config import OUTPUTS  # noqa: E402
from youtube_code.step6_auswertung.deskriptiv_aggregation import lade_medientyp  # noqa: E402

# =========================================================
# CONFIG
# =========================================================

MODUS = "populismus"          # "populismus" | "stance" - unterschiedliche Videopools
                               # (Populismus: Baseline+Kriegsvideos, Stance: nur Kriegsvideos)
GRANULARITAET = "monat"       # "quartal" | "monat"

SPALTE_PERIODE = {"quartal": "rel_quartal", "monat": "rel_monat"}[GRANULARITAET]

DATEINAME_VIDEO_EBENE = {
    "populismus": "channel_video_populism.csv",
    "stance": "channel_video_position.csv",
}
PFAD_EINGABE = OUTPUTS / "segment_analysis" / DATEINAME_VIDEO_EBENE[MODUS]

PFAD_UEBERSICHT = OUTPUTS / "segment_analysis" / "sample_uebersicht_medientyp_periode_{modus}_{granularitaet}.csv"
PFAD_DUENNE_ZELLEN = OUTPUTS / "segment_analysis" / "sample_duenne_kanal_zellen_{modus}_{granularitaet}.csv"

# Nur Perioden im Fenster betrachten (z.B. um sehr alte/zukuenftige Randperioden auszuschliessen).
# None = kein Limit.
PERIODE_MIN = None
PERIODE_MAX = None

# Zielwert: ab wie vielen Videos gilt eine Zelle als ausreichend besetzt.
ZIEL_VIDEOS_PRO_MEDIENTYP_PERIODE = 10   # fuer die Medientyp x Periode Uebersicht
ZIEL_VIDEOS_PRO_KANAL_PERIODE = 3        # fuer die kanalscharfe Duenne-Zellen-Liste


# =========================================================
# DATEN LADEN
# =========================================================

def lade_klassifizierte_videos():
    df = pd.read_csv(PFAD_EINGABE)
    print(f"[Eingabe] {len(df)} klassifizierte Videos aus {PFAD_EINGABE}")

    if SPALTE_PERIODE not in df.columns:
        raise KeyError(f"Spalte '{SPALTE_PERIODE}' nicht in '{PFAD_EINGABE}'. "
                        f"Vorhanden: {list(df.columns)}")

    med = lade_medientyp()
    df = df.merge(med, on="channel_id", how="left")

    fehlend = df["medientyp"].isna().sum()
    if fehlend:
        print(f"[Warnung] {fehlend} Videos ohne zuordenbaren Medientyp (Kanal nicht in "
              f"Medientyp-Datei gefunden) -> werden in der Uebersicht als 'NaN' gefuehrt.")

    if PERIODE_MIN is not None:
        df = df[df[SPALTE_PERIODE] >= PERIODE_MIN]
    if PERIODE_MAX is not None:
        df = df[df[SPALTE_PERIODE] <= PERIODE_MAX]

    return df


# =========================================================
# UEBERSICHT: Medientyp x Periode
# =========================================================

def erstelle_medientyp_periode_uebersicht(df):
    """Pivot-Tabelle: Anzahl klassifizierter Videos je Medientyp x Periode."""
    zaehlung = df.groupby(["medientyp", SPALTE_PERIODE], as_index=False).agg(
        n_videos=("video_id", "nunique"),
        n_kanaele=("channel_id", "nunique"),
    )

    pivot_videos = zaehlung.pivot(index="medientyp", columns=SPALTE_PERIODE, values="n_videos").fillna(0).astype(int)

    pfad = str(PFAD_UEBERSICHT).format(modus=MODUS, granularitaet=GRANULARITAET)
    pivot_videos.to_csv(pfad, encoding="utf-8")
    print(f"\n[Uebersicht] Medientyp x Periode (Videoanzahl) -> {pfad}")
    print(pivot_videos.to_string())

    duenn = zaehlung[zaehlung["n_videos"] < ZIEL_VIDEOS_PRO_MEDIENTYP_PERIODE].copy()
    duenn["defizit"] = ZIEL_VIDEOS_PRO_MEDIENTYP_PERIODE - duenn["n_videos"]
    duenn = duenn.sort_values("defizit", ascending=False)

    print(f"\n[Duenne Zellen] {len(duenn)} von {len(zaehlung)} Medientyp-Perioden-Zellen unter "
          f"ZIEL_VIDEOS_PRO_MEDIENTYP_PERIODE={ZIEL_VIDEOS_PRO_MEDIENTYP_PERIODE}:")
    if not duenn.empty:
        print(duenn.to_string(index=False))
    else:
        print("  (keine)")

    return zaehlung, duenn


# =========================================================
# GEZIELTE KANAL-EBENE: wo genau nachdownloaden?
# =========================================================

def erstelle_duenne_kanal_zellen(df):
    """Kanalscharfe Liste: Kanal x Periode Zellen unter dem Zielwert, NUR innerhalb der
    Medientyp-Perioden-Kombinationen, die laut Uebersicht ohnehin zu duenn sind - das
    sind die Stellen, an denen zusaetzliche Downloads/Klassifikationen am meisten zur
    Balance beitragen."""

    zaehlung_kanal = df.groupby(
        ["channel_id", "channel_title", "medientyp", SPALTE_PERIODE], as_index=False
    ).agg(n_videos=("video_id", "nunique"))

    duenn_kanal = zaehlung_kanal[zaehlung_kanal["n_videos"] < ZIEL_VIDEOS_PRO_KANAL_PERIODE].copy()
    duenn_kanal["defizit"] = ZIEL_VIDEOS_PRO_KANAL_PERIODE - duenn_kanal["n_videos"]
    duenn_kanal = duenn_kanal.sort_values(
        ["medientyp", SPALTE_PERIODE, "defizit"], ascending=[True, True, False]
    )

    pfad = str(PFAD_DUENNE_ZELLEN).format(modus=MODUS, granularitaet=GRANULARITAET)
    duenn_kanal.to_csv(pfad, index=False, encoding="utf-8")
    print(f"\n[Duenne Kanal-Zellen] {len(duenn_kanal)} Kanal-Perioden-Zellen unter "
          f"ZIEL_VIDEOS_PRO_KANAL_PERIODE={ZIEL_VIDEOS_PRO_KANAL_PERIODE} -> {pfad}")

    zusammenfassung = duenn_kanal.groupby("channel_id", as_index=False).agg(
        channel_title=("channel_title", "first"),
        n_duenne_perioden=(SPALTE_PERIODE, "nunique"),
        summe_defizit=("defizit", "sum"),
    ).sort_values("summe_defizit", ascending=False)

    print(f"\n[Top-Kanaele nach Gesamtdefizit] (groesster Hebel fuer gezielte Downloads):")
    print(zusammenfassung.head(20).to_string(index=False))

    return duenn_kanal


# =========================================================
# MAIN
# =========================================================

def main():
    print(f"=== Sample-Uebersicht: {MODUS}, {GRANULARITAET} ===")

    df = lade_klassifizierte_videos()
    erstelle_medientyp_periode_uebersicht(df)
    erstelle_duenne_kanal_zellen(df)


if __name__ == "__main__":
    main()

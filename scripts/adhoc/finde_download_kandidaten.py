# -*- coding: utf-8 -*-
"""
finde_download_kandidaten.py

Nimmt die duenn besetzten Kanal-Perioden-Zellen aus video_sample_uebersicht.py
(sample_duenne_kanal_zellen_*.csv) und sucht darin gezielt nach Videos aus
videos_compact_pol_labels.csv, die

- zum jeweiligen Kanal UND zur jeweiligen Periode gehoeren (Periode wird hier selbst aus
  published_at berechnet - NICHT aus den Spalten period/interval_index/interval_label der
  Datei, da diese bekanntermassen anders/kalendermonatsbasiert gerechnet sind, siehe
  Diskussion zu KRIEGSBEGINN-Tagesgenauigkeit),
- als Kriegsvideo markiert sind (is_war_core ODER is_war_wide),
- noch NICHT klassifiziert wurden (video_id noch nicht in channel_video_populism.csv).

Ergebnis: eine Liste von Video-IDs, geordnet nach Kanal-Periode-Zelle, als konkrete
Download-/Klassifikations-Vorschlagsliste. Deckt eine Zelle keinen einzigen Kandidaten ab,
wird das separat ausgewiesen (Sample kann dort mit den vorhandenen Videos nicht verbessert
werden).
"""

import pandas as pd

from youtube_code.config import OUTPUTS

# =========================================================
# CONFIG
# =========================================================

GRANULARITAET = "monat"       # "quartal" | "monat" - muss zur Defizit-Datei passen
SPALTE_PERIODE = {"quartal": "rel_quartal", "monat": "rel_monat"}[GRANULARITAET]

KRIEGSBEGINN = "2022-02-24"
MONATE_PRO_PERIODE = {"quartal": 3, "monat": 1}[GRANULARITAET]

PFAD_DEFIZIT = OUTPUTS / "segment_analysis" / f"sample_duenne_kanal_zellen_populismus_{GRANULARITAET}.csv"
PFAD_VIDEOS_ALLE = OUTPUTS / "sample_feasibility" / "videos_compact_pol_labels.csv"
PFAD_BEREITS_KLASSIFIZIERT = OUTPUTS / "segment_analysis" / "channel_video_populism.csv"

PFAD_AUSGABE_KANDIDATEN = OUTPUTS / "segment_analysis" / f"download_kandidaten_{GRANULARITAET}.csv"
PFAD_AUSGABE_OHNE_KANDIDATEN = OUTPUTS / "segment_analysis" / f"download_kandidaten_leer_{GRANULARITAET}.csv"

MEDIENTYP_FILTER = ["Alternatives Medium"]

# Kriegsvideo-Flags in videos_compact_pol_labels.csv - ODER-verknuepft
KRIEGSVIDEO_SPALTEN = ["is_war_core", "is_war_wide"]

# Deficit-Zellen mit rel_periode < diesem Wert werden ignoriert: is_war_core/is_war_wide
# markiert Kriegsvideos, die per Definition nicht in die Vorkriegs-Baseline gehoeren.
# None = keine Einschraenkung (nicht empfohlen, siehe Docstring).
PERIODE_MIN_FUER_KRIEGSVIDEOS = 0


# =========================================================
# HILFSFUNKTION: Periode aus published_at berechnen
# =========================================================

def relativ_periode(datum, start, monate_pro_periode):
    """Identisch zur Logik in prepare_channel_scores.py."""
    monate = (datum.dt.year - start.year) * 12 + (datum.dt.month - start.month)
    monate = monate - (datum.dt.day < start.day).astype(int)
    return (monate // monate_pro_periode).astype(int)


# =========================================================
# DATEN LADEN
# =========================================================

def lade_defizit_zellen():
    df = pd.read_csv(PFAD_DEFIZIT)
    print(f"[Defizit] {len(df)} Kanal-Perioden-Zellen aus {PFAD_DEFIZIT}")

    df = df[df["medientyp"].isin(MEDIENTYP_FILTER)]
    if PERIODE_MIN_FUER_KRIEGSVIDEOS is not None:
        vor = len(df)
        df = df[df[SPALTE_PERIODE] >= PERIODE_MIN_FUER_KRIEGSVIDEOS]
        print(f"[Defizit] {vor} -> {len(df)} Zellen nach Filter auf "
              f"{SPALTE_PERIODE} >= {PERIODE_MIN_FUER_KRIEGSVIDEOS} (nur Kriegszeit).")

    print(f"[Defizit] {len(df)} Zellen fuer {MEDIENTYP_FILTER} zu befuellen.")
    return df


def lade_kriegsvideo_kandidaten():
    usecols = ["channel_id", "channel_title", "video_id", "published_at"] + KRIEGSVIDEO_SPALTEN
    videos = pd.read_csv(PFAD_VIDEOS_ALLE, usecols=lambda c: c in usecols)
    fehlend = [s for s in usecols if s not in videos.columns]
    if fehlend:
        raise KeyError(f"In '{PFAD_VIDEOS_ALLE}' fehlen Spalten {fehlend}. "
                        f"Vorhanden: {list(pd.read_csv(PFAD_VIDEOS_ALLE, nrows=0).columns)}")

    videos["published_at"] = pd.to_datetime(videos["published_at"], errors="coerce", utc=True).dt.tz_localize(None)
    ohne_datum = videos["published_at"].isna()
    if ohne_datum.any():
        print(f"[Warnung] {int(ohne_datum.sum())} Videos ohne published_at -> verworfen.")
        videos = videos[~ohne_datum]

    start = pd.Timestamp(KRIEGSBEGINN)
    videos[SPALTE_PERIODE] = relativ_periode(videos["published_at"], start, MONATE_PRO_PERIODE)

    ist_kriegsvideo = videos[KRIEGSVIDEO_SPALTEN].fillna(0).astype(int).eq(1).any(axis=1)
    vor = len(videos)
    videos = videos[ist_kriegsvideo]
    print(f"[Kriegsvideos] {vor} -> {len(videos)} Videos mit "
          f"{' oder '.join(KRIEGSVIDEO_SPALTEN)} == 1.")

    bereits = pd.read_csv(PFAD_BEREITS_KLASSIFIZIERT, usecols=["video_id"])
    bereits_ids = set(bereits["video_id"])
    vor = len(videos)
    videos = videos[~videos["video_id"].isin(bereits_ids)]
    print(f"[Noch nicht klassifiziert] {vor} -> {len(videos)} Videos "
          f"(bereits klassifizierte video_ids ausgeschlossen).")

    return videos


# =========================================================
# ZUORDNUNG: Kandidaten je Defizit-Zelle
# =========================================================

def finde_kandidaten(defizit_df, kandidaten_df):
    ergebnisse = []
    leere_zellen = []

    for _, zeile in defizit_df.iterrows():
        treffer = kandidaten_df[
            (kandidaten_df["channel_id"] == zeile["channel_id"]) &
            (kandidaten_df[SPALTE_PERIODE] == zeile[SPALTE_PERIODE])
        ].sort_values("published_at")

        if treffer.empty:
            leere_zellen.append(zeile)
            continue

        treffer = treffer.copy()
        treffer["rang"] = range(1, len(treffer) + 1)
        treffer["defizit"] = zeile["defizit"]
        treffer["innerhalb_defizit"] = treffer["rang"] <= zeile["defizit"]
        ergebnisse.append(treffer)

    kandidaten = pd.concat(ergebnisse, ignore_index=True) if ergebnisse else pd.DataFrame()
    leer = pd.DataFrame(leere_zellen) if leere_zellen else pd.DataFrame()

    return kandidaten, leer


# =========================================================
# MAIN
# =========================================================

def main():
    defizit = lade_defizit_zellen()
    kandidaten_pool = lade_kriegsvideo_kandidaten()

    kandidaten, leer = finde_kandidaten(defizit, kandidaten_pool)

    spalten = ["video_id", "channel_id", "channel_title", SPALTE_PERIODE, "published_at",
               "defizit", "rang", "innerhalb_defizit"] + KRIEGSVIDEO_SPALTEN
    kandidaten = kandidaten[[s for s in spalten if s in kandidaten.columns]]
    kandidaten.to_csv(PFAD_AUSGABE_KANDIDATEN, index=False, encoding="utf-8")

    n_zellen_gesamt = len(defizit)
    n_zellen_mit_kandidaten = kandidaten[["channel_id", SPALTE_PERIODE]].drop_duplicates().shape[0] if not kandidaten.empty else 0
    n_innerhalb_defizit = int(kandidaten["innerhalb_defizit"].sum()) if not kandidaten.empty else 0

    print(f"\n[Ergebnis] {len(kandidaten)} Download-Kandidaten fuer "
          f"{n_zellen_mit_kandidaten} von {n_zellen_gesamt} Defizit-Zellen -> {PFAD_AUSGABE_KANDIDATEN}")
    print(f"  Davon {n_innerhalb_defizit} innerhalb des jeweiligen Defizits (Rest ist Puffer "
          f"fuer Download-/Transkript-Ausfaelle, siehe 'innerhalb_defizit'-Spalte).")

    if not leer.empty:
        leer[["channel_id", "channel_title", SPALTE_PERIODE, "defizit"]].to_csv(
            PFAD_AUSGABE_OHNE_KANDIDATEN, index=False, encoding="utf-8"
        )
        print(f"\n[Ohne Kandidaten] {len(leer)} Zellen haben KEIN passendes Kriegsvideo im "
              f"Rohsample -> {PFAD_AUSGABE_OHNE_KANDIDATEN} (Sample dort mit den vorhandenen "
              f"Videos nicht verbesserbar).")


if __name__ == "__main__":
    main()

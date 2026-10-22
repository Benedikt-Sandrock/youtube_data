# -*- coding: utf-8 -*-
"""
export_kanalliste_2019_2020.py

Schreibt die Kanalliste fuer die Erweiterung der Datenbasis auf 2019-2020
(Plan: .claude/plans/ -> "Datenbasis auf 2019-2020 erweitern", nur Metadaten).
Die Liste ist Input fuer `src/youtube_code/step1_sample/channel_video_formats.py`
(Video-Discovery + Format + Metadaten in einem Durchgang) mit
PUBLISHED_AFTER = PUBLISHED_BEFORE = None: das Fenster kommt aus den Spalten
fenster_von/fenster_bis dieser Liste. Spaeter auch Input fuer
metadata_collection.py (CHECK_CHANNELS_MODE) und classify_topic_relevance.py.

Aufgenommen werden alle Kanaele mit eligible_current_analysis == True aus
data/samples/<ANALYSIS_ID>/channel_sample_provenance.csv, die vor
GRUENDUNG_VOR gegruendet wurden (spaeter gegruendete Kanaele koennen im
Fenster keine Videos haben). Kanaele ohne Gruendungsdatum bleiben drin.
Sortierung: Whitelist-Kanaele (sample_whitelist == 1 in kanaele_roh.dta)
zuerst, danach nach video_count (Kanal-Metadaten) aufsteigend - bei einem
Quota-Abbruch sind so moeglichst viele Analysekanaele schon durch.
channel_video_formats.py liest nur channel_id und das Fenster; die uebrigen
Spalten dienen der Nachvollziehbarkeit.

Ausgabe: data/channel_lists/video_formats/sample_2019_2020.csv
(die Statusdatei des Formatlaufs entsteht daneben als
sample_2019_2020_formats_status.csv). Optional zusaetzlich eine Pilotliste
(PILOT_AUSGABE) mit PILOT_N_KLEIN/PILOT_N_MITTEL/PILOT_N_GROSS Kanaelen.

Ausfuehren aus dem Repo-Root:
    PYTHONPATH=src .venv/Scripts/python.exe scripts/adhoc/export_kanalliste_2019_2020.py
"""

import sys

import pandas as pd

from youtube_code.config import CHANNEL_LISTS, OUTPUTS, SAMPLES

# =========================================================
# KONFIGURATION
# =========================================================
# Sample-Definition (Unterordner in data/samples/)
ANALYSIS_ID = "russia_longitudinal_v1"
# Fenster der Erweiterung, ISO mit Z, Ende inklusive (Format wie
# channel_video_formats.PUBLISHED_AFTER/_BEFORE)
FENSTER_VON = "2019-01-01T00:00:00Z"
FENSTER_BIS = "2020-12-31T23:59:59Z"
# Nur Kanaele, die vor diesem Datum (YYYY-MM-DD) gegruendet wurden
GRUENDUNG_VOR = "2021-01-01"
# Quelle der Whitelist-Kennung (Spalte sample_whitelist); None = keine
# Whitelist-Sortierung
WHITELIST_QUELLE = OUTPUTS / "stata_rohdaten" / "kanaele_roh.dta"
# Kanaele mit so vielen Uploads laufen in channel_video_formats.py ueber den
# yt-dlp-Fallback (UPLOADS_CAP_THRESHOLD dort) - nur fuer die Pilot-Auswahl
GROSS_AB = 19_500
AUSGABE = CHANNEL_LISTS / "video_formats" / "sample_2019_2020.csv"
# Pilotliste: None = keine; sonst Anzahl kleiner (< 2.000 Uploads), mittlerer
# (2.000 bis GROSS_AB) und grosser (>= GROSS_AB) Kanaele, je >= 0
PILOT_AUSGABE = CHANNEL_LISTS / "video_formats" / "pilot_2019_2020.csv"
PILOT_N_KLEIN, PILOT_N_MITTEL, PILOT_N_GROSS = 2, 2, 1
PILOT_SEED = 2019


def main():
    if FENSTER_VON >= FENSTER_BIS:
        sys.exit(f"FENSTER_VON ({FENSTER_VON}) muss vor FENSTER_BIS ({FENSTER_BIS}) liegen.")
    if min(PILOT_N_KLEIN, PILOT_N_MITTEL, PILOT_N_GROSS) < 0:
        sys.exit("PILOT_N_* muessen >= 0 sein.")
    if str(AUSGABE).endswith("_formats_status.csv"):
        sys.exit("AUSGABE darf nicht auf _formats_status.csv enden (Export liest diese per Glob).")

    sample = pd.read_csv(SAMPLES / ANALYSIS_ID / "channel_sample_provenance.csv",
                         usecols=["channel_id", "channel_title", "eligible_current_analysis",
                                  "channel_created_at", "video_count"])
    sample = sample[sample["eligible_current_analysis"] == True].copy()
    erstellt = pd.to_datetime(sample["channel_created_at"], errors="coerce", utc=True)
    alt_genug = erstellt.isna() | (erstellt < pd.Timestamp(GRUENDUNG_VOR, tz="UTC"))
    liste = sample[alt_genug].drop(columns="eligible_current_analysis")
    liste["video_count"] = liste["video_count"].fillna(0).astype(int)

    if WHITELIST_QUELLE is not None:
        k = pd.read_stata(WHITELIST_QUELLE, columns=["channel_id", "sample_whitelist"],
                          convert_categoricals=False)
        wl = set(k.loc[k["sample_whitelist"] == 1, "channel_id"].astype(str))
    else:
        wl = set()
    liste["whitelist"] = liste["channel_id"].isin(wl).astype(int)
    liste["fenster_von"] = FENSTER_VON
    liste["fenster_bis"] = FENSTER_BIS
    liste = liste.sort_values(["whitelist", "video_count"], ascending=[False, True])
    liste.to_csv(AUSGABE, index=False, encoding="utf-8")

    print(f"Sample {ANALYSIS_ID}: {len(sample)} Kanaele, davon vor {GRUENDUNG_VOR} gegruendet "
          f"(oder ohne Datum): {len(liste)} (ohne Datum: {int(erstellt.isna().sum())}), "
          f"Whitelist: {int(liste['whitelist'].sum())}, >= {GROSS_AB} Uploads: "
          f"{int((liste['video_count'] >= GROSS_AB).sum())}, Uploads gesamt: {liste['video_count'].sum():,}")
    print(f"Geschrieben: {AUSGABE}")

    if PILOT_AUSGABE is not None:
        vc = liste["video_count"]
        teile = [
            liste[vc < 2000].sample(n=min(PILOT_N_KLEIN, int((vc < 2000).sum())), random_state=PILOT_SEED),
            liste[(vc >= 2000) & (vc < GROSS_AB)].sample(
                n=min(PILOT_N_MITTEL, int(((vc >= 2000) & (vc < GROSS_AB)).sum())), random_state=PILOT_SEED),
            liste[vc >= GROSS_AB].sample(n=min(PILOT_N_GROSS, int((vc >= GROSS_AB).sum())), random_state=PILOT_SEED),
        ]
        pilot = pd.concat(teile)
        pilot.to_csv(PILOT_AUSGABE, index=False, encoding="utf-8")
        print(f"Pilotliste ({len(pilot)} Kanaele) geschrieben: {PILOT_AUSGABE}")
        print(pilot[["channel_id", "channel_title", "video_count", "whitelist"]].to_string(index=False))


if __name__ == "__main__":
    main()

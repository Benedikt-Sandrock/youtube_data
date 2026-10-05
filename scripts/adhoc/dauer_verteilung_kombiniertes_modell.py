# -*- coding: utf-8 -*-
"""
dauer_verteilung_kombiniertes_modell.py

Ad-hoc-Auswertung (.claude/CLAUDE.md: einmalige Auswertungen gehoeren nach
scripts/adhoc/, nicht nach src/youtube_code/) zur Nutzerfrage: "Wie viele Videos aus
dem jetzt verwendeten Sample bleiben uebrig, wenn man sich auf Videos bestimmter
Dauern beschraenkt?" - bezogen auf das kombinierte-Modell-Sample aus
step6_auswertung/populismuspraemie_kriegsvideos_bericht.py (Baustein (c)/(e)/(f):
Kriegsvideos mit allen KOMBI_VARIABLEN gleichzeitig klassifiziert, siehe
lade_kombiniertes_modell_daten() dort; Datei hiess zum Zeitpunkt dieses Ad-hoc-Skripts
noch regression_erfolg.py, seither umbenannt - siehe .claude/plans/
lies-aufgaben-md-in-claude-compressed-cascade.md). Wiederholt NUR den Daten-Load-Teil
dieser Funktion hier direkt (kein Import - populismuspraemie_kriegsvideos_bericht.py
setzt einen bare sibling import von deskriptiv_aggregation.py
voraus, der bei einem Import ueber den Paketpfad youtube_code.step6_auswertung.*
fehlschlaegt; gleiches Vorgehen wie diagnose_oerr_populismuspraemie.py).

Dauer steht NICHT in channel_video_erfolg.csv, sondern wird per
video_registry.duration_lookup() aus dem videos-Store nachgeladen (ISO-8601-Dauer,
z.B. "PT12M34S", wird zu Sekunden geparst). Die untere Grenze von 3 Minuten gilt im
Projekt ohnehin schon INDIREKT fuer die klassifizierten Kriegsvideos: Transkripte
(Voraussetzung fuer jede LLM-Klassifikation) werden nur fuer Videos ab
MIN_VIDEO_DURATION_SECONDS=181s (~3 Min) erhoben (siehe
step4_transcript_download/select_targets.py). Nutzervorgabe fuer die Bins:
3-10 / 10-20 / 20-60 / 60+ Minuten.

Ausfuehrung (aus dem Projekt-Root):
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        scripts/adhoc/dauer_verteilung_kombiniertes_modell.py

Schreibt scripts/adhoc/output/dauer_verteilung_kombiniertes_modell.csv.
"""

import pandas as pd

from youtube_code.config import MIN_VIDEO_DURATION_SECONDS, OUTPUTS
from youtube_code.store import video_registry

RESULTS_PATH = OUTPUTS / "segment_analysis"
PFAD_POPULISMUS = RESULTS_PATH / "channel_video_populism.csv"
PFAD_POSITION = RESULTS_PATH / "channel_video_position.csv"
PFAD_ERFOLG = RESULTS_PATH / "channel_video_erfolg.csv"

# Muss mit KOMBI_VARIABLEN in populismuspraemie_kriegsvideos_bericht.py uebereinstimmen
# (Stand 2026-09-08), damit hier exakt dasselbe Sample entsteht wie in dessen
# Baustein (c)/(e)/(f).
KOMBI_VARIABLEN = ["populismus_gesamt", "emotionale_intensitaet", "position_russland", "position_westpolitik"]

AUSGABE = OUTPUTS.parent / "scripts" / "adhoc" / "output" / "dauer_verteilung_kombiniertes_modell.csv"

# Nutzervorgabe: untere Grenze 3 Minuten (siehe Moduldocstring), Bins 3-10/10-20/20-60/60+.
GRENZEN_MINUTEN = [3, 10, 20, 60]


# =========================================================
# DATEN LADEN (Kopie von populismuspraemie_kriegsvideos_bericht.py::
# lade_kombiniertes_modell_daten(), nur die fuer die Dauer-Uebersicht relevanten Spalten)
# =========================================================

def lade_kombiniertes_modell_sample():
    pop = pd.read_csv(PFAD_POPULISMUS)
    pop["channel_id"] = pop["channel_id"].astype(str)
    pop_spalten = [v for v in KOMBI_VARIABLEN if v in pop.columns]

    pos = pd.read_csv(PFAD_POSITION)
    pos["channel_id"] = pos["channel_id"].astype(str)
    pos_spalten = [v for v in KOMBI_VARIABLEN if v in pos.columns]

    dim = pop[["channel_id", "video_id"] + pop_spalten].merge(
        pos[["channel_id", "video_id"] + pos_spalten], on=["channel_id", "video_id"], how="outer"
    )

    erfolg = pd.read_csv(PFAD_ERFOLG)
    erfolg["channel_id"] = erfolg["channel_id"].astype(str)

    merged = dim.merge(
        erfolg[["channel_id", "video_id", "log_views", "ist_kriegsvideo"]],
        on=["channel_id", "video_id"], how="inner",
    )
    kriegsvideos = merged[merged["ist_kriegsvideo"] == 1].copy()
    print(f"[Sample] {len(kriegsvideos)} Kriegsvideos ({kriegsvideos['channel_id'].nunique()} "
          f"Kanaele) - identisch zum Sample vor der KOMBI_VARIABLEN-dropna in "
          f"populismuspraemie_kriegsvideos_bericht.py::lade_kombiniertes_modell_daten().")
    return kriegsvideos


# =========================================================
# DAUER-BINS
# =========================================================

def erstelle_dauer_bins(minuten, grenzen):
    """Bins gemaess GRENZEN_MINUTEN, linke einschliessende Grenzen, letzter Bin
    offen nach oben (z.B. [3, 10, 20, 60] -> "3-10 Min"/"10-20 Min"/"20-60 Min"/
    "60+ Min"). Werte unterhalb der ersten Grenze (hier: < 3 Minuten) fallen in
    KEINEN Bin (NaN) - werden separat ausgewiesen, siehe main()."""
    labels = [f"{u}-{o} Min" for u, o in zip(grenzen, grenzen[1:])] + [f"{grenzen[-1]}+ Min"]
    bins = grenzen + [float("inf")]
    return pd.cut(minuten, bins=bins, labels=labels, right=False)


def main():
    df = lade_kombiniertes_modell_sample()

    dauer_sek = video_registry.duration_lookup(df["video_id"].tolist())
    df["dauer_sekunden"] = pd.to_numeric(df["video_id"].map(dauer_sek), errors="coerce")
    df["dauer_minuten"] = df["dauer_sekunden"] / 60

    unbekannt = df["dauer_sekunden"].isna()
    print(f"[Dauer] {int(unbekannt.sum())} von {len(df)} Videos ohne bekannte/parsebare Dauer "
          f"(contentDetails nie abgefragt) - fallen aus der Bin-Uebersicht raus.")

    unter_grenze = df["dauer_sekunden"].notna() & (df["dauer_minuten"] < GRENZEN_MINUTEN[0])
    print(f"[Dauer] {int(unter_grenze.sum())} von {len(df)} Videos unter "
          f"{GRENZEN_MINUTEN[0]} Minuten ({MIN_VIDEO_DURATION_SECONDS}s-Mindestlaengen-Filter "
          f"greift projektweit nur beim Transkript-Download, nicht rueckwirkend auf bereits "
          f"vorhandene Videos) - fallen ebenfalls aus der Bin-Uebersicht raus.")

    df["dauer_bin"] = erstelle_dauer_bins(df["dauer_minuten"], GRENZEN_MINUTEN)

    bin_reihenfolge = [f"{u}-{o} Min" for u, o in zip(GRENZEN_MINUTEN, GRENZEN_MINUTEN[1:])] \
        + [f"{GRENZEN_MINUTEN[-1]}+ Min"]
    uebersicht = (
        df.groupby("dauer_bin", observed=True)
        .agg(n_videos=("video_id", "size"), n_kanaele=("channel_id", "nunique"))
        .reindex(bin_reihenfolge)
        .fillna(0)
        .astype({"n_videos": int, "n_kanaele": int})
    )
    uebersicht["anteil_am_sample"] = (uebersicht["n_videos"] / len(df)).round(4)

    print("\n[Uebersicht je Dauer-Bin]")
    print(uebersicht.to_string())
    print(f"\n[Summe ueber alle vier Bins] {int(uebersicht['n_videos'].sum())} von {len(df)} "
          f"Videos ({uebersicht['anteil_am_sample'].sum():.1%}).")

    AUSGABE.parent.mkdir(parents=True, exist_ok=True)
    uebersicht.to_csv(AUSGABE, encoding="utf-8")
    print(f"\n[Ausgabe] -> {AUSGABE}")


if __name__ == "__main__":
    main()

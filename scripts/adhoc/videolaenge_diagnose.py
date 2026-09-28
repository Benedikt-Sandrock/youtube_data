# -*- coding: utf-8 -*-
"""
videolaenge_diagnose.py

Ad-hoc-Diagnose (.claude/CLAUDE.md: einmalige Auswertungen gehoeren nach scripts/adhoc/) zum
letzten Absatz aus .claude/Aufgaben.md: "Zudem soll geschaut werden, ob das Sample auf
bestimmte Videolaengen eingeschraenkt werden sollte. Ein kurzes 5 Minuten Video kann schwierig
mit einem Video ueber einer Stunde verglichen werden." Erster Schritt (rein deskriptive
Pruefung, OB Videolaenge ueberhaupt ein relevanter Stoerfaktor ist) VOR der eigentlichen
Integration - dieser Befund ("Videolaenge ist ein relevanter Stoerfaktor", siehe unten) hat
dazu gefuehrt, dass die Kontrollvariable log_duration_seconds/log_duration_mean UND eine
laengenbeschraenkte Sensitivitaets-Teilstichprobe seit 2026-09-08 fest in
frage4_kriegspraemie_medientyp_bericht.py und populismuspraemie_kriegsvideos_bericht.py
eingebaut sind (siehe dortige Moduldocstrings, Abschnitt "VIDEOLAENGE..."). DIESES Skript
bleibt trotzdem als eigenstaendige, rein deskriptive Diagnose bestehen (Verteilungsvergleich
+ einfache Kanal-FE-Regression ohne die vollen Kriegspraemie-/Populismuspraemie-Modelle) -
liest die bestehende channel_video_erfolg.csv nur, Dauer kommt seit prepare_success_metrics.py
::ergaenze_videodauer() bereits fest darin mit (siehe unten), kein eigener Lookup mehr noetig.

Zwei Bausteine:
(a) verteilung(): Verteilung der Videolaenge je Gruppe5-Kategorie x Kriegsvideo-Flag (Median,
    Mittelwert, Quartile) - unterscheiden sich Kriegs-/Nichtkriegsvideos bzw. die Medientypen
    systematisch in der Laenge?
(b) regression_je_umfang(): wie stark haengt der Erfolg ueberhaupt an der Videolaenge,
    unabhaengig von Gruppenzugehoerigkeit? Getrennt fuer {alle, nur Kriegsvideos, nur sonstige
    Videos} (koennte sich unterscheiden - z.B. lange Analysen/Livestreams bei Kriegsvideos vs.
    kurze News-Clips sonst). Modell: log_views ~ log_duration_seconds, Kanal-Fixed-Effects.

    WICHTIG - Within-Transformation statt C(channel_id): "alle"/"sonstige_videos" umfassen
    hunderttausende Zeilen ueber ~260 Kanaele - eine patsy-Dummy-Matrix (C(channel_id)) waere
    dort ungewoehnlich gross fuer dieses Projekt (die uebrigen Kanal-FE-Regressionen in
    step6_auswertung laufen auf deutlich kleineren, bereits aggregierten Stichproben). Stattdessen
    werden log_views und log_duration_seconds je Kanal ZENTRIERT (Kanalmittel abgezogen) und
    eine einfache OLS auf den zentrierten Werten gerechnet - das ist der Standard-"Within"-
    Schaetzer und liefert EXAKT denselben Koeffizienten wie C(channel_id) (Frisch-Waugh-Lovell),
    nur ohne die Dummy-Matrix im Speicher zu halten. Geclusterte SE (Kanalebene) wie ueberall
    sonst im Projekt.

Datenquelle: outputs/segment_analysis/channel_video_erfolg.csv (bereits vorhandene Datei, KEIN
Neulauf von prepare_success_metrics.py noetig fuer DIESES Skript). Die Dauer
(duration_seconds/log_duration_seconds) wurde urspruenglich hier lokal per
video_registry.duration_lookup() nachgeschlagen; seit die Ergebnisse dieser Diagnose in
prepare_success_metrics.py::ergaenze_videodauer() eingeflossen sind (.claude/Aufgaben.md,
Nutzervorgabe "Integriere die Videodauer in die Analyse"), liegen beide Spalten bereits FEST
in channel_video_erfolg.csv - dieses Skript liest sie nur noch, statt sie selbst zu
berechnen. Medientyp/Ideologie ueber Paketimport aus step6_auswertung (deskriptiv_
aggregation.py/deskriptiv_plots.py haben selbst keine bare-sibling-Importe, sind daher von
hier aus paketimportierbar - siehe scripts/adhoc/video_sample_uebersicht.py fuer dasselbe
Vorgehen); baue_gruppe5_lokal() aus frage2_sensitivitaet_plots.py ist NICHT paketimportierbar
(dessen eigene bare-sibling-Importe wuerden fehlschlagen) und wird deshalb als kurze lokale
Kopie nachgebildet (gleiches Vorgehen wie scripts/adhoc/dauer_verteilung_kombiniertes_modell.py).

Ausfuehrung (aus dem Projekt-Root):
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/adhoc/videolaenge_diagnose.py

Schreibt scripts/adhoc/output/videolaenge_diagnose_verteilung.csv und
scripts/adhoc/output/videolaenge_diagnose_regression.csv.
"""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from youtube_code.config import OUTPUTS
from youtube_code.step6_auswertung.deskriptiv_aggregation import lade_medientyp, lade_ideologie
from youtube_code.step6_auswertung.deskriptiv_plots import GRUPPE5_REIHENFOLGE

PFAD_ERFOLG = OUTPUTS / "segment_analysis" / "channel_video_erfolg.csv"
PFAD_OUTPUT_DIR = OUTPUTS.parent / "scripts" / "adhoc" / "output"
AUSGABE_VERTEILUNG = PFAD_OUTPUT_DIR / "videolaenge_diagnose_verteilung.csv"
AUSGABE_REGRESSION = PFAD_OUTPUT_DIR / "videolaenge_diagnose_regression.csv"


# =========================================================
# Basisdaten
# =========================================================

def baue_gruppe5_lokal(df):
    """Kurze lokale Kopie von frage2_sensitivitaet_plots.py::baue_gruppe5_lokal() (siehe
    Moduldocstring fuer die Begruendung, warum kein Paketimport moeglich ist)."""
    df = df.copy()
    ist_alt = df["medientyp"] == "Alternatives Medium"
    df["gruppe5"] = df["medientyp"]
    df.loc[ist_alt, "gruppe5"] = "Alternative Medien (" + df.loc[ist_alt, "ideologie_gruppe"].astype(str) + ")"
    vor = df["channel_id"].nunique()
    df = df[df["gruppe5"].isin(GRUPPE5_REIHENFOLGE)]
    print(f"[Gruppe5] {vor - df['channel_id'].nunique()} Kanaele ausgeschlossen "
          "(Politiker/Partei oder Alternatives Medium ohne Ideologie-Einordnung).")
    return df


def lade_basisdaten():
    df = pd.read_csv(PFAD_ERFOLG)
    df["channel_id"] = df["channel_id"].astype(str)
    df["video_id"] = df["video_id"].astype(str)

    med = lade_medientyp()
    ideo = lade_ideologie()
    df = df.merge(med, on="channel_id", how="left").merge(ideo, on="channel_id", how="left")
    df = baue_gruppe5_lokal(df)

    # duration_seconds liegt seit prepare_success_metrics.py::ergaenze_videodauer() bereits
    # fest in channel_video_erfolg.csv (siehe Moduldocstring) - hier nur noch umbenannt/
    # in Minuten umgerechnet, kein eigener duration_lookup()-Aufruf mehr noetig.
    df["dauer_sekunden"] = df["duration_seconds"]
    df["dauer_minuten"] = df["dauer_sekunden"] / 60
    unbekannt = df["dauer_sekunden"].isna().sum()
    print(f"[Dauer] {unbekannt} von {len(df)} Videos ohne bekannte/parsebare Dauer "
          "(contentDetails nie abgefragt) - fallen aus beiden Bausteinen raus.")
    return df


# =========================================================
# Baustein (a): Verteilung
# =========================================================

def verteilung(df):
    """Median/Mittelwert/Quartile der Videolaenge (Minuten) je (gruppe5, ist_kriegsvideo)."""
    gruppiert = df.dropna(subset=["dauer_minuten"]).groupby(["gruppe5", "ist_kriegsvideo"])["dauer_minuten"]
    tabelle = gruppiert.agg(
        n="size", median="median", mean="mean",
        q25=lambda x: x.quantile(0.25), q75=lambda x: x.quantile(0.75),
    ).reset_index()
    return tabelle.sort_values(["gruppe5", "ist_kriegsvideo"])


# =========================================================
# Baustein (b): Regression (Within-Transformation, siehe Moduldocstring)
# =========================================================

def regression_je_umfang(df, umfang_label):
    """log_views ~ log_duration_seconds, Kanal-FE ueber Kanal-Zentrierung (Within-Schaetzer)
    statt C(channel_id) - siehe Moduldocstring fuer die Begruendung. Geclusterte SE
    (Kanalebene)."""
    teil = df.dropna(subset=["log_views", "dauer_sekunden"]).copy()
    teil = teil[teil["dauer_sekunden"] > 0]
    teil["log_duration_seconds"] = np.log(teil["dauer_sekunden"])

    teil["log_views_z"] = teil["log_views"] - teil.groupby("channel_id")["log_views"].transform("mean")
    teil["log_duration_z"] = (teil["log_duration_seconds"]
                               - teil.groupby("channel_id")["log_duration_seconds"].transform("mean"))

    modell = smf.ols("log_views_z ~ log_duration_z", data=teil).fit(
        cov_type="cluster", cov_kwds={"groups": teil["channel_id"]})
    koef = modell.params["log_duration_z"]
    se = modell.bse["log_duration_z"]
    p = modell.pvalues["log_duration_z"]
    print(f"[Regression][{umfang_label}] n={len(teil)}, n_kanaele={teil['channel_id'].nunique()}, "
          f"log_duration_seconds: koeffizient={koef:.4f}, se={se:.4f}, p={p:.4g}")
    return {"umfang": umfang_label, "n_beobachtungen": len(teil),
            "n_kanaele": teil["channel_id"].nunique(),
            "koeffizient_log_duration": koef, "se": se, "p": p}


# =========================================================
# MAIN
# =========================================================

def main():
    df = lade_basisdaten()

    tabelle_verteilung = verteilung(df)
    PFAD_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tabelle_verteilung.to_csv(AUSGABE_VERTEILUNG, index=False, encoding="utf-8")
    print(f"\n[Verteilung] -> {AUSGABE_VERTEILUNG}")
    print(tabelle_verteilung.to_string(index=False))

    print()
    ergebnisse = [
        regression_je_umfang(df, "alle_videos"),
        regression_je_umfang(df[df["ist_kriegsvideo"] == 1], "kriegsvideos"),
        regression_je_umfang(df[df["ist_kriegsvideo"] == 0], "sonstige_videos"),
    ]
    tabelle_regression = pd.DataFrame(ergebnisse)
    tabelle_regression.to_csv(AUSGABE_REGRESSION, index=False, encoding="utf-8")
    print(f"\n[Regression] -> {AUSGABE_REGRESSION}")


if __name__ == "__main__":
    main()

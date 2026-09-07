# -*- coding: utf-8 -*-
"""
prepare_success_metrics.py

Bereitet Views/Engagement aus video_registry.sqlite als Erfolgsmetrik-
Zeitreihe auf, analog zu prepare_channel_scores.py fuer die LLM-Scores
(Schritt 0 dieses Ordners). Grundlage fuer die Forschungsfragen 2-4
(.claude/CLAUDE.md: "Wie hat sich der Erfolg der Kanaele entwickelt?
Werden populistische Kanaele erfolgreicher? Werden Kanaele, die
populistischer werden, auch erfolgreicher? Betrifft das nur Kriegsvideos
oder auch andere Videos?"). Siehe .claude/plans/success_analysis.md fuer
die vollstaendige Herleitung und outputs/segment_analysis/
frage2_4_methodik_und_stichprobe.md fuer die Methodik-Dokumentation.

Laeuft NACH prepare_channel_scores.py (Schritt 0, liefert
channel_video_populism.csv fuer die Kriegsvideo-Whitelist-Herleitung) und
NACH frage1_stichprobe.py (Schritt 0b, liefert frage1_kanal_whitelist.csv).
Als -m-Modul ausfuehren (echter Paketimport von
youtube_code.step6_auswertung.prepare_channel_scores fuer
ergaenze_periodenspalten(), nicht dupliziert):

    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        -m youtube_code.step6_auswertung.prepare_success_metrics

Zwei zentrale Designentscheidungen (siehe success_analysis.md fuer die
vollstaendige Begruendung):

1. Views/Abos liegen nur als EINMALIGER Snapshot vor (video_registry:
   COALESCE-Upsert ueberschreibt nie einen bestehenden Wert) - Erfolg wird
   daher ausschliesslich ueber Video-Performance gemessen (view_count/
   engagement_rate je Video, einsortiert nach published_at in Vorkriegs-/
   Nachkriegsperioden), nicht ueber Abo-Wachstum. Kein neuer API-Pull fuer
   einen zweiten Snapshot.
2. Rohe view_count-Werte werden OHNE Division durch Tage-seit-
   Veroeffentlichung verwendet (kein Views-pro-Tag) - die meisten Videos
   sammeln den Grossteil ihrer Views kurz nach Veroeffentlichung, eine
   Alters-Normalisierung wuerde aeltere, laengst plateauierte Videos
   systematisch bestrafen. age_days wird nur als Kontext/Diagnose
   mitgefuehrt (Sensitivitaetsanalyse), nicht zur Normalisierung.

engagement_rate = (like_count + comment_count) / view_count wird OHNE
fillna(0) auf like_count/comment_count berechnet: beide Spalten sind in
video_registry.sqlite nullable und ein fehlender Wert bedeutet "von der
API nie geliefert" (z.B. deaktivierte Likes/Kommentare bei diesem Video),
NICHT "0 Interaktionen" (siehe get_video_stats()-Docstring in
video_registry.py). Ein fillna(0) wuerde Kanaele mit deaktivierten Likes/
Kommentaren faelschlich als "wenig Engagement" einstufen. pandas
propagiert NaN automatisch durch +/-, engagement_rate wird fuer
betroffene Videos also korrekt NaN.

Neben dem Mittelwert je Kanal x Periode wird zusaetzlich die SUMME aller
Views (view_count_summe, davon abgeleitet log_views_summe =
log1p(view_count_summe)) berechnet - macht Kanaele sichtbar, die durch
hoehere Aktivitaet (mehr Videos) insgesamt mehr Reichweite erzielen, ohne
dass der Durchschnitt pro Video steigt.

Outputs (outputs/segment_analysis/):
  - channel_video_erfolg.csv: Video-Ebene, eine Zeile je Video.
  - channel_{quartal,monat}_erfolg_timeseries.csv: Long-Format wie die
    bestehenden channel_{gran}_populism_timeseries.csv, Dimensionen
    {view_count, log_views, engagement_rate, view_count_summe,
    log_views_summe}.
  - channel_{quartal,monat}_erfolg_kriegsvideos_timeseries.csv: dieselbe
    Aggregation/Dimensionen wie oben, aber NUR ueber Videos mit
    ist_kriegsvideo == 1 (Topic TOPIC, siehe _ergaenze_kriegsvideo_flag()) -
    Grundlage fuer deskriptiv_plots.py::NUR_TOPICVIDEOS (Forschungsfrage 4:
    "Betrifft eine Erfolgssteigerung nur Kriegsvideos oder auch andere
    Videos?"). Wird ueber deskriptiv_aggregation.py::MODUS = "erfolg_kriegsvideos"
    zu deskriptiv_erfolg_kriegsvideos_{granularitaet}.csv weiterverarbeitet
    (Medientyp/Ideologie/Whitelist wie beim gewoehnlichen MODUS = "erfolg").
  - channel_erfolg_snapshot.csv: rein deskriptiver Kanal-Kontext
    (Abonnenten/Views/Video-Anzahl, EINMALIGER Snapshot) - explizit NICHT
    Teil der Pre/Post-Regression.
"""

import os

import numpy as np
import pandas as pd

from youtube_code.config import OUTPUTS
from youtube_code.step6_auswertung.prepare_channel_scores import (
    GRANULARITAETEN, ergaenze_periodenspalten,
)
from youtube_code.store import video_registry

RESULTS_PATH = OUTPUTS / "segment_analysis"
os.makedirs(RESULTS_PATH, exist_ok=True)

PFAD_WHITELIST = RESULTS_PATH / "frage1_kanal_whitelist.csv"
PFAD_VIDEO_EBENE = RESULTS_PATH / "channel_video_erfolg.csv"
PFAD_ZEITREIHE = RESULTS_PATH / "channel_{granularitaet}_erfolg_timeseries.csv"
PFAD_ZEITREIHE_KRIEGSVIDEOS = RESULTS_PATH / "channel_{granularitaet}_erfolg_kriegsvideos_timeseries.csv"
PFAD_SNAPSHOT = RESULTS_PATH / "channel_erfolg_snapshot.csv"

TOPIC = "russia_ukraine_war"

# Kein Fetch-Zeitstempel in video_registry.sqlite gespeichert (siehe
# success_analysis.md, Limitation 2) - REFERENZDATUM naehert den
# Datenabruf-Zeitpunkt ueber "heute" an. age_days ist reine Kontext-/
# Diagnosespalte (Sensitivitaetsanalyse: Ausschluss sehr junger Videos),
# NICHT Teil der Erfolgsmetrik selbst - die Naeherung hat daher keinen
# Einfluss auf view_count/log_views/engagement_rate.
REFERENZDATUM = pd.Timestamp.today().normalize()


# =========================================================
# DATEN LADEN
# =========================================================

def _lade_whitelist():
    """Liest frage1_kanal_whitelist.csv - dieselbe Whitelist wie Forschungsfrage 1
    (siehe success_analysis.md Punkt 3: maximale Vergleichbarkeit zwischen allen
    vier Forschungsfragen, Frage 3/4 brauchen ohnehin den Populismus-Score bzw.
    das Kriegsvideo-Flag, die nur fuer diese Whitelist-Kanaele systematisch vorliegen)."""
    whitelist = pd.read_csv(PFAD_WHITELIST)
    whitelist["channel_id"] = whitelist["channel_id"].astype(str)
    return whitelist["channel_id"].tolist()


def _lade_video_stats(channel_ids):
    stats = video_registry.get_video_stats(channel_ids=channel_ids)
    stats["channel_id"] = stats["channel_id"].astype(str)
    stats["published_at"] = pd.to_datetime(
        stats["published_at"], errors="coerce", utc=True
    ).dt.tz_localize(None)

    # ergaenze_periodenspalten() (prepare_channel_scores.py) verlangt ein vollstaendiges
    # Datum je Zeile - vereinzelte Videos ohne bekanntes published_at (seltener Fetch-Rest,
    # analog "ohne_datum"-Filter in prepare_channel_scores.py::_video_populismus()/
    # prepare_position_results()) muessen daher vorher raus.
    ohne_datum = stats["published_at"].isna()
    if ohne_datum.any():
        print(f"[Video-Stats] {int(ohne_datum.sum())} von {len(stats)} Videos ohne published_at "
              f"-> verworfen (kann keiner Periode zugeordnet werden).")
        stats = stats[~ohne_datum]

    return stats


def _ergaenze_kriegsvideo_flag(df):
    """Merged video_registry.get_topic_relevance(topic="russia_ukraine_war").
    Videos OHNE Eintrag in video_topic_relevance gelten explizit als
    ist_kriegsvideo = 0 ("nicht als kriegsbezogen klassifiziert" - die
    Keyword-Klassifikation lief ueber ALLE bekannten Videos, ein fehlender
    Eintrag ist also keine Wissensluecke, sondern schlicht "kein Treffer"),
    NICHT als "unbekannt"/NaN."""
    relevanz = video_registry.get_topic_relevance(topic=TOPIC, video_ids=df["video_id"].tolist())
    relevante_ids = set(relevanz.loc[relevanz["is_relevant"] == 1, "video_id"])
    df["ist_kriegsvideo"] = df["video_id"].isin(relevante_ids).astype(int)

    n_kriegsvideos = int(df["ist_kriegsvideo"].sum())
    print(f"[Kriegsvideo-Flag] {n_kriegsvideos} von {len(df)} Videos als kriegsbezogen "
          f"markiert (topic={TOPIC!r}, video_topic_relevance.is_relevant == 1; "
          f"kein Eintrag -> 0, siehe Docstring).")
    return df


# =========================================================
# ERFOLGSMETRIKEN
# =========================================================

def berechne_erfolgsmetriken(df):
    """Siehe Moduldocstring fuer die vollstaendige Begruendung: rohe view_count-
    Werte ohne Alters-Normalisierung, engagement_rate OHNE fillna(0) auf
    like_count/comment_count (NaN bleibt NaN statt faelschlich 0)."""
    n_vor = len(df)
    ohne_views = df["view_count"].isna()
    if ohne_views.any():
        print(f"[Erfolgsmetriken] {int(ohne_views.sum())} von {n_vor} Videos ohne "
              f"view_count -> verworfen.")
    df = df[~ohne_views].copy()

    df["log_views"] = np.log1p(df["view_count"])
    df["engagement_rate"] = (df["like_count"] + df["comment_count"]) / df["view_count"].replace(0, np.nan)
    df["age_days"] = (REFERENZDATUM - df["published_at"]).dt.days

    ohne_engagement = df["engagement_rate"].isna()
    if ohne_engagement.any():
        print(f"[Erfolgsmetriken] {int(ohne_engagement.sum())} von {len(df)} Videos mit "
              f"engagement_rate = NaN (like_count und/oder comment_count fehlt in der "
              f"Registry, z.B. deaktivierte Kommentare/Likes - bewusst NICHT als 0 "
              f"interpretiert, siehe Moduldocstring).")

    return df


def aggregiere_kanal_periode_erfolg(df, spalte_periode):
    """Video-Ebene -> Kanal x Periode. Neben den Mittelwert-Dimensionen
    (view_count, log_views, engagement_rate) zusaetzlich die Summe aller
    Views (view_count_summe, davon abgeleitet log_views_summe =
    log1p(Summe) - NICHT die Summe der bereits logarithmierten log_views-
    Werte, log1p(sum(x)) != sum(log1p(x))). engagement_rate nutzt weiterhin
    "mean" (schliesst NaN automatisch aus); die zugehoerige Zaehlspalte
    (n_videos_engagement, zaehlt nur Nicht-NaN-Werte via "count") ist
    bewusst dimensionsspezifisch statt identisch mit dem allgemeinen
    n_videos (Muster analog prepare_channel_scores.py::
    prepare_position_results(), n_videos_<dimension>)."""
    grouped = df.groupby(["channel_id", "channel_title", spalte_periode], as_index=False).agg(
        view_count=("view_count", "mean"),
        log_views=("log_views", "mean"),
        engagement_rate=("engagement_rate", "mean"),
        view_count_summe=("view_count", "sum"),
        n_videos=("video_id", "count"),
        n_videos_engagement=("engagement_rate", "count"),
    )
    grouped["log_views_summe"] = np.log1p(grouped["view_count_summe"])
    return grouped


DIMENSIONEN_ZEITREIHE = ["view_count", "log_views", "engagement_rate", "view_count_summe", "log_views_summe"]


def _als_zeitreihe(grouped, spalte_periode):
    """Kanal x Periode (breit, eine Spalte je Dimension) -> Long-Format, wie
    channel_{gran}_populism_timeseries.csv. n_videos_engagement wird pro
    Zeile mitgefuehrt (nur bei dimension == "engagement_rate" inhaltlich
    abweichend von n_videos, siehe aggregiere_kanal_periode_erfolg())."""
    lang = grouped.melt(
        id_vars=["channel_id", "channel_title", spalte_periode, "n_videos", "n_videos_engagement"],
        value_vars=DIMENSIONEN_ZEITREIHE,
        var_name="dimension",
        value_name="wert",
    )
    return lang


# =========================================================
# MAIN
# =========================================================

def main():
    channel_ids = _lade_whitelist()
    print(f"[Whitelist] {len(channel_ids)} Kanal-IDs aus {PFAD_WHITELIST}.")

    video_ebene = _lade_video_stats(channel_ids)
    print(f"[Video-Stats] {len(video_ebene)} Videos, {video_ebene['channel_id'].nunique()} "
          f"Kanaele aus video_registry.get_video_stats().")

    video_ebene = _ergaenze_kriegsvideo_flag(video_ebene)
    video_ebene = ergaenze_periodenspalten(video_ebene)
    video_ebene = berechne_erfolgsmetriken(video_ebene)

    spalten = ["channel_id", "channel_title", "video_id", "published_at", "rel_quartal", "rel_monat",
               "view_count", "like_count", "comment_count", "log_views", "engagement_rate", "age_days",
               "ist_kriegsvideo"]
    video_ebene[spalten].to_csv(PFAD_VIDEO_EBENE, index=False, encoding="utf-8")
    print(f"[Ausgabe] {len(video_ebene)} Videos -> {PFAD_VIDEO_EBENE}")

    kriegsvideos = video_ebene[video_ebene["ist_kriegsvideo"] == 1]

    for granularitaet, cfg in GRANULARITAETEN.items():
        spalte = cfg["spalte"]
        grouped = aggregiere_kanal_periode_erfolg(video_ebene, spalte)
        lang = _als_zeitreihe(grouped, spalte)

        pfad = str(PFAD_ZEITREIHE).format(granularitaet=cfg["datei_suffix"])
        lang.to_csv(pfad, index=False, encoding="utf-8")
        print(f"[Zeitreihe][{granularitaet}] {lang['channel_id'].nunique()} Kanaele, "
              f"{grouped[spalte].nunique()} Perioden, {len(lang)} Zeilen -> {pfad}")

        # NEU: dieselbe Aggregation nur ueber Kriegsvideos (ist_kriegsvideo == 1) -
        # Grundlage fuer deskriptiv_plots.py::NUR_TOPICVIDEOS (Forschungsfrage 4), siehe
        # Moduldocstring.
        grouped_kv = aggregiere_kanal_periode_erfolg(kriegsvideos, spalte)
        lang_kv = _als_zeitreihe(grouped_kv, spalte)

        pfad_kv = str(PFAD_ZEITREIHE_KRIEGSVIDEOS).format(granularitaet=cfg["datei_suffix"])
        lang_kv.to_csv(pfad_kv, index=False, encoding="utf-8")
        print(f"[Zeitreihe-Kriegsvideos][{granularitaet}] {lang_kv['channel_id'].nunique()} Kanaele, "
              f"{grouped_kv[spalte].nunique() if len(grouped_kv) else 0} Perioden, "
              f"{len(lang_kv)} Zeilen -> {pfad_kv}")

    snapshot = video_registry.get_channels(channel_ids=channel_ids)
    snapshot_spalten = [s for s in ["channel_id", "title", "subscribers", "views", "video_count"]
                        if s in snapshot.columns]
    snapshot = snapshot[snapshot_spalten]
    snapshot.to_csv(PFAD_SNAPSHOT, index=False, encoding="utf-8")
    print(f"[Snapshot] {len(snapshot)} Kanaele (rein deskriptiver Kontext, EINMALIGER "
          f"API-Snapshot, NICHT Teil der Pre/Post-Regression) -> {PFAD_SNAPSHOT}")


if __name__ == "__main__":
    main()

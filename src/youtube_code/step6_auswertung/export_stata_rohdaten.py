"""Exportiert den Rohdatensatz fuer die Stata-Do-Files (Bloecke 1-3) - der
Hauptdatensatz des Projekts (seit 13.10.2026; enthaelt auch alles aus dem
frueheren scripts/adhoc/output/kriegspraemie/videos_kriegspraemie.dta).

Verbindliche Spezifikation: docs/codebuch_rohdatensatz.md (inkl. Abschnitt
"Entscheidungen zur Umsetzung"). Der Export bleibt so roh wie moeglich: keine
Logs, keine Aggregation ueber Videos auf Videoebene. Ausnahmen: die Messregel
"deskriptiv"-Segmente = 0 bei den Positionsskalen sowie die Hilfsvariablen
post_war und monat.

Population Videos: ALLE Videos der Sample-Kanaele, kein Laengenfilter. Das
Kennzeichen min_dauer (dauer_sek >= 181) ersetzt den frueheren Filter:
Analysen mit LLM-Klassifikationen (pop_*/pos_*) muessen auf min_dauer == 1
einschraenken (AP-1-Befund, siehe Codebuch). Alle Kanalgroessen
(n_videos, erstes_video_ts, sample_vorkrieg, baseline_stichprobe,
pop_baseline, ideo_*_baseline) werden weiterhin nur aus Videos mit
min_dauer == 1 berechnet und bleiben damit gegenueber dem Export mit Filter
unveraendert.

Ausgabe (AUSGABE_PFAD = outputs/stata_rohdaten/)
------------------------------------------------
- videos_roh.dta   eine Zeile je Video (Sample-Kanaele, alle Laengen)
- kanaele_roh.dta  eine Zeile je Kanal des Kanal-Samples
- export_log.txt   Fallzahlen, Merge-Bilanzen, Abdeckung, Konsistenzpruefungen
- check_rohdaten.do  Pruef-Do-File (describe, codebook, isid, merge-Bilanz)

Quellen (ausschliesslich die Stores bzw. ihre Zugriffsmodule)
------------------------------------------------------------
- Kanal-Sample: data/samples/<ANALYSIS_ID>/channel_sample_provenance.csv
  (wie prepare_channel_scores.py).
- Videos/Metriken/Dauer: video_registry.get_video_stats(channel_ids=...).
- politisch: video_registry.politics_topic_lookup() (YouTube-topic_categories
  "Politics"), NICHT screening_state.politics_final.
- Titel: video_registry.get_video_metadata(min_duration_seconds=None).
- rel_<topic>_core/_cw: Stichwortsuche NUR im Titel, live berechnet mit den
  Regexen aus step3_topic_relevance.topic_keywords (KW_RE), fuer alle Themen
  in TOPIC_KEYWORDS und alle Videos (wie frueher videos_kriegspraemie.dta).
  video_topic_relevance (Titel + Beschreibung, nur Videos > 180 s) wird nur
  noch intern fuer die Ideologie-Baseline (Ausschluss von Kriegsvideos)
  gelesen und nicht exportiert.
- format/format_quelle: video_registry.get_video_formats() (Tabelle
  video_format, step1_sample/channel_video_formats.py); Laufstatus je Kanal
  aus data/channel_lists/video_formats/*_formats_status.csv.
- news_show/special_show/pk_sitzung: step3_topic_relevance.news_show_patterns
  (Kategorien NEWS/SPECIAL/PRESSE), nur fuer Kanaele mit geprueften
  Titelmustern (FORMAT_LISTEN, drei Listen), sonst '.'.
- Kanalmetadaten: video_registry.get_channels().
- Kanaltypologie (kanaltyp*, sample_kern): manuelle Codierung
  data/external/kanal_typologie.csv (nur Whitelist-Kanaele; Typdefinitionen
  im Codebuch, Grenzfaelle in scripts/adhoc/outputs/
  kanal_typologie_grenzfaelle.md).
- Transkript: transcript_store.has_transcript().
- Baseline-Zugehoerigkeit: screening_state_store.get_state() (interval_index
  in BASELINE_INTERVAL_INDIZES) - wird NUR fuer baseline_stichprobe und die
  daraus berechneten Kanal-Baselines verwendet, alle uebrigen Zeitbezuege
  kommen aus published_at.
- LLM-Ergebnisse: llm_run_store.get_results_for_prompt() fuer POPULISMUS_P,
  POSITION_V1, IDEOLOGIE_I (Original-Runs; Test-Runs ausgeschlossen wie in
  prepare_channel_scores.py).

Abweichungen von prepare_channel_scores.py (bewusst, siehe Codebuch)
-------------------------------------------------------------------
- Deduplizierung auf SEGMENT-Ebene (video_id, segment_index): Segmente ohne
  parse_error haben Vorrang, sonst gewinnt der neueste run_id. In
  prepare_channel_scores.py gewinnt der neueste Run pro Video. Beim Lauf
  vom 02.10.2026 war das Ergebnis identisch (alle Mehrfach-Runs, auch die
  Parse-Error-Nachlaeufe run_0030/run_0031, umfassten jeweils ganze Videos);
  die Segment-Regel bleibt robust, falls ein Nachlauf nur Teile eines
  Videos enthaelt.
- Kanal-Baselines werden nach channel_id gruppiert (dort channel_id +
  channel_title, wodurch Kanaele mit Titelaenderung zerfallen koennen).
- Ideologie-Baseline nur aus Baseline-Videos ohne Kriegsbezug (krieg == 1
  oder krieg_transkript == 1 ausgeschlossen), Segment -> Video -> Kanal.

Ausfuehren aus dem Repo-Root als Paketmodul (importiert prepare_channel_scores):
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.export_stata_rohdaten
"""

import os

import numpy as np
import pandas as pd

from youtube_code.config import CHANNEL_LISTS, OUTPUTS, EXTERNAL, SAMPLES, MIN_VIDEO_DURATION_SECONDS
from youtube_code.store import llm_run_store, screening_state_store, transcript_store, video_registry
from youtube_code.step3_topic_relevance.news_show_patterns import NEWS, PRESSE, SPECIAL, classify_frame
from youtube_code.step3_topic_relevance.topic_keywords import KW_RE, TIERS, TOPIC_KEYWORDS
from youtube_code.step6_auswertung.prepare_channel_scores import (
    BASELINE_INTERVAL_INDIZES,
    EXCLUDE_DATASET_SUBSTRING,
    GESAMTSCORE_AUS,
    KRIEGSBEGINN,
    POPULISM_VARS,
    PROMPT_IDEOLOGIE,
    PROMPT_POPULISMUS,
    PROMPT_POSITION,
    SOURCE,
    _korrigiere_populismus,
    _korrigiere_position,
    relativ_periode,
)

# =========================================================
# CONFIG
# =========================================================

ANALYSIS_ID = "russia_longitudinal_v1"
KANAL_SAMPLE_PFAD = SAMPLES / ANALYSIS_ID / "channel_sample_provenance.csv"
WHITELIST_PFAD = OUTPUTS / "segment_analysis" / "frage1_kanal_whitelist.csv"
MEDIENTYP_PFAD = EXTERNAL / "media_type_russia_merged.xlsx"
# Kanaele mit Flag "playlist_limit" (~20.000er-Limit der Uploads-Playlist),
# per yt-dlp-Nachscraping am 01.10.2026 behoben.
API_ABBRUCH_PFAD = OUTPUTS / "segment_analysis" / "datenluecken_quartale" / "auffaelligkeiten.csv"

AUSGABE_PFAD = OUTPUTS / "stata_rohdaten"

# min_dauer = 1: Dauer >= MIN_VIDEO_DURATION_SECONDS (181 s, d. h. > 180 s).
# Kein Filter mehr, nur Kennzeichen; Kanalgroessen nutzen nur min_dauer == 1.
MIN_DAUER_SEK = MIN_VIDEO_DURATION_SECONDS
# sample_vorkrieg: in der Frage-1-Whitelist UND >= 1 Video (> 180 s) in
# [VORKRIEG_START, KRIEGSBEGINN)
VORKRIEG_START = "2021-02-24"
VORKRIEG_MIN_VIDEOS = 1

# Medientyp: Rohcodes aus MEDIENTYP_PFAD -> Codebuch-Kodierung
# (Roh: 1 ÖRR, 2 traditionell, 3 Alternatives Medium, 4 Politiker/Partei,
#  5 Sonderfall ÖRR-nah, bisher zu ÖRR gezaehlt - siehe deskriptiv_aggregation.TYP5_ZU_1)
MEDIENTYP_UMKODIERUNG = {1: 1, 2: 2, 3: 4, 4: 3, 5: 1}
MEDIENTYP_LABELS = {1: "ÖRR", 2: "traditionelle Medien", 3: "Partei/Politiker",
                    4: "Creator & alternative Medien"}

# Kanaltypologie (manuell, 15+1 Typen in drei Gruppen; Definitionen im
# Codebuch, Grenzfallentscheidungen in
# scripts/adhoc/outputs/kanal_typologie_grenzfaelle.md). Codiert sind genau
# die Whitelist-Kanaele, alle uebrigen bekommen '.'.
# Numerischer Code: Zehnerstelle = Gruppe (1 A, 2 B, 3 C), Einerstelle = Typ.
KANALTYP_PFAD = EXTERNAL / "kanal_typologie.csv"
KANALTYP_LABELS = {
    11: "A1 ÖRR-Nachrichten", 12: "A2 Private Nachrichten", 13: "A3 Private Nachrichten regional/lokal",
    14: "A4 Auslandsrundfunk", 15: "A5 Magazin/Reportage/Doku", 16: "A6 Satire & Comedy",
    17: "A7 Unterhaltung/Sport/Kinder", 18: "A8 Senderhauptkanal Mischprogramm",
    21: "B1 Alternative Portale", 22: "B2 Einzelkommentatoren/Journalisten-Creator",
    23: "B3 Anonyme Politikkanäle", 24: "B4 Parteien/Politiker/Organisationen",
    31: "C1 Wirtschaft & Finanzen", 32: "C2 Wissen/Bildung/Technik",
    33: "C3 Unterhaltung/Reaction/Podcasts", 34: "C4 Lifestyle/Coaching/Esoterik",
}
KANALTYP_CODES = {label.split()[0]: code for code, label in KANALTYP_LABELS.items()}
KANALTYP_GRUPPE_LABELS = {1: "A Etablierte Medien", 2: "B Politisch-alternativ & Akteure", 3: "C Themenkanäle"}
KANALTYP_SICHER_LABELS = {1: "hoch", 2: "mittel", 3: "niedrig"}
# sample_kern: Typen mit moeglichst homogenem Nachrichten-/Meinungsangebot
# (Entscheidung 14.10.2026; A3/A4/A8 bewusst draussen) ohne Einzelausschluesse
SAMPLE_KERN_TYPEN = ["A1", "A2", "A5", "B1", "B2", "B3", "C1"]
SAMPLE_KERN_AUSSCHLUSS = {
    "UCAU09OnUvIPwe19RdrJBg0w": "Kurbel TV: umgewidmeter Kanal (vor Kriegsbeginn Retro-Filme)",
}

# Titel-Topics: je Thema aus TOPIC_KEYWORDS rel_<topic>_core (nur core-Liste =
# Hauptdefinition) und rel_<topic>_cw (core ODER wide = Robustheit). Neue
# Themen in TOPIC_KEYWORDS kommen automatisch dazu. Nur intern (Ausschluss
# von Kriegsvideos aus der Ideologie-Baseline) wird zusaetzlich
# video_topic_relevance[KRIEG_TOPIC] (Titel + Beschreibung) gelesen.
KRIEG_TOPIC = "russia_ukraine_war"
REL_SPALTEN = [f"rel_{t}_{v}" for t in TOPIC_KEYWORDS for v in ("core", "cw")]

# Videoformat (step1_sample/channel_video_formats.py). Fenster wie dort
# PUBLISHED_AFTER/PUBLISHED_BEFORE (nicht importiert, weil das Modul beim
# Import einen API-Client baut) - ausserhalb gibt es kein Format.
FORMAT_LISTEN_DIR = CHANNEL_LISTS / "video_formats"
FORMAT_FENSTER = ("2021-01-01", "2026-07-01")
# Kanallisten mit geprueften Sendungs-Titelmustern (news_show_patterns.py)
# -> Code fuer kanaele_roh.format_liste. Nur fuer diese Kanaele werden
# news_show/special_show/pk_sitzung berechnet (sonst .). Dateinamen duerfen
# nicht auf _formats_status.csv enden (lade_format_status() liest per Glob);
# ein Kanal darf nur in einer Liste stehen (lade_format_listen() prueft das).
FORMAT_LISTEN = {"upload_starke_kanaele.csv": 1, "alt_kanaele.csv": 2, "weitere_kanaele.csv": 3}
FORMAT_LISTEN_LABELS = {0: "keine", 1: "upload-starke Kanaele", 2: "alt_kanaele",
                        3: "weitere Kanaele (Sendungsmuster)"}
# WELT: yt-dlp-Fallback fuer /videos endet ca. Juli 2025 (siehe
# step1_sample/README.md), Shorts (/shorts) und Livestreams (/streams) sind
# aber vollstaendig -> Videos ohne Format im Fenster per Ausschluss "long"
# (format_derived = 1; ggf. inkl. inzwischen geloeschter/privater Videos).
# Regel uebernommen aus step8_targeted_analysis/preparation.py.
FORMAT_AUSSCHLUSS_LONG = {"UCZMsvbAhhRblVGXmEXW8TSA"}

# Manuelle Hinweise je Kanal (Freitext, kanal_hinweis). Typ-5-Kanaele werden
# automatisch ergaenzt.
KANAL_HINWEISE = {
    "UCQGqiGhMjc_p4lZEhSTb12g": "NIUS; erstellt 05.10.2022, erstes Video 31.01.2023; "
                                "Vorlaeuferformat 'Achtung, Reichelt!' ist eigener Kanal UCcoQ3WG2J_Xjwwyt-sJqh-w",
    "UCcoQ3WG2J_Xjwwyt-sJqh-w": "Achtung, Reichelt!; erstellt 07.04.2022; Format spaeter bei NIUS "
                                "(UCQGqiGhMjc_p4lZEhSTb12g)",
    "UCsFtUYhrGmOck_UeVPD-AJQ": "WDR aktuell; Kanal laut yt-dlp am 01.10.2026 nicht mehr vorhanden",
    "UCAU09OnUvIPwe19RdrJBg0w": "Kurbel TV; umgewidmeter Kanal (vor Kriegsbeginn Retro-Filme, danach "
                                "Bundestagsreden-Clips), nicht in sample_kern",
    "UCf4WJRXsgDEP7KH2eNGv8Hw": "Serge Menga; kanaltyp B2 (Kommentator ohne Mandat), medientyp bewusst "
                                "unveraendert Partei/Politiker",
    "UCqZSdUJqd2T0oqr6BEA3ONw": "Oli; Titelstil identisch mit Olli/MENTALE FITNESS, evtl. ein Betreiber",
    "UCC6MaGWuQS-t7k0TBkA5ZXQ": "Olli; Titelstil identisch mit Oli/MENTALE FITNESS, evtl. ein Betreiber",
    "UC5w2aXFKL_kLWSattQ6ekmQ": "MENTALE FITNESS; Titelstil identisch mit Oli/Olli, evtl. ein Betreiber",
}

# Toleranz fuer Pruefung 6 (pop_baseline vs. Nachberechnung aus videos_roh)
BASELINE_TOLERANZ = 1e-9


# =========================================================
# Hilfsfunktionen
# =========================================================

LOG_ZEILEN = []


def log(text="", nur_datei=False):
    if not nur_datei:
        print(text, flush=True)
    LOG_ZEILEN.append(str(text))


class KonsistenzFehler(Exception):
    pass


def pruefe(bedingung, meldung):
    if not bedingung:
        log(f"[Check] VERSTOSS: {meldung}")
        schreibe_log()
        raise KonsistenzFehler(meldung)
    log(f"[Check] ok: {meldung}")


def schreibe_log():
    os.makedirs(AUSGABE_PFAD, exist_ok=True)
    (AUSGABE_PFAD / "export_log.txt").write_text("\n".join(LOG_ZEILEN) + "\n", encoding="utf-8")


def zu_utc_naiv(serie):
    """ISO-8601-Strings (gemischte Formate) -> tz-naiver UTC-Zeitpunkt fuer %tc."""
    return pd.to_datetime(serie, format="ISO8601", utc=True, errors="coerce").dt.tz_localize(None)


def merge_bilanz(name, links_ids, rechts_ids):
    links_ids, rechts_ids = set(links_ids), set(rechts_ids)
    log(f"[Merge] {name}: {len(links_ids & rechts_ids)} gematcht, "
        f"{len(links_ids - rechts_ids)} nur Export, {len(rechts_ids - links_ids)} nur Quelle")


# =========================================================
# Laden
# =========================================================

def lade_kanaele():
    sample = pd.read_csv(KANAL_SAMPLE_PFAD, usecols=["channel_id", "eligible_current_analysis"])
    kanal_ids = sorted(sample.loc[sample["eligible_current_analysis"] == True, "channel_id"].astype(str))
    log(f"[Laden] Kanal-Sample {ANALYSIS_ID}: {len(kanal_ids)} Kanaele")
    return kanal_ids


def lade_videos(kanal_ids):
    v = video_registry.get_video_stats(channel_ids=kanal_ids)
    titel = video_registry.get_video_metadata(channel_ids=kanal_ids, min_duration_seconds=None)
    v = v.merge(titel[["video_id", "title"]].rename(columns={"title": "titel"}), on="video_id", how="left")
    v["upload_ts"] = zu_utc_naiv(v["published_at"])
    v["dauer_sek"] = video_registry._duration_seconds_series(v["duration"])
    log(f"[Laden] Videos der Sample-Kanaele (alle Laengen): {len(v)}, ohne Titel: {int(v['titel'].isna().sum())}")
    log(f"[Laden] ohne channel_id: {int(v['channel_id'].isna().sum())}, "
        f"ohne/unparsebares published_at: {int(v['upload_ts'].isna().sum())}, "
        f"ohne/unparsebare Dauer: {int(v['dauer_sek'].isna().sum())}")
    pruefe(not v["video_id"].duplicated().any(), "video_id in der Registry eindeutig")
    return v


def lade_llm(prompt_id, gueltig_spalte):
    """Alle Ergebnisse eines Prompts, Test-Runs ausgeschlossen, Segment-Dedup:
    gueltige Zeilen (ohne parse_error, Pflichtfeld gesetzt) vor ungueltigen,
    danach neuester run_id."""
    df = llm_run_store.get_results_for_prompt(prompt_id, source=SOURCE)
    test = df["dataset_id"].fillna("").str.contains(EXCLUDE_DATASET_SUBSTRING, case=False)
    log(f"[Laden] {prompt_id}: {len(df)} Segmentzeilen aus {df['run_id'].nunique()} Runs; "
        f"Test-Runs ausgeschlossen: {sorted(df.loc[test, 'run_id'].unique())} ({int(test.sum())} Zeilen)")
    df = df[~test].copy()

    df["_gueltig"] = df["parse_error"].isna()
    if gueltig_spalte is not None:
        df["_gueltig"] &= df[gueltig_spalte].notna()
    df = df.sort_values(["video_id", "segment_index", "_gueltig", "run_id"])
    schluessel = ["video_id", "segment_index"]
    doppelt = df.duplicated(schluessel, keep=False)
    if doppelt.any():
        mehrfach = df[doppelt]
        sha_abweichend = (mehrfach.groupby(schluessel)["text_sha1"].nunique() > 1).sum()
        log(f"[Laden] {prompt_id}: {mehrfach[schluessel].drop_duplicates().shape[0]} Segmente in mehreren Runs "
            f"({mehrfach['video_id'].nunique()} Videos), davon mit abweichendem Segmenttext (text_sha1): "
            f"{int(sha_abweichend)}")
    df = df.drop_duplicates(schluessel, keep="last")
    log(f"[Laden] {prompt_id}: nach Segment-Dedup {len(df)} Segmente, {df['video_id'].nunique()} Videos, "
        f"davon ungueltig (parse_error/leer): {int((~df['_gueltig']).sum())}")
    return df


# =========================================================
# Videoebene: Klassifikationen
# =========================================================

def run_liste(serie):
    return ";".join(sorted(set(serie)))


def video_populismus(pop):
    pop = _korrigiere_populismus(pop)
    pop["_nicht_kodierbar"] = (pop["kodierbar"] == False).astype(int)
    pop["_ukraine"] = (pop["ukraine_bezug"] == True).astype(int)
    v = pop.groupby("video_id").agg(
        pop_volk=("volkszentrismus", "mean"),
        pop_antielite=("antielitismus", "mean"),
        pop_manich=("manichaeische_moralisierung", "mean"),
        pop_emotion=("emotionale_intensitaet", "mean"),
        pop_n_seg=("segment_index", "size"),
        pop_n_seg_nichtkodierbar=("_nicht_kodierbar", "sum"),
        pop_n_seg_ukraine=("_ukraine", "sum"),
        pop_run=("run_id", run_liste),
    ).reset_index()
    # Gesamtscore auf Videoebene aus den Video-Mittelwerten der drei
    # GESAMTSCORE_AUS-Dimensionen (wie prepare_channel_scores._video_populismus)
    quelle = {"volkszentrismus": "pop_volk", "antielitismus": "pop_antielite",
              "manichaeische_moralisierung": "pop_manich"}
    v["pop_gesamt"] = v[[quelle[d] for d in GESAMTSCORE_AUS]].mean(axis=1)
    v["pop_klass"] = 1
    v["krieg_transkript"] = (v["pop_n_seg_ukraine"] > 0).astype(int)
    return v


def video_position(pos):
    pos = _korrigiere_position(pos)
    pos["_deskr_rus"] = (pos["rus_status"] == "deskriptiv").astype(int)
    pos["_deskr_west"] = (pos["west_status"] == "deskriptiv").astype(int)
    v = pos.groupby("video_id").agg(
        pos_russland=("rus_score", "mean"),
        pos_westpolitik=("west_score", "mean"),
        pos_n_seg=("segment_index", "size"),
        pos_n_seg_deskr_rus=("_deskr_rus", "sum"),
        pos_n_seg_deskr_west=("_deskr_west", "sum"),
        pos_run=("run_id", run_liste),
    ).reset_index()
    v["pos_klass"] = 1
    return v


def video_ideologie(ideo):
    return ideo.groupby("video_id").agg(
        ideo_wirtschaft=("wirtschaft", "mean"),
        ideo_gesellschaft=("gesellschaft", "mean"),
    ).reset_index()


def titel_themen(v):
    """rel_<topic>_core/_cw: Stichwortsuche nur im Titel, dieselben Regexe wie
    step3_topic_relevance (fuer klassifizierte Videos identisch mit den
    *_title-Eintraegen in video_topic_relevance.matched_keywords). Direkt
    berechnet, weil video_topic_relevance Videos <= 180 s nicht abdeckt.
    Fehlender Titel -> 0 (wie in preparation.py)."""
    titel = v["titel"].fillna("")
    for topic, cfg in TOPIC_KEYWORDS.items():
        treffer = {t: titel.str.contains(KW_RE[f"{cfg['prefix']}_{t}"], na=False) for t in TIERS if t in cfg}
        v[f"rel_{topic}_core"] = treffer["core"].astype(int)
        v[f"rel_{topic}_cw"] = pd.concat(treffer.values(), axis=1).any(axis=1).astype(int)
    return v


def krieg_titel_beschreibung(video_ids):
    """Nur intern: Kriegsbezug laut video_topic_relevance (Titel + Beschreibung,
    nur Videos > 180 s) fuer den Ausschluss aus der Ideologie-Baseline - haelt
    ideo_*_baseline identisch zum Export vor dem 13.10.2026."""
    t = video_registry.get_topic_relevance(KRIEG_TOPIC, video_ids=video_ids)
    merge_bilanz(f"video_topic_relevance[{KRIEG_TOPIC}] (nur intern)", video_ids, t["video_id"])
    return dict(zip(t["video_id"], t["is_relevant"]))


def lade_format_status():
    """Letzter Laufstatus je Kanal ueber alle *_formats_status.csv (komplett,
    unvollstaendig, fehler, abgebrochen_quota, ...)."""
    dateien = sorted(FORMAT_LISTEN_DIR.glob("*_formats_status.csv"))
    status = pd.concat([pd.read_csv(d, usecols=["zeitpunkt", "channel_id", "status"]) for d in dateien])
    status = status.sort_values("zeitpunkt").drop_duplicates("channel_id", keep="last")
    log(f"[Laden] Format-Status aus {[d.name for d in dateien]}: {status['status'].value_counts().to_dict()}")
    return dict(zip(status["channel_id"], status["status"]))


def lade_format_listen():
    """channel_id -> Code der Kanalliste (FORMAT_LISTEN). Bricht ab, wenn ein
    Kanal in mehreren Listen steht."""
    listen = {}
    for datei, code in FORMAT_LISTEN.items():
        for cid in pd.read_csv(FORMAT_LISTEN_DIR / datei)["channel_id"].astype(str):
            if cid in listen and listen[cid] != code:
                raise ValueError(f"Kanal {cid} steht in mehreren FORMAT_LISTEN ({listen[cid]} und {code})")
            listen[cid] = code
    log(f"[Laden] Kanallisten mit Sendungsmustern: {pd.Series(listen).value_counts().sort_index().to_dict()}")
    return listen


def video_format(v, format_status):
    fmt = video_registry.get_video_formats(video_ids=v["video_id"].tolist())
    merge_bilanz("video_format", v["video_id"], fmt["video_id"])
    v = v.merge(fmt[["video_id", "format", "source"]].rename(columns={"source": "format_quelle"}),
                on="video_id", how="left")
    im_fenster = v["upload_ts"].between(pd.Timestamp(FORMAT_FENSTER[0]), pd.Timestamp(FORMAT_FENSTER[1]),
                                        inclusive="left")
    ausschluss = v["channel_id"].isin(FORMAT_AUSSCHLUSS_LONG) & v["format"].isna() & im_fenster
    v.loc[ausschluss, "format"] = "long"
    v["format_derived"] = ausschluss.astype(int)
    log(f"[Format] per Ausschluss als long gesetzt (FORMAT_AUSSCHLUSS_LONG): {int(ausschluss.sum())} Videos")
    komplett = v["channel_id"].map(format_status).eq("komplett")
    v["format_klass"] = (komplett & im_fenster).astype(int)
    log(f"[Format] format_klass = 1 (Kanal komplett, Video im Fenster {FORMAT_FENSTER[0]} bis "
        f"< {FORMAT_FENSTER[1]}): {int(v['format_klass'].sum())} von {len(v)}; davon ohne Format: "
        f"{int(((v['format_klass'] == 1) & v['format'].isna()).sum())}")
    return v


def video_sendungen(v, format_listen):
    """news_show/special_show/pk_sitzung per Titelmuster (NEWS/SPECIAL/PRESSE
    aus news_show_patterns.py); '.' fuer Kanaele ohne gepruefte Muster. Mehr-
    Themen-Teaser (Shorts) zaehlen als news_show. Muster der Listen 1/2 sind
    nur auf long-Videos geprueft, die der Liste 3 auf allen Formaten."""
    geprueft = v["channel_id"].isin(format_listen)
    sendung = classify_frame(v.loc[geprueft, ["channel_id", "titel"]].assign(titel=lambda d: d["titel"].fillna("")),
                             title_col="titel")
    v["news_show"] = (sendung == NEWS).astype(float).reindex(v.index)
    v["special_show"] = (sendung == SPECIAL).astype(float).reindex(v.index)
    v["pk_sitzung"] = (sendung == PRESSE).astype(float).reindex(v.index)
    log(f"[Sendungen] Videos aus Kanaelen mit geprueften Mustern: {int(geprueft.sum())}, "
        f"news_show = 1: {int(v['news_show'].sum())}, special_show = 1: {int(v['special_show'].sum())}, "
        f"pk_sitzung = 1: {int(v['pk_sitzung'].sum())}")
    liste = v.loc[geprueft, "channel_id"].map(format_listen).rename("format_liste")
    log("[Sendungen] je Kanalliste (Summe = 1):\n"
        + v.loc[geprueft, ["news_show", "special_show", "pk_sitzung"]].groupby(liste).sum().astype(int).to_string())
    return v


# =========================================================
# Kanalebene: Baselines
# =========================================================

def berechne_pop_baseline(videos):
    """Segment -> Video (bereits erfolgt) -> Kanal x Quartal -> Kanal, Quartale
    gleich gewichtet (wie prepare_channel_scores.prepare_populism_results),
    nur Videos mit baseline_stichprobe == 1."""
    b = videos[videos["baseline_stichprobe"] == 1].copy()
    b["rel_quartal"] = relativ_periode(b["upload_ts"], pd.Timestamp(KRIEGSBEGINN), 3)
    quartal = b.groupby(["channel_id", "rel_quartal"], as_index=False).agg(
        pop_gesamt=("pop_gesamt", "mean"), n=("video_id", "count"))
    return quartal.groupby("channel_id").agg(
        pop_baseline=("pop_gesamt", "mean"),
        pop_baseline_n=("n", "sum"),
        pop_baseline_nq=("rel_quartal", "nunique"),
    ).reset_index()


def berechne_ideo_baseline(videos, ideo_video):
    """Ideologie nur aus Baseline-Fenster-Videos mit min_dauer == 1 ohne
    Kriegsbezug (Titel/Beschreibung laut video_topic_relevance != 1 und
    krieg_transkript != 1); Segment -> Video -> Kanal."""
    basis = videos[(videos["im_baseline_fenster"] == 1)
                   & (videos["min_dauer"] == 1)
                   & (videos["_krieg_tb"] != 1)
                   & (videos["krieg_transkript"] != 1)][["video_id", "channel_id"]]
    b = basis.merge(ideo_video, on="video_id", how="inner")
    log(f"[Ideologie] Baseline-Videos ohne Kriegsbezug mit IDEOLOGIE_I-Klassifikation: {len(b)} "
        f"({b['channel_id'].nunique()} Kanaele)")
    return b.groupby("channel_id").agg(
        ideo_gesellschaft_baseline=("ideo_gesellschaft", "mean"),
        ideo_wirtschaft_baseline=("ideo_wirtschaft", "mean"),
        ideo_baseline_n=("video_id", "count"),
    ).reset_index()


def lade_medientyp():
    med = pd.read_excel(MEDIENTYP_PFAD)[["channel_id", "type"]].rename(columns={"type": "typ_roh"})
    med["typ_roh"] = pd.to_numeric(med["typ_roh"], errors="coerce")
    widerspruch = med.groupby("channel_id")["typ_roh"].nunique()
    pruefe((widerspruch <= 1).all(), "Medientyp-Datei ohne widerspruechliche Duplikate")
    n_dup = int(med.duplicated().sum())
    med = med.drop_duplicates("channel_id")
    log(f"[Laden] Medientyp: {len(med)} Kanaele ({n_dup} identische Duplikatzeilen entfernt), "
        f"Rohcodes {med['typ_roh'].value_counts().sort_index().to_dict()}")
    unbekannt = ~med["typ_roh"].isin(list(MEDIENTYP_UMKODIERUNG))
    pruefe(not (unbekannt & med["typ_roh"].notna()).any(), "nur bekannte Medientyp-Rohcodes")
    med["medientyp"] = med["typ_roh"].map(MEDIENTYP_UMKODIERUNG)
    return med


def lade_kanaltyp():
    typ = pd.read_csv(KANALTYP_PFAD, dtype=str)
    pruefe(not typ["channel_id"].duplicated().any(), "Kanaltypologie: channel_id eindeutig")
    pruefe(typ["typ_code"].isin(list(KANALTYP_CODES)).all(), "Kanaltypologie: nur bekannte typ_code")
    sicher = {v: k for k, v in KANALTYP_SICHER_LABELS.items()}
    pruefe(typ["sicherheit"].isin(list(sicher)).all(), "Kanaltypologie: sicherheit nur hoch/mittel/niedrig")
    out = pd.DataFrame({
        "channel_id": typ["channel_id"],
        "kanaltyp": typ["typ_code"].map(KANALTYP_CODES),
        "kanaltyp_subtyp": typ["subtyp"],
        "kanaltyp_org": typ["organisationsform"],
        "kanaltyp_sicher": typ["sicherheit"].map(sicher),
    })
    out["kanaltyp_gruppe"] = out["kanaltyp"] // 10
    log(f"[Laden] Kanaltypologie: {len(out)} Kanaele, "
        f"Typen {typ['typ_code'].value_counts().sort_index().to_dict()}")
    return out


# =========================================================
# Hauptablauf
# =========================================================

def baue_videos(kanal_ids, format_status, format_listen):
    v = lade_videos(kanal_ids)
    v["min_dauer"] = (v["dauer_sek"] >= MIN_DAUER_SEK).astype(int)
    log(f"[min_dauer] Dauer >= {MIN_DAUER_SEK} s: {int(v['min_dauer'].sum())} von {len(v)} Videos "
        f"({v.loc[v['min_dauer'] == 1, 'channel_id'].nunique()} Kanaele mit >= 1 solchen Video); "
        f"Dauer unbekannt (-> min_dauer = 0): {int(v['dauer_sek'].isna().sum())}")
    ids = v["video_id"].tolist()

    # Zeitvariablen fuer den Vorher/Nachher-Vergleich
    v["post_war"] = (v["upload_ts"] >= pd.Timestamp(KRIEGSBEGINN)).astype(int)
    v["monat"] = v["upload_ts"].dt.to_period("M").dt.to_timestamp()

    # Format, Titel-Topics, Sendungen
    v = video_format(v, format_status)
    v = titel_themen(v)
    v = video_sendungen(v, format_listen)

    # Metriken
    v = v.rename(columns={"view_count": "views", "like_count": "likes", "comment_count": "kommentare"})
    for spalte in ["views", "likes", "kommentare"]:
        v[spalte] = v[spalte].astype("float64")
    for spalte, kennz in [("likes", "likes_verfuegbar"), ("kommentare", "komm_verfuegbar")]:
        v[kennz] = np.where(v[spalte].notna(), 1.0, np.where(v["views"].notna(), 0.0, np.nan))

    # politisch (YouTube-topic_categories)
    pol = video_registry.politics_topic_lookup(ids)
    merge_bilanz("video_details.topic_categories (politisch)", ids, pol.keys())
    v["politisch"] = v["video_id"].map(pol).map({True: 1.0, False: 0.0})
    v["politisch_klass"] = v["politisch"].notna().astype(int)

    # Kriegsbezug Titel + Beschreibung - nur intern (Ideologie-Baseline)
    v["_krieg_tb"] = v["video_id"].map(krieg_titel_beschreibung(ids))

    # Transkript
    mit_transkript = transcript_store.has_transcript(ids)
    v["transkript"] = v["video_id"].isin(mit_transkript).astype(int)
    log(f"[Merge] transcript_store: {len(mit_transkript)} Videos mit Transkript (status OK)")

    # LLM-Klassifikationen
    pop = video_populismus(lade_llm(PROMPT_POPULISMUS, "kodierbar"))
    pos = video_position(lade_llm(PROMPT_POSITION, "rus_status"))
    # Ideologie: Scores sind bei "nicht_erkennbar" regulaer leer -> gueltig
    # heisst hier nur "ohne parse_error"
    ideo = video_ideologie(lade_llm(PROMPT_IDEOLOGIE, None))
    for name, df in [("POPULISMUS_P", pop), ("POSITION_V1", pos), ("IDEOLOGIE_I", ideo)]:
        merge_bilanz(name, ids, df["video_id"])
        kurz = set(df["video_id"]) & set(v.loc[v["min_dauer"] == 0, "video_id"])
        fremd = set(df["video_id"]) - set(v["video_id"])
        log(f"[Check] Pruefung 7 ({name}): klassifiziert mit min_dauer = 0 (im Export, fuer LLM-Analysen "
            f"ausschliessen): {len(kurz)}; nicht unter den Videos der Sample-Kanaele (fehlen im Export): {len(fremd)}")
    v = v.merge(pop, on="video_id", how="left").merge(pos, on="video_id", how="left")
    for k in ["pop_klass", "pos_klass"]:
        v[k] = v[k].fillna(0).astype(int)
    for s in ["pop_run", "pos_run"]:
        v[s] = v[s].fillna("")

    # Baseline-Zugehoerigkeit (einzige Verwendung von interval_index); nur
    # Videos mit min_dauer == 1, damit pop_baseline unveraendert bleibt
    state = screening_state_store.get_state(channel_ids=kanal_ids)
    merge_bilanz("screening_state", ids, state["video_id"])
    fenster = set(state.loc[state["interval_index"].isin(BASELINE_INTERVAL_INDIZES), "video_id"])
    v["im_baseline_fenster"] = v["video_id"].isin(fenster).astype(int)
    v["baseline_stichprobe"] = ((v["im_baseline_fenster"] == 1) & (v["pop_klass"] == 1)
                                & (v["min_dauer"] == 1)).astype(int)

    v["abruf_ts"] = pd.NaT

    return v, ideo


def baue_kanaele(kanal_ids, v_alle, ideo_video, format_status, format_listen):
    # Kanalgroessen nur aus Videos mit min_dauer == 1 (wie vor dem 13.10.2026)
    v = v_alle[v_alle["min_dauer"] == 1]
    k = pd.DataFrame({"channel_id": kanal_ids})
    meta = video_registry.get_channels(kanal_ids)
    merge_bilanz("channels (Kanalmetadaten)", kanal_ids, meta["channel_id"])
    meta = meta[["channel_id", "title", "published_at", "subscribers"]].rename(
        columns={"title": "kanal_name", "subscribers": "abonnenten"})
    meta["kanal_erstellt"] = zu_utc_naiv(meta.pop("published_at"))
    meta["abonnenten"] = meta["abonnenten"].astype("float64")
    k = k.merge(meta, on="channel_id", how="left")

    k["n_videos_alle"] = k["channel_id"].map(v_alle.groupby("channel_id").size()).fillna(0)
    k["n_videos"] = k["channel_id"].map(v.groupby("channel_id").size()).fillna(0)
    k["erstes_video_ts"] = k["channel_id"].map(v.groupby("channel_id")["upload_ts"].min())

    log("[min_dauer] Videos je Kanal alle / min_dauer == 1 (channel_id | alle | min_dauer):")
    for z in k.itertuples():
        log(f"    {z.channel_id} | {int(z.n_videos_alle)} | {int(z.n_videos)}", nur_datei=True)

    # Videoformat: letzter Laufstatus von channel_video_formats.py, Kanalliste
    k["format_status"] = k["channel_id"].map(format_status).fillna("fehlt")
    k["format_liste"] = k["channel_id"].map(format_listen).fillna(0)
    log(f"[Format] format_status der Sample-Kanaele: {k['format_status'].value_counts().to_dict()}")

    # Sample-Kennzeichen
    whitelist = set(pd.read_csv(WHITELIST_PFAD)["channel_id"].astype(str))
    merge_bilanz("frage1_kanal_whitelist", kanal_ids, whitelist)
    k["sample_whitelist"] = k["channel_id"].isin(whitelist).astype(int)
    vorkrieg = v[(v["upload_ts"] >= pd.Timestamp(VORKRIEG_START)) & (v["upload_ts"] < pd.Timestamp(KRIEGSBEGINN))]
    aktiv = vorkrieg.groupby("channel_id").size()
    aktiv = set(aktiv[aktiv >= VORKRIEG_MIN_VIDEOS].index)
    log(f"[Sample] aktiv vor Kriegsbeginn (>= {VORKRIEG_MIN_VIDEOS} Video in [{VORKRIEG_START}, {KRIEGSBEGINN})): "
        f"{len(aktiv & set(kanal_ids))} Kanaele")
    k["sample_vorkrieg"] = (k["channel_id"].isin(aktiv) & (k["sample_whitelist"] == 1)).astype(int)

    # Medientyp und Kriterien
    med = lade_medientyp()
    merge_bilanz("Medientyp-Excel", kanal_ids, med["channel_id"])
    k = k.merge(med[["channel_id", "medientyp", "typ_roh"]], on="channel_id", how="left")
    k["krit_creator"] = np.nan
    k["krit_korrektiv"] = np.nan

    # Kanaltypologie und Kernstichprobe
    typ = lade_kanaltyp()
    merge_bilanz("Kanaltypologie", kanal_ids, typ["channel_id"])
    k = k.merge(typ, on="channel_id", how="left")
    kern_codes = [KANALTYP_CODES[t] for t in SAMPLE_KERN_TYPEN]
    k["sample_kern"] = (k["kanaltyp"].isin(kern_codes) & (k["sample_whitelist"] == 1)
                        & ~k["channel_id"].isin(SAMPLE_KERN_AUSSCHLUSS)).astype(int)
    log(f"[Sample] sample_kern ({', '.join(SAMPLE_KERN_TYPEN)}, ohne {len(SAMPLE_KERN_AUSSCHLUSS)} "
        f"Einzelausschluss): {int(k['sample_kern'].sum())} Kanaele, davon sample_vorkrieg "
        f"{int(((k['sample_kern'] == 1) & (k['sample_vorkrieg'] == 1)).sum())}")

    # Baselines
    pop_b = berechne_pop_baseline(v)
    k = k.merge(pop_b, on="channel_id", how="left")
    k["sample_baseline"] = k["pop_baseline"].notna().astype(int)
    k = k.merge(berechne_ideo_baseline(v_alle, ideo_video), on="channel_id", how="left")
    for s in ["pop_baseline_n", "pop_baseline_nq", "ideo_baseline_n"]:
        k[s] = k[s].fillna(0)

    # Datenqualitaet
    auff = pd.read_csv(API_ABBRUCH_PFAD)
    abbruch = set(auff.loc[auff["flag"] == "playlist_limit", "channel_id"])
    k["api_abbruch"] = k["channel_id"].isin(abbruch).astype(int)
    log(f"[Merge] API-Abbruch (playlist_limit): {len(abbruch)} Kanaele, davon im Sample {int(k['api_abbruch'].sum())}")

    # Hinweise
    hinweise = dict(KANAL_HINWEISE)
    for cid in k.loc[k["typ_roh"] == 5, "channel_id"]:
        zusatz = "Medientyp-Rohcode 5 (Sonderfall), als ÖRR (1) gezaehlt"
        hinweise[cid] = f"{hinweise[cid]}; {zusatz}" if cid in hinweise else zusatz
    k["kanal_hinweis"] = k["channel_id"].map(hinweise).fillna("")
    return k.drop(columns="typ_roh")


# =========================================================
# Konsistenzpruefungen
# =========================================================

def konsistenz(v, k):
    log("")
    log("[Check] ===== Konsistenzpruefungen (Codebuch) =====")
    pruefe(not v["video_id"].duplicated().any(), "1a video_id in videos_roh eindeutig")
    pruefe(not k["channel_id"].duplicated().any(), "1b channel_id in kanaele_roh eindeutig")
    pruefe(v["channel_id"].isin(k["channel_id"]).all(), "2 jede channel_id aus videos_roh existiert in kanaele_roh")
    pruefe((v["min_dauer"] == (v["dauer_sek"] >= MIN_DAUER_SEK).astype(int)).all(),
           f"3 min_dauer = 1 genau bei dauer_sek >= {MIN_DAUER_SEK} (unbekannte Dauer -> 0)")
    pruefe((v.loc[v["baseline_stichprobe"] == 1, "min_dauer"] == 1).all(), "3 baseline_stichprobe = 1 => min_dauer = 1")

    vor = (v["pos_klass"] == 1) & (v["upload_ts"] < pd.Timestamp(KRIEGSBEGINN))
    log(f"[Check] 4 (nur Anzahl, Entscheidung 02.10.2026: Werte bleiben drin): "
        f"{int(vor.sum())} positionsklassifizierte Videos vor Kriegsbeginn")

    paare = {
        "pop_klass": ["pop_gesamt", "pop_volk", "pop_antielite", "pop_manich", "pop_emotion"],
        "pos_klass": ["pos_russland", "pos_westpolitik"],
        "politisch_klass": ["politisch"],
    }
    for kennz, werte in paare.items():
        for w in werte:
            pruefe(not (v.loc[v[kennz] == 0, w].notna()).any(), f"5 {kennz} = 0 => {w} = .")
            leer = int(((v[kennz] == 1) & v[w].isna()).sum())
            if leer:
                log(f"[Check] 5 Hinweis: {kennz} = 1, aber {w} = . bei {leer} Videos "
                    f"(klassifiziert, Dimension nicht kodierbar/thematisiert)")
    pruefe(not (v.loc[v["pop_klass"] == 0, "krieg_transkript"].notna()).any(), "5 pop_klass = 0 => krieg_transkript = .")
    pruefe(all(((v[f"rel_{t}_core"] == 0) | (v[f"rel_{t}_cw"] == 1)).all() for t in TOPIC_KEYWORDS),
           "5 rel_<topic>_core = 1 => rel_<topic>_cw = 1 (alle Themen)")
    pruefe(v["format"].isin(["short", "long", "live"]).sum() == v["format"].notna().sum(),
           "5 format nur short/long/live oder leer")
    pruefe(((v["format_derived"] == 0) | (v["format"] == "long")).all(), "5 format_derived = 1 => format = long")
    geprueft = v["channel_id"].isin(k.loc[k["format_liste"] > 0, "channel_id"])
    pruefe(all((v[s].isna() == ~geprueft).all() for s in ["news_show", "special_show", "pk_sitzung"]),
           "5 news_show/special_show/pk_sitzung = . genau fuer Kanaele ohne gepruefte Titelmuster (format_liste = 0)")
    pruefe((v[["news_show", "special_show", "pk_sitzung"]].sum(axis=1) <= 1).all(),
           "5 news_show + special_show + pk_sitzung <= 1 (Kategorien schliessen sich aus)")

    # 8: Kanaltypologie
    pruefe((k["kanaltyp"].notna() == (k["sample_whitelist"] == 1)).all(),
           "8 kanaltyp gesetzt genau fuer sample_whitelist = 1")
    pruefe((k["kanaltyp_gruppe"].dropna() == k["kanaltyp"].dropna() // 10).all(),
           "8 kanaltyp_gruppe = Zehnerstelle von kanaltyp")
    kern_codes = [KANALTYP_CODES[t] for t in SAMPLE_KERN_TYPEN]
    pruefe(k.loc[k["sample_kern"] == 1, "kanaltyp"].isin(kern_codes).all(),
           f"8 sample_kern = 1 => kanaltyp in {SAMPLE_KERN_TYPEN}")
    abw = k[k["kanaltyp"].notna()]
    log("[Check] 8 Hinweis kanaltyp x medientyp (Abweichungen dokumentiert in "
        "scripts/adhoc/outputs/kanal_typologie_grenzfaelle.md):")
    log(pd.crosstab(abw["kanaltyp"].astype(int).map(KANALTYP_LABELS),
                    abw["medientyp"].fillna(-1).astype(int)).to_string())

    # 6: unabhaengige Nachberechnung aus den exportierten Videowerten
    # (baseline_stichprobe enthaelt nur Videos mit min_dauer == 1)
    b = v[v["baseline_stichprobe"] == 1]
    q = (b["upload_ts"].dt.year - 2022) * 12 + (b["upload_ts"].dt.month - 2) - (b["upload_ts"].dt.day < 24).astype(int)
    nach = b.assign(q=q // 3).groupby(["channel_id", "q"])["pop_gesamt"].mean().groupby("channel_id").mean()
    vergleich = k.set_index("channel_id")["pop_baseline"].dropna()
    diff = (vergleich - nach.reindex(vergleich.index)).abs()
    pruefe(nach.dropna().index.isin(vergleich.index).all() and diff.max() <= BASELINE_TOLERANZ,
           f"6 pop_baseline = Nachberechnung aus Baseline-Videos (max. Abweichung {diff.max():.2e}, "
           f"Toleranz {BASELINE_TOLERANZ})")


# =========================================================
# Export
# =========================================================

VIDEO_SPALTEN = {
    # Name: (Typ, Label)
    "video_id": ("str", "YouTube-Video-ID"),
    "channel_id": ("str", "YouTube-Kanal-ID"),
    "titel": ("strL", "Videotitel"),
    "upload_ts": ("tc", "Veroeffentlichung (published_at), UTC"),
    "monat": ("tm", "Veroeffentlichungsmonat (UTC)"),
    "post_war": ("byte", "ab Kriegsbeginn 24.02.2022"),
    "abruf_ts": ("tc", "Abruf der Metriken, UTC (nicht gespeichert -> .)"),
    "dauer_sek": ("long", "Videolaenge in Sekunden; . = unbekannt"),
    "min_dauer": ("byte", f"dauer_sek >= {MIN_VIDEO_DURATION_SECONDS} (Pflicht fuer LLM-Analysen)"),
    "format": ("str", "Format short/long/live (leer = nicht zugeordnet)"),
    "format_quelle": ("str", "Quelle Format (api_UULF/UUSH/UULV, ytdlp_*)"),
    "format_klass": ("byte", "Kanal-Formatlauf komplett und Video im Format-Fenster"),
    "format_derived": ("byte", "Format per Ausschluss als long gesetzt (nur WELT)"),
    "news_show": ("byte", "ganze Nachrichtensendung (Titelmuster); . = ungeprueft"),
    "special_show": ("byte", "Sondersendung/Themen-Update (Titelmuster); . = ungeprueft"),
    "pk_sitzung": ("byte", "Pressekonferenz/Regierungsbefragung/Sitzung (Titelmuster); . = ungeprueft"),
    "views": ("double", "Aufrufe kumuliert (Stand Abruf)"),
    "likes": ("double", "Likes kumuliert; . = ausgeblendet"),
    "kommentare": ("double", "Kommentare kumuliert; . = deaktiviert"),
    "likes_verfuegbar": ("byte", "Likes sichtbar (1) / Feld fehlt (0)"),
    "komm_verfuegbar": ("byte", "Kommentare aktiv (1) / Feld fehlt (0)"),
    "politisch": ("byte", "politisch laut YouTube-topic_categories (Politics)"),
    "politisch_klass": ("byte", "topic_categories liegt vor"),
    **{f"rel_{topic}_{variante}": ("byte", f"Titel-Treffer {cfg['label']} ({text})")
       for topic, cfg in TOPIC_KEYWORDS.items()
       for variante, text in (("core", "nur core"), ("cw", "core+wide"))},
    "krieg_transkript": ("byte", ">= 1 Segment mit ukraine_bezug (POPULISMUS_P)"),
    "pop_gesamt": ("double", "Populismus gesamt (Mittel volk/antielite/manich), 0-3"),
    "pop_volk": ("double", "Volkszentrismus 0-3"),
    "pop_antielite": ("double", "Antielitismus 0-3"),
    "pop_manich": ("double", "Manichaeische Moralisierung 0-3"),
    "pop_emotion": ("double", "Emotionale Intensitaet 0-3 (Kontrollgroesse)"),
    "pop_klass": ("byte", "Populismus klassifiziert"),
    "pop_n_seg": ("long", "Anzahl Populismus-Segmente"),
    "pop_n_seg_nichtkodierbar": ("long", "davon kodierbar = false (-> . gesetzt)"),
    "pop_n_seg_ukraine": ("long", "davon mit ukraine_bezug = true"),
    "pop_run": ("str", "Run-ID(s) POPULISMUS_P"),
    "baseline_stichprobe": ("byte", "Video in Baseline-Stichprobe (pop_baseline)"),
    "pos_russland": ("double", "Position Russland -2..+2 (+2 = rechtfertigend)"),
    "pos_westpolitik": ("double", "Position westl. Ukraine-Politik -2..+2 (+2 = unterst.)"),
    "pos_klass": ("byte", "Position klassifiziert"),
    "pos_n_seg": ("long", "Anzahl Positions-Segmente"),
    "pos_n_seg_deskr_rus": ("long", "Segmente Russland deskriptiv (= 0 gesetzt)"),
    "pos_n_seg_deskr_west": ("long", "Segmente Westpolitik deskriptiv (= 0 gesetzt)"),
    "pos_run": ("str", "Run-ID(s) POSITION_V1"),
    "transkript": ("byte", "Transkript vorhanden (transcript_store, status OK)"),
}

KANAL_SPALTEN = {
    "channel_id": ("str", "YouTube-Kanal-ID"),
    "kanal_name": ("str", "Kanalname (Stand Abruf)"),
    "kanal_erstellt": ("tc", "Erstellungsdatum Kanal, UTC"),
    "erstes_video_ts": ("tc", "aeltestes Video mit min_dauer = 1 im Datensatz, UTC"),
    "abonnenten": ("double", "Abonnenten zum Abruf (deskriptiv)"),
    "kanal_hinweis": ("str", "Freitext Sonderfaelle"),
    "sample_vorkrieg": ("byte", "Whitelist und >= 1 Video im Jahr vor Kriegsbeginn"),
    "sample_baseline": ("byte", "Baseline-Populismus vorhanden"),
    "sample_whitelist": ("byte", "in frage1_kanal_whitelist.csv"),
    "medientyp": ("byte", "Medientyp (1 ÖRR, 2 trad., 3 Partei, 4 Creator/alt.)"),
    "krit_creator": ("byte", "Kriterium Creator (Newman et al. 2025), . = offen"),
    "krit_korrektiv": ("byte", "Kriterium Korrektiv (Holt et al. 2019), . = offen"),
    "kanaltyp": ("byte", "Kanaltyp (Typologie, nur Whitelist; . = nicht codiert)"),
    "kanaltyp_gruppe": ("byte", "Kanaltyp-Gruppe (A etabliert, B pol.-alt., C Themen)"),
    "kanaltyp_subtyp": ("str", "Kanaltyp Subtyp (Freitext, nur deskriptiv)"),
    "kanaltyp_org": ("str", "Organisationsform (Freitext, nur deskriptiv)"),
    "kanaltyp_sicher": ("byte", "Sicherheit der Typzuordnung"),
    "sample_kern": ("byte", "Kernstichprobe (A1 A2 A5 B1 B2 B3 C1, ohne Ausschl.)"),
    "pop_baseline": ("double", "Baseline-Populismus (Video->Quartal->Kanal)"),
    "pop_baseline_n": ("long", "Anzahl Baseline-Videos"),
    "pop_baseline_nq": ("long", "Anzahl Baseline-Quartale"),
    "ideo_gesellschaft_baseline": ("double", "Ideologie gesellschaftl. -2 progr. .. +2 kons."),
    "ideo_wirtschaft_baseline": ("double", "Ideologie wirtschaftl. -2 umvert. .. +2 marktlib."),
    "ideo_baseline_n": ("long", "Anzahl Ideologie-Baseline-Videos (ohne Krieg)"),
    "api_abbruch": ("byte", "vom ~20.000er-Playlist-Limit betroffen (nachgescrapt)"),
    "format_status": ("str", "letzter Status channel_video_formats.py (fehlt = nie)"),
    "format_liste": ("byte", "Kanalliste Formatlauf mit geprueften Sendungsmustern"),
    "n_videos_alle": ("long", "Videos im Datensatz (alle Laengen)"),
    "n_videos": ("long", "Videos mit min_dauer = 1"),
}

DTYPES = {"byte": "Int8", "long": "Int32", "double": "float64", "str": "str"}


def exportiere(df, spalten, datei, wertelabels):
    df = df[list(spalten)].copy()
    daten, strl = {}, []
    for name, (typ, _) in spalten.items():
        assert len(name) <= 32 and name.isascii(), name
        if typ in ("tc", "tm"):
            df[name] = pd.to_datetime(df[name])
            daten[name] = typ
        elif typ in ("str", "strL"):
            df[name] = df[name].fillna("").astype(str)
            if typ == "strL":
                # strL statt fester Breite: Titel enthalten Mehrbyte-Zeichen,
                # str<n> wuerde die Datei um mehrere 100 MB aufblaehen
                strl.append(name)
        else:
            df[name] = df[name].astype(DTYPES[typ])
    df.to_stata(AUSGABE_PFAD / datei, version=118, write_index=False, convert_dates=daten,
                convert_strl=strl, variable_labels={n: l for n, (_, l) in spalten.items()},
                value_labels=wertelabels)
    log(f"[Export] {datei}: {len(df)} Zeilen, {len(df.columns)} Variablen")


DO_FILE = r"""* check_rohdaten.do - Pruefung des Stata-Rohdatensatzes
* erzeugt von src/youtube_code/step6_auswertung/export_stata_rohdaten.py
* Ausfuehren im Ordner outputs/stata_rohdaten (cd dorthin).

clear all
set more off

use kanaele_roh.dta, clear
describe
codebook, compact
isid channel_id
tab medientyp, missing
tab kanaltyp medientyp, missing
tab kanaltyp sample_vorkrieg if sample_whitelist == 1
tab1 sample_vorkrieg sample_baseline sample_whitelist sample_kern api_abbruch format_liste
tab format_status, missing

use videos_roh.dta, clear
describe
codebook, compact
isid video_id
tab1 min_dauer post_war politisch_klass pop_klass pos_klass transkript baseline_stichprobe
tab format format_klass, missing
tab1 news_show special_show pk_sitzung, missing
* LLM-Analysen (pop_*, pos_*) nur mit min_dauer == 1 (siehe Codebuch)
tab pop_klass min_dauer

merge m:1 channel_id using kanaele_roh.dta
* Erwartung: keine Videos nur in master (_merge == 1); Kanaele nur in using
* (_merge == 2) sind solche ganz ohne Video in der Registry.
tab _merge
assert _merge != 1
"""


def main():
    os.makedirs(AUSGABE_PFAD, exist_ok=True)
    kanal_ids = lade_kanaele()
    format_status = lade_format_status()
    format_listen = lade_format_listen()
    v, ideo_video = baue_videos(kanal_ids, format_status, format_listen)
    k = baue_kanaele(kanal_ids, v, ideo_video, format_status, format_listen)

    log("")
    log("[Abdeckung] Videoebene (Anteil nicht fehlend bzw. = 1):")
    for s in ["views", "likes", "kommentare", "politisch", "dauer_sek", "news_show", "krieg_transkript",
              "pop_gesamt", "pos_russland", "pos_westpolitik"]:
        log(f"    {s}: {v[s].notna().mean():.2%} nicht fehlend")
    for s in ["min_dauer", "post_war", "format_klass", "format_derived", "politisch_klass", "pop_klass",
              "pos_klass", "transkript", "baseline_stichprobe", *REL_SPALTEN]:
        log(f"    {s} = 1: {int(v[s].sum())} ({v[s].mean():.2%})")
    log("[Abdeckung] format (leer = nicht zugeordnet) x format_klass:")
    log(pd.crosstab(v["format"].fillna("(leer)"), v["format_klass"]).to_string())
    log("[Abdeckung] pop_klass x min_dauer:")
    log(pd.crosstab(v["pop_klass"], v["min_dauer"]).to_string())
    log("[Abdeckung] Kanaele je Sample-Kennzeichen und Medientyp:")
    log(k.groupby(k["medientyp"].fillna(-1).astype(int))[["sample_vorkrieg", "sample_baseline", "sample_whitelist"]]
        .agg(["sum", "size"]).to_string())
    log(f"    Kanaele gesamt: {len(k)}, ohne Medientyp: {int(k['medientyp'].isna().sum())}, "
        f"mit Ideologie-Baseline: {int(k['ideo_gesellschaft_baseline'].notna().sum())}")
    log("[Abdeckung] Kanaele je Kanaltyp (sample_vorkrieg, sample_kern):")
    log(k[k["kanaltyp"].notna()].groupby(k["kanaltyp"].dropna().astype(int).map(KANALTYP_LABELS))
        [["sample_vorkrieg", "sample_kern"]].agg(["sum", "size"]).to_string())

    konsistenz(v, k)

    ja_nein = {0: "nein", 1: "ja"}
    exportiere(v, VIDEO_SPALTEN, "videos_roh.dta",
               {s: ja_nein for s, (t, _) in VIDEO_SPALTEN.items() if t == "byte"})
    eigene = {"medientyp": MEDIENTYP_LABELS, "format_liste": FORMAT_LISTEN_LABELS,
              "kanaltyp": KANALTYP_LABELS, "kanaltyp_gruppe": KANALTYP_GRUPPE_LABELS,
              "kanaltyp_sicher": KANALTYP_SICHER_LABELS}
    exportiere(k, KANAL_SPALTEN, "kanaele_roh.dta",
               {**eigene, **{s: ja_nein for s, (t, _) in KANAL_SPALTEN.items() if t == "byte" and s not in eigene}})
    (AUSGABE_PFAD / "check_rohdaten.do").write_text(DO_FILE, encoding="utf-8")
    log("[Export] check_rohdaten.do geschrieben")
    schreibe_log()


if __name__ == "__main__":
    main()

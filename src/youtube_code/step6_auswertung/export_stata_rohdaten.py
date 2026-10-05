"""Exportiert den Rohdatensatz fuer die Stata-Do-Files (Bloecke 1-3).

Verbindliche Spezifikation: docs/codebuch_rohdatensatz.md (inkl. Abschnitt
"Entscheidungen zur Umsetzung"). Der Export bleibt so roh wie moeglich: keine
Logs, keine Phasen, keine Aggregation ueber Videos auf Videoebene. Ausnahme:
die Messregel "deskriptiv"-Segmente = 0 bei den Positionsskalen.

Ausgabe (AUSGABE_PFAD = outputs/stata_rohdaten/)
------------------------------------------------
- videos_roh.dta   eine Zeile je Video (Sample-Kanaele, Dauer > 180 s)
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
- krieg/topic_*: video_registry.get_topic_relevance() (Stichwortklassifikation
  aus step3_topic_relevance, Titel + Beschreibung).
- Kanalmetadaten: video_registry.get_channels().
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

from youtube_code.config import OUTPUTS, EXTERNAL, SAMPLES, MIN_VIDEO_DURATION_SECONDS
from youtube_code.store import llm_run_store, screening_state_store, transcript_store, video_registry
from youtube_code.step3_topic_relevance.topic_keywords import TOPIC_KEYWORDS
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

# Population Videos: Dauer >= MIN_VIDEO_DURATION_SECONDS (181 s, d. h. > 180 s)
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

# Themen aus video_topic_relevance -> Exportvariable (krieg separat). Alle
# Themen aus step3_topic_relevance.topic_keywords.TOPIC_KEYWORDS ausser dem
# Krieg; Labels kommen von dort ("label"). Neues Thema in TOPIC_KEYWORDS ->
# hier ergaenzen (main() bricht sonst ab).
KRIEG_TOPIC = "russia_ukraine_war"
TOPICS = {
    "politics_general": "topic_politik",
    "corona_pandemic": "topic_corona",
    "migration": "topic_migration",
    "economy_general": "topic_wirtschaft",
    "energy": "topic_energie",
    "climate": "topic_klima",
    "gender": "topic_gender",
    "mideast": "topic_nahost",
    "iran": "topic_iran",
    "eu": "topic_eu",
    "usa": "topic_usa",
    "education": "topic_bildung",
}

# Manuelle Hinweise je Kanal (Freitext, kanal_hinweis). Typ-5-Kanaele werden
# automatisch ergaenzt.
KANAL_HINWEISE = {
    "UCQGqiGhMjc_p4lZEhSTb12g": "NIUS; erstellt 05.10.2022, erstes Video 31.01.2023; "
                                "Vorlaeuferformat 'Achtung, Reichelt!' ist eigener Kanal UCcoQ3WG2J_Xjwwyt-sJqh-w",
    "UCcoQ3WG2J_Xjwwyt-sJqh-w": "Achtung, Reichelt!; erstellt 07.04.2022; Format spaeter bei NIUS "
                                "(UCQGqiGhMjc_p4lZEhSTb12g)",
    "UCsFtUYhrGmOck_UeVPD-AJQ": "WDR aktuell; Kanal laut yt-dlp am 01.10.2026 nicht mehr vorhanden",
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
    v["upload_ts"] = zu_utc_naiv(v["published_at"])
    v["dauer_sek"] = video_registry._duration_seconds_series(v["duration"])
    log(f"[Laden] Videos der Sample-Kanaele (vor Laengenfilter): {len(v)}")
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


def video_themen(video_ids):
    ergebnis = pd.DataFrame({"video_id": video_ids})
    alle = {KRIEG_TOPIC: "krieg", **TOPICS}
    for topic, name in alle.items():
        t = video_registry.get_topic_relevance(topic, video_ids=video_ids)
        t = t[["video_id", "is_relevant", "matched_keywords", "title_only"]].rename(
            columns={"is_relevant": name, "matched_keywords": f"_kw_{name}", "title_only": f"_titel_{name}"})
        ergebnis = ergebnis.merge(t, on="video_id", how="left")
        merge_bilanz(f"video_topic_relevance[{topic}]", video_ids, t["video_id"])

    ergebnis["krieg_klass"] = ergebnis["krieg"].notna().astype(int)
    ergebnis["topic_klass"] = ergebnis[list(TOPICS.values())].notna().all(axis=1).astype(int)
    teil_klass = ergebnis[list(TOPICS.values())].notna().any(axis=1) & (ergebnis["topic_klass"] == 0)
    if teil_klass.any():
        log(f"[Merge] Achtung: {int(teil_klass.sum())} Videos nur fuer einen Teil der Vergleichsthemen klassifiziert")
    # title_only ist eine Videoeigenschaft (Beschreibung fehlt) -> erstes
    # vorhandenes Thema nehmen, da nicht alle Themen alle Videos abdecken
    titel_spalten = [f"_titel_{n}" for n in alle.values()]
    ergebnis["topic_nur_titel"] = ergebnis[titel_spalten].bfill(axis=1).iloc[:, 0]

    # krieg_quelle: Trefferstufen der Stichwortsuche (z. B. ukr_core_title,
    # ukr_wide_desc) - zeigt Titel/Beschreibung und core/wide
    def stufen(kw):
        if not isinstance(kw, str) or kw in ("", "[]"):
            return ""
        return ",".join(sorted(s.strip(' "[]') for s in kw.split(",")))
    ergebnis["krieg_quelle"] = ergebnis["_kw_krieg"].map(stufen)

    # <name>_core: nur Treffer der core-Liste (Titel oder Beschreibung);
    # . wo das Thema nicht klassifiziert ist
    for topic, name in alle.items():
        core = {f"{TOPIC_KEYWORDS[topic]['prefix']}_core_{ort}" for ort in ("title", "desc")}
        treffer = ergebnis[f"_kw_{name}"].map(stufen).map(lambda s: bool(core & set(s.split(","))))
        ergebnis[f"{name}_core"] = treffer.astype(float).where(ergebnis[name].notna())
    return ergebnis.drop(columns=[c for c in ergebnis.columns if c.startswith("_")])


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
    """Ideologie nur aus Baseline-Fenster-Videos ohne Kriegsbezug
    (krieg != 1 und krieg_transkript != 1); Segment -> Video -> Kanal."""
    basis = videos[(videos["im_baseline_fenster"] == 1)
                   & (videos["krieg"] != 1)
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


# =========================================================
# Hauptablauf
# =========================================================

def baue_videos(kanal_ids):
    alle = lade_videos(kanal_ids)
    alle["_lang"] = alle["dauer_sek"] >= MIN_DAUER_SEK
    v = alle[alle["_lang"]].copy()
    log(f"[Laengenfilter] Dauer >= {MIN_DAUER_SEK} s: {len(v)} von {len(alle)} Videos "
        f"({v['channel_id'].nunique()} Kanaele mit >= 1 Video)")
    ids = v["video_id"].tolist()

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

    # Themen
    v = v.merge(video_themen(ids), on="video_id", how="left")

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
        kurz = set(df["video_id"]) & set(alle.loc[~alle["_lang"], "video_id"])
        fremd = set(df["video_id"]) - set(alle["video_id"])
        log(f"[Check] Pruefung 7 ({name}): klassifiziert, aber nicht im Export: {len(kurz) + len(fremd)} "
            f"(Laengenfilter/Dauer fehlt: {len(kurz)}, nicht unter den Videos der Sample-Kanaele: {len(fremd)})")
    v = v.merge(pop, on="video_id", how="left").merge(pos, on="video_id", how="left")
    for k in ["pop_klass", "pos_klass"]:
        v[k] = v[k].fillna(0).astype(int)
    for s in ["pop_run", "pos_run", "krieg_quelle"]:
        v[s] = v[s].fillna("")

    # Baseline-Zugehoerigkeit (einzige Verwendung von interval_index)
    state = screening_state_store.get_state(channel_ids=kanal_ids)
    merge_bilanz("screening_state", ids, state["video_id"])
    fenster = set(state.loc[state["interval_index"].isin(BASELINE_INTERVAL_INDIZES), "video_id"])
    v["im_baseline_fenster"] = v["video_id"].isin(fenster).astype(int)
    v["baseline_stichprobe"] = ((v["im_baseline_fenster"] == 1) & (v["pop_klass"] == 1)).astype(int)

    v["abruf_ts"] = pd.NaT
    v["live_typ"] = np.nan

    return alle, v, ideo


def baue_kanaele(kanal_ids, alle, v, ideo_video):
    k = pd.DataFrame({"channel_id": kanal_ids})
    meta = video_registry.get_channels(kanal_ids)
    merge_bilanz("channels (Kanalmetadaten)", kanal_ids, meta["channel_id"])
    meta = meta[["channel_id", "title", "published_at", "subscribers"]].rename(
        columns={"title": "kanal_name", "subscribers": "abonnenten"})
    meta["kanal_erstellt"] = zu_utc_naiv(meta.pop("published_at"))
    meta["abonnenten"] = meta["abonnenten"].astype("float64")
    k = k.merge(meta, on="channel_id", how="left")

    k["n_videos_api"] = k["channel_id"].map(alle.groupby("channel_id").size()).fillna(0)
    k["n_videos"] = k["channel_id"].map(v.groupby("channel_id").size()).fillna(0)
    k["erstes_video_ts"] = k["channel_id"].map(v.groupby("channel_id")["upload_ts"].min())

    log("[Laengenfilter] Videos je Kanal vor/nach Filter (channel_id | vorher | nachher):")
    for z in k.itertuples():
        log(f"    {z.channel_id} | {int(z.n_videos_api)} | {int(z.n_videos)}", nur_datei=True)

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

    # Baselines
    pop_b = berechne_pop_baseline(v)
    k = k.merge(pop_b, on="channel_id", how="left")
    k["sample_baseline"] = k["pop_baseline"].notna().astype(int)
    k = k.merge(berechne_ideo_baseline(v, ideo_video), on="channel_id", how="left")
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
    pruefe((v["dauer_sek"] > 180).all(), "3 dauer_sek > 180 fuer alle Videos")

    vor = (v["pos_klass"] == 1) & (v["upload_ts"] < pd.Timestamp(KRIEGSBEGINN))
    log(f"[Check] 4 (nur Anzahl, Entscheidung 02.10.2026: Werte bleiben drin): "
        f"{int(vor.sum())} positionsklassifizierte Videos vor Kriegsbeginn")

    paare = {
        "pop_klass": ["pop_gesamt", "pop_volk", "pop_antielite", "pop_manich", "pop_emotion"],
        "pos_klass": ["pos_russland", "pos_westpolitik"],
        "politisch_klass": ["politisch"],
        "krieg_klass": ["krieg"],
    }
    # topic_klass = 1 heisst: ALLE Vergleichsthemen klassifiziert. Die Themen
    # wurden in verschiedenen Laeufen ueber verschiedene Videomengen
    # klassifiziert, daher hier nur die Richtung topic_klass = 1 => kein '.'
    ganz = v["topic_klass"] == 1
    pruefe(v.loc[ganz, list(TOPICS.values())].notna().all().all(), "5 topic_klass = 1 => alle topic_* gesetzt")
    for w in TOPICS.values():
        log(f"[Check] 5 Hinweis: {w} klassifiziert bei {int(v[w].notna().sum())} Videos, "
            f"davon mit topic_klass = 0: {int((~ganz & v[w].notna()).sum())}")
    for kennz, werte in paare.items():
        for w in werte:
            pruefe(not (v.loc[v[kennz] == 0, w].notna()).any(), f"5 {kennz} = 0 => {w} = .")
            leer = int(((v[kennz] == 1) & v[w].isna()).sum())
            if leer:
                log(f"[Check] 5 Hinweis: {kennz} = 1, aber {w} = . bei {leer} Videos "
                    f"(klassifiziert, Dimension nicht kodierbar/thematisiert)")
    pruefe(not (v.loc[v["krieg_klass"] == 0, "krieg_quelle"] != "").any(), "5 krieg_klass = 0 => krieg_quelle leer")
    for w in ["krieg", *TOPICS.values()]:
        c = f"{w}_core"
        pruefe((v[c].isna() == v[w].isna()).all() and not ((v[c] == 1) & (v[w] != 1)).any(),
               f"5 {c} gleiche Missings wie {w} und {c} = 1 => {w} = 1")
    pruefe(not (v.loc[v["pop_klass"] == 0, "krieg_transkript"].notna()).any(), "5 pop_klass = 0 => krieg_transkript = .")

    # 6: unabhaengige Nachberechnung aus den exportierten Videowerten
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
    "upload_ts": ("tc", "Veroeffentlichung (published_at), UTC"),
    "abruf_ts": ("tc", "Abruf der Metriken, UTC (nicht gespeichert -> .)"),
    "dauer_sek": ("long", "Videolaenge in Sekunden"),
    "live_typ": ("byte", "0 regulaer, 1 Livestream, 2 Premiere (nicht erhoben -> .)"),
    "views": ("double", "Aufrufe kumuliert (Stand Abruf)"),
    "likes": ("double", "Likes kumuliert; . = ausgeblendet"),
    "kommentare": ("double", "Kommentare kumuliert; . = deaktiviert"),
    "likes_verfuegbar": ("byte", "Likes sichtbar (1) / Feld fehlt (0)"),
    "komm_verfuegbar": ("byte", "Kommentare aktiv (1) / Feld fehlt (0)"),
    "politisch": ("byte", "politisch laut YouTube-topic_categories (Politics)"),
    "politisch_klass": ("byte", "topic_categories liegt vor"),
    "krieg": ("byte", "Kriegsvideo (Stichworte Titel/Beschreibung)"),
    "krieg_klass": ("byte", "Stichwortklassifikation Krieg liegt vor"),
    "krieg_quelle": ("str", "Trefferstufen Stichwortsuche (ukr_core/wide_title/desc)"),
    "krieg_transkript": ("byte", ">= 1 Segment mit ukraine_bezug (POPULISMUS_P)"),
    "krieg_core": ("byte", "Kriegsvideo, nur core-Stichworte"),
    **{name: ("byte", f"Thema {TOPIC_KEYWORDS[topic]['label']} (Stichworte, core+wide)")
       for topic, name in TOPICS.items()},
    **{f"{name}_core": ("byte", f"Thema {TOPIC_KEYWORDS[topic]['label']} (nur core-Stichworte)")
       for topic, name in TOPICS.items()},
    "topic_klass": ("byte", "Stichwortklassifikation ALLER Vergleichsthemen liegt vor"),
    "topic_nur_titel": ("byte", "Stichwortsuche nur im Titel (Beschreibung fehlt)"),
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
    "erstes_video_ts": ("tc", "aeltestes Video > 180 s im Datensatz, UTC"),
    "abonnenten": ("double", "Abonnenten zum Abruf (deskriptiv)"),
    "kanal_hinweis": ("str", "Freitext Sonderfaelle"),
    "sample_vorkrieg": ("byte", "Whitelist und >= 1 Video im Jahr vor Kriegsbeginn"),
    "sample_baseline": ("byte", "Baseline-Populismus vorhanden"),
    "sample_whitelist": ("byte", "in frage1_kanal_whitelist.csv"),
    "medientyp": ("byte", "Medientyp (1 ÖRR, 2 trad., 3 Partei, 4 Creator/alt.)"),
    "krit_creator": ("byte", "Kriterium Creator (Newman et al. 2025), . = offen"),
    "krit_korrektiv": ("byte", "Kriterium Korrektiv (Holt et al. 2019), . = offen"),
    "pop_baseline": ("double", "Baseline-Populismus (Video->Quartal->Kanal)"),
    "pop_baseline_n": ("long", "Anzahl Baseline-Videos"),
    "pop_baseline_nq": ("long", "Anzahl Baseline-Quartale"),
    "ideo_gesellschaft_baseline": ("double", "Ideologie gesellschaftl. -2 progr. .. +2 kons."),
    "ideo_wirtschaft_baseline": ("double", "Ideologie wirtschaftl. -2 umvert. .. +2 marktlib."),
    "ideo_baseline_n": ("long", "Anzahl Ideologie-Baseline-Videos (ohne Krieg)"),
    "api_abbruch": ("byte", "vom ~20.000er-Playlist-Limit betroffen (nachgescrapt)"),
    "n_videos_api": ("long", "abgerufene Videos (vor Laengenfilter)"),
    "n_videos": ("long", "Videos nach Laengenfilter"),
}

DTYPES = {"byte": "Int8", "long": "Int32", "double": "float64", "str": "str"}


def exportiere(df, spalten, datei, wertelabels):
    df = df[list(spalten)].copy()
    daten = {}
    for name, (typ, _) in spalten.items():
        assert len(name) <= 32 and name.isascii(), name
        if typ == "tc":
            df[name] = pd.to_datetime(df[name])
            daten[name] = "tc"
        elif typ == "str":
            df[name] = df[name].fillna("").astype(str)
        else:
            df[name] = df[name].astype(DTYPES[typ])
    df.to_stata(AUSGABE_PFAD / datei, version=118, write_index=False, convert_dates=daten,
                variable_labels={n: l for n, (_, l) in spalten.items()},
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
tab1 sample_vorkrieg sample_baseline sample_whitelist api_abbruch

use videos_roh.dta, clear
describe
codebook, compact
isid video_id
tab1 politisch_klass krieg_klass pop_klass pos_klass transkript baseline_stichprobe

merge m:1 channel_id using kanaele_roh.dta
* Erwartung: keine Videos nur in master (_merge == 1); Kanaele nur in using
* (_merge == 2) sind solche ohne Video > 180 s.
tab _merge
assert _merge != 1
"""


def main():
    fehlend = set(TOPIC_KEYWORDS) - set(TOPICS) - {KRIEG_TOPIC}
    if fehlend:
        raise KonsistenzFehler(f"Themen aus TOPIC_KEYWORDS ohne Exportvariable in TOPICS: {sorted(fehlend)}")
    os.makedirs(AUSGABE_PFAD, exist_ok=True)
    kanal_ids = lade_kanaele()
    alle, v, ideo_video = baue_videos(kanal_ids)
    k = baue_kanaele(kanal_ids, alle, v, ideo_video)

    log("")
    log("[Abdeckung] Videoebene (Anteil nicht fehlend bzw. = 1):")
    for s in ["views", "likes", "kommentare", "politisch", "krieg", *TOPICS.values(), "krieg_transkript",
              "pop_gesamt", "pos_russland", "pos_westpolitik"]:
        log(f"    {s}: {v[s].notna().mean():.2%} nicht fehlend")
    for s in ["politisch_klass", "krieg_klass", "topic_klass", "pop_klass", "pos_klass", "transkript",
              "baseline_stichprobe"]:
        log(f"    {s} = 1: {int(v[s].sum())} ({v[s].mean():.2%})")
    log("[Abdeckung] Kanaele je Sample-Kennzeichen und Medientyp:")
    log(k.groupby(k["medientyp"].fillna(-1).astype(int))[["sample_vorkrieg", "sample_baseline", "sample_whitelist"]]
        .agg(["sum", "size"]).to_string())
    log(f"    Kanaele gesamt: {len(k)}, ohne Medientyp: {int(k['medientyp'].isna().sum())}, "
        f"mit Ideologie-Baseline: {int(k['ideo_gesellschaft_baseline'].notna().sum())}")

    konsistenz(v, k)

    ja_nein = {0: "nein", 1: "ja"}
    exportiere(v, VIDEO_SPALTEN, "videos_roh.dta",
               {"live_typ": {0: "regulaer", 1: "Livestream", 2: "Premiere"},
                **{s: ja_nein for s, (t, _) in VIDEO_SPALTEN.items() if t == "byte" and s != "live_typ"}})
    exportiere(k, KANAL_SPALTEN, "kanaele_roh.dta",
               {"medientyp": MEDIENTYP_LABELS,
                **{s: ja_nein for s, (t, _) in KANAL_SPALTEN.items() if t == "byte" and s != "medientyp"}})
    (AUSGABE_PFAD / "check_rohdaten.do").write_text(DO_FILE, encoding="utf-8")
    log("[Export] check_rohdaten.do geschrieben")
    schreibe_log()


if __name__ == "__main__":
    main()

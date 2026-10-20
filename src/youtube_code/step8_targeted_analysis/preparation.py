# get df mit videos in long format from respective channels
# alt_kanaele + upload_starke_kanaele

# remove all daily news videos

# get overview of video-length by channel
# check whether there is a war premium

# Hinweis (13.10.2026): Alle Variablen dieses Datensatzes stecken inzwischen im
# Hauptdatensatz outputs/stata_rohdaten/videos_roh.dta
# (step6_auswertung/export_stata_rohdaten.py, alle Sample-Kanaele): rel_*,
# format/format_derived, news_show/special_show (dort . fuer Kanaele ohne
# gepruefte Muster; dazu pk_sitzung), post_war, monat, titel. alt_kanal = format_liste == 2 in
# kanaele_roh.dta; Umbenennungen siehe docs/codebuch_rohdatensatz.md.

import pandas as pd

from youtube_code.config import ADHOC_OUTPUT
from youtube_code.store.video_registry import (
    get_video_metadata, get_video_formats, get_video_stats, _duration_seconds_series,
)
from youtube_code.step3_topic_relevance.topic_keywords import KW_RE, TIERS, TOPIC_KEYWORDS
from youtube_code.step3_topic_relevance.news_show_patterns import NEWS, SPECIAL, classify_frame

clist = ["UC5NOEUbkLheQcaaRldYW5GA",
         "UCACdxU3VrJIJc7ujxtHWs1w",
         "UCwyiPnNlT8UABRmGmU0T9jg",
         "UCeqKIgPQfNInOswGRWt48kQ",
         "UCMIgOXM2JEQ2Pv2d0_PVfcg",
         "UCZMsvbAhhRblVGXmEXW8TSA",
         "UC4zcMHyrT_xyWlgy5WGpFFQ",
         "UCSeil5V81-mEGB1-VNR7YEA",
         "UCcPcua2PF7hzik2TeOBx3uw",
         "UCMpW4tdyZUid2Ka9_FuDDhQ",]

alist = [
    "UC62IIFhchBWQxLPSyUatD-A", "UCJiRXf1Pb0ZkoPD7qcQIvlg", "UCyH9w3VhfZPdjH28VFeoHUA",
     "UC-qQ1TNcFK3DqD7jEK5D_jg", "UCq-b0dwW97YRZWgSCikWQRA", "UCnk0-FU1ybs9MpWg8g3yqMw",
     "UCsekpwdMv9PBCOftuuKncfw", "UCpV9LpCg4uwYCQZ3qoEn_YQ",
     "UCqZSdUJqd2T0oqr6BEA3ONw", "UCbanHTRuGv2Fi7flpO735yw", "UCiTKi7Ahf3E2yMGpmIxSvgw",
     "UCthYpKoujTMmDX75fGr5o8A", "UCiTJladOHCMkKndVBsn23VQ", "UCvOXPxj9VHHUQjGWENjpceg",
]

channel_list = clist + alist

df = get_video_metadata(channel_list, min_duration_seconds=None)
video_ids = df["video_id"].tolist()

fmt = get_video_formats(video_ids = video_ids)
df = pd.merge(df, fmt[["video_id", "format"]], on = "video_id", how = "left")

# WELT: yt-dlp-Fallback fuer /videos endet ca. Juli 2025 (siehe step1_sample/README.md),
# Shorts (/shorts) und Livestreams (/streams) sind aber bis 2021 vollstaendig erfasst
# -> Videos ohne Format im Format-Fenster per Ausschluss als "long" (ggf. inkl.
# inzwischen geloeschter/privater Videos). format_derived markiert diese Faelle.
WELT_ID = "UCZMsvbAhhRblVGXmEXW8TSA"
FORMAT_WINDOW = ("2021-01-01", "2026-07-01")
welt_ohne_format = (
    (df["channel_id"] == WELT_ID)
    & df["format"].isna()
    & df["published_at"].between(*FORMAT_WINDOW)
)
df["format_derived"] = welt_ohne_format
df.loc[welt_ohne_format, "format"] = "long"
print(f"WELT: {welt_ohne_format.sum()} Videos per Ausschluss als long gesetzt")

# Themen-Relevanz NUR auf Basis des Titels, fuer alle 13 Themen: dieselben Regexe
# wie step3_topic_relevance, aber ohne Beschreibung. Direkt berechnet statt aus
# video_topic_relevance gelesen, weil dort Videos <= 180 s (inkl. aller Shorts)
# gar nicht klassifiziert sind. Fuer die klassifizierten Videos identisch mit den
# *_title-Eintraegen in matched_keywords.
# Je Thema zwei Varianten: rel_{topic}_core (nur core-Liste = Hauptdefinition) und
# rel_{topic}_cw (core ODER wide = Robustheit). Die wide-Listen von climate/gender
# enthalten Kampfbegriffe ("Klimahysterie", "woke") und messen damit teils das
# Framing mit (siehe Docstring topic_keywords.py).
title = df["title"].fillna("")
for topic, cfg in TOPIC_KEYWORDS.items():
    hits = {t: title.str.contains(KW_RE[f"{cfg['prefix']}_{t}"], na=False)
            for t in TIERS if t in cfg}
    df[f"rel_{topic}_core"] = hits["core"].astype(int)
    df[f"rel_{topic}_cw"] = pd.concat(hits.values(), axis=1).any(axis=1).astype(int)

# Ganze Nachrichtensendungen / Sondersendungen per Titel-Muster je Kanal
# (step3_topic_relevance/news_show_patterns.py). Kanaele ohne Ganzsendungs-Format
# haben dort bewusst keine Muster -> immer 0. Die Muster fuer clist/alist sind
# nur auf long-Videos geprueft (Teaser-Regel fuer Shorts dort ungeprueft, siehe
# Modul-Docstring). Die Kategorie PRESSE (pressekonferenz) betrifft nur Kanaele
# aus weitere_kanaele.csv, die hier nicht vorkommen.
sendung = classify_frame(df)
df["news_show"] = (sendung == NEWS).astype(int)
df["special_show"] = (sendung == SPECIAL).astype(int)

# Video-Stats: rohe kumulierte Werte (einmaliger Snapshot beim Abruf, NICHT pro Tag
# normalisiert). Fehlende Werte = von der API nicht geliefert (z.B. Likes/Kommentare
# deaktiviert), nicht 0 - bleiben missing.
stats = get_video_stats(video_ids = video_ids)
df = pd.merge(df, stats[["video_id", "view_count", "like_count", "comment_count", "duration"]],
              on = "video_id", how = "left")
df["duration_sec"] = _duration_seconds_series(df["duration"]).to_numpy()
df = df.drop(columns = "duration")

# Zeitvariablen fuer den Vorher/Nachher-Vergleich (Kriegsbeginn 24.02.2022)
KRIEGSBEGINN = pd.Timestamp("2022-02-24")
df["published_at"] = pd.to_datetime(df["published_at"], format = "ISO8601", utc = True).dt.tz_localize(None)
df["post_war"] = (df["published_at"] >= KRIEGSBEGINN).astype(int)
df["monat"] = (df["published_at"].dt.year - 1960) * 12 + df["published_at"].dt.month - 1   # Stata %tm
df["alt_kanal"] = df["channel_id"].isin(alist).astype(int)
df["format_derived"] = df["format_derived"].astype(int)

print(len(df))

print(df["format"].value_counts(dropna=False))
print(df["format"].value_counts(dropna=False, normalize=True).mul(100).round(1))

# Stata-Export (.dta Version 118 = UTF-8)
labels = {
    "video_id": "YouTube Video-ID",
    "channel_id": "YouTube Kanal-ID",
    "channel_title": "Kanalname",
    "published_at": "Veroeffentlichung (UTC)",
    "title": "Videotitel",
    "format": "Format: short/long/live (leer = unbekannt)",
    "format_derived": "1 = Format per Ausschluss gesetzt (nur WELT)",
    "view_count": "Views (Snapshot, kumuliert)",
    "like_count": "Likes (Snapshot, kumuliert)",
    "comment_count": "Kommentare (Snapshot, kumuliert)",
    "duration_sec": "Videodauer in Sekunden",
    "post_war": "1 = ab Kriegsbeginn 24.02.2022",
    "monat": "Veroeffentlichungsmonat (Stata %tm)",
    "alt_kanal": "1 = Kanal aus alist (alternative Kanaele)",
    "news_show": "1 = ganze Nachrichtensendung (Titel-Muster)",
    "special_show": "1 = Sondersendung/Themen-Update (Titel-Muster)",
}
for t in TOPIC_KEYWORDS:
    labels[f"rel_{t}_core"] = f"Titel-Treffer {t} (nur core)"[:80]
    labels[f"rel_{t}_cw"] = f"Titel-Treffer {t} (core+wide)"[:80]

export = df[list(labels)].copy()
export["format"] = export["format"].fillna("")
for col in ["view_count", "like_count", "comment_count", "duration_sec"]:
    export[col] = export[col].astype("float64")

STATA_PATH = ADHOC_OUTPUT / "kriegspraemie" / "videos_kriegspraemie.dta"
STATA_PATH.parent.mkdir(parents = True, exist_ok = True)
export.to_stata(STATA_PATH, version = 118, write_index = False,
                convert_dates = {"published_at": "tc"}, variable_labels = labels)
print(f"Stata-Datei geschrieben: {STATA_PATH} ({len(export)} Videos, {export.shape[1]} Variablen)")

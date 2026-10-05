"""
Summary Stats für verschiedene Medientypen (ÖRR, TRAD, L/M/R ALT):
    - Durchschnittliche/Median Views (Video-/Monats-Ebene)
    - Anteil politischer Videos
    - Anteil Kriegsvideos
    - Views nach Art des Videos (politisch, Kriegs-, gesamt)
    - Videolängen
    - Anzahl Videos/Monat
"""

import pandas as pd

from deskriptiv_aggregation import lade_medientyp, lade_ideologie
from youtube_code.config import OUTPUTS
from frage4_kriegspraemie_medientyp_bericht import lade_video_daten

RESULTS_PATH = OUTPUTS / "segment_analysis"
PFAD_EINGABE = RESULTS_PATH / "channel_video_erfolg.csv"
PFAD_WHITELIST = RESULTS_PATH / "frage1_kanal_whitelist.csv"

print("Reading df...")
df = pd.read_csv(RESULTS_PATH / "df_overview.csv", low_memory = False)


print("Generating Stats...")
views_by_gruppe = df.groupby("gruppe5").agg(
    log_views = ("log_views", "mean"),
    median_views = ("view_count", "median"),
    n_videos = ("video_id", "count")
).reset_index()

views_by_gruppe_videotype = df.groupby(["gruppe5", "ist_politisches_video"]).agg(
    log_views = ("log_views", "mean"),
    median_views = ("view_count", "median"),
    n_videos=("video_id", "count")
).reset_index()

views_by_gruppe_kriegsvideo = df.groupby(["gruppe5", "ist_kriegsvideo"]).agg(
    log_views = ("log_views", "mean"),
    median_views = ("view_count", "median"),
    n_videos = ("video_id", "count"),
).reset_index()

type_by_gruppe = df.groupby("gruppe5").agg(
    kriegsvideo_share = ("ist_kriegsvideo", "mean"),
    politics_share = ("ist_politisches_video", "mean"),
    politics_share_llm = ("ist_politisches_video_llm", "mean"),
    upload_dichte = ("log_upload_dichte", "mean"),
    duration = ("duration_seconds", "mean"),
    n_videos=("video_id", "count"),
)

with pd.option_context("display.max_columns", None, "display.width", None):
    print("Video-Level Stats:")
    print("\n", "="*90, "\n", views_by_gruppe)
    print("\n", "="*90, "\n", views_by_gruppe_videotype)
    print("\n", "="*90, "\n", views_by_gruppe_kriegsvideo)
    print("\n", "="*90, "\n", type_by_gruppe)


monthly = df.groupby(["channel_id", "rel_monat"]).agg(
    gruppe5 = ("gruppe5", "first"),
    log_views=("log_views", "mean"),
    median_views=("view_count", "median"),
    n_videos=("video_id", "count"),
).reset_index()


views_by_gruppe = monthly.groupby("gruppe5").agg(
    log_views = ("log_views", "mean"),
    median_views = ("median_views", "median"),
    n_videos = ("n_videos", "sum")
).reset_index()

monthly_separate = df.groupby(["channel_id", "rel_monat", "ist_politisches_video"]).agg(
    gruppe5 = ("gruppe5", "first"),
    log_views=("log_views", "mean"),
    median_views=("view_count", "median"),
    n_videos=("video_id", "count"),
).reset_index()

views_by_gruppe_videotype = monthly_separate.groupby(["gruppe5", "ist_politisches_video"]).agg(
    log_views = ("log_views", "mean"),
    median_views = ("median_views", "median"),
    n_videos=("n_videos", "sum"),
).reset_index()

monthly_separate = df.groupby(["channel_id", "rel_monat", "ist_kriegsvideo"]).agg(
    gruppe5 = ("gruppe5", "first"),
    log_views=("log_views", "mean"),
    median_views=("view_count", "median"),
    n_videos=("video_id", "count"),
).reset_index()

views_by_gruppe_kriegsvideo = monthly_separate.groupby(["gruppe5", "ist_kriegsvideo"]).agg(
    log_views = ("log_views", "mean"),
    median_views = ("median_views", "median"),
    n_videos=("n_videos", "sum"),
).reset_index()

with pd.option_context("display.max_columns", None, "display.width", None):
    print("\n\nMonthly-Level Stats:")
    print("\n", "="*90, "\n", views_by_gruppe)
    print("\n", "="*90, "\n", views_by_gruppe_videotype)
    print("\n", "="*90, "\n", views_by_gruppe_kriegsvideo)

# df.to_csv(RESULTS_PATH / "df_overview.csv", index = False)
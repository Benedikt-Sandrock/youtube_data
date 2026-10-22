from pathlib import Path
import pandas as pd
import ast
import numpy as np
from youtube_code.store.video_registry import get_video_stats

# === CONFIG ===


results_pattern = "*results.xlsx"
key_file = "schluessel.csv"
directory = Path(".")   # "." = current directory

constant_vars = ["channel_id", "channel_title", "media_type", "medientyp", "published_at",
                 "datum_lokal", "phase", "hand", "pilot", "video_id"]

phasen_grenzen = [
    pd.to_datetime("2022-01-01"),
    pd.to_datetime("2022-02-09"),
    pd.to_datetime("2022-02-23"),
    pd.to_datetime("2022-04-30")
]
phasen_labels = ["Vorher", "Eskalation", "Kriegsbeginn"]

dfs = []
for file in directory.glob(results_pattern):
    temp_df = pd.read_excel(file)
    dfs.append(temp_df)

df = pd.concat(dfs, ignore_index = True)
segments = len(df)
print(f"Number of segments rated: {segments}")

key_df = pd.read_csv(key_file)

df = pd.merge(df, key_df, on = "segment_id", how = "left")

df = df[df["kodierbar"] == 1]
segments_new = len(df)
dropped = segments - segments_new
print(f"Dropped {dropped} segments which could not be rated.")

df = df.reset_index(drop = True)
df["words_total"] = df.groupby("video_id")["n_woerter"].transform("sum")
df["segment_weight"] = df["n_woerter"] / df["words_total"]

# Rangfolgen für "größter Wert gewinnt" (höherer Rang = stärker)
explicitness_rank = {"implizit": 1, "explizit": 2}
status_rank = {"nicht_thematisiert": 0, "deskriptiv": 1, "bewertend": 2}
intensitaet_rank = {"sachlich": 0, "abwertend": 1, "delegitimierung": 2}

for col in ["themen", "krieg_aspekte", "estab_gegenstand"]:
    df[col] = df[col].apply(ast.literal_eval)

inverse_intens = {n:w for w,n in intensitaet_rank.items()}
df["estab_intensitaet"] = df["estab_intensitaet"].replace(inverse_intens)


# Spalten, die auf Segmentebene klassifiziert wurden bzw. segmentspezifisch sind
classification_vars = ["text", "kodierbar", "themen", "hauptthema", "krieg_bezug", "krieg_aspekte",
                       "rus_status", "rus_score", "estab_status", "estab_explizit", "estab_score",
                       "estab_gegenstand", "estab_kritik_richtung", "estab_intensitaet"]
segment_vars = ["segment_id", "segment_index", "n_segmente_video", "n_woerter", "segment_weight"]


def multi_hot(lists, prefix):
    """Listenspalte -> 0/1-Matrix (eine Spalte pro Label, Index = Segmentindex)."""
    exploded = lists.explode().dropna()
    dummies = pd.get_dummies(exploded, prefix = prefix, dtype = int).groupby(level = 0).max()
    return dummies.reindex(lists.index, fill_value = 0)


def video_max_label(col, rank):
    """Pro Video das Label mit dem höchsten Rang; NaN, wenn alle Segmente NaN."""
    inverse = {v: k for k, v in rank.items()}
    num = df[col].map(rank).groupby(df["video_id"]).max()
    return num.map(inverse)


def video_weighted_mean(col):
    """Pro Video Mittelwert über nicht-NaN-Segmente, gewichtet mit segment_weight."""
    weight = df["segment_weight"].where(df[col].notna(), 0.0)
    numerator = (df[col].fillna(0.0) * weight).groupby(df["video_id"]).sum()
    denominator = weight.groupby(df["video_id"]).sum()
    return numerator / denominator.where(denominator > 0)


# ==== AGGREGATION =====

# 1. Kanal-/Video-Metadaten: alle Spalten, die innerhalb eines Videos konstant sind
candidate_vars = [c for c in df.columns if c not in classification_vars + segment_vars + ["video_id"]]
nunique_per_video = df.groupby("video_id")[candidate_vars].nunique(dropna = False).max()
meta_vars = nunique_per_video[nunique_per_video <= 1].index.tolist()
varying_vars = nunique_per_video[nunique_per_video > 1].index.tolist()
video_groups = df.groupby("video_id")
df_video = video_groups[meta_vars].first()

# Segment-Flags (z.B. hand, pilot): 1, wenn mind. ein Segment des Videos den Wert 1 hat
for col in varying_vars:
    if not set(df[col].dropna().unique()) <= {0, 1}:
        print(f"Warnung: Spalte {col} variiert innerhalb von Videos und ist kein 0/1-Flag, wird nicht übernommen.")
        continue
    df_video[col] = video_groups[col].max()

# 2. Themen: gewichteter Anteil des Videos
topic_dummies = multi_hot(df["themen"], "thema")
topic_share = topic_dummies.mul(df["segment_weight"], axis = 0).groupby(df["video_id"]).sum()
topic_any = topic_dummies.groupby(df["video_id"]).max()
df_video = df_video.join(topic_share)
df_video["n_topics"] = topic_any.sum(axis = 1)   # Anzahl verschiedener Themen im Video

# Hauptthemen: Anzahl und Liste
df_video["n_hauptthemen"] = video_groups["hauptthema"].nunique()
df_video["hauptthemen"] = video_groups["hauptthema"].agg(lambda x: sorted(x.dropna().unique()))

# Gewichteter Anteil des Hauptthemas am Videos
main_topic_dummies = multi_hot(df["hauptthema"], "main_topic")
main_topic_share = main_topic_dummies.mul(df["segment_weight"], axis = 0).groupby(df["video_id"]).sum()
df_video = df_video.join(main_topic_share)

# 3. Krieg
df_video["krieg_bezug"] = video_max_label("krieg_bezug", explicitness_rank)
war_dummies = multi_hot(df["krieg_aspekte"], "krieg_aspekt")
df_video = df_video.join(war_dummies.groupby(df["video_id"]).max())

# 4. Russland
df_video["rus_status"] = video_max_label("rus_status", status_rank)
df_video["rus_score"] = video_weighted_mean("rus_score")

# 5. Establishment
df_video["estab_explizit"] = video_max_label("estab_explizit", explicitness_rank)
df_video["estab_status"] = video_max_label("estab_status", status_rank)
df_video["estab_score"] = video_weighted_mean("estab_score")
df_video["estab_intensitaet"] = video_max_label("estab_intensitaet", intensitaet_rank)

estab_topic_dummies = multi_hot(df["estab_gegenstand"], "estab_gegenstand")
df_video = df_video.join(estab_topic_dummies.groupby(df["video_id"]).max())

critique_dummies = pd.get_dummies(df["estab_kritik_richtung"], prefix = "estab_kritik", dtype = int)
df_video = df_video.join(critique_dummies.groupby(df["video_id"]).max())

# 6. Phase
df_video["datum_lokal"] = pd.to_datetime(df_video["datum_lokal"])
df_video["phase"] = pd.cut(df_video["datum_lokal"], bins = phasen_grenzen, labels = phasen_labels,
                           include_lowest = True)

df_video = df_video.reset_index()
print(f"Videos: {len(df_video)}, Variablen: {df_video.shape[1]}")
print(df_video.filter(like = "thema_").mean())

ids = df_video["video_id"].tolist()

stats_df = get_video_stats(video_ids=ids)
stats_ids = stats_df["video_id"].tolist()

cols_to_use = stats_df.columns.difference(df_video.columns).tolist() + ["video_id"]
df_video_stats = pd.merge(df_video, stats_df[cols_to_use], on = "video_id", how = "inner")
print(len(stats_df), len(df_video_stats), len(df_video))

df_video_stats.to_csv("video_results.csv", index = False)
print(f"Description of thema_krieg_ukraine:"
      f"\n{df_video["thema_krieg_ukraine"].describe(percentiles = [x / 100 for x in range(5,100, 5)])}")

# ===== EVALUATION =====

df = df_video.groupby(["channel_title","phase"])["thema_krieg_ukraine"].mean().reset_index()

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 1000)
print(df)
























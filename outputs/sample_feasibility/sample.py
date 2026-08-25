import pandas as pd
import numpy as np
import json

from youtube_code.config import TRANSCRIPTS, SAMPLES


def create_video_file_w_lables():
    df = pd.read_csv("videos_compact.csv")
    df2 = pd.read_csv("screening_labels.csv")

    print(len(df))
    print(df["politics"].mean())

    df = pd.merge(df, df2, on = "video_id", how = "left")
    df = df.drop(columns = "politics")
    print(df["politics_final"].mean())

    print(f"Core videos identified by title: {df["ukr_core_title"].mean()}")
    print(f"Core videos identified by desc: {df["ukr_core_desc"].mean()}")

    df["is_war_core"] = np.maximum(df["ukr_core_title"], df["ukr_core_desc"])
    df["is_war_wide"] = np.maximum.reduce(df[["is_war_core", "ukr_wide_title", "ukr_wide_desc"]], axis = 1)
    print(df["is_war_core"].mean(), df["is_war_wide"].mean())

    print(len(df))                              # muss weiterhin 733.824 sein
    print(df["politics_final"].notna().sum())         # wie viele Videos haben ein Label?
    print(df[["ukr_core_title","ukr_core_desc",
              "ukr_wide_title","ukr_wide_desc"]].isna().sum())

    # df["is_war"]      = df["is_war_core"].astype(bool)   # Treatment
    # df["war_adjacent"] = df["is_war_wide"].astype(bool)  # aus Kontrollen raus

    df.to_csv("videos_compact_pol_labels.csv", index = False)


def create_video_list_treatment_vids():
    df = pd.read_csv("videos_compact_pol_labels.csv")
    print(len(df))
    df = df[df["is_war_core"] == 1]
    print(len(df))

    vids = df["video_id"].to_list()

    with open("war_core_ids.json", "w", encoding = "utf-8") as f:
        json.dump(vids, f, ensure_ascii = False, indent = 2)



WAR_START    = pd.Timestamp("2022-02-24", tz="UTC")
MAX_WAR      = 50
MAX_BASELINE = 10
MIN_BASELINE = 5
SEED         = 20260821


def draw(pool, max_n):
    """Pro Kanal max_n Videos, gleichmäßig über Halbjahre, Vorhandene zuerst."""
    p = pool.sample(frac=1, random_state=SEED)                      # Zufallsreihenfolge
    p = p.sort_values("has_transcript", ascending=False, kind="stable")  # Vorhandene nach vorn
    p["rank"] = p.groupby(["channel_id", "half_index"]).cumcount()  # Position im Halbjahr
    return p.sort_values("rank", kind="stable").groupby("channel_id").head(max_n)


def create_download_list_descriptive():
    downloaded = set(pd.read_csv(TRANSCRIPTS / "all_transcripts_segments.csv",
                                 usecols=["video_id"])["video_id"])

    df = pd.read_csv("videos_compact_pol_labels.csv",
                     usecols=["video_id", "channel_id", "published_at",
                              "interval_index", "politics_final", "is_war_core"])
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    df = df.dropna(subset=["published_at", "interval_index", "channel_id"])
    df["half_index"]     = df["interval_index"].astype(int) // 2
    df["has_transcript"] = df["video_id"].isin(downloaded)

    war      = df[(df["is_war_core"] == 1) & (df["published_at"] >= WAR_START)]
    baseline = df[(df["is_war_core"] != 1) & (df["published_at"] < WAR_START)
                  & (df["politics_final"] == 1)]

    # --- Kanalflags ---
    flags = pd.DataFrame(index=pd.Index(df["channel_id"].unique(), name="channel_id"))
    flags["n_war"]      = war.groupby("channel_id").size().reindex(flags.index).fillna(0).astype(int)
    flags["n_baseline"] = baseline.groupby("channel_id").size().reindex(flags.index).fillna(0).astype(int)
    flags["channel_flag"] = "kein_krieg"
    flags.loc[flags["n_war"] > 0, "channel_flag"] = "krieg_ohne_baseline"
    flags.loc[(flags["n_war"] > 0) & (flags["n_baseline"] >= MIN_BASELINE),
              "channel_flag"] = "baseline_und_krieg"

    # --- Ziehung ---
    sample = pd.concat([draw(war, MAX_WAR).assign(sample_group="war"),
                        draw(baseline, MAX_BASELINE).assign(sample_group="baseline")])
    sample = sample.merge(flags["channel_flag"], left_on="channel_id", right_index=True)

    # --- Output ---
    to_download = sample.loc[~sample["has_transcript"], "video_id"].tolist()
    with open("descriptive_download_list.json", "w", encoding="utf-8") as f:
        json.dump(to_download, f, ensure_ascii=False, indent=2)

    sample.to_csv("descriptive_sample.csv", index=False)
    flags.reset_index().to_csv("descriptive_channel_flags.csv", index=False)

    print(flags["channel_flag"].value_counts())
    print(f"\nSample: {len(sample):,} | vorhanden: {sample['has_transcript'].sum():,} "
          f"| zu laden: {len(to_download):,}")
    return sample, flags


def prepare():
    """Lädt Metadaten + Transkriptstatus, gibt (war, baseline, df) zurück."""
    downloaded = set(pd.read_csv(TRANSCRIPTS / "all_transcripts_segments.csv",
                                 usecols=["video_id"])["video_id"])

    df = pd.read_csv("videos_compact_pol_labels.csv",
                     usecols=["video_id", "channel_id", "published_at",
                              "interval_index", "politics_final", "is_war_core"])
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    df = df.dropna(subset=["published_at", "interval_index", "channel_id"])
    df["half_index"]     = df["interval_index"].astype(int) // 2
    df["has_transcript"] = df["video_id"].isin(downloaded)

    war      = df[(df["is_war_core"] == 1) & (df["published_at"] >= WAR_START)]
    baseline = df[(df["is_war_core"] != 1) & (df["published_at"] < WAR_START)
                  & (df["politics_final"] == 1)]
    return war, baseline, df


def report_coverage():
    """Übersicht: was ist an Transkripten schon da?"""
    war, baseline, df = prepare()

    # Verfügbare Videos vs. bereits geladene Transkripte, je Kanal
    cov = pd.DataFrame(index=pd.Index(df["channel_id"].unique(), name="channel_id"))
    for name, pool in [("baseline", baseline), ("war", war)]:
        g = pool.groupby("channel_id")
        cov[f"{name}_videos"] = g.size().reindex(cov.index).fillna(0).astype(int)
        cov[f"{name}_trans"]  = g["has_transcript"].sum().reindex(cov.index).fillna(0).astype(int)

    n = len(cov)
    print(f"Kanäle gesamt: {n}\n")

    print("--- Kanäle mit verfügbaren Videos (Potenzial) ---")
    print(f"  Baseline (>=1 / >={MIN_BASELINE}): "
          f"{(cov.baseline_videos >= 1).sum()} / {(cov.baseline_videos >= MIN_BASELINE).sum()}")
    print(f"  Kriegsvideos (>=1 / >=10):        "
          f"{(cov.war_videos >= 1).sum()} / {(cov.war_videos >= 10).sum()}\n")

    print("--- Kanäle mit bereits vorhandenen Transkripten ---")
    print(f"  Baseline (>=1 / >={MIN_BASELINE}): "
          f"{(cov.baseline_trans >= 1).sum()} / {(cov.baseline_trans >= MIN_BASELINE).sum()}")
    print(f"  Kriegsvideos (>=1 / >=10):        "
          f"{(cov.war_trans >= 1).sum()} / {(cov.war_trans >= 10).sum()}\n")

    print("--- Kombination (vorhandene Transkripte) ---")
    print(pd.crosstab(cov.baseline_trans >= MIN_BASELINE, cov.war_trans >= 1,
                      rownames=["Baseline ok"], colnames=["Krieg >=1"]), "\n")

    print("--- Abdeckungsquote je Halbjahr ---")
    for name, pool in [("baseline", baseline), ("war", war)]:
        q = pool.groupby("half_index").agg(videos=("video_id", "size"),
                                           transkripte=("has_transcript", "sum"))
        q["quote"] = (q.transkripte / q.videos).round(3)
        print(f"[{name}]")
        print(q, "\n")

    print("--- Vorhandene Transkripte je Kanal (Verteilung) ---")
    print(cov[["baseline_trans", "war_trans"]].describe().round(1))

    return cov

# create_download_list_descriptive()
# report_coverage()

df = pd.read_csv("videos_compact_pol_labels.csv")

df = df[df["channel_id"] == "UC9qdoYTVU413M6EvqDRZDtA"]
df = df[df["period"] < 0]

print(len(df))
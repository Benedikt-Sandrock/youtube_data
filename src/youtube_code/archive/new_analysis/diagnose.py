import pandas as pd
from pathlib import Path

from youtube_code.config import OUTPUTS, SAMPLES

OUT   = OUTPUTS / "pilot"
STATE = SAMPLES / "russia" / "longitudinal_screening_state.csv"   # anpassen


p = pd.read_csv(OUT / "pilot_videos.csv")
m = p[(p.role == "primary") & (p.sample_type == "main") & (p.treat == 1)]
print(m.nlargest(8, "weight")[
    ["channel_title", "window", "weight"]].to_string())
print(m.weight.quantile([.5, .9, .95, .99]).round(1).to_string())
# s = pd.read_csv(STATE, usecols=["video_id", "politics_final"])
# s[s.politics_final.notna()].to_csv(
#     OUT / "screening_labels.csv", index=False)      # ca. 278.000 Zeilen

# state = pd.read_csv(STATE, usecols=[
#     "video_id", "channel_id", "interval_index", "candidate_rank",
#     "politics_final"])
# rich  = pd.read_csv(OUT / "videos_rich.csv",
#                     usecols=["channel_id", "channel_title", "interval_index"])
#
# # --- 1. Wer fehlt? ----------------------------------------------------
# missing = sorted(set(rich.channel_id) - set(state.channel_id))
# print(f"{len(missing)} Kanaele ohne Screening")
#
# info = (rich[rich.channel_id.isin(missing)]
#         .groupby(["channel_id", "channel_title"]).size()
#         .rename("videos").reset_index())
# traj = pd.read_csv(OUT / "A2_channel_trajectories_all_etabliert.csv")
# coh  = pd.read_csv(OUT / "B0_cohorts_all_etabliert.csv")
# coh  = coh.rename(columns={coh.columns[0]: "channel_id"})
# info = info.merge(traj[["channel_id", "typ", "shock"]], how="left") \
#            .merge(coh[["channel_id", "kohorte"]], how="left")
# print(info.to_string())
# print("\nVerteilung der Fehlenden nach Typ:")
# print(info.typ.value_counts(dropna=False))
#
# # --- 2. Steht die Antwort schon in der Ausschlussdatei? ---------------
# excl = OUT.parent / "excluded_channels.csv"     # Pfad ggf. anpassen
# if excl.exists():
#     e = pd.read_csv(excl)
#     print(f"\nIn excluded_channels.csv: "
#           f"{len(set(missing) & set(e.channel_id))} von {len(missing)}")
#
# # --- 3. Aggregat fuer mich --------------------------------------------
# agg = (state.groupby(["channel_id", "interval_index"])
#        .agg(n_candidates=("video_id", "size"),
#             n_screened=("politics_final", "count"),
#             n_political=("politics_final", lambda s: (s == 1).sum()),
#             n_unclear=("politics_final", lambda s: (s == -1).sum()),
#             max_screened_rank=("candidate_rank",
#                                lambda s: s[state.loc[s.index,
#                                    "politics_final"].notna()].max()))
#        .reset_index())
# agg.to_csv(OUT / "screening_coverage.csv", index=False)
# print(f"\n{len(agg):,} Zeilen -> screening_coverage.csv")
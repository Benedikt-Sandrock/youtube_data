#!/usr/bin/env python3
"""
war_video_overview.py — Wie viele Kriegsvideos hat welcher Kanal wann?

Beantwortet die Designfrage: Wie gross koennen die Zellen (Kriegsvideos vs.
politische Kontrollvideos je Kanal-Quartal) tatsaechlich werden?

Der Median ueber ALLE Kanaele ist dafuer der falsche Massstab — er wird von
den Kanaelen gedrueckt, die zum Thema gar nicht senden und die fuer die
Ziehung ohnehin ausscheiden. Dieses Skript zeigt die Verteilung, nicht nur
die Mitte, und rechnet je Schwelle aus, wie viele Kanaele eine Zelle dieser
Groesse tragen koennten.

Ausgabe:
  war_videos_by_quarter.csv    Kanal x Quartal, Kriegs- und Kontrollzahlen
  war_videos_wide.csv          dasselbe breit, eine Zeile je Kanal
  war_videos_overview.pdf      vier Diagramme

Benoetigt: pandas, numpy. Optional: matplotlib (fuer die Grafik).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# KONFIGURATION
# ---------------------------------------------------------------------------

INDIR = r"C:\Users\bened\PycharmProjects\youtube_data\outputs\sample_feasibility"
OUTDIR = r"C:\Users\bened\PycharmProjects\youtube_data\outputs\pilot"

VIDEOS_FILE = "videos_rich.csv"
TRAJ_FILE = "A2_channel_trajectories_all_etabliert.csv"
COHORT_FILE = "B0_cohorts_all_etabliert.csv"
LABELS_FILE = "screening_labels.csv"

# Gleiche Filter wie in der Pilotziehung, damit die Zahlen vergleichbar sind.
MIN_DURATION_S = 180
EXCLUDE_LIVE = True
ONLY_ETABLIERT = True

# Fenstergroesse in Intervallen: 1 = Quartal, 2 = Halbjahr.
# Halbjahre verdoppeln die verfuegbaren Kriegsvideos je Zelle.
WINDOW_SIZE = 1

# Nur Perioden ab hier (0 = Invasionsmonat)
MIN_PERIOD = 0


def load(indir: Path):
    v = pd.read_csv(indir / VIDEOS_FILE)
    v["treat"] = (v.ukr_core_title | v.ukr_wide_title
                  | v.ukr_core_desc | v.ukr_wide_desc).astype(int)

    n0 = len(v)
    v = v[v.duration_s >= MIN_DURATION_S]
    if EXCLUDE_LIVE:
        v = v[v.is_live == 0]
    v = v[v.period >= MIN_PERIOD]
    print(f"Videos: {n0:,} -> {len(v):,} (Dauer >= {MIN_DURATION_S}s, "
          f"period >= {MIN_PERIOD})")

    lab = indir / LABELS_FILE
    if lab.exists():
        s = pd.read_csv(lab)
        v = v.merge(s[["video_id", "politics_final"]], on="video_id", how="left")
        v["is_political"] = v.politics_final == 1
        print(f"Screening-Labels: {v.politics_final.notna().sum():,} Videos")
    else:
        v["is_political"] = np.nan
        print(f"! {LABELS_FILE} fehlt — Kontrollzahlen bleiben leer")

    traj = pd.read_csv(indir / TRAJ_FILE)
    traj = traj[[c for c in ("channel_id", "typ", "shock", "late")
                 if c in traj.columns]]
    coh = pd.read_csv(indir / COHORT_FILE)
    if coh.columns[0] != "channel_id":
        coh = coh.rename(columns={coh.columns[0]: "channel_id"})
    meta = traj.merge(coh[["channel_id", "kohorte"]], on="channel_id", how="outer")

    if ONLY_ETABLIERT:
        keep = set(meta.loc[meta.kohorte == "etabliert", "channel_id"])
        v = v[v.channel_id.isin(keep)]
        print(f"Nur etablierte Kanaele: {v.channel_id.nunique():,}")
    return v, meta


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--indir", default=INDIR)
    p.add_argument("--outdir", default=OUTDIR)
    a = p.parse_args()

    indir, outdir = Path(a.indir), Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    v, meta = load(indir)

    # Fenster bilden
    v["win"] = v.interval_index // WINDOW_SIZE
    lab = (v.groupby("win").period.agg(["min", "max"])
           .apply(lambda r: f"M{int(r['min'])}-{int(r['max'])}", axis=1))

    long = v.groupby(["channel_id", "win"]).agg(
        n_videos=("treat", "size"),
        n_war=("treat", "sum"),
        n_pol_ctrl=("is_political",
                    lambda s: int((s.fillna(False)
                                   & (v.loc[s.index, "treat"] == 0)).sum())),
    ).reset_index()
    long["win_label"] = long.win.map(lab)
    long["war_share"] = long.n_war / long.n_videos
    long = long.merge(
        v[["channel_id", "channel_title"]].drop_duplicates("channel_id"),
        on="channel_id", how="left").merge(meta, on="channel_id", how="left")

    cols = ["channel_id", "channel_title", "typ", "kohorte", "win",
            "win_label", "n_videos", "n_war", "n_pol_ctrl", "war_share"]
    long[cols].to_csv(outdir / "war_videos_by_quarter.csv", index=False)

    wide = long.pivot(index="channel_id", columns="win_label", values="n_war")
    order = lab.sort_index().tolist()
    wide = wide.reindex(columns=[c for c in order if c in wide.columns])
    wide = wide.fillna(0).astype(int)
    wide.insert(0, "n_war_total", wide.sum(axis=1))
    wide = (v[["channel_id", "channel_title"]].drop_duplicates("channel_id")
            .merge(meta[["channel_id", "typ"]], on="channel_id", how="left")
            .set_index("channel_id").join(wide, how="right")
            .sort_values("n_war_total", ascending=False))
    wide.to_csv(outdir / "war_videos_wide.csv")

    # ---------------------------------------------------------------- Bericht
    print("\n" + "=" * 72)
    print("KONZENTRATION — wie ungleich sind die Kriegsvideos verteilt?")
    print("=" * 72)
    tot = wide.n_war_total.sort_values(ascending=False)
    print(f"Kriegsvideos gesamt : {int(tot.sum()):,}")
    print(f"Kanaele             : {len(tot):,}")
    for q in (0.10, 0.25, 0.50):
        k = max(int(len(tot) * q), 1)
        print(f"  Top {q:.0%} der Kanaele ({k:>3}) tragen "
              f"{tot.head(k).sum() / max(tot.sum(), 1):>5.1%} aller Kriegsvideos")
    print(f"  Kanaele ohne ein einziges: {int((tot == 0).sum()):,}")

    print("\n" + "=" * 72)
    print("VERTEILUNG JE FENSTER (nur Kanaele mit >= 1 Kriegsvideo)")
    print("=" * 72)
    print("Der Median ueber ALLE Kanaele ist irrefuehrend — er misst vor allem,")
    print("wie viele Kanaele zum Thema gar nicht senden.\n")
    print(f"{'Fenster':<12}{'Kanaele>0':>11}{'p25':>6}{'Median':>8}"
          f"{'p75':>6}{'p90':>6}{'max':>7}")
    for w in sorted(long.win.unique()):
        g = long[(long.win == w) & (long.n_war > 0)]
        if not len(g):
            continue
        q = g.n_war.quantile([.25, .5, .75, .9])
        print(f"{lab[w]:<12}{len(g):>11,}{q.iloc[0]:>6.0f}{q.iloc[1]:>8.0f}"
              f"{q.iloc[2]:>6.0f}{q.iloc[3]:>6.0f}{g.n_war.max():>7.0f}")

    print("\n" + "=" * 72)
    print("TRAGFAEHIGKEIT — wie viele Kanaele koennen welche Zellgroesse?")
    print("=" * 72)
    print("Bedingung: >= k Kriegsvideos UND >= k politische Kontrollen,")
    print("und zwar in ALLEN Fenstern. Das ist die Zahl, an der die")
    print("Ziehung dimensioniert wird.\n")
    nwin = long.win.nunique()
    print(f"{'k (Zelle kxk)':<16}{'alle Fenster':>14}{'>= 3 Fenster':>14}"
          f"{'>= 2 Fenster':>14}")
    for k in (1, 2, 3, 4, 6, 8):
        ok = ((long.n_war >= k) & (long.n_pol_ctrl >= k))
        cnt = long.assign(ok=ok).groupby("channel_id").ok.sum()
        print(f"{k:<16}{int((cnt >= nwin).sum()):>14}"
              f"{int((cnt >= 3).sum()):>14}{int((cnt >= 2).sum()):>14}")
    print(f"\n(Fenstergroesse: {WINDOW_SIZE} Intervall(e) = "
          f"{WINDOW_SIZE * 3} Monate, {nwin} Fenster insgesamt)")

    print("\n" + "=" * 72)
    print("NACH KANALTYP — Median Kriegsvideos je Fenster")
    print("=" * 72)
    pt = long.pivot_table(index="typ", columns="win_label", values="n_war",
                          aggfunc="median")
    pt = pt.reindex(columns=[c for c in order if c in pt.columns])
    print(pt.to_string())

    print(f"\n-> {outdir}/war_videos_by_quarter.csv, war_videos_wide.csv")

    # ---------------------------------------------------------------- Grafik
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("(matplotlib fehlt — keine Grafik)")
        return

    fig, ax = plt.subplots(2, 2, figsize=(15, 10))

    # (1) Heatmap: Kanaele x Fenster, nach Gesamtzahl sortiert
    hm = wide[[c for c in wide.columns if c not in ("channel_title", "typ",
                                                    "n_war_total")]]
    hm = hm.loc[wide.n_war_total.sort_values(ascending=False).index]
    im = ax[0, 0].imshow(np.log1p(hm.values), aspect="auto", cmap="magma",
                         interpolation="nearest")
    ax[0, 0].set_title("Kriegsvideos je Kanal und Fenster (log1p)")
    ax[0, 0].set_ylabel("Kanaele, sortiert nach Gesamtzahl")
    ax[0, 0].set_xticks(range(len(hm.columns)))
    ax[0, 0].set_xticklabels(hm.columns, rotation=90, fontsize=6)
    fig.colorbar(im, ax=ax[0, 0], fraction=.03)

    # (2) Lorenzkurve der Konzentration
    c = np.cumsum(tot.values) / max(tot.sum(), 1)
    x = np.arange(1, len(c) + 1) / len(c)
    ax[0, 1].plot(x, c, lw=2)
    ax[0, 1].plot([0, 1], [0, 1], ls="--", lw=.8, color="gray")
    ax[0, 1].set_title("Konzentration: Anteil der Kriegsvideos")
    ax[0, 1].set_xlabel("Anteil der Kanaele (absteigend sortiert)")
    ax[0, 1].set_ylabel("kumulierter Anteil der Kriegsvideos")
    ax[0, 1].grid(alpha=.3)

    # (3) Tragfaehigkeit je Fenster
    for k in (2, 3, 4, 6):
        y = [((long.win == w) & (long.n_war >= k)
              & (long.n_pol_ctrl >= k)).sum() for w in sorted(long.win.unique())]
        ax[1, 0].plot(range(len(y)), y, marker="o", ms=3, label=f"k = {k}")
    ax[1, 0].set_title("Kanaele mit >= k Kriegs- UND k Kontrollvideos")
    ax[1, 0].set_xticks(range(len(order)))
    ax[1, 0].set_xticklabels(order, rotation=90, fontsize=6)
    ax[1, 0].legend(fontsize=8)
    ax[1, 0].grid(alpha=.3)

    # (4) Verteilung je Fenster als Quantilbaender
    ws = sorted(long.win.unique())
    for qq, st in [(.5, "-"), (.75, "--"), (.9, ":")]:
        y = [long[(long.win == w) & (long.n_war > 0)].n_war.quantile(qq)
             for w in ws]
        ax[1, 1].plot(range(len(ws)), y, st, marker="o", ms=3,
                      label=f"p{int(qq * 100)}")
    ax[1, 1].set_title("Kriegsvideos je Kanal-Fenster (Kanaele mit > 0)")
    ax[1, 1].set_xticks(range(len(order)))
    ax[1, 1].set_xticklabels(order, rotation=90, fontsize=6)
    ax[1, 1].legend(fontsize=8)
    ax[1, 1].grid(alpha=.3)

    fig.tight_layout()
    fig.savefig(outdir / "war_videos_overview.pdf", dpi=300)
    print(f"-> {outdir}/war_videos_overview.pdf")


if __name__ == "__main__":
    main()
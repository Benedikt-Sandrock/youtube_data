#!/usr/bin/env python3
"""
draw_pilot.py — Stichprobenziehung fuer den Transkript-Piloten (v2).

Zwei Stichproben mit unterschiedlichem Zweck:

  BASELINE  Vorkriegsmaterial je Kanal, gepoolt. Grundlage fuer Kanal-
            Ideologie und -Populismus, die spaeter als MODERATOR dienen.
            Ausschliesslich Vorfenster: eine aus Nachkriegsmaterial
            geschaetzte Ideologie waere ein Bad Control.

  MAIN      Nachkriegsfenster, je Zelle Treatment UND Kontrolle.
            Grundlage fuer den Within-Video-Kontrast.

TREATMENT vs. KONTROLLE
  Treatment = Kriegs-Keyword in Titel ODER bereinigter Beschreibung.
              Politisch per Konstruktion (93.2% tragen YouTubes Kategorie
              Politics/Society), deshalb ohne Screening verwendbar.
  Kontrolle = ausschliesslich Videos mit politics_final == 1.
              Ohne diesen Filter waeren rund 58% der Kontrollvideos
              unpolitisch (gemessener Politikanteil: 42.1%).
              Weil das gescreente Set ein PRAEFIX einer Zufallsreihenfolge
              ist, entsteht durch die Beschraenkung KEINE Verzerrung.

  Estimand damit: Kriegsvideos vs. andere POLITISCHE Videos desselben
  Kanals im selben Fenster. Konservativer als der Vergleich gegen alle
  Videos und inhaltlich aussagekraeftiger.

ERWEITERBARKEIT
Alle Ziehungen sind Rangfolgen ueber einen stabilen blake2b-Hash; gezogen
wird "Rang < n". Erhoehst du eine Zahl, bleibt die bisherige Auswahl
vollstaendig enthalten, es kommen nur Faelle dazu. Bereits geladene
Transkripte bleiben gueltig. Bedingung: PILOT_SEED nie aendern.

Stufen:
  coverage  Prueft die Screening-Abdeckung, bestimmt geeignete Kanaele
  draw      Zieht Kanaele und Videos
  report    Fasst die Ziehung zusammen
  gold      Kodierbogen-Vorlage fuer den Goldstandard
  all       coverage -> draw -> report

Benoetigt: pandas, numpy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# KONFIGURATION
# ---------------------------------------------------------------------------

INDIR = r"C:\Users\bened\PycharmProjects\youtube_data\outputs\sample_feasibility"
OUTDIR = r"C:\Users\bened\PycharmProjects\youtube_data\outputs\pilot"
COMMAND = "coverage"  # ["coverage", "draw", "report", "all", "gold"]

VIDEOS_FILE = "videos_rich.csv"
TRAJ_FILE = "A2_channel_trajectories_all_etabliert.csv"
COHORT_FILE = "B0_cohorts_all_etabliert.csv"
# Schlanker Export aus dem Screening-State: video_id, politics_final
# (nur gescreente Zeilen). Erzeugung siehe README-Block am Dateiende.
LABELS_FILE = "screening_labels.csv"

PILOT_SEED = 20260820          # NIE aendern

# --- Analysefenster --------------------------------------------------------
# Intervallindex = (period + 12) // 3
# Das Schockfenster ist zusammengefasst: Intervall 4 allein hat im Median
# nur 2 gescreente politische Videos je Kanal — zu duenn fuer 2 Kontrollen.
# Ursache: 2022 waren die Kanaele weniger produktiv, und die Kriegsvideos
# sind aus dem Screening-Pool entfernt, was den Rest ausduennt.
MAIN_WINDOWS = {
    "shock_0_5":  [4, 5],      # Monat 0-5
    "y1_12_14":   [8],         # Monat 12-14
    "y2_24_26":   [12],        # Monat 24-26
    "y3_36_38":   [16],        # Monat 36-38
}

BASELINE_PERIODS = (-12, -2)   # Monat -1 = Aufmarsch, bleibt draussen
BASELINE_VIDEOS = 12
BASELINE_RESERVE = 6
BASELINE_MIN_REQUIRED = 8      # Kanal-Eignung: politische Videos im Vorfenster

MAIN_TREAT_PER_CELL = 2
MAIN_CONTROL_PER_CELL = 2
MAIN_RESERVE_PER_CELL = 3

# Kanal-Eignung: Mindestzahl verfuegbarer Videos je Fenster
ELIG_MIN_TREAT = 1
ELIG_MIN_CONTROL = 3           # etwas ueber dem Bedarf, als Puffer
# Wie viele der Fenster muessen die Bedingung erfuellen? Standard: alle.
# Die Eignungstabelle in 'coverage' zeigt, was jede Lockerung bringt.
# Weniger als alle Fenster heisst: unbalanciertes Panel, die betroffenen
# Kanaele fehlen in einzelnen Fenstern. Fuer Fixed-Effects-Modelle
# unproblematisch, fuer deskriptive Zeitvergleiche nicht.
ELIG_MIN_WINDOWS = len(MAIN_WINDOWS)

CHANNELS_PER_STRATUM = {
    "dauerhaft": 12,
    "Spitze, dann Abfall": 12,
    "schwach": 12,
    "kaum Reaktion": 0,        # keine Treatment-Videos -> kein Kontrast
    "nicht beobachtet": 0,
}

MIN_DURATION_S = 180
EXCLUDE_LIVE = True

GOLD_N_PER_STRATUM = 100


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def stable_key(value: str, salt: str = "") -> int:
    """Reproduzierbarer Schluessel ohne globalen RNG-Zustand.
    Gleiche Logik wie stable_random_key in der Screening-Pipeline."""
    raw = f"{PILOT_SEED}|{salt}|{value}".encode("utf-8")
    return int.from_bytes(hashlib.blake2b(raw, digest_size=8).digest(),
                          byteorder="big", signed=False)


def rank_by_hash(df, id_col, group_cols, salt):
    keys = df[id_col].astype(str).map(lambda v: stable_key(v, salt))
    return keys.groupby([df[c] for c in group_cols]).rank(method="first") - 1


def window_of(interval_index):
    for name, ivs in MAIN_WINDOWS.items():
        if interval_index in ivs:
            return name
    return None


def load_videos(indir: Path) -> pd.DataFrame:
    v = pd.read_csv(indir / VIDEOS_FILE)
    v["treat"] = (v.ukr_core_title | v.ukr_wide_title
                  | v.ukr_core_desc | v.ukr_wide_desc).astype(int)
    for t in ("corona", "migration", "energie"):
        v[f"plac_{t}"] = (v[f"{t}_title"] | v[f"{t}_desc"]).astype(int)

    n0 = len(v)
    v = v[v.duration_s >= MIN_DURATION_S]
    if EXCLUDE_LIVE:
        v = v[v.is_live == 0]
    print(f"Videos: {n0:,} -> {len(v):,} nach Dauer >= {MIN_DURATION_S}s"
          + (" / ohne Livestreams" if EXCLUDE_LIVE else ""))

    lab_path = indir / LABELS_FILE
    if not lab_path.exists():
        raise FileNotFoundError(
            f"{LABELS_FILE} fehlt in {indir}.\n"
            "Schlanken Export aus dem Screening-State erzeugen:\n"
            "  s = pd.read_csv(STATE, usecols=['video_id','politics_final'])\n"
            "  s[s.politics_final.notna()].to_csv(OUT/'screening_labels.csv',\n"
            "                                     index=False)")
    lab = pd.read_csv(lab_path)
    v = v.merge(lab[["video_id", "politics_final"]], on="video_id", how="left")
    v["screened"] = v.politics_final.notna()
    v["is_political"] = (v.politics_final == 1)
    print(f"Screening-Labels: {v.screened.sum():,} von {len(v):,} Videos "
          f"({v.screened.mean():.1%})")
    v["window"] = v.interval_index.map(window_of)
    return v


# ---------------------------------------------------------------------------
# Stufe: coverage
# ---------------------------------------------------------------------------

def empirical_bayes_rates(v: pd.DataFrame) -> pd.DataFrame:
    """Kanal-Politikanteil mit Shrinkage.

    Ein Anteil aus 15 gescreenten Videos ist verrauscht. Der Beta-Prior
    wird per Momentenmethode aus der Verteilung der Kanalraten geschaetzt;
    kleine Kanaele werden dadurch zum Gesamtmittel gezogen.
    """
    s = v[v.screened].groupby("channel_id").agg(
        k=("is_political", "sum"), n=("is_political", "size"))
    s = s[s.n >= 5]
    p = s.k / s.n
    mu, var = p.mean(), p.var(ddof=1)
    # Beta(a,b) per Momentenmethode; var muss kleiner sein als mu(1-mu)
    conc = max(mu * (1 - mu) / var - 1, 0.5) if var > 0 else 2.0
    a, b = mu * conc, (1 - mu) * conc
    out = v[v.screened].groupby("channel_id").agg(
        k=("is_political", "sum"), n=("is_political", "size"))
    out["rate_raw"] = out.k / out.n
    out["rate_eb"] = (out.k + a) / (out.n + a + b)
    print(f"  Beta-Prior: a={a:.2f}, b={b:.2f} "
          f"(Gesamtmittel {mu:.1%}, Konzentration {conc:.1f})")
    return out


def cmd_coverage(args):
    indir, outdir = Path(args.indir), Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    v = load_videos(indir)

    traj = pd.read_csv(indir / TRAJ_FILE)
    coh = pd.read_csv(indir / COHORT_FILE)
    if coh.columns[0] != "channel_id":
        coh = coh.rename(columns={coh.columns[0]: "channel_id"})
    ch = traj.merge(coh[["channel_id", "kohorte"]], on="channel_id", how="left")
    ch = ch[ch.kohorte == "etabliert"].copy()
    print(f"\nEtablierte Kanaele: {len(ch):,}")

    # --- Verfuegbarkeit je Kanal x Fenster --------------------------------
    m = v[v.window.notna()]
    av = m.groupby(["channel_id", "window"]).agg(
        n_treat=("treat", "sum"),
        n_ctrl=("is_political", lambda s: int(
            (s & (m.loc[s.index, "treat"] == 0)).sum())),
        n_screened=("screened", "sum"),
        n_total=("treat", "size"),
    ).reset_index()

    print("\n" + "=" * 70)
    print("SCREENING-ABDECKUNG JE FENSTER (nur etablierte Kanaele)")
    print("=" * 70)
    av_e = av[av.channel_id.isin(ch.channel_id)]
    print(f"{'Fenster':<14}{'Kanaele':>9}{'Median Treat':>14}"
          f"{'Median Kontr.':>15}{'>= Bedarf':>11}")
    for w in MAIN_WINDOWS:
        g = av_e[av_e.window == w]
        ok = ((g.n_treat >= ELIG_MIN_TREAT)
              & (g.n_ctrl >= ELIG_MIN_CONTROL)).mean() if len(g) else 0
        print(f"{w:<14}{len(g):>9,}{g.n_treat.median():>14.0f}"
              f"{g.n_ctrl.median():>15.0f}{ok:>11.1%}")

    # --- Baseline ---------------------------------------------------------
    lo, hi = BASELINE_PERIODS
    b = v[(v.period >= lo) & (v.period <= hi)]
    bavail = b.groupby("channel_id").agg(
        base_political=("is_political", "sum"),
        base_total=("is_political", "size")).reset_index()

    # --- Eignung ----------------------------------------------------------
    wide = av_e.pivot(index="channel_id", columns="window",
                      values=["n_treat", "n_ctrl"]).fillna(0)
    elig = pd.DataFrame(index=wide.index)
    for w in MAIN_WINDOWS:
        elig[w] = ((wide[("n_treat", w)] >= ELIG_MIN_TREAT)
                   & (wide[("n_ctrl", w)] >= ELIG_MIN_CONTROL))
    elig["windows_ok"] = elig[list(MAIN_WINDOWS)].sum(axis=1)
    elig = elig.reset_index().merge(bavail, on="channel_id", how="left")
    elig["base_ok"] = elig.base_political.fillna(0) >= BASELINE_MIN_REQUIRED
    elig["eligible"] = (elig.windows_ok >= ELIG_MIN_WINDOWS) & elig.base_ok
    elig = elig.merge(ch[["channel_id", "typ"]], on="channel_id", how="left")

    print("\n" + "=" * 70)
    print("KANAL-EIGNUNG")
    print("=" * 70)
    print(f"Bedingung: >= {ELIG_MIN_TREAT} Treatment und >= {ELIG_MIN_CONTROL} "
          f"politische Kontrollen in ALLEN {len(MAIN_WINDOWS)} Fenstern,")
    print(f"           >= {BASELINE_MIN_REQUIRED} politische Videos im Vorfenster\n")
    print(f"{'Stratum':<22}{'etabliert':>11}{'geeignet':>10}{'Ziel':>7}")
    for t, n in CHANNELS_PER_STRATUM.items():
        g = elig[elig.typ == t]
        e = int(g.eligible.sum())
        flag = "  <- ZU WENIG" if n and e < n else ""
        print(f"{t:<22}{len(g):>11,}{e:>10,}{n:>7}{flag}")

    # Was bringt jede Lockerung? Daran den Schwellenwert ablesen, statt
    # ihn zu raten.
    print("\nGeeignete Kanaele je Stratum bei unterschiedlichen Schwellen:")
    strata = [t for t, n in CHANNELS_PER_STRATUM.items() if n > 0]
    print(f"{'min. Fenster':<14}" + "".join(f"{t[:16]:>18}" for t in strata)
          + f"{'gesamt':>9}")
    for k in range(len(MAIN_WINDOWS), 0, -1):
        e = (elig.windows_ok >= k) & elig.base_ok
        cells = "".join(f"{int((e & (elig.typ == t)).sum()):>18}"
                        for t in strata)
        mark = "  <- aktuell" if k == ELIG_MIN_WINDOWS else ""
        print(f"{k:<14}{cells}{int(e.sum()):>9}{mark}")
    print(f"\nZiel je Stratum: "
          + ", ".join(f"{t}={CHANNELS_PER_STRATUM[t]}" for t in strata))
    print("Reicht die aktuelle Zeile nicht, ELIG_MIN_WINDOWS senken oder")
    print("ELIG_MIN_CONTROL/MAIN_CONTROL_PER_CELL reduzieren.")

    print("\nEmpirical-Bayes-Schaetzung der Kanal-Politikanteile:")
    eb = empirical_bayes_rates(v)
    elig = elig.merge(eb[["rate_raw", "rate_eb"]], on="channel_id", how="left")

    elig.to_csv(outdir / "channel_eligibility.csv", index=False)
    av.to_csv(outdir / "window_availability.csv", index=False)
    print(f"\n-> channel_eligibility.csv, window_availability.csv")


# ---------------------------------------------------------------------------
# Stufe: draw
# ---------------------------------------------------------------------------

KEEP = ["video_id", "channel_id", "channel_title", "published_at", "period",
        "interval_index", "window", "duration_s", "views", "likes", "comments",
        "treat", "politics_final", "plac_corona", "plac_migration",
        "plac_energie", "sample_type", "role", "cell", "weight", "_rank"]


def cmd_draw(args):
    indir, outdir = Path(args.indir), Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    v = load_videos(indir)

    elig = pd.read_csv(outdir / "channel_eligibility.csv")
    pool = elig[elig.eligible].copy()
    pool["_rank"] = rank_by_hash(pool, "channel_id", ["typ"], "channel")
    pool["n_target"] = pool.typ.map(CHANNELS_PER_STRATUM).fillna(0)
    sel = pool[pool._rank < pool.n_target].copy()
    chans = sel.channel_id.tolist()

    print(f"\n{'Stratum':<22}{'geeignet':>10}{'Ziel':>7}{'gezogen':>9}")
    for t, g in pool.groupby("typ"):
        n = int(g.n_target.iloc[0])
        d = int((g._rank < g.n_target).sum())
        print(f"{t:<22}{len(g):>10,}{n:>7}{d:>9}"
              + ("  <- erschoepft" if d < n else ""))
    if any((g._rank < g.n_target).sum() < g.n_target.iloc[0]
           for _, g in pool.groupby("typ") if g.n_target.iloc[0] > 0):
        print("\n! Mindestens ein Stratum ist erschoepft. Optionen:")
        print("  - ELIG_MIN_WINDOWS senken (Tabelle in 'coverage' ansehen)")
        print("  - ELIG_MIN_CONTROL bzw. MAIN_CONTROL_PER_CELL reduzieren")
        print("  - Screening fuer weitere Kanaele nachziehen")
        print("  - Zielzahl je Stratum senken (dann alle gleichmaessig)")
    print(f"\n{len(chans)} Kanaele gezogen.")

    # --- Baseline: nur politische Videos aus dem Vorfenster ---------------
    lo, hi = BASELINE_PERIODS
    b = v[(v.channel_id.isin(chans)) & (v.period >= lo) & (v.period <= hi)
          & v.is_political].copy()
    b["_rank"] = rank_by_hash(b, "video_id", ["channel_id"], "baseline")
    navail = b.groupby("channel_id").size().rename("n_avail")
    b = b[b._rank < BASELINE_VIDEOS + BASELINE_RESERVE].merge(
        navail, on="channel_id", how="left")
    b["sample_type"] = "baseline"
    b["role"] = np.where(b._rank < BASELINE_VIDEOS, "primary", "reserve")
    b["cell"] = b.channel_id + "|pre"
    b["weight"] = b.n_avail / np.minimum(b.n_avail, BASELINE_VIDEOS)

    # --- Main: Treatment ohne Screening, Kontrolle nur politisch ----------
    m = v[(v.channel_id.isin(chans)) & v.window.notna()].copy()
    m = m[(m.treat == 1) | m.is_political]
    navail_m = (m.groupby(["channel_id", "window", "treat"]).size()
                 .rename("n_avail").reset_index())
    m = m.merge(navail_m, on=["channel_id", "window", "treat"], how="left")
    m["_rank"] = rank_by_hash(m, "video_id",
                              ["channel_id", "window", "treat"], "main")
    m["n_primary"] = np.where(m.treat == 1, MAIN_TREAT_PER_CELL,
                              MAIN_CONTROL_PER_CELL)
    m = m[m._rank < m.n_primary + MAIN_RESERVE_PER_CELL].copy()
    m["sample_type"] = "main"
    m["role"] = np.where(m._rank < m.n_primary, "primary", "reserve")
    m["cell"] = m.channel_id + "|" + m.window
    m["weight"] = m.n_avail / np.minimum(m.n_avail, m.n_primary)

    out = pd.concat([b.reindex(columns=KEEP), m.reindex(columns=KEEP)],
                    ignore_index=True)
    out = out.drop_duplicates(subset=["video_id", "sample_type"])

    sel.to_csv(outdir / "pilot_channels.csv", index=False)
    out.to_csv(outdir / "pilot_videos.csv", index=False)

    # --- Download-Warteschlange ------------------------------------------
    # Wellenweise ueber ALLE Kanaele: nach jeder Welle ist der Datensatz ein
    # balanciertes Panel und du kannst jederzeit abbrechen.
    prim = out[out.role == "primary"].copy()
    prim["wave"] = prim.groupby(["sample_type", "cell", "treat"]).cumcount()
    prim = prim.sort_values(["wave", "sample_type", "channel_id", "window"])
    q = prim[["wave", "video_id", "channel_id", "channel_title", "window",
              "sample_type", "treat", "published_at", "duration_s"]]
    q.to_csv(outdir / "download_queue.csv", index=False)

    res = out[out.role == "reserve"].copy()
    res["wave"] = res.groupby(["sample_type", "cell", "treat"]).cumcount()
    res.sort_values(["wave", "channel_id"])[
        ["wave", "video_id", "channel_id", "window", "sample_type", "treat"]
    ].to_csv(outdir / "download_reserve.csv", index=False)

    # Reine ID-Liste in Downloadreihenfolge, fuer den Downloader
    (outdir / "video_ids.json").write_text(
        json.dumps(q.video_id.astype(str).tolist(), indent=2),
        encoding="utf-8")

    print(f"\nPrimaer {len(prim):,} Videos in {prim.wave.nunique()} Wellen, "
          f"Reserve {len(res):,}")

    (outdir / "pilot_manifest.json").write_text(json.dumps({
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "pilot_seed": PILOT_SEED,
        "channels_per_stratum": CHANNELS_PER_STRATUM,
        "channels_drawn": len(chans),
        "main_windows": MAIN_WINDOWS,
        "baseline": {"periods": list(BASELINE_PERIODS),
                     "videos": BASELINE_VIDEOS, "reserve": BASELINE_RESERVE,
                     "min_required": BASELINE_MIN_REQUIRED},
        "main": {"treat_per_cell": MAIN_TREAT_PER_CELL,
                 "control_per_cell": MAIN_CONTROL_PER_CELL,
                 "reserve_per_cell": MAIN_RESERVE_PER_CELL},
        "eligibility": {"min_treat": ELIG_MIN_TREAT,
                        "min_control": ELIG_MIN_CONTROL},
        "filters": {"min_duration_s": MIN_DURATION_S,
                    "exclude_live": EXCLUDE_LIVE},
        "control_definition": "politics_final == 1 (gescreentes Praefix)",
        "treatment_definition": "Kriegs-Keyword in Titel oder bereinigter Beschreibung",
        "n_primary": int(len(prim)), "n_reserve": int(len(res)),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {outdir}: pilot_videos.csv, download_queue.csv, "
          "download_reserve.csv, video_ids.json, pilot_manifest.json")


# ---------------------------------------------------------------------------
# Stufe: report
# ---------------------------------------------------------------------------

def cmd_report(args):
    outdir = Path(args.outdir)
    out = pd.read_csv(outdir / "pilot_videos.csv")
    sel = pd.read_csv(outdir / "pilot_channels.csv")
    prim = out[out.role == "primary"]

    print("=" * 70)
    print("UMFANG")
    print("=" * 70)
    print(f"Kanaele                : {out.channel_id.nunique()}")
    print(f"Videos primaer         : {len(prim):,}")
    print(f"Videos inkl. Reserve   : {len(out):,}")
    for s, g in prim.groupby("sample_type"):
        print(f"  {s:<20} {len(g):>6,}  ({int((g.treat == 1).sum()):,} Treatment / "
              f"{int((g.treat == 0).sum()):,} Kontrolle)")

    print("\n" + "=" * 70)
    print("KONTROLLGRUPPE — sind wirklich alle politisch?")
    print("=" * 70)
    ctrl = prim[prim.treat == 0]
    npol = int((ctrl.politics_final != 1).sum())
    print(f"Kontrollvideos                 : {len(ctrl):,}")
    print(f"davon NICHT politics_final==1  : {npol:,}"
          + ("   <- Fehler, pruefen!" if npol else "   (korrekt)"))
    print("\nOhne diesen Filter waeren rund 58% der Kontrollvideos unpolitisch")
    print("(gemessener Politikanteil ueber alle gescreenten Videos: 42.1%).")

    print("\n" + "=" * 70)
    print("BASELINE")
    print("=" * 70)
    b = prim[prim.sample_type == "baseline"].groupby("channel_id").size()
    b = b.reindex(sel.channel_id).fillna(0)
    print(f"Median Videos je Kanal : {b.median():.0f}")
    thin = b[b < BASELINE_MIN_REQUIRED]
    print(f"Kanaele unter {BASELINE_MIN_REQUIRED}       : {len(thin)}")
    if len(thin):
        print("  ! Verrauschte Moderatoren daempfen Interaktionseffekte.")

    print("\n" + "=" * 70)
    print("HAUPTSTICHPROBE — Zellendeckung")
    print("=" * 70)
    m = prim[prim.sample_type == "main"]
    cells = m.groupby(["channel_id", "window"]).agg(
        n_treat=("treat", "sum"), n=("treat", "size")).reset_index()
    cells["n_ctrl"] = cells.n - cells.n_treat
    exp = sel.channel_id.nunique() * len(MAIN_WINDOWS)
    both = (cells.n_treat > 0) & (cells.n_ctrl > 0)
    full = (cells.n_treat >= MAIN_TREAT_PER_CELL) & \
           (cells.n_ctrl >= MAIN_CONTROL_PER_CELL)
    print(f"Erwartete Zellen       : {exp:,}")
    print(f"Zellen mit Material    : {len(cells):,}")
    print(f"Zellen vollstaendig    : {int(full.sum()):,} ({full.mean():.0%})")
    print(f"Zellen mit BEIDEN Typen: {int(both.sum()):,} ({both.mean():.0%})"
          "   <- diese identifizieren den Effekt")
    print(f"\n{'Fenster':<14}{'Zellen':>8}{'beide':>8}{'Treat':>8}{'Kontr.':>8}")
    for w, g in cells.groupby("window"):
        print(f"{w:<14}{len(g):>8}"
              f"{int(((g.n_treat > 0) & (g.n_ctrl > 0)).sum()):>8}"
              f"{int(g.n_treat.sum()):>8}{int(g.n_ctrl.sum()):>8}")

    print("\n" + "=" * 70)
    print("DESIGNGEWICHTE")
    print("=" * 70)
    print("Treatment ist bewusst ueberzogen. OHNE Gewichte ueberschaetzt")
    print("jede deskriptive Auswertung den Kriegsanteil erheblich.")
    print("Fuer Within-Video-Modelle mit Fixed Effects unkritisch.\n")
    for t, g in m.groupby("treat"):
        lab = "Treatment" if t else "Kontrolle"
        print(f"  {lab:<12} Median {g.weight.median():>6.1f}, "
              f"Max {g.weight.max():>7.1f}")

    print("\n" + "=" * 70)
    print("NAECHSTE SCHRITTE")
    print("=" * 70)
    print("1. video_ids.json in den Transkript-Downloader, Reihenfolge")
    print("   beibehalten (wellenweise = jederzeit balanciert abbrechbar).")
    print("2. Verfuegbarkeitsrate GETRENNT nach treat protokollieren.")
    print("   Differenzielle Ausfaelle waeren Selektion auf dem Treatment.")
    print("3. Fehlschlaege aus download_reserve.csv nachziehen (gleiche Zelle).")
    print("4. Erweiterung: Konstanten erhoehen, 'draw' erneut. Die bisherige")
    print("   Auswahl bleibt erhalten. PILOT_SEED unveraendert lassen.")


# ---------------------------------------------------------------------------
# Stufe: gold
# ---------------------------------------------------------------------------

def cmd_gold(args):
    outdir = Path(args.outdir)
    out = pd.read_csv(outdir / "pilot_videos.csv")
    prim = out[(out.role == "primary") & (out.sample_type == "main")].copy()
    prim["_g"] = rank_by_hash(prim, "video_id", ["treat"], "gold")
    gold = prim[prim._g < GOLD_N_PER_STRATUM].copy()

    dims = ["volkszentrismus", "antielitismus", "moralisierung",
            "emotion", "ukraine_bezug"]
    sheet = gold[["video_id", "channel_id", "window", "treat"]].copy()
    sheet["segment_id"] = ""
    sheet["segment_text"] = ""
    for c in dims:
        sheet[f"coder_1_{c}"] = ""
        sheet[f"coder_1_retest_{c}"] = ""
        sheet[f"coder_2_{c}"] = ""
        sheet[f"llm_{c}"] = ""
    sheet["notiz"] = ""
    p = outdir / "gold_standard_template.csv"
    sheet.to_csv(p, index=False)
    print(f"{len(sheet):,} Videos ({int((sheet.treat == 1).sum())} Treatment / "
          f"{int((sheet.treat == 0).sum())} Kontrolle) -> {p}")
    print("\nStratifiziert nach Videotyp. Wenn die Mensch-LLM-Uebereinstimmung")
    print("bei Kriegsvideos schlechter ist als bei Kontrollvideos, ist der")
    print("Haupteffekt teilweise Messfehler.")
    print("\ncoder_1        selbst kodieren")
    print("coder_1_retest nach 2 Wochen erneut, ohne Blick auf Runde 1")
    print("coder_2        leer lassen, bis ein Zweitkodierer verfuegbar ist")


# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", nargs="?", default=COMMAND,
                   choices=["coverage", "draw", "report", "gold", "all"])
    p.add_argument("--indir", default=INDIR)
    p.add_argument("--outdir", default=OUTDIR)
    a = p.parse_args()

    print(f"Quelle : {a.indir}\nZiel   : {a.outdir}\nSeed   : {PILOT_SEED}")
    steps = {"coverage": cmd_coverage, "draw": cmd_draw,
             "report": cmd_report, "gold": cmd_gold}
    order = ["coverage", "draw", "report"] if a.cmd == "all" else [a.cmd]
    for s in order:
        print(f"\n{'#' * 70}\n# {s.upper()}\n{'#' * 70}")
        steps[s](a)


if __name__ == "__main__":
    main()
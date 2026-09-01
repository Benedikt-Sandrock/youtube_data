"""
run_pilot.py
============

Ein Durchlauf, ein Ergebnis: von der Videotabelle zur Downloadliste.

    python run_pilot.py

Vorher nur den CONFIG-Block anpassen. Ausgabe:

    out/pilot_kanaele.csv   gezogene Kanaele + geordnete Reserve
    out/pilot_videos.csv    Downloadliste (Rolle, Fenster, primary/reserve)
    out/pilot_zellen.csv    Diagnose je Kanal x Fenster
    out/engpass.csv         nur falls ein Stratum unterbesetzt ist

Ist ein Stratum unterbesetzt, sagt das Skript das am Ende und schreibt die
Kanaele heraus, fuer die sich gezieltes Nachscreening lohnt.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from youtube_code.config import EXTERNAL, OUTPUTS

# ==========================================================================
# CONFIG -- nur hier etwas aendern
# ==========================================================================

VIDEOS   = OUTPUTS / "sample_feasibility" / "videos_compact_pol_labels.csv"                        # .csv oder .parquet
TYPOLOGY = EXTERNAL / "media_type_russia_merged.xlsx"
OUTDIR   = "out"

COLS = {
    "channel_id":   "channel_id",
    "video_id":     "video_id",
    "published_at": "published_at",
    "is_war":       "is_war_core",      # TREATMENT: enge Definition (Praezision)
    "war_adj":      "is_war_wide",      # aus dem KONTROLLPOOL raus (Sensitivitaet)
    "politics":     "politics_final",   # 1/0/NaN
    "screened":     "screened",         # bool; None -> aus politics abgeleitet
}

PILOT_SEED = "pilot-2026-typ-v1"        # NIE aendern (Nestbarkeit der Ziehung)

STRATUM_N = {"OERR": 10, "TRAD": 10, "ALT": 20, "PARTEI": 6}
DROP_FOREIGN = True

# Fenster: None = automatisch nach Kriegssalienz. Sonst z.B. [(0,2),(9,11),(21,23)]
POST_WINDOWS = [(0, 2), (12, 14), (21, 23), (36, 38)]
SCAN = False           # True: nur den Fenster-Scan rechnen, keine Ziehung
N_POST_WINDOWS = 3

# Pre-Periode
PRE_WINDOW        = (-12, -3)      # -2/-1 raus: Eskalationsphase ab Dez 2021
PRE_DRAW          = 12             # Baseline-Videos je Kanal
PRE_MIN_POLITICAL = 16             # Eignungsschwelle (Puffer ueber PRE_DRAW)
PRE_MIN_QUARTERS  = 3              # in >=3 von 4 Vorkriegsquartalen >=1 politisch

# Post-Periode
POST_MIN_PER_SIDE = 2              # darunter faellt die Zelle raus
POST_TREAT_MAX    = 4
SHOCK_TREAT_MAX   = 6
CHANNEL_MIN_POST  = 2              # Schock MUSS bestehen + >=1 weiteres Fenster

TRANSCRIPT_LOSS = 0.35             # Reserve-Aufschlag

INVASION = pd.Timestamp("2022-02-24", tz="UTC")
TYPE_LABELS = {1: "OERR", 2: "TRAD", 3: "ALT", 4: "PARTEI",
               5: "OERR_TEILW", 6: "SONSTIGES"}

# ==========================================================================


def hkey(s: str) -> str:
    """Stabiler Sortierschluessel. Ziehung ist damit nestbar: erhoehst du eine
    Zahl, bleibt die bisherige Auswahl vollstaendig enthalten."""
    return hashlib.blake2b(f"{PILOT_SEED}|{s}".encode(), digest_size=8).hexdigest()


# --- 1. Laden -------------------------------------------------------------

def load_videos() -> pd.DataFrame:
    p = Path(VIDEOS)
    df = pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)
    # Zielnamen, die in der CSV schon belegt sind (z.B. eine frueher manuell
    # angelegte Spalte is_war), wuerden beim Umbenennen doppelte Spalten
    # erzeugen. Die Quellspalte aus COLS gewinnt.
    src = {k: v for k, v in COLS.items() if v in df.columns}
    clash = [k for k, v in src.items() if k != v and k in df.columns]
    if clash:
        print(f"[laden] vorhandene Spalten ueberschrieben: {clash}")
        df = df.drop(columns=clash)
    df = df.rename(columns={v: k for k, v in src.items()})
    if df.columns.duplicated().any():
        dup = df.columns[df.columns.duplicated()].tolist()
        print(f"[laden] WARNUNG doppelte Spalten entfernt: {dup}")
        df = df.loc[:, ~df.columns.duplicated()]
    fehlt = [k for k in ("channel_id", "video_id", "published_at",
                         "is_war", "politics") if k not in df.columns]
    if fehlt:
        raise KeyError(f"Spalten fehlen nach dem Mapping: {fehlt}. "
                       f"COLS pruefen. Vorhanden: {list(df.columns)}")
    ts = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    df = df[ts.notna()].copy()
    if "time_delta" in df.columns:
        df["month_rel"] = df["time_delta"].astype(int)   # bereits vorhanden
    else:
        df["month_rel"] = ((ts.dt.year - INVASION.year) * 12
                           + (ts.dt.month - INVASION.month))
    df["is_war"] = df["is_war"].fillna(0).astype(bool)
    # Grenzfaelle (wide, aber nicht core) sind weder Treatment noch Kontrolle.
    # Gleiche Definition fuer beides wuerde C-B in beide Richtungen verwaessern.
    if "war_adj" in df.columns:
        df["war_adj"] = df["war_adj"].fillna(0).astype(bool) | df["is_war"]
    else:
        df["war_adj"] = df["is_war"]
    df["ctrl_pool"] = ~df["war_adj"]
    n_gr = int((df["war_adj"] & ~df["is_war"]).sum())
    print(f"[laden] Treatment {int(df['is_war'].sum()):,} | "
          f"Grenzfaelle ausgeschlossen {n_gr:,} | "
          f"Kontrollpool {int(df['ctrl_pool'].sum()):,}")
    df["politics"] = pd.to_numeric(df["politics"], errors="coerce")
    if "screened" not in df.columns:
        df["screened"] = df["politics"].notna()
    df["screened"] = df["screened"].fillna(False).astype(bool)
    print(f"[laden] {len(df):,} Videos, {df['channel_id'].nunique()} Kanaele")
    return df


def load_typology() -> pd.DataFrame:
    t = pd.read_excel(TYPOLOGY)
    t = t[[c for c in t.columns if not str(c).startswith("Unnamed")]]
    n0 = len(t)
    t = t.drop_duplicates(subset="channel_id").copy()
    t["label"] = t["type"].astype(int).map(TYPE_LABELS)
    t["foreign"] = t["foreign"].fillna(0).astype(int).astype(bool)
    t["excluded"] = t["exclude"].notna()
    t["pool"] = (t["label"].isin(STRATUM_N)
                 & ~t["excluded"]
                 & ~(t["foreign"] & DROP_FOREIGN))
    print(f"[typologie] {n0} Zeilen, {n0-len(t)} Duplikate entfernt, "
          f"Pilotpool {int(t['pool'].sum())} Kanaele")
    return t[["channel_id", "title", "label", "foreign", "excluded", "pool"]]


# --- 2. Fenster -----------------------------------------------------------

def pick_windows(df: pd.DataFrame) -> list[tuple[int, int]]:
    if POST_WINDOWS:
        print(f"[fenster] manuell gesetzt: {POST_WINDOWS}")
        return sorted(POST_WINDOWS)
    post = df[df["month_rel"] >= 0].copy()
    post["q"] = (post["month_rel"] // 3) * 3
    sal = (post.groupby(["channel_id", "q"])["is_war"].mean()
               .groupby("q").mean().sort_values(ascending=False))
    wins = [(0, 2)]
    rest = sal.drop(index=0, errors="ignore")
    if len(rest) and N_POST_WINDOWS >= 2:
        med = (rest - rest.median()).abs().idxmin()
        wins.append((int(med), int(med) + 2))
    if len(rest) > 1 and N_POST_WINDOWS >= 3:
        low = rest.drop(index=[w[0] for w in wins], errors="ignore").idxmin()
        wins.append((int(low), int(low) + 2))
    print("[fenster] Kriegsanteil je Quartal:")
    print(sal.round(3).to_string())
    print(f"[fenster] gewaehlt (Schock / Median / niedrig): {sorted(wins)}")
    return sorted(wins)


# --- 2b. Fenster-Scan: wie viele Kanaele bei welcher Mindestzahl? ---------

SCAN_MAX_OTHER = 6      # bis zu wie vielen Zusatzfenstern durchrechnen


def window_scan(df: pd.DataFrame, pre: pd.DataFrame, typ: pd.DataFrame):
    """Prueft ALLE Nachkriegsquartale statt der manuell gesetzten Fenster.

    Beantwortet: Wie viele Kanaele ueberleben, wenn die Regel lautet
    "Schockfenster + mindestens k weitere beliebige Quartale"? Und wie viele
    Fenster steuert ein ueberlebender Kanal im Schnitt bei?

    Achtung bei der Interpretation: Duerfen Kanaele beliebige Fenster
    beisteuern, ist das Panel zeitlich unbalanciert. Fuer den Kontrast
    innerhalb der Zelle egal, fuer Verlaufsaussagen nicht.
    """
    d = df[df["month_rel"] >= 0].copy()
    d["q"] = (d["month_rel"] // 3) * 3
    d["pol"] = (d["politics"] == 1) & d["ctrl_pool"]

    g = (d.groupby(["channel_id", "q"])
           .agg(n_war=("is_war", "sum"), n_pol=("pol", "sum")).reset_index())
    cap = np.where(g["q"] == 0, SHOCK_TREAT_MAX, POST_TREAT_MAX)
    g["n_draw"] = np.minimum(np.minimum(g["n_war"], cap), g["n_pol"]).astype(int)
    g["ok"] = g["n_draw"] >= POST_MIN_PER_SIDE

    ok = g[g["ok"]]
    per_ch = pd.DataFrame({"channel_id": g["channel_id"].unique()})
    per_ch["shock_ok"] = per_ch["channel_id"].isin(
        set(ok.loc[ok["q"] == 0, "channel_id"]))
    per_ch = per_ch.merge(
        ok[ok["q"] != 0].groupby("channel_id")
          .agg(n_other=("q", "size"), draw_other=("n_draw", "sum")).reset_index(),
        on="channel_id", how="left").fillna({"n_other": 0, "draw_other": 0})
    per_ch = per_ch.merge(
        ok[ok["q"] == 0].groupby("channel_id")["n_draw"].sum()
          .rename("draw_shock").reset_index(), on="channel_id", how="left")
    per_ch["draw_shock"] = per_ch["draw_shock"].fillna(0)
    per_ch = per_ch.merge(pre[["channel_id", "pre_ok"]],
                          on="channel_id", how="left")
    per_ch["pre_ok"] = per_ch["pre_ok"].fillna(False)

    # --- Kanaele je Quartal ------------------------------------------------
    print("\n[scan] Kanaele mit gueltiger Zelle je Quartal")
    qtab = (ok.groupby("q").agg(kanaele=("channel_id", "nunique"),
                                median_draw=("n_draw", "median")))
    print(qtab.to_string())

    # --- Sensitivitaet gegenueber k ---------------------------------------
    rows = []
    for k in range(1, SCAN_MAX_OTHER + 1):
        m = per_ch["shock_ok"] & (per_ch["n_other"] >= k) & per_ch["pre_ok"]
        sub = per_ch[m]
        if sub.empty:
            rows.append({"k_zusatzfenster": k, "kanaele": 0}); continue
        # Videos: Baseline + 2 x gezogene je gueltigem Fenster
        vids = PRE_DRAW + 2 * (sub["draw_shock"] + sub["draw_other"])
        rows.append({
            "k_zusatzfenster": k,
            "kanaele": len(sub),
            "fenster_im_schnitt": round((1 + sub["n_other"]).mean(), 1),
            "primaervideos_je_kanal": round(vids.mean(), 1),
        })
    sens = pd.DataFrame(rows)
    print("\n[scan] Regel: Schockfenster + k weitere beliebige Quartale")
    print(sens.to_string(index=False))

    # --- Aufschluesselung je Stratum --------------------------------------
    t = typ[typ["pool"]][["channel_id", "label"]]
    strat = per_ch.merge(t, on="channel_id")
    out = []
    for k in range(1, min(4, SCAN_MAX_OTHER) + 1):
        m = strat["shock_ok"] & (strat["n_other"] >= k) & strat["pre_ok"]
        c = strat[m].groupby("label").size().rename(f"k={k}")
        out.append(c)
    st = pd.concat(out, axis=1).fillna(0).astype(int)
    st["ziel"] = [STRATUM_N.get(i, 0) for i in st.index]
    print("\n[scan] geeignete Kanaele je Stratum")
    print(st.to_string())
    return per_ch, sens, st



def potential_scan(df: pd.DataFrame, pre: pd.DataFrame, typ: pd.DataFrame):
    """Trennt drei Engpaesse, die window_scan() vermischt:

      Treatment  -- hat der Kanal genug Kriegsvideos?  (fix, nicht aenderbar)
      Kontrolle  -- sind genug politische Videos gescreent?  (durch Screening
                    aenderbar -> das ist die Frage "was waere noch moeglich")
      Schock/Pre -- Kohortenbedingungen (Designentscheidung)

    Die Zeile "nur Treatment" ist die Obergrenze: so viele Kanaele koennten es
    maximal werden, wenn die Kontrollseite unbegrenzt waere.
    """
    d = df[df["month_rel"] >= 0].copy()
    d["q"] = (d["month_rel"] // 3) * 3
    d["pol"] = (d["politics"] == 1) & d["ctrl_pool"]
    d["scr"] = d["screened"] & d["ctrl_pool"]

    g = (d.groupby(["channel_id", "q"])
           .agg(n_war=("is_war", "sum"), n_pol=("pol", "sum"),
                n_scr=("scr", "sum"), n_ctrl=("ctrl_pool", "sum"))
           .reset_index())
    cap = np.where(g["q"] == 0, SHOCK_TREAT_MAX, POST_TREAT_MAX)
    g["treat_ok"] = np.minimum(g["n_war"], cap) >= POST_MIN_PER_SIDE
    g["both_ok"] = (np.minimum(np.minimum(g["n_war"], cap), g["n_pol"])
                    >= POST_MIN_PER_SIDE)
    g["nur_kontrolle_fehlt"] = g["treat_ok"] & ~g["both_ok"]

    pre_ok = set(pre.loc[pre["pre_ok"], "channel_id"])

    def count(flag: str, need_shock: bool, need_pre: bool, k: int,
              wins=None) -> int:
        h = g if wins is None else g[g["q"].isin([w[0] for w in wins])]
        ok = h[h[flag]]
        ch = set(ok["channel_id"])
        if need_shock:
            ch &= set(ok.loc[ok["q"] == 0, "channel_id"])
            n = ok[ok["q"] != 0].groupby("channel_id").size()
        else:
            n = ok.groupby("channel_id").size()
        ch &= set(n[n >= k].index)
        if need_pre:
            ch &= pre_ok
        return len(ch)

    for titel, wins, k in [("beliebige Quartale", None, 1),
                           ("feste Fenster " + str(POST_WINDOWS),
                            POST_WINDOWS, 1)]:
        rows = [
            ("aktuell: Schock + 1 weiteres + Pre",
             count("both_ok", True, True, k, wins)),
            ("ohne Schockpflicht: 2 beliebige + Pre",
             count("both_ok", False, True, 2, wins)),
            ("NUR Treatment: Schock + 1 weiteres + Pre",
             count("treat_ok", True, True, k, wins)),
            ("NUR Treatment: 2 beliebige + Pre",
             count("treat_ok", False, True, 2, wins)),
            ("NUR Treatment: 2 beliebige, ohne Pre (Obergrenze)",
             count("treat_ok", False, False, 2, wins)),
        ]
        print(f"\n[potenzial] {titel}")
        print(pd.DataFrame(rows, columns=["regel", "kanaele"])
                .to_string(index=False))

    # --- was gezieltes Nachscreening konkret braechte ----------------------
    rate = (g.groupby("channel_id")[["n_pol", "n_scr"]].sum()
              .assign(rate=lambda x: x["n_pol"] / x["n_scr"].replace(0, np.nan))
              ["rate"] * 0.85)
    gap = g[g["nur_kontrolle_fehlt"]].copy()
    if POST_WINDOWS:
        gap = gap[gap["q"].isin([w[0] for w in POST_WINDOWS])]
    gap["fehlend"] = POST_MIN_PER_SIDE - gap["n_pol"]
    gap["rate"] = gap["channel_id"].map(rate)
    gap["ungescreent"] = gap["n_ctrl"] - gap["n_scr"]
    gap["titel_noetig"] = np.ceil(gap["fehlend"] / gap["rate"])
    gap["machbar"] = gap["titel_noetig"] <= gap["ungescreent"]
    gap["budget"] = np.where(gap["machbar"], gap["titel_noetig"],
                             gap["ungescreent"])

    print(f"\n[nachscreening] {len(gap)} Zellen scheitern NUR an der "
          f"Kontrollseite ({gap['channel_id'].nunique()} Kanaele)")
    if len(gap):
        print(f"[nachscreening] davon machbar: {int(gap['machbar'].sum())} | "
              f"Titelbudget: {int(gap.loc[gap['machbar'],'budget'].sum()):,}")
        gap = gap.merge(typ[["channel_id", "title", "label"]],
                        on="channel_id", how="left")
        Path(OUTDIR).mkdir(exist_ok=True)
        gap.sort_values("budget").to_csv(f"{OUTDIR}/nachscreening.csv",
                                         index=False)
        print(f"[nachscreening] -> {OUTDIR}/nachscreening.csv")
    return g, gap


# --- 3. Zellen und Eignung ------------------------------------------------

def build_cells(df: pd.DataFrame, wins) -> pd.DataFrame:
    out = []
    for w in wins:
        s = df[df["month_rel"].between(*w)]
        g = (s.assign(pol=s["politics"].fillna(0) * s["ctrl_pool"])
               .groupby("channel_id")
               .agg(n_war=("is_war", "sum"), n_pol=("pol", "sum"),
                    n_pool=("video_id", "size"),
                    n_screened=("screened", "sum")).reset_index())
        g["fenster"] = f"{w[0]}..{w[1]}"
        g["is_shock"] = (w == (0, 2))
        out.append(g)
    c = pd.concat(out, ignore_index=True)
    cap = np.where(c["is_shock"], SHOCK_TREAT_MAX, POST_TREAT_MAX)
    c["n_draw"] = np.minimum(np.minimum(c["n_war"], cap), c["n_pol"]).astype(int)
    c["ok"] = c["n_draw"] >= POST_MIN_PER_SIDE
    # scheitert nur an der Kontrollseite? -> Nachscreening-Kandidat
    c["engpass_kontrolle"] = ~c["ok"] & (np.minimum(c["n_war"], cap)
                                         >= POST_MIN_PER_SIDE)
    return c


def build_pre(df: pd.DataFrame) -> pd.DataFrame:
    p = df[df["month_rel"].between(*PRE_WINDOW) & df["ctrl_pool"]].copy()
    p["pol"] = p["politics"].fillna(0)
    p["pq"] = ((p["month_rel"] - PRE_WINDOW[0]) // 3).clip(0, 3)
    a = p.groupby("channel_id")["pol"].sum().rename("n_pol_pre")
    b = (p[p["pol"] > 0].groupby("channel_id")["pq"].nunique()
           .rename("pre_quartale"))
    pre = pd.concat([a, b], axis=1).fillna(0).reset_index()
    pre["pre_ok"] = ((pre["n_pol_pre"] >= PRE_MIN_POLITICAL)
                     & (pre["pre_quartale"] >= PRE_MIN_QUARTERS))
    return pre


def eligibility(cells, pre) -> pd.DataFrame:
    ok = cells[cells["ok"]]
    ch = cells[["channel_id"]].drop_duplicates()
    ch["shock_ok"] = ch["channel_id"].isin(
        set(ok.loc[ok["is_shock"], "channel_id"]))
    ch = ch.merge(ok.groupby("channel_id").size().rename("n_fenster_ok"),
                  on="channel_id", how="left").fillna({"n_fenster_ok": 0})
    ch = ch.merge(pre, on="channel_id", how="left")
    ch["pre_ok"] = ch["pre_ok"].fillna(False)
    ch["eligible"] = (ch["shock_ok"] & (ch["n_fenster_ok"] >= CHANNEL_MIN_POST)
                      & ch["pre_ok"])
    print(f"\n[eignung] Schockfenster ok: {int(ch['shock_ok'].sum())} | "
          f">={CHANNEL_MIN_POST} Fenster: {int((ch['n_fenster_ok']>=CHANNEL_MIN_POST).sum())} | "
          f"Pre ok: {int(ch['pre_ok'].sum())} | GEEIGNET: {int(ch['eligible'].sum())}")
    return ch


# --- 4. Ziehung -----------------------------------------------------------

def draw_channels(typ, elig_ids) -> pd.DataFrame:
    t = typ[typ["pool"] & typ["channel_id"].isin(set(elig_ids))].copy()
    t["hash"] = t["channel_id"].map(hkey)
    t = t.sort_values(["label", "hash"])
    t["rang"] = t.groupby("label").cumcount()
    t["gezogen"] = t.apply(lambda r: r["rang"] < STRATUM_N.get(r["label"], 0),
                           axis=1)
    cov = (t.groupby("label")
             .agg(geeignet=("channel_id", "size"),
                  gezogen=("gezogen", "sum")).reset_index())
    cov["ziel"] = cov["label"].map(STRATUM_N)
    cov["fehlt"] = (cov["ziel"] - cov["gezogen"]).clip(lower=0)
    print("\n[ziehung] Kanaele je Stratum")
    print(cov.to_string(index=False))
    return t.sort_values(["label", "rang"]).reset_index(drop=True), cov


def _take(pool: pd.DataFrame, n: int, **tags) -> pd.DataFrame:
    """n primaere + Reserve, in stabiler Hash-Reihenfolge."""
    if n <= 0 or pool.empty:
        return pd.DataFrame()
    p = pool.copy()
    p["hash"] = p["video_id"].map(hkey)
    p = p.sort_values("hash").reset_index(drop=True)
    total = min(len(p), int(np.ceil(n / (1 - TRANSCRIPT_LOSS))))
    p = p.head(total)
    p["primary"] = np.arange(len(p)) < n
    for k, v in tags.items():
        p[k] = v
    return p[["channel_id", "video_id", "published_at", "month_rel",
              "primary"] + list(tags)]


def draw_videos(df, cells, chans, wins) -> pd.DataFrame:
    sel = set(chans.loc[chans["gezogen"], "channel_id"])
    parts = []

    pre = df[df["channel_id"].isin(sel) & df["month_rel"].between(*PRE_WINDOW)
             & df["ctrl_pool"] & (df["politics"] == 1)]
    for cid, g in pre.groupby("channel_id"):
        parts.append(_take(g, PRE_DRAW, rolle="baseline", fenster="pre"))

    good = cells[cells["ok"] & cells["channel_id"].isin(sel)]
    for _, r in good.iterrows():
        w = tuple(int(x) for x in r["fenster"].split(".."))
        s = df[(df["channel_id"] == r["channel_id"])
               & df["month_rel"].between(*w)]
        n = int(r["n_draw"])
        parts.append(_take(s[s["is_war"]], n,
                           rolle="treatment", fenster=r["fenster"]))
        parts.append(_take(s[s["ctrl_pool"] & (s["politics"] == 1)], n,
                           rolle="kontrolle", fenster=r["fenster"]))

    v = pd.concat([p for p in parts if len(p)], ignore_index=True)
    v = v.drop_duplicates(subset="video_id")
    print(f"\n[videos] {int(v['primary'].sum()):,} primaer, "
          f"{int((~v['primary']).sum()):,} Reserve, {len(v):,} gesamt")
    print(v[v["primary"]].groupby(["rolle"]).size().to_string())
    return v


# --- main -----------------------------------------------------------------

def main():
    Path(OUTDIR).mkdir(exist_ok=True)
    df = load_videos()
    typ = load_typology()
    df = df[df["channel_id"].isin(set(typ.loc[typ["pool"], "channel_id"]))]

    pre = build_pre(df)
    if SCAN:
        window_scan(df, pre, typ)
        potential_scan(df, pre, typ)
        return
    wins = pick_windows(df)
    cells = build_cells(df, wins)
    ch = eligibility(cells, pre)

    chans, cov = draw_channels(typ, ch.loc[ch["eligible"], "channel_id"])
    vids = draw_videos(df, cells, chans, wins)

    cells.to_csv(f"{OUTDIR}/pilot_zellen.csv", index=False)
    chans.to_csv(f"{OUTDIR}/pilot_kanaele.csv", index=False)
    vids.to_csv(f"{OUTDIR}/pilot_videos.csv", index=False)

    print(f"\n=== OUTPUTS ===\n"
          f"{OUTDIR}/pilot_zellen.csv\n"
          f"{OUTDIR}/pilot_kanaele.csv\n"
          f"{OUTDIR}/pilot_videos.csv")

    fehl = cov[cov["fehlt"] > 0]
    if len(fehl):
        print("\n[engpass] Ziel nicht erreicht in: "
              + ", ".join(f"{r.label} (-{int(r.fehlt)})"
                          for r in fehl.itertuples()))
        near = (cells[cells["engpass_kontrolle"]]
                .merge(typ[["channel_id", "title", "label"]], on="channel_id")
                .query("label in @fehl.label.tolist()"))
        near.to_csv(f"{OUTDIR}/engpass.csv", index=False)
        print(f"[engpass] {len(near)} Zellen scheitern nur an der "
              f"Kontrollseite -> engpass.csv (Nachscreening-Kandidaten)")
    else:
        print("\n[fertig] Alle Strata voll besetzt. Download kann starten.")


if __name__ == "__main__":
    main()
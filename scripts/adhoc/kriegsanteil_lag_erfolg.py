"""Kriegsanteil im Vormonat und Kanalerfolg im Folgemonat (Kanal-Monats-Panel).

Frage: Werden Kanäle, die im Monat t-1 einen höheren Anteil Russland/Ukraine-Videos
haben, im Monat t erfolgreicher? (Bezug zu Forschungsfrage 2 und 4.)

Daten: outputs/stata_rohdaten/videos_roh.dta + kanaele_roh.dta (zentraler Analysedatensatz).
Nur Long-Videos (`format == "long"`, ersetzt die 181-s-Regel), Zeitraum = Format-Fenster
[01.01.2021, 01.07.2026). Gelöschte Kanäle ohne Format (WDR aktuell, ZyproX) und OE24.TV
(Format fast überall gesetzt, aber format_klass = 0) bleiben drin, soweit `format` gesetzt.

Kriegsanteil (Titel-Stichwörter, rel_*):
  Hauptspezifikation: n(rel_russia_ukraine_war_cw = 1) / n(irgendein rel_*_cw = 1),
  d. h. Anteil Kriegsvideos an allen thematisch erkannten Videos (inkl. Krieg).
  Robustheit: Zähler/Nenner mit core-Listen; Nenner = alle Long-Videos.
  Zellen mit < MIN_NENNER Videos im Nenner -> Anteil fehlt.

Erfolg: Median log(1 + views) der Long-Videos im Monat t (rohe kumulierte Views, keine
Alters-Normierung; Videoalter/Abrufzeitpunkt über Monats-FE). Kernoutcome: dasselbe nur
für Nicht-Kriegsvideos (rel_russia_ukraine_war_cw = 0), damit die Kriegsprämie einzelner
Videos das Ergebnis nicht mechanisch erzeugt. Zellen mit < MIN_VIDEOS_OUTCOME -> fehlt.

Modelle (WLS, Gewicht sqrt(n Outcome-Videos), Kanal- und Monats-FE, Cluster Kanal):
  M1  y_alle ~ Anteil(t-1)
  M2  y_alle ~ Anteil(t-1) + Anteil(t)
  M3  y_nk   ~ Anteil(t-1)                     (Kerntest)
  M3b y_nk   ~ Anteil(t-1) + Anteil(t)
  M4  y_nk   ~ Anteil(t-1) + y_nk(t-1)
  M5  y_nk   ~ Anteil(t-1) + Anteil(t-2) + Anteil(t-3)
  M6  y_nk   ~ Anteil(t-1) + Anteil(t+1)       (Placebo-Lead)
Alle mit Upload-Dichte als Kontrolle. Robustheits-Durchläufe (je komplett M1-M6):
Upload-Dichte als Fenster-Variante (Zellmittel von berechne_upload_dichte, +/-48 h),
core, Nenner alle Long, ohne format_derived (WELT), nur Nachkriegsmonate (t >= 03/2022),
nur sample_kern. Heterogenität (M3): Anteil(t-1) x Medientyp bzw. x Ideologie.

Aufruf: python scripts/adhoc/kriegsanteil_lag_erfolg.py
Output: outputs/kriegsanteil_lag/regression_results/kriegsanteil_lag_erfolg.md
        outputs/kriegsanteil_lag/kanal_monat_panel.csv (Panel der Hauptspezifikation)
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from youtube_code.step6_auswertung.bericht_utils import berechne_upload_dichte  # noqa: E402

ROH = ROOT / "outputs/stata_rohdaten"
OUT = ROOT / "outputs/kriegsanteil_lag"
RES = OUT / "regression_results"
START, ENDE = pd.Timestamp("2021-01-01"), pd.Timestamp("2026-07-01")
KRIEGSBEGINN = pd.Period("2022-02", "M")
MIN_NENNER = 3
MIN_VIDEOS_OUTCOME = 3
KRIEG = "rel_russia_ukraine_war"
MEDIENTYP = {1: "ÖRR", 2: "traditionell", 3: "Partei/Politiker", 4: "Creator/alternativ"}


def lade_daten():
    with pd.io.stata.StataReader(ROH / "videos_roh.dta") as r:
        rel = [c for c in r.variable_labels() if c.startswith("rel_")]
    v = pd.read_stata(ROH / "videos_roh.dta",
                      columns=["video_id", "channel_id", "upload_ts", "format",
                               "format_derived", "views"] + rel,
                      convert_categoricals=False)
    v = v[(v.upload_ts >= START) & (v.upload_ts < ENDE)].copy()
    v["monat"] = v.upload_ts.dt.to_period("M")
    k = pd.read_stata(ROH / "kanaele_roh.dta",
                      columns=["channel_id", "kanal_name", "medientyp", "sample_kern",
                               "ideo_gesellschaft_baseline"],
                      convert_categoricals=False)
    return v, k, rel


def baue_panel(v, rel, stufe="cw", nenner="themen", ohne_derived=False):
    """Kanal-Monats-Panel (vollständiges Gitter je Kanal, damit Lags Kalendermonate sind)."""
    # Upload-Dichte auf der vollen Videomenge (alle Formate), wie in bericht_utils verlangt
    dichte_p = v.groupby(["channel_id", "monat"]).size().rename("dichte_periode")
    fenster = berechne_upload_dichte(v.rename(columns={"upload_ts": "published_at"}),
                                     published_at_spalte="published_at")
    lv = v[v.format == "long"].merge(fenster[["video_id", "upload_dichte"]], on="video_id",
                                     how="left")
    if ohne_derived:
        lv = lv[lv.format_derived != 1]
    lv = lv[lv.views.notna()].copy()
    lv["lv"] = np.log1p(lv.views)
    krieg = lv[f"{KRIEG}_{stufe}"] == 1
    themen = lv[[c for c in rel if c.endswith(f"_{stufe}")]].eq(1).any(axis=1)
    lv["krieg"], lv["themen"] = krieg.astype(int), themen.astype(int)

    g = lv.groupby(["channel_id", "monat"])
    p = pd.DataFrame({
        "n_long": g.size(),
        "n_krieg": g.krieg.sum(),
        "n_themen": g.themen.sum(),
        "y_alle": g.lv.median(),
        "dichte_fenster": g.upload_dichte.mean(),
    })
    nk = lv[lv.krieg == 0].groupby(["channel_id", "monat"])
    p["y_nk"], p["n_nk"] = nk.lv.median(), nk.size()
    p = p.join(dichte_p, how="outer")

    # vollständiges Gitter: erster bis letzter Monat je Kanal
    teile = []
    for ch, d in p.groupby(level=0):
        m = d.index.get_level_values(1)
        idx = pd.MultiIndex.from_product(
            [[ch], pd.period_range(m.min(), m.max(), freq="M")], names=["channel_id", "monat"])
        teile.append(d.reindex(idx))
    p = pd.concat(teile)
    for c in ["n_long", "n_krieg", "n_themen", "n_nk", "dichte_periode"]:
        p[c] = p[c].fillna(0)

    den = p.n_themen if nenner == "themen" else p.n_long
    p["anteil"] = np.where(den >= MIN_NENNER, p.n_krieg / den.replace(0, np.nan), np.nan)
    p.loc[p.n_long < MIN_VIDEOS_OUTCOME, "y_alle"] = np.nan
    p.loc[p.n_nk < MIN_VIDEOS_OUTCOME, "y_nk"] = np.nan
    p["log_dichte_periode"] = np.log1p(p.dichte_periode)
    p["log_dichte_fenster"] = np.log1p(p.dichte_fenster)

    gc = p.groupby(level=0)
    for L in (1, 2, 3):
        p[f"anteil_l{L}"] = gc.anteil.shift(L)
    p["anteil_f1"] = gc.anteil.shift(-1)
    p["y_nk_l1"] = gc.y_nk.shift(1)
    p = p.reset_index()
    p["monat_str"] = p.monat.astype(str)
    p["w_alle"] = np.sqrt(p.n_long)
    p["w_nk"] = np.sqrt(p.n_nk)
    return p


MODELLE = {
    "M1": ("y_alle", "anteil_l1", "w_alle"),
    "M2": ("y_alle", "anteil_l1 + anteil", "w_alle"),
    "M3": ("y_nk", "anteil_l1", "w_nk"),
    "M3b": ("y_nk", "anteil_l1 + anteil", "w_nk"),
    "M4": ("y_nk", "anteil_l1 + y_nk_l1", "w_nk"),
    "M5": ("y_nk", "anteil_l1 + anteil_l2 + anteil_l3", "w_nk"),
    "M6": ("y_nk", "anteil_l1 + anteil_f1", "w_nk"),
}


def schaetze(p, y, rhs, w, dichte):
    f = f"{y} ~ {rhs} + {dichte} + C(channel_id) + C(monat_str)"
    vars_ = [y, w, dichte, "channel_id", "monat_str"] + \
        [t.strip() for t in rhs.replace("*", "+").replace(":", "+").split("+")
         if t.strip() and not t.strip().startswith("C(")]
    vars_ += [c for c in ("medientyp", "ideo_gruppe") if c in rhs]
    d = p.dropna(subset=list(dict.fromkeys(vars_)))
    # Kanäle mit nur einer Beobachtung tragen zur Within-Schätzung nichts bei
    d = d[d.groupby("channel_id").channel_id.transform("size") > 1]
    m = smf.wls(f, data=d, weights=d[w]).fit(cov_type="cluster",
                                             cov_kwds={"groups": d.channel_id.astype("category").cat.codes})
    return m, d


def zeile(m, d, terme):
    out = []
    for t in terme:
        if t in m.params:
            b, se, pv = m.params[t], m.bse[t], m.pvalues[t]
            stern = "***" if pv < .01 else "**" if pv < .05 else "*" if pv < .1 else ""
            out.append(f"{b:.3f}{stern} ({se:.3f})")
        else:
            out.append("")
    return out + [f"{len(d):,}".replace(",", "."), str(d.channel_id.nunique())]


TERME = ["anteil_l1", "anteil", "anteil_l2", "anteil_l3", "anteil_f1", "y_nk_l1"]


def lauf_tabelle(p, dichte):
    kopf = ["Modell", "Outcome"] + TERME + ["N Zellen", "N Kanäle"]
    zeilen, info = [], {}
    for name, (y, rhs, w) in MODELLE.items():
        m, d = schaetze(p, y, rhs, w, dichte)
        zeilen.append([name, y] + zeile(m, d, TERME))
        info[name] = (m, d)
    md = ["| " + " | ".join(kopf) + " |", "|" + "---|" * len(kopf)]
    md += ["| " + " | ".join(z) + " |" for z in zeilen]
    # Summe der Lags in M5
    m5 = info["M5"][0]
    t = m5.t_test("anteil_l1 + anteil_l2 + anteil_l3 = 0")
    md.append("")
    md.append(f"M5 Summe der Lags t-1..t-3: {float(t.effect[0]):.3f} "
              f"(SE {float(t.sd[0][0]):.3f}, p = {float(t.pvalue):.3f})")
    return "\n".join(md), info


def effekt_text(b):
    return f"{(np.exp(b * 0.10) - 1) * 100:+.1f} %"


def deskriptiv(p):
    d = p.dropna(subset=["anteil"])
    vor = d[d.monat < KRIEGSBEGINN]
    nach = d[d.monat >= KRIEGSBEGINN]
    within = d.groupby("channel_id").anteil.transform(lambda s: s - s.mean())
    zeilen = [
        f"- Zellen mit Kriegsanteil: {len(d):,} aus {d.channel_id.nunique()} Kanälen".replace(",", "."),
        f"- Mittlerer Kriegsanteil vor Kriegsbeginn: {vor.anteil.mean():.3f}, "
        f"ab 02/2022: {nach.anteil.mean():.3f} (Median {nach.anteil.median():.3f})",
        f"- SD Kriegsanteil gesamt: {d.anteil.std():.3f}, innerhalb der Kanäle: {within.std():.3f}",
        f"- Zellen mit Outcome alle/Nicht-Krieg: {p.y_alle.notna().sum():,} / "
        f"{p.y_nk.notna().sum():,}".replace(",", "."),
        f"- Autokorrelation Anteil(t) vs. Anteil(t-1): "
        f"{p[['anteil', 'anteil_l1']].dropna().corr().iloc[0, 1]:.3f}",
    ]
    jahr = (d.assign(jahr=d.monat.dt.year).groupby("jahr").anteil
            .agg(["mean", "median", "count"]).round(3))
    tab = ["| Jahr | Mittel | Median | Zellen |", "|---|---|---|---|"]
    tab += [f"| {j} | {r['mean']} | {r['median']} | {int(r['count'])} |" for j, r in jahr.iterrows()]
    return "\n".join(zeilen) + "\n\n" + "\n".join(tab)


def heterogenitaet(p, k, dichte):
    p = p.merge(k, on="channel_id", how="left")
    p["ideo_gruppe"] = pd.cut(p.ideo_gesellschaft_baseline, [-9, -0.5, 0.5, 9],
                              labels=["links", "mitte", "rechts"]).astype(str)
    p.loc[p.ideo_gesellschaft_baseline.isna(), "ideo_gruppe"] = np.nan
    p["medientyp"] = p.medientyp.map(MEDIENTYP)
    md = []
    for var in ["medientyp", "ideo_gruppe"]:
        dd = p.dropna(subset=[var])
        m, d = schaetze(dd, "y_nk", f"anteil_l1:C({var})", "w_nk", dichte)
        md += [f"### Anteil(t-1) × {var} (Outcome y_nk, Effekt je Gruppe)", "",
               "| Gruppe | Koeffizient (SE) | p | +10 pp | N Kanäle |", "|---|---|---|---|---|"]
        for t in m.params.index:
            if t.startswith("anteil_l1:"):
                gr = t.split("[")[1].rstrip("]").replace("T.", "")
                nk = d[d[var] == gr].channel_id.nunique()
                md.append(f"| {gr} | {m.params[t]:.3f} ({m.bse[t]:.3f}) | {m.pvalues[t]:.3f} | "
                          f"{effekt_text(m.params[t])} | {nk} |")
        md.append("")
    return "\n".join(md)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    RES.mkdir(parents=True, exist_ok=True)
    v, k, rel = lade_daten()
    print(f"{len(v):,} Videos im Fenster geladen")
    kern = set(k.loc[k.sample_kern == 1, "channel_id"])

    haupt = baue_panel(v, rel)
    haupt.to_csv(OUT / "kanal_monat_panel.csv", index=False)
    panels = {
        "Haupt (cw, Nenner Themen, Dichte Periode)": (haupt, "log_dichte_periode"),
        "Upload-Dichte Fenster ±48 h": (haupt, "log_dichte_fenster"),
        "core (Zähler und Nenner)": (baue_panel(v, rel, stufe="core"), "log_dichte_periode"),
        "Nenner alle Long-Videos": (baue_panel(v, rel, nenner="alle"), "log_dichte_periode"),
        "ohne format_derived (WELT)": (baue_panel(v, rel, ohne_derived=True), "log_dichte_periode"),
        "nur Nachkriegsmonate (t ≥ 03/2022)": (haupt[haupt.monat > KRIEGSBEGINN], "log_dichte_periode"),
        "nur sample_kern": (haupt[haupt.channel_id.isin(kern)], "log_dichte_periode"),
    }

    md = ["# Kriegsanteil (t-1) und Kanalerfolg (t)", "",
          "Erzeugt von `scripts/adhoc/kriegsanteil_lag_erfolg.py` (Details im Docstring). "
          "Kanal-Monats-Panel, nur Long-Videos, 01/2021–06/2026. WLS mit Kanal- und Monats-FE, "
          "Gewicht sqrt(n Videos), SE geclustert nach Kanal. "
          f"Kriegsanteil fehlt bei < {MIN_NENNER} Videos im Nenner, Outcome bei < {MIN_VIDEOS_OUTCOME} Videos.", "",
          "**Variablen:** `anteil` = Kriegsanteil im Monat t (Hauptspezifikation: Kriegsvideos cw / "
          "Videos mit irgendeinem rel_*_cw-Treffer), `_l1..3` = Lags, `_f1` = Lead (Placebo). "
          "`y_alle` = Median log(1+Views) aller Long-Videos in t, `y_nk` = dto. nur Nicht-Kriegsvideos. "
          "Koeffizient × 0,1 ≈ Veränderung der Median-Views (log) bei +10 Prozentpunkten Kriegsanteil.", "",
          "Signifikanz: * p<0,1, ** p<0,05, *** p<0,01; Standardfehler in Klammern.", "",
          "## Deskriptiv (Hauptspezifikation)", "", deskriptiv(haupt), ""]

    for titel, (p, dichte) in panels.items():
        tab, info = lauf_tabelle(p, dichte)
        b3 = info["M3"][0].params["anteil_l1"]
        md += [f"## {titel}", "", tab, "",
               f"M3: +10 pp Kriegsanteil in t-1 ⇒ Median-Views der Nicht-Kriegsvideos in t "
               f"{effekt_text(b3)}.", ""]
        print(f"fertig: {titel}")

    md += ["## Heterogenität (Hauptspezifikation)", "", heterogenitaet(haupt, k, "log_dichte_periode")]
    (RES / "kriegsanteil_lag_erfolg.md").write_text("\n".join(md), encoding="utf-8")
    print(f"geschrieben: {RES / 'kriegsanteil_lag_erfolg.md'}")


if __name__ == "__main__":
    main()

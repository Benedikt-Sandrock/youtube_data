"""Welche Kanaele tragen den Views-Anstieg der Alternativmedien zwischen
Woche 20 und 36 nach Kriegsbeginn (Mitte Juli bis Mitte Okt. 2022)?
Bezug: marktanteil_medientyp_ideologie_kombiniert_long_woche_20211230-20230104_manuell_absolut.png
(outputs/segment_analysis/plots_marktanteil_rohdaten/).

Vorgehen:
- Kanalliste wie KANALLISTE in step6_auswertung/marktanteil_rohdaten_plots.py
  (channels_check.xlsx: media_category in MEDIA_CATEGORIES, sample in
  SAMPLE_CODES, foreign != 1), aber mit eigenen MEDIA_CATEGORIES (Default 3/4/5 =
  alle Alternativen statt nur 5). Gruppenzuordnung ueber medientyp_ideologie
  (Ideologie-Baseline) und MANUELL_ALT_RECHTS aus marktanteil_rohdaten_plots;
  analysiert werden die Kanaele der Gruppen in GRUPPEN (gepoolt, Gruppe je Kanal
  in den Tabellen). Kanaele der Liste ohne passende Gruppe (z. B. media_category
  3/4 ohne Ideologie-Baseline) werden im Ergebnis aufgelistet.
  Videos aus videos_roh.dta mit format == long, rel_woche = Woche relativ zum
  24.02.2022 (Do-Mi).
- Phasen (rel_woche, inklusive) siehe PHASEN; Phasenwerte = mittlere Views je
  Woche (Wochen ohne Upload = 0). Hauptvergleich VERGLEICH = (vorher, nachher).
- Kanaltabellen: groesste Zuwaechse und Rueckgaenge, Zerlegung in Uploads je
  Woche und Views je Video, Anteil der Kriegsvideos (rel_russia_ukraine_war_cw).
- Wachstumsraten je Kanal (% gegenueber dem Mittel der Phase WACHSTUM_BASIS) je
  Phase und je BLOCK_WOCHEN-Wochen-Block, nur Kanaele mit mind. WACHSTUM_MIN_BASIS
  Mio. Views je Woche in der Basis (kleine Nenner verzerren die Raten).
- Grafik: gestapelte Wochen-Views der TOP_GRAFIK groessten Zuwachs-Kanaele plus Rest.
Hinweis: Der Skriptname stammt aus der ersten Fassung (nur Alternative rechts,
Ergebnisse in scripts/adhoc/alt_rechts_anstieg_woche/).

Views sind kumulierte Snapshots (Abruf 2026); innerhalb von 2022 ist der
Alterseffekt klein, aber nicht null.
Ausgabe: AUSGABE, Default scripts/adhoc/alternative_anstieg_woche/ (ergebnis.md, kanaele.csv,
wochen_top_kanaele.csv, wachstumsraten.csv, stapel_top_kanaele.png).
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from youtube_code.step6_auswertung import marktanteil_rohdaten_plots as mp  # noqa: E402
from youtube_code.step6_auswertung.prepare_channel_scores import KRIEGSBEGINN  # noqa: E402

# =========================================================
# KONFIGURATION
# =========================================================
MEDIA_CATEGORIES = [3, 4, 5]      # media_category in channels_check.xlsx: 3/4/5 = alternativ links/mitte/rechts
SAMPLE_CODES = [1, 2, 3]          # sample-Codes in channels_check.xlsx wie in marktanteil_rohdaten_plots (0-5)
GRUPPEN = ["Alternative (links)", "Alternative (mitte)", "Alternative (rechts)"]  # Gruppen aus medientyp_ideologie
WOCHEN = (-8, 44)                 # rel_woche-Bereich (inklusive) wie in der Grafik
PHASEN = {                        # Name -> rel_woche (von, bis), inklusive, aufsteigend, ohne Ueberlappung
    "VORKRIEG": (-8, -1),
    "KONSTANT": (1, 19),          # konstante Phase nach Kriegsbeginn
    "ANSTIEG": (20, 36),          # Anstiegsphase laut Grafik
    "DANACH": (37, 44),
}
VERGLEICH = ("KONSTANT", "ANSTIEG")   # (vorher, nachher), beide aus PHASEN
TOP_KANAELE = 25                  # Zeilen der Zuwachs-Tabelle (int >= 1)
TOP_RUECKGANG = 10                # Zeilen der Rueckgangs-Tabelle (int >= 0)
TOP_GRAFIK = 8                    # Kanaele einzeln in der Stapelgrafik (1..12)
BLOCK_WOCHEN = 4                  # Wochen je Spalte der Verlaufstabelle (int >= 1)
WACHSTUM_BASIS = "KONSTANT"       # Phase aus PHASEN, auf deren Mittel (= 0 %) die Wachstumsraten bezogen sind
WACHSTUM_MIN_BASIS = 0.05         # Mio. Views je Woche in WACHSTUM_BASIS, ab der ein Kanal in die Wachstumstabelle kommt (> 0)
AUSGABE = ROOT / "scripts" / "adhoc" / "alternative_anstieg_woche"   # Ausgabeordner


def kanalliste():
    """channel_id -> media_category wie KANALLISTE in marktanteil_rohdaten_plots, mit MEDIA_CATEGORIES/SAMPLE_CODES."""
    df = pd.read_excel(mp.STATA_OUTPUT / "channels_check.xlsx")
    df = df[df["media_category"].isin(MEDIA_CATEGORIES) & df["sample"].isin(SAMPLE_CODES) & (df["foreign"] != 1)]
    return df.set_index("channel_id")["media_category"]


def lade():
    liste = kanalliste()
    k = mp.lade_kanaele()
    k, _ = mp.bilde_gruppen(k)
    k = k[k["channel_id"].isin(liste.index)]
    k, _ = mp.manuell_alt_rechts(k)
    k["media_category"] = k["channel_id"].map(liste).astype(int)
    k["kanal_name"] = k["kanal_name"].astype(str).str.strip()
    ohne = k[~k["medientyp_ideologie"].isin(GRUPPEN)][["kanal_name", "media_category", "medientyp",
                                                        "medientyp_ideologie"]]
    k = k[k["medientyp_ideologie"].isin(GRUPPEN)].rename(columns={"medientyp_ideologie": "gruppe"})
    k = k[["channel_id", "kanal_name", "gruppe", "media_category", "sample_vorkrieg"]]
    v = pd.read_stata(mp.ROHDATEN_PFAD / "videos_roh.dta",
                      columns=["video_id", "channel_id", "titel", "upload_ts", "views", "format",
                               "rel_russia_ukraine_war_cw"])
    v = v[(v["format"].astype(str) == "long") & v["views"].notna()]
    v = v.merge(k[["channel_id", "kanal_name"]], on="channel_id", how="inner")
    v["rel_woche"] = ((v["upload_ts"] - pd.Timestamp(KRIEGSBEGINN)).dt.days // 7).astype(int)
    v = v[v["rel_woche"].between(*WOCHEN)].copy()
    v["krieg"] = v["rel_russia_ukraine_war_cw"].astype(str) == "ja"
    return k.set_index("channel_id"), v, ohne


def md(df, fmt=None):
    df = df.copy()
    for c, f in (fmt or {}).items():
        if c not in df.columns:
            continue
        df[c] = df[c].map(lambda x: f.format(x) if pd.notna(x) else "")
    kopf = "| " + " | ".join(map(str, df.columns)) + " |"
    trenn = "|" + "---|" * len(df.columns)
    zeilen = ["| " + " | ".join(str(x).replace("|", "/") for x in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([kopf, trenn, *zeilen])


def n_wochen(p):
    return PHASEN[p][1] - PHASEN[p][0] + 1


def main():
    grenzen = list(PHASEN.values())
    if any(len(f) != 2 or f[0] > f[1] for f in grenzen) or any(a[1] >= b[0] for a, b in zip(grenzen, grenzen[1:])):
        raise SystemExit("PHASEN: je (von, bis) mit von <= bis, aufsteigend und ohne Ueberlappung.")
    if not all(WOCHEN[0] <= f[0] and f[1] <= WOCHEN[1] for f in grenzen):
        raise SystemExit(f"PHASEN muessen innerhalb von WOCHEN {WOCHEN} liegen.")
    if len(VERGLEICH) != 2 or not set(VERGLEICH) <= set(PHASEN):
        raise SystemExit(f"VERGLEICH muss zwei Phasen aus PHASEN nennen, nicht {VERGLEICH!r}.")
    if WACHSTUM_BASIS not in PHASEN or not WACHSTUM_MIN_BASIS > 0:
        raise SystemExit(f"WACHSTUM_BASIS muss eine Phase aus PHASEN sein und WACHSTUM_MIN_BASIS > 0.")
    if not MEDIA_CATEGORIES or not set(MEDIA_CATEGORIES) <= {1, 2, 3, 4, 5, 6}:
        raise SystemExit(f"MEDIA_CATEGORIES muss eine nicht leere Liste von Codes 1-6 sein, nicht {MEDIA_CATEGORIES!r}.")
    if not SAMPLE_CODES or not set(SAMPLE_CODES) <= {0, 1, 2, 3, 4, 5}:
        raise SystemExit(f"SAMPLE_CODES muss eine nicht leere Liste von Codes 0-5 sein, nicht {SAMPLE_CODES!r}.")
    erlaubt = mp.KLASSIFIKATIONEN["medientyp_ideologie"]["gruppen"]
    if not GRUPPEN or not set(GRUPPEN) <= set(erlaubt):
        raise SystemExit(f"GRUPPEN muss eine nicht leere Teilmenge von {erlaubt} sein, nicht {GRUPPEN!r}.")
    if TOP_KANAELE < 1 or TOP_RUECKGANG < 0 or not 1 <= TOP_GRAFIK <= 12 or BLOCK_WOCHEN < 1:
        raise SystemExit("TOP_KANAELE >= 1, TOP_RUECKGANG >= 0, TOP_GRAFIK in 1..12, BLOCK_WOCHEN >= 1.")
    AUSGABE.mkdir(parents=True, exist_ok=True)
    k, v, ohne = lade()
    ph = list(PHASEN)
    v["phase"] = None
    for p, f in PHASEN.items():
        v.loc[v["rel_woche"].between(*f), "phase"] = p
    vor, nach = VERGLEICH

    titel = " + ".join(GRUPPEN)
    n_gr = k["gruppe"].value_counts().reindex(GRUPPEN, fill_value=0)
    out = [f"# Views-Anstieg bei {titel} zwischen Woche {PHASEN['ANSTIEG'][0]} und {PHASEN['ANSTIEG'][1]}"
           if "ANSTIEG" in PHASEN else f"# Views-Verlauf bei {titel}", "",
           f"Erzeugt von `scripts/adhoc/alt_rechts_anstieg_woche.py`. Kanalliste wie in `marktanteil_rohdaten_plots.py` "
           f"(channels_check.xlsx: media_category in {MEDIA_CATEGORIES}, sample in {SAMPLE_CODES}, foreign != 1), "
           f"Gruppen aus medientyp_ideologie (Ideologie-Baseline, MANUELL_ALT_RECHTS = {mp.MANUELL_ALT_RECHTS}), "
           f"nur long-Videos, Sample „alle Kanäle“; Gruppen gepoolt. "
           f"{len(k)} Kanäle ({', '.join(f'{g}: {n}' for g, n in n_gr.items())}), davon "
           f"{v['channel_id'].nunique()} mit Videos in Woche "
           f"{WOCHEN[0]}–{WOCHEN[1]}. Phasen (rel_woche, Woche 0 = 24.02.–02.03.2022): "
           + ", ".join(f"{p} {a}–{b} ({mp.woche_start(a):%d.%m.}–{mp.woche_start(b) + pd.Timedelta(days=6):%d.%m.%y})"
                       for p, (a, b) in PHASEN.items())
           + ". Phasenwerte = mittlere Views je Woche (Wochen ohne Upload = 0). Views = kumulierter Snapshot 2026. "
           "„Gesamt“ = alle Gruppen in GRUPPEN zusammen.", ""]
    if len(ohne):
        out += [f"Kanäle der Liste ohne Gruppe aus GRUPPEN (nicht enthalten): {len(ohne)}", "",
                md(ohne.astype(object).fillna("–").sort_values("kanal_name")), ""]
    kz = k["media_category"].groupby(k["gruppe"]).value_counts().unstack(fill_value=0)
    out += ["Gruppe (Ideologie-Baseline) × manuelle media_category der enthaltenen Kanäle:", "",
            md(kz.rename(columns=lambda c_: f"cat_{c_}").rename_axis(index="gruppe", columns=None).reset_index()), ""]

    # --- 1. Niveau je Phase
    c = v.groupby(["channel_id", "phase"])["views"].sum().unstack(fill_value=0).reindex(columns=ph, fill_value=0)
    upl = v.groupby(["channel_id", "phase"]).size().unstack(fill_value=0).reindex(columns=ph, fill_value=0)
    krieg = v[v["krieg"]].groupby(["channel_id", "phase"])["views"].sum().unstack(fill_value=0) \
        .reindex(index=c.index, columns=ph, fill_value=0)
    for p in ph:
        c[p] /= n_wochen(p)
        upl[p] /= n_wochen(p)
        krieg[p] /= n_wochen(p)
    v["gruppe"] = v["channel_id"].map(k["gruppe"])
    kurz = {g: "mio_" + g.removeprefix("Alternative (").rstrip(")") for g in GRUPPEN}
    rows = []
    for p in ph:
        d = v[v["phase"] == p]
        s = c[p].sort_values(ascending=False)
        rows.append({"phase": p, **{kurz[g]: d.loc[d["gruppe"] == g, "views"].sum() / 1e6 / n_wochen(p)
                                    for g in GRUPPEN},
                     "wochen": f"{PHASEN[p][0]}–{PHASEN[p][1]}", "views_mio_je_woche": s.sum() / 1e6,
                     "uploads_je_woche": len(d) / n_wochen(p), "kanaele_aktiv": d["channel_id"].nunique(),
                     "views_je_video_tsd": d["views"].mean() / 1e3, "median_tsd": d["views"].median() / 1e3,
                     "anteil_krieg_views": d.loc[d["krieg"], "views"].sum() / d["views"].sum(),
                     "anteil_top5": s.head(5).sum() / s.sum(), "anteil_top10": s.head(10).sum() / s.sum()})
    out += ["## 1. Niveau je Phase", "",
            "mio_<gruppe> = Mio. Views je Woche der Gruppe, views_mio_je_woche = gesamt. Top-5/Top-10 = Anteil der in der jeweiligen Phase stärksten Kanäle an den Views der Phase; "
            "anteil_krieg_views = Anteil der Views von Kriegsvideos (Titel-Stichworte).", "",
            md(pd.DataFrame(rows), {**{c_: "{:.2f}" for c_ in kurz.values()}, "views_mio_je_woche": "{:.2f}", "uploads_je_woche": "{:.0f}",
                                    "views_je_video_tsd": "{:.1f}", "median_tsd": "{:.1f}",
                                    "anteil_krieg_views": "{:.0%}", "anteil_top5": "{:.0%}",
                                    "anteil_top10": "{:.0%}"}), ""]

    # --- 2. Kanalzerlegung
    t = k[["kanal_name", "gruppe", "sample_vorkrieg"]].join(c.div(1e6).add_prefix("views_"), how="left").fillna(0)
    t = t.join(upl.add_prefix("uploads_"), how="left").fillna(0)
    t["delta"] = t[f"views_{nach}"] - t[f"views_{vor}"]
    t["faktor"] = t[f"views_{nach}"] / t[f"views_{vor}"].replace(0, np.nan)
    t["vpv_vor"] = t[f"views_{vor}"] * 1e3 / t[f"uploads_{vor}"].replace(0, np.nan)   # Tsd. Views je Video
    t["vpv_nach"] = t[f"views_{nach}"] * 1e3 / t[f"uploads_{nach}"].replace(0, np.nan)
    t["delta_krieg"] = (krieg[nach] - krieg[vor]).reindex(t.index).fillna(0) / 1e6
    gesamt = t["delta"].sum()
    pos = t.loc[t["delta"] > 0, "delta"].sort_values(ascending=False)
    t["anteil_delta"] = t["delta"] / gesamt
    t.sort_values("delta", ascending=False).to_csv(AUSGABE / "kanaele.csv", encoding="utf-8-sig")

    beide = t[(t[f"uploads_{vor}"] > 0) & (t[f"uploads_{nach}"] > 0)]
    neu = t[(t[f"uploads_{vor}"] == 0) & (t[f"uploads_{nach}"] > 0)]
    weg = t[(t[f"uploads_{vor}"] > 0) & (t[f"uploads_{nach}"] == 0)]
    ohne_top5 = t.drop(pos.index[:5])
    out += [f"## 2. Wer trägt den Anstieg ({vor} → {nach})?", "",
            *[f"- {g}: {t.loc[t['gruppe'] == g, f'views_{vor}'].sum():.2f} → "
              f"{t.loc[t['gruppe'] == g, f'views_{nach}'].sum():.2f} Mio. Views je Woche "
              f"({t.loc[t['gruppe'] == g, 'delta'].sum():+.2f} Mio., "
              f"{t.loc[t['gruppe'] == g, 'delta'].sum() / gesamt:.0%} des Netto-Anstiegs)." for g in GRUPPEN],
            f"- Gesamt: {t[f'views_{vor}'].sum():.2f} → {t[f'views_{nach}'].sum():.2f} Mio. Views je Woche "
            f"(**{gesamt:+.2f} Mio.**, Faktor {t[f'views_{nach}'].sum() / t[f'views_{vor}'].sum():.2f}).",
            f"- Kanäle mit Zuwachs: {int((t['delta'] > 0).sum())}, mit Rückgang: {int((t['delta'] < 0).sum())}; "
            f"Summe der Zuwächse {pos.sum():+.2f}, der Rückgänge {t.loc[t['delta'] < 0, 'delta'].sum():+.2f} Mio.",
            f"- Anteil am Netto-Anstieg: Top 1 {pos.head(1).sum() / gesamt:.0%}, Top 3 {pos.head(3).sum() / gesamt:.0%}, "
            f"Top 5 {pos.head(5).sum() / gesamt:.0%}, Top 10 {pos.head(10).sum() / gesamt:.0%}.",
            f"- Ohne die Top-5-Zuwachskanäle: {ohne_top5[f'views_{vor}'].sum():.2f} → "
            f"{ohne_top5[f'views_{nach}'].sum():.2f} Mio. je Woche "
            f"(Faktor {ohne_top5[f'views_{nach}'].sum() / ohne_top5[f'views_{vor}'].sum():.2f}).",
            f"- Median-Faktor über {len(beide)} Kanäle mit Videos in beiden Phasen: {beide['faktor'].median():.2f}; "
            f"Anteil mit Faktor > 1,25: {(beide['faktor'] > 1.25).mean():.0%}, < 0,8: {(beide['faktor'] < 0.8).mean():.0%}.",
            f"- Erst in {nach} aktiv: {len(neu)} Kanäle ({neu[f'views_{nach}'].sum():.2f} Mio. je Woche"
            + (f": {', '.join(neu.sort_values(f'views_{nach}', ascending=False)['kanal_name'].head(5))}" if len(neu) else "")
            + f"); nur in {vor} aktiv: {len(weg)} ({weg[f'views_{vor}'].sum():.2f} Mio.).",
            f"- Beitrag der Kriegsvideos zum Netto-Anstieg: {t['delta_krieg'].sum():+.2f} Mio. je Woche "
            f"({t['delta_krieg'].sum() / gesamt:.0%}).", ""]

    spalten = ["kanal_name", "gruppe", "sample_vorkrieg", f"views_{vor}", f"views_{nach}", "views_DANACH" if "DANACH" in PHASEN
               else f"views_{nach}", "faktor", f"uploads_{vor}", f"uploads_{nach}", "vpv_vor", "vpv_nach",
               "delta", "anteil_delta", "delta_krieg"]
    spalten = list(dict.fromkeys(spalten))
    fmt = {c_: "{:.2f}" for c_ in spalten if c_.startswith("views_") or c_ in ("faktor", "delta_krieg")}
    fmt.update({f"uploads_{vor}": "{:.1f}", f"uploads_{nach}": "{:.1f}", "vpv_vor": "{:.1f}", "vpv_nach": "{:.1f}",
                "delta": "{:+.2f}", "anteil_delta": "{:.0%}"})
    out += [f"### Top {TOP_KANAELE} nach absolutem Zuwachs", "",
            "Views in Mio. je Woche, uploads = Videos je Woche, vpv = Tsd. Views je Video, "
            "anteil_delta = Anteil am Netto-Anstieg der Gruppe, delta_krieg = Zuwachs der Views aus Kriegsvideos.", "",
            md(t.sort_values("delta", ascending=False).head(TOP_KANAELE)[spalten], fmt), ""]
    if TOP_RUECKGANG:
        out += [f"### Kanäle mit dem größten Rückgang", "",
                md(t[t["delta"] < 0].sort_values("delta").head(TOP_RUECKGANG)[spalten], fmt), ""]

    # --- 3. Verlauf der wichtigsten Kanaele in Wochenbloecken
    wichtig = list(dict.fromkeys([*pos.index[:12], *t.sort_values(f"views_{nach}", ascending=False).index[:8],
                                  *t[t["delta"] < 0].sort_values("delta").index[:5]]))
    wv = v.groupby(["channel_id", "rel_woche"])["views"].sum().unstack(fill_value=0) \
        .reindex(columns=range(WOCHEN[0], WOCHEN[1] + 1), fill_value=0)
    wv.loc[wichtig].div(1e6).rename(index=t["kanal_name"]).to_csv(AUSGABE / "wochen_top_kanaele.csv",
                                                                   encoding="utf-8-sig")
    blk = (np.arange(WOCHEN[0], WOCHEN[1] + 1) - WOCHEN[0]) // BLOCK_WOCHEN
    namen = {b: f"W{WOCHEN[0] + b * BLOCK_WOCHEN}" for b in np.unique(blk)}
    bl = wv.T.groupby(blk).mean().T.rename(columns=namen) / 1e6
    tab = bl.loc[wichtig].rename(index=t["kanal_name"])
    tab.loc["Rest (übrige Kanäle)"] = bl.drop(index=wichtig, errors="ignore").sum()
    for g in GRUPPEN:
        tab.loc[f"{g} gesamt"] = bl.reindex(k.index[k["gruppe"] == g]).sum()
    tab.loc["Gesamt"] = bl.sum()
    out += [f"## 3. Verlauf wichtiger Kanäle (Mio. Views je Woche, Mittel über {BLOCK_WOCHEN}-Wochen-Blöcke)", "",
            "Zeilen: die 12 größten Zuwachskanäle, die 8 reichweitenstärksten Kanäle der Anstiegsphase und die "
            "5 größten Rückgänge. Spaltenname = erste Woche des Blocks. Wochenwerte in wochen_top_kanaele.csv.", "",
            md(tab.rename_axis("kanal").reset_index(), {c_: "{:.2f}" for c_ in tab.columns}), ""]

    # --- 3b. Wachstumsraten gegenueber der Basisphase
    basis = t[f"views_{WACHSTUM_BASIS}"]
    auswahl = t[basis >= WACHSTUM_MIN_BASIS].sort_values("delta", ascending=False).index
    rate_ph = pd.DataFrame({p: (t[f"views_{p}"] / basis - 1) * 100 for p in ph if p != WACHSTUM_BASIS})
    bl_b = bl.reindex(t.index).fillna(0)
    rate_bl = (bl_b.div(basis, axis=0) - 1) * 100
    vp = [f"views_{p}" for p in ph]
    zeilen_g = {**{f"{g} gesamt": (t.loc[t["gruppe"] == g, vp].sum(), bl_b[t["gruppe"] == g].sum())
                   for g in GRUPPEN if t.loc[t["gruppe"] == g, f"views_{WACHSTUM_BASIS}"].sum() > 0},
                "Gesamt": (t[vp].sum(), bl_b.sum()),
                f"Gesamt ohne Top 5 ({vor} → {nach})": (t.drop(pos.index[:5])[[f"views_{p}" for p in ph]].sum(),
                                                         bl_b.drop(pos.index[:5]).sum())}
    wt = pd.DataFrame({"kanal": t.loc[auswahl, "kanal_name"], "basis_mio": basis[auswahl]}) \
        .join(rate_ph.loc[auswahl]).join(rate_bl.loc[auswahl])
    wt.insert(1, "gruppe", t.loc[auswahl, "gruppe"])
    for name, (s_ph, s_bl) in zeilen_g.items():
        b = s_ph[f"views_{WACHSTUM_BASIS}"]
        wt.loc[name] = {"kanal": name, "gruppe": "", "basis_mio": b,
                        **{p: (s_ph[f"views_{p}"] / b - 1) * 100 for p in rate_ph.columns},
                        **{c_: (s_bl[c_] / b - 1) * 100 for c_ in rate_bl.columns}}
    wt.to_csv(AUSGABE / "wachstumsraten.csv", encoding="utf-8-sig", index=False)
    n_klein = int(((basis > 0) & (basis < WACHSTUM_MIN_BASIS)).sum())
    pfmt = {c_: "{:+.0f}" for c_ in wt.columns if c_ not in ("kanal", "gruppe", "basis_mio")}
    letzter = WOCHEN[0] + (len(namen) - 1) * BLOCK_WOCHEN
    out += [f"## 3b. Wachstumsraten gegenüber {WACHSTUM_BASIS} (Woche {PHASEN[WACHSTUM_BASIS][0]}–"
            f"{PHASEN[WACHSTUM_BASIS][1]})", "",
            f"Veränderung der mittleren Views je Woche in % gegenüber dem Mittel der Phase {WACHSTUM_BASIS} "
            f"(basis_mio, Mio. Views je Woche; Wochen ohne Upload = 0). Nur Kanäle mit basis_mio >= "
            f"{WACHSTUM_MIN_BASIS} ({len(auswahl)} Kanäle; {n_klein} kleinere Kanäle mit Videos in der Basis "
            f"ausgelassen, ihre Raten wären durch kleine Nenner verzerrt). Sortiert nach absolutem Zuwachs "
            f"{vor} → {nach}. Blockspalten = Mittel über {BLOCK_WOCHEN}-Wochen-Blöcke, Name = erste Woche "
            f"(Block W{letzter} ggf. unvollständig: Woche {letzter}–{WOCHEN[1]}). Wochenwerte einzelner Kanäle "
            "schwanken stark (einzelne Hits), Blockwerte daher nur als grober Verlauf lesen. "
            "Auch als wachstumsraten.csv.", "",
            "### Nach Phasen", "",
            md(wt[["kanal", "gruppe", "basis_mio", *rate_ph.columns]], {"basis_mio": "{:.2f}", **pfmt}), "",
            f"### Nach {BLOCK_WOCHEN}-Wochen-Blöcken", "",
            md(wt[["kanal", "gruppe", "basis_mio", *rate_bl.columns]], {"basis_mio": "{:.2f}", **pfmt}), ""]

    # --- 4. Stapelgrafik
    top = list(pos.index[:TOP_GRAFIK])
    stapel = wv.loc[top].rename(index=t["kanal_name"] + " (" + t["gruppe"].str.removeprefix("Alternative (")) / 1e6
    rest = (wv.drop(index=top).sum() / 1e6).rename("übrige Kanäle")
    farben = ["#2a78b5", "#e5a33b", "#3a9e6c", "#c2493f", "#7a5aa8", "#8c6239", "#d47bb0", "#5a5a5a",
              "#6cb8d6", "#b5b33a", "#9e3a5a", "#3a5a9e"][:TOP_GRAFIK]
    fig, ax = plt.subplots(figsize=(14, 6.5))
    x = wv.columns.to_numpy()
    ax.stackplot(x, rest.to_numpy(), *stapel.to_numpy(), labels=[rest.name, *stapel.index],
                 colors=["#d9d9d9", *farben], linewidth=0)
    for p, (a, b) in PHASEN.items():
        ax.axvspan(a - 0.5, b + 0.5, color="none", ec="#999", lw=0.6, ls=":")
        ax.text((a + b) / 2, 0.98, p, transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=9,
                color="#555")
    ax.axvline(-0.5, color="#333", ls="--", lw=1)
    ax.set_xlim(x[0] - 0.5, x[-1] + 0.5)
    ax.set_xticks(range(WOCHEN[0], WOCHEN[1] + 1, 4))
    ax.set_xticklabels([f"{w}\n{mp.woche_start(w):%d.%m.%y}" for w in range(WOCHEN[0], WOCHEN[1] + 1, 4)])
    ax.set_xlabel("Woche relativ zum Kriegsbeginn (Woche 0 = 24.02.–02.03.2022, Do–Mi)")
    ax.set_ylabel("Views je Woche (Mio.)")
    ax.set_title(f"{titel}: Wochen-Views, gestapelt – {TOP_GRAFIK} größte Zuwachskanäle ({vor} → {nach})")
    ax.spines[["top", "right"]].set_visible(False)
    h, l = ax.get_legend_handles_labels()
    ax.legend(h[::-1], l[::-1], loc="upper left", fontsize=8, frameon=False, bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    fig.savefig(AUSGABE / "stapel_top_kanaele.png", dpi=150)
    out += ["## 4. Grafik", "", "![Stapelgrafik](stapel_top_kanaele.png)", ""]

    (AUSGABE / "ergebnis.md").write_text("\n".join(out), encoding="utf-8")
    print(f"Geschrieben: {AUSGABE / 'ergebnis.md'}")


if __name__ == "__main__":
    main()

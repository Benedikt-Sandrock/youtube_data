"""Zerlegung des Views-Sprungs der rechten Alternativmedien in Monat 5/6
(24.07.-23.09.2022) aus marktanteil_medientyp_ideologie_kombiniert_long_manuell_absolut.png.

Fragen: Welche Kanaele tragen den Anstieg? Breit getragen oder wenige Kanaele?
Mehr Uploads oder mehr Views je Video? Einzelne virale Videos? Welche Themen?
Bleibt das Niveau danach erhalten (je Kanal)?

Vorgehen:
- Kanaele und Gruppen exakt wie in step6_auswertung/marktanteil_rohdaten_plots.py
  (KANALLISTE, medientyp_ideologie, MANUELL_ALT_RECHTS), Videos aus videos_roh.dta
  mit format == long, rel_monat relativ zum 24.02.2022.
- Fenster (rel_monat, inklusive): VOR, SPRUNG, SPAETER; Vergleich = mittlere
  Views je Monat im Fenster (Monate ohne Upload = 0).
- Themen: Titel-Stichworte rel_<thema>_cw aus dem Export plus lokale Regex
  (Energie breit, Inflation/Geld, Regierungskritik) ueber den Titel.
- Titel/Beschreibung aus data/store/video_registry.sqlite.

Views sind kumulierte Snapshots (Abruf 2026).
Ausgabe: scripts/adhoc/alt_rechts_sprung/ergebnis.md (+ kanaele.csv, monate.csv).
"""
import re
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from youtube_code.step6_auswertung import marktanteil_rohdaten_plots as mp  # noqa: E402
from youtube_code.step6_auswertung.prepare_channel_scores import KRIEGSBEGINN, relativ_periode  # noqa: E402
from youtube_code.step3_topic_relevance.topic_keywords import TOPIC_KEYWORDS  # noqa: E402

# =========================================================
# KONFIGURATION
# =========================================================
GRUPPE = "Alternative (rechts)"   # Gruppe aus medientyp_ideologie
VOR = (1, 4)                      # rel_monat (von, bis) vor dem Sprung, inklusive
SPRUNG = (5, 8)                   # rel_monat nach dem Sprung, inklusive
SPAETER = (9, 20)                 # rel_monat fuer "bleibt das Niveau?", inklusive
MONATE_TABELLE = (-6, 14)         # Monatsbereich der Monatstabellen
TOP_KANAELE = 25                  # Zeilen der Kanaltabelle (int >= 1)
TOP_TITEL = 12                    # meistgesehene Titel je Top-Kanal im Sprungfenster
TOP_KANAELE_TITEL = 8             # fuer so viele Top-Wachstumskanaele Titel listen
# Lokale Themen-Regex ueber den Titel (Kleinschreibung)
REGEX_THEMEN = {
    "energie_breit": (r"energie|strom(?!ung)|erdgas|\bgas(?!t)|gasum|heiz|blackout|frier|"
                      r"nord ?stream|\blng\b|atomkraft|\bakw|kernkraft|kraftwerk|sprit|benzin|"
                      r"diesel|tankrabatt|windkraft|wärmepumpe|lastabwurf"),
    "inflation_geld": (r"inflation|preis|teuer|zins|\bezb\b|euro\b|crash|rezession|krise|"
                       r"gold|silber|aktie|börse|immobil|miete|vermiet|geld|enteign|pleite|insolvenz"),
    "regierung": (r"habeck|scholz|lauterbach|baerbock|lindner|faeser|ampel|regierung|grüne"),
}
REGISTRY = ROOT / "data" / "store" / "video_registry.sqlite"
AUSGABE = ROOT / "scripts" / "adhoc" / "alt_rechts_sprung"


def lade():
    k = mp.lade_kanaele()
    k, _ = mp.bilde_gruppen(k)
    k, _ = mp.manuell_alt_rechts(k)
    k = k[k["channel_id"].isin(mp.KANALLISTE) & (k["medientyp_ideologie"] == GRUPPE)]
    k = k[["channel_id", "kanal_name", "abonnenten", "sample_vorkrieg"]]
    themen = [f"rel_{t}_cw" for t in TOPIC_KEYWORDS]
    v = pd.read_stata(mp.ROHDATEN_PFAD / "videos_roh.dta",
                      columns=["video_id", "channel_id", "upload_ts", "views", "format", "dauer_sek", *themen])
    v = v[(v["format"].astype(str) == "long") & v["views"].notna()]
    v = v.merge(k, on="channel_id", how="inner")
    v["rel_monat"] = relativ_periode(v["upload_ts"], pd.Timestamp(KRIEGSBEGINN), 1)
    v = v[v["rel_monat"].between(min(MONATE_TABELLE[0], VOR[0]), max(MONATE_TABELLE[1], SPAETER[1]))]
    for t in themen:
        v[t.removeprefix("rel_").removesuffix("_cw")] = (v[t].astype(str) == "ja").astype(int)
    v = v.drop(columns=themen)

    con = sqlite3.connect(f"file:{REGISTRY}?mode=ro", uri=True)
    ids, teile = v["video_id"].tolist(), []
    for i in range(0, len(ids), 900):
        c = ids[i:i + 900]
        teile.append(pd.read_sql_query(
            "SELECT v.video_id, v.title, d.description FROM videos v LEFT JOIN video_details d "
            "USING(video_id) WHERE v.video_id IN (%s)" % ",".join("?" * len(c)), con, params=c))
    con.close()
    v = v.merge(pd.concat(teile), on="video_id", how="left")
    tl = v["title"].fillna("").str.lower()
    for name, rx in REGEX_THEMEN.items():
        v["rx_" + name] = tl.str.contains(rx, regex=True).astype(int)
    return k, v


def md(df, fmt=None):
    df = df.copy()
    for c, f in (fmt or {}).items():
        df[c] = df[c].map(lambda x: f.format(x) if pd.notna(x) else "")
    kopf = "| " + " | ".join(map(str, df.columns)) + " |"
    trenn = "|" + "---|" * len(df.columns)
    zeilen = ["| " + " | ".join(str(x).replace("|", "/") for x in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([kopf, trenn, *zeilen])


def fenster_mittel(kv, von, bis, spalte):
    """Mittel je Monat im Fenster je Kanal (Monate ohne Upload = 0)."""
    s = kv[kv["rel_monat"].between(von, bis)].groupby("channel_id")[spalte].sum()
    return s / (bis - von + 1)


def main():
    for name, f in {"VOR": VOR, "SPRUNG": SPRUNG, "SPAETER": SPAETER, "MONATE_TABELLE": MONATE_TABELLE}.items():
        if len(f) != 2 or f[0] > f[1]:
            raise SystemExit(f"{name} muss (von, bis) mit von <= bis sein, nicht {f!r}.")
    if not (VOR[1] < SPRUNG[0] and SPRUNG[1] < SPAETER[0]):
        raise SystemExit("Fenster muessen in der Reihenfolge VOR < SPRUNG < SPAETER liegen.")
    AUSGABE.mkdir(parents=True, exist_ok=True)
    k, v = lade()
    out = [f"# Sprung der Views bei „{GRUPPE}“ in Monat 5/6", "",
           f"Erzeugt von `scripts/adhoc/alt_rechts_sprung_m5_m6.py`. Sample wie "
           f"`marktanteil_rohdaten_plots.py` (KANALLISTE, MANUELL_ALT_RECHTS = {mp.MANUELL_ALT_RECHTS}), "
           f"nur long-Videos. {len(k)} Kanäle in der Gruppe. Fenster (rel_monat): VOR {VOR}, "
           f"SPRUNG {SPRUNG}, SPÄTER {SPAETER}; Kanalwerte = mittlere Views je Monat (Monate ohne Upload = 0). "
           "Views = kumulierter Snapshot 2026.", ""]

    # --- 1. Monatsverlauf: Uploads, Views, Views/Video, Median, Top-Video-Anteil
    rows = []
    for m, d in v[v["rel_monat"].between(*MONATE_TABELLE)].groupby("rel_monat"):
        s = d["views"].sort_values(ascending=False)
        rows.append({"monat": m, "kanaele_aktiv": d["channel_id"].nunique(), "uploads": len(d),
                     "views_mio": s.sum() / 1e6, "views_je_video_tsd": s.mean() / 1e3,
                     "median_tsd": s.median() / 1e3,
                     "anteil_top10_videos": s.head(10).sum() / s.sum(),
                     "views_ohne_top10_mio": s.iloc[10:].sum() / 1e6,
                     "anteil_krieg_views": d.loc[d["russia_ukraine_war"] == 1, "views"].sum() / s.sum()})
    monate = pd.DataFrame(rows)
    monate.to_csv(AUSGABE / "monate.csv", index=False)
    out += ["## 1. Monatsverlauf der Gruppe", "",
            md(monate, {"views_mio": "{:.1f}", "views_je_video_tsd": "{:.1f}", "median_tsd": "{:.1f}",
                        "anteil_top10_videos": "{:.0%}", "views_ohne_top10_mio": "{:.1f}",
                        "anteil_krieg_views": "{:.0%}"}), ""]

    # --- 2. Kanalzerlegung
    kv = v.groupby(["channel_id", "rel_monat"]).agg(views=("views", "sum"), uploads=("video_id", "size")).reset_index()
    kt = k.set_index("channel_id")[["kanal_name", "abonnenten", "sample_vorkrieg"]].copy()
    for lab, f in {"vor": VOR, "sprung": SPRUNG, "spaeter": SPAETER}.items():
        kt[f"views_{lab}"] = fenster_mittel(kv, *f, "views")
        kt[f"uploads_{lab}"] = fenster_mittel(kv, *f, "uploads")
    kt = kt.fillna({c: 0 for c in kt.columns if c.startswith(("views_", "uploads_"))})
    kt["delta"] = kt["views_sprung"] - kt["views_vor"]
    kt["delta_spaeter"] = kt["views_spaeter"] - kt["views_vor"]
    kt["faktor"] = np.where(kt["views_vor"] > 0, kt["views_sprung"] / kt["views_vor"], np.nan)
    kt["vpv_vor"] = kt["views_vor"] / kt["uploads_vor"].replace(0, np.nan)
    kt["vpv_sprung"] = kt["views_sprung"] / kt["uploads_sprung"].replace(0, np.nan)
    erstes = v.groupby("channel_id")["rel_monat"].min()
    kt["erster_monat_im_fenster"] = erstes
    kt = kt.sort_values("delta", ascending=False)
    kt.reset_index().to_csv(AUSGABE / "kanaele.csv", index=False)

    gesamt = kt["delta"].sum()
    pos = kt.loc[kt["delta"] > 0, "delta"]
    neu = kt["views_vor"].eq(0) & kt["views_sprung"].gt(0)
    aktiv_beide = (kt["views_vor"] > 0) & (kt["views_sprung"] > 0)
    out += ["## 2. Wer trägt den Anstieg?", "",
            f"- Gesamtanstieg (Mittel je Monat SPRUNG minus VOR): **{gesamt / 1e6:+.1f} Mio.** "
            f"(VOR {kt['views_vor'].sum() / 1e6:.1f} → SPRUNG {kt['views_sprung'].sum() / 1e6:.1f} → "
            f"SPÄTER {kt['views_spaeter'].sum() / 1e6:.1f} Mio. je Monat).",
            f"- Kanäle mit Zuwachs: {int((kt['delta'] > 0).sum())}, mit Rückgang: "
            f"{int((kt['delta'] < 0).sum())}, ohne Videos in beiden Fenstern: "
            f"{int(((kt['views_vor'] == 0) & (kt['views_sprung'] == 0)).sum())}.",
            f"- Anteil am Gesamtanstieg: Top 1 {kt['delta'].head(1).sum() / gesamt:.0%}, "
            f"Top 3 {kt['delta'].head(3).sum() / gesamt:.0%}, Top 5 {kt['delta'].head(5).sum() / gesamt:.0%}, "
            f"Top 10 {kt['delta'].head(10).sum() / gesamt:.0%} (Summe der positiven Zuwächse: "
            f"{pos.sum() / 1e6:.1f} Mio.).",
            f"- Neu gestartete Kanäle (keine Videos in VOR, aber in SPRUNG): {int(neu.sum())} mit "
            f"{kt.loc[neu, 'views_sprung'].sum() / 1e6:.1f} Mio. je Monat.",
            f"- Median-Faktor SPRUNG/VOR über Kanäle mit Videos in beiden Fenstern ({int(aktiv_beide.sum())}): "
            f"{kt.loc[aktiv_beide, 'faktor'].median():.2f}; Anteil mit Faktor > 1,25: "
            f"{(kt.loc[aktiv_beide, 'faktor'] > 1.25).mean():.0%}, > 1,5: "
            f"{(kt.loc[aktiv_beide, 'faktor'] > 1.5).mean():.0%}.",
            f"- Ohne die Top-5-Kanäle: VOR {kt['views_vor'].iloc[5:].sum() / 1e6:.1f} → SPRUNG "
            f"{kt['views_sprung'].iloc[5:].sum() / 1e6:.1f} → SPÄTER {kt['views_spaeter'].iloc[5:].sum() / 1e6:.1f} "
            "Mio. je Monat.", ""]
    zeig = kt.head(TOP_KANAELE).reset_index()[
        ["kanal_name", "sample_vorkrieg", "abonnenten", "views_vor", "views_sprung", "views_spaeter",
         "faktor", "uploads_vor", "uploads_sprung", "vpv_vor", "vpv_sprung", "delta"]].copy()
    zeig["anteil_delta"] = zeig["delta"] / gesamt
    for c in ["views_vor", "views_sprung", "views_spaeter", "delta"]:
        zeig[c] = zeig[c] / 1e6
    for c in ["vpv_vor", "vpv_sprung", "abonnenten"]:
        zeig[c] = zeig[c] / 1e3
    out += [f"### Top {TOP_KANAELE} Kanäle nach absolutem Zuwachs (Views in Mio. je Monat, "
            "Views/Video und Abos in Tsd.)", "",
            md(zeig, {"views_vor": "{:.2f}", "views_sprung": "{:.2f}", "views_spaeter": "{:.2f}",
                      "faktor": "{:.2f}", "uploads_vor": "{:.1f}", "uploads_sprung": "{:.1f}",
                      "vpv_vor": "{:.1f}", "vpv_sprung": "{:.1f}", "delta": "{:+.2f}",
                      "anteil_delta": "{:.0%}", "abonnenten": "{:.0f}"}), "",
            "### Kanäle mit dem größten Rückgang", "",
            md(kt.tail(5).reset_index()[["kanal_name", "views_vor", "views_sprung", "delta"]]
               .assign(views_vor=lambda d: d["views_vor"] / 1e6, views_sprung=lambda d: d["views_sprung"] / 1e6,
                       delta=lambda d: d["delta"] / 1e6),
               {"views_vor": "{:.2f}", "views_sprung": "{:.2f}", "delta": "{:+.2f}"}), ""]

    # --- 3. Uploads vs. Views je Video (Shift-Share)
    U0, U1 = kt["uploads_vor"].sum(), kt["uploads_sprung"].sum()
    V0, V1 = kt["views_vor"].sum(), kt["views_sprung"].sum()
    out += ["## 3. Mehr Videos oder mehr Views je Video?", "",
            f"- Uploads je Monat: {U0:.0f} → {U1:.0f} ({U1 / U0 - 1:+.0%}); Views je Video: "
            f"{V0 / U0 / 1e3:.1f} → {V1 / U1 / 1e3:.1f} Tsd. ({(V1 / U1) / (V0 / U0) - 1:+.0%}).",
            f"- Zerlegung (log): Anteil des Anstiegs aus Upload-Menge "
            f"{np.log(U1 / U0) / np.log(V1 / V0):.0%}, aus Views je Video "
            f"{np.log((V1 / U1) / (V0 / U0)) / np.log(V1 / V0):.0%}.", ""]

    # --- 4. Themen: Views nach Titelthema, VOR vs. SPRUNG
    def fen(m):
        return np.select([m.between(*VOR), m.between(*SPRUNG), m.between(*SPAETER)],
                         ["vor", "sprung", "spaeter"], "")
    v["fenster"] = fen(v["rel_monat"])
    f = v[v["fenster"] != ""]
    n_mon = {"vor": VOR[1] - VOR[0] + 1, "sprung": SPRUNG[1] - SPRUNG[0] + 1, "spaeter": SPAETER[1] - SPAETER[0] + 1}
    themen = [*TOPIC_KEYWORDS, *["rx_" + t for t in REGEX_THEMEN]]
    rows = []
    for t in themen:
        r = {"thema": t}
        for fe in ["vor", "sprung", "spaeter"]:
            d = f[f["fenster"] == fe]
            r[f"anteil_uploads_{fe}"] = d[t].mean()
            r[f"views_{fe}_mio"] = d.loc[d[t] == 1, "views"].sum() / n_mon[fe] / 1e6
        r["delta_mio"] = r["views_sprung_mio"] - r["views_vor_mio"]
        r["anteil_am_gesamtanstieg"] = r["delta_mio"] * 1e6 / gesamt
        rows.append(r)
    keinthema = (f[list(TOPIC_KEYWORDS)].sum(axis=1) == 0)
    r = {"thema": "(kein Stichwortthema)"}
    for fe in ["vor", "sprung", "spaeter"]:
        d = f[(f["fenster"] == fe)]
        kt_ = keinthema[d.index]
        r[f"anteil_uploads_{fe}"] = kt_.mean()
        r[f"views_{fe}_mio"] = d.loc[kt_, "views"].sum() / n_mon[fe] / 1e6
    r["delta_mio"] = r["views_sprung_mio"] - r["views_vor_mio"]
    r["anteil_am_gesamtanstieg"] = r["delta_mio"] * 1e6 / gesamt
    rows.append(r)
    th = pd.DataFrame(rows).sort_values("delta_mio", ascending=False)
    out += ["## 4. Themen (Titel-Stichworte; ein Video kann mehrere Themen haben)", "",
            "`rel_*_cw` = Export-Stichworte, `rx_*` = lokale breitere Regex. Views = mittlere Views je Monat "
            "der Videos mit diesem Thema (Mio.). Anteile am Gesamtanstieg addieren sich wegen Mehrfachzuordnung "
            "nicht zu 100 %.", "",
            md(th[["thema", "anteil_uploads_vor", "anteil_uploads_sprung", "views_vor_mio", "views_sprung_mio",
                   "views_spaeter_mio", "delta_mio", "anteil_am_gesamtanstieg"]],
               {"anteil_uploads_vor": "{:.1%}", "anteil_uploads_sprung": "{:.1%}", "views_vor_mio": "{:.2f}",
                "views_sprung_mio": "{:.2f}", "views_spaeter_mio": "{:.2f}", "delta_mio": "{:+.2f}",
                "anteil_am_gesamtanstieg": "{:.0%}"}), ""]

    # --- 5. Top-Titel der Wachstumskanaele im Sprungfenster + Vergleich VOR
    out += ["## 5. Meistgesehene Titel der größten Wachstumskanäle", ""]
    for cid in kt.head(TOP_KANAELE_TITEL).index:
        d = v[(v["channel_id"] == cid)]
        out += [f"### {kt.loc[cid, 'kanal_name']} (Δ {kt.loc[cid, 'delta'] / 1e6:+.2f} Mio./Monat)", ""]
        for fe, lab in [("sprung", "SPRUNG"), ("vor", "VOR")]:
            dd = d[d["fenster"] == fe].sort_values("views", ascending=False)
            n = TOP_TITEL if fe == "sprung" else 5
            out += [f"**{lab}** ({len(dd)} Videos, Median {dd['views'].median() / 1e3:.0f} Tsd.):", ""]
            out += [f"- {r.upload_ts:%d.%m.%Y} · {r.views / 1e3:,.0f} Tsd. · {str(r.title).strip()}"
                    for r in dd.head(n).itertuples()]
            out += [""]

    # --- 6. Meistgesehene Videos der Gruppe im Sprungfenster
    top = v[v["fenster"] == "sprung"].sort_values("views", ascending=False).head(30)
    out += ["## 6. Die 30 meistgesehenen Videos der Gruppe im SPRUNG-Fenster", "",
            md(top.assign(datum=top["upload_ts"].dt.strftime("%d.%m.%Y"), views_tsd=top["views"] / 1e3,
                          titel=top["title"].str.strip().str[:110])[["datum", "kanal_name", "views_tsd", "titel"]],
               {"views_tsd": "{:,.0f}"}), ""]

    (AUSGABE / "ergebnis.md").write_text("\n".join(out), encoding="utf-8")
    print(f"-> {AUSGABE / 'ergebnis.md'}")


if __name__ == "__main__":
    main()

"""Datenbasierte Kanalklassifikation nach Politikanteil (einmalig, 2026-10-15).

Zweite, von der manuellen Typologie unabhängige Klassifikation aller Kanäle
aus ``data/external/channels.xlsx``: Je Kanal wird der Anteil politischer
Videos gemessen und in drei Klassen eingeteilt.

Maß (Hauptdefinition):
    Anteil der Videos mit YouTube-Themenkategorie "Politics"
    (``video_details.topic_categories`` enthält ``wiki/Politics``) an allen
    Videos mit nicht-leerer Themenkategorie. Videos ohne Kategorie (leere
    Liste) zählen nicht im Nenner, weil "keine Kategorie" nicht "unpolitisch"
    heißt; ihr Anteil wird mit ausgegeben.
    Zeitraum 2021-01-01 bis 2026-07-01 (wie FORMAT_FENSTER im Stata-Export).
Varianten:
    - pol_vor / pol_nach: vor bzw. ab Kriegsbeginn (2022-02-24). Der
      Politikanteil steigt bei manchen Typen (v. a. C1) über die Zeit; für
      eine Gruppierung, die nicht vom Ergebnis abhängt, ist pol_vor die
      richtige Basis (Klasse ``pol_klasse_vor``).
    - pol_long: nur Videos mit format == "long" (video_format).
    - pol_kw: Validierung mit den Titel-Keyword-Topics
      (video_topic_relevance, irgendein Topic relevant). Nur für Kanäle, bei
      denen >= 80 % der Videos dort klassifiziert sind.
Klassen (feste Schwellen, vorab gesetzt):
    politisch  >= 0.50 | teilpolitisch 0.20-0.50 | unpolitisch < 0.20
    Kanäle mit < 30 kategorisierten Videos im jeweiligen Zeitraum: keine
    Klasse (zu unsicher).

Ausgabe:
    scripts/adhoc/outputs/kanal_politikanteil.csv
    scripts/adhoc/outputs/kanal_politikanteil.md (Verteilung, Validierung,
        Abweichungen zur manuellen Typologie)
Die Werte in channels.xlsx (Spalten pol_*) wurden aus der CSV übernommen.

Laufzeit: ca. 10-15 min (Joins über die Video-Registry).
Aufruf:  python scripts/adhoc/kanal_politikanteil.py
"""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "data" / "store" / "video_registry.sqlite"
CHANNELS_XLSX = ROOT / "data" / "external" / "channels.xlsx"
OUT_DIR = ROOT / "scripts" / "adhoc" / "outputs"
OUT_CSV = OUT_DIR / "kanal_politikanteil.csv"
OUT_MD = OUT_DIR / "kanal_politikanteil.md"

START, ENDE, KRIEG = "2021-01-01", "2026-07-01", "2022-02-24"
SCHWELLEN = (0.20, 0.50)
MIN_N = 30
MIN_KW_ABDECKUNG = 0.80


def klasse(anteil, n):
    if pd.isna(anteil) or n < MIN_N:
        return None
    if anteil >= SCHWELLEN[1]:
        return "politisch"
    if anteil >= SCHWELLEN[0]:
        return "teilpolitisch"
    return "unpolitisch"


def lade_kanaele():
    x = pd.read_excel(CHANNELS_XLSX)
    x = x[x["Column1"] != "channel_id"]
    return x.rename(columns={"Column1": "channel_id", "Column2": "kanal_name",
                             "Column3": "typ_code"})[["channel_id", "kanal_name", "typ_code"]]


def politik_aggregate(con):
    """Je Kanal x Periode (vor/nach) und Format: Videos, kategorisiert, Politics."""
    q = f"""
    select v.channel_id,
           case when v.published_at < '{KRIEG}' then 'vor' else 'nach' end as periode,
           coalesce(f.format, 'unbekannt') as format,
           count(*) as n_videos,
           sum(d.topic_categories is not null and d.topic_categories not in ('', '[]')) as n_kat,
           sum(d.topic_categories like '%wiki/Politics%') as n_pol
    from videos v
    join ch on ch.id = v.channel_id
    join video_details d on d.video_id = v.video_id
    left join video_format f on f.video_id = v.video_id
    where v.published_at >= '{START}' and v.published_at < '{ENDE}'
    group by 1, 2, 3
    """
    return pd.read_sql(q, con)


def keyword_aggregate(con):
    """Je Kanal: Videos im Zeitraum, davon Keyword-klassifiziert, davon irgendein Topic relevant."""
    q = f"""
    with r as (select video_id, max(is_relevant) as rel from video_topic_relevance group by video_id)
    select v.channel_id, count(*) as n_videos, count(r.video_id) as n_kw, sum(r.rel) as n_kw_rel
    from videos v
    join ch on ch.id = v.channel_id
    left join r on r.video_id = v.video_id
    where v.published_at >= '{START}' and v.published_at < '{ENDE}'
    group by 1
    """
    return pd.read_sql(q, con)


def anteil(df, maske):
    t = df[maske].groupby("channel_id")[["n_kat", "n_pol", "n_videos"]].sum()
    return t["n_pol"] / t["n_kat"].replace(0, np.nan), t["n_kat"], t["n_videos"]


def main():
    kan = lade_kanaele()
    con = sqlite3.connect(REGISTRY)
    con.execute("create temp table ch(id text primary key)")
    con.executemany("insert into ch values (?)", [(i,) for i in kan["channel_id"]])

    agg = politik_aggregate(con)
    kw = keyword_aggregate(con)

    alle = agg["periode"].notna()
    res = pd.DataFrame(index=kan["channel_id"])
    res["pol"], res["n_kat"], res["n_videos"] = anteil(agg, alle)
    res["anteil_ohne_kat"] = 1 - res["n_kat"] / res["n_videos"]
    res["pol_vor"], res["n_kat_vor"], _ = anteil(agg, agg["periode"] == "vor")
    res["pol_nach"], res["n_kat_nach"], _ = anteil(agg, agg["periode"] == "nach")
    res["pol_long"], res["n_kat_long"], _ = anteil(agg, agg["format"] == "long")
    kw = kw.set_index("channel_id")
    res["kw_abdeckung"] = kw["n_kw"] / kw["n_videos"]
    res["pol_kw"] = (kw["n_kw_rel"] / kw["n_kw"]).where(res["kw_abdeckung"] >= MIN_KW_ABDECKUNG)
    for c in ["n_kat", "n_kat_vor", "n_kat_nach", "n_kat_long"]:
        res[c] = res[c].fillna(0).astype(int)
    res["pol_klasse"] = [klasse(a, n) for a, n in zip(res["pol"], res["n_kat"])]
    res["pol_klasse_vor"] = [klasse(a, n) for a, n in zip(res["pol_vor"], res["n_kat_vor"])]

    out = kan.merge(res, left_on="channel_id", right_index=True, how="left")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.round(3).to_csv(OUT_CSV, index=False, encoding="utf-8")
    schreibe_bericht(out)
    print(f"{len(out)} Kanäle -> {OUT_CSV}\nBericht -> {OUT_MD}")


def md_tabelle(df):
    df = df.copy()
    kopf = "| " + " | ".join(map(str, df.columns)) + " |"
    trenn = "|" + "---|" * len(df.columns)
    zeilen = ["| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([kopf, trenn, *zeilen])


def schreibe_bericht(out):
    gruppe = out["typ_code"].str[0].map({"A": "A", "B": "B", "C": "C"})
    erwartet = gruppe.map({"A": None, "B": "politisch", "C": "unpolitisch"})

    vert = (out.groupby("typ_code")["pol"].describe(percentiles=[.25, .5, .75])
            [["count", "25%", "50%", "75%"]].round(2).reset_index())
    kreuz = pd.crosstab(out["typ_code"], out["pol_klasse"].fillna("zu wenig Daten")).reset_index()
    kreuz_vor = pd.crosstab(out["typ_code"], out["pol_klasse_vor"].fillna("zu wenig Daten / nach 2022")).reset_index()

    v = out.dropna(subset=["pol", "pol_kw"])
    r_kw = v["pol"].corr(v["pol_kw"], method="spearman")
    v2 = out.dropna(subset=["pol", "pol_long"])
    r_long = v2["pol"].corr(v2["pol_long"], method="spearman")
    v3 = out.dropna(subset=["pol_vor", "pol_nach"])
    r_zeit = v3["pol_vor"].corr(v3["pol_nach"], method="spearman")

    spalten = ["kanal_name", "typ_code", "n_kat", "pol", "pol_vor", "pol_nach", "pol_kw", "pol_klasse"]
    c_pol = out[(gruppe == "C") & out["pol_klasse"].isin(["politisch", "teilpolitisch"])]
    b_unpol = out[(gruppe == "B") & out["pol_klasse"].isin(["unpolitisch", "teilpolitisch"])]
    anstieg = out[(out["pol_nach"] - out["pol_vor"] >= 0.30) & (out["n_kat_vor"] >= MIN_N)]

    teile = [
        "# Kanalklassifikation nach Politikanteil (2026-10-15)",
        "",
        "Erzeugt von `scripts/adhoc/kanal_politikanteil.py`. Maß: Anteil der Videos mit YouTube-Themenkategorie "
        f"\"Politics\" an allen kategorisierten Videos, {START} bis {ENDE}. Klassen: politisch ≥ {SCHWELLEN[1]:.0%}, "
        f"teilpolitisch {SCHWELLEN[0]:.0%}–{SCHWELLEN[1]:.0%}, unpolitisch < {SCHWELLEN[0]:.0%}; "
        f"keine Klasse bei < {MIN_N} kategorisierten Videos.",
        "",
        "## Validierung",
        f"- Spearman Politics-Anteil vs. Titel-Keyword-Topics (n = {len(v)} Kanäle mit ≥ 80 % Keyword-Abdeckung): **{r_kw:.2f}**",
        f"- Spearman alle Videos vs. nur Long-Videos (n = {len(v2)}): **{r_long:.2f}**",
        f"- Spearman vor vs. ab Kriegsbeginn (n = {len(v3)}): **{r_zeit:.2f}**",
        f"- Median Anteil Videos ohne Themenkategorie: {out['anteil_ohne_kat'].median():.0%} "
        f"(max. {out['anteil_ohne_kat'].max():.0%})",
        "",
        "## Politikanteil nach manuellem Typ",
        md_tabelle(vert),
        "",
        "## Klasse (Gesamtzeitraum) nach manuellem Typ",
        md_tabelle(kreuz),
        "",
        "## Klasse (nur vor Kriegsbeginn) nach manuellem Typ",
        md_tabelle(kreuz_vor),
        "",
        f"## C-Kanäle mit Klasse politisch/teilpolitisch ({len(c_pol)})",
        md_tabelle(c_pol.sort_values("pol", ascending=False)[spalten].round(2)),
        "",
        f"## B-Kanäle mit Klasse unpolitisch/teilpolitisch ({len(b_unpol)})",
        md_tabelle(b_unpol.sort_values("pol")[spalten].round(2)),
        "",
        f"## Kanäle mit Anstieg ≥ 30 Prozentpunkte nach Kriegsbeginn ({len(anstieg)})",
        md_tabelle(anstieg.assign(diff=anstieg["pol_nach"] - anstieg["pol_vor"])
                   .sort_values("diff", ascending=False)[spalten + ["diff"]].round(2)),
    ]
    OUT_MD.write_text("\n".join(teile) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

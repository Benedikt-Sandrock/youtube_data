"""Einmalige Übersicht: Wie stark sind die Kanäle der Typ-Gruppen (A/B/C aus
kanal_typologie.csv) auf den Ukraine-Krieg eingestiegen? Anzahl und Anteil der
Kriegsvideos (Titel-Stichwort, core bzw. core+wide) im ersten Kriegsjahr
(24.02.2022–23.02.2023), nur Long-Videos (format == "long"; ersetzt die veraltete
181-s-Regel min_dauer). Gelöschte Kanäle ohne Formatzuordnung haben dadurch 0 Videos.
Zusätzlich `n Krieg gesamt` (core) und `n Krieg gesamt cw` (core+wide): Kriegsvideos ab
Kriegsbeginn bis Datenende.
Aufruf: python scripts/adhoc/typen_krieg_anteil.py
Output (scripts/adhoc/outputs/):
  typ_<A|B|C>_krieg_anteil.md   Verteilung je Typ + Kanaltabellen pro Gruppe
  typen_krieg_anteil.csv        alle Kanäle aller Typen in einer Tabelle
                                (Semikolon, Dezimalkomma, UTF-8 mit BOM für Excel)
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "scripts/adhoc/outputs"
t = pd.read_csv(ROOT / "data/external/kanal_typologie.csv")
k = pd.read_stata(ROOT / "outputs/stata_rohdaten/kanaele_roh.dta",
                  columns=["channel_id", "ideo_gesellschaft_baseline", "pop_baseline"],
                  convert_categoricals=False)
v = pd.read_stata(ROOT / "outputs/stata_rohdaten/videos_roh.dta",
                  columns=["channel_id", "upload_ts", "format",
                           "rel_russia_ukraine_war_core", "rel_russia_ukraine_war_cw"],
                  convert_categoricals=False)
v = v[(v.format == "long") & v.channel_id.isin(t.channel_id)]
start, ende = pd.Timestamp("2022-02-24"), pd.Timestamp("2023-02-24")
j1 = v[(v.upload_ts >= start) & (v.upload_ts < ende)]
q1 = j1[j1.upload_ts < pd.Timestamp("2022-05-24")]
nach = v[v.upload_ts >= start]
datenende = nach.upload_ts.max().strftime("%d.%m.%Y")

agg = j1.groupby("channel_id").agg(n_j1=("upload_ts", "size"),
                                   n_krieg_core=("rel_russia_ukraine_war_core", "sum"),
                                   n_krieg_cw=("rel_russia_ukraine_war_cw", "sum"),
                                   krieg_core=("rel_russia_ukraine_war_core", "mean"),
                                   krieg_cw=("rel_russia_ukraine_war_cw", "mean"))
agg = agg.join(q1.groupby("channel_id").agg(n_3m=("upload_ts", "size"),
                                            n_krieg_core_3m=("rel_russia_ukraine_war_core", "sum"),
                                            krieg_core_3m=("rel_russia_ukraine_war_core", "mean")))
agg = agg.join(nach.groupby("channel_id").agg(
    n_krieg_core_gesamt=("rel_russia_ukraine_war_core", "sum"),
    n_krieg_cw_gesamt=("rel_russia_ukraine_war_cw", "sum")), how="outer")
d = t.merge(agg, on="channel_id", how="left").merge(k, on="channel_id", how="left")
for c in ["n_j1", "n_krieg_core", "n_krieg_cw", "n_3m", "n_krieg_core_3m",
          "n_krieg_core_gesamt", "n_krieg_cw_gesamt"]:
    d[c] = d[c].fillna(0).astype(int)
for c in ["krieg_core", "krieg_cw", "krieg_core_3m"]:
    d[c] = d[c] * 100
d = d.sort_values(["typ_code", "krieg_core"], ascending=[True, False])

SPALTEN = {"kanal_name": "Kanal", "subtyp": "subtyp", "n_j1": "n Jahr 1",
           "n_krieg_core": "n Krieg core", "krieg_core": "Krieg % core",
           "n_krieg_cw": "n Krieg cw", "krieg_cw": "Krieg % cw",
           "n_3m": "n 3M", "krieg_core_3m": "3M % core",
           "n_krieg_core_gesamt": "n Krieg gesamt", "n_krieg_cw_gesamt": "n Krieg gesamt cw",
           "ideo_gesellschaft_baseline": "Ideo", "pop_baseline": "Pop"}


def md(df, index=True):
    if index:
        df = df.reset_index()
    rows = [[("" if pd.isna(x) else str(x)) for x in r] for r in df.itertuples(index=False)]
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "---|" * len(df.columns)
    return "\n".join([head, sep] + ["| " + " | ".join(r) + " |" for r in rows])


for gruppe in ["A", "B", "C"]:
    dg = d[d.typ_code.str.startswith(gruppe)]
    out = [f"# {gruppe}-Typen: Kriegsvideos im ersten Kriegsjahr", "",
           "Kriegsvideo = Titel-Treffer `rel_russia_ukraine_war_core` (cw = core+wide). "
           "Zeitraum 24.02.2022–23.02.2023, nur Long-Videos (`format == \"long\"`; Shorts und "
           "Livestreams ausgeschlossen). `n Krieg` = Anzahl, `%` = Anteil an `n Jahr 1`. "
           "`3M` = erste drei Kriegsmonate (Nenner `n 3M`). "
           f"`n Krieg gesamt` = Kriegsvideos (core) im gesamten Zeitraum ab Kriegsbeginn "
           f"(24.02.2022–{datenende}), `n Krieg gesamt cw` dasselbe mit core+wide. "
           "Ideo = `ideo_gesellschaft_baseline` (−2 progressiv … +2 konservativ).", "",
           "## Verteilung je Typ (Kanäle mit ≥ 10 Videos im Kriegsjahr)", ""]
    tab = dg[dg.n_j1 >= 10].groupby("typ_code").krieg_core.describe(
        percentiles=[.25, .5, .75])[["count", "min", "25%", "50%", "75%", "max"]].round(1)
    out += [md(tab), "", "## Kanäle", ""]
    for code, g in dg.groupby("typ_code", sort=True):
        out += [f"### {code} – {g.typ.iloc[0]}", "",
                md(g[list(SPALTEN)].rename(columns=SPALTEN).round(1), index=False), ""]
    (OUT / f"typ_{gruppe}_krieg_anteil.md").write_text("\n".join(out), encoding="utf-8")

csv = d[["channel_id", "typ_code", "typ", "medientyp_label"] + list(SPALTEN)].rename(
    columns=SPALTEN).round(2)
csv.to_csv(OUT / "typen_krieg_anteil.csv", sep=";", decimal=",", index=False,
           encoding="utf-8-sig")
print("geschrieben: typ_A/B/C_krieg_anteil.md, typen_krieg_anteil.csv")

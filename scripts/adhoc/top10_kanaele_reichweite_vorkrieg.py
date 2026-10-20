"""Top-10-Kanäle je Medientyp nach Reichweite vor Kriegsbeginn.

Grundgesamtheit: Kanäle mit ``sample_whitelist == "ja"`` (ohne die Einschränkung
landen unpolitische Kanäle wie Gronkh, TOGGO oder Nickelodeon oben).

Reichweite (Rangkriterium) = Summe der kumulierten, zum Abrufzeitpunkt
gemessenen Views aller politischen Long-Videos (``format == "long"``,
``politisch == "ja"``), die vor dem 24.02.2022 hochgeladen wurden. Das Fenster
beginnt mit dem Datensatz am 01.01.2021 (knapp 14 Monate). Die Views aller
Long-Videos, Shorts und Livestreams werden zur Einordnung mit ausgewiesen.

Medientypen: ÖRR, traditionelle Medien, Creator & alternative Medien
(Partei/Politiker bleibt außen vor).

Quelle: ``outputs/stata_rohdaten/videos_roh.dta`` + ``kanaele_roh.dta``.
Ausgabe: ``scripts/adhoc/outputs/top10_kanaele_reichweite_vorkrieg.{md,csv}``.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
ROH = ROOT / "outputs" / "stata_rohdaten"
OUT = ROOT / "scripts" / "adhoc" / "outputs"
KRIEGSBEGINN = pd.Timestamp("2022-02-24")
TOP_N = 10
MEDIENTYPEN = ["ÖRR", "traditionelle Medien", "Creator & alternative Medien"]

k = pd.read_stata(ROH / "kanaele_roh.dta")
v = pd.read_stata(ROH / "videos_roh.dta",
                  columns=["channel_id", "upload_ts", "format", "views", "politisch"])
for d in (k, v):
    for c in d.select_dtypes("category"):
        d[c] = d[c].astype(str).str.replace("�", "Ö")

vor = v[v["upload_ts"] < KRIEGSBEGINN]
long_ = vor[vor["format"] == "long"]
pol = long_[long_["politisch"] == "ja"]
agg = pd.DataFrame({
    "views_pol": pol.groupby("channel_id")["views"].sum(),
    "n_pol": pol.groupby("channel_id").size(),
    "views_long": long_.groupby("channel_id")["views"].sum(),
    "n_long": long_.groupby("channel_id").size(),
    "views_short": vor[vor["format"] == "short"].groupby("channel_id")["views"].sum(),
    "views_live": vor[vor["format"] == "live"].groupby("channel_id")["views"].sum(),
}).fillna(0).reset_index()

df = k[k["sample_whitelist"] == "ja"].merge(agg, on="channel_id", how="left").fillna(
    {c: 0 for c in agg.columns if c != "channel_id"})
df["anteil_pol"] = df["n_pol"] / df["n_long"].where(df["n_long"] > 0)

spalten = {
    "kanal_name": "Kanal", "kanaltyp": "Kanaltyp",
    "views_pol": "Views pol. Long", "n_pol": "pol. Long-Videos",
    "views_long": "Views alle Long", "anteil_pol": "Anteil pol.",
    "views_short": "Views Shorts", "views_live": "Views Live",
    "abonnenten": "Abonnenten (heute)", "sample_kern": "Kern",
    "api_abbruch": "API-Abbruch", "format_status": "Format-Status",
}
zahlen = ["Views pol. Long", "pol. Long-Videos", "Views alle Long",
          "Views Shorts", "Views Live", "Abonnenten (heute)"]

OUT.mkdir(parents=True, exist_ok=True)
teile = []
md = ["# Top-10-Kanäle je Medientyp nach Reichweite vor Kriegsbeginn", "",
      "Grundgesamtheit: Whitelist-Kanäle (`sample_whitelist == ja`). Ranking nach "
      "der Summe der Views politischer Long-Videos (`format == \"long\"`, "
      "`politisch == ja`), hochgeladen 01.01.2021–23.02.2022. Views sind kumuliert "
      "zum Abrufzeitpunkt, nicht zum Kriegsbeginn.", ""]
for mt in MEDIENTYPEN:
    top = (df[df["medientyp"] == mt].sort_values("views_pol", ascending=False)
           .head(TOP_N).copy())
    top.insert(0, "Rang", range(1, len(top) + 1))
    top.insert(1, "Medientyp", mt)
    teile.append(top[["Rang", "Medientyp", "channel_id", *spalten]])
    t = top[["Rang", *spalten]].rename(columns=spalten)
    for c in zahlen:
        t[c] = t[c].map(lambda x: f"{x:,.0f}".replace(",", "."))
    t["Anteil pol."] = t["Anteil pol."].map(lambda x: "" if pd.isna(x) else f"{x:.0%}")
    t = t.astype(str).replace({"nan": "", "None": ""})
    md += [f"## {mt}", "", "| " + " | ".join(t.columns) + " |",
           "|" + "---|" * len(t.columns),
           *("| " + " | ".join(r) + " |" for r in t.values), ""]

pd.concat(teile).rename(columns=spalten).to_csv(
    OUT / "top10_kanaele_reichweite_vorkrieg.csv", index=False, encoding="utf-8-sig")
(OUT / "top10_kanaele_reichweite_vorkrieg.md").write_text("\n".join(md), encoding="utf-8")
print("\n".join(md))

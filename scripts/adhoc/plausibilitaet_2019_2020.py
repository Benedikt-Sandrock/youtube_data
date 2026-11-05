# -*- coding: utf-8 -*-
"""
plausibilitaet_2019_2020.py

Plausibilitaetschecks fuer die Datenbasis-Erweiterung 2019-2020
(.claude/plans/datenbasis_2019_2020.md, Schritte 3 und 4):
  1. Trefferquote je Thema und Jahr (video_topic_relevance, nur Kanaele der
     Sample-/Pilotliste). Erwartung: corona_pandemic ab 2020 breit,
     russia_ukraine_war 2019-2020 selten.
  2. Videos pro Kanal und Jahr (2019, 2020, 2021) aus `videos`; Kanaele mit
     0 Videos in 2019+2020 trotz Videos in 2021 werden gelistet.
Schreibt nur einen Markdown-Report.

Ausfuehren aus dem Repo-Root:
    PYTHONPATH=src .venv/Scripts/python.exe scripts/adhoc/plausibilitaet_2019_2020.py
"""
import sqlite3

import pandas as pd

from youtube_code.config import CHANNEL_LISTS, DATA, OUTPUTS

# =========================================================
# KONFIGURATION
# =========================================================
# Kanallisten (Spalte channel_id)
KANALLISTEN = [CHANNEL_LISTS / "video_formats" / "sample_2019_2020.csv",
               CHANNEL_LISTS / "video_formats" / "pilot_2019_2020.csv"]
REGISTRY = DATA / "store" / "video_registry.sqlite"
AUSGABE = OUTPUTS / "video_formats" / "plausibilitaet_2019_2020.md"
# Jahre der Auswertung
JAHRE = ["2019", "2020", "2021"]


def md(df):
    """DataFrame als Markdown-Tabelle (ohne tabulate-Abhaengigkeit)."""
    df = df.reset_index()
    k = [str(c) for c in df.columns]
    z = ["| " + " | ".join(k) + " |", "|" + "---|" * len(k)]
    z += ["| " + " | ".join(str(x) for x in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(z)


def main():
    ids = pd.concat([pd.read_csv(p, usecols=["channel_id"]) for p in KANALLISTEN])["channel_id"].drop_duplicates()
    con = sqlite3.connect(REGISTRY)
    con.execute("create temp table k(channel_id text primary key)")
    con.executemany("insert into k values (?)", [(c,) for c in ids])
    v = pd.read_sql("select v.video_id, v.channel_id, substr(v.published_at,1,4) jahr from videos v "
                    "join k using(channel_id) where substr(v.published_at,1,4) between '2019' and '2021'", con)
    t = pd.read_sql("select t.video_id, t.topic, t.is_relevant from video_topic_relevance t "
                    "join videos v using(video_id) join k using(channel_id) "
                    "where substr(v.published_at,1,4) between '2019' and '2021'", con)
    t = t.merge(v[["video_id", "jahr"]], on="video_id")
    quote = (t.groupby(["topic", "jahr"])["is_relevant"].mean().mul(100).round(1).unstack("jahr"))
    n_jahr = v.groupby("jahr").size()
    pro_kanal = v.groupby(["channel_id", "jahr"]).size().unstack(fill_value=0).reindex(ids, fill_value=0)
    pro_kanal = pro_kanal.reindex(columns=JAHRE, fill_value=0)
    luecke = pro_kanal[(pro_kanal["2019"] + pro_kanal["2020"] == 0) & (pro_kanal["2021"] > 0)]
    titel = pd.read_sql("select channel_id, max(channel_title) t from videos join k using(channel_id) group by channel_id", con).set_index("channel_id")["t"]

    out = ["# Plausibilitaet Datenbasis 2019-2020", "",
           "## Videos pro Jahr (Sample + Pilot)", "", md(n_jahr.to_frame("n_videos")), "",
           "## Trefferquote je Thema und Jahr (% is_relevant)", "", md(quote), "",
           f"## Kanaele mit 0 Videos in 2019+2020, aber Videos 2021 ({len(luecke)})", ""]
    for cid, r in luecke.iterrows():
        out.append(f"- `{cid}` {titel.get(cid, '')} (2021: {r['2021']})")
    out += ["", "## Kanaele ohne jedes Video 2019-2021", ""]
    out += [f"- `{c}` {titel.get(c, '')}" for c in pro_kanal[pro_kanal.sum(axis=1) == 0].index]
    out += ["", "## Verteilung Videos je Kanal und Jahr", "", md(pro_kanal.describe().round(1))]
    AUSGABE.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Report: {AUSGABE}")


if __name__ == "__main__":
    main()

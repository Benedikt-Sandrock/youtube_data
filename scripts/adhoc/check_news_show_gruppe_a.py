# -*- coding: utf-8 -*-
"""
check_news_show_gruppe_a.py

Prueft die Sendungs-Titelmuster aus
`src/youtube_code/step3_topic_relevance/news_show_patterns.py` fuer die 10
Kanaele aus Gruppe A (Plan `.claude/plans/news_show_gruppe_a.md`, Kanalliste
`data/channel_lists/video_formats/weitere_kanaele.csv`).

Datenbasis: `outputs/stata_rohdaten/videos_roh.dta` (nur video_id, channel_id,
titel, format, dauer_sek, upload_ts, views, pop_klass, min_dauer). Die Datei
wird einmal in Chunks gelesen (wenig Arbeitsspeicher, dauert einige Minuten)
und fuer die 10 Kanaele nach `scripts/adhoc/outputs/news_show_gruppe_a_titel.pkl`
gecacht. `--refresh` liest die .dta neu (z.B. nach einem Neu-Export).

Ausgabe: `scripts/adhoc/outputs/news_show_gruppe_a_check.md`, je Kanal:
- Treffer NEWS/SPECIAL/PRESSE nach format (short/long/live) und
  Dauer-Quartile der Treffer
- 15 zufaellige Treffer je Kategorie (long, min_dauer == 1) und bis zu 15
  Treffer bei Shorts (Teaser-Check)
- 15 zufaellige Nicht-Treffer mit Sendungsnamen-Fragmenten (False Negatives)
- unmarkierte Shorts mit Mehr-Themen-Trennern (moegliche Teaser-Luecken)

`--transkripte` haengt fuer die Kanaele mit Transkript-Stichprobe (Tichy,
NIUS, Reichelt, Meinungsmache "NEWS:") je 8 zufaellige NEWS-Treffer mit
den ersten ca. 2.000 Zeichen des Transkripts an (transcript_store).

Ausfuehren aus dem Repo-Root:
    PYTHONPATH=src .venv/Scripts/python.exe scripts/adhoc/check_news_show_gruppe_a.py [--refresh] [--transkripte]
"""

import argparse
import re

import pandas as pd

from youtube_code.config.paths import OUTPUTS, ROOT
from youtube_code.step3_topic_relevance.news_show_patterns import (
    NEWS, PRESSE, SPECIAL, PATTERN_VERSION, classify_frame,
)

DTA = OUTPUTS / "stata_rohdaten" / "videos_roh.dta"
OUT_DIR = ROOT / "scripts" / "adhoc" / "outputs"
CACHE = OUT_DIR / "news_show_gruppe_a_titel.pkl"
REPORT = OUT_DIR / "news_show_gruppe_a_check.md"
SPALTEN = ["video_id", "channel_id", "titel", "format", "dauer_sek", "upload_ts",
           "views", "pop_klass", "min_dauer"]
SEED = 42
N = 15

# channel_id -> (Name, Regex fuer Sendungsnamen-Fragmente fuer die
# False-Negative-Stichprobe, Transkript-Stichprobe ja/nein)
KANAELE = {
    "UCv1WDP5EiipMQ__C4Cg6aow": ("Jung & Naiv", r"bpk|regpk|pressekonferenz|briefing", False),
    "UCB37CFICVTUlewYdbMSChIA": ("Tichys Einblick", r"wecker|\bte\b", True),
    "UCQGqiGhMjc_p4lZEhSTb12g": ("NIUS", r"nius live|schlagzeilen|breaking|vom \d|am \d", True),
    "UCcoQ3WG2J_Xjwwyt-sJqh-w": ("Achtung, Reichelt!", r"reichelt", True),
    "UCOOc_k7pKmmjq8qtGLjBW5A": ("Meinungsmache", r"news|spe[cz]ial|vom \d", True),
    "UC4qhj5cnX0MkbwXQ5vlI1NQ": ("Kronen Zeitung", r"\+|news|show|krone\.tv", False),
    "UCPhsnKyNcH3huafz_wNG_5A": ("hessenschau", r"hessenschau|extra|spezial", False),
    "UCjhkuC_Pi85wGjnB0I1ydxw": ("extra 3", r"extra 3|spezial|teil \d", False),
    "UCbh5D3EdIHP4YQA5X-eK1ug": ("Deutscher Bundestag", r"sitzung|fragestunde|befragung|debatte", False),
    "UC_dZp8bZipnjntBGLVHm6rw": ("AfD-Fraktion Bundestag", r"bundestag live|sitzung|befragung|live", False),
}
# Mehr-Themen-Trenner fuer den Teaser-Check bei Shorts
TRENNER = re.compile(r"\+\+|\s\+\s|•|\|.*\||,.*&|\s&\s.*,", re.IGNORECASE)


def lade():
    if CACHE.exists():
        return pd.read_pickle(CACHE)
    teile = []
    with pd.read_stata(DTA, columns=SPALTEN, convert_categoricals=False, chunksize=100_000) as reader:
        for chunk in reader:
            teile.append(chunk[chunk["channel_id"].isin(KANAELE)])
    v = pd.concat(teile, ignore_index=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    v.to_pickle(CACHE)
    return v


def md_tabelle(df):
    if df.empty:
        return "_keine_\n"
    df = df.copy()
    for c in df.columns:
        df[c] = df[c].astype(str).str.replace("|", "\\|", regex=False)
    zeilen = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    zeilen += ["| " + " | ".join(r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(zeilen) + "\n"


def beispiele(df, n=N):
    df = df.sample(min(n, len(df)), random_state=SEED) if len(df) > n else df
    out = df.sort_values("upload_ts")[["upload_ts", "format", "dauer_sek", "titel"]].copy()
    out["upload_ts"] = out["upload_ts"].dt.date
    out["dauer_min"] = (out.pop("dauer_sek") / 60).round(1)
    return md_tabelle(out[["upload_ts", "format", "dauer_min", "titel"]])


def transkript_anfang(video_ids, n_zeichen=2000):
    from youtube_code.store import transcript_store
    tr = transcript_store.get_transcripts(video_ids)
    out = {}
    for vid, d in tr.items():
        seg = d.get("transcript_segments")
        if isinstance(seg, str):
            text = seg
        elif isinstance(seg, list):
            text = " ".join(s.get("text", "") if isinstance(s, dict) else str(s) for s in seg)
        else:
            text = ""
        if text:
            out[vid] = text[:n_zeichen]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--transkripte", action="store_true")
    args = ap.parse_args()
    if args.refresh and CACHE.exists():
        CACHE.unlink()

    v = lade()
    v["kat"] = classify_frame(v, title_col="titel").fillna("-")
    v["format"] = v["format"].replace("", "leer").fillna("leer")

    md = [f"# Prüfung news_show-Muster Gruppe A\n",
          f"PATTERN_VERSION {PATTERN_VERSION}, {len(v)} Videos der 10 Kanäle aus `videos_roh.dta`.\n"]
    gesamt = pd.crosstab(v["channel_id"].map(lambda c: KANAELE[c][0]), v["kat"])
    md += ["## Übersicht (alle Formate)\n", md_tabelle(gesamt.reset_index().rename(columns={"channel_id": "Kanal"}))]

    for cid, (name, fragmente, mit_tr) in KANAELE.items():
        k = v[v["channel_id"] == cid]
        md.append(f"\n## {name} (`{cid}`, {len(k)} Videos)\n")
        md.append(md_tabelle(pd.crosstab(k["format"], k["kat"], margins=True).reset_index()))
        treffer = k[k["kat"] != "-"]
        if not treffer.empty:
            q = treffer.groupby(["kat", "format"])["dauer_sek"].describe()[["count", "25%", "50%", "75%"]]
            q[["25%", "50%", "75%"]] = (q[["25%", "50%", "75%"]] / 60).round(1)
            md += ["\nDauer der Treffer (Minuten):\n", md_tabelle(q.reset_index())]
        for kat in (NEWS, SPECIAL, PRESSE):
            t = k[(k["kat"] == kat) & (k["format"] == "long") & (k["min_dauer"] == 1)]
            if len(t):
                md += [f"\n### Treffer {kat} (long, min_dauer = 1), n = {len(t)}\n", beispiele(t)]
            s = k[(k["kat"] == kat) & (k["format"] == "short")]
            if len(s):
                md += [f"\n### Treffer {kat} (Shorts), n = {len(s)}\n", beispiele(s)]
        fn = k[(k["kat"] == "-") & k["titel"].str.contains(fragmente, case=False, regex=True, na=False)]
        md += [f"\n### Nicht-Treffer mit Fragment `{fragmente}`, n = {len(fn)}\n", beispiele(fn)]
        sh = k[(k["kat"] == "-") & (k["format"] == "short") & k["titel"].str.contains(TRENNER, na=False)]
        md += [f"\n### Unmarkierte Shorts mit Mehr-Themen-Trennern, n = {len(sh)}\n", beispiele(sh)]

        if args.transkripte and mit_tr:
            t = k[(k["kat"] == NEWS) & (k["format"] == "long") & (k["min_dauer"] == 1)]
            t = t.sample(min(8, len(t)), random_state=SEED)
            texte = transkript_anfang(t["video_id"].tolist())
            md.append(f"\n### Transkript-Stichprobe ({len(texte)} von {len(t)} mit Transkript)\n")
            for r in t.itertuples():
                if r.video_id in texte:
                    md.append(f"\n**{r.upload_ts.date()} · {r.dauer_sek / 60:.0f} min · {r.titel}** (`{r.video_id}`)\n\n"
                              f"> {texte[r.video_id]}\n")

    REPORT.write_text("\n".join(md), encoding="utf-8")
    print(f"geschrieben: {REPORT}")
    print(gesamt.to_string())


if __name__ == "__main__":
    main()

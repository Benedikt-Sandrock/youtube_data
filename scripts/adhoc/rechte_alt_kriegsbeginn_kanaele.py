"""
Übersicht rechter alternativer Kanäle in den ersten drei Kriegsmonaten
(24.02.–23.05.2022) zum manuellen Sichten einzelner Videos.

Auswahl: medientyp == 4 und ideo_gesellschaft_baseline >= 0,5 (= Gruppe
"Alternative (rechts)" in supply_reaction.do), nur format == "long",
mind. 5 Long-Videos im Fenster. Themen-Anteile aus rel_*_cw (Titel, binär,
hier nicht anteilig gewichtet).

Ausgabe: scripts/adhoc/outputs/rechte_alt_kriegsbeginn_kanaele.md
- Tabelle aller Kanäle, sortiert nach Views im Fenster
- je Kanal der Top-Liste die meistgesehenen Videos + meistgesehene
  Kriegsvideos im Fenster, mit Link

Ausführen aus dem Repo-Root:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/adhoc/rechte_alt_kriegsbeginn_kanaele.py
"""

from pathlib import Path

import pandas as pd

from youtube_code.config import OUTPUTS

PFAD_ROH = OUTPUTS / "stata_rohdaten"
PFAD_AUSGABE = Path(__file__).parent / "outputs" / "rechte_alt_kriegsbeginn_kanaele.md"

KRIEGSBEGINN = pd.Timestamp("2022-02-24")
FENSTER_ENDE = pd.Timestamp("2022-05-24")
MIN_VIDEOS = 5
N_KANAELE_DETAIL = 15
N_VIDEOS_TOP = 3
N_VIDEOS_KRIEG = 3


def lade():
    k = pd.read_stata(PFAD_ROH / "kanaele_roh.dta", convert_categoricals=False)
    k = k[(k["medientyp"] == 4) & (k["ideo_gesellschaft_baseline"] >= 0.5)]
    spalten = ["video_id", "channel_id", "upload_ts", "format", "views", "titel",
               "rel_russia_ukraine_war_cw", "rel_politics_general_cw"]
    v = pd.read_stata(PFAD_ROH / "videos_roh.dta", columns=spalten,
                      convert_categoricals=False)
    v = v[v["channel_id"].isin(k["channel_id"]) & (v["format"] == "long")]
    return k, v


def kanal_tabelle(k, v):
    w = v[(v["upload_ts"] >= KRIEGSBEGINN) & (v["upload_ts"] < FENSTER_ENDE)]
    vor = v[(v["upload_ts"] >= KRIEGSBEGINN - (FENSTER_ENDE - KRIEGSBEGINN))
            & (v["upload_ts"] < KRIEGSBEGINN)]
    g = w.groupby("channel_id").agg(
        n=("video_id", "size"),
        krieg=("rel_russia_ukraine_war_cw", "mean"),
        politik=("rel_politics_general_cw", "mean"),
        views_med=("views", "median"),
        views_sum=("views", "sum"),
    )
    g["n_vor"] = vor.groupby("channel_id").size().reindex(g.index).fillna(0)
    g = g.join(k.set_index("channel_id")[["kanal_name", "abonnenten",
                                          "ideo_gesellschaft_baseline",
                                          "pop_baseline", "sample_vorkrieg"]])
    g = g[g["n"] >= MIN_VIDEOS].sort_values("views_sum", ascending=False)
    return g, w


def zeile(r):
    return (f"| {r.kanal_name} | {r.n:.0f} | {r.n_vor:.0f} | {r.krieg:.0%} | "
            f"{r.politik:.0%} | {r.views_med / 1e3:.0f} | {r.views_sum / 1e6:.1f} | "
            f"{r.abonnenten / 1e3:.0f} | {r.ideo_gesellschaft_baseline:.2f} | "
            f"{r.pop_baseline:.2f} | {r.sample_vorkrieg:.0f} |")


def video_zeile(r):
    return (f"- {r.upload_ts:%d.%m.%Y} · {r.views / 1e3:,.0f} Tsd. Views · "
            f"[{r.titel}](https://www.youtube.com/watch?v={r.video_id})")


def schreibe(g, w):
    t = [
        "# Rechte alternative Kanäle in den ersten drei Kriegsmonaten",
        "",
        f"Fenster {KRIEGSBEGINN:%d.%m.%Y} bis {FENSTER_ENDE - pd.Timedelta(days=1):%d.%m.%Y}, "
        f"nur Long-Videos, Kanäle mit mind. {MIN_VIDEOS} Videos im Fenster "
        f"({len(g)} Kanäle). Auswahl: medientyp 4, ideo_gesellschaft_baseline ≥ 0,5. "
        "Krieg/Politik = Anteil der Videos mit rel_*_cw = 1 (Titel). "
        "n_vor = Long-Videos in den gleich langen Wochen vor Kriegsbeginn. "
        "Views kumuliert zum Abrufzeitpunkt.",
        "",
        "## Alle Kanäle (sortiert nach Views im Fenster)",
        "",
        "| Kanal | n | n_vor | Krieg | Politik | Views Median (Tsd.) | Views Summe (Mio.) "
        "| Abos (Tsd.) | Ideologie | Pop. | Vorkriegs-Sample |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
        *[zeile(r) for r in g.itertuples()],
        "",
        f"## Videos der {N_KANAELE_DETAIL} reichweitenstärksten Kanäle",
    ]
    for cid, r in g.head(N_KANAELE_DETAIL).iterrows():
        vk = w[w["channel_id"] == cid]
        t += ["", f"### {r.kanal_name}",
              f"{r.n:.0f} Videos, davon {r.krieg:.0%} Krieg, {r.politik:.0%} Politik; "
              f"Ideologie {r.ideo_gesellschaft_baseline:.2f}, Populismus {r.pop_baseline:.2f}",
              "", "Meistgesehen:"]
        t += [video_zeile(x) for x in vk.nlargest(N_VIDEOS_TOP, "views").itertuples()]
        krieg = vk[vk["rel_russia_ukraine_war_cw"] == 1]
        if len(krieg):
            t += ["", "Meistgesehene Kriegsvideos:"]
            t += [video_zeile(x) for x in krieg.nlargest(N_VIDEOS_KRIEG, "views").itertuples()]
    PFAD_AUSGABE.parent.mkdir(parents=True, exist_ok=True)
    PFAD_AUSGABE.write_text("\n".join(t) + "\n", encoding="utf-8")
    print(f"[Ausgabe] {PFAD_AUSGABE}")


def main():
    k, v = lade()
    g, w = kanal_tabelle(k, v)
    schreibe(g, w)


if __name__ == "__main__":
    main()

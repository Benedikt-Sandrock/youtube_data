"""Kleiner deskriptiver Test: Steigen die rechten Alternativmedien um den
Gas-Lieferstopp (02.09.2022) ins Energiethema ein, und steigt dabei ihre Reichweite?

Plan: .claude/plans/energiekrise_alternative_wachstum.md (Vortest, keine Regression).

Vorgehen:
- Kanäle und Gruppen wie in step6_auswertung/marktanteil_rohdaten_plots.py
  (KANALLISTE aus channels_check.xlsx, medientyp_ideologie, MANUELL_ALT_RECHTS),
  Videos aus videos_roh.dta mit format == long.
- Energie-Video zweifach: rel_energy_cw (Titelstichworte des Exports) und eine
  lokale, breitere Regex über den Titel (ENERGIE_REGEX, u. a. Strom, Gas, Heizung,
  Blackout). Zusätzlich deskriptiv: Treffer der Regex in der Beschreibung.
- Wochen relativ zum EREIGNIS (Woche 0 = [02.09., 09.09.2022)), je Gruppe:
  Uploads, Energie-Anteil, Views-Summe und Median-Views energie/sonst.
- Für die rechten Alternativen: Kanäle mit dem größten Energie-Einstieg
  (Anteil nachher minus vorher) und die meistgesehenen Energie-Titel je Fenster.

Views sind kumulierte Snapshots (Abruf 2026), d. h. Reichweite = Gesamtaufrufe
der in der Woche hochgeladenen Videos.

Ausgabe: scripts/adhoc/energie_lieferstopp/ergebnis.md (+ CSV je Woche).
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

# =========================================================
# KONFIGURATION
# =========================================================
EREIGNIS = pd.Timestamp("2022-09-02")   # Hauptdatum laut Plan (Nord-Stream-1-Stopp)
WOCHEN_VOR = 10                          # Wochen vor dem Ereignis (int >= 2)
WOCHEN_NACH = 10                         # Wochen nach dem Ereignis (int >= 2)
VERGLEICH_WOCHEN = 4                     # Fenster je Seite für Vorher/Nachher-Vergleiche (int >= 1)
GRUPPEN = ["Alternative (rechts)", "Traditionelle Medien", "ÖRR"]  # aus medientyp_ideologie
ZIELGRUPPE = "Alternative (rechts)"     # Gruppe für Kanal- und Titelauswertung
TOP_TITEL = 15                           # Anzahl meistgesehener Energie-Titel je Fenster
# Lokale Energie-Regex (Kleinschreibung), breiter als rel_energy_cw
ENERGIE_REGEX = (r"energie|strom(?!ung)|erdgas|flüssiggas|\bgas(?!t)|gasum|heiz|blackout|"
                 r"frier|nord ?stream|\blng\b|atomkraft|\bakw|kernkraft|kraftwerk|sprit|"
                 r"benzin|diesel|tankrabatt|windkraft|windr[aä]d|wärmepumpe|lastabwurf|"
                 r"stadtwerke|versorger")
REGISTRY = ROOT / "data" / "store" / "video_registry.sqlite"
AUSGABE = ROOT / "scripts" / "adhoc" / "energie_lieferstopp"


def lade_daten():
    k = mp.lade_kanaele()
    k, _ = mp.bilde_gruppen(k)
    k, _ = mp.manuell_alt_rechts(k)
    k = k[k["channel_id"].isin(mp.KANALLISTE) & k["medientyp_ideologie"].isin(GRUPPEN)]
    k = k[["channel_id", "kanal_name", "medientyp_ideologie"]].rename(columns={"medientyp_ideologie": "gruppe"})

    v = pd.read_stata(mp.ROHDATEN_PFAD / "videos_roh.dta",
                      columns=["video_id", "channel_id", "upload_ts", "views", "format",
                               "rel_energy_cw", "rel_russia_ukraine_war_cw"])
    v = v[v["format"].astype(str) == "long"]
    start = EREIGNIS - pd.Timedelta(weeks=WOCHEN_VOR)
    ende = EREIGNIS + pd.Timedelta(weeks=WOCHEN_NACH)
    v = v[(v["upload_ts"] >= start) & (v["upload_ts"] < ende)]
    v = v.merge(k, on="channel_id", how="inner")
    v["woche"] = ((v["upload_ts"] - EREIGNIS).dt.days // 7).astype(int)
    v["energie_kw"] = (v["rel_energy_cw"].astype(str) == "ja").astype(int)
    v["krieg"] = (v["rel_russia_ukraine_war_cw"].astype(str) == "ja").astype(int)

    con = sqlite3.connect(f"file:{REGISTRY}?mode=ro", uri=True)
    ids = v["video_id"].tolist()
    texte = []
    for i in range(0, len(ids), 900):
        chunk = ids[i:i + 900]
        q = ("SELECT v.video_id, v.title, d.description FROM videos v "
             "LEFT JOIN video_details d USING(video_id) WHERE v.video_id IN (%s)" % ",".join("?" * len(chunk)))
        texte.append(pd.read_sql_query(q, con, params=chunk))
    con.close()
    v = v.merge(pd.concat(texte), on="video_id", how="left")
    rx = re.compile(ENERGIE_REGEX)
    v["energie_rx"] = v["title"].fillna("").str.lower().map(lambda s: int(bool(rx.search(s))))
    v["energie_desc"] = v["description"].fillna("").str.lower().map(lambda s: int(bool(rx.search(s))))
    return v


def wochentabelle(v):
    rows = []
    for (g, w), d in v.groupby(["gruppe", "woche"]):
        e = d["energie_rx"] == 1
        rows.append({"gruppe": g, "woche": w, "uploads": len(d),
                     "anteil_energie_kw": d["energie_kw"].mean(),
                     "anteil_energie_rx": e.mean(),
                     "anteil_energie_desc": d["energie_desc"].mean(),
                     "anteil_krieg": d["krieg"].mean(),
                     "views_mio": d["views"].sum() / 1e6,
                     "views_energie_mio": d.loc[e, "views"].sum() / 1e6,
                     "views_sonst_mio": d.loc[~e, "views"].sum() / 1e6,
                     "median_energie": d.loc[e, "views"].median(),
                     "median_sonst": d.loc[~e, "views"].median()})
    return pd.DataFrame(rows)


def vorher_nachher(v):
    f = v[v["woche"].between(-VERGLEICH_WOCHEN, VERGLEICH_WOCHEN - 1)].copy()
    f["fenster"] = np.where(f["woche"] < 0, "vorher", "nachher")
    rows = []
    for (g, fe), d in f.groupby(["gruppe", "fenster"]):
        e = d["energie_rx"] == 1
        rows.append({"gruppe": g, "fenster": fe, "kanaele_aktiv": d["channel_id"].nunique(),
                     "uploads": len(d), "anteil_energie_rx": e.mean(),
                     "anteil_energie_kw": d["energie_kw"].mean(),
                     "views_mio": d["views"].sum() / 1e6,
                     "views_energie_mio": d.loc[e, "views"].sum() / 1e6,
                     "views_sonst_mio": d.loc[~e, "views"].sum() / 1e6,
                     "median_energie": d.loc[e, "views"].median(),
                     "median_sonst": d.loc[~e, "views"].median()})
    return pd.DataFrame(rows), f


def kanal_einstieg(f):
    d = f[f["gruppe"] == ZIELGRUPPE]
    t = d.groupby(["kanal_name", "fenster"]).agg(
        uploads=("video_id", "size"), energie=("energie_rx", "sum"),
        views=("views", "sum")).unstack("fenster").fillna(0)
    t.columns = [f"{a}_{b}" for a, b in t.columns]
    for c in ["uploads", "energie", "views"]:
        for fe in ["vorher", "nachher"]:
            if f"{c}_{fe}" not in t:
                t[f"{c}_{fe}"] = 0
    t["anteil_vorher"] = t["energie_vorher"] / t["uploads_vorher"].replace(0, np.nan)
    t["anteil_nachher"] = t["energie_nachher"] / t["uploads_nachher"].replace(0, np.nan)
    t["delta_views_mio"] = (t["views_nachher"] - t["views_vorher"]) / 1e6
    return t.sort_values("delta_views_mio", ascending=False)


def md_tabelle(df, fmt=None):
    df = df.copy()
    for c, f_ in (fmt or {}).items():
        df[c] = df[c].map(lambda x: "" if pd.isna(x) else f_.format(x))
    kopf = "| " + " | ".join(map(str, df.columns)) + " |"
    trenn = "|" + "---|" * len(df.columns)
    zeilen = ["| " + " | ".join(map(str, r)) + " |" for r in df.itertuples(index=False)]
    return "\n".join([kopf, trenn, *zeilen])


def main():
    if WOCHEN_VOR < 2 or WOCHEN_NACH < 2 or VERGLEICH_WOCHEN < 1:
        raise SystemExit("WOCHEN_VOR/WOCHEN_NACH >= 2 und VERGLEICH_WOCHEN >= 1 setzen.")
    if ZIELGRUPPE not in GRUPPEN:
        raise SystemExit("ZIELGRUPPE muss in GRUPPEN stehen.")
    AUSGABE.mkdir(parents=True, exist_ok=True)

    v = lade_daten()
    wt = wochentabelle(v)
    wt.to_csv(AUSGABE / "wochen.csv", index=False)
    vn, f = vorher_nachher(v)
    ke = kanal_einstieg(f)
    ke.to_csv(AUSGABE / "kanaele_zielgruppe.csv")

    pct = "{:.1%}"
    mio = "{:.2f}"
    ganz = "{:,.0f}"
    teile = [f"# Energiethema um den Lieferstopp {EREIGNIS:%d.%m.%Y}",
             "", f"Erzeugt von `scripts/adhoc/energie_lieferstopp_check.py`. Woche 0 = "
             f"[{EREIGNIS:%d.%m.}, +7 Tage). Energie_rx = lokale Titel-Regex, "
             "energie_kw = `rel_energy_cw`, energie_desc = Regex in Beschreibung. "
             "Views = kumulierte Aufrufe (Snapshot 2026) der in der Woche hochgeladenen Videos.", ""]
    teile += [f"## Vorher/Nachher ({VERGLEICH_WOCHEN} Wochen je Seite)", "",
              md_tabelle(vn, {"anteil_energie_rx": pct, "anteil_energie_kw": pct, "views_mio": mio,
                              "views_energie_mio": mio, "views_sonst_mio": mio,
                              "median_energie": ganz, "median_sonst": ganz}), ""]
    for g in GRUPPEN:
        d = wt[wt["gruppe"] == g].drop(columns="gruppe")
        teile += [f"## Wochen: {g}", "",
                  md_tabelle(d, {c: pct for c in d.columns if c.startswith("anteil")}
                             | {c: mio for c in d.columns if c.endswith("_mio")}
                             | {"median_energie": ganz, "median_sonst": ganz}), ""]
    kz = ke.reset_index()[["kanal_name", "uploads_vorher", "uploads_nachher", "anteil_vorher",
                           "anteil_nachher", "views_vorher", "views_nachher", "delta_views_mio"]]
    kz = kz[(kz["uploads_vorher"] + kz["uploads_nachher"]) > 0].head(25)
    teile += [f"## {ZIELGRUPPE}: Kanäle nach Views-Zuwachs (nachher − vorher)", "",
              md_tabelle(kz, {"anteil_vorher": pct, "anteil_nachher": pct, "views_vorher": ganz,
                              "views_nachher": ganz, "delta_views_mio": mio,
                              "uploads_vorher": "{:.0f}", "uploads_nachher": "{:.0f}"}), ""]
    z = f[(f["gruppe"] == ZIELGRUPPE) & (f["energie_rx"] == 1)]
    for fe in ["vorher", "nachher"]:
        t = z[z["fenster"] == fe].nlargest(TOP_TITEL, "views")
        t = t.assign(datum=t["upload_ts"].dt.strftime("%d.%m."),
                     titel=t["title"].str.replace("|", "/", regex=False))
        teile += [f"## {ZIELGRUPPE}: meistgesehene Energie-Titel ({fe})", "",
                  md_tabelle(t[["datum", "kanal_name", "views", "titel"]], {"views": ganz}), ""]
    # Titel, die nur die Regex (nicht rel_energy_cw) findet: Plausibilitätscheck
    nur_rx = f[(f["energie_rx"] == 1) & (f["energie_kw"] == 0) & (f["gruppe"] == ZIELGRUPPE)]
    teile += [f"## Plausibilität: Regex-Treffer ohne rel_energy_cw ({len(nur_rx)}; Stichprobe 20)", "",
              *[f"- {t}" for t in nur_rx.sample(min(20, len(nur_rx)), random_state=1)["title"]], ""]
    (AUSGABE / "ergebnis.md").write_text("\n".join(teile), encoding="utf-8")
    print(f"-> {AUSGABE / 'ergebnis.md'}")


if __name__ == "__main__":
    main()

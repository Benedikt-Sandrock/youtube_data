"""Zerlegung des zweiten Views-Schubs der rechten Alternativmedien ab Monat 15
(24.05.2023) bis zur Bundestagswahl 2025 (Monat 35) und danach, aus
marktanteil_medientyp_ideologie_kombiniert_long_manuell_absolut.png.

Fragen: Ist "Monat 15 bis zur Wahl" eine durchgaengige Phase? Welche Kanaele
tragen den Anstieg in den einzelnen Phasen, breit oder konzentriert? Mehr
Uploads oder mehr Views je Video? Kommt der Zuwachs von etablierten oder von
neuen Kanaelen? Welche Themen (Titel)?

Vorgehen:
- Kanaele und Gruppen exakt wie in step6_auswertung/marktanteil_rohdaten_plots.py
  (KANALLISTE, medientyp_ideologie, MANUELL_ALT_RECHTS), Videos aus videos_roh.dta
  mit format == long, rel_monat relativ zum 24.02.2022.
- Phasen (rel_monat, inklusive) siehe PHASEN; Phasenwerte = mittlere Views je
  Monat (Monate ohne Upload = 0).
- "Etabliert" = erstes long-Video eines Kanals bis ETABLIERT_BIS (balanced-
  panel-Naeherung); "neu" in einer Phase = erstes Video ab Phasenbeginn minus
  NEU_VORLAUF Monate.
- Themen: Titel-Stichworte rel_<thema>_cw aus dem Export plus lokale Regex
  ueber den Titel (REGEX_THEMEN, ueberlappend).

Views sind kumulierte Snapshots (Abruf 2026); juengere Videos hatten weniger
Zeit, Views zu sammeln. Das Sample ist nachtraeglich gezogen (Kanaele, die
spaeter gross wurden, sind ueberrepraesentiert), was vor allem den Zuwachs
ueber neue Kanaele betrifft.
Ausgabe: scripts/adhoc/alt_rechts_zweiter_schub/ergebnis.md (+ kanaele.csv, monate.csv).
Ergebnisse zusammengefasst in .claude/plans/energiekrise_alternative_wachstum.md.
"""
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
PHASEN = {                        # Name -> rel_monat (von, bis), inklusive, aufsteigend, ohne Ueberlappung
    "A": (6, 14),                 # Plateau nach dem Sprung in Monat 5/6
    "B1": (15, 24),               # AfD-Umfragehoch bis Bauernproteste/Correctiv
    "B2": (25, 33),               # bis Ampel-Aus / Dez. 2024
    "WAHL": (34, 36),             # Wahlkampf und BTW 23.02.2025 (Monat 35)
    "DANACH": (37, 51),           # nach der Wahl (Monat 52 ist unvollstaendig)
}
VERGLEICHE = [("A", "B1"), ("B1", "B2"), ("A", "B2"), ("B2", "WAHL")]  # Phasenpaare (vorher, nachher) aus PHASEN
MONATE_TABELLE = (12, 51)         # Monatsbereich der Monatstabelle
ETABLIERT_BIS = 0                 # rel_monat: Kanaele mit erstem long-Video bis hier gelten als etabliert
NEU_VORLAUF = 3                   # Monate vor Phasenbeginn, ab denen ein Kanal als "neu" zaehlt (int >= 0)
MIN_VIEWS_BASIS = 50_000          # Mindest-Views je Monat in der Vorphase fuer den Median-Wachstumsfaktor
TOP_KANAELE = 15                  # Zeilen je Kanaltabelle (int >= 1)
TOP_VIDEOS = 20                   # meistgesehene Videos je Phase in TOP_VIDEO_PHASEN
TOP_VIDEO_PHASEN = ["B1", "B2", "WAHL"]  # Phasen aus PHASEN
PROFIL_KANAELE = 6                # Profile der Top-Wachstumskanaele je Vergleich
# Lokale Themen-Regex ueber den Titel (ohne Gross-/Kleinschreibung, ueberlappend)
REGEX_THEMEN = {
    "AfD": r"\bafd\b|weidel|chrupalla|höcke|hoecke|\bkrah\b",
    "Ampel/Grüne/Regierung": (r"ampel|grüne|gruene|habeck|baerbock|bärbock|scholz|ricarda|\blang\b|"
                              r"lauterbach|faeser|kühnert|lindner"),
    "Merz/CDU/Union": r"merz|\bcdu\b|\bcsu\b|union\b|söder|brandmauer",
    "Wahl/Umfrage": r"wahl|umfrage|koalition",
    "Clip/Reaktion": (r"zerlegt|zerstört|\brede\b|eklat|lanz|illner|maischberger|miosga|talk|reaction|"
                      r"reaktion|bundestag|vorgeführt|blamiert"),
    "Migration/Kriminalität": (r"migra|asyl|flüchtl|abschieb|messer|clan|gewalt|kriminal|anschlag|"
                               r"solingen|magdeburg|aschaffenburg"),
    "Bauern": r"bauer|landwirt|traktor|agrardiesel",
    "Ukraine/Russland/Krieg": r"ukrain|russ|putin|selensk|krieg|nato",
    "Trump/USA/Musk": r"trump|\busa\b|musk|vance|biden|harris",
    "Finanzen/Immobilien": (r"aktie|börse|immobil|gold|silber|zins|inflation|crash|geld|vermiet|steuer|"
                            r"rente|bitcoin"),
}
PROFIL_THEMEN = ["AfD", "Ampel/Grüne/Regierung", "Merz/CDU/Union", "Migration/Kriminalität",
                 "Finanzen/Immobilien"]  # Teilmenge von REGEX_THEMEN
AUSGABE = ROOT / "scripts" / "adhoc" / "alt_rechts_zweiter_schub"


def lade():
    k = mp.lade_kanaele()
    k, _ = mp.bilde_gruppen(k)
    k, _ = mp.manuell_alt_rechts(k)
    k = k[k["channel_id"].isin(mp.KANALLISTE) & (k["medientyp_ideologie"] == GRUPPE)]
    k = k[["channel_id", "kanal_name"]].assign(kanal_name=lambda d: d["kanal_name"].astype(str).str.strip())
    themen = [f"rel_{t}_cw" for t in TOPIC_KEYWORDS]
    v = pd.read_stata(mp.ROHDATEN_PFAD / "videos_roh.dta",
                      columns=["video_id", "channel_id", "titel", "upload_ts", "views", "format", *themen])
    v = v[(v["format"].astype(str) == "long") & v["views"].notna()]
    v = v.merge(k, on="channel_id", how="inner")
    v["rel_monat"] = relativ_periode(v["upload_ts"], pd.Timestamp(KRIEGSBEGINN), 1)
    # erstes long-Video ueber die ganze Historie, vor dem Zuschnitt auf die Phasen
    k = k.merge(v.groupby("channel_id")["rel_monat"].min().rename("erster_monat"), on="channel_id", how="left")
    alle = [m for f in PHASEN.values() for m in f] + list(MONATE_TABELLE)
    v = v[v["rel_monat"].between(min(alle), max(alle))].copy()
    for t in themen:
        v[t.removeprefix("rel_").removesuffix("_cw")] = (v[t].astype(str) == "ja")
    v = v.drop(columns=themen)
    tl = v["titel"].astype(str)
    for name, rx in REGEX_THEMEN.items():
        v["rx_" + name] = tl.str.contains(rx, case=False, regex=True)
    return k, v


def md(df, fmt=None):
    df = df.copy()
    for c, f in (fmt or {}).items():
        df[c] = df[c].map(lambda x: f.format(x) if pd.notna(x) else "")
    kopf = "| " + " | ".join(map(str, df.columns)) + " |"
    trenn = "|" + "---|" * len(df.columns)
    zeilen = ["| " + " | ".join(str(x).replace("|", "/") for x in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([kopf, trenn, *zeilen])


def n_monate(p):
    return PHASEN[p][1] - PHASEN[p][0] + 1


def main():
    for name, f in {**PHASEN, "MONATE_TABELLE": MONATE_TABELLE}.items():
        if len(f) != 2 or f[0] > f[1]:
            raise SystemExit(f"{name} muss (von, bis) mit von <= bis sein, nicht {f!r}.")
    grenzen = list(PHASEN.values())
    if any(a[1] >= b[0] for a, b in zip(grenzen, grenzen[1:])):
        raise SystemExit("PHASEN muessen aufsteigend und ohne Ueberlappung angegeben sein.")
    for x, y in VERGLEICHE:
        if x not in PHASEN or y not in PHASEN:
            raise SystemExit(f"VERGLEICHE enthaelt unbekannte Phase: {(x, y)!r}.")
    if not set(TOP_VIDEO_PHASEN) <= set(PHASEN):
        raise SystemExit(f"TOP_VIDEO_PHASEN muss Teilmenge von PHASEN sein: {TOP_VIDEO_PHASEN!r}.")
    if not set(PROFIL_THEMEN) <= set(REGEX_THEMEN):
        raise SystemExit(f"PROFIL_THEMEN muss Teilmenge von REGEX_THEMEN sein: {PROFIL_THEMEN!r}.")
    if NEU_VORLAUF < 0 or TOP_KANAELE < 1 or PROFIL_KANAELE < 0 or TOP_VIDEOS < 0:
        raise SystemExit("NEU_VORLAUF, PROFIL_KANAELE, TOP_VIDEOS muessen >= 0 sein, TOP_KANAELE >= 1.")
    AUSGABE.mkdir(parents=True, exist_ok=True)
    k, v = lade()
    k = k.set_index("channel_id")
    etabliert = set(k.index[k["erster_monat"] <= ETABLIERT_BIS])
    v["phase"] = None
    for p, f in PHASEN.items():
        v.loc[v["rel_monat"].between(*f), "phase"] = p
    ph = list(PHASEN)
    rx = ["rx_" + t for t in REGEX_THEMEN]

    out = [f"# Zweiter Views-Schub bei „{GRUPPE}“ ab Monat 15", "",
           f"Erzeugt von `scripts/adhoc/alt_rechts_zweiter_schub.py`. Sample wie "
           f"`marktanteil_rohdaten_plots.py` (KANALLISTE, MANUELL_ALT_RECHTS = {mp.MANUELL_ALT_RECHTS}), "
           f"nur long-Videos. {len(k)} Kanäle in der Gruppe, davon {len(etabliert)} etabliert (erstes Video "
           f"bis Monat {ETABLIERT_BIS}). Phasen (rel_monat): "
           + ", ".join(f"{p} {a}–{b}" for p, (a, b) in PHASEN.items())
           + ". Phasenwerte = mittlere Views je Monat (Monate ohne Upload = 0). Views = kumulierter Snapshot "
           "2026; das Sample ist nachträglich gezogen (Vorbehalt vor allem für neue Kanäle).", ""]

    # --- 1. Monatsverlauf
    g = v[v["rel_monat"].between(*MONATE_TABELLE)]
    mon = pd.DataFrame({
        "kanaele_aktiv": g.groupby("rel_monat")["channel_id"].nunique(),
        "uploads": g.groupby("rel_monat").size(),
        "views_mio": g.groupby("rel_monat")["views"].sum() / 1e6,
        "views_etabliert_mio": g[g["channel_id"].isin(etabliert)].groupby("rel_monat")["views"].sum() / 1e6,
        "median_tsd": g.groupby("rel_monat")["views"].median() / 1e3,
        **{t: g[g["rx_" + t]].groupby("rel_monat")["views"].sum() / 1e6 for t in REGEX_THEMEN},
    }).fillna(0)
    mon.to_csv(AUSGABE / "monate.csv", encoding="utf-8-sig")
    out += ["## 1. Monatsverlauf", "",
            "Views in Mio.; Themenspalten = Views der Videos mit Treffer der Titel-Regex (überlappend).", "",
            md(mon.reset_index().rename(columns={"rel_monat": "monat"}),
               {c: "{:.1f}" for c in mon.columns if c not in ("kanaele_aktiv", "uploads")}), ""]

    # --- 2. Phasenniveau
    c = v.groupby(["channel_id", "phase"])["views"].sum().unstack(fill_value=0).reindex(columns=ph, fill_value=0)
    upl = v.groupby(["channel_id", "phase"]).size().unstack(fill_value=0).reindex(columns=ph, fill_value=0)
    for p in ph:
        c[p] = c[p] / n_monate(p)
        upl[p] = upl[p] / n_monate(p)
    rows = []
    for p in ph:
        d = v[v["phase"] == p]
        s = c[p].sort_values(ascending=False)
        rows.append({"phase": p, "monate": f"{PHASEN[p][0]}–{PHASEN[p][1]}", "views_mio": s.sum() / 1e6,
                     "views_etabliert_mio": c.loc[c.index.isin(etabliert), p].sum() / 1e6,
                     "uploads_je_monat": len(d) / n_monate(p), "kanaele_aktiv": d["channel_id"].nunique(),
                     "views_je_video_tsd": d["views"].mean() / 1e3, "median_tsd": d["views"].median() / 1e3,
                     "anteil_top5": s.head(5).sum() / s.sum(), "anteil_top10": s.head(10).sum() / s.sum()})
    out += ["## 2. Niveau je Phase", "",
            "Views und Uploads als Mittel je Monat; Top-5/Top-10 = Anteil der stärksten Kanäle an den Views der Phase.",
            "", md(pd.DataFrame(rows), {"views_mio": "{:.1f}", "views_etabliert_mio": "{:.1f}",
                                         "uploads_je_monat": "{:.0f}", "views_je_video_tsd": "{:.1f}",
                                         "median_tsd": "{:.1f}", "anteil_top5": "{:.0%}",
                                         "anteil_top10": "{:.0%}"}), ""]

    # --- 3. Kanalzerlegung je Vergleich
    kanaele = c.div(1e6).add_prefix("views_mio_").join(upl.add_prefix("uploads_"))
    kanaele = k[["kanal_name", "erster_monat"]].join(kanaele, how="left").fillna(0)
    kanaele.to_csv(AUSGABE / "kanaele.csv", encoding="utf-8-sig")
    out += ["## 3. Welche Kanäle tragen den Zuwachs?", ""]
    for x, y in VERGLEICHE:
        delta = (c[y] - c[x]).sort_values(ascending=False)
        tot = delta.sum()
        aktiv = (c[[x, y]].sum(axis=1) > 0).sum()
        basis = c[c[x] > MIN_VIEWS_BASIS]
        faktor = (basis[y] / basis[x]).median()
        neu = k.index[k["erster_monat"] >= PHASEN[y][0] - NEU_VORLAUF]
        et = delta[delta.index.isin(etabliert)].sum()
        out += [f"### {x} → {y}: {tot / 1e6:+.1f} Mio. Views/Monat", "",
                f"- Konzentration: Top 1 {delta.iloc[0] / tot:.0%}, Top 3 {delta.head(3).sum() / tot:.0%}, "
                f"Top 5 {delta.head(5).sum() / tot:.0%}, Top 10 {delta.head(10).sum() / tot:.0%} des Zuwachses.",
                f"- Wachsende Kanäle: {(delta > 0).sum()} von {aktiv} (in einer der beiden Phasen aktiv).",
                f"- Median-Wachstumsfaktor {y}/{x} der Kanäle mit > {MIN_VIEWS_BASIS:,} Views/Monat in {x}: "
                f"{faktor:.2f} (n = {len(basis)}).",
                f"- Etablierte Kanäle: {et / tot:.0%} des Zuwachses; neue Kanäle (erstes Video ab Monat "
                f"{PHASEN[y][0] - NEU_VORLAUF}, n = {len(neu)}): {delta[delta.index.isin(neu)].sum() / tot:.0%}.",
                ""]
        t = pd.DataFrame({"kanal": k.loc[delta.index, "kanal_name"],
                          "erster_monat": k.loc[delta.index, "erster_monat"],
                          **{p: c.loc[delta.index, p] / 1e6 for p in ph},
                          "delta": delta / 1e6, "anteil": delta / tot})
        fmt = {**{p: "{:.2f}" for p in ph}, "delta": "{:+.2f}", "anteil": "{:.0%}", "erster_monat": "{:.0f}"}
        out += ["Größte Gewinner (Mio. Views/Monat je Phase):", "", md(t.head(TOP_KANAELE), fmt), "",
                "Größte Verlierer:", "", md(t.tail(5), fmt), ""]

    # --- 4. Themen je Phase
    def themen_tabelle(spalten, namen):
        rows = []
        for s, n in zip(spalten, namen):
            r = {"thema": n}
            for p in ph:
                d = v[v["phase"] == p]
                r[f"{p}_mio"] = d.loc[d[s], "views"].sum() / n_monate(p) / 1e6
                r[f"{p}_anteil"] = d.loc[d[s], "views"].sum() / d["views"].sum()
            rows.append(r)
        return pd.DataFrame(rows)
    fmt = {**{f"{p}_mio": "{:.1f}" for p in ph}, **{f"{p}_anteil": "{:.0%}" for p in ph}}
    out += ["## 4. Themen je Phase (Titel; Mio. Views/Monat und Anteil an den Views der Phase)", "",
            "### Lokale Regex (überlappend)", "",
            md(themen_tabelle(rx, list(REGEX_THEMEN)), fmt), "",
            "### Export-Stichworte `rel_*_cw`", "",
            md(themen_tabelle(list(TOPIC_KEYWORDS), list(TOPIC_KEYWORDS))
               .sort_values(f"{ph[-1]}_mio", ascending=False), fmt), ""]

    # --- 5. Profile der Top-Wachstumskanaele
    out += ["## 5. Profile der größten Wachstumskanäle", "",
            "Anteil der Views mit Treffer der Titel-Regex; meistgesehene Titel der Nachher-Phase.", ""]
    for x, y in VERGLEICHE:
        delta = (c[y] - c[x]).sort_values(ascending=False)
        out += [f"### {x} → {y}", ""]
        for cid in delta.index[:PROFIL_KANAELE]:
            out += [f"**{k.loc[cid, 'kanal_name']}** (Δ {delta[cid] / 1e6:+.2f} Mio./Monat)", ""]
            for p in (x, y):
                d = v[(v["channel_id"] == cid) & (v["phase"] == p)]
                if len(d):
                    anteile = ", ".join(f"{t} {d.loc[d['rx_' + t], 'views'].sum() / d['views'].sum():.0%}"
                                        for t in PROFIL_THEMEN)
                    out += [f"- {p}: {len(d) / n_monate(p):.0f} Uploads/Monat, Median "
                            f"{d['views'].median() / 1e3:.0f} Tsd.; {anteile}"]
            d = v[(v["channel_id"] == cid) & (v["phase"] == y)].nlargest(4, "views")
            out += [f"  - {r.upload_ts:%d.%m.%Y} · {r.views / 1e3:,.0f} Tsd. · {str(r.titel).strip()}"
                    for r in d.itertuples()] + [""]

    # --- 6. Meistgesehene Videos je Phase
    out += ["## 6. Meistgesehene Videos je Phase", ""]
    for p in TOP_VIDEO_PHASEN:
        top = v[v["phase"] == p].nlargest(TOP_VIDEOS, "views")
        out += [f"### {p}", "",
                md(top.assign(datum=top["upload_ts"].dt.strftime("%d.%m.%Y"), views_tsd=top["views"] / 1e3,
                              titel=top["titel"].astype(str).str.strip().str[:110])
                   [["rel_monat", "datum", "kanal_name", "views_tsd", "titel"]], {"views_tsd": "{:,.0f}"}), ""]

    (AUSGABE / "ergebnis.md").write_text("\n".join(out), encoding="utf-8")
    print(f"-> {AUSGABE / 'ergebnis.md'}")


if __name__ == "__main__":
    main()

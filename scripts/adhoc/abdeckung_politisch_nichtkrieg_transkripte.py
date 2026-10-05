# -*- coding: utf-8 -*-
"""
abdeckung_politisch_nichtkrieg_transkripte.py

Abdeckungscheck: Fuer wie viele politische Nicht-Kriegsvideos der
Frage-1-Whitelist-Kanaele (`outputs/segment_analysis/frage1_kanal_whitelist.csv`)
liegen Transkripte vor, und wie viele Kanal-Monate sind damit abgedeckt?

Definitionen:
  - politisch: video_details.topic_categories enthaelt YouTube's "Politics"
    (video_registry.politics_topic_lookup()). Videos ohne video_details-Zeile
    gelten als "unbekannt" und werden separat gezaehlt, nicht als unpolitisch.
  - Kriegsvideo: video_topic_relevance, topic="russia_ukraine_war",
    is_relevant=1 (video_registry.topic_relevant_video_ids()).
  - Mindestdauer: nur Videos >= MIN_VIDEO_DURATION_SECONDS (181 s), da kuerzere
    Videos nie themenklassifiziert wurden und aus allen Transkript-Analysen
    ausgeschlossen sind (get_video_metadata()-Default).
  - Transkript vorhanden: ausschliesslich transcript_store.has_transcript()
    (status OK, n_segments > 0); "versucht" = attempted_video_ids().
  - Kanal-Monat: Kalendermonat der Veroeffentlichung. Periode: vor = bis
    einschliesslich 2022-01, Uebergang = 2022-02 (Kriegsbeginn 24.02.),
    nach = ab 2022-03.

Hauptteil (Zellen-Abgleich): Basis sind Kanal-Monats-Zellen mit >= k
Kriegsvideos MIT Transkript (k in KRIEG_SCHWELLEN; 3 = min_videos_pro_periode
der Monatsgranularitaet in deskriptiv_aggregation.py). Fuer diese Zellen wird
geprueft, ob es in derselben Zelle politische Nicht-Kriegsvideos gibt und fuer
wie viele davon Transkripte vorliegen (>= 1/3/5) - d.h. ob ein Within-Zelle-
Vergleich Krieg vs. politisch-nicht-Krieg moeglich ist.

Zusatz: allgemeine Abdeckung aller Kanal-Monate mit >= 1 politischen
Nicht-Kriegsvideo (unabhaengig von Kriegsvideos).

Ausgabe: outputs/segment_analysis/abdeckung_politisch_nichtkrieg/
  - README.md (Zusammenfassung, menschenlesbar)
  - zellen_krieg_vs_pol_nk.csv (channel_id x monat aller Zellen: n_krieg,
    n_krieg_tr, n_pol_nk, n_pol_nk_tr)
  - kanal_monat.csv (channel_id x monat: n_pol_nk, n_transkript, n_versucht)
  - kanal.csv (Abdeckung je Kanal)

    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        scripts/adhoc/abdeckung_politisch_nichtkrieg_transkripte.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "youtube_code", "step6_auswertung"))

import pandas as pd

from deskriptiv_aggregation import lade_medientyp
from youtube_code.config import OUTPUTS
from youtube_code.store import transcript_store, video_registry

PFAD_WHITELIST = OUTPUTS / "segment_analysis" / "frage1_kanal_whitelist.csv"
ERGEBNIS_ORDNER = OUTPUTS / "segment_analysis" / "abdeckung_politisch_nichtkrieg"
SCHWELLEN = [1, 3, 5, 10]
KRIEG_SCHWELLEN = [1, 3, 5]
NK_SCHWELLEN = [1, 3, 5]


def periode(monat):
    if monat <= pd.Period("2022-01", "M"):
        return "vor"
    if monat == pd.Period("2022-02", "M"):
        return "uebergang"
    return "nach"


def lade():
    whitelist = pd.read_csv(PFAD_WHITELIST)["channel_id"].astype(str).tolist()
    v = video_registry.get_video_metadata(channel_ids=whitelist)  # >= 181 s
    pol = video_registry.politics_topic_lookup(v["video_id"])
    krieg = video_registry.topic_relevant_video_ids("russia_ukraine_war")
    v["politisch"] = v["video_id"].map(pol)  # NaN = keine video_details
    v["krieg"] = v["video_id"].isin(krieg)
    v["transkript"] = v["video_id"].isin(transcript_store.has_transcript(v["video_id"]))
    v["versucht"] = v["video_id"].isin(transcript_store.attempted_video_ids())
    v["monat"] = pd.to_datetime(v["published_at"], utc=True, errors="coerce").dt.tz_localize(None).dt.to_period("M")
    v["periode"] = v["monat"].map(periode)

    med = lade_medientyp().drop_duplicates("channel_id")[["channel_id", "medientyp"]]
    kanaele = pd.DataFrame({"channel_id": whitelist}).merge(med, on="channel_id", how="left")
    kanaele["medientyp"] = kanaele["medientyp"].fillna("unbekannt")
    titel = v.groupby("channel_id")["channel_title"].last()
    kanaele["title"] = kanaele["channel_id"].map(titel).fillna(kanaele["channel_id"])
    return v, kanaele


def md_tabelle(df):
    zeilen = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + " --- |" * len(df.columns)]
    zeilen += ["| " + " | ".join(map(str, r)) + " |" for r in df.itertuples(index=False)]
    return "\n".join(zeilen)


def abdeckung_km(km, gruppe):
    """Kanal-Monats-Abdeckung je Gruppe (nur Kanal-Monate mit >= 1 pol. NK-Video)."""
    rows = []
    for name, g in (km.groupby(gruppe) if gruppe else [("gesamt", km)]):
        r = {gruppe or "gruppe": name, "Kanal-Monate": len(g), "Kanäle": g["channel_id"].nunique(),
             "pol. NK-Videos": int(g["n_pol_nk"].sum()), "mit Transkript": int(g["n_transkript"].sum())}
        r["Video-Quote"] = f"{r['mit Transkript'] / r['pol. NK-Videos']:.1%}" if r["pol. NK-Videos"] else "–"
        for s in SCHWELLEN:
            r[f"KM ≥{s} Tr."] = f"{(g['n_transkript'] >= s).mean():.1%}"
        rows.append(r)
    return pd.DataFrame(rows)


def zellen_abgleich(v):
    """Alle Kanal-Monats-Zellen mit Kriegs- und pol. Nicht-Kriegsvideo-Zaehlungen."""
    pnk = (v["politisch"] == True) & ~v["krieg"]  # noqa: E712
    return (v.assign(k=v["krieg"], k_tr=v["krieg"] & v["transkript"], p=pnk, p_tr=pnk & v["transkript"])
            .groupby(["channel_id", "medientyp", "monat", "periode"])
            .agg(n_krieg=("k", "sum"), n_krieg_tr=("k_tr", "sum"), n_pol_nk=("p", "sum"), n_pol_nk_tr=("p_tr", "sum"))
            .reset_index())


def zellen_tabelle(z, gruppe=None):
    rows = []
    for k in KRIEG_SCHWELLEN:
        basis = z[z["n_krieg_tr"] >= k]
        for name, g in (basis.groupby(gruppe) if gruppe else [("gesamt", basis)]):
            r = {"≥k Kriegs-Tr.": k}
            if gruppe:
                r[gruppe] = name
            r.update({"Zellen": len(g), "Kanäle": g["channel_id"].nunique(),
                      "mit pol. NK-Video": f"{(g['n_pol_nk'] > 0).mean():.1%}"})
            for s in NK_SCHWELLEN:
                n = int((g["n_pol_nk_tr"] >= s).sum())
                r[f"≥{s} NK-Tr."] = f"{n} ({n / len(g):.1%})" if len(g) else "–"
            r["Σ NK-Videos"] = int(g["n_pol_nk"].sum())
            r["Σ NK-Tr."] = int(g["n_pol_nk_tr"].sum())
            rows.append(r)
    return pd.DataFrame(rows)


def main():
    ERGEBNIS_ORDNER.mkdir(parents=True, exist_ok=True)
    v, kanaele = lade()
    v = v.merge(kanaele[["channel_id", "medientyp"]], on="channel_id", how="left")

    n_unbekannt = int(v["politisch"].isna().sum())
    z = zellen_abgleich(v)
    z.assign(monat=z["monat"].astype(str)).to_csv(ERGEBNIS_ORDNER / "zellen_krieg_vs_pol_nk.csv",
                                                  index=False, encoding="utf-8")
    z_vn = z[z["periode"] != "uebergang"]
    z3 = z[z["n_krieg_tr"] >= 3]
    kanal_z3 = (z3.groupby("channel_id")
                .agg(zellen=("monat", "size"), mit_nk_tr=("n_pol_nk_tr", lambda s: (s > 0).sum())).reset_index())
    pnk = v[(v["politisch"] == True) & ~v["krieg"]]  # noqa: E712

    km = (pnk.groupby(["channel_id", "medientyp", "monat", "periode"])
          .agg(n_pol_nk=("video_id", "size"), n_transkript=("transkript", "sum"), n_versucht=("versucht", "sum"))
          .reset_index())
    km.assign(monat=km["monat"].astype(str)).to_csv(ERGEBNIS_ORDNER / "kanal_monat.csv", index=False, encoding="utf-8")

    # Kanal-Ebene
    kanal = (km.groupby("channel_id")
             .agg(km_gesamt=("monat", "size"), km_mit_tr=("n_transkript", lambda s: (s > 0).sum()),
                  n_pol_nk=("n_pol_nk", "sum"), n_transkript=("n_transkript", "sum")).reset_index())
    for p in ["vor", "nach"]:
        sub = km[km["periode"] == p]
        kanal = kanal.merge(sub.groupby("channel_id")
                            .agg(**{f"km_{p}": ("monat", "size"),
                                    f"km_{p}_mit_tr": ("n_transkript", lambda s: (s > 0).sum()),
                                    f"tr_{p}": ("n_transkript", "sum")}).reset_index(),
                            on="channel_id", how="left")
    kanal = kanaele.merge(kanal, on="channel_id", how="left").fillna(0)
    kanal.to_csv(ERGEBNIS_ORDNER / "kanal.csv", index=False, encoding="utf-8")

    # Video-Uebersicht
    def zaehl(df):
        return {"Videos": len(df), "mit Transkript": int(df["transkript"].sum()),
                "versucht (jeder Status)": int(df["versucht"].sum())}
    uebersicht = pd.DataFrame([
        {"Menge": "alle Videos ≥181 s", **zaehl(v)},
        {"Menge": "davon politisch (topic_categories)", **zaehl(v[v["politisch"] == True])},  # noqa: E712
        {"Menge": "– davon Kriegsvideos", **zaehl(v[(v["politisch"] == True) & v["krieg"]])},  # noqa: E712
        {"Menge": "– davon Nicht-Kriegsvideos", **zaehl(pnk)},
        {"Menge": "ohne video_details (politisch unbekannt)", **zaehl(v[v["politisch"].isna()])},
    ])
    uebersicht["Quote"] = (uebersicht["mit Transkript"] / uebersicht["Videos"]).map("{:.1%}".format)

    nach_periode_video = (pnk.groupby("periode").agg(Videos=("video_id", "size"), Transkripte=("transkript", "sum"))
                          .reindex(["vor", "uebergang", "nach"]).reset_index())
    nach_periode_video["Quote"] = (nach_periode_video["Transkripte"] / nach_periode_video["Videos"]).map("{:.1%}".format)

    # Kanäle mit Vor- UND Nach-Abdeckung
    beide = {s: int(((kanal["km_vor_mit_tr"] >= s) & (kanal["km_nach_mit_tr"] >= s)).sum()) for s in [1, 3, 6, 12]}
    ohne_tr = kanal[kanal["n_transkript"] == 0]

    jahr = km.assign(jahr=km["monat"].dt.year)
    zeilen = [
        "# Transkript-Abdeckung politischer Nicht-Kriegsvideos (Frage-1-Whitelist)",
        "",
        "Erzeugt von `scripts/adhoc/abdeckung_politisch_nichtkrieg_transkripte.py`.",
        "",
        "## Methodik",
        "",
        f"- Kanäle: `frage1_kanal_whitelist.csv` ({len(kanaele)} Kanäle).",
        "- Videos: `video_registry.videos`, nur Dauer ≥ 181 s (`MIN_VIDEO_DURATION_SECONDS`).",
        "- Politisch: `video_details.topic_categories` enthält „Politics“ (YouTube-Klassifikation). "
        f"{n_unbekannt} Videos ohne `video_details` → unbekannt, nicht mitgezählt.",
        "- Kriegsvideo: `video_topic_relevance` (`russia_ukraine_war`, `is_relevant = 1`).",
        "- Transkript: `transcript_store.has_transcript()` (Status OK, > 0 Segmente).",
        "- Kanal-Monat (KM): Veröffentlichungsmonat; Nenner = KM mit ≥ 1 politischen Nicht-Kriegsvideo. "
        "Periode: vor ≤ 2022-01, Übergang = 2022-02, nach ≥ 2022-03.",
        "- „KM ≥k Tr.“ = Anteil der Kanal-Monate mit mindestens k Transkripten.",
        "",
        "## Zellen-Abgleich: Kriegsvideo-Zellen vs. politische Nicht-Kriegsvideos",
        "",
        "Basis: Kanal-Monats-Zellen mit mindestens k Kriegsvideos **mit Transkript**. "
        "„mit pol. NK-Video“ = Anteil der Zellen, in denen es überhaupt ein politisches Nicht-Kriegsvideo "
        "(≥ 181 s) gibt; „≥s NK-Tr.“ = Zellen (Anteil), in denen mindestens s davon ein Transkript haben.",
        "",
        "### Gesamt",
        "",
        md_tabelle(zellen_tabelle(z)),
        "",
        "### Nach Periode",
        "",
        md_tabelle(zellen_tabelle(z, "periode")),
        "",
        "### Nach Medientyp (vor/nach getrennt)",
        "",
        md_tabelle(zellen_tabelle(z_vn.assign(gruppe=lambda d: d["medientyp"] + " / " + d["periode"]), "gruppe")),
        "",
        "### Kanal-Ebene (Zellen mit ≥ 3 Kriegs-Transkripten)",
        "",
        f"- Kanäle mit ≥ 1 solchen Zelle: {len(kanal_z3)}",
        f"- davon mit ≥ 1 Zelle, die auch ≥ 1 NK-Transkript hat: {int((kanal_z3['mit_nk_tr'] > 0).sum())}",
        f"- davon mit ≥ 3 solchen Zellen: {int((kanal_z3['mit_nk_tr'] >= 3).sum())}",
        "",
        "## Allgemeine Abdeckung politischer Nicht-Kriegsvideos",
        "",
        "### Videos",
        "",
        md_tabelle(uebersicht),
        "",
        "### Politische Nicht-Kriegsvideos nach Periode",
        "",
        md_tabelle(nach_periode_video),
        "",
        "## Kanal-Monats-Abdeckung",
        "",
        "### Gesamt",
        "",
        md_tabelle(abdeckung_km(km, None)),
        "",
        "### Nach Periode",
        "",
        md_tabelle(abdeckung_km(km, "periode")),
        "",
        "### Nach Medientyp",
        "",
        md_tabelle(abdeckung_km(km, "medientyp")),
        "",
        "### Nach Medientyp × Periode (nur vor/nach)",
        "",
        md_tabelle(abdeckung_km(km[km["periode"] != "uebergang"].assign(
            gruppe=lambda d: d["medientyp"] + " / " + d["periode"]), "gruppe")),
        "",
        "### Nach Jahr",
        "",
        md_tabelle(abdeckung_km(jahr, "jahr")),
        "",
        "## Kanal-Ebene",
        "",
        f"- Kanäle mit ≥ 1 politischen Nicht-Kriegsvideo: {int((kanal['n_pol_nk'] > 0).sum())} von {len(kanal)}",
        f"- Kanäle ohne jedes Transkript eines pol. NK-Videos: {len(ohne_tr)}",
        "",
        "Kanäle mit mindestens k abgedeckten Kanal-Monaten (≥ 1 Transkript) **sowohl vor als auch nach** Kriegsbeginn:",
        "",
        md_tabelle(pd.DataFrame([{"k": k, "Kanäle": n} for k, n in beide.items()])),
        "",
        "### Kanäle ohne Transkripte (aber mit pol. NK-Videos)",
        "",
        md_tabelle(ohne_tr[ohne_tr["n_pol_nk"] > 0][["title", "medientyp", "n_pol_nk", "km_gesamt"]]
                   .astype({"n_pol_nk": int, "km_gesamt": int}).sort_values("n_pol_nk", ascending=False)),
        "",
    ]
    (ERGEBNIS_ORDNER / "README.md").write_text("\n".join(zeilen), encoding="utf-8")
    print("\n".join(zeilen))


if __name__ == "__main__":
    main()

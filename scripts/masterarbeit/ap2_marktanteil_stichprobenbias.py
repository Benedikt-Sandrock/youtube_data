# -*- coding: utf-8 -*-
"""
ap2_marktanteil_stichprobenbias.py - AP 2 (.claude/plans/ap2_stichprobenbias.md)

Prueft, ob der Anstieg des Marktanteils der rechten Alternativmedien (~17 % -> ~39 % bei allen
politischen Videos) ein Artefakt der Stichprobenziehung ist. Das Sample russia_longitudinal_v1
wurde nach Erfolg am Ende des Zeitraums gezogen (>50k Abonnenten zum Abrufzeitpunkt 2026), und
geloeschte Kanaele fehlen (Survivorship).

Kanalpopulationen (vorab festgelegt, siehe Plan Abschnitt 1, keine Nachjustierung):
  V0   kanonisches Sample, alle Kanaele mit gueltigem gruppe5 (Referenz)
  V0w  V0 geschnitten mit der 279er-Frage-1-Whitelist (nur Referenzzeile)
  V1   balanciertes Panel: activity_phases-Kategorie "aktivitaet_deckt_kriegsbeginn"
  V2   V1 und mindestens ein Upload in den letzten V2_LETZTE_MONATE Monaten des Fensters
  V3   V1 und Vorkriegs-Reichweite (Summe der Views aller Videos aus rel_monat -12..-1) ueber
       dem Median aller V1-Kanaele mit gueltigem gruppe5

Marktanteils-Formel: berechne_marktanteile() (echter Import ueber marktanteil_themen_plots.py),
Nenner = alle 5 rohen gruppe5-Kategorien, MIN_VIDEOS_GESAMT_PRO_PERIODE = 20. Periodenwerte sind
Mittelwerte der Monatsanteile (Monate ohne Video einer Gruppe zaehlen mit 0 %). Das
Delta (rel_monat >= 20 minus -12..-1) bekommt ein Kanal-Bootstrap-KI: Kanaele werden innerhalb
ihrer gruppe5 mit Zuruecklegen gezogen, danach werden die Monatsanteile neu berechnet.

Datenbasis: lade_basisdaten(kanalquelle="kanon") aus frage4_kriegspraemie_relative_views_plots.py
(inkl. defensivem Dedup von lade_ideologie(); der zentrale Fix ist offener Punkt fuer AP 9).
Die Whitelist-Variante V0w wird aus derselben Kanon-Basis gefiltert (daher nicht bitgleich mit
den bereits berichteten 279er-Zahlen, die den Dedup-Bug noch enthalten).

Ausgaben nach MASTERARBEIT_OUTPUTS / "ap2_stichprobenbias":
  - regression_results/marktanteil_stichprobenbias.md (Bericht, Abschnitte 1-6 laut Plan)
  - marktanteil_varianten_monat.csv (Variante x Szenario x Monat x gruppe5)
  - ap2_kanaele.csv (Kanal-Tabelle mit Aktivitaetskategorie und Variantenzugehoerigkeit)
  - marktanteil_rechts_varianten_monat.png

Ausfuehren aus dem Repo-Root:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        scripts/masterarbeit/ap2_marktanteil_stichprobenbias.py [--n-bootstrap 1000]
Liest nur SQLite-Stores und CSVs (video_registry read-only), ruft keine API auf.
"""

import argparse
import sqlite3
import sys
import warnings

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from youtube_code.config.paths import MASTERARBEIT_OUTPUTS, OUTPUTS, SRC  # noqa: E402
from youtube_code.store import video_registry  # noqa: E402
from youtube_code.step2_baseline_channels.activity_phases import (  # noqa: E402
    classify_channels_bulk, GAP_THRESHOLD_MONTHS,
)

# step6_auswertung-Module werden dort als Geschwister importiert (bare sibling import)
sys.path.insert(0, str(SRC / "step6_auswertung"))
from deskriptiv_plots import GRUPPE5_REIHENFOLGE  # noqa: E402
from prepare_channel_scores import ergaenze_periodenspalten  # noqa: E402
from frage2_sensitivitaet_plots import glaette  # noqa: E402
from frage4_kriegspraemie_relative_views_plots import (  # noqa: E402
    lade_basisdaten, KANON_SAMPLE_PFAD, PERIODE_MIN, PERIODE_MAX, SPALTE_PERIODE,
)
from marktanteil_themen_plots import (  # noqa: E402
    berechne_marktanteile, MIN_VIDEOS_GESAMT_PRO_PERIODE,
)

# =========================================================
# CONFIG
# =========================================================

GRUPPE_RECHTS = "Alternative Medien (rechts)"
OHNE_GRUPPE5 = "(ohne gruppe5)"

# Szenario -> (Titel, Filterfunktion auf die Video-Basisdaten)
SZENARIEN = {
    "alle_politik": ("Alle politischen Videos (topic_categories='Politics')",
                     lambda df: df[df["ist_politics_topic"] == True]),  # noqa: E712
    "kriegsvideos": ("Kriegsvideos (russia_ukraine_war, is_relevant=1)",
                     lambda df: df[df["ist_kriegsvideo"] == 1]),
}
HAUPTSZENARIO = "alle_politik"

# Periodenfenster (rel_monat, jeweils inklusive)
PERIODEN = {
    "vorher": (-12, -1),
    "m0_19": (0, 19),
    "ab20": (20, PERIODE_MAX),
    "ab40": (40, PERIODE_MAX),
}
PERIODEN_LABEL = {"vorher": "vorher (−12…−1)", "m0_19": "0…19", "ab20": "≥20", "ab40": "≥40"}

VARIANTEN = ["V0", "V0w", "V1", "V2", "V3"]
VARIANTEN_TITEL = {
    "V0": "kanonisch, alle gruppe5-Kanäle",
    "V0w": "V0 ∩ 279er-Whitelist",
    "V1": "balanciertes Panel (Aktivität deckt Kriegsbeginn)",
    "V2": "V1 + Uploads in den letzten 6 Monaten",
    "V3": "V1 + Vorkriegs-Reichweite > Median",
}
V2_LETZTE_MONATE = 6
KAT_BESTAND = "aktivitaet_deckt_kriegsbeginn"

N_BOOTSTRAP_DEFAULT = 1000
SEED = 20260928
ANTEIL_SCHWELLE_HAELT = 0.5  # Delta(V) >= 50 % von Delta(V0)

PFAD_WHITELIST = OUTPUTS / "segment_analysis" / "frage1_kanal_whitelist.csv"
AUSGABE = MASTERARBEIT_OUTPUTS / "ap2_stichprobenbias"
AUSGABE_REG = AUSGABE / "regression_results"
PFAD_BERICHT = AUSGABE_REG / "marktanteil_stichprobenbias.md"
PFAD_CSV_MONAT = AUSGABE / "marktanteil_varianten_monat.csv"
PFAD_CSV_KANAELE = AUSGABE / "ap2_kanaele.csv"
PFAD_PLOT = AUSGABE / "marktanteil_rechts_varianten_monat.png"

# Plot: Referenzpalette des dataviz-Skills, Slots 1-3 (all-pairs-validiert)
PLOT_FARBEN = {"V0": "#2a78d6", "V1": "#eb6834", "V3": "#1baf7a"}
PLOT_VARIANTEN = ["V0", "V1", "V3"]

# Qualitative Liste gesperrter/geloeschter Kanaele (nur Limitationen-Abschnitt)
GELOESCHTE_KANAELE = [
    ("KenFM (Ken Jebsen)", "22.01.2021", "YouTube löscht den Kanal endgültig (Corona-Richtlinien)",
     "https://www.heise.de/news/KenFM-Youtube-sperrt-Ken-Jebsens-Kanal-endgueltig-5033216.html",
     "kurz vor Fensterbeginn (rel_monat −12 = Feb. 2021): fehlt im gesamten Vorkriegsfenster"),
    ("Querdenken 711", "26.05.2021", "Löschung wegen Falschinformationen (~75k Abonnenten)",
     "https://netzpolitik.org/2021/desinformation-youtube-loescht-kanal-von-stuttgarter-querdenkern/",
     "fehlt in den Vorkriegsmonaten −9…−1 und danach"),
    ("RT DE und „Der Fehlende Part“", "29.09.2021",
     "Strike am 21.09.2021 (Corona-Fehlinformation), Umgehung über Zweitkanal, beide gelöscht",
     "https://www.dwdl.de/nachrichten/84672/youtube_loescht_konto_von_rt_deutsch_dauerhaft/",
     "fehlt in den Vorkriegsmonaten −5…−1 und danach"),
    ("RT- und Sputnik-Kanäle (europaweit)", "01.03.2022",
     "Geoblocking in Europa wegen des Kriegs, global ab 11.03.2022",
     "https://www.tagesspiegel.de/gesellschaft/panorama/youtube-blockiert-kanale-von-rt-und-sputnik-6853780.html",
     "nach Kriegsbeginn: fehlt im Nachher-Fenster (Bias dort in Gegenrichtung)"),
]
NAMENSMUSTER_GELOESCHT = r"KenFM|Querdenken|RT DE|RT Deutsch|Fehlende Part|Sputnik"


# =========================================================
# SCHRITT 1: Datenbasis und Kanalklassifikation
# =========================================================

def lade_kanal_uploads(channel_ids):
    """Alle Registry-Videos der Kanaele (auch ohne view_count) - Grundlage fuer die
    Aktivitaetsphasen, fuer V2 und fuer die Survivorship-Kennzahl 'ohne view_count'."""
    up = video_registry.get_video_stats(channel_ids=channel_ids)
    up["channel_id"] = up["channel_id"].astype(str)
    up["published_at"] = pd.to_datetime(up["published_at"], errors="coerce",
                                         utc=True).dt.tz_localize(None)
    up = up.dropna(subset=["published_at"])
    return ergaenze_periodenspalten(up)


def baue_kanaltabelle(basis, uploads, kanon_ids):
    """Eine Zeile je Kanon-Kanal: gruppe5, Aktivitaetskategorie, Provenance-Flag
    active_before_reference (Quelle der Zahl '90'), Uploads am Fensterende, Vorkriegs-Views und
    Variantenzugehoerigkeit V0-V3."""
    kanaele = pd.DataFrame({"channel_id": kanon_ids})

    ch = video_registry.get_channels(kanon_ids)[["channel_id", "title", "published_at"]]
    ch = ch.rename(columns={"published_at": "channel_created_at", "title": "kanal_titel"})
    ch["channel_id"] = ch["channel_id"].astype(str)
    ch["channel_created_at"] = pd.to_datetime(ch["channel_created_at"], errors="coerce",
                                              utc=True).dt.tz_localize(None)
    kanaele = kanaele.merge(ch.drop_duplicates("channel_id"), on="channel_id", how="left")

    kat = classify_channels_bulk(kanaele[["channel_id", "channel_created_at"]],
                                 uploads[["channel_id", "published_at"]])
    kanaele = kanaele.merge(kat[["channel_id", "kategorie", "war_group"]], on="channel_id")

    prov = pd.read_csv(KANON_SAMPLE_PFAD)
    prov["channel_id"] = prov["channel_id"].astype(str)
    prov = prov.drop_duplicates("channel_id")[["channel_id", "active_before_reference"]]
    kanaele = kanaele.merge(prov, on="channel_id", how="left")

    g5 = basis.drop_duplicates("channel_id").set_index("channel_id")["gruppe5"]
    kanaele["gruppe5"] = kanaele["channel_id"].map(g5).fillna(OHNE_GRUPPE5)

    ende_min = PERIODE_MAX - V2_LETZTE_MONATE + 1
    ende = uploads[(uploads[SPALTE_PERIODE] >= ende_min) & (uploads[SPALTE_PERIODE] <= PERIODE_MAX)]
    kanaele["uploads_fensterende"] = kanaele["channel_id"].map(
        ende.groupby("channel_id").size()).fillna(0).astype(int)

    vor = basis[(basis[SPALTE_PERIODE] >= -12) & (basis[SPALTE_PERIODE] <= -1)]
    kanaele["views_vorkrieg"] = kanaele["channel_id"].map(
        vor.groupby("channel_id")["view_count"].sum()).fillna(0)

    whitelist = set(pd.read_csv(PFAD_WHITELIST)["channel_id"].astype(str))
    hat_g5 = kanaele["gruppe5"] != OHNE_GRUPPE5
    kanaele["V0"] = hat_g5
    kanaele["V0w"] = hat_g5 & kanaele["channel_id"].isin(whitelist)
    kanaele["V1"] = hat_g5 & (kanaele["kategorie"] == KAT_BESTAND)
    kanaele["V2"] = kanaele["V1"] & (kanaele["uploads_fensterende"] > 0)
    median_v1 = kanaele.loc[kanaele["V1"], "views_vorkrieg"].median()
    kanaele["V3"] = kanaele["V1"] & (kanaele["views_vorkrieg"] > median_v1)
    kanaele.attrs["median_v1_views_vorkrieg"] = median_v1
    return kanaele


# =========================================================
# SCHRITT 2: Marktanteile je Variante + Kanal-Bootstrap
# =========================================================

MONATE = np.arange(PERIODE_MIN, PERIODE_MAX + 1)


def kanal_monat_matrizen(df_szen, kanal_ids):
    """(Views, Anzahl Videos) je Kanal x Monat als numpy-Arrays in der Reihenfolge kanal_ids.
    Kanaele ohne Video im Szenario bleiben als Nullzeile drin - sie gehoeren zur Population,
    aus der der Bootstrap zieht."""
    v = df_szen.pivot_table(index="channel_id", columns=SPALTE_PERIODE, values="view_count",
                            aggfunc="sum", fill_value=0)
    n = df_szen.pivot_table(index="channel_id", columns=SPALTE_PERIODE, values="view_count",
                            aggfunc="size", fill_value=0)
    v = v.reindex(index=kanal_ids, columns=MONATE, fill_value=0).to_numpy(dtype=float)
    n = n.reindex(index=kanal_ids, columns=MONATE, fill_value=0).to_numpy(dtype=float)
    return v, n


def anteile_aus_gruppensummen(gv, gn):
    """gv/gn: (B, G, M) Gruppensummen -> Anteile (B, G, M) in %, NaN fuer Monate unter der
    Mindestbesetzung (gleiche Regel wie berechne_marktanteile())."""
    tot_v = gv.sum(axis=1, keepdims=True)
    tot_n = gn.sum(axis=1, keepdims=True)
    gueltig = tot_n >= MIN_VIDEOS_GESAMT_PRO_PERIODE
    with np.errstate(invalid="ignore", divide="ignore"):
        anteil = gv / tot_v * 100
    return np.where(gueltig, anteil, np.nan)


def periodenmittel(anteile):
    """(B, G, M) -> {periode: (B, G)} Mittel der gueltigen Monatsanteile je Periode."""
    out = {}
    for p, (lo, hi) in PERIODEN.items():
        maske = (MONATE >= lo) & (MONATE <= hi)
        with warnings.catch_warnings():  # Periode ohne gueltigen Monat -> NaN, ohne Warnung
            warnings.simplefilter("ignore", category=RuntimeWarning)
            out[p] = np.nanmean(anteile[..., maske], axis=-1)
    return out


def berechne_variante(basis, kanaele, variante, szenario, n_boot, rng):
    """Punktschaetzer, Periodenmittel, Bootstrap-KI fuer Delta (ab20 - vorher) aller 5 Gruppen,
    Monatstabelle und Kanal-Monat-Matrizen (fuer die Konzentration) einer Variante."""
    kv = kanaele[kanaele[variante]]
    kanal_ids = kv["channel_id"].tolist()
    gruppe_je_kanal = kv["gruppe5"].to_numpy()
    df_szen = SZENARIEN[szenario][1](basis[basis["channel_id"].isin(kanal_ids)])

    # Referenz: exakt die Projektfunktion (Monatstabelle fuer CSV und Plot)
    monat = berechne_marktanteile(df_szen, MIN_VIDEOS_GESAMT_PRO_PERIODE)

    v, n = kanal_monat_matrizen(df_szen, kanal_ids)
    G = len(GRUPPE5_REIHENFOLGE)
    gv = np.zeros((1, G, len(MONATE)))
    gn = np.zeros_like(gv)
    for gi, g in enumerate(GRUPPE5_REIHENFOLGE):
        m = gruppe_je_kanal == g
        gv[0, gi] = v[m].sum(axis=0)
        gn[0, gi] = n[m].sum(axis=0)
    punkt = anteile_aus_gruppensummen(gv, gn)

    # Sanity-Check gegen berechne_marktanteile()
    ref = monat.pivot(index=SPALTE_PERIODE, columns="gruppe5", values="wert")
    for gi, g in enumerate(GRUPPE5_REIHENFOLGE):
        if g not in ref.columns:
            continue
        s = ref[g].dropna()
        idx = np.searchsorted(MONATE, s.index.to_numpy())
        abw = np.nanmax(np.abs(punkt[0, gi, idx] - s.to_numpy())) if len(s) else 0.0
        if abw > 1e-6:
            raise RuntimeError(f"[{variante}/{szenario}/{g}] Matrix-Anteile weichen von "
                               f"berechne_marktanteile() ab ({abw:.2e} pp).")

    per_punkt = {p: w[0] for p, w in periodenmittel(punkt).items()}

    # Kanal-Bootstrap innerhalb von gruppe5
    gv_b = np.zeros((n_boot, G, len(MONATE)))
    gn_b = np.zeros_like(gv_b)
    for gi, g in enumerate(GRUPPE5_REIHENFOLGE):
        idx = np.where(gruppe_je_kanal == g)[0]
        if len(idx) == 0:
            continue
        ziehung = rng.integers(0, len(idx), size=(n_boot, len(idx)))
        gewichte = np.stack([np.bincount(z, minlength=len(idx)) for z in ziehung]).astype(float)
        gv_b[:, gi] = gewichte @ v[idx]
        gn_b[:, gi] = gewichte @ n[idx]
    per_boot = periodenmittel(anteile_aus_gruppensummen(gv_b, gn_b))
    delta_boot = per_boot["ab20"] - per_boot["vorher"]

    zeilen = []
    for gi, g in enumerate(GRUPPE5_REIHENFOLGE):
        m = gruppe_je_kanal == g
        d = delta_boot[:, gi]
        d = d[np.isfinite(d)]
        zeilen.append({
            "variante": variante, "szenario": szenario, "gruppe5": g,
            "n_kanaele": int(m.sum()),
            "n_kanaele_mit_videos": int((n[m].sum(axis=1) > 0).sum()),
            "n_videos": int(n[m].sum()),
            **{f"anteil_{p}": per_punkt[p][gi] for p in PERIODEN},
            "delta": per_punkt["ab20"][gi] - per_punkt["vorher"][gi],
            "ki_lo": np.percentile(d, 2.5) if len(d) else np.nan,
            "ki_hi": np.percentile(d, 97.5) if len(d) else np.nan,
            "n_boot_gueltig": len(d),
        })

    monat = monat.assign(variante=variante, szenario=szenario)
    return {"tabelle": pd.DataFrame(zeilen), "monat": monat, "v": v, "n": n,
            "kanal_ids": kanal_ids, "gruppe_je_kanal": gruppe_je_kanal, "punkt": punkt[0]}


def einstufung(delta, ki_lo, ki_hi, delta_v0):
    """Vorab festgelegtes Entscheidungskriterium (Plan Abschnitt 1)."""
    if not np.isfinite(delta) or not np.isfinite(ki_lo):
        return "nicht bestimmbar"
    if ki_lo <= 0 <= ki_hi:
        return "hält nicht"
    if delta <= 0:
        return "hält nicht (Vorzeichenumkehr)"
    if delta >= ANTEIL_SCHWELLE_HAELT * delta_v0:
        return "hält"
    return "abgeschwächt"


# =========================================================
# SCHRITT 3: Zerlegung und Konzentration
# =========================================================

def konzentration_bestand(res_v1, kanaele):
    """Beitrag jedes rechten V1-Kanals zum Delta des V1-Gruppenanteils: Kanalanteil je Monat
    (Kanal-Views / V1-Gesamtviews des Monats), gemittelt je Periode wie der Gruppenanteil -
    die Kanalbeitraege summieren sich exakt zum Delta der Gruppe. Dazu Top-1/Top-5/HHI der
    Kanalanteile an den Gruppen-Views je Periode (Logik aus
    scripts/adhoc/marktanteil_rechts_levelshift_konzentration.py)."""
    v, n = res_v1["v"], res_v1["n"]
    tot_v = v.sum(axis=0)
    tot_n = n.sum(axis=0)
    gueltig = tot_n >= MIN_VIDEOS_GESAMT_PRO_PERIODE
    with np.errstate(invalid="ignore", divide="ignore"):
        kanalanteil = np.where(gueltig, v / tot_v * 100, np.nan)
    per = {}
    for p in ("vorher", "ab20"):
        lo, hi = PERIODEN[p]
        maske = (MONATE >= lo) & (MONATE <= hi)
        per[p] = np.nanmean(kanalanteil[:, maske], axis=1)

    m = res_v1["gruppe_je_kanal"] == GRUPPE_RECHTS
    ids = np.array(res_v1["kanal_ids"])[m]
    titel = kanaele.set_index("channel_id")["kanal_titel"]
    beitr = pd.DataFrame({
        "channel_id": ids,
        "kanal_titel": [titel.get(c, c) for c in ids],
        "anteil_vorher": per["vorher"][m],
        "anteil_ab20": per["ab20"][m],
    })
    beitr["beitrag_pp"] = beitr["anteil_ab20"] - beitr["anteil_vorher"]
    beitr = beitr.sort_values("beitrag_pp", ascending=False).reset_index(drop=True)
    delta_ges = beitr["beitrag_pp"].sum()

    konz = []
    for p in ("vorher", "ab20"):
        lo, hi = PERIODEN[p]
        maske = (MONATE >= lo) & (MONATE <= hi)
        views = v[m][:, maske].sum(axis=1)
        a = np.sort(views / views.sum())[::-1] if views.sum() > 0 else np.array([np.nan])
        konz.append({"periode": PERIODEN_LABEL[p], "top1": a[0] * 100, "top5": a[:5].sum() * 100,
                     "hhi": (a ** 2).sum() * 10000,
                     "n_kanaele_mit_videos": int((n[m][:, maske].sum(axis=1) > 0).sum())})
    return beitr, delta_ges, pd.DataFrame(konz)


# =========================================================
# SCHRITT 4: Survivorship
# =========================================================

def survivorship_suchtreffer():
    """Read-only-Diagnose der Suchlaeufe: Ausfuehrungsdatum und Metadaten-Abdeckung der Treffer
    je Suchjahr. Keine Schreibzugriffe, kein API-Aufruf."""
    con = sqlite3.connect(f"file:{video_registry.DB_PATH.as_posix()}?mode=ro", uri=True)
    try:
        runs = pd.read_sql_query(
            "SELECT MIN(executed_at) AS erster_lauf, MAX(executed_at) AS letzter_lauf, "
            "COUNT(*) AS n_laeufe FROM search_runs", con)
        treffer = pd.read_sql_query(
            "SELECT substr(r.search_start,1,4) AS suchjahr, COUNT(*) AS treffer, "
            "SUM(v.video_id IS NULL) AS ohne_videos_zeile, "
            "SUM(v.channel_id IS NULL) AS ohne_channel_id, "
            "SUM(v.view_count IS NULL) AS ohne_view_count, "
            "SUM(v.view_count IS NULL AND d.video_id IS NULL AND v.title IS NULL) "
            "  AS ohne_view_count_nie_abgerufen "
            "FROM video_search_hits h JOIN search_runs r USING(run_id) "
            "LEFT JOIN videos v USING(video_id) LEFT JOIN video_details d USING(video_id) "
            "GROUP BY 1 ORDER BY 1", con)
    finally:
        con.close()
    return runs.iloc[0], treffer


def survivorship_sample(uploads, kanaele):
    """Anteil der Registry-Videos der V0-Kanaele ohne view_count je gruppe5 x Periode (die
    Marktanteile verwerfen diese Videos)."""
    g5 = kanaele.set_index("channel_id")["gruppe5"]
    up = uploads[uploads["channel_id"].isin(kanaele.loc[kanaele["V0"], "channel_id"])].copy()
    up["gruppe5"] = up["channel_id"].map(g5)
    zeilen = []
    for g in GRUPPE5_REIHENFOLGE:
        teil = up[up["gruppe5"] == g]
        z = {"gruppe5": g}
        for p in ("vorher", "m0_19", "ab20"):
            lo, hi = PERIODEN[p]
            t = teil[(teil[SPALTE_PERIODE] >= lo) & (teil[SPALTE_PERIODE] <= hi)]
            z[p] = t["view_count"].isna().mean() * 100 if len(t) else np.nan
            z[f"n_{p}"] = len(t)
        zeilen.append(z)
    return pd.DataFrame(zeilen)


def survivorship_kanaele_ohne_views(uploads, kanaele, basis, schwelle=0.2):
    """V0-Kanaele, bei denen in einer Periode mehr als `schwelle` der Videos ohne view_count
    sind - mit ihrem Anteil an den Gruppen-Views (Hauptszenario) nach Kriegsbeginn als
    Groessenordnung fuer den moeglichen Einfluss auf den Vorkriegsanteil."""
    v0 = kanaele[kanaele["V0"]].set_index("channel_id")
    up = uploads[uploads["channel_id"].isin(v0.index)]
    szen = SZENARIEN[HAUPTSZENARIO][1](basis)
    nach = szen[szen[SPALTE_PERIODE] >= PERIODEN["ab20"][0]]
    zeilen = []
    for p in ("vorher", "m0_19", "ab20"):
        lo, hi = PERIODEN[p]
        t = up[(up[SPALTE_PERIODE] >= lo) & (up[SPALTE_PERIODE] <= hi)]
        q = t.groupby("channel_id")["view_count"].agg(n="size", ohne=lambda s: s.isna().sum())
        q = q[q["ohne"] > schwelle * q["n"]]
        for cid, r in q.iterrows():
            g = v0.loc[cid, "gruppe5"]
            gruppen_views = nach.loc[nach["gruppe5"] == g, "view_count"].sum()
            kanal_views = nach.loc[nach["channel_id"] == cid, "view_count"].sum()
            zeilen.append({"periode": PERIODEN_LABEL[p], "kanal": v0.loc[cid, "kanal_titel"],
                           "gruppe5": g, "videos": int(r["n"]), "ohne_view_count": int(r["ohne"]),
                           "anteil_gruppenviews_ab20": kanal_views / gruppen_views * 100
                           if gruppen_views else np.nan})
    return pd.DataFrame(zeilen)


# =========================================================
# SCHRITT 5: Plot
# =========================================================

def plotte_rechts(ergebnisse):
    fig, ax = plt.subplots(figsize=(10, 5.5))
    for var in PLOT_VARIANTEN:
        res = ergebnisse[(var, HAUPTSZENARIO)]
        gi = GRUPPE5_REIHENFOLGE.index(GRUPPE_RECHTS)
        y = res["punkt"][gi]
        ok = np.isfinite(y)
        x, y = MONATE[ok], y[ok]
        farbe = PLOT_FARBEN[var]
        ax.plot(x, y, color=farbe, lw=1, alpha=0.35, marker="o", ms=3)
        y_glatt = glaette(x, y)
        ax.plot(x, y_glatt, color=farbe, lw=2, label=f"{var}: {VARIANTEN_TITEL[var]}")
        ax.annotate(var, (x[-1], y_glatt[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=9, color="#52514e")
    ax.axvline(-0.5, color="#8a8983", lw=1, ls="--")
    ax.text(-0.3, ax.get_ylim()[0], " Kriegsbeginn", fontsize=8, color="#52514e", va="bottom")
    ax.set_xlabel("Monat relativ zum Kriegsbeginn")
    ax.set_ylabel("Marktanteil an Views (%)")
    ax.set_title(f"Marktanteil {GRUPPE_RECHTS} – {SZENARIEN[HAUPTSZENARIO][0]}\n"
                 "dünn = Monatswerte, dick = LOWESS", fontsize=11)
    ax.grid(axis="y", color="#e5e4df", lw=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, fontsize=9, loc="upper left", bbox_to_anchor=(0.02, 1.0))
    ax.set_ylim(top=ax.get_ylim()[1] * 1.12)  # Platz fuer die Legende ueber den Linien
    fig.tight_layout()
    fig.savefig(PFAD_PLOT, dpi=150)
    plt.close(fig)
    print(f"[Plot] {PFAD_PLOT}")


# =========================================================
# SCHRITT 6: Bericht
# =========================================================

def f1(x, nachkomma=1):
    return "–" if x is None or not np.isfinite(x) else f"{x:.{nachkomma}f}"


def md_tabelle(kopf, zeilen):
    out = ["| " + " | ".join(kopf) + " |", "|" + "---|" * len(kopf)]
    out += ["| " + " | ".join(str(z) for z in zeile) + " |" for zeile in zeilen]
    return out


def formulierung(stufe_v1, stufe_v3):
    if stufe_v1 == "hält" and stufe_v3 == "hält":
        return ("Der Anstieg des Marktanteils der rechten Alternativmedien bleibt erhalten, wenn "
                "man nur Kanäle betrachtet, die schon vor Kriegsbeginn aktiv waren, und auch "
                "unter Kanälen, die bereits vor dem Krieg reichweitenstark waren. Er ist damit "
                "nicht auf den Eintritt neuer Kanäle zurückzuführen. Die Auswahl nach Erfolg am "
                "Ende des Zeitraums lässt sich mit den verfügbaren Daten nicht vollständig "
                "korrigieren; der Befund ist deshalb als Obergrenze zu lesen.")
    if stufe_v1 == "hält":
        return ("Der Anstieg bleibt im balancierten Panel erhalten, wird aber von Kanälen "
                "getragen, die vor dem Krieg klein waren. Da das Sample nach Erfolg am Ende des "
                "Zeitraums gezogen wurde, sind gerade gewachsene kleine Kanäle überrepräsentiert; "
                "dieser Teil des Anstiegs kann ein Auswahleffekt sein.")
    if stufe_v1 == "abgeschwächt":
        return ("Der Anstieg ist im balancierten Panel deutlich kleiner (weniger als die Hälfte), "
                "aber von null verschieden. Ein erheblicher Teil des Gesamtanstiegs geht auf neu "
                "hinzugekommene Kanäle zurück und ist durch die Stichprobenziehung mitbedingt.")
    return ("Im balancierten Panel ist kein von null verschiedener Anstieg nachweisbar. Der "
            "Befund im Gesamtsample ist nicht robust gegenüber dem Eintritt neuer Kanäle und "
            "sollte nicht als Kernbotschaft formuliert werden.")


def schreibe_bericht(kanaele, tabelle, zerlegung, beitr, delta_v1_kanal, konz, runs, treffer,
                     surv_sample, surv_kanaele, n_boot, kanon_gesamt):
    z = ["# AP 2: Stichproben-Bias beim Marktanteil der rechten Alternativmedien", "",
         "Erzeugt von `scripts/masterarbeit/ap2_marktanteil_stichprobenbias.py`, Plan: "
         "`.claude/plans/ap2_stichprobenbias.md`.", ""]

    # 1 Methodik
    med = kanaele.attrs["median_v1_views_vorkrieg"]
    z += ["## 1. Methodik-Übersicht", "",
          "**Frage:** Ist der Anstieg des Marktanteils der rechten Alternativmedien nach "
          "Kriegsbeginn ein Artefakt der Stichprobe? Das Sample wurde nach Erfolg am Ende des "
          "Zeitraums gezogen (>50k Abonnenten 2026), gelöschte Kanäle fehlen.", "",
          f"**Ausgangsmenge:** kanonisches Sample `russia_longitudinal_v1` "
          f"({kanon_gesamt} Kanäle, `eligible_current_analysis == True`), Videos direkt aus der "
          f"`video_registry` (`lade_basisdaten(kanalquelle=\"kanon\")`), Fenster rel_monat "
          f"{PERIODE_MIN}…{PERIODE_MAX}. Videos ohne `view_count` sind verworfen.", "",
          "**Varianten (vorab festgelegt):**", ""]
    z += md_tabelle(["Kürzel", "Kanalpopulation", "adressiert"], [
        ["V0", "alle Kanäle mit gültigem gruppe5", "Referenz"],
        ["V0w", "V0 ∩ 279er-Whitelist (`frage1_kanal_whitelist.csv`)", "Referenzzeile"],
        ["V1", f"`activity_phases`-Kategorie `{KAT_BESTAND}` (Lückenschwelle "
               f"{GAP_THRESHOLD_MONTHS} Monate → mind. ein Upload in −12…−1)", "Eintritt neuer Kanäle"],
        ["V2", f"V1 und ≥1 Upload in rel_monat {PERIODE_MAX - V2_LETZTE_MONATE + 1}…{PERIODE_MAX}",
         "streng balanciert, informativ"],
        ["V3", f"V1 und Summe der Views aller Videos aus −12…−1 > Median der V1-Kanäle "
               f"({med:,.0f} Views)", "Auswahl nach Erfolg am Ende (Näherung)"],
    ])
    z += ["", "**Formel** (`berechne_marktanteile()`, identisch zu `marktanteil_themen_plots.py`):",
          "", "```",
          "Anteil(g, Monat) = Σ view_count(g, Szenario, Monat) / Σ view_count(alle 5 gruppe5, "
          "Szenario, Monat) × 100", "```", "",
          f"Monate mit weniger als {MIN_VIDEOS_GESAMT_PRO_PERIODE} Videos (über alle 5 Gruppen) "
          "entfallen. Der Nenner umfasst jeweils nur die Kanäle der Variante.", "",
          "**Perioden:** Mittelwert der Monatsanteile in " +
          ", ".join(f"{PERIODEN_LABEL[p]}" for p in PERIODEN) +
          ". Monate, in denen eine Gruppe kein Video hat, zählen mit 0 %. Abweichend von "
          "`marktanteil_rechts_levelshift_konzentration.py` (dort „<20“ inkl. Vorkriegsmonaten) "
          "ist die Zwischenperiode hier 0…19; das Entscheidungskriterium ist davon nicht betroffen. "
          "Deshalb liegt der Vorher-Wert der rechten Alternativmedien hier niedriger als die "
          "~17 % aus `zentrale_ergebnisse.md` (Kernbotschaft 1), die die Monate 0…19 einschließen.",
          "",
          "**Δ** = Anteil(≥20) − Anteil(vorher). **Szenarien:** Hauptszenario alle politischen "
          "Videos (`ist_politics_topic`), Nebenszenario Kriegsvideos.", "",
          f"**Bootstrap:** {n_boot} Ziehungen, Kanäle mit Zurücklegen innerhalb ihrer gruppe5 "
          f"(Seed {SEED}); je Ziehung werden Monatsanteile, Periodenmittel und Δ neu berechnet. "
          "95-%-Perzentil-KI. Kanäle ohne Video im Szenario bleiben in der Ziehungsmenge.", "",
          "**Entscheidungskriterium** (Hauptvariante V1, Robustheit V3, Gruppe rechte "
          "Alternativmedien, Hauptszenario):", "",
          "- **hält:** Δ(V) ≥ 50 % von Δ(V0) und KI schließt 0 aus",
          "- **abgeschwächt:** Δ(V) > 0 mit KI ohne 0, aber < 50 % von Δ(V0)",
          "- **hält nicht:** KI von Δ(V) enthält 0", ""]

    # 2 Kategorien
    z += ["## 2. Kategorien der Kanalaktivität je gruppe5", "",
          f"Alle {kanon_gesamt} Kanon-Kanäle, Klassifikation mit `classify_channels_bulk()` "
          "(Uploads aus der `video_registry`, Gründungsdatum aus `channels`).", ""]
    kt = pd.crosstab(kanaele["kategorie"], kanaele["gruppe5"], margins=True, margins_name="Summe")
    spalten = [g for g in GRUPPE5_REIHENFOLGE + [OHNE_GRUPPE5] if g in kt.columns] + ["Summe"]
    z += md_tabelle(["Kategorie"] + spalten,
                    [[idx] + [int(kt.loc[idx, s]) for s in spalten] for idx in kt.index])
    n90 = int((kanaele["active_before_reference"] == False).sum())  # noqa: E712
    ab = pd.crosstab(kanaele["kategorie"], kanaele["active_before_reference"])
    z += ["", f"**Herkunft der Zahl „90“:** `channel_sample_provenance.csv`, Spalte "
          f"`active_before_reference == False` (erstes beobachtetes Video am oder nach dem "
          f"24.02.2022, `build_channel_provenance.py`): {n90} Kanäle. Abgleich mit den "
          "Aktivitätskategorien:", ""]
    z += md_tabelle(["Kategorie"] + [f"active_before_reference={c}" for c in ab.columns],
                    [[i] + [int(ab.loc[i, c]) for c in ab.columns] for i in ab.index])
    neu_rechts = kanaele[(kanaele["gruppe5"] == GRUPPE_RECHTS) & (kanaele["kategorie"] != KAT_BESTAND)]
    alle_rechts = (kanaele["gruppe5"] == GRUPPE_RECHTS).sum()
    z += ["", f"**Rechte Alternativmedien:** {len(neu_rechts)} von {alle_rechts} Kanälen sind "
          f"nicht in V1 (keine Aktivitätsphase über den Kriegsbeginn), davon "
          f"{int((neu_rechts['war_group'] == 'nachkriegskanal').sum())} Nachkriegskanäle.", ""]
    zn = []
    for var in VARIANTEN:
        zn.append([var] + [int(((kanaele[var]) & (kanaele["gruppe5"] == g)).sum())
                           for g in GRUPPE5_REIHENFOLGE] + [int(kanaele[var].sum())])
    z += ["Kanäle je Variante:", ""]
    z += md_tabelle(["Variante"] + GRUPPE5_REIHENFOLGE + ["Summe"], zn)
    z += [""]

    # 3 Level-Shift
    z += ["## 3. Level-Shift-Tabellen mit Δ und Bootstrap-KI", ""]
    for szen, (titel, _) in SZENARIEN.items():
        t = tabelle[tabelle["szenario"] == szen]
        z += [f"### {titel}", "", f"**{GRUPPE_RECHTS}:**", ""]
        r = t[t["gruppe5"] == GRUPPE_RECHTS].set_index("variante")
        dv0 = r.loc["V0", "delta"]
        zeilen = []
        for var in VARIANTEN:
            x = r.loc[var]
            stufe = einstufung(x["delta"], x["ki_lo"], x["ki_hi"], dv0) if var != "V0" else "–"
            anteil_v0 = f"{x['delta'] / dv0 * 100:.0f} %" if np.isfinite(dv0) and dv0 else "–"
            zeilen.append([var, int(x["n_kanaele"]), int(x["n_kanaele_mit_videos"]),
                           int(x["n_videos"])] + [f1(x[f"anteil_{p}"]) for p in PERIODEN] +
                          [f1(x["delta"]), f"[{f1(x['ki_lo'])}; {f1(x['ki_hi'])}]", anteil_v0, stufe])
        z += md_tabelle(["Variante", "Kanäle", "mit Videos", "Videos"] +
                        [f"Anteil {PERIODEN_LABEL[p]}" for p in PERIODEN] +
                        ["Δ (pp)", "95-%-KI", "Δ / Δ(V0)", "Einstufung"], zeilen)
        z += ["", "**Alle Gruppen (Δ mit KI):**", ""]
        zeilen = []
        for g in GRUPPE5_REIHENFOLGE:
            zeile = [g]
            for var in VARIANTEN:
                x = t[(t["gruppe5"] == g) & (t["variante"] == var)].iloc[0]
                zeile.append(f"{f1(x['anteil_vorher'])} → {f1(x['anteil_ab20'])}: "
                             f"{f1(x['delta'])} [{f1(x['ki_lo'])}; {f1(x['ki_hi'])}]")
            zeilen.append(zeile)
        z += md_tabelle(["gruppe5"] + VARIANTEN, zeilen)
        z += ["", "Zellen: Anteil vorher → Anteil ≥20: Δ [95-%-KI], jeweils in %/pp.", ""]

    # 4 Zerlegung
    zl = zerlegung
    z += ["## 4. Zerlegung des Anstiegs und Konzentration", "",
          f"Rechte Alternativmedien, {SZENARIEN[HAUPTSZENARIO][0]}, vorher (−12…−1) gegen "
          "nachher (≥20):", ""]
    z += md_tabelle(["Komponente", "pp"], [
        ["Δ gesamt = Anteil≥20(V0) − Anteil_vorher(V0)", f1(zl["gesamt"])],
        ["(a) Wachstum der Bestandskanäle = Anteil≥20(V1) − Anteil_vorher(V0)", f1(zl["a"])],
        ["(b) Beitrag der Nicht-Bestandskanäle = Anteil≥20(V0) − Anteil≥20(V1)", f1(zl["b"])],
        ["Kontrolle: Anteil_vorher(V1) − Anteil_vorher(V0)", f1(zl["abw_vorher"])],
        ["Δ innerhalb V1 = Anteil≥20(V1) − Anteil_vorher(V1)", f1(zl["delta_v1"])],
    ])
    z += ["", f"(a) + (b) = Δ gesamt. Anteil (a) am Gesamtanstieg: "
          f"{f1(zl['a'] / zl['gesamt'] * 100, 0)} %. Die Nicht-Bestandskanäle in (b) sind "
          "überwiegend neue Kanäle, dazu reaktivierte und vor dem Krieg eingeschlafene Kanäle "
          "(siehe Abschnitt 2). (b) enthält auch den Nenner-Effekt: Neue Kanäle anderer Gruppen "
          "senken den Anteil der rechten Kanäle in V0.", "",
          "**Konzentration innerhalb von (a):** Beitrag der einzelnen rechten V1-Kanäle zum "
          f"V1-internen Δ ({f1(delta_v1_kanal)} pp; Kanalanteil = Kanal-Views / alle V1-Views "
          "des Monats, gemittelt wie der Gruppenanteil, Summe der Beiträge = Δ).", ""]
    top1 = beitr["beitrag_pp"].iloc[:1].sum()
    top5 = beitr["beitrag_pp"].iloc[:5].sum()
    z += [f"- Top-1-Kanal: {f1(top1)} pp = {f1(top1 / delta_v1_kanal * 100, 0)} % des Zuwachses",
          f"- Top-5-Kanäle: {f1(top5)} pp = {f1(top5 / delta_v1_kanal * 100, 0)} % des Zuwachses",
          f"- Kanäle mit positivem Beitrag: {int((beitr['beitrag_pp'] > 0).sum())} von {len(beitr)}",
          ""]
    z += md_tabelle(["Rang", "Kanal", "Anteil vorher", "Anteil ≥20", "Beitrag (pp)"],
                    [[i + 1, r.kanal_titel, f1(r.anteil_vorher, 2), f1(r.anteil_ab20, 2),
                      f1(r.beitrag_pp, 2)] for i, r in beitr.head(10).iterrows()])
    z += ["", "Konzentration der Views innerhalb der rechten V1-Kanäle "
          "(Anteile an den Gruppen-Views der Periode):", ""]
    z += md_tabelle(["Periode", "Top-1 (%)", "Top-5 (%)", "HHI", "Kanäle mit Videos"],
                    [[r.periode, f1(r.top1), f1(r.top5), f1(r.hhi, 0), r.n_kanaele_mit_videos]
                     for r in konz.itertuples()])
    z += [""]

    # 5 Survivorship
    z += ["## 5. Survivorship", "",
          "### Quantitativ", "",
          f"**Suchläufe:** {runs['n_laeufe']} Läufe in `search_runs`, ausgeführt zwischen "
          f"{runs['erster_lauf'][:10]} und {runs['letzter_lauf'][:10]}. Die Suchfenster reichen "
          "zwar zurück bis 2021, die Suche selbst lief aber erst 2026. Videos und Kanäle, die "
          "vorher gelöscht wurden, konnten deshalb gar nicht gefunden werden. Treffer ohne "
          "Metadaten messen folglich keine Löschungen:", ""]
    z += md_tabelle(["Suchjahr", "Treffer", "ohne `videos`-Zeile", "ohne channel_id",
                     "ohne view_count", "davon nie abgerufen (kein Titel, keine Details)"],
                    [[r.suchjahr, r.treffer, r.ohne_videos_zeile, r.ohne_channel_id,
                      r.ohne_view_count, r.ohne_view_count_nie_abgerufen]
                     for r in treffer.itertuples()])
    z += ["", "Jeder Treffer hat eine `videos`-Zeile mit channel_id. Fehlende view_counts "
          "betreffen Videos von Kanälen außerhalb des Samples, für die nie Statistiken "
          "abgerufen wurden („nie abgerufen“ oder nur Titel aus der Suche). Ein "
          "Metadaten-Refetch über `metadata_collection.py` würde nur Löschungen **nach** "
          "Juni 2026 zeigen und ist für die Frage wertlos. **Deshalb wurde kein Refetch "
          "durchgeführt.**", "",
          "**Innerhalb des Samples:** Anteil der Registry-Videos der V0-Kanäle ohne "
          "view_count (in den Marktanteilen verworfen):", ""]
    z += md_tabelle(["gruppe5", "vorher (%)", "0…19 (%)", "≥20 (%)", "Videos vorher"],
                    [[r.gruppe5, f1(r.vorher), f1(r.m0_19), f1(r.ab20), r.n_vorher]
                     for r in surv_sample.itertuples()])
    z += ["", "Kanäle mit mehr als 20 % Videos ohne view_count in einer Periode (Größenordnung: "
          "Anteil des Kanals an den Views seiner Gruppe im Hauptszenario ab Monat 20):", ""]
    if len(surv_kanaele):
        z += md_tabelle(["Periode", "Kanal", "gruppe5", "Videos", "ohne view_count",
                         "Anteil an Gruppen-Views ≥20 (%)"],
                        [[r.periode, r.kanal, r.gruppe5, r.videos, r.ohne_view_count,
                          f1(r.anteil_gruppenviews_ab20, 2)] for r in surv_kanaele.itertuples()])
        z += ["", "Im Chat geprüft (2026-09-28) wurde der Vorkriegsfall „Habibiflo Dawah "
              "Produktion“: Dort fehlen neben view_count auch Dauer und `video_details` für alle "
              "Videos bis März 2022, ab April 2022 sind sie vollständig. Die Videos wurden also nie "
              "abgerufen und sind nicht gelöscht. Der größte Anteil eines aufgeführten Kanals an "
              f"den Gruppen-Views liegt bei {f1(surv_kanaele['anteil_gruppenviews_ab20'].max(), 2)} %. "
              "Die Lücken verschieben die Marktanteile damit kaum."]
    else:
        z += ["keine"]
    treffer_namen = kanaele[kanaele["kanal_titel"].fillna("").str.contains(
        NAMENSMUSTER_GELOESCHT, case=False, regex=True)]
    z += ["", "### Qualitativ: gesperrte oder gelöschte Kanäle im Suchzeitraum", ""]
    z += md_tabelle(["Kanal", "Datum", "Vorgang", "Wirkung auf das Fenster", "Quelle"],
                    [[k, d, v, w, f"[Link]({u})"] for k, d, v, u, w in GELOESCHTE_KANAELE])
    z += ["", "Namensabgleich mit dem Kanon-Sample (`" + NAMENSMUSTER_GELOESCHT + "`): " +
          (", ".join(treffer_namen["kanal_titel"]) if len(treffer_namen) else "kein Treffer") + ".",
          "",
          "**Richtung des Bias:** Kanäle, die vor dem Krieg gelöscht wurden (KenFM, "
          "Querdenken 711, RT DE), fehlen im Vorkriegsfenster. Soweit sie als rechte "
          "Alternativmedien einzuordnen wären, ist der Vorkriegsanteil zu niedrig und der "
          "Anstieg überschätzt. Die Sperrung der RT-/Sputnik-Kanäle ab März 2022 wirkt in die "
          "Gegenrichtung (fehlende Reichweite nach Kriegsbeginn). Zuschauer gelöschter Kanäle "
          "können zudem zu verbliebenen Kanälen im Sample abgewandert sein; dann ist ein Teil "
          "des gemessenen Anstiegs eine Verlagerung und kein Wachstum der Nachfrage. Die Größe "
          "lässt sich mit den Projektdaten nicht beziffern.", ""]

    # 6 Einstufung
    r = tabelle[(tabelle["szenario"] == HAUPTSZENARIO) & (tabelle["gruppe5"] == GRUPPE_RECHTS)
                ].set_index("variante")
    dv0 = r.loc["V0", "delta"]
    st = {v: einstufung(r.loc[v, "delta"], r.loc[v, "ki_lo"], r.loc[v, "ki_hi"], dv0)
          for v in ("V1", "V3")}
    z += ["## 6. Einstufung", "",
          f"- Δ(V0) = {f1(dv0)} pp [{f1(r.loc['V0', 'ki_lo'])}; {f1(r.loc['V0', 'ki_hi'])}]",
          f"- Δ(V1) = {f1(r.loc['V1', 'delta'])} pp [{f1(r.loc['V1', 'ki_lo'])}; "
          f"{f1(r.loc['V1', 'ki_hi'])}] → **{st['V1']}**",
          f"- Δ(V3) = {f1(r.loc['V3', 'delta'])} pp [{f1(r.loc['V3', 'ki_lo'])}; "
          f"{f1(r.loc['V3', 'ki_hi'])}] → **{st['V3']}**", "",
          "**Formulierung für die Arbeit:** " + formulierung(st["V1"], st["V3"]), "",
          "Einschränkungen: V3 ist nur eine Näherung an eine Auswahl nach Anfangsgröße, weil "
          "historische Abonnentenzahlen fehlen. Kanäle, die 2021 groß waren und bis 2026 unter "
          "die Aufnahmeschwelle gefallen sind, fehlen auch in V3. Survivorship ist nur "
          "qualitativ abschätzbar (Abschnitt 5).", ""]

    AUSGABE_REG.mkdir(parents=True, exist_ok=True)
    PFAD_BERICHT.write_text("\n".join(z) + "\n", encoding="utf-8")
    print(f"[Bericht] {PFAD_BERICHT}")
    return st


# =========================================================
# MAIN
# =========================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-bootstrap", type=int, default=N_BOOTSTRAP_DEFAULT)
    args = ap.parse_args()
    rng = np.random.default_rng(SEED)
    AUSGABE.mkdir(parents=True, exist_ok=True)

    basis = lade_basisdaten(kanalquelle="kanon")
    prov = pd.read_csv(KANON_SAMPLE_PFAD)
    kanon_ids = (prov[prov["eligible_current_analysis"] == True]["channel_id"]  # noqa: E712
                 .astype(str).drop_duplicates().tolist())

    uploads = lade_kanal_uploads(kanon_ids)
    kanaele = baue_kanaltabelle(basis, uploads, kanon_ids)
    kanaele.to_csv(PFAD_CSV_KANAELE, index=False, encoding="utf-8")
    print(f"[Kanaele] {PFAD_CSV_KANAELE}")
    print(kanaele[VARIANTEN].sum().to_string())

    ergebnisse, tabellen, monate = {}, [], []
    for szen in SZENARIEN:
        for var in VARIANTEN:
            res = berechne_variante(basis, kanaele, var, szen, args.n_bootstrap, rng)
            ergebnisse[(var, szen)] = res
            tabellen.append(res["tabelle"])
            monate.append(res["monat"])
    tabelle = pd.concat(tabellen, ignore_index=True)
    pd.concat(monate, ignore_index=True)[
        ["variante", "szenario", SPALTE_PERIODE, "gruppe5", "wert", "views_summe", "n_videos"]
    ].to_csv(PFAD_CSV_MONAT, index=False, encoding="utf-8")
    print(f"[CSV] {PFAD_CSV_MONAT}")

    r = tabelle[(tabelle["szenario"] == HAUPTSZENARIO) & (tabelle["gruppe5"] == GRUPPE_RECHTS)
                ].set_index("variante")
    zerlegung = {
        "gesamt": r.loc["V0", "anteil_ab20"] - r.loc["V0", "anteil_vorher"],
        "a": r.loc["V1", "anteil_ab20"] - r.loc["V0", "anteil_vorher"],
        "b": r.loc["V0", "anteil_ab20"] - r.loc["V1", "anteil_ab20"],
        "abw_vorher": r.loc["V1", "anteil_vorher"] - r.loc["V0", "anteil_vorher"],
        "delta_v1": r.loc["V1", "delta"],
    }
    beitr, delta_v1_kanal, konz = konzentration_bestand(ergebnisse[("V1", HAUPTSZENARIO)], kanaele)

    runs, treffer = survivorship_suchtreffer()
    surv_sample = survivorship_sample(uploads, kanaele)
    surv_kanaele = survivorship_kanaele_ohne_views(uploads, kanaele, basis)

    plotte_rechts(ergebnisse)
    st = schreibe_bericht(kanaele, tabelle, zerlegung, beitr, delta_v1_kanal, konz, runs,
                          treffer, surv_sample, surv_kanaele, args.n_bootstrap, len(kanon_ids))
    print(f"\n[Einstufung] V1: {st['V1']}, V3: {st['V3']}")
    print(r[["n_kanaele", "anteil_vorher", "anteil_ab20", "delta", "ki_lo", "ki_hi"]].round(2)
          .to_string())


if __name__ == "__main__":
    main()

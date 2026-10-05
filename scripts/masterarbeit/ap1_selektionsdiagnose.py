# -*- coding: utf-8 -*-
"""
ap1_selektionsdiagnose.py - AP 1, Schritt 1 (.claude/plans/masterarbeit_strategie.md)

Diagnose der Selektions-Asymmetrie in Frage 1. Der Schnellcheck zeigte, dass
Nicht-Kriegsvideos nach Kriegsbeginn einen viel niedrigeren Populismus haben
als vorher (Volkszentrismus 0,90 -> 0,23). Das Skript rekonstruiert, WOHER die
klassifizierten Videos vor und nach Kriegsbeginn stammen. Anschliessend prueft
es die Hypothesen (a)-(e) aus der Strategie-Datei.

Datensatz auf Videoebene: alle Videos in channel_video_populism.csv, deren
Kanal auf der 279er-Whitelist steht (frage1_kanal_whitelist.csv). Dazu kommen
folgende Merkmale und Quellen.

  - ist_kriegsvideo, duration_seconds, category_id: aus channel_video_erfolg.csv
    (fehlt ein Video dort: topic_relevant_video_ids / duration_lookup /
    category_id_lookup aus der video_registry)
  - run_id, dataset_id, n_segmente, Zeichen je Segment, Anteil
    kodierbar == False, Anteil ukraine_bezug: aus
    prepare_channel_scores._lade_llm_ergebnisse("POPULISMUS_P"), also exakt
    dieselben Rohzeilen, die auch channel_video_populism.csv speisen.
    Alternative Aggregationen fuer (d): nur erstes Segment (segment_index
    minimal) bzw. Maximum ueber die Segmente.
  - politics_final, politics_title, politics_title_desc, interval_index:
    aus screening_state_store.get_state()
  - topic_politics: YouTube-topic_categories enthaelt Politics
    (video_registry.politics_topic_lookup)
  - kw_treffer / kw_teiltreffer: matched_keywords fuer russia_ukraine_war
    (video_registry.get_topic_relevance). kw_teiltreffer bedeutet: es gibt
    Keyword-Treffer, aber is_relevant == 0.
  - in_political_nonwar_ids: Video steht in
    step4_transcript_download/political_nonwar_ids.json (Zelle-auffuellen-Auswahl
    "politisch, nicht Krieg")
  - gruppe5: nach baue_gruppe5() aus deskriptiv_plots.py

Ausgaben nach MASTERARBEIT_OUTPUTS / "ap1_selektion":
  - ap1_diagnose_videos.csv: der Videodatensatz (Grundlage fuer
    ap1_selektionscheck.py)
  - regression_results/frage1_selektionsdiagnose.md: Diagnosebericht mit
    Methodik-Uebersicht, Abschnitten A-D und Urteilen zu den Hypothesen

Ausfuehren aus dem Repo-Root:
    PYTHONPATH=src python scripts/masterarbeit/ap1_selektionsdiagnose.py
Das Skript liest nur CSVs und SQLite-Stores und ruft keine API und kein LLM auf.
"""

import json
import sys

import numpy as np
import pandas as pd

from youtube_code.config.paths import MASTERARBEIT_OUTPUTS, OUTPUTS, SRC
from youtube_code.config.settings import MIN_VIDEO_DURATION_SECONDS
from youtube_code.store import screening_state_store, video_registry

# step6_auswertung-Module werden dort als Geschwister importiert (bare sibling import)
sys.path.insert(0, str(SRC / "step6_auswertung"))
from prepare_channel_scores import _lade_llm_ergebnisse, _korrigiere_populismus  # noqa: E402
from deskriptiv_aggregation import lade_medientyp, lade_ideologie  # noqa: E402
from deskriptiv_plots import baue_gruppe5, GRUPPE5_REIHENFOLGE  # noqa: E402
from bericht_utils import post_dummy_test  # noqa: E402

# =========================================================
# CONFIG
# =========================================================

SEG = OUTPUTS / "segment_analysis"
PFAD_POPULISMUS = SEG / "channel_video_populism.csv"
PFAD_ERFOLG = SEG / "channel_video_erfolg.csv"
PFAD_WHITELIST = SEG / "frage1_kanal_whitelist.csv"
PFAD_NONWAR_IDS = SRC / "step4_transcript_download" / "political_nonwar_ids.json"

AUSGABE = MASTERARBEIT_OUTPUTS / "ap1_selektion"
AUSGABE_REG = AUSGABE / "regression_results"
PFAD_VIDEOS = AUSGABE / "ap1_diagnose_videos.csv"
PFAD_BERICHT = AUSGABE_REG / "frage1_selektionsdiagnose.md"

DIMENSIONEN = ["volkszentrismus", "antielitismus", "manichaeische_moralisierung",
               "populismus_gesamt", "emotionale_intensitaet"]
KERN = ["volkszentrismus", "antielitismus", "manichaeische_moralisierung"]

# Analysefenster wie frage1_populismus_bericht.py (GRANULARITAETEN["monat"])
MONAT_MIN, MONAT_MAX = -12, 42

# Kriegsfenster aus run_transcript_selection.py (MODE war_period)
KRIEGSFENSTER = ("2022-02-20", "2022-03-10")

DAUER_BAENDER = [0, 300, 900, 1800, 3600, np.inf]
DAUER_LABELS = ["<5 min", "5-15 min", "15-30 min", "30-60 min", ">60 min"]


# =========================================================
# HILFSFUNKTIONEN
# =========================================================

def md_tabelle(df, float_fmt="{:.3f}", index=True):
    """DataFrame -> Markdown-Tabelle (ohne tabulate-Abhaengigkeit)."""
    d = df.reset_index() if index else df.copy()
    spalten = [str(c) for c in d.columns]
    zeilen = ["| " + " | ".join(spalten) + " |", "|" + "---|" * len(spalten)]
    for _, r in d.iterrows():
        werte = []
        for v in r.values:
            if isinstance(v, (float, np.floating)):
                werte.append("" if pd.isna(v) else float_fmt.format(v))
            else:
                werte.append(str(v))
        zeilen.append("| " + " | ".join(werte) + " |")
    return "\n".join(zeilen)


def zelle(df):
    """Zellenbezeichnung vor/nach x Krieg/Nichtkrieg."""
    return (np.where(df["post"] == 1, "nach", "vor") + " / "
            + np.where(df["ist_kriegsvideo"] == 1, "Krieg", "Nichtkrieg"))


def post_effekt_nichtkrieg(df, dimension="populismus_gesamt", maske=None):
    """Kanal-FE-Post-Dummy auf Kanal-Monat-Mitteln NUR der Nicht-Kriegsvideos
    (Spezifikation 3 des Schnellchecks), optional auf eine Teilmenge eingeschraenkt.
    Gibt (koeffizient, p, n_videos_vor, n_videos_nach, n_kanaele) zurueck."""
    d = df[(df["ist_kriegsvideo"] == 0) & df["im_fenster"]]
    if maske is not None:
        d = d[maske.reindex(d.index).fillna(False).astype(bool)]
    n_vor, n_nach = int((d["post"] == 0).sum()), int((d["post"] == 1).sum())
    agg = d.groupby(["channel_id", "rel_monat"], as_index=False)[dimension].mean()
    # nur Kanaele mit Beobachtungen auf beiden Seiten tragen zur Identifikation bei
    res = post_dummy_test(agg, dimension, "rel_monat", bezeichnung="teilmenge") if len(agg) else None
    if not res:
        return np.nan, np.nan, n_vor, n_nach, 0
    return res["koeffizient_post"], res["p"], n_vor, n_nach, res["n_kanaele"]


# =========================================================
# DATEN AUFBAUEN
# =========================================================

def lade_rohsegmente():
    raw = _lade_llm_ergebnisse("POPULISMUS_P")
    raw = _korrigiere_populismus(raw)
    raw["nicht_kodierbar"] = (raw["kodierbar"] == False).astype(int)  # noqa: E712
    raw["ukraine_bezug_num"] = raw["ukraine_bezug"].map({True: 1, False: 0, "True": 1, "False": 0})
    return raw


def video_merkmale_aus_segmenten(raw):
    raw = raw.sort_values(["video_id", "segment_index"])
    basis = raw.groupby("video_id").agg(
        run_id=("run_id", "first"),
        dataset_id=("dataset_id", "first"),
        n_segmente=("segment_id", "nunique"),
        zeichen_gesamt=("n_chars", "sum"),
        zeichen_je_segment=("n_chars", "mean"),
        anteil_nicht_kodierbar=("nicht_kodierbar", "mean"),
        anteil_ukraine_bezug=("ukraine_bezug_num", "mean"),
    )
    raw = raw.copy()
    raw["populismus_gesamt"] = raw[KERN].mean(axis=1)
    erstes = raw.groupby("video_id").first()[KERN + ["populismus_gesamt"]].add_suffix("_erstes_seg")
    maximum = raw.groupby("video_id")[KERN + ["populismus_gesamt"]].max().add_suffix("_max")
    return basis.join(erstes).join(maximum).reset_index()


def screening_merkmale(video_ids):
    st = screening_state_store.get_state(video_ids=list(video_ids))
    st = st[["video_id", "interval_index", "politics_title", "politics_title_desc",
             "politics_final", "screening_round"]].drop_duplicates("video_id")
    st["in_screening"] = 1
    return st


def keyword_merkmale(video_ids):
    t = video_registry.get_topic_relevance("russia_ukraine_war", video_ids=list(video_ids))
    t = t[["video_id", "is_relevant", "matched_keywords"]].copy()

    def _parse(s):
        try:
            return json.loads(s) if isinstance(s, str) else []
        except ValueError:
            return []
    kws = t["matched_keywords"].map(_parse)
    t["kw_treffer"] = kws.map(len).gt(0).astype(int)
    t["kw_nur_wide_desc"] = kws.map(lambda k: k == ["ukr_wide_desc"]).astype(int)
    t["kw_stufen"] = kws.map(lambda k: ",".join(sorted(k)))
    t = t.rename(columns={"is_relevant": "kw_is_relevant"}).drop(columns="matched_keywords")
    return t


def baue_datensatz():
    pop = pd.read_csv(PFAD_POPULISMUS)
    whitelist = set(pd.read_csv(PFAD_WHITELIST)["channel_id"].astype(str))
    pop = pop[pop["channel_id"].astype(str).isin(whitelist)].copy()
    print(f"[Populismus] {len(pop)} Videos, {pop['channel_id'].nunique()} Whitelist-Kanaele")

    erfolg = pd.read_csv(PFAD_ERFOLG, usecols=["video_id", "published_at", "ist_kriegsvideo",
                                                 "duration_seconds", "category_id"])
    df = pop.merge(erfolg, on="video_id", how="left")

    ids = df["video_id"].tolist()
    fehlt = df["ist_kriegsvideo"].isna()
    if fehlt.any():
        print(f"[Hinweis] {int(fehlt.sum())} Videos ohne Zeile in channel_video_erfolg.csv -> "
              f"Merkmale aus video_registry")
        krieg_ids = video_registry.topic_relevant_video_ids("russia_ukraine_war")
        df.loc[fehlt, "ist_kriegsvideo"] = df.loc[fehlt, "video_id"].isin(krieg_ids).astype(int)
        dauer = video_registry.duration_lookup(df.loc[fehlt, "video_id"])
        df.loc[fehlt, "duration_seconds"] = df.loc[fehlt, "video_id"].map(dauer)
        kat = video_registry.category_id_lookup(df.loc[fehlt, "video_id"])
        df.loc[fehlt, "category_id"] = df.loc[fehlt, "video_id"].map(kat)
    df["ist_kriegsvideo"] = df["ist_kriegsvideo"].astype(int)
    df["category_id"] = df["category_id"].astype("string").str.replace(r"\.0$", "", regex=True)

    raw = lade_rohsegmente()
    df = df.merge(video_merkmale_aus_segmenten(raw[raw["video_id"].isin(ids)]), on="video_id", how="left")
    df = df.merge(screening_merkmale(ids), on="video_id", how="left")
    df["in_screening"] = df["in_screening"].fillna(0).astype(int)
    df = df.merge(keyword_merkmale(ids), on="video_id", how="left")
    df["kw_teiltreffer"] = ((df["kw_treffer"] == 1) & (df["kw_is_relevant"] == 0)).astype(int)

    pol = video_registry.politics_topic_lookup(ids)
    df["topic_politics"] = df["video_id"].map(pol)  # NaN = keine video_details-Zeile

    with open(PFAD_NONWAR_IDS, encoding="utf-8") as f:
        nonwar_ids = set(json.load(f))
    df["in_political_nonwar_ids"] = df["video_id"].isin(nonwar_ids).astype(int)

    med = lade_medientyp().drop_duplicates("channel_id")
    ideo = lade_ideologie().drop_duplicates("channel_id")
    df = df.merge(med, on="channel_id", how="left").merge(ideo, on="channel_id", how="left")
    g5 = baue_gruppe5(df[["channel_id", "medientyp", "ideologie_gruppe"]].drop_duplicates("channel_id"))
    df = df.merge(g5[["channel_id", "gruppe5"]], on="channel_id", how="left")

    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce")
    df["post"] = (df["rel_monat"] >= 0).astype(int)
    df["im_fenster"] = df["rel_monat"].between(MONAT_MIN, MONAT_MAX)
    df["zelle"] = zelle(df)
    df["dauer_band"] = pd.cut(df["duration_seconds"], DAUER_BAENDER, labels=DAUER_LABELS, right=False)
    df["herkunft"] = rekonstruiere_herkunft(df)
    return df, raw


def rekonstruiere_herkunft(df):
    """Heuristische Rekonstruktion des Auswahlwegs. Es gibt dafuer keine gespeicherte
    Spalte, deshalb gilt die Prioritaet von oben nach unten."""
    pf1 = df["politics_final"] == 1
    kf = df["published_at"].between(*KRIEGSFENSTER)
    bedingungen = [
        df["interval_index"].between(0, 3) & pf1,
        df["interval_index"].eq(-1),
        (df["interval_index"] >= 4) & pf1,
        df["kw_is_relevant"].isna() & (df["duration_seconds"] < MIN_VIDEO_DURATION_SECONDS),
        df["in_political_nonwar_ids"].eq(1),
        df["ist_kriegsvideo"].eq(1) & kf,
        df["ist_kriegsvideo"].eq(1),
    ]
    labels = ["baseline_vor (Intervall 0-3, pf=1)", "baseline_nach (Intervall -1)",
              "screening_nach (Intervall >= 4, pf=1)",
              "kurzclip < 181 s ohne Themenklassifikation",
              "cellfill_nonwar (political_nonwar_ids)", "kriegsfenster", "cellfill_krieg / sonstige Kriegsvideos"]
    return np.select(bedingungen, labels, default="unbekannt")


# =========================================================
# BERICHT
# =========================================================

def anteil(s):
    return s.mean() if len(s) else np.nan


def abschnitt_kennzahlen(df):
    g = df.groupby("zelle")
    tab = pd.DataFrame({
        "n_videos": g.size(),
        "Anteil pf=1": g["politics_final"].apply(lambda s: (s == 1).mean()),
        "Anteil pf=0": g["politics_final"].apply(lambda s: (s == 0).mean()),
        "Anteil pf fehlt": g["politics_final"].apply(lambda s: s.isna().mean()),
        "Anteil topic_politics": g["topic_politics"].apply(lambda s: (s == True).mean()),  # noqa: E712
        "Anteil Kat. 25 (News&Politics)": g["category_id"].apply(lambda s: (s == "25").mean()),
        "Anteil kw_teiltreffer": g["kw_teiltreffer"].mean(),
        "Anteil in_screening": g["in_screening"].mean(),
        "Dauer Median (min)": g["duration_seconds"].median() / 60,
        "n_segmente Median": g["n_segmente"].median(),
        "Zeichen/Segment Median": g["zeichen_je_segment"].median(),
        "Anteil nicht kodierbar": g["anteil_nicht_kodierbar"].mean(),
        "Anteil ukraine_bezug": g["anteil_ukraine_bezug"].mean(),
        "Populismus gesamt": g["populismus_gesamt"].mean(),
        "Volkszentrismus": g["volkszentrismus"].mean(),
    }).T
    return tab


def mittel_je(df, spalte, dims=("populismus_gesamt", "volkszentrismus", "antielitismus")):
    d = df[df["ist_kriegsvideo"] == 0]
    t = d.groupby([spalte, "post"], observed=True).agg(
        n=("video_id", "size"), **{k: (k, "mean") for k in dims}).reset_index()
    t["post"] = t["post"].map({0: "vor", 1: "nach"})
    return t


def schreibe_bericht(df, raw, mehrfach):
    L = []
    L.append("# AP 1 – Diagnose der Selektions-Asymmetrie in Frage 1\n")
    L.append("*Erzeugt von `scripts/masterarbeit/ap1_selektionsdiagnose.py`.*\n")
    L.append("## Methodik-Übersicht\n")
    L.append(f"- **Grundgesamtheit:** alle Videos in `channel_video_populism.csv` von Kanälen der "
             f"279er-Whitelist (`frage1_kanal_whitelist.csv`): **{len(df):,} Videos**, "
             f"{df['channel_id'].nunique()} Kanäle. Das ist exakt der Input von `frage1_populismus_bericht.py`.")
    L.append("- **vor/nach:** `rel_monat < 0` bzw. `>= 0` (Kalendermonat relativ zum 24.02.2022). "
             f"Die Regressionen nutzen das Fenster `rel_monat` {MONAT_MIN}…{MONAT_MAX} wie der Frage-1-Bericht; "
             "die deskriptiven Tabellen nutzen alle Videos.")
    L.append("- **Kriegsvideo:** `ist_kriegsvideo` aus `channel_video_erfolg.csv` "
             "(`video_topic_relevance.is_relevant` für `russia_ukraine_war`, Keyword-basiert).")
    L.append("- **Herkunft/Auswahlweg:** Nirgends gespeichert. Hier rekonstruiert (a) über die `dataset_id` des "
             "LLM-Runs, aus dem das Video stammt, und (b) heuristisch über `screening_state.interval_index`, "
             "`politics_final`, `political_nonwar_ids.json` und das Kriegsfenster "
             f"{KRIEGSFENSTER[0]}–{KRIEGSFENSTER[1]}.")
    L.append("- **Post-Effekt in Teilmengen (Abschnitt D):** Nur Nicht-Kriegsvideos. Sie werden zu "
             "Kanal-Monat-Mitteln aggregiert; darauf läuft `y ~ C(channel_id) + post` mit SE geclustert nach "
             "Kanal (`bericht_utils.post_dummy_test`). Das entspricht Spezifikation 3 des Schnellchecks.")
    L.append("- **Prompt/Modell:** Alle Produktions-Runs für `POPULISMUS_P` verwenden Prompt-Version v4 "
             "(`prompt_sha1` 1aac52e5…), `gemini-2.5-flash`, Temperatur 0, thinking_budget 0 "
             "(`llm_runs.sqlite`, geprüft).\n")

    # --- Reproduktion Schnellcheck
    L.append("## Reproduktion des Schnellchecks\n")
    rep = df.groupby("post").agg(n=("video_id", "size"), anteil_krieg=("ist_kriegsvideo", "mean"))
    nk = df[df["ist_kriegsvideo"] == 0].groupby("post")[["volkszentrismus", "emotionale_intensitaet"]].mean()
    rep = rep.join(nk.add_suffix(" (Nichtkrieg)"))
    rep.index = rep.index.map({0: "vor", 1: "nach"})
    L.append(md_tabelle(rep) + "\n")

    # --- A Zusammensetzung
    L.append("## A. Zusammensetzung: Herkunft der Videos\n")
    L.append("### A1. Nach LLM-Datensatz (`dataset_id`)\n")
    a1 = pd.crosstab(df["dataset_id"], df["zelle"])
    L.append(md_tabelle(a1, float_fmt="{:.0f}") + "\n")
    L.append("### A2. Nach rekonstruiertem Auswahlweg\n")
    a2 = pd.crosstab(df["herkunft"], df["zelle"])
    L.append(md_tabelle(a2, float_fmt="{:.0f}") + "\n")

    # --- B Kennzahlen
    L.append("## B. Kennzahlen je Zelle (alle Videos, ohne Fensterbeschränkung)\n")
    L.append(md_tabelle(abschnitt_kennzahlen(df)) + "\n")
    L.append("### B2. Segmentierung je LLM-Datensatz\n")
    b2 = df.groupby("dataset_id").agg(n_videos=("video_id", "size"),
                                      n_segmente_median=("n_segmente", "median"),
                                      zeichen_je_segment_median=("zeichen_je_segment", "median"),
                                      zeichen_gesamt_median=("zeichen_gesamt", "median"),
                                      dauer_median_min=("duration_seconds", lambda s: s.median() / 60),
                                      anteil_krieg=("ist_kriegsvideo", "mean"),
                                      anteil_post=("post", "mean"),
                                      populismus_gesamt=("populismus_gesamt", "mean"))
    L.append(md_tabelle(b2) + "\n")

    # --- C Mittelwerte je Merkmal
    L.append("## C. Populismus der Nicht-Kriegsvideos je Merkmal, vor vs. nach\n")
    for spalte, titel in [("dataset_id", "LLM-Datensatz"), ("herkunft", "Auswahlweg"),
                          ("politics_final", "politics_final (NaN = nicht im Screening)"),
                          ("topic_politics", "topic_categories enthält Politics"),
                          ("kw_teiltreffer", "Keyword-Teiltreffer ohne is_relevant"),
                          ("dauer_band", "Längenband"), ("gruppe5", "gruppe5")]:
        d = df.copy()
        d[spalte] = d[spalte].astype("object").where(d[spalte].notna(), "fehlt")
        L.append(f"### {titel}\n")
        L.append(md_tabelle(mittel_je(d, spalte), index=False) + "\n")

    # --- (c) Mehrfach klassifizierte Videos
    L.append("## D. Hypothesenprüfung\n")
    L.append(abschnitt_hypothesen(df, mehrfach))

    PFAD_BERICHT.write_text("\n".join(L), encoding="utf-8")
    print(f"[Bericht] {PFAD_BERICHT}")


def mehrfach_klassifizierte():
    """Videos, die in mehreren Produktions-Runs klassifiziert wurden (vor der
    'neuester Run gewinnt'-Regel). Vergleicht ihre Video-Scores zwischen den Runs:
    derselbe Inhalt, zweimal gemessen -> Test auf Mess-/Segmentierungsartefakt."""
    from youtube_code.store import llm_run_store
    r = llm_run_store.get_results_for_prompt("POPULISMUS_P", source="segment_analysis_active")
    r = r[~r["dataset_id"].fillna("").str.contains("test", case=False)]
    r = _korrigiere_populismus(r)
    r["populismus_gesamt"] = r[KERN].mean(axis=1)
    v = r.groupby(["video_id", "run_id", "dataset_id"]).agg(
        n_segmente=("segment_id", "nunique"), **{k: (k, "mean") for k in KERN + ["populismus_gesamt"]}
    ).reset_index()
    mehr = v[v.duplicated("video_id", keep=False)]
    return mehr


def abschnitt_hypothesen(df, mehrfach):
    L = []
    pf1 = df["politics_final"] == 1
    tp = df["topic_politics"] == True  # noqa: E712
    teilmengen = [
        ("Alle Nicht-Kriegsvideos (= Schnellcheck Spez. 3)", None),
        ("politics_final == 1", pf1),
        ("topic_politics", tp),
        ("politics_final == 1 & topic_politics", pf1 & tp),
        ("ohne Keyword-Teiltreffer", df["kw_teiltreffer"] == 0),
        ("ohne jedes Segment mit ukraine_bezug", df["anteil_ukraine_bezug"] == 0),
        ("pf == 1 & topic_politics & ohne Teiltreffer", pf1 & tp & (df["kw_teiltreffer"] == 0)),
        ("Dauer >= 15 min", df["duration_seconds"] >= 900),
        ("n_segmente >= 3", df["n_segmente"] >= 3),
        ("nur Screening-Videos (in_screening)", df["in_screening"] == 1),
    ]
    zeilen = []
    for name, maske in teilmengen:
        for dim in ["populismus_gesamt", "volkszentrismus", "antielitismus"]:
            b, p, nv, nn, nk = post_effekt_nichtkrieg(df, dim, maske)
            zeilen.append({"Teilmenge": name, "Dimension": dim, "post": b, "p": p,
                           "n_vor": nv, "n_nach": nn, "Kanäle": nk})
    t = pd.DataFrame(zeilen)
    L.append("### D1. Post-Effekt der Nicht-Kriegsvideos in Teilmengen (Kanal-Monat, Kanal-FE)\n")
    L.append(md_tabelle(t, index=False) + "\n")

    # alternative Aggregation
    zeilen = []
    for suffix, name in [("", "Mittelwert über Segmente (Standard)"),
                         ("_erstes_seg", "nur erstes Segment"), ("_max", "Maximum über Segmente")]:
        d = df.copy()
        for k in KERN + ["populismus_gesamt"]:
            d[k] = d[k + suffix] if suffix else d[k]
        for dim in ["populismus_gesamt", "volkszentrismus"]:
            b, p, nv, nn, nk = post_effekt_nichtkrieg(d, dim)
            zeilen.append({"Aggregation Segment→Video": name, "Dimension": dim, "post": b, "p": p})
    L.append("### D2. Alternative Aggregation Segment → Video (Hypothese d)\n")
    L.append(md_tabelle(pd.DataFrame(zeilen), index=False) + "\n")

    # Mehrfachmessungen
    L.append("### D3. Videos, die in mehreren Runs klassifiziert wurden (Hypothese c)\n")
    if mehrfach.empty:
        L.append("Keine Videos in mehreren Produktions-Runs.\n")
    else:
        paare = mehrfach.sort_values("run_id").groupby("video_id")
        erste = paare.first()
        letzte = paare.last()
        vergleich = pd.DataFrame({
            "n_videos": [len(erste)],
            "Run-Paare": [", ".join(sorted((erste["dataset_id"] + " → " + letzte["dataset_id"]).unique())[:6])],
            "n_seg früh (Median)": [erste["n_segmente"].median()],
            "n_seg spät (Median)": [letzte["n_segmente"].median()],
            "Populismus früh": [erste["populismus_gesamt"].mean()],
            "Populismus spät": [letzte["populismus_gesamt"].mean()],
            "Korrelation": [erste["populismus_gesamt"].corr(letzte["populismus_gesamt"])],
        })
        L.append(md_tabelle(vergleich, index=False) + "\n")

    L.append("### D4. Urteile zu den Hypothesen\n")
    L.append("*Die Urteile sind von Hand formuliert (Stand 2026-09-28). Die ausführliche Fassung steht in "
             "`outputs/segment_analysis/frage1_methodik_und_stichprobe.md`, Abschnitt 4a.*\n")
    L.append("- **(a) Anderer Auswahlweg bzw. abweichende Kriegsvideo-Definition: TRIFFT ZU (Hauptursache).** "
             "10.784 der 11.125 Nachher-Nichtkriegsvideos haben keine Zeile in `video_topic_relevance`. "
             "Sie sind zu 97 % kürzer als 181 s, und die Themenklassifikation (`get_videos_with_text()`) "
             "lässt sie deshalb aus. Sie gelten per Default als Nicht-Kriegsvideo. Zu 96 % stammen sie aus "
             "der alten Liste `archive/sample_feasibility/war_vids.csv` (Batches "
             "`videos_to_classify_populism1-4`); dort sind 79 % Kern-Kriegsvideos.")
    L.append("- **(b) Wenig politisch: TEILWEISE.** Nur 3 % haben `politics_final == 1`, weil sie gar nicht "
             "im Screening sind. `topic_politics` trifft auf 91 % zu. Das Problem ist also nicht fehlende "
             "Politik, sondern Kürze und falsche Themenzuordnung. Mit `politics_final == 1` verschwindet "
             "der Effekt (+0,02 n. s.).")
    L.append("- **(c) Prompt oder Segmentierung: TRIFFT NICHT ZU.** Alle Runs nutzen dieselbe Prompt-Version "
             "v4, dasselbe Modell und dieselbe Temperatur. Mehrfach klassifizierte Videos korrelieren über "
             "die Runs mit r = 0,98. Die kleinen Segmentzahlen der Batches 1–3 folgen aus der Videolänge.")
    L.append("- **(d) Aggregation Segment → Video: TRIFFT NICHT ZU.** Der Effekt bleibt bei jeder "
             "Aggregationsregel bestehen (D2), verschwindet aber bei Dauer ≥ 15 min oder "
             "≥ 3 Segmenten (D1).")
    L.append("- **(e) Realer Rückgang: NICHT GESTÜTZT.** In allen Teilmengen mit vergleichbarem "
             "Auswahlweg ist der Post-Effekt der Nicht-Kriegsvideos nahe null und nicht signifikant. "
             "Einzige Ausnahme: Volkszentrismus in der strengen Teilmenge, −0,12, p = 0,04. Allerdings "
             "hat dieser Vergleich wenig Power: 341 Nachher-Videos, 197 Kanäle.\n")
    return "\n".join(L)


def main():
    AUSGABE_REG.mkdir(parents=True, exist_ok=True)
    df, raw = baue_datensatz()
    mehrfach = mehrfach_klassifizierte()
    mehrfach = mehrfach[mehrfach["video_id"].isin(df["video_id"])]
    df.to_csv(PFAD_VIDEOS, index=False)
    print(f"[Videos] {PFAD_VIDEOS} ({len(df)} Zeilen)")
    schreibe_bericht(df, raw, mehrfach)


if __name__ == "__main__":
    main()

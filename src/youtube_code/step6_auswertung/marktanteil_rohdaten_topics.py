# -*- coding: utf-8 -*-
"""
marktanteil_rohdaten_topics.py

Marktanteile nach Themen der Transkript-Segmente, Spiegel von
marktanteil_rohdaten_plots.py (8i). Kanaele (KANALLISTE, KANAELE_AUSSCHLIESSEN,
MANUELL_ALT_RECHTS), Klassifikationen, Schalter (POPULISMUS_MEDIAN usw.) und
Kanal-Samples kommen direkt aus diesem Skript und werden DORT eingestellt, damit
beide Skripte dieselben Gruppen zeigen. Population: format == "long" mit Views aus
videos_roh.dta im Zeitraum der Ziehung.

Themen: videos_klassifiziert.csv aus step3_topic_relevance/classify_segment_topics.py
(wortgewichteter Textanteil je Thema und Video, Klassifikatoren "dict"/"lr"). Die
Klassifikation steht nicht in videos_roh.dta; dieses Skript liest sie deshalb direkt.
Ein Video zaehlt bei THEMA_ZUORDNUNG = "schwelle" zu einem Thema, wenn der Textanteil
>= THEMA_SCHWELLE ist (Mehrfachzuordnung moeglich); bei "anteilig" geht es mit dem
Textanteil anteilig ein (Mehrthemen-Nachrichtensendungen fallen dann nicht heraus).

Normierung
----------
Je Kanal-Einheit (Kanal x Woche/Monat, NORMIERUNG_EINHEIT) ist nur ein Teil der Videos
klassifiziert: Die Ziehung kappt bei 14 Videos je Kanal-Woche, und nicht fuer alle
gezogenen Videos gibt es ein Transkript. Jedes klassifizierte Video bekommt deshalb

    faktor(Kanal, Einheit) = n_videos_gesamt(Kanal, Einheit) / n_klassifiziert(Kanal, Einheit)

n_videos_gesamt = alle long-Videos in videos_roh. Videozahlen und Views werden mit dem
Faktor multipliziert. Damit zaehlt ein Kanal nach seinem tatsaechlichen Upload-Volumen.

Marktanteil je Zelle (Gruppe x Periode x Thema):

    gewicht     = faktor * thema_gewicht (0/1 bzw. Textanteil)
    views_summe = sum(views * gewicht), n_videos = sum(gewicht)
    anteil      = views_summe / sum(views_summe | alle Gruppen) * 100
    angebot_anteil = n_videos / sum(n_videos | alle Gruppen) * 100

Perioden unter MIN_KLASSIFIZIERT (echte klassifizierte Videos ueber alle Gruppen) fallen
weg. n_klassifiziert, anteil_ungewichtet und top_video_anteil (Anteil des groessten
gewichteten Videos an den Views der Zelle) stehen in der CSV, um Rauschen zu erkennen.

Grenze der Normierung: Sie korrigiert Luecken NUR innerhalb einer Kanal-Einheit und
setzt dort zufaelliges Fehlen voraus. Kanal-Einheiten ganz ohne klassifiziertes Video
fallen heraus; das laesst sich nicht hochrechnen.

Abdeckungspruefung (laeuft immer, Grundlage: videos_roh, ID_DATEI, transcript_store)
-----------------------------------------------------------------------------------
Trichter je Zeiteinheit, Gruppe und Kanal: gesamt -> gezogen -> Scrape-Versuch ->
Transkript -> klassifiziert. Transkripte zaehlen nur laut transcript_store.
- quote_klassifiziert = klassifiziert / gezogen (sind alle gezogenen Videos da?)
- views_abgedeckt = Anteil der Views in Kanal-Einheiten mit mindestens einem
  klassifizierten Video (nur dieser Teil wird hochgerechnet)
- Selektionstest: Anteil Titel-Kriegsvideos (rel_russia_ukraine_war_cw) und Median-Views
  unter gezogenen vs. klassifizierten Videos
- status "kritisch": quote_klassifiziert < MIN_QUOTE_KLASSIFIZIERT,
  views_abgedeckt < MIN_VIEWS_ABGEDECKT oder selektion_krieg_pp (Krieg-Titel-Anteil
  klassifiziert minus gezogen) betragsmaessig > MAX_SELEKTION_KRIEG_PP; kritische
  Perioden sind grau hinterlegt. Bei Selektion ist die Annahme der Normierung verletzt:
  Der Faktor rechnet dann die selektierten Videos hoch, statt die Luecke zu schliessen.
Validierung: Der "wahre" Marktanteil aller Videos ist aus videos_roh bekannt. Er wird mit
dem normierten und dem ungewichteten Wert aus den klassifizierten Videos verglichen
(gleiche Grundmenge). Grosse Abweichungen hier treffen auch die Themenwerte.

Ausgabe nach OUTPUTS / "segment_analysis" / "plots_marktanteil_topics" (<zusatz> wie 8i:
_manuell, _oerrdoku, _ohne_...):
- marktanteil_topics_<klassifikation>_<klassifikator>_<zeiteinheit><zusatz>.png: Spalten
  Alle Videos + THEMEN, oben Views-Anteil, unten Upload-Anteil; durchgezogen Sample
  "alle", gestrichelt "vorkrieg" (nach KOMBI_VERSION aus 8i). Bei ABSOLUT_VERSION
  zusaetzlich ..._absolut.png mit normierten Views (Mio.) und Uploads
- marktanteil_topics_<zeiteinheit><zusatz>.csv: alle Werte im Long-Format
- abdeckung_<zeiteinheit><zusatz>.csv / .png: Trichter je Klassifikation, Gruppe, Periode
- abdeckung_kanal_<zeiteinheit><zusatz>.csv, abdeckung_kanaele_<zeiteinheit><zusatz>.png:
  dasselbe je Kanal, Heatmap klassifiziert / gezogen
- validierung_<zeiteinheit><zusatz>.csv: wahrer vs. normierter vs. ungewichteter Anteil
- marktanteil_topics_methodik<zusatz>.md: Methodik, Abdeckung, Validierung, Phasenwerte

Einschraenkung: Die Klassifikatoren sind nur fuer Jan-Apr 2022 validiert, 2.210 Videos
daraus sind Trainingsdaten (TRAININGSVIDEOS_AUSSCHLIESSEN). Nur grosse Verschiebungen
(>= 5 Prozentpunkte) bei haeufigen Themen als Hinweis werten, nicht als Befund.

Ausfuehren aus dem Repo-Root:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.marktanteil_rohdaten_topics
"""

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from youtube_code.config import ADHOC_OUTPUT, KEYWORD_KLASSIFIZIERUNG, OUTPUTS
from youtube_code.step6_auswertung import marktanteil_rohdaten_plots as ma
from youtube_code.step6_auswertung.prepare_channel_scores import KRIEGSBEGINN, relativ_periode
from youtube_code.store.transcript_store import attempted_video_ids, has_transcript


# =========================================================
# CONFIG
# =========================================================

PFAD_PLOTS = OUTPUTS / "segment_analysis" / "plots_marktanteil_topics"
ID_DATEI = ADHOC_OUTPUT / "video_ids_angebot_2022-06-02_2022-11-02.csv"   # Ziehung (Spalten video_id, datum)
VIDEO_DATEI = KEYWORD_KLASSIFIZIERUNG / "videos_klassifiziert.csv"        # Themenanteile je Video
STATUS_DATEI = KEYWORD_KLASSIFIZIERUNG / "video_status.csv"               # segmentiert / zu_kurz

# Teilmenge von ["dict", "lr"], nicht leer; je Klassifikator ein Satz Grafiken.
KLASSIFIKATOREN = ["dict", "lr"]
# Themen als Spalten (ausser "Alle Videos"): krieg_ukraine, corona, migration, wirtschaft,
# energie, klima, gender, nahost, iran, eu, usa, bildung, innenpolitik_sonstige,
# sonstiges_politisch, unpolitisch. Default = die Themen mit brauchbarer Trendtreue.
THEMEN = ["energie"] #, "krieg_ukraine", "corona", "migration", "wirtschaft"
# "schwelle" = Video zaehlt ganz, wenn Textanteil >= THEMA_SCHWELLE (auf Video-Ebene
# validiert); "anteilig" = Video zaehlt mit seinem Textanteil.
THEMA_ZUORDNUNG = "schwelle"
THEMA_SCHWELLE = 0.5   # 0 < x <= 1, nur bei "schwelle"
# True = Trainingsvideos (Jan-Apr 2022, in-sample) gelten als nicht klassifiziert,
# der Faktor gleicht sie aus. True/False.
TRAININGSVIDEOS_AUSSCHLIESSEN = False

# Teilmenge von ["monat", "woche", "quartal"], nicht leer. Monat 0 = [24.02.2022, 24.03.2022),
# Woche 0 = [24.02.2022, 03.03.2022), Do-Mi, Quartal 0 = [24.02.2022, 24.05.2022).
ZEITEINHEITEN = ["monat", "woche"]
# Einheit der Normierung: "zeiteinheit" = Kanal x jeweilige Zeiteinheit der Auswertung;
# "woche" = immer Kanal x Woche (Schicht der Ziehung), Kanal-Wochen ohne klassifiziertes
# Video gehen dann aber auch in der Monatsauswertung verloren.
NORMIERUNG_EINHEIT = "zeiteinheit"
# True = nur Perioden, die vollstaendig im Ziehungszeitraum liegen (ohne Monat -2 und 10).
# False = Teilperioden bleiben drin (Anteile vergleichbar, absolute Werte nicht); sonst
# bliebe vor Kriegsbeginn nur ein Monatswert. True/False.
NUR_VOLLE_PERIODEN = False

MIN_KLASSIFIZIERT = 20          # Mindestzahl klassifizierter Videos je Periode und Thema (alle Gruppen), >= 1
MIN_QUOTE_KLASSIFIZIERT = 0.4   # darunter "kritisch": klassifiziert / gezogen, 0..1
MIN_VIEWS_ABGEDECKT = 0.8       # darunter "kritisch": Views-Anteil abgedeckter Kanal-Einheiten, 0..1
MAX_SELEKTION_KRIEG_PP = 4      # darueber "kritisch": |Krieg-Titel-Anteil klassifiziert - gezogen| in pp, >= 0

ABSOLUT_VERSION = True         # zusaetzlich ..._absolut.png (normierte Views/Uploads). True/False
LOWESS_WOCHE = 0.25             # Glaettung der Wochenwerte, 0 <= x <= 1; 0 = nur Rohwerte

# Senkrechte Linien neben dem Kriegsbeginn: {Beschriftung: "JJJJ-MM-TT"}; leer = keine.
EREIGNISSE = {}

# Phasen der Vorher-Nachher-Tabelle in der Methodik-Datei: {Name: (von, bis)}, inklusive;
# gepoolte normierte Werte je Phase.
PHASEN = {
    "Vorkrieg": ("2022-01-06", "2022-02-23"),
    "Kriegsbeginn": ("2022-02-24", "2022-05-23"),
    "Sommer/Herbst": ("2022-05-24", "2022-10-05"),
    "Ende 2022 (selektiert)": ("2022-10-06", "2023-01-04"),   # Stand 05.11.2026: fast nur Kriegsvideos abgedeckt
}

# =========================================================
# CONFIG ENDE
# =========================================================

ZEIT = {
    "monat": dict(wort="Monat", monate=1, xlabel="Monat relativ zum Kriegsbeginn (Monat 0 = 24.02.–23.03.2022)"),
    "quartal": dict(wort="Quartal", monate=3, xlabel="Quartal relativ zum Kriegsbeginn (Quartal 0 = 24.02.–23.05.2022)"),
    "woche": dict(wort="Woche", monate=None, xlabel="Woche relativ zum Kriegsbeginn (Woche 0 = 24.02.–02.03.2022, Do–Mi)"),
}
THEMA_TITEL = {"krieg_ukraine": "Ukraine-Krieg", "corona": "Corona", "energie": "Energie", "wirtschaft": "Wirtschaft",
               "migration": "Migration", "klima": "Klima", "gender": "Gender", "nahost": "Nahost", "iran": "Iran",
               "eu": "EU", "usa": "USA", "bildung": "Bildung", "innenpolitik_sonstige": "Innenpolitik (sonstige)",
               "sonstiges_politisch": "Sonstiges Politisches", "unpolitisch": "Unpolitisch"}
ALLE = "alle"   # Schluessel der Spalte "Alle Videos"
GESAMT = "Gesamt"
KB = pd.Timestamp(KRIEGSBEGINN)


# =========================================================
# SCHRITT 1: Kanaele und Videos
# =========================================================

def lade_kanaele():
    """Gruppen und Kanaele genau wie main() in marktanteil_rohdaten_plots.py."""
    ma.setze_oerr_doku_gruppe()
    kanaele, _ = ma.bilde_gruppen(ma.lade_kanaele())
    ausschluss = ma.loese_ausschluss_auf(kanaele) if ma.KANAELE_AUSSCHLIESSEN else None
    if ma.KANALLISTE:
        kanaele = kanaele[kanaele["channel_id"].isin(ma.KANALLISTE)]
    kanaele, _ = ma.manuell_alt_rechts(kanaele)
    kanaele, _ = ma.bilde_tertil_gruppen(kanaele)
    kanaele, _ = ma.bilde_median_gruppen(kanaele)
    if ausschluss is not None:
        ausschluss = ausschluss[ausschluss["channel_id"].isin(kanaele["channel_id"])].reset_index(drop=True)
        kanaele = kanaele[~kanaele["channel_id"].isin(ausschluss["channel_id"])]
        ma._AUSSCHLUSS_ZUSATZ = ma.ausschluss_zusatz(ausschluss)
    print(f"[Kanaele] {len(kanaele)} Kanaele wie in marktanteil_rohdaten_plots.py")
    return kanaele


def lade_videos(kanaele, aktive):
    """Alle long-Videos der Kanaele im Ziehungszeitraum mit den Trichter-Flags und den
    Themenanteilen. Gibt (Videos, Trichter-Kennzahlen der Ziehung, Start, Ende) zurueck."""
    ids = pd.read_csv(ID_DATEI, encoding="utf-8-sig", usecols=["video_id", "datum"])
    start, ende = pd.Timestamp(ids["datum"].min()), pd.Timestamp(ids["datum"].max())
    v = pd.read_stata(ma.ROHDATEN_PFAD / "videos_roh.dta",
                      columns=["video_id", "channel_id", "upload_ts", "views", "format", "rel_russia_ukraine_war_cw"])
    v = v[(v["format"].astype(str) == "long") & v["views"].notna() & v["channel_id"].isin(kanaele["channel_id"])
          & (v["upload_ts"] >= start) & (v["upload_ts"] < ende + pd.Timedelta(days=1))]
    v = v.drop(columns="format").rename(columns={"rel_russia_ukraine_war_cw": "krieg_titel"})
    v["krieg_titel"] = v["krieg_titel"].astype(str) == "ja"
    v["views"] = v["views"].astype(float)
    v["rel_woche"] = ((v["upload_ts"] - KB).dt.days // 7).astype(int)

    v["gezogen"] = v["video_id"].isin(ids["video_id"])
    gezogen_ids = v.loc[v["gezogen"], "video_id"].tolist()
    v["versucht"] = v["gezogen"] & v["video_id"].isin(attempted_video_ids())
    v["transkript"] = v["gezogen"] & v["video_id"].isin(has_transcript(gezogen_ids))

    spalten = [f"{k}_{t}" for k in KLASSIFIKATOREN for t in THEMEN]
    klass = pd.read_csv(VIDEO_DATEI, usecols=["video_id", "im_training", *spalten])
    v = v.merge(klass, on="video_id", how="left")
    v["klassifiziert"] = v["im_training"].notna()
    v["im_training"] = v["im_training"].fillna(0).astype(int)
    if TRAININGSVIDEOS_AUSSCHLIESSEN:
        v["klassifiziert"] &= v["im_training"] == 0

    status = pd.read_csv(STATUS_DATEI)
    info = {"n_ids": len(ids), "n_ids_im_rahmen": int(v["gezogen"].sum()),
            "n_klass_datei": len(klass), "n_klass_im_rahmen": int(v["klassifiziert"].sum()),
            "n_zu_kurz": int((status["aufbereitung"] == "zu_kurz").sum())}
    print(f"[Videos] {len(v):,} long-Videos {start:%d.%m.%Y}-{ende:%d.%m.%Y}; {info['n_ids_im_rahmen']:,} gezogen "
          f"(von {info['n_ids']:,} IDs, Rest: Kanaele ausserhalb der KANALLISTE), "
          f"{int(v['transkript'].sum()):,} mit Transkript, {info['n_klass_im_rahmen']:,} klassifiziert")
    return v.merge(kanaele[["channel_id", "sample_vorkrieg", "kanal_name", *aktive]], on="channel_id"), info, start, ende


def setze_periode(v, zeiteinheit, start, ende):
    """rel_periode und Normierungsfaktor fuer eine Zeiteinheit. Gibt (Videos, Periodentabelle) zurueck."""
    v = v.copy()
    monate = ZEIT[zeiteinheit]["monate"]
    v["rel_periode"] = v["rel_woche"] if monate is None else relativ_periode(v["upload_ts"], KB, monate)
    perioden = pd.DataFrame({"rel_periode": sorted(v["rel_periode"].unique())})
    if monate is None:
        beginn = KB + pd.to_timedelta(perioden["rel_periode"] * 7, unit="D")
        naechste = beginn + pd.Timedelta(days=7)
    else:
        beginn = perioden["rel_periode"].map(lambda p: KB + pd.DateOffset(months=int(p) * monate))
        naechste = perioden["rel_periode"].map(lambda p: KB + pd.DateOffset(months=(int(p) + 1) * monate))
    perioden["periode_start"] = beginn.dt.date
    perioden["periode_ende"] = (naechste - pd.Timedelta(days=1)).dt.date
    perioden["periode_voll"] = (beginn >= start) & (naechste <= ende + pd.Timedelta(days=1))
    if NUR_VOLLE_PERIODEN:
        perioden = perioden[perioden["periode_voll"]]
        v = v[v["rel_periode"].isin(perioden["rel_periode"])].copy()

    einheit = "rel_periode" if NORMIERUNG_EINHEIT == "zeiteinheit" else "rel_woche"
    g = v.groupby(["channel_id", einheit])
    v["n_gesamt_einheit"] = g["video_id"].transform("size")
    v["n_klass_einheit"] = g["klassifiziert"].transform("sum")
    v["abgedeckt"] = v["n_klass_einheit"] > 0
    v["faktor"] = np.where(v["klassifiziert"], v["n_gesamt_einheit"] / v["n_klass_einheit"].replace(0, np.nan), 0.0)
    return v, perioden


# =========================================================
# SCHRITT 2: Abdeckung und Validierung
# =========================================================

def kennzahlen(d):
    """Trichter und Selektionstest fuer eine Menge von Videos."""
    n_gez, n_kl = int(d["gezogen"].sum()), int(d["klassifiziert"].sum())
    gez, kl = d[d["gezogen"]], d[d["klassifiziert"]]
    aktiv = d["channel_id"].nunique()
    return {
        "n_gesamt": len(d), "n_gezogen": n_gez, "n_versucht": int(d["versucht"].sum()),
        "n_transkript": int(d["transkript"].sum()), "n_klassifiziert": n_kl,
        "n_fehlend": n_gez - n_kl, "n_im_training": int(d["im_training"].sum()),
        "quote_gezogen": n_gez / len(d),
        "quote_klassifiziert": n_kl / n_gez if n_gez else np.nan,
        "kanaele_aktiv": aktiv, "kanaele_abgedeckt": kl["channel_id"].nunique(),
        "views_abgedeckt": d.loc[d["abgedeckt"], "views"].sum() / d["views"].sum() if d["views"].sum() else np.nan,
        "krieg_titel_gezogen": gez["krieg_titel"].mean() if n_gez else np.nan,
        "krieg_titel_klassifiziert": kl["krieg_titel"].mean() if n_kl else np.nan,
        "selektion_krieg_pp": (kl["krieg_titel"].mean() - gez["krieg_titel"].mean()) * 100 if n_kl else np.nan,
        "views_median_gezogen": gez["views"].median() if n_gez else np.nan,
        "views_median_klassifiziert": kl["views"].median() if n_kl else np.nan,
    }


def status_aus(tab):
    kritisch = ((tab["quote_klassifiziert"].fillna(0) < MIN_QUOTE_KLASSIFIZIERT)
                | (tab["views_abgedeckt"].fillna(0) < MIN_VIEWS_ABGEDECKT)
                | (tab["selektion_krieg_pp"].abs() > MAX_SELEKTION_KRIEG_PP))
    return np.where(kritisch, "kritisch", "ok")


def abdeckung_gruppen(v, aktive, perioden):
    """Trichter je Klassifikation, Gruppe (inkl. GESAMT) und Periode."""
    zeilen = []
    for k_key in aktive:
        d = v[v[k_key].notna()]
        for p, dp in d.groupby("rel_periode"):
            zeilen.append({"klassifikation": k_key, "rel_periode": p, "gruppe": GESAMT, **kennzahlen(dp)})
            for g, dg in dp.groupby(k_key):
                zeilen.append({"klassifikation": k_key, "rel_periode": p, "gruppe": g, **kennzahlen(dg)})
    tab = pd.DataFrame(zeilen).merge(perioden, on="rel_periode")
    tab["status"] = status_aus(tab)
    return tab


def abdeckung_kanaele(v, perioden):
    """Trichter je Kanal und Periode."""
    zeilen = [{"channel_id": c, "kanal_name": n, "rel_periode": p, **kennzahlen(d)}
              for (c, n, p), d in v.groupby(["channel_id", "kanal_name", "rel_periode"])]
    tab = pd.DataFrame(zeilen).merge(perioden, on="rel_periode")
    tab["status"] = status_aus(tab)
    return tab


def validierung(v, aktive):
    """Wahrer Marktanteil aller Videos (videos_roh) vs. normierter und ungewichteter
    Wert aus den klassifizierten Videos; Sample "alle"."""
    teile = []
    for k_key in aktive:
        d = v[v[k_key].notna()]
        kl = d[d["klassifiziert"]]
        schluessel = ["rel_periode", k_key]
        t = pd.concat({
            "views_wahr": d.groupby(schluessel)["views"].sum(),
            "n_wahr": d.groupby(schluessel).size(),
            "views_norm": kl.assign(x=kl["views"] * kl["faktor"]).groupby(schluessel)["x"].sum(),
            "n_norm": kl.groupby(schluessel)["faktor"].sum(),
            "views_roh": kl.groupby(schluessel)["views"].sum(),
            "n_roh": kl.groupby(schluessel).size(),
        }, axis=1).fillna(0).reset_index().rename(columns={k_key: "gruppe"})
        t.insert(0, "klassifikation", k_key)
        for s, name in [("views_wahr", "anteil_wahr"), ("views_norm", "anteil_normiert"),
                        ("views_roh", "anteil_ungewichtet"), ("n_wahr", "angebot_wahr"),
                        ("n_norm", "angebot_normiert"), ("n_roh", "angebot_ungewichtet")]:
            t[name] = t[s] / t.groupby("rel_periode")[s].transform("sum") * 100
        teile.append(t)
    tab = pd.concat(teile, ignore_index=True)
    tab["abw_anteil_normiert"] = tab["anteil_normiert"] - tab["anteil_wahr"]
    tab["abw_anteil_ungewichtet"] = tab["anteil_ungewichtet"] - tab["anteil_wahr"]
    tab["abw_angebot_normiert"] = tab["angebot_normiert"] - tab["angebot_wahr"]
    tab["abw_angebot_ungewichtet"] = tab["angebot_ungewichtet"] - tab["angebot_wahr"]
    return tab


# =========================================================
# SCHRITT 3: Marktanteile
# =========================================================

def thema_gewicht(d, klassifikator, thema):
    if thema == ALLE:
        return pd.Series(1.0, index=d.index)
    anteil = d[f"{klassifikator}_{thema}"].fillna(0)
    return anteil if THEMA_ZUORDNUNG == "anteilig" else (anteil >= THEMA_SCHWELLE).astype(float)


def berechne_marktanteile(v, gruppen_spalte, klassifikator, thema):
    """Normierte Anteile je Gruppe und Periode (Formeln im Moduldocstring)."""
    d = v[v["klassifiziert"] & v[gruppen_spalte].notna()].copy()
    gew = thema_gewicht(d, klassifikator, thema)
    d = d[gew > 0].assign(n_gewichtet=(d["faktor"] * gew)[gew > 0], roh=gew[gew > 0])
    d["views_gewichtet"] = d["views"] * d["n_gewichtet"]
    d["views_roh"] = d["views"] * d["roh"]
    if d.empty:
        return pd.DataFrame()
    z = d.groupby(["rel_periode", gruppen_spalte], as_index=False).agg(
        views_summe=("views_gewichtet", "sum"), n_videos=("n_gewichtet", "sum"),
        views_roh=("views_roh", "sum"), n_roh=("roh", "sum"), n_klassifiziert=("roh", "size"),
        top_view=("views_gewichtet", "max"))
    p = z.groupby("rel_periode", as_index=False).agg(
        views_gesamt=("views_summe", "sum"), n_gesamt=("n_videos", "sum"),
        views_roh_gesamt=("views_roh", "sum"), n_roh_gesamt=("n_roh", "sum"),
        n_klassifiziert_gesamt=("n_klassifiziert", "sum"))
    z = z.merge(p[p["n_klassifiziert_gesamt"] >= MIN_KLASSIFIZIERT], on="rel_periode")
    z["anteil"] = z["views_summe"] / z["views_gesamt"] * 100
    z["angebot_anteil"] = z["n_videos"] / z["n_gesamt"] * 100
    z["anteil_ungewichtet"] = z["views_roh"] / z["views_roh_gesamt"] * 100
    z["angebot_anteil_ungewichtet"] = z["n_roh"] / z["n_roh_gesamt"] * 100
    z["top_video_anteil"] = z["top_view"] / z["views_summe"] * 100
    for spalte in ["anteil", "angebot_anteil"]:
        abw = (z.groupby("rel_periode")[spalte].sum() - 100).abs().max() if len(z) else 0
        if abw > 0.01:
            raise ValueError(f"{spalte} summiert sich nicht zu 100 % (max. Abweichung {abw:.4f} pp)")
    return z.rename(columns={gruppen_spalte: "gruppe"}).drop(
        columns=["top_view", "views_roh", "n_roh", "views_roh_gesamt", "n_roh_gesamt"])


def phasenwerte(v, gruppen_spalte, klassifikator, thema):
    """Gepoolter normierter Views- und Upload-Anteil je Gruppe und Phase."""
    d = v[v["klassifiziert"] & v[gruppen_spalte].notna()]
    gew = d["faktor"] * thema_gewicht(d, klassifikator, thema)
    views, angebot, fall = {}, {}, {}
    for name, (von, bis) in PHASEN.items():
        m = (d["upload_ts"] >= pd.Timestamp(von)) & (d["upload_ts"] < pd.Timestamp(bis) + pd.Timedelta(days=1))
        vs = (d["views"] * gew)[m].groupby(d[gruppen_spalte][m]).sum()
        ns = gew[m].groupby(d[gruppen_spalte][m]).sum()
        views[name], angebot[name] = vs / vs.sum() * 100, ns / ns.sum() * 100
        fall[name] = int((gew[m] > 0).sum())
    return pd.DataFrame(views), pd.DataFrame(angebot), fall


# =========================================================
# SCHRITT 4: Grafiken
# =========================================================

def kritische_perioden(abdeckung, k_key):
    t = abdeckung[(abdeckung["klassifikation"] == k_key) & (abdeckung["gruppe"] == GESAMT)]
    return t.loc[t["status"] == "kritisch", "rel_periode"].to_list()


def achse_einrichten(ax, zeiteinheit, kritisch, x_von, x_bis):
    """Kriegsbeginn, EREIGNISSE, kritische Perioden; Punkt k markiert den Periodenbeginn."""
    for p in kritisch:
        ax.axvspan(p, p + 1, color="#e5e4e0", alpha=0.7, linewidth=0, zorder=0)
    ax.axvline(0, color="#52514e", linestyle="--", linewidth=1)
    for datum in EREIGNISSE.values():
        monate = ZEIT[zeiteinheit]["monate"]
        xe = (pd.Timestamp(datum) - KB).days / 7 if monate is None else ma.ereignis_position(datum, monate)
        if x_von <= xe <= x_bis:
            ax.axvline(xe, color="#8a8883", linestyle=":", linewidth=1.2, zorder=1)
    ax.grid(axis="y", color="#e5e4e0", linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)


def plotte_marktanteile(je_sample, k_key, klassifikator, zeiteinheit, kritisch, dateiname, absolut=False):
    """Oben Views, unten Uploads; je Thema eine Spalte. je_sample = {Sample: {Thema: Anteile}}."""
    cfg = ma.KLASSIFIKATIONEN[k_key]
    themen = [ALLE, *THEMEN]
    z = ZEIT[zeiteinheit]
    reihen = ([("views_summe", f"Normierte Views je {z['wort']} (Mio.)"), ("n_videos", f"Normierte Uploads je {z['wort']}")]
              if absolut else [("anteil", "Anteil an allen Views (%)"), ("angebot_anteil", "Anteil an allen Uploads (%)")])
    fig, achsen = plt.subplots(2, len(themen), figsize=(max(4.2 * len(themen), ma.GRAFIK_MINDESTBREITE), 8.2),
                               sharex=True, sharey=False if absolut else "row", squeeze=False)
    alle_p = pd.concat([a["rel_periode"] for s in je_sample.values() for a in s.values() if len(a)])
    x_von, x_bis = alle_p.min(), alle_p.max() + 1
    haupt = "alle" if "alle" in je_sample else next(iter(je_sample))
    for zeile, (spalte, ylabel) in enumerate(reihen):
        faktor = 1e6 if spalte == "views_summe" else 1
        for nr, thema in enumerate(themen):
            ax = achsen[zeile, nr]
            achse_einrichten(ax, zeiteinheit, kritisch, x_von, x_bis)
            for gruppe, farbe in zip(cfg["gruppen"], cfg["farben"]):
                a = je_sample[haupt][thema]
                r = a[a["gruppe"] == gruppe].sort_values("rel_periode") if len(a) else a
                if len(r):
                    x, y = r["rel_periode"].to_numpy(float), r[spalte].to_numpy(float) / faktor
                    if zeiteinheit == "woche" and LOWESS_WOCHE:
                        ax.plot(x, y, color=farbe, linewidth=0.7, alpha=0.35, zorder=2)
                        ax.plot(x, ma.glaette(x, y, LOWESS_WOCHE), color=farbe, linewidth=2, zorder=3)
                    else:
                        ax.plot(x, y, color=farbe, linewidth=2, marker="o", markersize=4.5,
                                markeredgecolor="white", markeredgewidth=0.5, zorder=3)
                for s_key, anteile in je_sample.items():
                    if s_key == haupt or not len(anteile[thema]):
                        continue
                    rv = anteile[thema]
                    rv = rv[rv["gruppe"] == gruppe].sort_values("rel_periode")
                    if len(rv):
                        xv, yv = rv["rel_periode"].to_numpy(float), rv[spalte].to_numpy(float) / faktor
                        if zeiteinheit == "woche" and LOWESS_WOCHE:
                            yv = ma.glaette(xv, yv, LOWESS_WOCHE)
                        ax.plot(xv, yv, color=farbe, linewidth=1.3, linestyle="--", zorder=3)
            if zeile == 0:
                ax.set_title("Alle Videos" if thema == ALLE else THEMA_TITEL.get(thema, thema), fontsize=11)
            else:
                ax.set_xlabel(f"{z['wort']} relativ zum Kriegsbeginn", fontsize=9)
        achsen[zeile, 0].set_ylabel(ylabel)
    # erst nach allen Linien, sonst friert die Grenze die gemeinsame y-Achse ein
    for ax in achsen.flat:
        ax.set_ylim(bottom=0)
    belegt = set(pd.concat([a["gruppe"] for s in je_sample.values() for a in s.values() if len(a)]))
    griffe, namen = [], []
    for gruppe, farbe in zip(cfg["gruppen"], cfg["farben"]):
        if gruppe in belegt:
            griffe.append(Line2D([], [], color=farbe, linewidth=2))
            namen.append(gruppe)
    if len(je_sample) > 1:
        griffe += [Line2D([], [], color="#52514e", linewidth=2), Line2D([], [], color="#52514e", linewidth=1.3, linestyle="--")]
        namen += [ma.SAMPLES["alle"][0], ma.SAMPLES["vorkrieg"][0]]
    if kritisch:
        griffe.append(Patch(color="#e5e4e0"))
        namen.append("kritische Abdeckung")
    fig.legend(griffe, namen, loc="lower center", frameon=False, fontsize=9, ncol=min(len(namen), 6))
    art = "Normierte absolute Zahlen" if absolut else "Normierter Marktanteil"
    regel = f"Textanteil ≥ {THEMA_SCHWELLE:.0%}" if THEMA_ZUORDNUNG == "schwelle" else "anteilig nach Textanteil"
    fig.suptitle(f"{art} nach Thema und {cfg['titel']} – Klassifikator {klassifikator}, {regel}", fontsize=12)
    fig.tight_layout(rect=(0, 0.06, 1, 0.97))
    fig.savefig(PFAD_PLOTS / dateiname, dpi=150)
    plt.close(fig)
    print(f"[Plot] {PFAD_PLOTS / dateiname}")


def plotte_abdeckung(abdeckung, k_key, zeiteinheit, dateiname):
    """Klassifiziert / gezogen und abgedeckter Views-Anteil je Gruppe und Periode."""
    cfg = ma.KLASSIFIKATIONEN[k_key]
    t = abdeckung[abdeckung["klassifikation"] == k_key]
    fig, achsen = plt.subplots(1, 2, figsize=(ma.GRAFIK_MINDESTBREITE, 5.2), sharey=True, sharex=True)
    kritisch = kritische_perioden(abdeckung, k_key)
    reihen = [("quote_klassifiziert", "Klassifiziert / gezogen", MIN_QUOTE_KLASSIFIZIERT),
              ("views_abgedeckt", "Views in Kanal-Einheiten mit klassifiziertem Video", MIN_VIEWS_ABGEDECKT)]
    for ax, (spalte, titel, grenze) in zip(achsen, reihen):
        achse_einrichten(ax, zeiteinheit, kritisch, t["rel_periode"].min(), t["rel_periode"].max() + 1)
        ax.axhline(grenze * 100, color="#8a8883", linestyle=":", linewidth=1.2)
        for gruppe, farbe in zip(cfg["gruppen"], cfg["farben"]):
            r = t[t["gruppe"] == gruppe].sort_values("rel_periode")
            ax.plot(r["rel_periode"], r[spalte] * 100, color=farbe, linewidth=1.5, marker="o", markersize=3.5,
                    markeredgecolor="white", markeredgewidth=0.4, zorder=3)
        r = t[t["gruppe"] == GESAMT].sort_values("rel_periode")
        ax.plot(r["rel_periode"], r[spalte] * 100, color="#0b0b0b", linewidth=2.4, zorder=4)
        ax.set_title(titel, fontsize=11)
        ax.set_xlabel(ZEIT[zeiteinheit]["xlabel"], fontsize=9)
        ax.set_ylim(0, 103)
    achsen[0].set_ylabel("Prozent")
    belegt = [(g, f) for g, f in zip(cfg["gruppen"], cfg["farben"]) if g in set(t["gruppe"])]
    griffe = [Line2D([], [], color=f, linewidth=1.5) for _, f in belegt] + [Line2D([], [], color="#0b0b0b", linewidth=2.4)]
    fig.legend(griffe, [*[g for g, _ in belegt], GESAMT], loc="lower center", frameon=False, fontsize=9, ncol=len(griffe))
    fig.suptitle(f"Abdeckung der gezogenen Videos nach {cfg['titel']} (grau = kritisch, gepunktet = Grenze)", fontsize=12)
    fig.tight_layout(rect=(0, 0.06, 1, 0.97))
    fig.savefig(PFAD_PLOTS / dateiname, dpi=150)
    plt.close(fig)
    print(f"[Plot] {PFAD_PLOTS / dateiname}")


def plotte_kanal_heatmap(kanal_tab, zeiteinheit, dateiname):
    """Heatmap klassifiziert / gezogen je Kanal und Periode; grau = nichts gezogen."""
    m = kanal_tab.pivot(index="kanal_name", columns="rel_periode", values="quote_klassifiziert")
    reihenfolge = kanal_tab.groupby("kanal_name")[["n_klassifiziert", "n_gezogen"]].sum()
    reihenfolge = (reihenfolge["n_klassifiziert"] / reihenfolge["n_gezogen"].replace(0, np.nan)).fillna(-1).sort_values()
    m = m.loc[reihenfolge.index]
    karte = LinearSegmentedColormap.from_list("abdeckung", ["#f7fafe", "#9cc3ee", "#2a78d6", "#0d3a73"])
    karte.set_bad("#e5e4e0")
    fig, ax = plt.subplots(figsize=(max(9, 0.22 * m.shape[1] + 5), max(5, 0.17 * m.shape[0] + 1.5)))
    bild = ax.imshow(m.to_numpy(float) * 100, aspect="auto", cmap=karte, vmin=0, vmax=100, interpolation="nearest")
    ax.set_yticks(range(len(m)), [str(n)[:38] for n in m.index], fontsize=6.5)
    schritt = 4 if m.shape[1] > 24 else 1
    ax.set_xticks(range(0, m.shape[1], schritt), m.columns[::schritt], fontsize=8)
    ax.set_xlabel(ZEIT[zeiteinheit]["xlabel"], fontsize=9)
    if 0 in m.columns:
        ax.axvline(list(m.columns).index(0) - 0.5, color="#eb6834", linewidth=1.2)
    fig.colorbar(bild, ax=ax, label="Klassifiziert / gezogen (%)", fraction=0.025, pad=0.01)
    ax.set_title("Abdeckung je Kanal (grau = keine gezogenen Videos; Linie = Kriegsbeginn)", fontsize=11)
    fig.tight_layout()
    fig.savefig(PFAD_PLOTS / dateiname, dpi=150)
    plt.close(fig)
    print(f"[Plot] {PFAD_PLOTS / dateiname}")


# =========================================================
# SCHRITT 5: Methodik-Datei
# =========================================================

def periodentabelle(abdeckung, k_key):
    """Trichter ueber alle Gruppen einer Klassifikation (Markdown und Konsole)."""
    t = abdeckung[(abdeckung["klassifikation"] == k_key) & (abdeckung["gruppe"] == GESAMT)].sort_values("rel_periode")
    aus = pd.DataFrame({
        "Periode": t["rel_periode"], "Start": t["periode_start"], "Voll": np.where(t["periode_voll"], "ja", "nein"),
        "Gesamt": t["n_gesamt"], "Gezogen": t["n_gezogen"], "Versuch": t["n_versucht"],
        "Transkript": t["n_transkript"], "Klassifiziert": t["n_klassifiziert"],
        "Quote %": (t["quote_klassifiziert"] * 100).round(1),
        "Kanäle aktiv": t["kanaele_aktiv"], "Kanäle abgedeckt": t["kanaele_abgedeckt"],
        "Views abgedeckt %": (t["views_abgedeckt"] * 100).round(1),
        "Krieg-Titel gezogen %": (t["krieg_titel_gezogen"] * 100).round(1),
        "Krieg-Titel klass. %": (t["krieg_titel_klassifiziert"] * 100).round(1),
        "Median-Views gezogen": t["views_median_gezogen"].round(0),
        "Median-Views klass.": t["views_median_klassifiziert"].round(0),
        "Status": t["status"]})
    return aus


def md_tabelle(df):
    """Markdown-Tabelle ohne Index; Zahlen ohne unnoetige Nullen, fehlende Werte als –."""
    def zelle(w):
        if pd.isna(w):
            return "–"
        return f"{w:g}" if isinstance(w, (float, np.floating)) else str(w)
    zeilen = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "---|" * df.shape[1]]
    zeilen += ["| " + " | ".join(zelle(w) for w in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(zeilen)


def schreibe_methodik(ergebnisse, aktive, info, kanaele, zusatz):
    L = ["# Marktanteile nach Themen: Methodik und Abdeckung", "",
         "Erzeugt von `step6_auswertung/marktanteil_rohdaten_topics.py`. Formeln im Docstring.", "",
         f"- Kanäle (wie 8i): {len(kanaele)}; Klassifikatoren: {', '.join(KLASSIFIKATOREN)}",
         f"- Themenzuordnung: {THEMA_ZUORDNUNG}" + (f" (Textanteil ≥ {THEMA_SCHWELLE})" if THEMA_ZUORDNUNG == "schwelle" else ""),
         f"- Normierung: faktor = alle long-Videos / klassifizierte Videos je Kanal x {NORMIERUNG_EINHEIT}",
         f"- Trainingsvideos ausgeschlossen: {TRAININGSVIDEOS_AUSSCHLIESSEN}",
         f"- IDs in `{ID_DATEI.name}`: {info['n_ids']:,}, davon in der Kanalliste: {info['n_ids_im_rahmen']:,}",
         f"- Klassifizierte Videos in der Datei: {info['n_klass_datei']:,}, davon in der Kanalliste: {info['n_klass_im_rahmen']:,}",
         f"- Videos mit Transkript, aber zu kurz zum Segmentieren (ganze Ziehung): {info['n_zu_kurz']}", "",
         "**Achtung:** Die Normierung gleicht Lücken nur innerhalb einer Kanal-Einheit aus und unterstellt dort "
         "zufälliges Fehlen. Die Klassifikatoren sind nur für Jan–Apr 2022 validiert. Nur große Verschiebungen "
         "(≳ 5 Prozentpunkte) bei häufigen Themen als Hinweis werten.", ""]
    for z_key, e in ergebnisse.items():
        k0 = aktive[0]
        L += [f"## Zeiteinheit: {z_key}", "", "### Abdeckung aller Gruppen", "",
              md_tabelle(periodentabelle(e["abdeckung"], k0)), ""]
        f = e["v"].loc[e["v"]["klassifiziert"], "faktor"]
        anteil_gross = (e["v"]["views"] * e["v"]["faktor"])[e["v"]["faktor"] > 10].sum() / (e["v"]["views"] * e["v"]["faktor"]).sum()
        L += [f"Faktor: Median {f.median():.1f}, 90 %-Quantil {f.quantile(.9):.1f}, Maximum {f.max():.0f}; "
              f"{anteil_gross:.0%} der normierten Views stammen von Videos mit Faktor > 10.", ""]
        L += ["### Validierung gegen die wahren Anteile aller Videos", "",
              "Mittlere absolute Abweichung in Prozentpunkten je Periode, über Gruppen.", ""]
        val = e["validierung"]
        for k_key in aktive:
            t = val[val["klassifikation"] == k_key].groupby("rel_periode")[
                ["abw_anteil_normiert", "abw_anteil_ungewichtet", "abw_angebot_normiert", "abw_angebot_ungewichtet"]
            ].agg(lambda s: s.abs().mean()).round(1).reset_index()
            t.columns = ["Periode", "Views normiert", "Views ungewichtet", "Uploads normiert", "Uploads ungewichtet"]
            L += [f"**{k_key}**", "", md_tabelle(t), ""]
        L += ["### Kritische Kanäle (mindestens eine gezogene Video-ID, nichts klassifiziert, ganzer Zeitraum)", ""]
        s = e["kanaele"].groupby("kanal_name")[["n_gesamt", "n_gezogen", "n_klassifiziert"]].sum().reset_index()
        s = s[(s["n_klassifiziert"] == 0) & (s["n_gezogen"] > 0)]
        L += [md_tabelle(s) if len(s) else "Keine.", ""]
        ohne = e["kanaele"].groupby("kanal_name")[["n_gesamt", "n_gezogen"]].sum().reset_index()
        ohne = ohne[ohne["n_gezogen"] == 0]
        if len(ohne):
            L += ["Kanäle mit Videos im Zeitraum, aber ohne gezogene ID:", "", md_tabelle(ohne), ""]
    z_key = next(iter(ergebnisse))
    L += [f"## Phasenwerte (gepoolt, normiert, Sample alle, Normierung nach {z_key})", ""]
    e = ergebnisse[z_key]
    for k_key in aktive:
        for klassifikator in KLASSIFIKATOREN:
            L += [f"### {k_key}, {klassifikator}", ""]
            for thema in [ALLE, *THEMEN]:
                views, angebot, fall = phasenwerte(e["v"], k_key, klassifikator, thema)
                titel = "Alle Videos" if thema == ALLE else THEMA_TITEL.get(thema, thema)
                faelle = ", ".join(f"{p} {n:,}" for p, n in fall.items())
                L += [f"**{titel}**, klassifizierte Videos: {faelle}", "", "Views-Anteil (%):", "",
                      md_tabelle(views.round(1).reset_index(names="Gruppe")), "",
                      "Upload-Anteil (%):", "", md_tabelle(angebot.round(1).reset_index(names="Gruppe")), ""]
    pfad = PFAD_PLOTS / f"marktanteil_topics_methodik{zusatz}.md"
    pfad.write_text("\n".join(L), encoding="utf-8")
    print(f"[Methodik] {pfad}")


# =========================================================
# MAIN
# =========================================================

def main():
    if not KLASSIFIKATOREN or not set(KLASSIFIKATOREN) <= {"dict", "lr"}:
        raise SystemExit(f'KLASSIFIKATOREN muss nicht-leere Teilmenge von ["dict", "lr"] sein, nicht {KLASSIFIKATOREN!r}.')
    falsch = [t for t in THEMEN if t not in THEMA_TITEL]
    if not THEMEN or falsch:
        raise SystemExit(f"THEMEN darf nicht leer sein; unbekannt: {falsch}, erlaubt: {list(THEMA_TITEL)}.")
    if THEMA_ZUORDNUNG not in ("schwelle", "anteilig"):
        raise SystemExit(f"THEMA_ZUORDNUNG muss 'schwelle' oder 'anteilig' sein, nicht {THEMA_ZUORDNUNG!r}.")
    if not 0 < THEMA_SCHWELLE <= 1:
        raise SystemExit(f"THEMA_SCHWELLE muss in (0, 1] liegen, nicht {THEMA_SCHWELLE!r}.")
    if not ZEITEINHEITEN or not set(ZEITEINHEITEN) <= set(ZEIT):
        raise SystemExit(f"ZEITEINHEITEN muss nicht-leere Teilmenge von {list(ZEIT)} sein, nicht {ZEITEINHEITEN!r}.")
    if NORMIERUNG_EINHEIT not in ("zeiteinheit", "woche"):
        raise SystemExit(f"NORMIERUNG_EINHEIT muss 'zeiteinheit' oder 'woche' sein, nicht {NORMIERUNG_EINHEIT!r}.")
    for name, wert in [("TRAININGSVIDEOS_AUSSCHLIESSEN", TRAININGSVIDEOS_AUSSCHLIESSEN),
                       ("NUR_VOLLE_PERIODEN", NUR_VOLLE_PERIODEN), ("ABSOLUT_VERSION", ABSOLUT_VERSION)]:
        if not isinstance(wert, bool):
            raise SystemExit(f"{name} muss True oder False sein, nicht {wert!r}.")
    if not isinstance(MIN_KLASSIFIZIERT, int) or MIN_KLASSIFIZIERT < 1:
        raise SystemExit(f"MIN_KLASSIFIZIERT muss eine ganze Zahl >= 1 sein, nicht {MIN_KLASSIFIZIERT!r}.")
    if not (0 <= MIN_QUOTE_KLASSIFIZIERT <= 1 and 0 <= MIN_VIEWS_ABGEDECKT <= 1 and 0 <= LOWESS_WOCHE <= 1):
        raise SystemExit("MIN_QUOTE_KLASSIFIZIERT, MIN_VIEWS_ABGEDECKT und LOWESS_WOCHE muessen in [0, 1] liegen.")
    if MAX_SELEKTION_KRIEG_PP < 0:
        raise SystemExit(f"MAX_SELEKTION_KRIEG_PP muss >= 0 sein, nicht {MAX_SELEKTION_KRIEG_PP!r}.")
    for name, (von, bis) in PHASEN.items():
        if pd.Timestamp(von) > pd.Timestamp(bis):
            raise SystemExit(f"PHASEN[{name!r}]: von liegt nach bis.")
    for pfad in (ID_DATEI, VIDEO_DATEI, STATUS_DATEI):
        if not pfad.exists():
            raise SystemExit(f"Datei fehlt: {pfad} (classify_segment_topics.py bzw. random_video_ids_for_channel_period.py).")

    PFAD_PLOTS.mkdir(parents=True, exist_ok=True)
    aktive = [k for k in ma.KLASSIFIKATIONEN if k not in ma.SCHALTER or getattr(ma, ma.SCHALTER[k])]
    kanaele = lade_kanaele()
    videos, info, start, ende = lade_videos(kanaele, aktive)
    zusatz = ma.datei_zusatz()
    # Nach KOMBI_VERSION aus 8i: "kombi"/"alle" zeigt beide Samples in einer Grafik
    grafik_samples = [["alle", "vorkrieg"]] if ma.KOMBI_VERSION == "kombi" else (
        [["alle"], ["vorkrieg"]] if ma.KOMBI_VERSION == "getrennt" else [["alle", "vorkrieg"], ["alle"], ["vorkrieg"]])

    ergebnisse = {}
    for z_key in ZEITEINHEITEN:
        v, perioden = setze_periode(videos, z_key, start, ende)
        abdeckung = abdeckung_gruppen(v, aktive, perioden)
        kanal_tab = abdeckung_kanaele(v, perioden)
        val = validierung(v, aktive)
        print(f"\n[Abdeckung] {z_key}, alle Gruppen ({aktive[0]}):")
        with pd.option_context("display.width", 250, "display.max_columns", None, "display.max_rows", None):
            print(periodentabelle(abdeckung, aktive[0]).drop(columns=["Median-Views gezogen", "Median-Views klass."]).to_string(index=False))
        vollst = abdeckung[(abdeckung["klassifikation"] == aktive[0]) & (abdeckung["gruppe"] == GESAMT)]
        print(f"[Abdeckung] Perioden, in denen alle gezogenen Videos klassifiziert sind: "
              f"{int((vollst['n_fehlend'] == 0).sum())} von {len(vollst)}; "
              f"kritisch: {vollst.loc[vollst['status'] == 'kritisch', 'rel_periode'].to_list()}")

        werte = []
        for k_key in aktive:
            kritisch = kritische_perioden(abdeckung, k_key)
            plotte_abdeckung(abdeckung, k_key, z_key, f"abdeckung_{k_key}_{z_key}{zusatz}.png")
            for klassifikator in KLASSIFIKATOREN:
                je_sample = {}
                for s_key, (_, s_filter) in ma.SAMPLES.items():
                    ids = set(kanaele.loc[s_filter(kanaele), "channel_id"])
                    v_s = v[v["channel_id"].isin(ids)]
                    je_sample[s_key] = {t: berechne_marktanteile(v_s, k_key, klassifikator, t) for t in [ALLE, *THEMEN]}
                    for t, a in je_sample[s_key].items():
                        if len(a):
                            werte.append(a.assign(sample=s_key, klassifikation=k_key, klassifikator=klassifikator, thema=t))
                for samples in grafik_samples:
                    auswahl = {s: je_sample[s] for s in samples}
                    teil = "" if len(samples) > 1 else f"_{samples[0]}"
                    basis = f"marktanteil_topics_{k_key}_{klassifikator}_{z_key}{teil}{zusatz}"
                    plotte_marktanteile(auswahl, k_key, klassifikator, z_key, kritisch, f"{basis}.png")
                    if ABSOLUT_VERSION:
                        plotte_marktanteile(auswahl, k_key, klassifikator, z_key, kritisch, f"{basis}_absolut.png", absolut=True)
        csv = pd.concat(werte).merge(perioden, on="rel_periode")
        erste = ["sample", "klassifikation", "klassifikator", "thema", "rel_periode", "periode_start", "periode_ende",
                 "periode_voll", "gruppe", "anteil", "angebot_anteil", "anteil_ungewichtet", "angebot_anteil_ungewichtet",
                 "views_summe", "n_videos", "views_gesamt", "n_gesamt", "n_klassifiziert", "n_klassifiziert_gesamt",
                 "top_video_anteil"]
        csv[erste].rename(columns={"rel_periode": f"rel_{z_key}"}).to_csv(
            PFAD_PLOTS / f"marktanteil_topics_{z_key}{zusatz}.csv", index=False)
        abdeckung.rename(columns={"rel_periode": f"rel_{z_key}"}).to_csv(PFAD_PLOTS / f"abdeckung_{z_key}{zusatz}.csv", index=False)
        kanal_tab.rename(columns={"rel_periode": f"rel_{z_key}"}).to_csv(PFAD_PLOTS / f"abdeckung_kanal_{z_key}{zusatz}.csv", index=False)
        val.rename(columns={"rel_periode": f"rel_{z_key}"}).to_csv(PFAD_PLOTS / f"validierung_{z_key}{zusatz}.csv", index=False)
        plotte_kanal_heatmap(kanal_tab, z_key, f"abdeckung_kanaele_{z_key}{zusatz}.png")
        ergebnisse[z_key] = dict(v=v, abdeckung=abdeckung, kanaele=kanal_tab, validierung=val)
    schreibe_methodik(ergebnisse, aktive, info, kanaele, zusatz)


if __name__ == "__main__":
    main()

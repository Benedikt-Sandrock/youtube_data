# -*- coding: utf-8 -*-
"""
strukturbruch_rohdaten.py

Gab es mit dem Kriegsbeginn einen Strukturbruch im Erfolg der alternativen rechten
Kanaele relativ zum ÖRR (Forschungsfrage 2)? Bezug ist die Grafik
marktanteil_medientyp_ideologie_kombiniert_long_quartal_manuell_absolut.png.
Datenbasis: outputs/stata_rohdaten/ (videos_roh.dta, kanaele_roh.dta) und die manuelle
Klassifikation channels_check.xlsx. Das Skript braucht linearmodels nicht.

Sample
------
media_category 1 = ÖRR (Referenz), 5 = Alternative rechts; sample in [1, 2, 3];
foreign != 1; nur format == "long"; Videos ohne Views fallen weg. Die Traditionellen
sind wie in event_study_rohdaten.py nicht enthalten. Die Gruppen kommen direkt aus
media_category und koennen deshalb leicht von den Gruppen der Grafik abweichen (dort
Medientyp x Ideologie aus kanaele_roh plus manuelle Ergaenzung).
Monate und Quartale wie in der Grafik (relativ_periode): Monat 0 beginnt am 24.02.2022,
Quartal = floor(Monat / 3). Standardfenster: Monat -36..50 = Quartal -12..16.

Schritt 1: Strukturbruchtests auf der Zeitreihe D_t (Monate)
------------------------------------------------------------
D_t = ln(Summe Alternative rechts) - ln(Summe ÖRR), fuer Views, Uploads und Views je
Video (ln(Views-Summe / Upload-Summe)). Modelle mit Bruch am Monat tau:
    niveau_und_trend: D_t = a + b t + delta 1[t >= tau] + theta (t - tau) 1[t >= tau] + u_t
    nur_trend:        nur theta (stetiger Knick)
    nur_niveau:       nur delta
- Sup-F (Quandt-Andrews): groesstes F(tau) ueber alle Kandidaten (TRIMMUNG).
- Die Tabellen von Andrews gelten nicht fuer trendbehaftete Regressoren. p-Werte und
  kritische Werte kommen deshalb aus einem Bootstrap mit zwei Nullhypothesen:
  "AR" = stationaer um einen Trend mit AR(p)-Fehlern (p per BIC) und
  "RW" = Random Walk mit Drift (konservative Schranke, weil eine persistente Reihe
  auch ohne Bruch grosse F-Werte erzeugt).
- F am vorab festgelegten Datum (Chow-Test, Monat 0) mit denselben Nullhypothesen, ohne
  Suche nach dem Datum.
- Konfidenzmenge fuer das Bruchdatum: Inversion der LR-Statistik (Hansen 2000), kritischer
  Wert aus einem Bootstrap unter dem geschaetzten Bruchmodell. Nur sinnvoll lesbar, wenn
  der Sup-F-Test tatsaechlich einen Bruch zeigt.
- Mehrere Brueche (nur MEHRFACH_OUTCOME): global optimale Daten per dynamischer
  Programmierung (Bai-Perron, je Segment eigener Achsenabschnitt und Trend), sequenzielle
  Tests F(l+1 | l) mit Bootstrap unter dem l-Bruch-Modell, dazu BIC.
- Placebo: dieselben Tests nur auf den Vorkriegsmonaten (PLACEBO_FENSTER).
- Stichproben (BRUCH_SAMPLES): alle = durchgezogene Linie der Grafik, vorkrieg =
  gestrichelte Linie (sample_vorkrieg == 1), balanciert = erstes langes Video vor
  Fensterbeginn (ohne Eintritte), vorkrieg_ohne_top = ohne die TOP_KANAELE.

Schritt 2: Event Study mit langem Fenster (Kanal x Quartal)
-----------------------------------------------------------
    y_ck = a_c + l_k + sum_{j != REFERENZ_QUARTAL} d_j * Alt_c * 1[k = j] + e_ck
y = ln(Views-Summe + 1), ln(Uploads + 1), ln(Views je Video + 1). Kanal-FE a_c,
Quartals-FE l_k, Referenz k = -1. Die Standardfehler sind nach Kanal geclustert
(CR1 wie xtreg, fe). Wegen der wenigen ÖRR-Kanaele gibt es zusaetzlich p-Werte aus einem
Wild-Cluster-Bootstrap (Webb-Gewichte, unrestricted, t-Statistik).
Ausgewiesen: d_k, gemeinsame Vortrend-Tests (alle k <= -2; k = -6..-2), linearer
Vortrend, Mittel von d_k in Jahresbloecken (POST_BLOECKE).
Varianten (ES_VARIANTEN): balanciert, balanciert_ab_m8 (Fenster ab -8, mehr Kanaele),
vorkrieg, alle (unbalanciert), balanciert_ohne_top, balanciert_leer_null.
Bins ohne Upload sind fehlend (intensive Marge), ausser in balanciert_leer_null (ln(0+1)).

Grenzen (stehen auch im Bericht)
--------------------------------
Der Test belegt einen Bruch in der relativen Entwicklung, keinen kausalen Kriegseffekt.
Views sind ein Snapshot; geloeschte Videos und Kanaele fehlen (Ueberlebensverzerrung). Die
Trennung von Schritt 1 (Summen, grosse Kanaele dominieren) und Schritt 2 (Kanaele gleich
gewichtet) ist gewollt: Weichen die Ergebnisse ab, tragen wenige grosse Kanaele den Effekt.

Ausgabe nach OUTPUTS / "segment_analysis" / "strukturbruch_rohdaten"
--------------------------------------------------------------------
- bruch_<outcome>.png: D_t mit Anpassung (oben) und F-Profil (unten) je Stichprobe
- es_<outcome>_<variante>.png: Verlauf je Gruppe und Differenz d_k
- es_vergleich_<outcome>.png: d_k aller Varianten nebeneinander
- monatsreihen.csv, bruchtests.csv, es_koeffizienten.csv
- regression_results/strukturbruch_ergebnisse.md: Methodik, Funnel, alle Tabellen

Ausfuehren aus dem Repo-Root (liest videos_roh.dta, vorher Arbeitsspeicher pruefen):
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.strukturbruch_rohdaten
"""

import datetime as dt
import math

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy import signal, stats
import statsmodels.api as sm

from youtube_code.config import OUTPUTS, STATA_OUTPUT
from youtube_code.step4_transcript_download.period import relativ_periode


# =========================================================
# CONFIG
# =========================================================

ROHDATEN_PFAD = STATA_OUTPUT                     # Ordner mit videos_roh.dta, kanaele_roh.dta
CHANNELS_CHECK = STATA_OUTPUT / "channels_check.xlsx"
PFAD_OUT = OUTPUTS / "segment_analysis" / "strukturbruch_rohdaten"
PFAD_REG = PFAD_OUT / "regression_results"

KRIEGSBEGINN = "2022-02-24"                      # ISO-Datum, Beginn von Monat 0
MONATS_FENSTER = (-36, 50)                       # (min, max), min < 0 <= max; -36 = 24.02.2019
PLACEBO_FENSTER = (-36, -1)                      # Vorkriegsmonate, max < 0
QUARTALS_FENSTER = (-12, 16)                     # (min, max), min <= -2, max >= 0
REFERENZ_QUARTAL = -1                            # normiertes Quartal, < 0 und im Fenster

MEDIA_CATEGORIES = {1: "ÖRR", 5: "Alternative rechts"}  # genau zwei Codes aus channels_check
REFERENZ_GRUPPE = "ÖRR"                          # Wert aus MEDIA_CATEGORIES
SAMPLE_CODES = [1, 2, 3]                         # Teilmenge von 0..5, Spalte "sample"
FORMAT = "long"                                  # "long" oder "alle" (long, short, live)
# Kanaele mit starkem Einfluss, dieselbe Liste wie "ohne_top_alt" in event_study_rohdaten.py
TOP_KANAELE = ["Vermietertagebuch - Alexander Raue",
               "Erfolgskanal - Community für Finanzen & Wirtschaft",
               "Kettner-Edelmetalle (Gold & Silber)",
               "Achtung, Reichelt!"]             # exakte channel_title

# --- Schritt 1 ---
BRUCH_OUTCOMES = {"ln_views": "ln(Views)", "ln_uploads": "ln(Uploads)",
                  "ln_views_pro_video": "ln(Views je Video)"}
MEHRFACH_OUTCOME = "ln_views"                    # Schluessel aus BRUCH_OUTCOMES
# basis: "alle" | "vorkrieg" | "balanciert"; ohne_top: True/False
BRUCH_SAMPLES = {"alle": {"basis": "alle", "ohne_top": False},
                 "vorkrieg": {"basis": "vorkrieg", "ohne_top": False},
                 "balanciert": {"basis": "balanciert", "ohne_top": False},
                 "vorkrieg_ohne_top": {"basis": "vorkrieg", "ohne_top": True}}
BRUCH_MODELLE = {"niveau_und_trend": "Niveau und Trend", "nur_trend": "nur Trend (Knick)",
                 "nur_niveau": "nur Niveau"}     # Schluessel fest, Werte nur Beschriftung
TRIMMUNG = 0.15                                  # Anteil an jedem Rand, 0 < x < 0.5
MAX_BRUECHE = 3                                  # ganze Zahl >= 1
AR_MAX = 6                                       # hoechste AR-Ordnung im Bootstrap, >= 0
BOOTSTRAP_B = 1999                               # Einzelbruchtests, >= 199
BOOTSTRAP_B_MEHRFACH = 499                       # sequenzielle Tests, >= 99
SEED = 20220224                                  # ganze Zahl

# --- Schritt 2 ---
ES_OUTCOMES = {"ln_views": "ln(Views-Summe + 1)", "ln_uploads": "ln(Uploads + 1)",
               "ln_views_pro_video": "ln(Views je Video + 1)"}
# basis: "alle" | "vorkrieg" | "balanciert"; fenster_start: Quartal >= QUARTALS_FENSTER[0]
# ohne_top: True/False; leere_bins: "fehlend" | "null"
ES_VARIANTEN = {
    "balanciert": {"basis": "balanciert", "fenster_start": -12, "ohne_top": False, "leere_bins": "fehlend"},
    "balanciert_ab_m8": {"basis": "balanciert", "fenster_start": -8, "ohne_top": False, "leere_bins": "fehlend"},
    "vorkrieg": {"basis": "vorkrieg", "fenster_start": -12, "ohne_top": False, "leere_bins": "fehlend"},
    "alle": {"basis": "alle", "fenster_start": -12, "ohne_top": False, "leere_bins": "fehlend"},
    "balanciert_ohne_top": {"basis": "balanciert", "fenster_start": -12, "ohne_top": True, "leere_bins": "fehlend"},
    "balanciert_leer_null": {"basis": "balanciert", "fenster_start": -12, "ohne_top": False, "leere_bins": "null"},
}
# Jahresbloecke vorab und nicht nach Sichtung der Grafik gewaehlt (inklusive Grenzen, >= 0)
POST_BLOECKE = {"Jahr 1 (0 bis 3)": (0, 3), "Jahr 2 (4 bis 7)": (4, 7),
                "Jahr 3 (8 bis 11)": (8, 11), "ab Jahr 4 (12 bis 16)": (12, 16)}
KURZER_VORTREND = (-6, -2)                       # Bereich fuer den zweiten Vortrend-Test
WILD_B = 1999                                    # Wild-Cluster-Bootstrap, >= 199
MIN_KANAELE_GRUPPE = 3                           # Mindestzahl Kanaele je Gruppe, >= 2

# Nur Grafik (Beschriftung -> ISO-Datum), wie EREIGNISSE in marktanteil_rohdaten_plots.py
KONTEXT = {"KenFM deleted": "2021-01-22", "BTW 2021 / RT DE deleted": "2021-09-26",
           "US-Wahl 2024 / Ampel Ende": "2024-11-05", "BTW 2025": "2025-02-23"}
FARBEN = {"ÖRR": "#2a78d6", "Alternative rechts": "#e87ba4"}  # wie marktanteil_rohdaten_plots
MARKER = {"ÖRR": "o", "Alternative rechts": "s"}

# =========================================================


def alt_gruppe():
    return next(g for g in MEDIA_CATEGORIES.values() if g != REFERENZ_GRUPPE)


def pruefe_config():
    fehler = []
    a, b = MONATS_FENSTER
    if not a < 0 <= b:
        fehler.append("MONATS_FENSTER muss min < 0 <= max erfuellen")
    if not (PLACEBO_FENSTER[0] < PLACEBO_FENSTER[1] < 0):
        fehler.append("PLACEBO_FENSTER muss vollstaendig vor dem Krieg liegen")
    k0, k1 = QUARTALS_FENSTER
    if not (k0 <= -2 and k1 >= 0 and k0 <= REFERENZ_QUARTAL < 0):
        fehler.append("QUARTALS_FENSTER/REFERENZ_QUARTAL ungueltig")
    if len(MEDIA_CATEGORIES) != 2 or REFERENZ_GRUPPE not in MEDIA_CATEGORIES.values():
        fehler.append("MEDIA_CATEGORIES braucht genau zwei Gruppen, darunter REFERENZ_GRUPPE")
    if set(MEDIA_CATEGORIES.values()) != set(FARBEN) or set(FARBEN) != set(MARKER):
        fehler.append("FARBEN und MARKER muessen genau die Gruppen aus MEDIA_CATEGORIES enthalten")
    if not set(SAMPLE_CODES) <= set(range(6)):
        fehler.append("SAMPLE_CODES muss eine Teilmenge von 0..5 sein")
    if FORMAT not in ("long", "alle"):
        fehler.append("FORMAT muss 'long' oder 'alle' sein")
    if MEHRFACH_OUTCOME not in BRUCH_OUTCOMES:
        fehler.append("MEHRFACH_OUTCOME muss in BRUCH_OUTCOMES sein")
    for name, s in BRUCH_SAMPLES.items():
        if s["basis"] not in ("alle", "vorkrieg", "balanciert"):
            fehler.append(f"BRUCH_SAMPLES[{name}]: basis ungueltig")
    if set(BRUCH_MODELLE) != {"niveau_und_trend", "nur_trend", "nur_niveau"}:
        fehler.append("BRUCH_MODELLE: Schluessel duerfen nicht geaendert werden")
    if not 0 < TRIMMUNG < 0.5:
        fehler.append("TRIMMUNG muss zwischen 0 und 0.5 liegen")
    if not isinstance(MAX_BRUECHE, int) or MAX_BRUECHE < 1:
        fehler.append("MAX_BRUECHE muss ganze Zahl >= 1 sein")
    if AR_MAX < 0 or BOOTSTRAP_B < 199 or BOOTSTRAP_B_MEHRFACH < 99 or WILD_B < 199:
        fehler.append("AR_MAX >= 0, BOOTSTRAP_B >= 199, BOOTSTRAP_B_MEHRFACH >= 99, WILD_B >= 199")
    for name, v in ES_VARIANTEN.items():
        if v["basis"] not in ("alle", "vorkrieg", "balanciert"):
            fehler.append(f"ES_VARIANTEN[{name}]: basis ungueltig")
        if v["leere_bins"] not in ("fehlend", "null"):
            fehler.append(f"ES_VARIANTEN[{name}]: leere_bins ungueltig")
        if not k0 <= v["fenster_start"] <= REFERENZ_QUARTAL - 1:
            fehler.append(f"ES_VARIANTEN[{name}]: fenster_start ausserhalb des Fensters")
    if any(x < 0 or y < x for x, y in POST_BLOECKE.values()):
        fehler.append("POST_BLOECKE: Grenzen muessen 0 <= a <= b sein")
    if MIN_KANAELE_GRUPPE < 2:
        fehler.append("MIN_KANAELE_GRUPPE muss >= 2 sein")
    if fehler:
        raise SystemExit("Konfigurationsfehler:\n  - " + "\n  - ".join(fehler))


# ---------------------------------------------------------
# Daten
# ---------------------------------------------------------

def monat_start(m):
    return pd.Timestamp(KRIEGSBEGINN) + pd.DateOffset(months=int(m))


def lade_kanaele(funnel):
    c = pd.read_excel(CHANNELS_CHECK, sheet_name=0,
                      usecols=["channel_id", "channel_title", "media_category", "sample", "foreign"])
    if c["channel_id"].duplicated().any():
        raise SystemExit("channels_check.xlsx: channel_id mehrfach vorhanden")
    c = c[c["media_category"].isin(MEDIA_CATEGORIES)]
    funnel["media_category passend"] = len(c)
    c = c[c["sample"].isin(SAMPLE_CODES)]
    funnel[f"sample in {SAMPLE_CODES}"] = len(c)
    c = c[c["foreign"] != 1]
    funnel["ohne foreign == 1"] = len(c)
    # convert_categoricals=False: sample_vorkrieg bleibt 0/1 statt Wertelabel
    k = pd.read_stata(ROHDATEN_PFAD / "kanaele_roh.dta", columns=["channel_id", "sample_vorkrieg"],
                      convert_categoricals=False)
    c = c.merge(k, on="channel_id", how="inner")
    funnel["in kanaele_roh"] = len(c)
    c["gruppe"] = c["media_category"].map(MEDIA_CATEGORIES)
    titel = set(c["channel_title"].str.strip().str.lower())
    unbekannt = [t for t in TOP_KANAELE if t.strip().lower() not in titel]
    if unbekannt:
        raise SystemExit(f"TOP_KANAELE nicht im Sample: {unbekannt}")
    c["top"] = c["channel_title"].str.strip().str.lower().isin({t.strip().lower() for t in TOP_KANAELE})
    return c.reset_index(drop=True)


def lade_videos(kanal_ids, funnel):
    v = pd.read_stata(ROHDATEN_PFAD / "videos_roh.dta",
                      columns=["channel_id", "upload_ts", "views", "format"])
    v = v[v["channel_id"].isin(kanal_ids) & v["upload_ts"].notna()].copy()
    v["format"] = v["format"].astype(str)
    v = v[v["format"] == "long"] if FORMAT == "long" else v[v["format"].isin(["long", "short", "live"])]
    funnel["Videos im Format"] = len(v)
    funnel["davon ohne Views (verworfen)"] = int(v["views"].isna().sum())
    v = v[v["views"].notna()]
    v["monat"] = relativ_periode(v["upload_ts"], pd.Timestamp(KRIEGSBEGINN), 1)
    return v[["channel_id", "upload_ts", "views", "monat"]]


def kanal_ids_je_basis(kan, erstes, basis, ohne_top, stichtag):
    """Kanal-IDs einer Stichprobe; stichtag = Beginn des Fensters (nur 'balanciert')."""
    k = kan[kan["channel_id"].isin(erstes.index)]
    if ohne_top:
        k = k[~k["top"]]
    if basis == "vorkrieg":
        k = k[k["sample_vorkrieg"] == 1]
    elif basis == "balanciert":
        k = k[k["channel_id"].map(erstes) < stichtag]
    return k


def monatsreihen(videos, k_sample, fenster):
    """Gruppensummen je Monat und D_t je Outcome. Monate ohne Daten bleiben fehlend."""
    monate = np.arange(fenster[0], fenster[1] + 1)
    gruppe = k_sample.set_index("channel_id")["gruppe"]
    v = videos[videos["channel_id"].isin(gruppe.index) & videos["monat"].between(*fenster)]
    agg = (v.assign(gruppe=v["channel_id"].map(gruppe))
             .groupby(["gruppe", "monat"])["views"].agg(views="sum", uploads="size"))
    alt, ref = alt_gruppe(), REFERENZ_GRUPPE
    d = pd.DataFrame({"monat": monate})
    for g, kurz in [(alt, "alt"), (ref, "ref")]:
        for s in ["views", "uploads"]:
            x = agg[s].xs(g, level="gruppe") if g in agg.index.get_level_values("gruppe") else pd.Series(dtype=float)
            d[f"{s}_{kurz}"] = x.reindex(monate).fillna(0).to_numpy(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        d["ln_views"] = np.log(d["views_alt"]) - np.log(d["views_ref"])
        d["ln_uploads"] = np.log(d["uploads_alt"]) - np.log(d["uploads_ref"])
        d["ln_views_pro_video"] = (np.log(d["views_alt"] / d["uploads_alt"])
                                   - np.log(d["views_ref"] / d["uploads_ref"]))
    return d.replace([np.inf, -np.inf], np.nan)


# ---------------------------------------------------------
# Schritt 1: Einzelbruch
# ---------------------------------------------------------

def kandidaten(T, trim=None):
    h = math.ceil((TRIMMUNG if trim is None else trim) * T)
    return np.arange(h, T - h + 1)


def _x_null(T):
    return np.column_stack([np.ones(T), np.arange(T, dtype=float)])


def _regressoren(T, kand, modell):
    t = np.arange(T, dtype=float)[:, None]
    stufe = (t >= kand[None, :]).astype(float)
    rampe = (t - kand[None, :]) * stufe
    return {"niveau_und_trend": [stufe, rampe], "nur_trend": [rampe], "nur_niveau": [stufe]}[modell]


def f_profil(Y, kand, modell):
    """F(tau) je Kandidat und Spalte von Y (T x B). Rueckgabe: F (K x B), SSR (K x B)."""
    T = Y.shape[0]
    Q, _ = np.linalg.qr(_x_null(T))
    rest = lambda A: A - Q @ (Q.T @ A)
    Yr = rest(Y)
    ssr0 = (Yr ** 2).sum(axis=0)
    Zs = [rest(z) for z in _regressoren(T, kand, modell)]
    if len(Zs) == 1:
        z = Zs[0]
        red = (z.T @ Yr) ** 2 / (z ** 2).sum(axis=0, keepdims=True).T
    else:
        z1, z2 = Zs
        a = (z1 ** 2).sum(axis=0)[:, None]
        b = (z1 * z2).sum(axis=0)[:, None]
        c = (z2 ** 2).sum(axis=0)[:, None]
        u, w = z1.T @ Yr, z2.T @ Yr
        red = (c * u ** 2 - 2 * b * u * w + a * w ** 2) / (a * c - b ** 2)
    ssr = np.maximum(ssr0[None, :] - red, 1e-12)
    q = len(Zs)
    return (red / q) / (ssr / (T - 2 - q)), ssr


def ar_anpassen(u, p_max=None):
    """AR(p) per Yule-Walker (immer stationaer), p per BIC. Rueckgabe: phi, Innovationen."""
    p_max = AR_MAX if p_max is None else p_max
    u = np.asarray(u, float) - np.mean(u)
    T = len(u)
    p_max = min(p_max, max(T // 4, 0))
    gamma = np.array([u[:T - k] @ u[k:] / T for k in range(p_max + 1)])
    bester = (T * np.log(max(gamma[0], 1e-12)), np.zeros(0))
    for p in range(1, p_max + 1):
        R = np.array([[gamma[abs(i - j)] for j in range(p)] for i in range(p)])
        phi = np.linalg.solve(R, gamma[1:p + 1])
        s2 = gamma[0] - phi @ gamma[1:p + 1]
        bic = T * np.log(max(s2, 1e-12)) + p * np.log(T)
        if bic < bester[0]:
            bester = (bic, phi)
    phi = bester[1]
    eps = signal.lfilter(np.r_[1.0, -phi], [1.0], u)[len(phi):]
    return phi, eps - eps.mean()


def simuliere_ar(phi, eps, T, B, rng, burn=100):
    ziehung = rng.choice(eps, size=(T + burn, B), replace=True)
    return signal.lfilter([1.0], np.r_[1.0, -phi], ziehung, axis=0)[burn:]


def simuliere_rw(y, B, rng):
    d = np.diff(y)
    d = d - d.mean()
    pfad = np.cumsum(rng.choice(d, size=(len(y) - 1, B), replace=True), axis=0)
    return np.vstack([np.zeros((1, B)), pfad])


def bruch_ols(y, tau_idx, modell):
    """OLS mit HAC-SE am Bruchindex; delta/theta sind None, wenn nicht im Modell."""
    T = len(y)
    z = _regressoren(T, np.array([tau_idx]), modell)
    X = np.column_stack([_x_null(T)] + z)
    lag = int(4 * (T / 100) ** (2 / 9))
    r = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": lag, "use_correction": True})
    aus = {"vortrend": r.params[1], "vortrend_se": r.bse[1], "delta": None, "delta_se": None,
           "theta": None, "theta_se": None, "fit": r.fittedvalues}
    namen = {"niveau_und_trend": ["delta", "theta"], "nur_trend": ["theta"], "nur_niveau": ["delta"]}[modell]
    for i, n in enumerate(namen):
        aus[n], aus[n + "_se"] = r.params[2 + i], r.bse[2 + i]
    return aus


def bruchtest(y, monate, modell, B, rng, krieg=0):
    y = np.asarray(y, float)
    T = len(y)
    kand = kandidaten(T)
    F, ssr = f_profil(y[:, None], kand, modell)
    F, ssr = F[:, 0], ssr[:, 0]
    i_max = int(np.argmax(F))
    sup_f = float(F[i_max])

    # Nullverteilungen: AR um einen Trend und Random Walk
    X = _x_null(T)
    u0 = y - X @ np.linalg.lstsq(X, y, rcond=None)[0]
    phi0, eps0 = ar_anpassen(u0)
    F_ar, _ = f_profil(simuliere_ar(phi0, eps0, T, B, rng), kand, modell)
    F_rw, _ = f_profil(simuliere_rw(y, B, rng), kand, modell)
    sup_ar, sup_rw = F_ar.max(axis=0), F_rw.max(axis=0)
    pwert = lambda b, x: float((1 + np.sum(b >= x)) / (len(b) + 1))

    # Chow-Test am vorab festgelegten Datum
    idx0 = {int(monate[t]): j for j, t in enumerate(kand)}.get(krieg)
    f0 = p0_ar = p0_rw = None
    if idx0 is not None:
        f0 = float(F[idx0])
        p0_ar, p0_rw = pwert(F_ar[idx0], f0), pwert(F_rw[idx0], f0)

    # Konfidenzmenge per LR-Inversion unter dem geschaetzten Bruchmodell
    tau_idx = int(kand[i_max])
    fit = bruch_ols(y, tau_idx, modell)
    u1 = y - fit["fit"]
    phi1, eps1 = ar_anpassen(u1)
    Y1 = fit["fit"][:, None] + simuliere_ar(phi1, eps1, T, B, rng)
    _, ssr_b = f_profil(Y1, kand, modell)
    lr_b = T * np.log(ssr_b[i_max, :] / ssr_b.min(axis=0))
    q95 = float(np.quantile(lr_b, 0.95))
    lr = T * np.log(ssr / ssr.min())
    menge = [int(monate[t]) for t, x in zip(kand, lr) if x <= q95]

    return {"modell": modell, "T": T, "tau": int(monate[tau_idx]), "sup_f": sup_f,
            "krit5_ar": float(np.quantile(sup_ar, 0.95)), "krit5_rw": float(np.quantile(sup_rw, 0.95)),
            "p_ar": pwert(sup_ar, sup_f), "p_rw": pwert(sup_rw, sup_f),
            "f_krieg": f0, "p_krieg_ar": p0_ar, "p_krieg_rw": p0_rw,
            "menge": menge, "ar_ordnung": len(phi0), "ar_summe": float(phi0.sum()),
            "koef_tau": fit,
            "koef_krieg": bruch_ols(y, int(kand[idx0]), modell) if idx0 is not None else None,
            "profil_monate": monate[kand], "profil_f": F}


# ---------------------------------------------------------
# Schritt 1: Mehrere Brueche
# ---------------------------------------------------------

def ssr_segmente(y):
    """SSR einer linearen Trendregression fuer alle Segmente [i, j); Matrix (T+1) x (T+1)."""
    T = len(y)
    t = np.arange(T, dtype=float)
    s_t = np.r_[0.0, np.cumsum(t)]
    s_tt = np.r_[0.0, np.cumsum(t * t)]
    s_y = np.r_[0.0, np.cumsum(y)]
    s_ty = np.r_[0.0, np.cumsum(t * y)]
    s_yy = np.r_[0.0, np.cumsum(y * y)]
    idx = np.arange(T + 1, dtype=float)
    dif = lambda s: s[None, :] - s[:, None]
    n = dif(idx)
    with np.errstate(divide="ignore", invalid="ignore"):
        st, sy = dif(s_t), dif(s_y)
        xx = dif(s_tt) - st ** 2 / n
        xy = dif(s_ty) - st * sy / n
        yy = dif(s_yy) - sy ** 2 / n
        ssr = yy - xy ** 2 / xx
    ssr[n < 3] = np.inf
    return np.where(np.isnan(ssr), np.inf, np.maximum(ssr, 0.0))


def dp_brueche(S, T, m_max, h):
    """Global optimale Brueche fuer m = 0..m_max (Segmentlaenge >= h). {m: (SSR, [Indizes])}."""
    aus = {0: (float(S[0, T]), [])}
    opt = np.full(T + 1, np.inf)
    opt[h:] = S[0, h:]
    zurueck = []
    for m in range(1, m_max + 1):
        neu = np.full(T + 1, np.inf)
        arg = np.zeros(T + 1, dtype=int)
        for j in range((m + 1) * h, T + 1):
            kand_i = np.arange(m * h, j - h + 1)
            wert = opt[kand_i] + S[kand_i, j]
            b = int(np.argmin(wert))
            neu[j], arg[j] = wert[b], kand_i[b]
        zurueck.append(arg)
        opt = neu
        if not np.isfinite(opt[T]):
            break
        pos, brueche = T, []
        for r in range(m - 1, -1, -1):
            pos = int(zurueck[r][pos])
            brueche.insert(0, pos)
        aus[m] = (float(opt[T]), brueche)
    return aus


def segment_fit(y, brueche):
    T = len(y)
    fit = np.zeros(T)
    grenzen = [0] + list(brueche) + [T]
    for a, b in zip(grenzen[:-1], grenzen[1:]):
        t = np.arange(a, b, dtype=float)
        fit[a:b] = np.polyval(np.polyfit(t, y[a:b], 1), t)
    return fit


def mehrfachbrueche(y, monate, m_max, B, rng):
    y = np.asarray(y, float)
    T = len(y)
    h = max(math.ceil(TRIMMUNG * T), 3)
    S = ssr_segmente(y)
    opt = dp_brueche(S, T, m_max, h)
    zeilen = []
    for m in sorted(opt):
        ssr, br = opt[m]
        n_par = 2 * (m + 1) + m
        zeile = {"m": m, "brueche": [int(monate[i]) for i in br], "ssr": ssr,
                 "bic": T * np.log(max(ssr, 1e-12) / T) + n_par * np.log(T),
                 "f_von_vorher": None, "p_von_vorher": None}
        if m >= 1:
            f_stat = lambda s0, s1, k: ((s0 - s1) / 2) / (s1 / (T - 2 * (k + 1) - k))
            ssr0, br0 = opt[m - 1]
            f = f_stat(ssr0, ssr, m)
            fit = segment_fit(y, br0)
            phi, eps = ar_anpassen(y - fit)
            sim = fit[:, None] + simuliere_ar(phi, eps, T, B, rng)
            f_b = np.empty(B)
            for b in range(B):
                d = dp_brueche(ssr_segmente(sim[:, b]), T, m, h)
                f_b[b] = f_stat(d[m - 1][0], d[m][0], m) if m in d else np.nan
            f_b = f_b[np.isfinite(f_b)]
            zeile["f_von_vorher"] = float(f)
            zeile["p_von_vorher"] = float((1 + np.sum(f_b >= f)) / (len(f_b) + 1))
        zeilen.append(zeile)
    return zeilen


# ---------------------------------------------------------
# Schritt 2: Event Study
# ---------------------------------------------------------

def baue_es_panel(videos, kan, erstes, var, funnel=None):
    k0, k1 = var["fenster_start"], QUARTALS_FENSTER[1]
    stichtag = monat_start(3 * k0)
    k = kanal_ids_je_basis(kan, erstes, var["basis"], var["ohne_top"], stichtag)
    v = videos[videos["channel_id"].isin(k["channel_id"])]
    v = v.assign(k=v["monat"] // 3)
    v = v[v["k"].between(k0, k1)]
    zellen = v.groupby(["channel_id", "k"])["views"].agg(views="sum", n="size").reset_index()
    k = k[k["channel_id"].isin(zellen["channel_id"])]
    if var["basis"] == "balanciert":
        start = pd.Series(k0, index=k["channel_id"])
    else:
        erst_m = relativ_periode(erstes.reindex(k["channel_id"]), pd.Timestamp(KRIEGSBEGINN), 1)
        start = (erst_m // 3).clip(lower=k0)
    gitter = pd.DataFrame([(c, q) for c, s in start.items() for q in range(int(s), k1 + 1)],
                          columns=["channel_id", "k"])
    p = gitter.merge(zellen, on=["channel_id", "k"], how="left")
    p[["views", "n"]] = p[["views", "n"]].fillna(0)
    p["ln_views"] = np.log1p(p["views"])
    p["ln_uploads"] = np.log1p(p["n"])
    p["ln_views_pro_video"] = np.where(p["n"] > 0, np.log1p(p["views"] / p["n"].where(p["n"] > 0)), np.nan)
    if funnel is not None:
        funnel["Kanal-Quartale"] = len(p)
        funnel["davon ohne Upload"] = int((p["n"] == 0).sum())
    if var["leere_bins"] == "fehlend":
        p.loc[p["n"] == 0, ["ln_views", "ln_uploads"]] = np.nan
    return p.merge(k[["channel_id", "channel_title", "gruppe"]], on="channel_id")


def schaetze_es(panel, outcome, k0, k1, rng):
    d = panel.dropna(subset=[outcome])
    d = d[d.groupby("channel_id")["k"].transform("size") >= 2].reset_index(drop=True)
    alt = alt_gruppe()
    n_kan = d.groupby("gruppe")["channel_id"].nunique().to_dict()
    if n_kan.get(alt, 0) < MIN_KANAELE_GRUPPE or n_kan.get(REFERENZ_GRUPPE, 0) < MIN_KANAELE_GRUPPE:
        raise SystemExit(f"Zu wenige Kanaele je Gruppe: {n_kan} (Minimum {MIN_KANAELE_GRUPPE})")
    bins = [k for k in range(k0, k1 + 1) if k != REFERENZ_QUARTAL]
    kk = d["k"].to_numpy()
    ist_alt = (d["gruppe"] == alt).to_numpy(float)
    spalten = {f"l|{k}": (kk == k).astype(float) for k in bins}
    spalten.update({f"d|{k}": (kk == k) * ist_alt for k in bins})
    X = pd.DataFrame(spalten)
    y = d[outcome].to_numpy(float)
    code, kanaele = pd.factorize(d["channel_id"])
    G = len(kanaele)
    # Within-Transformation fuer die Kanal-FE
    Xw = (X - X.groupby(code).transform("mean")).to_numpy(float)
    yw = y - pd.Series(y).groupby(code).transform("mean").to_numpy()
    behalten = np.abs(Xw).sum(axis=0) > 1e-10
    namen = X.columns[behalten].tolist()
    Xw = Xw[:, behalten]
    if np.linalg.matrix_rank(Xw) < Xw.shape[1]:
        raise SystemExit(f"Event Study ({outcome}): Design ist nicht voll spaltenrangig")
    N, K = Xw.shape
    A = np.linalg.inv(Xw.T @ Xw)
    beta = A @ (Xw.T @ yw)
    e = yw - Xw @ beta
    S = np.zeros((G, K))
    np.add.at(S, code, Xw * e[:, None])
    cf = G / (G - 1) * (N - 1) / (N - K - 1)
    V = cf * A @ (S.T @ S) @ A
    XgXg = np.zeros((G, K, K))
    for g in range(G):
        Xg = Xw[code == g]
        XgXg[g] = Xg.T @ Xg
    return {"namen": namen, "beta": beta, "V": V, "A": A, "S": S, "XgXg": XgXg, "cf": cf, "G": G,
            "n_obs": N, "n_kan": n_kan, "bins": list(range(k0, k1 + 1)), "rng": rng}


def kontrast(res, gewichte, mit_wild=True):
    """Linearkombination der Parameter mit CR1-SE und optional Wild-Cluster-p; Referenzbin = 0."""
    c = np.zeros(len(res["namen"]))
    for n, w in gewichte.items():
        if n.endswith(f"|{REFERENZ_QUARTAL}"):
            continue
        if n not in res["namen"]:
            return {"est": np.nan, "se": np.nan, "p": np.nan, "p_wild": np.nan}
        c[res["namen"].index(n)] = w
    if not c.any():
        return {"est": 0.0, "se": 0.0, "p": np.nan, "p_wild": np.nan}
    est = float(c @ res["beta"])
    se = float(np.sqrt(max(c @ res["V"] @ c, 0.0)))
    p = 2 * stats.t.sf(abs(est / se), res["G"] - 1) if se > 0 else np.nan
    p_wild = wild_p(res, c, est / se if se > 0 else np.nan) if mit_wild else np.nan
    return {"est": est, "se": se, "p": float(p), "p_wild": p_wild}


def wild_p(res, c, t_hat):
    """Wild-Cluster-Bootstrap (unrestricted, Webb) fuer die t-Statistik von c'beta."""
    if not np.isfinite(t_hat):
        return np.nan
    webb = np.array([-np.sqrt(1.5), -1.0, -np.sqrt(0.5), np.sqrt(0.5), 1.0, np.sqrt(1.5)])
    W = res["rng"].choice(webb, size=(WILD_B, res["G"]))
    S, A = res["S"], res["A"]
    v = A @ c
    a_g = S @ v
    C_g = np.einsum("gkl,l->gk", res["XgXg"], v)
    delta = W @ S @ A
    innen = W * a_g - delta @ C_g.T
    se_b = np.sqrt(res["cf"] * (innen ** 2).sum(axis=1))
    with np.errstate(divide="ignore", invalid="ignore"):
        t_b = (delta @ c) / se_b
    t_b = t_b[np.isfinite(t_b)]
    return float((1 + np.sum(np.abs(t_b) >= abs(t_hat))) / (len(t_b) + 1))


def wald(res, zeilen):
    """F-Test H0: alle Kombinationen = 0, df2 = Kanaele - 1 (bei wenigen Clustern eher zu liberal)."""
    R = []
    for gw in zeilen:
        r = np.zeros(len(res["namen"]))
        for n, w in gw.items():
            if n in res["namen"]:
                r[res["namen"].index(n)] = w
        if r.any():
            R.append(r)
    if not R:
        return {"F": np.nan, "p": np.nan, "q": 0}
    R = np.array(R)
    rb = R @ res["beta"]
    q = len(R)
    F = float(rb @ np.linalg.pinv(R @ res["V"] @ R.T) @ rb) / q
    return {"F": F, "p": float(stats.f.sf(F, q, res["G"] - 1)), "q": q}


def es_kennzahlen(res):
    zeilen = []
    for k in res["bins"]:
        ref = kontrast(res, {f"l|{k}": 1.0}, mit_wild=False)
        dd = kontrast(res, {f"d|{k}": 1.0})
        alt = kontrast(res, {f"l|{k}": 1.0, f"d|{k}": 1.0}, mit_wild=False)
        zeilen.append({"k": k, "verlauf_ref": ref["est"], "verlauf_ref_se": ref["se"],
                       "verlauf_alt": alt["est"], "verlauf_alt_se": alt["se"],
                       "differenz": dd["est"], "differenz_se": dd["se"],
                       "p": dd["p"], "p_wild": dd["p_wild"]})
    tab = pd.DataFrame(zeilen)
    vor = [k for k in res["bins"] if k < REFERENZ_QUARTAL]
    kurz = [k for k in vor if KURZER_VORTREND[0] <= k <= KURZER_VORTREND[1]]
    pre = [k for k in res["bins"] if k <= REFERENZ_QUARTAL]
    mitte = np.mean(pre)
    nenner = sum((k - mitte) ** 2 for k in pre)
    zus = {"vortrend_alle": wald(res, [{f"d|{k}": 1.0} for k in vor]),
           "vortrend_kurz": wald(res, [{f"d|{k}": 1.0} for k in kurz]),
           "vortrend_linear": kontrast(res, {f"d|{k}": (k - mitte) / nenner for k in pre}),
           "bloecke": {}}
    for name, (a, b) in POST_BLOECKE.items():
        ks = [k for k in res["bins"] if a <= k <= b]
        zus["bloecke"][name] = kontrast(res, {f"d|{k}": 1.0 / len(ks) for k in ks}) if ks else None
    return tab, zus


# ---------------------------------------------------------
# Grafiken
# ---------------------------------------------------------

TINTE, GRAU, GITTER = "#1f1e1c", "#8a8883", "#e5e4e0"


def achsen_stil(ax):
    ax.grid(axis="y", color=GITTER, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)


def kontext_linien(ax, einheit_tage, beschriften=True):
    """Kriegsbeginn (Grenze vor Periode 0) und Kontextereignisse in Einheiten der x-Achse."""
    krieg = pd.Timestamp(KRIEGSBEGINN)
    links, rechts = ax.get_xlim()
    ax.axvline(-0.5, color=TINTE, linestyle="--", linewidth=1, zorder=1)
    if beschriften:
        ax.text(-0.5, 1.0, " Kriegsbeginn", transform=ax.get_xaxis_transform(), rotation=90,
                va="top", ha="left", fontsize=7, color=TINTE)
    for lab, d in KONTEXT.items():
        x = (pd.Timestamp(d) - krieg).days / einheit_tage - 0.5
        if links <= x <= rechts:
            ax.axvline(x, color=GRAU, linestyle=":", linewidth=1, zorder=1)
            if beschriften:
                ax.text(x, 1.0, " " + lab, transform=ax.get_xaxis_transform(), rotation=90,
                        va="top", ha="left", fontsize=7, color=GRAU)


def plot_bruch(reihen, tests, outcome, pfad):
    """D_t mit Anpassung (oben), F-Profil (unten); Modell Niveau und Trend."""
    namen = [s for s in BRUCH_SAMPLES if s in tests]
    if not namen:
        return
    fig, axes = plt.subplots(2, len(namen), figsize=(4.6 * len(namen), 7), sharex=True, squeeze=False)
    for j, s in enumerate(namen):
        d = reihen[s].dropna(subset=[outcome])
        r = tests[s]["niveau_und_trend"]
        oben, unten = axes[0][j], axes[1][j]
        oben.plot(d["monat"], d[outcome], color=GRAU, linewidth=1, marker="o", markersize=2.5)
        oben.plot(d["monat"], r["koef_tau"]["fit"], color=TINTE, linewidth=2)
        if r["koef_krieg"] is not None:
            oben.plot(d["monat"], r["koef_krieg"]["fit"], color=TINTE, linewidth=1.3, linestyle="--")
        oben.set_title(f"{s}\ngeschätzter Bruch: Monat {r['tau']} ({monat_start(r['tau']):%m/%Y})",
                       fontsize=9, loc="left")
        unten.plot(r["profil_monate"] - 0.5, r["profil_f"], color=TINTE, linewidth=2)
        unten.axhline(r["krit5_ar"], color=GRAU, linewidth=1, linestyle="-")
        # Der RW-Wert ist oft um ein Vielfaches groesser und wuerde das Profil flachdruecken;
        # liegt er ausserhalb des Bereichs, steht er als Text in der Grafik.
        oben_grenze = 1.25 * max(r["sup_f"], r["krit5_ar"])
        if r["krit5_rw"] <= oben_grenze:
            unten.axhline(r["krit5_rw"], color=GRAU, linewidth=1, linestyle="--")
        else:
            unten.text(0.98, 0.95, f"5-%-Wert Random Walk: {r['krit5_rw']:.0f}", transform=unten.transAxes,
                       ha="right", va="top", fontsize=8, color="#52514e")
        unten.set_ylim(0, oben_grenze)
        unten.set_xlabel("Monat relativ zum Kriegsbeginn")
        for ax in (oben, unten):
            achsen_stil(ax)
        kontext_linien(oben, 30.4375, beschriften=j == 0)
        kontext_linien(unten, 30.4375, beschriften=False)
    axes[0][0].set_ylabel(f"D_t: {BRUCH_OUTCOMES[outcome]}, {alt_gruppe()} − {REFERENZ_GRUPPE}")
    axes[1][0].set_ylabel("F(τ), Modell Niveau und Trend")
    griffe = [Line2D([], [], color=GRAU, marker="o", markersize=3, linewidth=1, label="D_t (Monatswerte)"),
              Line2D([], [], color=TINTE, linewidth=2, label="Anpassung, geschätzter Bruch / F-Profil"),
              Line2D([], [], color=TINTE, linewidth=1.3, linestyle="--", label="Anpassung, Bruch bei Kriegsbeginn"),
              Line2D([], [], color=GRAU, linewidth=1, label="5-%-Wert Sup-F, H0: AR um Trend"),
              Line2D([], [], color=GRAU, linewidth=1, linestyle="--", label="5-%-Wert Sup-F, H0: Random Walk")]
    fig.legend(handles=griffe, loc="lower center", ncol=3, fontsize=8, frameon=False)
    fig.suptitle(f"Strukturbruch im Abstand {alt_gruppe()} − {REFERENZ_GRUPPE}: {BRUCH_OUTCOMES[outcome]}",
                 fontsize=11, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.07, 1, 0.96))
    fig.savefig(pfad, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_es(tab, res, outcome, variante, pfad):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.2), sharex=True)
    alt, ref = alt_gruppe(), REFERENZ_GRUPPE
    for g, sp, vers in [(ref, "verlauf_ref", -0.1), (alt, "verlauf_alt", 0.1)]:
        x = tab["k"] + vers
        axes[0].plot(x, tab[sp], color=FARBEN[g], linewidth=2, marker=MARKER[g], markersize=5,
                     markeredgecolor="white", markeredgewidth=0.6, zorder=3)
        axes[0].vlines(x, tab[sp] - 1.96 * tab[sp + "_se"], tab[sp] + 1.96 * tab[sp + "_se"],
                       color=FARBEN[g], linewidth=1, alpha=0.5, zorder=2)
    axes[1].plot(tab["k"], tab["differenz"], color=TINTE, linewidth=2, marker="o", markersize=5,
                 markeredgecolor="white", markeredgewidth=0.6, zorder=3)
    axes[1].fill_between(tab["k"], tab["differenz"] - 1.96 * tab["differenz_se"],
                         tab["differenz"] + 1.96 * tab["differenz_se"], color=GRAU, alpha=0.25,
                         linewidth=0, zorder=2)
    titel = [f"Verlauf je Gruppe relativ zu k = {REFERENZ_QUARTAL}", f"Differenz d_k: {alt} − {ref}"]
    for ax, t in zip(axes, titel):
        ax.axhline(0, color=TINTE, linewidth=0.8)
        achsen_stil(ax)
        ax.set_title(t, fontsize=10, loc="left")
        ax.set_xlabel("Quartal relativ zum Kriegsbeginn (Quartal 0 = 24.02.–23.05.2022)")
        kontext_linien(ax, 91.3125)
    axes[0].set_ylabel(f"Δ {ES_OUTCOMES[outcome]}")
    griffe = [Line2D([], [], color=FARBEN[g], marker=MARKER[g], linewidth=2,
                     label=f"{g} (n = {res['n_kan'].get(g, 0)})") for g in (ref, alt)]
    griffe.append(Line2D([], [], color=TINTE, marker="o", linewidth=2, label="Differenz (Band: 95-%-KI, CR1)"))
    fig.legend(handles=griffe, loc="lower center", ncol=3, fontsize=8, frameon=False)
    fig.suptitle(f"Event Study Kriegsbeginn: {ES_OUTCOMES[outcome]}, Variante {variante} "
                 f"({res['G']} Kanäle, {res['n_obs']} Kanal-Quartale)", fontsize=11, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    fig.savefig(pfad, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_es_vergleich(koef, outcome, pfad):
    d = koef[koef["outcome"] == outcome]
    fig, ax = plt.subplots(figsize=(11, 5.4))
    linien = ["--", ":", "-.", (0, (5, 1, 1, 1)), (0, (1, 2))]
    grau = [TINTE, "#52514e", "#6b6a66", GRAU, "#a8a6a1"]
    weitere = [v for v in ES_VARIANTEN if v != "balanciert" and v in set(d["variante"])]
    for i, v in enumerate(weitere):
        t = d[d["variante"] == v].sort_values("k")
        ax.plot(t["k"], t["differenz"], color=grau[i % 5], linestyle=linien[i % 5], linewidth=1.2, label=v)
    t = d[d["variante"] == "balanciert"].sort_values("k")
    if len(t):
        ax.plot(t["k"], t["differenz"], color=FARBEN[alt_gruppe()], linewidth=2.4, marker="o",
                markersize=4, label="balanciert", zorder=4)
    ax.axhline(0, color=TINTE, linewidth=0.8)
    achsen_stil(ax)
    ax.set_xlabel("Quartal relativ zum Kriegsbeginn")
    ax.set_ylabel(f"d_k: {ES_OUTCOMES[outcome]}, {alt_gruppe()} − {REFERENZ_GRUPPE}")
    ax.set_title("Event Study: Differenz je Variante", fontsize=11, loc="left")
    kontext_linien(ax, 91.3125)
    ax.legend(fontsize=8, frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    fig.savefig(pfad, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------
# Markdown
# ---------------------------------------------------------

def sterne(p):
    if p is None or not np.isfinite(p):
        return ""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""


def zahl(x, nachkomma=3):
    return "–" if x is None or not np.isfinite(x) else f"{x:.{nachkomma}f}"


def koef_zelle(est, se):
    if est is None or not np.isfinite(est):
        return "–"
    z = abs(est / se) if se else np.nan
    p = 2 * stats.norm.sf(z) if np.isfinite(z) else np.nan
    return f"{est:.3f}{sterne(p)} ({se:.3f})"


def monat_lab(m):
    return f"{m} ({monat_start(m):%m/%Y})"


def menge_text(menge):
    if not menge:
        return "leer"
    teile, a, b = [], menge[0], menge[0]
    for m in menge[1:]:
        if m == b + 1:
            b = m
        else:
            teile.append((a, b))
            a = b = m
    teile.append((a, b))
    return ", ".join(f"{x}" if x == y else f"{x} bis {y}" for x, y in teile)


def md_einzelbruch(tests):
    z = ["| Stichprobe | Modell | Monate | Bruch τ̂ | Sup-F | 5 % AR / RW | p AR | p RW | "
         "Konfidenzmenge τ | Monat 0 darin | F bei Monat 0 | p AR | p RW | AR(p), Σφ |",
         "|" + "---|" * 14]
    for s, je in tests.items():
        for m, r in je.items():
            z.append(f"| {s} | {BRUCH_MODELLE[m]} | {r['T']} | {monat_lab(r['tau'])} | {r['sup_f']:.2f} | "
                     f"{r['krit5_ar']:.2f} / {r['krit5_rw']:.2f} | {r['p_ar']:.3f} | {r['p_rw']:.3f} | "
                     f"{menge_text(r['menge'])} | {'ja' if 0 in r['menge'] else 'nein'} | "
                     f"{zahl(r['f_krieg'], 2)} | {zahl(r['p_krieg_ar'])} | {zahl(r['p_krieg_rw'])} | "
                     f"{r['ar_ordnung']}, {r['ar_summe']:.2f} |")
    return z


def md_koef(tests):
    z = ["| Stichprobe | Modell | Datum | Vortrend je Jahr | Niveausprung δ | Trendänderung θ je Jahr |",
         "|---|---|---|---|---|---|"]
    for s, je in tests.items():
        for m, r in je.items():
            for lab, k in [(f"Kriegsbeginn (Monat 0)", r["koef_krieg"]), (f"τ̂ = {r['tau']}", r["koef_tau"])]:
                if k is None:
                    continue
                th = None if k["theta"] is None else 12 * k["theta"]
                th_se = None if k["theta_se"] is None else 12 * k["theta_se"]
                z.append(f"| {s} | {BRUCH_MODELLE[m]} | {lab} | {koef_zelle(12 * k['vortrend'], 12 * k['vortrend_se'])} | "
                         f"{koef_zelle(k['delta'], k['delta_se'])} | {koef_zelle(th, th_se)} |")
    return z


def md_methodik(funnel_kan, funnel_vid):
    a, b = MONATS_FENSTER
    return [
        "# Strukturbruch und Event Study: Alternative rechts vs. ÖRR", "",
        f"Erzeugt: {dt.datetime.now():%d.%m.%Y %H:%M} von `src/youtube_code/step6_auswertung/strukturbruch_rohdaten.py`.", "",
        "## Lesehilfe", "",
        "- **Gibt es überhaupt einen Bruch?** Sup-F mit p AR und p RW. Klein unter beiden: klarer Befund. Klein nur unter "
        "AR: Der Befund hängt davon ab, dass die Reihe trendstationär ist; bei hoher Persistenz (Σφ nahe 1) kann er ein "
        "Artefakt sein. p RW ist sehr streng und übersieht auch echte Brüche, ein großes p RW widerlegt also keinen Bruch.",
        "- **Passt der Kriegsbeginn als Datum?** „Monat 0 darin“ zeigt, ob der Kriegsbeginn in der Konfidenzmenge liegt. "
        "F bei Monat 0 testet das vorab festgelegte Datum ohne Suche. Die Konfidenzmenge sagt nur etwas aus, wenn Sup-F signifikant ist.",
        "- **Ein oder mehrere Brüche?** Abschnitt Mehrfachbrüche. Ein Bruch im Vorkriegs-Placebo spricht dafür, dass "
        "die Reihe auch ohne Krieg instabil ist.",
        "- **Summen oder typischer Kanal?** Schritt 1 nutzt Gruppensummen (große Kanäle dominieren), Schritt 2 gewichtet "
        "jeden Kanal gleich. Weichen sie ab, tragen wenige Kanäle den Effekt.", "",
        "## Methodik", "",
        f"**Sample:** `media_category` {MEDIA_CATEGORIES}, `sample` ∈ {SAMPLE_CODES}, `foreign` ≠ 1, `format` = {FORMAT}, "
        f"Videos ohne Views verworfen. Funnel Kanäle: {funnel_kan}. Funnel Videos: {funnel_vid}.", "",
        f"**Schritt 1:** D_t = ln(Summe {alt_gruppe()}) − ln(Summe {REFERENZ_GRUPPE}), Monate {a} bis {b}, Trimmung {TRIMMUNG}. "
        f"Einzelbruch-Bootstrap B = {BOOTSTRAP_B}, Mehrfachbrüche B = {BOOTSTRAP_B_MEHRFACH}, Seed {SEED}. Monat τ ist der erste Monat "
        "nach dem Bruch. Modelle und Tests siehe Docstring. Koeffizienten mit Newey-West-SE; Sterne dort aus der Normalverteilung.", "",
        f"**Schritt 2:** y_ck = a_c + l_k + Σ_j d_j · Alt_c · 1[k = j] + e_ck, Referenz k = {REFERENZ_QUARTAL}, SE nach Kanal geclustert (CR1). "
        f"Wild-Cluster-Bootstrap B = {WILD_B}, Webb-Gewichte, unrestricted. Bei wenigen ÖRR-Kanälen ist p (wild) "
        "maßgeblich; p (CR1) ist dann meist zu klein. Der gemeinsame Vortrend-F-Test nutzt die CR1-Kovarianz.", "",
        "## Grenzen", "",
        "- *Keine kausale Aussage:* Alle Kanäle sind gleichzeitig betroffen, Energiekrise, Inflation, AfD-Aufstieg und "
        "Plattformänderungen fallen in denselben Zeitraum. Der ÖRR ist selbst vom Krieg betroffen und kann Publikum abgeben.",
        "- *Datierung:* Ein Bruch Monate nach Kriegsbeginn ist kein Beleg für einen Kriegseffekt, auch wenn er signifikant ist.",
        "- *Wenige Referenzkanäle:* Der ÖRR hat im Sample nur rund 16 Kanäle, im balancierten Panel weniger.",
        "- *Views-Snapshot:* Kumulierte Views zum Abrufzeitpunkt; ältere Videos hatten mehr Zeit. Das kürzt sich nur heraus, "
        "wenn beide Gruppen ähnlich altern.",
        "- *Überleben:* Gelöschte Videos und Kanäle (z. B. KenFM, RT DE) fehlen. Das drückt die frühen Werte der Alternativen "
        "und kann einen Aufwärtstrend vortäuschen. Auch die Auswahl der Kanäle kann vom späteren Erfolg abhängen.",
        "- *Format:* `long` ist kein Längenmaß, und beide Gruppen laden Unterschiedliches hoch (siehe `docs/projektueberblick.md`).",
        "- *Gruppen:* direkt aus `media_category`, daher nicht zwingend identisch mit den Gruppen der Grafik.", "",
    ]


def md_es(kennz):
    z = ["| Variante | Outcome | Kanäle Alt/ÖRR | Vortrend alle k ≤ −2: F (df), p | "
         f"Vortrend k = {KURZER_VORTREND[0]}..{KURZER_VORTREND[1]}: F (df), p | Linearer Vortrend je Quartal (p wild) | "
         + " | ".join(f"{n} (p wild)" for n in POST_BLOECKE) + " |",
         "|" + "---|" * (6 + len(POST_BLOECKE))]
    alt = alt_gruppe()
    for (v, o), (tab, zus, res) in kennz.items():
        va, vk, vl = zus["vortrend_alle"], zus["vortrend_kurz"], zus["vortrend_linear"]
        bl = []
        for n in POST_BLOECKE:
            b = zus["bloecke"][n]
            bl.append("–" if b is None else f"{zahl(b['est'])}{sterne(b['p_wild'])} ({zahl(b['se'])}; p = {zahl(b['p_wild'])})")
        z.append(f"| {v} | {o} | {res['n_kan'].get(alt, 0)}/{res['n_kan'].get(REFERENZ_GRUPPE, 0)} | "
                 f"{zahl(va['F'], 2)} ({va['q']}), {zahl(va['p'])} | {zahl(vk['F'], 2)} ({vk['q']}), {zahl(vk['p'])} | "
                 f"{zahl(vl['est'])} (p = {zahl(vl['p_wild'])}) | " + " | ".join(bl) + " |")
    return z


def md_es_koef(tab):
    z = ["| k | Beginn | ÖRR-Verlauf | Alt-Verlauf | d_k (SE) | p CR1 | p wild |", "|---|---|---|---|---|---|---|"]
    for _, r in tab.iterrows():
        k = int(r["k"])
        if k == REFERENZ_QUARTAL:
            z.append(f"| {k} | {monat_start(3 * k):%d.%m.%Y} | 0 (Ref.) | 0 (Ref.) | 0 (Ref.) | – | – |")
            continue
        z.append(f"| {k} | {monat_start(3 * k):%d.%m.%Y} | {zahl(r['verlauf_ref'])} | {zahl(r['verlauf_alt'])} | "
                 f"{zahl(r['differenz'])}{sterne(r['p_wild'])} ({zahl(r['differenz_se'])}) | {zahl(r['p'])} | {zahl(r['p_wild'])} |")
    return z


# ---------------------------------------------------------
# main
# ---------------------------------------------------------

def bruch_zeile(s, o, r, fenster):
    return {"stichprobe": s, "outcome": o, "fenster": fenster, "modell": r["modell"], "T": r["T"], "tau": r["tau"],
            "sup_f": r["sup_f"], "krit5_ar": r["krit5_ar"], "krit5_rw": r["krit5_rw"], "p_ar": r["p_ar"], "p_rw": r["p_rw"],
            "f_krieg": r["f_krieg"], "p_krieg_ar": r["p_krieg_ar"], "p_krieg_rw": r["p_krieg_rw"],
            "konfidenzmenge": menge_text(r["menge"]), "monat0_in_menge": 0 in r["menge"],
            "ar_ordnung": r["ar_ordnung"], "ar_summe": r["ar_summe"]}


def main():
    pruefe_config()
    PFAD_OUT.mkdir(parents=True, exist_ok=True)
    PFAD_REG.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    funnel_kan, funnel_vid = {}, {}
    kan = lade_kanaele(funnel_kan)
    print(f"Lade videos_roh.dta ({len(kan)} Kanäle) ...")
    videos = lade_videos(set(kan["channel_id"]), funnel_vid)
    erstes = videos.groupby("channel_id")["upload_ts"].min()
    print(f"  {len(videos)} Videos")

    # --- Schritt 1 ---
    stichtag = monat_start(MONATS_FENSTER[0])
    reihen, n_kanaele, alle_zeilen = {}, {}, []
    for s, cfg in BRUCH_SAMPLES.items():
        k = kanal_ids_je_basis(kan, erstes, cfg["basis"], cfg["ohne_top"], stichtag)
        n_kanaele[s] = k["gruppe"].value_counts().to_dict()
        reihen[s] = monatsreihen(videos, k, MONATS_FENSTER)
    pd.concat([d.assign(stichprobe=s) for s, d in reihen.items()]).to_csv(
        PFAD_OUT / "monatsreihen.csv", index=False, encoding="utf-8-sig")

    tests_je_outcome, placebo, mehrfach = {}, {}, {}
    for o in BRUCH_OUTCOMES:
        tests_je_outcome[o] = {}
        for s, d in reihen.items():
            if d[o].isna().any():
                print(f"  [Hinweis] {s}/{o}: {int(d[o].isna().sum())} Monate ohne Wert, Test entfällt")
                continue
            je = {}
            for m in BRUCH_MODELLE:
                je[m] = bruchtest(d[o].to_numpy(), d["monat"].to_numpy(), m, BOOTSTRAP_B, rng)
                alle_zeilen.append(bruch_zeile(s, o, je[m], "gesamt"))
            tests_je_outcome[o][s] = je
            print(f"  Bruchtest {o:20s} {s:20s} τ̂ = {je['niveau_und_trend']['tau']:4d}, "
                  f"p AR = {je['niveau_und_trend']['p_ar']:.3f}, p RW = {je['niveau_und_trend']['p_rw']:.3f}")
        plot_bruch(reihen, tests_je_outcome[o], o, PFAD_OUT / f"bruch_{o}.png")

    for s, d in reihen.items():
        x = d[d["monat"].between(*PLACEBO_FENSTER)]
        if x[MEHRFACH_OUTCOME].isna().any():
            print(f"  [Hinweis] Placebo {s}: Monate ohne Wert, entfällt")
            continue
        placebo[s] = {m: bruchtest(x[MEHRFACH_OUTCOME].to_numpy(), x["monat"].to_numpy(), m, BOOTSTRAP_B, rng)
                      for m in BRUCH_MODELLE}
        alle_zeilen += [bruch_zeile(s, MEHRFACH_OUTCOME, r, "placebo") for r in placebo[s].values()]
        if not d[MEHRFACH_OUTCOME].isna().any():
            mehrfach[s] = mehrfachbrueche(d[MEHRFACH_OUTCOME].to_numpy(), d["monat"].to_numpy(),
                                          MAX_BRUECHE, BOOTSTRAP_B_MEHRFACH, rng)
            print(f"  Mehrfachbrüche {s}: fertig")
    pd.DataFrame(alle_zeilen).to_csv(PFAD_OUT / "bruchtests.csv", index=False, encoding="utf-8-sig")

    # --- Schritt 2 ---
    kennz, koef, funnel_es = {}, [], {}
    for v, cfg in ES_VARIANTEN.items():
        f = {}
        panel = baue_es_panel(videos, kan, erstes, cfg, f)
        funnel_es[v] = f
        for o in ES_OUTCOMES:
            if cfg["leere_bins"] == "null" and o == "ln_views_pro_video":
                continue   # Views je Video ist in leeren Bins nicht definiert, identisch zu "balanciert"
            res = schaetze_es(panel, o, cfg["fenster_start"], QUARTALS_FENSTER[1], rng)
            tab, zus = es_kennzahlen(res)
            kennz[(v, o)] = (tab, zus, res)
            koef.append(tab.assign(variante=v, outcome=o))
            plot_es(tab, res, o, v, PFAD_OUT / f"es_{o}_{v}.png")
            print(f"  Event Study {v:22s} {o:20s} Kanäle {res['n_kan']}, Obs {res['n_obs']}")
    koef = pd.concat(koef, ignore_index=True)
    koef.to_csv(PFAD_OUT / "es_koeffizienten.csv", index=False, encoding="utf-8-sig")
    for o in ES_OUTCOMES:
        plot_es_vergleich(koef, o, PFAD_OUT / f"es_vergleich_{o}.png")

    # --- Bericht ---
    z = md_methodik(funnel_kan, funnel_vid)
    z += ["## Kanäle je Stichprobe in Schritt 1", "", "| Stichprobe | " + " | ".join(MEDIA_CATEGORIES.values()) + " |",
          "|" + "---|" * (len(MEDIA_CATEGORIES) + 1)]
    z += [f"| {s} | " + " | ".join(str(n.get(g, 0)) for g in MEDIA_CATEGORIES.values()) + " |" for s, n in n_kanaele.items()]
    z += ["", "## Schritt 1: Einzelbruchtests", ""]
    for o, lab in BRUCH_OUTCOMES.items():
        z += [f"### {lab}", "", f"Grafik: `bruch_{o}.png`", ""] + md_einzelbruch(tests_je_outcome[o]) + [""]
        z += ["**Koeffizienten** (Newey-West-SE in Klammern):", ""] + md_koef(tests_je_outcome[o]) + [""]
    z += [f"## Schritt 1: Mehrfachbrüche ({BRUCH_OUTCOMES[MEHRFACH_OUTCOME]})", "",
          "Je Segment eigener Achsenabschnitt und Trend. F(m | m−1) testet m gegen m−1 Brüche, p aus dem Bootstrap "
          "unter dem Modell mit m−1 Brüchen. Niedriger BIC ist besser.", "",
          "| Stichprobe | Brüche m | Bruchmonate | SSR | BIC | F(m, m−1) | p |", "|---|---|---|---|---|---|---|"]
    for s, zeilen in mehrfach.items():
        for r in zeilen:
            z.append(f"| {s} | {r['m']} | {', '.join(monat_lab(x) for x in r['brueche']) or '–'} | {r['ssr']:.3f} | "
                     f"{r['bic']:.1f} | {zahl(r['f_von_vorher'], 2)} | {zahl(r['p_von_vorher'])} |")
    z += ["", f"## Schritt 1: Placebo nur Vorkriegsmonate {PLACEBO_FENSTER} ({BRUCH_OUTCOMES[MEHRFACH_OUTCOME]})", ""]
    z += md_einzelbruch(placebo) + [""]
    z += [f"## Schritt 2: Event Study, Quartale bis {QUARTALS_FENSTER[1]}", "",
          "Blöcke = Mittel von d_k (SE), Sterne aus p wild. Die Vergleichsgrafiken heißen `es_vergleich_<outcome>.png`.", ""]
    z += md_es(kennz) + ["", "**Kanal-Quartale je Variante:**", ""]
    z += [f"- {v}: {f}" for v, f in funnel_es.items()]
    z += ["", "### Koeffizienten je Variante und Outcome", ""]
    for (v, o), (tab, _, res) in kennz.items():
        z += [f"#### {v}, {ES_OUTCOMES[o]}", "", f"{res['G']} Kanäle ({res['n_kan']}), {res['n_obs']} Kanal-Quartale. "
              f"Grafik: `es_{o}_{v}.png`", ""] + md_es_koef(tab) + [""]
    (PFAD_REG / "strukturbruch_ergebnisse.md").write_text("\n".join(z), encoding="utf-8")
    print(f"Fertig: {PFAD_OUT}")


if __name__ == "__main__":
    main()

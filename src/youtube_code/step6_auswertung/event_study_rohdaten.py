# -*- coding: utf-8 -*-
"""
event_study_rohdaten.py

Event Study zum Kanalerfolg (Forschungsfrage 2) um frei waehlbare Ereignisdaten
auf Basis des zentralen Analysedatensatzes outputs/stata_rohdaten/
(videos_roh.dta, kanaele_roh.dta; Codebuch docs/codebuch_rohdatensatz.md) und der
manuellen Medienklassifikation in outputs/stata_rohdaten/channels_check.xlsx.

Sample (wie KANALLISTE in marktanteil_rohdaten_plots.py)
--------------------------------------------------------
- media_category in channels_check.xlsx: 1 = ÖRR, 5 = Alternative rechts
  (MEDIA_CATEGORIES; 2 = Traditionelle ist seit 04.11.2026 abgeschaltet, weil sie
  von wenigen Kanaelen mit wechselnder Strategie getragen werden und deshalb als
  Vergleichsgruppe wenig taugen); Gruppe direkt aus media_category, NICHT aus
  medientyp/Ideologie-Baseline in kanaele_roh. Vergleich: Alternative rechts vs. ÖRR.
- Unterkategorie = Spalte "sample" in channels_check.xlsx (aufgeteilt werden nur die
  Medientypen in UNTERKAT_AUFTEILEN, Default nur Alternative rechts; der ÖRR bleibt
  als Referenz gepoolt, weil seine Unterkategorien nur 3-7 Kanaele haben) (1 = News, 2 =
  Recherche/Doku, 3 = Regional, 4 = Clips, 5 = Doku unpolitisch, 0 = ohne
  Zuordnung). Hauptsample: sample in [1, 2, 3]; andere Codes nur als
  Robustheitsvarianten (VARIANTEN).
- foreign == 1 (auslaendische Kanaele) faellt raus.
- Nur Videos mit format == "long" (keine Shorts/Livestreams/ohne Format).

Ereigniszeit
------------
BIN_MODUS waehlt die Aggregation; je Modus legt MODI die geschaetzten Ereignisse,
das Fenster (k_min, k_max), das Fenster von "fenster_kurz", die POST_BLOECKE und
den Ausgabeordner fest (Uploads ausserhalb des Fensters fallen weg):
- "tage": Bin k = floor((Upload-Tag - Ereignistag) / BIN_TAGE), also k = 0 =
  [Ereignis, Ereignis + 30 Tage), k = -1 = die 30 Tage davor (Referenz).
  Default: 24.02./14.06./31.08.2022, Fenster -6..12, Ordner event_study_rohdaten.
- "quartal": Bin k = [Ereignis + 3k Monate, Ereignis + 3(k+1) Monate), d. h.
  Quartale aus drei Kalendermonaten, die am Ereignistag beginnen (pd.DateOffset
  jeweils vom Ereignistag aus; Monatsende gekuerzt, 31.08. -> 30.11. -> 28.02.).
  Default: 24.02. und 31.08.2022, Fenster -4..3 (je 4 Quartale vor/nach),
  Post-Bloecke 0 und 1..3, Ordner event_study_rohdaten_quartal.

Panel und Outcomes (Kanal c x Bin k)
-----------------------------------
- ln_views            = ln(Views-Summe der im Bin hochgeladenen Videos + 1)
- ln_uploads          = ln(Anzahl Uploads + 1)
- ln_views_pro_video  = ln(Views-Summe / Uploads + 1), nur Bins mit Upload
Views sind kumuliert zum Abrufzeitpunkt (rohe Views, keine Alters-Normierung).
Bins ohne Upload (leere_bins): "fehlend" (Haupt) = gehen bei allen Outcomes nicht
ein, die Schaetzung misst also die intensive Marge aktiver Kanal-Bins; "null"
(Robustheit) = ln_views/ln_uploads = ln(0 + 1) = 0. "null" ist anfaellig: ein
einzelner Kanal, der einige Bins pausiert (z. B. NDR Info), erzeugt Spruenge von
rund -12 Log-Punkten und dominiert kleine Gruppen. Panel "balanciert": nur Kanaele mit erstem langen Video vor
Fensterbeginn, alle Bins k_min..k_max. "unbalanciert": alle Kanaele mit Upload im
Fenster, Bins ab dem Bin des ersten langen Videos. Kanaele ohne einen einzigen
Upload im Fenster tragen nichts bei und fallen raus.

Modell
------
Je Ebene (Medientyp bzw. Medientyp x Unterkategorie) ein voll interagiertes Modell

    y_ck = a_c + sum_g sum_{j != -1} b_gj * 1[g(c) = g] * 1[k = j] + e_ck

mit Kanal-FE a_c, SE geclustert nach Kanal (linearmodels.PanelOLS). b_gj ist der
Verlauf der Gruppe g relativ zu ihrem eigenen Bin -1 ("Verlauf je Gruppe"; enthaelt
Saison- und Alterseffekte der Views, die alle Gruppen treffen). Die eigentliche
Event-Study-Schaetzung ist die Differenz zur Referenzgruppe r

    d_gj = b_gj - b_rj,

was exakt dem Modell mit Ereigniszeit-FE (y = a_c + l_k + sum_{g != r} d_gj D_gj)
entspricht; gemeinsame Schocks und der Views-Alterseffekt kuerzen sich heraus.
Ausgewiesen werden: Vortrend-Test (H0: d_gj = 0 fuer alle j <= -2, Wald-F),
Mittel von d_gj ueber POST_BLOECKE (z. B. 0-2 und 3-12) mit SE.
Gewichtung "wurzel" (Robustheit): Kanalgewicht sqrt(mittlere Views je Bin im
Vorfenster + 1), zwischen "jeder Kanal gleich" und gepoolten Views.

Ausgabe nach OUTPUTS / "segment_analysis" / MODI[BIN_MODUS]["ordner"]
---------------------------------------------------------------------
- es_<ereignis>_<ebene>_<outcome>_<variante>.png: links Verlauf je Gruppe, rechts
  Differenz zur Referenzgruppe, jeweils 95-%-KI; gestrichelt = Ereignis, gepunktet =
  die anderen Ereignisse und KONTEXT_EREIGNISSE im Fenster. Hauptvariante: alle
  Outcomes und Ebenen; Robustheitsvarianten: nur HAUPT_OUTCOME, beide Ebenen.
- es_robustheit_<ereignis>_<ebene>.png: Differenz zur Referenz (HAUPT_OUTCOME) je
  Variante fuer jede Nicht-Referenzgruppe.
- event_study_koeffizienten.csv: alle b_gj und d_gj (Long-Format).
- regression_results/event_study_ergebnisse.md: Methodik, Modellgleichung,
  Kanal-Funnel je Variante/Ereignis, Zusammenfassung und Koeffiziententabellen der
  Hauptvariante.
- regression_results/event_study_robustheit.md: Kennzahlen (Post-Mittel,
  Vortrend-p) aller Varianten nebeneinander.

Ausfuehren aus dem Repo-Root:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.event_study_rohdaten
"""

import datetime as dt

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from linearmodels.panel import PanelOLS
from scipy import stats

from youtube_code.config import OUTPUTS, STATA_OUTPUT


# =========================================================
# CONFIG
# =========================================================

ROHDATEN_PFAD = STATA_OUTPUT                      # videos_roh.dta, kanaele_roh.dta
CHANNELS_CHECK = STATA_OUTPUT / "channels_check.xlsx"

# Alle bekannten Ereignisse: Schluessel (Dateiname, nur a-z0-9_) -> (Datum ISO, Label).
# Welche davon geschaetzt werden, legt der Bin-Modus fest (MODI[...]["ereignisse"]);
# die uebrigen erscheinen nur als gepunktete Linie in den Grafiken.
EREIGNISSE_ALLE = {
    "e20220224": ("2022-02-24", "24.02.2022 (Kriegsbeginn)"),
    "e20220614": ("2022-06-14", "14.06.2022"),
    "e20220831": ("2022-08-31", "31.08.2022"),
}
# Weitere Daten, die nur als gepunktete Linie in die Grafiken kommen (kein Modell)
KONTEXT_EREIGNISSE = {"BTW 2021": "2021-09-26"}

# Bin-Modus: "tage" = Bins zu BIN_TAGE Tagen ab Ereignistag (erster Lauf, 30-Tage-Bins)
#            "quartal" = Quartale zu 3 Kalendermonaten, die am Ereignistag beginnen
#            (Grenzen = Ereignistag + 3k Monate, z. B. 24.02./24.05./24.08./24.11.;
#            bei Monatsende auf den letzten Tag gekuerzt: 31.08. -> 30.11. -> 28.02.)
BIN_MODUS = "quartal"
BIN_TAGE = 30            # nur Modus "tage": Breite eines Bins in Tagen, ganze Zahl >= 7
# Je Modus: geschaetzte Ereignisse (Schluessel aus EREIGNISSE_ALLE), Fenster (k_min <= -2,
# k_max >= 0), Fenster der Robustheitsvariante "fenster_kurz", Post-Bloecke (inklusive
# Grenzen, >= 0) und Ausgabeordner unter OUTPUTS / "segment_analysis"
MODI = {
    "tage": {"ereignisse": ["e20220224", "e20220614", "e20220831"],
             "fenster": (-6, 12), "fenster_kurz": (-3, 6),
             "post_bloecke": {"kurz (0 bis 2)": (0, 2), "mittel (3 bis 12)": (3, 12)},
             "ordner": "event_study_rohdaten"},
    "quartal": {"ereignisse": ["e20220224", "e20220831"],
                "fenster": (-4, 3), "fenster_kurz": (-2, 1),
                "post_bloecke": {"kurz (0)": (0, 0), "mittel (1 bis 3)": (1, 3)},
                "ordner": "event_study_rohdaten_quartal"},
}
REFERENZ_BIN = -1        # normierter Bin, muss im Fenster liegen und < 0 sein
FORMAT = "long"          # "long" (Hauptdefinition) | "alle" (long, short, live)

# --- abgeleitet aus BIN_MODUS (nicht aendern; Pruefung in pruefe_config) ---
_MODUS = MODI.get(BIN_MODUS, MODI["tage"])
EREIGNISSE = {k: EREIGNISSE_ALLE[k] for k in _MODUS["ereignisse"] if k in EREIGNISSE_ALLE}
FENSTER = _MODUS["fenster"]
POST_BLOECKE = _MODUS["post_bloecke"]
PFAD_OUT = OUTPUTS / "segment_analysis" / _MODUS["ordner"]
PFAD_REG = PFAD_OUT / "regression_results"
BIN_NAME = f"{BIN_TAGE}-Tage-Bin" if BIN_MODUS == "tage" else "Quartal"

# media_category in channels_check.xlsx -> Medientyp (Reihenfolge = Farb-/Legendenreihenfolge)
# (2: "Traditionelle" waere moeglich, ist aber als Vergleichsgruppe ungeeignet, s. Docstring)
MEDIA_CATEGORIES = {1: "ÖRR", 5: "Alternative rechts"}
# Spalte "sample" in channels_check.xlsx -> Unterkategorie
SAMPLE_LABELS = {0: "ohne Zuordnung", 1: "News", 2: "Recherche/Doku", 3: "Regional",
                 4: "Clips", 5: "Doku unpolitisch"}

# Referenzgruppen der Differenzschaetzung, je Ebene ein Gruppenname
# (Gruppenname der Ebene; ein Medientyp ausserhalb UNTERKAT_AUFTEILEN heisst auf
# beiden Ebenen wie der Medientyp, z. B. "ÖRR")
REFERENZ = {"medientyp": "ÖRR", "unterkategorie": "ÖRR"}
# Medientypen, die auf der Ebene "unterkategorie" nach sample-Code aufgeteilt werden
# (Werte aus MEDIA_CATEGORIES); die uebrigen bleiben gepoolt
UNTERKAT_AUFTEILEN = ["Alternative rechts"]
# Gruppen mit weniger Kanaelen im Panel werden nicht geschaetzt (>= 2)
MIN_KANAELE_GRUPPE = 3

OUTCOMES = {
    "ln_views": "ln(Views-Summe + 1)",
    "ln_uploads": "ln(Uploads + 1)",
    "ln_views_pro_video": "ln(Views je Video + 1)",
}
HAUPT_OUTCOME = "ln_views"   # muss in OUTCOMES sein

# Varianten: "haupt" ist das Hauptsample, alle anderen sind Robustheitslaeufe mit
# genau einer Aenderung. Schluessel je Variante:
#   sample_codes: Liste aus SAMPLE_LABELS
#   panel: "balanciert" | "unbalanciert"
#   gewichtung: "gleich" | "wurzel"
#   ausschliessen: Liste von channel_title (exakt, Gross-/Kleinschreibung egal)
#   fenster: (k_min, k_max) oder None = FENSTER
#   leere_bins: "fehlend" (Bins ohne Upload fallen raus) | "null" (ln(0 + 1) = 0)
BASIS = {"sample_codes": [1, 2, 3], "panel": "balanciert", "gewichtung": "gleich",
         "ausschliessen": [], "fenster": None, "leere_bins": "fehlend"}
VARIANTEN = {
    "haupt": {},
    "sample_1234": {"sample_codes": [1, 2, 3, 4]},
    "sample_1235": {"sample_codes": [1, 2, 3, 5]},
    "sample_alle": {"sample_codes": [0, 1, 2, 3, 4, 5]},
    "unbalanciert": {"panel": "unbalanciert"},
    "gewichtet_wurzel": {"gewichtung": "wurzel"},
    "ohne_top_alt": {"ausschliessen": ["Vermietertagebuch - Alexander Raue",
                                       "Erfolgskanal - Community für Finanzen & Wirtschaft",
                                       "Kettner-Edelmetalle (Gold & Silber)",
                                       "Achtung, Reichelt!"]},
    "fenster_kurz": {"fenster": _MODUS["fenster_kurz"]},
    "leere_bins_null": {"leere_bins": "null"},
}
EBENEN = ["medientyp", "unterkategorie"]

# Farben: Medientyp wie in marktanteil_rohdaten_plots (ÖRR blau, Traditionelle
# orange, Alternative rechts pink); Unterkategorien = Farbe des Medientyps plus
# Marker/Linienstil als zweite Kodierung.
FARBEN = {"ÖRR": "#2a78d6", "Traditionelle": "#eb6834", "Alternative rechts": "#e87ba4"}
MARKER = {"News": "o", "Recherche/Doku": "s", "Regional": "^", "Clips": "D",
          "Doku unpolitisch": "v", "ohne Zuordnung": "X"}
LINIE = {"News": "-", "Recherche/Doku": "--", "Regional": ":", "Clips": "-.",
         "Doku unpolitisch": (0, (5, 1, 1, 1)), "ohne Zuordnung": (0, (1, 2))}

# =========================================================


def pruefe_config():
    fehler = []
    if BIN_MODUS not in MODI:
        fehler.append(f"BIN_MODUS muss einer von {list(MODI)} sein")
    for mk, m in MODI.items():
        unbekannt = [k for k in m["ereignisse"] if k not in EREIGNISSE_ALLE]
        if unbekannt or not m["ereignisse"]:
            fehler.append(f"MODI['{mk}']['ereignisse']: unbekannt oder leer {unbekannt}")
        if any(a < 0 or b < a for a, b in m["post_bloecke"].values()):
            fehler.append(f"MODI['{mk}']['post_bloecke']: Grenzen muessen 0 <= a <= b sein")
    if not isinstance(BIN_TAGE, int) or BIN_TAGE < 7:
        fehler.append("BIN_TAGE muss ganze Zahl >= 7 sein")
    for name, var in VARIANTEN.items():
        cfg = {**BASIS, **var}
        k0, k1 = cfg["fenster"] or FENSTER
        if not (k0 <= -2 and k1 >= 0 and k0 <= REFERENZ_BIN < 0):
            fehler.append(f"Fenster {k0, k1} der Variante {name} ungueltig (k_min <= -2, k_max >= 0, Referenzbin darin)")
        if cfg["panel"] not in ("balanciert", "unbalanciert"):
            fehler.append(f"{name}: panel muss balanciert/unbalanciert sein")
        if cfg["leere_bins"] not in ("fehlend", "null"):
            fehler.append(f"{name}: leere_bins muss fehlend/null sein")
        if cfg["gewichtung"] not in ("gleich", "wurzel"):
            fehler.append(f"{name}: gewichtung muss gleich/wurzel sein")
        if not set(cfg["sample_codes"]) <= set(SAMPLE_LABELS):
            fehler.append(f"{name}: unbekannte sample_codes {cfg['sample_codes']}")
    if "haupt" not in VARIANTEN:
        fehler.append("VARIANTEN braucht 'haupt'")
    if HAUPT_OUTCOME not in OUTCOMES:
        fehler.append("HAUPT_OUTCOME nicht in OUTCOMES")
    if FORMAT not in ("long", "alle"):
        fehler.append("FORMAT muss 'long' oder 'alle' sein")
    if set(REFERENZ) != set(EBENEN):
        fehler.append("REFERENZ braucht genau die Ebenen aus EBENEN")
    if not set(UNTERKAT_AUFTEILEN) <= set(MEDIA_CATEGORIES.values()):
        fehler.append("UNTERKAT_AUFTEILEN enthaelt unbekannte Medientypen")
    if REFERENZ.get("medientyp") not in MEDIA_CATEGORIES.values():
        fehler.append("REFERENZ['medientyp'] muss ein Wert aus MEDIA_CATEGORIES sein")
    ref_u = REFERENZ.get("unterkategorie", "")
    if ref_u.split(" · ")[0] not in MEDIA_CATEGORIES.values() or             ((" · " in ref_u) != (ref_u.split(" · ")[0] in UNTERKAT_AUFTEILEN)):
        fehler.append("REFERENZ['unterkategorie'] passt nicht zu UNTERKAT_AUFTEILEN "
                      "(aufgeteilte Medientypen als 'Typ · Unterkategorie', sonst nur 'Typ')")
    for key, (datum, _) in EREIGNISSE_ALLE.items():
        try:
            dt.date.fromisoformat(datum)
        except ValueError:
            fehler.append(f"Ereignis {key}: Datum {datum} nicht ISO")
    if MIN_KANAELE_GRUPPE < 2:
        fehler.append("MIN_KANAELE_GRUPPE muss >= 2 sein")
    if fehler:
        raise SystemExit("Konfigurationsfehler:\n  - " + "\n  - ".join(fehler))


# ---------------------------------------------------------
# Daten
# ---------------------------------------------------------

def lade_kanaele():
    check = pd.read_excel(CHANNELS_CHECK, sheet_name=0,
                          usecols=["channel_id", "channel_title", "media_category", "sample", "foreign"])
    if check["channel_id"].duplicated().any():
        raise SystemExit("channels_check.xlsx: channel_id mehrfach vorhanden")
    kan = pd.read_stata(ROHDATEN_PFAD / "kanaele_roh.dta",
                        columns=["channel_id", "kanal_name", "medientyp", "sample_vorkrieg"])
    k = check.merge(kan, on="channel_id", how="left", indicator=True)
    k["in_kanaele_roh"] = k["_merge"] == "both"
    k = k.drop(columns="_merge")
    k["medientyp_check"] = k["media_category"].map(MEDIA_CATEGORIES)
    k["unterkat"] = k["sample"].map(SAMPLE_LABELS)
    k["auslaendisch"] = k["foreign"] == 1
    return k


def lade_videos(kanal_ids):
    v = pd.read_stata(ROHDATEN_PFAD / "videos_roh.dta",
                      columns=["channel_id", "upload_ts", "views", "format"])
    v = v[v["channel_id"].isin(kanal_ids)]
    if FORMAT == "long":
        v = v[v["format"] == "long"]
    else:
        v = v[v["format"].isin(["long", "short", "live"])]
    v = v.copy()
    v["tag"] = v["upload_ts"].dt.normalize()
    return v


# ---------------------------------------------------------
# Ereigniszeit-Bins
# ---------------------------------------------------------

_K_GITTER = np.arange(-400, 401)   # deckt in beiden Modi weit mehr als den Datenzeitraum ab
_GRENZEN_CACHE = {}


def bin_start(e, k):
    """Erster Tag von Bin k relativ zum Ereignistag e (je Modus)."""
    e = pd.Timestamp(e)
    if BIN_MODUS == "tage":
        return e + pd.Timedelta(days=int(k) * BIN_TAGE)
    return e + pd.DateOffset(months=3 * int(k))   # jeweils vom Ereignistag aus, kein Aufsummieren


def bin_grenzen(e):
    e = pd.Timestamp(e)
    if e not in _GRENZEN_CACHE:
        _GRENZEN_CACHE[e] = pd.DatetimeIndex([bin_start(e, k) for k in _K_GITTER])
    return _GRENZEN_CACHE[e]


def bin_von(tage, e):
    """Bin-Index k (int-Array) fuer Tage (Series/Index von Timestamps)."""
    pos = bin_grenzen(e).searchsorted(pd.DatetimeIndex(tage), side="right") - 1
    if (pos < 0).any() or (pos >= len(_K_GITTER) - 1).any():
        raise SystemExit("Datum ausserhalb des Bin-Gitters")
    return _K_GITTER[pos]


def bin_position(datum, e):
    """Kontinuierliche Lage eines Datums in Bin-Einheiten (k + Anteil am Bin)."""
    d = pd.Timestamp(datum)
    k = int(bin_von(pd.DatetimeIndex([d]), e)[0])
    a, b = bin_start(e, k), bin_start(e, k + 1)
    return k + (d - a).days / (b - a).days


# ---------------------------------------------------------
# Panel
# ---------------------------------------------------------

def baue_panel(videos, kanaele, ereignis_datum, cfg, funnel):
    """Kanal x Bin-Panel fuer ein Ereignis und eine Variante."""
    k0, k1 = cfg["fenster"] or FENSTER
    e = pd.Timestamp(ereignis_datum)
    fenster_start = bin_start(e, k0)

    kan = kanaele.copy()
    f = {"channels_check: media_category in MEDIA_CATEGORIES": len(kan)}
    kan = kan[kan["sample"].isin(cfg["sample_codes"])]
    f[f"sample in {cfg['sample_codes']}"] = len(kan)
    kan = kan[~kan["auslaendisch"]]
    f["ohne foreign == 1"] = len(kan)
    kan = kan[kan["in_kanaele_roh"]]
    f["in kanaele_roh"] = len(kan)
    if cfg["ausschliessen"]:
        titel = {t.strip().lower() for t in cfg["ausschliessen"]}
        kan = kan[~kan["channel_title"].str.strip().str.lower().isin(titel)]
        f["ohne ausgeschlossene Kanaele"] = len(kan)

    vid = videos[videos["channel_id"].isin(kan["channel_id"])].copy()
    erstes = vid.groupby("channel_id")["tag"].min()
    kan = kan[kan["channel_id"].isin(erstes.index)]
    f[f"mit >= 1 Video (Format {FORMAT}) ab 2019"] = len(kan)

    vid["k"] = bin_von(vid["tag"], e).astype(int)
    vid = vid[(vid["k"] >= k0) & (vid["k"] <= k1)]
    zellen = (vid.groupby(["channel_id", "k"])
                 .agg(n=("views", "size"), views=("views", lambda s: s.fillna(0).sum()),
                      views_fehlt=("views", lambda s: s.isna().sum()))
                 .reset_index())

    if cfg["panel"] == "balanciert":
        kan = kan[kan["channel_id"].map(erstes) < fenster_start]
        f["balanciert: erstes Video vor Fensterbeginn"] = len(kan)
        start_k = pd.Series(k0, index=kan["channel_id"])
    else:
        erst_k = pd.Series(bin_von(erstes, e), index=erstes.index).clip(lower=k0)
        start_k = erst_k.reindex(kan["channel_id"])
    aktiv = set(zellen["channel_id"])
    kan = kan[kan["channel_id"].isin(aktiv)]
    f["mit >= 1 Upload im Fenster"] = len(kan)
    start_k = start_k.reindex(kan["channel_id"])
    start_k = start_k[start_k <= k1]

    gitter = pd.DataFrame([(c, k) for c, s in start_k.items() for k in range(int(s), k1 + 1)],
                          columns=["channel_id", "k"])
    p = gitter.merge(zellen, on=["channel_id", "k"], how="left")
    p[["n", "views", "views_fehlt"]] = p[["n", "views", "views_fehlt"]].fillna(0)
    p["ln_views"] = np.log1p(p["views"])
    p["ln_uploads"] = np.log1p(p["n"])
    p["ln_views_pro_video"] = np.where(p["n"] > 0, np.log1p(p["views"] / p["n"].where(p["n"] > 0)), np.nan)
    leer = p["n"] == 0
    f["Kanal-Bins gesamt"] = len(p)
    f["davon ohne Upload"] = int(leer.sum())
    if cfg["leere_bins"] == "fehlend":
        p.loc[leer, ["ln_views", "ln_uploads"]] = np.nan
    p = p.merge(kan[["channel_id", "channel_title", "medientyp_check", "unterkat"]], on="channel_id")
    p["g_medientyp"] = p["medientyp_check"]
    p["g_unterkategorie"] = np.where(p["medientyp_check"].isin(UNTERKAT_AUFTEILEN),
                                     p["medientyp_check"] + " · " + p["unterkat"], p["medientyp_check"])

    # Gewicht je Kanal
    vor = p[p["k"] < 0].groupby("channel_id")["views"].mean()
    p["gewicht"] = np.sqrt(p["channel_id"].map(vor) + 1) if cfg["gewichtung"] == "wurzel" else 1.0
    if cfg["gewichtung"] == "wurzel":
        ohne = p["gewicht"].isna()
        if ohne.any():
            f["wurzel-Gewicht: ohne Vorfenster-Bin entfernt"] = -p.loc[ohne, "channel_id"].nunique()
        p = p[~ohne]
    funnel.update(f)
    return p


# ---------------------------------------------------------
# Schaetzung
# ---------------------------------------------------------

def schaetze(panel, ebene, outcome, k0, k1):
    gcol = f"g_{ebene}"
    d = panel.dropna(subset=[outcome]).copy()
    n_kan = d.groupby(gcol)["channel_id"].nunique()
    gruppen = [g for g in sortierte_gruppen(n_kan.index, ebene) if n_kan[g] >= MIN_KANAELE_GRUPPE]
    weg = {g: int(n_kan[g]) for g in n_kan.index if g not in gruppen}
    d = d[d[gcol].isin(gruppen)]
    bins = [k for k in range(k0, k1 + 1) if k != REFERENZ_BIN]
    idx = pd.MultiIndex.from_arrays([d["channel_id"], d["k"]])
    kk = d["k"].to_numpy()
    spalten = {}
    for g in gruppen:
        ig = (d[gcol] == g).to_numpy()
        for k in bins:
            spalten[f"{g}|{k}"] = (ig & (kk == k)).astype(float)
    Xi = pd.DataFrame(spalten, index=idx)
    Xi = Xi.loc[:, Xi.sum() > 0]
    y = pd.Series(d[outcome].to_numpy(), index=idx)
    w = pd.Series(d["gewicht"].to_numpy(), index=idx)
    # Hinweis: drop_absorbed=True/check_rank=False liefert hier falsche Niveaus (getestet), daher Defaults
    mod = PanelOLS(y, Xi, entity_effects=True, weights=w)
    res = mod.fit(cov_type="clustered", cluster_entity=True)
    return {"params": res.params, "cov": res.cov, "gruppen": gruppen, "weg": weg,
            "n_obs": int(res.nobs), "n_kanaele": int(d["channel_id"].nunique()),
            "n_kan_gruppe": {g: int(n_kan[g]) for g in gruppen},
            "n_cluster": int(d["channel_id"].nunique()), "bins": list(range(k0, k1 + 1))}


def sortierte_gruppen(gruppen, ebene):
    mt = list(MEDIA_CATEGORIES.values())
    uk = list(SAMPLE_LABELS.values())
    uk = [uk[i] for i in [1, 2, 3, 4, 5, 0]]
    if ebene == "medientyp":
        return [g for g in mt if g in gruppen]
    return sorted(gruppen, key=lambda g: (mt.index(g.split(" · ")[0]),
                                          uk.index(g.split(" · ")[1]) if " · " in g else -1))


def linkomb(res, gewichte):
    """Schaetzer und SE fuer sum w_i * param_i; fehlende Parameter (Referenzbin) = 0."""
    p, V = res["params"], res["cov"]
    namen = []
    for n in gewichte:
        if n.endswith(f"|{REFERENZ_BIN}"):
            continue          # normierter Bin = 0
        if n not in p.index:
            return np.nan, np.nan   # Bin ohne Beobachtung
        namen.append(n)
    if not namen:
        return 0.0, 0.0
    w = np.array([gewichte[n] for n in namen])
    est = float(w @ p[namen].to_numpy())
    var = float(w @ V.loc[namen, namen].to_numpy() @ w)
    return est, np.sqrt(max(var, 0.0))


def wald(res, zeilen):
    """F-Test H0: alle Linearkombinationen in zeilen = 0 (Liste von dicts)."""
    p, V = res["params"], res["cov"]
    namen = list(p.index)
    R = []
    for z in zeilen:
        if any(n not in namen and not n.endswith(f"|{REFERENZ_BIN}") for n in z):
            continue
        r = np.zeros(len(namen))
        for n, w in z.items():
            if n in namen:
                r[namen.index(n)] = w
        if r.any():
            R.append(r)
    if not R:
        return np.nan, np.nan, 0
    R = np.array(R)
    rb = R @ p.to_numpy()
    RVR = R @ V.to_numpy() @ R.T
    try:
        W = float(rb @ np.linalg.pinv(RVR) @ rb)
    except np.linalg.LinAlgError:
        return np.nan, np.nan, len(R)
    q = len(R)
    F = W / q
    pval = 1 - stats.f.cdf(F, q, res["n_cluster"] - 1)
    return F, pval, q


def kennzahlen(res, ebene):
    """Verlauf b_gk, Differenz d_gk, Vortrend-Test und Post-Mittel."""
    ref = REFERENZ[ebene]
    zeilen, zusammen = [], []
    for g in res["gruppen"]:
        for k in res["bins"]:
            b, bse = linkomb(res, {f"{g}|{k}": 1.0})
            if ref in res["gruppen"]:
                dd, dse = linkomb(res, {f"{g}|{k}": 1.0, f"{ref}|{k}": -1.0}) if g != ref else (np.nan, np.nan)
            else:
                dd, dse = np.nan, np.nan
            zeilen.append({"gruppe": g, "k": k, "verlauf": b, "verlauf_se": bse,
                           "differenz": dd, "differenz_se": dse})
        if g == ref or ref not in res["gruppen"]:
            continue
        pre = [{f"{g}|{k}": 1.0, f"{ref}|{k}": -1.0} for k in res["bins"] if k < REFERENZ_BIN]
        F, pv, q = wald(res, pre)
        z = {"gruppe": g, "vortrend_F": F, "vortrend_p": pv, "vortrend_df": q}
        for name, (a, bb) in POST_BLOECKE.items():
            ks = [k for k in res["bins"] if a <= k <= bb]
            if not ks:
                z[name] = (np.nan, np.nan)
                continue
            gw = {}
            for k in ks:
                gw[f"{g}|{k}"] = 1.0 / len(ks)
                gw[f"{ref}|{k}"] = -1.0 / len(ks)
            z[name] = linkomb(res, gw)
            z[name + " Bins"] = f"{min(ks)}–{max(ks)}"
        zusammen.append(z)
    return pd.DataFrame(zeilen), zusammen


# ---------------------------------------------------------
# Grafiken
# ---------------------------------------------------------

def stil(g, ebene):
    mt = g.split(" · ")[0]
    if ebene == "medientyp" or " · " not in g:
        return FARBEN[mt], "o", "-"
    uk = g.split(" · ")[1]
    return FARBEN[mt], MARKER[uk], LINIE[uk]


def vlinien(ax, ereignis_key, k0, k1):
    e = pd.Timestamp(EREIGNISSE[ereignis_key][0])
    ax.axvline(-0.5, color="#52514e", linestyle="--", linewidth=1, zorder=1)
    andere = {lab.split(" (")[0]: d for key, (d, lab) in EREIGNISSE_ALLE.items() if key != ereignis_key}
    andere.update(KONTEXT_EREIGNISSE)
    for lab, d in andere.items():
        x = bin_position(d, e) - 0.5
        if k0 - 0.5 <= x <= k1 + 0.5:
            ax.axvline(x, color="#8a8883", linestyle=":", linewidth=1.1, zorder=1)
            ax.text(x, 1.0, " " + lab, transform=ax.get_xaxis_transform(), rotation=90,
                    va="top", ha="left", fontsize=7, color="#8a8883")


def plot_event(tab, res, ebene, outcome, ereignis_key, variante, pfad):
    k0, k1 = res["bins"][0], res["bins"][-1]
    gruppen = res["gruppen"]
    ref = REFERENZ[ebene]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.2), sharex=True)
    versatz = np.linspace(-0.22, 0.22, len(gruppen)) if len(gruppen) > 1 else [0]
    for ax, spalte, titel in [(axes[0], "verlauf", "Verlauf je Gruppe (relativ zu k = −1)"),
                              (axes[1], "differenz", f"Differenz zur Referenz „{ref}“")]:
        for i, g in enumerate(gruppen):
            if spalte == "differenz" and g == ref:
                continue
            t = tab[tab["gruppe"] == g].sort_values("k")
            farbe, marker, linie = stil(g, ebene)
            x = t["k"] + versatz[i]
            yv, se = t[spalte], t[spalte + "_se"]
            ax.plot(x, yv, color=farbe, linestyle=linie, linewidth=1.6, marker=marker,
                    markersize=5, markeredgecolor="white", markeredgewidth=0.6, zorder=3)
            ax.vlines(x, yv - 1.96 * se, yv + 1.96 * se, color=farbe, linewidth=1, alpha=0.55, zorder=2)
        ax.axhline(0, color="#52514e", linewidth=0.8)
        vlinien(ax, ereignis_key, k0, k1)
        ax.set_title(titel, fontsize=10, loc="left")
        ax.grid(axis="y", color="#e5e4e0", linewidth=0.8)
        ax.set_xticks(range(k0, k1 + 1))
        ax.set_xlabel(f"Bin k ({BIN_NAME}) relativ zum Ereignis; k = 0 beginnt am Ereignistag")
        for s in ["top", "right"]:
            ax.spines[s].set_visible(False)
    axes[0].set_ylabel(f"Δ {OUTCOMES[outcome]} ggü. k = −1")
    handles = []
    for g in gruppen:
        farbe, marker, linie = stil(g, ebene)
        lab = f"{g} (n = {res['n_kan_gruppe'][g]})" + (" [Referenz]" if g == ref else "")
        handles.append(Line2D([], [], color=farbe, marker=marker, linestyle=linie, label=lab))
    fig.legend(handles=handles, loc="lower center", ncol=min(len(handles), 4), fontsize=8, frameon=False,
               bbox_to_anchor=(0.5, -0.01))
    fig.suptitle(f"Event Study {EREIGNISSE[ereignis_key][1]} – {OUTCOMES[outcome]} – "
                 f"{'Medientyp' if ebene == 'medientyp' else 'Medientyp × Unterkategorie'} – Variante {variante}",
                 fontsize=11, x=0.01, ha="left")
    fig.text(0.01, -0.06, f"Kanal-FE, 95-%-KI mit nach Kanal geclusterten SE; {res['n_kanaele']} Kanäle, "
             f"{res['n_obs']} Kanal-Bins. Gestrichelt: Ereignis; gepunktet: andere Daten. "
             f"Weggelassen (< {MIN_KANAELE_GRUPPE} Kanäle): {res['weg'] or 'keine'}",
             fontsize=7.5, color="#52514e")
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    fig.savefig(pfad, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_robustheit(koef, ereignis_key, ebene, pfad):
    d = koef[(koef["ereignis"] == ereignis_key) & (koef["ebene"] == ebene) &
             (koef["outcome"] == HAUPT_OUTCOME) & koef["differenz"].notna()]
    gruppen = [g for g in sortierte_gruppen(d["gruppe"].unique(), ebene)]
    if not gruppen:
        return
    varianten = [v for v in VARIANTEN if v in d["variante"].unique()]
    n = len(gruppen)
    fig, axes = plt.subplots(1, n, figsize=(5.2 * n, 4.6), sharey=True, squeeze=False)
    grau = plt.get_cmap("Greys")
    for ax, g in zip(axes[0], gruppen):
        for i, v in enumerate(varianten):
            t = d[(d["gruppe"] == g) & (d["variante"] == v)].sort_values("k")
            if t.empty:
                continue
            if v == "haupt":
                ax.plot(t["k"], t["differenz"], color=stil(g, ebene)[0], linewidth=2.2, marker="o",
                        markersize=4, zorder=4, label=v)
                ax.fill_between(t["k"], t["differenz"] - 1.96 * t["differenz_se"],
                                t["differenz"] + 1.96 * t["differenz_se"], color=stil(g, ebene)[0],
                                alpha=0.15, linewidth=0, zorder=2)
            else:
                ax.plot(t["k"], t["differenz"], color=grau(0.35 + 0.5 * i / max(len(varianten), 1)),
                        linewidth=1, linestyle=["-", "--", ":", "-."][i % 4], zorder=3, label=v)
        ax.axhline(0, color="#52514e", linewidth=0.8)
        ax.axvline(-0.5, color="#52514e", linestyle="--", linewidth=1)
        ax.set_title(f"{g} − {REFERENZ[ebene]}", fontsize=9, loc="left")
        ax.grid(axis="y", color="#e5e4e0", linewidth=0.8)
        ax.set_xlabel("Bin k")
        ks = sorted(d["k"].unique())
        ax.set_xticks(range(int(min(ks)), int(max(ks)) + 1, 2 if max(ks) - min(ks) > 10 else 1))
        for s in ["top", "right"]:
            ax.spines[s].set_visible(False)
    axes[0][0].set_ylabel(f"Differenz Δ {OUTCOMES[HAUPT_OUTCOME]}")
    h, l = axes[0][0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=min(len(l), 8), fontsize=8, frameon=False)
    fig.suptitle(f"Robustheit – {EREIGNISSE[ereignis_key][1]} – Differenz zur Referenz (Haupt: Band = 95-%-KI)",
                 fontsize=10, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.08, 1, 0.94))
    fig.savefig(pfad, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------
# Markdown
# ---------------------------------------------------------

def sterne(est, se):
    if not np.isfinite(est) or not np.isfinite(se) or se == 0:
        return ""
    p = 2 * (1 - stats.norm.cdf(abs(est / se)))
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""


def zelle(est, se):
    if not np.isfinite(est):
        return "–"
    return f"{est:.3f}{sterne(est, se)} ({se:.3f})"


def md_zusammenfassung(zus):
    """zus: Liste von dicts mit ereignis, ebene, outcome, variante + kennzahlen."""
    kopf = "| Ereignis | Gruppe | Kanäle (Gruppe/Ref.) | " + " | ".join(f"Post {n}" for n in POST_BLOECKE) + \
           " | Vortrend F (df) | Vortrend p |"
    trenn = "|" + "---|" * (5 + len(POST_BLOECKE))
    zeilen = [kopf, trenn]
    for z in zus:
        post = " | ".join(zelle(*z[n]) for n in POST_BLOECKE)
        zeilen.append(f"| {EREIGNISSE[z['ereignis']][1]} | {z['gruppe']} | {z['n_g']}/{z['n_ref']} | {post} | "
                      f"{z['vortrend_F']:.2f} ({z['vortrend_df']}) | {z['vortrend_p']:.3f} |")
    return "\n".join(zeilen)


def md_koeftabelle(tab, res, ebene):
    ref = REFERENZ[ebene]
    gruppen = res["gruppen"]
    spalten = [f"{g}: Verlauf" for g in gruppen] + [f"{g} − Ref." for g in gruppen if g != ref]
    zeilen = ["| k | " + " | ".join(spalten) + " |", "|" + "---|" * (len(spalten) + 1)]
    for k in res["bins"]:
        werte = []
        for g in gruppen:
            r = tab[(tab["gruppe"] == g) & (tab["k"] == k)].iloc[0]
            werte.append("0 (Ref.)" if k == REFERENZ_BIN else zelle(r["verlauf"], r["verlauf_se"]))
        for g in gruppen:
            if g == ref:
                continue
            r = tab[(tab["gruppe"] == g) & (tab["k"] == k)].iloc[0]
            werte.append("0 (Ref.)" if k == REFERENZ_BIN else zelle(r["differenz"], r["differenz_se"]))
        zeilen.append(f"| {k} | " + " | ".join(werte) + " |")
    return "\n".join(zeilen)


def bin_datum(ereignis_key, k):
    e = pd.Timestamp(EREIGNISSE[ereignis_key][0])
    a = bin_start(e, k)
    b = bin_start(e, k + 1) - pd.Timedelta(days=1)
    return f"{a:%d.%m.%Y}–{b:%d.%m.%Y}"


def md_ueberlappung():
    """Lage der jeweils anderen Daten in Bins jedes geschaetzten Ereignisses."""
    teile = []
    for key, (d, lab) in EREIGNISSE.items():
        andere = {l.split(" (")[0]: dd for kk, (dd, l) in EREIGNISSE_ALLE.items() if kk != key}
        andere.update(KONTEXT_EREIGNISSE)
        lagen = [f"{l} in k = {int(bin_von(pd.DatetimeIndex([pd.Timestamp(dd)]), d)[0])}"
                 for l, dd in andere.items()]
        teile.append(f"{lab.split(' (')[0]}: " + ", ".join(lagen))
    return "; ".join(teile)


def md_methodik(kanaele):
    k0, k1 = FENSTER
    post = "; ".join(f"{n}: Mittel der d_gk für k = {a}..{b}" for n, (a, b) in POST_BLOECKE.items())
    haupt = {**BASIS, **VARIANTEN["haupt"]}
    zeilen = [
        f"# Event Study Kanalerfolg (Rohdatensatz) – {BIN_NAME}",
        "",
        f"Erzeugt: {dt.datetime.now():%d.%m.%Y %H:%M} von `src/youtube_code/step6_auswertung/event_study_rohdaten.py`.",
        "",
        "## Methodik",
        "",
        "**Datenbasis:** `outputs/stata_rohdaten/videos_roh.dta` + `kanaele_roh.dta`, Gruppen aus der manuellen "
        "Klassifikation `channels_check.xlsx` (`media_category` " +
        ", ".join(f"{c} = {n}" for c, n in MEDIA_CATEGORIES.items()) + "; Unterkategorie = Spalte `sample`, "
        f"aufgeteilt nur für {UNTERKAT_AUFTEILEN}). Die Traditionellen (`media_category` 2) sind nicht enthalten: "
        "Sie werden von wenigen Kanälen getragen, deren Strategie wechselt, und taugen deshalb nicht als "
        "Vergleichsgruppe. Ausländische Kanäle (`foreign` = 1) sind ausgeschlossen. "
        f"Nur Videos mit `format` = {FORMAT}. Rohe kumulierte Views zum Abrufzeitpunkt.",
        "",
        f"**Hauptsample:** `sample` ∈ {haupt['sample_codes']}, Panel {haupt['panel']}, Gewichtung {haupt['gewichtung']}, "
        f"leere Bins {haupt['leere_bins']}. "
        "Das entspricht der `KANALLISTE` in `marktanteil_rohdaten_plots.py` (dort zusätzlich die Gruppen aus "
        "`kanaele_roh`; hier direkt `media_category`).",
        "",
        (f"**Ereigniszeit:** Bin k = floor((Upload-Tag − Ereignistag) / {BIN_TAGE}). k = 0 umfasst den Ereignistag und die "
         f"folgenden {BIN_TAGE - 1} Tage, k = {REFERENZ_BIN} (Referenz) die {BIN_TAGE} Tage davor. "
         if BIN_MODUS == "tage" else
         "**Ereigniszeit (Quartale):** Bin k = [Ereignistag + 3k Monate, Ereignistag + 3(k+1) Monate), d. h. "
         "Quartale aus je drei Kalendermonaten, die am Ereignistag beginnen (Monatsende wird gekürzt, z. B. 31.08. → "
         "30.11. → 28.02.; Bins sind 89–92 Tage lang). k = 0 = das erste Quartal ab Ereignistag, "
         f"k = {REFERENZ_BIN} (Referenz) = das Quartal davor. ") +
        f"Fenster k = {k0}..{k1} (Varianten können abweichen). Uploads außerhalb des Fensters gehen nicht ein.",
        "",
        "**Beobachtungseinheit:** Kanal × Bin. Outcomes: " +
        "; ".join(f"`{o}` = {l}" for o, l in OUTCOMES.items()) +
        ". Bins ohne Upload: im Hauptmodell (`leere_bins` = fehlend) fehlend bei allen Outcomes, gemessen wird "
        "also die Entwicklung aktiver Kanal-Bins (intensive Marge). Robustheit `leere_bins_null`: ln(0 + 1) = 0. "
        "Grund: Mit Nullen erzeugt ein einzelner pausierender Kanal Sprünge von ca. −12 Log-Punkten und "
        "dominiert kleine Gruppen (im ersten Lauf: NDR Info in ÖRR · Regional).",
        "",
        "**Panel:** *balanciert* = nur Kanäle, deren erstes Video (ab 2019) vor Fensterbeginn liegt, alle Bins "
        "des Fensters; *unbalanciert* = alle Kanäle, Bins ab dem Bin ihres ersten Videos. In beiden Fällen fallen "
        "Kanäle ohne Upload im Fenster raus (sie tragen bei Kanal-FE nichts bei).",
        "",
        "**Modell** (je Ebene, Ereignis, Outcome und Variante; `linearmodels.PanelOLS`):",
        "",
        "```",
        "y_ck = a_c + Σ_g Σ_{j ≠ -1} b_gj · 1[g(c) = g] · 1[k = j] + e_ck",
        "d_gj = b_gj − b_rj        (r = Referenzgruppe)",
        "```",
        "",
        "a_c = Kanal-FE; SE nach Kanal geclustert. `b_gj` (*Verlauf*) ist die Veränderung der Gruppe g gegenüber "
        "ihrem eigenen Bin −1; er enthält Saison, gemeinsame Nachrichtenlage und den Views-Alterseffekt und ist "
        "deshalb nur deskriptiv. `d_gj` (*Differenz*) ist die Event-Study-Schätzung: identisch mit dem Modell "
        "`y_ck = a_c + l_k + Σ_{g≠r} d_gj D_gj` mit Ereigniszeit-FE l_k, die gemeinsamen Schocks kürzen sich heraus. "
        f"Referenzgruppen: {', '.join(f'{e} → „{r}“' for e, r in REFERENZ.items())}.",
        "",
        f"**Tests:** Vortrend = Wald-F-Test H0: d_gj = 0 für alle j ≤ −2 (df2 = Kanäle − 1). {post} "
        "(gleich gewichtete Bins, SE per Delta-Methode aus der geclusterten Kovarianz). "
        "Sterne: * p < 0,1; ** p < 0,05; *** p < 0,01.",
        "",
        f"**Gruppen mit < {MIN_KANAELE_GRUPPE} Kanälen** werden nicht geschätzt. Bei Gruppen mit wenigen Kanälen "
        "(ÖRR- und Regional-Unterkategorien, oft 3–7 Kanäle) sind geclusterte SE unzuverlässig (zu wenige Cluster je "
        "Gruppe); diese Schätzungen sind deskriptiv zu lesen.",
        "",
        "**Wichtige Einschränkungen:**",
        "",
        "- *Überlappende Ereignisse:* 24.02., 14.06. und 31.08.2022 liegen 110 bzw. 78 Tage auseinander. Lage der "
        f"anderen Daten in der Ereigniszeit: {md_ueberlappung()}. „Vortrends“ bei den späteren Daten können also "
        "die Reaktion auf das frühere Ereignis sein; Effekte der Daten sind nicht voneinander trennbar, wenn sie "
        "gleichgerichtet sind.",
        "- *Kein Überraschungsschock bei 14.06./31.08.:* Gasdrosselung und Lieferstopp zeichneten sich ab; "
        "gleichzeitig enden Sommerpausen (Parlament, Talkshows). Gemeinsame Saison kürzt sich in d_gj nur heraus, "
        "soweit sie alle Gruppen gleich trifft.",
        "- *Ereignisdaten:* Der Plan `.claude/plans/energiekrise_alternative_wachstum.md` hatte vorab 02.09.2022 "
        "(Haupt) und 23.06.2022 (Robustheit) festgelegt; 14.06. und 31.08. weichen davon ab. Weitere Daten "
        "nachträglich hinzuzunehmen wäre Spezifikationssuche.",
        "- *Selektion:* Das Sample wurde nachträglich gezogen; im unbalancierten Panel misst die Differenz auch "
        "Markteintritte erfolgreicher Kanäle (z. B. Achtung, Reichelt!).",
        "- *Views-Alter:* Rohe kumulierte Views; jüngere Videos sind leicht unterschätzt. In d_gj kürzt sich das "
        "heraus, solange das Plateau-Verhalten in allen Gruppen gleich ist.",
        "",
        "### Ereignisse und Bins",
        "",
        "| Ereignis | Bin −1 (Referenz) | Bin 0 | Bin " + str(k1) + " |",
        "|---|---|---|---|",
    ]
    for key, (d, lab) in EREIGNISSE.items():
        zeilen.append(f"| {lab} | {bin_datum(key, REFERENZ_BIN)} | {bin_datum(key, 0)} | {bin_datum(key, k1)} |")
    zeilen += ["", "### Kanäle je Gruppe in channels_check.xlsx (ohne foreign, in kanaele_roh)", ""]
    kk = kanaele[~kanaele["auslaendisch"] & kanaele["in_kanaele_roh"]]
    ct = pd.crosstab(kk["medientyp_check"], kk["unterkat"])
    zeilen.append("| Medientyp | " + " | ".join(ct.columns) + " |")
    zeilen.append("|" + "---|" * (len(ct.columns) + 1))
    for i, r in ct.iterrows():
        zeilen.append(f"| {i} | " + " | ".join(str(x) for x in r) + " |")
    zeilen += ["", "Abgleich `media_category` (channels_check) mit `medientyp` (kanaele_roh):", ""]
    ct2 = pd.crosstab(kk["medientyp_check"], kk["medientyp"].astype(str))
    zeilen.append("| media_category | " + " | ".join(ct2.columns) + " |")
    zeilen.append("|" + "---|" * (len(ct2.columns) + 1))
    for i, r in ct2.iterrows():
        zeilen.append(f"| {i} | " + " | ".join(str(x) for x in r) + " |")
    return zeilen


def md_funnel(funnels):
    zeilen = ["", "## Kanal-Funnel je Variante und Ereignis", ""]
    for (variante, ereignis), f in funnels.items():
        zeilen.append(f"**{variante} – {EREIGNISSE[ereignis][1]}:** " +
                      " → ".join(f"{k}: {v}" for k, v in f.items()))
        zeilen.append("")
    return zeilen


# ---------------------------------------------------------
# main
# ---------------------------------------------------------

def main():
    pruefe_config()
    PFAD_OUT.mkdir(parents=True, exist_ok=True)
    PFAD_REG.mkdir(parents=True, exist_ok=True)

    kanaele = lade_kanaele()
    kanaele = kanaele[kanaele["media_category"].isin(MEDIA_CATEGORIES)]
    fehlt = kanaele[~kanaele["in_kanaele_roh"]]
    if len(fehlt):
        print(f"[Hinweis] {len(fehlt)} Kanäle aus channels_check fehlen in kanaele_roh: "
              f"{fehlt['channel_title'].tolist()[:10]}")
    for name, var in VARIANTEN.items():
        for t in var.get("ausschliessen", []):
            if t.strip().lower() not in set(kanaele["channel_title"].str.strip().str.lower()):
                raise SystemExit(f"Variante {name}: Kanaltitel '{t}' nicht in channels_check.xlsx")
    print(f"Lade videos_roh.dta ({len(kanaele)} Kandidatenkanäle) ...")
    videos = lade_videos(set(kanaele["channel_id"]))
    print(f"  {len(videos)} Videos (Format {FORMAT}), davon Views fehlend: {videos['views'].isna().sum()}")

    alle_koef, alle_zus, funnels, haupt_tabs = [], [], {}, []
    for variante, var in VARIANTEN.items():
        cfg = {**BASIS, **var}
        k0, k1 = cfg["fenster"] or FENSTER
        for ek, (datum, label) in EREIGNISSE.items():
            funnel = {}
            panel = baue_panel(videos, kanaele, datum, cfg, funnel)
            funnels[(variante, ek)] = funnel
            outcomes = list(OUTCOMES) if variante == "haupt" else [HAUPT_OUTCOME]
            for ebene in EBENEN:
                for outcome in outcomes:
                    res = schaetze(panel, ebene, outcome, k0, k1)
                    tab, zus = kennzahlen(res, ebene)
                    tab = tab.assign(variante=variante, ereignis=ek, ebene=ebene, outcome=outcome)
                    alle_koef.append(tab)
                    for z in zus:
                        z.update(variante=variante, ereignis=ek, ebene=ebene, outcome=outcome,
                                 n_g=res["n_kan_gruppe"][z["gruppe"]],
                                 n_ref=res["n_kan_gruppe"].get(REFERENZ[ebene], 0))
                        alle_zus.append(z)
                    if variante == "haupt":
                        haupt_tabs.append((ek, ebene, outcome, tab, res))
                    plot_event(tab, res, ebene, outcome, ek, variante,
                               PFAD_OUT / f"es_{ek}_{ebene}_{outcome}_{variante}.png")
                    print(f"  {variante:16s} {ek} {ebene:15s} {outcome:20s} "
                          f"Kanäle {res['n_kanaele']:4d}, Obs {res['n_obs']:5d}, weg {res['weg']}")

    koef = pd.concat(alle_koef, ignore_index=True)
    koef.to_csv(PFAD_OUT / "event_study_koeffizienten.csv", index=False, encoding="utf-8-sig")
    for ek in EREIGNISSE:
        for ebene in EBENEN:
            plot_robustheit(koef, ek, ebene, PFAD_OUT / f"es_robustheit_{ek}_{ebene}.png")

    # Hauptbericht
    zeilen = md_methodik(kanaele)
    zeilen += ["", "## Zusammenfassung Hauptvariante (Differenz zur Referenzgruppe)", ""]
    for ebene in EBENEN:
        for outcome in OUTCOMES:
            zs = [z for z in alle_zus if z["variante"] == "haupt" and z["ebene"] == ebene and z["outcome"] == outcome]
            zeilen += [f"### {ebene} – {OUTCOMES[outcome]} (Referenz: {REFERENZ[ebene]})", "", md_zusammenfassung(zs), ""]
    zeilen += ["## Koeffizienten Hauptvariante", "",
               "Verlauf = b_gk (Gruppe ggü. eigenem Bin −1), − Ref. = d_gk. Koeffizient (SE).", ""]
    for ek, ebene, outcome, tab, res in haupt_tabs:
        zeilen += [f"### {EREIGNISSE[ek][1]} – {ebene} – {OUTCOMES[outcome]}", "",
                   f"{res['n_kanaele']} Kanäle, {res['n_obs']} Kanal-Bins; Kanäle je Gruppe: "
                   f"{res['n_kan_gruppe']}; nicht geschätzt (< {MIN_KANAELE_GRUPPE} Kanäle): {res['weg'] or 'keine'}. "
                   f"Grafik: `es_{ek}_{ebene}_{outcome}_haupt.png`", "",
                   md_koeftabelle(tab, res, ebene), ""]
    zeilen += md_funnel(funnels)
    (PFAD_REG / "event_study_ergebnisse.md").write_text("\n".join(zeilen), encoding="utf-8")

    # Robustheitsbericht
    rz = [f"# Event Study – Robustheitsvarianten – {BIN_NAME}", "",
          f"Outcome {OUTCOMES[HAUPT_OUTCOME]}; je Variante genau eine Änderung gegenüber `haupt` "
          f"(Basis: {BASIS}). Methodik siehe `event_study_ergebnisse.md`.", "",
          "| Variante | Änderung |", "|---|---|"]
    for v, var in VARIANTEN.items():
        rz.append(f"| {v} | {var or 'Hauptspezifikation'} |")
    rz.append("")
    for ek in EREIGNISSE:
        for ebene in EBENEN:
            rz += [f"## {EREIGNISSE[ek][1]} – {ebene} (Referenz: {REFERENZ[ebene]})", "",
                   f"Grafik: `es_robustheit_{ek}_{ebene}.png`", ""]
            kopf = "| Gruppe | Variante | Kanäle (Gruppe/Ref.) | " + " | ".join(f"Post {n}" for n in POST_BLOECKE) + \
                   " | Vortrend p |"
            rz += [kopf, "|" + "---|" * (4 + len(POST_BLOECKE))]
            zs = [z for z in alle_zus if z["ereignis"] == ek and z["ebene"] == ebene and z["outcome"] == HAUPT_OUTCOME]
            for g in sortierte_gruppen({z["gruppe"] for z in zs}, ebene):
                for v in VARIANTEN:
                    for z in zs:
                        if z["gruppe"] == g and z["variante"] == v:
                            post = " | ".join(zelle(*z[n]) for n in POST_BLOECKE)
                            rz.append(f"| {g} | {v} | {z['n_g']}/{z['n_ref']} | {post} | {z['vortrend_p']:.3f} |")
            rz.append("")
    rz += md_funnel(funnels)
    (PFAD_REG / "event_study_robustheit.md").write_text("\n".join(rz), encoding="utf-8")
    print(f"Fertig: {PFAD_OUT}")


if __name__ == "__main__":
    main()

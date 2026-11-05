# -*- coding: utf-8 -*-
"""
marktkonzentration_rohdaten_plots.py

Marktkonzentration innerhalb der Gruppen (Kapitel D, Ergaenzung zu 8i
marktanteil_rohdaten_plots.py): Wie viele Kanaele eines Medientyps vereinen
wie viel der Views bzw. Uploads dieses Typs, und aendert sich das nach
Kriegsbeginn? Datenbasis wie 8i: outputs/stata_rohdaten/ (videos_roh.dta,
kanaele_roh.dta). Gruppen, Kanal-Samples und die Zuordnung manuell codierter
Kanaele kommen aus marktanteil_rohdaten_plots.py (bilde_gruppen(),
manuell_alt_rechts(), SAMPLES, KLASSIFIKATIONEN; dessen OERR_DOKU_CODES gelten
mit), damit die Zahlen direkt neben den Marktanteils-Grafiken lesbar sind.
Ersetzt den Konzentrationscheck aus dem veralteten 8f
(kanaluebersicht_marktanteil_bericht.py).

Population: Videos mit format in FORMAT (Default long) und views, kein
Themenfilter. Zelle = Gruppe x Phase (PHASEN, je 12 Monate). Kanaele mit
mindestens einem Upload in der Phase ("aktiv", Anzahl N); x_c = Summe der Views
bzw. Zahl der Uploads von Kanal c in der Phase, s_c = x_c / sum(x) = Anteil am
Typ:

    HHI    = sum s_c^2                     (1/N bei Gleichverteilung, 1 bei einem Kanal)
    N_eff  = 1 / HHI                       "verhaelt sich wie N_eff gleich grosse Kanaele"
    CR1/3  = Anteil des groessten bzw. der 3 groessten Kanaele (%)
    k50/80 = kleinste Zahl Kanaele, die zusammen >= 50 % bzw. 80 % haben
    Top10  = Anteil der groessten ceil(0.1 * N) Kanaele (%)
    Gini   = 2 * sum_i i * x_(i) / (N * sum x) - (N + 1) / N   (x aufsteigend sortiert)

N_eff, CR und k haengen von der Kanalzahl N ab, N_eff/N, Top10 und Gini kaum.
Kanaele ohne Upload in einer Phase zaehlen nicht mit (fuer HHI/N_eff/CR/k ohne
Wirkung; Top10 und Gini beziehen sich auf die aktiven Kanaele). Zellen mit
< MIN_KANAELE aktiven Kanaelen sind in den Tabellen mit * markiert und fehlen in
der Zeitreihengrafik.

Interpretation: gemessen wird die Konzentration im Kanal-Sample, nicht im Markt;
der "long tail" kleiner Kanaele fehlt je nach Typ unterschiedlich stark.
Belastbarer als Niveauvergleiche zwischen Typen ist die Veraenderung innerhalb
eines Typs (zwei Vorkriegsjahre als Pre-Trend-Check). Nach Kriegsbeginn neu
gestartete Kanaele senken die Konzentration mechanisch -> Sample "vorkrieg"
(gestrichelt) vergleichen. Views sind Stand zum Abruf; der Alterseffekt trifft
die Kanaele einer Phase gleichermassen und kuerzt sich in den Anteilen weitgehend.

Ausgabe nach OUTPUTS / "segment_analysis" / "plots_marktkonzentration_rohdaten"
(<zusatz> = _<format>[_manuell][_oerrdoku], wie in 8i):
- konzentrationskurven_<klassifikation>_<sample><zusatz>.png  (Spalten = Gruppen,
  Zeilen = Views / Uploads; je Phase aus KURVEN_PHASEN eine Kurve: x = Zahl der
  Kanaele, groesster zuerst (KURVE_X = "rang") bzw. Anteil der Kanaele
  ("anteil", mit Gleichverteilungs-Diagonale), y = kumulierter Anteil am Typ;
  waagrechte Linie bei 50 %)
- konzentration_zeitreihe_<klassifikation><zusatz>.png  (Zeilen Views / Uploads,
  Spalten N_eff und CR3 je Phase; durchgezogen Sample "alle", gestrichelt
  "vorkrieg")
- konzentration_phasen<zusatz>.csv  (alle Kennzahlen je Sample, Klassifikation,
  Gruppe, Phase und Metrik, Long-Format)
- konzentration_kanaele<zusatz>.csv  (Wert, Anteil und Rang je Kanal, Phase, Metrik)
- konzentration_methodik<zusatz>.md  (Formeln, Kennzahltabellen, groesste Kanaele)

Ausfuehren aus dem Repo-Root:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.marktkonzentration_rohdaten_plots
"""

import math

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from youtube_code.config import OUTPUTS
from youtube_code.step6_auswertung.prepare_channel_scores import KRIEGSBEGINN, relativ_periode
from youtube_code.step6_auswertung import marktanteil_rohdaten_plots as ma

# =========================================================
# CONFIG
# =========================================================

ROHDATEN_PFAD = OUTPUTS / "stata_rohdaten"
PFAD_PLOTS = OUTPUTS / "segment_analysis" / "plots_marktkonzentration_rohdaten"

# Videoformate (Werte der Spalte format in videos_roh, z. B. "long", "short"; nicht leer)
FORMAT = ["long"]

# Kanalauswahl: Liste von channel_ids (Strings wie in kanaele_roh.channel_id),
# leere Liste = alle Kanaele. Default = Auswahl der Marktanteils-Grafiken
# (ma.KANALLISTE, dort nach sample-Codes aus channels_check.xlsx gefiltert).
KANALLISTE = ma.KANALLISTE
# True/False: manuell als alternativ rechts codierte Kanaele ohne Baseline-Gruppe
# zu "Alternative (rechts)" zaehlen (wie ma.MANUELL_ALT_RECHTS, Default identisch)
MANUELL_ALT_RECHTS = ma.MANUELL_ALT_RECHTS

# Klassifikationen (Schluessel aus ma.KLASSIFIKATIONEN: "medientyp_ideologie",
# "populismus_tertile", "populismus_median"; nicht leer)
KLASSIFIKATIONEN_AKTIV = ["medientyp_ideologie"]

# Phasen in rel_monat (von, bis), inklusive, ganze Zahlen in [-37, 51], ohne
# Ueberschneidung; Monat 0 = [24.02.2022, 24.03.2022). Gleich lang (12 Monate),
# damit die Fensterlaenge die Konzentration nicht verschiebt (laengere Fenster
# glaetten virale Ausreisser staerker); zwei Vorkriegsjahre als Pre-Trend-Check.
PHASEN = {
    "Vorjahr 2 (-24 bis -13)": (-24, -13),
    "Vorjahr 1 (-12 bis -1)": (-12, -1),
    "Jahr 1 (0 bis 11)": (0, 11),
    "Jahr 2 (12 bis 23)": (12, 23),
    "Jahr 3 (24 bis 35)": (24, 35),
    "Jahr 4 (36 bis 47)": (36, 47),
}
# Phasen in den Konzentrationskurven (Namen aus PHASEN, 1 bis 4 Stueck, hell -> dunkel)
KURVEN_PHASEN = ["Vorjahr 1 (-12 bis -1)", "Jahr 1 (0 bis 11)", "Jahr 4 (36 bis 47)"]
# x-Achse der Kurven: "rang" = Zahl der Kanaele (groesster zuerst, eigene Achse je Gruppe);
# "anteil" = Anteil der Kanaele in % (Gruppen unterschiedlicher Groesse vergleichbar)
KURVE_X = "rang"
# Mindestzahl aktiver Kanaele je Gruppe und Phase (ganze Zahl >= 2); darunter
# Kennzahlen in den Tabellen mit * markiert und nicht in der Zeitreihengrafik
MIN_KANAELE = 5
# Zahl der groessten Kanaele je Gruppe in der Methodik-Datei (ganze Zahl >= 1)
TOP_KANAELE_MD = 5

# =========================================================
# CONFIG ENDE
# =========================================================

METRIKEN = {"views": "Views", "uploads": "Uploads"}
# Sequentielle Phasenfarben (validierte Referenzpalette wie in 8i, hell -> dunkel)
PHASEN_FARBEN = ["#c9ddf5", "#9cc3ee", "#2a78d6", "#0d3a73"]
SAMPLE_STIL = {"alle": "-", "vorkrieg": "--"}
KENNZAHLEN_MD = [
    ("n_kanaele", "Aktive Kanäle N", ".0f"),
    ("n_eff", "N_eff = 1/HHI", ".1f"),
    ("n_eff_rel", "N_eff / N (%)", ".0f"),
    ("cr1", "CR1: Anteil des größten Kanals (%)", ".0f"),
    ("cr3", "CR3: Anteil der 3 größten Kanäle (%)", ".0f"),
    ("k50", "k50: Kanäle für 50 %", ".0f"),
    ("k80", "k80: Kanäle für 80 %", ".0f"),
    ("top10", "Anteil der größten 10 % der Kanäle (%)", ".0f"),
    ("gini", "Gini", ".2f"),
]


def kurz(phase):
    """Phasenname ohne Monatsangabe ("Jahr 1 (0 bis 11)" -> "Jahr 1")."""
    return phase.split(" (")[0]


def phasen_sortiert():
    return sorted(PHASEN, key=lambda p: PHASEN[p][0])


# =========================================================
# SCHRITT 1: Daten
# =========================================================

def lade_videos():
    v = pd.read_stata(ROHDATEN_PFAD / "videos_roh.dta",
                      columns=["channel_id", "upload_ts", "views", "format"])
    v["format"] = v["format"].astype(str)
    v = v[v["format"].isin(FORMAT) & v["views"].notna()].copy()
    rel_monat = relativ_periode(v["upload_ts"], pd.Timestamp(KRIEGSBEGINN), 1)
    v["phase"] = None
    for name, (a, b) in PHASEN.items():
        v.loc[rel_monat.between(a, b), "phase"] = name
    v = v[v["phase"].notna()]
    print(f"[Videos] {len(v)} Videos (format {FORMAT}) in den Phasen: "
          f"{v['phase'].value_counts().reindex(phasen_sortiert()).to_dict()}")
    return v[["channel_id", "phase", "views"]]


def kanal_werte(v, gruppen_spalte):
    """Kanal x Phase x Metrik (Long-Format): wert = Views-Summe bzw. Zahl der
    Uploads, anteil = Anteil am Typ in der Phase (%), rang = 1 fuer den groessten
    Kanal. Nur aktive Kanaele (>= 1 Upload in der Phase)."""
    d = v[v[gruppen_spalte].notna()]
    k = d.groupby([gruppen_spalte, "phase", "channel_id"], as_index=False).agg(
        views=("views", "sum"), uploads=("views", "size"))
    k = k.rename(columns={gruppen_spalte: "gruppe"}).melt(
        id_vars=["gruppe", "phase", "channel_id"], value_vars=list(METRIKEN),
        var_name="metrik", value_name="wert")
    zelle = ["gruppe", "phase", "metrik"]
    k["anteil"] = k["wert"] / k.groupby(zelle)["wert"].transform("sum") * 100
    k["rang"] = k.groupby(zelle)["wert"].rank(method="first", ascending=False).astype(int)
    return k.sort_values([*zelle, "rang"]).reset_index(drop=True)


# =========================================================
# SCHRITT 2: Kennzahlen
# =========================================================

def kennzahlen(werte):
    """Konzentrationsmasse einer Zelle aus den Kanalwerten (Formeln im Docstring)."""
    x = np.sort(werte.to_numpy(dtype=float))[::-1]
    n, summe = len(x), x.sum()
    if summe <= 0:
        return {"n_kanaele": n, "summe": summe}
    s = x / summe
    kum = np.cumsum(s)
    hhi = float((s ** 2).sum())
    aufsteigend = x[::-1]
    return {
        "n_kanaele": n,
        "summe": summe,
        "hhi": hhi,
        "n_eff": 1 / hhi,
        "n_eff_rel": 1 / hhi / n * 100,
        "cr1": s[0] * 100,
        "cr3": s[:3].sum() * 100,
        # kleinster Rang mit kumuliertem Anteil >= 50 % bzw. 80 % (Toleranz fuer Rundung)
        "k50": int(np.searchsorted(kum, 0.5 - 1e-9) + 1),
        "k80": int(np.searchsorted(kum, 0.8 - 1e-9) + 1),
        "top10": s[:math.ceil(0.1 * n)].sum() * 100,
        "gini": 2 * np.sum(np.arange(1, n + 1) * aufsteigend) / (n * summe) - (n + 1) / n,
    }


def berechne_kennzahlen(k):
    zeilen = []
    for (gruppe, phase, metrik), r in k.groupby(["gruppe", "phase", "metrik"], sort=False):
        zeilen.append({"gruppe": gruppe, "phase": phase, "metrik": metrik,
                       **kennzahlen(r["wert"]),
                       "groesster_kanal": r.loc[r["rang"] == 1, "channel_id"].iloc[0]})
    return pd.DataFrame(zeilen)


# =========================================================
# SCHRITT 3: Grafiken
# =========================================================

def _stil(ax):
    ax.grid(color="#e5e4e0", linewidth=0.7)
    ax.set_axisbelow(True)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)


def plotte_kurven(k, klass, sample_label, dateiname):
    """Konzentrationskurven: Spalten = Gruppen, Zeilen = Views / Uploads, je Phase
    aus KURVEN_PHASEN eine Kurve (N der Phase in der Legende)."""
    cfg = ma.KLASSIFIKATIONEN[klass]
    gruppen = [g for g in cfg["gruppen"] if g in set(k["gruppe"])]
    farben = PHASEN_FARBEN[-len(KURVEN_PHASEN):]
    fig, achsen = plt.subplots(2, len(gruppen), figsize=(max(3.6 * len(gruppen), 10), 8.2),
                               sharey=True, squeeze=False)
    for zeile, (metrik, m_label) in enumerate(METRIKEN.items()):
        for sp, gruppe in enumerate(gruppen):
            ax = achsen[zeile, sp]
            for phase, farbe in zip(KURVEN_PHASEN, farben):
                r = k[(k["gruppe"] == gruppe) & (k["phase"] == phase) & (k["metrik"] == metrik)]
                if r.empty:
                    continue
                n = len(r)
                x = np.arange(n + 1, dtype=float)
                if KURVE_X == "anteil":
                    x = x / n * 100
                y = np.concatenate([[0.0], r.sort_values("rang")["anteil"].cumsum().to_numpy()])
                ax.plot(x, y, color=farbe, linewidth=2, marker="o" if n <= 30 else None,
                        markersize=3.5, markeredgecolor="white", markeredgewidth=0.4,
                        label=f"{kurz(phase)} (N = {n})")
            if KURVE_X == "anteil":
                ax.plot([0, 100], [0, 100], color="#8a8883", linestyle=":", linewidth=1)
            ax.axhline(50, color="#8a8883", linestyle="--", linewidth=0.9)
            ax.set_ylim(0, 101)
            ax.set_xlim(left=0)
            if zeile == 0:
                ax.set_title(gruppe, fontsize=11, color=cfg["farben"][cfg["gruppen"].index(gruppe)])
            else:
                ax.set_xlabel("Anteil der Kanäle (%, größte zuerst)" if KURVE_X == "anteil"
                              else "Zahl der Kanäle (größte zuerst)")
            ax.legend(fontsize=7.5, frameon=False, loc="lower right")
            _stil(ax)
        achsen[zeile, 0].set_ylabel(f"Kumulierter Anteil an den {m_label} des Typs (%)")
    fig.suptitle(f"Konzentration innerhalb der Gruppen ({cfg['titel']}) – {sample_label}\n"
                 "oben: Views, unten: Uploads; gestrichelt = 50 %", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(PFAD_PLOTS / dateiname, dpi=150)
    plt.close(fig)
    print(f"[Plot] {PFAD_PLOTS / dateiname}")
    return dateiname


def plotte_zeitreihe(kz_je_sample, klass, dateiname):
    """N_eff und CR3 je Phase und Gruppe; Zeilen Views / Uploads, Linienstil = Sample."""
    cfg = ma.KLASSIFIKATIONEN[klass]
    phasen = phasen_sortiert()
    n_vor = sum(PHASEN[p][1] <= -1 for p in phasen)
    spalten = [("n_eff", "Effektive Zahl der Kanäle (1/HHI)"),
               ("cr3", "Anteil der 3 größten Kanäle (%)")]
    fig, achsen = plt.subplots(2, 2, figsize=(14, 8.8), sharex=True, squeeze=False)
    for zeile, (metrik, m_label) in enumerate(METRIKEN.items()):
        for sp, (kz, kz_label) in enumerate(spalten):
            ax = achsen[zeile, sp]
            for s_key, d in kz_je_sample.items():
                for gruppe, farbe in zip(cfg["gruppen"], cfg["farben"]):
                    r = d[(d["gruppe"] == gruppe) & (d["metrik"] == metrik)
                          & (d["n_kanaele"] >= MIN_KANAELE)].set_index("phase").reindex(phasen)
                    if r[kz].notna().any():
                        ax.plot(range(len(phasen)), r[kz], color=farbe, linewidth=2 if s_key == "alle" else 1.4,
                                linestyle=SAMPLE_STIL.get(s_key, ":"),
                                marker="o" if s_key == "alle" else None, markersize=4)
            if 0 < n_vor < len(phasen):
                ax.axvline(n_vor - 0.5, color="#52514e", linestyle="--", linewidth=1)
                ax.text(n_vor - 0.45, 0.98, "Kriegsbeginn", transform=ax.get_xaxis_transform(),
                        va="top", fontsize=8, color="#52514e")
            ax.set_title(f"{m_label}: {kz_label}", fontsize=10.5)
            ax.set_ylim(bottom=0)
            ax.set_xticks(range(len(phasen)))
            ax.set_xticklabels([kurz(p) for p in phasen])
            _stil(ax)
    handles = [Line2D([], [], color=f, linewidth=2) for f in cfg["farben"]]
    labels = list(cfg["gruppen"])
    for s_key, (s_label, _) in ma.SAMPLES.items():
        handles.append(Line2D([], [], color="#52514e", linestyle=SAMPLE_STIL.get(s_key, ":")))
        labels.append(s_label)
    fig.legend(handles, labels, loc="lower center", ncol=len(labels), frameon=False, fontsize=9)
    fig.suptitle(f"Konzentration innerhalb der Gruppen je Phase ({cfg['titel']}); "
                 f"Zellen mit < {MIN_KANAELE} aktiven Kanälen ausgelassen", fontsize=12)
    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    fig.savefig(PFAD_PLOTS / dateiname, dpi=150)
    plt.close(fig)
    print(f"[Plot] {PFAD_PLOTS / dateiname}")
    return dateiname


# =========================================================
# SCHRITT 4: Methodik-Datei
# =========================================================

def _zelle(wert, n, fmt):
    if pd.isna(wert):
        return "–"
    return format(wert, fmt) + ("*" if n < MIN_KANAELE else "")


def kennzahl_tabelle(kz, metrik, spalte, fmt, gruppen):
    phasen = phasen_sortiert()
    d = kz[kz["metrik"] == metrik].set_index(["gruppe", "phase"])
    z = ["| Gruppe | " + " | ".join(kurz(p) for p in phasen) + " |", "|---|" + "---:|" * len(phasen)]
    for g in gruppen:
        zellen = [_zelle(d.at[(g, p), spalte], d.at[(g, p), "n_kanaele"], fmt)
                  if (g, p) in d.index else "–" for p in phasen]
        z.append(f"| {g} | " + " | ".join(zellen) + " |")
    return z


def top_tabelle(k, gruppe, metrik, namen):
    z = ["| Rang | " + " | ".join(kurz(p) for p in KURVEN_PHASEN) + " |",
         "|---:|" + "---|" * len(KURVEN_PHASEN)]
    for rang in range(1, TOP_KANAELE_MD + 1):
        zellen = []
        for p in KURVEN_PHASEN:
            r = k[(k["gruppe"] == gruppe) & (k["metrik"] == metrik) & (k["phase"] == p) & (k["rang"] == rang)]
            if r.empty:
                zellen.append("–")
            else:
                name = str(namen.get(r["channel_id"].iloc[0], r["channel_id"].iloc[0])).replace("|", "/").strip()
                zellen.append(f"{name} ({r['anteil'].iloc[0]:.0f} %)")
        z.append(f"| {rang} | " + " | ".join(zellen) + " |")
    return z


def schreibe_methodik(kanaele, ergebnisse, erzeugt, dateiname):
    """ergebnisse = {(Sample, Klassifikation): (kanalwerte, kennzahlen)}."""
    namen = kanaele.set_index("channel_id")["kanal_name"].to_dict()
    z = [
        "# Marktkonzentration innerhalb der Gruppen",
        "",
        "Skript: `src/youtube_code/step6_auswertung/marktkonzentration_rohdaten_plots.py`. "
        f"Datenbasis: `videos_roh.dta`/`kanaele_roh.dta`, `format` in {FORMAT}, alle Themen. "
        f"Kanalauswahl: {len(kanaele)} Kanäle"
        + (" (KANALLISTE)" if KANALLISTE else " (alle)")
        + f"; MANUELL_ALT_RECHTS = {MANUELL_ALT_RECHTS}"
        + (f"; ÖRR-Doku-Gruppe aus sample-Codes {ma.OERR_DOKU_CODES}" if ma.OERR_DOKU_CODES else "") + ".",
        "",
        "## Formeln",
        "",
        "Zelle = Gruppe × Phase; N = Kanäle mit ≥ 1 Upload in der Phase; x_c = Views-Summe bzw. "
        "Zahl der Uploads des Kanals, s_c = x_c / Σx.",
        "",
        "```",
        "HHI    = Σ s_c²            N_eff = 1 / HHI   (N_eff / N = 100 % bei Gleichverteilung)",
        "CR1/3  = Anteil des größten bzw. der 3 größten Kanäle",
        "k50/80 = kleinste Zahl Kanäle mit zusammen ≥ 50 % bzw. 80 %",
        "Top10  = Anteil der größten ceil(0.1 · N) Kanäle",
        "Gini   = 2 Σ i·x_(i) / (N Σx) − (N + 1) / N   (x aufsteigend)",
        "```",
        "",
        "Phasen (rel_monat, je 12 Monate): "
        + "; ".join(f"{p}" for p in phasen_sortiert()) + ".",
        "",
        "**Lesehilfe und Grenzen**",
        "",
        "- N_eff, CR und k hängen an der Kanalzahl N; zwischen Gruppen unterschiedlicher Größe "
        "sind N_eff / N, Top10 und Gini vergleichbarer.",
        f"- `*` = weniger als {MIN_KANAELE} aktive Kanäle, Kennzahl kaum belastbar.",
        "- Gemessen wird die Konzentration im Kanal-Sample, nicht im Markt: kleine Kanäle fehlen "
        "je Typ unterschiedlich stark. Aussagekräftig ist vor allem die Veränderung innerhalb einer "
        "Gruppe; Vorjahr 2 → Vorjahr 1 zeigt den Trend vor Kriegsbeginn.",
        "- Kommen nach Kriegsbeginn neue Kanäle hinzu, sinkt die Konzentration mechanisch; das "
        "Sample „nur vor Kriegsbeginn aktive Kanäle“ hält die Kanalbasis stabiler.",
        "- Views-Konzentration deutlich über der Upload-Konzentration = wenige Kanäle ziehen die "
        "Aufmerksamkeit, obwohl viele produzieren.",
        "",
    ]
    for (s_key, klass), (k, kz) in ergebnisse.items():
        cfg = ma.KLASSIFIKATIONEN[klass]
        gruppen = [g for g in cfg["gruppen"] if g in set(kz["gruppe"])]
        s_label = ma.SAMPLES[s_key][0]
        im_sample = kanaele[ma.SAMPLES[s_key][1](kanaele)]
        anzahl = im_sample[klass].value_counts()
        z += [f"## {cfg['titel']} – {s_label}", "",
              "Kanäle mit Gruppe im Sample: "
              + ", ".join(f"{g} {int(anzahl.get(g, 0))}" for g in gruppen) + ".", ""]
        for metrik, m_label in METRIKEN.items():
            z += [f"### {m_label}", ""]
            for spalte, titel, fmt in KENNZAHLEN_MD:
                z += [f"**{titel}**", ""] + kennzahl_tabelle(kz, metrik, spalte, fmt, gruppen) + [""]
        if s_key == "alle":
            z += [f"### Größte Kanäle je Gruppe (Anteil am Typ)", ""]
            for gruppe in gruppen:
                for metrik, m_label in METRIKEN.items():
                    z += [f"**{gruppe} – {m_label}**", ""] + top_tabelle(k, gruppe, metrik, namen) + [""]
    z += ["## Erzeugte Dateien", ""] + [f"- `{d}`" for d in erzeugt] + [""]
    pfad = PFAD_PLOTS / dateiname
    pfad.write_text("\n".join(z), encoding="utf-8")
    print(f"[Methodik] {pfad}")


# =========================================================
# MAIN
# =========================================================

def pruefe_config():
    if not isinstance(FORMAT, (list, tuple)) or not FORMAT or not all(isinstance(f, str) for f in FORMAT):
        raise SystemExit(f"FORMAT muss eine nicht leere Liste von Strings sein, nicht {FORMAT!r}.")
    if not isinstance(KANALLISTE, (list, tuple, set)) or not all(isinstance(c, str) for c in KANALLISTE):
        raise SystemExit("KANALLISTE muss eine Liste von channel_id-Strings sein (leer = alle Kanaele).")
    if not isinstance(MANUELL_ALT_RECHTS, bool):
        raise SystemExit(f"MANUELL_ALT_RECHTS muss True oder False sein, nicht {MANUELL_ALT_RECHTS!r}.")
    falsch = [k for k in KLASSIFIKATIONEN_AKTIV if k not in ma.KLASSIFIKATIONEN]
    if not KLASSIFIKATIONEN_AKTIV or falsch:
        raise SystemExit(f"KLASSIFIKATIONEN_AKTIV darf nicht leer sein; unbekannt: {falsch}, "
                         f"erlaubt: {list(ma.KLASSIFIKATIONEN)}.")
    if not PHASEN:
        raise SystemExit("PHASEN darf nicht leer sein.")
    for name, ab in PHASEN.items():
        if not (len(ab) == 2 and all(isinstance(m, int) for m in ab) and -37 <= ab[0] <= ab[1] <= 51):
            raise SystemExit(f"PHASEN[{name!r}] muss (von, bis) mit ganzen Zahlen -37 <= von <= bis <= 51 "
                             f"sein, nicht {ab!r}.")
    sortiert = phasen_sortiert()
    for p1, p2 in zip(sortiert, sortiert[1:]):
        if PHASEN[p1][1] >= PHASEN[p2][0]:
            raise SystemExit(f"PHASEN {p1!r} und {p2!r} ueberschneiden sich.")
    falsch = [p for p in KURVEN_PHASEN if p not in PHASEN]
    if not 1 <= len(KURVEN_PHASEN) <= len(PHASEN_FARBEN) or falsch:
        raise SystemExit(f"KURVEN_PHASEN muss 1 bis {len(PHASEN_FARBEN)} Namen aus PHASEN enthalten; "
                         f"unbekannt: {falsch}.")
    if KURVE_X not in ("rang", "anteil"):
        raise SystemExit(f"KURVE_X muss 'rang' oder 'anteil' sein, nicht {KURVE_X!r}.")
    if not isinstance(MIN_KANAELE, int) or MIN_KANAELE < 2:
        raise SystemExit(f"MIN_KANAELE muss eine ganze Zahl >= 2 sein, nicht {MIN_KANAELE!r}.")
    if not isinstance(TOP_KANAELE_MD, int) or TOP_KANAELE_MD < 1:
        raise SystemExit(f"TOP_KANAELE_MD muss eine ganze Zahl >= 1 sein, nicht {TOP_KANAELE_MD!r}.")


def main():
    pruefe_config()
    # Gruppenbildung aus 8i mit den hier gesetzten Schaltern
    ma.MANUELL_ALT_RECHTS = MANUELL_ALT_RECHTS
    ma.setze_oerr_doku_gruppe()
    zusatz = "_" + "_".join(FORMAT) + ma.datei_zusatz()

    kanaele, _ = ma.bilde_gruppen(ma.lade_kanaele())
    if KANALLISTE:
        fehlend = sorted(set(KANALLISTE) - set(kanaele["channel_id"]))
        if fehlend:
            print(f"[Kanalliste] {len(fehlend)} channel_ids nicht in kanaele_roh: {fehlend}")
        kanaele = kanaele[kanaele["channel_id"].isin(KANALLISTE)]
        if kanaele.empty:
            raise SystemExit("KANALLISTE: keine der channel_ids kommt in kanaele_roh vor.")
        print(f"[Kanalliste] Sample auf {len(kanaele)} Kanaele eingeschraenkt.")
    kanaele, _ = ma.manuell_alt_rechts(kanaele)
    # Tertil- und Mediangrenzen wie in 8i nur ueber das tatsaechliche Sample
    kanaele, _ = ma.bilde_tertil_gruppen(kanaele)
    kanaele, _ = ma.bilde_median_gruppen(kanaele)

    videos = lade_videos().merge(
        kanaele[["channel_id", "sample_vorkrieg", *KLASSIFIKATIONEN_AKTIV]], on="channel_id")
    PFAD_PLOTS.mkdir(parents=True, exist_ok=True)

    erzeugt, ergebnisse, alle_kz, alle_k = [], {}, [], []
    for klass in KLASSIFIKATIONEN_AKTIV:
        kz_je_sample = {}
        for s_key, (s_label, s_filter) in ma.SAMPLES.items():
            ids = set(kanaele.loc[s_filter(kanaele), "channel_id"])
            k = kanal_werte(videos[videos["channel_id"].isin(ids)], klass)
            kz = berechne_kennzahlen(k)
            ergebnisse[(s_key, klass)] = (k, kz)
            kz_je_sample[s_key] = kz
            alle_kz.append(kz.assign(sample=s_key, klassifikation=klass))
            alle_k.append(k.assign(sample=s_key, klassifikation=klass))
            erzeugt.append(plotte_kurven(k, klass, s_label,
                                         f"konzentrationskurven_{klass}_{s_key}{zusatz}.png"))
        erzeugt.append(plotte_zeitreihe(kz_je_sample, klass, f"konzentration_zeitreihe_{klass}{zusatz}.png"))

        # Kurzueberblick auf der Konsole: N_eff der Views, Sample alle
        tab = kz_je_sample["alle"].query("metrik == 'views'").pivot(
            index="gruppe", columns="phase", values="n_eff").reindex(columns=phasen_sortiert())
        print(f"[N_eff Views, alle Kanaele] {klass}\n{tab.rename(columns=kurz).round(1).to_string()}")

    namen = kanaele.set_index("channel_id")["kanal_name"]
    spalten_vorn = ["sample", "klassifikation", "gruppe", "phase", "metrik"]
    kz_csv = pd.concat(alle_kz)
    kz_csv["groesster_kanal_name"] = kz_csv["groesster_kanal"].map(namen)
    kz_csv = kz_csv[spalten_vorn + [c for c in kz_csv.columns if c not in spalten_vorn]]
    k_csv = pd.concat(alle_k)
    k_csv["kanal_name"] = k_csv["channel_id"].map(namen)
    k_csv = k_csv[spalten_vorn + [c for c in k_csv.columns if c not in spalten_vorn]]
    for df, name in [(kz_csv, f"konzentration_phasen{zusatz}.csv"),
                     (k_csv, f"konzentration_kanaele{zusatz}.csv")]:
        df.to_csv(PFAD_PLOTS / name, index=False)
        erzeugt.append(name)
    schreibe_methodik(kanaele, ergebnisse, erzeugt, f"konzentration_methodik{zusatz}.md")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
marktanteil_rohdaten_plots.py

Marktanteils-Grafiken (Kapitel D der Masterarbeit) auf Basis des zentralen
Analysedatensatzes outputs/stata_rohdaten/ (videos_roh.dta, kanaele_roh.dta,
erzeugt von export_stata_rohdaten.py, Spezifikation docs/codebuch_rohdatensatz.md).
Loest fuer die Marktanteile die bisherige Datenbasis ab
(channel_video_erfolg.csv + lade_basisdaten() aus
frage4_kriegspraemie_relative_views_plots.py, genutzt von
frage4_kriegspraemie_marktanteil_plots.py und marktanteil_themen_plots.py).

Marktanteil je Zelle (Gruppe x rel_monat x Umfang), gepoolt auf Video-Ebene:

    anteil = sum(views | Gruppe, Umfang, Monat) / sum(views | alle Gruppen der Klassifikation, Umfang, Monat) * 100

Die Anteile einer Klassifikation summieren sich je Monat zu 100 %. Monate mit
< MIN_VIDEOS_PRO_MONAT Videos (ueber alle Gruppen zusammen) fallen ganz weg.

Umfaenge
--------
- "politische Videos": politisch == "ja" (YouTube-topic_categories "Politics"),
  Kriegsvideos eingeschlossen.
- "Kriegsvideos": krieg == "ja" (Stichwortklassifikation russia_ukraine_war,
  Titel + Beschreibung), ungefiltert nach politisch (wie in den bisherigen
  Marktanteils-Skripten).

Klassifikationen
----------------
1. "medientyp_ideologie": OeRR, traditionelle Medien, alternative Medien
   links/mitte/rechts. Alternative Medien (medientyp "Creator & alternative
   Medien") nach ideo_gesellschaft_baseline mit den bisherigen Schnitten
   IDEOLOGIE_SCHNITTE = (-0.5, 0.5) aus deskriptiv_aggregation.py. Abweichung zu
   frueher: die Ideologie stammt jetzt aus der Baseline (Vorkriegsfenster, ohne
   Kriegsvideos) statt aus channel_classification_ideology.csv. Alternative
   Medien ohne Ideologie-Baseline und Partei/Politiker fallen raus.
2. "populismus_tertile": Kanaele aus OeRR, traditionellen und alternativen
   Medien (Partei/Politiker wie in 1. ausgeschlossen) mit pop_baseline, in
   Tertile nach pop_baseline (ungewichtet je Kanal). Die Baseline ist vor
   Kriegsbeginn gemessen, die Gruppenzugehoerigkeit ist also nicht durch das
   Verhalten nach Kriegsbeginn beeinflusst.

Kanal-Samples (je Sample ein Satz Grafiken, siehe AP 2 Stichprobenbias)
-----------------------------------------------------------------------
- "alle": alle Kanaele aus kanaele_roh (427er-Kanon-Sample).
- "vorkrieg": nur sample_vorkrieg == "ja" (vor Kriegsbeginn aktive Kanaele);
  zeigt, ob eine Verschiebung auch ohne erst spaeter gestartete Kanaele besteht.

Ausgabe nach OUTPUTS / "segment_analysis" / "plots_marktanteil_rohdaten":
- marktanteil_<klassifikation>_<sample>.png  (links politische Videos, rechts
  Kriegsvideos; Punkte = Monatswerte, Linie = LOWESS-Glaettung)
- marktanteil_monat.csv  (alle Monatswerte, Long-Format)
- marktanteil_methodik.md  (Methodik, Fallzahlen, Phasenmittel)

Ausfuehren aus dem Repo-Root:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.marktanteil_rohdaten_plots
"""

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from statsmodels.nonparametric.smoothers_lowess import lowess

from youtube_code.config import OUTPUTS
from youtube_code.step6_auswertung.prepare_channel_scores import KRIEGSBEGINN, relativ_periode

# =========================================================
# CONFIG
# =========================================================

ROHDATEN_PFAD = OUTPUTS / "stata_rohdaten"
PFAD_PLOTS = OUTPUTS / "segment_analysis" / "plots_marktanteil_rohdaten"

# Monat 0 = [24.02.2022, 24.03.2022). Daten reichen vom 01.01.2021 bis 30.06.2026,
# -13 und 51 sind die aeussersten vollstaendig abgedeckten Monate.
PERIODE_MIN = -13
PERIODE_MAX = 51
MIN_VIDEOS_PRO_MONAT = 20
GLAETTUNG_LOWESS_FRAC = 0.15

IDEOLOGIE_SCHNITTE = (-0.5, 0.5)   # wie deskriptiv_aggregation.IDEOLOGIE_SCHNITTE

MEDIENTYP_ALT = "Creator & alternative Medien"
MEDIENTYP_OERR = "ÖRR"
MEDIENTYP_TRAD = "traditionelle Medien"

# Phasen fuer die Mittelwert-Tabelle in der Methodik-Datei (rel_monat, inklusive)
PHASEN = {
    "Vorkrieg (-13 bis -1)": (-13, -1),
    "Jahr 1 (0 bis 11)": (0, 11),
    "Jahr 2 (12 bis 23)": (12, 23),
    "Jahr 3 (24 bis 35)": (24, 35),
    "Jahr 4+ (36 bis 51)": (36, 51),
}

UMFAENGE = {
    "politisch": ("Politische Videos", lambda v: v["politisch"] == "ja"),
    "krieg": ("Kriegsvideos", lambda v: v["krieg"] == "ja"),
}

SAMPLES = {
    "alle": ("alle Kanäle", lambda k: pd.Series(True, index=k.index)),
    "vorkrieg": ("nur vor Kriegsbeginn aktive Kanäle", lambda k: k["sample_vorkrieg"] == "ja"),
}

# Farben: kategorisch in fester Reihenfolge (validierte Referenzpalette des
# dataviz-Skills), Tertile sequentiell in einem Farbton (hell -> dunkel).
KLASSIFIKATIONEN = {
    "medientyp_ideologie": {
        "titel": "Medientyp und Ideologie",
        "gruppen": ["ÖRR", "Traditionelle Medien", "Alternative (links)",
                    "Alternative (mitte)", "Alternative (rechts)"],
        "farben": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"],
    },
    "populismus_tertile": {
        "titel": "Populismus-Baseline (Tertile)",
        "gruppen": ["Tertil 1 (niedrig)", "Tertil 2 (mittel)", "Tertil 3 (hoch)"],
        "farben": ["#9cc3ee", "#2a78d6", "#0d3a73"],
    },
}


# =========================================================
# SCHRITT 1: Daten laden und Gruppen bilden
# =========================================================

def lade_kanaele():
    k = pd.read_stata(ROHDATEN_PFAD / "kanaele_roh.dta")
    for c in ["medientyp", "sample_vorkrieg"]:
        k[c] = k[c].astype(str)
    print(f"[Kanaele] {len(k)} Kanaele; Medientyp: {k['medientyp'].value_counts().to_dict()}")
    return k


def bilde_gruppen(k):
    """Haengt je Klassifikation eine Gruppenspalte an (NaN = nicht zugeordnet).
    Gibt zusaetzlich die Tertilgrenzen zurueck."""
    k = k.copy()
    medien = k["medientyp"].isin([MEDIENTYP_OERR, MEDIENTYP_TRAD, MEDIENTYP_ALT])

    ideo = pd.cut(k["ideo_gesellschaft_baseline"],
                  bins=[-np.inf, *IDEOLOGIE_SCHNITTE, np.inf], labels=["links", "mitte", "rechts"])
    g1 = pd.Series(np.nan, index=k.index, dtype=object)
    g1[k["medientyp"] == MEDIENTYP_OERR] = "ÖRR"
    g1[k["medientyp"] == MEDIENTYP_TRAD] = "Traditionelle Medien"
    ist_alt = (k["medientyp"] == MEDIENTYP_ALT) & ideo.notna()
    g1[ist_alt] = "Alternative (" + ideo[ist_alt].astype(str) + ")"
    k["medientyp_ideologie"] = g1

    mit_pop = medien & k["pop_baseline"].notna()
    grenzen = k.loc[mit_pop, "pop_baseline"].quantile([1 / 3, 2 / 3]).to_list()
    g2 = pd.Series(np.nan, index=k.index, dtype=object)
    g2[mit_pop] = pd.qcut(k.loc[mit_pop, "pop_baseline"], 3,
                          labels=KLASSIFIKATIONEN["populismus_tertile"]["gruppen"]).astype(str)
    k["populismus_tertile"] = g2

    for name in KLASSIFIKATIONEN:
        print(f"[Gruppen] {name}: {k[name].value_counts().to_dict()}, "
              f"nicht zugeordnet: {int(k[name].isna().sum())}")
    print(f"[Gruppen] Tertilgrenzen pop_baseline: {grenzen[0]:.3f} / {grenzen[1]:.3f}")
    return k, grenzen


def lade_videos():
    v = pd.read_stata(ROHDATEN_PFAD / "videos_roh.dta",
                      columns=["video_id", "channel_id", "upload_ts", "views", "politisch", "krieg"])
    for c in ["politisch", "krieg"]:
        v[c] = v[c].astype(str)
    v["rel_monat"] = relativ_periode(v["upload_ts"], pd.Timestamp(KRIEGSBEGINN), 1)
    n_ohne_views = int(v["views"].isna().sum())
    v = v[v["views"].notna() & v["rel_monat"].between(PERIODE_MIN, PERIODE_MAX)]
    print(f"[Videos] {len(v)} Videos im Fenster {PERIODE_MIN}..{PERIODE_MAX} "
          f"({n_ohne_views} ohne views verworfen)")
    return v


# =========================================================
# SCHRITT 2: Marktanteile
# =========================================================

def berechne_marktanteile(v, gruppen_spalte):
    """Monatliche Anteile je Gruppe. Nenner = Summe ueber alle Gruppen der
    Klassifikation; Monate unter MIN_VIDEOS_PRO_MONAT fallen ganz weg."""
    d = v[v[gruppen_spalte].notna()]
    zellen = d.groupby(["rel_monat", gruppen_spalte], as_index=False).agg(
        views_summe=("views", "sum"), n_videos=("views", "size"))
    monat = zellen.groupby("rel_monat", as_index=False).agg(
        views_gesamt=("views_summe", "sum"), n_gesamt=("n_videos", "sum"))
    weg = monat.loc[monat["n_gesamt"] < MIN_VIDEOS_PRO_MONAT, "rel_monat"].to_list()
    if weg:
        print(f"[Marktanteil] {gruppen_spalte}: Monate unter Mindestbesetzung entfernt: {weg}")
    zellen = zellen.merge(monat[monat["n_gesamt"] >= MIN_VIDEOS_PRO_MONAT], on="rel_monat")
    zellen["anteil"] = zellen["views_summe"] / zellen["views_gesamt"] * 100
    zellen = zellen.rename(columns={gruppen_spalte: "gruppe"})

    abw = (zellen.groupby("rel_monat")["anteil"].sum() - 100).abs().max()
    if abw > 0.01:
        raise ValueError(f"Anteile summieren sich nicht zu 100 % (max. Abweichung {abw:.4f} pp)")
    return zellen


def phasenmittel(anteile):
    """Ungewichteter Mittelwert der Monatsanteile je Phase."""
    zeilen = []
    for phase, (a, b) in PHASEN.items():
        teil = anteile[anteile["rel_monat"].between(a, b)]
        mittel = teil.groupby("gruppe")["anteil"].mean()
        zeilen.append(mittel.rename(phase))
    return pd.DataFrame(zeilen).T


# =========================================================
# SCHRITT 3: Grafik
# =========================================================

def glaette(x, y):
    if not GLAETTUNG_LOWESS_FRAC or len(x) < 4:
        return y
    return lowess(y, x, frac=GLAETTUNG_LOWESS_FRAC, xvals=x, return_sorted=False, it=0)


def plotte(anteile_je_umfang, klass_key, sample_label, dateiname):
    cfg = KLASSIFIKATIONEN[klass_key]
    fig, achsen = plt.subplots(1, 2, figsize=(13, 5.2), sharey=True)
    for ax, (umfang_key, anteile) in zip(achsen, anteile_je_umfang.items()):
        for gruppe, farbe in zip(cfg["gruppen"], cfg["farben"]):
            r = anteile[anteile["gruppe"] == gruppe].sort_values("rel_monat")
            if r.empty:
                continue
            x = r["rel_monat"].to_numpy(dtype=float)
            y = r["anteil"].to_numpy(dtype=float)
            ax.scatter(x, y, s=10, color=farbe, alpha=0.3, linewidths=0, zorder=2)
            ax.plot(x, glaette(x, y), color=farbe, linewidth=2, label=gruppe, zorder=3)
        ax.axvline(-0.5, color="#52514e", linestyle="--", linewidth=1)
        ax.text(-0.2, 0.98, "Kriegsbeginn", transform=ax.get_xaxis_transform(),
                va="top", fontsize=8, color="#52514e")
        ax.set_title(UMFAENGE[umfang_key][0], fontsize=11)
        ax.set_xlabel("Monat relativ zum Kriegsbeginn (24.02.2022)")
        ax.grid(axis="y", color="#e5e4e0", linewidth=0.8)
        ax.set_axisbelow(True)
        for s in ["top", "right"]:
            ax.spines[s].set_visible(False)
    achsen[0].set_ylabel("Anteil an allen Views (%)")
    achsen[0].set_ylim(bottom=0)
    handles, labels = achsen[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(labels), frameon=False, fontsize=9)
    fig.suptitle(f"Marktanteil nach {cfg['titel']} – {sample_label}", fontsize=12)
    fig.tight_layout(rect=(0, 0.06, 1, 0.97))
    PFAD_PLOTS.mkdir(parents=True, exist_ok=True)
    fig.savefig(PFAD_PLOTS / dateiname, dpi=150)
    plt.close(fig)
    print(f"[Plot] {PFAD_PLOTS / dateiname}")


# =========================================================
# SCHRITT 4: Methodik-Datei
# =========================================================

def tabelle_md(df):
    df = df.round(1)
    kopf = "| Gruppe | " + " | ".join(df.columns) + " |"
    trenn = "|---|" + "---:|" * len(df.columns)
    zeilen = [f"| {idx} | " + " | ".join(f"{w:.1f}" if pd.notna(w) else "–" for w in row) + " |"
              for idx, row in df.iterrows()]
    return [kopf, trenn, *zeilen]


def schreibe_methodik(kanaele, grenzen, fallzahlen, phasen_tabellen, erzeugt):
    z = [
        "# Methodik: Marktanteile aus dem Rohdatensatz",
        "",
        "Skript: `src/youtube_code/step6_auswertung/marktanteil_rohdaten_plots.py` "
        "(Herleitung im Moduldocstring). Datenbasis: `outputs/stata_rohdaten/videos_roh.dta`, "
        "`kanaele_roh.dta`.",
        "",
        "## Formel",
        "",
        "```",
        "anteil = sum(views | Gruppe, Umfang, Monat) / sum(views | alle Gruppen der Klassifikation, Umfang, Monat) * 100",
        "```",
        "",
        f"- Monate `rel_monat` {PERIODE_MIN} bis {PERIODE_MAX} (Monat 0 beginnt am {KRIEGSBEGINN}).",
        f"- Monate mit < {MIN_VIDEOS_PRO_MONAT} Videos (alle Gruppen zusammen) entfallen.",
        "- Views = Stand zum Abrufzeitpunkt; jüngere Videos hatten weniger Zeit, Views zu sammeln. "
        "Das betrifft alle Gruppen, verzerrt Anteile aber, wenn sich der Views-Verlauf über das "
        "Videoalter zwischen den Gruppen unterscheidet.",
        f"- Grafik: Punkte = Monatswerte, Linie = LOWESS (frac={GLAETTUNG_LOWESS_FRAC}, it=0).",
        "- Umfänge: politische Videos = `politisch == ja` (inkl. Kriegsvideos); "
        "Kriegsvideos = `krieg == ja` (ohne zusätzlichen Politik-Filter).",
        "",
        "## Klassifikationen",
        "",
        "1. **Medientyp × Ideologie:** ÖRR, traditionelle Medien, alternative Medien nach "
        f"`ideo_gesellschaft_baseline` (Schnitte {IDEOLOGIE_SCHNITTE[0]} / {IDEOLOGIE_SCHNITTE[1]}). "
        "Alternative Medien ohne Ideologie-Baseline und Partei/Politiker sind ausgeschlossen. "
        "Anders als in den früheren Grafiken stammt die Ideologie aus dem Vorkriegsfenster "
        "(ohne Kriegsvideos), nicht aus `channel_classification_ideology.csv`.",
        "2. **Populismus-Tertile:** ÖRR, traditionelle und alternative Medien mit `pop_baseline`, "
        f"Tertile über Kanäle (ungewichtet). Grenzen: {grenzen[0]:.3f} / {grenzen[1]:.3f}. "
        "Kanäle ohne Populismus-Baseline sind ausgeschlossen.",
        "",
        "## Kanäle je Gruppe (alle Kanäle / nur vor Kriegsbeginn aktive)",
        "",
    ]
    for klass in KLASSIFIKATIONEN:
        z.append(f"**{KLASSIFIKATIONEN[klass]['titel']}**")
        z.append("")
        z.append("| Gruppe | alle | vorkrieg |")
        z.append("|---|---:|---:|")
        vk = kanaele["sample_vorkrieg"] == "ja"
        for g in KLASSIFIKATIONEN[klass]["gruppen"]:
            z.append(f"| {g} | {int((kanaele[klass] == g).sum())} | "
                     f"{int(((kanaele[klass] == g) & vk).sum())} |")
        z.append(f"| nicht zugeordnet | {int(kanaele[klass].isna().sum())} | "
                 f"{int((kanaele[klass].isna() & vk).sum())} |")
        z.append("")

    z += ["## Videos je Auswertung", "", "| Sample | Klassifikation | Umfang | Videos | Monate |",
          "|---|---|---|---:|---:|"]
    for (s, k, u), (n, m) in fallzahlen.items():
        z.append(f"| {s} | {k} | {u} | {n} | {m} |")
    z.append("")

    z += ["## Phasenmittel der Monatsanteile (%)", "",
          "Ungewichteter Mittelwert der monatlichen Anteile je Phase (rel_monat).", ""]
    for (s, k, u), tab in phasen_tabellen.items():
        z.append(f"**{SAMPLES[s][0]} – {KLASSIFIKATIONEN[k]['titel']} – {UMFAENGE[u][0]}**")
        z.append("")
        z += tabelle_md(tab.reindex(KLASSIFIKATIONEN[k]["gruppen"]))
        z.append("")

    z += [f"## Erzeugte Dateien ({len(erzeugt)})", ""] + [f"- `{d}`" for d in erzeugt]
    pfad = PFAD_PLOTS / "marktanteil_methodik.md"
    pfad.write_text("\n".join(z) + "\n", encoding="utf-8")
    print(f"[Methodik] {pfad}")


# =========================================================
# MAIN
# =========================================================

def main():
    kanaele, grenzen = bilde_gruppen(lade_kanaele())
    videos = lade_videos().merge(
        kanaele[["channel_id", "sample_vorkrieg", *KLASSIFIKATIONEN]], on="channel_id", how="left")

    erzeugt, alle_werte, fallzahlen, phasen_tabellen = [], [], {}, {}
    for s_key, (s_label, s_filter) in SAMPLES.items():
        s_ids = set(kanaele.loc[s_filter(kanaele), "channel_id"])
        v_s = videos[videos["channel_id"].isin(s_ids)]
        for k_key in KLASSIFIKATIONEN:
            je_umfang = {}
            for u_key, (_, u_filter) in UMFAENGE.items():
                teil = v_s[u_filter(v_s)]
                anteile = berechne_marktanteile(teil, k_key)
                je_umfang[u_key] = anteile
                fallzahlen[(s_key, k_key, u_key)] = (int(teil[k_key].notna().sum()),
                                                     anteile["rel_monat"].nunique())
                phasen_tabellen[(s_key, k_key, u_key)] = phasenmittel(anteile)
                alle_werte.append(anteile.assign(sample=s_key, klassifikation=k_key, umfang=u_key))
            dateiname = f"marktanteil_{k_key}_{s_key}.png"
            plotte(je_umfang, k_key, s_label, dateiname)
            erzeugt.append(dateiname)

    csv = pd.concat(alle_werte)[["sample", "klassifikation", "umfang", "rel_monat", "gruppe",
                                 "anteil", "views_summe", "n_videos", "views_gesamt", "n_gesamt"]]
    csv.to_csv(PFAD_PLOTS / "marktanteil_monat.csv", index=False)
    erzeugt.append("marktanteil_monat.csv")
    schreibe_methodik(kanaele, grenzen, fallzahlen, phasen_tabellen, erzeugt)


if __name__ == "__main__":
    main()

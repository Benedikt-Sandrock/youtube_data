# -*- coding: utf-8 -*-
"""
shorts_anteil_plots.py

Anteil der Shorts an allen hochgeladenen Videos je Gruppe und Monat, auf Basis
des zentralen Analysedatensatzes outputs/stata_rohdaten/ (videos_roh.dta,
kanaele_roh.dta). Gruppen (Medientyp x Ideologie, Populismus-Tertile), Kanal-
Samples und Farben stammen aus marktanteil_rohdaten_plots.py (bilde_gruppen(),
KLASSIFIKATIONEN, SAMPLES), damit die Grafik direkt neben den Marktanteils-
Grafiken gelesen werden kann.

Population: Videos mit format_klass == 1 (Formatlauf des Kanals fuer das
Zeitfenster komplett) und format in {short, long}. Livestreams und Videos ohne
Formatzuordnung zaehlen weder im Zaehler noch im Nenner. Kein Themenfilter.
Vorsicht: WELT-Videos mit format_derived == 1 sind per Ausschluss als long
gesetzt (siehe Codebuch); OE24.TV faellt wegen format_klass == 0 ganz weg.

Zwei Kennzahlen (Zeilen der Grafik):

    gepoolt:    shorts_anteil = n_short(Gruppe, Monat) / n_videos(Gruppe, Monat) * 100
                Zellen mit < MIN_VIDEOS_ZELLE Videos entfallen. Dominiert von
                upload-starken Kanaelen.
    Kanalmittel: ungewichteter Mittelwert der Kanal-Anteile n_short / n_videos
                ueber Kanaele mit >= MIN_VIDEOS_KANAL_MONAT Videos im Monat;
                Zellen mit < MIN_KANAELE_ZELLE Kanaelen entfallen. Zeigt, ob
                die typische Kanalstrategie sich aendert.

Die Kanalzusammensetzung je Monat ist nicht fest (spaeter gegruendete Kanaele
kommen hinzu); das Sample "vorkrieg" haelt sie stabiler.

Ausgabe nach OUTPUTS / "segment_analysis" / "plots_shorts_anteil":
- shorts_anteil_<sample>.png  (Spalten = Klassifikationen, Zeilen = gepoolt /
  Kanalmittel; Punkte = Monatswerte, Linie = LOWESS; senkrechte Linien:
  Kriegsbeginn (gestrichelt) und EREIGNISSE (gepunktet))
- shorts_anteil_monat.csv  (alle Zellwerte, Long-Format)
- shorts_anteil_methodik.md  (Methodik, Fallzahlen, Phasenmittel)

Ausfuehren aus dem Repo-Root:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step6_auswertung.shorts_anteil_plots
"""

import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

from youtube_code.config import OUTPUTS
from youtube_code.step6_auswertung.prepare_channel_scores import KRIEGSBEGINN, relativ_periode
from youtube_code.step6_auswertung.marktanteil_rohdaten_plots import (
    KLASSIFIKATIONEN, SAMPLES, bilde_gruppen, ereignis_position, glaette, lade_kanaele, tabelle_md,
)

# =========================================================
# CONFIG
# =========================================================

ROHDATEN_PFAD = OUTPUTS / "stata_rohdaten"
PFAD_PLOTS = OUTPUTS / "segment_analysis" / "plots_shorts_anteil"

# Einschraenkung auf eine Liste von channel_ids (Strings wie in kanaele_roh.channel_id);
# leere Liste = alle Kanaele. Gruppen/Tertilgrenzen werden vorher auf allen Kanaelen gebildet.
KANALLISTE = []

# Monat 0 = [24.02.2022, 24.03.2022). Formatdaten reichen vom 01.01.2019 bis 30.06.2026;
# -37 und 51 sind die aeussersten vollstaendig abgedeckten Monate (ganze Zahlen, MIN <= MAX).
PERIODE_MIN = -37
PERIODE_MAX = 51
MIN_VIDEOS_ZELLE = 20          # gepoolt: Mindestzahl Videos je Gruppe und Monat (>= 1)
MIN_VIDEOS_KANAL_MONAT = 3     # Kanalmittel: Mindestzahl Videos eines Kanals im Monat (>= 1)
MIN_KANAELE_ZELLE = 3          # Kanalmittel: Mindestzahl Kanaele je Gruppe und Monat (>= 1)

# Weitere senkrechte Linien {Beschriftung: "JJJJ-MM-TT"}; leeres Dict = nur Kriegsbeginn.
EREIGNISSE = {
    "Shorts-Start global": "2021-07-13",
}

# Phasen fuer die Mittelwert-Tabelle in der Methodik-Datei (rel_monat, inklusive)
PHASEN = {
    "2019/20 (-37 bis -14)": (-37, -14),
    "Vorkrieg 2021/22 (-13 bis -1)": (-13, -1),
    "Jahr 1 (0 bis 11)": (0, 11),
    "Jahr 2 (12 bis 23)": (12, 23),
    "Jahr 3 (24 bis 35)": (24, 35),
    "Jahr 4+ (36 bis 51)": (36, 51),
}

KENNZAHLEN = {
    "gepoolt": "Shorts-Anteil gepoolt (%)",
    "kanalmittel": "Shorts-Anteil Kanalmittel (%)",
}


# =========================================================
# SCHRITT 1: Daten
# =========================================================

def lade_videos():
    v = pd.read_stata(ROHDATEN_PFAD / "videos_roh.dta",
                      columns=["channel_id", "upload_ts", "format", "format_klass"])
    # format_klass ist in der .dta mit Wertelabels gespeichert -> read_stata liefert "ja"/"nein"
    for c in ["format", "format_klass"]:
        v[c] = v[c].astype(str)
    n_vorher = len(v)
    v = v[(v["format_klass"] == "ja") & v["format"].isin(["short", "long"])].copy()
    if v.empty:
        raise SystemExit("Keine short/long-Videos mit format_klass == 'ja' gefunden - Kodierung in "
                         "videos_roh.dta pruefen.")
    v["short"] = (v["format"] == "short").astype(int)
    v["rel_monat"] = relativ_periode(v["upload_ts"], pd.Timestamp(KRIEGSBEGINN), 1)
    v = v[v["rel_monat"].between(PERIODE_MIN, PERIODE_MAX)]
    print(f"[Videos] {len(v)} short/long-Videos mit format_klass == ja im Fenster "
          f"{PERIODE_MIN}..{PERIODE_MAX} (von {n_vorher}); Shorts: {int(v['short'].sum())}")
    return v


# =========================================================
# SCHRITT 2: Anteile
# =========================================================

def anteile_gepoolt(v, gruppen_spalte):
    d = v[v[gruppen_spalte].notna()]
    z = d.groupby(["rel_monat", gruppen_spalte], as_index=False).agg(
        n_videos=("short", "size"), n_short=("short", "sum"))
    z = z[z["n_videos"] >= MIN_VIDEOS_ZELLE]
    z["shorts_anteil"] = z["n_short"] / z["n_videos"] * 100
    return z.rename(columns={gruppen_spalte: "gruppe"})


def anteile_kanalmittel(v, gruppen_spalte):
    d = v[v[gruppen_spalte].notna()]
    k = d.groupby(["rel_monat", gruppen_spalte, "channel_id"], as_index=False).agg(
        n_videos=("short", "size"), n_short=("short", "sum"))
    k = k[k["n_videos"] >= MIN_VIDEOS_KANAL_MONAT]
    k["anteil_kanal"] = k["n_short"] / k["n_videos"] * 100
    z = k.groupby(["rel_monat", gruppen_spalte], as_index=False).agg(
        shorts_anteil=("anteil_kanal", "mean"), n_kanaele=("channel_id", "nunique"),
        n_videos=("n_videos", "sum"), n_short=("n_short", "sum"))
    z = z[z["n_kanaele"] >= MIN_KANAELE_ZELLE]
    return z.rename(columns={gruppen_spalte: "gruppe"})


def phasenmittel(werte):
    zeilen = []
    for phase, (a, b) in PHASEN.items():
        teil = werte[werte["rel_monat"].between(a, b)]
        zeilen.append(teil.groupby("gruppe")["shorts_anteil"].mean().rename(phase))
    return pd.DataFrame(zeilen).T


# =========================================================
# SCHRITT 3: Grafik
# =========================================================

def plotte(werte, sample_label, dateiname):
    """werte: {(kennzahl, klassifikation): DataFrame}. Spalten = Klassifikationen,
    Zeilen = Kennzahlen."""
    klassen, kennz = list(KLASSIFIKATIONEN), list(KENNZAHLEN)
    fig, achsen = plt.subplots(len(kennz), len(klassen), figsize=(6.5 * len(klassen), 9.6),
                               sharex=True, sharey=True, squeeze=False)
    alle_monate = pd.concat([w["rel_monat"] for w in werte.values()])
    x_von, x_bis = alle_monate.min(), alle_monate.max() + 1   # Punkte bei k, Periode [k, k + 1)
    for zeile, kz in enumerate(kennz):
        for sp, kl in enumerate(klassen):
            ax, cfg, w = achsen[zeile, sp], KLASSIFIKATIONEN[kl], werte[(kz, kl)]
            for gruppe, farbe in zip(cfg["gruppen"], cfg["farben"]):
                r = w[w["gruppe"] == gruppe].sort_values("rel_monat")
                if r.empty:
                    continue
                x = r["rel_monat"].to_numpy(dtype=float)
                y = r["shorts_anteil"].to_numpy(dtype=float)
                ax.scatter(x, y, s=10, color=farbe, alpha=0.3, linewidths=0, zorder=2)
                ax.plot(x, glaette(x, y), color=farbe, linewidth=2, label=gruppe, zorder=3)
            # Kriegsbeginn exakt auf dem Punkt von Monat 0 (Konvention von ereignis_position)
            ax.axvline(0, color="#52514e", linestyle="--", linewidth=1)
            ax.text(0.3, 0.98, "Kriegsbeginn", transform=ax.get_xaxis_transform(),
                    va="top", fontsize=8, color="#52514e")
            for name, datum in EREIGNISSE.items():
                xe = ereignis_position(datum)
                if not (x_von <= xe <= x_bis):
                    continue
                ax.axvline(xe, color="#8a8883", linestyle=":", linewidth=1.2, zorder=1)
                ax.text(xe + 0.3, 0.98, name, transform=ax.get_xaxis_transform(), rotation=90,
                        va="top", ha="left", fontsize=7, color="#8a8883")
            if zeile == 0:
                ax.set_title(cfg["titel"], fontsize=11)
                ax.legend(loc="upper left", frameon=False, fontsize=8)
            else:
                ax.set_xlabel("Monat relativ zum Kriegsbeginn (24.02.2022)")
            if sp == 0:
                ax.set_ylabel(KENNZAHLEN[kz])
            ax.set_ylim(bottom=0)
            ax.xaxis.set_major_locator(MultipleLocator(6))
            ax.grid(color="#e5e4e0", linewidth=0.6)
            ax.set_axisbelow(True)
            for s in ["top", "right"]:
                ax.spines[s].set_visible(False)
    fig.suptitle(f"Anteil der Shorts an allen Videos (short + long) – {sample_label}", fontsize=12)
    fig.text(0.01, 0.005,
             f"Gepoolt: Shorts / alle Videos der Gruppe (Zellen ≥ {MIN_VIDEOS_ZELLE} Videos). "
             f"Kanalmittel: ungewichtetes Mittel der Kanal-Anteile (Kanäle ≥ {MIN_VIDEOS_KANAL_MONAT} "
             f"Videos im Monat, Zellen ≥ {MIN_KANAELE_ZELLE} Kanäle). Ohne Livestreams und Videos ohne Format.",
             fontsize=7.5, color="#52514e")
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    PFAD_PLOTS.mkdir(parents=True, exist_ok=True)
    fig.savefig(PFAD_PLOTS / dateiname, dpi=150)
    plt.close(fig)
    print(f"[Plot] {PFAD_PLOTS / dateiname}")


# =========================================================
# SCHRITT 4: Methodik-Datei
# =========================================================

def schreibe_methodik(kanaele, fallzahlen, phasen_tabellen, erzeugt):
    z = [
        "# Methodik: Shorts-Anteil je Gruppe",
        "",
        "Skript: `src/youtube_code/step6_auswertung/shorts_anteil_plots.py` (Herleitung im "
        "Moduldocstring). Gruppen wie in `marktanteil_rohdaten_plots.py`.",
        "",
        "- Population: `format_klass == 1`, `format` ∈ {short, long}; Livestreams und Videos ohne "
        "Format entfallen. Kein Themenfilter.",
        f"- Monate `rel_monat` {PERIODE_MIN} bis {PERIODE_MAX} (Monat 0 beginnt am {KRIEGSBEGINN}).",
        f"- Gepoolt: n_short / n_videos je Gruppe und Monat, Zellen < {MIN_VIDEOS_ZELLE} Videos entfallen.",
        f"- Kanalmittel: ungewichtetes Mittel der Kanal-Anteile, Kanäle mit ≥ {MIN_VIDEOS_KANAL_MONAT} "
        f"Videos im Monat, Zellen < {MIN_KANAELE_ZELLE} Kanäle entfallen.",
        "- WELT: Videos mit `format_derived == 1` sind per Ausschluss als long gesetzt; OE24.TV fällt "
        "wegen `format_klass == 0` weg.",
        "- Die Kanalzusammensetzung ändert sich über die Zeit (spätere Gründungen; 2019/20 nur vor "
        "2021 gegründete Kanäle).",
        *([f"- **Kanalliste aktiv:** {len(kanaele)} Kanäle aus `KANALLISTE`."] if KANALLISTE else []),
        "",
        "## Videos je Auswertung",
        "",
        "| Sample | Klassifikation | Videos (zugeordnet) | davon Shorts |",
        "|---|---|---:|---:|",
    ]
    for (s, k), (n, ns) in fallzahlen.items():
        z.append(f"| {s} | {k} | {n} | {ns} |")
    z.append("")
    z += ["## Phasenmittel der monatlichen Shorts-Anteile (%)", "",
          "Ungewichteter Mittelwert der Monatswerte je Phase (rel_monat).", ""]
    for (s, kz, k), tab in phasen_tabellen.items():
        z.append(f"**{SAMPLES[s][0]} – {KENNZAHLEN[kz]} – {KLASSIFIKATIONEN[k]['titel']}**")
        z.append("")
        z += tabelle_md(tab.reindex(KLASSIFIKATIONEN[k]["gruppen"]))
        z.append("")
    z += [f"## Erzeugte Dateien ({len(erzeugt)})", ""] + [f"- `{d}`" for d in erzeugt]
    pfad = PFAD_PLOTS / "shorts_anteil_methodik.md"
    pfad.write_text("\n".join(z) + "\n", encoding="utf-8")
    print(f"[Methodik] {pfad}")


# =========================================================
# MAIN
# =========================================================

def main():
    if not isinstance(KANALLISTE, (list, tuple, set)) or not all(isinstance(c, str) for c in KANALLISTE):
        raise SystemExit("KANALLISTE muss eine Liste von channel_id-Strings sein (leer = alle Kanaele).")
    if PERIODE_MIN > PERIODE_MAX:
        raise SystemExit("PERIODE_MIN muss <= PERIODE_MAX sein.")
    if min(MIN_VIDEOS_ZELLE, MIN_VIDEOS_KANAL_MONAT, MIN_KANAELE_ZELLE) < 1:
        raise SystemExit("MIN_VIDEOS_ZELLE, MIN_VIDEOS_KANAL_MONAT und MIN_KANAELE_ZELLE muessen >= 1 sein.")
    for name, datum in EREIGNISSE.items():
        try:
            pd.Timestamp(datum)
        except (ValueError, TypeError):
            raise SystemExit(f"EREIGNISSE[{name!r}]: {datum!r} ist kein gueltiges Datum (Format JJJJ-MM-TT).")

    kanaele, _ = bilde_gruppen(lade_kanaele())
    if KANALLISTE:
        fehlend = sorted(set(KANALLISTE) - set(kanaele["channel_id"]))
        if fehlend:
            print(f"[Kanalliste] {len(fehlend)} channel_ids nicht in kanaele_roh: {fehlend}")
        kanaele = kanaele[kanaele["channel_id"].isin(KANALLISTE)]
        if kanaele.empty:
            raise SystemExit("KANALLISTE: keine der channel_ids kommt in kanaele_roh vor.")
        print(f"[Kanalliste] Sample auf {len(kanaele)} Kanaele eingeschraenkt.")
    videos = lade_videos().merge(kanaele[["channel_id", *KLASSIFIKATIONEN]], on="channel_id")

    erzeugt, alle, fallzahlen, phasen_tabellen = [], [], {}, {}
    for s_key, (s_label, s_filter) in SAMPLES.items():
        v_s = videos[videos["channel_id"].isin(kanaele.loc[s_filter(kanaele), "channel_id"])]
        werte = {}
        for k_key in KLASSIFIKATIONEN:
            zugeordnet = v_s[v_s[k_key].notna()]
            fallzahlen[(s_key, k_key)] = (len(zugeordnet), int(zugeordnet["short"].sum()))
            for kz, funk in [("gepoolt", anteile_gepoolt), ("kanalmittel", anteile_kanalmittel)]:
                w = funk(v_s, k_key)
                werte[(kz, k_key)] = w
                phasen_tabellen[(s_key, kz, k_key)] = phasenmittel(w)
                alle.append(w.assign(sample=s_key, kennzahl=kz, klassifikation=k_key))
        dateiname = f"shorts_anteil_{s_key}.png"
        plotte(werte, s_label, dateiname)
        erzeugt.append(dateiname)

    csv = pd.concat(alle)[["sample", "kennzahl", "klassifikation", "rel_monat", "gruppe",
                           "shorts_anteil", "n_videos", "n_short", "n_kanaele"]]
    csv.to_csv(PFAD_PLOTS / "shorts_anteil_monat.csv", index=False)
    erzeugt.append("shorts_anteil_monat.csv")
    schreibe_methodik(kanaele, fallzahlen, phasen_tabellen, erzeugt)


if __name__ == "__main__":
    main()

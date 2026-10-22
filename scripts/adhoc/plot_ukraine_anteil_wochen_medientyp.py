"""Wöchentlicher Anteil der Ukraine-Videos je Medientyp (Angebots-Stichprobe).

Liest ``data/claude_classification/angebot/video_results.csv`` (erzeugt von
``process_results.py``; ein Video pro Zeile, ``thema_krieg_ukraine`` = nach
Wörtern gewichteter Segmentanteil mit Thema Ukraine-Krieg) und plottet je
Medientyp den Anteil der Ukraine-Videos an allen Videos der Woche.

Wochen beginnen am 24.02.2022 (Kriegsbeginn = erster Tag einer Woche), d. h.
Wochengrenzen sind 24.02. + k * 7 Tage. Die erste Woche (Beginn 30.12.2021)
ist angeschnitten, weil die Daten erst am 01.01.2022 beginnen; die letzte
Woche ist ebenfalls angeschnitten (Daten enden am 30.04.2022). Beide sind im
Plot gestrichelt/blass markiert, die Fallzahl je Woche steht im unteren Panel.

Ausgaben (in ``scripts/adhoc/outputs/``):
- ``ukraine_anteil_wochen_medientyp.png``: drei Panels: (1) Anteil der Ukraine-Videos
  (Schwelle ``UKRAINE_SCHWELLE``), (2) mittlerer Themenanteil ``thema_krieg_ukraine``
  (ohne Schwelle), (3) Anzahl Videos je Woche.
- ``ukraine_anteil_wochen_medientyp.csv`` (Woche x Medientyp: n_videos, n_ukraine,
  anteil, themenanteil_mittel)

Aufruf: ``.venv/Scripts/python.exe scripts/adhoc/plot_ukraine_anteil_wochen_medientyp.py``
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# ===== KONFIGURATION =====
ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data" / "claude_classification" / "angebot" / "video_results.csv"
OUTPUT_DIR = ROOT / "scripts" / "adhoc" / "outputs"
KRIEGSBEGINN = "2022-02-24"      # erster Tag einer Woche (ISO-Datum)
UKRAINE_SCHWELLE = 0.5           # Video zählt als Ukraine-Video, wenn thema_krieg_ukraine >= Schwelle (0 < x <= 1)
MIN_VIDEOS_PRO_WOCHE = 5         # Wochen mit weniger Videos je Medientyp werden nicht gezeichnet (ganze Zahl >= 1)
# Medientyp-Code -> (Label, Farbe); Schlüssel müssen in der Spalte "medientyp" vorkommen
MEDIENTYPEN = {
    "oerr": ("Öffentlich-rechtlich", "#1f77b4"),
    "traditionell": ("Traditionell (privat/Verlage)", "#7f7f7f"),
    "alternativ_rechts": ("Alternativ-rechts", "#d62728"),
}
# ===== ENDE KONFIGURATION =====


def main():
    if not 0 < UKRAINE_SCHWELLE <= 1:
        raise SystemExit("UKRAINE_SCHWELLE muss im Intervall (0, 1] liegen.")
    if MIN_VIDEOS_PRO_WOCHE < 1:
        raise SystemExit("MIN_VIDEOS_PRO_WOCHE muss >= 1 sein.")

    df = pd.read_csv(INPUT, parse_dates=["datum_lokal"])
    fehlend = set(MEDIENTYPEN) - set(df["medientyp"].unique())
    if fehlend:
        raise SystemExit(f"Medientypen nicht in den Daten: {sorted(fehlend)}")

    start = pd.Timestamp(KRIEGSBEGINN)
    df["woche_idx"] = (df["datum_lokal"] - start).dt.days // 7   # floor: Tage vor Kriegsbeginn -> negative Wochen
    df["woche"] = start + pd.to_timedelta(df["woche_idx"] * 7, unit="D")
    df["ukraine"] = (df["thema_krieg_ukraine"] >= UKRAINE_SCHWELLE).astype(int)

    agg = (df.groupby(["woche", "medientyp"])
             .agg(n_videos=("ukraine", "size"), n_ukraine=("ukraine", "sum"),
                  themenanteil_mittel=("thema_krieg_ukraine", "mean")).reset_index())
    agg["anteil"] = agg["n_ukraine"] / agg["n_videos"]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    agg.to_csv(OUTPUT_DIR / "ukraine_anteil_wochen_medientyp.csv", index=False)

    erste_woche, letzte_woche = df["woche"].min(), df["woche"].max()
    fig, (ax, ax_m, ax_n) = plt.subplots(3, 1, figsize=(11, 10), sharex=True,
                                         gridspec_kw={"height_ratios": [3, 3, 1]})
    for typ, (label, farbe) in MEDIENTYPEN.items():
        sub = agg[(agg["medientyp"] == typ) & (agg["n_videos"] >= MIN_VIDEOS_PRO_WOCHE)]
        ax.plot(sub["woche"], sub["anteil"], marker="o", ms=4, color=farbe, label=label)
        ax_m.plot(sub["woche"], sub["themenanteil_mittel"], marker="o", ms=4, color=farbe, label=label)
        alle = agg[agg["medientyp"] == typ]
        ax_n.plot(alle["woche"], alle["n_videos"], marker="o", ms=3, color=farbe)

    for a in (ax, ax_m, ax_n):
        a.axvline(start, color="black", ls="--", lw=1)
        a.axvspan(erste_woche, erste_woche + pd.Timedelta(days=7), color="grey", alpha=0.12)
        a.axvspan(letzte_woche, letzte_woche + pd.Timedelta(days=7), color="grey", alpha=0.12)
        a.grid(alpha=0.3)
    ax.text(start, 0.02, " Kriegsbeginn", transform=ax.get_xaxis_transform(), fontsize=9, va="bottom")
    for a in (ax, ax_m):
        a.set_ylim(0, 1)
        a.yaxis.set_major_formatter(lambda y, _: f"{y:.0%}")
    ax_m.set_ylabel("Mittlerer Themenanteil Ukraine-Krieg (ohne Schwelle)")
    ax.set_ylabel(f"Anteil Ukraine-Videos (Themenanteil ≥ {UKRAINE_SCHWELLE:g})")
    ax.set_title("Anteil der Ukraine-Videos an allen Videos je Woche und Medientyp\n"
                 f"(Wochenbeginn: 24.02.; Wochen mit < {MIN_VIDEOS_PRO_WOCHE} Videos nicht gezeichnet; "
                 "graue Flächen = angeschnittene Wochen)", fontsize=11)
    ax.legend(loc="lower right")
    ax_n.set_ylabel("Anzahl Videos")
    ax_n.set_xlabel("Wochenbeginn")
    ax_n.set_xticks(sorted(df["woche"].unique()))
    ax_n.set_xticklabels([w.strftime("%d.%m.") for w in sorted(df["woche"].unique())], rotation=45)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "ukraine_anteil_wochen_medientyp.png", dpi=150)
    print(agg.pivot(index="woche", columns="medientyp", values="n_videos"))
    print(agg.pivot(index="woche", columns="medientyp", values="anteil").round(2))


if __name__ == "__main__":
    main()

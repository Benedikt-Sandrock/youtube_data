"""Wöchentlicher mittlerer Themenanteil aller Themen je Medientyp (Angebots-Stichprobe).

Liest ``data/claude_classification/angebot/video_results.csv`` (erzeugt von
``process_results.py``). Je Thema ``thema_*`` (nach Wörtern gewichteter
Segmentanteil je Video, 0-1) wird pro Woche und Medientyp der Mittelwert über
alle Videos gebildet. Ein Video kann mehrere Themen haben, die Anteile je
Video summieren sich nicht zwingend auf 1 (Segmente mit mehreren Themen).

Wochen beginnen am 24.02.2022 (Kriegsbeginn = erster Tag einer Woche); die
erste (ab 30.12.2021) und letzte Woche (ab 28.04.2022) sind angeschnitten.

Ausgaben (in ``scripts/adhoc/outputs/``):
- ``themen_wochen_medientyp_gleiche_skala.png``: ein Panel je Thema, gemeinsame
  y-Achse (0-100 %), damit sichtbar ist, welche Themen insgesamt wenig behandelt werden.
- ``themen_wochen_medientyp_freie_skala.png``: dieselben Panels mit eigener
  y-Achse je Thema (Verlauf kleiner Themen besser lesbar).
- ``themen_wochen_medientyp.csv``: Woche x Medientyp x Thema (n_videos, themenanteil_mittel).
- ``themen_ranking.csv``: mittlerer Themenanteil je Thema und Medientyp, gesamt
  sowie vor / nach Kriegsbeginn (Tabelle wird zusätzlich auf der Konsole ausgegeben).

Aufruf: ``.venv/Scripts/python.exe scripts/adhoc/plot_themen_wochen_medientyp.py``
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# ===== KONFIGURATION =====
ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data" / "claude_classification" / "angebot" / "video_results.csv"
OUTPUT_DIR = ROOT / "scripts" / "adhoc" / "outputs"
KRIEGSBEGINN = "2022-02-24"      # erster Tag einer Woche (ISO-Datum)
N_SPALTEN = 3                    # Panels je Zeile (ganze Zahl >= 1)
MIN_VIDEOS_PRO_WOCHE = 5         # Wochen mit weniger Videos je Medientyp werden nicht gezeichnet (>= 1)
# Medientyp-Code -> (Label, Farbe); Schlüssel müssen in der Spalte "medientyp" vorkommen
MEDIENTYPEN = {
    "oerr": ("Öffentlich-rechtlich", "#1f77b4"),
    "traditionell": ("Traditionell (privat/Verlage)", "#7f7f7f"),
    "alternativ_rechts": ("Alternativ-rechts", "#d62728"),
}
# ===== ENDE KONFIGURATION =====


def zeichne(agg, themen, start, erste, letzte, sharey, pfad):
    """Ein Panel je Thema, sortiert wie ``themen`` (absteigend nach Gesamt-Mittelwert)."""
    n_zeilen = -(-len(themen) // N_SPALTEN)
    fig, axes = plt.subplots(n_zeilen, N_SPALTEN, figsize=(5 * N_SPALTEN, 2.8 * n_zeilen),
                             sharex=True, sharey=sharey, squeeze=False)
    for ax, thema in zip(axes.flat, themen):
        for typ, (label, farbe) in MEDIENTYPEN.items():
            sub = agg[(agg["thema"] == thema) & (agg["medientyp"] == typ)
                      & (agg["n_videos"] >= MIN_VIDEOS_PRO_WOCHE)]
            ax.plot(sub["woche"], sub["themenanteil_mittel"], color=farbe, lw=1.5, label=label)
        ax.axvline(start, color="black", ls="--", lw=0.8)
        ax.axvspan(erste, erste + pd.Timedelta(days=7), color="grey", alpha=0.12)
        ax.axvspan(letzte, letzte + pd.Timedelta(days=7), color="grey", alpha=0.12)
        ax.set_title(thema.removeprefix("thema_").replace("_", " "), fontsize=10)
        ax.grid(alpha=0.3)
        ax.yaxis.set_major_formatter(lambda y, _: f"{y:.0%}")
        ax.tick_params(labelsize=8)
        if sharey:
            ax.set_ylim(0, 1)
    for ax in list(axes.flat)[len(themen):]:
        ax.set_visible(False)
    for ax in axes[-1]:
        ax.tick_params(axis="x", rotation=45)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(MEDIENTYPEN), bbox_to_anchor=(0.5, 1.0))
    fig.suptitle("Mittlerer Themenanteil je Woche und Medientyp "
                 f"({'gleiche' if sharey else 'freie'} y-Skala; Wochenbeginn 24.02., gestrichelt = Kriegsbeginn)",
                 y=1.03, fontsize=11)
    fig.tight_layout()
    fig.savefig(pfad, dpi=130, bbox_inches="tight")
    plt.close(fig)


def main():
    if N_SPALTEN < 1 or MIN_VIDEOS_PRO_WOCHE < 1:
        raise SystemExit("N_SPALTEN und MIN_VIDEOS_PRO_WOCHE müssen >= 1 sein.")

    df = pd.read_csv(INPUT, parse_dates=["datum_lokal"])
    fehlend = set(MEDIENTYPEN) - set(df["medientyp"].unique())
    if fehlend:
        raise SystemExit(f"Medientypen nicht in den Daten: {sorted(fehlend)}")
    themen_cols = [c for c in df.columns if c.startswith("thema_")]
    df[themen_cols] = df[themen_cols].fillna(0.0)   # Thema nicht vergeben = Anteil 0

    start = pd.Timestamp(KRIEGSBEGINN)
    df["woche"] = start + pd.to_timedelta((df["datum_lokal"] - start).dt.days // 7 * 7, unit="D")

    lang = df.melt(id_vars=["woche", "medientyp", "datum_lokal"], value_vars=themen_cols,
                   var_name="thema", value_name="anteil")
    agg = (lang.groupby(["woche", "medientyp", "thema"])["anteil"]
               .agg(n_videos="size", themenanteil_mittel="mean").reset_index())
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    agg.to_csv(OUTPUT_DIR / "themen_wochen_medientyp.csv", index=False)

    # Ranking: Mittelwert über Videos (nicht über Wochen), gesamt / vor / nach Kriegsbeginn
    lang["periode"] = (lang["datum_lokal"] >= start).map({False: "vor", True: "nach"})
    ranking = lang.pivot_table(index="thema", columns="medientyp", values="anteil", aggfunc="mean")
    ranking["gesamt"] = lang.groupby("thema")["anteil"].mean()
    for periode in ("vor", "nach"):
        ranking[f"gesamt_{periode}"] = lang[lang["periode"] == periode].groupby("thema")["anteil"].mean()
    ranking = ranking.sort_values("gesamt", ascending=False)
    ranking.to_csv(OUTPUT_DIR / "themen_ranking.csv")
    print((ranking * 100).round(1).to_string())

    themen = ranking.index.tolist()
    erste, letzte = df["woche"].min(), df["woche"].max()
    zeichne(agg, themen, start, erste, letzte, True, OUTPUT_DIR / "themen_wochen_medientyp_gleiche_skala.png")
    zeichne(agg, themen, start, erste, letzte, False, OUTPUT_DIR / "themen_wochen_medientyp_freie_skala.png")


if __name__ == "__main__":
    main()

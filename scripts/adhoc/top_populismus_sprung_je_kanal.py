"""Ad-hoc-Auswertung: Welche Kanaele haben in einzelnen Populismus-Subdimensionen
den groessten Sprung (Vorkriegs- vs. Nachkriegsmittelwert) gemacht?

Nutzt dieselbe Whitelist und dieselbe Vorkriegs/Nachkriegs-Definition wie
`frage1_populismus_bericht.py` (siehe outputs/segment_analysis/
frage1_methodik_und_stichprobe.md, Abschnitt 3b/4): post = rel_monat >= 0.

Input:
- outputs/segment_analysis/channel_video_populism.csv (Video-Ebene, alle Kanaele)
- outputs/segment_analysis/frage1_kanal_whitelist.csv (finale 279-Kanal-Whitelist)

Nur Kanaele mit mindestens MIN_VIDEOS_JE_PERIODE klassifizierten Videos SOWOHL
vor als auch nach Kriegsbeginn werden beruecksichtigt (Kanal-Fixed-Effect-
Vergleich, sonst kein within-Kanal-Sprung messbar).

Output: Konsolenausgabe, Top N je Dimension (staerkster Anstieg + staerkster
Rueckgang), keine Datei.
"""

import pandas as pd

BASE = "outputs/segment_analysis"
MIN_VIDEOS_JE_PERIODE = 3
TOP_N = 10

DIMENSIONEN = [
    "volkszentrismus",
    "antielitismus",
    "manichaeische_moralisierung",
    "emotionale_intensitaet",
    "populismus_gesamt",
]


def main():
    df = pd.read_csv(f"{BASE}/channel_video_populism.csv")
    whitelist = set(pd.read_csv(f"{BASE}/frage1_kanal_whitelist.csv")["channel_id"])
    df = df[df["channel_id"].isin(whitelist)].copy()
    df["post"] = df["rel_monat"] >= 0

    titel = df.drop_duplicates("channel_id").set_index("channel_id")["channel_title"]

    for dim in DIMENSIONEN:
        agg = (
            df.groupby(["channel_id", "post"])[dim]
            .agg(["mean", "count"])
            .unstack("post")
        )
        agg.columns = ["mean_vor", "mean_nach", "n_vor", "n_nach"]
        agg = agg.dropna()
        agg = agg[(agg["n_vor"] >= MIN_VIDEOS_JE_PERIODE) & (agg["n_nach"] >= MIN_VIDEOS_JE_PERIODE)]
        agg["sprung"] = agg["mean_nach"] - agg["mean_vor"]
        agg["channel_title"] = titel.reindex(agg.index)
        agg = agg.sort_values("sprung", ascending=False)

        print(f"\n{'=' * 70}\nDimension: {dim}  (n_kanaele mit beiden Perioden >= {MIN_VIDEOS_JE_PERIODE} Videos: {len(agg)})\n{'=' * 70}")
        print(f"-- Top {TOP_N} groesster ANSTIEG --")
        cols = ["channel_title", "mean_vor", "mean_nach", "sprung", "n_vor", "n_nach"]
        print(agg.head(TOP_N)[cols].to_string(float_format=lambda x: f"{x:.2f}"))

        print(f"\n-- Top {TOP_N} groesster RUECKGANG --")
        print(agg.tail(TOP_N)[cols].sort_values("sprung").to_string(float_format=lambda x: f"{x:.2f}"))


if __name__ == "__main__":
    main()

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

"""
Comment out files that are not supposed to be in the graph

*Legend*

First number refers to the prompt used:
1: Standard prompt
2: Standard prompt without rule to rate only statements of the creator
3: Standard prompt with "socio-cultural ideology" changed to "political ideology"

Second number refers to the model used (1= gemini-2.5-flash, 2 = gemini-2.5-flash-lite)
"""


files = {
    "Classification 1/g25_f": "downloaded_results/classification_results_1_g25_f.xlsx",
    "Classification 1/g25_f_l": "downloaded_results/classification_results_1_g25_f_l.xlsx",
    "Classification 2/g25_f": "downloaded_results/classification_results_2_g25_f.xlsx",
    "Classification 2/g25_f_l": "downloaded_results/classification_results_2_g25_f_l.xlsx",
}

dfs = []
for name, path in files.items():
    df = pd.read_excel(path)
    df = df[["video_id", "ideology_score", "populism_score"]].copy()
    df["Modell"] = name

    dfs.append(df)

df_all = pd.concat(dfs, ignore_index=True)

bins = [-1.5, -0.5, 2.4, 4.91, 5.01, 7.4, 10.1]
labels = ["-1", "0-2", "2.5-4.9", "5", "5.1-7", "7.5-10"]

df_all["ideology_range"] = pd.cut(
    df_all["ideology_score"], bins = bins, labels = labels, include_lowest=True
)

df_all["populism_range"] = pd.cut(
    df_all["populism_score"], bins = bins, labels = labels, include_lowest=True
)

category_order = ["0-2", "2.5-4.9", "5", "5.1-7", "7.5-10", "-1"]


def plot_grouped_bars(score_column, title, ylabel):
    plt.figure(figsize=(12, 6))

    # Prozente berechnen, damit man die Modelle trotz eventuell unterschiedlicher Zeilenanzahl vergleichen kann
    # Falls du absolute Zahlen willst, ersetze 'normalize=True' durch 'normalize=False' und multipliziere nicht mit 100
    counts = (
        df_all.groupby(["Modell", score_column], observed=False)
        .size()
        .reset_index(name="Anzahl")
    )

    # 2. Berechne die Prozentwerte separat für jedes Modell
    # .transform("sum") sorgt dafür, dass die Summe pro Modell stabil bleibt
    counts["Prozent"] = (
        counts["Anzahl"]
        / counts.groupby("Modell")["Anzahl"].transform("sum")
                        ) * 100

    # Plot erstellen
    sns.barplot(
        data=counts,
        x=score_column,
        y="Prozent",
        hue="Modell",
        order=category_order,
        palette="Set2",
    )

    plt.title(title, fontsize=14, pad=15)
    plt.xlabel("Reichweite (Scores)", fontsize=12)
    plt.ylabel(ylabel, fontsize=12)
    plt.ylim(0, max(counts["Prozent"]) + 5)
    plt.legend(title="Modelle")
    plt.tight_layout()
    plt.show()


# 4. Grafiken anzeigen
plot_grouped_bars(
    "ideology_range",
    "Verteilung der Ideologie-Scores nach Reichweite und Modell",
    "Anteil der Videos (%)",
)
plot_grouped_bars(
    "populism_range",
    "Verteilung der Populismus-Scores nach Reichweite und Modell",
    "Anteil der Videos (%)",
)


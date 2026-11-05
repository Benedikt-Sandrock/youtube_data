from youtube_code.config import CLAUDE, STATA_OUTPUT,KEYWORD_KLASSIFIZIERUNG

import pandas as pd
import os
from sklearn.metrics import (
    confusion_matrix, cohen_kappa_score, classification_report, precision_recall_fscore_support
)

# ============================================================================
# KONFIGURATION
# ============================================================================
THEMEN = ["krieg_ukraine", "energie"]  # Themen aus test_vorhersagen_kanal_holdout.csv (Video: Textanteil >= 0.5)
BERICHT = KEYWORD_KLASSIFIZIERUNG.parent / "bericht_precision_recall.md"  # Ausgabedatei der Gütetabellen
# ============================================================================

if os.path.exists("temp.csv"):
    df = pd.read_csv("temp.csv")
else:
    print("Loading and merging data")
    df_claude = pd.read_csv(CLAUDE / "angebot" / "video_results.csv")
    df_stata = pd.read_stata(STATA_OUTPUT / "videos_roh.dta", columns = ["video_id", "post_war", "politisch",
                                                                     "rel_russia_ukraine_war_core",
                                                                     "rel_russia_ukraine_war_cw",
                                                                     "rel_politics_general_core",
                                                                     "rel_politics_general_cw"])
    df = pd.merge(df_claude, df_stata, on ="video_id", how = "inner")
    df_channels = pd.read_excel(STATA_OUTPUT / "channels_check.xlsx")
    df_channels = df_channels[["channel_id","media_category", "sample"]]
    df = pd.merge(df, df_channels, on = "channel_id", how = "left")
    print(len(df_claude), len(df_stata), len(df))
    df.to_csv("temp.csv", index=False)

# Keyword-Klassifikatoren: Out-of-Fold-Vorhersagen aus dem Kanal-Holdout (keyword_klassifikation_segmente.py),
# NICHT videos_klassifiziert.csv: dort sind alle Videos mit LLM-Label im Training (in-sample)
seg = pd.read_csv(KEYWORD_KLASSIFIZIERUNG.parent / "test_vorhersagen_kanal_holdout.csv", encoding = "utf-8-sig")
ASPEKTE = [c.removeprefix("llm_a_") for c in seg.columns if c.startswith("llm_a_")]
LABELS = THEMEN + [f"a_{a}" for a in ASPEKTE]
woerter = pd.read_csv(CLAUDE / "angebot" / "results_segment_level.csv", usecols = ["segment_id", "n_woerter"])
# results_segment_level.csv enthält 176 Dubletten (siehe process_results.py); hier beide Dateien bereinigen
seg = pd.merge(seg.drop_duplicates("segment_id"), woerter.drop_duplicates("segment_id"), on = "segment_id",
               validate = "1:1")

# Video-Ebene: Themen wortgewichtet wie segment_weight in process_results.py,
# Aspekte = mind. ein Segment (wie krieg_aspekt_* in video_results.csv)
spalten_themen = [f"{k}_{t}" for k in ["llm", "dict", "lr"] for t in THEMEN]
spalten_aspekte = [f"{k}_a_{a}" for k in ["llm", "dict", "lr"] for a in ASPEKTE]
gewicht = seg["n_woerter"] / seg.groupby("video_id")["n_woerter"].transform("sum")
df_keyword = seg[spalten_themen].mul(gewicht, axis = 0).groupby(seg["video_id"]).sum().join(
    seg[spalten_aspekte].groupby(seg["video_id"]).max()).reset_index()
df = pd.merge(df, df_keyword, on = "video_id", how = "inner", validate = "1:1").copy()
seg = pd.merge(seg, df[["video_id", "media_category"]], on = "video_id", validate = "m:1")

# Kontrolle gegen video_results.csv: Abweichungen bei Themen stammen nur aus den dort noch enthaltenen Dubletten
abweichung = (df["llm_krieg_ukraine"] - df["thema_krieg_ukraine"]).abs()
abweichung_aspekte = sum((df[f"llm_a_{a}"] != df[f"krieg_aspekt_{a}"]).sum() for a in ASPEKTE)
print(f"Videos im Vergleich: {len(df)}; Kriegsanteil weicht bei {(abweichung > 0.001).sum()} Videos von "
      f"video_results.csv ab; Aspekt-Abweichungen: {abweichung_aspekte}")

# print(df["thema_krieg_ukraine"].describe())

df["ukraine_claude_core"] = df["llm_krieg_ukraine"] >= 0.5
df["ukraine_claude_wide"] = df["llm_krieg_ukraine"] > 0
df["ukraine_kw_core"] = df["rel_russia_ukraine_war_core"] == "ja"
df["ukraine_kw_cw"] = df["rel_russia_ukraine_war_cw"] == "ja"
df["ukraine_dict_core"] = df["dict_krieg_ukraine"] >= 0.5
df["ukraine_lr_core"] = df["lr_krieg_ukraine"] >= 0.5

gold = "ukraine_claude_core"

df_core = df.copy()
df_alt = df[df["media_category"] == 5]
df_main = df[df["media_category"].isin([1,2])]

df_dict = {
    "All channels": df_core,
    "Alternative Media": df_alt,
    "Mainstream Media": df_main
}

def evaluate_classification(df_dict):
    for name, df in df_dict.items():
        print(f"\n{20*"="}"
              f"\nAuswertung: {name}"
              f"\n{20*"="}")

        for i, col in enumerate(["ukraine_kw_core", "ukraine_kw_cw", "ukraine_dict_core", "ukraine_lr_core"], 1):
            print(f"\n--- Auswertung für Klassifikation {col} gegen {gold} ---")

            y_true = df[gold]
            y_pred = df[col]

            print("Konfusionsmatrix:")
            print("\nGold/Classification")
            print("false/false  false/true"
                  "\ntrue/false true/true")
            print(confusion_matrix(y_true, y_pred))

            print("\nKlassifikationsreport:")
            print(classification_report(y_true, y_pred))

            kappa = cohen_kappa_score(y_true, y_pred)
            print(f"Cohen's Kappa: {kappa:.3f}\n")


evaluate_classification(df_dict)


def guete_tabelle(daten):
    """Markdown-Tabelle mit Gütemaßen von Dict und LR gegen das LLM (Spalten mit Werten >= 0.5 gelten als positiv)."""
    zeilen = ["| Label | n LLM | Anteil LLM | Anteil Dict | P Dict | R Dict | F1 Dict | Kappa Dict "
              "| Anteil LR | P LR | R LR | F1 LR | Kappa LR |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for label in LABELS:
        y_true = daten[f"llm_{label}"] >= 0.5
        zelle = [label.removeprefix("a_"), str(y_true.sum()), f"{y_true.mean():.3f}"]
        for klassifikator in ["dict", "lr"]:
            y_pred = daten[f"{klassifikator}_{label}"] >= 0.5
            p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average = "binary", zero_division = 0)
            zelle += [f"{y_pred.mean():.3f}", f"{p:.2f}", f"{r:.2f}", f"{f1:.2f}",
                      f"{cohen_kappa_score(y_true, y_pred):.2f}"]
        zeilen.append("| " + " | ".join(zelle) + " |")
    return zeilen


gruppen = {"Alle Kanäle": [1, 2, 4, 5], "Alternative Medien (Kategorie 5)": [5], "Mainstream (Kategorie 1, 2)": [1, 2]}
bericht = ["# Precision und Recall der Keyword-Klassifikation gegen das LLM", "",
           "Out-of-Fold-Vorhersagen aus dem Kanal-Holdout (Jan–Apr 2022), nur Videos aus `video_results.csv`, "
           "Dubletten entfernt. Aspekte End-to-End: nur wo der Klassifikator selbst `krieg_ukraine` erkennt. "
           "Dict hat für den Aspekt `sonstiges` kein Lexikon.", "",
           "Video-Ebene: Themen positiv ab 50 % Textanteil, Aspekte positiv ab mindestens einem Segment."]
for name, kategorien in gruppen.items():
    bericht += ["", f"## {name}", "", f"### Video-Ebene (n = {df['media_category'].isin(kategorien).sum()})", "",
                *guete_tabelle(df[df["media_category"].isin(kategorien)]),
                "", f"### Segment-Ebene (n = {seg['media_category'].isin(kategorien).sum()})", "",
                *guete_tabelle(seg[seg["media_category"].isin(kategorien)])]
BERICHT.write_text("\n".join(bericht) + "\n", encoding = "utf-8")
print(f"Bericht: {BERICHT}")
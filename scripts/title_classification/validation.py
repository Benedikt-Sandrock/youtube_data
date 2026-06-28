import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, classification_report

seed_number = 41

model_label = {
    "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli": "mDeBERTa-v3",
    "sahajtomar/German_Zeroshot": "German_Zeroshot",
    "facebook/bart-large-mnli": "bart_large",
    "vicgalle/xlm-roberta-large-xnli-anli": "XLM_RoBERTa_Large"
}

df = pd.read_excel(f"results_all_models_{seed_number}.xlsx")
confidence_level = [0.6, 0.75, 0.85, 0.9]

for model, label in model_label.items():
    for level in confidence_level:
        df[f"{label}_{level}_politik_confident"] = df[f"{label}_politik_confidence"] > level

sub_df = df.drop(columns=["title", "mDeBERTa-v3_politik_confidence", "German_Zeroshot_politik_confidence",
                          "bart_large_politik_confidence", "XLM_RoBERTa_Large_politik_confidence"])

correlation = sub_df.corr()
print(correlation)


results = []
manual = "politics_manual"
sub_df_2 = sub_df.drop(columns=["politics_manual"])
model_cols = sub_df_2.columns.tolist()
# model_cols = ["mDeBERTa-v3_is_politics", "mDeBERTa-v3_politik_confident",
#              "German_Zeroshot_politik_confident", "German_Zeroshot_is_politics",
#              "bart_large_politik_confident", "bart_large_is_politics"]

for col in model_cols:
    acc = accuracy_score(df[manual], df[col])
    f1 = f1_score(df[manual], df[col])
    results.append({
        "modell": col,
        "accuracy": acc,
        "f1_score": f1
    })

performance_df = pd.DataFrame(results)
performance_df.to_excel(f"model_performance_{seed_number}.xlsx", engine = "openpyxl", index = False)
# df_auto = pd.read_json(f"classified_videos_{seed_number}.json")
# df_self = pd.read_excel(f"video_titles_sample_{seed_number}.xlsx")
# df_auto["politics_sure"] = df_auto["politik_confidence"] > 0.8
#df_auto.columns = ["title", "category", "confidence"]
# df_auto["value"] = df_auto["category"] == "Politik"
# print(len(df_auto))
# print(len(df_self))
# df_complete = pd.merge(df_auto, df_self, on = "title", how = "inner")
#
# print(len(df_complete))
# df_complete.to_excel("combined.xlsx", engine = "openpyxl", index = False)
#
# sub_df = df_complete[["is_politics", "politics_sure", "politics_manual"]]
import pandas as pd
import matplotlib.pyplot as plt

# 1. Daten aggregieren (Durchschnittswerte beider Test-Sets)
# Hier nehmen wir die Top-Kandidaten zur Übersicht
data = {
    'Modell': ['mDeBERTa-v3', 'German_Zeroshot', 'XLM_RoBERTa_Large', 'BART_Large'],
    'F1_Test_1': [0.817, 0.752, 0.812, 0.681],
    'F1_Test_2': [0.775, 0.846, 0.778, 0.744]
}

df_plot = pd.DataFrame(data)
df_plot['F1_Average'] = (df_plot['F1_Test_1'] + df_plot['F1_Test_2']) / 2

# 2. Visualisierung erstellen
plt.figure(figsize=(10, 6))
plt.bar(df_plot['Modell'], df_plot['F1_Average'], color=['skyblue', 'orange', 'lightgreen', 'salmon'])
plt.ylabel('Durchschnittlicher F1-Score')
plt.title('Modellvergleich über zwei Test-Sets hinweg')
plt.ylim(0.6, 0.9) # Fokus auf den relevanten Bereich
plt.grid(axis='y', linestyle='--', alpha=0.7)

plt.show()
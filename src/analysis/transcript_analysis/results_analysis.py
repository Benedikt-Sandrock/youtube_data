import pandas as pd
import glob
import re
from sklearn.metrics import (mean_absolute_error, root_mean_squared_error,
    accuracy_score, precision_score, recall_score, f1_score)
from scipy.stats import spearmanr
from src.config.paths import OUTPUT_GEMINI, EXTERNAL, VALIDATION

# =========================================
# PATHS AND CONFIGURATION
# =========================================
# If CONVERT is true the numerical classification is mapped to 5/6-point-scale:
# Ideology: extremely left - moderately left - neutral - moderately right - extremely right
# Populism: no populism at all - very little populism - latent populism - manifested populism - strong populism - total populism

CONVERT = True
seed_number = "42"

MAIN_FILE = EXTERNAL / f"complete_classification_{seed_number}.xlsx"
OUTPUT_PATH = OUTPUT_GEMINI / f"all_results_merged_{seed_number}.xlsx"
VALIDATION_PATH = VALIDATION / f"comparison_manual_model_{seed_number}.xlsx"
RESULTS_DIRECTORY = OUTPUT_GEMINI

ideology_bins = [-0.1, 2, 4, 6, 8, 10]
ideology_labels = ["extremely left", "moderately left", "center", "moderately right", "extremely right"]

populism_bins = [-0.1, 1, 3, 5, 7, 8, 10]
populism_labels = ["no populism", "little populism", "latent populism", "manifested populism", "strong populism", "total populism"]

# =========================================
# MAIN CODE
# =========================================
answer = input(f"Paths indicate that test sample {seed_number} is processed."
               f"\nCorrect? [Y/n] ")

if not answer.strip().lower() == "y":
    print("Aborted.")
    exit()

# df = pd.read_excel(OUTPUT_GEMINI / "classification_results_9_g25_f.xlsx")
# df = df[["video_id", "ideology_score", "populism_score"]]
# df.to_excel(OUTPUT_GEMINI / "classification_results_9_g25_f.xlsx", index = False)
#
# df = pd.read_excel(OUTPUT_GEMINI / "classification_results_8_g25_f.xlsx")
# df = df[["video_id", "ideology_score"]]
# df.to_excel(OUTPUT_GEMINI / "classification_results_8_g25_f.xlsx", index = False)


pattern_configuration = {
    "video_type_vs_all_models": (
        "reaction",
        lambda col: "video_type" in col
    ),
    "ideology_manual_vs_all_models": (
        "ideology_score_manual",
        lambda col: ("1_" in col or "3_" in col or "4_" in col or "7_" in col)
                    and "ideology_score" in col
    ),
    "ideology_all_statements_vs_all_models": (
        "ideology_score_all_statements",
        lambda col: ("2_" in col or "5_" in col or "6_" in col or "8_" in col) and "ideology_score" in col
    ),
    "populism_manual_vs_all_models": (
        "populism_score_manual",
        lambda col: ("1_" in col or "3_" in col or "4_" in col or "7_" in col)
                    and "populism_score" in col
    ),
    "populism_all_statements_vs_all_models": (
        "populism_score_all_statements",
        lambda col: ("2_" in col or "5_" in col or "6_" in col or "8_" in col) and "populism_score" in col
    ),
}


df = pd.read_excel(MAIN_FILE)


df["ideology_score_all_statements"] = df["ideology_score_all_statements"].fillna(df["ideology_score_manual"])
df["populism_score_all_statements"] = df["populism_score_all_statements"].fillna(df["populism_score_manual"])

if CONVERT:
    df["ideology_score_manual"] = pd.cut(df["ideology_score_manual"], bins = ideology_bins, labels = ideology_labels)
    df["ideology_score_all_statements"] = pd.cut(df["ideology_score_all_statements"], bins = ideology_bins, labels = ideology_labels)
    df["populism_score_manual"] = pd.cut(df["populism_score_manual"], bins = populism_bins, labels = populism_labels)
    df["populism_score_all_statements"] = pd.cut(df["populism_score_all_statements"], bins = populism_bins, labels = populism_labels)

search_scheme = "classification_results_*.xlsx"

all_files = glob.glob(search_scheme, root_dir = RESULTS_DIRECTORY)

print(f"{len(all_files)} files found.")

counter = 0
for file_name in all_files:
    match = re.search(r"classification_results_(\d+)_(.+)\.xlsx", file_name)

    if match:
        model_number = match.group(1)
        model_name = match.group(2)

        suffix = f"_{model_number}_{model_name}"
    else:
        suffix = "_pattern_not_found"

    df_model = pd.read_excel(OUTPUT_GEMINI / file_name)

    cols = df_model.columns
    if "video_type" in cols:
        df_model["video_type"] = (df_model["video_type"] == "Reaction").astype(int)

    if "ideology_score" in cols:
        df_model["political"] = (df_model["ideology_score"] != -1).astype(int)
    elif "populism_score" in cols:
        df_model["political"] = (df_model["populism_score"] != -1).astype(int)
        counter += 1
    else:
        print(f"No column to detect political content in '{file_name}'.")

    df_model = df_model.rename(columns  ={
        col: f"{col}{suffix}" for col in df_model.columns if col != "video_id"
    })

    df = pd.merge(df, df_model, on = "video_id", how = "left")

print(f"Populism used to detect political content in {counter} datasets.")
df.to_excel(OUTPUT_PATH, index = False)

print(f"Merged file saved under '{OUTPUT_PATH}'.")

political_results = []

political_cols = [col for col in df.columns if col.startswith("political_")]

for col in political_cols:
    y_true = df["political"]
    y_pred = df[col]

    accuracy = accuracy_score(y_true, y_pred)
    precision = precision_score(y_true, y_pred, zero_division = 0)
    recall = recall_score(y_true, y_pred, zero_division = 0)
    f1 = f1_score(y_true, y_pred, zero_division = 0)

    match = re.search(r"political_(\d+)_(.+)", col)
    prompt_number = match.group(1) if match else "N/A"
    model_name = match.group(2) if match else "N/A"

    political_results.append({
        "Comparison model": model_name,
        "Prompt": prompt_number,
        "Accuracy": round(accuracy, 3),
        "Precision": round(precision, 3),
        "Recall": round(recall, 3),
        "F1 score": round(f1, 3),
    })

df_political_results = pd.DataFrame(political_results)

all_pattern_results = []

large_differences = []

for pattern_name, (gold_col, filter_function) in pattern_configuration.items():
    if gold_col not in df.columns:
        print(f"Column {gold_col} not in df.")
        continue

    cols = [col for col in df.columns if filter_function(col)]

    for col in cols:
        match = re.search(r"(\d+)_(.+)", col)
        prompt_number = match.group(1) if match else "N/A"
        model_name = match.group(2) if match else "N/A"

        political_col = f"political_{prompt_number}_{model_name}"
        political_count = df[political_col].sum()

        mask = (
            (df["political"] ==1) & (df[political_col] == 1)
        )

        filtered = df.loc[mask]
        y_true = filtered[gold_col]
        y_pred = filtered[col]


        filtered[f"error_{prompt_number}_{model_name}"] = abs(y_true - y_pred)
        filtered = filtered.sort_values(by= f"error_{prompt_number}_{model_name}", ascending =False)
        print(filtered[["video_id", gold_col, col, f"error_{prompt_number}_{model_name}"]].head())
        

        mae = mean_absolute_error(y_true, y_pred)
        rmse = root_mean_squared_error(y_true, y_pred)

        corr, p_value = spearmanr(y_true, y_pred)


        all_pattern_results.append({
            "Analysis": pattern_name,
            "Comparison model": model_name,
            "Prompt": prompt_number,
            "MAE": round(mae, 2),
            "RMSE": round(rmse, 2),
            "Correlation": round(corr, 2),
            "p-value": round(p_value, 4),
            "Political Detection": political_count,
            "Sample after exclusion": len(filtered),
        })


df_results = pd.DataFrame(all_pattern_results)
df_results = pd.merge(df_results, df_political_results, on =["Comparison model", "Prompt"])
df_results.to_excel(VALIDATION_PATH, index = False)
print(f"Results saved to '{VALIDATION_PATH}'.")
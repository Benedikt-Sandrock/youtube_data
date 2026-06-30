import numpy as np
import pandas as pd
import krippendorff
from sklearn.metrics import (
    mean_absolute_error, root_mean_squared_error,
    accuracy_score, precision_score, recall_score, f1_score,
)
from scipy.stats import spearmanr

from youtube_code.config import EXTERNAL, VALIDATION
from registry.run_registry import RunRegistry

# =========================================
# CONFIGURATION
# =========================================

REGISTRY_PATH = "registry/runs_registry.csv"
CONVERT = False  # Mapping auf 5-/6-Punkte-Skala

# Statt eines fixen seed_number/MAIN_FILE: welche Runs sollen verglichen werden?
FILTER = {
    "dataset_id": "sample_vids_41",
    "dataset_version": "v1",
}
GOLD_FILE = EXTERNAL / "gold_labels_41.xlsx"  # enthält video_id, ideology_score_manual, ideology_score_all_statements, populism_score_manual, populism_score_all_statements

VALIDATION_PATH = VALIDATION / "comparison_manual_model.xlsx" if not CONVERT \
    else VALIDATION / "comparison_manual_model_converted.xlsx"

ideology_bins = [-2, -0.1, 2, 4, 6, 8, 10]
ideology_labels_numeric = [-1, 1, 2, 3, 4, 5]

populism_bins = [-2, -0.1, 1, 3, 5, 7, 8, 10]
populism_labels_numeric = [-1, 1, 2, 3, 4, 5, 6]

GOLD_COL_MAP = {
    ("ideology_score", "manual"): "ideology_score_manual",
    ("ideology_score", "all_statements"): "ideology_score_all_statements",
    ("populism_score", "manual"): "populism_score_manual",
    ("populism_score", "all_statements"): "populism_score_all_statements",
}


def krippendorff_alpha(y_true, y_pred, level_of_measurement: str) -> float | None:
    """
    Berechnet Krippendorffs Alpha für zwei 'Rater' (Gold-Label vs. LLM).
    reliability_data hat die Form (Anzahl Rater=2, Anzahl Units).
    level_of_measurement: "nominal" für Kategorien (z.B. political 0/1),
                          "ordinal" für geordnete Scores (z.B. ideology_score).
    Gibt None zurück, wenn zu wenige Werte für eine sinnvolle Berechnung vorliegen.
    """
    if len(y_true) < 2:
        return None
    reliability_data = np.array([
        pd.to_numeric(y_true, errors="coerce"),
        pd.to_numeric(y_pred, errors="coerce"),
    ])
    try:
        return round(
            krippendorff.alpha(reliability_data=reliability_data, level_of_measurement=level_of_measurement),
            3,
        )
    except (ValueError, ZeroDivisionError) as e:
        print(f"  Krippendorffs Alpha konnte nicht berechnet werden: {e}")
        return None

# =========================================
# LOAD REGISTRY + GOLD LABELS
# =========================================

registry = RunRegistry(REGISTRY_PATH)
runs = registry.get_runs(status="downloaded", **FILTER)

if runs.empty:
    raise SystemExit(f"Keine heruntergeladenen Runs für Filter {FILTER} gefunden.")

print(f"{len(runs)} Run(s) gefunden für Filter {FILTER}:")
print(runs[["run_id", "prompt_id", "model", "thinking_budget", "target_variable", "validation_basis"]])

gold_df = pd.read_excel(GOLD_FILE)
gold_df["ideology_score_all_statements"] = gold_df["ideology_score_all_statements"].fillna(
    gold_df["ideology_score_manual"]
)
gold_df["populism_score_all_statements"] = gold_df["populism_score_all_statements"].fillna(
    gold_df["populism_score_manual"]
)

df = gold_df.copy()

# =========================================
# MERGE RESULTS PER RUN
# =========================================
# Statt Regex auf Dateinamen: jede Ergebnisspalte wird mit der run_id
# als Suffix gemergt. Alle relevanten Metadaten (Modell, Prompt,
# Thinking Budget, Zielvariable, validation_basis) bleiben in der
# Registry und werden später per run_id wieder zugeordnet.

for _, run in runs.iterrows():
    run_id = run["run_id"]
    results_path = run["results_path"]

    if not results_path or pd.isna(results_path):
        print(f"  Kein results_path für {run_id}, übersprungen.")
        continue

    if str(results_path).endswith(".csv"):
        df_model = pd.read_csv(results_path)
    else:
        df_model = pd.read_excel(results_path)

    cols = df_model.columns
    if "video_type" in cols:
        df_model["video_type"] = (df_model["video_type"] == "Reaction").astype(int)

    if "ideology_score" in cols:
        df_model["political"] = (df_model["ideology_score"] != -1).astype(int)
    elif "populism_score" in cols:
        df_model["political"] = (df_model["populism_score"] != -1).astype(int)

    if CONVERT:
        for col in df_model.columns:
            if "ideology_score" in col:
                df_model[col] = pd.cut(df_model[col], bins=ideology_bins, labels=ideology_labels_numeric).astype(int)
            if "populism_score" in col:
                df_model[col] = pd.cut(df_model[col], bins=populism_bins, labels=populism_labels_numeric).astype(int)

    df_model = df_model.rename(
        columns={col: f"{col}_{run_id}" for col in df_model.columns if col != "video_id"}
    )

    df = pd.merge(df, df_model, on="video_id", how="left")

print(f"Merged dataframe shape: {df.shape}")

# =========================================
# POLITICAL DETECTION METRICS
# =========================================

political_results = []
for _, run in runs.iterrows():
    run_id = run["run_id"]
    col = f"political_{run_id}"
    if col not in df.columns:
        continue

    y_true = df["political"]
    y_pred = df[col]

    political_results.append({
        "run_id": run_id,
        "Comparison model": run["model"],
        "Prompt": run["prompt_id"],
        "Thinking budget": run["thinking_budget"],
        "Accuracy": round(accuracy_score(y_true, y_pred), 3),
        "Precision": round(precision_score(y_true, y_pred, zero_division=0), 3),
        "Recall": round(recall_score(y_true, y_pred, zero_division=0), 3),
        "F1 score": round(f1_score(y_true, y_pred, zero_division=0), 3),
        "Krippendorff alpha (political)": krippendorff_alpha(y_true, y_pred, level_of_measurement="nominal"),
    })

df_political_results = pd.DataFrame(political_results)

# =========================================
# SCORE COMPARISON (ideology / populism vs. gold)
# =========================================
# Statt der alten pattern_configuration mit Substring-Matching auf
# Prompt-Nummern wird jetzt direkt über target_variable + validation_basis
# aus der Registry gefiltert -- robust gegenüber beliebig vielen Prompts/Modellen.

all_pattern_results = []

for _, run in runs.iterrows():
    run_id = run["run_id"]
    target_variable = run["target_variable"]
    validation_basis = run["validation_basis"]

    gold_col = GOLD_COL_MAP.get((target_variable, validation_basis))
    score_col = f"{target_variable}_{run_id}"
    political_col = f"political_{run_id}"

    if gold_col is None or gold_col not in df.columns or score_col not in df.columns:
        print(f"  Übersprungen ({run_id}): gold_col={gold_col}, score_col={score_col} nicht vorhanden.")
        continue

    political_count = df[political_col].sum() if political_col in df.columns else None

    mask = (df["political"] == 1) & (df[political_col] == 1) if political_col in df.columns else df["political"] == 1
    filtered = df.loc[mask].copy()

    y_true = filtered[gold_col]
    y_pred = filtered[score_col]

    filtered[f"error_{run_id}"] = (y_true - y_pred).abs()
    filtered = filtered.sort_values(by=f"error_{run_id}", ascending=False)
    print(filtered[["video_id", gold_col, score_col, f"error_{run_id}"]].head())

    mae = mean_absolute_error(y_true, y_pred)
    rmse = root_mean_squared_error(y_true, y_pred)
    corr, p_value = spearmanr(y_true, y_pred)
    alpha = krippendorff_alpha(y_true, y_pred, level_of_measurement="ordinal")

    all_pattern_results.append({
        "run_id": run_id,
        "Target variable": target_variable,
        "Validation basis": validation_basis,
        "Comparison model": run["model"],
        "Prompt": run["prompt_id"],
        "Thinking budget": run["thinking_budget"],
        "MAE": round(mae, 2),
        "RMSE": round(rmse, 2),
        "Correlation": round(corr, 2),
        "p-value": round(p_value, 4),
        "Krippendorff alpha (score)": alpha,
        "Political Detection": political_count,
        "Sample after exclusion": len(filtered),
    })

df_results = pd.DataFrame(all_pattern_results)
df_results = pd.merge(df_results, df_political_results, on=["run_id", "Comparison model", "Prompt", "Thinking budget"])

df_results.to_excel(VALIDATION_PATH, index=False)
print(f"Results saved to '{VALIDATION_PATH}'.")
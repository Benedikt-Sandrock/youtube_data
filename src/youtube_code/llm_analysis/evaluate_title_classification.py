from pathlib import Path

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    cohen_kappa_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from youtube_code.config import LLM
from youtube_code.llm_analysis.registry.run_registry import (
    RunRegistry,
)
from youtube_code.politics_screening.screening_config import (
    REGISTRY_PATH,
    TRAINING_SAMPLE_FILE,
)


# ============================================================
# CONFIG
# ============================================================

RUN_ID = "run_0009"
MANUAL_LABEL_VERSION = "v2"

MANUAL_FILE = TRAINING_SAMPLE_FILE
OUTPUT_FILE = (
    LLM
    / "title_classification"
    / "title_classification_evaluations.xlsx"
)

LABELS = [-1, 0, 1]
LABEL_NAMES = {
    -1: "unsicher",
    0: "nicht_politisch",
    1: "politisch",
}


# ============================================================
# LOADING AND VALIDATION
# ============================================================

def load_and_merge(
    manual_file: Path,
    model_file: Path,
) -> pd.DataFrame:
    if not manual_file.exists():
        raise FileNotFoundError(
            f"Manual file not found: {manual_file}"
        )
    if not model_file.exists():
        raise FileNotFoundError(
            f"Model file not found: {model_file}"
        )

    manual = pd.read_csv(
        manual_file,
        dtype={"video_id": "string"},
    )
    model = pd.read_csv(
        model_file,
        dtype={"video_id": "string"},
    )

    required_manual = {
        "video_id",
        "politics_title",
        "politics_final_manual",
    }
    required_model = {"video_id", "politics_title"}

    missing_manual = required_manual - set(manual.columns)
    missing_model = required_model - set(model.columns)
    if missing_manual:
        raise ValueError(
            "Manual file is missing columns: "
            f"{sorted(missing_manual)}"
        )
    if missing_model:
        raise ValueError(
            "Model file is missing columns: "
            f"{sorted(missing_model)}"
        )

    manual["video_id"] = manual["video_id"].str.strip()
    model["video_id"] = model["video_id"].str.strip()

    if manual["video_id"].duplicated().any():
        raise ValueError(
            "Manual file contains duplicate video IDs."
        )
    if model["video_id"].duplicated().any():
        raise ValueError(
            "Model file contains duplicate video IDs."
        )

    manual_ids = set(manual["video_id"])
    model_ids = set(model["video_id"])
    missing_ids = sorted(manual_ids - model_ids)
    unexpected_ids = sorted(model_ids - manual_ids)
    if missing_ids or unexpected_ids:
        raise ValueError(
            "Manual and model video IDs differ. "
            f"Missing: {missing_ids[:10]}; "
            f"unexpected: {unexpected_ids[:10]}."
        )

    manual = manual.rename(
        columns={"politics_title": "politics_title_manual"}
    )
    model = model.rename(
        columns={"politics_title": "politics_title_model"}
    )

    merged = pd.merge(
        manual,
        model,
        on="video_id",
        how="inner",
        validate="one_to_one",
        suffixes=("_manual_file", "_model_file"),
    )

    for column in [
        "politics_title_manual",
        "politics_title_model",
        "politics_final_manual",
    ]:
        merged[column] = pd.to_numeric(
            merged[column],
            errors="raise",
        ).astype(int)

        invalid = ~merged[column].isin(LABELS)
        if invalid.any():
            invalid_values = sorted(
                merged.loc[invalid, column].unique().tolist()
            )
            raise ValueError(
                f"Invalid values in {column}: {invalid_values}"
            )

    return merged


# ============================================================
# METRICS
# ============================================================

def build_error_type(row: pd.Series) -> str:
    manual = row["politics_title_manual"]
    model = row["politics_title_model"]

    if manual == model:
        return "agreement"
    if manual == 1 and model == 0:
        return "critical_false_exclusion"
    if manual == 1 and model == -1:
        return "political_deferred_to_description"
    if manual == 0 and model == 1:
        return "nonpolitical_selected_directly"
    if manual == 0 and model == -1:
        return "nonpolitical_deferred_to_description"
    if manual == -1 and model == 1:
        return "manual_uncertain_model_political"
    if manual == -1 and model == 0:
        return "manual_uncertain_model_nonpolitical"
    return "other_disagreement"


def safe_binary_metric(
    metric_function,
    y_true: pd.Series,
    y_pred: pd.Series,
) -> float:
    if len(y_true) == 0:
        return 0.0
    return float(
        metric_function(
            y_true,
            y_pred,
            zero_division=0,
        )
    )


def evaluate(
    merged: pd.DataFrame,
    run_metadata: dict,
) -> dict[str, pd.DataFrame]:
    y_true = merged["politics_title_manual"]
    y_pred = merged["politics_title_model"]

    class_report = classification_report(
        y_true,
        y_pred,
        labels=LABELS,
        target_names=[LABEL_NAMES[label] for label in LABELS],
        output_dict=True,
        zero_division=0,
    )
    class_metrics = (
        pd.DataFrame(class_report)
        .transpose()
        .reset_index()
        .rename(columns={"index": "class"})
    )

    confusion = pd.DataFrame(
        confusion_matrix(
            y_true,
            y_pred,
            labels=LABELS,
        ),
        index=[
            f"manual_{LABEL_NAMES[label]}"
            for label in LABELS
        ],
        columns=[
            f"model_{LABEL_NAMES[label]}"
            for label in LABELS
        ],
    ).reset_index(names="manual_label")

    final_manual = merged["politics_final_manual"]
    resolved_final = final_manual.isin([0, 1])
    resolved_final_manual = final_manual.loc[resolved_final]
    resolved_model = y_pred.loc[resolved_final]

    final_political = final_manual.eq(1)
    model_political = y_pred.eq(1)

    # Operational title-screening rule:
    # 1 -> directly retain; -1 -> inspect description; 0 -> exclude.
    retained_after_title_stage = y_pred.ne(0)

    political_count = int(final_political.sum())
    false_exclusions = int(
        (final_political & y_pred.eq(0)).sum()
    )
    final_uncertain = final_manual.eq(-1)
    uncertain_exclusions = int(
        (final_uncertain & y_pred.eq(0)).sum()
    )

    potentially_relevant = final_manual.ne(0)
    potentially_relevant_count = int(potentially_relevant.sum())
    potentially_relevant_exclusions = int(
        (potentially_relevant & y_pred.eq(0)).sum()
    )

    resolved_true_binary = resolved_final_manual.eq(1)
    resolved_direct_binary = resolved_model.eq(1)
    resolved_retained_binary = resolved_model.ne(0)

    metadata_fields = {
        "run_id": run_metadata.get("run_id", RUN_ID),
        "prompt_id": run_metadata.get("prompt_id"),
        "prompt_version": run_metadata.get("prompt_version"),
        "model": run_metadata.get("model"),
        "thinking_budget": run_metadata.get("thinking_budget"),
        "dataset_id": run_metadata.get("dataset_id"),
        "dataset_version": run_metadata.get("dataset_version"),
        "manual_label_version": MANUAL_LABEL_VERSION,
        "manual_file": str(MANUAL_FILE.resolve()),
        "results_path": run_metadata.get("results_path"),
        "evaluated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
    }

    summary = pd.DataFrame(
        [
            {
                **metadata_fields,
                "n_videos": len(merged),
                "accuracy_3_class": accuracy_score(
                    y_true,
                    y_pred,
                ),
                "balanced_accuracy_3_class": (
                    balanced_accuracy_score(y_true, y_pred)
                ),
                "macro_f1_3_class": f1_score(
                    y_true,
                    y_pred,
                    labels=LABELS,
                    average="macro",
                    zero_division=0,
                ),
                "weighted_f1_3_class": f1_score(
                    y_true,
                    y_pred,
                    labels=LABELS,
                    average="weighted",
                    zero_division=0,
                ),
                "cohen_kappa_3_class": cohen_kappa_score(
                    y_true,
                    y_pred,
                    labels=LABELS,
                ),
                "direct_political_precision_final": safe_binary_metric(
                    precision_score,
                    resolved_true_binary,
                    resolved_direct_binary,
                ),
                "direct_political_recall_final": safe_binary_metric(
                    recall_score,
                    resolved_true_binary,
                    resolved_direct_binary,
                ),
                "direct_political_f1_final": safe_binary_metric(
                    f1_score,
                    resolved_true_binary,
                    resolved_direct_binary,
                ),
                "screening_recall_after_deferral_final": safe_binary_metric(
                    recall_score,
                    resolved_true_binary,
                    resolved_retained_binary,
                ),
                "screening_precision_after_deferral_final": safe_binary_metric(
                    precision_score,
                    resolved_true_binary,
                    resolved_retained_binary,
                ),
                "manual_final_political_count": political_count,
                "final_political_false_exclusion_count": false_exclusions,
                "final_political_false_exclusion_rate": (
                    false_exclusions / political_count
                    if political_count
                    else 0.0
                ),
                "manual_final_uncertain_count": int(
                    final_uncertain.sum()
                ),
                "final_uncertain_exclusion_count": uncertain_exclusions,
                "potentially_relevant_count": potentially_relevant_count,
                "potentially_relevant_exclusion_count": (
                    potentially_relevant_exclusions
                ),
                "potentially_relevant_retention_rate": (
                    1
                    - potentially_relevant_exclusions
                    / potentially_relevant_count
                    if potentially_relevant_count
                    else 0.0
                ),
                "direct_selection_rate": model_political.mean(),
                "description_review_rate": y_pred.eq(-1).mean(),
                "title_exclusion_rate": y_pred.eq(0).mean(),
            }
        ]
    )

    distributions = []
    for source, column in [
        ("manual", "politics_title_manual"),
        ("model", "politics_title_model"),
    ]:
        counts = (
            merged[column]
            .value_counts()
            .reindex(LABELS, fill_value=0)
        )
        for label in LABELS:
            distributions.append(
                {
                    "source": source,
                    "label": label,
                    "label_name": LABEL_NAMES[label],
                    "count": int(counts[label]),
                    "share": counts[label] / len(merged),
                }
            )
    distribution_df = pd.DataFrame(distributions)

    final_distributions = []
    for source, values in [
        ("final_manual", final_manual),
        ("title_model", y_pred),
    ]:
        counts = values.value_counts().reindex(
            LABELS,
            fill_value=0,
        )
        for label in LABELS:
            final_distributions.append(
                {
                    "source": source,
                    "label": label,
                    "label_name": LABEL_NAMES[label],
                    "count": int(counts[label]),
                    "share": counts[label] / len(merged),
                }
            )
    final_distribution_df = pd.DataFrame(final_distributions)

    detailed = merged.copy()
    detailed["error_type"] = detailed.apply(
        build_error_type,
        axis=1,
    )
    detailed["final_screening_outcome"] = "retained"
    detailed.loc[
        final_political & y_pred.eq(0),
        "final_screening_outcome",
    ] = "final_political_excluded"
    detailed.loc[
        final_uncertain & y_pred.eq(0),
        "final_screening_outcome",
    ] = "final_uncertain_excluded"
    detailed.loc[
        final_manual.eq(0) & y_pred.eq(0),
        "final_screening_outcome",
    ] = "final_nonpolitical_excluded"
    disagreements = detailed.loc[
        detailed["error_type"].ne("agreement")
    ].copy()

    priority = {
        "critical_false_exclusion": 1,
        "political_deferred_to_description": 2,
        "nonpolitical_selected_directly": 3,
        "nonpolitical_deferred_to_description": 4,
        "manual_uncertain_model_political": 5,
        "manual_uncertain_model_nonpolitical": 6,
        "other_disagreement": 7,
    }
    disagreements["error_priority"] = (
        disagreements["error_type"]
        .map(priority)
        .fillna(99)
        .astype(int)
    )
    disagreements = disagreements.sort_values(
        ["error_priority", "video_id"]
    )

    screening_errors = detailed.loc[
        detailed["final_screening_outcome"].isin(
            [
                "final_political_excluded",
                "final_uncertain_excluded",
            ]
        )
    ].copy()
    screening_errors["screening_error_priority"] = (
        screening_errors["final_screening_outcome"]
        .map(
            {
                "final_political_excluded": 1,
                "final_uncertain_excluded": 2,
            }
        )
        .astype(int)
    )
    screening_errors = screening_errors.sort_values(
        ["screening_error_priority", "video_id"]
    )

    return {
        "summary": summary,
        "class_metrics": class_metrics,
        "confusion_matrix": confusion,
        "label_distribution": distribution_df,
        "final_label_distribution": final_distribution_df,
        "disagreements": disagreements,
        "screening_errors": screening_errors,
        "all_comparisons": detailed,
    }


def save_evaluation(
    tables: dict[str, pd.DataFrame],
    output_file: Path,
    run_id: str,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    summary_new = tables["summary"].copy()

    class_metrics_new = tables["class_metrics"].copy()
    class_metrics_new.insert(0, "run_id", run_id)

    title_distribution_new = tables[
        "label_distribution"
    ].copy()
    title_distribution_new.insert(0, "run_id", run_id)

    final_distribution_new = tables[
        "final_label_distribution"
    ].copy()
    final_distribution_new.insert(0, "run_id", run_id)

    def load_existing(sheet_name: str) -> pd.DataFrame:
        if not output_file.exists():
            return pd.DataFrame()
        try:
            return pd.read_excel(
                output_file,
                sheet_name=sheet_name,
            )
        except ValueError:
            return pd.DataFrame()

    def upsert(
        existing: pd.DataFrame,
        new: pd.DataFrame,
        keys: list[str],
    ) -> pd.DataFrame:
        combined = pd.concat(
            [existing, new],
            ignore_index=True,
        )
        return combined.drop_duplicates(
            subset=keys,
            keep="last",
        ).reset_index(drop=True)

    summary_all = upsert(
        load_existing("summary_all_runs"),
        summary_new,
        ["run_id"],
    )
    class_metrics_all = upsert(
        load_existing("class_metrics_all"),
        class_metrics_new,
        ["run_id", "class"],
    )
    title_distribution_all = upsert(
        load_existing("title_distribution_all"),
        title_distribution_new,
        ["run_id", "source", "label"],
    )
    final_distribution_all = upsert(
        load_existing("final_distribution_all"),
        final_distribution_new,
        ["run_id", "source", "label"],
    )

    writer_kwargs = {
        "engine": "openpyxl",
        "mode": "a" if output_file.exists() else "w",
    }
    if output_file.exists():
        writer_kwargs["if_sheet_exists"] = "replace"

    with pd.ExcelWriter(
        output_file,
        **writer_kwargs,
    ) as writer:
        summary_all.to_excel(
            writer,
            sheet_name="summary_all_runs",
            index=False,
        )
        class_metrics_all.to_excel(
            writer,
            sheet_name="class_metrics_all",
            index=False,
        )
        title_distribution_all.to_excel(
            writer,
            sheet_name="title_distribution_all",
            index=False,
        )
        final_distribution_all.to_excel(
            writer,
            sheet_name="final_distribution_all",
            index=False,
        )

        # Run-specific sheets are replaced when the same run is evaluated
        # again, while sheets belonging to other runs remain untouched.
        tables["confusion_matrix"].to_excel(
            writer,
            sheet_name=f"confusion_{run_id}"[:31],
            index=False,
        )
        tables["disagreements"].to_excel(
            writer,
            sheet_name=f"disagreements_{run_id}"[:31],
            index=False,
        )
        tables["screening_errors"].to_excel(
            writer,
            sheet_name=f"screening_errors_{run_id}"[:31],
            index=False,
        )
        tables["all_comparisons"].to_excel(
            writer,
            sheet_name=f"comparisons_{run_id}"[:31],
            index=False,
        )


def load_run_metadata(
    registry_path: Path,
    run_id: str,
) -> tuple[dict, Path]:
    registry = RunRegistry(registry_path)
    run = registry.get_run(run_id)

    if run is None:
        raise ValueError(f"Run not found in registry: {run_id}")

    run_metadata = (
        run.to_dict()
        if hasattr(run, "to_dict")
        else dict(run)
    )
    run_metadata["run_id"] = run_id

    results_path = run_metadata.get("results_path")
    if not results_path or pd.isna(results_path):
        raise ValueError(
            f"Run {run_id} has no results_path in the registry."
        )

    model_file = Path(str(results_path))
    if not model_file.exists():
        raise FileNotFoundError(
            f"Registered result file not found: {model_file}"
        )

    return run_metadata, model_file


def main() -> None:
    run_metadata, model_file = load_run_metadata(
        registry_path=REGISTRY_PATH,
        run_id=RUN_ID,
    )
    merged = load_and_merge(
        manual_file=MANUAL_FILE,
        model_file=model_file,
    )
    tables = evaluate(
        merged,
        run_metadata=run_metadata,
    )
    save_evaluation(
        tables,
        OUTPUT_FILE,
        run_id=RUN_ID,
    )

    summary = tables["summary"].iloc[0]

    print(f"Evaluated videos: {int(summary['n_videos'])}")
    print(
        "Three-class accuracy: "
        f"{summary['accuracy_3_class']:.3f}"
    )
    print(
        "Three-class macro F1: "
        f"{summary['macro_f1_3_class']:.3f}"
    )
    print(
        "Direct political recall: "
        f"{summary['direct_political_recall_final']:.3f}"
    )
    print(
        "Final screening recall including -1 deferrals: "
        f"{summary['screening_recall_after_deferral_final']:.3f}"
    )
    print(
        "Final political false exclusions: "
        f"{int(summary['final_political_false_exclusion_count'])}"
    )
    print(
        "Final uncertain exclusions: "
        f"{int(summary['final_uncertain_exclusion_count'])}"
    )
    print(
        "Description review rate: "
        f"{summary['description_review_rate']:.3f}"
    )
    print(f"Saved evaluation to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

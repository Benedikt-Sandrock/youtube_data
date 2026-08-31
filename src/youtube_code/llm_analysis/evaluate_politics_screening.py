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
from youtube_code.politics_screening.screening_config import (
    TRAINING_SAMPLE_FILE,
)
from youtube_code.store.llm_run_store import get_run


# ============================================================
# CONFIG
# ============================================================

# "title"       -> PROMPT_32 against politics_title
# "description" -> PROMPT_33 against politics_final_manual, only for videos
#                  deferred by the title model
# "pipeline"    -> combined PROMPT_32/PROMPT_33 result against
#                  politics_final_manual for the complete manual sample
EVALUATION_MODE = "pipeline"

TITLE_RUN_ID = "run_0008"
DESCRIPTION_RUN_ID = "run_0011"

MANUAL_LABEL_VERSION = "v2"
MANUAL_FILE = TRAINING_SAMPLE_FILE

# The existing filename is retained so earlier title evaluations remain in
# the same workbook. The workbook now contains all three evaluation modes.
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
VALID_MODES = {"title", "description", "pipeline"}


# ============================================================
# LOADING AND VALIDATION
# ============================================================

def read_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() == ".csv":
        return pd.read_csv(
            path,
            dtype={"video_id": "string"},
            low_memory=False,
        )
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(
            path,
            dtype={"video_id": "string"},
        )
    raise ValueError(
        f"Unsupported file type for {path}. Use CSV or Excel."
    )


def validate_video_ids(
    data: pd.DataFrame,
    source_name: str,
) -> pd.DataFrame:
    if "video_id" not in data.columns:
        raise ValueError(f"{source_name} has no video_id column.")

    result = data.copy()
    result["video_id"] = result["video_id"].astype("string").str.strip()

    invalid = result["video_id"].isna() | result["video_id"].eq("")
    if invalid.any():
        raise ValueError(
            f"{source_name} contains {int(invalid.sum()):,} invalid "
            "video IDs."
        )
    if result["video_id"].duplicated().any():
        duplicates = (
            result.loc[
                result["video_id"].duplicated(keep=False),
                "video_id",
            ]
            .unique()
            .tolist()
        )
        raise ValueError(
            f"{source_name} contains duplicate video IDs: "
            f"{sorted(duplicates)[:10]}"
        )
    return result


def validate_label_column(
    data: pd.DataFrame,
    column: str,
    source_name: str,
) -> pd.DataFrame:
    if column not in data.columns:
        raise ValueError(
            f"{source_name} is missing label column {column!r}."
        )

    result = data.copy()
    result[column] = pd.to_numeric(
        result[column],
        errors="raise",
    )

    if result[column].isna().any():
        raise ValueError(
            f"{source_name} contains missing values in {column}."
        )

    result[column] = result[column].astype(int)
    invalid = ~result[column].isin(LABELS)
    if invalid.any():
        invalid_values = sorted(
            result.loc[invalid, column].unique().tolist()
        )
        raise ValueError(
            f"Invalid values in {source_name}.{column}: "
            f"{invalid_values}"
        )
    return result


def find_model_label_column(
    model: pd.DataFrame,
    base_column: str,
    source_name: str,
) -> str:
    candidates = [
        base_column,
        f"{base_column}_model",
    ]
    existing = [column for column in candidates if column in model.columns]

    if len(existing) != 1:
        raise ValueError(
            f"{source_name} must contain exactly one of {candidates}; "
            f"found {existing}."
        )
    return existing[0]


def load_manual_file(manual_file: Path) -> pd.DataFrame:
    manual = validate_video_ids(
        read_table(manual_file),
        "manual file",
    )

    required = {
        "politics_title",
        "politics_final_manual",
    }
    missing = required - set(manual.columns)
    if missing:
        raise ValueError(
            "Manual file is missing columns: "
            f"{sorted(missing)}"
        )

    manual = validate_label_column(
        manual,
        "politics_title",
        "manual file",
    )
    manual = validate_label_column(
        manual,
        "politics_final_manual",
        "manual file",
    )
    return manual.rename(
        columns={"politics_title": "politics_title_manual"}
    )


def load_model_file(
    model_file: Path,
    base_label_column: str,
    output_label_column: str,
    source_name: str,
) -> pd.DataFrame:
    model = validate_video_ids(
        read_table(model_file),
        source_name,
    )
    input_label_column = find_model_label_column(
        model=model,
        base_column=base_label_column,
        source_name=source_name,
    )
    model = validate_label_column(
        model,
        input_label_column,
        source_name,
    )

    keep_columns = ["video_id", input_label_column]
    return model[keep_columns].rename(
        columns={input_label_column: output_label_column}
    )


def require_exact_id_match(
    expected_ids: set[str],
    observed_ids: set[str],
    source_name: str,
) -> None:
    missing = sorted(expected_ids - observed_ids)
    unexpected = sorted(observed_ids - expected_ids)
    if missing or unexpected:
        raise ValueError(
            f"Video IDs differ for {source_name}. "
            f"Missing: {missing[:10]}; "
            f"unexpected: {unexpected[:10]}."
        )


def load_title_comparison(
    manual: pd.DataFrame,
    title_model_file: Path,
) -> pd.DataFrame:
    title_model = load_model_file(
        model_file=title_model_file,
        base_label_column="politics_title",
        output_label_column="politics_title_model",
        source_name="title model file",
    )

    require_exact_id_match(
        expected_ids=set(manual["video_id"]),
        observed_ids=set(title_model["video_id"]),
        source_name="title model file",
    )

    return manual.merge(
        title_model,
        on="video_id",
        how="inner",
        validate="one_to_one",
    )


def load_description_comparison(
    title_comparison: pd.DataFrame,
    description_model_file: Path,
) -> pd.DataFrame:
    description_model = load_model_file(
        model_file=description_model_file,
        base_label_column="politics_title_desc",
        output_label_column="politics_title_desc_model",
        source_name="description model file",
    )

    expected = title_comparison.loc[
        title_comparison["politics_title_model"].eq(-1)
    ].copy()

    if expected.empty:
        raise ValueError(
            "The title model deferred no videos. There is no description "
            "subset to evaluate."
        )

    require_exact_id_match(
        expected_ids=set(expected["video_id"]),
        observed_ids=set(description_model["video_id"]),
        source_name="description model file",
    )

    return expected.merge(
        description_model,
        on="video_id",
        how="inner",
        validate="one_to_one",
    )


def build_evaluation_data(
    evaluation_mode: str,
    manual_file: Path,
    title_model_file: Path,
    description_model_file: Path | None = None,
) -> pd.DataFrame:
    if evaluation_mode not in VALID_MODES:
        raise ValueError(
            f"EVALUATION_MODE must be one of {sorted(VALID_MODES)}."
        )

    manual = load_manual_file(manual_file)
    title_comparison = load_title_comparison(
        manual=manual,
        title_model_file=title_model_file,
    )

    if evaluation_mode == "title":
        result = title_comparison.copy()
        result["manual_label"] = result["politics_title_manual"]
        result["model_label"] = result["politics_title_model"]
        return result

    if description_model_file is None:
        raise ValueError(
            f"{evaluation_mode} evaluation requires a description run."
        )

    description_comparison = load_description_comparison(
        title_comparison=title_comparison,
        description_model_file=description_model_file,
    )

    if evaluation_mode == "description":
        result = description_comparison.copy()
        result["manual_label"] = result["politics_final_manual"]
        result["model_label"] = result["politics_title_desc_model"]
        return result

    # Complete two-stage pipeline:
    # title 0/1 is final; only title -1 is replaced by the description label.
    description_labels = description_comparison[
        ["video_id", "politics_title_desc_model"]
    ]
    result = title_comparison.merge(
        description_labels,
        on="video_id",
        how="left",
        validate="one_to_one",
    )

    deferred = result["politics_title_model"].eq(-1)
    missing_description = (
        deferred & result["politics_title_desc_model"].isna()
    )
    unexpected_description = (
        ~deferred & result["politics_title_desc_model"].notna()
    )
    if missing_description.any() or unexpected_description.any():
        raise RuntimeError(
            "Description results could not be assigned exactly to the "
            "title-deferred videos."
        )

    result["politics_pipeline_model"] = result[
        "politics_title_model"
    ].copy()
    result.loc[
        deferred,
        "politics_pipeline_model",
    ] = result.loc[
        deferred,
        "politics_title_desc_model",
    ].astype(int)
    result["politics_pipeline_model"] = result[
        "politics_pipeline_model"
    ].astype(int)
    result["manual_label"] = result["politics_final_manual"]
    result["model_label"] = result["politics_pipeline_model"]
    return result


# ============================================================
# METRICS
# ============================================================

def build_error_type(row: pd.Series) -> str:
    manual = row["manual_label"]
    model = row["model_label"]

    if manual == model:
        return "agreement"
    if manual == 1 and model == 0:
        return "critical_false_exclusion"
    if manual == 1 and model == -1:
        return "political_retained_as_uncertain"
    if manual == 0 and model == 1:
        return "nonpolitical_selected"
    if manual == 0 and model == -1:
        return "nonpolitical_retained_as_uncertain"
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
    comparison: pd.DataFrame,
    evaluation_metadata: dict,
) -> dict[str, pd.DataFrame]:
    y_true = comparison["manual_label"]
    y_pred = comparison["model_label"]

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
    ).reset_index(names="manual_label_name")

    resolved_manual = y_true.isin([0, 1])
    resolved_true_binary = y_true.loc[resolved_manual].eq(1)
    resolved_model = y_pred.loc[resolved_manual]
    resolved_direct_binary = resolved_model.eq(1)
    resolved_retained_binary = resolved_model.ne(0)

    final_political = y_true.eq(1)
    final_uncertain = y_true.eq(-1)
    potentially_relevant = y_true.ne(0)

    political_count = int(final_political.sum())
    false_exclusions = int(
        (final_political & y_pred.eq(0)).sum()
    )
    uncertain_exclusions = int(
        (final_uncertain & y_pred.eq(0)).sum()
    )
    potentially_relevant_count = int(potentially_relevant.sum())
    potentially_relevant_exclusions = int(
        (potentially_relevant & y_pred.eq(0)).sum()
    )

    summary = pd.DataFrame(
        [
            {
                **evaluation_metadata,
                "n_videos": len(comparison),
                "accuracy_3_class": accuracy_score(y_true, y_pred),
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
                "screening_recall_including_uncertain": safe_binary_metric(
                    recall_score,
                    resolved_true_binary,
                    resolved_retained_binary,
                ),
                "screening_precision_including_uncertain": safe_binary_metric(
                    precision_score,
                    resolved_true_binary,
                    resolved_retained_binary,
                ),
                "manual_political_count": political_count,
                "political_false_exclusion_count": false_exclusions,
                "political_false_exclusion_rate": (
                    false_exclusions / political_count
                    if political_count
                    else 0.0
                ),
                "manual_uncertain_count": int(final_uncertain.sum()),
                "uncertain_exclusion_count": uncertain_exclusions,
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
                "model_political_rate": y_pred.eq(1).mean(),
                "model_uncertain_rate": y_pred.eq(-1).mean(),
                "model_exclusion_rate": y_pred.eq(0).mean(),
            }
        ]
    )

    distributions = []
    for source, values in [
        ("manual", y_true),
        ("model", y_pred),
    ]:
        counts = values.value_counts().reindex(
            LABELS,
            fill_value=0,
        )
        for label in LABELS:
            distributions.append(
                {
                    "source": source,
                    "label": label,
                    "label_name": LABEL_NAMES[label],
                    "count": int(counts[label]),
                    "share": counts[label] / len(comparison),
                }
            )
    distribution_df = pd.DataFrame(distributions)

    detailed = comparison.copy()
    detailed["error_type"] = detailed.apply(
        build_error_type,
        axis=1,
    )
    detailed["screening_outcome"] = "retained"
    detailed.loc[
        final_political & y_pred.eq(0),
        "screening_outcome",
    ] = "political_excluded"
    detailed.loc[
        final_uncertain & y_pred.eq(0),
        "screening_outcome",
    ] = "uncertain_excluded"
    detailed.loc[
        y_true.eq(0) & y_pred.eq(0),
        "screening_outcome",
    ] = "nonpolitical_excluded"

    disagreements = detailed.loc[
        detailed["error_type"].ne("agreement")
    ].copy()
    priority = {
        "critical_false_exclusion": 1,
        "political_retained_as_uncertain": 2,
        "nonpolitical_selected": 3,
        "nonpolitical_retained_as_uncertain": 4,
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
        detailed["screening_outcome"].isin(
            ["political_excluded", "uncertain_excluded"]
        )
    ].copy()
    screening_errors["screening_error_priority"] = (
        screening_errors["screening_outcome"]
        .map(
            {
                "political_excluded": 1,
                "uncertain_excluded": 2,
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
        "disagreements": disagreements,
        "screening_errors": screening_errors,
        "all_comparisons": detailed,
    }


# ============================================================
# REGISTRY AND METADATA
# ============================================================

def load_run_metadata(
    source: str,
    run_id: str,
) -> tuple[dict, Path]:
    run = get_run(source, run_id)

    if run is None:
        raise ValueError(f"Run not found in registry: {run_id}")

    metadata = (
        run.to_dict()
        if hasattr(run, "to_dict")
        else dict(run)
    )
    metadata["run_id"] = run_id

    results_path = metadata.get("results_path")
    if not results_path or pd.isna(results_path):
        raise ValueError(
            f"Run {run_id} has no results_path in the registry."
        )

    model_file = Path(str(results_path))
    if not model_file.exists():
        raise FileNotFoundError(
            f"Registered result file not found: {model_file}"
        )
    return metadata, model_file


def build_evaluation_metadata(
    evaluation_mode: str,
    title_metadata: dict,
    description_metadata: dict | None,
    manual_file: Path,
) -> dict:
    title_run_id = title_metadata["run_id"]
    description_run_id = (
        description_metadata["run_id"]
        if description_metadata is not None
        else None
    )

    if evaluation_mode == "title":
        evaluation_key = f"title:{title_run_id}"
        primary_metadata = title_metadata
    elif evaluation_mode == "description":
        evaluation_key = f"description:{description_run_id}"
        primary_metadata = description_metadata
    else:
        evaluation_key = (
            f"pipeline:{title_run_id}+{description_run_id}"
        )
        primary_metadata = description_metadata

    return {
        "evaluation_key": evaluation_key,
        "evaluation_mode": evaluation_mode,
        "run_id": (
            primary_metadata.get("run_id")
            if primary_metadata is not None
            else None
        ),
        "title_run_id": title_run_id,
        "description_run_id": description_run_id,
        "prompt_id": (
            primary_metadata.get("prompt_id")
            if primary_metadata is not None
            else None
        ),
        "title_prompt_id": title_metadata.get("prompt_id"),
        "description_prompt_id": (
            description_metadata.get("prompt_id")
            if description_metadata is not None
            else None
        ),
        "model": (
            primary_metadata.get("model")
            if primary_metadata is not None
            else None
        ),
        "thinking_budget": (
            primary_metadata.get("thinking_budget")
            if primary_metadata is not None
            else None
        ),
        "dataset_id": title_metadata.get("dataset_id"),
        "dataset_version": title_metadata.get("dataset_version"),
        "manual_label_version": MANUAL_LABEL_VERSION,
        "manual_file": str(manual_file.resolve()),
        "title_results_path": title_metadata.get("results_path"),
        "description_results_path": (
            description_metadata.get("results_path")
            if description_metadata is not None
            else None
        ),
        "evaluated_at_utc": pd.Timestamp.now(
            tz="UTC"
        ).isoformat(),
    }


# ============================================================
# EXCEL OUTPUT
# ============================================================

def migrate_evaluation_key(
    existing: pd.DataFrame,
    default_mode: str = "title",
) -> pd.DataFrame:
    if existing.empty or "evaluation_key" in existing.columns:
        return existing

    migrated = existing.copy()
    if "run_id" in migrated.columns:
        migrated["evaluation_mode"] = default_mode
        migrated["evaluation_key"] = (
            default_mode + ":" + migrated["run_id"].astype(str)
        )
        migrated["title_run_id"] = migrated["run_id"]
        migrated["description_run_id"] = pd.NA
    return migrated


def save_evaluation(
    tables: dict[str, pd.DataFrame],
    output_file: Path,
    evaluation_key: str,
    sheet_tag: str,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)

    summary_new = tables["summary"].copy()

    class_metrics_new = tables["class_metrics"].copy()
    class_metrics_new.insert(0, "evaluation_key", evaluation_key)

    distribution_new = tables["label_distribution"].copy()
    distribution_new.insert(0, "evaluation_key", evaluation_key)

    def load_existing(
        sheet_name: str,
        fallback_sheet: str | None = None,
    ) -> pd.DataFrame:
        if not output_file.exists():
            return pd.DataFrame()
        for candidate in [sheet_name, fallback_sheet]:
            if candidate is None:
                continue
            try:
                return pd.read_excel(
                    output_file,
                    sheet_name=candidate,
                )
            except ValueError:
                continue
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

    summary_existing = migrate_evaluation_key(
        load_existing("summary_all_runs")
    )
    class_existing = migrate_evaluation_key(
        load_existing("class_metrics_all")
    )
    distribution_existing = migrate_evaluation_key(
        load_existing(
            "label_distribution_all",
            fallback_sheet="title_distribution_all",
        )
    )

    summary_all = upsert(
        summary_existing,
        summary_new,
        ["evaluation_key"],
    )
    class_metrics_all = upsert(
        class_existing,
        class_metrics_new,
        ["evaluation_key", "class"],
    )
    distribution_all = upsert(
        distribution_existing,
        distribution_new,
        ["evaluation_key", "source", "label"],
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
        distribution_all.to_excel(
            writer,
            sheet_name="label_distribution_all",
            index=False,
        )

        tables["confusion_matrix"].to_excel(
            writer,
            sheet_name=f"conf_{sheet_tag}"[:31],
            index=False,
        )
        tables["disagreements"].to_excel(
            writer,
            sheet_name=f"disagree_{sheet_tag}"[:31],
            index=False,
        )
        tables["screening_errors"].to_excel(
            writer,
            sheet_name=f"errors_{sheet_tag}"[:31],
            index=False,
        )
        tables["all_comparisons"].to_excel(
            writer,
            sheet_name=f"compare_{sheet_tag}"[:31],
            index=False,
        )


def build_sheet_tag(
    evaluation_mode: str,
    title_run_id: str,
    description_run_id: str | None,
) -> str:
    title_short = title_run_id.removeprefix("run_")
    if evaluation_mode == "title":
        return f"title_{title_short}"

    if description_run_id is None:
        raise ValueError(
            f"{evaluation_mode} evaluation requires DESCRIPTION_RUN_ID."
        )
    description_short = description_run_id.removeprefix("run_")
    if evaluation_mode == "description":
        return f"desc_{description_short}"
    return f"pipe_{title_short}_{description_short}"


def print_summary(summary: pd.Series) -> None:
    print(f"Evaluation mode: {summary['evaluation_mode']}")
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
        "Screening recall including -1: "
        f"{summary['screening_recall_including_uncertain']:.3f}"
    )
    print(
        "Political false exclusions: "
        f"{int(summary['political_false_exclusion_count'])}"
    )
    print(
        "Uncertain exclusions: "
        f"{int(summary['uncertain_exclusion_count'])}"
    )
    print(
        "Model uncertainty rate: "
        f"{summary['model_uncertain_rate']:.3f}"
    )


def main() -> None:
    if EVALUATION_MODE not in VALID_MODES:
        raise ValueError(
            f"EVALUATION_MODE must be one of {sorted(VALID_MODES)}."
        )

    title_metadata, title_model_file = load_run_metadata(
        source="screening_active",
        run_id=TITLE_RUN_ID,
    )

    description_metadata = None
    description_model_file = None
    if EVALUATION_MODE in {"description", "pipeline"}:
        description_metadata, description_model_file = load_run_metadata(
            source="screening_active",
            run_id=DESCRIPTION_RUN_ID,
        )

    comparison = build_evaluation_data(
        evaluation_mode=EVALUATION_MODE,
        manual_file=MANUAL_FILE,
        title_model_file=title_model_file,
        description_model_file=description_model_file,
    )
    evaluation_metadata = build_evaluation_metadata(
        evaluation_mode=EVALUATION_MODE,
        title_metadata=title_metadata,
        description_metadata=description_metadata,
        manual_file=MANUAL_FILE,
    )
    tables = evaluate(
        comparison=comparison,
        evaluation_metadata=evaluation_metadata,
    )

    sheet_tag = build_sheet_tag(
        evaluation_mode=EVALUATION_MODE,
        title_run_id=TITLE_RUN_ID,
        description_run_id=(
            DESCRIPTION_RUN_ID
            if EVALUATION_MODE in {"description", "pipeline"}
            else None
        ),
    )
    save_evaluation(
        tables=tables,
        output_file=OUTPUT_FILE,
        evaluation_key=evaluation_metadata["evaluation_key"],
        sheet_tag=sheet_tag,
    )

    print_summary(tables["summary"].iloc[0])
    print(f"Saved evaluation to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

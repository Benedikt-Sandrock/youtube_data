import pandas as pd
from pathlib import Path

from youtube_code.config import SAMPLES
from youtube_code.politics_screening.screening_config import OUTPUT_DIR


MANUAL_FILE = (
    SAMPLES
    / "russia"
    / "description_training_sample_41.csv"
)

TITLE_RESULT_FILE = (
    OUTPUT_DIR
    / "run_0009.csv"
)

DESCRIPTION_TEST_FILE = (
    SAMPLES
    / "russia"
    / "description_validation_sample_41.csv"
)


manual = pd.read_csv(
    MANUAL_FILE,
    dtype={"video_id": "string"},
)

title_results = pd.read_csv(
    TITLE_RESULT_FILE,
    dtype={"video_id": "string"},
)

# Falls das Ergebnis noch politics_title heißt:
title_results = title_results.rename(
    columns={"politics_title": "politics_title_model"}
)

required_manual = {
    "video_id",
    "title",
    "description",
    "politics_final_manual",
}

missing = required_manual - set(manual.columns)
if missing:
    raise ValueError(
        f"Missing manual columns: {sorted(missing)}"
    )

if "politics_title_model" not in title_results.columns:
    raise ValueError(
        "Title result has no politics_title_model column."
    )

merged = manual.merge(
    title_results[
        ["video_id", "politics_title_model"]
    ],
    on="video_id",
    how="inner",
    validate="one_to_one",
)

description_sample = merged.loc[
    merged["politics_title_model"].eq(-1),
    [
        "video_id",
        "title",
        "description",
        "politics_title_model",
        "politics_final_manual",
    ],
].copy()

description_sample.to_csv(
    DESCRIPTION_TEST_FILE,
    index=False,
    encoding="utf-8-sig",
)

print(
    f"{len(description_sample)} videos require "
    "description classification."
)
print(
    description_sample["politics_final_manual"]
    .value_counts(dropna=False)
    .sort_index()
)
print(f"Saved to: {DESCRIPTION_TEST_FILE}")
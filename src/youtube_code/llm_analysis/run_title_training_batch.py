from youtube_code.llm_analysis.prompts import (
    prompts_title_classification,
)
from youtube_code.llm_analysis.submit_batch_jobs import (
    run_all_prompts,
)
from youtube_code.politics_screening.screening_config import (
    BATCH_INPUT_DIR,
    GROUPING_SEED,
    MANIFEST_DIR,
    TITLES_PER_REQUEST,
    TRAINING_SAMPLE_FILE,
    DESCRIPTION_VALIDATION_SAMPLE_FILE,
    DESCRIPTIONS_PER_REQUEST
)


PROMPT_KEY = "PROMPT_33"
MODEL_NAME = "gemini_25_flash"

# Keep this True until the generated JSONL and manifest have been checked.
DRY_RUN = False


def main():
    if PROMPT_KEY not in prompts_title_classification:
        raise KeyError(
            f"{PROMPT_KEY} is missing from "
            "prompts_title_classification."
        )

    if not TRAINING_SAMPLE_FILE.exists():
        raise FileNotFoundError(
            f"Training sample not found: {TRAINING_SAMPLE_FILE}"
        )

    selected_prompts = {
        PROMPT_KEY: prompts_title_classification[PROMPT_KEY]
    }

    run_all_prompts(
        csv_path=DESCRIPTION_VALIDATION_SAMPLE_FILE,
        prompt_keys=["PROMPT_33"],
        prompts=selected_prompts,
        dataset_id=DESCRIPTION_VALIDATION_SAMPLE_FILE.stem,
        dataset_version="v1",
        target_variable="politics_title_desc",
        input_mode="title_description",
        validation_basis="manual",
        model_name="gemini_25_flash",
        thinking_budget=0,
        prompt_version="v1",
        items_per_request=5,
        grouping_seed=42,
        batch_input_dir=BATCH_INPUT_DIR,
        manifest_dir=MANIFEST_DIR,
        max_description_chars=5_000,
        dry_run=False,
    )


if __name__ == "__main__":
    main()

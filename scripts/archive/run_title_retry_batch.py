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
)

from pathlib import Path
RETRY_INPUT_FILE = Path(
    r"/outputs/llm/title_classification/run_0003_retry.csv"
)

PROMPT_KEY = "PROMPT_31"
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
        csv_path=RETRY_INPUT_FILE,
        prompt_keys=[PROMPT_KEY],
        prompts=selected_prompts,
        dataset_id="run_0003_retry",
        dataset_version="v1",
        target_variable="politics_title",
        input_mode="title",
        validation_basis="manual",
        model_name=MODEL_NAME,
        thinking_budget=0,
        prompt_version="v1",
        items_per_request=10,
        grouping_seed=GROUPING_SEED,
        batch_input_dir=BATCH_INPUT_DIR,
        manifest_dir=MANIFEST_DIR,
        dry_run=False,
    )


if __name__ == "__main__":
    main()

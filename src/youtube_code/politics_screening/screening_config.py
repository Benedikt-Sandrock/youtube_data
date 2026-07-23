from youtube_code.config import SAMPLES, EXPLORATION
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

SCREENING_DIR = SAMPLES / "russia"

TRAINING_SAMPLE_FILE = SCREENING_DIR / "description_training_sample_42.csv"

DESCRIPTIONS_FILE = SCREENING_DIR / "videos_wo_shorts_description.jsonl"

STATE_FILE = (SCREENING_DIR / "politics_screening_state.csv")


BATCH_DIR = SCREENING_DIR / "batches"
BATCH_INPUT_DIR = BATCH_DIR / "inputs"
MANIFEST_DIR = BATCH_DIR / "manifests"
RESULTS_DIR = SCREENING_DIR / "results"
OUTPUT_DIR = SCREENING_DIR / "output"
REGISTRY_PATH = PROJECT_ROOT / "llm_analysis" / "registry" / "runs_registry.csv"

REFERENCE_DATE = "2022-02-24T00:00:00Z"
WINDOW_MONTHS = 3

TARGET_POLITICAL_VIDEOS = 20
INITIAL_BATCH_SIZE_PER_CHANNEL = 10
MAX_BATCH_SIZE_PER_CHANNEL = 30
TITLES_PER_REQUEST = 10
GROUPING_SEED = 42
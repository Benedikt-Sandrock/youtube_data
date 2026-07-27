from pathlib import Path

from youtube_code.config import SAMPLES, LLM


PROJECT_ROOT = Path(__file__).parent.parent

SCREENING_DIR = SAMPLES / "russia"
TRAINING_SAMPLE_FILE = SCREENING_DIR / "description_training_sample_41.csv"

MAIN_VIDEO_FILE = SCREENING_DIR / "videos_wo_shorts_description.jsonl"
KEYWORD_VIDEOS_FILE = SCREENING_DIR / "keyword_videos_50k_channels.json"

STATE_FILE = SCREENING_DIR / "politics_screening_state.csv"
EXCLUDED_CHANNELS_FILE = SCREENING_DIR / "channels_without_keyword_video.csv"

REFERENCE_DATE = "2022-02-24T00:00:00Z"
WINDOW_MONTHS = 3

# Pro Kanal und Einmonatsperiode werden 10 Transkripte angestrebt.
# Zwei weitere politische Videos dienen als Ersatz, falls kein oder nur ein
# unbrauchbares Transkript verfügbar ist.
TARGET_POLITICAL_PER_PERIOD = 10
TARGET_WITH_BUFFER_PER_PERIOD = 12

# Keyword-Kanäle
EXCLUDE_CHANNELS_WITHOUT_KEYWORD_VIDEO = True

# "channel_window": mindestens ein Keyword-Video im individuellen
#                   Drei-Monats-Fenster des Kanals.
# "entire_dataset": mindestens ein Keyword-Video irgendwo im Datensatz.
KEYWORD_ACTIVITY_SCOPE = "entire_dataset"


DESCRIPTION_VALIDATION_SAMPLE_FILE = SCREENING_DIR / "description_validation_sample_41.csv"
DESCRIPTIONS_PER_REQUEST = 5
MAX_DESCRIPTION_CHARS = 5000

BATCH_DIR = SCREENING_DIR / "batches"
SCREENING_ROUND_DIR = BATCH_DIR / "screening_rounds"
SCREENING_ROUND_SUMMARY_DIR = BATCH_DIR / "screening_round_summaries"


BATCH_INPUT_DIR = BATCH_DIR / "inputs"
MANIFEST_DIR = BATCH_DIR / "manifests"
RESULTS_DIR = SCREENING_DIR / "results"
OUTPUT_DIR = LLM / "title_classification"
REGISTRY_PATH = PROJECT_ROOT / "llm_analysis" / "registry" / "runs_registry.csv"


# Das Rundenskript wird Kandidaten adaptiv nachziehen. Diese Werte begrenzen
# nur die Anzahl neuer Kandidaten je Kanal und Periode in einer Runde.
MIN_CANDIDATES_PER_PERIOD = 5
INITIAL_CANDIDATES_PER_PERIOD = 15
MAX_CANDIDATES_PER_PERIOD_PER_ROUND = 30

POLITICAL_RATE_FLOOR = 0.1
ROUND_SAFETY_FACTOR = 1.2

MAX_BATCH_SIZE_PER_CHANNEL = 30
TITLES_PER_REQUEST = 10
GROUPING_SEED = 42

SELECTION_SEED = 42

READ_CHUNK_SIZE = 50_000

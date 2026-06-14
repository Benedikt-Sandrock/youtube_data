from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Data

DATA = ROOT / "data"
DATA_RAW = DATA / "raw"
CHANNEL_LISTS = DATA / "channel_lists"
TRANSCRIPTS = DATA / "transcripts"
SAMPLES = DATA / "samples"

# Outputs

OUTPUTS = ROOT / "outputs"
GEMINI_RESULTS = OUTPUTS / "gemini_results"
VALIDATION = OUTPUTS / "validation"
REPORTS = OUTPUTS / "reports"
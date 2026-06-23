from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# Data

DATA = ROOT / "data"

RAW = DATA / "raw"
CHANNEL_LISTS = DATA / "channel_lists"
TRANSCRIPTS = DATA / "transcripts"
SAMPLES = DATA / "samples"
EXPLORATION = DATA/ "exploration"
EXTERNAL = DATA / "external"

# Outputs

OUTPUTS = ROOT / "outputs"
LLM = OUTPUTS / "llm"

OUTPUT_GEMINI = LLM / "gemini"
VALIDATION = OUTPUTS / "validation"
REPORTS = OUTPUTS / "reports"
GRAPHS = OUTPUTS / "graphs"
ACTIVITY = OUTPUTS / "activity_over_time"


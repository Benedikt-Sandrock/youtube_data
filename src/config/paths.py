from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Data

DATA = ROOT / "data"

RAW = DATA / "raw"
CHANNEL_LISTS = DATA / "channel_lists"
TRANSCRIPTS = DATA / "transcripts"
SAMPLES = DATA / "samples"
EXPLORATION = DATA/ "exploration"

# Outputs

OUTPUTS = ROOT / "outputs"
LLM = OUTPUTS / "llm"

GEMINI = LLM / "gemini"
VALIDATION = OUTPUTS / "validation"
REPORTS = OUTPUTS / "reports"


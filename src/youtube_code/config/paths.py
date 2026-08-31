from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# Data

DATA = ROOT / "data"

RAW = DATA / "raw"
STORE = DATA / "store"
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

SRC = ROOT / "src" / "youtube_code"
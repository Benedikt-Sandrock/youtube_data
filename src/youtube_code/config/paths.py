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
# Ergebnisse der Arbeitspakete aus .claude/plans/masterarbeit_strategie.md,
# je AP ein Unterordner (z. B. MASTERARBEIT_OUTPUTS / "ap1_selektion")
MASTERARBEIT_OUTPUTS = OUTPUTS / "masterarbeit"

ADHOC_OUTPUT = ROOT / "scripts" / "adhoc" / "output"
MASTERARBEIT_SCRIPTS = ROOT / "scripts" / "masterarbeit"

SRC = ROOT / "src" / "youtube_code"
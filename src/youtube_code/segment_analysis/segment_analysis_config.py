from youtube_code.config import SAMPLES



SAMPLE_DIR = SAMPLES / "russia"
CLASSIFICATION_DIR = SAMPLE_DIR / "classification"

BATCH_INPUT_DIR = CLASSIFICATION_DIR / "inputs"
MANIFEST_DIR = CLASSIFICATION_DIR / "manifests"

# source-Wert in der zentralen LLM-Run-Registry (data/raw/llm_runs.sqlite,
# siehe youtube_code.utils.llm_run_store). Ersetzt die fruehere
# REGISTRY_PATH-Konstante (eigene CSV-Datei je Quelle) seit Phase 4b der
# Restrukturierung - alle Call-Sites filtern jetzt ueber diesen source-Wert
# statt einen eigenen Dateipfad zu oeffnen.
LLM_RUN_SOURCE = "segment_analysis_active"

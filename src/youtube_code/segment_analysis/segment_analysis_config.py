from youtube_code.config import SAMPLES, ROOT



SAMPLE_DIR = SAMPLES / "russia"
CLASSIFICATION_DIR = SAMPLE_DIR / "classification"

BATCH_INPUT_DIR = CLASSIFICATION_DIR / "inputs"
MANIFEST_DIR = CLASSIFICATION_DIR / "manifests"
REGISTRY_PATH = ROOT / "llm_analysis" / "registry" / "runs_registry.csv"

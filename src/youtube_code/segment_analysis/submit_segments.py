"""
Segment-Klassifikation: Batch-Jobs absenden.

Eigenstaendig neben der Politics-Screening-Pipeline. Geteilt wird nur
die Registry-Datei.

Unterschiede zur bestehenden Transkript-Pipeline:
  - Identitaet ist das Segment, nicht das Video. custom_id enthaelt
    zusaetzlich den Replikat-Index.
  - responseSchema mit propertyOrdering wird immer mitgeschickt.
  - Es wird immer ein Manifest geschrieben, und das JSONL bleibt liegen.
  - Replikate laufen innerhalb EINES Runs. Die Registry bleibt dadurch
    unveraendert; der Replikat-Index steht in custom_id und Manifest.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
from google import genai
from google.cloud import storage

from youtube_code.config import PROJECT_ID, LOCATION, BUCKET_NAME, SAMPLES
from youtube_code.segment_analysis.segment_analysis_config import (
    BATCH_INPUT_DIR,
    LLM_RUN_SOURCE,
    MANIFEST_DIR,
)
from youtube_code.utils import llm_run_store

from youtube_code.segment_analysis.segment_prompts_simple import get_bundle


# ============================================================
# CONFIG
# ============================================================

SEGMENT_FILE = SAMPLES / "russia" / "out_segments" / "pilot_classification_segments.csv"

PROMPT_KEY = "POPULISMUS_P"

DATASET_VERSION = "v1"
PROMPT_VERSION = "v4"

MODEL_NAME = "gemini_25_flash"
THINKING_BUDGET = 0
TEMPERATURE = 0.0

# Anzahl unabhaengiger Durchlaeufe pro Segment. 1 = Produktivlauf,
# >1 = Reliabilitaetsschaetzung. Bei >1 muss TEMPERATURE > 0 sein,
# sonst misst man nur API-Rauschen.
REPLICATES = 1

# Woerter aus dem Ende des vorangehenden Segments (selbes Video), die als
# Kontextblock mitgeschickt werden. Nur wirksam bei Prompts mit
# bundle["use_context"] = True (z. B. POPULISMUS_P).
CONTEXT_WORDS = 80

# Nur fuer Pilotlaeufe: auf die ersten N Segmente begrenzen (None = alle).
MAX_SEGMENTS = None

# Erst das JSONL ansehen, dann auf False setzen.
DRY_RUN = False

# Schutz gegen versehentliche Doppel-Submits.
ALLOW_EXISTING_RUN = False

# Spaltennamen in SEGMENT_FILE. Fehlt SEGMENT_ID_COLUMN, wird die ID
# aus VIDEO_ID_COLUMN und SEGMENT_INDEX_COLUMN gebaut. Fehlt auch
# SEGMENT_INDEX_COLUMN, wird 0 angenommen (ein Segment pro Video -
# der Normalfall fuer ganze Transkripte wie bei IDEOLOGIE_I).
SEGMENT_ID_COLUMN = "segment_id"
VIDEO_ID_COLUMN = "video_id"
SEGMENT_INDEX_COLUMN = "segment_index"
TEXT_COLUMN = "text"


# ============================================================
# FIXES
# ============================================================

MODEL_ALIASES = {
    "gemini_25_flash": "gemini-2.5-flash",
    "gemini_25_pro": "gemini-2.5-pro",
}

SEGMENT_BATCH_INPUT_DIR = Path(BATCH_INPUT_DIR) / "segments"
SEGMENT_MANIFEST_DIR = Path(MANIFEST_DIR) / "segments"


# ============================================================
# HELFER
# ============================================================

def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def load_segments(path: Path) -> pd.DataFrame:
    """Liest die Segmentdatei und stellt eine eindeutige segment_id her."""
    if not path.exists():
        raise FileNotFoundError(f"Segmentdatei nicht gefunden: {path}")

    data = pd.read_csv(path, dtype="string", low_memory=False)

    if TEXT_COLUMN not in data.columns:
        raise ValueError(
            f"Spalte {TEXT_COLUMN!r} fehlt. Vorhandene Spalten: "
            f"{sorted(data.columns.tolist())}. "
            "Passe TEXT_COLUMN im CONFIG-Block an."
        )

    data["text"] = data[TEXT_COLUMN].fillna("").str.strip()

    if SEGMENT_ID_COLUMN in data.columns:
        data["segment_id"] = data[SEGMENT_ID_COLUMN].fillna("").str.strip()
        built_index = None
    else:
        if VIDEO_ID_COLUMN not in data.columns:
            raise ValueError(
                f"Weder {SEGMENT_ID_COLUMN!r} noch {VIDEO_ID_COLUMN!r} "
                f"vorhanden. Spalten: {sorted(data.columns.tolist())}"
            )
        if SEGMENT_INDEX_COLUMN in data.columns:
            built_index = pd.to_numeric(
                data[SEGMENT_INDEX_COLUMN], errors="coerce"
            )
            if built_index.isna().any():
                raise ValueError(
                    f"{SEGMENT_INDEX_COLUMN!r} enthaelt nicht-numerische Werte."
                )
        else:
            # Kein Index vorhanden: ein Segment pro Video. Das ist der
            # Normalfall fuer ganze Transkripte (z. B. Baseline-Videos
            # fuer IDEOLOGIE_I), die nicht weiter unterteilt werden.
            built_index = pd.Series(0, index=data.index)
        data["segment_id"] = (
            data[VIDEO_ID_COLUMN].fillna("").str.strip()
            + "__s"
            + built_index.astype(int).map("{:04d}".format)
        )

    # video_id und segment_index nur zur Information ins Manifest.
    data["video_id"] = (
        data[VIDEO_ID_COLUMN].fillna("") if VIDEO_ID_COLUMN in data.columns else ""
    )
    if SEGMENT_INDEX_COLUMN in data.columns:
        data["segment_index"] = data[SEGMENT_INDEX_COLUMN].fillna("")
    elif built_index is not None:
        data["segment_index"] = built_index.astype(int).astype(str)
    else:
        data["segment_index"] = ""

    empty_ids = data["segment_id"].eq("")
    if empty_ids.any():
        raise ValueError(f"{int(empty_ids.sum()):,} Zeilen ohne segment_id.")

    duplicated = data["segment_id"].duplicated(keep=False)
    if duplicated.any():
        examples = sorted(data.loc[duplicated, "segment_id"].unique().tolist())[:10]
        raise ValueError(f"segment_id muss eindeutig sein. Duplikate: {examples}")

    empty_text = data["text"].eq("")
    if empty_text.any():
        examples = data.loc[empty_text, "segment_id"].head(10).tolist()
        raise ValueError(
            f"{int(empty_text.sum()):,} leere Segmente, z. B.: {examples}"
        )

    data = data[["segment_id", "video_id", "segment_index", "text"]].copy()
    if MAX_SEGMENTS is not None:
        data = data.head(int(MAX_SEGMENTS)).copy()
    return data.reset_index(drop=True)


def build_context_blocks(segments: pd.DataFrame, context_words: int) -> dict[str, str]:
    """
    Letzte `context_words` Woerter des UNMITTELBAR VORANGEHENDEN Segments
    desselben Videos, sortiert nach segment_index. Kontext wird nur
    gesetzt, wenn segment_index exakt um 1 steigt (echte Nachbarschaft
    im urspruenglichen Transkript). Bei Luecken - z. B. durch die
    MAX_SEGMENTS_PER_VIDEO-Deckelung in process_scraped_segments.py,
    die nur eine Teilmenge der Segmente behaelt und deren urspruengliche
    Indizes nicht neu durchnummeriert - bleibt der Kontext leer, weil
    das vorherige Segment im File dann inhaltlich nicht direkt vorausgeht.
    Erstes Segment eines Videos bekommt ebenfalls keinen Kontext.

    Gibt segment_id -> Kontexttext zurueck (leerer String = kein Kontext).
    """
    ordering = segments.copy()
    ordering["idx_numeric"] = pd.to_numeric(
        ordering["segment_index"], errors="coerce"
    )
    ordering = ordering.sort_values(
        ["video_id", "idx_numeric"], na_position="last"
    )

    contexts: dict[str, str] = {}
    previous_video = object()
    previous_idx = None
    previous_text = ""
    for row in ordering.itertuples(index=False):
        is_adjacent = (
            row.video_id == previous_video
            and previous_idx is not None
            and pd.notna(row.idx_numeric)
            and row.idx_numeric == previous_idx + 1
        )
        if is_adjacent:
            words = previous_text.split()
            contexts[row.segment_id] = " ".join(words[-context_words:])
        else:
            contexts[row.segment_id] = ""
        previous_video = row.video_id
        previous_idx = row.idx_numeric
        previous_text = row.text
    return contexts


def render_request_text(
    bundle: dict,
    segment_text: str,
    context_text: str,
) -> str:
    label = bundle.get("segment_label", "SEGMENT")
    parts = [bundle["text"]]
    if bundle.get("use_context") and context_text:
        parts.append(
            "VORHERGEHENDER KONTEXT (nicht bewerten, nur zum Verstaendnis):\n"
            f"{context_text}"
        )
    parts.append(f"{label}:\n{segment_text}")
    return "\n\n".join(parts)

def build_jsonl_and_manifest(
    segments: pd.DataFrame,
    bundle: dict,
    jsonl_path: Path,
    manifest_path: Path,
    model_alias: str,
) -> int:
    """Schreibt eine Zeile pro (Segment x Replikat) und das Manifest."""
    prompt_text = bundle["text"]
    prompt_hash = sha1(prompt_text)

    generation_config = {
        "responseMimeType": "application/json",
        "responseSchema": bundle["schema"],
        "temperature": TEMPERATURE,
    }
    if THINKING_BUDGET is not None:
        generation_config["thinkingConfig"] = {"thinkingBudget": THINKING_BUDGET}

    manifest_rows = []
    written = 0

    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    context_map = (
        build_context_blocks(segments, CONTEXT_WORDS)
        if bundle.get("use_context")
        else {}
    )

    with jsonl_path.open("w", encoding="utf-8") as output_file:
        for row in segments.itertuples(index=False):
            segment_text = str(row.text)
            context_text = context_map.get(row.segment_id, "")
            full_text = render_request_text(bundle, segment_text, context_text)

            for replicate in range(1, REPLICATES + 1):
                custom_id = f"{row.segment_id}__r{replicate}"
                api_request = {
                    "custom_id": custom_id,
                    "request": {
                        "contents": [
                            {"role": "user", "parts": [{"text": full_text}]}
                        ],
                        "generationConfig": generation_config,
                    },
                }
                output_file.write(
                    json.dumps(api_request, ensure_ascii=False) + "\n"
                )
                manifest_rows.append(
                    {
                        "custom_id": custom_id,
                        "segment_id": row.segment_id,
                        "video_id": row.video_id,
                        "segment_index": row.segment_index,
                        "replicate": replicate,
                        "n_chars": len(segment_text),
                        "text_sha1": sha1(segment_text),
                        "prompt_key": PROMPT_KEY,
                        "prompt_sha1": prompt_hash,
                        "model": model_alias,
                        "temperature": TEMPERATURE,
                        "thinking_budget": THINKING_BUDGET,
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                    }
                )
                written += 1

    pd.DataFrame(manifest_rows).to_csv(
        manifest_path, index=False, encoding="utf-8-sig"
    )
    return written


def require_no_existing_run(dataset_id: str, target: str) -> None:
    if ALLOW_EXISTING_RUN:
        return
    existing = llm_run_store.get_runs(
        source=LLM_RUN_SOURCE,
        dataset_id=dataset_id,
        target_variable=target,
    )
    if not existing.empty:
        existing = existing[
            (existing["dataset_version"] == DATASET_VERSION)
            & (existing["prompt_id"] == PROMPT_KEY)
        ]
    if existing.empty:
        return
    columns = [
        column
        for column in ["run_id", "status", "job_id", "created_at"]
        if column in existing.columns
    ]
    raise ValueError(
        "Ein passender Run existiert bereits:\n"
        f"{existing[columns].to_string(index=False)}\n"
        "ALLOW_EXISTING_RUN=True nur fuer einen bewussten Retry setzen."
    )


def upload_and_start(jsonl_path: Path, model_alias: str, client) -> str:
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)
    blob_name = f"batch_inputs/segments/{jsonl_path.stem}_{uuid.uuid4().hex}.jsonl"
    bucket.blob(blob_name).upload_from_filename(str(jsonl_path))

    gcs_uri = f"gs://{BUCKET_NAME}/{blob_name}"
    print(f"Hochgeladen: {gcs_uri}")

    job = client.batches.create(model=model_alias, src=gcs_uri)
    # Das lokale JSONL wird bewusst NICHT geloescht.
    return job.name


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    if MODEL_NAME not in MODEL_ALIASES:
        raise ValueError(f"Unbekanntes Modell {MODEL_NAME!r}.")
    if REPLICATES < 1:
        raise ValueError("REPLICATES muss mindestens 1 sein.")
    if REPLICATES > 1 and TEMPERATURE == 0:
        raise ValueError(
            "REPLICATES > 1 bei TEMPERATURE = 0 misst kein echtes "
            "Modellrauschen. Setze TEMPERATURE z. B. auf 0.7."
        )

    model_alias = MODEL_ALIASES[MODEL_NAME]
    bundle = get_bundle(PROMPT_KEY)
    target_variable = bundle["target_variable"]

    segments = load_segments(Path(SEGMENT_FILE))
    dataset_id = Path(SEGMENT_FILE).stem

    require_no_existing_run(dataset_id, target_variable)

    stem = f"segments_{PROMPT_KEY}_{MODEL_NAME}"
    jsonl_path = SEGMENT_BATCH_INPUT_DIR / f"{stem}.jsonl"
    manifest_path = SEGMENT_MANIFEST_DIR / f"{stem}.manifest.csv"

    n_requests = build_jsonl_and_manifest(
        segments=segments,
        bundle=bundle,
        jsonl_path=jsonl_path,
        manifest_path=manifest_path,
        model_alias=model_alias,
    )

    lengths = segments["text"].str.len()
    print("\n" + "=" * 68)
    print("SEGMENT-KLASSIFIKATION")
    print("=" * 68)
    print(f"Eingabe          : {SEGMENT_FILE}")
    print(f"Dataset          : {dataset_id} ({DATASET_VERSION})")
    print(f"Prompt           : {PROMPT_KEY} ({PROMPT_VERSION})")
    print(f"Zielvariable     : {target_variable}")
    print(f"Modell           : {model_alias} | thinking={THINKING_BUDGET} "
          f"| temperature={TEMPERATURE}")
    print(f"Segmente         : {len(segments):,}")
    print(f"Replikate        : {REPLICATES}")
    print(f"Requests         : {n_requests:,}")
    print(f"Segmentlaenge    : median={lengths.median():,.0f} "
          f"max={lengths.max():,} Zeichen")
    print(f"JSONL            : {jsonl_path}")
    print(f"Manifest         : {manifest_path}")
    print(f"Dry run          : {DRY_RUN}")
    print("=" * 68)

    if DRY_RUN:
        print("\nDry run: nichts abgeschickt. JSONL und Manifest liegen bereit.")
        print("Erste Request-Zeile zur Kontrolle:")
        with jsonl_path.open(encoding="utf-8") as handle:
            first = json.loads(handle.readline())
        print(f"  custom_id: {first['custom_id']}")
        print(
            "  Feldreihenfolge: "
            + ", ".join(
                first["request"]["generationConfig"]["responseSchema"][
                    "propertyOrdering"
                ]
            )
        )
        return

    if input("\nJob abschicken? [y/N] ").strip().lower() != "y":
        print("Abgebrochen.")
        return

    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    job_id = upload_and_start(jsonl_path, model_alias, client)

    run_id = llm_run_store.add_run(
        LLM_RUN_SOURCE,
        prompt_id=PROMPT_KEY,
        prompt_number="seg",
        prompt_version=PROMPT_VERSION,
        model=model_alias,
        thinking_budget=THINKING_BUDGET,
        dataset_id=dataset_id,
        dataset_version=DATASET_VERSION,
        target_variable=target_variable,
        validation_basis="segment_schema",
        job_id=job_id,
        status="submitted",
        notes=(
            f"segments|replicates={REPLICATES}|temperature={TEMPERATURE}"
            f"|n_segments={len(segments)}|n_requests={n_requests}"
            f"|prompt_sha1={sha1(bundle['text'])[:12]}"
        ),
    )

    jsonl_path.replace(jsonl_path.with_name(f"{run_id}_{stem}.jsonl"))
    manifest_path.replace(SEGMENT_MANIFEST_DIR / f"{run_id}_manifest.csv")

    print(f"\nRun angelegt: {run_id}")
    print(f"Job: {job_id}")
    print("Weiter mit download_segments.py.")


if __name__ == "__main__":
    main()
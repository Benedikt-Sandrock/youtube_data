"""
Segment-Klassifikation: Ergebnisse abholen, pruefen, speichern.

Ausgabe ist ein Long-Format: eine Zeile pro (Segment x Replikat), mit
allen Modellfeldern und vier Pruefspalten:

  ok_schema      Antwort geparst, alle Felder vorhanden, Enums gueltig
  ok_status      status/gate-Konsistenz eingehalten
  ok_score       score im erlaubten Wertebereich (oder korrekt null bei kodierbar=False)
  beleg_quote    Anteil der Belegstellen, die woertlich im Segment stehen
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
from google import genai
from google.cloud import storage

from youtube_code.config import OUTPUTS, PROJECT_ID, LOCATION
from youtube_code.llm_analysis.registry.run_registry import RunRegistry
from youtube_code.segment_analysis.segment_analysis_config import (
    MANIFEST_DIR,
    REGISTRY_PATH,
)

from youtube_code.segment_analysis.segment_prompts_simple import get_bundle
from youtube_code.segment_analysis.submit_segments import (
    SEGMENT_FILE,
    load_segments,
)


# ============================================================
# CONFIG
# ============================================================

RUN_IDS: list[str] = []

RESULTS_DIR = OUTPUTS / "segment_analysis"
SEGMENT_MANIFEST_DIR = MANIFEST_DIR / "segments"

SEGMENT_FILE_FOR_CHECK = None

OVERWRITE = False


# ============================================================
# HELFER
# ============================================================

def normalize(text: str) -> str:
    """Kleinschreibung, nur Buchstaben/Ziffern/Leerzeichen, ein Space."""
    lowered = str(text).lower()
    cleaned = re.sub(r"[^0-9a-zaeoeuess\u00e4\u00f6\u00fc\u00df ]+", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_response_text(record: dict) -> str:
    response = record.get("response", {})
    if "candidates" in response:
        candidates = response["candidates"]
    elif "generateContentResponse" in response:
        candidates = response["generateContentResponse"]["candidates"]
    else:
        raise ValueError("Keine candidates (moeglicherweise Safety-Filter).")
    return candidates[0]["content"]["parts"][0]["text"]


def download_records(status_job, storage_client) -> list[dict]:
    output_folder = status_job.output_info.gcs_output_directory
    bucket_name, prefix = output_folder.replace("gs://", "").split("/", 1)
    bucket = storage_client.bucket(bucket_name)

    records = []
    blobs = [
        blob
        for blob in bucket.list_blobs(prefix=prefix)
        if blob.name.endswith(".jsonl") and "prediction" in blob.name.lower()
    ]
    if not blobs:
        raise ValueError(f"Keine prediction-JSONL unter {output_folder}.")

    for blob in sorted(blobs, key=lambda item: item.name):
        print(f"  Lade {blob.name} ...")
        for line in blob.download_as_text().splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


def parse_records(records: list[dict], bundle: dict) -> pd.DataFrame:
    fields = list(bundle["schema"]["properties"])
    rows = []

    for record in records:
        custom_id = str(record.get("custom_id", ""))
        row = {"custom_id": custom_id, "parse_error": ""}

        if "error" in record:
            row["parse_error"] = f"api_error: {record['error']}"
            rows.append(row)
            continue

        try:
            parsed = json.loads(extract_response_text(record))
            if not isinstance(parsed, dict):
                raise ValueError("Antwort ist kein JSON-Objekt.")
        except Exception as error:
            row["parse_error"] = f"parse_error: {error}"
            rows.append(row)
            continue

        for field in fields:
            row[field] = parsed.get(field, None)

        unexpected = sorted(set(parsed) - set(fields))
        if unexpected:
            row["parse_error"] = f"unerwartete Felder: {unexpected}"

        rows.append(row)

    return pd.DataFrame(rows)


def is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, dict, tuple, set)):
        return False
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def check_row(row: pd.Series, bundle: dict, segment_text: str | None) -> dict:
    if bundle.get("kind") == "nested_dimension":
        return check_row_nested(row, bundle, segment_text)
    return check_row_flat(row, bundle, segment_text)


def check_row_flat(row: pd.Series, bundle: dict, segment_text: str | None) -> dict:
    """Pruefung fuer flache Schemata (z. B. POSITION_V1, POPULISMUS_P)."""
    if row.get("parse_error"):
        return {
            "ok_schema": False,
            "ok_status": False,
            "ok_score": False,
            "beleg_quote": None,
            "beleg_fehlend": "",
        }

    schema_props = bundle["schema"]["properties"]
    fields = list(schema_props)

    ok_schema = True
    for field in fields:
        val = row.get(field)
        is_nullable = schema_props[field].get("nullable", False)
        if is_missing(val) and not is_nullable:
            ok_schema = False

    for field, allowed in bundle.get("enum_fields", {}).items():
        value = row.get(field)
        if isinstance(value, list):
            if any(item not in allowed for item in value):
                ok_schema = False
        elif value not in allowed:
            ok_schema = False

    for field, kind in bundle.get("trailing_fields", {}).items():
        val = row.get(field)
        if kind == "bool" and not isinstance(val, bool):
            ok_schema = False

    ok_status = True
    ok_score = True

    gate_field = bundle.get("gate_field")
    gate_open = True
    if gate_field:
        gate_val = row.get(gate_field)
        if not isinstance(gate_val, bool):
            ok_schema = False
        gate_open = (gate_val == bundle.get("gate_open_value", True))

    for status_field, expected_value, score_field in bundle.get("conditional_score_rules", []):
        status_value = row.get(status_field)
        score_value = row.get(score_field)
        score_present = not is_missing(score_value)
        should_have = (status_value == expected_value)
        if should_have != score_present:
            ok_status = False
        if score_present:
            low, high = bundle["score_ranges"][score_field]
            if not (low <= score_value <= high):
                ok_score = False

    status_score_fields = {
        rule[2] for rule in bundle.get("conditional_score_rules", [])
    }
    for field, (low, high) in bundle.get("score_ranges", {}).items():
        if field in status_score_fields:
            continue

        value = row.get(field)
        score_present = not is_missing(value)
        is_nullable = schema_props[field].get("nullable", False)

        if gate_field and not gate_open:
            if score_present:
                ok_status = False
        else:
            if not score_present:
                if not is_nullable:
                    ok_score = False
                # nullable und fehlend (echtes JSON-null) ist zulaessig,
                # z.B. IDEOLOGIE_I bei "nicht erkennbar".
            elif not (low <= value <= high):
                ok_score = False

    beleg_quote = None
    fehlend = []
    if segment_text is not None and bundle.get("evidence_fields"):
        haystack = normalize(segment_text)
        all_belege = []
        for field in bundle["evidence_fields"]:
            value = row.get(field)
            if isinstance(value, list):
                all_belege.extend(str(item) for item in value)
        if all_belege:
            hits = sum(1 for b in all_belege if normalize(b) and normalize(b) in haystack)
            fehlend = [b[:60] for b in all_belege if not (normalize(b) and normalize(b) in haystack)]
            beleg_quote = round(hits / len(all_belege), 3)
        else:
            beleg_quote = 1.0

    return {
        "ok_schema": bool(ok_schema),
        "ok_status": bool(ok_status),
        "ok_score": bool(ok_score),
        "beleg_quote": beleg_quote,
        "beleg_fehlend": " || ".join(fehlend),
    }


def check_row_nested(row: pd.Series, bundle: dict, segment_text: str | None) -> dict:
    if row.get("parse_error"):
        return {
            "ok_schema": False,
            "ok_status": False,
            "ok_score": False,
            "beleg_quote": None,
            "beleg_fehlend": "",
        }

    dims = bundle["dimensions"]
    low, high = bundle["wert_range"]
    gate_field = bundle.get("gate_field")
    gate_open_value = bundle.get("gate_open_value", True)
    null_convention = bundle["null_convention"]

    ok_schema = True
    ok_status = True
    ok_score = True

    gate_open = True
    if gate_field:
        gate_value = row.get(gate_field)
        if not isinstance(gate_value, bool):
            ok_schema = False
        gate_open = gate_value == gate_open_value

    all_belege: list[str] = []

    for dim in dims:
        obj = row.get(dim)
        if not isinstance(obj, dict):
            ok_schema = False
            continue

        beleg = obj.get("beleg")
        wert = obj.get("wert")
        if beleg is not None and not isinstance(beleg, str):
            ok_schema = False
        if wert is not None and not isinstance(wert, (int, float)):
            ok_schema = False

        if gate_field and not gate_open:
            if beleg is not None or wert is not None:
                ok_status = False
        else:
            has_beleg = beleg is not None
            if null_convention == "zero":
                if wert is None:
                    ok_score = False
                else:
                    expected_beleg = wert != 0
                    if has_beleg != expected_beleg:
                        ok_status = False
                    if not (low <= wert <= high):
                        ok_score = False
            else:
                expected_beleg = wert is not None
                if has_beleg != expected_beleg:
                    ok_status = False
                if wert is not None and not (low <= wert <= high):
                    ok_score = False

        if beleg:
            all_belege.append(str(beleg))

    for field, kind in bundle.get("trailing_fields", {}).items():
        value = row.get(field)
        if kind == "bool" and not isinstance(value, bool):
            ok_schema = False

    beleg_quote = None
    fehlend: list[str] = []
    if segment_text is not None:
        haystack = normalize(segment_text)
        if all_belege:
            hits = sum(1 for b in all_belege if normalize(b) and normalize(b) in haystack)
            fehlend = [b[:60] for b in all_belege if not (normalize(b) and normalize(b) in haystack)]
            beleg_quote = round(hits / len(all_belege), 3)
        else:
            beleg_quote = 1.0

    return {
        "ok_schema": bool(ok_schema),
        "ok_status": bool(ok_status),
        "ok_score": bool(ok_score),
        "beleg_quote": beleg_quote,
        "beleg_fehlend": " || ".join(fehlend),
    }


def print_qc(results: pd.DataFrame, expected: int) -> None:
    n = len(results)
    print("\n  Qualitaetspruefung")
    print(f"    Requests erwartet / erhalten : {expected:,} / {n:,}")
    if n == 0:
        return
    failed = results["parse_error"].ne("").sum()
    print(f"    Parse-Fehler                 : {failed:,} ({failed / n:.1%})")
    for column in ["ok_schema", "ok_status", "ok_score"]:
        share = results[column].mean()
        print(f"    {column:<29}: {share:.1%}")
    if results["beleg_quote"].notna().any():
        quote = results["beleg_quote"].mean()
        perfect = results["beleg_quote"].eq(1.0).mean()
        print(f"    beleg_quote (Mittel)         : {quote:.1%}")
        print(f"    Zeilen mit allen Belegen     : {perfect:.1%}")


# ============================================================
# EIN RUN
# ============================================================

def process_run(run_id: str, registry: RunRegistry, client, storage_client,
                texts: dict[str, str] | None) -> str:
    run = registry.get_run(run_id)
    prompt_key = str(run["prompt_id"])
    bundle = get_bundle(prompt_key)

    print(f"\n[{run_id}] {prompt_key} | {run['model']} | "
          f"{run['dataset_id']} ({run['dataset_version']})")

    status_job = client.batches.get(name=str(run["job_id"]))
    state = getattr(status_job.state, "name", str(status_job.state))
    print(f"  Status: {state}")

    if state in {"JOB_STATE_FAILED", "JOB_STATE_CANCELLED"}:
        registry.update_run(run_id, status="failed")
        return "failed"
    if state != "JOB_STATE_SUCCEEDED":
        return "pending"

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / f"{run_id}_{prompt_key}.csv"
    if output_path.exists() and not OVERWRITE:
        print(f"  Existiert bereits: {output_path} (OVERWRITE=False)")
        return "skipped"

    manifest_path = SEGMENT_MANIFEST_DIR / f"{run_id}_manifest.csv"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest fehlt: {manifest_path}")
    manifest = pd.read_csv(manifest_path, dtype="string")
    manifest["replicate"] = pd.to_numeric(manifest["replicate"])

    records = download_records(status_job, storage_client)
    parsed = parse_records(records, bundle)

    results = manifest.merge(parsed, on="custom_id", how="left", indicator=True)
    fehlend = results["_merge"].eq("left_only").sum()
    unerwartet = set(parsed["custom_id"]) - set(manifest["custom_id"])
    if unerwartet:
        raise ValueError(
            f"{len(unerwartet)} custom_ids in den Ergebnissen sind nicht im "
            f"Manifest, z. B. {sorted(unerwartet)[:5]}"
        )
    if fehlend:
        print(f"  Achtung: {fehlend:,} Requests ohne Antwort.")
    results = results.drop(columns=["_merge"])
    results["parse_error"] = results["parse_error"].fillna("keine Antwort")

    checks = results.apply(
        lambda row: check_row(
            row,
            bundle,
            None if texts is None else texts.get(str(row["segment_id"])),
        ),
        axis=1,
        result_type="expand",
    )
    results = pd.concat([results, checks], axis=1)
    results.insert(0, "run_id", run_id)

    for field, spec in bundle["schema"]["properties"].items():
        if spec["type"] == "ARRAY":
            results[field] = results[field].map(
                lambda value: json.dumps(value, ensure_ascii=False)
                if isinstance(value, list)
                else ""
            )
        elif spec["type"] == "OBJECT":
            results[field] = results[field].map(
                lambda value: json.dumps(value, ensure_ascii=False)
                if isinstance(value, dict)
                else ""
            )

    results.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"  Gespeichert: {output_path}")
    print_qc(results, expected=len(manifest))

    registry.update_run(run_id, status="downloaded", results_path=str(output_path))
    return "downloaded"


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    registry = RunRegistry(REGISTRY_PATH)
    client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    storage_client = storage.Client(project=PROJECT_ID)

    if RUN_IDS:
        run_ids = list(RUN_IDS)
    else:
        open_runs = registry.get_runs(status="submitted")
        notes = open_runs.get("notes", pd.Series(dtype=str)).fillna("")
        run_ids = open_runs.loc[
            notes.str.startswith("segments"), "run_id"
        ].tolist()

    if not run_ids:
        print("Keine offenen Segment-Runs.")
        return

    texts = None
    segment_file = SEGMENT_FILE_FOR_CHECK or SEGMENT_FILE
    try:
        segments = load_segments(Path(segment_file))
        texts = dict(zip(segments["segment_id"], segments["text"]))
        print(f"Belegpruefung gegen {len(texts):,} Segmente aus {segment_file}.")
    except Exception as error:
        print(f"Belegpruefung deaktiviert ({error}).")

    summary = {}
    for run_id in run_ids:
        try:
            summary[run_id] = process_run(
                run_id, registry, client, storage_client, texts
            )
        except Exception as error:
            print(f"  Fehlgeschlagen: {error}")
            summary[run_id] = f"error: {error}"

    print("\n" + "=" * 68)
    for run_id, state in summary.items():
        print(f"  {run_id}: {state}")
    print("=" * 68)


if __name__ == "__main__":
    main()
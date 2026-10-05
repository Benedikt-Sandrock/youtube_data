"""Durchsucht alle Runs unter outputs/llm_results/ nach parse_error-Zeilen.

Segment-Analysis-Runs (submit_segments.py / download_segments_simple.py)
schreiben pro (Segment x Replikat) eine Zeile; scheitert das JSON-Parsing der
Modellantwort, bleibt die Zeile erhalten und traegt eine `parse_error`-Meldung
statt Modellfeldern (siehe src/youtube_code/step5_segment_analysis/README.md,
Abschnitt "Ausgabe"). Screening-Runs (outputs/llm_results/screening_active__*)
haben keine `parse_error`-Spalte und werden hier uebersprungen.

Fuer jeden Prompt (`prompt_key`, z. B. POSITION_V1, POPULISMUS_P, IDEOLOGIE_I)
wird eine eigene CSV nach data/exploration/parse_errors_<PROMPT_KEY>.csv
geschrieben, mit einer `video_id`-Spalte sowie Zusatzspalten fuer Rueckverfolg-
barkeit (run_id, custom_id, segment_id, parse_error-Meldung, Quelldateien).

Manche Runs liegen doppelt vor (z. B. run_0010_POPULISMUS_P.csv und
run_0010_POPULISMUS_P_corrected.csv) - die "_corrected"-Varianten korrigieren
dort inhaltliche Felder (z. B. `kodierbar`-Gating), nicht aber parse_error-
Zeilen selbst, die Fehler tauchen also identisch in beiden Dateien auf. Um
Video-IDs nicht doppelt zu zaehlen, wird pro (run_id, custom_id) nur eine
Zeile behalten; alle Quelldateien, in denen der Fehler auftrat, werden in der
Spalte `source_files` gesammelt.

Aufruf: python scripts/adhoc/find_parse_errors.py
"""

import pandas as pd

from youtube_code.config import OUTPUTS, EXPLORATION  # Sources Root: src/

LLM_RESULTS = OUTPUTS / "llm_results"

REQUIRED_COLUMNS = {"video_id", "parse_error", "prompt_key", "run_id", "custom_id"}


def find_parse_error_rows() -> pd.DataFrame:
    """Liest alle CSVs unter LLM_RESULTS und gibt die parse_error-Zeilen zurueck."""
    rows = []
    for path in sorted(LLM_RESULTS.rglob("*.csv")):
        try:
            df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
        except Exception as exc:
            print(f"  [uebersprungen, Lesefehler] {path}: {exc}")
            continue

        if not REQUIRED_COLUMNS.issubset(df.columns):
            continue  # z. B. screening_active-CSVs ohne parse_error-Spalte

        errors = df[df["parse_error"].notna() & (df["parse_error"].str.strip() != "")]
        if errors.empty:
            continue

        errors = errors.copy()
        errors["source_file"] = str(path.relative_to(LLM_RESULTS))
        rows.append(errors)

    if not rows:
        return pd.DataFrame()

    return pd.concat(rows, ignore_index=True)


def main() -> None:
    all_errors = find_parse_error_rows()
    if all_errors.empty:
        print("Keine parse_error-Zeilen gefunden.")
        return

    EXPLORATION.mkdir(parents=True, exist_ok=True)

    keep_cols = [
        "prompt_key", "video_id", "run_id", "custom_id", "segment_id",
        "segment_index", "replicate", "parse_error", "source_file",
    ]
    keep_cols = [c for c in keep_cols if c in all_errors.columns]
    all_errors = all_errors[keep_cols]

    # Original- und "_corrected"-Datei melden denselben Fehler fuer dieselbe
    # (run_id, custom_id) doppelt -> zu einer Zeile zusammenfassen, aber die
    # Quelldateien fuer Rueckverfolgbarkeit sammeln.
    agg = {c: "first" for c in keep_cols if c != "source_file"}
    agg["source_file"] = lambda s: ";".join(sorted(set(s)))
    deduped = (
        all_errors.groupby(["run_id", "custom_id"], as_index=False)
        .agg(agg)
        .rename(columns={"source_file": "source_files"})
    )

    print(f"Gefundene parse_error-Zeilen (dedupliziert): {len(deduped)}")

    for prompt_key, group in deduped.groupby("prompt_key"):
        out_path = EXPLORATION / f"parse_errors_{prompt_key}.csv"
        group = group.sort_values(["run_id", "video_id"]).drop(columns="prompt_key")
        group.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"  {prompt_key}: {len(group)} Zeilen -> {out_path.relative_to(EXPLORATION.parent.parent)}")


if __name__ == "__main__":
    main()

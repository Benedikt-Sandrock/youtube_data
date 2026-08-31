"""
Adhoc: Fuer eine gewuenschte Liste von Kanal-IDs alle politischen
Baseline-Videos abrufen (Vorkriegs- ODER Postwar-Baseline-Fenster).

Baseline-Fenster (Details: src/youtube_code/politics_screening/README_BASELINE_WINDOW.md):
- Vorkriegs-Kanaele: interval_index in {0,1,2,3} (Labels -12_to_-10 ... -3_to_-1)
- Postwar-Kanaele:   interval_index == -1 (Sentinel, siehe assign_postwar_baseline.py)
"Politisch" heisst politics_final == 1 im screening_state_store.

Nutzung: unten CHANNEL_IDS (oder CHANNEL_IDS_FILE) setzen, dann:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
      scripts/adhoc/get_baseline_videos_for_channels.py

Schreibt zwei JSON-Dateien nach scripts/adhoc/output/ im Format
[{"video_id": ..., "channel_id": ...}, ...] - kompatibel mit dem VIDEO_LIST-Input
von src/youtube_code/scraping/transcript_scraping_segments.py:
- <OUTPUT_NAME>_all.json  - alle politischen Baseline-Videos der angefragten Kanaele
- <OUTPUT_NAME>_open.json - Teilmenge davon ohne bisherigen Transkript-Versuch
  (transcript_store.attempted_video_ids() - einzige gueltige Quelle dafuer, siehe
  .claude/CLAUDE.md)
"""
import json
from pathlib import Path

import pandas as pd

from youtube_code.store.screening_state_store import get_state
from youtube_code.store.transcript_store import attempted_video_ids
from youtube_code.config import OUTPUTS

# ============================================================
# CONFIG
# ============================================================

df = pd.read_csv(OUTPUTS /"segment_analysis" / "channel_video_populism.csv")

channels = set(df["channel_id"].tolist())
print(len(channels))


df2 = pd.read_csv(OUTPUTS / "segment_analysis" / "channel_classification_ideology.csv")
done = set(df2["channel_id"].tolist())

CHANNEL_IDS = channels - done
CHANNEL_IDS = list(CHANNEL_IDS)


# ... ODER eine CSV mit einer "channel_id"-Spalte angeben (hat Vorrang, falls gesetzt)
CHANNEL_IDS_FILE = None  # z. B. "outputs/segment_analysis/kanaele_baseline_collection_todo.csv"

OUTPUT_NAME = "baseline_videos"  # Praefix der Ausgabedateien

PREWAR_BASELINE_INTERVALS = [0, 1, 2, 3]
POSTWAR_BASELINE_INTERVAL = -1

OUTPUT_DIR = Path(__file__).parent / "output"


def load_channel_ids() -> list[str]:
    if CHANNEL_IDS_FILE:
        df = pd.read_csv(CHANNEL_IDS_FILE, dtype={"channel_id": "string"})
        ids = df["channel_id"].dropna().unique().tolist()
    else:
        ids = list(CHANNEL_IDS)
    if not ids:
        raise ValueError(
            "Weder CHANNEL_IDS noch CHANNEL_IDS_FILE liefern Kanal-IDs - "
            "eine der beiden Konstanten oben setzen."
        )
    return [str(v).strip() for v in ids]


def main():
    channel_ids = load_channel_ids()
    print(f"{len(channel_ids)} angefragte Kanal-IDs.")

    state = get_state(channel_ids=channel_ids)
    print(f"{len(state):,} State-Zeilen fuer diese Kanaele insgesamt.")

    baseline = state[
        state["interval_index"].isin(PREWAR_BASELINE_INTERVALS)
        | state["interval_index"].eq(POSTWAR_BASELINE_INTERVAL)
    ]
    political = baseline[baseline["politics_final"] == 1].copy()
    print(f"{len(political):,} politische Baseline-Videos (politics_final==1) gefunden.")

    found_channels = set(political["channel_id"].unique())
    missing_channels = set(channel_ids) - found_channels
    if missing_channels:
        print(
            f"\n{len(missing_channels)} angefragte Kanaele ohne ein einziges "
            "politisches Baseline-Video:"
        )
        for channel_id in sorted(missing_channels):
            print(f"  {channel_id}")

    print("\nPolitische Baseline-Videos je Kanal:")
    print(
        political.groupby("channel_id")
        .size()
        .sort_values(ascending=False)
        .to_string()
    )

    attempted = attempted_video_ids()
    open_videos = political[~political["video_id"].isin(attempted)]
    print(
        f"\n{len(open_videos):,}/{len(political):,} davon noch ohne "
        "Transkript-Versuch (transcript_store)."
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for suffix, df in [("all", political), ("open", open_videos)]:
        records = (
            df[["video_id", "channel_id"]]
            .drop_duplicates()
            .to_dict("records")
        )
        out_path = OUTPUT_DIR / f"{OUTPUT_NAME}_{suffix}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        print(f"Geschrieben: {out_path} ({len(records)} Video-IDs)")


if __name__ == "__main__":
    main()

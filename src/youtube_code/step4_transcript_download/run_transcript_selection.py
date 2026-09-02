"""
Duennes Runner-Skript: waehlt ueber MODE eine der drei
COMPLETE_PROCESS.md-Schritt-4-Konfigurationen aus (select_targets.py) und
uebergibt das Ergebnis an download_transcripts().

Config-Konstanten am Kopf anpassen, dann ausfuehren:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step4_transcript_download.run_transcript_selection
"""
import pandas as pd

from youtube_code.step4_transcript_download.download_transcripts import download_transcripts
from youtube_code.step4_transcript_download.select_targets import (
    select_baseline_targets,
    select_cell_fill_targets,
    select_war_period_targets,
)
from youtube_code.config import SAMPLES


# ============================================================
# CONFIG
# ============================================================

# "baseline" | "cell_fill" | "war_period"
MODE = "baseline"

# Gemeinsam: None = alle Kanaele (nur bei "cell_fill" ist eine konkrete Liste Pflicht).
channel_path = SAMPLES / "russia_longitudinal_v1" / "channel_sample_provenance.csv"
channels = pd.read_csv(channel_path, usecols=["channel_id"], dtype={"channel_id": "string"})["channel_id"].tolist()
CHANNEL_IDS = channels

# Nur fuer MODE == "cell_fill":
VIDEOS_PER_CELL = 5
TOPIC = "russia_ukraine_war"
GRANULARITY = "monat"  # "monat" | "quartal"

# Nur fuer MODE == "war_period":
START_DATE = "2022-02-20"
END_DATE = "2022-03-10"


def select_targets():
    if MODE == "baseline":
        return select_baseline_targets(channel_ids=CHANNEL_IDS)
    if MODE == "cell_fill":
        if not CHANNEL_IDS:
            raise ValueError("MODE='cell_fill' braucht eine konkrete CHANNEL_IDS-Liste.")
        return select_cell_fill_targets(
            CHANNEL_IDS, videos_per_cell=VIDEOS_PER_CELL, topic=TOPIC, granularity=GRANULARITY,
        )
    if MODE == "war_period":
        return select_war_period_targets(START_DATE, END_DATE, channel_ids=CHANNEL_IDS, topic=TOPIC)
    raise ValueError(f"Unbekannter MODE {MODE!r}, erwartet: baseline | cell_fill | war_period")


def main() -> None:
    targets = select_targets()
    print(f"MODE={MODE!r}: {len(targets)} Video-IDs ausgewaehlt.")
    if targets.empty:
        print("Keine Videos ausgewaehlt - Abbruch.")
        return

    channel_map = targets.set_index("video_id")["channel_id"].to_dict()
    download_transcripts(targets["video_id"].tolist(), channel_map=channel_map, confirm_speed=False)


if __name__ == "__main__":
    main()

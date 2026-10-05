"""
Adhoc: Politisch klassifizierte Videos (politics_final == 1 im
screening_state_store) finden, fuer die ein heruntergeladenes Transkript
vorliegt (transcript_store.has_transcript - status "OK" UND tatsaechlicher
Transkriptinhalt), die aber noch NICHT mit dem POPULISMUS_P-Prompt
klassifiziert wurden (llm_run_store.get_video_ids_for_prompt).

Analog zu find_political_transcripts_missing_ideologie.py, nur fuer
POPULISMUS_P statt IDEOLOGIE_I. Bewusst NICHT auf das Baseline-Fenster
(interval_index) eingeschraenkt: deskriptiv_aggregation.py braucht die volle
Zeitreihe je Kanal (Vor- und Nachkriegsperioden), nicht nur die Baseline.

Nutzung: unten ggf. PROMPT_ID/SOURCE anpassen, dann:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
      scripts/adhoc/find_political_transcripts_missing_populismus.py

Schreibt eine CSV mit den Spalten video_id, channel_id nach
scripts/adhoc/output/political_transcripts_missing_populismus.csv.
"""
from pathlib import Path

import pandas as pd

from youtube_code.store.screening_state_store import get_state
from youtube_code.store.transcript_store import has_transcript
from youtube_code.store.llm_run_store import get_video_ids_for_prompt
from youtube_code.config import EXPLORATION

PROMPT_ID = "POPULISMUS_P"
SOURCE = "segment_analysis_active"  # llm_run_store-Quelle fuer Segment-Klassifikation

OUTPUT_DIR = EXPLORATION
OUTPUT_NAME = "political_transcripts_missing_populismus.csv"


def main():
    political = get_state(politics_final=1)[["video_id", "channel_id"]].drop_duplicates()
    print(f"{len(political):,} politisch klassifizierte Videos (politics_final==1).")

    downloaded = has_transcript(political["video_id"].tolist())
    political = political[political["video_id"].isin(downloaded)]
    print(f"{len(political):,} davon mit heruntergeladenem Transkript (transcript_store.has_transcript).")

    classified = set(get_video_ids_for_prompt(PROMPT_ID, source=SOURCE))
    print(f"{len(classified):,} Videos bereits mit {PROMPT_ID} klassifiziert (ueber alle Runs).")

    missing = political[~political["video_id"].isin(classified)].copy()
    print(f"\n{len(missing):,} politische Videos mit Transkript, aber noch ohne {PROMPT_ID}-Klassifikation.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / OUTPUT_NAME
    missing.to_csv(out_path, index=False)
    print(f"Geschrieben: {out_path} ({len(missing)} Video-IDs)")


if __name__ == "__main__":
    main()

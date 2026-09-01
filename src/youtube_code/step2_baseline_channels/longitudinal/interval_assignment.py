"""
Kleine, aktiv gepflegte Hilfsfunktionen fuer die Interval-/Rank-Logik des
longitudinalen Screenings - herausgeloest aus dem inzwischen archivierten
`youtube_code.archive.politics_screening_legacy.prepare_longitudinal_screening`
(siehe dort), weil `append_channels_to_state.py` (aktiver Teil von Schritt 2)
weiterhin genau diese beiden Funktionen braucht und nicht von "totem,
nicht mehr gepflegtem" Code abhaengen soll.
"""

import hashlib

import pandas as pd


def stable_random_key(video_id: str, seed: int) -> int:
    """Return a reproducible pseudo-random key without global RNG state."""
    value = f"{seed}|{video_id}".encode("utf-8")
    return int.from_bytes(
        hashlib.blake2b(value, digest_size=8).digest(),
        byteorder="big",
        signed=False,
    )


def assign_intervals(
    period: pd.Series,
    interval_start: int,
    interval_size: int,
) -> tuple[pd.Series, pd.Series]:
    """
    Group consecutive periods into fixed-width intervals.

    Intervals are anchored at interval_start, e.g. with interval_start=-12
    and interval_size=3: [-12,-11,-10], [-9,-8,-7], ..., [0,1,2], [3,4,5], ...
    Requires period >= interval_start.
    """
    interval_index = (
        (period - interval_start) // interval_size
    ).astype("int32")
    interval_start_period = interval_start + interval_index * interval_size
    interval_end_period = interval_start_period + interval_size - 1
    interval_label = (
        interval_start_period.astype("string")
        + "_to_"
        + interval_end_period.astype("string")
    )
    return interval_index, interval_label

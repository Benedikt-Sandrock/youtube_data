"""
Klassifiziert Videos nach Themen-Relevanz (Schritt 3 aus COMPLETE_PROCESS.md,
Standard-Topic "russia_ukraine_war") und schreibt das Ergebnis nach
video_registry.video_topic_relevance.

Ablauf:
    1. get_videos_with_text(channel_ids=CHANNEL_FILTER) laedt Kandidaten
       (video_id, channel_id, published_at, title, description).
    2. learn_boilerplate() lernt pro Kanal wiederkehrende Beschreibungs-
       zeilen (siehe boilerplate.py) - EINMAL auf demselben DataFrame.
    3. classify() prueft Titel und boilerplate-bereinigte Beschreibung
       getrennt gegen die Keyword-Sets aus topic_keywords.py.
    4. Ergebnis wird batchweise ueber upsert_topic_relevance() geschrieben.

DRY_RUN=True (Default) druckt nur eine Zusammenfassung, ohne zu schreiben -
erst nach Pruefung auf False setzen (Muster: MODE/DRY_RUN in
step1_sample/channel_all_videos.py bzw. step2_baseline_channels/
update_screening_state.py).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from youtube_code.step3_war_videos.boilerplate import clean_description, learn_boilerplate
from youtube_code.step3_war_videos.topic_keywords import (
    KEYWORD_SET_VERSION,
    is_relevant,
    match_flags,
)
from youtube_code.store import video_registry


# ============================================================
# CONFIG
# ============================================================

TOPIC = "russia_ukraine_war"

# None = alle Kanaele in videos; sonst Liste von channel_ids.
CHANNEL_FILTER = None

# Anzahl Zeilen je upsert_topic_relevance()-Batch.
BATCH_SIZE = 500

# Erst mit True die gedruckte Zusammenfassung pruefen, dann auf False
# setzen, um tatsaechlich in video_topic_relevance zu schreiben.
DRY_RUN = True


def classify(df: pd.DataFrame, boiler: dict) -> pd.DataFrame:
    """
    Klassifiziert jede Zeile aus df (video_id, channel_id, title, description)
    gegen TOPIC. Rueckgabe: DataFrame mit den video_topic_relevance-Spalten.
    """
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    for row in df.itertuples(index=False):
        # pandas.read_sql_query liefert eine fehlende description aus dem
        # LEFT JOIN als float('nan'), nicht None/"" - deshalb isinstance-Check
        # statt "or ''" (nan ist truthy, "not nan" waere sonst False).
        description = row.description if isinstance(row.description, str) else ""
        title_only = int(not description)
        desc_clean = clean_description(description, row.channel_id, boiler)

        title = row.title if isinstance(row.title, str) else ""
        flags = match_flags(title, desc_clean)
        matched = [k for k, v in flags.items() if v]

        rows.append({
            "video_id": row.video_id,
            "topic": TOPIC,
            "is_relevant": int(is_relevant(flags)),
            "matched_keywords": matched,
            "title_only": title_only,
            "keyword_set_version": KEYWORD_SET_VERSION,
            "classified_at": now,
        })
    return pd.DataFrame(rows)


def main() -> None:
    df = video_registry.get_videos_with_text(channel_ids=CHANNEL_FILTER)
    print(f"{len(df):,} Videos geladen (CHANNEL_FILTER={CHANNEL_FILTER!r}).")
    if df.empty:
        print("Keine Videos gefunden - Abbruch.")
        return

    boiler = learn_boilerplate(df)
    print(f"Boilerplate gelernt fuer {len(boiler):,} von {df.channel_id.nunique():,} Kanaelen.")

    result = classify(df, boiler)
    n_relevant = int(result.is_relevant.sum())
    n_title_only = int(result.title_only.sum())
    print(f"Topic '{TOPIC}': {n_relevant:,} von {len(result):,} Videos als relevant "
          f"klassifiziert ({n_title_only:,} davon ohne Beschreibung, nur Titel geprueft).")

    if DRY_RUN:
        print("\nDRY_RUN=True - nichts geschrieben. Stichprobe relevanter Videos:")
        print(result[result.is_relevant == 1].head(10).to_string(index=False))
        return

    written = 0
    records = result.to_dict("records")
    for i in range(0, len(records), BATCH_SIZE):
        written += video_registry.upsert_topic_relevance(records[i:i + BATCH_SIZE])
    print(f"\n{written:,} Zeilen in video_topic_relevance geschrieben.")


if __name__ == "__main__":
    main()

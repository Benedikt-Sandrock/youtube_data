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

import time
from collections import Counter
from datetime import datetime, timezone

import pandas as pd

from youtube_code.step3_war_videos.boilerplate import clean_description, learn_boilerplate
from youtube_code.step3_war_videos.topic_keywords import (
    KEYWORD_SET_VERSION,
    KW_RE,
    is_relevant_vectorized,
)
from youtube_code.store import video_registry
from youtube_code.config import SAMPLES

# ============================================================
# CONFIG
# ============================================================

TOPIC = "russia_ukraine_war"

# None = alle Kanaele in videos; sonst Liste von channel_ids.
channel_path = SAMPLES / "russia_longitudinal_v1" / "channel_sample_provenance.csv"
channels = pd.read_csv(channel_path, usecols=["channel_id"], dtype={"channel_id": "string"})["channel_id"].tolist()
CHANNEL_FILTER = channels

# Anzahl Zeilen je upsert_topic_relevance()-Batch.
BATCH_SIZE = 500

# Anzahl Zeilen je classify()-Chunk. Nur fuer Zwischenstand-Ausgaben und
# begrenzten Speicherbedarf relevant, nicht fuer die Korrektheit - das
# Ergebnis ist unabhaengig von der Chunk-Groesse identisch.
CLASSIFY_CHUNK_SIZE = 100_000

# Erst mit True die gedruckte Zusammenfassung pruefen, dann auf False
# setzen, um tatsaechlich in video_topic_relevance zu schreiben.
DRY_RUN = False


def classify(df: pd.DataFrame, boiler: dict) -> pd.DataFrame:
    """
    Klassifiziert jede Zeile aus df (video_id, channel_id, title, description)
    gegen TOPIC. Rueckgabe: DataFrame mit den video_topic_relevance-Spalten.

    Vektorisiert statt zeilenweise: title/description werden je Keyword-Set
    per pandas.Series.str.contains() auf einmal gegen die kompilierten Regexe
    geprueft, statt pro Video vier re.search()-Aufrufe in einem Python-Loop
    zu machen. Die (teure) Boilerplate-Bereinigung laeuft weiterhin
    zeilenweise, aber nur noch fuer Videos aus Kanaelen, fuer die ueberhaupt
    Boilerplate gelernt wurde (siehe boilerplate.clean_description) - der
    Regelfall ohne Boilerplate braucht gar keine Zeilenzerlegung/Hashing mehr.
    """
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    title = df["title"].fillna("")
    # pandas.read_sql_query liefert eine fehlende description aus dem
    # LEFT JOIN als float('nan'), nicht None/"" - fillna deckt das ab.
    desc_filled = df["description"].fillna("")
    title_only = (desc_filled == "").astype(int)

    # isin() gegen ein leeres dict.keys() liefert einfach eine All-False-
    # Series - kein Sonderfall fuer "kein Kanal hat Boilerplate" noetig.
    needs_clean = df["channel_id"].isin(boiler.keys()) & (desc_filled != "")
    desc_clean = desc_filled.copy()
    if needs_clean.any():
        subset = df.loc[needs_clean]
        desc_clean.loc[needs_clean] = [
            clean_description(desc, ch, boiler)
            for desc, ch in zip(subset["description"], subset["channel_id"])
        ]

    flags = {}
    for k, rx in KW_RE.items():
        flags[f"{k}_title"] = title.str.contains(rx, na=False)
        flags[f"{k}_desc"] = desc_clean.str.contains(rx, na=False)

    flag_names = list(flags.keys())
    flag_columns = [flags[name].to_numpy() for name in flag_names]
    matched_keywords = [
        [name for name, hit in zip(flag_names, row) if hit]
        for row in zip(*flag_columns)
    ]

    return pd.DataFrame({
        "video_id": df["video_id"].values,
        "topic": TOPIC,
        "is_relevant": is_relevant_vectorized(flags).astype(int).values,
        "matched_keywords": matched_keywords,
        "title_only": title_only.values,
        "keyword_set_version": KEYWORD_SET_VERSION,
        "classified_at": now,
    })


def main() -> None:
    t0 = time.perf_counter()
    n_channels_filter = len(CHANNEL_FILTER) if CHANNEL_FILTER is not None else None

    df = video_registry.get_videos_with_text(channel_ids=CHANNEL_FILTER)
    if df.empty:
        print(f"0 Videos geladen (CHANNEL_FILTER: {n_channels_filter} Kanaele) - Abbruch.")
        return
    print(f"{len(df):,} Videos aus {df.channel_id.nunique():,} Kanaelen geladen "
          f"(CHANNEL_FILTER: {n_channels_filter} Kanaele) - Topic '{TOPIC}'.")

    boiler = learn_boilerplate(df)
    print(f"Boilerplate gelernt fuer {len(boiler):,} von {df.channel_id.nunique():,} Kanaelen "
          f"({time.perf_counter() - t0:.0f}s).")

    # In Chunks klassifizieren statt in einem Rutsch - Ergebnis ist identisch,
    # liefert aber regelmaessige Zwischenstaende bei grossen Video-Mengen.
    chunks = []
    n_done = 0
    for start in range(0, len(df), CLASSIFY_CHUNK_SIZE):
        chunk = df.iloc[start:start + CLASSIFY_CHUNK_SIZE]
        chunks.append(classify(chunk, boiler))
        n_done += len(chunk)
        print(f"  klassifiziert: {n_done:,}/{len(df):,} Videos "
              f"({n_done / len(df):.0%}, {time.perf_counter() - t0:.0f}s)...")
    result = pd.concat(chunks, ignore_index=True)

    n_relevant = int(result.is_relevant.sum())
    n_title_only = int(result.title_only.sum())
    print(f"\nTopic '{TOPIC}': {n_relevant:,} von {len(result):,} Videos als relevant "
          f"klassifiziert ({n_relevant / len(result):.1%}); "
          f"{n_title_only:,} davon ohne Beschreibung (nur Titel geprueft).")

    flag_counts = Counter(kw for row in result.matched_keywords for kw in row)
    print("Treffer je Keyword-Flag (ein Video kann mehrere Flags haben):")
    for flag in ("ukr_core_title", "ukr_core_desc", "ukr_wide_title", "ukr_wide_desc"):
        print(f"  {flag}: {flag_counts.get(flag, 0):,}")

    if DRY_RUN:
        print("\nDRY_RUN=True - nichts geschrieben. Stichprobe relevanter Videos:")
        print(result[result.is_relevant == 1].head(10).to_string(index=False))
        print(f"\nGesamtdauer: {time.perf_counter() - t0:.0f}s.")
        return

    written = 0
    n_batches = (len(result) + BATCH_SIZE - 1) // BATCH_SIZE
    # .to_dict("records") erst pro Batch statt einmal fuer das komplette
    # Ergebnis - vermeidet die zusaetzliche Kopie als eine grosse Liste im
    # Speicher und liefert nebenbei die Fortschrittsanzeige unten.
    for i in range(0, len(result), BATCH_SIZE):
        batch = result.iloc[i:i + BATCH_SIZE].to_dict("records")
        written += video_registry.upsert_topic_relevance(batch)
        batch_no = i // BATCH_SIZE + 1
        if batch_no % 20 == 0 or batch_no == n_batches:
            print(f"  geschrieben: {written:,}/{len(result):,} Zeilen "
                  f"(Batch {batch_no}/{n_batches})...")
    print(f"\n{written:,} Zeilen in video_topic_relevance geschrieben. "
          f"Gesamtdauer: {time.perf_counter() - t0:.0f}s.")


if __name__ == "__main__":
    main()

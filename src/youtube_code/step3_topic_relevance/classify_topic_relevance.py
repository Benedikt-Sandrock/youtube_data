"""
Klassifiziert Videos nach Themen-Relevanz (Schritt 3 aus COMPLETE_PROCESS.md)
und schreibt das Ergebnis nach video_registry.video_topic_relevance. Fuenf
Themen stehen zur Verfuegung (siehe topic_keywords.TOPIC_KEYWORDS):
russia_ukraine_war, corona_pandemic, migration, economy_general, energy -
Standard ist TOPICS_TO_RUN = alle fuenf.

Ablauf:
    1. get_videos_with_text(channel_ids=CHANNEL_FILTER) laedt Kandidaten
       (video_id, channel_id, published_at, title, description).
    2. learn_boilerplate() lernt pro Kanal wiederkehrende Beschreibungs-
       zeilen (siehe boilerplate.py) - EINMAL auf demselben DataFrame,
       unabhaengig davon, wie viele Themen klassifiziert werden.
    3. classify() prueft Titel und boilerplate-bereinigte Beschreibung
       getrennt gegen die Keyword-Sets aus topic_keywords.py, fuer jedes
       Thema in TOPICS_TO_RUN, und liefert ein langes DataFrame (eine Zeile
       je video_id x topic).
    4. Ergebnis wird batchweise ueber upsert_topic_relevance() geschrieben -
       das Batch-Upsert-Schema liest ohnehin pro Record eine eigene
       topic-Spalte, bleibt also unveraendert.

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
import numpy as np

from youtube_code.step3_topic_relevance.boilerplate import clean_description, learn_boilerplate
from youtube_code.step3_topic_relevance.topic_keywords import (
    KEYWORD_SET_VERSION,
    KW_RE,
    TOPIC_KEYWORDS,
    is_relevant_vectorized,
)
from youtube_code.store import video_registry
from youtube_code.config import SAMPLES

# ============================================================
# CONFIG
# ============================================================

# Welche Themen aus topic_keywords.TOPIC_KEYWORDS klassifiziert werden.
# Fuer Testlaeufe auf ein einzelnes Thema einschraenken, z.B. ["energy"].
TOPICS_TO_RUN = list(TOPIC_KEYWORDS.keys())

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


def classify(df: pd.DataFrame, boiler: dict, topics: list = None) -> pd.DataFrame:
    """
    Klassifiziert jede Zeile aus df (video_id, channel_id, title, description)
    gegen jedes Thema aus topics (Default: TOPICS_TO_RUN). Rueckgabe: langes
    DataFrame mit den video_topic_relevance-Spalten, eine Zeile je
    video_id x topic.

    Vektorisiert statt zeilenweise: title/description werden je
    Keyword-Set (ueber ALLE Themen hinweg, einmal) per
    pandas.Series.str.contains() auf einmal gegen die kompilierten Regexe
    geprueft, statt pro Video und Thema re.search()-Aufrufe in einem
    Python-Loop zu machen. Die (teure) Boilerplate-Bereinigung laeuft
    weiterhin zeilenweise, aber nur noch fuer Videos aus Kanaelen, fuer die
    ueberhaupt Boilerplate gelernt wurde (siehe boilerplate.clean_description)
    - der Regelfall ohne Boilerplate braucht gar keine
    Zeilenzerlegung/Hashing mehr. desc_clean wird ebenfalls nur einmal pro
    Chunk berechnet und dann gegen alle Themen gematcht.
    """
    topics = topics if topics is not None else TOPICS_TO_RUN
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

    # Flags fuer ALLE KW_RE-Eintraege (also ueber alle fuenf Themen) einmal
    # berechnen, unabhaengig davon, welche Themen in topics angefragt sind -
    # guenstig, weil title/desc_clean ohnehin je Chunk nur einmal vorliegen.
    flags = {}
    for k, rx in KW_RE.items():
        flags[f"{k}_title"] = title.str.contains(rx, na=False)
        flags[f"{k}_desc"] = desc_clean.str.contains(rx, na=False)

    video_ids = df["video_id"].values
    n = len(df)
    frames = []
    for topic in topics:
        prefix = TOPIC_KEYWORDS[topic]["prefix"]
        tier_names = [t for t in TOPIC_KEYWORDS[topic] if t != "prefix"]
        flag_names = [f"{prefix}_{tier}_{loc}" for tier in tier_names for loc in ("title", "desc")]
        topic_flags = {name: flags[name] for name in flag_names}

        matched_keywords = [[] for _ in range(n)]
        for name in flag_names:
            idx = np.flatnonzero(topic_flags[name].to_numpy())
            for i in idx:
                matched_keywords[i].append(name)

        frames.append(pd.DataFrame({
            "video_id": video_ids,
            "topic": topic,
            "is_relevant": is_relevant_vectorized(topic_flags).astype(int).values,
            "matched_keywords": matched_keywords,
            "title_only": title_only.values,
            "keyword_set_version": KEYWORD_SET_VERSION[topic],
            "classified_at": now,
        }))

    return pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]


def main() -> None:
    t0 = time.perf_counter()
    n_channels_filter = len(CHANNEL_FILTER) if CHANNEL_FILTER is not None else None

    df = video_registry.get_videos_with_text(channel_ids=CHANNEL_FILTER)
    if df.empty:
        print(f"0 Videos geladen (CHANNEL_FILTER: {n_channels_filter} Kanaele) - Abbruch.")
        return
    print(f"{len(df):,} Videos aus {df.channel_id.nunique():,} Kanaelen geladen "
          f"(CHANNEL_FILTER: {n_channels_filter} Kanaele) - Themen: {TOPICS_TO_RUN}.")

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

    print(f"\n{len(result):,} Zeilen ueber {result.topic.nunique()} Themen klassifiziert:")
    for topic, group in result.groupby("topic"):
        n_relevant = int(group.is_relevant.sum())
        n_title_only = int(group.title_only.sum())
        print(f"\nTopic '{topic}': {n_relevant:,} von {len(group):,} Videos als relevant "
              f"klassifiziert ({n_relevant / len(group):.1%}); "
              f"{n_title_only:,} davon ohne Beschreibung (nur Titel geprueft).")

        flag_counts = Counter(kw for row in group.matched_keywords for kw in row)
        prefix = TOPIC_KEYWORDS[topic]["prefix"]
        tier_names = [t for t in TOPIC_KEYWORDS[topic] if t != "prefix"]
        flags = [f"{prefix}_{tier}_{loc}" for tier in tier_names for loc in ("title", "desc")]
        print("  Treffer je Keyword-Flag (ein Video kann mehrere Flags haben):")
        for flag in flags:
            print(f"    {flag}: {flag_counts.get(flag, 0):,}")

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

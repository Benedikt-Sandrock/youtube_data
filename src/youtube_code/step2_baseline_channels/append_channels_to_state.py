# -*- coding: utf-8 -*-
"""
Fuegt neu gesammelte Videos (Titel + Beschreibung) fuer eine Liste von Kanaelen als
neue Kandidatenzeilen zum Screening-State (screening_state_store) hinzu - mit exakt
derselben Interval-/Rank-Logik wie prepare_longitudinal_screening.py, aber als APPEND
statt Neuaufbau, damit bestehende Labels/screening_round-Zuweisungen erhalten bleiben.

Kontext: manche Kanaele stehen schon im State (z.B. nur mit Kriegsperioden-Zeilen aus
einem frueheren TARGETED_SEARCH_YTDLP-Lauf), aber nicht mit Baseline-Zeilen (period<0).
Fuer solche Kanaele werden automatisch nur die fehlenden Baseline-Zeilen ergaenzt -
Videos mit period>=0 werden verworfen, falls der Kanal schon Zeilen im State hat.

Nutzung:
  1. Video-IDs fuer die Zielkanaele sammeln (channel_all_videos.py, TARGETED_SEARCH
     oder TARGETED_SEARCH_YTDLP je nach Kanalgroesse).
  2. Beschreibungen dafuer holen (metadata_collection.py, video_metadata=True,
     DETAILED=True) -> landet direkt in der zentralen video_registry.
  3. Dieses Skript nur noch mit NEW_CHANNELS_LIST (CSV mit channel_id-Spalte, aus
     Schritt 1) aufrufen - die Videos (Titel/Beschreibung) werden hier automatisch
     per video_registry.get_videos_with_text(channel_ids=...) geladen, keine separate
     Export-Datei mehr noetig.

Seit Phase 4d schreibt dieses Skript nur noch die tatsaechlich neuen Kandidatenzeilen
per screening_state_store.upsert_state_rows() (kein Vollkopie-CSV-Rewrite mehr, kein
manuelles Backup noetig - SQLite ist die alleinige Ablage).
"""
import argparse

import pandas as pd

from youtube_code.step2_baseline_channels.longitudinal.screening_config import (
    INTERVAL_START,
    INTERVAL_SIZE,
    TARGET_POLITICAL_PER_INTERVAL,
    TARGET_WITH_BUFFER_PER_INTERVAL,
    SELECTION_SEED,
)
from youtube_code.step2_baseline_channels.interval_assignment import (
    assign_intervals,
    stable_random_key,
)
from youtube_code.store import screening_state_store, video_registry

REQUIRED_COLUMNS = ["video_id", "channel_id", "channel_title", "published_at", "title", "description"]
REFERENCE_DATE = pd.Timestamp("2022-02-24", tz="UTC")


def calculate_period(published_at: pd.Series, anchor: pd.Timestamp) -> pd.Series:
    month_diff = (published_at.dt.year - anchor.year) * 12 + (published_at.dt.month - anchor.month)
    month_diff = month_diff - (published_at.dt.day < anchor.day).astype(int)
    return month_diff.astype("int64")


def main(new_channels_list: str, dry_run: bool = False) -> None:
    neue_kanaele = pd.read_csv(new_channels_list, dtype={"channel_id": "string"})
    ziel_ids = set(neue_kanaele["channel_id"])
    print(f"{len(ziel_ids)} Zielkanaele aus {new_channels_list}.")

    state = screening_state_store.get_state()
    print(f"Bestehender State: {len(state):,} Zeilen, {state['channel_id'].nunique():,} Kanaele.")

    bereits_im_state = ziel_ids & set(state["channel_id"])
    komplett_neu = ziel_ids - bereits_im_state
    print(f"{len(bereits_im_state)} Kanaele bereits im State -> nur fehlende period<0 (Baseline) wird ergaenzt.")
    print(f"{len(komplett_neu)} Kanaele komplett neu -> voller Zeitraum (period >= {INTERVAL_START}) wird ergaenzt.")

    df = video_registry.get_videos_with_text(channel_ids=sorted(ziel_ids))
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"video_registry.get_videos_with_text() liefert nicht alle benoetigten Spalten: {sorted(missing)}")
    if df.empty:
        raise ValueError(
            "Keine Videos in der video_registry fuer diese Zielkanaele - erst Schritt 2 "
            "(channel_all_videos.py) und Schritt 3 (metadata_collection.py) fuer diese "
            "Kanaele ausfuehren."
        )

    print(f"{len(df):,} Videos aus der video_registry fuer die Zielkanaele.")
    df = df.drop_duplicates(subset="video_id", keep="last")

    bereits_bekannte_ids = set(state["video_id"])
    vorher = len(df)
    df = df[~df["video_id"].isin(bereits_bekannte_ids)]
    print(f"{vorher - len(df):,} Videos waren bereits im State (video_id-Dublette) -> entfernt.")

    df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    df = df.dropna(subset=["video_id", "channel_id", "published_at"])

    df["period"] = calculate_period(df["published_at"], REFERENCE_DATE)

    below_start = df["period"].lt(INTERVAL_START)
    print(f"{below_start.sum():,} Videos mit period < {INTERVAL_START} -> werden verworfen.")
    df = df.loc[~below_start].copy()

    nur_baseline_maske = df["channel_id"].isin(bereits_im_state) & df["period"].ge(0)
    print(f"{nur_baseline_maske.sum():,} Kriegsperioden-Videos bei bereits-vorhandenen Kanaelen -> werden verworfen (schon im State).")
    df = df.loc[~nur_baseline_maske].copy()

    if df.empty:
        raise ValueError("Keine Videos nach dem Zuschnitt uebrig - nichts zu ergaenzen.")

    df["interval_index"], df["interval_label"] = assign_intervals(
        period=df["period"], interval_start=INTERVAL_START, interval_size=INTERVAL_SIZE
    )

    df["_random_order"] = df["video_id"].map(lambda vid: stable_random_key(video_id=str(vid), seed=SELECTION_SEED))
    df = df.sort_values(["channel_id", "period", "_random_order", "published_at"], ascending=[True, True, True, False])
    df["rank_within_period"] = df.groupby(["channel_id", "period"], sort=False).cumcount().astype("int32")

    df = df.sort_values(["channel_id", "interval_index", "rank_within_period", "period"], ascending=[True, True, True, True])
    df["candidate_rank"] = df.groupby(["channel_id", "interval_index"], sort=False).cumcount().astype("int32")
    df = df.drop(columns="_random_order")

    df["target_political_per_interval"] = TARGET_POLITICAL_PER_INTERVAL
    df["target_with_buffer_per_interval"] = TARGET_WITH_BUFFER_PER_INTERVAL

    for col in ["politics_title", "politics_title_desc", "politics_final"]:
        df[col] = pd.Series(pd.NA, index=df.index, dtype="Int8")
    df["screening_round"] = pd.Series(pd.NA, index=df.index, dtype="Int16")
    df["selected_for_transcript"] = pd.Series(pd.NA, index=df.index, dtype="boolean")
    df["is_transcript_reserve"] = pd.Series(pd.NA, index=df.index, dtype="boolean")

    df = df[[c for c in state.columns if c in df.columns]]
    fehlende_spalten = set(state.columns) - set(df.columns)
    if fehlende_spalten:
        raise ValueError(f"Neue Zeilen fehlen Spalten aus dem State: {sorted(fehlende_spalten)}")

    print(f"\n{len(df):,} neue Kandidatenzeilen fuer {df['channel_id'].nunique()} Kanaele.")
    print("Verteilung interval_index (neue Zeilen):")
    print(df["interval_index"].value_counts().sort_index().to_string())

    if dry_run:
        print("\nDRY RUN: State-Datei wurde NICHT veraendert.")
        return

    written = screening_state_store.upsert_state_rows(df.to_dict("records"))
    print(
        f"\nGespeichert in screening_state_store: {written:,} neue Zeilen "
        f"({len(state) + len(df):,} Zeilen gesamt, vorher {len(state):,})."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channels", required=True, help="CSV mit channel_id-Spalte (Zielkanaele, aus Schritt 1).")
    parser.add_argument("--dry-run", action="store_true", help="Nur Plan ausgeben, Store nicht schreiben.")
    args = parser.parse_args()

    main(args.channels, dry_run=args.dry_run)

# -*- coding: utf-8 -*-
"""
Synchronisiert den Screening-State (screening_state_store) mit dem
aktuellen Stand der video_registry fuer eine Menge von Zielkanaelen:
ergaenzt Videos, die in der Registry aber (noch) nicht im State stehen, und
korrigiert channel_id-Drift bei bereits vorhandenen State-Zeilen (siehe
.claude/plans/screening_state_update.md).

Historie/Hintergrund: Vor diesem Umbau fuegte dieses Skript ausschliesslich
komplett neue Kanaele hinzu und nahm dabei faelschlich an, ein Kanal mit
irgendeiner Zeile im State sei bereits vollstaendig erfasst (dann wurden
saemtliche Kriegsperioden-Videos verworfen, nur period<0 wurde ergaenzt) -
das liess den State bei laufend waechsender video_registry
(metadata_collection.py) zunehmend hinter der Registry zurueckfallen
(Diagnose in scripts/adhoc/sample_creation_diagnostics.py, u.a. WELT:
+3489 fehlende video_ids). Der Sync prueft jetzt PRO KANAL, welche
registry-video_ids noch fehlen, unabhaengig davon, ob der Kanal schon
(unvollstaendige) Zeilen im State hat. Zusaetzlich neu: channel_id-Drift-
Korrektur fuer Videos, deren Kanalzuordnung in der Registry nachtraeglich
korrigiert wurde, der State aber noch die alte channel_id haelt.

Wird automatisch vor jeder neuen Screening-Runde fuer alle im State
vorkommenden Kanaele aufgerufen (siehe
longitudinal/create_longitudinal_screening.create_screening_round()), kann
aber auch manuell fuer eine explizite Kanalliste ausgefuehrt werden (z.B.
neu zum Sample hinzugefuegte Kanaele, deren Videos/Metadaten bereits per
channel_all_videos.py + metadata_collection.py in der video_registry
liegen):

    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \\
      src/youtube_code/step2_baseline_channels/append_channels_to_state.py \\
      --channels meine_kanaele.csv --dry-run

--channels erwartet eine CSV mit einer channel_id-Spalte.

Neue Kandidatenzeilen erhalten dieselbe Interval-/Rank-Logik wie zuvor
(assign_intervals/stable_random_key aus interval_assignment.py) und werden
per screening_state_store.upsert_state_rows() geschrieben (kein
Vollkopie-CSV-Rewrite, kein manuelles Backup noetig - SQLite ist die
alleinige Ablage). channel_id-Drift-Korrekturen werden als gezielte,
minimale upsert_state_rows()-Records (nur video_id + channel_id)
geschrieben - das Feld-fuer-Feld-COALESCE-Update-Muster von
upsert_state_rows() laesst dabei alle anderen Spalten (Labels,
screening_round, ...) unangetastet.

Jeder Lauf schreibt einen Report nach STATE_SYNC_LOG_DIR
(screening_config.py): eine Detail-CSV der neu ergaenzten video_ids, eine
nach channel_id+interval_label gruppierte Summary-CSV (Anzahl sowie
published_at-Min/Max je Gruppe, um zu erkennen, ob eine Luecke auf einen
bestimmten Zeitraum konzentriert ist), sowie - nur falls Drifts gefunden
wurden - eine Korrektur-CSV (video_id, alte/neue channel_id, channel_title).
Bei dry_run=True wird der Report als Vorschau geschrieben, aber nichts in
den Store geschrieben.

Bekannte, bewusst nicht behobene Einschraenkung: candidate_rank wird fuer
neu angehaengte Zeilen pro Sync-Lauf neu ab 0 vergeben und kann daher mit
bereits vorhandenen candidate_rank-Werten im selben Kanal-Intervall
kollidieren (reiner Sortier-Tiebreaker, keine Unique-Constraint - bestand
schon vor diesem Umbau genauso).
"""
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from youtube_code.step2_baseline_channels.interval_assignment import (
    assign_intervals,
    stable_random_key,
)
from youtube_code.step2_baseline_channels.longitudinal.screening_config import (
    INTERVAL_SIZE,
    INTERVAL_START,
    SELECTION_SEED,
    STATE_SYNC_LOG_DIR,
    TARGET_POLITICAL_PER_INTERVAL,
    TARGET_WITH_BUFFER_PER_INTERVAL,
)
from youtube_code.store import screening_state_store, video_registry

REFERENCE_DATE = pd.Timestamp("2022-02-24", tz="UTC")

DETAIL_COLUMNS = [
    "video_id", "channel_id", "channel_title", "published_at",
    "period", "interval_index", "interval_label",
]


@dataclass
class SyncReport:
    """Ergebnis eines sync_state_with_registry()-Laufs."""
    added: pd.DataFrame    # eine Zeile je neu ergaenzter video_id (DETAIL_COLUMNS)
    summary: pd.DataFrame  # nach channel_id+interval_label gruppiert
    drift: pd.DataFrame    # eine Zeile je channel_id-Korrektur (leer, falls keine)

    @property
    def n_added(self) -> int:
        return len(self.added)

    @property
    def n_corrected(self) -> int:
        return len(self.drift)


def calculate_period(published_at: pd.Series, anchor: pd.Timestamp) -> pd.Series:
    month_diff = (published_at.dt.year - anchor.year) * 12 + (published_at.dt.month - anchor.month)
    month_diff = month_diff - (published_at.dt.day < anchor.day).astype(int)
    return month_diff.astype("int64")


def _atomic_write_csv(data: pd.DataFrame, output_path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    data.to_csv(
        temporary_path, index=False, encoding="utf-8-sig",
        date_format="%Y-%m-%dT%H:%M:%SZ",
    )
    temporary_path.replace(output_path)


def find_missing_videos(channel_ids, known_video_ids: set) -> pd.DataFrame:
    """Registry-Videos der Zielkanaele (nach INTERVAL_START-Filter), deren
    video_id noch NIRGENDS im State vorkommt - nicht nur nicht unter diesem
    Kanal, das vermeidet Ueberschneidungen mit der Drift-Korrektur in
    find_channel_id_drift()."""
    df = video_registry.get_videos_with_text(channel_ids=sorted(channel_ids))
    if df.empty:
        return df.assign(period=pd.Series(dtype="int64"))

    df = df.drop_duplicates(subset="video_id", keep="last")
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    df = df.dropna(subset=["video_id", "channel_id", "published_at"])

    df["period"] = calculate_period(df["published_at"], REFERENCE_DATE)
    df = df.loc[df["period"].ge(INTERVAL_START)].copy()

    return df.loc[~df["video_id"].isin(known_video_ids)].copy()


def build_new_rows(missing: pd.DataFrame) -> pd.DataFrame:
    """Leitet aus fehlenden Registry-Videos vollstaendige neue State-Zeilen
    ab - identische Interval-/Rank-Logik wie im frueheren, rein
    Neuanlage-fokussierten Skript."""
    df = missing.copy()
    df["interval_index"], df["interval_label"] = assign_intervals(
        period=df["period"], interval_start=INTERVAL_START, interval_size=INTERVAL_SIZE
    )

    df["_random_order"] = df["video_id"].map(
        lambda vid: stable_random_key(video_id=str(vid), seed=SELECTION_SEED)
    )
    df = df.sort_values(
        ["channel_id", "period", "_random_order", "published_at"],
        ascending=[True, True, True, False],
    )
    df["rank_within_period"] = df.groupby(["channel_id", "period"], sort=False).cumcount().astype("int32")

    df = df.sort_values(
        ["channel_id", "interval_index", "rank_within_period", "period"],
        ascending=[True, True, True, True],
    )
    df["candidate_rank"] = df.groupby(["channel_id", "interval_index"], sort=False).cumcount().astype("int32")
    df = df.drop(columns="_random_order")

    df["target_political_per_interval"] = TARGET_POLITICAL_PER_INTERVAL
    df["target_with_buffer_per_interval"] = TARGET_WITH_BUFFER_PER_INTERVAL
    for col in ["politics_title", "politics_title_desc", "politics_final"]:
        df[col] = pd.Series(pd.NA, index=df.index, dtype="Int8")
    df["screening_round"] = pd.Series(pd.NA, index=df.index, dtype="Int16")
    df["selected_for_transcript"] = pd.Series(pd.NA, index=df.index, dtype="boolean")
    df["is_transcript_reserve"] = pd.Series(pd.NA, index=df.index, dtype="boolean")
    return df


def find_channel_id_drift(channel_ids) -> pd.DataFrame:
    """Zeilen im State, die aktuell einem der Zielkanaele zugeordnet sind,
    deren video_registry-channel_id aber davon abweicht (z.B. weil das
    Video nachtraeglich einem anderen Kanal zugeordnet wurde - Beispiel:
    ehemalige RTL-Videos gehoeren laut Registry jetzt zu "RTL Soap
    Classics"). Gibt video_id, channel_id_state (alt), channel_id_registry
    (neu) und channel_title (neu, nur fuer den Report) zurueck."""
    state_scope = screening_state_store.get_state(channel_ids=sorted(channel_ids))
    if state_scope.empty:
        return pd.DataFrame(columns=["video_id", "channel_id_state", "channel_id_registry", "channel_title"])

    registry = video_registry.get_video_metadata(
        video_ids=state_scope["video_id"].tolist(), duration_filter=False,
    )[["video_id", "channel_id", "channel_title"]]

    merged = state_scope[["video_id", "channel_id"]].merge(
        registry, on="video_id", how="inner", suffixes=("_state", "_registry")
    )
    return merged.loc[
        merged["channel_id_registry"].notna()
        & merged["channel_id_registry"].ne(merged["channel_id_state"])
    ].reset_index(drop=True)


def sync_state_with_registry(channel_ids, dry_run: bool = False) -> SyncReport:
    """Kernfunktion: ergaenzt fehlende Registry-Videos als neue State-Zeilen
    und korrigiert channel_id-Drift fuer die uebergebenen Zielkanaele.
    Schreibt bei dry_run=False in screening_state_store, gibt in jedem Fall
    einen SyncReport mit den betroffenen Zeilen zurueck."""
    channel_ids = sorted({str(c) for c in channel_ids if c})
    if not channel_ids:
        empty = pd.DataFrame(columns=DETAIL_COLUMNS)
        return SyncReport(added=empty, summary=empty, drift=empty)

    known_video_ids = set(screening_state_store.get_state()["video_id"])

    missing = find_missing_videos(channel_ids, known_video_ids)
    new_rows = build_new_rows(missing) if not missing.empty else missing
    drift = find_channel_id_drift(channel_ids)

    if not dry_run:
        if not new_rows.empty:
            state_cols = [c for c in screening_state_store.COLUMNS if c in new_rows.columns]
            missing_cols = set(screening_state_store.COLUMNS) - set(new_rows.columns)
            if missing_cols:
                raise ValueError(f"Neue Zeilen fehlen Spalten aus dem State: {sorted(missing_cols)}")
            screening_state_store.upsert_state_rows(new_rows[state_cols].to_dict("records"))
        if not drift.empty:
            correction_records = drift.rename(columns={"channel_id_registry": "channel_id"})[
                ["video_id", "channel_id"]
            ].to_dict("records")
            screening_state_store.upsert_state_rows(correction_records)

    if new_rows.empty:
        detail = pd.DataFrame(columns=DETAIL_COLUMNS)
    else:
        detail = new_rows[DETAIL_COLUMNS].copy()

    if detail.empty:
        summary = pd.DataFrame(
            columns=["channel_id", "interval_label", "n_added", "published_at_min", "published_at_max"]
        )
    else:
        summary = (
            detail.groupby(["channel_id", "interval_label"])
            .agg(
                n_added=("video_id", "size"),
                published_at_min=("published_at", "min"),
                published_at_max=("published_at", "max"),
            )
            .reset_index()
        )

    return SyncReport(added=detail, summary=summary, drift=drift)


def write_sync_report(report: SyncReport, log_dir=STATE_SYNC_LOG_DIR, timestamp: str = None) -> dict:
    """Schreibt die Report-CSVs (Detail, Summary, ggf. Korrektur) nach
    log_dir und gibt die geschriebenen Pfade zurueck."""
    timestamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    paths = {"added": log_dir / f"state_sync_{timestamp}_added.csv"}
    _atomic_write_csv(report.added, paths["added"])

    paths["summary"] = log_dir / f"state_sync_{timestamp}_summary.csv"
    _atomic_write_csv(report.summary, paths["summary"])

    if not report.drift.empty:
        paths["drift"] = log_dir / f"state_sync_{timestamp}_channel_id_corrections.csv"
        _atomic_write_csv(report.drift, paths["drift"])

    return paths


def print_sync_report(report: SyncReport, paths: dict) -> None:
    print("\n" + "=" * 60)
    print("STATE-SYNC MIT VIDEO_REGISTRY")
    print("=" * 60)
    print(f"Neu ergaenzte Zeilen   : {report.n_added:,}")
    print(f"channel_id-Korrekturen : {report.n_corrected:,}")
    if report.n_added:
        print("\nNeue Zeilen je interval_label:")
        print(report.added["interval_label"].value_counts().sort_index().to_string())
    print("\nReport geschrieben:")
    for kind, path in paths.items():
        print(f"  {kind}: {path}")
    print("=" * 60)


def main(new_channels_list: str, dry_run: bool = False) -> None:
    neue_kanaele = pd.read_csv(new_channels_list, dtype={"channel_id": "string"})
    ziel_ids = sorted(set(neue_kanaele["channel_id"]))
    print(f"{len(ziel_ids)} Zielkanaele aus {new_channels_list}.")

    report = sync_state_with_registry(ziel_ids, dry_run=dry_run)
    paths = write_sync_report(report)
    print_sync_report(report, paths)

    if dry_run:
        print("\nDRY RUN: Store wurde NICHT veraendert (Report ist Vorschau).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channels", required=True, help="CSV mit channel_id-Spalte (Zielkanaele).")
    parser.add_argument("--dry-run", action="store_true", help="Nur Report schreiben, Store nicht veraendern.")
    args = parser.parse_args()

    main(args.channels, dry_run=args.dry_run)

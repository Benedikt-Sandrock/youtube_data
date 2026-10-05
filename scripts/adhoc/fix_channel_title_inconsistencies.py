"""
Diagnose- und Reparaturskript: findet channel_ids in der video_registry
(videos-Tabelle), denen mehr als ein channel_title zugeordnet ist. Das
passiert typischerweise, weil sich ein Kanal seit dem jeweiligen Video-Fetch
umbenannt hat: videos.channel_title wird beim Insert per snippet.channelTitle
des zum Fetch-Zeitpunkt aktuellen Namens gesetzt und danach nie mehr
aktualisiert (siehe upsert_videos()/_UPSERT_SQL: bei einem Konflikt gewinnt
per COALESCE immer der ALTE Wert).

Fuer jede betroffene channel_id wird der AKTUELL bei YouTube hinterlegte
Kanal-Name per channel_id_to_name_batched() (youtube_code.utils.io)
abgefragt - bewusst nicht get_channel_metadata(), das channel_ids
ueberspringt, die laut video_registry.known_channel_ids() schon eine
channels-Zeile haben, und den dortigen (moeglicherweise ebenfalls
veralteten) Titel deshalb nie neu abfragen wuerde. Anschliessend werden alle
betroffenen Zeilen in videos.channel_title sowie - fuer dieselben
channel_ids - channels.title auf diesen aktuellen Namen vereinheitlicht, so
dass jeder channel_id danach nur noch genau ein (der aktuelle) channel_title
zugeordnet ist.

Standardmaessig ein Dry-Run (nur Diagnose-CSV, keine API-Calls, kein
Schreiben) - erst mit --apply werden die aktuellen Titel abgefragt und die
DB geschrieben.

Nutzung:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        scripts/adhoc/fix_channel_title_inconsistencies.py [--apply] [--limit N]
"""
import argparse
import sqlite3

import pandas as pd
from googleapiclient.discovery import build

from youtube_code.config import API_KEY_C, VALIDATION
from youtube_code.store.video_registry import DB_PATH
from youtube_code.utils import channel_id_to_name_batched

OUTPUT_FILE = VALIDATION / "channel_title_inconsistencies.csv"


def find_channel_ids_with_multiple_titles() -> pd.DataFrame:
    """
    Gibt ein DataFrame mit einer Zeile je channel_id zurueck, der in der
    videos-Tabelle mindestens zwei unterschiedliche channel_title zugeordnet
    sind: n_titles (Anzahl unterschiedlicher Titel), titles (Pipe-getrennt,
    zur Sichtkontrolle), n_videos (Anzahl betroffener Video-Zeilen).
    """
    con = sqlite3.connect(DB_PATH)
    try:
        distinct_titles = pd.read_sql_query(
            "SELECT channel_id, channel_title, COUNT(*) AS n_videos "
            "FROM videos "
            "WHERE channel_id IS NOT NULL AND channel_title IS NOT NULL "
            "GROUP BY channel_id, channel_title",
            con,
        )
    finally:
        con.close()

    n_titles_per_channel = distinct_titles.groupby("channel_id")["channel_title"].transform("size")
    affected = distinct_titles.loc[n_titles_per_channel >= 2]

    summary = (
        affected.groupby("channel_id")
        .agg(
            n_titles=("channel_title", "nunique"),
            titles=("channel_title", lambda s: " | ".join(s)),
            n_videos=("n_videos", "sum"),
        )
        .reset_index()
        .sort_values("n_titles", ascending=False)
    )
    return summary


def fetch_current_titles(channel_ids: list, youtube) -> dict:
    """
    Gibt ein Mapping channel_id -> aktueller channel_title zurueck (Wert
    None, falls der Kanal per API nicht mehr auffindbar ist, z.B. geloescht).
    Nutzt channel_id_to_name_batched() aus youtube_code.utils.io, das ohne
    Registry-Abgleich direkt den aktuellen Namen je ID abfragt.
    """
    names = channel_id_to_name_batched(youtube, channel_ids)
    return dict(zip(channel_ids, names))


def apply_current_titles(current_titles: dict) -> None:
    """
    Schreibt den aktuellen Titel in videos.channel_title und channels.title
    fuer alle uebergebenen channel_ids. channel_ids ohne per API abrufbaren
    aktuellen Titel (Wert None in current_titles) werden uebersprungen, damit
    ein bestehender Titel nie durch NULL ersetzt wird.
    """
    updates = [(title, cid) for cid, title in current_titles.items() if title]
    skipped = [cid for cid, title in current_titles.items() if not title]

    con = sqlite3.connect(DB_PATH)
    try:
        con.executemany("UPDATE videos SET channel_title = ? WHERE channel_id = ?", updates)
        con.executemany("UPDATE channels SET title = ? WHERE channel_id = ?", updates)
        con.commit()
    finally:
        con.close()

    print(f"\n{len(updates)} channel_ids aktualisiert (videos.channel_title + channels.title).")
    if skipped:
        print(
            f"{len(skipped)} channel_ids uebersprungen (kein aktueller Titel per API "
            f"abrufbar, z.B. geloeschter Kanal): {skipped}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply", action="store_true",
        help="Aktuelle Titel per API abfragen und in die DB schreiben (Default: nur Diagnose-CSV, kein API-Call).",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Nur die ersten N betroffenen channel_ids verarbeiten (zum Testen).",
    )
    args = parser.parse_args()

    print("Suche channel_ids mit >=2 unterschiedlichen channel_title in der video_registry...")
    summary = find_channel_ids_with_multiple_titles()
    print(f"Gefunden: {len(summary):,} betroffene channel_ids.")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUT_FILE, index=False)
    print(f"Diagnose gespeichert: {OUTPUT_FILE}")

    if summary.empty:
        return

    print("\nBeispiele:")
    print(summary.head(10).to_string(index=False))

    if args.limit:
        summary = summary.head(args.limit)
        print(f"\n--limit gesetzt, verarbeite nur {len(summary):,} channel_ids.")

    if not args.apply:
        print("\nDRY RUN - kein --apply uebergeben. Es wurden keine API-Calls gemacht und nichts geschrieben.")
        return

    youtube = build("youtube", "v3", developerKey=API_KEY_C)
    channel_ids = summary["channel_id"].tolist()
    print(f"\nFrage aktuelle Titel fuer {len(channel_ids):,} channel_ids per API ab...")
    current_titles = fetch_current_titles(channel_ids, youtube)

    apply_current_titles(current_titles)


if __name__ == "__main__":
    main()

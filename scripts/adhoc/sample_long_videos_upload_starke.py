"""Zieht je Kanal einer Kanalliste N zufällige Long-Format-Videos.

Quelle: Tabelle `video_format` (format = 'long') im video_registry-Store,
Titel aus `videos`. Ergebnis als Excel-Datei
scripts/adhoc/outputs/<kanalliste>_long_sample.xlsx. Fester Seed für
Reproduzierbarkeit.

Aufruf (Kanalliste aus data/channel_lists/video_formats/, ohne .csv):
    python scripts/adhoc/sample_long_videos_upload_starke.py                  # upload_starke_kanaele, 20 je Kanal
    python scripts/adhoc/sample_long_videos_upload_starke.py alt_kanaele 15   # alt_kanaele, 15 je Kanal
"""
from pathlib import Path
import sqlite3
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CHANNEL_LISTS = ROOT / "data" / "channel_lists" / "video_formats"
DB = ROOT / "data" / "store" / "video_registry.sqlite"
OUT_DIR = Path(__file__).resolve().parent / "outputs"
DEFAULT_LIST = "upload_starke_kanaele"
DEFAULT_N = 20
SEED = 42


def main(list_name: str = DEFAULT_LIST, n_per_channel: int = DEFAULT_N) -> None:
    channels = pd.read_csv(CHANNEL_LISTS / f"{list_name}.csv")["channel_id"].tolist()
    out = OUT_DIR / f"{list_name}_long_sample.xlsx"
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as con:
        df = pd.read_sql_query(
            f"""
            SELECT f.video_id, v.title, f.channel_id, v.channel_title
            FROM video_format f
            LEFT JOIN videos v ON v.video_id = f.video_id
            WHERE f.format = 'long'
              AND f.channel_id IN ({",".join("?" * len(channels))})
            """,
            con,
            params=channels,
        )

    counts = df.groupby("channel_id").size().reindex(channels, fill_value=0)
    too_few = counts[counts < n_per_channel]
    if not too_few.empty:
        raise SystemExit(f"Zu wenige Long-Videos für: {too_few.to_dict()}")

    sample = (
        df.groupby("channel_id")
        .sample(n_per_channel, random_state=SEED)
        .reset_index(drop=True)
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    sample.to_excel(out, index=False)
    print(f"{len(sample)} Videos aus {sample.channel_id.nunique()} Kanälen -> {out}")


if __name__ == "__main__":
    args = sys.argv[1:]
    main(args[0] if args else DEFAULT_LIST, int(args[1]) if len(args) > 1 else DEFAULT_N)

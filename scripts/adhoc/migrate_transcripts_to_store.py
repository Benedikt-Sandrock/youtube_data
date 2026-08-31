"""
Einmaliges Migrationsskript fuer Phase 3b der Restrukturierung
(siehe .claude/restructuring/RESTRUCTURING_PROGRESS.md und
.claude/plans/phase_3b.md).

Importiert data/transcripts/all_transcripts_segments.csv (laut
.claude/CLAUDE.md die einzige Source of Truth fuer Transkript-
Verfuegbarkeit) nach data/raw/transcripts.sqlite (Tabelle transcripts,
siehe youtube_code.store.transcript_store). Upsert-basiert ueber
upsert_transcripts() - ueberschreibt nie einen besseren vorhandenen
Datensatz (Prioritaetsregel "OK" > "Kein Transkript" > "Fehler: ..."),
daher idempotent bei mehrfacher Ausfuehrung. Loescht die Quell-CSV nicht.
Kein Bestandteil einer laufenden Pipeline, danach nicht mehr regelmaessig
auszufuehren.

Vor dem Lauf sicherstellen, dass kein transcript_scraping_segments.py-Lauf
parallel auf dieselbe CSV schreibt (Sicherheits-Checkpoint aus dem Plan).

Ausfuehrung (aus dem Repo-Root, src muss auf dem PYTHONPATH liegen):
    PYTHONPATH=src python scripts/adhoc/migrate_transcripts_to_store.py
"""
import shutil

import pandas as pd

from youtube_code.config import TRANSCRIPTS
from youtube_code.store.transcript_store import DB_PATH, status_counts, total_count, upsert_transcripts

SOURCE_CSV = TRANSCRIPTS / "all_transcripts_segments.csv"
CSV_CHUNKSIZE = 500
PROGRESS_EVERY = 10_000

# Recherche-Referenzwert aus dem Plan (91.036 physische Zeilen, aber nur
# ~72.443 echte Records wegen eingebetteter Zeilenumbrueche im
# status-Feld). Grobe Toleranzgrenzen als Sicherheits-Checkpoint - kein
# exakter Wert, da sich die CSV zwischen Planung und Ausfuehrung durch
# laufendes Scraping veraendert haben kann.
EXPECTED_RECORDS_MIN = 60_000
EXPECTED_RECORDS_MAX = 120_000


def preflight_duplicate_report() -> tuple[int, int]:
    """
    Liest NUR die video_id-Spalte chunk-weise (billig gegenueber einem
    vollen Read), zaehlt Vorkommen und meldet Zeilen-/Duplikat-Uebersicht
    als Sicherheits-Checkpoint vor dem eigentlichen Migrationslauf.
    """
    print(f"== Preflight: {SOURCE_CSV} ==")
    counts: dict[str, int] = {}
    n_rows = 0
    for chunk in pd.read_csv(SOURCE_CSV, usecols=["video_id"], chunksize=CSV_CHUNKSIZE):
        for vid in chunk["video_id"].dropna().astype(str):
            counts[vid] = counts.get(vid, 0) + 1
            n_rows += 1

    n_unique = len(counts)
    n_duplicated_ids = sum(1 for n in counts.values() if n > 1)
    print(f"  Zeilen gesamt: {n_rows}")
    print(f"  eindeutige video_ids: {n_unique}")
    print(f"  davon mit >1 Vorkommen: {n_duplicated_ids}")

    if not (EXPECTED_RECORDS_MIN <= n_unique <= EXPECTED_RECORDS_MAX):
        raise SystemExit(
            f"ABBRUCH: {n_unique} eindeutige video_ids liegt weit außerhalb der "
            f"erwarteten Spanne [{EXPECTED_RECORDS_MIN}, {EXPECTED_RECORDS_MAX}] "
            f"aus den Plan-Referenzwerten. Bitte manuell pruefen, bevor migriert wird."
        )
    return n_rows, n_unique


def migrate() -> int:
    """
    Liest die volle CSV in 500er-Chunks (konsistent mit dem
    CSV_CHUNKSIZE-Muster in segment_transcripts.py), wandelt NaN robust zu
    None (sonst bindet sqlite3 NaN als REAL NaN statt NULL) und upserted
    jeden Chunk. Gibt die Gesamtzahl gelesener Zeilen zurueck.
    """
    print(f"\n== Migration: {SOURCE_CSV} ==")
    n_read = 0
    n_written = 0
    for chunk in pd.read_csv(SOURCE_CSV, chunksize=CSV_CHUNKSIZE):
        chunk = chunk.astype(object).where(pd.notnull(chunk), None)
        records = chunk.to_dict(orient="records")
        n_read += len(records)
        n_written += upsert_transcripts(records)
        if n_read % PROGRESS_EVERY < CSV_CHUNKSIZE:
            print(f"  ... {n_read} Zeilen gelesen")

    print(f"  gelesen: {n_read}, transcripts upserted (angewendet): {n_written}")
    return n_read


def main() -> None:
    backup_path = DB_PATH.with_name(DB_PATH.name + ".bak_pre_migration")
    if DB_PATH.exists():
        if backup_path.exists():
            print(f"Backup existiert bereits, wird nicht ueberschrieben: {backup_path}")
        else:
            print(f"Sichere {DB_PATH} nach {backup_path} ...")
            shutil.copy2(DB_PATH, backup_path)
    else:
        print(f"{DB_PATH} existiert noch nicht, kein Backup noetig.")

    n_rows, n_unique = preflight_duplicate_report()

    count_before = total_count()
    print(f"\ntranscripts-Zeilen vor der Migration: {count_before}")

    migrate()

    count_after = total_count()
    print(f"\ntranscripts-Zeilen nach der Migration: {count_after}")
    if count_after != n_unique:
        print(
            f"WARNUNG: {count_after} Zeilen in der DB weicht ab von "
            f"{n_unique} eindeutigen video_ids aus dem Preflight."
        )
    else:
        print(f"OK: stimmt mit den {n_unique} eindeutigen video_ids aus dem Preflight ueberein.")

    print("\n== status_counts() ==")
    print(status_counts())


if __name__ == "__main__":
    main()

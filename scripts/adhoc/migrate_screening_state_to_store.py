"""
Einmaliges Migrationsskript fuer Phase 3c der Restrukturierung
(siehe .claude/restructuring/RESTRUCTURING_PROGRESS.md und
.claude/plans/phase_3c.md).

Importiert data/samples/russia/longitudinal_screening_state.csv (1,3 GB,
1.012.206 Zeilen, zentrale Tabelle des Longitudinal-Screening-Workflows)
nach data/raw/screening_state.sqlite (Tabelle screening_state, siehe
youtube_code.store.screening_state_store). Upsert-basiert ueber
upsert_state_rows() (Feld-fuer-Feld-COALESCE), daher idempotent bei
mehrfacher Ausfuehrung. Loescht die Quell-CSV nicht. Kein Bestandteil einer
laufenden Pipeline, danach nicht mehr regelmaessig auszufuehren.

Vor dem Lauf sicherstellen, dass keiner der vier Schreib-Orte
(append_channels_to_state.py, create_longitudinal_screening.py,
assign_postwar_baseline.py, update_screening_state.py) parallel auf dieselbe
CSV schreibt (Sicherheits-Checkpoint aus dem Plan) - wird unten technisch per
Prozessliste geprueft, nicht nur auf Zuruf vertraut.

Ausfuehrung (aus dem Repo-Root, src muss auf dem PYTHONPATH liegen):
    PYTHONPATH=src python scripts/adhoc/migrate_screening_state_to_store.py
"""
import shutil
import subprocess

import pandas as pd

from youtube_code.politics_screening.screening_config import STATE_FILE
from youtube_code.store.screening_state_store import (
    COLUMNS,
    DB_PATH,
    label_counts,
    round_counts,
    total_count,
    upsert_state_rows,
)

SOURCE_CSV = STATE_FILE
CSV_CHUNKSIZE = 5_000
PROGRESS_EVERY = 100_000

# Referenzwert aus dem Plan (voller Spalten-Scan zum Planungszeitpunkt:
# 1.012.206 Zeilen, 0 doppelte video_id). Enge Toleranz, weil video_id hier
# strukturell eindeutig ist (normalize_video_ids() erzwingt das bei jedem
# Laden) - anders als bei Transkripten (Phase 3b) kein Mehrquellen-Merge.
EXPECTED_ROWS = 1_012_206
EXPECTED_TOLERANCE = 5_000

# Prozessnamen der vier aktiven Schreib-Orte (Sicherheits-Checkpoint).
WRITER_SCRIPT_NAMES = [
    "append_channels_to_state.py",
    "create_longitudinal_screening.py",
    "assign_postwar_baseline.py",
    "update_screening_state.py",
]


def check_no_writer_running() -> None:
    """
    Technischer Sicherheits-Checkpoint: bricht ab, falls einer der vier
    Schreib-Orte aktuell als Prozess laeuft (Windows: tasklist mit
    Kommandozeile ueber wmic/Get-CimInstance, da tasklist selbst keine
    Kommandozeile anzeigt).
    """
    print("== Sicherheits-Checkpoint: laufende Screening-Schreib-Prozesse pruefen ==")
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" "
                "| Select-Object -ExpandProperty CommandLine",
            ],
            capture_output=True, text=True, timeout=30,
        )
        command_lines = result.stdout or ""
    except Exception as exc:
        print(f"  WARNUNG: Prozessliste konnte nicht geprueft werden ({exc}). "
              "Fahre fort, da der Nutzer bereits bestaetigt hat, dass kein "
              "Screening-Lauf aktiv ist.")
        return

    hits = [name for name in WRITER_SCRIPT_NAMES if name in command_lines]
    if hits:
        raise SystemExit(
            f"ABBRUCH: Laufender Prozess gefunden, der auf {hits} referenziert. "
            "Bitte zuerst beenden, bevor migriert wird."
        )
    print("  OK: kein aktiver Schreib-Prozess gefunden.")


def preflight_uniqueness_check() -> int:
    """
    Liest NUR die video_id-Spalte chunk-weise, prueft Eindeutigkeit
    (video_id ist hier strukturell eindeutig, siehe Modul-Docstring) und die
    Zeilenzahl gegen den Referenzwert aus dem Plan.
    """
    print(f"\n== Preflight: {SOURCE_CSV} ==")
    seen = set()
    n_rows = 0
    n_duplicates = 0
    for chunk in pd.read_csv(SOURCE_CSV, usecols=["video_id"], chunksize=CSV_CHUNKSIZE):
        for vid in chunk["video_id"].dropna().astype(str):
            n_rows += 1
            if vid in seen:
                n_duplicates += 1
            seen.add(vid)

    n_unique = len(seen)
    print(f"  Zeilen gesamt: {n_rows}")
    print(f"  eindeutige video_ids: {n_unique}")
    print(f"  Duplikate: {n_duplicates}")

    if n_duplicates:
        raise SystemExit(
            f"ABBRUCH: {n_duplicates} doppelte video_ids gefunden. Laut Plan "
            "sollte video_id strukturell eindeutig sein - bitte manuell pruefen."
        )
    if abs(n_rows - EXPECTED_ROWS) > EXPECTED_TOLERANCE:
        raise SystemExit(
            f"ABBRUCH: {n_rows} Zeilen weicht um mehr als {EXPECTED_TOLERANCE} "
            f"vom Referenzwert {EXPECTED_ROWS} aus dem Plan ab. Bitte manuell "
            "pruefen, bevor migriert wird."
        )
    return n_rows


def migrate() -> int:
    """
    Liest die volle CSV in 5000er-Chunks, wandelt NaN robust zu None (sonst
    bindet sqlite3 NaN als REAL NaN statt NULL) und upserted jeden Chunk.
    Gibt die Gesamtzahl gelesener Zeilen zurueck.
    """
    print(f"\n== Migration: {SOURCE_CSV} ==")
    n_read = 0
    n_written = 0
    for chunk in pd.read_csv(
        SOURCE_CSV,
        dtype={"video_id": "string", "channel_id": "string"},
        low_memory=False,
        chunksize=CSV_CHUNKSIZE,
    ):
        chunk = chunk[COLUMNS]
        chunk = chunk.astype(object).where(pd.notnull(chunk), None)
        records = chunk.to_dict(orient="records")
        n_read += len(records)
        n_written += upsert_state_rows(records)
        if n_read % PROGRESS_EVERY < CSV_CHUNKSIZE:
            print(f"  ... {n_read} Zeilen gelesen")

    print(f"  gelesen: {n_read}, screening_state-Zeilen upserted (angewendet): {n_written}")
    return n_read


def main() -> None:
    check_no_writer_running()

    backup_path = DB_PATH.with_name(DB_PATH.name + ".bak_pre_migration")
    if DB_PATH.exists():
        if backup_path.exists():
            print(f"Backup existiert bereits, wird nicht ueberschrieben: {backup_path}")
        else:
            print(f"Sichere {DB_PATH} nach {backup_path} ...")
            shutil.copy2(DB_PATH, backup_path)
    else:
        print(f"{DB_PATH} existiert noch nicht, kein Backup noetig.")

    n_unique = preflight_uniqueness_check()

    count_before = total_count()
    print(f"\nscreening_state-Zeilen vor der Migration: {count_before}")

    migrate()

    count_after = total_count()
    print(f"\nscreening_state-Zeilen nach der Migration: {count_after}")
    if count_after != n_unique:
        print(
            f"WARNUNG: {count_after} Zeilen in der DB weicht ab von "
            f"{n_unique} eindeutigen video_ids aus dem Preflight."
        )
    else:
        print(f"OK: stimmt mit den {n_unique} eindeutigen video_ids aus dem Preflight ueberein.")

    print("\n== round_counts() ==")
    print(round_counts().to_string(index=False))
    print("\n== label_counts() ==")
    print(label_counts().to_string(index=False))


if __name__ == "__main__":
    main()

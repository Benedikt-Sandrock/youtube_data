"""
Einmaliges Migrationsskript fuer .claude/plans/screening_state_update.md
(Schritt 1): entfernt die vier Text-Spalten channel_title/published_at/
title/description physisch aus der bestehenden data/store/screening_state.sqlite
(Tabelle screening_state). Diese Spalten waren eine zum Zeitpunkt der
Kandidatenauswahl eingefrorene Kopie aus video_registry und liefen derselben
Veraltungs-Bug-Klasse wie der channel_id-Drift hinterher - siehe
screening_state_store-Moduldocstring. Konsumenten laden die vier Spalten seit
diesem Schritt bei Bedarf per screening_state_store.get_state_with_text()
(video_id-Join gegen video_registry) statt sie aus dem Store selbst zu lesen.

Nutzt ALTER TABLE ... DROP COLUMN (SQLite >= 3.35, lokal 3.42 vorhanden -
siehe Preflight-Check unten). Idempotent: bereits entfernte Spalten werden
uebersprungen, ein zweiter Lauf ist ein No-Op.

Sicherheitsnetz vor dem DROP:
1. Vollstaendiger CSV-Export INKLUSIVE der vier Spalten (ueber den direkten
   SQL-SELECT unten, NICHT ueber screening_state_store.export_csv(), da
   dessen COLUMNS-Liste zum Zeitpunkt dieses Laufs bereits ohne die vier
   Spalten definiert ist).
2. Rohe Kopie der kompletten .sqlite-Datei (analog zum Vorgehen in
   migrate_screening_state_to_store.py).

Ausfuehrung (aus dem Repo-Root, src muss auf dem PYTHONPATH liegen):
    PYTHONPATH=src python scripts/adhoc/drop_screening_state_text_columns.py
"""
import shutil
import sqlite3

from youtube_code.store.screening_state_store import DB_PATH, _connect, total_count

TEXT_COLUMNS_TO_DROP = ["channel_title", "published_at", "title", "description"]

BACKUP_CSV_PATH = DB_PATH.with_name("screening_state_backup_pre_text_column_drop.csv")
BACKUP_DB_PATH = DB_PATH.with_name(DB_PATH.name + ".bak_pre_text_column_drop")

MIN_SQLITE_VERSION = (3, 35, 0)  # ALTER TABLE DROP COLUMN erst ab hier verfuegbar


def check_sqlite_version() -> None:
    version = tuple(int(p) for p in sqlite3.sqlite_version.split("."))
    print(f"SQLite-Version: {sqlite3.sqlite_version}")
    if version < MIN_SQLITE_VERSION:
        raise SystemExit(
            f"ABBRUCH: SQLite {sqlite3.sqlite_version} unterstuetzt kein "
            f"ALTER TABLE ... DROP COLUMN (benoetigt >= "
            f"{'.'.join(map(str, MIN_SQLITE_VERSION))})."
        )


def existing_columns(con: sqlite3.Connection) -> list[str]:
    return [row[1] for row in con.execute("PRAGMA table_info(screening_state)").fetchall()]


def backup_full_snapshot(con: sqlite3.Connection) -> int:
    """Exportiert ALLE aktuell vorhandenen Spalten (inkl. der vier zu
    loeschenden) roh per SQL, unabhaengig vom COLUMNS-Stand des bereits
    umgestellten Store-Moduls."""
    import pandas as pd

    cols = existing_columns(con)
    df = pd.read_sql_query(f"SELECT {', '.join(cols)} FROM screening_state", con)
    df.to_csv(BACKUP_CSV_PATH, index=False)
    print(f"Backup-CSV geschrieben ({len(df)} Zeilen, {len(cols)} Spalten): {BACKUP_CSV_PATH}")
    return len(df)


def drop_text_columns(con: sqlite3.Connection) -> list[str]:
    cols = existing_columns(con)
    dropped = []
    for col in TEXT_COLUMNS_TO_DROP:
        if col not in cols:
            print(f"  {col}: bereits entfernt, ueberspringe.")
            continue
        con.execute(f"ALTER TABLE screening_state DROP COLUMN {col}")
        dropped.append(col)
        print(f"  {col}: entfernt.")
    con.commit()
    return dropped


def main() -> None:
    check_sqlite_version()

    if not DB_PATH.exists():
        raise SystemExit(f"ABBRUCH: {DB_PATH} existiert nicht.")

    if BACKUP_DB_PATH.exists():
        print(f"DB-Backup existiert bereits, wird nicht ueberschrieben: {BACKUP_DB_PATH}")
    else:
        print(f"Sichere {DB_PATH} nach {BACKUP_DB_PATH} ...")
        shutil.copy2(DB_PATH, BACKUP_DB_PATH)

    con = _connect()
    try:
        cols_before = existing_columns(con)
        print(f"\nSpalten vor der Migration ({len(cols_before)}): {cols_before}")

        count_before = total_count()
        print(f"Zeilen vor der Migration: {count_before}")

        backup_full_snapshot(con)

        print("\n== ALTER TABLE ... DROP COLUMN ==")
        dropped = drop_text_columns(con)

        cols_after = existing_columns(con)
        count_after = total_count()
        print(f"\nSpalten nach der Migration ({len(cols_after)}): {cols_after}")
        print(f"Zeilen nach der Migration: {count_after}")

        if count_after != count_before:
            print(
                f"WARNUNG: Zeilenzahl hat sich veraendert ({count_before} -> "
                f"{count_after}) - ALTER TABLE DROP COLUMN sollte Zeilen nicht "
                "beruehren, bitte pruefen."
            )
        elif not dropped:
            print("Keine Spalte wurde entfernt (bereits vorher migriert).")
        else:
            print(f"OK: {len(dropped)} Spalte(n) entfernt, Zeilenzahl unveraendert.")
    finally:
        con.close()


if __name__ == "__main__":
    main()

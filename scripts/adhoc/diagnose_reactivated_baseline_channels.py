"""
Ad-hoc-Diagnoseskript: Zeigt fuer das aktuelle Sample die Verteilung ueber
die Aktivitaetsphasen-Kategorien aus
youtube_code.step2_baseline_channels.activity_phases - insbesondere, wie
viele Kanaele von der frueheren, rein channel_created_at-basierten Baseline-
Fensterzuweisung falsch eingeordnet wurden (siehe dortiger Modul-Docstring
fuer die Kategorien und die Herleitung).

War urspruenglich das Skript, in dem die Aktivitaetsphasen-Logik entwickelt
wurde; die eigentliche Logik (find_activity_phases, classify_channel_activity,
classify_channels_bulk) liegt seither in activity_phases.py, damit
assign_postwar_baseline.py und check_baseline_availability.py sie
mitverwenden koennen. Dieses Skript bleibt als reine Diagnose/Reporting-
Schicht darauf bestehen - schreibt nichts in den Screening-State.

Nutzung:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        scripts/adhoc/diagnose_reactivated_baseline_channels.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from youtube_code.step1_sample import build_channel_provenance
from youtube_code.step2_baseline_channels import activity_phases
from youtube_code.store import video_registry

OUTPUT_FILE = Path("scripts/adhoc/output/reactivated_baseline_channels_diagnosis.csv")


# ============================================================
# KANALLISTE + VIDEO-HISTORIE LADEN
# ============================================================

def load_channels() -> pd.DataFrame:
    """Analyse-relevante Kanaele (eligible_current_analysis==True) aus dem
    Provenance-Output von build_channel_provenance.py, mit channel_created_at
    als tz-naiven Timestamp."""
    if not build_channel_provenance.PROVENANCE_FILE.exists():
        raise FileNotFoundError(
            f"{build_channel_provenance.PROVENANCE_FILE} existiert nicht - "
            "zuerst build_channel_provenance.py laufen lassen."
        )

    channels = pd.read_csv(
        build_channel_provenance.PROVENANCE_FILE,
        usecols=["channel_id", "channel_title", "channel_created_at", "eligible_current_analysis"],
        dtype={"channel_id": "string", "channel_title": "string"},
    )
    channels = channels.loc[channels["eligible_current_analysis"]].drop(
        columns=["eligible_current_analysis"]
    )
    channels["channel_created_at"] = pd.to_datetime(
        channels["channel_created_at"], errors="coerce", utc=True, format="ISO8601"
    ).dt.tz_localize(None)
    return channels.reset_index(drop=True)


def load_upload_dates(channel_ids: list[str]) -> pd.DataFrame:
    """video_id/channel_id/published_at fuer ALLE in der video_registry
    bekannten Videos dieser Kanaele - Grundlage der Aktivitaetsphasen."""
    videos = video_registry.get_video_rows_for_channels(channel_ids)
    videos["published_at"] = pd.to_datetime(
        videos["published_at"], errors="coerce", utc=True, format="ISO8601"
    ).dt.tz_localize(None)
    return videos.dropna(subset=["published_at"])


def build_diagnosis(channels: pd.DataFrame, uploads: pd.DataFrame) -> pd.DataFrame:
    """Reichert activity_phases.classify_channels_bulk() um channel_title,
    channel_created_at und die zuvor verwendete rein datumsbasierte
    Klassifikation an (fuer den direkten Vergleich in der Ergebnis-CSV)."""
    classified = activity_phases.classify_channels_bulk(channels, uploads)
    result = channels.merge(classified, on="channel_id", how="left")
    result["alte_klassifikation_nur_gruendungsdatum"] = result["channel_created_at"].apply(
        lambda d: "vorkriegskanal"
        if pd.notna(d) and d < activity_phases.KRIEGSBEGINN
        else "nachkriegskanal"
    )
    return result


# ============================================================
# REPORTING
# ============================================================

def _print_group(diagnosis: pd.DataFrame, kategorie: str, titel: str, spalten: list[str]) -> None:
    group = diagnosis.loc[diagnosis["kategorie"] == kategorie]
    if group.empty:
        return
    print(f"\n{'-' * 72}\n{titel} ({len(group):,} Kanaele):\n{'-' * 72}")
    print(group[spalten].to_string(index=False))


def print_overview(diagnosis: pd.DataFrame) -> None:
    print("\n" + "=" * 72)
    print(
        f"AKTIVITAETSPHASEN-DIAGNOSE "
        f"(Luecken-Schwelle: {activity_phases.GAP_THRESHOLD_MONTHS} Monate)"
    )
    print("=" * 72)
    print(f"Kanaele insgesamt: {len(diagnosis):,}")
    print("\nVerteilung nach Kategorie:")
    print(diagnosis["kategorie"].value_counts().to_string())

    _print_group(
        diagnosis,
        "reaktiviert_faelschlich_vorkrieg",
        "reaktiviert_faelschlich_vorkrieg - aktuell als vorkriegskanal behandelt, "
        "sollten aber ein individuelles Ersatzfenster ab phase_nach_kriegsbeginn_start bekommen",
        ["channel_id", "channel_title", "channel_created_at",
         "phase_vor_kriegsbeginn_ende", "phase_nach_kriegsbeginn_start"],
    )
    _print_group(
        diagnosis,
        "nachkrieg_verzoegerter_start",
        "nachkrieg_verzoegerter_start - channel_created_at nach Kriegsbeginn, aber erste "
        "Aktivitaet erst deutlich spaeter - Anchor sollte auf phase_nach_kriegsbeginn_start "
        "statt channel_created_at verschoben werden",
        ["channel_id", "channel_title", "channel_created_at", "phase_nach_kriegsbeginn_start"],
    )
    _print_group(
        diagnosis,
        "nachkrieg_keine_aktivitaet",
        "nachkrieg_keine_aktivitaet - channel_created_at nach Kriegsbeginn, aber keine "
        "Aktivitaetsphase danach gefunden (Datenanomalie, manuell pruefen)",
        ["channel_id", "channel_title", "channel_created_at"],
    )
    _print_group(
        diagnosis,
        "tot_zum_kriegsbeginn",
        "tot_zum_kriegsbeginn - letzte Aktivitaet vor Kriegsbeginn beendet, seither keine "
        "neue Phase - Ausschluss-Kandidaten",
        ["channel_id", "channel_title", "channel_created_at", "phase_vor_kriegsbeginn_ende"],
    )

    print("\n" + "=" * 72)


def save_output(diagnosis: pd.DataFrame) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    diagnosis.to_csv(OUTPUT_FILE, index=False)
    print(f"\nGespeichert: {OUTPUT_FILE}")


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("Lade Kanalliste aus build_channel_provenance-Output...")
    channels = load_channels()
    print(f"{len(channels):,} Kanaele geladen ({build_channel_provenance.PROVENANCE_FILE}).")

    print("Lade Upload-Daten dieser Kanaele aus der video_registry...")
    uploads = load_upload_dates(channels["channel_id"].tolist())
    print(f"{len(uploads):,} Videos mit gueltigem published_at gefunden.")

    diagnosis = build_diagnosis(channels, uploads)
    print_overview(diagnosis)
    save_output(diagnosis)


if __name__ == "__main__":
    main()

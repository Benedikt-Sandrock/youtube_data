"""
Pruefskript: Verfuegbarkeits-Uebersicht der Longitudinal-Baseline je Kanal
(siehe README.md Abschnitt 1-2 fuer die zugrunde liegende Fenster-/Ziel-Logik).

Liest die aktuelle Sample-Kanalliste aus dem Provenance-Output von
../step1_sample/build_channel_provenance.py (PROVENANCE_FILE,
channel_sample_provenance.csv - enthaelt nur eligible_current_analysis==True-
Kanaele, siehe dessen Modul-Docstring) und stellt sie dem Screening-State
(screening_state_store) gegenueber.

Jeder Kanal wird per
youtube_code.step2_baseline_channels.activity_phases.classify_channels_bulk
(datengetriebene Aktivitaetsphasen-Analyse der tatsaechlichen Upload-
Historie, NICHT mehr allein channel_created_at - siehe dortiger Modul-
Docstring fuer die volle Herleitung und alle Kategorien) einer von drei
Gruppen zugeordnet:

- vorkriegskanal (README Abschnitt 1a): Baseline-Fenster ist
  interval_index in [0,1,2,3].
- nachkriegskanal (README Abschnitt 1b, siehe assign_postwar_baseline.py):
  Baseline-Fenster ist interval_index == -1 (Postwar-Sentinel), Fensteranfang
  ist der von activity_phases bestimmte anchor_date (NICHT channel_created_at).
- ausgeschlossen: Kanal hat weder ein nutzbares Vorkriegs- noch ein
  Postwar-Fenster (z.B. letzte Aktivitaet schon vor Kriegsbeginn beendet
  und seither keine neue Phase - "tot_zum_kriegsbeginn"; siehe
  activity_phases) oder channel_created_at/Videos fehlen (frueher
  "unbekannt").

Ein Kanal gilt als "vollstaendige Baseline" sobald er in seinem Fenster
mindestens TARGET_POLITICAL_PER_INTERVAL politics_final==1-Videos hat -
identische Schwelle wie
step4_transcript_download.select_targets.select_baseline_targets() und
README.md Abschnitt 2 ("fuer die Frage 'hat der Kanal genug fuer die
Baseline' reicht in der Praxis bereits >= TARGET_POLITICAL_PER_INTERVAL").

Fuer Kanaele OHNE vollstaendige Baseline wird zusaetzlich ausgegeben:
- Anzahl bereits gefundener politischer Videos (politics_final == 1) im Fenster,
- Anzahl unsicherer Videos (politics_final == -1) im Fenster,
- Anzahl noch ungescreenter Videos (politics_final IS NULL) im Fenster,
- die bisherige Politik-Quote im Fenster
  (politics_final==1 / politics_final NOT NULL, also gescreente Videos),
- verfuegbare_videos_im_fenster: Anzahl ALLER in der video_registry bekannten
  Videos des Kanals im Fenster - unabhaengig davon, ob sie bereits als
  Kandidat im Screening-State stehen (im Unterschied zu videos_im_fenster,
  das nur Kandidaten zaehlt). Zeigt, ob im Fenster ueberhaupt noch
  ungenutztes Rohmaterial fuer weitere Screening-Runden vorhanden ist.
  Fuer nachkriegskanal-Kanaele, deren individuelles Postwar-Fenster noch
  nicht per assign_postwar_baseline.py zugewiesen wurde (und fuer die Gruppe
  "ausgeschlossen"), ist der Wert NaN statt einer irrefuehrenden 0.

Nutzung:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        src/youtube_code/step2_baseline_channels/check_baseline_availability.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from youtube_code.step1_sample import build_channel_provenance
from youtube_code.step2_baseline_channels import activity_phases
from youtube_code.step2_baseline_channels.append_channels_to_state import calculate_period
from youtube_code.step2_baseline_channels.assign_postwar_baseline import WINDOW_STEPS_MONTHS
from youtube_code.step2_baseline_channels.interval_assignment import assign_intervals
from youtube_code.step2_baseline_channels.longitudinal.screening_config import (
    INTERVAL_START,
    INTERVAL_SIZE,
    TARGET_POLITICAL_PER_INTERVAL,
)
from youtube_code.store import screening_state_store, video_registry
from youtube_code.config import OUTPUTS
# ============================================================
# CONFIG
# ============================================================

PREWAR_INTERVALS = (0, 1, 2, 3)
POSTWAR_INTERVAL = -1

OUTPUT_FILE = OUTPUTS / "segment_analysis" / "baseline_availability_check.csv"


# ============================================================
# KANALLISTE + KLASSIFIKATION VOR-/NACHKRIEGSKANAL
# ============================================================

def load_channels() -> pd.DataFrame:
    """Laedt die aktuelle Sample-Kanalliste aus build_channel_provenance's
    PROVENANCE_FILE (nur channel_id/channel_title/channel_created_at - die
    Aktivitaetsphasen-Klassifikation braucht zusaetzlich die Upload-Historie
    und passiert erst in classify_war_groups(), sobald die Videos geladen
    sind)."""
    if not build_channel_provenance.PROVENANCE_FILE.exists():
        raise FileNotFoundError(
            f"{build_channel_provenance.PROVENANCE_FILE} existiert nicht - "
            "zuerst build_channel_provenance.py laufen lassen."
        )

    channels = pd.read_csv(
        build_channel_provenance.PROVENANCE_FILE,
        usecols=["channel_id", "channel_title", "channel_created_at"],
        dtype={"channel_id": "string", "channel_title": "string"},
    )
    channels["channel_created_at"] = pd.to_datetime(
        channels["channel_created_at"], errors="coerce", utc=True, format="ISO8601"
    ).dt.tz_localize(None)
    return channels


def classify_war_groups(channels: pd.DataFrame, all_videos: pd.DataFrame) -> pd.DataFrame:
    """Haengt an `channels` die Aktivitaetsphasen-Klassifikation
    (activity_phases.classify_channels_bulk) an: kategorie, war_group
    (vorkriegskanal/nachkriegskanal/ausgeschlossen) und anchor_date (der bei
    nachkriegskanal-Kanaelen fuer das Postwar-Fenster zu verwendende
    Startpunkt statt channel_created_at)."""
    classified = activity_phases.classify_channels_bulk(channels, all_videos)
    war_group = classified["war_group"].where(classified["war_group"].notna(), "ausgeschlossen")
    classified = classified.assign(war_group=war_group)
    return channels.merge(
        classified[["channel_id", "kategorie", "war_group", "anchor_date"]],
        on="channel_id",
        how="left",
    )


def load_all_channel_videos(channel_ids: list[str]) -> pd.DataFrame:
    """Laedt fuer die uebergebenen Kanaele SAEMTLICHE in der video_registry
    bekannten Videos (video_id/channel_id/published_at) - unabhaengig davon,
    ob sie bereits als Kandidat im Screening-State stehen. Grundlage fuer die
    Spalte 'verfuegbare_videos_im_fenster' (siehe compute_available_video_counts),
    die damit im Unterschied zu 'videos_im_fenster' (nur Kandidaten im State)
    zeigt, wie viel Rohmaterial ueberhaupt im jeweiligen Fenster vorliegt."""
    videos = video_registry.get_video_rows_for_channels(channel_ids)
    # tz-naiv (wie channels["channel_created_at"] und activity_phases'
    # anchor_date) - direkte Timestamp-Vergleiche (postwar_hit unten)
    # brauchen auf beiden Seiten dieselbe tz-Awareness.
    videos["published_at"] = pd.to_datetime(
        videos["published_at"], errors="coerce", utc=True, format="ISO8601"
    ).dt.tz_localize(None)
    return videos


def compute_available_video_counts(
    channels: pd.DataFrame,
    all_videos: pd.DataFrame,
    state: pd.DataFrame,
) -> pd.Series:
    """Zaehlt je Kanal ALLE in der video_registry bekannten Videos (nicht nur
    die im Screening-State als Kandidaten gefuehrten) im jeweils zustaendigen
    Baseline-Fenster:
    - vorkriegskanal: Kalendermonate interval_index in PREWAR_INTERVALS, exakt
      dieselbe period-/Interval-Logik wie beim Aufbau des States
      (append_channels_to_state.calculate_period + interval_assignment.assign_intervals).
    - nachkriegskanal: individuelles Fenster [anchor_date,
      anchor_date + fenster_monate), mit anchor_date aus
      activity_phases.classify_channels_bulk (NICHT channel_created_at -
      siehe dortiger Modul-Docstring) und fenster_monate aus dem bereits von
      assign_postwar_baseline.py zugewiesenen interval_label (Suffix
      '_0_to_<m>', z.B. 'postwar_reactivated_0_to_9' - LABEL_PREFIX_BY_KATEGORIE
      dort listet alle moeglichen Praefixe). Wurde die Postwar-Zuweisung fuer
      einen Kanal noch nicht ausgefuehrt, ist fenster_monate unbekannt - der
      Kanal erhaelt NaN statt einer (dann falschen) 0.
    - ausgeschlossen: kein Fenster definierbar -> NaN.

    Gibt eine pd.Series (Index: channel_id) zurueck, Werte als Int64
    (nullable, wegen der NaN-Faelle oben)."""
    merged = channels[["channel_id", "anchor_date", "war_group"]].merge(
        all_videos, on="channel_id", how="left"
    )

    # calculate_period() vertraegt kein NaT (Videos ohne published_at) - daher
    # nur auf der Teilmenge mit gueltigem Datum berechnen und den Rest als
    # <NA> zurueckmergen (zaehlt dann ueber isin() automatisch als False).
    reference = pd.Timestamp(build_channel_provenance.REFERENCE_DATE)
    has_date = merged["published_at"].notna()
    interval_index = pd.Series(pd.NA, index=merged.index, dtype="Int64")
    period = calculate_period(merged.loc[has_date, "published_at"], reference)
    interval_index.loc[has_date], _ = assign_intervals(period, INTERVAL_START, INTERVAL_SIZE)
    prewar_hit = (
        merged["war_group"].eq("vorkriegskanal") & interval_index.isin(PREWAR_INTERVALS)
    )

    fenster_monate = (
        state.loc[state["interval_index"] == POSTWAR_INTERVAL, ["channel_id", "interval_label"]]
        .groupby("channel_id")["interval_label"]
        .first()
        .str.extract(r"_0_to_(\d+)$")[0]
        .astype("float")
        .rename("fenster_monate")
    )
    merged = merged.merge(fenster_monate.reset_index(), on="channel_id", how="left")

    merged["fenster_ende"] = pd.Series(pd.NaT, index=merged.index, dtype="datetime64[ns]")
    for monate in WINDOW_STEPS_MONTHS:
        mask = merged["fenster_monate"].eq(monate)
        merged.loc[mask, "fenster_ende"] = (
            merged.loc[mask, "anchor_date"] + pd.DateOffset(months=monate)
        )

    postwar_hit = (
        merged["war_group"].eq("nachkriegskanal")
        & merged["published_at"].notna()
        & merged["fenster_ende"].notna()
        & merged["published_at"].ge(merged["anchor_date"])
        & merged["published_at"].lt(merged["fenster_ende"])
    )

    counts = (
        merged.loc[prewar_hit | postwar_hit]
        .groupby("channel_id")
        .size()
        .reindex(channels["channel_id"], fill_value=0)
    )

    # Nachkriegskanaele ohne bekanntes fenster_monate (Postwar-Zuweisung noch
    # nicht gelaufen) sowie "ausgeschlossen"-Kanaele: Fenster nicht
    # bestimmbar -> NaN statt der sonst irrefuehrenden 0.
    bekanntes_postwar_fenster = set(fenster_monate.dropna().index)
    unbestimmbar = channels["channel_id"][
        channels["war_group"].eq("ausgeschlossen")
        | (
            channels["war_group"].eq("nachkriegskanal")
            & ~channels["channel_id"].isin(bekanntes_postwar_fenster)
        )
    ]
    counts = counts.astype("Int64")
    counts.loc[counts.index.isin(unbestimmbar)] = pd.NA

    return counts


# ============================================================
# BASELINE-VERFUEGBARKEIT PRO KANAL
# ============================================================

def compute_channel_coverage(
    channels: pd.DataFrame,
    state: pd.DataFrame,
    all_videos: pd.DataFrame,
) -> pd.DataFrame:
    """Eine Zeile je Kanal mit political/unsicher/ungescreent-Zaehlungen und
    Politik-Quote im jeweils zustaendigen Baseline-Fenster (Vor- oder
    Nachkriegsfenster, siehe Modul-Docstring), sowie ob die Baseline damit
    schon als vollstaendig gilt."""
    merged = state[["channel_id", "interval_index", "politics_final"]].merge(
        channels[["channel_id", "war_group"]],
        on="channel_id",
        how="inner",
    )

    in_window = (
        merged["war_group"].eq("vorkriegskanal")
        & merged["interval_index"].isin(PREWAR_INTERVALS)
    ) | (
        merged["war_group"].eq("nachkriegskanal")
        & merged["interval_index"].eq(POSTWAR_INTERVAL)
    )
    windowed = merged.loc[in_window]

    grouped = windowed.groupby("channel_id")["politics_final"]
    stats = pd.DataFrame(
        {
            "videos_im_fenster": grouped.size(),
            "politische_videos": grouped.apply(lambda s: int((s == 1).sum())),
            "unsichere_videos": grouped.apply(lambda s: int((s == -1).sum())),
            "ungescreente_videos": grouped.apply(lambda s: int(s.isna().sum())),
            "gescreente_videos": grouped.apply(lambda s: int(s.notna().sum())),
        }
    )

    result = channels.merge(stats, on="channel_id", how="left")
    for column in (
        "videos_im_fenster",
        "politische_videos",
        "unsichere_videos",
        "ungescreente_videos",
        "gescreente_videos",
    ):
        result[column] = result[column].fillna(0).astype(int)

    result["politik_quote"] = (
        result["politische_videos"] / result["gescreente_videos"].replace(0, pd.NA)
    )

    verfuegbare = compute_available_video_counts(channels, all_videos, state).rename(
        "verfuegbare_videos_im_fenster"
    )
    result = result.merge(verfuegbare.reset_index(), on="channel_id", how="left")

    result["baseline_vollstaendig"] = (
        result["politische_videos"] >= TARGET_POLITICAL_PER_INTERVAL
    )

    return result


# ============================================================
# REPORTING
# ============================================================

def print_group_overview(
    group_name: str,
    group_df: pd.DataFrame,
) -> None:
    complete = group_df.loc[group_df["baseline_vollstaendig"]]
    incomplete = group_df.loc[~group_df["baseline_vollstaendig"]].sort_values(
        "politische_videos"
    )

    print(f"\n{'-' * 72}")
    print(f"{group_name} ({len(group_df):,} Kanaele)")
    print(f"{'-' * 72}")
    print(f"  Vollstaendige Baseline (>= {TARGET_POLITICAL_PER_INTERVAL} politische Videos): "
          f"{len(complete):,}")
    print(f"  Ohne vollstaendige Baseline: {len(incomplete):,}")

    if incomplete.empty:
        return

    preview = incomplete[
        [
            "channel_id",
            "channel_title",
            "politische_videos",
            "unsichere_videos",
            "ungescreente_videos",
            "politik_quote",
            "verfuegbare_videos_im_fenster",
        ]
    ].copy()
    preview["politik_quote"] = preview["politik_quote"].map(
        lambda q: f"{q:.1%}" if pd.notna(q) else "n/a"
    )

    print(f"\n  Kanaele ohne vollstaendige Baseline (aufsteigend nach politischen Videos):")
    print(preview.to_string(index=False))

    print(
        f"\n  Summe ueber diese {len(incomplete):,} Kanaele: "
        f"{incomplete['politische_videos'].sum():,} politische, "
        f"{incomplete['unsichere_videos'].sum():,} unsichere, "
        f"{incomplete['ungescreente_videos'].sum():,} ungescreente Videos."
    )


def print_overview(coverage: pd.DataFrame) -> None:
    print("\n" + "=" * 72)
    print("BASELINE-VERFUEGBARKEIT")
    print("=" * 72)
    print(f"Kanaele insgesamt: {len(coverage):,}")
    print(f"Ziel je Fenster (TARGET_POLITICAL_PER_INTERVAL): {TARGET_POLITICAL_PER_INTERVAL}")

    for group_name in ("vorkriegskanal", "nachkriegskanal", "ausgeschlossen"):
        group_df = coverage.loc[coverage["war_group"] == group_name]
        if group_df.empty:
            continue
        if group_name == "ausgeschlossen":
            print(f"\n{'-' * 72}")
            print(f"ausgeschlossen ({len(group_df):,} Kanaele - kein nutzbares Vorkriegs- "
                  "oder Postwar-Fenster laut activity_phases, oder channel_created_at/"
                  "Videos fehlen; siehe dortige kategorie-Spalte fuer den Einzelfall)")
            print(f"{'-' * 72}")
            print(group_df[["channel_id", "channel_title", "kategorie"]].to_string(index=False))
            continue
        print_group_overview(group_name, group_df)

    print("\n" + "=" * 72)


def save_output(coverage: pd.DataFrame) -> None:
    path = Path(OUTPUT_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    coverage.to_csv(path, index=False)
    print(f"\nGespeichert: {path}")


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("Lade Kanalliste aus build_channel_provenance-Output...")
    channels = load_channels()
    print(f"{len(channels):,} Kanaele geladen ({build_channel_provenance.PROVENANCE_FILE}).")

    print("Lade Screening-State fuer diese Kanaele...")
    state = screening_state_store.get_state(channel_ids=channels["channel_id"].tolist())
    print(f"{len(state):,} State-Zeilen gefunden.")

    print("Lade ALLE Videos dieser Kanaele aus der video_registry...")
    all_videos = load_all_channel_videos(channels["channel_id"].tolist())
    print(f"{len(all_videos):,} Videos in der video_registry gefunden.")

    print("Klassifiziere Vor-/Nachkriegskanaele per Aktivitaetsphasen-Analyse...")
    channels = classify_war_groups(channels, all_videos)
    print(channels["war_group"].value_counts().to_string())

    coverage = compute_channel_coverage(channels, state, all_videos)
    print_overview(coverage)
    save_output(coverage)


if __name__ == "__main__":
    main()

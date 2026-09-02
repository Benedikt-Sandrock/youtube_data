"""
Pruefskript: Verfuegbarkeits-Uebersicht der Longitudinal-Baseline je Kanal
(siehe README.md Abschnitt 1-2 fuer die zugrunde liegende Fenster-/Ziel-Logik).

Liest die aktuelle Sample-Kanalliste aus dem Provenance-Output von
../step1_sample/build_channel_provenance.py (PROVENANCE_FILE,
channel_sample_provenance.csv - enthaelt nur eligible_current_analysis==True-
Kanaele, siehe dessen Modul-Docstring) und stellt sie dem Screening-State
(screening_state_store) gegenueber.

Jeder Kanal wird anhand von channel_created_at (vs. REFERENCE_DATE aus
build_channel_provenance) einer von zwei Gruppen zugeordnet:

- vorkriegskanal (README Abschnitt 1a): Baseline-Fenster ist
  interval_index in [0,1,2,3].
- nachkriegskanal (README Abschnitt 1b, siehe
  longitudinal/assign_postwar_baseline.py): Baseline-Fenster ist
  interval_index == -1 (Postwar-Sentinel).
- unbekannt: channel_created_at fehlt - kann keinem Fenster zugeordnet
  werden (Kanal-Metadaten nachcollecten).

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
  (politics_final==1 / politics_final NOT NULL, also gescreente Videos).

Nutzung:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        src/youtube_code/step2_baseline_channels/check_baseline_availability.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from youtube_code.step1_sample import build_channel_provenance
from youtube_code.step2_baseline_channels.longitudinal.screening_config import TARGET_POLITICAL_PER_INTERVAL
from youtube_code.store import screening_state_store
from youtube_code.config import OUTPUTS
# ============================================================
# CONFIG
# ============================================================

PREWAR_INTERVALS = (0, 1, 2, 3)
POSTWAR_INTERVAL = -1

OUTPUT_FILE = OUTPUTS / "segment_analysis" /" baseline_availability_check.csv"


# ============================================================
# KANALLISTE + KLASSIFIKATION VOR-/NACHKRIEGSKANAL
# ============================================================

def load_channels() -> pd.DataFrame:
    """Laedt die aktuelle Sample-Kanalliste aus build_channel_provenance's
    PROVENANCE_FILE und klassifiziert jeden Kanal anhand von
    channel_created_at als Vor- oder Nachkriegskanal (README.md Abschnitt 1)."""
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
    )

    reference = pd.Timestamp(build_channel_provenance.REFERENCE_DATE)

    channels["war_group"] = "unbekannt"
    channels.loc[
        channels["channel_created_at"].notna()
        & channels["channel_created_at"].lt(reference),
        "war_group",
    ] = "vorkriegskanal"
    channels.loc[
        channels["channel_created_at"].notna()
        & channels["channel_created_at"].ge(reference),
        "war_group",
    ] = "nachkriegskanal"

    return channels


# ============================================================
# BASELINE-VERFUEGBARKEIT PRO KANAL
# ============================================================

def compute_channel_coverage(
    channels: pd.DataFrame,
    state: pd.DataFrame,
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

    for group_name in ("vorkriegskanal", "nachkriegskanal", "unbekannt"):
        group_df = coverage.loc[coverage["war_group"] == group_name]
        if group_df.empty:
            continue
        if group_name == "unbekannt":
            print(f"\n{'-' * 72}")
            print(f"unbekannt ({len(group_df):,} Kanaele ohne channel_created_at - "
                  "koennen keinem Fenster zugeordnet werden, Kanal-Metadaten nachcollecten)")
            print(f"{'-' * 72}")
            print(group_df[["channel_id", "channel_title"]].to_string(index=False))
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

    coverage = compute_channel_coverage(channels, state)
    print_overview(coverage)
    save_output(coverage)


if __name__ == "__main__":
    main()

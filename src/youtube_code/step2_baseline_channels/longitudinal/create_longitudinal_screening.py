"""Create the next adaptive title-screening round for longitudinal intervals.

The script reads the screening state from ``screening_state_store`` and selects
new, previously unassigned title candidates separately for every channel and
multi-month interval. An interval is skipped when:

- Target final political videos have already been found;
- title results from an earlier round are still pending;
- title-uncertain videos still await description classification; or
- no unused candidates remain.

The output CSV can be passed to the existing grouped title-batch pipeline.
Selected videos are reserved in the state through ``screening_round`` so they
cannot accidentally be submitted twice. Since Phase 4d, only the changed rows
are pushed back via ``screening_state_store.upsert_state_rows`` - no more
full-table CSV rewrite. Each pushed record carries ``video_id``,
``channel_id`` and ``screening_round`` - ``channel_id`` never actually
changes here, but it must be included because SQLite's UPSERT checks
NOT NULL constraints (``screening_state.channel_id`` is NOT NULL) against
the raw INSERT values before ever reaching the ON CONFLICT DO UPDATE /
COALESCE fallback, so a record missing a NOT NULL column fails even when
the row already exists with a valid value.

Since .claude/plans/screening_state_update.md, ``create_screening_round()``
first syncs the state against ``video_registry`` for every channel currently
present in the state (``append_channels_to_state.sync_state_with_registry``)
before planning the round - this backfills videos the registry has gained
since the state was last touched and corrects any channel_id drift, instead
of silently planning against a state that has fallen behind the registry.
``load_screening_state()`` also loads channel_title/published_at/title/
description via ``screening_state_store.get_state_with_text()`` rather than
from the state's own (now removed) copy of those columns. Because that
text-column reload runs a chunked video_id join against ``video_registry``
(chunk size 500), ``create_screening_round()`` passes its ``channel_ids``
filter straight into ``load_screening_state()`` so a channel-scoped round
only loads and joins the rows of those channels instead of the full state
(>750,000 rows as of this writing) - only the round number is still taken
from a separate, unfiltered ``screening_state_store.get_state()`` call
(cheap, no text join), since round numbers must stay globally sequential
regardless of any channel/interval filtering.

Optional targeted planning: ``create_screening_round()`` accepts a
``channel_ids`` argument (module constant ``CHANNEL_IDS`` when run as a
script) to restrict a round to a specific subset of channels instead of the
default state-wide plan. When set, only those channels are synced and only
their channel-interval cells are considered for new candidates; the round
number itself is still taken from the full, unfiltered state so round
numbers stay globally sequential regardless of any filtering (round numbers
are relied on downstream by the batch submission/merge scripts).

Optional interval filtering: ``create_screening_round()`` also accepts an
``interval_indices`` argument (module constant ``INTERVAL_INDICES`` when run
as a script) to further restrict planning to specific ``interval_index``
values (e.g. ``[-1]`` for only the postwar-baseline sentinel cells). Unlike
``channel_ids``, this filter only narrows which channel-interval cells are
*planned* - it does not affect the ``video_registry`` sync step, which
still runs for the full (or ``channel_ids``-filtered) set of channels, since
syncing is channel-scoped, not interval-scoped.
"""

import math
from pathlib import Path
import json

import pandas as pd

from youtube_code.config import MIN_VIDEO_DURATION_SECONDS, EXPLORATION, ADHOC_OUTPUT
from youtube_code.step2_baseline_channels.append_channels_to_state import (
    print_sync_report,
    sync_state_with_registry,
    write_sync_report,
)
from youtube_code.step2_baseline_channels.longitudinal.screening_config import (
    INITIAL_CANDIDATES_PER_PERIOD,
    MAX_CANDIDATES_PER_PERIOD_PER_ROUND,
    MIN_CANDIDATES_PER_PERIOD_PER_ROUND,
    POLITICAL_RATE_FLOOR,
    ROUND_SAFETY_FACTOR,
    SCREENING_ROUND_DIR,
    SCREENING_ROUND_SUMMARY_DIR,
    TARGET_WITH_BUFFER_PER_INTERVAL,
    TITLES_PER_REQUEST,
)
from youtube_code.store import screening_state_store, video_registry

# First inspect the printed plan with DRY_RUN=True. Change it to False only
# after the counts and the sample rows look plausible.
DRY_RUN = True

# Optional: Rundenplanung auf bestimmte Kanaele einschraenken (z. B. um
# gezielt nur neu hinzugefuegte oder einzelne Kanaele screenen zu lassen,
# statt state-weit ueber alle Kanaele im screening_state zu planen). Liste
# von channel_ids ("UC...") eintragen, sonst None fuer das Standardverhalten
# (alle Kanaele im State).
ids = pd.read_csv(ADHOC_OUTPUT / "topic_vids_per_channel.csv")
ids = ids[ids["topic_vids"] >= 5]["channel_id"].tolist()

# with open(EXPLORATION / "channels_add_screening.json") as f:
#     ids = json.load(f)
CHANNEL_IDS: list[str] | None = ids
if CHANNEL_IDS:
    print(f"{len(CHANNEL_IDS)} Channels selected.")

# Optional: Rundenplanung zusaetzlich auf bestimmte interval_index-Werte
# einschraenken (z. B. [-1] fuer nur die Postwar-Baseline-Sentinel-Zellen,
# oder [0, 1, 2, 3] fuer nur die Vorkriegs-Kalenderintervalle). Wirkt nur auf
# die Planung, nicht auf den video_registry-Sync (der bleibt kanalbasiert
# unveraendert). None fuer das Standardverhalten (alle Intervalle).
INTERVAL_INDICES: list[int] | None = None

REQUIRED_COLUMNS = {
    "video_id",
    "channel_id",
    "published_at",
    "title",
    "period",
    "interval_index",
    "interval_label",
    "rank_within_period",
    "candidate_rank",
    "politics_title",
    "politics_final",
    "screening_round",
}

LABEL_COLUMNS = [
    "politics_title",
    "politics_title_desc",
    "politics_final",
]

ROUND_OUTPUT_COLUMNS = [
    "screening_round",
    "video_id",
    "channel_id",
    "interval_index",
    "interval_label",
    "period",
    "published_at",
    "title",
    "description",
    "candidate_rank",
    "rank_within_period",
]


def validate_state_consistency(state: pd.DataFrame) -> pd.DataFrame:
    """Normalisiert Typen und prueft Konsistenz eines bereits geladenen
    Screening-State-DataFrame (Spalten wie aus screening_state_store.get_state()).
    Wirft ValueError bei Inkonsistenzen. Wiederverwendbar, um auch einen
    Store-Export direkt zu verifizieren (analog Phase-3c-Verify-Muster)."""
    state = state.copy()
    for column in ["video_id", "channel_id", "title", "description", "interval_label"]:
        if column in state.columns:
            state[column] = state[column].astype("string")

    missing = REQUIRED_COLUMNS - set(state.columns)
    if missing:
        raise ValueError(
            f"Screening state is missing columns: {sorted(missing)}"
        )

    state["video_id"] = state["video_id"].str.strip()
    state["channel_id"] = state["channel_id"].str.strip()
    state["title"] = state["title"].fillna("").str.strip()

    invalid_identity = (
            state["video_id"].isna()
            | state["video_id"].eq("")
            | state["channel_id"].isna()
            | state["channel_id"].eq("")
    )
    if invalid_identity.any():
        raise ValueError(
            f"{int(invalid_identity.sum()):,} rows have an invalid video_id "
            "or channel_id."
        )

    duplicate_ids = state.loc[
        state["video_id"].duplicated(keep=False),
        "video_id",
    ].unique()
    if len(duplicate_ids):
        raise ValueError(
            "Duplicate video IDs in screening state: "
            f"{sorted(duplicate_ids.tolist())[:10]}"
        )

    for column in LABEL_COLUMNS:
        if column in state.columns:
            state[column] = pd.to_numeric(
                state[column],
                errors="coerce",
            ).astype("Int8")

            invalid_labels = (
                    state[column].notna()
                    & ~state[column].isin([-1, 0, 1])
            )
            if invalid_labels.any():
                values = sorted(
                    state.loc[invalid_labels, column]
                    .dropna()
                    .unique()
                    .tolist()
                )
                raise ValueError(
                    f"Invalid labels in {column}: {values}"
                )

    state["screening_round"] = pd.to_numeric(
        state["screening_round"],
        errors="coerce",
    ).astype("Int16")

    for column in ["period", "interval_index", "rank_within_period", "candidate_rank"]:
        state[column] = pd.to_numeric(
            state[column],
            errors="raise",
        ).astype("int32")

    direct_labels = state["politics_title"].isin([0, 1])
    inconsistent_direct = (
            direct_labels
            & (
                    state["politics_final"].isna()
                    | state["politics_final"].ne(state["politics_title"])
            )
    )
    if inconsistent_direct.any():
        raise ValueError(
            f"{int(inconsistent_direct.sum()):,} directly classified videos "
            "have a missing or inconsistent politics_final. Merge the title "
            "results into the state before creating another round."
        )

    unresolved_without_title = (
            state["politics_final"].notna()
            & state["politics_title"].isna()
    )
    if unresolved_without_title.any():
        raise ValueError(
            f"{int(unresolved_without_title.sum()):,} rows have "
            "politics_final but no politics_title."
        )

    return state


def load_screening_state(channel_ids: list[str] | None = None) -> pd.DataFrame:
    """Laedt den Screening-State aus screening_state_store (inkl. der per
    video_registry-Join nachgeladenen Text-Spalten channel_title/
    published_at/title/description, siehe
    screening_state_store.get_state_with_text()) und wendet
    validate_state_consistency an. Ersatz fuer pd.read_csv(STATE_FILE).

    channel_ids (optional): reicht den Filter an get_state_with_text()
    durch, statt wie zuvor immer den kompletten State (aktuell >750.000
    Zeilen) zu laden und dessen Text-Spalten per gechunktem video_id-Join
    (Chunk-Groesse 500, siehe video_registry.get_videos_with_text())
    nachzuladen - bei einer auf wenige Kanaele eingeschraenkten Runde
    (CHANNEL_IDS) waren das bislang >1.500 unnoetige Einzel-Queries gegen
    videos/video_details, obwohl nur die Zeilen dieser Kanaele gebraucht
    wurden. Fuer die Rundennummer (die immer aus dem vollstaendigen State
    stammen muss) wird in create_screening_round() bewusst NICHT diese
    Funktion, sondern das billigere screening_state_store.get_state()
    (ohne Text-Join) verwendet."""
    state = screening_state_store.get_state_with_text(channel_ids=channel_ids)
    if state.empty:
        raise FileNotFoundError("screening_state_store ist leer.")
    return validate_state_consistency(state)


def get_next_round_number(state: pd.DataFrame) -> int:
    existing_rounds = state["screening_round"].dropna()
    if existing_rounds.empty:
        return 1
    return int(existing_rounds.max()) + 1


def calculate_candidate_count(
        political_found: int,
        final_classified: int,
        available_candidates: int,
        target_with_buffer: int,
        initial_candidates: int,
        minimum_candidates: int,
        maximum_candidates: int,
        political_rate_floor: float,
        safety_factor: float,
) -> int:
    """Calculate how many new titles should be screened in this interval."""
    if available_candidates <= 0 or political_found >= target_with_buffer:
        return 0

    needed_political = target_with_buffer - political_found

    if final_classified == 0:
        requested = initial_candidates
    else:
        observed_rate = political_found / final_classified
        effective_rate = max(observed_rate, political_rate_floor)
        requested = math.ceil(
            needed_political / effective_rate * safety_factor
        )
        requested = max(requested, minimum_candidates)

    requested = min(requested, maximum_candidates)
    return min(requested, available_candidates)


def plan_screening_round(
        state: pd.DataFrame,
        round_number: int,
        target_with_buffer: int = TARGET_WITH_BUFFER_PER_INTERVAL,
        initial_candidates: int = INITIAL_CANDIDATES_PER_PERIOD,
        minimum_candidates: int = MIN_CANDIDATES_PER_PERIOD_PER_ROUND,
        maximum_candidates: int = MAX_CANDIDATES_PER_PERIOD_PER_ROUND,
        political_rate_floor: float = POLITICAL_RATE_FLOOR,
        safety_factor: float = ROUND_SAFETY_FACTOR,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if target_with_buffer < 1:
        raise ValueError("target_with_buffer must be at least 1.")
    if not 0 < political_rate_floor <= 1:
        raise ValueError("political_rate_floor must lie in (0, 1].")
    if safety_factor < 1:
        raise ValueError("safety_factor must be at least 1.")

    # Mindestlaengen-Filter VOR jeglicher Zaehlung/Auswahl (analog zu Fix in
    # step4_transcript_download/select_targets.select_baseline_targets):
    # ohne diese Zeile wuerden zu kurze/unbekannt lange Altzeilen (siehe
    # scripts/adhoc/check_min_duration_violations.py) sowohl faelschlich zum
    # "target_reached"-Status beitragen (political_found) als auch als
    # unused-Kandidaten fuer kuenftige Screening-Runden ausgewaehlt werden -
    # letzteres verschwendet LLM-Klassifikationsbudget fuer Videos, die
    # ohnehin nie ins finale Sample kommen (siehe select_targets._filter_min_duration).
    duration_lookup = video_registry.duration_lookup(state["video_id"].tolist())
    state = state.assign(
        _duration_ok=state["video_id"].map(
            lambda v: duration_lookup.get(v) is not None
            and duration_lookup.get(v) >= MIN_VIDEO_DURATION_SECONDS
        )
    )

    selected_parts = []
    summary_rows = []

    grouped = state.groupby(
        ["channel_id", "interval_index", "interval_label"],
        sort=True,
        observed=True,
    )

    for (channel_id, interval_index, interval_label), interval_df in grouped:
        # Determine target buffer per interval (use column value if present in state)
        if (
                "target_with_buffer_per_interval" in interval_df.columns
                and pd.notna(interval_df["target_with_buffer_per_interval"].iloc[0])
        ):
            interval_target = int(
                interval_df["target_with_buffer_per_interval"].iloc[0]
            )
        else:
            interval_target = target_with_buffer

        political_found = int(
            (interval_df["politics_final"].eq(1) & interval_df["_duration_ok"]).sum()
        )
        final_classified = int(
            (interval_df["politics_final"].notna() & interval_df["_duration_ok"]).sum()
        )
        pending_title = int(
            (
                    interval_df["screening_round"].notna()
                    & interval_df["politics_title"].isna()
            ).sum()
        )
        pending_description = int(
            (
                    interval_df["politics_title"].eq(-1)
                    & interval_df["politics_final"].isna()
            ).sum()
        )

        unused = interval_df.loc[
            interval_df["screening_round"].isna()
            & interval_df["politics_title"].isna()
            & interval_df["_duration_ok"]
            ].copy()
        unused = unused.loc[unused["title"].fillna("").str.strip().ne("")]

        # Order by candidate_rank (interleaved ordering from prepare_longitudinal_screening)
        unused = unused.sort_values(
            ["candidate_rank", "rank_within_period", "published_at"],
            ascending=[True, True, True],
        )

        if political_found >= interval_target:
            status = "target_reached"
            number_to_select = 0
        elif pending_title:
            status = "awaiting_title_results"
            number_to_select = 0
        elif pending_description:
            status = "awaiting_description_results"
            number_to_select = 0
        elif unused.empty:
            status = "candidate_pool_exhausted"
            number_to_select = 0
        else:
            status = "selected_for_next_round"
            number_to_select = calculate_candidate_count(
                political_found=political_found,
                final_classified=final_classified,
                available_candidates=len(unused),
                target_with_buffer=interval_target,
                initial_candidates=initial_candidates,
                minimum_candidates=minimum_candidates,
                maximum_candidates=maximum_candidates,
                political_rate_floor=political_rate_floor,
                safety_factor=safety_factor,
            )

        if number_to_select:
            selected = unused.head(number_to_select).copy()
            selected["screening_round"] = round_number
            selected_parts.append(selected)

        summary_rows.append(
            {
                "screening_round": round_number,
                "channel_id": channel_id,
                "interval_index": interval_index,
                "interval_label": interval_label,
                "status_before_round": status,
                "candidate_videos_total": len(interval_df),
                "final_classified": final_classified,
                "political_found": political_found,
                "political_still_needed": max(
                    interval_target - political_found,
                    0,
                ),
                "pending_title_results": pending_title,
                "pending_description_results": pending_description,
                "unused_candidates_before_round": len(unused),
                "selected_this_round": number_to_select,
                "target_with_buffer": interval_target,
            }
        )

    if selected_parts:
        selected_round = pd.concat(
            selected_parts,
            ignore_index=True,
        )
        selected_round = selected_round.sort_values(
            [
                "channel_id",
                "interval_index",
                "candidate_rank",
            ],
            ascending=[True, True, True],
        ).reset_index(drop=True)
    else:
        selected_round = state.head(0).copy()
        selected_round["screening_round"] = pd.Series(dtype="Int16")

    summary = pd.DataFrame(summary_rows)
    return selected_round, summary


def update_state_with_round(
        state: pd.DataFrame,
        selected_round: pd.DataFrame,
        round_number: int,
) -> pd.DataFrame:
    updated = state.copy()
    selected_ids = set(selected_round["video_id"].astype(str))

    if not selected_ids:
        return updated

    selected_mask = updated["video_id"].astype(str).isin(selected_ids)
    if int(selected_mask.sum()) != len(selected_ids):
        raise RuntimeError(
            "Not every selected video could be found in the screening state."
        )
    if updated.loc[selected_mask, "screening_round"].notna().any():
        raise RuntimeError(
            "At least one selected video was already assigned to a round."
        )

    updated.loc[selected_mask, "screening_round"] = round_number
    updated["screening_round"] = updated["screening_round"].astype("Int16")
    return updated


def atomic_write_csv(
        data: pd.DataFrame,
        output_path: Path,
        *,
        encoding: str = "utf-8-sig",
):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(
        output_path.suffix + ".tmp"
    )
    data.to_csv(
        temporary_path,
        index=False,
        encoding=encoding,
        date_format="%Y-%m-%dT%H:%M:%SZ",
    )
    temporary_path.replace(output_path)


def print_round_plan(
        selected_round: pd.DataFrame,
        summary: pd.DataFrame,
        round_number: int,
):
    selected_count = len(selected_round)
    expected_requests = (
        math.ceil(selected_count / TITLES_PER_REQUEST)
        if selected_count
        else 0
    )

    print("\n" + "=" * 60)
    print(f"SCREENING ROUND {round_number:03d}")
    print("=" * 60)
    print(f"Channel-intervals in state : {len(summary):,}")
    print(f"Selected title candidates  : {selected_count:,}")
    print(f"Expected model requests     : {expected_requests:,}")
    print(
        "Selected channels          : "
        f"{selected_round['channel_id'].nunique():,}"
        if selected_count
        else "Selected channels          : 0"
    )

    print("\nChannel-interval status:")
    print(
        summary["status_before_round"]
        .value_counts()
        .to_string()
    )

    if selected_count:
        print("\nSelected candidates by interval:")
        print(
            selected_round["interval_label"]
            .value_counts()
            .sort_index()
            .to_string()
        )

        print("\nFirst selected rows:")
        preview_columns = [
            "channel_id",
            "interval_label",
            "video_id",
            "title",
        ]
        print(
            selected_round[preview_columns]
            .head(10)
            .to_string(index=False)
        )

    print("=" * 60)


def create_screening_round(
        round_dir: Path = SCREENING_ROUND_DIR,
        summary_dir: Path = SCREENING_ROUND_SUMMARY_DIR,
        dry_run: bool = DRY_RUN,
        channel_ids: list[str] | None = None,
        interval_indices: list[int] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """channel_ids (optional): schraenkt Sync UND Rundenplanung auf genau
    diese Kanaele ein, statt state-weit ueber alle Kanaele im
    screening_state zu planen (Standard, channel_ids=None). Die
    Rundennummer wird trotzdem immer aus dem vollstaendigen, ungefilterten
    State bestimmt (get_next_round_number), damit Rundennummern global
    fortlaufend bleiben - nachgelagerte Skripte (run_longitudinal_
    screening_batch.py, update_screening_state.py) adressieren Runden ueber
    genau diese Nummer.

    interval_indices (optional): schraenkt zusaetzlich NUR die
    Rundenplanung auf genau diese interval_index-Werte ein (z. B. [-1] fuer
    nur die Postwar-Baseline-Sentinel-Zellen). Der video_registry-Sync
    bleibt davon unberuehrt, da er kanal- und nicht intervallbasiert ist."""
    # Sync VOR dem Laden des States: gleicht fehlende video_registry-Videos
    # und channel_id-Drift fuer die betroffenen Kanaele ab (siehe
    # append_channels_to_state.sync_state_with_registry und
    # .claude/plans/screening_state_update.md) - ohne diesen Schritt wuerde
    # die Rundenplanung unten weiter auf einem gegenueber der Registry
    # zurueckfallenden State arbeiten. dry_run gilt hier genauso wie fuer den
    # Rest der Funktion: kein Schreiben, nur Report-Vorschau. Ohne
    # channel_ids-Filter sind das wie bisher alle Kanaele im State; mit
    # Filter nur die angeforderten (kein unnoetiger Sync fremder Kanaele).
    if channel_ids is not None:
        sync_target_ids = list(dict.fromkeys(channel_ids))
    else:
        sync_target_ids = screening_state_store.get_state()["channel_id"].unique().tolist()
    sync_report = sync_state_with_registry(sync_target_ids, dry_run=dry_run)
    sync_paths = write_sync_report(sync_report)
    print_sync_report(sync_report, sync_paths)

    # Rundennummer immer aus dem vollstaendigen, ungefilterten State
    # bestimmen (siehe Docstring oben) - dafuer reicht das billige
    # get_state() ohne Text-Join, ein voller load_screening_state() waere
    # hier unnoetig teuer.
    round_number = get_next_round_number(screening_state_store.get_state())

    # state direkt auf channel_ids eingeschraenkt laden (siehe
    # load_screening_state()-Docstring) statt wie frueher den kompletten
    # State zu laden und erst danach in Python zu filtern - bei einer auf
    # wenige Kanaele eingeschraenkten Runde spart das den Text-Join fuer
    # alle uebrigen Kanaele.
    state = load_screening_state(channel_ids=channel_ids)

    if channel_ids is not None:
        missing_channel_ids = set(channel_ids) - set(state["channel_id"].unique())
        if missing_channel_ids:
            raise ValueError(
                f"{len(missing_channel_ids):,} angeforderte channel_ids sind "
                f"nicht im Screening-State: {sorted(missing_channel_ids)[:10]}"
            )
    planning_state = state

    if interval_indices is not None:
        planning_state = planning_state[
            planning_state["interval_index"].isin(interval_indices)
        ]
        missing_interval_indices = set(interval_indices) - set(
            planning_state["interval_index"].unique()
        )
        if missing_interval_indices:
            raise ValueError(
                f"{len(missing_interval_indices):,} angeforderte "
                "interval_indices kommen im (ggf. bereits per channel_ids "
                f"gefilterten) Screening-State nicht vor: "
                f"{sorted(missing_interval_indices)}"
            )

    selected_round, summary = plan_screening_round(
        state=planning_state,
        round_number=round_number,
    )
    print_round_plan(
        selected_round=selected_round,
        summary=summary,
        round_number=round_number,
    )

    if selected_round.empty:
        print(
            "No new title candidates were selected. Check whether results "
            "or description classifications are still pending."
        )
        return selected_round, summary

    round_path = (
            round_dir
            / f"screening_round_{round_number:03d}_title_candidates.csv"
    )
    summary_path = (
            summary_dir
            / f"screening_round_{round_number:03d}_selection_summary.csv"
    )

    if dry_run:
        print("DRY RUN: no files or state values were changed.")
        print(f"Planned round file: {round_path}")
        print(f"Planned summary   : {summary_path}")
        return selected_round, summary

    if round_path.exists() or summary_path.exists():
        raise FileExistsError(
            "A file for the next round already exists. Resolve the existing "
            f"round before continuing: {round_path}"
        )

    output_columns = [
        column
        for column in ROUND_OUTPUT_COLUMNS
        if column in selected_round.columns
    ]
    atomic_write_csv(
        selected_round[output_columns],
        round_path,
    )
    atomic_write_csv(summary, summary_path)

    updated_state = update_state_with_round(
        state=state,
        selected_round=selected_round,
        round_number=round_number,
    )
    # channel_id wird hier mitgeschickt, obwohl sich der Wert nie aendert:
    # screening_state.channel_id ist NOT NULL, und SQLites INSERT ... ON
    # CONFLICT DO UPDATE prueft NOT-NULL-Constraints gegen die rohen VALUES
    # des INSERT-Teils, BEVOR es zur Konfliktaufloesung (und damit zum
    # COALESCE(excluded.channel_id, screening_state.channel_id) im
    # DO-UPDATE-Teil) kommt - ein Record ohne channel_id fuehrt darum immer
    # zu "NOT NULL constraint failed: screening_state.channel_id", auch fuer
    # laengst vorhandene Zeilen mit gueltigem channel_id. Reines Beibehalten
    # des vorhandenen Werts reicht, um das zu umgehen.
    changed_records = updated_state.loc[
        updated_state["video_id"].astype(str).isin(
            selected_round["video_id"].astype(str)
        ),
        ["video_id", "channel_id", "screening_round"],
    ].to_dict("records")
    written = screening_state_store.upsert_state_rows(changed_records)

    print(f"Saved round candidates: {round_path}")
    print(f"Saved round summary   : {summary_path}")
    print(f"Updated screening state in store: {written:,} rows (screening_round={round_number}).")
    return selected_round, summary


if __name__ == "__main__":
    create_screening_round(channel_ids=CHANNEL_IDS, interval_indices=INTERVAL_INDICES)
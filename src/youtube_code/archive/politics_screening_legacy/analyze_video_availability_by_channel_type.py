"""
Analyze monthly video availability by channel type.

Input
-----
The channel-period report created by select_final_screening_videos.py:
``final_video_selection_by_channel_period.csv``.

Channel types
-------------
- established_pre_reference: active before the analysis window/reference date
- new_near_reference: first observed shortly before the reference date
- new_after_reference: first observed on/after the reference date

The report distinguishes:
- all candidate uploads available in each relative one-month period;
- screened videos;
- known political videos;
- final primary and reserve selections.

Political shares are calculated among screened videos. A separate lower bound
relative to all candidates is reported because unscreened videos must not be
treated as non-political.
"""

from __future__ import annotations

import pandas as pd

from youtube_code.step2_baseline_channels.longitudinal.screening_config import (
    SCREENING_DIR,
    TARGET_POLITICAL_PER_PERIOD,
    TARGET_WITH_BUFFER_PER_PERIOD,
    WINDOW_MONTHS,
)


# ============================================================
# CONFIG
# ============================================================

DRY_RUN = True
OVERWRITE_EXISTING = False

FINAL_SELECTION_DIR = SCREENING_DIR / "final_selection"
INPUT_FILE = (
    FINAL_SELECTION_DIR
    / "final_video_selection_by_channel_period.csv"
)

OUTPUT_EXCEL = (
    FINAL_SELECTION_DIR
    / "video_availability_by_channel_type.xlsx"
)
OUTPUT_MAIN_CSV = (
    FINAL_SELECTION_DIR
    / "video_availability_by_channel_type_and_month.csv"
)


WINDOW_TYPE_ORDER = [
    "established_pre_reference",
    "new_near_reference",
    "new_after_reference",
]

WINDOW_TYPE_LABELS = {
    "established_pre_reference": (
        "bereits vor Referenzdatum aktiv"
    ),
    "new_near_reference": (
        "kurz vor Referenzdatum entstanden"
    ),
    "new_after_reference": (
        "nach Referenzdatum entstanden"
    ),
}


COUNT_COLUMNS = [
    "candidate_videos",
    "available_political",
    "available_nonpolitical",
    "available_uncertain",
    "never_screened",
    "primary_total",
    "primary_political",
    "primary_uncertain",
    "primary_nonpolitical",
    "reserve_total",
    "reserve_political",
    "reserve_uncertain",
    "reserve_nonpolitical",
]

REQUIRED_COLUMNS = {
    "channel_id",
    "time_period",
    "window_type",
    "primary_fill_type",
    *COUNT_COLUMNS,
}


# ============================================================
# LOADING AND VALIDATION
# ============================================================

def load_and_validate_detail() -> pd.DataFrame:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            "Channel-period selection report not found. Run "
            "select_final_screening_videos.py with DRY_RUN=False first:\n"
            f"{INPUT_FILE}"
        )

    data = pd.read_csv(
        INPUT_FILE,
        dtype={
            "channel_id": "string",
            "time_period": "string",
            "window_type": "string",
            "primary_fill_type": "string",
        },
        low_memory=False,
    )

    missing = REQUIRED_COLUMNS - set(data.columns)
    if missing:
        raise ValueError(
            f"Input file is missing columns: {sorted(missing)}"
        )
    if data.empty:
        raise ValueError("Input file contains no channel-period rows.")

    for column in [
        "channel_id",
        "time_period",
        "window_type",
    ]:
        data[column] = data[column].astype("string").str.strip()
        invalid = data[column].isna() | data[column].eq("")
        if invalid.any():
            raise ValueError(
                f"{column} contains {int(invalid.sum()):,} missing "
                "or empty values."
            )

    duplicated = data.duplicated(
        ["channel_id", "time_period"],
        keep=False,
    )
    if duplicated.any():
        rows = (
            data.loc[
                duplicated,
                ["channel_id", "time_period"],
            ]
            .head(10)
            .to_dict("records")
        )
        raise ValueError(
            f"Duplicate channel-period rows found: {rows}"
        )

    for column in COUNT_COLUMNS:
        raw = data[column]
        numeric = pd.to_numeric(raw, errors="coerce")
        invalid = raw.notna() & numeric.isna()
        if invalid.any() or numeric.isna().any():
            raise ValueError(
                f"{column} contains missing or non-numeric values."
            )
        non_integer = numeric.mod(1).ne(0)
        negative = numeric.lt(0)
        if non_integer.any() or negative.any():
            raise ValueError(
                f"{column} must contain non-negative integers."
            )
        data[column] = numeric.astype("int32")

    unknown_types = sorted(
        set(data["window_type"]) - set(WINDOW_TYPE_ORDER)
    )
    if unknown_types:
        raise ValueError(
            "Unknown window_type values. Update WINDOW_TYPE_ORDER and "
            f"WINDOW_TYPE_LABELS if these are intentional: {unknown_types}"
        )

    expected_periods = {
        f"period_{number}"
        for number in range(1, WINDOW_MONTHS + 1)
    }
    observed_periods = set(data["time_period"])
    unexpected_periods = sorted(observed_periods - expected_periods)
    if unexpected_periods:
        raise ValueError(
            f"Unexpected time periods: {unexpected_periods}"
        )

    period_counts = (
        data.groupby("channel_id", observed=True)["time_period"]
        .nunique()
    )
    incomplete_channels = period_counts.loc[
        period_counts.ne(len(expected_periods))
    ]
    if not incomplete_channels.empty:
        examples = {}
        for channel_id in incomplete_channels.head(10).index:
            observed = (
                data.loc[
                    data["channel_id"].eq(channel_id),
                    "time_period",
                ]
                .astype(str)
                .drop_duplicates()
                .sort_values()
                .tolist()
            )
            examples[str(channel_id)] = observed
        raise ValueError(
            f"{len(incomplete_channels):,} channels do not have exactly "
            f"the expected periods {sorted(expected_periods)}. "
            f"Examples: {examples}"
        )

    types_per_channel = (
        data.groupby("channel_id", observed=True)["window_type"]
        .nunique()
    )
    inconsistent_types = types_per_channel.gt(1)
    if inconsistent_types.any():
        channels = (
            types_per_channel.loc[inconsistent_types]
            .head(10)
            .index.tolist()
        )
        raise ValueError(
            "A channel must have one constant window_type. "
            f"Inconsistent channels: {channels}"
        )

    screened_from_labels = (
        data["available_political"]
        + data["available_uncertain"]
        + data["available_nonpolitical"]
    )
    accounted_candidates = (
        screened_from_labels + data["never_screened"]
    )
    inconsistent_candidates = accounted_candidates.ne(
        data["candidate_videos"]
    )
    if inconsistent_candidates.any():
        rows = (
            data.loc[
                inconsistent_candidates,
                [
                    "channel_id",
                    "time_period",
                    "candidate_videos",
                    "available_political",
                    "available_uncertain",
                    "available_nonpolitical",
                    "never_screened",
                ],
            ]
            .head(10)
            .to_dict("records")
        )
        raise ValueError(
            "Candidate counts are not fully explained by political, "
            f"uncertain, non-political, and never-screened counts: {rows}"
        )

    primary_from_labels = (
        data["primary_political"]
        + data["primary_uncertain"]
        + data["primary_nonpolitical"]
    )
    reserve_from_labels = (
        data["reserve_political"]
        + data["reserve_uncertain"]
        + data["reserve_nonpolitical"]
    )
    if primary_from_labels.ne(data["primary_total"]).any():
        raise ValueError(
            "Primary label counts do not sum to primary_total."
        )
    if reserve_from_labels.ne(data["reserve_total"]).any():
        raise ValueError(
            "Reserve label counts do not sum to reserve_total."
        )
    if data["primary_total"].gt(
        TARGET_POLITICAL_PER_PERIOD
    ).any():
        raise ValueError("A primary selection exceeds its target.")
    if (
        data["primary_total"] + data["reserve_total"]
    ).gt(TARGET_WITH_BUFFER_PER_PERIOD).any():
        raise ValueError("A selection exceeds its buffer target.")

    return data


# ============================================================
# DERIVED CHANNEL-PERIOD VARIABLES
# ============================================================

def safe_divide(
    numerator: pd.Series,
    denominator: pd.Series,
) -> pd.Series:
    result = numerator.div(denominator.where(denominator.ne(0)))
    return result.astype("float64")


def enrich_detail(data: pd.DataFrame) -> pd.DataFrame:
    detail = data.copy()

    detail["period_number"] = pd.to_numeric(
        detail["time_period"].str.extract(r"(\d+)$")[0],
        errors="raise",
    ).astype("int8")
    detail["period_label"] = (
        "Monat " + detail["period_number"].astype(str)
    )
    detail["window_type_label"] = detail["window_type"].map(
        WINDOW_TYPE_LABELS
    )

    detail["screened_videos"] = (
        detail["available_political"]
        + detail["available_uncertain"]
        + detail["available_nonpolitical"]
    )
    detail["selected_total_with_reserve"] = (
        detail["primary_total"] + detail["reserve_total"]
    )
    detail["selected_political_with_reserve"] = (
        detail["primary_political"]
        + detail["reserve_political"]
    )
    detail["selected_uncertain_with_reserve"] = (
        detail["primary_uncertain"]
        + detail["reserve_uncertain"]
    )
    detail["selected_nonpolitical_with_reserve"] = (
        detail["primary_nonpolitical"]
        + detail["reserve_nonpolitical"]
    )

    detail["screening_rate"] = safe_divide(
        detail["screened_videos"],
        detail["candidate_videos"],
    )
    detail["political_share_among_screened"] = safe_divide(
        detail["available_political"],
        detail["screened_videos"],
    )
    detail["political_lower_bound_all_candidates"] = safe_divide(
        detail["available_political"],
        detail["candidate_videos"],
    )
    detail["selected_political_share"] = safe_divide(
        detail["selected_political_with_reserve"],
        detail["selected_total_with_reserve"],
    )

    detail["no_video_available"] = detail[
        "candidate_videos"
    ].eq(0)
    detail["fewer_uploads_than_primary_target"] = detail[
        "candidate_videos"
    ].lt(TARGET_POLITICAL_PER_PERIOD)
    detail["primary_target_reached"] = detail[
        "primary_total"
    ].eq(TARGET_POLITICAL_PER_PERIOD)
    detail["buffer_target_reached"] = detail[
        "selected_total_with_reserve"
    ].eq(TARGET_WITH_BUFFER_PER_PERIOD)

    window_order = {
        value: position
        for position, value in enumerate(WINDOW_TYPE_ORDER)
    }
    detail["_window_order"] = detail["window_type"].map(
        window_order
    )
    detail = (
        detail.sort_values(
            ["_window_order", "period_number", "channel_id"]
        )
        .drop(columns="_window_order")
        .reset_index(drop=True)
    )

    return detail


# ============================================================
# AGGREGATION
# ============================================================

def descriptive_values(
    values: pd.Series,
    prefix: str,
) -> dict:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return {
            f"{prefix}_mean": None,
            f"{prefix}_median": None,
            f"{prefix}_p25": None,
            f"{prefix}_p75": None,
            f"{prefix}_min": None,
            f"{prefix}_max": None,
        }

    return {
        f"{prefix}_mean": float(numeric.mean()),
        f"{prefix}_median": float(numeric.median()),
        f"{prefix}_p25": float(numeric.quantile(0.25)),
        f"{prefix}_p75": float(numeric.quantile(0.75)),
        f"{prefix}_min": int(numeric.min()),
        f"{prefix}_max": int(numeric.max()),
    }


def summarize_group(group: pd.DataFrame) -> dict:
    candidates = int(group["candidate_videos"].sum())
    screened = int(group["screened_videos"].sum())
    political = int(group["available_political"].sum())
    selected = int(
        group["selected_total_with_reserve"].sum()
    )
    selected_political = int(
        group["selected_political_with_reserve"].sum()
    )

    result = {
        "channels": int(group["channel_id"].nunique()),
        "channel_period_observations": int(len(group)),
        "candidate_videos_total": candidates,
        "screened_videos_total": screened,
        "political_videos_total": political,
        "uncertain_videos_total": int(
            group["available_uncertain"].sum()
        ),
        "nonpolitical_videos_total": int(
            group["available_nonpolitical"].sum()
        ),
        "never_screened_total": int(
            group["never_screened"].sum()
        ),
        "selected_with_reserve_total": selected,
        "selected_political_total": selected_political,
        "selected_uncertain_total": int(
            group["selected_uncertain_with_reserve"].sum()
        ),
        "selected_nonpolitical_total": int(
            group["selected_nonpolitical_with_reserve"].sum()
        ),
        "screening_rate_aggregate": (
            screened / candidates if candidates else None
        ),
        "political_share_among_screened_aggregate": (
            political / screened if screened else None
        ),
        "political_lower_bound_all_candidates": (
            political / candidates if candidates else None
        ),
        "selected_political_share_aggregate": (
            selected_political / selected if selected else None
        ),
        "periods_without_video": int(
            group["no_video_available"].sum()
        ),
        "share_periods_without_video": float(
            group["no_video_available"].mean()
        ),
        "periods_below_primary_upload_target": int(
            group["fewer_uploads_than_primary_target"].sum()
        ),
        "share_periods_below_primary_upload_target": float(
            group["fewer_uploads_than_primary_target"].mean()
        ),
        "periods_reaching_primary_selection": int(
            group["primary_target_reached"].sum()
        ),
        "share_periods_reaching_primary_selection": float(
            group["primary_target_reached"].mean()
        ),
        "periods_reaching_buffer_selection": int(
            group["buffer_target_reached"].sum()
        ),
        "share_periods_reaching_buffer_selection": float(
            group["buffer_target_reached"].mean()
        ),
    }

    for column, prefix in [
        ("candidate_videos", "available_per_channel_period"),
        ("screened_videos", "screened_per_channel_period"),
        ("available_political", "political_per_channel_period"),
        ("available_uncertain", "uncertain_per_channel_period"),
        ("primary_total", "primary_selected_per_channel_period"),
        (
            "selected_total_with_reserve",
            "selected_with_reserve_per_channel_period",
        ),
    ]:
        result.update(
            descriptive_values(group[column], prefix)
        )

    return result


def aggregate_table(
    data: pd.DataFrame,
    group_columns: list[str],
) -> pd.DataFrame:
    rows = []
    grouper = (
        group_columns[0]
        if len(group_columns) == 1
        else group_columns
    )

    for group_key, group in data.groupby(
        grouper,
        observed=True,
        sort=False,
        dropna=False,
    ):
        keys = (
            (group_key,)
            if len(group_columns) == 1
            else tuple(group_key)
        )
        row = {
            column: value
            for column, value in zip(group_columns, keys)
        }
        row.update(summarize_group(group))
        rows.append(row)

    return pd.DataFrame(rows)


def build_type_period_table(
    detail: pd.DataFrame,
) -> pd.DataFrame:
    table = aggregate_table(
        detail,
        ["window_type", "time_period"],
    )
    table["window_type_label"] = table["window_type"].map(
        WINDOW_TYPE_LABELS
    )
    table["period_number"] = pd.to_numeric(
        table["time_period"].str.extract(r"(\d+)$")[0]
    ).astype("int8")
    table["period_label"] = (
        "Monat " + table["period_number"].astype(str)
    )

    order = {
        value: position
        for position, value in enumerate(WINDOW_TYPE_ORDER)
    }
    table["_window_order"] = table["window_type"].map(order)
    table = (
        table.sort_values(["_window_order", "period_number"])
        .drop(columns="_window_order")
        .reset_index(drop=True)
    )

    leading_columns = [
        "window_type",
        "window_type_label",
        "time_period",
        "period_number",
        "period_label",
    ]
    remaining = [
        column
        for column in table.columns
        if column not in leading_columns
    ]
    return table[[*leading_columns, *remaining]]


def build_channel_totals(
    detail: pd.DataFrame,
) -> pd.DataFrame:
    sum_columns = [
        "candidate_videos",
        "screened_videos",
        "available_political",
        "available_uncertain",
        "available_nonpolitical",
        "never_screened",
        "primary_total",
        "primary_political",
        "primary_uncertain",
        "primary_nonpolitical",
        "reserve_total",
        "reserve_political",
        "reserve_uncertain",
        "reserve_nonpolitical",
        "selected_total_with_reserve",
        "selected_political_with_reserve",
        "selected_uncertain_with_reserve",
        "selected_nonpolitical_with_reserve",
    ]

    totals = (
        detail.groupby(
            ["channel_id", "window_type", "window_type_label"],
            observed=True,
            as_index=False,
        )[sum_columns]
        .sum()
    )

    active_periods = (
        detail.loc[detail["candidate_videos"].gt(0)]
        .groupby("channel_id", observed=True)
        .size()
        .rename("periods_with_video")
    )
    primary_periods = (
        detail.loc[detail["primary_target_reached"]]
        .groupby("channel_id", observed=True)
        .size()
        .rename("periods_reaching_primary_selection")
    )
    buffer_periods = (
        detail.loc[detail["buffer_target_reached"]]
        .groupby("channel_id", observed=True)
        .size()
        .rename("periods_reaching_buffer_selection")
    )

    totals = totals.merge(
        active_periods,
        on="channel_id",
        how="left",
        validate="one_to_one",
    )
    totals = totals.merge(
        primary_periods,
        on="channel_id",
        how="left",
        validate="one_to_one",
    )
    totals = totals.merge(
        buffer_periods,
        on="channel_id",
        how="left",
        validate="one_to_one",
    )
    period_count_columns = [
        "periods_with_video",
        "periods_reaching_primary_selection",
        "periods_reaching_buffer_selection",
    ]
    totals[period_count_columns] = (
        totals[period_count_columns].fillna(0).astype("int8")
    )

    totals["political_share_among_screened"] = safe_divide(
        totals["available_political"],
        totals["screened_videos"],
    )
    totals["political_lower_bound_all_candidates"] = safe_divide(
        totals["available_political"],
        totals["candidate_videos"],
    )

    order = {
        value: position
        for position, value in enumerate(WINDOW_TYPE_ORDER)
    }
    totals["_window_order"] = totals["window_type"].map(order)
    return (
        totals.sort_values(["_window_order", "channel_id"])
        .drop(columns="_window_order")
        .reset_index(drop=True)
    )


def build_type_overall_table(
    channel_totals: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for window_type, group in channel_totals.groupby(
        "window_type",
        observed=True,
        sort=False,
    ):
        candidates = int(group["candidate_videos"].sum())
        screened = int(group["screened_videos"].sum())
        political = int(group["available_political"].sum())

        row = {
            "window_type": window_type,
            "window_type_label": WINDOW_TYPE_LABELS[window_type],
            "channels": int(len(group)),
            "candidate_videos_total": candidates,
            "screened_videos_total": screened,
            "political_videos_total": political,
            "uncertain_videos_total": int(
                group["available_uncertain"].sum()
            ),
            "nonpolitical_videos_total": int(
                group["available_nonpolitical"].sum()
            ),
            "political_share_among_screened_aggregate": (
                political / screened if screened else None
            ),
            "political_lower_bound_all_candidates": (
                political / candidates if candidates else None
            ),
        }

        for column, prefix in [
            ("candidate_videos", "available_per_channel_3months"),
            (
                "available_political",
                "political_per_channel_3months",
            ),
            (
                "selected_total_with_reserve",
                "selected_per_channel_3months",
            ),
            ("periods_with_video", "active_periods_per_channel"),
        ]:
            row.update(descriptive_values(group[column], prefix))

        rows.append(row)

    table = pd.DataFrame(rows)
    order = {
        value: position
        for position, value in enumerate(WINDOW_TYPE_ORDER)
    }
    table["_window_order"] = table["window_type"].map(order)
    return (
        table.sort_values("_window_order")
        .drop(columns="_window_order")
        .reset_index(drop=True)
    )


def build_fill_type_table(
    detail: pd.DataFrame,
) -> pd.DataFrame:
    table = (
        detail.groupby(
            [
                "window_type",
                "window_type_label",
                "time_period",
                "period_number",
                "primary_fill_type",
            ],
            observed=True,
        )
        .size()
        .rename("channel_periods")
        .reset_index()
    )
    totals = table.groupby(
        ["window_type", "time_period"],
        observed=True,
    )["channel_periods"].transform("sum")
    table["share_within_type_period"] = (
        table["channel_periods"] / totals
    )

    order = {
        value: position
        for position, value in enumerate(WINDOW_TYPE_ORDER)
    }
    table["_window_order"] = table["window_type"].map(order)
    return (
        table.sort_values(
            [
                "_window_order",
                "period_number",
                "primary_fill_type",
            ]
        )
        .drop(columns="_window_order")
        .reset_index(drop=True)
    )


def build_definitions() -> pd.DataFrame:
    definitions = [
        (
            "candidate_videos",
            "Alle im individuellen Einmonatsfenster verfügbaren Uploads "
            "des Kanals im Screening-State.",
        ),
        (
            "screened_videos",
            "Videos mit politics_final in {-1, 0, 1}.",
        ),
        (
            "available_political",
            "Gescreente Videos mit politics_final == 1.",
        ),
        (
            "available_uncertain",
            "Auch nach Titel und Beschreibung unsichere Videos mit "
            "politics_final == -1.",
        ),
        (
            "never_screened",
            "Nach erreichter Zielzahl bewusst nicht mehr klassifizierte "
            "Kandidaten; sie gelten nicht als unpolitisch.",
        ),
        (
            "political_share_among_screened",
            "Politische Videos geteilt durch alle gescreenten Videos.",
        ),
        (
            "political_lower_bound_all_candidates",
            "Politische Videos geteilt durch alle Kandidaten. Nur eine "
            "Untergrenze, weil nie gescreente Videos politisch sein können.",
        ),
        (
            "primary_total",
            f"Primäre Auswahl, maximal "
            f"{TARGET_POLITICAL_PER_PERIOD} Videos je Kanal-Periode.",
        ),
        (
            "selected_total_with_reserve",
            f"Primäre Auswahl plus Reserve, maximal "
            f"{TARGET_WITH_BUFFER_PER_PERIOD} Videos je Kanal-Periode.",
        ),
        (
            "period_1 ... period_n",
            "Relative Einmonatsperioden innerhalb des individuellen "
            "Kanalzeitfensters, keine Kalendermonate.",
        ),
        (
            "established_pre_reference",
            "Kanal war bereits vor dem relevanten Vorfenster aktiv.",
        ),
        (
            "new_near_reference",
            "Erstes beobachtetes Video lag kurz vor dem Referenzdatum.",
        ),
        (
            "new_after_reference",
            "Erstes beobachtetes Video lag am oder nach dem Referenzdatum.",
        ),
    ]
    return pd.DataFrame(
        definitions,
        columns=["variable", "definition"],
    )


# ============================================================
# OUTPUT
# ============================================================

def print_main_results(
    type_period: pd.DataFrame,
    type_overall: pd.DataFrame,
) -> None:
    print("\n" + "=" * 78)
    print("VIDEO AVAILABILITY BY CHANNEL TYPE AND RELATIVE MONTH")
    print("=" * 78)

    display_columns = [
        "window_type_label",
        "period_label",
        "channels",
        "available_per_channel_period_mean",
        "available_per_channel_period_median",
        "political_per_channel_period_mean",
        "political_per_channel_period_median",
        "political_share_among_screened_aggregate",
        "share_periods_below_primary_upload_target",
        "share_periods_reaching_primary_selection",
    ]
    display = type_period[display_columns].copy()
    for column in [
        "political_share_among_screened_aggregate",
        "share_periods_below_primary_upload_target",
        "share_periods_reaching_primary_selection",
    ]:
        display[column] = display[column].round(3)

    print("\nBy channel type and relative month:")
    print(display.to_string(index=False))

    overall_columns = [
        "window_type_label",
        "channels",
        "available_per_channel_3months_mean",
        "available_per_channel_3months_median",
        "political_per_channel_3months_mean",
        "political_per_channel_3months_median",
        "political_share_among_screened_aggregate",
    ]
    overall_display = type_overall[overall_columns].copy()
    overall_display[
        "political_share_among_screened_aggregate"
    ] = overall_display[
        "political_share_among_screened_aggregate"
    ].round(3)

    print("\nThree-period totals by channel type:")
    print(overall_display.to_string(index=False))
    print("=" * 78)


def require_writable_outputs() -> None:
    existing = [
        path
        for path in [OUTPUT_EXCEL, OUTPUT_MAIN_CSV]
        if path.exists()
    ]
    if existing and not OVERWRITE_EXISTING:
        paths = "\n".join(str(path) for path in existing)
        raise FileExistsError(
            "Availability output already exists. Set "
            "OVERWRITE_EXISTING=True only for a deliberate rebuild:\n"
            f"{paths}"
        )


def write_outputs(
    type_period: pd.DataFrame,
    type_overall: pd.DataFrame,
    channel_totals: pd.DataFrame,
    detail: pd.DataFrame,
    fill_types: pd.DataFrame,
    definitions: pd.DataFrame,
) -> None:
    require_writable_outputs()
    FINAL_SELECTION_DIR.mkdir(parents=True, exist_ok=True)

    type_period.to_csv(
        OUTPUT_MAIN_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    with pd.ExcelWriter(
        OUTPUT_EXCEL,
        engine="openpyxl",
    ) as writer:
        type_period.to_excel(
            writer,
            sheet_name="type_period",
            index=False,
        )
        type_overall.to_excel(
            writer,
            sheet_name="type_overall",
            index=False,
        )
        channel_totals.to_excel(
            writer,
            sheet_name="channel_totals",
            index=False,
        )
        detail.to_excel(
            writer,
            sheet_name="channel_period_detail",
            index=False,
        )
        fill_types.to_excel(
            writer,
            sheet_name="fill_types",
            index=False,
        )
        definitions.to_excel(
            writer,
            sheet_name="definitions",
            index=False,
        )

        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions

    print("\nSaved availability statistics:")
    print(f"  Main CSV : {OUTPUT_MAIN_CSV}")
    print(f"  Workbook : {OUTPUT_EXCEL}")


def main() -> None:
    raw_detail = load_and_validate_detail()
    detail = enrich_detail(raw_detail)
    type_period = build_type_period_table(detail)
    channel_totals = build_channel_totals(detail)
    type_overall = build_type_overall_table(channel_totals)
    fill_types = build_fill_type_table(detail)
    definitions = build_definitions()

    print_main_results(type_period, type_overall)

    if DRY_RUN:
        print(
            "\nDRY RUN: no files were written. If the statistics are "
            "plausible, set DRY_RUN=False."
        )
        return

    write_outputs(
        type_period=type_period,
        type_overall=type_overall,
        channel_totals=channel_totals,
        detail=detail,
        fill_types=fill_types,
        definitions=definitions,
    )


if __name__ == "__main__":
    main()

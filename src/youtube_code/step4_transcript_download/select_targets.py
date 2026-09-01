"""
Zielauswahl fuer den Transkript-Download (COMPLETE_PROCESS.md Schritt 4): aus
gespeicherten Videodaten eine Liste von Video-IDs fuer eine der drei
dokumentierten Konfigurationen extrahieren. Jede select_*-Funktion gibt ein
pd.DataFrame[video_id, channel_id] zurueck, bereits gefiltert gegen
transcript_store.attempted_video_ids() (Videos mit bestehendem
Transkript-Versuch werden nie erneut vorgeschlagen).
"""
import pandas as pd

from youtube_code.step2_baseline_channels.screening_config import TARGET_POLITICAL_PER_INTERVAL
from youtube_code.step4_transcript_download.period import add_period_column
from youtube_code.store import screening_state_store, transcript_store, video_registry

_OUT_COLS = ["video_id", "channel_id"]


def _filter_attempted(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df[_OUT_COLS] if list(df.columns) else pd.DataFrame(columns=_OUT_COLS)
    attempted = transcript_store.attempted_video_ids()
    return df[~df["video_id"].isin(attempted)][_OUT_COLS].reset_index(drop=True)


def select_baseline_targets(channel_ids=None) -> pd.DataFrame:
    """
    Konfiguration 1: fuer alle Kanaele die Baseline pruefen und alle
    Video-IDs qualifizierender Kanaele extrahieren. Verallgemeinerung von
    scraping/get_baseline_ids.py (dort hart auf eine 27-Kanal-Todo-Liste
    kodiert) nach dem in step2_baseline_channels/README.md §4 dokumentierten
    Rezept - hier ueber ALLE Kanaele im State (oder die
    per channel_ids uebergebene Teilmenge), nicht nur eine feste Liste.

    Vorkriegs-Fenster: interval_index in [0,1,2,3].
    Postwar-Fenster: interval_index == -1.
    Ein Kanal "qualifiziert" je Fenster, wenn er darin mindestens
    TARGET_POLITICAL_PER_INTERVAL politics_final==1-Videos hat; alle
    politics_final==1-Videos dieses Fensters werden dann vorgeschlagen.
    """
    state = screening_state_store.get_state(channel_ids=channel_ids)
    df = state[["video_id", "channel_id", "interval_index", "politics_final"]]

    prewar = df[df["interval_index"].isin([0, 1, 2, 3])]
    prewar_counts = prewar.groupby("channel_id")["politics_final"].apply(lambda s: (s == 1).sum())
    prewar_qualified = set(prewar_counts[prewar_counts >= TARGET_POLITICAL_PER_INTERVAL].index)

    postwar = df[df["interval_index"] == -1]
    postwar_counts = postwar.groupby("channel_id")["politics_final"].apply(lambda s: (s == 1).sum())
    postwar_qualified = set(postwar_counts[postwar_counts >= TARGET_POLITICAL_PER_INTERVAL].index)

    fill_candidates = pd.concat([
        prewar[prewar["channel_id"].isin(prewar_qualified) & (prewar["politics_final"] == 1)],
        postwar[postwar["channel_id"].isin(postwar_qualified) & (postwar["politics_final"] == 1)],
    ])[_OUT_COLS].drop_duplicates()

    return _filter_attempted(fill_candidates)


def _fill_cell(war_ids: list, political_ids: list, videos_per_cell: int, fill_order: tuple) -> list:
    """Fuellt eine Zelle bis videos_per_cell, in der per fill_order gegebenen Reihenfolge."""
    pools = {"war": sorted(war_ids), "political": sorted(political_ids)}
    selected = []
    for key in fill_order:
        if len(selected) >= videos_per_cell:
            break
        remaining = videos_per_cell - len(selected)
        selected.extend(pools[key][:remaining])
    return selected


def select_cell_fill_targets(
    channel_ids,
    videos_per_cell: int,
    topic: str = "russia_ukraine_war",
    granularity: str = "monat",
    fill_order: tuple = ("war", "political"),
) -> pd.DataFrame:
    """
    Konfiguration 2: Kanal-Perioden-Zellen identifizieren und Kriegs-/
    (bestenfalls) politisch klassifizierte Nicht-Kriegsvideos einfuellen, bis
    jede Zelle videos_per_cell Videos hat.

    Nutzt rel_monat/rel_quartal (period.relativ_periode, siehe period.py) statt
    interval_index aus screening_state_store - deckt anders als interval_index
    auch die Zeit nach Kriegsbeginn ab und bietet feinere Granularitaet.

    fill_order bestimmt, welcher Pool zuerst aufgefuellt wird (Default:
    Kriegsvideos zuerst, dann politische Nicht-Kriegsvideos).
    """
    videos = video_registry.get_videos_with_text(channel_ids=channel_ids)[
        ["video_id", "channel_id", "published_at"]
    ]
    if videos.empty:
        return pd.DataFrame(columns=_OUT_COLS)

    videos = add_period_column(videos, granularity)

    war_ids = video_registry.topic_relevant_video_ids(topic)

    state = screening_state_store.get_state(channel_ids=channel_ids)
    political_ids = set(state.loc[state["politics_final"] == 1, "video_id"])

    selected_rows = []
    for (channel_id, period), group in videos.groupby(["channel_id", "period"]):
        candidate_ids = set(group["video_id"])
        war_in_cell = candidate_ids & war_ids
        political_in_cell = (candidate_ids & political_ids) - war_in_cell

        chosen = _fill_cell(list(war_in_cell), list(political_in_cell), videos_per_cell, fill_order)
        selected_rows.extend({"video_id": vid, "channel_id": channel_id} for vid in chosen)

    return _filter_attempted(pd.DataFrame(selected_rows, columns=_OUT_COLS))


def select_war_period_targets(start_date, end_date, channel_ids=None, topic: str = "russia_ukraine_war") -> pd.DataFrame:
    """
    Konfiguration 3: alle Kriegsvideos in einem bestimmten Zeitraum
    identifizieren (z.B. kurz vor/nach einem wichtigen Event).

    start_date/end_date: 'YYYY-MM-DD'-Strings (Vergleich auf videos.published_at).
    """
    relevant_ids = video_registry.topic_relevant_video_ids(topic)
    if not relevant_ids:
        return pd.DataFrame(columns=_OUT_COLS)

    rows = video_registry.get_video_rows(relevant_ids)
    if rows.empty:
        return pd.DataFrame(columns=_OUT_COLS)

    # Datumsvergleich ueber pd.Timestamp statt roher String-Vergleich: ein
    # ISO-Zeitstempel mit Uhrzeit ("2022-02-24T15:00:00Z") waere lexikografisch
    # groesser als das reine Datum "2022-02-24" und faelschlich ausgeschlossen.
    published = pd.to_datetime(rows["published_at"], errors="coerce", utc=True).dt.tz_localize(None)
    start_ts = pd.Timestamp(start_date)
    end_ts_exclusive = pd.Timestamp(end_date) + pd.Timedelta(days=1)
    rows = rows[(published >= start_ts) & (published < end_ts_exclusive)]
    if channel_ids is not None:
        channel_ids = {str(c) for c in channel_ids}
        rows = rows[rows["channel_id"].isin(channel_ids)]

    return _filter_attempted(rows[_OUT_COLS].drop_duplicates())

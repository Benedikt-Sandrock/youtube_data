"""
Zielauswahl fuer den Transkript-Download (COMPLETE_PROCESS.md Schritt 4): aus
gespeicherten Videodaten eine Liste von Video-IDs fuer eine der drei
dokumentierten Konfigurationen extrahieren. Jede select_*-Funktion gibt ein
pd.DataFrame[video_id, channel_id] zurueck, bereits gefiltert gegen
transcript_store.attempted_video_ids() (Videos mit bestehendem
Transkript-Versuch werden nie erneut vorgeschlagen) sowie gegen
MIN_VIDEO_DURATION_SECONDS (siehe _filter_min_duration).
"""
import pandas as pd

from youtube_code.config import MIN_VIDEO_DURATION_SECONDS
from youtube_code.step2_baseline_channels.longitudinal.screening_config import (
    TARGET_POLITICAL_PER_INTERVAL,
    TARGET_WITH_BUFFER_PER_INTERVAL,
)
from youtube_code.step4_transcript_download.period import add_period_column
from youtube_code.store import screening_state_store, transcript_store, video_registry

_OUT_COLS = ["video_id", "channel_id"]


def _filter_min_duration(df: pd.DataFrame, min_duration_seconds=MIN_VIDEO_DURATION_SECONDS) -> pd.DataFrame:
    """
    Letzte Absicherung gegen zu kurze Videos im tatsaechlichen Sample -
    unabhaengig davon, ob screening_state_store/video_topic_relevance schon
    vor Einfuehrung des Mindestlaengen-Filters in get_videos_with_text()
    befuellt wurden (siehe scripts/adhoc/check_min_duration_violations.py).
    Wie dort gilt: Videos mit unbekannter Dauer gelten als nicht bestaetigt
    lang genug und werden ebenfalls verworfen. min_duration_seconds=None
    deaktiviert die Pruefung.
    """
    if min_duration_seconds is None or df.empty:
        return df
    lookup = video_registry.duration_lookup(df["video_id"].tolist())

    def _long_enough(video_id):
        seconds = lookup.get(video_id)
        return seconds is not None and seconds >= min_duration_seconds

    keep = df["video_id"].map(_long_enough)
    removed = int((~keep).sum())
    if removed:
        print(
            f"⏱️ {removed} Video(s) unter Mindestlaenge ({min_duration_seconds}s) "
            "oder mit unbekannter Dauer verworfen."
        )
    return df.loc[keep].reset_index(drop=True)


def _filter_attempted(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df[_OUT_COLS] if list(df.columns) else pd.DataFrame(columns=_OUT_COLS)
    attempted = transcript_store.attempted_video_ids()
    return df[~df["video_id"].isin(attempted)][_OUT_COLS].reset_index(drop=True)


def _prioritize(group: pd.DataFrame, transcribed: set) -> pd.DataFrame:
    """
    Sortiert eine Kandidatengruppe so, dass Videos mit bereits vorhandenem
    Transkript (laut transcript_store.has_transcript()) zuerst kommen -
    innerhalb beider Teilgruppen chronologisch (published_at) aufsteigend.
    Bereits transkribierte Videos "verbrauchen" so bevorzugt eine Quote-Stelle,
    ohne einen neuen Download auszuloesen (_filter_attempted entfernt sie am
    Ende ohnehin aus dem Ergebnis).
    """
    ordered = group.copy()
    ordered["_needs_download"] = (~ordered["video_id"].isin(transcribed)).astype(int)
    return ordered.sort_values(["_needs_download", "published_at"])


def _select_prioritized(group: pd.DataFrame, limit: int, transcribed: set) -> list[dict]:
    """Waehlt bis zu `limit` Videos aus einer einzelnen Gruppe (z.B. das Postwar-Fenster eines Kanals)."""
    return _prioritize(group, transcribed)[_OUT_COLS].head(limit).to_dict("records")


def _select_prewar_balanced(group: pd.DataFrame, limit: int, transcribed: set) -> list[dict]:
    """
    Verteilt bis zu `limit` Videos moeglichst gleichmaessig ueber die vier
    Vorkriegs-Intervalle eines Kanals (Round-Robin in Intervall-Reihenfolge)
    - bei limit=TARGET_WITH_BUFFER_PER_INTERVAL (12) und genug Kandidaten je
    Intervall ergibt das exakt 3 je Intervall. Reicht ein Intervall nicht
    aus, fuellt das Round-Robin den Rest automatisch gleichmaessig aus den
    uebrigen Intervallen auf. Innerhalb jedes Intervalls werden Videos mit
    vorhandenem Transkript bevorzugt (siehe _prioritize).
    """
    pools = {
        interval: _prioritize(interval_group, transcribed)[_OUT_COLS].to_dict("records")
        for interval, interval_group in group.groupby("interval_index")
    }
    selected = []
    while len(selected) < limit and any(pools.values()):
        for interval in sorted(pools):
            if len(selected) >= limit:
                break
            if pools[interval]:
                selected.append(pools[interval].pop(0))
    return selected


def select_baseline_targets(channel_ids=None, limit_per_channel: int | None = TARGET_WITH_BUFFER_PER_INTERVAL) -> pd.DataFrame:
    """
    Konfiguration 1: fuer alle Kanaele die Baseline pruefen und Video-IDs
    qualifizierender Kanaele extrahieren. Verallgemeinerung von
    scraping/get_baseline_ids.py (dort hart auf eine 27-Kanal-Todo-Liste
    kodiert) nach dem in step2_baseline_channels/README.md §4 dokumentierten
    Rezept - hier ueber ALLE Kanaele im State (oder die
    per channel_ids uebergebene Teilmenge), nicht nur eine feste Liste.

    Vorkriegs-Fenster: interval_index in [0,1,2,3].
    Postwar-Fenster: interval_index == -1.
    Ein Kanal "qualifiziert" je Fenster, wenn er darin mindestens
    TARGET_POLITICAL_PER_INTERVAL politics_final==1-Videos hat, DIE
    MIN_VIDEO_DURATION_SECONDS ERFUELLEN.

    Der Duration-Filter laeuft bewusst VOR der Qualifikationszaehlung (nicht
    erst am Ende auf die fertige Kandidatenliste): sonst koennten zu kurze
    oder unbekannt lange Altzeilen (siehe scripts/adhoc/check_min_duration_violations.py)
    einen Kanal faelschlich als "Ziel erreicht" markieren, obwohl ein Teil
    der dafuer gezaehlten Videos im finalen Sample gar nicht landet.

    limit_per_channel begrenzt, wie viele Video-IDs je Kanal und Fenster
    tatsaechlich uebernommen werden (Default TARGET_WITH_BUFFER_PER_INTERVAL
    = 12, um nicht mehr Transkripte herunterladen zu muessen als noetig):
    - Postwar-Fenster: die (nach Praeferenz sortierten) ersten
      limit_per_channel Videos, siehe _select_prioritized.
    - Vorkriegs-Fenster: gleichmaessig ueber die vier Intervalle verteilt
      (Ziel 3 je Intervall bei limit_per_channel=12), siehe
      _select_prewar_balanced.
    limit_per_channel=None schaltet das Limit ab und uebernimmt wie im
    urspruenglichen Verhalten ALLE politics_final==1-Videos qualifizierender
    Kanaele (keine Priorisierung noetig, da ohnehin alles genommen wird).
    """
    state = screening_state_store.get_state(channel_ids=channel_ids)
    state = _filter_min_duration(state)
    df = state[["video_id", "channel_id", "interval_index", "politics_final", "published_at"]]

    prewar = df[df["interval_index"].isin([0, 1, 2, 3])]
    prewar_counts = prewar.groupby("channel_id")["politics_final"].apply(lambda s: (s == 1).sum())
    prewar_qualified = set(prewar_counts[prewar_counts >= TARGET_POLITICAL_PER_INTERVAL].index)

    postwar = df[df["interval_index"] == -1]
    postwar_counts = postwar.groupby("channel_id")["politics_final"].apply(lambda s: (s == 1).sum())
    postwar_qualified = set(postwar_counts[postwar_counts >= TARGET_POLITICAL_PER_INTERVAL].index)

    prewar_political = prewar[prewar["channel_id"].isin(prewar_qualified) & (prewar["politics_final"] == 1)]
    postwar_political = postwar[postwar["channel_id"].isin(postwar_qualified) & (postwar["politics_final"] == 1)]

    if limit_per_channel is None:
        fill_candidates = pd.concat([prewar_political, postwar_political])[_OUT_COLS].drop_duplicates()
        return _filter_attempted(fill_candidates)

    transcribed = transcript_store.has_transcript(
        pd.concat([prewar_political["video_id"], postwar_political["video_id"]]).tolist()
    )

    selected_rows = []
    for _channel_id, group in postwar_political.groupby("channel_id"):
        selected_rows.extend(_select_prioritized(group, limit_per_channel, transcribed))
    for _channel_id, group in prewar_political.groupby("channel_id"):
        selected_rows.extend(_select_prewar_balanced(group, limit_per_channel, transcribed))

    fill_candidates = pd.DataFrame(selected_rows, columns=_OUT_COLS).drop_duplicates()
    return _filter_attempted(fill_candidates)


def select_cell_fill_targets(
    channel_ids,
    videos_per_cell: int,
    topic: str = "russia_ukraine_war",
    granularity: str = "monat",
) -> pd.DataFrame:
    """
    Konfiguration 2: Kanal-Perioden-Zellen identifizieren und je Zelle
    GETRENNT bis zu videos_per_cell Kriegsvideos UND bis zu videos_per_cell
    politisch klassifizierte Nicht-Kriegsvideos auswaehlen (zwei unabhaengige
    Quoten statt einer gemeinsamen - eine volle Zelle enthaelt also bis zu
    2 * videos_per_cell Videos).

    Nutzt rel_monat/rel_quartal (period.relativ_periode, siehe period.py) statt
    interval_index aus screening_state_store - deckt anders als interval_index
    auch die Zeit nach Kriegsbeginn ab und bietet feinere Granularitaet.

    Je Zelle und Pool (Krieg/politisch) werden zuerst Videos beruecksichtigt,
    fuer die laut transcript_store.has_transcript() bereits ein Transkript
    vorliegt (siehe _prioritize/_select_prioritized) - nur wenn das nicht
    ausreicht, um videos_per_cell zu erreichen, werden weitere, noch nicht
    heruntergeladene Video-IDs ergaenzt. Eine Zelle, die ihre Quote (je Pool)
    bereits allein aus vorhandenen Transkripten erreicht, bekommt also KEINE
    zusaetzlichen Download-Kandidaten - es werden nur so viele neue IDs
    aufgefuellt, wie zum Erreichen von videos_per_cell tatsaechlich fehlen.
    """
    videos = video_registry.get_video_metadata(channel_ids=channel_ids)[
        ["video_id", "channel_id", "published_at"]
    ]
    if videos.empty:
        return pd.DataFrame(columns=_OUT_COLS)

    videos = add_period_column(videos, granularity)

    war_ids = video_registry.topic_relevant_video_ids(topic)

    state = screening_state_store.get_state(channel_ids=channel_ids)
    political_ids = set(state.loc[state["politics_final"] == 1, "video_id"])

    transcribed = transcript_store.has_transcript(videos["video_id"].tolist())

    is_war = videos["video_id"].isin(war_ids)
    is_political_only = videos["video_id"].isin(political_ids) & ~is_war

    selected_rows = []
    for _cell, group in videos[is_war].groupby(["channel_id", "period"]):
        selected_rows.extend(_select_prioritized(group, videos_per_cell, transcribed))
    for _cell, group in videos[is_political_only].groupby(["channel_id", "period"]):
        selected_rows.extend(_select_prioritized(group, videos_per_cell, transcribed))

    fill_candidates = pd.DataFrame(selected_rows, columns=_OUT_COLS).drop_duplicates()
    return _filter_attempted(_filter_min_duration(fill_candidates))


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

    return _filter_attempted(_filter_min_duration(rows[_OUT_COLS].drop_duplicates()))

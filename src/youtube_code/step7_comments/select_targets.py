"""
Zielauswahl fuer den Kommentar-Download (COMPLETE_PROCESS.md Schritt 7):
aus gespeicherten Videodaten eine Liste von Video-IDs extrahieren. Anders
als step4_transcript_download/select_targets.py (drei fest dokumentierte
Konfigurationen) gibt es hier bewusst erst EINE Funktion - welche
Videopools tatsaechlich Kommentare bekommen sollen, haengt davon ab, welche
der COMPLETE_PROCESS.md-Forschungsfragen die Kommentardaten am Ende
beantworten sollen (offene Folgeentscheidung, siehe README.md dieses
Ordners). Weitere select_*-Funktionen (z.B. analog zu
select_baseline_targets/select_cell_fill_targets) ergaenzen, sobald das
geklaert ist.

select_topic_targets() deckt den naheliegendsten Startfall ab: Kommentare
fuer bereits als themenrelevant klassifizierte Videos (Standard-Topic
"russia_ukraine_war", siehe step3_war_videos).

select_channel_targets() deckt den zweiten Fall ab: ALLE in der
video_registry bekannten Videos einer Kanal-Liste (kein Themen- oder
Klassifikations-Filter) - z.B. um fuer eine feste Kanal-Auswahl vollstaendig
Kommentare zu sammeln statt nur fuer themenrelevante Videos.
"""
import pandas as pd

from youtube_code.config import MIN_VIDEO_DURATION_SECONDS
from youtube_code.store import comment_store, video_registry

_OUT_COLS = ["video_id", "channel_id"]


def select_topic_targets(
    topic: str = "russia_ukraine_war",
    channel_ids=None,
    include_replies: bool = False,
    min_duration_seconds=MIN_VIDEO_DURATION_SECONDS,
) -> pd.DataFrame:
    """
    Video-IDs, die fuer `topic` als themenrelevant klassifiziert sind
    (video_registry.topic_relevant_video_ids, Schritt 3), optional auf
    channel_ids eingeschraenkt, gefiltert auf MIN_VIDEO_DURATION_SECONDS
    (Muster: step4_transcript_download/select_targets.py) und gegen
    comment_store.attempted_video_ids(include_replies) - Videos, die die
    angefragte Fetch-Tiefe schon abdecken, werden nicht erneut vorgeschlagen.
    """
    relevant_ids = video_registry.topic_relevant_video_ids(topic)
    if not relevant_ids:
        return pd.DataFrame(columns=_OUT_COLS)

    rows = video_registry.get_video_rows(relevant_ids)
    if rows.empty:
        return pd.DataFrame(columns=_OUT_COLS)

    if channel_ids is not None:
        channel_ids = {str(c) for c in channel_ids}
        rows = rows[rows["channel_id"].isin(channel_ids)]

    if min_duration_seconds is not None and not rows.empty:
        duration_by_id = video_registry.duration_lookup(rows["video_id"].tolist())

        def _long_enough(video_id):
            seconds = duration_by_id.get(video_id)
            return seconds is not None and seconds >= min_duration_seconds

        keep = rows["video_id"].map(_long_enough)
        removed = int((~keep).sum())
        if removed:
            print(f"⏱️ {removed} Video(s) unter Mindestlaenge ({min_duration_seconds}s) oder mit unbekannter Dauer verworfen.")
        rows = rows.loc[keep]

    attempted = comment_store.attempted_video_ids(include_replies=include_replies)
    rows = rows[~rows["video_id"].isin(attempted)]

    return rows[_OUT_COLS].drop_duplicates().reset_index(drop=True)


def select_channel_targets(
    channel_ids,
    include_replies: bool = False,
    min_duration_seconds=MIN_VIDEO_DURATION_SECONDS,
) -> pd.DataFrame:
    """
    ALLE in video_registry bekannten Video-IDs der uebergebenen channel_ids
    (kein Themen- oder Klassifikations-Filter wie bei select_topic_targets)
    - fuer den Fall, dass fuer eine feste Kanal-Liste vollstaendig
    Kommentare gesammelt werden sollen. Wie select_topic_targets gefiltert
    auf min_duration_seconds sowie gegen
    comment_store.attempted_video_ids(include_replies): Videos, die die
    angefragte Fetch-Tiefe schon abdecken, werden nicht erneut vorgeschlagen.

    channel_ids: Liste/Menge von channel_id-Strings.
    """
    channel_ids = [str(c) for c in channel_ids if c]
    if not channel_ids:
        return pd.DataFrame(columns=_OUT_COLS)

    rows = video_registry.get_video_rows_for_channels(channel_ids)
    if rows.empty:
        return pd.DataFrame(columns=_OUT_COLS)

    if min_duration_seconds is not None:
        duration_by_id = video_registry.duration_lookup(rows["video_id"].tolist())

        def _long_enough(video_id):
            seconds = duration_by_id.get(video_id)
            return seconds is not None and seconds >= min_duration_seconds

        keep = rows["video_id"].map(_long_enough)
        removed = int((~keep).sum())
        if removed:
            print(f"⏱️ {removed} Video(s) unter Mindestlaenge ({min_duration_seconds}s) oder mit unbekannter Dauer verworfen.")
        rows = rows.loc[keep]

    attempted = comment_store.attempted_video_ids(include_replies=include_replies)
    rows = rows[~rows["video_id"].isin(attempted)]

    return rows[_OUT_COLS].drop_duplicates().reset_index(drop=True)

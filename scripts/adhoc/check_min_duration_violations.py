"""
Prueft, ob VOR Einfuehrung des zentralen Mindestlaengen-Filters
(youtube_code.config.MIN_VIDEO_DURATION_SECONDS, durchgesetzt in
video_registry.get_videos_with_text()) bereits zu kurze Videos in die
nachgelagerten Pipeline-Stores gerutscht sind:

- screening_state.sqlite      (Titel-/Beschreibungs-Screening-Kandidaten, Schritt 2)
- video_registry.sqlite        (Tabelle video_topic_relevance, Themen-Relevanz, Schritt 3)
- transcripts.sqlite           (bereits heruntergeladene/-versuchte Transkripte, Schritt 4)

Reiner Report - es wird NICHTS geloescht oder veraendert. Fuer jede der drei
Quellen wird gezaehlt, wie viele Zeilen zu Videos gehoeren, die (a) kuerzer
als MIN_VIDEO_DURATION_SECONDS sind oder (b) noch gar keine bekannte Dauer
haben (video_registry.videos.duration IS NULL - fuer sie liess sich die
Mindestlaenge bisher nicht pruefen, weil contentDetails nie abgefragt wurde).
Die betroffenen video_ids werden je Quelle als CSV unter outputs/validation/
abgelegt, damit sie manuell durchgesehen und bei Bedarf gezielt bereinigt
werden koennen. Kein automatisches Loeschen: das wuerde bei screening_state
bereits bezahlte LLM-Klassifikationen bzw. bei transcripts bereits
investierten Download-Aufwand unwiderruflich verwerfen, ohne dass das vorher
sichtbar war.

Nutzung:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        scripts/adhoc/check_min_duration_violations.py
"""
import pandas as pd

from youtube_code.config import MIN_VIDEO_DURATION_SECONDS, OUTPUTS
from youtube_code.store import screening_state_store, transcript_store, video_registry

OUTPUT_DIR = OUTPUTS / "validation"


def _report(label: str, df: pd.DataFrame, video_id_col: str = "video_id", extra_cols=None) -> pd.DataFrame:
    """Reichert df um duration_seconds an, meldet Verstoesse/unbekannte Dauer,
    schreibt eine CSV mit den betroffenen Zeilen und gibt sie zurueck."""
    print(f"\n{'=' * 60}\n{label}\n{'=' * 60}")
    if df.empty:
        print("Keine Zeilen vorhanden.")
        return df

    lookup = video_registry.duration_lookup(df[video_id_col].tolist())
    df = df.copy()
    df["duration_seconds"] = df[video_id_col].map(lookup)

    too_short = df["duration_seconds"].notna() & (df["duration_seconds"] < MIN_VIDEO_DURATION_SECONDS)
    unknown = df["duration_seconds"].isna()

    print(f"Zeilen gesamt                    : {len(df):,}")
    print(f"Zu kurz (< {MIN_VIDEO_DURATION_SECONDS}s)                 : {int(too_short.sum()):,}")
    print(f"Dauer unbekannt (nicht pruefbar) : {int(unknown.sum()):,}")

    violations = df.loc[too_short].copy()
    if violations.empty:
        return violations

    preview_cols = [video_id_col, "duration_seconds"] + [c for c in (extra_cols or []) if c in violations.columns]
    print("\nBeispiele (kuerzeste zuerst):")
    print(violations[preview_cols].sort_values("duration_seconds").head(10).to_string(index=False))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"min_duration_violations_{label}.csv"
    violations.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\nAlle {len(violations):,} Verstoesse geschrieben nach: {out_path}")

    return violations


def check_screening_state() -> pd.DataFrame:
    state = screening_state_store.get_state()
    return _report(
        "screening_state",
        state,
        extra_cols=[
            "channel_id", "channel_title", "title", "interval_label",
            "screening_round", "politics_final",
        ],
    )


def check_topic_relevance() -> pd.DataFrame:
    con = video_registry._connect()
    try:
        df = pd.read_sql_query(
            "SELECT video_id, topic, is_relevant, matched_keywords FROM video_topic_relevance",
            con,
        )
    finally:
        con.close()
    return _report("video_topic_relevance", df, extra_cols=["topic", "is_relevant"])


def check_transcripts() -> pd.DataFrame:
    con = transcript_store._connect()
    try:
        df = pd.read_sql_query("SELECT video_id, status, n_segments FROM transcripts", con)
    finally:
        con.close()
    return _report("transcripts", df, extra_cols=["status", "n_segments"])


def main():
    print(f"Mindestlaenge (MIN_VIDEO_DURATION_SECONDS): {MIN_VIDEO_DURATION_SECONDS}s")
    check_screening_state()
    check_topic_relevance()
    check_transcripts()
    print(
        "\nHinweis: Dies ist ein reiner Report - es wurde nichts geloescht oder "
        "veraendert. Die CSVs in outputs/validation/ dienen als Grundlage fuer "
        "eine manuelle Entscheidung, was mit den betroffenen Videos passieren soll."
    )


if __name__ == "__main__":
    main()

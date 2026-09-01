"""
Fuer Kanaele OHNE Baseline-Klassifikation, die laut video_registry.sqlite (Tabelle channels)
bereits im oder vor dem Baseline-Fenster (Monate -12 bis -3 vor Kriegsbeginn) existierten:

- Wie viele Videos liegen in videos_compact_pol_labels.csv vor?
- Wie viele davon sind klassifiziert (in run_0013 Base oder populism_runs_combined Main)?
- Wie viele davon sind als politisch markiert (politics_final == 1)?
- Kanaele mit GAR KEINEM Video werden gesondert ausgewiesen (Kandidaten fuer Nach-Download).

Baut auf derselben Grundgesamtheits-/Baseline-Logik wie check_baseline_coverage.py auf.
"""

import pandas as pd

from youtube_code.config import OUTPUTS
from youtube_code.store import video_registry

RESULTS_PATH = OUTPUTS / "segment_analysis"
VIDEO_PATH = OUTPUTS / "sample_feasibility" / "videos_compact_pol_labels.csv"

RESULTS_PATH_POPULISM_BASE = RESULTS_PATH / "run_0013_POPULISMUS_P_corrected.csv"
RESULTS_PATH_POPULISM_MAIN = RESULTS_PATH / "populism_runs_combined.csv"
CHANNEL_CLASSIFICATION_PATH = RESULTS_PATH / "channel_classification_populism.csv"

KRIEGSBEGINN = pd.Timestamp("2022-02-24")
BASELINE_ENDE = KRIEGSBEGINN - pd.DateOffset(months=3)
BASELINE_START = KRIEGSBEGINN - pd.DateOffset(months=12)


def lade_grundgesamtheit_kanaele():
    """Alle Kanaele, fuer die irgendeine Populismus-Klassifikation existiert (Base oder Main)."""
    main = pd.read_csv(RESULTS_PATH_POPULISM_MAIN, usecols=["video_id"])
    videos = pd.read_csv(VIDEO_PATH, usecols=["channel_id", "channel_title", "video_id", "published_at"])
    videos["published_at"] = pd.to_datetime(videos["published_at"], errors="coerce", utc=True).dt.tz_localize(None)

    main_kanaele = pd.merge(main, videos, on="video_id", how="left")["channel_id"].unique()

    base = pd.read_csv(RESULTS_PATH_POPULISM_BASE, usecols=["video_id"])
    base_kanaele = pd.merge(base, videos, on="video_id", how="left")["channel_id"].unique()

    alle_ids = set(main_kanaele) | set(base_kanaele)
    grundgesamtheit = videos[videos["channel_id"].isin(alle_ids)][
        ["channel_id", "channel_title"]
    ].drop_duplicates()

    return grundgesamtheit


def lade_kanaele_mit_baseline():
    try:
        klass = pd.read_csv(CHANNEL_CLASSIFICATION_PATH, usecols=["channel_id"])
        return set(klass["channel_id"].unique())
    except FileNotFoundError:
        base = pd.read_csv(RESULTS_PATH_POPULISM_BASE, usecols=["video_id"])
        videos = pd.read_csv(VIDEO_PATH, usecols=["channel_id", "video_id"])
        return set(pd.merge(base, videos, on="video_id", how="left")["channel_id"].unique())


def lade_kanal_erstellungsdaten():
    """channel_id -> Kanal-Erstellungsdatum, aus video_registry.sqlite (Tabelle channels)
    statt aus der frueheren, inzwischen verschwundenen channel_metadata_total.json."""
    meta_df = video_registry.get_channels()[["channel_id", "published_at"]].rename(
        columns={"published_at": "kanal_erstellt"}
    )
    meta_df["kanal_erstellt"] = pd.to_datetime(
        meta_df["kanal_erstellt"], format="ISO8601", utc=True
    ).dt.tz_localize(None)

    return meta_df.set_index("channel_id")["kanal_erstellt"]


def main():
    grundgesamtheit = lade_grundgesamtheit_kanaele()
    kanaele_mit_baseline = lade_kanaele_mit_baseline()
    kanal_erstellt = lade_kanal_erstellungsdaten()

    fehlende = grundgesamtheit[~grundgesamtheit["channel_id"].isin(kanaele_mit_baseline)].copy()
    fehlende = pd.merge(fehlende, kanal_erstellt.rename("kanal_erstellt"), on="channel_id", how="left")

    # Fokus: nur Kanaele, die laut Metadaten im oder vor dem Baseline-Fenster existierten
    im_fenster = fehlende[fehlende["kanal_erstellt"] <= BASELINE_ENDE].copy()
    ohne_erstellungsdatum = fehlende[fehlende["kanal_erstellt"].isna()].copy()

    print(f"[Info] {len(fehlende)} Kanaele ohne Baseline insgesamt.")
    print(f"[Info] {len(im_fenster)} davon existierten laut Metadaten im/vor dem Baseline-Fenster "
          f"(<= {BASELINE_ENDE.date()}).")
    if len(ohne_erstellungsdatum):
        print(f"[Warnung] {len(ohne_erstellungsdatum)} Kanaele ohne Erstellungsdatum in "
              f"video_registry.sqlite (Tabelle channels) - werden hier NICHT beruecksichtigt: "
              f"{ohne_erstellungsdatum['channel_id'].tolist()}")

    if im_fenster.empty:
        print("\nKeine relevanten Kanaele - fertig.")
        return

    # Alle Videos dieser Kanaele aus videos_compact_pol_labels.csv laden
    relevante_ids = set(im_fenster["channel_id"])
    videos = pd.read_csv(
        VIDEO_PATH,
        usecols=["video_id", "channel_id", "channel_title", "published_at", "politics_final"]
    )
    videos["published_at"] = pd.to_datetime(videos["published_at"], errors="coerce", utc=True).dt.tz_localize(None)

    videos_relevant = videos[videos["channel_id"].isin(relevante_ids)].copy()

    # Nur Videos aus dem Baseline-Fenster selbst (tagesgenau, wie in prepare_channel_scores.py):
    # [BASELINE_START, BASELINE_ENDE)
    vor_filter_n = len(videos_relevant)
    videos_relevant = videos_relevant[
        (videos_relevant["published_at"] >= BASELINE_START)
        & (videos_relevant["published_at"] < BASELINE_ENDE)
    ]
    print(f"[Info] {vor_filter_n} Videos dieser Kanaele insgesamt gefunden, "
          f"{len(videos_relevant)} davon im Baseline-Fenster ({BASELINE_START.date()} bis {BASELINE_ENDE.date()}).")

    # Klassifizierte video_ids (Base + Main) laden
    base_ids = set(pd.read_csv(RESULTS_PATH_POPULISM_BASE, usecols=["video_id"])["video_id"])
    main_ids = set(pd.read_csv(RESULTS_PATH_POPULISM_MAIN, usecols=["video_id"])["video_id"])
    klassifizierte_ids = base_ids | main_ids

    videos_relevant["ist_klassifiziert"] = videos_relevant["video_id"].isin(klassifizierte_ids)
    videos_relevant["ist_politisch"] = videos_relevant["politics_final"] == 1

    zusammenfassung = videos_relevant.groupby(["channel_id", "channel_title"], as_index=False).agg(
        n_videos_gesamt=("video_id", "count"),
        n_klassifiziert=("ist_klassifiziert", "sum"),
        n_politisch=("ist_politisch", "sum"),
        n_unsicher=("politics_final", lambda s: (s == -1).sum()),
        n_unpolitisch=("politics_final", lambda s: (s == 0).sum()),
        n_nicht_bewertet=("politics_final", lambda s: s.isna().sum()),
    )

    # Kanaele mit GAR KEINEM Video ergaenzen (kommen nicht in videos_relevant vor)
    kanaele_mit_video = set(zusammenfassung["channel_id"])
    ohne_video = im_fenster[~im_fenster["channel_id"].isin(kanaele_mit_video)][
        ["channel_id", "channel_title", "kanal_erstellt"]
    ].copy()

    for spalte in ["n_videos_gesamt", "n_klassifiziert", "n_politisch",
                    "n_unsicher", "n_unpolitisch", "n_nicht_bewertet"]:
        ohne_video[spalte] = 0

    gesamt = pd.concat([zusammenfassung, ohne_video.drop(columns="kanal_erstellt")], ignore_index=True)
    gesamt = pd.merge(gesamt, im_fenster[["channel_id", "kanal_erstellt"]], on="channel_id", how="left")
    gesamt = gesamt.sort_values("n_videos_gesamt")

    print(f"\n[Uebersicht] {len(gesamt)} Kanaele (im/vor Baseline-Fenster existiert, keine Baseline-Klassifikation).")
    print("Alle Video-Zahlen beziehen sich NUR auf Videos aus dem Baseline-Fenster selbst:\n")
    print(gesamt.to_string(index=False))

    n_ohne_video = (gesamt["n_videos_gesamt"] == 0).sum()
    print(f"\n[Zusammenfassung] {n_ohne_video} von {len(gesamt)} Kanaelen haben GAR KEIN Video aus dem "
          f"Baseline-Fenster in videos_compact_pol_labels.csv - Kandidaten fuer Video-Nachdownload.")

    out_path = RESULTS_PATH / "baseline_missing_video_coverage.csv"
    gesamt.to_csv(out_path, index=False)
    print(f"[Gespeichert] {out_path}")


if __name__ == "__main__":
    main()
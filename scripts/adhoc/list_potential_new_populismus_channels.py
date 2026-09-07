"""
Adhoc: Aus scripts/adhoc/find_political_transcripts_missing_populismus.py
(bzw. dessen Output data/exploration/political_transcripts_missing_populismus.csv)
eine Liste der Kanaele bauen, die durch eine POPULISMUS_P-Nachklassifikation
POTENZIELL ihren Qualifikationsstatus aendern wuerden - zur manuellen Pruefung,
ob sich der Submit lohnt, BEVOR tatsaechlich submittet wird.

Drei Gruppen (vgl. deskriptiv_aggregation.py-Schwellen):
    A - noch GAR KEINE Baseline-Klassifikation vorhanden
    B - Baseline vorhanden, aber < MIN_VIDEOS_BASELINE_GESAMT (5) Videos
    C - Baseline qualifiziert (>=5 Videos), aber KEIN Nachkriegsvideo
        klassifiziert (kein Vor/Nach-Vergleich moeglich)
Kanaele, die bereits voll qualifiziert sind (Gruppe D in der Chat-Analyse),
werden hier bewusst NICHT aufgefuehrt - fuer sie waere eine Nachklassifikation
keine Status-, nur eine Praezisionsverbesserung.

WICHTIG: "projected_total_baseline >= 5" ist eine NOTWENDIGE, aber keine
HINREICHENDE Bedingung fuer eine tatsaechliche Neuqualifikation - der
inhaltliche MIN_BASELINE_WERT=0.15-Schwellenwert (deskriptiv_aggregation.py)
laesst sich erst nach der Klassifikation pruefen.

Nutzung:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
      scripts/adhoc/list_potential_new_populismus_channels.py

Schreibt data/exploration/potenzielle_neue_kanaele_populismus.csv.
"""
import pandas as pd

from youtube_code.config import EXPLORATION, SAMPLES, OUTPUTS, EXTERNAL

MIN_VIDEOS_BASELINE_GESAMT = 5  # aus deskriptiv_aggregation.py

MISSING_CSV = EXPLORATION / "political_transcripts_missing_populismus.csv"
PROVENANCE_CSV = SAMPLES / "russia_longitudinal_v1" / "channel_sample_provenance.csv"
POP_KLASS_CSV = OUTPUTS / "segment_analysis" / "channel_classification_populism.csv"
VIDEO_POP_CSV = OUTPUTS / "segment_analysis" / "channel_video_populism.csv"
IDEOLOGY_CSV = OUTPUTS / "segment_analysis" / "channel_classification_ideology.csv"
MEDIA_TYPE_XLSX = EXTERNAL / "media_type_russia_merged.xlsx"

OUT_PATH = EXPLORATION / "potenzielle_neue_kanaele_populismus.csv"


def main() -> None:
    from youtube_code.store.screening_state_store import get_state

    missing = pd.read_csv(MISSING_CSV, dtype={"video_id": "string", "channel_id": "string"})
    state = get_state(politics_final=1)[["video_id", "interval_index"]].drop_duplicates("video_id")
    missing = missing.merge(state, on="video_id", how="left")

    prov = pd.read_csv(PROVENANCE_CSV, dtype={"channel_id": "string"})
    eligible = set(prov.loc[prov["eligible_current_analysis"] == True, "channel_id"])
    missing = missing[missing["channel_id"].isin(eligible)].copy()
    missing["is_baseline"] = missing["interval_index"].isin([0, 1, 2, 3, -1])

    pop_klass = pd.read_csv(POP_KLASS_CSV, dtype={"channel_id": "string"})
    video_pop = pd.read_csv(VIDEO_POP_CSV, dtype={"channel_id": "string"})

    classified_channels = set(pop_klass["channel_id"])
    current_baseline_n = pop_klass.set_index("channel_id")["n_videos_total"].to_dict()
    qualified_5 = set(pop_klass.loc[pop_klass["n_videos_total"] >= MIN_VIDEOS_BASELINE_GESAMT, "channel_id"])
    has_postwar_video = set(video_pop.loc[video_pop["rel_quartal"] >= 0, "channel_id"].unique())

    by_channel = missing.groupby("channel_id").agg(
        n_missing_baseline=("is_baseline", "sum"),
        n_missing_other=("is_baseline", lambda s: (~s).sum()),
    ).reset_index()

    by_channel["group"] = "D"
    by_channel.loc[~by_channel["channel_id"].isin(classified_channels), "group"] = "A"
    mask_b = by_channel["channel_id"].isin(classified_channels) & ~by_channel["channel_id"].isin(qualified_5)
    by_channel.loc[mask_b, "group"] = "B"
    mask_c = by_channel["channel_id"].isin(qualified_5) & ~by_channel["channel_id"].isin(has_postwar_video)
    by_channel.loc[mask_c, "group"] = "C"

    candidates = by_channel[by_channel["group"].isin(["A", "B", "C"])].copy()
    candidates["current_baseline_videos"] = candidates["channel_id"].map(current_baseline_n).fillna(0).astype(int)
    candidates["projected_baseline_videos"] = candidates["current_baseline_videos"] + candidates["n_missing_baseline"]
    candidates["reaches_min_5_threshold"] = candidates["projected_baseline_videos"] >= MIN_VIDEOS_BASELINE_GESAMT

    # Anreicherung: Kanalname/Abonnenten, Medientyp, Ideologie (nur zur Einordnung)
    meta = prov.set_index("channel_id")[["channel_title", "subscribers"]]
    candidates = candidates.join(meta, on="channel_id")

    if MEDIA_TYPE_XLSX.exists():
        media = pd.read_excel(MEDIA_TYPE_XLSX, dtype={"channel_id": "string"})
        media_map = media.set_index("channel_id")["type"].to_dict() if "type" in media.columns else {}
        candidates["medientyp"] = candidates["channel_id"].map(media_map)

    if IDEOLOGY_CSV.exists():
        ideo = pd.read_csv(IDEOLOGY_CSV, dtype={"channel_id": "string"})
        ideo_col = "ideologie_gruppe" if "ideologie_gruppe" in ideo.columns else None
        if ideo_col:
            candidates["ideologie_gruppe"] = candidates["channel_id"].map(
                ideo.set_index("channel_id")[ideo_col]
            )

    cols = [
        "channel_id", "channel_title", "subscribers", "group",
        "current_baseline_videos", "n_missing_baseline", "projected_baseline_videos",
        "reaches_min_5_threshold", "n_missing_other",
    ] + [c for c in ["medientyp", "ideologie_gruppe"] if c in candidates.columns]
    candidates = candidates[cols].sort_values(["group", "subscribers"], ascending=[True, False])

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")

    print(f"{len(candidates)} Kanaele (Gruppen A/B/C) -> {OUT_PATH}")
    print(candidates["group"].value_counts().to_string())
    print(f"\nDavon erreichen nach Nachtrag voraussichtlich >= {MIN_VIDEOS_BASELINE_GESAMT} Baseline-Videos: "
          f"{int(candidates['reaches_min_5_threshold'].sum())}")


if __name__ == "__main__":
    main()

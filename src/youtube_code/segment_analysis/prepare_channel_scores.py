import pandas as pd
import numpy as np

from youtube_code.config import OUTPUTS, SAMPLES

VIDEO_PATH = OUTPUTS / "sample_feasibility" / "videos_compact_pol_labels.csv"
RESULTS_PATH = OUTPUTS / "segment_analysis"

RESULTS_PATH_IDEOLOGY = RESULTS_PATH / "run_0012_IDEOLOGIE_I_corrected.csv"
RESULTS_PATH_POPULISM_BASE = RESULTS_PATH / "run_0013_POPULISMUS_P_corrected.csv"
RESULTS_PATH_POPULISM_MAIN = RESULTS_PATH / "populism_runs_combined.csv"
RESULTS_PATH_STANCE = RESULTS_PATH / "run_0011_POSITION_V1.csv"


KRIEGSBEGINN = "2022-02-24"

GESAMTSCORE_NAME = "populismus_gesamt"
GESAMTSCORE_AUS = ["volkszentrismus", "antielitismus", "manichaeische_moralisierung"]

# Granularitaeten, fuer die jeweils eine eigene Zeitreihen-Datei erzeugt wird.
# "spalte" ist der Name der Periodenspalte in der jeweiligen Ausgabedatei.
GRANULARITAETEN = {
    "quartal": {"monate_pro_periode": 3, "spalte": "rel_quartal", "datei_suffix": "quartal"},
    "monat":   {"monate_pro_periode": 1, "spalte": "rel_monat",   "datei_suffix": "monat"},
}


def relativ_periode(datum, start, monate_pro_periode):
    """Periode relativ zum Kriegsbeginn, tagesgenau.
    Periode 0 = [start, start + monate_pro_periode Monate), usw."""
    monate = (datum.dt.year - start.year) * 12 + (datum.dt.month - start.month)
    monate = monate - (datum.dt.day < start.day).astype(int)
    return (monate // monate_pro_periode).astype(int)


def ergaenze_periodenspalten(df, spalte_datum="published_at"):
    """Fuegt beide Periodenspalten (rel_quartal, rel_monat) gleichzeitig hinzu, da sie
    pro Video/Zeile ohnehin konstant sind - vermeidet wiederholtes Neuberechnen je Granularitaet."""
    start = pd.Timestamp(KRIEGSBEGINN)
    for gran, cfg in GRANULARITAETEN.items():
        df[cfg["spalte"]] = relativ_periode(df[spalte_datum], start, cfg["monate_pro_periode"])
    return df


def _kanal_periode_aus_video(video_df, alle_dimensionen, periodenspalte):
    """Video-Ebene -> Kanal x Periode. Gemeinsame Aggregationslogik fuer jede Granularitaet,
    setzt auf einer bereits fertigen Video-Tabelle auf (kein erneutes Segment-Merging)."""
    return video_df.groupby(
        ["channel_id", "channel_title", periodenspalte], as_index=False
    ).agg(**{d: (d, "mean") for d in alle_dimensionen},
          n_videos=("video_id", "count"))


# =========================================================
# POPULISMUS
# =========================================================

def _video_populismus(pop_df, videos, dimensionen):
    """Segment -> Video, mit beiden Periodenspalten gleichzeitig."""
    pop_df = pd.merge(pop_df, videos, on="video_id", how="left")

    ohne_datum = pop_df["published_at"].isna()
    if ohne_datum.any():
        print(f"[Warnung] {int(ohne_datum.sum())} Segmente ohne published_at -> verworfen.")
        pop_df = pop_df[~ohne_datum]

    pop_df = ergaenze_periodenspalten(pop_df)
    periodenspalten = [cfg["spalte"] for cfg in GRANULARITAETEN.values()]

    video_mittel = pop_df.groupby(
        ["channel_id", "channel_title", "video_id"] + periodenspalten,
        as_index=False
    )[dimensionen].mean()

    # Gesamtscore auf Video-Ebene, aus den Rohwerten VOR der Periodenaggregation
    video_mittel[GESAMTSCORE_NAME] = video_mittel[GESAMTSCORE_AUS].mean(axis=1)

    return video_mittel


def prepare_populism_results(results_path_base, results_path_main, video_path):
    """Gibt (zeitreihen, kanal_klassifikation, video_ebene) zurueck.
    zeitreihen: dict {granularitaet: Long-Format-DataFrame}
    kanal_klassifikation: EIN DataFrame, granularitaetsunabhaengig (nur aus Quartals-Baseline)
    video_ebene: EIN DataFrame, eine Zeile je Video (Base + Main), inkl. beider Periodenspalten."""
    videos = pd.read_csv(video_path, usecols=["channel_id", "channel_title", "video_id", "published_at"])
    videos["published_at"] = pd.to_datetime(videos["published_at"], errors="coerce", utc=True).dt.tz_localize(None)

    dimensionen = ["volkszentrismus", "antielitismus", "manichaeische_moralisierung",
                   "emotionale_intensitaet"]
    alle_dimensionen = dimensionen + [GESAMTSCORE_NAME]
    usecols = ["video_id"] + dimensionen + ["ukraine_bezug"]

    pop_base = pd.read_csv(results_path_base, usecols=usecols)
    pop_main = pd.read_csv(results_path_main, usecols=usecols, low_memory = False)

    video_base = _video_populismus(pop_base, videos, dimensionen)
    video_main = _video_populismus(pop_main, videos, dimensionen)

    # Ueberlappungspruefung auf Video-Ebene: derselbe video_id sollte nicht in Base UND Main
    # klassifiziert worden sein (praeziser als der vorherige Check auf Kanal-Periode-Ebene).
    ueberlappende_ids = set(video_base["video_id"]) & set(video_main["video_id"])
    if ueberlappende_ids:
        print(f"[Warnung] {len(ueberlappende_ids)} video_id(s) in Base UND Main klassifiziert "
              f"(sollte nicht vorkommen): {sorted(ueberlappende_ids)}")
    else:
        print("[OK] Keine ueberlappenden video_ids zwischen Base und Main.")

    video_base = video_base.assign(quelle="base")
    video_main = video_main.assign(quelle="main")
    video_ebene = pd.concat([video_base, video_main], ignore_index=True)
    print(f"[Video-Ebene] {len(video_ebene)} Videos ({len(video_base)} Base, {len(video_main)} Main), "
          f"{video_ebene['channel_id'].nunique()} Kanaele.")

    zeitreihen = {}
    for granularitaet, cfg in GRANULARITAETEN.items():
        spalte = cfg["spalte"]

        periode_alle = _kanal_periode_aus_video(video_ebene, alle_dimensionen, spalte)

        lang = periode_alle.melt(
            id_vars=["channel_id", "channel_title", spalte, "n_videos"],
            value_vars=alle_dimensionen,
            var_name="dimension",
            value_name="wert",
        )
        zeitreihen[granularitaet] = lang
        print(f"[Zeitreihe][{granularitaet}] {lang['channel_id'].nunique()} Kanaele, "
              f"{periode_alle[spalte].nunique()} Perioden, {len(lang)} Zeilen.")

    # Kanalweite Baseline-Klassifikation: bewusst granularitaetsunabhaengig, nur aus den
    # Base-Videos (Quartals-Periodenspalte fuer die Aggregationsreihenfolge, wie zuvor).
    spalte_quartal = GRANULARITAETEN["quartal"]["spalte"]
    periode_base = _kanal_periode_aus_video(
        video_ebene[video_ebene["quelle"] == "base"], alle_dimensionen, spalte_quartal
    )

    kanal_klassifikation = periode_base.groupby(
        ["channel_id", "channel_title"], as_index=False
    ).agg(**{d: (d, "mean") for d in alle_dimensionen},
          n_quartale_besetzt=(spalte_quartal, "nunique"))

    n_videos_total = periode_base.groupby(
        ["channel_id", "channel_title"], as_index=False
    ).agg(n_videos_total=("n_videos", "sum"))
    kanal_klassifikation = pd.merge(kanal_klassifikation, n_videos_total,
                                     on=["channel_id", "channel_title"], how="left")

    print(f"[Klassifikation] {len(kanal_klassifikation)} Kanaele, "
          f"{(kanal_klassifikation['n_quartale_besetzt'] == 1).sum()} davon mit nur 1 Quartal.")

    return zeitreihen, kanal_klassifikation, video_ebene


# =========================================================
# IDEOLOGIE
# =========================================================

def prepare_ideology_results(results_path_ideology, video_path):
    videos = pd.read_csv(video_path, usecols=["channel_id", "channel_title", "video_id"])
    dimensionen = ["wirtschaft", "gesellschaft"]

    id_results = pd.read_csv(results_path_ideology, usecols=["video_id"] + dimensionen)
    id_results = pd.merge(id_results, videos, on="video_id", how="left")

    # Bewusst einfacher Video-Mittelwert, NICHT ueber Quartal gewichtet
    # (anders als bei der Populismus-Zeitreihe) - hier nur einmaliger Kanalwert.
    id_results_grouped = id_results.groupby("channel_title", as_index=False).agg(
        channel_id=("channel_id", "first"),
        gesellschaft_mean=("gesellschaft", "mean"),
        wirtschaft_mean=("wirtschaft", "mean"),
        gesellschaft_median=("gesellschaft", "median"),
        wirtschaft_median=("wirtschaft", "median"),
        n_videos=("channel_id", "count"),
    )

    print(f"[Ideologie] {len(id_results)} Segmente/Videos, "
          f"{id_results_grouped['channel_id'].nunique()} Kanaele.")
    return id_results_grouped


# =========================================================
# POSITION / STANCE
# =========================================================

def prepare_position_results(results_path_position, video_path):
    """Gibt (zeitreihen, video_ebene) zurueck.
    zeitreihen: dict {granularitaet: Long-Format-DataFrame}
    video_ebene: EIN DataFrame, eine Zeile je Video, inkl. beider Periodenspalten."""
    videos = pd.read_csv(video_path, usecols=["channel_id", "channel_title", "video_id", "published_at"])
    videos["published_at"] = pd.to_datetime(videos["published_at"], errors="coerce", utc=True).dt.tz_localize(None)

    pos = pd.read_csv(results_path_position, usecols=["video_id", "rus_status", "rus_score",
                                                        "west_status", "west_score", "emo_intensitaet"])
    pos = pd.merge(pos, videos, on="video_id", how="left")

    ohne_datum = pos["published_at"].isna()
    if ohne_datum.any():
        print(f"[Warnung] {int(ohne_datum.sum())} Segmente ohne published_at -> verworfen.")
        pos = pos[~ohne_datum]

    pos = ergaenze_periodenspalten(pos)
    periodenspalten = [cfg["spalte"] for cfg in GRANULARITAETEN.values()]

    # Score nur aus "bewertend"-Segmenten; deskriptive Erwaehnungen separat zaehlen
    pos["rus_score_bewertend"] = pos["rus_score"].where(pos["rus_status"] == "bewertend")
    pos["west_score_bewertend"] = pos["west_score"].where(pos["west_status"] == "bewertend")
    pos["ist_deskriptiv_rus"] = (pos["rus_status"] == "deskriptiv").astype(int)
    pos["ist_deskriptiv_west"] = (pos["west_status"] == "deskriptiv").astype(int)

    # Segment -> Video (einmalig, mit beiden Periodenspalten gleichzeitig)
    video_ebene = pos.groupby(
        ["channel_id", "channel_title", "video_id"] + periodenspalten, as_index=False
    ).agg(
        position_russland=("rus_score_bewertend", "mean"),
        n_deskriptiv_russland=("ist_deskriptiv_rus", "sum"),
        position_westpolitik=("west_score_bewertend", "mean"),
        n_deskriptiv_westpolitik=("ist_deskriptiv_west", "sum"),
        emotion=("emo_intensitaet", "mean"),
    )
    print(f"[Video-Ebene] {len(video_ebene)} Videos, {video_ebene['channel_id'].nunique()} Kanaele.")

    zeitreihen = {}
    for granularitaet, cfg in GRANULARITAETEN.items():
        spalte = cfg["spalte"]

        periode = video_ebene.groupby(
            ["channel_id", "channel_title", spalte], as_index=False
        ).agg(
            position_russland=("position_russland", "mean"),
            n_videos_russland=("position_russland", "count"),   # nur Videos mit >=1 bewertendem Segment
            n_deskriptiv_russland=("n_deskriptiv_russland", "sum"),
            position_westpolitik=("position_westpolitik", "mean"),
            n_videos_westpolitik=("position_westpolitik", "count"),
            n_deskriptiv_westpolitik=("n_deskriptiv_westpolitik", "sum"),
            emotion=("emotion", "mean"),
            n_videos_emotion=("emotion", "count"),
        )

        teile = []
        for dim, wert_spalte, n_spalte, n_deskr_spalte in [
            ("position_russland", "position_russland", "n_videos_russland", "n_deskriptiv_russland"),
            ("position_westpolitik", "position_westpolitik", "n_videos_westpolitik", "n_deskriptiv_westpolitik"),
            ("emotion", "emotion", "n_videos_emotion", None),
        ]:
            teil = periode[["channel_id", "channel_title", spalte, wert_spalte, n_spalte]].rename(
                columns={wert_spalte: "wert_roh", n_spalte: "n_videos"}
            )
            teil["n_deskriptiv"] = periode[n_deskr_spalte] if n_deskr_spalte else np.nan
            teil["dimension"] = dim
            teile.append(teil)

        lang = pd.concat(teile, ignore_index=True)
        zeitreihen[granularitaet] = lang
        print(f"[Position][{granularitaet}] {lang['channel_id'].nunique()} Kanaele, "
              f"{periode[spalte].nunique()} Perioden, {len(lang)} Zeilen.")

    return zeitreihen, video_ebene


id_results_grouped = prepare_ideology_results(RESULTS_PATH_IDEOLOGY, VIDEO_PATH)
id_results_grouped.to_csv(RESULTS_PATH / "channel_classification_ideology.csv", index=False)

zeitreihen_populismus, kanal_klassifikation, video_ebene_populismus = prepare_populism_results(
    RESULTS_PATH_POPULISM_BASE, RESULTS_PATH_POPULISM_MAIN, VIDEO_PATH
)
for granularitaet, cfg in GRANULARITAETEN.items():
    dateiname = f"channel_{cfg['datei_suffix']}_populism_timeseries.csv"
    zeitreihen_populismus[granularitaet].to_csv(RESULTS_PATH / dateiname, index=False)
kanal_klassifikation.to_csv(RESULTS_PATH / "channel_classification_populism.csv", index=False)
video_ebene_populismus.to_csv(RESULTS_PATH / "channel_video_populism.csv", index=False)

zeitreihen_position, video_ebene_position = prepare_position_results(RESULTS_PATH_STANCE, VIDEO_PATH)
for granularitaet, cfg in GRANULARITAETEN.items():
    dateiname = f"channel_{cfg['datei_suffix']}_position_timeseries.csv"
    zeitreihen_position[granularitaet].to_csv(RESULTS_PATH / dateiname, index=False)
video_ebene_position.to_csv(RESULTS_PATH / "channel_video_position.csv", index=False)
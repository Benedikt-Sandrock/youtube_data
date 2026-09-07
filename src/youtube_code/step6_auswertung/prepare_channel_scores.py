import os
import pandas as pd
import numpy as np

from youtube_code.config import OUTPUTS, SAMPLES
from youtube_code.store import llm_run_store, screening_state_store, video_registry

RESULTS_PATH = OUTPUTS / "segment_analysis"   # Ziel-/Lese-Ordner fuer abgeleitete Outputs
os.makedirs(RESULTS_PATH, exist_ok= True)
# Runs werden automatisch aus llm_runs.sqlite gesucht (source + prompt_id),
# statt einzelne run_NNNN-Dateipfade hart zu kodieren - siehe
# llm_run_store.get_results_for_prompt(). "downloaded"-Runs mit einer
# dataset_id, die EXCLUDE_DATASET_SUBSTRING enthaelt (Test-/Pilot-Laeufe,
# z.B. "single_channels_test_populism_segments"), werden dabei ausgeschlossen.
SOURCE = "segment_analysis_active"
PROMPT_IDEOLOGIE = "IDEOLOGIE_I"
PROMPT_POPULISMUS = "POPULISMUS_P"
PROMPT_POSITION = "POSITION_V1"
EXCLUDE_DATASET_SUBSTRING = "test"

# Kanal-Sample wird automatisch aus der kanonischen Sample-Definition
# (step1_sample/build_channel_provenance.py) geladen, statt aus einer
# manuell gepflegten Video-Metadaten-CSV.
ANALYSIS_ID = "russia_longitudinal_v1"
CHANNEL_SAMPLE_PATH = SAMPLES / ANALYSIS_ID / "channel_sample_provenance.csv"


KRIEGSBEGINN = "2022-02-24"

GESAMTSCORE_NAME = "populismus_gesamt"
GESAMTSCORE_AUS = ["volkszentrismus", "antielitismus", "manichaeische_moralisierung"]
POPULISM_VARS = ["volkszentrismus", "antielitismus", "manichaeische_moralisierung", "emotionale_intensitaet"]

# Baseline-Fenster fuer channel_classification_populism.csv: dieselben
# interval_index-Werte wie in step4_transcript_download/select_targets.py
# ::select_baseline_targets() - Vorkriegsfenster [0,1,2,3], Postwar-
# Baseline-Sentinel -1 (siehe step2_baseline_channels/README.md §1).
BASELINE_INTERVAL_INDIZES = [-1, 0, 1, 2, 3]

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
# Automatische Datenbeschaffung (llm_runs + Kanal-Sample)
# =========================================================

def _lade_llm_ergebnisse(prompt_id):
    """
    Holt alle Ergebniszeilen aller "downloaded"-Runs mit gegebenem prompt_id
    unter SOURCE (llm_run_store.get_results_for_prompt()), wendet die
    Test-Run-Ausschlussregel an und loest verbleibende video_id-
    Ueberlappungen zwischen Runs auf (z.B. ein Video, das versehentlich in
    zwei unterschiedlichen Batches klassifiziert wurde): pro video_id
    gewinnt der hoechste run_id, die Zeilen der verdraengten Runs fuer
    dieselbe video_id werden verworfen. Gibt das bereinigte DataFrame
    zurueck (inkl. run_id/dataset_id/allen Ergebnisspalten).
    """
    df = llm_run_store.get_results_for_prompt(prompt_id, source=SOURCE)
    if df.empty:
        raise ValueError(f"Keine Ergebnisse fuer prompt_id={prompt_id!r}, source={SOURCE!r} gefunden.")

    n_vor = len(df)
    ist_test = df["dataset_id"].fillna("").str.contains(EXCLUDE_DATASET_SUBSTRING, case=False)
    if ist_test.any():
        test_runs = sorted(df.loc[ist_test, "run_id"].unique())
        df = df[~ist_test]
        print(f"[{prompt_id}] {n_vor - len(df)} Zeile(n) aus Test-Runs {test_runs} ausgeschlossen.")

    gewinner_run = df.groupby("video_id")["run_id"].transform("max")
    ueberschrieben = df["run_id"] != gewinner_run
    if ueberschrieben.any():
        betroffene_videos = df.loc[ueberschrieben, "video_id"].nunique()
        verdraengte_runs = sorted(df.loc[ueberschrieben, "run_id"].unique())
        print(f"[{prompt_id}] [Warnung] {betroffene_videos} video_id(s) in mehreren Runs klassifiziert - "
              f"jeweils neuester Run gewinnt, Zeilen aus {verdraengte_runs} verworfen.")
        df = df[~ueberschrieben]

    return df.reset_index(drop=True)


def _lade_kanal_sample():
    """Gibt die Menge der channel_id's mit eligible_current_analysis == True aus der
    kanonischen Sample-Definition (CHANNEL_SAMPLE_PATH) zurueck."""
    sample = pd.read_csv(CHANNEL_SAMPLE_PATH, usecols=["channel_id", "eligible_current_analysis"])
    return set(sample.loc[sample["eligible_current_analysis"] == True, "channel_id"])


def _lade_video_metadaten(video_ids, eligible_channel_ids):
    """
    Video-Metadaten (channel_id, channel_title, published_at) live aus der
    video_registry statt aus einer manuell gepflegten CSV. Der
    Mindestlaengen-Filter von get_video_metadata() wird bewusst deaktiviert
    (min_duration_seconds=None) - die Videos sind bereits klassifiziert,
    ein nachtraeglicher Laengenfilter wuerde nur stillschweigend Zeilen
    verlieren. Anschliessend Filterung auf eligible_channel_ids (aktuell
    gueltiges Kanal-Sample, siehe _lade_kanal_sample()).
    """
    videos = video_registry.get_video_metadata(video_ids=video_ids, min_duration_seconds=None)
    videos = videos[["channel_id", "channel_title", "video_id", "published_at"]]
    videos["published_at"] = pd.to_datetime(videos["published_at"], errors="coerce", utc=True).dt.tz_localize(None)

    n_vor = len(videos)
    videos = videos[videos["channel_id"].isin(eligible_channel_ids)]
    if n_vor - len(videos):
        print(f"  {n_vor - len(videos)} Video(s) ausserhalb des aktuellen Kanal-Samples "
              f"(eligible_current_analysis) verworfen.")
    return videos


# =========================================================
# Korrekturen an den LLM-Rohergebnissen
# =========================================================

def _korrigiere_populismus(df):
    """kodierbar == False -> alle vier Populismus-/Intensitaets-Dimensionen auf NaN setzen.
    Der Prompt (segment_prompts_simple.py) sieht das so vor (nicht-politischer Inhalt
    bekommt kodierbar=false und null-Dimensionswerte), wird vom LLM aber nicht immer
    sauber eingehalten - diese Korrektur erzwingt es nachtraeglich."""
    mask = df["kodierbar"] == False
    df.loc[mask, POPULISM_VARS] = np.nan
    return df


def _korrigiere_position(df):
    """rus_status/west_status == 'deskriptiv' -> rus_score/west_score auf 0 setzen
    (statt roh NaN). 'deskriptiv' bedeutet: Thema kommt vor, wird aber nicht bewertet -
    das entspricht einer neutralen Position (0) auf der -2..+2-Skala, nicht einem
    fehlenden Wert. Wichtig: die Video-/Kanal-Aggregation unten mittelt danach direkt
    ueber rus_score/west_score (kein .where(status=="bewertend")-Ausschluss mehr) -
    sonst wuerde diese Korrektur von der Aggregation gleich wieder maskiert.
    'nicht_thematisiert' bleibt unveraendert NaN (roh nie gesetzt) und wird von
    pandas' mean() weiterhin automatisch ausgeschlossen."""
    df.loc[df["rus_status"] == "deskriptiv", "rus_score"] = 0
    df.loc[df["west_status"] == "deskriptiv", "west_score"] = 0
    return df


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


def prepare_populism_results():
    """Gibt (zeitreihen, kanal_klassifikation, video_ebene) zurueck.
    zeitreihen: dict {granularitaet: Long-Format-DataFrame}
    kanal_klassifikation: EIN DataFrame, granularitaetsunabhaengig (nur aus dem
        Baseline-Fenster, siehe BASELINE_INTERVAL_INDIZES)
    video_ebene: EIN DataFrame, eine Zeile je Video, inkl. beider Periodenspalten."""
    pop = _lade_llm_ergebnisse(PROMPT_POPULISMUS)
    pop = _korrigiere_populismus(pop)

    dimensionen = ["volkszentrismus", "antielitismus", "manichaeische_moralisierung",
                   "emotionale_intensitaet"]
    alle_dimensionen = dimensionen + [GESAMTSCORE_NAME]

    eligible_channel_ids = _lade_kanal_sample()
    videos = _lade_video_metadaten(pop["video_id"].unique(), eligible_channel_ids)

    video_ebene = _video_populismus(pop, videos, dimensionen)
    print(f"[Video-Ebene] {len(video_ebene)} Videos, {video_ebene['channel_id'].nunique()} Kanaele.")

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

    # Kanalweite Baseline-Klassifikation: granularitaetsunabhaengig, nur aus Videos im
    # Baseline-Fenster (Vorkriegsintervalle 0-3 bzw. Postwar-Sentinel -1, siehe
    # screening_state_store/select_baseline_targets()), unabhaengig davon aus welchem
    # Run ein Video stammt.
    state = screening_state_store.get_state(video_ids=video_ebene["video_id"].tolist())
    baseline_ids = set(state.loc[state["interval_index"].isin(BASELINE_INTERVAL_INDIZES), "video_id"])
    video_ebene_baseline = video_ebene[video_ebene["video_id"].isin(baseline_ids)]

    spalte_quartal = GRANULARITAETEN["quartal"]["spalte"]
    periode_base = _kanal_periode_aus_video(video_ebene_baseline, alle_dimensionen, spalte_quartal)

    kanal_klassifikation = periode_base.groupby(
        ["channel_id", "channel_title"], as_index=False
    ).agg(**{d: (d, "mean") for d in alle_dimensionen},
          n_quartale_besetzt=(spalte_quartal, "nunique"))

    n_videos_total = periode_base.groupby(
        ["channel_id", "channel_title"], as_index=False
    ).agg(n_videos_total=("n_videos", "sum"))
    kanal_klassifikation = pd.merge(kanal_klassifikation, n_videos_total,
                                     on=["channel_id", "channel_title"], how="left")

    print(f"[Klassifikation] {len(kanal_klassifikation)} Kanaele (aus {len(video_ebene_baseline)} "
          f"Baseline-Videos), {(kanal_klassifikation['n_quartale_besetzt'] == 1).sum()} davon mit nur 1 Quartal.")

    return zeitreihen, kanal_klassifikation, video_ebene


# =========================================================
# IDEOLOGIE
# =========================================================

def prepare_ideology_results():
    dimensionen = ["wirtschaft", "gesellschaft"]

    id_results = _lade_llm_ergebnisse(PROMPT_IDEOLOGIE)
    eligible_channel_ids = _lade_kanal_sample()
    videos = _lade_video_metadaten(id_results["video_id"].unique(), eligible_channel_ids)
    videos = videos[["channel_id", "channel_title", "video_id"]]

    id_results = pd.merge(id_results[["video_id"] + dimensionen], videos, on="video_id", how="left")

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

def prepare_position_results():
    """Gibt (zeitreihen, video_ebene) zurueck.
    zeitreihen: dict {granularitaet: Long-Format-DataFrame}
    video_ebene: EIN DataFrame, eine Zeile je Video, inkl. beider Periodenspalten."""
    pos = _lade_llm_ergebnisse(PROMPT_POSITION)
    pos = _korrigiere_position(pos)

    eligible_channel_ids = _lade_kanal_sample()
    videos = _lade_video_metadaten(pos["video_id"].unique(), eligible_channel_ids)

    pos = pos[["video_id", "rus_status", "rus_score", "west_status", "west_score", "emo_intensitaet"]]
    pos = pd.merge(pos, videos, on="video_id", how="left")

    ohne_datum = pos["published_at"].isna()
    if ohne_datum.any():
        print(f"[Warnung] {int(ohne_datum.sum())} Segmente ohne published_at -> verworfen.")
        pos = pos[~ohne_datum]

    pos = ergaenze_periodenspalten(pos)
    periodenspalten = [cfg["spalte"] for cfg in GRANULARITAETEN.values()]

    # rus_score/west_score sind nach _korrigiere_position() bereits die richtige
    # Eingabe fuer die Mittelwertbildung (bewertend -> echter Score, deskriptiv -> 0,
    # nicht_thematisiert -> weiterhin NaN, wird von mean() automatisch ausgeschlossen).
    pos["ist_deskriptiv_rus"] = (pos["rus_status"] == "deskriptiv").astype(int)
    pos["ist_deskriptiv_west"] = (pos["west_status"] == "deskriptiv").astype(int)

    # Segment -> Video (einmalig, mit beiden Periodenspalten gleichzeitig)
    video_ebene = pos.groupby(
        ["channel_id", "channel_title", "video_id"] + periodenspalten, as_index=False
    ).agg(
        position_russland=("rus_score", "mean"),
        n_deskriptiv_russland=("ist_deskriptiv_rus", "sum"),
        position_westpolitik=("west_score", "mean"),
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
            n_videos_russland=("position_russland", "count"),   # nur Videos mit >=1 bewertendem/deskriptivem Segment
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


def main():
    id_results_grouped = prepare_ideology_results()
    id_results_grouped.to_csv(RESULTS_PATH / "channel_classification_ideology.csv", index=False)

    zeitreihen_populismus, kanal_klassifikation, video_ebene_populismus = prepare_populism_results()
    for granularitaet, cfg in GRANULARITAETEN.items():
        dateiname = f"channel_{cfg['datei_suffix']}_populism_timeseries.csv"
        zeitreihen_populismus[granularitaet].to_csv(RESULTS_PATH / dateiname, index=False)
    kanal_klassifikation.to_csv(RESULTS_PATH / "channel_classification_populism.csv", index=False)
    video_ebene_populismus.to_csv(RESULTS_PATH / "channel_video_populism.csv", index=False)

    zeitreihen_position, video_ebene_position = prepare_position_results()
    for granularitaet, cfg in GRANULARITAETEN.items():
        dateiname = f"channel_{cfg['datei_suffix']}_position_timeseries.csv"
        zeitreihen_position[granularitaet].to_csv(RESULTS_PATH / dateiname, index=False)
    video_ebene_position.to_csv(RESULTS_PATH / "channel_video_position.csv", index=False)


if __name__ == "__main__":
    main()

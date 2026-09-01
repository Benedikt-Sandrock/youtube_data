"""
Periodenberechnung fuer select_cell_fill_targets() (Konfiguration 2 aus
COMPLETE_PROCESS.md Schritt 4).

relativ_periode() ist bewusst aus
youtube_code/step5_segment_analysis/finde_download_kandidaten.py gespiegelt statt
von dort importiert, um Schritt 4 nicht an den dortigen, legacy CSV-basierten
Pfad zu koppeln - siehe README.md in diesem Ordner fuer die Begruendung, warum
diese Rechnung statt screening_state_store.interval_index/period verwendet
wird (deckt auch die Zeit nach Kriegsbeginn ab, feinere Granularitaet).
"""
import pandas as pd

# Invasionsdatum - identisch zu KRIEGSBEGINN in finde_download_kandidaten.py.
KRIEGSBEGINN = pd.Timestamp("2022-02-24")

GRANULARITAET_MONATE = {"monat": 1, "quartal": 3}


def relativ_periode(datum: pd.Series, start: pd.Timestamp, monate_pro_periode: int) -> pd.Series:
    """
    Ganzzahlige Periode relativ zu start, in Schritten von monate_pro_periode
    Monaten (1=Monat, 3=Quartal). Identisch zur Logik in
    finde_download_kandidaten.py/prepare_channel_scores.py: Monatsdifferenz
    inkl. Tages-Korrektur (ein Datum vor dem Tag-des-Monats von start zaehlt
    noch zur vorherigen Periode), dann durch monate_pro_periode geteilt.
    """
    monate = (datum.dt.year - start.year) * 12 + (datum.dt.month - start.month)
    monate = monate - (datum.dt.day < start.day).astype(int)
    return (monate // monate_pro_periode).astype(int)


def add_period_column(df: pd.DataFrame, granularity: str, published_col: str = "published_at") -> pd.DataFrame:
    """
    Haengt df eine "period"-Spalte an (rel_monat oder rel_quartal je nach
    granularity), berechnet aus published_col. Zeilen mit fehlendem/nicht
    parsebarem Datum werden verworfen (Muster: "ohne_datum"-Filter in
    finde_download_kandidaten.lade_kriegsvideo_kandidaten - relativ_periode()
    kann mit NaT nicht rechnen).
    """
    if granularity not in GRANULARITAET_MONATE:
        raise ValueError(f"Unbekannte granularity {granularity!r}, erwartet: {list(GRANULARITAET_MONATE)}")

    out = df.copy()
    datum = pd.to_datetime(out[published_col], errors="coerce", utc=True).dt.tz_localize(None)
    ohne_datum = datum.isna()
    if ohne_datum.any():
        out = out[~ohne_datum]
        datum = datum[~ohne_datum]

    out["period"] = relativ_periode(datum, KRIEGSBEGINN, GRANULARITAET_MONATE[granularity])
    return out

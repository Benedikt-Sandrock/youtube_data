"""
Aktivitaetsphasen-basierte Klassifikation von Kanaelen fuer die Baseline-
Fensterzuweisung (siehe README.md Abschnitt 1).

Hintergrund: channel_created_at (Kanal-Gruendungsdatum) allein ist kein
verlaessliches Kriterium dafuer, ob ein Kanal das globale Vorkriegsfenster
(Monate -12 bis -1 vor Kriegsbeginn) sinnvoll ausfuellen kann. Zwei Faelle
brechen die reine Datums-Regel:

1. Ein Kanal ist alt (channel_created_at lange vor Kriegsbeginn), hat seine
   urspruengliche Aktivitaet aber eingestellt und ist erst Jahre spaeter -
   ggf. erst nach Kriegsbeginn - wieder aktiv geworden. channel_created_at
   suggeriert "vorkriegskanal", das globale Vorkriegsfenster enthaelt aber
   keine (oder kaum) Videos.
2. Ein Kanal wurde nach Kriegsbeginn gegruendet, laedt seine ersten Videos
   aber erst deutlich spaeter hoch (z.B. Gruendung 2022-03-01, erste
   Videos erst 2024). assign_postwar_baseline.py setzte den Fensteranfang
   bisher auf channel_created_at - dort liegen dann ebenfalls keine
   Kandidaten.

Dieses Modul bestimmt stattdessen je Kanal datengetrieben "Aktivitaets-
phasen" aus der tatsaechlichen Upload-Historie (video_registry) und leitet
daraus sowohl die Fenster-Gruppe (vorkriegskanal/nachkriegskanal/
ausgeschlossen) als auch den zu verwendenden Fenster-Anchor ab. Ersetzt die
reine channel_created_at-vs-Kriegsbeginn-Regel, die zuvor direkt in
assign_postwar_baseline.py und check_baseline_availability.py stand.

Kategorien (siehe classify_channel_activity):
- aktivitaet_deckt_kriegsbeginn: Eine Aktivitaetsphase deckt den
  Kriegsbeginn direkt ab - Kanal war durchgehend aktiv. war_group
  "vorkriegskanal", Anchor irrelevant (globales Fenster gilt).
- reaktiviert_faelschlich_vorkrieg: channel_created_at vor Kriegsbeginn,
  aber keine Phase deckt den Kriegsbeginn ab und die naechste Phase
  beginnt erst danach. war_group "nachkriegskanal", Anchor = Beginn dieser
  Phase (NICHT channel_created_at).
- nachkrieg_verzoegerter_start: channel_created_at nach Kriegsbeginn, aber
  die erste Aktivitaetsphase beginnt deutlich spaeter (Luecke >=
  GAP_THRESHOLD_MONTHS). war_group "nachkriegskanal", Anchor = Beginn
  dieser Phase (NICHT channel_created_at).
- nachkrieg_konsistent: channel_created_at nach Kriegsbeginn, erste
  Aktivitaetsphase beginnt nah an der Gruendung. war_group
  "nachkriegskanal", Anchor = Beginn dieser Phase (praktisch identisch zu
  channel_created_at).
- tot_zum_kriegsbeginn: letzte Aktivitaetsphase vor Kriegsbeginn war zum
  Kriegsbeginn schon abgeschlossen, keine neue Phase danach. war_group
  "ausgeschlossen" (Nutzer-Entscheidung: kein sinnvolles Signal nahe am
  Kriegsbeginn).
- nachkrieg_keine_aktivitaet: channel_created_at nach Kriegsbeginn, aber
  keine Aktivitaetsphase danach gefunden - i.d.R. eine Datenanomalie.
  war_group "ausgeschlossen", manuell pruefen.
- keine_videos_bekannt: keine Videos in der video_registry fuer den Kanal.
  war_group "ausgeschlossen".

Herkunft: Diese Logik wurde zuerst als einmalige Diagnose in
scripts/adhoc/diagnose_reactivated_baseline_channels.py entwickelt (dort
liegt auch die Auswertung der Kategorienverteilung ueber das aktuelle
Sample) und hierher verallgemeinert, damit assign_postwar_baseline.py und
check_baseline_availability.py dieselbe Logik verwenden statt sie zu
duplizieren.
"""
from __future__ import annotations

import pandas as pd

# ============================================================
# CONFIG
# ============================================================

KRIEGSBEGINN = pd.Timestamp("2022-02-24")

# Ab welcher Luecke zwischen zwei aufeinanderfolgenden Uploads eine neue
# Aktivitaetsphase beginnt. Symmetrisch zum groessten Schritt in
# assign_postwar_baseline.WINDOW_STEPS_MONTHS ([3, 6, 9, 12]) gewaehlt.
GAP_THRESHOLD_MONTHS = 12

# pd.DateOffset(months=...) laesst sich nicht direkt mit einem Timedelta
# vergleichen - daher einmalig ueber die durchschnittliche Monatslaenge in
# einen Timedelta umgerechnet (30.44 Tage/Monat reicht fuer eine
# 12-Monats-Schwelle voellig aus).
GAP_THRESHOLD = pd.Timedelta(days=GAP_THRESHOLD_MONTHS * 30.44)

WAR_GROUP_BY_KATEGORIE = {
    "aktivitaet_deckt_kriegsbeginn": "vorkriegskanal",
    "reaktiviert_faelschlich_vorkrieg": "nachkriegskanal",
    "nachkrieg_verzoegerter_start": "nachkriegskanal",
    "nachkrieg_konsistent": "nachkriegskanal",
    "tot_zum_kriegsbeginn": "ausgeschlossen",
    "nachkrieg_keine_aktivitaet": "ausgeschlossen",
    "keine_videos_bekannt": "ausgeschlossen",
}


# ============================================================
# AKTIVITAETSPHASEN
# ============================================================

def find_activity_phases(
    dates: pd.Series, gap_threshold_months: int = GAP_THRESHOLD_MONTHS
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Segmentiert sortierte Upload-Daten eines Kanals in zusammenhaengende
    Aktivitaetsphasen: zwei aufeinanderfolgende Videos gehoeren zur selben
    Phase, wenn ihr zeitlicher Abstand < gap_threshold_months ist. Gibt eine
    nach phase_start aufsteigend sortierte Liste von (phase_start, phase_end)
    zurueck (leer, falls dates leer ist)."""
    sorted_dates = dates.sort_values().reset_index(drop=True)
    if sorted_dates.empty:
        return []

    threshold = (
        GAP_THRESHOLD
        if gap_threshold_months == GAP_THRESHOLD_MONTHS
        else pd.Timedelta(days=gap_threshold_months * 30.44)
    )
    phases: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    phase_start = phase_end = sorted_dates.iloc[0]

    for d in sorted_dates.iloc[1:]:
        if d - phase_end >= threshold:
            phases.append((phase_start, phase_end))
            phase_start = d
        phase_end = d
    phases.append((phase_start, phase_end))
    return phases


def classify_channel_activity(
    channel_created_at: pd.Timestamp, phases: list[tuple[pd.Timestamp, pd.Timestamp]]
) -> dict:
    """Ordnet einen Kanal anhand seiner Aktivitaetsphasen (siehe
    find_activity_phases) und seines channel_created_at einer der Kategorien
    aus dem Modul-Docstring zu. Gibt ein Dict mit 'kategorie', 'war_group',
    'anchor_date' (der fuer die Fensterzuweisung zu verwendende Startpunkt -
    NaT fuer 'vorkriegskanal', wo das globale Fenster gilt, sowie fuer
    ausgeschlossene Kanaele) und den Debug-Feldern phase_vor_kriegsbeginn_*/
    phase_nach_kriegsbeginn_* zurueck."""
    if not phases:
        kategorie = "keine_videos_bekannt"
        return {
            "kategorie": kategorie,
            "war_group": WAR_GROUP_BY_KATEGORIE[kategorie],
            "anchor_date": pd.NaT,
            "phase_vor_kriegsbeginn_start": pd.NaT,
            "phase_vor_kriegsbeginn_ende": pd.NaT,
            "phase_nach_kriegsbeginn_start": pd.NaT,
            "phase_nach_kriegsbeginn_ende": pd.NaT,
        }

    traegt_kriegsbeginn = next(
        ((s, e) for s, e in phases if s <= KRIEGSBEGINN <= e), None
    )
    phasen_vor = [p for p in phases if p[1] < KRIEGSBEGINN]
    phasen_nach = [p for p in phases if p[0] > KRIEGSBEGINN]
    letzte_vor = phasen_vor[-1] if phasen_vor else None
    erste_nach = phasen_nach[0] if phasen_nach else None
    ist_vorkriegskanal = pd.notna(channel_created_at) and channel_created_at < KRIEGSBEGINN

    if traegt_kriegsbeginn is not None:
        kategorie = "aktivitaet_deckt_kriegsbeginn"
        anchor_date = pd.NaT
    elif ist_vorkriegskanal:
        if erste_nach is not None:
            kategorie = "reaktiviert_faelschlich_vorkrieg"
            anchor_date = erste_nach[0]
        else:
            kategorie = "tot_zum_kriegsbeginn"
            anchor_date = pd.NaT
    elif erste_nach is None:
        # channel_created_at nach Kriegsbeginn (oder unbekannt), aber gar
        # keine Aktivitaetsphase danach - i.d.R. eine Datenanomalie.
        kategorie = "nachkrieg_keine_aktivitaet"
        anchor_date = pd.NaT
    elif pd.isna(channel_created_at) or (erste_nach[0] - channel_created_at) >= GAP_THRESHOLD:
        kategorie = "nachkrieg_verzoegerter_start"
        anchor_date = erste_nach[0]
    else:
        kategorie = "nachkrieg_konsistent"
        anchor_date = erste_nach[0]

    return {
        "kategorie": kategorie,
        "war_group": WAR_GROUP_BY_KATEGORIE[kategorie],
        "anchor_date": anchor_date,
        "phase_vor_kriegsbeginn_start": letzte_vor[0] if letzte_vor else pd.NaT,
        "phase_vor_kriegsbeginn_ende": letzte_vor[1] if letzte_vor else pd.NaT,
        "phase_nach_kriegsbeginn_start": erste_nach[0] if erste_nach else pd.NaT,
        "phase_nach_kriegsbeginn_ende": erste_nach[1] if erste_nach else pd.NaT,
    }


def classify_channels_bulk(
    channels: pd.DataFrame, uploads: pd.DataFrame
) -> pd.DataFrame:
    """Vektorisiertes Frontend fuer classify_channel_activity ueber mehrere
    Kanaele. `channels` braucht die Spalten channel_id, channel_created_at
    (tz-naive Timestamps); `uploads` braucht channel_id, published_at
    (tz-naive Timestamps, wie von video_registry.get_video_rows_for_channels
    nach pd.to_datetime().dt.tz_localize(None) geliefert). Gibt einen
    DataFrame zurueck: eine Zeile je Kanal aus `channels`, mit channel_id und
    allen Feldern aus classify_channel_activity."""
    uploads_by_channel = {
        cid: group["published_at"] for cid, group in uploads.dropna(subset=["published_at"]).groupby("channel_id")
    }

    rows = []
    for _, row in channels.iterrows():
        cid = row["channel_id"]
        phases = find_activity_phases(
            uploads_by_channel.get(cid, pd.Series(dtype="datetime64[ns]"))
        )
        result = classify_channel_activity(row["channel_created_at"], phases)
        rows.append({"channel_id": cid, **result})

    return pd.DataFrame(rows)

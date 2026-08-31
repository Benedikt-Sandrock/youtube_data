"""
Weist Kanaelen, die ERST NACH Kriegsbeginn erstellt wurden, eine eigene
"Baseline"-Gruppe im Screening-State (screening_state_store) zu.

Hintergrund: Die normale Baseline-Logik (Monate -12 bis -1 relativ zum
globalen Kriegsbeginn) setzt voraus, dass der Kanal vor dem Krieg existierte.
Fuer Kanaele, die es vor dem Krieg nicht gab, gibt es kein "Vorher" - als
Ersatz gilt hier: die ersten paar Monate NACH Kanal-Erstellung (kanal-
individueller Anker statt globalem Kriegsbeginn-Datum).

Technisch: Es werden KEINE neuen Zeilen angelegt und keine geteilte Logik
(create_screening_round.py, submit/merge-Skripte) veraendert. Stattdessen
wird fuer bereits im State vorhandene Zeilen dieser Kanaele im jeweiligen
Erstellungsfenster interval_index auf den Sentinel-Wert POSTWAR_INTERVAL_INDEX
(-1) umgeschrieben - ein Wert, den echte Kalenderintervalle nie annehmen
(Post-Kriegs-Kanaele haben nur period >= 0, Baseline-Kanaele stoppen bei
Intervall-Index 3). Schon vorhandene Klassifikationen (politics_final etc.)
wandern mit und zaehlen sofort auf das neue Intervall-Ziel ein - nichts wird
verworfen oder muss neu eingereicht werden.

Kanaele mit zu wenigen Videos im Fenster werden automatisch erweitert
(3 -> 6 -> 9 -> 12 Monate), bis TARGET_WITH_BUFFER_PER_INTERVAL erreicht ist
oder das Maximalfenster ausgeschoepft ist.

Seit Phase 4d werden nur die tatsaechlich geaenderten Zeilen (die 4 betroffenen
Spalten) per screening_state_store.upsert_state_rows() geschrieben; das
frueher hier erzeugte CSV-Vollkopie-Backup (*.before_postwar_assignment.csv)
entfaellt ersatzlos - SQLite braucht kein manuelles Vollkopie-Backup-Muster.
"""

from __future__ import annotations

import json

import pandas as pd

from youtube_code.config import RAW
from youtube_code.politics_screening.screening_config import (
    TARGET_POLITICAL_PER_INTERVAL,
    TARGET_WITH_BUFFER_PER_INTERVAL,
)
from youtube_code.store import screening_state_store

# ============================================================
# CONFIG
# ============================================================

KRIEGSBEGINN = pd.Timestamp("2022-02-24")

MIN_SUBSCRIBERS = 50_000
WINDOW_STEPS_MONTHS = [3, 6, 9, 12]   # adaptiv erweitert, bis genug Kandidaten da sind

POSTWAR_INTERVAL_INDEX = -1  # Sentinel, kollidiert nie mit echten Kalender-Intervallen

CHANNEL_METADATA_PATH = RAW / "channel_metadata_total.json"
CLASSIFIED_CHANNELS_PATH = RAW / "classified_channels_total.json"

DRY_RUN = False


# ============================================================
# KANDIDATEN-KANAELE ERMITTELN
# ============================================================

def load_postwar_candidate_channels() -> pd.DataFrame:
    """Post-Kriegs-Kanaele mit is_german=True und >= MIN_SUBSCRIBERS Abos.
    Gibt channel_id, channel_title, erstellt (Timestamp) zurueck."""
    with open(CHANNEL_METADATA_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)
    meta_df = pd.DataFrame(meta)
    meta_df["published_at"] = pd.to_datetime(
        meta_df["published_at"], format="ISO8601", utc=True
    ).dt.tz_localize(None)
    meta_df["subscribers"] = pd.to_numeric(meta_df["subscribers"], errors="coerce")

    with open(CLASSIFIED_CHANNELS_PATH, "r", encoding="utf-8") as f:
        classified = json.load(f)
    class_df = pd.DataFrame(classified)[["channel_id", "is_german"]]

    merged = pd.merge(meta_df, class_df, on="channel_id", how="left")
    post_war = merged[merged["published_at"] >= KRIEGSBEGINN].copy()
    kandidaten = post_war[
        (post_war["is_german"] == True) & (post_war["subscribers"] >= MIN_SUBSCRIBERS)
    ][["channel_id", "title", "published_at"]].rename(
        columns={"title": "channel_title", "published_at": "erstellt"}
    )
    return kandidaten.reset_index(drop=True)


# ============================================================
# STATE LADEN UND ZUWEISEN
# ============================================================

def assign_postwar_intervals(
    state: pd.DataFrame,
    kandidaten: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Gibt (aktualisierter State, Zusammenfassung pro Kanal) zurueck."""
    state = state.copy()
    state["published_at_dt"] = pd.to_datetime(
        state["published_at"], errors="coerce", utc=True
    ).dt.tz_localize(None)

    zusammenfassung = []
    geaenderte_indices = []

    for _, row in kandidaten.iterrows():
        cid = row["channel_id"]
        erstellt = row["erstellt"]
        kanal_zeilen = state[state["channel_id"] == cid]

        gewaehltes_fenster_monate = None
        gefundene_zeilen = pd.DataFrame()

        for monate in WINDOW_STEPS_MONTHS:
            fenster_ende = erstellt + pd.DateOffset(months=monate)
            treffer = kanal_zeilen[
                (kanal_zeilen["published_at_dt"] >= erstellt)
                & (kanal_zeilen["published_at_dt"] < fenster_ende)
            ]
            gewaehltes_fenster_monate = monate
            gefundene_zeilen = treffer
            if len(treffer) >= TARGET_WITH_BUFFER_PER_INTERVAL:
                break

        n_political_bereits = int(
            (gefundene_zeilen["politics_final"] == 1).sum()
        ) if not gefundene_zeilen.empty else 0

        zusammenfassung.append({
            "channel_id": cid,
            "channel_title": row["channel_title"],
            "erstellt": erstellt,
            "fenster_monate": gewaehltes_fenster_monate,
            "n_kandidaten_im_fenster": len(gefundene_zeilen),
            "n_bereits_politisch": n_political_bereits,
        })

        geaenderte_indices.extend(gefundene_zeilen.index.tolist())

    summary_df = pd.DataFrame(zusammenfassung)

    state.loc[geaenderte_indices, "interval_index"] = POSTWAR_INTERVAL_INDEX
    state.loc[geaenderte_indices, "interval_label"] = state.loc[
        geaenderte_indices, "channel_id"
    ].map(
        summary_df.set_index("channel_id")["fenster_monate"]
    ).apply(lambda m: f"postwar_0_to_{int(m)}")
    state.loc[geaenderte_indices, "target_political_per_interval"] = TARGET_POLITICAL_PER_INTERVAL
    state.loc[geaenderte_indices, "target_with_buffer_per_interval"] = TARGET_WITH_BUFFER_PER_INTERVAL

    state = state.drop(columns=["published_at_dt"])
    return state, summary_df


def main():
    print(f"Lade Kandidaten-Kanaele (post-war, deutsch, >= {MIN_SUBSCRIBERS:,} Abos)...")
    kandidaten = load_postwar_candidate_channels()
    print(f"{len(kandidaten)} Kandidaten-Kanaele.")

    print("Lade State aus screening_state_store...")
    state = screening_state_store.get_state()
    print(f"{len(state):,} Zeilen im State.")

    updated_state, summary = assign_postwar_intervals(state, kandidaten)

    print("\n" + "=" * 72)
    print("POST-WAR BASELINE ZUWEISUNG")
    print("=" * 72)
    print(f"Kanaele insgesamt: {len(summary)}")
    print(f"  ohne jeden Kandidaten im Fenster (auch nach Erweiterung auf 12 Monate): "
          f"{(summary['n_kandidaten_im_fenster'] == 0).sum()}")
    print(f"  mit >=1, aber < Ziel ({TARGET_WITH_BUFFER_PER_INTERVAL}) Kandidaten: "
          f"{((summary['n_kandidaten_im_fenster'] > 0) & (summary['n_kandidaten_im_fenster'] < TARGET_WITH_BUFFER_PER_INTERVAL)).sum()}")
    print(f"  mit ausreichend (>= {TARGET_WITH_BUFFER_PER_INTERVAL}) Kandidaten: "
          f"{(summary['n_kandidaten_im_fenster'] >= TARGET_WITH_BUFFER_PER_INTERVAL).sum()}")
    print(f"\nFensterlaenge-Verteilung (nur Kanaele mit >=1 Kandidat):")
    print(summary.loc[summary['n_kandidaten_im_fenster'] > 0, 'fenster_monate'].value_counts().sort_index().to_string())
    print(f"\nBereits politisch klassifizierte Videos, die sofort auf das neue Ziel einzahlen: "
          f"{summary['n_bereits_politisch'].sum()}")
    print(f"\nGeaenderte Zeilen im State: {(updated_state['interval_index'] == POSTWAR_INTERVAL_INDEX).sum()}")

    print("\nKanaele ohne jeden Kandidaten (brauchen zuerst Video-Nachdownload):")
    print(summary[summary['n_kandidaten_im_fenster'] == 0][['channel_id', 'channel_title', 'erstellt']].to_string(index=False))

    summary_path = "outputs/segment_analysis/postwar_baseline_assignment_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"\nZusammenfassung gespeichert: {summary_path}")

    if DRY_RUN:
        print("\nDRY RUN: State wurde NICHT geschrieben.")
        return

    changed = updated_state.loc[
        updated_state["interval_index"] == POSTWAR_INTERVAL_INDEX,
        [
            "video_id",
            "interval_index",
            "interval_label",
            "target_political_per_interval",
            "target_with_buffer_per_interval",
        ],
    ]
    written = screening_state_store.upsert_state_rows(changed.to_dict("records"))
    print(f"State aktualisiert in screening_state_store: {written:,} Zeilen.")


if __name__ == "__main__":
    main()

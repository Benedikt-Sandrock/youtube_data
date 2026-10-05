"""
Weist Kanaelen OHNE nutzbares globales Vorkriegsfenster eine eigene
"Baseline"-Gruppe im Screening-State (screening_state_store) zu.

Hintergrund: Die normale Baseline-Logik (Monate -12 bis -1 relativ zum
globalen Kriegsbeginn) setzt voraus, dass der Kanal rund um Kriegsbeginn
tatsaechlich aktiv war. Das trifft nicht nur auf Kanaele zu, die es vor dem
Krieg schlicht noch nicht gab, sondern auch auf zwei subtilere Faelle, die
allein anhand von channel_created_at (Kanal-Gruendungsdatum) nicht zu
erkennen sind (siehe youtube_code.step2_baseline_channels.activity_phases
fuer die vollstaendige Herleitung und alle Kategorien):

- "reaktiviert_faelschlich_vorkrieg": Der Kanal ist alt (channel_created_at
  lange vor Kriegsbeginn), hat seine urspruengliche Aktivitaet aber
  eingestellt und ist erst Jahre spaeter - teils erst nach Kriegsbeginn -
  wieder aktiv geworden. Das globale Vorkriegsfenster enthaelt fuer solche
  Kanaele keine (oder kaum) Videos.
- "nachkrieg_verzoegerter_start": Der Kanal wurde zwar nach Kriegsbeginn
  gegruendet, laedt seine ersten Videos aber erst deutlich spaeter hoch
  (z.B. Gruendung 2022-03-01, erste Videos erst 2024) - der fruehere
  Anker channel_created_at fand dort keine Kandidaten.

Fuer alle drei Faelle (inkl. des Normalfalls "frisch gegruendet und sofort
aktiv") gilt: Als Ersatz-Anchor dient der Beginn der tatsaechlichen,
kriegsnahen Aktivitaetsphase (activity_phases.classify_channel_activity ->
anchor_date), NICHT channel_created_at. Kanaele, deren letzte Aktivitaet
schon vor Kriegsbeginn beendet war und die seither nie wieder aktiv wurden
("tot_zum_kriegsbeginn"), werden bewusst NICHT hierher aufgenommen - sie
liefern unabhaengig vom Anker-Verfahren kein sinnvolles Signal nahe am
Kriegsbeginn (Nutzer-Entscheidung, siehe README.md Abschnitt 1b).

Technisch: Es werden KEINE neuen Zeilen angelegt und keine geteilte Logik
(create_screening_round.py, submit/merge-Skripte) veraendert. Stattdessen
wird fuer bereits im State vorhandene Zeilen dieser Kanaele im jeweiligen
Anchor-Fenster interval_index auf den Sentinel-Wert POSTWAR_INTERVAL_INDEX
(-1) umgeschrieben - ein Wert, den echte Kalenderintervalle nie annehmen
(Post-Kriegs-Kanaele haben nur period >= 0, Baseline-Kanaele stoppen bei
Intervall-Index 3). Schon vorhandene Klassifikationen (politics_final etc.)
wandern mit und zaehlen sofort auf das neue Intervall-Ziel ein - nichts wird
verworfen oder muss neu eingereicht werden. interval_label kodiert
zusaetzlich die Kategorie (postwar_new_0_to_<N> / postwar_reactivated_0_to_<N>
/ postwar_delayed_0_to_<N>), damit spaetere Auswertungen (Schritt 6) bei
Bedarf Robustheitschecks mit/ohne die reaktivierten bzw. verzoegert
gestarteten Kanaele fahren koennen - siehe README.md fuer die vollstaendige
Label-Konvention. check_baseline_availability.py's Regex-Parsing dieser
Labels ist rueckwaertskompatibel zu den frueher geschriebenen
"postwar_0_to_<N>"-Zeilen ohne Kategorie-Suffix.

Kanaele mit zu wenigen Videos im Fenster werden automatisch erweitert
(3 -> 6 -> 9 -> 12 Monate), bis WINDOW_RAW_CANDIDATE_TARGET (30) rohe
Kandidatenzeilen erreicht sind oder das Maximalfenster ausgeschoepft ist.
Dieser Schwellenwert ist bewusst deutlich hoeher als TARGET_WITH_BUFFER_PER_INTERVAL
(12, das eigentliche Rundenplanungsziel fuer politische Videos): Zum Zeitpunkt
dieser Fensterwahl ist politics_final fuer die meisten Kandidaten noch nicht
klassifiziert, die Fensterwahl kann also nicht auf Basis der politischen Quote
entscheiden. Der groessere Rohpuffer soll stattdessen sicherstellen, dass auch
bei niedriger Politik-Trefferquote genug unklassifiziertes Rohmaterial im
Fenster liegt, aus dem die spaetere Rundenplanung (siehe
longitudinal/create_longitudinal_screening.py, POLITICAL_RATE_FLOOR /
ROUND_SAFETY_FACTOR) noch politische Kandidaten nachziehen kann. Die
Fensterlaenge selbst wird danach nicht mehr veraendert (bleibt bei
WINDOW_STEPS_MONTHS-Maximum gedeckelt) - Nutzerentscheidung: rohe Anzahl als
Kriterium beibehalten, aber mit groesserem Puffer (30 statt 12) fuer
unpolitische Videos.

Seit Phase 4d werden nur die tatsaechlich geaenderten Zeilen (die 4 betroffenen
Spalten interval_index/interval_label/target_political_per_interval/
target_with_buffer_per_interval, plus channel_id nur zur Erfuellung der
NOT-NULL-Spalte - screening_state_store.upsert_state_rows() prueft
NOT-NULL-Constraints beim INSERT-Versuch bereits VOR der Aufloesung des
video_id-PK-Konflikts, ein fehlendes channel_id im Record laesst den ganzen
Upsert-Batch mit sqlite3.IntegrityError fehlschlagen, obwohl inhaltlich nur
bestehende Zeilen upgedatet werden) per screening_state_store.upsert_state_rows()
geschrieben; das frueher hier erzeugte CSV-Vollkopie-Backup
(*.before_postwar_assignment.csv) entfaellt ersatzlos - SQLite braucht kein
manuelles Vollkopie-Backup-Muster.
"""

from __future__ import annotations

import pandas as pd

from youtube_code.step2_baseline_channels import activity_phases
from youtube_code.step2_baseline_channels.longitudinal.screening_config import (
    TARGET_POLITICAL_PER_INTERVAL,
    TARGET_WITH_BUFFER_PER_INTERVAL,
)
from youtube_code.store import screening_state_store, video_registry
from youtube_code.config import OUTPUTS

# ============================================================
# CONFIG
# ============================================================

summary_path = OUTPUTS / "segment_analysis" / "postwar_baseline_assignment_summary.csv"

MIN_SUBSCRIBERS = 50_000
WINDOW_STEPS_MONTHS = [3, 6, 9, 12]   # adaptiv erweitert, bis genug Kandidaten da sind

# Schwellenwert fuer die Fensterwahl-Schleife (siehe Modul-Docstring): bewusst
# hoeher als TARGET_WITH_BUFFER_PER_INTERVAL (12), da politics_final zum
# Zeitpunkt der Fensterwahl fuer die meisten Kandidaten noch fehlt und daher
# nur die rohe Zeilenzahl als Kriterium zur Verfuegung steht. 30 rohe
# Kandidatenzeilen als Puffer, damit auch bei niedriger Politik-Trefferquote
# noch genug Rohmaterial fuer die spaetere Rundenplanung uebrig bleibt.
WINDOW_RAW_CANDIDATE_TARGET = 50

POSTWAR_INTERVAL_INDEX = -1  # Sentinel, kollidiert nie mit echten Kalender-Intervallen

# Kategorien aus activity_phases, die hier ein individuelles Ersatzfenster
# bekommen, sowie das jeweilige interval_label-Praefix (siehe Modul-
# Docstring). "aktivitaet_deckt_kriegsbeginn" bekommt bewusst KEIN
# Ersatzfenster (globales Vorkriegsfenster reicht), "tot_zum_kriegsbeginn" /
# "nachkrieg_keine_aktivitaet" / "keine_videos_bekannt" werden ausgeschlossen
# (siehe Modul-Docstring).
LABEL_PREFIX_BY_KATEGORIE = {
    "nachkrieg_konsistent": "postwar_new",
    "reaktiviert_faelschlich_vorkrieg": "postwar_reactivated",
    "nachkrieg_verzoegerter_start": "postwar_delayed",
}

# Bewusst True als Default nach der Umstellung auf die Aktivitaetsphasen-
# Logik (siehe Modul-Docstring) - vor dem ersten echten Lauf mit dieser
# Logik erst die Vorschau pruefen (Kategorienverteilung, betroffene Zeilen),
# dann bewusst auf False setzen. Siehe README.md Abschnitt 3, Schritt 4 fuer
# das Backup-Vorgehen vor jedem schreibenden Schritt.
DRY_RUN = False


# ============================================================
# KANDIDATEN-KANAELE ERMITTELN
# ============================================================

def load_postwar_candidate_channels() -> pd.DataFrame:
    """Kanaele mit is_german=True und >= MIN_SUBSCRIBERS Abos, deren
    Aktivitaetsphasen (activity_phases.classify_channels_bulk) kein
    nutzbares globales Vorkriegsfenster ergeben (war_group ==
    "nachkriegskanal" - siehe LABEL_PREFIX_BY_KATEGORIE fuer die drei
    zugrunde liegenden Kategorien). Gibt channel_id, channel_title,
    kategorie, erstellt (= anchor_date aus activity_phases, der fuer die
    Fensterzuweisung zu verwendende Ankerpunkt) zurueck. Liest Kanal-
    Metadaten und Sprach-Klassifikation aus video_registry.sqlite
    (channels/language_classification)."""
    meta_df = video_registry.get_channels()
    meta_df["published_at"] = pd.to_datetime(
        meta_df["published_at"], format="ISO8601", utc=True
    ).dt.tz_localize(None)
    meta_df["subscribers"] = pd.to_numeric(meta_df["subscribers"], errors="coerce")

    class_df = video_registry.get_language_classification()[["channel_id", "is_german"]]

    merged = pd.merge(meta_df, class_df, on="channel_id", how="left")
    pool = merged[
        (merged["is_german"] == True) & (merged["subscribers"] >= MIN_SUBSCRIBERS)
    ][["channel_id", "title", "published_at"]].rename(
        columns={"title": "channel_title", "published_at": "channel_created_at"}
    ).reset_index(drop=True)

    uploads = video_registry.get_video_rows_for_channels(pool["channel_id"].tolist())
    uploads["published_at"] = pd.to_datetime(
        uploads["published_at"], errors="coerce", utc=True, format="ISO8601"
    ).dt.tz_localize(None)

    classified = activity_phases.classify_channels_bulk(pool, uploads)
    kandidaten = pool.merge(classified[["channel_id", "kategorie", "war_group", "anchor_date"]], on="channel_id")
    kandidaten = kandidaten.loc[kandidaten["war_group"] == "nachkriegskanal"]

    return kandidaten[["channel_id", "channel_title", "kategorie", "anchor_date"]].rename(
        columns={"anchor_date": "erstellt"}
    ).reset_index(drop=True)


# ============================================================
# STATE LADEN UND ZUWEISEN
# ============================================================

def assign_postwar_intervals(
    state: pd.DataFrame,
    kandidaten: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Gibt (aktualisierter State, Zusammenfassung pro Kanal) zurueck."""
    if kandidaten.empty:
        # Kein KeyError beim spaeteren set_index("channel_id") auf einer
        # spaltenlosen leeren summary_df - z.B. solange video_registry.channels
        # noch keine Post-Kriegs-Kandidaten mit Metadaten enthaelt.
        return state, pd.DataFrame(
            columns=["channel_id", "channel_title", "kategorie", "erstellt", "fenster_monate",
                     "n_kandidaten_im_fenster", "n_bereits_politisch"]
        )

    state = state.copy()
    # format="ISO8601" ist zwingend: screening_state.sqlite.published_at
    # enthaelt zwei unterschiedliche ISO8601-Schreibweisen ("...T...Z" und
    # "... +00:00", je nach Schreibpfad). Ohne explizites format leitet
    # pandas ein einziges Format aus der Spalte ab und wandelt jede Zeile,
    # die nicht dazu passt, mit errors="coerce" in NaT um - dadurch faellt
    # die betroffene Minderheit (rund 2 % der Zeilen) beim Fenster-Filter
    # unten immer raus, selbst wenn der Kanal korrekt als Kandidat
    # klassifiziert wurde (Bug gefunden 2026-09-03: liess unter anderem den
    # Kanal "Alexander Raue Klartext" komplett durchfallen).
    state["published_at_dt"] = pd.to_datetime(
        state["published_at"], errors="coerce", utc=True, format="ISO8601"
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
            if len(treffer) >= WINDOW_RAW_CANDIDATE_TARGET:
                break

        n_political_bereits = int(
            (gefundene_zeilen["politics_final"] == 1).sum()
        ) if not gefundene_zeilen.empty else 0

        zusammenfassung.append({
            "channel_id": cid,
            "channel_title": row["channel_title"],
            "kategorie": row["kategorie"],
            "erstellt": erstellt,
            "fenster_monate": gewaehltes_fenster_monate,
            "n_kandidaten_im_fenster": len(gefundene_zeilen),
            "n_bereits_politisch": n_political_bereits,
        })

        geaenderte_indices.extend(gefundene_zeilen.index.tolist())

    summary_df = pd.DataFrame(zusammenfassung)
    # interval_label kodiert die Kategorie (siehe LABEL_PREFIX_BY_KATEGORIE
    # und Modul-Docstring) mit, damit spaetere Auswertungen Robustheitschecks
    # mit/ohne reaktivierte bzw. verzoegert gestartete Kanaele fahren koennen.
    summary_df["interval_label"] = summary_df.apply(
        lambda r: f"{LABEL_PREFIX_BY_KATEGORIE[r['kategorie']]}_0_to_{int(r['fenster_monate'])}",
        axis=1,
    )

    state.loc[geaenderte_indices, "interval_index"] = POSTWAR_INTERVAL_INDEX
    state.loc[geaenderte_indices, "interval_label"] = state.loc[
        geaenderte_indices, "channel_id"
    ].map(summary_df.set_index("channel_id")["interval_label"])
    state.loc[geaenderte_indices, "target_political_per_interval"] = TARGET_POLITICAL_PER_INTERVAL
    state.loc[geaenderte_indices, "target_with_buffer_per_interval"] = TARGET_WITH_BUFFER_PER_INTERVAL

    state = state.drop(columns=["published_at_dt"])
    return state, summary_df


def main():
    print(f"Lade Kandidaten-Kanaele (deutsch, >= {MIN_SUBSCRIBERS:,} Abos, ohne nutzbares "
          f"globales Vorkriegsfenster laut Aktivitaetsphasen-Analyse)...")
    kandidaten = load_postwar_candidate_channels()
    print(f"{len(kandidaten)} Kandidaten-Kanaele.")
    print("Verteilung nach Kategorie (siehe activity_phases-Modul-Docstring):")
    print(kandidaten["kategorie"].value_counts().to_string())

    print("Lade State aus screening_state_store (inkl. per video_registry-Join "
          "nachgeladenem published_at, siehe get_state_with_text())...")
    state = screening_state_store.get_state_with_text()
    print(f"{len(state):,} Zeilen im State.")

    updated_state, summary = assign_postwar_intervals(state, kandidaten)

    print("\n" + "=" * 72)
    print("POST-WAR BASELINE ZUWEISUNG")
    print("=" * 72)
    print(f"Kanaele insgesamt: {len(summary)}")
    print(f"  ohne jeden Kandidaten im Fenster (auch nach Erweiterung auf 12 Monate): "
          f"{(summary['n_kandidaten_im_fenster'] == 0).sum()}")
    print(f"  mit >=1, aber < Rohpuffer-Ziel ({WINDOW_RAW_CANDIDATE_TARGET}) Kandidaten: "
          f"{((summary['n_kandidaten_im_fenster'] > 0) & (summary['n_kandidaten_im_fenster'] < WINDOW_RAW_CANDIDATE_TARGET)).sum()}")
    print(f"  mit ausreichend (>= {WINDOW_RAW_CANDIDATE_TARGET}) Kandidaten: "
          f"{(summary['n_kandidaten_im_fenster'] >= WINDOW_RAW_CANDIDATE_TARGET).sum()}")
    print(f"\nFensterlaenge-Verteilung (nur Kanaele mit >=1 Kandidat):")
    print(summary.loc[summary['n_kandidaten_im_fenster'] > 0, 'fenster_monate'].value_counts().sort_index().to_string())
    print(f"\nBereits politisch klassifizierte Videos, die sofort auf das neue Ziel einzahlen: "
          f"{summary['n_bereits_politisch'].sum()}")
    print(f"\nGeaenderte Zeilen im State: {(updated_state['interval_index'] == POSTWAR_INTERVAL_INDEX).sum()}")

    print("\nKanaele ohne jeden Kandidaten (brauchen zuerst Video-Nachdownload):")
    print(summary[summary['n_kandidaten_im_fenster'] == 0][['channel_id', 'channel_title', 'erstellt']].to_string(index=False))

    summary.to_csv(summary_path, index=False)
    print(f"\nZusammenfassung gespeichert: {summary_path}")

    if DRY_RUN:
        print("\nDRY RUN: State wurde NICHT geschrieben.")
        return

    changed = updated_state.loc[
        updated_state["interval_index"] == POSTWAR_INTERVAL_INDEX,
        [
            "video_id",
            "channel_id",
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

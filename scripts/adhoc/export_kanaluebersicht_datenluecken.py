# -*- coding: utf-8 -*-
"""
export_kanaluebersicht_datenluecken.py

Ad-hoc-Export der (Kanal, Periode)-Datenluecken, die beim Betrachten des
Kanaluebersicht-Marktanteil-Artifacts (`kanaluebersicht_marktanteil_bericht.py`,
Session vom 2026-09-10) auffielen (z.B. "tagesschau" nahe 0 Videos in der
Vorkriegsperiode, "WELT Nachrichtensender" nahe 0 in P1-P3, obwohl beide Kanaele
durchgehend prolifisch politisch berichten). Direkte Pruefung gegen
`video_registry.sqlite` (nicht gegen die abgeleitete channel_video_erfolg.csv)
ergab ZWEI unterschiedliche Ursachen fuer denselben Effekt in der Kanaluebersicht
(dort einheitlich sichtbar als niedrige "alle_videos"-Zaehlung):

  Kategorie 1 ("detail_fehlt"): Die Videos sind in der Registry BEKANNT
      (videos.published_at gesetzt), aber view_count und/oder
      video_details.topic_categories fehlen - die Detail-Metadaten-Abfrage
      (get_video_metadata(..., detailed=True) bzw. get_video_metadata() fuer
      view_count) ist fuer diese Videos nie gelaufen. Betrifft die
      auffaelligsten Faelle (tagesschau, WELT Nachrichtensender, euronews
      (deutsch), WDR aktuell, quer, OE24.TV).
  Kategorie 2 ("keine_videos"): video_registry.videos hat FUER DEN GESAMTEN
      Kanal x Periode-Ausschnitt keine einzige Zeile - nicht einmal die
      Basis-Video-ID-Liste wurde fuer dieses Zeitfenster gefuellt (Discovery-
      Luecke, vermutlich weil channel_all_videos.py fuer diesen Kanal nie
      rueckwirkend bis in dieses Fenster gelaufen ist).

Schreibt drei CSVs nach outputs/segment_analysis/datenluecken_kanaluebersicht/
(siehe PFAD_* unten) sowie eine zusammenfassende README.md im selben Ordner:

  - kategorie1_fehlende_stats.csv: video_id/channel_id/channel_title/
    published_at/periode fuer Videos OHNE view_count (Basis-Metadaten-Fetch
    fehlt komplett) - Grundlage fuer einen get_video_metadata(video_ids,
    youtube_client)-Nachzieh-Lauf (detailed=True, damit gleich auch
    topic_categories mitkommt).
  - kategorie1_fehlender_topic_nur.csv: video_id/... fuer Videos MIT
    view_count, aber OHNE video_details.topic_categories - hier reicht ein
    get_video_metadata(video_ids, youtube_client, detailed=True)-Lauf NUR
    fuer diese (kleinere) Teilmenge.
  - kategorie2_keine_videos.csv: channel_id/channel_title/periode/
    datum_von/datum_bis (keine video_id, da keine vorhanden) - Grundlage fuer
    einen rueckwirkenden channel_all_videos.py-Lauf genau fuer dieses Fenster.

Kanal-/Perioden-Liste ist bewusst als Konstante (KATEGORIE_1_ZELLEN/
KATEGORIE_2_ZELLEN unten) hart hinterlegt statt aus dem Artifact-JSON
nachgeladen - das Artifact ist eine Session-spezifische, nicht dauerhaft
verfuegbare Zwischenablage; die Kanal-Liste selbst stammt aus der manuellen
Diagnose derselben Session (siehe Chat-Verlauf fuer die vollstaendige
Herleitung ueber alle 260 Kanaele/7 Perioden).

Rel_monat-Grenzen (KRIEGSBEGINN, PERIOD_BOUNDS) 1:1 aus
step6_auswertung/prepare_channel_scores.py::relativ_periode() bzw.
frage4_kriegspraemie_medientyp_bericht.py::PHASEN uebernommen, NICHT
neu definiert.

Laeuft direkt als Skript (kein -m, keine Paket-relativen Importe):

    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        scripts/adhoc/export_kanaluebersicht_datenluecken.py
"""
import sqlite3

import pandas as pd

from youtube_code.config import OUTPUTS, STORE

DB_PATH = STORE / "video_registry.sqlite"
ERGEBNIS_ORDNER = OUTPUTS / "segment_analysis" / "datenluecken_kanaluebersicht"

PFAD_FEHLENDE_STATS = ERGEBNIS_ORDNER / "kategorie1_fehlende_stats.csv"
PFAD_FEHLENDER_TOPIC = ERGEBNIS_ORDNER / "kategorie1_fehlender_topic_nur.csv"
PFAD_KEINE_VIDEOS = ERGEBNIS_ORDNER / "kategorie2_keine_videos.csv"
PFAD_README = ERGEBNIS_ORDNER / "README.md"

# Kriegsbeginn-Anker und Phasengrenzen 1:1 aus prepare_channel_scores.py/
# frage4_kriegspraemie_medientyp_bericht.py (siehe Moduldocstring).
KRIEGSBEGINN = pd.Timestamp("2022-02-24")
PERIOD_BOUNDS = {
    "vorkrieg_fern": (-12, -7),
    "vorkrieg_nah": (-6, -1),
    "P1_schock_konsens": (0, 6),
    "P2_energiekrise_bruch": (7, 18),
    "P3_aufmerksamkeitsverdraengung": (19, 26),
    "P4_wahlkampfphase": (27, 36),
    "P5_nachwahlphase": (37, 48),
}

# Kategorie 1: Videos in der Registry bekannt, aber Detail-Metadaten
# (view_count und/oder topic_categories) fehlen fuer einen Grossteil.
KATEGORIE_1_ZELLEN = [
    ("UC5NOEUbkLheQcaaRldYW5GA", "tagesschau", "vorkrieg_fern"),
    ("UC5NOEUbkLheQcaaRldYW5GA", "tagesschau", "vorkrieg_nah"),
    ("UCZMsvbAhhRblVGXmEXW8TSA", "WELT Nachrichtensender", "P1_schock_konsens"),
    ("UCZMsvbAhhRblVGXmEXW8TSA", "WELT Nachrichtensender", "P2_energiekrise_bruch"),
    ("UCZMsvbAhhRblVGXmEXW8TSA", "WELT Nachrichtensender", "P3_aufmerksamkeitsverdraengung"),
    ("UCACdxU3VrJIJc7ujxtHWs1w", "euronews (deutsch)", "P1_schock_konsens"),
    ("UCsFtUYhrGmOck_UeVPD-AJQ", "WDR aktuell", "P3_aufmerksamkeitsverdraengung"),
    ("UCAeXKE-3J-6u68tO5Oafyag", "quer", "P3_aufmerksamkeitsverdraengung"),
    ("UCyQpfuhftLvrmjxgEzVH78Q", "OE24.TV", "P1_schock_konsens"),
]

# Kategorie 2: video_registry.videos hat fuer den gesamten Kanal x Periode-
# Ausschnitt keine einzige Zeile (Discovery-Luecke).
KATEGORIE_2_ZELLEN = [
    ("UC7n_Hml4hw5H4G-HP8QPeKw", ":newstime", "vorkrieg_fern"),
    ("UC7n_Hml4hw5H4G-HP8QPeKw", ":newstime", "vorkrieg_nah"),
    ("UCt8HsnMdQAuQUMDNNjSJdnw", "RTL Doku", "vorkrieg_fern"),
    ("UCt8HsnMdQAuQUMDNNjSJdnw", "RTL Doku", "vorkrieg_nah"),
    ("UCt8HsnMdQAuQUMDNNjSJdnw", "RTL Doku", "P1_schock_konsens"),
    ("UC8WYi3XQXsf-6FNvqoEvxag", "RTL Sport", "vorkrieg_fern"),
    ("UCWKEY-aEu7gcv5ayIpgrnvg", "ZDFunbubble", "vorkrieg_fern"),
    ("UCWKEY-aEu7gcv5ayIpgrnvg", "ZDFunbubble", "vorkrieg_nah"),
    ("UCAeXKE-3J-6u68tO5Oafyag", "quer", "vorkrieg_fern"),
    ("UCucMlG7a_4kewYrXhTK_PKg", "rbb24", "vorkrieg_fern"),
    ("UCdG3Qj5snC8LL26g0oZmXqw", "stern", "P5_nachwahlphase"),
]


def _datumsfenster(periode):
    """(datum_von, datum_bis_exklusiv) als 'YYYY-MM-DD', analog
    frage4_kriegspraemie_medientyp_bericht._phase_fenster() (inklusive
    Monatsgrenzen), aber in Kalenderdaten aufgeloest (rel_monat selbst ist
    nicht direkt in videos.published_at abfragbar)."""
    monat_min, monat_max = PERIOD_BOUNDS[periode]
    von = KRIEGSBEGINN + pd.DateOffset(months=monat_min)
    bis = KRIEGSBEGINN + pd.DateOffset(months=monat_max + 1)
    return von.strftime("%Y-%m-%d"), bis.strftime("%Y-%m-%d")


def _lade_kategorie1(con):
    fehlende_stats, fehlender_topic = [], []
    for channel_id, channel_name, periode in KATEGORIE_1_ZELLEN:
        von, bis = _datumsfenster(periode)
        rows = pd.read_sql_query(
            "SELECT v.video_id, v.published_at, v.view_count, d.topic_categories "
            "FROM videos v LEFT JOIN video_details d ON v.video_id = d.video_id "
            "WHERE v.channel_id = ? AND v.published_at >= ? AND v.published_at < ?",
            con, params=(channel_id, von, bis),
        )
        rows["channel_id"] = channel_id
        rows["channel_title"] = channel_name
        rows["periode"] = periode

        ohne_stats = rows[rows["view_count"].isna()]
        fehlende_stats.append(
            ohne_stats[["video_id", "channel_id", "channel_title", "published_at", "periode"]]
        )

        nur_topic = rows[rows["view_count"].notna() & rows["topic_categories"].isna()]
        fehlender_topic.append(
            nur_topic[["video_id", "channel_id", "channel_title", "published_at", "periode"]]
        )

    return (
        pd.concat(fehlende_stats, ignore_index=True) if fehlende_stats else pd.DataFrame(),
        pd.concat(fehlender_topic, ignore_index=True) if fehlender_topic else pd.DataFrame(),
    )


def _lade_kategorie2():
    zeilen = []
    for channel_id, channel_name, periode in KATEGORIE_2_ZELLEN:
        von, bis = _datumsfenster(periode)
        zeilen.append({
            "channel_id": channel_id, "channel_title": channel_name, "periode": periode,
            "datum_von": von, "datum_bis_exklusiv": bis,
        })
    return pd.DataFrame(zeilen)


def _schreibe_readme(fehlende_stats, fehlender_topic, keine_videos):
    zeilen = [
        "# Datenluecken Kanaluebersicht-Marktanteil (Export)",
        "",
        "Export vom Chat-Verlauf am 2026-09-10 (Diagnose der auffaelligen Kanal x Periode-"
        "Zellen aus `kanaluebersicht_marktanteil_bericht.csv`, siehe "
        "`scripts/adhoc/export_kanaluebersicht_datenluecken.py` fuer die vollstaendige "
        "Herleitung und Kategorie-Definition).",
        "",
        f"- `kategorie1_fehlende_stats.csv` ({len(fehlende_stats)} Videos): view_count fehlt "
        "komplett - Basis-Metadaten-Fetch nie gelaufen. Nachziehen per "
        "`get_video_metadata(video_ids, youtube_client, detailed=True)` "
        "(`src/youtube_code/utils/io.py`) - detailed=True gleich mit, damit "
        "topic_categories nicht in einem zweiten Lauf separat nachgezogen werden muss.",
        f"- `kategorie1_fehlender_topic_nur.csv` ({len(fehlender_topic)} Videos): view_count "
        "vorhanden, aber KEINE video_details-Zeile (topic_categories fehlt) - reicht ein "
        "`get_video_metadata(..., detailed=True)`-Lauf NUR fuer diese (kleinere) Teilmenge "
        "(known_video_detail_ids()-Filter greift automatisch, da view_count bereits bekannt "
        "ist).",
        f"- `kategorie2_keine_videos.csv` ({len(keine_videos)} Kanal x Periode-Zellen): "
        "video_registry hat fuer den gesamten Zeitraum keine einzige Video-Zeile - kein "
        "video_id-Export moeglich, stattdessen Kanal + Datumsfenster fuer einen "
        "rueckwirkenden `channel_all_videos.py`-Lauf.",
        "",
        "Nach jedem Nachzieh-Lauf empfiehlt sich ein erneuter Durchlauf von "
        "`prepare_success_metrics.py` und `kanaluebersicht_marktanteil_bericht.py`, um zu "
        "pruefen, ob die betroffenen Zellen jetzt die Mindestbesetzung "
        "(`MIN_VIDEOS_GESAMT_PRO_PHASE`) erreichen.",
        "",
    ]
    PFAD_README.write_text("\n".join(zeilen), encoding="utf-8")


def main():
    ERGEBNIS_ORDNER.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        fehlende_stats, fehlender_topic = _lade_kategorie1(con)
    finally:
        con.close()
    keine_videos = _lade_kategorie2()

    fehlende_stats.to_csv(PFAD_FEHLENDE_STATS, index=False, encoding="utf-8")
    fehlender_topic.to_csv(PFAD_FEHLENDER_TOPIC, index=False, encoding="utf-8")
    keine_videos.to_csv(PFAD_KEINE_VIDEOS, index=False, encoding="utf-8")
    _schreibe_readme(fehlende_stats, fehlender_topic, keine_videos)

    print(f"[Kategorie 1a] {len(fehlende_stats)} Videos ohne view_count -> {PFAD_FEHLENDE_STATS}")
    print(f"[Kategorie 1b] {len(fehlender_topic)} Videos ohne topic_categories (view_count "
          f"vorhanden) -> {PFAD_FEHLENDER_TOPIC}")
    print(f"[Kategorie 2] {len(keine_videos)} Kanal x Periode-Zellen ohne jedes Video -> "
          f"{PFAD_KEINE_VIDEOS}")
    print(f"[README] {PFAD_README}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
select_political_nonwar_targets.py

Zielauswahl-Vorbereitung fuer einen Gegentest zu populismuspraemie_kriegsvideos_bericht.py
(Schritt 9 in diesem Ordner): jenes Skript prueft, ob populistischere Kriegsvideos
innerhalb eines Kanals mehr Views erzielen als weniger populistische Kriegsvideos
DESSELBEN Kanals. Um zu pruefen, ob dieselbe Populismus-Views-Beziehung ("Praemie")
bei politischen NICHT-Kriegsvideos genauso hoch ausfaellt, braucht es zuerst fuer
eine ausreichende Zahl politischer Nicht-Kriegsvideos je Kanal-Monat ein Transkript
und eine Populismus-Klassifikation (Schritt 5) - dieses Skript deckt NUR den
ERSTEN Teilschritt ab: die Zielauswahl fuer den Transkript-Download. Weder die
Klassifikation noch der eigentliche Praemie-Vergleichsbericht sind Teil dieses
Skripts.

Wiederverwendet select_cell_fill_targets() aus
step4_transcript_download/select_targets.py (Konfiguration 2, Pool "politisch
klassifizierte Nicht-Kriegsvideos") mit include_war=False - identische
Cell-Fill-/Prioritaets-Logik wie beim bestehenden Kriegsvideo-Sample (Videos mit
bereits vorhandenem Transkript werden je Kanal-Periode-Zelle bevorzugt und
"verbrauchen" damit bevorzugt eine der VIDEOS_PER_CELL Quote-Stellen), nur ohne
den (hier ungebrauchten) Kriegsvideo-Pool. "Politisch" bedeutet wie dort
politics_final == 1 aus screening_state_store (longitudinales Politik-Screening,
Schritt 2) - NICHT jedes inhaltlich politische Video, sondern nur die (zufaellig
gezogene) Teilmenge, die im Screening tatsaechlich bewertet wurde (Limitation:
siehe frage4_kriegspraemie_relative_views_plots.py-Docstring, dort nur ca. 12%
Abdeckung der Videos in channel_video_erfolg.csv).

Kanalauswahl: dieselbe frage1_kanal_whitelist.csv wie ueberall sonst in diesem
Ordner (siehe prepare_success_metrics.py::_lade_whitelist()) - der spaetere
Praemie-Vergleich soll auf genau denselben Kanaelen laufen wie
populismuspraemie_kriegsvideos_bericht.py (dessen channel_video_erfolg.csv
bereits auf diese Whitelist beschraenkt ist).

Ergebnis von select_cell_fill_targets() ist bereits gegen
transcript_store.attempted_video_ids() gefiltert (siehe dortiger
Moduldocstring) - enthaelt also NUR Videos, fuer die noch KEIN
Transkript-Download-Versuch vorliegt (Videos mit bereits vorhandenem Transkript
wurden zwar bevorzugt in die Kanal-Monats-Auswahl aufgenommen, tauchen aber
NICHT in dieser Liste auf, weil fuer sie kein neuer Download noetig ist). Das ist
direkt die Liste, die an download_transcripts()/run_transcript_selection.py
(MODE="cell_fill", TOPIC/GRANULARITY/CHANNEL_IDS entsprechend gesetzt,
VIDEOS_PER_CELL=VIDEOS_PER_CELL und include_war=False dort ergaenzen) uebergeben
werden kann. Dieses Skript startet selbst KEINEN Download (bewusst getrennt vom
eigentlichen Scraping-Schritt, siehe .claude/CLAUDE.md "Testlaeufe" - Downloads
brauchen vorherige Rueckfrage).

Schreibt political_nonwar_download_ids.csv (video_id, channel_id) nach
outputs/segment_analysis/.

Als -m-Modul ausfuehren (echter Paketimport von select_cell_fill_targets aus
step4_transcript_download, andere Verzeichnisebene als dieses Skript - Muster
wie scripts/adhoc/video_sample_uebersicht.py fuer lade_medientyp()):

    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        -m youtube_code.step6_auswertung.select_political_nonwar_targets
"""
import pandas as pd

from youtube_code.config import OUTPUTS
from youtube_code.step4_transcript_download.select_targets import select_cell_fill_targets

RESULTS_PATH = OUTPUTS / "segment_analysis"
PFAD_WHITELIST = RESULTS_PATH / "frage1_kanal_whitelist.csv"
PFAD_AUSGABE = RESULTS_PATH / "political_nonwar_download_ids.csv"

VIDEOS_PER_CELL = 3
GRANULARITY = "monat"
TOPIC = "russia_ukraine_war"


def _lade_whitelist():
    """Siehe prepare_success_metrics.py::_lade_whitelist() - dieselbe Whitelist."""
    whitelist = pd.read_csv(PFAD_WHITELIST)
    whitelist["channel_id"] = whitelist["channel_id"].astype(str)
    return whitelist["channel_id"].tolist()


def main():
    channel_ids = _lade_whitelist()
    print(f"[Whitelist] {len(channel_ids)} Kanal-IDs aus {PFAD_WHITELIST}.")

    targets = select_cell_fill_targets(
        channel_ids, videos_per_cell=VIDEOS_PER_CELL, topic=TOPIC,
        granularity=GRANULARITY, include_war=False,
    )
    n_kanaele = targets["channel_id"].nunique() if not targets.empty else 0
    print(f"[Auswahl] {len(targets)} politische Nicht-Kriegsvideos ohne bestehenden "
          f"Transkript-Versuch (bis zu {VIDEOS_PER_CELL} je Kanal-{GRANULARITY}-Zelle; "
          f"Videos mit bereits vorhandenem Transkript wurden bevorzugt in die Auswahl "
          f"aufgenommen und sind deshalb NICHT in dieser Liste, siehe Moduldocstring), "
          f"{n_kanaele} Kanaele betroffen.")

    targets.to_csv(PFAD_AUSGABE, index=False, encoding="utf-8")
    print(f"[Ausgabe] -> {PFAD_AUSGABE}")


if __name__ == "__main__":
    main()

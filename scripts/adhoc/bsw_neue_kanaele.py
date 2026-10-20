"""Schritt 2 der BSW-Sample-Erweiterung (.claude/plans/bsw_sample_erweiterung.md):
neue Kanaele aus den BSW-Suchlaeufen bestimmen, Kanal-Metadaten und
Sprachklassifikation nachholen und die Liste fuer den Video-Download schreiben.

Reihenfolge (billig vor teuer):
  1. Kanal-Metadaten (channels.list, 1 Einheit je 50 Kanaele) fuer alle
     BSW-Trefferkanaele ohne Eintrag in der Tabelle channels.
  2. Filter subscribers > MIN_SUBSCRIBERS (wie build_channel_provenance.py).
  3. Sprachklassifikation (is_german_channel aus step1_sample/channel_all_videos.py,
     ca. 3 Einheiten je Kanal) nur fuer diese Kanaele, sofern noch nicht
     klassifiziert.
  4. Ausgabe: deutsche >50k-Kanaele, die noch nicht im bisherigen Sample
     (eligible_current_analysis im Backup der Provenienz vom 14.10.2026) sind,
     nach data/channel_lists/bsw_neue_kanaele.csv - Spalten channel_id, title,
     subscribers, video_count, nur_bsw (nicht ueber andere Parteisuchen gefunden).

Der Modus NEW_CHANNELS von channel_all_videos.py passt hier nicht: Er
ueberspringt Kanaele, die schon Videos in der Registry haben - das trifft auf
alle Suchtrefferkanaele zu.

Ausfuehren aus dem Repo-Root:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/adhoc/bsw_neue_kanaele.py
"""

import sys

import pandas as pd

from youtube_code.config import CHANNEL_LISTS, ROOT, SRC
from youtube_code.store import video_registry
from youtube_code.utils import get_channel_metadata

sys.path.insert(0, str(SRC / "step1_sample"))
import channel_all_videos as cav  # noqa: E402  (bare sibling import, siehe dortiger Docstring)

MIN_SUBSCRIBERS = 50_000
QUERY = "BSW"
ALTES_SAMPLE = ROOT / "_backups" / "vor_bsw_2026-10-14" / "russia_longitudinal_v1" / "channel_sample_provenance.csv"
AUSGABE = CHANNEL_LISTS / "bsw_neue_kanaele.csv"


def kanaele_nach_query():
    prov = video_registry.get_search_provenance().dropna(subset=["channel_id"])
    bsw = set(prov.loc[prov["query"] == QUERY, "channel_id"])
    andere = set(prov.loc[prov["query"] != QUERY, "channel_id"])
    return bsw, andere


def main():
    bsw, andere = kanaele_nach_query()
    print(f"BSW-Trefferkanaele: {len(bsw)} (davon nur ueber BSW: {len(bsw - andere)})")

    get_channel_metadata(sorted(bsw), cav.YOUTUBE)

    ch = video_registry.get_channels(sorted(bsw))
    gross = ch[ch["subscribers"] > MIN_SUBSCRIBERS]
    print(f"Mit Kanal-Metadaten: {len(ch)}, davon > {MIN_SUBSCRIBERS:,} Abonnenten: {len(gross)}")

    lang = video_registry.get_language_classification(gross["channel_id"].tolist())
    offen = sorted(set(gross["channel_id"]) - set(lang["channel_id"]))
    print(f"Sprachklassifikation offen: {len(offen)}")
    cav.classify_new_channels(offen)

    lang = video_registry.get_language_classification(gross["channel_id"].tolist())
    deutsch = set(lang.loc[lang["is_german"].astype(bool), "channel_id"])
    alt = pd.read_csv(ALTES_SAMPLE, usecols=["channel_id", "eligible_current_analysis"])
    alt_eligible = set(alt.loc[alt["eligible_current_analysis"] == True, "channel_id"])

    neu = gross[gross["channel_id"].isin(deutsch) & ~gross["channel_id"].isin(alt_eligible)].copy()
    neu["nur_bsw"] = (~neu["channel_id"].isin(andere)).astype(int)
    neu = neu[["channel_id", "title", "subscribers", "video_count", "nur_bsw"]].sort_values("subscribers", ascending=False)
    neu.to_csv(AUSGABE, index=False, encoding="utf-8")
    print(f"Deutsch & > 50k: {len(deutsch)}, davon schon im alten Sample: {len(deutsch & alt_eligible)}")
    print(f"Neue Kanaele: {len(neu)} (nur_bsw: {int(neu['nur_bsw'].sum())}) -> {AUSGABE}")
    print(neu.to_string(index=False))


if __name__ == "__main__":
    main()

"""Ad-hoc: Zufaellige long-Video-IDs je Kanal-Woche fuer den Transkript-Download.

Zieht fuer jeden Kanal des Samples (channels_check.xlsx, Filter siehe
Konfiguration) im Zeitraum START..ENDE je Woche hoechstens MAX_PRO_WOCHE
zufaellige long-Videos. Gedacht fuer die Erweiterung der Angebotsstudie auf
Juni-Oktober 2022 (.claude/plans/angebotsstudie_zeitraum_2023.md).

Wochen: 7-Tage-Bloecke, verankert am Kriegsbeginn (Do, 24.02.2022) wie in
data/claude_classification/ziehung_angebotsstudie.py. START muss ein
Wochenbeginn (Donnerstag) und ENDE ein Wochenende (Mittwoch) sein, damit nur
volle Wochen gezogen werden.

Ziehung: Jedes Video bekommt einen festen Zufallsschluessel aus SEED und
video_id (BLAKE2b-Hash). Mit TAGE_REIHUM = True wird je Kanal-Woche reihum nach
Tagen gezogen (erst je ein Video pro Tag, dann ein zweites usw.; Tage mit
weniger Videos geben ihre Plaetze ab), bei MAX_PRO_WOCHE = 14 also moeglichst
2 Videos pro Tag. Mit False einfach die MAX_PRO_WOCHE Videos mit den kleinsten
Schluesseln. Kanal-Wochen mit hoechstens MAX_PRO_WOCHE Videos gehen
vollstaendig ein.

Formate: Es zaehlen nur Videos mit format == "long" (video_format in der
Registry). Videos ohne Format fallen heraus und werden je Kanal gemeldet.
Die betroffenen Kanaele landen in FEHLENDE_FORMATE_OUTPUT (Spalten wie von
step1_sample/channel_video_formats.py erwartet, Fenster in fenster_von/_bis).
Workflow bei fehlenden Formaten (Stand 28.10.2026: WELT Nachrichtensender,
3.569 von 3.925 Videos im Zeitraum ohne Format):
  1. dieses Skript ausfuehren -> Kanalliste wird geschrieben
  2. channel_video_formats.py mit CHANNEL_INPUT = diese Liste und
     PUBLISHED_AFTER = PUBLISHED_BEFORE = None ausfuehren
  3. dieses Skript erneut ausfuehren (gleicher SEED)
WELT liess sich so nicht nachscrapen (yt-dlp /videos endet zu frueh); die
4.175 formatlosen WELT-Videos 2022-01-01 bis 2022-10-26 stehen seit 04.11.2026
per Ausschluss als long im Store (scripts/adhoc/welt_format_ausschluss_long.py,
source = "ausschluss_long") und werden damit mitgezogen.

Bereits vorhandene Transkripte werden nicht herausgefiltert; download_transcripts()
ueberspringt im transcript_store schon versuchte IDs selbst.

Outputs (Ordner scripts/adhoc/outputs/):
  <OUTPUT_NAME>.json  Liste {video_id, channel_id} -> VIDEO_LIST in
                      step4_transcript_download/download_transcripts.py
  <OUTPUT_NAME>.csv   dieselben Videos mit Kanal, Datum, Woche, Rang
"""

import hashlib
import json
import sys

import pandas as pd

from youtube_code.config import CHANNEL_LISTS, ROOT, STATA_OUTPUT
from youtube_code.store.video_registry import get_video_formats, get_video_rows_for_channels

# ============================================================================
# KONFIGURATION
# ============================================================================

CHANNEL_FILE = STATA_OUTPUT / "channels_check.xlsx"   # Kanalliste mit channel_id, channel_title,
                                                      # media_category, sample, foreign
MEDIA_CATEGORIES = [1, 2, 5]           # Werte aus media_category, die ins Sample kommen
SAMPLES = [1, 2, 3, 4, 5]              # Werte aus sample, die ins Sample kommen
OHNE_AUSLAND = True                    # True = Kanaele mit foreign == 1 ausschliessen

START = "2022-01-06"                   # erster Tag (inkl.), muss ein Wochenbeginn sein (s. WOCHEN_ANKER)
ENDE = "2023-01-04"                    # letzter Tag (inkl.), muss ein Wochenende sein
WOCHEN_ANKER = "2022-02-24"            # Beginn einer Woche (Kriegsbeginn, Do), wie in ziehung_angebotsstudie.py
ZEITZONE = "Europe/Berlin"             # Datum der Videos in Ortszeit

MAX_PRO_WOCHE = 14                     # Videos je Kanal-Woche (ganze Zahl >= 1)
TAGE_REIHUM = True                     # True = reihum nach Tagen (moeglichst gleich viele je Tag),
                                       # False = rein zufaellig innerhalb der Woche
SEED = "angebot-2022h2-v1"             # beliebiger String; fuer Reproduzierbarkeit nicht aendern

OUTPUT_DIR = ROOT / "scripts" / "adhoc" / "outputs"
OUTPUT_NAME = "video_ids_angebot_2022-06-02_2022-11-02"   # Dateiname ohne Endung
FEHLENDE_FORMATE_OUTPUT = CHANNEL_LISTS / "video_formats" / "angebot_2022h2_fehlende_formate.csv"


# ============================================================================
# FUNKTIONEN
# ============================================================================

def zufallsschluessel(wert: str, salt: str) -> int:
    return int(hashlib.blake2b(f"{SEED}::{salt}::{wert}".encode("utf-8"),
                               digest_size=8).hexdigest(), 16)


def lade_kanaele() -> pd.DataFrame:
    k = pd.read_excel(CHANNEL_FILE)
    k = k[k["media_category"].isin(MEDIA_CATEGORIES) & k["sample"].isin(SAMPLES)]
    if OHNE_AUSLAND:
        k = k[k["foreign"] != 1]
    return k[["channel_id", "channel_title", "media_category"]].drop_duplicates("channel_id")


def lade_videos(kanaele: pd.DataFrame, start: pd.Timestamp, ende: pd.Timestamp) -> pd.DataFrame:
    v = get_video_rows_for_channels(kanaele["channel_id"].tolist())
    v["datum"] = (pd.to_datetime(v["published_at"], utc=True, format="mixed")
                  .dt.tz_convert(ZEITZONE).dt.tz_localize(None).dt.normalize())
    v = v[(v["datum"] >= start) & (v["datum"] <= ende)]
    formate = get_video_formats(kanaele["channel_id"].tolist())[["video_id", "format"]]
    v = v.merge(formate, on="video_id", how="left")
    return v.merge(kanaele, on="channel_id")


def melde_fehlende_formate(v: pd.DataFrame) -> None:
    je_kanal = (v.groupby(["channel_id", "channel_title"])
                .agg(n_videos_zeitraum=("video_id", "size"),
                     n_ohne_format=("format", lambda s: int(s.isna().sum())))
                .reset_index())
    fehlend = je_kanal[je_kanal["n_ohne_format"] > 0].sort_values("n_ohne_format", ascending=False)
    if fehlend.empty:
        print("[Formate] Alle Videos im Zeitraum haben ein Format.")
        return
    print(f"[Formate] {int(fehlend['n_ohne_format'].sum()):,} Videos ohne Format "
          f"(fallen heraus), {len(fehlend)} Kanaele:")
    print(fehlend[["channel_title", "n_videos_zeitraum", "n_ohne_format"]].to_string(index=False))
    liste = fehlend.rename(columns={"channel_title": "kanalname"}).assign(
        fenster_von=f"{START}T00:00:00Z", fenster_bis=f"{ENDE}T23:59:59Z")
    FEHLENDE_FORMATE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    liste.to_csv(FEHLENDE_FORMATE_OUTPUT, index=False, encoding="utf-8")
    print(f"[Formate] Kanalliste fuer channel_video_formats.py: {FEHLENDE_FORMATE_OUTPUT}")


def ziehe(v: pd.DataFrame) -> pd.DataFrame:
    v = v.copy()
    v["woche"] = (v["datum"] - pd.Timestamp(WOCHEN_ANKER)).dt.days // 7   # 0 = erste Kriegswoche
    v["_h"] = v["video_id"].map(lambda x: zufallsschluessel(x, "video"))
    if TAGE_REIHUM:
        v["rang_tag"] = v.groupby(["channel_id", "datum"])["_h"].rank(method="first").astype(int)
        v["_h_tag"] = (v["channel_id"] + "|" + v["datum"].dt.strftime("%Y-%m-%d")).map(
            lambda x: zufallsschluessel(x, "tag"))
        v = v.sort_values(["channel_id", "woche", "rang_tag", "_h_tag", "_h"])
    else:
        v = v.sort_values(["channel_id", "woche", "_h"])
    v["rang_woche"] = v.groupby(["channel_id", "woche"]).cumcount() + 1
    v["n_woche"] = v.groupby(["channel_id", "woche"])["video_id"].transform("size")
    return v[v["rang_woche"] <= MAX_PRO_WOCHE].drop(columns=[c for c in ("_h", "_h_tag") if c in v])


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    try:
        start, ende, anker = pd.Timestamp(START), pd.Timestamp(ENDE), pd.Timestamp(WOCHEN_ANKER)
    except ValueError as e:
        sys.exit(f"START/ENDE/WOCHEN_ANKER muessen Datumsangaben 'JJJJ-MM-TT' sein: {e}")
    if ende < start:
        sys.exit("ENDE liegt vor START.")
    if (start - anker).days % 7 != 0:
        sys.exit(f"START {START} ist kein Wochenbeginn (Wochen beginnen am {anker:%A}, Anker {WOCHEN_ANKER}).")
    if (ende - anker).days % 7 != 6:
        sys.exit(f"ENDE {ENDE} ist kein Wochenende (Wochen enden am {anker - pd.Timedelta(days=1):%A}).")
    if not isinstance(MAX_PRO_WOCHE, int) or MAX_PRO_WOCHE < 1:
        sys.exit("MAX_PRO_WOCHE muss eine ganze Zahl >= 1 sein.")
    if not isinstance(TAGE_REIHUM, bool) or not isinstance(OHNE_AUSLAND, bool):
        sys.exit("TAGE_REIHUM und OHNE_AUSLAND muessen True oder False sein.")
    if not CHANNEL_FILE.exists():
        sys.exit(f"Kanalliste fehlt: {CHANNEL_FILE}")

    kanaele = lade_kanaele()
    v = lade_videos(kanaele, start, ende)
    print(f"[Daten] {len(kanaele)} Kanaele, {(ende - start).days // 7 + 1} Wochen ({START} bis {ENDE}), "
          f"{len(v):,} Videos im Zeitraum")
    print("[Daten] Formate:", v["format"].fillna("(fehlt)").value_counts().to_dict())
    melde_fehlende_formate(v)

    gezogen = ziehe(v[v["format"] == "long"])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    spalten = ["channel_id", "channel_title", "media_category", "video_id", "published_at",
               "datum", "woche", "rang_woche", "n_woche"]
    gezogen[spalten].to_csv(OUTPUT_DIR / f"{OUTPUT_NAME}.csv", index=False, encoding="utf-8-sig")
    with open(OUTPUT_DIR / f"{OUTPUT_NAME}.json", "w", encoding="utf-8") as fh:
        json.dump(gezogen[["video_id", "channel_id"]].to_dict("records"), fh, indent=1)

    kw = gezogen.groupby(["channel_id", "woche"])["n_woche"].first()
    print(f"\n[Ziehung] {len(gezogen):,} Videos aus {gezogen['channel_id'].nunique()} Kanaelen, "
          f"max {MAX_PRO_WOCHE}/Kanal-Woche; gekuerzte Kanal-Wochen: {int((kw > MAX_PRO_WOCHE).sum())} "
          f"von {len(kw)}")
    print("[Ziehung] Videos je media_category:", gezogen.groupby("media_category").size().to_dict())
    print(f"[Output] {OUTPUT_DIR / (OUTPUT_NAME + '.json')}\n[Output] {OUTPUT_DIR / (OUTPUT_NAME + '.csv')}")


if __name__ == "__main__":
    main()

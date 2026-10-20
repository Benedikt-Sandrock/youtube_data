"""Ad-hoc-Export: Zufallsstichprobe von Videos je Kanal und Zeitperiode.

Zieht fuer jeden angegebenen Kanal innerhalb eines Zeitraums je Periode
(Tag/Woche/Monat/Quartal/Jahr oder gesamter Zeitraum) N zufaellige Videos und
schreibt sie als CSV raus - z.B. um Beispielvideos fuer eine qualitative
Sichtung oder fuer manuelle Codierung zu ziehen.

Kanaele koennen als Channel-IDs (UC...), als Handle (@name) oder als
Kanalname angegeben werden (Abgleich case-insensitiv und exakt gegen
channels.title, channels.handle und videos.channel_title). Mehrdeutige oder
unbekannte Namen werden gemeldet und uebersprungen.

Datenquelle: data/store/video_registry.sqlite (Tabellen videos,
video_details, channels, ggf. video_format) - nicht der Stata-Rohdatensatz,
da dieser keine Videobeschreibungen enthaelt. Views sind der einmalige
Snapshot aus videos.view_count (siehe Docstring von video_registry.py).

Hat ein Kanal in einer Periode weniger als N Videos, werden alle Videos
dieser Periode genommen (und am Ende gezaehlt). Perioden ganz ohne Video
tauchen nicht auf. Mit SEED ist die Ziehung reproduzierbar.

Ziehungsverfahren: Jedes Video bekommt einen festen Zufallsschluessel, der nur
aus SEED und video_id berechnet wird (BLAKE2b-Hash). Je Kanal x Periode werden
die N Videos mit den kleinsten Schluesseln genommen. Dadurch haengt die
Auswahl eines Kanals nicht davon ab, welche anderen Kanaele im Sample sind
oder in welcher Reihenfolge die Daten geladen werden; neu hinzugekommene
Videos verdraengen hoechstens einzelne Videos (wenn ihr Schluessel kleiner
ist). Hinweis: Stichproben aus der frueheren Version (gemeinsames Mischen
aller Kanaele per DataFrame.sample) sind damit nicht reproduzierbar.

Nutzung: Parameter im Konfigurationsblock unten anpassen, dann das Skript
ausfuehren (src muss im PYTHONPATH liegen, in PyCharm automatisch).

Output (Default): scripts/adhoc/outputs/zufallsstichprobe_videos_<Zeitstempel>.csv
Spalten: channel_id, kanalname, video_id, video_titel, video_beschreibung,
views, published_at, periode

Fehlende Formate: Videos ohne Eintrag in video_format fallen bei VIDEO_FORMAT
heraus. Deshalb schreibt das Skript zusaetzlich die Kanalliste
FEHLENDE_FORMATE_OUTPUT (Default:
data/channel_lists/video_formats/zufallsstichprobe_fehlende_formate.csv) mit
allen Kanaelen, die im Zeitraum Videos ohne Format haben, inkl. Zeitfenster.
Workflow bei einem neuen Sample:
  1. dieses Skript ausfuehren -> Kanalliste wird (neu) geschrieben
  2. step1_sample/channel_video_formats.py mit
     CHANNEL_INPUT = CHANNEL_LISTS / "video_formats" / "zufallsstichprobe_fehlende_formate.csv"
     und PUBLISHED_AFTER = PUBLISHED_BEFORE = None ausfuehren (Fenster kommt
     aus der Liste; kostet API-Quota)
  3. dieses Skript erneut ausfuehren (gleicher SEED) -> Stichprobe mit
     vollstaendigen Formaten. Videos, die danach immer noch ohne Format sind,
     sind meist geloescht/privat und bei YouTube nicht mehr abrufbar.
"""

import hashlib
import random
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from youtube_code.config import CHANNEL_LISTS, ROOT, STATA_OUTPUT
from youtube_code.store import video_registry

# ============================================================================
# KONFIGURATION
# ============================================================================

# Kanaele als Channel-ID (UC...), @Handle oder Kanalname
cats = [1,2,5]
df = pd.read_stata(STATA_OUTPUT / "views_aug21-jan22.dta")

df_top10 = (df.sort_values(by=["media_category", "views"], ascending = [True, False])
            .groupby("media_category").head(10))

df_top10 = df_top10[df_top10["media_category"].isin(cats)]

df_top10.to_csv("top10.csv", index = False)

KANAELE = df_top10["channel_id"].tolist() + ["UCSiFC1DCXr3p1YDzyu9rogA"]

print(len(KANAELE))
# Optional zusaetzlich/alternativ: Textdatei (eine Zeile je Kanal) oder CSV mit
# Spalte channel_id bzw. kanalname. None = nicht verwenden.
KANAELE_DATEI = None

START = "2022-01-01"  # inklusive
ENDE = "2022-04-30"   # inklusive

# "tag", "woche", "monat", "quartal", "jahr" oder "gesamt"
FREQUENZ = "woche"

# Anzahl zufaellig gezogener Videos je Kanal und Periode
N = 50

# Nur dieses Videoformat ("long", "short", "live"); None = alle Formate.
# "long" schliesst Shorts und Livestreams aus.
VIDEO_FORMAT = "long"

# Zufalls-Seed fuer reproduzierbare Ziehung (int oder str); None = jedes Mal neu
# (der dann zufaellig gewaehlte Seed wird ausgegeben)
SEED = 42

# Ausgabe-CSV; None = scripts/adhoc/outputs/zufallsstichprobe_videos_<Zeitstempel>.csv
OUTPUT = None

# Kanalliste fuer step1_sample/channel_video_formats.py: alle Kanaele, die im
# Zeitraum Videos ohne Format-Zuordnung haben (Spalten channel_id, kanalname,
# n_videos_zeitraum, n_ohne_format, fenster_von, fenster_bis). Wird bei jedem
# Lauf ueberschrieben (bei vollstaendigen Formaten nur mit Kopfzeile).
# None = nicht schreiben.
FEHLENDE_FORMATE_OUTPUT = CHANNEL_LISTS / "video_formats" / "zufallsstichprobe_fehlende_formate.csv"

# ============================================================================

OUT_DIR = ROOT / "scripts" / "adhoc" / "outputs"

FREQUENZEN = {
    "tag": "D",
    "woche": "W",
    "monat": "M",
    "quartal": "Q",
    "jahr": "Y",
    "gesamt": None,
}

CHANNEL_ID_RE = re.compile(r"^UC[\w-]{22}$")


def lade_kanal_eingaben(kanaele: list, kanaele_datei) -> list:
    eingaben = [k.strip() for k in kanaele if k and k.strip()]
    if kanaele_datei:
        pfad = Path(kanaele_datei)
        if pfad.suffix.lower() == ".csv":
            df = pd.read_csv(pfad, dtype=str)
            spalte = next((c for c in ("channel_id", "kanalname") if c in df.columns), df.columns[0])
            eingaben += df[spalte].dropna().str.strip().tolist()
        else:
            eingaben += [z.strip() for z in pfad.read_text(encoding="utf-8").splitlines() if z.strip()]
    # Reihenfolge erhalten, Duplikate entfernen
    return list(dict.fromkeys(eingaben))


def _schluessel(name: str) -> str:
    return name.strip().lstrip("@").casefold()


def baue_namensindex() -> pd.DataFrame:
    """Kanaltitel und Handles aus der channels-Tabelle."""
    channels = video_registry.get_channels()
    index = pd.concat([
        channels[["channel_id", "title"]].rename(columns={"title": "name"}),
        channels[["channel_id", "handle"]].rename(columns={"handle": "name"}),
    ], ignore_index=True).dropna()
    index["schluessel"] = index["name"].map(_schluessel)
    return index.drop_duplicates(["channel_id", "schluessel"])


def suche_in_video_kanaltiteln(namen: list) -> pd.DataFrame:
    """Fallback fuer Kanaele ohne channels-Eintrag: Abgleich gegen
    videos.channel_title. channel_title ist nicht indiziert, die Abfrage
    scannt daher die ganze videos-Tabelle (dauert mehrere Minuten) und laeuft nur,
    wenn ein Name in channels nicht gefunden wurde."""
    print(f"Suche {len(namen)} Name(n) in videos.channel_title (kann mehrere Minuten dauern) ...")
    placeholders = ",".join("?" * len(namen))
    con = video_registry._connect()
    try:
        index = pd.read_sql_query(
            f"SELECT DISTINCT channel_id, channel_title AS name FROM videos "
            f"WHERE lower(trim(channel_title)) IN ({placeholders})",
            con,
            params=[n.lower() for n in namen],
        )
    finally:
        con.close()
    index["schluessel"] = index["name"].map(_schluessel)
    return index


def loese_kanaele_auf(eingaben: list) -> list:
    channel_ids, probleme = [], []
    namen = [e for e in eingaben if not CHANNEL_ID_RE.match(e)]
    namensindex = baue_namensindex() if namen else pd.DataFrame(columns=["channel_id", "schluessel"])
    fehlend = [n for n in namen if _schluessel(n) not in set(namensindex["schluessel"])]
    if fehlend:
        namensindex = pd.concat([namensindex, suche_in_video_kanaltiteln(fehlend)], ignore_index=True)

    for eingabe in eingaben:
        if CHANNEL_ID_RE.match(eingabe):
            channel_ids.append(eingabe)
            continue
        treffer = namensindex.loc[namensindex["schluessel"] == _schluessel(eingabe), "channel_id"].unique()
        if len(treffer) == 1:
            channel_ids.append(treffer[0])
        elif len(treffer) == 0:
            probleme.append(f"  nicht gefunden: {eingabe!r}")
        else:
            probleme.append(f"  mehrdeutig: {eingabe!r} -> {', '.join(treffer)} (bitte Channel-ID angeben)")
    if probleme:
        print("Kanaele uebersprungen:\n" + "\n".join(probleme), file=sys.stderr)
    return list(dict.fromkeys(channel_ids))


def lade_videos(channel_ids: list, start, ende, video_format) -> pd.DataFrame:
    videos = video_registry.get_videos_with_text(channel_ids=channel_ids, min_duration_seconds=None)
    stats = video_registry.get_video_stats(channel_ids=channel_ids)[["video_id", "view_count"]]
    videos = videos.merge(stats, on="video_id", how="left")

    videos["published_at"] = pd.to_datetime(videos["published_at"], utc=True, format="ISO8601").dt.tz_localize(None)
    # Enddatum inklusive (ganzer Tag)
    im_zeitraum = (videos["published_at"] >= start) & (videos["published_at"] < ende + pd.Timedelta(days=1))
    videos = videos.loc[im_zeitraum]

    formate = video_registry.get_video_formats(channel_ids=channel_ids)
    if FEHLENDE_FORMATE_OUTPUT:
        schreibe_fehlende_formate(videos, formate, start, ende)
    if video_format:
        ids = set(formate.loc[formate["format"] == video_format, "video_id"])
        ohne_format = (~videos["video_id"].isin(formate["video_id"])).sum()
        if ohne_format:
            print(f"Hinweis: {ohne_format} Videos ohne Format-Zuordnung werden bei VIDEO_FORMAT ausgeschlossen.",
                  file=sys.stderr)
        videos = videos.loc[videos["video_id"].isin(ids)]
    return videos


def schreibe_fehlende_formate(videos: pd.DataFrame, formate: pd.DataFrame, start, ende) -> None:
    """Schreibt die Kanaele mit Videos ohne Format im Zeitraum als Kanalliste
    fuer step1_sample/channel_video_formats.py (CHANNEL_INPUT auf diese Datei,
    PUBLISHED_AFTER/PUBLISHED_BEFORE = None -> Fenster aus fenster_von/fenster_bis)."""
    videos = videos.assign(ohne_format=~videos["video_id"].isin(formate["video_id"]))
    je_kanal = videos.groupby("channel_id").agg(
        kanalname=("channel_title", "first"),
        n_videos_zeitraum=("video_id", "size"),
        n_ohne_format=("ohne_format", "sum"),
    ).reset_index()
    liste = je_kanal.loc[je_kanal["n_ohne_format"] > 0].sort_values("n_ohne_format", ascending=False)
    # Fensterformat wie in channel_video_formats.py (ISO mit Z, Ende inklusive)
    liste = liste.assign(fenster_von=f"{start:%Y-%m-%d}T00:00:00Z", fenster_bis=f"{ende:%Y-%m-%d}T23:59:59Z")
    pfad = Path(FEHLENDE_FORMATE_OUTPUT)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    liste.to_csv(pfad, index=False, encoding="utf-8")
    if liste.empty:
        print(f"Alle Videos im Zeitraum haben ein Format (leere Kanalliste -> {pfad}).")
    else:
        print(f"{int(liste['n_ohne_format'].sum())} Videos ohne Format in {len(liste)} Kanaelen -> {pfad}\n"
              f"  Formate abfragen: step1_sample/channel_video_formats.py mit CHANNEL_INPUT = diese Datei "
              f"und PUBLISHED_AFTER = PUBLISHED_BEFORE = None, danach dieses Skript erneut ausfuehren.")


def _zufallsschluessel(seed, video_id: str) -> int:
    """Deterministischer Pseudo-Zufallswert aus seed und video_id (unabhaengig
    von Python-Hash-Salt, Datenreihenfolge und den uebrigen Videos)."""
    digest = hashlib.blake2b(f"{seed}|{video_id}".encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def ziehe_stichprobe(videos: pd.DataFrame, frequenz: str, n: int, seed) -> pd.DataFrame:
    freq = FREQUENZEN[frequenz]
    videos = videos.copy()
    if freq is None:
        videos["periode"] = "gesamt"
    else:
        videos["periode"] = videos["published_at"].dt.to_period(freq).astype(str)
    # Fester Zufallsschluessel je Video (nur von seed und video_id abhaengig),
    # dann je Kanal x Periode die n kleinsten Schluessel nehmen
    videos["_schluessel"] = videos["video_id"].map(lambda v: _zufallsschluessel(seed, v))
    stichprobe = (
        videos.sort_values(["_schluessel", "video_id"])
        .groupby(["channel_id", "periode"], sort=False)
        .head(n)
        .drop(columns="_schluessel")
    )

    groessen = videos.groupby(["channel_id", "periode"]).size()
    zu_klein = (groessen < n).sum()
    if zu_klein:
        print(f"Hinweis: in {zu_klein} von {len(groessen)} Kanal-Perioden gab es weniger als {n} Videos "
              f"(dort wurden alle genommen).")
    return stichprobe.sort_values(["channel_id", "periode", "published_at"])


def main():
    if not KANAELE and not KANAELE_DATEI:
        sys.exit("KANAELE oder KANAELE_DATEI angeben.")
    if FREQUENZ not in FREQUENZEN:
        sys.exit(f"FREQUENZ muss eines von {list(FREQUENZEN)} sein.")
    if VIDEO_FORMAT is not None and VIDEO_FORMAT not in video_registry.VIDEO_FORMATS:
        sys.exit(f"VIDEO_FORMAT muss None oder eines von {video_registry.VIDEO_FORMATS} sein.")
    if N < 1:
        sys.exit("N muss >= 1 sein.")
    if SEED is not None and not isinstance(SEED, (int, str)):
        sys.exit("SEED muss None, eine ganze Zahl oder ein String sein.")
    start, ende = pd.Timestamp(START), pd.Timestamp(ENDE)
    if ende < start:
        sys.exit("ENDE liegt vor START.")

    channel_ids = loese_kanaele_auf(lade_kanal_eingaben(KANAELE, KANAELE_DATEI))
    if not channel_ids:
        sys.exit("Keine gueltigen Kanaele.")

    videos = lade_videos(channel_ids, start, ende, VIDEO_FORMAT)
    ohne_videos = set(channel_ids) - set(videos["channel_id"])
    if ohne_videos:
        print(f"Hinweis: keine Videos im Zeitraum fuer {len(ohne_videos)} Kanal/Kanaele: "
              f"{', '.join(sorted(ohne_videos))}", file=sys.stderr)
    if videos.empty:
        sys.exit("Keine Videos im Zeitraum gefunden.")

    seed = SEED
    if seed is None:
        seed = random.randrange(2**31)
        print(f"Hinweis: SEED = None, zufaellig gewaehlter Seed fuer diese Ziehung: {seed}")
    stichprobe = ziehe_stichprobe(videos, FREQUENZ, N, seed)

    kanalnamen = video_registry.get_channels(channel_ids).set_index("channel_id")["title"]
    stichprobe["kanalname"] = stichprobe["channel_id"].map(kanalnamen).fillna(stichprobe["channel_title"])

    ausgabe = stichprobe.rename(columns={
        "title": "video_titel",
        "description": "video_beschreibung",
        "view_count": "views",
    })[["channel_id", "kanalname", "video_id", "video_titel", "video_beschreibung",
        "views", "published_at", "periode"]]
    ausgabe["views"] = ausgabe["views"].astype("Int64")

    out_path = Path(OUTPUT) if OUTPUT else (
        OUT_DIR / f"zufallsstichprobe_videos_{datetime.now():%Y%m%d_%H%M%S}.csv"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig, damit Excel Umlaute korrekt anzeigt
    ausgabe.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"{len(ausgabe)} Videos aus {ausgabe['channel_id'].nunique()} Kanaelen -> {out_path}")


if __name__ == "__main__":
    main()

"""
yt-dlp-Helfer zum Aufzaehlen der Video-IDs eines Kanal-Tabs, ohne Downloads.

Ausgelagert aus step1_sample/channel_all_videos.py (TARGETED_SEARCH_YTDLP), damit
auch step1_sample/channel_video_formats.py ihn nutzen kann. Bewusst nicht ueber
youtube_code.utils.__init__ re-exportiert, damit yt_dlp nur dort importiert
wird, wo es wirklich gebraucht wird.

Die Kanal-Tabs trennen nach Format:
  /videos  - nur normale Videos (long-form), KEINE Shorts und keine Livestreams
  /shorts  - nur Shorts
  /streams - nur (vergangene) Livestreams

Unvollstaendige Aufzaehlung: yt-dlp blaettert einen Tab in Seiten zu ~30
Eintraegen durch. Liefert YouTube fuer eine Seite "Incomplete data" und
scheitern alle Wiederholungen, bricht yt-dlp standardmaessig STILL ab und gibt
die bis dahin gesammelte Teilliste zurueck (nur eine Warnung). So geschehen am
2026-10-06 bei tagesschau /videos: 6.510 statt 29.973 IDs. Deshalb hier:
mehr Wiederholungen mit Wartezeit (YTDLP_EXTRACTOR_RETRIES) und
raise_incomplete_data -> der Fall wird zu einer Exception statt einer
Teilliste; die aufrufenden Skripte vermerken den Kanal dann als "fehler", ein
Folgelauf fragt ihn neu ab.

Frueher Abbruch: iter_channel_video_id_batches() blaettert den Tab lazy in
Bloecken; die Aufrufer (channel_video_formats.py, channel_all_videos.py)
brechen ab, sobald YTDLP_EARLY_STOP_BATCHES Bloecke komplett vor ihrem
Zeitfenster liegen, und sparen so das Abrufen der aelteren Seiten.
"""
from typing import Iterator

import yt_dlp

CHANNEL_TABS = ("videos", "shorts", "streams")

# Wiederholungen je Seite bei "Incomplete data"/Netzwerkfehlern (yt-dlp-Default: 3)
# mit exponentieller Wartezeit 1, 2, 4, ... hoechstens 30 s.
YTDLP_EXTRACTOR_RETRIES = 10


class _WarningLogger:
    """Unterdrueckt Debug/Info-Ausgaben, gibt Warnungen und Fehler aber aus
    (statt sie per no_warnings zu verschlucken)."""

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        print(f"    [yt-dlp] {msg}")

    def error(self, msg):
        # Fehlender Tab wird in iter_channel_video_id_batches() als 0 Videos
        # behandelt - keine irrefuehrende ERROR-Zeile ausgeben.
        if "does not have" not in msg.lower():
            print(f"    [yt-dlp] {msg}")


def _ydl_opts() -> dict:
    return {
        "extract_flat": True,
        "quiet": True,
        "logger": _WarningLogger(),
        "skip_download": True,
        "extractor_retries": YTDLP_EXTRACTOR_RETRIES,
        "retry_sleep_functions": {"extractor": lambda n: min(2 ** n, 30)},
        # Erschoepfte Wiederholungen bei "Incomplete data" -> Exception statt
        # stillem Abbruch mit Teilliste
        "extractor_args": {"youtube": {"raise_incomplete_data": ["true"]}},
    }


def iter_channel_video_id_batches(channel_id: str, tab: str = "videos",
                                  batch_size: int = 50) -> Iterator[list[str]]:
    """
    Zaehlt die Video-IDs des oeffentlichen Tabs `tab` (siehe CHANNEL_TABS)
    eines Kanals per flat (metadata-only) playlist extraction auf - keine
    Downloads, keine Requests pro Video - und liefert sie in Bloecken zu
    `batch_size` IDs, neueste zuerst.

    Lazy: yt-dlp laedt die naechste Tab-Seite (~30 Eintraege) erst, wenn der
    Aufrufer den naechsten Block anfordert. Bricht der Aufrufer die Schleife ab
    (z.B. sobald die Bloecke vor seinem Zeitfenster liegen), werden die
    restlichen, aelteren Seiten gar nicht erst abgerufen - bei tagesschau
    /videos rund 12.000 von 30.000 IDs fuer das Fenster ab 2021.

    Reicht bei sehr grossen Kanaelen deutlich weiter zurueck als
    playlistItems.list, das nach rund 20.000 Eintraegen abbricht (verifiziert:
    Videos von ueber einem Jahr vor dem playlistItems-Abbruch gefunden).
    Das Upload-Datum, das yt-dlp im flat-Modus raten kann, ist unzuverlaessig
    und wird bewusst NICHT zurueckgegeben - das echte publishedAt muss aus der
    Registry bzw. per Data API (videos().list) kommen; darauf beruht auch die
    Abbruchentscheidung des Aufrufers.

    Ein Kanal ohne diesen Tab (z.B. keine Livestreams) liefert keine Bloecke.
    Bricht die Aufzaehlung trotz YTDLP_EXTRACTOR_RETRIES Wiederholungen wegen
    "Incomplete data" ab, wird yt_dlp.utils.DownloadError geworfen - auch
    mitten in der Iteration, nachdem schon Bloecke geliefert wurden (keine
    stille Teilliste, siehe Moduldocstring).
    """
    if tab not in CHANNEL_TABS:
        raise ValueError(f"Unbekannter Tab {tab!r}, erlaubt: {CHANNEL_TABS}")

    url = f"https://www.youtube.com/channel/{channel_id}/{tab}"
    with yt_dlp.YoutubeDL(_ydl_opts()) as ydl:
        try:
            # process=False: entries bleibt ein Generator, der Seite fuer
            # Seite nachlaedt (statt den ganzen Tab vorab aufzuzaehlen).
            info = ydl.extract_info(url, download=False, process=False)
        except yt_dlp.utils.DownloadError as e:
            # Fehlender Tab ("This channel does not have a streams tab") ist
            # kein Fehler, sondern bedeutet: 0 Videos dieses Formats.
            if "does not have" in str(e).lower():
                return
            raise

        batch: list[str] = []
        for e in (info or {}).get("entries") or []:
            vid = (e or {}).get("id")
            if not vid:
                continue
            batch.append(vid)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch


def list_channel_video_ids_ytdlp(channel_id: str, tab: str = "videos") -> list[str]:
    """
    Alle Video-IDs des Tabs `tab` als Liste (neueste zuerst), ohne frueheren
    Abbruch - zaehlt den kompletten Tab auf (tagesschau /videos: ~30.000 IDs,
    ~10 Minuten). Fuer ein Zeitfenster stattdessen
    iter_channel_video_id_batches() nutzen und abbrechen, sobald das Fenster
    verlassen ist. Fehlerverhalten wie dort.
    """
    return [vid for batch in iter_channel_video_id_batches(channel_id, tab) for vid in batch]

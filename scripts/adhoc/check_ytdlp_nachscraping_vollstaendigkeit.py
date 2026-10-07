# -*- coding: utf-8 -*-
"""
check_ytdlp_nachscraping_vollstaendigkeit.py

Prueft, ob das yt-dlp-Nachscraping vom 01.10.2026
(channel_all_videos.py, Modus TARGETED_SEARCH_YTDLP) pro Kanal still
abgebrochen ist. Hintergrund: yt-dlp hat damals bei wiederholtem
"Incomplete data" das Blaettern im /videos-Tab ohne Fehler beendet und eine
Teilliste geliefert (nachgewiesen 06.10.2026 an tagesschau: 6.510 statt
29.973 IDs; behoben in youtube_code/utils/ytdlp.py). Die Statusdateien
zeigen dann trotzdem "komplett".

Vorgehen (keine API-Quota): Der /videos-Tab jedes Kanals wird erneut per
yt-dlp aufgezaehlt (neueste zuerst, lazy ueber
utils/ytdlp.iter_channel_video_id_batches mit dessen robusten Optionen)
und gegen die Registry abgeglichen. Die Registry enthaelt fuer diese Kanaele nur Videos ab 2021-01-01. Daraus folgt:
  - Unbekannte IDs VOR der ersten bekannten ID: neuer als die Registry
    (nach dem Fenster oder nach dem letzten Scraping) -> irrelevant.
  - Unbekannte IDs ZWISCHEN bekannten IDs: liegen zeitlich im Fenster, wurden
    aber nicht erfasst -> "verpasst".
  - Nach STOP_AFTER_UNKNOWN aufeinanderfolgenden unbekannten IDs wird
    abgebrochen (dann liegt die Liste vor 2021). Eine echte Luecke von mehr
    als STOP_AFTER_UNKNOWN Videos wuerde damit zu frueh stoppen; das zeigt
    die Spalte "gestoppt_bei" (Position) und laesst sich am Abstand zur
    Gesamtzahl erkennen.

Eingaben: Statusdateien nachscraping_ytdlp_*_status.csv in
outputs/segment_analysis/datenluecken_quartale/ (Kanaele mit Status
"komplett").

Ausgaben (outputs/segment_analysis/datenluecken_quartale/):
  - ytdlp_vollstaendigkeit.csv          eine Zeile pro Kanal (wird fortlaufend
                                        geschrieben; fertige Kanaele werden
                                        beim Neustart uebersprungen)
  - ytdlp_vollstaendigkeit_verpasst.csv verpasste Video-IDs (zum Nachtragen
                                        per videos.list)
  - ytdlp_vollstaendigkeit.md           Uebersicht

Laufzeit: grob 1 s pro 30 Videos im Fenster (tagesschau ~10 min), fuer alle
Kanaele zusammen etwa 1,5-2 h. Kein nennenswerter Speicherbedarf.

Aufruf: python scripts/adhoc/check_ytdlp_nachscraping_vollstaendigkeit.py
"""
import csv
import glob
import os
import sqlite3
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from youtube_code.config import OUTPUTS
from youtube_code.store import video_registry
from youtube_code.utils.ytdlp import iter_channel_video_id_batches

DIR = OUTPUTS / "segment_analysis" / "datenluecken_quartale"
OUT_CSV = DIR / "ytdlp_vollstaendigkeit.csv"
OUT_VERPASST = DIR / "ytdlp_vollstaendigkeit_verpasst.csv"
OUT_MD = DIR / "ytdlp_vollstaendigkeit.md"
REGISTRY = video_registry.DB_PATH

STOP_AFTER_UNKNOWN = 1000

FIELDS = ["channel_id", "title", "status_alt", "aufrufe_alt", "n_neu_alt",
          "n_registry", "n_gelesen", "n_bekannt_im_tab", "n_verpasst",
          "gestoppt", "gestoppt_bei", "sekunden", "fehler"]


def load_channels() -> list[dict]:
    letzter = {}
    for f in sorted(glob.glob(str(DIR / "nachscraping_ytdlp_*_status.csv"))):
        with open(f, encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                letzter[row["channel_id"]] = row
    return [r for r in letzter.values() if r["status"] == "komplett"]


def check_channel(channel_id: str, known: set[str]) -> dict:
    n_gelesen = n_bekannt = 0
    seit_bekannt = []          # unbekannte IDs seit der letzten bekannten
    verpasst = []
    gestoppt, gestoppt_bei = False, None
    for batch in iter_channel_video_id_batches(channel_id, "videos"):
        for vid in batch:
            n_gelesen += 1
            if vid in known:
                if n_bekannt:
                    verpasst.extend(seit_bekannt)
                n_bekannt += 1
                seit_bekannt = []
            elif n_bekannt:
                seit_bekannt.append(vid)
                if len(seit_bekannt) >= STOP_AFTER_UNKNOWN:
                    gestoppt, gestoppt_bei = True, n_gelesen
                    break
        if gestoppt:
            break
    return {"n_gelesen": n_gelesen, "n_bekannt_im_tab": n_bekannt,
            "verpasst": verpasst, "gestoppt": gestoppt, "gestoppt_bei": gestoppt_bei}


def write_md(rows: list[dict]) -> None:
    lines = [
        "# yt-dlp-Nachscraping 01.10.2026: Vollstaendigkeitspruefung",
        "",
        "Erzeugt von `scripts/adhoc/check_ytdlp_nachscraping_vollstaendigkeit.py`. "
        "Der /videos-Tab wurde erneut aufgezaehlt (ohne stillen Abbruch) und gegen die Registry "
        "abgeglichen. *verpasst* = IDs im Tab zwischen zwei Registry-Videos, also im Fenster, "
        "aber nicht in der Registry. *bekannt im Tab* < *Registry* ist normal (Registry enthaelt "
        "auch Shorts/Livestreams/geloeschte Videos, der /videos-Tab nicht).",
        "",
        "| Kanal | Registry | gelesen | bekannt im Tab | verpasst | Stopp (Pos.) | Sek. | Fehler |",
        "| --- | ---: | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for r in sorted(rows, key=lambda r: -int(r["n_verpasst"] or 0)):
        lines.append(f"| {r['title']} | {r['n_registry']} | {r['n_gelesen']} | {r['n_bekannt_im_tab']} "
                     f"| **{r['n_verpasst']}** | {r['gestoppt_bei'] or '-'} | {r['sekunden']} "
                     f"| {r['fehler'] or ''} |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    channels = load_channels()
    con = sqlite3.connect(REGISTRY)
    titles = dict(con.execute("select channel_id, title from channels"))

    done = {}
    if OUT_CSV.exists():
        with open(OUT_CSV, encoding="utf-8", newline="") as fh:
            done = {r["channel_id"]: r for r in csv.DictReader(fh) if not r["fehler"]}
    print(f"Kanaele: {len(channels)}, bereits geprueft: {len(done)}")

    for i, ch in enumerate(channels, 1):
        cid = ch["channel_id"]
        if cid in done:
            continue
        known = {v for (v,) in con.execute("select video_id from videos where channel_id=?", (cid,))}
        title = (titles.get(cid) or cid).strip()
        print(f"[{i}/{len(channels)}] {title} (Registry {len(known)})", flush=True)
        t = time.time()
        row = {"channel_id": cid, "title": title, "status_alt": ch["status"],
               "aufrufe_alt": ch["n_videos_list_aufrufe"], "n_neu_alt": ch["n_neue_videos"],
               "n_registry": len(known), "fehler": ""}
        try:
            res = check_channel(cid, known)
            row.update({k: res[k] for k in ("n_gelesen", "n_bekannt_im_tab", "gestoppt", "gestoppt_bei")})
            row["n_verpasst"] = len(res["verpasst"])
            neu_v = not OUT_VERPASST.exists()
            with open(OUT_VERPASST, "a", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh)
                if neu_v:
                    w.writerow(["channel_id", "video_id"])
                w.writerows([cid, v] for v in res["verpasst"])
        except Exception as e:
            row["fehler"] = str(e)[:200]
        row["sekunden"] = round(time.time() - t)
        print(f"  gelesen {row.get('n_gelesen')}, bekannt {row.get('n_bekannt_im_tab')}, "
              f"verpasst {row.get('n_verpasst')}, {row['sekunden']} s {row['fehler']}", flush=True)
        neu = not OUT_CSV.exists()
        with open(OUT_CSV, "a", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            if neu:
                w.writeheader()
            w.writerow({k: row.get(k, "") for k in FIELDS})
        done[cid] = {k: str(row.get(k, "")) for k in FIELDS}

    write_md(list(done.values()))
    print(f"Fertig: {OUT_MD}")


if __name__ == "__main__":
    main()

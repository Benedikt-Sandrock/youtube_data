"""
ziehung_angebotsstudie.py
=========================

Zieht aus den aufbereiteten Segmenten (aufbereitung_angebotsstudie.py)
die Stichprobe fuer den Codierlauf und teilt sie in Codier-Batches.

    python ziehung_angebotsstudie.py

Regeln (Entscheidung 19.10.2026):
    1. Videos: je Kanal und Woche hoechstens LIMIT_PRO_WOCHE Videos (mit
       Transkript). Kanal-Wochen mit hoechstens LIMIT_PRO_WOCHE Videos gehen
       vollstaendig ein. Bei mehr Videos wird reihum nach Tagen gezogen:
       erst je ein Video pro Tag, dann ein zweites pro Tag usw.; Tage mit
       weniger Videos geben ihre Plaetze an die anderen Tage ab.
       Bei LIMIT_PRO_WOCHE = 14 ergibt das bis zu 2 Videos pro Tag.
    2. Segmente: je Video hoechstens MAX_SEGMENTE_PRO_VIDEO Segmente,
       gleichmaessig ueber das Video verteilt (erstes, letztes, Mitte, ...).
       Videos bis ca. 23 Minuten sind bei 4 Segmenten vollstaendig.
    3. Wochen sind 7-Tage-Bloecke, verankert am Kriegsbeginn (Do, 24.02.2022),
       damit keine Woche den Kriegsbeginn ueberspannt.

NACHZIEHEN: Die Auswahl ist verschachtelt. Jedes Video und jedes Segment
erhaelt eine feste Prioritaet (stabiler Hash, SEED). Ein hoeheres Limit
waehlt immer eine Obermenge der bisherigen Auswahl. Bereits gebildete
Batches bleiben unveraendert (batches/manifest.csv); neu ausgewaehlte
Segmente kommen in neue Batches mit fortlaufender Nummer. Zum Nachziehen
nur LIMIT_PRO_WOCHE bzw. MAX_SEGMENTE_PRO_VIDEO erhoehen und erneut
ausfuehren. Ein SENKEN der Limits ist nicht vorgesehen (Abbruch).

Ausgaben (Ordner angebot/):
    stichprobe_videos.csv     je Video: Kanal-Woche, Prioritaet, Auswahl,
                              Ziehungsgewicht
    stichprobe_segmente.csv   je Segment: Prioritaet, Auswahl, Segmentgewicht
    batches/batch_XXXX.txt    blinde Codier-Batches (Fliesstext, je Segment
                              "### SEGMENT <segment_id>" und Text; ohne Kontext)
    batches/manifest.csv      segment_id -> batch, Lauf-Kennung, Limits
"""

from __future__ import annotations

import hashlib
import json
import sys
import textwrap
from pathlib import Path

import pandas as pd

# ============================================================
# CONFIG
# ============================================================

BASIS = Path(__file__).resolve().parent
ANGEBOT = BASIS / "angebot"
SEGMENTE_DATEI = ANGEBOT / "segmente_alle.csv"
SCHLUESSEL_DATEI = ANGEBOT / "schluessel.csv"
BATCH_DIR = ANGEBOT / "batches"
MANIFEST = BATCH_DIR / "manifest.csv"

LIMIT_PRO_WOCHE = 14           # Videos je Kanal und Woche (nur erhoehen!)
MAX_SEGMENTE_PRO_VIDEO = 4     # Segmente je Video (nur erhoehen!)
WOCHEN_ANKER = "2022-02-24"    # Beginn einer Woche (Kriegsbeginn, Donnerstag)
BATCH_GROESSE = 50             # Segmente je Batch (Videos werden nicht geteilt)
ZEILENBREITE = 120             # Batch-Dateien als Fliesstext mit Zeilenumbruechen

# Kanalauswahl (Entscheidung 20.10.2026, stern TV statt Der Dunkle Parabelritter): alle Kanaele des Typs
# alternativ_rechts, von ÖRR und traditionellen Medien nur diese:
TYPEN_VOLLSTAENDIG = ["alternativ_rechts"]
KANAELE_ETABLIERT = [
    "ZDFheute Nachrichten", "tagesschau", "phoenix", "MrWissen2go", "DW Deutsch",
    "WELT Nachrichtensender", "BILD", "DER SPIEGEL", "faz", "stern TV",
]

# Bereits codierte Segmente (Messlauf mit Codebuch 1.3, auf 2.0-Felder reduziert):
# werden nicht erneut in Batches aufgenommen.
BEREITS_CODIERT = ANGEBOT / "codierung_messlauf_v13.jsonl"

SEED = "angebot-ziehung-2026-v1"   # NIE aendern (Verschachtelung haengt daran)


# ============================================================
# Hilfsfunktionen
# ============================================================

def h(wert: str, salt: str) -> int:
    return int(hashlib.blake2b(f"{SEED}::{salt}::{wert}".encode("utf-8"),
                               digest_size=8).hexdigest(), 16)


def segment_reihenfolge(n: int) -> list[int]:
    """Verschachtelte Reihenfolge der Segmentindizes: erstes, letztes, dann
    jeweils die Mitte der groessten Luecke. Die ersten k Eintraege sind fuer
    jedes k gleichmaessig ueber das Video verteilt."""
    if n <= 0:
        return []
    if n == 1:
        return [0]
    ordnung = [0, n - 1]
    luecken = [(0, n - 1)]
    while len(ordnung) < n:
        luecken.sort(key=lambda ab: (-(ab[1] - ab[0]), ab[0]))
        a, b = luecken.pop(0)
        if b - a < 2:
            continue
        m = (a + b) // 2
        ordnung.append(m)
        luecken += [(a, m), (m, b)]
    return ordnung


# ============================================================
# 1. Videoauswahl
# ============================================================

def videoauswahl(schl: pd.DataFrame) -> pd.DataFrame:
    fehlend = set(KANAELE_ETABLIERT) - set(schl["channel_title"])
    if fehlend:
        sys.exit(f"[Ziehung] Kanaele nicht gefunden: {sorted(fehlend)}")
    behalten = schl["medientyp"].isin(TYPEN_VOLLSTAENDIG) | schl["channel_title"].isin(KANAELE_ETABLIERT)
    schl = schl[behalten]
    v = (schl.groupby("video_id")
         .agg(channel_id=("channel_id", "first"), channel_title=("channel_title", "first"),
              medientyp=("medientyp", "first"), phase=("phase", "first"),
              datum=("datum_lokal", "first"), n_segmente=("n_segmente_video", "first"))
         .reset_index())
    v["datum"] = pd.to_datetime(v["datum"])
    anker = pd.Timestamp(WOCHEN_ANKER)
    v["woche"] = ((v["datum"] - anker).dt.days // 7).astype(int)   # 0 = erste Kriegswoche

    # Prioritaet: Rang innerhalb des Tages (Hash), dann Tag (Hash) -> reihum nach Tagen
    v["_h_vid"] = v["video_id"].map(lambda x: h(x, "video"))
    v["rang_tag"] = v.groupby(["channel_id", "datum"])["_h_vid"].rank(method="first").astype(int)
    v["_h_tag"] = (v["channel_id"] + "|" + v["datum"].dt.strftime("%Y-%m-%d")).map(lambda x: h(x, "tag"))
    v = v.sort_values(["channel_id", "woche", "rang_tag", "_h_tag", "_h_vid"])
    v["prio_woche"] = v.groupby(["channel_id", "woche"]).cumcount() + 1

    v["n_woche"] = v.groupby(["channel_id", "woche"])["video_id"].transform("size")
    v["ausgewaehlt"] = (v["prio_woche"] <= LIMIT_PRO_WOCHE).astype(int)
    v["n_woche_gezogen"] = v.groupby(["channel_id", "woche"])["ausgewaehlt"].transform("sum")
    # Ziehungsgewicht (Kanal-Woche): Videos gesamt / gezogen
    v["gewicht_video"] = (v["n_woche"] / v["n_woche_gezogen"]).where(v["ausgewaehlt"] == 1)
    return v.drop(columns=["_h_vid", "_h_tag"])


# ============================================================
# 2. Segmentauswahl
# ============================================================

def segmentauswahl(seg: pd.DataFrame, videos: pd.DataFrame) -> pd.DataFrame:
    s = seg[["segment_id", "video_id", "segment_index", "n_segmente_video", "n_woerter"]].copy()
    prio = {}
    for vid, n in s.groupby("video_id")["n_segmente_video"].first().items():
        for p, idx in enumerate(segment_reihenfolge(int(n)), start=1):
            prio[(vid, idx)] = p
    s["prio_segment"] = [prio[(a, b)] for a, b in zip(s["video_id"], s["segment_index"])]
    gewaehlt = videos.loc[videos["ausgewaehlt"] == 1, "video_id"]
    s["ausgewaehlt"] = (s["video_id"].isin(gewaehlt) & (s["prio_segment"] <= MAX_SEGMENTE_PRO_VIDEO)).astype(int)
    n_cod = s.groupby("video_id")["ausgewaehlt"].transform("sum")
    s["gewicht_segment"] = (s["n_segmente_video"] / n_cod).where(s["ausgewaehlt"] == 1)
    return s


def kontext(seg: pd.DataFrame) -> pd.Series:
    s = seg.sort_values(["video_id", "segment_index"])
    vorher = s.groupby("video_id")["text"].shift(1).fillna("")
    return vorher.map(lambda t: " ".join(t.split()[-KONTEXT_WOERTER:])).reindex(seg.index)


# ============================================================
# 3. Batches (append-only)
# ============================================================

def bilde_batches(auswahl: pd.DataFrame, texte: pd.DataFrame) -> None:
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    if MANIFEST.exists():
        alt = pd.read_csv(MANIFEST)
        if (alt["limit_pro_woche"].max() > LIMIT_PRO_WOCHE
                or alt["max_segmente_pro_video"].max() > MAX_SEGMENTE_PRO_VIDEO):
            sys.exit("[Batches] Limits sind kleiner als in frueheren Laeufen - Senken ist nicht vorgesehen.")
        fehlend = set(alt["segment_id"]) - set(auswahl["segment_id"])
        if fehlend:
            sys.exit(f"[Batches] {len(fehlend)} bereits gebatchte Segmente sind nicht mehr ausgewaehlt "
                     "(Datengrundlage geaendert?). Abbruch.")
        naechste = int(alt["batch"].max()) + 1
        lauf = int(alt["lauf"].max()) + 1
    else:
        alt = pd.DataFrame(columns=["segment_id"])
        naechste, lauf = 1, 1

    erledigt = set(alt["segment_id"])
    if BEREITS_CODIERT.exists():
        with open(BEREITS_CODIERT, encoding="utf-8") as fh:
            erledigt |= {json.loads(l)["segment_id"] for l in fh if l.strip()}
    neu = auswahl[~auswahl["segment_id"].isin(erledigt)].copy()
    if neu.empty:
        print("[Batches] Keine neuen Segmente - nichts zu tun.")
        return

    neu = neu.merge(texte, on="segment_id")
    # Videos in Zufallsreihenfolge, Segmente eines Videos zusammen und in Reihenfolge
    neu["_h"] = neu["video_id"].map(lambda x: h(x, "batchreihe"))
    neu = neu.sort_values(["_h", "segment_index"])

    zeilen, batch, im_batch = [], naechste, 0
    for vid, gruppe in neu.groupby("_h", sort=True):
        if im_batch and im_batch + len(gruppe) > BATCH_GROESSE:
            batch, im_batch = batch + 1, 0
        for r in gruppe.itertuples(index=False):
            zeilen.append((r.segment_id, batch, r.text))
        im_batch += len(gruppe)

    df = pd.DataFrame(zeilen, columns=["segment_id", "batch", "text"])
    for b, g in df.groupby("batch"):
        # Fliesstext statt JSON: spart Tokens, keine ueberlangen Zeilen beim Lesen
        with open(BATCH_DIR / f"batch_{b:04d}.txt", "w", encoding="utf-8") as fh:
            for r in g.itertuples(index=False):
                fh.write(f"### SEGMENT {r.segment_id}\n")
                fh.write(textwrap.fill(r.text, width=ZEILENBREITE) + "\n\n")
    man = df[["segment_id", "batch"]].assign(lauf=lauf, limit_pro_woche=LIMIT_PRO_WOCHE,
                                             max_segmente_pro_video=MAX_SEGMENTE_PRO_VIDEO)
    man = pd.concat([alt, man], ignore_index=True) if len(alt) else man
    man.to_csv(MANIFEST, index=False, encoding="utf-8-sig")
    print(f"[Batches] Lauf {lauf}: {len(df):,} neue Segmente in Batches "
          f"{naechste:04d}-{batch:04d} ({batch - naechste + 1} Batches)")


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    for f in (SEGMENTE_DATEI, SCHLUESSEL_DATEI):
        if not f.exists():
            sys.exit(f"[Ziehung] {f} fehlt - erst aufbereitung_angebotsstudie.py ausfuehren.")
    seg = pd.read_csv(SEGMENTE_DATEI, dtype={"video_id": "string"})
    schl = pd.read_csv(SCHLUESSEL_DATEI, dtype={"video_id": "string"})

    videos = videoauswahl(schl)
    segs = segmentauswahl(seg, videos)

    videos.to_csv(ANGEBOT / "stichprobe_videos.csv", index=False, encoding="utf-8-sig")
    segs.to_csv(ANGEBOT / "stichprobe_segmente.csv", index=False, encoding="utf-8-sig")

    auswahl = segs[segs["ausgewaehlt"] == 1][["segment_id", "video_id", "segment_index"]]
    bilde_batches(auswahl, seg[["segment_id", "text"]])

    # Log
    print("\n" + "=" * 64)
    print(f"[Log] Limit {LIMIT_PRO_WOCHE} Videos/Kanal-Woche, {MAX_SEGMENTE_PRO_VIDEO} Segmente/Video")
    sv = videos[videos.ausgewaehlt == 1]
    print(f"[Log] Videos: {len(sv):,} von {len(videos):,} | Segmente: {segs.ausgewaehlt.sum():,} von {len(segs):,} "
          f"| Woerter: {segs.loc[segs.ausgewaehlt == 1, 'n_woerter'].sum():,}")
    t = segs.merge(videos[["video_id", "medientyp", "phase"]], on="video_id")
    print("\n[Log] Ausgewaehlte Segmente je Medientyp x Phase:")
    print(t[t.ausgewaehlt == 1].groupby(["medientyp", "phase"]).size().to_string())
    print("\n[Log] Kanal-Wochen mit Kuerzung (n_woche > Limit):",
          int((videos.groupby(['channel_id', 'woche'])['n_woche'].first() > LIMIT_PRO_WOCHE).sum()))
    print("=" * 64)


if __name__ == "__main__":
    main()

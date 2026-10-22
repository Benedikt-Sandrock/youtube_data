"""
aufbereitung_angebotsstudie.py
==============================

Bereitet die Transkripte der Angebotsstudie fuer die Codierung auf
(Codebuch: codebuch_angebotsstudie_v1.md).

    python aufbereitung_angebotsstudie.py

Schritte:
    1. segments.csv (Untertitel je Video) + metadata.csv (Kanal, Datum,
       Medientyp, Titel) einlesen und auf das Zeitfenster filtern.
    2. Untertitel zu Fliesstext zusammenfuehren und in Segmente von ca.
       800 Woertern schneiden. Logik unveraendert aus
       process_scraped_segments.py (transcript_to_text, split_segments),
       aber OHNE Deckelung der Segmentzahl pro Video.
    3. Anonyme Segment-IDs vergeben (aus der video_id nicht rueckrechenbar).
    4. Pilotstichprobe ziehen: Medientyp x Phase (vor/nach Kriegsbeginn),
       je Zelle PILOT_N_PRO_ZELLE Segmente, ein Segment pro Video, Kanaele
       innerhalb der Zelle reihum. Davon HAND_N verschachtelt als blinder
       Kodierbogen fuer die Handcodierung.

Ausgaben (Ordner OUT_DIR):
    segmente_alle.csv          alle Segmente (segment_id, text, ...)
    schluessel.csv             segment_id -> video, Kanal, Datum, Typ, Phase,
                               Pilot-/Hand-Kennzeichen. WAEHREND DES
                               CODIERENS NICHT OEFFNEN.
    pilot_segmente.jsonl       blinde Pilot-Segmente (segment_id, kontext,
                               text) in Zufallsreihenfolge
    kodierbogen_hand_50.xlsx   blinder Kodierbogen fuer die Handcodierung

Alle Zufallsschritte sind ueber SEED deterministisch (stabile Hashes,
keine Abhaengigkeit von Python-hash()).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd

# ============================================================
# CONFIG
# ============================================================

BASIS = Path(__file__).resolve().parent

SEGMENTS_FILE = BASIS / "segments_new.csv"      # vollstaendiger Download (20.10.2026)
METADATA_FILE = BASIS / "metadata.csv"
OUT_DIR = BASIS / "angebot"

# Zeitfenster (Ortszeit Europe/Berlin, Enddatum inklusive)
ZEITZONE = "Europe/Berlin"
ZEITFENSTER_START = "2022-01-01"
ZEITFENSTER_ENDE = "2022-04-30"
KRIEGSBEGINN = "2022-02-24"            # Phase "nach" ab diesem Tag (inklusive)

MEDIENTYP_LABEL = {1: "oerr", 2: "traditionell", 5: "alternativ_rechts"}

# Segmentierung (Werte wie in process_scraped_segments.py)
TARGET_WORDS = 800
SNAP_WINDOW = 150
MIN_TAIL = 200
MIN_WORDS_TOTAL = 50
MAX_SEGMENTS_PER_VIDEO = None          # keine Deckelung (Entscheidung 19.10.)

# Pilot- und Handstichprobe fixieren: Liegt bereits ein schluessel.csv mit
# Pilot-/Hand-Kennzeichen vor, wird diese Auswahl uebernommen und NICHT neu
# gezogen. pilot_segmente.jsonl und der Kodierbogen werden dann nicht
# ueberschrieben. Nur auf False setzen, wenn die Stichprobe bewusst neu
# gezogen werden soll.
PILOT_FIXIEREN = True

# Stichproben
SEED = "angebot-2026-v1"               # NIE aendern (Reproduzierbarkeit)
PILOT_N_PRO_ZELLE = 25                 # 3 Typen x 2 Phasen x 25 = 150
HAND_N = 50                            # verschachtelt in der Pilotstichprobe
KONTEXT_WOERTER = 80                   # Ende des vorangehenden Segments


# ============================================================
# 1. Hilfsfunktionen
# ============================================================

def stabiler_hash(wert: str, salt: str = "") -> int:
    digest = hashlib.blake2b(
        f"{SEED}::{salt}::{wert}".encode("utf-8"), digest_size=8
    ).hexdigest()
    return int(digest, 16)


def anonyme_video_kennung(video_id: str) -> str:
    return hashlib.blake2b(
        f"{SEED}::anon::{video_id}".encode("utf-8"), digest_size=5
    ).hexdigest()


# --- unveraendert aus process_scraped_segments.py --------------------------

def transcript_to_text(raw: str) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None

    parsed = None
    stripped = raw.strip()
    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = None

    if isinstance(parsed, list) and parsed:
        out: list[str] = []
        for entry in parsed:
            if not isinstance(entry, dict):
                continue
            t = (entry.get("text") or "").strip()
            if not t:
                continue
            new = t.split()
            for k in range(min(len(out), len(new), 20), 3, -1):
                if out[-k:] == new[:k]:
                    new = new[k:]
                    break
            out.extend(new)
        text = " ".join(out)
    else:
        text = " ".join(stripped.split())

    return text if len(text.split()) >= MIN_WORDS_TOTAL else None


_SENT_END = re.compile(r"[.!?]$")


def split_segments(
    text: str,
    target: int = TARGET_WORDS,
    snap: int = SNAP_WINDOW,
    min_tail: int = MIN_TAIL,
) -> list[str]:
    words = text.split()
    n = len(words)
    if n <= target + snap:
        return [" ".join(words)]

    segments: list[str] = []
    start = 0
    while start < n:
        end = min(start + target, n)
        if end < n:
            search_lo = max(end - snap, start + 1)
            search_hi = min(end + snap, n)
            best = None
            for i in range(end, search_hi):
                if _SENT_END.search(words[i - 1]):
                    best = i
                    break
            if best is None:
                for i in range(end, search_lo, -1):
                    if _SENT_END.search(words[i - 1]):
                        best = i
                        break
            end = best if best is not None else end
        segments.append(" ".join(words[start:end]))
        start = end

    if len(segments) > 1 and len(segments[-1].split()) < min_tail:
        segments[-2] = segments[-2] + " " + segments[-1]
        segments.pop()

    return segments

# ---------------------------------------------------------------------------


# ============================================================
# 2. Einlesen und Filtern
# ============================================================

def lade_videos() -> pd.DataFrame:
    for f in (SEGMENTS_FILE, METADATA_FILE):
        if not f.exists():
            sys.exit(f"[Einlesen] {f} fehlt.")

    meta = pd.read_csv(METADATA_FILE, dtype={"video_id": "string", "channel_id": "string"})
    pflicht = {"video_id", "channel_id", "channel_title", "published_at", "media_type"}
    fehlt = pflicht - set(meta.columns)
    if fehlt:
        sys.exit(f"[Einlesen] metadata.csv ohne Spalten {sorted(fehlt)}")
    if meta["video_id"].duplicated().any():
        sys.exit("[Einlesen] metadata.csv: video_id nicht eindeutig.")
    unbekannt = set(meta["media_type"].unique()) - set(MEDIENTYP_LABEL)
    if unbekannt:
        sys.exit(f"[Einlesen] unbekannte media_type-Werte: {sorted(unbekannt)}")

    ts = pd.to_datetime(meta["published_at"], utc=True, format="ISO8601")
    meta["datum_lokal"] = ts.dt.tz_convert(ZEITZONE).dt.date.astype(str)
    im_fenster = meta["datum_lokal"].between(ZEITFENSTER_START, ZEITFENSTER_ENDE)
    print(f"[Einlesen] metadata.csv: {len(meta):,} Videos, im Zeitfenster: {im_fenster.sum():,}")
    meta = meta[im_fenster].copy()
    meta["phase"] = (meta["datum_lokal"] >= KRIEGSBEGINN).map({True: "nach", False: "vor"})
    meta["medientyp"] = meta["media_type"].map(MEDIENTYP_LABEL)

    seg = pd.read_csv(
        SEGMENTS_FILE,
        dtype={"video_id": "string"},
        usecols=["video_id", "transcript_segments", "status", "is_generated"],
    )
    if seg["video_id"].duplicated().any():
        sys.exit("[Einlesen] segments.csv: video_id nicht eindeutig.")
    print(f"[Einlesen] segments.csv: {len(seg):,} Videos, davon status OK: "
          f"{(seg['status'].str.lower() == 'ok').sum():,}")

    ohne_meta = ~seg["video_id"].isin(meta["video_id"])
    if ohne_meta.any():
        print(f"[Einlesen] WARNUNG: {ohne_meta.sum():,} Transkripte ohne Metadaten "
              "im Zeitfenster - werden ignoriert.")

    df = meta.merge(seg, on="video_id", how="left", validate="1:1")
    df["transkript_status"] = df["status"].fillna("noch_nicht_geladen").map(status_kategorie)
    return df


def status_kategorie(status: str) -> str:
    """Fehlermeldungen der Transcript-API auf wenige Kategorien verdichten."""
    s = str(status)
    if s.lower() == "ok":
        return "OK"
    if s.startswith("Fehler"):
        if "age-restricted" in s:
            return "fehler_altersbeschraenkt"
        if "Subtitles are disabled" in s:
            return "fehler_untertitel_deaktiviert"
        return "fehler_sonstige"
    return s


# ============================================================
# 3. Segmentierung
# ============================================================

def segmentiere(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    zeilen = []
    video_status = []
    for row in df.itertuples(index=False):
        if str(row.transkript_status).lower() != "ok":
            video_status.append((row.video_id, row.transkript_status, 0))
            continue
        text = transcript_to_text(row.transcript_segments)
        if text is None:
            video_status.append((row.video_id, "zu_kurz", 0))
            continue
        teile = split_segments(text)
        if MAX_SEGMENTS_PER_VIDEO is not None and len(teile) > MAX_SEGMENTS_PER_VIDEO:
            sys.exit("[Segmente] Deckelung ist laut Entscheidung deaktiviert.")
        anon = anonyme_video_kennung(row.video_id)
        for i, t in enumerate(teile):
            zeilen.append({
                "segment_id": f"{anon}_s{i:03d}",
                "video_id": row.video_id,
                "segment_index": i,
                "n_segmente_video": len(teile),
                "n_woerter": len(t.split()),
                "text": t,
            })
        video_status.append((row.video_id, "segmentiert", len(teile)))

    segmente = pd.DataFrame(zeilen)
    status = pd.DataFrame(video_status, columns=["video_id", "aufbereitung", "n_segmente"])

    if segmente["segment_id"].duplicated().any():
        sys.exit("[Segmente] Kollision der anonymen Segment-IDs - SEED/Laenge pruefen.")
    return segmente, status


def kontext_spalte(segmente: pd.DataFrame) -> pd.Series:
    """Letzte KONTEXT_WOERTER Woerter des vorangehenden Segments desselben Videos."""
    seg = segmente.sort_values(["video_id", "segment_index"])
    vorher = seg.groupby("video_id")["text"].shift(1)
    kontext = vorher.fillna("").map(lambda t: " ".join(t.split()[-KONTEXT_WOERTER:]))
    return kontext.reindex(segmente.index)


# ============================================================
# 4. Pilot- und Handstichprobe
# ============================================================

def ziehe_pilot(segmente: pd.DataFrame, videos: pd.DataFrame) -> pd.DataFrame:
    seg = segmente.merge(
        videos[["video_id", "channel_id", "medientyp", "phase"]], on="video_id"
    )
    # Ein Segment pro Video: das mit dem kleinsten stabilen Hash
    seg["_h_seg"] = seg["segment_id"].map(lambda s: stabiler_hash(s, "seg"))
    je_video = seg.sort_values("_h_seg").groupby("video_id", as_index=False).first()
    je_video["_h_vid"] = je_video["video_id"].map(lambda v: stabiler_hash(v, "vid"))

    gezogen = []
    for (typ, phase), zelle in je_video.groupby(["medientyp", "phase"]):
        zelle = zelle.sort_values("_h_vid").copy()
        # Kanaele reihum: Rang des Videos innerhalb seines Kanals, dann Kanal-Hash
        zelle["_rang_kanal"] = zelle.groupby("channel_id").cumcount()
        zelle["_h_kanal"] = zelle["channel_id"].map(lambda c: stabiler_hash(c, "kanal"))
        zelle = zelle.sort_values(["_rang_kanal", "_h_kanal"])
        auswahl = zelle.head(PILOT_N_PRO_ZELLE)
        if len(auswahl) < PILOT_N_PRO_ZELLE:
            print(f"[Pilot] WARNUNG: Zelle {typ}/{phase} nur {len(auswahl)} Videos.")
        gezogen.append(auswahl)

    pilot = pd.concat(gezogen)

    # Handstichprobe verschachtelt: je Zelle die ersten k nach Hash, k moeglichst gleich
    pilot["_h_hand"] = pilot["segment_id"].map(lambda s: stabiler_hash(s, "hand"))
    zellen = sorted(pilot.groupby(["medientyp", "phase"]).groups)
    basis, rest = divmod(HAND_N, len(zellen))
    hand_ids = []
    for j, z in enumerate(zellen):
        k = basis + (1 if j < rest else 0)
        teil = pilot[(pilot["medientyp"] == z[0]) & (pilot["phase"] == z[1])]
        hand_ids += teil.sort_values("_h_hand").head(k)["segment_id"].tolist()
    pilot["hand"] = pilot["segment_id"].isin(hand_ids).astype(int)

    # Zufallsreihenfolge fuer die Codierung
    pilot["_h_reihe"] = pilot["segment_id"].map(lambda s: stabiler_hash(s, "reihe"))
    return pilot.sort_values("_h_reihe")[["segment_id", "hand"]]


# ============================================================
# 5. Ausgaben
# ============================================================

KODIERFELDER = [
    "kodierbar", "redeform", "fremdrede_dominant",
    "themen", "hauptthema", "krieg_bezug", "krieg_aspekte",
    "volkszentrismus", "antielitismus", "manichaeische_moralisierung",
    "emotionale_intensitaet",
    "rus_status", "rus_score", "west_status", "west_score",
    "estab_status", "estab_ziel", "estab_explizit", "estab_score", "estab_gegenstand",
    "estab_kritik_richtung", "estab_intensitaet", "estab_urheber",
    "folgen_verantwortung", "medienkritik",
]


def schreibe_kodierbogen(blind: pd.DataFrame, pfad: Path) -> None:
    bogen = blind.rename(columns={"text": "segment_text"})[["segment_id", "kontext", "segment_text"]]
    for f in KODIERFELDER:
        bogen[f] = ""
    hinweis = pd.DataFrame({
        "Hinweis": [
            "Codierung nach codebuch_angebotsstudie_v1.md (Version 1.1).",
            "Kontext = Ende des vorangehenden Segments, nur zum Verstaendnis, nicht mitcodieren.",
            "Listen-Felder: Werte mit Semikolon trennen (z. B. krieg_ukraine;energie). Leer = leere Liste.",
            "Nicht zutreffende Felder leer lassen (= null).",
            "Wahrheitswerte als true/false.",
            "Die Datei schluessel.csv waehrend der Codierung nicht oeffnen.",
        ]
    })
    with pd.ExcelWriter(pfad, engine="openpyxl") as w:
        bogen.to_excel(w, sheet_name="Kodierung", index=False)
        hinweis.to_excel(w, sheet_name="Hinweise", index=False)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    videos = lade_videos()
    segmente, status = segmentiere(videos)
    segmente["kontext"] = kontext_spalte(segmente)

    # Schluessel
    schluessel = segmente[["segment_id", "video_id", "segment_index", "n_segmente_video", "n_woerter"]].merge(
        videos[["video_id", "channel_id", "channel_title", "media_type", "medientyp",
                "published_at", "datum_lokal", "phase"]],
        on="video_id",
    )

    alt_schluessel = OUT_DIR / "schluessel.csv"
    pilot_fixiert = PILOT_FIXIEREN and alt_schluessel.exists()
    if pilot_fixiert:
        alt = pd.read_csv(alt_schluessel, usecols=["segment_id", "pilot", "hand"])
        pilot = alt.loc[alt["pilot"] == 1, ["segment_id", "hand"]]
        fehlt = set(pilot["segment_id"]) - set(segmente["segment_id"])
        if fehlt:
            sys.exit(f"[Pilot] {len(fehlt)} fixierte Pilotsegmente fehlen in der neuen Segmentierung - Abbruch.")
        alt_text = OUT_DIR / "pilot_segmente.jsonl"
        if alt_text.exists():
            with open(alt_text, encoding="utf-8") as fh:
                alt_t = {json.loads(l)["segment_id"]: json.loads(l)["text"] for l in fh if l.strip()}
            neu_t = segmente.set_index("segment_id")["text"]
            abw = [k for k, t in alt_t.items() if neu_t.get(k) != t]
            if abw:
                sys.exit(f"[Pilot] {len(abw)} Pilotsegmente haben einen anderen Text als bisher - Abbruch.")
        print(f"[Pilot] Fixierte Stichprobe uebernommen: {len(pilot)} Pilot-, {int(pilot['hand'].sum())} Handsegmente.")
    else:
        pilot = ziehe_pilot(segmente, videos)
    schluessel = schluessel.merge(pilot[["segment_id", "hand"]], on="segment_id", how="left")
    schluessel["pilot"] = schluessel["hand"].notna().astype(int)
    schluessel["hand"] = schluessel["hand"].fillna(0).astype(int)

    # Dateien
    segmente[["segment_id", "video_id", "segment_index", "n_segmente_video", "n_woerter", "text"]].to_csv(
        OUT_DIR / "segmente_alle.csv", index=False, encoding="utf-8-sig")
    schluessel.to_csv(OUT_DIR / "schluessel.csv", index=False, encoding="utf-8-sig")

    if not pilot_fixiert:
        blind = pilot.merge(segmente[["segment_id", "kontext", "text"]], on="segment_id")
        with open(OUT_DIR / "pilot_segmente.jsonl", "w", encoding="utf-8") as fh:
            for r in blind.itertuples(index=False):
                fh.write(json.dumps({"segment_id": r.segment_id, "kontext": r.kontext, "text": r.text},
                                    ensure_ascii=False) + "\n")
        schreibe_kodierbogen(blind[blind["hand"] == 1], OUT_DIR / f"kodierbogen_hand_{HAND_N}.xlsx")

    # Log
    print("\n" + "=" * 64)
    print("[Log] Videos im Zeitfenster nach Aufbereitungsstatus:")
    print(status["aufbereitung"].value_counts().to_string())
    v = videos.merge(status, on="video_id")
    print("\n[Log] Videos mit Transkript / gesamt, je Medientyp x Phase:")
    tab = v.assign(ok=v["aufbereitung"].eq("segmentiert")).groupby(["medientyp", "phase"])["ok"].agg(["sum", "count"])
    tab["anteil"] = (tab["sum"] / tab["count"]).round(3)
    print(tab.to_string())
    print(f"\n[Log] Segmente gesamt: {len(segmente):,}  |  Woerter gesamt: {segmente['n_woerter'].sum():,}")
    print(f"[Log] Segmente/Video: median={status.loc[status.n_segmente > 0, 'n_segmente'].median():.0f} "
          f"max={status['n_segmente'].max()}")
    print("\n[Log] Segmente und Woerter je Medientyp:")
    print(schluessel.groupby("medientyp")["n_woerter"].agg(["count", "sum"]).to_string())
    print("\n[Log] Pilot (Hand) je Zelle:")
    print(schluessel[schluessel.pilot == 1].groupby(["medientyp", "phase"])["hand"].agg(["count", "sum"]).to_string())
    print("\n[Log] Pilot: Kanaele je Zelle:")
    print(schluessel[schluessel.pilot == 1].groupby(["medientyp", "phase"])["channel_id"].nunique().to_string())
    print(f"\n[Log] Ausgaben in {OUT_DIR}")
    print("=" * 64)


if __name__ == "__main__":
    main()

"""
process_scrape_segments.py
=======================

Baut aus einer Liste von video_ids eine Datei, die direkt als SEGMENT_FILE
in submit_segments.py eingesetzt werden kann - wahlweise als einzelne
Segmente (bisherige Regeln: ~800 Woerter, auf Satzgrenzen gerundet) oder
als ganze Transkripte (ein Segment pro Video, z. B. fuer IDEOLOGIE_I).

    python segment_transcripts.py

Was passiert, steht im CONFIG-Block unter BEFEHL:

    "segmente"  Segmentierte oder ganze Transkripte schreiben (siehe MODUS)
    "sample"    Blinde Handkodier-Stichprobe aus dem zuletzt erzeugten
                Cache ziehen

NICHT MEHR TEIL DIESES SKRIPTS (von anderen Skripten uebernommen):
    - Kandidaten-ID-Filterung (frueher BEFEHL "ids"). Die Videoliste
      kommt jetzt von aussen: eine CSV mit mindestens der Spalte
      "video_id" (VIDEO_ID_SOURCE), z. B. gefiltert aus
      descriptive_sample.csv oder einer anderen Vorauswahl.
    - Batch-Payload-Erzeugung samt eingebettetem Prompt/Codebuch
      (frueher BEFEHL "payloads"). Das macht jetzt submit_segments.py,
      inklusive responseSchema und Registry-Anbindung.
    - Belegzitat-Pruefung (frueher BEFEHL "verify"). Das leistet jetzt
      die beleg_quote-Spalte in download_segments.py.

Der Output dieses Skripts ist deshalb bewusst schlank: video_id,
segment_index, text, n_woerter - keine Kontext-Spalte mehr, kein
kanalspezifischer Zusatz. Den Kontextblock fuer Prompts mit
use_context=True (z. B. POPULISMUS_P) baut submit_segments.py selbst aus
video_id + segment_index.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys

import pandas as pd

from youtube_code.config import SAMPLES, TRANSCRIPTS, OUTPUTS

# ============================================================
# CONFIG
# ============================================================

BEFEHL = "segmente"                    # "segmente" | "sample"

# CSV mit mindestens der Spalte "video_id" - die zu verarbeitenden Videos.

VIDEO_ID_SOURCE = SAMPLES / "russia" / "out_segments" / "baseline.csv"
# VIDEO_ID_SOURCE = OUTPUTS / "sample_feasibility" / "descriptive_sample.csv"

# Transkript-Quelle. Erwartete Spalten: video_id, transcript, status.
# "transcript" darf entweder eine JSON-Liste von Untertitel-Eintraegen
# ({"text": "..."} je Zeile, mit ueberlappenden rollenden Zeitstempeln)
# oder bereits reiner Fliesstext sein - beides wird erkannt.
TRANSCRIPT_FILE = TRANSCRIPTS / "all_transcripts_segments.csv"
NUR_STATUS_OK = True                   # nur Zeilen mit status == "ok"
CSV_CHUNKSIZE = 500                    # Bloeckgroesse beim Streaming-Lesen

# "segmente"           -> Segmentierung nach den bisherigen Regeln
# "ganze_transkripte"  -> ein Segment (= das ganze Transkript) pro Video
MODUS = "ganze_transkripte"

TARGET_WORDS = 800                     # Zielwortzahl je Segment
SNAP_WINDOW = 150                      # Suchfenster fuer die naechste Satzgrenze
MIN_TAIL = 200                         # Restsegment darunter wird angehaengt
MIN_WORDS_TOTAL = 50                   # Transkripte darunter werden verworfen

OUT_DIR = SAMPLES / "russia" / "out_segments"
OUT_FILE = OUT_DIR / "single_channels_test_populism_segments.csv"    # direkt als SEGMENT_FILE nutzbar

# Nur fuer BEFEHL = "sample"
SAMPLE_N = 200
SAMPLE_SEED = "segment-2026-v1"        # NIE aendern (Nestbarkeit)
SAMPLE_IN_FILE = OUT_FILE              # welcher Cache beprobt wird
SAMPLE_CONTEXT_WORDS = 80              # nur fuer die Anzeige im Kodierbogen


# ============================================================
# 1. Transkripttext aus der Rohspalte
# ============================================================

def transcript_to_text(raw: str) -> str | None:
    """
    Rohwert der "transcript"-Spalte zu fortlaufendem Text.

    Zwei Formate werden akzeptiert:
    - JSON-Liste von Untertitel-Eintraegen mit "text"-Feld. Die
      Zeitstempel ueberlappen (rollende Untertitel), deshalb wird
      geprueft, ob ein Eintrag das Ende des vorherigen woertlich
      wiederholt (>=4 Woerter) und die Wiederholung entfernt.
    - Bereits reiner Fliesstext -> wird unveraendert verwendet.

    None, wenn nach dem Zusammenbau weniger als MIN_WORDS_TOTAL Woerter
    uebrig bleiben.
    """
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


# ============================================================
# 2. Segmentierung
# ============================================================

_SENT_END = re.compile(r"[.!?]$")


def split_segments(
    text: str,
    target: int = TARGET_WORDS,
    snap: int = SNAP_WINDOW,
    min_tail: int = MIN_TAIL,
) -> list[str]:
    """
    Nach Wortzahl schneiden, auf die naechste Satzgrenze runden.

    Pausenbasierte Grenzen sind bei rollenden Untertiteln nicht
    verwendbar: Die Zeitabstaende folgen der Zeilenlaenge, nicht dem
    Sprechrhythmus. Deshalb rein wortbasiert mit Snap auf Satzenden.
    """
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


def to_rows(text: str) -> list[tuple[int, str]]:
    """(segment_index, text)-Paare, je nach MODUS."""
    if MODUS == "ganze_transkripte":
        return [(0, text)]
    if MODUS == "segmente":
        return list(enumerate(split_segments(text)))
    sys.exit(f"Unbekannter MODUS: {MODUS!r}. Erwartet 'segmente' oder 'ganze_transkripte'.")


# ============================================================
# 3. Segmente/Transkripte schreiben
# ============================================================

def load_video_id_filter() -> set[str]:
    if not VIDEO_ID_SOURCE.exists():
        sys.exit(f"{VIDEO_ID_SOURCE} fehlt.")
    ids_df = pd.read_csv(VIDEO_ID_SOURCE, dtype={"video_id": "string"})
    if "video_id" not in ids_df.columns:
        sys.exit(
            f"{VIDEO_ID_SOURCE} hat keine Spalte 'video_id'. "
            f"Vorhanden: {sorted(ids_df.columns.tolist())}"
        )
    ids = set(ids_df["video_id"].dropna().str.strip())
    ids.discard("")
    if not ids:
        sys.exit(f"{VIDEO_ID_SOURCE} enthaelt keine video_ids.")
    print(f"[segmente] {len(ids):,} angeforderte video_ids aus {VIDEO_ID_SOURCE}")
    return ids


def build_segments_file() -> None:
    if MODUS not in ("segmente", "ganze_transkripte"):
        sys.exit(f"MODUS muss 'segmente' oder 'ganze_transkripte' sein, ist {MODUS!r}.")
    if not TRANSCRIPT_FILE.exists():
        sys.exit(f"{TRANSCRIPT_FILE} fehlt.")

    wanted = load_video_id_filter()
    found: set[str] = set()
    excluded_by_status: set[str] = set()
    n_skipped_short = 0
    n_rows = 0
    word_counts: list[int] = []

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_FILE.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["video_id", "segment_index", "text", "n_woerter"])

        reader = pd.read_csv(
            TRANSCRIPT_FILE,
            usecols=lambda c: c in {"video_id", "transcript_segments", "status"},
            dtype={"video_id": "string"},
            chunksize=CSV_CHUNKSIZE,
            low_memory=False,
        )
        for chunk in reader:
            chunk = chunk[chunk["video_id"].isin(wanted)]
            if chunk.empty:
                continue
            found.update(chunk["video_id"].astype(str))

            if NUR_STATUS_OK and "status" in chunk.columns:
                keep = chunk["status"].astype(str).str.lower().eq("ok")
                excluded_by_status.update(chunk.loc[~keep, "video_id"].astype(str))
                chunk = chunk[keep]

            for row in chunk.itertuples(index=False):
                video_id = str(row.video_id)
                text = transcript_to_text(getattr(row, "transcript_segments", None))
                if text is None:
                    n_skipped_short += 1
                    continue
                for segment_index, segment_text in to_rows(text):
                    writer.writerow([video_id, segment_index, segment_text, len(segment_text.split())])
                    word_counts.append(len(segment_text.split()))
                    n_rows += 1

    not_in_file = sorted(wanted - found)

    print("\n" + "=" * 64)
    print(f"MODUS               : {MODUS}")
    print(f"Angefordert         : {len(wanted):,} video_ids")
    print(f"Im Transkript-File  : {len(found):,}")
    if not_in_file:
        print(f"Nicht im File       : {len(not_in_file):,} (z. B. {not_in_file[:5]})")
    if NUR_STATUS_OK and excluded_by_status:
        print(f"Ausgeschlossen (status): {len(excluded_by_status):,}")
    print(f"Uebersprungen (kurz): {n_skipped_short:,}  (< {MIN_WORDS_TOTAL} Woerter)")
    print(f"Zeilen geschrieben  : {n_rows:,}")
    if word_counts:
        series = pd.Series(word_counts)
        print(f"Woerter/Zeile       : median={series.median():.0f} max={series.max():,}")
    print(f"Datei               : {OUT_FILE}")
    print("=" * 64)
    print(
        "\nDirekt als SEGMENT_FILE in submit_segments.py nutzbar - "
        "die Spalten video_id/segment_index/text entsprechen den "
        "Standard-Konfigurationsnamen dort."
    )


# ============================================================
# 4. Blinde Handkodier-Stichprobe
# ============================================================

def stable_hash(value: str) -> int:
    digest = hashlib.blake2b(
        f"{SAMPLE_SEED}::{value}".encode("utf-8"), digest_size=8
    ).hexdigest()
    return int(digest, 16)


def build_context_map(segments: pd.DataFrame, context_words: int) -> dict[tuple[str, int], str]:
    """Letzte `context_words` Woerter des jeweils vorangehenden Segments
    desselben Videos - nur fuer die Anzeige im Kodierbogen."""
    ordering = segments.sort_values(["video_id", "segment_index"])
    contexts: dict[tuple[str, int], str] = {}
    previous_video = object()
    previous_text = ""
    for row in ordering.itertuples(index=False):
        key = (row.video_id, row.segment_index)
        if row.video_id != previous_video:
            contexts[key] = ""
        else:
            contexts[key] = " ".join(previous_text.split()[-context_words:])
        previous_video = row.video_id
        previous_text = row.text
    return contexts


def draw_sample() -> None:
    if not SAMPLE_IN_FILE.exists():
        sys.exit(f"{SAMPLE_IN_FILE} fehlt. Erst BEFEHL = 'segmente' ausfuehren.")

    segments = pd.read_csv(SAMPLE_IN_FILE, dtype={"video_id": "string"})
    required = {"video_id", "segment_index", "text"}
    missing_cols = required - set(segments.columns)
    if missing_cols:
        sys.exit(f"{SAMPLE_IN_FILE} hat nicht die Spalten {sorted(missing_cols)}.")

    if segments.groupby("video_id")["segment_index"].nunique().eq(1).all():
        print(
            "[sample] Hinweis: jedes Video hat nur ein Segment (ganze "
            "Transkripte). Die Stichprobe zieht dann ganze Videos, ohne "
            "Kontext-Mehrwert."
        )

    segments = segments.copy()
    segments["segment_id"] = (
        segments["video_id"].astype(str) + "__s"
        + segments["segment_index"].astype(int).map("{:04d}".format)
    )

    # Ein Segment je Video: pro Video das nach stabilem Hash "kleinste"
    # Segment als Repraesentant waehlen. Deterministisch, unabhaengig
    # von SAMPLE_N.
    segments["_seg_hash"] = segments["segment_id"].map(stable_hash)
    representatives = (
        segments.sort_values("_seg_hash")
        .groupby("video_id", as_index=False)
        .first()
    )

    # Videos nach stabilem Hash ordnen und die kleinsten SAMPLE_N nehmen.
    # Nestbarkeit folgt direkt daraus: dieselbe Rangfolge fuer jedes N.
    representatives["_vid_hash"] = representatives["video_id"].map(stable_hash)
    representatives = representatives.sort_values("_vid_hash")

    n = min(SAMPLE_N, len(representatives))
    if n < SAMPLE_N:
        print(
            f"[sample] Nur {n} Videos verfuegbar, SAMPLE_N={SAMPLE_N} "
            "kann nicht voll ausgeschoepft werden."
        )
    drawn = representatives.head(n).copy()

    context_map = build_context_map(segments, SAMPLE_CONTEXT_WORDS)
    drawn["kontext"] = drawn.apply(
        lambda r: context_map.get((r["video_id"], r["segment_index"]), ""), axis=1
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    key_path = OUT_DIR / f"kodierung_schluessel_{n}.csv"
    workbook_path = OUT_DIR / f"kodierung_{n}.xlsx"

    drawn[["segment_id", "video_id", "segment_index"]].to_csv(
        key_path, index=False, encoding="utf-8-sig"
    )

    blind = drawn[["segment_id", "kontext", "text"]].rename(
        columns={"text": "segment_text"}
    )
    sheet_a = blind.sample(frac=1, random_state=hash(SAMPLE_SEED + "A") % (2**31)).reset_index(drop=True)
    sheet_b = blind.sample(frac=1, random_state=hash(SAMPLE_SEED + "B") % (2**31)).reset_index(drop=True)

    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        sheet_a.to_excel(writer, sheet_name="A", index=False)
        sheet_b.to_excel(writer, sheet_name="B", index=False)

    print(f"\n[sample] {n} Videos gezogen (aus {len(representatives):,} Kandidaten).")
    print(f"[sample] Kodierbogen : {workbook_path}")
    print(f"[sample] Schluessel  : {key_path}  (waehrend des Kodierens nicht oeffnen)")


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    if BEFEHL == "segmente":
        build_segments_file()
    elif BEFEHL == "sample":
        draw_sample()
    else:
        sys.exit(f"BEFEHL {BEFEHL!r} unbekannt. Erwartet 'segmente' oder 'sample'.")


if __name__ == "__main__":
    main()

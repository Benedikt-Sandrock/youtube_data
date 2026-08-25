"""
segment_transcripts.py
======================

Von den heruntergeladenen Transkript-JSONs zu (a) versandfertigen
Prompt-Payloads und (b) einem blinden Handkodier-Bogen.

    python segment_transcripts.py

Was passiert, steht im CONFIG-Block unter BEFEHL:

    "ids"       Liste der zu segmentierenden video_ids bauen (zuerst)
    "segment"   Transkripte einlesen und segmentieren, Cache schreiben
    "payloads"  Batch-Payloads aus dem Cache schreiben
    "sample"    SAMPLE_N Segmente zum Handkodieren ziehen
    "verify"    Belegzitate in RESULTS_FILE pruefen

Der Cache wird beim ersten Lauf automatisch angelegt; "segment" muss man nur
erneut ausfuehren, wenn neue Transkripte dazugekommen sind.

Die Handkodier-Stichprobe ist BLIND: keine Kanalnamen, keine Titel, keine
Treatment-Information, zufaellige Reihenfolge. Der Schluessel liegt in einer
separaten Datei, die man beim Kodieren nicht oeffnet. Wer beim Kodieren
weiss, ob ein Segment aus einem Kriegsvideo stammt, produziert keinen
Goldstandard, sondern eine Bestaetigung der eigenen Erwartung.

Die Ziehung ist ueber einen stabilen Hash genestet: `sample 300` enthaelt die
`sample 200` vollstaendig. Bereits kodierte Segmente bleiben gueltig.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd

from youtube_code.config import TRANSCRIPTS, EXTERNAL, OUTPUTS, SAMPLES

# ==========================================================================
# CONFIG
# ==========================================================================

# Woher die Transkripte kommen: "csv" (eine Tabelle) oder "dir" ({video_id}.json)
QUELLE         = "csv"
TRANSCRIPT_CSV = Path(TRANSCRIPTS / "all_transcripts_segments.csv")
TRANSCRIPT_DIR = Path("transcripts")          # nur fuer QUELLE = "dir"

# Spalten in TRANSCRIPT_CSV
COL_VIDEO_ID   = "video_id"
COL_TRANSCRIPT = "transcript_segments"
COL_STATUS     = "status"                     # None, wenn es keine gibt
STATUS_OK      = "OK"                         # Zeilen mit diesem Status zaehlen

VIDEO_TABLE    = Path(OUTPUTS / "sample_feasibility" / "videos_compact_pol_labels.csv")
TYPOLOGY       = Path(EXTERNAL / "media_type_russia_merged.xlsx")
OUTDIR         = SAMPLES / "russia" / "out_segments"

SEED = "segment-2026-v1"                      # NIE aendern (Nestbarkeit)

# Was dieser Lauf tun soll:
#   "ids" | "segment" | "payloads" | "sample" | "verify"
#   "ids"       Liste der zu segmentierenden video_ids bauen (zuerst!)
BEFEHL       = "sample"
SAMPLE_N     = 200                            # nur fuer BEFEHL = "sample"
RESULTS_FILE = Path("results.jsonl")          # nur fuer BEFEHL = "verify"
NEU_SEGMENTIEREN = False                      # True erzwingt Neuaufbau des Caches

# Grosse CSV: zeilenweise in Bloecken lesen, nie am Stueck.
# Speicherbedarf ~ CSV_CHUNKSIZE x Groesse einer Transkriptzelle.
# 500 x ~200 KB = ~100 MB. Bei sehr langen Videos eher 200 setzen.
CSV_CHUNKSIZE  = 500

# Nur diese Videos segmentieren. None = alle mit Status OK.
# Die Datei erzeugt BEFEHL = "ids".
VIDEO_ID_FILE  = Path("segment_ids.txt")

# Kriterien fuer BEFEHL = "ids"
IDS_NUR_KRIEG    = False                       # nur is_war_core == 1
IDS_MEDIENTYPEN  = ("OERR", "TRAD", "ALT", "PARTEI")
IDS_QUARTALE     = None                       # z.B. [(0, 2), (12, 14)]; None = alle

# Segmentierung
TARGET_WORDS   = 800     # Zielgroesse, ~5-6 Minuten Sprechzeit
SNAP_WINDOW    = 120     # Suchfenster fuer die naechste Satzgrenze
MIN_TAIL       = 250     # kuerzeres Reststueck wird angehaengt
CONTEXT_WORDS  = 80      # Kontext aus dem Vorsegment (wird nicht kodiert)
PAYLOAD_CHUNK  = 20000   # Segmente je Payload-Datei

# Handkodier-Stichprobe
STRATIFY_BY    = ["is_war", "label"]   # gleichmaessig ueber diese Zellen
DOPPELKODIERUNG = True   # zweiter Bogen, andere Reihenfolge, fuer Reliabilitaet

TYPE_LABELS = {1: "OERR", 2: "TRAD", 3: "ALT", 4: "PARTEI",
               5: "OERR_TEILW", 6: "SONSTIGES"}

# ==========================================================================
# Prompts (Stand: eingefrorene Fassung -- Aenderungen entwerten den Goldstandard)
# ==========================================================================

SYSTEM_P = """\
Du kodierst deutschsprachige politische Videotranskripte fuer die
sozialwissenschaftliche Forschung. Du arbeitest mit automatisch erzeugten
Transkripten: Eigennamen sind haeufig falsch geschrieben, Satzzeichen fehlen
oder sitzen falsch, einzelne Woerter sind verschluckt. Erschliesse die
Bedeutung aus dem Zusammenhang.

Die Transkripte enthalten oft mehrere Sprechende (Moderation, Gaeste) ohne
Kennzeichnung. Kodiere das Segment als Ganzes, so wie es der Kanal
veroeffentlicht hat -- unabhaengig davon, wer spricht.

Du bewertest die Form der Kommunikation, nicht ihren Wahrheitsgehalt und
nicht ihre politische Richtung. Linke und rechte Inhalte werden nach exakt
denselben Kriterien bewertet. Deine eigene Haltung zu den Aussagen ist
irrelevant.

Du gibst ausschliesslich ein JSON-Objekt aus, ohne Vorrede, ohne
Markdown-Codefence."""

# Der Kodierteil ist ausgelagert, damit Codebuch und Prompt nicht auseinanderlaufen.
CODEBOOK = (Path(__file__).parent / "codebook_populismus.txt")

USER_P_TEMPLATE = """\
{kontext_block}ZU KODIERENDES SEGMENT:
{segment}

---

{codebook}"""


def load_codebook() -> str:
    if not CODEBOOK.exists():
        sys.exit(f"Codebuch fehlt: {CODEBOOK}\n"
                 f"Den Abschnitt '### 1. volkszentrismus' bis zum Ausgabeformat "
                 f"aus prompts_klassifikation.md dort hineinkopieren.")
    return CODEBOOK.read_text(encoding="utf-8")


# ==========================================================================
# 1. Transkript einlesen und zu Text machen
# ==========================================================================

def _entries_to_text(data) -> str | None:
    """Liste von {start, duration, text} zu fortlaufendem Text.

    Die Zeitstempel ueberlappen (rollende Untertitel) -- ein Anzeigeartefakt,
    kein Duplikat. Zur Sicherheit wird trotzdem geprueft, ob ein Eintrag den
    Schluss des vorherigen woertlich wiederholt; manche Untertitelspuren tun das.
    """
    out: list[str] = []
    for entry in data:
        t = (entry.get("text") if isinstance(entry, dict) else str(entry)) or ""
        new_w = t.strip().split()
        if not new_w:
            continue
        for k in range(min(len(out), len(new_w), 20), 3, -1):
            if out[-k:] == new_w[:k]:
                new_w = new_w[k:]
                break
        out.extend(new_w)
    return " ".join(out) if len(out) >= 50 else None


def parse_transcript_cell(cell) -> str | None:
    """Nimmt eine Transkriptzelle und gibt fortlaufenden Text zurueck.

    Akzeptiert drei Formen, weil je nach Speicherweg eine andere ankommt:
      - JSON-Liste   '[{"start": 2.3, "text": "..."}]'
      - Python-Repr  "[{'start': 2.3, 'text': '...'}]"   (pandas-Standard)
      - reiner Text  bereits zusammengefuegt
    """
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return None
    if isinstance(cell, list):
        return _entries_to_text(cell)

    txt = str(cell).strip()
    if not txt:
        return None

    if txt[0] in "[{":
        data = None
        for parser in (json.loads, ast.literal_eval):
            try:
                data = parser(txt)
                break
            except (ValueError, SyntaxError, MemoryError):
                continue
        if isinstance(data, list):
            return _entries_to_text(data)
        if isinstance(data, dict):
            for k in ("segments", "transcript", "events", "text"):
                if isinstance(data.get(k), list):
                    return _entries_to_text(data[k])
                if isinstance(data.get(k), str):
                    txt = data[k]
                    break

    return txt if len(txt.split()) >= 50 else None


def transcript_to_text(path: Path) -> str | None:
    """Dateivariante fuer QUELLE = 'dir'."""
    try:
        return parse_transcript_cell(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None


def load_id_filter() -> set[str] | None:
    if VIDEO_ID_FILE is None or not VIDEO_ID_FILE.exists():
        return None
    ids = {l.strip() for l in VIDEO_ID_FILE.read_text(encoding="utf-8").splitlines()
           if l.strip()}
    print(f"[filter] {len(ids):,} video_ids aus {VIDEO_ID_FILE}")
    return ids


def iter_transcripts(video_ids: set[str] | None = None):
    """Liefert (video_id, text) -- streamend, nie die ganze Tabelle im Speicher."""
    if QUELLE == "dir":
        files = sorted(TRANSCRIPT_DIR.glob("*.json"))
        if video_ids is not None:
            files = [f for f in files if f.stem in video_ids]
        if not files:
            sys.exit(f"Keine Transkripte in {TRANSCRIPT_DIR}")
        print(f"[quelle] Verzeichnis {TRANSCRIPT_DIR}, {len(files)} Dateien")
        for f in files:
            yield f.stem, transcript_to_text(f)
        return

    if not TRANSCRIPT_CSV.exists():
        sys.exit(f"{TRANSCRIPT_CSV} nicht gefunden. QUELLE/Pfad pruefen.")

    cols = [COL_VIDEO_ID, COL_TRANSCRIPT]
    if COL_STATUS:
        cols.append(COL_STATUS)
    kopf = pd.read_csv(TRANSCRIPT_CSV, nrows=0)
    fehlend = [c for c in cols if c not in kopf.columns]
    if fehlend:
        sys.exit(f"Spalten fehlen in {TRANSCRIPT_CSV}: {fehlend}. "
                 f"Vorhanden: {list(kopf.columns)}")

    print(f"[quelle] {TRANSCRIPT_CSV}, Bloecke zu {CSV_CHUNKSIZE} Zeilen, "
          f"Spalten {cols}")
    gesehen: set[str] = set()
    status_zaehler: dict = {}
    n_zeilen = 0

    reader = pd.read_csv(TRANSCRIPT_CSV, usecols=cols,
                         chunksize=CSV_CHUNKSIZE, low_memory=False)
    for block in reader:
        n_zeilen += len(block)
        if COL_STATUS:
            for k, v in block[COL_STATUS].value_counts(dropna=False).items():
                status_zaehler[k] = status_zaehler.get(k, 0) + int(v)
            block = block[block[COL_STATUS] == STATUS_OK]
        if video_ids is not None:
            block = block[block[COL_VIDEO_ID].isin(video_ids)]
        for r in block.itertuples():
            vid = getattr(r, COL_VIDEO_ID)
            if vid in gesehen:
                continue
            gesehen.add(vid)
            yield vid, parse_transcript_cell(getattr(r, COL_TRANSCRIPT))

    print(f"[quelle] {n_zeilen:,} Zeilen gelesen")
    if status_zaehler:
        print("[quelle] Statusverteilung:")
        for k, v in sorted(status_zaehler.items(), key=lambda x: -x[1]):
            print(f"          {k}: {v:,}")


def build_ids() -> None:
    """Schreibt die Liste der zu segmentierenden video_ids.

    Vorschalten, bevor segmentiert wird: Es hat keinen Sinn, 20.000
    Transkripte zu zerlegen, wenn nur ein Teil in die Analyse geht.
    """
    if not VIDEO_TABLE.exists():
        sys.exit(f"{VIDEO_TABLE} fehlt -- ohne sie kann keine ID-Liste "
                 f"gebaut werden. VIDEO_ID_FILE = None setzen, um alle "
                 f"Transkripte mit Status OK zu nehmen.")
    v = pd.read_csv(VIDEO_TABLE)
    war = "is_war_core" if "is_war_core" in v.columns else "is_war"
    print(f"[ids] {len(v):,} Videos in {VIDEO_TABLE}")

    if IDS_NUR_KRIEG:
        v = v[v[war].fillna(0).astype(int) == 1]
        print(f"[ids]   nach Kriegsfilter: {len(v):,}")

    if IDS_QUARTALE and "time_delta" in v.columns:
        m = pd.Series(False, index=v.index)
        for a, b in IDS_QUARTALE:
            m |= v["time_delta"].between(a, b)
        v = v[m]
        print(f"[ids]   nach Quartalsfilter {IDS_QUARTALE}: {len(v):,}")

    if IDS_MEDIENTYPEN and TYPOLOGY.exists():
        t = pd.read_excel(TYPOLOGY).drop_duplicates(subset="channel_id")
        t["label"] = t["type"].astype(int).map(TYPE_LABELS)
        t = t[t["label"].isin(IDS_MEDIENTYPEN)]
        v = v[v["channel_id"].isin(set(t["channel_id"]))]
        print(f"[ids]   nach Medientyp {list(IDS_MEDIENTYPEN)}: {len(v):,}")

    ids = sorted(set(v["video_id"].astype(str)))
    ziel = VIDEO_ID_FILE or Path("segment_ids.txt")
    ziel.write_text("\n".join(ids), encoding="utf-8")
    print(f"[ids] {len(ids):,} video_ids -> {ziel}")
    print("[ids] Das sind Kandidaten. Wie viele davon ein Transkript haben, "
          "zeigt der naechste Lauf mit BEFEHL = 'segment'.")


# ==========================================================================
# 2. Segmentierung
# ==========================================================================

_SENT_END = re.compile(r"[.!?]$")


def split_segments(text: str,
                   target: int = TARGET_WORDS,
                   snap: int = SNAP_WINDOW,
                   min_tail: int = MIN_TAIL) -> list[str]:
    """Nach Wortzahl schneiden, auf die naechste Satzgrenze runden.

    Pausenbasierte Grenzen sind bei rollenden Untertiteln nicht verwendbar:
    Die Zeitabstaende folgen der Zeilenlaenge, nicht dem Sprechrhythmus.
    """
    w = text.split()
    if len(w) <= target + min_tail:
        return [text] if w else []

    cuts, pos = [], 0
    while pos + target + min_tail <= len(w):
        cand = pos + target
        best = None
        for off in range(0, snap + 1):                 # naechste Satzgrenze
            for c in (cand + off, cand - off):
                if pos < c < len(w) and _SENT_END.search(w[c - 1]):
                    best = c
                    break
            if best:
                break
        cut = best or cand
        cuts.append(cut)
        pos = cut

    segs, prev = [], 0
    for c in cuts:
        segs.append(" ".join(w[prev:c]))
        prev = c
    segs.append(" ".join(w[prev:]))
    return [s for s in segs if s.strip()]


SEG_FIELDS = ["video_id", "segment_nr", "segment_id", "n_woerter",
              "kontext", "segment"]


def build_segments(cache: Path, video_ids: set[str] | None = None) -> None:
    """Segmentiert streamend und schreibt Zeile fuer Zeile in den Cache.

    Sammelt bewusst nichts im Speicher: Bei 20.000 Videos entstehen rund
    100.000 Segmente zu je ~5 KB Text, das waeren einige hundert MB.
    """
    n_in = leer = n_seg = 0
    laengen: list[int] = []
    je_video: list[int] = []

    with cache.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SEG_FIELDS)
        w.writeheader()
        for vid, text in iter_transcripts(video_ids):
            n_in += 1
            if text is None:
                leer += 1
                continue
            segs = split_segments(text)
            je_video.append(len(segs))
            for i, seg in enumerate(segs):
                ctx = " ".join(segs[i - 1].split()[-CONTEXT_WORDS:]) if i else ""
                nw = len(seg.split())
                laengen.append(nw)
                w.writerow({"video_id": vid, "segment_nr": i,
                            "segment_id": f"{vid}__{i:03d}", "n_woerter": nw,
                            "kontext": ctx, "segment": seg})
                n_seg += 1
            if n_in % 2000 == 0:
                print(f"[segment]   ... {n_in:,} Transkripte, {n_seg:,} Segmente")

    print(f"[segment] {n_in:,} Transkripte gelesen, {leer:,} unbrauchbar "
          f"(leer, zu kurz oder nicht parsebar)")
    if not n_seg:
        sys.exit("[segment] Keine verwertbaren Transkripte -- COL_TRANSCRIPT "
                 "und das Zellformat pruefen.")
    q = pd.Series(laengen).quantile([.05, .5, .95]).round(0)
    print(f"[segment] {n_in - leer:,} Videos, {n_seg:,} Segmente")
    print(f"[segment] Woerter je Segment: p5={q.iloc[0]:.0f} "
          f"median={q.iloc[1]:.0f} p95={q.iloc[2]:.0f}")
    print(f"[segment] Segmente je Video: median="
          f"{pd.Series(je_video).median():.0f}")


# ==========================================================================
# 3. Metadaten anspielen
# ==========================================================================

def load_meta() -> pd.DataFrame | None:
    """Kleine Nachschlagetabelle video_id -> is_war, label, time_delta."""
    if not VIDEO_TABLE.exists():
        print(f"[meta] {VIDEO_TABLE} fehlt -- Stichprobe ohne Strata")
        return None
    v = pd.read_csv(VIDEO_TABLE)
    war = "is_war_core" if "is_war_core" in v.columns else "is_war"
    keep = ["video_id", "channel_id", war] + \
           (["time_delta"] if "time_delta" in v.columns else [])
    v = v[keep].rename(columns={war: "is_war"})
    v["is_war"] = v["is_war"].fillna(0).astype(int)
    if TYPOLOGY.exists():
        t = pd.read_excel(TYPOLOGY).drop_duplicates(subset="channel_id")
        t["label"] = t["type"].astype(int).map(TYPE_LABELS)
        v = v.merge(t[["channel_id", "label"]], on="channel_id", how="left")
    else:
        v["label"] = pd.NA
    return v


# ==========================================================================
# 4. Batch-Payloads
# ==========================================================================

def hkey(s: str) -> str:
    return hashlib.blake2b(f"{SEED}|{s}".encode(), digest_size=8).hexdigest()


def write_payloads(cache: Path, chunk_size: int = PAYLOAD_CHUNK) -> None:
    """Neutrales JSONL: item_id, system, user. Streamend aus dem Cache.

    Von hier in das Format deiner Batch-Pipeline umschreiben -- das
    Prompt-Rendering passiert an dieser einen Stelle, damit es nicht
    zweimal existiert.
    """
    cb = load_codebook()
    OUTDIR.mkdir(exist_ok=True)
    n = teil = 0
    fh = None
    try:
        for block in pd.read_csv(cache, chunksize=2000,
                                 keep_default_na=False, na_values=[""]):
            for r in block.itertuples():
                if n % chunk_size == 0:
                    if fh:
                        fh.close()
                    path = OUTDIR / f"payload_populismus_{teil:03d}.jsonl"
                    fh = path.open("w", encoding="utf-8")
                    teil += 1
                ctx = (f"VORHERGEHENDER KONTEXT (nicht bewerten, nur zum "
                       f"Verstaendnis):\n{r.kontext}\n\n") if r.kontext else ""
                fh.write(json.dumps({
                    "item_id": r.segment_id,
                    "system": SYSTEM_P,
                    "user": USER_P_TEMPLATE.format(kontext_block=ctx,
                                                   segment=r.segment,
                                                   codebook=cb),
                }, ensure_ascii=False) + "\n")
                n += 1
    finally:
        if fh:
            fh.close()
    print(f"[payload] {n:,} Segmente in {teil} Datei(en) "
          f"-> {OUTDIR}/payload_populismus_*.jsonl")
    print(f"[payload] Codebuch ist in jedem Item identisch -- "
          f"Prompt-Caching aktivieren, sonst zahlst du es {n:,} mal")


# ==========================================================================
# 5. Handkodier-Stichprobe (blind, genestet, stratifiziert)
# ==========================================================================

def draw_sample(cache: Path, n: int) -> pd.DataFrame:
    """Zieht n Segmente in zwei Durchgaengen.

    Durchgang 1 liest nur die Schluesselspalten und entscheidet, WELCHE
    Segmente gezogen werden. Durchgang 2 holt nur fuer diese den Text.
    So bleibt der Speicherbedarf unabhaengig von der Gesamtgroesse.

    Genestet ueber den Hash-Rang: eine spaetere groessere Ziehung enthaelt
    die kleinere vollstaendig.
    """
    keys = []
    for block in pd.read_csv(cache, usecols=["segment_id", "video_id"],
                             chunksize=50000):
        keys.append(block)
    k = pd.concat(keys, ignore_index=True)
    print(f"[sample] Grundgesamtheit: {len(k):,} Segmente aus "
          f"{k['video_id'].nunique():,} Videos")

    meta = load_meta()
    if meta is not None:
        k = k.merge(meta, on="video_id", how="left")

    k["hash"] = k["segment_id"].map(hkey)
    # hoechstens ein Segment je Video, sonst kodierst du dieselbe Sendung mehrfach
    k = k.sort_values("hash").groupby("video_id", as_index=False).head(1)
    k = k.sort_values("hash")

    strata = [c for c in STRATIFY_BY if c in k.columns and k[c].notna().any()]
    if strata:
        k["_z"] = k[strata].astype(str).agg("|".join, axis=1)
        k["rang"] = k.groupby("_z").cumcount()
        k = k[k["rang"] < -(-n // k["_z"].nunique())]
    sel = k.sort_values("hash").head(n)

    print(f"\n[sample] {len(sel)} Segmente gezogen")
    if len(sel) < n:
        print(f"[sample] WARNUNG: {n} angefordert. Begrenzend ist die Regel "
              f"'hoechstens ein Segment je Video'.")
    for c in strata:
        print(f"[sample] Verteilung {c}:")
        print(sel[c].value_counts().to_string())

    want = set(sel["segment_id"])
    teile = []
    for block in pd.read_csv(cache, chunksize=20000,
                             keep_default_na=False, na_values=[""]):
        hit = block[block["segment_id"].isin(want)]
        if len(hit):
            teile.append(hit)
    text = pd.concat(teile, ignore_index=True)
    out = sel.drop(columns=[c for c in ("_z", "rang") if c in sel.columns])
    return out.merge(text[["segment_id", "kontext", "segment"]],
                     on="segment_id", how="left")


def write_coding_workbook(sample: pd.DataFrame, n: int) -> None:
    """Blinder Kodierbogen + separater Schluessel."""
    OUTDIR.mkdir(exist_ok=True)

    # Schluessel: NICHT beim Kodieren oeffnen
    key_cols = [c for c in ["segment_id", "video_id", "channel_id", "label",
                            "is_war", "time_delta", "segment_nr"]
                if c in sample.columns]
    sample[key_cols].to_csv(OUTDIR / f"kodierung_schluessel_{n}.csv", index=False)

    def bogen(df: pd.DataFrame, seed_suffix: str) -> pd.DataFrame:
        d = df.copy()
        d["_ord"] = d["segment_id"].map(lambda x: hkey(x + seed_suffix))
        d = d.sort_values("_ord").reset_index(drop=True)
        out = pd.DataFrame({
            "lfd_nr": range(1, len(d) + 1),
            "segment_id": d["segment_id"],
            "kontext": d["kontext"],
            "segment": d["segment"],
        })
        for dim in ("volkszentrismus", "antielitismus",
                    "manichaeische_moralisierung", "emotionale_intensitaet"):
            out[f"{dim}_beleg"] = ""
            out[f"{dim}_wert"] = ""
        out["kodierbar"] = ""
        out["anmerkung"] = ""
        return out

    boegen = {"kodierung_A": bogen(sample, "|A")}
    if DOPPELKODIERUNG:
        boegen["kodierung_B"] = bogen(sample, "|B")

    path = OUTDIR / f"kodierung_{n}.xlsx"
    try:
        with pd.ExcelWriter(path, engine="openpyxl") as xw:
            for name, df in boegen.items():
                df.to_excel(xw, sheet_name=name, index=False)
                ws = xw.sheets[name]
                widths = {"C": 45, "D": 90}
                for col, wdt in widths.items():
                    ws.column_dimensions[col].width = wdt
                for col in ("A", "B"):
                    ws.column_dimensions[col].width = 16
                from openpyxl.styles import Alignment
                al = Alignment(wrap_text=True, vertical="top")
                for row in ws.iter_rows(min_row=2):
                    for cell in row:
                        cell.alignment = al
                ws.freeze_panes = "E2"
        print(f"[sample] -> {path}")
    except ImportError:
        for name, df in boegen.items():
            df.to_csv(OUTDIR / f"{name}_{n}.csv", index=False)
        print(f"[sample] openpyxl fehlt -- CSV statt xlsx geschrieben")

    print(f"[sample] Schluessel -> {OUTDIR}/kodierung_schluessel_{n}.csv "
          f"(beim Kodieren NICHT oeffnen)")
    if DOPPELKODIERUNG:
        print("[sample] Blatt kodierung_B enthaelt dieselben Segmente in "
              "anderer Reihenfolge -- fuer den zweiten Kodierenden oder fuer "
              "deine eigene Zweitkodierung mit mindestens zwei Wochen Abstand")


# ==========================================================================
# 6. Belegzitate pruefen (nach dem LLM-Rueckla|uf)
# ==========================================================================

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9äöüß ]", " ", s.lower())


def verify(results_path: Path, cache: Path) -> pd.DataFrame:
    """Prueft, ob jedes Belegzitat woertlich im Segment steht.

    Billigster verfuegbarer Halluzinationsindikator. Trefferquote unter
    95 Prozent heisst: Prompt nachschaerfen, nicht hochskalieren.
    """
    text: dict[str, str] = {}
    for block in pd.read_csv(cache, usecols=["segment_id", "segment"],
                             chunksize=20000, keep_default_na=False,
                             na_values=[""]):
        text.update(zip(block["segment_id"], block["segment"].map(_norm)))
    dims = ("volkszentrismus", "antielitismus",
            "manichaeische_moralisierung", "emotionale_intensitaet")
    rows = []
    with results_path.open(encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            sid = r.get("item_id")
            body = r.get("result") if isinstance(r.get("result"), dict) else r
            src = text.get(sid, "")
            for d in dims:
                block = (body or {}).get(d) or {}
                beleg = block.get("beleg")
                rows.append({
                    "segment_id": sid, "dimension": d,
                    "wert": block.get("wert"),
                    "hat_beleg": bool(beleg),
                    "beleg_gefunden": bool(beleg) and _norm(beleg) in src,
                })
    v = pd.DataFrame(rows)
    mit = v[v["hat_beleg"]]
    print(f"\n[verify] {len(v):,} Bewertungen, {len(mit):,} mit Beleg")
    if len(mit):
        print(f"[verify] Trefferquote gesamt: "
              f"{mit['beleg_gefunden'].mean():.1%}")
        print(mit.groupby("dimension")["beleg_gefunden"].mean()
                 .round(3).to_string())
    print("\n[verify] Verteilung der Werte (Ziel: nicht >60 % auf 2/3)")
    print(pd.crosstab(v["dimension"], v["wert"], normalize="index").round(3)
            .to_string())
    korr = (v.pivot_table(index="segment_id", columns="dimension",
                          values="wert").corr().round(2))
    print("\n[verify] Korrelation der Dimensionen")
    print(korr.to_string())
    return v


# ==========================================================================

def _cache_path() -> Path:
    return OUTDIR / "segmente.csv"


def main() -> None:
    erlaubt = ("ids", "segment", "payloads", "sample", "verify")
    if BEFEHL not in erlaubt:
        sys.exit(f"BEFEHL '{BEFEHL}' unbekannt. Erlaubt: {', '.join(erlaubt)}")

    OUTDIR.mkdir(exist_ok=True)
    print(f"[lauf] BEFEHL = {BEFEHL}")

    if BEFEHL == "ids":
        build_ids()
        return

    cache = _cache_path()
    if BEFEHL == "segment" or NEU_SEGMENTIEREN or not cache.exists():
        if BEFEHL != "segment" and not NEU_SEGMENTIEREN:
            print(f"[cache] {cache} fehlt -- wird jetzt aufgebaut")
        build_segments(cache, load_id_filter())
        print(f"[cache] -> {cache}")
        if BEFEHL == "segment":
            return

    if BEFEHL == "payloads":
        write_payloads(cache)
    elif BEFEHL == "sample":
        write_coding_workbook(draw_sample(cache, SAMPLE_N), SAMPLE_N)
    elif BEFEHL == "verify":
        if not RESULTS_FILE.exists():
            sys.exit(f"RESULTS_FILE nicht gefunden: {RESULTS_FILE}")
        verify(RESULTS_FILE, cache)


if __name__ == "__main__":
    main()
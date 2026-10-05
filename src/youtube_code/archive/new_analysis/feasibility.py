#!/usr/bin/env python3
"""
yt_feasibility.py — Streaming-Pipeline fuer das Ukraine/Populismus-Projekt.

Verarbeitet die grosse videos.jsonl zeilenweise (nie komplett im RAM) und
beantwortet die Feasibility-Frage fuer das Within-Channel-Design:

    Wie viele Kanal-Quartale enthalten sowohl Keyword- als auch Kontrollvideos?

Stufen (einzeln oder per 'all' aufrufbar):

  1. inspect      Schema, Kennzahlen, Wertebereiche. Immer zuerst laufen lassen.
  2. boilerplate  Lernt kanalweise konstante Beschreibungsbausteine
                  (Spendenblöcke, Hashtag-Ketten, Abo-Aufrufe).
  3. extract      Streamt die JSONL -> kompakte Video-Tabelle mit Keyword-Flags
                  auf Titel und BEREINIGTER Beschreibung. Ohne Volltexte.
  4. feasibility  Rechnet die Design-Tabellen aus der kompakten Tabelle.

Beispiel:
    python yt_feasibility.py all --jsonl videos.jsonl --outdir ./out

Benoetigt: pandas. Optional: pyarrow (Parquet statt CSV), orjson (ca. 2-3x
schnelleres Parsen), tqdm (Fortschrittsbalken). Alle drei sind ersetzbar.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from youtube_code.config import RAW, SAMPLES, OUTPUTS

try:
    import orjson

    def loads(b):
        return orjson.loads(b)
except ImportError:
    def loads(b):
        return json.loads(b)

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(it, **kw):
        return it


# ---------------------------------------------------------------------------
# KONFIGURATION — hier anpassen
# ---------------------------------------------------------------------------

JSONL_PATH = SAMPLES / "russia" / "sample_50k_channels_russia_ukraine_wo_shorts.jsonl"
OUTDIR     = OUTPUTS / "sample_feasibility"
COMMAND    = "all"      # inspect | boilerplate | extract | feasibility | all
LIMIT      = None           # None für die ganze Datei

# Invasionsdatum. Bestimmt period=0.
INVASION = datetime(2022, 2, 24, tzinfo=timezone.utc)

INTERVAL_START = -12
# Feldnamen in der JSONL. Links = interner Name, rechts = Name in deiner Datei.
FIELDS = {
    "video_id": "video_id",
    "channel_id": "channel_id",
    "channel_title": "channel_title",
    "published_at": "published_at",
    "title": "title",
    "description": "description",
    "politics": "politics_classification",
    "period": "time_delta",  # None -> wird aus published_at berechnet
}

# Ein Beschreibungs-Absatz gilt als Boilerplate, wenn er bei >= diesem Anteil
# der gepruefen Videos eines Kanals vorkommt.
BOILERPLATE_THRESHOLD = 0.60
# Nur so viele Videos pro Kanal zum Lernen der Boilerplate heranziehen.
BOILERPLATE_SAMPLE_PER_CHANNEL = 300
# Absaetze unter dieser Laenge werden beim Lernen ignoriert (Leerzeilen etc.).
BOILERPLATE_MIN_LEN = 12

# --- Keyword-Sets ----------------------------------------------------------
# WICHTIG: Deutsche Komposita machen Teilstring-Matching meist richtig
# ("ukrain" faengt Ukraine/ukrainisch/Ukrainer). Bei kurzen, mehrdeutigen
# Stems brauchst du Wortgrenzen — "krim" wuerde sonst "Kriminalitaet" fangen,
# "nato" wuerde in Eigennamen zuschlagen. Genau solche Treffer haben im
# CSV-Sample Fehlalarme erzeugt.

KEYWORDS = {
    # Enger Kern: praktisch nur Kriegskontext. Das ist die Hauptdefinition.
    "ukr_core": r"""
        ukrain | selensk | zelensk | wolodymyr
        | kyjiw | kyiw | \bkiew\b | charkiw | mariupol | bachmut | cherson
        | donbas | donezk | luhansk | saporischschja
        | butscha | asow | wagner
    """,
    # Erweitert: Russland/Krieg allgemein. Hohe Recall, niedrigere Precision.
    "ukr_wide": r"""
        russland | russisch | russische[nrms]? | putin | kreml | \bmoskau\b
        | \bkrim\b | krimhalbinsel
        | waffenlieferung | panzerlieferung | \bleopard\b | \btaurus\b
        | ringtausch | kriegsverbrech | ostfront | frontverlauf
    """,
    # Bewusst getrennt: politisch relevant, aber NICHT kriegsspezifisch.
    # Nie in die Treatment-Definition aufnehmen, nur zur Diagnose.
    "ukr_risky": r"""
        \bnato\b | \bkrieg\b | sanktion | aufruesten | aufrüsten | \beu\b
    """,
    # Placebo-Themen fuer den Vergleichstest (siehe Analyseplan).
    "corona": r"""
        corona | covid | pandemie | lockdown | impf | maskenpflicht | inzidenz
        | rki | \b2g\b | \b3g\b
    """,
    "migration": r"""
        migration | migrant | fluechtling | flüchtling | asyl | abschieb
        | geflucht | geflüchtet | zuwander | remigration | grenzschutz
    """,
    "energie": r"""
        energiepreis | gaspreis | strompreis | inflation | heizung
        | nord\s*stream | atomkraft | kernkraft | energiewende
    """,
}


def _compile(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE | re.VERBOSE)


KW_RE = {k: _compile(v) for k, v in KEYWORDS.items()}


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def open_maybe_gzip(path: str):
    """Oeffnet .jsonl oder .jsonl.gz transparent, binaer, gepuffert."""
    if str(path).endswith(".gz"):
        return io.BufferedReader(gzip.open(path, "rb"), buffer_size=1 << 20)
    return open(path, "rb", buffering=1 << 20)


def iter_jsonl(path: str, limit: int | None = None):
    """Streamt die JSONL Zeile fuer Zeile. Defekte Zeilen werden gezaehlt,
    nicht geworfen — bei API-Dumps gibt es fast immer ein paar."""
    bad = 0
    with open_maybe_gzip(path) as fh:
        for i, raw in enumerate(fh):
            if limit is not None and i >= limit:
                break
            raw = raw.strip()
            if not raw:
                continue
            try:
                yield loads(raw)
            except Exception:
                bad += 1
                if bad <= 5:
                    print(f"  ! Zeile {i} nicht parsebar", file=sys.stderr)
    if bad:
        print(f"  ! insgesamt {bad} defekte Zeilen uebersprungen", file=sys.stderr)


def get(rec: dict, key: str):
    """Feldzugriff ueber das FIELDS-Mapping."""
    src = FIELDS.get(key)
    return rec.get(src) if src else None


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def months_since_invasion(dt: datetime) -> int:
    """Ganze Monate seit Feb 2022. Konsistent mit deinem 'time_delta'."""
    return (dt.year - INVASION.year) * 12 + (dt.month - INVASION.month)


def interval_of(period: int) -> tuple[int, str]:
    """3-Monats-Bucket, identisch zur Logik im CSV-Sample.
    period -12 -> index 0, label '-12_to_-10'."""
    idx = (period + 12) // 3
    start = idx * 3 - 12
    return idx, f"{start}_to_{start + 2}"


def split_paragraphs(desc: str) -> list[str]:
    """Beschreibung in Absaetze/Zeilen zerlegen und normalisieren."""
    if not desc:
        return []
    return [ln.strip() for ln in desc.replace("\r", "\n").split("\n") if ln.strip()]


def line_hash(s: str) -> str:
    return hashlib.blake2b(s.encode("utf-8", "ignore"), digest_size=8).hexdigest()


# ---------------------------------------------------------------------------
# Stufe 1: inspect
# ---------------------------------------------------------------------------

def cmd_inspect(args):
    """Schema und Kennzahlen. Bestaetigt, dass das FIELDS-Mapping stimmt."""
    n = 0
    key_counts = Counter()
    channels = set()
    politics = Counter()
    periods = []
    dates = []
    no_desc = 0
    sample = None

    for rec in tqdm(iter_jsonl(args.jsonl, args.limit), desc="inspect", unit=" rec"):
        n += 1
        if sample is None:
            sample = rec
        key_counts.update(rec.keys())
        ch = get(rec, "channel_id")
        if ch:
            channels.add(ch)
        politics[get(rec, "politics")] += 1
        if not get(rec, "description"):
            no_desc += 1
        p = get(rec, "period")
        if p is not None:
            periods.append(int(p))
        dt = parse_ts(get(rec, "published_at"))
        if dt:
            dates.append(dt)

    print(f"\n{'=' * 62}\nSCHEMA & KENNZAHLEN\n{'=' * 62}")
    print(f"Zeilen gesamt      : {n:,}")
    print(f"Kanaele            : {len(channels):,}")
    print(f"ohne Beschreibung  : {no_desc:,} ({no_desc / max(n, 1):.1%})")
    if dates:
        print(f"Zeitraum           : {min(dates).date()} bis {max(dates).date()}")
    if periods:
        print(f"period (time_delta): {min(periods)} bis {max(periods)}")
        i0, l0 = interval_of(min(periods))
        i1, l1 = interval_of(max(periods))
        print(f"  -> Intervalle    : {i0} ({l0}) bis {i1} ({l1})")

    print("\nFelder (Anteil der Zeilen, in denen der Schluessel vorkommt):")
    for k, c in key_counts.most_common():
        flag = "  <- gemappt" if k in FIELDS.values() else ""
        print(f"  {k:28s} {c / max(n, 1):7.1%}{flag}")

    missing = [k for k, v in FIELDS.items() if v and v not in key_counts]
    if missing:
        print(f"\n  !! FIELDS-Mapping zeigt auf nicht vorhandene Felder: {missing}")
        print("     Bitte FIELDS oben im Skript korrigieren.")

    print("\npolitics_classification:")
    for k, c in politics.most_common():
        print(f"  {str(k):10s} {c:>10,} ({c / max(n, 1):6.1%})")

    if sample:
        print("\nBeispielsatz (Beschreibung gekuerzt):")
        s = dict(sample)
        if s.get(FIELDS["description"]):
            s[FIELDS["description"]] = s[FIELDS["description"]][:200] + " ..."
        print(json.dumps(s, ensure_ascii=False, indent=2)[:1400])


# ---------------------------------------------------------------------------
# Stufe 2: boilerplate
# ---------------------------------------------------------------------------

def cmd_boilerplate(args):
    """Lernt pro Kanal die konstanten Beschreibungsbausteine.

    Ohne diesen Schritt wird jede Keyword-Suche auf der Beschreibung
    unbrauchbar: Kanaele mit fixen Hashtag-Ketten (#NeinZumKrieg o.ae.)
    wuerden zu 100% als Kriegskanal gelten.
    """
    seen = Counter()                       # channel_id -> geprueft
    counts = defaultdict(Counter)          # channel_id -> {line_hash: n}
    texts = {}                             # line_hash -> Klartext (fuer Report)

    for rec in tqdm(iter_jsonl(args.jsonl, args.limit), desc="boilerplate", unit=" rec"):
        ch = get(rec, "channel_id")
        if not ch or seen[ch] >= BOILERPLATE_SAMPLE_PER_CHANNEL:
            continue
        seen[ch] += 1
        for ln in split_paragraphs(get(rec, "description") or ""):
            if len(ln) < BOILERPLATE_MIN_LEN:
                continue
            h = line_hash(ln)
            counts[ch][h] += 1
            if h not in texts:
                texts[h] = ln[:160]

    boiler = {}
    for ch, c in counts.items():
        n = seen[ch]
        if n < 3:
            continue
        hs = [h for h, k in c.items() if k / n >= BOILERPLATE_THRESHOLD]
        if hs:
            boiler[ch] = hs

    out = Path(args.outdir) / "boilerplate.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(boiler), encoding="utf-8")

    total = sum(len(v) for v in boiler.values())
    print(f"\n{len(boiler):,} von {len(seen):,} Kanaelen mit Boilerplate, "
          f"{total:,} Bausteine -> {out}")

    # Nur die Bausteine zeigen, die Keyword-Fehlalarme erzeugen wuerden.
    print("\nBoilerplate MIT Kriegs-Keywords (haette Fehlalarme erzeugt):")
    shown = 0
    for ch, hs in boiler.items():
        for h in hs:
            t = texts.get(h, "")
            if any(KW_RE[k].search(t) for k in ("ukr_core", "ukr_wide", "ukr_risky")):
                print(f"  [{ch}] {t}")
                shown += 1
                if shown >= 25:
                    print("  ... (gekuerzt)")
                    return
    if not shown:
        print("  keine gefunden")


# ---------------------------------------------------------------------------
# Stufe 3: extract
# ---------------------------------------------------------------------------

OUT_COLS = [
    "video_id", "channel_id", "channel_title", "published_at",
    "period", "interval_index", "interval_label", "politics",
    "desc_missing", "desc_chars_raw", "desc_chars_clean",
] + [f"{k}_title" for k in KEYWORDS] + [f"{k}_desc" for k in KEYWORDS]


def cmd_extract(args):
    """Streamt die JSONL in eine kompakte Video-Tabelle.

    Keyword-Flags werden getrennt fuer Titel und bereinigte Beschreibung
    berechnet — genau diese Trennung macht die Kontamination sichtbar.
    """
    bp_path = Path(args.outdir) / "boilerplate.json"
    boiler = {}
    if bp_path.exists():
        boiler = {k: set(v) for k, v in json.loads(bp_path.read_text()).items()}
        print(f"Boilerplate fuer {len(boiler):,} Kanaele geladen")
    else:
        print("! boilerplate.json fehlt — Beschreibungs-Flags sind unbereinigt.")

    out_path = Path(args.outdir) / "videos_compact.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n = n_period_derived = 0
    n_skipped = 0
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_COLS)
        w.writeheader()

        for rec in tqdm(iter_jsonl(args.jsonl, args.limit), desc="extract", unit=" rec"):
            ch = get(rec, "channel_id")
            dt = parse_ts(get(rec, "published_at"))

            period = get(rec, "period")
            if period is None:
                if dt is None:
                    continue
                period = months_since_invasion(dt)
                n_period_derived += 1
            period = int(period)
            if period < INTERVAL_START:
                n_skipped += 1
                continue
            idx, label = interval_of(period)

            title = get(rec, "title") or ""
            desc_raw = get(rec, "description") or ""

            # Boilerplate entfernen
            lines = split_paragraphs(desc_raw)
            drop = boiler.get(ch, set())
            desc = "\n".join(ln for ln in lines if line_hash(ln) not in drop)

            row = {
                "video_id": rec.get(FIELDS["video_id"]),
                "channel_id": ch,
                "channel_title": get(rec, "channel_title"),
                "published_at": dt.isoformat() if dt else None,
                "period": period,
                "interval_index": idx,
                "interval_label": label,
                "politics": get(rec, "politics"),
                "desc_missing": int(not desc_raw),
                "desc_chars_raw": len(desc_raw),
                "desc_chars_clean": len(desc),
            }
            for k, rx in KW_RE.items():
                row[f"{k}_title"] = int(bool(rx.search(title)))
                row[f"{k}_desc"] = int(bool(rx.search(desc)))
            w.writerow(row)
            n += 1

    print(f"\n{n:,} Videos -> {out_path}")
    if n_period_derived:
        print(f"  ({n_period_derived:,} mal period aus published_at abgeleitet)")


# ---------------------------------------------------------------------------
# Stufe 4: feasibility
# ---------------------------------------------------------------------------

def cmd_feasibility(args):
    import pandas as pd

    path = Path(args.outdir) / "videos_compact.csv"
    df = pd.read_csv(path)
    print(f"{len(df):,} Videos, {df.channel_id.nunique():,} Kanaele\n")

    # --- Treatment-Definitionen ------------------------------------------
    # eng   = so, wie du es bisher machst (Titel)
    # weit  = Titel oder bereinigte Beschreibung
    df["treat_title"] = (df.ukr_core_title | df.ukr_wide_title).astype(int)
    df["treat_wide"] = (df.treat_title | df.ukr_core_desc | df.ukr_wide_desc).astype(int)

    # --- 0. Kontrolle der Boilerplate-Regel -------------------------------
    # Wenn ein Kanal wenig Beschreibungsvielfalt hat, kann die Regel echten
    # Inhalt wegwerfen. Kanaele mit sehr hoher Strip-Rate manuell pruefen.
    has = df.desc_chars_raw > 0
    strip = 1 - df.loc[has, "desc_chars_clean"].sum() / df.loc[has, "desc_chars_raw"].sum()
    per_ch_strip = (1 - df[has].groupby("channel_id").desc_chars_clean.sum()
                    / df[has].groupby("channel_id").desc_chars_raw.sum())
    print("=" * 62)
    print("0. BOILERPLATE-DIAGNOSE")
    print("=" * 62)
    print(f"Entfernter Beschreibungstext gesamt : {strip:.1%}")
    print(f"Kanaele mit >80% entferntem Text    : {(per_ch_strip > 0.8).sum():,}"
          "   <- pruefen, dort wird evtl. echter Inhalt geloescht")
    if (per_ch_strip > 0.8).any():
        print("  " + ", ".join(per_ch_strip[per_ch_strip > 0.8].index[:8]))

    # --- 1. Kontamination -------------------------------------------------
    print("\n" + "=" * 62)
    print("1. KONTAMINATION DER KONTROLLGRUPPE")
    print("=" * 62)
    ctrl = df[df.treat_title == 0]
    print(f"Videos ohne Keyword im Titel : {len(ctrl):,}")
    print(f"davon Kriegsbezug in Beschr. : {ctrl.treat_wide.sum():,} "
          f"({ctrl.treat_wide.mean():.1%})\n")

    bands = [(-12, -1, "vor Invasion"), (0, 11, "Monat 0-11"),
             (12, 23, "Monat 12-23"), (24, 200, "Monat 24+")]
    print(f"{'Zeitraum':<16}{'Kontrollvideos':>16}{'kontaminiert':>16}{'Rate':>9}")
    for lo, hi, lab in bands:
        s = ctrl[(ctrl.period >= lo) & (ctrl.period <= hi)]
        if len(s):
            print(f"{lab:<16}{len(s):>16,}{s.treat_wide.sum():>16,}{s.treat_wide.mean():>9.1%}")

    # --- 2. Kernzahl ------------------------------------------------------
    print("\n" + "=" * 62)
    print("2. KANAL-QUARTALE MIT BEIDEN VIDEOTYPEN")
    print("=" * 62)
    print("Nur diese Zellen identifizieren den Within-Channel-Effekt.\n")

    for name, col in [("Treatment = Titel", "treat_title"),
                      ("Treatment = Titel+Beschr.", "treat_wide")]:
        d = df[df.period >= 0]
        cell = d.groupby(["channel_id", "interval_index"]).agg(
            n_treat=(col, "sum"), n_total=(col, "size")).reset_index()
        cell["n_ctrl"] = cell.n_total - cell.n_treat
        both = cell[(cell.n_treat > 0) & (cell.n_ctrl > 0)]
        print(f"{name}")
        print(f"  Zellen gesamt          : {len(cell):,}")
        print(f"  davon mit beiden Typen : {len(both):,} ({len(both) / max(len(cell), 1):.1%})")
        print(f"  beitragende Kanaele    : {both.channel_id.nunique():,}")
        print(f"  Videos in diesen Zellen: {both.n_total.sum():,} "
              f"({both.n_treat.sum():,} Treatment / {both.n_ctrl.sum():,} Kontrolle)\n")

    # --- 3. Verteilung ueber Kanaele --------------------------------------
    d = df[df.period >= 0]
    cell = d.groupby(["channel_id", "interval_index"]).agg(
        n_treat=("treat_wide", "sum"), n_total=("treat_wide", "size")).reset_index()
    cell["n_ctrl"] = cell.n_total - cell.n_treat
    both = cell[(cell.n_treat > 0) & (cell.n_ctrl > 0)]
    per_ch = both.groupby("channel_id").size()
    print("=" * 62)
    print("3. WIE VIELE BRAUCHBARE QUARTALE PRO KANAL?")
    print("=" * 62)
    print("Kanaele mit ...")
    for k in [1, 2, 4, 8, 12]:
        print(f"  >= {k:2d} Quartalen : {(per_ch >= k).sum():,}")
    if len(per_ch):
        print(f"  Median          : {per_ch.median():.0f}")

    # --- 4. Placebo-Themen ------------------------------------------------
    print("\n" + "=" * 62)
    print("4. PLACEBO-THEMEN (Vergleichsmassstab)")
    print("=" * 62)
    print("Ein Ukraine-Effekt ist nur dann substanziell, wenn er sich von\n"
          "diesen Themen abhebt. Genug Videos fuer den Test?\n")
    for t in ["corona", "migration", "energie"]:
        flag = (df[f"{t}_title"] | df[f"{t}_desc"]).astype(int)
        c = df.assign(f=flag).groupby(["channel_id", "interval_index"]).f.agg(["sum", "size"])
        n_both = ((c["sum"] > 0) & (c["size"] - c["sum"] > 0)).sum()
        print(f"  {t:<10} {flag.sum():>8,} Videos   {n_both:>6,} nutzbare Zellen")

    # --- 5. Optionale Joins ----------------------------------------------
    if args.transcripts:
        tr = pd.read_csv(args.transcripts)
        idcol = "video_id"
        df2 = df.merge(tr[[idcol] + [c for c in tr.columns if c != idcol]],
                       on=idcol, how="left")
        avail = [c for c in df2.columns if "avail" in c.lower() or "transcript" in c.lower()]
        print("\n" + "=" * 62)
        print("5. TRANSKRIPT-VERFUEGBARKEIT NACH VIDEOTYP")
        print("=" * 62)
        print("Differenzielle Verfuegbarkeit = Selektion auf dem Treatment.\n")
        for c in avail:
            g = df2.groupby("treat_wide")[c].mean()
            print(f"  {c}: Kontrolle {g.get(0, float('nan')):.1%} | "
                  f"Treatment {g.get(1, float('nan')):.1%}")

    out = Path(args.outdir) / "cell_counts.csv"
    cell.to_csv(out, index=False)
    print(f"\nZell-Tabelle -> {out}")


# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("cmd", nargs="?", default=COMMAND,
                   choices=["inspect", "boilerplate", "extract",
                            "feasibility", "all"])
    p.add_argument("--jsonl", default=str(JSONL_PATH))
    p.add_argument("--outdir", default=str(OUTDIR))
    p.add_argument("--limit", type=int, default=LIMIT)
    p.add_argument("--transcripts", default=None)
    a = p.parse_args()

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Effektive Parameter mitschreiben (siehe unten).
    (outdir / "run_config.json").write_text(json.dumps({
        "cmd": a.cmd,
        "jsonl": str(a.jsonl),
        "limit": a.limit,
        "invasion": INVASION.isoformat(),
        "boilerplate_threshold": BOILERPLATE_THRESHOLD,
        "keywords": KEYWORDS,
        "executed_at": datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Eingabe : {a.jsonl}")
    print(f"Ausgabe : {outdir}")
    print(f"Limit   : {a.limit}")

    steps = {"inspect": cmd_inspect, "boilerplate": cmd_boilerplate,
             "extract": cmd_extract, "feasibility": cmd_feasibility}
    order = (["inspect", "boilerplate", "extract", "feasibility"]
             if a.cmd == "all" else [a.cmd])
    for s in order:
        print(f"\n{'#' * 62}\n# {s.upper()}\n{'#' * 62}")
        steps[s](a)

if __name__ == "__main__":
    main()
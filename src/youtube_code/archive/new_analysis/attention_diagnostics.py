#!/usr/bin/env python3
"""
attention_diagnostics.py — Stufe A des Analyseplans (v2).

Beantwortet ohne Transkripte und ohne LLM-Kosten die Frage:
Gibt es Dynamiken, deren Analyse sich lohnt?

Stufen:
  compare    Stellt die Kennzahlen mehrerer Laeufe nebeneinander
             (Dauerfilter x Kohorte).
  clean      Lernt kanalweise Boilerplate und schreibt EINMAL eine bereinigte
             Kopie der JSONL. Alle spaeteren Laeufe lesen diese Kopie.
  extract    Bereinigte JSONL -> videos_rich.csv (Engagement, Dauer, Titelstil)
  diagnose   Rechnet A1-A7
  all        clean -> extract -> diagnose

Analysen:
  A0  Dauerfilter-Diagnose      Was wuerde ein 180s-Filter entfernen, und
                                trifft er Treatment und Kontrolle gleich?
  B0  Kohorten                  Wer war beim Kriegsbeginn aktiv? Trennt
                                Verhaltens- von Kompositionsaenderung.
  B2  Neuzugaenge               Unterscheiden sich spaeter gestartete
                                Kanaele von den Etablierten?
  A1  Aufmerksamkeitskurve      Gibt es den Schock?
  A2  Abklingheterogenitaet     Reagieren Kanaele UNTERSCHIEDLICH?
  A3  Varianzzerlegung (ICC)    Kanaltypen oder Nachrichtenzyklus?
                                Liefert den Design-Effekt fuer die Power-Rechnung.
  A4  Engagement                Kriegsvideos vs. andere Videos DESSELBEN Kanals,
                                inkl. Selektionspruefung und Kreuzung mit A2.
  A5  Titelstil                 Kostenloser Vortest auf Stilunterschiede.
  A6  topic_categories          Externe, modellunabhaengige Validierung.
  A7  Datenqualitaet            Was ist ueberhaupt auswertbar?

Benoetigt: pandas, numpy. Optional: orjson, tqdm, matplotlib.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import orjson
    def loads(b): return orjson.loads(b)
    def dumps(o): return orjson.dumps(o)
except ImportError:
    def loads(b): return json.loads(b)
    def dumps(o): return json.dumps(o, ensure_ascii=False).encode("utf-8")

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(it, **kw): return it


# ---------------------------------------------------------------------------
# KONFIGURATION
# ---------------------------------------------------------------------------

JSONL_PATH = r"/data/samples/russia/sample_50k_channels_russia_ukraine_wo_shorts.jsonl"
OUTDIR     = r"C:\Users\bened\PycharmProjects\youtube_data\outputs\sample_feasibility"
COMMAND    = "compare"          # clean | extract | diagnose | all
LIMIT      = None

# Bereinigte Kopie der JSONL. Wird von 'clean' geschrieben und danach von
# 'extract' gelesen. Auf None setzen, um immer die Rohdatei zu verwenden.
CLEAN_JSONL = "videos_clean.jsonl"
CLEAN_GZIP = False          # True spart ~70% Platz, kostet etwas Lesezeit
FORCE_CLEAN = False         # True erzwingt Neuberechnung trotz vorhandener Datei

# ACHTUNG: auf das Datum setzen, an dem die Metadaten abgerufen wurden.
SCRAPE_DATE = datetime(2026, 7, 1, tzinfo=timezone.utc)

INTERVAL_START = -12
INTERVAL_SIZE = 3

# Monat -1 (24.01.-23.02.2022) liegt bereits dreifach ueber dem Vorniveau:
# der antizipierte Aufmarsch. Er gehoert NICHT in die Baseline.
PRE_WINDOW = (-12, -2)
SHOCK_WINDOW = (0, 5)
MID_WINDOW = (6, 23)
LATE_WINDOW = (24, 60)

MIN_PER_GROUP = 3           # Videos je Gruppe fuer den gepaarten Vergleich
MIN_VIDEOS_CHANNEL = 30     # Mindestzahl fuer die Kanal-Trajektorien
MIN_VIDEOS_WINDOW = 10      # Mindestzahl je Fenster fuer eine gueltige Rate
MIN_CELL_N = 5              # Videos je Kanal-Quartal fuer die ICC
SHORTS_SECONDS = 60         # Schwelle fuer die Shorts-Pruefung

# --- Dauerfilter -----------------------------------------------------------
# None  = alle Videos (Referenzlauf)
# 180   = nur Langform. Bewusst KEIN Shorts-Filter: 'Short' ist eine
#         Plattformkategorie, deren Definition im Oktober 2024 von 60 auf
#         180 Sekunden wechselte. Eine feste Dauerschwelle ist ueber den
#         ganzen Zeitraum dieselbe Operationalisierung — in einem Laengs-
#         schnitt ist das der entscheidende Vorteil.
#
# Zweimal laufen lassen (None und 180); die Ausgabedateien bekommen das
# Suffix automatisch, dann 'compare' fuer die Gegenueberstellung.
MIN_DURATION_S = 180

# Videos ohne Dauerangabe beim aktiven Filter behalten oder verwerfen.
KEEP_MISSING_DURATION = False

# --- Kohorten --------------------------------------------------------------
# Die A1-Kurve mischt sonst Verhaltens- und Kompositionsaenderung: ab Monat 20
# stehen immer mehr Kanaele im Nenner, die den Schock nie erlebt haben.
#
# etabliert  = mindestens COHORT_PRE_MIN_VIDEOS Uploads im Vorfenster
# Neuzugang  = erster Upload im Sample ab Monat 0
# sporadisch = existierte vorher, aber zu wenige Uploads im Vorfenster
COHORT_PRE_MIN_VIDEOS = 10

# None        = alle Kohorten (Referenzlauf)
# "etabliert" = balanciertes Panel fuer den Vorher-Nachher-Vergleich
COHORT_RESTRICT = "etabliert"

# Gemeinsames Spaetfenster fuer den Kohortenvergleich. Neuzuganege haben kein
# Vorfenster, also ist ein Zeitraum noetig, in dem beide Kohorten praesent sind.
COHORT_COMPARE_WINDOW = (24, 60)

BOILERPLATE_THRESHOLD = 0.60
BOILERPLATE_SAMPLE_PER_CHANNEL = 300
BOILERPLATE_MIN_LEN = 12

FIELDS = {
    "video_id": "video_id",
    "channel_id": "channel_id",
    "channel_title": "channel_title",
    "published_at": "published_at",
    "title": "title",
    "description": "description",
    "duration": "duration",
    "views": "view_count",
    "likes": "like_count",
    "comments": "comment_count",
    "live": "live_broadcast_content",
    "topics": "topic_categories",
    "lang": "default_language",
}

# Zusatzfeld, das 'clean' in die bereinigte Kopie schreibt.
RAW_LEN_FIELD = "description_chars_raw"

# Muster sind bereits kleingeschrieben; der Text wird einmal per .lower()
# normalisiert. Das ist deutlich schneller als re.IGNORECASE pro Suche.
KEYWORDS = {
    "ukr_core": r"""
        ukrain | selensk | zelensk | wolodymyr
        | kyjiw | kyiw | \bkiew\b | charkiw | mariupol | bachmut | cherson
        | donbas | donezk | luhansk | saporischschja
        | butscha | asow | wagner
    """,
    "ukr_wide": r"""
        russland | russisch | russische[nrms]? | putin | kreml | \bmoskau\b
        | \bkrim\b | krimhalbinsel
        | waffenlieferung | panzerlieferung | \bleopard\b | \btaurus\b
        | ringtausch | kriegsverbrech | ostfront | frontverlauf
    """,
    "corona": r"""
        corona | covid | pandemie | lockdown | impf | maskenpflicht
        | inzidenz | \brki\b | \b2g\b | \b3g\b
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
KW_RE = {k: re.compile(v, re.VERBOSE) for k, v in KEYWORDS.items()}

INVASION = datetime(2022, 2, 24, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def period_of(dt: datetime) -> int:
    """Monate seit dem 24.02.2022, verankert auf Tag 24.

    Periode 0 = 24.02.2022 bis 23.03.2022. Identisch zu 'time_delta'
    (geprueft: 2026-01-30 -> 47, 2021-01-01 -> -14).
    Diese Funktion gehoert projektweit in genau EINE Datei.
    """
    p = (dt.year - INVASION.year) * 12 + (dt.month - INVASION.month)
    if dt.day < INVASION.day:
        p -= 1
    return p


def interval_of(period: int) -> int:
    return (period - INTERVAL_START) // INTERVAL_SIZE


DUR_RE = re.compile(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
                    re.IGNORECASE)


def duration_seconds(s):
    if not s:
        return None
    m = DUR_RE.fullmatch(str(s).strip())
    if not m:
        return None
    d, h, mi, sec = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + sec


CAPS_WORD = re.compile(r"\b[A-ZÄÖÜ]{3,}\b")


def title_style(title: str) -> dict:
    """Deutsch schreibt Substantive gross, ein Grossbuchstaben-ANTEIL waere
    also unbrauchbar. Stattdessen komplett grossgeschriebene Woerter — die
    Betonungskonvention in zugespitzten Titeln."""
    return {
        "n_excl": title.count("!"),
        "n_quest": title.count("?"),
        "n_caps_words": len(CAPS_WORD.findall(title)),
        "title_chars": len(title),
        "title_words": len(title.split()),
    }


def to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def open_read(path):
    if str(path).endswith(".gz"):
        return io.BufferedReader(gzip.open(path, "rb"), buffer_size=1 << 20)
    return open(path, "rb", buffering=1 << 20)


def open_write(path):
    if str(path).endswith(".gz"):
        return gzip.open(path, "wb", compresslevel=5)
    return open(path, "wb", buffering=1 << 20)


def iter_jsonl(path, limit=None):
    bad = 0
    with open_read(path) as fh:
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
    if bad:
        print(f"  ! {bad} defekte Zeilen uebersprungen", file=sys.stderr)


def g(rec, key):
    src = FIELDS.get(key)
    return rec.get(src) if src else None


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def line_hash(s):
    return hashlib.blake2b(s.encode("utf-8", "ignore"), digest_size=8).digest()


def split_paragraphs(desc):
    if not desc:
        return []
    return [l.strip() for l in desc.replace("\r", "\n").split("\n") if l.strip()]


def clean_path(outdir) -> Path | None:
    if not CLEAN_JSONL:
        return None
    name = CLEAN_JSONL + (".gz" if CLEAN_GZIP and not CLEAN_JSONL.endswith(".gz")
                          else "")
    return Path(outdir) / name


# ---------------------------------------------------------------------------
# Stufe: clean
# ---------------------------------------------------------------------------

def cmd_clean(args):
    """Lernt Boilerplate und schreibt eine bereinigte Kopie der JSONL.

    Laeuft EINMAL. Danach lesen alle Analysen die bereinigte Datei, was das
    zeilenweise Hashing aus jedem weiteren Durchlauf entfernt.

    Die Kopie behaelt alle Originalfelder; 'description' ist ersetzt, die
    urspruengliche Laenge bleibt in einem Zusatzfeld erhalten.
    """
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    target = clean_path(outdir)
    if target is None:
        print("CLEAN_JSONL = None — Bereinigung uebersprungen.")
        return

    if target.exists() and not FORCE_CLEAN:
        print(f"Bereinigte Datei existiert bereits: {target}")
        print("  FORCE_CLEAN = True setzen, um sie neu zu berechnen.")
        return

    # --- Durchlauf 1: Boilerplate lernen ---------------------------------
    print("Durchlauf 1/2: kanalweise Boilerplate lernen")
    seen = Counter()
    counts = defaultdict(Counter)
    texts = {}
    for rec in tqdm(iter_jsonl(args.jsonl, args.limit), desc="lernen", unit=" rec"):
        ch = g(rec, "channel_id")
        if not ch or seen[ch] >= BOILERPLATE_SAMPLE_PER_CHANNEL:
            continue
        seen[ch] += 1
        for ln in split_paragraphs(g(rec, "description") or ""):
            if len(ln) < BOILERPLATE_MIN_LEN:
                continue
            h = line_hash(ln)
            counts[ch][h] += 1
            texts.setdefault(h, ln[:160])

    boiler = {}
    for ch, c in counts.items():
        n = seen[ch]
        if n < 3:
            continue
        hs = {h for h, k in c.items() if k / n >= BOILERPLATE_THRESHOLD}
        if hs:
            boiler[ch] = hs
    print(f"  {len(boiler):,} von {len(seen):,} Kanaelen mit Boilerplate, "
          f"{sum(len(v) for v in boiler.values()):,} Bausteine")

    # Bausteine mit Kriegs-Keywords zeigen — die waeren Fehlalarme.
    hits = [(ch, texts[h]) for ch, hs in boiler.items() for h in hs
            if any(rx.search(texts.get(h, "").lower())
                   for k, rx in KW_RE.items() if k.startswith("ukr"))]
    print(f"  davon mit Kriegs-Keywords: {len(hits)}")
    for ch, t in hits[:10]:
        print(f"    [{ch}] {t}")

    # --- Durchlauf 2: bereinigt schreiben ---------------------------------
    print(f"\nDurchlauf 2/2: bereinigte Kopie schreiben -> {target}")
    desc_field = FIELDS["description"]
    n = 0
    removed_chars = kept_chars = 0
    with open_write(target) as out:
        for rec in tqdm(iter_jsonl(args.jsonl, args.limit), desc="schreiben",
                        unit=" rec"):
            raw = rec.get(desc_field) or ""
            drop = boiler.get(g(rec, "channel_id"))
            if drop:
                cleaned = "\n".join(l for l in split_paragraphs(raw)
                                    if line_hash(l) not in drop)
            else:
                cleaned = raw
            rec[desc_field] = cleaned
            rec[RAW_LEN_FIELD] = len(raw)
            removed_chars += len(raw) - len(cleaned)
            kept_chars += len(cleaned)
            out.write(dumps(rec) + b"\n")
            n += 1

    tot = removed_chars + kept_chars
    print(f"\n{n:,} Zeilen geschrieben.")
    print(f"Entfernter Beschreibungstext: {removed_chars / max(tot, 1):.1%}")

    meta = {
        "source": str(args.jsonl),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "boilerplate_threshold": BOILERPLATE_THRESHOLD,
        "boilerplate_sample_per_channel": BOILERPLATE_SAMPLE_PER_CHANNEL,
        "boilerplate_min_len": BOILERPLATE_MIN_LEN,
        "channels_with_boilerplate": len(boiler),
        "removed_share": removed_chars / max(tot, 1),
        "rows": n,
    }
    (outdir / "videos_clean_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Stufe: extract
# ---------------------------------------------------------------------------

OUT_COLS = [
    "video_id", "channel_id", "channel_title", "published_at",
    "period", "interval_index", "age_days",
    "duration_s", "is_live", "lang", "topic_political", "topic_n",
    "views", "likes", "comments",
    "n_excl", "n_quest", "n_caps_words", "title_chars", "title_words",
    "desc_chars_raw", "desc_chars_clean",
] + [f"{k}_title" for k in KEYWORDS] + [f"{k}_desc" for k in KEYWORDS]


def cmd_extract(args):
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    src = clean_path(outdir)
    if src and src.exists():
        print(f"Lese bereinigte Datei: {src}")
    else:
        src = args.jsonl
        print(f"! Bereinigte Datei fehlt — lese Rohdatei: {src}")
        print("  ('clean' zuerst laufen lassen; Beschreibungs-Flags sind sonst")
        print("   von Boilerplate wie Spendenblöcken oder Hashtag-Ketten verzerrt.)")

    out = outdir / "videos_rich.csv"
    n = 0
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_COLS)
        w.writeheader()
        for rec in tqdm(iter_jsonl(src, args.limit), desc="extract", unit=" rec"):
            dt = parse_ts(g(rec, "published_at"))
            if dt is None:
                continue
            title = g(rec, "title") or ""
            desc = g(rec, "description") or ""
            # einmal normalisieren statt IGNORECASE pro Suche
            title_l, desc_l = title.lower(), desc.lower()

            topics = g(rec, "topics") or []
            if isinstance(topics, str):
                topics = [topics]
            p = period_of(dt)

            row = {
                "video_id": g(rec, "video_id"),
                "channel_id": g(rec, "channel_id"),
                "channel_title": g(rec, "channel_title"),
                "published_at": dt.isoformat(),
                "period": p,
                # Zeitreihen nutzen ALLE Perioden; nur zellbasierte Analysen
                # brauchen ein Intervall.
                "interval_index": interval_of(p) if p >= INTERVAL_START else "",
                "age_days": (SCRAPE_DATE - dt).days,
                "duration_s": duration_seconds(g(rec, "duration")),
                "is_live": int((g(rec, "live") or "none") != "none"),
                "lang": g(rec, "lang"),
                "topic_political": int(any(
                    t.rsplit("/", 1)[-1] in ("Politics", "Society")
                    for t in topics)),
                "topic_n": len(topics),
                "views": to_int(g(rec, "views")),
                "likes": to_int(g(rec, "likes")),
                "comments": to_int(g(rec, "comments")),
                "desc_chars_raw": rec.get(RAW_LEN_FIELD, len(desc)),
                "desc_chars_clean": len(desc),
                **title_style(title),
            }
            for k, rx in KW_RE.items():
                row[f"{k}_title"] = int(bool(rx.search(title_l)))
                row[f"{k}_desc"] = int(bool(rx.search(desc_l)))
            w.writerow(row)
            n += 1
    print(f"\n{n:,} Videos -> {out}")


# ---------------------------------------------------------------------------
# Stufe: diagnose
# ---------------------------------------------------------------------------

def run_tag() -> str:
    """Kennung des Laufs. Haengt an allen Ausgabedateien, damit sich die
    Varianten (Dauerfilter x Kohorte) nicht ueberschreiben."""
    dur = "all" if MIN_DURATION_S is None else f"dur{MIN_DURATION_S}"
    return dur if COHORT_RESTRICT is None else f"{dur}_{COHORT_RESTRICT}"


def assign_cohorts(df, pd, np):
    """Ordnet jedem Kanal eine Eintrittskohorte zu.

    Grundlage ist die Upload-Aktivitaet, nicht das Kanalgruendungsdatum —
    letzteres steht nicht in den Daten, und fuer die Frage 'war der Kanal
    beim Kriegsbeginn beobachtbar' ist Aktivitaet ohnehin das Richtige.
    """
    per = df.groupby("channel_id").period
    first, last = per.min(), per.max()
    pre_n = (df[(df.period >= PRE_WINDOW[0]) & (df.period <= PRE_WINDOW[1])]
             .groupby("channel_id").size()
             .reindex(first.index).fillna(0).astype(int))

    coh = pd.DataFrame({
        "first_period": first, "last_period": last, "pre_videos": pre_n,
        "n_videos": df.groupby("channel_id").size(),
    })
    coh["kohorte"] = np.select(
        [coh.pre_videos >= COHORT_PRE_MIN_VIDEOS, coh.first_period >= 0],
        ["etabliert", "Neuzugang"],
        default="sporadisch",
    )
    return coh


def hdr(t):
    print("\n" + "=" * 70 + f"\n{t}\n" + "=" * 70)


def sign_share(d):
    """Anteil positiver Differenzen OHNE Gleichstaende.

    Bei Zaehlmerkmalen, die meist 0 sind (Ausrufezeichen etc.), sind sehr
    viele Zellen unentschieden. Wuerde man Gleichstaende als negativ zaehlen,
    laege der Anteil systematisch unter 50%, ohne dass das etwas bedeutet.
    """
    d = d.dropna()
    d = d[d != 0]
    return (d > 0).mean() if len(d) else float("nan"), len(d)


def cmd_diagnose(args):
    import numpy as np
    import pandas as pd

    outdir = Path(args.outdir)
    df = pd.read_csv(outdir / "videos_rich.csv")

    df["treat"] = (df.ukr_core_title | df.ukr_wide_title
                   | df.ukr_core_desc | df.ukr_wide_desc).astype(int)
    df["treat_title_only"] = (df.ukr_core_title | df.ukr_wide_title).astype(int)

    print(f"{len(df):,} Videos, {df.channel_id.nunique():,} Kanaele, "
          f"period {df.period.min()} bis {df.period.max()}")

    S = {"tag": run_tag(), "min_duration_s": MIN_DURATION_S}   # Kennzahlen-Sammler

    # ================================================================= A0
    # Laeuft IMMER, auch ohne aktiven Filter — die Diagnose sagt dir, ob der
    # Filter ueberhaupt unschaedlich waere.
    hdr("A0  DAUERFILTER-DIAGNOSE")
    thr = MIN_DURATION_S or 180
    short = df.duration_s < thr
    print(f"Schwelle fuer die Diagnose: {thr}s"
          f"   (Filter aktiv: {'ja' if MIN_DURATION_S else 'nein'})\n")

    # (1) Der kritische Punkt: trifft der Filter beide Gruppen gleich?
    #     Ungleiche Entfernung = Selektion auf dem Treatment.
    r = df.groupby("treat").apply(lambda s: (s.duration_s < thr).mean())
    d0, d1 = r.get(0, float("nan")), r.get(1, float("nan"))
    print(f"Anteil unter {thr}s:")
    print(f"  Kontrollvideos : {d0:.1%}")
    print(f"  Kriegsvideos   : {d1:.1%}")
    print(f"  Differenz      : {d1 - d0:+.1%}", end="")
    print("   <- >3pp waere Selektion auf dem Treatment"
          if abs(d1 - d0) > 0.03 else "   (unauffaellig)")
    S["short_share_control"], S["short_share_treat"] = float(d0), float(d1)

    # (2) Zeitverlauf: der Oktober-2024-Bruch muesste hier sichtbar werden.
    _q = pd.to_datetime(df.published_at, utc=True, format="mixed"
                        ).dt.tz_convert(None).dt.to_period("Q")
    pq = df.assign(short=short).groupby(_q).short.mean()
    print(f"\nAnteil unter {thr}s je Quartal (letzte 10):")
    for k, v in pq.tail(10).items():
        print(f"  {k}   {v:6.1%}  {'#' * int(v * 60)}")

    # (3) Verlierst du ganze Kanaele?
    per_ch = df.assign(short=short).groupby("channel_id").short.mean()
    long_n = df[~short].groupby("channel_id").size()
    lost = df.channel_id.nunique() - long_n.reindex(
        df.channel_id.unique()).fillna(0).gt(0).sum()
    thin = (long_n.reindex(df.channel_id.unique()).fillna(0)
            < MIN_VIDEOS_CHANNEL).sum()
    print(f"\nKanaele mit >70% Kurzvideos            : {(per_ch > 0.7).sum():,}")
    print(f"Kanaele ohne ein einziges Langvideo    : {int(lost):,}")
    print(f"Kanaele unter {MIN_VIDEOS_CHANNEL} Langvideos          : {int(thin):,}"
          "   <- fallen aus A2 heraus")
    S["channels_mostly_short"] = int((per_ch > 0.7).sum())
    S["channels_lost"] = int(lost)
    S["channels_thin"] = int(thin)

    # --- Filter anwenden --------------------------------------------------
    if MIN_DURATION_S is not None:
        before = len(df)
        keep = df.duration_s >= MIN_DURATION_S
        if KEEP_MISSING_DURATION:
            keep = keep | df.duration_s.isna()
        df = df[keep].copy()
        print(f"\nFILTER AKTIV: {before - len(df):,} von {before:,} Videos "
              f"entfernt ({1 - len(df) / before:.1%}).")
        print(f"Verbleiben {len(df):,} Videos in "
              f"{df.channel_id.nunique():,} Kanaelen.")
    else:
        print("\nKein Filter aktiv — Referenzlauf ueber alle Videos.")

    S["n_videos"], S["n_channels"] = len(df), int(df.channel_id.nunique())

    # ================================================================= B0
    hdr("B0  KOHORTEN — wer war beim Kriegsbeginn ueberhaupt da?")
    print("Die Aufmerksamkeitskurve mischt sonst zwei Dinge: Kanaele aendern")
    print("ihr Verhalten UND die Zusammensetzung der Stichprobe aendert sich.")
    print("Ohne diese Trennung ist der Abfall nach dem Peak nicht deutbar.\n")

    coh = assign_cohorts(df, pd, np)
    df = df.merge(coh[["kohorte"]], left_on="channel_id", right_index=True,
                  how="left")

    print(f"{'Kohorte':<14}{'Kanaele':>9}{'Videos':>12}"
          f"{'Median 1. Monat':>17}")
    for k, g_ in coh.groupby("kohorte"):
        print(f"{k:<14}{len(g_):>9,}{int(g_.n_videos.sum()):>12,}"
              f"{g_.first_period.median():>17.0f}")
    S["cohorts"] = {k: int(v) for k, v in coh.kohorte.value_counts().items()}

    # Wann treten Neuzugaenge ein? Ein Peak kurz nach der Invasion waere
    # substanziell interessant: kriegsgetriebene Kanalgruendung.
    ent = coh[coh.kohorte == "Neuzugang"]
    if len(ent):
        print(f"\nEintritt der {len(ent):,} Neuzugaenge (erster Upload):")
        bins = [(0, 5, "Mon 0-5"), (6, 11, "Mon 6-11"), (12, 23, "Mon 12-23"),
                (24, 35, "Mon 24-35"), (36, 99, "Mon 36+")]
        for lo, hi, lab in bins:
            m = int(((ent.first_period >= lo) & (ent.first_period <= hi)).sum())
            print(f"  {lab:<12}{m:>5,}  {'#' * int(m / max(len(ent), 1) * 50)}")

    # Kompositionseffekt sichtbar machen: dieselbe Kurve je Kohorte.
    ch_m0 = (df.groupby(["channel_id", "period", "kohorte"])
               .agg(n=("treat", "size"), k=("treat", "sum")).reset_index())
    ch_m0["share"] = ch_m0.k / ch_m0.n
    print("\nKriegsanteil je Kohorte und Fenster (Mittel ueber Kanaele):")
    print(f"{'Kohorte':<14}{'Mon 0-5':>10}{'Mon 6-23':>10}{'Mon 24+':>10}")
    for k, gk in ch_m0.groupby("kohorte"):
        vals = []
        for lo, hi in [SHOCK_WINDOW, MID_WINDOW, LATE_WINDOW]:
            sub = gk[(gk.period >= lo) & (gk.period <= hi)]
            vals.append(sub.share.mean() if len(sub) else float("nan"))
        print(f"{k:<14}" + "".join(f"{v:>10.1%}" for v in vals))
    print("\n  Liegen die Neuzugaenge im Spaetfenster unter den Etablierten,")
    print("  erklaert Komposition einen Teil des Abfalls in A1 — nicht nur")
    print("  nachlassendes Interesse der einzelnen Kanaele.")

    coh.to_csv(outdir / f"B0_cohorts_{run_tag()}.csv")

    # --- Kohortenrestriktion ---------------------------------------------
    df_all = df.copy()   # B2 braucht spaeter beide Kohorten
    if COHORT_RESTRICT is not None:
        before = len(df)
        df = df[df.kohorte == COHORT_RESTRICT].copy()
        print(f"\nKOHORTE AKTIV: nur '{COHORT_RESTRICT}' — "
              f"{len(df):,} von {before:,} Videos, "
              f"{df.channel_id.nunique():,} Kanaele.")
        print("  Balanciertes Panel: alle Kanaele sind vor UND nach dem")
        print("  Schock beobachtet, Komposition damit konstant.")
        S["n_videos"], S["n_channels"] = len(df), int(df.channel_id.nunique())
    else:
        print("\nKeine Kohortenrestriktion — alle Kanaele.")

    # ================================================================= A7
    hdr("A7  DATENQUALITAET — was ist ueberhaupt auswertbar?")
    for c in ["views", "likes", "comments", "duration_s"]:
        print(f"  {c:12s} fehlt bei {df[c].isna().sum():>8,} "
              f"({df[c].isna().mean():.1%})")

    print(f"\n  Likes = 0 trotz >1000 Views : "
          f"{((df.likes == 0) & (df.views > 1000)).sum():,}"
          "   <- ausgeblendet, nicht null")
    print(f"  Livestreams                 : {df.is_live.sum():,} "
          f"({df.is_live.mean():.1%})")

    # Shorts-Pruefung: der Dateiname verspricht 'wo_shorts', p10 lag aber
    # bei 76 Sekunden. Falls der Filter ueber URL/Tag lief statt ueber die
    # Dauer, sind kurze Videos noch enthalten.
    print("\n  Dauer-Verteilung (Shorts-Pruefung):")
    d_ok = df.duration_s.dropna()
    for lo, hi, lab in [(0, 60, "< 60 s"), (60, 90, "60-90 s"),
                        (90, 180, "90-180 s"), (180, 10 ** 9, "> 180 s")]:
        m = ((d_ok >= lo) & (d_ok < hi)).sum()
        print(f"    {lab:<10}{m:>9,} ({m / len(d_ok):6.1%})")
    n_short = (d_ok < SHORTS_SECONDS).sum()
    if n_short:
        print(f"    -> {n_short:,} Videos unter {SHORTS_SECONDS}s trotz "
              "'wo_shorts' im Dateinamen. Filter pruefen.")

    print("\n  Sprache (default_language):")
    for v, c in df.lang.fillna("(fehlt)").value_counts().head(6).items():
        print(f"    {str(v):<10}{c:>9,} ({c / len(df):6.1%})")
    n_nonde = (df.lang.notna() & (df.lang != "de")).sum()
    print(f"    -> {n_nonde:,} Videos mit gesetzter Sprache != 'de'. "
          "Der Sprachfilter lief auf KANALebene.")

    # ================================================================= A1
    hdr("A1  AUFMERKSAMKEITSKURVE — gibt es den Schock?")
    print("Ungewichteter Mittelwert UEBER KANAELE, damit produktive Kanaele")
    print("die Kurve nicht dominieren.\n")

    ch_m = (df.groupby(["channel_id", "period"])
              .agg(n=("treat", "size"), k=("treat", "sum")).reset_index())
    ch_m["share"] = ch_m.k / ch_m.n
    curve = ch_m.groupby("period").agg(
        kanaele=("channel_id", "nunique"),
        mean_share=("share", "mean"),
        median_share=("share", "median"),
        anteil_aktiv=("share", lambda s: (s > 0).mean()),
    ).reset_index()

    show = curve[(curve.period >= -6) & (curve.period <= 30)]
    print(f"{'Monat':>6}{'Kanaele':>9}{'Mittel':>9}{'Median':>9}{'>0':>7}   Verlauf")
    for _, r in show.iterrows():
        bar = "#" * int(round(r.mean_share * 120))
        print(f"{int(r.period):>6}{int(r.kanaele):>9}{r.mean_share:>9.1%}"
              f"{r.median_share:>9.1%}{r.anteil_aktiv:>7.0%}   {bar}")
    curve.to_csv(outdir / f"A1_attention_curve_{run_tag()}.csv", index=False)

    def wmean(lo, hi):
        s = curve[(curve.period >= lo) & (curve.period <= hi)]
        return s.mean_share.mean()

    pre = wmean(*PRE_WINDOW)
    anticip = wmean(-1, -1)
    post = curve[curve.period >= 0]
    peak = post.mean_share.max()
    peak_m = int(post.loc[post.mean_share.idxmax(), "period"])
    late = wmean(*LATE_WINDOW)
    print(f"\n  Baseline (Monat {PRE_WINDOW[0]} bis {PRE_WINDOW[1]}) : {pre:.2%}")
    print(f"  Monat -1 (Aufmarsch, separat)      : {anticip:.2%}"
          f"   = {anticip / max(pre, 1e-9):.1f}x Baseline")
    print(f"  Peak                               : {peak:.2%} in Monat {peak_m}")
    print(f"  ab Monat {LATE_WINDOW[0]}                       : {late:.2%}")
    print(f"  Peak / Baseline                    : {peak / max(pre, 1e-9):.1f}x")
    print(f"  spaet / Peak                       : {late / max(peak, 1e-9):.1%}")
    S.update(baseline=float(pre), anticip=float(anticip), peak=float(peak),
             peak_month=peak_m, late=float(late),
             peak_over_baseline=float(peak / max(pre, 1e-9)),
             late_over_peak=float(late / max(peak, 1e-9)))
    print("\n  'Anteil >0' = Kanaele mit mindestens einem Kriegsvideo im Monat.")
    print("  Klafft er weit vom Mittelwert, traegt eine Minderheit die Kurve.")

    # ================================================================= A2
    hdr("A2  ABKLINGHETEROGENITAET — reagieren Kanaele unterschiedlich?")
    print("Ist die Streuung klein, gibt es nichts zu erklaeren.\n")

    def win(d, w):
        s = d[(d.period >= w[0]) & (d.period <= w[1])]
        tot = s.n.sum()
        # Unter der Schwelle ist die Rate zu verrauscht: bei 2 Videos sind
        # nur 0, 0.5 und 1 moeglich. Solche Werte gehoeren nicht in eine
        # Quantiltabelle -> als 'nicht beobachtet' behandeln.
        return s.k.sum() / tot if tot >= MIN_VIDEOS_WINDOW else np.nan

    rows = []
    for cid, d in ch_m.groupby("channel_id"):
        rows.append({
            "channel_id": cid,
            "n_videos": int(d.n.sum()),
            "pre": win(d, PRE_WINDOW),
            "shock": win(d, SHOCK_WINDOW),
            "mid": win(d, MID_WINDOW),
            "late": win(d, LATE_WINDOW),
        })
    ch = pd.DataFrame(rows)
    ch = ch[ch.n_videos >= MIN_VIDEOS_CHANNEL].copy()
    ch["persistence"] = ch.late / ch.shock.replace(0, np.nan)

    print(f"Kanaele mit >= {MIN_VIDEOS_CHANNEL} Videos: {len(ch):,}\n")
    print(f"{'Fenster':<12}{'p10':>8}{'p25':>8}{'Median':>8}{'p75':>8}{'p90':>8}")
    for c, lab in [("pre", "Baseline"), ("shock", "Mon 0-5"),
                   ("mid", "Mon 6-23"), ("late", "Mon 24+")]:
        q = ch[c].quantile([.1, .25, .5, .75, .9])
        print(f"{lab:<12}" + "".join(f"{v:>8.1%}" for v in q))

    print(f"\nStreuung im Schockfenster: SD = {ch.shock.std():.3f}, "
          f"p10-p90 = {ch.shock.quantile(.9) - ch.shock.quantile(.1):.1%}")
    S.update(a2_channels=len(ch), shock_sd=float(ch.shock.std()),
             shock_p10_p90=float(ch.shock.quantile(.9) - ch.shock.quantile(.1)),
             shock_median=float(ch.shock.median()))

    # Jeder Vergleich mit NaN ergibt False. Mit verschachtelten np.where
    # fielen Kanaele ohne Schockfenster-Beobachtung deshalb still in den
    # else-Zweig und wurden als 'schwach' etikettiert — obwohl sie 2022
    # gar nicht aktiv waren. np.select macht die Faelle flach und sichtbar.
    observed = ch.shock.notna()
    n_unobs = int((~observed).sum())
    if n_unobs:
        print(f"\nOhne verwertbare Beobachtung im Schockfenster: {n_unobs:,}")
        print(f"  (2022 nicht aktiv oder unter {MIN_VIDEOS_WINDOW} Uploads)")

    thr = ch.loc[observed, "shock"].median()
    # Persistenz ist bei winzigem Nenner instabil: 0.02/0.03 = 0.67 waere
    # 'dauerhaft', obwohl beide Werte Rauschen sind.
    stable = ch.shock >= 0.05

    ch["typ"] = np.select(
        [~observed,
         ch.shock < 0.02,
         stable & (ch.persistence.fillna(0) >= 0.5),
         ch.shock >= thr],
        ["nicht beobachtet", "kaum Reaktion", "dauerhaft",
         "Spitze, dann Abfall"],
        default="schwach",
    )
    print("\nTypologie:")
    for t, c in ch.typ.value_counts().items():
        print(f"  {t:<22}{c:>5,} ({c / len(ch):5.1%})")

    n_nonreact = int((ch.typ == "kaum Reaktion").sum())
    n_unobs2 = int((ch.typ == "nicht beobachtet").sum())
    usable = len(ch) - n_nonreact - n_unobs2
    print(f"\n  {n_nonreact:,} Kanaele ohne Reaktion tragen zum Within-Channel-")
    print(f"  Kontrast nichts bei; {n_unobs2:,} sind im Schockfenster nicht")
    print(f"  beobachtet und haben keinen Vorher-Nachher-Vergleich.")
    print(f"  Effektive Stichprobe fuer Frage (b): rund {usable:,} "
          f"von {len(ch):,} Kanaelen.")
    S["a2_unobserved"] = n_unobs2
    S["a2_usable"] = int(usable)
    S["typology"] = {k: int(v) for k, v in ch.typ.value_counts().items()}
    ch.to_csv(outdir / f"A2_channel_trajectories_{run_tag()}.csv", index=False)
    print(f"\n  -> A2_channel_trajectories_{run_tag()}.csv (Stratifizierung)")

    # ================================================================= A3
    hdr("A3  VARIANZZERLEGUNG — Kanaltypen oder Nachrichtenzyklus?")
    print("ICC = Anteil der Varianz ZWISCHEN Kanaelen.\n")

    q = df[df.period >= 0].groupby(["channel_id", "interval_index"]).agg(
        n=("treat", "size"), k=("treat", "sum")).reset_index()
    q = q[q.n >= MIN_CELL_N].copy()
    q["share"] = q.k / q.n

    # (1) Gemeinsamen Zeittrend entfernen. Der Kriegsanteil faellt bei ALLEN
    #     Kanaelen; das ist ein geteilter Schock, keine kanalindividuelle
    #     Schwankung, wuerde aber sonst die Innerhalb-Varianz aufblaehen.
    q["resid"] = q.share - q.groupby("interval_index").share.transform("mean")

    gm = q.groupby("channel_id").resid.agg(["mean", "size"])
    J, N = len(gm), len(q)
    ssb = (gm["size"] * (gm["mean"] - q.resid.mean()) ** 2).sum()
    ssw = q.groupby("channel_id").resid.transform(
        lambda s: (s - s.mean()) ** 2).sum()
    msb = ssb / max(J - 1, 1)
    msw = ssw / max(N - J, 1)

    # (2) Binomiales Stichprobenrauschen abziehen. Selbst bei voellig
    #     konstantem wahren Anteil schwankt k/n mit Varianz p(1-p)/n.
    noise = (q.share * (1 - q.share) / q.n).mean()
    msw_true = max(msw - noise, 1e-9)

    n0 = (N - (gm["size"] ** 2).sum() / N) / max(J - 1, 1)
    var_b = max((msb - msw) / n0, 0.0)
    icc_raw = var_b / (var_b + msw) if (var_b + msw) > 0 else np.nan
    icc_corr = var_b / (var_b + msw_true) if (var_b + msw_true) > 0 else np.nan

    print(f"  Kanal-Quartale (n>={MIN_CELL_N})         : {N:,} in {J:,} Kanaelen")
    print(f"  mittlere Clustergroesse n0        : {n0:.1f}")
    print(f"  Varianz zwischen Kanaelen         : {var_b:.5f}")
    print(f"  Varianz innerhalb (roh)           : {msw:.5f}")
    print(f"    davon Binomialrauschen          : {noise:.5f} "
          f"({noise / max(msw, 1e-9):.0%})")
    print(f"    echte zeitliche Variation       : {msw_true:.5f}")
    print(f"\n  ICC unkorrigiert                  : {icc_raw:.3f}   (Untergrenze)")
    print(f"  ICC rauschkorrigiert              : {icc_corr:.3f}   <- berichten")

    S.update(icc_raw=float(icc_raw), icc_corr=float(icc_corr),
             noise_share=float(noise / max(msw, 1e-9)),
             n_cells=int(N), n_cell_channels=int(J))
    print("\n  Design-Effekt DEFF = 1 + (m-1)*ICC:")
    print(f"  {'Quartale/Kanal':>16}{'DEFF':>8}{'effektives N':>15}")
    for m in (4, 9, 20):
        deff = 1 + (m - 1) * icc_corr
        print(f"  {m:>16}{deff:>8.2f}{N / deff:>15,.0f}")
    print(f"\n  Grenzwert bei unendlich viel Material je Kanal: "
          f"J/ICC = {J / max(icc_corr, 1e-9):,.0f}")
    print("  Mehr Material pro Kanal bringt kaum etwas, mehr KANAELE schon.")

    # ================================================================= A4
    hdr("A4  ENGAGEMENT — Kriegsvideos vs. andere Videos DESSELBEN Kanals")
    print("Gepaart innerhalb Kanal x MONAT: kontrolliert Videoalter,")
    print("Kanalgroesse und Nachrichtenlage in einem Schritt.\n")

    # --- Selektionspruefung VOR der Auswertung ---------------------------
    # Kanaele schalten Kommentare gerade bei kontroversen Themen ab. Ist die
    # Ausfallrate bei Kriegsvideos hoeher, ist jeder Kommentarbefund selektiert.
    print("Selektionspruefung — fehlende Werte nach Videotyp:")
    print(f"{'Feld':<12}{'Kontrolle':>12}{'Krieg':>12}{'Differenz':>12}")
    sel_warn = False
    for c in ["comments", "likes", "views"]:
        r = df.groupby("treat")[c].apply(lambda s: s.isna().mean())
        d0, d1 = r.get(0, np.nan), r.get(1, np.nan)
        print(f"{c:<12}{d0:>12.1%}{d1:>12.1%}{d1 - d0:>+12.1%}")
        if abs(d1 - d0) > 0.03:
            sel_warn = True
    if sel_warn:
        print("\n  ! Differenz > 3 Prozentpunkte: Selektion auf dem Treatment.")
        print("    Den betroffenen Befund entweder mit dieser Einschraenkung")
        print("    berichten oder auf Kanaele beschraenken, die durchgehend")
        print("    Kommentare zulassen.")
    else:
        print("\n  Keine auffaellige differenzielle Ausfallrate.")

    e = df[(df.views.notna()) & (df.views > 0) & (df.is_live == 0)].copy()
    e["log_views"] = np.log10(e.views)
    e["like_rate"] = e.likes / e.views
    e["comment_rate"] = e.comments / e.views
    e.loc[(e.likes == 0) & (e.views > 1000), "like_rate"] = np.nan

    metrics = ["log_views", "like_rate", "comment_rate"]
    grp = e.groupby(["channel_id", "period", "treat"])
    tab = grp[metrics].median().join(grp.size().rename("n")).reset_index()
    piv = tab.pivot_table(index=["channel_id", "period"], columns="treat",
                          values=metrics + ["n"])
    piv = piv[(piv[("n", 0)] >= MIN_PER_GROUP) & (piv[("n", 1)] >= MIN_PER_GROUP)]
    print(f"\nVergleichbare Kanal-Monate (>= {MIN_PER_GROUP} je Gruppe): "
          f"{len(piv):,} in {piv.index.get_level_values(0).nunique():,} Kanaelen\n")
    S["a4_cells"] = int(len(piv))
    S["a4_channels"] = int(piv.index.get_level_values(0).nunique())

    print(f"{'Metrik':<16}{'Median-Diff':>14}{'Zellen +':>11}{'n':>9}")
    diffs = {}
    for m in metrics:
        d = (piv[(m, 1)] - piv[(m, 0)]).dropna()
        diffs[m] = d
        if not len(d):
            continue
        sh, nn = sign_share(d)
        txt = f"{10 ** d.median():.2f}x" if m == "log_views" else f"{d.median():+.4f}"
        print(f"{m:<16}{txt:>14}{sh:>11.1%}{nn:>9,}")
        S[f"a4_{m}_median"] = float(
            10 ** d.median() if m == "log_views" else d.median())
        S[f"a4_{m}_signshare"] = float(sh)
    print("\n  Vorzeichentest ohne Gleichstaende: 50% = kein Zusammenhang.")
    print("  Verteilungsfrei, ein virales Einzelvideo kann es nicht kippen.")
    print("\n  Deskriptiv, nicht kausal: Kanaele waehlen ihre Themen, und der")
    print("  Algorithmus verstaerkt, was laeuft.")

    # --- Kreuzung mit der A2-Typologie -----------------------------------
    print("\n" + "-" * 70)
    print("Engagement nach Kanaltyp (A2) — warum bleiben manche beim Thema?")
    print("-" * 70)
    dd = pd.DataFrame({m: diffs[m] for m in metrics}).reset_index()
    dd = dd.merge(ch[["channel_id", "typ"]], on="channel_id", how="left")
    print(f"{'Typ':<22}{'Kanaele':>9}{'Views':>10}{'Like-R +':>11}{'Komm-R +':>11}")
    for t, s in dd.groupby("typ"):
        lv = s.log_views.dropna()
        shl, _ = sign_share(s.like_rate)
        shc, _ = sign_share(s.comment_rate)
        print(f"{t:<22}{s.channel_id.nunique():>9,}"
              f"{10 ** lv.median() if len(lv) else float('nan'):>9.2f}x"
              f"{shl:>11.1%}{shc:>11.1%}")
    print("\n  Belohnt der Algorithmus die Kanaele, die dranbleiben, staerker?")
    dd.to_csv(outdir / f"A4_engagement_by_type_{run_tag()}.csv", index=False)

    # ================================================================= B2
    hdr("B2  NEUZUGAENGE — unterscheiden sie sich von den Etablierten?")
    print("WICHTIG zur Deutung: Neuzugaenge haben kein Vorfenster. Ein")
    print("Vergleich mit dem VORKRIEGSVERHALTEN der Etablierten ist deshalb")
    print("nicht moeglich. Verglichen wird im gemeinsamen Spaetfenster")
    print(f"(Monat {COHORT_COMPARE_WINDOW[0]}-{COHORT_COMPARE_WINDOW[1]}), in dem beide Kohorten praesent sind.\n")

    lo, hi = COHORT_COMPARE_WINDOW
    w = df_all[(df_all.period >= lo) & (df_all.period <= hi)].copy()
    w = w[(w.views.notna()) & (w.views > 0) & (w.is_live == 0)]
    w["like_rate"] = w.likes / w.views
    w.loc[(w.likes == 0) & (w.views > 1000), "like_rate"] = np.nan
    w["comment_rate"] = w.comments / w.views

    # Erst je Kanal mitteln, dann je Kohorte: sonst dominieren produktive
    # Kanaele, und die sind zwischen den Kohorten ungleich verteilt.
    per_ch = w.groupby(["channel_id", "kohorte"]).agg(
        ukr=("treat", "mean"),
        politisch=("topic_political", "mean"),
        like_rate=("like_rate", "median"),
        comment_rate=("comment_rate", "median"),
        n_excl=("n_excl", "mean"),
        title_chars=("title_chars", "mean"),
        dauer_s=("duration_s", "median"),
        videos=("video_id", "size"),
    ).reset_index()
    per_ch = per_ch[per_ch.videos >= MIN_VIDEOS_WINDOW]

    rows = [("ukr", "Kriegsanteil", "{:.1%}"),
            ("politisch", "Anteil Politics/Society", "{:.1%}"),
            ("videos", "Videos im Fenster", "{:,.0f}"),
            ("dauer_s", "Videodauer (s)", "{:,.0f}"),
            ("like_rate", "Like-Rate", "{:.4f}"),
            ("comment_rate", "Kommentar-Rate", "{:.4f}"),
            ("n_excl", "Ausrufezeichen/Titel", "{:.2f}"),
            ("title_chars", "Titellaenge", "{:.1f}")]
    order = [k for k in ("etabliert", "sporadisch", "Neuzugang")
             if k in set(per_ch.kohorte)]
    print(f"{'Merkmal':<26}" + "".join(f"{k:>14}" for k in order))
    print(f"{'(Median ueber Kanaele)':<26}"
          + "".join(f"{'n=' + str((per_ch.kohorte == k).sum()):>14}"
                    for k in order))
    print("-" * (26 + 14 * len(order)))
    for col, lab, fmt in rows:
        vals = [per_ch.loc[per_ch.kohorte == k, col].median() for k in order]
        print(f"{lab:<26}" + "".join(
            f"{(fmt.format(v) if pd.notna(v) else '-'):>14}" for v in vals))

    if {"etabliert", "Neuzugang"} <= set(order):
        a = per_ch.loc[per_ch.kohorte == "etabliert", "ukr"]
        b = per_ch.loc[per_ch.kohorte == "Neuzugang", "ukr"]
        S["b2_ukr_etabliert"] = float(a.median())
        S["b2_ukr_neuzugang"] = float(b.median())
        print(f"\n  Kriegsanteil Neuzugaenge / Etablierte: "
              f"{b.median() / max(a.median(), 1e-9):.2f}x")

    # Fruehe vs. spaete Neuzugaenge: die kurz nach der Invasion gestarteten
    # Kanaele sind der interessante Fall.
    ent2 = coh[coh.kohorte == "Neuzugang"]
    early = set(ent2[ent2.first_period <= 11].index)
    if early:
        pe = per_ch[per_ch.kohorte == "Neuzugang"].copy()
        pe["frueh"] = pe.channel_id.isin(early)
        if pe.frueh.nunique() > 1:
            print("\nNeuzugaenge nach Eintrittszeitpunkt:")
            print(f"{'':<26}{'Mon 0-11':>14}{'ab Mon 12':>14}")
            for col, lab, fmt in rows[:4]:
                v1 = pe.loc[pe.frueh, col].median()
                v2 = pe.loc[~pe.frueh, col].median()
                print(f"{lab:<26}"
                      + "".join(f"{(fmt.format(v) if pd.notna(v) else '-'):>14}"
                                for v in (v1, v2)))
            print("\n  Kanaele, die im ersten Kriegsjahr starteten, koennten")
            print("  kriegsgetrieben gegruendet sein. Ein deutlich hoeherer")
            print("  Kriegsanteil waere ein Hinweis darauf.")

    per_ch.to_csv(outdir / f"B2_cohort_profiles_{run_tag()}.csv", index=False)

    # ================================================================= A5
    hdr("A5  TITELSTIL — unterscheiden sich die Videotypen sprachlich?")
    print("Kein Unterschied -> grosser Populismuseffekt unwahrscheinlich.")
    print("Deutlicher Unterschied -> koennte ein LLM mit Populismus verwechseln.\n")

    sty = ["n_excl", "n_quest", "n_caps_words", "title_chars", "title_words"]
    sp = df.groupby(["channel_id", "period", "treat"])[sty].mean().unstack("treat")
    print(f"{'Merkmal':<16}{'Kontrolle':>11}{'Krieg':>11}{'Diff':>10}"
          f"{'Zellen +':>10}{'n':>8}")
    for m in sty:
        try:
            a, b = sp[(m, 0)], sp[(m, 1)]
        except KeyError:
            continue
        d = (b - a).dropna()
        if not len(d):
            continue
        sh, nn = sign_share(d)
        print(f"{m:<16}{a.mean():>11.2f}{b.mean():>11.2f}"
              f"{d.mean():>+10.2f}{sh:>10.1%}{nn:>8,}")
        S[f"a5_{m}_signshare"] = float(sh)
    print("\n  Gleichstaende sind ausgeschlossen — bei Zaehlmerkmalen, die")
    print("  meist 0 sind, waeren sie sonst als 'negativ' gezaehlt worden.")

    # ================================================================= A6
    hdr("A6  topic_categories — externe Validierung, gratis")
    ct = pd.crosstab(df.treat, df.topic_political, normalize="index")
    print("Anteil mit YouTube-Kategorie Politics/Society:")
    for t in sorted(df.treat.unique()):
        lab = "Kriegsvideos" if t == 1 else "uebrige Videos"
        if 1 in ct.columns:
            print(f"  {lab:<18}{ct.loc[t, 1]:>7.1%}")
    print(f"\n  Videos ohne jede topic_category: {(df.topic_n == 0).sum():,} "
          f"({(df.topic_n == 0).mean():.1%})")
    if 1 in ct.columns:
        S["a6_topic_control"] = float(ct.loc[0, 1])
        S["a6_topic_treat"] = float(ct.loc[1, 1])

    hdr("ZUSATZ  Attenuation durch reine Titelsuche")
    n_t, n_w = df.treat_title_only.sum(), df.treat.sum()
    print(f"  Keyword im Titel        : {n_t:,}")
    print(f"  Titel ODER Beschreibung : {n_w:,}")
    print(f"  nur ueber Beschreibung  : {n_w - n_t:,} "
          f"({(n_w - n_t) / max(n_w, 1):.1%} aller Kriegsvideos)")
    print("\n  Anteil der Treatment-Videos, den eine reine Titelsuche in die")
    print("  Kontrollgruppe verschiebt. Gehoert in den Methodenteil.")
    S.update(treat_title=int(n_t), treat_wide=int(n_w),
             attenuation=float((n_w - n_t) / max(n_w, 1)))

    sp_path = outdir / f"summary_{run_tag()}.json"
    sp_path.write_text(json.dumps(S, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    print(f"\nKennzahlen -> {sp_path}")
    print("  Nach beiden Laeufen: 'compare' fuer die Gegenueberstellung.")

    # --- Grafik -----------------------------------------------------------
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
        axes[0].plot(curve.period, curve.mean_share, lw=1.6, label="Mittel")
        axes[0].plot(curve.period, curve.median_share, lw=1.0, ls="--",
                     label="Median")
        axes[0].plot(curve.period, curve.anteil_aktiv, lw=1.0, ls=":",
                     label="Anteil Kanaele > 0")
        axes[0].axvline(0, color="k", lw=.8)
        axes[0].set_ylabel("Anteil Kriegsvideos")
        axes[0].legend(fontsize=8)
        for t, s in ch_m.merge(ch[["channel_id", "typ"]], on="channel_id").groupby("typ"):
            c = s.groupby("period").share.mean()
            axes[1].plot(c.index, c.values, lw=1.2, label=t)
        axes[1].axvline(0, color="k", lw=.8)
        axes[1].set_xlabel("Monate seit 24.02.2022")
        axes[1].set_ylabel("Anteil (nach Typ)")
        axes[1].legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(outdir / f"A1_attention_curve_{run_tag()}.png", dpi=140)
        print(f"\nGrafik -> {outdir}/A1_attention_curve_{run_tag()}.png")
    except ImportError:
        print("\n(matplotlib nicht installiert — nur CSV geschrieben)")


# ---------------------------------------------------------------------------
# Stufe: compare
# ---------------------------------------------------------------------------

# Kennzahl -> (Beschriftung, Format). Nur was fuer die Entscheidung zaehlt.
COMPARE_ROWS = [
    ("n_videos", "Videos", "{:,.0f}"),
    ("n_channels", "Kanaele", "{:,.0f}"),
    (None, "— A1 Aufmerksamkeit —", None),
    ("baseline", "Baseline", "{:.2%}"),
    ("peak", "Peak", "{:.2%}"),
    ("peak_month", "Peak-Monat", "{:.0f}"),
    ("peak_over_baseline", "Peak / Baseline", "{:.1f}x"),
    ("late", "ab Monat 24", "{:.2%}"),
    ("late_over_peak", "spaet / Peak", "{:.1%}"),
    (None, "— B0/B2 Kohorten —", None),
    ("b2_ukr_etabliert", "Kriegsanteil etabliert", "{:.1%}"),
    ("b2_ukr_neuzugang", "Kriegsanteil Neuzugang", "{:.1%}"),
    (None, "— A2 Heterogenitaet —", None),
    ("a2_channels", "Kanaele in A2", "{:,.0f}"),
    ("a2_unobserved", "davon nicht beobachtet", "{:,.0f}"),
    ("a2_usable", "nutzbar fuer Frage (b)", "{:,.0f}"),
    ("shock_median", "Median Schock", "{:.1%}"),
    ("shock_p10_p90", "p10-p90 Schock", "{:.1%}"),
    ("shock_sd", "SD Schock", "{:.3f}"),
    (None, "— A3 Varianz —", None),
    ("n_cells", "Kanal-Quartale", "{:,.0f}"),
    ("noise_share", "Anteil Binomialrauschen", "{:.0%}"),
    ("icc_raw", "ICC unkorrigiert", "{:.3f}"),
    ("icc_corr", "ICC korrigiert", "{:.3f}"),
    (None, "— A4 Engagement —", None),
    ("a4_cells", "Kanal-Monate", "{:,.0f}"),
    ("a4_log_views_median", "Views-Faktor", "{:.2f}x"),
    ("a4_log_views_signshare", "Views Zellen +", "{:.1%}"),
    ("a4_comment_rate_signshare", "Komm.-Rate Zellen +", "{:.1%}"),
    ("a4_like_rate_signshare", "Like-Rate Zellen +", "{:.1%}"),
    (None, "— A5 Titelstil —", None),
    ("a5_n_excl_signshare", "Ausrufezeichen +", "{:.1%}"),
    ("a5_title_chars_signshare", "Titellaenge +", "{:.1%}"),
    (None, "— Sonstiges —", None),
    ("a6_topic_treat", "Politics-Anteil Krieg", "{:.1%}"),
    ("attenuation", "Attenuation Titelsuche", "{:.1%}"),
]


def cmd_compare(args):
    """Stellt die Kennzahlen beider Laeufe nebeneinander.

    Voraussetzung: 'diagnose' einmal mit MIN_DURATION_S = None und einmal
    mit MIN_DURATION_S = 180 laufen lassen.
    """
    outdir = Path(args.outdir)
    files = sorted(outdir.glob("summary_*.json"))
    if len(files) < 2:
        print("Es liegen weniger als zwei Laeufe vor:")
        for f in files:
            print(f"  {f.name}")
        print("\nMIN_DURATION_S umstellen und 'diagnose' erneut laufen lassen.")
        return

    runs = {}
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        runs[d.get("tag", f.stem)] = d
    keys = sorted(runs, key=lambda k: (k != "all", k))

    w = 26
    print(f"{'Kennzahl':<{w}}" + "".join(f"{k:>16}" for k in keys)
          + f"{'Aenderung':>14}")
    print("-" * (w + 16 * len(keys) + 14))
    for key, label, fmt in COMPARE_ROWS:
        if key is None:
            print(f"\n{label}")
            continue
        vals = [runs[k].get(key) for k in keys]
        if all(v is None for v in vals):
            continue
        cells = "".join(
            f"{(fmt.format(v) if v is not None else '-'):>16}" for v in vals)
        delta = ""
        if len(vals) >= 2 and all(isinstance(v, (int, float)) for v in vals[:2]):
            a, b = vals[0], vals[1]
            delta = f"{(b - a) / a:+.1%}" if a else "n/a"
        print(f"{label:<{w}}{cells}{delta:>14}")

    print("\nWorauf zu achten ist:")
    print("  ICC korrigiert  — aendert sich die Power-Rechnung?")
    print("  p10-p90 Schock  — bleibt die Heterogenitaet erhalten?")
    print("  Views-Faktor    — haelt der Engagement-Befund?")
    print("  Kanaele         — wie viele gehen verloren?")
    print("\nBleiben die Kennzahlen stabil, ist der Filter unschaedlich und")
    print("du kannst ihn mit der Langform-Begruendung setzen. Kippen sie,")
    print("gehoeren beide Varianten in die Arbeit.")


# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", nargs="?", default=COMMAND,
                   choices=["clean", "extract", "diagnose", "compare", "all"])
    p.add_argument("--jsonl", default=str(JSONL_PATH))
    p.add_argument("--outdir", default=str(OUTDIR))
    p.add_argument("--limit", type=int, default=LIMIT)
    a = p.parse_args()

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"Eingabe : {a.jsonl}\nAusgabe : {outdir}\nLimit   : {a.limit}")
    print(f"Stichtag Videoalter: {SCRAPE_DATE.date()}  <- muss dem Abrufdatum "
          "der Metadaten entsprechen")
    print(f"Dauerfilter        : "
          f"{'aus (alle Videos)' if MIN_DURATION_S is None else str(MIN_DURATION_S) + 's'}")
    print(f"Kohorte            : {COHORT_RESTRICT or 'alle'}"
          f"   -> Lauf-Kennung '{run_tag()}'")

    (outdir / f"run_config_{run_tag()}.json").write_text(json.dumps({
        "cmd": a.cmd, "jsonl": str(a.jsonl), "limit": a.limit,
        "min_duration_s": MIN_DURATION_S, "run_tag": run_tag(),
        "cohort_restrict": COHORT_RESTRICT,
        "cohort_pre_min_videos": COHORT_PRE_MIN_VIDEOS,
        "min_videos_window": MIN_VIDEOS_WINDOW,
        "scrape_date": SCRAPE_DATE.isoformat(),
        "invasion": INVASION.isoformat(),
        "pre_window": PRE_WINDOW, "shock_window": SHOCK_WINDOW,
        "boilerplate_threshold": BOILERPLATE_THRESHOLD,
        "min_cell_n": MIN_CELL_N, "min_per_group": MIN_PER_GROUP,
        "keywords": KEYWORDS,
        "executed_at": datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    steps = {"clean": cmd_clean, "extract": cmd_extract,
             "diagnose": cmd_diagnose, "compare": cmd_compare}
    order = ["clean", "extract", "diagnose"] if a.cmd == "all" else [a.cmd]
    for s in order:
        print(f"\n{'#' * 70}\n# {s.upper()}\n{'#' * 70}")
        steps[s](a)


if __name__ == "__main__":
    main()
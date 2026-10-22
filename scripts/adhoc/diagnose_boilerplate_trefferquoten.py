"""
Diagnose der Boilerplate-Bereinigung (step3_topic_relevance/boilerplate.py):
vergleicht pro Kanal x Jahr die Keyword-Trefferquote im Titel allein mit der
in der bereinigten Beschreibung - einmal mit der alten Bereinigung
(feasibility.py-Fassung: 300er-Stichprobe, wortgleiche Zeilen, 60% kanalweit)
und einmal mit der neuen (normalisierte Zeilen, Zeitfenster, absolute Regel).

Idee: Ein Kanal, bei dem die Quote "nur Beschreibung trifft, Titel nicht"
sprunghaft ansteigt (z.B. 2022 von 5% auf 70%), hat sehr wahrscheinlich eine
neue feste Beschreibungszeile mit Keyword (Spendenaufruf, Hashtag-Kette), die
der Filter nicht erkennt. Wirkt die Korrektur, sollte dieser Sprung in der
neuen Spalte verschwinden.

Ausgabe (OUTPUT_DIR):
    trefferquoten_kanal_jahr.csv - alle Kanal x Jahr-Zellen
    bericht.md                    - Zusammenfassung + auffaellige Kanaele

Laedt alle Videos des Samples und lernt die Boilerplate zweimal - Laufzeit
und Speicherbedarf aehnlich wie classify_topic_relevance.py (Boilerplate-
Phase), d.h. bei ~500k Videos grob 10-20 Minuten.

Ausfuehrung:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/adhoc/diagnose_boilerplate_trefferquoten.py
"""
from __future__ import annotations

import time
from collections import Counter, defaultdict

import pandas as pd

from youtube_code.config import OUTPUTS, SAMPLES
from youtube_code.step3_topic_relevance import boilerplate as bp
from youtube_code.step3_topic_relevance.topic_keywords import KW_RE, TIERS, TOPIC_KEYWORDS
from youtube_code.store import video_registry

# ============================================================
# CONFIG
# ============================================================
TOPIC = "russia_ukraine_war"
channel_path = SAMPLES / "russia_longitudinal_v1" / "channel_sample_provenance.csv"
CHANNEL_FILTER = pd.read_csv(channel_path, usecols=["channel_id"],
                             dtype={"channel_id": "string"})["channel_id"].tolist()
# Kanal x Jahr-Zellen mit weniger Videos werden fuer die Sprung-Erkennung ignoriert.
MIN_VIDEOS_PER_YEAR = 10
# Auffaellig: Quote "nur Beschreibung" (alte Bereinigung) >= MIN_LEVEL und
# gegenueber dem Vorjahr um >= MIN_JUMP Prozentpunkte gestiegen.
MIN_LEVEL = 0.30
MIN_JUMP = 0.20
OUTPUT_DIR = OUTPUTS / "boilerplate_diagnose"

LEGACY_SAMPLE_PER_CHANNEL = 300


def learn_boilerplate_legacy(df) -> dict:
    """Alte Fassung (vor 2026-10-05) zum Vergleich: {channel_id: {hash}}."""
    valid = df[df["channel_id"].notna() & (df["channel_id"] != "")]
    sample = (valid.sort_values("video_id")
              .groupby("channel_id", sort=False, group_keys=False)
              .head(LEGACY_SAMPLE_PER_CHANNEL))
    seen = sample.groupby("channel_id")["video_id"].size()
    counts = defaultdict(Counter)
    for ch, desc in zip(sample["channel_id"], sample["description"]):
        for ln in bp.split_paragraphs(desc):
            if len(ln) >= bp.BOILERPLATE_MIN_LEN:
                counts[ch][bp.line_hash(ln)] += 1
    boiler = {}
    for ch, c in counts.items():
        n = seen[ch]
        if n < bp.BOILERPLATE_MIN_SAMPLE:
            continue
        hashes = {h for h, k in c.items() if k / n >= bp.BOILERPLATE_THRESHOLD}
        if hashes:
            boiler[ch] = hashes
    return boiler


def clean_legacy(desc, ch, boiler) -> str:
    drop = boiler.get(ch)
    if not drop:
        return desc or ""
    return "\n".join(ln for ln in bp.split_paragraphs(desc) if bp.line_hash(ln) not in drop)


def topic_hit(texts: pd.Series) -> pd.Series:
    prefix = TOPIC_KEYWORDS[TOPIC]["prefix"]
    hit = pd.Series(False, index=texts.index)
    for tier in TIERS:
        if tier in TOPIC_KEYWORDS[TOPIC]:
            hit |= texts.str.contains(KW_RE[f"{prefix}_{tier}"], na=False)
    return hit


def main() -> None:
    t0 = time.perf_counter()
    df = video_registry.get_videos_with_text(channel_ids=CHANNEL_FILTER)
    df["description"] = df["description"].fillna("")
    print(f"{len(df):,} Videos aus {df.channel_id.nunique():,} Kanaelen geladen.")

    legacy = learn_boilerplate_legacy(df)
    print(f"Alt: Boilerplate fuer {len(legacy):,} Kanaele ({time.perf_counter() - t0:.0f}s).")
    new = bp.learn_boilerplate(df)
    n_win = sum(len(b["windows"]) for b in new.values())
    print(f"Neu: Boilerplate fuer {len(new):,} Kanaele, {n_win:,} Kanal-Fenster mit "
          f"zusaetzlichen Zeilen ({time.perf_counter() - t0:.0f}s).")

    desc_old = pd.Series([clean_legacy(d, c, legacy) for d, c in
                          zip(df["description"], df["channel_id"])], index=df.index)
    desc_new = pd.Series([bp.clean_description(d, c, new, p) for d, c, p in
                          zip(df["description"], df["channel_id"], df["published_at"])],
                         index=df.index)
    print(f"Beschreibungen bereinigt ({time.perf_counter() - t0:.0f}s).")

    title = topic_hit(df["title"].fillna(""))
    d_old = topic_hit(desc_old)
    d_new = topic_hit(desc_new)
    d_raw = topic_hit(df["description"])
    cells = pd.DataFrame({
        "channel_id": df["channel_id"],
        "channel_title": df["channel_title"],
        "year": df["published_at"].str[:4],
        "titel": title,
        "beschr_roh": d_raw,
        "beschr_alt": d_old,
        "beschr_neu": d_new,
        "nur_beschr_alt": d_old & ~title,
        "nur_beschr_neu": d_new & ~title,
        "relevant_alt": title | d_old,
        "relevant_neu": title | d_new,
    })
    rate_cols = [c for c in cells.columns if c not in ("channel_id", "channel_title", "year")]
    agg = (cells.groupby(["channel_id", "year"])
           .agg(channel_title=("channel_title", "first"), n=("titel", "size"),
                **{c: (c, "mean") for c in rate_cols})
           .reset_index().sort_values(["channel_id", "year"]))
    agg["sprung_alt"] = agg.groupby("channel_id")["nur_beschr_alt"].diff()
    agg["sprung_neu"] = agg.groupby("channel_id")["nur_beschr_neu"].diff()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    agg.to_csv(OUTPUT_DIR / "trefferquoten_kanal_jahr.csv", index=False)

    big = agg[agg["n"] >= MIN_VIDEOS_PER_YEAR]
    sus = big[(big["nur_beschr_alt"] >= MIN_LEVEL) & (big["sprung_alt"] >= MIN_JUMP)]
    sus = sus.sort_values("sprung_alt", ascending=False)
    still = sus[(sus["nur_beschr_neu"] >= MIN_LEVEL) & (sus["sprung_neu"] >= MIN_JUMP)]

    by_year = (cells.groupby("year")[["titel", "beschr_alt", "beschr_neu",
                                      "relevant_alt", "relevant_neu"]].mean())
    fmt = lambda x: f"{x:.1%}" if pd.notna(x) else "-"  # noqa: E731

    lines = [
        f"# Boilerplate-Diagnose: Trefferquoten Titel vs. bereinigte Beschreibung",
        "",
        f"Thema: `{TOPIC}` - {len(df):,} Videos, {df.channel_id.nunique():,} Kanaele. "
        f"Neue Bereinigung: Fenster `{bp.BOILERPLATE_WINDOW}`, Schwelle "
        f"{bp.BOILERPLATE_THRESHOLD:.0%}, absolute Regel >= {bp.BOILERPLATE_MIN_ABS_VIDEOS} Videos, "
        f"min. {bp.BOILERPLATE_MIN_WINDOW_VIDEOS} Videos je Fenster.",
        "",
        f"- Kanaele mit Boilerplate: alt {len(legacy):,}, neu {len(new):,}",
        f"- Als relevant klassifiziert: alt {cells.relevant_alt.mean():.1%}, "
        f"neu {cells.relevant_neu.mean():.1%} "
        f"({int(cells.relevant_alt.sum() - cells.relevant_neu.sum()):,} Videos weniger)",
        f"- Davon nur ueber die Beschreibung: alt {cells.nur_beschr_alt.mean():.1%}, "
        f"neu {cells.nur_beschr_neu.mean():.1%}",
        "",
        "## Quoten je Jahr (alle Kanaele)",
        "",
        "| Jahr | Titel | Beschr. alt | Beschr. neu | relevant alt | relevant neu |",
        "|---|---|---|---|---|---|",
    ]
    for year, r in by_year.iterrows():
        lines.append(f"| {year} | {fmt(r.titel)} | {fmt(r.beschr_alt)} | {fmt(r.beschr_neu)} | "
                     f"{fmt(r.relevant_alt)} | {fmt(r.relevant_neu)} |")
    lines += [
        "",
        f"## Auffaellige Kanal-Jahre (alte Bereinigung)",
        "",
        f"Kriterium: >= {MIN_VIDEOS_PER_YEAR} Videos im Jahr, Quote \"nur Beschreibung trifft\" "
        f">= {MIN_LEVEL:.0%} und gegenueber Vorjahr um >= {MIN_JUMP * 100:.0f} Pp. gestiegen. "
        f"{len(sus):,} Kanal-Jahre auffaellig, davon {len(still):,} auch nach neuer Bereinigung.",
        "",
        "| Kanal | Jahr | n | Titel | nur Beschr. alt | Sprung alt | nur Beschr. neu | Sprung neu |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in sus.itertuples():
        lines.append(f"| {r.channel_title} | {r.year} | {r.n} | {fmt(r.titel)} | "
                     f"{fmt(r.nur_beschr_alt)} | {fmt(r.sprung_alt)} | "
                     f"{fmt(r.nur_beschr_neu)} | {fmt(r.sprung_neu)} |")
    (OUTPUT_DIR / "bericht.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Geschrieben nach {OUTPUT_DIR} ({time.perf_counter() - t0:.0f}s). "
          f"{len(sus)} auffaellige Kanal-Jahre, davon {len(still)} auch nach neuer Bereinigung.")


if __name__ == "__main__":
    main()

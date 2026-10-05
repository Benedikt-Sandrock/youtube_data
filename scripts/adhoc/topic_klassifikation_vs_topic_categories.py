"""
Vergleich der Keyword-Themenklassifikation (Schritt 3, Tabelle
`video_topic_relevance`) mit der YouTube-eigenen Metadaten-Kategorie
`video_details.topic_categories` (topicDetails.topicCategories, Wikipedia-URLs).

Erzeugt Überschneidungsmatrizen (Anzahl gemeinsamer Videos) über alle Listen:
13 Keyword-Themen + YouTube-topicCategories (Kategorien mit >= MIN_N Videos).

Stichprobe: Videos, die für ALLE Keyword-Themen klassifiziert sind UND eine
`video_details`-Zeile haben. Videos ohne topicCategory laufen als eigene
Spalte "YT: (keine)" mit.

Output (outputs/validation/topic_vs_topic_categories/):
- regression_results/topic_vs_topic_categories.md  Übersicht (menschenlesbar)
- overlap_counts_full.csv        quadratische Matrix, alle Listen x alle Listen
- overlap_keyword_x_yt_counts.csv  Keyword-Themen x YT-Kategorien (Anzahl)
- heatmap_full_rowshare.png      Zeilenanteil P(Spalte | Zeile) als Heatmap

Ausführung:
    PYTHONPATH=src .venv/Scripts/python.exe scripts/adhoc/topic_klassifikation_vs_topic_categories.py
"""
import json
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "store" / "video_registry.sqlite"
OUT = ROOT / "outputs" / "validation" / "topic_vs_topic_categories"
MD_DIR = OUT / "regression_results"
MIN_N = 1000  # YT-Kategorien mit weniger Videos werden ausgelassen


def load() -> pd.DataFrame:
    con = sqlite3.connect(DB)
    try:
        topics = [r[0] for r in con.execute(
            "SELECT DISTINCT topic FROM video_topic_relevance ORDER BY topic")]
        cases = ",\n".join(
            f"MAX(CASE WHEN topic='{t}' THEN is_relevant END) AS \"KW: {t}\"" for t in topics)
        sql = f"""
            WITH kw AS (
                SELECT video_id, {cases}, COUNT(*) AS n_topics
                FROM video_topic_relevance GROUP BY video_id
            )
            SELECT kw.*, d.topic_categories
            FROM kw JOIN video_details d USING (video_id)
            WHERE kw.n_topics = {len(topics)}
        """
        df = pd.read_sql_query(sql, con)
    finally:
        con.close()
    return df, topics


def yt_dummies(series: pd.Series) -> pd.DataFrame:
    def parse(x):
        if not x:
            return []
        try:
            lst = json.loads(x)
        except (TypeError, ValueError):
            return []
        return [u.rsplit("/", 1)[-1].replace("_", " ") for u in lst]

    cats = series.map(parse)
    d = pd.get_dummies(cats.explode()).groupby(level=0).max()
    d = d.reindex(series.index, fill_value=False)
    d.columns = [f"YT: {c}" for c in d.columns]
    d["YT: (keine)"] = cats.map(len) == 0
    return d.astype(bool)


def md_table(df: pd.DataFrame, fmt) -> str:
    cols = [""] + [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for idx, row in df.iterrows():
        lines.append("| " + " | ".join([str(idx)] + [fmt(v) for v in row]) + " |")
    return "\n".join(lines)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    MD_DIR.mkdir(parents=True, exist_ok=True)

    df, topics = load()
    n = len(df)
    kw_cols = [f"KW: {t}" for t in topics]
    kw = df[kw_cols].fillna(0).astype(bool)
    yt = yt_dummies(df["topic_categories"])
    yt_n = yt.sum().sort_values(ascending=False)
    yt_keep = [c for c in yt_n.index if yt_n[c] >= MIN_N]
    yt = yt[yt_keep]

    # Ukraine-Krieg und Politik vorne, Rest nach Größe
    kw_order = ["KW: russia_ukraine_war", "KW: politics_general"] + sorted(
        [c for c in kw_cols if c not in ("KW: russia_ukraine_war", "KW: politics_general")],
        key=lambda c: -kw[c].sum())
    kw = kw[kw_order]
    yt_order = [c for c in ["YT: Politics", "YT: Military", "YT: Society"] if c in yt] + [
        c for c in yt.columns if c not in ("YT: Politics", "YT: Military", "YT: Society")]
    yt = yt[yt_order]

    X = pd.concat([kw, yt], axis=1).astype(np.int32)
    M = X.T @ X  # Anzahl gemeinsamer Videos, Diagonale = Größe der Liste
    diag = np.diag(M.values)
    rowshare = M.div(diag, axis=0)  # P(Spalte | Zeile)
    jaccard = M / (diag[:, None] + diag[None, :] - M.values)

    cross = M.loc[kw.columns, yt.columns]
    cross_row = rowshare.loc[kw.columns, yt.columns]
    cross_col = rowshare.loc[yt.columns, kw.columns].T  # P(KW | YT)

    M.to_csv(OUT / "overlap_counts_full.csv")
    cross.to_csv(OUT / "overlap_keyword_x_yt_counts.csv")

    # Heatmap
    fig, ax = plt.subplots(figsize=(0.42 * len(M) + 4, 0.42 * len(M) + 3))
    im = ax.imshow(rowshare.values, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(M)), M.columns, rotation=90, fontsize=8)
    ax.set_yticks(range(len(M)), [f"{c} (n={d:,})" for c, d in zip(M.index, diag)], fontsize=8)
    for i in range(len(M)):
        for j in range(len(M)):
            v = rowshare.values[i, j]
            if v >= 0.05:
                ax.text(j, i, f"{v*100:.0f}", ha="center", va="center", fontsize=6,
                        color="white" if v > 0.6 else "black")
    k = len(kw.columns) - 0.5
    ax.axhline(k, color="red", lw=1); ax.axvline(k, color="red", lw=1)
    ax.set_title(f"Anteil der Zeilen-Videos (%), die auch in der Spalten-Liste sind  (N={n:,})")
    fig.colorbar(im, ax=ax, fraction=0.03)
    fig.tight_layout()
    fig.savefig(OUT / "heatmap_full_rowshare.png", dpi=150)
    plt.close(fig)

    pct = lambda v: f"{v*100:.1f}"
    cnt = lambda v: f"{int(v):,}"
    sizes = pd.DataFrame({"n": diag, "Anteil %": diag / n * 100}, index=M.index)

    no_kw = ~kw.drop(columns="KW: politics_general").any(axis=1)
    pol = yt["YT: Politics"] if "YT: Politics" in yt else pd.Series(False, index=yt.index)

    md = [
        "# Keyword-Themen vs. YouTube-topicCategories",
        "",
        f"Skript: `scripts/adhoc/topic_klassifikation_vs_topic_categories.py`  ",
        f"Stichprobe: {n:,} Videos (für alle {len(topics)} Keyword-Themen klassifiziert "
        f"und mit `video_details`-Zeile). YT-Kategorien mit < {MIN_N:,} Videos ausgelassen.",
        "",
        "`KW:` = Keyword-Klassifikation (`video_topic_relevance.is_relevant`), "
        "`YT:` = `video_details.topic_categories`. Ein Video kann in mehreren Listen sein.",
        "",
        "## Größe der Listen",
        "",
        md_table(sizes, lambda v: f"{v:,.1f}" if isinstance(v, float) and v < 100 else f"{int(v):,}"),
        "",
        "## Keyword-Themen × YT-Kategorien: Anzahl gemeinsamer Videos",
        "",
        md_table(cross, cnt),
        "",
        "## Zeilenanteil: % der Keyword-Videos, die die YT-Kategorie tragen  P(YT | KW)",
        "",
        md_table(cross_row, pct),
        "",
        "## Spaltenanteil: % der YT-Kategorie-Videos, die das Keyword-Thema tragen  P(KW | YT)",
        "",
        md_table(cross_col, pct),
        "",
        "## Keyword-Themen untereinander: Anzahl gemeinsamer Videos",
        "",
        md_table(M.loc[kw.columns, kw.columns], cnt),
        "",
        "## Keyword-Themen untereinander: Jaccard (%)",
        "",
        md_table(jaccard.loc[kw.columns, kw.columns], pct),
        "",
        "## YT-Kategorien untereinander: Anzahl gemeinsamer Videos",
        "",
        md_table(M.loc[yt.columns, yt.columns], cnt),
        "",
        "## Kennzahlen",
        "",
        f"- YT: Politics gesamt: {int(pol.sum()):,}; davon ohne jedes Keyword-Thema "
        f"(außer politics_general): {int((pol & no_kw).sum()):,} "
        f"({(pol & no_kw).sum() / max(pol.sum(), 1) * 100:.1f} %)",
        f"- Videos mit mind. einem Keyword-Thema (außer politics_general): "
        f"{int((~no_kw).sum()):,}; davon ohne YT: Politics: {int((~no_kw & ~pol).sum()):,} "
        f"({(~no_kw & ~pol).sum() / max((~no_kw).sum(), 1) * 100:.1f} %)",
        "",
        "Vollständige quadratische Matrix: `overlap_counts_full.csv`, "
        "Heatmap (Zeilenanteile): `heatmap_full_rowshare.png`.",
    ]
    (MD_DIR / "topic_vs_topic_categories.md").write_text("\n".join(md), encoding="utf-8")
    print(f"N={n:,}; Output: {OUT}")


if __name__ == "__main__":
    main()

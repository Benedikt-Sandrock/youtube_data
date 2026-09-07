"""Ad-hoc-Export: Beispielvideos von "Steuern mit Kopf" (UCCwCa-faBqcY-zJ4PS1lCHA)
zur Illustration des in top_populismus_sprung_je_kanal.py gefundenen
Populismus-Sprungs (Sprung Vorkriegs- vs. Nachkriegsmittelwert).

Enthaelt:
- ALLE vorkriegs-klassifizierten (politischen Baseline-)Videos des Kanals
  (rel_monat < 0, aus channel_video_populism.csv)
- die TOP_N nachkriegs-Videos mit dem hoechsten populismus_gesamt-Wert
  innerhalb der ersten POST_WINDOW_DAYS Tage nach Kriegsbeginn (24.02.2022)

Metadaten (Titel, Veroeffentlichungsdatum, Views/Likes) kommen aus
data/store/video_registry.sqlite (Tabelle `videos`).

Output: scripts/adhoc/output/steuern_mit_kopf_beispielvideos.csv
"""

import sqlite3
from datetime import datetime, timedelta

import pandas as pd

CHANNEL_ID = "UCCwCa-faBqcY-zJ4PS1lCHA"
KRIEGSBEGINN = datetime(2022, 2, 24)
POST_WINDOW_DAYS = 90  # erste 3 Monate
TOP_N_POST = 5

POP_PATH = "outputs/segment_analysis/channel_video_populism.csv"
REGISTRY_PATH = "data/store/video_registry.sqlite"
OUT_PATH = "scripts/adhoc/output/steuern_mit_kopf_beispielvideos.csv"


def main():
    pop = pd.read_csv(POP_PATH)
    pop = pop[pop["channel_id"] == CHANNEL_ID].copy()

    con = sqlite3.connect(REGISTRY_PATH)
    meta = pd.read_sql_query(
        "SELECT video_id, published_at, title, view_count, like_count, comment_count "
        "FROM videos WHERE channel_id = ?",
        con,
        params=(CHANNEL_ID,),
    )
    con.close()
    meta["published_at"] = pd.to_datetime(meta["published_at"]).dt.tz_localize(None)

    df = pop.merge(meta, on="video_id", how="left")

    # (a) alle vorkriegs-klassifizierten (politischen Baseline-)Videos
    vor = df[df["rel_monat"] < 0].copy()
    vor["gruppe"] = "vorkrieg_alle"

    # (b) Top-N nachkriegs-Videos nach populismus_gesamt, erste POST_WINDOW_DAYS Tage
    fenster_ende = KRIEGSBEGINN + timedelta(days=POST_WINDOW_DAYS)
    nach_fenster = df[(df["rel_monat"] >= 0) & (df["published_at"] >= KRIEGSBEGINN) & (df["published_at"] < fenster_ende)].copy()
    if nach_fenster.empty:
        # Fuer diesen Kanal existiert kein klassifiziertes Nachkriegsvideo in den ersten
        # POST_WINDOW_DAYS Tagen (individuelles Klassifikations-Fenster, siehe
        # frage1_methodik_und_stichprobe.md Abschnitt 3a/3b) -> Fallback auf die
        # TOP_N_POST Videos ueber den GESAMTEN Nachkriegszeitraum, deutlich markiert.
        alle_nach = df[df["rel_monat"] >= 0]
        print(
            f"WARNUNG: keine klassifizierten Nachkriegsvideos in den ersten {POST_WINDOW_DAYS} Tagen "
            f"nach Kriegsbeginn gefunden. Fruehestes klassifiziertes Nachkriegsvideo: "
            f"{alle_nach['published_at'].min()} (rel_monat={alle_nach['rel_monat'].min()}). "
            f"Fallback: Top {TOP_N_POST} ueber den gesamten Nachkriegszeitraum."
        )
        nach = alle_nach.sort_values("populismus_gesamt", ascending=False).head(TOP_N_POST)
        nach["gruppe"] = f"nachkrieg_top{TOP_N_POST}_GESAMTER_ZEITRAUM_ACHTUNG_kein_video_in_ersten_{POST_WINDOW_DAYS}_tagen"
    else:
        nach = nach_fenster.sort_values("populismus_gesamt", ascending=False).head(TOP_N_POST)
        nach["gruppe"] = f"nachkrieg_top{TOP_N_POST}_erste_{POST_WINDOW_DAYS}_tage"

    out = pd.concat([vor, nach], ignore_index=True)
    out = out.sort_values(["gruppe", "published_at"])

    cols = [
        "gruppe", "video_id", "title", "published_at", "rel_monat", "rel_quartal",
        "view_count", "like_count", "comment_count",
        "volkszentrismus", "antielitismus", "manichaeische_moralisierung",
        "emotionale_intensitaet", "populismus_gesamt",
    ]
    out = out[cols]
    out.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"Geschrieben: {OUT_PATH} ({len(out)} Zeilen: {len(vor)} vorkriegs + {len(nach)} nachkriegs)")
    print(out.to_string())


if __name__ == "__main__":
    main()

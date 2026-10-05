# -*- coding: utf-8 -*-
"""
videos_pro_quartal_whitelist.py

Zaehlt fuer alle Kanaele der Frage-1-Whitelist
(`outputs/segment_analysis/frage1_kanal_whitelist.csv`) die Anzahl der in
`video_registry.sqlite` (Tabelle `videos`) bekannten Videos pro Kalenderquartal
und markiert Auffaelligkeiten, die auf fehlgeschlagenes Scraping hindeuten
koennen. Quelle ist bewusst direkt die Registry (nicht die abgeleitete
channel_video_erfolg.csv), damit auch Videos ohne view_count/Details mitzaehlen
und Discovery-Luecken sichtbar werden.

Gezaehlt werden ALLE Videos (keine Mindestdauer, keine Politik-/Themenfilter),
da es um die Vollstaendigkeit der Video-Discovery geht, nicht um eine
inhaltliche Auswertung.

Heuristiken (Flags in `auffaelligkeiten.csv`, Schwellen als Konstanten unten):

  - null_luecke: Quartal mit 0 Videos, obwohl der Kanal davor UND danach
    Videos hat.
  - einbruch: Quartal mit < EINBRUCH_FAKTOR x dem Median der umliegenden
    aktiven Quartale (+-NACHBARN, ohne das Quartal selbst), sofern dieser
    lokale Median >= MIN_LOKALER_MEDIAN ist. Geprueft wird nur im aktiven
    Zeitraum des Kanals, ohne Anlauf-Quartal eines spaeter startenden und
    Auslauf-Quartal eines frueh endenden Kanals. Ein isolierter Einbruch
    spricht eher fuer einen Scraping-Ausfall als ein gradueller Trend.
  - anhaltende_luecke: Quartal mit < ANHALTEND_FAKTOR x dem Niveau, das der
    Kanal davor UND danach schon einmal erreicht hat (min(max davor, max
    danach) >= MIN_REF_ANHALTEND). Faengt mehrquartalige Luecken ab, bei
    denen auch die Nachbarquartale leer sind und der lokale Median versagt.
    geschaetzt_fehlend ist hier eine Obergrenze.
  - playlist_limit: Registry kennt >= PLAYLIST_LIMIT_SCHWELLE Videos, aber
    weniger als MIN_ANTEIL_REGISTRY_VS_API des API-Bestands
    (`channels.video_count`) -> die Uploads-Playlist liefert nur die ~20.000
    neuesten Videos, fruehe/mittlere Quartale sind vermutlich unvollstaendig.
    (Ein allgemeiner Registry-vs-API-Abgleich ist nicht aussagekraeftig, da die
    Registry nur Videos ab 2021 enthaelt, der API-Count aber alle.)
  - fruehes_ende: letztes Quartal mit Videos liegt vor dem letzten
    Beobachtungsquartal (Kanal inaktiv ODER Nachscraping fehlt).
  - fehlende_stats: Anteil Videos ohne view_count >= MAX_ANTEIL_OHNE_VIEWS in
    einem Quartal mit >= MIN_VIDEOS_FUER_STATS_FLAG Videos (Video bekannt,
    aber Metadaten-Fetch fehlt).

Ausgaben nach outputs/segment_analysis/datenluecken_quartale/:
  - videos_pro_quartal_lang.csv   (channel_id x quartal, n_videos, n_ohne_views)
  - videos_pro_quartal_breit.csv  (Kanal-Zeilen, Quartal-Spalten)
  - auffaelligkeiten.csv          (ein Flag pro Zeile, inkl. grober Schaetzung
                                   geschaetzt_fehlend fuer die Priorisierung)
  - README.md                     (Zusammenfassung, menschenlesbar)

Laeuft direkt als Skript:

    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        scripts/adhoc/videos_pro_quartal_whitelist.py
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src", "youtube_code", "step6_auswertung"))

import pandas as pd

from deskriptiv_aggregation import lade_medientyp
from youtube_code.config import OUTPUTS, STORE

DB_PATH = STORE / "video_registry.sqlite"
PFAD_WHITELIST = OUTPUTS / "segment_analysis" / "frage1_kanal_whitelist.csv"
ERGEBNIS_ORDNER = OUTPUTS / "segment_analysis" / "datenluecken_quartale"

QUARTAL_START = pd.Period("2021Q1", freq="Q")
QUARTAL_ENDE = pd.Period("2026Q2", freq="Q")

EINBRUCH_FAKTOR = 0.3
NACHBARN = 2
MIN_LOKALER_MEDIAN = 10
MAX_ANTEIL_OHNE_VIEWS = 0.2
MIN_VIDEOS_FUER_STATS_FLAG = 10
ANHALTEND_FAKTOR = 0.2
MIN_REF_ANHALTEND = 50
PLAYLIST_LIMIT_SCHWELLE = 19500
MIN_ANTEIL_REGISTRY_VS_API = 0.9
TOP_N = 30


def lade_daten():
    whitelist = pd.read_csv(PFAD_WHITELIST)["channel_id"].astype(str).tolist()
    platzhalter = ",".join("?" * len(whitelist))
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        videos = pd.read_sql_query(
            f"SELECT channel_id, published_at, view_count FROM videos "
            f"WHERE channel_id IN ({platzhalter})",
            con, params=whitelist,
        )
        kanaele = pd.read_sql_query(
            f"SELECT channel_id, title, published_at AS kanal_erstellt, video_count AS api_video_count "
            f"FROM channels WHERE channel_id IN ({platzhalter})",
            con, params=whitelist,
        )
    finally:
        con.close()

    kanaele = pd.DataFrame({"channel_id": whitelist}).merge(kanaele, on="channel_id", how="left")
    medientyp = lade_medientyp().drop_duplicates("channel_id")
    kanaele = kanaele.merge(medientyp, on="channel_id", how="left")
    kanaele["medientyp"] = kanaele["medientyp"].fillna("unbekannt")
    kanaele["title"] = kanaele["title"].fillna(kanaele["channel_id"])

    videos["quartal"] = (
        pd.to_datetime(videos["published_at"], utc=True, errors="coerce")
        .dt.tz_localize(None).dt.to_period("Q")
    )
    n_registry_gesamt = videos.groupby("channel_id").size().rename("n_registry_gesamt")
    kanaele = kanaele.merge(n_registry_gesamt, on="channel_id", how="left")
    videos = videos[(videos["quartal"] >= QUARTAL_START) & (videos["quartal"] <= QUARTAL_ENDE)]
    return videos, kanaele


def zaehle(videos, kanaele):
    quartale = pd.period_range(QUARTAL_START, QUARTAL_ENDE, freq="Q")
    gitter = pd.MultiIndex.from_product([kanaele["channel_id"], quartale], names=["channel_id", "quartal"])
    lang = (
        videos.assign(ohne_views=videos["view_count"].isna())
        .groupby(["channel_id", "quartal"])
        .agg(n_videos=("published_at", "size"), n_ohne_views=("ohne_views", "sum"))
        .reindex(gitter, fill_value=0)
        .reset_index()
    )
    lang = lang.merge(kanaele[["channel_id", "title", "medientyp"]], on="channel_id", how="left")
    return lang


def finde_auffaelligkeiten(lang, kanaele):
    flags = []

    def flag(zeile, typ, detail, quartal=None, fehlend=None):
        flags.append({
            "channel_id": zeile["channel_id"], "title": zeile["title"], "medientyp": zeile["medientyp"],
            "flag": typ, "quartal": str(quartal) if quartal is not None else "", "detail": detail,
            "geschaetzt_fehlend": round(fehlend) if fehlend is not None else None,
        })

    kanal_info = kanaele.set_index("channel_id")
    for cid, grp in lang.groupby("channel_id", sort=False):
        grp = grp.sort_values("quartal").reset_index(drop=True)
        info = kanal_info.loc[cid]
        basis = {"channel_id": cid, "title": info["title"], "medientyp": info["medientyp"]}
        n = grp["n_videos"].to_numpy()
        aktiv = (n > 0).nonzero()[0]
        if len(aktiv) == 0:
            flag(basis, "keine_videos", "keine Videos im gesamten Beobachtungszeitraum")
            continue
        erst, letzt = aktiv[0], aktiv[-1]

        for i in range(erst + 1, letzt):
            if n[i] == 0:
                nachbarn = [n[j] for j in range(max(erst, i - NACHBARN), min(letzt, i + NACHBARN) + 1) if n[j] > 0]
                lokal = pd.Series(nachbarn).median() if nachbarn else 0
                flag(basis, "null_luecke", f"0 Videos zwischen aktiven Quartalen (Median aktiver Nachbarn {lokal:.0f})",
                     grp.loc[i, "quartal"], fehlend=lokal)

        # Einbruch nur im aktiven Zeitraum pruefen; das Anlauf-Quartal eines
        # spaeter startenden Kanals und das Auslauf-Quartal eines frueh endenden
        # Kanals sind natuerlich schwach und werden ausgelassen. Das erste
        # Beobachtungsquartal (erst == 0) bleibt drin (Linkstrunkierung).
        von = erst + 1 if erst > 0 else erst
        bis = letzt - 1 if letzt < len(n) - 1 else letzt
        for i in range(von, bis + 1):
            if n[i] == 0:
                continue  # schon als null_luecke erfasst
            nachbarn = [n[j] for j in range(max(erst, i - NACHBARN), min(letzt, i + NACHBARN) + 1) if j != i]
            lokal = pd.Series(nachbarn).median()
            if lokal >= MIN_LOKALER_MEDIAN and n[i] < EINBRUCH_FAKTOR * lokal:
                flag(basis, "einbruch", f"{n[i]} Videos vs. lokaler Median {lokal:.0f}", grp.loc[i, "quartal"],
                     fehlend=lokal - n[i])

        # Anhaltende Luecke: mehrere schwache Quartale am Stueck entgehen dem
        # lokalen Median (Nachbarn ebenfalls schwach). Referenz ist daher das
        # Niveau, das der Kanal VOR und NACH dem Quartal jeweils schon einmal
        # erreicht hat (Minimum der beiden Maxima).
        bereits = {f["quartal"] for f in flags if f["channel_id"] == cid}
        for i in range(erst + 1, letzt):
            q = str(grp.loc[i, "quartal"])
            if n[i] == 0 or q in bereits:
                continue
            ref = min(n[erst:i].max(), n[i + 1:letzt + 1].max())
            if ref >= MIN_REF_ANHALTEND and n[i] < ANHALTEND_FAKTOR * ref:
                flag(basis, "anhaltende_luecke", f"{n[i]} Videos vs. Niveau davor/danach {ref}",
                     grp.loc[i, "quartal"], fehlend=ref - n[i])

        n_reg, n_api = info["n_registry_gesamt"], info["api_video_count"]
        if pd.notna(n_reg) and n_reg >= PLAYLIST_LIMIT_SCHWELLE and pd.notna(n_api) \
                and n_reg < MIN_ANTEIL_REGISTRY_VS_API * n_api:
            flag(basis, "playlist_limit",
                 f"Registry {int(n_reg)} / API video_count {int(n_api)} — Uploads-Playlist liefert max. "
                 f"~20.000 Videos, ältere/mittlere Zeiträume vermutlich unvollständig")
        if letzt < len(n) - 1:
            flag(basis, "fruehes_ende", f"letzte Videos {grp.loc[letzt, 'quartal']}", grp.loc[letzt, "quartal"])

        for _, z in grp.iterrows():
            if z["n_videos"] >= MIN_VIDEOS_FUER_STATS_FLAG and z["n_ohne_views"] / z["n_videos"] >= MAX_ANTEIL_OHNE_VIEWS:
                flag(basis, "fehlende_stats",
                     f"{z['n_ohne_views']}/{z['n_videos']} Videos ohne view_count", z["quartal"])

    return pd.DataFrame(flags, columns=["channel_id", "title", "medientyp", "flag", "quartal", "detail",
                                        "geschaetzt_fehlend"])


def schreibe_readme(lang, kanaele, flags):
    breit = lang.pivot(index="title", columns="quartal", values="n_videos")
    zeilen = [
        "# Videos pro Quartal (Frage-1-Whitelist) — Datenlücken-Screening",
        "",
        "Erzeugt von `scripts/adhoc/videos_pro_quartal_whitelist.py` direkt aus "
        "`data/store/video_registry.sqlite` (Tabelle `videos`, alle Videos ohne Filter). "
        f"{len(kanaele)} Whitelist-Kanäle, Quartale {QUARTAL_START}–{QUARTAL_ENDE}.",
        "",
        "## Heuristiken",
        "",
        "| Flag | Bedeutung |",
        "| --- | --- |",
        "| `null_luecke` | 0 Videos in einem Quartal, obwohl der Kanal davor und danach Videos hat |",
        f"| `einbruch` | < {EINBRUCH_FAKTOR:.0%} des Medians der ±{NACHBARN} Nachbarquartale (lokaler Median ≥ {MIN_LOKALER_MEDIAN}) |",
        f"| `anhaltende_luecke` | < {ANHALTEND_FAKTOR:.0%} des Niveaus, das der Kanal davor und danach schon erreicht hat (Referenz ≥ {MIN_REF_ANHALTEND}); erkennt mehrquartalige Lücken |",
        f"| `playlist_limit` | Registry ≥ {PLAYLIST_LIMIT_SCHWELLE} Videos, aber < {MIN_ANTEIL_REGISTRY_VS_API:.0%} des API-Bestands → ~20.000er-Limit der Uploads-Playlist |",
        "| `fruehes_ende` | keine Videos bis zum Beobachtungsende (Kanal inaktiv oder Nachscraping fehlt) |",
        f"| `fehlende_stats` | ≥ {MAX_ANTEIL_OHNE_VIEWS:.0%} der Videos ohne view_count (bei ≥ {MIN_VIDEOS_FUER_STATS_FLAG} Videos) |",
        "| `keine_videos` | keine Videos im gesamten Zeitraum |",
        "",
        "`geschaetzt_fehlend` = lokaler Median minus beobachtete Anzahl (bzw. API minus Registry) — "
        "grobe Größenordnung, keine exakte Zahl. Die Flags sind Kandidaten, keine Befunde: ein "
        "Einbruch kann auch eine echte Pause, ein Formatwechsel oder gelöschte Videos sein. Vor einem "
        "Nachscraping am YouTube-Kanal selbst prüfen.",
        "",
        "## Anzahl Flags",
        "",
        "| Flag | Kanäle | Zeilen | Σ geschätzt fehlend |",
        "| --- | --- | --- | --- |",
    ]
    for typ, g in flags.groupby("flag"):
        zeilen.append(f"| `{typ}` | {g['channel_id'].nunique()} | {len(g)} | {g['geschaetzt_fehlend'].sum():.0f} |")

    luecken = flags[flags["flag"].isin(["null_luecke", "einbruch", "anhaltende_luecke"])]
    zeilen += ["", "## Lücken/Einbrüche je Quartal (systematische Ausfälle?)", "",
               "| Quartal | Kanäle mit Flag | Σ geschätzt fehlend |", "| --- | --- | --- |"]
    for q, g in luecken.groupby("quartal"):
        zeilen.append(f"| {q} | {g['channel_id'].nunique()} | {g['geschaetzt_fehlend'].sum():.0f} |")

    top = luecken.sort_values("geschaetzt_fehlend", ascending=False).head(TOP_N)
    zeilen += ["", f"## Top {TOP_N} nach geschätzt fehlenden Videos", "",
               "| Kanal | Medientyp | Flag | Quartal | geschätzt fehlend | Detail |",
               "| --- | --- | --- | --- | --- | --- |"]
    for _, f in top.iterrows():
        zeilen.append(f"| {f['title']} | {f['medientyp']} | `{f['flag']}` | {f['quartal']} | "
                      f"{f['geschaetzt_fehlend']:.0f} | {f['detail']} |")

    zeilen += ["", "## Alle Flags", "", "| Kanal | Medientyp | Flag | Quartal | Detail |", "| --- | --- | --- | --- | --- |"]
    for _, f in flags.sort_values(["flag", "title", "quartal"]).iterrows():
        zeilen.append(f"| {f['title']} | {f['medientyp']} | `{f['flag']}` | {f['quartal']} | {f['detail']} |")

    betroffen = top["title"].unique()
    if len(betroffen):
        zeilen += ["", f"## Quartalsverlauf der Kanäle aus den Top {TOP_N}", ""]
        tab = breit.loc[sorted(betroffen)]
        zeilen.append("| Kanal | " + " | ".join(str(q) for q in tab.columns) + " |")
        zeilen.append("| --- " * (len(tab.columns) + 1) + "|")
        for titel, r in tab.iterrows():
            zeilen.append(f"| {titel} | " + " | ".join(str(int(v)) for v in r) + " |")
    (ERGEBNIS_ORDNER / "README.md").write_text("\n".join(zeilen) + "\n", encoding="utf-8")


def main():
    ERGEBNIS_ORDNER.mkdir(parents=True, exist_ok=True)
    videos, kanaele = lade_daten()
    lang = zaehle(videos, kanaele)
    flags = finde_auffaelligkeiten(lang, kanaele)

    lang_out = lang.assign(quartal=lang["quartal"].astype(str))
    lang_out.to_csv(ERGEBNIS_ORDNER / "videos_pro_quartal_lang.csv", index=False, encoding="utf-8")
    breit = lang_out.pivot_table(index=["channel_id", "title", "medientyp"], columns="quartal",
                                 values="n_videos", dropna=False).reset_index()
    breit.to_csv(ERGEBNIS_ORDNER / "videos_pro_quartal_breit.csv", index=False, encoding="utf-8")
    flags.to_csv(ERGEBNIS_ORDNER / "auffaelligkeiten.csv", index=False, encoding="utf-8")
    schreibe_readme(lang, kanaele, flags)

    print(f"{len(kanaele)} Kanäle, {int(lang['n_videos'].sum())} Videos im Zeitraum")
    print(flags["flag"].value_counts().to_string())
    print(f"-> {ERGEBNIS_ORDNER}")


if __name__ == "__main__":
    main()

"""Keyword-Themenklassifikation der Transkript-Segmente der gezogenen Video-IDs.

Wendet die beiden Klassifikatoren aus
`scripts/adhoc/keyword_klassifikation_segmente.py` (Plan
`.claude/plans/keyword_klassifikation.md`) auf alle Segmente der Videos an,
die `scripts/adhoc/random_video_ids_for_channel_period.py` gezogen hat
(`ID_DATEI`, Standard `video_ids_angebot_2022-06-02_2022-11-02.csv`,
22.034 long-Videos aus 108 Kanälen, 06.01.–26.10.2022).

Ablauf
------
1. **Verfügbarkeit**: Abgleich der IDs mit dem `transcript_store`
   (`attempted_video_ids()`, `has_transcript()`); nur Videos mit Transkript
   werden verarbeitet.
2. **Training (einmal)** auf allen 9.214 LLM-kodierten Segmenten der
   Angebotsstudie (`results_segment_level.csv`, nur `kodierbar == 1`):
   - Dict: Mindest-Trefferzahl je Label F1-optimal (Lexika
     `LEXIKON_THEMEN`/`LEXIKON_ASPEKTE` aus dem Ad-hoc-Skript).
   - LR: TF-IDF + logistische Regression je Label, Schwelle per nach
     **Kanal** gruppierter CV (wie im Modus "kanal" des Ad-hoc-Skripts, da
     86 der 108 Kanäle nicht im Training vorkommen).
   - Aspekte nur auf LLM-Kriegssegmenten trainiert.
   Die Modelle werden in `MODELL_DATEI` gespeichert und bei weiteren Läufen
   wiederverwendet (`MODELL_NEU_TRAINIEREN = False`), damit alle Batches
   und Teil-Läufe mit identischen Modellen klassifiziert werden.
3. **Batches**: je `BATCH_GROESSE` Videos werden die Transkripte aus dem
   Store geholt, mit der Logik der Angebotsstudie
   (`data/claude_classification/aufbereitung_angebotsstudie.py`:
   `transcript_to_text`, `split_segments`, ca. 800 Wörter, gleiche anonyme
   Segment-IDs) segmentiert, kleingeschrieben und klassifiziert. Ergebnisse
   werden nach jedem Batch an die Ausgabedateien angehängt; danach wird der
   Speicher freigegeben. Nur die Modelle und ein Batch liegen gleichzeitig
   im RAM.
4. **Fortsetzen**: Mit `FORTSETZEN = True` werden Videos übersprungen, die
   in `video_status.csv` schon stehen. Ein abgebrochener Lauf setzt so am
   letzten vollständigen Batch an. Videos ohne Transkript werden NICHT in
   den Status geschrieben. Ein späterer Lauf nimmt sie also mit, sobald
   der Download sie nachgeliefert hat.
5. **Abschluss**: Video-Aggregation (wortgewichtete Anteile wie
   `segment_weight` in `process_results.py`) und kurzer Markdown-Bericht.

Ausgaben (`OUTPUT_DIR`)
-----------------------
- `segmente_klassifiziert.csv`: eine Zeile je Segment. Metadaten
  (`segment_id`, `video_id`, `channel_id`, `channel_title`,
  `media_category`, `datum`, `woche`, `segment_index`, `n_segmente_video`,
  `n_woerter`, `im_training`), danach `dict_<thema>`, `lr_<thema>`
  (0/1, 15 Themen), `dict_a_<aspekt>`, `lr_a_<aspekt>` (0/1, 15 Aspekte,
  End-to-End: nur wenn derselbe Klassifikator `krieg_ukraine` erkennt),
  `lr_p_<thema>` (LR-Wahrscheinlichkeit), `hauptthema_dict`,
  `hauptthema_lr`, optional `text` (`TEXT_SPEICHERN`).
- `video_status.csv`: `video_id`, `aufbereitung` (`segmentiert`/`zu_kurz`),
  `n_segmente`.
- `videos_klassifiziert.csv`: Video-Ebene, wortgewichteter Anteil je Label.
- `bericht.md`: Fallzahlen, Monatsanteile je Thema und Klassifikator.
- `modelle.joblib`: trainierte Modelle, Vektorisierer und Schwellen.

`im_training = 1` markiert Videos, deren Segmente im Trainingsset liegen
(2.210 der gezogenen Videos aus Jan–Apr 2022). Für diese sind die
Vorhersagen in-sample und daher zu optimistisch. Für Vergleiche mit dem LLM
nicht verwenden.

Einschränkung (siehe Plan): Die Klassifikatoren sind nur für Jan–Apr 2022
validiert. Für Mai–Okt 2022 ist die Güte ungetestet, weil sich das Vokabular
verschiebt. Ergebnisse dienen als Vorfilter für große Verschiebungen
(≳ 5 Prozentpunkte) bei häufigen Themen, nicht als Befund.

Ressourcen: Training ca. 3–5 min, danach pro Batch à 500 Videos grob
< 1 min. Speicherbedarf < 2 GB. Aufruf aus dem Repo-Root (sklearn nötig):
    .venv/Scripts/python -m youtube_code.step3_topic_relevance.classify_segment_topics
"""

from __future__ import annotations

import ast
import gc
import importlib.util
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from youtube_code.config import ADHOC_OUTPUT, ROOT
from youtube_code.store.transcript_store import attempted_video_ids, get_transcripts, has_transcript

# ============================================================================
# KONFIGURATION
# ============================================================================
ID_DATEI = ADHOC_OUTPUT / "video_ids_angebot_2022-06-02_2022-11-02.csv"  # CSV mit Spalte video_id
                                                     # (+ channel_id, channel_title, media_category, datum, woche)
KEYWORD_SKRIPT = ROOT / "scripts" / "adhoc" / "keyword_klassifikation_segmente.py"  # Lexika + Klassifikator-Funktionen
AUFBEREITUNG_SKRIPT = ROOT / "data" / "claude_classification" / "aufbereitung_angebotsstudie.py"  # Segmentierung
OUTPUT_DIR = ROOT / "scripts" / "adhoc" / "keyword_klassifikation_segmente" / "anwendung_2022"  # Ausgabeordner
MODELL_DATEI = OUTPUT_DIR / "modelle.joblib"  # gespeicherte Modelle (wird angelegt)
KLASSIFIKATOREN = ["dict", "lr"]  # Teilmenge von ["dict", "lr"]
BATCH_GROESSE = 500               # Videos je Batch (int, 50..5000; kleiner = weniger RAM)
FORTSETZEN = True                 # True = bereits verarbeitete Videos (video_status.csv) überspringen;
                                  # False = Ausgabedateien (außer Modellen) löschen und neu beginnen
MODELL_NEU_TRAINIEREN = False     # True = Modelle neu schätzen, auch wenn MODELL_DATEI existiert
                                  # (nur zusammen mit FORTSETZEN = False sinnvoll)
TEXT_SPEICHERN = False            # True = Segmenttext in segmente_klassifiziert.csv mitschreiben (Datei wird groß)
MAX_BATCHES = None            # None = alle; int >= 1 = nach so vielen Batches stoppen (Testlauf)
# ============================================================================

SEGMENT_DATEI = OUTPUT_DIR / "segmente_klassifiziert.csv"
STATUS_DATEI = OUTPUT_DIR / "video_status.csv"
VIDEO_DATEI = OUTPUT_DIR / "videos_klassifiziert.csv"
BERICHT_DATEI = OUTPUT_DIR / "bericht.md"
META_SPALTEN = ["channel_id", "channel_title", "media_category", "datum", "woche"]


def lade_modul(name: str, pfad: Path):
    """Skript als Modul laden (ohne main() auszuführen)."""
    spec = importlib.util.spec_from_file_location(name, pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


# ----------------------------------------------------------------------------
# Training
# ----------------------------------------------------------------------------
def trainiere(kw) -> dict:
    """Beide Klassifikatoren auf allen kodierbaren LLM-Segmenten schätzen."""
    df = pd.read_csv(kw.INPUT_CSV, encoding="utf-8")
    df = df[df["kodierbar"] == 1].reset_index(drop=True)
    df["text"] = df["text"].fillna("").str.lower()
    for col in ["themen", "krieg_aspekte"]:
        df[col] = df[col].apply(ast.literal_eval)
    Y_t = kw.multi_hot(df["themen"], kw.THEMEN)
    Y_a = kw.multi_hot(df["krieg_aspekte"], kw.ASPEKTE)
    krieg = Y_t["krieg_ukraine"].values == 1
    pol = [l for l in kw.THEMEN if l != "unpolitisch"]
    print(f"[Training] {len(df):,} Segmente, {df.channel_id.nunique()} Kanäle, davon Krieg: {krieg.sum():,}",
          flush=True)

    hits_t = kw.count_hits(df["text"], kw.LEXIKON_THEMEN)
    hits_a = kw.count_hits(df["text"], kw.LEXIKON_ASPEKTE)
    thr_dict_t = kw.fit_dictionary(hits_t, Y_t[pol])
    thr_dict_a = kw.fit_dictionary(hits_a[krieg], Y_a[krieg][list(kw.LEXIKON_ASPEKTE)])
    print("[Training] Diktionär fertig", flush=True)

    # identische Vektorisierer-Einstellungen wie fit_predict() im Ad-hoc-Skript
    vec = TfidfVectorizer(min_df=kw.TFIDF_MIN_DF, max_df=0.5, ngram_range=(1, kw.TFIDF_NGRAM_MAX),
                          sublinear_tf=True, max_features=150_000, token_pattern=r"(?u)\b\w\w+\b")
    X = vec.fit_transform(df["text"])
    gruppen = df["channel_id"].values
    lr_t_models, lr_t_thr = kw.fit_lr(X, Y_t, gruppen)
    lr_a_models, lr_a_thr = kw.fit_lr(X[krieg], Y_a[krieg], gruppen[krieg])
    print("[Training] Logistische Regression fertig", flush=True)

    return {"thr_dict_t": thr_dict_t, "thr_dict_a": thr_dict_a, "vec": vec,
            "lr_t_models": lr_t_models, "lr_t_thr": lr_t_thr,
            "lr_a_models": lr_a_models, "lr_a_thr": lr_a_thr,
            "trainings_videos": set(df["video_id"]),
            "trainiert_am": time.strftime("%Y-%m-%d %H:%M")}


# ----------------------------------------------------------------------------
# Segmentierung und Klassifikation je Batch
# ----------------------------------------------------------------------------
def segmentiere_batch(aufb, transkripte: dict) -> tuple[pd.DataFrame, list[tuple]]:
    zeilen, status = [], []
    for vid, rec in transkripte.items():
        text = aufb.transcript_to_text(rec.get("transcript_segments"))
        if text is None:
            status.append((vid, "zu_kurz", 0))
            continue
        teile = aufb.split_segments(text)
        anon = aufb.anonyme_video_kennung(vid)
        for i, t in enumerate(teile):
            zeilen.append({"segment_id": f"{anon}_s{i:03d}", "video_id": vid, "segment_index": i,
                           "n_segmente_video": len(teile), "n_woerter": len(t.split()), "text": t})
        status.append((vid, "segmentiert", len(teile)))
    return pd.DataFrame(zeilen), status


def klassifiziere(kw, modelle: dict, texte: pd.Series) -> pd.DataFrame:
    """Vorhersagen beider Klassifikatoren (Logik wie fit_predict() im Ad-hoc-Skript)."""
    pol = [l for l in kw.THEMEN if l != "unpolitisch"]
    teile = []
    if "dict" in KLASSIFIKATOREN:
        ht = kw.count_hits(texte, kw.LEXIKON_THEMEN)
        ha = kw.count_hits(texte, kw.LEXIKON_ASPEKTE)
        pd_t = kw.predict_dictionary(ht, modelle["thr_dict_t"])
        pd_t["unpolitisch"] = (pd_t[pol].sum(axis=1) == 0).astype(int)
        pd_t = pd_t[kw.THEMEN]
        pd_a = kw.predict_dictionary(ha, modelle["thr_dict_a"])
        pd_a["sonstiges"] = 0
        pd_a = pd_a[kw.ASPEKTE].mul(pd_t["krieg_ukraine"], axis=0)  # End-to-End
        scores = ht / pd.Series(modelle["thr_dict_t"])
        scores["unpolitisch"] = 0.0
        teile += [pd_t.add_prefix("dict_"), pd_a.add_prefix("dict_a_"),
                  kw.hauptthema_from_scores(scores, pd_t).rename("hauptthema_dict")]
    if "lr" in KLASSIFIKATOREN:
        X = modelle["vec"].transform(texte)
        plr_t, prob_t = kw.predict_lr(modelle["lr_t_models"], modelle["lr_t_thr"], X, texte.index, kw.THEMEN)
        plr_a, _ = kw.predict_lr(modelle["lr_a_models"], modelle["lr_a_thr"], X, texte.index, kw.ASPEKTE)
        plr_a = plr_a.mul(plr_t["krieg_ukraine"], axis=0)  # End-to-End
        teile += [plr_t.add_prefix("lr_"), plr_a.add_prefix("lr_a_"), prob_t.round(4).add_prefix("lr_p_"),
                  kw.hauptthema_from_scores(prob_t, plr_t).rename("hauptthema_lr")]
    return pd.concat(teile, axis=1)


def haenge_an(df: pd.DataFrame, pfad: Path) -> None:
    """An CSV anhängen; bricht ab, wenn die Spalten nicht zur vorhandenen Datei passen
    (z. B. KLASSIFIKATOREN oder TEXT_SPEICHERN zwischen zwei Läufen geändert)."""
    if pfad.exists():
        kopf = list(pd.read_csv(pfad, nrows=0).columns)
        if kopf != list(df.columns):
            sys.exit(f"Spalten passen nicht zu {pfad.name} (Konfiguration geändert?). FORTSETZEN = False setzen.")
    df.to_csv(pfad, mode="a", header=not pfad.exists(), index=False, encoding="utf-8")


# ----------------------------------------------------------------------------
# Fortsetzen / Abschluss
# ----------------------------------------------------------------------------
def bereite_ausgabe_vor() -> set:
    """Gibt die bereits fertig verarbeiteten video_ids zurück; räumt Reste eines Abbruchs auf."""
    if not FORTSETZEN:
        for f in (SEGMENT_DATEI, STATUS_DATEI, VIDEO_DATEI, BERICHT_DATEI):
            f.unlink(missing_ok=True)
        return set()
    if not STATUS_DATEI.exists():
        SEGMENT_DATEI.unlink(missing_ok=True)
        return set()
    fertig = set(pd.read_csv(STATUS_DATEI, usecols=["video_id"])["video_id"])
    if SEGMENT_DATEI.exists():
        # Segmente eines abgebrochenen Batches (geschrieben, aber ohne Status) entfernen
        seg = pd.read_csv(SEGMENT_DATEI, encoding="utf-8", low_memory=False)
        rest = ~seg["video_id"].isin(fertig)
        if rest.any():
            print(f"[Fortsetzen] entferne {rest.sum():,} Segmente eines unvollständigen Batches", flush=True)
            seg[~rest].to_csv(SEGMENT_DATEI, index=False, encoding="utf-8")
        del seg
    return fertig


def label_spalten(spalten) -> list[str]:
    return [c for c in spalten if c.startswith(("dict_", "lr_")) and not c.startswith("lr_p_")]


def aggregiere_videos() -> pd.DataFrame:
    """Wortgewichteter Anteil je Label und Video (wie segment_weight in process_results.py)."""
    kopf = pd.read_csv(SEGMENT_DATEI, nrows=0).columns
    labs = label_spalten(kopf)
    seg = pd.read_csv(SEGMENT_DATEI, usecols=["video_id", "n_woerter", *META_SPALTEN, "im_training", *labs],
                      encoding="utf-8", low_memory=False)
    gew = seg["n_woerter"] / seg.groupby("video_id")["n_woerter"].transform("sum")
    anteile = seg[labs].mul(gew, axis=0).groupby(seg["video_id"]).sum().round(4)
    meta = seg.groupby("video_id").agg(**{c: (c, "first") for c in [*META_SPALTEN, "im_training"]},
                                       n_segmente=("n_woerter", "size"), n_woerter=("n_woerter", "sum"))
    return meta.join(anteile).reset_index()


def schreibe_bericht(kw, videos: pd.DataFrame, n_ids: int, n_versucht: int, n_verfuegbar: int,
                     status: pd.DataFrame, modelle: dict) -> None:
    v = videos[videos["im_training"] == 0].copy()
    v["monat"] = pd.to_datetime(v["datum"]).dt.to_period("M").astype(str)
    L = ["# Keyword-Themenklassifikation – Anwendung auf die gezogenen Video-IDs", "",
         f"ID-Datei: `{ID_DATEI.relative_to(ROOT).as_posix()}`. Modelle trainiert am {modelle['trainiert_am']} "
         f"auf allen LLM-kodierten Segmenten der Angebotsstudie (Jan–Apr 2022).", "",
         f"- Gezogene IDs: {n_ids:,}; mit Scrape-Versuch: {n_versucht:,}; mit Transkript: {n_verfuegbar:,}",
         f"- Verarbeitet: {len(status):,} Videos, davon segmentiert "
         f"{(status.aufbereitung == 'segmentiert').sum():,}, zu kurz {(status.aufbereitung == 'zu_kurz').sum():,}",
         f"- Segmente: {int(status.n_segmente.sum()):,}; Videos im Trainingsset (unten ausgeschlossen): "
         f"{int(videos.im_training.sum()):,}", "",
         "**Achtung:** Für Mai–Okt 2022 sind die Klassifikatoren nicht validiert. Nur große Verschiebungen "
         "(≳ 5 Prozentpunkte) bei häufigen Themen als Hinweis werten.", "",
         "## Wortgewichtete Themenanteile je Monat (Mittel über Videos, ohne Trainingsvideos)", ""]
    for k in KLASSIFIKATOREN:
        spalten = [f"{k}_{t}" for t in kw.THEMEN]
        tab = v.groupby("monat")[spalten].mean()
        tab.columns = kw.THEMEN
        tab.insert(0, "Videos", v.groupby("monat").size())
        L += [f"### {k.upper()}", "", kw.md_table(tab.reset_index(), "{:.3f}"), ""]
    L += ["## Kriegsaspekte je Monat (Anteil am Videotext, End-to-End)", ""]
    for k in KLASSIFIKATOREN:
        spalten = [f"{k}_a_{a}" for a in kw.ASPEKTE]
        tab = v.groupby("monat")[spalten].mean()
        tab.columns = kw.ASPEKTE
        L += [f"### {k.upper()}", "", kw.md_table(tab.reset_index(), "{:.3f}"), ""]
    BERICHT_DATEI.write_text("\n".join(L), encoding="utf-8")


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main() -> None:
    if not ID_DATEI.exists():
        sys.exit(f"ID_DATEI fehlt: {ID_DATEI}")
    for f in (KEYWORD_SKRIPT, AUFBEREITUNG_SKRIPT):
        if not f.exists():
            sys.exit(f"Skript fehlt: {f}")
    if not KLASSIFIKATOREN or not set(KLASSIFIKATOREN) <= {"dict", "lr"}:
        sys.exit('KLASSIFIKATOREN muss eine nicht-leere Teilmenge von ["dict", "lr"] sein.')
    if not (isinstance(BATCH_GROESSE, int) and 50 <= BATCH_GROESSE <= 5000):
        sys.exit("BATCH_GROESSE muss eine ganze Zahl zwischen 50 und 5000 sein.")
    if MAX_BATCHES is not None and not (isinstance(MAX_BATCHES, int) and MAX_BATCHES >= 1):
        sys.exit("MAX_BATCHES muss None oder eine ganze Zahl >= 1 sein.")
    if MODELL_NEU_TRAINIEREN and FORTSETZEN and STATUS_DATEI.exists():
        sys.exit("MODELL_NEU_TRAINIEREN = True mit FORTSETZEN = True würde alte und neue Modelle mischen. "
                 "FORTSETZEN = False setzen.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    kw = lade_modul("keyword_klassifikation_segmente", KEYWORD_SKRIPT)
    aufb = lade_modul("aufbereitung_angebotsstudie", AUFBEREITUNG_SKRIPT)

    # --- 1. IDs und Verfügbarkeit -------------------------------------------
    ids_df = pd.read_csv(ID_DATEI, dtype={"video_id": "string", "channel_id": "string"})
    fehlt = {"video_id", *META_SPALTEN} - set(ids_df.columns)
    if fehlt:
        sys.exit(f"ID_DATEI ohne Spalten {sorted(fehlt)}")
    ids_df = ids_df.drop_duplicates("video_id").set_index("video_id")
    ids = set(ids_df.index)
    versucht = ids & attempted_video_ids()
    verfuegbar = has_transcript(ids)
    print(f"{len(ids):,} IDs gezogen, {len(versucht):,} mit Scrape-Versuch, {len(verfuegbar):,} mit Transkript.")
    print(f"Kanäle: {ids_df.channel_id.nunique()}; Kanäle mit Transkripten: "
          f"{ids_df.loc[list(verfuegbar), 'channel_id'].nunique()}", flush=True)

    # --- 2. Modelle -----------------------------------------------------------
    if MODELL_DATEI.exists() and not MODELL_NEU_TRAINIEREN:
        modelle = joblib.load(MODELL_DATEI)
        print(f"[Training] Modelle geladen ({MODELL_DATEI.name}, trainiert am {modelle['trainiert_am']})")
    else:
        t0 = time.time()
        modelle = trainiere(kw)
        joblib.dump(modelle, MODELL_DATEI)
        print(f"[Training] gespeichert nach {MODELL_DATEI} ({time.time() - t0:.0f} s)", flush=True)

    # --- 3. Batches -----------------------------------------------------------
    fertig = bereite_ausgabe_vor()
    offen = sorted(verfuegbar - fertig)
    batches = [offen[i:i + BATCH_GROESSE] for i in range(0, len(offen), BATCH_GROESSE)]
    if MAX_BATCHES is not None:
        batches = batches[:MAX_BATCHES]
    print(f"Bereits verarbeitet: {len(fertig):,} Videos; offen: {len(offen):,} -> {len(batches)} Batches "
          f"à {BATCH_GROESSE}", flush=True)

    t0 = time.time()
    for b, batch in enumerate(batches, 1):
        transkripte = get_transcripts(batch)
        seg, status = segmentiere_batch(aufb, transkripte)
        del transkripte
        if len(seg):
            seg["text"] = seg["text"].str.lower()
            pred = klassifiziere(kw, modelle, seg["text"])
            meta = ids_df.loc[seg["video_id"], META_SPALTEN].reset_index(drop=True)
            meta["im_training"] = seg["video_id"].isin(modelle["trainings_videos"]).astype(int).values
            spalten = ["segment_id", "video_id", "segment_index", "n_segmente_video", "n_woerter"]
            out = pd.concat([seg[spalten], meta, pred], axis=1)
            if TEXT_SPEICHERN:
                out["text"] = seg["text"]
            haenge_an(out, SEGMENT_DATEI)
            del pred, meta, out
        # Status erst nach den Segmenten schreiben (Grundlage fürs Fortsetzen)
        haenge_an(pd.DataFrame(status, columns=["video_id", "aufbereitung", "n_segmente"]), STATUS_DATEI)
        n_seg = len(seg)
        del seg, status
        gc.collect()
        dauer = time.time() - t0
        print(f"Batch {b}/{len(batches)}: {len(batch)} Videos, {n_seg:,} Segmente | "
              f"{dauer / 60:.1f} min, Rest ca. {dauer / b * (len(batches) - b) / 60:.1f} min", flush=True)

    # --- 4. Abschluss ---------------------------------------------------------
    if not SEGMENT_DATEI.exists():
        print("Keine Segmente klassifiziert.")
        return
    videos = aggregiere_videos()
    videos.to_csv(VIDEO_DATEI, index=False, encoding="utf-8")
    status_alle = pd.read_csv(STATUS_DATEI)
    schreibe_bericht(kw, videos, len(ids), len(versucht), len(verfuegbar), status_alle, modelle)
    print(f"Fertig. {len(videos):,} Videos klassifiziert -> {OUTPUT_DIR}")
    if len(verfuegbar) < len(ids):
        print(f"Hinweis: {len(ids) - len(verfuegbar):,} IDs noch ohne Transkript; nach weiterem Download "
              "mit FORTSETZEN = True erneut starten.")


if __name__ == "__main__":
    main()

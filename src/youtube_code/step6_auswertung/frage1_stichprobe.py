# -*- coding: utf-8 -*-
"""
frage1_stichprobe.py

Dokumentiert und erzeugt die Kanal-Stichprobe fuer Forschungsfrage 1
(.claude/CLAUDE.md) explizit und nachvollziehbar, statt das implizit in den
Analyseskripten zu verstecken. Beantwortet drei Fragen in EINER
Uebersichtsdatei:
  - An welchen Stellen fliegen Kanaele aus dem Sample (und warum)?
  - Welche Kanaele kommen wo dazu / fehlen auf einer Seite des Kriegsbeginns?
  - Wie genau wird "Baseline" und "Veraenderung" gemessen?

Auswahltrichter (Funnel), in dieser Reihenfolge:
  0. Kanonisches Sample: channel_sample_provenance.csv (ANALYSIS_ID),
     eligible_current_analysis == True (siehe step1_sample/README.md).
  1. Mindestens MIN_KRIEGSVIDEOS (Default 5) Kriegsvideos IM GESAMTEN
     Upload-Verlauf des Kanals (nicht nur unter den fuer die LLM-
     Klassifikation ausgewaehlten Videos) - Spalte topic_vids aus
     scripts/adhoc/output/topic_vids_per_channel.csv. Diese Datei zaehlt
     is_relevant==True aus der Tabelle video_topic_relevance (Topic
     "russia_ukraine_war", Keyword-Klassifikation aus step3_war_videos) ueber
     ALLE Videos des Kanals seit 24.02.2021, siehe
     scripts/adhoc/sample_creation_diagnostics.py::create_channel_overview().
  2. Mindestens MIN_KLASSIFIZIERTE_VIDEOS (Default 5) Videos mit gueltiger
     Populismus-Klassifikation (channel_video_populism.csv, Output von
     prepare_channel_scores.py).

Stufe 0-2 ergeben zusammen die WHITELIST fuer alle Frage-1-artigen
Vorkriegs/Nachkriegs-Vergleiche (frage1_populismus_bericht.py und
frage1_stance_bericht.py per WHITELIST-Import, deskriptiv_aggregation.py per
KANAL_WHITELIST) - Stufe 2 prueft dabei bewusst nur die Populismus-
Klassifikation (channel_video_populism.csv), nicht die Position-
Klassifikation, da beide Prompts auf praktisch derselben Kanalmenge laufen
(siehe frage1_stance_bericht.py-Docstring). Innerhalb dieser Whitelist wird zusaetzlich - OHNE
weiter zu filtern - dokumentiert, welche Kanaele nur Vorkriegs-, nur
Nachkriegs- oder beide Beobachtungen haben (siehe Docstring in
frage1_populismus_bericht.py zur Bedeutung fuer die Post-Dummy-Regression),
sowie - ebenfalls rein informativ, ohne die Whitelist zu filtern - wie viele
Whitelist-Kanaele bei einer Mindestbesetzung von 5 bzw. 10 Baseline-Videos
fuer die Ideologie-Klassifikation (IDEOLOGIE_MIN_VIDEOS_SCHWELLEN) uebrig
blieben.

Schreibt drei Dateien nach outputs/segment_analysis/:
  - frage1_stichprobe_kanalstatus.csv: eine Zeile je Kanal aus dem
    kanonischen Sample, mit einer Spalte je Filterstufe (inkl.
    n_baseline_videos_ideologie, rein informativ) - vollstaendige
    Audit-Spur, warum ein Kanal drin oder draussen ist.
  - frage1_kanal_whitelist.csv: nur channel_id der finalen Whitelist -
    Eingabedatei fuer KANAL_WHITELIST (deskriptiv_aggregation.py) und
    WHITELIST_PFAD (frage1_populismus_bericht.py).
  - frage1_methodik_und_stichprobe.md: Erzaehltext-Uebersicht (Funnel-Tabelle,
    exakte Baseline-/Post-Definition, exakte Modellgleichung).
"""

import pandas as pd

from youtube_code.config import OUTPUTS, SAMPLES, ROOT

RESULTS_PATH = OUTPUTS / "segment_analysis"

ANALYSIS_ID = "russia_longitudinal_v1"
CHANNEL_SAMPLE_PATH = SAMPLES / ANALYSIS_ID / "channel_sample_provenance.csv"
TOPIC_VIDS_PATH = ROOT / "scripts" / "adhoc" / "output" / "topic_vids_per_channel.csv"
POPULISM_VIDEO_PATH = RESULTS_PATH / "channel_video_populism.csv"
IDEOLOGIE_KLASSIFIKATION_PATH = RESULTS_PATH / "channel_classification_ideology.csv"

MIN_KRIEGSVIDEOS = 5
MIN_KLASSIFIZIERTE_VIDEOS = 5  # Stufe 2 des Funnels: Mindestanzahl klassifizierter Baseline-Videos je Kanal
# Rein informative Schwellenwerte (siehe baue_kanalstatus()): wie viele Whitelist-Kanaele
# haben mindestens so viele Baseline-Videos in der Ideologie-Klassifikation
# (channel_classification_ideology.csv::n_videos) - filtert NICHT die Whitelist selbst,
# dient nur als Orientierung fuer eine moegliche zusaetzliche Mindestbesetzung.
IDEOLOGIE_MIN_VIDEOS_SCHWELLEN = [5, 10]

PFAD_KANALSTATUS = RESULTS_PATH / "frage1_stichprobe_kanalstatus.csv"
PFAD_WHITELIST = RESULTS_PATH / "frage1_kanal_whitelist.csv"
PFAD_METHODIK = RESULTS_PATH / "frage1_methodik_und_stichprobe.md"


# =========================================================
# FUNNEL
# =========================================================

def baue_kanalstatus():
    sample = pd.read_csv(CHANNEL_SAMPLE_PATH)
    sample["channel_id"] = sample["channel_id"].astype(str)
    kanon = sample[sample["eligible_current_analysis"] == True][["channel_id", "channel_title"]].drop_duplicates()
    n_kanon = len(kanon)
    print(f"[Stufe 0] Kanonisches Sample ({ANALYSIS_ID}, eligible_current_analysis): {n_kanon} Kanaele.")

    topic = pd.read_csv(TOPIC_VIDS_PATH)
    topic["channel_id"] = topic["channel_id"].astype(str)
    topic = topic[["channel_id", "topic_vids", "all_vids"]]

    status = kanon.merge(topic, on="channel_id", how="left")
    fehlt_topic = status["topic_vids"].isna()
    if fehlt_topic.any():
        print(f"[Warnung] {int(fehlt_topic.sum())} Kanaele aus dem kanonischen Sample fehlen in "
              f"'{TOPIC_VIDS_PATH}' (topic_vids unbekannt) -> konservativ als nicht ausreichend "
              f"behandelt (Stufe 1 = False): "
              f"{status.loc[fehlt_topic, ['channel_id', 'channel_title']].to_dict('records')}")
    status["hat_5plus_kriegsvideos"] = status["topic_vids"] >= MIN_KRIEGSVIDEOS  # NaN -> False

    n_nach_stufe1 = int(status["hat_5plus_kriegsvideos"].sum())
    print(f"[Stufe 1] >= {MIN_KRIEGSVIDEOS} Kriegsvideos (gesamter Upload-Verlauf lt. "
          f"video_topic_relevance): {n_nach_stufe1} von {n_kanon} Kanaelen.")

    pop = pd.read_csv(POPULISM_VIDEO_PATH)
    pop["channel_id"] = pop["channel_id"].astype(str)
    pro_kanal = pop.groupby("channel_id").agg(
        n_videos_klassifiziert=("video_id", "count"),
        n_vorkrieg=("rel_quartal", lambda s: int((s < 0).sum())),
        n_nachkrieg=("rel_quartal", lambda s: int((s >= 0).sum())),
    ).reset_index()

    status = status.merge(pro_kanal, on="channel_id", how="left")
    for spalte in ["n_videos_klassifiziert", "n_vorkrieg", "n_nachkrieg"]:
        status[spalte] = status[spalte].fillna(0).astype(int)

    status["hat_populismus_klassifikation"] = status["n_videos_klassifiziert"] >= MIN_KLASSIFIZIERTE_VIDEOS
    status["in_whitelist"] = status["hat_5plus_kriegsvideos"] & status["hat_populismus_klassifikation"]
    n_final = int(status["in_whitelist"].sum())
    print(f"[Stufe 2] + mind. {MIN_KLASSIFIZIERTE_VIDEOS} klassifizierte Videos: {n_final} von "
          f"{n_nach_stufe1} Kanaelen (finale Whitelist).")

    status["hat_vorkriegsdaten"] = status["n_vorkrieg"] > 0
    status["hat_nachkriegsdaten"] = status["n_nachkrieg"] > 0

    whitelist = status[status["in_whitelist"]]
    nur_vorkrieg = whitelist[~whitelist["hat_nachkriegsdaten"]]
    nur_nachkrieg = whitelist[~whitelist["hat_vorkriegsdaten"]]
    beide = whitelist[whitelist["hat_vorkriegsdaten"] & whitelist["hat_nachkriegsdaten"]]
    print(f"[Zusammensetzung Whitelist] {len(beide)} Kanaele mit Vor- UND Nachkriegsbeobachtungen, "
          f"{len(nur_vorkrieg)} nur Vorkrieg, {len(nur_nachkrieg)} nur Nachkrieg (diese beiden "
          f"Gruppen tragen NICHTS zur Schaetzung des Post-Koeffizienten bei, siehe Methodik-Datei).")

    # --- Zusatzinfo (rein informativ, filtert die Whitelist NICHT): wie viele Whitelist-
    # Kanaele haetten genug Baseline-Videos fuer eine Ideologie-Klassifikation mit
    # hoeherer Mindestbesetzung? Baseline-Videos = alle Videos, die dem Ideologie-Prompt
    # vorgelegt wurden (channel_classification_ideology.csv::n_videos, siehe
    # prepare_channel_scores.py::prepare_ideology_results() - per Konstruktion die
    # Klassifikations-Baseline aus step2_baseline_channels/select_baseline_targets()).
    # channel_classification_ideology.csv gruppiert nach channel_title statt channel_id
    # (prepare_ideology_results()) - einzelne Kanaele mit einer Titeländerung im
    # Beobachtungszeitraum haben daher dort ZWEI Zeilen mit identischer channel_id, aber
    # unterschiedlichem channel_title. Vor dem Merge auf channel_id summieren, sonst
    # dupliziert der Merge Zeilen in status (bricht die spaeteren Boolean-Indexer).
    ideologie = pd.read_csv(IDEOLOGIE_KLASSIFIKATION_PATH)
    ideologie["channel_id"] = ideologie["channel_id"].astype(str)
    dupliziert = ideologie["channel_id"].duplicated(keep=False)
    if dupliziert.any():
        print(f"[Ideologie-Baseline] {ideologie.loc[dupliziert, 'channel_id'].nunique()} channel_id(s) mit "
              f"mehreren channel_title-Zeilen in '{IDEOLOGIE_KLASSIFIKATION_PATH}' (Titeländerung) -> "
              f"n_videos je channel_id aufsummiert.")
    ideologie = ideologie.groupby("channel_id", as_index=False)["n_videos"].sum().rename(
        columns={"n_videos": "n_baseline_videos_ideologie"}
    )
    status = status.merge(ideologie, on="channel_id", how="left")
    status["n_baseline_videos_ideologie"] = status["n_baseline_videos_ideologie"].fillna(0).astype(int)
    whitelist = status[status["in_whitelist"]]  # neu einlesen, jetzt inkl. n_baseline_videos_ideologie

    ideologie_schwellen = {}
    for schwelle in IDEOLOGIE_MIN_VIDEOS_SCHWELLEN:
        n = int((whitelist["n_baseline_videos_ideologie"] >= schwelle).sum())
        ideologie_schwellen[schwelle] = n
        print(f"[Ideologie-Baseline] Innerhalb der Whitelist ({len(whitelist)} Kanaele): "
              f"{n} mit >= {schwelle} Baseline-Videos fuer die Ideologie-Klassifikation "
              f"(rein informativ, keine zusaetzliche Filterung der Whitelist).")

    kennzahlen = {
        "n_kanon": n_kanon,
        "n_stufe1": n_nach_stufe1,
        "n_final": n_final,
        "fehlt_topic": status.loc[fehlt_topic, ["channel_id", "channel_title"]],
        "zu_wenig_kriegsvideos": status[~status["hat_5plus_kriegsvideos"] & status["topic_vids"].notna()],
        "keine_klassifikation": status[status["hat_5plus_kriegsvideos"] & ~status["hat_populismus_klassifikation"]],
        "nur_vorkrieg": nur_vorkrieg,
        "nur_nachkrieg": nur_nachkrieg,
        "beide": beide,
        "ideologie_schwellen": ideologie_schwellen,
    }
    return status, kennzahlen


# =========================================================
# METHODIK-MARKDOWN
# =========================================================

def schreibe_methodik_markdown(status, k):
    beispiele_fehlt = k["fehlt_topic"][["channel_id", "channel_title"]].to_dict("records")
    beispiele_zu_wenig = (
        k["zu_wenig_kriegsvideos"][["channel_id", "channel_title", "topic_vids"]]
        .sort_values("topic_vids", ascending=False)
        .head(15)
        .to_dict("records")
    )
    beispiele_keine_klass = k["keine_klassifikation"][["channel_id", "channel_title"]].to_dict("records")

    def liste(rows, felder):
        if not rows:
            return "  (keine)\n"
        return "".join(f"  - {' | '.join(str(r[f]) for f in felder)}\n" for r in rows)

    ideologie_schwellen_zeilen = "".join(
        f"| >= {schwelle} | {n} |\n" for schwelle, n in k["ideologie_schwellen"].items()
    )

    md = f"""# Forschungsfrage 1 — Stichprobe und Methodik

Dieses Dokument haelt fest, WELCHE Kanaele in die Frage-1-Analyse
(`frage1_populismus_bericht.py`, `deskriptiv_aggregation.py` /
`deskriptiv_plots.py`) eingehen, an welcher Stelle Kanaele ausgeschlossen
werden, und WIE genau "Baseline" und "Veraenderung nach Kriegsbeginn"
gemessen werden. Erzeugt von `frage1_stichprobe.py`.

**Wiederverwendung fuer die Russland-Haltung:** Dieselbe Whitelist, dasselbe
Regressionsmodell (Abschnitt 4) und dieselben Gruppierungen (Ideologie/
Medientyp) verwendet auch `frage1_stance_bericht.py` fuer die Auswertung von
`position_russland`/`position_westpolitik`/`emotion` (Prompt `POSITION_V1`,
`channel_video_position.csv`) - inhaltlich keine der vier nummerierten
Forschungsfragen aus `.claude/CLAUDE.md`, sondern deskriptiv/inferentieller
Kontext zur selben Vorkriegs/Nachkriegs-Vergleichsanlage. Alles unten
Beschriebene (Funnel, Baseline-Definitionen, Regressionsgleichung) gilt
identisch fuer beide Berichte; nur die Zielgroesse (`DIMENSIONEN` in den
jeweiligen `frage1_*_bericht.py`) unterscheidet sich.

## 1. Auswahltrichter (Funnel)

| Stufe | Kriterium | Kanaele |
|---|---|---|
| 0 | Kanonisches Sample (`{ANALYSIS_ID}`, `eligible_current_analysis == True`) | {k['n_kanon']} |
| 1 | + mindestens {MIN_KRIEGSVIDEOS} Kriegsvideos im GESAMTEN Upload-Verlauf | {k['n_stufe1']} |
| 2 | + mindestens {MIN_KLASSIFIZIERTE_VIDEOS} Videos mit gueltiger Populismus-Klassifikation | {k['n_final']} (= finale Whitelist) |

**Stufe 1** zaehlt `topic_vids` aus
`scripts/adhoc/output/topic_vids_per_channel.csv`: Anzahl Videos eines
Kanals, die die Keyword-basierte Themen-Relevanz-Klassifikation
(`step3_war_videos/classify_topic_relevance.py`, Tabelle
`video_topic_relevance`, Topic `russia_ukraine_war`) als (vermutlich)
kriegsbezogen einstuft — ueber ALLE Videos des Kanals seit dem 24.02.2021,
nicht nur die tatsaechlich fuer die LLM-Klassifikation ausgewaehlten. Das
ist ein Relevanzfilter auf Kanalebene: Kanaele, die sich kaum mit dem Krieg
befasst haben, sind fuer einen Vorher/Nachher-Vergleich rund um den
Kriegsbeginn ungeeignet.

{len(k['fehlt_topic'])} Kanaele aus Stufe 0 fehlen in der `topic_vids`-Datei (keine Angabe) und werden konservativ als "nicht ausreichend" behandelt:
{liste(beispiele_fehlt, ['channel_id', 'channel_title'])}
Von den verbleibenden {k['n_kanon'] - len(k['fehlt_topic'])} Kanaelen scheitern {len(k['zu_wenig_kriegsvideos'])} an der {MIN_KRIEGSVIDEOS}er-Schwelle (Top 15 nach `topic_vids`, absteigend):
{liste(beispiele_zu_wenig, ['channel_id', 'channel_title', 'topic_vids'])}
**Stufe 2** entfernt zusaetzlich {len(k['keine_klassifikation'])} Kanaele, die zwar >= {MIN_KRIEGSVIDEOS} Kriegsvideos haben, aber weniger als {MIN_KLASSIFIZIERTE_VIDEOS} Videos mit Populismus-Klassifikation in `channel_video_populism.csv` (Schritt 5, LLM-Klassifikation noch nicht/nicht ausreichend abgeschlossen):
{liste(beispiele_keine_klass, ['channel_id', 'channel_title'])}
Vollstaendige Zeile-fuer-Kanal-Audit-Spur (alle {k['n_kanon']} Kanaele aus
Stufe 0, mit allen Zwischenwerten): `frage1_stichprobe_kanalstatus.csv`.
Nur die finale Whitelist (Stufe 2, {k['n_final']} Kanal-IDs):
`frage1_kanal_whitelist.csv`.

## 2. Zusammensetzung ueber den Kriegsbeginn hinweg

Innerhalb der finalen Whitelist ({k['n_final']} Kanaele) haben:

| Gruppe | Kanaele | Bedeutung |
|---|---|---|
| Vor- UND Nachkriegsbeobachtungen | {len(k['beide'])} | tragen zur Schaetzung des Post-Effekts bei (within-Kanal-Vergleich) |
| NUR Vorkriegsbeobachtungen | {len(k['nur_vorkrieg'])} | Kanal in der Whitelist, aber ohne klassifiziertes Video ab Kriegsbeginn (z.B. Kanal seither inaktiv/nicht klassifiziert) |
| NUR Nachkriegsbeobachtungen | {len(k['nur_nachkrieg'])} | Kanal ohne klassifiziertes Video vor Kriegsbeginn (u.a. "postwar baseline"-Kanaele, siehe unten) |

Kanaele mit nur einer Seite tragen in der Post-Dummy-Regression (Abschnitt 3)
NICHTS zur Schaetzung von `post` bei — ihre Kanal-Fixed-Effect absorbiert
ihren gesamten (konstanten) Mittelwert vollstaendig. Sie bleiben trotzdem
Teil der Whitelist und erscheinen deskriptiv in den Zeitverlaufsplots.

## 2a. Abdeckung der Ideologie-Klassifikation (rein informativ)

Die Ideologie-Einordnung (links/mitte/rechts, `deskriptiv_aggregation.py::lade_ideologie()`)
stammt aus `channel_classification_ideology.csv` und beruht je Kanal auf einer
unterschiedlichen Anzahl klassifizierter Baseline-Videos (`n_videos` dort,
identisch mit den Videos aus der Klassifikations-Baseline, Abschnitt 3a).
Diese Tabelle zeigt, wie viele Whitelist-Kanaele bei einer strengeren
Mindestbesetzung fuer die Ideologie-Klassifikation uebrig blieben — **rein
informativ, filtert die Whitelist selbst NICHT**:

| Mindestanzahl Baseline-Videos (Ideologie) | Kanaele in der Whitelist mit >= dieser Anzahl |
|---|---|
{ideologie_schwellen_zeilen}
## 3. Was genau ist "Baseline" — zwei unterschiedliche Verfahren im Projekt

**(a) Klassifikations-Baseline (Schritt 2, Kanalzuordnung):** bestimmt,
WELCHE Videos ueberhaupt als "Baseline-Video" fuer die LLM-Klassifikation
ausgewaehlt werden (`select_baseline_targets()`,
`step2_baseline_channels/README.md` Abschnitt 1). Fuer Kanaele mit
durchgehender Aktivitaet ueber den Kriegsbeginn hinweg: die letzten 12
Monate VOR dem 24.02.2022. Fuer Kanaele OHNE durchgehende Aktivitaet: ein
individuelles Ersatzfenster von bis zu 12 Monaten ab Beginn ihrer
massgeblichen Aktivitaetsphase — dieses Ersatzfenster KANN NACH dem
24.02.2022 LIEGEN. Das ist der Grund, warum manche Kanaele in Abschnitt 2
"nur Nachkriegsbeobachtungen" haben, obwohl ihre Videos formal als
"Baseline" klassifiziert wurden.

**(b) Vergleichsmessung in `frage1_populismus_bericht.py` (Abschnitt 4):**
verwendet NICHT das individuelle Fenster aus (a), sondern ausschliesslich
die KALENDARISCHE Position eines Videos relativ zum 24.02.2022
(`rel_quartal`/`rel_monat`, `prepare_channel_scores.py::relativ_periode()`):
`post = 1` genau dann, wenn ein Video am/nach dem 24.02.2022 veroeffentlicht
wurde. Bewusste Entscheidung, um den Kriegsbeginn als fuer ALLE Kanaele
GLEICHE, exogene Zeitmarke zu nutzen (siehe COMPLETE_PROCESS.md), statt das
individuell verschobene Klassifikations-Fenster aus (a) zu uebernehmen.

**(c) Baseline-INDEX in `deskriptiv_aggregation.py::berechne_index()`
(nochmal ein drittes, eigenstaendiges Verfahren):** berechnet zusaetzlich zum
Rohwert einen Index auf Basis des Mittelwerts der letzten 1-2 Vorkriegsquartale
(bzw. letzten 6 Vorkriegsmonate) = 100, je Kanal x Dimension. Die
Zeitverlaufsplots (`deskriptiv_plots.py`) zeigen standardmaessig NICHT diesen
Index, sondern die absoluten Rohwerte (`wert_roh`) — die Index-Spalte
(`index_100`) bleibt nur als Zusatzinformation in der `deskriptiv_*.csv`
erhalten. Kanaele ohne besetztes Vorkriegsfenster bekommen `index_100 = NaN`,
tauchen aber mit ihrem Rohwert weiterhin in den Plots auf (anders als vor
dieser Umstellung, als solche Kanaele komplett aus der Aggregation
herausfielen). `deskriptiv_plots.py` erzeugt deshalb je Dimension zwei
Plot-Varianten: **"alle"** (alle Kanaele mit einem Wert in der jeweiligen
Periode, inkl. seit Kriegsbeginn neu dazugekommene) und **"beide_perioden"**
(nur Kanaele mit mindestens einem Vor- UND einem Nachkriegswert — der within-
Kanal-Vergleich, s. Abschnitt 2).

## 4. Veraenderungsmessung (Regressionsmodell)

Eine Beobachtung ist ein **Kanal-Monat** `m` eines Kanals `c` (bzw. ein
Kanal-Quartal bei `GRANULARITAET = "quartal"`) — der Mittelwert ueber alle in
diesem Monat klassifizierten Videos des Kanals
(`frage1_populismus_bericht.py::aggregiere_kanal_periode()`), NICHT ein
einzelnes Video. Das verhindert, dass Kanal-Monate mit ueberdurchschnittlich
vielen klassifizierten Videos die Schaetzung staerker gewichten als
Kanal-Monate mit wenigen:

```
y_cm = alpha_c + beta * post_cm + epsilon_cm
```

- `alpha_c`: Kanal-Fixed-Effect (kontrolliert jedes feste Kanalniveau vollstaendig weg)
- `post_cm`: 1 wenn der Kanal-Monat am/nach 24.02.2022 liegt, sonst 0 (siehe 3b)
- Standardfehler auf Kanalebene geclustert (wiederholte Beobachtungen je Kanal)
- `beta`: durchschnittliche Niveauveraenderung nach Kriegsbeginn GEGENUEBER
  dem EIGENEN Vorkriegsniveau des Kanals — nicht gegenueber einem
  gemeinsamen Referenzwert oder einer Baseline=100-Normierung.

Fuer den Gruppenvergleich (Ideologie/Medientyp) zusaetzlich:

```
y_cm = alpha_c + beta * post_cm + sum_g gamma_g * (post_cm x Gruppe_g) + epsilon_cm
```

mit gemeinsamem F-Test auf alle `gamma_g` (H0: der Post-Effekt ist in allen
Gruppen gleich). Details und Code: `frage1_populismus_bericht.py`.

## 5. Konfiguration dieses Skripts

| Parameter | Wert | Bedeutung |
|---|---|---|
| `ANALYSIS_ID` | `{ANALYSIS_ID}` | kanonische Sample-Definition |
| `MIN_KRIEGSVIDEOS` | {MIN_KRIEGSVIDEOS} | Schwelle in Stufe 1 |
| `TOPIC_VIDS_PATH` | `scripts/adhoc/output/topic_vids_per_channel.csv` | Quelle fuer `topic_vids` |
"""
    PFAD_METHODIK.write_text(md, encoding="utf-8")
    print(f"[Methodik] -> {PFAD_METHODIK}")


# =========================================================
# MAIN
# =========================================================

def main():
    status, kennzahlen = baue_kanalstatus()

    status.to_csv(PFAD_KANALSTATUS, index=False, encoding="utf-8")
    print(f"[Kanalstatus] {len(status)} Zeilen -> {PFAD_KANALSTATUS}")

    whitelist = status.loc[status["in_whitelist"], ["channel_id"]]
    whitelist.to_csv(PFAD_WHITELIST, index=False, encoding="utf-8")
    print(f"[Whitelist] {len(whitelist)} Kanal-IDs -> {PFAD_WHITELIST}")

    schreibe_methodik_markdown(status, kennzahlen)


if __name__ == "__main__":
    main()

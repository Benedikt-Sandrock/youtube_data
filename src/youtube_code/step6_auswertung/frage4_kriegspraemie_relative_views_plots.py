# -*- coding: utf-8 -*-
"""
frage4_kriegspraemie_relative_views_plots.py

Deskriptive Ergaenzung zu TODO 1 aus .claude/Aufgaben.md ("Kriegspraemie": Erzielen Kriegsvideos
fuer bestimmte Medientypen/Ideologien verglichen mit anderen (politischen) Videos ueberdurch-
schnittlich viele Views?) und zu Forschungsfrage 4 (.claude/CLAUDE.md: "Betrifft eine erfolgreicher
werdende Entwicklung nur Kriegsvideos oder auch andere Videos?"). Anders als
frage4_kriegspraemie_medientyp_bericht.py (formale FE-Regression) zeigt dieses Skript die relativen
Views von Kriegsvideos direkt als Zeitreihen-Index: Kriegsvideo-Views (Median bzw. Mittelwert, auf
der VIDEO-Ebene gepoolt, keine Kanal-Zwischenaggregation) geteilt durch die Views derselben Metrik
einer Vergleichsgruppe, je Gruppe5-Kategorie (OERR, Traditionelles Medium, Alternative Medien
links/mitte/rechts, siehe frage2_sensitivitaet_plots.baue_gruppe5_lokal()) und Monat (rel_monat).
Siehe .claude/plans/frage4_kriegspraemie_relative_views.md fuer die vollstaendige Herleitung.

Drei Vergleichsgruppen (die ersten beiden vom Nutzer bestaetigt, siehe Plan-Datei; die dritte seit
2026-09-08 ergaenzt, ebenfalls Nutzervorgabe - siehe .claude/plans/
lies-aufgaben-md-in-claude-compressed-cascade.md), der Kriegsvideo-Zaehler ist fuer ALLE DREI
identisch (Kriegsvideos werden NICHT nach politics_final/topic_categories gefiltert - sie gehen
unabhaengig davon, ob sie je politisch gescreent wurden, vollstaendig ein):
  - "alle_videos": ist_kriegsvideo == 0 (unabhaengig von politics_final/topic_categories).
  - "andere_politische_videos": ist_kriegsvideo == 0 UND politics_final == 1 (Klassifikation aus
    data/store/screening_state.sqlite, siehe screening_state_store.get_state()).
  - "andere_politische_videos_topic": ist_kriegsvideo == 0 UND topic_categories enthaelt
    "Politics" (YouTube-eigene automatische Themenkategorisierung aus
    data/store/video_registry.sqlite::video_details, siehe video_registry.is_politics_topic()/
    politics_topic_lookup()) - deutlich hoehere Abdeckung als politics_final (siehe unten), aber
    eine INHALTLICH ANDERE, breiter gefasste Definition von "politisch" (auch allgemeine
    Gesellschafts-/Nachrichteninhalte ohne engeren parteipolitischen Bezug) - als eigenstaendige,
    ergaenzende Vergleichsgruppe zu behandeln, NICHT als Ersatz fuer andere_politische_videos.

WICHTIGE LIMITATION zu "andere_politische_videos" (siehe Methodik-Datei fuer die vollstaendigen
Diagnosezahlen aus dem Chatverlauf): screening_state.sqlite enthaelt NUR eine per stable_random_key
GEZOGENE Zufallsstichprobe von Kandidaten je Kanal x 3-Monats-Intervall aus dem longitudinalen
Politik-Screening (step2_baseline_channels/) - keine erschoepfende Klassifikation aller Videos.
Insgesamt haben nur ~12% der Videos in channel_video_erfolg.csv ueberhaupt einen
screening_state-Eintrag. Da die Auswahl nachweislich zufaellig (NICHT nach Views sortiert) erfolgt,
ist keine systematische View-Verzerrung durch die Stichprobenziehung selbst zu erwarten - die
Limitation betrifft ausschliesslich die (reduzierte) Zellbesetzung/statistische Power des
Vergleichs "andere_politische_videos", nicht dessen Repraesentativitaet. "andere_politische_videos_
topic" hat dieses Abdeckungsproblem NICHT (~99% der Whitelist-Videos haben einen
topic_categories-Eintrag, Stand 2026-09-08-Diagnose), dafuer die oben beschriebene inhaltliche
Einschraenkung (breiter gefasste, automatische statt manuelle/LLM-Klassifikation).

Index-Formel je Zelle (Gruppe5 x rel_monat) und Vergleich:

    index = metrik(view_count | Kriegsvideos in Zelle) / metrik(view_count | Vergleichsgruppe in Zelle) * 100

mit metrik in {median, mean}. index == 100 bedeutet "Kriegsvideos performen genauso gut wie die
Vergleichsgruppe" (gestrichelte Referenzlinie in jeder Grafik, zusaetzlich zur bestehenden
Kriegsbeginn-Vertikale bei rel_monat = -0.5). index > 100 = Kriegspraemie, < 100 = Kriegsabschlag.

Mindestbesetzung je Zellseite (Zaehler UND Nenner muessen die jeweilige Schwelle separat erreichen,
sonst wird der Punkt uebersprungen - wie MIN_VIDEOS_PRO_ZELLE_VIDEOEBENE in
frage2_sensitivitaet_plots.py): MIN_VIDEOS_KRIEGSVIDEOS (Zaehler, fuer beide Vergleiche identisch),
MIN_VIDEOS_VERGLEICH_ALLE bzw. MIN_VIDEOS_VERGLEICH_POLITICS_FINAL (Nenner, je Vergleich).

Kein Kanalfilter "beide_perioden" (anders als frage2_sensitivitaet_plots.py): die Zellen werden
direkt aus gepoolten Videos gebildet (Nutzervorgabe: "auf der Video-Ebene"), nicht aus
Kanal-Zeitreihen - ein Kanalfilter auf gemeinsame Vor-/Nachkriegsaktivitaet ist dafuer nicht noetig
und wuerde die ohnehin knappe Kriegsvideo-Stichprobe weiter verkleinern.

Datenquelle: outputs/segment_analysis/channel_video_erfolg.csv (Video-Ebene, bereits Whitelist-
gefiltert, aus prepare_success_metrics.py) + screening_state_store.get_state() (politics_final),
gemerged ueber video_id. lade_basisdaten(kanalquelle="kanon") liefert dieselbe Struktur fuer das
volle kanonische Sample (russia_longitudinal_v1) direkt aus der video_registry - von diesem
Skript selbst nicht genutzt, sondern von scripts/masterarbeit/ap2_marktanteil_stichprobenbias.py
und scripts/adhoc/marktanteil_vergleich_279_vs_427.py (siehe _lade_basisdaten_kanon()).

Wiederverwendete Bausteine (Reuse-Prinzip aus CLAUDE.md): baue_gruppe5_lokal() und glaette() werden
als echter Import aus frage2_sensitivitaet_plots uebernommen (kein Duplikat) - analog zu
frage4_kriegspraemie_medientyp_bericht.py, das von dort bereits winsorisiere() importiert.
GRUPPE5_REIHENFOLGE kommt wie dort direkt aus deskriptiv_plots.py.

Laeuft direkt als Skript (sibling-Importe wie die anderen step6_auswertung-Dateien, kein -m):

    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe frage4_kriegspraemie_relative_views_plots.py

(im Ordner src/youtube_code/step6_auswertung/ ausgefuehrt).
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from youtube_code.config import OUTPUTS, SAMPLES
from youtube_code.store.screening_state_store import get_state
from youtube_code.store.video_registry import politics_topic_lookup
from deskriptiv_aggregation import lade_medientyp, lade_ideologie
from deskriptiv_plots import GRUPPE5_REIHENFOLGE
from frage2_sensitivitaet_plots import baue_gruppe5_lokal, glaette

# =========================================================
# CONFIG
# =========================================================

SPALTE_PERIODE = "rel_monat"
PERIODE_MIN = -12
PERIODE_MAX = 48
ACHSENLABEL = "Monat relativ zum Kriegsbeginn"

# Mindestbesetzung je Zellseite (Anzahl Videos), siehe Moduldocstring.
MIN_VIDEOS_KRIEGSVIDEOS = 10
MIN_VIDEOS_VERGLEICH_ALLE = 10
MIN_VIDEOS_VERGLEICH_POLITICS_FINAL = 10
MIN_VIDEOS_VERGLEICH_TOPIC = 10

# Vergleich -> (Anzeigename, zusaetzlicher Filter auf die Vergleichsgruppe (ist_kriegsvideo == 0
# ist bereits Teil der Basisfilterung, siehe baue_vergleichsgruppen()), Mindestbesetzung Nenner).
# "politics_final_filter" und "topic_politics_filter" schliessen sich gegenseitig nicht aus
# (beide default False), werden hier aber nie gleichzeitig True gesetzt - siehe Moduldocstring
# fuer die Abgrenzung der beiden Klassifikationen.
VERGLEICHE = {
    "alle_videos": {
        "titel": "alle anderen Videos",
        "politics_final_filter": False,
        "topic_politics_filter": False,
        "min_videos_vergleich": MIN_VIDEOS_VERGLEICH_ALLE,
    },
    "andere_politische_videos": {
        "titel": "andere politische Videos (politics_final == 1)",
        "politics_final_filter": True,
        "topic_politics_filter": False,
        "min_videos_vergleich": MIN_VIDEOS_VERGLEICH_POLITICS_FINAL,
    },
    "andere_politische_videos_topic": {
        "titel": "andere politische Videos (topic_categories='Politics')",
        "politics_final_filter": False,
        "topic_politics_filter": True,
        "min_videos_vergleich": MIN_VIDEOS_VERGLEICH_TOPIC,
    },
}

METRIKEN = {
    "median": np.median,
    "mean": np.mean,
}

PFAD_VIDEO_EBENE = OUTPUTS / "segment_analysis" / "channel_video_erfolg.csv"

# Nur fuer lade_basisdaten(kanalquelle="kanon"): volles kanonisches Sample statt Whitelist.
KANON_ANALYSIS_ID = "russia_longitudinal_v1"
KANON_SAMPLE_PFAD = SAMPLES / KANON_ANALYSIS_ID / "channel_sample_provenance.csv"
KANON_TOPIC = "russia_ukraine_war"
PFAD_PLOTS = OUTPUTS / "segment_analysis" / "plots_frage4_kriegspraemie_relative_views"
PFAD_METHODIK = PFAD_PLOTS / "kriegspraemie_relative_views_methodik.md"

ABBILDUNG_GROESSE = (9, 5)
DPI = 150

# LOWESS-Glaettung (dieselbe Methode/Funktion glaette() wie in frage2_sensitivitaet_plots.py und
# deskriptiv_plots.py) - reine Darstellungshilfe gegen das Monat-zu-Monat-Zickzack bei den 5
# ueberlagerten Gruppe5-Linien. 0/None = keine Glaettung (rohe Linie mit Punktmarkern).
GLAETTUNG_LOWESS_FRAC = 0.1


# =========================================================
# SCHRITT 1: Basisdaten
# =========================================================

def lade_kanon_kanalliste():
    """channel_id's mit eligible_current_analysis == True aus der kanonischen Sample-Definition
    (KANON_SAMPLE_PFAD, dieselbe Quelle/Bedingung wie frage1_stichprobe.py Stufe 0, aber OHNE
    die Stufen 1/2 des Frage-1-Funnels - genau das ist der Unterschied zur Whitelist)."""
    sample = pd.read_csv(KANON_SAMPLE_PFAD)
    sample["channel_id"] = sample["channel_id"].astype(str)
    kanon = sample[sample["eligible_current_analysis"] == True][["channel_id"]].drop_duplicates()
    return kanon["channel_id"].tolist()


def _lade_basisdaten_kanon():
    """Baut dieselbe Video-Ebene-Struktur wie die Whitelist-Variante von lade_basisdaten(), aber
    fuer das volle kanonische Sample (KANON_ANALYSIS_ID, 427 Kanaele, davon 367 mit gueltigem
    gruppe5) direkt aus der video_registry statt aus channel_video_erfolg.csv:
    video_registry.get_video_stats() + get_topic_relevance() fuer ist_kriegsvideo +
    screening_state_store.get_state() fuer politics_final + politics_topic_lookup() fuer
    ist_politics_topic + prepare_channel_scores.ergaenze_periodenspalten() fuer rel_monat/
    rel_quartal. Videos ohne published_at oder view_count werden verworfen (Konsolenhinweis).

    Uebernommen aus scripts/adhoc/marktanteil_vergleich_279_vs_427.py (2026-09-28, AP 2 der
    Masterarbeit-Strategie), damit AP 2 und das Adhoc-Skript denselben Lader nutzen.

    Anders als die Whitelist-Variante dedupliziert diese Variante lade_medientyp()/
    lade_ideologie() defensiv auf channel_id: channel_classification_ideology.csv enthaelt fuer
    3 channel_id's Duplikatzeilen, ein ungeschuetzter Merge wuerde jede Videozeile dieser Kanaele
    verdoppeln. Der zentrale Fix in deskriptiv_aggregation.lade_ideologie() steht noch aus
    (offener Punkt fuer AP 9) - die Whitelist-Variante bleibt bis dahin bewusst unveraendert,
    damit bereits berichtete Zahlen reproduzierbar bleiben."""
    from youtube_code.store import video_registry
    from deskriptiv_plots import baue_gruppe5
    from prepare_channel_scores import ergaenze_periodenspalten

    channel_ids = lade_kanon_kanalliste()
    print(f"[Kanon-Sample] {len(channel_ids)} Kanaele (eligible_current_analysis==True).")

    stats = video_registry.get_video_stats(channel_ids=channel_ids)
    stats["channel_id"] = stats["channel_id"].astype(str)
    stats["video_id"] = stats["video_id"].astype(str)
    stats["published_at"] = pd.to_datetime(
        stats["published_at"], errors="coerce", utc=True
    ).dt.tz_localize(None)

    ohne_datum = stats["published_at"].isna()
    if ohne_datum.any():
        print(f"[Video-Stats] {int(ohne_datum.sum())} von {len(stats)} Videos ohne "
              f"published_at -> verworfen.")
        stats = stats[~ohne_datum]

    ohne_views = stats["view_count"].isna()
    if ohne_views.any():
        print(f"[Video-Stats] {int(ohne_views.sum())} von {len(stats)} Videos ohne "
              f"view_count -> verworfen.")
        stats = stats[~ohne_views]

    med = lade_medientyp().drop_duplicates(subset="channel_id", keep="first")
    ideo = lade_ideologie().drop_duplicates(subset="channel_id", keep="first")
    med["channel_id"] = med["channel_id"].astype(str)
    ideo["channel_id"] = ideo["channel_id"].astype(str)

    df = stats.merge(med, on="channel_id", how="left").merge(ideo, on="channel_id", how="left")
    df = baue_gruppe5(df)
    print(f"[Gruppe5] {df['channel_id'].nunique()} von {len(channel_ids)} Kanon-Kanaelen mit "
          f"gueltigem gruppe5.")

    relevanz = video_registry.get_topic_relevance(topic=KANON_TOPIC,
                                                  video_ids=df["video_id"].tolist())
    relevante_ids = set(relevanz.loc[relevanz["is_relevant"] == 1, "video_id"])
    df["ist_kriegsvideo"] = df["video_id"].isin(relevante_ids).astype(int)

    df = ergaenze_periodenspalten(df)

    state = get_state()[["video_id", "politics_final"]]
    state["video_id"] = state["video_id"].astype(str)
    df = df.merge(state, on="video_id", how="left")

    topic_map = politics_topic_lookup(df["video_id"].tolist())
    df["ist_politics_topic"] = df["video_id"].map(topic_map)

    df = df[(df[SPALTE_PERIODE] >= PERIODE_MIN) & (df[SPALTE_PERIODE] <= PERIODE_MAX)]
    print(f"[Basisdaten Kanon] {len(df)} Videos, {df['channel_id'].nunique()} Kanaele im Fenster "
          f"{SPALTE_PERIODE} in [{PERIODE_MIN}, {PERIODE_MAX}].")
    return df


def lade_basisdaten(kanalquelle="whitelist"):
    """Video-Ebene-Basisdaten fuer die Marktanteils-/Kriegspraemien-Skripte.

    kanalquelle="whitelist" (Default, alle bestehenden Aufrufe): liest channel_video_erfolg.csv
    (Video-Ebene, 279er-Frage-1-Whitelist), ergaenzt medientyp/ideologie_gruppe/gruppe5
    (dieselben Bausteine wie frage2_sensitivitaet_plots.py) sowie politics_final aus
    screening_state_store.get_state() (Merge ueber video_id, Left-Join - Videos ohne
    screening_state-Eintrag bekommen politics_final = NaN) UND ist_politics_topic aus
    video_registry.politics_topic_lookup() (seit 2026-09-08, deutlich hoehere Abdeckung - siehe
    Moduldocstring), filtert auf PERIODE_MIN/PERIODE_MAX.

    kanalquelle="kanon": volles kanonisches Sample direkt aus der video_registry, siehe
    _lade_basisdaten_kanon()."""
    if kanalquelle == "kanon":
        return _lade_basisdaten_kanon()
    if kanalquelle != "whitelist":
        raise ValueError(f"Unbekannte kanalquelle {kanalquelle!r} (erlaubt: 'whitelist', 'kanon').")

    df = pd.read_csv(PFAD_VIDEO_EBENE)
    df["channel_id"] = df["channel_id"].astype(str)
    df["video_id"] = df["video_id"].astype(str)

    med = lade_medientyp()
    ideo = lade_ideologie()
    df = df.merge(med, on="channel_id", how="left").merge(ideo, on="channel_id", how="left")
    df = baue_gruppe5_lokal(df)

    state = get_state()[["video_id", "politics_final"]]
    state["video_id"] = state["video_id"].astype(str)
    n_vor_merge = len(df)
    df = df.merge(state, on="video_id", how="left")
    n_mit_state = df["politics_final"].notna().sum()
    print(f"[politics_final] {n_mit_state} von {n_vor_merge} Videos ({n_mit_state / n_vor_merge:.1%}) "
          f"haben einen screening_state-Eintrag (siehe Abdeckungs-Limitation im Moduldocstring).")

    topic_map = politics_topic_lookup(df["video_id"].tolist())
    df["ist_politics_topic"] = df["video_id"].map(topic_map)
    n_mit_topic = df["ist_politics_topic"].notna().sum()
    n_politics_topic = (df["ist_politics_topic"] == True).sum()
    print(f"[topic_categories] {n_mit_topic} von {n_vor_merge} Videos ({n_mit_topic / n_vor_merge:.1%}) "
          f"haben einen video_details-Eintrag, davon {n_politics_topic} "
          f"({n_politics_topic / n_vor_merge:.1%} aller Videos) mit Kategorie 'Politics'.")

    df = df[(df[SPALTE_PERIODE] >= PERIODE_MIN) & (df[SPALTE_PERIODE] <= PERIODE_MAX)]
    print(f"[Basisdaten] {len(df)} Videos, {df['channel_id'].nunique()} Kanaele mit gueltiger "
          f"gruppe5-Zuordnung im Fenster {SPALTE_PERIODE} in [{PERIODE_MIN}, {PERIODE_MAX}].")
    return df


def baue_vergleichsgruppen(df, vergleich_key):
    """Liefert (kriegsvideos, vergleichsgruppe): kriegsvideos ist fuer ALLE Vergleiche identisch
    (ist_kriegsvideo == 1, KEIN politics_final-/topic_categories-Filter, siehe Moduldocstring),
    vergleichsgruppe ist ist_kriegsvideo == 0, je nach VERGLEICHE[vergleich_key] zusaetzlich auf
    politics_final == 1 ('politics_final_filter') oder ist_politics_topic == True
    ('topic_politics_filter') eingeschraenkt (Videos ohne video_details-Eintrag haben
    ist_politics_topic = NaN, `== True` schliesst diese korrekt aus, nicht faelschlich ein)."""
    cfg = VERGLEICHE[vergleich_key]
    kriegsvideos = df[df["ist_kriegsvideo"] == 1]
    vergleich = df[df["ist_kriegsvideo"] == 0]
    if cfg["politics_final_filter"]:
        vergleich = vergleich[vergleich["politics_final"] == 1]
    if cfg["topic_politics_filter"]:
        vergleich = vergleich[vergleich["ist_politics_topic"] == True]
    return kriegsvideos, vergleich


# =========================================================
# SCHRITT 2: Index berechnen
# =========================================================

def berechne_index(kriegsvideos, vergleich, metrik_name, min_videos_vergleich):
    """Gruppiert beide Seiten nach (rel_monat, gruppe5), wendet METRIKEN[metrik_name] auf
    view_count an und bildet je Zelle index = kriegsvideo_wert / vergleich_wert * 100. Zellen, die
    die jeweilige Mindestbesetzung (MIN_VIDEOS_KRIEGSVIDEOS bzw. min_videos_vergleich) nicht
    erreichen, fehlen im Ergebnis (Inner-Join ueber die bereits gefilterten Zellen)."""
    metrik_funktion = METRIKEN[metrik_name]
    schluessel = [SPALTE_PERIODE, "gruppe5"]

    kv_zellen = kriegsvideos.groupby(schluessel, as_index=False).agg(
        wert_krieg=("view_count", metrik_funktion), n_krieg=("view_count", "size"))
    kv_zellen = kv_zellen[kv_zellen["n_krieg"] >= MIN_VIDEOS_KRIEGSVIDEOS]

    vg_zellen = vergleich.groupby(schluessel, as_index=False).agg(
        wert_vergleich=("view_count", metrik_funktion), n_vergleich=("view_count", "size"))
    vg_zellen = vg_zellen[vg_zellen["n_vergleich"] >= min_videos_vergleich]

    zusammen = kv_zellen.merge(vg_zellen, on=schluessel, how="inner")
    zusammen["wert"] = zusammen["wert_krieg"] / zusammen["wert_vergleich"] * 100
    return zusammen


# =========================================================
# SCHRITT 3: Plotten
# =========================================================

def plotte_index(werte_df, dateiname, titel, y_label):
    """Eine Grafik, 5 Linien (GRUPPE5_REIHENFOLGE), Kriegsbeginn-Referenzlinie bei rel_monat = -0.5
    (wie deskriptiv_plots.py) UND eine gestrichelte Referenzlinie bei index = 100 ("Kriegsvideos
    performen genauso gut wie die Vergleichsgruppe"). Jede Linie wird ueber glaette() (importiert
    aus frage2_sensitivitaet_plots) LOWESS-geglaettet."""
    if werte_df.empty:
        print(f"[Skip] {dateiname}: keine Zelle erreicht die Mindestbesetzung.")
        return False

    fig, ax = plt.subplots(figsize=ABBILDUNG_GROESSE)
    gezeichnet = False
    for g in GRUPPE5_REIHENFOLGE:
        reihe = werte_df[werte_df["gruppe5"] == g].sort_values(SPALTE_PERIODE)
        if reihe.empty:
            continue
        x = reihe[SPALTE_PERIODE].to_numpy(dtype=float)
        y = reihe["wert"].to_numpy(dtype=float)
        y_glatt = glaette(x, y) if GLAETTUNG_LOWESS_FRAC else y

        if GLAETTUNG_LOWESS_FRAC:
            ax.plot(x, y_glatt, linewidth=2.2, label=g)
        else:
            ax.plot(x, y_glatt, marker="o", markersize=3, linewidth=1.8, label=g)
        gezeichnet = True

    if not gezeichnet:
        print(f"[Skip] {dateiname}: keine Gruppe5-Kategorie mit Daten.")
        plt.close(fig)
        return False

    ax.axhline(100, color="grey", linestyle=":", linewidth=1.2, zorder=1)
    ax.text(ax.get_xlim()[0], 100, " Index=100 (= Vergleichsgruppe)", va="bottom", fontsize=7,
            color="grey")
    ax.axvline(-0.5, color="black", linestyle="--", linewidth=1)
    ax.text(-0.45, ax.get_ylim()[1], " Kriegsbeginn", va="top", fontsize=8)
    ax.set_xlabel(ACHSENLABEL)
    ax.set_ylabel(y_label)
    ax.set_title(titel)
    ax.legend(fontsize=7)
    fig.tight_layout()

    PFAD_PLOTS.mkdir(parents=True, exist_ok=True)
    pfad = PFAD_PLOTS / dateiname
    fig.savefig(pfad, dpi=DPI)
    plt.close(fig)
    print(f"[Plot] {pfad}")
    return True


# =========================================================
# SCHRITT 4: Methodik-Uebersichtsdatei
# =========================================================

def schreibe_methodik(erzeugte_dateien, n_gesamt, n_mit_state, n_mit_topic, n_politics_topic):
    """Schreibt kriegspraemie_relative_views_methodik.md - Pflichtdokumentation fuer Vergleichs-
    analysen (siehe document-comparative-analysis-methodology). Enthaelt die Index-Formel, die
    Mindestbesetzung sowie die vollstaendige politics_final-/topic_categories-Abdeckungs-
    Limitation."""
    zeilen = [
        "# Methodik: Relative Views von Kriegsvideos (Kriegspraemie, Forschungsfrage 4 / TODO 1)",
        "",
        "Diese Datei dokumentiert `frage4_kriegspraemie_relative_views_plots.py` - siehe "
        "`.claude/plans/frage4_kriegspraemie_relative_views.md` fuer die vollstaendige Herleitung "
        "und den Modul-Docstring des Skripts fuer die genaue Implementierung.",
        "",
        "## Index-Formel",
        "",
        "Je Zelle (Gruppe5-Kategorie x `rel_monat`), gepoolt auf Video-Ebene (keine "
        "Kanal-Zwischenaggregation):",
        "",
        "```",
        "index = metrik(view_count | Kriegsvideos) / metrik(view_count | Vergleichsgruppe) * 100",
        "```",
        "",
        "mit `metrik` in {Median, Mittelwert}. `index == 100` bedeutet \"Kriegsvideos performen "
        "genauso gut wie die Vergleichsgruppe\" (gestrichelte Referenzlinie in jeder Grafik). "
        "`index > 100` = Kriegspraemie, `< 100` = Kriegsabschlag.",
        "",
        "## Vergleichsgruppen",
        "",
        "Der Kriegsvideo-Zaehler (`ist_kriegsvideo == 1`) ist fuer ALLE DREI Vergleiche identisch - "
        "Kriegsvideos werden NICHT nach `politics_final`/`topic_categories` gefiltert, sie gehen "
        "unabhaengig davon, ob sie je politisch gescreent/kategorisiert wurden, vollstaendig ein "
        "(Nutzervorgabe).",
        "",
        "- **alle_videos**: `ist_kriegsvideo == 0` (unabhaengig von `politics_final`/"
        "`topic_categories`).",
        "- **andere_politische_videos**: `ist_kriegsvideo == 0 UND politics_final == 1` "
        "(manuelle/LLM-Klassifikation aus `data/store/screening_state.sqlite`).",
        "- **andere_politische_videos_topic** (seit 2026-09-08): `ist_kriegsvideo == 0 UND "
        "topic_categories enthaelt \"Politics\"` (YouTube-eigene automatische "
        "Themenkategorisierung aus `data/store/video_registry.sqlite::video_details`, siehe "
        "`video_registry.is_politics_topic()`/`politics_topic_lookup()`) - deutlich hoehere "
        "Abdeckung, aber inhaltlich eine ANDERE, breiter gefasste Definition von \"politisch\" "
        "(siehe unten) - eigenstaendige, ergaenzende Vergleichsgruppe, kein Ersatz fuer "
        "`andere_politische_videos`.",
        "",
        "## Mindestbesetzung",
        "",
        f"Zaehler- und Nennerseite muessen JEWEILS separat die Schwelle erreichen, sonst wird die "
        f"Zelle uebersprungen (fehlender Punkt in der Linie): "
        f"`MIN_VIDEOS_KRIEGSVIDEOS={MIN_VIDEOS_KRIEGSVIDEOS}` (Zaehler, alle drei Vergleiche), "
        f"`MIN_VIDEOS_VERGLEICH_ALLE={MIN_VIDEOS_VERGLEICH_ALLE}` (Nenner bei alle_videos), "
        f"`MIN_VIDEOS_VERGLEICH_POLITICS_FINAL={MIN_VIDEOS_VERGLEICH_POLITICS_FINAL}` (Nenner bei "
        "andere_politische_videos), "
        f"`MIN_VIDEOS_VERGLEICH_TOPIC={MIN_VIDEOS_VERGLEICH_TOPIC}` (Nenner bei "
        "andere_politische_videos_topic).",
        "",
        "## Limitation: Abdeckung von `politics_final` vs. `topic_categories`",
        "",
        "`screening_state.sqlite` enthaelt NUR eine per `stable_random_key` GEZOGENE "
        "Zufallsstichprobe von Kandidaten je Kanal x 3-Monats-Intervall aus dem longitudinalen "
        "Politik-Screening (`step2_baseline_channels/`) - keine erschoepfende Klassifikation aller "
        "Videos. Da die Auswahl nachweislich zufaellig (NICHT nach Views sortiert) erfolgt, ist "
        "KEINE systematische View-Verzerrung durch die Stichprobenziehung selbst zu erwarten - die "
        "Limitation betrifft ausschliesslich die (reduzierte) Zellbesetzung/statistische Power des "
        "Vergleichs `andere_politische_videos`, nicht dessen Repraesentativitaet.",
        "",
        f"Bei diesem Lauf hatten {n_mit_state} von {n_gesamt} Videos "
        f"({n_mit_state / n_gesamt:.1%}) im gefilterten Fenster ueberhaupt einen "
        "`screening_state`-Eintrag (Diagnosewerte aus dem Chatverlauf zum Gesamtdatensatz: "
        "~12% insgesamt, ~11% bei Kriegsvideos, ~12% bei Nicht-Kriegsvideos - fuer Kriegsvideos "
        "ohne Belang, da sie ungefiltert eingehen, siehe oben).",
        "",
        "`topic_categories` (`andere_politische_videos_topic`) ist YouTube's eigene automatische "
        "Themenkategorisierung, praktisch fuer alle Videos verfuegbar - deckt dafuer aber auch "
        "allgemeine Gesellschafts-/Nachrichteninhalte ohne engeren parteipolitischen Bezug ab und "
        "ist damit eine breiter gefasste, GROBERE Definition von \"politisch\" als die manuelle/"
        "LLM-Klassifikation `politics_final`. Kein Zufallsstichproben-Problem, aber eine andere "
        "inhaltliche Abgrenzung - beide Vergleiche ergaenzen sich, ersetzen sich nicht.",
        "",
        f"Bei diesem Lauf hatten {n_mit_topic} von {n_gesamt} Videos "
        f"({n_mit_topic / n_gesamt:.1%}) im gefilterten Fenster einen `video_details`-Eintrag, "
        f"davon {n_politics_topic} ({n_politics_topic / n_gesamt:.1%} aller Videos im Fenster) mit "
        "Kategorie \"Politics\".",
        "",
        "## Fenster und Darstellung",
        "",
        f"- `{SPALTE_PERIODE}` in [{PERIODE_MIN}, {PERIODE_MAX}] (wie "
        "`frage2_sensitivitaet_plots.py`).",
        "- Kein Kanalfilter \"beide_perioden\": die Zellen werden direkt aus gepoolten Videos "
        "gebildet, nicht aus Kanal-Zeitreihen.",
        f"- LOWESS-Glaettung `GLAETTUNG_LOWESS_FRAC={GLAETTUNG_LOWESS_FRAC}` je Gruppe5-Linie "
        "(dieselbe Methode wie `frage2_sensitivitaet_plots.py`/`deskriptiv_plots.py`), reine "
        "Darstellungshilfe.",
        "",
        f"## Erzeugte Grafiken bei diesem Lauf: {len(erzeugte_dateien)}",
        "",
    ]
    for d in erzeugte_dateien:
        zeilen.append(f"- `{d}`")

    PFAD_PLOTS.mkdir(parents=True, exist_ok=True)
    with open(PFAD_METHODIK, "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen) + "\n")
    print(f"[Methodik] {PFAD_METHODIK}")


# =========================================================
# MAIN
# =========================================================

def main():
    basisdaten = lade_basisdaten()
    n_gesamt = len(basisdaten)
    n_mit_state = int(basisdaten["politics_final"].notna().sum())
    n_mit_topic = int(basisdaten["ist_politics_topic"].notna().sum())
    n_politics_topic = int((basisdaten["ist_politics_topic"] == True).sum())

    erzeugte_dateien = []
    for vergleich_key, cfg in VERGLEICHE.items():
        kriegsvideos, vergleichsgruppe = baue_vergleichsgruppen(basisdaten, vergleich_key)
        print(f"[Vergleich={vergleich_key}] {len(kriegsvideos)} Kriegsvideos vs. "
              f"{len(vergleichsgruppe)} Videos in der Vergleichsgruppe ({cfg['titel']}).")

        for metrik_name in METRIKEN:
            werte_df = berechne_index(kriegsvideos, vergleichsgruppe, metrik_name,
                                       cfg["min_videos_vergleich"])
            dateiname = f"kriegspraemie_relative_views_{vergleich_key}_{metrik_name}_monat.png"
            titel = (f"Relative Views (Index): Kriegsvideos vs. {cfg['titel']}\n"
                     f"Metrik={metrik_name}, Video-Ebene, {SPALTE_PERIODE}")
            y_label = f"Index ({cfg['titel']} = 100)"
            if plotte_index(werte_df, dateiname, titel, y_label):
                erzeugte_dateien.append(dateiname)

    n_moeglich = len(VERGLEICHE) * len(METRIKEN)
    print(f"\n[Fertig] {len(erzeugte_dateien)} von {n_moeglich} moeglichen Grafiken erzeugt "
          f"-> {PFAD_PLOTS}")
    schreibe_methodik(erzeugte_dateien, n_gesamt, n_mit_state, n_mit_topic, n_politics_topic)


if __name__ == "__main__":
    main()

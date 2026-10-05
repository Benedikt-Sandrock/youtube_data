# -*- coding: utf-8 -*-
"""
schockfenster_bericht.py

Antwort auf TODO 3 aus .claude/Aufgaben.md ("Schockfenster" - kurze
Zeitraeume vor und nach wichtigen Ereignissen wie Kriegsbeginn oder der
US-Wahl 2024, Untersuchung ob bestimmte Kanalgruppen einen Reichweiten-
Sprung erlebt haben, mit Fokus auf Heterogenitaet nach Ideologie/Medientyp).
Siehe .claude/plans/schockfenster_bericht.md fuer die vollstaendige
Herleitung und moegliche Ausbauschritte (Marktanteil-Verschiebung, Plots -
bewusst NICHT Teil dieses ersten Wurfs).

Anders als alle bisherigen Vorher/Nachher-Berichte in diesem Ordner (groebste
Aufloesung: rel_monat/rel_quartal, EIN festes Referenzdatum = Kriegsbeginn)
arbeitet dieses Skript auf einer TAGESGENAUEN Periodenspalte (tage_relativ =
published_at - Ereignisdatum, je Schock neu berechnet) und iteriert
automatisch ueber ein Kreuzprodukt aus mehreren Ereignissen, mehreren
Fensterbreiten (als eingebaute Sensitivitaetspruefung) und mehreren
Heterogenitaetsdimensionen - leicht anpassbar per Konfigurationsblock
unten, ohne den restlichen Code anfassen zu muessen.

METRIKEN sind nicht nur Erfolgsmetriken (view_count/log_views): seit
2026-09-10 (Nutzervorgabe, Anschlussfrage an den Bucha-Schock) werden auch
position_russland/position_westpolitik (Haltung gegenueber Russland bzw.
westlicher Ukraine-Politik, Prompt POSITION_V1) aus channel_video_position.csv
in lade_basisdaten() an die Video-Ebene gemerged und laufen als ganz normale
METRIKEN-Eintraege durch dieselbe post_dummy_test()/interaktions_test()-
Maschinerie wie die Erfolgsmetriken - KEINE Sonderbehandlung im Code noetig,
weil beide Testfunktionen NaN-Zeilen in der jeweiligen y-Spalte ohnehin per
dropna() ausschliessen. WICHTIG: Das reduziert die effektive Stichprobe fuer
diese beiden Metriken auf die LLM-klassifizierte Teilmenge (channel_video_
position.csv deckt ~29.600 von den insgesamt weit mehr Videos der breiteren
Schockfenster-Kanalpopulation ab, siehe Moduldocstring "Kanalpopulation"
unten) - bei den ohnehin schon knapp besetzten engen Tage-Fenstern (7/14
Tage) ist die Power fuer position_russland/position_westpolitik deshalb
nochmal deutlich niedriger als fuer view_count/log_views auf derselben
Fensterbreite.

Kanalpopulation bewusst BREITER als die Frage-1-Whitelist: alle Kanaele mit
Medientyp-Klassifikation (lade_medientyp()), nicht nur die Kanaele mit >=5
klassifizierten Baseline-Videos - eine reine Reichweiten-Analyse braucht keinen
Populismus-Score, und bei engen Tage-Fenstern ist die Power ohnehin knapp
(viele Kanaele haben keine Videos in Vor- UND Nachfenster). baue_gruppe5()
filtert die Population zusaetzlich auf vollstaendig klassifizierte Kanaele
(OERR/Traditionell/Alternative Medien MIT Ideologie-Einordnung, kein
Politiker/Partei) - dieselbe gefilterte Population gilt dann auch fuer die
Dimensionen "medientyp"/"ideologie_gruppe" (siehe HETEROGENITAETS_
DIMENSIONEN unten: "medientyp" enthaelt deshalb bewusst kein "Politiker/
Partei" mehr). Fuer die Metriken position_russland/position_westpolitik wird
diese breite Population NICHT zusaetzlich eingeschraenkt - sie schrumpft
implizit ueber die dropna() in post_dummy_test()/interaktions_test() auf die
Videos, die channel_video_position.csv abdeckt (siehe METRIKEN-Hinweis oben).

Zwei Beobachtungsebenen laufen je Kombination als GETRENNTE
Robustheits-Durchlaeufe (Projekt-Konvention, siehe berechne_upload_dichte()
vs. berechne_upload_dichte_periode() in bericht_utils.py - zwei Varianten
nie gemeinsam im selben Modell, sondern als getrennte vollstaendige
Laeufe):
  - Video-Ebene: jede Zeile = 1 Video, periode = tage_relativ (kontinuierlich
    in Tagen). Mehr Beobachtungen/Power, aber Kanaele mit vielen Videos
    dominieren staerker.
  - Kanal x Fensterseite aggregiert: fenster_bucket = -1 (vor) / +1 (nach) -
    der Ereignistag selbst (tage_relativ == 0) zaehlt zu "nach". Aggregation
    ueber die bereits vorhandene prepare_success_metrics.py::
    aggregiere_kanal_periode_erfolg() (keine neue Aggregationsfunktion
    noetig), Kanalmerkmale (gruppe5/medientyp/ideologie_gruppe) werden danach
    erneut auf channel_id gemerged (gehen bei der Aggregation verloren, sind
    aber kanalkonstant).

bericht_utils.post_dummy_test()/interaktions_test() werden UNVERAENDERT
importiert - beide funktionieren bereits mit jeder beliebigen numerischen
Periodenspalte (der interne Test ist schlicht "periode >= 0"), nicht nur mit
rel_monat/rel_quartal. Keine neue Regressionslogik in diesem Skript. Beide
Funktionen geben bereits None zurueck und loggen "zu wenig Variation", wenn
ein Fenster zu duenn besetzt ist - main() sammelt nur die nicht-None
Ergebnisse ein.

Als Paket-Modul ausfuehren (braucht sowohl youtube_code.store.video_registry
als auch mehrere Sibling-Module als echte Paketimporte, siehe README):

    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        -m youtube_code.step6_auswertung.schockfenster_bericht

Outputs (outputs/segment_analysis/):
  - schockfenster_ergebnisse.csv: eine Zeile je Schock x Fensterbreite x
    Beobachtungsebene x Dimension x Metrik x Testtyp (post_dummy/interaktion)
    x Gruppe/Referenzgruppe.
  - schockfenster_methodik.md: Formel-Dokumentation, Ereignistag-Konvention,
    Begruendung der breiteren Kanalpopulation, Sparsity-Limitation.
"""

import os

import numpy as np
import pandas as pd

from youtube_code.config import OUTPUTS
from youtube_code.store import video_registry
from youtube_code.step6_auswertung.deskriptiv_aggregation import lade_medientyp, lade_ideologie
from youtube_code.step6_auswertung.deskriptiv_plots import baue_gruppe5, GRUPPE5_REIHENFOLGE
from youtube_code.step6_auswertung.prepare_success_metrics import (
    berechne_erfolgsmetriken, aggregiere_kanal_periode_erfolg, TOPIC,
)
from youtube_code.step6_auswertung.bericht_utils import post_dummy_test, interaktions_test

RESULTS_PATH = OUTPUTS / "segment_analysis"
os.makedirs(RESULTS_PATH, exist_ok=True)

PFAD_ERGEBNISSE = RESULTS_PATH / "schockfenster_ergebnisse.csv"
PFAD_METHODIK = RESULTS_PATH / "schockfenster_methodik.md"

# =========================================================
# CONFIG (hier neue Schocks/Fensterbreiten/
# Dimensionen ergaenzen, kein Code-Umbau noetig)
# =========================================================

# Jeder Eintrag: Ereignisdatum (ISO-String) + Label + optionaler
# Video-Filter. video_filter="nur_kriegsvideos" beschraenkt die Videos
# dieses Schocks auf ist_kriegsvideo == 1 (z.B. um "Kriegsbeginn" wahlweise
# nur ueber Kriegsvideos statt alle Videos zu pruefen); Default "alle_videos".
SCHOCKS = {
    "kriegsbeginn": {
        "datum": "2022-02-24",
        "label": "Kriegsbeginn",
        "video_filter": "alle_videos",
    },
    "us_wahl_2024": {
        "datum": "2024-11-05",
        "label": "US-Wahl (Trump)",
        "video_filter": "alle_videos",
    },
    "us_wahl_2024_kriegsvideos": {
        "datum": "2024-11-05",
        "label": "US-Wahl (Trump)",
        "video_filter": "nur_kriegsvideos",
    },
    # Bucha (2026-09-10, Nutzervorgabe): Bekanntwerden des Massakers, nachdem
    # sich russische Truppen aus der Region Kiew zurueckgezogen hatten -
    # internationale Medien berichteten ab dem 3./4.4.2022 breit. video_filter
    # bewusst "alle_videos" statt "nur_kriegsvideos": position_russland/
    # position_westpolitik sind ohnehin nur fuer die LLM-klassifizierte
    # Teilmenge belegt (siehe Moduldocstring), die view_count/log_views-Laeufe
    # fuer diesen Schock profitieren dagegen von der vollen Population.
    "bucha": {
        "datum": "2022-04-03",
        "label": "Bucha bekannt",
        "video_filter": "alle_videos",
    },

    # Vier weitere Kriegsereignisse (2026-09-10, Nutzervorgabe): Validierung
    # des Bucha-Musters (ÖRR bewegt sich bei position_russland/gruppe5 nicht,
    # andere Gruppen schon) an inhaltlich unterschiedlichen Ereignistypen -
    # siehe schockfenster_methodik.md Abschnitt "Validierungs-Schocks" fuer
    # die vollstaendige Begruendung je Ereignis.
    "olenivka": {
        "datum": "2022-07-29",
        "label": "Olenivka-Gefangenenlager",
        "video_filter": "alle_videos",
    },
    "isjum": {
        "datum": "2022-09-16",
        "label": "Isjum-Massengraeber",
        "video_filter": "alle_videos",
    },
    "nord_stream": {
        "datum": "2022-09-26",
        "label": "Nord-Stream-Sabotage",
        "video_filter": "alle_videos",
    },
    "annexion_mobilisierung": {
        "datum": "2022-09-21",
        "label": "Annexion + Mobilisierung",
        "video_filter": "alle_videos",
    },

    # weiteres Ereignis: einfach neuen Eintrag ergaenzen, z.B.
    # "neues_ereignis": {"datum": "JJJJ-MM-TT", "label": "...",
    #                     "video_filter": "alle_videos"},
}

# Mehrere Fensterbreiten parallel als eingebaute Sensitivitaetspruefung -
# schmale Fenster (mehr Trennschaerfe zum Ereignis, aber duenner besetzt)
# gegen breitere (mehr Beobachtungen, aber naeher an Monats-Aufloesung).
FENSTER_BREITEN_TAGE = [7, 14, 30]

# Heterogenitaetsdimensionen: Spalte muss NACH lade_basisdaten() an der
# Video-Ebene vorhanden sein. "medientyp" enthaelt bewusst kein "Politiker/
# Partei" (siehe Moduldocstring: baue_gruppe5() filtert das bereits aus der
# Kanalpopulation heraus).
HETEROGENITAETS_DIMENSIONEN = {
    "gruppe5": {"spalte": "gruppe5", "werte": GRUPPE5_REIHENFOLGE},
    "medientyp": {"spalte": "medientyp", "werte": ["ÖRR", "Traditionelles Medium", "Alternatives Medium"]},
    "ideologie_gruppe": {"spalte": "ideologie_gruppe", "werte": ["links", "mitte", "rechts"]},
}

METRIKEN = ["view_count", "log_views", "position_russland", "position_westpolitik"]

MIN_KANAELE_JE_GRUPPE = 5  # wie bericht_utils.interaktions_test()


# =========================================================
# DATEN LADEN
# =========================================================

PFAD_POSITION = OUTPUTS / "segment_analysis" / "channel_video_position.csv"


def lade_basisdaten():
    """Video-Ebene fuer die BREITERE Kanalpopulation (alle Kanaele mit
    Medientyp-Klassifikation, siehe Moduldocstring) mit Erfolgsmetriken,
    Kriegsvideo-Flag, Kanalmerkmalen (gruppe5/medientyp/ideologie_gruppe) und
    - seit 2026-09-10 - position_russland/position_westpolitik (Haltung
    gegenueber Russland bzw. westlicher Ukraine-Politik, aus
    channel_video_position.csv gemergt). Beide Positions-Spalten bleiben NaN
    fuer Videos ausserhalb der LLM-klassifizierten Teilmenge - das ist
    gewollt, siehe Moduldocstring "METRIKEN"/"Kanalpopulation". baue_gruppe5()
    filtert dabei zusaetzlich auf vollstaendig klassifizierte Kanaele (siehe
    dortiger Docstring)."""
    medientyp = lade_medientyp()
    channel_ids = medientyp["channel_id"].astype(str).tolist()
    print(f"[Kanalpopulation] {len(channel_ids)} Kanaele mit Medientyp-Klassifikation "
          f"(breiter als die Frage-1-Whitelist, siehe schockfenster_bericht.md).")

    video_ebene = video_registry.get_video_stats(channel_ids=channel_ids)
    video_ebene["channel_id"] = video_ebene["channel_id"].astype(str)
    video_ebene["published_at"] = pd.to_datetime(
        video_ebene["published_at"], errors="coerce", utc=True
    ).dt.tz_localize(None)

    ohne_datum = video_ebene["published_at"].isna()
    if ohne_datum.any():
        print(f"[Video-Stats] {int(ohne_datum.sum())} von {len(video_ebene)} Videos ohne "
              f"published_at -> verworfen.")
        video_ebene = video_ebene[~ohne_datum]

    video_ebene = berechne_erfolgsmetriken(video_ebene)

    relevanz = video_registry.get_topic_relevance(topic=TOPIC, video_ids=video_ebene["video_id"].tolist())
    relevante_ids = set(relevanz.loc[relevanz["is_relevant"] == 1, "video_id"])
    video_ebene["ist_kriegsvideo"] = video_ebene["video_id"].isin(relevante_ids).astype(int)

    video_ebene = video_ebene.merge(medientyp, on="channel_id", how="left")
    ideologie = lade_ideologie()
    video_ebene = video_ebene.merge(ideologie, on="channel_id", how="left")
    video_ebene = baue_gruppe5(video_ebene)

    position = pd.read_csv(PFAD_POSITION, usecols=[
        "channel_id", "video_id", "position_russland", "position_westpolitik",
    ])
    position["channel_id"] = position["channel_id"].astype(str)
    position["video_id"] = position["video_id"].astype(str)
    video_ebene["video_id"] = video_ebene["video_id"].astype(str)
    video_ebene = video_ebene.merge(position, on=["channel_id", "video_id"], how="left")
    print(f"[Position] {video_ebene['position_russland'].notna().sum()} von "
          f"{len(video_ebene)} Videos mit position_russland belegt (LLM-klassifizierte "
          f"Teilmenge, siehe Moduldocstring).")

    print(f"[Basisdaten] {len(video_ebene)} Videos, {video_ebene['channel_id'].nunique()} "
          f"Kanaele nach Medientyp-/Ideologie-Merge und gruppe5-Filter.")
    return video_ebene


def berechne_tage_relativ(df, event_datum):
    """Neue Spalte tage_relativ = Tage zwischen published_at und
    event_datum (negativ = vor dem Ereignis, 0 = am Ereignistag,
    positiv = danach)."""
    event_datum = pd.Timestamp(event_datum)
    df = df.copy()
    df["tage_relativ"] = (df["published_at"] - event_datum).dt.days
    return df


def filtere_fenster(df, fenster_breite_tage, video_filter):
    """Behaelt nur Videos mit |tage_relativ| <= fenster_breite_tage, optional
    zusaetzlich auf Kriegsvideos beschraenkt (video_filter="nur_kriegsvideos",
    siehe SCHOCKS-Konfiguration)."""
    gefiltert = df[df["tage_relativ"].abs() <= fenster_breite_tage].copy()
    if video_filter == "nur_kriegsvideos":
        gefiltert = gefiltert[gefiltert["ist_kriegsvideo"] == 1]
    elif video_filter != "alle_videos":
        raise ValueError(f"Unbekannter video_filter: {video_filter!r}")

    print(f"  [Fenster] +/-{fenster_breite_tage} Tage, video_filter={video_filter}: "
          f"{len(gefiltert)} Videos, {gefiltert['channel_id'].nunique()} Kanaele.")
    return gefiltert


def baue_kanal_fenster(video_fenster, dimensionen_spalten):
    """Aggregiert video_fenster (mit Spalte fenster_bucket = -1/+1, siehe
    main()) zu Kanal x Fensterseite ueber die bereits vorhandene
    aggregiere_kanal_periode_erfolg() (Beobachtungsebene 2, siehe
    Moduldocstring) und mergt die kanalkonstanten Heterogenitaetsspalten
    wieder dazu (gehen bei der Aggregation verloren). aggregiere_kanal_
    periode_erfolg() kennt nur die Erfolgsmetriken (view_count/log_views/
    engagement_rate) - fuer position_russland/position_westpolitik (seit
    2026-09-10, siehe Moduldocstring "METRIKEN") wird deshalb HIER eine
    eigene, kleine Mittelwert-Aggregation ergaenzt (pandas mean() ignoriert
    NaN automatisch, wie bei prepare_channel_scores.py::prepare_position_
    results()) statt die geteilte Erfolgsmetrik-Funktion fuer diesen einen
    Anwendungsfall zu erweitern."""
    kanal_fenster = aggregiere_kanal_periode_erfolg(video_fenster, "fenster_bucket")

    position_spalten = [s for s in ("position_russland", "position_westpolitik")
                        if s in video_fenster.columns]
    if position_spalten:
        position_agg = (video_fenster.groupby(["channel_id", "fenster_bucket"], as_index=False)
                         [position_spalten].mean())
        kanal_fenster = kanal_fenster.merge(position_agg, on=["channel_id", "fenster_bucket"], how="left")

    kanalmerkmale = (video_fenster[["channel_id"] + dimensionen_spalten]
                      .drop_duplicates(subset="channel_id"))
    kanal_fenster = kanal_fenster.merge(kanalmerkmale, on="channel_id", how="left")
    return kanal_fenster


# =========================================================
# ANALYSE
# =========================================================

def _meta(schock_name, schock_cfg, fenster_breite, beobachtungsebene, dimension_name, metrik, testtyp):
    return {
        "schock": schock_name,
        "schock_label": schock_cfg["label"],
        "event_datum": schock_cfg["datum"],
        "fenster_breite_tage": fenster_breite,
        "video_filter": schock_cfg["video_filter"],
        "beobachtungsebene": beobachtungsebene,
        "dimension": dimension_name,
        "metrik": metrik,
        "testtyp": testtyp,
    }


def fuehre_dimension_analyse(video_fenster, kanal_fenster, schock_name, schock_cfg,
                              fenster_breite, dimension_name, dimension_cfg, metrik):
    """Post-Dummy- und Interaktionstest fuer EINE Kombination aus Schock x
    Fensterbreite x Dimension x Metrik, auf beiden Beobachtungsebenen (siehe
    Moduldocstring). Gibt eine Liste von Ergebnis-dicts zurueck (leer, wenn
    alle vier Tests wegen zu duenner Besetzung uebersprungen wurden)."""
    ergebnisse = []
    dim_spalte = dimension_cfg["spalte"]
    dim_werte = dimension_cfg["werte"]
    bezeichnung = f"{schock_name}/{fenster_breite}T/{dimension_name}/{metrik}"

    # --- Beobachtungsebene 1: Video-Ebene (periode = tage_relativ) ---
    gesamt = post_dummy_test(video_fenster, metrik, "tage_relativ",
                              bezeichnung=f"{bezeichnung}/video/gesamt")
    if gesamt:
        ergebnisse.append({**_meta(schock_name, schock_cfg, fenster_breite, "video",
                                    dimension_name, metrik, "post_dummy"), **gesamt})

    interaktion = interaktions_test(video_fenster, metrik, "tage_relativ",
                                     dim_spalte, dim_werte, MIN_KANAELE_JE_GRUPPE)
    if interaktion:
        ergebnisse.append({**_meta(schock_name, schock_cfg, fenster_breite, "video",
                                    dimension_name, metrik, "interaktion"), **interaktion})

    # --- Beobachtungsebene 2: Kanal x Fensterseite (periode = fenster_bucket) ---
    gesamt_kf = post_dummy_test(kanal_fenster, metrik, "fenster_bucket",
                                 bezeichnung=f"{bezeichnung}/kanal_fenster/gesamt")
    if gesamt_kf:
        ergebnisse.append({**_meta(schock_name, schock_cfg, fenster_breite, "kanal_fenster",
                                    dimension_name, metrik, "post_dummy"), **gesamt_kf})

    interaktion_kf = interaktions_test(kanal_fenster, metrik, "fenster_bucket",
                                        dim_spalte, dim_werte, MIN_KANAELE_JE_GRUPPE)
    if interaktion_kf:
        ergebnisse.append({**_meta(schock_name, schock_cfg, fenster_breite, "kanal_fenster",
                                    dimension_name, metrik, "interaktion"), **interaktion_kf})

    return ergebnisse


def schreibe_methodik():
    text = f"""# Methodik: Schockfenster-Bericht

Antwort auf TODO 3 aus `.claude/Aufgaben.md`. Vollstaendige Herleitung in
`.claude/plans/schockfenster_bericht.md`.

## Fensterdefinition

`tage_relativ = (published_at - Ereignisdatum).dt.days`, je Schock aus
`SCHOCKS` neu berechnet. Ein Fenster der Breite W (`FENSTER_BREITEN_TAGE`)
behaelt alle Videos mit `|tage_relativ| <= W`. Der Ereignistag selbst
(`tage_relativ == 0`) zaehlt in der aggregierten Beobachtungsebene
(`fenster_bucket`) zu "nach" (`fenster_bucket = +1`), in der Video-Ebene geht
er als `tage_relativ = 0 >= 0` ebenfalls in "post" ein.

## Beobachtungsebenen (zwei getrennte Robustheits-Durchlaeufe)

- **Video-Ebene**: jede Zeile ein Video, Periodenspalte `tage_relativ`
  (kontinuierlich in Tagen). Mehr Beobachtungen, aber Kanaele mit vielen
  Videos wiegen staerker.
- **Kanal x Fensterseite**: `fenster_bucket = -1`/`+1`, ueber
  `prepare_success_metrics.aggregiere_kanal_periode_erfolg()` gebildet -
  konsistent mit dem dokumentierten Kanal-x-Periode-Interface von
  `bericht_utils.post_dummy_test()`/`interaktions_test()`, aber nur zwei
  Zeilen je Kanal (weniger Varianz bei sehr engen Fenstern).
  `position_russland`/`position_westpolitik` (seit 2026-09-10) werden dabei
  in `baue_kanal_fenster()` separat per Mittelwert aggregiert, weil
  `aggregiere_kanal_periode_erfolg()` nur die Erfolgsmetriken kennt.

## Kanalpopulation

Bewusst BREITER als die Frage-1-Whitelist: alle Kanaele mit
Medientyp-Klassifikation (`lade_medientyp()`), zusaetzlich gefiltert durch
`baue_gruppe5()` auf vollstaendig klassifizierte Kanaele (OERR/Traditionell/
Alternative Medien MIT Ideologie-Einordnung, kein Politiker/Partei). Grund:
eine reine Reichweiten-Analyse braucht keinen Populismus-Score, und bei
engen Tage-Fenstern ist die Power ohnehin knapp (viele Kanaele haben keine
Videos in Vor- UND Nachfenster).

## Heterogenitaetstest

`bericht_utils.interaktions_test()` unveraendert wiederverwendet: Kanal-FE +
Post-Dummy + Post:Gruppe-Interaktion, gemeinsamer F-Test auf alle
Interaktionsterme, geclusterte Standardfehler auf Kanalebene. Gruppen mit
weniger als `MIN_KANAELE_JE_GRUPPE` Kanaelen werden vom Test ausgeschlossen.

## Limitation: Sparsity bei engen Fenstern

Je enger das Fenster, desto weniger Kanaele haben Videos in BEIDEN
Fensterhaelften (Voraussetzung fuer eine Kanal-FE-Schaetzung). Beide
wiederverwendeten Testfunktionen erkennen das automatisch (`n_kanaele < 2`
bzw. `post.nunique() < 2`) und geben `None` zurueck statt eines instabilen
Schaetzers - solche Kombinationen fehlen einfach in
`schockfenster_ergebnisse.csv`. Die mehreren `FENSTER_BREITEN_TAGE` sind die
eingebaute Sensitivitaetspruefung gegen dieses Problem.

## Zusaetzliche Metriken: position_russland/position_westpolitik

Seit 2026-09-10 (Nutzervorgabe, Anschlussfrage an den Bucha-Schock) laufen
neben den Erfolgsmetriken auch `position_russland`/`position_westpolitik`
(Haltung gegenueber Russland bzw. westlicher Ukraine-Politik, Prompt
`POSITION_V1`) als ganz normale `METRIKEN`-Eintraege mit - technisch
unveraendert dieselbe `post_dummy_test()`/`interaktions_test()`-Maschinerie,
nur mit `channel_video_position.csv` als zusaetzlicher, vorher an die
Video-Ebene gemergter Spalte. Beide Spalten sind NaN fuer Videos ausserhalb
der LLM-klassifizierten Teilmenge (~29.600 von den insgesamt weit mehr
Videos der breiten Schockfenster-Kanalpopulation); `dropna()` in beiden
Testfunktionen entfernt diese Zeilen automatisch, OHNE die
Erfolgsmetriken-Zeilen fuer denselben Schock/dieselbe Fensterbreite zu
beeinflussen (jede Metrik hat ihren eigenen `n_beobachtungen`/`n_kanaele` in
`schockfenster_ergebnisse.csv`). Konkret heisst das: fuer
`position_russland`/`position_westpolitik` ist die Power bei engen
Fensterbreiten (7/14 Tage) nochmal deutlich niedriger als fuer
`view_count`/`log_views` auf derselben Fensterbreite - bei der Interpretation
immer zuerst `n_beobachtungen`/`n_kanaele` der jeweiligen Zeile pruefen.

## Schock "bucha"

Bekanntwerden des Massakers von Butscha (Region Kiew) nach dem Abzug
russischer Truppen Ende Maerz 2022 - internationale Medien berichteten ab
dem 3./4.4.2022 breit, `datum = "2022-04-03"`. Ein Blick in die bereits
vorhandene Monats-Zeitreihe (`channel_monat_position_timeseries.csv`, ueber
alle Kanaele nach `n_deskiptiv` gewichtet) zeigt VOR diesem Lauf kein
eigenstaendiges Bucha-Signal: der staerkste Ausschlag Richtung
"russlandkritisch" liegt bereits im Kriegsbeginn-Monat selbst
(rel_monat=0, Februar 2022, Ø ≈ -0.63) und klingt danach graduell ab (Maerz
≈ -0.50, April/Bucha-Monat ≈ -0.47, Mai ≈ -0.26) - keine Umkehr, kein
zusaetzlicher Sprung im Bucha-Monat. Dieser Lauf ist also ausdruecklich ein
EXPLORATIVER Test auf einen moeglichen tagesgenauen Effekt, der im
Monatsmittel verschwinden wuerde (Nutzerwunsch trotz dieser Einschraenkung) -
kein Befund, der schon durch Vorarbeit gestuetzt ist.

## Validierungs-Schocks

Vier weitere Ereignisse (2026-09-10, Nutzervorgabe), um zu pruefen, ob sich
das Bucha-Muster bei `position_russland`/`gruppe5` (ÖRR bewegt sich nicht,
andere Gruppen schon - siehe Abschnitt "Schock bucha" oben, dortige
Einschraenkung zur fehlenden Erklaerung fuer den ÖRR-Nulleffekt gilt
unveraendert) an unterschiedlichen Ereignistypen wiederholt:

- **olenivka** (29.7.2022): Explosion im Gefangenenlager Olenivka mit vielen
  toten ukrainischen Kriegsgefangenen - anders als bei Bucha ist die
  Verantwortung STRITTIG (Russland beschuldigt Ukraine, Ukraine Russland).
  Falls das Muster nur bei eindeutig zugeschriebenen Graueltaten auftritt,
  sollte es hier schwaecher oder anders ausfallen.
- **isjum** (16.9.2022): Massengraeber bei Isjum nach russischem Rueckzug -
  direktestes Analogon zu Bucha (erneute Graueltat-Aufdeckung, Verantwortung
  eindeutig), sauberster Wiederholungstest derselben Hypothese.
- **nord_stream** (26.9.2022): Sabotage der Nord-Stream-Pipelines -
  Verantwortung bis heute ungeklaert/umstritten, rechte alternative Medien
  vertraten haeufig abweichende Theorien (USA/Ukraine statt Russland
  verantwortlich) - Kontrastfall, an dem sich eine andersartige statt
  gleichgerichtete Reaktion zeigen koennte.
- **annexion_mobilisierung** (21.9.2022, Beginn der russischen
  Teilmobilisierung; die Annexionsreferenden liefen bis 27.9., die formale
  Annexion war am 30.9.): Eskalation durch Russland selbst statt Aufdeckung
  einer vergangenen Tat - testet, ob das Muster auch auf russische
  Eskalation (nicht nur auf Enthuellung) reagiert.

Alle vier mit `video_filter="alle_videos"` (gleiche Begruendung wie bei
"bucha" oben). Die Gruppenaufschluesselung (welche gruppe5-Gruppe treibt
eine ggf. signifikante Interaktion) steht NICHT in
`schockfenster_ergebnisse.csv` (nur der gemeinsame F-Test, siehe
`bericht_utils.interaktions_test()`) - dafuer wurde je Schock ein
Zusatz-Skript ausserhalb des Repos (Scratchpad) mit `post_dummy_test()` je
Einzelgruppe gerechnet, Ergebnisse siehe Gespraechsverlauf/Analyse-Notizen.

## Rohwerte, keine Alters-Normalisierung

`view_count`/`log_views` sind rohe Werte ohne Division durch Tage seit
Veroeffentlichung (siehe `prepare_success_metrics.py`-Moduldocstring) - bei
sehr engen Nach-Fenstern (z.B. 7 Tage) haben Videos ohnehin kaum Zeit,
Views zu sammeln; das betrifft Vor- UND Nachfenster gleichermassen und
verzerrt den Vorher/Nachher-Vergleich daher nicht systematisch, macht die
absoluten Werte aber nicht mit spaeteren Monats-/Quartals-Analysen
vergleichbar.
"""
    PFAD_METHODIK.write_text(text, encoding="utf-8")
    print(f"[Methodik] -> {PFAD_METHODIK}")


# =========================================================
# MAIN
# =========================================================

def main():
    basisdaten = lade_basisdaten()
    dimensionen_spalten = [cfg["spalte"] for cfg in HETEROGENITAETS_DIMENSIONEN.values()]
    alle_ergebnisse = []

    for schock_name, schock_cfg in SCHOCKS.items():
        print(f"\n=== Schock: {schock_cfg['label']} ({schock_cfg['datum']}) ===")
        mit_periode = berechne_tage_relativ(basisdaten, schock_cfg["datum"])

        for fenster_breite in FENSTER_BREITEN_TAGE:
            video_fenster = filtere_fenster(mit_periode, fenster_breite, schock_cfg["video_filter"])
            video_fenster["fenster_bucket"] = np.where(video_fenster["tage_relativ"] < 0, -1, 1)
            kanal_fenster = baue_kanal_fenster(video_fenster, dimensionen_spalten)

            for dimension_name, dimension_cfg in HETEROGENITAETS_DIMENSIONEN.items():
                for metrik in METRIKEN:
                    alle_ergebnisse.extend(fuehre_dimension_analyse(
                        video_fenster, kanal_fenster, schock_name, schock_cfg,
                        fenster_breite, dimension_name, dimension_cfg, metrik,
                    ))

    ergebnisse_df = pd.DataFrame(alle_ergebnisse)
    ergebnisse_df.to_csv(PFAD_ERGEBNISSE, index=False, encoding="utf-8")
    print(f"\n[Ausgabe] {len(ergebnisse_df)} Zeilen -> {PFAD_ERGEBNISSE}")

    schreibe_methodik()


if __name__ == "__main__":
    main()

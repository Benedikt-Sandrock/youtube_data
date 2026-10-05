# -*- coding: utf-8 -*-
"""
frage4_kriegspraemie_marktanteil_phasen_bericht.py

Phasenweise Ergaenzung zu `frage4_kriegspraemie_marktanteil_plots.py` (Schritt 8d) -
Nutzervorgabe nach dem Marktanteils-Plot: "Ich moechte eine Phasenweise Tabelle. Sie soll die
jeweiligen Marktanteile der Gruppen (an Kriegsberichterstattung, allen politischen Videos, alle
Videos) und auch die absolute Gesamtnachfrage zeigen, um zu sehen, ob der Kuchen waechst oder
nur umverteilt wird."

Anders als 8d (EINE rel_monat-Zeitreihe, zwei Umfaenge im Zaehler/Vergleichsgruppen-Kontrast:
Kriegsvideos vs. andere politische Videos) aggregiert dieses Skript auf die Phasenaufteilung aus
`frage4_kriegspraemie_medientyp_bericht.py` (PHASEN, echter Import - siehe dortigen
Moduldocstring fuer die inhaltliche Begruendung je Phase), ergaenzt um eine eigene
"Vorkriegszeitraum"-Phase (das komplette Vorkriegsfenster aus `lade_basisdaten()`, PERIODE_MIN
bis -1 - Baseline fuer den Kuchen-Wachstumsvergleich) UND DREI statt zwei Umfaenge:

  - "kriegsvideos": ist_kriegsvideo == 1
  - "andere_politische_videos": ist_kriegsvideo == 0 UND ist_politics_topic == True
    (topic_categories='Politics') - schliesst Kriegsvideos EXPLIZIT aus (Nutzervorgabe
    2026-09-10, analog zu 8d/8c: "Kriegsvideos" und "andere politische Videos" sollen sich
    gegenseitig ausschliessen statt zu ueberlappen; bis dahin hiess dieser Umfang
    "politische_videos" und enthielt Kriegsvideos MIT)
  - "alle_videos": kein Filter (die gesamte Whitelist-Stichprobe)

"kriegsvideos" und "andere_politische_videos" sind seit 2026-09-10 disjunkt (jedes Video faellt
in hoechstens einen der beiden), "alle_videos" bleibt eine echte Obermenge von beiden (jede
Video-ID aus den beiden anderen Umfaengen ist auch in "alle_videos" enthalten). Damit lassen
sich weiterhin drei zunehmend WEITE Betrachtungsebenen ablesen ("nur beim Kriegsthema", "bei
anderen politischen Themen", "insgesamt") - anders als in der fruehreren Fassung schliessen sich
die ersten beiden Umfaenge nun aber gegenseitig aus, statt dass "politische_videos" die
Kriegsvideos mit einschloss.

Je Zelle (Phase x Umfang x Gruppe5):

    anteil = sum(view_count | Gruppe, Phase, Umfang) / sum(view_count | ALLE 5 Gruppen, Phase, Umfang) * 100

Die 5 Anteile summieren sich je (Phase, Umfang) IMMER zu 100% (wie 8d), UND zusaetzlich wird
sum(view_count | ALLE 5 Gruppen, Phase, Umfang) selbst als "Gesamtnachfrage" ausgegeben - das ist
die eigentliche Antwort auf die Nutzerfrage "waechst der Kuchen oder wird er nur umverteilt":
steigt diese Summe von Phase zu Phase, waechst die absolute Nachfrage nach diesem Umfang,
unabhaengig davon, wie sie sich auf die 5 Gruppen verteilt. Da Phasen unterschiedlich lang sind
(siehe PHASEN), wird zusaetzlich Gesamtnachfrage/Monat (Summe / Anzahl Monate der Phase)
ausgegeben, um Phasen unterschiedlicher Laenge fair zu vergleichen.

Datenquelle: `lade_basisdaten()` aus `frage4_kriegspraemie_relative_views_plots.py` (echter
Import - Video-Ebene, bereits Whitelist-gefiltert, mit gruppe5/ist_kriegsvideo/
ist_politics_topic/rel_monat), `PHASEN` und `_phase_fenster()` aus
`frage4_kriegspraemie_medientyp_bericht.py` (echte Importe, keine Duplikate).

Mindestbesetzung: eine (Phase, Umfang)-Zelle wird GESAMT (ueber alle 5 Gruppen) uebersprungen,
wenn sie unter MIN_VIDEOS_GESAMT_PRO_PHASE liegt (analog 8d, aber auf Phasenebene hochskaliert,
da eine Phase mehrere Monate umfasst) - genau wie bei 8d wirkt die Schwelle auf die GESAMTE
Zelle, nicht auf einzelne Gruppen, damit die 5 Anteile immer zu 100% aufsummieren.

Schreibt `frage4_kriegspraemie_marktanteil_phasen_bericht.csv` (eine Zeile je Phase x Umfang x
Gruppe5, inkl. Gesamtnachfrage-Spalten) und `..._bericht.md` (dieselben Zahlen als lesbare
Tabelle, eine Tabelle je Umfang, Zeilen = Phasen, Spalten = Gruppe5-Anteile + Gesamtnachfrage).

Shift-Share-Zerlegung (fuer ALLE DREI Umfaenge, Nutzervorgabe - urspruenglich nur fuer
"kriegsvideos" eingefuehrt, auf Nutzerwunsch auf "andere_politische_videos" und "alle_videos"
erweitert): Der Marktanteil einer Gruppe5-Kategorie an einem Umfang wird zusaetzlich
multiplikativ zerlegt in

    Marktanteil(g) = output_anteil(g) x relative_reichweite(g)

    output_anteil(g)       = n_videos_gruppe(g) / n_videos_gesamt (alle 5 Gruppen, im Umfang)
    relative_reichweite(g) = views_pro_video_gruppe(g) / views_pro_video_alle (im Umfang)
    views_pro_video_gruppe = views_gruppe_summe / n_videos_gruppe  (arithmetisches Mittel,
                              EINZELVIDEO-Ebene, nicht Kanal-Periode-vorgemittelt)

Aggregationsebene/-mass mit Nutzer abgestimmt (nicht selbst entschieden): Nur das arithmetische
Mittel auf Einzelvideo-Ebene macht die Zerlegung exakt multiplikativ konsistent mit dem bereits
berichteten Marktanteil (der selbst video-gepoolt ueber sum(view_count) berechnet wird, siehe
oben) - Median oder eine Kanal-Perioden-Vorglaettung wuerden die Identitaet brechen, weil sie
Kanaelen/Perioden statt Videos gleiches Gewicht geben. Die Zerlegung rechnet je Umfang
ausschliesslich INNERHALB des jeweiligen Umfangs (dort ist jedes Video genau einer
Gruppe5-Kategorie zugeordnet, keine Ueberschneidung) - dass sich die drei Umfaenge selbst
ueberschneiden (siehe oben), betrifft nur den Vergleich ZWISCHEN den Umfaengen, nicht die
Zerlegung je Umfang.

Validierung: `output_anteil x relative_reichweite` muss dem bereits berechneten `anteil_pct/100`
bis auf TOLERANZ_SHIFT_SHARE entsprechen - bei Abweichung bricht das Skript mit ValueError ab
(keine stille Korrektur, siehe berechne_tabelle()). Die Validierung laeuft je Umfang separat.

Zusaetzlich `n_videos_gruppe_pro_monat = n_videos_gruppe / n_monate` je Gruppe (Nutzervorgabe,
analog zu `views_gesamt_pro_monat` oben, aber je Gruppe statt aggregiert ueber alle 5 Gruppen) -
macht die absolute Videozahl zwischen unterschiedlich langen Phasen fair vergleichbar.

Laeuft direkt als Skript (sibling-Importe wie die anderen step6_auswertung-Dateien, kein -m):

    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe frage4_kriegspraemie_marktanteil_phasen_bericht.py

(im Ordner src/youtube_code/step6_auswertung/ ausgefuehrt).
"""

import pandas as pd

from youtube_code.config import OUTPUTS
from deskriptiv_plots import GRUPPE5_REIHENFOLGE
from frage4_kriegspraemie_relative_views_plots import lade_basisdaten
from frage4_kriegspraemie_medientyp_bericht import PHASEN, _phase_fenster

# =========================================================
# CONFIG
# =========================================================

# Gesamt-Mindestbesetzung je (Phase, Umfang)-Zelle (ueber alle 5 Gruppen zusammen, siehe
# Moduldocstring) - hoeher als bei 8d (MIN_VIDEOS_GESAMT_PRO_PERIODE=20), weil eine Phase
# mehrere Monate zusammenfasst.
MIN_VIDEOS_GESAMT_PRO_PHASE = 100

# Toleranz fuer die Shift-Share-Validierung (output_anteil x relative_reichweite == anteil_pct/100,
# fuer ALLE Umfaenge, siehe Moduldocstring) - reine Gleitkomma-Rundungstoleranz, kein
# methodischer Freiheitsgrad. Abweichung darueber hinaus -> Abbruch mit ValueError, keine
# stille Korrektur (Nutzervorgabe).
TOLERANZ_SHIFT_SHARE = 1e-6

UMFAENGE = {
    "kriegsvideos": {
        "titel": "Kriegsberichterstattung",
        "filter": lambda df: df["ist_kriegsvideo"] == 1,
    },
    "andere_politische_videos": {
        "titel": "Andere politische Videos (topic_categories='Politics', ohne Kriegsvideos)",
        "filter": lambda df: (df["ist_kriegsvideo"] == 0) & (df["ist_politics_topic"] == True),
    },
    "alle_videos": {
        "titel": "Alle Videos (keine Themen-Einschraenkung)",
        "filter": lambda df: pd.Series(True, index=df.index),
    },
}

PFAD_ERGEBNIS_CSV = OUTPUTS / "segment_analysis" / "frage4_kriegspraemie_marktanteil_phasen_bericht.csv"
PFAD_ERGEBNIS_MD = OUTPUTS / "segment_analysis" / "frage4_kriegspraemie_marktanteil_phasen_bericht.md"


# =========================================================
# SCHRITT 1: Phasen (inkl. Vorkriegszeitraum) zusammenstellen
# =========================================================

def baue_phasenliste(basisdaten):
    """Liefert [(phase_id, label, monat_min, monat_max)]: "Vorkriegszeitraum" (das komplette
    Vorkriegsfenster aus lade_basisdaten(), tatsaechliches Datenminimum bis -1) zuerst, dann
    PHASEN (echter Import) in Reihenfolge. monat_max=None (P5) wird auf das tatsaechliche
    Datenmaximum aufgeloest, damit die Monatsanzahl fuer Gesamtnachfrage/Monat definiert ist."""
    monat_min_gesamt = int(basisdaten["rel_monat"].min())
    monat_max_gesamt = int(basisdaten["rel_monat"].max())

    phasen = [("vorkrieg", "Vorkriegszeitraum", monat_min_gesamt, -1)]
    for phase_id, cfg in PHASEN.items():
        monat_max = cfg["monat_max"] if cfg["monat_max"] is not None else monat_max_gesamt
        phasen.append((phase_id, cfg["label"], cfg["monat_min"], monat_max))
    return phasen


# =========================================================
# SCHRITT 2: Marktanteile + Gesamtnachfrage je (Phase, Umfang, Gruppe5)
# =========================================================

def berechne_tabelle(basisdaten, phasenliste, min_videos_gesamt=MIN_VIDEOS_GESAMT_PRO_PHASE):
    """Eine Zeile je (Phase, Umfang, Gruppe5): Marktanteil (%), Gesamtnachfrage der Phase/des
    Umfangs (Summe view_count ueber ALLE 5 Gruppen - je Zeile identisch, zur direkten
    Ablesbarkeit dupliziert statt in eine eigene Tabelle ausgelagert), Gesamtnachfrage/Monat,
    n_videos_gesamt. Eine (Phase, Umfang)-Zelle wird komplett uebersprungen (alle 5 Gruppen),
    wenn die Gesamtbesetzung unter min_videos_gesamt liegt (siehe Moduldocstring).

    Fuer ALLE Umfaenge zusaetzlich die Shift-Share-Zerlegung des Marktanteils
    (output_anteil x relative_reichweite, siehe Moduldocstring) inkl. Validierung gegen
    anteil_pct - bricht mit ValueError ab, falls die Zerlegung nicht (bis auf
    TOLERANZ_SHIFT_SHARE) dem bereits berechneten Marktanteil entspricht."""
    zeilen = []
    uebersprungen = []
    for phase_id, label, monat_min, monat_max in phasenliste:
        phase_df = _phase_fenster(basisdaten, monat_min, monat_max)
        n_monate = monat_max - monat_min + 1
        for umfang_key, umfang_cfg in UMFAENGE.items():
            umfang_df = phase_df[umfang_cfg["filter"](phase_df)]
            n_gesamt = len(umfang_df)
            if n_gesamt < min_videos_gesamt:
                uebersprungen.append((label, umfang_cfg["titel"], n_gesamt))
                continue

            views_gesamt = float(umfang_df["view_count"].sum())
            je_gruppe = umfang_df.groupby("gruppe5", as_index=False).agg(
                views_summe=("view_count", "sum"), n_videos=("view_count", "size"))
            je_gruppe["anteil"] = je_gruppe["views_summe"] / views_gesamt * 100
            views_pro_video_alle = views_gesamt / n_gesamt

            for g in GRUPPE5_REIHENFOLGE:
                reihe = je_gruppe[je_gruppe["gruppe5"] == g]
                anteil = float(reihe["anteil"].iloc[0]) if not reihe.empty else 0.0
                n_videos_gruppe = int(reihe["n_videos"].iloc[0]) if not reihe.empty else 0
                zeile = {
                    "phase": phase_id, "phase_label": label,
                    "monat_min": monat_min, "monat_max": monat_max, "n_monate": n_monate,
                    "umfang": umfang_key, "umfang_titel": umfang_cfg["titel"],
                    "gruppe5": g, "anteil_pct": anteil, "n_videos_gruppe": n_videos_gruppe,
                    "views_gesamt": views_gesamt, "views_gesamt_pro_monat": views_gesamt / n_monate,
                    "n_videos_gesamt": n_gesamt,
                }

                # Shift-Share-Zerlegung fuer ALLE Umfaenge (nicht nur "kriegsvideos" -
                # Nutzervorgabe, siehe Moduldocstring).
                views_summe_g = (float(reihe["views_summe"].iloc[0]) if not reihe.empty
                                  else 0.0)
                views_pro_video_g = (views_summe_g / n_videos_gruppe
                                      if n_videos_gruppe > 0 else 0.0)
                output_anteil = n_videos_gruppe / n_gesamt
                relative_reichweite = (views_pro_video_g / views_pro_video_alle
                                        if n_videos_gruppe > 0 else 0.0)

                produkt = output_anteil * relative_reichweite
                erwartet = anteil / 100
                abweichung = abs(produkt - erwartet)
                if abweichung > TOLERANZ_SHIFT_SHARE:
                    raise ValueError(
                        "Shift-Share-Zerlegung stimmt nicht mit dem bereits berechneten "
                        f"Marktanteil ueberein (Phase='{label}', Umfang='{umfang_key}', "
                        f"Gruppe='{g}'): "
                        f"output_anteil x relative_reichweite = {produkt:.8f}, "
                        f"Marktanteil = {erwartet:.8f} "
                        f"(Abweichung {abweichung:.2e} > Toleranz {TOLERANZ_SHIFT_SHARE:.0e}). "
                        "Abbruch statt stiller Korrektur - bitte Berechnung pruefen."
                    )

                zeile.update({
                    "views_gruppe_summe": views_summe_g,
                    "views_pro_video_gruppe": views_pro_video_g,
                    "output_anteil": output_anteil,
                    "relative_reichweite": relative_reichweite,
                    "n_videos_gruppe_pro_monat": n_videos_gruppe / n_monate,
                })

                zeilen.append(zeile)

    if uebersprungen:
        print(f"[Marktanteil-Phasen] {len(uebersprungen)} (Phase, Umfang)-Zellen uebersprungen "
              f"(< {min_videos_gesamt} Videos insgesamt):")
        for label, titel, n in uebersprungen:
            print(f"  - {label} / {titel}: {n} Videos")

    tabelle = pd.DataFrame(zeilen)
    print(f"[Shift-Share] Validierung bestanden: output_anteil x relative_reichweite entspricht "
          f"in allen Phase x Umfang x Gruppe5-Zellen dem Marktanteil "
          f"(Toleranz {TOLERANZ_SHIFT_SHARE:.0e}).")
    return tabelle


# =========================================================
# SCHRITT 3: Lesbarer Bericht (eine Tabelle je Umfang)
# =========================================================

def _formatiere_zahl(x):
    """Tausenderpunkt statt Komma (deutsche Lesekonvention wie in den anderen Berichten)."""
    return f"{x:,.0f}".replace(",", ".")


def _formatiere_dezimal(x, nachkommastellen=1):
    """Wie _formatiere_zahl, aber mit Nachkommastellen (Tausenderpunkt, Komma als
    Dezimaltrennzeichen) - fuer Werte wie Videos/Monat, bei denen 0 Nachkommastellen zu grob
    waeren."""
    ganzzahl, _, dezimal = f"{x:,.{nachkommastellen}f}".partition(".")
    return f"{ganzzahl.replace(',', '.')},{dezimal}"


def _baue_wide_tabelle(zeilen, teil, phase_ids, spalten_fn, formatiere_fn):
    """Haengt eine Phase(Zeilen) x Gruppe5(Spalten)-Tabelle an `zeilen` an - gemeinsamer Aufbau
    fuer die Marktanteils- und die Shift-Share-Tabellen (gleiche Struktur, Nutzervorgabe)."""
    header = ["Phase"] + GRUPPE5_REIHENFOLGE + spalten_fn(None)
    zeilen.append("| " + " | ".join(header) + " |")
    zeilen.append("|" + "---|" * len(header))
    for phase_id in phase_ids:
        phase_teil = teil[teil["phase"] == phase_id]
        label = phase_teil["phase_label"].iloc[0]
        zeile = [label]
        for g in GRUPPE5_REIHENFOLGE:
            reihe = phase_teil[phase_teil["gruppe5"] == g]
            zeile.append(formatiere_fn(reihe) if not reihe.empty else "-")
        zeile.extend(spalten_fn(phase_teil))
        zeilen.append("| " + " | ".join(zeile) + " |")
    zeilen.append("")


def baue_bericht(tabelle):
    zeilen = [
        "# Marktanteile je Gruppe5-Kategorie nach Phase (Nachfrageperspektive)",
        "",
        "Ergaenzung zu `frage4_kriegspraemie_marktanteil_plots.py` (Schritt 8d) - phasenweise "
        "Aggregation statt Monatszeitreihe, UND mit der absoluten Gesamtnachfrage je Zelle, um "
        "zu erkennen, ob der 'Aufmerksamkeits-Kuchen' waechst oder nur zwischen den Gruppen "
        "umverteilt wird (siehe Moduldocstring von "
        "`frage4_kriegspraemie_marktanteil_phasen_bericht.py`).",
        "",
        "Marktanteil je Zelle (Phase x Umfang x Gruppe5): "
        "`anteil = sum(views | Gruppe) / sum(views | alle 5 Gruppen) * 100` - summiert sich je "
        "(Phase, Umfang) immer zu 100%. Gesamtnachfrage = `sum(views | alle 5 Gruppen)` "
        "derselben Zelle, zusaetzlich durch die Monatsanzahl der Phase geteilt "
        "(Gesamtnachfrage/Monat), da die Phasen unterschiedlich lang sind. Die drei Umfaenge "
        "sind NICHT exklusiv gegeneinander abgegrenzt (Kriegsvideos sind i. d. R. auch "
        "politische Videos, politische Videos eine Teilmenge aller Videos) - siehe "
        "Moduldocstring.",
        "",
    ]

    for umfang_key, umfang_cfg in UMFAENGE.items():
        teil = tabelle[tabelle["umfang"] == umfang_key]
        if teil.empty:
            continue
        zeilen.append(f"## Umfang: {umfang_cfg['titel']}")
        zeilen.append("")
        phase_ids = list(teil["phase"].drop_duplicates())
        _baue_wide_tabelle(
            zeilen, teil, phase_ids,
            spalten_fn=lambda pt: (["Gesamtnachfrage (Summe Views)", "Gesamtnachfrage/Monat",
                                     "n Videos"] if pt is None else
                                    [_formatiere_zahl(pt["views_gesamt"].iloc[0]),
                                     _formatiere_zahl(pt["views_gesamt_pro_monat"].iloc[0]),
                                     _formatiere_zahl(pt["n_videos_gesamt"].iloc[0])]),
            formatiere_fn=lambda reihe: f"{reihe['anteil_pct'].iloc[0]:.1f}%",
        )

        # Shift-Share-Zerlegung fuer ALLE Umfaenge (nicht nur "kriegsvideos" - Nutzervorgabe,
        # siehe Moduldocstring).
        zeilen.extend(_baue_shift_share_abschnitt(teil, phase_ids, umfang_cfg["titel"]))

    return "\n".join(zeilen) + "\n"


def _baue_shift_share_abschnitt(teil, phase_ids, umfang_titel):
    """Shift-Share-Zerlegung des Marktanteils eines Umfangs (Nutzervorgabe, urspruenglich nur
    fuer "kriegsvideos", auf Nutzerwunsch auf alle drei Umfaenge erweitert): gleiche Phase x
    Gruppe5-Struktur wie die Marktanteilstabelle, in vier Teiltabellen (n Videos, n Videos/Monat,
    Output-Anteil, relative Reichweite pro Video) statt einer ueberladenen Tabelle mit allen
    Spalten. `umfang_titel` fliesst nur in die Beschriftung ein (z. B. "Videos" statt
    "Kriegsvideos"), die zugrunde liegenden Spalten sind fuer alle Umfaenge identisch benannt."""
    einheit_plural = "Kriegsvideos" if "Kriegsberichterstattung" in umfang_titel else "Videos"
    einheit_singular = "Kriegsvideo" if einheit_plural == "Kriegsvideos" else "Video"
    abschnitt = [
        f"### Shift-Share-Zerlegung: Marktanteil = Output-Anteil x relative Reichweite "
        f"({umfang_titel})",
        "",
        "Zerlegt den Marktanteil aus der Tabelle oben multiplikativ: "
        "`Marktanteil(g) = output_anteil(g) x relative_reichweite(g)` mit "
        "`output_anteil(g) = n_videos_gruppe(g) / n_videos_gesamt(alle)` und "
        "`relative_reichweite(g) = views_pro_video_gruppe(g) / views_pro_video_alle` "
        "(`views_pro_video_gruppe = views_gruppe_summe / n_videos_gruppe`, arithmetisches "
        "Mittel auf Einzelvideo-Ebene - mit dem Nutzer abgestimmt, siehe Moduldocstring). "
        "Validiert gegen den bereits berichteten Marktanteil (Toleranz "
        f"{TOLERANZ_SHIFT_SHARE:.0e}) - das Skript wuerde bei Abweichung abbrechen, die "
        "folgenden Tabellen sind also rechnerisch konsistent mit der Marktanteilstabelle oben.",
        "",
        f"**n {einheit_plural} je Gruppe** (absolut - Basis von `output_anteil`, identisch mit "
        "`n_videos_gruppe` in der CSV fuer diesen Umfang):",
        "",
    ]
    _baue_wide_tabelle(
        abschnitt, teil, phase_ids,
        spalten_fn=lambda pt: [],
        formatiere_fn=lambda reihe: _formatiere_zahl(reihe["n_videos_gruppe"].iloc[0]),
    )
    abschnitt.append(f"**n {einheit_plural} je Gruppe pro Monat** (absolute Videozahl durch die "
                      "Monatsanzahl der Phase geteilt, `n_videos_gruppe_pro_monat` in der CSV - "
                      "macht die Videozahl zwischen unterschiedlich langen Phasen "
                      "vergleichbar, analog `views_gesamt_pro_monat` oben):")
    abschnitt.append("")
    _baue_wide_tabelle(
        abschnitt, teil, phase_ids,
        spalten_fn=lambda pt: [],
        formatiere_fn=lambda reihe: _formatiere_dezimal(reihe["n_videos_gruppe_pro_monat"].iloc[0]),
    )
    abschnitt.append(f"**Output-Anteil** (Anteil an der Anzahl {einheit_plural}, nicht an den "
                      "Views):")
    abschnitt.append("")
    _baue_wide_tabelle(
        abschnitt, teil, phase_ids,
        spalten_fn=lambda pt: [],
        formatiere_fn=lambda reihe: f"{reihe['output_anteil'].iloc[0] * 100:.1f}%",
    )
    abschnitt.append(f"**Relative Reichweite pro {einheit_singular}** "
                      "(Index, Gesamtdurchschnitt aller 5 Gruppen = 1,00 - Wert > 1 bedeutet "
                      f"ueberdurchschnittliche Views je {einheit_singular}):")
    abschnitt.append("")
    _baue_wide_tabelle(
        abschnitt, teil, phase_ids,
        spalten_fn=lambda pt: [],
        formatiere_fn=lambda reihe: f"{reihe['relative_reichweite'].iloc[0]:.2f}",
    )
    return abschnitt


# =========================================================
# MAIN
# =========================================================

def main():
    basisdaten = lade_basisdaten()
    phasenliste = baue_phasenliste(basisdaten)
    tabelle = berechne_tabelle(basisdaten, phasenliste)

    PFAD_ERGEBNIS_CSV.parent.mkdir(parents=True, exist_ok=True)
    tabelle.to_csv(PFAD_ERGEBNIS_CSV, index=False)
    print(f"[CSV] {PFAD_ERGEBNIS_CSV}")

    bericht = baue_bericht(tabelle)
    with open(PFAD_ERGEBNIS_MD, "w", encoding="utf-8") as f:
        f.write(bericht)
    print(f"[Bericht] {PFAD_ERGEBNIS_MD}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
marktanteil_themen_treiber_plots.py

Zerlegungs-Erweiterung von `marktanteil_themen_plots.py` (Schritt 8g) - Nutzervorgabe
2026-09-10: "Ich moechte, dass du ein neues Skript erstellst, das sie [die bisherigen
Marktanteilsgrafiken] etwas abaendert: Ich moechte die durchschnittlichen Views pro Video und
die Anzahl der Videos (also eine Shift-Share-Zerlegung wie im Marktanteilsbericht)." Nach
Rueckfrage (siehe Chatverlauf) entschieden: Basis ist AUSSCHLIESSLICH 8g (nicht 8d), und die
beiden neuen Linien zeigen ROHE Werte (Anzahl Videos, durchschnittliche Views pro Video je
Anzeigegruppe), NICHT die bereits in `frage4_kriegspraemie_marktanteil_phasen_bericht.py`
(Schritt 8e) berichteten normierten Groessen `output_anteil` (%) und `relative_reichweite`
(Index).

Hintergrund/Formel: Der in 8g berichtete Marktanteil einer Anzeigegruppe laesst sich exakt in
zwei Faktoren zerlegen (dieselbe Logik wie die Shift-Share-Zerlegung in 8e, hier aber als
monatliche Zeitreihe statt 5-Phasen-Tabelle UND als absolute Werte statt %/Index):

    views_summe(g) = n_videos(g) x views_pro_video(g)
    Marktanteil(g)% [8g] = views_summe(g) / views_summe(ALLE 5 rohen Gruppe5-Kategorien) * 100

Steigt der Marktanteil einer Gruppe, kann das an mehr VIDEOS (n_videos, "Output") liegen, an
HOEHEREN Views pro Video ("Reichweite pro Video") oder an beidem - genau diese beiden Treiber
zeigt dieses Skript getrennt. `views_pro_video(g) = views_summe(g) / n_videos(g)` wird dabei IMMER
NACH dem Kombinieren roher Gruppe5-Kategorien zu einer Anzeigegruppe neu berechnet (siehe
`aggregiere_anzeigegruppen_treiber()`), NICHT als Summe/Mittel der einzelnen Kategorie-Durch-
schnitte - ein arithmetisches Mittel von Durchschnitten waere bei unterschiedlich grossen
Kategorien falsch (Simpson-Paradox-Gefahr), die Summe aus views_summe/n_videos beider Kategorien
ist dagegen exakt.

Uebernimmt Szenarien (THEMEN/THEMEN_AKTIV, SCOPE_ALLE_POLITIK, SCOPE_ALLE_VIDEOS), Anzeigegruppen
(ANZEIGE_GRUPPEN/ANZEIGE_GRUPPEN_AKTIV), Mindestbesetzung (MIN_VIDEOS_GESAMT_PRO_PERIODE) und die
Basisdaten-Aufbereitung (baue_szenarien()/filter_fuer_scope()/ergaenze_themen_flags()) 1:1 als
echte Importe aus `marktanteil_themen_plots.py` - keine Neudefinition, keine Abweichung in der
Szenario-/Gruppen-Logik. `berechne_marktanteile()` aus `frage4_kriegspraemie_marktanteil_plots.py`
(8d, echter Import wie in 8g) liefert je (rel_monat, rohe Gruppe5-Kategorie) bereits views_summe
und n_videos inkl. der MIN_VIDEOS_GESAMT_PRO_PERIODE-Mindestbesetzung - nur die "wert"-Spalte
(Marktanteil %) dieser Funktion wird hier NICHT verwendet.

Zwei Grafik-Typen je Metrik (Anzahl Videos, Views/Video), dieselbe Struktur wie 8g (Typ-A/Typ-B-
Funktionen dort dienten als Vorlage, hier fuer zwei Metriken dupliziert statt parametrisiert
importiert, da 8g's Typ-A/Typ-B intern fest auf eine "wert"-Spalte zugreifen):

  Typ A ("je Szenario", 1 + len(THEMEN_AKTIV) Grafiken je Metrik): dick/duenn-Overlay wie 8g -
  dick = Metrik-Wert der Anzeigegruppen INNERHALB des Szenarios, duenn = derselbe Metrik-Wert bei
  der Vergleichsbasis (Thema -> alle_politische_videos -> alle_videos, dieselbe genestete Logik
  wie 8g). ACHTUNG bei der Metrik "Anzahl Videos": anders als beim Marktanteil (%) ist die duenne
  Linie hier i.d.R. HOEHER als die dicke, weil die Vergleichsbasis eine echte Obermenge ist (mehr
  Videos insgesamt) - die Grafik zeigt absolute Ausstoss-Niveaus, kein Verhaeltnis/keinen Anteil.

  Typ B ("je Anzeigegruppe ueber alle Themen", eine Grafik je aktive Anzeigegruppe x Metrik): eine
  Linie je Szenario, ohne Dick/Duenn-Vergleich - direkter Cross-Themen-Vergleich fuer eine
  Anzeigegruppe.

Wiederverwendet `plotte_kombinierte_grafik()`/`plotte_kombination()` aus
`frage2_sensitivitaet_plots.py` (echte Importe, wie 8g) mit `gruppen_spalte="anzeige_gruppe"`.

Schreibt je Metrik die PNGs, EINE gemeinsame CSV (`marktanteil_themen_treiber_monat.csv`, Zeilen =
Szenario x Periode x Anzeigegruppe, Spalten n_videos/views_pro_video/views_summe - dieselben Werte
wie in den Typ-A-"dick"-Linien) und eine Methodik-Uebersichtsdatei
(`marktanteil_themen_treiber_methodik.md`) nach
`outputs/segment_analysis/plots_marktanteil_themen_treiber/`.

Laeuft direkt als Skript (sibling-Importe wie die anderen step6_auswertung-Dateien, kein -m):

    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe marktanteil_themen_treiber_plots.py

(im Ordner src/youtube_code/step6_auswertung/ ausgefuehrt).
"""

import pandas as pd

from youtube_code.config import OUTPUTS
from frage4_kriegspraemie_relative_views_plots import lade_basisdaten, SPALTE_PERIODE
from frage4_kriegspraemie_marktanteil_plots import berechne_marktanteile
from frage2_sensitivitaet_plots import plotte_kombinierte_grafik, plotte_kombination
from marktanteil_themen_plots import (
    ANZEIGE_GRUPPEN, ANZEIGE_GRUPPEN_AKTIV, THEMEN_AKTIV,
    SCOPE_ALLE_VIDEOS, MIN_VIDEOS_GESAMT_PRO_PERIODE,
    ergaenze_themen_flags, baue_szenarien, filter_fuer_scope, _slug,
)

# =========================================================
# CONFIG
# =========================================================

# Zwei Treiber-Metriken (siehe Moduldocstring fuer die Formel) - Name -> Spalte in der von
# aggregiere_anzeigegruppen_treiber() gelieferten Tabelle + Achsenbeschriftung + Dateinamen-Praefix.
METRIKEN = {
    "anzahl_videos": {
        "titel": "Anzahl Videos",
        "spalte": "n_videos",
        "y_label": "Anzahl Videos je Monat",
    },
    "views_pro_video": {
        "titel": "Durchschnittliche Views pro Video",
        "spalte": "views_pro_video",
        "y_label": "Views pro Video (arithm. Mittel)",
    },
}

PFAD_PLOTS = OUTPUTS / "segment_analysis" / "plots_marktanteil_themen_treiber"
PFAD_CSV = PFAD_PLOTS / "marktanteil_themen_treiber_monat.csv"
PFAD_METHODIK = PFAD_PLOTS / "marktanteil_themen_treiber_methodik.md"


# =========================================================
# SCHRITT 1: Rohdaten je Szenario + Aggregation zu Anzeigegruppen
# =========================================================

def berechne_szenario_rohdaten(basisdaten, scope):
    """views_summe/n_videos je rohe Gruppe5-Kategorie x Periode fuer den Video-Ausschnitt von
    `scope`, inkl. MIN_VIDEOS_GESAMT_PRO_PERIODE-Mindestbesetzung (echter Import aus
    berechne_marktanteile(), Schritt 8d/8g - dessen "wert"-Spalte (Marktanteil %) wird hier
    NICHT verwendet, nur views_summe/n_videos). Gibt (rohdaten, n_videos_scope) zurueck."""
    umfang_df = filter_fuer_scope(basisdaten, scope)
    rohdaten = berechne_marktanteile(umfang_df, MIN_VIDEOS_GESAMT_PRO_PERIODE)
    return rohdaten, len(umfang_df)


def aggregiere_anzeigegruppen_treiber(rohdaten):
    """Fasst die rohen Gruppe5-Kennzahlen (views_summe, n_videos) zu den in
    ANZEIGE_GRUPPEN_AKTIV konfigurierten Anzeigegruppen zusammen - views_summe und n_videos
    werden SUMMIERT (fuer beide ist das exakt, siehe Moduldocstring), views_pro_video wird ERST
    NACH dieser Summation aus views_summe/n_videos NEU berechnet (nicht als Summe/Mittel der
    einzelnen Kategorie-Durchschnitte - waere bei unterschiedlich grossen Kategorien falsch)."""
    teile = []
    for name in ANZEIGE_GRUPPEN_AKTIV:
        rohe_gruppen = ANZEIGE_GRUPPEN[name]
        teil = rohdaten[rohdaten["gruppe5"].isin(rohe_gruppen)]
        if teil.empty:
            continue
        agg = teil.groupby(SPALTE_PERIODE, as_index=False).agg(
            views_summe=("views_summe", "sum"), n_videos=("n_videos", "sum"))
        agg["views_pro_video"] = agg["views_summe"] / agg["n_videos"]
        agg["anzeige_gruppe"] = name
        teile.append(agg)
    spalten = [SPALTE_PERIODE, "anzeige_gruppe", "n_videos", "views_pro_video", "views_summe"]
    return pd.concat(teile, ignore_index=True)[spalten] if teile else pd.DataFrame(columns=spalten)


def _mit_wert_spalte(df, metrik_spalte):
    """plotte_kombinierte_grafik()/plotte_kombination() erwarten eine Spalte "wert" - liefert
    eine Kopie von df mit "wert" = df[metrik_spalte] (je Metrik neu gesetzt, siehe METRIKEN)."""
    df = df.copy()
    df["wert"] = df[metrik_spalte]
    return df


# =========================================================
# SCHRITT 2: Plot Typ A (je Szenario, dick/duenn ueber Anzeigegruppen) - je Metrik
# =========================================================

def plotte_typ_a(anzeige_treiber_je_scope, szenarien, metrik_key, metrik_cfg):
    """Eine Grafik je Szenario (dick=Szenario, duenn=cfg['vergleich_scope']) fuer EINE Metrik -
    siehe Moduldocstring Typ A. Gibt die Liste der erzeugten Dateinamen zurueck."""
    erzeugt = []
    for szenario_key, cfg in szenarien.items():
        dick = _mit_wert_spalte(anzeige_treiber_je_scope[szenario_key], metrik_cfg["spalte"])
        duenn = _mit_wert_spalte(anzeige_treiber_je_scope[cfg["vergleich_scope"]], metrik_cfg["spalte"])
        dateiname = f"treiber_{metrik_key}_{szenario_key}_vs_{cfg['vergleich_scope']}_monat.png"
        titel = (f"{metrik_cfg['titel']} je Anzeigegruppe\n"
                 f"dick={cfg['titel']}, duenn={cfg['vergleich_titel']}")
        if plotte_kombinierte_grafik(dick, duenn, dateiname, titel, metrik_cfg["y_label"],
                                      hauptfokus_label=cfg["titel"],
                                      vergleichs_label=cfg["vergleich_titel"],
                                      pfad_plots=PFAD_PLOTS,
                                      gruppen_liste=ANZEIGE_GRUPPEN_AKTIV,
                                      gruppen_spalte="anzeige_gruppe"):
            erzeugt.append(dateiname)
    return erzeugt


# =========================================================
# SCHRITT 3: Plot Typ B (je Anzeigegruppe, eine Linie je Szenario) - je Metrik
# =========================================================

def baue_medientyp_dataframe(anzeige_treiber_je_scope, szenario_reihenfolge, szenarien,
                              anzeige_gruppe, metrik_spalte):
    """Ein DataFrame [SPALTE_PERIODE, 'wert', 'szenario'] fuer EINE Anzeigegruppe x EINE Metrik,
    ueber alle Szenarien aus szenario_reihenfolge hinweg (analog 8g, hier je Metrik aufgerufen)."""
    teile = []
    for szenario_key in szenario_reihenfolge:
        df = anzeige_treiber_je_scope[szenario_key]
        teil = df[df["anzeige_gruppe"] == anzeige_gruppe][[SPALTE_PERIODE, metrik_spalte]].copy()
        teil = teil.rename(columns={metrik_spalte: "wert"})
        teil["szenario"] = szenarien[szenario_key]["titel"]
        teile.append(teil)
    spalten = [SPALTE_PERIODE, "wert", "szenario"]
    return pd.concat(teile, ignore_index=True)[spalten] if teile else pd.DataFrame(columns=spalten)


def plotte_typ_b(anzeige_treiber_je_scope, szenarien, metrik_key, metrik_cfg):
    """Eine Grafik je aktive Anzeigegruppe (ANZEIGE_GRUPPEN_AKTIV) x Metrik, eine Linie je
    Szenario, ohne Dick/Duenn-Vergleich - siehe Moduldocstring Typ B. Gibt die Liste der
    erzeugten Dateinamen zurueck."""
    szenario_reihenfolge = list(szenarien.keys())
    szenario_titel_reihenfolge = [szenarien[k]["titel"] for k in szenario_reihenfolge]

    erzeugt = []
    for anzeige_gruppe in ANZEIGE_GRUPPEN_AKTIV:
        df_gruppe = baue_medientyp_dataframe(anzeige_treiber_je_scope, szenario_reihenfolge,
                                              szenarien, anzeige_gruppe, metrik_cfg["spalte"])
        dateiname = f"treiber_{metrik_key}_medientyp_{_slug(anzeige_gruppe)}_alle_themen_monat.png"
        titel = (f"{metrik_cfg['titel']} von {anzeige_gruppe} je Thema\n"
                 "(dieselben Szenarien wie marktanteil_themen_plots.py, eine Linie je Thema)")
        if plotte_kombination(df_gruppe, dateiname, titel, metrik_cfg["y_label"],
                               gruppen_liste=szenario_titel_reihenfolge,
                               gruppen_spalte="szenario", pfad_plots=PFAD_PLOTS):
            erzeugt.append(dateiname)
    return erzeugt


# =========================================================
# SCHRITT 4: CSV + Methodik-Uebersichtsdatei
# =========================================================

def schreibe_csv(anzeige_treiber_je_scope, szenarien):
    """Schreibt marktanteil_themen_treiber_monat.csv - eine Zeile je Szenario (nur die
    len(szenarien) Themen-/Politik-Szenarien, NICHT SCOPE_ALLE_VIDEOS, analog 8g) x Periode x
    Anzeigegruppe, mit beiden rohen Metriken (n_videos, views_pro_video) plus views_summe zur
    Nachvollziehbarkeit."""
    teile = []
    for szenario_key, cfg in szenarien.items():
        df = anzeige_treiber_je_scope[szenario_key].copy()
        df["szenario"] = szenario_key
        df["szenario_titel"] = cfg["titel"]
        teile.append(df)
    tabelle = pd.concat(teile, ignore_index=True)
    tabelle = tabelle[["szenario", "szenario_titel", SPALTE_PERIODE, "anzeige_gruppe",
                        "n_videos", "views_pro_video", "views_summe"]]

    PFAD_CSV.parent.mkdir(parents=True, exist_ok=True)
    tabelle.to_csv(PFAD_CSV, index=False)
    print(f"[CSV] {PFAD_CSV} ({len(tabelle)} Zeilen)")


def schreibe_methodik(erzeugt_je_metrik, n_videos_je_scope, szenarien):
    """Schreibt marktanteil_themen_treiber_methodik.md - Pflichtdokumentation fuer
    Vergleichsanalysen (siehe document-comparative-analysis-methodology)."""
    gesamt_erzeugt = sum(len(v) for v in erzeugt_je_metrik.values())
    zeilen = [
        "# Methodik: Treiber des Marktanteils (Anzahl Videos x Views/Video), monatlich",
        "",
        "Diese Datei dokumentiert `marktanteil_themen_treiber_plots.py` - siehe Moduldocstring "
        "fuer die vollstaendige Herleitung. Zerlegungs-Erweiterung von "
        "`marktanteil_themen_plots.py` (Schritt 8g): derselbe Marktanteil laesst sich exakt in "
        "zwei rohe Treiber zerlegen.",
        "",
        "## Formel",
        "",
        "```",
        "views_summe(g) = n_videos(g) x views_pro_video(g)",
        "Marktanteil(g)% [8g] = views_summe(g) / views_summe(ALLE 5 rohen Gruppe5-Kategorien) * 100",
        "```",
        "",
        "`views_pro_video(g)` wird nach dem Kombinieren roher Gruppe5-Kategorien zu einer "
        "Anzeigegruppe NEU aus der summierten views_summe/n_videos berechnet, nicht als Summe/"
        "Mittel der Einzelkategorie-Durchschnitte (siehe `aggregiere_anzeigegruppen_treiber()`).",
        "",
        "**Unterschied zu Schritt 8e** (`frage4_kriegspraemie_marktanteil_phasen_bericht.py`, "
        "Shift-Share-Tabelle `output_anteil x relative_reichweite`): 8e zeigt NORMIERTE Groessen "
        "(Anteil in %, Index relativ zum Periodendurchschnitt) je 5-Phasen-Tabelle. Dieses "
        "Skript zeigt dieselbe Zerlegung als ROHE Werte (Anzahl Videos, durchschnittliche Views "
        "pro Video) UND monatlich statt phasenweise - Nutzerentscheidung nach Rueckfrage, siehe "
        "Moduldocstring.",
        "",
        "## Szenarien und Anzeigegruppen",
        "",
        "1:1 uebernommen aus `marktanteil_themen_plots.py` (echte Importe: THEMEN_AKTIV, "
        "ANZEIGE_GRUPPEN/ANZEIGE_GRUPPEN_AKTIV, baue_szenarien(), filter_fuer_scope()) - siehe "
        "dortige Methodikdatei (`plots_marktanteil_themen/marktanteil_themen_methodik.md`) fuer "
        "die vollstaendige Definition und Video-Anzahlen je Szenario.",
        "",
    ]
    for szenario_key, cfg in szenarien.items():
        n = n_videos_je_scope[szenario_key]
        zeilen.append(f"- **{szenario_key}** ({cfg['titel']}): {n} Videos, Vergleichs-Szenario "
                       f"'{cfg['vergleich_scope']}' ({cfg['vergleich_titel']}, "
                       f"{n_videos_je_scope[cfg['vergleich_scope']]} Videos).")
    zeilen.extend([
        "",
        "## Grafik-Typen (je der beiden Metriken 'Anzahl Videos' und "
        "'Durchschnittliche Views pro Video')",
        "",
        "- **Typ A** (dick/duenn je Szenario): dick = Metrik-Wert INNERHALB des Szenarios, "
        "duenn = Metrik-Wert im Vergleichs-Szenario. Bei der Metrik 'Anzahl Videos' ist die "
        "duenne Linie i.d.R. HOEHER als die dicke (die Vergleichsbasis ist eine echte Obermenge, "
        "kein Anteil/Verhaeltnis wie beim Marktanteil in 8g) - die Grafik zeigt absolute "
        "Ausstoss-Niveaus.",
        "- **Typ B** (je Anzeigegruppe ueber alle Szenarien): eine Linie je Szenario, NUR fuer "
        "eine einzelne Anzeigegruppe, ohne Dick/Duenn-Vergleich.",
        "",
        f"Mindestbesetzung `MIN_VIDEOS_GESAMT_PRO_PERIODE={MIN_VIDEOS_GESAMT_PRO_PERIODE}` "
        "(echter Import aus 8g, identisch zu 8d/8g - wirkt auf die GESAMTE Periode ueber alle 5 "
        "rohen Gruppe5-Kategorien).",
        "",
        f"## Erzeugte Grafiken bei diesem Lauf: {gesamt_erzeugt}",
        "",
    ])
    for metrik_key, metrik_cfg in METRIKEN.items():
        zeilen.append(f"### {metrik_cfg['titel']} ({len(erzeugt_je_metrik[metrik_key])} Grafiken)")
        zeilen.append("")
        for d in erzeugt_je_metrik[metrik_key]:
            zeilen.append(f"- `{d}`")
        zeilen.append("")

    PFAD_PLOTS.mkdir(parents=True, exist_ok=True)
    with open(PFAD_METHODIK, "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen) + "\n")
    print(f"[Methodik] {PFAD_METHODIK}")


# =========================================================
# MAIN
# =========================================================

def main():
    szenarien = baue_szenarien()

    basisdaten = lade_basisdaten()
    basisdaten = ergaenze_themen_flags(basisdaten, THEMEN_AKTIV)

    alle_scopes = list(szenarien.keys()) + [SCOPE_ALLE_VIDEOS]
    anzeige_treiber_je_scope = {}
    n_videos_je_scope = {}
    for scope in alle_scopes:
        rohdaten, n = berechne_szenario_rohdaten(basisdaten, scope)
        anzeige_treiber_je_scope[scope] = aggregiere_anzeigegruppen_treiber(rohdaten)
        n_videos_je_scope[scope] = n
        print(f"[Szenario={scope}] {n} Videos.")

    erzeugt_je_metrik = {}
    for metrik_key, metrik_cfg in METRIKEN.items():
        erzeugt_a = plotte_typ_a(anzeige_treiber_je_scope, szenarien, metrik_key, metrik_cfg)
        erzeugt_b = plotte_typ_b(anzeige_treiber_je_scope, szenarien, metrik_key, metrik_cfg)
        erzeugt_je_metrik[metrik_key] = erzeugt_a + erzeugt_b
        print(f"[Metrik={metrik_key}] {len(erzeugt_a)} von {len(szenarien)} moeglichen "
              f"Typ-A-Grafiken, {len(erzeugt_b)} von {len(ANZEIGE_GRUPPEN_AKTIV)} moeglichen "
              f"Typ-B-Grafiken.")

    gesamt = sum(len(v) for v in erzeugt_je_metrik.values())
    print(f"\n[Fertig] {gesamt} Grafiken insgesamt -> {PFAD_PLOTS}")

    schreibe_csv(anzeige_treiber_je_scope, szenarien)
    schreibe_methodik(erzeugt_je_metrik, n_videos_je_scope, szenarien)


if __name__ == "__main__":
    main()

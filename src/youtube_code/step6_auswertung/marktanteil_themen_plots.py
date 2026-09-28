# -*- coding: utf-8 -*-
"""
marktanteil_themen_plots.py

Erweiterung von `frage4_kriegspraemie_marktanteil_plots.py` (Schritt 8d) auf mehrere Themen -
Nutzervorgabe 2026-09-10: "Ich moechte, dass die anderen Themen auch eingearbeitet werden, nicht
nur Russland/Ukraine. Ich moechte fuer jedes einzelne Thema und fuer alle politischen Videos
(diesmal wieder nicht-exklusiv, also auch Videos, die in den Themen sind) einen Verlauf
dargestellt haben. Ich moechte im CONFIG Block einstellen koennen, welche Medientypen, welche
Themen und ggf. kombinierte Typen (z.B. OERR und Traditionelle als Summe) dargestellt werden."
Eigenes Skript statt Umbau von Schritt 8d (Nutzervorgabe) - 8d bleibt unveraendert als
spezifische Antwort auf die TODO-1-Zusatzfrage (nur Kriegsvideos vs. andere politische Videos,
disjunkt) erhalten, dieses Skript deckt die breitere Themen-Uebersicht ab (Aufgaben.md TODO 2:
"Marktanteile der Gruppen monatsweise... fuer eine feinere Uebersicht").

Themen: die fuenf per Keyword-Screening klassifizierten Themen aus
`step3_topic_relevance/topic_keywords.TOPIC_KEYWORDS` (`video_topic_relevance`-Tabelle in
`data/store/video_registry.sqlite`, siehe `.claude/plans/new_topics.md`) - russia_ukraine_war,
corona_pandemic, migration, economy_general, energy. "Alle politischen Videos" ist KEIN
video_topic_relevance-Thema, sondern die breite `topic_categories='Politics'`-Klassifikation
(`video_registry.is_politics_topic()`/`politics_topic_lookup()`, wie
`frage4_kriegspraemie_relative_views_plots.py`) und ANDERS als in Schritt 8d/8e (dort seit
2026-09-10 EXKLUSIV zu Kriegsvideos) hier bewusst NICHT-EXKLUSIV - ein Kriegs-/Corona-/.../Video
ist i.d.R. AUCH in "alle politischen Videos" enthalten (Nutzervorgabe fuer dieses Skript, siehe
Moduldocstring-Zitat oben).

Marktanteils-Formel je Zelle (Anzeigegruppe x rel_monat x Szenario), IDENTISCH zu Schritt 8d
(`berechne_marktanteile()`/`pruefe_summe_100()` dort als echter Import wiederverwendet, kein
Duplikat):

    anteil = sum(view_count | Gruppe, Szenario, Periode) / sum(view_count | ALLE 5 rohen
             Gruppe5-Kategorien, Szenario, Periode) * 100

Der Nenner bleibt IMMER die Summe ueber alle 5 ROHEN Gruppe5-Kategorien (OERR, Traditionelles
Medium, Alternative Medien links/mitte/rechts) - unabhaengig davon, welche/wie viele
ANZEIGE_GRUPPEN (siehe CONFIG) tatsaechlich als Linien gezeigt werden. Eine Anzeigegruppe, die
mehrere rohe Gruppe5-Kategorien kombiniert (z.B. "OERR + Traditionell", Nutzerbeispiel), ist die
SUMME der Einzelanteile ihrer rohen Kategorien (korrekt, da Anteile am selben festen Nenner -
siehe aggregiere_anzeigegruppen()).

Zwei Grafik-Typen (Nutzervorgabe nach Rueckfrage zur Liniendichte - siehe Chatverlauf: "18 Linien
[5 Anzeigegruppen x 6 Szenarien in einer Grafik] waeren zu unuebersichtlich"):

  Typ A ("je Szenario", eine Grafik je Thema + eine fuer "alle politischen Videos" = 1 +
  len(THEMEN_AKTIV) Grafiken): dick/duenn-Overlay wie Schritt 8d, aber pro Szenario statt nur
  fuer Kriegsvideos, UND mit ANZEIGE_GRUPPEN_AKTIV statt der festen Gruppe5-Reihenfolge als
  Linien - dick = Marktanteil der Anzeigegruppen INNERHALB des Szenarios (z.B. nur
  Coronavideos), duenn = Marktanteil derselben Anzeigegruppen bei "alle politischen Videos" als
  gemeinsame Vergleichsbasis fuer alle Themen-Grafiken. Die Grafik fuer "alle politischen Videos"
  selbst nimmt als duennen Vergleich "alle Videos" (kein Filter) - dieselbe genestete Logik wie
  die drei Umfaenge in `frage4_kriegspraemie_marktanteil_phasen_bericht.py`
  (Thema < alle politischen Videos < alle Videos), hier aber themenspezifisch statt nur fuer
  Kriegsvideos. Wiederverwendet `plotte_kombinierte_grafik()` aus `frage2_sensitivitaet_plots.py`
  - seit 2026-09-10 mit optionalen `gruppen_liste`/`gruppen_spalte`-Parametern (Default weiterhin
  GRUPPE5_REIHENFOLGE/"gruppe5", bestehende Aufrufe unveraendert), hier mit
  ANZEIGE_GRUPPEN_AKTIV/"anzeige_gruppe" aufgerufen - echter Import, kein Duplikat.

  Typ B ("je Anzeigegruppe ueber alle Themen", eine Grafik je aktive Anzeigegruppe): eine Linie
  je Szenario (Themen + "alle politischen Videos"), NUR fuer eine einzelne Anzeigegruppe -
  direkte Antwort auf die konkrete Nutzer-Rueckfrage ("fuer jeden Medientypen eine Grafik, in dem
  alle Themen nur fuer diesen Typen dargestellt sind"), OHNE Dick/Duenn-Vergleich (eine
  Anzeigegruppe braucht keinen Vergleichswert in derselben Grafik). Wiederverwendet
  `plotte_kombination()` aus `frage2_sensitivitaet_plots.py` - seit 2026-09-10 ebenfalls mit
  optionalen `gruppen_liste`/`gruppen_spalte`/`pfad_plots`-Parametern, hier mit den
  Szenario-Anzeigetiteln als "Linien" aufgerufen.

Mindestbesetzung: MIN_VIDEOS_GESAMT_PRO_PERIODE (identisch zu Schritt 8d, wirkt auf die GESAMTE
Periode ueber alle 5 rohen Gruppe5-Kategorien, nicht auf einzelne Anzeigegruppen - siehe
`berechne_marktanteile()`-Docstring in Schritt 8d) - eine Themen-Periode kann deutlich weniger
Videos haben als "alle politischen Videos"/"alle Videos" (v.a. bei schmal geschnittenen Themen
wie Energie), einzelne Punkte einer duennen Themen-Linie koennen dadurch fehlen.

Datenquelle: `lade_basisdaten()` aus `frage4_kriegspraemie_relative_views_plots.py` (echter
Import, Video-Ebene, bereits Whitelist-gefiltert, inkl. gruppe5/ist_kriegsvideo/
ist_politics_topic) ERGAENZT um die vier weiteren Themen-Flags (`ergaenze_themen_flags()`), aus
`video_registry.get_topic_relevance()` (`is_relevant=1` je Thema, video_ids-gefiltert auf die
Whitelist - dasselbe Muster wie `prepare_success_metrics.py::_ergaenze_kriegsvideo_flag()` fuer
russia_ukraine_war, ungefiltert wie ist_kriegsvideo, kein zusaetzlicher politics_final-/
topic_categories-Filter auf den Zaehler, konsistent mit Schritt 8c/8d).

Schreibt je Grafik-Typ die PNGs, EINE gemeinsame CSV (`marktanteil_themen_monat.csv`, Zeilen =
Szenario x Periode x Anzeigegruppe, dieselben Werte wie in den Typ-A-"dick"-Linien) und eine
Methodik-Uebersichtsdatei (`marktanteil_themen_methodik.md`) nach
`outputs/segment_analysis/plots_marktanteil_themen/`.

Laeuft direkt als Skript (sibling-Importe wie die anderen step6_auswertung-Dateien, kein -m):

    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe marktanteil_themen_plots.py

(im Ordner src/youtube_code/step6_auswertung/ ausgefuehrt).
"""

import re

import pandas as pd

from youtube_code.config import OUTPUTS
from youtube_code.store.video_registry import get_topic_relevance
from frage2_sensitivitaet_plots import plotte_kombinierte_grafik, plotte_kombination
from frage4_kriegspraemie_relative_views_plots import lade_basisdaten, SPALTE_PERIODE
from frage4_kriegspraemie_marktanteil_plots import berechne_marktanteile, pruefe_summe_100

# =========================================================
# CONFIG
# =========================================================

# --- Anzeigegruppen: welche Medientyp(en)/Kombinationen als eigene Linie(n) gezeigt werden. ---
# Name -> Liste roher gruppe5-Kategorien (GRUPPE5_REIHENFOLGE), die zu dieser Linie summiert
# werden (siehe aggregiere_anzeigegruppen() - der Nenner bleibt IMMER die Summe ueber ALLE 5
# rohen Kategorien, unabhaengig von dieser Config). Beispiel fuer einen kombinierten Typ
# (Nutzerbeispiel): "OERR + Traditionell": ["ÖRR", "Traditionelles Medium"].
ANZEIGE_GRUPPEN = {
    "ÖRR": ["ÖRR"],
    "Traditionelles Medium": ["Traditionelles Medium"],
    "Alternative Medien (links)": ["Alternative Medien (links)"],
    "Alternative Medien (mitte)": ["Alternative Medien (mitte)"],
    "Alternative Medien (rechts)": ["Alternative Medien (rechts)"],
}
# Teilmenge von ANZEIGE_GRUPPEN.keys(), die tatsaechlich als Linien gezeichnet wird (Reihenfolge
# bestimmt Legenden-/Farbreihenfolge in beiden Grafik-Typen) UND wofuer Typ B eine eigene Grafik
# bekommt - Stellschraube, um z.B. nur 3 statt 5 Anzeigegruppen zu zeigen.
ANZEIGE_GRUPPEN_AKTIV = list(ANZEIGE_GRUPPEN.keys())

# --- Themen aus video_topic_relevance (step3_topic_relevance/topic_keywords.TOPIC_KEYWORDS). ---
# Themenschluessel -> Anzeigetitel.
THEMEN = {
    "russia_ukraine_war": "Ukraine-Krieg",
    "corona_pandemic": "Corona/Pandemie",
    "migration": "Migration",
    "economy_general": "Wirtschaft (allgemein)",
    "energy": "Energie",
}
# Teilmenge von THEMEN.keys(), die tatsaechlich geplottet wird (Reihenfolge bestimmt die
# Legenden-/Farbreihenfolge in Typ B) - Stellschraube, um z.B. nur den Kriegskontext zu zeigen.
THEMEN_AKTIV = list(THEMEN.keys())

# "Alle politischen Videos" ist kein video_topic_relevance-Thema, sondern topic_categories=
# "Politics" (siehe Moduldocstring) - NICHT exklusiv zu den Themen oben (anders als Schritt 8d).
SCOPE_ALLE_POLITIK = "alle_politische_videos"
SCOPE_ALLE_POLITIK_TITEL = "Alle politischen Videos (topic_categories='Politics', nicht-exklusiv)"
# Nur als duenne Vergleichslinie fuer die SCOPE_ALLE_POLITIK-Grafik in Typ A verwendet (kein
# eigenes Thema, taucht in Typ B nicht als Linie auf - siehe Moduldocstring).
SCOPE_ALLE_VIDEOS = "alle_videos"
SCOPE_ALLE_VIDEOS_TITEL = "Alle Videos (keine Themen-/Politik-Einschraenkung)"

# Bereits in channel_video_erfolg.csv vorhanden (prepare_success_metrics.py, aus
# video_registry.get_topic_relevance(topic="russia_ukraine_war")) - fuer die anderen vier Themen
# ergaenzt ergaenze_themen_flags() je eine eigene 0/1-Spalte, ebenfalls aus get_topic_relevance().
THEMA_SPALTE = {
    "russia_ukraine_war": "ist_kriegsvideo",
    "corona_pandemic": "ist_thema_corona_pandemic",
    "migration": "ist_thema_migration",
    "economy_general": "ist_thema_economy_general",
    "energy": "ist_thema_energy",
}

# Mindestbesetzung je (Szenario, Periode)-Zelle, GESAMT ueber alle 5 rohen Gruppe5-Kategorien
# (identisch zu Schritt 8d - siehe berechne_marktanteile()-Docstring dort).
MIN_VIDEOS_GESAMT_PRO_PERIODE = 20

PFAD_PLOTS = OUTPUTS / "segment_analysis" / "plots_marktanteil_themen"
PFAD_CSV = PFAD_PLOTS / "marktanteil_themen_monat.csv"
PFAD_METHODIK = PFAD_PLOTS / "marktanteil_themen_methodik.md"


# =========================================================
# SCHRITT 1: Basisdaten + Themen-Flags
# =========================================================

def ergaenze_themen_flags(df, themen):
    """Ergaenzt fuer jedes Thema in `themen`, das noch keine Spalte in THEMA_SPALTE hat bzw.
    dessen Spalte noch nicht in df steckt (nur russia_ukraine_war ist bereits als
    ist_kriegsvideo in channel_video_erfolg.csv enthalten, siehe THEMA_SPALTE), eine eigene 0/1-
    Spalte aus video_registry.get_topic_relevance(thema, video_ids=...) (is_relevant=1) - exakt
    dasselbe Muster wie prepare_success_metrics.py::_ergaenze_kriegsvideo_flag() fuer
    russia_ukraine_war, hier auf die anderen vier Themen angewendet: ungefiltert (keine
    zusaetzliche politics_final-/topic_categories-Einschraenkung auf den Zaehler, konsistent mit
    Schritt 8c/8d), video_ids-Filter auf df (Whitelist) statt der vollen video_topic_relevance-
    Tabelle (~519k Zeilen je Thema)."""
    df = df.copy()
    for thema in themen:
        spalte = THEMA_SPALTE[thema]
        if spalte in df.columns:
            continue
        relevanz = get_topic_relevance(topic=thema, video_ids=df["video_id"].tolist())
        relevante_ids = set(relevanz.loc[relevanz["is_relevant"] == 1, "video_id"])
        df[spalte] = df["video_id"].isin(relevante_ids).astype(int)
        print(f"[Thema={thema}] {int(df[spalte].sum())} von {len(df)} Videos relevant "
              f"(Spalte {spalte!r}).")
    return df


# =========================================================
# SCHRITT 2: Szenarien (Themen + "alle politischen Videos", je mit Vergleichs-Szenario)
# =========================================================

def baue_szenarien():
    """Liefert {szenario_key: {"titel": ..., "vergleich_scope": ..., "vergleich_titel": ...}} -
    ein Eintrag je aktives Thema (Vergleich = SCOPE_ALLE_POLITIK, siehe Moduldocstring) PLUS
    SCOPE_ALLE_POLITIK selbst (Vergleich = SCOPE_ALLE_VIDEOS)."""
    szenarien = {
        thema: {"titel": THEMEN[thema], "vergleich_scope": SCOPE_ALLE_POLITIK,
                "vergleich_titel": SCOPE_ALLE_POLITIK_TITEL}
        for thema in THEMEN_AKTIV
    }
    szenarien[SCOPE_ALLE_POLITIK] = {"titel": SCOPE_ALLE_POLITIK_TITEL,
                                      "vergleich_scope": SCOPE_ALLE_VIDEOS,
                                      "vergleich_titel": SCOPE_ALLE_VIDEOS_TITEL}
    return szenarien


def filter_fuer_scope(df, scope):
    """Filtert basisdaten auf den Video-Ausschnitt eines Szenarios/einer Vergleichsbasis -
    scope ist entweder ein Themenschluessel aus THEMA_SPALTE, SCOPE_ALLE_POLITIK
    (ist_politics_topic == True, siehe Moduldocstring) oder SCOPE_ALLE_VIDEOS (kein Filter)."""
    if scope == SCOPE_ALLE_VIDEOS:
        return df
    if scope == SCOPE_ALLE_POLITIK:
        return df[df["ist_politics_topic"] == True]
    return df[df[THEMA_SPALTE[scope]] == 1]


# =========================================================
# SCHRITT 3: Marktanteile je Szenario + Aggregation zu Anzeigegruppen
# =========================================================

def berechne_szenario_anteile(basisdaten, scope):
    """Rohe Gruppe5-Marktanteile (berechne_marktanteile()/pruefe_summe_100(), echte Importe aus
    frage4_kriegspraemie_marktanteil_plots.py - Schritt 8d, kein Duplikat) fuer den
    Video-Ausschnitt von `scope`. Gibt (anteile_roh, n_videos) zurueck."""
    umfang_df = filter_fuer_scope(basisdaten, scope)
    anteile_roh = berechne_marktanteile(umfang_df, MIN_VIDEOS_GESAMT_PRO_PERIODE)
    pruefe_summe_100(anteile_roh, scope)
    return anteile_roh, len(umfang_df)


def aggregiere_anzeigegruppen(anteile_roh):
    """Fasst die rohen Gruppe5-Anteile (Nenner bleibt IMMER die Summe ueber alle 5 rohen
    Kategorien, siehe berechne_marktanteile()) zu den in ANZEIGE_GRUPPEN_AKTIV konfigurierten
    Linien zusammen - eine kombinierte Anzeigegruppe ist die SUMME der Anteile ihrer rohen
    gruppe5-Kategorien (korrekt, da Anteile am selben festen Nenner, siehe Moduldocstring)."""
    teile = []
    for name in ANZEIGE_GRUPPEN_AKTIV:
        rohe_gruppen = ANZEIGE_GRUPPEN[name]
        teil = anteile_roh[anteile_roh["gruppe5"].isin(rohe_gruppen)]
        if teil.empty:
            continue
        agg = teil.groupby(SPALTE_PERIODE, as_index=False).agg(
            wert=("wert", "sum"), views_summe=("views_summe", "sum"),
            n_videos=("n_videos", "sum"))
        agg["anzeige_gruppe"] = name
        teile.append(agg)
    spalten = [SPALTE_PERIODE, "anzeige_gruppe", "wert", "views_summe", "n_videos"]
    return pd.concat(teile, ignore_index=True)[spalten] if teile else pd.DataFrame(columns=spalten)


# =========================================================
# SCHRITT 4: Plot Typ A (je Szenario, dick/duenn ueber Anzeigegruppen)
# =========================================================

def _slug(text):
    """Dateiname-taugliches Kuerzel (Kleinbuchstaben, nur [a-z0-9_]) - fuer Typ-B-Dateinamen aus
    frei konfigurierbaren ANZEIGE_GRUPPEN-Namen (z.B. "OERR + Traditionell")."""
    text = text.lower().replace("ö", "oe").replace("ä", "ae").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def plotte_typ_a(anzeige_anteile_je_scope, szenarien):
    """Eine Grafik je Szenario (dick=Szenario, duenn=cfg['vergleich_scope'], je Anzeigegruppe
    dieselbe Farbe) - siehe Moduldocstring Typ A. Gibt die Liste der erzeugten Dateinamen
    zurueck."""
    erzeugt = []
    for szenario_key, cfg in szenarien.items():
        dick = anzeige_anteile_je_scope[szenario_key]
        duenn = anzeige_anteile_je_scope[cfg["vergleich_scope"]]
        dateiname = f"marktanteil_{szenario_key}_vs_{cfg['vergleich_scope']}_monat.png"
        titel = (f"Marktanteil an der Reichweite je Anzeigegruppe\n"
                 f"dick={cfg['titel']}, duenn={cfg['vergleich_titel']}")
        if plotte_kombinierte_grafik(dick, duenn, dateiname, titel, "Marktanteil an Views (%)",
                                      hauptfokus_label=cfg["titel"],
                                      vergleichs_label=cfg["vergleich_titel"],
                                      pfad_plots=PFAD_PLOTS,
                                      gruppen_liste=ANZEIGE_GRUPPEN_AKTIV,
                                      gruppen_spalte="anzeige_gruppe"):
            erzeugt.append(dateiname)
    return erzeugt


# =========================================================
# SCHRITT 5: Plot Typ B (je Anzeigegruppe, eine Linie je Szenario)
# =========================================================

def baue_medientyp_dataframe(anzeige_anteile_je_scope, szenario_reihenfolge, szenarien,
                              anzeige_gruppe):
    """Ein DataFrame [SPALTE_PERIODE, 'wert', 'szenario'] fuer EINE Anzeigegruppe, ueber alle
    Szenarien aus szenario_reihenfolge hinweg (dick-Seite aus Typ A, 'szenario' traegt den
    Anzeigetitel statt des internen Schluessels - direkt als Legendenbeschriftung nutzbar)."""
    teile = []
    for szenario_key in szenario_reihenfolge:
        df = anzeige_anteile_je_scope[szenario_key]
        teil = df[df["anzeige_gruppe"] == anzeige_gruppe][[SPALTE_PERIODE, "wert"]].copy()
        teil["szenario"] = szenarien[szenario_key]["titel"]
        teile.append(teil)
    spalten = [SPALTE_PERIODE, "wert", "szenario"]
    return pd.concat(teile, ignore_index=True)[spalten] if teile else pd.DataFrame(columns=spalten)


def plotte_typ_b(anzeige_anteile_je_scope, szenarien):
    """Eine Grafik je aktive Anzeigegruppe (ANZEIGE_GRUPPEN_AKTIV), eine Linie je Szenario
    (Themen + 'alle politischen Videos', OHNE Dick/Duenn-Vergleich) - siehe Moduldocstring Typ B.
    Gibt die Liste der erzeugten Dateinamen zurueck."""
    szenario_reihenfolge = list(szenarien.keys())
    szenario_titel_reihenfolge = [szenarien[k]["titel"] for k in szenario_reihenfolge]

    erzeugt = []
    for anzeige_gruppe in ANZEIGE_GRUPPEN_AKTIV:
        df_gruppe = baue_medientyp_dataframe(anzeige_anteile_je_scope, szenario_reihenfolge,
                                              szenarien, anzeige_gruppe)
        dateiname = f"marktanteil_medientyp_{_slug(anzeige_gruppe)}_alle_themen_monat.png"
        titel = (f"Marktanteil von {anzeige_gruppe} je Thema\n"
                 "(dieselbe Marktanteils-Formel wie oben, eine Linie je Thema/Szenario)")
        if plotte_kombination(df_gruppe, dateiname, titel, "Marktanteil an Views (%)",
                               gruppen_liste=szenario_titel_reihenfolge,
                               gruppen_spalte="szenario", pfad_plots=PFAD_PLOTS):
            erzeugt.append(dateiname)
    return erzeugt


# =========================================================
# SCHRITT 6: CSV + Methodik-Uebersichtsdatei
# =========================================================

def schreibe_csv(anzeige_anteile_je_scope, szenarien):
    """Schreibt marktanteil_themen_monat.csv - eine Zeile je Szenario (nur die len(szenarien)
    Themen-/Politik-Szenarien, NICHT SCOPE_ALLE_VIDEOS, das nur intern als Vergleichsbasis fuer
    die SCOPE_ALLE_POLITIK-Grafik dient) x Periode x Anzeigegruppe - dieselben Werte wie in den
    Typ-A-'dick'-Linien."""
    teile = []
    for szenario_key, cfg in szenarien.items():
        df = anzeige_anteile_je_scope[szenario_key].copy()
        df["szenario"] = szenario_key
        df["szenario_titel"] = cfg["titel"]
        teile.append(df)
    tabelle = pd.concat(teile, ignore_index=True)
    tabelle = tabelle[["szenario", "szenario_titel", SPALTE_PERIODE, "anzeige_gruppe", "wert",
                        "views_summe", "n_videos"]]

    PFAD_CSV.parent.mkdir(parents=True, exist_ok=True)
    tabelle.to_csv(PFAD_CSV, index=False)
    print(f"[CSV] {PFAD_CSV} ({len(tabelle)} Zeilen)")


def schreibe_methodik(erzeugt_a, erzeugt_b, n_videos_je_scope, szenarien):
    """Schreibt marktanteil_themen_methodik.md - Pflichtdokumentation fuer Vergleichsanalysen
    (siehe document-comparative-analysis-methodology)."""
    zeilen = [
        "# Methodik: Marktanteil je Anzeigegruppe, ueber mehrere Themen",
        "",
        "Diese Datei dokumentiert `marktanteil_themen_plots.py` - siehe Moduldocstring fuer die "
        "vollstaendige Herleitung. Erweiterung von `frage4_kriegspraemie_marktanteil_plots.py` "
        "(Schritt 8d) auf alle fuenf klassifizierten Themen (nicht nur Ukraine-Krieg) UND eine "
        "nicht-exklusive 'alle politischen Videos'-Ansicht.",
        "",
        "## Anteils-Formel",
        "",
        "Je Zelle (Anzeigegruppe x Periode x Szenario), Nenner IMMER die Summe ueber alle 5 "
        "rohen Gruppe5-Kategorien (unabhaengig von ANZEIGE_GRUPPEN_AKTIV):",
        "",
        "```",
        "anteil = sum(view_count | Gruppe, Szenario, Periode) / "
        "sum(view_count | ALLE 5 rohen Gruppe5-Kategorien, Szenario, Periode) * 100",
        "```",
        "",
        "## Anzeigegruppen",
        "",
        f"Aktiv: {', '.join(ANZEIGE_GRUPPEN_AKTIV)}. Definition (Name -> rohe Gruppe5-"
        f"Kategorien, die summiert werden): `{ANZEIGE_GRUPPEN}`.",
        "",
        "## Szenarien",
        "",
        "Fuenf Themen aus `video_topic_relevance` (ungefiltert, keine politics_final-/"
        "topic_categories-Einschraenkung auf den Zaehler) PLUS 'alle politischen Videos' "
        "(`topic_categories='Politics'`, NICHT-EXKLUSIV zu den Themen - ein Kriegsvideo z.B. "
        "ist i.d.R. AUCH darin enthalten, anders als Schritt 8d/8e):",
        "",
    ]
    for szenario_key, cfg in szenarien.items():
        n = n_videos_je_scope[szenario_key]
        zeilen.append(f"- **{szenario_key}** ({cfg['titel']}): {n} Videos, Vergleichs-Szenario "
                       f"'{cfg['vergleich_scope']}' ({cfg['vergleich_titel']}, "
                       f"{n_videos_je_scope[cfg['vergleich_scope']]} Videos).")
    zeilen.extend([
        "",
        "## Grafik-Typen",
        "",
        "- **Typ A** (dick/duenn je Szenario): dick = Marktanteil der Anzeigegruppen INNERHALB "
        "des Szenarios, duenn = Marktanteil derselben Anzeigegruppen im Vergleichs-Szenario "
        "(siehe Tabelle oben) - direkter visueller Vergleich pro Thema.",
        "- **Typ B** (je Anzeigegruppe ueber alle Szenarien): eine Linie je Szenario, NUR fuer "
        "eine einzelne Anzeigegruppe, ohne Dick/Duenn-Vergleich.",
        "",
        f"Mindestbesetzung `MIN_VIDEOS_GESAMT_PRO_PERIODE={MIN_VIDEOS_GESAMT_PRO_PERIODE}` "
        "(wirkt auf die GESAMTE Periode ueber alle 5 rohen Gruppe5-Kategorien, wie Schritt 8d).",
        "",
        f"## Erzeugte Grafiken bei diesem Lauf: {len(erzeugt_a) + len(erzeugt_b)} "
        f"({len(erzeugt_a)} Typ A, {len(erzeugt_b)} Typ B)",
        "",
    ])
    for d in erzeugt_a + erzeugt_b:
        zeilen.append(f"- `{d}`")

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
    anzeige_anteile_je_scope = {}
    n_videos_je_scope = {}
    for scope in alle_scopes:
        anteile_roh, n = berechne_szenario_anteile(basisdaten, scope)
        anzeige_anteile_je_scope[scope] = aggregiere_anzeigegruppen(anteile_roh)
        n_videos_je_scope[scope] = n
        print(f"[Szenario={scope}] {n} Videos.")

    erzeugt_a = plotte_typ_a(anzeige_anteile_je_scope, szenarien)
    erzeugt_b = plotte_typ_b(anzeige_anteile_je_scope, szenarien)
    print(f"\n[Fertig] {len(erzeugt_a)} von {len(szenarien)} moeglichen Typ-A-Grafiken, "
          f"{len(erzeugt_b)} von {len(ANZEIGE_GRUPPEN_AKTIV)} moeglichen Typ-B-Grafiken "
          f"-> {PFAD_PLOTS}")

    schreibe_csv(anzeige_anteile_je_scope, szenarien)
    schreibe_methodik(erzeugt_a, erzeugt_b, n_videos_je_scope, szenarien)


if __name__ == "__main__":
    main()

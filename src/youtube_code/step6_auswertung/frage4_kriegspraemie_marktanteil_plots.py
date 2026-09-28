# -*- coding: utf-8 -*-
"""
frage4_kriegspraemie_marktanteil_plots.py

Antwort auf die Zusatzfrage aus TODO 1 in .claude/Aufgaben.md ("Kriegspraemie": "...Faellt
diese Praemie ggf. hoeher fuer rechte alternative Medien aus? Oder koennen sie hier einen
hoeheren Marktanteil als bei anderen (politischen) Videos erzielen?"). Anders als
frage4_kriegspraemie_medientyp_bericht.py (Regressionskoeffizient je Gruppe - wie stark
schneiden Kriegsvideos INNERHALB der eigenen Kanaele/Gruppe ab) und
frage4_kriegspraemie_relative_views_plots.py (Index: Kriegsvideo-Views vs. Vergleichsgruppen-
Views DERSELBEN Gruppe) misst dieses Skript den ANTEIL, den jede Gruppe5-Kategorie an der
GESAMTEN Reichweite (Summe aller Views) INNERHALB eines Video-Umfangs (Kriegsvideos bzw.
andere politische Videos) hat - eine echte Marktanteils-Kennzahl ueber die Gruppen hinweg,
nicht innerhalb einer Gruppe.

Klassifikation "politisches Video": video_details.topic_categories (Kategorie "Politics",
siehe video_registry.is_politics_topic()/politics_topic_lookup()) statt politics_final aus
screening_state.sqlite - Nutzervorgabe (siehe .claude/plans/
lies-aufgaben-md-in-claude-compressed-cascade.md): politics_final deckt nur ~12% der Videos
ab, topic_categories dagegen ~99% (Whitelist-Diagnose 2026-09-08, siehe Moduldocstring von
frage4_kriegspraemie_relative_views_plots.py). Fuer eine Marktanteils-Kennzahl (Summe ueber
viele Videos einer ganzen Periode) ist die breite Abdeckung wichtiger als die engere
inhaltliche Praezision von politics_final (siehe dortige Limitation-Dokumentation fuer die
Abgrenzung der beiden Klassifikationen) - Kriegsvideos gehen wie ueberall in diesem Ordner
UNGEFILTERT ein (nicht zusaetzlich auf topic_categories="Politics" eingeschraenkt).

Anteil je Zelle (Gruppe5-Kategorie x rel_monat x Umfang):

    anteil = sum(view_count | Gruppe, Umfang, Periode) / sum(view_count | ALLE 5 Gruppen, Umfang, Periode) * 100

Die 5 Gruppe5-Kategorien (OERR, Traditionelles Medium, Alternative Medien links/mitte/rechts,
siehe frage2_sensitivitaet_plots.baue_gruppe5_lokal()) sind die vollstaendige Grundgesamtheit
fuer den Nenner (Politiker/Partei und Alternativmedien ohne Ideologie-Einordnung sind bereits
in lade_basisdaten() rausgefiltert) - die Anteile der 5 Gruppen summieren sich je Zelle
IMMER zu 100% (siehe Sanity-Check in main()), WEIL anders als bei
frage4_kriegspraemie_relative_views_plots.py hier KEINE einzelne Gruppe/Zelle wegen zu
geringer Besetzung rausfaellt - stattdessen wird eine ganze PERIODE (alle 5 Gruppen
gemeinsam) uebersprungen, wenn die Videoanzahl ueber alle 5 Gruppen zusammen unter
MIN_VIDEOS_GESAMT_PRO_PERIODE liegt (siehe berechne_marktanteile()).

Zwei Umfaenge, EIN gemeinsamer Plot (dieselbe Kombinierte-Grafik-Logik wie
frage2_sensitivitaet_plots.py::plotte_kombinierte_grafik(), als echter Import
wiederverwendet - kein Duplikat): dicke Linie = Marktanteil bei Kriegsvideos, duenne Linie =
Marktanteil bei anderen politischen Videos (topic_categories="Politics",
ist_kriegsvideo==0), je Gruppe5-Kategorie in derselben Farbe. Ein Marktanteil bei
Kriegsvideos oberhalb des Marktanteils bei anderen politischen Videos (dicke Linie ueber der
duennen) bedeutet: die Gruppe erreicht bei Kriegsvideos einen hoeheren Marktanteil als bei
anderen politischen Videos - direkte Antwort auf die TODO-1-Zusatzfrage.

Datenquelle: outputs/segment_analysis/channel_video_erfolg.csv (Video-Ebene, bereits
Whitelist-gefiltert) + video_registry.politics_topic_lookup(), gemerged ueber video_id -
identische Basisdaten-Aufbereitung wie frage4_kriegspraemie_relative_views_plots.py, dessen
lade_basisdaten() hier als echter Import wiederverwendet wird (kein Duplikat).

Laeuft direkt als Skript (sibling-Importe wie die anderen step6_auswertung-Dateien, kein -m):

    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe frage4_kriegspraemie_marktanteil_plots.py

(im Ordner src/youtube_code/step6_auswertung/ ausgefuehrt).
"""

from youtube_code.config import OUTPUTS
from frage2_sensitivitaet_plots import plotte_kombinierte_grafik
from frage4_kriegspraemie_relative_views_plots import lade_basisdaten, SPALTE_PERIODE

# =========================================================
# CONFIG
# =========================================================

# Mindestbesetzung je (Umfang, Periode)-Zelle, GESAMT ueber alle 5 Gruppe5-Kategorien
# (nicht je Gruppe - siehe Moduldocstring, damit die Anteile IMMER zu 100% aufsummieren).
MIN_VIDEOS_GESAMT_PRO_PERIODE = 20

PFAD_PLOTS = OUTPUTS / "segment_analysis" / "plots_frage4_kriegspraemie_relative_views"
DATEINAME = "kriegspraemie_marktanteil_kriegsvideos-vs-andere_politische_videos_topic_monat.png"
PFAD_METHODIK = PFAD_PLOTS / "kriegspraemie_marktanteil_methodik.md"


# =========================================================
# SCHRITT 1: Marktanteile berechnen
# =========================================================

def berechne_marktanteile(df, min_videos_gesamt=MIN_VIDEOS_GESAMT_PRO_PERIODE):
    """Gruppiert nach (rel_monat, gruppe5), summiert view_count je Zelle. Der Nenner je
    Periode ist die Summe ueber ALLE 5 Gruppe5-Kategorien in dieser Periode (nicht nur die
    ueberlebenden - die Mindestbesetzung wirkt VOR der Anteilsberechnung auf die ganze
    Periode, siehe Moduldocstring), damit die 5 Anteile sich immer exakt zu 100% aufsummieren.
    Periode faellt komplett raus (alle 5 Gruppen), wenn die Videoanzahl ueber alle Gruppen
    zusammen unter min_videos_gesamt liegt."""
    schluessel = [SPALTE_PERIODE, "gruppe5"]
    zellen = df.groupby(schluessel, as_index=False).agg(
        views_summe=("view_count", "sum"), n_videos=("view_count", "size"))

    periode_summen = zellen.groupby(SPALTE_PERIODE, as_index=False).agg(
        views_gesamt=("views_summe", "sum"), n_videos_gesamt=("n_videos", "sum"))
    vor = periode_summen[SPALTE_PERIODE].nunique()
    periode_summen = periode_summen[periode_summen["n_videos_gesamt"] >= min_videos_gesamt]
    nach = periode_summen[SPALTE_PERIODE].nunique()
    if nach < vor:
        print(f"[Marktanteil] {vor - nach} von {vor} Perioden uebersprungen "
              f"(< {min_videos_gesamt} Videos insgesamt ueber alle 5 Gruppen).")

    zellen = zellen.merge(periode_summen[[SPALTE_PERIODE, "views_gesamt"]],
                           on=SPALTE_PERIODE, how="inner")
    zellen["wert"] = zellen["views_summe"] / zellen["views_gesamt"] * 100
    return zellen


def pruefe_summe_100(werte_df, label):
    """Sanity-Check (siehe Moduldocstring): je Periode muessen sich die 5 Gruppenanteile zu
    100% aufsummieren. Reine Rundungstoleranz (0.01 Prozentpunkte), kein methodischer
    Freiheitsgrad - eine Abweichung darueber hinaus deutet auf einen Bug hin."""
    if werte_df.empty:
        return
    summen = werte_df.groupby(SPALTE_PERIODE)["wert"].sum()
    abweichung = (summen - 100).abs().max()
    if abweichung > 0.01:
        print(f"[Warnung][{label}] Anteile summieren sich in mind. einer Periode NICHT zu "
              f"100% (max. Abweichung {abweichung:.4f} Prozentpunkte) - bitte pruefen.")
    else:
        print(f"[Sanity-Check][{label}] Anteile summieren sich in jeder Periode zu 100% "
              f"(max. Abweichung {abweichung:.4f} Prozentpunkte).")


# =========================================================
# SCHRITT 2: Methodik-Uebersichtsdatei
# =========================================================

def schreibe_methodik(erzeugt, n_krieg, n_politik):
    """Schreibt kriegspraemie_marktanteil_methodik.md - Pflichtdokumentation fuer
    Vergleichsanalysen (siehe document-comparative-analysis-methodology)."""
    zeilen = [
        "# Methodik: Marktanteil je Gruppe5-Kategorie (TODO 1, Zusatzfrage)",
        "",
        "Diese Datei dokumentiert `frage4_kriegspraemie_marktanteil_plots.py` - siehe "
        "Moduldocstring fuer die vollstaendige Herleitung.",
        "",
        "## Anteils-Formel",
        "",
        "Je Zelle (Gruppe5-Kategorie x `rel_monat`), gepoolt auf Video-Ebene:",
        "",
        "```",
        "anteil = sum(view_count | Gruppe, Umfang, Periode) / "
        "sum(view_count | ALLE 5 Gruppen, Umfang, Periode) * 100",
        "```",
        "",
        "Die 5 Anteile summieren sich je Periode und Umfang IMMER zu 100% - die "
        f"Mindestbesetzung (`MIN_VIDEOS_GESAMT_PRO_PERIODE={MIN_VIDEOS_GESAMT_PRO_PERIODE}`) "
        "wirkt auf die GESAMTE Periode (alle 5 Gruppen gemeinsam), nicht auf einzelne Gruppen.",
        "",
        "## Umfaenge",
        "",
        "- **Kriegsvideos**: `ist_kriegsvideo == 1`, ungefiltert (wie ueberall in diesem "
        "Ordner - kein zusaetzlicher topic_categories-Filter auf den Zaehler).",
        "- **andere politische Videos**: `ist_kriegsvideo == 0 UND topic_categories enthaelt "
        "\"Politics\"` (YouTube-eigene automatische Themenkategorisierung, ~99% Abdeckung auf "
        "der Whitelist statt der ~12% von `politics_final` - siehe "
        "`frage4_kriegspraemie_relative_views_plots.py`-Methodik fuer die vollstaendige "
        "Abgrenzung zu `politics_final`).",
        "",
        f"Videos in dieser Auswertung: {n_krieg} Kriegsvideos, {n_politik} andere politische "
        "Videos (nach Mindestbesetzungs-Filter).",
        "",
        f"## Erzeugte Grafiken bei diesem Lauf: {len(erzeugt)}",
        "",
    ]
    for d in erzeugt:
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

    kriegsvideos = basisdaten[basisdaten["ist_kriegsvideo"] == 1]
    andere_politische = basisdaten[(basisdaten["ist_kriegsvideo"] == 0)
                                    & (basisdaten["ist_politics_topic"] == True)]
    print(f"[Umfang] {len(kriegsvideos)} Kriegsvideos, {len(andere_politische)} andere "
          "politische Videos (topic_categories='Politics').")

    anteile_krieg = berechne_marktanteile(kriegsvideos)
    anteile_politik = berechne_marktanteile(andere_politische)
    pruefe_summe_100(anteile_krieg, "Kriegsvideos")
    pruefe_summe_100(anteile_politik, "andere politische Videos")

    titel = ("Marktanteil an der Gesamtreichweite je Gruppe5-Kategorie\n"
             "dick=Kriegsvideos, duenn=andere politische Videos (topic_categories='Politics')")
    erzeugt = []
    if plotte_kombinierte_grafik(anteile_krieg, anteile_politik, DATEINAME, titel,
                                  "Marktanteil an Views (%)",
                                  hauptfokus_label="Kriegsvideos",
                                  vergleichs_label="andere politische Videos",
                                  pfad_plots=PFAD_PLOTS):
        erzeugt.append(DATEINAME)

    print(f"\n[Fertig] {len(erzeugt)} von 1 moeglicher Grafik erzeugt -> {PFAD_PLOTS}")
    schreibe_methodik(erzeugt, len(kriegsvideos), len(andere_politische))


if __name__ == "__main__":
    main()

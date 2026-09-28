# -*- coding: utf-8 -*-
"""
kanaluebersicht_marktanteil_bericht.py

Kanal-Ebenen-Ergaenzung zu `frage4_kriegspraemie_marktanteil_plots.py` (Schritt 8d) und
`frage4_kriegspraemie_marktanteil_phasen_bericht.py` (Schritt 8e) - ausgeloest durch die
Nutzerfrage beim Betrachten der dortigen Grafik
(`plots_frage4_kriegspraemie_relative_views/kriegspraemie_marktanteil_kriegsvideos-vs-
andere_politische_videos_topic_monat.png`): "In der Vorkriegsperiode sieht man einen starken
Anstieg der traditionellen Medien und einen starken Abschwung der rechten Alternativen. Ich
moechte wissen, ob das von ein paar grossen Kanaelen getrieben wird." Zerlegt den dort auf
Gruppe5-Ebene berichteten Marktanteil auf Kanalebene, damit sichtbar wird, ob wenige grosse
Kanaele einen Gruppentrend treiben.

Zwei Kennzahlen je Kanal x Periode x Umfang (dieselben drei Umfaenge - "kriegsvideos",
"andere_politische_videos" (schliesst Kriegsvideos EXPLIZIT aus), "alle_videos" - echter Import
aus `frage4_kriegspraemie_marktanteil_phasen_bericht.UMFAENGE`, keine Neudefinition):

    anteil_am_markt_pct  = sum(views | Kanal) / sum(views | ALLE 5 Gruppen) * 100
        Kanal-Zerlegung des bereits in Schritt 8d/8e berichteten Gruppen-Marktanteils - die
        anteil_am_markt_pct-Werte aller Kanaele EINER Gruppe summieren sich exakt zum
        Gruppen-Marktanteil aus Schritt 8e (`frage4_kriegspraemie_marktanteil_phasen_bericht.
        csv::anteil_pct`, Toleranz reine Gleitkommarundung).
    anteil_an_gruppe_pct = sum(views | Kanal) / sum(views | eigene Gruppe5) * 100
        Konzentration INNERHALB der Gruppe - die eigentliche Antwort auf die Nutzerfrage: liegt
        der Wert bei 1-2 Kanaelen nahe 100%, dominieren diese die Gruppe und ein Gruppentrend
        kann allein von deren individueller Entwicklung getrieben sein statt von einer
        breiten Bewegung vieler Kanaele.

Perioden: die 5 Nachkriegsphasen aus `frage4_kriegspraemie_medientyp_bericht.PHASEN` (echter
Import, wie Schritt 8e) PLUS zwei Vorkriegsperioden (Nutzervorgabe "Vorkrieg -12 bis -6, -6 bis
0" - an der gemeinsamen Grenze -6 auf zwei sich NICHT UEBERSCHNEIDENDE Fenster aufgeteilt, analog
zur Nicht-Ueberlappungskonvention von PHASEN, wo P1 bei Monat 0 beginnt):

    vorkrieg_fern: Monat -12 bis -7
    vorkrieg_nah:  Monat -6 bis -1

Datenquelle: `lade_basisdaten()` aus `frage4_kriegspraemie_relative_views_plots.py` (echter
Import, identisch zu Schritt 8d/8e) - `rel_monat` in [-12, 48] (dortiges PERIODE_MIN/
PERIODE_MAX). Das ist GENAU der Datenausschnitt, der in der referenzierten Grafik gezeigt wird
(der Datenrand bei rel_monat=52 in `channel_video_erfolg.csv` wird dadurch wie auch in Schritt 8e
abgeschnitten - bewusst beibehalten fuer 1:1-Konsistenz mit der Grafik, kein Bug).

Mindestbesetzung: wie Schritt 8e (`MIN_VIDEOS_GESAMT_PRO_PHASE`, echter Import) - eine (Periode,
Umfang)-Zelle wird GESAMT uebersprungen (alle Kanaele), wenn sie unterbesetzt ist, damit die
Anteile innerhalb einer Zelle weiterhin konsistent (Gruppen- und Marktanteile summieren sich zu
100%) bleiben.

Schreibt `kanaluebersicht_marktanteil_bericht.csv` (eine Zeile je Kanal x Periode x Umfang) und
`kanaluebersicht_marktanteil_bericht.md` (fokussierte Tabellen: Top-Kanaele je Gruppe5 in den
beiden Vorkriegsperioden fuer den Umfang "andere_politische_videos" - der in der Nutzerfrage
referenzierte Umfang). Fuer die vollstaendige Kanal x Periode x Umfang-Matrix (zu gross fuer eine
lesbare Markdown-Tabelle) siehe die CSV oder das sortierbare/filterbare HTML-Artifact (siehe
Chat-Verlauf der Session, in der dieses Skript entstand).

Laeuft direkt als Skript (sibling-Importe wie die anderen step6_auswertung-Dateien, kein -m):

    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe kanaluebersicht_marktanteil_bericht.py

(im Ordner src/youtube_code/step6_auswertung/ ausgefuehrt).
"""

import json

import pandas as pd

from youtube_code.config import OUTPUTS
from deskriptiv_plots import GRUPPE5_REIHENFOLGE
from frage4_kriegspraemie_relative_views_plots import lade_basisdaten
from frage4_kriegspraemie_medientyp_bericht import PHASEN, _phase_fenster
from frage4_kriegspraemie_marktanteil_phasen_bericht import UMFAENGE, MIN_VIDEOS_GESAMT_PRO_PHASE

# =========================================================
# CONFIG
# =========================================================

# Zwei Vorkriegsperioden statt der EINEN "Vorkriegszeitraum"-Phase aus Schritt 8e - siehe
# Moduldocstring fuer die Grenzziehung.
VORKRIEGSPERIODEN = [
    ("vorkrieg_fern", "Vorkrieg fern (Monat -12 bis -7)", -12, -7),
    ("vorkrieg_nah", "Vorkrieg nah (Monat -6 bis -1)", -6, -1),
]

# Fokus-Umfang/-Gruppen fuer den Markdown-Bericht (Nutzerfrage bezog sich konkret auf diese
# Kombination - siehe Moduldocstring). Die CSV/das Artifact enthalten weiterhin ALLE Umfaenge
# und Gruppen.
FOKUS_UMFANG = "andere_politische_videos"
FOKUS_GRUPPEN = ["Traditionelles Medium", "Alternative Medien (rechts)"]
TOP_N_FOKUS = 8

PFAD_ERGEBNIS_CSV = OUTPUTS / "segment_analysis" / "kanaluebersicht_marktanteil_bericht.csv"
PFAD_ERGEBNIS_MD = OUTPUTS / "segment_analysis" / "kanaluebersicht_marktanteil_bericht.md"


# =========================================================
# SCHRITT 1: Perioden (2 Vorkriegsperioden + 5 Nachkriegsphasen)
# =========================================================

def baue_periodenliste(basisdaten):
    """[(periode_id, label, monat_min, monat_max)]: VORKRIEGSPERIODEN zuerst, dann PHASEN (echter
    Import) in Reihenfolge. monat_max=None (P5) wird auf das tatsaechliche Datenmaximum
    aufgeloest (wie in Schritt 8e)."""
    monat_max_gesamt = int(basisdaten["rel_monat"].max())
    perioden = list(VORKRIEGSPERIODEN)
    for phase_id, cfg in PHASEN.items():
        monat_max = cfg["monat_max"] if cfg["monat_max"] is not None else monat_max_gesamt
        perioden.append((phase_id, cfg["label"], cfg["monat_min"], monat_max))
    return perioden


# =========================================================
# SCHRITT 2: Kanal-Kennzahlen je Periode x Umfang
# =========================================================

def berechne_tabelle(basisdaten, periodenliste, min_videos_gesamt=MIN_VIDEOS_GESAMT_PRO_PHASE):
    """Eine Zeile je (Periode, Umfang, Kanal): n_videos, views_summe, anteil_am_markt_pct
    (Anteil an der Views-Summe ALLER 5 Gruppen) und anteil_an_gruppe_pct (Anteil an der
    Views-Summe der EIGENEN Gruppe5-Kategorie) - siehe Moduldocstring fuer die Formeln. Eine
    (Periode, Umfang)-Zelle wird GESAMT uebersprungen (analog Schritt 8e), wenn ihre
    Gesamtbesetzung unter min_videos_gesamt liegt."""
    zeilen = []
    uebersprungen = []
    for periode_id, label, monat_min, monat_max in periodenliste:
        periode_df = _phase_fenster(basisdaten, monat_min, monat_max)
        for umfang_key, umfang_cfg in UMFAENGE.items():
            umfang_df = periode_df[umfang_cfg["filter"](periode_df)]
            n_gesamt = len(umfang_df)
            if n_gesamt < min_videos_gesamt:
                uebersprungen.append((label, umfang_cfg["titel"], n_gesamt))
                continue

            views_markt_gesamt = float(umfang_df["view_count"].sum())
            views_je_gruppe = umfang_df.groupby("gruppe5")["view_count"].sum()

            je_kanal = umfang_df.groupby(
                ["channel_id", "channel_title", "gruppe5"], as_index=False
            ).agg(views_summe=("view_count", "sum"), n_videos=("view_count", "size"))

            for row in je_kanal.itertuples(index=False):
                views_gruppe = float(views_je_gruppe.get(row.gruppe5, 0.0))
                zeilen.append({
                    "periode": periode_id, "periode_label": label,
                    "monat_min": monat_min, "monat_max": monat_max,
                    "umfang": umfang_key, "umfang_titel": umfang_cfg["titel"],
                    "channel_id": row.channel_id, "channel_title": row.channel_title,
                    "gruppe5": row.gruppe5,
                    "n_videos": int(row.n_videos), "views_summe": float(row.views_summe),
                    "anteil_am_markt_pct": float(row.views_summe) / views_markt_gesamt * 100,
                    "anteil_an_gruppe_pct": (float(row.views_summe) / views_gruppe * 100
                                              if views_gruppe > 0 else 0.0),
                })

    if uebersprungen:
        print(f"[Kanaluebersicht] {len(uebersprungen)} (Periode, Umfang)-Zellen uebersprungen "
              f"(< {min_videos_gesamt} Videos insgesamt):")
        for label, titel, n in uebersprungen:
            print(f"  - {label} / {titel}: {n} Videos")

    return pd.DataFrame(zeilen)


# =========================================================
# SCHRITT 3: Fokus-Bericht (Markdown)
# =========================================================

def _formatiere_zahl(x):
    return f"{x:,.0f}".replace(",", ".")


def baue_bericht(tabelle, periodenliste):
    zeilen = [
        "# Kanaluebersicht: Marktanteil je Kanal (Konzentrationscheck)",
        "",
        "Kanal-Ebenen-Zerlegung des Gruppen-Marktanteils aus "
        "`frage4_kriegspraemie_marktanteil_plots.py` (8d) / "
        "`frage4_kriegspraemie_marktanteil_phasen_bericht.py` (8e) - siehe Moduldocstring von "
        "`kanaluebersicht_marktanteil_bericht.py` fuer die vollstaendige Herleitung und die "
        "beiden Kennzahlen-Formeln.",
        "",
        "- **anteil_am_markt_pct**: Anteil des Kanals an der Views-Summe ALLER 5 Gruppe5-"
        "Kategorien (Kanal-Zerlegung des bereits berichteten Gruppen-Marktanteils).",
        "- **anteil_an_gruppe_pct**: Anteil des Kanals an der Views-Summe der EIGENEN Gruppe5-"
        "Kategorie - zeigt Konzentration INNERHALB der Gruppe (nahe 100% = ein/zwei Kanaele "
        "dominieren die Gruppe).",
        "",
        f"Vollstaendige Matrix (alle Kanaele x alle {len(periodenliste)} Perioden x alle 3 "
        f"Umfaenge, {len(tabelle)} Zeilen) in `kanaluebersicht_marktanteil_bericht.csv`. Dieser "
        "Bericht zeigt nur den Ausschnitt, der die konkrete Nutzerfrage beantwortet: Umfang "
        f"'{UMFAENGE[FOKUS_UMFANG]['titel']}', Gruppen {', '.join(FOKUS_GRUPPEN)}, beide "
        "Vorkriegsperioden.",
        "",
    ]

    fokus = tabelle[(tabelle["umfang"] == FOKUS_UMFANG)
                     & (tabelle["gruppe5"].isin(FOKUS_GRUPPEN))
                     & (tabelle["periode"].isin([p[0] for p in VORKRIEGSPERIODEN]))]

    for gruppe in FOKUS_GRUPPEN:
        zeilen.append(f"## {gruppe}")
        zeilen.append("")
        for periode_id, label, _, _ in VORKRIEGSPERIODEN:
            teil = fokus[(fokus["gruppe5"] == gruppe) & (fokus["periode"] == periode_id)]
            teil = teil.sort_values("anteil_an_gruppe_pct", ascending=False)
            zeilen.append(f"**{label}**"
                          + ("" if not teil.empty else " - Zelle unterbesetzt, uebersprungen.")
                          )
            zeilen.append("")
            if not teil.empty:
                zeilen.append("| Kanal | n Videos | Views-Summe | Anteil an Gruppe | "
                               "Anteil am Gesamtmarkt |")
                zeilen.append("|---|---|---|---|---|")
                for row in teil.head(TOP_N_FOKUS).itertuples(index=False):
                    zeilen.append(
                        f"| {row.channel_title} | {_formatiere_zahl(row.n_videos)} | "
                        f"{_formatiere_zahl(row.views_summe)} | "
                        f"{row.anteil_an_gruppe_pct:.1f}% | {row.anteil_am_markt_pct:.2f}% |"
                    )
                rest_n = len(teil) - min(len(teil), TOP_N_FOKUS)
                if rest_n > 0:
                    zeilen.append(f"| *... {rest_n} weitere Kanaele* | | | | |")
                # Herfindahl-aehnliche Kurzkennzahl: Anteil der Top-2-Kanaele an der Gruppe.
                top2 = teil.head(2)["anteil_an_gruppe_pct"].sum()
                zeilen.append("")
                zeilen.append(f"-> Top-2-Kanaele vereinen {top2:.0f}% der Gruppen-Views auf sich "
                               f"({len(teil)} Kanaele insgesamt in dieser Zelle).")
            zeilen.append("")

    return "\n".join(zeilen) + "\n"


# =========================================================
# MAIN
# =========================================================

def main():
    basisdaten = lade_basisdaten()
    periodenliste = baue_periodenliste(basisdaten)
    tabelle = berechne_tabelle(basisdaten, periodenliste)

    PFAD_ERGEBNIS_CSV.parent.mkdir(parents=True, exist_ok=True)
    tabelle.to_csv(PFAD_ERGEBNIS_CSV, index=False)
    print(f"[CSV] {PFAD_ERGEBNIS_CSV} ({len(tabelle)} Zeilen)")

    bericht = baue_bericht(tabelle, periodenliste)
    with open(PFAD_ERGEBNIS_MD, "w", encoding="utf-8") as f:
        f.write(bericht)
    print(f"[Bericht] {PFAD_ERGEBNIS_MD}")

    return tabelle, periodenliste


if __name__ == "__main__":
    main()

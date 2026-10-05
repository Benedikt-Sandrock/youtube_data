# -*- coding: utf-8 -*-
"""
patch_frage4_executive_summary.py

Einmaliger Nachtrag der neuen Executive-Summary-Sektion (siehe
frage4_kriegspraemie_medientyp_bericht.py::_baue_executive_summary(),
Nutzervorgabe 2026-09-09 "Executive summary ... aufgeteilt nach den
wesentlichen Kriterien ... in wie vielen Spezifikationen der Koeffizient fuer
einen Medientyp signifikant ist") in die BEREITS GELAUFENEN Berichte
frage4_kriegspraemie_medientyp_bericht_{granularitaet}.md, OHNE die 108
Regressionen je Granularitaet erneut zu rechnen (das waere ein laenger
laufendes Skript und braucht laut CLAUDE.md vorherige Ruecksprache - hier
unnoetig, da die _baue_executive_summary()-Eingabe [dieselbe Long-Format-
Tabelle wie ergebnis in verarbeite_granularitaet()] bereits als CSV auf
Platte liegt).

Liest die vorhandene {...}.csv, ruft _baue_executive_summary() (importiert aus
dem eigentlichen Berichtsskript, damit exakt dieselbe Logik wie bei kuenftigen
main()-Laeufen verwendet wird) auf und fuegt das Ergebnis zwischen den
bestehenden Report-Kopf (Methodik-Absatz) und den ersten Modell-Block ein -
der Rest der Datei (alle Modell-Bloecke) bleibt Byte-fuer-Byte unveraendert.

Nur fuer diesen einmaligen Nachtrag noetig: ein neuer main()-Lauf von
frage4_kriegspraemie_medientyp_bericht.py schreibt die Executive Summary ab
jetzt automatisch mit (siehe dortige verarbeite_granularitaet()) - dieses
Skript hier wird danach nicht mehr gebraucht, deshalb scripts/adhoc/ statt
src/youtube_code/ (siehe .claude/CLAUDE.md "Keine Ad-hoc-Skripte ... ausserhalb
von scripts/adhoc/").
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BERICHT_DIR = REPO_ROOT / "src" / "youtube_code" / "step6_auswertung"
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(BERICHT_DIR))

import pandas as pd  # noqa: E402
from frage4_kriegspraemie_medientyp_bericht import (  # noqa: E402
    _baue_executive_summary, RESULTS_PATH,
)

GRANULARITAETEN = ["monat", "quartal"]
MARKER = "\n### Modell:"


def patch_eine_granularitaet(granularitaet):
    csv_pfad = RESULTS_PATH / f"frage4_kriegspraemie_medientyp_bericht_{granularitaet}.csv"
    md_pfad = RESULTS_PATH / f"frage4_kriegspraemie_medientyp_bericht_{granularitaet}.md"

    ergebnis = pd.read_csv(csv_pfad, encoding="utf-8")
    executive_summary = _baue_executive_summary(ergebnis)

    text = md_pfad.read_text(encoding="utf-8")
    if MARKER not in text:
        raise ValueError(f"{md_pfad}: Marker '{MARKER}' nicht gefunden - Datei hat "
                          "nicht die erwartete Struktur (Report-Kopf + Modell-Bloecke).")
    if "## Executive Summary" in text:
        print(f"[{granularitaet}] enthaelt bereits eine Executive Summary - ueberspringe.")
        return

    idx = text.index(MARKER)
    report_kopf = text[:idx]
    rest = text[idx:].lstrip("\n")
    neuer_text = report_kopf.rstrip("\n") + "\n\n" + executive_summary + "\n\n" + rest

    md_pfad.write_text(neuer_text, encoding="utf-8")
    print(f"[{granularitaet}] Executive Summary eingefuegt ({len(executive_summary)} Zeichen) -> {md_pfad}")


def main():
    for granularitaet in GRANULARITAETEN:
        patch_eine_granularitaet(granularitaet)


if __name__ == "__main__":
    main()

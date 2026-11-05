# -*- coding: utf-8 -*-
"""
regressionstest_export_2019_2020.py

Vergleicht den neuen Export (outputs/stata_rohdaten/) mit der gesicherten
Version vor der 2019-2020-Erweiterung (_backups/stata_rohdaten_vor_2019/).
Erwartung: Fuer Videos ab 01.01.2021 sind alle gemeinsamen Variablen gleich
(Ausnahmen: format_klass fuer Kanaele, deren Status sich geaendert hat; Views
zeigen den Snapshot der Registry), Kanalvariablen n_videos/erstes_video_ts
unveraendert. Schreibt einen Markdown-Report.

Ausfuehren aus dem Repo-Root:
    PYTHONPATH=src .venv/Scripts/python.exe scripts/adhoc/regressionstest_export_2019_2020.py
"""
import pandas as pd

from youtube_code.config import OUTPUTS

# =========================================================
# KONFIGURATION
# =========================================================
ALT = OUTPUTS.parent / "_backups" / "stata_rohdaten_vor_2019"
NEU = OUTPUTS / "stata_rohdaten"
AUSGABE = OUTPUTS / "video_formats" / "regressionstest_export_2019_2020.md"
# Videos ab diesem Zeitpunkt werden verglichen
AB = pd.Timestamp("2021-01-01")


def vergleiche(alt, neu, schluessel):
    gemeinsam = [c for c in alt.columns if c in neu.columns and c != schluessel]
    m = alt[[schluessel] + gemeinsam].merge(neu[[schluessel] + gemeinsam], on=schluessel, suffixes=("_a", "_n"))
    zeilen = []
    for c in gemeinsam:
        a, n = m[c + "_a"], m[c + "_n"]
        gleich = (a == n) | (a.isna() & n.isna())
        zeilen.append((c, int((~gleich).sum())))
    return m, zeilen, gemeinsam


def main():
    out = ["# Regressionstest Export 2019-2020 vs. vor_2019", ""]
    va = pd.read_stata(ALT / "videos_roh.dta", convert_categoricals=False)
    vn = pd.read_stata(NEU / "videos_roh.dta", convert_categoricals=False)
    va = va[va["upload_ts"] >= AB]
    vn_ab = vn[vn["upload_ts"] >= AB]
    out += [f"- Videos ab 2021: alt {len(va)}, neu {len(vn_ab)}; nur alt: {len(set(va.video_id) - set(vn_ab.video_id))}, "
            f"nur neu: {len(set(vn_ab.video_id) - set(va.video_id))}", f"- Videos neu gesamt: {len(vn)}", ""]
    m, zeilen, gem = vergleiche(va, vn_ab, "video_id")
    out += ["## videos_roh: abweichende Werte je Variable (nur Videos in beiden)", "", "| Variable | n abweichend |", "|---|---|"]
    out += [f"| {c} | {d} |" for c, d in zeilen if d]
    out += ["", f"Variablen ohne Abweichung: {sum(1 for _, d in zeilen if d == 0)} von {len(zeilen)}", ""]
    neue_spalten = [c for c in vn.columns if c not in va.columns]
    out += [f"Neue Variablen videos_roh: {neue_spalten}", ""]
    ka = pd.read_stata(ALT / "kanaele_roh.dta", convert_categoricals=False)
    kn = pd.read_stata(NEU / "kanaele_roh.dta", convert_categoricals=False)
    _, zk, _ = vergleiche(ka, kn, "channel_id")
    out += ["## kanaele_roh: abweichende Werte je Variable", "", "| Variable | n abweichend |", "|---|---|"]
    out += [f"| {c} | {d} |" for c, d in zk if d]
    out += ["", f"Neue Variablen kanaele_roh: {[c for c in kn.columns if c not in ka.columns]}", ""]
    AUSGABE.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()

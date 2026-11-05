"""Vergleichsmassstab fuer die Breite des Wachstums der rechten Alternativmedien
in Monat 5-8 (siehe alt_rechts_sprung_m5_m6.py): dieselbe Kennzahl fuer alle
aufeinanderfolgenden Fensterpaare (A = 4 Monate, B = die 4 Monate danach) von
2019 bis 2025, je Gruppe (Alternative rechts, Traditionelle Medien, OeRR).

Kennzahl je Kanal: Faktor = mittlere Views je Monat in B / in A (Monate ohne
Upload = 0); nur Kanaele mit Uploads in mind. MIN_AKTIVE_MONATE Monaten von A
und Views > 0 in beiden Fenstern. Ausgabe je Fenster: Median-Faktor, Anteile
> 1,25 / > 1,5 / < 0,8, gepoolter Faktor.

Kanalliste: channels_check.xlsx mit sample in SAMPLE_CODES und foreign != 1
(ohne den media_category-Filter von marktanteil_rohdaten_plots.KANALLISTE,
damit Traditionelle und OeRR enthalten sind). Gruppen wie dort inkl. _manuell.
Ausgabe: scripts/adhoc/alt_rechts_sprung/benchmark_fenster.md
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from youtube_code.step6_auswertung import marktanteil_rohdaten_plots as mp  # noqa: E402
from youtube_code.step6_auswertung.prepare_channel_scores import KRIEGSBEGINN, relativ_periode  # noqa: E402

# =========================================================
# KONFIGURATION
# =========================================================
GRUPPEN = ["Alternative (rechts)", "Traditionelle Medien", "ÖRR"]  # aus medientyp_ideologie
SAMPLE_CODES = [1, 2, 3]       # Codes der Spalte "sample" in channels_check.xlsx
FENSTER = 4                    # Monate je Fenster (int >= 1)
ERSTES_B = -27                 # rel_monat, an dem das erste Fenster B beginnt (so gewaehlt, dass 5 ein Start ist)
LETZTES_B = 41                 # rel_monat, an dem das letzte Fenster B beginnt
MIN_AKTIVE_MONATE = 3          # Mindestzahl Monate mit Upload im Fenster A (1..FENSTER)
AUSGABE = ROOT / "scripts" / "adhoc" / "alt_rechts_sprung" / "benchmark_fenster.md"


def main():
    if not 1 <= MIN_AKTIVE_MONATE <= FENSTER:
        raise SystemExit(f"MIN_AKTIVE_MONATE muss zwischen 1 und FENSTER ({FENSTER}) liegen.")
    if (5 - ERSTES_B) % FENSTER:
        raise SystemExit("ERSTES_B so waehlen, dass Monat 5 ein Fensterstart ist.")
    k = mp.lade_kanaele()
    k, _ = mp.bilde_gruppen(k)
    k, _ = mp.manuell_alt_rechts(k)
    cc = pd.read_excel(mp.STATA_OUTPUT / "channels_check.xlsx")
    cc = cc[cc["sample"].isin(SAMPLE_CODES) & (cc["foreign"] != 1)]
    k = k[k["channel_id"].isin(set(cc["channel_id"])) & k["medientyp_ideologie"].isin(GRUPPEN)]
    k = k[["channel_id", "medientyp_ideologie"]]
    v = pd.read_stata(mp.ROHDATEN_PFAD / "videos_roh.dta", columns=["channel_id", "upload_ts", "views", "format"])
    v = v[(v["format"].astype(str) == "long") & v["views"].notna()].merge(k, on="channel_id")
    v["m"] = relativ_periode(v["upload_ts"], pd.Timestamp(KRIEGSBEGINN), 1)
    cm = v.groupby(["medientyp_ideologie", "channel_id", "m"])["views"].sum()

    out = ["# Vergleichsmaßstab: Wachstumsbreite je Fensterpaar", "",
           f"Erzeugt von `scripts/adhoc/alt_rechts_sprung_benchmark.py`. Fenster je {FENSTER} Monate; "
           f"Faktor = Views B / Views A je Kanal; Kanäle mit Uploads in ≥ {MIN_AKTIVE_MONATE} Monaten von A. "
           f"Kanalzahl je Gruppe: {k['medientyp_ideologie'].value_counts().to_dict()}.", ""]
    for g in GRUPPEN:
        d = cm.loc[g].unstack(fill_value=0)
        rows = []
        for b in range(ERSTES_B, LETZTES_B + 1, FENSTER):
            da = d.reindex(columns=range(b - FENSTER, b), fill_value=0)
            db = d.reindex(columns=range(b, b + FENSTER), fill_value=0)
            a, bb = da.mean(axis=1), db.mean(axis=1)
            ok = (a > 0) & (bb > 0) & (da.gt(0).sum(axis=1) >= MIN_AKTIVE_MONATE)
            f = bb[ok] / a[ok]
            start = pd.Timestamp(KRIEGSBEGINN) + pd.DateOffset(months=b)
            rows.append({"B_start": b, "ab": f"{start:%m/%Y}", "n": int(ok.sum()),
                         "median_faktor": f"{f.median():.2f}", "anteil_>1,25": f"{(f > 1.25).mean():.0%}",
                         "anteil_>1,5": f"{(f > 1.5).mean():.0%}", "anteil_<0,8": f"{(f < 0.8).mean():.0%}",
                         "gepoolt": f"{bb[ok].sum() / a[ok].sum():.2f}"})
        t = pd.DataFrame(rows)
        out += [f"## {g}", "", "| " + " | ".join(t.columns) + " |", "|" + "---|" * len(t.columns),
                *["| " + " | ".join(map(str, r)) + " |" for r in t.itertuples(index=False)], ""]
    AUSGABE.parent.mkdir(parents=True, exist_ok=True)
    AUSGABE.write_text("\n".join(out), encoding="utf-8")
    print(f"-> {AUSGABE}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
welt_kriegspraemie.py

Prueft die "Kriegspraemie" bei den traditionellen Medien (v. a. WELT) statistisch:
Haben Kriegsvideos nach Kriegsbeginn mehr Views je Video als Nicht-Kriegsvideos
desselben Kanals im selben Monat, und ist dieser Abstand groesser als vor
Kriegsbeginn? Kontext: `.claude/plans/session_2026-10-27_traditionelle_views.md`.

Datenbasis: `outputs/stata_rohdaten/videos_roh.dta` + `kanaele_roh.dta`, nur
format in FORMAT, Kanal-Sample wie im Marktanteils-Plot (channels_check.xlsx).
Kriegsvideo = rel_russia_ukraine_war_cw == "ja" (Titel-Stichworte core+wide).
Vor Kriegsbeginn misst diese Variable v. a. Russland-Berichterstattung, die
"Vorkriegspraemie" ist also eine Russland-Themen-Praemie.

1. Deskriptiv je Phase und Kanal (KANAELE_EINZELN): Kriegs- vs. Nicht-Kriegsvideos
   (Uploads/Monat, Median und Mittel der Views je Video, Mio. Views/Monat) und
   die "Mehr-Views durch die Praemie" = sum(views Kriegsvideos) -
   n(Kriegsvideos) * mittlere Views der Nicht-Kriegsvideos (Mio./Monat).
2. Regressionen (OLS, abhaengige Variable log(1 + views)), Video-Ebene:
   a) je Kanal in KANAELE_EINZELN: Kriegsvideo x Phase mit Monats-FE
      (Phase REFERENZPHASE = Referenz); der Koeffizient "krieg" ist die Praemie in
      der Referenzphase, "krieg:phase_X" die Veraenderung in Phase X.
   b) alle traditionellen Kanaele gepoolt: wie a), aber mit Kanal-x-Monat-FE
      (Vergleich nur innerhalb Kanal und Monat).
   Monats-FE fangen den Alterseffekt (juengere Videos weniger Views) ab.
   Standardfehler geclustert nach Monat (a) bzw. Kanal-Monat (b).

Ausgabe: `scripts/adhoc/outputs/regression_results/welt_kriegspraemie.md`

Ausfuehren aus dem Repo-Root (ca. 1 min):
    PYTHONPATH=src .venv/Scripts/python.exe scripts/adhoc/welt_kriegspraemie.py
"""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from youtube_code.config import OUTPUTS, ROOT, STATA_OUTPUT
from youtube_code.step6_auswertung.prepare_channel_scores import KRIEGSBEGINN, relativ_periode

# =========================================================
# CONFIG
# =========================================================

ROHDATEN_PFAD = OUTPUTS / "stata_rohdaten"
OUT_DIR = ROOT / "scripts" / "adhoc" / "outputs" / "regression_results"

# Medientyp wie in kanaele_roh.medientyp (z. B. "traditionelle Medien", "ÖRR")
MEDIENTYP = "traditionelle Medien"

# Videoformate (Teilmenge von "long", "short", "live")
FORMAT = ["long"]

# Kanaele (kanal_name wie in kanaele_roh) mit eigener Tabelle und Regression a)
KANAELE_EINZELN = ["WELT Nachrichtensender", "BILD", "DER SPIEGEL", "ntv Nachrichten"]

# Phasen (Name, von, bis) in rel_monat, inklusive, aufsteigend, ohne Ueberlappung
PHASEN = [
    ("A", -25, -13),
    ("B", -12, -1),
    ("C", 0, 16),
    ("D", 17, 26),
    ("E", 27, 36),
    ("F", 37, 51),
]

# Referenzphase der Regressionen (einer der Namen aus PHASEN, sinnvoll: eine Vorkriegsphase)
REFERENZPHASE = "B"

# Zeilen je Chunk beim Lesen von videos_roh.dta
CHUNK_ZEILEN = 500_000


# =========================================================
# Daten laden
# =========================================================

def lade_kanaele():
    k = pd.read_stata(ROHDATEN_PFAD / "kanaele_roh.dta", columns=["channel_id", "kanal_name", "medientyp"])
    k["medientyp"] = k["medientyp"].astype(str)
    k["kanal_name"] = k["kanal_name"].astype(str)
    cc = pd.read_excel(STATA_OUTPUT / "channels_check.xlsx")
    cc = cc[cc["media_category"].isin([1, 2, 5]) & (cc["sample"] == 1) & (cc["foreign"] != 1)]
    k = k[(k["medientyp"] == MEDIENTYP) & k["channel_id"].isin(cc["channel_id"])]
    print(f"[Kanaele] {len(k)} Kanaele")
    return k


def lade_videos(k):
    spalten = ["channel_id", "upload_ts", "views", "format", "rel_russia_ukraine_war_cw"]
    teile = []
    with pd.read_stata(ROHDATEN_PFAD / "videos_roh.dta", columns=spalten, chunksize=CHUNK_ZEILEN) as leser:
        for chunk in leser:
            teile.append(chunk[chunk["channel_id"].isin(k["channel_id"])
                               & chunk["format"].astype(str).isin(FORMAT)
                               & chunk["views"].notna()])
    v = pd.concat(teile, ignore_index=True)
    v["kanal"] = v["channel_id"].map(k.set_index("channel_id")["kanal_name"])
    v["krieg"] = (v["rel_russia_ukraine_war_cw"].astype(str) == "ja").astype(int)
    v["monat"] = relativ_periode(v["upload_ts"], pd.Timestamp(KRIEGSBEGINN), 1)
    v["log_views"] = np.log1p(v["views"])
    v["phase"] = None
    for name, von, bis in PHASEN:
        v.loc[v["monat"].between(von, bis), "phase"] = name
    v = v[v["phase"].notna()]
    print(f"[Videos] {len(v)} Videos in den Phasen, davon {v['krieg'].sum()} Kriegsvideos")
    return v


# =========================================================
# 1. Deskriptiv
# =========================================================

def deskriptiv(v):
    monate = {name: bis - von + 1 for name, von, bis in PHASEN}
    zeilen = []
    for phase, d in v.groupby("phase", sort=False):
        kr, nk = d[d["krieg"] == 1], d[d["krieg"] == 0]
        m = monate[phase]
        mehr = kr["views"].sum() - len(kr) * nk["views"].mean() if len(nk) else np.nan
        zeilen.append({
            "Phase": phase,
            "Uploads Krieg/Monat": round(len(kr) / m),
            "Uploads sonst/Monat": round(len(nk) / m),
            "Median Krieg (Tsd.)": round(kr["views"].median() / 1e3, 1),
            "Median sonst (Tsd.)": round(nk["views"].median() / 1e3, 1),
            "Mittel Krieg (Tsd.)": round(kr["views"].mean() / 1e3, 1),
            "Mittel sonst (Tsd.)": round(nk["views"].mean() / 1e3, 1),
            "Views Krieg (Mio./Monat)": round(kr["views"].sum() / m / 1e6, 1),
            "Views sonst (Mio./Monat)": round(nk["views"].sum() / m / 1e6, 1),
            "Mehr-Views Praemie (Mio./Monat)": round(mehr / m / 1e6, 1),
        })
    return pd.DataFrame(zeilen).set_index("Phase").reindex([p[0] for p in PHASEN])


# =========================================================
# 2. Regressionen
# =========================================================

def regression(d, fe, cluster):
    d = d.copy()
    phasen = [p[0] for p in PHASEN if p[0] != REFERENZPHASE]
    terme = []
    for p in phasen:
        d[f"phase_{p}"] = (d["phase"] == p).astype(int)
        d[f"krieg_x_{p}"] = d[f"phase_{p}"] * d["krieg"]
        terme.append(f"krieg_x_{p}")
    # FE ueber Within-Transformation (Mittelwert je FE-Gruppe abziehen) statt Dummies,
    # spart bei Kanal-x-Monat-FE >1.000 Dummy-Spalten; Koeffizienten identisch, SE ohne
    # Freiheitsgrad-Korrektur fuer die FE (bei Cluster-SE vernachlaessigbar).
    # Phasen-Haupteffekte stecken in den FE.
    spalten = ["log_views", "krieg", *terme]
    d[spalten] = d[spalten] - d.groupby(fe)[spalten].transform("mean")
    formel = f"log_views ~ 0 + krieg + {' + '.join(terme)}"
    gruppen = pd.factorize(d[cluster])[0]
    res = smf.ols(formel, data=d).fit(cov_type="cluster", cov_kwds={"groups": gruppen})
    zeilen = []
    for t in ["krieg", *terme]:
        b, se, pw = res.params[t], res.bse[t], res.pvalues[t]
        praemie = res.params["krieg"] + (b if t != "krieg" else 0)
        zeilen.append({
            "Term": t if t == "krieg" else f"krieg x Phase {t.split('_')[-1]}",
            "Koeffizient": round(b, 3), "SE": round(se, 3), "p": round(pw, 4),
            "Praemie in Phase (log)": round(praemie, 3),
            "Praemie in Phase (%)": round((np.exp(praemie) - 1) * 100, 0),
        })
    return pd.DataFrame(zeilen).set_index("Term"), int(res.nobs), res.rsquared


def als_markdown(t, index_name):
    kopf = f"| {index_name} | " + " | ".join(t.columns) + " |"
    trenner = "|---|" + "---:|" * len(t.columns)
    zeilen = [f"| {idx} | " + " | ".join("" if pd.isna(x) else f"{x:g}" for x in row) + " |"
              for idx, row in t.iterrows()]
    return "\n".join([kopf, trenner, *zeilen])


# =========================================================
# Main
# =========================================================

def main():
    if not FORMAT or not set(FORMAT) <= {"long", "short", "live"}:
        raise SystemExit("FORMAT muss eine nicht-leere Teilmenge von long/short/live sein.")
    if REFERENZPHASE not in [p[0] for p in PHASEN]:
        raise SystemExit(f"REFERENZPHASE {REFERENZPHASE!r} ist keine Phase aus PHASEN.")
    for (_, von, bis), (_, von2, _) in zip(PHASEN, PHASEN[1:] + [("", 10**6, 0)]):
        if not von <= bis < von2:
            raise SystemExit("PHASEN muessen aufsteigend sein, von <= bis, ohne Ueberlappung.")

    k = lade_kanaele()
    fehlend = sorted(set(KANAELE_EINZELN) - set(k["kanal_name"]))
    if fehlend:
        raise SystemExit(f"KANAELE_EINZELN nicht im Sample: {fehlend}")
    v = lade_videos(k)

    phasen_text = ", ".join(f"{n} = Monat {a}..{b}" for n, a, b in PHASEN)
    teile = [
        f"# Kriegsprämie {MEDIENTYP}, format {'+'.join(FORMAT)}",
        "",
        f"Erzeugt von `scripts/adhoc/welt_kriegspraemie.py` am {pd.Timestamp.now():%d.%m.%Y %H:%M}. "
        f"Phasen: {phasen_text}; Monat 0 beginnt am {KRIEGSBEGINN}. Kriegsvideo = "
        "`rel_russia_ukraine_war_cw` (vor Kriegsbeginn v. a. Russland-Themen).",
        "",
        "Regressionen: OLS, y = log(1 + views), Monats-FE (Einzelkanäle) bzw. Kanal-x-Monat-FE (gepoolt); "
        f"Referenzphase {REFERENZPHASE}. 'Prämie in Phase' = krieg + krieg x Phase, in % = exp(b) - 1 "
        "(Views je Kriegsvideo relativ zu Nicht-Kriegsvideos desselben Monats).",
    ]

    teile += ["", "## Gepoolt: alle Kanäle des Medientyps (Kanal-x-Monat-FE, Cluster Kanal-Monat)", ""]
    v["kanal_monat"] = v["kanal"] + "_" + v["monat"].astype(str)
    t, n, r2 = regression(v, "kanal_monat", "kanal_monat")
    teile += [f"N = {n}, R² (within) = {r2:.3f}", "", als_markdown(t, "Term")]
    print(f"\n[gepoolt] N={n}\n{t.to_string()}")

    for kanal in KANAELE_EINZELN:
        d = v[v["kanal"] == kanal]
        teile += ["", f"## {kanal}", "", "### Deskriptiv", "", als_markdown(deskriptiv(d), "Phase")]
        t, n, r2 = regression(d, "monat", "monat")
        teile += ["", "### Regression (Monats-FE, Cluster Monat)", "", f"N = {n}, R² (within) = {r2:.3f}", "",
                  als_markdown(t, "Term")]
        print(f"\n[{kanal}]\n{deskriptiv(d).to_string()}\nN={n}\n{t.to_string()}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    datei = OUT_DIR / "welt_kriegspraemie.md"
    datei.write_text("\n".join(teile) + "\n", encoding="utf-8")
    print(f"\n[Ausgabe] {datei}")


if __name__ == "__main__":
    main()

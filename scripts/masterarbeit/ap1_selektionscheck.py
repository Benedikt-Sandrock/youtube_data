# -*- coding: utf-8 -*-
"""
ap1_selektionscheck.py - AP 1, Schritt 3 (.claude/plans/masterarbeit_strategie.md)

Robustheitstabelle fuer Frage 1: drei Spezifikationen des Nachkriegseffekts
auf der Original-Population und auf den bereinigten Analysepopulationen, fuer
Populismus UND Stance (Position).

Voraussetzung: ap1_selektionsdiagnose.py ist gelaufen und hat
MASTERARBEIT_OUTPUTS/ap1_selektion/ap1_diagnose_videos.csv geschrieben.

Populationen (Definition und Herleitung siehe frage1_selektionsdiagnose.md
und frage1_methodik_und_stichprobe.md, Abschnitt "Selektions-Asymmetrie"):
  P0 original:    alle Videos der 279er-Whitelist in channel_video_populism.csv
                  (= Input von frage1_populismus_bericht.py)
  P1 bereinigt:   duration_seconds >= MIN_VIDEO_DURATION_SECONDS (181 s) UND
                  (ist_kriegsvideo == 1 ODER politics_final == 1). Unter 181 s
                  gibt es keine Themenklassifikation (get_videos_with_text()
                  filtert sie heraus), ist_kriegsvideo ist dort also nicht
                  definiert. Nicht-Kriegsvideos kommen vorher wie nachher aus
                  demselben Auswahlweg (Screening, politics_final == 1).
  P2 streng:      P1 UND Nicht-Kriegsvideos zusaetzlich mit Politics in
                  topic_categories

Spezifikationen (alle Kanal-FE, SE geclustert nach Kanal, rel_monat -12..42):
  (1) alle Videos: Kanal-Monat-Mittel, y ~ C(channel_id) + post
  (2) mit Kontrolle ist_kriegsvideo: Kanal-Monat-Krieg-Zellen,
      y ~ C(channel_id) + post + ist_kriegsvideo
  (3) nur Nicht-Kriegsvideos: Kanal-Monat-Mittel, y ~ C(channel_id) + post

Zusaetzlich fuer Kriegsvideos (nur P1, gesamt und je gruppe5):
  A  Kriegsvideos nach Kriegsbeginn vs. politische Nicht-Kriegsvideos desselben
     Kanals vorher (Kanal-Monat, Kanal-FE, post). Ausgabe mit Cluster-SE und
     der Zahl identifizierender Kanaele (Kanal-Monate vorher UND nachher)
  C  Entwicklung der Kriegsvideos in Kriegsjahr 1-4 (Kanal-FE + Jahr-Dummies,
     Referenz Jahr 1); C1 alle Kanaele, C2 balanciertes Panel (nur Kanaele
     mit Kriegsvideos in allen vier Kriegsjahren)
  B  Krieg vs. Nichtkrieg im selben Kanal-Monat nach Kriegsbeginn: zurueckgestellt,
     da zu wenige klassifizierte politische Nicht-Kriegsvideos nach Kriegsbeginn
     vorliegen (Neuklassifikation vorerst zu aufwendig).

Ausgabe: MASTERARBEIT_OUTPUTS/ap1_selektion/regression_results/frage1_selektionscheck.md

Ausfuehren aus dem Repo-Root:
    PYTHONPATH=src python scripts/masterarbeit/ap1_selektionscheck.py
"""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from youtube_code.config.paths import MASTERARBEIT_OUTPUTS, OUTPUTS
from youtube_code.config.settings import MIN_VIDEO_DURATION_SECONDS

# =========================================================
# CONFIG
# =========================================================

AUSGABE = MASTERARBEIT_OUTPUTS / "ap1_selektion"
PFAD_VIDEOS = AUSGABE / "ap1_diagnose_videos.csv"
PFAD_POSITION = OUTPUTS / "segment_analysis" / "channel_video_position.csv"
PFAD_BERICHT = AUSGABE / "regression_results" / "frage1_selektionscheck.md"

MONAT_MIN, MONAT_MAX = -12, 42
MIN_VIDEOS_WHITELIST = 5   # Stufe 2 der Whitelist (frage1_stichprobe.py)

DIM_POPULISMUS = ["populismus_gesamt", "antielitismus", "volkszentrismus",
                  "manichaeische_moralisierung", "emotionale_intensitaet"]
DIM_STANCE = ["position_russland", "position_westpolitik"]
GRUPPE5 = ["ÖRR", "Traditionelles Medium", "Alternative Medien (links)",
           "Alternative Medien (mitte)", "Alternative Medien (rechts)"]

POPULATIONEN = {
    "P0 original": lambda d: pd.Series(True, index=d.index),
    "P1 bereinigt": lambda d: (d["duration_seconds"] >= MIN_VIDEO_DURATION_SECONDS)
                              & ((d["ist_kriegsvideo"] == 1) | (d["politics_final"] == 1)),
    "P2 streng": lambda d: (d["duration_seconds"] >= MIN_VIDEO_DURATION_SECONDS)
                           & ((d["ist_kriegsvideo"] == 1)
                              | ((d["politics_final"] == 1) & (d["topic_politics"] == True))),  # noqa: E712
}


# =========================================================
# SCHAETZUNG
# =========================================================

def _fit(daten, formel):
    daten = daten.copy()
    daten["channel_id"] = daten["channel_id"].astype(str)
    if daten["post"].nunique() < 2 or daten["channel_id"].nunique() < 2:
        return None
    m = smf.ols(formel, data=daten).fit(cov_type="cluster", cov_kwds={"groups": daten["channel_id"]})
    # Wegen Kanal-FE tragen nur Kanaele mit Kanal-Monaten vorher UND nachher zu "post" bei
    k_ident = int(daten.groupby("channel_id")["post"].nunique().eq(2).sum())
    return {"b": m.params["post"], "se": m.bse["post"], "p": m.pvalues["post"],
            "n": len(daten), "k": daten["channel_id"].nunique(), "k_ident": k_ident}


def schaetze(df, dim, spez):
    d = df.dropna(subset=[dim])
    d = d[d["rel_monat"].between(MONAT_MIN, MONAT_MAX)]
    if spez == 3:
        d = d[d["ist_kriegsvideo"] == 0]
    schluessel = ["channel_id", "rel_monat"] + (["ist_kriegsvideo"] if spez == 2 else [])
    agg = d.groupby(schluessel, as_index=False)[dim].mean().rename(columns={dim: "y"})
    agg["post"] = (agg["rel_monat"] >= 0).astype(int)
    formel = "y ~ C(channel_id) + post" + (" + ist_kriegsvideo" if spez == 2 else "")
    return _fit(agg, formel)


def sterne(p):
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""


def ergebnis_tabelle(df, dims):
    zeilen = []
    for pop_name, filt in POPULATIONEN.items():
        d = df[filt(df)]
        for dim in dims:
            zeile = {"Population": pop_name, "Dimension": dim}
            for spez, label in [(1, "(1) alle"), (2, "(2) + Kriegskontrolle"), (3, "(3) nur Nichtkrieg")]:
                r = schaetze(d, dim, spez)
                zeile[label] = "–" if r is None else f"{r['b']:+.3f}{sterne(r['p'])} ({r['se']:.3f})"
            r3 = schaetze(d, dim, 3)
            zeile["Kanäle (3)"] = "–" if r3 is None else r3["k"]
            zeilen.append(zeile)
    return pd.DataFrame(zeilen)


def kriegsvideos_a(df, dims):
    """Vergleich A (nur P1): Kriegsvideos nach Kriegsbeginn gegen politische
    Nicht-Kriegsvideos desselben Kanals vor Kriegsbeginn. Kanal-Monat, Kanal-FE, post.
    Gesamt und je gruppe5 (getrennte Schaetzungen)."""
    d = df[POPULATIONEN["P1 bereinigt"](df) & df["rel_monat"].between(MONAT_MIN, MONAT_MAX)]
    d = d[((d["post"] == 1) & (d["ist_kriegsvideo"] == 1)) | ((d["post"] == 0) & (d["ist_kriegsvideo"] == 0))]
    gruppen = [("gesamt", d)] + [(g, d[d["gruppe5"] == g]) for g in GRUPPE5]
    zeilen = []
    for dim in dims:
        zeile = {"Dimension": dim}
        for name, teil in gruppen:
            t = teil.dropna(subset=[dim])
            agg = t.groupby(["channel_id", "rel_monat"], as_index=False)[dim].mean().rename(columns={dim: "y"})
            agg["post"] = (agg["rel_monat"] >= 0).astype(int)
            r = _fit(agg, "y ~ C(channel_id) + post") if len(agg) else None
            zeile[name] = ("–" if r is None else
                           f"{r['b']:+.3f}{sterne(r['p'])} ({r['se']:.3f}) [{r['k_ident']}/{r['k']}]")
        zeilen.append(zeile)
    return pd.DataFrame(zeilen)


def kriegsvideos_c(df, dims, balanciert=False):
    """Vergleich C (nur P1): Entwicklung der Kriegsvideos nach Kriegsbeginn.
    Kanal-Monat-Mittel der Kriegsvideos, Kanal-FE + Dummies fuer Kriegsjahr 2-4
    (Referenz Jahr 1 = rel_monat 0-11). Gesamt und je gruppe5.
    balanciert=True: nur Kanaele mit Kriegsvideos (nicht-NaN in der Dimension)
    in allen vier Kriegsjahren. Dann spiegeln auch die Mittel J1-J4 keine
    Veraenderung der Kanalzusammensetzung mehr wider."""
    d = df[POPULATIONEN["P1 bereinigt"](df) & (df["ist_kriegsvideo"] == 1)
           & df["rel_monat"].between(0, MONAT_MAX)]
    gruppen = [("gesamt", d)] + [(g, d[d["gruppe5"] == g]) for g in GRUPPE5]
    zeilen = []
    for dim in dims:
        for name, teil in gruppen:
            t = teil.dropna(subset=[dim])
            agg = t.groupby(["channel_id", "rel_monat"], as_index=False)[dim].mean().rename(columns={dim: "y"})
            agg["jahr"] = (agg["rel_monat"] // 12 + 1).clip(upper=4)
            if balanciert:
                n_jahre = agg.groupby("channel_id")["jahr"].nunique()
                agg = agg[agg["channel_id"].isin(n_jahre[n_jahre == 4].index)]
            mittel = agg.groupby("jahr")["y"].mean()
            zeile = {"Dimension": dim, "Gruppe": name, "Kanäle": agg["channel_id"].nunique()}
            for j in [1, 2, 3, 4]:
                zeile[f"Mittel J{j}"] = f"{mittel.get(j, np.nan):.3f}"
            if agg["jahr"].nunique() > 1 and agg["channel_id"].nunique() > 1:
                agg["channel_id"] = agg["channel_id"].astype(str)
                m = smf.ols("y ~ C(channel_id) + C(jahr)", data=agg).fit(
                    cov_type="cluster", cov_kwds={"groups": agg["channel_id"]})
                for j in [2, 3, 4]:
                    term = f"C(jahr)[T.{j}]"
                    zeile[f"Δ J{j} vs J1"] = (f"{m.params[term]:+.3f}{sterne(m.pvalues[term])}"
                                              if term in m.params else "–")
            zeilen.append(zeile)
    return pd.DataFrame(zeilen)


def fallzahlen(df):
    zeilen = []
    for pop_name, filt in POPULATIONEN.items():
        d = df[filt(df) & df["rel_monat"].between(MONAT_MIN, MONAT_MAX)]
        nk = d[d["ist_kriegsvideo"] == 0]
        n_je_kanal = d.groupby("channel_id").size()
        beide_seiten = nk.groupby("channel_id")["post"].nunique()
        zeilen.append({
            "Population": pop_name,
            "Videos": len(d),
            "Krieg vor": int(((d["ist_kriegsvideo"] == 1) & (d["post"] == 0)).sum()),
            "Krieg nach": int(((d["ist_kriegsvideo"] == 1) & (d["post"] == 1)).sum()),
            "Nichtkrieg vor": int((nk["post"] == 0).sum()),
            "Nichtkrieg nach": int((nk["post"] == 1).sum()),
            "Kanäle": d["channel_id"].nunique(),
            f"Kanäle ≥{MIN_VIDEOS_WHITELIST} Videos": int((n_je_kanal >= MIN_VIDEOS_WHITELIST).sum()),
            "Kanäle mit Nichtkrieg vor UND nach": int((beide_seiten == 2).sum()),
        })
    return pd.DataFrame(zeilen)


def md_tabelle(df):
    spalten = [str(c) for c in df.columns]
    z = ["| " + " | ".join(spalten) + " |", "|" + "---|" * len(spalten)]
    for _, r in df.iterrows():
        z.append("| " + " | ".join(str(v) for v in r.values) + " |")
    return "\n".join(z)


# =========================================================
# MAIN
# =========================================================

def main():
    df = pd.read_csv(PFAD_VIDEOS, low_memory=False)
    df["topic_politics"] = df["topic_politics"].map({True: True, False: False, "True": True, "False": False})

    merkmale = df[["video_id", "channel_id", "rel_monat", "post", "ist_kriegsvideo",
                   "duration_seconds", "politics_final", "topic_politics", "gruppe5"]]
    pos = pd.read_csv(PFAD_POSITION, usecols=["video_id"] + DIM_STANCE)
    stance = merkmale.merge(pos, on="video_id", how="inner")

    L = ["# AP 1 – Selektionscheck Frage 1: Robustheitstabelle\n",
         "*Erzeugt von `scripts/masterarbeit/ap1_selektionscheck.py`; Diagnose in "
         "`frage1_selektionsdiagnose.md` (gleicher Ordner).*\n",
         "## Methodik-Übersicht\n",
         "- **Vergleich:** Nachkriegseffekt `post` (`rel_monat >= 0`, Fenster "
         f"{MONAT_MIN}…{MONAT_MAX}) innerhalb eines Kanals (Kanal-FE), SE geclustert nach Kanal. "
         "Die Beobachtungseinheit ist der Kanal-Monat (Mittel über Videos) wie in `frage1_populismus_bericht.py`.",
         "- **Spezifikationen:** (1) alle Videos je Kanal-Monat; (2) Zellen Kanal × Monat × "
         "`ist_kriegsvideo` mit Kriegsvideo-Dummy als Kontrolle; (3) nur Nicht-Kriegsvideos.",
         "- **Populationen:**",
         "  - **P0 original:** alle Videos der 279er-Whitelist in `channel_video_populism.csv`.",
         f"  - **P1 bereinigt:** Dauer ≥ {MIN_VIDEO_DURATION_SECONDS} s (`MIN_VIDEO_DURATION_SECONDS`) **und** "
         "(Kriegsvideo **oder** `politics_final == 1`). Nicht-Kriegsvideos stammen damit vorher und nachher "
         "aus demselben Auswahlweg (Screening mit LLM-Politikfilter). Kriegsvideos stammen vorher und nachher "
         "aus der Keyword-Klassifikation, die ebenfalls erst ab 181 s greift.",
         "  - **P2 streng:** P1, Nicht-Kriegsvideos zusätzlich mit YouTube-`topic_categories` = Politics.",
         f"- **Stance:** `channel_video_position.csv`, inner join auf die Videos der Diagnose "
         f"({len(stance):,} Videos mit Stance-Klassifikation). Nicht thematisierte Positionen sind NaN "
         "und fallen je Dimension heraus.",
         "- Signifikanz: * p<0,05, ** p<0,01, *** p<0,001; in Klammern der Cluster-SE.\n",
         "## Fallzahlen\n", md_tabelle(fallzahlen(df)) + "\n",
         "## Populismus\n", md_tabelle(ergebnis_tabelle(df, DIM_POPULISMUS)) + "\n",
         "## Stance (Position)\n",
         "Skala −2…+2 gemäß `POSITION_V1` (`segment_prompts_simple.py`). `position_russland`: "
         "+2 heißt russisches Handeln wird gerechtfertigt. `position_westpolitik`: +2 heißt deutliche "
         "Unterstützung der westlichen Politik, −2 heißt grundsätzliche Ablehnung.\n",
         md_tabelle(ergebnis_tabelle(stance, DIM_STANCE)) + "\n",
         "## Kriegsvideos (nur P1 bereinigt)\n",
         f"Vor Kriegsbeginn gibt es kaum Kriegsvideos ({int(((df['ist_kriegsvideo'] == 1) & (df['post'] == 0) & POPULATIONEN['P1 bereinigt'](df)).sum())} in P1). "
         "Ein direkter Vergleich „Kriegsvideos vorher vs. nachher“ ist deshalb nicht möglich. "
         "Vergleich B (Krieg vs. Nichtkrieg im selben Kanal-Monat nach Kriegsbeginn) ist zurückgestellt: "
         "Dafür fehlen klassifizierte politische Nicht-Kriegsvideos nach Kriegsbeginn.\n",
         "### A. Kriegsvideos nach Kriegsbeginn vs. politische Videos desselben Kanals vorher\n",
         "Stichprobe: vorher nur politische Nicht-Kriegsvideos, nachher nur Kriegsvideos. Kanal-Monat, "
         "Kanal-FE, Koeffizient `post`, je Gruppe getrennt geschätzt. "
         "Die Schätzung trennt nicht zwischen einem Effekt des Kriegs und einem Effekt des Themas: "
         "Sie misst, wie sich der Kanal verändert, wenn er über den Krieg spricht, verglichen mit "
         "seinem politischen Programm vorher.\n",
         "Zellformat: `Koeffizient Sterne (Cluster-SE) [identifizierende Kanäle / alle Kanäle]`. "
         "Identifizierend sind wegen der Kanal-FE nur Kanäle mit Kanal-Monaten vorher **und** nachher; "
         "Kanäle mit nur einer Seite gehen ins Modell ein, tragen aber nichts zum `post`-Koeffizienten bei.\n",
         md_tabelle(kriegsvideos_a(df, DIM_POPULISMUS)) + "\n",
         md_tabelle(kriegsvideos_a(stance, DIM_STANCE)) + "\n",
         "### C. Entwicklung der Kriegsvideos nach Kriegsbeginn (Kriegsjahr 1–4)\n",
         "Nur Kriegsvideos, `rel_monat` 0…42. Jahr 1 = Monate 0–11, Jahr 4 = Monate 36–42. "
         "Mittelwerte über Kanal-Monate. Δ aus einem Modell Kanal-FE + Jahr-Dummies mit Referenz "
         "Jahr 1 und Cluster-SE. Das Δ misst also die Veränderung innerhalb desselben Kanals.\n",
         "#### C1. Alle Kanäle (unbalanciert)\n",
         "Die Mittel J1–J4 enthalten auch Verschiebungen in der Kanalzusammensetzung (welche Kanäle "
         "in welchem Jahr über den Krieg berichten); für die Veränderung innerhalb der Kanäle zählt das Δ. "
         "„Kanäle“ zählt auch Kanäle, die nur in einem Jahr vorkommen und nichts zum Δ beitragen.\n",
         md_tabelle(kriegsvideos_c(df, DIM_POPULISMUS)) + "\n",
         md_tabelle(kriegsvideos_c(stance, DIM_STANCE)) + "\n",
         "#### C2. Balanciertes Panel (nur Kanäle mit Kriegsvideos in allen vier Jahren)\n",
         "Gleiche Rechnung, aber nur Kanäle, die in jedem Kriegsjahr mindestens einen Kanal-Monat mit "
         "Wert in der jeweiligen Dimension haben. Die Mittel J1–J4 sind damit frei von "
         "Zusammensetzungseffekten auf Kanalebene (Gewichtung weiterhin je Kanal-Monat).\n",
         md_tabelle(kriegsvideos_c(df, DIM_POPULISMUS, balanciert=True)) + "\n",
         md_tabelle(kriegsvideos_c(stance, DIM_STANCE, balanciert=True)) + "\n"]

    PFAD_BERICHT.parent.mkdir(parents=True, exist_ok=True)
    PFAD_BERICHT.write_text("\n".join(L), encoding="utf-8")
    print(f"[Bericht] {PFAD_BERICHT}")


if __name__ == "__main__":
    main()

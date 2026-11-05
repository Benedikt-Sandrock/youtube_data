# -*- coding: utf-8 -*-
"""
phasen_grosse_kanaele.py

Einfache Phasen-Tabelle fuer die grossen Kanaele eines Medientyps (Default:
traditionelle Medien), Kontext: `.claude/plans/session_2026-10-27_traditionelle_views.md`
(Frage 2). Gedacht zum schnellen Nachvollziehen, welche Kanaele den
Views-Verlauf in `marktanteil_medientyp_ideologie_kombiniert_long_absolut.png`
tragen.

Datenbasis: `outputs/stata_rohdaten/videos_roh.dta` + `kanaele_roh.dta`.
Kanal-Sample wie in `step6_auswertung/marktanteil_rohdaten_plots.py`
(channels_check.xlsx: media_category in [1, 2, 5], sample == 1, foreign != 1),
abschaltbar ueber KANALLISTE_AUS_CHANNELS_CHECK.

Monat = rel_monat relativ zum Kriegsbeginn (24.02.2022, Monat 0 =
[24.02.2022, 24.03.2022)), wie im Plot-Skript ueber `relativ_periode()`.

Je Phase (PHASEN) und Kanal:
- Views:          Summe der Views aller Videos der Phase / Anzahl Monate der Phase (Mio.)
- Uploads:        Anzahl Videos / Anzahl Monate der Phase
- Median-Views:   Median der Views je Video in der Phase (Tsd.)
- Views/Video:    Mittelwert der Views je Video (Tsd.) - zum Vergleich mit dem Median;
                  liegt der Mittelwert weit darueber, tragen wenige Ausreisser die Phase.
Die N_GROSSE_KANAELE Kanaele mit den meisten Views im Gesamtzeitraum werden
einzeln gezeigt, alle uebrigen als "Rest"; "Summe" = alle Kanaele des Medientyps.

Hinweis: absolute Views juengerer Videos sind wegen der kuerzeren Zeit bis zum
Abruf systematisch niedriger (Alterseffekt, siehe Plot-Skript).

Ausgabe: `scripts/adhoc/outputs/phasen_grosse_kanaele_<medientyp>_<format>.md`

Ausfuehren aus dem Repo-Root (liest videos_roh.dta in Chunks, dauert einige Minuten):
    PYTHONPATH=src .venv/Scripts/python.exe scripts/adhoc/phasen_grosse_kanaele.py
"""

import pandas as pd

from youtube_code.config import OUTPUTS, ROOT, STATA_OUTPUT
from youtube_code.step6_auswertung.prepare_channel_scores import KRIEGSBEGINN, relativ_periode

# =========================================================
# CONFIG
# =========================================================

ROHDATEN_PFAD = OUTPUTS / "stata_rohdaten"
OUT_DIR = ROOT / "scripts" / "adhoc" / "outputs"

# Medientyp wie in kanaele_roh.medientyp: "ÖRR", "traditionelle Medien",
# "Partei/Politiker", "Creator & alternative Medien"
MEDIENTYP = "traditionelle Medien"

# Videoformate (Teilmenge von "long", "short", "live"); Shorts-Views sind ab
# 31.03.2025 anders gezaehlt (Strukturbruch)
FORMAT = ["long"]

# True = Kanal-Sample wie im Marktanteils-Plot (channels_check.xlsx), False = alle
# Kanaele des Medientyps aus kanaele_roh
KANALLISTE_AUS_CHANNELS_CHECK = True

# Anzahl einzeln gezeigter Kanaele (int >= 1), Rangfolge nach Views im Gesamtzeitraum
N_GROSSE_KANAELE = 6

# Phasen als (Name, von, bis) in rel_monat, inklusive, aufsteigend und ohne Ueberlappung.
# Phase A' (Monat -14/-13) entfaellt seit Schliessung der WELT-Datenluecke und ist in A enthalten.
PHASEN = [
    ("A Vorkrieg", -25, -13),
    ("B um Kriegsbeginn", -12, -1),
    ("C Plateau", 0, 16),
    ("D Delle", 17, 26),
    ("E Wiederanstieg", 27, 36),
    ("F", 37, 47),
    ("G", 48, 51),
]

# Zeilen je Chunk beim Lesen von videos_roh.dta (begrenzt den Arbeitsspeicher)
CHUNK_ZEILEN = 500_000


# =========================================================
# Daten laden
# =========================================================

def lade_kanaele():
    k = pd.read_stata(ROHDATEN_PFAD / "kanaele_roh.dta", columns=["channel_id", "kanal_name", "medientyp"])
    k["medientyp"] = k["medientyp"].astype(str)
    k = k[k["medientyp"] == MEDIENTYP]
    if KANALLISTE_AUS_CHANNELS_CHECK:
        cc = pd.read_excel(STATA_OUTPUT / "channels_check.xlsx")
        cc = cc[cc["media_category"].isin([1, 2, 5]) & (cc["sample"] == 1) & (cc["foreign"] != 1)]
        k = k[k["channel_id"].isin(cc["channel_id"])]
    print(f"[Kanaele] {len(k)} Kanaele mit medientyp == {MEDIENTYP!r}")
    return k


def lade_videos(kanal_ids):
    spalten = ["channel_id", "upload_ts", "views", "format"]
    teile = []
    with pd.read_stata(ROHDATEN_PFAD / "videos_roh.dta", columns=spalten, chunksize=CHUNK_ZEILEN) as leser:
        for chunk in leser:
            chunk = chunk[chunk["channel_id"].isin(kanal_ids)
                          & chunk["format"].astype(str).isin(FORMAT)
                          & chunk["views"].notna()]
            teile.append(chunk)
    v = pd.concat(teile, ignore_index=True)
    v["monat"] = relativ_periode(v["upload_ts"], pd.Timestamp(KRIEGSBEGINN), 1)
    print(f"[Videos] {len(v)} Videos (format {FORMAT}, mit views)")
    return v


def ordne_phasen_zu(v):
    v = v.copy()
    v["phase"] = None
    for name, von, bis in PHASEN:
        v.loc[v["monat"].between(von, bis), "phase"] = name
    return v[v["phase"].notna()]


# =========================================================
# Tabellen
# =========================================================

def phasen_tabellen(v, kanal_namen):
    phasen = [p[0] for p in PHASEN]
    monate = pd.Series({name: bis - von + 1 for name, von, bis in PHASEN})

    v = v.assign(kanal=v["channel_id"].map(kanal_namen))
    gross = v.groupby("kanal")["views"].sum().nlargest(N_GROSSE_KANAELE).index.tolist()
    v["spalte"] = v["kanal"].where(v["kanal"].isin(gross), "Rest")
    spalten = gross + ["Rest"]

    def je_phase(werte, agg):
        t = werte.groupby(["phase", "spalte"])["views"].agg(agg).unstack()
        t["Summe"] = werte.groupby("phase")["views"].agg(agg)
        return t.reindex(index=phasen, columns=spalten + ["Summe"])

    views = je_phase(v, "sum").fillna(0).div(monate, axis=0) / 1e6
    uploads = je_phase(v, "size").fillna(0).div(monate, axis=0)
    median = je_phase(v, "median") / 1e3
    mittel = je_phase(v, "mean") / 1e3
    return {
        "Views (Mio. je Monat)": views.round(1),
        "Uploads (je Monat)": uploads.round(0),
        "Median-Views je Video (Tsd.)": median.round(1),
        "Mittlere Views je Video (Tsd.)": mittel.round(1),
    }


def als_markdown(t):
    kopf = "| Phase | " + " | ".join(t.columns) + " |"
    trenner = "|---|" + "---:|" * len(t.columns)
    zeilen = [f"| {idx} | " + " | ".join("" if pd.isna(x) else f"{x:g}" for x in row) + " |"
              for idx, row in t.iterrows()]
    return "\n".join([kopf, trenner, *zeilen])


# =========================================================
# Main
# =========================================================

def main():
    erlaubt_format = {"long", "short", "live"}
    if not FORMAT or not set(FORMAT) <= erlaubt_format:
        raise SystemExit(f"FORMAT muss eine nicht-leere Teilmenge von {sorted(erlaubt_format)} sein.")
    if not isinstance(N_GROSSE_KANAELE, int) or N_GROSSE_KANAELE < 1:
        raise SystemExit("N_GROSSE_KANAELE muss eine ganze Zahl >= 1 sein.")
    for (_, von, bis), (_, von2, _) in zip(PHASEN, PHASEN[1:] + [("", 10**6, 0)]):
        if not von <= bis < von2:
            raise SystemExit("PHASEN muessen aufsteigend sein, von <= bis, ohne Ueberlappung.")

    k = lade_kanaele()
    if k.empty:
        raise SystemExit(f"Keine Kanaele mit medientyp == {MEDIENTYP!r} gefunden.")
    v = ordne_phasen_zu(lade_videos(set(k["channel_id"])))
    tabellen = phasen_tabellen(v, k.set_index("channel_id")["kanal_name"].astype(str))

    phasen_text = ", ".join(f"{n} = Monat {a}..{b}" for n, a, b in PHASEN)
    teile = [
        f"# Phasen-Tabelle grosse Kanaele: {MEDIENTYP}, format {'+'.join(FORMAT)}",
        "",
        f"Erzeugt von `scripts/adhoc/phasen_grosse_kanaele.py` am {pd.Timestamp.now():%d.%m.%Y %H:%M}. "
        f"{k['channel_id'].nunique()} Kanaele, {len(v)} Videos in den Phasen. "
        f"Kanal-Sample: {'channels_check.xlsx (wie Marktanteils-Plot)' if KANALLISTE_AUS_CHANNELS_CHECK else 'alle Kanaele des Medientyps'}.",
        "",
        f"Phasen ({phasen_text}); Monat 0 beginnt am {KRIEGSBEGINN}. "
        "Views und Uploads sind Phasensummen geteilt durch die Zahl der Monate der Phase. "
        f"Einzeln gezeigt: die {N_GROSSE_KANAELE} Kanaele mit den meisten Views im Gesamtzeitraum.",
    ]
    for titel, t in tabellen.items():
        teile += ["", f"## {titel}", "", als_markdown(t)]
        print(f"\n{titel}\n{t.to_string()}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    datei = OUT_DIR / f"phasen_grosse_kanaele_{MEDIENTYP.split()[0].lower()}_{'_'.join(FORMAT)}.md"
    datei.write_text("\n".join(teile) + "\n", encoding="utf-8")
    print(f"\n[Ausgabe] {datei}")


if __name__ == "__main__":
    main()

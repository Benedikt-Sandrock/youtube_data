"""Marktanteils-Grafiken (marktanteil_rohdaten_plots.py) fuer mehrere Kanalauswahlen
aus channels_check.xlsx (Spalte "sample", Codes siehe Blatt "Codebuch") nacheinander.

Je Variante wird KANALLISTE des Hauptskripts ueberschrieben und die Ausgabe in einen
eigenen Unterordner von PFAD_PLOTS / "sample_varianten" geschrieben. Zusaetzlich
entsteht dort vergleich_sample_varianten<zusatz>.md mit den Phasenmitteln der Views-Anteile
(Medientyp x Ideologie, Sample "alle Kanaele") je Variante und Umfang.
Alle anderen Einstellungen kommen aus dem Config-Block des Hauptskripts; gelesene und
geschriebene Dateien tragen dessen Zusatz <zusatz> (m.datei_zusatz(): _manuell bei
MANUELL_ALT_RECHTS, _oerrdoku bei OERR_DOKU_CODES). Bei OERR_DOKU_CODES muss jede
Variante mindestens einen dieser Codes enthalten.
"""
import pandas as pd

import youtube_code.step6_auswertung.marktanteil_rohdaten_plots as m

# =========================================================
# CONFIG
# =========================================================

# Varianten: {Name: Liste der sample-Codes}; Codes 0-5, je Liste nicht leer
VARIANTEN = {"s1": [1], "s1_2": [1, 2], "s1_3": [1, 3], "s1_2_5": [1,2,5]}
# Medienkategorien (media_category) wie im Hauptskript
KATEGORIEN = [1, 2, 5]
# Zusaetzliche Umfaenge je Lauf (Schluessel aus m.UMFAENGE ausser "alle"; leer = nur alle Videos)
UMFANG_ZUSATZ = ["politisch"]
# Phasen (rel_monat, inklusive) fuer die Vergleichstabelle
PHASEN = {"Vorkrieg (-25 bis -1)": (-25, -1), "Jahr 1 (0 bis 11)": (0, 11),
          "Jahr 2-3 (12 bis 35)": (12, 35), "Jahr 4+ (36 bis 51)": (36, 51)}

# =========================================================
# CONFIG ENDE
# =========================================================

ZIEL = m.PFAD_PLOTS / "sample_varianten"


def kanalliste(codes):
    cc = pd.read_excel(m.STATA_OUTPUT / "channels_check.xlsx")
    cc = cc[cc["media_category"].isin(KATEGORIEN) & cc["sample"].isin(codes) & (cc["foreign"] != 1)]
    return cc["channel_id"].tolist()


def main():
    for name, codes in VARIANTEN.items():
        if not codes or not set(codes) <= {0, 1, 2, 3, 4, 5}:
            raise SystemExit(f"VARIANTEN[{name!r}] muss eine nicht leere Liste von Codes 0-5 sein.")
    falsch = [u for u in UMFANG_ZUSATZ if u not in m.UMFAENGE or u == "alle"]
    if falsch:
        raise SystemExit(f"UMFANG_ZUSATZ enthaelt ungueltige Umfaenge {falsch}.")
    ohne = [n for n, c in VARIANTEN.items() if m.OERR_DOKU_CODES and not set(c) & set(m.OERR_DOKU_CODES)]
    if ohne:
        raise SystemExit(f"OERR_DOKU_CODES = {m.OERR_DOKU_CODES} im Hauptskript, aber die Varianten {ohne} "
                         "enthalten keinen dieser Codes; Varianten anpassen oder OERR_DOKU_CODES = [].")

    zeilen = []
    for name, codes in VARIANTEN.items():
        m.KANALLISTE = kanalliste(codes)
        m.UMFANG_ZUSATZ = UMFANG_ZUSATZ
        m.PFAD_PLOTS = ZIEL / name
        print(f"\n===== Variante {name}: sample in {codes}, {len(m.KANALLISTE)} Kanaele =====")
        m.main()
        csv = pd.read_csv(m.PFAD_PLOTS / f"marktanteil_{m.periode_name()}{m.datei_zusatz()}.csv")
        zeilen.append(csv.assign(variante=name))

    vergleich()


def phase_von(rel):
    for name, (von, bis) in PHASEN.items():
        if von <= rel <= bis:
            return name
    return None


def md_tabelle(t):
    """DataFrame mit MultiIndex-Zeilen -> Markdown-Tabelle (ohne tabulate)."""
    kopf = [*t.index.names, *t.columns]
    zeilen = ["| " + " | ".join(map(str, kopf)) + " |", "|" + "---|" * len(kopf)]
    for idx, r in t.iterrows():
        idx = idx if isinstance(idx, tuple) else (idx,)
        zeilen.append("| " + " | ".join([*map(str, idx), *(f"{x:.1f}" for x in r)]) + " |")
    return "\n".join(zeilen)


def phasen_tabelle(d, wert, zeilen_spalten):
    d = d.assign(phase=d["rel_monat"].map(phase_von)).dropna(subset=["phase"])
    t = d.groupby([*zeilen_spalten, "phase"])[wert].mean().unstack("phase")[list(PHASEN)]
    t["Δ Jahr 4+ − Vorkrieg"] = t[list(PHASEN)[-1]] - t[list(PHASEN)[0]]
    return t.round(1)


def vergleich():
    """Phasenmittel der Views-Anteile je Variante -> vergleich_sample_varianten.md."""
    teile_m, teile_k = [], []
    for name in VARIANTEN:
        z = m.periode_name() + m.datei_zusatz()
        teile_m.append(pd.read_csv(ZIEL / name / f"marktanteil_{z}.csv").assign(variante=name))
        teile_k.append(pd.read_csv(ZIEL / name / f"kanalindex_{z}.csv").assign(variante=name))
    dm = pd.concat(teile_m)
    dm = dm[dm["klassifikation"] == "medientyp_ideologie"]
    dk = pd.concat(teile_k)
    dk = dk[dk["klassifikation"] == "medientyp_ideologie"]

    out = ["# Marktanteile nach Kanalauswahl (channels_check.xlsx, Spalte sample)", "",
           f"Erzeugt von `scripts/adhoc/marktanteil_sample_varianten.py`. Varianten: "
           + ", ".join(f"`{n}` = sample ∈ {c}" for n, c in VARIANTEN.items())
           + f". Format {m.FORMAT}, Kategorien {KATEGORIEN}, foreign ≠ 1. "
           "Werte: Mittel der Monatsanteile (Views, %) je Phase.", ""]
    for umfang in dm["umfang"].unique():
        for sample in dm["sample"].unique():
            t = phasen_tabelle(dm[(dm["umfang"] == umfang) & (dm["sample"] == sample)], "anteil",
                               ["gruppe", "variante"])
            out += [f"## Views-Anteil gepoolt – Umfang `{umfang}`, Sample `{sample}`", "",
                    md_tabelle(t), ""]
    for w in ["anteil_linear", "anteil_wurzel", "anteil_gleich"]:
        t = phasen_tabelle(dk, w, ["gruppe", "variante"])
        out += [f"## Kanalindex `{w}` (Basis-Kanäle, alle Videos)", "", md_tabelle(t), ""]
    ziel = ZIEL / f"vergleich_sample_varianten{m.datei_zusatz()}.md"
    ziel.write_text("\n".join(out), encoding="utf-8")
    print(f"[Vergleich] {ziel}")


if __name__ == "__main__":
    main()

"""
pruefung_codierung.py
=====================

Prueft Codierungen der Angebotsstudie gegen die Regeln des Codebuchs
(codebuch_angebotsstudie_v1.md, Version 1.3) und berechnet - bei zwei unabhaengigen
Codierungen derselben Segmente - die Uebereinstimmung je Feld.

    python pruefung_codierung.py

Uebereinstimmung:
    - Skalare Felder: Krippendorffs Alpha (nominal fuer Kategorien, ordinal
      fuer Skalen) ueber alle Segmente, in denen beide Codierungen einen
      Wert haben, plus prozentuale Uebereinstimmung.
    - Listen-Felder: je Kategorie ein 0/1-Indikator, Alpha nominal je
      Kategorie (nur Kategorien mit mind. MIN_POSITIV Nennungen).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

import pandas as pd

# ============================================================
# CONFIG
# ============================================================

BASIS = Path(__file__).resolve().parent
DATEI_A = BASIS / "angebot" / "pilot_codierung_a.jsonl"
DATEI_B = BASIS / "angebot" / "pilot_codierung_b.jsonl"   # None = nur Regelpruefung
BERICHT = BASIS / "angebot" / "pilot_uebereinstimmung.csv"
MIN_POSITIV = 5

# ============================================================
# Codebuch-Regeln
# ============================================================

FELDER = [
    "segment_id", "kodierbar", "redeform", "fremdrede_dominant",
    "themen", "hauptthema", "krieg_bezug", "krieg_aspekte",
    "volkszentrismus", "antielitismus", "manichaeische_moralisierung", "emotionale_intensitaet",
    "rus_status", "rus_score", "west_status", "west_score",
    "estab_status", "estab_ziel", "estab_explizit", "estab_score", "estab_gegenstand",
    "estab_kritik_richtung", "estab_intensitaet", "estab_urheber",
    "folgen_verantwortung", "medienkritik",
]

THEMEN = ["krieg_ukraine", "corona", "migration", "wirtschaft", "energie", "klima", "gender",
          "nahost", "iran", "eu", "usa", "bildung", "innenpolitik_sonstige",
          "sonstiges_politisch", "unpolitisch"]
ENUM_LISTE = {
    "themen": THEMEN,
    "krieg_aspekte": ["kriegsgeschehen_militaer", "kriegsverbrechen_zivilisten",
                      "verhandlungen_diplomatie", "waffenlieferungen", "sanktionen", "finanzhilfe",
                      "nato_eu_beitritt", "truppen_einsatz", "gefluechtete", "energie_preise_inland",
                      "bundeswehr_sondervermoegen", "russland_innen", "medien_desinformation", "wirtschaft_inland",
                      "sonstiges"],
    "estab_ziel": ["bundesregierung", "sonstiges_establishment"],
    "estab_gegenstand": ["kriegspolitik", "kriegsfolgen_inland", "corona", "migration",
                       "wirtschaft_soziales", "energie_klima", "gesellschaft_kultur",
                       "kompetenz_fuehrung_kommunikation", "sonstiges"],
    "folgen_verantwortung": ["russland", "establishment", "eu_westen_sanktionen", "ukraine",
                             "andere"],
    "medienkritik": ["etablierte_medien", "alternative_medien", "russische_staatsmedien",
                     "soziale_medien_plattformen"],
}
STATUS = ["nicht_thematisiert", "deskriptiv", "bewertend"]
ENUM_SKALAR = {
    "redeform": ["monolog", "gespraech", "beitrag", "unklar"],
    "hauptthema": THEMEN,
    "krieg_bezug": ["explizit", "implizit"],
    "rus_status": STATUS, "west_status": STATUS, "estab_status": STATUS,
    "estab_explizit": ["explizit", "implizit"],
    "estab_kritik_richtung": ["zu_zoegerlich", "zu_weitgehend", "sonstige"],
    "estab_urheber": ["kanal", "fremdrede", "beides", "unklar"],
}
BOOL = ["kodierbar", "fremdrede_dominant"]
SKALEN = {
    "volkszentrismus": (0, 3), "antielitismus": (0, 3),
    "manichaeische_moralisierung": (0, 3), "emotionale_intensitaet": (0, 3),
    "rus_score": (-2, 2), "west_score": (-2, 2), "estab_score": (-2, 2),
    "estab_intensitaet": (0, 2),
}
POPULISMUS = ["volkszentrismus", "antielitismus", "manichaeische_moralisierung",
              "emotionale_intensitaet"]


def pruefe_zeile(z: dict) -> list[str]:
    f = []
    if list(z.keys()) != FELDER:
        fehlend = [k for k in FELDER if k not in z]
        extra = [k for k in z if k not in FELDER]
        if fehlend or extra:
            return [f"Felder fehlen {fehlend} / zusaetzlich {extra}"]
        f.append("Feldreihenfolge abweichend")

    for k in BOOL:
        if not isinstance(z[k], bool):
            f.append(f"{k} kein bool")
    for k, erlaubt in ENUM_SKALAR.items():
        if z[k] is not None and z[k] not in erlaubt:
            f.append(f"{k}={z[k]!r} unzulaessig")
    for k, (lo, hi) in SKALEN.items():
        v = z[k]
        if v is not None and (not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi):
            f.append(f"{k}={v!r} ausserhalb [{lo},{hi}]")
    for k, erlaubt in ENUM_LISTE.items():
        v = z[k]
        if k == "folgen_verantwortung" and v is None:
            continue
        if not isinstance(v, list):
            f.append(f"{k} keine Liste")
            continue
        bad = [x for x in v if x not in erlaubt]
        if bad:
            f.append(f"{k} unzulaessige Werte {bad}")
        if len(set(v)) != len(v):
            f.append(f"{k} doppelte Werte")

    if z["kodierbar"] is False:
        for k in FELDER[4:]:
            v = z[k]
            if v not in (None, []):
                f.append(f"kodierbar=false, aber {k}={v!r}")
        return f

    themen = z["themen"] if isinstance(z["themen"], list) else []
    if not themen:
        f.append("kodierbar=true, aber themen leer")
    if z["hauptthema"] not in themen:
        f.append("hauptthema nicht in themen")
    if "unpolitisch" in themen and len(themen) > 1:
        f.append("unpolitisch nicht allein")
    for k in POPULISMUS:
        if z[k] is None:
            f.append(f"{k} fehlt bei kodierbar=true")

    krieg = "krieg_ukraine" in themen
    if not krieg:
        if z["krieg_aspekte"]:
            f.append("krieg_aspekte ohne krieg_ukraine")
        if z["krieg_bezug"] is not None:
            f.append("krieg_bezug ohne krieg_ukraine")
        for k in ["rus_status", "rus_score", "west_status", "west_score"]:
            if z[k] is not None:
                f.append(f"{k} gesetzt ohne krieg_ukraine")
    else:
        if z["krieg_bezug"] is None:
            f.append("krieg_bezug fehlt bei krieg_ukraine")
        for s in ["rus_status", "west_status"]:
            if z[s] is None:
                f.append(f"{s} fehlt bei krieg_ukraine")
    for s, sc in [("rus_status", "rus_score"), ("west_status", "west_score"),
                  ("estab_status", "estab_score")]:
        if (z[s] == "bewertend") != (z[sc] is not None):
            f.append(f"{sc} inkonsistent zu {s}={z[s]}")

    if z["estab_status"] is None:
        f.append("estab_status fehlt bei kodierbar=true")
    if z["estab_ziel"] and z["estab_status"] not in ("deskriptiv", "bewertend"):
        f.append("estab_ziel ohne Thematisierung")
    if z["estab_status"] in ("deskriptiv", "bewertend") and not z["estab_ziel"]:
        f.append("estab_ziel leer trotz Thematisierung")
    bew = z["estab_status"] == "bewertend"
    if bool(z["estab_gegenstand"]) != bew:
        f.append("estab_gegenstand inkonsistent zu estab_status")
    if (z["estab_urheber"] is not None) != bew:
        f.append("estab_urheber inkonsistent zu estab_status")
    if (z["estab_explizit"] is not None) != bew:
        f.append("estab_explizit inkonsistent zu estab_status")
    neg = isinstance(z["estab_score"], int) and z["estab_score"] < 0
    if (z["estab_intensitaet"] is not None) != neg:
        f.append("estab_intensitaet inkonsistent zu estab_score")
    soll_richtung = neg and "kriegspolitik" in (z["estab_gegenstand"] or [])
    if (z["estab_kritik_richtung"] is not None) != soll_richtung:
        f.append("estab_kritik_richtung inkonsistent")
    return f


def lade(pfad: Path) -> pd.DataFrame:
    zeilen, fehler = [], []
    with open(pfad, encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                z = json.loads(line, object_pairs_hook=dict)
            except json.JSONDecodeError as e:
                fehler.append((f"Zeile {i}", f"kein JSON: {e}"))
                continue
            for m in pruefe_zeile(z):
                fehler.append((z.get("segment_id", f"Zeile {i}"), m))
            zeilen.append(z)
    df = pd.DataFrame(zeilen)
    print(f"[Pruefung] {pfad.name}: {len(df)} Zeilen, {len(fehler)} Regelverstoesse")
    for sid, m in fehler[:40]:
        print(f"    {sid}: {m}")
    if df["segment_id"].duplicated().any():
        print("[Pruefung] WARNUNG: doppelte segment_id")
    return df


# ============================================================
# Krippendorffs Alpha (zwei Codierende, keine fehlenden Paare)
# ============================================================

def krippendorff_alpha(paare: list[tuple], metrik: str = "nominal") -> float | None:
    if len(paare) < 2:
        return None
    werte = sorted({v for p in paare for v in p})
    if len(werte) < 2:
        return None
    # Koinzidenzmatrix
    o = Counter()
    for a, b in paare:
        o[(a, b)] += 1
        o[(b, a)] += 1
    n_c = Counter()
    for (c, _), cnt in o.items():
        n_c[c] += cnt
    n = sum(n_c.values())

    if metrik == "nominal":
        def d(c, k):
            return 0.0 if c == k else 1.0
    elif metrik == "ordinal":
        rang = {v: i for i, v in enumerate(werte)}

        def d(c, k):
            lo, hi = sorted((rang[c], rang[k]))
            s = sum(n_c[werte[g]] for g in range(lo, hi + 1)) - (n_c[c] + n_c[k]) / 2
            return s ** 2
    else:
        raise ValueError(metrik)

    D_o = sum(cnt * d(c, k) for (c, k), cnt in o.items()) / n
    D_e = sum(n_c[c] * n_c[k] * d(c, k) for c in werte for k in werte) / (n * (n - 1))
    if D_e == 0:
        return None
    return 1 - D_o / D_e


def uebereinstimmung(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    m = a.merge(b, on="segment_id", suffixes=("_a", "_b"))
    print(f"\n[Uebereinstimmung] {len(m)} gemeinsame Segmente")
    zeilen = []

    def zeile(feld, paare, metrik, kategorie=""):
        if not paare:
            return
        prozent = sum(x == y for x, y in paare) / len(paare)
        alpha = krippendorff_alpha(paare, metrik)
        zeilen.append({"feld": feld, "kategorie": kategorie, "metrik": metrik,
                       "n": len(paare), "prozent": round(prozent, 3),
                       "alpha": None if alpha is None else round(alpha, 3)})

    skalar = (["kodierbar", "redeform", "fremdrede_dominant", "hauptthema", "krieg_bezug"]
              + ["rus_status", "west_status", "estab_status", "estab_explizit",
                 "estab_kritik_richtung", "estab_urheber"])
    for f in skalar:
        p = [(x, y) for x, y in zip(m[f + "_a"], m[f + "_b"]) if x is not None and y is not None]
        zeile(f, [(str(x), str(y)) for x, y in p], "nominal")
    for f in SKALEN:
        p = [(int(x), int(y)) for x, y in zip(m[f + "_a"], m[f + "_b"])
             if x is not None and y is not None and not pd.isna(x) and not pd.isna(y)]
        zeile(f, p, "ordinal")
    for f, kats in ENUM_LISTE.items():
        for k in kats:
            p = []
            for x, y in zip(m[f + "_a"], m[f + "_b"]):
                if x is None or y is None:   # folgen_verantwortung null
                    continue
                p.append((int(k in x), int(k in y)))
            if sum(u + v for u, v in p) >= MIN_POSITIV:
                zeile(f, p, "nominal", k)
    # folgen_verantwortung: Thematisierung ja/nein
    p = [(int(x is not None), int(y is not None))
         for x, y in zip(m["folgen_verantwortung_a"], m["folgen_verantwortung_b"])]
    zeile("folgen_verantwortung", p, "nominal", "(thematisiert)")
    return pd.DataFrame(zeilen)


def main() -> None:
    a = lade(DATEI_A)
    if DATEI_B is None or not DATEI_B.exists():
        return
    b = lade(DATEI_B)
    bericht = uebereinstimmung(a, b)
    bericht.to_csv(BERICHT, index=False, encoding="utf-8-sig")
    pd.set_option("display.width", 160)
    print(bericht.to_string(index=False))
    print(f"\n[Uebereinstimmung] Bericht: {BERICHT}")


if __name__ == "__main__":
    main()

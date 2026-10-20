"""
pruefung_v2.py
==============

Regelpruefung fuer Codierungen nach Codebuch 2.0 (codebuch_angebotsstudie_v2.md).
Wird von status_codierlauf.py importiert; kann auch direkt eine Datei pruefen:

    python pruefung_v2.py      (prueft DATEI aus dem CONFIG-Block)
"""

from __future__ import annotations

import json
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================

BASIS = Path(__file__).resolve().parent
DATEI = BASIS / "angebot" / "codierung_gesamt.jsonl"

# ============================================================
# Codebuch 2.0
# ============================================================

FELDER = [
    "segment_id", "kodierbar", "themen", "hauptthema", "krieg_bezug", "krieg_aspekte",
    "rus_status", "rus_score",
    "estab_status", "estab_explizit", "estab_score", "estab_gegenstand",
    "estab_kritik_richtung", "estab_intensitaet",
]
THEMEN = ["krieg_ukraine", "corona", "migration", "wirtschaft", "energie", "klima", "gender",
          "nahost", "iran", "eu", "usa", "bildung", "innenpolitik_sonstige",
          "sonstiges_politisch", "unpolitisch"]
LISTEN = {
    "themen": THEMEN,
    "krieg_aspekte": ["kriegsgeschehen_militaer", "kriegsverbrechen_zivilisten",
                      "verhandlungen_diplomatie", "waffenlieferungen", "sanktionen", "finanzhilfe",
                      "nato_eu_beitritt", "truppen_einsatz", "gefluechtete", "energie_preise_inland",
                      "wirtschaft_inland", "bundeswehr_sondervermoegen", "russland_innen",
                      "medien_desinformation", "sonstiges"],
    "estab_gegenstand": ["kriegspolitik", "kriegsfolgen_inland", "corona", "migration",
                         "wirtschaft_soziales", "energie_klima", "gesellschaft_kultur",
                         "kompetenz_fuehrung_kommunikation", "sonstiges"],
}
STATUS = ["nicht_thematisiert", "deskriptiv", "bewertend"]
SKALAR = {
    "hauptthema": THEMEN,
    "krieg_bezug": ["explizit", "implizit"],
    "rus_status": STATUS,
    "estab_status": STATUS,
    "estab_explizit": ["explizit", "implizit"],
    "estab_kritik_richtung": ["zu_zoegerlich", "zu_weitgehend", "sonstige"],
}
SKALEN = {"rus_score": (-2, 2), "estab_score": (-2, 2), "estab_intensitaet": (0, 2)}


def pruefe_zeile(z: dict) -> list[str]:
    f: list[str] = []
    fehlend = [k for k in FELDER if k not in z]
    extra = [k for k in z if k not in FELDER]
    if fehlend or extra:
        return [f"Felder fehlen {fehlend} / zusaetzlich {extra}"]

    if not isinstance(z["kodierbar"], bool):
        f.append("kodierbar kein bool")
    for k, erlaubt in SKALAR.items():
        if z[k] is not None and z[k] not in erlaubt:
            f.append(f"{k}={z[k]!r} unzulaessig")
    for k, (lo, hi) in SKALEN.items():
        v = z[k]
        if v is not None and (not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi):
            f.append(f"{k}={v!r} ausserhalb [{lo},{hi}]")
    for k, erlaubt in LISTEN.items():
        v = z[k]
        if not isinstance(v, list):
            f.append(f"{k} keine Liste")
            continue
        bad = [x for x in v if x not in erlaubt]
        if bad:
            f.append(f"{k} unzulaessige Werte {bad}")

    if z["kodierbar"] is False:
        for k in FELDER[2:]:
            if z[k] not in (None, []):
                f.append(f"kodierbar=false, aber {k}={z[k]!r}")
        return f

    themen = z["themen"] if isinstance(z["themen"], list) else []
    if not themen:
        f.append("themen leer")
    if z["hauptthema"] not in themen:
        f.append("hauptthema nicht in themen")
    if "unpolitisch" in themen and len(themen) > 1:
        f.append("unpolitisch nicht allein")

    if "krieg_ukraine" in themen:
        for k in ["krieg_bezug", "rus_status"]:
            if z[k] is None:
                f.append(f"{k} fehlt bei krieg_ukraine")
    else:
        for k in ["krieg_bezug", "rus_status", "rus_score"]:
            if z[k] is not None:
                f.append(f"{k} gesetzt ohne krieg_ukraine")
        if z["krieg_aspekte"]:
            f.append("krieg_aspekte ohne krieg_ukraine")
    if (z["rus_status"] == "bewertend") != (z["rus_score"] is not None):
        f.append("rus_score inkonsistent zu rus_status")

    if z["estab_status"] is None:
        f.append("estab_status fehlt")
    bew = z["estab_status"] == "bewertend"
    if (z["estab_score"] is not None) != bew:
        f.append("estab_score inkonsistent zu estab_status")
    if (z["estab_explizit"] is not None) != bew:
        f.append("estab_explizit inkonsistent zu estab_status")
    if bool(z["estab_gegenstand"]) != bew:
        f.append("estab_gegenstand inkonsistent zu estab_status")
    neg = isinstance(z["estab_score"], int) and z["estab_score"] < 0
    if (z["estab_intensitaet"] is not None) != neg:
        f.append("estab_intensitaet inkonsistent zu estab_score")
    soll = neg and "kriegspolitik" in (z["estab_gegenstand"] or [])
    if (z["estab_kritik_richtung"] is not None) != soll:
        f.append("estab_kritik_richtung inkonsistent")
    return f


def main() -> None:
    n, fehler = 0, 0
    with open(DATEI, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            z = json.loads(line)
            n += 1
            for m in pruefe_zeile(z):
                fehler += 1
                print(f"    {z.get('segment_id')}: {m}")
    print(f"[Pruefung] {DATEI.name}: {n} Zeilen, {fehler} Regelverstoesse")


if __name__ == "__main__":
    main()

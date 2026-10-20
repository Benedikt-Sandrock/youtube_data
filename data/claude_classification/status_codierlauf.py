"""
status_codierlauf.py
====================

Zeigt den Stand des Codierlaufs und prueft alle fertigen Batches gegen die
Regeln von Codebuch 2.0 (pruefung_v2.py).

    python status_codierlauf.py

Erwartete Struktur:
    angebot/batches/batch_XXXX.txt       Eingabe (aus ziehung_angebotsstudie.py)
    angebot/codierung/batch_XXXX.jsonl   Ausgabe des Codierlaufs (gleiche Nummer)
    angebot/codierung_messlauf_v13.jsonl bereits codierte Segmente aus dem
                                         Messlauf (Codebuch 1.3, auf 2.0 reduziert)

Ausgabe:
    - Batches gesamt / fertig / offen (+ naechste offene Batchnummern)
    - je fertigem Batch mit Problemen: fehlende/zusaetzliche segment_ids,
      Regelverstoesse
    - angebot/codierung_gesamt.jsonl: Messlauf + alle fehlerfreien Batches,
      je Zeile ergaenzt um "codebuch" (Version) und "batch"
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================

BASIS = Path(__file__).resolve().parent
BATCH_DIR = BASIS / "angebot" / "batches"
CODIER_DIR = BASIS / "angebot" / "codierung"
MESSLAUF = BASIS / "angebot" / "codierung_messlauf_v13.jsonl"
GESAMT = BASIS / "angebot" / "codierung_gesamt.jsonl"
N_OFFEN_ANZEIGEN = 10

_spec = importlib.util.spec_from_file_location("pruefung_v2", BASIS / "pruefung_v2.py")
pruefung = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pruefung)

_ID = re.compile(r"^### SEGMENT (\S+)\s*$")


def soll_ids(pfad: Path) -> list[str]:
    with open(pfad, encoding="utf-8") as fh:
        return [m.group(1) for l in fh if (m := _ID.match(l))]


def main() -> None:
    CODIER_DIR.mkdir(parents=True, exist_ok=True)
    eingaben = sorted(BATCH_DIR.glob("batch_*.txt"))
    fertig, offen, fehlerhaft, gut = [], [], [], []

    for e in eingaben:
        a = CODIER_DIR / (e.stem + ".jsonl")
        if not a.exists():
            offen.append(e.stem)
            continue
        fertig.append(e.stem)
        soll = soll_ids(e)
        zeilen, probleme = [], []
        with open(a, encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                if not line.strip():
                    continue
                try:
                    z = json.loads(line)
                except json.JSONDecodeError:
                    probleme.append(f"Zeile {i}: kein JSON")
                    continue
                probleme += [f"{z.get('segment_id')}: {m}" for m in pruefung.pruefe_zeile(z)]
                zeilen.append(z)
        ist = [z.get("segment_id") for z in zeilen]
        fehlt, extra = set(soll) - set(ist), set(ist) - set(soll)
        if fehlt:
            probleme.append(f"{len(fehlt)} segment_ids fehlen")
        if extra:
            probleme.append(f"{len(extra)} unbekannte segment_ids")
        if len(ist) != len(set(ist)):
            probleme.append("doppelte segment_ids")
        if probleme:
            fehlerhaft.append((e.stem, probleme))
        else:
            gut.extend({**z, "codebuch": "2.0", "batch": e.stem} for z in zeilen)

    mess = []
    if MESSLAUF.exists():
        with open(MESSLAUF, encoding="utf-8") as fh:
            mess = [{**json.loads(l), "codebuch": "1.3", "batch": "messlauf"} for l in fh if l.strip()]

    print(f"[Status] Batches gesamt: {len(eingaben)} | fertig: {len(fertig)} | offen: {len(offen)}")
    if offen:
        print(f"[Status] Naechste offene: {', '.join(offen[:N_OFFEN_ANZEIGEN])}")
    if fehlerhaft:
        print(f"[Status] {len(fehlerhaft)} fertige Batches mit Problemen (nicht zusammengefuehrt):")
        for name, probs in fehlerhaft:
            print(f"    {name}: {len(probs)} Probleme, z. B. {probs[:3]}")
    with open(GESAMT, "w", encoding="utf-8") as fh:
        for z in mess + gut:
            fh.write(json.dumps(z, ensure_ascii=False) + "\n")
    print(f"[Status] {len(mess) + len(gut):,} Segmente in {GESAMT.name} "
          f"(davon {len(mess)} aus dem Messlauf)")


if __name__ == "__main__":
    main()

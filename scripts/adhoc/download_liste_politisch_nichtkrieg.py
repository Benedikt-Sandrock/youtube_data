# -*- coding: utf-8 -*-
"""
download_liste_politisch_nichtkrieg.py

Erstellt zwei Download-Listen (Format fuer VIDEO_LIST in
step4_transcript_download/download_transcripts.py: JSON-Liste von
{"video_id", "channel_id"}-Dicts) mit politischen Nicht-Kriegsvideos der
Frage-1-Whitelist, damit in Kanal-Monats-Zellen mit Kriegsvideo-Transkripten
ein Vergleich Krieg vs. politisch-nicht-Krieg innerhalb derselben Zelle
moeglich wird. Folgeschritt zu abdeckung_politisch_nichtkrieg_transkripte.py
(Definitionen von "politisch", "Kriegsvideo", Mindestdauer und Kanal-Monat
werden von dort uebernommen).

  - Liste 1: Zellen mit >= 3 Kriegsvideos MIT Transkript
  - Liste 2: alle weiteren Zellen mit >= 1 Kriegsvideo mit Transkript (also 1-2)

Je Zelle werden bis zu ZIEL_PRO_ZELLE (3) politische Nicht-Kriegsvideos
angestrebt. Bereits vorhandene Transkripte (has_transcript()) zaehlen gegen die
Quote; nur der fehlende Rest wird zufaellig (SEED) aus den Kandidaten gezogen,
fuer die noch kein Download-Versuch vorliegt (attempted_video_ids()). Videos mit
fehlgeschlagenem frueheren Versuch werden nicht erneut gezogen. Die Reihenfolge
innerhalb jeder Liste wird ebenfalls zufaellig gemischt, damit ein
abgebrochener Download keine Kanaele/Zeitraeume systematisch bevorzugt.

Hinweis: Fehlgeschlagene Downloads (kein Transkript verfuegbar) werden nicht
durch Reserve-Videos ersetzt - Zellen koennen nach dem Download also unter
3 bleiben. Ein erneuter Lauf dieses Skripts nach dem Download zieht fuer diese
Zellen automatisch Nachruecker.

Ausgabe nach outputs/segment_analysis/abdeckung_politisch_nichtkrieg/:
  - download_liste1_zellen_ge3_krieg.json
  - download_liste2_zellen_1bis2_krieg.json
  - download_listen_zellen.csv (je Zelle: Liste, n_krieg_tr, n_pol_nk,
    vorhandene NK-Transkripte, gezogen, erreichbar)
  - download_listen_README.md

    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        scripts/adhoc/download_liste_politisch_nichtkrieg.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd

from abdeckung_politisch_nichtkrieg_transkripte import ERGEBNIS_ORDNER, lade, md_tabelle, zellen_abgleich

ZIEL_PRO_ZELLE = 3
SEED = 20261002
LISTEN = {
    "liste1": {"datei": "download_liste1_zellen_ge3_krieg.json", "min_krieg_tr": 3, "max_krieg_tr": None},
    "liste2": {"datei": "download_liste2_zellen_1bis2_krieg.json", "min_krieg_tr": 1, "max_krieg_tr": 2},
}
ZELLE = ["channel_id", "monat"]


def main():
    v, kanaele = lade()
    v = v.merge(kanaele[["channel_id", "medientyp"]], on="channel_id", how="left")
    z = zellen_abgleich(v)

    def liste_von(n):
        for name, cfg in LISTEN.items():
            if n >= cfg["min_krieg_tr"] and (cfg["max_krieg_tr"] is None or n <= cfg["max_krieg_tr"]):
                return name
        return None
    z["liste"] = z["n_krieg_tr"].map(liste_von)
    z = z[z["liste"].notna()].copy()
    z["bedarf"] = (ZIEL_PRO_ZELLE - z["n_pol_nk_tr"]).clip(lower=0)

    pnk = (v["politisch"] == True) & ~v["krieg"]  # noqa: E712
    kandidaten = v[pnk & ~v["versucht"]][["video_id", "channel_id", "monat"]]
    kandidaten = kandidaten.merge(z[ZELLE + ["liste", "bedarf"]], on=ZELLE, how="inner")
    kandidaten = kandidaten[kandidaten["bedarf"] > 0]

    # Zufallsrang je Zelle, dann die ersten `bedarf` Videos nehmen
    kandidaten = kandidaten.sample(frac=1, random_state=SEED)
    kandidaten["rang"] = kandidaten.groupby(ZELLE).cumcount()
    gezogen = kandidaten[kandidaten["rang"] < kandidaten["bedarf"]]

    n_gez = gezogen.groupby(ZELLE).size().rename("gezogen")
    n_kand = kandidaten.groupby(ZELLE).size().rename("kandidaten")
    z = z.merge(n_gez, on=ZELLE, how="left").merge(n_kand, on=ZELLE, how="left").fillna({"gezogen": 0, "kandidaten": 0})
    z["erreichbar"] = (z["n_pol_nk_tr"] + z["gezogen"]).clip(upper=ZIEL_PRO_ZELLE)
    z.assign(monat=z["monat"].astype(str)).to_csv(ERGEBNIS_ORDNER / "download_listen_zellen.csv",
                                                  index=False, encoding="utf-8")

    rows = []
    for name, cfg in LISTEN.items():
        g = gezogen[gezogen["liste"] == name].sample(frac=1, random_state=SEED)
        eintraege = [{"video_id": r.video_id, "channel_id": r.channel_id} for r in g.itertuples()]
        (ERGEBNIS_ORDNER / cfg["datei"]).write_text(json.dumps(eintraege, indent=2), encoding="utf-8")
        zl = z[z["liste"] == name]
        rows.append({
            "Liste": f"`{cfg['datei']}`", "Zellen": len(zl), "Kanäle": zl["channel_id"].nunique(),
            "Zellen bereits voll": int((zl["bedarf"] == 0).sum()),
            "Zellen ohne pol. NK-Video": int((zl["n_pol_nk"] == 0).sum()),
            "IDs gezogen": len(eintraege),
            "Zellen danach mit 3 (wenn alle OK)": f"{int((zl['erreichbar'] >= ZIEL_PRO_ZELLE).sum())} "
                                                 f"({(zl['erreichbar'] >= ZIEL_PRO_ZELLE).mean():.1%})",
            "Zellen danach mit ≥1": f"{(zl['erreichbar'] >= 1).mean():.1%}",
        })
        print(f"[{name}] {len(eintraege)} IDs -> {ERGEBNIS_ORDNER / cfg['datei']}")

    zp = z[z["periode"] != "uebergang"].assign(gruppe=lambda d: d["liste"] + " / " + d["medientyp"] + " / " + d["periode"])
    nach_typ = (zp.groupby("gruppe").agg(Zellen=("monat", "size"), gezogen=("gezogen", "sum"),
                                         voll_danach=("erreichbar", lambda s: f"{(s >= ZIEL_PRO_ZELLE).mean():.1%}"))
                .reset_index().astype({"gezogen": int}))
    text = "\n".join([
        "# Download-Listen politische Nicht-Kriegsvideos",
        "",
        "Erzeugt von `scripts/adhoc/download_liste_politisch_nichtkrieg.py` (Seed "
        f"{SEED}). Definitionen wie in `README.md` dieses Ordners. Je Kanal-Monats-Zelle "
        f"Ziel {ZIEL_PRO_ZELLE} politische Nicht-Kriegsvideos mit Transkript; vorhandene Transkripte "
        "zählen gegen die Quote, der Rest wird zufällig aus noch nie versuchten Videos gezogen.",
        "",
        "- Liste 1: Zellen mit ≥ 3 Kriegsvideos mit Transkript",
        "- Liste 2: Zellen mit 1–2 Kriegsvideos mit Transkript",
        "",
        md_tabelle(pd.DataFrame(rows)),
        "",
        "„danach“ unterstellt, dass jeder Download klappt. Fehlschläge werden nicht ersetzt; ein erneuter "
        "Lauf des Skripts nach dem Download zieht Nachrücker.",
        "",
        "## Nach Liste × Medientyp × Periode",
        "",
        md_tabelle(nach_typ),
        "",
        "## Verwendung",
        "",
        "In `src/youtube_code/step4_transcript_download/download_transcripts.py` `VIDEO_LIST` auf den "
        "Pfad der jeweiligen JSON-Datei setzen und das Modul starten.",
        "",
    ])
    (ERGEBNIS_ORDNER / "download_listen_README.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

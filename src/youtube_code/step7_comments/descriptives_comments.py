# -*- coding: utf-8 -*-
"""
descriptives_comments.py

Deskriptive Uebersicht, bei welchen Medientypen die Nutzer der Kommentar-Stichprobe
kommentieren, wie stark sich die Publika ueberschneiden und ob Nutzer im Verlauf von
2022 von ÖRR/traditionellen Kanaelen zu rechten alternativen Kanaelen wandern.

Daten
-----
- Videos: VIDEO_LISTE (Ziehung max. 14 long-Videos je Kanal-Woche, 06.01.2022 bis
  04.01.2023; der Dateiname nennt nur den urspruenglichen Zeitraum).
- Kanal je Video: videos_roh.dta. Medientyp: kanaele_roh.dta ueber die Gruppen
  "medientyp_ideologie" aus marktanteil_rohdaten_plots.py (inkl. MANUELL_ALT_RECHTS).
  Ausgewertet werden GRUPPEN, Kanaele ohne eine dieser Gruppen fallen heraus.
- Kommentare: comment_store.get_comment_meta() (nur Top-Level, ohne Text). Kommentare
  des Kanals unter eigenen Videos und Kommentare ohne Autor fallen heraus.

Auswertungen
------------
1. Ueberblick und Ueberschneidung: alle Kommentare der Videos, auch solche nach
   dem Analysefenster. Nutzer je Gruppenkombination und bedingte Ueberschneidung
   ("x % der ÖRR-Kommentierenden kommentieren auch bei ..."), jeweils fuer die
   Mindestaktivitaeten SCHWELLEN_UEBERSCHNEIDUNG (wer einmal kommentiert, kann keine
   Ueberschneidung haben).
2. Zeitverlauf: nur Kommentare, deren Datum in PERIODEN liegt. Kommentar- und
   Videoanteile je Woche und Periode; Anteil der in einer Woche aktiven Nutzer, die
   in derselben Woche in beiden Lagern kommentieren (ÖRR/Traditionelle und Alternative).
3. Kohorten: Nutzer werden in der ersten Periode nach ihrem Anteil Kommentare bei
   ALT_GRUPPE eingeteilt (<= 1 - HEIMAT_SCHWELLE = "ÖRR/Traditionelle", >= HEIMAT_SCHWELLE =
   "Alternative", sonst "Gemischt") und spaeter weiterverfolgt.

Wer nach extremem Verhalten ausgewaehlt wird, wirkt spaeter auch ohne echte Veraenderung
weniger extrem (Regression zur Mitte). Die Kommentare der ersten Periode werden deshalb
zufaellig halbiert: Haelfte A bildet die Kohorte, Haelfte B misst dieselben Nutzer im
selben Zeitraum und ist der Benchmark fuer "keine Veraenderung". Eine Wanderung
zeigt sich erst als Abstand spaeterer Perioden zu Haelfte B, gemessen als Differenz
innerhalb derselben Nutzer und im Vergleich beider Richtungen.

Robustheit im Bericht: Kohorten getrennt nach ÖRR und traditionellen Medien; Lauf ohne
Kanaele ohne abgefragtes Vorkriegsvideo (neue Kanaele veraendern das Angebot); Lauf ohne
ROBUST_KANAELE; Rueckwaerts-Placebo (Kohorte in der letzten Periode, Blick zurueck: reine
Regression zur Mitte waere vorwaerts und rueckwaerts spiegelbildlich); Herkunft der
Kommentare bei ALT_GRUPPE in der letzten Periode.

Ausgabe nach PFAD_AUSGABE: bericht_kommentare_medientyp.md, kombinationen.png,
zeitverlauf_woche.png, kohorten_alt_anteil.png, woche.csv, kohorten.csv,
nutzer_kommentare.csv (Kommentare je Nutzer, gesamt und je Gruppe).

Ausfuehren aus dem Repo-Root:
    PYTHONPATH=src PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m youtube_code.step7_comments.descriptives_comments
"""

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from youtube_code.config import ADHOC_OUTPUT, OUTPUTS
from youtube_code.step6_auswertung import marktanteil_rohdaten_plots as ma
from youtube_code.step6_auswertung.prepare_channel_scores import KRIEGSBEGINN
from youtube_code.store.comment_store import get_comment_meta, get_comment_status


# =========================================================
# CONFIG
# =========================================================

VIDEO_LISTE = ADHOC_OUTPUT / "video_ids_angebot_2022-06-02_2022-11-02.csv"   # CSV mit Spalte video_id
PFAD_AUSGABE = OUTPUTS / "kommentare" / "medientyp_ueberschneidung"
ZEITZONE = "Europe/Berlin"   # Datum der Kommentare in Ortszeit, wie in VIDEO_LISTE

# True = nur Kanaele aus ma.KANALLISTE, False = alle Kanaele aus VIDEO_LISTE
NUR_KANALLISTE = False

# Mindestzahl Kommentare je Nutzer fuer die Ueberschneidungstabellen (ganze Zahlen >= 1)
SCHWELLEN_UEBERSCHNEIDUNG = [1, 5, 20]

# Zeitfenster {Name: (von, bis)}, "JJJJ-MM-TT", inklusive, aufsteigend und ohne
# Ueberlappung. Die erste Periode ist die Startperiode der Kohorten. Ende 26.10.2022, weil
# danach nur rund 10 % der Videos abgefragt sind (Stand 05.11.2026, vorher 45-90 % je Gruppe);
# nach weiterem Kommentar-Download verlaengerbar.
PERIODEN = {
    "Vorkrieg": ("2022-01-06", "2022-02-23"),
    "Quartal 0": ("2022-02-24", "2022-05-23"),
    "Quartal 1": ("2022-05-24", "2022-08-23"),
    "Quartal 2 (bis 26.10.)": ("2022-08-24", "2022-10-26"),
}

# Robustheitslauf ohne diese Kanaele (kanal_name in kanaele_roh, exakt; leere Liste = kein Lauf)
ROBUST_KANAELE = ["BILD", "Achtung, Reichelt!"]

# Mindestzahl Kommentare in Haelfte A der Startperiode, um in eine Kohorte zu kommen (>= 1);
# 5 bedeutet rund 10 Kommentare in der Startperiode ("kommentiert viel")
MIN_KOMMENTARE_KOHORTE = 5
# Mindestzahl Kommentare, damit ein Kohorten-Nutzer in einer Vergleichsperiode zaehlt (>= 1)
MIN_KOMMENTARE_VERGLEICH = 3
# Anteil der Kommentare in einem Lager, ab dem ein Nutzer zu diesem Lager zaehlt (0.5 < x <= 1)
HEIMAT_SCHWELLE = 0.8
SEED = 20220224   # beliebige ganze Zahl; Zufallshalbierung der Startperiode

# =========================================================
# CONFIG ENDE
# =========================================================

GRUPPEN = ["ÖRR", "Traditionelle Medien", "Alternative (rechts)"]
ALT_GRUPPE = "Alternative (rechts)"

_mt = ma.KLASSIFIKATIONEN["medientyp_ideologie"]
FARBEN = {g: f for g, f in zip(_mt["gruppen"], _mt["farben"]) if g in GRUPPEN}

K_MAIN, K_MIX, K_ALT = "ÖRR/Traditionelle", "Gemischt", "Alternative"
KOHORTEN = [K_MAIN, K_MIX, K_ALT]
KOHORTEN_FARBEN = {K_MAIN: FARBEN["ÖRR"], K_MIX: "#7c7a74", K_ALT: FARBEN[ALT_GRUPPE]}
BENCHMARK = "Vorkrieg (Hälfte B)"

TINTE = "#3d3c38"
RASTER = "#e5e3dc"


# =========================================================
# Daten
# =========================================================

def lade_kanaele():
    """Gruppe je Kanal wie in marktanteil_rohdaten_plots.py (ÖRR-Doku zaehlt hier zu ÖRR)."""
    kanaele, _ = ma.bilde_gruppen(ma.lade_kanaele())
    kanaele, _ = ma.manuell_alt_rechts(kanaele)
    if NUR_KANALLISTE:
        kanaele = kanaele[kanaele["channel_id"].isin(ma.KANALLISTE)]
    kanaele = kanaele.assign(gruppe=kanaele["medientyp_ideologie"].replace({ma.OERR_DOKU_GRUPPE: "ÖRR"}))
    return kanaele[kanaele["gruppe"].isin(GRUPPEN)][["channel_id", "kanal_name", "gruppe"]]


def periode_von(datum):
    """Datumsspalte -> Periodenname aus PERIODEN (NaN = ausserhalb)."""
    p = pd.Series(np.nan, index=datum.index, dtype=object)
    for name, (von, bis) in PERIODEN.items():
        p[(datum >= pd.Timestamp(von)) & (datum <= pd.Timestamp(bis))] = name
    return pd.Categorical(p, categories=list(PERIODEN), ordered=True)


def woche_von(datum):
    return (datum - pd.Timestamp(KRIEGSBEGINN)).dt.days // 7


def lade_daten():
    """Gibt (Videos, Kommentare, Trichter-Dict) zurueck. Nutzer sind als Ganzzahl codiert,
    die Autoren-IDs dazu stehen in Trichter["autoren"]."""
    liste = pd.read_csv(VIDEO_LISTE, encoding="utf-8-sig", usecols=["video_id", "datum"])
    roh = pd.read_stata(ma.ROHDATEN_PFAD / "videos_roh.dta", columns=["video_id", "channel_id"])
    v = liste.merge(roh, on="video_id", how="left")
    n_nicht_in_roh = int(v["channel_id"].isna().sum())
    kanaele = lade_kanaele()
    v = v.merge(kanaele, on="channel_id", how="left")
    t = {"videos_liste": len(v), "videos_nicht_in_roh": n_nicht_in_roh,
         "videos_ohne_gruppe": int(v["gruppe"].isna().sum()),
         "kanaele": int(v.loc[v["gruppe"].notna(), "channel_id"].nunique())}
    ohne = v.loc[v["gruppe"].isna() & v["channel_id"].notna(), "channel_id"].nunique()
    print(f"[Videos] {len(v):,} in der Liste, {n_nicht_in_roh} nicht in videos_roh, "
          f"{t['videos_ohne_gruppe']:,} aus {ohne} Kanaelen ohne Gruppe")
    v = v[v["gruppe"].notna()].copy()
    v["datum"] = pd.to_datetime(v["datum"])
    v["periode"] = periode_von(v["datum"])
    v["woche"] = woche_von(v["datum"])
    status = get_comment_status(v["video_id"].tolist())
    v["abgefragt"] = v["video_id"].map(lambda i: status.get(i, {}).get("status") == "OK")

    c = get_comment_meta(v["video_id"].tolist())
    t["kommentare_roh"] = len(c)
    print(f"[Kommentare] {len(c):,} geladen")
    c["channel_id"] = c["video_id"].map(v.set_index("video_id")["channel_id"])
    c = c.drop(columns="video_id")
    ohne_autor = c["author_channel_id"].isna()
    eigen = c["author_channel_id"] == c["channel_id"]
    t["ohne_autor"], t["eigene"] = int(ohne_autor.sum()), int(eigen.sum())
    c = c[~ohne_autor & ~eigen].copy()
    codes, t["autoren"] = pd.factorize(c["author_channel_id"])
    c["nutzer"] = codes.astype("int32")
    c = c.drop(columns="author_channel_id")
    c["datum"] = (pd.to_datetime(c["published_at"], utc=True, format="ISO8601")
                  .dt.tz_convert(ZEITZONE).dt.tz_localize(None).dt.normalize())
    c = c.drop(columns="published_at")
    c["gruppe"] = pd.Categorical(c["channel_id"].map(kanaele.set_index("channel_id")["gruppe"]),
                                 categories=GRUPPEN, ordered=True)
    c["channel_id"] = c["channel_id"].astype("category")
    c["periode"] = periode_von(c["datum"])
    c["woche"] = woche_von(c["datum"])
    t["kommentare"] = len(c)
    t["kommentare_fenster"] = int(c["periode"].notna().sum())
    t["nutzer"] = int(c["nutzer"].nunique())
    t["namen"] = kanaele.set_index("channel_id")["kanal_name"].fillna("(ohne Name)").to_dict()
    return v, c, t


def nutzer_matrix(c):
    """Kommentare je Nutzer (Zeile) und Gruppe (Spalte)."""
    return (c.groupby(["nutzer", "gruppe"], observed=True).size().unstack(fill_value=0)
            .reindex(columns=GRUPPEN, fill_value=0))


# =========================================================
# 1. Ueberblick und Ueberschneidung
# =========================================================

def tabelle_gruppen(v, m):
    zeilen = []
    for g in GRUPPEN:
        vg, s = v[v["gruppe"] == g], m.loc[m[g] > 0, g]
        nur_hier = (m.loc[s.index].drop(columns=g).sum(axis=1) == 0).mean() if len(s) else np.nan
        zeilen.append({
            "Gruppe": g, "Kanäle": vg["channel_id"].nunique(), "Videos Liste": len(vg),
            "Videos abgefragt": int(vg["abgefragt"].sum()), "Abdeckung %": 100 * vg["abgefragt"].mean(),
            "Kommentare": int(s.sum()), "Kommentare je abgefr. Video": s.sum() / max(vg["abgefragt"].sum(), 1),
            "Nutzer": len(s), "Kommentare je Nutzer": s.mean() if len(s) else np.nan,
            "Median": s.median() if len(s) else np.nan, "Nur diese Gruppe %": 100 * nur_hier,
        })
    return pd.DataFrame(zeilen)


def tabelle_aktivitaet(m):
    n = m.sum(axis=1).sort_values(ascending=False)
    top1 = n.iloc[:max(1, len(n) // 100)].sum() / n.sum() * 100
    top10 = n.iloc[:max(1, len(n) // 10)].sum() / n.sum() * 100
    return pd.DataFrame([{"Nutzer": len(n), "Mittelwert": n.mean(), "Median": n.median(),
                          "genau 1 Kommentar %": 100 * (n == 1).mean(), ">= 5 %": 100 * (n >= 5).mean(),
                          ">= 20 %": 100 * (n >= 20).mean(), "Kommentare der Top 1 % (Anteil %)": top1,
                          "Kommentare der Top 10 % (Anteil %)": top10}])


KOMBI_REIHENFOLGE = ["ÖRR", "Trad.", "Alt. rechts", "ÖRR + Trad.", "ÖRR + Alt. rechts",
                     "Trad. + Alt. rechts", "ÖRR + Trad. + Alt. rechts"]


def kombination_namen(m):
    kurz = {"ÖRR": "ÖRR", "Traditionelle Medien": "Trad.", ALT_GRUPPE: "Alt. rechts"}
    teile = [np.where(m[g] > 0, kurz[g], "") for g in GRUPPEN]
    return pd.Series([" + ".join(x for x in z if x) for z in zip(*teile)], index=m.index)


def tabelle_kombinationen(m):
    """Nutzer je Gruppenkombination, Spalten je Mindestaktivitaet."""
    aus = pd.DataFrame(index=KOMBI_REIHENFOLGE)
    for s in SCHWELLEN_UEBERSCHNEIDUNG:
        t = m[m.sum(axis=1) >= s]
        aus[f"Nutzer (>= {s})"] = kombination_namen(t).value_counts().reindex(KOMBI_REIHENFOLGE, fill_value=0)
        aus[f"% (>= {s})"] = 100 * aus[f"Nutzer (>= {s})"] / max(len(t), 1)
    return aus.rename_axis("Kommentiert bei").reset_index()


def tabelle_bedingt(m):
    """Anteil der Nutzer aus Zeilengruppe, die auch bei der Spaltengruppe kommentieren."""
    zeilen = []
    for s in SCHWELLEN_UEBERSCHNEIDUNG:
        t = m[m.sum(axis=1) >= s]
        for g in GRUPPEN:
            aktiv = t[t[g] > 0]
            zeile = {"Mind. Kommentare": s, "Nutzer von": g, "n": len(aktiv)}
            for h in GRUPPEN:
                zeile[f"auch {h} %"] = np.nan if h == g else 100 * (aktiv[h] > 0).mean()
            zeilen.append(zeile)
    return pd.DataFrame(zeilen)


def tabelle_top_kanaele(c, namen, n=5):
    zeilen = []
    for g in GRUPPEN:
        d = c[c["gruppe"] == g]
        for kanal, wert in d["channel_id"].value_counts().head(n).items():
            zeilen.append({"Gruppe": g, "Kanal": namen.get(kanal, kanal), "Kommentare": int(wert),
                           "Anteil an Gruppe %": 100 * wert / max(len(d), 1)})
    return pd.DataFrame(zeilen)


# =========================================================
# 2. Zeitverlauf
# =========================================================

def beide_lager(z, zeit):
    """Je Zeiteinheit: Anteil der Nutzer eines Lagers, die im selben Zeitraum auch im anderen kommentieren."""
    d = z.assign(alt=z["gruppe"] == ALT_GRUPPE)
    f = d.groupby([zeit, "nutzer", "alt"], observed=True).size().unstack(fill_value=0).reindex(
        columns=[False, True], fill_value=0)
    main, alt = f[False] > 0, f[True] > 0
    g = pd.DataFrame({"main": main, "alt": alt, "beide": main & alt}).groupby(level=0, observed=True).sum()
    return pd.DataFrame({"Nutzer ÖRR/Trad.": g["main"], "Nutzer Alt. rechts": g["alt"],
                         "ÖRR/Trad. auch bei Alt. %": 100 * g["beide"] / g["main"].replace(0, np.nan),
                         "Alt. auch bei ÖRR/Trad. %": 100 * g["beide"] / g["alt"].replace(0, np.nan)})


def anteile_je(d, zeit, praefix):
    t = d.groupby([zeit, "gruppe"], observed=True).size().unstack(fill_value=0).reindex(columns=GRUPPEN, fill_value=0)
    return t.div(t.sum(axis=1), axis=0).mul(100).add_prefix(praefix)


def tabelle_woche(v, z):
    w = anteile_je(z, "woche", "Kommentare % ").join(z.groupby("woche").size().rename("Kommentare"))
    w = w.join(anteile_je(v[v["abgefragt"]], "woche", "Videos % ")).join(beide_lager(z, "woche"))
    return w.reset_index()


def tabelle_periode(v, z):
    t = z.groupby("periode", observed=True).size().rename("Kommentare").to_frame()
    tage = {p: (pd.Timestamp(b) - pd.Timestamp(a)).days + 1 for p, (a, b) in PERIODEN.items()}
    t["je Tag"] = t["Kommentare"] / t.index.map(tage).astype(float)
    t = t.join(anteile_je(z, "periode", "Kommentare % "))
    t = t.join(anteile_je(v[v["abgefragt"]], "periode", "Videos % ")).join(beide_lager(z, "periode"))
    return t.rename_axis("Periode").reset_index()


def tabelle_abdeckung(v):
    t = v.groupby(["periode", "gruppe"], observed=True)["abgefragt"].mean().mul(100).unstack()
    return t.reindex(columns=GRUPPEN).rename_axis(index="Upload-Periode", columns=None).reset_index()


def tabelle_luecken(v, namen, n=8):
    """Kanaele mit den meisten noch nicht abgefragten Videos im Analysefenster."""
    d = v[v["periode"].notna()]
    t = d.groupby(["channel_id", "gruppe"]).agg(Videos=("abgefragt", "size"), abgefragt=("abgefragt", "sum")).reset_index()
    t["fehlen"] = t["Videos"] - t["abgefragt"]
    t = t.sort_values("fehlen", ascending=False).head(n)
    t.insert(0, "Kanal", t["channel_id"].map(lambda i: namen.get(i, i)))
    return t.drop(columns="channel_id").rename(columns={"gruppe": "Gruppe"})


# =========================================================
# 3. Kohorten
# =========================================================

def einteilen(m):
    alt = m[ALT_GRUPPE] / m.sum(axis=1)
    return pd.Series(np.select([alt >= HEIMAT_SCHWELLE, alt <= 1 - HEIMAT_SCHWELLE], [K_ALT, K_MAIN], K_MIX), index=m.index)


def ki(s):
    return 1.96 * s.std() / np.sqrt(len(s)) if len(s) > 1 else np.nan


def analysiere_kohorten(z):
    """Gibt (Verlauf je Kohorte und Vergleichszeitraum, Kohorten-Series, Matrizen je Vergleich) zurueck."""
    perioden = list(PERIODEN)
    start = z[z["periode"] == perioden[0]]
    halb_a = np.random.default_rng(SEED).random(len(start)) < 0.5
    a = nutzer_matrix(start[halb_a])
    a = a[a.sum(axis=1) >= MIN_KOMMENTARE_KOHORTE]
    kohorte = einteilen(a)

    vergleiche = {BENCHMARK: start[~halb_a], **{p: z[z["periode"] == p] for p in perioden[1:]}}
    anteile = {}
    for name, d in vergleiche.items():
        m = nutzer_matrix(d[d["nutzer"].isin(kohorte.index)])
        anteile[name] = m[m.sum(axis=1) >= MIN_KOMMENTARE_VERGLEICH]

    zeilen, matrizen = [], {}
    basis = anteile[BENCHMARK].div(anteile[BENCHMARK].sum(axis=1), axis=0)
    basis_kohorte = kohorte.reindex(basis.index)
    for name, m in anteile.items():
        s = m.div(m.sum(axis=1), axis=0)
        wert_kohorte = kohorte.reindex(s.index)
        matrizen[name] = pd.crosstab(wert_kohorte, einteilen(m)).reindex(index=KOHORTEN, columns=KOHORTEN, fill_value=0)
        for k in KOHORTEN:
            d = s[wert_kohorte == k]
            alt = d[ALT_GRUPPE]
            paar = alt.index.intersection(basis.index[basis_kohorte == k])
            diff = (alt.loc[paar] - basis.loc[paar, ALT_GRUPPE]) * 100
            n_k = int((kohorte == k).sum())
            zeilen.append({
                "Kohorte": k, "Vergleich": name, "Kohorte n": n_k, "aktiv n": len(d),
                "aktiv %": 100 * len(d) / max(n_k, 1),
                "ÖRR %": 100 * d["ÖRR"].mean(), "Trad. %": 100 * d["Traditionelle Medien"].mean(),
                "Alt. rechts %": 100 * alt.mean(), "KI Alt. (+/-)": 100 * ki(alt),
                "überwiegend Alt. %": 100 * (alt >= 0.5).mean(),
                "Paare n": len(paar), "Änderung ggü. Hälfte B (pp)": diff.mean() if len(paar) else np.nan,
                "KI Änderung (+/-)": ki(diff),
            })
    return pd.DataFrame(zeilen), kohorte, matrizen


def einteilen_fein(m):
    """Wie einteilen(), aber ÖRR und traditionelle Medien getrennt."""
    n = m.sum(axis=1)
    return pd.Series(np.select(
        [m[ALT_GRUPPE] / n >= HEIMAT_SCHWELLE, m["ÖRR"] / n >= HEIMAT_SCHWELLE,
         m["Traditionelle Medien"] / n >= HEIMAT_SCHWELLE, m[ALT_GRUPPE] / n <= 1 - HEIMAT_SCHWELLE],
        [K_ALT, "ÖRR", "Traditionelle Medien", "ÖRR + Trad. gemischt"], K_MIX), index=m.index)


def alt_verlauf(z, start, ziele, einteilung=einteilen):
    """Mittlerer Anteil bei ALT_GRUPPE (%) je Kohorte (aus Haelfte A von start) in Haelfte B
    und in den Perioden ziele, Reihenfolge wie angegeben."""
    s = z[z["periode"] == start]
    halb_a = np.random.default_rng(SEED).random(len(s)) < 0.5
    a = nutzer_matrix(s[halb_a])
    k = einteilung(a[a.sum(axis=1) >= MIN_KOMMENTARE_KOHORTE])
    t = k.value_counts().rename("Kohorte n").to_frame()
    for name, d in {f"{start} (Hälfte B)": s[~halb_a], **{p: z[z["periode"] == p] for p in ziele}}.items():
        m = nutzer_matrix(d[d["nutzer"].isin(k.index)])
        m = m[m.sum(axis=1) >= MIN_KOMMENTARE_VERGLEICH]
        t[name] = (100 * m[ALT_GRUPPE] / m.sum(axis=1)).groupby(k.reindex(m.index)).mean()
    return t.rename_axis("Kohorte").reset_index()


def tabelle_herkunft(z):
    """Kommentare bei ALT_GRUPPE in der letzten Periode nach dem Verhalten derselben Nutzer im Vorkrieg."""
    perioden = list(PERIODEN)
    vor = nutzer_matrix(z[z["periode"] == perioden[0]])
    main, alt = vor[GRUPPEN[:2]].sum(axis=1) > 0, vor[ALT_GRUPPE] > 0
    status = pd.Series(np.select([main & alt, alt], ["beide Lager", "nur Alt. rechts"], "nur ÖRR/Trad."), index=vor.index)
    d = z[(z["periode"] == perioden[-1]) & (z["gruppe"] == ALT_GRUPPE)]
    herkunft = d["nutzer"].map(status).fillna("kein Kommentar im Vorkrieg")
    t = d.groupby(herkunft)["nutzer"].agg(Kommentare="size", Nutzer="nunique").rename_axis("Im Vorkrieg").reset_index()
    t["Anteil Kommentare %"] = 100 * t["Kommentare"] / max(t["Kommentare"].sum(), 1)
    return t.sort_values("Kommentare", ascending=False)


def robustheit(v, z, namen):
    """Tabellen der Robustheitslaeufe (siehe Moduldocstring)."""
    perioden = list(PERIODEN)
    vorwaerts = lambda d, **kw: alt_verlauf(d, perioden[0], perioden[1:], **kw)
    abgefragt_vor = set(v.loc[(v["periode"] == perioden[0]) & v["abgefragt"], "channel_id"])
    neue = set(v["channel_id"]) - abgefragt_vor
    tab = {"fein": vorwaerts(z, einteilung=einteilen_fein),
           "ohne_neue": vorwaerts(z[~z["channel_id"].isin(neue)]),
           "rueckwaerts": alt_verlauf(z, perioden[-1], perioden[-2::-1]),
           "herkunft": tabelle_herkunft(z)}
    anteil_neu = z.assign(neu=z["channel_id"].isin(neue)).groupby("periode", observed=True)["neu"].mean().mul(100)
    tab["neue_kanaele"] = anteil_neu.rename("Kommentare neuer Kanäle %").rename_axis("Periode").reset_index()
    tab["neu_n"] = len(neue)
    if ROBUST_KANAELE:
        ids = {i for i, n in namen.items() if n in ROBUST_KANAELE}
        tab["ohne_kanaele"] = vorwaerts(z[~z["channel_id"].isin(ids)])
    return tab


def zeilenprozent(matrix):
    t = matrix.div(matrix.sum(axis=1).replace(0, np.nan), axis=0).mul(100)
    t.insert(0, "n", matrix.sum(axis=1))
    return t.rename_axis(index="Kohorte (Hälfte A)", columns=None).reset_index()


def tabelle_ziele(z, kohorte, namen, n=10):
    """Bei welchen rechten alternativen Kanaelen kommentiert die ÖRR/Trad.-Kohorte nach der Startperiode?"""
    nutzer = kohorte.index[kohorte == K_MAIN]
    d = z[z["nutzer"].isin(nutzer) & (z["gruppe"] == ALT_GRUPPE) & (z["periode"] != list(PERIODEN)[0])]
    t = d.groupby("channel_id", observed=True).agg(Kommentare=("nutzer", "size"), Nutzer=("nutzer", "nunique"))
    t = t.sort_values("Kommentare", ascending=False).head(n)
    t["Anteil %"] = 100 * t["Kommentare"] / max(len(d), 1)
    t.insert(0, "Kanal", [namen.get(i, i) for i in t.index])
    return t.reset_index(drop=True)


# =========================================================
# Grafiken
# =========================================================

def stil(ax):
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(RASTER)
    ax.grid(axis="y", color=RASTER, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=TINTE, length=0)
    for t in (ax.title, ax.xaxis.label, ax.yaxis.label):
        t.set_color(TINTE)


def grafik_kombinationen(kombi, pfad):
    schwellen = SCHWELLEN_UEBERSCHNEIDUNG
    fig, axes = plt.subplots(1, len(schwellen), figsize=(4.4 * len(schwellen), 4.2), sharey=True, squeeze=False)
    y = np.arange(len(kombi))[::-1]
    for ax, s in zip(axes[0], schwellen):
        werte = kombi[f"% (>= {s})"]
        ax.barh(y, werte, height=0.62, color=FARBEN["ÖRR"])
        for yi, w in zip(y, werte):
            ax.text(w + 1, yi, f"{w:.1f} %", va="center", fontsize=9, color=TINTE)
        ax.set_yticks(y, kombi["Kommentiert bei"])
        ax.set_xlim(0, max(werte.max() * 1.25, 10))
        n = int(kombi[f"Nutzer (>= {s})"].sum())
        ax.set_title(f"mind. {s} Kommentar{'e' if s > 1 else ''} ({n:,} Nutzer)".replace(",", "."), fontsize=11)
        ax.set_xlabel("Anteil der Nutzer (%)")
        stil(ax)
        ax.grid(False)
    fig.suptitle("Bei welchen Medientypen die Nutzer kommentieren", color=TINTE, fontsize=13)
    fig.tight_layout()
    fig.savefig(pfad, dpi=200)
    plt.close(fig)


def grafik_woche(w, pfad):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    for g in GRUPPEN:
        ax1.plot(w["woche"], w[f"Kommentare % {g}"], color=FARBEN[g], linewidth=2, label=g)
        ax1.plot(w["woche"], w[f"Videos % {g}"], color=FARBEN[g], linewidth=1, linestyle=":")
    ax1.plot([], [], color=TINTE, linewidth=1, linestyle=":", label="gepunktet: Anteil abgefragter Videos")
    ax1.set_ylabel("Anteil je Woche (%)")
    ax1.set_title("Kommentare und abgefragte Videos je Gruppe", fontsize=11)
    ax1.legend(frameon=False, fontsize=9)

    ax2.plot(w["woche"], w["ÖRR/Trad. auch bei Alt. %"], color="#52514e", linewidth=2,
             label="ÖRR/Trad.-Nutzer, die auch bei Alt. rechts kommentieren")
    ax2.plot(w["woche"], w["Alt. auch bei ÖRR/Trad. %"], color=FARBEN[ALT_GRUPPE], linewidth=2,
             label="Alt. rechts-Nutzer, die auch bei ÖRR/Trad. kommentieren")
    ax2.set_ylabel("Anteil der in der Woche aktiven Nutzer (%)")
    ax2.set_title("Überschneidung innerhalb derselben Woche", fontsize=11)
    ax2.set_ylim(bottom=0)
    ax2.legend(frameon=False, fontsize=9)
    for ax in (ax1, ax2):
        ax.axvline(0, color=TINTE, linestyle="--", linewidth=1)
        ax.set_xlabel("Woche relativ zum Kriegsbeginn (Woche 0 = 24.02.2022)")
        stil(ax)
    fig.tight_layout()
    fig.savefig(pfad, dpi=200)
    plt.close(fig)


def grafik_kohorten(verlauf, pfad):
    namen = [BENCHMARK, *list(PERIODEN)[1:]]
    x = np.arange(len(namen))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    for k in KOHORTEN:
        d = verlauf[verlauf["Kohorte"] == k].set_index("Vergleich").reindex(namen)
        ax1.errorbar(x, d["Alt. rechts %"], yerr=d["KI Alt. (+/-)"], color=KOHORTEN_FARBEN[k], linewidth=2,
                     marker="o", markersize=7, capsize=3, label=f"{k} (n = {int(d['Kohorte n'].iloc[0]):,})".replace(",", "."))
        ax2.errorbar(x[1:], d["Änderung ggü. Hälfte B (pp)"].iloc[1:], yerr=d["KI Änderung (+/-)"].iloc[1:],
                     color=KOHORTEN_FARBEN[k], linewidth=2, marker="o", markersize=7, capsize=3, label=k)
    ax1.set_ylim(0, 100)
    ax1.set_ylabel("Mittlerer Anteil Kommentare bei Alt. rechts (%)")
    ax1.set_title("Niveau je Kohorte (Hälfte B = Benchmark ohne Regressionseffekt)", fontsize=11)
    ax1.legend(frameon=False, fontsize=9, title="Kohorte nach Hälfte A", title_fontsize=9)
    ax1.set_xticks(x, namen)
    ax2.axhline(0, color=TINTE, linewidth=1)
    ax2.set_ylabel("Änderung ggü. Hälfte B, dieselben Nutzer (pp)")
    ax2.set_title("Änderung innerhalb der Nutzer", fontsize=11)
    ax2.set_xticks(x[1:], namen[1:])
    ax2.legend(frameon=False, fontsize=9)
    for ax in (ax1, ax2):
        stil(ax)
    fig.tight_layout()
    fig.savefig(pfad, dpi=200)
    plt.close(fig)


# =========================================================
# Bericht
# =========================================================

def fmt(wert):
    if isinstance(wert, (float, np.floating)):
        if np.isnan(wert):
            return "-"
        return f"{wert:.1f}"
    if isinstance(wert, (int, np.integer)):
        return f"{wert:,}".replace(",", ".")
    return str(wert)


def md_tabelle(df):
    kopf = "| " + " | ".join(map(str, df.columns)) + " |"
    trenn = "|" + " --- |" * len(df.columns)
    return "\n".join([kopf, trenn, *("| " + " | ".join(fmt(x) for x in z) + " |"
                                     for z in df.itertuples(index=False))])


def schreibe_bericht(t, tab, pfad):
    p = list(PERIODEN)
    teile = [
        "# Kommentare nach Medientyp: Überschneidung und Wanderung",
        "",
        "Erzeugt von `src/youtube_code/step7_comments/descriptives_comments.py`.",
        "",
        "## Datenbasis",
        "",
        f"- Videos in der Liste: {fmt(t['videos_liste'])}, davon {fmt(t['videos_ohne_gruppe'])} aus Kanälen ohne "
        f"eine der drei Gruppen; ausgewertet {fmt(t['kanaele'])} Kanäle.",
        f"- Kommentare geladen: {fmt(t['kommentare_roh'])}; ohne Autor {fmt(t['ohne_autor'])}, vom Kanal selbst "
        f"{fmt(t['eigene'])}; ausgewertet {fmt(t['kommentare'])} von {fmt(t['nutzer'])} Nutzern.",
        f"- Davon im Analysefenster {PERIODEN[p[0]][0]} bis {PERIODEN[p[-1]][1]}: {fmt(t['kommentare_fenster'])}.",
        "",
        "## Grenzen beim Lesen",
        "",
        "- **Ungleiche Abdeckung:** Der Kommentar-Download ist nicht abgeschlossen, und der Anteil abgefragter Videos "
        "unterscheidet sich zwischen den Gruppen (Tabellen unten). Absolute Zahlen und Gruppenanteile sind deshalb nicht "
        "die tatsächliche Verteilung; die Ziehung kappt zudem bei 14 Videos je Kanal-Woche, was uploadstarke Kanäle "
        "trifft. Überschneidungen sind untere Grenzen, weil nicht abgefragte Videos fehlen.",
        "- **Nur Top-Level-Kommentare** aus einem späteren Abruf: inzwischen gelöschte Kommentare und Konten fehlen, "
        "möglicherweise je Gruppe unterschiedlich stark.",
        "- **Überschneidung hängt von der Aktivität ab:** Wer wenig kommentiert, kann kaum in mehreren Gruppen auftauchen.",
        "- **Gleiche Nutzer-Kennung ist nicht gleiche Person**, und Bots werden nicht herausgefiltert.",
        "- **Vorkriegsfenster nur 7 Wochen**, Kommentare darin nur unter Videos ab 06.01.2022. Kein Kausalnachweis: "
        "Es gibt keine Kontrollgruppe, und Wanderungen können auch das veränderte Angebot widerspiegeln.",
        "- **Konfidenzintervalle** behandeln Nutzer als unabhängig und sind bei dieser Fallzahl eng; "
        "entscheidend ist die Größe des Effekts, nicht die Signifikanz.",
        "",
        "## 1. Überblick",
        "",
        "Alle Kommentare der Videos (auch nach dem Analysefenster).",
        "",
        md_tabelle(tab["gruppen"]),
        "",
        md_tabelle(tab["aktivitaet"]),
        "",
        "### Gruppenkombinationen",
        "",
        "![Kombinationen](kombinationen.png)",
        "",
        md_tabelle(tab["kombi"]),
        "",
        "### Bedingte Überschneidung",
        "",
        md_tabelle(tab["bedingt"]),
        "",
        "### Größte Kanäle je Gruppe",
        "",
        md_tabelle(tab["top"]),
        "",
        "## 2. Zeitverlauf",
        "",
        "Nur Kommentare mit Datum im Analysefenster. Die Überschneidung je Periode steigt mechanisch mit der "
        "Periodenlänge; für den Trend zählt die Grafik je Woche.",
        "",
        "![Woche](zeitverlauf_woche.png)",
        "",
        md_tabelle(tab["periode"]),
        "",
        "### Abdeckung: Anteil abgefragter Videos je Upload-Periode (%)",
        "",
        md_tabelle(tab["abdeckung"]),
        "",
        "Kanäle mit den meisten noch nicht abgefragten Videos im Analysefenster:",
        "",
        md_tabelle(tab["luecken"]),
        "",
        "## 3. Kohorten: Wandern Nutzer von ÖRR/Traditionellen zu rechten Alternativen?",
        "",
        f"Kohorte aus Hälfte A der Periode „{p[0]}“ (mind. {MIN_KOMMENTARE_KOHORTE} Kommentare, Lagerschwelle "
        f"{HEIMAT_SCHWELLE:.0%}). Vergleichsperioden zählen Nutzer mit mind. {MIN_KOMMENTARE_VERGLEICH} Kommentaren. "
        f"„{BENCHMARK}“ misst dieselben Nutzer im selben Zeitraum und zeigt die Regression zur Mitte ohne "
        "jede Verhaltensänderung. Eine Wanderung ist nur der Abstand zu diesem Benchmark, nicht zur Kohortendefinition.",
        "",
        "![Kohorten](kohorten_alt_anteil.png)",
        "",
        md_tabelle(tab["verlauf"]),
        "",
        f"### Übergänge: Benchmark ({BENCHMARK}, Zeilen-%)",
        "",
        md_tabelle(tab["matrix_b"]),
        "",
        f"### Übergänge: letzte Periode ({p[-1]}, Zeilen-%)",
        "",
        md_tabelle(tab["matrix_ende"]),
        "",
        "### Wo die ÖRR/Traditionelle-Kohorte bei rechten Alternativen kommentiert",
        "",
        "Nach der Startperiode. Wenige Kanäle mit großem Anteil sprechen eher für einen Kanaleffekt als für einen "
        "allgemeinen Wechsel.",
        "",
        md_tabelle(tab["ziele"]),
        "",
        "## 4. Robustheit",
        "",
        "Alle Tabellen zeigen den mittleren Anteil der Kommentare bei Alternative (rechts) in %.",
        "",
        "### ÖRR und traditionelle Medien getrennt",
        "",
        md_tabelle(tab["rob"]["fein"]),
        "",
        f"### Ohne neue Kanäle ({tab['rob']['neu_n']} Kanäle ohne abgefragtes Vorkriegsvideo)",
        "",
        md_tabelle(tab["rob"]["neue_kanaele"]),
        "",
        md_tabelle(tab["rob"]["ohne_neue"]),
        "",
        *([f"### Ohne {', '.join(ROBUST_KANAELE)}", "", md_tabelle(tab["rob"]["ohne_kanaele"]), ""]
          if ROBUST_KANAELE else []),
        "### Rückwärts-Placebo",
        "",
        "Kohorte in der letzten Periode, Blick zurück. Reine Regression zur Mitte wäre spiegelbildlich zur "
        "Vorwärtsrichtung: Die ÖRR/Traditionelle-Kohorte hätte dann früher höhere Anteile bei Alt. rechts.",
        "",
        md_tabelle(tab["rob"]["rueckwaerts"]),
        "",
        "### Woher die Kommentare bei Alt. rechts in der letzten Periode kommen",
        "",
        "Das Vorkriegsfenster ist kurz: „kein Kommentar im Vorkrieg“ heißt nicht, dass der Nutzer neu ist.",
        "",
        md_tabelle(tab["rob"]["herkunft"]),
        "",
    ]
    pfad.write_text("\n".join(teile), encoding="utf-8")


# =========================================================
# Main
# =========================================================

def pruefe_config():
    if not isinstance(NUR_KANALLISTE, bool):
        raise SystemExit(f"NUR_KANALLISTE muss True oder False sein, nicht {NUR_KANALLISTE!r}.")
    if not SCHWELLEN_UEBERSCHNEIDUNG or not all(isinstance(s, int) and s >= 1 for s in SCHWELLEN_UEBERSCHNEIDUNG):
        raise SystemExit(f"SCHWELLEN_UEBERSCHNEIDUNG muss ganze Zahlen >= 1 enthalten: {SCHWELLEN_UEBERSCHNEIDUNG!r}.")
    for name, wert in (("MIN_KOMMENTARE_KOHORTE", MIN_KOMMENTARE_KOHORTE), ("MIN_KOMMENTARE_VERGLEICH", MIN_KOMMENTARE_VERGLEICH)):
        if not isinstance(wert, int) or wert < 1:
            raise SystemExit(f"{name} muss eine ganze Zahl >= 1 sein, nicht {wert!r}.")
    if not 0.5 < HEIMAT_SCHWELLE <= 1:
        raise SystemExit(f"HEIMAT_SCHWELLE muss in (0.5, 1] liegen, nicht {HEIMAT_SCHWELLE!r}.")
    if len(PERIODEN) < 2:
        raise SystemExit("PERIODEN braucht mindestens zwei Zeitfenster.")
    ende = None
    for name, (von, bis) in PERIODEN.items():
        von, bis = pd.Timestamp(von), pd.Timestamp(bis)
        if bis < von or (ende is not None and von <= ende):
            raise SystemExit(f"PERIODEN: {name} ist verkehrt herum oder überlappt die vorige Periode.")
        ende = bis
    if not isinstance(ROBUST_KANAELE, list):
        raise SystemExit(f"ROBUST_KANAELE muss eine Liste von Kanalnamen sein, nicht {ROBUST_KANAELE!r}.")
    if not VIDEO_LISTE.exists():
        raise SystemExit(f"VIDEO_LISTE fehlt: {VIDEO_LISTE}")


def main():
    pruefe_config()
    v, c, t = lade_daten()
    PFAD_AUSGABE.mkdir(parents=True, exist_ok=True)
    m = nutzer_matrix(c)
    z = c[c["periode"].notna()]
    verlauf, kohorte, matrizen = analysiere_kohorten(z)
    woche = tabelle_woche(v, z)
    p = list(PERIODEN)
    tab = {
        "gruppen": tabelle_gruppen(v, m), "aktivitaet": tabelle_aktivitaet(m), "kombi": tabelle_kombinationen(m),
        "bedingt": tabelle_bedingt(m), "top": tabelle_top_kanaele(c, t["namen"]), "periode": tabelle_periode(v, z),
        "abdeckung": tabelle_abdeckung(v), "verlauf": verlauf, "matrix_b": zeilenprozent(matrizen[BENCHMARK]),
        "matrix_ende": zeilenprozent(matrizen[p[-1]]), "ziele": tabelle_ziele(z, kohorte, t["namen"]),
        "luecken": tabelle_luecken(v, t["namen"]), "rob": robustheit(v, z, t["namen"]),
    }
    woche.to_csv(PFAD_AUSGABE / "woche.csv", index=False, encoding="utf-8-sig")
    verlauf.to_csv(PFAD_AUSGABE / "kohorten.csv", index=False, encoding="utf-8-sig")
    (m.assign(n_comments=m.sum(axis=1)).rename_axis(index="nutzer", columns=None).reset_index()
     .assign(author_channel_id=lambda d: t["autoren"][d["nutzer"].to_numpy()]).drop(columns="nutzer")
     [["author_channel_id", "n_comments", *GRUPPEN]]
     .to_csv(PFAD_AUSGABE / "nutzer_kommentare.csv", index=False, encoding="utf-8-sig"))
    grafik_kombinationen(tab["kombi"], PFAD_AUSGABE / "kombinationen.png")
    grafik_woche(woche, PFAD_AUSGABE / "zeitverlauf_woche.png")
    grafik_kohorten(verlauf, PFAD_AUSGABE / "kohorten_alt_anteil.png")
    schreibe_bericht(t, tab, PFAD_AUSGABE / "bericht_kommentare_medientyp.md")
    print(f"[Output] {PFAD_AUSGABE / 'bericht_kommentare_medientyp.md'}")


if __name__ == "__main__":
    main()

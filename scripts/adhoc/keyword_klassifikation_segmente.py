"""Keyword-/Bag-of-Words-Annäherung der LLM-Themenklassifikation auf Segmentebene.

Fragestellung
-------------
Lässt sich die teure LLM-Klassifikation der Angebotsstudie
(`data/claude_classification/angebot/results_segment_level.csv`, Codebuch
`data/claude_classification/codebuch_angebotsstudie_v2.md`) durch eine lokal
laufende, billige Klassifikation so gut annähern, dass man damit vorab prüfen
kann, ob es überhaupt Trends (vor vs. nach Kriegsbeginn, nach Medientyp, nach
Kanal) gibt, die eine LLM-Klassifikation lohnen?

Erfasst werden nur zwei Dinge:
1. `themen` (Mehrfachnennung, 15 Kategorien) und daraus `hauptthema`.
2. `krieg_aspekte` (Mehrfachnennung, 15 Aspekte), nur wenn `krieg_ukraine`
   ein Thema ist.

Zwei Klassifikatoren
--------------------
A) **Stichwort-Diktionär** (`LEXIKON_THEMEN`, `LEXIKON_ASPEKTE` unten): von Hand
   aus den Codebuch-Definitionen abgeleitete Regex-Stämme. Pro Label wird die
   Zahl der Treffer im Segment gezählt; die Mindest-Trefferzahl, ab der ein
   Label vergeben wird, wird auf dem Trainingsset (F1-optimal) gewählt.
   `unpolitisch` = kein anderes Thema erkannt. Voll transparent, aber starr.
B) **TF-IDF + logistische Regression** (ein binäres Modell pro Label,
   Uni- und Bigramme). Entscheidungsschwelle pro Label F1-optimal per
   5-facher, nach Video gruppierter Kreuzvalidierung im Trainingsset.
   Das ist eine "gelernte Stichwortsuche": die Gewichte der Terme werden aus
   den LLM-Labels geschätzt (Top-Terme je Label stehen im Bericht).

Aspekte werden nur auf Segmenten mit (LLM-)Kriegsbezug trainiert und in der
End-to-End-Auswertung nur dort vergeben, wo der jeweilige Klassifikator selbst
`krieg_ukraine` erkannt hat.

Zwei Validierungsmodi (`SPLIT_MODUS` im Konfigurationsblock):
- `"video"`: ein Train/Test-Split nach `video_id` gruppiert (kein Video in
  beiden Teilen), damit nicht Nachbarsegmente desselben Videos die Testgüte
  aufblähen. Train und Test enthalten aber dieselben Kanäle.
- `"kanal"`: Kanal-Holdout per Kreuzanpassung. Die Kanäle werden innerhalb
  jedes Medientyps reihum (nach Segmentzahl, "Schlangen"-Verteilung) auf
  `KANAL_FOLDS` Folds verteilt; jeder Fold wird mit Modellen vorhergesagt, die
  nur auf den Kanälen der anderen Folds trainiert wurden (Schwellenwahl der
  LR ebenfalls per nach Kanal gruppierter CV). So ist jedes Segment genau
  einmal out-of-sample und das Testset umfasst alle Segmente und alle Kanäle.
  Das simuliert die Anwendung auf neue, ungesehene Kanäle. Liegt die Ausgabe
  des Video-Modus vor, enthält der Bericht einen F1-Vergleich beider Modi.

Auswertung (nur Testset)
------------------------
- Segmentgüte je Label: Prävalenz, Precision, Recall, F1.
- Trendtreue: Anteile vor/nach Kriegsbeginn (LLM vs. Klassifikator), dasselbe
  nach Medientyp, Korrelation der Wochen-Anteile und der Kanal-Veränderungen
  (nach − vor). Für die Vorab-Trendprüfung ist das die entscheidende Größe,
  nicht die Segment-F1.
Anteile sind ungewichtete Segmentanteile (nicht `segment_weight`).

Ausgabe: `scripts/adhoc/keyword_klassifikation_segmente/`
  - Modus "video": `bericht.md`, `test_vorhersagen.csv`
  - Modus "kanal": `bericht_kanal_holdout.md`, `test_vorhersagen_kanal_holdout.csv`
  (Bericht menschenlesbar; CSV = LLM-Labels und Vorhersagen je Testsegment)

Wiederverwendung: `src/youtube_code/step3_topic_relevance/classify_segment_topics.py`
lädt dieses Skript per importlib (Lexika, THEMEN/ASPEKTE, count_hits, fit_*/predict_*,
hauptthema_from_scores, md_table, INPUT_CSV, TFIDF_*) - Namen nicht ändern.

Laufzeit: Modus "video" ca. 4 Minuten, Modus "kanal" (3 Folds) ca. 8–10
Minuten (fast nur die CV der log. Regression), jeweils < 2 GB RAM.

Einschränkung: Beide Modi decken nur den Zeitraum Jan–Apr 2022 ab. Im Modus
"video" lernt die LR teils kanal-/sprecherspezifische Terme (z. B.
Reporternamen); der Modus "kanal" zeigt, wie viel davon bei neuen Kanälen
verloren geht. Für andere Zeiträume (z. B. 2023) ist keiner der Modi ein
Test. Aufruf aus dem Repo-Root:
    .venv/Scripts/python scripts/adhoc/keyword_klassifikation_segmente.py
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, GroupShuffleSplit

# ============================================================================
# KONFIGURATION
# ============================================================================
ROOT = Path(__file__).resolve().parents[2]
INPUT_CSV = ROOT / "data" / "claude_classification" / "angebot" / "results_segment_level.csv"  # Pfad zur LLM-Segmentdatei
OUTPUT_DIR = ROOT / "scripts" / "adhoc" / "keyword_klassifikation_segmente"  # Ausgabeordner (wird angelegt)
SPLIT_MODUS = "kanal"      # "video" = ein Split nach Video; "kanal" = Kanal-Holdout per Kreuzanpassung
TEST_ANTEIL = 0.4          # nur Modus "video": Anteil Videos im Testset, 0 < x < 1
KANAL_FOLDS = 3            # nur Modus "kanal": Zahl der Kanal-Folds (int, 2..5; mehr = längere Laufzeit)
SEED = 42                  # Zufallsseed für den Split (int)
CV_FOLDS = 5               # Folds für die Schwellenwahl der log. Regression (int >= 2)
LR_C = 4.0                 # Regularisierung der log. Regression (> 0; größer = weniger Regularisierung)
TFIDF_MIN_DF = 3           # Mindest-Dokumentfrequenz eines Terms (int >= 1)
TFIDF_NGRAM_MAX = 2        # 1 = nur Einzelwörter, 2 = zusätzlich Bigramme
MAX_TREFFER_SCHWELLE = 15  # größte getestete Mindest-Trefferzahl im Diktionär (int >= 1)
MIN_SEG_KANAL_PHASE = 10   # Mindestzahl Testsegmente je Kanal und Phase für die Kanal-Korrelation (int >= 1)
N_TOP_TERME = 15           # Anzahl Top-Terme je Label im Bericht (int >= 1)
# ============================================================================

THEMEN = ["krieg_ukraine", "corona", "migration", "wirtschaft", "energie", "klima",
          "gender", "nahost", "iran", "eu", "usa", "bildung", "innenpolitik_sonstige",
          "sonstiges_politisch", "unpolitisch"]
ASPEKTE = ["kriegsgeschehen_militaer", "kriegsverbrechen_zivilisten", "verhandlungen_diplomatie",
           "waffenlieferungen", "sanktionen", "finanzhilfe", "nato_eu_beitritt", "truppen_einsatz",
           "gefluechtete", "energie_preise_inland", "wirtschaft_inland", "bundeswehr_sondervermoegen",
           "russland_innen", "medien_desinformation", "sonstiges"]

# Regex-Stämme (Texte sind kleingeschrieben, ohne Satzzeichen; Stämme matchen
# auch innerhalb von Komposita, kurze/mehrdeutige Wörter mit \b begrenzt).
LEXIKON_THEMEN = {
    "krieg_ukraine": [r"ukrain", r"russland", r"russisch", r"putin", r"sel[ae]ns?k", r"zelensk", r"kiew", r"kyjiw",
                      r"donbas", r"donezk", r"luhansk", r"lugansk", r"invasion", r"kreml", r"mariupol", r"charkiw",
                      r"nord ?stream", r"\bkrim\b", r"separatist", r"lawrow", r"angriffskrieg", r"\bkrieg",
                      r"truppenaufmarsch", r"moskau"],
    "corona": [r"corona", r"covid", r"pandemie", r"\bimpf", r"geimpft", r"omi[ck]ron", r"inzidenz", r"lockdown",
               r"\b[23]g\b", r"\bmaske", r"maskenpflicht", r"infektion", r"\bvirus", r"drosten", r"lauterbach",
               r"spazierg", r"querdenk", r"intensivstation", r"booster", r"quarantäne", r"stiko", r"rki\b",
               r"robert koch", r"genesen"],
    "migration": [r"migra", r"flüchtling", r"geflüchtet", r"\bflucht", r"\basyl", r"abschieb", r"einwander",
                  r"zuwander", r"integration", r"grenzschutz", r"schleuser", r"staatsangehörig", r"ausländer",
                  r"geflohen"],
    "wirtschaft": [r"wirtschaft", r"inflation", r"teuerung", r"konjunktur", r"rezession", r"arbeitsmarkt",
                   r"arbeitslos", r"\blöhne", r"\blohn", r"mindestlohn", r"\brente", r"hartz", r"sozialleist",
                   r"bürgergeld", r"\bsteuer", r"schulden", r"haushalt", r"\bezb\b", r"zentralbank", r"leitzins",
                   r"\bzins", r"unternehmen", r"lieferkette", r"mittelstand", r"wachstum", r"\bpreise\b",
                   r"finanzminister", r"\bbip\b", r"industrie"],
    "energie": [r"energie", r"\bgas\b", r"gaspreis", r"erdgas", r"gasliefer", r"gasversorg", r"\böl\b", r"ölpreis",
                r"erdöl", r"\bkohle", r"atomkraft", r"\bakw", r"kernkraft", r"\bstrom", r"pipeline", r"nord ?stream",
                r"\blng\b", r"flüssiggas", r"benzin", r"diesel", r"sprit", r"\bheiz", r"erneuerbar", r"windkraft",
                r"windräder", r"\bsolar", r"photovolt", r"tankrabatt"],
    "klima": [r"klima", r"\bco2", r"emission", r"erderwärm", r"erderhitz", r"letzte generation", r"fridays",
              r"verbrenner", r"tempolimit", r"treibhaus", r"klimaneutral", r"kohleausstieg"],
    "gender": [r"gender", r"frauenquote", r"feminis", r"gleichstell", r"\btrans", r"lgbt", r"queer", r"homosex",
               r"schwul", r"lesb", r"\bwoke", r"geschlecht", r"sternchen", r"diversität"],
    "nahost": [r"israel", r"palästin", r"gaza", r"hamas", r"westjordan", r"antisemit", r"nahost", r"netanjahu",
               r"jerusalem"],
    "iran": [r"\biran", r"teheran", r"hisbollah", r"huthi", r"atomabkommen", r"mullah"],
    "eu": [r"\beu\b", r"europäische union", r"kommission", r"von der leyen", r"europaparlament",
           r"europäischen parlament", r"brüssel", r"mitglied?s?staat", r"ratspräsident", r"\beuropas?\b"],
    "usa": [r"\busa\b", r"amerika", r"biden", r"trump", r"washington", r"weiße[n]? haus", r"kongress", r"\bsenat",
            r"republikaner", r"pentagon", r"\bus\b"],
    "bildung": [r"schule", r"schüler", r"lehrer", r"universität", r"hochschule", r"studier", r"student", r"\bkita",
                r"kinderbetreuung", r"bildung", r"abitur", r"unterricht"],
    "innenpolitik_sonstige": [r"bundestag", r"koalition", r"\bampel", r"\bspd\b", r"\bcdu\b", r"\bcsu\b", r"\bfdp\b",
                              r"grünen", r"\bafd\b", r"\blinke\b", r"\bwahl", r"landtag", r"umfrage", r"minister",
                              r"kanzler", r"\bpartei", r"bundespräsident", r"steinmeier", r"polizei", r"justiz",
                              r"gericht", r"verfassung", r"extremis", r"rechtsextrem", r"\bpflege", r"merz",
                              r"lindner", r"habeck", r"faeser", r"\bbahn\b", r"söder"],
    "sonstiges_politisch": [r"china", r"chines", r"peking", r"\bxi\b", r"frankreich", r"französ", r"macron",
                            r"le pen", r"großbritannien", r"brit", r"johnson", r"türkei", r"erdogan", r"afghanistan",
                            r"taliban", r"syrien", r"\bmali\b", r"afrika", r"ungarn", r"orban", r"indien",
                            r"brasilien", r"kanada", r"trudeau", r"kasachstan", r"taiwan", r"österreich",
                            r"schweiz", r"demokratie", r"gesellschaft"],
}

LEXIKON_ASPEKTE = {
    "kriegsgeschehen_militaer": [r"truppen", r"panzer", r"soldat", r"\bfront", r"offensive", r"rakete", r"artillerie",
                                 r"kämpf", r"gefecht", r"militär", r"armee", r"luftwaff", r"\bbomb", r"beschuss",
                                 r"einmarsch", r"belager", r"eingekesselt", r"drohne", r"erober", r"gefallen",
                                 r"\bstreitkr", r"angriff", r"kampfhandlung", r"vormarsch"],
    "kriegsverbrechen_zivilisten": [r"zivil", r"kriegsverbrech", r"butscha", r"bucha", r"massaker", r"\bopfer",
                                    r"\btote", r"getötet", r"krankenhaus", r"geburtsklinik", r"völkermord", r"genozid",
                                    r"leichen", r"vergewalt", r"folter", r"\bleid", r"humanitäre katastrophe",
                                    r"schutzkeller", r"bunker"],
    "verhandlungen_diplomatie": [r"verhandl", r"waffenstillstand", r"waffenruhe", r"diplomat", r"gipfel",
                                 r"vermittl", r"frieden", r"istanbul", r"\bminsk", r"telefonat", r"telefoniert",
                                 r"außenminister", r"gespräche"],
    "waffenlieferungen": [r"waffenliefer", r"schwere waffen", r"panzerabwehr", r"stinger", r"javelin", r"\bhelme",
                          r"gepard", r"marder", r"leopard", r"haubitze", r"ringtausch", r"waffen an die ukraine",
                          r"waffen liefern", r"waffen geliefert", r"liefern wir", r"rüstungsgüter"],
    "sanktionen": [r"sanktion", r"\bswift", r"embargo", r"oligarch", r"eingefroren", r"einfrier", r"boykott", r"rubel",
                   r"strafmaßnahm"],
    "finanzhilfe": [r"finanzhilfe", r"hilfspaket", r"hilfsgüter", r"humanitäre hilfe", r"spende", r"wiederaufbau",
                    r"milliarden euro für die ukraine", r"unterstützungs?paket", r"hilfslieferung"],
    "nato_eu_beitritt": [r"beitritt", r"osterweiterung", r"erweiterung", r"finnland", r"schweden", r"beitreten",
                         r"mitgliedschaft", r"kandidatenstatus", r"neutralität", r"neutral"],
    "truppen_einsatz": [r"flugverbotszone", r"ostflanke", r"bündnisfall", r"artikel 5", r"weltkrieg", r"kriegspartei",
                        r"kriegsbeteiligung", r"atomkrieg", r"atomwaff", r"nuklear", r"baltikum", r"baltisch",
                        r"rumänien", r"nato.?truppen", r"bodentruppen"],
    "gefluechtete": [r"flüchtling", r"geflüchtet", r"\bflucht", r"geflohen", r"flieh", r"aufnahme", r"unterbring",
                     r"unterkunft", r"hauptbahnhof", r"vertrieb"],
    "energie_preise_inland": [r"\bgas", r"\böl\b", r"ölpreis", r"energie", r"nord ?stream", r"pipeline", r"benzin",
                              r"diesel", r"sprit", r"\bheiz", r"strompreis", r"\blng\b", r"abhängigkeit", r"kohle"],
    "wirtschaft_inland": [r"inflation", r"lieferkette", r"\bpreise", r"weizen", r"getreide", r"lebensmittel",
                          r"sonnenblumenöl", r"unternehmen", r"börse", r"aktie", r"\bdax\b", r"wirtschaft",
                          r"rezession", r"produktion", r"teuer"],
    "bundeswehr_sondervermoegen": [r"bundeswehr", r"sondervermögen", r"100 milliarden", r"hundert milliarden",
                                   r"verteidigungsausgaben", r"verteidigungshaushalt", r"zwei prozent", r"2 prozent",
                                   r"aufrüst", r"lambrecht", r"f.?35", r"zeitenwende", r"wehrpflicht"],
    "russland_innen": [r"nawalny", r"repression", r"festgenommen", r"festnahme", r"in russland", r"russische bevölkerung",
                       r"opposition", r"demonstr", r"protest", r"auswander", r"stimmung", r"verhaftet"],
    "medien_desinformation": [r"propaganda", r"desinformation", r"fake ?news", r"falschinformation", r"falschmeldung",
                              r"\brt\b", r"russia today", r"zensur", r"\bmedien", r"berichterstattung", r"journalist",
                              r"staatsfernsehen", r"informationskrieg", r"narrativ", r"mainstream", r"leitmedien",
                              r"lügenpresse", r"telegram"],
    # "sonstiges" ist per Definition ein Residuum ohne Stichworte -> nur log. Regression
}


# ----------------------------------------------------------------------------
# Hilfsfunktionen
# ----------------------------------------------------------------------------
def md_table(df: pd.DataFrame, floatfmt: str = "{:.2f}") -> str:
    """DataFrame -> Markdown-Tabelle (ohne tabulate-Abhängigkeit)."""
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        cells = []
        for v in row:
            if isinstance(v, (float, np.floating)):
                cells.append("" if np.isnan(v) else floatfmt.format(v))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def multi_hot(series: pd.Series, labels: list[str]) -> pd.DataFrame:
    return pd.DataFrame({lab: series.map(lambda l, lab=lab: int(lab in l)) for lab in labels}, index=series.index)


def prf(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float, float, float]:
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    p = tp / (tp + fp) if tp + fp else np.nan
    r = tp / (tp + fn) if tp + fn else np.nan
    f = 2 * p * r / (p + r) if (tp and not np.isnan(p) and not np.isnan(r)) else 0.0
    return p, r, f


def best_threshold(y: np.ndarray, scores: np.ndarray, candidates: np.ndarray) -> float:
    best_t, best_f = candidates[0], -1.0
    for t in candidates:
        f = prf(y, (scores >= t).astype(int))[2]
        if f > best_f:
            best_t, best_f = t, f
    return float(best_t)


def count_hits(texts: pd.Series, lexikon: dict[str, list[str]]) -> pd.DataFrame:
    out = {}
    for lab, pats in lexikon.items():
        rx = re.compile("|".join(f"(?:{p})" for p in pats))
        out[lab] = texts.map(lambda t, rx=rx: len(rx.findall(t)))
    return pd.DataFrame(out, index=texts.index)


# ----------------------------------------------------------------------------
# Klassifikatoren
# ----------------------------------------------------------------------------
def fit_dictionary(hits_train: pd.DataFrame, y_train: pd.DataFrame) -> dict[str, int]:
    cands = np.arange(1, MAX_TREFFER_SCHWELLE + 1)
    return {lab: int(best_threshold(y_train[lab].values, hits_train[lab].values, cands)) for lab in hits_train}


def predict_dictionary(hits: pd.DataFrame, thresholds: dict[str, int]) -> pd.DataFrame:
    return pd.DataFrame({lab: (hits[lab] >= t).astype(int) for lab, t in thresholds.items()}, index=hits.index)


def fit_lr(X_train, y_train: pd.DataFrame, groups: np.ndarray):
    """Ein binäres LR-Modell je Label, Schwelle per gruppierter CV."""
    models, thresholds = {}, {}
    gkf = GroupKFold(n_splits=CV_FOLDS)
    cands = np.round(np.arange(0.05, 0.96, 0.025), 3)
    for lab in y_train.columns:
        y = y_train[lab].values
        if y.sum() < CV_FOLDS:  # zu selten -> kein Modell
            continue
        oof = np.zeros(len(y))
        for tr, va in gkf.split(X_train, y, groups):
            if y[tr].sum() == 0:
                continue
            m = LogisticRegression(C=LR_C, class_weight="balanced", solver="liblinear", max_iter=2000)
            m.fit(X_train[tr], y[tr])
            oof[va] = m.predict_proba(X_train[va])[:, 1]
        thresholds[lab] = best_threshold(y, oof, cands)
        m = LogisticRegression(C=LR_C, class_weight="balanced", solver="liblinear", max_iter=2000)
        m.fit(X_train, y)
        models[lab] = m
    return models, thresholds


def predict_lr(models, thresholds, X, index, labels) -> tuple[pd.DataFrame, pd.DataFrame]:
    proba = pd.DataFrame(0.0, index=index, columns=labels)
    for lab, m in models.items():
        proba[lab] = m.predict_proba(X)[:, 1]
    pred = pd.DataFrame({lab: (proba[lab] >= thresholds.get(lab, 2.0)).astype(int) for lab in labels}, index=index)
    return pred, proba


def top_terms(models, vectorizer, n: int) -> dict[str, list[str]]:
    vocab = np.array(vectorizer.get_feature_names_out())
    return {lab: list(vocab[np.argsort(m.coef_[0])[::-1][:n]]) for lab, m in models.items()}


# ----------------------------------------------------------------------------
# Auswertung
# ----------------------------------------------------------------------------
def label_metrics(y: pd.DataFrame, preds: dict[str, pd.DataFrame], labels: list[str]) -> pd.DataFrame:
    rows = []
    for lab in labels:
        row = {"Label": lab, "n LLM": int(y[lab].sum()), "Anteil LLM": y[lab].mean()}
        for name, p in preds.items():
            pr, rc, f1 = prf(y[lab].values, p[lab].values)
            row[f"Anteil {name}"] = p[lab].mean()
            row[f"P {name}"], row[f"R {name}"], row[f"F1 {name}"] = pr, rc, f1
        rows.append(row)
    return pd.DataFrame(rows)


def phase_shares(meta: pd.DataFrame, y: pd.DataFrame, preds: dict[str, pd.DataFrame], labels: list[str]) -> pd.DataFrame:
    vor, nach = (meta["phase"] == "vor").values, (meta["phase"] == "nach").values
    rows = []
    for lab in labels:
        row = {"Label": lab}
        for name, d in {"LLM": y, **preds}.items():
            v, n = d[lab].values[vor].mean(), d[lab].values[nach].mean()
            row[f"{name} vor"], row[f"{name} nach"], row[f"{name} Δ"] = v, n, n - v
        rows.append(row)
    return pd.DataFrame(rows)


def medientyp_deltas(meta, y, preds, labels) -> pd.DataFrame:
    rows = []
    for mt in sorted(meta["medientyp"].unique()):
        m = (meta["medientyp"] == mt).values
        vor = m & (meta["phase"] == "vor").values
        nach = m & (meta["phase"] == "nach").values
        for lab in labels:
            row = {"Medientyp": mt, "Label": lab, "n vor/nach": f"{vor.sum()}/{nach.sum()}"}
            for name, d in {"LLM": y, **preds}.items():
                row[f"Δ {name}"] = d[lab].values[nach].mean() - d[lab].values[vor].mean()
            rows.append(row)
    return pd.DataFrame(rows)


def series_correlations(meta, y, preds, labels) -> pd.DataFrame:
    """Korrelation Wochenanteile und Kanal-Δ (nach − vor) zwischen LLM und Klassifikator."""
    week = pd.to_datetime(meta["datum_lokal"]).dt.to_period("W").astype(str)
    cnt = meta.groupby(["channel_id", "phase"]).size().unstack(fill_value=0)
    ok_channels = cnt.index[(cnt.get("vor", 0) >= MIN_SEG_KANAL_PHASE) & (cnt.get("nach", 0) >= MIN_SEG_KANAL_PHASE)]
    in_ok = meta["channel_id"].isin(ok_channels).values
    rows = []
    for lab in labels:
        row = {"Label": lab}
        llm_w = y[lab].groupby(week.values).mean()
        llm_c = y[lab][in_ok].groupby([meta["channel_id"][in_ok], meta["phase"][in_ok]]).mean().unstack()
        llm_cd = llm_c["nach"] - llm_c["vor"]
        for name, p in preds.items():
            pw = p[lab].groupby(week.values).mean()
            pc = p[lab][in_ok].groupby([meta["channel_id"][in_ok], meta["phase"][in_ok]]).mean().unstack()
            pcd = pc["nach"] - pc["vor"]
            row[f"r Woche {name}"] = llm_w.corr(pw)
            row[f"r Kanal-Δ {name}"] = llm_cd.corr(pcd)
            row[f"Vorzeichen Kanal-Δ gleich {name}"] = float((np.sign(llm_cd) == np.sign(pcd)).mean())
        rows.append(row)
    return pd.DataFrame(rows), len(ok_channels), week.nunique()


def hauptthema_from_scores(scores: pd.DataFrame, pred: pd.DataFrame) -> pd.Series:
    """Hauptthema = höchster Score unter den vorhergesagten Themen; sonst unpolitisch."""
    s = scores.where(pred.astype(bool), -np.inf).drop(columns="unpolitisch", errors="ignore")
    out = s.idxmax(axis=1)
    return out.where(np.isfinite(s.max(axis=1)), "unpolitisch")


# ----------------------------------------------------------------------------
# Split und Anpassung
# ----------------------------------------------------------------------------
def kanal_folds(df: pd.DataFrame) -> pd.Series:
    """Kanal -> Fold; je Medientyp nach Segmentzahl in Schlangen-Reihenfolge verteilt."""
    rng = np.random.default_rng(SEED)
    n = df.groupby(["medientyp", "channel_id"]).size().reset_index(name="n")
    fold_of = {}
    for _, g in n.groupby("medientyp"):
        g = g.sort_values("n", ascending=False)
        offset = int(rng.integers(KANAL_FOLDS))
        for i, ch in enumerate(g["channel_id"]):
            r, k = divmod(i, KANAL_FOLDS)
            f = k if r % 2 == 0 else KANAL_FOLDS - 1 - k
            fold_of[ch] = (f + offset) % KANAL_FOLDS
    return df["channel_id"].map(fold_of)


def fit_predict(df, Y_t, Y_a, hits_t, hits_a, tr_idx, te_idx, inner_groups) -> dict:
    """Beide Klassifikatoren auf tr_idx anpassen und für te_idx vorhersagen."""
    tr = df.iloc[tr_idx]
    pol = [l for l in THEMEN if l != "unpolitisch"]
    # --- A) Diktionär
    thr_dict_t = fit_dictionary(hits_t.iloc[tr_idx], Y_t.iloc[tr_idx][pol])
    war_tr = Y_t.iloc[tr_idx]["krieg_ukraine"].values == 1
    thr_dict_a = fit_dictionary(hits_a.iloc[tr_idx][war_tr], Y_a.iloc[tr_idx][war_tr][list(LEXIKON_ASPEKTE)])
    hte, hae = hits_t.iloc[te_idx], hits_a.iloc[te_idx]
    pd_t = predict_dictionary(hte, thr_dict_t)
    pd_t["unpolitisch"] = (pd_t[pol].sum(axis=1) == 0).astype(int)
    pd_a = predict_dictionary(hae, thr_dict_a)
    pd_a["sonstiges"] = 0
    dict_scores = hte / pd.Series(thr_dict_t)  # normierte Treffer als Score fürs Hauptthema
    dict_scores["unpolitisch"] = 0.0
    # --- B) TF-IDF + LR
    vec = TfidfVectorizer(min_df=TFIDF_MIN_DF, max_df=0.5, ngram_range=(1, TFIDF_NGRAM_MAX),
                          sublinear_tf=True, max_features=150_000, token_pattern=r"(?u)\b\w\w+\b")
    X_tr = vec.fit_transform(tr["text"])
    X_te = vec.transform(df["text"].iloc[te_idx])
    g_tr = inner_groups[tr_idx]
    lr_t_models, lr_t_thr = fit_lr(X_tr, Y_t.iloc[tr_idx], g_tr)
    lr_a_models, lr_a_thr = fit_lr(X_tr[war_tr], Y_a.iloc[tr_idx][war_tr], g_tr[war_tr])
    te_index = df.index[te_idx]
    plr_t, prob_t = predict_lr(lr_t_models, lr_t_thr, X_te, te_index, THEMEN)
    plr_a, _ = predict_lr(lr_a_models, lr_a_thr, X_te, te_index, ASPEKTE)
    return {"pd_t": pd_t[THEMEN], "pd_a": pd_a[ASPEKTE], "dict_scores": dict_scores, "plr_t": plr_t,
            "plr_a": plr_a, "prob_t": prob_t, "thr_dict_t": thr_dict_t, "thr_dict_a": thr_dict_a,
            "top_t": top_terms(lr_t_models, vec, N_TOP_TERME), "top_a": top_terms(lr_a_models, vec, N_TOP_TERME)}


def vergleich_video_modus(out_kanal: pd.DataFrame) -> pd.DataFrame | None:
    """F1 je Label: Video-Split (vorhandene CSV) vs. Kanal-Holdout."""
    f = OUTPUT_DIR / "test_vorhersagen.csv"
    if not f.exists():
        return None
    out_video = pd.read_csv(f, encoding="utf-8-sig")
    rows = []
    for typ, labs, pre in [("Thema", THEMEN, ""), ("Aspekt (E2E)", ASPEKTE, "a_")]:
        for lab in labs:
            row = {"Label": lab, "Typ": typ}
            for modus, o in [("Video", out_video), ("Kanal", out_kanal)]:
                for k, name in [("dict", "Dict"), ("lr", "LR")]:
                    row[f"F1 {name} {modus}"] = prf(o[f"llm_{pre}{lab}"].values, o[f"{k}_{pre}{lab}"].values)[2]
            rows.append(row)
    d = pd.DataFrame(rows)
    return d[["Label", "Typ", "F1 Dict Video", "F1 Dict Kanal", "F1 LR Video", "F1 LR Kanal"]]


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main() -> None:
    if not INPUT_CSV.exists():
        raise SystemExit(f"Eingabedatei fehlt: {INPUT_CSV}")
    if SPLIT_MODUS not in ("video", "kanal"):
        raise SystemExit('SPLIT_MODUS muss "video" oder "kanal" sein.')
    if not 0 < TEST_ANTEIL < 1:
        raise SystemExit("TEST_ANTEIL muss zwischen 0 und 1 liegen.")
    if not (isinstance(KANAL_FOLDS, int) and 2 <= KANAL_FOLDS <= 5):
        raise SystemExit("KANAL_FOLDS muss eine ganze Zahl zwischen 2 und 5 sein.")
    if CV_FOLDS < 2 or LR_C <= 0 or TFIDF_MIN_DF < 1 or TFIDF_NGRAM_MAX not in (1, 2, 3):
        raise SystemExit("CV_FOLDS >= 2, LR_C > 0, TFIDF_MIN_DF >= 1, TFIDF_NGRAM_MAX in {1,2,3} erforderlich.")
    if MAX_TREFFER_SCHWELLE < 1 or MIN_SEG_KANAL_PHASE < 1 or N_TOP_TERME < 1:
        raise SystemExit("MAX_TREFFER_SCHWELLE, MIN_SEG_KANAL_PHASE, N_TOP_TERME müssen >= 1 sein.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "" if SPLIT_MODUS == "video" else "_kanal_holdout"

    df = pd.read_csv(INPUT_CSV, encoding="utf-8")
    df = df[df["kodierbar"] == 1].reset_index(drop=True)
    df["text"] = df["text"].fillna("").str.lower()
    for col in ["themen", "krieg_aspekte"]:
        df[col] = df[col].apply(ast.literal_eval)
    Y_t = multi_hot(df["themen"], THEMEN)
    Y_a = multi_hot(df["krieg_aspekte"], ASPEKTE)
    hits_t = count_hits(df["text"], LEXIKON_THEMEN)
    hits_a = count_hits(df["text"], LEXIKON_ASPEKTE)

    if SPLIT_MODUS == "video":
        split = GroupShuffleSplit(n_splits=1, test_size=TEST_ANTEIL, random_state=SEED)
        folds = [next(split.split(df, groups=df["video_id"]))]
        inner_groups = df["video_id"].values
        fold_col = pd.Series(0, index=df.index)
    else:
        fold_col = kanal_folds(df)
        folds = [(np.where(fold_col != f)[0], np.where(fold_col == f)[0]) for f in range(KANAL_FOLDS)]
        inner_groups = df["channel_id"].values

    res = []
    for i, (tr_idx, te_idx) in enumerate(folds, 1):
        print(f"Fold {i}/{len(folds)}: Train {len(tr_idx)} Segmente / {df.iloc[tr_idx].channel_id.nunique()} Kanäle, "
              f"Test {len(te_idx)} / {df.iloc[te_idx].channel_id.nunique()} Kanäle", flush=True)
        res.append(fit_predict(df, Y_t, Y_a, hits_t, hits_a, tr_idx, te_idx, inner_groups))
    cat = lambda k: pd.concat([r[k] for r in res]).sort_index()
    pd_t, pd_a, dict_scores = cat("pd_t"), cat("pd_a"), cat("dict_scores")
    plr_t, plr_a, prob_t = cat("plr_t"), cat("plr_a"), cat("prob_t")
    te = df.loc[pd_t.index]
    n_train = len(folds[0][0])

    # --- Testset-Auswertung -------------------------------------------------
    meta = te[["segment_id", "video_id", "channel_id", "channel_title", "medientyp", "phase", "datum_lokal"]]
    yT, yA = Y_t.loc[te.index], Y_a.loc[te.index]
    preds_t = {"Dict": pd_t, "LR": plr_t}
    # End-to-End-Aspekte: nur wo der Klassifikator selbst Krieg erkennt
    preds_a_e2e = {"Dict": pd_a.mul(pd_t["krieg_ukraine"], axis=0), "LR": plr_a.mul(plr_t["krieg_ukraine"], axis=0)}
    war_te = yT["krieg_ukraine"].values == 1
    preds_a_cond = {"Dict": pd_a[war_te], "LR": plr_a[war_te]}

    m_t = label_metrics(yT, preds_t, THEMEN)
    m_a_cond = label_metrics(yA[war_te], preds_a_cond, ASPEKTE)
    m_a_e2e = label_metrics(yA, preds_a_e2e, ASPEKTE)

    ht_llm = te["hauptthema"].values
    ht_dict = hauptthema_from_scores(dict_scores, pd_t).values
    ht_lr = hauptthema_from_scores(prob_t, plr_t).values
    acc_dict, acc_lr = (ht_dict == ht_llm).mean(), (ht_lr == ht_llm).mean()

    ph_t = phase_shares(meta, yT, preds_t, THEMEN)
    # Aspekte: Anteil an ALLEN Segmenten (End-to-End), damit LLM und Klassifikator vergleichbar
    ph_a = phase_shares(meta, yA, preds_a_e2e, ASPEKTE)
    mt_t = medientyp_deltas(meta, yT, preds_t, ["krieg_ukraine", "corona", "energie", "wirtschaft", "migration"])
    mt_a = medientyp_deltas(meta, yA, preds_a_e2e, ["sanktionen", "waffenlieferungen", "energie_preise_inland",
                                                     "verhandlungen_diplomatie", "medien_desinformation"])
    corr_t, n_ch, n_wk = series_correlations(meta, yT, preds_t, THEMEN)
    corr_a, _, _ = series_correlations(meta, yA, preds_a_e2e, ASPEKTE)

    # --- Ausgabe ------------------------------------------------------------
    out = meta.copy()
    out["fold"] = fold_col.loc[te.index].values + (0 if SPLIT_MODUS == "video" else 1)
    for lab in THEMEN:
        out[f"llm_{lab}"], out[f"dict_{lab}"], out[f"lr_{lab}"] = yT[lab].values, pd_t[lab].values, plr_t[lab].values
    for lab in ASPEKTE:
        out[f"llm_a_{lab}"], out[f"dict_a_{lab}"], out[f"lr_a_{lab}"] = (
            yA[lab].values, preds_a_e2e["Dict"][lab].values, preds_a_e2e["LR"][lab].values)
    out["hauptthema_llm"], out["hauptthema_dict"], out["hauptthema_lr"] = ht_llm, ht_dict, ht_lr
    out.to_csv(OUTPUT_DIR / f"test_vorhersagen{suffix}.csv", index=False, encoding="utf-8-sig")

    sel = lambda d, keep: d[[c for c in d.columns if any(c.startswith(k) for k in keep)]]
    if SPLIT_MODUS == "video":
        titel = "# Keyword-Annäherung der LLM-Themenklassifikation (Segmentebene)"
        split_txt = (f"Split nach Video gruppiert, Seed {SEED}: **Train {n_train} Segmente / "
                     f"{df.iloc[folds[0][0]].video_id.nunique()} Videos, Test {len(te)} Segmente / "
                     f"{te.video_id.nunique()} Videos** (Test vor/nach: "
                     f"{(meta.phase == 'vor').sum()}/{(meta.phase == 'nach').sum()}).")
        cv_txt = "gruppierter CV (nach Video)"
    else:
        titel = "# Keyword-Annäherung der LLM-Themenklassifikation – Kanal-Holdout"
        split_txt = (f"**Kanal-Holdout per Kreuzanpassung, {KANAL_FOLDS} Folds** (Seed {SEED}): Die "
                     f"{df.channel_id.nunique()} Kanäle sind je Medientyp auf die Folds verteilt; jeder Fold wird "
                     f"mit Modellen vorhergesagt, die die Kanäle dieses Folds **nie gesehen** haben. Testset = alle "
                     f"{len(te)} Segmente (vor/nach: {(meta.phase == 'vor').sum()}/{(meta.phase == 'nach').sum()}).")
        cv_txt = "nach Kanal gruppierter CV"
    L = [titel, "",
         f"Quelle: `{INPUT_CSV.relative_to(ROOT).as_posix()}` (nur `kodierbar == 1`).  ", split_txt, "",
         "- **Dict** = Stichwort-Diktionär (Regex-Stämme aus dem Codebuch, Mindest-Trefferzahl je Label auf Train F1-optimal).",
         f"- **LR** = TF-IDF (1–{TFIDF_NGRAM_MAX}-Gramme) + logistische Regression je Label, Schwelle per {CV_FOLDS}-facher {cv_txt} auf Train.",
         "- Alle Kennzahlen unten auf dem **Testset**. Anteile = ungewichtete Segmentanteile.", ""]
    if SPLIT_MODUS == "kanal":
        fa = (df.assign(fold=fold_col + 1).groupby(["fold", "medientyp", "channel_title"]).size()
              .reset_index(name="Segmente"))
        L += ["### Kanal-Folds", "",
              md_table(fa.groupby(["fold", "medientyp"]).agg(
                  Kanäle=("channel_title", "size"), Segmente=("Segmente", "sum"),
                  Namen=("channel_title", lambda s: ", ".join(s))).reset_index()), ""]
        vgl = vergleich_video_modus(out)
        if vgl is not None:
            L += ["## 0. Vergleich: Video-Split vs. Kanal-Holdout (F1)", "",
                  "Video-Split = Testset aus `test_vorhersagen.csv` (Kanäle auch im Training); "
                  "Kanal-Holdout = dieser Lauf (alle Segmente, Kanäle nie im Training). Aspekte End-to-End.", "",
                  md_table(vgl), ""]
    L += ["## 1. Themen – Segmentgüte", "",
          md_table(sel(m_t, ["Label", "n LLM", "Anteil", "F1", "P ", "R "])), "",
          f"**Hauptthema** (eine Kategorie je Segment): Übereinstimmung mit LLM – Dict {acc_dict:.1%}, LR {acc_lr:.1%}.", "",
          "## 2. Themen – Trendtreue vor/nach Kriegsbeginn", "",
          "Anteil der Segmente mit dem Thema vor (01.01.–23.02.2022) und nach (24.02.–30.04.2022) Kriegsbeginn.", "",
          md_table(ph_t, "{:.3f}"), "",
          f"Korrelation der Wochenanteile ({n_wk} Wochen) und der Kanal-Veränderungen nach − vor "
          f"({n_ch} Kanäle mit ≥ {MIN_SEG_KANAL_PHASE} Testsegmenten je Phase):", "",
          md_table(corr_t), "",
          "### Veränderung nach − vor je Medientyp (ausgewählte Themen)", "",
          md_table(mt_t, "{:+.3f}"), "",
          "## 3. Kriegsaspekte – Segmentgüte", "",
          "### 3a. Bedingt: nur Testsegmente, die laut LLM `krieg_ukraine` enthalten", "",
          md_table(sel(m_a_cond, ["Label", "n LLM", "Anteil", "F1", "P ", "R "])), "",
          "### 3b. End-to-End: alle Testsegmente; Aspekt nur, wenn der Klassifikator selbst Krieg erkennt", "",
          md_table(sel(m_a_e2e, ["Label", "n LLM", "Anteil", "F1"])), "",
          "`sonstiges` hat kein Diktionär (Residualkategorie).", "",
          "## 4. Kriegsaspekte – Trendtreue (Anteil an allen Segmenten, End-to-End)", "",
          md_table(ph_a, "{:.3f}"), "",
          md_table(corr_a), "",
          "### Veränderung nach − vor je Medientyp (ausgewählte Aspekte)", "",
          md_table(mt_a, "{:+.3f}"), "",
          "## 5. Gewählte Diktionär-Schwellen (Mindest-Treffer je Segment)", ""]
    thr = pd.DataFrame({"Label": list(res[0]["thr_dict_t"]) + list(res[0]["thr_dict_a"]),
                        "Typ": ["Thema"] * len(res[0]["thr_dict_t"]) + ["Aspekt"] * len(res[0]["thr_dict_a"])})
    for i, r in enumerate(res, 1):
        col = "Schwelle" if len(res) == 1 else f"Schwelle Fold {i}"
        thr[col] = list(r["thr_dict_t"].values()) + list(r["thr_dict_a"].values())
    L += [md_table(thr), "", "## 6. Top-Terme der logistischen Regression (datengetriebene Stichwortlisten)", ""]
    if len(res) > 1:
        L += ["Aus dem Modell von Fold 1 (trainiert ohne die Kanäle von Fold 1).", ""]
    for lab, terms in {**res[0]["top_t"], **{f"aspekt:{k}": v for k, v in res[0]["top_a"].items()}}.items():
        L.append(f"- **{lab}**: {', '.join(terms)}")
    L += ["", f"Dateien: `test_vorhersagen{suffix}.csv` (LLM-Labels und beide Vorhersagen je Testsegment)."]
    (OUTPUT_DIR / f"bericht{suffix}.md").write_text("\n".join(L), encoding="utf-8")
    print(f"Bericht: {OUTPUT_DIR / f'bericht{suffix}.md'}")


if __name__ == "__main__":
    main()

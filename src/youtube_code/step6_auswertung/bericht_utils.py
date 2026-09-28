# -*- coding: utf-8 -*-
"""
bericht_utils.py

Gemeinsame Regressions-Bausteine fuer alle Kanal-FE + Post-Dummy-Berichte
in diesem Ordner (frage1_populismus_bericht.py, frage1_stance_bericht.py,
frage2_erfolg_bericht.py, frage3_populismus_erfolg_bericht.py). Reiner
Funktions-Umzug aus frage1_populismus_bericht.py (siehe .claude/plans/
success_analysis.md, Abschnitt "Architekturentscheidung") - post_dummy_test()
und interaktions_test() waren dort und in frage1_stance_bericht.py
wortidentisch dupliziert; ab jetzt importieren alle Berichte von hier
(bare sibling import: `from bericht_utils import post_dummy_test,
interaktions_test`, direkt im Ordner ausgefuehrt).

Beide Funktionen erwarten ein DataFrame auf Kanal x Periode-Ebene (eine
Zeile je Kanal-Monat bzw. Kanal-Quartal, NICHT je einzelnes Video/Segment)
- die jeweils aufrufenden Berichte sind fuer diese Aggregation zustaendig
(aggregiere_kanal_periode() in den Frage-1-Berichten, bereits fertig
aggregierte Eingabedateien bei Frage 2/3).

Seit 2026-09-08 zusaetzlich dauer_teilstichprobe() (.claude/Aufgaben.md,
letzter Absatz: Videolaenge als Stoerfaktor, Nutzervorgabe "Integriere die
Videodauer... als Kontrollvariable... und eine laengen-eingegrenzte
Sensitivitaets-Teilstichprobe") - gemeinsame Filterfunktion fuer die
DAUER_TEILSTICHPROBEN-Konfiguration in frage4_kriegspraemie_medientyp_
bericht.py und populismuspraemie_kriegsvideos_bericht.py, auf Video-Ebene
(operiert auf duration_seconds aus channel_video_erfolg.csv, seit
prepare_success_metrics.py::ergaenze_videodauer()).

Ebenfalls seit 2026-09-08 berechne_upload_dichte() (Nutzervorgabe "Bau jetzt
die Upload-Dichte als Kontrollvariable ein", als Antwort auf die Frage nach
weiteren Kontrollvariablen) - gemeinsame Aggregationsfunktion fuer beide
Skripte: wie viele ANDERE Videos hat ein Kanal INSGESAMT (alle Themen, nicht
nur Kriegsvideos) in einem Zeitfenster um das jeweilige Video veroeffentlicht -
ein Mass fuer die Konkurrenz um Aufmerksamkeit INNERHALB des Kanals. Anders
als age_days wird diese Variable NICHT durch die bestehenden Perioden-Fixed-
Effects redundant, weil sie kanalspezifisch INNERHALB einer Periode variiert
(die Periode selbst ist bereits ueber C(periode)/Zeitperioden-Bins
kontrolliert, die Kanalaktivitaet INNERHALB dieser Periode nicht) - wird
deshalb, anders als age_days/category_id, in BEIDEN Skripten ergaenzt.

Seit 2026-09-09 (Nutzervorgabe: "es kommt auf Videos kurz vor und nach dem
jeweiligen Video an") gibt es ZWEI Varianten statt einer: berechne_upload_
dichte() zaehlt jetzt fenster-basiert (die Videos desselben Kanals, deren
published_at innerhalb von +/- FENSTER_STUNDEN um das published_at des
jeweiligen Videos liegt - direkte zeitliche Nachbarn statt gemeinsame
Periodenzugehoerigkeit, da eine Periodengrenze wie ein Monatswechsel sonst
benachbarte Videos, die nur Stunden auseinander lagen, kuenstlich in
unterschiedliche Zellen trennte) und liefert damit eine VIDEO-eigene
Kennzahl, zum Mergen ueber (channel_id, video_id). Die URSPRUENGLICHE,
periodenbasierte Zaehlung (alle Videos derselben rel_monat/rel_quartal-
Periode, Kennzahl auf Kanal x Periode-Ebene) bleibt als eigene Funktion
berechne_upload_dichte_periode() bestehen - wird weiterhin gebraucht fuer
Regressionen, deren Beobachtungseinheit bereits Kanal x Periode ist (z.B.
Kanal-Monat-Panels), wo es kein einzelnes "jeweiliges Video" gibt, um ein
Zeitfenster darum zu legen (siehe dortiger Docstring fuer die genaue
Abgrenzung, wann welche Funktion zum Einsatz kommt).

Ebenfalls seit 2026-09-08 vergleichsgruppe_filter() (.claude/plans/
frage4_kriegspraemie_vergleichsgruppen_und_beobachtungseinheiten.md,
Nutzervorgabe "die 'sonstigen Videos' sollen wahlweise ALLE sonstigen Videos
ODER nur andere politische Videos sein"): schraenkt die Vergleichsgruppe
("sonstige Videos", treatment_spalte == 0) wahlweise auf Videos mit
bestaetigter Politik-Klassifikation ein - das Kriegsvideo-Flag selbst
(treatment_spalte == 1) bleibt in ALLEN Modi immer ungefiltert (konsistent
mit der bereits etablierten Konvention aus frage4_kriegspraemie_relative_
views_plots.py::andere_politische_videos_topic). Wird auf Video-Ebene, VOR
jeder Zellenaggregation, angewendet - Aufrufer (frage4_kriegspraemie_
medientyp_bericht.py, Baustein 1-4) sind fuer das Mergen der Politik-
Klassifikation in die aufrufende Spalte zustaendig.

Seit 2026-09-09 (Nutzervorgabe "als Robustheitscheck auch meine LLM-
Klassifikation aus dem screening_state mit politics_final verwenden")
zwei gleichberechtigte Politik-Quellen statt einer, ueber denselben Modus-
Namensraum unterschieden: modus="nur_politische_videos" (Default-Spalte
"ist_politisches_video", topic_categories-basiert ueber
video_registry.politics_topic_lookup(), hohe Abdeckung ~99,7%) und
modus="nur_politische_videos_llm" (Aufrufer uebergibt politik_spalte=
"ist_politisches_video_llm", screening_state_store.get_state()["politics_final"]
== 1 - manuelle/LLM-Klassifikation aus dem longitudinalen Politik-Screening,
deutlich geringere Abdeckung nur ~12% der Videos, siehe Docstring
lade_video_daten() in frage4_kriegspraemie_medientyp_bericht.py). Beide Modi
teilen sich dieselbe Filterlogik (treatment_spalte == 0 UND NICHT
politik_spalte verwerfen), unterscheiden sich nur in der Quelle/Spalte der
Politik-Klassifikation.
"""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


# =========================================================
# BAUSTEIN 3: Laengenbeschraenkte Sensitivitaets-Teilstichprobe
# =========================================================

def dauer_teilstichprobe(df, minuten_min, minuten_max, spalte_dauer_sekunden="duration_seconds"):
    """Filtert df auf Videos mit Dauer im geschlossenen Intervall
    [minuten_min, minuten_max] Minuten (minuten_max=None -> keine Obergrenze).
    Gemeinsame Basis fuer die DAUER_TEILSTICHPROBEN-Sensitivitaetslaeufe in
    frage4_kriegspraemie_medientyp_bericht.py (dort auf Video-Ebene VOR
    aggregiere_zellen() angewendet) und populismuspraemie_kriegsvideos_
    bericht.py (dort auf der bereits auf Kriegsvideos gefilterten Video-Ebene).
    Videos ohne bekannte Dauer (NaN in spalte_dauer_sekunden) fallen automatisch
    raus (NaN-Vergleiche sind immer False)."""
    dauer_minuten = df[spalte_dauer_sekunden] / 60
    maske = dauer_minuten >= minuten_min
    if minuten_max is not None:
        maske &= dauer_minuten <= minuten_max
    gefiltert = df[maske]
    obergrenze = minuten_max if minuten_max is not None else "unbegrenzt"
    print(f"  [Dauerfilter] {minuten_min}-{obergrenze} Min: {len(df)} -> {len(gefiltert)} Zeilen.")
    return gefiltert


# =========================================================
# BAUSTEIN 4: Upload-Dichte (Konkurrenz um Aufmerksamkeit im Kanal)
# =========================================================

# Fenstergroesse in Stunden fuer berechne_upload_dichte() (Nutzervorgabe: "wie viele
# Videos der Kanal in einem Zeitraum von 48 Stunden vor und nach dem jeweiligen Video
# hochgeladen hat") - symmetrisch um published_at, an einer Stelle gepflegt.
UPLOAD_DICHTE_FENSTER_STUNDEN = 48


def berechne_upload_dichte(video_ebene, channel_id_spalte="channel_id",
                            video_id_spalte="video_id", published_at_spalte="published_at",
                            fenster_stunden=UPLOAD_DICHTE_FENSTER_STUNDEN):
    """Zaehlt je Video, wie viele ANDERE Videos desselben Kanals - ALLE Themen, nicht
    nur Kriegsvideos (siehe Moduldocstring) - in einem symmetrischen Zeitfenster von
    +/- fenster_stunden um dessen published_at veroeffentlicht wurden (direkte
    zeitliche Nachbarn, seit 2026-09-09 statt der frueheren periodenbasierten
    Zaehlung, siehe Moduldocstring). `video_ebene` MUSS die volle, ungefilterte
    Video-Menge sein (nicht schon nach ist_kriegsvideo, Dauer-Teilstichprobe o.ae.
    gefiltert) - die Dichte soll die tatsaechliche Kanalaktivitaet abbilden, nicht nur
    die Aktivitaet innerhalb einer spaeteren (Teil-)Stichprobe. Videos ohne bekanntes
    published_at (NaN) bekommen NaN als Dichte (koennen weder selbst gezaehlt werden
    noch fuer andere Videos als Nachbar zaehlen). Gibt ein DataFrame mit
    [channel_id_spalte, video_id_spalte, 'upload_dichte', 'log_upload_dichte'] zurueck,
    zum Mergen auf (channel_id, video_id) durch den Aufrufer."""
    df = video_ebene[[channel_id_spalte, video_id_spalte, published_at_spalte]].copy()
    # utc=True normalisiert gemischte/fehlende Zeitzonenangaben einheitlich, tz_localize(None)
    # macht daraus tz-naive datetime64[ns] - .to_numpy() liefert sonst bei tz-aware Werten ein
    # Objekt-Array (dtype=object), auf dem numpy nicht subtrahieren/searchsorted kann.
    df[published_at_spalte] = pd.to_datetime(
        df[published_at_spalte], errors="coerce", utc=True
    ).dt.tz_localize(None)

    ohne_datum = df[published_at_spalte].isna()
    if ohne_datum.any():
        print(f"  [Upload-Dichte] {int(ohne_datum.sum())} von {len(df)} Videos ohne "
              f"bekanntes {published_at_spalte} -> Dichte = NaN.")

    fenster_ns = pd.Timedelta(hours=fenster_stunden).to_timedelta64()
    dichte_werte = pd.Series(np.nan, index=df.index)
    for _, gruppe in df[~ohne_datum].groupby(channel_id_spalte):
        gruppe = gruppe.sort_values(published_at_spalte)
        ts = gruppe[published_at_spalte].to_numpy()
        # Fuer jeden Zeitpunkt t: Anzahl anderer Zeitpunkte in [t - fenster, t + fenster].
        # searchsorted ist hier vektorisiert (Array als zweites Argument) - O(n log n)
        # je Kanal statt einer quadratischen Paarzaehlung.
        lo = np.searchsorted(ts, ts - fenster_ns, side="left")
        hi = np.searchsorted(ts, ts + fenster_ns, side="right")
        dichte_werte.loc[gruppe.index] = (hi - lo - 1).astype(float)  # -1: sich selbst nicht mitzaehlen

    df["upload_dichte"] = dichte_werte
    df["log_upload_dichte"] = np.log1p(df["upload_dichte"])
    return df[[channel_id_spalte, video_id_spalte, "upload_dichte", "log_upload_dichte"]]


def berechne_upload_dichte_periode(video_ebene, channel_id_spalte="channel_id", periode_spalte="rel_monat"):
    """Aeltere, periodenbasierte Variante von berechne_upload_dichte(): zaehlt je
    (channel_id_spalte, periode_spalte) die Gesamtzahl der Videos, die der Kanal in
    dieser Periode veroeffentlicht hat - ALLE Themen, nicht nur Kriegsvideos (siehe
    Moduldocstring). Bis 2026-09-09 war das die einzige Upload-Dichte-Funktion; seit
    dem Umstieg auf die fenster-basierte berechne_upload_dichte() (Nutzervorgabe: "es
    kommt auf Videos kurz vor und nach dem jeweiligen Video an") bleibt DIESE Funktion
    fuer Regressionen, deren Beobachtungseinheit bereits Kanal x Periode ist (z.B.
    Kanal-Monat-Panels wie frage1_populismus_bericht.py/frage3_populismus_erfolg_
    bericht.py) - dort gibt es kein einzelnes "jeweiliges Video", um ein Zeitfenster
    darum zu legen, sondern nur die Periode selbst als Kontext. berechne_upload_
    dichte() (Video-eigene Fenster-Kennzahl) ist dagegen fuer Regressionen auf Video-
    Ebene oder als Kontrollvariable, die anschliessend zu einem Zellmittel je Kanal-
    Periode-Zelle aggregiert wird (z.B. frage4_kriegspraemie_medientyp_bericht.py,
    populismuspraemie_kriegsvideos_bericht.py).

    Nutzervorgabe (.claude/Aufgaben.md, 2026-09-09): bei Regressionen auf Kanal-Monats-/
    Kanal-Quartals-Ebene sollen zur Robustheit BEIDE Varianten verwendet werden, aber
    NICHT gemeinsam als zwei Kontrollvariablen im selben Modell - stattdessen als zwei
    GETRENNTE, vollstaendige Durchlaeufe (analog zu DAUER_TEILSTICHPROBEN/
    VERGLEICHSGRUPPEN in frage4_kriegspraemie_medientyp_bericht.py): ein Durchlauf mit
    der simplen Zaehlung hier (berechne_upload_dichte_periode()) als Kontrollvariable,
    ein zweiter, davon unabhaengiger Durchlauf mit dem Zellmittel der Video-eigenen
    Fenster-Dichte (berechne_upload_dichte() je Video, dann per .groupby(...).mean()
    aggregiert) als Kontrollvariable - der zweite Durchlauf ist der Robustheitscheck
    zum ersten. Noch nicht umgesetzt, betrifft insbesondere frage1_populismus_
    bericht.py/frage2_erfolg_bericht.py/frage3_populismus_erfolg_bericht.py, sobald
    dort Upload-Dichte als Kontrolle ergaenzt wird.

    `video_ebene` MUSS wie dort die volle,
    ungefilterte Video-Menge sein. Gibt ein DataFrame mit [channel_id_spalte,
    periode_spalte, 'upload_dichte', 'log_upload_dichte'] zurueck, zum Mergen auf
    (channel_id, periode) durch den Aufrufer."""
    dichte = (video_ebene.groupby([channel_id_spalte, periode_spalte])
              .size().reset_index(name="upload_dichte"))
    dichte["log_upload_dichte"] = np.log1p(dichte["upload_dichte"])
    return dichte


# =========================================================
# BAUSTEIN 5: Vergleichsgruppen-Filter (alle sonstigen Videos vs. nur politische)
# =========================================================

# Erkannte "nur politische Videos"-Modi (siehe Moduldocstring) - beide teilen sich die
# Filterlogik unten, unterscheiden sich nur in der vom Aufrufer uebergebenen politik_spalte.
_POLITIK_MODI = {"nur_politische_videos", "nur_politische_videos_llm"}


def vergleichsgruppe_filter(df, modus, treatment_spalte="ist_kriegsvideo",
                             politik_spalte="ist_politisches_video"):
    """Filtert die Vergleichsgruppe (treatment_spalte == 0, also die "sonstigen Videos")
    wahlweise auf ALLE sonstigen Videos (modus="alle_videos", df unveraendert) oder NUR
    andere Videos mit bestaetigter Politik-Klassifikation (modus in _POLITIK_MODI:
    verwirft treatment_spalte == 0 UND NICHT politik_spalte). treatment_spalte == 1
    (Kriegsvideos) bleibt in ALLEN Modi IMMER erhalten - Kriegsvideos werden nie nach dem
    Politik-Kriterium gefiltert (Nutzervorgabe, siehe Moduldocstring, konsistent mit
    frage4_kriegspraemie_relative_views_plots.py::andere_politische_videos_topic).
    politik_spalte ist bool/NaN (z.B. aus video_registry.politics_topic_lookup() fuer
    modus="nur_politische_videos", oder politics_final == 1 fuer modus=
    "nur_politische_videos_llm", NaN jeweils bei fehlender Klassifikation) - NaN wird wie
    False behandelt (nicht bestaetigt politisch -> verworfen), da hier klassifikations-
    sicher gefiltert werden muss, nicht bloss ein "unbekannt" propagiert werden kann. Der
    Aufrufer waehlt ueber politik_spalte, WELCHE Politik-Quelle fuer den jeweiligen modus
    verwendet wird (siehe Moduldocstring fuer die beiden vorgesehenen Spalten). Operiert
    auf Video-Ebene, VOR jeder Zellenaggregation."""
    if modus == "alle_videos":
        return df
    if modus not in _POLITIK_MODI:
        raise ValueError(f"Unbekannter Vergleichsgruppen-Modus: {modus!r}")

    ist_politisch = df[politik_spalte].fillna(False).astype(bool)
    verwerfen = (df[treatment_spalte] == 0) & ~ist_politisch
    gefiltert = df[~verwerfen]
    print(f"  [Vergleichsgruppenfilter] {modus}: {len(df)} -> {len(gefiltert)} Zeilen "
          f"({int(verwerfen.sum())} nicht-politische sonstige Videos verworfen, "
          f"Kriegsvideos unangetastet).")
    return gefiltert


# =========================================================
# BAUSTEIN 1: Post-Dummy-Test (Gesamt oder je Gruppe)
# =========================================================

def post_dummy_test(df, dimension, spalte_periode, bezeichnung="gesamt"):
    """Kanal-FE + EIN Post-Dummy (post = periode >= 0), SE geclustert auf
    Kanalebene. Gibt ein dict mit Koeffizient/SE/p/n zurueck, oder None wenn
    nicht schaetzbar (z.B. nur eine Seite der Periode vorhanden)."""

    daten = df.dropna(subset=[dimension]).copy()
    daten["channel_id"] = daten["channel_id"].astype(str)
    daten["y"] = daten[dimension]
    daten["post"] = (daten[spalte_periode] >= 0).astype(int)

    n_kanaele = daten["channel_id"].nunique()
    if daten["post"].nunique() < 2 or n_kanaele < 2:
        print(f"  [Skip][{bezeichnung}] zu wenig Variation (Kanaele={n_kanaele}) fuer post_dummy_test.")
        return None

    modell_reduziert = smf.ols("y ~ C(channel_id)", data=daten).fit()
    modell = smf.ols("y ~ C(channel_id) + post", data=daten).fit(
        cov_type="cluster", cov_kwds={"groups": daten["channel_id"]}
    )

    partielles_r2 = (modell_reduziert.ssr - modell.ssr) / modell_reduziert.ssr

    return {
        "gruppe": bezeichnung,
        "n_beobachtungen": len(daten),
        "n_kanaele": n_kanaele,
        "mittel_vorkrieg": daten.loc[daten["post"] == 0, "y"].mean(),
        "mittel_nachkrieg": daten.loc[daten["post"] == 1, "y"].mean(),
        "koeffizient_post": modell.params["post"],
        "se": modell.bse["post"],
        "p": modell.pvalues["post"],
        "partielles_r2": partielles_r2,
    }


# =========================================================
# BAUSTEIN 2: Interaktionstest (Post x Gruppe)
# =========================================================

def interaktions_test(df, dimension, spalte_periode, gruppen_spalte, gruppen_werte, min_kanaele_je_gruppe=5):
    """Ein Modell ueber ALLE Kanaele der uebergebenen Gruppen: Kanal-FE + post +
    post:Gruppe-Interaktion (bewusst OHNE eigenen Gruppen-Haupteffekt, da
    Gruppenzugehoerigkeit zeitkonstant ist und daher vollstaendig mit den
    Kanal-FE kollinear waere). Gemeinsamer F-Test: sind alle
    post:Gruppe-Interaktionsterme gemeinsam 0 -> unterscheidet sich der
    Post-Effekt zwischen den Gruppen? min_kanaele_je_gruppe: unterhalb dieser
    Kanalzahl wird eine Gruppe aus dem Test ausgeschlossen (Aufrufer steuert
    das ueber ihre eigene MIN_KANAELE_JE_GRUPPE-Konstante)."""

    daten = df.dropna(subset=[dimension, gruppen_spalte]).copy()
    daten = daten[daten[gruppen_spalte].isin(gruppen_werte)]
    daten["channel_id"] = daten["channel_id"].astype(str)
    daten["y"] = daten[dimension]
    daten["post"] = (daten[spalte_periode] >= 0).astype(int)

    vorhandene_gruppen = [g for g in gruppen_werte if (daten[gruppen_spalte] == g).any()
                          and daten.loc[daten[gruppen_spalte] == g, "channel_id"].nunique() >= min_kanaele_je_gruppe]
    if len(vorhandene_gruppen) < 2:
        print(f"  [Skip][Interaktion {gruppen_spalte}] zu wenig Gruppen mit >= "
              f"{min_kanaele_je_gruppe} Kanaelen ({vorhandene_gruppen}).")
        return None
    daten = daten[daten[gruppen_spalte].isin(vorhandene_gruppen)]

    if daten["post"].nunique() < 2 or daten["channel_id"].nunique() < 2:
        print(f"  [Skip][Interaktion {gruppen_spalte}] zu wenig Variation.")
        return None

    referenz = vorhandene_gruppen[0]
    daten[gruppen_spalte] = pd.Categorical(daten[gruppen_spalte], categories=vorhandene_gruppen)

    formel = f"y ~ C(channel_id) + post + post:C({gruppen_spalte}, Treatment(reference='{referenz}'))"
    modell = smf.ols(formel, data=daten).fit(
        cov_type="cluster", cov_kwds={"groups": daten["channel_id"]}
    )

    interaktions_terme = [p for p in modell.params.index if p.startswith("post:C(")]
    if not interaktions_terme:
        print(f"  [Skip][Interaktion {gruppen_spalte}] keine Interaktionsterme im Modell.")
        return None

    hypothese = ", ".join(f"{p} = 0" for p in interaktions_terme)
    f_test = modell.f_test(hypothese)

    return {
        "referenzgruppe": referenz,
        "gruppen": vorhandene_gruppen,
        "n_beobachtungen": len(daten),
        "n_kanaele": daten["channel_id"].nunique(),
        "f_stat": float(f_test.fvalue),
        "df_num": int(f_test.df_num),
        "df_denom": int(f_test.df_denom),
        "p": float(f_test.pvalue),
    }

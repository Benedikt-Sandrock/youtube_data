"""
Kanalweise Boilerplate-Erkennung fuer Video-Beschreibungen - store-basierte
Portierung von youtube_code.new_analysis.feasibility (cmd_boilerplate/
cmd_extract, Zeilen 84-90, 202-210, 284-339, 394-397).

Ohne diesen Filter wuerde jede Keyword-Suche auf der Beschreibung
unbrauchbar: Kanaele mit fixen Hashtag-Ketten oder Spendenbloecken (z.B.
"#NeinZumKrieg" in jedem Video) wuerden sonst zu 100% als themenrelevant
gelten, sobald diese feste Zeile ein Keyword enthaelt.

Ablauf (zwei Phasen, siehe classify_topic_relevance.py):
    1. learn_boilerplate(df)   - pro Kanal wiederkehrende Beschreibungszeilen
                                  aus einer Stichprobe lernen.
    2. clean_description(...) - diese Zeilen vor dem Keyword-Matching aus
                                  einer einzelnen Beschreibung entfernen.

Konstanten und split_paragraphs()/line_hash() sind 1:1 aus feasibility.py
uebernommen (dort bereits validiert) - feasibility.py selbst bleibt
unangetastet.
"""
import hashlib
from collections import Counter, defaultdict

# Ein Beschreibungs-Absatz gilt als Boilerplate, wenn er bei >= diesem Anteil
# der geprueften Videos eines Kanals vorkommt.
BOILERPLATE_THRESHOLD = 0.60
# Nur so viele Videos pro Kanal zum Lernen der Boilerplate heranziehen.
BOILERPLATE_SAMPLE_PER_CHANNEL = 300
# Absaetze unter dieser Laenge werden beim Lernen ignoriert (Leerzeilen etc.).
BOILERPLATE_MIN_LEN = 12
# Mindestanzahl geprueften Videos pro Kanal, damit ueberhaupt Boilerplate
# gelernt wird (feasibility.py: "n < 3" -> kein Boilerplate fuer den Kanal).
BOILERPLATE_MIN_SAMPLE = 3


def split_paragraphs(desc: str) -> list:
    """
    Beschreibung in Absaetze/Zeilen zerlegen und normalisieren. Nimmt
    zusaetzlich zu None/"" auch NaN entgegen (pandas.read_sql_query liefert
    fehlende TEXT-Spalten aus einem LEFT JOIN als float('nan'), nicht None).
    """
    if not isinstance(desc, str) or not desc:
        return []
    return [ln.strip() for ln in desc.replace("\r", "\n").split("\n") if ln.strip()]


def line_hash(s: str) -> str:
    return hashlib.blake2b(s.encode("utf-8", "ignore"), digest_size=8).hexdigest()


def learn_boilerplate(df) -> dict:
    """
    Lernt pro channel_id die konstanten Beschreibungsbausteine aus einer
    Stichprobe seiner Videos (Muster: feasibility.cmd_boilerplate).

    df: DataFrame mit mind. den Spalten channel_id, video_id, description
        (z.B. aus video_registry.get_videos_with_text()).

    Rueckgabe: {channel_id: {hash, ...}} - nur fuer Kanaele mit mindestens
    BOILERPLATE_MIN_SAMPLE geprueften Videos und mindestens einer Zeile, die
    den Schwellenwert erreicht.

    Performance: die pro-Kanal-Stichprobe (BOILERPLATE_SAMPLE_PER_CHANNEL)
    wird per groupby().head() vektorisiert bestimmt, statt sie ueber einen
    Python-Loop mit Counter-Check ueber ALLE Zeilen von df auszuwaehlen
    (bei mehreren hunderttausend Zeilen mit nur wenigen hundert Kanaelen
    sonst ein voller Durchlauf durch df fuer eine winzige Teilmenge).
    Zeilenweise gehasht wird nur noch diese (kleine, deterministische)
    Stichprobe.
    """
    valid = df[df["channel_id"].notna() & (df["channel_id"] != "")]
    if valid.empty:
        return {}

    # Deterministische Reihenfolge (nach video_id sortiert) statt der
    # arbitraeren Zeilenreihenfolge einer JSONL-Datei in feasibility.py -
    # bewusste Abweichung, damit Wiederholungslaeufe reproduzierbar sind.
    sample = (
        valid.sort_values("video_id")
        .groupby("channel_id", sort=False, group_keys=False)
        .head(BOILERPLATE_SAMPLE_PER_CHANNEL)
    )
    seen = sample.groupby("channel_id")["video_id"].size()

    counts = defaultdict(Counter)
    for row in sample.itertuples(index=False):
        for ln in split_paragraphs(row.description or ""):
            if len(ln) < BOILERPLATE_MIN_LEN:
                continue
            counts[row.channel_id][line_hash(ln)] += 1

    boiler = {}
    for ch, c in counts.items():
        n = seen[ch]
        if n < BOILERPLATE_MIN_SAMPLE:
            continue
        hashes = {h for h, k in c.items() if k / n >= BOILERPLATE_THRESHOLD}
        if hashes:
            boiler[ch] = hashes
    return boiler


def clean_description(description: str, channel_id, boiler: dict) -> str:
    """
    Entfernt die fuer channel_id gelernten Boilerplate-Zeilen aus einer
    einzelnen Beschreibung (1:1 aus feasibility.cmd_extract, Zeilen 394-397).

    Schneller Sonderfall: hat der Kanal ueberhaupt keine gelernte Boilerplate
    (der Regelfall - BOILERPLATE_THRESHOLD von 60% wird nur von wenigen
    Kanaelen ueberhaupt erreicht), entfaellt das Hashen jeder einzelnen Zeile
    komplett - das war zuvor die teuerste Operation in classify(), weil sie
    unabhaengig vom Ergebnis fuer JEDE Zeile JEDES Videos ausgefuehrt wurde.
    """
    drop = boiler.get(channel_id)
    if not drop:
        return description or ""
    lines = split_paragraphs(description or "")
    return "\n".join(ln for ln in lines if line_hash(ln) not in drop)

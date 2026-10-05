"""
Kanalweise Boilerplate-Erkennung fuer Video-Beschreibungen - urspruenglich
store-basierte Portierung von youtube_code.new_analysis.feasibility
(cmd_boilerplate/cmd_extract), seit 2026-10-05 um vier Korrekturen erweitert.

Ohne diesen Filter wuerde jede Keyword-Suche auf der Beschreibung
unbrauchbar: Kanaele mit fixen Hashtag-Ketten oder Spendenbloecken (z.B.
"#NeinZumKrieg" in jedem Video) wuerden sonst zu 100% als themenrelevant
gelten, sobald diese feste Zeile ein Keyword enthaelt.

Ablauf (zwei Phasen, siehe classify_topic_relevance.py):
    1. learn_boilerplate(df)   - pro Kanal (und Zeitfenster) wiederkehrende
                                  Beschreibungszeilen lernen.
    2. clean_description(...) - diese Zeilen vor dem Keyword-Matching aus
                                  einer einzelnen Beschreibung entfernen.

Korrekturen gegenueber der feasibility.py-Fassung (eine Kanal-Stichprobe von
300 Videos, 60%-Schwelle, wortgleiche Zeilen):
    Luecke 1 - Boilerplate, die nur zeitweise genutzt wird (z.B. ein
        Spendenaufruf nur 2022), erreicht kanalweit nie 60%.
        -> Lernen zusaetzlich pro Kanal x Zeitfenster (BOILERPLATE_WINDOW,
           Default Kalenderhalbjahr) mit eigener Schwelle und Mindestzahl
           an Videos je Fenster (BOILERPLATE_MIN_WINDOW_VIDEOS).
    Luecke 2 - Fast-Duplikate (wechselnde Daten/Folgennummern, Emojis,
        URL-Parameter, umsortierte Hashtags) werden bei wortgleichem
        Hashing nicht als dieselbe Zeile erkannt.
        -> normalize_line(): Kleinschreibung, URLs/Ziffern/Emojis/
           Sonderzeichen entfernen, Hashtags sortieren, erst dann hashen.
    Absolute Regel - eine Zeile, die (nach Normalisierung) in mindestens
        BOILERPLATE_MIN_ABS_VIDEOS (20) Videos eines Kanals vorkommt, ist
        Boilerplate, unabhaengig von Anteil und Zeitfenster.
    Diagnose - scripts/adhoc/diagnose_boilerplate_trefferquoten.py
        vergleicht pro Kanal x Jahr die Trefferquote im Titel mit der in der
        bereinigten Beschreibung (alte vs. neue Bereinigung).

Statt einer Stichprobe werden jetzt ALLE Videos eines Kanals gezaehlt (die
absolute Regel und die Fensterschwellen brauchen die vollen Zaehlungen).
Jede Zeile wird pro Video nur einmal gezaehlt (Mehrfachvorkommen innerhalb
einer Beschreibung zaehlen nicht doppelt).
"""
import hashlib
import re
from collections import Counter, defaultdict

# Ein Beschreibungs-Absatz gilt als Boilerplate, wenn er bei >= diesem Anteil
# der Videos eines Kanals (gesamt) bzw. eines Kanal-Zeitfensters vorkommt.
BOILERPLATE_THRESHOLD = 0.60
# Absolute Regel: in >= so vielen Videos eines Kanals (nach Normalisierung
# wortgleich) -> Boilerplate. Echte Inhaltszeilen wiederholen sich so gut wie
# nie 20-mal.
BOILERPLATE_MIN_ABS_VIDEOS = 20
# Zeitfenster fuer das fensterweise Lernen: "halfyear" (2022H1) oder
# "quarter" (2022Q1), jeweils Kalenderfenster.
BOILERPLATE_WINDOW = "halfyear"
# Mindestzahl Videos je Kanal-Zeitfenster, damit fuer das Fenster eine eigene
# Schwelle angewendet wird (bei 10 Videos und 60% also >= 6 Vorkommen).
# Kleinere Fenster bekommen nur die kanalweiten Regeln.
BOILERPLATE_MIN_WINDOW_VIDEOS = 10
# Absaetze, deren normalisierte Form kuerzer ist, werden ueber ihre rohe
# (nur kleingeschriebene) Form gezaehlt; ist auch diese kuerzer, wird die
# Zeile ignoriert (Leerzeilen, "Quellen:" etc.).
BOILERPLATE_MIN_LEN = 12
# Mindestanzahl Videos pro Kanal, damit ueberhaupt Boilerplate gelernt wird
# (feasibility.py: "n < 3" -> kein Boilerplate fuer den Kanal).
BOILERPLATE_MIN_SAMPLE = 3

_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_HASHTAG_RE = re.compile(r"#\w+")
# Alles ausser Buchstaben (inkl. Umlaute/ß), Leerzeichen und '#' entfernen -
# trifft Ziffern, Satz-/Sonderzeichen und Emojis in einem Schritt.
_NONLETTER_RE = re.compile(r"[^a-zäöüß#\s]+")
_WS_RE = re.compile(r"\s+")


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


def normalize_line(ln: str) -> str:
    """
    Normalisiert eine Beschreibungszeile, damit Fast-Duplikate denselben Hash
    bekommen: Kleinschreibung, URLs, Ziffern, Emojis und Sonderzeichen
    entfernen, Hashtags alphabetisch sortiert ans Ende stellen.
    Beispiel: "🔴 Folge 123 – #Ukraine #NATO https://x.y/?a=1"
           -> "folge #nato #ukraine"
    """
    s = _URL_RE.sub(" ", ln.lower())
    s = _NONLETTER_RE.sub(" ", s)
    tags = sorted(set(_HASHTAG_RE.findall(s)))
    rest = _HASHTAG_RE.sub(" ", s).replace("#", " ")
    return _WS_RE.sub(" ", " ".join([rest] + tags)).strip()


def line_key(ln: str):
    """
    Schluessel einer Zeile fuer Lernen und Bereinigung: Hash der normalisierten
    Form; ist diese kuerzer als BOILERPLATE_MIN_LEN (z.B. reine URL- oder
    Emoji-Zeilen), Hash der rohen kleingeschriebenen Zeile - sonst wuerde eine
    feste Link-Zeile wie "https://spenden.de/ukraine-hilfe" (normalisiert
    leer) nie entfernt, obwohl sie ein Keyword enthaelt. None = Zeile zu
    kurz, wird weder gelernt noch entfernt.
    """
    norm = normalize_line(ln)
    if len(norm) >= BOILERPLATE_MIN_LEN:
        return "n:" + line_hash(norm)
    raw = ln.lower()
    if len(raw) >= BOILERPLATE_MIN_LEN:
        return "r:" + line_hash(raw)
    return None


def window_key(published_at) -> str:
    """
    Zeitfenster-Schluessel aus published_at (ISO-String "YYYY-MM-DD...") je
    nach BOILERPLATE_WINDOW, z.B. "2022H1" bzw. "2022Q1". Unbekanntes/
    fehlendes Datum -> None (Video zaehlt dann nur kanalweit).
    """
    if not isinstance(published_at, str) or len(published_at) < 7:
        return None
    try:
        year, month = published_at[:4], int(published_at[5:7])
    except ValueError:
        return None
    if BOILERPLATE_WINDOW == "quarter":
        return f"{year}Q{(month - 1) // 3 + 1}"
    return f"{year}H{1 if month <= 6 else 2}"


def learn_boilerplate(df) -> dict:
    """
    Lernt pro channel_id die konstanten Beschreibungsbausteine aus ALLEN
    Videos des Kanals.

    df: DataFrame mit mind. den Spalten channel_id, video_id, description,
        published_at (z.B. aus video_registry.get_videos_with_text()).

    Rueckgabe: {channel_id: {"all": {key, ...}, "windows": {window: {key, ...}}}}
        "all"     - kanalweit Boilerplate: Anteil >= BOILERPLATE_THRESHOLD
                    ueber alle Videos ODER >= BOILERPLATE_MIN_ABS_VIDEOS Videos.
        "windows" - zusaetzlich nur im jeweiligen Zeitfenster Boilerplate
                    (Anteil >= BOILERPLATE_THRESHOLD bei >=
                    BOILERPLATE_MIN_WINDOW_VIDEOS Videos im Fenster).
    Nur Kanaele mit mindestens BOILERPLATE_MIN_SAMPLE Videos und mindestens
    einer Boilerplate-Zeile sind enthalten.
    """
    valid = df[df["channel_id"].notna() & (df["channel_id"] != "")]
    if valid.empty:
        return {}

    pub = valid["published_at"] if "published_at" in valid.columns else [None] * len(valid)
    ch_counts = defaultdict(Counter)
    win_counts = defaultdict(Counter)   # (channel_id, window) -> Counter
    ch_n = Counter()
    win_n = Counter()
    for ch, desc, published_at in zip(valid["channel_id"], valid["description"], pub):
        ch_n[ch] += 1
        win = window_key(published_at)
        if win is not None:
            win_n[(ch, win)] += 1
        keys = {k for k in map(line_key, split_paragraphs(desc)) if k is not None}
        if not keys:
            continue
        ch_counts[ch].update(keys)
        if win is not None:
            win_counts[(ch, win)].update(keys)

    boiler = {}
    for ch, c in ch_counts.items():
        n = ch_n[ch]
        if n < BOILERPLATE_MIN_SAMPLE:
            continue
        hashes = {h for h, k in c.items()
                  if k / n >= BOILERPLATE_THRESHOLD or k >= BOILERPLATE_MIN_ABS_VIDEOS}
        boiler[ch] = {"all": hashes, "windows": {}}

    for (ch, win), c in win_counts.items():
        if ch not in boiler:
            continue
        n = win_n[(ch, win)]
        if n < BOILERPLATE_MIN_WINDOW_VIDEOS:
            continue
        extra = {h for h, k in c.items() if k / n >= BOILERPLATE_THRESHOLD} - boiler[ch]["all"]
        if extra:
            boiler[ch]["windows"][win] = extra

    return {ch: b for ch, b in boiler.items() if b["all"] or b["windows"]}


def clean_description(description: str, channel_id, boiler: dict, published_at=None) -> str:
    """
    Entfernt die fuer channel_id gelernten Boilerplate-Zeilen (kanalweit plus
    die des Zeitfensters von published_at) aus einer einzelnen Beschreibung.
    Verglichen wird ueber line_key(), d.h. auf normalisierter Form; die
    zurueckgegebenen Zeilen bleiben im Original erhalten.

    Schneller Sonderfall: hat der Kanal ueberhaupt keine gelernte Boilerplate,
    entfaellt das Normalisieren/Hashen jeder einzelnen Zeile komplett.
    """
    entry = boiler.get(channel_id)
    if not entry:
        return description or ""
    drop = entry["all"]
    win_drop = entry["windows"].get(window_key(published_at))
    if win_drop:
        drop = drop | win_drop
    lines = split_paragraphs(description or "")
    return "\n".join(ln for ln in lines if line_key(ln) not in drop)

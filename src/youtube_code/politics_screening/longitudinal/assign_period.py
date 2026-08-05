import json
import random
from datetime import date, datetime

from youtube_code.config import RAW, SAMPLES
from youtube_code.politics_screening.screening_config import (
    MAIN_VIDEO_FILE,
    REFERENCE_DATE,
)

ref_dt = datetime.fromisoformat(REFERENCE_DATE.replace("Z", "+00:00")).date()

# Pfade an deine Dateien anpassen:
# INPUT_FILE = SAMPLES / "russia" / "videos_wo_shorts_description.jsonl"
INPUT_FILE = MAIN_VIDEO_FILE
OUTPUT_FILE = SAMPLES / "russia" / "output_with_periods.jsonl"


def calculate_period(published_at_str: str, anchor_date: date = ref_dt) -> int:
    """Berechnet die Monatsperiode relativ zu einem variablen Ankerdatum."""
    dt = datetime.fromisoformat(published_at_str.replace("Z", "+00:00")).date()

    # Monatsdifferenz berechnen
    month_diff = (dt.year - anchor_date.year) * 12 + (
        dt.month - anchor_date.month
    )

    # Tag-Korrektur relativ zum Tag des Ankerdatums
    if dt.day < anchor_date.day:
        month_diff -= 1

    return month_diff


def print_random_samples(records: list, k: int = 10):
    """Gibt k zufällige Stichproben formatiert in der Konsole aus."""
    if not records:
        print("\nKeine Datensätze zur Kontrolle vorhanden.")
        return

    sample_size = min(k, len(records))
    samples = random.sample(records, sample_size)

    print(f"\n{'='*80}")
    print(
        f"MANUELLE KONTROLLE: {sample_size} ZUFÄLLIGE BEISPIELE (Ankerdatum: {ref_dt})"
    )
    print(f"{'='*80}\n")

    for idx, item in enumerate(samples, 1):
        v_id = item.get("video_id", "N/A")
        title = item.get("title", "N/A")
        pub_at = item.get("published_at", "N/A")
        period = item.get("period", "N/A")

        print(f"Beispiel {idx:02d}:")
        print(f"  ► Periode:      {period}")
        print(f"  ► Published At: {pub_at}")
        print(f"  ► Video ID:     {v_id}")
        print(f"  ► Titel:        {title}")
        print("-" * 80)


def process_jsonl(input_file, output_file, num_samples: int = 10):
    """Liest die Input-JSONL ein, fügt das Feld 'period' (bzw.

    'time_delta') hinzu, schreibt das Ergebnis in die Output-Datei und
    gibt eine Zufallsstichprobe aus.
    """
    processed_records = []

    with open(input_file, "r", encoding="utf-8") as infile, open(
        output_file, "w", encoding="utf-8"
    ) as outfile:

        for line_num, line in enumerate(infile, 1):
            line = line.strip()
            if not line:
                continue  # Leere Zeilen überspringen

            try:
                data = json.loads(line)

                published_at = data.get("published_at")
                if published_at:
                    period = calculate_period(published_at)

                    # Hier fügen wir das Ergebnis hinzu
                    data["period"] = period
                    # Falls du das bestehende Feld 'time_delta' überschreiben möchtest:
                    data["time_delta"] = period
                else:
                    data["period"] = None

                # Wieder als JSON-Zeile schreiben
                outfile.write(json.dumps(data, ensure_ascii=False) + "\n")

                # Für die spätere Stichprobe im Speicher behalten
                processed_records.append(data)

            except (json.JSONDecodeError, ValueError) as e:
                print(
                    f"Warnung: Zeile {line_num} konnte nicht verarbeitet werden ({e})"
                )

    # Zufällige Stichproben in der Konsole ausgeben
    print_random_samples(processed_records, k=num_samples)


if __name__ == "__main__":
    print(f"Processing '{INPUT_FILE}'...")
    process_jsonl(INPUT_FILE, OUTPUT_FILE, num_samples=10)
    print(f"Done! Results saved in: '{OUTPUT_FILE}'.")
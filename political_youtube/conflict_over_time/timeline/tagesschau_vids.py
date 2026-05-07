import pandas as pd
from docx import Document

df = pd.read_json("../../JSON Files/video_files/videos_total.json")
print(len(df))
df = df[df["channel_id"] == "UC5NOEUbkLheQcaaRldYW5GA"]
print(len(df))

keywords = ["nahe osten", "naher osten", "nahen osten", "nahost", "shani louk", "israël",
            "israel", "palästina", "palästin", "gaza", "hamas", "IDF", "Jerusalem",
            "netanjahu", "netanyahu", "hisbollah", "mossad"]

pattern = '|'.join(keywords)

df = df[df["title"].str.contains(pattern, case = False, na = False) == True]

print(len(df))

df = df.sort_values(by="published_at")

df_transcripts = pd.read_csv("../../Transcript files/transcripts_conflict_over_time.csv")

df = pd.merge(df, df_transcripts, on = "video_id", how ="left")
df["published_at"] = pd.to_datetime(df["published_at"])
df = df[(df["published_at"] >= "2023-10-07T00:00:00Z") & (df["published_at"] <= "2023-10-31T00:00:00Z")]


def excel_zu_word_vertikal(word_ausgabe):

    # 2. Word-Dokument erstellen
    doc = Document()

    # 3. Zeile für Zeile durchgehen
    for i, row in df.iterrows():
        # Jede Spalte der aktuellen Zeile untereinander schreiben
        for spalte in df.columns:
            wert = str(row[spalte]) if pd.notna(row[spalte]) else ""

            # Text einfügen (Fett für den Spaltennamen)
            p = doc.add_paragraph()
            run = p.add_run(f"{spalte}: ")
            run.bold = True
            p.add_run(wert)

        # 4. Seitenumbruch nach jeder kompletten Excel-Zeile
        # (Außer nach der absolut letzten Zeile)
        if i < len(df) - 1:
            doc.add_page_break()

    # 5. Speichern
    doc.save(word_ausgabe)
    print(f"Erfolgreich gespeichert unter: {word_ausgabe}")


# Anwendung
excel_zu_word_vertikal("oct7-oct31.docx")

#df.to_csv("tagesschau_keyword_vids.csv", index = False)
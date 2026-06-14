from dotenv import load_dotenv
import os
import json
import pandas as pd
from google import genai
from google.cloud import storage
from google.genai import types


load_dotenv()
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = "us-central1"
BUCKET_NAME = os.getenv("GCP_BUCKET_NAME")
API_KEY = os.getenv("API_KEY_GEMINI")

client = genai.Client(
    vertexai = True,
    project=PROJECT_ID,
    location = LOCATION
)

INPUT_CSV = "test_transcripts.csv"
#INPUT_CSV = "../../Transcript files/transcripts_conflict_over_time_sampled.csv"
BATCH_INPUT_JSONL = "gemini_batch_input.jsonl"

gemini_25_flash = "gemini-2.5-flash"
gemini_25_flash_lite = "gemini-2.5-flash-lite"
gemini_35_flash = "gemini-3.5-flash"
gemini_31_flash_lite = "gemini-3.1-flash-lite"

prompts = {
    # Base prompt
    "PROMPT_1": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.
    
    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Video handelt, in dem der Creator aktiv auf ein anderes Video oder einen Medienbeitrag reagiert (Reaction-Video). Achte auf Indikatoren im Text wie "Wir schauen uns an", "Ich pausiere mal" oder direkte Kommentare zu eingespielten Fremdinhalten. Erlaubte Werte: "Reaction" oder "Standard".
    
    2. SOZIO-KULTURELLE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die Position des Creators zu soziokulturellen und gesellschaftspolitischen Themen im Kontext Deutschlands auf einer Skala von 0 (extrem links) bis 10 (extrem rechts). 
    - Die mathematische Mitte (neutral/ausgewogen berichtet, ohne eigenes Framing) liegt exakt bei 5.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist (z. B. reines Gaming, Kochvideo, Lifestyle ohne gesellschaftlichen Bezug), setze den Score zwingend auf -1.0.
    
    !!! WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus) !!!
    Unterscheide strikt zwischen populistischer Rhetorik (Systemkritik) und der tatsächlichen politischen Ideologie (vorgeschlagene Lösungen):
    - Systemkritik, Anti-Establishment-Rhetorik, pauschales Misstrauen gegenüber Institutionen/Medien und die Aufteilung in "die Elite da oben vs. das Volk" sind reine Merkmale von POPULISMUS, nicht von linker oder rechter Ideologie.
    - Bestimme die IDEOLOGIE (Links vs. Rechts) ausschließlich anhand konkreter Inhalte und Werte:
      -> LINKS (0.0-4.9): Fokus auf soziale Gerechtigkeit, staatliche Regulierung, Umverteilung, Antikapitalismus, progressive Gesellschaftspolitik, Klimaschutz durch Ge- und Verbote.
      -> RECHTS (5.1-10.0): Fokus auf individuelle Freiheit (Wirtschaftsliberalismus), Marktmechanismen, private Sachwerte/Selbstvorsorge, traditionelle Werte, Nationalstaat, explizite Ablehnung staatlicher Eingriffe.
    
    3. POPULISMUS (Skala 0 bis 10):
    Bewerte den Text hinsichtlich des Populismusgrads basierend auf dem "ideational approach" (ideationeller Ansatz) auf einer Skala von 0 (gar nicht populistisch) bis 10 (extrem populistisch). 
    - Ein Video, in dem rein neutral argumentiert wird, erhält den Wert 0.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist und kein Bezug zu gesellschaftlichen Debatten oder Eliten hergestellt wird, setze den Score zwingend auf -1.0.
    - Nutze diese Skala für die reine Systemkritik, das Framing "Reine Bevölkerung vs. korrupte Elite" und das Misstrauen gegenüber dem "Mainstream".
    
    4. EVALUATIONS-REGEL:
    Bewerte ausschließlich Aussagen des Creators/Kanalinhabers. Ignoriere Aussagen von gezeigten Dritten (z. B. in Reaction-Ausschnitten oder Interviewgästen), es sei denn, der Creator stimmt ihnen explizit und nachweisbar zu.
    
    5. BEGRÜNDUNGEN (Maximal 2 Sätze pro Begründung):
    Erkläre deine Punktebewertungen extrem kurz und präzise anhand konkreter Argumentationsmuster oder Themen aus dem Transkript.
    
    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
      "ideology_reason": "Kurzer Grund.",
      "populism_score": 0.0,
      "populism_reason": "Kurzer Grund."
    }
    """,

    # PROMPT 2 removes the rule to only rate statements from the creator.
    "PROMPT_2": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.
    
    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Video handelt, in dem der Creator aktiv auf ein anderes Video oder einen Medienbeitrag reagiert (Reaction-Video). Achte auf Indikatoren im Text wie "Wir schauen uns an", "Ich pausiere mal" oder direkte Kommentare zu eingespielten Fremdinhalten. Erlaubte Werte: "Reaction" oder "Standard".
    
    2. SOZIO-KULTURELLE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die Position des Creators zu soziokulturellen und gesellschaftspolitischen Themen im Kontext Deutschlands auf einer Skala von 0 (extrem links) bis 10 (extrem rechts). 
    - Die mathematische Mitte (neutral/ausgewogen berichtet, ohne eigenes Framing) liegt exakt bei 5.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist (z. B. reines Gaming, Kochvideo, Lifestyle ohne gesellschaftlichen Bezug), setze den Score zwingend auf -1.0.
    
    !!! WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus) !!!
    Unterscheide strikt zwischen populistischer Rhetorik (Systemkritik) und der tatsächlichen politischen Ideologie (vorgeschlagene Lösungen):
    - Systemkritik, Anti-Establishment-Rhetorik, pauschales Misstrauen gegenüber Institutionen/Medien und die Aufteilung in "die Elite da oben vs. das Volk" sind reine Merkmale von POPULISMUS, nicht von linker oder rechter Ideologie.
    - Bestimme die IDEOLOGIE (Links vs. Rechts) ausschließlich anhand konkreter Inhalte und Werte:
      -> LINKS (0.0-4.9): Fokus auf soziale Gerechtigkeit, staatliche Regulierung, Umverteilung, Antikapitalismus, progressive Gesellschaftspolitik, Klimaschutz durch Ge- und Verbote.
      -> RECHTS (5.1-10.0): Fokus auf individuelle Freiheit (Wirtschaftsliberalismus), Marktmechanismen, private Sachwerte/Selbstvorsorge, traditionelle Werte, Nationalstaat, explizite Ablehnung staatlicher Eingriffe.
    
    3. POPULISMUS (Skala 0 bis 10):
    Bewerte den Text hinsichtlich des Populismusgrads basierend auf dem "ideational approach" (ideationeller Ansatz) auf einer Skala von 0 (gar nicht populistisch) bis 10 (extrem populistisch). 
    - Ein Video, in dem rein neutral argumentiert wird, erhält den Wert 0.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist und kein Bezug zu gesellschaftlichen Debatten oder Eliten hergestellt wird, setze den Score zwingend auf -1.0.
    - Nutze diese Skala für die reine Systemkritik, das Framing "Reine Bevölkerung vs. korrupte Elite" und das Misstrauen gegenüber dem "Mainstream".
    
    4. BEGRÜNDUNGEN (Maximal 2 Sätze pro Begründung):
    Erkläre deine Punktebewertungen extrem kurz und präzise anhand konkreter Argumentationsmuster oder Themen aus dem Transkript.
    
    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
      "ideology_reason": "Kurzer Grund.",
      "populism_score": 0.0,
      "populism_reason": "Kurzer Grund."
    }
    """,

    # PROMPT 3 replaces socio-cultural ideology with political ideology
    "PROMPT_3" : """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.
    
    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Video handelt, in dem der Creator aktiv auf ein anderes Video oder einen Medienbeitrag reagiert (Reaction-Video). Achte auf Indikatoren im Text wie "Wir schauen uns an", "Ich pausiere mal" oder direkte Kommentare zu eingespielten Fremdinhalten. Erlaubte Werte: "Reaction" oder "Standard".
    
    2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die politische Ideologie des Creators Themen im Kontext Deutschlands auf einer Skala von 0 (extrem links) bis 10 (extrem rechts). 
    - Die mathematische Mitte (neutral/ausgewogen berichtet, ohne eigenes Framing) liegt exakt bei 5.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist (z. B. reines Gaming, Kochvideo, Lifestyle ohne gesellschaftlichen Bezug), setze den Score zwingend auf -1.0.
    
    !!! WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus) !!!
    Unterscheide strikt zwischen populistischer Rhetorik (Systemkritik) und der tatsächlichen politischen Ideologie (vorgeschlagene Lösungen):
    - Systemkritik, Anti-Establishment-Rhetorik, pauschales Misstrauen gegenüber Institutionen/Medien und die Aufteilung in "die Elite da oben vs. das Volk" sind reine Merkmale von POPULISMUS, nicht von linker oder rechter Ideologie.
    - Bestimme die IDEOLOGIE (Links vs. Rechts) ausschließlich anhand konkreter Inhalte und Werte:
      -> LINKS (0.0-4.9): Fokus auf soziale Gerechtigkeit, staatliche Regulierung, Umverteilung, Antikapitalismus, progressive Gesellschaftspolitik, Klimaschutz durch Ge- und Verbote.
      -> RECHTS (5.1-10.0): Fokus auf individuelle Freiheit (Wirtschaftsliberalismus), Marktmechanismen, private Sachwerte/Selbstvorsorge, traditionelle Werte, Nationalstaat, explizite Ablehnung staatlicher Eingriffe.
    
    3. POPULISMUS (Skala 0 bis 10):
    Bewerte den Text hinsichtlich des Populismusgrads basierend auf dem "ideational approach" (ideationeller Ansatz) auf einer Skala von 0 (gar nicht populistisch) bis 10 (extrem populistisch). 
    - Ein Video, in dem rein neutral argumentiert wird, erhält den Wert 0.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist und kein Bezug zu gesellschaftlichen Debatten oder Eliten hergestellt wird, setze den Score zwingend auf -1.0.
    - Nutze diese Skala für die reine Systemkritik, das Framing "Reine Bevölkerung vs. korrupte Elite" und das Misstrauen gegenüber dem "Mainstream".
    
    4. EVALUATIONS-REGEL:
    Bewerte ausschließlich Aussagen des Creators/Kanalinhabers. Ignoriere Aussagen von gezeigten Dritten (z. B. in Reaction-Ausschnitten oder Interviewgästen), es sei denn, der Creator stimmt ihnen explizit und nachweisbar zu.
    
    5. BEGRÜNDUNGEN (Maximal 2 Sätze pro Begründung):
    Erkläre deine Punktebewertungen extrem kurz und präzise anhand konkreter Argumentationsmuster oder Themen aus dem Transkript.
    
    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
      "ideology_reason": "Kurzer Grund.",
      "populism_score": 0.0,
      "populism_reason": "Kurzer Grund."
    }
    """,

    # Prompt 4 rates only political ideology
    "PROMPT_4" : """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.
    
    1. SOZIO-KULTURELLE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die Position des Creators zu soziokulturellen und gesellschaftspolitischen Themen im Kontext Deutschlands auf einer Skala von 0 (extrem links) bis 10 (extrem rechts). 
    - Die mathematische Mitte (neutral/ausgewogen berichtet, ohne eigenes Framing) liegt exakt bei 5.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist (z. B. reines Gaming, Kochvideo, Lifestyle ohne gesellschaftlichen Bezug), setze den Score zwingend auf -1.0.
    
    !!! WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus) !!!
    Unterscheide strikt zwischen populistischer Rhetorik (Systemkritik) und der tatsächlichen politischen Ideologie (vorgeschlagene Lösungen):
    - Systemkritik, Anti-Establishment-Rhetorik, pauschales Misstrauen gegenüber Institutionen/Medien und die Aufteilung in "die Elite da oben vs. das Volk" sind reine Merkmale von POPULISMUS, nicht von linker oder rechter Ideologie.
    - Bestimme die IDEOLOGIE (Links vs. Rechts) ausschließlich anhand konkreter Inhalte und Werte:
      -> LINKS (0.0-4.9): Fokus auf soziale Gerechtigkeit, staatliche Regulierung, Umverteilung, Antikapitalismus, progressive Gesellschaftspolitik, Klimaschutz durch Ge- und Verbote.
      -> RECHTS (5.1-10.0): Fokus auf individuelle Freiheit (Wirtschaftsliberalismus), Marktmechanismen, private Sachwerte/Selbstvorsorge, traditionelle Werte, Nationalstaat, explizite Ablehnung staatlicher Eingriffe.
    
    2. EVALUATIONS-REGEL:
    Bewerte ausschließlich Aussagen des Creators/Kanalinhabers. Ignoriere Aussagen von gezeigten Dritten (z. B. in Reaction-Ausschnitten oder Interviewgästen), es sei denn, der Creator stimmt ihnen explizit und nachweisbar zu.
    
    3. BEGRÜNDUNGEN (Maximal 2 Sätze pro Begründung):
    Erkläre deine Punktebewertungen extrem kurz und präzise anhand konkreter Argumentationsmuster oder Themen aus dem Transkript.
    
    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "ideology_score": 5.0,
      "ideology_reason": "Kurzer Grund."
    }
    """,

    # Prompt 5 rates only populism
    "PROMPT_5" : """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.
    
    1. POPULISMUS (Skala 0 bis 10):
    Bewerte den Text hinsichtlich des Populismusgrads basierend auf dem "ideational approach" (ideationeller Ansatz) auf einer Skala von 0 (gar nicht populistisch) bis 10 (extrem populistisch). 
    - Ein Video, in dem rein neutral argumentiert wird, erhält den Wert 0.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist und kein Bezug zu gesellschaftlichen Debatten oder Eliten hergestellt wird, setze den Score zwingend auf -1.0.
    - Nutze diese Skala für die reine Systemkritik, das Framing "Reine Bevölkerung vs. korrupte Elite" und das Misstrauen gegenüber dem "Mainstream".
    
    2. EVALUATIONS-REGEL:
    Bewerte ausschließlich Aussagen des Creators/Kanalinhabers. Ignoriere Aussagen von gezeigten Dritten (z. B. in Reaction-Ausschnitten oder Interviewgästen), es sei denn, der Creator stimmt ihnen explizit und nachweisbar zu.
    
    3. BEGRÜNDUNGEN (Maximal 2 Sätze pro Begründung):
    Erkläre deine Punktebewertungen extrem kurz und präzise anhand konkreter Argumentationsmuster oder Themen aus dem Transkript.
    
    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "populism_score": 0.0,
      "populism_reason": "Kurzer Grund."
    }
    """,

    # Prompt 6 rates only political ideology and removes the rule to only rate statements from the creator.
    "PROMPT_6": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. SOZIO-KULTURELLE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die Position des Creators zu soziokulturellen und gesellschaftspolitischen Themen im Kontext Deutschlands auf einer Skala von 0 (extrem links) bis 10 (extrem rechts). 
    - Die mathematische Mitte (neutral/ausgewogen berichtet, ohne eigenes Framing) liegt exakt bei 5.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist (z. B. reines Gaming, Kochvideo, Lifestyle ohne gesellschaftlichen Bezug), setze den Score zwingend auf -1.0.

    !!! WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus) !!!
    Unterscheide strikt zwischen populistischer Rhetorik (Systemkritik) und der tatsächlichen politischen Ideologie (vorgeschlagene Lösungen):
    - Systemkritik, Anti-Establishment-Rhetorik, pauschales Misstrauen gegenüber Institutionen/Medien und die Aufteilung in "die Elite da oben vs. das Volk" sind reine Merkmale von POPULISMUS, nicht von linker oder rechter Ideologie.
    - Bestimme die IDEOLOGIE (Links vs. Rechts) ausschließlich anhand konkreter Inhalte und Werte:
      -> LINKS (0.0-4.9): Fokus auf soziale Gerechtigkeit, staatliche Regulierung, Umverteilung, Antikapitalismus, progressive Gesellschaftspolitik, Klimaschutz durch Ge- und Verbote.
      -> RECHTS (5.1-10.0): Fokus auf individuelle Freiheit (Wirtschaftsliberalismus), Marktmechanismen, private Sachwerte/Selbstvorsorge, traditionelle Werte, Nationalstaat, explizite Ablehnung staatlicher Eingriffe.

    2. BEGRÜNDUNGEN (Maximal 2 Sätze pro Begründung):
    Erkläre deine Punktebewertungen extrem kurz und präzise anhand konkreter Argumentationsmuster oder Themen aus dem Transkript.

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "ideology_score": 5.0,
      "ideology_reason": "Kurzer Grund."
    }
    """,

    # Prompt 7 rates only populism and removes the rule to only rate statements from the creator.
    "PROMPT_7": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. POPULISMUS (Skala 0 bis 10):
    Bewerte den Text hinsichtlich des Populismusgrads basierend auf dem "ideational approach" (ideationeller Ansatz) auf einer Skala von 0 (gar nicht populistisch) bis 10 (extrem populistisch). 
    - Ein Video, in dem rein neutral argumentiert wird, erhält den Wert 0.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist und kein Bezug zu gesellschaftlichen Debatten oder Eliten hergestellt wird, setze den Score zwingend auf -1.0.
    - Nutze diese Skala für die reine Systemkritik, das Framing "Reine Bevölkerung vs. korrupte Elite" und das Misstrauen gegenüber dem "Mainstream".

    2. BEGRÜNDUNGEN (Maximal 2 Sätze pro Begründung):
    Erkläre deine Punktebewertungen extrem kurz und präzise anhand konkreter Argumentationsmuster oder Themen aus dem Transkript.

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "populism_score": 0.0,
      "populism_reason": "Kurzer Grund."
    }
    """,

    # PROMPT 10 increases the threshold of rating a video as non-political
    "PROMPT_10": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.
    
    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Video handelt, in dem der Creator aktiv auf ein anderes Video oder einen Medienbeitrag reagiert (Reaction-Video). Achte auf Indikatoren im Text wie "Wir schauen uns an", "Ich pausiere mal" oder direkte Kommentare zu eingespielten Fremdinhalten. Erlaubte Werte: "Reaction" oder "Standard".
    
    2. SOZIO-KULTURELLE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die Position des Creators zu soziokulturellen und gesellschaftspolitischen Themen im Kontext Deutschlands auf einer Skala von 0 (extrem links) bis 10 (extrem rechts). 
    - Die mathematische Mitte (neutral/ausgewogen berichtet, ohne eigenes Framing) liegt exakt bei 5.0.
    - Wenn die im Video behandelten Themen vollständig unpolitisch/ideologiefrei sind (z. B. reines Gaming, Kochvideo, Lifestyle ohne gesellschaftlichen Bezug), setze den Score zwingend auf -1.0. Wenn das Video ein vollständig neutraler Bericht über politische Ereignisse ist, setze den Score auf 5.0.
    
    !!! WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus) !!!
    Unterscheide strikt zwischen populistischer Rhetorik (Systemkritik) und der tatsächlichen politischen Ideologie (vorgeschlagene Lösungen):
    - Systemkritik, Anti-Establishment-Rhetorik, pauschales Misstrauen gegenüber Institutionen/Medien und die Aufteilung in "die Elite da oben vs. das Volk" sind reine Merkmale von POPULISMUS, nicht von linker oder rechter Ideologie.
    - Bestimme die IDEOLOGIE (Links vs. Rechts) ausschließlich anhand konkreter Inhalte und Werte:
      -> LINKS (0.0-4.9): Fokus auf soziale Gerechtigkeit, staatliche Regulierung, Umverteilung, Antikapitalismus, progressive Gesellschaftspolitik, Klimaschutz durch Ge- und Verbote.
      -> RECHTS (5.1-10.0): Fokus auf individuelle Freiheit (Wirtschaftsliberalismus), Marktmechanismen, private Sachwerte/Selbstvorsorge, traditionelle Werte, Nationalstaat, explizite Ablehnung staatlicher Eingriffe.
    
    3. POPULISMUS (Skala 0 bis 10):
    Bewerte den Text hinsichtlich des Populismusgrads basierend auf dem "ideational approach" (ideationeller Ansatz) auf einer Skala von 0 (gar nicht populistisch) bis 10 (extrem populistisch). 
    - Ein Video, in dem rein neutral argumentiert wird, erhält den Wert 0.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist und kein Bezug zu gesellschaftlichen Debatten oder Eliten hergestellt wird, setze den Score zwingend auf -1.0.
    - Nutze diese Skala für die reine Systemkritik, das Framing "Reine Bevölkerung vs. korrupte Elite" und das Misstrauen gegenüber dem "Mainstream".
    
    4. EVALUATIONS-REGEL:
    Bewerte ausschließlich Aussagen des Creators/Kanalinhabers. Ignoriere Aussagen von gezeigten Dritten (z. B. in Reaction-Ausschnitten oder Interviewgästen), es sei denn, der Creator stimmt ihnen explizit und nachweisbar zu.
    
    5. BEGRÜNDUNGEN (Maximal 2 Sätze pro Begründung):
    Erkläre deine Punktebewertungen extrem kurz und präzise anhand konkreter Argumentationsmuster oder Themen aus dem Transkript.
    
    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
      "ideology_reason": "Kurzer Grund.",
      "populism_score": 0.0,
      "populism_reason": "Kurzer Grund."
    }
    """,

    # PROMPT 11 uses a different scale description
    "PROMPT_11": """Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".
    
    2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die Position des Creators auf einer Skala von 0 (extrem links) bis 10 (extrem rechts).
    - Neutral/ausgewogen = 5.0. Unpolitisches Video = -1.0.
    
    WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus)
    Unterscheide strikt zwischen populistischer Rhetorik (Systemkritik) und der tatsächlichen politischen Ideologie (vorgeschlagene Lösungen):
    - Systemkritik, Anti-Establishment-Rhetorik, pauschales Misstrauen gegenüber Institutionen/Medien und die Aufteilung in "die Elite da oben vs. das Volk" sind reine Merkmale von POPULISMUS, nicht von linker oder rechter Ideologie.
    - Bestimme die IDEOLOGIE (Links vs. Rechts) ausschließlich anhand konkreter Inhalte und Werte
       
    Skala (Orientierungspunkte):
    0.0–2.0 = klar links bis extrem links
    3.0–4.0 = moderat bis leicht links
    5.0     = neutral, ausgewogen oder nicht eindeutig einordenbar
    6.0–7.0 = leicht bis moderat rechts
    8.0–10.0 = klar bis extrem rechts
    
    - Bei gemischten Signalen: folge dem dominierenden Bereich, setze NICHT automatisch 5.0.
    - Wenn die im Video behandelten Themen vollständig unpolitisch/ideologiefrei sind (z. B. reines Gaming, Kochvideo, Lifestyle ohne gesellschaftlichen Bezug), setze den Score zwingend auf -1.0.
    - Wenn das Video ein vollständig neutraler Bericht über politische Ereignisse ist, setze den Score auf 5.0.

    
    3. POPULISMUS (Skala 0 bis 10):
    Bewerte den Populismusgrad basierend auf dem ideationellen Ansatz.
    Skala:
    0.0 = keinerlei populistische Kommunikation
    2.0 = gelegentliche Kritik an Institutionen
    4.0 = wiederkehrende Systemkritik
    6.0 = deutliches Establishment-vs-Bürger-Framing
    8.0 = starkes Volk-vs-Elite-Narrativ
    10.0 = nahezu vollständiges Weltbild basiert auf korrupten Eliten gegen das Volk
    
    - Berücksichtige: Volk-vs-Elite-Framing, Anti-Establishment-Rhetorik, Misstrauen gegenüber Institutionen/Medien.
    - Nicht berücksichtigen: wirtschaftspolitische Positionen, reine Sachkritik ohne Volk-vs-Elite-Element.
    
    4. BEGRÜNDUNGEN: Maximal 2 Sätze pro Begründung.
    Erkläre deine Punktebewertungen extrem kurz und präzise anhand konkreter Argumentationsmuster oder Themen aus dem Transkript.

    Gib ausschließlich folgendes JSON zurück:
    
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
      "ideology_reason": "Kurzer Grund.",
      "populism_score": 0.0,
      "populism_reason": "Kurzer Grund."
    }
    """,

    # PROMPT 12 uses PROMPT 11 and removes the rule to rate only the creator's statements
    "PROMPT_12": """Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die Position des Creators auf einer Skala von 0 (extrem links) bis 10 (extrem rechts).
    - Neutral/ausgewogen = 5.0. Unpolitisches Video = -1.0.

    WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus)
    Unterscheide strikt zwischen populistischer Rhetorik (Systemkritik) und der tatsächlichen politischen Ideologie (vorgeschlagene Lösungen):
    - Systemkritik, Anti-Establishment-Rhetorik, pauschales Misstrauen gegenüber Institutionen/Medien und die Aufteilung in "die Elite da oben vs. das Volk" sind reine Merkmale von POPULISMUS, nicht von linker oder rechter Ideologie.
    - Bestimme die IDEOLOGIE (Links vs. Rechts) ausschließlich anhand konkreter Inhalte und Werte

    Skala (Orientierungspunkte):
    0.0–2.0 = klar links bis extrem links
    3.0–4.0 = moderat bis leicht links
    5.0     = neutral, ausgewogen oder nicht eindeutig einordenbar
    6.0–7.0 = leicht bis moderat rechts
    8.0–10.0 = klar bis extrem rechts

    - Bei gemischten Signalen: folge dem dominierenden Bereich, setze NICHT automatisch 5.0.
    - Wenn die im Video behandelten Themen vollständig unpolitisch/ideologiefrei sind (z. B. reines Gaming, Kochvideo, Lifestyle ohne gesellschaftlichen Bezug), setze den Score zwingend auf -1.0. Wenn das Video ein vollständig neutraler Bericht über politische Ereignisse ist, setze den Score auf 5.0.


    3. POPULISMUS (Skala 0 bis 10):
    Bewerte den Text hinsichtlich des Populismusgrads basierend auf dem "ideational approach" (ideationeller Ansatz) auf einer Skala von 0 (gar nicht populistisch) bis 10 (extrem populistisch). 
    - Ein Video, in dem rein neutral argumentiert wird, erhält den Wert 0.0.
    - Wenn die im Video behandelten Themen vollständig unpolitisch/ideologiefrei ist und kein Bezug zu gesellschaftlichen Debatten oder Eliten hergestellt wird, setze den Score zwingend auf -1.0.
    - Nutze diese Skala für die reine Systemkritik, das Framing "Reine Bevölkerung vs. korrupte Elite" und das Misstrauen gegenüber dem "Mainstream".
    - Nicht berücksichtigen: wirtschaftspolitische Positionen, reine Sachkritik ohne Volk-vs-Elite-Element.


    4. BEGRÜNDUNGEN: Maximal 2 Sätze pro Begründung.
    Erkläre deine Punktebewertungen extrem kurz und präzise anhand konkreter Argumentationsmuster oder Themen aus dem Transkript.

    Gib ausschließlich folgendes JSON zurück:

    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
      "ideology_reason": "Kurzer Grund.",
      "populism_score": 0.0,
      "populism_reason": "Kurzer Grund."
    }
    """
}

### Choose prompt and model ###

PROMPT_KEY = "PROMPT_12"
SYSTEM_PROMPT = prompts[PROMPT_KEY]

MODEL_NAME = gemini_25_flash


if PROMPT_KEY.startswith("PROMPT_") and PROMPT_KEY[7:].isdigit():
    prompt_number = PROMPT_KEY.split("_")[1]
elif PROMPT_KEY.startswith("GPT_") and PROMPT_KEY[4:].isdigit():
    prompt_number = "gpt" + PROMPT_KEY.split("_")[1]
else:
    prompt_number = 0

if MODEL_NAME == gemini_25_flash:
    model_name = "g25_f"
elif MODEL_NAME == gemini_25_flash_lite:
    model_name = "g25_f_l"
elif MODEL_NAME == gemini_35_flash:
    model_name = "g35_f"
elif MODEL_NAME == gemini_31_flash_lite:
    model_name = "g31_f_l"
else:
    model_name = "model_name_missing"


# ==================================
# 1. Convert CSV to JSONL
# ==================================

def csv_to_jsonl(csv_path, jsonl_path):
    print("Converting CSV to JSONL...")
    df = pd.read_csv(csv_path)

    with open(jsonl_path, "w", encoding = "utf-8") as f:
        for index, row in df.iterrows():
            v_id = str(row["video_id"])
            transcript = str(row.get("transcript", ""))

            if not transcript.strip():
                continue

            api_request = {
                "custom_id": v_id,
                "request": {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nHier ist das Transkript:\n\n{transcript}"}]}],
                    "generationConfig": {
                        "responseMimeType": "application/json",
                        "temperature": 0
                    }
                }
            }

            #wirte as row in jsonl file
            f.write(json.dumps(api_request, ensure_ascii=False) + "\n")
    print(f"File {jsonl_path} was successfully created.")
    return True


# ==================================
# 2. Uploading and starting batch job
# ==================================

def start_batch_job(jsonl_path):
    print("Uploading JSONL-file to Google...")
    #uploaded_file = client.files.upload(file = jsonl_path)
    storage_client = storage.Client(project = PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)

    blob_name = f"batch_inputs/{jsonl_path}"
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(jsonl_path)

    gcs_uri = f"gs://{BUCKET_NAME}/{blob_name}"
    print("File successfully uploaded.")

    print("Starting batch job...")
    job = client.batches.create(
        model = MODEL_NAME,
        src = gcs_uri,
    )

    job_id = job.name
    print(f"Job successfully transmitted. Job-ID: {job_id}")
    return job_id


# ==================================
# 3. Executing the request
# ==================================

if __name__ == "__main__":
    try:
        answer = input(f"Configuration:"
                       f"\nModel: {MODEL_NAME}, {model_name}"
                       f"\nPrompt: {SYSTEM_PROMPT}\n Prompt number: {prompt_number}"
                       f"\nOnly start if the last request is already downloaded."
                       f"\nContinue? [Y/n]")
        if not answer.lower() == "y":
            print("Execution stopped. Download old results first.")
            exit()

        csv_to_jsonl(INPUT_CSV, BATCH_INPUT_JSONL)
        job_id = start_batch_job(BATCH_INPUT_JSONL)


        with open(f"job_id_{prompt_number}_{model_name}.txt", "w") as f:
            f.write(f"{job_id}\n{prompt_number}\n{model_name}")


    except Exception as e:
        print(f"Error: {e}")

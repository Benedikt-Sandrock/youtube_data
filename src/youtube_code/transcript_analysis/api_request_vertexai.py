import os
import json
import pandas as pd
from google import genai
from google.cloud import storage
from youtube_code.config import EXPLORATION, BUCKET_NAME, PROJECT_ID, LOCATION, SAMPLES

# ===============================================
# CONFIGURATION
# ===============================================
# Specify seed number and prompts
seed_number = "41"

INPUT_CSV = SAMPLES / "cot_50k_channels" / "transcripts_leftover.csv"
#INPUT_CSV = EXPLORATION / "training_data" / f"sample_vids_{seed_number}.csv"
BATCH_INPUT_JSONL_TEMPLATE = "gemini_batch_input{prompt_number}_{model_name}.jsonl"

MODEL_ALIASES = {
    "gemini_25_flash": "gemini-2.5-flash",
    "gemini_25_flash_lite": "gemini-2.5-flash-lite",
    "gemini_35_flash": "gemini-3.5-flash",
    "gemini_31_flash_lite": "gemini-3.1-flash-lite",
}

prompts_both = {
    # Base prompt (000)
    "PROMPT_01": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.
    
    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".
    
    2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
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
    Bewerte den Text hinsichtlich des Populismusgrads basierend auf dem "ideational approach" auf einer Skala von 0 (gar nicht populistisch) bis 10 (extrem populistisch). 
    - Ein Video, in dem rein neutral argumentiert wird, erhält den Wert 0.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist und kein Bezug zu gesellschaftlichen Debatten oder Eliten hergestellt wird, setze den Score zwingend auf -1.0.
    - Nutze diese Skala für die reine Systemkritik, das Framing "Reine Bevölkerung vs. korrupte Elite" und das Misstrauen gegenüber dem "Mainstream".
    
    4. EVALUATIONS-REGEL:
    Bewerte ausschließlich Aussagen des Creators/Kanalinhabers. Ignoriere Aussagen von gezeigten Dritten (z. B. in Reaction-Ausschnitten oder Interviewgästen), es sei denn, der Creator stimmt ihnen explizit und nachweisbar zu.
    
    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
      "populism_score": 0.0,
    }
    """,

    # Prompt 2: Remove creator-rule (100)
    "PROMPT_02": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".
    
    2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
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
    Bewerte den Text hinsichtlich des Populismusgrads basierend auf dem "ideational approach" auf einer Skala von 0 (gar nicht populistisch) bis 10 (extrem populistisch). 
    - Ein Video, in dem rein neutral argumentiert wird, erhält den Wert 0.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist und kein Bezug zu gesellschaftlichen Debatten oder Eliten hergestellt wird, setze den Score zwingend auf -1.0.
    - Nutze diese Skala für die reine Systemkritik, das Framing "Reine Bevölkerung vs. korrupte Elite" und das Misstrauen gegenüber dem "Mainstream".

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
      "populism_score": 0.0,
    }
    """,

    # Prompt 3: Increase threshold (010)
    "PROMPT_03": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
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
    Bewerte den Text hinsichtlich des Populismusgrads basierend auf dem "ideational approach" auf einer Skala von 0 (gar nicht populistisch) bis 10 (extrem populistisch). 
    - Ein Video, in dem rein neutral argumentiert wird, erhält den Wert 0.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist und kein Bezug zu gesellschaftlichen Debatten oder Eliten hergestellt wird, setze den Score zwingend auf -1.0.
    - Nutze diese Skala für die reine Systemkritik, das Framing "Reine Bevölkerung vs. korrupte Elite" und das Misstrauen gegenüber dem "Mainstream".

    4. EVALUATIONS-REGEL:
    Bewerte ausschließlich Aussagen des Creators/Kanalinhabers. Ignoriere Aussagen von gezeigten Dritten (z. B. in Reaction-Ausschnitten oder Interviewgästen), es sei denn, der Creator stimmt ihnen explizit und nachweisbar zu.

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
      "populism_score": 0.0,
    }
    """,

    # Prompt 4: Scale-instructions (001)
    "PROMPT_04": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die Position des Creators auf einer Skala von 0 (extrem links) bis 10 (extrem rechts).
    - Neutral/ausgewogen = 5.0. Unpolitisches Video = -1.0.

    !!! WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus) !!!
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
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist (z. B. reines Gaming, Kochvideo, Lifestyle ohne gesellschaftlichen Bezug), setze den Score zwingend auf -1.0.

    3. POPULISMUS (Skala 0 bis 10):
    Bewerte den Populismusgrad basierend auf dem "ideational approach".
    WICHTIG: Reine Sachkritik an Institutionen, Politikern oder Gesetzen ist KEIN Populismus. Populismus erfordert zwingend eine moralisierende Abwertung und die Aufteilung der Welt in zwei homogene, antagonistische Gruppen.
    
    Skala (Orientierungspunkte):
    0.0 = Keinerlei populistische Kommunikation. (Entweder komplett unpolitisch oder rein sachliche, differenzierte Kritik an Institutionen/Prozessen ohne moralisierendes Framing).
    2.0 = Erste populistische Tendenzen. (Die Kritik an Institutionen verlässt punktuell die Sachebene. Es gibt vereinzelte, moralisierende Spitzen oder ein leichtes "Wir gegen Die"-Gefühl, das aber nicht den Kern der Argumentation bildet).
    4.0 = Latenter Populismus / Wiederkehrende populistische Kritik. (Institutionen oder Medien werden regelmäßig als abgehoben oder bürgerfern geframed. Die Kritik wechselt wiederholt von der Sachebene in ein pauschalisierendes Muster, bleibt aber noch moderat im Ton).
    6.0 = Manifestierter Populismus / Deutliches Establishment-vs-Bürger-Framing. (Die Argumentation baut aktiv auf dem Gegensatz zwischen "den Bürgern" und "den Institutionen/Eliten" auf. Institutionen wird systematisch unterstellt, nicht im Sinne des Volkes zu handeln).
    8.0 = Starker Populismus / Ausgeprägtes Volk-vs-Elite-Narrativ. (Dominantes Weltbild im Video. "Die Elite/Das System" wird als homogen, egoistisch und grundlegend korrupt dargestellt, während "das Volk" als die einzig moralisch reine Instanz inszeniert wird).
    10.0 = Totaler Populismus / Verschwörungsideologisches Eliten-Narrativ. (Das gesamte Video basiert ausschließlich auf der Prämisse einer fundamental korrupten, böswilligen Elite, die das Volk aktiv betrügt, unterdrückt oder manipuliert. Jegliche Sachlichkeit fehlt).
    
    4. EVALUATIONS-REGEL:
    Bewerte ausschließlich Aussagen des Creators/Kanalinhabers. Ignoriere Aussagen von gezeigten Dritten (z. B. in Reaction-Ausschnitten oder Interviewgästen), es sei denn, der Creator stimmt ihnen explizit und nachweisbar zu.

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
      "populism_score": 0.0,
    }
    """,

    # Prompt 5: Remove creator-rule and increase threshold (110)
    "PROMPT_05": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
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
    Bewerte den Text hinsichtlich des Populismusgrads basierend auf dem "ideational approach" auf einer Skala von 0 (gar nicht populistisch) bis 10 (extrem populistisch). 
    - Ein Video, in dem rein neutral argumentiert wird, erhält den Wert 0.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist und kein Bezug zu gesellschaftlichen Debatten oder Eliten hergestellt wird, setze den Score zwingend auf -1.0.
    - Nutze diese Skala für die reine Systemkritik, das Framing "Reine Bevölkerung vs. korrupte Elite" und das Misstrauen gegenüber dem "Mainstream".

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
      "populism_score": 0.0,
    }
    """,

    # Prompt 6: Remove creator-rule, scale-instructions (101)
    "PROMPT_06": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die Position des Creators auf einer Skala von 0 (extrem links) bis 10 (extrem rechts).
    - Neutral/ausgewogen = 5.0. Unpolitisches Video = -1.0.

    !!! WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus) !!!
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
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist (z. B. reines Gaming, Kochvideo, Lifestyle ohne gesellschaftlichen Bezug), setze den Score zwingend auf -1.0.

    3. POPULISMUS (Skala 0 bis 10):
    Bewerte den Populismusgrad basierend auf dem "ideational approach".
    WICHTIG: Reine Sachkritik an Institutionen, Politikern oder Gesetzen ist KEIN Populismus. Populismus erfordert zwingend eine moralisierende Abwertung und die Aufteilung der Welt in zwei homogene, antagonistische Gruppen.
    
    Skala (Orientierungspunkte):
    0.0 = Keinerlei populistische Kommunikation. (Entweder komplett unpolitisch oder rein sachliche, differenzierte Kritik an Institutionen/Prozessen ohne moralisierendes Framing).
    2.0 = Erste populistische Tendenzen. (Die Kritik an Institutionen verlässt punktuell die Sachebene. Es gibt vereinzelte, moralisierende Spitzen oder ein leichtes "Wir gegen Die"-Gefühl, das aber nicht den Kern der Argumentation bildet).
    4.0 = Latenter Populismus / Wiederkehrende populistische Kritik. (Institutionen oder Medien werden regelmäßig als abgehoben oder bürgerfern geframed. Die Kritik wechselt wiederholt von der Sachebene in ein pauschalisierendes Muster, bleibt aber noch moderat im Ton).
    6.0 = Manifestierter Populismus / Deutliches Establishment-vs-Bürger-Framing. (Die Argumentation baut aktiv auf dem Gegensatz zwischen "den Bürgern" und "den Institutionen/Eliten" auf. Institutionen wird systematisch unterstellt, nicht im Sinne des Volkes zu handeln).
    8.0 = Starker Populismus / Ausgeprägtes Volk-vs-Elite-Narrativ. (Dominantes Weltbild im Video. "Die Elite/Das System" wird als homogen, egoistisch und grundlegend korrupt dargestellt, während "das Volk" als die einzig moralisch reine Instanz inszeniert wird).
    10.0 = Totaler Populismus / Verschwörungsideologisches Eliten-Narrativ. (Das gesamte Video basiert ausschließlich auf der Prämisse einer fundamental korrupten, böswilligen Elite, die das Volk aktiv betrügt, unterdrückt oder manipuliert. Jegliche Sachlichkeit fehlt).
    
    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
      "populism_score": 0.0,
    }
    """,

    # Prompt 7: Increase threshold, scale-instructions (011)
    "PROMPT_07": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die Position des Creators auf einer Skala von 0 (extrem links) bis 10 (extrem rechts).
    - Neutral/ausgewogen = 5.0. Unpolitisches Video = -1.0.

    !!! WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus) !!!
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
    Bewerte den Populismusgrad basierend auf dem "ideational approach".
    WICHTIG: Reine Sachkritik an Institutionen, Politikern oder Gesetzen ist KEIN Populismus. Populismus erfordert zwingend eine moralisierende Abwertung und die Aufteilung der Welt in zwei homogene, antagonistische Gruppen.
    
    Skala (Orientierungspunkte):
    0.0 = Keinerlei populistische Kommunikation. (Entweder komplett unpolitisch oder rein sachliche, differenzierte Kritik an Institutionen/Prozessen ohne moralisierendes Framing).
    2.0 = Erste populistische Tendenzen. (Die Kritik an Institutionen verlässt punktuell die Sachebene. Es gibt vereinzelte, moralisierende Spitzen oder ein leichtes "Wir gegen Die"-Gefühl, das aber nicht den Kern der Argumentation bildet).
    4.0 = Latenter Populismus / Wiederkehrende populistische Kritik. (Institutionen oder Medien werden regelmäßig als abgehoben oder bürgerfern geframed. Die Kritik wechselt wiederholt von der Sachebene in ein pauschalisierendes Muster, bleibt aber noch moderat im Ton).
    6.0 = Manifestierter Populismus / Deutliches Establishment-vs-Bürger-Framing. (Die Argumentation baut aktiv auf dem Gegensatz zwischen "den Bürgern" und "den Institutionen/Eliten" auf. Institutionen wird systematisch unterstellt, nicht im Sinne des Volkes zu handeln).
    8.0 = Starker Populismus / Ausgeprägtes Volk-vs-Elite-Narrativ. (Dominantes Weltbild im Video. "Die Elite/Das System" wird als homogen, egoistisch und grundlegend korrupt dargestellt, während "das Volk" als die einzig moralisch reine Instanz inszeniert wird).
    10.0 = Totaler Populismus / Verschwörungsideologisches Eliten-Narrativ. (Das gesamte Video basiert ausschließlich auf der Prämisse einer fundamental korrupten, böswilligen Elite, die das Volk aktiv betrügt, unterdrückt oder manipuliert. Jegliche Sachlichkeit fehlt).
    
    4. EVALUATIONS-REGEL:
    Bewerte ausschließlich Aussagen des Creators/Kanalinhabers. Ignoriere Aussagen von gezeigten Dritten (z. B. in Reaction-Ausschnitten oder Interviewgästen), es sei denn, der Creator stimmt ihnen explizit und nachweisbar zu.

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
      "populism_score": 0.0,
    }
    """,

    # Prompt 8: Remove creator-rule, increase threshold, scale-instructions (111)
    "PROMPT_08": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die Position des Creators auf einer Skala von 0 (extrem links) bis 10 (extrem rechts).
    - Neutral/ausgewogen = 5.0. Unpolitisches Video = -1.0.

    !!! WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus) !!!
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
    Bewerte den Populismusgrad basierend auf dem "ideational approach".
    WICHTIG: Reine Sachkritik an Institutionen, Politikern oder Gesetzen ist KEIN Populismus. Populismus erfordert zwingend eine moralisierende Abwertung und die Aufteilung der Welt in zwei homogene, antagonistische Gruppen.
    
    Skala (Orientierungspunkte):
    0.0 = Keinerlei populistische Kommunikation. (Entweder komplett unpolitisch oder rein sachliche, differenzierte Kritik an Institutionen/Prozessen ohne moralisierendes Framing).
    2.0 = Erste populistische Tendenzen. (Die Kritik an Institutionen verlässt punktuell die Sachebene. Es gibt vereinzelte, moralisierende Spitzen oder ein leichtes "Wir gegen Die"-Gefühl, das aber nicht den Kern der Argumentation bildet).
    4.0 = Latenter Populismus / Wiederkehrende populistische Kritik. (Institutionen oder Medien werden regelmäßig als abgehoben oder bürgerfern geframed. Die Kritik wechselt wiederholt von der Sachebene in ein pauschalisierendes Muster, bleibt aber noch moderat im Ton).
    6.0 = Manifestierter Populismus / Deutliches Establishment-vs-Bürger-Framing. (Die Argumentation baut aktiv auf dem Gegensatz zwischen "den Bürgern" und "den Institutionen/Eliten" auf. Institutionen wird systematisch unterstellt, nicht im Sinne des Volkes zu handeln).
    8.0 = Starker Populismus / Ausgeprägtes Volk-vs-Elite-Narrativ. (Dominantes Weltbild im Video. "Die Elite/Das System" wird als homogen, egoistisch und grundlegend korrupt dargestellt, während "das Volk" als die einzig moralisch reine Instanz inszeniert wird).
    10.0 = Totaler Populismus / Verschwörungsideologisches Eliten-Narrativ. (Das gesamte Video basiert ausschließlich auf der Prämisse einer fundamental korrupten, böswilligen Elite, die das Volk aktiv betrügt, unterdrückt oder manipuliert. Jegliche Sachlichkeit fehlt).
    
    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
      "populism_score": 0.0,
    }
    """,

}

prompts_ideology = {
    # Base prompt ideology (000)
    "PROMPT_11": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die Position des Creators zu soziokulturellen und gesellschaftspolitischen Themen im Kontext Deutschlands auf einer Skala von 0 (extrem links) bis 10 (extrem rechts). 
    - Die mathematische Mitte (neutral/ausgewogen berichtet, ohne eigenes Framing) liegt exakt bei 5.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist (z. B. reines Gaming, Kochvideo, Lifestyle ohne gesellschaftlichen Bezug), setze den Score zwingend auf -1.0.

    !!! WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus) !!!
    Unterscheide strikt zwischen populistischer Rhetorik (Systemkritik) und der tatsächlichen politischen Ideologie (vorgeschlagene Lösungen):
    - Systemkritik, Anti-Establishment-Rhetorik, pauschales Misstrauen gegenüber Institutionen/Medien und die Aufteilung in "die Elite da oben vs. das Volk" sind reine Merkmale von POPULISMUS, nicht von linker oder rechter Ideologie.
    - Bestimme die IDEOLOGIE (Links vs. Rechts) ausschließlich anhand konkreter Inhalte und Werte:
      -> LINKS (0.0-4.9): Fokus auf soziale Gerechtigkeit, staatliche Regulierung, Umverteilung, Antikapitalismus, progressive Gesellschaftspolitik, Klimaschutz durch Ge- und Verbote.
      -> RECHTS (5.1-10.0): Fokus auf individuelle Freiheit (Wirtschaftsliberalismus), Marktmechanismen, private Sachwerte/Selbstvorsorge, traditionelle Werte, Nationalstaat, explizite Ablehnung staatlicher Eingriffe.

    3. EVALUATIONS-REGEL:
    Bewerte ausschließlich Aussagen des Creators/Kanalinhabers. Ignoriere Aussagen von gezeigten Dritten (z. B. in Reaction-Ausschnitten oder Interviewgästen), es sei denn, der Creator stimmt ihnen explizit und nachweisbar zu.

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
    }
    """,

    # Prompt 2: Remove creator-rule (100)
    "PROMPT_12": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die Position des Creators zu soziokulturellen und gesellschaftspolitischen Themen im Kontext Deutschlands auf einer Skala von 0 (extrem links) bis 10 (extrem rechts). 
    - Die mathematische Mitte (neutral/ausgewogen berichtet, ohne eigenes Framing) liegt exakt bei 5.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist (z. B. reines Gaming, Kochvideo, Lifestyle ohne gesellschaftlichen Bezug), setze den Score zwingend auf -1.0.

    !!! WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus) !!!
    Unterscheide strikt zwischen populistischer Rhetorik (Systemkritik) und der tatsächlichen politischen Ideologie (vorgeschlagene Lösungen):
    - Systemkritik, Anti-Establishment-Rhetorik, pauschales Misstrauen gegenüber Institutionen/Medien und die Aufteilung in "die Elite da oben vs. das Volk" sind reine Merkmale von POPULISMUS, nicht von linker oder rechter Ideologie.
    - Bestimme die IDEOLOGIE (Links vs. Rechts) ausschließlich anhand konkreter Inhalte und Werte:
      -> LINKS (0.0-4.9): Fokus auf soziale Gerechtigkeit, staatliche Regulierung, Umverteilung, Antikapitalismus, progressive Gesellschaftspolitik, Klimaschutz durch Ge- und Verbote.
      -> RECHTS (5.1-10.0): Fokus auf individuelle Freiheit (Wirtschaftsliberalismus), Marktmechanismen, private Sachwerte/Selbstvorsorge, traditionelle Werte, Nationalstaat, explizite Ablehnung staatlicher Eingriffe.

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
    }
    """,

    # Prompt 3: Increase threshold (010)
    "PROMPT_13": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die Position des Creators zu soziokulturellen und gesellschaftspolitischen Themen im Kontext Deutschlands auf einer Skala von 0 (extrem links) bis 10 (extrem rechts). 
    - Die mathematische Mitte (neutral/ausgewogen berichtet, ohne eigenes Framing) liegt exakt bei 5.0.
    - Wenn die im Video behandelten Themen vollständig unpolitisch/ideologiefrei sind (z. B. reines Gaming, Kochvideo, Lifestyle ohne gesellschaftlichen Bezug), setze den Score zwingend auf -1.0. Wenn das Video ein vollständig neutraler Bericht über politische Ereignisse ist, setze den Score auf 5.0.

    !!! WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus) !!!
    Unterscheide strikt zwischen populistischer Rhetorik (Systemkritik) und der tatsächlichen politischen Ideologie (vorgeschlagene Lösungen):
    - Systemkritik, Anti-Establishment-Rhetorik, pauschales Misstrauen gegenüber Institutionen/Medien und die Aufteilung in "die Elite da oben vs. das Volk" sind reine Merkmale von POPULISMUS, nicht von linker oder rechter Ideologie.
    - Bestimme die IDEOLOGIE (Links vs. Rechts) ausschließlich anhand konkreter Inhalte und Werte:
      -> LINKS (0.0-4.9): Fokus auf soziale Gerechtigkeit, staatliche Regulierung, Umverteilung, Antikapitalismus, progressive Gesellschaftspolitik, Klimaschutz durch Ge- und Verbote.
      -> RECHTS (5.1-10.0): Fokus auf individuelle Freiheit (Wirtschaftsliberalismus), Marktmechanismen, private Sachwerte/Selbstvorsorge, traditionelle Werte, Nationalstaat, explizite Ablehnung staatlicher Eingriffe.

    3. EVALUATIONS-REGEL:
    Bewerte ausschließlich Aussagen des Creators/Kanalinhabers. Ignoriere Aussagen von gezeigten Dritten (z. B. in Reaction-Ausschnitten oder Interviewgästen), es sei denn, der Creator stimmt ihnen explizit und nachweisbar zu.

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
    }
    """,

    # Prompt 4: Scale-instructions (001)
    "PROMPT_14": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die Position des Creators auf einer Skala von 0 (extrem links) bis 10 (extrem rechts).
    - Neutral/ausgewogen = 5.0. Unpolitisches Video = -1.0.

    !!! WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus) !!!
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
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist (z. B. reines Gaming, Kochvideo, Lifestyle ohne gesellschaftlichen Bezug), setze den Score zwingend auf -1.0.

    3. EVALUATIONS-REGEL:
    Bewerte ausschließlich Aussagen des Creators/Kanalinhabers. Ignoriere Aussagen von gezeigten Dritten (z. B. in Reaction-Ausschnitten oder Interviewgästen), es sei denn, der Creator stimmt ihnen explizit und nachweisbar zu.

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
    }
    """,

    # Prompt 5: Remove creator-rule and increase threshold (110)
    "PROMPT_15": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die Position des Creators zu soziokulturellen und gesellschaftspolitischen Themen im Kontext Deutschlands auf einer Skala von 0 (extrem links) bis 10 (extrem rechts). 
    - Die mathematische Mitte (neutral/ausgewogen berichtet, ohne eigenes Framing) liegt exakt bei 5.0.
    - Wenn die im Video behandelten Themen vollständig unpolitisch/ideologiefrei sind (z. B. reines Gaming, Kochvideo, Lifestyle ohne gesellschaftlichen Bezug), setze den Score zwingend auf -1.0. Wenn das Video ein vollständig neutraler Bericht über politische Ereignisse ist, setze den Score auf 5.0.

    !!! WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus) !!!
    Unterscheide strikt zwischen populistischer Rhetorik (Systemkritik) und der tatsächlichen politischen Ideologie (vorgeschlagene Lösungen):
    - Systemkritik, Anti-Establishment-Rhetorik, pauschales Misstrauen gegenüber Institutionen/Medien und die Aufteilung in "die Elite da oben vs. das Volk" sind reine Merkmale von POPULISMUS, nicht von linker oder rechter Ideologie.
    - Bestimme die IDEOLOGIE (Links vs. Rechts) ausschließlich anhand konkreter Inhalte und Werte:
      -> LINKS (0.0-4.9): Fokus auf soziale Gerechtigkeit, staatliche Regulierung, Umverteilung, Antikapitalismus, progressive Gesellschaftspolitik, Klimaschutz durch Ge- und Verbote.
      -> RECHTS (5.1-10.0): Fokus auf individuelle Freiheit (Wirtschaftsliberalismus), Marktmechanismen, private Sachwerte/Selbstvorsorge, traditionelle Werte, Nationalstaat, explizite Ablehnung staatlicher Eingriffe.

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
    }
    """,

    # Prompt 6: Remove creator-rule, scale-instructions (101)
    "PROMPT_16": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die Position des Creators auf einer Skala von 0 (extrem links) bis 10 (extrem rechts).
    - Neutral/ausgewogen = 5.0. Unpolitisches Video = -1.0.

    !!! WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus) !!!
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
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist (z. B. reines Gaming, Kochvideo, Lifestyle ohne gesellschaftlichen Bezug), setze den Score zwingend auf -1.0.

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
    }
    """,

    # Prompt 7: Increase threshold, scale-instructions (011)
    "PROMPT_17": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

      2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die Position des Creators auf einer Skala von 0 (extrem links) bis 10 (extrem rechts).
    - Neutral/ausgewogen = 5.0. Unpolitisches Video = -1.0.

    !!! WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus) !!!
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

    3. EVALUATIONS-REGEL:
    Bewerte ausschließlich Aussagen des Creators/Kanalinhabers. Ignoriere Aussagen von gezeigten Dritten (z. B. in Reaction-Ausschnitten oder Interviewgästen), es sei denn, der Creator stimmt ihnen explizit und nachweisbar zu.

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
    }
    """,

    # Prompt 8: Remove creator-rule, increase threshold, scale-instructions (111)
    "PROMPT_18": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
    Bewerte die Position des Creators auf einer Skala von 0 (extrem links) bis 10 (extrem rechts).
    - Neutral/ausgewogen = 5.0. Unpolitisches Video = -1.0.

    !!! WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus) !!!
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
    
    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
     "video_type": "Reaction",
     "ideology_score": 5.0,
    }
    """,

}

prompts_populism = {
    # Base prompt populism (000)
    "PROMPT_21": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POPULISMUS (Skala 0 bis 10):
    Bewerte den Text hinsichtlich des Populismusgrads basierend auf dem "ideational approach" auf einer Skala von 0 (gar nicht populistisch) bis 10 (extrem populistisch). 
    - Ein Video, in dem rein neutral argumentiert wird, erhält den Wert 0.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist und kein Bezug zu gesellschaftlichen Debatten oder Eliten hergestellt wird, setze den Score zwingend auf -1.0.
    - Nutze diese Skala für die reine Systemkritik, das Framing "Reine Bevölkerung vs. korrupte Elite" und das Misstrauen gegenüber dem "Mainstream".

    3. EVALUATIONS-REGEL:
    Bewerte ausschließlich Aussagen des Creators/Kanalinhabers. Ignoriere Aussagen von gezeigten Dritten (z. B. in Reaction-Ausschnitten oder Interviewgästen), es sei denn, der Creator stimmt ihnen explizit und nachweisbar zu.

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "populism_score": 0.0,
    }
    """,

    # Prompt 2: Remove creator-rule (100)
    "PROMPT_22": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POPULISMUS (Skala 0 bis 10):
    Bewerte den Text hinsichtlich des Populismusgrads basierend auf dem "ideational approach" auf einer Skala von 0 (gar nicht populistisch) bis 10 (extrem populistisch). 
    - Ein Video, in dem rein neutral argumentiert wird, erhält den Wert 0.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist und kein Bezug zu gesellschaftlichen Debatten oder Eliten hergestellt wird, setze den Score zwingend auf -1.0.
    - Nutze diese Skala für die reine Systemkritik, das Framing "Reine Bevölkerung vs. korrupte Elite" und das Misstrauen gegenüber dem "Mainstream".

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "populism_score": 0.0,
    }
    """,

    # Prompt 3: Increase threshold (010)
    "PROMPT_23": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POPULISMUS (Skala 0 bis 10):
    Bewerte den Text hinsichtlich des Populismusgrads basierend auf dem "ideational approach" auf einer Skala von 0 (gar nicht populistisch) bis 10 (extrem populistisch). 
    - Ein Video, in dem rein neutral argumentiert wird, erhält den Wert 0.0.
    - Wenn die im Video behandelten Themen vollständig unpolitisch/ideologiefrei sind und kein Bezug zu gesellschaftlichen Debatten oder Eliten hergestellt wird, setze den Score zwingend auf -1.0. Wenn das Video ein vollständig neutraler Bericht über politische Ereignisse ist, setze den Score auf 0.0.
    - Nutze diese Skala für die reine Systemkritik, das Framing "Reine Bevölkerung vs. korrupte Elite" und das Misstrauen gegenüber dem "Mainstream".

    3. EVALUATIONS-REGEL:
    Bewerte ausschließlich Aussagen des Creators/Kanalinhabers. Ignoriere Aussagen von gezeigten Dritten (z. B. in Reaction-Ausschnitten oder Interviewgästen), es sei denn, der Creator stimmt ihnen explizit und nachweisbar zu.

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "populism_score": 0.0,
    }
    """,

    # Prompt 4: Scale-instructions (001)
    "PROMPT_24": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POPULISMUS (Skala 0 bis 10):
    Bewerte den Populismusgrad basierend auf dem "ideational approach".
    WICHTIG: Reine Sachkritik an Institutionen, Politikern oder Gesetzen ist KEIN Populismus. Populismus erfordert zwingend eine moralisierende Abwertung und die Aufteilung der Welt in zwei homogene, antagonistische Gruppen.
    
    Skala (Orientierungspunkte):
    0.0 = Keinerlei populistische Kommunikation. (Entweder komplett unpolitisch oder rein sachliche, differenzierte Kritik an Institutionen/Prozessen ohne moralisierendes Framing).
    2.0 = Erste populistische Tendenzen. (Die Kritik an Institutionen verlässt punktuell die Sachebene. Es gibt vereinzelte, moralisierende Spitzen oder ein leichtes "Wir gegen Die"-Gefühl, das aber nicht den Kern der Argumentation bildet).
    4.0 = Latenter Populismus / Wiederkehrende populistische Kritik. (Institutionen oder Medien werden regelmäßig als abgehoben oder bürgerfern geframed. Die Kritik wechselt wiederholt von der Sachebene in ein pauschalisierendes Muster, bleibt aber noch moderat im Ton).
    6.0 = Manifestierter Populismus / Deutliches Establishment-vs-Bürger-Framing. (Die Argumentation baut aktiv auf dem Gegensatz zwischen "den Bürgern" und "den Institutionen/Eliten" auf. Institutionen wird systematisch unterstellt, nicht im Sinne des Volkes zu handeln).
    8.0 = Starker Populismus / Ausgeprägtes Volk-vs-Elite-Narrativ. (Dominantes Weltbild im Video. "Die Elite/Das System" wird als homogen, egoistisch und grundlegend korrupt dargestellt, während "das Volk" als die einzig moralisch reine Instanz inszeniert wird).
    10.0 = Totaler Populismus / Verschwörungsideologisches Eliten-Narrativ. (Das gesamte Video basiert ausschließlich auf der Prämisse einer fundamental korrupten, böswilligen Elite, die das Volk aktiv betrügt, unterdrückt oder manipuliert. Jegliche Sachlichkeit fehlt).
    
    3. EVALUATIONS-REGEL:
    Bewerte ausschließlich Aussagen des Creators/Kanalinhabers. Ignoriere Aussagen von gezeigten Dritten (z. B. in Reaction-Ausschnitten oder Interviewgästen), es sei denn, der Creator stimmt ihnen explizit und nachweisbar zu.

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "populism_score": 0.0,
    }
    """,

    # Prompt 5: Remove creator-rule and increase threshold (110)
    "PROMPT_25": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POPULISMUS (Skala 0 bis 10):
    Bewerte den Text hinsichtlich des Populismusgrads basierend auf dem "ideational approach" auf einer Skala von 0 (gar nicht populistisch) bis 10 (extrem populistisch). 
    - Ein Video, in dem rein neutral argumentiert wird, erhält den Wert 0.0.
    - Wenn die im Video behandelten Themen vollständig unpolitisch/ideologiefrei sind und kein Bezug zu gesellschaftlichen Debatten oder Eliten hergestellt wird, setze den Score zwingend auf -1.0. Wenn das Video ein vollständig neutraler Bericht über politische Ereignisse ist, setze den Score auf 0.0.
    - Nutze diese Skala für die reine Systemkritik, das Framing "Reine Bevölkerung vs. korrupte Elite" und das Misstrauen gegenüber dem "Mainstream".

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "populism_score": 0.0,
    }
    """,

    # Prompt 6: Remove creator-rule, scale-instructions (101)
    "PROMPT_26": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POPULISMUS (Skala 0 bis 10):
    Bewerte den Populismusgrad basierend auf dem "ideational approach".
    WICHTIG: Reine Sachkritik an Institutionen, Politikern oder Gesetzen ist KEIN Populismus. Populismus erfordert zwingend eine moralisierende Abwertung und die Aufteilung der Welt in zwei homogene, antagonistische Gruppen.
    
    Skala (Orientierungspunkte):
    0.0 = Keinerlei populistische Kommunikation. (Entweder komplett unpolitisch oder rein sachliche, differenzierte Kritik an Institutionen/Prozessen ohne moralisierendes Framing).
    2.0 = Erste populistische Tendenzen. (Die Kritik an Institutionen verlässt punktuell die Sachebene. Es gibt vereinzelte, moralisierende Spitzen oder ein leichtes "Wir gegen Die"-Gefühl, das aber nicht den Kern der Argumentation bildet).
    4.0 = Latenter Populismus / Wiederkehrende populistische Kritik. (Institutionen oder Medien werden regelmäßig als abgehoben oder bürgerfern geframed. Die Kritik wechselt wiederholt von der Sachebene in ein pauschalisierendes Muster, bleibt aber noch moderat im Ton).
    6.0 = Manifestierter Populismus / Deutliches Establishment-vs-Bürger-Framing. (Die Argumentation baut aktiv auf dem Gegensatz zwischen "den Bürgern" und "den Institutionen/Eliten" auf. Institutionen wird systematisch unterstellt, nicht im Sinne des Volkes zu handeln).
    8.0 = Starker Populismus / Ausgeprägtes Volk-vs-Elite-Narrativ. (Dominantes Weltbild im Video. "Die Elite/Das System" wird als homogen, egoistisch und grundlegend korrupt dargestellt, während "das Volk" als die einzig moralisch reine Instanz inszeniert wird).
    10.0 = Totaler Populismus / Verschwörungsideologisches Eliten-Narrativ. (Das gesamte Video basiert ausschließlich auf der Prämisse einer fundamental korrupten, böswilligen Elite, die das Volk aktiv betrügt, unterdrückt oder manipuliert. Jegliche Sachlichkeit fehlt).
    
    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "populism_score": 0.0,
    }
    """,

    # Prompt 7: Increase threshold, scale-instructions (011)
    "PROMPT_27": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POPULISMUS (Skala 0 bis 10):
    Bewerte den Populismusgrad basierend auf dem "ideational approach".
    WICHTIG: Reine Sachkritik an Institutionen, Politikern oder Gesetzen ist KEIN Populismus. Populismus erfordert zwingend eine moralisierende Abwertung und die Aufteilung der Welt in zwei homogene, antagonistische Gruppen.
    
    Skala (Orientierungspunkte):
    0.0 = Keinerlei populistische Kommunikation. (Entweder komplett unpolitisch oder rein sachliche, differenzierte Kritik an Institutionen/Prozessen ohne moralisierendes Framing).
    2.0 = Erste populistische Tendenzen. (Die Kritik an Institutionen verlässt punktuell die Sachebene. Es gibt vereinzelte, moralisierende Spitzen oder ein leichtes "Wir gegen Die"-Gefühl, das aber nicht den Kern der Argumentation bildet).
    4.0 = Latenter Populismus / Wiederkehrende populistische Kritik. (Institutionen oder Medien werden regelmäßig als abgehoben oder bürgerfern geframed. Die Kritik wechselt wiederholt von der Sachebene in ein pauschalisierendes Muster, bleibt aber noch moderat im Ton).
    6.0 = Manifestierter Populismus / Deutliches Establishment-vs-Bürger-Framing. (Die Argumentation baut aktiv auf dem Gegensatz zwischen "den Bürgern" und "den Institutionen/Eliten" auf. Institutionen wird systematisch unterstellt, nicht im Sinne des Volkes zu handeln).
    8.0 = Starker Populismus / Ausgeprägtes Volk-vs-Elite-Narrativ. (Dominantes Weltbild im Video. "Die Elite/Das System" wird als homogen, egoistisch und grundlegend korrupt dargestellt, während "das Volk" als die einzig moralisch reine Instanz inszeniert wird).
    10.0 = Totaler Populismus / Verschwörungsideologisches Eliten-Narrativ. (Das gesamte Video basiert ausschließlich auf der Prämisse einer fundamental korrupten, böswilligen Elite, die das Volk aktiv betrügt, unterdrückt oder manipuliert. Jegliche Sachlichkeit fehlt).
    
    - Wenn die im Video behandelten Themen vollständig unpolitisch/ideologiefrei sind und kein Bezug zu gesellschaftlichen Debatten oder Eliten hergestellt wird, setze den Score zwingend auf -1.0. Wenn das Video ein vollständig neutraler Bericht über politische Ereignisse ist, setze den Score auf 0.0.

    3. EVALUATIONS-REGEL:
    Bewerte ausschließlich Aussagen des Creators/Kanalinhabers. Ignoriere Aussagen von gezeigten Dritten (z. B. in Reaction-Ausschnitten oder Interviewgästen), es sei denn, der Creator stimmt ihnen explizit und nachweisbar zu.

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "populism_score": 0.0,
    }
    """,

    # Prompt 8: Remove creator-rule, increase threshold, scale-instructions (111)
    "PROMPT_28": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POPULISMUS (Skala 0 bis 10):
    Bewerte den Populismusgrad basierend auf dem "ideational approach".
    WICHTIG: Reine Sachkritik an Institutionen, Politikern oder Gesetzen ist KEIN Populismus. Populismus erfordert zwingend eine moralisierende Abwertung und die Aufteilung der Welt in zwei homogene, antagonistische Gruppen.
    
    Skala (Orientierungspunkte):
    0.0 = Keinerlei populistische Kommunikation. (Entweder komplett unpolitisch oder rein sachliche, differenzierte Kritik an Institutionen/Prozessen ohne moralisierendes Framing).
    2.0 = Erste populistische Tendenzen. (Die Kritik an Institutionen verlässt punktuell die Sachebene. Es gibt vereinzelte, moralisierende Spitzen oder ein leichtes "Wir gegen Die"-Gefühl, das aber nicht den Kern der Argumentation bildet).
    4.0 = Latenter Populismus / Wiederkehrende populistische Kritik. (Institutionen oder Medien werden regelmäßig als abgehoben oder bürgerfern geframed. Die Kritik wechselt wiederholt von der Sachebene in ein pauschalisierendes Muster, bleibt aber noch moderat im Ton).
    6.0 = Manifestierter Populismus / Deutliches Establishment-vs-Bürger-Framing. (Die Argumentation baut aktiv auf dem Gegensatz zwischen "den Bürgern" und "den Institutionen/Eliten" auf. Institutionen wird systematisch unterstellt, nicht im Sinne des Volkes zu handeln).
    8.0 = Starker Populismus / Ausgeprägtes Volk-vs-Elite-Narrativ. (Dominantes Weltbild im Video. "Die Elite/Das System" wird als homogen, egoistisch und grundlegend korrupt dargestellt, während "das Volk" als die einzig moralisch reine Instanz inszeniert wird).
    10.0 = Totaler Populismus / Verschwörungsideologisches Eliten-Narrativ. (Das gesamte Video basiert ausschließlich auf der Prämisse einer fundamental korrupten, böswilligen Elite, die das Volk aktiv betrügt, unterdrückt oder manipuliert. Jegliche Sachlichkeit fehlt).
    
    - Wenn die im Video behandelten Themen vollständig unpolitisch/ideologiefrei sind und kein Bezug zu gesellschaftlichen Debatten oder Eliten hergestellt wird, setze den Score zwingend auf -1.0. Wenn das Video ein vollständig neutraler Bericht über politische Ereignisse ist, setze den Score auf 0.0.

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "populism_score": 0.0,
    }
    """,
}

prompt_5_adjusted = {
"PROMPT_051": """
    Du erhältst das Transkript eines deutschen YouTube-Videos. Analysiere es anhand der folgenden Kriterien und strukturiere das Ergebnis exakt nach dem vorgegebenen JSON-Schema.

    1. VIDEO-TYP:
    Bestimme, ob es sich um ein Reaction-Video handelt. Erlaubte Werte: "Reaction" oder "Standard".

    2. POLITISCHE IDEOLOGIE (Skala 0 bis 10):
    Bewerte im Video zum Ausdruck gebrachte Position zu soziokulturellen und gesellschaftspolitischen Themen im Kontext Deutschlands auf einer Skala von 0 (extrem links) bis 10 (extrem rechts). 
    - Die mathematische Mitte (neutral/ausgewogen berichtet, ohne eigenes Framing) liegt exakt bei 5.0.
    - Wenn die im Video behandelten Themen vollständig unpolitisch/ideologiefrei sind (z. B. reines Gaming, Kochvideo, Lifestyle ohne gesellschaftlichen Bezug), setze den Score zwingend auf -1.0. Wenn das Video ein vollständig neutraler Bericht über politische Ereignisse ist, setze den Score auf 5.0.

    !!! WICHTIGER DIAGNOSTISCHER UNTERSCHIED (Ideologie vs. Populismus) !!!
    Unterscheide strikt zwischen populistischer Rhetorik (Systemkritik) und der tatsächlichen politischen Ideologie (vorgeschlagene Lösungen):
    - Systemkritik, Anti-Establishment-Rhetorik, pauschales Misstrauen gegenüber Institutionen/Medien und die Aufteilung in "die Elite da oben vs. das Volk" sind reine Merkmale von POPULISMUS, nicht von linker oder rechter Ideologie.
    - Bestimme die IDEOLOGIE (Links vs. Rechts) ausschließlich anhand konkreter Inhalte und Werte:
      -> LINKS (0.0-4.9): Fokus auf soziale Gerechtigkeit, staatliche Regulierung, Umverteilung, Antikapitalismus, progressive Gesellschaftspolitik, Klimaschutz durch Ge- und Verbote.
      -> RECHTS (5.1-10.0): Fokus auf individuelle Freiheit (Wirtschaftsliberalismus), Marktmechanismen, private Sachwerte/Selbstvorsorge, traditionelle Werte, Nationalstaat, explizite Ablehnung staatlicher Eingriffe.

    3. POPULISMUS (Skala 0 bis 10):
    Bewerte den Text hinsichtlich des Populismusgrads basierend auf dem "ideational approach" auf einer Skala von 0 (gar nicht populistisch) bis 10 (extrem populistisch). 
    - Ein Video, in dem rein neutral argumentiert wird, erhält den Wert 0.0.
    - Wenn das Video vollständig unpolitisch/ideologiefrei ist und kein Bezug zu gesellschaftlichen Debatten oder Eliten hergestellt wird, setze den Score zwingend auf -1.0.
    - Nutze diese Skala für die reine Systemkritik, das Framing "Reine Bevölkerung vs. korrupte Elite" und das Misstrauen gegenüber dem "Mainstream".

    Ausgabeformat:
    Gib ausschließlich ein valides JSON-Objekt zurück. Kein Markdown-Codeblock, kein Text davor oder danach. 
    Die Struktur MUSS exakt so aussehen:
    {
      "video_type": "Reaction",
      "ideology_score": 5.0,
      "populism_score": 0.0,
    }
    """,
}
### Choose prompts ###

prompts = prompt_5_adjusted    # [prompts_both, prompts_ideology, prompts_populism]

client = genai.Client(
    vertexai = True,
    project=PROJECT_ID,
    location = LOCATION
)

# ===============================================
# FUNCTIONS
# ===============================================

def get_prompt_number(prompt_key: str) -> str:
    if prompt_key.startswith("PROMPT_") and prompt_key[7:].isdigit():
        return prompt_key.split("_")[1]
    elif prompt_key.startswith("GPT_") and prompt_key[4:].isdigit():
        return "gpt" + prompt_key.split("_")[1]
    else:
        return "0"


def csv_to_jsonl(csv_path, jsonl_path, system_prompt):
    print(f"Converting CSV to JSONL -> {jsonl_path}")
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
                            "parts": [{"text": f"{system_prompt}\n\nHier ist das Transkript:\n\n{transcript}"}]}],
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


def start_batch_job(jsonl_path, model):
    print(f"Uploading {jsonl_path} to GCS...")
    storage_client = storage.Client(project = PROJECT_ID)
    bucket = storage_client.bucket(BUCKET_NAME)

    blob_name = f"batch_inputs/{jsonl_path}"
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(jsonl_path)

    gcs_uri = f"gs://{BUCKET_NAME}/{blob_name}"
    print("File successfully uploaded.")

    print("Starting batch job...")
    job = client.batches.create(model = model,
        src = gcs_uri,)

    os.remove(jsonl_path)
    print(f"JSONL file ('{jsonl_path}') locally deleted.")
    return job.name


def run_all_prompts(csv_path, prompt_keys, model_name: str = "gemini_25_flash", dry_run: bool = False):
    model_alias = MODEL_ALIASES.get(model_name, "unknown_model")
    if isinstance(prompt_keys, str):
        prompt_keys = [prompt_keys]

    df = pd.read_csv(csv_path)
    transcripts = len(df)

    print(f"\n{'=' * 60}")
    print(f"Input: '{csv_path}'")
    print(f"Model: {model_alias}")
    print(f"Prompts to run: {len(prompt_keys)}")
    print(f"Prompts: {prompt_keys}")
    print(f"Number of transcripts to be rated: {transcripts}")
    print(f"Dry run: {dry_run}")
    print(f"{'=' * 60}\n")

    answer = input("Start all jobs? [Y/n]")
    if answer.strip().lower() != "y":
        print("Aborted.")
        return

    results = {}
    failed = []

    for i, prompt_key in enumerate(prompt_keys, 1):
        prompt_number = get_prompt_number(prompt_key)
        system_prompt = prompts[prompt_key]
        jsonl_path = BATCH_INPUT_JSONL_TEMPLATE.format(
            prompt_number=prompt_number,
            model_name=model_name
        )

        print(f"\n[{i}/{len(prompt_keys)}] Processing {prompt_key}")

        try:
            id_file_path = f"id_files/job_id_{prompt_number}_{model_alias}.txt"
            #answer = "y"
            if os.path.exists(id_file_path):
                answer = input(f"ID file '{id_file_path}' still in 'id_files'."
                               f"\nOverwrite? [y/N] ")

                if not answer.strip().lower() == "y":
                    print(f"Prompt {prompt_number} skipped. Continuing with next request.")
                    continue

            if not dry_run:
                csv_to_jsonl(csv_path, jsonl_path, system_prompt)
                job_id = start_batch_job(jsonl_path, model_alias)

            else:
                print(f"[DRY RUN] Would create {jsonl_path} and submit job.")
                job_id = f"dry-run-job-{prompt_number}"

            with open(id_file_path, "w") as f:
                f.write(f"{job_id}\n{prompt_number}\n{model_alias}")

                results[prompt_key] = {"job_id": job_id, "status": "submitted"}
                print(f"ID file saved: {id_file_path}")


        except Exception as e:
            print(f"Error for {prompt_key}: {e}")
            failed.append(prompt_key)
            results[prompt_key] = {"job_id": None, "status": f"Error: {e}"}

    print(f"\n{'='*60}")
    print(f"Summary: {len(prompt_keys) - len(failed)}/{len(prompt_keys)} jobs submitted successfully.")
    if failed:
        print(f"Failed: {failed}")
    for key, info in results.items():
        status_icon = "✓" if info["status"] == "submitted" else "✗"
        print(f"  {status_icon} {key}: {info['job_id']}")
    print(f"{'=' * 60}\n")

    return results


# ===============================================
# MAIN
# ===============================================

if __name__ == "__main__":
    PROMPTS_TO_RUN = list(prompts.keys())

    run_all_prompts(
        csv_path = INPUT_CSV,
        prompt_keys = PROMPTS_TO_RUN,
        model_name = "gemini_25_flash",
        dry_run = False
    )

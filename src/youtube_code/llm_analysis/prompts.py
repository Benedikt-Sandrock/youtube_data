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

prompts_populism_creator = {
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
}

prompts_populism_all = {
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

prompt_99_sentiment = {
    "PROMPT_99_SENTIMENT": """Du analysierst ein Transkript eines deutschsprachigen YouTube-Videos zum Nahostkonflikt.

Bewerte für jeden der folgenden Akteure, FALLS er im Transkript vorkommt, das Sentiment gegenüber seinen Handlungen/seiner Politik (nicht: Mitgefühl mit Leid, das er erfährt):

- israel_regierung (Staat Israel, Regierung, Militär/IDF)
- palaestinenser_zivil (palästinensische Zivilbevölkerung, NICHT Hamas)
- hamas (Hamas als Organisation)
- westliche_staaten (USA, EU, Deutschland u.a. im Kontext des Konflikts)

Wert pro Akteur auf einer kontinuierlichen Skala: -1 (negativ), -0.5 (eher negativ), 0 (neutral), +0.5 (eher positiv), +1 (positiv) | null (falls Akteur im Transkript nicht vorkommt)

Wichtig: Eine reine Schilderung, dass ein Akteur Opfer von Gewalt wird, ist NICHT automatisch "positiv" für diesen Akteur — kodiere in diesem Fall "null", sofern keine explizite Bewertung seines Handelns erfolgt.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt, keine Erklärung, kein Markdown:
{"israel_regierung": ..., "palaestinenser_zivil": ..., "hamas": ..., "westliche_staaten": ...}
"""
}

### Choose prompts ###

prompts = prompts_populism_all  # [prompts_both, prompts_ideology, prompts_populism]
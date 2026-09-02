import os
from dotenv import load_dotenv


load_dotenv()

# API Keys
API_KEY = os.getenv("API_KEY")
API_KEY_C = os.getenv("API_KEY_C")
API_KEY_GEMINI = os.getenv("API_KEY_GEMINI")


#Gemini settings
BUCKET_NAME = os.getenv("GCP_BUCKET_NAME")
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = "us-central1"


# General lists/variables
KEYWORDS_MIDDLE_EAST = ["nahe osten", "naher osten", "nahen osten", "nahost", "shani louk", "israël",
            "israel", "palästina", "palästin", "gaza", "hamas", "IDF", "Jerusalem",
            "netanjahu", "netanyahu", "hisbollah", "mossad"]

KEYWORDS_RUSSIA_UKRAINE = ["russland", "ukraine", "putin", "selenskyj", "zelensky",
                           "kiew", "moskau", "ukrain", "russisch",]
# how to capture videos like "Europa: Aufrüsten für den Frieden?"

IDEOLOGY_BINS = [-0.1, 4.5, 6, 10.1]
IDEOLOGY_BINS_STRICT = [-0.1, 4, 6.5, 10.1]
IDEOLOGY_LABELS = ["left", "center", "right"]

POPULISM_BINS = [-0.1, 3, 7, 10.1]
POPULISM_LABELS = ["low", "moderate", "high"]

# Mindestlaenge (Sekunden), ab der ein Video ueberhaupt als Kandidat fuer
# Titel-Screening (Schritt 2) und Themen-Relevanz-Klassifikation (Schritt 3)
# beruecksichtigt wird - zentral durchgesetzt in
# video_registry.get_videos_with_text(). Kuerzere Videos (z.B. Shorts) werden
# dort automatisch verworfen.
MIN_VIDEO_DURATION_SECONDS = 181




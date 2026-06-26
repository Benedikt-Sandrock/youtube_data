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
KEYWORDS = ["nahe osten", "naher osten", "nahen osten", "nahost", "shani louk", "israël",
            "israel", "palästina", "palästin", "gaza", "hamas", "IDF", "Jerusalem",
            "netanjahu", "netanyahu", "hisbollah", "mossad"]

IDEOLOGY_BINS = [-0.1, 4, 6, 10.1]
IDEOLOGY_BINS_STRICT = [-0.1, 3.5, 6.5, 10.1]
IDEOLOGY_LABELS = ["left", "center", "right"]

POPULISM_BINS = [-0.1, 3, 7, 10.1]
POPULISM_LABELS = ["low", "moderate", "high"]




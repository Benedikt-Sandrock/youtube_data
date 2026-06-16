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


KEYWORDS = ["nahe osten", "naher osten", "nahen osten", "nahost", "shani louk", "israël",
            "israel", "palästina", "palästin", "gaza", "hamas", "IDF", "Jerusalem",
            "netanjahu", "netanyahu", "hisbollah", "mossad"]




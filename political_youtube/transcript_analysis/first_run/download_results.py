from dotenv import load_dotenv
import os
from google import genai
import pandas as pd
import json


load_dotenv()
API_KEY = os.getenv("API_KEY_GEMINI")

client = genai.Client(api_key = API_KEY)

for job in client.batches.list():
    print("")


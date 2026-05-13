from google import genai
from google.genai  import types
import pandas as pd
import time
from dotenv import load_dotenv
import os
import json

load_dotenv()
api_key_gem = os.getenv("API_KEY_GEMINI")

model_name = "gemini-3.1-flash-lite"
client = genai.Client(api_key = api_key_gem)



def analyze_transcript(video_id, transcript):
    prompt = f"""
    Bewerte die politische Ideologie des Videos (Video ID = {video_id}) auf einer Skala von 1 (linksaußen) bis 5 (rechtsaußen).
    Achte dabei auf die Absicht, mit der der Urheber des Videos spricht. Achte auf Satire und Ironie.
    Bewerte nur die Aussagen des Urhebers des Videos, keine Sequenzen aus anderen Videos, die er einblendet, oder andere Quellen, die er zitiert.
    
    Gib die Antwort streng in folgender Struktur aus:
    {{
      "video_id": "{video_id}",
      "ideology_score": Integer
    }}
    
    Hier ist das Transkript: {transcript}
    """

    try:
        response = client.models.generate_content(
            model = model_name,
            contents = prompt,
            config = types.GenerateContentConfig(
                response_mime_type = "application/json"
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Error: {e}")
        return None


file_path = "transcripts_channel.csv"
df = pd.read_csv(file_path)
all_results = []

for index, row in df.iterrows():
    print(f"Analyzing {row["video_id"]}...")
    result = analyze_transcript(row["video_id"], row["transcript"])

    if result:
        all_results.append(result)

    time.sleep(5)

    output_df = pd.DataFrame(all_results)
    output_df.to_csv("transcripts_ideology.csv", index = False)



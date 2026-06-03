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
    You will be provided with a transcript of a YouTube video.
    Where does this text stand on the ‘left’ to ‘right’ wing scale in terms of political ideology? 
    Provide your response as a score between 0 and 100 where 0 means ‘Extremely left’ and 100 means ‘Extremely right’.
    Ideology is here defined in the context of the German political system. 
    If the text does not have political content, set the score to -1. 
    You will only respond with a JSON object with the following structure:
    
    {{
      "video_id": "{video_id}",
      "ideology_score": Integer
    }}
    
    Here is the transcript: {transcript}
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
    output_df.to_csv("transcripts_ideology_en_.csv", index = False)



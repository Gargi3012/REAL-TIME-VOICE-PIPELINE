import os
import requests
from dotenv import load_dotenv

load_dotenv()
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")

file_path = "/Users/rahulmanchanda/.gemini/antigravity/brain/656eae5e-3db1-496f-9333-96b5b051bcb7/uploaded_media_1784623657997.img"

headers = {
    "Authorization": f"Token {DEEPGRAM_API_KEY}",
    "Content-Type": "audio/webm"
}

with open(file_path, "rb") as audio:
    response = requests.post(
        "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true",
        headers=headers,
        data=audio
    )

if response.status_code == 200:
    print("Transcription:")
    print(response.json()["results"]["channels"][0]["alternatives"][0]["transcript"])
else:
    print(f"Error {response.status_code}: {response.text}")

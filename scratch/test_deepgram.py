import os
import requests
from dotenv import load_dotenv

load_dotenv()
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")
print(f"Using API Key: {DEEPGRAM_API_KEY[:6]}...")

file_path = "hmm.wav"

headers = {
    "Authorization": f"Token {DEEPGRAM_API_KEY}",
    "Content-Type": "audio/wav"
}

with open(file_path, "rb") as audio:
    response = requests.post(
        "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true",
        headers=headers,
        data=audio
    )

if response.status_code == 200:
    print("Transcription Success:")
    print(response.json()["results"]["channels"][0]["alternatives"][0]["transcript"])
else:
    print(f"Error {response.status_code}: {response.text}")

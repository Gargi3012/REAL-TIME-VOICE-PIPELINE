import urllib.request
import json
import os
from dotenv import load_dotenv

load_dotenv()

text = "Hello, I'm Sarah from Cybernauts Noida. How can I assist you?"
voice_id = "829ccd10-f8b3-43cd-b8a0-4aeaa81f3b30" # Linda

url = "https://api.cartesia.ai/tts/bytes"
data = json.dumps({
    "model_id": "sonic-english",
    "transcript": text,
    "voice": {
        "mode": "id",
        "id": voice_id
    },
    "output_format": {
        "container": "wav",
        "encoding": "pcm_f32le",
        "sample_rate": 8000
    }
}).encode()

req = urllib.request.Request(url, data=data, headers={
    "X-API-Key": os.environ["CARTESIA_API_KEY"],
    "Cartesia-Version": "2024-06-10",
    "Content-Type": "application/json"
})

with urllib.request.urlopen(req) as response:
    with open("greetings.wav", "wb") as f:
        f.write(response.read())
print("Greeting generated.")

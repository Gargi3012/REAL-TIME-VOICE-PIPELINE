import urllib.request
import json
import os
from dotenv import load_dotenv

load_dotenv()

req = urllib.request.Request("https://api.cartesia.ai/voices", headers={"X-API-Key": os.environ["CARTESIA_API_KEY"], "Cartesia-Version": "2024-06-10"})
with urllib.request.urlopen(req) as response:
    voices = json.loads(response.read().decode())
    print("All Feminine and Custom Voices:")
    for v in voices:
        name = v.get("name", "")
        vid = v.get("id", "")
        # Print voice if feminine or has customized name
        print(f"ID: {vid} | Name: {name} | Lang: {v.get('language')} | Gender: {v.get('gender')}")

import urllib.request
import json
import os
from dotenv import load_dotenv

load_dotenv()

req = urllib.request.Request("https://api.cartesia.ai/voices", headers={"X-API-Key": os.environ["CARTESIA_API_KEY"], "Cartesia-Version": "2024-06-10"})
with urllib.request.urlopen(req) as response:
    voices = json.loads(response.read().decode())
    females = [v for v in voices if v.get("gender") == "feminine" and v.get("language") == "en"]
    for v in females[:5]:
        print(f"ID: {v['id']} | Name: {v['name']}")

import os
from cartesia import Cartesia
from dotenv import load_dotenv

load_dotenv()
client = Cartesia(api_key=os.environ.get("CARTESIA_API_KEY"))

voice_id = "829ccd10-f8b3-43cd-b8a0-4aeaa81f3b30" # Linda
fillers = {
    "hmm.wav": "Hmm...",
    "wait_a_minute.wav": "Wait a minute...",
    "let_me_think.wav": "Let me think..."
}

for filename, text in fillers.items():
    res = client.tts.generate(
        model_id="sonic-3.5",
        transcript=text,
        voice={"mode": "id", "id": voice_id},
        output_format={
            "container": "wav",
            "encoding": "pcm_s16le",
            "sample_rate": 8000,
        },
    )
    with open(filename, "wb") as f:
        f.write(res.content)
    print(f"Generated {filename}")

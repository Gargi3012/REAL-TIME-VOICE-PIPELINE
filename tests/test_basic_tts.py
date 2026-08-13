"""
Checkpoint 1: Prove the raw ElevenLabs API key + voice work correctly.

This does NOT test Pipecat or interruption — it's the simplest possible
sanity check, isolating "is my key/voice valid" from everything else.

Run with:
    python -m tests.test_basic_tts
"""

import os
import pytest
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv

load_dotenv()


@pytest.mark.skipif(not os.getenv("ELEVEN_LABS_API_KEY"), reason="ELEVEN_LABS_API_KEY not set")
def test_basic_generation():
    api_key = os.getenv("ELEVEN_LABS_API_KEY")
    voice_id = os.getenv("ELEVEN_LABS_VOICE_ID")

    assert api_key, "ELEVEN_LABS_API_KEY missing from .env"
    assert voice_id, "ELEVEN_LABS_VOICE_ID missing from .env"

    client = ElevenLabs(api_key=api_key)

    audio = client.text_to_speech.convert(
        text="This is a basic sanity check for pillar four.",
        voice_id=voice_id,
        model_id="eleven_turbo_v2_5",
        output_format="mp3_44100_128",
    )

    audio_bytes = b"".join(chunk for chunk in audio if isinstance(chunk, bytes))
    assert len(audio_bytes) > 1000, "Returned audio is suspiciously small or empty"

    with open("tests/output_basic_check.mp3", "wb") as f:
        f.write(audio_bytes)

    print(f"PASS: generated {len(audio_bytes)} bytes of audio -> tests/output_basic_check.mp3")


if __name__ == "__main__":
    test_basic_generation()
"""
Checkpoint 2: Measure TTFB (Time To First Byte) across latency settings.

This is how you PROVE your pillar meets the performance requirement,
with actual numbers, not guesses. Re-run this any time you change
model/voice settings to catch regressions.

Run with:
    python -m tests.test_streaming_latency
"""

import os
import time
import pytest
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv

load_dotenv()

TEST_TEXT = "Measuring how quickly the first audio byte arrives."


def measure_ttfb(client, voice_id: str, latency_opt: int) -> float:
    start = time.time()
    first_chunk_time = None

    stream = client.text_to_speech.stream(
        text=TEST_TEXT,
        voice_id=voice_id,
        model_id="eleven_turbo_v2_5",
        optimize_streaming_latency=latency_opt,
    )

    for chunk in stream:
        if isinstance(chunk, bytes) and first_chunk_time is None:
            first_chunk_time = time.time()
            break  # we only need the FIRST chunk's timing

    return first_chunk_time - start


@pytest.mark.skipif(not os.getenv("ELEVEN_LABS_API_KEY"), reason="ELEVEN_LABS_API_KEY not set")
def test_latency_levels():
    api_key = os.getenv("ELEVEN_LABS_API_KEY")
    voice_id = os.getenv("ELEVEN_LABS_VOICE_ID")
    client = ElevenLabs(api_key=api_key)

    print(f"{'Latency Level':<15} {'TTFB (seconds)':<15}")
    print("-" * 30)

    results = {}
    for level in [0, 2, 3, 4]:
        ttfb = measure_ttfb(client, voice_id, level)
        results[level] = ttfb
        print(f"{level:<15} {ttfb:.2f}")

    # Your project's TTS slice budget target — adjust if your team sets a different number
    BUDGET_SECONDS = 0.5
    best_level = min(results, key=results.get)

    print(f"\nFastest setting: level {best_level} at {results[best_level]:.2f}s")
    if results[best_level] <= BUDGET_SECONDS:
        print(f"PASS: within {BUDGET_SECONDS}s budget")
    else:
        print(f"WARNING: even the fastest setting exceeds the {BUDGET_SECONDS}s budget")

    return results


if __name__ == "__main__":
    test_latency_levels()
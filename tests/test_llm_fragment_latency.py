"""
Checkpoint: Realistic LLM-fragment latency test.

Groq (Pillar 3) will NOT hand you full, tidy sentences. It streams text
in short bursts as tokens arrive. This test measures your TTFB against
fragments that actually resemble that pattern, instead of one long
polished sentence — which is what we tested before and is NOT
representative of production traffic.

Run with:
    python -m tests.test_llm_fragment_latency
"""

import os
import time
import pytest
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv

load_dotenv()

# Realistic short bursts — mimicking how an LLM streams partial thoughts,
# not full grammatical sentences. Lengths deliberately vary.
LLM_STYLE_FRAGMENTS = [
    "Sure,",
    "let me check that for you.",
    "Based on what you told me,",
    "I think the best option is",
    "the second one.",
    "Here's why:",
    "it's faster",
    "and more reliable.",
]


def measure_fragment_ttfb(client, voice_id: str, text: str) -> float:
    start = time.time()
    stream = client.text_to_speech.stream(
        text=text,
        voice_id=voice_id,
        model_id="eleven_turbo_v2_5",
        optimize_streaming_latency=4,
    )
    for chunk in stream:
        if isinstance(chunk, bytes):
            return time.time() - start
    return -1.0  # no audio returned at all — a real failure, not just slow


@pytest.mark.skipif(not os.getenv("ELEVEN_LABS_API_KEY"), reason="ELEVEN_LABS_API_KEY not set")
def test_llm_fragment_latency():
    api_key = os.getenv("ELEVEN_LABS_API_KEY")
    voice_id = os.getenv("ELEVEN_LABS_VOICE_ID")
    client = ElevenLabs(api_key=api_key)

    print(f"{'Fragment':<45} {'Length (chars)':<16} {'TTFB (s)':<10}")
    print("-" * 75)

    results = []
    for fragment in LLM_STYLE_FRAGMENTS:
        ttfb = measure_fragment_ttfb(client, voice_id, fragment)
        results.append((fragment, len(fragment), ttfb))
        print(f"{fragment:<45} {len(fragment):<16} {ttfb:.2f}")

    valid = [r[2] for r in results if r[2] > 0]
    avg = sum(valid) / len(valid)
    worst = max(valid)

    print(f"\nAverage TTFB across {len(valid)} fragments: {avg:.2f}s")
    print(f"Worst-case TTFB: {worst:.2f}s")

    # Short fragments should NOT be dramatically slower than long ones —
    # if they are, it likely means per-request connection overhead is
    # dominating, which matters a lot given how often the LLM will send
    # you short bursts like these in a real conversation.
    if worst > 0.6:
        print("\nNOTE: worst-case fragment latency is on the higher side — "
              "worth checking if connection reuse / keep-alive is happening "
              "correctly rather than a fresh handshake per fragment.")
    else:
        print("\nPASS: fragment latency stays low and consistent across short bursts.")

    return results


if __name__ == "__main__":
    test_llm_fragment_latency()
"""
test_mic_stt.py
---------------
Windows pe seedha mic se speech-to-text test karo.
Daily.co ki zaroorat NAHI — sirf Deepgram + mic se kaam karta hai.

Chalane ka tarika:
    python src/test_mic_stt.py

Bolo kuch bhi mic mein — terminal mein text dikhega.
Ctrl+C dabao band karne ke liye.
"""

import os
import asyncio
import sounddevice as sd
import numpy as np
from dotenv import load_dotenv
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions

load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

# Audio settings
SAMPLE_RATE = 16000   # 16kHz — Deepgram ke liye best
CHANNELS = 1          # Mono audio
CHUNK_SIZE = 1024     # Kitne samples ek baar bhejne hain


async def main():
    if not DEEPGRAM_API_KEY:
        print("❌ ERROR: DEEPGRAM_API_KEY .env file mein nahi mila!")
        return

    print("✅ Deepgram se connect ho raha hai...")

    deepgram = DeepgramClient(DEEPGRAM_API_KEY)
    connection = deepgram.listen.asynclive.v("1")

    # ---- Jab bhi transcript aaye — yeh function chalega ----
    async def on_transcript(self, result, **kwargs):
        transcript = result.channel.alternatives[0].transcript
        if transcript.strip():
            print(f"\n🎤 [SUNA]: {transcript}")

    async def on_error(self, error, **kwargs):
        print(f"❌ Deepgram Error: {error}")

    connection.on(LiveTranscriptionEvents.Transcript, on_transcript)
    connection.on(LiveTranscriptionEvents.Error, on_error)

    # ---- Deepgram options ----
    options = LiveOptions(
        model="nova-2",
        language="en-US",
        smart_format=True,
        interim_results=True,
        endpointing=300,
    )

    await connection.start(options)

    print("🎙️  Mic se sun raha hai... bolo kuch bhi! (Ctrl+C = band karo)\n")

    # ---- Mic se audio lo aur Deepgram ko bhejo ----
    loop = asyncio.get_event_loop()

    def audio_callback(indata, frames, time, status):
        if status:
            print(f"⚠️  Audio status: {status}")
        # numpy array ko bytes mein convert karo
        audio_bytes = (indata * 32767).astype(np.int16).tobytes()
        asyncio.run_coroutine_threadsafe(
            connection.send(audio_bytes), loop
        )

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocksize=CHUNK_SIZE,
            callback=audio_callback,
        ):
            # Jab tak Ctrl+C na dabaao — chalta rahe
            while True:
                await asyncio.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\n👋 Band ho raha hai...")
    finally:
        await connection.finish()
        print("✅ Done!")


if __name__ == "__main__":
    asyncio.run(main())

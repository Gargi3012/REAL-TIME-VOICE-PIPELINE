
"""
Custom Pipecat TTS service for Sarvam AI (supporting Shreya, Meera, etc.).
"""

import asyncio
import base64
import io
import wave
from typing import AsyncGenerator, Optional

import aiohttp
from loguru import logger

from pipecat.frames.frames import Frame, TTSAudioRawFrame, TTSStartedFrame, TTSStoppedFrame, ErrorFrame
from pipecat.services.tts_service import TTSService


class SarvamTTSService(TTSService):
    """Real-time TTS service using Sarvam AI Bulbul models."""

    def __init__(
        self,
        *,
        api_key: str,
        voice: str = "shreya",
        model: str = "bulbul:v3",
        target_language_code: str = "hi-IN",
        sample_rate: Optional[int] = 16000,
        **kwargs
    ):
        super().__init__(sample_rate=sample_rate, **kwargs)
        self.api_key = api_key
        self.voice = voice.lower()
        self.model = model
        self.target_language_code = target_language_code
        self.url = "https://api.sarvam.ai/text-to-speech"

    def can_generate_metrics(self) -> bool:
        return True

    async def run_tts(self, text: str, *args, **kwargs) -> AsyncGenerator[Frame, None]:
        if not text or not text.strip():
            return

        if not self.api_key:
            logger.error("SarvamTTSService error: SARVAM_API_KEY is missing.")
            yield ErrorFrame(error="Sarvam API key is missing")
            return

        try:
            yield TTSStartedFrame()
            logger.info(f"SarvamTTSService: generating audio | voice='{self.voice}' | model='{self.model}' | text='{text[:40]}...'")

            headers = {
                "api-subscription-key": self.api_key,
                "Content-Type": "application/json",
            }
            
            # Map LiveKit/Twilio sample rates
            req_sample_rate = self.sample_rate if self.sample_rate in (8000, 16000, 22050) else 16000

            payload = {
                "inputs": [text.strip()],
                "target_language_code": self.target_language_code,
                "speaker": self.voice,
                "pace": 1.0,
                "speech_sample_rate": req_sample_rate,
                "enable_preprocessing": True,
                "model": self.model,
            }
            if "v3" not in self.model.lower():
                payload["pitch"] = 0
                payload["loudness"] = 1.5

            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, headers=headers, json=payload, timeout=15) as resp:
                    if resp.status != 200:
                        err_body = await resp.text()
                        logger.error(f"Sarvam AI TTS API error {resp.status}: {err_body}")
                        yield ErrorFrame(error=f"Sarvam TTS API returned status {resp.status}")
                        return

                    data = await resp.json()
                    audios = data.get("audios", [])
                    if not audios:
                        logger.warning("Sarvam AI TTS returned empty audio list.")
                        yield TTSStoppedFrame()
                        return

                    audio_base64 = audios[0]
                    audio_bytes = base64.b64decode(audio_base64)

            # Extract raw PCM bytes from WAV container
            raw_pcm = audio_bytes
            detected_rate = req_sample_rate
            num_channels = 1

            try:
                with wave.open(io.BytesIO(audio_bytes), 'rb') as wav_file:
                    detected_rate = wav_file.getframerate()
                    num_channels = wav_file.getnchannels()
                    raw_pcm = wav_file.readframes(wav_file.getnframes())
            except Exception as wav_err:
                logger.debug(f"Parsing WAV header failed (assuming raw PCM): {wav_err}")

            # Stream audio in 4KB PCM chunks
            chunk_size = 4096
            for i in range(0, len(raw_pcm), chunk_size):
                chunk = raw_pcm[i : i + chunk_size]
                yield TTSAudioRawFrame(
                    audio=chunk,
                    sample_rate=detected_rate,
                    num_channels=num_channels,
                )

            yield TTSStoppedFrame()

        except Exception as e:
            logger.error(f"SarvamTTSService error: {e}")
            yield ErrorFrame(error=f"Sarvam TTS generation failed: {e}")

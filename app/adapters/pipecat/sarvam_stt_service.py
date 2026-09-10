"""
Custom Pipecat STT service for Sarvam AI (Saaras model).
"""

import asyncio
import io
import wave
from typing import Optional

import aiohttp
from loguru import logger

from pipecat.frames.frames import AudioRawFrame, TranscriptionFrame, ErrorFrame
from pipecat.services.stt_service import STTService


class SarvamSTTService(STTService):
    """STT service using Sarvam AI Saaras model."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "saaras:v2",
        language_code: str = "hi-IN",
        sample_rate: Optional[int] = 16000,
        **kwargs
    ):
        super().__init__(sample_rate=sample_rate, **kwargs)
        self.api_key = api_key
        self.model = model
        self.language_code = language_code
        self.url = "https://api.sarvam.ai/speech-to-text"
        self._audio_buffer = bytearray()

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, AudioRawFrame):
            self._audio_buffer.extend(frame.audio)
            # Send when buffer gathers ~1 second of audio data
            if len(self._audio_buffer) >= (self.sample_rate * 2):
                audio_to_send = bytes(self._audio_buffer)
                self._audio_buffer.clear()
                asyncio.create_task(self._transcribe(audio_to_send))

    async def _transcribe(self, pcm_bytes: bytes):
        if not self.api_key:
            return

        try:
            # Wrap raw PCM into WAV format in-memory
            wav_io = io.BytesIO()
            with wave.open(wav_io, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2) # 16-bit
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(pcm_bytes)
            wav_io.seek(0)

            headers = {
                "api-subscription-key": self.api_key,
            }

            form = aiohttp.FormData()
            form.add_field('file', wav_io, filename='audio.wav', content_type='audio/wav')
            form.add_field('model', self.model)
            form.add_field('language_code', self.language_code)

            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, headers=headers, data=form, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        transcript = data.get("transcript", "").strip()
                        if transcript:
                            logger.info(f"SarvamSTTService transcript: '{transcript}'")
                            await self.push_frame(
                                TranscriptionFrame(
                                    text=transcript,
                                    user_id="",
                                    timestamp="",
                                )
                            )
                    else:
                        err_text = await resp.text()
                        logger.warning(f"Sarvam STT returned status {resp.status}: {err_text}")

        except Exception as e:
            logger.error(f"SarvamSTTService transcription error: {e}")

import asyncio
import wave
import os
from loguru import logger
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.frames.frames import (
    Frame, TranscriptionFrame, LLMFullResponseStartFrame,
    OutputAudioRawFrame, TTSStartedFrame, TTSStoppedFrame, TextFrame
)

class LatencyFillerProcessor(FrameProcessor):
    """
    Monitors transcription frames and plays a short filler audio 
    if the LLM response is delayed by more than a given threshold.
    """
    def __init__(self, filler_wav_paths: list[str] = None, delay_threshold_ms: int = 400, **kwargs):
        super().__init__(**kwargs)
        if filler_wav_paths is None:
            filler_wav_paths = ["hmm.wav", "wait_a_minute.wav", "let_me_think.wav"]
            
        self.delay_threshold = delay_threshold_ms / 1000.0
        self._wait_task = None
        self._audio_frames_list = []
        
        # Preload all audio files
        import random
        import soundfile as sf
        self.random = random
        
        for path in filler_wav_paths:
            try:
                if os.path.exists(path):
                    frames = []
                    data, sample_rate = sf.read(path, dtype="int16")
                    num_channels = 1 if data.ndim == 1 else data.shape[1]
                    
                    # Convert to bytes
                    bytes_data = data.tobytes()
                    
                    # Chunk it into 50ms chunks (sample_rate * 0.05 * 2 bytes per sample * num_channels)
                    bytes_per_sample = 2
                    chunk_bytes = int(sample_rate * 0.05) * bytes_per_sample * num_channels
                    
                    for i in range(0, len(bytes_data), chunk_bytes):
                        chunk = bytes_data[i:i+chunk_bytes]
                        frames.append(OutputAudioRawFrame(
                            audio=chunk,
                            sample_rate=sample_rate,
                            num_channels=num_channels
                        ))
                    self._audio_frames_list.append(frames)
                    logger.info(f"Loaded {len(frames)} chunks from {path} for filler processor.")
                else:
                    logger.warning(f"Filler audio {path} not found.")
            except Exception as e:
                logger.error(f"Failed to load filler audio {path}: {e}")

    async def _play_filler_if_delayed(self):
        """Task that waits for the threshold and pushes the audio."""
        if not self._audio_frames_list:
            return
            
        try:
            await asyncio.sleep(self.delay_threshold)
            logger.info(f"LLM response delayed > {self.delay_threshold}s. Playing filler audio...")
            
            # Use self.push_frame directly. Note: Pipecat processor queues handles concurrent push_frame safely.
            audio_frames = self.random.choice(self._audio_frames_list)
            
            await self.push_frame(TTSStartedFrame(), FrameDirection.DOWNSTREAM)
            for frame in audio_frames:
                await self.push_frame(frame, FrameDirection.DOWNSTREAM)
                await asyncio.sleep(0.01) # Yield to event loop, simulate streaming
            await self.push_frame(TTSStoppedFrame(), FrameDirection.DOWNSTREAM)
            
        except asyncio.CancelledError:
            # Task was cancelled because LLM responded fast enough!
            logger.debug("Filler wait task cancelled, LLM responded fast.")

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        
        from pipecat.frames.frames import LLMMessagesAppendFrame
        
        # Intercept going DOWNSTREAM from user_agg to LLM
        if isinstance(frame, LLMMessagesAppendFrame):
            # Only trigger filler if it's a user message, not system message
            # LLMMessagesAppendFrame has 'messages' list
            is_user_msg = any(m.get("role") == "user" for m in frame.messages)
            if is_user_msg:
                if self._wait_task and not self._wait_task.done():
                    self._wait_task.cancel()
                self._wait_task = asyncio.create_task(self._play_filler_if_delayed())
                
        # Intercept when LLM starts generating or when TTS starts
        elif isinstance(frame, (LLMFullResponseStartFrame, TextFrame, TTSStartedFrame)):
            if self._wait_task and not self._wait_task.done():
                self._wait_task.cancel()
            self._wait_task = None
            
        await self.push_frame(frame, direction)

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
    def __init__(self, filler_wav_paths: list[str] = None, delay_threshold_ms: int = 400, event_bus = None, session_id = None, shared_state = None, **kwargs):
        super().__init__(**kwargs)
        if filler_wav_paths is None:
            filler_wav_paths = ["hmm.wav", "wait_a_minute.wav", "let_me_think.wav"]
            
        self.delay_threshold = delay_threshold_ms / 1000.0
        self._wait_task = None
        self._audio_frames_list = []
        self.event_bus = event_bus
        self.session_id = session_id
        self.shared_state = shared_state if shared_state is not None else {}
        
        if self.event_bus and self.session_id:
            asyncio.create_task(self._subscribe_to_events())
            
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
            if self.shared_state.get("hangup_requested"):
                logger.debug("Hangup requested, skipping filler playback.")
                return
            logger.info(f"LLM response delayed > {self.delay_threshold}s. Playing filler audio...")
            
            # Use self.push_frame directly. Note: Pipecat processor queues handles concurrent push_frame safely.
            audio_frames = self.random.choice(self._audio_frames_list)
            
            await self.push_frame(TTSStartedFrame(), FrameDirection.DOWNSTREAM)
            for frame in audio_frames:
                await self.push_frame(frame, FrameDirection.DOWNSTREAM)
                await asyncio.sleep(0.01) # Yield to event loop, simulate streaming
            
            # Tag this stop frame as filler so CallTerminationProcessor knows to ignore it
            stop_frame = TTSStoppedFrame()
            stop_frame.is_filler = True
            await self.push_frame(stop_frame, FrameDirection.DOWNSTREAM)
            
        except asyncio.CancelledError:
            # Task was cancelled because LLM responded fast enough!
            logger.debug("Filler wait task cancelled, LLM responded fast.")

    async def _subscribe_to_events(self):
        async def cancel_wait(event):
            if event.session_id == self.session_id:
                if self._wait_task and not self._wait_task.done():
                    self._wait_task.cancel()
                    logger.debug("Filler wait task cancelled by EventBus event.")
                self._wait_task = None
                
        await self.event_bus.subscribe("ThinkingStarted", cancel_wait)
        await self.event_bus.subscribe("ResponseGenerated", cancel_wait)
        await self.event_bus.subscribe("SpeakingStarted", cancel_wait)

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        
        from pipecat.frames.frames import LLMContextFrame
        
        # Intercept going DOWNSTREAM from user_agg to LLM
        if isinstance(frame, LLMContextFrame):
            # Only trigger filler if it's a user message, not system message
            messages = frame.context.messages if hasattr(frame.context, "messages") else frame.context.get_messages()
            is_user_msg = any(m.get("role") == "user" for m in messages)
            if is_user_msg:
                if self.shared_state.get("hangup_requested"):
                    logger.debug("Hangup requested, not starting filler wait task.")
                    return
                if self._wait_task and not self._wait_task.done():
                    self._wait_task.cancel()
                self._wait_task = asyncio.create_task(self._play_filler_if_delayed())
                
        # Intercept when LLM starts generating or when TTS starts
        elif isinstance(frame, (LLMFullResponseStartFrame, TextFrame, TTSStartedFrame)):
            if self._wait_task and not self._wait_task.done():
                self._wait_task.cancel()
            self._wait_task = None
            
        await self.push_frame(frame, direction)

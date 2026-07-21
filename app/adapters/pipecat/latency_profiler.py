import time
from loguru import logger
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.frames.frames import (
    Frame,
    TranscriptionFrame,
    TextFrame,
    AudioRawFrame,
    LLMFullResponseStartFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    LLMFullResponseEndFrame,
)


class LatencyProfiler(FrameProcessor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.transcription_count = 0
        self.text_frame_count = 0
        self.audio_chunk_count = 0

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        now = time.perf_counter()
        
            if isinstance(frame, TranscriptionFrame):
                logger.info(f"[PROFILER] First Partial Transcript: {now}")
                
            elif isinstance(frame, LLMFullResponseStartFrame):
                logger.info(f"[PROFILER] LLM First Token: {now}")
                    
            elif isinstance(frame, LLMFullResponseEndFrame):
                logger.info(f"[PROFILER] LLM Complete: {now}")
                    
            elif isinstance(frame, TTSStartedFrame):
                logger.info(f"[PROFILER] TTS First Byte: {now}")
                
            elif isinstance(frame, TTSStoppedFrame):
                logger.info(f"[PROFILER] TTS Complete: {now}")
                
            elif isinstance(frame, AudioRawFrame):
                logger.info(f"[PROFILER] First Audio Playback: {now}")

        await self.push_frame(frame, direction)

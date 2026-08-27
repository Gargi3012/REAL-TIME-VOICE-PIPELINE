import re
from loguru import logger
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.frames.frames import Frame, TranscriptionFrame, LLMMessagesAppendFrame

class LanguageRoutingProcessor(FrameProcessor):
    """
    Analyzes the user's transcribed text to detect language dynamically.
    Instead of changing the entire system prompt, it appends a strict language 
    instruction to the end of the user's message before the LLM processes it.
    """
    def __init__(self, shared_state=None, **kwargs):
        super().__init__(**kwargs)
        self.shared_state = shared_state if shared_state is not None else {}
        self.HINDI_INDICATORS = {
            'hai', 'mujhe', 'kya', 'kaise', 'chahiye', 'mera', 'namaste', 'nahi', 
            'haan', 'ko', 'se', 'mein', 'liye', 'karna', 'kar', 
            'rha', 'rhi', 'hu', 'tha', 'thi', 'sakte', 'bata', 'batao', 'koi'
        }

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        from pipecat.frames.frames import TranscriptionFrame
        
        # We only care about TranscriptionFrame containing user's speech text
        if isinstance(frame, TranscriptionFrame) and frame.text and not frame.user_id == "bot":
            text = frame.text.lower()
            
            # --- Fix Deepgram Time Formatting Bug ---
            # Deepgram smart_format sometimes converts spoken numbers like '708' into times like '07:08'.
            frame.text = re.sub(r'\b0?(\d{1,2}):(\d{2})\b', r'\1\2', frame.text)
            text = frame.text.lower()
            
            # --- Language Detection ---
            # Check for explicit Devanagari script
            devanagari_count = len(re.findall(r'[\u0900-\u097F]', text))
            has_devanagari = devanagari_count > 10
            
            # Check for romanized Hindi words (Hinglish)
            words = set(re.findall(r'\b\w+\b', text))
            hindi_word_count = len(words.intersection(self.HINDI_INDICATORS))
            
            # Force language based on indicators (logged for diagnostic purposes)
            if has_devanagari:
                logger.info(f"Language Detection: Devanagari detected in '{frame.text}'")
            elif hindi_word_count >= 1:
                logger.info(f"Language Detection: Hinglish detected in '{frame.text}'")
            else:
                logger.info(f"Language Detection: English detected in '{frame.text}'")
            
        await self.push_frame(frame, direction)


class CallTerminationProcessor(FrameProcessor):
    """
    Monitors the user's speech. If the user says a closing phrase (e.g. bye, thank you),
    it flags the call for termination.
    When the LLM finishes its response (saying goodbye back), it gracefully pushes an EndFrame.
    """
    def __init__(self, shared_state=None, **kwargs):
        super().__init__(**kwargs)
        self.shared_state = shared_state if shared_state is not None else {}
        self.llm_response_completed = False

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        from pipecat.frames.frames import (
            TTSStoppedFrame, EndTaskFrame, TextFrame, AudioRawFrame,
            TranscriptionFrame, LLMFullResponseEndFrame, CancelFrame
        )
        
        # Reset completed flag when a new user turn starts (user starts speaking/transcribing)
        if isinstance(frame, TranscriptionFrame) and not getattr(frame, 'user_id', None) == "bot":
            self.llm_response_completed = False
            
        # Set completed flag when LLM finishes generating response text
        if isinstance(frame, LLMFullResponseEndFrame):
            self.llm_response_completed = True
        
        # Log frame types (skip spammy ones)
        if not isinstance(frame, (AudioRawFrame, TextFrame)):
            logger.debug(f"CallTerminationProcessor received: {type(frame).__name__} | hangup_requested={self.shared_state.get('hangup_requested', False)} | llm_completed={self.llm_response_completed}")
            
        await self.push_frame(frame, direction)
        
        # When bot finishes its response, if hangup requested and LLM is done, queue EndTaskFrame or CancelFrame
        if isinstance(frame, TTSStoppedFrame):
            if getattr(frame, "is_filler", False):
                logger.info("CallTerminationProcessor: Ignoring filler TTSStoppedFrame.")
                return
            logger.info(f"CallTerminationProcessor saw TTSStoppedFrame. state: {self.shared_state} | llm_completed={self.llm_response_completed}")
            if self.shared_state.get("hangup_requested") and self.llm_response_completed:
                logger.warning("CallTerminationProcessor: Bot finished responding to goodbye. Terminating the call via master Task.")
                task = self.shared_state.get("task")
                if task:
                    await task.queue_frames([CancelFrame()])
                else:
                    await self.push_frame(EndTaskFrame(), direction)
                self.shared_state["hangup_requested"] = False
                self.llm_response_completed = False

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
            
            # --- Check for Goodbye phrases ---
            clean_text = re.sub(r'[^\w\s]', '', text.strip())
            closing_phrases = ["bye", "goodbye", "good bye", "alvida", "thank you", "thanks", "that is all", "thats all", "bas itna hi", "theek hai", "end call", "disconnect"]
            
            if len(clean_text.split()) <= 8 and any(phrase in clean_text for phrase in closing_phrases):
                logger.info(f"LanguageRoutingProcessor: User said goodbye ('{frame.text}'). Will terminate after bot replies.")
                self.shared_state["hangup_requested"] = True
            
            # --- Language Detection ---
            # Check for explicit Devanagari script
            devanagari_count = len(re.findall(r'[\u0900-\u097F]', text))
            has_devanagari = devanagari_count > 10
            
            # Check for romanized Hindi words (Hinglish)
            words = set(re.findall(r'\b\w+\b', text))
            hindi_word_count = len(words.intersection(self.HINDI_INDICATORS))
            
            # Force language based on indicators
            if has_devanagari:
                logger.info(f"Language Detection: Pure Hindi detected in '{frame.text}'")
                frame.text = f"{frame.text}\n[You MUST reply completely in natural Hindi (Devanagari script)]"
            elif hindi_word_count >= 1:
                logger.info(f"Language Detection: Hinglish detected in '{frame.text}'")
                frame.text = f"{frame.text}\n[You MUST reply in conversational Hinglish (Roman script)]"
            else:
                logger.info(f"Language Detection: English detected in '{frame.text}'")
                frame.text = f"{frame.text}\n[You MUST reply completely in English]"
            
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

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        from pipecat.frames.frames import TTSStoppedFrame, EndFrame, TextFrame, AudioRawFrame
        
        # Log frame types (skip spammy ones)
        if not isinstance(frame, (AudioRawFrame, TextFrame)):
            logger.debug(f"CallTerminationProcessor received: {type(frame).__name__} | hangup_requested={self.shared_state.get('hangup_requested', False)}")
            
        await self.push_frame(frame, direction)
        
        # When bot finishes its response, if hangup requested, queue EndFrame
        if isinstance(frame, TTSStoppedFrame):
            logger.info(f"CallTerminationProcessor saw TTSStoppedFrame. state: {self.shared_state}")
            if self.shared_state.get("hangup_requested"):
                logger.warning("CallTerminationProcessor: Bot finished responding to goodbye. Pushing EndFrame to terminate the call.")
                await self.push_frame(EndFrame(), direction)
                self.shared_state["hangup_requested"] = False

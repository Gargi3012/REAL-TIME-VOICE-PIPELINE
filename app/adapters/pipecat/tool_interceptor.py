import re
import json
import asyncio
from loguru import logger

from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.frames.frames import Frame, TextFrame, LLMFullResponseEndFrame

class ToolInterceptionProcessor(FrameProcessor):
    """
    Intercepts streaming TextFrames from the LLM, detects text-based function calls
    like (function=save_lead>...) and (function=end_call>), runs/flags the tools, 
    and filters out the tool call text so the user never hears it spoken.
    """
    def __init__(self, shared_state=None, **kwargs):
        super().__init__(**kwargs)
        self._buffer = ""
        self.shared_state = shared_state if shared_state is not None else {}

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TextFrame):
            text = frame.text
            self._buffer += text
            
            # If we see potential function tags/blocks, we buffer and wait to parse
            if "function=" in self._buffer or "save_lead" in self._buffer or "end_call" in self._buffer or (len(self._buffer) < 20 and any(self._buffer.startswith(x) for x in ["(", "<", "function", "func"])):
                # 1. Match save_lead tool call block
                pattern_save = r'(?:\(|<)?\s*function=save_lead\s*>?\s*({.*?})(?:\s*<\/function>|\s*\)|>)?'
                match_save = re.search(pattern_save, self._buffer, re.DOTALL)
                if match_save:
                    try:
                        args_str = match_save.group(1)
                        args = json.loads(args_str)
                        name = args.get("name", "")
                        phone = args.get("phone", "")
                        project_details = args.get("project_details", "")
                        if name or phone:
                            logger.info(f"ToolInterceptionProcessor: Intercepted text tool call! name='{name}', phone='{phone}', project='{project_details}'")
                            from app.services.lead_manager import save_lead
                            asyncio.create_task(save_lead(None, name, phone, project_details))
                    except Exception as e:
                        logger.error(f"ToolInterceptionProcessor: Failed to parse save_lead args: {e}")
                    
                    matched_str = match_save.group(0)
                    self._buffer = self._buffer.replace(matched_str, "")

                # 2. Match end_call tool call block
                pattern_end = r'(?:\(|<)?\s*function=end_call\s*>?\s*({.*?})?(?:\s*<\/function>|\s*\)|>)?'
                match_end = re.search(pattern_end, self._buffer, re.DOTALL)
                if match_end:
                    logger.info("ToolInterceptionProcessor: Intercepted text tool call for end_call! Setting hangup_requested=True.")
                    self.shared_state["hangup_requested"] = True
                    matched_str = match_end.group(0)
                    self._buffer = self._buffer.replace(matched_str, "")
                
                # Push whatever non-tool text remains in the buffer downstream if we aren't accumulating
                # a tag.
                if not any(x in self._buffer for x in ["function=", "save_lead", "end_call"]):
                    if self._buffer.strip():
                        await self.push_frame(TextFrame(text=self._buffer), direction)
                    self._buffer = ""
            else:
                # Normal text, push immediately
                if self._buffer:
                    await self.push_frame(TextFrame(text=self._buffer), direction)
                    self._buffer = ""
                    
        elif isinstance(frame, LLMFullResponseEndFrame):
            # Clean any remaining partial tool tags at the end of the response
            if self._buffer:
                clean_text = re.sub(r'(?:\(|<)?\s*function=save_lead.*$', '', self._buffer, flags=re.DOTALL).strip()
                clean_text = re.sub(r'(?:\(|<)?\s*function=end_call.*$', '', clean_text, flags=re.DOTALL).strip()
                # Remove loose closing tags if any
                clean_text = clean_text.replace("</function>", "").replace("</function", "").strip()
                if clean_text:
                    await self.push_frame(TextFrame(text=clean_text), direction)
            self._buffer = ""
            await self.push_frame(frame, direction)
            
        else:
            await self.push_frame(frame, direction)

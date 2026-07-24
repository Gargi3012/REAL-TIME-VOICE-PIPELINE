import re
import json
import asyncio
from loguru import logger

from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.frames.frames import Frame, TextFrame, LLMFullResponseEndFrame

class ToolInterceptionProcessor(FrameProcessor):
    """
    Intercepts streaming TextFrames from the LLM, detects text-based function calls
    like (function=save_lead>...), runs the tool in the background, and filters out
    the tool call text so the user never hears it spoken.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._buffer = ""

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TextFrame):
            text = frame.text
            self._buffer += text
            
            # If we see potential function tags/blocks, we buffer and wait to parse
            if "function=" in self._buffer or "save_lead" in self._buffer or (len(self._buffer) < 20 and any(self._buffer.startswith(x) for x in ["(", "<", "function", "func"])):
                # Match complete tool call block
                # Accommodates (function=save_lead>{"name": "...", "phone": "..."}) and <function=save_lead>...</function>
                pattern = r'(?:\(|<)?\s*function=save_lead\s*>?\s*({.*?})(?:\s*<\/function>|\s*\)|>)?'
                match = re.search(pattern, self._buffer, re.DOTALL)
                if match:
                    try:
                        args_str = match.group(1)
                        args = json.loads(args_str)
                        name = args.get("name", "")
                        phone = args.get("phone", "")
                        project_details = args.get("project_details", "")
                        if name or phone:
                            logger.info(f"ToolInterceptionProcessor: Intercepted text tool call! name='{name}', phone='{phone}', project='{project_details}'")
                            from app.services.lead_manager import save_lead
                            # Run save_lead asynchronously in the background so it doesn't block the audio stream
                            asyncio.create_task(save_lead(None, name, phone, project_details))
                    except Exception as e:
                        logger.error(f"ToolInterceptionProcessor: Failed to parse intercepted args: {e}")
                    
                    # Remove the matched function call block from the buffer
                    matched_str = match.group(0)
                    self._buffer = self._buffer.replace(matched_str, "")
                    
                    # Push whatever remains in the buffer downstream immediately
                    if self._buffer.strip():
                        await self.push_frame(TextFrame(text=self._buffer), direction)
                        self._buffer = ""
                else:
                    # Still accumulating the tool call pattern, don't push yet
                    pass
            else:
                # Normal text, push immediately
                if self._buffer:
                    await self.push_frame(TextFrame(text=self._buffer), direction)
                    self._buffer = ""
                    
        elif isinstance(frame, LLMFullResponseEndFrame):
            # Clean any remaining partial tool tags at the end of the response
            if self._buffer:
                clean_text = re.sub(r'(?:\(|<)?\s*function=save_lead.*$', '', self._buffer, flags=re.DOTALL).strip()
                # Remove loose closing tags if any
                clean_text = clean_text.replace("</function>", "").replace("</function", "").strip()
                if clean_text:
                    await self.push_frame(TextFrame(text=clean_text), direction)
            self._buffer = ""
            await self.push_frame(frame, direction)
            
        else:
            await self.push_frame(frame, direction)

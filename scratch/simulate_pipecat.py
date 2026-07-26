import asyncio
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai.base_llm import BaseOpenAILLMService
from pipecat.frames.frames import LLMContextFrame, LLMRunFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.processors.aggregators.llm_response_universal import LLMContext
from loguru import logger
from app.config import OPENAI_API_KEY

async def test():
    logger.info("Initializing LLM")
    llm = OpenAILLMService(
        api_key=OPENAI_API_KEY,
        settings=BaseOpenAILLMService.Settings(
            model='gpt-5.6-luna',
            extra={"reasoning_effort": "none"}
        ),
    )
    
    class Sink:
        async def process_frame(self, frame, direction):
            print(f"SINK RECEIVED: {type(frame).__name__}")
            if hasattr(frame, "text"):
                print(f"TEXT: {frame.text}")
    
    sink = Sink()
    llm.link(sink)
    
    logger.info("Creating context")
    context = LLMContext(
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Why are you not speaking?"}
        ]
    )
    
    logger.info("Pushing LLMContextFrame")
    await llm.process_frame(LLMContextFrame(context=context), FrameDirection.DOWNSTREAM)
    
    # give it time to stream the response
    await asyncio.sleep(5)
    print("Done")

if __name__ == "__main__":
    asyncio.run(test())

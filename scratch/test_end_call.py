import asyncio
import os
from loguru import logger
from app.llm.prompts import VOICE_SYSTEM_PROMPT
from pipecat.services.groq.llm import GroqLLMService
from pipecat.processors.aggregators.llm_response_universal import LLMContext
from pipecat.frames.frames import LLMContextFrame, LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner

class MockInputProcessor:
    pass

class MockOutputProcessor:
    pass

async def test_end_call():
    llm = GroqLLMService(
        api_key=os.getenv("GROQ_API_KEY"),
        settings=GroqLLMService.Settings(model="llama-3.3-70b-versatile"),
    )
    
    prompt = VOICE_SYSTEM_PROMPT
    async def end_call(params):
        """End the conversation when the user naturally says goodbye or indicates they are done. ALWAYS say a natural farewell to the user FIRST before calling this function."""
        logger.info(f"LLM called end_call!")
        if params.result_callback:
            await params.result_callback({"status": "ending"})
        import sys
        sys.exit(0)
        
    context = LLMContext(
        messages=[{"role": "system", "content": prompt}],
        tools=[end_call]
    )
    
    context.add_message({"role": "user", "content": "Thank you Sarah, that's all."})
    from pipecat.services.openai.base_llm import OpenAILLMInvocationParams
    
    # Actually, easiest is just to use run_inference if it supports tools, but let's just use get_chat_completions
    logger.info("Generating...")
    stream = await llm.get_chat_completions(context)
    async for chunk in stream:
        print(chunk)
        if chunk.choices and chunk.choices[0].delta:
            delta = chunk.choices[0].delta
            if delta.content:
                print(f"Content: {delta.content}", end="")
            if delta.tool_calls:
                print(f"\nTool Call: {delta.tool_calls}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(test_end_call())

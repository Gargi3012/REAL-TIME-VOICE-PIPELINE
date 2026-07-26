import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_cartesia():
    from pipecat.services.cartesia.tts import CartesiaTTSService
    from pipecat.frames.frames import TextFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.task import PipelineTask
    
    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        voice_id=os.getenv("CARTESIA_VOICE_ID", "a0e99841-438c-4a64-b679-ae501e7d6091"),
        sample_rate=8000,
    )
    print("Cartesia initialized.")

if __name__ == "__main__":
    asyncio.run(test_cartesia())

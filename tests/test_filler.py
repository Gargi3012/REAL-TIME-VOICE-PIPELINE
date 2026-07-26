import asyncio
from app.adapters.pipecat.filler_processor import LatencyFillerProcessor

async def test():
    processor = LatencyFillerProcessor(filler_wav_paths=["hmm.wav"], delay_threshold_ms=400)
    print(len(processor._audio_frames_list))
    
if __name__ == "__main__":
    asyncio.run(test())

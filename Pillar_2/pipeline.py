from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.services.deepgram.stt import DeepgramSTTService

def create_deepgram_stt(api_key: str, model: str = "nova-2-phonecall", language: str = "multi") -> DeepgramSTTService:
    """Exposed factory for the main app to build the Deepgram service via Pillar 2."""
    return DeepgramSTTService(
        api_key=api_key,
        sample_rate=16000,
        settings=DeepgramSTTService.Settings(
            model=model,
            language=language,
            smart_format=True,
            interim_results=True,
            endpointing=300,
        ),
    )

def build_vad_analyzer() -> SileroVADAnalyzer:
    """Exposed factory for the main app to build the VAD analyzer via Pillar 2."""
    return SileroVADAnalyzer(
        params=VADParams(
            confidence=0.7,
            start_secs=0.1,     # Faster start detection
            stop_secs=0.2,      # Reduced from 0.4
            min_volume=0.01,
        )
    )
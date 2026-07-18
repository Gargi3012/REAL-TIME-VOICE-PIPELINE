from typing import Any

import os
import importlib.util

from loguru import logger

from app.pipeline.processors import ProcessorRole

def _import_pillar2_module(module_name: str, file_name: str):
    """Helper to load Pillar 2 modules without sys.path conflicts."""
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Pillar_2", file_name))
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PipecatProcessorAdapter:
    """Wraps a Pipecat processor to track its execution."""

    def __init__(self, name: str, pipecat_processor: Any) -> None:
        self.name = name
        self.pipecat_processor = pipecat_processor

    def get_processor(self) -> Any:
        return self.pipecat_processor


# ── Fallback mock (used in tests / when pipecat-ai is not installed) ──

class MockPipecatProcessor:
    """Lightweight stand-in used exclusively in unit tests."""

    def __init__(self, name: str) -> None:
        self.name = name


# ── Real service factory ──────────────────────────────────────────────

def create_pipecat_processor(role: ProcessorRole, metadata: dict[str, Any]) -> Any:
    """Instantiate the appropriate Pipecat service for a given ProcessorRole.

    When pipecat-ai is installed (production), real service objects are
    returned.  If the import fails (CI / unit-test environments without
    the native media stack), MockPipecatProcessor is returned instead so
    existing tests continue to pass without modification.

    Args:
        role:     The canonical role this processor fills in the pipeline.
        metadata: Configuration dict forwarded from the ProcessorNode.

    Returns:
        A Pipecat-compatible processor object.
    """
    try:
        return _create_real_processor(role, metadata)
    except ImportError as e:
        logger.error(f"MOCK FALLBACK for role={role.value} | REASON: {e}")
        import traceback
        traceback.print_exc()
        return _create_mock_processor(role)


def _create_real_processor(role: ProcessorRole, metadata: dict[str, Any]) -> Any:
    """Build a real Pipecat service. Raises ImportError if pipecat-ai is absent."""
    from app.config import (
        DEEPGRAM_API_KEY,
        GROQ_API_KEY,
        GROQ_MODEL,
        ELEVEN_LABS_API_KEY,
        ELEVEN_LABS_VOICE_ID,
    )

    if role == ProcessorRole.STT:
        if not DEEPGRAM_API_KEY:
            raise ValueError("DEEPGRAM_API_KEY is not set in your .env file.")

        from app.config import TRANSPORT_MODE
        sample_rate = 16000 if TRANSPORT_MODE.lower() == "livekit" else 8000

        # Call Pillar_2 STT factory
        pillar2_pipeline = _import_pillar2_module("pillar2_pipeline", "pipeline.py")
        stt = pillar2_pipeline.create_deepgram_stt(
            api_key=DEEPGRAM_API_KEY,
            model=metadata.get("model", "nova-2"),
            language=metadata.get("language", "hi"),
            sample_rate=sample_rate
        )
        logger.info("DeepgramSTTService created (via Pillar 2) | model={m}", m=metadata.get("model", "nova-2"))
        return stt

    elif role == ProcessorRole.LLM:
        from pipecat.services.groq.llm import GroqLLMService

        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set in your .env file.")

        model = metadata.get("model", GROQ_MODEL)
        llm = GroqLLMService(
            api_key=GROQ_API_KEY,
            settings=GroqLLMService.Settings(model=model),
        )
        logger.info("GroqLLMService created | model={m}", m=model)
        return llm

    elif role == ProcessorRole.TTS:
        from app.config import TTS_PROVIDER, TRANSPORT_MODE
        
        provider = metadata.get("provider", TTS_PROVIDER)
        sample_rate = 16000 if TRANSPORT_MODE.lower() == "livekit" else 8000
        
        if provider == "elevenlabs":
            from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
            from app.config import ELEVEN_LABS_API_KEY, ELEVEN_LABS_VOICE_ID, ELEVENLABS_MODEL

            if not ELEVEN_LABS_API_KEY:
                raise ValueError("ELEVEN_LABS_API_KEY is not set in your .env file.")

            voice_id = metadata.get("voice_id", ELEVEN_LABS_VOICE_ID)
            model_name = metadata.get("model", ELEVENLABS_MODEL)
            tts = ElevenLabsTTSService(
                api_key=ELEVEN_LABS_API_KEY,
                sample_rate=sample_rate,
                settings=ElevenLabsTTSService.Settings(
                    voice=voice_id,
                    model=model_name,
                    stability=0.5,
                    similarity_boost=0.8,
                ),
            )
            logger.info("ElevenLabsTTSService created | voice_id={v}", v=voice_id)
            return tts

        elif provider == "deepgram":
            from pipecat.services.deepgram.tts import DeepgramTTSService
            from app.config import DEEPGRAM_API_KEY, DEEPGRAM_TTS_VOICE

            if not DEEPGRAM_API_KEY:
                raise ValueError("DEEPGRAM_API_KEY is not set in your .env file.")

            voice = metadata.get("voice", DEEPGRAM_TTS_VOICE)
            tts = DeepgramTTSService(
                api_key=DEEPGRAM_API_KEY,
                sample_rate=sample_rate,
                settings=DeepgramTTSService.Settings(voice=voice),
            )
            logger.info("DeepgramTTSService created | voice={v}", v=voice)
            return tts

        elif provider == "chatterbox":
            from app.adapters.pipecat.chatterbox_tts_service import ChatterboxTTSService

            tts = ChatterboxTTSService(sample_rate=sample_rate)
            logger.info("ChatterboxTTSService created (local CPU)")
            return tts

        elif provider == "cartesia":    
            from pipecat.services.cartesia.tts import CartesiaTTSService
            from app.config import CARTESIA_API_KEY, CARTESIA_VOICE_ID

            if not CARTESIA_API_KEY:
                raise ValueError("CARTESIA_API_KEY is not set in your .env file.")

            voice_id = metadata.get("voice_id", CARTESIA_VOICE_ID)
            tts = CartesiaTTSService(
                api_key=CARTESIA_API_KEY,
                voice_id=voice_id,
                sample_rate=sample_rate,
            )
            logger.info("CartesiaTTSService created | voice_id={v}", v=voice_id)
            return tts

        else:
            raise ValueError(f"Unknown TTS_PROVIDER: {provider}")



    elif role in (ProcessorRole.TRANSPORT_INPUT, ProcessorRole.TRANSPORT_OUTPUT):
        # Transport processors are injected via PipecatTransportAdapter,
        # not through this factory. Return a no-op placeholder.
        return MockPipecatProcessor(f"Transport_{role.value}")

    else:
        return MockPipecatProcessor(f"Custom_{role.value}")


def _create_mock_processor(role: ProcessorRole) -> MockPipecatProcessor:
    """Return a named mock processor for CI/test environments."""
    role_to_name: dict[ProcessorRole, str] = {
        ProcessorRole.STT: "MockSTT",
        ProcessorRole.LLM: "MockLLM",
        ProcessorRole.TTS: "MockTTS",
        ProcessorRole.TRANSPORT_INPUT: "MockTransport_input",
        ProcessorRole.TRANSPORT_OUTPUT: "MockTransport_output",
    }
    name = role_to_name.get(role, f"MockCustom_{role.value}")
    return MockPipecatProcessor(name)


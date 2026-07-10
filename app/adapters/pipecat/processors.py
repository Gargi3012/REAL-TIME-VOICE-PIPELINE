"""
Processor mapping for Pipecat.

create_pipecat_processor() is a factory that returns the real Pipecat
service instance for each ProcessorRole when the full pipecat-ai package
is installed, or a MockPipecatProcessor when it is not (test environments).
"""

from typing import Any

from loguru import logger

from app.pipeline.processors import ProcessorRole


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
    except ImportError:
        logger.debug(
            "pipecat-ai not installed — using MockPipecatProcessor for role={role}",
            role=role.value,
        )
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
        from pipecat.services.deepgram.stt import DeepgramSTTService

        if not DEEPGRAM_API_KEY:
            raise ValueError("DEEPGRAM_API_KEY is not set in your .env file.")

        stt = DeepgramSTTService(
            api_key=DEEPGRAM_API_KEY,
            sample_rate=8000,
            settings=DeepgramSTTService.Settings(
                model=metadata.get("model", "nova-2"),
                language=metadata.get("language", "hi"),
                smart_format=metadata.get("smart_format", True),
                interim_results=metadata.get("interim_results", True),
                endpointing=metadata.get("endpointing", 300),
            ),
        )
        logger.info("DeepgramSTTService created | model={m}", m=metadata.get("model", "nova-2"))
        return stt

    elif role == ProcessorRole.LLM:
        from pipecat.services.groq.llm import GroqLLMService

        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set in your .env file.")

        model = metadata.get("model", GROQ_MODEL)
        llm = GroqLLMService(
            api_key=GROQ_API_KEY,
            settings=GroqLLMService.Settings(
                model=model,
            )
        )
        logger.info("GroqLLMService created | model={m}", m=model)
        return llm

    elif role == ProcessorRole.TTS:
        from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

        if not ELEVEN_LABS_API_KEY:
            raise ValueError("ELEVEN_LABS_API_KEY is not set in your .env file.")

        voice_id = metadata.get("voice_id", ELEVEN_LABS_VOICE_ID)
        tts = ElevenLabsTTSService(
            api_key=ELEVEN_LABS_API_KEY,
            settings=ElevenLabsTTSService.Settings(
                voice=voice_id,
            )
        )
        logger.info("ElevenLabsTTSService created | voice_id={v}", v=voice_id)
        return tts

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


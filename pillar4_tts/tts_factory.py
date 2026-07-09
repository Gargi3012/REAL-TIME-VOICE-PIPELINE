"""
Pillar 4 — Premium Audio Generation (TTS & Performance Lead)

Final standalone module. build_tts_service()'s signature and metadata
keys are written to match your team's app/adapters/pipecat/processors.py
exactly, so handoff later is a copy-paste, not a rewrite.

Confirmed against pipecat-ai 0.0.108 docs (checked directly, not assumed):
  - ElevenLabsTTSService (WebSocket variant) is the correct choice here —
    it supports word-level timestamps and interruption handling, which
    the HTTP variant does not.
  - Current recommended construction uses `settings=` with a Settings
    object, not the older direct voice_id=/model= kwargs (those still
    work but log a DeprecationWarning).
  - IMPORTANT: optimize_streaming_latency does NOT exist on this
    WebSocket service's settings — that flag only applies to
    ElevenLabsHttpTTSService. The WebSocket variant manages latency
    internally via its own audio-context streaming, which is why it's
    the right pick for an interactive, interruptible pipeline anyway.

Interruption handling is intentionally NOT implemented here: Pipecat's
ElevenLabsTTSService already handles StartInterruptionFrame internally
(stopping generation, closing the ElevenLabs context). That's framework
behavior, not something this module needs to own.
"""

from typing import Any, Optional
from loguru import logger

from .config import (
    ELEVEN_LABS_API_KEY,
    ELEVEN_LABS_VOICE_ID,
    DEFAULT_TTS_MODEL,
    DEFAULT_STABILITY,
    DEFAULT_SIMILARITY_BOOST,
    validate_config,
)


def build_tts_service(metadata: Optional[dict[str, Any]] = None) -> Any:
    """
    Build a fully-tuned ElevenLabsTTSService (WebSocket) instance.

    Args:
        metadata: optional per-session overrides, read the same way
                  your team's processors.py reads node.metadata:
                  - voice_id
                  - model
                  - stability
                  - similarity_boost

    Returns:
        A configured pipecat ElevenLabsTTSService instance, ready to be
        placed directly into a Pipecat Pipeline([...]) list.
    """
    validate_config()
    metadata = metadata or {}

    from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

    voice_id = metadata.get("voice_id", ELEVEN_LABS_VOICE_ID)
    model = metadata.get("model", DEFAULT_TTS_MODEL)
    stability = metadata.get("stability", DEFAULT_STABILITY)
    similarity_boost = metadata.get("similarity_boost", DEFAULT_SIMILARITY_BOOST)

    assert ELEVEN_LABS_API_KEY is not None
    tts = ElevenLabsTTSService(
        api_key=ELEVEN_LABS_API_KEY,
        voice_id=voice_id,
        model=model,
        settings=ElevenLabsTTSService.Settings(
            stability=stability,
            similarity_boost=similarity_boost,
        ),
    )

    logger.info(
        "ElevenLabsTTSService built | voice_id={v} | model={m} | stability={s} | similarity_boost={sb}",
        v=voice_id, m=model, s=stability, sb=similarity_boost,
    )
    return tts
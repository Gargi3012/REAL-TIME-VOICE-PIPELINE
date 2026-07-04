

import os
from dotenv import load_dotenv
from pipecat.services.deepgram import DeepgramSTTService

from logger import log_event, log_error

load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")


def get_deepgram_stt():
    """
    Returns a configured Deepgram STT service.
    model="nova-2" is Deepgram's fastest + most accurate real-time model.

    Raises a clear error early if the API key is missing.
    """
    # ---- ERROR HANDLING: fail early with a clear message ----
    if not DEEPGRAM_API_KEY:
        log_error(
            "Deepgram STT Setup",
            ValueError("DEEPGRAM_API_KEY is missing. Check your .env file."),
        )
        raise ValueError(
            "DEEPGRAM_API_KEY is not set. Add it to your .env file."
        )

    try:
        stt = DeepgramSTTService(
            api_key=DEEPGRAM_API_KEY,
            live_options={
                "model": "nova-2",
                "language": "en-US",
                "smart_format": True,     # auto punctuation/capitalization
                "interim_results": True,  # gives partial words as they're spoken
                "endpointing": 300,       # ms of silence before it decides user stopped talking
            },
        )

        log_event("DEEPGRAM_STT_INITIALIZED", extra="model=nova-2")
        return stt

    except Exception as e:
        log_error("Deepgram STT Setup", e)
        raise


def wrap_stt_with_logging(stt_service):
    """
    Optional wrapper that hooks into Deepgram's events to log
    exactly when speech starts and when the final transcript arrives.
    This is what lets us measure "audio in -> text out" latency.

    Call this after get_deepgram_stt() if you want detailed timing logs.
    """

    original_on_message = getattr(stt_service, "_on_message", None)

    async def logged_on_message(*args, **kwargs):
        try:
            log_event("DEEPGRAM_TRANSCRIPT_RECEIVED")
            if original_on_message:
                return await original_on_message(*args, **kwargs)
        except Exception as e:
            log_error("Deepgram STT (runtime)", e)
            raise

    if original_on_message:
        stt_service._on_message = logged_on_message

    return stt_service
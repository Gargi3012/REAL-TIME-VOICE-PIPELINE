"""
transport.py
--------------
PILLAR 2 - Audio Ingestion & Transport

This file configures the actual "door" the audio walks through:
DailyTransport = WebRTC connection between the user's browser mic
and our Pipecat pipeline.

Includes:
- Error handling (so a bad room URL / network issue doesn't crash silently)
- VAD tuning (controls how quickly we detect the user started/stopped talking)
- Logging (so we can see connection events + measure latency)

Pillar 1 will import `get_daily_transport()` and plug it as the
first + last step of the pipeline:

    pipeline = Pipeline([
        transport.input(),   <-- Pillar 2 (this file)
        stt,                 <-- Pillar 2 (deepgram_stt.py)
        llm,                 <-- Pillar 3
        tts,                 <-- Pillar 4
        transport.output(),  <-- Pillar 2 (this file)
    ])
"""

import os
from dotenv import load_dotenv
from pipecat.transports.services.daily import DailyTransport, DailyParams
from pipecat.vad.silero import SileroVADAnalyzer
from pipecat.vad.vad_analyzer import VADParams

from logger import log_event, log_error

load_dotenv()

DAILY_ROOM_URL = os.getenv("DAILY_ROOM_URL")
DAILY_API_KEY = os.getenv("DAILY_API_KEY")


def get_daily_transport(room_url: str = None, bot_name: str = "Cybernauts Agent"):
    """
    Returns a configured DailyTransport object.
    This is what actually receives the user's mic audio and
    sends the AI's voice back out.

    Raises a clear error early if the room URL is missing/invalid,
    instead of failing later with a confusing network error.
    """
    room_url = room_url or DAILY_ROOM_URL

    # ---- ERROR HANDLING: fail early with a clear message ----
    if not room_url:
        log_error(
            "Daily Transport Setup",
            ValueError("DAILY_ROOM_URL is missing. Check your .env file."),
        )
        raise ValueError(
            "DAILY_ROOM_URL is not set. Add it to your .env file "
            "or pass room_url directly to get_daily_transport()."
        )

    if not DAILY_API_KEY:
        log_error(
            "Daily Transport Setup",
            ValueError("DAILY_API_KEY is missing. Check your .env file."),
        )
        raise ValueError("DAILY_API_KEY is not set in your .env file.")

    try:
        transport = DailyTransport(
            room_url,
            None,  # token - pass a meeting token here if the room is private
            bot_name,
            DailyParams(
                audio_out_enabled=True,     # bot can speak
                audio_in_enabled=True,      # bot can hear the user
                camera_out_enabled=False,   # voice-only, no video needed
                vad_enabled=True,           # detects when user starts/stops speaking

                # ---- VAD TUNING ----
                # confidence: how sure it needs to be that speech started (0-1)
                # start_secs: how many seconds of speech before triggering "user started talking"
                # stop_secs: how many seconds of silence before triggering "user stopped talking"
                #   Lower stop_secs = AI responds faster, but might cut off user mid-sentence
                #   Higher stop_secs = safer, but adds latency
                vad_analyzer=SileroVADAnalyzer(
                    params=VADParams(
                        confidence=0.7,
                        start_secs=0.2,
                        stop_secs=0.5,   # tuned down from default for faster turn-taking
                        min_volume=0.6,
                    )
                ),
                transcription_enabled=False,  # we use Deepgram separately, not Daily's built-in
            ),
        )

        log_event("DAILY_TRANSPORT_INITIALIZED", extra=f"room={room_url}")
        return transport

    except Exception as e:
        log_error("Daily Transport Setup", e)
        raise


def register_transport_events(transport):
    """
    Attaches logging to key connection events, so we can see in the
    terminal exactly when a user joins/leaves and if anything fails.
    Call this once after creating the transport, from your main pipeline file.
    """

    @transport.event_handler("on_joined")
    async def on_joined(transport, data):
        log_event("USER_JOINED_ROOM", extra=str(data.get("participants", "")))

    @transport.event_handler("on_participant_left")
    async def on_participant_left(transport, participant, reason):
        log_event("USER_LEFT_ROOM", extra=f"reason={reason}")

    @transport.event_handler("on_error")
    async def on_error(transport, error):
        log_error("Daily Transport (runtime)", Exception(str(error)))

    return transport
"""
Configuration — Loads all environment variables required by the pipeline.

All API keys are read from a .env file at the project root.
Each setting is validated at import time so errors surface immediately
on startup rather than mid-call.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (works whether you run from repo root or app/)
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env", override=False)

# ── Daily.co (WebRTC transport) ────────────────────────────────────────
DAILY_API_KEY: str = os.getenv("DAILY_API_KEY", "")
DAILY_ROOM_URL: str = os.getenv("DAILY_ROOM_URL", "")

# ── LiveKit (WebRTC transport) ─────────────────────────────────────────
LIVEKIT_URL: str = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY: str = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET: str = os.getenv("LIVEKIT_API_SECRET", "")
LIVEKIT_ROOM: str = os.getenv("LIVEKIT_ROOM", "room-1")
LIVEKIT_ROOM_NAME: str = os.getenv("LIVEKIT_ROOM_NAME", "default-voice-room")

# ── Deepgram (Speech-to-Text) ──────────────────────────────────────────
DEEPGRAM_API_KEY: str = os.getenv("DEEPGRAM_API_KEY", "")

# ── Groq (LLM) ────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama3-8b-8192")

# ── ElevenLabs (Text-to-Speech) ───────────────────────────────────────
ELEVEN_LABS_API_KEY: str = os.getenv("ELEVEN_LABS_API_KEY", "")
ELEVEN_LABS_VOICE_ID: str = os.getenv("ELEVEN_LABS_VOICE_ID", "21m00TlvDq8ikWAM")

# ── Bot identity ───────────────────────────────────────────────────────
BOT_NAME: str = os.getenv("BOT_NAME", "Cybernauts Agent")

# ── Transport (Telephony/WebRTC transport) ────────────────────────────────
TRANSPORT_MODE: str = os.getenv("TRANSPORT_MODE", "livekit") # "twilio", or "livekit"
TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")

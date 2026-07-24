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

# ── LLM Provider Selection ─────────────────────────────────────────────
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")  # "openai" | "groq"

# ── Groq (LLM) ────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_WHISPER_MODEL: str = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

# ── OpenAI (LLM) ──────────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ── ElevenLabs (Text-to-Speech) ───────────────────────────────────────
ELEVEN_LABS_API_KEY: str = os.getenv("ELEVEN_LABS_API_KEY", "")
ELEVEN_LABS_VOICE_ID: str = os.getenv("ELEVEN_LABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
ELEVENLABS_MODEL: str = os.getenv("ELEVENLABS_MODEL", "eleven_turbo_v2_5")

# ── TTS Provider Selection ─────────────────────────────────────────────
TTS_PROVIDER: str = os.getenv("TTS_PROVIDER", "elevenlabs")  # "elevenlabs" | "deepgram" | "cartesia"

# ── Deepgram (also used for TTS, separate voice setting from STT) ─────
DEEPGRAM_TTS_VOICE: str = os.getenv("DEEPGRAM_TTS_VOICE", "aura-2-asteria-en")

# ── Cartesia (Text-to-Speech) ──────────────────────────────────────────
CARTESIA_API_KEY: str = os.getenv("CARTESIA_API_KEY", "")
CARTESIA_VOICE_ID: str = os.getenv("CARTESIA_VOICE_ID", "a0e99841-438c-4a64-b679-ae501e7d6091")

# ── Bot identity ───────────────────────────────────────────────────────
BOT_NAME: str = os.getenv("BOT_NAME", "Cybernauts Agent")

# ── Transport (Telephony/WebRTC transport) ────────────────────────────────
TRANSPORT_MODE: str = os.getenv("TRANSPORT_MODE", "livekit") # "twilio", or "livekit"
TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")

# ── Database (Neon PostgreSQL) ──────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/voice_db")
DATABASE_POOL_SIZE: int = int(os.getenv("DATABASE_POOL_SIZE", "5"))
DATABASE_MAX_OVERFLOW: int = int(os.getenv("DATABASE_MAX_OVERFLOW", "10"))
DATABASE_POOL_TIMEOUT: int = int(os.getenv("DATABASE_POOL_TIMEOUT", "30"))

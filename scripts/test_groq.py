#!/usr/bin/env python3
"""Standalone script to verify Groq LLM Client and Context Manager."""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv

# Load .env file if present
load_dotenv(Path(project_root) / ".env")

from loguru import logger
from app.session.manager import SessionManager
from app.llm.prompts import VOICE_SYSTEM_PROMPT
from app.llm.client import GroqLLMClient
from app.llm.context_manager import ContextManager

# Configure logger to output to stderr for tracking execution details
logger.remove()
logger.add(sys.stderr, level="INFO")


async def main() -> None:
    # 1. Check API Key
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY is not set in environment or .env file.")
        print(
            "\nError: GROQ_API_KEY environment variable is not set.",
            file=sys.stderr,
        )
        print(
            "Please create a .env file at the project root with your key, e.g.:",
            file=sys.stderr,
        )
        print("GROQ_API_KEY=gsk_...", file=sys.stderr)
        sys.exit(1)

    print("Initializing SessionManager and ContextManager...")
    session_manager = SessionManager()
    context_manager = ContextManager(session_manager)

    # 2. Create a session
    session = session_manager.create_session(metadata={"test": "true"})
    session_id = session.session_id
    print(f"Created session ID: {session_id}")

    # 3. Add system prompt
    session_manager.add_message(session_id, role="system", content=VOICE_SYSTEM_PROMPT)

    # 4. Add conversation history
    print("\nAdding conversation history...")
    turns = [
        ("user", "Hello, who are you?"),
        (
            "assistant",
            "Hello! I am your voice assistant. How can I help you today?",
        ),
        ("user", "What is the capital of France?"),
        ("assistant", "The capital of France is Paris."),
        ("user", "What is the weather like there usually?"),
        (
            "assistant",
            "Paris has a temperate climate, with mild summers and cool winters.",
        ),
        ("user", "Can you summarize the capital and its climate in one sentence?"),
    ]

    for role, content in turns:
        session_manager.add_message(session_id, role=role, content=content)  # type: ignore

    # Print the full history to verify
    full_history = session_manager.get_history(session_id)
    if full_history:
        print("\n--- Full History ---")
        for i, msg in enumerate(full_history):
            print(f"{i:2d}: [{msg.role.upper()}] {msg.content}")

    # 5. Trim to last 5 messages (retains system prompt at index 0)
    print("\nTrimming history to max_messages=5 (sliding window)...")
    trimmed_history = context_manager.get_trimmed_history(session_id, max_messages=5)

    print("\n--- Trimmed History (Expected 5 messages, starting with SYSTEM) ---")
    for i, msg in enumerate(trimmed_history):
        print(f"{i:2d}: [{msg.role.upper()}] {msg.content}")

    # Ensure trimmed_history is indeed 5 messages and first is system
    assert len(trimmed_history) == 5, f"Expected 5 messages, got {len(trimmed_history)}"
    assert (
        trimmed_history[0].role == "system"
    ), f"Expected first message to be system, got {trimmed_history[0].role}"

    # 6. Initialize GroqLLMClient
    print("\nInitializing GroqLLMClient...")
    client = GroqLLMClient(api_key=api_key)

    # 7. Stream completion response
    print("\nStreaming response from Groq:")
    print("----------------------------------------------------------------------")
    response_chunks = []
    async for chunk in client.stream_response(trimmed_history):
        sys.stdout.write(chunk)
        sys.stdout.flush()
        response_chunks.append(chunk)
    print("\n----------------------------------------------------------------------")

    full_response = "".join(response_chunks)
    print(f"Full reply received: {len(full_response)} characters.")


if __name__ == "__main__":
    asyncio.run(main())

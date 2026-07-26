# scripts/check_latency.py
import asyncio
import time
from app.llm.client import GroqLLMClient
from app.session.message import Message
import os
from dotenv import load_dotenv
load_dotenv()

async def main():
    client = GroqLLMClient()
    messages = [
        Message(role="system", content="You are a helpful voice assistant. Keep responses short."),
        Message(role="user", content="What is the capital of France?"),
    ]

    start = time.perf_counter()
    first_token_time = None
    full_response = ""

    async for chunk in client.stream_response(messages):
        if first_token_time is None:
            first_token_time = time.perf_counter()
        full_response += chunk

    end = time.perf_counter()

    print(f"Response: {full_response}")
    print(f"Time to first token: {(first_token_time - start)*1000:.1f} ms")
    print(f"Total time (full response): {(end - start)*1000:.1f} ms")

if __name__ == "__main__":
    asyncio.run(main())
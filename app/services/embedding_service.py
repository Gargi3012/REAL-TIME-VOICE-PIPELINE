"""
Embedding service — wraps OpenAI's embedding API to generate 384-dim vectors.
No heavy local model loading, saving gigabytes of disk space and memory.
"""
import os
from openai import OpenAI
from loguru import logger

_client = None


def get_openai_client() -> OpenAI:
    """Lazily initialize OpenAI client (singleton)."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        _client = OpenAI(api_key=api_key)
    return _client


def embed_text(text: str) -> list[float]:
    """Generate a 384-dim embedding vector for the given text using OpenAI API."""
    logger.debug(f"Generating embedding for text: {text[:30]}...")
    client = get_openai_client()
    response = client.embeddings.create(
        input=[text],
        model="text-embedding-3-small",
        dimensions=384
    )
    return response.data[0].embedding
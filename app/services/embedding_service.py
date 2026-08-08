"""
Embedding service — wraps a local sentence-transformers model as a singleton
so the (relatively heavy) model load happens once at process startup, not
per-request. No external API calls, no GPT dependency, no network latency.
"""
from sentence_transformers import SentenceTransformer
from loguru import logger

_model = None


def get_embedding_model() -> SentenceTransformer:
    """Lazily load and cache the embedding model (singleton)."""
    global _model
    if _model is None:
        logger.info("Loading embedding model: all-MiniLM-L6-v2 ...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model loaded.")
    return _model


def embed_text(text: str) -> list[float]:
    """Generate a 384-dim embedding vector for the given text."""
    model = get_embedding_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()
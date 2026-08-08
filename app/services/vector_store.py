"""
Vector store service — wraps Qdrant for two purposes:
1. Semantic search against known/approved FAQs (RAG lookup)
2. Storing unanswered caller questions for later human review
"""
import asyncio
import os
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from loguru import logger

from app.services.embedding_service import embed_text
from qdrant_client.models import PointIdsList

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)  # only needed for Qdrant Cloud

FAQ_COLLECTION = "faq_knowledge_base"
PENDING_COLLECTION = "pending_faqs"
VECTOR_SIZE = 384  # matches all-MiniLM-L6-v2 output dimension
MATCH_THRESHOLD = 0.75  # cosine similarity cutoff — tune this after testing

_client = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    return _client


def ensure_collections():
    """Call once at startup — creates collections if they don't exist."""
    client = get_client()
    existing = {c.name for c in client.get_collections().collections}

    for name in (FAQ_COLLECTION, PENDING_COLLECTION):
        if name not in existing:
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            logger.info(f"Created Qdrant collection: {name}")


async def search_faq(query: str) -> dict | None:
    """
    Semantic search against the approved FAQ collection.
    Returns the matched FAQ dict if similarity >= MATCH_THRESHOLD, else None.
    """
    loop = asyncio.get_event_loop()
    vector = await loop.run_in_executor(None, embed_text, query)

    client = get_client()
    response = await loop.run_in_executor(
        None,
        lambda: client.query_points(
            collection_name=FAQ_COLLECTION,
            query=vector,
            limit=1,
            score_threshold=MATCH_THRESHOLD,
            with_payload=True,
        ),
    )

    if response.points:
        hit = response.points[0]
        return {"question": hit.payload.get("question"), "answer": hit.payload.get("answer"), "score": hit.score}
    return None


async def store_pending_faq(question: str, phone_number: str = "", session_id: str = ""):
    """Store an unanswered question in the pending collection for later review."""
    loop = asyncio.get_event_loop()
    vector = await loop.run_in_executor(None, embed_text, question)

    client = get_client()
    point = PointStruct(
        id=str(uuid.uuid4()),
        vector=vector,
        payload={
            "question": question,
            "phone_number": phone_number,
            "session_id": session_id,
            "status": "pending",
        },
    )
    await loop.run_in_executor(None, lambda: client.upsert(collection_name=PENDING_COLLECTION, points=[point]))
    logger.info(f"Stored pending FAQ: {question[:60]}...")


async def add_faq(question: str, answer: str):
    """Add an approved question-answer pair to the official FAQ collection."""
    loop = asyncio.get_event_loop()
    vector = await loop.run_in_executor(None, embed_text, question)

    client = get_client()
    point = PointStruct(
        id=str(uuid.uuid4()),
        vector=vector,
        payload={"question": question, "answer": answer},
    )
    await loop.run_in_executor(None, lambda: client.upsert(collection_name=FAQ_COLLECTION, points=[point]))
    logger.info(f"Added FAQ: {question[:60]}...")

   
async def list_pending_faqs(limit: int = 50) -> list[dict]:
    """List all questions waiting for human review."""
    loop = asyncio.get_event_loop()
    client = get_client()

    response = await loop.run_in_executor(
        None,
        lambda: client.scroll(
            collection_name=PENDING_COLLECTION,
            limit=limit,
            with_payload=True,
        ),
    )
    points, _ = response
    return [{"id": p.id, **p.payload} for p in points]


async def delete_pending_faq(point_id: str):
    """Remove a question from the pending collection (after it's been reviewed)."""
    loop = asyncio.get_event_loop()
    client = get_client()
    await loop.run_in_executor(
        None,
        lambda: client.delete(
            collection_name=PENDING_COLLECTION,
            points_selector=PointIdsList(points=[point_id]),
        ),
    )
    logger.info(f"Deleted pending FAQ: {point_id}")
"""
company_faq.py

Loads company FAQ knowledge base from the database and formats it as a
text block that can be appended to VOICE_SYSTEM_PROMPT, so the LLM can
answer company-related customer questions accurately instead of guessing.

FAQ data is cached in memory after being loaded once from the DB (via
refresh_faq_cache(), called at app startup), so the hot call path
(get_faq_context_block) stays synchronous and fast — no DB query per call.

Usage:
    from app.llm.company_faq import get_faq_context_block, refresh_faq_cache
    # at startup:
    await refresh_faq_cache()
    # per call:
    full_prompt = VOICE_SYSTEM_PROMPT + "\n\n" + get_faq_context_block()
"""

from typing import Optional
from loguru import logger

_CACHED_CONTEXT_BLOCK: Optional[str] = None
_COMPANY_NAME = "Cybernauts"


async def refresh_faq_cache() -> None:
    """Load all FAQ entries from the database and build the cached context block.

    Call this once at application startup (and optionally on a timer/admin
    action if FAQs are edited at runtime).
    """
    global _CACHED_CONTEXT_BLOCK

    from app.db.connection import db_manager
    from app.repositories.faq_repository import FAQRepository

    try:
        async with db_manager.get_session() as db:
            faqs = await FAQRepository.get_all(db)

        lines = [
            f"COMPANY KNOWLEDGE BASE — {_COMPANY_NAME}",
            "Use the following verified information to answer customer questions "
            "about the company. If a caller asks something not covered here, "
            "don't guess — instead say you don't have that specific detail, and "
            "offer to take their Name and Phone number so the team can reach out to them.",
            "",
        ]

        current_category = None
        for faq in faqs:
            if faq.category != current_category:
                lines.append(f"## {faq.category}")
                current_category = faq.category
            lines.append(f"Q: {faq.question}")
            lines.append(f"A: {faq.answer}")

        _CACHED_CONTEXT_BLOCK = "\n".join(lines)
        logger.info("FAQ cache refreshed from database | entries={count}", count=len(faqs))
    except Exception as e:
        logger.error("Failed to refresh FAQ cache from database: {err}", err=e)
        if _CACHED_CONTEXT_BLOCK is None:
            _CACHED_CONTEXT_BLOCK = ""  # fail safe: empty block rather than crashing calls


def get_faq_context_block() -> str:
    """Return the cached FAQ context block (synchronous, no DB call).

    Returns an empty string if the cache hasn't been populated yet
    (refresh_faq_cache() wasn't called or failed) — this fails safe rather
    than crashing the call.
    """
    if _CACHED_CONTEXT_BLOCK is None:
        logger.warning("get_faq_context_block called before cache was populated")
        return ""
    return _CACHED_CONTEXT_BLOCK
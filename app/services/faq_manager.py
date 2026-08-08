import asyncio
from loguru import logger
from app.db.connection import db_manager
from app.repositories.faq_repository import FAQRepository
from app.services.vector_store import search_faq as vector_search_faq, store_pending_faq


async def fetch_faq(params, query: str):
    """Retrieve verified company information, products, services, pricing, or policies from the FAQ knowledge base.
    
    Call this tool when the user asks a question about the company's offerings.
    Do NOT guess or hallucinate answers about the company.
    
    Args:
        query (str): The search term or question to look up in the FAQ.
    """
    logger.info(f"ACTIONABLE AI: Triggered 'fetch_faq' tool! Query: {query}")
    
    try:
        # ── 1. Existing keyword search (unchanged) ──
        words = [w for w in query.split() if len(w) > 3]
        search_terms = words if words else [query]
        
        results = []
        async with db_manager.get_session() as db:
            for term in search_terms:
                faqs = await FAQRepository.search_faqs(db, term)
                for f in faqs:
                    if f.question not in [r["question"] for r in results]:
                        results.append({"category": f.category, "question": f.question, "answer": f.answer})
                        
        if results:
            top_results = results[:3]
            answer_text = "\n".join([f"Q: {r['question']}\nA: {r['answer']}" for r in top_results])
            logger.info(f"fetch_faq found {len(top_results)} results via keyword search.")
            if getattr(params, "result_callback", None):
                await params.result_callback({
                    "success": True, 
                    "found": True, 
                    "answer": answer_text
                })
            return

        # ── 2. Keyword search failed — try semantic vector search ──
        logger.info("Keyword search found nothing, trying semantic vector search...")
        semantic_match = await vector_search_faq(query)

        if semantic_match:
            logger.info(f"fetch_faq found semantic match (score={semantic_match['score']:.2f}): {semantic_match['question'][:60]}...")
            if getattr(params, "result_callback", None):
                await params.result_callback({
                    "success": True,
                    "found": True,
                    "answer": f"Q: {semantic_match['question']}\nA: {semantic_match['answer']}"
                })
            return

        # ── 3. Neither found anything — store as a pending FAQ for review ──
        logger.info("fetch_faq found no results (keyword or semantic).")
        try:
            await store_pending_faq(question=query)
        except Exception as store_err:
            logger.error(f"Failed to store pending FAQ: {store_err}")

        if getattr(params, "result_callback", None):
            await params.result_callback({
                "success": True, 
                "found": False, 
                "message": "No relevant FAQ found. You must tell the user that you don't have that verified information and offer to connect them with the team."
            })

    except Exception as e:
        logger.error(f"Failed to fetch FAQ: {e}")
        if getattr(params, "result_callback", None):
            await params.result_callback({"success": False, "error": "database_error"})
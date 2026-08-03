import asyncio
from loguru import logger
from app.db.connection import db_manager
from app.repositories.faq_repository import FAQRepository

async def fetch_faq(params, query: str):
    """Retrieve verified company information, products, services, pricing, or policies from the FAQ knowledge base.
    
    Call this tool when the user asks a question about the company's offerings.
    Do NOT guess or hallucinate answers about the company.
    
    Args:
        query (str): The search term or question to look up in the FAQ.
    """
    logger.info(f"ACTIONABLE AI: Triggered 'fetch_faq' tool! Query: {query}")
    
    try:
        # We process search keywords: if the query is a long sentence, we might want to split it. 
        # But ILIKE %query% might fail if the query is a full sentence.
        # Let's extract key terms or just try the query directly.
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
            # We can format the top 3 results
            top_results = results[:3]
            answer_text = "\n".join([f"Q: {r['question']}\nA: {r['answer']}" for r in top_results])
            logger.info(f"fetch_faq found {len(top_results)} results.")
            if getattr(params, "result_callback", None):
                await params.result_callback({
                    "success": True, 
                    "found": True, 
                    "answer": answer_text
                })
        else:
            logger.info("fetch_faq found no results.")
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

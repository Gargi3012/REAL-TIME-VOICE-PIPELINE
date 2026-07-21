import asyncio
from app.db.connection import db_manager
from sqlalchemy import text

async def check():
    async with db_manager.get_session() as db:
        # Fetch clients and their summaries
        result = await db.execute(text("""
            SELECT c.phone_number, cs.summary, cs.updated_at 
            FROM clients c
            LEFT JOIN conversation_summaries cs ON c.id = cs.client_id
            ORDER BY cs.updated_at DESC NULLS LAST
            LIMIT 10
        """))
        
        print("--- RECENT CONVERSATION SUMMARIES ---")
        for row in result:
            phone, summary, updated_at = row
            if summary:
                short_summary = (summary[:100] + '...') if len(summary) > 100 else summary
            else:
                short_summary = "NO SUMMARY STORED"
            print(f"[{updated_at}] Phone: {phone}")
            print(f"Summary: {short_summary}")
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(check())

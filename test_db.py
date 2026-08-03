import asyncio
from app.db.connection import db_manager
from sqlalchemy import text
from datetime import datetime, timedelta

async def cleanup_stale_streams():
    db_manager.init_db()
    async with db_manager.get_session() as db:
        res = await db.execute(text("DELETE FROM active_streams WHERE started_at < NOW() - INTERVAL '2 hours'"))
        print(f"Cleaned up {res.rowcount} stale streams")
        
asyncio.run(cleanup_stale_streams())

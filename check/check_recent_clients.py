import asyncio
from app.db.connection import db_manager
from sqlalchemy import select
from app.db.models import Client

async def main():
    async with db_manager.get_session() as db:
        stmt = select(Client).order_by(Client.created_at.desc()).limit(5)
        result = await db.execute(stmt)
        for c in result.scalars().all():
            print(f"Client: {repr(c.phone_number)}, ID: {c.id}, Created At: {c.created_at}")

asyncio.run(main())

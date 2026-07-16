import asyncio
from sqlalchemy import select
from app.db.connection import db_manager
from app.db.models import Client


async def list_all():
    async with db_manager.get_session() as db:
        stmt = select(Client)
        result = await db.execute(stmt)
        clients = result.scalars().all()
        for c in clients:
            print(f"ID: {c.id} | Phone: {c.phone_number} | Created: {c.created_at}")


if __name__ == "__main__":
    asyncio.run(list_all())
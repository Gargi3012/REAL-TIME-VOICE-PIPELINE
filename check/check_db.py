import asyncio
from app.db.connection import db_manager
from app.repositories.client_repository import ClientRepository
from app.repositories.session_repository import SessionRepository

async def main():
    async with db_manager.get_session() as db:
        client = await ClientRepository.get_by_phone_number(db, "+917082968702")
        if client:
            print(f"Client found: ID {client.id}")
            summary = await SessionRepository.get_summary(db, client.id)
            print(f"Summary: {summary}")
        else:
            print("Client not found")

asyncio.run(main())

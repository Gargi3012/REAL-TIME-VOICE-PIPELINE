import asyncio
from app.db.connection import db_manager
from app.repositories.client_repository import ClientRepository
from app.repositories.session_repository import SessionRepository


async def check():
    phone_number = "unknown_client"  # <-- yahan apna actual number

    async with db_manager.get_session() as db:
        client = await ClientRepository.get_by_phone_number(db, phone_number)
        if client:
            summary = await SessionRepository.get_summary(db, client.id)
            print("SAVED SUMMARY:", summary)
        else:
            print("No client found for this number")


if __name__ == "__main__":
    asyncio.run(check())
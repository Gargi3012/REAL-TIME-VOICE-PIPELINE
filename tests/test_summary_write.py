import asyncio
from app.db.connection import db_manager
from app.repositories.client_repository import ClientRepository
from app.repositories.session_repository import SessionRepository


async def test_summary():
    try:
        async with db_manager.get_session() as db:
            # Create/get a test client
            client = await ClientRepository.get_or_create_client(db, "+91TESTNUMBER123")
            print("Client:", client.id)

            # Save a summary
            await SessionRepository.save_summary(db, client.id, "Test summary: caller asked about AI services and pricing.")
            print("Summary saved successfully!")

            # Read it back
            summary = await SessionRepository.get_summary(db, client.id)
            print("SAVED SUMMARY:", summary)
    except Exception as e:
        print("FAILED with error:")
        print(type(e).__name__, str(e))


if __name__ == "__main__":
    asyncio.run(test_summary())
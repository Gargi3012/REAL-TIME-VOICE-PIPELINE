import asyncio
from app.db.connection import db_manager
from app.repositories.client_repository import ClientRepository
from app.repositories.session_repository import SessionRepository

async def test_fetch():
    phone_number = "+917082968702"
    
    async def fetch_db():
        for attempt in range(2):
            try:
                async with db_manager.get_session() as db:
                    print(f"Attempt {attempt}: getting client")
                    client = await ClientRepository.get_or_create_client(db, phone_number)
                    print(f"Got client: {client.id}")
                    summary_text = await SessionRepository.get_summary(db, client.id)
                    print(f"Got summary: {bool(summary_text)}")
                    return str(client.id), summary_text
            except Exception as db_err:
                print(f"Exception on attempt {attempt}: {db_err}")
                import traceback
                traceback.print_exc()
                if attempt == 1:
                    raise db_err
                await asyncio.sleep(0.5)

    client_id_str, summary_text = await asyncio.wait_for(fetch_db(), timeout=3.0)
    print("Final result:", client_id_str)

if __name__ == "__main__":
    asyncio.run(test_fetch())

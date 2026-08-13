import asyncio
from dotenv import load_dotenv
load_dotenv()

from app.services.vector_store import search_faq, store_pending_faq

async def main():
    # Test 1: Search for something that shouldn't match any existing FAQ
    print("=== Testing semantic search (should find nothing, since FAQ collection is empty) ===")
    result = await search_faq("xenobiology protocol compliance zebra migration")
    print("Search result:", result)

    # Test 2: Store it as a pending FAQ
    print("\n=== Storing as pending FAQ ===")
    await store_pending_faq(
        question="xenobiology protocol compliance zebra migration",
        phone_number="test_phone",
        session_id="test_session_123"
    )
    print("Done — check Qdrant dashboard 'pending_faqs' collection now.")

if __name__ == "__main__":
    asyncio.run(main())
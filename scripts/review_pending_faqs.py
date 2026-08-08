"""
Interactive CLI to review pending FAQs and promote approved ones
into the official FAQ knowledge base.

Run: python -m scripts.review_pending_faqs
"""
import asyncio
from dotenv import load_dotenv
load_dotenv()

from app.services.vector_store import list_pending_faqs, delete_pending_faq, add_faq


async def main():
    pending = await list_pending_faqs()

    if not pending:
        print("No pending FAQs to review. 🎉")
        return

    print(f"\nFound {len(pending)} pending question(s).\n")

    for item in pending:
        print("─" * 60)
        print(f"Question: {item.get('question')}")
        print(f"From phone: {item.get('phone_number', 'unknown')}")
        print(f"Session: {item.get('session_id', 'unknown')}")

        choice = input("\n[a]pprove & answer / [s]kip / [d]elete permanently: ").strip().lower()

        if choice == "a":
            answer = input("Enter the answer: ").strip()
            if answer:
                await add_faq(item["question"], answer)
                await delete_pending_faq(item["id"])
                print("✅ Added to official FAQ and removed from pending.\n")
            else:
                print("⚠️  Empty answer, skipped.\n")
        elif choice == "d":
            await delete_pending_faq(item["id"])
            print("🗑️  Deleted permanently.\n")
        else:
            print("⏭️  Skipped for now.\n")

    print("Review complete.")


if __name__ == "__main__":
    asyncio.run(main())
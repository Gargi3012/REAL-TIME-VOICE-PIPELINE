"""
One-time script to migrate FAQ data from app/llm/knowledge_base.json
into the company_faqs database table.
"""
import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from app.db.connection import db_manager
from app.repositories.faq_repository import FAQRepository


async def seed():
    json_path = Path(__file__).parent.parent / "app" / "llm" / "knowledge_base.json"

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    async with db_manager.get_session() as db:
        # Clear existing entries first, so re-running this script is safe (idempotent)
        await FAQRepository.delete_all(db)

        count = 0
        for section in data.get("faqs", []):
            category = section.get("category", "General")
            for pair in section.get("qa", []):
                await FAQRepository.create_faq(
                    db,
                    category=category,
                    question=pair["q"],
                    answer=pair["a"],
                )
                count += 1

    print(f"Seeded {count} FAQ entries into the database.")


if __name__ == "__main__":
    asyncio.run(seed())
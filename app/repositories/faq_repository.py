from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CompanyFAQ


class FAQRepository:
    """Handles database operations for the CompanyFAQ model."""

    @staticmethod
    async def get_all(session: AsyncSession) -> List[CompanyFAQ]:
        """Fetch all FAQ entries, ordered by category."""
        stmt = select(CompanyFAQ).order_by(CompanyFAQ.category)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_category(session: AsyncSession, category: str) -> List[CompanyFAQ]:
        """Fetch all FAQ entries for a specific category."""
        stmt = select(CompanyFAQ).where(CompanyFAQ.category == category)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_faq(
        session: AsyncSession, category: str, question: str, answer: str
    ) -> CompanyFAQ:
        """Create a new FAQ entry."""
        faq = CompanyFAQ(category=category, question=question, answer=answer)
        session.add(faq)
        await session.flush()
        return faq

    @staticmethod
    async def delete_all(session: AsyncSession) -> None:
        """Delete all FAQ entries (used before re-seeding)."""
        from sqlalchemy import delete
        stmt = delete(CompanyFAQ)
        await session.execute(stmt)
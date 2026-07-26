import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ConversationSummary, DbSession


class SessionRepository:
    """Handles database operations for Session and ConversationSummary models."""

    @staticmethod
    async def create_session(session: AsyncSession, session_id: str, client_id: uuid.UUID) -> DbSession:
        """Create a new session record in the database."""
        db_session = DbSession(
            session_id=session_id,
            client_id=client_id,
            status="ACTIVE"
        )
        session.add(db_session)
        await session.flush()
        return db_session

    @staticmethod
    async def close_session(session: AsyncSession, session_id: str, duration: Optional[int] = None) -> Optional[DbSession]:
        """Mark a session as CLOSED and record its end time and duration."""
        stmt = select(DbSession).where(DbSession.session_id == session_id)
        result = await session.execute(stmt)
        db_session = result.scalars().first()

        if db_session:
            db_session.status = "CLOSED"
            db_session.ended_at = datetime.utcnow()
            if duration is not None:
                db_session.duration = duration
            await session.flush()
        
        return db_session

    @staticmethod
    async def get_summary(session: AsyncSession, client_id: uuid.UUID) -> Optional[str]:
        """Retrieve the latest conversation summary for a client."""
        stmt = select(ConversationSummary).where(ConversationSummary.client_id == client_id)
        result = await session.execute(stmt)
        summary_record = result.scalars().first()
        return summary_record.summary if summary_record else None

    @staticmethod
    async def save_summary(session: AsyncSession, client_id: uuid.UUID, summary_text: str) -> ConversationSummary:
        """Create or update the conversation summary for a client."""
        stmt = select(ConversationSummary).where(ConversationSummary.client_id == client_id)
        result = await session.execute(stmt)
        summary_record = result.scalars().first()

        from datetime import datetime, timezone
        if summary_record:
            summary_record.summary = summary_text
            summary_record.updated_at = datetime.now(timezone.utc)
        else:
            summary_record = ConversationSummary(client_id=client_id, summary=summary_text)
            session.add(summary_record)
        
        await session.flush()
        return summary_record

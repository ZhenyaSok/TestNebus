from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import OutboxModel


class OutboxEvent:
    """Событие, которое ещё не ушло в брокер."""

    def __init__(
        self, event_id: UUID, event_type: str, payload: dict[str, Any]
    ) -> None:
        self.id = event_id
        self.event_type = event_type
        self.payload = payload


class SqlAlchemyOutbox:
    """Берёт одну неопубликованную строку и помечает её после отправки."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim_next(self) -> OutboxEvent | None:
        """Один запрос самой старой неопубликованной записи."""
        statement = (
            select(OutboxModel)
            .where(OutboxModel.published_at.is_(None))
            .order_by(OutboxModel.created_at)
            .limit(1)
        )
        if self._session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update(skip_locked=True)
        row = await self._session.scalar(statement)
        if row is None:
            return None
        return OutboxEvent(row.id, row.event_type, dict(row.payload))

    async def mark_published(self, event_id: UUID) -> None:
        """Ставит published_at у уже выбранной строки."""
        row = await self._session.get(OutboxModel, event_id)
        if row is None:
            return
        row.published_at = datetime.now(timezone.utc)
        await self._session.flush()

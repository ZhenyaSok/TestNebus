import logging
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.outbox import SqlAlchemyOutbox

logger = logging.getLogger(__name__)


class EventPublisher(Protocol):
    """Публикация события в брокер."""

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """Кладёт тело события в очередь event_type."""


async def publish_next(
    session_factory: async_sessionmaker[AsyncSession],
    publisher: EventPublisher,
) -> bool:
    """Отправляет одну строку outbox и только потом ставит published_at."""
    async with session_factory() as session:
        store = SqlAlchemyOutbox(session)
        event = await store.claim_next()
        if event is None:
            await session.rollback()
            return False
        try:
            await publisher.publish(event.event_type, event.payload)
        except Exception:
            await session.rollback()
            raise
        await store.mark_published(event.id)
        await session.commit()
        logger.info(
            "Событие %s опубликовано для платежа %s",
            event.event_type,
            event.payload.get("payment_id"),
        )
        return True

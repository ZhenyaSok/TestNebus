import logging
from datetime import timedelta
from typing import Any
from uuid import UUID

from faststream.rabbit import RabbitBroker
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.processing import (
    RetryLater,
    SendToDeadLetter,
    WebhookDeliveryError,
    decide_delivery,
    process_payment,
)
from app.infrastructure.clock import AsyncSleeper
from app.infrastructure.db.repository import SqlAlchemyPaymentRepository
from app.infrastructure.gateway import SimulatedGateway
from app.infrastructure.messaging.topology import (
    DEAD_EXCHANGE,
    DEAD_QUEUE,
    PAYMENTS_EXCHANGE,
)
from app.infrastructure.webhook import HttpWebhookNotifier

logger = logging.getLogger(__name__)


class SessionCommit:
    """Коммит сессии, в которой обновили статус."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        """Фиксирует статус до отправки webhook."""
        await self._session.commit()


class RabbitDelivery:
    """Повтор через TTL-очередь или запись в DLQ."""

    def __init__(self, broker: RabbitBroker) -> None:
        self._broker = broker

    async def retry(self, payload: dict[str, Any], decision: RetryLater) -> None:
        """Возвращает сообщение в работу после паузы."""
        await self._broker.publish(
            payload,
            exchange=PAYMENTS_EXCHANGE,
            routing_key="payments.new.retry",
            headers={"x-attempts": decision.attempts},
            expiration=timedelta(seconds=decision.delay_seconds),
            persist=True,
        )

    async def dead(self, payload: dict[str, Any]) -> None:
        """Кладёт сообщение в DLQ."""
        await self._broker.publish(
            payload,
            exchange=DEAD_EXCHANGE,
            routing_key=DEAD_QUEUE.routing_key,
            persist=True,
        )


def read_attempts(headers: dict[str, Any] | None) -> int:
    """Номер попытки из заголовка. Первая доставка — 1."""
    if not headers:
        return 1
    return int(headers.get("x-attempts", 1))


async def deliver_payment(
    broker: RabbitBroker,
    sessions: async_sessionmaker[AsyncSession],
    payload: dict[str, Any],
    attempts: int,
) -> None:
    """Проводит платёж. Ошибка доставки уходит в повтор или в DLQ."""
    payment_id = UUID(str(payload["payment_id"]))
    async with sessions() as session:
        repository = SqlAlchemyPaymentRepository(session)
        try:
            await process_payment(
                repository,
                SimulatedGateway(AsyncSleeper()),
                HttpWebhookNotifier(),
                SessionCommit(session),
                payment_id,
            )
        except WebhookDeliveryError:
            logger.warning(
                "Webhook не доставлен для платежа %s, попытка %s",
                payload.get("payment_id"),
                attempts,
            )
            await _forward(broker, payload, attempts)
        except Exception:
            logger.exception("Не удалось обработать платёж")
            await session.rollback()
            await _forward(broker, payload, attempts)


async def _forward(
    broker: RabbitBroker, payload: dict[str, Any], attempts: int
) -> None:
    decision = decide_delivery(attempts)
    delivery = RabbitDelivery(broker)
    payment_id = payload.get("payment_id")
    if isinstance(decision, SendToDeadLetter):
        logger.warning("Платёж %s отправлен в DLQ на попытке %s", payment_id, attempts)
        await delivery.dead(payload)
        return
    logger.info(
        "Платёж %s вернётся через %s с, попытка %s",
        payment_id,
        decision.delay_seconds,
        decision.attempts,
    )
    await delivery.retry(payload, decision)

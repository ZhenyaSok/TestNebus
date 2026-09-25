import asyncio
import contextlib
import logging
from typing import Any

from faststream import FastStream
from faststream.rabbit import RabbitBroker, RabbitMessage

from app.config import get_settings
from app.infrastructure.db.session import session_factory
from app.infrastructure.messaging.delivery import deliver_payment, read_attempts
from app.infrastructure.messaging.relay import EventPublisher, publish_next
from app.infrastructure.messaging.topology import (
    NEW_QUEUE,
    PAYMENTS_EXCHANGE,
    declare_topology,
)

logger = logging.getLogger(__name__)
broker = RabbitBroker(get_settings().rabbitmq_url)
app = FastStream(broker)


class BrokerPublisher:
    """Публикует событие outbox в обменник payments."""

    def __init__(self, rabbit: RabbitBroker) -> None:
        self._rabbit = rabbit

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """Кладёт тело в очередь с именем типа события."""
        await self._rabbit.publish(
            payload,
            exchange=PAYMENTS_EXCHANGE,
            routing_key=event_type,
            persist=True,
        )


@broker.subscriber(NEW_QUEUE, PAYMENTS_EXCHANGE)
async def on_payment_created(body: dict[str, Any], message: RabbitMessage) -> None:
    """Обрабатывает одно событие payments.new."""
    await deliver_payment(broker, session_factory, body, read_attempts(message.headers))


async def _relay(stop: asyncio.Event, publisher: EventPublisher) -> None:
    while not stop.is_set():
        try:
            published = await publish_next(session_factory, publisher)
        except Exception:
            logger.exception("Не удалось опубликовать outbox")
            published = False
        if published:
            continue
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=1)


async def serve() -> None:
    """Поднимает очереди, реле outbox и consumer."""
    stop = asyncio.Event()
    await broker.connect()
    await declare_topology(broker)
    relay = asyncio.create_task(_relay(stop, BrokerPublisher(broker)))
    try:
        await app.run()
    finally:
        stop.set()
        relay.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await relay


def main() -> None:
    """Точка входа процесса consumer."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve())


if __name__ == "__main__":
    main()

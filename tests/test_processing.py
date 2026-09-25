from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.processing import (
    RetryLater,
    SendToDeadLetter,
    WebhookDeliveryError,
    decide_delivery,
    process_payment,
)
from app.domain.payment import Currency, Payment, PaymentStatus
from app.infrastructure.db.outbox import SqlAlchemyOutbox
from app.infrastructure.db.repository import SqlAlchemyPaymentRepository
from app.infrastructure.gateway import SimulatedGateway
from app.infrastructure.messaging.relay import publish_next
from app.infrastructure.webhook import HttpWebhookNotifier


class ImmediateSleeper:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def sleep(self, seconds: float) -> None:
        """Запоминает паузу и сразу возвращает управление."""
        self.calls.append(seconds)


class FixedGateway:
    def __init__(self, succeeded: bool) -> None:
        self.succeeded = succeeded
        self.calls = 0

    async def authorize(self) -> bool:
        """Возвращает заранее известный итог шлюза."""
        self.calls += 1
        return self.succeeded


class RecordingNotifier:
    def __init__(self, failed_times: int = 0) -> None:
        self.failed_times = failed_times
        self.sent: list[PaymentStatus] = []

    async def notify(self, payment: Payment) -> None:
        """Падает заданное число раз, затем запоминает статус."""
        if self.failed_times:
            self.failed_times -= 1
            raise RuntimeError("webhook down")
        self.sent.append(payment.status)


class SessionCommit:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        """Фиксирует тестовую транзакцию."""
        await self._session.commit()


class MemoryPublisher:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, str]]] = []

    async def publish(self, event_type: str, payload: dict[str, str]) -> None:
        """Запоминает событие вместо брокера."""
        self.events.append((event_type, payload))


def _payment() -> Payment:
    return Payment.create(
        amount=Decimal("10.50"),
        currency=Currency.RUB,
        description="order",
        metadata={"order": "42"},
        idempotency_key=f"key-{uuid4()}",
        webhook_url="https://example.com/hook",
    )


def test_decide_delivery_backs_off_then_stops() -> None:
    """Первые две неудачи ждут, третья уходит в DLQ."""
    first = decide_delivery(1)
    second = decide_delivery(2)
    third = decide_delivery(3)
    assert isinstance(first, RetryLater)
    assert first.delay_seconds == 1
    assert first.attempts == 2
    assert isinstance(second, RetryLater)
    assert second.delay_seconds == 2
    assert isinstance(third, SendToDeadLetter)


async def test_gateway_sleeps_and_uses_threshold() -> None:
    """Шлюз ждёт переданную паузу и считает успехом значение ниже 0.9."""
    sleeper = ImmediateSleeper()
    success = SimulatedGateway(sleeper, roll=lambda: 0.0, delay=lambda: 3)
    failure = SimulatedGateway(sleeper, roll=lambda: 0.95, delay=lambda: 4)
    assert await success.authorize() is True
    assert await failure.authorize() is False
    assert sleeper.calls == [3, 4]


async def test_webhook_retries_then_succeeds() -> None:
    """Две ошибки отправки, третья попытка проходит."""
    sleeper = ImmediateSleeper()
    calls = 0

    async def post(url: str, body: dict[str, str]) -> None:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError(url)

    notifier = HttpWebhookNotifier(sleeper, post=post)
    await notifier.notify(_payment())
    assert calls == 3
    assert sleeper.calls == [1.0, 2.0]


async def test_webhook_gives_up_after_three_attempts() -> None:
    """Три неудачи подряд заканчиваются ошибкой доставки."""

    async def post(url: str, body: dict[str, str]) -> None:
        raise RuntimeError(url)

    notifier = HttpWebhookNotifier(ImmediateSleeper(), post=post)
    with pytest.raises(WebhookDeliveryError):
        await notifier.notify(_payment())


async def test_process_payment_charges_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Шлюз вызывается один раз, повторная обработка только шлёт webhook."""
    payment = _payment()
    gateway = FixedGateway(True)
    notifier = RecordingNotifier()
    async with session_factory() as session:
        repository = SqlAlchemyPaymentRepository(session)
        assert await repository.add(
            payment, "payments.new", {"payment_id": str(payment.id)}
        )
        await process_payment(
            repository,
            gateway,
            notifier,
            SessionCommit(session),
            payment.id,
        )
    assert gateway.calls == 1
    assert notifier.sent == [PaymentStatus.SUCCEEDED]

    async with session_factory() as session:
        repository = SqlAlchemyPaymentRepository(session)
        await process_payment(
            repository,
            gateway,
            notifier,
            SessionCommit(session),
            payment.id,
        )
    assert gateway.calls == 1
    assert notifier.sent == [PaymentStatus.SUCCEEDED, PaymentStatus.SUCCEEDED]


async def test_publish_next_marks_outbox(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """После публикации у строки outbox появляется published_at."""
    payment = _payment()
    async with session_factory() as session:
        repository = SqlAlchemyPaymentRepository(session)
        await repository.add(payment, "payments.new", {"payment_id": str(payment.id)})
        await session.commit()

    publisher = MemoryPublisher()
    assert await publish_next(session_factory, publisher) is True
    assert publisher.events[0][0] == "payments.new"
    assert await publish_next(session_factory, publisher) is False

    async with session_factory() as session:
        event = await SqlAlchemyOutbox(session).claim_next()
    assert event is None

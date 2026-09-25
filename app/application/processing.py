import logging
from typing import Protocol
from uuid import UUID

from app.domain.payment import Payment, PaymentStatus

logger = logging.getLogger(__name__)


class WebhookDeliveryError(Exception):
    """Webhook не принял уведомление."""


class PaymentGateway(Protocol):
    """Эмуляция платёжного шлюза."""

    async def authorize(self) -> bool:
        """True, если шлюз провёл платёж."""


class PaymentNotifier(Protocol):
    """Отправка результата на webhook."""

    async def notify(self, payment: Payment) -> None:
        """Сообщает клиенту итоговый статус."""


class Transaction(Protocol):
    """Фиксация статуса до вызова webhook."""

    async def commit(self) -> None:
        """Сохраняет изменения текущей транзакции."""


class ProcessingRepository(Protocol):
    """Чтение и обновление платежа без лишних запросов."""

    async def get(self, payment_id: UUID) -> Payment | None:
        """Один запрос платежа по id."""

    async def save(self, payment: Payment) -> None:
        """Записывает статус обратно в ту же строку."""


class RetryLater:
    """Повтор доставки через delay_seconds."""

    def __init__(self, delay_seconds: int, attempts: int) -> None:
        self.delay_seconds = delay_seconds
        self.attempts = attempts


class SendToDeadLetter:
    """Три попытки исчерпаны."""


def decide_delivery(attempts: int) -> RetryLater | SendToDeadLetter:
    """Три попытки. Пауза между ними 1 с, затем 2 с."""
    if attempts >= 3:
        return SendToDeadLetter()
    return RetryLater(delay_seconds=2 ** (attempts - 1), attempts=attempts + 1)


async def process_payment(
    repository: ProcessingRepository,
    gateway: PaymentGateway,
    notifier: PaymentNotifier,
    transaction: Transaction,
    payment_id: UUID,
) -> None:
    """Проводит платёж один раз и отправляет webhook."""
    payment = await repository.get(payment_id)
    if payment is None:
        logger.warning("Платёж %s не найден", payment_id)
        return
    if payment.status == PaymentStatus.PENDING:
        payment.finish(await gateway.authorize())
        await repository.save(payment)
        await transaction.commit()
        logger.info(
            "Платёж %s проведён со статусом %s",
            payment.id,
            payment.status.value,
        )
    else:
        logger.info(
            "Платёж %s уже в статусе %s, повторяем webhook",
            payment.id,
            payment.status.value,
        )
    await notifier.notify(payment)
    logger.info("Webhook отправлен для платежа %s", payment.id)

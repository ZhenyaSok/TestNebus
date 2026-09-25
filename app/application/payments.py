from typing import Any, Protocol
from uuid import UUID

from app.domain.payment import PAYMENT_CREATED_EVENT, Payment


class IdempotencyConflict(Exception):
    """Тот же ключ уже сохранён с другим телом запроса."""

    def __init__(self) -> None:
        super().__init__("Ключ идемпотентности уже использован с другими данными")


class PaymentNotFound(Exception):
    """Платёж с таким id не найден."""

    def __init__(self) -> None:
        super().__init__("Платёж не найден")


class PaymentRepository(Protocol):
    """Хранилище платежей. Реализация в инфраструктуре."""

    async def get(self, payment_id: UUID) -> Payment | None:
        """Один запрос платежа по id."""

    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        """Один запрос платежа по ключу идемпотентности."""

    async def add(
        self, payment: Payment, event_type: str, payload: dict[str, Any]
    ) -> bool:
        """Пишет платёж и outbox. False, если ключ уже занят."""


async def create_payment(repository: PaymentRepository, payment: Payment) -> Payment:
    """Сохраняет платёж. Повтор с тем же телом возвращает уже созданный."""
    existing = await repository.get_by_idempotency_key(payment.idempotency_key)
    if existing is not None:
        return _same_or_conflict(existing, payment)

    saved = await repository.add(
        payment,
        PAYMENT_CREATED_EVENT,
        {"payment_id": str(payment.id)},
    )
    if saved:
        return payment

    existing = await repository.get_by_idempotency_key(payment.idempotency_key)
    if existing is None:
        raise RuntimeError("Не удалось сохранить платёж")
    return _same_or_conflict(existing, payment)


async def get_payment(repository: PaymentRepository, payment_id: UUID) -> Payment:
    """Возвращает платёж или ошибку, если его нет."""
    payment = await repository.get(payment_id)
    if payment is None:
        raise PaymentNotFound()
    return payment


def _same_or_conflict(existing: Payment, incoming: Payment) -> Payment:
    if not existing.same_data(incoming):
        raise IdempotencyConflict()
    return existing

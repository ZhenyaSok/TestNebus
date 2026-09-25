from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

PAYMENT_CREATED_EVENT = "payments.new"
_MONEY = Decimal("0.01")


class Currency(str, Enum):
    """Валюта платежа."""

    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class PaymentStatus(str, Enum):
    """Статус обработки платежа."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class InvalidPayment(Exception):
    """Платёж не проходит проверку."""


@dataclass(slots=True)
class Payment:
    """Платёж, принятый сервисом."""

    id: UUID
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict[str, Any]
    status: PaymentStatus
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        amount: Decimal,
        currency: Currency,
        description: str,
        metadata: dict[str, Any],
        idempotency_key: str,
        webhook_url: str,
    ) -> "Payment":
        """Собирает новый платёж в статусе pending."""
        idempotency_key = idempotency_key.strip()
        if not idempotency_key:
            raise InvalidPayment("Ключ идемпотентности пустой")
        return cls(
            id=uuid4(),
            amount=normalize_amount(amount),
            currency=currency,
            description=description,
            metadata=dict(metadata),
            status=PaymentStatus.PENDING,
            idempotency_key=idempotency_key,
            webhook_url=webhook_url,
            created_at=datetime.now(timezone.utc),
        )

    def same_data(self, other: "Payment") -> bool:
        """Совпадает ли тело запроса, без учёта id и статуса."""
        return (
            self.amount == other.amount
            and self.currency == other.currency
            and self.description == other.description
            and self.metadata == other.metadata
            and self.webhook_url == other.webhook_url
        )


def normalize_amount(amount: Decimal) -> Decimal:
    """Приводит сумму к двум знакам. Лишняя точность — ошибка."""
    if amount <= 0:
        raise InvalidPayment("Сумма должна быть больше нуля")
    exponent = amount.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -2:
        raise InvalidPayment("У суммы не больше двух знаков после запятой")
    return amount.quantize(_MONEY)

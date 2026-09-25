from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.payment import Currency, Payment, PaymentStatus
from app.infrastructure.db.models import OutboxModel, PaymentModel


class SqlAlchemyPaymentRepository:
    """Платёж и запись outbox в одной транзакции."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, payment_id: UUID) -> Payment | None:
        """Загружает платёж одним запросом по первичному ключу."""
        row = await self._session.get(PaymentModel, payment_id)
        if row is None:
            return None
        return _to_payment(row)

    async def get_by_idempotency_key(self, key: str) -> Payment | None:
        """Загружает платёж одним запросом по уникальному ключу."""
        statement = select(PaymentModel).where(PaymentModel.idempotency_key == key)
        row = await self._session.scalar(statement)
        if row is None:
            return None
        return _to_payment(row)

    async def add(
        self, payment: Payment, event_type: str, payload: dict[str, Any]
    ) -> bool:
        """Добавляет платёж и outbox. False, если такой ключ уже есть."""
        self._session.add(_to_row(payment))
        try:
            await self._session.flush()
        except IntegrityError as error:
            await self._session.rollback()
            if _is_duplicate_idempotency(error):
                return False
            raise

        self._session.add(
            OutboxModel(
                id=uuid4(),
                payment_id=payment.id,
                event_type=event_type,
                payload=payload,
                created_at=datetime.now(timezone.utc),
                published_at=None,
            )
        )
        await self._session.flush()
        return True


def _is_duplicate_idempotency(error: IntegrityError) -> bool:
    text = str(error.orig).lower()
    return "idempotency_key" in text or "uq_payments_idempotency_key" in text


def _to_row(payment: Payment) -> PaymentModel:
    return PaymentModel(
        id=payment.id,
        amount=payment.amount,
        currency=payment.currency.value,
        description=payment.description,
        metadata_json=payment.metadata,
        status=payment.status.value,
        idempotency_key=payment.idempotency_key,
        webhook_url=payment.webhook_url,
        created_at=payment.created_at,
        processed_at=payment.processed_at,
    )


def _to_payment(row: PaymentModel) -> Payment:
    return Payment(
        id=row.id,
        amount=Decimal(row.amount).quantize(Decimal("0.01")),
        currency=Currency(row.currency),
        description=row.description,
        metadata=dict(row.metadata_json),
        status=PaymentStatus(row.status),
        idempotency_key=row.idempotency_key,
        webhook_url=row.webhook_url,
        created_at=_aware(row.created_at),
        processed_at=_aware(row.processed_at) if row.processed_at is not None else None,
    )


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value

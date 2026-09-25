from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import AnyHttpUrl, BaseModel, Field

from app.api.deps import get_repository, require_api_key
from app.application import payments as payment_commands
from app.application.payments import (
    IdempotencyConflict,
    PaymentNotFound,
    PaymentRepository,
)
from app.domain.payment import Currency, InvalidPayment, Payment, PaymentStatus

router = APIRouter(
    prefix="/api/v1",
    tags=["payments"],
    dependencies=[Depends(require_api_key)],
)


class CreatePaymentRequest(BaseModel):
    """Тело запроса на создание платежа."""

    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: Currency
    description: str = Field(max_length=2000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    webhook_url: AnyHttpUrl


class PaymentAccepted(BaseModel):
    """Ответ, что платёж принят в обработку."""

    payment_id: UUID
    status: PaymentStatus
    created_at: datetime


class PaymentDetails(BaseModel):
    """Полная карточка платежа."""

    payment_id: UUID
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict[str, Any]
    status: PaymentStatus
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None


@router.post("/payments", status_code=202, response_model=PaymentAccepted)
async def create_payment(
    body: CreatePaymentRequest,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=255)
    ],
    repository: Annotated[PaymentRepository, Depends(get_repository)],
) -> PaymentAccepted:
    """Принимает платёж и пишет событие в outbox в той же транзакции."""
    try:
        payment = Payment.create(
            amount=body.amount,
            currency=body.currency,
            description=body.description,
            metadata=body.metadata,
            idempotency_key=idempotency_key,
            webhook_url=str(body.webhook_url),
        )
        payment = await payment_commands.create_payment(repository, payment)
    except InvalidPayment as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except IdempotencyConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return PaymentAccepted(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
    )


@router.get("/payments/{payment_id}", response_model=PaymentDetails)
async def get_payment(
    payment_id: UUID,
    repository: Annotated[PaymentRepository, Depends(get_repository)],
) -> PaymentDetails:
    """Возвращает платёж по id."""
    try:
        payment = await payment_commands.get_payment(repository, payment_id)
    except PaymentNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return PaymentDetails(
        payment_id=payment.id,
        amount=payment.amount,
        currency=payment.currency,
        description=payment.description,
        metadata=payment.metadata,
        status=payment.status,
        idempotency_key=payment.idempotency_key,
        webhook_url=payment.webhook_url,
        created_at=payment.created_at,
        processed_at=payment.processed_at,
    )

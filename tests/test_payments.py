from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.domain.payment import PAYMENT_CREATED_EVENT, InvalidPayment, normalize_amount
from app.infrastructure.db.models import OutboxModel

_BODY = {
    "amount": "10.50",
    "currency": "RUB",
    "description": "order",
    "metadata": {"order": "42"},
    "webhook_url": "https://example.com/hook",
}


def _headers(key: str = "order-1") -> dict[str, str]:
    return {
        "X-API-Key": get_settings().api_key,
        "Idempotency-Key": key,
    }


async def _outbox_count(factory: async_sessionmaker[AsyncSession]) -> int:
    async with factory() as session:
        count = await session.scalar(select(func.count()).select_from(OutboxModel))
    return int(count or 0)


async def test_create_and_get_payment(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Создаёт платёж, кладёт одно событие в outbox и отдаёт карточку."""
    created = await client.post("/api/v1/payments", json=_BODY, headers=_headers())
    assert created.status_code == 202
    body = created.json()
    assert body["status"] == "pending"
    assert body["payment_id"]

    loaded = await client.get(
        f"/api/v1/payments/{body['payment_id']}",
        headers={"X-API-Key": get_settings().api_key},
    )
    assert loaded.status_code == 200
    details = loaded.json()
    assert details["amount"] == "10.50"
    assert details["currency"] == "RUB"
    assert details["metadata"] == {"order": "42"}
    assert details["processed_at"] is None
    assert await _outbox_count(session_factory) == 1

    async with session_factory() as session:
        event = await session.scalar(select(OutboxModel))
    assert event is not None
    assert event.event_type == PAYMENT_CREATED_EVENT
    assert event.payload == {"payment_id": body["payment_id"]}
    assert event.published_at is None


async def test_same_key_returns_existing_payment(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Повтор с тем же телом не создаёт второй платёж и второе событие."""
    first = await client.post("/api/v1/payments", json=_BODY, headers=_headers())
    second = await client.post("/api/v1/payments", json=_BODY, headers=_headers())
    assert second.status_code == 202
    assert second.json()["payment_id"] == first.json()["payment_id"]
    assert await _outbox_count(session_factory) == 1


async def test_same_key_with_other_body_is_conflict(client: AsyncClient) -> None:
    """Тот же ключ и другая сумма — 409."""
    await client.post("/api/v1/payments", json=_BODY, headers=_headers("order-2"))
    other = {**_BODY, "amount": "11.00"}
    response = await client.post(
        "/api/v1/payments", json=other, headers=_headers("order-2")
    )
    assert response.status_code == 409


async def test_missing_api_key_is_rejected(client: AsyncClient) -> None:
    """Без ключа платёж не создаётся."""
    response = await client.post(
        "/api/v1/payments",
        json=_BODY,
        headers={"Idempotency-Key": "order-3"},
    )
    assert response.status_code == 401


async def test_unknown_payment_is_not_found(client: AsyncClient) -> None:
    """Чужой id возвращает 404."""
    response = await client.get(
        f"/api/v1/payments/{uuid4()}",
        headers={"X-API-Key": get_settings().api_key},
    )
    assert response.status_code == 404


def test_amount_keeps_two_decimal_places() -> None:
    """Лишний знак в сумме не проходит в домен."""
    assert normalize_amount(Decimal("10.5")) == Decimal("10.50")
    with pytest.raises(InvalidPayment):
        normalize_amount(Decimal("10.555"))

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.payments import PaymentRepository
from app.config import get_settings
from app.infrastructure.db.repository import SqlAlchemyPaymentRepository
from app.infrastructure.db.session import get_session


async def require_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    """Проверяет статический ключ. Без ключа или с чужим — 401."""
    expected = get_settings().api_key
    if x_api_key is None or not secrets.compare_digest(
        x_api_key.encode(), expected.encode()
    ):
        raise HTTPException(status_code=401, detail="Неверный API-ключ")


def get_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PaymentRepository:
    """Отдаёт хранилище на сессии текущего запроса."""
    return SqlAlchemyPaymentRepository(session)

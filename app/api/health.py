"""Служебная проверка живости процесса."""

from fastapi import APIRouter

router = APIRouter(tags=["service"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Проверяет, что API-процесс запущен."""
    return {"status": "ok"}

import asyncio
from typing import Protocol


class Sleeper(Protocol):
    """Пауза, которую в тестах можно не ждать."""

    async def sleep(self, seconds: float) -> None:
        """Ждёт указанное число секунд."""


class AsyncSleeper:
    """Обычный asyncio.sleep."""

    async def sleep(self, seconds: float) -> None:
        """Ждёт указанное число секунд."""
        await asyncio.sleep(seconds)

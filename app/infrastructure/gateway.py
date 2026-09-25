import random
from collections.abc import Callable

from app.infrastructure.clock import Sleeper


class SimulatedGateway:
    """Ждёт 2–5 секунд. В 90% случаев платёж успешен."""

    def __init__(
        self,
        sleeper: Sleeper,
        roll: Callable[[], float] | None = None,
        delay: Callable[[], float] | None = None,
    ) -> None:
        self._sleeper = sleeper
        self._roll = roll or random.random
        self._delay = delay or (lambda: random.uniform(2, 5))

    async def authorize(self) -> bool:
        """Возвращает итог эмуляции шлюза."""
        await self._sleeper.sleep(self._delay())
        return self._roll() < 0.9

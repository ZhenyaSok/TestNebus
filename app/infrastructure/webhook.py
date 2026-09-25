from collections.abc import Awaitable, Callable

import httpx

from app.application.processing import WebhookDeliveryError
from app.domain.payment import Payment
from app.infrastructure.clock import Sleeper

Post = Callable[[str, dict[str, str]], Awaitable[None]]


class HttpWebhookNotifier:
    """Три попытки POST с паузой 1 с и 2 с."""

    def __init__(self, sleeper: Sleeper, post: Post | None = None) -> None:
        self._sleeper = sleeper
        self._post = post

    async def notify(self, payment: Payment) -> None:
        """Шлёт статус. После третьей ошибки поднимает WebhookDeliveryError."""
        body = {
            "payment_id": str(payment.id),
            "status": payment.status.value,
            "amount": str(payment.amount),
            "currency": payment.currency.value,
        }
        delay = 1.0
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                await self._deliver(payment.webhook_url, body)
                return
            except Exception as error:
                last_error = error
                if attempt == 2:
                    break
                await self._sleeper.sleep(delay)
                delay *= 2
        raise WebhookDeliveryError from last_error

    async def _deliver(self, url: str, body: dict[str, str]) -> None:
        if self._post is not None:
            await self._post(url, body)
            return
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=body)
            response.raise_for_status()

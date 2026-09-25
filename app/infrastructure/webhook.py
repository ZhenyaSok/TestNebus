from collections.abc import Awaitable, Callable

import httpx

from app.application.processing import WebhookDeliveryError
from app.domain.payment import Payment

Post = Callable[[str, dict[str, str]], Awaitable[None]]


class HttpWebhookNotifier:
    """Один POST. Повтор и пауза живут в очереди."""

    def __init__(self, post: Post | None = None) -> None:
        self._post = post

    async def notify(self, payment: Payment) -> None:
        """Шлёт статус. Ошибка отправки поднимает WebhookDeliveryError."""
        body = {
            "payment_id": str(payment.id),
            "status": payment.status.value,
            "amount": str(payment.amount),
            "currency": payment.currency.value,
        }
        try:
            await self._deliver(payment.webhook_url, body)
        except Exception as error:
            raise WebhookDeliveryError from error

    async def _deliver(self, url: str, body: dict[str, str]) -> None:
        if self._post is not None:
            await self._post(url, body)
            return
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=body)
            response.raise_for_status()

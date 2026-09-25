from httpx import ASGITransport, AsyncClient

from app import __version__
from app.main import create_app


async def test_health() -> None:
    """Проверяет, что /health отвечает 200."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}

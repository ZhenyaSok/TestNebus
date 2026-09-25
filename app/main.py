"""Точка входа HTTP API."""

from fastapi import FastAPI

from app import __version__
from app.api.health import router as health_router
from app.config import get_settings


def create_app() -> FastAPI:
    """Создаёт экземпляр API и подключает роуты."""
    app = FastAPI(title="Payment service", version=__version__)
    app.state.settings = get_settings()
    app.include_router(health_router)
    return app


app = create_app()

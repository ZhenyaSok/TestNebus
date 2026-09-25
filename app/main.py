"""Точка входа HTTP API."""

from fastapi import FastAPI

from app.api.health import router as health_router
from app.config import get_settings


def create_app() -> FastAPI:
    """Создаёт экземпляр API и подключает роуты."""
    app = FastAPI(title="Payment service", version="0.1.0")
    app.state.settings = get_settings()
    app.include_router(health_router)
    return app


app = create_app()

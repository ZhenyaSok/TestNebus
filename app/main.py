from fastapi import FastAPI

from app import __version__
from app.api.health import router as health_router
from app.api.v1.payments import router as payments_router


def create_app() -> FastAPI:
    """Создаёт экземпляр API и подключает роуты."""
    app = FastAPI(title="Payment service", version=__version__)
    app.include_router(health_router)
    app.include_router(payments_router)
    return app


app = create_app()

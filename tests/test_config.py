"""Проверка настроек по умолчанию."""

from app.config import Settings


def test_default_settings() -> None:
    """Проверяет адреса БД и брокера, если переменные окружения не заданы."""
    settings = Settings(_env_file=None)
    assert settings.api_key
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.rabbitmq_url.startswith("amqp://")

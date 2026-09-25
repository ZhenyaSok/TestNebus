import pytest

from app.config import Settings


def test_settings_come_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Адрес базы и брокера собирается из переменных, не из кода."""
    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setenv("POSTGRES_USER", "user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_DB", "payments")
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("RABBITMQ_USER", "rmq")
    monkeypatch.setenv("RABBITMQ_PASSWORD", "secret")
    monkeypatch.setenv("RABBITMQ_HOST", "mq")
    monkeypatch.setenv("RABBITMQ_PORT", "5672")

    settings = Settings(_env_file=None)

    assert settings.api_key == "test-key"
    assert settings.database_url == "postgresql+asyncpg://user:secret@db:5432/payments"
    assert settings.rabbitmq_url == "amqp://rmq:secret@mq:5672/"

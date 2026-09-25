from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Читает настройки из переменных окружения и файла .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: str
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str
    postgres_port: int
    rabbitmq_user: str
    rabbitmq_password: str
    rabbitmq_host: str
    rabbitmq_port: int

    @property
    def database_url(self) -> str:
        """Собирает адрес Postgres из полей .env."""
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def rabbitmq_url(self) -> str:
        """Собирает адрес RabbitMQ из полей .env."""
        user = quote_plus(self.rabbitmq_user)
        password = quote_plus(self.rabbitmq_password)
        return f"amqp://{user}:{password}@{self.rabbitmq_host}:{self.rabbitmq_port}/"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Возвращает один экземпляр настроек на процесс."""
    return Settings()

# Payment service

Асинхронный микросервис процессинга платежей. Принимает запрос на оплату, сохраняет платёж и публикует событие через outbox в RabbitMQ. Consumer эмулирует шлюз и шлёт результат на webhook.

Сейчас в репозитории каркас: зависимости, линтеры и слои DDD. Бизнес-эндпоинты, миграции и Docker — следующими шагами.

## Требования

- Python 3.10+
- Poetry 2

## Локальный запуск

```powershell
poetry install
poetry run uvicorn app.main:app --reload
```

Версия сервиса задаётся в `pyproject.toml` и отдаётся в `GET /health`.

Проверка живости: `GET http://127.0.0.1:8000/health` → `{"status":"ok","version":"0.1.0"}`.

Скопируйте `.env.example` в `.env`, когда появятся Postgres и RabbitMQ.

## Проверки

```powershell
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy app
poetry run pytest
```

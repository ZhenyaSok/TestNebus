# Payment service

Асинхронный сервис приёма платежей. `POST /api/v1/payments` сохраняет платёж и событие `payments.new` в таблицу `outbox` одной транзакцией. Consumer публикует событие в RabbitMQ, проводит его через шлюз и шлёт webhook.

Версия задаётся в `pyproject.toml` и видна в `GET /health`.

## Запуск

Нужны Docker и Poetry 2.

```powershell
poetry lock
poetry install
docker compose up --build
```

API: `http://127.0.0.1:8000`. Ключ и доступ к базе берутся из `.env`.

Остановка: `docker compose down`. Данные Postgres лежат в томе `postgres_data`, их удаляет `docker compose down -v`.

## Пример

```powershell
Get-Content .env | ForEach-Object {
  if ($_ -match '^(.*?)=(.*)$') { Set-Item -Path "env:$($matches[1])" -Value $matches[2] }
}

$body = @{
  amount = "10.50"
  currency = "RUB"
  description = "order"
  metadata = @{ order = "42" }
  webhook_url = "https://httpbin.org/post"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/payments `
  -Headers @{ "X-API-Key" = $env:API_KEY; "Idempotency-Key" = "order-1" } `
  -ContentType "application/json" `
  -Body $body
```

Ответ `202`: `payment_id`, `status`, `created_at`.

Повтор с тем же `Idempotency-Key` и тем же телом возвращает тот же `payment_id`. Другое тело с тем же ключом — `409`.

Через несколько секунд статус становится `succeeded` или `failed` (шлюз: 90% и 10%). Webhook уходит на `webhook_url` одним POST. Если адрес не отвечает `200`, сообщение возвращается через очередь `payments.new.retry` (пауза 1 с, затем 2 с) и после третьей доставки попадает в `payments.new.dlq`. Статус платежа к этому моменту уже записан, шлюз повторно не вызывается.

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/payments/<payment_id> `
  -Headers @{ "X-API-Key" = $env:API_KEY }

docker compose exec postgres psql -U $env:POSTGRES_USER -d $env:POSTGRES_DB -c "select status, published_at from payments p join outbox o on o.payment_id = p.id;"
```

Очереди видны в панели RabbitMQ: `http://127.0.0.1:15672`. Логин и пароль — `RABBITMQ_USER` и `RABBITMQ_PASSWORD` из `.env`.

## Проверки

Без Docker, на SQLite в памяти:

```powershell
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy app
poetry run pytest
```

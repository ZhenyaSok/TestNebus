# Payment service

Асинхронный сервис приёма платежей. `POST /api/v1/payments` сохраняет платёж и событие `payments.new` в таблицу `outbox` одной транзакцией. Статус после создания — `pending`. Публикация в брокер и обработка платежа в этот процесс не входят.

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
  webhook_url = "https://example.com/hook"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/payments `
  -Headers @{ "X-API-Key" = $env:API_KEY; "Idempotency-Key" = "order-1" } `
  -ContentType "application/json" `
  -Body $body
```

Ответ `202`: `payment_id`, `status`, `created_at`.

Повтор с тем же `Idempotency-Key` и тем же телом возвращает тот же `payment_id`. Другое тело с тем же ключом — `409`.

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/payments/<payment_id> `
  -Headers @{ "X-API-Key" = $env:API_KEY }
```

Строка outbox:

```powershell
docker compose exec postgres psql -U $env:POSTGRES_USER -d $env:POSTGRES_DB -c "select event_type, published_at from outbox;"
```

`published_at` пустой: событие записано, в очередь ещё не ушло.

## Проверки

Без Docker, на SQLite в памяти:

```powershell
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy app
poetry run pytest
```

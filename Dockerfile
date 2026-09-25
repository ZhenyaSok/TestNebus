FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /app

RUN pip install --no-cache-dir "poetry==2.2.1"

COPY pyproject.toml poetry.lock poetry.toml README.md ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

RUN poetry install --without dev --no-ansi

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

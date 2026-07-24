FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md alembic.ini ./
COPY alembic ./alembic
COPY src ./src
RUN pip install .
RUN mkdir -p /data/raw

CMD ["/bin/sh", "-c", "alembic upgrade head && uvicorn btc_engine.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

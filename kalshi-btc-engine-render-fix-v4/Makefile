.PHONY: install test lint migrate api worker up down
install:
	python -m pip install -e '.[dev]'

test:
	pytest -q

lint:
	ruff check src tests

migrate:
	alembic upgrade head

api:
	uvicorn btc_engine.api.main:app --host 0.0.0.0 --port $${PORT:-8000}

worker:
	python -m btc_engine.worker

up:
	docker compose up --build

down:
	docker compose down

web: uvicorn btc_engine.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
worker: python -m btc_engine.worker
release: alembic upgrade head

from btc_engine.config import Settings


def test_kraken_depth_accepts_environment_style_string():
    settings = Settings(kraken_book_depth="100")
    assert settings.kraken_book_depth == 100


def test_kraken_depth_rejects_unsupported_value():
    try:
        Settings(kraken_book_depth="50")
    except ValueError as exc:
        assert "KRAKEN_BOOK_DEPTH" in str(exc)
    else:
        raise AssertionError("Unsupported Kraken depth should fail validation")


def test_render_psycopg2_database_url_is_normalized(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg2://user:pass@host:5432/dbname?sslmode=require",
    )
    settings = Settings(_env_file=None)
    assert settings.database_url == (
        "postgresql+asyncpg://user:pass@host:5432/dbname?sslmode=require"
    )


def test_plain_render_database_url_is_normalized(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:pass@host:5432/dbname",
    )
    settings = Settings(_env_file=None)
    assert settings.database_url == "postgresql+asyncpg://user:pass@host:5432/dbname"

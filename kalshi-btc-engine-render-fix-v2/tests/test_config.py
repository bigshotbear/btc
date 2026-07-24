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

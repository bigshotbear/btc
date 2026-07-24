from __future__ import annotations

from btc_engine.auth.kalshi import KalshiSigner
from btc_engine.config import get_settings


def main() -> None:
    settings = get_settings()
    print(f"Environment: {settings.app_env}")
    print(f"Kalshi environment: {settings.kalshi_env}")
    print(f"Kalshi REST: {settings.kalshi_rest_base}")
    print(f"Kalshi WebSocket: {settings.kalshi_ws_url}")
    print(f"Raw data directory: {settings.raw_data_dir}")
    if settings.kalshi_enable:
        KalshiSigner(settings.kalshi_api_key_id, settings.kalshi_private_key_bytes)
        print("Kalshi RSA key: valid")
    print("Configuration check passed")


if __name__ == "__main__":
    main()

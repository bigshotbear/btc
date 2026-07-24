from __future__ import annotations

import base64
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


class KalshiSigner:
    def __init__(self, api_key_id: str, private_key_bytes: bytes) -> None:
        if not api_key_id:
            raise ValueError("Kalshi API key ID is required")
        key = serialization.load_pem_private_key(private_key_bytes, password=None)
        if not isinstance(key, rsa.RSAPrivateKey):
            raise TypeError("Kalshi private key must be RSA")
        self.api_key_id = api_key_id
        self.private_key = key

    def sign(self, timestamp_ms: str, method: str, path: str) -> str:
        path_without_query = path.split("?", 1)[0]
        message = f"{timestamp_ms}{method.upper()}{path_without_query}".encode()
        signature = self.private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode()

    def headers(self, method: str, path: str) -> dict[str, str]:
        timestamp_ms = str(int(time.time() * 1000))
        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
            "KALSHI-ACCESS-SIGNATURE": self.sign(timestamp_ms, method, path),
        }

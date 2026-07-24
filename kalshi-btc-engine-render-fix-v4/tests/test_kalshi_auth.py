import base64

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from btc_engine.auth.kalshi import KalshiSigner


def test_kalshi_signature_verifies() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    signer = KalshiSigner("test-key", pem)
    timestamp = "1703123456789"
    signature = base64.b64decode(signer.sign(timestamp, "GET", "/trade-api/ws/v2?x=1"))
    key.public_key().verify(
        signature,
        f"{timestamp}GET/trade-api/ws/v2".encode(),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )

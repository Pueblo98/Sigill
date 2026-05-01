"""Kalshi API authentication.

The current (post-2024) Kalshi API uses RSA-PSS-SHA256 signed headers per
request; the legacy email/password ``/login`` endpoint returns 404. To
sign:

    msg = f"{timestamp_ms}{method}{path}"
    sig = base64( RSA-PSS-SHA256(msg, salt_len=DIGEST_LEN, key=private_key) )

    headers = {
        "KALSHI-ACCESS-KEY":       <KALSHI_KEY_ID>,
        "KALSHI-ACCESS-TIMESTAMP": str(timestamp_ms),
        "KALSHI-ACCESS-SIGNATURE": sig,
    }

The same triplet is sent on the WebSocket upgrade. ``path`` is the API
path (e.g. ``/trade-api/v2/markets``) without query string.

Provisioning: kalshi.com → Profile → API Keys → "Create new key" yields
a UUID-shaped key ID and a one-time-download PEM private key file. Drop
both into ``config.py`` (``KALSHI_KEY_ID`` + ``KALSHI_PRIVATE_KEY_PATH``)
or sops-encrypt them into ``secrets.enc.yaml``.
"""
from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


class KalshiAuthError(RuntimeError):
    """Raised when credentials are missing or malformed."""


@dataclass
class KalshiAuthConfig:
    """Resolved auth material. Build via :meth:`from_config`."""

    key_id: str
    private_key: rsa.RSAPrivateKey

    @classmethod
    def from_config(
        cls,
        *,
        key_id: Optional[str],
        private_key_pem: Optional[str] = None,
        private_key_path: Optional[str] = None,
    ) -> "KalshiAuthConfig":
        if not key_id:
            raise KalshiAuthError(
                "Kalshi key ID missing. Set config.KALSHI_KEY_ID."
            )
        pem_bytes: Optional[bytes] = None
        if private_key_pem:
            pem_bytes = private_key_pem.encode("utf-8")
        elif private_key_path:
            p = Path(private_key_path).expanduser()
            if not p.is_file():
                raise KalshiAuthError(
                    f"Kalshi private key path does not exist: {p}"
                )
            pem_bytes = p.read_bytes()
        if pem_bytes is None:
            raise KalshiAuthError(
                "Kalshi private key missing. Set KALSHI_PRIVATE_KEY_PEM "
                "or KALSHI_PRIVATE_KEY_PATH."
            )
        try:
            key = serialization.load_pem_private_key(pem_bytes, password=None)
        except Exception as exc:
            raise KalshiAuthError(f"failed to load Kalshi private key: {exc}") from exc
        if not isinstance(key, rsa.RSAPrivateKey):
            raise KalshiAuthError("Kalshi private key must be RSA")
        return cls(key_id=key_id, private_key=key)


def _sign(private_key: rsa.RSAPrivateKey, message: bytes) -> str:
    """RSA-PSS-SHA256 signature, base64-encoded.

    Salt length = digest length per Kalshi's published auth scheme.
    """
    sig = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(sig).decode("ascii")


def auth_headers(
    auth: KalshiAuthConfig,
    *,
    method: str,
    path: str,
    timestamp_ms: Optional[int] = None,
) -> Dict[str, str]:
    """Build the three-header set Kalshi requires per request.

    ``path`` is the API path with the leading slash, no query string,
    e.g. ``/trade-api/v2/markets``.
    """
    ts = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
    msg = f"{ts}{method.upper()}{path}".encode("utf-8")
    return {
        "KALSHI-ACCESS-KEY": auth.key_id,
        "KALSHI-ACCESS-TIMESTAMP": str(ts),
        "KALSHI-ACCESS-SIGNATURE": _sign(auth.private_key, msg),
    }

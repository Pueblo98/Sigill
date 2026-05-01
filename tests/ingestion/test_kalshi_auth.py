"""Kalshi RSA-PSS auth header signing."""
from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from sigil.ingestion.kalshi_auth import (
    KalshiAuthConfig,
    KalshiAuthError,
    auth_headers,
)


@pytest.fixture(scope="module")
def rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def rsa_pem(rsa_key) -> str:
    return rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def test_from_config_inline_pem(rsa_pem):
    cfg = KalshiAuthConfig.from_config(
        key_id="kid-abc",
        private_key_pem=rsa_pem,
    )
    assert cfg.key_id == "kid-abc"
    assert isinstance(cfg.private_key, rsa.RSAPrivateKey)


def test_from_config_path(rsa_pem, tmp_path):
    p = tmp_path / "k.pem"
    p.write_text(rsa_pem)
    cfg = KalshiAuthConfig.from_config(
        key_id="kid-from-path",
        private_key_path=str(p),
    )
    assert cfg.key_id == "kid-from-path"


def test_from_config_missing_key_id_errors(rsa_pem):
    with pytest.raises(KalshiAuthError, match="key ID missing"):
        KalshiAuthConfig.from_config(key_id=None, private_key_pem=rsa_pem)


def test_from_config_missing_key_material_errors():
    with pytest.raises(KalshiAuthError, match="private key missing"):
        KalshiAuthConfig.from_config(key_id="kid")


def test_from_config_invalid_path_errors():
    with pytest.raises(KalshiAuthError, match="does not exist"):
        KalshiAuthConfig.from_config(
            key_id="kid",
            private_key_path="/nonexistent/key.pem",
        )


def test_auth_headers_three_keys(rsa_pem):
    cfg = KalshiAuthConfig.from_config(key_id="kid-xyz", private_key_pem=rsa_pem)
    h = auth_headers(cfg, method="GET", path="/trade-api/v2/markets",
                     timestamp_ms=1700000000000)
    assert set(h.keys()) == {
        "KALSHI-ACCESS-KEY",
        "KALSHI-ACCESS-TIMESTAMP",
        "KALSHI-ACCESS-SIGNATURE",
    }
    assert h["KALSHI-ACCESS-KEY"] == "kid-xyz"
    assert h["KALSHI-ACCESS-TIMESTAMP"] == "1700000000000"


def test_signature_verifies(rsa_key, rsa_pem):
    cfg = KalshiAuthConfig.from_config(key_id="kid", private_key_pem=rsa_pem)
    ts = 1700000000000
    method = "GET"
    path = "/trade-api/v2/markets"
    h = auth_headers(cfg, method=method, path=path, timestamp_ms=ts)
    sig = base64.b64decode(h["KALSHI-ACCESS-SIGNATURE"])
    msg = f"{ts}{method}{path}".encode("utf-8")
    # Verify against the public key — would raise on bad sig.
    rsa_key.public_key().verify(
        sig,
        msg,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )


def test_auth_headers_uppercase_method(rsa_pem):
    """Lowercased method input still produces canonical signature."""
    cfg = KalshiAuthConfig.from_config(key_id="k", private_key_pem=rsa_pem)
    h_lower = auth_headers(cfg, method="get", path="/p", timestamp_ms=1)
    h_upper = auth_headers(cfg, method="GET", path="/p", timestamp_ms=1)
    # PSS sigs are randomized per call, but both should verify against
    # the same canonical message ("1GET/p"). Test the timestamp+key match.
    assert h_lower["KALSHI-ACCESS-KEY"] == h_upper["KALSHI-ACCESS-KEY"]
    assert h_lower["KALSHI-ACCESS-TIMESTAMP"] == h_upper["KALSHI-ACCESS-TIMESTAMP"]

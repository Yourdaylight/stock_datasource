"""Tests for JWT verification of nps_enhanced tokens (TC-PY-01 through TC-PY-06)."""

import json
import time
import base64
import tempfile
import os

import pytest
from unittest.mock import patch, MagicMock
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rsa_keypair():
    """Generate a temporary RSA key pair for testing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()

    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return private_key, public_key, priv_pem, pub_pem


@pytest.fixture
def wrong_rsa_keypair():
    """Generate a different RSA key pair (for signature mismatch tests)."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    return private_key


@pytest.fixture
def pub_key_file(rsa_keypair, tmp_path):
    """Write the public key to a temp file and return its path."""
    _, _, _, pub_pem = rsa_keypair
    key_file = tmp_path / "test_pub.pem"
    key_file.write_bytes(pub_pem)
    return str(key_file)


def _sign_jwt(private_key, payload: dict) -> str:
    """Create an RS256-signed JWT for testing."""
    header = {"alg": "RS256", "typ": "JWT"}
    enc = base64.urlsafe_b64encode

    def _b64(data: bytes) -> str:
        return enc(data).rstrip(b"=").decode()

    header_b64 = _b64(json.dumps(header).encode())
    payload_b64 = _b64(json.dumps(payload).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()

    signature = private_key.sign(
        signing_input,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    sig_b64 = _b64(signature)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def _make_claims(scope_type="mcp_query", exp_offset=3600):
    """Build standard JWT claims for testing."""
    now = int(time.time())
    return {
        "iss": "test.example.com",
        "sub": "testuser",
        "iat": now,
        "nbf": now,
        "exp": now + exp_offset,
        "scope": {
            "type": scope_type,
            "quota": {"total": 10000, "used": 0, "remaining": 10000},
            "node_id": 1,
        },
        "rev": 1,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestJwtVerifier:
    """TC-PY-01 through TC-PY-06: JWT verifier tests."""

    def test_no_public_key_configured(self):
        """TC-PY-01: verify_nps_jwt returns failure when no public key is configured."""
        # Reset module cache
        import stock_datasource.modules.mcp_api_key.jwt_verifier as mod
        mod._public_key = None
        mod._public_key_path = None

        with patch.object(mod, "_load_public_key", return_value=None):
            ok, claims, err = mod.verify_nps_jwt("some.jwt.token")
            assert ok is False
            assert "not configured" in err.lower() or "public key" in err.lower()

    def test_public_key_file_not_found(self, tmp_path):
        """TC-PY-02: verify_nps_jwt fails when public key file doesn't exist."""
        import stock_datasource.modules.mcp_api_key.jwt_verifier as mod
        mod._public_key = None
        mod._public_key_path = None

        fake_settings = MagicMock()
        fake_settings.MCP_JWT_PUBLIC_KEY_PATH = str(tmp_path / "nonexistent.pem")
        fake_settings.BASE_DIR = str(tmp_path)

        with patch("stock_datasource.modules.mcp_api_key.jwt_verifier.settings", fake_settings, create=True):
            # Reset cache to force re-load
            mod._public_key = None
            mod._public_key_path = None
            result = mod._load_public_key()
            assert result is None

    def test_valid_token_verification(self, rsa_keypair, pub_key_file):
        """TC-PY-03: verify_nps_jwt passes for a validly signed token."""
        private_key, _, _, pub_pem = rsa_keypair

        claims = _make_claims(scope_type="mcp_query")
        token = _sign_jwt(private_key, claims)

        import stock_datasource.modules.mcp_api_key.jwt_verifier as mod
        # Inject the public key directly into cache
        mod._public_key = pub_pem
        mod._public_key_path = pub_key_file

        with patch.object(mod, "_load_public_key", return_value=pub_pem):
            ok, payload, err = mod.verify_nps_jwt(token)
            assert ok is True, f"Expected valid but got err={err}"
            assert err == ""
            assert payload["sub"] == "testuser"
            assert payload["scope"]["type"] == "mcp_query"

    def test_expired_token(self, rsa_keypair, pub_key_file):
        """TC-PY-04: verify_nps_jwt rejects expired tokens."""
        private_key, _, _, pub_pem = rsa_keypair

        claims = _make_claims(exp_offset=-3600)  # expired 1 hour ago
        token = _sign_jwt(private_key, claims)

        import stock_datasource.modules.mcp_api_key.jwt_verifier as mod

        with patch.object(mod, "_load_public_key", return_value=pub_pem):
            ok, _, err = mod.verify_nps_jwt(token)
            assert ok is False
            assert "expired" in err.lower()

    def test_wrong_signature(self, rsa_keypair, wrong_rsa_keypair, pub_key_file):
        """TC-PY-05: verify_nps_jwt rejects tokens signed with wrong key."""
        _, _, _, pub_pem = rsa_keypair  # public key from one pair
        wrong_private = wrong_rsa_keypair  # sign with a different key

        claims = _make_claims()
        token = _sign_jwt(wrong_private, claims)

        import stock_datasource.modules.mcp_api_key.jwt_verifier as mod

        with patch.object(mod, "_load_public_key", return_value=pub_pem):
            ok, _, err = mod.verify_nps_jwt(token)
            assert ok is False
            assert err != ""

    def test_invalid_scope_type(self, rsa_keypair, pub_key_file):
        """TC-PY-06: verify_nps_jwt rejects tokens with invalid scope type."""
        private_key, _, _, pub_pem = rsa_keypair

        claims = _make_claims(scope_type="unknown_type")
        token = _sign_jwt(private_key, claims)

        import stock_datasource.modules.mcp_api_key.jwt_verifier as mod

        with patch.object(mod, "_load_public_key", return_value=pub_pem):
            ok, _, err = mod.verify_nps_jwt(token)
            assert ok is False
            assert "scope" in err.lower() or "invalid" in err.lower()

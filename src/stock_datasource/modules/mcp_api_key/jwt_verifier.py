"""Verify RSA-signed JWT tokens issued by nps_enhanced management platform."""

import base64
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_public_key = None
_public_key_path: Optional[str] = None


def _load_public_key():
    """Load RSA public key from configured path.

    Supports both PEM public key files and auto-detection from settings.
    Returns raw PEM bytes or None if not configured/not found.
    """
    global _public_key, _public_key_path

    from stock_datasource.config.settings import settings

    key_path = getattr(settings, "MCP_JWT_PUBLIC_KEY_PATH", None) or os.environ.get(
        "MCP_JWT_PUBLIC_KEY_PATH"
    )
    if not key_path:
        return None

    # Cache hit
    if _public_key is not None and _public_key_path == key_path:
        return _public_key

    path = Path(key_path)
    if not path.is_absolute():
        # Resolve relative paths from project root
        path = Path(settings.BASE_DIR).parent / path

    if not path.exists():
        logger.error(f"JWT public key not found: {path}")
        return None

    try:
        _public_key = path.read_bytes()
        _public_key_path = key_path
        logger.info(f"Loaded RSA public key from {path}")
        return _public_key
    except Exception as e:
        logger.error(f"Failed to read JWT public key: {e}")
        return None


def verify_nps_jwt(token: str) -> Tuple[bool, dict, str]:
    """Verify JWT token signed by nps_enhanced (RS256).

    This uses the ``cryptography`` and ``PyJWT`` libraries when available,
    falling back to a manual RS256 verification otherwise.

    Returns:
        (is_valid, claims_dict, error_message)
    """
    public_key_pem = _load_public_key()
    if not public_key_pem:
        return False, {}, "RSA public key not configured"

    # --- Try PyJWT first (preferred) ---
    try:
        import jwt as pyjwt

        payload = pyjwt.decode(
            token,
            public_key_pem,
            algorithms=["RS256"],
            options={
                "verify_exp": True,
                "verify_iss": False,
                "verify_aud": False,
            },
        )

        # Validate scope contains mcp_query or is a stock subscription token
        scope = payload.get("scope", {})
        if not isinstance(scope, dict):
            return False, {}, "Invalid token: scope must be a dict"
        scope_type = scope.get("type", "")
        if scope_type not in ("mcp_query", "realtime_stock", ""):
            # Allow stock subscription tokens (no type field, has markets/levels)
            if "markets" not in scope:
                return False, {}, f"Invalid token scope type: {scope_type}"

        return True, payload, ""

    except ImportError:
        logger.debug("PyJWT not available, falling back to manual RS256 verification")
    except Exception as e:
        error_type = type(e).__name__
        if "ExpiredSignature" in error_type:
            return False, {}, "Token expired"
        return False, {}, f"Invalid token: {e}"

    # --- Fallback: manual RS256 verification ---
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, utils

        parts = token.split(".")
        if len(parts) != 3:
            return False, {}, "Malformed JWT: expected 3 parts"

        header_b64, payload_b64, signature_b64 = parts

        # Decode payload
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + "==")
        payload = json.loads(payload_bytes)

        # Check expiration
        exp = payload.get("exp")
        if exp and time.time() > exp:
            return False, {}, "Token expired"

        # Verify signature
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        signature = base64.urlsafe_b64decode(signature_b64 + "==")

        pub_key = serialization.load_pem_public_key(public_key_pem)
        pub_key.verify(
            signature,
            signing_input,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

        return True, payload, ""

    except ImportError:
        return False, {}, "Neither PyJWT nor cryptography library available"
    except Exception as e:
        return False, {}, f"Token verification failed: {e}"

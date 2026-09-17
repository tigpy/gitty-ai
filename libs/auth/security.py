import os
import hmac
import json
import base64
import hashlib
import secrets
import time
from typing import Dict, Any, Tuple, Optional
from libs.config import get_settings

PBKDF2_ITERATIONS = 600_000

def _base64url_encode(data: bytes) -> str:
    """Encode bytes to a base64url-encoded string without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def _base64url_decode(data: str) -> bytes:
    """Decode a base64url-encoded string, restoring required padding."""
    rem = len(data) % 4
    if rem > 0:
        data += '=' * (4 - rem)
    return base64.urlsafe_b64decode(data.encode('utf-8'))

def hash_password(password: str) -> Tuple[str, str]:
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with 600,000 iterations (OWASP recommendation).
    Returns (hex_hash, hex_salt).
    """
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        PBKDF2_ITERATIONS
    )
    return key.hex(), salt

def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """
    Verifies a password against the stored PBKDF2 hash using constant-time comparison.
    """
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        PBKDF2_ITERATIONS
    )
    return hmac.compare_digest(key.hex(), password_hash)

def create_access_token(
    user_id: str,
    username: str,
    expires_delta_seconds: Optional[int] = None,
    expires_delta: Optional[Any] = None
) -> str:
    """
    Generates an RFC 7519 compliant HMAC-SHA256 signed JWT token.
    """
    settings = get_settings()
    secret = getattr(settings, "JWT_SECRET_KEY", "gitty-insecure-dev-secret-change-in-production-32bytesmin").encode('utf-8')

    now = int(time.time())
    if expires_delta is not None:
        if hasattr(expires_delta, "total_seconds"):
            expires_delta_seconds = int(expires_delta.total_seconds())
        else:
            expires_delta_seconds = int(expires_delta)
    elif expires_delta_seconds is None:
        expires_delta_seconds = getattr(settings, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 1440) * 60

    header = {
        "alg": "HS256",
        "typ": "JWT"
    }

    payload = {
        "sub": user_id,
        "username": username,
        "iat": now,
        "exp": now + expires_delta_seconds,
        "jti": secrets.token_hex(8)
    }

    header_b64 = _base64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    payload_b64 = _base64url_encode(json.dumps(payload, separators=(',', ':')).encode('utf-8'))

    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    signature = hmac.new(secret, signing_input, hashlib.sha256).digest()
    signature_b64 = _base64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"

def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodes and verifies an HMAC-SHA256 signed JWT token.
    Raises ValueError on invalid token, signature mismatch, or expiration.
    """
    settings = get_settings()
    secret = getattr(settings, "JWT_SECRET_KEY", "gitty-insecure-dev-secret-change-in-production-32bytesmin").encode('utf-8')

    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError("Invalid JWT structure: token must have 3 segments.")

    header_b64, payload_b64, signature_b64 = parts

    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    expected_sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
    actual_sig = _base64url_decode(signature_b64)

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("JWT signature verification failed.")

    try:
        payload_bytes = _base64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode('utf-8'))
    except Exception as e:
        raise ValueError(f"Malformed JWT payload: {e}")

    now = int(time.time())
    if "exp" in payload and payload["exp"] < now:
        raise ValueError("Token has expired.")

    return payload

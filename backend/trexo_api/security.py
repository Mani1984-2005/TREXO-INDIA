"""Authentication and error primitives.

A compact, dependency-free HMAC-signed bearer token is used so the prototype
does not need a session store.  Tokens are signed server-side; the passcode and
secret never reach the browser.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import logging
from typing import Any

from fastapi import Header, HTTPException, status

from .config import (
    ADMIN_TOKEN,
    AUTH_SECRET,
    OWNER_PASSCODE,
    OWNER_PASSCODE_HASH,
    TOKEN_TTL_SECONDS,
)

logger = logging.getLogger("trexo.api.security")


class ApiError(Exception):
    """Application error carrying a stable machine code."""

    def __init__(self, code: str, message: str, status_code: int = 400, details: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _sign(payload: bytes) -> str:
    return _b64(hmac.new(AUTH_SECRET.encode(), payload, hashlib.sha256).digest())


def create_token(subject: str = "owner", ttl: int | None = None) -> str:
    ttl = TOKEN_TTL_SECONDS if ttl is None else ttl
    payload = json.dumps({"sub": subject, "exp": int(time.time()) + ttl}).encode()
    return f"{_b64(payload)}.{_sign(payload)}"


def verify_token(token: str) -> dict:
    try:
        body, sig = token.split(".", 1)
        payload = _unb64(body)
    except (ValueError, TypeError) as exc:
        raise ApiError("INVALID_TOKEN", "Bearer token is malformed", 401) from exc
    if not hmac.compare_digest(sig, _sign(payload)):
        raise ApiError("INVALID_TOKEN", "Bearer token signature is invalid", 401)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ApiError("INVALID_TOKEN", "Bearer token payload is invalid", 401) from exc
    if int(data.get("exp", 0)) < int(time.time()):
        raise ApiError("TOKEN_EXPIRED", "Bearer token has expired", 401)
    return data


def check_passcode(password: str) -> bool:
    if OWNER_PASSCODE_HASH:
        try:
            algorithm, iterations_text, salt_text, digest_text = OWNER_PASSCODE_HASH.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            iterations = int(iterations_text)
            salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
            candidate = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt, iterations
            )
            expected = base64.urlsafe_b64decode(digest_text + "=" * (-len(digest_text) % 4))
            return hmac.compare_digest(candidate, expected)
        except (TypeError, ValueError):
            return False
    if not OWNER_PASSCODE:
        return False
    return hmac.compare_digest(password.encode(), OWNER_PASSCODE.encode())


async def require_auth(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_REQUIRED", "message": "Bearer token required"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return verify_token(authorization.split(" ", 1)[1].strip())
    except ApiError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Model-management guard.  Disabled entirely when no admin token is set."""
    if not ADMIN_TOKEN:
        logger.warning("Administrative operation rejected: admin credential is not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "ADMIN_DISABLED", "message": "Model management is disabled: set TREXO_ADMIN_TOKEN"},
        )
    if not x_admin_token or not hmac.compare_digest(x_admin_token, ADMIN_TOKEN):
        logger.warning("Administrative operation rejected: invalid or missing admin credential")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ADMIN_FORBIDDEN", "message": "Valid X-Admin-Token required"},
        )

"""Authentication helpers shared by the control API and key management.

Two credential types:
  * the **admin token** (a shared env secret) gates every write/control op;
  * **API keys** (generated here, stored hashed) authenticate router inference.

Only the SHA-256 hash of an API key is ever persisted — the plaintext is shown
to the operator exactly once, at creation.
"""
from __future__ import annotations

import hashlib
import secrets

from fastapi import Header, HTTPException, Request, status

KEY_PREFIX = "sk-llmops-"


def hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Return (plaintext, key_hash, display_prefix) for a fresh API key."""
    plaintext = KEY_PREFIX + secrets.token_urlsafe(24)
    display = f"{plaintext[: len(KEY_PREFIX) + 4]}…{plaintext[-4:]}"
    return plaintext, hash_key(plaintext), display


def extract_token(authorization: str | None, x_admin_token: str | None) -> str | None:
    """Pull a bearer token from either the Authorization or X-Admin-Token header."""
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if x_admin_token:
        return x_admin_token.strip()
    return None


def require_admin(
    request: Request,
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    """Dependency that gates a write op. No-op when auth is disabled (no token
    configured) so local dev stays frictionless; otherwise demands the token."""
    settings = request.app.state.settings
    if not settings.auth_enabled:
        return
    token = extract_token(authorization, x_admin_token)
    if not token or not secrets.compare_digest(token, settings.admin_token):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "admin authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

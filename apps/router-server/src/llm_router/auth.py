"""API-key authentication for inference endpoints.

Enforcement is opt-in via ``LLMOPS_REQUIRE_API_KEY`` so local/dev stays open.
When on, a request must carry ``Authorization: Bearer <token>`` where the token
is either the shared admin token (``LLMOPS_ADMIN_TOKEN``, used by the dashboard
itself) or a non-revoked API key minted by the backend. The resolved key name
is returned so the request can be attributed in the telemetry store.

A tiny in-process TTL cache keeps the hot inference path off SQLite for repeat
keys; revocation therefore takes effect within ``_CACHE_TTL`` seconds.
"""
from __future__ import annotations

import hashlib
import os
import time
from collections import deque

from fastapi import HTTPException, Request, status

_CACHE_TTL = 30.0
# hash -> (key_id_or_None, name, rpm_limit_or_None, expires_at)
_cache: dict[str, tuple[int | None, str, int | None, float]] = {}
# key name -> request timestamps in the trailing 60s (sliding-window limiter)
_hits: dict[str, deque] = {}


def _check_rate(name: str, rpm_limit: int | None) -> None:
    if not rpm_limit:
        return
    now = time.monotonic()
    dq = _hits.setdefault(name, deque())
    while dq and dq[0] <= now - 60.0:
        dq.popleft()
    if len(dq) >= rpm_limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"rate limit exceeded for key '{name}' ({rpm_limit}/min)",
            headers={"Retry-After": "60"},
        )
    dq.append(now)


def _hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _require_enabled() -> bool:
    return os.environ.get("LLMOPS_REQUIRE_API_KEY", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _bearer(request: Request) -> str | None:
    h = request.headers.get("authorization", "")
    return h[7:].strip() if h.lower().startswith("bearer ") else None


async def authenticate(request: Request) -> str | None:
    """Return the attributed key name, or None when auth is disabled.

    Raises 401 when enforcement is on and the bearer token is missing/invalid.
    """
    if not _require_enabled():
        return None

    token = _bearer(request)
    if not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # The dashboard's own admin token is always accepted (attributed "dashboard",
    # never rate-limited).
    admin = os.environ.get("LLMOPS_ADMIN_TOKEN", "").strip()
    if admin and token == admin:
        return "dashboard"

    key_hash = _hash_key(token)
    now = time.monotonic()
    cached = _cache.get(key_hash)
    if cached and cached[3] > now:
        _check_rate(cached[1], cached[2])
        return cached[1]

    store = getattr(request.app.state, "store", None)
    row = await store.get_active_api_key_by_hash(key_hash) if store is not None else None
    if row is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "invalid or revoked API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    _cache[key_hash] = (row["id"], row["name"], row.get("rpm_limit"), now + _CACHE_TTL)
    _check_rate(row["name"], row.get("rpm_limit"))
    return row["name"]

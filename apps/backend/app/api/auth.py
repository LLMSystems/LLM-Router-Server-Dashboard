"""Admin auth status + API-key management (all key mutations are admin-gated)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.auth import generate_api_key, require_admin

router = APIRouter(tags=["auth"])


def _store(request: Request):
    return request.app.state.store


class CreateKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    rpm_limit: int | None = Field(default=None, ge=1)  # requests/min; None = unlimited


@router.get("/auth/status")
async def auth_status(request: Request):
    """Public: lets the UI decide whether to prompt for the admin token."""
    return {"auth_enabled": request.app.state.settings.auth_enabled}


@router.post("/auth/verify", dependencies=[Depends(require_admin)])
async def auth_verify():
    """200 iff the supplied admin token is valid (or auth is disabled)."""
    return {"ok": True}


@router.get("/keys", dependencies=[Depends(require_admin)])
async def list_keys(request: Request):
    store = _store(request)
    keys = await store.list_api_keys()
    usage = await store.api_key_usage()
    for k in keys:
        u = usage.get(k["name"], {})
        k["request_count"] = u.get("request_count", 0)
        k["total_tokens"] = u.get("total_tokens", 0)
        k["usage_last_ts"] = u.get("last_ts")
    return keys


@router.post("/keys", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
async def create_key(body: CreateKeyRequest, request: Request):
    """Mint a key. The plaintext is returned **once** — it is never stored."""
    plaintext, key_hash, prefix = generate_api_key()
    key_id = await _store(request).create_api_key(
        body.name.strip(), key_hash, prefix, rpm_limit=body.rpm_limit
    )
    return {"id": key_id, "name": body.name.strip(), "prefix": prefix, "key": plaintext}


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_admin)])
async def revoke_key(key_id: int, request: Request):
    if not await _store(request).revoke_api_key(key_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown or already-revoked key: {key_id}")
